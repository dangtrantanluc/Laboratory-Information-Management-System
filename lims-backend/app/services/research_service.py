"""Research achievement service (M4.3) — đề tài NCKH + thành viên n-n, bài báo/sáng chế
+ đồng tác giả n-n (XOR user_id/external_name), hướng dẫn SV, đăng ký lab (có duyệt),
giảng dạy, phục vụ cộng đồng, hồ sơ năng lực tổng hợp, thống kê.

Scope research (BR-HR-023): admin/leader=all; staff=own (chỉ bản ghi mình tham gia);
accountant → 403 FORBIDDEN_ACCOUNTANT (enforce ở router qua hc.assert_research_access).
Tác giả/thành viên ngoài hệ thống qua external_name (D7, XOR).
"""
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.department import Department
from app.models.hr import (
    CommunityService,
    LabRegistration,
    MentorshipType,
    ProjectMember,
    Publication,
    PublicationAuthor,
    PublicationCategory,
    ResearchProject,
    ResearchProjectLevel,
    StudentMentorship,
    TeachingCourse,
)
from app.models.user import User
from app.services import audit_service, hr_common as hc


# ===================== Helpers chung members/authors =====================
def _validate_members(db: Session, members: list, *, allow_external: bool, lead_user_id):
    """Validate danh sách thành viên/tác giả. Trả (internal_user_ids set).

    allow_external=False (project_members FK chặt): chỉ user_id; external → INVALID_AUTHOR.
    Đề tài: lead_user_id phải nằm trong members.
    """
    if not members:
        raise AppException("VALIDATION_ERROR", "members không được rỗng", 400)
    seen_users: set[uuid.UUID] = set()
    for idx, m in enumerate(members):
        uid = m.get("user_id")
        ext = m.get("external_name")
        if (uid is None) == (ext is None):
            raise AppException(
                "INVALID_AUTHOR",
                "Mỗi thành viên phải là user_id HOẶC external_name, không cả hai/để trống",
                422,
                [{"field": f"members[{idx}]", "message": "XOR user_id/external_name"}],
            )
        if ext is not None and not allow_external:
            raise AppException(
                "INVALID_AUTHOR",
                "Thành viên đề tài phải là người nội bộ (user_id)",
                422,
                [{"field": f"members[{idx}]", "message": "external_name không cho phép"}],
            )
        if uid is not None:
            if uid in seen_users:
                raise AppException(
                    "DUPLICATE_MEMBER", "Một người là thành viên 2 lần", 409
                )
            hc.assert_user_exists(db, uid)
            seen_users.add(uid)
    if lead_user_id is not None and lead_user_id not in seen_users:
        raise AppException(
            "LEAD_REQUIRED", "Chủ nhiệm phải nằm trong danh sách thành viên", 400
        )
    return seen_users


def _assert_staff_in_members(user: CurrentUser, internal_users: set, field: str):
    """Staff own: phải là thành viên/tác giả nội bộ của bản ghi (BR-HR-023)."""
    if user.role == "staff" and user.id not in internal_users:
        raise hc.forbidden(f"Bạn phải là một {field} nội bộ của bản ghi này")


# ===================== ĐỀ TÀI (#17-#22) =====================
def _project_dict(db: Session, p: ResearchProject, *, with_members: bool) -> dict:
    member_count = db.execute(
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.project_id == p.id)
    ).scalar_one()
    data = {
        "id": p.id,
        "code": p.code,
        "title": p.title,
        "level": p.level,
        "lead_user_id": p.lead_user_id,
        "lead_user_name": hc.user_name(db, p.lead_user_id),
        "department_id": p.department_id,
        "department_name": hc.dept_name(db, p.department_id),
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "end_date": p.end_date.isoformat() if p.end_date else None,
        "status": p.status,
        "member_count": member_count,
        "created_at": p.created_at,
    }
    if with_members:
        rows = db.execute(
            select(ProjectMember).where(ProjectMember.project_id == p.id)
        ).scalars().all()
        data["members"] = [
            {
                "user_id": m.user_id,
                "name": hc.user_name(db, m.user_id),
                "role_in_project": m.role_in_project,
            }
            for m in rows
        ]
    return data


def _staff_project_ids(db: Session, user: CurrentUser):
    sub = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
    return sub


