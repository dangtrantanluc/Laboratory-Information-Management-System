"""M3 version service — vòng đời phiên bản (state machine §8.3) + file MinIO + duyệt.

Pattern y hệt M1 result_service: state machine whitelist, versioning immutable
(approved/obsolete bất biến), approve atomic + row-lock document + auto-obsolete bản
cũ + set current_version_id (BR-DOC-008, ≤1 approved enforce partial unique DB-level),
tách soạn–duyệt (SELF_APPROVAL_FORBIDDEN — BR-DOC-009).
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import CurrentUser
from app.core.exceptions import AppException, unprocessable, validation_error
from app.models.attachment import Attachment
from app.models.document import Document, DocumentVersion
from app.services import audit_service, document_common as dc, notification_service, storage_service

# Whitelist MIME tài liệu (BR-DOC-013): PDF/DOCX/XLSX/PNG/JPG
_ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword",
    "application/vnd.ms-excel",
    "image/png",
    "image/jpeg",
    "image/jpg",
}
_OWNER_TYPE = "document_version"


def _check_mime(mime: Optional[str]) -> None:
    if mime is None or mime.lower() not in _ALLOWED_MIME:
        raise unprocessable(
            "INVALID_FILE_TYPE",
            "Định dạng tệp không hợp lệ (chỉ PDF/DOCX/XLSX/PNG/JPG)",
        )


def _check_size(content: bytes) -> None:
    if len(content) > settings.max_upload_size_bytes:
        raise unprocessable(
            "FILE_TOO_LARGE",
            f"Tệp vượt quá giới hạn {settings.max_upload_size_bytes // (1024 * 1024)}MB",
        )


def _version_file(db: Session, version_id: uuid.UUID) -> Optional[Attachment]:
    return db.execute(
        select(Attachment)
        .where(
            Attachment.owner_type == _OWNER_TYPE,
            Attachment.owner_id == version_id,
            Attachment.deleted_at.is_(None),
        )
        .order_by(Attachment.uploaded_at.desc())
    ).scalars().first()


def _file_dict(att: Optional[Attachment]) -> Optional[dict]:
    if att is None:
        return None
    return {
        "attachment_id": att.id,
        "filename": att.file_name,
        "size": att.size,
        "mime": att.mime,
    }


def _store_file(
    db: Session,
    *,
    user: CurrentUser,
    version_id: uuid.UUID,
    file_name: str,
    content: bytes,
    mime: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> Attachment:
    """Validate + đẩy MinIO + INSERT attachments (owner_type=document_version). Caller commit."""
    _check_mime(mime)
    _check_size(content)
    file_key = storage_service.build_object_key(_OWNER_TYPE, version_id, file_name)
    storage_service.put_object(file_key, content, content_type=mime)
    att = Attachment(
        owner_type=_OWNER_TYPE,
        owner_id=version_id,
        file_key=file_key,
        file_name=file_name,
        mime=mime,
        size=len(content),
        uploaded_by=user.id,
    )
    db.add(att)
    db.flush()
    return att


def serialize_version(
    db: Session, version: DocumentVersion, *, include_file: bool = True
) -> dict:
    is_obsolete = version.status == "obsolete"
    data: dict = {
        "id": version.id,
        "document_id": version.document_id,
        "version_no": version.version_no,
        "status": version.status,
        "is_obsolete": is_obsolete,
        "change_note": version.change_note,
        "created_by": version.created_by,
        "created_by_name": dc.user_name(db, version.created_by),
        "created_at": version.created_at,
        "submitted_at": version.submitted_at,
        "reviewed_at": version.reviewed_at,
        "approved_by_name": dc.user_name(db, version.approved_by),
        "approved_at": version.approved_at,
        "reject_reason": version.reject_reason,
    }
    if is_obsolete:
        data["obsolete_label"] = "KHÔNG SỬ DỤNG — lỗi thời"
    if include_file:
        data["file"] = _file_dict(_version_file(db, version.id))
    return data


# ===== Create new version (FR-DOC-006, #9) =====
def create_version(
    db: Session,
    *,
    user: CurrentUser,
    document_id: uuid.UUID,
    change_note: Optional[str],
    file_name: str,
    content: bytes,
    mime: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    dc.deny_accountant_write(user)
    doc = dc.get_document_or_404(db, document_id, lock=True)
    dc.assert_write_scope(user, doc.department_id)

    # change_note bắt buộc từ v2 (BR-DOC-016)
    existing_count = db.execute(
        select(func.count())
        .select_from(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
    ).scalar_one()
    if existing_count >= 1 and not (change_note and change_note.strip()):
        raise AppException(
            "CHANGE_NOTE_REQUIRED",
            "Bắt buộc ghi chú thay đổi từ phiên bản thứ 2",
            400,
        )

    # 1 draft/review chưa kết thúc/tài liệu (OQ#6, DRAFT_ALREADY_EXISTS)
    open_exists = db.execute(
        select(func.count())
        .select_from(DocumentVersion)
        .where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.status.in_(("draft", "review")),
            DocumentVersion.deleted_at.is_(None),
        )
    ).scalar_one()
    if open_exists > 0:
        raise AppException(
            "DRAFT_ALREADY_EXISTS",
            "Đã có phiên bản đang soạn/chờ duyệt — hoàn tất trước khi tạo mới",
            409,
        )

    max_no = db.execute(
        select(func.coalesce(func.max(DocumentVersion.version_no), 0)).where(
            DocumentVersion.document_id == document_id
        )
    ).scalar_one()
    version = DocumentVersion(
        document_id=document_id,
        version_no=max_no + 1,
        change_note=change_note.strip() if change_note else None,
        status="draft",
        created_by=user.id,
    )
    db.add(version)
    db.flush()

    _store_file(
        db,
        user=user,
        version_id=version.id,
        file_name=file_name,
        content=content,
        mime=mime,
        correlation_id=correlation_id,
        ip=ip,
    )

    audit_service.log_action(
        db,
        action="DOCUMENT_VERSION_CREATE",
        resource="document_version",
        user_id=user.id,
        resource_id=version.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"document_id": str(document_id), "version_no": version.version_no},
    )
    dc.log_access(
        db,
        document_id=document_id,
        version_id=version.id,
        user_id=user.id,
        action="edit",
    )
    db.commit()
    db.refresh(version)
    return serialize_version(db, version)


# ===== Update version (FR-DOC-007, #11) — chỉ draft =====
def update_version(
    db: Session,
    *,
    user: CurrentUser,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    change_note: Optional[str],
    file_name: Optional[str],
    content: Optional[bytes],
    mime: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    dc.deny_accountant_write(user)
    doc = dc.get_document_or_404(db, document_id, lock=True)
    version = dc.get_version_or_404(db, document_id, version_id, lock=True)

    # người soạn / trưởng nhóm phòng / admin / leader (FR-007 A2)
    if not (version.created_by == user.id or dc.can_approve(user, doc.department_id)):
        raise dc.forbidden("Bạn không có quyền sửa phiên bản này")
    if version.status != "draft":
        raise unprocessable(
            "VERSION_LOCKED",
            "Chỉ phiên bản nháp được sửa (đã gửi duyệt/ban hành thì bất biến)",
        )
    if change_note is None and content is None:
        raise validation_error("Phải cung cấp ít nhất 1 trường để cập nhật")

    if change_note is not None:
        version.change_note = change_note.strip() or None
    if content is not None:
        # đánh dấu file cũ deleted, thêm file mới
        old = _version_file(db, version.id)
        if old is not None:
            old.deleted_at = func.now()
        _store_file(
            db,
            user=user,
            version_id=version.id,
            file_name=file_name or "document",
            content=content,
            mime=mime,
            correlation_id=correlation_id,
            ip=ip,
        )
    version.updated_at = func.now()
    db.flush()

    audit_service.log_action(
        db,
        action="DOCUMENT_VERSION_UPDATE",
        resource="document_version",
        user_id=user.id,
        resource_id=version.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"document_id": str(document_id), "file_replaced": content is not None},
    )
    dc.log_access(
        db,
        document_id=document_id,
        version_id=version.id,
        user_id=user.id,
        action="edit",
    )
    db.commit()
    db.refresh(version)
    return serialize_version(db, version)


# ===== Submit review (FR-DOC-008, #12) — draft → review =====
def submit_review(
    db: Session,
    *,
    user: CurrentUser,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    dc.deny_accountant_write(user)
    doc = dc.get_document_or_404(db, document_id, lock=True)
    version = dc.get_version_or_404(db, document_id, version_id, lock=True)

    if not (version.created_by == user.id or dc.can_approve(user, doc.department_id)):
        raise dc.forbidden("Chỉ người soạn / trưởng nhóm / admin được gửi duyệt")
    if version.status != "draft":
        raise dc.invalid_state(
            f"Không thể gửi duyệt phiên bản đang ở trạng thái '{version.status}'"
        )
    if _version_file(db, version.id) is None:
        raise unprocessable(
            "VERSION_FILE_REQUIRED", "Phiên bản chưa có tệp đính kèm để gửi duyệt"
        )

    version.submitted_by = user.id
    version.submitted_at = func.now()
    dc.change_version_status(
        db,
        version,
        "review",
        trigger="submit_review",
        user_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
    )
    db.flush()

    audit_service.log_action(
        db,
        action="DOCUMENT_VERSION_SUBMIT",
        resource="document_version",
        user_id=user.id,
        resource_id=version.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"document_id": str(document_id)},
    )
    # thông báo người duyệt (trưởng nhóm phòng) — best-effort
    _notify_reviewers(db, doc, version)
    db.commit()
    db.refresh(version)
    return {
        "id": version.id,
        "version_no": version.version_no,
        "status": version.status,
        "submitted_at": version.submitted_at,
        "state_change": {"from": "draft", "to": "review"},
    }


def _notify_reviewers(db: Session, doc: Document, version: DocumentVersion) -> None:
    """Thông báo trưởng nhóm phòng sở hữu (BR-DOC-018)."""
    from app.models.department import Department

    dept = db.get(Department, doc.department_id)
    if dept and dept.lead_user_id and dept.lead_user_id != version.created_by:
        notification_service.create_notification(
            db,
            user_id=dept.lead_user_id,
            type="document_review",
            title="Phiên bản tài liệu chờ duyệt",
            body=f"{doc.code} — phiên bản {version.version_no} cần duyệt",
            ref_type="document_version",
            ref_id=version.id,
        )


# ===== Approve (FR-DOC-009/011, #13) — review → approved + auto-obsolete (CỐT LÕI) =====
def approve_version(
    db: Session,
    *,
    user: CurrentUser,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    note: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    dc.deny_accountant_write(user)
    # row-lock document → tuần tự hóa approve cùng tài liệu (NFR-CONCUR-DOC-001)
    doc = dc.get_document_or_404(db, document_id, lock=True)
    version = dc.get_version_or_404(db, document_id, version_id, lock=True)

    if not dc.can_approve(user, doc.department_id):
        raise dc.forbidden("Chỉ trưởng nhóm phòng / lãnh đạo / admin được duyệt")
    # tách soạn–duyệt (BR-DOC-009, §8.3.2)
    if version.created_by == user.id:
        raise AppException(
            "SELF_APPROVAL_FORBIDDEN",
            "Người duyệt phải khác người soạn phiên bản (tách trách nhiệm §8.3.2)",
            403,
            details=[{"field": "approved_by", "created_by": str(version.created_by)}],
        )
    if version.status != "review":
        raise dc.invalid_state(
            f"Không thể duyệt phiên bản đang ở trạng thái '{version.status}'. "
            "Phải gửi duyệt (draft → review) trước."
        )

    # obsolete bản approved cũ (nếu có) TRONG transaction
    old = db.execute(
        select(DocumentVersion)
        .where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.status == "approved",
        )
        .with_for_update()
    ).scalar_one_or_none()
    obsoleted = None
    if old is not None:
        dc.change_version_status(
            db,
            old,
            "obsolete",
            trigger="auto_obsolete_on_approve",
            user_id=user.id,
            correlation_id=correlation_id,
            ip=ip,
        )
        audit_service.log_action(
            db,
            action="DOCUMENT_VERSION_OBSOLETE",
            resource="document_version",
            user_id=user.id,
            resource_id=old.id,
            correlation_id=correlation_id,
            ip=ip,
            detail={"document_id": str(document_id), "replaced_by": str(version.id)},
        )
        obsoleted = old

    # approve version mới
    version.reviewed_by = user.id
    version.reviewed_at = func.now()
    version.approved_by = user.id
    version.approved_at = func.now()
    dc.change_version_status(
        db,
        version,
        "approved",
        trigger="approve",
        user_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
    )
    doc.current_version_id = version.id
    doc.updated_by = user.id
    doc.updated_at = func.now()

    audit_service.log_action(
        db,
        action="DOCUMENT_VERSION_APPROVE",
        resource="document_version",
        user_id=user.id,
        resource_id=version.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"document_id": str(document_id), "note": note},
    )
    # thông báo người soạn
    notification_service.create_notification(
        db,
        user_id=version.created_by,
        type="document_approved",
        title="Phiên bản tài liệu đã được ban hành",
        body=f"{doc.code} — phiên bản {version.version_no} đã được duyệt",
        ref_type="document_version",
        ref_id=version.id,
    )

    try:
        db.commit()
    except IntegrityError:
        # uq_doc_one_approved race — bản approved thứ 2 bị DB chặn (NFR-INTEG-DOC-001)
        db.rollback()
        raise AppException(
            "VERSION_CONFLICT",
            "Tài liệu vừa được ban hành phiên bản khác — vui lòng tải lại",
            409,
        )
    db.refresh(version)
    db.refresh(doc)
    return {
        "id": version.id,
        "version_no": version.version_no,
        "status": version.status,
        "approved_by": version.approved_by,
        "approved_by_name": dc.user_name(db, version.approved_by),
        "approved_at": version.approved_at,
        "state_change": {"from": "review", "to": "approved"},
        "document": {
            "id": doc.id,
            "current_version_id": doc.current_version_id,
            "obsoleted_version": (
                {
                    "id": obsoleted.id,
                    "version_no": obsoleted.version_no,
                    "status": "obsolete",
                }
                if obsoleted is not None
                else None
            ),
        },
    }


# ===== Reject (FR-DOC-010, #14) — review → draft =====
def reject_version(
    db: Session,
    *,
    user: CurrentUser,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    reject_reason: str,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    dc.deny_accountant_write(user)
    doc = dc.get_document_or_404(db, document_id, lock=True)
    version = dc.get_version_or_404(db, document_id, version_id, lock=True)

    if not dc.can_approve(user, doc.department_id):
        raise dc.forbidden("Chỉ trưởng nhóm phòng / lãnh đạo / admin được từ chối")
    if not (reject_reason and reject_reason.strip()):
        raise AppException(
            "REJECT_REASON_REQUIRED", "Phải nhập lý do từ chối", 400
        )
    if version.status != "review":
        raise dc.invalid_state(
            f"Không thể từ chối phiên bản đang ở trạng thái '{version.status}'"
        )

    version.reviewed_by = user.id
    version.reviewed_at = func.now()
    version.reject_reason = reject_reason.strip()
    # về draft + reset mốc submit để được gửi duyệt lại
    version.submitted_by = None
    version.submitted_at = None
    dc.change_version_status(
        db,
        version,
        "draft",
        trigger="reject",
        user_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
    )
    db.flush()

    audit_service.log_action(
        db,
        action="DOCUMENT_VERSION_REJECT",
        resource="document_version",
        user_id=user.id,
        resource_id=version.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"document_id": str(document_id), "reason": reject_reason.strip()},
    )
    notification_service.create_notification(
        db,
        user_id=version.created_by,
        type="document_rejected",
        title="Phiên bản tài liệu bị từ chối",
        body=f"{doc.code} — phiên bản {version.version_no}: {reject_reason.strip()}",
        ref_type="document_version",
        ref_id=version.id,
    )
    db.commit()
    db.refresh(version)
    return {
        "id": version.id,
        "version_no": version.version_no,
        "status": version.status,
        "reject_reason": version.reject_reason,
        "state_change": {"from": "review", "to": "draft"},
    }


# ===== Download (FR-DOC-012, #15) — presigned URL + ghi access_log =====
def download_version(
    db: Session,
    *,
    user: CurrentUser,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    doc = dc.get_document_or_404(db, document_id)
    # mức bảo mật (BR-DOC-006)
    if not dc.can_view_restricted(user, doc):
        raise dc.restricted_access()
    version = dc.get_version_or_404(db, document_id, version_id)

    # hiển thị version theo trạng thái (BR-DOC-011)
    if not dc.can_view_unpublished_version(user, doc, version):
        raise AppException(
            "VERSION_NOT_PUBLISHED",
            "Phiên bản chưa ban hành — bạn không có quyền tải",
            403,
        )
    # kế toán chỉ tải approved (BR-DOC-005)
    if user.role == "accountant" and version.status != "approved":
        raise AppException(
            "VERSION_NOT_PUBLISHED", "Kế toán chỉ được tải phiên bản đã ban hành", 403
        )

    att = _version_file(db, version.id)
    if att is None:
        raise dc.version_not_found()

    try:
        download_url = storage_service.presigned_get_url(
            att.file_key, file_name=att.file_name
        )
    except Exception as exc:  # noqa: BLE001
        raise AppException(
            "STORAGE_UNAVAILABLE", "Kho lưu trữ tạm thời không khả dụng", 503
        ) from exc

    is_obsolete = version.status == "obsolete"
    audit_service.log_action(
        db,
        action="DOCUMENT_DOWNLOAD",
        resource="document_version",
        user_id=user.id,
        resource_id=version.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"document_id": str(document_id), "attachment_id": str(att.id)},
    )
    dc.log_access(
        db,
        document_id=document_id,
        version_id=version.id,
        user_id=user.id,
        action="download",
    )
    db.commit()
    return {
        "version_id": version.id,
        "version_no": version.version_no,
        "status": version.status,
        "is_obsolete": is_obsolete,
        "obsolete_warning": (
            "Tài liệu lỗi thời — KHÔNG SỬ DỤNG" if is_obsolete else None
        ),
        "filename": att.file_name,
        "mime": att.mime,
        "size": att.size,
        "download_url": download_url,
        "url_expires_at": datetime.now(timezone.utc)
        + timedelta(seconds=settings.presigned_url_ttl_seconds),
    }


# ===== List versions (FR-DOC-005, #8) =====
def list_versions(
    db: Session,
    *,
    user: CurrentUser,
    document_id: uuid.UUID,
    status_filter: Optional[str],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    doc = dc.get_document_or_404(db, document_id)
    if not dc.can_view_restricted(user, doc):
        raise dc.restricted_access()

    rows = db.execute(
        select(DocumentVersion)
        .where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.deleted_at.is_(None),
        )
        .order_by(DocumentVersion.version_no.desc())
    ).scalars().all()

    visible = [v for v in rows if dc.can_view_unpublished_version(user, doc, v)]
    if status_filter:
        visible = [v for v in visible if v.status == status_filter]
    total = len(visible)
    start = (page - 1) * limit
    page_rows = visible[start : start + limit]
    return [serialize_version(db, v) for v in page_rows], total


# ===== Get single version (FR-DOC-005, #10) =====
def get_version(
    db: Session,
    *,
    user: CurrentUser,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
) -> dict:
    doc = dc.get_document_or_404(db, document_id)
    if not dc.can_view_restricted(user, doc):
        raise dc.restricted_access()
    version = dc.get_version_or_404(db, document_id, version_id)
    if not dc.can_view_unpublished_version(user, doc, version):
        raise AppException(
            "VERSION_NOT_PUBLISHED",
            "Phiên bản chưa ban hành — bạn không có quyền xem",
            403,
        )
    data = serialize_version(db, version)
    data["document_code"] = doc.code
    return data


# ===== Pending review (#17) =====
def list_pending_review(
    db: Session,
    *,
    user: CurrentUser,
    department_id: Optional[uuid.UUID],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    dc.deny_accountant_write(user)  # nghiệp vụ quản lý — kế toán cấm
    if not (dc.is_privileged(user) or user.is_dept_lead):
        raise dc.forbidden("Chỉ trưởng nhóm / lãnh đạo / admin xem hàng chờ duyệt")

    conditions = [
        DocumentVersion.status == "review",
        DocumentVersion.deleted_at.is_(None),
        Document.deleted_at.is_(None),
    ]
    if dc.is_privileged(user):
        if department_id is not None:
            conditions.append(Document.department_id == department_id)
    else:
        # trưởng nhóm: chỉ phòng mình
        conditions.append(Document.department_id == user.department_id)

    base = (
        select(DocumentVersion, Document)
        .join(Document, Document.id == DocumentVersion.document_id)
        .where(*conditions)
    )
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()
    rows = db.execute(
        base.order_by(DocumentVersion.submitted_at.asc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    items = []
    for version, doc in rows:
        items.append(
            {
                "document_id": doc.id,
                "document_code": doc.code,
                "title": doc.title,
                "department_name": dc.dept_name(db, doc.department_id),
                "version_id": version.id,
                "version_no": version.version_no,
                "status": version.status,
                "change_note": version.change_note,
                "created_by_name": dc.user_name(db, version.created_by),
                "submitted_at": version.submitted_at,
                # can_approve=false nếu user tự soạn (sẽ SELF_APPROVAL_FORBIDDEN)
                "can_approve": version.created_by != user.id,
            }
        )
    return items, total
