"""Quản lý TỆP của kho biểu mẫu VILAS — tải lên / thay thế / gỡ / lịch sử.

Mô hình: mỗi biểu mẫu (template) và mỗi minh chứng (submission) có ĐÚNG 1 tệp
hiện hành. Thay tệp KHÔNG xóa bản cũ khỏi MinIO mà chỉ soft-delete bản ghi
attachment (`deleted_at`) → giữ nguyên vết cho đánh giá VILAS/ISO 17025 (§8.4).

Vì sao không dùng `POST /attachments` generic: endpoint đó chỉ yêu cầu đăng nhập
(không kiểm quyền theo owner_type), nên bất kỳ ai biết id biểu mẫu cũng ghi đè
được kho VILAS. Các endpoint ở đây đi kèm RBAC `form:manage` / `form:submit`
cùng ràng buộc phòng ban và trạng thái duyệt.
"""
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found
from app.models.attachment import Attachment
from app.models.audit_log import AuditLog
from app.models.department import Department
from app.models.form import FormSubmission, FormTemplate
from app.models.user import User
from app.services import (
    attachment_common,
    audit_service,
    form_service,
    notification_service,
    storage_service,
)

OWNER_TEMPLATE = "form_template"
OWNER_SUBMISSION = "form_submission"

# Action audit theo owner — dùng cả khi ghi lẫn khi dựng lịch sử.
_ACTIONS = {
    OWNER_TEMPLATE: {
        "upload": "FORM_TEMPLATE_FILE_UPLOAD",
        "replace": "FORM_TEMPLATE_FILE_REPLACE",
        "delete": "FORM_TEMPLATE_FILE_DELETE",
    },
    OWNER_SUBMISSION: {
        "upload": "FORM_SUBMISSION_FILE_UPLOAD",
        "replace": "FORM_SUBMISSION_FILE_REPLACE",
        "delete": "FORM_SUBMISSION_FILE_DELETE",
    },
}

_ACTION_LABELS = {
    "FORM_TEMPLATE_FILE_UPLOAD": "Tải lên",
    "FORM_TEMPLATE_FILE_REPLACE": "Thay tệp",
    "FORM_TEMPLATE_FILE_DELETE": "Gỡ tệp",
    "FORM_SUBMISSION_FILE_UPLOAD": "Tải lên",
    "FORM_SUBMISSION_FILE_REPLACE": "Thay tệp",
    "FORM_SUBMISSION_FILE_DELETE": "Gỡ tệp",
}


# ===== Truy cập & ràng buộc nghiệp vụ =====
def _get_template_or_404(db: Session, template_id: uuid.UUID) -> FormTemplate:
    tpl = db.get(FormTemplate, template_id)
    if tpl is None:
        raise not_found("Không tìm thấy biểu mẫu")
    return tpl


def _get_submission_or_404(db: Session, submission_id: uuid.UUID) -> FormSubmission:
    sub = db.get(FormSubmission, submission_id)
    if sub is None:
        raise not_found("Không tìm thấy minh chứng")
    return sub


def _check_submission_scope(user: CurrentUser, sub: FormSubmission) -> None:
    """Phòng lab chỉ thao tác trên minh chứng của phòng mình; admin/QLCL toàn quyền."""
    if form_service._is_privileged(user):
        return
    if user.department_id is None or user.department_id != sub.department_id:
        raise AppException(
            ErrorCode.FORBIDDEN, "Bạn chỉ được sửa minh chứng của phòng mình", 403
        )


def _check_submission_writable(sub: FormSubmission) -> None:
    """Đã duyệt thì khóa tệp — sửa tệp sau khi duyệt làm mất giá trị của chữ ký duyệt."""
    if sub.status == "approved":
        raise AppException(
            ErrorCode.INVALID_STATE,
            "Minh chứng đã được duyệt — không thể đổi tệp. "
            "Hãy nộp minh chứng mới hoặc đề nghị Phòng QLCL mở lại.",
            422,
        )


def _resolve_owner(
    db: Session, *, user: CurrentUser, owner_type: str, owner_id: uuid.UUID, for_write: bool
):
    """Trả về đối tượng owner sau khi kiểm tra tồn tại + quyền + trạng thái."""
    if owner_type == OWNER_TEMPLATE:
        return _get_template_or_404(db, owner_id)
    sub = _get_submission_or_404(db, owner_id)
    _check_submission_scope(user, sub)
    if for_write:
        _check_submission_writable(sub)
    return sub


