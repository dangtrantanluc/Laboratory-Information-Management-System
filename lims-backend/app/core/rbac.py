"""RBAC enforce — đọc roles_permissions (dữ liệu hóa, D4) + scope theo phòng ban (R13).

KHÔNG hardcode quyền trong code — luôn tra bảng (admin sửa ma trận không cần deploy).
Cache theo role ở Redis (warm bằng idx_rp_role) để tránh query mỗi request.
"""
import json
import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.redis_client import get_redis, rbac_role_key
from app.models.permission import RolePermission

logger = logging.getLogger("lims.rbac")

_CACHE_TTL = 300  # 5 phút


@dataclass
class PermissionEntry:
    resource: str
    action: str
    scope: str  # all | department | own


def _load_role_permissions_from_db(db: Session, role: str) -> list[PermissionEntry]:
    rows = db.execute(
        select(RolePermission.resource, RolePermission.action, RolePermission.scope).where(
            RolePermission.role == role
        )
    ).all()
    return [PermissionEntry(r.resource, r.action, r.scope) for r in rows]


def get_role_permissions(db: Session, role: str) -> list[PermissionEntry]:
    """Lấy toàn bộ quyền của 1 vai trò (cache Redis, fallback DB)."""
    r = get_redis()
    key = rbac_role_key(role)
    try:
        cached = r.get(key)
        if cached:
            data = json.loads(cached)
            return [PermissionEntry(**e) for e in data]
    except Exception as exc:  # noqa: BLE001 — cache lỗi không được chặn nghiệp vụ
        logger.warning("RBAC cache read failed: %s", exc)

    perms = _load_role_permissions_from_db(db, role)
    try:
        r.setex(
            key,
            _CACHE_TTL,
            json.dumps([p.__dict__ for p in perms]),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("RBAC cache write failed: %s", exc)
    return perms


def invalidate_role_cache(role: Optional[str] = None) -> None:
    """Xóa cache RBAC (gọi khi seed/đổi ma trận quyền)."""
    r = get_redis()
    try:
        if role:
            r.delete(rbac_role_key(role))
        else:
            for role_name in ("admin", "leader", "accountant", "staff"):
                r.delete(rbac_role_key(role_name))
    except Exception as exc:  # noqa: BLE001
        logger.warning("RBAC cache invalidate failed: %s", exc)


def find_permission(
    db: Session, role: str, resource: str, action: str
) -> Optional[PermissionEntry]:
    """Tìm dòng quyền (role, resource, action). None = không có quyền (→ 403)."""
    for p in get_role_permissions(db, role):
        if p.resource == resource and p.action == action:
            return p
    return None


def has_permission(db: Session, role: str, resource: str, action: str) -> bool:
    return find_permission(db, role, resource, action) is not None
