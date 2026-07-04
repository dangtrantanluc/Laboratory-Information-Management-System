"""Router M2 — lô (chi tiết, CoA, giao dịch in/out/adjust, kiểm tra lại) + lịch sử giao dịch.

Giao dịch IMMUTABLE: chỉ POST tạo; KHÔNG có PUT/PATCH/DELETE (BR-CHEM-015).
Endpoint giao dịch dùng row-lock + transaction trong service (chống race).
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.chemical import CreateRecheckRequest, CreateTransactionRequest
from app.services import chemical_common as cc, chemical_service, chemical_txn_service

router = APIRouter(tags=["m2-lots"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# ===== global transactions list (đăng ký trước /lots/{id} để tránh nuốt path) =====
@router.get("/transactions")
def list_transactions(
    chemical_id: Optional[uuid.UUID] = Query(default=None),
    lot_id: Optional[uuid.UUID] = Query(default=None),
    ref_sample_id: Optional[uuid.UUID] = Query(default=None),
    by_user: Optional[uuid.UUID] = Query(default=None),
    type: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    display_unit: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = chemical_txn_service.list_transactions(
        db,
        chemical_id=chemical_id,
        lot_id=lot_id,
        ref_sample_id=ref_sample_id,
        by_user=by_user,
        txn_type=type,
        date_from=date_from,
        date_to=date_to,
        department_id=department_id,
        display_unit=display_unit,
        page=page,
        limit=limit,
        can_cost=cc.can_see_cost(db, user),
    )
    return paginated(items, page=page, limit=limit, total=total)


# ===== lot detail / coa =====
@router.get("/lots/{lot_id}")
def get_lot(
    lot_id: uuid.UUID,
    display_unit: Optional[str] = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = chemical_service.get_lot_detail(db, lot_id=lot_id, display_unit=display_unit)
    data = cc.strip_price_fields(data, cc.can_see_cost(db, user))
    return ok(data)


@router.get("/lots/{lot_id}/coa")
def get_coa(
    lot_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(chemical_service.get_coa(db, lot_id=lot_id))


@router.post("/lots/{lot_id}/coa", status_code=status.HTTP_201_CREATED)
async def upload_coa(
    lot_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload/ghi đè chứng chỉ phân tích (CoA) cho lô hóa chất."""
    content = await file.read()
    data = chemical_service.upload_coa(
        db,
        user=user,
        lot_id=lot_id,
        file_name=file.filename or "coa",
        content=content,
        mime=file.content_type,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


# ===== transactions (in/out/adjust) =====
@router.post("/lots/{lot_id}/transactions", status_code=status.HTTP_201_CREATED)
def create_transaction(
    lot_id: uuid.UUID,
    body: CreateTransactionRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = chemical_txn_service.create_transaction(
        db,
        user=user,
        lot_id=lot_id,
        payload=body.model_dump(),
        correlation_id=_cid(request),
        ip=_ip(request),
        can_cost=cc.can_see_cost(db, user),
    )
    return ok(data)


# ===== rechecks =====
@router.post("/lots/{lot_id}/rechecks", status_code=status.HTTP_201_CREATED)
def create_recheck(
    lot_id: uuid.UUID,
    body: CreateRecheckRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = chemical_txn_service.create_recheck(
        db,
        user=user,
        lot_id=lot_id,
        result=body.result,
        checked_at=body.checked_at,
        next_recheck_date=body.next_recheck_date,
        note=body.note,
        attachment_file_key=body.attachment_file_key,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)
