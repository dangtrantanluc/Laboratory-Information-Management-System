"""M6 export service (M6.4) — xuất Excel/PDF báo cáo tổng hợp (#12/#13).

Áp RBAC scope vào NỘI DUNG file (NFR-SEC-RPT-002): accountant không xuất samples (403);
staff chỉ phòng mình + không cột tiền; system-access chỉ admin/leader. Ghi audit
REPORT_EXPORT (BR-RPT-012). Tái dùng service tổng hợp (dashboard/report/system-access)
để file = đúng dữ liệu trên màn (consistency).
"""
import io
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.services import (
    audit_service,
    dashboard_service,
    m6_report_service,
    report_common as rc,
    system_access_service,
)

SUPPORTED_REPORT_TYPES = ("dashboard", "samples", "chemicals", "system-access")
PDF_SUPPORTED = ("dashboard",)  # bản đầu chỉ dashboard có template PDF (OQ#3)


def _check_report_type(report_type: str) -> None:
    if report_type not in SUPPORTED_REPORT_TYPES:
        raise rc.err(
            "REPORT_TYPE_NOT_FOUND",
            f"Loại báo cáo '{report_type}' không hỗ trợ", 404,
        )


def _enforce_export_rbac(db: Session, user: CurrentUser, report_type: str) -> None:
    if report_type == "samples":
        rc.deny_accountant_samples(user)  # accountant 403
    if report_type == "system-access":
        rc.require_audit_read(db, user)  # chỉ admin/leader


def _gather(
    db: Session, user: CurrentUser, report_type: str, params: dict
) -> dict:
    """Lấy data đã áp scope từ service tổng hợp tương ứng."""
    if report_type == "dashboard":
        data, _meta = dashboard_service.get_dashboard(
            db, user=user,
            department_id=params.get("department_id"),
            due_within_days=params.get("due_within_days", 30),
        )
        return data
    if report_type == "samples":
        data, _meta = m6_report_service.report_samples(
            db, user=user,
            date_from=params.get("date_from"), date_to=params.get("date_to"),
            department_id=params.get("department_id"),
            group_by=params.get("group_by", "month"),
            status_filter=params.get("status"),
            time_field=params.get("time_field", "received_at"),
            breakdown=params.get("breakdown", "status"),
        )
        return data
    if report_type == "chemicals":
        data, _meta = m6_report_service.report_chemicals(
            db, user=user,
            date_from=params.get("date_from"), date_to=params.get("date_to"),
            department_id=params.get("department_id"),
            group_by=params.get("group_by", "month"),
            measurement_group=params.get("type"),
            chemical_id=params.get("chemical_id"),
            metric=params.get("metric", "consumption"),
        )
        return data
    # system-access
    data, _meta = system_access_service.system_access(
        db, user=user,
        date_from=params.get("date_from"), date_to=params.get("date_to"),
        group_by=params.get("group_by", "month"),
        filter_user_id=params.get("user_id"),
        action_type=params.get("action_type", "all"),
        top_n=params.get("top_n", 10),
        include_timeline=True,
    )
    return data


def _audit_export(
    db: Session, user: CurrentUser, report_type: str, fmt: str,
    params: dict, correlation_id: Optional[str], ip: Optional[str],
) -> None:
    audit_service.log_action(
        db,
        action="REPORT_EXPORT",
        resource="report",
        user_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={
            "report_type": report_type,
            "format": fmt,
            "from": str(params.get("date_from")) if params.get("date_from") else None,
            "to": str(params.get("date_to")) if params.get("date_to") else None,
            "scope_role": user.role,
            "scope_department": str(params.get("department_id"))
            if params.get("department_id") else None,
        },
    )
    db.commit()


