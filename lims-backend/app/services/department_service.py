"""Department service — CRUD cây phòng ban + gán lead_user_id (M1 OQ#11).

Validate: code unique, parent không tạo vòng (app-layer đệ quy), lead thuộc phòng + active.
"""
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, conflict, not_found, unprocessable
from app.models.department import Department
from app.models.user import User
from app.services import audit_service


def _get_dept_or_404(db: Session, dept_id: uuid.UUID) -> Department:
    dept = db.get(Department, dept_id)
    if dept is None:
        raise not_found("Không tìm thấy phòng ban")
    return dept


def _code_exists(db: Session, code: str, exclude_id: Optional[uuid.UUID] = None) -> bool:
    q = select(Department.id).where(Department.code == code)
    if exclude_id:
        q = q.where(Department.id != exclude_id)
    return db.execute(q).first() is not None


def _member_count(db: Session, dept_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count()).select_from(User).where(User.department_id == dept_id)
    ).scalar_one()


def _would_create_cycle(
    db: Session, dept_id: uuid.UUID, new_parent_id: uuid.UUID
) -> bool:
    """Đi ngược từ new_parent lên gốc; nếu gặp dept_id → tạo vòng."""
    if new_parent_id == dept_id:
        return True
    visited: set[uuid.UUID] = set()
    current: Optional[uuid.UUID] = new_parent_id
    while current is not None:
        if current == dept_id:
            return True
        if current in visited:
            break  # tránh vòng lặp vô hạn nếu dữ liệu hỏng
        visited.add(current)
        parent = db.execute(
            select(Department.parent_id).where(Department.id == current)
        ).scalar_one_or_none()
        current = parent
    return False


def _validate_lead(db: Session, dept_id: uuid.UUID, lead_user_id: uuid.UUID) -> User:
    lead = db.get(User, lead_user_id)
    if lead is None:
        raise AppException("USER_NOT_FOUND", "Người dùng trưởng nhóm không tồn tại", 404)
    if lead.department_id != dept_id:
        raise unprocessable(
            "LEAD_NOT_IN_DEPARTMENT", "Trưởng nhóm phải thuộc đúng phòng ban này"
        )
    if lead.status != "active":
        raise unprocessable("LEAD_USER_INACTIVE", "Trưởng nhóm đang bị vô hiệu hóa")
    return lead


def _serialize(db: Session, dept: Department, with_members: bool = True) -> dict:
    lead_name = None
    if dept.lead_user_id:
        lead = db.get(User, dept.lead_user_id)
        lead_name = lead.full_name if lead else None
    data = {
        "id": dept.id,
        "name": dept.name,
        "code": dept.code,
        "parent_id": dept.parent_id,
        "lead_user_id": dept.lead_user_id,
        "lead_user_name": lead_name,
        "status": dept.status,
        "created_at": dept.created_at,
    }
    if with_members:
        data["member_count"] = _member_count(db, dept.id)
    return data


