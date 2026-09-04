"""m38: tách CHỈ TIÊU KHÁCH ĐẶT khỏi PHIẾU GIAO VIỆC cho phòng lab.

VẤN ĐỀ
------
`sample_dispatches` đang gánh hai khái niệm khác nhau cùng lúc:

  · "chỉ tiêu khách đặt"      — dùng để báo giá, tính tiền
  · "phiếu giao việc cho lab" — dùng để theo dõi thực hiện

Vì gộp làm một nên `quotation_service.create_from_intake()` buộc phải từ chối khi
phiếu chưa có dispatch ("hãy phân chỉ tiêu trước khi lập báo giá") — mà tạo dispatch
lại đẩy phiếu thẳng sang 'dispatched' và bắn thông báo cho phòng lab.

Hệ quả: muốn báo giá thì phải giao việc cho lab trước, nên ba trạng thái
`quoted → quote_accepted → paid` mà m28 thiết kế là mã chết trên đường đi tự nhiên.
Giao diện vẫn vẽ thanh tiến trình 6 bước nhưng thực tế chỉ đi được 2.

CÁCH TÁCH
---------
`intake_items` = khách đặt gì (nguồn cho báo giá).
`sample_dispatches.intake_item_id` = việc này thực hiện cho dòng đặt hàng nào.

Quan hệ 1–n: một chỉ tiêu đặt có thể giao cho nhiều phòng lab, hoặc chưa giao cho
phòng nào (đã báo giá, khách chưa đồng ý). Đó chính là thứ mô hình cũ không diễn
tả được.

BACKFILL
--------
Mỗi dòng `sample_dispatches` hiện có sinh ĐÚNG MỘT `intake_items` tương ứng rồi
trỏ ngược lại — ánh xạ 1–1, không gộp các chỉ tiêu trùng tên. Gộp sẽ làm số dòng
và tổng tiền của báo giá đã lập lệch so với trước khi migrate, và không có cách
nào hoàn tác chính xác.

Cột tạm `_src_dispatch_id` tồn tại trong đúng transaction này: INSERT không trả về
được cặp (id mới, dispatch nguồn) nếu không mang khoá nguồn theo.

⚠ CÓ BACKFILL DỮ LIỆU — diễn tập trên bản sao production trước khi chạy thật, và
kiểm `SELECT count(*) FROM sample_dispatches WHERE intake_item_id IS NULL` = 0 sau
khi chạy.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "1718870400037"
down_revision: str = "1718870400036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intake_items",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "intake_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sample_intakes.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "test_parameter_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("test_parameters.id", ondelete="SET NULL"), nullable=True,
        ),
        # Chụp GIÁ TRỊ từ danh mục tại thời điểm đặt: bảng giá đổi về sau không được
        # làm lệch báo giá đã gửi khách. Cùng nguyên tắc snapshot của sample_intakes.
        sa.Column("parameter_name", sa.String(500), nullable=False),
        sa.Column("method", sa.String(500), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("sample_name", sa.String(500), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", postgresql.TIMESTAMP(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("quantity >= 1", name="ck_ii_quantity"),
        sa.CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_ii_price_nonneg"),
    )
    op.create_index("ix_intake_items_intake", "intake_items", ["intake_id"])

    op.add_column(
        "sample_dispatches",
        sa.Column("intake_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_dispatch_intake_item", "sample_dispatches", "intake_items",
        ["intake_item_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(
        "ix_sample_dispatches_item", "sample_dispatches", ["intake_item_id"]
    )

    # ===== BACKFILL: mỗi dispatch cũ → 1 dòng đặt hàng tương ứng =====
    op.add_column(
        "intake_items",
        sa.Column("_src_dispatch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        """
        INSERT INTO intake_items (
            intake_id, sort_order, test_parameter_id, parameter_name, method, unit,
            sample_name, quantity, unit_price, created_at, updated_at, _src_dispatch_id
        )
        SELECT
            d.intake_id,
            (row_number() OVER (PARTITION BY d.intake_id ORDER BY d.dispatched_at, d.id))::int - 1,
            d.test_parameter_id,
            d.chi_tieu,
            d.phuong_phap,
            d.don_vi,
            d.sample_name,
            GREATEST(COALESCE(d.quantity, 1), 1),
            d.unit_price,
            d.dispatched_at,
            d.dispatched_at,
            d.id
        FROM sample_dispatches d;
        """
    )
    op.execute(
        """
        UPDATE sample_dispatches d
           SET intake_item_id = i.id
          FROM intake_items i
         WHERE i._src_dispatch_id = d.id;
        """
    )
    op.drop_column("intake_items", "_src_dispatch_id")


def downgrade() -> None:
    # Dữ liệu trong intake_items đều suy được từ sample_dispatches (backfill 1–1),
    # nên gỡ bảng không mất thông tin của phiếu chuyển. Dòng đặt hàng CHƯA giao lab
    # thì không có bản sao ở đâu — đó là mất mát chấp nhận được khi lùi phiên bản,
    # và là lý do phải chốt kỹ trước khi chạy upgrade trên production.
    op.drop_index("ix_sample_dispatches_item", table_name="sample_dispatches")
    op.drop_constraint("fk_dispatch_intake_item", "sample_dispatches", type_="foreignkey")
    op.drop_column("sample_dispatches", "intake_item_id")
    op.drop_index("ix_intake_items_intake", table_name="intake_items")
    op.drop_table("intake_items")
