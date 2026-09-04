"""m44: tra cứu khách hàng theo mã số thuế / điện thoại / email.

VẤN ĐỀ
`list_customers()` chỉ lọc theo `name`. Khách đọc mã số thuế hoặc số điện thoại qua
điện thoại, nhân viên gõ vào ô tìm kiếm không ra gì, bấm "thêm vào sổ" — sinh khách
trùng ngay tại quầy. Không có chỉ mục nào trên `tax_code` nên kể cả khi mở rộng truy
vấn thì mỗi lần tìm vẫn quét toàn bảng.

VÌ SAO KHÔNG ĐẶT UNIQUE TRÊN tax_code — HAI LÝ DO, CẢ HAI ĐỀU CHẶN
1. Câu hỏi nghiệp vụ Q3 chưa chốt: "khách hàng" là PHÁP NHÂN hay ĐỊA ĐIỂM/NHÀ MÁY?
   Nếu là địa điểm thì ba nhà máy của cùng một công ty PHẢI trùng mã số thuế, và
   ràng buộc duy nhất là sai.
2. Dữ liệu hiện có chưa được kiểm. Đặt unique lên bảng đang có bản trùng thì
   migration THẤT BẠI GIỮA CHỪNG lúc deploy.

Nên migration này chỉ làm phần đúng trong mọi trường hợp: chỉ mục để tra nhanh, và
cảnh báo trùng ở tầng service (service không chặn — người dùng vẫn quyết). Ràng buộc
cứng chờ Q3 + một lượt dọn dữ liệu; câu kiểm:

    SELECT tax_code, count(*) FROM customers
     WHERE tax_code IS NOT NULL AND btrim(tax_code) <> '' AND deleted_at IS NULL
     GROUP BY 1 HAVING count(*) > 1;
"""
from alembic import op

revision: str = "1718870400043"
down_revision: str = "1718870400042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Chỉ mục TỪNG PHẦN: chỉ khách còn sống và có mã số thuế mới đáng đánh chỉ mục.
    op.execute(
        """
        CREATE INDEX ix_customers_tax_code ON customers (tax_code)
         WHERE tax_code IS NOT NULL AND deleted_at IS NULL;
        """
    )
    # Tra theo số điện thoại — khách hay đọc số qua điện thoại hơn là đọc tên đầy đủ.
    op.execute(
        """
        CREATE INDEX ix_customers_phone ON customers (phone)
         WHERE phone IS NOT NULL AND deleted_at IS NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_customers_phone;")
    op.execute("DROP INDEX IF EXISTS ix_customers_tax_code;")
