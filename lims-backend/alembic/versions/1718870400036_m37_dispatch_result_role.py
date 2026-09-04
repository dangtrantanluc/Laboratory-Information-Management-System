"""m37: tách quyền GHI KẾT QUẢ khỏi quyền SỬA PHIẾU chuyển mẫu (BM 7.1/02).

VÌ SAO m36 PHẢI CẮT QUYỀN CỦA CẢ KHỐI LAB
------------------------------------------
m36 thu hồi `dispatch:update` của staff/lab_manager, và chính docstring của nó nêu
nguyên nhân: "Cả hai đi qua cùng một endpoint nên không tách được bằng quyền."

Yêu cầu nghiệp vụ khi đó — chỉ Phòng nhận mẫu được sửa NỘI DUNG HÀNH CHÍNH của
phiếu — là hợp lệ. Nhưng vì `PATCH /dispatches/{id}` gánh cả cột kết quả, cách duy
nhất để thực thi nó là cắt luôn quyền ghi kết quả của chính người làm phép thử.

Hậu quả: người thực hiện phép thử không phải người ghi kết quả, và `can_bo` tụt
xuống thành ô text do người khác gõ hộ — không truy về được tài khoản nào.
ISO/IEC 17025 §7.8.2 đòi kết quả phải truy xuất được tới người thực hiện.

MIGRATION NÀY KHÔNG HOÀN TÁC m36. Nó gỡ bỏ ràng buộc kỹ thuật đã buộc m36 phải
chọn giữa hai điều đáng lẽ không xung đột:

    dispatch:update  admin · leader · reception    → note, sample_name, quantity
    dispatch:result  admin · lab_manager · staff   → ket_qua, don_vi, phuong_phap, status

Phòng nhận mẫu VẪN độc quyền sửa nội dung hành chính của phiếu như m36 đã chốt;
khối lab lấy lại đúng phần việc của mình, không hơn.

`performed_by` thay vai trò của `can_bo`: điền TỰ ĐỘNG từ tài khoản đăng nhập,
KHÔNG nhận từ client, nên không ai gõ hộ tên người khác được. `can_bo` giữ nguyên
cột để phiếu cũ đọc lại được — cố ý KHÔNG backfill vì đó là text tự do, map ngược
sang user id chỉ tạo ra dữ liệu truy xuất giả.

⚠ TRIỂN KHAI — BẮT BUỘC XÓA CACHE RBAC SAU KHI CHẠY
`roles_permissions` được cache Redis TTL 300s, và `core/rbac.invalidate_role_cache()`
hiện KHÔNG được gọi ở bất kỳ đâu trong backend. Chạy migration xong mà không xóa
cache thì quyền mới chưa có hiệu lực, đồng thời quyền cũ vẫn tiếp tục được cấp
thêm tối đa 5 phút. Xem README §Triển khai.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "1718870400036"
down_revision: str = "1718870400035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Danh mục quyền TRƯỚC — roles_permissions có FK (resource, action) → permissions,
    #    chèn thẳng cặp chưa tồn tại sẽ nổ ForeignKeyViolation giữa chừng migration.
    op.execute(
        """
        INSERT INTO permissions (resource, action, description)
        VALUES ('dispatch', 'result',
                'Ghi kết quả thử nghiệm và trạng thái thực hiện trên phiếu chuyển mẫu')
        ON CONFLICT (resource, action) DO NOTHING;
        """
    )

    # 2) Cấp cho người THỰC HIỆN phép thử. Scope 'department': khối lab chỉ ghi được
    #    kết quả của lượt chuyển tới phòng mình (service đã enforce, đây là khai báo
    #    để /auth/me trả đúng phạm vi cho frontend).
    op.execute(
        """
        INSERT INTO roles_permissions (role, resource, action, scope)
        VALUES ('staff',       'dispatch', 'result', 'department'),
               ('lab_manager', 'dispatch', 'result', 'department'),
               ('admin',       'dispatch', 'result', 'all')
        ON CONFLICT (role, resource, action) DO NOTHING;
        """
    )

    # 3) Danh tính người thực hiện — KHÔNG nhận từ client, service gán từ token.
    #    ondelete RESTRICT: đã ký tên vào kết quả thì không xoá tài khoản để mất vết.
    op.add_column(
        "sample_dispatches",
        sa.Column("performed_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "sample_dispatches",
        sa.Column("performed_at", sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_dispatch_performed_by", "sample_dispatches", "users",
        ["performed_by"], ["id"], ondelete="RESTRICT",
    )
    op.create_index(
        "ix_sample_dispatches_performed_by", "sample_dispatches", ["performed_by"]
    )


def downgrade() -> None:
    op.drop_index("ix_sample_dispatches_performed_by", table_name="sample_dispatches")
    op.drop_constraint("fk_dispatch_performed_by", "sample_dispatches", type_="foreignkey")
    op.drop_column("sample_dispatches", "performed_at")
    op.drop_column("sample_dispatches", "performed_by")
    op.execute(
        """
        DELETE FROM roles_permissions
        WHERE resource = 'dispatch' AND action = 'result';
        """
    )
    op.execute(
        "DELETE FROM permissions WHERE resource = 'dispatch' AND action = 'result';"
    )
