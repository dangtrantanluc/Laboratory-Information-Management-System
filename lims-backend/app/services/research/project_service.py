"""Đề tài NCKH (#17-#22) — CRUD + thành viên n-n.

Tách từ research_service.py (1.736 dòng, 9 domain) — M-03/T1.1.
Xem app/services/research/__init__.py để biết vì sao có mặt tiền tương thích.
"""
import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db_helpers import get_or_404
from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.hr import (
    ProjectMember,
    ResearchProject,
    ResearchProjectLevel,
)
from app.services import audit_service, hr_common as hc
from app.services.research._shared import _assert_staff_in_members, _validate_members


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
        # Chủ nhiệm: tên user nội bộ HOẶC tên ngoài HT (lead_external_name).
        "lead_user_name": hc.user_name(db, p.lead_user_id) or p.lead_external_name,
        "lead_external_name": p.lead_external_name,
        "department_id": p.department_id,
        "department_name": hc.dept_name(db, p.department_id),
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "end_date": p.end_date.isoformat() if p.end_date else None,
        "academic_year": p.academic_year,
        "budget_amount": str(p.budget_amount) if p.budget_amount is not None else None,
        "budget_currency": p.budget_currency,
        "is_transferred": p.is_transferred,
        "transfer_product": p.transfer_product,
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
                "name": hc.user_name(db, m.user_id) or m.external_name,
                "external_name": m.external_name,
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
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu title", 400)
    level = payload.get("level")
    if not level or db.get(ResearchProjectLevel, level) is None:
        raise AppException(ErrorCode.INVALID_PROJECT_LEVEL, "Cấp đề tài ngoài danh mục", 400)
    lead_user_id = payload.get("lead_user_id")
    if not lead_user_id:
        raise AppException(ErrorCode.LEAD_REQUIRED, "Thiếu chủ nhiệm (lead_user_id)", 400)
    members = payload.get("members") or []
    internal_users = _validate_members(
        db, members, allow_external=False, lead_user_id=lead_user_id
    )
    _assert_staff_in_members(user, internal_users, "thành viên")

    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    if start_date and end_date and end_date < start_date:
        raise AppException(ErrorCode.INVALID_DATE_ORDER, "end_date < start_date", 422)

    department_id = payload.get("department_id")
    if department_id is None:
        department_id = hc.user_dept(db, lead_user_id)

    budget = hc.parse_decimal(payload.get("budget_amount"), field="budget_amount", positive=False)
    p = ResearchProject(
        code=payload.get("code"),
        title=str(title).strip(),
        level=level,
        lead_user_id=lead_user_id,
        department_id=department_id,
        start_date=start_date,
        end_date=end_date,
        academic_year=payload.get("academic_year"),
        budget_amount=budget,
        budget_currency=payload.get("budget_currency") or "VND",
        is_transferred=bool(payload.get("is_transferred")),
        transfer_product=payload.get("transfer_product"),
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
    return get_or_404(db, ResearchProject, project_id, "Đề tài không tồn tại", code=ErrorCode.PROJECT_NOT_FOUND)


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
        raise AppException(ErrorCode.VALIDATION_ERROR, "Body rỗng", 400)
    if "level" in changes and changes["level"] is not None:
        if db.get(ResearchProjectLevel, changes["level"]) is None:
            raise AppException(ErrorCode.INVALID_PROJECT_LEVEL, "Cấp đề tài ngoài danh mục", 400)
    if "lead_user_id" in changes and changes["lead_user_id"]:
        member = db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == p.id,
                ProjectMember.user_id == changes["lead_user_id"],
            )
        ).scalar_one_or_none()
        if member is None:
            raise AppException(
                ErrorCode.LEAD_REQUIRED, "Chủ nhiệm mới phải là thành viên đề tài", 400
            )
    new_start = changes.get("start_date", p.start_date)
    new_end = changes.get("end_date", p.end_date)
    if new_start and new_end and new_end < new_start:
        raise AppException(ErrorCode.INVALID_DATE_ORDER, "end_date < start_date", 422)
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
