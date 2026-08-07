"""Router BÁO GIÁ (m29) — /quotations.

Quyền: Phòng nhận mẫu + Quản trị + Ban lãnh đạo lập/sửa/xóa.

ĐỌC — ĐÃ SIẾT: trước đây docstring ghi "mọi vai trò đã đăng nhập đọc" và ba endpoint
đọc chỉ có `get_current_user`, nên bất kỳ tài khoản nào (kể cả KTV phòng lab) cũng
liệt kê và xuất Excel được toàn bộ báo giá — gồm tên/địa chỉ/email/điện thoại khách
hàng và đơn giá từng chỉ tiêu. Trong khi module `customers` giữ CÙNG loại dữ liệu lại
giới hạn vai trò và CẤM `office` (B03). Hai luật không thể cùng đúng.

Danh sách vai trò dưới đây lấy từ chính frontend — `nav.ts` chỉ hiện menu "Báo giá"
cho ['admin', 'leader', 'reception', 'office'] — nên đây KHÔNG phải thay đổi nghiệp vụ,
chỉ là bắt backend enforce đúng thứ giao diện vốn đã giả định. (Route guard
`canViewQuotations` trả `!!user` nên vẫn vào thẳng URL được — đã siết kèm.)
Xuất Excel theo đúng mẫu "BẢNG BÁO GIÁ" của Viện.
"""
import uuid
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.request_meta import client_ip
from app.core.concurrency import export_slot
from app.core.deps import CurrentUser, get_current_user, require_roles
from app.core.rate_limit import rate_limit
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

# Đọc báo giá — khớp nav.ts của frontend. Ghi vẫn qua quotation_service._assert_manage.
quotation_read = require_roles("admin", "leader", "reception", "office")


def _cid(r: Request) -> Optional[str]:
    return getattr(r.state, "correlation_id", None)


@router.get("/quotations")
def list_quotations(
    q: Optional[str] = Query(default=None),
    status_: Optional[str] = Query(default=None, alias="status"),
    intake_id: Optional[uuid.UUID] = Query(default=None),
    page: Optional[int] = Query(default=None),
    limit: Optional[int] = Query(default=None, le=100),
    user: CurrentUser = Depends(quotation_read),
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
    user: CurrentUser = Depends(quotation_read),
    db: Session = Depends(get_db),
):
    return ok(svc.get_quotation(db, quotation_id=quotation_id))


@router.get(
    "/quotations/{quotation_id}/export.xlsx",
    dependencies=[Depends(rate_limit("report-export", limit=10, window_seconds=60))],
)
def export_quotation_xlsx(
    quotation_id: uuid.UUID,
    user: CurrentUser = Depends(quotation_read),
    db: Session = Depends(get_db),
):
    """Tải BẢNG BÁO GIÁ (.xlsx) đúng layout mẫu của Viện.

    export_slot(): sinh Excel bằng openpyxl là CPU-bound. Semaphore này đã tồn tại và
    được các đường xuất khác dùng, riêng đây thì không — nên một người gọi vòng lặp
    chiếm được CPU của cả 4 worker.
    """
    with export_slot():
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
