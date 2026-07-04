"""m1_sample_lifecycle — Quản lý Mẫu & Yêu cầu thử nghiệm (Sample Lifecycle).

Tạo 6 bảng theo Contract M1 Schema (06-contract-m1-schema.md §2):
test_requests → samples → sample_assignments → sample_results →
sample_handovers → overdue_reasons → indexes.

DDL viết raw SQL để khớp CHÍNH XÁC contract (CHECK, partial unique, FK RESTRICT, index).
Bảng IMMUTABLE (sample_handovers, overdue_reasons): không thêm trigger riêng — enforce
ở app-layer (không expose route sửa/xóa) đồng bộ phong cách M7.

Revision ID: 1718870400002
Revises: 1718870400001 (M7 platform)
Create Date: 2026-06-20

Thứ tự migration tổng thể: M7 → M1 → (M2 sau, FK ref_sample_id → samples.id).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400002"
down_revision: Union[str, None] = "1718870400001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgcrypto đã bật ở M7; CREATE EXTENSION IF NOT EXISTS để an toàn nếu chạy độc lập.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # ===== 1. test_requests =====
    op.execute(
        """
        CREATE TABLE test_requests (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            request_code  VARCHAR(32)  NOT NULL,
            customer_id   UUID         NULL,
            sender_name   VARCHAR(255) NULL,
            department_id UUID         NOT NULL,
            received_by   UUID         NOT NULL,
            received_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
            note          TEXT         NULL,
            deleted_at    TIMESTAMPTZ  NULL,
            created_by    UUID         NOT NULL,
            updated_by    UUID         NULL,
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT uq_req_code        UNIQUE (request_code),
            CONSTRAINT fk_req_customer    FOREIGN KEY (customer_id)   REFERENCES customers(id)   ON DELETE RESTRICT,
            CONSTRAINT fk_req_dept        FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
            CONSTRAINT fk_req_received_by FOREIGN KEY (received_by)   REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_req_created     FOREIGN KEY (created_by)    REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_req_updated     FOREIGN KEY (updated_by)    REFERENCES users(id)       ON DELETE RESTRICT
        );
        """
    )

    # ===== 2. samples =====
    op.execute(
        """
        CREATE TABLE samples (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sample_code          VARCHAR(32)  NOT NULL,
            request_id           UUID         NOT NULL,
            department_id        UUID         NOT NULL,
            received_by          UUID         NOT NULL,
            current_custodian_id UUID         NOT NULL,
            description          TEXT         NULL,
            received_at          TIMESTAMPTZ  NOT NULL,
            deadline_at          TIMESTAMPTZ  NOT NULL,
            completed_at         TIMESTAMPTZ  NULL,
            status               VARCHAR(10)  NOT NULL DEFAULT 'received'
                CHECK (status IN ('received','assigned','testing','done','overdue','returned')),
            condition_status     VARCHAR(16)  NULL
                CHECK (condition_status IS NULL OR condition_status IN ('acceptable','not_acceptable')),
            condition_note       TEXT         NULL,
            deleted_at           TIMESTAMPTZ  NULL,
            created_by           UUID         NOT NULL,
            updated_by           UUID         NULL,
            created_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT uq_sample_code     UNIQUE (sample_code),
            CONSTRAINT fk_smp_request     FOREIGN KEY (request_id)           REFERENCES test_requests(id) ON DELETE RESTRICT,
            CONSTRAINT fk_smp_dept        FOREIGN KEY (department_id)        REFERENCES departments(id)   ON DELETE RESTRICT,
            CONSTRAINT fk_smp_received_by FOREIGN KEY (received_by)          REFERENCES users(id)         ON DELETE RESTRICT,
            CONSTRAINT fk_smp_custodian   FOREIGN KEY (current_custodian_id) REFERENCES users(id)         ON DELETE RESTRICT,
            CONSTRAINT fk_smp_created     FOREIGN KEY (created_by)           REFERENCES users(id)         ON DELETE RESTRICT,
            CONSTRAINT fk_smp_updated     FOREIGN KEY (updated_by)           REFERENCES users(id)         ON DELETE RESTRICT,
            CONSTRAINT ck_smp_deadline    CHECK (deadline_at > received_at),
            CONSTRAINT ck_smp_condition   CHECK (
                condition_status IS DISTINCT FROM 'not_acceptable'
                OR (condition_note IS NOT NULL AND length(btrim(condition_note)) > 0)
            )
        );
        """
    )

    # ===== 3. sample_assignments =====
    op.execute(
        """
        CREATE TABLE sample_assignments (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sample_id   UUID         NOT NULL,
            assigned_to UUID         NOT NULL,
            assigned_by UUID         NOT NULL,
            part_name   VARCHAR(255) NOT NULL,
            status      VARCHAR(16)  NOT NULL DEFAULT 'assigned'
                CHECK (status IN ('assigned','in_progress','result_entered','approved')),
            assigned_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
            created_by  UUID         NOT NULL,
            updated_by  UUID         NULL,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT fk_asg_sample      FOREIGN KEY (sample_id)   REFERENCES samples(id) ON DELETE RESTRICT,
            CONSTRAINT fk_asg_assigned_to FOREIGN KEY (assigned_to) REFERENCES users(id)   ON DELETE RESTRICT,
            CONSTRAINT fk_asg_assigned_by FOREIGN KEY (assigned_by) REFERENCES users(id)   ON DELETE RESTRICT,
            CONSTRAINT fk_asg_created     FOREIGN KEY (created_by)  REFERENCES users(id)   ON DELETE RESTRICT,
            CONSTRAINT fk_asg_updated     FOREIGN KEY (updated_by)  REFERENCES users(id)   ON DELETE RESTRICT
        );
        """
    )

    # ===== 4. sample_results (versioning immutable) =====
    op.execute(
        """
        CREATE TABLE sample_results (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            assignment_id   UUID         NOT NULL,
            version         INT          NOT NULL DEFAULT 1 CHECK (version >= 1),
            result_data     JSONB        NOT NULL,
            note            TEXT         NULL,
            entered_by      UUID         NOT NULL,
            entered_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            approved_by     UUID         NULL,
            approved_at     TIMESTAMPTZ  NULL,
            is_current      BOOLEAN      NOT NULL DEFAULT true,
            revision_reason TEXT         NULL,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT fk_res_assignment  FOREIGN KEY (assignment_id) REFERENCES sample_assignments(id) ON DELETE RESTRICT,
            CONSTRAINT fk_res_entered_by  FOREIGN KEY (entered_by)    REFERENCES users(id)              ON DELETE RESTRICT,
            CONSTRAINT fk_res_approved_by FOREIGN KEY (approved_by)   REFERENCES users(id)              ON DELETE RESTRICT,
            CONSTRAINT uq_res_assignment_version UNIQUE (assignment_id, version),
            CONSTRAINT ck_res_approval_pair CHECK (
                (approved_by IS NULL AND approved_at IS NULL)
                OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
            ),
            CONSTRAINT ck_res_revision_reason CHECK (
                version = 1
                OR (revision_reason IS NOT NULL AND length(btrim(revision_reason)) > 0)
            )
        );
        CREATE UNIQUE INDEX uq_res_assignment_current
            ON sample_results(assignment_id) WHERE is_current;
        """
    )

    # ===== 5. sample_handovers (immutable) =====
    op.execute(
        """
        CREATE TABLE sample_handovers (
            id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sample_id UUID        NOT NULL,
            from_user UUID        NOT NULL,
            to_user   UUID        NOT NULL,
            reason    TEXT        NULL,
            at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_ho_sample    FOREIGN KEY (sample_id) REFERENCES samples(id) ON DELETE RESTRICT,
            CONSTRAINT fk_ho_from_user FOREIGN KEY (from_user) REFERENCES users(id)   ON DELETE RESTRICT,
            CONSTRAINT fk_ho_to_user   FOREIGN KEY (to_user)   REFERENCES users(id)   ON DELETE RESTRICT,
            CONSTRAINT ck_ho_diff_user CHECK (from_user <> to_user)
        );
        """
    )

    # ===== 6. overdue_reasons (immutable) =====
    op.execute(
        """
        CREATE TABLE overdue_reasons (
            id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sample_id UUID        NOT NULL,
            reason    TEXT        NOT NULL CHECK (length(btrim(reason)) > 0),
            by_user   UUID        NOT NULL,
            at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_ovr_sample  FOREIGN KEY (sample_id) REFERENCES samples(id) ON DELETE RESTRICT,
            CONSTRAINT fk_ovr_by_user FOREIGN KEY (by_user)   REFERENCES users(id)   ON DELETE RESTRICT
        );
        """
    )

    # ===== INDEXES (§4 contract) =====
    op.execute(
        """
        CREATE INDEX idx_req_department  ON test_requests(department_id);
        CREATE INDEX idx_req_customer    ON test_requests(customer_id) WHERE customer_id IS NOT NULL;
        CREATE INDEX idx_req_received_at  ON test_requests(received_at DESC);

        CREATE INDEX idx_smp_request       ON samples(request_id);
        CREATE INDEX idx_smp_dept_status   ON samples(department_id, status);
        CREATE INDEX idx_smp_deadline_open ON samples(deadline_at)
            WHERE status NOT IN ('done','returned') AND deleted_at IS NULL;
        CREATE INDEX idx_smp_completed_at  ON samples(completed_at) WHERE completed_at IS NOT NULL;
        CREATE INDEX idx_smp_custodian     ON samples(current_custodian_id);
        CREATE INDEX idx_smp_received_by   ON samples(received_by);

        CREATE INDEX idx_asg_sample          ON sample_assignments(sample_id);
        CREATE INDEX idx_asg_sample_status   ON sample_assignments(sample_id, status);
        CREATE INDEX idx_asg_assignee_status ON sample_assignments(assigned_to, status);

        CREATE INDEX idx_res_assignment ON sample_results(assignment_id);
        CREATE INDEX idx_res_approved   ON sample_results(assignment_id) WHERE approved_by IS NOT NULL;

        CREATE INDEX idx_ho_sample_at ON sample_handovers(sample_id, at DESC);

        CREATE INDEX idx_ovr_sample ON overdue_reasons(sample_id);
        """
    )


def downgrade() -> None:
    # Drop ngược thứ tự FK. LƯU Ý: nếu M2 đã tạo chemical_transactions FK ref_sample_id,
    # phải rollback M2 trước (DROP chemical_transactions).
    op.execute("DROP TABLE IF EXISTS overdue_reasons    CASCADE;")
    op.execute("DROP TABLE IF EXISTS sample_handovers   CASCADE;")
    op.execute("DROP TABLE IF EXISTS sample_results     CASCADE;")
    op.execute("DROP TABLE IF EXISTS sample_assignments CASCADE;")
    op.execute("DROP TABLE IF EXISTS samples            CASCADE;")
    op.execute("DROP TABLE IF EXISTS test_requests      CASCADE;")
    # KHÔNG drop extension pgcrypto / users / departments / customers (M7 sở hữu).
