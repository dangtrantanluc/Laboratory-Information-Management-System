"""Router M5 — Thiết bị & Hiệu chuẩn (CRUD thiết bị, cảnh báo, tài liệu, hiệu chuẩn).

RBAC: đọc toàn lab (mọi vai trò 👁); ghi theo phòng (admin all; staff phòng mình;
leader/accountant cấm — enforce service). Bản ghi hiệu chuẩn IMMUTABLE — chỉ POST tạo;
KHÔNG PATCH/DELETE (§8.4, BR-EQP-007). Upload CoC/tài liệu qua multipart.

Thứ tự khai báo: route tĩnh (/calibration-due) TRƯỚC /{equipment_id} để tránh nuốt path.
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.equipment import CreateEquipmentRequest, UpdateEquipmentRequest
from app.services import calibration_service, equipment_service

router = APIRouter(prefix="/equipments", tags=["m5-equipments"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# ===== #2 GET /equipments/calibration-due (khai trước /{id}) =====
@router.get("/calibration-due")
def calibration_due(
    within_days: int = Query(default=30, ge=1, le=365),
    department_id: Optional[uuid.UUID] = Query(default=None),
    bucket: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = equipment_service.list_calibration_due(
        db,
        within_days=within_days,
        department_id=department_id,
        bucket=bucket,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


# ===== #1 GET /equipments =====
@router.get("")
def list_equipments(
    q: Optional[str] = Query(default=None, max_length=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    responsible_user_id: Optional[uuid.UUID] = Query(default=None),
    calibration_status: Optional[str] = Query(default=None),
    overdue: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = equipment_service.list_equipments(
        db,
        q=q,
        status_filter=status_filter,
        department_id=department_id,
        responsible_user_id=responsible_user_id,
        calibration_status=calibration_status,
        overdue=overdue,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


# ===== #4 POST /equipments =====
@router.post("", status_code=status.HTTP_201_CREATED)
def create_equipment(
    body: CreateEquipmentRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = equipment_service.create_equipment(
        db,
        user=user,
        payload=body.model_dump(),
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== #3 GET /equipments/:id =====
@router.get("/{equipment_id}")
def get_equipment(
    equipment_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(equipment_service.get_equipment_detail(db, equipment_id=equipment_id))


# ===== #5 PATCH /equipments/:id =====
@router.patch("/{equipment_id}")
def update_equipment(
    equipment_id: uuid.UUID,
    body: UpdateEquipmentRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = equipment_service.update_equipment(
        db,
        user=user,
        equipment_id=equipment_id,
        raw_body=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== #6 POST /equipments/:id/attachments (multipart) =====
@router.post("/{equipment_id}/attachments", status_code=status.HTTP_201_CREATED)
async def add_attachment(
    equipment_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    doc_type: Optional[str] = Form(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    data = equipment_service.add_attachment(
        db,
        user=user,
        equipment_id=equipment_id,
        file_name=file.filename or "document",
        content=content,
        mime=file.content_type,
        doc_type=doc_type,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== #7 GET /equipments/:id/attachments/:attId/download =====
@router.get("/{equipment_id}/attachments/{attachment_id}/download")
def download_attachment(
    equipment_id: uuid.UUID,
    attachment_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        equipment_service.download_attachment(
            db,
            user=user,
            equipment_id=equipment_id,
            attachment_id=attachment_id,
            correlation_id=_cid(request),
            ip=_ip(request),
        )
    )


# ===== #8 GET /equipments/:id/calibrations =====
@router.get("/{equipment_id}/calibrations")
def list_calibrations(
    equipment_id: uuid.UUID,
    result: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = calibration_service.list_calibrations(
        db, equipment_id=equipment_id, result=result, page=page, limit=limit
    )
    return paginated(items, page=page, limit=limit, total=total)


# ===== #9 POST /equipments/:id/calibrations (multipart, CỐT LÕI) =====
@router.post("/{equipment_id}/calibrations", status_code=status.HTTP_201_CREATED)
async def create_calibration(
    equipment_id: uuid.UUID,
    request: Request,
    calibrated_at: date = Form(...),
    result: str = Form(...),
    provider: Optional[str] = Form(default=None),
    next_due_date_override: Optional[date] = Form(default=None),
    override_reason: Optional[str] = Form(default=None),
    note: Optional[str] = Form(default=None),
    correction_of: Optional[uuid.UUID] = Form(default=None),
    cert: Optional[UploadFile] = File(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cert_content = await cert.read() if cert is not None else None
    data = calibration_service.create_calibration(
        db,
        user=user,
        equipment_id=equipment_id,
        calibrated_at=calibrated_at,
        result=result,
        provider=provider,
        next_due_date_override=next_due_date_override,
        override_reason=override_reason,
        note=note,
        correction_of=correction_of,
        cert_file_name=cert.filename if cert is not None else None,
        cert_content=cert_content,
        cert_mime=cert.content_type if cert is not None else None,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)
