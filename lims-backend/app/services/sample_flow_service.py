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
from app.core.exceptions import AppException, not_found
from app.models.attachment import Attachment
from app.models.department import Department
from app.models.sample_flow import (
    INTAKE_NEXT, INTAKE_STATUS_LABELS, VALID_PAYMENT_STATUS,
    SampleDispatch, SampleIntake, TestParameter,
)
from app.models.user import User
from app.services import audit_service, customer_info_service, notification_service


def _forbidden(msg: str = "Bạn không có quyền thực hiện thao tác này") -> AppException:
    return AppException(ErrorCode.FORBIDDEN, msg, 403)


def _privileged(user: CurrentUser) -> bool:
    return user.role in ("admin", "leader", "qms", "reception")


def _next_intake_code(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    like = f"NM-{year}-%"
    n = db.execute(
        select(func.count()).select_from(SampleIntake).where(SampleIntake.code.like(like))
    ).scalar_one()
    return f"NM-{year}-{n + 1:04d}"


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
        "customer_name": it.customer_name,
        "contact": it.contact,
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
        "result_language": it.result_language,
        "return_method": it.return_method,
        "fee_note": it.fee_note,
        "other_request": it.other_request,
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
    it = SampleIntake(
        code=_next_intake_code(db),
        status="received",
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
    for k, v in changes.items():
        setattr(it, k, v)
    it.updated_by = user.id
    audit_service.log_action(
        db, action="INTAKE_UPDATE", resource="sample_intake", user_id=user.id,
        resource_id=it.id, correlation_id=correlation_id, ip=ip, detail=changes,
    )
    db.commit()
    db.refresh(it)
    return _serialize_intake(db, it, user=user)


# ===== Dispatches =====
def _lab_targets(db: Session, dept_id: uuid.UUID) -> list[uuid.UUID]:
    """Người nhận thông báo của phòng: ưu tiên trưởng phòng, không có thì mọi thành viên."""
    dept = db.get(Department, dept_id)
    if dept and dept.lead_user_id:
        return [dept.lead_user_id]
    return db.execute(
        select(User.id).where(User.department_id == dept_id, User.status == "active")
    ).scalars().all()


def _notify_lab_batch(
    db: Session, dept_id: uuid.UUID, intake: SampleIntake, dispatches: list[SampleDispatch]
) -> None:
    """Gộp 1 thông báo cho nhiều chỉ tiêu cùng chuyển tới 1 phòng (tránh spam)."""
    if len(dispatches) == 1:
        _notify_lab(db, dept_id, intake, dispatches[0])
        return
    names = ", ".join(d.chi_tieu for d in dispatches)[:200]
    for uid in _lab_targets(db, dept_id):
        notification_service.create_notification(
            db, user_id=uid, type="SAMPLE_DISPATCHED",
            title=f"{len(dispatches)} chỉ tiêu mới được chuyển đến phòng",
            body=f"{intake.code} · {names}",
            ref_type="sample_dispatch", ref_id=dispatches[0].id,
        )


def _notify_lab(db: Session, dept_id: uuid.UUID, intake: SampleIntake, dispatch: SampleDispatch) -> None:
    """Báo phòng lab: ưu tiên trưởng phòng; nếu không có thì báo mọi thành viên."""
    dept = db.get(Department, dept_id)
    targets: list[uuid.UUID] = []
    if dept and dept.lead_user_id:
        targets = [dept.lead_user_id]
    else:
        targets = db.execute(
            select(User.id).where(User.department_id == dept_id, User.status == "active")
        ).scalars().all()
    for uid in targets:
        notification_service.create_notification(
            db, user_id=uid, type="SAMPLE_DISPATCHED",
            title="Mẫu mới được chuyển đến phòng",
            body=f"{intake.code} · chỉ tiêu: {dispatch.chi_tieu[:120]}",
            ref_type="sample_dispatch", ref_id=dispatch.id,
        )


def _build_dispatch(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, chi_tieu: Optional[str],
    target_department_id: uuid.UUID, note: Optional[str],
    don_vi: Optional[str], phuong_phap: Optional[str], test_parameter_id: Optional[uuid.UUID],
    sample_name: Optional[str] = None, quantity: Optional[int] = None,
) -> SampleDispatch:
    """Dựng 1 dòng phiếu chuyển (CHƯA commit, CHƯA notify) — dùng cho cả tạo lẻ và tạo loạt."""
    dept = db.get(Department, target_department_id)
    if dept is None:
        raise AppException(ErrorCode.DEPARTMENT_NOT_FOUND, "Phòng lab không tồn tại", 404)

    # m27: chọn từ danh mục chỉ tiêu → lấy tên/phương pháp/đơn giá; hoặc nhập tự do.
    unit_price = None
    if test_parameter_id is not None:
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

    d = SampleDispatch(
        intake_id=intake_id,
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
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    it = db.get(SampleIntake, intake_id)
    if it is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")

    d = _build_dispatch(
        db, user=user, intake_id=intake_id, chi_tieu=chi_tieu,
        target_department_id=target_department_id, note=note,
        don_vi=don_vi, phuong_phap=phuong_phap, test_parameter_id=test_parameter_id,
        sample_name=sample_name, quantity=quantity,
    )
    if it.status in ("received", "quoted", "quote_accepted", "paid"):
        it.status = "dispatched"
    db.flush()
    _notify_lab(db, target_department_id, it, d)
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
        ))
    if it.status in ("received", "quoted", "quote_accepted", "paid"):
        it.status = "dispatched"
    db.flush()

    # Gộp thông báo theo phòng: mỗi phòng nhận 1 thông báo liệt kê các chỉ tiêu.
    by_dept: dict[uuid.UUID, list[SampleDispatch]] = {}
    for d in created:
        by_dept.setdefault(d.target_department_id, []).append(d)
    for dept_id, ds in by_dept.items():
        _notify_lab_batch(db, dept_id, it, ds)

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


def update_dispatch(
    db: Session, *, user: CurrentUser, dispatch_id: uuid.UUID, changes: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    d = db.get(SampleDispatch, dispatch_id)
    if d is None:
        raise not_found("Không tìm thấy phiếu chuyển mẫu")
    # Scope: lab chỉ cập nhật dispatch của phòng mình (admin/leader/reception toàn quyền)
    if not _privileged(user) and user.department_id != d.target_department_id:
        raise _forbidden("Bạn chỉ được cập nhật phiếu chuyển tới phòng của mình")

    new_status = changes.get("status")
    # Trường kết quả BM 7.1.02 + note
    for f in ("note", "don_vi", "phuong_phap", "ket_qua", "can_bo", "sample_name"):
        if changes.get(f) is not None:
            setattr(d, f, changes[f])
    if changes.get("quantity") is not None:
        d.quantity = int(changes["quantity"])

    now = datetime.now(timezone.utc)
    if new_status:
        d.status = new_status
        if new_status == "received" and d.received_at is None:
            d.received_at = now
        if new_status in ("done", "returned"):
            d.completed_at = now
    d.updated_by = user.id
    db.flush()

    # Notify lại phòng nhận mẫu CHỈ khi đổi trạng thái
    if new_status:
        it = db.get(SampleIntake, d.intake_id)
        status_vi = {
            "received": "đã tiếp nhận", "in_progress": "đang thực hiện",
            "done": "đã hoàn thành", "returned": "đã trả lại", "sent": "chờ tiếp nhận",
        }.get(new_status, new_status)
        recipients = {it.created_by, it.received_by} if it else set()
        for uid in recipients:
            if uid and uid != user.id:
                notification_service.create_notification(
                    db, user_id=uid, type="DISPATCH_STATUS",
                    title="Cập nhật trạng thái chuyển mẫu",
                    body=f"{it.code} — {_dept_name(db, d.target_department_id)}: {status_vi}",
                    ref_type="sample_dispatch", ref_id=d.id,
                )
    audit_service.log_action(
        db, action="DISPATCH_UPDATE", resource="sample_dispatch", user_id=user.id,
        resource_id=d.id, correlation_id=correlation_id, ip=ip, detail=changes,
    )
    db.commit()
    db.refresh(d)
    return _serialize_dispatch(db, d, user)


# ===== m28: Trạng thái phiếu + thanh toán =====
def change_status(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, new_status: str,
    note: Optional[str], correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Chuyển trạng thái phiếu theo state machine (chặn nhảy bậc không hợp lệ)."""
    if not _privileged(user):
        raise _forbidden("Chỉ Phòng nhận mẫu / lãnh đạo được đổi trạng thái phiếu")
    it = db.get(SampleIntake, intake_id)
    if it is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")

    allowed = INTAKE_NEXT.get(it.status, ())
    if new_status not in allowed:
        raise AppException(
            ErrorCode.INVALID_TRANSITION,
            f"Không thể chuyển từ '{INTAKE_STATUS_LABELS.get(it.status, it.status)}' sang "
            f"'{INTAKE_STATUS_LABELS.get(new_status, new_status)}'",
            409,
        )
    old = it.status
    it.status = new_status
    if note:
        it.note = f"{it.note}\n{note}" if it.note else note
    it.updated_by = user.id
    it.updated_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db, action="INTAKE_STATUS_CHANGE", resource="sample_intake", user_id=user.id,
        resource_id=it.id, correlation_id=correlation_id, ip=ip,
        detail={"code": it.code, "from": old, "to": new_status},
    )
    db.commit()
    db.refresh(it)
    return _serialize_intake(db, it, user=user)


def update_payment(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, changes: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Ghi nhận thanh toán (khách chuyển khoản): trạng thái + số tiền + mã giao dịch."""
    if not _privileged(user):
        raise _forbidden("Chỉ Phòng nhận mẫu / lãnh đạo được ghi nhận thanh toán")
    it = db.get(SampleIntake, intake_id)
    if it is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")

    ps = changes.get("payment_status")
    if ps is not None:
        if ps not in VALID_PAYMENT_STATUS:
            raise AppException(ErrorCode.VALIDATION_ERROR, "Trạng thái thanh toán không hợp lệ", 400)
        it.payment_status = ps
    for f in ("paid_amount", "payment_date", "payment_ref", "payment_note"):
        if f in changes:
            setattr(it, f, changes[f])
    it.updated_by = user.id
    it.updated_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db, action="INTAKE_PAYMENT_UPDATE", resource="sample_intake", user_id=user.id,
        resource_id=it.id, correlation_id=correlation_id, ip=ip,
        detail={"code": it.code, "payment_status": it.payment_status,
                "paid_amount": str(it.paid_amount) if it.paid_amount is not None else None},
    )
    db.commit()
    db.refresh(it)
    return _serialize_intake(db, it, user=user)
