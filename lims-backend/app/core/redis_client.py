"""Redis client dùng chung: jti denylist, lockout đăng nhập, cache RBAC."""
import logging
from typing import Optional

import redis

from app.config import settings

logger = logging.getLogger("lims.redis")

# decode_responses=True → trả str thay vì bytes (tiện cho counter/denylist).
# socket_timeout/socket_connect_timeout: chặn treo vô hạn khi Redis chậm/không phản hồi
# (PRODUCTION_READINESS_REVIEW H2). health_check_interval: bỏ conn cũ đã stale.
_pool = redis.ConnectionPool.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_timeout=settings.redis_socket_timeout,
    socket_connect_timeout=settings.redis_connect_timeout,
    health_check_interval=30,
)


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


# ---- Key helpers ----
def jti_denylist_key(jti: str) -> str:
    return f"denylist:jti:{jti}"


# Lockout keyed theo (email, ip) — 1 IP tấn công KHÔNG khoá được nạn nhân đăng nhập từ IP
# khác (PRODUCTION_READINESS_REVIEW M11: targeted victim DoS). ip=None → "noip".
def login_fail_key(email: str, ip: Optional[str] = None) -> str:
    return f"login:fail:{email.lower()}:{ip or 'noip'}"


def login_lock_key(email: str, ip: Optional[str] = None) -> str:
    return f"login:lock:{email.lower()}:{ip or 'noip'}"


def rbac_role_key(role: str) -> str:
    return f"rbac:role:{role}"
