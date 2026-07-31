"""m33: sample_intakes.customer_id — nối phiếu nhận mẫu với master data khách hàng.

Trước đây phiếu chỉ có customer_name dạng text tự do → cùng một khách gõ ba kiểu
("Cty TNHH ABC" / "Công ty ABC" / "ABC Co.,Ltd") thành ba khách khác nhau, không
thống kê được theo khách.

Theo đúng khuôn m27 đã dùng cho CHỈ TIÊU (sample_dispatches.test_parameter_id):
  - FK NULLABLE — khách vãng lai vẫn nhận mẫu được, phiếu cũ không phải backfill.
  - GIỮ NGUYÊN customer_name và 5 ô liên hệ trên phiếu: đó là BẢN CHỤP tại thời
    điểm nhận mẫu. Khách đổi địa chỉ về sau không được phép làm sai lệch phiếu đã
    in — yêu cầu hồ sơ VILAS.
  - ON DELETE SET NULL (không RESTRICT): xoá khách trong sổ thì phiếu mất liên kết
    nhưng vẫn đọc được, không khoá cứng thao tác quản trị.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "1718870400032"
down_revision: str = "1718870400031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sample_intakes",
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_intake_customer",
        "sample_intakes",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Postgres không tự tạo index cho FK (xem m31) — cần để lọc phiếu theo khách.
    op.create_index("ix_sample_intakes_customer_id", "sample_intakes", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_sample_intakes_customer_id", table_name="sample_intakes")
    op.drop_constraint("fk_intake_customer", "sample_intakes", type_="foreignkey")
    op.drop_column("sample_intakes", "customer_id")
