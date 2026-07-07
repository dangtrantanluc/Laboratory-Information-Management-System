"""Router M10 — chạy thủ công CRON-8 (nhắc đánh giá lại rủi ro 30/15/7 ngày). Chỉ Admin."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_roles
from app.core.responses import ok
from app.db.database import get_db
from app.services import risk_cron_service

router = APIRouter(prefix="/admin/crons", tags=["m10-crons"])

admin_only = require_roles("admin")


class RunRiskReviewDueBody(BaseModel):
    as_of_date: Optional[date] = None
    model_config = {"extra": "forbid"}


@router.post("/risk-review-due/run")
def run_risk_review_due(
    body: Optional[RunRiskReviewDueBody] = None,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    as_of = body.as_of_date if body else None
    return ok(risk_cron_service.run_risk_review_due(db, actor=user, as_of_date=as_of))