# ===== Tệp hiện hành =====
def _current_attachments(
    db: Session, owner_type: str, owner_id: uuid.UUID
) -> list[Attachment]:
    """Mọi tệp còn hiệu lực, mới nhất trước.

    Mô hình mới là 1 tệp hiện hành, nhưng dữ liệu tạo trước đây có thể còn nhiều tệp
    (mỗi lần sửa biểu mẫu lại đính thêm một bản). Trả về danh sách để lần thay tệp
    đầu tiên dọn hết bản cũ, đưa biểu mẫu về đúng mô hình.
    """
    return list(
        db.execute(
            select(Attachment)
            .where(
                Attachment.owner_type == owner_type,
                Attachment.owner_id == owner_id,
                Attachment.deleted_at.is_(None),
            )
            .order_by(Attachment.uploaded_at.desc())
        ).scalars()
    )


def _current_attachment(
    db: Session, owner_type: str, owner_id: uuid.UUID
) -> Optional[Attachment]:
    rows = _current_attachments(db, owner_type, owner_id)
    return rows[0] if rows else None


def _serialize_attachment(a: Attachment) -> dict:
    return {
        "id": a.id,
        "file_name": a.file_name,
        "mime": a.mime,
        "size": a.size,
        "uploaded_at": a.uploaded_at,
    }


def _serialize_owner(db: Session, owner_type: str, owner) -> dict:
    if owner_type == OWNER_TEMPLATE:
        return form_service._serialize_template(db, owner)
    return form_service._serialize_submission(db, owner)


