"""Service Nhận & Chuyển mẫu (GĐ2b).

reception tạo Phiếu nhận → thêm chỉ tiêu (text) chuyển tới phòng lab (Phiếu chuyển)
→ notify lab. Lab đổi status → notify lại reception (người tạo phiếu).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException, conflict, not_found
from app.models.attachment import Attachment
from app.models.customer import Customer
from app.models.department import Department
from app.models.sample_flow import (
    DISPATCH_NEXT, DISPATCH_STATUS_LABELS,
    INTAKE_NEXT, INTAKE_STATUS_LABELS, VALID_PAYMENT_STATUS,
    SampleDispatch, SampleIntake, TestParameter,
)
from app.models.user import User
from app.services import audit_service, customer_info_service, intake_item_service
from app.services import dispatch_result_bridge as result_bridge
from app.services import sample_flow_notify as flow_notify


def _forbidden(msg: str = "Bạn không có quyền thực hiện thao tác này") -> AppException:
    return AppException(ErrorCode.FORBIDDEN, msg, 403)


def _privileged(user: CurrentUser) -> bool:
    return user.role in ("admin", "leader", "qms", "reception")


def _assert_customer_exists(db: Session, customer_id: Optional[uuid.UUID]) -> None:
    """m33 — chặn trước khi đổ **fields vào model, nếu không Postgres ném lỗi FK thô.

    Logic khớp test_request_service.create_request (khách đã xoá mềm = không tồn tại).
    """
    if customer_id is None:
        return
    exists = db.execute(
        select(Customer.id).where(Customer.id == customer_id, Customer.deleted_at.is_(None))
    ).scalar_one_or_none()
    if exists is None:
        raise AppException(ErrorCode.CUSTOMER_NOT_FOUND, "Không tìm thấy khách hàng", 404)


# Field mà PATCH /intakes/{id} được phép ghi. KHÔNG có `status` — đổi trạng thái phải
# qua POST /intakes/{id}/status để đi qua state machine INTAKE_NEXT + kiểm _privileged.
# Cũng KHÔNG có department_id/received_by/created_by (bất biến hoặc do hệ thống đặt).
# `code` CÓ trong danh sách: từ nay nhân viên tự đặt mã phiếu nên phải sửa được khi
# gõ nhầm — nhưng đi qua _resolve_intake_code() để giữ ràng buộc duy nhất.
_UPDATABLE_INTAKE_FIELDS = (
    "code",
    "customer_id",
    "customer_name",
    "description",
    "note",
    "dispatch_note",
    "address",
    "tax_code",
    "contact_person",
    "phone",
    "email",
    "due_date",
    "result_language",
    "return_method",
    "fee_note",
    "other_request",
)


def _next_intake_code(db: Session) -> str:
    """Mã dự phòng khi nhân viên để trống ô "Mã số mẫu" — KHÔNG còn là đường mặc định.

    Lấy MAX(số thứ tự)+1 chứ không phải COUNT(*)+1: đếm bản ghi thì chỉ cần xoá một
    phiếu là mã kế tiếp trùng với mã đã cấp, và người dùng nhận 409 từ uq_intake_code
    mà không hiểu vì sao.
    """
    year = datetime.now(timezone.utc).year
    prefix = f"NM-{year}-"
    last = db.execute(
        select(SampleIntake.code).where(SampleIntake.code.like(f"{prefix}%"))
        .order_by(SampleIntake.code.desc()).limit(1)
    ).scalar_one_or_none()
    seq = 1
    if last:
        try:
            seq = int(last.rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            # Mã do người dùng tự đặt có thể không theo khuôn — bỏ qua, không để
            # một mã lạ làm hỏng đường sinh mã dự phòng.
            seq = 1
    return f"{prefix}{seq:04d}"


def _resolve_intake_code(
    db: Session, raw: Optional[str], *, exclude_id: Optional[uuid.UUID] = None
) -> str:
    """Chuẩn hoá mã phiếu do nhân viên nhập; bỏ trống thì sinh mã dự phòng.

    Kiểm trùng ở tầng service để trả 409 có thông báo tiếng Việt, thay vì để
    UniqueConstraint uq_intake_code nổ IntegrityError thành 500.
    """
    code = (raw or "").strip()
    if not code:
        return _next_intake_code(db)
    conds = [SampleIntake.code == code]
    if exclude_id is not None:
        conds.append(SampleIntake.id != exclude_id)
    dup = db.execute(select(SampleIntake.id).where(*conds)).scalar_one_or_none()
    if dup is not None:
        raise conflict(ErrorCode.DUPLICATE_CODE, f"Mã phiếu '{code}' đã tồn tại")
    return code


def _parse_due_date(raw: Optional[str]):
    """Chuyển ô "ngày hẹn trả" (text tự do) sang kiểu ngày, hoặc None (m39).

    Ô gốc `due_date` GIỮ NGUYÊN thứ nhân viên gõ — nó đã in ra phiếu. Cột `due_date_at`
    chỉ là bản so sánh được để tính quá hạn; không phân giải nổi ("cuối tháng 3") thì
    để None, KHÔNG đoán, vì một hạn sai âm thầm còn tệ hơn không có hạn.
    """
    s = (raw or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _files_of(db: Session, owner_type: str, owner_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(Attachment).where(
            Attachment.owner_type == owner_type,
            Attachment.owner_id == owner_id,
            Attachment.deleted_at.is_(None),
        ).order_by(Attachment.uploaded_at.desc())
    ).scalars().all()
    return [
        {"id": a.id, "file_name": a.file_name, "mime": a.mime, "size": a.size,
         "uploaded_at": a.uploaded_at}
        for a in rows
    ]


def _dept_name(db: Session, dept_id: Optional[uuid.UUID]) -> Optional[str]:
    if not dept_id:
        return None
    d = db.get(Department, dept_id)
    return d.name if d else None


def _serialize_dispatch(db: Session, d: SampleDispatch, user: Optional[CurrentUser] = None) -> dict:
    intake = db.get(SampleIntake, d.intake_id)
    data = {
        "id": d.id,
        "intake_id": d.intake_id,
        "intake_code": intake.code if intake else None,
        "customer_name": intake.customer_name if intake else None,
        "sample_name": d.sample_name,
        "quantity": d.quantity,
        "chi_tieu": d.chi_tieu,
        "don_vi": d.don_vi,
        "phuong_phap": d.phuong_phap,
        "ket_qua": d.ket_qua,
        "can_bo": d.can_bo,
        # m37 — người thực hiện phép thử (từ tài khoản đăng nhập). `can_bo` bên trên
        # là ô text cũ, giữ để đọc phiếu cũ chứ không phải nguồn truy xuất.
        "performed_by": d.performed_by,
        "performed_by_name": (db.get(User, d.performed_by).full_name if d.performed_by else None),
        "performed_at": d.performed_at,
        # Bước hợp lệ kế tiếp — FE dựng đúng danh sách trạng thái chọn được, thay vì
        # cho chọn mọi giá trị rồi để backend từ chối.
        "next_statuses": list(DISPATCH_NEXT.get(d.status, ())),
        "test_parameter_id": d.test_parameter_id,
        "unit_price": str(d.unit_price) if d.unit_price is not None else None,
        "target_department_id": d.target_department_id,
        "target_department_name": _dept_name(db, d.target_department_id),
        "status": d.status,
        "note": d.note,
        "dispatched_by": d.dispatched_by,
        "dispatched_by_name": (db.get(User, d.dispatched_by).full_name if d.dispatched_by else None),
        "dispatched_at": d.dispatched_at,
        "received_at": d.received_at,
        "completed_at": d.completed_at,
        "updated_at": d.updated_at,
        "files": _files_of(db, "sample_dispatch", d.id),
        # m40 — trạng thái duyệt suy TỪ sample_results, không lưu cờ song song.
        **result_bridge.approval_state(db, d),
    }
    # Ẩn tên KH với khối lab chưa được duyệt (m26)
    if user is not None:
        data = customer_info_service.mask_dispatch(db, user, data)
    return data


def _serialize_intake(
    db: Session, it: SampleIntake, with_dispatches: bool = True,
    user: Optional[CurrentUser] = None,
) -> dict:
    data = {
        "id": it.id,
        "code": it.code,
        "customer_id": it.customer_id,
        "customer_name": it.customer_name,
        "description": it.description,
        "note": it.note,
        "status": it.status,
        "status_label": INTAKE_STATUS_LABELS.get(it.status, it.status),
        "payment_status": it.payment_status,
        "paid_amount": str(it.paid_amount) if it.paid_amount is not None else None,
        "payment_date": it.payment_date,
        "payment_ref": it.payment_ref,
        "payment_note": it.payment_note,
        "dispatch_note": it.dispatch_note,
        # Bước hợp lệ kế tiếp (FE dựng nút chuyển trạng thái)
        "next_statuses": list(INTAKE_NEXT.get(it.status, ())),
        "address": it.address,
        "tax_code": it.tax_code,
        "contact_person": it.contact_person,
        "phone": it.phone,
        "email": it.email,
        "due_date": it.due_date,
        "due_date_at": it.due_date_at,
        "result_language": it.result_language,
        "return_method": it.return_method,
        "fee_note": it.fee_note,
        "other_request": it.other_request,
        # m42 — tình trạng & số lượng mẫu, và dấu vết quyết định từ chối.
        "sample_count": it.sample_count,
        "condition_status": it.condition_status,
        "condition_note": it.condition_note,
        "rejected_reason": it.rejected_reason,
        "decided_by_name": (db.get(User, it.decided_by).full_name if it.decided_by else None),
        "decided_at": it.decided_at,
        "department_id": it.department_id,
        "department_name": _dept_name(db, it.department_id),
        "received_by": it.received_by,
        "received_by_name": (db.get(User, it.received_by).full_name if it.received_by else None),
        "received_at": it.received_at,
        "created_at": it.created_at,
        "files": _files_of(db, "sample_intake", it.id),
    }
    if with_dispatches:
        rows = db.execute(
            select(SampleDispatch).where(SampleDispatch.intake_id == it.id)
            .order_by(SampleDispatch.dispatched_at)
        ).scalars().all()
        data["dispatches"] = [_serialize_dispatch(db, d, user) for d in rows]
    # Ẩn PII khách hàng với khối lab chưa được duyệt (m26)
    if user is not None:
        data = customer_info_service.mask_intake(db, user, data)
    return data


# ===== Intakes =====
def list_intakes(
    db: Session, *, user: CurrentUser, q: Optional[str], status: Optional[str],
    page: int, limit: int,
) -> tuple[list[dict], int]:
    conds = []
    if status:
        conds.append(SampleIntake.status == status)
    if q:
        like = f"%{q.strip()}%"
        if customer_info_service.is_masked_role(user):
            # Bộ lọc chạy TRƯỚC khi che, nên khớp theo customer_name biến ô tìm kiếm
            # thành một oracle: gửi ?q=<tên công ty> rồi xem phiếu nào trả về là suy
            # ra chủ mẫu, dù mọi trường đều hiển thị "••• Đã ẩn •••". Khối lab đọc
            # được cả sổ khách qua GET /customers nên có sẵn từ điển tên để dò.
            # Với vai trò bị che, chỉ khớp MÃ PHIẾU — đúng cách m26 muốn họ nhận diện mẫu.
            conds.append(SampleIntake.code.ilike(like))
        else:
            conds.append(SampleIntake.customer_name.ilike(like) | SampleIntake.code.ilike(like))
    # Phòng lab chỉ thấy phiếu có chỉ tiêu chuyển tới phòng mình
    if not _privileged(user):
        if user.department_id is None:
            return [], 0
        sub = select(SampleDispatch.intake_id).where(
            SampleDispatch.target_department_id == user.department_id
        )
        conds.append(SampleIntake.id.in_(sub))
    total = db.execute(select(func.count()).select_from(SampleIntake).where(*conds)).scalar_one()
    rows = db.execute(
        select(SampleIntake).where(*conds)
        .order_by(SampleIntake.received_at.desc())
        .offset((page - 1) * limit).limit(limit)
    ).scalars().all()
    return [_serialize_intake(db, it, with_dispatches=True, user=user) for it in rows], total


def get_intake(db: Session, *, intake_id: uuid.UUID, user: CurrentUser) -> dict:
    it = db.get(SampleIntake, intake_id)
    if it is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")
    return _serialize_intake(db, it, user=user)


def create_intake(
    db: Session, *, user: CurrentUser, fields: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    fields = dict(fields)
    fields["customer_name"] = str(fields.get("customer_name", "")).strip()
    _assert_customer_exists(db, fields.get("customer_id"))
    # Chặn ở service để trả 400 có thông báo nghiệp vụ; nếu để CHECK
    # ck_intake_condition_note của DB bắt thì người dùng nhận 500 không hiểu gì.
    if fields.get("condition_status") == "not_acceptable" and not (
        fields.get("condition_note") or ""
    ).strip():
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            "Mẫu không đạt điều kiện tiếp nhận phải mô tả sai lệch "
            "(thiếu mẫu, sai bao bì, sai nhiệt độ bảo quản…)",
            400,
        )
    code = _resolve_intake_code(db, fields.pop("code", None))
    it = SampleIntake(
        code=code,
        status="received",
        due_date_at=_parse_due_date(fields.get("due_date")),
        department_id=user.department_id,
        received_by=user.id,
        created_by=user.id,
        updated_by=user.id,
        **fields,
    )
    db.add(it)
    db.flush()
    audit_service.log_action(
        db, action="INTAKE_CREATE", resource="sample_intake", user_id=user.id,
        resource_id=it.id, correlation_id=correlation_id, ip=ip, detail={"code": it.code},
    )
    db.commit()
    db.refresh(it)
    return _serialize_intake(db, it, user=user)


def update_intake(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, changes: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    it = db.get(SampleIntake, intake_id)
    if it is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")
    if "customer_id" in changes:
        _assert_customer_exists(db, changes["customer_id"])
    if "code" in changes:
        changes = dict(changes)
        changes["code"] = _resolve_intake_code(db, changes["code"], exclude_id=it.id)
    _assert_intake_editable(it, changes)

    # Giá trị TRƯỚC phải chụp trước vòng ghi bên dưới, nếu không audit chỉ có giá
    # trị mới và không tái dựng được hồ sơ tại thời điểm in (W14).
    _detail = audit_service.diff_detail(
        it, {k: changes[k] for k in _UPDATABLE_INTAKE_FIELDS if k in changes},
        extra={"code": it.code},
    )

    # Danh sách TƯỜNG MINH thay cho `for k, v in changes.items(): setattr(it, k, v)`.
    # Vòng lặp cũ ghi bất cứ khoá nào lọt qua schema — nghĩa là mỗi lần ai đó thêm
    # trường vào UpdateIntakeRequest là nó tự động ghi được, kể cả `status`. Cách làm
    # đúng đã có sẵn trong dự án: quotation_service.update_quotation liệt kê từng field.
    for k in _UPDATABLE_INTAKE_FIELDS:
        if k in changes:
            setattr(it, k, changes[k])
    if "due_date" in changes:
        it.due_date_at = _parse_due_date(changes["due_date"])
    it.updated_by = user.id
    audit_service.log_action(
        db, action="INTAKE_UPDATE", resource="sample_intake", user_id=user.id,
        resource_id=it.id, correlation_id=correlation_id, ip=ip, detail=_detail,
    )
    db.commit()
    db.refresh(it)
    return _serialize_intake(db, it, user=user)


# ===== Dispatches =====
# Trường KHOÁ sau khi phiếu đóng — chúng là danh tính pháp lý của hồ sơ đã phát hành.
# `note` vẫn ghi được: ghi chú bổ sung sau khi trả kết quả là nghiệp vụ bình thường.
_LOCKED_AFTER_CLOSE = tuple(f for f in _UPDATABLE_INTAKE_FIELDS if f != "note")
_CLOSED_STATUSES = ("completed", "cancelled", "rejected")


def _assert_intake_editable(it: SampleIntake, changes: dict) -> None:
    """Phiếu đã đóng thì bản chụp phải đứng yên (W14).

    Nguyên tắc snapshot của m33 bảo vệ phiếu khỏi thay đổi của MASTER DATA, nhưng
    không bảo vệ nó khỏi chỉnh sửa TRỰC TIẾP: `_UPDATABLE_INTAKE_FIELDS` cho sửa cả
    `customer_name`, `tax_code` và `code` ở mọi trạng thái, kể cả 'completed'. Bản
    chụp mà sửa được sau khi phát hành thì không còn giá trị pháp lý.

    `code` khoá SỚM HƠN — ngay khi đã chuyển lab: lúc đó mã đã dán lên mẫu vật lý và
    phòng lab đang cầm nhãn đó.
    """
    if it.status in _CLOSED_STATUSES:
        locked = [f for f in _LOCKED_AFTER_CLOSE if f in changes]
        if locked:
            raise AppException(
                ErrorCode.LOCKED,
                f"Phiếu {it.code} đã ở trạng thái "
                f"'{INTAKE_STATUS_LABELS.get(it.status, it.status)}' — "
                f"không sửa được {', '.join(locked)}. Chỉ ghi chú còn sửa được.",
                409,
            )
    if "code" in changes and it.status not in ("received", "quoted", "quote_accepted", "paid"):
        raise AppException(
            ErrorCode.LOCKED,
            f"Phiếu {it.code} đã chuyển lab — mã phiếu đã dán lên mẫu, không đổi được",
            409,
        )


def _assert_intake_accepts_dispatch(it: SampleIntake) -> None:
    """Chặn giao việc mới trên phiếu đã đóng (m37).

    Trước đây add_dispatch không kiểm trạng thái phiếu: câu `if it.status in (...)`
    chỉ dùng để NÂNG trạng thái, nên với phiếu 'cancelled' dòng chỉ tiêu vẫn được
    tạo và phòng lab vẫn nhận thông báo "Mẫu mới được chuyển đến phòng" — lab làm
    việc trên một phiếu đã hủy mà không ai biết.
    """
    if it.status in ("cancelled", "completed", "rejected"):
        raise AppException(
            ErrorCode.INVALID_STATE,
            f"Phiếu {it.code} đã ở trạng thái "
            f"'{INTAKE_STATUS_LABELS.get(it.status, it.status)}' — không chuyển thêm chỉ tiêu được",
            409,
        )


def _build_dispatch(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, chi_tieu: Optional[str],
    target_department_id: uuid.UUID, note: Optional[str],
    don_vi: Optional[str], phuong_phap: Optional[str], test_parameter_id: Optional[uuid.UUID],
    sample_name: Optional[str] = None, quantity: Optional[int] = None,
    intake_item_id: Optional[uuid.UUID] = None,
) -> SampleDispatch:
    """Dựng 1 dòng phiếu chuyển (CHƯA commit, CHƯA notify) — dùng cho cả tạo lẻ và tạo loạt."""
    dept = db.get(Department, target_department_id)
    if dept is None:
        raise AppException(ErrorCode.DEPARTMENT_NOT_FOUND, "Phòng lab không tồn tại", 404)

    # Ba nguồn cho nội dung một lượt giao việc, xét theo thứ tự ưu tiên:
    #   m38  dòng khách ĐÃ ĐẶT  → tên/giá lấy từ đơn hàng (có thể đã thương lượng)
    #   m27  danh mục chỉ tiêu  → chụp tên/phương pháp/đơn giá từ bảng giá
    #        nhập tay           → chỉ có tên
    unit_price = None
    item = None
    if intake_item_id is not None:
        item = intake_item_service.resolve_for_dispatch(
            db, user=user, intake_id=intake_id, intake_item_id=intake_item_id, fields={},
        )
        chi_tieu = (chi_tieu or "").strip() or item.parameter_name
        phuong_phap, don_vi = phuong_phap or item.method, don_vi or item.unit
        sample_name = sample_name or item.sample_name
        test_parameter_id = test_parameter_id or item.test_parameter_id
        unit_price = item.unit_price
    elif test_parameter_id is not None:
        tp = db.get(TestParameter, test_parameter_id)
        if tp is None:
            raise AppException(ErrorCode.PARAM_NOT_FOUND, "Chỉ tiêu thử nghiệm không tồn tại", 404)
        if not tp.is_active:
            raise AppException(ErrorCode.PARAM_INACTIVE, f"Chỉ tiêu '{tp.name}' đã ngưng sử dụng", 400)
        chi_tieu = (chi_tieu or tp.name).strip()
        phuong_phap = phuong_phap or tp.method
        don_vi = don_vi or tp.unit
        unit_price = tp.unit_price  # chốt giá tại thời điểm chuyển mẫu
    else:
        chi_tieu = (chi_tieu or "").strip()
        if not chi_tieu:
            raise AppException(
                ErrorCode.VALIDATION_ERROR, "Nhập chỉ tiêu hoặc chọn từ danh mục chỉ tiêu", 400
            )

    # m38 — mọi lượt giao việc phải trỏ về một DÒNG ĐẶT HÀNG. Giao việc theo đường cũ
    # (chưa có đơn hàng) thì tự sinh, nên báo giá luôn có nguồn kể cả khi quầy vẫn
    # thao tác theo thói quen cũ.
    if item is None:
        item = intake_item_service.resolve_for_dispatch(
            db, user=user, intake_id=intake_id, intake_item_id=None,
            fields={"test_parameter_id": test_parameter_id, "parameter_name": chi_tieu,
                    "method": phuong_phap, "unit": don_vi,
                    "sample_name": sample_name, "quantity": quantity},
        )
        db.flush()

    d = SampleDispatch(
        intake_id=intake_id,
        intake_item_id=item.id,
        chi_tieu=chi_tieu,
        test_parameter_id=test_parameter_id,
        unit_price=unit_price,
        sample_name=(sample_name or "").strip() or None,
        quantity=quantity or 1,
        target_department_id=target_department_id,
        status="sent",
        note=note,
        don_vi=don_vi,
        phuong_phap=phuong_phap,
        dispatched_by=user.id,
        updated_by=user.id,
    )
    db.add(d)
    return d


def add_dispatch(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, chi_tieu: Optional[str],
    target_department_id: uuid.UUID, note: Optional[str],
    don_vi: Optional[str] = None, phuong_phap: Optional[str] = None,
    test_parameter_id: Optional[uuid.UUID] = None,
    sample_name: Optional[str] = None, quantity: Optional[int] = None,
    intake_item_id: Optional[uuid.UUID] = None,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    it = db.get(SampleIntake, intake_id)
    if it is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")
    _assert_intake_accepts_dispatch(it)

    d = _build_dispatch(
        db, user=user, intake_id=intake_id, chi_tieu=chi_tieu,
        target_department_id=target_department_id, note=note,
        don_vi=don_vi, phuong_phap=phuong_phap, test_parameter_id=test_parameter_id,
        sample_name=sample_name, quantity=quantity, intake_item_id=intake_item_id,
    )
    if it.status in ("received", "quoted", "quote_accepted", "paid"):
        it.status = "dispatched"
    db.flush()
    flow_notify.notify_lab(db, target_department_id, it, d)
    audit_service.log_action(
        db, action="SAMPLE_DISPATCH", resource="sample_dispatch", user_id=user.id,
        resource_id=d.id, correlation_id=correlation_id, ip=ip,
        detail={"intake": it.code, "dept": str(target_department_id)},
    )
    db.commit()
    db.refresh(d)
    return _serialize_dispatch(db, d, user)


def add_dispatches_batch(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, items: list[dict],
    correlation_id: Optional[str], ip: Optional[str],
) -> list[dict]:
    """Chuyển NHIỀU chỉ tiêu trong MỘT giao dịch (m27).

    Mỗi item: {test_parameter_id?, chi_tieu?, target_department_id, note?, don_vi?, phuong_phap?}.
    Nguyên tử: 1 item lỗi → rollback toàn bộ (không để trạng thái nửa vời).
    Thông báo GỘP theo phòng lab (chọn 10 chỉ tiêu cùng phòng → 1 thông báo, không phải 10).
    """
    if not items:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Chưa chọn chỉ tiêu nào để chuyển", 400)
    if len(items) > 100:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Tối đa 100 chỉ tiêu mỗi lần chuyển", 400)

    it = db.get(SampleIntake, intake_id)
    if it is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")
    _assert_intake_accepts_dispatch(it)

    created: list[SampleDispatch] = []
    for item in items:
        created.append(_build_dispatch(
            db, user=user, intake_id=intake_id,
            chi_tieu=item.get("chi_tieu"),
            target_department_id=item["target_department_id"],
            note=item.get("note"),
            don_vi=item.get("don_vi"),
            phuong_phap=item.get("phuong_phap"),
            test_parameter_id=item.get("test_parameter_id"),
            sample_name=item.get("sample_name"),
            quantity=item.get("quantity"),
            intake_item_id=item.get("intake_item_id"),
        ))
    if it.status in ("received", "quoted", "quote_accepted", "paid"):
        it.status = "dispatched"
    db.flush()

    # Gộp thông báo theo phòng: mỗi phòng nhận 1 thông báo liệt kê các chỉ tiêu.
    by_dept: dict[uuid.UUID, list[SampleDispatch]] = {}
    for d in created:
        by_dept.setdefault(d.target_department_id, []).append(d)
    for dept_id, ds in by_dept.items():
        flow_notify.notify_lab_batch(db, dept_id, it, ds)

    audit_service.log_action(
        db, action="SAMPLE_DISPATCH_BATCH", resource="sample_intake", user_id=user.id,
        resource_id=intake_id, correlation_id=correlation_id, ip=ip,
        detail={"intake": it.code, "count": len(created),
                "depts": [str(k) for k in by_dept.keys()]},
    )
    db.commit()
    for d in created:
        db.refresh(d)
    return [_serialize_dispatch(db, d, user) for d in created]


def list_dispatches(
    db: Session, *, user: CurrentUser, status: Optional[str], page: int, limit: int,
) -> tuple[list[dict], int]:
    conds = []
    if status:
        conds.append(SampleDispatch.status == status)
    # Lab chỉ thấy dispatch tới phòng mình; reception/admin/leader/qms thấy tất cả
    if not _privileged(user):
        if user.department_id is None:
            return [], 0
        conds.append(SampleDispatch.target_department_id == user.department_id)
    total = db.execute(select(func.count()).select_from(SampleDispatch).where(*conds)).scalar_one()
    rows = db.execute(
        select(SampleDispatch).where(*conds)
        .order_by(SampleDispatch.dispatched_at.desc())
        .offset((page - 1) * limit).limit(limit)
    ).scalars().all()
    return [_serialize_dispatch(db, d, user) for d in rows], total


def get_dispatch(db: Session, *, dispatch_id: uuid.UUID, user: CurrentUser) -> dict:
    d = db.get(SampleDispatch, dispatch_id)
    if d is None:
        raise not_found("Không tìm thấy phiếu chuyển mẫu")
    return _serialize_dispatch(db, d, user)


def _get_dispatch_or_404(db: Session, dispatch_id: uuid.UUID) -> SampleDispatch:
    d = db.get(SampleDispatch, dispatch_id)
    if d is None:
        raise not_found("Không tìm thấy phiếu chuyển mẫu")
    return d


def update_dispatch(
    db: Session, *, user: CurrentUser, dispatch_id: uuid.UUID, changes: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Phòng nhận mẫu sửa NỘI DUNG HÀNH CHÍNH của lượt chuyển (quyền dispatch:update).

    m37 đã chuyển cột kết quả và trạng thái thực hiện sang update_dispatch_result().
    Hàm này cố ý KHÔNG còn ghi được `ket_qua`/`can_bo`/`status`: gộp chung chính là
    ràng buộc kỹ thuật đã buộc m36 phải cắt quyền ghi kết quả của cả khối lab.
    """
    d = _get_dispatch_or_404(db, dispatch_id)
    # Scope giữ nguyên như trước m37 (admin/leader/reception toàn quyền).
    if not _privileged(user) and user.department_id != d.target_department_id:
        raise _forbidden("Bạn chỉ được cập nhật phiếu chuyển tới phòng của mình")

    detail = audit_service.diff_detail(
        d, {k: v for k, v in changes.items() if v is not None}
    )
    for f in ("note", "sample_name"):
        if changes.get(f) is not None:
            setattr(d, f, changes[f])
    if changes.get("quantity") is not None:
        d.quantity = int(changes["quantity"])
    d.updated_by = user.id

    audit_service.log_action(
        db, action="DISPATCH_UPDATE", resource="sample_dispatch", user_id=user.id,
        resource_id=d.id, correlation_id=correlation_id, ip=ip, detail=detail,
    )
    db.commit()
    db.refresh(d)
    return _serialize_dispatch(db, d, user)


