"""Giảng dạy (#35).

Tách từ research_service.py (1.736 dòng, 9 domain) — M-03/T1.1.
Xem app/services/research/__init__.py để biết vì sao có mặt tiền tương thích.
"""
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.hr import (
    TeachingCourse,
)
from app.services import audit_service, hr_common as hc


def _teaching_dict(db: Session, t: TeachingCourse) -> dict:
    return {
        "id": t.id,
        "user_id": t.user_id,
        "user_name": hc.user_name(db, t.user_id) or t.lecturer_external_name,
        "lecturer_external_name": t.lecturer_external_name,
        "course_name": t.course_name,
        "semester": t.semester,
        "year": t.year,
        "academic_year": t.academic_year,
        "hk1_theory_hours": t.hk1_theory_hours,
        "hk1_practice_hours": t.hk1_practice_hours,
        "hk2_theory_hours": t.hk2_theory_hours,
        "hk2_practice_hours": t.hk2_practice_hours,
        "note": t.note,
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
        academic_year=payload.get("academic_year"),
        hk1_theory_hours=payload.get("hk1_theory_hours"),
        hk1_practice_hours=payload.get("hk1_practice_hours"),
        hk2_theory_hours=payload.get("hk2_theory_hours"),
        hk2_practice_hours=payload.get("hk2_practice_hours"),
        note=payload.get("note"),
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
