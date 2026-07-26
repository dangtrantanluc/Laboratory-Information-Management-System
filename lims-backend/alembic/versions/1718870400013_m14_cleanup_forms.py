"""M14 — Dọn 2 lab demo cũ (d2/d3) + thêm category 'TL' cho kho biểu mẫu.

- d2 "PTN Hóa" → e22 (Hóa sinh, DIV2); d3 "PTN Sinh" → e13 (Công nghệ vi sinh, DIV1).
  Remap mọi FK department_id + users rồi xóa d2/d3 (bỏ trùng lặp với 9 lab thật).
- form_templates.category thêm 'TL' (tài liệu chung: quyết định, sổ tay, sơ đồ… không
  phải BM/QT/HD) để import 199 file VILAS thật.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400013"
down_revision: Union[str, None] = "1718870400012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_D2 = "'00000000-0000-0000-0000-0000000000d2'"
_D3 = "'00000000-0000-0000-0000-0000000000d3'"
_E22 = "'00000000-0000-0000-0000-000000000e22'"
_E13 = "'00000000-0000-0000-0000-000000000e13'"

# Mọi bảng có FK department_id
_DEPT_FK_TABLES = [
    "chemicals", "community_services", "documents", "equipments", "form_submissions",
    "improvements", "lab_registrations", "nonconformities", "publications",
    "research_projects", "risks", "samples", "student_mentorships",
    "teaching_courses", "test_requests", "users",
]


def upgrade() -> None:
    # ===== 1. Remap d2→e22, d3→e13 trên mọi bảng =====
    for tbl in _DEPT_FK_TABLES:
        op.execute(f"UPDATE {tbl} SET department_id={_E22} WHERE department_id={_D2};")
        op.execute(f"UPDATE {tbl} SET department_id={_E13} WHERE department_id={_D3};")

    # Chuyển trưởng phòng cũ sang lab tương ứng nếu lab thật chưa có trưởng
    op.execute(
        f"""
        UPDATE departments t SET lead_user_id=(SELECT lead_user_id FROM departments WHERE id={_D2})
        WHERE t.id={_E22} AND t.lead_user_id IS NULL;
        UPDATE departments t SET lead_user_id=(SELECT lead_user_id FROM departments WHERE id={_D3})
        WHERE t.id={_E13} AND t.lead_user_id IS NULL;
        """
    )
    # Gỡ lead của d2/d3 trước khi xóa (tránh vướng nếu có ràng buộc)
    op.execute(f"UPDATE departments SET lead_user_id=NULL WHERE id IN ({_D2},{_D3});")
    op.execute(f"DELETE FROM departments WHERE id IN ({_D2},{_D3});")

    # ===== 2. Thêm category 'TL' =====
    op.execute("ALTER TABLE form_templates DROP CONSTRAINT IF EXISTS ck_form_tpl_category;")
    op.execute(
        "ALTER TABLE form_templates ADD CONSTRAINT ck_form_tpl_category "
        "CHECK (category IN ('BM','QT','HD','TL'));"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE form_templates DROP CONSTRAINT IF EXISTS ck_form_tpl_category;")
    op.execute("DELETE FROM form_templates WHERE category='TL';")
    op.execute(
        "ALTER TABLE form_templates ADD CONSTRAINT ck_form_tpl_category "
        "CHECK (category IN ('BM','QT','HD'));"
    )
    # Không tái tạo d2/d3 (dữ liệu đã remap — không đảo ngược an toàn).
