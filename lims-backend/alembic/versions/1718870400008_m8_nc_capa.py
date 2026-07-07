"""m8_nc_capa — Không phù hợp & Hành động khắc phục (NC & CAPA, §7.10/§8.7/§8.4).

Tạo 4 bảng theo Contract M8 (23-contract-m8-nc-capa.md §1), thứ tự tuyến tính (KHÔNG vòng FK):
  ALTER users (+is_quality_manager cờ QM) → nonconformities → capa (UNIQUE nc_id) →
  capa_actions → capa_notification_dedup (CRON-7 idempotent)
  → trigger capa BẤT BIẾN sau đóng (chặn UPDATE khi status='closed' + chặn DELETE)
  → indexes → seed permissions (nonconformity:read/create/manage)
  → seed roles_permissions (admin/leader full; staff read all + create dept; accountant KHÔNG)

DDL raw SQL khớp contract (CHECK enum thay native ENUM). QM (mở/đóng CAPA cho staff) gate
app-layer bằng users.is_quality_manager. Logic nghiệp vụ enforce app-layer.

Revision ID: 1718870400008
Revises: 1718870400007 (M6 Reporting)
Create Date: 2026-07-07

Thứ tự migration tổng thể: M7 → M1 → M2 → M4 → M3 → M5 → M6 → M8 (file này).
Phụ thuộc users/departments/audit_logs/notifications/permissions/roles_permissions (M7).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400008"
down_revision: Union[str, None] = "1718870400007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")  # gen_random_uuid()

    # ===== ALTER users: +is_quality_manager (cờ QM §8.7 — pattern is_dept_lead) =====
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_quality_manager BOOLEAN NOT NULL DEFAULT false;"
    )

    # ===== TABLE 1: nonconformities — phiếu NC §7.10 (nguồn polymorphic) =====
    op.execute(
        """
        CREATE TABLE nonconformities (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            nc_code           VARCHAR(32)  NOT NULL,
            source_type       VARCHAR(16)  NOT NULL DEFAULT 'manual'
                CHECK (source_type IN ('manual','complaint','qc','audit','env','sample','pt')),
            source_id         UUID         NULL,
            severity          VARCHAR(12)  NOT NULL
                CHECK (severity IN ('minor','major','critical')),
            title             VARCHAR(255) NOT NULL,
            description       TEXT         NOT NULL,
            impact_assessment TEXT         NULL,
            affected_ref_type VARCHAR(32)  NULL,
            affected_ref_id   UUID         NULL,
            department_id     UUID         NOT NULL,
            raised_by         UUID         NOT NULL,
            raised_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
            status            VARCHAR(12)  NOT NULL DEFAULT 'open'
                CHECK (status IN ('open','in_capa','closed','cancelled')),
            created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_by        UUID         NULL,

            CONSTRAINT uq_nc_code        UNIQUE (nc_code),
            CONSTRAINT fk_nc_dept        FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
            CONSTRAINT fk_nc_raised_by   FOREIGN KEY (raised_by)     REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_nc_updated_by  FOREIGN KEY (updated_by)    REFERENCES users(id)       ON DELETE RESTRICT
        );
        """
    )

    # ===== TABLE 2: capa — hành động khắc phục §8.7 (1 CAPA / 1 NC) =====
    op.execute(
        """
        CREATE TABLE capa (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            nc_id                UUID         NOT NULL,
            capa_type            VARCHAR(12)  NOT NULL DEFAULT 'corrective'
                CHECK (capa_type IN ('corrective','preventive')),
            root_cause           TEXT         NOT NULL,
            owner_id             UUID         NOT NULL,
            due_date             DATE         NULL,
            status               VARCHAR(12)  NOT NULL DEFAULT 'in_progress'
                CHECK (status IN ('in_progress','closed')),
            effectiveness_result VARCHAR(16)  NULL
                CHECK (effectiveness_result IS NULL OR effectiveness_result IN ('effective','not_effective')),
            effectiveness_note   TEXT         NULL,
            verified_by          UUID         NULL,
            verified_at          TIMESTAMPTZ  NULL,
            closed_by            UUID         NULL,
            closed_at            TIMESTAMPTZ  NULL,
            created_by           UUID         NOT NULL,
            created_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT uq_capa_nc        UNIQUE (nc_id),
            CONSTRAINT fk_capa_nc        FOREIGN KEY (nc_id)       REFERENCES nonconformities(id) ON DELETE CASCADE,
            CONSTRAINT fk_capa_owner     FOREIGN KEY (owner_id)    REFERENCES users(id)           ON DELETE RESTRICT,
            CONSTRAINT fk_capa_verified  FOREIGN KEY (verified_by) REFERENCES users(id)           ON DELETE RESTRICT,
            CONSTRAINT fk_capa_closed    FOREIGN KEY (closed_by)   REFERENCES users(id)           ON DELETE RESTRICT,
            CONSTRAINT fk_capa_created   FOREIGN KEY (created_by)  REFERENCES users(id)           ON DELETE RESTRICT
        );
        """
    )

    # ===== TABLE 3: capa_actions — hành động con =====
    op.execute(
        """
        CREATE TABLE capa_actions (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            capa_id      UUID        NOT NULL,
            action       TEXT        NOT NULL,
            assignee_id  UUID        NULL,
            due_date     DATE        NULL,
            status       VARCHAR(8)  NOT NULL DEFAULT 'todo'
                CHECK (status IN ('todo','done')),
            done_at      TIMESTAMPTZ NULL,
            note         TEXT        NULL,
            created_by   UUID        NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT fk_action_capa     FOREIGN KEY (capa_id)     REFERENCES capa(id)  ON DELETE CASCADE,
            CONSTRAINT fk_action_assignee FOREIGN KEY (assignee_id) REFERENCES users(id) ON DELETE SET NULL,
            CONSTRAINT fk_action_created  FOREIGN KEY (created_by)  REFERENCES users(id) ON DELETE RESTRICT
        );
        """
    )

    # ===== TABLE 4: capa_notification_dedup — CRON-7 idempotent =====
    op.execute(
        """
        CREATE TABLE capa_notification_dedup (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            capa_id        UUID        NOT NULL,
            kind           VARCHAR(20) NOT NULL CHECK (kind IN ('CAPA_DUE')),
            milestone_days SMALLINT    NOT NULL CHECK (milestone_days IN (7, 3, 0)),
            fire_date      DATE        NOT NULL,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT fk_capadedup_capa FOREIGN KEY (capa_id) REFERENCES capa(id) ON DELETE CASCADE,
            CONSTRAINT uq_capadedup_capa_ms_date UNIQUE (capa_id, milestone_days, fire_date)
        );
        """
    )

    # ===== TRIGGER: capa BẤT BIẾN sau đóng (§8.7) — chặn UPDATE khi closed + chặn DELETE =====
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_capa_immutable_when_closed()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'capa is an append-only record (ISO/IEC 17025 §8.7): DELETE not allowed';
            END IF;
            IF OLD.status = 'closed' THEN
                RAISE EXCEPTION 'capa is immutable once closed (ISO/IEC 17025 §8.7): UPDATE not allowed';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER capa_no_update_when_closed
            BEFORE UPDATE ON capa
            FOR EACH ROW EXECUTE FUNCTION trg_capa_immutable_when_closed();
        """
    )
    op.execute(
        """
        CREATE TRIGGER capa_no_delete
            BEFORE DELETE ON capa
            FOR EACH ROW EXECUTE FUNCTION trg_capa_immutable_when_closed();
        """
    )

    # ===== INDEXES =====
    op.execute("CREATE INDEX idx_nc_department ON nonconformities(department_id);")
    op.execute("CREATE INDEX idx_nc_status     ON nonconformities(status);")
    op.execute("CREATE INDEX idx_nc_severity   ON nonconformities(severity);")
    op.execute("CREATE INDEX idx_nc_source     ON nonconformities(source_type, source_id);")
    op.execute("CREATE INDEX idx_nc_raised_at  ON nonconformities(raised_at DESC);")
    op.execute("CREATE INDEX idx_nc_code_trgm  ON nonconformities USING gin (nc_code gin_trgm_ops);")
    op.execute("CREATE INDEX idx_capa_owner    ON capa(owner_id);")
    op.execute("CREATE INDEX idx_capa_due      ON capa(due_date) WHERE status = 'in_progress';")
    op.execute("CREATE INDEX idx_action_capa   ON capa_actions(capa_id);")

    # ===== SEED permissions (idempotent) =====
    op.execute(
        """
        INSERT INTO permissions (resource, action, description) VALUES
            ('nonconformity', 'read',   'Xem phiếu không phù hợp / CAPA / hành động khắc phục'),
            ('nonconformity', 'create', 'Tạo phiếu không phù hợp (NC)'),
            ('nonconformity', 'manage', 'Mở/đóng CAPA, thêm hành động, xác minh hiệu lực (QM §8.7)')
        ON CONFLICT (resource, action) DO NOTHING;
        """
    )

    # ===== SEED roles_permissions (idempotent). accountant KHÔNG truy cập (cách ly lab). =====
    op.execute(
        """
        INSERT INTO roles_permissions (role, resource, action, scope) VALUES
            ('admin','nonconformity','read','all'),
            ('admin','nonconformity','create','all'),
            ('admin','nonconformity','manage','all'),

            ('leader','nonconformity','read','all'),
            ('leader','nonconformity','create','all'),
            ('leader','nonconformity','manage','all'),

            ('staff','nonconformity','read','all'),
            ('staff','nonconformity','create','department')
        ON CONFLICT (role, resource, action) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS capa_no_delete ON capa;")
    op.execute("DROP TRIGGER IF EXISTS capa_no_update_when_closed ON capa;")
    op.execute("DROP FUNCTION IF EXISTS trg_capa_immutable_when_closed();")
    op.execute("DROP TABLE IF EXISTS capa_notification_dedup CASCADE;")
    op.execute("DROP TABLE IF EXISTS capa_actions            CASCADE;")
    op.execute("DROP TABLE IF EXISTS capa                    CASCADE;")
    op.execute("DROP TABLE IF EXISTS nonconformities         CASCADE;")

    op.execute(
        """
        DELETE FROM roles_permissions WHERE (role, resource, action) IN (
            ('admin','nonconformity','read'), ('admin','nonconformity','create'),
            ('admin','nonconformity','manage'),
            ('leader','nonconformity','read'), ('leader','nonconformity','create'),
            ('leader','nonconformity','manage'),
            ('staff','nonconformity','read'), ('staff','nonconformity','create')
        );
        """
    )
    op.execute(
        """
        DELETE FROM permissions WHERE (resource, action) IN (
            ('nonconformity','read'), ('nonconformity','create'), ('nonconformity','manage')
        );
        """
    )
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_quality_manager;")
    # KHÔNG drop extension pgcrypto/pg_trgm (dùng chung M7).
