"""m5_equipment_calibration — Quản lý Thiết bị & Hiệu chuẩn (§6.4/§6.5/§8.4).

Tạo 3 bảng theo Contract M5 Schema (17-contract-m5-schema.md §2), thứ tự tuyến tính
(KHÔNG vòng FK — D3):
  equipments (next_due_date denormalize) → calibration_records (IMMUTABLE, trigger DB
  chặn UPDATE/DELETE — D5) → equipment_notification_dedup (CRON-5 idempotent — D8)
  → trigger immutable (calibration_records) → indexes
  → seed permissions (equipment:read/create/update, calibration:create)
  → seed roles_permissions (ma trận §5.3: leader=👁 chỉ xem, accountant=read only,
    staff=read all + ghi phòng mình, admin=full) — idempotent ON CONFLICT.

DDL raw SQL khớp CHÍNH XÁC contract (CHECK enum thay native ENUM; cặp value/unit nhất
quán ck_equip_cycle_pair; trigger immutable như audit_logs M7 D8). Logic nghiệp vụ
(tính next_due, denormalize lần gần nhất, RBAC scope, badge, người phụ trách cùng phòng)
enforce app-layer.

attachments.owner_type whitelist ('equipment','calibration') ĐÃ có ở M7 → KHÔNG ALTER.

Revision ID: 1718870400006
Revises: 1718870400005 (M3 Document Control)
Create Date: 2026-06-20

Thứ tự migration tổng thể: M7 → M1 → M2 → M4 → M3 → M5 (file này).
Phụ thuộc users/departments/attachments/audit_logs/notifications/permissions/
roles_permissions (M7).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400006"
down_revision: Union[str, None] = "1718870400005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")  # gen_random_uuid()
    # pg_trgm đã bật ở M7 (dùng cho GIN trgm name/code) → KHÔNG tạo lại.

    # ===== TABLE 1: equipments — thiết bị §6.4 (D3/D4/D9) =====
    op.execute(
        """
        CREATE TABLE equipments (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code                    VARCHAR(64)  NOT NULL,
            name                    VARCHAR(255) NOT NULL,
            location                VARCHAR(255) NULL,
            department_id           UUID         NOT NULL,
            responsible_user_id     UUID         NULL,
            purchase_date           DATE         NULL,
            status                  VARCHAR(12)  NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'maintenance', 'broken', 'retired')),
            calibration_cycle_value INT          NULL
                CHECK (calibration_cycle_value IS NULL OR calibration_cycle_value > 0),
            calibration_cycle_unit  VARCHAR(8)   NULL
                CHECK (calibration_cycle_unit IS NULL OR calibration_cycle_unit IN ('month', 'year')),
            next_due_date           DATE         NULL,
            note                    TEXT         NULL,
            created_by              UUID         NOT NULL,
            updated_by              UUID         NULL,
            created_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
            deleted_at              TIMESTAMPTZ  NULL,

            CONSTRAINT uq_equip_code    UNIQUE (code),
            CONSTRAINT fk_equip_dept    FOREIGN KEY (department_id)       REFERENCES departments(id) ON DELETE RESTRICT,
            CONSTRAINT fk_equip_resp    FOREIGN KEY (responsible_user_id) REFERENCES users(id)       ON DELETE SET NULL,
            CONSTRAINT fk_equip_created FOREIGN KEY (created_by)          REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_equip_updated FOREIGN KEY (updated_by)          REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT ck_equip_cycle_pair CHECK (
                (calibration_cycle_value IS NULL AND calibration_cycle_unit IS NULL)
                OR (calibration_cycle_value IS NOT NULL AND calibration_cycle_unit IS NOT NULL)
            )
        );
        """
    )

    # ===== TABLE 2: calibration_records — lần hiệu chuẩn §6.4/§6.5 (IMMUTABLE, D5) =====
    op.execute(
        """
        CREATE TABLE calibration_records (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            equipment_id    UUID         NOT NULL,
            calibrated_at   DATE         NOT NULL,
            provider        VARCHAR(255) NULL,
            result          VARCHAR(8)   NOT NULL
                CHECK (result IN ('pass', 'fail')),
            next_due_date   DATE         NOT NULL,
            cert_file_key   VARCHAR(512) NULL,
            note            TEXT         NULL,
            correction_of   UUID         NULL,
            override_reason VARCHAR(255) NULL,
            next_due_overridden BOOLEAN  NOT NULL DEFAULT false,
            created_by      UUID         NOT NULL,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_cal_equipment FOREIGN KEY (equipment_id)  REFERENCES equipments(id)          ON DELETE RESTRICT,
            CONSTRAINT fk_cal_created   FOREIGN KEY (created_by)     REFERENCES users(id)               ON DELETE RESTRICT,
            CONSTRAINT fk_cal_correction FOREIGN KEY (correction_of) REFERENCES calibration_records(id) ON DELETE RESTRICT
        );
        """
    )

    # ===== TABLE 3: equipment_notification_dedup — CRON-5 idempotent (D8) =====
    op.execute(
        """
        CREATE TABLE equipment_notification_dedup (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            equipment_id    UUID         NOT NULL,
            kind            VARCHAR(20)  NOT NULL
                CHECK (kind IN ('CALIBRATION_DUE')),
            milestone_days  SMALLINT     NOT NULL
                CHECK (milestone_days IN (30, 15, 7)),
            fire_date       DATE         NOT NULL,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_eqdedup_equipment FOREIGN KEY (equipment_id) REFERENCES equipments(id) ON DELETE CASCADE,
            CONSTRAINT uq_eqdedup_eq_ms_date UNIQUE (equipment_id, milestone_days, fire_date)
        );
        """
    )

    # ===== TRIGGER: calibration_records IMMUTABLE — chặn UPDATE/DELETE (D5, §8.4) =====
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_calibration_records_immutable()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'calibration_records is immutable (ISO/IEC 17025 §8.4): % not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER calibration_records_no_update
            BEFORE UPDATE ON calibration_records
            FOR EACH ROW EXECUTE FUNCTION trg_calibration_records_immutable();
        """
    )
    op.execute(
        """
        CREATE TRIGGER calibration_records_no_delete
            BEFORE DELETE ON calibration_records
            FOR EACH ROW EXECUTE FUNCTION trg_calibration_records_immutable();
        """
    )

    # ===== INDEXES (§4 contract) =====
    op.execute(
        "CREATE INDEX idx_equip_department  ON equipments(department_id) WHERE deleted_at IS NULL;"
    )
    op.execute(
        "CREATE INDEX idx_equip_status      ON equipments(status) WHERE deleted_at IS NULL;"
    )
    op.execute(
        "CREATE INDEX idx_equip_dept_status ON equipments(department_id, status) WHERE deleted_at IS NULL;"
    )
    op.execute(
        "CREATE INDEX idx_equip_next_due    ON equipments(next_due_date) "
        "WHERE next_due_date IS NOT NULL AND deleted_at IS NULL;"
    )
    op.execute(
        "CREATE INDEX idx_equip_responsible ON equipments(responsible_user_id) "
        "WHERE responsible_user_id IS NOT NULL;"
    )
    op.execute(
        "CREATE INDEX idx_equip_name_trgm   ON equipments USING gin (name gin_trgm_ops);"
    )
    op.execute(
        "CREATE INDEX idx_equip_code_trgm   ON equipments USING gin (code gin_trgm_ops);"
    )
    op.execute(
        "CREATE INDEX idx_cal_equip_date    ON calibration_records(equipment_id, calibrated_at DESC);"
    )
    op.execute(
        "CREATE INDEX idx_cal_created_by    ON calibration_records(created_by);"
    )

    # ===== SEED permissions (action mịn M5; FK fk_rp_permission cần có trước) — idempotent =====
    op.execute(
        """
        INSERT INTO permissions (resource, action, description) VALUES
            ('equipment',   'read',   'Xem thiết bị / lịch sử hiệu chuẩn / cảnh báo'),
            ('equipment',   'create', 'Tạo thiết bị + đính kèm tài liệu thiết bị'),
            ('equipment',   'update', 'Sửa thiết bị / tình trạng / cấu hình chu kỳ hiệu chuẩn'),
            ('calibration', 'create', 'Ghi lần hiệu chuẩn (CoC + tự tính next_due)')
        ON CONFLICT (resource, action) DO NOTHING;
        """
    )

    # ===== SEED roles_permissions (ma trận §5.3) — idempotent =====
    op.execute(
        """
        INSERT INTO roles_permissions (role, resource, action, scope) VALUES
            ('admin','equipment','read','all'),
            ('admin','equipment','create','all'),
            ('admin','equipment','update','all'),
            ('admin','calibration','create','all'),

            ('leader','equipment','read','all'),

            ('accountant','equipment','read','all'),

            ('staff','equipment','read','all'),
            ('staff','equipment','create','department'),
            ('staff','equipment','update','department'),
            ('staff','calibration','create','department')
        ON CONFLICT (role, resource, action) DO NOTHING;
        """
    )


