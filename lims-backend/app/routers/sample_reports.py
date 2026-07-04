"""Router reports (M1) — báo cáo on-time rate (FR-015, contract #36)."""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.exceptions import validation_error
from app.core.responses import ok
from app.db.database import get_db
from app.services import sample_common, sample_service

router = APIRouter(prefix="/reports", tags=["m1-reports"])


@router.get("/sample-on-time")
def sample_on_time(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    group_by: str = Query(default="department"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sample_common.deny_accountant(user)
    if date_from > date_to:
        raise validation_error("date_from phải <= date_to")
    if group_by not in ("department", "user"):
        raise validation_error("group_by chỉ nhận 'department' hoặc 'user'")
    data = sample_service.on_time_report(
        db,
        user=user,
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        department_id=department_id,
    )
    return ok(data)
