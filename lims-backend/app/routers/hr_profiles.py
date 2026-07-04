"""Router M4.1 — Hồ sơ nhân sự, lương (hệ số×cơ sở), HĐ, chu kỳ, lịch sử lương, năng lực.

Field-level RBAC lương/HĐ/PII strip ở service (hr_common.strip_profile). Quyền sửa lương/HĐ
= admin/accountant (SALARY_FORBIDDEN). LƯU Ý thứ tự đăng ký: /hr-profiles/me tĩnh đăng ký
trước /hr-profiles/{user_id} động.
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.hr import (
    CreateCompetenceRequest,
    CreateProfileRequest,
    CreateSalaryRaiseRequest,
    UpdateCompetenceRequest,
    UpdateContractRequest,
    UpdateProfileRequest,
    UpdateSalaryCycleRequest,
)
from app.services import attachment_service, hr_service

router = APIRouter(tags=["m4-hr-profiles"])

_COMPETENCE_MIME_WHITELIST = {"application/pdf", "image/png", "image/jpeg"}


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# ===================== #1 LIST =====================
@router.get("/hr-profiles")
def list_profiles(
    q: Optional[str] = Query(default=None, max_length=100),
    department_id: Optional[uuid.UUID] = Query(default=None),
    job_title: Optional[str] = Query(default=None, max_length=100),
    contract_expiring_within_days: Optional[int] = Query(default=None, ge=1, le=3650),
    salary_raise_within_days: Optional[int] = Query(default=None, ge=1, le=3650),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(require_roles("admin", "leader", "accountant")),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = hr_service.list_profiles(
        db,
        user=user,
        q=q,
        department_id=department_id,
        job_title=job_title,
        contract_expiring_within_days=contract_expiring_within_days,
        salary_raise_within_days=salary_raise_within_days,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


# ===================== #2 CREATE =====================
@router.post("/hr-profiles", status_code=status.HTTP_201_CREATED)
def create_profile(
    body: CreateProfileRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = hr_service.create_profile(
        db,
        user=user,
        target_user_id=body.user_id,
        job_title=body.job_title,
        hired_date=body.hired_date,
        phone=body.phone,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===================== #4 GET me (tĩnh — trước /{user_id}) =====================
@router.get("/hr-profiles/me")
def get_my_profile(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(hr_service.get_my_profile(db, user=user))


# ===================== #3 GET detail =====================
@router.get("/hr-profiles/{user_id}")
def get_profile(
    user_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(hr_service.get_profile(db, user=user, target_user_id=user_id))


# ===================== #5 PATCH =====================
@router.patch("/hr-profiles/{user_id}")
def update_profile(
    user_id: uuid.UUID,
    body: UpdateProfileRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    changes = body.model_dump(exclude_unset=True)
    data = hr_service.update_profile(
        db,
        user=user,
        target_user_id=user_id,
        changes=changes,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===================== #6 PATCH contract =====================
@router.patch("/hr-profiles/{user_id}/contract")
def update_contract(
    user_id: uuid.UUID,
    body: UpdateContractRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = hr_service.update_contract(
        db,
        user=user,
        target_user_id=user_id,
        contract_signed_date=body.contract_signed_date,
        contract_type=body.contract_type,
        contract_end_date=body.contract_end_date,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===================== #7 PATCH salary-cycle =====================
@router.patch("/hr-profiles/{user_id}/salary-cycle")
def update_salary_cycle(
    user_id: uuid.UUID,
    body: UpdateSalaryCycleRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = hr_service.update_salary_cycle(
        db,
        user=user,
        target_user_id=user_id,
        salary_cycle_years=body.salary_cycle_years,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===================== #8 POST salary-raises =====================
@router.post("/hr-profiles/{user_id}/salary-raises", status_code=status.HTTP_201_CREATED)
def create_salary_raise(
    user_id: uuid.UUID,
    body: CreateSalaryRaiseRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = hr_service.create_salary_raise(
        db,
        user=user,
        target_user_id=user_id,
        salary_grade=body.salary_grade,
        salary_coefficient=body.salary_coefficient,
        base_salary_amount=body.base_salary_amount,
        raise_date=body.raise_date,
        note=body.note,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===================== #9 GET salary-history =====================
@router.get("/hr-profiles/{user_id}/salary-history")
def list_salary_history(
    user_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = hr_service.list_salary_history(
        db, user=user, target_user_id=user_id, page=page, limit=limit
    )
    return paginated(items, page=page, limit=limit, total=total)


# ===================== #10 GET competences =====================
@router.get("/hr-profiles/{user_id}/competences")
def list_competences(
    user_id: uuid.UUID,
    kind: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = hr_service.list_competences(
        db, user=user, target_user_id=user_id, kind=kind, status_filter=status_filter
    )
    return ok(items)


# ===================== #11 POST competences =====================
@router.post("/hr-profiles/{user_id}/competences", status_code=status.HTTP_201_CREATED)
def create_competence(
    user_id: uuid.UUID,
    body: CreateCompetenceRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = hr_service.create_competence(
        db,
        user=user,
        target_user_id=user_id,
        payload=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===================== #15 GET competence-summary =====================
@router.get("/hr-profiles/{user_id}/competence-summary")
def competence_summary(
    user_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import research_service

    return ok(research_service.competence_summary(db, user=user, target_user_id=user_id))


# ===================== #12 PATCH competence =====================
@router.patch("/competences/{competence_id}")
def update_competence(
    competence_id: uuid.UUID,
    body: UpdateCompetenceRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    changes = body.model_dump(exclude_unset=True)
    data = hr_service.update_competence(
        db,
        user=user,
        competence_id=competence_id,
        changes=changes,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===================== #13 DELETE competence =====================
@router.delete("/competences/{competence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_competence(
    competence_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hr_service.delete_competence(
        db,
        user=user,
        competence_id=competence_id,
        correlation_id=_cid(request),
        ip=_ip(request),
    )


# ===================== #14 POST competence attachment =====================
@router.post("/competences/{competence_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_competence_attachment(
    competence_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import hr_common as hc

    hc.assert_can_manage_competence(user)
    comp = hr_service.get_competence_or_404(db, competence_id)
    if file.content_type not in _COMPETENCE_MIME_WHITELIST:
        raise AppException(
            "INVALID_FILE_TYPE", "Định dạng file không hợp lệ (PDF/PNG/JPG)", 422
        )
    content = await file.read()
    # owner = hồ sơ nhân sự (owner_type='hr_profile', owner_id = user_id của năng lực)
    data = attachment_service.create_attachment(
        db,
        user=user,
        owner_type="hr_profile",
        owner_id=comp.user_id,
        file_name=file.filename or "competence",
        content=content,
        mime=file.content_type,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)
