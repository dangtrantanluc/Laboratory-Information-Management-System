"""Sample result report PDF (M1, FR-016) — xuất phiếu kết quả thử nghiệm bằng reportlab.

Chỉ khi mẫu done (SAMPLE_NOT_FINALIZED nếu chưa). Hiển thị mã phiếu/mã mẫu, khách gửi,
tình trạng, danh sách chỉ tiêu + kết quả approved (version hiện tại), người thực hiện/duyệt.
Lần đầu xuất: done → returned. Lưu PDF vào attachments. Audit lượt tải (R15).
"""
import io
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.customer import Customer
from app.models.overdue_reason import OverdueReason
from app.models.sample_assignment import SampleAssignment
from app.models.sample_result import SampleResult
from app.models.test_request import TestRequest
from app.services import audit_service, sample_common, storage_service


def _build_pdf(db: Session, sample, req: TestRequest) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("PHIẾU KẾT QUẢ THỬ NGHIỆM", styles["Title"]))
    elements.append(Paragraph("Theo ISO/IEC 17025:2017", styles["Normal"]))
    elements.append(Spacer(1, 8 * mm))

    customer_name = "-"
    if req.customer_id:
        c = db.get(Customer, req.customer_id)
        customer_name = c.name if c else "-"

    info = [
        ["Mã phiếu:", req.request_code, "Mã mẫu:", sample.sample_code],
        ["Khách gửi:", customer_name, "Người gửi:", req.sender_name or "-"],
        [
            "Phòng:",
            sample_common.dept_name(db, sample.department_id) or "-",
            "Tình trạng mẫu:",
            sample.condition_status or "-",
        ],
        [
            "Ngày nhận:",
            sample.received_at.strftime("%d/%m/%Y %H:%M"),
            "Hoàn thành:",
            sample.completed_at.strftime("%d/%m/%Y %H:%M") if sample.completed_at else "-",
        ],
    ]
    info_table = Table(info, colWidths=[30 * mm, 55 * mm, 30 * mm, 55 * mm])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(info_table)
    elements.append(Spacer(1, 6 * mm))

    # Bảng kết quả approved
    elements.append(Paragraph("Kết quả thử nghiệm", styles["Heading3"]))
    rows = [["Chỉ tiêu", "Kết quả", "Người thực hiện", "Người duyệt"]]
    assignments = db.execute(
        select(SampleAssignment)
        .where(SampleAssignment.sample_id == sample.id)
        .order_by(SampleAssignment.assigned_at.asc())
    ).scalars().all()
    for a in assignments:
        result = db.execute(
            select(SampleResult).where(
                SampleResult.assignment_id == a.id,
                SampleResult.is_current.is_(True),
                SampleResult.approved_by.isnot(None),
            )
        ).scalar_one_or_none()
        if result is None:
            continue
        rd = result.result_data
        value = rd.get("value") if isinstance(rd, dict) else None
        unit = rd.get("unit", "") if isinstance(rd, dict) else ""
        result_str = f"{value} {unit}".strip() if value is not None else str(rd)
        rows.append(
            [
                a.part_name,
                result_str,
                sample_common.user_name(db, result.entered_by) or "-",
                sample_common.user_name(db, result.approved_by) or "-",
            ]
        )
    result_table = Table(rows, colWidths=[50 * mm, 50 * mm, 35 * mm, 35 * mm])
    result_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(result_table)
    elements.append(Spacer(1, 8 * mm))
    elements.append(
        Paragraph(
            f"Xuất ngày {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC",
            styles["Italic"],
        )
    )

    doc.build(elements)
    return buf.getvalue()


def export_report(
    db: Session,
    *,
    user: CurrentUser,
    sample_id: uuid.UUID,
    reissue: bool,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> tuple[bytes, str]:
    sample = sample_common.get_sample_or_404(db, sample_id, lock=True)

    if not sample_common.can_lead_action(user, sample.department_id):
        raise sample_common.forbidden("Chỉ trưởng nhóm / lãnh đạo / admin được ban hành phiếu")

    if sample.status not in ("done", "returned"):
        raise AppException(
            "SAMPLE_NOT_FINALIZED", "Mẫu chưa được chốt hoàn thành", 422
        )

    # mẫu từng overdue chưa nhập lý do trễ → chặn
    if sample.completed_at and sample.completed_at > sample.deadline_at:
        has_reason = db.execute(
            select(func.count())
            .select_from(OverdueReason)
            .where(OverdueReason.sample_id == sample.id)
        ).scalar_one() > 0
        if not has_reason:
            raise AppException(
                "OVERDUE_REASON_REQUIRED",
                "Mẫu trễ hạn phải nhập lý do trễ trước khi xuất phiếu",
                422,
            )

    req = db.get(TestRequest, sample.request_id)
    pdf_bytes = _build_pdf(db, sample, req)

    # Lần đầu xuất (done) → chuyển returned + lưu PDF
    first_issue = sample.status == "done" and not reissue
    if first_issue:
        sample_common.change_status(
            db,
            sample,
            "returned",
            trigger="report_export",
            user_id=user.id,
            correlation_id=correlation_id,
            ip=ip,
        )
        # Lưu PDF vào MinIO + attachments
        file_name = f"result-{sample.sample_code}.pdf"
        file_key = storage_service.build_object_key("sample", sample.id, file_name)
        storage_service.put_object(file_key, pdf_bytes, content_type="application/pdf")
        from app.models.attachment import Attachment

        att = Attachment(
            owner_type="sample",
            owner_id=sample.id,
            file_key=file_key,
            file_name=file_name,
            mime="application/pdf",
            size=len(pdf_bytes),
            uploaded_by=user.id,
        )
        db.add(att)

    audit_service.log_action(
        db,
        action="SAMPLE_REPORT_EXPORT",
        resource="sample",
        user_id=user.id,
        resource_id=sample.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"reissue": reissue, "first_issue": first_issue},
    )
    db.commit()
    return pdf_bytes, f"result-{sample.sample_code}.pdf"
