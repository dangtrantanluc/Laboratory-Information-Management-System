"""M12 — Kho biểu mẫu VILAS (GĐ3): form_templates + form_submissions.

QLCL quản trị template; phòng lab nộp minh chứng → thông báo QLCL.
File gắn qua attachments (owner_type 'form_template' | 'form_submission').
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400011"
down_revision: Union[str, None] = "1718870400010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy import text

    # ===== 1. Bảng form_templates =====
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS form_templates (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code        VARCHAR(64)  NOT NULL,
            title       VARCHAR(500) NOT NULL,
            iso_clause  VARCHAR(16)  NOT NULL,
            category    VARCHAR(4)   NOT NULL DEFAULT 'BM',
            year        INTEGER,
            is_active   BOOLEAN      NOT NULL DEFAULT true,
            note        VARCHAR(1000),
            created_by  UUID REFERENCES users(id) ON DELETE RESTRICT,
            updated_by  UUID REFERENCES users(id) ON DELETE RESTRICT,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT uq_form_tpl_code UNIQUE (code),
            CONSTRAINT ck_form_tpl_category CHECK (category IN ('BM','QT','HD'))
        );
        CREATE INDEX IF NOT EXISTS idx_form_tpl_clause ON form_templates(iso_clause);
        """
    )

    # ===== 2. Bảng form_submissions (minh chứng) =====
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS form_submissions (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            template_id   UUID NOT NULL REFERENCES form_templates(id) ON DELETE RESTRICT,
            department_id UUID NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
            year          INTEGER,
            note          VARCHAR(1000),
            submitted_by  UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            submitted_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_form_sub_dept ON form_submissions(department_id);
        CREATE INDEX IF NOT EXISTS idx_form_sub_tpl  ON form_submissions(template_id);
        """
    )

    # ===== 3. Nới owner_type của attachments =====
    # m7 tạo CHECK inline không tên → auto 'attachments_owner_type_check'. Drop cả 2 tên.
    op.execute("ALTER TABLE attachments DROP CONSTRAINT IF EXISTS attachments_owner_type_check;")
    op.execute("ALTER TABLE attachments DROP CONSTRAINT IF EXISTS ck_att_owner_type;")
    op.execute(
        """
        ALTER TABLE attachments ADD CONSTRAINT ck_att_owner_type CHECK (
            owner_type IN ('test_request','sample','sample_result','chemical','chem_lot',
                'document','document_version','equipment','calibration','hr_profile',
                'publication','form_template','form_submission')
        );
        """
    )

    # ===== 4. RBAC: permissions + roles_permissions cho resource 'form' =====
    conn.execute(
        text(
            """
            INSERT INTO permissions (resource, action, description) VALUES
                ('form','read','Xem/tải kho biểu mẫu VILAS'),
                ('form','manage','Quản trị biểu mẫu (QLCL)'),
                ('form','submit','Nộp minh chứng biểu mẫu')
            ON CONFLICT (resource, action) DO NOTHING;
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO roles_permissions (role, resource, action, scope) VALUES
                ('admin','form','read','all'),
                ('admin','form','manage','all'),
                ('admin','form','submit','all'),
                ('leader','form','read','all'),
                ('qms','form','read','all'),
                ('qms','form','manage','all'),
                ('qms','form','submit','all'),
                ('staff','form','read','all'),
                ('staff','form','submit','department'),
                ('lab_manager','form','read','all'),
                ('lab_manager','form','submit','department'),
                ('reception','form','read','all')
            ON CONFLICT (role, resource, action) DO NOTHING;
            """
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM roles_permissions WHERE resource='form';")
    op.execute("DELETE FROM permissions WHERE resource='form';")
    op.execute("DROP TABLE IF EXISTS form_submissions CASCADE;")
    op.execute("DROP TABLE IF EXISTS form_templates CASCADE;")
    op.execute("ALTER TABLE attachments DROP CONSTRAINT IF EXISTS ck_att_owner_type;")
    op.execute(
        """
        ALTER TABLE attachments ADD CONSTRAINT ck_att_owner_type CHECK (
            owner_type IN ('test_request','sample','sample_result','chemical','chem_lot',
                'document','document_version','equipment','calibration','hr_profile',
                'publication')
        );
        """
    )
