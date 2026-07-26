"""M18 — Đổi tên vai trò 'accountant' (Kế toán) thành 'office' (Văn phòng).

Chỉ đổi mã vai trò dùng để phân quyền trong hệ thống; KHÔNG đổi tên phòng ban
"Phòng Kế toán" (department) và KHÔNG đổi chức danh HR "Kế toán viên" — đó là
tên đơn vị/chức danh thực tế, độc lập với vai trò RBAC.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400017"
down_revision: Union[str, None] = "1718870400016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_ROLES = "'admin', 'leader', 'accountant', 'staff', 'reception', 'qms', 'lab_manager'"
_NEW_ROLES = "'admin', 'leader', 'office', 'staff', 'reception', 'qms', 'lab_manager'"


def upgrade() -> None:
    # Nới CHECK trước để chấp nhận cả 2 giá trị trong lúc UPDATE dữ liệu.
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role;")
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_role "
        "CHECK (role IN ('admin', 'leader', 'accountant', 'office', 'staff', "
        "'reception', 'qms', 'lab_manager'));"
    )
    op.execute("ALTER TABLE roles_permissions DROP CONSTRAINT IF EXISTS ck_rp_role;")
    op.execute(
        "ALTER TABLE roles_permissions ADD CONSTRAINT ck_rp_role "
        "CHECK (role IN ('admin', 'leader', 'accountant', 'office', 'staff', "
        "'reception', 'qms', 'lab_manager'));"
    )

    op.execute("UPDATE users SET role = 'office' WHERE role = 'accountant';")
    op.execute("UPDATE roles_permissions SET role = 'office' WHERE role = 'accountant';")

    # Siết lại CHECK còn 'office', bỏ 'accountant'.
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role;")
    op.execute(f"ALTER TABLE users ADD CONSTRAINT ck_users_role CHECK (role IN ({_NEW_ROLES}));")
    op.execute("ALTER TABLE roles_permissions DROP CONSTRAINT IF EXISTS ck_rp_role;")
    op.execute(f"ALTER TABLE roles_permissions ADD CONSTRAINT ck_rp_role CHECK (role IN ({_NEW_ROLES}));")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role;")
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_role "
        "CHECK (role IN ('admin', 'leader', 'accountant', 'office', 'staff', "
        "'reception', 'qms', 'lab_manager'));"
    )
    op.execute("ALTER TABLE roles_permissions DROP CONSTRAINT IF EXISTS ck_rp_role;")
    op.execute(
        "ALTER TABLE roles_permissions ADD CONSTRAINT ck_rp_role "
        "CHECK (role IN ('admin', 'leader', 'accountant', 'office', 'staff', "
        "'reception', 'qms', 'lab_manager'));"
    )

    op.execute("UPDATE users SET role = 'accountant' WHERE role = 'office';")
    op.execute("UPDATE roles_permissions SET role = 'accountant' WHERE role = 'office';")

    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role;")
    op.execute(f"ALTER TABLE users ADD CONSTRAINT ck_users_role CHECK (role IN ({_OLD_ROLES}));")
    op.execute("ALTER TABLE roles_permissions DROP CONSTRAINT IF EXISTS ck_rp_role;")
    op.execute(f"ALTER TABLE roles_permissions ADD CONSTRAINT ck_rp_role CHECK (role IN ({_OLD_ROLES}));")
