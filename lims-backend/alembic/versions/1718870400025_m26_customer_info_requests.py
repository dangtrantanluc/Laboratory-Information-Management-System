"""m26: customer_info_requests — phòng lab xin xem thông tin khách hàng của phiếu nhận mẫu.

Nghiệp vụ: PII khách hàng (tên, MST, địa chỉ, người liên hệ, mail, điện thoại) bị ẨN với
khối lab (staff/lab_manager). Muốn xem phải gửi yêu cầu → Phòng nhận mẫu duyệt.
Quyền cấp theo (intake_id, department_id) và VĨNH VIỄN cho phiếu đó.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1718870400025"
down_revision: Union[str, None] = "1718870400024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_info_requests",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "intake_id", sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sample_intakes.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "requester_user_id", sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False,
        ),
        # Quyền xem được cấp cho PHÒNG của người xin (cả phòng lab cùng làm trên mẫu đó).
        sa.Column(
            "department_id", sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column(
            "decided_by", sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("decided_at", sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("decide_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','approved','rejected')", name="ck_cir_status"
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND decided_by IS NULL AND decided_at IS NULL) "
            "OR (status IN ('approved','rejected') AND decided_at IS NOT NULL)",
            name="ck_cir_decision_consistency",
        ),
    )
    op.create_index("ix_cir_intake", "customer_info_requests", ["intake_id"])
    op.create_index("ix_cir_status", "customer_info_requests", ["status"])
    op.create_index(
        "ix_cir_grant", "customer_info_requests", ["intake_id", "department_id", "status"]
    )
    # Chặn xin trùng khi đang CHỜ duyệt (cùng phiếu + cùng phòng).
    op.execute(
        "CREATE UNIQUE INDEX uq_cir_pending ON customer_info_requests "
        "(intake_id, department_id) WHERE status = 'pending'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_cir_pending")
    op.drop_index("ix_cir_grant", table_name="customer_info_requests")
    op.drop_index("ix_cir_status", table_name="customer_info_requests")
    op.drop_index("ix_cir_intake", table_name="customer_info_requests")
    op.drop_table("customer_info_requests")
