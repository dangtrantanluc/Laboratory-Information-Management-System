"""Router M4 — chạy thủ công CRON-3 (nhắc nâng lương) / CRON-4 (hết hạn HĐ) để test/vận
hành (#42/#43, FR-HR-008/009).

Chỉ Admin. Idempotent + Redis lock (CRON_ALREADY_RUNNING nếu đang chạy).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_roles
from app.core.responses import ok
from app.db.database import get_db
from app.services import hr_cron_service

router = APIRouter(prefix="/admin/crons", tags=["m4-crons"])

admin_only = require_roles("admin")


@router.post("/salary-raise-due/run")
def run_salary_raise_due(
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return ok(hr_cron_service.run_salary_raise_due(db, actor=user))


@router.post("/contract-expiry/run")
def run_contract_expiry(
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return ok(hr_cron_service.run_contract_expiry(db, actor=user))
