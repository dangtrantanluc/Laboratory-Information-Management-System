"""Router BÁO GIÁ (m29) — /quotations.

Quyền: Phòng nhận mẫu + Quản trị + Ban lãnh đạo lập/sửa/xóa; mọi vai trò đã đăng nhập đọc.
Xuất Excel theo đúng mẫu "BẢNG BÁO GIÁ" của Viện.
"""
import uuid
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.request_meta import client_ip
from app.core.deps import CurrentUser, get_current_user
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.quotation import (
    ChangeQuotationStatusRequest,
    CreateQuotationRequest,
    UpdateQuotationRequest,
)
from app.services import quotation_export_service as export_svc
from app.services import quotation_service as svc

router = APIRouter(tags=["m29-quotations"])

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _cid(r: Request) -> Optional[str]:
    return getattr(r.state, "correlation_id", None)


@router.get("/quotations")
def list_quotations(
    q: Optional[str] = Query(default=None),
    status_: Optional[str] = Query(default=None, alias="status"),
    intake_id: Optional[uuid.UUID] = Query(default=None),
    page: Optional[int] = Query(default=None),
    limit: Optional[int] = Query(default=None, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p, lim = normalize_pagination(page, limit)
    items, total = svc.list_quotations(
        db, user=user, q=q, status=status_, intake_id=intake_id, page=p, limit=lim
    )
    return paginated(items, page=p, limit=lim, total=total)


@router.get("/quotations/{quotation_id}")
def get_quotation(
    quotation_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(svc.get_quotation(db, quotation_id=quotation_id))


@router.get("/quotations/{quotation_id}/export.xlsx")
def export_quotation_xlsx(
    quotation_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tải BẢNG BÁO GIÁ (.xlsx) đúng layout mẫu của Viện."""
    data = svc.get_quotation(db, quotation_id=quotation_id)
    content = export_svc.build_xlsx(data)
    safe_customer = (data.get("customer_name") or "").replace("/", "-")[:60]
    filename = f"BaoGia_{data['code']}_{safe_customer}.xlsx".replace(" ", "_")
    return Response(
        content=content,
        media_type=_XLSX_MIME,
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(filename)}"
            )
        },
    )


@router.post("/quotations", status_code=status.HTTP_201_CREATED)
def create_quotation(
    body: CreateQuotationRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(svc.create_quotation(
        db, user=user, fields=body.model_dump(), correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.post("/quotations/from-intake/{intake_id}", status_code=status.HTTP_201_CREATED)
def create_from_intake(
    intake_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tạo báo giá tự động từ các chỉ tiêu đã phân của phiếu nhận mẫu."""
    return ok(svc.create_from_intake(
        db, user=user, intake_id=intake_id, correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.patch("/quotations/{quotation_id}")
def update_quotation(
    quotation_id: uuid.UUID,
    body: UpdateQuotationRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(svc.update_quotation(
        db, user=user, quotation_id=quotation_id,
        changes=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.post("/quotations/{quotation_id}/status")
def change_status(
    quotation_id: uuid.UUID,
    body: ChangeQuotationStatusRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(svc.change_status(
        db, user=user, quotation_id=quotation_id, new_status=body.status,
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.delete("/quotations/{quotation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quotation(
    quotation_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc.delete_quotation(
        db, user=user, quotation_id=quotation_id, correlation_id=_cid(request), ip=client_ip(request),
    )
