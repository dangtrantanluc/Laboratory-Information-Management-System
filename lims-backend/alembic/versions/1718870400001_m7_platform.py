"""m7_platform — migration nền tảng đầu tiên (Auth, Org, RBAC, Audit, Notification, Attachment).

Tạo 10 bảng theo Contract M7 Schema (08-contract-m7-schema.md §2):
departments → users → ALTER fk_dept_lead/created/updated → permissions →
roles_permissions → customers → attachments → refresh_tokens → notifications →
audit_logs → access_stats → trigger append-only → indexes → seed.

DDL viết raw SQL để khớp CHÍNH XÁC contract (CHECK, trigger, vòng FK, citext).

Revision ID: 1718870400001
Revises:
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op

from app.config import settings
from app.core.security import hash_password

revision: str = "1718870400001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ---- Extensions dùng chung toàn hệ thống ----
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext;")

    # ===== 1. departments (lead_user_id NULL, chưa FK — D3) =====
    op.execute(
        """
        CREATE TABLE departments (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name         VARCHAR(255) NOT NULL,
            code         VARCHAR(32)  NOT NULL,
            parent_id    UUID         NULL,
            lead_user_id UUID         NULL,
            status       VARCHAR(10)  NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'inactive')),
            created_by   UUID         NULL,
            updated_by   UUID         NULL,
            created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT uq_dept_code   UNIQUE (code),
            CONSTRAINT fk_dept_parent FOREIGN KEY (parent_id) REFERENCES departments(id) ON DELETE RESTRICT,
            CONSTRAINT ck_dept_not_self_parent CHECK (parent_id IS NULL OR parent_id <> id)
        );
        """
    )

    # ===== 2. users (FK department_id → departments) =====
    op.execute(
        """
        CREATE TABLE users (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email               CITEXT       NOT NULL,
            password_hash       VARCHAR(255) NOT NULL,
            full_name           VARCHAR(255) NOT NULL,
            department_id       UUID         NULL,
            role                VARCHAR(16)  NOT NULL
                CHECK (role IN ('admin', 'leader', 'accountant', 'staff')),
            status              VARCHAR(10)  NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'disabled')),
            last_login_at       TIMESTAMPTZ  NULL,
            password_changed_at TIMESTAMPTZ  NULL,
            created_by          UUID         NULL,
            updated_by          UUID         NULL,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT uq_users_email   UNIQUE (email),
            CONSTRAINT fk_users_dept    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
            CONSTRAINT fk_users_created FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
            CONSTRAINT fk_users_updated FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT,
            CONSTRAINT ck_users_email   CHECK (position('@' IN email) > 1)
        );
        """
    )

    # ===== ALTER: gắn FK vòng (D3) =====
    op.execute(
        """
        ALTER TABLE departments
            ADD CONSTRAINT fk_dept_lead FOREIGN KEY (lead_user_id)
            REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE departments
            ADD CONSTRAINT fk_dept_created FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT;
        ALTER TABLE departments
            ADD CONSTRAINT fk_dept_updated FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT;
        """
    )

    # ===== 3. permissions =====
    op.execute(
        """
        CREATE TABLE permissions (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            resource    VARCHAR(64)  NOT NULL,
            action      VARCHAR(32)  NOT NULL,
            description VARCHAR(255) NULL,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT uq_perm_resource_action UNIQUE (resource, action)
        );
        """
    )

    # ===== 4. roles_permissions =====
    op.execute(
        """
        CREATE TABLE roles_permissions (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            role        VARCHAR(16)  NOT NULL
                CHECK (role IN ('admin', 'leader', 'accountant', 'staff')),
            resource    VARCHAR(64)  NOT NULL,
            action      VARCHAR(32)  NOT NULL,
            scope       VARCHAR(12)  NOT NULL DEFAULT 'all'
                CHECK (scope IN ('all', 'department', 'own')),
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT uq_rp_role_res_act UNIQUE (role, resource, action),
            CONSTRAINT fk_rp_permission FOREIGN KEY (resource, action)
                REFERENCES permissions(resource, action) ON DELETE CASCADE
        );
        """
    )

    # ===== 5. customers =====
    op.execute(
        """
        CREATE TABLE customers (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name       VARCHAR(255) NOT NULL,
            contact    VARCHAR(255) NULL,
            type       VARCHAR(16)  NOT NULL DEFAULT 'external'
                CHECK (type IN ('internal', 'external', 'individual', 'organization')),
            note       TEXT         NULL,
            deleted_at TIMESTAMPTZ  NULL,
            created_by UUID         NULL,
            updated_by UUID         NULL,
            created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT fk_cust_created FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
            CONSTRAINT fk_cust_updated FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
        );
        """
    )

    # ===== 6. attachments (polymorphic) =====
    op.execute(
        """
        CREATE TABLE attachments (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_type  VARCHAR(32)  NOT NULL
                CHECK (owner_type IN (
                    'test_request', 'sample', 'sample_result',
                    'chemical', 'chem_lot',
                    'document', 'document_version',
                    'equipment', 'calibration',
                    'hr_profile', 'publication'
                )),
            owner_id    UUID         NOT NULL,
            file_key    VARCHAR(512) NOT NULL,
            file_name   VARCHAR(255) NOT NULL,
            mime        VARCHAR(127) NULL,
            size        BIGINT       NULL CHECK (size IS NULL OR size >= 0),
            uploaded_by UUID         NOT NULL,
            uploaded_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
            deleted_at  TIMESTAMPTZ  NULL,
            CONSTRAINT fk_att_uploaded_by FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE RESTRICT
        );
        """
    )

    # ===== 7. refresh_tokens =====
    op.execute(
        """
        CREATE TABLE refresh_tokens (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id      UUID         NOT NULL,
            token_hash   VARCHAR(255) NOT NULL,
            expires_at   TIMESTAMPTZ  NOT NULL,
            revoked_at   TIMESTAMPTZ  NULL,
            rotated_from UUID         NULL,
            user_agent   VARCHAR(255) NULL,
            ip           INET         NULL,
            created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT uq_rt_token_hash   UNIQUE (token_hash),
            CONSTRAINT fk_rt_user         FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT fk_rt_rotated_from FOREIGN KEY (rotated_from) REFERENCES refresh_tokens(id) ON DELETE SET NULL,
            CONSTRAINT ck_rt_expiry       CHECK (expires_at > created_at)
        );
        """
    )

    # ===== 8. notifications =====
    op.execute(
        """
        CREATE TABLE notifications (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id    UUID         NOT NULL,
            type       VARCHAR(48)  NOT NULL,
            title      VARCHAR(255) NOT NULL,
            body       TEXT         NULL,
            ref_type   VARCHAR(32)  NULL,
            ref_id     UUID         NULL,
            read_at    TIMESTAMPTZ  NULL,
            created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )

    # ===== 9. audit_logs (append-only) =====
    op.execute(
        """
        CREATE TABLE audit_logs (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id        UUID         NULL,
            action         VARCHAR(64)  NOT NULL,
            resource       VARCHAR(64)  NOT NULL,
            resource_id    UUID         NULL,
            correlation_id VARCHAR(64)  NULL,
            ip             INET         NULL,
            detail         JSONB        NULL,
            at             TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );
        """
    )

    # ===== 10. access_stats =====
    op.execute(
        """
        CREATE TABLE access_stats (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID         NULL,
            path        VARCHAR(512) NOT NULL,
            method      VARCHAR(8)   NULL,
            status_code SMALLINT     NULL,
            ip          INET         NULL,
            at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT fk_access_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );
        """
    )

    # ===== TRIGGER append-only audit_logs (D8) =====
    op.execute(
        """
        CREATE OR REPLACE FUNCTION trg_audit_logs_immutable()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only (ISO/IEC 17025 8.4): % not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER audit_logs_no_update
            BEFORE UPDATE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION trg_audit_logs_immutable();
        CREATE TRIGGER audit_logs_no_delete
            BEFORE DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION trg_audit_logs_immutable();
        """
    )

    # ===== INDEXES (§4 contract) =====
    op.execute(
        """
        CREATE INDEX idx_users_department    ON users(department_id) WHERE department_id IS NOT NULL;
        CREATE INDEX idx_users_role          ON users(role);
        CREATE INDEX idx_users_status        ON users(status);
        CREATE INDEX idx_users_fullname_trgm ON users USING gin (full_name gin_trgm_ops);

        CREATE INDEX idx_dept_parent ON departments(parent_id) WHERE parent_id IS NOT NULL;
        CREATE INDEX idx_dept_lead   ON departments(lead_user_id) WHERE lead_user_id IS NOT NULL;

        CREATE INDEX idx_rp_role ON roles_permissions(role);

        CREATE INDEX idx_cust_name_trgm ON customers USING gin (name gin_trgm_ops);

        CREATE INDEX idx_att_owner       ON attachments(owner_type, owner_id) WHERE deleted_at IS NULL;
        CREATE INDEX idx_att_uploaded_by ON attachments(uploaded_by);

        CREATE INDEX idx_rt_user           ON refresh_tokens(user_id);
        CREATE INDEX idx_rt_expires_active ON refresh_tokens(expires_at) WHERE revoked_at IS NULL;

        CREATE INDEX idx_notif_user_unread  ON notifications(user_id, created_at DESC) WHERE read_at IS NULL;
        CREATE INDEX idx_notif_user_created ON notifications(user_id, created_at DESC);
        CREATE INDEX idx_notif_ref          ON notifications(ref_type, ref_id, type) WHERE ref_id IS NOT NULL;

        CREATE INDEX idx_audit_correlation ON audit_logs(correlation_id) WHERE correlation_id IS NOT NULL;
        CREATE INDEX idx_audit_at          ON audit_logs(at DESC);
        CREATE INDEX idx_audit_resource    ON audit_logs(resource, resource_id, at DESC) WHERE resource_id IS NOT NULL;
        CREATE INDEX idx_audit_user_at     ON audit_logs(user_id, at DESC) WHERE user_id IS NOT NULL;

        CREATE INDEX idx_access_user_at ON access_stats(user_id, at DESC) WHERE user_id IS NOT NULL;
        CREATE INDEX idx_access_at      ON access_stats(at DESC);
        """
    )

    # ===== SEED =====
    _seed(conn)


