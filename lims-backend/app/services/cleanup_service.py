"""Cleanup service — dọn dữ liệu hết hạn/mồ côi (R9.6).

Ba loại rác tích tụ vô hạn nếu không dọn:

1. `auth_tokens` đã hết hạn hoặc đã dùng (m30). Mỗi lần quên mật khẩu / đăng ký
   sinh một hàng; không ai xoá.
2. `access_stats` cũ. Mỗi GET whitelist ghi một hàng — đây là bảng lớn nhất hệ
   thống ngay từ đầu (6.924 hàng khi hệ thống còn chưa có người dùng thật).
3. Object MinIO mồ côi: attachment đã soft-delete quá lâu, file vẫn nằm nguyên
   trong bucket và chiếm đĩa.

Nguyên tắc: xoá theo LÔ, có trần mỗi lần chạy. Một câu DELETE quét cả triệu hàng
sẽ khoá bảng và làm treo API — đúng thứ ta đang cố tránh.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.models.auth_token import AuthToken
from app.services import storage_service

logger = logging.getLogger("lims.cleanup")

# Trần mỗi lần chạy — job chạy hằng ngày nên vẫn theo kịp tốc độ sinh rác.
_BATCH_LIMIT = 5_000

AUTH_TOKEN_RETENTION_DAYS = 7
ACCESS_STAT_RETENTION_DAYS = 90
ORPHAN_ATTACHMENT_GRACE_DAYS = 30


def purge_expired_auth_tokens(db: Session) -> int:
    """Xoá token xác thực email / đặt lại mật khẩu đã hết hạn hoặc đã dùng.

    Giữ lại 7 ngày sau khi hết hạn để còn tra được khi điều tra sự cố.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=AUTH_TOKEN_RETENTION_DAYS)
    ids = db.scalars(
        select(AuthToken.id)
        .where((AuthToken.expires_at < cutoff) | (AuthToken.used_at < cutoff))
        .limit(_BATCH_LIMIT)
    ).all()
    if not ids:
        return 0
    db.execute(delete(AuthToken).where(AuthToken.id.in_(ids)))
    db.commit()
    logger.info("purge_expired_auth_tokens", extra={"deleted": len(ids)})
    return len(ids)


def purge_old_access_stats(db: Session) -> int:
    """Xoá bản ghi lượt truy cập cũ hơn 90 ngày.

    Báo cáo lượt truy cập chỉ dùng số liệu ngày/tuần/tháng, nên dữ liệu thô quá
    90 ngày không phục vụ gì ngoài việc phình bảng.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=ACCESS_STAT_RETENTION_DAYS)
    # Dùng SQL thô: model access_stat có tên cột khác nhau giữa các phiên bản,
    # còn đây là bảng append-only đơn giản.
    # Cột thời gian của access_stats là `at` (không phải created_at).
    # ctid cho phép xoá theo lô mà không cần khoá chính.
    res = db.execute(
        text(
            "DELETE FROM access_stats WHERE ctid IN ("
            "  SELECT ctid FROM access_stats WHERE at < :cutoff LIMIT :lim"
            ")"
        ),
        {"cutoff": cutoff, "lim": _BATCH_LIMIT},
    )
    db.commit()
    n = res.rowcount or 0
    if n:
        logger.info("purge_old_access_stats", extra={"deleted": n})
    return n


def purge_orphan_attachments(db: Session) -> int:
    """Xoá object MinIO của attachment đã soft-delete quá 30 ngày.

    Soft-delete chỉ đặt `deleted_at`; file vẫn nằm trong bucket. Sau thời gian ân
    hạn (đủ để khôi phục nếu xoá nhầm) thì mới xoá thật để lấy lại đĩa.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=ORPHAN_ATTACHMENT_GRACE_DAYS)
    rows = db.execute(
        text(
            "SELECT id, file_key FROM attachments "
            "WHERE deleted_at IS NOT NULL AND deleted_at < :cutoff LIMIT :lim"
        ),
        {"cutoff": cutoff, "lim": _BATCH_LIMIT},
    ).all()
    if not rows:
        return 0

    removed = 0
    for att_id, file_key in rows:
        try:
            storage_service.remove_object(file_key)
            removed += 1
        except Exception as exc:  # noqa: BLE001 — MinIO lỗi không được chặn cả job
            logger.warning(
                "purge_orphan_attachments: bỏ qua object",
                extra={"attachment_id": str(att_id), "error": str(exc)},
            )
    logger.info("purge_orphan_attachments", extra={"objects_removed": removed})
    return removed


def run_cleanup(db: Session) -> dict:
    """Điểm vào cho cron. Mỗi bước độc lập: bước này lỗi không chặn bước sau."""
    result: dict = {}
    for name, fn in (
        ("auth_tokens", purge_expired_auth_tokens),
        ("access_stats", purge_old_access_stats),
        ("orphan_attachments", purge_orphan_attachments),
    ):
        try:
            result[name] = fn(db)
        except Exception as exc:  # noqa: BLE001
            logger.error("cleanup step failed", extra={"step": name, "error": str(exc)})
            result[name] = -1
            db.rollback()
    return result
