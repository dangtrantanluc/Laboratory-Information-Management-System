"""M1 common helpers — RBAC scope, state machine, code generation, error factories.

Tập trung logic dùng chung cho mọi service M1 để khớp contract:
- Cấm Kế toán toàn M1 (FORBIDDEN_ACCOUNTANT).
- Phạm vi phòng ban cho ghi (FORBIDDEN).
- Quyền trưởng nhóm/Admin/Lãnh đạo (assign/approve/finalize) — đọc is_dept_lead (M7).
- State machine whitelist (FR-017, §7.1).
- Sinh request_code / sample_code (RQ-YYYY-NNNN / SP-YYYY-NNNN) idempotent + retry.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found

# ---- State machine whitelist (FR-SAMPLE-017, contract §7.1) ----
# (from_status, to_status) hợp lệ. Ngoài tập này → INVALID_STATE_TRANSITION (422).
STATE_WHITELIST: set[tuple[str, str]] = {
    ("received", "assigned"),
    ("received", "overdue"),
    ("assigned", "testing"),
    ("assigned", "overdue"),
    ("testing", "overdue"),
    ("assigned", "received"),  # hủy phân công cuối → quay về received
    ("testing", "done"),
    ("overdue", "done"),
    ("done", "returned"),
    ("overdue", "assigned"),  # gia hạn deadline (OQ#9)
    ("overdue", "testing"),
}


# ===== Error factories (đồng bộ danh mục error code §3 contract) =====
def forbidden_accountant() -> AppException:
    return AppException(
        "FORBIDDEN_ACCOUNTANT",
        "Kế toán không được phép truy cập module Quản lý Mẫu",
        403,
    )


def forbidden(message: str = "Bạn không có quyền thực hiện thao tác này") -> AppException:
    return AppException("FORBIDDEN", message, 403)


def invalid_state(message: str = "Chuyển trạng thái không hợp lệ") -> AppException:
    return AppException("INVALID_STATE_TRANSITION", message, 422)


# ===== RBAC =====
def deny_accountant(user: CurrentUser) -> None:
    """Cấm Kế toán toàn bộ M1 (B03, BR-014). Gọi đầu mọi endpoint."""
    if user.role == "accountant":
        raise forbidden_accountant()


def is_privileged(user: CurrentUser) -> bool:
    """Admin / Ban lãnh đạo = toàn hệ thống (bỏ qua scope phòng)."""
    return user.role in ("admin", "leader")


def can_lead_action(user: CurrentUser, sample_dept_id: uuid.UUID) -> bool:
    """Quyền assign / approve / finalize (BR-022):
    Admin / Lãnh đạo / trưởng nhóm CỦA PHÒNG MẪU.
    """
    if is_privileged(user):
        return True
    return bool(
        user.is_dept_lead
        and user.department_id is not None
        and user.department_id == sample_dept_id
    )


def assert_write_scope(user: CurrentUser, dept_id: uuid.UUID) -> None:
    """Phạm vi ghi theo phòng (BR-014): KTV chỉ ghi trong phòng mình."""
    if is_privileged(user):
        return
    if user.department_id is None or user.department_id != dept_id:
        raise forbidden("Bạn chỉ được thao tác trong phạm vi phòng ban của mình")


# ===== Helpers tra cứu tên (cho response shape contract) =====
def user_name(db: Session, user_id: Optional[uuid.UUID]) -> Optional[str]:
    if user_id is None:
        return None
    from app.models.user import User

    u = db.get(User, user_id)
    return u.full_name if u else None


def dept_name(db: Session, dept_id: Optional[uuid.UUID]) -> Optional[str]:
    if dept_id is None:
        return None
    from app.models.department import Department

    d = db.get(Department, dept_id)
    return d.name if d else None


# ===== Sinh mã (RQ-YYYY-NNNN / SP-YYYY-NNNN) =====
def _next_code(db: Session, *, model, column, prefix: str) -> str:
    """Sinh mã <prefix>-YYYY-NNNN theo bộ đếm năm. UNIQUE constraint là lưới chống trùng;
    caller retry khi IntegrityError (FR-002 A1)."""
    year = datetime.now(timezone.utc).year
    like = f"{prefix}-{year}-%"
    # Đếm số bản ghi cùng năm để lấy số kế tiếp (đơn giản, đủ cho ~50K mẫu).
    count = db.execute(
        select(func.count()).select_from(model).where(column.like(like))
    ).scalar_one()
    seq = count + 1
    return f"{prefix}-{year}-{seq:04d}"


def next_request_code(db: Session) -> str:
    from app.models.test_request import TestRequest

    return _next_code(
        db, model=TestRequest, column=TestRequest.request_code, prefix="RQ"
    )


def next_sample_code(db: Session) -> str:
    from app.models.sample import Sample

    return _next_code(db, model=Sample, column=Sample.sample_code, prefix="SP")


# ===== State transition trung tâm (FR-017, §7.1) =====
def change_status(
    db: Session,
    sample,
    to_status: str,
    *,
    trigger: str,
    user_id: Optional[uuid.UUID],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> None:
    """Đổi trạng thái mẫu theo whitelist + audit. Caller phải giữ row-lock + commit.

    Idempotent: nếu from == to thì bỏ qua (không audit). Ngoài whitelist → 422.
    """
    from_status = sample.status
    if from_status == to_status:
        return
    if (from_status, to_status) not in STATE_WHITELIST:
        raise invalid_state(
            f"Không thể chuyển trạng thái từ '{from_status}' sang '{to_status}'"
        )
    sample.status = to_status
    from app.services import audit_service

    audit_service.log_action(
        db,
        action="SAMPLE_STATE_CHANGE",
        resource="sample",
        user_id=user_id,
        resource_id=sample.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"from": from_status, "to": to_status, "trigger": trigger},
    )


def get_sample_or_404(db: Session, sample_id: uuid.UUID, *, lock: bool = False):
    from app.models.sample import Sample

    stmt = select(Sample).where(
        Sample.id == sample_id, Sample.deleted_at.is_(None)
    )
    if lock:
        stmt = stmt.with_for_update()
    sample = db.execute(stmt).scalar_one_or_none()
    if sample is None:
        raise not_found("Không tìm thấy mẫu")
    return sample
