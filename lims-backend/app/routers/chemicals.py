"""Router M2 — Hóa chất, lô, tồn kho, units, low-stock, reconcile, MSDS, export, report.

Field-level RBAC: cột giá strip với vai trò không có chemical:cost (ở service).
Phạm vi phòng cho ghi. Mọi vai trò đăng nhập đọc được tồn/lịch sử (chemical:read).

LƯU Ý thứ tự đăng ký: /chemicals tĩnh đăng ký trước /chemicals/{id} động.
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.chemical import (
    CreateChemicalRequest,
    CreateLotRequest,
    UpdateChemicalRequest,
)
from app.services import (
    attachment_service,
    chemical_common as cc,
    chemical_report_service,
    chemical_service,
)

router = APIRouter(tags=["m2-chemicals"])

_MSDS_MIME_WHITELIST = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# ===== units =====
@router.get("/units")
def list_units(
    group: Optional[str] = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if group and group not in ("mass", "volume", "count"):
        raise AppException("VALIDATION_ERROR", "group không hợp lệ", 400)
    return ok(chemical_service.list_units(db, group=group))


# ===== inventory aggregates (đăng ký trước /chemicals/{id}) =====
@router.get("/inventory/low-stock")
def low_stock(
    department_id: Optional[uuid.UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = chemical_service.list_low_stock(
        db, department_id=department_id, page=page, limit=limit
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.get("/inventory/reconcile")
def reconcile(
    chemical_id: Optional[uuid.UUID] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    include_ok: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(require_roles("admin", "leader")),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = chemical_service.reconcile(
        db,
        chemical_id=chemical_id,
        department_id=department_id,
        include_ok=include_ok,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


# ===== exports & reports =====
@router.get("/exports/transactions.xlsx")
def export_transactions(
    request: Request,
    date_from: date = Query(...),
    date_to: date = Query(...),
    chemical_id: Optional[uuid.UUID] = Query(default=None),
    ref_sample_id: Optional[uuid.UUID] = Query(default=None),
    by_user: Optional[uuid.UUID] = Query(default=None),
    type: Optional[str] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = chemical_report_service.export_transactions_xlsx(
        db,
        user=user,
        date_from=date_from,
        date_to=date_to,
        chemical_id=chemical_id,
        ref_sample_id=ref_sample_id,
        by_user=by_user,
        txn_type=type,
        department_id=department_id,
        can_cost=cc.can_see_cost(db, user),
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    filename = f"chem-journal-{date_from.isoformat()}_{date_to.isoformat()}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/consumption")
def consumption(
    group_by: str = Query(...),
    date_from: date = Query(...),
    date_to: date = Query(...),
    chemical_id: Optional[uuid.UUID] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = chemical_report_service.consumption_report(
        db,
        user=user,
        group_by=group_by,
        date_from=date_from,
        date_to=date_to,
        chemical_id=chemical_id,
        department_id=department_id,
        can_cost=cc.can_see_cost(db, user),
    )
    return ok(data)


# ===== chemicals: list / create =====
@router.get("/chemicals")
def list_chemicals(
    q: Optional[str] = Query(default=None, max_length=100),
    department_id: Optional[uuid.UUID] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    measurement_group: Optional[str] = Query(default=None),
    has_stock: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = chemical_service.list_chemicals(
        db,
        q=q,
        department_id=department_id,
        status_filter=status_filter,
        measurement_group=measurement_group,
        has_stock=has_stock,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("/chemicals", status_code=status.HTTP_201_CREATED)
def create_chemical(
    body: CreateChemicalRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = chemical_service.create_chemical(
        db,
        user=user,
        name=body.name,
        cas_no=body.cas_no,
        manufacturer=body.manufacturer,
        base_unit=body.base_unit,
        hazard_code=body.hazard_code,
        department_id=body.department_id,
        reorder_threshold=body.reorder_threshold,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.get("/chemicals/{chemical_id}")
def get_chemical(
    chemical_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(chemical_service.get_chemical_detail(db, chemical_id))


@router.patch("/chemicals/{chemical_id}")
def update_chemical(
    chemical_id: uuid.UUID,
    body: UpdateChemicalRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise AppException("VALIDATION_ERROR", "Body rỗng", 400)
    data = chemical_service.update_chemical(
        db,
        user=user,
        chemical_id=chemical_id,
        changes=changes,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.post("/chemicals/{chemical_id}/deactivate")
def deactivate_chemical(
    chemical_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = chemical_service.deactivate_chemical(
        db,
        user=user,
        chemical_id=chemical_id,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== MSDS attachments =====
@router.get("/chemicals/{chemical_id}/attachments")
def list_msds(
    chemical_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cc.get_chemical_or_404(db, chemical_id)
    from sqlalchemy import select

    from app.config import settings
    from app.models.attachment import Attachment
    from app.services import storage_service

    atts = db.execute(
        select(Attachment).where(
            Attachment.owner_type == "chemical",
            Attachment.owner_id == chemical_id,
            Attachment.deleted_at.is_(None),
        )
    ).scalars().all()
    items = [
        {
            "id": a.id,
            "file_name": a.file_name,
            "mime": a.mime,
            "size": a.size,
            "download_url": storage_service.presigned_get_url(
                a.file_key, file_name=a.file_name
            ),
            "uploaded_by": a.uploaded_by,
            "uploaded_at": a.uploaded_at,
        }
        for a in atts
    ]
    return ok(items)


@router.post("/chemicals/{chemical_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_msds(
    chemical_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chem = cc.get_chemical_or_404(db, chemical_id)
    cc.assert_can_create(db, user)
    cc.assert_write_scope(user, chem.department_id)
    if file.content_type not in _MSDS_MIME_WHITELIST:
        raise AppException(
            "INVALID_FILE_TYPE", "Định dạng file không hợp lệ (PDF/PNG/JPG/XLSX)", 422
        )
    content = await file.read()
    data = attachment_service.create_attachment(
        db,
        user=user,
        owner_type="chemical",
        owner_id=chemical_id,
        file_name=file.filename or "msds",
        content=content,
        mime=file.content_type,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== lots under chemical =====
@router.get("/chemicals/{chemical_id}/lots")
def list_lots(
    chemical_id: uuid.UUID,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    display_unit: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, _meta, total = chemical_service.list_lots(
        db,
        chemical_id=chemical_id,
        status_filter=status_filter,
        display_unit=display_unit,
        page=page,
        limit=limit,
    )
    items = cc.strip_price_fields(items, cc.can_see_cost(db, user))
    return paginated(items, page=page, limit=limit, total=total)


@router.post("/chemicals/{chemical_id}/lots", status_code=status.HTTP_201_CREATED)
def create_lot(
    chemical_id: uuid.UUID,
    body: CreateLotRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    intake = body.initial_intake.model_dump() if body.initial_intake else None
    data = chemical_service.create_lot(
        db,
        user=user,
        chemical_id=chemical_id,
        lot_no=body.lot_no,
        received_at=body.received_at,
        expiry_date=body.expiry_date,
        recheck_date=body.recheck_date,
        initial_intake=intake,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    data = cc.strip_price_fields(data, cc.can_see_cost(db, user))
    return ok(data)


@router.get("/chemicals/{chemical_id}/fefo-suggestion")
def fefo(
    chemical_id: uuid.UUID,
    display_unit: Optional[str] = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        chemical_service.fefo_suggestion(
            db, chemical_id=chemical_id, display_unit=display_unit
        )
    )


@router.get("/chemicals/{chemical_id}/stock")
def stock(
    chemical_id: uuid.UUID,
    display_unit: Optional[str] = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(
        chemical_service.get_stock(
            db,
            chemical_id=chemical_id,
            display_unit=display_unit,
            can_cost=cc.can_see_cost(db, user),
        )
    )
