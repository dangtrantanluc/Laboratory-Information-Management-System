"""Router health — liveness/readiness (no auth)."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.redis_client import get_redis
from app.db.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"success": True, "data": {"status": "ok"}}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)):
    checks = {"db": False, "redis": False}
    try:
        db.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        get_redis().ping()
        checks["redis"] = True
    except Exception:  # noqa: BLE001
        pass
    healthy = all(checks.values())
    return {"success": healthy, "data": {"status": "ok" if healthy else "degraded", "checks": checks}}