def replace_file(
    db: Session,
    *,
    user: CurrentUser,
    owner_type: str,
    owner_id: uuid.UUID,
    file_name: str,
    content: bytes,
    mime: Optional[str],
    reason: Optional[str] = None,
    expected_attachment_id: Optional[uuid.UUID] = None,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    """Tải lên tệp mới; nếu đã có tệp hiện hành thì bản cũ chuyển thành lịch sử.

    Object cũ trên MinIO KHÔNG bị xóa (còn tải lại được từ màn hình lịch sử).
    Object mới ghi bằng key mới nên nếu transaction DB hỏng, bản cũ vẫn nguyên vẹn.
    """
    owner = _resolve_owner(
        db, user=user, owner_type=owner_type, owner_id=owner_id, for_write=True
    )

    attachment_common.check_mime(mime, allowed=attachment_common.GENERIC_ALLOWED_MIME)
    attachment_common.check_size(content)
    if not content:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Tệp rỗng", 400)

    olds = _current_attachments(db, owner_type, owner_id)
    old = olds[0] if olds else None

    # Chống ghi đè chéo: FE gửi kèm id tệp đang thấy; lệch nghĩa là người khác vừa thay.
    if expected_attachment_id is not None:
        current_id = old.id if old else None
        if current_id != expected_attachment_id:
            raise AppException(
                ErrorCode.CONFLICT,
                "Tệp đã được người khác thay đổi. Hãy tải lại trang rồi thử lại.",
                409,
            )

    file_key = storage_service.build_object_key(owner_type, owner_id, file_name)
    storage_service.put_object(file_key, content, content_type=mime)

    try:
        for prev in olds:
            # now() phía SQL để nhất quán múi giờ với các cột server_default.
            prev.deleted_at = func.now()

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

        if owner_type == OWNER_TEMPLATE:
            owner.updated_by = user.id

        # Minh chứng bị từ chối mà nộp lại tệp → quay về hàng chờ duyệt.
        resubmitted = False
        if owner_type == OWNER_SUBMISSION and owner.status == "rejected":
            owner.status = "pending"
            owner.reviewed_by = None
            owner.reviewed_at = None
            owner.reject_reason = None
            resubmitted = True

        action = _ACTIONS[owner_type]["replace" if old is not None else "upload"]
        audit_service.log_action(
            db,
            action=action,
            resource=owner_type,
            user_id=user.id,
            resource_id=owner_id,
            correlation_id=correlation_id,
            ip=ip,
            detail={
                "attachment_id": str(att.id),
                "file_name": file_name,
                "size": len(content),
                "mime": mime,
                "old_attachment_id": str(old.id) if old else None,
                "old_file_name": old.file_name if old else None,
                # Dữ liệu cũ có thể có nhiều tệp cùng hiệu lực — ghi hết id đã thay.
                "replaced_attachment_ids": [str(p.id) for p in olds],
                "reason": reason,
                "resubmitted": resubmitted,
            },
        )

        if resubmitted:
            _notify_qms_resubmitted(db, owner)

        db.commit()
    except Exception:
        db.rollback()
        # Object vừa ghi chưa được tham chiếu bởi bản ghi nào → dọn để không rác kho.
        storage_service.remove_object(file_key)
        raise

    db.refresh(owner)
    return _serialize_owner(db, owner_type, owner)


def _notify_qms_resubmitted(db: Session, sub: FormSubmission) -> None:
    tpl = db.get(FormTemplate, sub.template_id)
    qms_users = db.execute(
        select(User.id).where(User.role == "qms", User.status == "active")
    ).scalars().all()
    for qid in qms_users:
        notification_service.create_notification(
            db,
            user_id=qid,
            type="FORM_SUBMITTED",
            title="Minh chứng đã nộp lại",
            body=f"{tpl.code if tpl else ''} — {tpl.title if tpl else ''} (đã thay tệp sau khi bị từ chối)",
            ref_type="form_submission",
            ref_id=sub.id,
        )


def delete_file(
    db: Session,
    *,
    user: CurrentUser,
    owner_type: str,
    owner_id: uuid.UUID,
    reason: Optional[str] = None,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    """Gỡ tệp hiện hành (soft delete — vẫn xem/tải được ở màn hình lịch sử)."""
    owner = _resolve_owner(
        db, user=user, owner_type=owner_type, owner_id=owner_id, for_write=True
    )
    # Minh chứng bắt buộc có tệp — gỡ tệp cuối cùng sẽ để lại minh chứng rỗng vô nghĩa.
    if owner_type == OWNER_SUBMISSION:
        raise AppException(
            ErrorCode.INVALID_STATE,
            "Minh chứng phải có tệp — hãy dùng chức năng Thay tệp thay vì gỡ.",
            422,
        )

    atts = _current_attachments(db, owner_type, owner_id)
    if not atts:
        raise not_found("Chưa có tệp nào để gỡ")
    att = atts[0]

    for a in atts:
        a.deleted_at = func.now()
    if owner_type == OWNER_TEMPLATE:
        owner.updated_by = user.id
    audit_service.log_action(
        db,
        action=_ACTIONS[owner_type]["delete"],
        resource=owner_type,
        user_id=user.id,
        resource_id=owner_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={
            "attachment_id": str(att.id),
            "file_name": att.file_name,
            "removed_attachment_ids": [str(a.id) for a in atts],
            "reason": reason,
        },
    )
    db.commit()
    db.refresh(owner)
    return _serialize_owner(db, owner_type, owner)


# ===== Lịch sử tải lên =====
def file_history(
    db: Session, *, user: CurrentUser, owner_type: str, owner_id: uuid.UUID
) -> list[dict]:
    """Lịch sử tệp: mọi bản đã tải lên (kể cả bản đã bị thay), kèm ai làm & vì sao.

    Nguồn dữ liệu là bảng `attachments` (đủ tên tệp/dung lượng/người tải), làm giàu
    thêm lý do + loại thao tác lấy từ `audit_logs` khớp theo attachment_id.
    """
    _resolve_owner(
        db, user=user, owner_type=owner_type, owner_id=owner_id, for_write=False
    )

    rows = db.execute(
        select(Attachment)
        .where(Attachment.owner_type == owner_type, Attachment.owner_id == owner_id)
        .order_by(Attachment.uploaded_at.desc())
    ).scalars().all()
    if not rows:
        return []

    uploader_ids = {a.uploaded_by for a in rows}
    names = {
        u.id: u.full_name
        for u in db.execute(select(User).where(User.id.in_(uploader_ids))).scalars()
    }

    # Audit của owner này → map attachment_id -> {action, reason}; thêm cả bản ghi gỡ tệp.
    audit_rows = db.execute(
        select(AuditLog)
        .where(
            AuditLog.resource == owner_type,
            AuditLog.resource_id == owner_id,
            AuditLog.action.in_(tuple(_ACTIONS[owner_type].values())),
        )
        .order_by(AuditLog.at.asc())
    ).scalars().all()
    meta_by_att: dict[str, dict] = {}
    removed_by_att: dict[str, dict] = {}
    delete_action = _ACTIONS[owner_type]["delete"]
    for log in audit_rows:
        detail = log.detail or {}
        att_id = detail.get("attachment_id")
        reason = detail.get("reason")
        if att_id and log.action != delete_action:
            meta_by_att[att_id] = {"action": log.action, "reason": reason}
        # Bản bị thay/gỡ: gắn lý do của chính thao tác đó để trả lời "vì sao không còn dùng".
        gone_ids = list(detail.get("replaced_attachment_ids") or []) + list(
            detail.get("removed_attachment_ids") or []
        )
        if not gone_ids and detail.get("old_attachment_id"):
            gone_ids = [detail["old_attachment_id"]]
        if not gone_ids and log.action == delete_action and att_id:
            gone_ids = [att_id]
        for gid in gone_ids:
            removed_by_att[gid] = {"action": log.action, "reason": reason}

    items: list[dict] = []
    for a in rows:
        att_id = str(a.id)
        meta = meta_by_att.get(att_id, {})
        removed = removed_by_att.get(att_id, {})
        items.append(
            {
                "id": a.id,
                "file_name": a.file_name,
                "mime": a.mime,
                "size": a.size,
                "uploaded_at": a.uploaded_at,
                "uploaded_by_name": names.get(a.uploaded_by),
                "is_current": a.deleted_at is None,
                "replaced_at": a.deleted_at,
                "action": meta.get("action") or _ACTIONS[owner_type]["upload"],
                "action_label": _ACTION_LABELS.get(
                    meta.get("action") or _ACTIONS[owner_type]["upload"], ""
                ),
                "reason": meta.get("reason"),
                "removed_reason": removed.get("reason") if a.deleted_at else None,
            }
        )
    return items


def history_download_url(
    db: Session,
    *,
    user: CurrentUser,
    owner_type: str,
    owner_id: uuid.UUID,
    attachment_id: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    """URL tải cho MỘT bản bất kỳ trong lịch sử (kể cả bản đã bị thay).

    `GET /attachments/{id}` chỉ phục vụ bản chưa soft-delete nên không dùng được
    cho bản cũ; ở đây kiểm quyền theo owner rồi mới ký URL.
    """
    _resolve_owner(
        db, user=user, owner_type=owner_type, owner_id=owner_id, for_write=False
    )
    att = db.execute(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.owner_type == owner_type,
            Attachment.owner_id == owner_id,
        )
    ).scalar_one_or_none()
    if att is None:
        raise not_found("Không tìm thấy tệp")

    url = storage_service.presigned_get_url(att.file_key, file_name=att.file_name)
    audit_service.log_action(
        db,
        action="ATTACHMENT_DOWNLOAD",
        resource=owner_type,
        user_id=user.id,
        resource_id=owner_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={
            "attachment_id": str(att.id),
            "file_name": att.file_name,
            "historical": att.deleted_at is not None,
        },
    )
    db.commit()
    return {"download_url": url, "file_name": att.file_name}


# ===== Lịch sử TỔNG HỢP toàn kho biểu mẫu (tab "Lịch sử") =====
def history_feed(
    db: Session, *, user: CurrentUser, q: Optional[str], owner_type: Optional[str],
    page: int, limit: int,
) -> tuple[list[dict], int]:
    """Dòng thời gian mọi thao tác tệp trong kho biểu mẫu (biểu mẫu gốc + minh chứng đã nộp).

    Nguồn: audit_logs (đã ghi đủ ai/khi nào/lý do) — gộp chung, mới nhất trước.
    """
    from app.models.form import FormSubmission, FormTemplate

    all_actions = tuple(a for m in _ACTIONS.values() for a in m.values())
    conds = [AuditLog.action.in_(all_actions)]
    if owner_type in (OWNER_TEMPLATE, OWNER_SUBMISSION):
        conds.append(AuditLog.resource == owner_type)

    base = select(AuditLog).where(*conds)
    total = db.execute(
        select(func.count()).select_from(AuditLog).where(*conds)
    ).scalar_one()
    rows = db.execute(
        base.order_by(AuditLog.at.desc()).offset((page - 1) * limit).limit(limit)
    ).scalars().all()

    # Làm giàu: tên người, mã/tên biểu mẫu
    user_ids = {r.user_id for r in rows if r.user_id}
    names = {
        u.id: u.full_name
        for u in db.execute(select(User).where(User.id.in_(user_ids))).scalars()
    } if user_ids else {}

    out: list[dict] = []
    tpl_cache: dict = {}
    for r in rows:
        detail = r.detail or {}
        code = title = None
        dept_name = None
        if r.resource == OWNER_TEMPLATE:
            t = tpl_cache.get(r.resource_id) or db.get(FormTemplate, r.resource_id)
            tpl_cache[r.resource_id] = t
            if t is not None:
                code, title = t.code, t.title
        else:
            sub = db.get(FormSubmission, r.resource_id)
            if sub is not None:
                t = tpl_cache.get(sub.template_id) or db.get(FormTemplate, sub.template_id)
                tpl_cache[sub.template_id] = t
                if t is not None:
                    code, title = t.code, t.title
                dept = db.get(Department, sub.department_id) if sub.department_id else None
                dept_name = dept.name if dept else None

        item = {
            "id": r.id,
            "at": r.at,
            "owner_type": r.resource,
            "owner_id": r.resource_id,
            "owner_label": "Biểu mẫu gốc" if r.resource == OWNER_TEMPLATE else "Minh chứng đã nộp",
            "form_code": code,
            "form_title": title,
            "department_name": dept_name,
            "action": r.action,
            "action_label": _ACTION_LABELS.get(r.action, r.action),
            "attachment_id": detail.get("attachment_id"),
            "file_name": detail.get("file_name") or detail.get("filename"),
            "reason": detail.get("reason"),
            "user_name": names.get(r.user_id),
        }
        if q:
            hay = " ".join(
                str(v or "") for v in (code, title, item["file_name"], item["user_name"], dept_name)
            ).lower()
            if q.strip().lower() not in hay:
                continue
        out.append(item)
    return out, total
