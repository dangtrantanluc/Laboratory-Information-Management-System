"""m28: mở rộng trạng thái phiếu nhận mẫu + theo dõi thanh toán + đủ cột BM 7.1.02.

Luồng thật: khách gửi phiếu → tiếp nhận → BÁO GIÁ → khách đồng ý → CHUYỂN KHOẢN
→ nhập BM 7.1.02 → chuyển lab → trả kết quả.

1) sample_intakes.status: open/dispatched/closed → received/quoted/quote_accepted/paid/
   dispatched/completed/cancelled (map dữ liệu cũ: open→received, closed→completed).
2) Thêm khối thanh toán: payment_status, paid_amount, payment_date, payment_ref, payment_note.
3) BM 7.1.02: sample_dispatches thêm sample_name (Loại/Tên mẫu) + quantity (Số lượng);
   sample_intakes thêm dispatch_note (ô "Lưu ý" trên phiếu chuyển).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1718870400027"
down_revision: Union[str, None] = "1718870400026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_STATUSES = (
    "received", "quoted", "quote_accepted", "paid", "dispatched", "completed", "cancelled",
)
OLD_STATUSES = ("open", "dispatched", "closed")


def upgrade() -> None:
    # --- 1) Trạng thái: bỏ CHECK cũ → map dữ liệu → CHECK mới ---
    op.drop_constraint("ck_intake_status", "sample_intakes", type_="check")
    op.execute("UPDATE sample_intakes SET status = 'received'  WHERE status = 'open'")
    op.execute("UPDATE sample_intakes SET status = 'completed' WHERE status = 'closed'")
    op.alter_column(
        "sample_intakes", "status", server_default=sa.text("'received'"), existing_type=sa.String(16)
    )
    op.create_check_constraint(
        "ck_intake_status", "sample_intakes",
        "status IN ('received','quoted','quote_accepted','paid','dispatched','completed','cancelled')",
    )

    # --- 2) Khối thanh toán ---
    op.add_column(
        "sample_intakes",
        sa.Column(
            "payment_status", sa.String(16), nullable=False, server_default=sa.text("'unpaid'")
        ),
    )
    op.add_column("sample_intakes", sa.Column("paid_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("sample_intakes", sa.Column("payment_date", sa.Date(), nullable=True))
    # Mã giao dịch / số UNC chuyển khoản
    op.add_column("sample_intakes", sa.Column("payment_ref", sa.String(120), nullable=True))
    op.add_column("sample_intakes", sa.Column("payment_note", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_intake_payment_status", "sample_intakes",
        "payment_status IN ('unpaid','partial','paid','waived')",
    )
    op.create_check_constraint(
        "ck_intake_paid_amount", "sample_intakes", "paid_amount IS NULL OR paid_amount >= 0"
    )
    op.create_index("ix_intake_status", "sample_intakes", ["status"])
    op.create_index("ix_intake_payment_status", "sample_intakes", ["payment_status"])

    # --- 3) Đủ cột BM 7.1.02 ---
    op.add_column("sample_dispatches", sa.Column("sample_name", sa.String(500), nullable=True))
    op.add_column(
        "sample_dispatches",
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.create_check_constraint("ck_dispatch_quantity", "sample_dispatches", "quantity >= 1")
    op.add_column("sample_intakes", sa.Column("dispatch_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sample_intakes", "dispatch_note")
    op.drop_constraint("ck_dispatch_quantity", "sample_dispatches", type_="check")
    op.drop_column("sample_dispatches", "quantity")
    op.drop_column("sample_dispatches", "sample_name")

    op.drop_index("ix_intake_payment_status", table_name="sample_intakes")
    op.drop_index("ix_intake_status", table_name="sample_intakes")
    op.drop_constraint("ck_intake_paid_amount", "sample_intakes", type_="check")
    op.drop_constraint("ck_intake_payment_status", "sample_intakes", type_="check")
    for col in ("payment_note", "payment_ref", "payment_date", "paid_amount", "payment_status"):
        op.drop_column("sample_intakes", col)

    # Trả trạng thái về bộ cũ (gộp các trạng thái mới về 3 giá trị gốc)
    op.drop_constraint("ck_intake_status", "sample_intakes", type_="check")
    op.execute(
        "UPDATE sample_intakes SET status = 'open' "
        "WHERE status IN ('received','quoted','quote_accepted','paid','cancelled')"
    )
    op.execute("UPDATE sample_intakes SET status = 'closed' WHERE status = 'completed'")
    op.alter_column(
        "sample_intakes", "status", server_default=sa.text("'open'"), existing_type=sa.String(16)
    )
    op.create_check_constraint(
        "ck_intake_status", "sample_intakes", "status IN ('open','dispatched','closed')"
    )
