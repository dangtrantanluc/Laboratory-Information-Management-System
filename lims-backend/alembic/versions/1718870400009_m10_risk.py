"""m10_risk — Rủi ro & Cơ hội + Cải tiến (Risk & Improvement, §8.5/§8.6/§8.4).

Tạo 4 bảng theo Contract M10 (24-contract-m10-risk.md §1):
  risks (level GENERATED = likelihood*impact) → risk_treatments → improvements
  (linked_nc_id → nonconformities M8) → risk_notification_dedup (CRON-8 idempotent)
  → indexes → seed permissions (risk/improvement: read/create/manage)
  → seed roles_permissions (admin/leader full; staff read all + create dept; accountant KHÔNG)

Revision ID: 1718870400009
Revises: 1718870400008 (M8 NC & CAPA)
Create Date: 2026-07-07

Thứ tự migration: M7→M1→M2→M4→M3→M5→M6→M8→M10 (file này).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400009"
down_revision: Union[str, None] = "1718870400008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # ===== TABLE 1: risks — sổ rủi ro/cơ hội §8.5 (level GENERATED) =====
    op.execute(
        """
        CREATE TABLE risks (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            risk_code        VARCHAR(32)  NOT NULL,
            kind             VARCHAR(12)  NOT NULL DEFAULT 'risk'
                CHECK (kind IN ('risk','opportunity')),
            title            VARCHAR(255) NOT NULL,
            context          TEXT         NOT NULL,
            process_ref      VARCHAR(255) NULL,
            likelihood       SMALLINT     NOT NULL CHECK (likelihood BETWEEN 1 AND 5),
            impact           SMALLINT     NOT NULL CHECK (impact BETWEEN 1 AND 5),
            level            SMALLINT     GENERATED ALWAYS AS (likelihood * impact) STORED,
            status           VARCHAR(12)  NOT NULL DEFAULT 'open'
                CHECK (status IN ('open','treating','monitoring','closed')),
            owner_id         UUID         NOT NULL,
            department_id    UUID         NOT NULL,
            next_review_date DATE         NULL,
            closed_at        TIMESTAMPTZ  NULL,
            closed_by        UUID         NULL,
            created_by       UUID         NOT NULL,
            created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_by       UUID         NULL,

            CONSTRAINT uq_risk_code       UNIQUE (risk_code),
            CONSTRAINT fk_risk_owner      FOREIGN KEY (owner_id)      REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_risk_dept       FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
            CONSTRAINT fk_risk_closed     FOREIGN KEY (closed_by)     REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_risk_created    FOREIGN KEY (created_by)    REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_risk_updated    FOREIGN KEY (updated_by)    REFERENCES users(id)       ON DELETE RESTRICT
        );
        """
    )

    # ===== TABLE 2: risk_treatments — biện pháp xử lý =====
    op.execute(
        """
        CREATE TABLE risk_treatments (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            risk_id    UUID        NOT NULL,
            treatment  TEXT        NOT NULL,
            owner_id   UUID        NULL,
            due_date   DATE        NULL,
            status     VARCHAR(8)  NOT NULL DEFAULT 'todo' CHECK (status IN ('todo','done')),
            done_at    TIMESTAMPTZ NULL,
            created_by UUID        NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT fk_treatment_risk    FOREIGN KEY (risk_id)    REFERENCES risks(id) ON DELETE CASCADE,
            CONSTRAINT fk_treatment_owner   FOREIGN KEY (owner_id)   REFERENCES users(id) ON DELETE SET NULL,
            CONSTRAINT fk_treatment_created FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
        );
        """
    )

    # ===== TABLE 3: improvements — cơ hội cải tiến §8.6 =====
    op.execute(
        """
        CREATE TABLE improvements (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            improvement_code VARCHAR(32)  NOT NULL,
            source           VARCHAR(16)  NOT NULL DEFAULT 'other'
                CHECK (source IN ('customer','staff','review','audit','other')),
            title            VARCHAR(255) NOT NULL,
            description      TEXT         NOT NULL,
            owner_id         UUID         NULL,
            department_id    UUID         NULL,
            status           VARCHAR(12)  NOT NULL DEFAULT 'open'
                CHECK (status IN ('open','in_progress','done','rejected')),
            linked_nc_id     UUID         NULL,
            created_by       UUID         NOT NULL,
            created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_by       UUID         NULL,

            CONSTRAINT uq_improvement_code    UNIQUE (improvement_code),
            CONSTRAINT fk_imp_owner   FOREIGN KEY (owner_id)      REFERENCES users(id)           ON DELETE SET NULL,
            CONSTRAINT fk_imp_dept    FOREIGN KEY (department_id) REFERENCES departments(id)     ON DELETE SET NULL,
            CONSTRAINT fk_imp_nc      FOREIGN KEY (linked_nc_id)  REFERENCES nonconformities(id) ON DELETE SET NULL,
            CONSTRAINT fk_imp_created FOREIGN KEY (created_by)    REFERENCES users(id)           ON DELETE RESTRICT,
            CONSTRAINT fk_imp_updated FOREIGN KEY (updated_by)    REFERENCES users(id)           ON DELETE RESTRICT
        );
        """
    )

    # ===== TABLE 4: risk_notification_dedup — CRON-8 idempotent =====
    op.execute(
        """
        CREATE TABLE risk_notification_dedup (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            risk_id        UUID        NOT NULL,
            kind           VARCHAR(20) NOT NULL CHECK (kind IN ('RISK_REVIEW_DUE')),
            milestone_days SMALLINT    NOT NULL CHECK (milestone_days IN (30, 15, 7)),
            fire_date      DATE        NOT NULL,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT fk_riskdedup_risk FOREIGN KEY (risk_id) REFERENCES risks(id) ON DELETE CASCADE,
            CONSTRAINT uq_riskdedup_risk_ms_date UNIQUE (risk_id, milestone_days, fire_date)
        );
        """
    )

    # ===== INDEXES =====
    op.execute("CREATE INDEX idx_risk_department ON risks(department_id);")
    op.execute("CREATE INDEX idx_risk_status     ON risks(status);")
    op.execute("CREATE INDEX idx_risk_kind_level ON risks(kind, level);")
    op.execute("CREATE INDEX idx_risk_owner      ON risks(owner_id);")
    op.execute("CREATE INDEX idx_risk_review_due ON risks(next_review_date) WHERE status <> 'closed' AND next_review_date IS NOT NULL;")
    op.execute("CREATE INDEX idx_risk_code_trgm  ON risks USING gin (risk_code gin_trgm_ops);")
    op.execute("CREATE INDEX idx_treatment_risk  ON risk_treatments(risk_id);")
    op.execute("CREATE INDEX idx_improvement_status ON improvements(status);")
    op.execute("CREATE INDEX idx_improvement_nc   ON improvements(linked_nc_id) WHERE linked_nc_id IS NOT NULL;")

    # ===== SEED permissions (idempotent) =====
    op.execute(
        """
        INSERT INTO permissions (resource, action, description) VALUES
            ('risk',        'read',   'Xem sổ rủi ro & cơ hội / biện pháp xử lý'),
            ('risk',        'create', 'Tạo rủi ro / cơ hội'),
            ('risk',        'manage', 'Thêm biện pháp xử lý, đóng rủi ro (QM §8.5)'),
            ('improvement', 'read',   'Xem sổ cải tiến'),
            ('improvement', 'create', 'Ghi nhận cơ hội cải tiến (§8.6)'),
            ('improvement', 'manage', 'Cập nhật/đóng cải tiến, liên kết CAPA')
        ON CONFLICT (resource, action) DO NOTHING;
        """
    )

    # ===== SEED roles_permissions (idempotent). accountant KHÔNG truy cập. =====
    op.execute(
        """
        INSERT INTO roles_permissions (role, resource, action, scope) VALUES
            ('admin','risk','read','all'), ('admin','risk','create','all'), ('admin','risk','manage','all'),
            ('admin','improvement','read','all'), ('admin','improvement','create','all'), ('admin','improvement','manage','all'),
            ('leader','risk','read','all'), ('leader','risk','create','all'), ('leader','risk','manage','all'),
            ('leader','improvement','read','all'), ('leader','improvement','create','all'), ('leader','improvement','manage','all'),
            ('staff','risk','read','all'), ('staff','risk','create','department'),
            ('staff','improvement','read','all'), ('staff','improvement','create','department')
        ON CONFLICT (role, resource, action) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS risk_notification_dedup CASCADE;")
    op.execute("DROP TABLE IF EXISTS improvements            CASCADE;")
    op.execute("DROP TABLE IF EXISTS risk_treatments         CASCADE;")
    op.execute("DROP TABLE IF EXISTS risks                   CASCADE;")

    op.execute(
        """
        DELETE FROM roles_permissions WHERE resource IN ('risk','improvement')
          AND role IN ('admin','leader','staff');
        """
    )
    op.execute("DELETE FROM permissions WHERE resource IN ('risk','improvement');")