def downgrade() -> None:
    # Drop ngược thứ tự; gỡ trigger + function (§9 contract).
    op.execute("DROP TRIGGER IF EXISTS calibration_records_no_delete ON calibration_records;")
    op.execute("DROP TRIGGER IF EXISTS calibration_records_no_update ON calibration_records;")
    op.execute("DROP FUNCTION IF EXISTS trg_calibration_records_immutable();")
    op.execute("DROP TABLE IF EXISTS equipment_notification_dedup CASCADE;")
    op.execute("DROP TABLE IF EXISTS calibration_records          CASCADE;")
    op.execute("DROP TABLE IF EXISTS equipments                   CASCADE;")

    # Thu hồi seed M5 (chỉ dòng M5 thêm — KHÔNG đụng seed M7).
    op.execute(
        """
        DELETE FROM roles_permissions WHERE (role, resource, action) IN (
            ('admin','equipment','read'), ('admin','equipment','create'),
            ('admin','equipment','update'), ('admin','calibration','create'),
            ('leader','equipment','read'),
            ('accountant','equipment','read'),
            ('staff','equipment','read'), ('staff','equipment','create'),
            ('staff','equipment','update'), ('staff','calibration','create')
        );
        """
    )
    op.execute(
        """
        DELETE FROM permissions WHERE (resource, action) IN (
            ('equipment','read'), ('equipment','create'),
            ('equipment','update'), ('calibration','create')
        );
        """
    )
    # KHÔNG drop extension pgcrypto/pg_trgm (dùng chung M7).
