"""RBAC read service — roles, permissions matrix, role detail (M7.2, endpoints #17-19)."""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.permission import RolePermission
from app.models.user import VALID_ROLES

ROLE_META = {
    "admin": {"label": "Quản trị viên", "description": "Toàn quyền hệ thống", "scope": "global"},
    "leader": {"label": "Ban lãnh đạo", "description": "Xem toàn hệ thống, duyệt nghiệp vụ", "scope": "global"},
    "accountant": {"label": "Kế toán", "description": "Tài chính; không xem mẫu/kết quả", "scope": "global"},
    "staff": {"label": "Nhân sự/KTV", "description": "Nghiệp vụ lab theo phòng ban", "scope": "department"},
}

# Quyền trưởng nhóm phái sinh từ is_dept_lead (không nằm trong matrix theo role)
DERIVED_LEAD_PERMISSIONS = [
    {"resource": "sample", "action": "assign", "condition": "is_dept_lead"},
    {"resource": "sample", "action": "approve", "condition": "is_dept_lead"},
    {"resource": "sample", "action": "finalize", "condition": "is_dept_lead"},
]


def list_roles() -> list[dict]:
    return [
        {"role": role, **meta} for role, meta in ROLE_META.items()
    ]


def list_permissions(
    db: Session,
    *,
    role: Optional[str],
    resource: Optional[str],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    if role:
        conditions.append(RolePermission.role == role)
    if resource:
        conditions.append(RolePermission.resource == resource)

    total = db.execute(
        select(func.count()).select_from(RolePermission).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(RolePermission)
        .where(*conditions)
        .order_by(RolePermission.role, RolePermission.resource, RolePermission.action)
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return (
        [
            {
                "role": r.role,
                "resource": r.resource,
                "action": r.action,
                "scope": r.scope,
            }
            for r in rows
        ],
        total,
    )


def get_role_permissions(db: Session, role: str) -> dict:
    if role not in VALID_ROLES:
        raise AppException("ROLE_NOT_FOUND", "Vai trò không tồn tại", 404)
    rows = db.execute(
        select(RolePermission)
        .where(RolePermission.role == role)
        .order_by(RolePermission.resource, RolePermission.action)
    ).scalars().all()
    meta = ROLE_META[role]
    return {
        "role": role,
        "label": meta["label"],
        "scope": meta["scope"],
        "permissions": [
            {"resource": r.resource, "action": r.action, "scope": r.scope} for r in rows
        ],
        "derived_lead_permissions": DERIVED_LEAD_PERMISSIONS,
    }


def get_effective_permissions_for_user(
    db: Session, role: str, is_dept_lead: bool
) -> list[dict]:
    """Quyền hiệu lực của user (cho GET /auth/me) — role matrix + lead derived nếu là lead."""
    rows = db.execute(
        select(RolePermission.resource, RolePermission.action, RolePermission.scope).where(
            RolePermission.role == role
        )
    ).all()
    perms = [{"resource": r.resource, "action": r.action, "scope": r.scope} for r in rows]
    if is_dept_lead:
        for d in DERIVED_LEAD_PERMISSIONS:
            perms.append(
                {"resource": d["resource"], "action": d["action"], "scope": "department"}
            )
    return perms
