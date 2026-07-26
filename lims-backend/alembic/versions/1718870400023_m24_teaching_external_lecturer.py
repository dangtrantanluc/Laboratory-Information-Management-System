"""M24 — teaching_courses cho phép giảng viên NGOÀI hệ thống (lecturer_external_name).

File "Tổng hợp hoạt động 2024-2025" ghi tên giảng viên tự do, đa số chưa có tài khoản
user → không import được (user_id NOT NULL). Nới: user_id nullable + lecturer_external_name
(XOR như project_members/publication_authors) để nhập được cả giảng viên ngoài HT.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400023"
down_revision: Union[str, None] = "1718870400022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE teaching_courses
            ALTER COLUMN user_id DROP NOT NULL,
            ADD COLUMN IF NOT EXISTS lecturer_external_name VARCHAR(255);
        ALTER TABLE teaching_courses
            ADD CONSTRAINT ck_tc_lecturer_xor CHECK (
                (user_id IS NOT NULL AND lecturer_external_name IS NULL)
                OR (user_id IS NULL AND lecturer_external_name IS NOT NULL)
            );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE teaching_courses DROP CONSTRAINT IF EXISTS ck_tc_lecturer_xor;
        DELETE FROM teaching_courses WHERE user_id IS NULL;
        ALTER TABLE teaching_courses ALTER COLUMN user_id SET NOT NULL;
        ALTER TABLE teaching_courses DROP COLUMN IF EXISTS lecturer_external_name;
        """
    )
