"""Research report service M4 (#37b) — xuất Excel báo cáo thành tích §6.2 (FR-HR-018).

KHÔNG chứa lương (chỉ đếm thành tích). Reuse research_service.achievement_stats để giữ
1 nguồn số liệu (scope staff own + accountant 403 đã enforce ở router). Audit
RESEARCH_REPORT_EXPORT (đếm lượt tải — R15).
"""
import io
import uuid
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.services import audit_service, research_service


def export_stats_xlsx(
    db: Session,
    *,
    user: CurrentUser,
    group_by: str,
    user_id: Optional[uuid.UUID],
    department_id: Optional[uuid.UUID],
    date_from: Optional[date],
    date_to: Optional[date],
    level: Optional[str],
    category: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> bytes:
    stats = research_service.achievement_stats(
        db,
        user=user,
        group_by=group_by,
        user_id=user_id,
        department_id=department_id,
        date_from=date_from,
        date_to=date_to,
        level=level,
        category=category,
    )

    from openpyxl import Workbook  # local import — openpyxl chỉ cần khi xuất Excel

    wb = Workbook()
    ws = wb.active
    ws.title = "Thành tích NCKH"

    subject = stats.get("user_name") or stats.get("department_name") or ""
    ws.append(["BÁO CÁO THÀNH TÍCH NCKH (§6.2)"])
    ws.append(["Chiều tổng hợp", stats["group_by"]])
    ws.append(["Đối tượng", subject])
    period = stats.get("period", {})
    ws.append(["Khoảng thời gian", f"{period.get('from') or '-'} → {period.get('to') or '-'}"])
    ws.append([])
    ws.append(["Chỉ tiêu", "Số lượng"])
    ws.append(["Đề tài NCKH", stats["projects"]["total"]])
    for lv, cnt in stats["projects"]["by_level"].items():
        ws.append([f"  - Cấp {lv}", cnt])
    ws.append(["Bài báo", stats["publications"]["total"]])
    for idx, cnt in stats["publications"]["by_index"].items():
        ws.append([f"  - {idx}", cnt])
    ws.append(["Sáng chế / GPHI", stats["patents"]])
    ws.append(["Hướng dẫn SV", stats["mentorships"]])
    ws.append(["Lượt đăng ký lab (đã duyệt)", stats["lab_registrations_approved"]])
    ws.append(["Môn giảng dạy", stats["teaching_courses"]])
    ws.append(["Phục vụ cộng đồng", stats["community_services"]])

    audit_service.log_action(
        db,
        action="RESEARCH_REPORT_EXPORT",
        resource="research_achievement",
        user_id=user.id,
        resource_id=user_id or department_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"group_by": stats["group_by"]},
    )
    db.commit()

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
