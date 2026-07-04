"""m4_hr — Nhân sự & Thành tích NCKH (HR & Research Achievement).

Tạo 16 bảng theo Contract M4 Schema (11-contract-m4-schema.md §2):
4 danh mục (contract_types, research_project_levels, publication_categories,
mentorship_types) → hr_profiles → salary_history → competences →
hr_notification_dedup → research_projects → project_members → publications →
publication_authors → student_mentorships → lab_registrations →
teaching_courses → community_services → indexes → seed danh mục.

DDL raw SQL khớp CHÍNH XÁC contract (CHECK enum, XOR tác giả, PK kép n-n, partial
unique patent_no, FK RESTRICT, hr_profiles user_id PK=FK 1-1, ck_lr_approval).
Bảng APPEND-ONLY (salary_history) + immutable: enforce app-layer (không trigger),
đồng bộ phong cách M7/M1/M2.

Quyền hr:read/hr:manage/research:manage đã seed đủ ở M7 §5.2 → M4 KHÔNG thêm
roles_permissions. Field-level RBAC lương/PII + scope research enforce app-layer.

Revision ID: 1718870400004
Revises: 1718870400003 (M2 chemical inventory)
Create Date: 2026-06-20

Thứ tự migration tổng thể: M7 → M1 → M2 → M4. Phụ thuộc users/departments/attachments (M7).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400004"
down_revision: Union[str, None] = "1718870400003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # ===== DANH MỤC 1-4 (D5 — natural-key code PK, cấu hình được) =====
    op.execute(
        """
        CREATE TABLE contract_types (
            code        VARCHAR(32)  PRIMARY KEY,
            label       VARCHAR(128) NOT NULL,
            sort_order  SMALLINT     NOT NULL DEFAULT 0,
            is_active   BOOLEAN      NOT NULL DEFAULT true,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE research_project_levels (
            code        VARCHAR(32)  PRIMARY KEY,
            label       VARCHAR(128) NOT NULL,
            sort_order  SMALLINT     NOT NULL DEFAULT 0,
            is_active   BOOLEAN      NOT NULL DEFAULT true,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE publication_categories (
            code        VARCHAR(32)  PRIMARY KEY,
            label       VARCHAR(128) NOT NULL,
            sort_order  SMALLINT     NOT NULL DEFAULT 0,
            is_active   BOOLEAN      NOT NULL DEFAULT true,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE mentorship_types (
            code        VARCHAR(32)  PRIMARY KEY,
            label       VARCHAR(128) NOT NULL,
            sort_order  SMALLINT     NOT NULL DEFAULT 0,
            is_active   BOOLEAN      NOT NULL DEFAULT true,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
        );
        """
    )

    # ===== TABLE 1: hr_profiles (1-1 user_id PK=FK, D3) =====
    op.execute(
        """
        CREATE TABLE hr_profiles (
            user_id                 UUID         PRIMARY KEY,
            job_title               VARCHAR(255) NOT NULL,
            hired_date              DATE         NULL,
            phone                   VARCHAR(32)  NULL,
            position                VARCHAR(255) NULL,

            contract_type           VARCHAR(32)  NULL,
            contract_signed_date    DATE         NULL,
            contract_end_date       DATE         NULL,

            salary_grade            VARCHAR(32)  NULL,
            salary_coefficient      NUMERIC(6,2) NULL
                CHECK (salary_coefficient IS NULL OR salary_coefficient > 0),
            base_salary_amount      NUMERIC(14,2) NULL
                CHECK (base_salary_amount IS NULL OR base_salary_amount >= 0),
            currency                VARCHAR(3)   NOT NULL DEFAULT 'VND',

            salary_cycle_years      INT          NOT NULL DEFAULT 3 CHECK (salary_cycle_years >= 1),
            last_salary_raise_date  DATE         NULL,
            next_salary_raise_date  DATE         NULL,

            created_by              UUID         NULL,
            updated_by              UUID         NULL,
            created_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_hrp_user      FOREIGN KEY (user_id)       REFERENCES users(id)            ON DELETE RESTRICT,
            CONSTRAINT fk_hrp_contract  FOREIGN KEY (contract_type) REFERENCES contract_types(code) ON DELETE RESTRICT,
            CONSTRAINT fk_hrp_created   FOREIGN KEY (created_by)     REFERENCES users(id)            ON DELETE RESTRICT,
            CONSTRAINT fk_hrp_updated   FOREIGN KEY (updated_by)     REFERENCES users(id)            ON DELETE RESTRICT,
            CONSTRAINT ck_hrp_contract_date_order CHECK (
                contract_end_date IS NULL OR contract_signed_date IS NULL
                OR contract_end_date > contract_signed_date
            )
        );
        """
    )

    # ===== TABLE 2: salary_history (APPEND-ONLY, D8) =====
    op.execute(
        """
        CREATE TABLE salary_history (
            id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id             UUID         NOT NULL,
            old_grade           VARCHAR(32)  NULL,
            old_coefficient     NUMERIC(6,2) NULL,
            old_base_amount     NUMERIC(14,2) NULL,
            new_grade           VARCHAR(32)  NULL,
            new_coefficient     NUMERIC(6,2) NULL
                CHECK (new_coefficient IS NULL OR new_coefficient > 0),
            new_base_amount     NUMERIC(14,2) NULL
                CHECK (new_base_amount IS NULL OR new_base_amount >= 0),
            currency            VARCHAR(3)   NOT NULL DEFAULT 'VND',
            raise_date          DATE         NOT NULL,
            note                TEXT         NULL,
            by_user             UUID         NOT NULL,
            correlation_id      VARCHAR(64)  NULL,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_sh_profile FOREIGN KEY (user_id) REFERENCES hr_profiles(user_id) ON DELETE RESTRICT,
            CONSTRAINT fk_sh_byuser  FOREIGN KEY (by_user) REFERENCES users(id)            ON DELETE RESTRICT
        );
        """
    )

    # ===== TABLE 3: competences (năng lực §6.2) =====
    op.execute(
        """
        CREATE TABLE competences (
            id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID         NOT NULL,
            kind            VARCHAR(16)  NOT NULL
                CHECK (kind IN ('degree', 'certificate', 'authorization')),
            title           VARCHAR(255) NOT NULL,
            issuer          VARCHAR(255) NULL,
            issued_date     DATE         NULL,
            expiry_date     DATE         NULL,
            scope_detail    TEXT         NULL,
            authorized_by   UUID         NULL,
            created_by      UUID         NULL,
            updated_by      UUID         NULL,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_comp_profile     FOREIGN KEY (user_id)       REFERENCES hr_profiles(user_id) ON DELETE RESTRICT,
            CONSTRAINT fk_comp_authorized  FOREIGN KEY (authorized_by) REFERENCES users(id)            ON DELETE RESTRICT,
            CONSTRAINT fk_comp_created     FOREIGN KEY (created_by)     REFERENCES users(id)            ON DELETE RESTRICT,
            CONSTRAINT fk_comp_updated     FOREIGN KEY (updated_by)     REFERENCES users(id)            ON DELETE RESTRICT,
            CONSTRAINT ck_comp_date_order  CHECK (
                expiry_date IS NULL OR issued_date IS NULL OR expiry_date >= issued_date
            )
        );
        """
    )

    # ===== TABLE 4: hr_notification_dedup (CRON-3/4, D10) =====
    op.execute(
        """
        CREATE TABLE hr_notification_dedup (
            id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            profile_user_id UUID         NOT NULL,
            kind            VARCHAR(20)  NOT NULL
                CHECK (kind IN ('SALARY_RAISE_DUE', 'CONTRACT_EXPIRY')),
            milestone_days  SMALLINT     NOT NULL
                CHECK (milestone_days IN (3, 7, 15, 30)),
            fire_date       DATE         NOT NULL,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_hrdedup_profile FOREIGN KEY (profile_user_id)
                REFERENCES hr_profiles(user_id) ON DELETE CASCADE,
            CONSTRAINT uq_hrdedup UNIQUE (profile_user_id, kind, milestone_days, fire_date)
        );
        """
    )

    # ===== TABLE 5: research_projects =====
    op.execute(
        """
        CREATE TABLE research_projects (
            id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            code            VARCHAR(64)  NULL,
            title           VARCHAR(512) NOT NULL,
            level           VARCHAR(32)  NULL,
            lead_user_id    UUID         NOT NULL,
            department_id   UUID         NULL,
            start_date      DATE         NULL,
            end_date        DATE         NULL,
            status          VARCHAR(16)  NOT NULL DEFAULT 'ongoing'
                CHECK (status IN ('ongoing', 'completed', 'accepted', 'cancelled')),
            created_by      UUID         NULL,
            updated_by      UUID         NULL,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_rp_level    FOREIGN KEY (level)         REFERENCES research_project_levels(code) ON DELETE RESTRICT,
            CONSTRAINT fk_rp_lead     FOREIGN KEY (lead_user_id)  REFERENCES users(id)        ON DELETE RESTRICT,
            CONSTRAINT fk_rp_dept     FOREIGN KEY (department_id) REFERENCES departments(id)  ON DELETE RESTRICT,
            CONSTRAINT fk_rp_created  FOREIGN KEY (created_by)     REFERENCES users(id)        ON DELETE RESTRICT,
            CONSTRAINT fk_rp_updated  FOREIGN KEY (updated_by)     REFERENCES users(id)        ON DELETE RESTRICT,
            CONSTRAINT uq_rp_code     UNIQUE (code),
            CONSTRAINT ck_rp_date_order CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
        );
        """
    )

    # ===== TABLE 6: project_members (n-n) =====
    op.execute(
        """
        CREATE TABLE project_members (
            project_id      UUID         NOT NULL,
            user_id         UUID         NOT NULL,
            role_in_project VARCHAR(64)  NOT NULL DEFAULT 'member',
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT pk_project_members PRIMARY KEY (project_id, user_id),
            CONSTRAINT fk_pm_project FOREIGN KEY (project_id) REFERENCES research_projects(id) ON DELETE CASCADE,
            CONSTRAINT fk_pm_user    FOREIGN KEY (user_id)    REFERENCES users(id)             ON DELETE RESTRICT
        );
        """
    )

    # ===== TABLE 7: publications =====
    op.execute(
        """
        CREATE TABLE publications (
            id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            title               VARCHAR(512) NOT NULL,
            journal             VARCHAR(255) NULL,
            year                SMALLINT     NULL,
            doi                 VARCHAR(255) NULL,
            category            VARCHAR(32)  NULL,
            type                VARCHAR(8)   NOT NULL DEFAULT 'paper'
                CHECK (type IN ('paper', 'patent')),
            patent_no           VARCHAR(64)  NULL,
            issuing_authority   VARCHAR(255) NULL,
            department_id       UUID         NULL,
            created_by          UUID         NULL,
            updated_by          UUID         NULL,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_pub_category FOREIGN KEY (category)      REFERENCES publication_categories(code) ON DELETE RESTRICT,
            CONSTRAINT fk_pub_dept     FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
            CONSTRAINT fk_pub_created  FOREIGN KEY (created_by)     REFERENCES users(id)      ON DELETE RESTRICT,
            CONSTRAINT fk_pub_updated  FOREIGN KEY (updated_by)     REFERENCES users(id)      ON DELETE RESTRICT,
            CONSTRAINT ck_pub_patent_no CHECK (
                type <> 'patent' OR (patent_no IS NOT NULL AND length(btrim(patent_no)) > 0)
            )
        );
        """
    )

    # ===== TABLE 8: publication_authors (n-n + XOR) =====
    op.execute(
        """
        CREATE TABLE publication_authors (
            publication_id  UUID         NOT NULL,
            author_order    SMALLINT     NOT NULL CHECK (author_order >= 1),
            user_id         UUID         NULL,
            external_name   VARCHAR(255) NULL,
            is_corresponding BOOLEAN     NOT NULL DEFAULT false,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT pk_pub_authors PRIMARY KEY (publication_id, author_order),
            CONSTRAINT fk_pa_publication FOREIGN KEY (publication_id) REFERENCES publications(id) ON DELETE CASCADE,
            CONSTRAINT fk_pa_user        FOREIGN KEY (user_id)        REFERENCES users(id)        ON DELETE RESTRICT,
            CONSTRAINT ck_pa_author_xor CHECK (
                (user_id IS NOT NULL AND external_name IS NULL)
                OR (user_id IS NULL AND external_name IS NOT NULL)
            )
        );
        """
    )

    # ===== TABLE 9: student_mentorships =====
    op.execute(
        """
        CREATE TABLE student_mentorships (
            id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            mentor_id       UUID         NOT NULL,
            student_name    VARCHAR(255) NOT NULL,
            topic           VARCHAR(512) NULL,
            year            SMALLINT     NULL,
            type            VARCHAR(32)  NULL,
            department_id   UUID         NULL,
            created_by      UUID         NULL,
            updated_by      UUID         NULL,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_sm_mentor  FOREIGN KEY (mentor_id)     REFERENCES users(id)              ON DELETE RESTRICT,
            CONSTRAINT fk_sm_type    FOREIGN KEY (type)          REFERENCES mentorship_types(code) ON DELETE RESTRICT,
            CONSTRAINT fk_sm_dept    FOREIGN KEY (department_id) REFERENCES departments(id)        ON DELETE RESTRICT,
            CONSTRAINT fk_sm_created FOREIGN KEY (created_by)     REFERENCES users(id)              ON DELETE RESTRICT,
            CONSTRAINT fk_sm_updated FOREIGN KEY (updated_by)     REFERENCES users(id)              ON DELETE RESTRICT
        );
        """
    )

    # ===== TABLE 10: lab_registrations (có duyệt, D6) =====
    op.execute(
        """
        CREATE TABLE lab_registrations (
            id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            student_name    VARCHAR(255) NOT NULL,
            mentor_id       UUID         NOT NULL,
            registered_at   DATE         NOT NULL DEFAULT CURRENT_DATE,
            registered_from DATE         NULL,
            registered_to   DATE         NULL,
            purpose         TEXT         NULL,
            status          VARCHAR(12)  NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'approved', 'rejected')),
            approved_by     UUID         NULL,
            approved_at     TIMESTAMPTZ  NULL,
            department_id   UUID         NULL,
            created_by      UUID         NULL,
            updated_by      UUID         NULL,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_lr_mentor   FOREIGN KEY (mentor_id)     REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_lr_approved FOREIGN KEY (approved_by)   REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_lr_dept     FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
            CONSTRAINT fk_lr_created  FOREIGN KEY (created_by)     REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_lr_updated  FOREIGN KEY (updated_by)     REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT ck_lr_date_order CHECK (
                registered_to IS NULL OR registered_from IS NULL OR registered_to >= registered_from
            ),
            CONSTRAINT ck_lr_approval CHECK (
                (status = 'pending'  AND approved_by IS NULL AND approved_at IS NULL)
                OR (status IN ('approved', 'rejected') AND approved_by IS NOT NULL AND approved_at IS NOT NULL)
            )
        );
        """
    )

    # ===== TABLE 11: teaching_courses =====
    op.execute(
        """
        CREATE TABLE teaching_courses (
            id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID         NOT NULL,
            course_name     VARCHAR(255) NOT NULL,
            semester        VARCHAR(32)  NULL,
            year            SMALLINT     NULL,
            department_id   UUID         NULL,
            created_by      UUID         NULL,
            updated_by      UUID         NULL,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_tc_user    FOREIGN KEY (user_id)       REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_tc_dept    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
            CONSTRAINT fk_tc_created FOREIGN KEY (created_by)     REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_tc_updated FOREIGN KEY (updated_by)     REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT uq_tc_user_course_term UNIQUE (user_id, course_name, semester, year)
        );
        """
    )

    # ===== TABLE 12: community_services =====
    op.execute(
        """
        CREATE TABLE community_services (
            id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            content             TEXT         NOT NULL,
            performed_at        DATE         NULL,
            host                VARCHAR(255) NULL,
            performer_user_id   UUID         NOT NULL,
            department_id       UUID         NULL,
            created_by          UUID         NULL,
            updated_by          UUID         NULL,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

            CONSTRAINT fk_cs_performer FOREIGN KEY (performer_user_id) REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_cs_dept      FOREIGN KEY (department_id)     REFERENCES departments(id) ON DELETE RESTRICT,
            CONSTRAINT fk_cs_created   FOREIGN KEY (created_by)        REFERENCES users(id)       ON DELETE RESTRICT,
            CONSTRAINT fk_cs_updated   FOREIGN KEY (updated_by)        REFERENCES users(id)       ON DELETE RESTRICT
        );
        """
    )

    # ===== INDEXES (§4 contract) =====
    op.execute(
        "CREATE INDEX idx_hrp_next_raise ON hr_profiles(next_salary_raise_date) "
        "WHERE next_salary_raise_date IS NOT NULL;"
    )
    op.execute(
        "CREATE INDEX idx_hrp_contract_end ON hr_profiles(contract_end_date) "
        "WHERE contract_end_date IS NOT NULL;"
    )
    op.execute(
        "CREATE INDEX idx_hrp_contract_type ON hr_profiles(contract_type) "
        "WHERE contract_type IS NOT NULL;"
    )
    op.execute("CREATE INDEX idx_sh_user_date ON salary_history(user_id, raise_date DESC);")
    op.execute("CREATE INDEX idx_comp_user ON competences(user_id);")
    op.execute("CREATE INDEX idx_comp_kind ON competences(user_id, kind);")
    op.execute(
        "CREATE INDEX idx_comp_expiry ON competences(expiry_date) WHERE expiry_date IS NOT NULL;"
    )
    op.execute(
        "CREATE INDEX idx_comp_authorized ON competences(authorized_by) WHERE authorized_by IS NOT NULL;"
    )
    op.execute("CREATE INDEX idx_rp_lead ON research_projects(lead_user_id);")
    op.execute(
        "CREATE INDEX idx_rp_dept ON research_projects(department_id) WHERE department_id IS NOT NULL;"
    )
    op.execute("CREATE INDEX idx_rp_level ON research_projects(level) WHERE level IS NOT NULL;")
    op.execute(
        "CREATE INDEX idx_rp_dept_dates ON research_projects(department_id, start_date);"
    )
    op.execute("CREATE INDEX idx_pm_user ON project_members(user_id);")
    op.execute(
        "CREATE INDEX idx_pub_dept ON publications(department_id) WHERE department_id IS NOT NULL;"
    )
    op.execute(
        "CREATE INDEX idx_pub_category ON publications(category) WHERE category IS NOT NULL;"
    )
    op.execute("CREATE INDEX idx_pub_year ON publications(year) WHERE year IS NOT NULL;")
    op.execute("CREATE INDEX idx_pub_type ON publications(type);")
    op.execute(
        "CREATE UNIQUE INDEX uq_pub_patent_no ON publications(patent_no) "
        "WHERE type = 'patent' AND patent_no IS NOT NULL;"
    )
    op.execute(
        "CREATE INDEX idx_pa_user ON publication_authors(user_id) WHERE user_id IS NOT NULL;"
    )
    op.execute("CREATE INDEX idx_sm_mentor_year ON student_mentorships(mentor_id, year);")
    op.execute(
        "CREATE INDEX idx_sm_dept ON student_mentorships(department_id) WHERE department_id IS NOT NULL;"
    )
    op.execute("CREATE INDEX idx_sm_type ON student_mentorships(type) WHERE type IS NOT NULL;")
    op.execute("CREATE INDEX idx_lr_mentor ON lab_registrations(mentor_id);")
    op.execute("CREATE INDEX idx_lr_dept_status ON lab_registrations(department_id, status);")
    op.execute(
        "CREATE INDEX idx_lr_status ON lab_registrations(status) WHERE status = 'pending';"
    )
    op.execute("CREATE INDEX idx_lr_registered ON lab_registrations(registered_at);")
    op.execute("CREATE INDEX idx_tc_user_year ON teaching_courses(user_id, year);")
    op.execute(
        "CREATE INDEX idx_tc_dept ON teaching_courses(department_id) WHERE department_id IS NOT NULL;"
    )
    op.execute("CREATE INDEX idx_cs_performer ON community_services(performer_user_id);")
    op.execute(
        "CREATE INDEX idx_cs_dept ON community_services(department_id) WHERE department_id IS NOT NULL;"
    )
    op.execute(
        "CREATE INDEX idx_cs_performed ON community_services(performed_at) WHERE performed_at IS NOT NULL;"
    )

    # ===== SEED danh mục (§5 contract) — idempotent =====
    op.execute(
        """
        INSERT INTO contract_types (code, label, sort_order) VALUES
            ('probation',    'Hợp đồng thử việc',                1),
            ('fixed_term',   'Hợp đồng xác định thời hạn',       2),
            ('indefinite',   'Hợp đồng không xác định thời hạn', 3),
            ('civil_servant','Viên chức / biên chế',            4),
            ('collaborator', 'Cộng tác viên / thỉnh giảng',     5)
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO research_project_levels (code, label, sort_order) VALUES
            ('institution',  'Cấp Cơ sở',     1),
            ('university',   'Cấp Trường',    2),
            ('ministry',     'Cấp Bộ',        3),
            ('province',     'Cấp Tỉnh',      4),
            ('national',     'Cấp Nhà nước',  5),
            ('international','Cấp Quốc tế / Hợp tác quốc tế', 6)
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO publication_categories (code, label, sort_order) VALUES
            ('isi_q1',     'ISI Q1',             1),
            ('isi_q2',     'ISI Q2',             2),
            ('isi_q3',     'ISI Q3',             3),
            ('isi_q4',     'ISI Q4',             4),
            ('scopus',     'Scopus',             5),
            ('domestic',   'Tạp chí trong nước', 6),
            ('conference', 'Kỷ yếu hội nghị',    7)
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        INSERT INTO mentorship_types (code, label, sort_order) VALUES
            ('thesis_bachelor', 'Khóa luận tốt nghiệp (ĐH)',   1),
            ('thesis_master',   'Luận văn Thạc sĩ',            2),
            ('thesis_phd',      'Luận án Tiến sĩ',             3),
            ('student_research','NCKH sinh viên',              4),
            ('project',         'Đồ án môn học / chuyên ngành',5)
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:
    # Drop ngược thứ tự FK (§9 contract). KHÔNG drop extension dùng chung;
    # KHÔNG đụng roles_permissions/attachments (M4 không sửa).
    op.execute("DROP TABLE IF EXISTS community_services       CASCADE;")
    op.execute("DROP TABLE IF EXISTS teaching_courses         CASCADE;")
    op.execute("DROP TABLE IF EXISTS lab_registrations        CASCADE;")
    op.execute("DROP TABLE IF EXISTS student_mentorships      CASCADE;")
    op.execute("DROP TABLE IF EXISTS publication_authors      CASCADE;")
    op.execute("DROP TABLE IF EXISTS publications             CASCADE;")
    op.execute("DROP TABLE IF EXISTS project_members          CASCADE;")
    op.execute("DROP TABLE IF EXISTS research_projects        CASCADE;")
    op.execute("DROP TABLE IF EXISTS hr_notification_dedup    CASCADE;")
    op.execute("DROP TABLE IF EXISTS competences              CASCADE;")
    op.execute("DROP TABLE IF EXISTS salary_history           CASCADE;")
    op.execute("DROP TABLE IF EXISTS hr_profiles              CASCADE;")
    op.execute("DROP TABLE IF EXISTS mentorship_types         CASCADE;")
    op.execute("DROP TABLE IF EXISTS publication_categories   CASCADE;")
    op.execute("DROP TABLE IF EXISTS research_project_levels  CASCADE;")
    op.execute("DROP TABLE IF EXISTS contract_types           CASCADE;")
