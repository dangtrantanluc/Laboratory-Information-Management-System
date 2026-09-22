"""m47: dọn danh mục "Chỉ số" — trả nó về đúng nghĩa xếp hạng tạp chí.

VẤN ĐỀ
Danh mục `publication_categories` (hiển thị là "Chỉ số") đang trộn BA khái niệm khác
nhau vào một danh sách chọn:

    isi_q1 · isi_q2 · isi_q3 · isi_q4 · scopus   ← xếp hạng tạp chí  (đúng nghĩa)
    domestic                                     ← PHẠM VI công bố
    conference                                   ← LOẠI công bố

Hậu quả: cùng một sự thật "bài báo này trong nước hay quốc tế" được lưu ở HAI chỗ —
`publications.category` và `publications.pub_scope` — mà không có ràng buộc nào ép
chúng khớp. Dữ liệu hiện tại khớp, nhưng vì người nhập cẩn thận chứ không vì hệ thống.
Không gì ngăn một bản ghi có `category='isi_q1'` đi cùng `pub_scope='domestic'`, và khi
đó màn hình "Công bố khoa học" tách theo trường nào sẽ ra hai kết quả khác nhau mà
không ai biết bên nào đúng.

Đây là điều kiện tiên quyết của m47 (tách công bố khoa học / sáng chế): hai màn hình
mới lọc theo `pub_scope`, nên `pub_scope` phải là nguồn chân lý duy nhất.

CÁCH LÀM — VÔ HIỆU HOÁ, KHÔNG XOÁ
`publications.category` có khoá ngoại tới đây với ON DELETE RESTRICT, và các bản ghi cũ
vẫn cần đọc lại được. `hr_catalog_service._list()` đã lọc `is_active = true`, nên đặt cờ
là đủ để hai mục biến khỏi ô chọn mà bản ghi lịch sử không hỏng.

KHÔNG MẤT THÔNG TIN
Thứ tự bắt buộc: điền `pub_scope` TRƯỚC rồi mới xoá `category`. Làm ngược lại thì bản
ghi nào có category='domestic' mà pub_scope trống sẽ mất luôn thông tin phạm vi.
"""
from alembic import op

revision: str = "1718870400046"
down_revision: str = "1718870400045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) CỨU THÔNG TIN TRƯỚC — 'domestic' trong ô Chỉ số vốn có nghĩa là phạm vi.
    op.execute(
        """
        UPDATE publications
           SET pub_scope = 'domestic'
         WHERE category = 'domestic' AND pub_scope IS NULL;
        """
    )
    # Bản ghi mang category='conference' thì loại của nó vốn đã phải là 'conference';
    # chỉ điền cho bản ghi nào bị bỏ sót, không đổi loại của bản ghi đã đúng.
    op.execute(
        """
        UPDATE publications
           SET type = 'conference'
         WHERE category = 'conference' AND type = 'paper';
        """
    )

    # 2) Giờ mới gỡ giá trị khỏi ô Chỉ số — nó không phải chỉ số.
    op.execute(
        "UPDATE publications SET category = NULL WHERE category IN ('domestic', 'conference');"
    )

    # 3) Ẩn khỏi ô chọn. Hàng vẫn còn: khoá ngoại và hồ sơ cũ không hỏng.
    op.execute(
        """
        UPDATE publication_categories
           SET is_active = false
         WHERE code IN ('domestic', 'conference');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE publication_categories
           SET is_active = true
         WHERE code IN ('domestic', 'conference');
        """
    )
    # Khôi phục gần đúng: bài báo trong nước không có xếp hạng nào khác thì trước m47
    # chính là bản ghi mang category='domestic'. Không khôi phục 'conference' vì loại
    # của bản ghi (`type`) đã mang đủ thông tin đó.
    op.execute(
        """
        UPDATE publications
           SET category = 'domestic'
         WHERE type = 'paper' AND pub_scope = 'domestic' AND category IS NULL;
        """
    )
