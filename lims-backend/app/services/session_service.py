"""Session service — xem và thu hồi phiên đăng nhập của chính mình (m30).

Một "phiên" = một bản ghi refresh_tokens chưa thu hồi và chưa hết hạn. Bảng này đã
lưu sẵn `user_agent` + `ip` + `created_at`, nên tính năng gần như chỉ là trình bày lại.

Thu hồi refresh token KHÔNG giết access token đang cầm (JWT stateless, sống tối đa
`access_token_ttl_minutes` = 30 phút). Đây là đánh đổi có ý thức của thiết kế hiện tại:
sau khi thu hồi, phiên đó không gia hạn được nữa và tắt hẳn trong vòng ≤30 phút.
"""
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.exceptions import not_found
from app.models.refresh_token import RefreshToken
from app.services import audit_service

logger = logging.getLogger("lims.session")


def _describe_user_agent(ua: Optional[str]) -> str:
    """Rút gọn User-Agent thành nhãn người đọc được. Cố tình đơn giản — không cần
    thư viện phân tích UA cho một danh sách thiết bị."""
    if not ua:
        return "Không rõ thiết bị"
    ua_l = ua.lower()

    if "edg/" in ua_l:
        browser = "Microsoft Edge"
    elif "opr/" in ua_l or "opera" in ua_l:
        browser = "Opera"
    elif "chrome" in ua_l and "chromium" not in ua_l:
        browser = "Chrome"
    elif "firefox" in ua_l:
        browser = "Firefox"
    elif "safari" in ua_l:
        browser = "Safari"
    else:
        browser = "Trình duyệt khác"

    if "android" in ua_l:
        os_name = "Android"
    elif "iphone" in ua_l or "ipad" in ua_l:
        os_name = "iOS"
    elif "windows" in ua_l:
        os_name = "Windows"
    elif "mac os" in ua_l or "macintosh" in ua_l:
        os_name = "macOS"
    elif "linux" in ua_l:
        os_name = "Linux"
    else:
        os_name = "Hệ điều hành khác"

    return f"{browser} · {os_name}"


def _is_mobile(ua: Optional[str]) -> bool:
    return bool(ua) and bool(re.search(r"android|iphone|ipad|mobile", ua, re.I))


def list_sessions(
    db: Session, *, user_id: uuid.UUID, current_token_hash: Optional[str]
) -> list[dict]:
    """Danh sách phiên còn sống, mới nhất trước. Đánh dấu phiên hiện tại."""
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .order_by(RefreshToken.created_at.desc())
    ).all()

    return [
        {
            "id": r.id,
            "device": _describe_user_agent(r.user_agent),
            "is_mobile": _is_mobile(r.user_agent),
            "ip": str(r.ip) if r.ip else None,
            "created_at": r.created_at,
            "expires_at": r.expires_at,
            # Phiên đang dùng để gọi API này — frontend không cho thu hồi trực tiếp,
            # muốn kết thúc thì bấm Đăng xuất.
            "is_current": bool(current_token_hash) and r.token_hash == current_token_hash,
        }
        for r in rows
    ]


def revoke_session(
    db: Session,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    correlation_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> dict:
    """Thu hồi một phiên cụ thể của CHÍNH user (không cho thu hồi phiên người khác)."""
    now = datetime.now(timezone.utc)
    row = db.scalar(
        select(RefreshToken).where(
            RefreshToken.id == session_id,
            # Điều kiện user_id là hàng rào phân quyền — không được bỏ.
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    if row is None:
        raise not_found("Không tìm thấy phiên đăng nhập này")

    row.revoked_at = now
    audit_service.log_action(
        db,
        action="REVOKE_SESSION",
        resource="refresh_token",
        resource_id=row.id,
        user_id=user_id,
        correlation_id=correlation_id,
        ip=ip,
    )
    db.commit()
    return {"id": row.id, "revoked_at": now}


def revoke_other_sessions(
    db: Session,
    *,
    user_id: uuid.UUID,
    keep_token_hash: Optional[str],
    correlation_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> dict:
    """Đăng xuất khỏi mọi thiết bị KHÁC, giữ lại phiên hiện tại."""
    now = datetime.now(timezone.utc)
    stmt = update(RefreshToken).where(
        RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
    )
    if keep_token_hash:
        stmt = stmt.where(RefreshToken.token_hash != keep_token_hash)

    count = db.execute(stmt.values(revoked_at=now)).rowcount
    audit_service.log_action(
        db,
        action="REVOKE_OTHER_SESSIONS",
        resource="refresh_token",
        user_id=user_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"revoked_count": count},
    )
    db.commit()
    return {"revoked_count": count}
