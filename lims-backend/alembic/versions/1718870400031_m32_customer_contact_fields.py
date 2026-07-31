"""m32: customers — 5 trường liên hệ đầy đủ (địa chỉ, MST, người liên hệ, ĐT, mail).

Phiếu nhận mẫu BM 7.1.01 cần 6 thông tin khách hàng, nhưng master data `customers`
chỉ có name + contact (1 ô gộp) → chọn khách từ sổ cũng chỉ tự điền được mỗi TÊN,
5 ô còn lại vẫn phải gõ tay. Bổ sung đúng 5 cột còn thiếu để m33 nối
sample_intakes → customers mới có cái để tự điền.

Độ dài cột lấy KHỚP với cột cùng tên ở sample_intakes (m28) — hai bên chép qua lại
nên lệch độ dài là cắt chuỗi âm thầm.

Thuần ADD COLUMN NULL: không backfill, không khoá bảng lâu, dữ liệu cũ vẫn hợp lệ.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "1718870400031"
down_revision: str = "1718870400030"
branch_labels = None
depends_on = None

# (tên cột, độ dài) — khớp sample_intakes.<cùng tên>
_COLUMNS = [
    ("address", 500),
    ("tax_code", 50),
    ("contact_person", 255),
    ("phone", 50),
    ("email", 255),
]


def upgrade() -> None:
    for name, length in _COLUMNS:
        op.add_column("customers", sa.Column(name, sa.String(length), nullable=True))


def downgrade() -> None:
    for name, _ in reversed(_COLUMNS):
        op.drop_column("customers", name)
