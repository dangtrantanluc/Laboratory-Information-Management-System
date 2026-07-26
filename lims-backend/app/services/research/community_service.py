"""Phục vụ cộng đồng (#36).

Tách từ research_service.py (1.736 dòng, 9 domain) — M-03/T1.1.
Xem app/services/research/__init__.py để biết vì sao có mặt tiền tương thích.
"""
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.hr import (
    CommunityService,
)
from app.services import audit_service, hr_common as hc


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
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu performer_user_id", 400)
    if user.role == "staff" and performer != user.id:
        raise hc.forbidden("Bạn chỉ khai hoạt động của chính mình")
    hc.assert_user_exists(db, performer)
    if not payload.get("content"):
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu content", 400)
    if not payload.get("performed_at"):
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu performed_at", 400)
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
        raise AppException(ErrorCode.COMMUNITY_SERVICE_NOT_FOUND, "Hoạt động không tồn tại", 404)
    if not hc.is_research_all(user) and c.performer_user_id != user.id:
        raise hc.forbidden("Bạn chỉ sửa hoạt động của chính mình")
    if not changes:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Body rỗng", 400)
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
        raise AppException(ErrorCode.COMMUNITY_SERVICE_NOT_FOUND, "Hoạt động không tồn tại", 404)
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
