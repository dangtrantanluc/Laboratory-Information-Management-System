"""m40: nối phiếu chuyển mẫu vào cơ chế DUYỆT KẾT QUẢ bất biến của M1.

VẤN ĐỀ
`sample_dispatches.ket_qua` là một cột Text sửa tự do: không phiên bản, không người
duyệt, không lý do sửa. Kết quả đã trả cho khách vẫn viết đè được và chỉ để lại một
dòng nhật ký ghi giá trị MỚI — không tái dựng được nội dung đã phát hành.

Trong khi đó module M1 đã có sẵn đúng cơ chế cần thiết, và làm đúng:
  · sample_results.version + is_current      → phiên bản, bản cũ giữ nguyên
  · ck_res_revision_reason                   → sửa sau khi duyệt BẮT BUỘC có lý do
  · ck_res_approval_pair                     → approved_by và approved_at đi cùng nhau
  · result_service: SELF_APPROVAL_FORBIDDEN  → người duyệt ≠ người nhập

Migration này KHÔNG xây lại cơ chế đó. Nó bắc cầu để luồng nhận mẫu dùng chính nó:

    sample_intakes  ──test_request_id──▶  test_requests
    sample_dispatches ──assignment_id──▶  sample_assignments ──▶ sample_results

Bản ghi M1 được tạo LƯỜI (lazy): chỉ sinh khi phòng lab lần đầu gửi kết quả đi
duyệt. Phiếu chưa có kết quả thì không sinh rác vào bảng `samples`.

MỘT `Sample` CHO MỖI (PHIẾU × PHÒNG LAB), không phải mỗi chỉ tiêu: nhiều chỉ tiêu
của cùng một phiếu gửi tới cùng một phòng là CÙNG MỘT mẫu vật lý. Mỗi chỉ tiêu là
một `sample_assignments` (phần việc) — đúng ngữ nghĩa mà M1 đã định nghĩa.

HẠN TRẢ (samples.deadline_at là NOT NULL, CHECK deadline_at > received_at) lấy theo
thứ tự: `sample_intakes.due_date_at` (m39) → `test_parameters.turnaround_days` của
chỉ tiêu. Cả hai đều là số liệu nghiệp vụ có thật; KHÔNG bịa một mặc định, vì hạn
sai sẽ chảy thẳng vào KPI "mẫu quá hạn" và làm số liệu điều hành sai lệch. Không có
nguồn nào thì service từ chối và yêu cầu điền ngày hẹn trả.

KHÔNG bỏ cột `ket_qua`: nó vẫn là ô hiển thị nhanh trên BM 7.1/02 và giữ dữ liệu
phiếu cũ. Từ m40 nó được đồng bộ TỪ phiên bản kết quả hiện hành, không còn là nguồn.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "1718870400039"
down_revision: str = "1718870400038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sample_intakes",
        sa.Column("test_request_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_intake_test_request", "sample_intakes", "test_requests",
        ["test_request_id"], ["id"], ondelete="SET NULL",
    )

    op.add_column(
        "sample_dispatches",
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_dispatch_assignment", "sample_dispatches", "sample_assignments",
        ["assignment_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(
        "ix_sample_dispatches_assignment", "sample_dispatches", ["assignment_id"]
    )

    # KHÔNG backfill. Phiếu cũ giữ nguyên `ket_qua` như một giá trị lịch sử; dựng
    # phiên bản kết quả giả cho chúng sẽ tạo ra hồ sơ "đã duyệt" mà thực tế chưa ai
    # duyệt — tệ hơn nhiều so với việc thừa nhận dữ liệu cũ không có bước duyệt.


def downgrade() -> None:
    op.drop_index("ix_sample_dispatches_assignment", table_name="sample_dispatches")
    op.drop_constraint("fk_dispatch_assignment", "sample_dispatches", type_="foreignkey")
    op.drop_column("sample_dispatches", "assignment_id")
    op.drop_constraint("fk_intake_test_request", "sample_intakes", type_="foreignkey")
    op.drop_column("sample_intakes", "test_request_id")