def _seed(conn) -> None:
    from sqlalchemy import text

    # --- permissions (§5.1) ---
    conn.execute(
        text(
            """
            INSERT INTO permissions (resource, action, description) VALUES
                ('sample','create','Tạo phiếu nhận / nhận mẫu'),
                ('sample','read','Xem mẫu / kết quả công khai nội bộ'),
                ('sample','assign','Phân công / chuyển giao mẫu'),
                ('sample','result','Nhập kết quả phần được giao'),
                ('sample','approve','Duyệt kết quả / chốt hoàn thành mẫu'),
                ('chemical','create','CRUD hóa chất / lô'),
                ('chemical','read','Xem tồn / lịch sử hóa chất'),
                ('chemical','transact','Nhập / xuất / điều chỉnh hóa chất'),
                ('chemical','cost','Xem giá trị tiền hóa chất'),
                ('document','create','Tạo / sửa tài liệu'),
                ('document','read','Xem tài liệu'),
                ('document','approve','Duyệt / ban hành tài liệu'),
                ('hr','read','Xem hồ sơ nhân sự / hợp đồng'),
                ('hr','manage','Quản lý hồ sơ / lương / nâng lương'),
                ('research','manage','Quản lý thành tích NCKH'),
                ('equipment','manage','Quản lý thiết bị / hiệu chuẩn'),
                ('report','business','Báo cáo nghiệp vụ (mẫu / hóa chất)'),
                ('report','finance','Báo cáo tài chính'),
                ('user','manage','Quản lý user / role / phòng ban'),
                ('audit','read','Xem nhật ký kiểm toán');
            """
        )
    )

    # --- roles_permissions (§5.2) ---
    conn.execute(
        text(
            """
            INSERT INTO roles_permissions (role, resource, action, scope) VALUES
                ('admin','sample','create','all'), ('admin','sample','read','all'),
                ('admin','sample','assign','all'), ('admin','sample','result','all'),
                ('admin','sample','approve','all'),
                ('admin','chemical','create','all'), ('admin','chemical','read','all'),
                ('admin','chemical','transact','all'), ('admin','chemical','cost','all'),
                ('admin','document','create','all'), ('admin','document','read','all'),
                ('admin','document','approve','all'),
                ('admin','hr','read','all'), ('admin','hr','manage','all'),
                ('admin','research','manage','all'),
                ('admin','equipment','manage','all'),
                ('admin','report','business','all'), ('admin','report','finance','all'),
                ('admin','user','manage','all'), ('admin','audit','read','all'),

                ('leader','sample','read','all'), ('leader','sample','assign','all'),
                ('leader','sample','approve','all'),
                ('leader','chemical','read','all'), ('leader','chemical','transact','all'),
                ('leader','chemical','cost','all'),
                ('leader','document','create','all'), ('leader','document','read','all'),
                ('leader','document','approve','all'),
                ('leader','hr','read','all'), ('leader','hr','manage','all'),
                ('leader','research','manage','all'),
                ('leader','equipment','manage','all'),
                ('leader','report','business','all'), ('leader','report','finance','all'),
                ('leader','audit','read','all'),

                ('accountant','chemical','read','all'), ('accountant','chemical','cost','all'),
                ('accountant','document','read','all'),
                ('accountant','hr','read','all'),
                ('accountant','hr','manage','all'),
                ('accountant','report','business','all'),
                ('accountant','report','finance','all'),

                ('staff','sample','create','department'),
                ('staff','sample','read','all'),
                ('staff','sample','assign','department'),
                ('staff','sample','result','own'),
                ('staff','sample','approve','department'),
                ('staff','chemical','read','all'),
                ('staff','chemical','transact','department'),
                ('staff','document','create','department'),
                ('staff','document','read','all'),
                ('staff','hr','read','own'),
                ('staff','research','manage','own'),
                ('staff','equipment','manage','department'),
                ('staff','report','business','department');
            """
        )
    )

    # --- departments mẫu (§5.3) ---
    conn.execute(
        text(
            """
            INSERT INTO departments (id, name, code, status) VALUES
                ('00000000-0000-0000-0000-0000000000d1', 'Ban Giám đốc',          'BGD',      'active'),
                ('00000000-0000-0000-0000-0000000000d2', 'Phòng Thí nghiệm Hóa',  'LAB-HOA',  'active'),
                ('00000000-0000-0000-0000-0000000000d3', 'Phòng Thí nghiệm Sinh', 'LAB-SINH', 'active'),
                ('00000000-0000-0000-0000-0000000000d4', 'Phòng Kế toán',         'KT',       'active');
            """
        )
    )

    # --- admin mặc định (bcrypt hash sinh runtime; password_changed_at NULL → ép đổi) ---
    admin_hash = hash_password(settings.seed_admin_password)
    conn.execute(
        text(
            """
            INSERT INTO users (id, email, password_hash, full_name, department_id, role, status, password_changed_at)
            VALUES (
                '00000000-0000-0000-0000-0000000000a1',
                :email, :pwd, 'Quản trị hệ thống',
                '00000000-0000-0000-0000-0000000000d1',
                'admin', 'active', NULL
            );
            """
        ),
        {"email": settings.seed_admin_email.lower(), "pwd": admin_hash},
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS trg_audit_logs_immutable();")
    op.execute("DROP TABLE IF EXISTS access_stats CASCADE;")
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE;")
    op.execute("DROP TABLE IF EXISTS notifications CASCADE;")
    op.execute("DROP TABLE IF EXISTS refresh_tokens CASCADE;")
    op.execute("DROP TABLE IF EXISTS attachments CASCADE;")
    op.execute("DROP TABLE IF EXISTS customers CASCADE;")
    op.execute("DROP TABLE IF EXISTS roles_permissions CASCADE;")
    op.execute("DROP TABLE IF EXISTS permissions CASCADE;")
    op.execute("ALTER TABLE departments DROP CONSTRAINT IF EXISTS fk_dept_lead;")
    op.execute("ALTER TABLE departments DROP CONSTRAINT IF EXISTS fk_dept_created;")
    op.execute("ALTER TABLE departments DROP CONSTRAINT IF EXISTS fk_dept_updated;")
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
    op.execute("DROP TABLE IF EXISTS departments CASCADE;")
    # KHÔNG drop extension (dùng chung toàn hệ thống).
