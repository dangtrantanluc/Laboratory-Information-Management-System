"""M5 cron service — CRON-5 nhắc trước hiệu chuẩn (mốc 30/15/7 ngày) (FR-EQP-011).

Idempotent qua bảng equipment_notification_dedup (UNIQUE equipment×milestone×fire_date,
D8/BR-EQP-011) + ON CONFLICT/IntegrityError. Redis lock chống chạy chồng (giống CRON-6
M2 / CRON-3/4 M4). Dedup chỉ theo THIẾT BỊ×mốc×ngày; gửi cho người phụ trách +
trưởng nhóm phòng vẫn idempotent.

Quét: next_due_date - today ∈ {30,15,7} AND chu kỳ ≠ NULL (diện hiệu chuẩn — BR-EQP-010)
AND status ∉ {retired} AND deleted_at IS NULL. Không người phụ trách → chỉ trưởng nhóm;
không trưởng nhóm → skipped_no_recipient + WARN (không lỗi job). In-app only (C02).
"""
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.core.redis_client import get_redis
from app.models.department import Department
from app.models.equipment import Equipment, EquipmentNotificationDedup
from app.services import audit_service, notification_service

logger = logging.getLogger("lims.equipment.cron")

_LOCK_TTL = 300
_MILESTONES = (30, 15, 7)
_LOCK_KEY = "cron:lock:equipment-calibration-due"


def _acquire_lock(key: str) -> bool:
    return bool(get_redis().set(key, "1", nx=True, ex=_LOCK_TTL))


def _release_lock(key: str) -> None:
    try:
        get_redis().delete(key)
    except Exception:  # noqa: BLE001
        pass


def _recipients(db: Session, eq: Equipment) -> set[uuid.UUID]:
    """Người phụ trách + trưởng nhóm phòng (BR-EQP-011)."""
    rec: set[uuid.UUID] = set()
    if eq.responsible_user_id:
        rec.add(eq.responsible_user_id)
    dept = db.get(Department, eq.department_id)
    if dept and dept.lead_user_id:
        rec.add(dept.lead_user_id)
    return rec


def run_calibration_due(
    db: Session, *, actor: Optional[CurrentUser] = None, as_of_date: Optional[date] = None
) -> dict:
    """CRON-5 — quét next_due_date tới mốc 30/15/7 ngày, nhắc in-app idempotent."""
    if not _acquire_lock(_LOCK_KEY):
        raise AppException("CRON_ALREADY_RUNNING", "CRON-5 đang chạy", 409)

    now = datetime.now(timezone.utc)
    today = as_of_date or now.date()
    scanned = 0
    notifications_created = 0
    deduped = 0
    skipped_no_recipient = 0
    skipped_retired_or_no_cycle = 0
    recipients_total = 0
    by_milestone = {30: 0, 15: 0, 7: 0}

    try:
        # Chỉ thiết bị diện hiệu chuẩn + chưa xóa + có next_due (partial index idx_equip_next_due)
        equipments = db.execute(
            select(Equipment).where(
                Equipment.deleted_at.is_(None),
                Equipment.next_due_date.is_not(None),
                Equipment.calibration_cycle_value.is_not(None),
            )
        ).scalars().all()

        for eq in equipments:
            if eq.status == "retired" or eq.calibration_cycle_value is None:
                skipped_retired_or_no_cycle += 1
                continue
            scanned += 1
            days_left = (eq.next_due_date - today).days
            if days_left not in _MILESTONES:
                continue

            # Idempotent: INSERT dedup trước; UNIQUE violation = đã gửi mốc này
            dedup = EquipmentNotificationDedup(
                equipment_id=eq.id,
                kind="CALIBRATION_DUE",
                milestone_days=days_left,
                fire_date=today,
            )
            db.add(dedup)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                deduped += 1
                continue

            recipients = _recipients(db, eq)
            if not recipients:
                skipped_no_recipient += 1
                logger.warning(
                    "CRON-5 no recipient for equipment",
                    extra={"equipmentCode": eq.code, "milestone": days_left},
                )
                continue

            for uid in recipients:
                notification_service.create_notification(
                    db,
                    user_id=uid,
                    type="CALIBRATION_DUE",
                    title="Thiết bị sắp tới hạn hiệu chuẩn",
                    body=f"{eq.code} - {eq.name} tới hạn hiệu chuẩn vào "
                    f"{eq.next_due_date.isoformat()} (còn {days_left} ngày)",
                    ref_type="equipment",
                    ref_id=eq.id,
                )
                notifications_created += 1
            recipients_total += len(recipients)
            by_milestone[days_left] += 1
            db.flush()

        db.commit()
    finally:
        _release_lock(_LOCK_KEY)

    _audit_cron(
        db,
        actor,
        scanned=scanned,
        created=notifications_created,
        by_milestone=by_milestone,
    )
    logger.info(
        "CRON-5 calibration-due done",
        extra={
            "scanned": scanned,
            "notif_created": notifications_created,
            "deduped": deduped,
        },
    )
    return {
        "run_at": now,
        "as_of_date": today,
        "scanned_equipments": scanned,
        "notifications_created": notifications_created,
        "by_milestone": {str(k): v for k, v in by_milestone.items()},
        "recipients": recipients_total,
        "skipped_no_recipient": skipped_no_recipient,
        "skipped_retired_or_no_cycle": skipped_retired_or_no_cycle,
        "deduped": deduped,
    }


def _audit_cron(db, actor, *, scanned, created, by_milestone) -> None:
    try:
        audit_service.log_action(
            db,
            action="CRON_CALIBRATION_REMINDER",
            resource="equipment_cron",
            user_id=actor.id if actor else None,
            correlation_id=None,
            detail={"scanned": scanned, "created": created, "by_milestone": by_milestone},
        )
        db.commit()
    except Exception:  # noqa: BLE001 — audit lỗi không chặn cron
        db.rollback()
