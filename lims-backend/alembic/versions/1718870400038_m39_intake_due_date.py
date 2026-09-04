"""m39: ngày hẹn trả kết quả thành KIỂU NGÀY, để tính được "quá hạn".

VẤN ĐỀ
`sample_intakes.due_date` là VARCHAR(30) nhập tự do (giao diện gợi ý "dd/mm/yyyy"
nhưng không ép). Không so sánh được với hôm nay, nên không có KPI "mẫu quá hạn trả
kết quả" nào tính được từ luồng nhận mẫu — trong khi dashboard vẫn hiển thị ô đó,
lấy số từ bảng `samples` của module M1 mà quầy nhận mẫu không ghi vào.

CÁCH LÀM
Thêm cột `due_date_at DATE` song song, KHÔNG xoá `due_date`. Hai lý do:
1. `due_date` là bản chụp đúng thứ nhân viên đã gõ và đã in ra phiếu. Ghi đè nó
   bằng giá trị chuẩn hoá là sửa hồ sơ đã phát hành.
2. Có dòng không phân giải được ("cuối tháng 3", "sau Tết"). Ép kiểu tại chỗ sẽ
   làm mất chúng; để song song thì `due_date_at` NULL và ô gốc vẫn đọc được.

BACKFILL
Chỉ đụng dòng khớp CHÍNH XÁC một trong hai khuôn dạng. Regex đứng trước để `to_date`
không bao giờ nhận chuỗi rác — `to_date` của Postgres rất dễ dãi, '99/99/9999' cũng
ra một ngày nào đó thay vì báo lỗi, và một ngày sai âm thầm còn tệ hơn NULL.

Sau khi chạy, kiểm số dòng chưa phân giải được để xử lý tay:
    SELECT code, due_date FROM sample_intakes
     WHERE due_date IS NOT NULL AND btrim(due_date) <> '' AND due_date_at IS NULL;
"""
import sqlalchemy as sa
from alembic import op

revision: str = "1718870400038"
down_revision: str = "1718870400037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sample_intakes", sa.Column("due_date_at", sa.Date(), nullable=True))

    # dd/mm/yyyy — khuôn dạng giao diện gợi ý, chiếm đa số dữ liệu hiện có.
    op.execute(
        r"""
        UPDATE sample_intakes
           SET due_date_at = to_date(btrim(due_date), 'DD/MM/YYYY')
         WHERE due_date ~ '^\s*\d{1,2}/\d{1,2}/\d{4}\s*$';
        """
    )
    # yyyy-mm-dd — người dùng dán từ ô <input type="date"> của trình duyệt.
    op.execute(
        r"""
        UPDATE sample_intakes
           SET due_date_at = btrim(due_date)::date
         WHERE due_date_at IS NULL
           AND due_date ~ '^\s*\d{4}-\d{2}-\d{2}\s*$';
        """
    )

    # Chỉ mục từng phần: KPI "quá hạn" luôn kèm điều kiện NOT NULL, và phần lớn
    # phiếu cũ sẽ có cột này rỗng.
    op.execute(
        """
        CREATE INDEX ix_sample_intakes_due_date_at
            ON sample_intakes (due_date_at)
         WHERE due_date_at IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_sample_intakes_due_date_at;")
    op.drop_column("sample_intakes", "due_date_at")
