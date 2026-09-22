"""m49: hồ sơ nhân sự có PHÒNG CÔNG TÁC của riêng nó.

VẤN ĐỀ
Phòng ban của một hồ sơ nhân sự đang được đọc gián tiếp qua tài khoản:

    department_id = users.department_id  (join theo hr_profiles.user_id)

Từ m48, `user_id` là tuỳ chọn và phần lớn hồ sơ bỏ trống — 32/33 người trong
DANH SÁCH VIÊN CHỨC - NGƯỜI LAO ĐỘNG 2026 chưa có tài khoản. Hệ quả: màn hình nhân sự
hiển thị "Chưa có phòng" cho gần như cả Viện, và bộ lọc theo phòng trả về rỗng — trong
khi danh sách giấy của Viện xếp rành mạch từng người vào một trong 9 phòng nghiên cứu,
Ban Lãnh đạo hoặc Bộ phận văn phòng.

Không thể vá bằng cách tạo tài khoản cho đủ 32 người: m48 sinh ra chính là để tách
"người" khỏi "lối đăng nhập". Chỗ đúng để ghi phòng công tác là hồ sơ nhân sự.

CỘT MỚI, KHÔNG THAY CỘT CŨ
`users.department_id` vẫn giữ nguyên nghĩa: phòng ban dùng cho phân quyền theo phạm vi
(RBAC scope 'department'). Cột mới `hr_profiles.department_id` là dữ liệu NHÂN SỰ.
Hai thứ trùng nhau trong đa số trường hợp nhưng không phải một:

    users.department_id        → quyết định tài khoản này được thấy gì
    hr_profiles.department_id  → người này công tác ở phòng nào

Tầng dịch vụ ưu tiên cột mới, lùi về cột cũ khi cột mới trống, nên hồ sơ đã gắn tài
khoản từ trước không mất phòng ban sau migration này.

NULLABLE, ONDELETE RESTRICT
NULL = chưa xếp phòng, một trạng thái có thật (người mới, người đang chờ phân công).
RESTRICT vì xoá một phòng đang có người là chuyện phải xử lý bằng tay ở nghiệp vụ, chứ
không phải âm thầm gỡ phòng của cả chục hồ sơ.
"""
from alembic import op

revision: str = "1718870400048"
down_revision: str = "1718870400047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE hr_profiles ADD COLUMN IF NOT EXISTS department_id UUID;")
    op.execute(
        "ALTER TABLE hr_profiles ADD CONSTRAINT fk_hrp_department "
        "FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT;"
    )

    # Nạp sẵn từ tài khoản đã gắn: những hồ sơ này ĐANG hiển thị phòng ban nhờ join,
    # không backfill thì sau migration chúng trống cột mới và phải dựa vào đường lùi —
    # nạp thẳng để cột mới là nguồn duy nhất cho dữ liệu đã biết.
    op.execute(
        """
        UPDATE hr_profiles h SET department_id = u.department_id
          FROM users u
         WHERE u.id = h.user_id AND u.department_id IS NOT NULL;
        """
    )

    # Bộ lọc "nhân sự theo phòng" là truy vấn thường trực của màn hình danh sách.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_hrp_department ON hr_profiles (department_id);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_hrp_department;")
    op.execute("ALTER TABLE hr_profiles DROP CONSTRAINT IF EXISTS fk_hrp_department;")
    op.execute("ALTER TABLE hr_profiles DROP COLUMN IF EXISTS department_id;")
