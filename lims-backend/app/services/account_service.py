"""Account service — tự đăng ký, xác thực email, quên/đặt lại mật khẩu (m30).

Nguyên tắc bảo mật xuyên suốt:

1. KHÔNG rò rỉ email nào tồn tại (user enumeration). `register` và `forgot_password`
   luôn trả cùng một phản hồi bất kể email có trong hệ thống hay không. Cùng tinh thần
   với `_DUMMY_PASSWORD_HASH` mà auth_service dùng để chống dò qua timing.

2. Token gửi trong mail là chuỗi ngẫu nhiên 48 byte; DB chỉ lưu SHA-256. Rò rỉ bảng
   auth_tokens không cho phép đặt lại mật khẩu của ai.

3. Token dùng-một-lần: mọi token cùng mục đích của user bị vô hiệu khi phát hành token
   mới, và bị đánh dấu `used_at` ngay khi tiêu thụ.

4. Tài khoản tự đăng ký LUÔN ở status 'pending' — xác thực email chỉ chứng minh
   "đúng chủ hộp thư", KHÔNG tự cấp quyền vào hệ thống. Quản trị viên phải duyệt và
   gán vai trò (yêu cầu kiểm soát truy cập của ISO/IEC 17025).
"""
import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.core import security
from app.core.exceptions import validation_error
from app.models.auth_token import (
    PURPOSE_EMAIL_VERIFY,
    PURPOSE_PASSWORD_RESET,
    AuthToken,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services import audit_service, email_service

logger = logging.getLogger("lims.account")

# Vai trò tạm cho tài khoản chờ duyệt. Quản trị viên gán lại vai trò thật lúc duyệt.
# Chọn 'staff' vì đây là vai trò ít quyền nhất; dù sao status='pending' cũng chặn đăng nhập.
_PENDING_PLACEHOLDER_ROLE = "staff"


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _issue_token(
    db: Session,
    *,
    user_id: uuid.UUID,
    purpose: str,
    ttl: timedelta,
    ip: Optional[str],
) -> str:
    """Phát hành token mới và VÔ HIỆU mọi token cùng mục đích còn hiệu lực của user.

    Trả về token THÔ (chỉ dùng để dựng link gửi mail — không lưu, không log).
    """
    now = datetime.now(timezone.utc)
    db.execute(
        update(AuthToken)
        .where(
            AuthToken.user_id == user_id,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    raw = secrets.token_urlsafe(48)
    db.add(
        AuthToken(
            user_id=user_id,
            token_hash=_hash_token(raw),
            purpose=purpose,
            expires_at=now + ttl,
            ip=ip,
        )
    )
    db.flush()
    return raw


def _consume_token(db: Session, *, raw_token: str, purpose: str) -> AuthToken:
    """Xác thực + tiêu thụ token. Raise nếu sai/hết hạn/đã dùng."""
    token = db.scalar(
        select(AuthToken).where(
            AuthToken.token_hash == _hash_token(raw_token),
            AuthToken.purpose == purpose,
        )
    )
    now = datetime.now(timezone.utc)
    # Gộp chung một thông báo cho mọi trường hợp hỏng — không tiết lộ token có tồn tại
    # hay chỉ hết hạn.
    if token is None or token.used_at is not None or token.expires_at <= now:
        raise validation_error(
            "Liên kết không hợp lệ hoặc đã hết hạn. Vui lòng thực hiện lại yêu cầu."
        )
    token.used_at = now
    db.flush()
    return token


def _check_email_domain(email: str) -> None:
    allowed = settings.self_registration_domain_list
    if not allowed:
        return
    domain = email.rsplit("@", 1)[-1].lower()
    if domain not in allowed:
        raise validation_error(
            "Địa chỉ email không thuộc tên miền được phép đăng ký.",
            details=[{"field": "email", "allowed_domains": allowed}],
        )


# ──────────────────────────── Đăng ký ────────────────────────────


def register(
    db: Session,
    *,
    email: str,
    full_name: str,
    password: str,
    correlation_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> dict:
    """Tạo tài khoản ở trạng thái 'pending' và gửi mail xác thực.

    Phản hồi LUÔN giống nhau dù email đã tồn tại hay chưa — chống dò danh sách người dùng.
    """
    if not settings.self_registration_enabled:
        raise validation_error("Hệ thống hiện không mở đăng ký tự phục vụ.")

    _check_email_domain(email)

    generic_response = {
        "message": (
            "Nếu địa chỉ email hợp lệ, chúng tôi đã gửi thư xác thực. "
            "Vui lòng kiểm tra hộp thư (kể cả mục Spam)."
        )
    }

    existing = db.scalar(select(User).where(User.email == email))

    if existing is not None:
        # Email đã có. Không tiết lộ điều đó, nhưng vẫn xử lý hợp lý:
        # - Nếu tài khoản đang chờ và CHƯA xác thực mail → gửi lại link xác thực.
        # - Còn lại (đã active/disabled) → không làm gì, trả phản hồi chung.
        if existing.status == "pending" and existing.email_verified_at is None:
            raw = _issue_token(
                db,
                user_id=existing.id,
                purpose=PURPOSE_EMAIL_VERIFY,
                ttl=timedelta(hours=settings.email_verify_ttl_hours),
                ip=ip,
            )
            db.commit()
            email_service.send_email_verification(
                to=str(existing.email),
                full_name=existing.full_name,
                verify_url=f"{settings.app_public_url}/verify-email?token={raw}",
            )
        else:
            logger.info(
                "register: email đã tồn tại, bỏ qua",
                extra={"correlation_id": correlation_id},
            )
        return generic_response

    user = User(
        email=email,
        password_hash=security.hash_password(password),
        full_name=full_name.strip(),
        role=_PENDING_PLACEHOLDER_ROLE,
        department_id=None,
        status="pending",
        # Người dùng tự đặt mật khẩu lúc đăng ký → không bắt đổi lại ở lần đăng nhập đầu.
        password_changed_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()

    raw = _issue_token(
        db,
        user_id=user.id,
        purpose=PURPOSE_EMAIL_VERIFY,
        ttl=timedelta(hours=settings.email_verify_ttl_hours),
        ip=ip,
    )
    audit_service.log_action(
        db,
        action="REGISTER",
        resource="user",
        resource_id=user.id,
        user_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"email": email, "status": "pending"},
    )
    db.commit()

    email_service.send_email_verification(
        to=email,
        full_name=user.full_name,
        verify_url=f"{settings.app_public_url}/verify-email?token={raw}",
    )
    return generic_response


def verify_email(
    db: Session,
    *,
    raw_token: str,
    correlation_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> dict:
    """Đánh dấu email đã xác thực. KHÔNG kích hoạt tài khoản — vẫn chờ duyệt."""
    token = _consume_token(db, raw_token=raw_token, purpose=PURPOSE_EMAIL_VERIFY)
    user = db.get(User, token.user_id)
    if user is None:
        raise validation_error("Liên kết không hợp lệ hoặc đã hết hạn.")

    already = user.email_verified_at is not None
    if not already:
        user.email_verified_at = datetime.now(timezone.utc)
        audit_service.log_action(
            db,
            action="VERIFY_EMAIL",
            resource="user",
            resource_id=user.id,
            user_id=user.id,
            correlation_id=correlation_id,
            ip=ip,
        )
    db.commit()

    return {
        "email": str(user.email),
        "already_verified": already,
        "status": user.status,
        # Frontend dùng cờ này để hiển thị đúng thông điệp: đã xác thực xong nhưng
        # còn phải chờ Quản trị viên duyệt.
        "awaiting_approval": user.status == "pending",
    }


# ──────────────────────────── Quên / đặt lại mật khẩu ────────────────────────────


def forgot_password(
    db: Session,
    *,
    email: str,
    correlation_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> dict:
    """Gửi link đặt lại mật khẩu. LUÔN trả phản hồi giống nhau."""
    generic_response = {
        "message": (
            "Nếu địa chỉ email tồn tại trong hệ thống, chúng tôi đã gửi hướng dẫn "
            "đặt lại mật khẩu. Vui lòng kiểm tra hộp thư (kể cả mục Spam)."
        )
    }

    user = db.scalar(select(User).where(User.email == email))
    # Chỉ tài khoản đang hoạt động mới đặt lại được. Tài khoản pending/disabled im lặng
    # bỏ qua — nói ra là tiết lộ trạng thái tài khoản cho người ngoài.
    if user is None or user.status != "active":
        logger.info(
            "forgot_password: bỏ qua (không tồn tại hoặc không active)",
            extra={"correlation_id": correlation_id},
        )
        return generic_response

    raw = _issue_token(
        db,
        user_id=user.id,
        purpose=PURPOSE_PASSWORD_RESET,
        ttl=timedelta(minutes=settings.password_reset_ttl_minutes),
        ip=ip,
    )
    audit_service.log_action(
        db,
        action="FORGOT_PASSWORD",
        resource="user",
        resource_id=user.id,
        user_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
    )
    db.commit()

    email_service.send_password_reset(
        to=str(user.email),
        full_name=user.full_name,
        reset_url=f"{settings.app_public_url}/reset-password?token={raw}",
    )
    return generic_response


def reset_password(
    db: Session,
    *,
    raw_token: str,
    new_password: str,
    correlation_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> dict:
    """Đặt mật khẩu mới bằng token trong mail, và THU HỒI mọi phiên đang mở.

    Thu hồi phiên là bắt buộc: nếu người dùng đặt lại mật khẩu vì nghi bị chiếm tài
    khoản, mà phiên của kẻ tấn công vẫn sống thì việc đổi mật khẩu vô nghĩa.
    """
    token = _consume_token(db, raw_token=raw_token, purpose=PURPOSE_PASSWORD_RESET)
    user = db.get(User, token.user_id)
    if user is None or user.status != "active":
        raise validation_error("Liên kết không hợp lệ hoặc đã hết hạn.")

    now = datetime.now(timezone.utc)
    user.password_hash = security.hash_password(new_password)
    user.password_changed_at = now

    revoked = db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    ).rowcount

    audit_service.log_action(
        db,
        action="RESET_PASSWORD",
        resource="user",
        resource_id=user.id,
        user_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"revoked_sessions": revoked},
    )
    db.commit()

    email_service.send_password_changed_notice(
        to=str(user.email), full_name=user.full_name, ip=ip
    )
    return {"message": "Đã đặt lại mật khẩu. Vui lòng đăng nhập bằng mật khẩu mới."}
