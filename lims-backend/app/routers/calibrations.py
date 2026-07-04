"""Router M5 — bản ghi hiệu chuẩn (chi tiết, tải CoC). IMMUTABLE: KHÔNG PATCH/DELETE
(§8.4, BR-EQP-007). Đính chính = tạo bản ghi mới qua POST /equipments/:id/calibrations.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import ok
from app.db.database import get_db
from app.services import calibration_service

router = APIRouter(prefix="/calibrations", tags=["m5-calibrations"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# ===== #10 GET /calibrations/:id =====
@router.get("/{calibration_id}")
def get_calibration(
    calibration_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(calibration_service.get_calibration(db, calibration_id=calibration_id))


# ===== #14 GET /calibrations/:id/cert/download =====
@router.get("/{calibration_id}/cert/download")
def download_cert(
    calibration_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        calibration_service.download_cert(
            db,
            user=user,
            calibration_id=calibration_id,
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )
