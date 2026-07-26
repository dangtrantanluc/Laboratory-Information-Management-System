"""M15 — Bỏ CHECK owner_type cũ (auto-named) còn sót trên attachments.

m12 chỉ drop 'ck_att_owner_type' (tên model) nên constraint gốc do m7 tạo inline
('attachments_owner_type_check') vẫn tồn tại → chặn owner_type 'form_template'/
'form_submission'. Migration này gỡ nó và bảo đảm constraint đúng (đủ owner types).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400014"
down_revision: Union[str, None] = "1718870400013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_TYPES = (
    "'test_request','sample','sample_result','chemical','chem_lot','document',"
    "'document_version','equipment','calibration','hr_profile','publication',"
    "'form_template','form_submission'"
)


def upgrade() -> None:
    op.execute("ALTER TABLE attachments DROP CONSTRAINT IF EXISTS attachments_owner_type_check;")
    op.execute("ALTER TABLE attachments DROP CONSTRAINT IF EXISTS ck_att_owner_type;")
    op.execute(
        f"ALTER TABLE attachments ADD CONSTRAINT ck_att_owner_type "
        f"CHECK (owner_type IN ({_OWNER_TYPES}));"
    )


def downgrade() -> None:
    pass
