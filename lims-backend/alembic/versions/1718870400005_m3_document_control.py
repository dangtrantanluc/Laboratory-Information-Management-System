"""m3_document_control — Quản lý Tài liệu (Document Control, §8.3/§8.4).

Tạo 4 bảng theo Contract M3 Schema (14-contract-m3-schema.md §2):
document_types (danh mục natural-key code) → documents (current_version_id NULL,
chưa FK) → document_versions (state machine) → ALTER documents ADD fk_doc_current
(phá vòng FK — D3) → uq_doc_one_approved (partial unique ≤1 approved/tài liệu — D7)
→ document_access_log (R15 high-volume) → indexes → seed document_types (6 loại).

DDL raw SQL khớp CHÍNH XÁC contract (CHECK enum thay native ENUM, UNIQUE
(document_id, version_no), cặp submit/review/approve nhất quán, partial unique
1-approved). State machine / tách soạn–duyệt / immutable enforce app-layer (như
M1/M4 — không trigger). Bỏ cột created_at_audit (ghi chú §2/§8.5 contract).

Quyền document:create/read/approve đã seed đủ ở M7 §5.2 → M3 KHÔNG thêm
roles_permissions. attachments.owner_type ('document','document_version') đã có
whitelist ở M7 → M3 KHÔNG ALTER attachments. M3 chỉ seed document_types.

Revision ID: 1718870400005
Revises: 1718870400004 (M4 HR)
Create Date: 2026-06-20

Thứ tự migration tổng thể: M7 → M1 → M2 → M4 → M3 (file này).
Phụ thuộc users/departments/attachments/audit_logs/notifications (M7).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400005"
down_revision: Union[str, None] = "1718870400004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")  # gen_random_uuid()

    # ===== TABLE 1: document_types (danh mục natural-key code PK, D4) =====
    op.execute(
        """
        CREATE TABLE document_types (
            code        VARCHAR(32)  PRIMARY KEY,
            label       VARCHAR(128) NOT NULL,
            prefix      VARCHAR(16)  NOT NULL,
            sort_order  SMALLINT     NOT NULL DEFAULT 0,
            is_active   BOOLEAN      NOT NULL DEFAULT true,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
        );
        """
    )

    # ===== TABLE 2: documents (current_version_id NULL, CHƯA FK — phá vòng D3) =====
    op.execute(
        """
        CREATE TABLE documents (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code                VARCHAR(64)  NOT NULL,
            title               VARCHAR(512) NOT NULL,
            type                VARCHAR(32)  NOT NULL,
            department_id       UUID         NOT NULL,
            security_level      VARCHAR(12)  NOT NULL DEFAULT 'internal'
                CHECK (security_level IN ('internal', 'restricted')),
            status              VARCHAR(10)  NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'archived', 'deleted')),
            current_version_id  UUID         NULL,
            deleted_at          TIMESTAMPTZ  NULL,
            created_by          UUID         NOT NULL,
            updated_by          UUID         NULL,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT uq_doc_code    UNIQUE (code),
            CONSTRAINT fk_doc_type    FOREIGN KEY (type)          REFERENCES document_types(code) ON DELETE RESTRICT,
            CONSTRAINT fk_doc_dept    FOREIGN KEY (department_id) REFERENCES departments(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_doc_created FOREIGN KEY (created_by)     REFERENCES users(id)             ON DELETE RESTRICT,
            CONSTRAINT fk_doc_updated FOREIGN KEY (updated_by)     REFERENCES users(id)             ON DELETE RESTRICT
        );
        """
    )

    # ===== TABLE 3: document_versions (state machine §8.3, D6/D9) =====
    op.execute(
        """
        CREATE TABLE document_versions (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id     UUID         NOT NULL,
            version_no      INT          NOT NULL CHECK (version_no >= 1),
            change_note     TEXT         NULL,
            status          VARCHAR(10)  NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'review', 'approved', 'obsolete')),
            created_by      UUID         NOT NULL,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            submitted_by    UUID         NULL,
            submitted_at    TIMESTAMPTZ  NULL,
            reviewed_by     UUID         NULL,
            reviewed_at     TIMESTAMPTZ  NULL,
            approved_by     UUID         NULL,
            approved_at     TIMESTAMPTZ  NULL,
            reject_reason   TEXT         NULL,
            deleted_at      TIMESTAMPTZ  NULL,

            CONSTRAINT fk_dv_document  FOREIGN KEY (document_id)  REFERENCES documents(id) ON DELETE RESTRICT,
            CONSTRAINT fk_dv_created   FOREIGN KEY (created_by)    REFERENCES users(id)     ON DELETE RESTRICT,
            CONSTRAINT fk_dv_submitted FOREIGN KEY (submitted_by)  REFERENCES users(id)    ON DELETE RESTRICT,
            CONSTRAINT fk_dv_reviewed  FOREIGN KEY (reviewed_by)   REFERENCES users(id)    ON DELETE RESTRICT,
            CONSTRAINT fk_dv_approved  FOREIGN KEY (approved_by)   REFERENCES users(id)    ON DELETE RESTRICT,
            CONSTRAINT uq_dv_doc_version UNIQUE (document_id, version_no),
            CONSTRAINT ck_dv_approval_pair CHECK (
                (approved_by IS NULL AND approved_at IS NULL)
                OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
            ),
            CONSTRAINT ck_dv_review_pair CHECK (
                (reviewed_by IS NULL AND reviewed_at IS NULL)
                OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)
            ),
            CONSTRAINT ck_dv_submit_pair CHECK (
                (submitted_by IS NULL AND submitted_at IS NULL)
                OR (submitted_by IS NOT NULL AND submitted_at IS NOT NULL)
            ),
            CONSTRAINT ck_dv_approved_has_approver CHECK (
                status <> 'approved' OR approved_by IS NOT NULL
            )
        );
        """
    )

    # ===== ALTER: gắn FK current_version_id sau khi document_versions tồn tại (D3) =====
    op.execute(
        """
        ALTER TABLE documents
            ADD CONSTRAINT fk_doc_current FOREIGN KEY (current_version_id)
            REFERENCES document_versions(id) ON DELETE SET NULL;
        """
    )

    # ===== PARTIAL UNIQUE: ≤1 version approved/tài liệu (BR-DOC-008, D7) — DB-LEVEL =====
    op.execute(
        "CREATE UNIQUE INDEX uq_doc_one_approved "
        "ON document_versions(document_id) WHERE status = 'approved';"
    )

    # ===== TABLE 4: document_access_log (R15 high-volume, KHÔNG immutable, D11) =====
    op.execute(
        """
        CREATE TABLE document_access_log (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID         NOT NULL,
            version_id  UUID         NULL,
            user_id     UUID         NOT NULL,
            action      VARCHAR(10)  NOT NULL
                CHECK (action IN ('view', 'download', 'edit')),
            at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_dal_document FOREIGN KEY (document_id) REFERENCES documents(id)         ON DELETE RESTRICT,
            CONSTRAINT fk_dal_version  FOREIGN KEY (version_id)  REFERENCES document_versions(id) ON DELETE SET NULL,
            CONSTRAINT fk_dal_user     FOREIGN KEY (user_id)     REFERENCES users(id)             ON DELETE RESTRICT
        );
        """
    )

    # ===== INDEXES (§4 contract) =====
    op.execute("CREATE INDEX idx_doc_dept_type   ON documents(department_id, type);")
    op.execute("CREATE INDEX idx_doc_status      ON documents(status);")
    op.execute("CREATE INDEX idx_doc_security    ON documents(security_level);")
    op.execute(
        "CREATE INDEX idx_doc_current_ver ON documents(current_version_id) "
        "WHERE current_version_id IS NOT NULL;"
    )
    op.execute(
        "CREATE INDEX idx_doc_title_trgm ON documents USING gin (title gin_trgm_ops);"
    )
    op.execute(
        "CREATE INDEX idx_doc_code_trgm  ON documents USING gin (code gin_trgm_ops);"
    )

    op.execute(
        "CREATE INDEX idx_dv_doc_status ON document_versions(document_id, status);"
    )
    op.execute(
        "CREATE INDEX idx_dv_review ON document_versions(document_id) WHERE status = 'review';"
    )
    op.execute("CREATE INDEX idx_dv_created_by ON document_versions(created_by);")

    op.execute(
        "CREATE INDEX idx_dal_doc_action_at ON document_access_log(document_id, action, at);"
    )
    op.execute("CREATE INDEX idx_dal_at      ON document_access_log(at);")
    op.execute("CREATE INDEX idx_dal_user_at ON document_access_log(user_id, at);")

    # ===== SEED document_types (6 loại, D4 / §5) — idempotent =====
    op.execute(
        """
        INSERT INTO document_types (code, label, prefix, sort_order) VALUES
            ('sop',      'Quy trình thao tác chuẩn (SOP)',  'SOP', 1),
            ('process',  'Quy trình / Thủ tục',             'QT',  2),
            ('form',     'Biểu mẫu',                        'BM',  3),
            ('guide',    'Hướng dẫn công việc',             'HD',  4),
            ('standard', 'Tiêu chuẩn / Quy chuẩn',          'TC',  5),
            ('other',    'Tài liệu khác',                   'TL',  6)
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:
    # Drop ngược thứ tự FK (§9 contract). Phá vòng FK trước (fk_doc_current).
    # KHÔNG drop extension dùng chung; KHÔNG đụng bảng M7.
    op.execute("ALTER TABLE documents DROP CONSTRAINT IF EXISTS fk_doc_current;")
    op.execute("DROP TABLE IF EXISTS document_access_log CASCADE;")
    op.execute("DROP TABLE IF EXISTS document_versions   CASCADE;")
    op.execute("DROP TABLE IF EXISTS documents           CASCADE;")
    op.execute("DROP TABLE IF EXISTS document_types      CASCADE;")
