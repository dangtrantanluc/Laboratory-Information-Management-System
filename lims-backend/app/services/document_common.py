"""M3 common helpers — RBAC scope, state machine, sinh mã, mức bảo mật, access log.

Tập trung logic dùng chung cho mọi service M3 để khớp contract (15-contract-m3-api.md):
- Cấm Kế toán mọi endpoint GHI (FORBIDDEN — tầng API/service, BR-DOC-005).
- Phạm vi phòng cho ghi (staff chỉ phòng mình — BR-DOC-004).
- Quyền duyệt = trưởng nhóm phòng đó / leader / admin (đọc is_dept_lead — BR-DOC-010).
- 2 mức bảo mật internal/restricted enforce list/get/download (BR-DOC-006).
- Hiển thị version theo trạng thái (BR-DOC-011).
- State machine whitelist version draft→review→approved→obsolete (+review→draft).
- Sinh document_code <prefix loại>-<mã phòng>-<seq> idempotent + UNIQUE chống trùng.
- Ghi document_access_log best-effort (D11, BR-DOC-015).
"""
import logging
import re
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found
from app.models.department import Department
from app.models.document import Document, DocumentAccessLog, DocumentType, DocumentVersion

logger = logging.getLogger("lims.document")

# ---- State machine whitelist version (FR-DOC-013, BR-DOC-007, §7.3) ----
# (from_status, to_status) hợp lệ. Ngoài tập này → INVALID_STATE_TRANSITION (422).
# approved→obsolete là TỰ ĐỘNG khi approve bản mới (không thao tác thủ công).
VERSION_STATE_WHITELIST: set[tuple[str, str]] = {
    ("draft", "review"),
    ("review", "approved"),
    ("review", "draft"),
    ("approved", "obsolete"),
}


# ===== Error factories (đồng bộ danh mục error code §3 contract) =====
def forbidden(message: str = "Bạn không có quyền thực hiện thao tác này") -> AppException:
    return AppException("FORBIDDEN", message, 403)


def invalid_state(message: str = "Chuyển trạng thái không hợp lệ") -> AppException:
    return AppException("INVALID_STATE_TRANSITION", message, 422)


def restricted_access(
    message: str = "Tài liệu hạn chế — bạn không thuộc phòng sở hữu",
) -> AppException:
    return AppException("RESTRICTED_ACCESS", message, 403)


def document_not_found() -> AppException:
    return AppException("DOCUMENT_NOT_FOUND", "Không tìm thấy tài liệu", 404)


def version_not_found() -> AppException:
    return AppException("VERSION_NOT_FOUND", "Không tìm thấy phiên bản tài liệu", 404)


# ===== RBAC =====
def deny_accountant_write(user: CurrentUser) -> None:
    """Cấm Kế toán mọi endpoint GHI M3 (BR-DOC-005). Gọi đầu mọi endpoint ghi."""
    if user.role == "accountant":
        raise forbidden("Kế toán không được phép thao tác ghi trên tài liệu")


def is_privileged(user: CurrentUser) -> bool:
    """Admin / Ban lãnh đạo = toàn hệ thống (bỏ qua scope phòng + mức bảo mật)."""
    return user.role in ("admin", "leader")


def can_approve(user: CurrentUser, doc_dept_id: uuid.UUID) -> bool:
    """Quyền duyệt/từ chối/ban hành (BR-DOC-010):
    Admin / Lãnh đạo / trưởng nhóm CỦA PHÒNG SỞ HỮU tài liệu."""
    if is_privileged(user):
        return True
    return bool(
        user.is_dept_lead
        and user.department_id is not None
        and user.department_id == doc_dept_id
    )


def assert_write_scope(user: CurrentUser, doc_dept_id: uuid.UUID) -> None:
    """Phạm vi ghi theo phòng (BR-DOC-004): staff chỉ ghi trong phòng mình."""
    if is_privileged(user):
        return
    if user.department_id is None or user.department_id != doc_dept_id:
        raise forbidden("Bạn chỉ được thao tác tài liệu trong phạm vi phòng của mình")


def can_view_restricted(user: CurrentUser, doc: Document) -> bool:
    """Mức bảo mật restricted (BR-DOC-006): chỉ phòng sở hữu + admin/leader."""
    if doc.security_level != "restricted":
        return True
    if is_privileged(user):
        return True
    return user.department_id is not None and user.department_id == doc.department_id


def can_view_unpublished_version(
    user: CurrentUser, doc: Document, version: DocumentVersion
) -> bool:
    """Hiển thị version draft/review (BR-DOC-011): chỉ người soạn + trưởng nhóm phòng
    đó + admin/leader. approved/obsolete cho mọi người có quyền xem tài liệu."""
    if version.status in ("approved", "obsolete"):
        return True
    if is_privileged(user):
        return True
    if version.created_by == user.id:
        return True
    return can_approve(user, doc.department_id)


