"""M25 — Báo cáo hoạt động hàng tháng (activity_reports).

Giảng viên/leader/lãnh đạo/KTV nộp báo cáo THÁNG gồm các hoạt động; văn phòng xem danh
sách tổng hợp. Mỗi dòng hoạt động được tạo THẲNG vào bảng thành tích đã có (gắn report_id)
→ tự động hiện ở các trang Đề tài/Bài báo/Hợp đồng/Giảng dạy/Công tác khác.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400024"
down_revision: Union[str, None] = "1718870400023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            reporter_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            department_id UUID REFERENCES departments(id) ON DELETE RESTRICT,
            period_label VARCHAR(32) NOT NULL,   -- "01/2026"
            period_year SMALLINT,
            academic_year VARCHAR(16),
            status VARCHAR(16) NOT NULL DEFAULT 'submitted',  -- draft|submitted|reviewed
            note TEXT,
            submitted_at TIMESTAMPTZ,
            reviewed_by UUID REFERENCES users(id) ON DELETE RESTRICT,
            reviewed_at TIMESTAMPTZ,
            created_by UUID REFERENCES users(id) ON DELETE RESTRICT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_ar_status CHECK (status IN ('draft','submitted','reviewed')),
            CONSTRAINT uq_ar_reporter_period UNIQUE (reporter_user_id, period_label)
        );
        CREATE INDEX IF NOT EXISTS ix_activity_reports_reporter ON activity_reports(reporter_user_id);
        CREATE INDEX IF NOT EXISTS ix_activity_reports_department_id ON activity_reports(department_id);
        CREATE INDEX IF NOT EXISTS ix_activity_reports_status ON activity_reports(status);

        -- Gắn report_id (nullable) vào các bảng thành tích để dòng nhập từ báo cáo hiện
        -- ở đúng module + truy vết được về báo cáo nguồn.
        ALTER TABLE research_projects   ADD COLUMN IF NOT EXISTS report_id UUID
            REFERENCES activity_reports(id) ON DELETE SET NULL;
        ALTER TABLE publications        ADD COLUMN IF NOT EXISTS report_id UUID
            REFERENCES activity_reports(id) ON DELETE SET NULL;
        ALTER TABLE teaching_courses    ADD COLUMN IF NOT EXISTS report_id UUID
            REFERENCES activity_reports(id) ON DELETE SET NULL;
        ALTER TABLE research_contracts  ADD COLUMN IF NOT EXISTS report_id UUID
            REFERENCES activity_reports(id) ON DELETE SET NULL;
        ALTER TABLE staff_activities    ADD COLUMN IF NOT EXISTS report_id UUID
            REFERENCES activity_reports(id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS ix_research_projects_report_id ON research_projects(report_id);
        CREATE INDEX IF NOT EXISTS ix_publications_report_id ON publications(report_id);
        CREATE INDEX IF NOT EXISTS ix_teaching_courses_report_id ON teaching_courses(report_id);
        CREATE INDEX IF NOT EXISTS ix_research_contracts_report_id ON research_contracts(report_id);
        CREATE INDEX IF NOT EXISTS ix_staff_activities_report_id ON staff_activities(report_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE research_projects   DROP COLUMN IF EXISTS report_id;
        ALTER TABLE publications        DROP COLUMN IF EXISTS report_id;
        ALTER TABLE teaching_courses    DROP COLUMN IF EXISTS report_id;
        ALTER TABLE research_contracts  DROP COLUMN IF EXISTS report_id;
        ALTER TABLE staff_activities    DROP COLUMN IF EXISTS report_id;
        DROP TABLE IF EXISTS activity_reports;
        """
    )