def list_projects(
    db: Session,
    *,
    user: CurrentUser,
    q: Optional[str],
    department_id: Optional[uuid.UUID],
    level: Optional[str],
    year: Optional[int],
    lead_user_id: Optional[uuid.UUID],
    status_filter: Optional[str],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    if q:
        conditions.append(ResearchProject.title.ilike(f"%{q.strip()}%"))
    if department_id:
        conditions.append(ResearchProject.department_id == department_id)
    if level:
        conditions.append(ResearchProject.level == level)
    if lead_user_id:
        conditions.append(ResearchProject.lead_user_id == lead_user_id)
    if status_filter:
        conditions.append(ResearchProject.status == status_filter)
    if year:
        from datetime import date as _d

        conditions.append(
            or_(
                ResearchProject.start_date.is_(None),
                ResearchProject.start_date <= _d(year, 12, 31),
            )
        )
        conditions.append(
            or_(
                ResearchProject.end_date.is_(None),
                ResearchProject.end_date >= _d(year, 1, 1),
            )
        )
    if not hc.is_research_all(user):
        conditions.append(ResearchProject.id.in_(_staff_project_ids(db, user)))

    total = db.execute(
        select(func.count()).select_from(ResearchProject).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(ResearchProject)
        .where(*conditions)
        .order_by(ResearchProject.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return [_project_dict(db, p, with_members=False) for p in rows], total


def create_project(
    db: Session,
    *,
    user: CurrentUser,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    title = payload.get("title")
    if not title or not str(title).strip():
        raise AppException("VALIDATION_ERROR", "Thiếu title", 400)
    level = payload.get("level")
    if not level or db.get(ResearchProjectLevel, level) is None:
        raise AppException("INVALID_PROJECT_LEVEL", "Cấp đề tài ngoài danh mục", 400)
    lead_user_id = payload.get("lead_user_id")
    if not lead_user_id:
        raise AppException("LEAD_REQUIRED", "Thiếu chủ nhiệm (lead_user_id)", 400)
    members = payload.get("members") or []
    internal_users = _validate_members(
        db, members, allow_external=False, lead_user_id=lead_user_id
    )
    _assert_staff_in_members(user, internal_users, "thành viên")

    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    if start_date and end_date and end_date < start_date:
        raise AppException("INVALID_DATE_ORDER", "end_date < start_date", 422)

    department_id = payload.get("department_id")
    if department_id is None:
        department_id = hc.user_dept(db, lead_user_id)

    p = ResearchProject(
        code=payload.get("code"),
        title=str(title).strip(),
        level=level,
        lead_user_id=lead_user_id,
        department_id=department_id,
        start_date=start_date,
        end_date=end_date,
        status=payload.get("status") or "ongoing",
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(p)
    db.flush()
    for m in members:
        db.add(
            ProjectMember(
                project_id=p.id,
                user_id=m["user_id"],
                role_in_project=m.get("role_in_project") or "member",
            )
        )
    db.flush()
    audit_service.log_action(
        db,
        action="RESEARCH_PROJECT_CREATE",
        resource="research_project",
        user_id=user.id,
        resource_id=p.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"title": p.title, "level": level},
    )
    db.commit()
    db.refresh(p)
    return _project_dict(db, p, with_members=True)


def _get_project_or_404(db: Session, project_id: uuid.UUID) -> ResearchProject:
    p = db.get(ResearchProject, project_id)
    if p is None:
        raise AppException("PROJECT_NOT_FOUND", "Đề tài không tồn tại", 404)
    return p


def _assert_project_scope(db: Session, user: CurrentUser, p: ResearchProject) -> None:
    if hc.is_research_all(user):
        return
    is_member = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == p.id, ProjectMember.user_id == user.id
        )
    ).scalar_one_or_none()
    if is_member is None:
        raise hc.forbidden("Bạn chỉ thao tác trên đề tài mình tham gia")


def get_project(db: Session, *, user: CurrentUser, project_id: uuid.UUID) -> dict:
    p = _get_project_or_404(db, project_id)
    _assert_project_scope(db, user, p)
    return _project_dict(db, p, with_members=True)


def update_project(
    db: Session,
    *,
    user: CurrentUser,
    project_id: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    p = _get_project_or_404(db, project_id)
    _assert_project_scope(db, user, p)
    if not changes:
        raise AppException("VALIDATION_ERROR", "Body rỗng", 400)
    if "level" in changes and changes["level"] is not None:
        if db.get(ResearchProjectLevel, changes["level"]) is None:
            raise AppException("INVALID_PROJECT_LEVEL", "Cấp đề tài ngoài danh mục", 400)
    if "lead_user_id" in changes and changes["lead_user_id"]:
        member = db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == p.id,
                ProjectMember.user_id == changes["lead_user_id"],
            )
        ).scalar_one_or_none()
        if member is None:
            raise AppException(
                "LEAD_REQUIRED", "Chủ nhiệm mới phải là thành viên đề tài", 400
            )
    new_start = changes.get("start_date", p.start_date)
    new_end = changes.get("end_date", p.end_date)
    if new_start and new_end and new_end < new_start:
        raise AppException("INVALID_DATE_ORDER", "end_date < start_date", 422)
    for field in (
        "code",
        "title",
        "level",
        "lead_user_id",
        "department_id",
        "start_date",
        "end_date",
        "status",
    ):
        if field in changes:
            setattr(p, field, changes[field])
    p.updated_by = user.id
    p.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="RESEARCH_PROJECT_UPDATE",
        resource="research_project",
        user_id=user.id,
        resource_id=p.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"changed_fields": list(changes.keys())},
    )
    db.commit()
    db.refresh(p)
    return _project_dict(db, p, with_members=True)


def delete_project(
    db: Session,
    *,
    user: CurrentUser,
    project_id: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> None:
    p = _get_project_or_404(db, project_id)
    _assert_project_scope(db, user, p)
    db.delete(p)  # CASCADE project_members
    audit_service.log_action(
        db,
        action="RESEARCH_PROJECT_DELETE",
        resource="research_project",
        user_id=user.id,
        resource_id=project_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"op": "delete"},
    )
    db.commit()


