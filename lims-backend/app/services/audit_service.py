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
    """Lọc field nhạy cảm khỏi detail trước khi ghi.

    Khoá được ép về `str`: JSONB không có khái niệm khoá số (json.dumps cũng ép),
    và bản cũ gọi thẳng `key.lower()` nên **ném AttributeError với khoá số**. Sự cố
    thật (2026-08-07): `by_milestone = {7: 0, 3: 0, 0: 0}` trong 3 cron nhắc hạn làm
    CRON-7 capa-due và CRON-8 risk-review-due HỎNG mỗi lần chạy (mất luôn notification
    trong lô đó vì db.commit() không tới), còn CRON-5 calibration-due thì "ok" nhưng
    dòng audit im lặng biến mất — 0 dòng CRON_CALIBRATION_REMINDER trong production.

    Bài học: ghi nhật ký là mối quan tâm cắt ngang, nó KHÔNG được phép làm đổ vỡ
    nghiệp vụ mà nó đang ghi lại. Hàm này phải chịu được mọi dict caller đưa vào.
    """
    if not detail:
        return None
    clean: dict[str, Any] = {}
    for key, value in detail.items():
        skey = key if isinstance(key, str) else str(key)
        if skey.lower() in _SENSITIVE_KEYS:
            clean[skey] = "***"
        elif isinstance(value, dict):
            clean[skey] = _sanitize(value)
        else:
            clean[skey] = value
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
