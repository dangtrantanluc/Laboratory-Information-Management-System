"""Bài báo/sáng chế (#23-#28) — đồng tác giả n-n, XOR user_id/external_name.

Tách từ research_service.py (1.736 dòng, 9 domain) — M-03/T1.1.
Xem app/services/research/__init__.py để biết vì sao có mặt tiền tương thích.
"""
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db_helpers import get_or_404
from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.research import Publication, PublicationAuthor, PublicationCategory
from app.services import audit_service, hr_common as hc
from app.services.research._shared import _assert_staff_in_members


def _pub_dict(db: Session, p: Publication) -> dict:
    rows = db.execute(
        select(PublicationAuthor)
        .where(PublicationAuthor.publication_id == p.id)
        .order_by(PublicationAuthor.author_order.asc())
    ).scalars().all()
    authors = [
        {
            "user_id": a.user_id,
            "external_name": a.external_name,
            "name": hc.user_name(db, a.user_id) if a.user_id else a.external_name,
            "author_order": a.author_order,
            "is_corresponding": a.is_corresponding,
            "author_role": a.author_role,
        }
        for a in rows
    ]
    return {
        "id": p.id,
        "type": p.type,
        "title": p.title,
        "journal": p.journal,
        "year": p.year,
        "doi": p.doi,
        "category": p.category,
        "pub_scope": p.pub_scope,
        "is_scie": p.is_scie,
        "is_ssci": p.is_ssci,
        "is_scopus": p.is_scopus,
        "is_aci": p.is_aci,
        "academic_year": p.academic_year,
        "department_id": p.department_id,
        "department_name": hc.dept_name(db, p.department_id),
        "patent_no": p.patent_no,
        "issuing_authority": p.issuing_authority,
        "application_no": p.application_no,
        "application_date": p.application_date.isoformat() if p.application_date else None,
        "granted_date": p.granted_date.isoformat() if p.granted_date else None,
        "patent_holder": p.patent_holder,
        "patent_kind": p.patent_kind,
        "evidence_url": p.evidence_url,
        "authors": authors,
        "created_at": p.created_at,
    }


def _validate_authors(db: Session, authors: list) -> set:
    if not authors:
        raise AppException(ErrorCode.VALIDATION_ERROR, "authors không được rỗng", 400)
    seen_order: set[int] = set()
    internal_users: set[uuid.UUID] = set()
    for idx, a in enumerate(authors):
        uid = a.get("user_id")
        ext = a.get("external_name")
        if (uid is None) == (ext is None):
            raise AppException(
                ErrorCode.INVALID_AUTHOR,
                "Mỗi tác giả phải là user_id HOẶC external_name, không cả hai/để trống",
                422,
                [{"field": f"authors[{idx}]", "message": "XOR user_id/external_name"}],
            )
        order = a.get("author_order")
        if order is None or int(order) < 1:
            raise AppException(ErrorCode.VALIDATION_ERROR, "author_order phải >= 1", 400)
        if order in seen_order:
            raise AppException(
                ErrorCode.DUPLICATE_AUTHOR_ORDER, "author_order trùng trong cùng bài", 422
            )
        seen_order.add(order)
        if uid is not None:
            hc.assert_user_exists(db, uid)
            internal_users.add(uid)
    return internal_users


def _validate_pub_fields(db: Session, payload: dict) -> None:
    ptype = payload.get("type")
    if ptype not in ("paper", "patent", "conference"):
        raise AppException(ErrorCode.VALIDATION_ERROR, "type phải là paper|patent|conference", 400)
    if not payload.get("title") or not str(payload["title"]).strip():
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu title", 400)
    year = payload.get("year")
    if year is None:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu year", 400)
    if not (1900 <= int(year) <= date.today().year + 1):
        raise AppException(ErrorCode.VALIDATION_ERROR, "year ngoài khoảng hợp lệ", 400)
    doi = payload.get("doi")
    if doi:
        import re

        if not re.match(r"^10\.\d{4,}/.+", doi):
            raise AppException(ErrorCode.VALIDATION_ERROR, "DOI sai định dạng (10.xxxx/...)", 400)
    if ptype == "paper":
        cat = payload.get("category")
        if not cat:
            raise AppException(ErrorCode.INVALID_INDEX, "Thiếu chỉ số bài báo (category)", 400)
        if db.get(PublicationCategory, cat) is None:
            raise AppException(ErrorCode.INVALID_INDEX, "Chỉ số bài báo ngoài danh mục", 400)
        if not payload.get("journal"):
            raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu journal (bài báo)", 400)
    if ptype == "conference":
        # Báo cáo hội nghị/kỷ yếu: cần tên kỷ yếu/hội nghị (journal), KHÔNG cần category.
        if not payload.get("journal"):
            raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu tên kỷ yếu/hội nghị (journal)", 400)
    if ptype == "patent":
        if not payload.get("patent_no") or not str(payload["patent_no"]).strip():
            raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu patent_no (sáng chế)", 400)
        if not payload.get("issuing_authority"):
            raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu issuing_authority (sáng chế)", 400)
    elif payload.get("patent_kind"):
        # Khớp CHECK ck_pub_patent_kind: bắt ở tầng service để trả lỗi nghiệp vụ rõ ràng
        # thay vì để Postgres ném IntegrityError 500.
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            "patent_kind chỉ áp dụng cho sáng chế/GPHI/giống cây trồng (type=patent)",
            400,
        )


