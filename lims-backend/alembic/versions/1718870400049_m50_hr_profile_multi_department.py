"""m50: một người công tác ở NHIỀU phòng (kiêm nhiệm).

VẤN ĐỀ VỚI m49
m49 vừa cho hồ sơ nhân sự một cột `department_id`. Cột đơn phát biểu "mỗi người thuộc
đúng một phòng" — và DANH SÁCH VIÊN CHỨC 2026 bác bỏ điều đó ngay ở dòng đầu tiên:

    * Ban Lãnh đạo              → 1. Huỳnh Văn Biết
    I. Phòng NC Sinh học Phân tử → 1. Huỳnh Văn Biết

33 dòng người, 32 người khác nhau. Với cột đơn, đợt nhập buộc phải chọn một mục và vứt
mục kia: bỏ Ban Lãnh đạo thì mất chức trách quản lý, bỏ phòng nghiên cứu thì ông biến
mất khỏi thống kê chuyên môn của phòng. Cả hai lựa chọn đều làm sai dữ liệu gốc.

BẢNG NỐI, KHÔNG PHẢI THÊM CỘT
`hr_profile_departments(profile_id, department_id, is_primary)`. Kiêm nhiệm là quan hệ
nhiều-nhiều; thêm `department_id_2` là cách vá chỉ đúng tới người kiêm nhiệm thứ ba.

VÌ SAO GIỮ `is_primary`
Vài chỗ chỉ chứa được MỘT phòng — tiêu đề hồ sơ, và nhất là báo cáo đếm đầu người theo
phòng: tổng các phòng phải bằng sĩ số Viện, nếu đếm mọi dòng kiêm nhiệm thì người kiêm
nhiệm bị tính hai lần và tổng vượt sĩ số. `is_primary` trả lời "nếu chỉ được kể một
phòng thì kể phòng nào". Chỉ mục riêng phần bảo đảm tối đa MỘT phòng chính mỗi hồ sơ.

GỠ CỘT CŨ, KHÔNG GIỮ SONG SONG
`hr_profiles.department_id` bị gỡ sau khi nạp sang bảng nối. Giữ cả hai nghĩa là hai
nguồn sự thật cho cùng một câu hỏi, và chúng sẽ lệch nhau — phòng chính đọc được từ
bảng nối, không cần bản sao.

AN TOÀN DỮ LIỆU
Nạp trước, gỡ sau, trong cùng một migration: mọi giá trị của m49 thành một dòng
is_primary=true ở bảng mới. Downgrade dựng lại cột và chép phòng chính ngược về — chỉ
mất các dòng KIÊM NHIỆM, vì lược đồ cũ không chứa được chúng; ghi rõ ở đây theo
CONTRIBUTING §5.
"""
from alembic import op

revision: str = "1718870400049"
down_revision: str = "1718870400048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hr_profile_departments (
            profile_id    UUID NOT NULL REFERENCES hr_profiles(id) ON DELETE CASCADE,
            department_id UUID NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
            is_primary    BOOLEAN NOT NULL DEFAULT false,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (profile_id, department_id)
        );
        """
    )

    # Tối đa MỘT phòng chính mỗi hồ sơ. Ràng buộc riêng phần chứ không phải UNIQUE
    # thường: hồ sơ được phép có nhiều dòng kiêm nhiệm (is_primary = false).
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hrpd_primary
            ON hr_profile_departments (profile_id) WHERE is_primary;
        """
    )
    # Lọc "ai thuộc phòng X" quét theo chiều ngược với khoá chính.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_hrpd_department "
        "ON hr_profile_departments (department_id);"
    )

    # Nạp từ cột đơn của m49 — mỗi giá trị thành phòng CHÍNH.
    op.execute(
        """
        INSERT INTO hr_profile_departments (profile_id, department_id, is_primary)
        SELECT id, department_id, true FROM hr_profiles WHERE department_id IS NOT NULL
        ON CONFLICT (profile_id, department_id) DO NOTHING;
        """
    )

    op.execute("DROP INDEX IF EXISTS idx_hrp_department;")
    op.execute("ALTER TABLE hr_profiles DROP CONSTRAINT IF EXISTS fk_hrp_department;")
    op.execute("ALTER TABLE hr_profiles DROP COLUMN IF EXISTS department_id;")


def downgrade() -> None:
    # MẤT DỮ LIỆU: lược đồ cũ chứa được đúng một phòng mỗi hồ sơ, nên mọi dòng kiêm
    # nhiệm (is_primary = false) biến mất. Chỉ phòng chính được chép ngược.
    op.execute("ALTER TABLE hr_profiles ADD COLUMN IF NOT EXISTS department_id UUID;")
    op.execute(
        "ALTER TABLE hr_profiles ADD CONSTRAINT fk_hrp_department "
        "FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT;"
    )
    op.execute(
        """
        UPDATE hr_profiles h SET department_id = pd.department_id
          FROM hr_profile_departments pd
         WHERE pd.profile_id = h.id AND pd.is_primary;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_hrp_department ON hr_profiles (department_id);"
    )
    op.execute("DROP TABLE IF EXISTS hr_profile_departments;")
