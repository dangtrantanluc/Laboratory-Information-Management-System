"""Models luồng Nhận & Chuyển mẫu (reception → lab) — GĐ2b.

- SampleIntake (Phiếu nhận mẫu, BM 7.1.01): reception nhận mẫu từ khách, đính kèm form đã điền.
- SampleDispatch (Phiếu chuyển mẫu, BM 7.1.02): mỗi dòng = 1 chỉ tiêu (text tự do) → 1 phòng lab.
  Gửi → notify lab; lab đổi status → notify lại phòng nhận mẫu.
File gắn qua attachments owner_type 'sample_intake' | 'sample_dispatch'.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, ForeignKey, Integer, Numeric, SmallInteger, String, Text,
    UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

# m28: luồng thật — tiếp nhận → báo giá → khách đồng ý → thanh toán → chuyển lab → trả KQ
VALID_INTAKE_STATUS = (
    "received", "quoted", "quote_accepted", "paid", "dispatched", "completed", "cancelled",
)
VALID_PAYMENT_STATUS = ("unpaid", "partial", "paid", "waived")

# Bước tiếp theo hợp lệ (state machine). Hủy được từ mọi bước chưa hoàn tất.
INTAKE_NEXT = {
    "received": ("quoted", "dispatched", "cancelled"),
    "quoted": ("quote_accepted", "received", "cancelled"),
    "quote_accepted": ("paid", "dispatched", "cancelled"),
    "paid": ("dispatched", "cancelled"),
    "dispatched": ("completed", "cancelled"),
    "completed": (),
    "cancelled": (),
}

INTAKE_STATUS_LABELS = {
    "received": "Đã tiếp nhận",
    "quoted": "Đã báo giá",
    "quote_accepted": "Khách đồng ý giá",
    "paid": "Đã thanh toán",
    "dispatched": "Đã chuyển lab",
    "completed": "Đã trả kết quả",
    "cancelled": "Đã hủy",
}
VALID_DISPATCH_STATUS = ("sent", "received", "in_progress", "done", "returned")


class SampleIntake(Base):
    __tablename__ = "sample_intakes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    # m33 — liên kết master data (nullable: khách vãng lai không cần vào sổ).
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True
    )
    # BẢN CHỤP tại thời điểm nhận mẫu — cố ý KHÔNG đọc ngược từ customers, để phiếu
    # đã in không đổi theo khi khách cập nhật thông tin về sau (hồ sơ VILAS).
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # mô tả mẫu
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'received'")
    )
    # m28: theo dõi thanh toán (khách chuyển khoản trước khi chuyển mẫu)
    payment_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'unpaid'")
    )
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Ô "Lưu ý" trên phiếu chuyển mẫu BM 7.1.02
    dispatch_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # BM 7.1.01 — thông tin khách hàng
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)  # địa chỉ
    tax_code: Mapped[str | None] = mapped_column(String(50), nullable=True)  # mã số thuế
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)  # người liên hệ
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)  # điện thoại
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)  # mail
    due_date: Mapped[str | None] = mapped_column(String(30), nullable=True)  # ngày hẹn trả KQ (text)
    result_language: Mapped[str | None] = mapped_column(String(10), nullable=True)  # vi | en
    return_method: Mapped[str | None] = mapped_column(String(20), nullable=True)  # direct|mail|email
    fee_note: Mapped[str | None] = mapped_column(String(500), nullable=True)  # lệ phí/ứng trước/còn lại
    other_request: Mapped[str | None] = mapped_column(Text, nullable=True)  # yêu cầu khác
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    received_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_intake_code"),
        CheckConstraint("status IN ('open','dispatched','closed')", name="ck_intake_status"),
    )


class SampleDispatch(Base):
    __tablename__ = "sample_dispatches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    intake_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sample_intakes.id", ondelete="CASCADE"), nullable=False
    )
    chi_tieu: Mapped[str] = mapped_column(Text, nullable=False)  # chỉ tiêu — text tự do
    target_department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'sent'"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # BM 7.1.02 — cột trả kết quả (lab điền khi thực hiện)
    don_vi: Mapped[str | None] = mapped_column(String(100), nullable=True)  # đơn vị
    phuong_phap: Mapped[str | None] = mapped_column(Text, nullable=True)  # phương pháp thử
    ket_qua: Mapped[str | None] = mapped_column(Text, nullable=True)  # kết quả
    can_bo: Mapped[str | None] = mapped_column(String(255), nullable=True)  # cán bộ phân tích
    # m28 — đủ cột BM 7.1.02
    sample_name: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Loại/Tên mẫu
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    # m27: liên kết master data chỉ tiêu (tùy chọn — vẫn cho nhập chi_tieu tự do)
    test_parameter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_parameters.id", ondelete="SET NULL"), nullable=True
    )
    # Đơn giá chốt tại thời điểm chuyển mẫu (bảng giá có thể đổi sau)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    dispatched_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    dispatched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    received_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('sent','received','in_progress','done','returned')",
            name="ck_dispatch_status",
        ),
    )


VALID_INFO_REQUEST_STATUS = ("pending", "approved", "rejected")


class CustomerInfoRequest(Base):
    """Yêu cầu xem thông tin khách hàng của 1 phiếu nhận mẫu (m26).

    Khối lab (staff/lab_manager) bị ẩn PII khách hàng; muốn xem phải gửi yêu cầu,
    Phòng nhận mẫu duyệt. Khi approved → quyền xem VĨNH VIỄN cho (intake, department).
    """

    __tablename__ = "customer_info_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    intake_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sample_intakes.id", ondelete="CASCADE"), nullable=False
    )
    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    decide_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected')", name="ck_cir_status"
        ),
    )


VALID_TEST_MATRIX = (
    "soil", "water", "fertilizer", "feed", "food", "quarantine", "molecular", "other",
)

MATRIX_LABELS = {
    "soil": "Đất",
    "water": "Nước",
    "fertilizer": "Phân bón, Chế phẩm sinh học",
    "feed": "Thức ăn chăn nuôi",
    "food": "Nông sản, Thực phẩm",
    "quarantine": "Kiểm dịch thực vật",
    "molecular": "Sinh học phân tử (SHPT)",
    "other": "Khác",
}


class TestParameter(Base):
    """Master data CHỈ TIÊU THỬ NGHIỆM + phương pháp + đơn giá (m27).

    Nguồn: Bảng giá phân tích 2024. Phòng nhận mẫu chọn chỉ tiêu khi chuyển mẫu
    (department_id = phòng lab mặc định để định tuyến); vẫn cho nhập chỉ tiêu tự do.
    """

    __tablename__ = "test_parameters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    matrix: Mapped[str] = mapped_column(String(24), nullable=False)
    sample_matrix: Mapped[str | None] = mapped_column(String(500), nullable=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[str | None] = mapped_column(String(500), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default=text("'VND'"))
    turnaround_days: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    in_charge: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    is_accredited: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
            "matrix IN ('soil','water','fertilizer','feed','food','quarantine','molecular','other')",
            name="ck_tp_matrix",
        ),
        CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_tp_price_nonneg"),
    )
