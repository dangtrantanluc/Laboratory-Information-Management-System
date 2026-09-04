"""m42: ghi nhận TÌNH TRẠNG MẪU và bước CHẤP NHẬN / TỪ CHỐI tại quầy.

VẤN ĐỀ
Form nhận mẫu không có ô nào cho tình trạng mẫu, số lượng mẫu, bao bì hay nhiệt độ
bảo quản — đúng những việc đầu tiên nhân viên quầy làm với mẫu vật lý. Cột
`condition_status`/`condition_note` CÓ tồn tại, nhưng ở bảng `samples` của module M1
mà quầy không chạm tới. `quantity` chỉ có ở dòng chuyển lab, tức là số phép thử chứ
không phải số lượng mẫu nhận.

Trạng thái phiếu cũng chỉ có 'cancelled', và lý do là tuỳ chọn. Về nghiệp vụ "huỷ
phiếu" khác hẳn "từ chối tiếp nhận vì mẫu không đạt": cái đầu là thao tác hành chính,
cái sau là một QUYẾT ĐỊNH KỸ THUẬT phải ghi rõ ai quyết, lúc nào, vì sao.

ISO/IEC 17025 §7.4.2–7.4.3 đòi ghi nhận sai lệch điều kiện mẫu, và bảo lưu trách
nhiệm khi vẫn nhận mẫu không đạt.

HAI ĐƯỜNG XỬ LÝ, KHÔNG PHẢI MỘT
Câu hỏi nghiệp vụ Q6 ("từ chối hẳn, hay nhận có bảo lưu?") chưa được chốt, nên
migration này KHÔNG chọn thay: nó mở cả hai đường, vì hai đường này vốn cùng tồn tại
trong thực tế phòng thử nghiệm.

  · nhận có bảo lưu → condition_status='not_acceptable' + condition_note, phiếu chạy tiếp
  · từ chối hẳn     → status='rejected' + rejected_reason + decided_by/decided_at

CHECK ép lý do đi kèm quyết định, sao khuôn `ck_smp_condition` mà models/sample.py đã
dùng: một quyết định từ chối không có lý do thì hồ sơ không giải trình được.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "1718870400041"
down_revision: str = "1718870400040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sample_intakes", sa.Column("sample_count", sa.Integer(), nullable=True))
    op.add_column(
        "sample_intakes", sa.Column("condition_status", sa.String(16), nullable=True)
    )
    op.add_column("sample_intakes", sa.Column("condition_note", sa.Text(), nullable=True))
    op.add_column("sample_intakes", sa.Column("rejected_reason", sa.Text(), nullable=True))
    op.add_column(
        "sample_intakes",
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "sample_intakes",
        sa.Column("decided_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_intake_decided_by", "sample_intakes", "users",
        ["decided_by"], ["id"], ondelete="RESTRICT",
    )

    # 'rejected' vào CHECK trạng thái (m28 đã thay CHECK gốc của m16).
    op.drop_constraint("ck_intake_status", "sample_intakes", type_="check")
    op.create_check_constraint(
        "ck_intake_status", "sample_intakes",
        "status IN ('received','quoted','quote_accepted','paid',"
        "'dispatched','completed','cancelled','rejected')",
    )
    op.create_check_constraint(
        "ck_intake_condition", "sample_intakes",
        "condition_status IS NULL OR condition_status IN ('acceptable','not_acceptable')",
    )
    # Mẫu không đạt thì PHẢI mô tả sai lệch — cùng khuôn ck_smp_condition của M1.
    op.create_check_constraint(
        "ck_intake_condition_note", "sample_intakes",
        "condition_status IS DISTINCT FROM 'not_acceptable' "
        "OR (condition_note IS NOT NULL AND length(btrim(condition_note)) > 0)",
    )
    # Từ chối thì PHẢI có lý do — quyết định kỹ thuật không giải trình được là vô giá trị.
    op.create_check_constraint(
        "ck_intake_rejected_reason", "sample_intakes",
        "status <> 'rejected' "
        "OR (rejected_reason IS NOT NULL AND length(btrim(rejected_reason)) > 0)",
    )
    op.create_check_constraint(
        "ck_intake_sample_count", "sample_intakes",
        "sample_count IS NULL OR sample_count >= 1",
    )


def downgrade() -> None:
    for name in (
        "ck_intake_sample_count", "ck_intake_rejected_reason",
        "ck_intake_condition_note", "ck_intake_condition",
    ):
        op.drop_constraint(name, "sample_intakes", type_="check")
    op.drop_constraint("ck_intake_status", "sample_intakes", type_="check")
    op.execute("UPDATE sample_intakes SET status = 'cancelled' WHERE status = 'rejected';")
    op.create_check_constraint(
        "ck_intake_status", "sample_intakes",
        "status IN ('received','quoted','quote_accepted','paid',"
        "'dispatched','completed','cancelled')",
    )
    op.drop_constraint("fk_intake_decided_by", "sample_intakes", type_="foreignkey")
    for col in (
        "decided_at", "decided_by", "rejected_reason",
        "condition_note", "condition_status", "sample_count",
    ):
        op.drop_column("sample_intakes", col)
