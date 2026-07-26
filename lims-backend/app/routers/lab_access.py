"""Router Thẻ vào PTN (sinh viên) — M19 — /lab-access-cards.

Danh sách quản trị (CRUD, không qua duyệt): Văn phòng (office) quản trị
(lab_access_card:manage); admin/leader/qms/office đọc (lab_access_card:read).
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_permission
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.lab_access import CreateLabAccessCardRequest, UpdateLabAccessCardRequest
from app.services import lab_access_service

router = APIRouter(prefix="/lab-access-cards", tags=["lab-access-cards"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("")
def list_cards(
    q: Optional[str] = Query(default=None, max_length=100),
    supervisor_name: Optional[str] = Query(default=None, max_length=255),
    room: Optional[str] = Query(default=None, max_length=255),
    active_on: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(require_permission("lab_access_card", "read")),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = lab_access_service.list_cards(
        db, q=q, supervisor_name=supervisor_name, room=room, active_on=active_on,
        page=page, limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_card(
    body: CreateLabAccessCardRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("lab_access_card", "manage")),
    db: Session = Depends(get_db),
):
    data = lab_access_service.create_card(
        db, user=user, payload=body.model_dump(),
        correlation_id=_cid(request), ip=_ip(request),
    )
    return ok(data)


@router.patch("/{card_id}")
def update_card(
    card_id: uuid.UUID,
    body: UpdateLabAccessCardRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("lab_access_card", "manage")),
    db: Session = Depends(get_db),
):
    changes = body.model_dump(exclude_unset=True)
    data = lab_access_service.update_card(
        db, user=user, card_id=card_id, changes=changes,
        correlation_id=_cid(request), ip=_ip(request),
    )
    return ok(data)


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(
    card_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(require_permission("lab_access_card", "manage")),
    db: Session = Depends(get_db),
):
    lab_access_service.delete_card(
        db, user=user, card_id=card_id, correlation_id=_cid(request), ip=_ip(request)
    )
