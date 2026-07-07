"""M8 common helpers — RBAC/QM, sinh nc_code, serialize, nhãn nguồn, get-or-404.

- RBAC: đọc roles_permissions M8 (admin/leader full; staff read all + create dept;
  accountant KHÔNG). QM (mở/đóng CAPA + actions): admin/leader luôn được; staff CHỈ khi
  is_quality_manager (cờ QM, giống pattern is_dept_lead cho duyệt mẫu M1).
- nc_code = NC-YYYY-NNNN idempotent theo năm + UNIQUE chống trùng (caller retry).
- Không lộ ID tuần tự (hiển thị nc_code).
"""
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.core.rbac import has_permission
from app.models.department import Department
from app.models.nonconformity import Capa, CapaAction, Nonconformity
from app.models.user import User

SOURCE_LABELS = {
    "manual": "Nhập thủ công",
    "complaint": "Khiếu nại",
    "qc": "Kiểm soát chất lượng (QC)",
    "audit": "Đánh giá nội bộ",
    "env": "Điều kiện môi trường",
    "sample": "Mẫu thử nghiệm",
    "pt": "Thử nghiệm thành thạo",
}


# ===== Error factories =====
def forbidden(message: str = "Bạn không có quyền thực hiện thao tác này") -> AppException:
    return AppException("FORBIDDEN", message, 403)


def nc_not_found() -> AppException:
    return AppException("NC_NOT_FOUND", "Không tìm thấy phiếu không phù hợp", 404)


# ===== RBAC =====
def assert_can_read(db: Session, user: CurrentUser) -> None:
    if not has_permission(db, user.role, "nonconformity", "read"):
        raise forbidden("Vai trò của bạn không được xem phiếu không phù hợp")


def assert_can_create(db: Session, user: CurrentUser) -> None:
    if not has_permission(db, user.role, "nonconformity", "create"):
        raise forbidden("Vai trò của bạn không được tạo phiếu không phù hợp")


def is_quality_manager(user: CurrentUser) -> bool:
    """Người có quyền QMS: admin/leader luôn; staff CHỈ khi được ủy quyền QM (cờ)."""
    if user.role in ("admin", "leader"):
        return True
    return user.role == "staff" and bool(user.is_quality_manager)


def assert_can_manage(db: Session, user: CurrentUser) -> None:
    """Mở/đóng CAPA + hành động khắc phục — quyền QM (§8.7)."""
    if not is_quality_manager(user):
        raise forbidden(
            "Chỉ Phụ trách chất lượng (QM), lãnh đạo hoặc quản trị viên được quản lý CAPA"
        )


def resolve_create_department(
    user: CurrentUser, requested: Optional[uuid.UUID]
) -> uuid.UUID:
    """Phòng tạo NC: staff ép phòng mình; admin/leader theo yêu cầu (mặc định phòng mình)."""
    if user.role in ("admin", "leader"):
        if requested is not None:
            return requested
        if user.department_id is not None:
            return user.department_id
        raise AppException("VALIDATION_ERROR", "Cần chỉ định department_id", 400)
    if user.department_id is None:
        raise forbidden("Người dùng chưa thuộc phòng ban nào")
    if requested is not None and requested != user.department_id:
        raise forbidden("Bạn chỉ được tạo phiếu cho phòng của mình")
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


def get_nc_or_404(db: Session, nc_id: uuid.UUID, *, lock: bool = False) -> Nonconformity:
    stmt = select(Nonconformity).where(Nonconformity.id == nc_id)
    if lock:
        stmt = stmt.with_for_update()
    nc = db.execute(stmt).scalar_one_or_none()
    if nc is None:
        raise nc_not_found()
    return nc


def get_capa_for_nc(db: Session, nc_id: uuid.UUID) -> Optional[Capa]:
    return db.execute(
        select(Capa).where(Capa.nc_id == nc_id)
    ).scalar_one_or_none()


# ===== nc_code = NC-YYYY-NNNN =====
def next_nc_code(db: Session, *, now: Optional[datetime] = None) -> str:
    year = (now or datetime.now(timezone.utc)).year
    like = f"NC-{year}-%"
    count = db.execute(
        select(func.count()).select_from(Nonconformity).where(Nonconformity.nc_code.like(like))
    ).scalar_one()
    return f"NC-{year}-{count + 1:04d}"


# ===== Serialize =====
def action_dict(db: Session, a: CapaAction) -> dict:
    return {
        "id": a.id,
        "action": a.action,
        "assignee_id": a.assignee_id,
        "assignee_name": user_name(db, a.assignee_id),
        "due_date": a.due_date,
        "status": a.status,
        "done_at": a.done_at,
        "note": a.note,
        "created_at": a.created_at,
    }


def capa_dict(db: Session, capa: Optional[Capa], *, with_actions: bool = True) -> Optional[dict]:
    if capa is None:
        return None
    data = {
        "id": capa.id,
        "nc_id": capa.nc_id,
        "capa_type": capa.capa_type,
        "root_cause": capa.root_cause,
        "owner_id": capa.owner_id,
        "owner_name": user_name(db, capa.owner_id),
        "due_date": capa.due_date,
        "status": capa.status,
        "effectiveness_result": capa.effectiveness_result,
        "effectiveness_note": capa.effectiveness_note,
        "verified_by_name": user_name(db, capa.verified_by),
        "verified_at": capa.verified_at,
        "closed_by_name": user_name(db, capa.closed_by),
        "closed_at": capa.closed_at,
        "created_by_name": user_name(db, capa.created_by),
        "created_at": capa.created_at,
    }
    if with_actions:
        rows = db.execute(
            select(CapaAction)
            .where(CapaAction.capa_id == capa.id)
            .order_by(CapaAction.created_at.asc())
        ).scalars().all()
        data["actions"] = [action_dict(db, a) for a in rows]
    return data


def nc_list_dict(db: Session, nc: Nonconformity, *, has_capa: bool) -> dict:
    return {
        "id": nc.id,
        "nc_code": nc.nc_code,
        "title": nc.title,
        "source_type": nc.source_type,
        "source_label": SOURCE_LABELS.get(nc.source_type, nc.source_type),
        "severity": nc.severity,
        "status": nc.status,
        "department_id": nc.department_id,
        "department_name": dept_name(db, nc.department_id),
        "raised_by_name": user_name(db, nc.raised_by),
        "raised_at": nc.raised_at,
        "has_capa": has_capa,
    }


def nc_detail_dict(db: Session, nc: Nonconformity) -> dict:
    capa = get_capa_for_nc(db, nc.id)
    return {
        "id": nc.id,
        "nc_code": nc.nc_code,
        "title": nc.title,
        "description": nc.description,
        "source_type": nc.source_type,
        "source_label": SOURCE_LABELS.get(nc.source_type, nc.source_type),
        "source_id": nc.source_id,
        "severity": nc.severity,
        "status": nc.status,
        "impact_assessment": nc.impact_assessment,
        "affected_ref_type": nc.affected_ref_type,
        "affected_ref_id": nc.affected_ref_id,
        "department_id": nc.department_id,
        "department_name": dept_name(db, nc.department_id),
        "raised_by": nc.raised_by,
        "raised_by_name": user_name(db, nc.raised_by),
        "raised_at": nc.raised_at,
        "updated_at": nc.updated_at,
        "capa": capa_dict(db, capa),
    }
