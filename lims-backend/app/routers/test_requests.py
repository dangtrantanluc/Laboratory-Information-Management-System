"""Router test_requests (M1) — phiếu yêu cầu thử nghiệm + mẫu/đính kèm nested (FR-018/001/003).

Kế toán cấm toàn bộ (FORBIDDEN_ACCOUNTANT). Phạm vi phòng cho ghi.
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.sample import (
    CreateSampleRequest,
    CreateTestRequestRequest,
    UpdateTestRequestRequest,
)
from app.services import (
    sample_attachment_service,
    sample_common,
    sample_service,
    test_request_service,
)

router = APIRouter(prefix="/test-requests", tags=["m1-test-requests"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("")
def list_requests(
    request: Request,
    q: Optional[str] = Query(default=None, max_length=100),
    department_id: Optional[uuid.UUID] = Query(default=None),
    customer_id: Optional[uuid.UUID] = Query(default=None),
    received_from: Optional[datetime] = Query(default=None),
    received_to: Optional[datetime] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    page, limit = normalize_pagination(page, limit)
    items, total = test_request_service.list_requests(
        db,
        q=q,
        department_id=department_id,
        customer_id=customer_id,
        received_from=received_from,
        received_to=received_to,
        status_filter=status_filter,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_request(
    body: CreateTestRequestRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    data = test_request_service.create_request(
        db,
        user=user,
        customer_id=body.customer_id,
        sender_name=body.sender_name,
        department_id=body.department_id,
        received_by=body.received_by,
        received_at=body.received_at,
        note=body.note,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.get("/{request_id}")
def get_request(
    request_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    return ok(test_request_service.get_request_detail(db, request_id))


@router.patch("/{request_id}")
def update_request(
    request_id: uuid.UUID,
    body: UpdateTestRequestRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    changes = body.model_dump(exclude_unset=True)
    data = test_request_service.update_request(
        db,
        user=user,
        request_id=request_id,
        changes=changes,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== Nested: samples =====
@router.get("/{request_id}/samples")
def list_request_samples(
    request_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    page, limit = normalize_pagination(page, limit)
    items, total = sample_service.list_request_samples(
        db, request_id=request_id, page=page, limit=limit
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("/{request_id}/samples", status_code=status.HTTP_201_CREATED)
def add_sample(
    request_id: uuid.UUID,
    body: CreateSampleRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    data = sample_service.add_sample(
        db,
        user=user,
        request_id=request_id,
        description=body.description,
        deadline_at=body.deadline_at,
        condition_status=body.condition_status,
        condition_note=body.condition_note,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== Nested: attachments =====
@router.get("/{request_id}/attachments")
def list_request_attachments(
    request_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    return ok(
        sample_attachment_service.list_request_attachments(db, request_id=request_id)
    )


@router.post("/{request_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_request_attachment(
    request_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    content = await file.read()
    data = sample_attachment_service.upload_request_attachment(
        db,
        user=user,
        request_id=request_id,
        file_name=file.filename or "file",
        content=content,
        mime=file.content_type,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)
