"""m36: siết quyền sửa phiếu chuyển mẫu (BM 7.1/02) về admin + leader + reception.

TRƯỚC:  dispatch:update = admin, lab_manager, reception, staff
SAU:    dispatch:update = admin, leader, reception

Yêu cầu nghiệp vụ: chỉ Ban lãnh đạo, Phòng nhận mẫu và Quản trị viên được sửa nội
dung phiếu chuyển mẫu — TOÀN BỘ phiếu, gồm cả cột kết quả.

HỆ QUẢ PHẢI BIẾT TRƯỚC (đã xác nhận với nghiệp vụ):
  - KTV (staff) và Trưởng phòng lab (lab_manager) KHÔNG còn ghi được `ket_qua`,
    `don_vi`, `can_bo` lên phiếu, và KHÔNG còn đổi được trạng thái lượt chuyển
    (sent → received → in_progress → done). Cả hai đi qua cùng một endpoint
    PATCH /dispatches/{id} nên không tách được bằng quyền.
  - Hai vai trò này VẪN đọc được phiếu: `intake:read` không đổi.
  - Kết quả thử nghiệm từ nay do Phòng nhận mẫu / lãnh đạo nhập hộ, hoặc lab báo
    qua kênh khác rồi Phòng nhận mẫu ghi vào.

KHÔNG cấp cho office: office không có `intake:read` nên cũng chưa mở được phiếu,
và office KHÔNG nằm trong MASKED_ROLES (xem customer_info_service) nên cấp quyền
sẽ cho họ thấy trọn thông tin khách hàng — vượt xa phạm vi yêu cầu.

Frontend không phải sửa: canUpdateDispatch() đọc mảng permissions của /auth/me,
vốn sinh thẳng từ bảng này.
"""
from alembic import op

revision: str = "1718870400035"
down_revision: str = "1718870400034"
branch_labels = None
depends_on = None



def upgrade() -> None:
    # Gỡ quyền của khối lab.
    op.execute(
        """
        DELETE FROM roles_permissions
        WHERE resource='dispatch' AND action='update'
          AND role IN ('staff', 'lab_manager');
        """
    )
    # Cấp cho Ban lãnh đạo (admin và reception đã có sẵn).
    op.execute(
        """
        INSERT INTO roles_permissions (role, resource, action, scope)
        VALUES ('leader', 'dispatch', 'update', 'all')
        ON CONFLICT (role, resource, action) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM roles_permissions
        WHERE resource='dispatch' AND action='update' AND role='leader';
        """
    )
    op.execute(
        """
        INSERT INTO roles_permissions (role, resource, action, scope)
        VALUES ('staff', 'dispatch', 'update', 'all'),
               ('lab_manager', 'dispatch', 'update', 'all')
        ON CONFLICT (role, resource, action) DO NOTHING;
        """
    )
