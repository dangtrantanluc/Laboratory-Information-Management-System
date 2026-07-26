"""Service Thẻ vào PTN (sinh viên) — M19.

Danh sách quản trị (CRUD, không qua duyệt) do Văn phòng quản lý — đối chiếu
theo file "DANH SÁCH SINH VIÊN ĐÃ ĐƯỢC CẤP THẺ VÀO PTN".
"""
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found
from app.models.lab_access import LabAccessCard
from app.services import audit_service


def _serialize(c: LabAccessCard) -> dict:
    return {
        "id": c.id,
        "student_name": c.student_name,
        "class_name": c.class_name,
        "student_code": c.student_code,
        "email": c.email,
        "room": c.room,
        "purpose": c.purpose,
        "supervisor_name": c.supervisor_name,
        "valid_from": c.valid_from,
        "valid_to": c.valid_to,
        "note": c.note,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


def _check_period(valid_from: Optional[date], valid_to: Optional[date]) -> None:
    if valid_from and valid_to and valid_to < valid_from:
        raise AppException(ErrorCode.INVALID_PERIOD, "Thời gian đến phải sau thời gian từ", 422)


def list_cards(
    db: Session,
    *,
    q: Optional[str],
    supervisor_name: Optional[str],
    room: Optional[str],
    active_on: Optional[date],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conds = []
    if q:
        like = f"%{q.strip()}%"
        conds.append(
            or_(
                LabAccessCard.student_name.ilike(like),
                LabAccessCard.student_code.ilike(like),
                LabAccessCard.class_name.ilike(like),
                LabAccessCard.email.ilike(like),
            )
        )
    if supervisor_name:
        conds.append(LabAccessCard.supervisor_name.ilike(f"%{supervisor_name.strip()}%"))
    if room:
        conds.append(LabAccessCard.room.ilike(f"%{room.strip()}%"))
    if active_on:
        conds.append(LabAccessCard.valid_from <= active_on)
        conds.append(
            or_(LabAccessCard.valid_to.is_(None), LabAccessCard.valid_to >= active_on)
        )
    total = db.execute(
        select(func.count()).select_from(LabAccessCard).where(*conds)
    ).scalar_one()
    rows = db.execute(
        select(LabAccessCard)
        .where(*conds)
        .order_by(LabAccessCard.valid_from.desc(), LabAccessCard.student_name)
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return [_serialize(c) for c in rows], total


def create_card(
    db: Session,
    *,
    user: CurrentUser,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    _check_period(payload.get("valid_from"), payload.get("valid_to"))
    c = LabAccessCard(**payload, created_by=user.id, updated_by=user.id)
    db.add(c)
    db.flush()
    audit_service.log_action(
        db, action="LAB_ACCESS_CARD_CREATE", resource="lab_access_card",
        user_id=user.id, resource_id=c.id, correlation_id=correlation_id, ip=ip,
        detail={"student_code": c.student_code},
    )
    db.commit()
    db.refresh(c)
    return _serialize(c)


def update_card(
    db: Session,
    *,
    user: CurrentUser,
    card_id: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    c = db.get(LabAccessCard, card_id)
    if c is None:
        raise not_found("Không tìm thấy bản ghi thẻ vào PTN")
    _check_period(
        changes.get("valid_from", c.valid_from), changes.get("valid_to", c.valid_to)
    )
    for k, v in changes.items():
        setattr(c, k, v)
    c.updated_by = user.id
    audit_service.log_action(
        db, action="LAB_ACCESS_CARD_UPDATE", resource="lab_access_card",
        user_id=user.id, resource_id=c.id, correlation_id=correlation_id, ip=ip,
        detail=changes,
    )
    db.commit()
    db.refresh(c)
    return _serialize(c)


def delete_card(
    db: Session,
    *,
    user: CurrentUser,
    card_id: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> None:
    c = db.get(LabAccessCard, card_id)
    if c is None:
        raise not_found("Không tìm thấy bản ghi thẻ vào PTN")
    db.delete(c)
    audit_service.log_action(
        db, action="LAB_ACCESS_CARD_DELETE", resource="lab_access_card",
        user_id=user.id, resource_id=card_id, correlation_id=correlation_id, ip=ip,
        detail={"op": "delete"},
    )
    db.commit()
