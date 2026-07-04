"""m2_chemical_inventory — Quản lý Hóa chất & Tồn kho (Chemical Inventory).

Tạo 6 bảng theo Contract M2 Schema (03-contract-m2-schema.md §2):
units → chemicals → chemical_lots → chemical_transactions →
chemical_recheck_records → chemical_notification_dedup → indexes → seed units.

DDL viết raw SQL để khớp CHÍNH XÁC contract (CHECK, composite FK, partial unique,
partial index qty_base>0, FK RESTRICT, ref_sample_id → samples.id ON DELETE RESTRICT).
Bảng IMMUTABLE (chemical_transactions): không thêm trigger riêng — enforce ở app-layer
(không expose route sửa/xóa) đồng bộ phong cách M7/M1.

Seed bổ sung roles_permissions: chemical:create cho leader/staff (department) — contract
04-api cho phép Admin + KTV(phòng) tạo hóa chất/lô; M7 mới seed chemical:create cho admin.
Thêm idempotent (ON CONFLICT DO NOTHING) để khớp contract mà không sửa migration M7.

Revision ID: 1718870400003
Revises: 1718870400002 (M1 sample lifecycle)
Create Date: 2026-06-20

Thứ tự migration tổng thể: M7 → M1 → M2 (FK ref_sample_id → samples.id của M1).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400003"
down_revision: Union[str, None] = "1718870400002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgcrypto + pg_trgm đã bật ở M7; CREATE IF NOT EXISTS để an toàn nếu chạy độc lập.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # ===== 1. units (danh mục seed cố định, natural PK code) =====
    op.execute(
        """
        CREATE TABLE units (
            code                VARCHAR(16)  PRIMARY KEY,
            label               VARCHAR(64)  NOT NULL,
            measurement_group   VARCHAR(10)  NOT NULL
                CHECK (measurement_group IN ('mass', 'volume', 'count')),
            factor_to_base      NUMERIC(20,6) NOT NULL CHECK (factor_to_base > 0),
            UNIQUE (code, measurement_group)
        );
        """
    )

    # ===== 2. chemicals =====
    op.execute(
        """
        CREATE TABLE chemicals (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name                VARCHAR(255) NOT NULL,
            cas_no              VARCHAR(20)  NULL,
            manufacturer        VARCHAR(255) NULL,
            base_unit           VARCHAR(16)  NOT NULL,
            measurement_group   VARCHAR(10)  NOT NULL
                CHECK (measurement_group IN ('mass', 'volume', 'count')),
            hazard_code         VARCHAR(64)  NULL,
            reorder_threshold   NUMERIC(18,6) NULL
                CHECK (reorder_threshold IS NULL OR reorder_threshold >= 0),
            department_id       UUID         NOT NULL,
            status              VARCHAR(10)  NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'inactive')),
            created_by          UUID         NOT NULL,
            updated_by          UUID         NULL,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_chem_dept     FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
            CONSTRAINT fk_chem_created  FOREIGN KEY (created_by)    REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_chem_updated  FOREIGN KEY (updated_by)    REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_chem_baseunit FOREIGN KEY (base_unit, measurement_group)
                REFERENCES units(code, measurement_group) ON DELETE RESTRICT,
            CONSTRAINT uq_chem_dept_name_cas UNIQUE (department_id, name, cas_no)
        );
        """
    )

    # ===== 3. chemical_lots =====
    op.execute(
        """
        CREATE TABLE chemical_lots (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            chemical_id         UUID         NOT NULL,
            lot_no              VARCHAR(64)  NOT NULL,
            qty_base            NUMERIC(18,6) NOT NULL DEFAULT 0 CHECK (qty_base >= 0),
            unit_price          NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (unit_price >= 0),
            price_unit          VARCHAR(16)  NOT NULL,
            currency            VARCHAR(3)   NOT NULL DEFAULT 'VND',
            received_at         DATE         NULL,
            expiry_date         DATE         NULL,
            recheck_date        DATE         NULL,
            recheck_result      VARCHAR(4)   NULL
                CHECK (recheck_result IS NULL OR recheck_result IN ('pass', 'fail')),
            is_expired          BOOLEAN      NOT NULL DEFAULT false,
            coa_file_key        VARCHAR(512) NULL,
            created_by          UUID         NOT NULL,
            updated_by          UUID         NULL,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_lot_chemical  FOREIGN KEY (chemical_id) REFERENCES chemicals(id) ON DELETE RESTRICT,
            CONSTRAINT fk_lot_priceunit FOREIGN KEY (price_unit)  REFERENCES units(code)   ON DELETE RESTRICT,
            CONSTRAINT fk_lot_created   FOREIGN KEY (created_by)   REFERENCES users(id)     ON DELETE RESTRICT,
            CONSTRAINT fk_lot_updated   FOREIGN KEY (updated_by)   REFERENCES users(id)     ON DELETE RESTRICT,
            CONSTRAINT uq_lot_chem_lotno UNIQUE (chemical_id, lot_no),
            CONSTRAINT ck_lot_date_order CHECK (
                recheck_date IS NULL OR expiry_date IS NULL OR recheck_date <= expiry_date
            )
        );
        """
    )

    # ===== 4. chemical_transactions (IMMUTABLE) =====
    op.execute(
        """
        CREATE TABLE chemical_transactions (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            lot_id              UUID         NOT NULL,
            type                VARCHAR(8)   NOT NULL CHECK (type IN ('in', 'out', 'adjust')),
            qty_base            NUMERIC(18,6) NOT NULL,
            base_unit           VARCHAR(16)  NOT NULL,
            qty_input           NUMERIC(14,4) NOT NULL,
            input_unit          VARCHAR(16)  NOT NULL,
            balance_after       NUMERIC(18,6) NOT NULL CHECK (balance_after >= 0),
            unit_price          NUMERIC(14,2) NULL CHECK (unit_price IS NULL OR unit_price >= 0),
            price_unit          VARCHAR(16)  NULL,
            currency            VARCHAR(3)   NULL,
            ref_sample_id       UUID         NULL,
            warning_override    BOOLEAN      NOT NULL DEFAULT false,
            note                TEXT         NULL,
            by_user             UUID         NOT NULL,
            correlation_id      VARCHAR(64)  NULL,
            at                  TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_txn_lot       FOREIGN KEY (lot_id)        REFERENCES chemical_lots(id) ON DELETE RESTRICT,
            CONSTRAINT fk_txn_baseunit  FOREIGN KEY (base_unit)     REFERENCES units(code)       ON DELETE RESTRICT,
            CONSTRAINT fk_txn_inputunit FOREIGN KEY (input_unit)    REFERENCES units(code)       ON DELETE RESTRICT,
            CONSTRAINT fk_txn_priceunit FOREIGN KEY (price_unit)    REFERENCES units(code)       ON DELETE RESTRICT,
            CONSTRAINT fk_txn_sample    FOREIGN KEY (ref_sample_id) REFERENCES samples(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_txn_byuser    FOREIGN KEY (by_user)       REFERENCES users(id)         ON DELETE RESTRICT,

            CONSTRAINT ck_txn_qty_sign CHECK (
                (type IN ('in', 'out') AND qty_base > 0)
                OR (type = 'adjust' AND qty_base <> 0)
            ),
            CONSTRAINT ck_txn_out_sample CHECK (
                type <> 'out' OR ref_sample_id IS NOT NULL
            ),
            CONSTRAINT ck_txn_adjust_note CHECK (
                type <> 'adjust' OR (note IS NOT NULL AND length(btrim(note)) > 0)
            )
        );
        """
    )

    # ===== 5. chemical_recheck_records =====
    op.execute(
        """
        CREATE TABLE chemical_recheck_records (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            lot_id              UUID         NOT NULL,
            checked_at          DATE         NOT NULL,
            result              VARCHAR(4)   NOT NULL CHECK (result IN ('pass', 'fail')),
            note                TEXT         NULL,
            attachment_id       UUID         NULL,
            next_recheck_date   DATE         NULL,
            checked_by          UUID         NOT NULL,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_recheck_lot    FOREIGN KEY (lot_id)        REFERENCES chemical_lots(id) ON DELETE RESTRICT,
            CONSTRAINT fk_recheck_attach FOREIGN KEY (attachment_id) REFERENCES attachments(id)   ON DELETE SET NULL,
            CONSTRAINT fk_recheck_byuser FOREIGN KEY (checked_by)    REFERENCES users(id)         ON DELETE RESTRICT
        );
        """
    )

    # ===== 6. chemical_notification_dedup =====
    op.execute(
        """
        CREATE TABLE chemical_notification_dedup (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            lot_id              UUID         NOT NULL,
            kind                VARCHAR(20)  NOT NULL
                CHECK (kind IN ('CHEM_EXPIRY', 'CHEM_RECHECK_DUE')),
            milestone_days      SMALLINT     NOT NULL CHECK (milestone_days IN (30, 15, 7)),
            fire_date           DATE         NOT NULL,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_dedup_lot FOREIGN KEY (lot_id) REFERENCES chemical_lots(id) ON DELETE CASCADE,
            CONSTRAINT uq_dedup_lot_kind_ms_date UNIQUE (lot_id, kind, milestone_days, fire_date)
        );
        """
    )

    # ===== INDEXES (§4 contract) =====
    op.execute("CREATE INDEX idx_chemicals_department ON chemicals(department_id);")
    op.execute("CREATE INDEX idx_chemicals_status     ON chemicals(status);")
    op.execute("CREATE INDEX idx_chemicals_cas        ON chemicals(cas_no) WHERE cas_no IS NOT NULL;")
    op.execute("CREATE INDEX idx_chemicals_name_trgm  ON chemicals USING gin (name gin_trgm_ops);")
    op.execute(
        "CREATE UNIQUE INDEX uq_chemicals_dept_name_nullcas "
        "ON chemicals(department_id, name) WHERE cas_no IS NULL;"
    )
    op.execute("CREATE INDEX idx_chemicals_base_unit  ON chemicals(base_unit);")

    op.execute("CREATE INDEX idx_lots_chemical        ON chemical_lots(chemical_id);")
    op.execute("CREATE INDEX idx_lots_expiry_active   ON chemical_lots(expiry_date) WHERE qty_base > 0;")
    op.execute("CREATE INDEX idx_lots_recheck_active  ON chemical_lots(recheck_date) WHERE qty_base > 0;")
    op.execute(
        "CREATE INDEX idx_lots_recheck_result ON chemical_lots(recheck_result) "
        "WHERE recheck_result IS NOT NULL;"
    )
    op.execute("CREATE INDEX idx_lots_price_unit      ON chemical_lots(price_unit);")

    op.execute("CREATE INDEX idx_txn_lot             ON chemical_transactions(lot_id);")
    op.execute(
        "CREATE INDEX idx_txn_ref_sample ON chemical_transactions(ref_sample_id) "
        "WHERE ref_sample_id IS NOT NULL;"
    )
    op.execute("CREATE INDEX idx_txn_by_user         ON chemical_transactions(by_user);")
    op.execute("CREATE INDEX idx_txn_type_at         ON chemical_transactions(type, at DESC);")
    op.execute("CREATE INDEX idx_txn_lot_at          ON chemical_transactions(lot_id, at DESC);")
    op.execute("CREATE INDEX idx_txn_at              ON chemical_transactions(at DESC);")

    op.execute("CREATE INDEX idx_recheck_lot ON chemical_recheck_records(lot_id, checked_at DESC);")

    # ===== SEED units (§5 contract) =====
    op.execute(
        """
        INSERT INTO units (code, label, measurement_group, factor_to_base) VALUES
            ('mg',   'Miligam',   'mass',   1),
            ('g',    'Gam',       'mass',   1000),
            ('kg',   'Kilogam',   'mass',   1000000),
            ('mL',   'Mililit',   'volume', 1),
            ('L',    'Lit',       'volume', 1000),
            ('unit', 'Đơn vị',    'count',  1),
            ('vien', 'Viên',      'count',  1),
            ('ong',  'Ống',       'count',  1)
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # ===== SEED bổ sung roles_permissions: chemical:create cho leader/staff =====
    # Contract 04-api: tạo hóa chất/lô = Admin + KTV(phòng). M7 mới seed cho admin.
    op.execute(
        """
        INSERT INTO roles_permissions (role, resource, action, scope) VALUES
            ('leader', 'chemical', 'create', 'all'),
            ('staff',  'chemical', 'create', 'department')
        ON CONFLICT (role, resource, action) DO NOTHING;
        """
    )


def downgrade() -> None:
    # Drop ngược thứ tự FK (§9 contract). KHÔNG drop extension dùng chung.
    op.execute(
        "DELETE FROM roles_permissions WHERE resource = 'chemical' AND action = 'create' "
        "AND role IN ('leader', 'staff');"
    )
    op.execute("DROP TABLE IF EXISTS chemical_notification_dedup CASCADE;")
    op.execute("DROP TABLE IF EXISTS chemical_recheck_records    CASCADE;")
    op.execute("DROP TABLE IF EXISTS chemical_transactions       CASCADE;")
    op.execute("DROP TABLE IF EXISTS chemical_lots               CASCADE;")
    op.execute("DROP TABLE IF EXISTS chemicals                   CASCADE;")
    op.execute("DROP TABLE IF EXISTS units                       CASCADE;")
