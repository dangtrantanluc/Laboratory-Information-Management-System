"""m52: thêm "Được Hội đồng Giáo sư Nhà nước công nhận" vào danh mục Chỉ số.

VẤN ĐỀ
Ô "Chỉ số" của form công bố khoa học chỉ có ISI Q1–Q4 và Scopus — toàn bộ là xếp hạng
QUỐC TẾ. Một bài đăng trên tạp chí trong nước vì thế không có gì để chọn, và ô hint đang
phải nói "tạp chí trong nước không có xếp hạng thì để trống".

Nhưng tạp chí trong nước CÓ một mức công nhận, và đó là mức duy nhất được dùng khi xét
chức danh giáo sư / phó giáo sư: nằm trong danh mục được Hội đồng Giáo sư Nhà nước tính
điểm. Không ghi được điều đó nghĩa là mỗi lần Viện làm hồ sơ xét chức danh lại phải tra
tay từng bài xem tạp chí có trong danh mục hay không.

VÌ SAO Ở ĐÂY CHỨ KHÔNG PHẢI MỘT Ô TÍCH RIÊNG
Đây là một mức XẾP HẠNG của tạp chí, cùng loại với ISI và Scopus — nên nó thuộc về cùng
một ô chọn. Cụm ô tích bên dưới là "Chỉ mục quốc tế" (SCIE/SSCI/Scopus/ACI); HĐGSNN là
công nhận trong nước nên đặt vào đó sẽ sai nghĩa ngay ở nhãn.

KHÔNG ĐỤNG DỮ LIỆU CŨ
Chỉ thêm một dòng danh mục. Bản ghi đang có giữ nguyên `category` của chúng; không bản
ghi nào bị tự động gán mức này, vì "tạp chí này có trong danh mục HĐGSNN hay không" là
việc người nhập phải tra, hệ thống không suy ra được từ tên tạp chí.
"""
from alembic import op

revision: str = "1718870400051"
down_revision: str = "1718870400050"
branch_labels = None
depends_on = None

_CODE = "hdgsnn"


def upgrade() -> None:
    # sort_order 6: ngay sau Scopus (5), trước hai mục đã bị m47 vô hiệu hoá (6, 7).
    # Trùng số với 'domestic' là chấp nhận được vì hai lẽ: mục đó is_active = false nên
    # không bao giờ cùng xuất hiện trong danh sách chọn, và hr_catalog_service sắp xếp
    # theo (sort_order, code) — có sẵn tiêu chí phá hoà, danh sách không tự đảo thứ tự
    # giữa hai lần gọi.
    op.execute(
        f"""
        INSERT INTO publication_categories (code, label, sort_order, is_active)
        VALUES ('{_CODE}', 'Được Hội đồng Giáo sư Nhà nước công nhận', 6, true)
        ON CONFLICT (code) DO UPDATE
           SET label = EXCLUDED.label,
               sort_order = EXCLUDED.sort_order,
               is_active = true;
        """
    )


def downgrade() -> None:
    # `publications.category` tham chiếu tới đây với ON DELETE RESTRICT: xoá thẳng sẽ
    # đổ vỡ nếu đã có bản ghi dùng mức này. Vô hiệu hoá là cách lùi an toàn và giữ
    # nguyên dữ liệu đã nhập — cùng cách m47 đã xử lý 'domestic' / 'conference'.
    op.execute(
        f"UPDATE publication_categories SET is_active = false WHERE code = '{_CODE}';"
    )
