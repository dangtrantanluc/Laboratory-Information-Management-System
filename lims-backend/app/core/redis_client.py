"""Redis client dùng chung: jti denylist, lockout đăng nhập, cache RBAC."""
import logging

import redis

from app.config import settings

logger = logging.getLogger("lims.redis")

# decode_responses=True → trả str thay vì bytes (tiện cho counter/denylist)
_pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


# ---- Key helpers ----
def jti_denylist_key(jti: str) -> str:
    return f"denylist:jti:{jti}"


def login_fail_key(email: str) -> str:
    return f"login:fail:{email.lower()}"


def login_lock_key(email: str) -> str:
    return f"login:lock:{email.lower()}"


def rbac_role_key(role: str) -> str:
    return f"rbac:role:{role}"
