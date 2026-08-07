"""Attachment service — tải file dùng chung (M7 #30) + upload generic cho M1/M2.

Uỷ quyền cấp đối tượng nằm ở `attachment_authz` (bảng định tuyến theo owner_type,
DENY BY DEFAULT). Trước đây file này chỉ có MỘT luật — cấm `office` đọc 3 owner_type
của M1 — nên bất kỳ ai đăng nhập cũng tải được mọi tệp trong hệ thống nếu biết id, và
gắn được tệp vào bất kỳ owner_id nào. Xem docstring của `attachment_authz` để biết vì
sao luật được đặt ở module riêng thay vì ở đây.
"""
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import not_found, unprocessable
from app.models.attachment import Attachment, VALID_OWNER_TYPES
from app.services import attachment_authz, attachment_common, audit_service, storage_service


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

    attachment_authz.assert_can_read(
        db, user, owner_type=att.owner_type, owner_id=att.owner_id
    )

    # Chặn stored-XSS: chỉ phục vụ inline nếu mime nằm trong allowlist an toàn,
    # bất kể client yêu cầu `disposition=inline` (PRODUCTION_READINESS_REVIEW
    # §Security: "Same-origin inline file serving enables stored XSS").
    safe_inline = inline and attachment_common.is_inline_safe(
        att.mime, allowed=attachment_common.GENERIC_ALLOWED_MIME
    )
    download_url = storage_service.presigned_get_url(
        att.file_key, file_name=att.file_name, inline=safe_inline
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
    skip_authz: bool = False,
) -> dict:
    """Upload generic. Quyền ghi + sự tồn tại của owner do `attachment_authz` kiểm.

    `skip_authz=True` dành cho caller ĐÃ tự kiểm quyền theo luật riêng của module
    (sample_report_service, calibration_service, equipment_service, form_file_service,
    và các router có guard ngay trước lời gọi). Mặc định là KIỂM — đường generic
    `POST /attachments` đi qua nhánh mặc định đó.
    """
    if owner_type not in VALID_OWNER_TYPES:
        raise unprocessable(ErrorCode.INVALID_OWNER_TYPE, "Loại đối tượng đính kèm không hợp lệ")

    if not skip_authz:
        attachment_authz.assert_can_write(db, user, owner_type=owner_type, owner_id=owner_id)

    attachment_common.check_mime(mime, allowed=attachment_common.GENERIC_ALLOWED_MIME)
    attachment_common.check_size(content)

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
