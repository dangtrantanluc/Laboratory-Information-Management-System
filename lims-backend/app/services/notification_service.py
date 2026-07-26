"""Notification service — tạo/đọc thông báo in-app (M7.5).

create_notification dùng chung cho cron M1/M2/M4/M5 (interface ổn định).
Đọc/đánh dấu STRICT SELF (user_id == current user) — chống IDOR.
"""
import logging
import uuid
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification

logger = logging.getLogger("lims.notification")


def create_notification(
    db: Session,
    *,
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: Optional[str] = None,
    ref_type: Optional[str] = None,
    ref_id: Optional[uuid.UUID] = None,
) -> Notification:
    """Tạo 1 thông báo cho user. Caller commit. Dùng chung cho M1/M2/M4/M5 cron."""
    notif = Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    db.add(notif)
    db.flush()

    try:
        from app.services import push_service

        # send_push chỉ lên lịch gửi trên thread nền (session DB riêng) — trả về ngay,
        # KHÔNG chờ mạng và KHÔNG giữ transaction/lock hiện tại của caller (vd
        # chemical_txn_service/document_version_service đang with_for_update()).
        push_service.send_push(
            user_id=user_id,
            payload={
                "title": title,
                "body": body or "",
                "ref_type": ref_type,
                "ref_id": str(ref_id) if ref_id else None,
                "notification_id": str(notif.id),
            },
        )
    except Exception:  # noqa: BLE001
        logger.warning("Push send skipped", exc_info=True)

    return notif


def list_notifications(
    db: Session,
    *,
    user_id: uuid.UUID,
    unread: Optional[bool],
    type_filter: Optional[str],
    page: int,
    limit: int,
) -> tuple[list[Notification], int]:
    conditions = [Notification.user_id == user_id]
    if unread:
        conditions.append(Notification.read_at.is_(None))
    if type_filter:
        conditions.append(Notification.type == type_filter)

    total = db.execute(
        select(func.count()).select_from(Notification).where(*conditions)
    ).scalar_one()

    rows = db.execute(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return list(rows), total


def unread_count(db: Session, *, user_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    ).scalar_one()


def mark_read(
    db: Session, *, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Optional[Notification]:
    """Đánh dấu 1 thông báo đã đọc — STRICT SELF. None nếu không thuộc user (→ 404)."""
    notif = db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    ).scalar_one_or_none()
    if notif is None:
        return None
    if notif.read_at is None:
        notif.read_at = func.now()
    db.flush()
    return notif


def mark_unread(
    db: Session, *, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Optional[Notification]:
    """Bỏ đánh dấu đã đọc (read_at = NULL) — STRICT SELF. None nếu không thuộc user (→ 404)."""
    notif = db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    ).scalar_one_or_none()
    if notif is None:
        return None
    notif.read_at = None
    db.flush()
    return notif


def mark_all_read(
    db: Session, *, user_id: uuid.UUID, type_filter: Optional[str]
) -> int:
    conditions = [Notification.user_id == user_id, Notification.read_at.is_(None)]
    if type_filter:
        conditions.append(Notification.type == type_filter)
    result = db.execute(
        update(Notification)
        .where(*conditions)
        .values(read_at=func.now())
    )
    db.flush()
    return result.rowcount or 0
