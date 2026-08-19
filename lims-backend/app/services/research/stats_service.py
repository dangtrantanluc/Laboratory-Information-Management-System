"""Thống kê research (#37).

Tách từ research_service.py (1.736 dòng, 9 domain) — M-03/T1.1.
Xem app/services/research/__init__.py để biết vì sao có mặt tiền tương thích.
"""
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.research import (
    CommunityService,
    LabRegistration,
    ProjectMember,
    Publication,
    PublicationAuthor,
    ResearchProject,
    StudentMentorship,
    TeachingCourse,
)
from app.services import hr_common as hc


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
        raise AppException(ErrorCode.VALIDATION_ERROR, "group_by phải là individual|department", 400)
    if date_from and date_to and date_from > date_to:
        raise AppException(ErrorCode.INVALID_DATE_RANGE, "from > to", 400)

    # Staff scope own: ép về dữ liệu chính mình
    if not hc.is_research_all(user):
        group_by = "individual"
        user_id = user.id
        department_id = None

    if group_by == "individual" and user_id is None:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu user_id (group_by=individual)", 400)
    if group_by == "department" and department_id is None:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, "Thiếu department_id (group_by=department)", 400
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
