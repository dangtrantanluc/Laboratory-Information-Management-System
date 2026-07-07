"""Router M8 — chạy thủ công CRON-7 (nhắc CAPA tới/quá hạn 7/3/0 ngày) để test/vận hành
(§8.7, #11). Chỉ Admin. Idempotent + Redis lock (CRON_ALREADY_RUNNING nếu đang chạy).
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_roles
from app.core.responses import ok
from app.db.database import get_db
from app.services import nc_cron_service

router = APIRouter(prefix="/admin/crons", tags=["m8-crons"])

admin_only = require_roles("admin")


class RunCapaDueBody(BaseModel):
    as_of_date: Optional[date] = None  # chỉ dev/staging để test mốc
    model_config = {"extra": "forbid"}


@router.post("/capa-due/run")
def run_capa_due(
    body: Optional[RunCapaDueBody] = None,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    as_of = body.as_of_date if body else None
    return ok(nc_cron_service.run_capa_due(db, actor=user, as_of_date=as_of))
