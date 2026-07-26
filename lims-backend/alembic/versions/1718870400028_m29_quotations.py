"""m29: BÁO GIÁ (quotations) — theo mẫu "BẢNG BÁO GIÁ" của Viện.

Luồng: tiếp nhận phiếu → lập BÁO GIÁ gửi khách → khách đồng ý → chuyển khoản → chuyển lab.

quotations: đầu báo giá (khách hàng snapshot, hiệu lực, VAT, tổng tiền, trạng thái).
quotation_items: dòng chi tiết = STT · Loại/Tên mẫu · Chỉ tiêu · Số lượng · Đơn giá · Thành tiền.
Tiền dùng Numeric(14,2); tổng tính ở SERVER (không tin số từ client).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1718870400028"
down_revision: Union[str, None] = "1718870400027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quotations",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(32), nullable=False),  # BG-2026-0001
        # Có thể lập báo giá độc lập (khách hỏi giá trước khi gửi mẫu) → intake_id nullable
        sa.Column(
            "intake_id", sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sample_intakes.id", ondelete="SET NULL"), nullable=True,
        ),
        # Thông tin khách hàng — snapshot tại thời điểm báo giá
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("customer_address", sa.String(500), nullable=True),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("customer_phone", sa.String(50), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),  # mẫu: hiệu lực 1 tháng
        sa.Column(
            "vat_rate", sa.Numeric(5, 2), nullable=False, server_default=sa.text("8")
        ),  # % — mặc định 8, cho sửa
        sa.Column("subtotal", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("vat_amount", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("decided_at", sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_by", sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("updated_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("code", name="uq_quotation_code"),
        sa.CheckConstraint(
            "status IN ('draft','sent','accepted','rejected','expired')", name="ck_quo_status"
        ),
        sa.CheckConstraint("vat_rate >= 0 AND vat_rate <= 100", name="ck_quo_vat_rate"),
        sa.CheckConstraint("subtotal >= 0 AND vat_amount >= 0 AND total >= 0", name="ck_quo_amounts"),
    )
    op.create_index("ix_quo_intake", "quotations", ["intake_id"])
    op.create_index("ix_quo_status", "quotations", ["status"])

    op.create_table(
        "quotation_items",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "quotation_id", sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("sample_name", sa.String(500), nullable=True),  # Loại/Tên mẫu (gộp theo nhóm khi xuất)
        # Link danh mục chỉ tiêu (m27) — snapshot tên/phương pháp để báo giá không đổi khi bảng giá đổi
        sa.Column(
            "test_parameter_id", sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("test_parameters.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("parameter_name", sa.String(500), nullable=False),
        sa.Column("method", sa.String(500), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("quantity >= 1", name="ck_quoi_qty"),
        sa.CheckConstraint("unit_price >= 0 AND amount >= 0", name="ck_quoi_amount"),
    )
    op.create_index("ix_quoi_quotation", "quotation_items", ["quotation_id"])


def downgrade() -> None:
    op.drop_index("ix_quoi_quotation", table_name="quotation_items")
    op.drop_table("quotation_items")
    op.drop_index("ix_quo_status", table_name="quotations")
    op.drop_index("ix_quo_intake", table_name="quotations")
    op.drop_table("quotations")
