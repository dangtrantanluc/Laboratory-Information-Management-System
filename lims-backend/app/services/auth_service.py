"""Auth service — login, refresh rotation + reuse detection, logout, đổi mật khẩu.

Tuân thủ NFR-SEC-003: lockout 5 lần/15 phút, refresh rotation, reuse → revoke toàn chuỗi.
KHÔNG log/trả password hay token thô.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.core import rate_limit as rate_limit_mod
from app.core import security
from app.core.exceptions import AppException, validation_error
from app.core.redis_client import (
    get_redis,
    login_fail_key,
    login_lock_key,
)
from app.models.department import Department
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services import audit_service

logger = logging.getLogger("lims.auth")


# Hash bcrypt "mồi" cố định — verify mật khẩu với hash này khi email KHÔNG tồn tại để
# thời gian phản hồi bằng với trường hợp email tồn tại (chống user enumeration qua timing
# — PRODUCTION_READINESS_REVIEW M12). Sinh 1 lần lúc import (bcrypt cost 12 như thật).
_DUMMY_PASSWORD_HASH = security.hash_password("timing-equalizer-not-a-real-password")


# ---------- Lockout (Redis, keyed theo email+ip — M11) ----------
def _check_lockout(email: str, ip: Optional[str]) -> None:
    r = get_redis()
    ttl = r.ttl(login_lock_key(email, ip))
    if ttl and ttl > 0:
        locked_until = datetime.now(timezone.utc).timestamp() + ttl
        raise AppException(
            "ACCOUNT_LOCKED",
            "Tài khoản tạm khóa do nhập sai mật khẩu quá nhiều lần. Vui lòng thử lại sau.",
            423,
            details=[
                {
                    "field": "account",
                    "locked_until": datetime.fromtimestamp(
                        locked_until, tz=timezone.utc
                    ).isoformat(),
                    "remaining_seconds": int(ttl),
                }
            ],
        )


def _register_failed_login(email: str, ip: Optional[str]) -> None:
    r = get_redis()
    key = login_fail_key(email, ip)
    count = r.incr(key)
    if count == 1:
        # cửa sổ đếm = thời gian lockout (đếm sai liên tiếp)
        r.expire(key, settings.login_lockout_minutes * 60)
    if count >= settings.login_max_failed:
        r.setex(login_lock_key(email, ip), settings.login_lockout_minutes * 60, "1")
        r.delete(key)


def _reset_failed_login(email: str, ip: Optional[str]) -> None:
    r = get_redis()
    r.delete(login_fail_key(email, ip))
    r.delete(login_lock_key(email, ip))


# ---------- Helpers ----------
def _is_dept_lead(db: Session, user: User) -> bool:
    if user.department_id is None:
        return False
    dept = db.get(Department, user.department_id)
    return bool(dept and dept.lead_user_id == user.id)


def _issue_tokens(
    db: Session,
    user: User,
    *,
    user_agent: Optional[str],
    ip: Optional[str],
    rotated_from: Optional[uuid.UUID] = None,
) -> tuple[str, str, int]:
    """Tạo access token + refresh token (lưu hash). Trả (access, refresh_raw, expires_in)."""
    is_lead = _is_dept_lead(db, user)
    access, _jti, expires_in = security.create_access_token(
        user_id=user.id,
        role=user.role,
        department_id=user.department_id,
        is_dept_lead=is_lead,
    )
    refresh_raw, refresh_hash = security.generate_refresh_token()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=security.refresh_expiry(),
        rotated_from=rotated_from,
        user_agent=(user_agent or "")[:255] or None,
        ip=ip,
    )
    db.add(rt)
    db.flush()
    return access, refresh_raw, expires_in


# ---------- Login ----------
def login(
    db: Session,
    *,
    email: str,
    password: str,
    user_agent: Optional[str],
    ip: Optional[str],
    correlation_id: Optional[str],
) -> dict:
    email_norm = email.strip().lower()
    _check_lockout(email_norm, ip)
    # Rate limit theo email+IP. Dependency ở tầng router chỉ chặn theo IP, mà cả
    # viện đi chung một IP NAT nên rổ đó bị dùng chung — xem check_rate().
    rate_limit_mod.check_rate(
        "login_identity", f"{email_norm}|{ip or 'unknown'}", limit=10, window_seconds=300
    )

    user = db.execute(
        select(User).where(User.email == email_norm)
    ).scalar_one_or_none()

    # Chống user enumeration: cùng thông điệp + cùng thời gian (verify bcrypt kể cả khi
    # email không tồn tại — dùng hash mồi) cho sai email / sai password (M12).
    if user is None:
        security.verify_password(password, _DUMMY_PASSWORD_HASH)  # equalize timing
    if user is None or not security.verify_password(password, user.password_hash):
        _register_failed_login(email_norm, ip)
        audit_service.log_action(
            db,
            action="AUTH_LOGIN_FAIL",
            resource="user",
            user_id=user.id if user else None,
            correlation_id=correlation_id,
            ip=ip,
            detail={"email_attempt": email_norm},
        )
        db.commit()
        raise AppException(
            "INVALID_CREDENTIALS", "Email hoặc mật khẩu không đúng", 401
        )

    if user.status == "disabled":
        raise AppException("ACCOUNT_DISABLED", "Tài khoản đã bị vô hiệu hóa", 403)

    # m30 — tài khoản tự đăng ký. Chỉ báo trạng thái SAU KHI mật khẩu đã đúng, nên
    # thông điệp này không dùng để dò xem email nào đang chờ duyệt.
    if user.status == "pending":
        if user.email_verified_at is None:
            raise AppException(
                "EMAIL_NOT_VERIFIED",
                "Bạn chưa xác thực địa chỉ email. Vui lòng mở liên kết trong thư đã gửi.",
                403,
            )
        raise AppException(
            "ACCOUNT_PENDING_APPROVAL",
            "Tài khoản đang chờ Quản trị viên duyệt. Bạn sẽ nhận được thư khi tài "
            "khoản được kích hoạt.",
            403,
        )

    _reset_failed_login(email_norm, ip)
    user.last_login_at = func.now()

    access, refresh_raw, expires_in = _issue_tokens(
        db, user, user_agent=user_agent, ip=ip
    )

    dept = db.get(Department, user.department_id) if user.department_id else None
    is_lead = bool(dept and dept.lead_user_id == user.id)

    audit_service.log_action(
        db,
        action="AUTH_LOGIN_SUCCESS",
        resource="user",
        user_id=user.id,
        resource_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
    )
    # M6.3/R15: ghi lượt đăng nhập vào access_stats (nguồn đếm login — BR-RPT-004).
    # own_transaction=False → cùng commit với login flow (best-effort, không fail login).
    from app.services import access_stat_service

    access_stat_service.record(
        db,
        user_id=user.id,
        path="/auth/login",
        method="POST",
        status_code=200,
        ip=ip,
        event_type="login",
        own_transaction=False,
    )
    db.commit()

    return {
        "access_token": access,
        "refresh_token_raw": refresh_raw,  # router set vào cookie, KHÔNG trả body
        "token_type": "Bearer",
        "expires_in": expires_in,
        "must_change_password": user.password_changed_at is None,
        "user": {
            "id": user.id,
            "email": str(user.email),
            "full_name": user.full_name,
            "role": user.role,
            "department_id": user.department_id,
            "department_name": dept.name if dept else None,
            "is_dept_lead": is_lead,
        },
    }


# ---------- Refresh (rotation + reuse detection) ----------
def refresh(
    db: Session,
    *,
    refresh_token_raw: str,
    user_agent: Optional[str],
    ip: Optional[str],
    correlation_id: Optional[str],
) -> dict:
    token_hash = security.hash_refresh_token(refresh_token_raw)
    # Khoá hàng refresh-token để 2 request refresh SONG SONG cùng token tuần tự hoá:
    # request đầu revoke + rotate; request sau chờ lock, đọc lại thấy revoked → reuse
    # detection (single-use được đảm bảo — PRODUCTION_READINESS_REVIEW L2).
    rt = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    ).scalar_one_or_none()

    if rt is None:
        raise AppException("TOKEN_INVALID", "Refresh token không hợp lệ", 401)

    now = datetime.now(timezone.utc)

    # Reuse detection: token đã revoke vẫn dùng lại → token theft → revoke toàn chuỗi user
    if rt.revoked_at is not None:
        db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == rt.user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=func.now())
        )
        audit_service.log_action(
            db,
            action="AUTH_TOKEN_REUSE_DETECTED",
            resource="user",
            user_id=rt.user_id,
            resource_id=rt.user_id,
            correlation_id=correlation_id,
            ip=ip,
        )
        db.commit()
        logger.warning(
            "Refresh token reuse detected — revoked all sessions",
            extra={"correlationId": correlation_id, "userId": str(rt.user_id)},
        )
        raise AppException(
            "TOKEN_REUSED",
            "Phát hiện sử dụng lại token — toàn bộ phiên đã bị thu hồi. Vui lòng đăng nhập lại.",
            401,
        )

    if rt.expires_at <= now:
        raise AppException("TOKEN_EXPIRED", "Refresh token đã hết hạn", 401)

    user = db.get(User, rt.user_id)
    if user is None:
        raise AppException("TOKEN_INVALID", "Người dùng không tồn tại", 401)
    if user.status == "disabled":
        raise AppException("ACCOUNT_DISABLED", "Tài khoản đã bị vô hiệu hóa", 403)

    # Rotation: revoke token cũ + cấp token mới (rotated_from = id cũ) trong 1 transaction
    rt.revoked_at = func.now()
    db.flush()
    access, refresh_raw, expires_in = _issue_tokens(
        db, user, user_agent=user_agent, ip=ip, rotated_from=rt.id
    )

    audit_service.log_action(
        db,
        action="AUTH_TOKEN_REFRESH",
        resource="user",
        user_id=user.id,
        resource_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
    )
    db.commit()

    return {
        "access_token": access,
        "refresh_token_raw": refresh_raw,
        "token_type": "Bearer",
        "expires_in": expires_in,
    }


# ---------- Logout ----------
def logout(
    db: Session,
    *,
    user_id: uuid.UUID,
    jti: str,
    token_exp: int,
    refresh_token_raw: Optional[str],
    all_devices: bool,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> None:
    if all_devices:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
    elif refresh_token_raw:
        token_hash = security.hash_refresh_token(refresh_token_raw)
        db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=func.now())
        )

    # Đẩy jti access token hiện tại vào denylist (cắt phiên ngay)
    if jti and token_exp:
        security.deny_jti(jti, token_exp)

    audit_service.log_action(
        db,
        action="AUTH_LOGOUT",
        resource="user",
        user_id=user_id,
        resource_id=user_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"all_devices": all_devices},
    )
    db.commit()


# ---------- Đổi mật khẩu (self) ----------
def change_own_password(
    db: Session,
    *,
    user_id: uuid.UUID,
    current_password: str,
    new_password: str,
    keep_token_hash: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> datetime:
    user = db.get(User, user_id)
    if user is None:
        raise AppException("UNAUTHORIZED", "Người dùng không tồn tại", 401)

    if not security.verify_password(current_password, user.password_hash):
        raise AppException("INVALID_CREDENTIALS", "Mật khẩu hiện tại không đúng", 401)

    if new_password == current_password:
        raise validation_error(
            "Mật khẩu mới phải khác mật khẩu hiện tại",
            details=[{"field": "new_password", "message": "Trùng mật khẩu cũ"}],
        )

    user.password_hash = security.hash_password(new_password)
    user.password_changed_at = func.now()

    # Revoke mọi refresh token KHÁC (giữ phiên hiện tại nếu xác định được)
    revoke_q = update(RefreshToken).where(
        RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
    )
    if keep_token_hash:
        revoke_q = revoke_q.where(RefreshToken.token_hash != keep_token_hash)
    db.execute(revoke_q.values(revoked_at=func.now()))

    audit_service.log_action(
        db,
        action="PASSWORD_CHANGE_SELF",
        resource="user",
        user_id=user_id,
        resource_id=user_id,
        correlation_id=correlation_id,
        ip=ip,
    )
    db.commit()
    db.refresh(user)
    return user.password_changed_at
