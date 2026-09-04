"""Service: ẩn PII khách hàng với khối lab + luồng xin/duyệt quyền xem (m26).

Nghiệp vụ:
- Khối lab (staff, lab_manager) KHÔNG thấy thông tin khách hàng của phiếu nhận mẫu
  (tên KH, mã số thuế, địa chỉ, người liên hệ, email, điện thoại) — nhận diện qua MÃ PHIẾU.
- Muốn xem → gửi yêu cầu tới Phòng nhận mẫu; được duyệt thì quyền xem là VĨNH VIỄN
  cho (phiếu đó × phòng của người xin).
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found
from app.models.department import Department
from app.models.sample_flow import CustomerInfoRequest, SampleIntake
from app.models.user import User
from app.services import audit_service, notification_service

# Vai trò bị ẩn PII (khối lab). Các vai trò khác xem bình thường.
MASKED_ROLES = ("staff", "lab_manager")
# Vai trò được duyệt yêu cầu (Phòng nhận mẫu + quản trị).
APPROVER_ROLES = ("reception", "admin")
# Các field PII bị ẩn.
PII_FIELDS = ("customer_name", "address", "tax_code", "contact_person", "phone", "email")
# m33 — khoá ngoại tới master data: KHÔNG che thì khối lab lấy id gọi GET /customers/{id}
# (staff và lab_manager đều nằm trong read_roles của router customers) là đọc lại được
# đúng những field vừa che ở trên. Xoá hẳn khỏi payload thay vì gắn placeholder vì đây
# là UUID, không phải chuỗi hiển thị.
PII_ID_FIELDS = ("customer_id",)

MASK_PLACEHOLDER = "••• Đã ẩn •••"

# m45 — thời hạn mặc định của một lượt duyệt xem thông tin khách hàng.
GRANT_TTL_DAYS = 90


def _forbidden(msg: str = "Bạn không có quyền thực hiện thao tác này") -> AppException:
    return AppException(ErrorCode.FORBIDDEN, msg, 403)


def is_masked_role(user: CurrentUser) -> bool:
    return user.role in MASKED_ROLES


def has_access(db: Session, user: CurrentUser, intake_id: uuid.UUID) -> bool:
    """Phòng của user đã được duyệt xem thông tin KH của phiếu này chưa?"""
    if not is_masked_role(user):
        return True
    if user.department_id is None:
        return False
    now = datetime.now(timezone.utc)
    row = db.execute(
        select(CustomerInfoRequest.id).where(
            CustomerInfoRequest.intake_id == intake_id,
            CustomerInfoRequest.department_id == user.department_id,
            CustomerInfoRequest.status == "approved",
            # m45 — quyền có thời hạn và thu hồi được. NULL = vĩnh viễn (bản ghi cũ,
            # cố ý không backfill để không cắt quyền của phòng đang làm dở).
            CustomerInfoRequest.revoked_at.is_(None),
            (CustomerInfoRequest.expires_at.is_(None))
            | (CustomerInfoRequest.expires_at > now),
        ).limit(1)
    ).first()
    return row is not None


def _pending_request(db: Session, intake_id: uuid.UUID, dept_id: Optional[uuid.UUID]):
    if dept_id is None:
        return None
    return db.execute(
        select(CustomerInfoRequest).where(
            CustomerInfoRequest.intake_id == intake_id,
            CustomerInfoRequest.department_id == dept_id,
            CustomerInfoRequest.status == "pending",
        ).limit(1)
    ).scalars().first()


def mask_intake(db: Session, user: CurrentUser, data: dict) -> dict:
    """Ẩn PII trong dict phiếu nhận mẫu nếu user thuộc khối lab và chưa được duyệt.

    Thêm cờ cho FE: customer_info_masked, customer_info_request_status.
    """
    intake_id = data.get("id")
    if not is_masked_role(user) or (intake_id and has_access(db, user, intake_id)):
        data["customer_info_masked"] = False
        return data

    for f in PII_FIELDS:
        if f in data:
            data[f] = MASK_PLACEHOLDER if data[f] else None
    for f in PII_ID_FIELDS:
        if f in data:
            data[f] = None
    # Tệp đính kèm của phiếu là bản scan BM 7.1.01 ĐÃ ĐIỀN — nó chứa đúng những
    # trường vừa che ở trên. Trả danh sách id ra là trao sẵn khoá cho đường vòng
    # GET /attachments/{id}. Guard trong attachment_authz chặn lượt tải, còn đây
    # chặn từ đầu: không đưa id thì không có gì để thử.
    if "files" in data:
        data["files"] = []
    data["customer_info_masked"] = True
    pending = _pending_request(db, intake_id, user.department_id) if intake_id else None
    data["customer_info_request_status"] = "pending" if pending else None
    return data


def mask_dispatch(db: Session, user: CurrentUser, data: dict) -> dict:
    """Ẩn customer_name trong dict phiếu chuyển (dispatch)."""
    intake_id = data.get("intake_id")
    if not is_masked_role(user) or (intake_id and has_access(db, user, intake_id)):
        return data
    if data.get("customer_name"):
        data["customer_name"] = MASK_PLACEHOLDER
    # CỐ Ý không xoá `files` ở đây, khác với mask_intake(). Tệp của LƯỢT CHUYỂN là sản
    # phẩm của chính phòng lab — số liệu thô, ảnh, báo cáo họ vừa đính kèm khi nhập
    # kết quả. Ẩn đi là chặn họ đọc lại việc của mình. Tệp chứa PII khách hàng là bản
    # scan BM 7.1.01, và nó gắn vào PHIẾU NHẬN chứ không phải lượt chuyển.
    data["customer_info_masked"] = True
    return data


def _serialize(db: Session, r: CustomerInfoRequest) -> dict:
    intake = db.get(SampleIntake, r.intake_id)
    requester = db.get(User, r.requester_user_id)
    dept = db.get(Department, r.department_id) if r.department_id else None
    decider = db.get(User, r.decided_by) if r.decided_by else None
    return {
        "id": r.id,
        "intake_id": r.intake_id,
        "intake_code": intake.code if intake else None,
        "requester_user_id": r.requester_user_id,
        "requester_name": requester.full_name if requester else None,
        "department_id": r.department_id,
        "department_name": dept.name if dept else None,
        "reason": r.reason,
        "status": r.status,
        "decided_by": r.decided_by,
        "decided_by_name": decider.full_name if decider else None,
        "decided_at": r.decided_at,
        "decide_note": r.decide_note,
        "expires_at": r.expires_at,
        "revoked_at": r.revoked_at,
        "created_at": r.created_at,
    }


def create_request(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, reason: Optional[str],
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Khối lab gửi yêu cầu xin xem thông tin KH của 1 phiếu."""
    if not is_masked_role(user):
        raise _forbidden("Chỉ phòng lab cần gửi yêu cầu xem thông tin khách hàng")
    if user.department_id is None:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Tài khoản chưa gắn phòng ban", 400)

    intake = db.get(SampleIntake, intake_id)
    if intake is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")

    if has_access(db, user, intake_id):
        raise AppException(
            ErrorCode.ALREADY_GRANTED, "Phòng bạn đã được duyệt xem thông tin của phiếu này", 409
        )
    existing = _pending_request(db, intake_id, user.department_id)
    if existing is not None:
        raise AppException(
            ErrorCode.DUPLICATE_REQUEST, "Đã có yêu cầu đang chờ Phòng nhận mẫu duyệt", 409
        )

    r = CustomerInfoRequest(
        intake_id=intake_id,
        requester_user_id=user.id,
        department_id=user.department_id,
        reason=(reason or None),
        status="pending",
    )
    db.add(r)
    db.flush()

    # Thông báo cho Phòng nhận mẫu (người đã nhận phiếu) — KHÔNG kèm PII trong body.
    if intake.received_by:
        notification_service.create_notification(
            db, user_id=intake.received_by, type="CUSTOMER_INFO_REQUEST",
            title="Yêu cầu xem thông tin khách hàng",
            body=f"Phiếu {intake.code} — {user.full_name} xin xem thông tin khách hàng.",
            ref_type="sample_intake", ref_id=intake_id,
        )
    audit_service.log_action(
        db, action="CUSTOMER_INFO_REQUEST_CREATE", resource="customer_info_request",
        user_id=user.id, resource_id=r.id, correlation_id=correlation_id, ip=ip,
        detail={"intake_code": intake.code},
    )
    db.commit()
    db.refresh(r)
    return _serialize(db, r)


