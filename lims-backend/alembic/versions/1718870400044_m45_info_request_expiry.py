"""m45: quyền xem thông tin khách hàng có THỜI HẠN.

VẤN ĐỀ
Theo thiết kế m26, một KTV xin xem thông tin khách của MỘT phiếu, được duyệt, thì
TOÀN BỘ PHÒNG đó có quyền xem VĨNH VIỄN — không hết hạn, không thu hồi được, không
có endpoint huỷ. Với dữ liệu định danh khách hàng, cấp quyền không thời hạn cho một
đơn vị tổ chức là mức kiểm soát yếu: người xin đã chuyển việc từ lâu mà quyền vẫn còn.

CÁCH LÀM
`expires_at` NULL = vĩnh viễn (giữ nguyên hành vi cho mọi bản ghi CŨ — không thu hồi
hồi tố quyền ai đó đang dùng). Bản duyệt MỚI mặc định 90 ngày; người duyệt đặt khác
được. `revoked_at` cho phép thu hồi sớm khi cần.

KHÔNG backfill `expires_at` cho bản cũ: đặt hạn hồi tố sẽ cắt quyền của những phòng
đang làm dở giữa chừng, mà không ai được báo trước. Hạn chỉ áp cho quyền cấp từ đây.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "1718870400044"
down_revision: str = "1718870400043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customer_info_requests",
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "customer_info_requests",
        sa.Column("revoked_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "customer_info_requests",
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_cir_revoked_by", "customer_info_requests", "users",
        ["revoked_by"], ["id"], ondelete="SET NULL",
    )
    # Tra quyền chạy trên mọi lần đọc phiếu của khối lab — cần chỉ mục.
    op.execute(
        """
        CREATE INDEX ix_cir_active_grant
            ON customer_info_requests (intake_id, department_id)
         WHERE status = 'approved' AND revoked_at IS NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cir_active_grant;")
    op.drop_constraint("fk_cir_revoked_by", "customer_info_requests", type_="foreignkey")
    op.drop_column("customer_info_requests", "revoked_by")
    op.drop_column("customer_info_requests", "revoked_at")
    op.drop_column("customer_info_requests", "expires_at")
