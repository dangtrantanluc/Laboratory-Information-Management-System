"""m6_reporting — Báo cáo & Thống kê (M6.3 R15 hạ tầng access_stats).

M6 READ-ONLY aggregate: KHÔNG tạo bảng nghiệp vụ/snapshot mới (SRS OUT-OF-SCOPE).
Chỉ:
  - ALTER access_stats ADD COLUMN event_type (login|page_view, NULL — non-breaking)
    để middleware M6 phân loại lượt đăng nhập vs xem trang (FR-RPT-009, BR-RPT-004).
  - CREATE INDEX (at,event_type) + (event_type,at) phục vụ thống kê truy cập R15
    (FR-RPT-007). Index (user_id,at)/(at) đã có ở M7 → KHÔNG tạo lại.

KHÔNG seed permission mới: report:business/report:finance đã seed ở M7;
R15 (thống kê truy cập hệ thống) map quyền audit:read (admin/leader) — đã có M7.

Revision ID: 1718870400007
Revises: 1718870400006 (M5 Equipment Calibration)
Create Date: 2026-06-20

Thứ tự migration tổng thể: M7 → M1 → M2 → M4 → M3 → M5 → M6 (file này).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400007"
down_revision: Union[str, None] = "1718870400006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER access_stats: ADD event_type (non-breaking, nullable + CHECK) — M6-D2
    op.execute(
        """
        ALTER TABLE access_stats
            ADD COLUMN IF NOT EXISTS event_type VARCHAR(16) NULL
                CHECK (event_type IS NULL OR event_type IN ('login', 'page_view'));
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN access_stats.event_type IS
            'Loại lượt truy cập (M6.3/R15): login | page_view. NULL = bản ghi trước M6.';
        """
    )

    # Index aggregate R15 — (at,event_type) + (event_type,at) — M6-D4
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_access_at_event "
        "ON access_stats(at DESC, event_type);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_access_event_at "
        "ON access_stats(event_type, at DESC) WHERE event_type IS NOT NULL;"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_access_event_at;")
    op.execute("DROP INDEX IF EXISTS idx_access_at_event;")
    op.execute("ALTER TABLE access_stats DROP COLUMN IF EXISTS event_type;")
