"""m51: công bố khoa học ghi được THÁNG, không chỉ năm.

VẤN ĐỀ
`publications` chỉ có cột `year`. Màn hình chi tiết vì thế chỉ nói được "NĂM CÔNG BỐ
2025", trong khi bìa tạp chí và quyết định cấp bằng đều ghi tháng. Với hồ sơ chịu kiểm
toán, "tháng 3/2025" và "tháng 11/2025" là hai mốc khác nhau — gộp về một con số năm là
mất thông tin ngay từ lúc nhập, không lấy lại được.

NULLABLE, KHÔNG BẮT BUỘC
Dữ liệu sẵn có (file "TỔNG HỢP CÁC HOẠT ĐỘNG 2024-2025" của Viện) chỉ ghi năm. Ép NOT
NULL thì hoặc phải bịa tháng cho hàng trăm bản ghi cũ, hoặc migration đổ vỡ. NULL ở đây
có nghĩa thật và đọc được: "chỉ biết năm". Giao diện hiển thị "3/2025" khi có tháng và
"2025" khi không — không bịa "1/2025".

KHÔNG ĐỤNG `year`
`year` vẫn là cột được lọc và được xuất Excel theo biểu mẫu của Viện. `month` là chi
tiết bổ sung, không thay thế, nên mọi truy vấn và báo cáo hiện có giữ nguyên hành vi.

CHECK 1..12 ở tầng DB là lưới an toàn cho đường nhập liệu không qua API (script nhập
Excel, sửa tay); tầng ứng dụng vẫn validate để trả lỗi 400 đọc được.
"""
from alembic import op

revision: str = "1718870400050"
down_revision: str = "1718870400049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE publications ADD COLUMN IF NOT EXISTS month SMALLINT;")
    op.execute(
        "ALTER TABLE publications ADD CONSTRAINT ck_pub_month "
        "CHECK (month IS NULL OR (month >= 1 AND month <= 12));"
    )


def downgrade() -> None:
    # MẤT DỮ LIỆU: lược đồ cũ không có chỗ chứa tháng.
    op.execute("ALTER TABLE publications DROP CONSTRAINT IF EXISTS ck_pub_month;")
    op.execute("ALTER TABLE publications DROP COLUMN IF EXISTS month;")
