"""Hướng dẫn sinh viên (#30-#32).

Tách từ research_service.py (1.736 dòng, 9 domain) — M-03/T1.1.
Xem app/services/research/__init__.py để biết vì sao có mặt tiền tương thích.
"""
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db_helpers import get_or_404
from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.research import MentorshipType, StudentMentorship
from app.services import audit_service, hr_common as hc


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
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu mentor_id", 400)
    if user.role == "staff" and mentor_id != user.id:
        raise hc.forbidden("Bạn chỉ khai hướng dẫn của chính mình")
    hc.assert_user_exists(db, mentor_id)
    if not payload.get("student_name"):
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu student_name", 400)
    year = payload.get("year")
    if year is None or not (1900 <= int(year) <= date.today().year + 1):
        raise AppException(ErrorCode.VALIDATION_ERROR, "year ngoài khoảng hợp lệ", 400)
    mtype = payload.get("type")
    if not mtype or db.get(MentorshipType, mtype) is None:
        raise AppException(ErrorCode.INVALID_MENTORSHIP_TYPE, "Loại hướng dẫn ngoài danh mục", 400)
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
    return get_or_404(db, StudentMentorship, mid, "Bản ghi hướng dẫn không tồn tại", code=ErrorCode.MENTORSHIP_NOT_FOUND)


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
        raise AppException(ErrorCode.VALIDATION_ERROR, "Body rỗng", 400)
    if "type" in changes and changes["type"]:
        if db.get(MentorshipType, changes["type"]) is None:
            raise AppException(
                ErrorCode.INVALID_MENTORSHIP_TYPE, "Loại hướng dẫn ngoài danh mục", 400
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
