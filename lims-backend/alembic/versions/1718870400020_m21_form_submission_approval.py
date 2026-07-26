"""M21 — Duyệt minh chứng VILAS: thêm status/reviewed_by/reviewed_at/reject_reason
vào form_submissions + permission form:approve (admin, qms).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400020"
down_revision: Union[str, None] = "1718870400019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy import text

    op.execute(
        """
        ALTER TABLE form_submissions
            ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'pending',
            ADD COLUMN IF NOT EXISTS reviewed_by UUID REFERENCES users(id) ON DELETE RESTRICT,
            ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS reject_reason VARCHAR(1000);

        ALTER TABLE form_submissions
            ADD CONSTRAINT ck_fs_status CHECK (status IN ('pending','approved','rejected'));
        ALTER TABLE form_submissions
            ADD CONSTRAINT ck_fs_review_pair CHECK (
                (reviewed_by IS NULL AND reviewed_at IS NULL)
                OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)
            );

        CREATE INDEX IF NOT EXISTS idx_form_sub_status ON form_submissions(status);
        """
    )

    conn.execute(
        text(
            """
            INSERT INTO permissions (resource, action, description) VALUES
                ('form','approve','Duyệt/từ chối minh chứng biểu mẫu VILAS')
            ON CONFLICT (resource, action) DO NOTHING;
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO roles_permissions (role, resource, action, scope) VALUES
                ('admin','form','approve','all'),
                ('qms','form','approve','all')
            ON CONFLICT (role, resource, action) DO NOTHING;
            """
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM roles_permissions WHERE resource='form' AND action='approve';")
    op.execute("DELETE FROM permissions WHERE resource='form' AND action='approve';")
    op.execute(
        """
        ALTER TABLE form_submissions
            DROP CONSTRAINT IF EXISTS ck_fs_review_pair,
            DROP CONSTRAINT IF EXISTS ck_fs_status,
            DROP COLUMN IF EXISTS reject_reason,
            DROP COLUMN IF EXISTS reviewed_at,
            DROP COLUMN IF EXISTS reviewed_by,
            DROP COLUMN IF EXISTS status;
        """
    )
