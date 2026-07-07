"""M8 cron service — CRON-7 nhắc CAPA tới/quá hạn (mốc 7/3/0 ngày) (§8.7).

Idempotent qua capa_notification_dedup (UNIQUE capa×milestone×fire_date) + IntegrityError.
Redis lock chống chạy chồng (giống CRON-5 M5). Quét capa status='in_progress' & due_date
≠ NULL: days_left ∈ {7,3} → nhắc trước; days_left ≤ 0 → mốc 0 (quá hạn, nhắc mỗi ngày,
dedup theo fire_date). Nhận: owner CAPA. In-app only (C02).
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
from app.models.nonconformity import Capa, CapaNotificationDedup, Nonconformity
from app.services import audit_service, notification_service

logger = logging.getLogger("lims.nc.cron")

_LOCK_TTL = 300
_LOCK_KEY = "cron:lock:capa-due"


def _acquire_lock(key: str) -> bool:
    return bool(get_redis().set(key, "1", nx=True, ex=_LOCK_TTL))


def _release_lock(key: str) -> None:
    try:
        get_redis().delete(key)
    except Exception:  # noqa: BLE001
        pass


def _milestone(days_left: int) -> Optional[int]:
    if days_left in (7, 3):
        return days_left
    if days_left <= 0:
        return 0
    return None


def run_capa_due(
    db: Session, *, actor: Optional[CurrentUser] = None, as_of_date: Optional[date] = None
) -> dict:
    """CRON-7 — quét CAPA đang mở tới/quá hạn, nhắc in-app owner idempotent."""
    if not _acquire_lock(_LOCK_KEY):
        raise AppException("CRON_ALREADY_RUNNING", "CRON-7 đang chạy", 409)

    now = datetime.now(timezone.utc)
    today = as_of_date or now.date()
    scanned = 0
    notifications_created = 0
    deduped = 0
    by_milestone = {7: 0, 3: 0, 0: 0}

    try:
        capas = db.execute(
            select(Capa).where(
                Capa.status == "in_progress", Capa.due_date.is_not(None)
            )
        ).scalars().all()

        for capa in capas:
            scanned += 1
            ms = _milestone((capa.due_date - today).days)
            if ms is None:
                continue

            dedup = CapaNotificationDedup(
                capa_id=capa.id, kind="CAPA_DUE", milestone_days=ms, fire_date=today
            )
            db.add(dedup)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                deduped += 1
                continue

            entity = db.get(Nonconformity, capa.nc_id)
            code = entity.nc_code if entity else "NC"
            overdue = ms == 0
            notification_service.create_notification(
                db,
                user_id=capa.owner_id,
                type="CAPA_DUE",
                title=(
                    f"CAPA {code} đã QUÁ HẠN" if overdue else f"CAPA {code} sắp tới hạn"
                ),
                body=(
                    f"Hạn xử lý: {capa.due_date.isoformat()}"
                    + ("" if overdue else f" (còn {ms} ngày)")
                ),
                ref_type="nonconformity",
                ref_id=capa.nc_id,
            )
            notifications_created += 1
            by_milestone[ms] += 1
            db.flush()

        db.commit()
    finally:
        _release_lock(_LOCK_KEY)

    try:
        audit_service.log_action(
            db,
            action="CRON_CAPA_REMINDER",
            resource="nc_cron",
            user_id=actor.id if actor else None,
            correlation_id=None,
            detail={"scanned": scanned, "created": notifications_created, "by_milestone": by_milestone},
        )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()

    logger.info(
        "CRON-7 capa-due done",
        extra={"scanned": scanned, "notif_created": notifications_created, "deduped": deduped},
    )
    return {
        "run_at": now,
        "as_of_date": today,
        "scanned_capa": scanned,
        "notifications_created": notifications_created,
        "by_milestone": {str(k): v for k, v in by_milestone.items()},
        "deduped": deduped,
    }
