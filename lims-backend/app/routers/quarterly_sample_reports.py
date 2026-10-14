"""Router Báo cáo mẫu phân tích theo quý — m54 — /quarterly-sample-reports.

Lab (staff / lab_manager thuộc phòng) nhập và nộp báo cáo của phòng mình; Văn phòng
và admin xem toàn Viện, trả lại / chốt / mở khoá, xuất Excel; Ban lãnh đạo chỉ xem.
Phạm vi dữ liệu theo phòng do service quyết định — router chỉ chặn ở mức "có quyền đọc".

Các đường dẫn tĩnh (/overview, /stats, /current, /export.xlsx) khai TRƯỚC /{report_id}.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_permission
from app.core.rate_limit import rate_limit
from app.core.request_meta import client_ip
from app.core.responses import ok
from app.db.database import get_db
from app.schemas.quarterly_sample_report import (
    BatchSampleReportItemsRequest,
    CurrentSampleReportResponse,
    EnsureSampleReportRequest,
    ReasonRequest,
    SampleReportItemRequest,
    SampleReportItemResponse,
    SampleReportOverviewResponse,
    SampleReportResponse,
    SampleReportStatsResponse,
    SubmitSampleReportRequest,
)
from app.services import quarterly_sample_report_excel as excel
from app.services import quarterly_sample_report_service as svc
from app.services import quarterly_sample_report_stats as stats_svc

router = APIRouter(prefix="/quarterly-sample-reports", tags=["quarterly-sample-reports"])

_read = require_permission("quarterly_sample_report", "read")
_write = require_permission("quarterly_sample_report", "write")
_review = require_permission("quarterly_sample_report", "review")


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


@router.get("/overview", response_model=SampleReportOverviewResponse)
def overview(
    year: int = Query(ge=2000, le=2100),
    quarter: int = Query(ge=1, le=4),
    user: CurrentUser = Depends(_read),
    db: Session = Depends(get_db),
):
    """Tình trạng nộp của mọi phòng lab trong quý (Văn phòng / Ban lãnh đạo)."""
    return ok(svc.overview(db, user=user, year=year, quarter=quarter))


@router.get("/stats", response_model=SampleReportStatsResponse)
def stats(
    year: int = Query(ge=2000, le=2100),
    quarter: Optional[int] = Query(default=None, ge=1, le=4, description="Bỏ trống = cả năm"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    include_unlocked: bool = Query(default=False, description="true = gồm cả báo cáo chưa chốt"),
    user: CurrentUser = Depends(_read),
    db: Session = Depends(get_db),
):
    """Thống kê số mẫu theo phòng × quý × loại mẫu + chỉ tiêu phân tích nhiều nhất."""
    return ok(stats_svc.stats(
        db, user=user, year=year, quarter=quarter, department_id=department_id,
        include_unlocked=include_unlocked,
    ))


@router.get("/current", response_model=CurrentSampleReportResponse)
def current(
    year: int = Query(ge=2000, le=2100),
    quarter: int = Query(ge=1, le=4),
    department_id: Optional[uuid.UUID] = Query(
        default=None, description="Bỏ trống = phòng của người đang đăng nhập"
    ),
    user: CurrentUser = Depends(_read),
    db: Session = Depends(get_db),
):
    """Báo cáo của một phòng trong một quý — `report` là null nếu phòng chưa lập."""
    return ok(svc.get_current(
        db, user=user, year=year, quarter=quarter, department_id=department_id,
    ))


@router.get(
    "/export.xlsx",
    # Trả file nhị phân — khai tường minh để test hợp đồng API bỏ qua response_model.
    response_class=Response,
    dependencies=[Depends(rate_limit("quarterly-sample-export", limit=20, window_seconds=60))],
)
def export_xlsx(
    request: Request,
    year: int = Query(ge=2000, le=2100),
    quarter: int = Query(ge=1, le=4),
    include_unlocked: bool = Query(
        default=False, description="true = gồm cả báo cáo chưa chốt (xem nháp giữa kỳ)"
    ),
    user: CurrentUser = Depends(_read),
    db: Session = Depends(get_db),
):
    """Excel toàn Viện theo đúng mẫu của Văn phòng, kèm sheet tình trạng nộp."""
    content, filename = excel.export_xlsx(
        db, user=user, year=year, quarter=quarter, include_unlocked=include_unlocked,
        correlation_id=_cid(request), ip=client_ip(request),
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("", response_model=SampleReportResponse)
def ensure_report(
    body: EnsureSampleReportRequest,
    request: Request,
    user: CurrentUser = Depends(_write),
    db: Session = Depends(get_db),
):
    """Lấy hoặc lập báo cáo quý cho phòng của mình — gọi lại vẫn chỉ ra một bản."""
    return ok(svc.ensure_report(
        db, user=user, year=body.year, quarter=body.quarter,
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.get("/{report_id}", response_model=SampleReportResponse)
def get_report(
    report_id: uuid.UUID,
    user: CurrentUser = Depends(_read),
    db: Session = Depends(get_db),
):
    return ok(svc.get_report(db, user=user, report_id=report_id))


@router.post(
    "/{report_id}/items", status_code=status.HTTP_201_CREATED,
    response_model=SampleReportItemResponse,
)
def create_item(
    report_id: uuid.UUID,
    body: SampleReportItemRequest,
    request: Request,
    user: CurrentUser = Depends(_write),
    db: Session = Depends(get_db),
):
    return ok(svc.create_item(
        db, user=user, report_id=report_id, body=body.model_dump(),
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.post(
    "/{report_id}/items/batch", status_code=status.HTTP_201_CREATED,
    response_model=SampleReportResponse,
)
def create_items_batch(
    report_id: uuid.UUID,
    body: BatchSampleReportItemsRequest,
    request: Request,
    user: CurrentUser = Depends(_write),
    db: Session = Depends(get_db),
):
    """Nhập nhiều mẫu một lần. Có dòng lỗi thì không lưu gì — lỗi trả về theo từng dòng."""
    return ok(svc.create_items_batch(
        db, user=user, report_id=report_id, items=[i.model_dump() for i in body.items],
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.put("/{report_id}/items/{item_id}", response_model=SampleReportItemResponse)
def update_item(
    report_id: uuid.UUID,
    item_id: uuid.UUID,
    body: SampleReportItemRequest,
    request: Request,
    user: CurrentUser = Depends(_write),
    db: Session = Depends(get_db),
):
    return ok(svc.update_item(
        db, user=user, report_id=report_id, item_id=item_id, body=body.model_dump(),
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.delete("/{report_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    report_id: uuid.UUID,
    item_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(_write),
    db: Session = Depends(get_db),
):
    svc.delete_item(
        db, user=user, report_id=report_id, item_id=item_id,
        correlation_id=_cid(request), ip=client_ip(request),
    )


@router.post("/{report_id}/submit", response_model=SampleReportResponse)
def submit(
    report_id: uuid.UUID,
    body: SubmitSampleReportRequest,
    request: Request,
    user: CurrentUser = Depends(_write),
    db: Session = Depends(get_db),
):
    return ok(svc.submit(
        db, user=user, report_id=report_id, lab_note=body.lab_note,
        confirm_empty=body.confirm_empty, correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.post("/{report_id}/return", response_model=SampleReportResponse)
def return_report(
    report_id: uuid.UUID,
    body: ReasonRequest,
    request: Request,
    user: CurrentUser = Depends(_review),
    db: Session = Depends(get_db),
):
    return ok(svc.return_report(
        db, user=user, report_id=report_id, reason=body.reason,
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.post("/{report_id}/lock", response_model=SampleReportResponse)
def lock(
    report_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(_review),
    db: Session = Depends(get_db),
):
    return ok(svc.lock(
        db, user=user, report_id=report_id, correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.post("/{report_id}/reopen", response_model=SampleReportResponse)
def reopen(
    report_id: uuid.UUID,
    body: ReasonRequest,
    request: Request,
    user: CurrentUser = Depends(_review),
    db: Session = Depends(get_db),
):
    return ok(svc.reopen(
        db, user=user, report_id=report_id, reason=body.reason,
        correlation_id=_cid(request), ip=client_ip(request),
    ))
