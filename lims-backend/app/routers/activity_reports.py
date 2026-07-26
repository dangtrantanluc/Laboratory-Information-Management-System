"""Router — báo cáo hoạt động hàng tháng (m25).

Người nộp (giảng viên/leader/lãnh đạo/KTV = admin/leader/lab_manager/staff) tạo báo cáo kỳ;
văn phòng/lãnh đạo/quản trị xem danh sách tổng hợp + duyệt. Dữ liệu dòng hoạt động đổ vào
các module đã có (Đề tài/Bài báo/Hợp đồng/Giảng dạy/Công tác khác) qua report_id.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.activity_report import CreateReportRequest
from app.services import activity_report_service as svc

router = APIRouter(tags=["m4-activity-reports"])


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("/activity-reports")
def list_reports(
    period: Optional[str] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = svc.list_reports(
        db, user=user, period=period, department_id=department_id,
        status=status_filter, page=page, limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("/activity-reports", status_code=status.HTTP_201_CREATED)
def create_report(
    body: CreateReportRequest, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    return ok(svc.create_report(
        db, user=user, payload=body.model_dump(), correlation_id=_cid(request), ip=_ip(request)))


@router.get("/activity-reports/{report_id}")
def get_report(
    report_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    return ok(svc.get_report(db, user=user, report_id=report_id))


@router.post("/activity-reports/{report_id}/review")
def review_report(
    report_id: uuid.UUID, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    return ok(svc.review_report(
        db, user=user, report_id=report_id, correlation_id=_cid(request), ip=_ip(request)))


@router.delete("/activity-reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(
    report_id: uuid.UUID, request: Request,
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    svc.delete_report(db, user=user, report_id=report_id, correlation_id=_cid(request), ip=_ip(request))
