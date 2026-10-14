"""Models Báo cáo mẫu phân tích theo quý (Quarterly Sample Report) — m54.

KHÔNG nhầm với "phiếu kết quả mẫu" (sample_report_service, test_reports): đây là bảng
thống kê mẫu các phòng lab nộp cho Văn phòng mỗi quý.

Các phòng lab nhập mẫu đã phân tích trong quý, nộp cho Văn phòng; Văn phòng trả lại
hoặc chốt rồi xuất Excel toàn Viện. Xem docstring migration m54.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint, Date, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

VALID_REPORT_STATUS = ("draft", "submitted", "returned", "locked")
REPORT_STATUS_LABELS = {
    "draft": "Đang nhập",
    "submitted": "Đã nộp",
    "returned": "Bị trả lại",
    "locked": "Đã chốt",
}
# Lab chỉ sửa được khi báo cáo đang ở tay mình.
EDITABLE_STATUS = ("draft", "returned")


class QuarterlyReport(Base):
    __tablename__ = "quarterly_sample_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    quarter: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default=text("'draft'"))
    lab_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # Dùng chung cho "trả lại" và "mở khoá" — cả hai đều đưa báo cáo về tay lab kèm lý do.
    returned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    returned_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    return_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("department_id", "year", "quarter", name="uq_sample_report_period"),
        CheckConstraint("quarter BETWEEN 1 AND 4", name="ck_sample_report_quarter"),
        CheckConstraint("year BETWEEN 2000 AND 2100", name="ck_sample_report_year"),
        CheckConstraint(
            "status IN ('draft','submitted','returned','locked')", name="ck_sample_report_status"
        ),
    )


class QuarterlyReportItem(Base):
    __tablename__ = "quarterly_sample_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quarterly_sample_reports.id", ondelete="CASCADE"), nullable=False
    )
    # Không unique: một mẫu có thể được nhiều phòng phân tích (mỗi phòng một phần chỉ tiêu).
    sample_code: Mapped[str] = mapped_column(String(50), nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    matrix: Mapped[str] = mapped_column(String(24), nullable=False)  # VALID_TEST_MATRIX
    matrix_other: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # số mẫu vật lý
    extra_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)  # ngoài danh mục
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_sri_quantity"),
        CheckConstraint(
            "matrix IN ('soil','water','fertilizer','feed','food','quarantine','molecular','other')",
            name="ck_sri_matrix",
        ),
        CheckConstraint("matrix <> 'other' OR matrix_other IS NOT NULL", name="ck_sri_matrix_other"),
    )


class QuarterlyReportItemCriterion(Base):
    """Chỉ tiêu chọn từ danh mục — kèm BẢN CHỤP tên lúc nhập (báo cáo đã chốt không đổi theo)."""

    __tablename__ = "quarterly_sample_item_criteria"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quarterly_sample_items.id", ondelete="CASCADE"), nullable=False
    )
    test_parameter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_parameters.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
