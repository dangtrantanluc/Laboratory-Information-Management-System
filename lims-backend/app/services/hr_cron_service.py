"""HR cron service (M4.2) — CRON-3 nhắc nâng lương (mốc 15/7/3) + CRON-4 nhắc hết hạn
HĐ (mốc 30/15/7) (FR-HR-008/009).

Idempotent qua bảng hr_notification_dedup (UNIQUE profile×kind×milestone×fire_date,
BR-HR-013) + ON CONFLICT/IntegrityError. Redis lock chống chạy chồng (giống CRON-6 M2).
Dedup chỉ theo HỒ SƠ; fan-out nhiều notifications cho từng người nhận trong 1 lần fire.

Người nhận:
  - CRON-3 (SALARY_RAISE_DUE): HR (admin/leader/accountant) + chính nhân sự + lãnh đạo.
  - CRON-4 (CONTRACT_EXPIRY): HR (admin/leader/accountant).
KHÔNG ghi giá trị lương/PII vào body/log (BR-HR-024) — chỉ fact + ngày.
"""
import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.core.redis_client import get_redis
from app.models.department import Department
from app.models.hr import HrNotificationDedup, HrProfile
from app.models.user import User
from app.services import audit_service, notification_service

logger = logging.getLogger("lims.hr.cron")

_LOCK_TTL = 300
_SALARY_MILESTONES = (15, 7, 3)
_CONTRACT_MILESTONES = (30, 15, 7)


def _acquire_lock(key: str) -> bool:
    return bool(get_redis().set(key, "1", nx=True, ex=_LOCK_TTL))


def _release_lock(key: str) -> None:
    try:
        get_redis().delete(key)
    except Exception:  # noqa: BLE001
        pass


def _hr_staff(db: Session) -> set[uuid.UUID]:
    """HR + lãnh đạo = admin/leader/accountant active (có hr:manage)."""
    rows = db.execute(
        select(User.id).where(
            User.role.in_(("admin", "leader", "accountant")), User.status == "active"
        )
    ).scalars().all()
    return set(rows)


def _milestone_hit(target: date, today: date, milestones) -> int | None:
    """Trả mốc nếu số ngày còn lại == đúng 1 mốc (nhắc đúng ngày mốc, không spam mỗi ngày)."""
    days_left = (target - today).days
    if days_left in milestones:
        return days_left
    return None


def _fire(
    db: Session,
    *,
    profile_user_id: uuid.UUID,
    kind: str,
    milestone: int,
    fire_date: date,
    recipients: set[uuid.UUID],
    notif_type: str,
    title: str,
    body: str,
) -> tuple[int, bool]:
    """Dedup theo hồ sơ trước; nếu chưa fire → tạo notifications cho từng người nhận.

    Trả (số notif tạo, skipped_duplicate?).
    """
    dedup = HrNotificationDedup(
        profile_user_id=profile_user_id,
        kind=kind,
        milestone_days=milestone,
        fire_date=fire_date,
    )
    db.add(dedup)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return 0, True
    created = 0
    for uid in recipients:
        notification_service.create_notification(
            db,
            user_id=uid,
            type=notif_type,
            title=title,
            body=body,
            ref_type="hr_profile",
            ref_id=profile_user_id,
        )
        created += 1
    db.flush()
    return created, False