def list_departments(
    db: Session, *, tree: bool, include_inactive: bool
) -> list[dict]:
    conditions = []
    if not include_inactive:
        conditions.append(Department.status == "active")
    rows = db.execute(
        select(Department).where(*conditions).order_by(Department.code)
    ).scalars().all()
    flat = [_serialize(db, d) for d in rows]
    if not tree:
        return flat

    # Dựng cây lồng nhau theo parent_id
    by_id = {d["id"]: {**d, "children": []} for d in flat}
    roots = []
    for node in by_id.values():
        parent_id = node["parent_id"]
        if parent_id and parent_id in by_id:
            by_id[parent_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


def create_department(
    db: Session,
    *,
    actor_id: uuid.UUID,
    name: str,
    code: str,
    parent_id: Optional[uuid.UUID],
    lead_user_id: Optional[uuid.UUID],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    if _code_exists(db, code):
        raise conflict("DUPLICATE_CODE", "Mã phòng ban đã tồn tại")
    if parent_id is not None:
        if db.get(Department, parent_id) is None:
            raise AppException("PARENT_NOT_FOUND", "Phòng ban cha không tồn tại", 404)

    dept = Department(
        name=name.strip(),
        code=code,
        parent_id=parent_id,
        status="active",
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(dept)
    db.flush()

    if lead_user_id is not None:
        lead = db.get(User, lead_user_id)
        if lead is None:
            raise AppException("USER_NOT_FOUND", "Người dùng trưởng nhóm không tồn tại", 404)
        if lead.department_id != dept.id:
            raise unprocessable(
                "LEAD_NOT_IN_DEPARTMENT", "Trưởng nhóm phải thuộc đúng phòng ban này"
            )
        if lead.status != "active":
            raise unprocessable("LEAD_USER_INACTIVE", "Trưởng nhóm đang bị vô hiệu hóa")
        dept.lead_user_id = lead_user_id

    audit_service.log_action(
        db,
        action="DEPARTMENT_CREATE",
        resource="department",
        user_id=actor_id,
        resource_id=dept.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"name": dept.name, "code": dept.code},
    )
    db.commit()
    db.refresh(dept)
    return _serialize(db, dept, with_members=False)


def update_department(
    db: Session,
    *,
    actor_id: uuid.UUID,
    dept_id: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    dept = _get_dept_or_404(db, dept_id)
    diff: dict = {}
    lead_changed = False
    old_lead = dept.lead_user_id

    if "name" in changes and changes["name"] is not None:
        dept.name = changes["name"].strip()
        diff["name"] = dept.name

    if "code" in changes and changes["code"] is not None:
        new_code = changes["code"]
        if new_code != dept.code:
            if _code_exists(db, new_code, exclude_id=dept.id):
                raise conflict("DUPLICATE_CODE", "Mã phòng ban đã tồn tại")
            diff["code"] = {"from": dept.code, "to": new_code}
            dept.code = new_code

    if "parent_id" in changes:
        new_parent = changes["parent_id"]
        if new_parent is not None:
            if db.get(Department, new_parent) is None:
                raise AppException("PARENT_NOT_FOUND", "Phòng ban cha không tồn tại", 404)
            if _would_create_cycle(db, dept.id, new_parent):
                raise unprocessable(
                    "INVALID_PARENT", "Không thể tạo vòng lặp trong cây phòng ban"
                )
        diff["parent_id"] = {
            "from": str(dept.parent_id) if dept.parent_id else None,
            "to": str(new_parent) if new_parent else None,
        }
        dept.parent_id = new_parent

    if "lead_user_id" in changes:
        new_lead = changes["lead_user_id"]
        if new_lead is not None:
            _validate_lead(db, dept.id, new_lead)
        if new_lead != dept.lead_user_id:
            lead_changed = True
            dept.lead_user_id = new_lead

    if not diff and not lead_changed:
        raise AppException("VALIDATION_ERROR", "Không có thay đổi nào hợp lệ", 400)

    dept.updated_by = actor_id
    dept.updated_at = func.now()

    if diff:
        audit_service.log_action(
            db,
            action="DEPARTMENT_UPDATE",
            resource="department",
            user_id=actor_id,
            resource_id=dept.id,
            correlation_id=correlation_id,
            ip=ip,
            detail={"diff": diff},
        )
    if lead_changed:
        audit_service.log_action(
            db,
            action="DEPARTMENT_LEAD_ASSIGN",
            resource="department",
            user_id=actor_id,
            resource_id=dept.id,
            correlation_id=correlation_id,
            ip=ip,
            detail={
                "old_lead": str(old_lead) if old_lead else None,
                "new_lead": str(dept.lead_user_id) if dept.lead_user_id else None,
            },
        )
    db.commit()
    db.refresh(dept)
    return _serialize(db, dept, with_members=False)


def delete_department(
    db: Session,
    *,
    actor_id: uuid.UUID,
    dept_id: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    dept = _get_dept_or_404(db, dept_id)

    # Chỉ cho vô hiệu khi rỗng: không user, không phòng con
    if _member_count(db, dept.id) > 0:
        raise unprocessable(
            "DEPARTMENT_NOT_EMPTY", "Phòng ban còn người dùng — không thể xóa"
        )
    has_child = db.execute(
        select(Department.id).where(Department.parent_id == dept.id)
    ).first()
    if has_child:
        raise unprocessable(
            "DEPARTMENT_NOT_EMPTY", "Phòng ban còn phòng con — không thể xóa"
        )

    # Soft-deactivate (giữ truy vết VILAS)
    dept.status = "inactive"
    dept.updated_by = actor_id
    dept.updated_at = func.now()

    audit_service.log_action(
        db,
        action="DEPARTMENT_DELETE",
        resource="department",
        user_id=actor_id,
        resource_id=dept.id,
        correlation_id=correlation_id,
        ip=ip,
    )
    db.commit()
    return {"id": dept.id, "status": dept.status}
