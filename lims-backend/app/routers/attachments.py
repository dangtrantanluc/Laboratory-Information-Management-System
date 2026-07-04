"""Router attachments (M7/chung) — tải file (presigned URL) + upload generic cho M1/M2."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import ok
from app.db.database import get_db
from app.services import attachment_service

router = APIRouter(prefix="/attachments", tags=["attachments"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    request: Request,
    owner_type: str = Form(...),
    owner_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload generic — M1/M2 dùng để gắn file. owner tồn tại enforce ở module owner."""
    content = await file.read()
    data = attachment_service.create_attachment(
        db,
        user=user,
        owner_type=owner_type,
        owner_id=owner_id,
        file_name=file.filename or "file",
        content=content,
        mime=file.content_type,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.get("/{attachment_id}")
def download_attachment(
    attachment_id: uuid.UUID,
    request: Request,
    disposition: str = Query(default="attachment"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = attachment_service.get_download(
        db,
        user=user,
        attachment_id=attachment_id,
        inline=(disposition == "inline"),
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)
