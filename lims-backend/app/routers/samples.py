"""Router samples (M1) — mẫu, tình trạng, deadline, QR, đính kèm, phân công, handover,
kết quả, chốt done, lý do trễ, danh sách overdue, xuất phiếu PDF.

LƯU Ý thứ tự: /samples/overdue đăng ký TRƯỚC /samples/{sample_id} (tránh nuốt path).
Kế toán cấm toàn bộ. Phạm vi phòng cho ghi.
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.sample import (
    ApproveResultRequest,
    CreateAssignmentRequest,
    CreateHandoverRequest,
    CreateResultRequest,
    FinalizeRequest,
    OverdueReasonRequest,
    UpdateConditionRequest,
    UpdateDeadlineRequest,
    UpdateSampleRequest,
)
from app.services import (
    assignment_service,
    result_service,
    sample_attachment_service,
    sample_common,
    sample_report_service,
    sample_service,
)

router = APIRouter(prefix="/samples", tags=["m1-samples"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# ===== List / search =====
@router.get("")
def list_samples(
    q: Optional[str] = Query(default=None, max_length=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    assigned_to: Optional[uuid.UUID] = Query(default=None),
    assigned_by: Optional[uuid.UUID] = Query(default=None),
    custodian_id: Optional[uuid.UUID] = Query(default=None),
    request_id: Optional[uuid.UUID] = Query(default=None),
    deadline_from: Optional[datetime] = Query(default=None),
    deadline_to: Optional[datetime] = Query(default=None),
    overdue_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    page, limit = normalize_pagination(page, limit)
    items, total = sample_service.list_samples(
        db,
        q=q,
        status_filter=status_filter,
        department_id=department_id,
        assigned_to=assigned_to,
        assigned_by=assigned_by,
        custodian_id=custodian_id,
        request_id=request_id,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        overdue_only=overdue_only,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


# ===== Overdue list (TRƯỚC /{sample_id}) =====
@router.get("/overdue")
def list_overdue(
    mode: str = Query(default="overdue"),
    within_days: int = Query(default=3, ge=1, le=30),
    department_id: Optional[uuid.UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    page, limit = normalize_pagination(page, limit)
    items, total = sample_service.list_overdue(
        db,
        mode=mode,
        within_days=within_days,
        department_id=department_id,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


# ===== Detail =====
@router.get("/{sample_id}")
def get_sample(
    sample_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    return ok(sample_service.get_sample_detail(db, sample_id))


@router.patch("/{sample_id}")
def update_sample(
    sample_id: uuid.UUID,
    body: UpdateSampleRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    data = sample_service.update_sample(
        db,
        user=user,
        sample_id=sample_id,
        changes=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.patch("/{sample_id}/condition")
def update_condition(
    sample_id: uuid.UUID,
    body: UpdateConditionRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    data = sample_service.update_condition(
        db,
        user=user,
        sample_id=sample_id,
        condition_status=body.condition_status,
        condition_note=body.condition_note,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.patch("/{sample_id}/deadline")
def update_deadline(
    sample_id: uuid.UUID,
    body: UpdateDeadlineRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    data = sample_service.update_deadline(
        db,
        user=user,
        sample_id=sample_id,
        deadline_at=body.deadline_at,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.get("/{sample_id}/qr")
def get_qr(
    sample_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    return ok(sample_service.get_qr(db, sample_id=sample_id))


# ===== Attachments =====
@router.get("/{sample_id}/attachments")
def list_sample_attachments(
    sample_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    return ok(sample_attachment_service.list_sample_attachments(db, sample_id=sample_id))


@router.post("/{sample_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_sample_attachment(
    sample_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    content = await file.read()
    data = sample_attachment_service.upload_sample_attachment(
        db,
        user=user,
        sample_id=sample_id,
        file_name=file.filename or "file",
        content=content,
        mime=file.content_type,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== Assignments =====
@router.get("/{sample_id}/assignments")
def list_assignments(
    sample_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    return ok(assignment_service.list_assignments(db, sample_id=sample_id))


@router.post("/{sample_id}/assignments", status_code=status.HTTP_201_CREATED)
def create_assignment(
    sample_id: uuid.UUID,
    body: CreateAssignmentRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    data = assignment_service.create_assignment(
        db,
        user=user,
        sample_id=sample_id,
        part_name=body.part_name,
        assigned_to=body.assigned_to,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== Handover / custody =====
@router.post("/{sample_id}/handovers", status_code=status.HTTP_201_CREATED)
def create_handover(
    sample_id: uuid.UUID,
    body: CreateHandoverRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    data = assignment_service.create_handover(
        db,
        user=user,
        sample_id=sample_id,
        to_user=body.to_user,
        reason=body.reason,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.get("/{sample_id}/custody-chain")
def get_custody_chain(
    sample_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    return ok(assignment_service.get_custody_chain(db, sample_id=sample_id))


# ===== Results summary =====
@router.get("/{sample_id}/results")
def sample_results(
    sample_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    return ok(result_service.sample_results_summary(db, user=user, sample_id=sample_id))


# ===== Finalize =====
@router.post("/{sample_id}/finalize")
def finalize_sample(
    sample_id: uuid.UUID,
    body: FinalizeRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    data = sample_service.finalize_sample(
        db,
        user=user,
        sample_id=sample_id,
        note=body.note,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== Overdue reason =====
@router.post("/{sample_id}/overdue-reasons", status_code=status.HTTP_201_CREATED)
def add_overdue_reason(
    sample_id: uuid.UUID,
    body: OverdueReasonRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    data = sample_service.add_overdue_reason(
        db,
        user=user,
        sample_id=sample_id,
        reason=body.reason,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== Result report PDF =====
@router.get("/{sample_id}/result-report.pdf")
def export_report(
    sample_id: uuid.UUID,
    request: Request,
    reissue: bool = Query(default=False),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    pdf_bytes, file_name = sample_report_service.export_report(
        db,
        user=user,
        sample_id=sample_id,
        reissue=reissue,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
