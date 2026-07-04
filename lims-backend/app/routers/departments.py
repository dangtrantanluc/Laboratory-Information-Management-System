"""Router departments (M7.3) — list (mọi vai trò), CRUD + gán lead (admin)."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user, require_roles
from app.core.responses import ok
from app.db.database import get_db
from app.schemas.department import CreateDepartmentRequest, UpdateDepartmentRequest
from app.services import department_service

router = APIRouter(prefix="/departments", tags=["departments"])
admin_only = require_roles("admin")


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("")
def list_departments(
    tree: bool = Query(default=False),
    include_inactive: bool = Query(default=False),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = department_service.list_departments(
        db, tree=tree, include_inactive=include_inactive
    )
    return ok(data)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_department(
    body: CreateDepartmentRequest,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    data = department_service.create_department(
        db,
        actor_id=user.id,
        name=body.name,
        code=body.code,
        parent_id=body.parent_id,
        lead_user_id=body.lead_user_id,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.patch("/{dept_id}")
def update_department(
    dept_id: uuid.UUID,
    body: UpdateDepartmentRequest,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    # exclude_unset → phân biệt "không gửi" vs "gửi null" (gỡ parent/lead)
    changes = body.model_dump(exclude_unset=True)
    data = department_service.update_department(
        db,
        actor_id=user.id,
        dept_id=dept_id,
        changes=changes,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.delete("/{dept_id}")
def delete_department(
    dept_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    data = department_service.delete_department(
        db,
        actor_id=user.id,
        dept_id=dept_id,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)
