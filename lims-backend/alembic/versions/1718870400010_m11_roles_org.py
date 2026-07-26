"""M11 — Vai trò mở rộng + cơ cấu phòng thật (division/lab/chức năng).

Thêm 3 role: reception (nhận mẫu), qms (quản lý chất lượng), lab_manager (trưởng phòng lab).
KHÔNG đổi mã 'staff' (nhãn hiển thị "KTV" ở FE) để tránh phá ma trận/seed cũ.

Cột departments.kind + is_vlab phân loại đơn vị; parent_id gom 9 lab thành 2 division.
Giữ nguyên d1..d4 (demo data cũ tham chiếu) — chỉ gán kind; thêm cơ cấu thật (e*/f*).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400010"
down_revision: Union[str, None] = "1718870400009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 3 role mới thêm vào các CHECK constraint role
_NEW_ROLES = "'admin', 'leader', 'accountant', 'staff', 'reception', 'qms', 'lab_manager'"


def upgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy import text

    # ===== 1. Nới CHECK role (users + roles_permissions) =====
    # m7 tạo CHECK inline KHÔNG đặt tên → Postgres tự đặt *_role_check. Drop cả 2 tên
    # (auto + ck_*) để chắc chắn, rồi thêm lại constraint có tên.
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role;")
    op.execute(
        f"ALTER TABLE users ADD CONSTRAINT ck_users_role CHECK (role IN ({_NEW_ROLES}));"
    )
    op.execute("ALTER TABLE roles_permissions DROP CONSTRAINT IF EXISTS roles_permissions_role_check;")
    op.execute("ALTER TABLE roles_permissions DROP CONSTRAINT IF EXISTS ck_rp_role;")
    op.execute(
        f"ALTER TABLE roles_permissions ADD CONSTRAINT ck_rp_role CHECK (role IN ({_NEW_ROLES}));"
    )

    # ===== 2. Cột phân loại đơn vị =====
    op.execute(
        """
        ALTER TABLE departments
            ADD COLUMN IF NOT EXISTS kind VARCHAR(20) NOT NULL DEFAULT 'lab',
            ADD COLUMN IF NOT EXISTS is_vlab BOOLEAN NOT NULL DEFAULT false;
        """
    )
    op.execute("ALTER TABLE departments DROP CONSTRAINT IF EXISTS ck_dept_kind;")
    op.execute(
        """
        ALTER TABLE departments ADD CONSTRAINT ck_dept_kind
            CHECK (kind IN ('leadership','reception','office','qms','division','lab'));
        """
    )

    # ===== 3. Gán kind cho 4 phòng demo cũ (d1..d4) =====
    op.execute(
        """
        UPDATE departments SET kind='leadership' WHERE id='00000000-0000-0000-0000-0000000000d1';
        UPDATE departments SET kind='lab'        WHERE id='00000000-0000-0000-0000-0000000000d2';
        UPDATE departments SET kind='lab'        WHERE id='00000000-0000-0000-0000-0000000000d3';
        UPDATE departments SET kind='office'     WHERE id='00000000-0000-0000-0000-0000000000d4';
        """
    )

    # ===== 4. Cơ cấu thật: 2 division + 9 lab + Nhận mẫu + QLCL =====
    conn.execute(
        text(
            """
            INSERT INTO departments (id, name, code, parent_id, kind, is_vlab, status) VALUES
              -- Phòng chức năng
              ('00000000-0000-0000-0000-0000000000f1','Phòng Nhận mẫu','NM',NULL,'reception',false,'active'),
              ('00000000-0000-0000-0000-0000000000f2','Phòng Quản lý chất lượng','QLCL',NULL,'qms',false,'active'),
              -- 2 Division (phòng nghiên cứu trọng điểm)
              ('00000000-0000-0000-0000-0000000000e1','Phòng Công nghệ sinh học & vi sinh ứng dụng tiên tiến','DIV1',NULL,'division',false,'active'),
              ('00000000-0000-0000-0000-0000000000e2','Phòng Công nghệ môi trường – Hóa sinh ứng dụng & Nông nghiệp tuần hoàn','DIV2',NULL,'division',false,'active'),
              -- Division 1: 5 lab (VLab)
              ('00000000-0000-0000-0000-000000000e11','Sinh học phân tử, công nghệ gen','LAB-SHPT','00000000-0000-0000-0000-0000000000e1','lab',true,'active'),
              ('00000000-0000-0000-0000-000000000e12','Công nghệ tế bào Thực vật và Phát triển dược liệu','LAB-CNTB','00000000-0000-0000-0000-0000000000e1','lab',true,'active'),
              ('00000000-0000-0000-0000-000000000e13','Công nghệ vi sinh','LAB-CNVS','00000000-0000-0000-0000-0000000000e1','lab',true,'active'),
              ('00000000-0000-0000-0000-000000000e14','Sức khoẻ cây trồng và vi sinh nông nghiệp','LAB-SKCT','00000000-0000-0000-0000-0000000000e1','lab',true,'active'),
              ('00000000-0000-0000-0000-000000000e15','Nấm ăn và nấm dược liệu','LAB-NAM','00000000-0000-0000-0000-0000000000e1','lab',true,'active'),
              -- Division 2: 4 lab
              ('00000000-0000-0000-0000-000000000e21','Nông nghiệp tuần hoàn','LAB-NNTH','00000000-0000-0000-0000-0000000000e2','lab',false,'active'),
              ('00000000-0000-0000-0000-000000000e22','Hóa sinh – Hoạt chất sinh học ứng dụng','LAB-HS','00000000-0000-0000-0000-0000000000e2','lab',false,'active'),
              ('00000000-0000-0000-0000-000000000e23','Khoa học kỹ thuật môi trường','LAB-KTMT','00000000-0000-0000-0000-0000000000e2','lab',false,'active'),
              ('00000000-0000-0000-0000-000000000e24','Môi trường - đất – phân bón','LAB-MTD','00000000-0000-0000-0000-0000000000e2','lab',false,'active')
            ON CONFLICT (id) DO NOTHING;
            """
        )
    )

    # ===== 5. Ma trận quyền cho role mới =====
    conn.execute(
        text(
            """
            INSERT INTO roles_permissions (role, resource, action, scope) VALUES
              -- reception: nghiệp vụ nhận mẫu (tạo/phân công mẫu toàn hệ thống)
              ('reception','sample','create','all'),
              ('reception','sample','read','all'),
              ('reception','sample','assign','all'),
              ('reception','report','business','all'),

              -- qms: quản trị kho tài liệu/biểu mẫu (duyệt) toàn hệ thống
              ('qms','document','create','all'),
              ('qms','document','read','all'),
              ('qms','document','approve','all'),
              ('qms','sample','read','all'),

              -- lab_manager: như KTV nhưng duyệt trong phạm vi phòng
              ('lab_manager','sample','create','department'),
              ('lab_manager','sample','read','all'),
              ('lab_manager','sample','assign','department'),
              ('lab_manager','sample','result','department'),
              ('lab_manager','sample','approve','department'),
              ('lab_manager','chemical','read','all'),
              ('lab_manager','chemical','transact','department'),
              ('lab_manager','chemical','create','department'),
              ('lab_manager','document','create','department'),
              ('lab_manager','document','read','all'),
              ('lab_manager','document','approve','department'),
              ('lab_manager','hr','read','own'),
              ('lab_manager','research','manage','own'),
              ('lab_manager','equipment','manage','department'),
              ('lab_manager','report','business','department')
            ON CONFLICT (role, resource, action) DO NOTHING;
            """
        )
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM roles_permissions WHERE role IN ('reception','qms','lab_manager');"
    )
    op.execute(
        """
        DELETE FROM departments WHERE id IN (
            '00000000-0000-0000-0000-0000000000f1','00000000-0000-0000-0000-0000000000f2',
            '00000000-0000-0000-0000-0000000000e1','00000000-0000-0000-0000-0000000000e2',
            '00000000-0000-0000-0000-000000000e11','00000000-0000-0000-0000-000000000e12',
            '00000000-0000-0000-0000-000000000e13','00000000-0000-0000-0000-000000000e14',
            '00000000-0000-0000-0000-000000000e15','00000000-0000-0000-0000-000000000e21',
            '00000000-0000-0000-0000-000000000e22','00000000-0000-0000-0000-000000000e23',
            '00000000-0000-0000-0000-000000000e24'
        );
        """
    )
    op.execute("ALTER TABLE departments DROP CONSTRAINT IF EXISTS ck_dept_kind;")
    op.execute("ALTER TABLE departments DROP COLUMN IF EXISTS is_vlab;")
    op.execute("ALTER TABLE departments DROP COLUMN IF EXISTS kind;")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role;")
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_role "
        "CHECK (role IN ('admin', 'leader', 'accountant', 'staff'));"
    )
    op.execute("ALTER TABLE roles_permissions DROP CONSTRAINT IF EXISTS ck_rp_role;")
    op.execute(
        "ALTER TABLE roles_permissions ADD CONSTRAINT ck_rp_role "
        "CHECK (role IN ('admin', 'leader', 'accountant', 'staff'));"
    )
