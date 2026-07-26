"""M16 — Nhận & Chuyển mẫu (GĐ2b): sample_intakes + sample_dispatches.

Reception nhận mẫu (Phiếu nhận) → phân chỉ tiêu (text) chuyển tới phòng lab (Phiếu chuyển)
→ notify lab; lab đổi status → notify lại reception. File qua attachments
(owner_type 'sample_intake' | 'sample_dispatch').
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400015"
down_revision: Union[str, None] = "1718870400014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_TYPES = (
    "'test_request','sample','sample_result','chemical','chem_lot','document',"
    "'document_version','equipment','calibration','hr_profile','publication',"
    "'form_template','form_submission','sample_intake','sample_dispatch'"
)


def upgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy import text

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sample_intakes (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code          VARCHAR(32)  NOT NULL,
            customer_name VARCHAR(255) NOT NULL,
            contact       VARCHAR(255),
            description   TEXT,
            note          TEXT,
            status        VARCHAR(16)  NOT NULL DEFAULT 'open',
            department_id UUID REFERENCES departments(id) ON DELETE RESTRICT,
            received_by   UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by    UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            updated_by    UUID,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_intake_code UNIQUE (code),
            CONSTRAINT ck_intake_status CHECK (status IN ('open','dispatched','closed'))
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sample_dispatches (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            intake_id            UUID NOT NULL REFERENCES sample_intakes(id) ON DELETE CASCADE,
            chi_tieu             TEXT NOT NULL,
            target_department_id UUID NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
            status               VARCHAR(16) NOT NULL DEFAULT 'sent',
            note                 TEXT,
            dispatched_by        UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            dispatched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            received_at          TIMESTAMPTZ,
            completed_at         TIMESTAMPTZ,
            updated_by           UUID,
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_dispatch_status
                CHECK (status IN ('sent','received','in_progress','done','returned'))
        );
        CREATE INDEX IF NOT EXISTS idx_dispatch_target ON sample_dispatches(target_department_id, status);
        CREATE INDEX IF NOT EXISTS idx_dispatch_intake ON sample_dispatches(intake_id);
        """
    )

    # Nới owner_type attachments
    op.execute("ALTER TABLE attachments DROP CONSTRAINT IF EXISTS attachments_owner_type_check;")
    op.execute("ALTER TABLE attachments DROP CONSTRAINT IF EXISTS ck_att_owner_type;")
    op.execute(
        f"ALTER TABLE attachments ADD CONSTRAINT ck_att_owner_type "
        f"CHECK (owner_type IN ({_OWNER_TYPES}));"
    )

    # RBAC
    conn.execute(
        text(
            """
            INSERT INTO permissions (resource, action, description) VALUES
                ('intake','read','Xem phiếu nhận & chuyển mẫu'),
                ('intake','manage','Nhận mẫu & phân chỉ tiêu chuyển phòng lab'),
                ('dispatch','update','Đổi trạng thái phiếu chuyển mẫu (phòng lab)')
            ON CONFLICT (resource, action) DO NOTHING;
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO roles_permissions (role, resource, action, scope) VALUES
                ('admin','intake','read','all'),
                ('admin','intake','manage','all'),
                ('admin','dispatch','update','all'),
                ('leader','intake','read','all'),
                ('qms','intake','read','all'),
                ('reception','intake','read','all'),
                ('reception','intake','manage','all'),
                ('reception','dispatch','update','all'),
                ('staff','intake','read','all'),
                ('staff','dispatch','update','department'),
                ('lab_manager','intake','read','all'),
                ('lab_manager','dispatch','update','department')
            ON CONFLICT (role, resource, action) DO NOTHING;
            """
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM roles_permissions WHERE resource IN ('intake','dispatch');")
    op.execute("DELETE FROM permissions WHERE resource IN ('intake','dispatch');")
    op.execute("DROP TABLE IF EXISTS sample_dispatches CASCADE;")
    op.execute("DROP TABLE IF EXISTS sample_intakes CASCADE;")