def list_publications(
    db: Session,
    *,
    user: CurrentUser,
    q: Optional[str],
    type_filter: Optional[str],
    year: Optional[int],
    category: Optional[str],
    department_id: Optional[uuid.UUID],
    author_user_id: Optional[uuid.UUID],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    if q:
        conditions.append(Publication.title.ilike(f"%{q.strip()}%"))
    if type_filter:
        conditions.append(Publication.type == type_filter)
    if year:
        conditions.append(Publication.year == year)
    if category:
        conditions.append(Publication.category == category)
    if department_id:
        conditions.append(Publication.department_id == department_id)
    author_filter = author_user_id
    if not hc.is_research_all(user):
        author_filter = user.id  # staff own: ép theo chính mình
    if author_filter:
        sub = select(PublicationAuthor.publication_id).where(
            PublicationAuthor.user_id == author_filter
        )
        conditions.append(Publication.id.in_(sub))

    total = db.execute(
        select(func.count()).select_from(Publication).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(Publication)
        .where(*conditions)
        .order_by(Publication.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return [_pub_dict(db, p) for p in rows], total


def create_publication(
    db: Session,
    *,
    user: CurrentUser,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    _validate_pub_fields(db, payload)
    authors = payload.get("authors") or []
    internal_users = _validate_authors(db, authors)
    _assert_staff_in_members(user, internal_users, "tác giả")

    ptype = payload["type"]
    if ptype == "patent" and payload.get("patent_no"):
        existing = db.execute(
            select(Publication.id).where(
                Publication.type == "patent",
                Publication.patent_no == payload["patent_no"],
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise AppException(ErrorCode.DUPLICATE_PATENT_NO, "Số bằng sáng chế đã tồn tại", 409)

    is_patent = ptype == "patent"
    p = Publication(
        title=str(payload["title"]).strip(),
        journal=payload.get("journal"),
        year=payload.get("year"),
        doi=payload.get("doi"),
        category=payload.get("category") if ptype == "paper" else None,
        type=ptype,
        pub_scope=payload.get("pub_scope") if not is_patent else None,
        is_scie=bool(payload.get("is_scie")),
        is_ssci=bool(payload.get("is_ssci")),
        is_scopus=bool(payload.get("is_scopus")),
        is_aci=bool(payload.get("is_aci")),
        academic_year=payload.get("academic_year"),
        patent_no=payload.get("patent_no") if is_patent else None,
        issuing_authority=payload.get("issuing_authority") if is_patent else None,
        application_no=payload.get("application_no") if is_patent else None,
        application_date=payload.get("application_date") if is_patent else None,
        granted_date=payload.get("granted_date") if is_patent else None,
        patent_holder=payload.get("patent_holder") if is_patent else None,
        patent_kind=payload.get("patent_kind") if is_patent else None,
        evidence_url=payload.get("evidence_url"),
        department_id=payload.get("department_id"),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(p)
    db.flush()
    for a in authors:
        db.add(
            PublicationAuthor(
                publication_id=p.id,
                author_order=a["author_order"],
                user_id=a.get("user_id"),
                external_name=a.get("external_name"),
                is_corresponding=bool(a.get("is_corresponding", False)),
                author_role=a.get("author_role"),
            )
        )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppException(ErrorCode.DUPLICATE_PATENT_NO, "Số bằng sáng chế đã tồn tại", 409)
    action = "RESEARCH_PATENT_CREATE" if ptype == "patent" else "RESEARCH_PUBLICATION_CREATE"
    audit_service.log_action(
        db,
        action=action,
        resource="publication",
        user_id=user.id,
        resource_id=p.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"type": ptype, "title": p.title},
    )
    db.commit()
    db.refresh(p)
    return _pub_dict(db, p)


def _get_pub_or_404(db: Session, pub_id: uuid.UUID) -> Publication:
    return get_or_404(db, Publication, pub_id, "Bài báo/sáng chế không tồn tại", code=ErrorCode.PUBLICATION_NOT_FOUND)


def _assert_pub_scope(db: Session, user: CurrentUser, p: Publication) -> None:
    if hc.is_research_all(user):
        return
    is_author = db.execute(
        select(PublicationAuthor).where(
            PublicationAuthor.publication_id == p.id,
            PublicationAuthor.user_id == user.id,
        )
    ).scalar_one_or_none()
    if is_author is None:
        raise hc.forbidden("Bạn chỉ thao tác trên công bố mình là tác giả")


def get_publication(db: Session, *, user: CurrentUser, pub_id: uuid.UUID) -> dict:
    p = _get_pub_or_404(db, pub_id)
    _assert_pub_scope(db, user, p)
    return _pub_dict(db, p)


def update_publication(
    db: Session,
    *,
    user: CurrentUser,
    pub_id: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    p = _get_pub_or_404(db, pub_id)
    _assert_pub_scope(db, user, p)
    if not changes:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Body rỗng", 400)
    if "category" in changes and changes["category"]:
        if db.get(PublicationCategory, changes["category"]) is None:
            raise AppException(ErrorCode.INVALID_INDEX, "Chỉ số bài báo ngoài danh mục", 400)
    if "patent_no" in changes and changes["patent_no"] and p.type == "patent":
        existing = db.execute(
            select(Publication.id).where(
                Publication.type == "patent",
                Publication.patent_no == changes["patent_no"],
                Publication.id != p.id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise AppException(ErrorCode.DUPLICATE_PATENT_NO, "Số bằng sáng chế đã tồn tại", 409)
    # patent_kind chỉ có nghĩa với type='patent' (khớp CHECK ck_pub_patent_kind).
    if changes.get("patent_kind") and p.type != "patent":
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            "patent_kind chỉ áp dụng cho sáng chế/GPHI/giống cây trồng (type=patent)",
            400,
        )
    # Danh sách này trước đây chỉ có 8 field, nên pub_scope / 4 cờ chỉ mục / các cột
    # sáng chế đã tồn tại trong CSDL vẫn không sửa được qua PATCH — bổ sung đủ để
    # bản ghi khớp mọi cột của file Excel.
    for field in (
        "title",
        "journal",
        "year",
        "doi",
        "category",
        "pub_scope",
        "is_scie",
        "is_ssci",
        "is_scopus",
        "is_aci",
        "academic_year",
        "patent_no",
        "issuing_authority",
        "application_no",
        "application_date",
        "granted_date",
        "patent_holder",
        "patent_kind",
        "evidence_url",
        "department_id",
    ):
        if field in changes:
            setattr(p, field, changes[field])
    p.updated_by = user.id
    p.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="RESEARCH_PUBLICATION_UPDATE",
        resource="publication",
        user_id=user.id,
        resource_id=p.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"changed_fields": list(changes.keys())},
    )
    db.commit()
    db.refresh(p)
    return _pub_dict(db, p)


def delete_publication(
    db: Session,
    *,
    user: CurrentUser,
    pub_id: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> None:
    p = _get_pub_or_404(db, pub_id)
    _assert_pub_scope(db, user, p)
    db.delete(p)
    audit_service.log_action(
        db,
        action="RESEARCH_PUBLICATION_DELETE",
        resource="publication",
        user_id=user.id,
        resource_id=pub_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"op": "delete"},
    )
    db.commit()


def replace_authors(
    db: Session,
    *,
    user: CurrentUser,
    pub_id: uuid.UUID,
    authors: list,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    p = _get_pub_or_404(db, pub_id)
    _assert_pub_scope(db, user, p)
    _validate_authors(db, authors)
    db.execute(
        PublicationAuthor.__table__.delete().where(
            PublicationAuthor.publication_id == p.id
        )
    )
    for a in authors:
        db.add(
            PublicationAuthor(
                publication_id=p.id,
                author_order=a["author_order"],
                user_id=a.get("user_id"),
                external_name=a.get("external_name"),
                is_corresponding=bool(a.get("is_corresponding", False)),
            )
        )
    p.updated_by = user.id
    p.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="RESEARCH_PUBLICATION_AUTHORS_UPDATE",
        resource="publication",
        user_id=user.id,
        resource_id=p.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"author_count": len(authors)},
    )
    db.commit()
    db.refresh(p)
    return _pub_dict(db, p)