# ======================= XLSX (#12) =======================
def export_xlsx(
    db: Session, *, user: CurrentUser, report_type: str, params: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> tuple[bytes, str]:
    _check_report_type(report_type)
    _enforce_export_rbac(db, user, report_type)
    data = _gather(db, user, report_type, params)

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = report_type[:31]
    ws.append([f"Báo cáo: {report_type}", f"Người xuất: {user.full_name}", f"Vai trò: {user.role}"])
    _write_sheet(ws, report_type, data)

    _audit_export(db, user, report_type, "xlsx", params, correlation_id, ip)
    buf = io.BytesIO()
    wb.save(buf)
    filename = f"bao-cao-{report_type}.xlsx"
    return buf.getvalue(), filename


def _write_sheet(ws, report_type: str, data: dict) -> None:
    ws.append([])
    if report_type == "dashboard":
        for block, content in data.items():
            if block == "scope" or not isinstance(content, dict):
                continue
            ws.append([f"== {block} =="])
            for k, v in content.items():
                if isinstance(v, (dict, list)):
                    ws.append([k, str(v)])
                else:
                    ws.append([k, v])
            ws.append([])
    elif report_type == "samples":
        ws.append(["Tổng số mẫu", data.get("total", 0)])
        ws.append([])
        ws.append(["Trạng thái", "Số lượng"])
        for s, c in (data.get("by_status") or {}).items():
            ws.append([s, c])
        ws.append([])
        ws.append(["Kỳ", "Số mẫu"])
        for row in data.get("by_time", []):
            ws.append([row["period"], row["count"]])
    elif report_type == "chemicals":
        has_cost = any("consumption_cost" in g for g in data.get("by_measurement_group", []))
        header = ["Nhóm đo", "Đơn vị base", "Tổng lượng"] + (["Chi phí"] if has_cost else [])
        ws.append(header)
        for g in data.get("by_measurement_group", []):
            row = [g["measurement_group"], g["base_unit"], g["total_qty"]]
            if has_cost:
                row.append(g.get("consumption_cost", ""))
            ws.append(row)
        if "total_cost" in data:
            ws.append(["Tổng chi phí", "", "", data["total_cost"]])
    else:  # system-access
        totals = data.get("totals", {})
        ws.append(["Lượt truy cập", totals.get("access_count", 0)])
        ws.append(["Lượt tải", totals.get("download_count", 0)])
        ws.append(["Lượt chỉnh sửa", totals.get("edit_count", 0)])
        ws.append([])
        ws.append(["Kỳ", "Truy cập", "Tải", "Chỉnh sửa"])
        for row in data.get("timeline", []):
            ws.append([
                row["period"], row["access_count"],
                row["download_count"], row["edit_count"],
            ])


# ======================= PDF (#13) =======================
def export_pdf(
    db: Session, *, user: CurrentUser, report_type: str, params: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> tuple[bytes, str]:
    _check_report_type(report_type)
    if report_type not in PDF_SUPPORTED:
        raise rc.err(
            "PDF_NOT_SUPPORTED",
            f"Báo cáo '{report_type}' chưa hỗ trợ xuất PDF (bản đầu chỉ dashboard)", 422,
        )
    _enforce_export_rbac(db, user, report_type)
    data = _gather(db, user, report_type, params)

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "BAO CAO TONG HOP - DASHBOARD")
    y -= 24
    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Nguoi xuat: {user.full_name} ({user.role})")
    y -= 24
    for block, content in data.items():
        if block == "scope" or not isinstance(content, dict):
            continue
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, f"[{block}]")
        y -= 16
        c.setFont("Helvetica", 10)
        for k, v in content.items():
            if isinstance(v, (dict, list)):
                continue
            c.drawString(70, y, f"{k}: {v}")
            y -= 14
            if y < 60:
                c.showPage()
                y = height - 60
        y -= 8
    c.showPage()
    c.save()

    _audit_export(db, user, report_type, "pdf", params, correlation_id, ip)
    filename = f"bao-cao-{report_type}.pdf"
    return buf.getvalue(), filename
