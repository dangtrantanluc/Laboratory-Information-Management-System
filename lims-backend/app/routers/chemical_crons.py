"""Router M2 — chạy thủ công CRON-6 (nhắc hết hạn / kiểm tra lại) để test/vận hành (FR-012).

Chỉ Admin. Idempotent + Redis lock (CRON_ALREADY_RUNNING nếu đang chạy).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_roles
from app.core.responses import ok
from app.db.database import get_db
from app.services import chemical_cron_service

router = APIRouter(prefix="/admin/crons", tags=["m2-crons"])

admin_only = require_roles("admin")


@router.post("/chem-expiry/run")
def run_chem_expiry(
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return ok(chemical_cron_service.run_chem_expiry(db))
