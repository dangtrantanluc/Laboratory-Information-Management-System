"""m41: báo giá đã gửi khách trở thành chứng từ — có phiên bản, không xoá cứng.

BA LỖ HỔNG ĐƯỢC BỊT
1. `update_quotation()` chỉ khoá khi trạng thái là 'accepted'. Một báo giá đã ở
   'sent' — tức là ĐÃ GỬI CHO KHÁCH — vẫn sửa được đơn giá, số lượng, danh sách chỉ
   tiêu và cả thông tin khách hàng, không để lại bản cũ. Nhật ký chỉ ghi `code` và
   `total`, không ghi nội dung, nên không tái dựng được thứ khách đã nhận.
2. `delete_quotation()` dùng `db.delete()` — XOÁ CỨNG, cascade luôn các dòng chi
   tiết. Chứng từ thương mại biến mất khỏi hệ thống.
3. `valid_until` qua rồi báo giá vẫn nằm ở 'sent'; trạng thái 'expired' chỉ đổi được
   bằng tay, nên trên thực tế không ai đổi.

CÁCH LÀM
- `deleted_at`  → xoá mềm. Bản ghi ở lại, biến mất khỏi danh sách.
- `version`     → số phiên bản hiện hành của báo giá.
- `quotation_versions` → BẢN CHỤP TOÀN VĂN (JSONB) của phiên bản trước mỗi lần sửa
  sau khi đã rời 'draft'. Chụp cả dòng chi tiết, vì thứ khách nhận là cả bảng giá
  chứ không riêng phần đầu.

Vì sao chụp JSONB thay vì dựng bảng dòng-phiên-bản: bản chụp chỉ để ĐỌC LẠI nguyên
trạng khi có tranh chấp, không bao giờ join hay tổng hợp. Dựng schema chuẩn hoá cho
dữ liệu chỉ-đọc-nguyên-khối là chi phí không đổi lấy được gì.

KHÔNG backfill: báo giá hiện có chưa từng qua cơ chế này nên `version` = 1 và không
có bản chụp nào — đúng sự thật, hơn là dựng lịch sử giả.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "1718870400040"
down_revision: str = "1718870400039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quotations",
        sa.Column("deleted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "quotations",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.execute(
        """
        CREATE INDEX ix_quotations_active ON quotations (created_at DESC)
         WHERE deleted_at IS NULL;
        """
    )

    op.create_table(
        "quotation_versions",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "quotation_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        # Toàn văn báo giá tại thời điểm đó, gồm cả các dòng chi tiết.
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("quotation_id", "version", name="uq_qv_quotation_version"),
        sa.CheckConstraint("version >= 1", name="ck_qv_version"),
    )
    op.create_index("ix_quotation_versions_quotation", "quotation_versions", ["quotation_id"])


def downgrade() -> None:
    op.drop_index("ix_quotation_versions_quotation", table_name="quotation_versions")
    op.drop_table("quotation_versions")
    op.execute("DROP INDEX IF EXISTS ix_quotations_active;")
    op.drop_column("quotations", "version")
    op.drop_column("quotations", "deleted_at")
