"""Router M6 — Báo cáo & Thống kê (Reporting & Analytics).

9 endpoint client: dashboard + charts + reports/samples + reports/chemicals +
system-access (#10/#11) + export xlsx/pdf (#12/#13) + analytics/page-view (#14).

RBAC enforce TẦNG API: accountant không thấy mẫu (B03); staff ép phòng + strip tiền;
R15 chỉ admin/leader (audit:read). Cache dashboard 60s. Bộ lọc thời gian [from,to).

LƯU Ý thứ tự đăng ký: path tĩnh (/reports/samples, /reports/chemicals,
/reports/system-access) ĐĂNG KÝ TRƯỚC path động (/reports/{report_type}/export.*).
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.core.responses import ok
from app.db.database import get_db
from app.schemas.reporting import PageViewRequest
from app.services import (
    access_stat_service,
    dashboard_service,
    m6_export_service,
    m6_report_service,
    report_common as rc,
    system_access_service,
)

router = APIRouter(tags=["m6-reporting"])

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _csv(value: Optional[str]) -> Optional[list[str]]:
    if not value:
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


# ===================== M6.1 Dashboard =====================
@router.get("/dashboard")
def get_dashboard(
    department_id: Optional[uuid.UUID] = Query(default=None),
    due_within_days: int = Query(default=30, ge=1, le=90),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data, meta = dashboard_service.get_dashboard(
        db, user=user, department_id=department_id, due_within_days=due_within_days
    )
    return {"success": True, "data": data, "meta": meta}


@router.get("/dashboard/charts")
def get_charts(
    date_from: Optional[date] = Query(default=None, alias="from"),
    date_to: Optional[date] = Query(default=None, alias="to"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    group_by: str = Query(default="month"),
    charts: Optional[str] = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chart_list = _csv(charts)
    if chart_list:
        valid = {"samples_by_status", "samples_over_time", "chemical_consumption"}
        bad = [c for c in chart_list if c not in valid]
        if bad:
            raise rc.err("VALIDATION_ERROR", f"charts không hợp lệ: {bad}")
    data, meta = dashboard_service.get_charts(
        db, user=user, date_from=date_from, date_to=date_to,
        department_id=department_id, group_by=group_by, charts=chart_list,
    )
    return {"success": True, "data": data, "meta": meta}


# ===================== M6.2 Reports theo thời gian (tĩnh) =====================
@router.get("/reports/samples")
def report_samples(
    date_from: Optional[date] = Query(default=None, alias="from"),
    date_to: Optional[date] = Query(default=None, alias="to"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    group_by: str = Query(default="month"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    time_field: str = Query(default="received_at"),
    breakdown: str = Query(default="status"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data, meta = m6_report_service.report_samples(
        db, user=user, date_from=date_from, date_to=date_to,
        department_id=department_id, group_by=group_by,
        status_filter=status_filter, time_field=time_field, breakdown=breakdown,
    )
    return {"success": True, "data": data, "meta": meta}


@router.get("/reports/chemicals")
def report_chemicals(
    date_from: Optional[date] = Query(default=None, alias="from"),
    date_to: Optional[date] = Query(default=None, alias="to"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    group_by: str = Query(default="month"),
    measurement_group: Optional[str] = Query(default=None, alias="type"),
    chemical_id: Optional[uuid.UUID] = Query(default=None),
    metric: str = Query(default="consumption"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data, meta = m6_report_service.report_chemicals(
        db, user=user, date_from=date_from, date_to=date_to,
        department_id=department_id, group_by=group_by,
        measurement_group=measurement_group, chemical_id=chemical_id, metric=metric,
    )
    return {"success": True, "data": data, "meta": meta}


# ===================== M6.3 System access (R15) — admin/leader CHỈ =====================
@router.get("/reports/system-access")
def system_access(
    date_from: Optional[date] = Query(default=None, alias="from"),
    date_to: Optional[date] = Query(default=None, alias="to"),
    group_by: str = Query(default="month"),
    filter_user_id: Optional[uuid.UUID] = Query(default=None, alias="user_id"),
    action_type: str = Query(default="all"),
    top_n: int = Query(default=10, ge=1, le=50),
    include_timeline: bool = Query(default=False),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rc.require_audit_read(db, user)  # BR-RPT-010 — chỉ admin/leader
    data, meta = system_access_service.system_access(
        db, user=user, date_from=date_from, date_to=date_to, group_by=group_by,
        filter_user_id=filter_user_id, action_type=action_type,
        top_n=top_n, include_timeline=include_timeline,
    )
    return {"success": True, "data": data, "meta": meta}


@router.get("/reports/system-access/users/{user_id}")
def system_access_user(
    user_id: uuid.UUID,
    date_from: Optional[date] = Query(default=None, alias="from"),
    date_to: Optional[date] = Query(default=None, alias="to"),
    recent_actions: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rc.require_audit_read(db, user)  # BR-RPT-010
    data, meta = system_access_service.user_detail(
        db, user=user, target_user_id=user_id,
        date_from=date_from, date_to=date_to, recent_actions=recent_actions,
    )
    return {"success": True, "data": data, "meta": meta}


# ===================== M6.4 Export (động — đăng ký SAU path tĩnh) =====================
@router.get("/reports/{report_type}/export.xlsx")
def export_xlsx(
    report_type: str,
    request: Request,
    date_from: Optional[date] = Query(default=None, alias="from"),
    date_to: Optional[date] = Query(default=None, alias="to"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    group_by: str = Query(default="month"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    time_field: str = Query(default="received_at"),
    breakdown: str = Query(default="status"),
    measurement_group: Optional[str] = Query(default=None, alias="type"),
    chemical_id: Optional[uuid.UUID] = Query(default=None),
    metric: str = Query(default="consumption"),
    filter_user_id: Optional[uuid.UUID] = Query(default=None, alias="user_id"),
    action_type: str = Query(default="all"),
    top_n: int = Query(default=10, ge=1, le=50),
    due_within_days: int = Query(default=30, ge=1, le=90),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    params = {
        "date_from": date_from, "date_to": date_to, "department_id": department_id,
        "group_by": group_by, "status": status_filter, "time_field": time_field,
        "breakdown": breakdown, "type": measurement_group, "chemical_id": chemical_id,
        "metric": metric, "user_id": filter_user_id, "action_type": action_type,
        "top_n": top_n, "due_within_days": due_within_days,
    }
    content, filename = m6_export_service.export_xlsx(
        db, user=user, report_type=report_type, params=params,
        correlation_id=_cid(request), ip=_ip(request),
    )
    return Response(
        content=content,
        media_type=_XLSX_MIME,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Correlation-Id": _cid(request) or "",
        },
    )


@router.get("/reports/{report_type}/export.pdf")
def export_pdf(
    report_type: str,
    request: Request,
    date_from: Optional[date] = Query(default=None, alias="from"),
    date_to: Optional[date] = Query(default=None, alias="to"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    due_within_days: int = Query(default=30, ge=1, le=90),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    params = {
        "date_from": date_from, "date_to": date_to,
        "department_id": department_id, "due_within_days": due_within_days,
    }
    content, filename = m6_export_service.export_pdf(
        db, user=user, report_type=report_type, params=params,
        correlation_id=_cid(request), ip=_ip(request),
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Correlation-Id": _cid(request) or "",
        },
    )


# ===================== Hạ tầng access_stats (#14) =====================
@router.post("/analytics/page-view", status_code=status.HTTP_204_NO_CONTENT)
def page_view(
    body: PageViewRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FE (SPA) ghi 1 lượt xem trang chính. Best-effort, luôn 204 (BR-RPT-013)."""
    path = body.path
    # chỉ ghi nếu path thuộc whitelist trang chính (BR-RPT-005); ngoài → bỏ qua âm thầm
    if access_stat_service.is_whitelisted(path):
        access_stat_service.record(
            db, user_id=user.id, path=path, method="PAGE_VIEW",
            status_code=200, ip=_ip(request), event_type="page_view",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
