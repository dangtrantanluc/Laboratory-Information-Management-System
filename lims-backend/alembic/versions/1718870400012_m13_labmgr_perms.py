"""M13 — Trưởng phòng lab kế thừa TOÀN BỘ quyền của KTV (staff).

lab_manager = KTV + quyền duyệt trong phòng. m11 chỉ thêm tập cốt lõi nên lab_manager
thiếu các quyền staff được cấp ở m5/m8/m10 (equipment granular, calibration, NC, risk,
improvement). Copy mọi quyền staff sang lab_manager (giữ scope), quyền duyệt đã thêm ở m11.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400012"
down_revision: Union[str, None] = "1718870400011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO roles_permissions (role, resource, action, scope)
        SELECT 'lab_manager', resource, action, scope
        FROM roles_permissions WHERE role='staff'
        ON CONFLICT (role, resource, action) DO NOTHING;
        """
    )


def downgrade() -> None:
    # Xóa các quyền lab_manager trùng resource/action với staff mà KHÔNG do m11 thêm.
    # Đơn giản: xóa toàn bộ lab_manager rồi để m11 downgrade lo phần còn lại nếu cần.
    op.execute(
        """
        DELETE FROM roles_permissions rp
        WHERE rp.role='lab_manager'
          AND EXISTS (
            SELECT 1 FROM roles_permissions s
            WHERE s.role='staff' AND s.resource=rp.resource AND s.action=rp.action
          )
          AND NOT (rp.resource='document' AND rp.action='approve')
          AND NOT (rp.resource='sample' AND rp.action='approve');
        """
    )
