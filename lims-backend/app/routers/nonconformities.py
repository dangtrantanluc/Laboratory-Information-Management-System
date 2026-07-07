"""Router M8 — NC & CAPA (§7.10/§8.7).

RBAC (enforce service): read/create theo roles_permissions; manage (mở/đóng CAPA + actions)
theo QM (admin/leader hoặc staff is_quality_manager). accountant KHÔNG truy cập.

Thứ tự khai báo: route tĩnh (/stats) TRƯỚC /{nc_id} để tránh nuốt path.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.nonconformity import (
    AddActionRequest,
    CancelNcRequest,
    CloseCapaRequest,
    CreateNcRequest,
    OpenCapaRequest,
    UpdateActionRequest,
    UpdateNcRequest,
)
from app.services import nc_common, nc_service

router = APIRouter(prefix="/nonconformities", tags=["m8-nonconformities"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# ===== #10 GET /nonconformities/stats (khai trước /{id}) =====
@router.get("/stats")
def get_stats(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nc_common.assert_can_read(db, user)
    return ok(nc_service.stats(db))


# ===== #1 GET /nonconformities =====
@router.get("")
def list_ncs(
    q: Optional[str] = Query(default=None, max_length=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    severity: Optional[str] = Query(default=None),
    source_type: Optional[str] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nc_common.assert_can_read(db, user)
    page, limit = normalize_pagination(page, limit)
    items, total = nc_service.list_ncs(
        db,
        q=q,
        status_filter=status_filter,
        severity=severity,
        source_type=source_type,
        department_id=department_id,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


# ===== #2 POST /nonconformities =====
@router.post("", status_code=status.HTTP_201_CREATED)
def create_nc(
    body: CreateNcRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        nc_service.create_nc(
            db, user=user, payload=body.model_dump(),
            correlation_id=_cid(request), ip=_ip(request),
        )
    )


# ===== #3 GET /nonconformities/:id =====
@router.get("/{nc_id}")
def get_nc(
    nc_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nc_common.assert_can_read(db, user)
    return ok(nc_service.get_nc(db, nc_id=nc_id))


# ===== #4 PATCH /nonconformities/:id =====
@router.patch("/{nc_id}")
def update_nc(
    nc_id: uuid.UUID,
    body: UpdateNcRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nc_common.assert_can_read(db, user)
    return ok(
        nc_service.update_nc(
            db, user=user, nc_id=nc_id, changes=body.model_dump(exclude_unset=True),
            correlation_id=_cid(request), ip=_ip(request),
        )
    )


# ===== #5 POST /nonconformities/:id/cancel =====
@router.post("/{nc_id}/cancel")
def cancel_nc(
    nc_id: uuid.UUID,
    body: CancelNcRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        nc_service.cancel_nc(
            db, user=user, nc_id=nc_id, reason=body.reason,
            correlation_id=_cid(request), ip=_ip(request),
        )
    )


# ===== #6 POST /nonconformities/:id/capa =====
@router.post("/{nc_id}/capa", status_code=status.HTTP_201_CREATED)
def open_capa(
    nc_id: uuid.UUID,
    body: OpenCapaRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        nc_service.open_capa(
            db, user=user, nc_id=nc_id, payload=body.model_dump(),
            correlation_id=_cid(request), ip=_ip(request),
        )
    )


# ===== #7 POST /nonconformities/:id/actions =====
@router.post("/{nc_id}/actions", status_code=status.HTTP_201_CREATED)
def add_action(
    nc_id: uuid.UUID,
    body: AddActionRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        nc_service.add_action(
            db, user=user, nc_id=nc_id, payload=body.model_dump(),
            correlation_id=_cid(request), ip=_ip(request),
        )
    )


# ===== #8 PATCH /nonconformities/:id/actions/:actionId =====
@router.patch("/{nc_id}/actions/{action_id}")
def update_action(
    nc_id: uuid.UUID,
    action_id: uuid.UUID,
    body: UpdateActionRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        nc_service.update_action(
            db, user=user, nc_id=nc_id, action_id=action_id,
            new_status=body.status, note=body.note,
            correlation_id=_cid(request), ip=_ip(request),
        )
    )


# ===== #9 POST /nonconformities/:id/close =====
@router.post("/{nc_id}/close")
def close_capa(
    nc_id: uuid.UUID,
    body: CloseCapaRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        nc_service.close_capa(
            db, user=user, nc_id=nc_id,
            effectiveness_result=body.effectiveness_result,
            effectiveness_note=body.effectiveness_note,
            correlation_id=_cid(request), ip=_ip(request),
        )
    )
