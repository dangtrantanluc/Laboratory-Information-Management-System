"""Router M5 — chạy thủ công CRON-5 (nhắc hiệu chuẩn 30/15/7 ngày) để test/vận hành
(FR-EQP-011, #15). Chỉ Admin. Idempotent + Redis lock (CRON_ALREADY_RUNNING nếu đang chạy).
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_roles
from app.core.responses import ok
from app.db.database import get_db
from app.services import equipment_cron_service

router = APIRouter(prefix="/admin/crons", tags=["m5-crons"])

admin_only = require_roles("admin")


class RunCalibrationDueBody(BaseModel):
    as_of_date: Optional[date] = None  # chỉ dev/staging để test mốc
    model_config = {"extra": "forbid"}


@router.post("/equipment-calibration-due/run")
def run_calibration_due(
    body: Optional[RunCalibrationDueBody] = None,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    as_of = body.as_of_date if body else None
    return ok(
        equipment_cron_service.run_calibration_due(db, actor=user, as_of_date=as_of)
    )
