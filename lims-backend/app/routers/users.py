"""Router users (M7.3) — CRUD + enable/disable + reset-password. CHỈ admin."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_roles
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.user import (
    CreateUserRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
)
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])

# Mọi endpoint user chỉ admin (RBAC matrix: quản trị user chỉ admin)
admin_only = require_roles("admin")


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("")
def list_users(
    request: Request,
    q: Optional[str] = Query(default=None, max_length=100),
    role: Optional[str] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = user_service.list_users(
        db,
        q=q,
        role=role,
        department_id=department_id,
        status=status_filter,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    data = user_service.create_user(
        db,
        actor_id=user.id,
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        department_id=body.department_id,
        password=body.password,
        is_dept_lead=body.is_dept_lead,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.get("/{user_id}")
def get_user(
    user_id: uuid.UUID,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return ok(user_service.get_user(db, user_id))


@router.patch("/{user_id}")
def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    # chỉ truyền field client thực sự gửi (phân biệt với default None)
    changes = body.model_dump(exclude_unset=True)
    data = user_service.update_user(
        db,
        actor_id=user.id,
        user_id=user_id,
        changes=changes,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.post("/{user_id}/enable")
def enable_user(
    user_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return ok(
        user_service.set_status(
            db,
            actor_id=user.id,
            user_id=user_id,
            enable=True,
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


@router.post("/{user_id}/disable")
def disable_user(
    user_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return ok(
        user_service.set_status(
            db,
            actor_id=user.id,
            user_id=user_id,
            enable=False,
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: uuid.UUID,
    body: ResetPasswordRequest,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return ok(
        user_service.reset_password(
            db,
            actor_id=user.id,
            user_id=user_id,
            new_password=body.new_password,
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )
