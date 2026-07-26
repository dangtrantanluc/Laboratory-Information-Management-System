"""IP-based rate limiting (Redis fixed-window) cho endpoint auth/export nhạy cảm.

Trước đây throttle duy nhất là per-account lockout (auth_service._check_lockout) —
một cuộc tấn công credential-stuffing rải đều nhiều tài khoản/IP không bao giờ chạm
ngưỡng đó (PRODUCTION_READINESS_REVIEW §Security: "No IP-based or global rate
limiting anywhere"). Đây là lớp phòng thủ bổ sung, độc lập với lockout theo email.

Fixed-window counter qua Redis INCR+EXPIRE — đơn giản, đủ cho use case chống
brute-force/lạm dụng (không cần độ mượt của token-bucket thật). Redis lỗi → fail-open
(log WARN, không chặn request) — cùng triết lý best-effort với RBAC cache/access-stats/
push đã dùng trong toàn bộ codebase.
"""
import logging

from fastapi import HTTPException, Request, status

from app.core.redis_client import get_redis

logger = logging.getLogger("lims.rate_limit")


def rate_limit(key_prefix: str, *, limit: int, window_seconds: int):
    """Trả về FastAPI dependency: tối đa `limit` request / `window_seconds` giây / IP.

    Dùng: `Depends(rate_limit("login", limit=20, window_seconds=60))`.
    """

    def _dep(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{key_prefix}:{ip}"
        try:
            r = get_redis()
            count = r.incr(key)
            if count == 1:
                r.expire(key, window_seconds)
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 — Redis lỗi KHÔNG được chặn request
            logger.warning(
                "rate_limit skipped (Redis unavailable)",
                extra={"key_prefix": key_prefix, "error": str(exc)},
            )
            return
        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Quá nhiều yêu cầu, vui lòng thử lại sau",
            )

    return _dep