def update_dispatch_result(
    db: Session, *, user: CurrentUser, dispatch_id: uuid.UUID, changes: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Phòng lab ghi KẾT QUẢ + trạng thái thực hiện (quyền dispatch:result, m37).

    Ba điều hàm này bảo đảm mà đường cũ không có:
    1. `performed_by` lấy từ token, KHÔNG nhận từ client — người ghi kết quả là
       người thực hiện phép thử, không ai gõ hộ tên người khác được.
    2. Trạng thái đi theo DISPATCH_NEXT, chặn lùi bước. Trước đây `done → sent`
       hợp lệ nên kết quả đã trả cho khách vẫn viết đè được không để lại vết.
    3. Phiếu đã trả kết quả cho khách thì khoá — sửa phải đi đường phiên bản.
    """
    d = _get_dispatch_or_404(db, dispatch_id)
    # Phạm vi: KTV/trưởng phòng chỉ ghi kết quả cho lượt chuyển tới phòng mình.
    # Cố ý KHÔNG dùng _privileged() ở đây: reception/leader/qms nằm trong đó, mà
    # cho họ ghi kết quả là quay lại đúng chỗ m37 sinh ra để sửa.
    if user.role != "admin" and user.department_id != d.target_department_id:
        raise _forbidden("Bạn chỉ được ghi kết quả cho phiếu chuyển tới phòng của mình")

    it = db.get(SampleIntake, d.intake_id)
    if it is not None and it.status in ("completed", "cancelled"):
        raise AppException(
            ErrorCode.RESULT_LOCKED,
            f"Phiếu {it.code} đã ở trạng thái "
            f"'{INTAKE_STATUS_LABELS.get(it.status, it.status)}' — không sửa được kết quả",
            409,
        )

    # m40 — kết quả ĐÃ DUYỆT là bất biến. Sửa phải đi đường tạo phiên bản mới
    # (POST /results/{id}/revisions) để còn lý do sửa và người chịu trách nhiệm.
    if changes.get("ket_qua") is not None and result_bridge.is_approved(db, d):
        raise AppException(
            ErrorCode.RESULT_LOCKED,
            "Kết quả đã được duyệt — sửa phải tạo phiên bản mới kèm lý do",
            409,
        )

    new_status = changes.get("status")
    if new_status and new_status != d.status:
        allowed = DISPATCH_NEXT.get(d.status, ())
        if new_status not in allowed:
            raise AppException(
                ErrorCode.INVALID_TRANSITION,
                f"Không thể chuyển lượt chuyển mẫu từ "
                f"'{DISPATCH_STATUS_LABELS.get(d.status, d.status)}' sang "
                f"'{DISPATCH_STATUS_LABELS.get(new_status, new_status)}'",
                409,
            )

    # Chụp giá trị TRƯỚC vòng ghi bên dưới — tính sau thì before == after và nhật ký
    # lại chỉ có giá trị mới, đúng thứ W14 sinh ra để sửa.
    _detail = audit_service.diff_detail(
        d, {k: v for k, v in changes.items() if v is not None},
        extra={"performed_by": str(user.id)},
    )

    now = datetime.now(timezone.utc)
    wrote_result = False
    for f in ("don_vi", "phuong_phap", "ket_qua"):
        if changes.get(f) is not None:
            setattr(d, f, changes[f])
            if f == "ket_qua":
                wrote_result = True
    if wrote_result:
        d.performed_by = user.id
        d.performed_at = now
        # Ô text cũ của BM 7.1/02 vẫn in ra phiếu giấy — điền theo danh tính thật
        # thay vì để trống, nhưng nguồn truy xuất là performed_by.
        d.can_bo = user.full_name

    if new_status and new_status != d.status:
        d.status = new_status
        if new_status == "received" and d.received_at is None:
            d.received_at = now
        if new_status in ("done", "returned"):
            d.completed_at = now
    d.updated_by = user.id
    db.flush()

    if new_status:
        flow_notify.notify_reception_status(
            db, d, it, new_status, user.id, _dept_name(db, d.target_department_id)
        )
    audit_service.log_action(
        db, action="DISPATCH_RESULT", resource="sample_dispatch", user_id=user.id,
        resource_id=d.id, correlation_id=correlation_id, ip=ip,
        detail=_detail,
    )
    db.commit()
    db.refresh(d)
    return _serialize_dispatch(db, d, user)


def delete_dispatch(
    db: Session, *, user: CurrentUser, dispatch_id: uuid.UUID,
    correlation_id: Optional[str], ip: Optional[str],
) -> None:
    """Xoá dòng chỉ tiêu chuyển NHẦM phòng/nhầm chỉ tiêu (m37).

    Trước đây không có đường xoá nào: một dòng chuyển nhầm tồn tại vĩnh viễn và chỉ
    sửa được nội dung. Chỉ xoá được khi lab CHƯA tiếp nhận — sau đó đã là việc đang
    làm, xoá đi là mất vết công việc của phòng lab.
    """
    d = _get_dispatch_or_404(db, dispatch_id)
    if d.status != "sent":
        raise AppException(
            ErrorCode.INVALID_STATE,
            f"Phòng lab đã tiếp nhận lượt chuyển này "
            f"('{DISPATCH_STATUS_LABELS.get(d.status, d.status)}') — không xoá được. "
            "Dùng trạng thái 'Đã trả lại' nếu cần hoàn tác.",
            409,
        )
    it = db.get(SampleIntake, d.intake_id)
    audit_service.log_action(
        db, action="DISPATCH_DELETE", resource="sample_dispatch", user_id=user.id,
        resource_id=d.id, correlation_id=correlation_id, ip=ip,
        detail={"intake": it.code if it else None, "chi_tieu": d.chi_tieu,
                "dept": str(d.target_department_id)},
    )
    db.delete(d)
    db.commit()
