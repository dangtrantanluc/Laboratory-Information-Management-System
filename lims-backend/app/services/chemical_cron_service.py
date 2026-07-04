"""Chemical cron service (M2) — CRON-6: nhắc lô sắp hết hạn / tới hạn kiểm tra lại
(FR-CHEM-012).

Idempotent qua bảng chemical_notification_dedup (UNIQUE lot×kind×milestone×fire_date,
BR-CHEM-021). Redis lock chống chạy chồng (AC3). Chỉ quét lô qty_base > 0 (AC4).
Mốc nhắc: 30 / 15 / 7 ngày trước expiry_date / recheck_date.
"""
import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.redis_client import get_redis
from app.models.chemical import (
    Chemical,
    ChemicalLot,
    ChemicalNotificationDedup,
)
from app.services import notification_service

logger = logging.getLogger("lims.chemical.cron")

_LOCK_TTL = 300
_MILESTONES = (30, 15, 7)


def _acquire_lock(key: str) -> bool:
    return bool(get_redis().set(key, "1", nx=True, ex=_LOCK_TTL))


def _release_lock(key: str) -> None:
    try:
        get_redis().delete(key)
    except Exception:  # noqa: BLE001
        pass


def _recipients(db: Session, chem: Chemical) -> set[uuid.UUID]:
    """Người nhận: trưởng phòng + admin (mặc định OQ#8). Tránh sót cảnh báo."""
    recipients: set[uuid.UUID] = set()
    from app.models.department import Department
    from app.models.user import User

    dept = db.get(Department, chem.department_id)
    if dept and dept.lead_user_id:
        recipients.add(dept.lead_user_id)
    admins = db.execute(
        select(User.id).where(User.role == "admin", User.status == "active")
    ).scalars().all()
    recipients.update(admins)
    return recipients


def _milestone_for(target: date, today: date):
    """Trả mốc (30/15/7) nếu số ngày còn lại <= mốc; chọn mốc nhỏ nhất phù hợp.

    target đã qua (today > target) → coi như mốc 7 (vẫn nhắc khẩn). None nếu còn xa.
    """
    days_left = (target - today).days
    if days_left < 0:
        return 7
    for m in sorted(_MILESTONES):
        if days_left <= m:
            return m
    return None


def run_chem_expiry(db: Session) -> dict:
    lock_key = "cron:lock:chem-expiry"
    if not _acquire_lock(lock_key):
        raise AppException("CRON_ALREADY_RUNNING", "CRON-6 đang chạy", 409)

    now = datetime.now(timezone.utc)
    today = now.date()
    fire_date = today
    scanned = 0
    created = 0
    skipped = 0
    try:
        lots = db.execute(
            select(ChemicalLot).where(ChemicalLot.qty_base > 0)
        ).scalars().all()
        for lot in lots:
            scanned += 1
            chem = db.get(Chemical, lot.chemical_id)
            checks = []
            if lot.expiry_date:
                m = _milestone_for(lot.expiry_date, today)
                if m is not None:
                    checks.append(("CHEM_EXPIRY", m, lot.expiry_date, "sắp hết hạn"))
            if lot.recheck_date:
                m = _milestone_for(lot.recheck_date, today)
                if m is not None:
                    checks.append(
                        ("CHEM_RECHECK_DUE", m, lot.recheck_date, "tới hạn kiểm tra lại")
                    )

            for kind, milestone, target, label in checks:
                dedup = ChemicalNotificationDedup(
                    lot_id=lot.id,
                    kind=kind,
                    milestone_days=milestone,
                    fire_date=fire_date,
                )
                db.add(dedup)
                try:
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    skipped += 1
                    continue
                for uid in _recipients(db, chem):
                    notification_service.create_notification(
                        db,
                        user_id=uid,
                        type=kind,
                        title=f"Lô hóa chất {label}",
                        body=f"Lô {lot.lot_no} ({chem.name}) {label} vào {target.isoformat()} "
                        f"(còn ~{milestone} ngày)",
                        ref_type="chem_lot",
                        ref_id=lot.id,
                    )
                    created += 1
                db.flush()
        db.commit()
    finally:
        _release_lock(lock_key)

    logger.info(
        "CRON-6 chem-expiry done",
        extra={"scanned": scanned, "notif_created": created, "skipped": skipped},
    )
    return {
        "scanned_lots": scanned,
        "notifications_created": created,
        "skipped_duplicate": skipped,
        "ran_at": now,
    }
