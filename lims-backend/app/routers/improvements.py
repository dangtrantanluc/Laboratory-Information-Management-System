"""Router M10 — Cải tiến (§8.6). Sổ nhẹ; liên kết linked_nc_id sang NC (M8)."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.risk import CreateImprovementRequest, UpdateImprovementRequest
from app.services import risk_common, risk_service

router = APIRouter(prefix="/improvements", tags=["m10-improvements"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("")
def list_improvements(
    q: Optional[str] = Query(default=None, max_length=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    source: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    risk_common.assert_can_read(db, user, "improvement")
    page, limit = normalize_pagination(page, limit)
    items, total = risk_service.list_improvements(
        db, q=q, status_filter=status_filter, source=source, page=page, limit=limit
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_improvement(
    body: CreateImprovementRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    return ok(risk_service.create_improvement(
        db, user=user, payload=body.model_dump(), correlation_id=_cid(request), ip=_ip(request)
    ))


@router.get("/{imp_id}")
def get_improvement(
    imp_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    risk_common.assert_can_read(db, user, "improvement")
    return ok(risk_service.get_improvement(db, imp_id=imp_id))


@router.patch("/{imp_id}")
def update_improvement(
    imp_id: uuid.UUID, body: UpdateImprovementRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    risk_common.assert_can_read(db, user, "improvement")
    return ok(risk_service.update_improvement(
        db, user=user, imp_id=imp_id, changes=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request), ip=_ip(request),
    ))
