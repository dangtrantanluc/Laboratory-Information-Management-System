"""M17 — Bổ sung trường theo biểu mẫu BM 7.1.01 / BM 7.1.02.

sample_intakes: thông tin khách hàng (địa chỉ, MST, người liên hệ, ĐT, mail, ngày hẹn,
ngôn ngữ KQ, cách trả, lệ phí, yêu cầu khác).
sample_dispatches: cột trả kết quả (đơn vị, phương pháp, kết quả, cán bộ phân tích).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400016"
down_revision: Union[str, None] = "1718870400015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE sample_intakes
            ADD COLUMN IF NOT EXISTS address         VARCHAR(500),
            ADD COLUMN IF NOT EXISTS tax_code        VARCHAR(50),
            ADD COLUMN IF NOT EXISTS contact_person  VARCHAR(255),
            ADD COLUMN IF NOT EXISTS phone           VARCHAR(50),
            ADD COLUMN IF NOT EXISTS email           VARCHAR(255),
            ADD COLUMN IF NOT EXISTS due_date        VARCHAR(30),
            ADD COLUMN IF NOT EXISTS result_language VARCHAR(10),
            ADD COLUMN IF NOT EXISTS return_method   VARCHAR(20),
            ADD COLUMN IF NOT EXISTS fee_note        VARCHAR(500),
            ADD COLUMN IF NOT EXISTS other_request   TEXT;
        """
    )
    op.execute(
        """
        ALTER TABLE sample_dispatches
            ADD COLUMN IF NOT EXISTS don_vi      VARCHAR(100),
            ADD COLUMN IF NOT EXISTS phuong_phap TEXT,
            ADD COLUMN IF NOT EXISTS ket_qua     TEXT,
            ADD COLUMN IF NOT EXISTS can_bo      VARCHAR(255);
        """
    )


def downgrade() -> None:
    for col in ("address", "tax_code", "contact_person", "phone", "email", "due_date",
                "result_language", "return_method", "fee_note", "other_request"):
        op.execute(f"ALTER TABLE sample_intakes DROP COLUMN IF EXISTS {col};")
    for col in ("don_vi", "phuong_phap", "ket_qua", "can_bo"):
        op.execute(f"ALTER TABLE sample_dispatches DROP COLUMN IF EXISTS {col};")
