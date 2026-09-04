"""m35: danh bạ liên hệ khách hàng (1 khách – n người liên hệ).

VÌ SAO:
Master data cũ chỉ có ĐÚNG MỘT bộ `contact_person/phone/email` cho mỗi khách.
Thực tế một công ty gửi mẫu qua nhiều người (QA gửi mẫu vi sinh, R&D gửi mẫu hoá
lý), và người mang mẫu đến thường khác người nhận kết quả. Một ô nghĩa là người
sau ghi đè người trước — mất luôn thông tin, không có lịch sử.

KHÔNG phân vai trò (chốt với nghiệp vụ): danh bạ phẳng, mỗi dòng là một người.
Enum vai trò là chỗ dễ sai nhất và mỗi vai trò mới lại phải migration.

BA ĐIỂM CỐ Ý:
  1. `is_active` thay cho xoá: người nghỉ việc phải TẮT chứ không xoá, vì phiếu
     cũ đã in tên họ — hồ sơ VILAS cần tra ngược được.
  2. `is_primary` + unique index từng phần: mỗi khách đúng MỘT liên hệ mặc định,
     để quầy nhận mẫu tự điền mà không phải bấm chọn (đa số khách chỉ có 1 người).
     Ràng buộc đặt ở DB chứ không chỉ ở service — hai request song song cùng đặt
     mặc định thì service kiểm xong vẫn ghi được cả hai.
  3. KHÔNG thêm `contact_id` vào sample_intakes. Phiếu vẫn chụp GIÁ TRỊ
     (contact_person/phone/email) như m33 đã làm với địa chỉ: mặt sau BM 7.1/01
     khoản (5) ghi "Viện sẽ không thay đổi tên khách hàng, tên mẫu sau khi đã phát
     hành phiếu kết quả, hoá đơn". Thêm khoá ngoại chỉ tạo thêm một đường rò PII
     phải che (xem m26) mà không thêm thông tin gì so với bản chụp.

Kèm hai việc dọn dẹp cùng phạm vi:
  - `quotations.customer_tax_code`: mặt sau BM 7.1/01 khoản (1) đòi mã số thuế để
    lập HOÁ ĐƠN TÀI CHÍNH, nhưng bảng báo giá không có cột này nên file Excel xuất
    ra thiếu MST.
  - Xoá `customers.contact` và `sample_intakes.contact`: ô "liên hệ" tự do từ thời
    chưa có `contact_person`. Cả hai đang RỖNG (0 bản ghi) và gây nhập nhằng —
    samplePdf phải viết `contact_person ?? contact` vì không biết ô nào là thật.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "1718870400034"
down_revision: str = "1718870400033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_contacts",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("job_title", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        # CASCADE: danh bạ là con của khách, xoá khách thì danh bạ hết nghĩa.
        # Phiếu đã in không bị ảnh hưởng vì phiếu chụp giá trị, không giữ khoá ngoại.
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    # Postgres không tự tạo index cho FK (xem m31) — cần để liệt kê danh bạ theo khách.
    op.create_index("ix_customer_contacts_customer_id", "customer_contacts", ["customer_id"])
    # Mỗi khách tối đa 1 liên hệ mặc định. Index TỪNG PHẦN vì các dòng is_primary=false
    # không bị ràng buộc — unique thường sẽ chặn khách có 2 liên hệ không mặc định.
    op.create_index(
        "uq_customer_contacts_primary", "customer_contacts", ["customer_id"],
        unique=True, postgresql_where=sa.text("is_primary"),
    )

    op.add_column("quotations", sa.Column("customer_tax_code", sa.String(50), nullable=True))

    op.drop_column("customers", "contact")
    op.drop_column("sample_intakes", "contact")


def downgrade() -> None:
    op.add_column("sample_intakes", sa.Column("contact", sa.String(255), nullable=True))
    op.add_column("customers", sa.Column("contact", sa.String(255), nullable=True))
    op.drop_column("quotations", "customer_tax_code")
    op.drop_index("uq_customer_contacts_primary", table_name="customer_contacts")
    op.drop_index("ix_customer_contacts_customer_id", table_name="customer_contacts")
    op.drop_table("customer_contacts")
