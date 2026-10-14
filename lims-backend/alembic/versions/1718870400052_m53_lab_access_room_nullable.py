"""m53: Thẻ vào PTN — cho phép trống "Đăng ký sử dụng PTN" (room).

VẤN ĐỀ
Tính năng nhập Excel lấy file "DANH SÁCH SINH VIÊN ĐÃ ĐƯỢC CẤP THẺ VÀO PTN" làm gốc.
Trong file thật (Quý I.2026) có sinh viên đã được cấp thẻ nhưng Văn phòng chưa ghi
phòng — cột này để trống. Giữ NOT NULL thì những dòng đó bị loại khi nhập, và file
xuất ra sẽ thiếu người so với file gốc: đúng thứ mà một danh sách cấp thẻ không được
phép sai.

Trống ở đây mang nghĩa "chưa ghi", không phải "không có phòng" — giao diện hiển thị
"—" và người dùng bổ sung sau.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "1718870400052"
down_revision: str = "1718870400051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("lab_access_cards", "room", existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE lab_access_cards SET room = '' WHERE room IS NULL")
    op.alter_column("lab_access_cards", "room", existing_type=sa.String(255), nullable=False)
