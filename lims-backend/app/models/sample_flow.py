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
    "received", "quoted", "quote_accepted", "paid", "dispatched", "completed",
    "cancelled", "rejected",
)
VALID_PAYMENT_STATUS = ("unpaid", "partial", "paid", "waived")

# Bước tiếp theo hợp lệ (state machine). Hủy được từ mọi bước chưa hoàn tất.
INTAKE_NEXT = {
    # m42 — 'rejected' (từ chối tiếp nhận vì mẫu không đạt) chỉ đi được từ những bước
    # mẫu CÒN Ở QUẦY. Đã chuyển lab rồi thì không "từ chối tiếp nhận" được nữa —
    # lúc đó là huỷ, hoặc lab trả lại lượt chuyển.
    "received": ("quoted", "dispatched", "rejected", "cancelled"),
    "quoted": ("quote_accepted", "received", "rejected", "cancelled"),
    "quote_accepted": ("paid", "dispatched", "cancelled"),
    "paid": ("dispatched", "cancelled"),
    "dispatched": ("completed", "cancelled"),
    "completed": (),
    "cancelled": (),
    "rejected": (),
}

INTAKE_STATUS_LABELS = {
    "received": "Đã tiếp nhận",
    "quoted": "Đã báo giá",
    "quote_accepted": "Khách đồng ý giá",
    "paid": "Đã thanh toán",
    "dispatched": "Đã chuyển lab",
    "completed": "Đã trả kết quả",
    "cancelled": "Đã hủy",
    "rejected": "Từ chối tiếp nhận",
}
VALID_DISPATCH_STATUS = ("sent", "received", "in_progress", "done", "returned")

# m37 — bước hợp lệ kế tiếp của MỘT LƯỢT CHUYỂN. Trước đây update_dispatch gán
# thẳng `d.status = new_status` nên `done → sent → sửa kết quả → done` lặp vô hạn
# đều hợp lệ, tức là kết quả đã trả cho khách vẫn viết đè được không để lại vết.
# 'returned' (trả lại phòng nhận mẫu) đi được từ mọi bước CHƯA hoàn tất — lab phát
# hiện mẫu không làm được ở bất kỳ giai đoạn nào.
DISPATCH_NEXT = {
    "sent": ("received", "returned"),
    "received": ("in_progress", "done", "returned"),
    "in_progress": ("done", "returned"),
    # Hoàn tất là điểm dừng: sửa kết quả sau khi đã trả phải đi qua đường tạo
    # phiên bản sửa của module kết quả, không phải bằng cách lùi trạng thái.
    "done": (),
    "returned": (),
}

DISPATCH_STATUS_LABELS = {
    "sent": "Chờ tiếp nhận",
    "received": "Đã tiếp nhận",
    "in_progress": "Đang thực hiện",
    "done": "Đã hoàn thành",
    "returned": "Đã trả lại",
}


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
    # Bản chụp ĐÚNG thứ nhân viên đã gõ và đã in ra phiếu — không chuẩn hoá, không ghi đè.
    due_date: Mapped[str | None] = mapped_column(String(30), nullable=True)  # ngày hẹn trả KQ (text)
    # m39 — cùng ngày đó ở dạng so sánh được, để tính "quá hạn trả kết quả". NULL khi
    # ô gốc không phân giải nổi ("cuối tháng 3") — chấp nhận, hơn là đoán bừa một ngày.
    due_date_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    result_language: Mapped[str | None] = mapped_column(String(10), nullable=True)  # vi | en
    return_method: Mapped[str | None] = mapped_column(String(20), nullable=True)  # direct|mail|email
    fee_note: Mapped[str | None] = mapped_column(String(500), nullable=True)  # lệ phí/ứng trước/còn lại
    other_request: Mapped[str | None] = mapped_column(Text, nullable=True)  # yêu cầu khác
    # m42 — việc ĐẦU TIÊN nhân viên quầy làm với mẫu vật lý: đếm và xem tình trạng.
    # Trước đây không có chỗ ghi, dù cột cùng tên đã tồn tại ở bảng `samples` của M1
    # (mà quầy không chạm tới).
    sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    condition_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    condition_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Quyết định TỪ CHỐI tiếp nhận — ai quyết, lúc nào, vì sao. Khác "huỷ phiếu"
    # (thao tác hành chính) ở chỗ đây là quyết định kỹ thuật phải giải trình được.
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    # m40 — phiếu yêu cầu M1 tương ứng, tạo LƯỜI khi lab lần đầu gửi kết quả đi duyệt.
    test_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_requests.id", ondelete="SET NULL"), nullable=True
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
        # Khớp DB thật sau m28 (migration đã ALTER). Ba giá trị cũ
        # ('open','dispatched','closed') nằm lại đây tới m41 và mô tả sai hoàn toàn
        # vòng đời phiếu — mã chết nhưng gây hiểu nhầm cho người đọc model.
        CheckConstraint(
            "status IN ('received','quoted','quote_accepted','paid',"
            "'dispatched','completed','cancelled','rejected')",
            name="ck_intake_status",
        ),
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
    # can_bo (m16): ô TEXT TỰ DO trên BM 7.1/02. Giữ lại để phiếu cũ đọc được, nhưng
    # KHÔNG còn là nguồn truy xuất — xem performed_by bên dưới.
    can_bo: Mapped[str | None] = mapped_column(String(255), nullable=True)  # cán bộ phân tích
    # m37 — NGƯỜI THỰC HIỆN phép thử, gán từ tài khoản đăng nhập chứ không nhận từ
    # client. Đây mới là thứ ISO/IEC 17025 §7.8.2 đòi: kết quả truy về được một
    # người cụ thể, không phải một chuỗi ký tự ai gõ cũng được.
    performed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    performed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # m28 — đủ cột BM 7.1.02
    sample_name: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Loại/Tên mẫu
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    # m27: liên kết master data chỉ tiêu (tùy chọn — vẫn cho nhập chi_tieu tự do)
    test_parameter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_parameters.id", ondelete="SET NULL"), nullable=True
    )
    # m38 — dòng đặt hàng mà lượt giao việc này thực hiện. Nullable vì ON DELETE
    # SET NULL: xoá dòng đặt hàng không được làm mất vết công việc phòng lab đã làm.
    intake_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("intake_items.id", ondelete="SET NULL"), nullable=True
    )
    # m40 — phần việc M1 của chỉ tiêu này. Kết quả CÓ DUYỆT nằm ở sample_results gắn
    # vào đây; cột `ket_qua` bên dưới chỉ còn là bản hiển thị đồng bộ từ nó.
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sample_assignments.id", ondelete="SET NULL"),
        nullable=True,
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


