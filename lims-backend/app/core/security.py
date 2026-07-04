"""Bảo mật: bcrypt password, JWT access token, refresh token opaque + hash, jti denylist.

Tuân thủ: bcrypt cost >= 10 (NFR-SEC-002); access TTL <= 60p; refresh opaque hash sha256 (D7).
KHÔNG log/trả password hay token thô.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.core.redis_client import get_redis, jti_denylist_key

# bcrypt cost 12 (>= 10 theo NFR-SEC-002)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


# ---------- Password ----------
def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd_context.verify(plain, hashed)
    except ValueError:
        return False


def generate_temp_password(length: int = 14) -> str:
    """Sinh mật khẩu tạm mạnh (chữ + số + ký tự) — bàn giao qua kênh an toàn, KHÔNG trả API."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    specials = "@#$%&*"
    base = "".join(secrets.choice(alphabet) for _ in range(length - 2))
    return base + secrets.choice("0123456789") + secrets.choice(specials)


# ---------- Access token (JWT, stateless) ----------
def create_access_token(
    *,
    user_id: uuid.UUID,
    role: str,
    department_id: Optional[uuid.UUID],
    is_dept_lead: bool,
) -> tuple[str, str, int]:
    """Trả (token, jti, expires_in_seconds)."""
    now = datetime.now(timezone.utc)
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "dept": str(department_id) if department_id else None,
        "is_dept_lead": is_dept_lead,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, int(ttl.total_seconds())


def decode_access_token(token: str) -> dict[str, Any]:
    """Giải mã + verify chữ ký/exp. Raise JWTError nếu sai/hết hạn."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# ---------- Refresh token (opaque + hash) ----------
def generate_refresh_token() -> tuple[str, str]:
    """Trả (token_raw, token_hash). token_raw set vào cookie; token_hash lưu DB (D7)."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def refresh_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_ttl_days)


# ---------- jti denylist (revoke access token tức thời) ----------
def deny_jti(jti: str, exp_ts: int) -> None:
    """Đưa jti vào denylist tới khi access token hết hạn (TTL = thời gian còn lại)."""
    now = int(datetime.now(timezone.utc).timestamp())
    ttl = max(exp_ts - now, 1)
    get_redis().setex(jti_denylist_key(jti), ttl, "1")


def is_jti_denied(jti: str) -> bool:
    return get_redis().exists(jti_denylist_key(jti)) == 1
