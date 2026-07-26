"""Avatar service — ảnh đại diện lưu MinIO, đường dẫn lưu DB (m30).

Thiết kế: ảnh nằm ở MinIO, bảng `users` chỉ giữ `avatar_key` (object key). API trả
presigned URL TTL 15 phút chứ không trả link vĩnh viễn — bucket không cần công khai.

Cố ý KHÔNG dùng bảng `attachments`: bảng đó có CHECK whitelist `owner_type` và một
tầng phân quyền theo module; ảnh đại diện là dữ liệu 1-1 của user, gắn thẳng vào
`users.avatar_key` đơn giản và đúng ngữ nghĩa hơn.
"""
import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import validation_error
from app.models.user import User
from app.services import audit_service, storage_service

logger = logging.getLogger("lims.avatar")

# Chỉ ảnh raster phổ biến. KHÔNG cho image/svg+xml: SVG là XML, có thể nhúng script →
# stored-XSS khi trình duyệt mở trực tiếp file từ presigned URL.
ALLOWED_AVATAR_MIME = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

# Chữ ký nhị phân (magic bytes) — không tin Content-Type do client khai báo.
_MAGIC = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],  # RIFF....WEBP — kiểm thêm ở dưới
}


def _sniff_mime(content: bytes) -> Optional[str]:
    """Đoán MIME từ magic bytes. Trả None nếu không khớp định dạng nào cho phép."""
    for mime, signatures in _MAGIC.items():
        for sig in signatures:
            if content.startswith(sig):
                if mime == "image/webp":
                    # RIFF<4 byte size>WEBP
                    if len(content) < 12 or content[8:12] != b"WEBP":
                        continue
                return mime
    return None


def upload_avatar(
    db: Session,
    *,
    user_id: uuid.UUID,
    content: bytes,
    file_name: str,
    declared_mime: Optional[str],
    correlation_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> dict:
    """Lưu ảnh vào MinIO, cập nhật users.avatar_key, xoá ảnh cũ."""
    if not content:
        raise validation_error("Tệp rỗng")
    if len(content) > settings.avatar_max_size_bytes:
        mb = settings.avatar_max_size_bytes // (1024 * 1024)
        raise validation_error(
            f"Ảnh vượt quá {mb}MB",
            details=[{"field": "file", "max_bytes": settings.avatar_max_size_bytes}],
        )

    # Tin magic bytes, không tin Content-Type của client. Đổi đuôi .png cho file .svg
    # hay .exe sẽ bị chặn ở đây.
    sniffed = _sniff_mime(content)
    if sniffed is None:
        raise validation_error(
            "Định dạng ảnh không hợp lệ. Chỉ chấp nhận JPG, PNG hoặc WEBP.",
            details=[{"field": "file", "declared_mime": declared_mime}],
        )

    user = db.get(User, user_id)
    if user is None:
        raise validation_error("Không tìm thấy người dùng")

    old_key = user.avatar_key
    new_key = storage_service.build_object_key("user_avatar", user_id, file_name)
    storage_service.put_object(new_key, content, content_type=sniffed)

    user.avatar_key = new_key
    audit_service.log_action(
        db,
        action="UPDATE_AVATAR",
        resource="user",
        resource_id=user_id,
        user_id=user_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"size": len(content), "mime": sniffed},
    )
    db.commit()

    # Xoá ảnh cũ SAU KHI commit — nếu commit hỏng, ảnh cũ vẫn còn nguyên.
    if old_key and old_key != new_key:
        storage_service.remove_object(old_key)

    return {"avatar_url": avatar_url(new_key), "avatar_key": new_key}


def remove_avatar(
    db: Session,
    *,
    user_id: uuid.UUID,
    correlation_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> dict:
    """Gỡ ảnh đại diện, quay về avatar chữ cái đầu."""
    user = db.get(User, user_id)
    if user is None:
        raise validation_error("Không tìm thấy người dùng")

    old_key = user.avatar_key
    if not old_key:
        return {"avatar_url": None}

    user.avatar_key = None
    audit_service.log_action(
        db,
        action="REMOVE_AVATAR",
        resource="user",
        resource_id=user_id,
        user_id=user_id,
        correlation_id=correlation_id,
        ip=ip,
    )
    db.commit()
    storage_service.remove_object(old_key)
    return {"avatar_url": None}


def avatar_url(avatar_key: Optional[str]) -> Optional[str]:
    """Presigned URL TTL ngắn cho ảnh đại diện. None nếu chưa có ảnh.

    Lỗi MinIO KHÔNG được làm hỏng /auth/me — thiếu ảnh thì frontend tự rơi về avatar
    chữ cái đầu.
    """
    if not avatar_key:
        return None
    try:
        return storage_service.presigned_get_url(avatar_key, inline=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Không tạo được presigned URL cho avatar",
            extra={"key": avatar_key, "error": str(exc)},
        )
        return None