class IntakeItem(Base):
    """CHỈ TIÊU KHÁCH ĐẶT trên một phiếu nhận mẫu (m38) — nguồn để lập báo giá.

    KHÁC `SampleDispatch`: dòng này nói khách đặt gì; dispatch nói việc đó giao cho
    phòng lab nào. Trước m38 hai khái niệm nằm chung một bảng, nên muốn báo giá thì
    phải giao việc cho lab trước — và giao việc lại đẩy phiếu sang 'dispatched',
    khiến ba bước báo giá → đồng ý → thanh toán không bao giờ đi qua được.

    Quan hệ 1–n với dispatch: một chỉ tiêu đặt có thể giao cho nhiều phòng, hoặc
    chưa giao cho phòng nào (đã báo giá, khách chưa chốt).

    Giá và phương pháp là BẢN CHỤP từ danh mục tại thời điểm đặt — bảng giá đổi về
    sau không được làm lệch báo giá đã gửi khách.
    """

    __tablename__ = "intake_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    intake_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sample_intakes.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    test_parameter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_parameters.id", ondelete="SET NULL"), nullable=True
    )
    parameter_name: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[str | None] = mapped_column(String(500), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sample_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
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
        CheckConstraint("quantity >= 1", name="ck_ii_quantity"),
        CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_ii_price_nonneg"),
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
    # m45 — quyền có THỜI HẠN. NULL = vĩnh viễn, giữ nguyên hành vi cho bản ghi cũ;
    # bản duyệt mới mặc định 90 ngày. Trước đây duyệt một lần là cả phòng xem mãi mãi,
    # kể cả sau khi người xin đã chuyển việc.
    expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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


VALID_CONTACT_ROLES = ("courier", "technical", "result_recipient", "billing")

CONTACT_ROLE_LABELS = {
    "courier": "Người gửi mẫu",
    "technical": "Liên hệ chuyên môn",
    "result_recipient": "Người nhận kết quả",
    "billing": "Liên hệ thanh toán",
}


class IntakeContact(Base):
    """Người liên hệ theo VAI TRÒ trên một phiếu nhận mẫu (m43).

    Trước m43 phiếu chỉ giữ được MỘT người (`contact_person` + `phone` + `email`), nên
    không diễn tả được ba tình huống rất phổ biến: người mang mẫu tới ≠ người nhận
    kết quả; liên hệ chuyên môn ≠ liên hệ thanh toán; và hai bộ phận của cùng một
    khách gửi hai loại mẫu khác nhau.

    BẢN CHỤP, KHÔNG PHẢI KHOÁ NGOẠI: cố ý không trỏ tới customer_contacts, cùng lý do
    m35 đã nêu — người liên hệ đổi hoặc nghỉ việc về sau không được làm sai lệch phiếu
    đã in (mặt sau BM 7.1/01, khoản 5).
    """

    __tablename__ = "intake_contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    intake_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sample_intakes.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('courier','technical','result_recipient','billing')",
            name="ck_intake_contact_role",
        ),
        # Mỗi phiếu một người cho mỗi vai. Nếu nghiệp vụ xác nhận một vai có nhiều
        # người (Q4), gỡ ràng buộc này — nhưng "kết quả giao cho ai" mà mơ hồ thì
        # tính năng mất ý nghĩa, nên đừng gỡ trước khi có xác nhận.
        UniqueConstraint("intake_id", "role", name="uq_intake_contact_role"),
    )
