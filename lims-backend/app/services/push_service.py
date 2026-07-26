"""Push service — quản lý đăng ký + gửi Web Push (VAPID) cho popup thông báo desktop (M20).

send_push() best-effort, không bao giờ raise ra ngoài caller (được gọi từ
notification_service.create_notification, chung cho toàn bộ cron/service M1-M11/M19).
Subscription hết hạn (404/410 từ push service của trình duyệt) tự bị xóa.

Gửi chạy nền qua threadpool riêng, với session DB riêng (KHÔNG dùng session của caller)
— caller (vd chemical_txn_service._reorder_check, document_version_service) thường đang
giữ row lock (with_for_update) trong 1 transaction chưa commit; pywebpush không có timeout
mặc định nên có thể treo trên endpoint chậm/không phản hồi (PRODUCTION_READINESS_REVIEW
§Data/§Performance: "Synchronous outbound Web Push calls execute inside open DB
transactions while holding row locks"). Tách hẳn ra thread nền + session riêng để lệnh
gửi push không bao giờ kéo dài thời gian giữ lock/connection của transaction gọi nó.
"""
import json
import logging
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.push_subscription import PushSubscription

logger = logging.getLogger("lims.push")

# Timeout ngắn cho mỗi lần gọi webpush() — pywebpush/requests mặc định KHÔNG timeout,
# có thể treo tới OS TCP timeout mặc định (hàng chục giây/vô hạn) trên endpoint chết.
_WEBPUSH_TIMEOUT_SECONDS = 5

# Threadpool nhỏ riêng cho gửi push — tách khỏi threadpool mặc định của FastAPI/uvicorn
# để không cạnh tranh slot với các sync endpoint khác.
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="webpush")

# Chặn hàng đợi submit phình vô hạn khi push dồn ứ (M9): đếm task đang chờ/chạy, vượt trần
# thì bỏ (best-effort — push là non-critical) thay vì tích tụ bộ nhớ.
_MAX_INFLIGHT = 500
_inflight = 0
_inflight_lock = threading.Lock()


def shutdown_executor() -> None:
    """Drain hàng đợi push khi tắt app (gọi ở on_shutdown) — tránh mất push đang chờ."""
    _EXECUTOR.shutdown(wait=True)


def subscribe(
    db: Session,
    *,
    user_id: uuid.UUID,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: Optional[str] = None,
) -> PushSubscription:
    """Upsert theo endpoint (1 endpoint chỉ thuộc về 1 subscription — trình duyệt/thiết bị)."""
    existing = db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    ).scalar_one_or_none()
    if existing is not None:
        existing.user_id = user_id
        existing.p256dh = p256dh
        existing.auth = auth
        existing.user_agent = user_agent
        existing.last_seen_at = func.now()
        db.flush()
        return existing

    sub = PushSubscription(
        user_id=user_id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        user_agent=user_agent,
    )
    db.add(sub)
    db.flush()
    return sub


def unsubscribe(db: Session, *, user_id: uuid.UUID, endpoint: str) -> None:
    """STRICT SELF — chỉ xóa subscription thuộc chính user hiện tại."""
    db.execute(
        delete(PushSubscription).where(
            PushSubscription.endpoint == endpoint,
            PushSubscription.user_id == user_id,
        )
    )
    db.flush()


def send_push(*, user_id: uuid.UUID, payload: dict) -> None:
    """Lên lịch gửi Web Push chạy NỀN (threadpool + session riêng) — trả về ngay lập
    tức, KHÔNG chờ mạng, KHÔNG dùng chung session/transaction của caller."""
    if not settings.vapid_private_key:
        return
    global _inflight
    with _inflight_lock:
        if _inflight >= _MAX_INFLIGHT:
            logger.warning("push dropped — inflight queue full", extra={"inflight": _inflight})
            return
        _inflight += 1
    _EXECUTOR.submit(_send_push_sync, user_id, payload)


def _dec_inflight() -> None:
    global _inflight
    with _inflight_lock:
        _inflight = max(0, _inflight - 1)


def _send_push_sync(user_id: uuid.UUID, payload: dict) -> None:
    """Thực thi thật sự trên thread nền: mở session riêng, gửi push mọi thiết bị của
    user, dọn subscription hết hạn (404/410). Best-effort — mọi lỗi chỉ log WARN."""
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        subs = db.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        ).scalars().all()
        if not subs:
            return

        data = json.dumps(payload, default=str)
        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=data,
                    vapid_private_key=settings.vapid_private_key,
                    vapid_claims={"sub": f"mailto:{settings.vapid_claims_email}"},
                    timeout=_WEBPUSH_TIMEOUT_SECONDS,
                )
            except WebPushException as exc:
                status_code = getattr(exc.response, "status_code", None)
                if status_code in (404, 410):
                    db.execute(delete(PushSubscription).where(PushSubscription.id == sub.id))
                    db.commit()
                else:
                    logger.warning(
                        "Push send failed",
                        extra={"userId": str(user_id), "status": status_code, "error": str(exc)},
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Push send error", extra={"userId": str(user_id), "error": str(exc)}
                )
    except Exception as exc:  # noqa: BLE001 — background task, KHÔNG bao giờ raise
        logger.warning("Push dispatch skipped", extra={"userId": str(user_id), "error": str(exc)})
    finally:
        db.close()
        _dec_inflight()
