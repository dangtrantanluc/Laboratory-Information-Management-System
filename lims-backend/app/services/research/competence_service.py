"""Hồ sơ năng lực tổng hợp (#15).

Tách từ research_service.py (1.736 dòng, 9 domain) — M-03/T1.1.
Xem app/services/research/__init__.py để biết vì sao có mặt tiền tương thích.
"""
import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.research import ProjectMember, Publication, PublicationAuthor, StudentMentorship
from app.models.user import User
from app.services import hr_common as hc


def competence_summary(db: Session, *, user: CurrentUser, target_user_id: uuid.UUID) -> dict:
    from app.models.hr import Competence, HrProfile

    if user.role == "office":
        raise hc.forbidden("Văn phòng không quản lý hồ sơ năng lực")
    if user.role == "staff" and user.id != target_user_id:
        raise hc.forbidden("Bạn chỉ xem hồ sơ năng lực của chính mình")
    p = db.get(HrProfile, target_user_id)
    if p is None:
        raise AppException(ErrorCode.PROFILE_NOT_FOUND, "Hồ sơ nhân sự không tồn tại", 404)
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
