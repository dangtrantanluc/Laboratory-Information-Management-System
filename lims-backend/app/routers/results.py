"""Router results (M1) — duyệt / trả lại / tạo phiên bản sửa / đính kèm raw data (FR-009/010)."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import ok
from app.db.database import get_db
from app.schemas.sample import (
    ApproveResultRequest,
    ReturnResultRequest,
    ReviseResultRequest,
)
from app.services import result_service, sample_attachment_service, sample_common

router = APIRouter(prefix="/results", tags=["m1-results"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.post("/{result_id}/approve")
def approve_result(
    result_id: uuid.UUID,
    body: ApproveResultRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    data = result_service.approve_result(
        db,
        user=user,
        result_id=result_id,
        note=body.note,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.post("/{result_id}/return")
def return_result(
    result_id: uuid.UUID,
    body: ReturnResultRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    data = result_service.return_result(
        db,
        user=user,
        result_id=result_id,
        reason=body.reason,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.post("/{result_id}/revisions", status_code=status.HTTP_201_CREATED)
def revise_result(
    result_id: uuid.UUID,
    body: ReviseResultRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    data = result_service.revise_result(
        db,
        user=user,
        result_id=result_id,
        result_data=body.result_data,
        reason=body.reason,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.get("/{result_id}/attachments")
def list_result_attachments(
    result_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    return ok(
        sample_attachment_service.list_result_attachments(
            db, user=user, result_id=result_id
        )
    )


@router.post("/{result_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_result_attachment(
    result_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    content = await file.read()
    data = sample_attachment_service.upload_result_attachment(
        db,
        user=user,
        result_id=result_id,
        file_name=file.filename or "file",
        content=content,
        mime=file.content_type,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)
