"""M3 document service — CRUD tài liệu + tìm/lọc + chi tiết + lịch sử + thống kê R15.

Tạo tài liệu kèm version đầu (upload file) trong 1 transaction (lỗi upload → rollback).
RBAC scope phòng + 2 mức bảo mật (BR-DOC-004/006). Mã document_code sinh server-side
(BR-DOC-014, không lộ tuần tự). Soft-delete chỉ khi chưa có version approved (§8.4).
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException, validation_error
from app.models.audit_log import AuditLog
from app.models.document import Document, DocumentAccessLog, DocumentType, DocumentVersion
from app.services import audit_service, document_common as dc
from app.services import document_version_service as dvs

_VALID_SECURITY = {"internal", "restricted"}


# ===== Lookups (#1, #2) =====
def list_document_types(db: Session) -> list[dict]:
    rows = db.execute(
        select(DocumentType)
        .where(DocumentType.is_active.is_(True))
        .order_by(DocumentType.sort_order.asc())
    ).scalars().all()
    return [
        {"code": t.code, "label": t.label, "prefix": t.prefix} for t in rows
    ]


def list_confidentiality_levels() -> list[dict]:
    return [
        {
            "code": "internal",
            "label": "Nội bộ",
            "description": "Mọi nhân sự đã đăng nhập đọc/tải bản approved",
            "is_default": True,
        },
        {
            "code": "restricted",
            "label": "Hạn chế",
            "description": "Chỉ phòng sở hữu + Ban lãnh đạo + Admin",
            "is_default": False,
        },
    ]


# ===== Serialize =====
def _current_version_brief(db: Session, doc: Document) -> Optional[dict]:
    if doc.current_version_id is None:
        return None
    v = db.get(DocumentVersion, doc.current_version_id)
    if v is None:
        return None
    return {
        "id": v.id,
        "version_no": v.version_no,
        "status": v.status,
        "approved_at": v.approved_at,
        "approved_by_name": dc.user_name(db, v.approved_by),
    }


def _doc_summary(db: Session, doc: Document) -> dict:
    dt = db.get(DocumentType, doc.type)
    return {
        "id": doc.id,
        "document_code": doc.code,
        "title": doc.title,
        "type": doc.type,
        "type_label": dt.label if dt else None,
        "department_id": doc.department_id,
        "department_name": dc.dept_name(db, doc.department_id),
        "security_level": doc.security_level,
        "status": doc.status,
        "current_version": _current_version_brief(db, doc),
        "created_at": doc.created_at,
    }


# ===== List / search (#3) =====
def list_documents(
    db: Session,
    *,
    user: CurrentUser,
    q: Optional[str],
    type_filter: Optional[str],
    department_id: Optional[uuid.UUID],
    security_level: Optional[str],
    status_filter: Optional[str],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = [Document.deleted_at.is_(None), Document.status != "deleted"]
    if q:
        like = f"%{q}%"
        conditions.append(or_(Document.code.ilike(like), Document.title.ilike(like)))
    if type_filter:
        conditions.append(Document.type == type_filter)
    if department_id is not None:
        conditions.append(Document.department_id == department_id)
    if security_level:
        if security_level not in _VALID_SECURITY:
            raise validation_error("Mức bảo mật không hợp lệ")
        conditions.append(Document.security_level == security_level)
    if status_filter == "has_current":
        conditions.append(Document.current_version_id.isnot(None))
    elif status_filter == "no_current":
        conditions.append(Document.current_version_id.is_(None))

    # 2 mức bảo mật (BR-DOC-006): restricted ngoài phòng KHÔNG xuất hiện
    if not dc.is_privileged(user):
        conditions.append(
            or_(
                Document.security_level == "internal",
                and_(
                    Document.security_level == "restricted",
                    Document.department_id == user.department_id,
                ),
            )
        )
        # tài liệu chưa có current chỉ hiện cho người soạn/duyệt phòng đó (BR-DOC-011)
        # → ẩn no-current ngoài phòng cho staff/accountant
        conditions.append(
            or_(
                Document.current_version_id.isnot(None),
                Document.department_id == user.department_id,
            )
        )

    base = select(Document).where(*conditions)
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()
    rows = db.execute(
        base.order_by(Document.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return [_doc_summary(db, d) for d in rows], total


# ===== Create document + first version (#4) =====
def create_document(
    db: Session,
    *,
    user: CurrentUser,
    title: str,
    type_code: str,
    department_id: Optional[uuid.UUID],
    security_level: Optional[str],
    change_note: Optional[str],
    file_name: str,
    content: bytes,
    mime: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    dc.deny_accountant_write(user)
    if not (title and title.strip()):
        raise validation_error("Tiêu đề tài liệu không được rỗng")
    dc.get_active_type_or_422(db, type_code)

    sec = security_level or "internal"
    if sec not in _VALID_SECURITY:
        raise AppException(
            "INVALID_CONFIDENTIALITY", "Mức bảo mật không hợp lệ", 422
        )

    # phòng sở hữu: staff ép = phòng mình
    if dc.is_privileged(user):
        dept_id = department_id or user.department_id
    else:
        dept_id = department_id or user.department_id
        if dept_id != user.department_id:
            raise dc.forbidden("Bạn chỉ được tạo tài liệu cho phòng của mình")
    if dept_id is None:
        raise validation_error("Thiếu phòng ban sở hữu tài liệu")

    from app.models.department import Department

    dept = db.get(Department, dept_id)
    if dept is None:
        raise AppException("DEPARTMENT_NOT_FOUND", "Không tìm thấy phòng ban", 404)

    # validate file sớm (tránh tạo tài liệu rỗng nếu file sai)
    dvs._check_mime(mime)
    dvs._check_size(content)

    # sinh document_code + retry chống race UNIQUE (FR-DOC-003 A1)
    last_err: Optional[Exception] = None
    for _ in range(5):
        code = dc.next_document_code(db, type_code=type_code, dept=dept)
        doc = Document(
            code=code,
            title=title.strip(),
            type=type_code,
            department_id=dept_id,
            security_level=sec,
            status="active",
            created_by=user.id,
        )
        db.add(doc)
        try:
            db.flush()
            break
        except IntegrityError as exc:
            db.rollback()
            last_err = exc
            doc = None  # type: ignore
    if doc is None:
        raise AppException(
            "DUPLICATE_DOCUMENT_CODE",
            "Không sinh được mã tài liệu duy nhất, vui lòng thử lại",
            409,
        )

    version = DocumentVersion(
        document_id=doc.id,
        version_no=1,
        change_note=change_note.strip() if change_note else None,
        status="draft",
        created_by=user.id,
    )
    db.add(version)
    db.flush()

    # upload file v1 — lỗi → toàn transaction rollback (không để tài liệu rỗng)
    dvs._store_file(
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
        action="DOCUMENT_CREATE",
        resource="document",
        user_id=user.id,
        resource_id=doc.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"code": doc.code, "type": type_code, "security_level": sec},
    )
    audit_service.log_action(
        db,
        action="DOCUMENT_VERSION_CREATE",
        resource="document_version",
        user_id=user.id,
        resource_id=version.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"document_id": str(doc.id), "version_no": 1},
    )
    dc.log_access(
        db,
        document_id=doc.id,
        version_id=version.id,
        user_id=user.id,
        action="edit",
    )
    db.commit()
    db.refresh(doc)
    db.refresh(version)

    summary = _doc_summary(db, doc)
    summary.pop("current_version", None)
    summary["current_version_id"] = doc.current_version_id
    summary["created_by"] = doc.created_by
    summary["first_version"] = dvs.serialize_version(db, version)
    return summary


# ===== Detail (#5) =====
def get_document_detail(
    db: Session, *, user: CurrentUser, document_id: uuid.UUID
) -> dict:
    doc = dc.get_document_or_404(db, document_id)
    # restricted ẩn sự tồn tại (BR-DOC-006) → 404
    if not dc.can_view_restricted(user, doc):
        raise dc.document_not_found()
    # tài liệu chưa có current + không phải người soạn/duyệt phòng đó/admin/leader → ẩn
    if doc.current_version_id is None and not (
        dc.is_privileged(user)
        or (user.department_id is not None and user.department_id == doc.department_id)
    ):
        raise dc.document_not_found()

    versions = db.execute(
        select(DocumentVersion)
        .where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.deleted_at.is_(None),
        )
        .order_by(DocumentVersion.version_no.asc())
    ).scalars().all()
    visible = [v for v in versions if dc.can_view_unpublished_version(user, doc, v)]

    dt = db.get(DocumentType, doc.type)
    current = None
    if doc.current_version_id is not None:
        cv = db.get(DocumentVersion, doc.current_version_id)
        if cv is not None:
            current = dvs.serialize_version(db, cv)

    # ghi access_log view (best-effort, không chặn)
    dc.log_access(
        db, document_id=document_id, version_id=None, user_id=user.id, action="view"
    )
    db.commit()

    return {
        "id": doc.id,
        "document_code": doc.code,
        "title": doc.title,
        "type": doc.type,
        "type_label": dt.label if dt else None,
        "department_id": doc.department_id,
        "department_name": dc.dept_name(db, doc.department_id),
        "security_level": doc.security_level,
        "status": doc.status,
        "current_version_id": doc.current_version_id,
        "created_by_name": dc.user_name(db, doc.created_by),
        "created_at": doc.created_at,
        "current_version": current,
        "versions": [dvs.serialize_version(db, v, include_file=False) for v in visible],
    }


# ===== Update metadata (#6) =====
def update_document(
    db: Session,
    *,
    user: CurrentUser,
    document_id: uuid.UUID,
    title: Optional[str],
    type_code: Optional[str],
    security_level: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    dc.deny_accountant_write(user)
    doc = dc.get_document_or_404(db, document_id, lock=True)
    dc.assert_write_scope(user, doc.department_id)

    if title is None and type_code is None and security_level is None:
        raise validation_error("Phải cung cấp ít nhất 1 trường để cập nhật")

    before = {
        "title": doc.title,
        "type": doc.type,
        "security_level": doc.security_level,
    }
    if title is not None:
        if not title.strip():
            raise validation_error("Tiêu đề không được rỗng")
        doc.title = title.strip()
    if type_code is not None:
        dc.get_active_type_or_422(db, type_code)
        doc.type = type_code
    if security_level is not None:
        if security_level not in _VALID_SECURITY:
            raise AppException(
                "INVALID_CONFIDENTIALITY", "Mức bảo mật không hợp lệ", 422
            )
        doc.security_level = security_level
    doc.updated_by = user.id
    doc.updated_at = func.now()
    db.flush()

    audit_service.log_action(
        db,
        action="DOCUMENT_UPDATE",
        resource="document",
        user_id=user.id,
        resource_id=doc.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={
            "before": before,
            "after": {
                "title": doc.title,
                "type": doc.type,
                "security_level": doc.security_level,
            },
        },
    )
    db.commit()
    db.refresh(doc)
    return _doc_summary(db, doc)


# ===== Soft delete (#7) =====
def delete_document(
    db: Session,
    *,
    user: CurrentUser,
    document_id: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    dc.deny_accountant_write(user)
    doc = dc.get_document_or_404(db, document_id, lock=True)
    dc.assert_write_scope(user, doc.department_id)

    has_published = db.execute(
        select(func.count())
        .select_from(DocumentVersion)
        .where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.status.in_(("approved", "obsolete")),
        )
    ).scalar_one()
    if has_published > 0:
        raise AppException(
            "DOCUMENT_HAS_APPROVED_VERSION",
            "Tài liệu đã có phiên bản ban hành — không được xóa (giữ hồ sơ §8.4)",
            422,
        )

    doc.status = "deleted"
    doc.deleted_at = func.now()
    doc.updated_by = user.id
    db.flush()
    audit_service.log_action(
        db,
        action="DOCUMENT_DELETE",
        resource="document",
        user_id=user.id,
        resource_id=doc.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"code": doc.code},
    )
    db.commit()
    return {"id": doc.id, "status": "deleted"}


# ===== History (#16) =====
_HISTORY_ACTIONS = (
    "DOCUMENT_VERSION_CREATE",
    "DOCUMENT_VERSION_SUBMIT",
    "DOCUMENT_VERSION_APPROVE",
    "DOCUMENT_VERSION_REJECT",
    "DOCUMENT_VERSION_OBSOLETE",
)


def get_history(db: Session, *, user: CurrentUser, document_id: uuid.UUID) -> dict:
    doc = dc.get_document_or_404(db, document_id)
    if not dc.can_view_restricted(user, doc):
        raise dc.restricted_access()

    versions = db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_no.asc())
    ).scalars().all()
    visible = {
        v.id: v for v in versions if dc.can_view_unpublished_version(user, doc, v)
    }

    # gom audit theo version_id (resource_id)
    audits = db.execute(
        select(AuditLog)
        .where(
            AuditLog.resource == "document_version",
            AuditLog.action.in_(_HISTORY_ACTIONS),
            AuditLog.resource_id.in_(list(visible.keys())) if visible else False,
        )
        .order_by(AuditLog.at.asc())
    ).scalars().all() if visible else []

    by_version: dict[uuid.UUID, list] = {vid: [] for vid in visible}
    for a in audits:
        if a.resource_id in by_version:
            detail = None
            if a.detail:
                if "reason" in a.detail:
                    detail = f"reason: {a.detail['reason']}"
                elif "replaced_by" in a.detail:
                    detail = "thay bởi phiên bản mới"
            by_version[a.resource_id].append(
                {
                    "action": a.action,
                    "by_name": dc.user_name(db, a.user_id),
                    "at": a.at,
                    "detail": detail,
                }
            )

    timeline = []
    for v in versions:
        if v.id not in visible:
            continue
        events = by_version.get(v.id, [])
        timeline.append({"version_no": v.version_no, "events": events})

    return {
        "document_id": doc.id,
        "document_code": doc.code,
        "timeline": timeline,
    }


# ===== Access stats — single document (#18) =====
def _resolve_range(from_: Optional[date], to_: Optional[date]) -> tuple[datetime, datetime]:
    today = datetime.now(timezone.utc).date()
    f = from_ or (today - timedelta(days=30))
    t = to_ or today
    if f > t:
        raise validation_error("Khoảng thời gian không hợp lệ (from > to)")
    start = datetime(f.year, f.month, f.day, tzinfo=timezone.utc)
    end = datetime(t.year, t.month, t.day, tzinfo=timezone.utc) + timedelta(days=1)
    return start, end


def _assert_stats_scope(user: CurrentUser, doc: Document) -> None:
    if user.role == "accountant":
        raise dc.forbidden("Kế toán không xem được thống kê truy cập")
    if dc.is_privileged(user):
        return
    if user.department_id != doc.department_id:
        raise dc.forbidden("Bạn chỉ xem thống kê tài liệu phòng mình")


def document_access_stats(
    db: Session,
    *,
    user: CurrentUser,
    document_id: uuid.UUID,
    from_: Optional[date],
    to_: Optional[date],
    group_by: Optional[str],
) -> dict:
    doc = dc.get_document_or_404(db, document_id)
    _assert_stats_scope(user, doc)
    start, end = _resolve_range(from_, to_)

    totals_row = db.execute(
        select(
            func.count().filter(DocumentAccessLog.action == "view"),
            func.count().filter(DocumentAccessLog.action == "download"),
            func.count().filter(DocumentAccessLog.action == "edit"),
        ).where(
            DocumentAccessLog.document_id == document_id,
            DocumentAccessLog.at >= start,
            DocumentAccessLog.at < end,
        )
    ).one()
    totals = {
        "view": totals_row[0] or 0,
        "download": totals_row[1] or 0,
        "edit": totals_row[2] or 0,
    }

    series = None
    if group_by in ("day", "week", "month"):
        trunc = func.date_trunc(group_by, DocumentAccessLog.at)
        rows = db.execute(
            select(
                trunc.label("period"),
                func.count().filter(DocumentAccessLog.action == "view"),
                func.count().filter(DocumentAccessLog.action == "download"),
                func.count().filter(DocumentAccessLog.action == "edit"),
            )
            .where(
                DocumentAccessLog.document_id == document_id,
                DocumentAccessLog.at >= start,
                DocumentAccessLog.at < end,
            )
            .group_by(trunc)
            .order_by(trunc.asc())
        ).all()
        series = [
            {
                "period": r[0].date().isoformat() if r[0] else None,
                "view": r[1] or 0,
                "download": r[2] or 0,
                "edit": r[3] or 0,
            }
            for r in rows
        ]

    result = {
        "document_id": doc.id,
        "document_code": doc.code,
        "range": {
            "from": (from_ or (datetime.now(timezone.utc).date() - timedelta(days=30))).isoformat(),
            "to": (to_ or datetime.now(timezone.utc).date()).isoformat(),
        },
        "totals": totals,
    }
    if series is not None:
        result["series"] = series
    return result


# ===== Access stats — aggregate + top N (#19) =====
def aggregate_access_stats(
    db: Session,
    *,
    user: CurrentUser,
    from_: Optional[date],
    to_: Optional[date],
    department_id: Optional[uuid.UUID],
    action: Optional[str],
    top: int,
    sort_by: str,
) -> dict:
    if user.role == "accountant":
        raise dc.forbidden("Kế toán không xem được thống kê truy cập")
    if top < 1 or top > 100:
        raise validation_error("Tham số top phải trong khoảng 1..100")
    start, end = _resolve_range(from_, to_)

    # scope phòng (staff ép = phòng mình)
    dept_filter = department_id
    if not dc.is_privileged(user):
        if department_id is not None and department_id != user.department_id:
            raise dc.forbidden("Bạn chỉ xem thống kê phòng mình")
        dept_filter = user.department_id

    conditions = [
        DocumentAccessLog.at >= start,
        DocumentAccessLog.at < end,
    ]
    if action in ("view", "download", "edit"):
        conditions.append(DocumentAccessLog.action == action)

    join = (
        select(
            Document.id.label("document_id"),
            Document.code.label("code"),
            Document.title.label("title"),
            Document.department_id.label("department_id"),
            func.count().filter(DocumentAccessLog.action == "view").label("view"),
            func.count().filter(DocumentAccessLog.action == "download").label("download"),
            func.count().filter(DocumentAccessLog.action == "edit").label("edit"),
        )
        .join(DocumentAccessLog, DocumentAccessLog.document_id == Document.id)
        .where(*conditions)
    )
    if dept_filter is not None:
        join = join.where(Document.department_id == dept_filter)
    join = join.group_by(Document.id, Document.code, Document.title, Document.department_id)

    rows = db.execute(join).all()
    total_view = sum(r.view for r in rows)
    total_download = sum(r.download for r in rows)
    total_edit = sum(r.edit for r in rows)

    def _key(r):
        if sort_by == "view":
            return r.view
        if sort_by == "edit":
            return r.edit
        if sort_by == "total":
            return r.view + r.download + r.edit
        return r.download

    top_rows = sorted(rows, key=_key, reverse=True)[:top]
    top_documents = [
        {
            "document_id": r.document_id,
            "document_code": r.code,
            "title": r.title,
            "department_name": dc.dept_name(db, r.department_id),
            "view": r.view,
            "download": r.download,
            "edit": r.edit,
            "total": r.view + r.download + r.edit,
        }
        for r in top_rows
    ]

    return {
        "range": {
            "from": (from_ or (datetime.now(timezone.utc).date() - timedelta(days=30))).isoformat(),
            "to": (to_ or datetime.now(timezone.utc).date()).isoformat(),
        },
        "summary": {
            "total_view": total_view,
            "total_download": total_download,
            "total_edit": total_edit,
            "document_count": len(rows),
        },
        "top_documents": top_documents,
    }


# ===== Access stats — export xlsx (#20) =====
def export_access_stats_xlsx(
    db: Session,
    *,
    user: CurrentUser,
    from_: Optional[date],
    to_: Optional[date],
    department_id: Optional[uuid.UUID],
    action: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> bytes:
    if not dc.is_privileged(user):
        raise dc.forbidden("Chỉ admin / lãnh đạo được xuất báo cáo")
    stats = aggregate_access_stats(
        db,
        user=user,
        from_=from_,
        to_=to_,
        department_id=department_id,
        action=action,
        top=100,
        sort_by="total",
    )

    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Thống kê truy cập tài liệu"
    rng = stats["range"]
    summ = stats["summary"]
    ws.append(["BÁO CÁO THỐNG KÊ TRUY CẬP TÀI LIỆU (R15)"])
    ws.append(["Khoảng thời gian", f"{rng['from']} → {rng['to']}"])
    ws.append(["Tổng lượt xem", summ["total_view"]])
    ws.append(["Tổng lượt tải", summ["total_download"]])
    ws.append(["Tổng lượt sửa", summ["total_edit"]])
    ws.append(["Số tài liệu", summ["document_count"]])
    ws.append([])
    ws.append(["Mã tài liệu", "Tiêu đề", "Phòng", "Xem", "Tải", "Sửa", "Tổng"])
    for d in stats["top_documents"]:
        ws.append(
            [
                d["document_code"],
                d["title"],
                d["department_name"],
                d["view"],
                d["download"],
                d["edit"],
                d["total"],
            ]
        )

    audit_service.log_action(
        db,
        action="DOCUMENT_STATS_EXPORT",
        resource="document",
        user_id=user.id,
        resource_id=None,
        correlation_id=correlation_id,
        ip=ip,
        detail={"range": rng},
    )
    db.commit()

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
