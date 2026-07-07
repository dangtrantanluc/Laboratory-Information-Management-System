"""M10 common helpers — RBAC/QM, sinh mã, band rủi ro, serialize.

- RBAC: risk/improvement read/create/manage (admin/leader full; staff read all + create
  dept; accountant KHÔNG). manage (biện pháp/đóng) = QM (admin/leader hoặc staff QM).
- band(level): low ≤4 · medium 5..12 · high ≥13 (level = likelihood×impact 1..25).
- mã: RSK-YYYY-NNNN / IMP-YYYY-NNNN idempotent theo năm + UNIQUE chống trùng.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.core.rbac import has_permission
from app.models.department import Department
from app.models.risk import Improvement, Risk, RiskTreatment
from app.models.user import User

KIND_LABELS = {"risk": "Rủi ro", "opportunity": "Cơ hội"}
RISK_STATUS_LABELS = {
    "open": "Mới mở",
    "treating": "Đang xử lý",
    "monitoring": "Theo dõi",
    "closed": "Đã đóng",
}


def band(level: int) -> str:
    if level <= 4:
        return "low"
    if level <= 12:
        return "medium"
    return "high"


# ===== Error factories =====
def forbidden(message: str = "Bạn không có quyền thực hiện thao tác này") -> AppException:
    return AppException("FORBIDDEN", message, 403)


def risk_not_found() -> AppException:
    return AppException("RISK_NOT_FOUND", "Không tìm thấy rủi ro", 404)


def improvement_not_found() -> AppException:
    return AppException("IMPROVEMENT_NOT_FOUND", "Không tìm thấy cải tiến", 404)


# ===== RBAC =====
def assert_can_read(db: Session, user: CurrentUser, resource: str) -> None:
    if not has_permission(db, user.role, resource, "read"):
        raise forbidden("Vai trò của bạn không được xem mục này")


def assert_can_create(db: Session, user: CurrentUser, resource: str) -> None:
    if not has_permission(db, user.role, resource, "create"):
        raise forbidden("Vai trò của bạn không được tạo mục này")


def is_quality_manager(user: CurrentUser) -> bool:
    if user.role in ("admin", "leader"):
        return True
    return user.role == "staff" and bool(user.is_quality_manager)


def assert_can_manage(user: CurrentUser) -> None:
    if not is_quality_manager(user):
        raise forbidden(
            "Chỉ Phụ trách chất lượng (QM), lãnh đạo hoặc quản trị viên được quản lý mục này"
        )


def resolve_create_department(
    user: CurrentUser, requested: Optional[uuid.UUID]
) -> uuid.UUID:
    if user.role in ("admin", "leader"):
        if requested is not None:
            return requested
        if user.department_id is not None:
            return user.department_id
        raise AppException("VALIDATION_ERROR", "Cần chỉ định department_id", 400)
    if user.department_id is None:
        raise forbidden("Người dùng chưa thuộc phòng ban nào")
    if requested is not None and requested != user.department_id:
        raise forbidden("Bạn chỉ được tạo cho phòng của mình")
    return user.department_id


# ===== Helpers =====
def user_name(db: Session, user_id: Optional[uuid.UUID]) -> Optional[str]:
    if user_id is None:
        return None
    u = db.get(User, user_id)
    return u.full_name if u else None


def dept_name(db: Session, dept_id: Optional[uuid.UUID]) -> Optional[str]:
    if dept_id is None:
        return None
    d = db.get(Department, dept_id)
    return d.name if d else None


def get_risk_or_404(db: Session, risk_id: uuid.UUID, *, lock: bool = False) -> Risk:
    stmt = select(Risk).where(Risk.id == risk_id)
    if lock:
        stmt = stmt.with_for_update()
    r = db.execute(stmt).scalar_one_or_none()
    if r is None:
        raise risk_not_found()
    return r


def get_improvement_or_404(db: Session, imp_id: uuid.UUID) -> Improvement:
    imp = db.get(Improvement, imp_id)
    if imp is None:
        raise improvement_not_found()
    return imp


# ===== Code gen =====
def next_code(db: Session, model, column, prefix: str) -> str:
    year = datetime.now(timezone.utc).year
    like = f"{prefix}-{year}-%"
    count = db.execute(
        select(func.count()).select_from(model).where(column.like(like))
    ).scalar_one()
    return f"{prefix}-{year}-{count + 1:04d}"


# ===== Serialize =====
def treatment_dict(db: Session, t: RiskTreatment) -> dict:
    return {
        "id": t.id,
        "treatment": t.treatment,
        "owner_id": t.owner_id,
        "owner_name": user_name(db, t.owner_id),
        "due_date": t.due_date,
        "status": t.status,
        "done_at": t.done_at,
        "created_at": t.created_at,
    }


def risk_list_dict(db: Session, r: Risk) -> dict:
    return {
        "id": r.id,
        "risk_code": r.risk_code,
        "kind": r.kind,
        "title": r.title,
        "likelihood": r.likelihood,
        "impact": r.impact,
        "level": r.level,
        "band": band(r.level),
        "status": r.status,
        "department_id": r.department_id,
        "department_name": dept_name(db, r.department_id),
        "owner_name": user_name(db, r.owner_id),
        "next_review_date": r.next_review_date,
        "created_at": r.created_at,
    }


def risk_detail_dict(db: Session, r: Risk) -> dict:
    rows = db.execute(
        select(RiskTreatment)
        .where(RiskTreatment.risk_id == r.id)
        .order_by(RiskTreatment.created_at.asc())
    ).scalars().all()
    return {
        **risk_list_dict(db, r),
        "context": r.context,
        "process_ref": r.process_ref,
        "owner_id": r.owner_id,
        "closed_at": r.closed_at,
        "closed_by_name": user_name(db, r.closed_by),
        "updated_at": r.updated_at,
        "treatments": [treatment_dict(db, t) for t in rows],
    }


def improvement_dict(db: Session, imp: Improvement) -> dict:
    return {
        "id": imp.id,
        "improvement_code": imp.improvement_code,
        "source": imp.source,
        "title": imp.title,
        "description": imp.description,
        "owner_id": imp.owner_id,
        "owner_name": user_name(db, imp.owner_id),
        "department_id": imp.department_id,
        "department_name": dept_name(db, imp.department_id),
        "status": imp.status,
        "linked_nc_id": imp.linked_nc_id,
        "created_at": imp.created_at,
        "updated_at": imp.updated_at,
    }
