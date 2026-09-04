"""Models BÁO GIÁ (m29) — theo mẫu "BẢNG BÁO GIÁ" của Viện.

quotations: đầu báo giá (khách hàng snapshot, hiệu lực, VAT, tổng tiền, trạng thái).
quotation_items: dòng chi tiết (Loại/Tên mẫu · Chỉ tiêu · Số lượng · Đơn giá · Thành tiền).
Tiền là Numeric — tổng LUÔN tính ở server (Decimal), không tin số từ client.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

VALID_QUOTATION_STATUS = ("draft", "sent", "accepted", "rejected", "expired")

QUOTATION_STATUS_LABELS = {
    "draft": "Nháp",
    "sent": "Đã gửi khách",
    "accepted": "Khách đồng ý",
    "rejected": "Khách từ chối",
    "expired": "Hết hiệu lực",
}

# Bước hợp lệ kế tiếp
QUOTATION_NEXT = {
    "draft": ("sent",),
    "sent": ("accepted", "rejected", "expired"),
    "accepted": (),
    "rejected": ("draft",),
    "expired": ("draft",),
}


class Quotation(Base):
    __tablename__ = "quotations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    intake_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sample_intakes.id", ondelete="SET NULL"), nullable=True
    )
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # m35 — mặt sau BM 7.1/01 khoản (1) đòi mã số thuế để lập HOÁ ĐƠN TÀI CHÍNH.
    customer_tax_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default=text("8"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0"))
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'draft'"))
    # m41 — phiên bản hiện hành. Mỗi lần sửa sau khi đã rời 'draft' sẽ chụp bản cũ
    # vào quotation_versions rồi tăng số này.
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    # m41 — xoá MỀM. Chứng từ đã gửi khách không được biến mất khỏi hệ thống.
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','sent','accepted','rejected','expired')", name="ck_quo_status"
        ),
    )


class QuotationItem(Base):
    __tablename__ = "quotation_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    quotation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    sample_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    test_parameter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_parameters.id", ondelete="SET NULL"), nullable=True
    )
    parameter_name: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[str | None] = mapped_column(String(500), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default=text("0"))
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, server_default=text("0"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class QuotationVersion(Base):
    """Bản chụp TOÀN VĂN của một phiên bản báo giá trước khi bị sửa (m41).

    Chụp cả dòng chi tiết vào một JSONB: thứ khách nhận là cả bảng giá, không phải
    riêng phần đầu. Bản chụp chỉ để đọc lại nguyên trạng khi có tranh chấp — không
    bao giờ join hay tổng hợp — nên chuẩn hoá thành bảng dòng là chi phí không đổi
    lấy được gì.
    """

    __tablename__ = "quotation_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    quotation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("quotation_id", "version", name="uq_qv_quotation_version"),
        CheckConstraint("version >= 1", name="ck_qv_version"),
    )
