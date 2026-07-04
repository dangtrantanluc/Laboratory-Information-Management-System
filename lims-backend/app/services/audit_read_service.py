"""Audit read service — tra cứu audit_logs (M7.4, #28/#29). CHỈ đọc (append-only)."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import not_found, validation_error
from app.models.audit_log import AuditLog
from app.models.user import User


def _serialize(db: Session, log: AuditLog) -> dict:
    user_name = None
    if log.user_id:
        user = db.get(User, log.user_id)
        user_name = user.full_name if user else None
    return {
        "id": log.id,
        "user_id": log.user_id,
        "user_name": user_name,
        "action": log.action,
        "resource": log.resource,
        "resource_id": log.resource_id,
        "correlation_id": log.correlation_id,
        "ip": str(log.ip) if log.ip else None,
        "at": log.at,
        "detail": log.detail,
    }


def list_audit_logs(
    db: Session,
    *,
    user_id: Optional[uuid.UUID],
    action: Optional[str],
    resource: Optional[str],
    resource_id: Optional[uuid.UUID],
    correlation_id: Optional[str],
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    ip: Optional[str],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    if date_from and date_to and date_from > date_to:
        raise validation_error("date_from phải nhỏ hơn hoặc bằng date_to")

    conditions = []
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if action:
        conditions.append(AuditLog.action == action)
    if resource:
        conditions.append(AuditLog.resource == resource)
    if resource_id:
        conditions.append(AuditLog.resource_id == resource_id)
    if correlation_id:
        conditions.append(AuditLog.correlation_id == correlation_id)
    if date_from:
        conditions.append(AuditLog.at >= date_from)
    if date_to:
        conditions.append(AuditLog.at <= date_to)
    if ip:
        conditions.append(AuditLog.ip == ip)

    total = db.execute(
        select(func.count()).select_from(AuditLog).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(AuditLog)
        .where(*conditions)
        .order_by(AuditLog.at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return [_serialize(db, r) for r in rows], total


def get_audit_log(db: Session, audit_id: uuid.UUID) -> dict:
    log = db.get(AuditLog, audit_id)
    if log is None:
        raise not_found("Không tìm thấy bản ghi audit")
    return _serialize(db, log)
