"""Router admin crons (M1) — chạy thủ công CRON-1/CRON-2 để test/vận hành (FR-013/014).

Chỉ Admin (require_roles). Idempotent + Redis lock (LOCK_HELD nếu đang chạy).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_roles
from app.core.responses import ok
from app.db.database import get_db
from app.services import sample_cron_service

router = APIRouter(prefix="/admin/crons", tags=["m1-crons"])

admin_only = require_roles("admin")


@router.post("/sample-due-soon/run")
def run_due_soon(
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return ok(sample_cron_service.run_due_soon(db))


@router.post("/sample-overdue/run")
def run_overdue(
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return ok(sample_cron_service.run_overdue(db, actor_id=user.id))
