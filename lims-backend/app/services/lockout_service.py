"""Quản lý TÀI KHOẢN BỊ KHOÁ ĐĂNG NHẬP — dành cho Quản trị viên (m49).

VÌ SAO CẦN
`auth_service` khoá tài khoản sau `login_max_failed` lần sai, ghi một khoá Redis có TTL
rồi thôi. Trạng thái đó **không hiện ở đâu cả**: người dùng chỉ thấy "tài khoản tạm
khoá", còn quản trị viên không có cách nào biết ai đang bị khoá, khoá từ lúc nào, còn
bao lâu, hay mở khoá sớm. Cách duy nhất từ trước tới nay là gõ lệnh redis-cli trên máy
chủ — tức là việc này không nằm trong phần mềm.

KHOÁ NẰM Ở REDIS, KHÔNG PHẢI Ở DATABASE
    login:fail:<email>:<ip>   bộ đếm sai liên tiếp, TTL = thời gian khoá
    login:lock:<email>:<ip>   đang bị khoá, TTL = thời gian còn lại

Hệ quả cần nhớ khi đọc mã này:
  · Khoá TỰ HẾT HẠN. Danh sách ở đây là ảnh chụp hiện tại, không phải lịch sử — lịch sử
    nằm ở nhật ký kiểm toán (`ACCOUNT_LOCKED` / `ACCOUNT_UNLOCKED`).
  · Khoá theo CẶP (email, IP), không theo tài khoản. Đây là chủ ý của M11: một kẻ tấn
    công từ IP lạ không khoá được nạn nhân đăng nhập từ IP thật của họ. Nên "mở khoá cho
    người này" = xoá MỌI khoá của email đó, không chỉ một IP.
  · Email trong khoá có thể KHÔNG ứng với tài khoản nào — đó là dấu hiệu có người dò
    email. Vẫn liệt kê ra, vì đó chính là thứ quản trị viên cần thấy.
"""
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.core.redis_client import get_redis, login_fail_key, login_lock_key
from app.models.user import User
from app.services import audit_service

_LOCK_PREFIX = "login:lock:"
_FAIL_PREFIX = "login:fail:"


def _split(key: str, prefix: str) -> tuple[str, str]:
    """Tách `<prefix><email>:<ip>` thành (email, ip).

    Cắt ở dấu hai chấm ĐẦU TIÊN sau tiền tố, không phải dấu cuối: địa chỉ IPv6 chứa đầy
    dấu hai chấm, nên `rsplit` sẽ băm nát chúng. Email thì không chứa dấu hai chấm bao
    giờ, nên ranh giới đầu tiên luôn đúng.
    """
    rest = key[len(prefix):]
    email, _, ip = rest.partition(":")
    return email, ip or "noip"


def list_lockouts(db: Session, *, user: CurrentUser) -> dict:
    """Ảnh chụp hiện tại: đang bị khoá, và đang đếm sai nhưng chưa khoá.

    Trả cả nhóm "chưa khoá" vì đó là cảnh báo sớm — 4/5 lần sai trên một email lạ là
    dấu hiệu dò mật khẩu, thấy lúc đang diễn ra thì còn xử lý được.
    """
    r = get_redis()
    locked: list[dict] = []
    failing: list[dict] = []

    try:
        # scan_iter, KHÔNG dùng KEYS: KEYS quét toàn bộ không gian khoá trong một lệnh
        # và chặn Redis — mà Redis ở đây còn giữ denylist token và cache phân quyền.
        for raw in r.scan_iter(match=f"{_LOCK_PREFIX}*", count=200):
            key = raw if isinstance(raw, str) else raw.decode()
            email, ip = _split(key, _LOCK_PREFIX)
            ttl = r.ttl(key)
            locked.append({"email": email, "ip": ip, "remaining_seconds": max(int(ttl or 0), 0)})

        for raw in r.scan_iter(match=f"{_FAIL_PREFIX}*", count=200):
            key = raw if isinstance(raw, str) else raw.decode()
            email, ip = _split(key, _FAIL_PREFIX)
            val = r.get(key)
            failing.append({
                "email": email, "ip": ip,
                "failed_attempts": int(val) if val else 0,
                "remaining_seconds": max(int(r.ttl(key) or 0), 0),
            })
    except Exception as exc:  # noqa: BLE001
        # Redis hỏng thì màn hình quản trị phải nói rõ, không im lặng trả danh sách rỗng
        # — "không có ai bị khoá" và "không hỏi được" là hai câu trả lời rất khác nhau.
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            f"Không đọc được trạng thái khoá đăng nhập: {exc}",
            503,
        )

    # Gắn tên tài khoản cho các email có thật. Email KHÔNG khớp tài khoản nào vẫn giữ
    # trong danh sách — đó là dấu hiệu dò email, không phải rác cần lọc bỏ.
    emails = {x["email"] for x in locked} | {x["email"] for x in failing}
    known = {
        str(u.email).lower(): u
        for u in db.execute(select(User).where(User.email.in_(list(emails)))).scalars()
    } if emails else {}
    for row in (*locked, *failing):
        u = known.get(row["email"].lower())
        row["user_id"] = u.id if u else None
        row["full_name"] = u.full_name if u else None
        row["is_known_account"] = u is not None

    locked.sort(key=lambda x: -x["remaining_seconds"])
    failing.sort(key=lambda x: -x["failed_attempts"])
    return {"locked": locked, "failing": failing}


def unlock_user(
    db: Session, *, user: CurrentUser, target_user_id: uuid.UUID,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Mở khoá cho MỘT TÀI KHOẢN — xoá khoá ở mọi IP, kèm cả bộ đếm sai.

    Xoá cả `login:fail:*`: để lại bộ đếm nghĩa là người vừa được mở khoá chỉ cần sai
    thêm một lần là bị khoá lại ngay, và họ sẽ tưởng việc mở khoá không có tác dụng.
    """
    target = db.get(User, target_user_id)
    if target is None:
        raise AppException(ErrorCode.USER_NOT_FOUND, "Người dùng không tồn tại", 404)

    email = str(target.email).lower()
    r = get_redis()
    removed = 0
    try:
        for prefix in (_LOCK_PREFIX, _FAIL_PREFIX):
            for raw in r.scan_iter(match=f"{prefix}{email}:*", count=200):
                key = raw if isinstance(raw, str) else raw.decode()
                removed += int(r.delete(key) or 0)
        # Dọn nốt biến thể "không có IP" mà scan theo mẫu ở trên không phủ.
        removed += int(r.delete(login_lock_key(email)) or 0)
        removed += int(r.delete(login_fail_key(email)) or 0)
    except Exception as exc:  # noqa: BLE001
        raise AppException(
            ErrorCode.INTERNAL_ERROR, f"Không mở khoá được: {exc}", 503
        )

    audit_service.log_action(
        db, action="ACCOUNT_UNLOCKED", resource="user", user_id=user.id,
        resource_id=target_user_id, correlation_id=correlation_id, ip=ip,
        detail={"email": email, "keys_removed": removed},
    )
    db.commit()
    return {"user_id": target_user_id, "email": email, "keys_removed": removed}