def list_requests(
    db: Session, *, user: CurrentUser, status: Optional[str], intake_id: Optional[uuid.UUID],
    page: int, limit: int,
) -> tuple[list[dict], int]:
    """Người duyệt (reception/admin) thấy tất cả; khối lab chỉ thấy yêu cầu của phòng mình."""
    from sqlalchemy import func

    q = select(CustomerInfoRequest)
    cq = select(func.count()).select_from(CustomerInfoRequest)
    conds = []
    if user.role not in APPROVER_ROLES and user.role not in ("leader", "qms"):
        if user.department_id is None:
            return [], 0
        conds.append(CustomerInfoRequest.department_id == user.department_id)
    if status:
        conds.append(CustomerInfoRequest.status == status)
    if intake_id:
        conds.append(CustomerInfoRequest.intake_id == intake_id)
    for c in conds:
        q = q.where(c)
        cq = cq.where(c)
    total = db.execute(cq).scalar_one()
    rows = db.execute(
        q.order_by(CustomerInfoRequest.created_at.desc())
        .offset((page - 1) * limit).limit(limit)
    ).scalars().all()
    return [_serialize(db, r) for r in rows], total


def decide_request(
    db: Session, *, user: CurrentUser, request_id: uuid.UUID, approve: bool,
    note: Optional[str], correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Phòng nhận mẫu duyệt / từ chối yêu cầu."""
    if user.role not in APPROVER_ROLES:
        raise _forbidden("Chỉ Phòng nhận mẫu (hoặc Quản trị) được duyệt yêu cầu này")

    r = db.get(CustomerInfoRequest, request_id)
    if r is None:
        raise not_found("Không tìm thấy yêu cầu")
    if r.status != "pending":
        raise AppException(ErrorCode.INVALID_STATE, "Yêu cầu đã được xử lý", 409)

    r.status = "approved" if approve else "rejected"
    r.decided_by = user.id
    r.decided_at = datetime.now(timezone.utc)
    if approve:
        # 90 ngày: đủ dài cho một phiếu chạy hết vòng đời, đủ ngắn để quyền không
        # tồn tại mãi sau khi người xin đã chuyển việc.
        r.expires_at = r.decided_at + timedelta(days=GRANT_TTL_DAYS)
    r.decide_note = note or None
    r.updated_at = datetime.now(timezone.utc)

    intake = db.get(SampleIntake, r.intake_id)
    notification_service.create_notification(
        db, user_id=r.requester_user_id,
        type="CUSTOMER_INFO_DECIDED",
        title="Đã duyệt xem thông tin khách hàng" if approve else "Từ chối xem thông tin khách hàng",
        body=(
            f"Phiếu {intake.code if intake else ''}: "
            + ("bạn đã được xem thông tin khách hàng." if approve else f"bị từ chối. {note or ''}")
        ).strip(),
        ref_type="sample_intake", ref_id=r.intake_id,
    )
    audit_service.log_action(
        db, action="CUSTOMER_INFO_REQUEST_APPROVE" if approve else "CUSTOMER_INFO_REQUEST_REJECT",
        resource="customer_info_request", user_id=user.id, resource_id=r.id,
        correlation_id=correlation_id, ip=ip,
        detail={"intake_code": intake.code if intake else None},
    )
    db.commit()
    db.refresh(r)
    return _serialize(db, r)
