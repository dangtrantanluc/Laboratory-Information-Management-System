"""M1 attachment service — upload/list file cho sample / test_request / sample_result.

Tái dùng storage_service (MinIO) + bảng attachments (polymorphic). RBAC M1:
- Cấm Kế toán.
- Ghi (upload) theo phạm vi phòng (sample/test_request) hoặc người nhập (sample_result).
- Đọc raw data kết quả: theo phạm vi xem kết quả (RESULT_NOT_PUBLISHED nếu pending ngoài nhóm).
- Whitelist MIME PDF/PNG/JPG/XLSX/CSV; size <= cấu hình.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found, unprocessable
from app.models.attachment import Attachment
from app.models.sample import Sample
from app.models.sample_assignment import SampleAssignment
from app.models.sample_result import SampleResult
from app.models.test_request import TestRequest
from app.services import audit_service, sample_common, storage_service

# Whitelist MIME (BR-SAMPLE-012)
_ALLOWED_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
}


def _check_mime(mime: Optional[str]) -> None:
    if mime is None or mime.lower() not in _ALLOWED_MIME:
        raise unprocessable(
            "INVALID_FILE_TYPE",
            "Định dạng tệp không hợp lệ (chỉ PDF/PNG/JPG/XLSX/CSV)",
        )


def _check_size(content: bytes) -> None:
    if len(content) > settings.max_upload_size_bytes:
        raise unprocessable(
            "FILE_TOO_LARGE",
            f"Tệp vượt quá giới hạn {settings.max_upload_size_bytes // (1024 * 1024)}MB",
        )


def _serialize_list(db: Session, att: Attachment) -> dict:
    download_url = storage_service.presigned_get_url(att.file_key, file_name=att.file_name)
    return {
        "id": att.id,
        "owner_type": att.owner_type,
        "owner_id": att.owner_id,
        "file_name": att.file_name,
        "mime": att.mime,
        "size": att.size,
        "download_url": download_url,
        "url_expires_at": datetime.now(timezone.utc)
        + timedelta(seconds=settings.presigned_url_ttl_seconds),
        "uploaded_by_name": sample_common.user_name(db, att.uploaded_by),
        "uploaded_at": att.uploaded_at,
    }


def _list_attachments(db: Session, owner_type: str, owner_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(Attachment)
        .where(
            Attachment.owner_type == owner_type,
            Attachment.owner_id == owner_id,
            Attachment.deleted_at.is_(None),
        )
        .order_by(Attachment.uploaded_at.asc())
    ).scalars().all()
    return [_serialize_list(db, a) for a in rows]


def _upload(
    db: Session,
    *,
    user: CurrentUser,
    owner_type: str,
    owner_id: uuid.UUID,
    file_name: str,
    content: bytes,
    mime: Optional[str],
    action: str,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    _check_mime(mime)
    _check_size(content)
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
        action=action,
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


# ===== Sample =====
def list_sample_attachments(db: Session, *, sample_id: uuid.UUID) -> list[dict]:
    sample_common.get_sample_or_404(db, sample_id)
    return _list_attachments(db, "sample", sample_id)


def upload_sample_attachment(
    db: Session, *, user: CurrentUser, sample_id: uuid.UUID, **kw
) -> dict:
    sample = sample_common.get_sample_or_404(db, sample_id)
    sample_common.assert_write_scope(user, sample.department_id)
    return _upload(
        db,
        user=user,
        owner_type="sample",
        owner_id=sample_id,
        action="SAMPLE_ATTACH_UPLOAD",
        **kw,
    )


# ===== Test request =====
def list_request_attachments(db: Session, *, request_id: uuid.UUID) -> list[dict]:
    req = db.get(TestRequest, request_id)
    if req is None or req.deleted_at is not None:
        raise not_found("Không tìm thấy phiếu yêu cầu")
    return _list_attachments(db, "test_request", request_id)


def upload_request_attachment(
    db: Session, *, user: CurrentUser, request_id: uuid.UUID, **kw
) -> dict:
    req = db.get(TestRequest, request_id)
    if req is None or req.deleted_at is not None:
        raise not_found("Không tìm thấy phiếu yêu cầu")
    sample_common.assert_write_scope(user, req.department_id)
    return _upload(
        db,
        user=user,
        owner_type="test_request",
        owner_id=request_id,
        action="REQUEST_ATTACH_UPLOAD",
        **kw,
    )


# ===== Result raw data =====
def _get_result(db: Session, result_id: uuid.UUID) -> SampleResult:
    r = db.get(SampleResult, result_id)
    if r is None:
        raise not_found("Không tìm thấy kết quả")
    return r


def upload_result_attachment(
    db: Session, *, user: CurrentUser, result_id: uuid.UUID, **kw
) -> dict:
    result = _get_result(db, result_id)
    # chỉ người nhập kết quả hoặc Admin
    if not (result.entered_by == user.id or user.role == "admin"):
        raise sample_common.forbidden("Chỉ người nhập kết quả được đính kèm raw data")
    if result.approved_by is not None:
        raise unprocessable(
            "RESULT_LOCKED",
            "Kết quả đã duyệt — sửa phải tạo phiên bản mới",
        )
    return _upload(
        db,
        user=user,
        owner_type="sample_result",
        owner_id=result_id,
        action="SAMPLE_RESULT_ATTACH",
        **kw,
    )


def list_result_attachments(
    db: Session, *, user: CurrentUser, result_id: uuid.UUID
) -> list[dict]:
    result = _get_result(db, result_id)
    assignment = db.get(SampleAssignment, result.assignment_id)
    is_approved = result.approved_by is not None
    if not is_approved:
        # phạm vi xem kết quả pending
        from app.services import result_service

        can_view = result_service._can_view_pending(db, user, assignment, result)
        if not can_view:
            raise AppException(
                "RESULT_NOT_PUBLISHED",
                "Kết quả chưa được duyệt — không thể xem raw data",
                403,
            )
    return _list_attachments(db, "sample_result", result_id)
