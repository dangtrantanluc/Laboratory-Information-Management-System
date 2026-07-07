"""Router M10 — Rủi ro & Cơ hội (§8.5).

RBAC (enforce service): read/create theo roles_permissions; manage (biện pháp/đóng) theo QM.
Thứ tự: route tĩnh (/stats) TRƯỚC /{risk_id}.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.risk import (
    AddTreatmentRequest,
    CloseRiskRequest,
    CreateRiskRequest,
    UpdateRiskRequest,
    UpdateTreatmentRequest,
)
from app.services import risk_common, risk_service

router = APIRouter(prefix="/risks", tags=["m10-risks"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("/stats")
def get_stats(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    risk_common.assert_can_read(db, user, "risk")
    return ok(risk_service.risk_stats(db))


@router.get("")
def list_risks(
    q: Optional[str] = Query(default=None, max_length=100),
    kind: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    band: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    risk_common.assert_can_read(db, user, "risk")
    page, limit = normalize_pagination(page, limit)
    items, total = risk_service.list_risks(
        db, q=q, kind=kind, status_filter=status_filter,
        department_id=department_id, band=band, page=page, limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_risk(
    body: CreateRiskRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    return ok(risk_service.create_risk(
        db, user=user, payload=body.model_dump(), correlation_id=_cid(request), ip=_ip(request)
    ))


@router.get("/{risk_id}")
def get_risk(
    risk_id: uuid.UUID, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
):
    risk_common.assert_can_read(db, user, "risk")
    return ok(risk_service.get_risk(db, risk_id=risk_id))


@router.patch("/{risk_id}")
def update_risk(
    risk_id: uuid.UUID, body: UpdateRiskRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    risk_common.assert_can_read(db, user, "risk")
    return ok(risk_service.update_risk(
        db, user=user, risk_id=risk_id, changes=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request), ip=_ip(request),
    ))


@router.post("/{risk_id}/treatments", status_code=status.HTTP_201_CREATED)
def add_treatment(
    risk_id: uuid.UUID, body: AddTreatmentRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    return ok(risk_service.add_treatment(
        db, user=user, risk_id=risk_id, payload=body.model_dump(),
        correlation_id=_cid(request), ip=_ip(request),
    ))


@router.patch("/{risk_id}/treatments/{treatment_id}")
def update_treatment(
    risk_id: uuid.UUID, treatment_id: uuid.UUID, body: UpdateTreatmentRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    return ok(risk_service.update_treatment(
        db, user=user, risk_id=risk_id, treatment_id=treatment_id,
        new_status=body.status, correlation_id=_cid(request), ip=_ip(request),
    ))


@router.post("/{risk_id}/close")
def close_risk(
    risk_id: uuid.UUID, body: CloseRiskRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    return ok(risk_service.close_risk(
        db, user=user, risk_id=risk_id, note=body.note,
        correlation_id=_cid(request), ip=_ip(request),
    ))
