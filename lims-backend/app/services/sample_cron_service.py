"""Sample cron service (M1) — CRON-1 nhắc sắp tới hạn, CRON-2 đánh dấu overdue.

Cả hai chạy dưới Redis lock + idempotent (BR-018):
- CRON-2: status filter ('received','assigned','testing') → idempotent tự nhiên.
- CRON-1: dedup theo (sample_id, milestone, fire_date) qua Redis key (TTL 2 ngày).
Dùng cùng cơ chế notifications M7 (create_notification).
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.redis_client import get_redis
from app.models.sample import Sample
from app.models.sample_assignment import SampleAssignment
from app.services import audit_service, notification_service, sample_common

logger = logging.getLogger("lims.sample.cron")

_LOCK_TTL = 300  # 5 phút — lock chống chạy chồng
# Mốc nhắc CRON-1 (ngày trước deadline) — OQ#4, cấu hình mặc định
_DUE_SOON_MILESTONES = (3, 1)


def _acquire_lock(key: str) -> bool:
    r = get_redis()
    return bool(r.set(key, "1", nx=True, ex=_LOCK_TTL))


def _release_lock(key: str) -> None:
    try:
        get_redis().delete(key)
    except Exception:  # noqa: BLE001
        pass


def _recipients(db: Session, sample: Sample) -> set[uuid.UUID]:
    """Người cần nhắc: custodian hiện tại + assignees + trưởng nhóm phòng."""
    users: set[uuid.UUID] = {sample.current_custodian_id}
    assignees = db.execute(
        select(SampleAssignment.assigned_to).where(
            SampleAssignment.sample_id == sample.id
        )
    ).scalars().all()
    users.update(assignees)
    from app.models.department import Department

    dept = db.get(Department, sample.department_id)
    if dept and dept.lead_user_id:
        users.add(dept.lead_user_id)
    return users


def run_due_soon(db: Session) -> dict:
    """CRON-1: nhắc mẫu sắp tới hạn trong các mốc (3 ngày, 1 ngày)."""
    lock_key = "cron:lock:sample-due-soon"
    if not _acquire_lock(lock_key):
        raise AppException("LOCK_HELD", "Cron đang chạy, vui lòng thử lại sau", 409)

    r = get_redis()
    now = datetime.now(timezone.utc)
    fire_date = now.date().isoformat()
    scanned = 0
    created = 0
    skipped = 0
    try:
        horizon = now + timedelta(days=max(_DUE_SOON_MILESTONES))
        samples = db.execute(
            select(Sample).where(
                Sample.deleted_at.is_(None),
                Sample.status.notin_(["done", "returned"]),
                Sample.deadline_at >= now,
                Sample.deadline_at <= horizon,
            )
        ).scalars().all()
        for sample in samples:
            scanned += 1
            days_left = (sample.deadline_at - now).days
            # chọn mốc nhỏ nhất phù hợp
            milestone = None
            for m in sorted(_DUE_SOON_MILESTONES):
                if days_left <= m:
                    milestone = m
                    break
            if milestone is None:
                continue
            dedup_key = f"cron:dedup:due-soon:{sample.id}:{milestone}:{fire_date}"
            if not r.set(dedup_key, "1", nx=True, ex=2 * 24 * 3600):
                skipped += 1
                continue
            for uid in _recipients(db, sample):
                notification_service.create_notification(
                    db,
                    user_id=uid,
                    type="SAMPLE_DUE_SOON",
                    title="Mẫu sắp tới hạn",
                    body=f"Mẫu {sample.sample_code} còn ~{days_left} ngày tới hạn",
                    ref_type="sample",
                    ref_id=sample.id,
                )
                created += 1
        db.commit()
    finally:
        _release_lock(lock_key)

    logger.info(
        "CRON-1 due-soon done",
        extra={"scanned": scanned, "notif_created": created, "skipped": skipped},
    )
    return {
        "scanned": scanned,
        "notifications_created": created,
        "skipped_duplicate": skipped,
        "ran_at": now,
    }


def run_overdue(db: Session, *, actor_id: Optional[uuid.UUID] = None) -> dict:
    """CRON-2: đánh dấu mẫu quá hạn chưa done → overdue (idempotent)."""
    lock_key = "cron:lock:sample-overdue"
    if not _acquire_lock(lock_key):
        raise AppException("LOCK_HELD", "Cron đang chạy, vui lòng thử lại sau", 409)

    now = datetime.now(timezone.utc)
    scanned = 0
    marked = 0
    created = 0
    try:
        samples = db.execute(
            select(Sample)
            .where(
                Sample.deleted_at.is_(None),
                Sample.status.in_(["received", "assigned", "testing"]),
                Sample.deadline_at < now,
            )
            .with_for_update()
        ).scalars().all()
        for sample in samples:
            scanned += 1
            sample_common.change_status(
                db,
                sample,
                "overdue",
                trigger="cron_overdue",
                user_id=actor_id,
                correlation_id=None,
                ip=None,
            )
            audit_service.log_action(
                db,
                action="SAMPLE_MARK_OVERDUE",
                resource="sample",
                user_id=actor_id,
                resource_id=sample.id,
                detail={"deadline_at": sample.deadline_at.isoformat()},
            )
            marked += 1
            for uid in _recipients(db, sample):
                notification_service.create_notification(
                    db,
                    user_id=uid,
                    type="SAMPLE_OVERDUE",
                    title="Mẫu đã quá hạn",
                    body=f"Mẫu {sample.sample_code} đã quá hạn xử lý",
                    ref_type="sample",
                    ref_id=sample.id,
                )
                created += 1
        db.commit()
    finally:
        _release_lock(lock_key)

    logger.info(
        "CRON-2 overdue done",
        extra={"scanned": scanned, "marked": marked, "notif_created": created},
    )
    return {
        "scanned": scanned,
        "marked_overdue": marked,
        "notifications_created": created,
        "ran_at": now,
    }
