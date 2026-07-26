"""M19 — Thẻ vào PTN (sinh viên): lab_access_cards.

Danh sách quản trị (CRUD, không qua duyệt) do Văn phòng (role 'office') quản lý,
đối chiếu theo file "DANH SÁCH SINH VIÊN ĐÃ ĐƯỢC CẤP THẺ VÀO PTN": họ tên, lớp,
MSSV, email, phòng đăng ký sử dụng, mục đích, giáo viên hướng dẫn, thời gian
hiệu lực (từ-đến), ghi chú. KHÔNG liên quan tới bảng lab_registrations (NCKH,
có quy trình duyệt) đã có sẵn.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400018"
down_revision: Union[str, None] = "1718870400017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy import text

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lab_access_cards (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            student_name     VARCHAR(255) NOT NULL,
            class_name       VARCHAR(50),
            student_code     VARCHAR(30)  NOT NULL,
            email            VARCHAR(255),
            room             VARCHAR(255) NOT NULL,
            purpose          VARCHAR(255),
            supervisor_name  VARCHAR(255),
            valid_from       DATE NOT NULL,
            valid_to         DATE,
            note             TEXT,
            created_by       UUID REFERENCES users(id) ON DELETE RESTRICT,
            updated_by       UUID REFERENCES users(id) ON DELETE RESTRICT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_lab_access_period CHECK (valid_to IS NULL OR valid_to >= valid_from)
        );
        CREATE INDEX IF NOT EXISTS idx_lab_access_student_code ON lab_access_cards(student_code);
        CREATE INDEX IF NOT EXISTS idx_lab_access_supervisor ON lab_access_cards(supervisor_name);
        """
    )

    # RBAC
    conn.execute(
        text(
            """
            INSERT INTO permissions (resource, action, description) VALUES
                ('lab_access_card','read','Xem danh sách thẻ vào PTN'),
                ('lab_access_card','manage','Thêm/sửa/xóa thẻ vào PTN')
            ON CONFLICT (resource, action) DO NOTHING;
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO roles_permissions (role, resource, action, scope) VALUES
                ('admin','lab_access_card','read','all'),
                ('admin','lab_access_card','manage','all'),
                ('leader','lab_access_card','read','all'),
                ('qms','lab_access_card','read','all'),
                ('office','lab_access_card','read','all'),
                ('office','lab_access_card','manage','all')
            ON CONFLICT (role, resource, action) DO NOTHING;
            """
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM roles_permissions WHERE resource = 'lab_access_card';")
    op.execute("DELETE FROM permissions WHERE resource = 'lab_access_card';")
    op.execute("DROP TABLE IF EXISTS lab_access_cards CASCADE;")
