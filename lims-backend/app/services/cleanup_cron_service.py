"""CRON-9 — dọn dữ liệu hết hạn (R9.6). Wrapper để scheduler gọi giống các cron khác.

LƯU Ý CHỮ KÝ: hàm này PHẢI nhận `db` làm tham số vị trí đầu tiên, giống 8 cron còn
lại — `scheduler._run_tracked` mở session rồi gọi `service_call(db)` cho mọi job.

Bản cũ khai `def run_cleanup() -> dict` và tự mở `SessionLocal()`. Nó là hàm duy nhất
lệch quy ước, nên mỗi lần scheduler chạy đều nổ:

    TypeError: run_cleanup() takes 0 positional arguments but 1 was given

Nghĩa là CRON-9 CHƯA TỪNG chạy được lần nào kể từ khi thêm vào — auth_token hết hạn,
access_stats quá 90 ngày và object MinIO mồ côi đều không được dọn. Không ai phát hiện
vì `_run_tracked` chỉ ghi "failed" vào Redis và không có cảnh báo nào đọc nó.
"""
import logging

from sqlalchemy.orm import Session

from app.services import cleanup_service

logger = logging.getLogger("lims.cleanup")


def run_cleanup(db: Session) -> dict:
    """Điểm vào cho scheduler. Session do caller mở và đóng (như mọi cron khác)."""
    result = cleanup_service.run_cleanup(db)
    logger.info("CRON-9 cleanup done", extra=result)
    return result
