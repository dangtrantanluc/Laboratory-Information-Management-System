"""M10 cron service — CRON-8 nhắc đánh giá lại rủi ro (mốc 30/15/7 ngày) (§8.5).

Idempotent qua risk_notification_dedup (UNIQUE risk×milestone×fire_date) + IntegrityError.
Redis lock chống chạy chồng (giống CRON-5/CRON-7). Quét risks status≠closed & next_review_date
≠ NULL: days_left ∈ {30,15,7} → nhắc owner. In-app only (C02).
"""
import logging
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.core.redis_client import get_redis
from app.models.risk import Risk, RiskNotificationDedup
from app.services import audit_service, notification_service

logger = logging.getLogger("lims.risk.cron")

_LOCK_TTL = 300
_MILESTONES = (30, 15, 7)
_LOCK_KEY = "cron:lock:risk-review-due"


def _acquire_lock(key: str) -> bool:
    return bool(get_redis().set(key, "1", nx=True, ex=_LOCK_TTL))


def _release_lock(key: str) -> None:
    try:
        get_redis().delete(key)
    except Exception:  # noqa: BLE001
        pass


def run_risk_review_due(
    db: Session, *, actor: Optional[CurrentUser] = None, as_of_date: Optional[date] = None
) -> dict:
    """CRON-8 — quét rủi ro tới hạn đánh giá lại, nhắc in-app owner idempotent."""
    if not _acquire_lock(_LOCK_KEY):
        raise AppException("CRON_ALREADY_RUNNING", "CRON-8 đang chạy", 409)

    now = datetime.now(timezone.utc)
    today = as_of_date or now.date()
    scanned = 0
    notifications_created = 0
    deduped = 0
    by_milestone = {30: 0, 15: 0, 7: 0}

    try:
        risks = db.execute(
            select(Risk).where(
                Risk.status != "closed", Risk.next_review_date.is_not(None)
            )
        ).scalars().all()

        for r in risks:
            scanned += 1
            days_left = (r.next_review_date - today).days
            if days_left not in _MILESTONES:
                continue

            dedup = RiskNotificationDedup(
                risk_id=r.id, kind="RISK_REVIEW_DUE", milestone_days=days_left, fire_date=today
            )
            db.add(dedup)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                deduped += 1
                continue

            notification_service.create_notification(
                db, user_id=r.owner_id, type="RISK_REVIEW_DUE",
                title=f"Rủi ro {r.risk_code} tới hạn đánh giá lại",
                body=f"{r.title} — đánh giá lại vào {r.next_review_date.isoformat()} (còn {days_left} ngày)",
                ref_type="risk", ref_id=r.id,
            )
            notifications_created += 1
            by_milestone[days_left] += 1
            db.flush()

        db.commit()
    finally:
        _release_lock(_LOCK_KEY)

    try:
        audit_service.log_action(
            db, action="CRON_RISK_REVIEW_REMINDER", resource="risk_cron",
            user_id=actor.id if actor else None, correlation_id=None,
            detail={"scanned": scanned, "created": notifications_created, "by_milestone": by_milestone},
        )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()

    logger.info(
        "CRON-8 risk-review-due done",
        extra={"scanned": scanned, "notif_created": notifications_created, "deduped": deduped},
    )
    return {
        "run_at": now,
        "as_of_date": today,
        "scanned_risks": scanned,
        "notifications_created": notifications_created,
        "by_milestone": {str(k): v for k, v in by_milestone.items()},
        "deduped": deduped,
    }
