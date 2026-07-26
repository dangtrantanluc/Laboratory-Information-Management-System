"""Router — menu mới m23: hợp đồng NCKH, công tác khác, chứng nhận đào tạo.

Văn phòng (office) là NGƯỜI QUẢN LÝ 3 menu này (đọc + ghi), cùng admin/leader. Hợp đồng
chỉ nhóm quản lý (admin/leader/office) xem được (có giá trị tiền); công tác khác + chứng
nhận đào tạo đọc mở cho mọi user, ghi giới hạn admin/leader/office (service._assert_can_write).
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.request_meta import client_ip
from app.core.deps import CurrentUser, get_current_user
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.activity import (
    CreateCertificateRequest,
    CreateContractRequest,
    CreateStaffActivityRequest,
    UpdateCertificateRequest,
    UpdateContractRequest,
    UpdateStaffActivityRequest,
)
from app.services import activity_service, hr_common as hc

router = APIRouter(tags=["m4-activities"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _assert_contract_read(user: CurrentUser) -> None:
    """Hợp đồng NCKH (có giá trị tiền) — chỉ nhóm quản lý xem: admin/leader/office."""
    if user.role not in ("admin", "leader", "office"):
        raise hc.forbidden("Chỉ Quản trị/Lãnh đạo/Văn phòng được xem hợp đồng NCKH")


# ===================== research_contracts (NCKH → Hợp đồng) =====================
@router.get("/research-contracts")
def list_contracts(
    q: Optional[str] = Query(default=None, max_length=100),
    academic_year: Optional[str] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_contract_read(user)  # admin/leader/office quản lý hợp đồng
    page, limit = normalize_pagination(page, limit)
    items, total = activity_service.list_contracts(
        db, academic_year=academic_year, department_id=department_id, q=q, page=page, limit=limit
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("/research-contracts", status_code=status.HTTP_201_CREATED)
def create_contract(
    body: CreateContractRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    _assert_contract_read(user)
    return ok(activity_service.create_contract(
        db, user=user, payload=body.model_dump(), correlation_id=_cid(request), ip=client_ip(request)))


@router.patch("/research-contracts/{contract_id}")
def update_contract(
    contract_id: uuid.UUID, body: UpdateContractRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    _assert_contract_read(user)
    return ok(activity_service.update_contract(
        db, user=user, contract_id=contract_id, changes=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request), ip=client_ip(request)))


@router.delete("/research-contracts/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract(
    contract_id: uuid.UUID, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    _assert_contract_read(user)
    activity_service.delete_contract(
        db, user=user, contract_id=contract_id, correlation_id=_cid(request), ip=client_ip(request))


# ===================== staff_activities (Công tác khác) =====================
@router.get("/staff-activities")
def list_activities(
    kind: Optional[str] = Query(default=None),
    academic_year: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = activity_service.list_activities(
        db, kind=kind, academic_year=academic_year, page=page, limit=limit)
    return paginated(items, page=page, limit=limit, total=total)


@router.post("/staff-activities", status_code=status.HTTP_201_CREATED)
def create_activity(
    body: CreateStaffActivityRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    return ok(activity_service.create_activity(
        db, user=user, payload=body.model_dump(), correlation_id=_cid(request), ip=client_ip(request)))


@router.patch("/staff-activities/{activity_id}")
def update_activity(
    activity_id: uuid.UUID, body: UpdateStaffActivityRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    return ok(activity_service.update_activity(
        db, user=user, activity_id=activity_id, changes=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request), ip=client_ip(request)))


@router.delete("/staff-activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(
    activity_id: uuid.UUID, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    activity_service.delete_activity(
        db, user=user, activity_id=activity_id, correlation_id=_cid(request), ip=client_ip(request))


# ===================== training_certificates (Phục vụ CĐ → Cấp GCN) =====================
@router.get("/training-certificates")
def list_certificates(
    q: Optional[str] = Query(default=None, max_length=100),
    academic_year: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = activity_service.list_certificates(
        db, academic_year=academic_year, q=q, page=page, limit=limit)
    return paginated(items, page=page, limit=limit, total=total)


@router.post("/training-certificates", status_code=status.HTTP_201_CREATED)
def create_certificate(
    body: CreateCertificateRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    return ok(activity_service.create_certificate(
        db, user=user, payload=body.model_dump(), correlation_id=_cid(request), ip=client_ip(request)))


@router.patch("/training-certificates/{cert_id}")
def update_certificate(
    cert_id: uuid.UUID, body: UpdateCertificateRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    return ok(activity_service.update_certificate(
        db, user=user, cert_id=cert_id, changes=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request), ip=client_ip(request)))


@router.delete("/training-certificates/{cert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_certificate(
    cert_id: uuid.UUID, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    activity_service.delete_certificate(
        db, user=user, cert_id=cert_id, correlation_id=_cid(request), ip=client_ip(request))
