"""Audit service — ghi audit_logs dùng chung cho mọi thao tác CUD (M7.4, 17025 §8.4).

APPEND-ONLY: chỉ INSERT. Lọc sensitive khỏi detail (D6, logging.md).
Dùng chung cho M1/M2/M3... — interface ổn định.
"""
import logging
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

logger = logging.getLogger("lims.audit")

# Field nhạy cảm bị loại khỏi detail trước khi ghi (D6)
_SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "new_password",
    "current_password",
    "old_password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "authorization",
    "jwt_secret",
}


def _sanitize(detail: Optional[dict]) -> Optional[dict]:
    if not detail:
        return None
    clean: dict[str, Any] = {}
    for key, value in detail.items():
        if key.lower() in _SENSITIVE_KEYS:
            clean[key] = "***"
        elif isinstance(value, dict):
            clean[key] = _sanitize(value)
        else:
            clean[key] = value
    return clean


def log_action(
    db: Session,
    *,
    action: str,
    resource: str,
    user_id: Optional[uuid.UUID] = None,
    resource_id: Optional[uuid.UUID] = None,
    correlation_id: Optional[str] = None,
    ip: Optional[str] = None,
    detail: Optional[dict] = None,
) -> AuditLog:
    """Ghi 1 bản ghi audit. KHÔNG commit (để caller kiểm soát transaction);
    flush để có id ngay. Caller phải commit sau."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        correlation_id=correlation_id,
        ip=ip,
        detail=_sanitize(detail),
    )
    db.add(entry)
    db.flush()
    logger.info(
        "audit",
        extra={
            "correlationId": correlation_id,
            "action": action,
            "resource": resource,
            "resourceId": str(resource_id) if resource_id else None,
            "userId": str(user_id) if user_id else None,
        },
    )
    return entry
