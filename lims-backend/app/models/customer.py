"""Model customers + customer_contacts — khách gửi mẫu dùng chung (M1 tham chiếu).

Soft-delete của customers = deleted_at. Danh bạ liên hệ (m35) KHÔNG soft-delete:
người nghỉ việc thì tắt `is_active`, còn dòng nhập nhầm thì xoá hẳn — phiếu đã in
không tham chiếu tới id nên xoá không làm hỏng hồ sơ.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, Text, ForeignKey, CheckConstraint, Index, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

VALID_CUSTOMER_TYPES = ("internal", "external", "individual", "organization")


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'external'")
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # m32 — thông tin để tự điền phiếu nhận mẫu BM 7.1.01; độ dài khớp
    # sample_intakes.<cùng tên> vì hai bên chép qua lại.
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tax_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
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
        CheckConstraint(
            "type IN ('internal', 'external', 'individual', 'organization')",
            name="ck_customer_type",
        ),
    )


class CustomerContact(Base):
    """Một người liên hệ của khách hàng (m35) — danh bạ phẳng, KHÔNG phân vai trò.

    Phiếu nhận mẫu chụp GIÁ TRỊ của dòng được chọn vào sample_intakes chứ không giữ
    khoá ngoại tới đây: người liên hệ đổi/nghỉ việc về sau không được phép làm sai
    lệch phiếu đã in (mặt sau BM 7.1/01, khoản 5).
    """

    __tablename__ = "customer_contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)  # chức vụ
    # m43 — vai trò MẶC ĐỊNH của người này với khách: người gửi mẫu / liên hệ chuyên
    # môn / người nhận kết quả / liên hệ thanh toán. Rỗng = chưa phân vai. Đây chỉ là
    # gợi ý tự điền cho quầy; vai trò THỰC TẾ của từng phiếu nằm ở intake_contacts.
    roles: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Liên hệ mặc định — quầy nhận mẫu tự điền dòng này, khỏi phải bấm chọn.
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Nghỉ việc thì TẮT, không xoá: phiếu cũ đã in tên họ, hồ sơ VILAS cần tra ngược.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
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
        CheckConstraint(
            "roles <@ ARRAY['courier','technical','result_recipient','billing']::text[]",
            name="ck_contact_roles",
        ),
        # Mỗi khách tối đa 1 liên hệ mặc định. Ràng buộc nằm ở DB chứ không chỉ ở
        # service: hai request song song cùng đặt mặc định thì service kiểm xong
        # vẫn ghi được cả hai.
        Index(
            "uq_customer_contacts_primary", "customer_id",
            unique=True, postgresql_where=text("is_primary"),
        ),
    )