def replace_project_members(
    db: Session,
    *,
    user: CurrentUser,
    project_id: uuid.UUID,
    members: list,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    p = _get_project_or_404(db, project_id)
    _assert_project_scope(db, user, p)
    internal_users = _validate_members(
        db, members, allow_external=False, lead_user_id=p.lead_user_id
    )
    _assert_staff_in_members(user, internal_users, "thành viên")
    db.execute(
        ProjectMember.__table__.delete().where(ProjectMember.project_id == p.id)
    )
    for m in members:
        db.add(
            ProjectMember(
                project_id=p.id,
                user_id=m["user_id"],
                role_in_project=m.get("role_in_project") or "member",
            )
        )
    p.updated_by = user.id
    p.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="RESEARCH_PROJECT_MEMBERS_UPDATE",
        resource="research_project",
        user_id=user.id,
        resource_id=p.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"member_count": len(members)},
    )
    db.commit()
    db.refresh(p)
    return _project_dict(db, p, with_members=True)


# ===================== PUBLICATIONS (#23-#28) =====================
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
        "department_id": p.department_id,
        "department_name": hc.dept_name(db, p.department_id),
        "patent_no": p.patent_no,
        "issuing_authority": p.issuing_authority,
        "authors": authors,
        "created_at": p.created_at,
    }


def _validate_authors(db: Session, authors: list) -> set:
    if not authors:
        raise AppException("VALIDATION_ERROR", "authors không được rỗng", 400)
    seen_order: set[int] = set()
    internal_users: set[uuid.UUID] = set()
    for idx, a in enumerate(authors):
        uid = a.get("user_id")
        ext = a.get("external_name")
        if (uid is None) == (ext is None):
            raise AppException(
                "INVALID_AUTHOR",
                "Mỗi tác giả phải là user_id HOẶC external_name, không cả hai/để trống",
                422,
                [{"field": f"authors[{idx}]", "message": "XOR user_id/external_name"}],
            )
        order = a.get("author_order")
        if order is None or int(order) < 1:
            raise AppException("VALIDATION_ERROR", "author_order phải >= 1", 400)
        if order in seen_order:
            raise AppException(
                "DUPLICATE_AUTHOR_ORDER", "author_order trùng trong cùng bài", 422
            )
        seen_order.add(order)
        if uid is not None:
            hc.assert_user_exists(db, uid)
            internal_users.add(uid)
    return internal_users


