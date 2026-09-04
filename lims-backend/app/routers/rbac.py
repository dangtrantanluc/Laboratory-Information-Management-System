"""Router RBAC (M7.2) — roles, permissions matrix, role detail (đọc cho mọi vai trò)."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user, require_roles
from app.core.rbac import invalidate_role_cache
from app.core.responses import normalize_pagination, ok, paginated
from app.schemas.rbac import InvalidateCacheResponse
from app.db.database import get_db
from app.services import rbac_service

router = APIRouter(tags=["rbac"])


@router.get("/roles")
def list_roles(user: CurrentUser = Depends(get_current_user)):
    return ok(rbac_service.list_roles())


@router.get("/permissions")
def list_permissions(
    role: Optional[str] = Query(default=None),
    resource: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = rbac_service.list_permissions(
        db, role=role, resource=resource, page=page, limit=limit
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.get("/roles/{role}/permissions")
def get_role_permissions(
    role: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(rbac_service.get_role_permissions(db, role))


@router.post("/roles/cache/invalidate", response_model=InvalidateCacheResponse)
def invalidate_rbac_cache(user: CurrentUser = Depends(require_roles("admin"))):
    """Xoá cache RBAC ngay lập tức (W4/R1).

    `roles_permissions` được cache Redis với TTL 300s. Mọi migration đổi ma trận
    quyền — m36, m37 — vì thế chỉ có hiệu lực sau tối đa 5 phút, VÀ trong 5 phút đó
    hệ thống vẫn cấp quyền cũ. Trước đây `invalidate_role_cache()` tồn tại nhưng
    KHÔNG được gọi ở bất kỳ đâu trong backend, nên không có cách nào rút ngắn cửa sổ
    đó ngoài việc chờ hoặc khởi động lại.

    Cách dùng: chạy migration quyền xong thì gọi endpoint này. Khởi động lại app cũng
    xoá cache (xem lifespan trong app/main.py) — endpoint này dành cho trường hợp
    migrate mà không restart.
    """
    invalidate_role_cache()
    return ok({"invalidated": True})