# ===== Helpers tra cứu (response shape contract) =====
def user_name(db: Session, user_id: Optional[uuid.UUID]) -> Optional[str]:
    if user_id is None:
        return None
    from app.models.user import User

    u = db.get(User, user_id)
    return u.full_name if u else None


def dept_name(db: Session, dept_id: Optional[uuid.UUID]) -> Optional[str]:
    if dept_id is None:
        return None
    d = db.get(Department, dept_id)
    return d.name if d else None


def get_document_or_404(
    db: Session, document_id: uuid.UUID, *, lock: bool = False
) -> Document:
    stmt = select(Document).where(
        Document.id == document_id, Document.deleted_at.is_(None)
    )
    if lock:
        stmt = stmt.with_for_update()
    doc = db.execute(stmt).scalar_one_or_none()
    if doc is None:
        raise document_not_found()
    return doc


def get_version_or_404(
    db: Session, document_id: uuid.UUID, version_id: uuid.UUID, *, lock: bool = False
) -> DocumentVersion:
    stmt = select(DocumentVersion).where(
        DocumentVersion.id == version_id,
        DocumentVersion.document_id == document_id,
        DocumentVersion.deleted_at.is_(None),
    )
    if lock:
        stmt = stmt.with_for_update()
    v = db.execute(stmt).scalar_one_or_none()
    if v is None:
        raise version_not_found()
    return v


def get_active_type_or_422(db: Session, type_code: str) -> DocumentType:
    dt = db.get(DocumentType, type_code)
    if dt is None or not dt.is_active:
        raise AppException(
            "INVALID_DOC_TYPE", "Loại tài liệu không hợp lệ hoặc đã ngừng dùng", 422
        )
    return dt


# ===== Sinh document_code <prefix>-<mã phòng>-<seq> =====
def _short_dept_code(dept: Department) -> str:
    """Lấy phần định danh ngắn của mã phòng (vd LAB-HOA → HOA)."""
    parts = [p for p in re.split(r"[-_\s]+", dept.code.upper()) if p]
    return parts[-1] if parts else dept.code.upper()


def next_document_code(db: Session, *, type_code: str, dept: Department) -> str:
    """Sinh <prefix loại>-<mã phòng>-<NNN>. UNIQUE uq_doc_code là lưới chống trùng;
    caller retry khi IntegrityError (FR-DOC-003 A1)."""
    dt = db.get(DocumentType, type_code)
    prefix = dt.prefix if dt else type_code.upper()
    dept_part = _short_dept_code(dept)
    like = f"{prefix}-{dept_part}-%"
    count = db.execute(
        select(func.count()).select_from(Document).where(Document.code.like(like))
    ).scalar_one()
    seq = count + 1
    return f"{prefix}-{dept_part}-{seq:03d}"


# ===== State transition trung tâm (FR-DOC-013, §7.3) =====
def change_version_status(
    db: Session,
    version: DocumentVersion,
    to_status: str,
    *,
    trigger: str,
    user_id: Optional[uuid.UUID],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> None:
    """Đổi trạng thái version theo whitelist + audit STATE_CHANGE. Caller giữ lock + commit."""
    from_status = version.status
    if from_status == to_status:
        return
    if (from_status, to_status) not in VERSION_STATE_WHITELIST:
        raise invalid_state(
            f"Không thể chuyển phiên bản từ '{from_status}' sang '{to_status}'"
        )
    version.status = to_status
    from app.services import audit_service

    audit_service.log_action(
        db,
        action="DOCUMENT_VERSION_STATE_CHANGE",
        resource="document_version",
        user_id=user_id,
        resource_id=version.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={
            "document_id": str(version.document_id),
            "from": from_status,
            "to": to_status,
            "trigger": trigger,
        },
    )


# ===== Access log best-effort (D11, BR-DOC-015) =====
def log_access(
    db: Session,
    *,
    document_id: uuid.UUID,
    version_id: Optional[uuid.UUID],
    user_id: uuid.UUID,
    action: str,
) -> None:
    """Ghi document_access_log best-effort. Lỗi ghi KHÔNG rollback nghiệp vụ (WARN).
    Caller chịu trách nhiệm commit (nằm trong transaction nghiệp vụ chung)."""
    try:
        db.add(
            DocumentAccessLog(
                document_id=document_id,
                version_id=version_id,
                user_id=user_id,
                action=action,
            )
        )
        db.flush()
    except Exception as exc:  # noqa: BLE001 — best-effort, không chặn nghiệp vụ
        logger.warning(
            "document_access_log write failed",
            extra={"documentId": str(document_id), "action": action, "error": str(exc)},
        )
