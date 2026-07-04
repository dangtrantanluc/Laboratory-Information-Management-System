"""Attachment service — tải file dùng chung (M7 #30) + upload generic cho M1/M2.

RBAC theo owner resource: M7 chỉ enforce phần đã biết (M1 mẫu/kết quả: cấm accountant).
Khi M1/M2/M3 có RBAC chi tiết, sẽ mở rộng _check_owner_read_permission.
"""
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException, forbidden, not_found, unprocessable
from app.models.attachment import Attachment, VALID_OWNER_TYPES
from app.services import audit_service, storage_service

# owner_type thuộc nghiệp vụ M1 (mẫu/kết quả) — kế toán bị cấm (B03)
_M1_OWNER_TYPES = {"test_request", "sample", "sample_result"}


def _check_owner_read_permission(user: CurrentUser, owner_type: str) -> None:
    """RBAC theo owner resource. M7 enforce phần đã chốt; module sau mở rộng.

    - M1 (mẫu/kết quả): kế toán bị cấm → FORBIDDEN_ACCOUNTANT (B03).
    - Các owner_type khác: mọi vai trò đã đăng nhập được đọc (M2/M3 nới RBAC riêng sau).
    """
    if owner_type in _M1_OWNER_TYPES and user.role == "accountant":
        raise AppException(
            "FORBIDDEN_ACCOUNTANT",
            "Kế toán không được truy cập tài nguyên mẫu/kết quả",
            403,
        )


def get_download(
    db: Session,
    *,
    user: CurrentUser,
    attachment_id: uuid.UUID,
    inline: bool,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    att = db.execute(
        select(Attachment).where(
            Attachment.id == attachment_id, Attachment.deleted_at.is_(None)
        )
    ).scalar_one_or_none()
    if att is None:
        raise not_found("Không tìm thấy tệp đính kèm")

    _check_owner_read_permission(user, att.owner_type)

    download_url = storage_service.presigned_get_url(
        att.file_key, file_name=att.file_name, inline=inline
    )

    uploader_name = None
    from app.models.user import User  # local import tránh vòng import

    uploader = db.get(User, att.uploaded_by)
    if uploader:
        uploader_name = uploader.full_name

    # Ghi audit lượt tải (R15 — đếm lượt tải cho M3.3/thống kê)
    audit_service.log_action(
        db,
        action="ATTACHMENT_DOWNLOAD",
        resource=att.owner_type,
        user_id=user.id,
        resource_id=att.owner_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"attachment_id": str(att.id), "file_name": att.file_name},
    )
    db.commit()

    from datetime import datetime, timedelta, timezone

    from app.config import settings

    return {
        "id": att.id,
        "owner_type": att.owner_type,
        "owner_id": att.owner_id,
        "file_name": att.file_name,
        "mime": att.mime,
        "size": att.size,
        "download_url": download_url,
        "url_expires_at": (
            datetime.now(timezone.utc)
            + timedelta(seconds=settings.presigned_url_ttl_seconds)
        ),
        "uploaded_by_name": uploader_name,
        "uploaded_at": att.uploaded_at,
    }


def create_attachment(
    db: Session,
    *,
    user: CurrentUser,
    owner_type: str,
    owner_id: uuid.UUID,
    file_name: str,
    content: bytes,
    mime: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    """Upload generic — M1/M2 gọi để gắn file. owner tồn tại enforce app-layer (D9).

    Lưu ý: M7 chưa có bảng owner (sample/chemical...) → kiểm tra owner tồn tại
    sẽ được module tương ứng bổ sung. M7 chỉ chấp nhận owner_type trong whitelist.
    """
    if owner_type not in VALID_OWNER_TYPES:
        raise unprocessable("INVALID_OWNER_TYPE", "Loại đối tượng đính kèm không hợp lệ")

    from app.config import settings

    if len(content) > settings.max_upload_size_bytes:
        raise unprocessable(
            "FILE_TOO_LARGE",
            f"Tệp vượt quá giới hạn {settings.max_upload_size_bytes // (1024*1024)}MB",
        )

    file_key = storage_service.build_object_key(owner_type, owner_id, file_name)
    storage_service.put_object(file_key, content, content_type=mime)

    att = Attachment(
        owner_type=owner_type,
        owner_id=owner_id,
        file_key=file_key,
        file_name=file_name,
        mime=mime,
        size=len(content),
        uploaded_by=user.id,
    )
    db.add(att)
    db.flush()
    audit_service.log_action(
        db,
        action="ATTACHMENT_UPLOAD",
        resource=owner_type,
        user_id=user.id,
        resource_id=owner_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"attachment_id": str(att.id), "file_name": file_name, "size": len(content)},
    )
    db.commit()
    db.refresh(att)
    return {
        "id": att.id,
        "owner_type": att.owner_type,
        "owner_id": att.owner_id,
        "file_name": att.file_name,
        "mime": att.mime,
        "size": att.size,
        "uploaded_at": att.uploaded_at,
    }
