"""m43: người liên hệ có VAI TRÒ — người gửi mẫu ≠ người nhận kết quả ≠ người trả tiền.

VẤN ĐỀ
`sample_intakes` chỉ có ba ô phẳng `contact_person`, `phone`, `email`, và trên giao
diện chọn một người trong danh bạ sẽ GHI ĐÈ cả ba. Danh bạ `customer_contacts` thì
được mô tả trong chính docstring của nó là "danh bạ phẳng, KHÔNG phân vai trò".

Ba tình huống rất phổ biến không biểu diễn được:
  · QA mang mẫu tới, nhưng kết quả phải giao cho Trưởng phòng QA
  · liên hệ chuyên môn (hỏi về phương pháp) ≠ liên hệ thanh toán (nhận hoá đơn)
  · QA gửi mẫu vi sinh, R&D gửi mẫu hoá lý — hệ thống không biết ai gửi mẫu nào

HAI TẦNG, HAI MỤC ĐÍCH
`customer_contacts.roles` — vai trò MẶC ĐỊNH trong sổ khách, để quầy tự điền nhanh.
`intake_contacts`        — BẢN CHỤP trên từng phiếu, giữ nguyên tắc snapshot của
                           sample_intakes: phiếu đã in không được đổi theo danh bạ.

KHÔNG có khoá ngoại từ intake_contacts tới customer_contacts. Đó là cố ý và cùng lý
do m35 đã nêu: người liên hệ đổi hoặc nghỉ việc về sau không được phép làm sai lệch
phiếu đã in (mặt sau BM 7.1/01, khoản 5).

GIỮ NGUYÊN `contact_person`/`phone`/`email` trên phiếu: chúng đã in ra giấy và là
liên hệ chính. Bảng mới BỔ SUNG các vai trò khác, không thay thế.

RÀNG BUỘC unique(intake_id, role): mỗi phiếu một người cho mỗi vai. Nếu nghiệp vụ xác
nhận một vai có thể nhiều người (Q4), gỡ ràng buộc này — nhưng đừng gỡ trước khi có
xác nhận, vì "kết quả giao cho ai" mà mơ hồ thì tính năng mất ý nghĩa.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "1718870400042"
down_revision: str = "1718870400041"
branch_labels = None
depends_on = None

# courier          — người mang mẫu tới quầy
# technical        — liên hệ chuyên môn (hỏi về phương pháp, nền mẫu)
# result_recipient — người nhận phiếu kết quả
# billing          — liên hệ hoá đơn / thanh toán
# Hai dạng cho hai ngữ cảnh SQL khác nhau: `IN (...)` dùng ngoặc TRÒN, còn
# `ARRAY[...]` dùng ngoặc VUÔNG — dùng nhầm thì Postgres báo lỗi cú pháp.
_ROLES_IN = "('courier','technical','result_recipient','billing')"
_ROLES_ARR = "['courier','technical','result_recipient','billing']"


def upgrade() -> None:
    op.add_column(
        "customer_contacts",
        sa.Column(
            "roles", postgresql.ARRAY(sa.Text()), nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    # Mảng rỗng hợp lệ (chưa phân vai); có phần tử thì phải nằm trong tập trên.
    op.create_check_constraint(
        "ck_contact_roles", "customer_contacts",
        f"roles <@ ARRAY{_ROLES_ARR}::text[]",
    )

    op.create_table(
        "intake_contacts",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "intake_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sample_intakes.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("role", sa.String(24), nullable=False),
        # BẢN CHỤP — không có FK tới customer_contacts, cố ý (xem docstring).
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("job_title", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(f"role IN {_ROLES_IN}", name="ck_intake_contact_role"),
        sa.UniqueConstraint("intake_id", "role", name="uq_intake_contact_role"),
    )
    op.create_index("ix_intake_contacts_intake", "intake_contacts", ["intake_id"])


def downgrade() -> None:
    op.drop_index("ix_intake_contacts_intake", table_name="intake_contacts")
    op.drop_table("intake_contacts")
    op.drop_constraint("ck_contact_roles", "customer_contacts", type_="check")
    op.drop_column("customer_contacts", "roles")
