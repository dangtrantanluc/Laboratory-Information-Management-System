"""m27: test_parameters — master data CHỈ TIÊU THỬ NGHIỆM (bảng giá phân tích).

Nguồn: "BẢNG GIÁ PHÂN TÍCH - 2024.xlsx" (7 nhóm nền mẫu: đất, nước, phân bón, thức ăn
chăn nuôi, nông sản/thực phẩm, kiểm dịch thực vật, SHPT).

Dùng để: Phòng nhận mẫu CHỌN chỉ tiêu khi phân chỉ tiêu → phòng lab (định tuyến qua
department_id), đồng thời VẪN cho nhập chỉ tiêu tự do (sample_dispatches.chi_tieu giữ text).
sample_dispatches thêm test_parameter_id (liên kết master, nullable) + unit_price (chốt giá
tại thời điểm chuyển mẫu — bảng giá có thể đổi về sau).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1718870400026"
down_revision: Union[str, None] = "1718870400025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "test_parameters",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        # Nhóm nền mẫu (matrix): soil|water|fertilizer|feed|food|quarantine|molecular|other
        sa.Column("matrix", sa.String(24), nullable=False),
        # Nền mẫu chi tiết (sheet SHPT có cột NỀN MẪU riêng, vd "Mẫu phân, gan, thận…")
        sa.Column("sample_matrix", sa.String(500), nullable=True),
        sa.Column("name", sa.String(500), nullable=False),          # CHỈ TIÊU THỬ NGHIỆM
        sa.Column("method", sa.String(500), nullable=True),         # PHƯƠNG PHÁP THỬ NGHIỆM
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=True),  # ĐƠN GIÁ (VNĐ)
        sa.Column("currency", sa.String(8), nullable=False, server_default=sa.text("'VND'")),
        sa.Column("turnaround_days", sa.SmallInteger(), nullable=True),  # Thời gian (ngày)
        sa.Column("in_charge", sa.String(255), nullable=True),      # người phụ trách (gợi ý)
        sa.Column("note", sa.Text(), nullable=True),                # GHI CHÚ
        # Phòng lab mặc định — dùng để định tuyến khi chuyển mẫu
        sa.Column(
            "department_id", sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("is_accredited", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=True),
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
        sa.CheckConstraint(
            "matrix IN ('soil','water','fertilizer','feed','food','quarantine','molecular','other')",
            name="ck_tp_matrix",
        ),
        sa.CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_tp_price_nonneg"),
        sa.CheckConstraint("char_length(btrim(name)) > 0", name="ck_tp_name_notblank"),
    )
    op.create_index("ix_tp_matrix", "test_parameters", ["matrix"])
    op.create_index("ix_tp_department", "test_parameters", ["department_id"])
    op.create_index("ix_tp_active", "test_parameters", ["is_active"])
    # Chống trùng: cùng nhóm nền mẫu + cùng tên + cùng phương pháp (không phân biệt hoa/thường)
    op.execute(
        "CREATE UNIQUE INDEX uq_tp_matrix_name_method ON test_parameters "
        "(matrix, lower(btrim(name)), lower(btrim(coalesce(method,''))))"
    )
    # Tìm kiếm nhanh theo tên (ILIKE '%…%')
    op.execute("CREATE INDEX ix_tp_name_trgm_like ON test_parameters (lower(name))")

    # --- sample_dispatches: liên kết master data (tùy chọn) + chốt đơn giá ---
    op.add_column(
        "sample_dispatches",
        sa.Column(
            "test_parameter_id", sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("test_parameters.id", ondelete="SET NULL"), nullable=True,
        ),
    )
    op.add_column(
        "sample_dispatches", sa.Column("unit_price", sa.Numeric(14, 2), nullable=True)
    )
    op.create_index("ix_dispatch_test_param", "sample_dispatches", ["test_parameter_id"])


def downgrade() -> None:
    op.drop_index("ix_dispatch_test_param", table_name="sample_dispatches")
    op.drop_column("sample_dispatches", "unit_price")
    op.drop_column("sample_dispatches", "test_parameter_id")
    op.execute("DROP INDEX IF EXISTS ix_tp_name_trgm_like")
    op.execute("DROP INDEX IF EXISTS uq_tp_matrix_name_method")
    op.drop_index("ix_tp_active", table_name="test_parameters")
    op.drop_index("ix_tp_department", table_name="test_parameters")
    op.drop_index("ix_tp_matrix", table_name="test_parameters")
    op.drop_table("test_parameters")
