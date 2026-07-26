"""M23 — Mở rộng M4 theo file "Tổng hợp hoạt động 2024-2025" (menu NCKH/Bài báo/Giảng
dạy/Công tác khác/Phục vụ cộng đồng).

- research_projects: +kinh phí/chuyển giao/chủ nhiệm ngoài HT/academic_year; lead nullable.
- project_members: cho phép thành viên NGOÀI HT (id PK riêng + external_name, XOR user_id).
- publications: +phạm vi/chỉ mục SCIE/SSCI/Scopus/ACI + type 'conference' + field sáng chế.
- publication_authors: +author_role.
- teaching_courses: +số tiết HKI/HKII × LT/TH + note + academic_year.
- Bảng mới: research_contracts, staff_activities, training_certificates.
- attachments: mở owner_type cho 5 loại mới.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400022"
down_revision: Union[str, None] = "1718870400021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- research_projects ----------
    op.execute(
        """
        ALTER TABLE research_projects
            ALTER COLUMN lead_user_id DROP NOT NULL,
            ADD COLUMN IF NOT EXISTS lead_external_name VARCHAR(255),
            ADD COLUMN IF NOT EXISTS academic_year VARCHAR(16),
            ADD COLUMN IF NOT EXISTS budget_amount NUMERIC(14,2),
            ADD COLUMN IF NOT EXISTS budget_currency VARCHAR(8) DEFAULT 'VND',
            ADD COLUMN IF NOT EXISTS is_transferred BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS transfer_product TEXT;
        ALTER TABLE research_projects
            ADD CONSTRAINT ck_rp_lead_present
            CHECK (lead_user_id IS NOT NULL OR lead_external_name IS NOT NULL);
        """
    )

    # ---------- project_members: đổi PK (project_id,user_id) -> id, cho external ----------
    op.execute(
        """
        ALTER TABLE project_members
            ADD COLUMN IF NOT EXISTS id UUID NOT NULL DEFAULT gen_random_uuid(),
            ADD COLUMN IF NOT EXISTS external_name VARCHAR(255);
        -- Bỏ PK cũ (project_id,user_id) TRƯỚC khi drop NOT NULL trên user_id
        ALTER TABLE project_members DROP CONSTRAINT IF EXISTS pk_project_members;
        ALTER TABLE project_members ALTER COLUMN user_id DROP NOT NULL;
        ALTER TABLE project_members ADD PRIMARY KEY (id);
        -- Giữ ràng buộc không trùng thành viên nội bộ trong 1 đề tài
        CREATE UNIQUE INDEX IF NOT EXISTS uq_pm_project_user
            ON project_members (project_id, user_id) WHERE user_id IS NOT NULL;
        ALTER TABLE project_members
            ADD CONSTRAINT ck_pm_member_xor CHECK (
                (user_id IS NOT NULL AND external_name IS NULL)
                OR (user_id IS NULL AND external_name IS NOT NULL)
            );
        """
    )

    # ---------- publications ----------
    op.execute(
        """
        ALTER TABLE publications
            ALTER COLUMN type TYPE VARCHAR(12),
            ADD COLUMN IF NOT EXISTS pub_scope VARCHAR(16),
            ADD COLUMN IF NOT EXISTS is_scie BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS is_ssci BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS is_scopus BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS is_aci BOOLEAN NOT NULL DEFAULT false,
            ADD COLUMN IF NOT EXISTS academic_year VARCHAR(16),
            ADD COLUMN IF NOT EXISTS application_no VARCHAR(64),
            ADD COLUMN IF NOT EXISTS application_date DATE,
            ADD COLUMN IF NOT EXISTS granted_date DATE,
            ADD COLUMN IF NOT EXISTS patent_holder VARCHAR(255);
        -- Bỏ CHECK type cũ (tên auto 'publications_type_check' từ m4, chỉ paper|patent)
        ALTER TABLE publications DROP CONSTRAINT IF EXISTS publications_type_check;
        ALTER TABLE publications DROP CONSTRAINT IF EXISTS ck_pub_type;
        ALTER TABLE publications
            ADD CONSTRAINT ck_pub_type CHECK (type IN ('paper', 'patent', 'conference'));
        ALTER TABLE publications
            ADD CONSTRAINT ck_pub_scope
            CHECK (pub_scope IS NULL OR pub_scope IN ('domestic', 'international'));
        ALTER TABLE publication_authors
            ADD COLUMN IF NOT EXISTS author_role VARCHAR(16);
        """
    )

    # ---------- teaching_courses ----------
    op.execute(
        """
        ALTER TABLE teaching_courses
            ADD COLUMN IF NOT EXISTS academic_year VARCHAR(16),
            ADD COLUMN IF NOT EXISTS hk1_theory_hours SMALLINT,
            ADD COLUMN IF NOT EXISTS hk1_practice_hours SMALLINT,
            ADD COLUMN IF NOT EXISTS hk2_theory_hours SMALLINT,
            ADD COLUMN IF NOT EXISTS hk2_practice_hours SMALLINT,
            ADD COLUMN IF NOT EXISTS note TEXT;
        """
    )

    # ---------- research_contracts (mới) ----------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS research_contracts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(512) NOT NULL,
            contract_type VARCHAR(64),
            value_amount NUMERIC(14,2),
            currency VARCHAR(8) DEFAULT 'VND',
            partner_org VARCHAR(255),
            start_date DATE,
            end_date DATE,
            academic_year VARCHAR(16),
            department_id UUID REFERENCES departments(id) ON DELETE RESTRICT,
            created_by UUID REFERENCES users(id) ON DELETE RESTRICT,
            updated_by UUID REFERENCES users(id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_rc_date_order
                CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
        );
        CREATE INDEX IF NOT EXISTS ix_research_contracts_department_id ON research_contracts(department_id);
        CREATE INDEX IF NOT EXISTS ix_research_contracts_academic_year ON research_contracts(academic_year);
        """
    )

    # ---------- staff_activities (mới) ----------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS staff_activities (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            kind VARCHAR(16) NOT NULL,
            content TEXT NOT NULL,
            performed_at DATE,
            academic_year VARCHAR(16),
            performer_user_id UUID REFERENCES users(id) ON DELETE RESTRICT,
            department_id UUID REFERENCES departments(id) ON DELETE RESTRICT,
            created_by UUID REFERENCES users(id) ON DELETE RESTRICT,
            updated_by UUID REFERENCES users(id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_sa_kind CHECK (kind IN ('dang','cong_doan','vilas','khac'))
        );
        CREATE INDEX IF NOT EXISTS ix_staff_activities_kind ON staff_activities(kind);
        CREATE INDEX IF NOT EXISTS ix_staff_activities_performer_user_id ON staff_activities(performer_user_id);
        """
    )

    # ---------- training_certificates (mới) ----------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS training_certificates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            issued_date DATE,
            certificate_no VARCHAR(64),
            recipient_name VARCHAR(255) NOT NULL,
            course_name VARCHAR(255),
            note TEXT,
            academic_year VARCHAR(16),
            host_user_id UUID REFERENCES users(id) ON DELETE RESTRICT,
            department_id UUID REFERENCES departments(id) ON DELETE RESTRICT,
            created_by UUID REFERENCES users(id) ON DELETE RESTRICT,
            updated_by UUID REFERENCES users(id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_training_certificates_department_id ON training_certificates(department_id);
        """
    )

    # ---------- attachments: mở owner_type mới ----------
    op.execute(
        """
        ALTER TABLE attachments DROP CONSTRAINT IF EXISTS ck_att_owner_type;
        ALTER TABLE attachments ADD CONSTRAINT ck_att_owner_type CHECK (
            owner_type IN ('test_request','sample','sample_result','chemical','chem_lot',
            'document','document_version','equipment','calibration','hr_profile','publication',
            'form_template','form_submission','sample_intake','sample_dispatch',
            'research_project','research_contract','teaching_course','staff_activity',
            'training_certificate')
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE attachments DROP CONSTRAINT IF EXISTS ck_att_owner_type;
        ALTER TABLE attachments ADD CONSTRAINT ck_att_owner_type CHECK (
            owner_type IN ('test_request','sample','sample_result','chemical','chem_lot',
            'document','document_version','equipment','calibration','hr_profile','publication',
            'form_template','form_submission','sample_intake','sample_dispatch')
        );
        DROP TABLE IF EXISTS training_certificates;
        DROP TABLE IF EXISTS staff_activities;
        DROP TABLE IF EXISTS research_contracts;

        ALTER TABLE teaching_courses
            DROP COLUMN IF EXISTS academic_year,
            DROP COLUMN IF EXISTS hk1_theory_hours,
            DROP COLUMN IF EXISTS hk1_practice_hours,
            DROP COLUMN IF EXISTS hk2_theory_hours,
            DROP COLUMN IF EXISTS hk2_practice_hours,
            DROP COLUMN IF EXISTS note;

        ALTER TABLE publication_authors DROP COLUMN IF EXISTS author_role;
        ALTER TABLE publications DROP CONSTRAINT IF EXISTS ck_pub_scope;
        ALTER TABLE publications DROP CONSTRAINT IF EXISTS ck_pub_type;
        ALTER TABLE publications
            DROP COLUMN IF EXISTS pub_scope,
            DROP COLUMN IF EXISTS is_scie,
            DROP COLUMN IF EXISTS is_ssci,
            DROP COLUMN IF EXISTS is_scopus,
            DROP COLUMN IF EXISTS is_aci,
            DROP COLUMN IF EXISTS academic_year,
            DROP COLUMN IF EXISTS application_no,
            DROP COLUMN IF EXISTS application_date,
            DROP COLUMN IF EXISTS granted_date,
            DROP COLUMN IF EXISTS patent_holder;
        ALTER TABLE publications DROP CONSTRAINT IF EXISTS ck_pub_type;
        ALTER TABLE publications
            ADD CONSTRAINT publications_type_check CHECK (type IN ('paper', 'patent'));

        ALTER TABLE project_members DROP CONSTRAINT IF EXISTS ck_pm_member_xor;
        DROP INDEX IF EXISTS uq_pm_project_user;
        ALTER TABLE project_members DROP CONSTRAINT IF EXISTS project_members_pkey;
        DELETE FROM project_members WHERE user_id IS NULL;
        ALTER TABLE project_members ALTER COLUMN user_id SET NOT NULL;
        ALTER TABLE project_members
            DROP COLUMN IF EXISTS id,
            DROP COLUMN IF EXISTS external_name;
        ALTER TABLE project_members ADD CONSTRAINT pk_project_members PRIMARY KEY (project_id, user_id);

        ALTER TABLE research_projects DROP CONSTRAINT IF EXISTS ck_rp_lead_present;
        ALTER TABLE research_projects
            DROP COLUMN IF EXISTS lead_external_name,
            DROP COLUMN IF EXISTS academic_year,
            DROP COLUMN IF EXISTS budget_amount,
            DROP COLUMN IF EXISTS budget_currency,
            DROP COLUMN IF EXISTS is_transferred,
            DROP COLUMN IF EXISTS transfer_product;
        """
    )
