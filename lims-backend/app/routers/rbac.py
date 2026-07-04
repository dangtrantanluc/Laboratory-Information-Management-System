"""Router RBAC (M7.2) — roles, permissions matrix, role detail (đọc cho mọi vai trò)."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import normalize_pagination, ok, paginated
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
    limit: int = Query(default=100, ge=1),
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
