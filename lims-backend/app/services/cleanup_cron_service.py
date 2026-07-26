"""CRON-9 — dọn dữ liệu hết hạn (R9.6). Wrapper để scheduler gọi giống các cron khác."""
import logging

from app.db.database import SessionLocal
from app.services import cleanup_service

logger = logging.getLogger("lims.cleanup")


def run_cleanup() -> dict:
    db = SessionLocal()
    try:
        result = cleanup_service.run_cleanup(db)
        logger.info("CRON-9 cleanup done", extra=result)
        return result
    finally:
        db.close()