def run_salary_raise_due(db: Session, *, actor: CurrentUser | None = None) -> dict:
    """CRON-3 — quét next_salary_raise_date tới mốc 15/7/3 ngày."""
    lock_key = "cron:lock:hr-salary-raise"
    if not _acquire_lock(lock_key):
        raise AppException("CRON_ALREADY_RUNNING", "CRON-3 đang chạy", 409)

    now = datetime.now(timezone.utc)
    today = now.date()
    scanned = created = skipped = 0
    try:
        hr_recipients = _hr_staff(db)
        profiles = db.execute(
            select(HrProfile).where(HrProfile.next_salary_raise_date.is_not(None))
        ).scalars().all()
        for p in profiles:
            scanned += 1
            milestone = _milestone_hit(p.next_salary_raise_date, today, _SALARY_MILESTONES)
            if milestone is None:
                continue
            # người nhận: HR + lãnh đạo + chính nhân sự
            recipients = set(hr_recipients)
            recipients.add(p.user_id)
            staff_name = _user_name(db, p.user_id)
            c, dup = _fire(
                db,
                profile_user_id=p.user_id,
                kind="SALARY_RAISE_DUE",
                milestone=milestone,
                fire_date=today,
                recipients=recipients,
                notif_type="SALARY_RAISE_DUE",
                title="Sắp tới hạn nâng lương",
                body=f"{staff_name} tới hạn xét nâng lương vào "
                f"{p.next_salary_raise_date.isoformat()} (còn ~{milestone} ngày)",
            )
            created += c
            if dup:
                skipped += 1
        db.commit()
    finally:
        _release_lock(lock_key)

    _audit_cron(db, "CRON_SALARY_RAISE_RUN", actor, scanned, created, skipped)
    logger.info(
        "CRON-3 salary-raise done",
        extra={"scanned": scanned, "notif_created": created, "skipped": skipped},
    )
    return {
        "scanned": scanned,
        "notifications_created": created,
        "skipped_duplicate": skipped,
        "ran_at": now,
    }


def run_contract_expiry(db: Session, *, actor: CurrentUser | None = None) -> dict:
    """CRON-4 — quét contract_end_date tới mốc 30/15/7 ngày (bỏ HĐ vô thời hạn)."""
    lock_key = "cron:lock:hr-contract-expiry"
    if not _acquire_lock(lock_key):
        raise AppException("CRON_ALREADY_RUNNING", "CRON-4 đang chạy", 409)

    now = datetime.now(timezone.utc)
    today = now.date()
    scanned = created = skipped = 0
    try:
        hr_recipients = _hr_staff(db)
        profiles = db.execute(
            select(HrProfile).where(HrProfile.contract_end_date.is_not(None))
        ).scalars().all()
        for p in profiles:
            scanned += 1
            milestone = _milestone_hit(p.contract_end_date, today, _CONTRACT_MILESTONES)
            if milestone is None:
                continue
            recipients = set(hr_recipients)
            staff_name = _user_name(db, p.user_id)
            c, dup = _fire(
                db,
                profile_user_id=p.user_id,
                kind="CONTRACT_EXPIRY",
                milestone=milestone,
                fire_date=today,
                recipients=recipients,
                notif_type="CONTRACT_EXPIRY",
                title="Hợp đồng sắp hết hạn",
                body=f"HĐ của {staff_name} hết hạn vào "
                f"{p.contract_end_date.isoformat()} (còn ~{milestone} ngày)",
            )
            created += c
            if dup:
                skipped += 1
        db.commit()
    finally:
        _release_lock(lock_key)

    _audit_cron(db, "CRON_CONTRACT_EXPIRY_RUN", actor, scanned, created, skipped)
    logger.info(
        "CRON-4 contract-expiry done",
        extra={"scanned": scanned, "notif_created": created, "skipped": skipped},
    )
    return {
        "scanned": scanned,
        "notifications_created": created,
        "skipped_duplicate": skipped,
        "ran_at": now,
    }


def _user_name(db: Session, user_id: uuid.UUID) -> str:
    u = db.get(User, user_id)
    return u.full_name if u else str(user_id)


def _audit_cron(db, action, actor, scanned, created, skipped) -> None:
    try:
        audit_service.log_action(
            db,
            action=action,
            resource="hr_cron",
            user_id=actor.id if actor else None,
            correlation_id=None,
            detail={"scanned": scanned, "created": created, "skipped": skipped},
        )
        db.commit()
    except Exception:  # noqa: BLE001 — audit lỗi không chặn cron
        db.rollback()
