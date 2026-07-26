"""Router health — liveness/readiness (no auth)."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.redis_client import get_redis
from app.db.database import get_db

router = APIRouter(tags=["health"])
logger = logging.getLogger("lims.health")


def _truncate(msg: str, limit: int = 200) -> str:
    """Cắt ngắn thông báo lỗi trả cho caller nội bộ (tránh lộ chi tiết dài/nhạy cảm)."""
    return msg[:limit]


@router.get("/health")
def health():
    return {"success": True, "data": {"status": "ok"}}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)):
    checks = {"db": False, "redis": False, "minio": False}
    errors: dict = {}

    try:
        db.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness db check failed", extra={"error": str(exc)})
        errors["db"] = _truncate(str(exc))

    try:
        get_redis().ping()
        checks["redis"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness redis check failed", extra={"error": str(exc)})
        errors["redis"] = _truncate(str(exc))

    try:
        from app.services import storage_service

        # head_bucket là gọi rẻ nhất xác nhận MinIO/S3 reachable + credential đúng.
        storage_service.check_connectivity()
        checks["minio"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness minio check failed", extra={"error": str(exc)})
        errors["minio"] = _truncate(str(exc))

    healthy = all(checks.values())
    data: dict = {"status": "ok" if healthy else "degraded", "checks": checks}
    if errors:
        data["errors"] = errors

    # Run-history của scheduler (bỏ lỡ cửa sổ cron ISO17025 → on-call cần thấy ngay).
    try:
        from app.scheduler import get_scheduler_status

        scheduler_status = get_scheduler_status()
        if scheduler_status:
            data["scheduler"] = scheduler_status
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness scheduler status failed", extra={"error": str(exc)})

    return {"success": healthy, "data": data}