def _validate_pub_fields(db: Session, payload: dict) -> None:
    ptype = payload.get("type")
    if ptype not in ("paper", "patent"):
        raise AppException("VALIDATION_ERROR", "type phải là paper|patent", 400)
    if not payload.get("title") or not str(payload["title"]).strip():
        raise AppException("VALIDATION_ERROR", "Thiếu title", 400)
    year = payload.get("year")
    if year is None:
        raise AppException("VALIDATION_ERROR", "Thiếu year", 400)
    if not (1900 <= int(year) <= date.today().year + 1):
        raise AppException("VALIDATION_ERROR", "year ngoài khoảng hợp lệ", 400)
    doi = payload.get("doi")
    if doi:
        import re

        if not re.match(r"^10\.\d{4,}/.+", doi):
            raise AppException("VALIDATION_ERROR", "DOI sai định dạng (10.xxxx/...)", 400)
    if ptype == "paper":
        cat = payload.get("category")
        if not cat:
            raise AppException("INVALID_INDEX", "Thiếu chỉ số bài báo (category)", 400)
        if db.get(PublicationCategory, cat) is None:
            raise AppException("INVALID_INDEX", "Chỉ số bài báo ngoài danh mục", 400)
        if not payload.get("journal"):
            raise AppException("VALIDATION_ERROR", "Thiếu journal (bài báo)", 400)
    if ptype == "patent":
        if not payload.get("patent_no") or not str(payload["patent_no"]).strip():
            raise AppException("VALIDATION_ERROR", "Thiếu patent_no (sáng chế)", 400)
        if not payload.get("issuing_authority"):
            raise AppException("VALIDATION_ERROR", "Thiếu issuing_authority (sáng chế)", 400)


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
            raise AppException("DUPLICATE_PATENT_NO", "Số bằng sáng chế đã tồn tại", 409)

    p = Publication(
        title=str(payload["title"]).strip(),
        journal=payload.get("journal"),
        year=payload.get("year"),
        doi=payload.get("doi"),
        category=payload.get("category") if ptype == "paper" else None,
        type=ptype,
        patent_no=payload.get("patent_no") if ptype == "patent" else None,
        issuing_authority=payload.get("issuing_authority") if ptype == "patent" else None,
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
            )
        )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppException("DUPLICATE_PATENT_NO", "Số bằng sáng chế đã tồn tại", 409)
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
    p = db.get(Publication, pub_id)
    if p is None:
        raise AppException("PUBLICATION_NOT_FOUND", "Bài báo/sáng chế không tồn tại", 404)
    return p


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
        raise AppException("VALIDATION_ERROR", "Body rỗng", 400)
    if "category" in changes and changes["category"]:
        if db.get(PublicationCategory, changes["category"]) is None:
            raise AppException("INVALID_INDEX", "Chỉ số bài báo ngoài danh mục", 400)
    if "patent_no" in changes and changes["patent_no"] and p.type == "patent":
        existing = db.execute(
            select(Publication.id).where(
                Publication.type == "patent",
                Publication.patent_no == changes["patent_no"],
                Publication.id != p.id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise AppException("DUPLICATE_PATENT_NO", "Số bằng sáng chế đã tồn tại", 409)
    for field in (
        "title",
        "journal",
        "year",
        "doi",
        "category",
        "patent_no",
        "issuing_authority",
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


# ===================== STUDENT MENTORSHIPS (#30-#32) =====================
def _mentorship_dict(db: Session, m: StudentMentorship) -> dict:
    return {
        "id": m.id,
        "mentor_id": m.mentor_id,
        "mentor_name": hc.user_name(db, m.mentor_id),
        "student_name": m.student_name,
        "topic": m.topic,
        "year": m.year,
        "type": m.type,
        "department_id": m.department_id,
        "department_name": hc.dept_name(db, m.department_id),
        "created_at": m.created_at,
    }


def list_mentorships(
    db: Session,
    *,
    user: CurrentUser,
    mentor_id: Optional[uuid.UUID],
    year: Optional[int],
    type_filter: Optional[str],
    department_id: Optional[uuid.UUID],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    eff_mentor = mentor_id
    if not hc.is_research_all(user):
        eff_mentor = user.id
    if eff_mentor:
        conditions.append(StudentMentorship.mentor_id == eff_mentor)
    if year:
        conditions.append(StudentMentorship.year == year)
    if type_filter:
        conditions.append(StudentMentorship.type == type_filter)
    if department_id:
        conditions.append(StudentMentorship.department_id == department_id)
    total = db.execute(
        select(func.count()).select_from(StudentMentorship).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(StudentMentorship)
        .where(*conditions)
        .order_by(StudentMentorship.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return [_mentorship_dict(db, m) for m in rows], total


def create_mentorship(
    db: Session,
    *,
    user: CurrentUser,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    mentor_id = payload.get("mentor_id")
    if not mentor_id:
        raise AppException("VALIDATION_ERROR", "Thiếu mentor_id", 400)
    if user.role == "staff" and mentor_id != user.id:
        raise hc.forbidden("Bạn chỉ khai hướng dẫn của chính mình")
    hc.assert_user_exists(db, mentor_id)
    if not payload.get("student_name"):
        raise AppException("VALIDATION_ERROR", "Thiếu student_name", 400)
    year = payload.get("year")
    if year is None or not (1900 <= int(year) <= date.today().year + 1):
        raise AppException("VALIDATION_ERROR", "year ngoài khoảng hợp lệ", 400)
    mtype = payload.get("type")
    if not mtype or db.get(MentorshipType, mtype) is None:
        raise AppException("INVALID_MENTORSHIP_TYPE", "Loại hướng dẫn ngoài danh mục", 400)
    m = StudentMentorship(
        mentor_id=mentor_id,
        student_name=str(payload["student_name"]).strip(),
        topic=payload.get("topic"),
        year=year,
        type=mtype,
        department_id=hc.user_dept(db, mentor_id),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(m)
    db.flush()
    audit_service.log_action(
        db,
        action="RESEARCH_MENTORSHIP_CREATE",
        resource="student_mentorship",
        user_id=user.id,
        resource_id=m.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"type": mtype, "year": year},
    )
    db.commit()
    db.refresh(m)
    return _mentorship_dict(db, m)


def _get_mentorship_or_404(db: Session, mid: uuid.UUID) -> StudentMentorship:
    m = db.get(StudentMentorship, mid)
    if m is None:
        raise AppException("MENTORSHIP_NOT_FOUND", "Bản ghi hướng dẫn không tồn tại", 404)
    return m


def update_mentorship(
    db: Session,
    *,
    user: CurrentUser,
    mid: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    m = _get_mentorship_or_404(db, mid)
    if not hc.is_research_all(user) and m.mentor_id != user.id:
        raise hc.forbidden("Bạn chỉ sửa hướng dẫn của chính mình")
    if not changes:
        raise AppException("VALIDATION_ERROR", "Body rỗng", 400)
    if "type" in changes and changes["type"]:
        if db.get(MentorshipType, changes["type"]) is None:
            raise AppException(
                "INVALID_MENTORSHIP_TYPE", "Loại hướng dẫn ngoài danh mục", 400
            )
    for field in ("student_name", "topic", "year", "type"):
        if field in changes:
            setattr(m, field, changes[field])
    m.updated_by = user.id
    m.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="RESEARCH_MENTORSHIP_UPDATE",
        resource="student_mentorship",
        user_id=user.id,
        resource_id=m.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"changed_fields": list(changes.keys())},
    )
    db.commit()
    db.refresh(m)
    return _mentorship_dict(db, m)


def delete_mentorship(
    db: Session,
    *,
    user: CurrentUser,
    mid: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> None:
    m = _get_mentorship_or_404(db, mid)
    if not hc.is_research_all(user) and m.mentor_id != user.id:
        raise hc.forbidden("Bạn chỉ xóa hướng dẫn của chính mình")
    db.delete(m)
    audit_service.log_action(
        db,
        action="RESEARCH_MENTORSHIP_DELETE",
        resource="student_mentorship",
        user_id=user.id,
        resource_id=mid,
        correlation_id=correlation_id,
        ip=ip,
        detail={"op": "delete"},
    )
    db.commit()


# ===================== LAB REGISTRATIONS (#33-#34c) =====================
def _registration_dict(db: Session, r: LabRegistration) -> dict:
    return {
        "id": r.id,
        "student_name": r.student_name,
        "mentor_id": r.mentor_id,
        "mentor_name": hc.user_name(db, r.mentor_id),
        "registered_at": r.registered_at.isoformat() if r.registered_at else None,
        "registered_from": r.registered_from.isoformat() if r.registered_from else None,
        "registered_to": r.registered_to.isoformat() if r.registered_to else None,
        "purpose": r.purpose,
        "status": r.status,
        "department_id": r.department_id,
        "decided_by_user_id": r.approved_by,
        "decided_at": r.approved_at,
        "created_at": r.created_at,
    }


def list_registrations(
    db: Session,
    *,
    user: CurrentUser,
    status_filter: Optional[str],
    mentor_id: Optional[uuid.UUID],
    department_id: Optional[uuid.UUID],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    if status_filter:
        conditions.append(LabRegistration.status == status_filter)
    eff_mentor = mentor_id
    if not hc.is_research_all(user):
        eff_mentor = user.id
    if eff_mentor:
        conditions.append(LabRegistration.mentor_id == eff_mentor)
    if department_id:
        conditions.append(LabRegistration.department_id == department_id)
    total = db.execute(
        select(func.count()).select_from(LabRegistration).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(LabRegistration)
        .where(*conditions)
        .order_by(LabRegistration.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return [_registration_dict(db, r) for r in rows], total


def create_registration(
    db: Session,
    *,
    user: CurrentUser,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    mentor_id = payload.get("mentor_id")
    if not mentor_id:
        raise AppException("VALIDATION_ERROR", "Thiếu mentor_id", 400)
    if user.role == "staff" and mentor_id != user.id:
        raise hc.forbidden("Bạn chỉ tạo đăng ký với mentor là chính mình")
    hc.assert_user_exists(db, mentor_id)
    if not payload.get("student_name"):
        raise AppException("VALIDATION_ERROR", "Thiếu student_name", 400)
    if not payload.get("registered_from"):
        raise AppException("VALIDATION_ERROR", "Thiếu registered_from", 400)
    if not payload.get("purpose"):
        raise AppException("VALIDATION_ERROR", "Thiếu purpose", 400)
    reg_from = payload.get("registered_from")
    reg_to = payload.get("registered_to")
    if reg_to and reg_from and reg_to < reg_from:
        raise AppException("INVALID_DATE_ORDER", "registered_to < registered_from", 422)
    r = LabRegistration(
        student_name=str(payload["student_name"]).strip(),
        mentor_id=mentor_id,
        registered_from=reg_from,
        registered_to=reg_to,
        purpose=payload.get("purpose"),
        status="pending",
        department_id=hc.user_dept(db, mentor_id),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(r)
    db.flush()
    audit_service.log_action(
        db,
        action="LAB_REGISTRATION_CREATE",
        resource="lab_registration",
        user_id=user.id,
        resource_id=r.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"mentor_id": str(mentor_id)},
    )
    db.commit()
    db.refresh(r)
    return _registration_dict(db, r)


def _can_decide_registration(db: Session, user: CurrentUser, r: LabRegistration) -> bool:
    """admin/leader; mentor của lượt; trưởng nhóm phòng của mentor (is_dept_lead)."""
    if user.role in ("admin", "leader"):
        return True
    if r.mentor_id == user.id:
        return True
    # trưởng nhóm phòng mentor
    mentor_dept = hc.user_dept(db, r.mentor_id)
    if user.is_dept_lead and mentor_dept is not None and user.department_id == mentor_dept:
        return True
    return False


def decide_registration(
    db: Session,
    *,
    user: CurrentUser,
    reg_id: uuid.UUID,
    decision: str,  # 'approved' | 'rejected'
    reason: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    r = db.get(LabRegistration, reg_id)
    if r is None:
        raise AppException("REGISTRATION_NOT_FOUND", "Lượt đăng ký không tồn tại", 404)
    if not _can_decide_registration(db, user, r):
        raise hc.forbidden("Bạn không có quyền duyệt lượt đăng ký này")
    if r.status != "pending":
        raise AppException(
            "REGISTRATION_ALREADY_DECIDED",
            "Lượt đăng ký đã được duyệt/từ chối, không thể quyết lại",
            409,
        )
    r.status = decision
    r.approved_by = user.id
    r.approved_at = datetime.now(timezone.utc)
    r.updated_by = user.id
    r.updated_at = func.now()
    db.flush()
    action = "LAB_REGISTRATION_APPROVE" if decision == "approved" else "LAB_REGISTRATION_REJECT"
    audit_service.log_action(
        db,
        action=action,
        resource="lab_registration",
        user_id=user.id,
        resource_id=r.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"decision": decision, "reason": (reason or "")[:255]},
    )
    db.commit()
    db.refresh(r)
    return {
        "id": r.id,
        "status": r.status,
        "decided_by_user_id": r.approved_by,
        "decided_at": r.approved_at,
    }


# ===================== TEACHING COURSES (#35) =====================
def _teaching_dict(db: Session, t: TeachingCourse) -> dict:
    return {
        "id": t.id,
        "user_id": t.user_id,
        "user_name": hc.user_name(db, t.user_id),
        "course_name": t.course_name,
        "semester": t.semester,
        "year": t.year,
        "department_id": t.department_id,
        "department_name": hc.dept_name(db, t.department_id),
        "created_at": t.created_at,
    }


def list_teaching(
    db: Session,
    *,
    user: CurrentUser,
    user_id: Optional[uuid.UUID],
    year: Optional[int],
    semester: Optional[str],
    department_id: Optional[uuid.UUID],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    eff_user = user_id
    if not hc.is_research_all(user):
        eff_user = user.id
    if eff_user:
        conditions.append(TeachingCourse.user_id == eff_user)
    if year:
        conditions.append(TeachingCourse.year == year)
    if semester:
        conditions.append(TeachingCourse.semester == semester)
    if department_id:
        conditions.append(TeachingCourse.department_id == department_id)
    total = db.execute(
        select(func.count()).select_from(TeachingCourse).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(TeachingCourse)
        .where(*conditions)
        .order_by(TeachingCourse.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return [_teaching_dict(db, t) for t in rows], total


def create_teaching(
    db: Session,
    *,
    user: CurrentUser,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    target = payload.get("user_id")
    if not target:
        raise AppException("VALIDATION_ERROR", "Thiếu user_id", 400)
    if user.role == "staff" and target != user.id:
        raise hc.forbidden("Bạn chỉ khai môn giảng dạy của chính mình")
    hc.assert_user_exists(db, target)
    if not payload.get("course_name"):
        raise AppException("VALIDATION_ERROR", "Thiếu course_name", 400)
    if not payload.get("semester"):
        raise AppException("VALIDATION_ERROR", "Thiếu semester", 400)
    year = payload.get("year")
    if year is None or not (1900 <= int(year) <= date.today().year + 1):
        raise AppException("VALIDATION_ERROR", "year ngoài khoảng hợp lệ", 400)
    t = TeachingCourse(
        user_id=target,
        course_name=str(payload["course_name"]).strip(),
        semester=payload.get("semester"),
        year=year,
        department_id=hc.user_dept(db, target),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(t)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppException("DUPLICATE_COURSE", "Trùng môn (user+môn+kỳ+năm)", 409)
    audit_service.log_action(
        db,
        action="TEACHING_COURSE_CREATE",
        resource="teaching_course",
        user_id=user.id,
        resource_id=t.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"year": year},
    )
    db.commit()
    db.refresh(t)
    return _teaching_dict(db, t)


def update_teaching(
    db: Session,
    *,
    user: CurrentUser,
    tid: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    t = db.get(TeachingCourse, tid)
    if t is None:
        raise AppException("TEACHING_COURSE_NOT_FOUND", "Môn học không tồn tại", 404)
    if not hc.is_research_all(user) and t.user_id != user.id:
        raise hc.forbidden("Bạn chỉ sửa môn giảng dạy của chính mình")
    if not changes:
        raise AppException("VALIDATION_ERROR", "Body rỗng", 400)
    for field in ("course_name", "semester", "year"):
        if field in changes:
            setattr(t, field, changes[field])
    t.updated_by = user.id
    t.updated_at = func.now()
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppException("DUPLICATE_COURSE", "Trùng môn (user+môn+kỳ+năm)", 409)
    audit_service.log_action(
        db,
        action="TEACHING_COURSE_UPDATE",
        resource="teaching_course",
        user_id=user.id,
        resource_id=t.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"changed_fields": list(changes.keys())},
    )
    db.commit()
    db.refresh(t)
    return _teaching_dict(db, t)


def delete_teaching(
    db: Session,
    *,
    user: CurrentUser,
    tid: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> None:
    t = db.get(TeachingCourse, tid)
    if t is None:
        raise AppException("TEACHING_COURSE_NOT_FOUND", "Môn học không tồn tại", 404)
    if not hc.is_research_all(user) and t.user_id != user.id:
        raise hc.forbidden("Bạn chỉ xóa môn giảng dạy của chính mình")
    db.delete(t)
    audit_service.log_action(
        db,
        action="TEACHING_COURSE_DELETE",
        resource="teaching_course",
        user_id=user.id,
        resource_id=tid,
        correlation_id=correlation_id,
        ip=ip,
        detail={"op": "delete"},
    )
    db.commit()


# ===================== COMMUNITY SERVICES (#36) =====================
def _community_dict(db: Session, c: CommunityService) -> dict:
    return {
        "id": c.id,
        "content": c.content,
        "performed_at": c.performed_at.isoformat() if c.performed_at else None,
        "host": c.host,
        "performer_user_id": c.performer_user_id,
        "performer_name": hc.user_name(db, c.performer_user_id),
        "department_id": c.department_id,
        "department_name": hc.dept_name(db, c.department_id),
        "created_at": c.created_at,
    }


def list_community(
    db: Session,
    *,
    user: CurrentUser,
    performer_user_id: Optional[uuid.UUID],
    year: Optional[int],
    date_from: Optional[date],
    date_to: Optional[date],
    department_id: Optional[uuid.UUID],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    eff_perf = performer_user_id
    if not hc.is_research_all(user):
        eff_perf = user.id
    if eff_perf:
        conditions.append(CommunityService.performer_user_id == eff_perf)
    if year:
        conditions.append(func.extract("year", CommunityService.performed_at) == year)
    if date_from:
        conditions.append(CommunityService.performed_at >= date_from)
    if date_to:
        conditions.append(CommunityService.performed_at <= date_to)
    if department_id:
        conditions.append(CommunityService.department_id == department_id)
    total = db.execute(
        select(func.count()).select_from(CommunityService).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(CommunityService)
        .where(*conditions)
        .order_by(CommunityService.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return [_community_dict(db, c) for c in rows], total


def create_community(
    db: Session,
    *,
    user: CurrentUser,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    performer = payload.get("performer_user_id")
    if not performer:
        raise AppException("VALIDATION_ERROR", "Thiếu performer_user_id", 400)
    if user.role == "staff" and performer != user.id:
        raise hc.forbidden("Bạn chỉ khai hoạt động của chính mình")
    hc.assert_user_exists(db, performer)
    if not payload.get("content"):
        raise AppException("VALIDATION_ERROR", "Thiếu content", 400)
    if not payload.get("performed_at"):
        raise AppException("VALIDATION_ERROR", "Thiếu performed_at", 400)
    c = CommunityService(
        content=str(payload["content"]).strip(),
        performed_at=payload.get("performed_at"),
        host=payload.get("host"),
        performer_user_id=performer,
        department_id=hc.user_dept(db, performer),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(c)
    db.flush()
    audit_service.log_action(
        db,
        action="COMMUNITY_SERVICE_CREATE",
        resource="community_service",
        user_id=user.id,
        resource_id=c.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"performer_user_id": str(performer)},
    )
    db.commit()
    db.refresh(c)
    return _community_dict(db, c)


def update_community(
    db: Session,
    *,
    user: CurrentUser,
    cid: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    c = db.get(CommunityService, cid)
    if c is None:
        raise AppException("COMMUNITY_SERVICE_NOT_FOUND", "Hoạt động không tồn tại", 404)
    if not hc.is_research_all(user) and c.performer_user_id != user.id:
        raise hc.forbidden("Bạn chỉ sửa hoạt động của chính mình")
    if not changes:
        raise AppException("VALIDATION_ERROR", "Body rỗng", 400)
    for field in ("content", "performed_at", "host"):
        if field in changes:
            setattr(c, field, changes[field])
    c.updated_by = user.id
    c.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="COMMUNITY_SERVICE_UPDATE",
        resource="community_service",
        user_id=user.id,
        resource_id=c.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"changed_fields": list(changes.keys())},
    )
    db.commit()
    db.refresh(c)
    return _community_dict(db, c)


def delete_community(
    db: Session,
    *,
    user: CurrentUser,
    cid: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> None:
    c = db.get(CommunityService, cid)
    if c is None:
        raise AppException("COMMUNITY_SERVICE_NOT_FOUND", "Hoạt động không tồn tại", 404)
    if not hc.is_research_all(user) and c.performer_user_id != user.id:
        raise hc.forbidden("Bạn chỉ xóa hoạt động của chính mình")
    db.delete(c)
    audit_service.log_action(
        db,
        action="COMMUNITY_SERVICE_DELETE",
        resource="community_service",
        user_id=user.id,
        resource_id=cid,
        correlation_id=correlation_id,
        ip=ip,
        detail={"op": "delete"},
    )
    db.commit()


# ===================== COMPETENCE SUMMARY (#15) =====================
def competence_summary(db: Session, *, user: CurrentUser, target_user_id: uuid.UUID) -> dict:
    from app.models.hr import Competence, HrProfile

    if user.role == "accountant":
        raise hc.forbidden("Kế toán không quản lý hồ sơ năng lực")
    if user.role == "staff" and user.id != target_user_id:
        raise hc.forbidden("Bạn chỉ xem hồ sơ năng lực của chính mình")
    p = db.get(HrProfile, target_user_id)
    if p is None:
        raise AppException("PROFILE_NOT_FOUND", "Hồ sơ nhân sự không tồn tại", 404)
    u = db.get(User, target_user_id)
    comps = db.execute(
        select(Competence).where(Competence.user_id == target_user_id)
    ).scalars().all()

    def _is_expired(c):
        return bool(c.expiry_date and c.expiry_date < date.today())

    degrees = [
        {
            "title": c.title,
            "issuer": c.issuer,
            "issued_date": c.issued_date.isoformat() if c.issued_date else None,
        }
        for c in comps
        if c.kind == "degree"
    ]
    certificates = [
        {
            "title": c.title,
            "expiry_date": c.expiry_date.isoformat() if c.expiry_date else None,
            "is_expired": _is_expired(c),
        }
        for c in comps
        if c.kind == "certificate"
    ]
    authorizations = [
        {
            "title": c.title,
            "scope_detail": c.scope_detail,
            "expiry_date": c.expiry_date.isoformat() if c.expiry_date else None,
            "is_expired": _is_expired(c),
        }
        for c in comps
        if c.kind == "authorization"
    ]
    rsum = _research_counts_for_user(db, target_user_id)
    return {
        "user_id": target_user_id,
        "full_name": u.full_name if u else None,
        "department_name": hc.dept_name(db, u.department_id) if u else None,
        "job_title": p.job_title,
        "degrees": degrees,
        "certificates": certificates,
        "authorizations": authorizations,
        "research_summary": rsum,
    }


def _research_counts_for_user(db: Session, user_id: uuid.UUID) -> dict:
    projects = db.execute(
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.user_id == user_id)
    ).scalar_one()
    pub_ids = select(PublicationAuthor.publication_id).where(
        PublicationAuthor.user_id == user_id
    )
    publications = db.execute(
        select(func.count())
        .select_from(Publication)
        .where(Publication.id.in_(pub_ids), Publication.type == "paper")
    ).scalar_one()
    patents = db.execute(
        select(func.count())
        .select_from(Publication)
        .where(Publication.id.in_(pub_ids), Publication.type == "patent")
    ).scalar_one()
    mentorships = db.execute(
        select(func.count())
        .select_from(StudentMentorship)
        .where(StudentMentorship.mentor_id == user_id)
    ).scalar_one()
    return {
        "projects": projects,
        "publications": publications,
        "patents": patents,
        "mentorships": mentorships,
    }


# ===================== STATS (#37) =====================
def achievement_stats(
    db: Session,
    *,
    user: CurrentUser,
    group_by: str,
    user_id: Optional[uuid.UUID],
    department_id: Optional[uuid.UUID],
    date_from: Optional[date],
    date_to: Optional[date],
    level: Optional[str],
    category: Optional[str],
) -> dict:
    if group_by not in ("individual", "department"):
        raise AppException("VALIDATION_ERROR", "group_by phải là individual|department", 400)
    if date_from and date_to and date_from > date_to:
        raise AppException("INVALID_DATE_RANGE", "from > to", 400)

    # Staff scope own: ép về dữ liệu chính mình
    if not hc.is_research_all(user):
        group_by = "individual"
        user_id = user.id
        department_id = None

    if group_by == "individual" and user_id is None:
        raise AppException("VALIDATION_ERROR", "Thiếu user_id (group_by=individual)", 400)
    if group_by == "department" and department_id is None:
        raise AppException(
            "VALIDATION_ERROR", "Thiếu department_id (group_by=department)", 400
        )

    def _project_scope():
        if group_by == "individual":
            ids = select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)
            return ResearchProject.id.in_(ids)
        return ResearchProject.department_id == department_id

    def _pub_scope():
        if group_by == "individual":
            ids = select(PublicationAuthor.publication_id).where(
                PublicationAuthor.user_id == user_id
            )
            return Publication.id.in_(ids)
        return Publication.department_id == department_id

    proj_cond = [_project_scope()]
    if level:
        proj_cond.append(ResearchProject.level == level)
    if date_from:
        proj_cond.append(
            or_(ResearchProject.end_date.is_(None), ResearchProject.end_date >= date_from)
        )
    if date_to:
        proj_cond.append(
            or_(
                ResearchProject.start_date.is_(None),
                ResearchProject.start_date <= date_to,
            )
        )

    projects_total = db.execute(
        select(func.count()).select_from(ResearchProject).where(*proj_cond)
    ).scalar_one()
    by_level_rows = db.execute(
        select(ResearchProject.level, func.count())
        .where(*proj_cond)
        .group_by(ResearchProject.level)
    ).all()
    by_level = {(lv or "unknown"): cnt for lv, cnt in by_level_rows}

    pub_cond = [_pub_scope()]
    if category:
        pub_cond.append(Publication.category == category)
    if date_from:
        pub_cond.append(
            or_(Publication.year.is_(None), Publication.year >= date_from.year)
        )
    if date_to:
        pub_cond.append(or_(Publication.year.is_(None), Publication.year <= date_to.year))

    papers_total = db.execute(
        select(func.count())
        .select_from(Publication)
        .where(*pub_cond, Publication.type == "paper")
    ).scalar_one()
    patents_total = db.execute(
        select(func.count())
        .select_from(Publication)
        .where(*pub_cond, Publication.type == "patent")
    ).scalar_one()
    by_index_rows = db.execute(
        select(Publication.category, func.count())
        .where(*pub_cond, Publication.type == "paper")
        .group_by(Publication.category)
    ).all()
    by_index = {(c or "unknown"): cnt for c, cnt in by_index_rows}

    # mentorships / teaching / community / lab (chỉ approved)
    if group_by == "individual":
        ment_cond = [StudentMentorship.mentor_id == user_id]
        teach_cond = [TeachingCourse.user_id == user_id]
        comm_cond = [CommunityService.performer_user_id == user_id]
        lab_cond = [LabRegistration.mentor_id == user_id, LabRegistration.status == "approved"]
    else:
        ment_cond = [StudentMentorship.department_id == department_id]
        teach_cond = [TeachingCourse.department_id == department_id]
        comm_cond = [CommunityService.department_id == department_id]
        lab_cond = [
            LabRegistration.department_id == department_id,
            LabRegistration.status == "approved",
        ]
    if date_from:
        comm_cond.append(CommunityService.performed_at >= date_from)
    if date_to:
        comm_cond.append(CommunityService.performed_at <= date_to)

    mentorships = db.execute(
        select(func.count()).select_from(StudentMentorship).where(*ment_cond)
    ).scalar_one()
    teaching = db.execute(
        select(func.count()).select_from(TeachingCourse).where(*teach_cond)
    ).scalar_one()
    community = db.execute(
        select(func.count()).select_from(CommunityService).where(*comm_cond)
    ).scalar_one()
    lab_approved = db.execute(
        select(func.count()).select_from(LabRegistration).where(*lab_cond)
    ).scalar_one()

    result = {
        "group_by": group_by,
        "period": {
            "from": date_from.isoformat() if date_from else None,
            "to": date_to.isoformat() if date_to else None,
        },
        "projects": {"total": projects_total, "by_level": by_level},
        "publications": {"total": papers_total, "by_index": by_index},
        "patents": patents_total,
        "mentorships": mentorships,
        "lab_registrations_approved": lab_approved,
        "teaching_courses": teaching,
        "community_services": community,
    }
    if group_by == "individual":
        result["user_id"] = user_id
        result["user_name"] = hc.user_name(db, user_id)
    else:
        result["department_id"] = department_id
        result["department_name"] = hc.dept_name(db, department_id)
    return result
