"""m30: TỰ PHỤC VỤ TÀI KHOẢN — đăng ký có duyệt, quên mật khẩu, avatar, quản lý phiên.

Bốn thay đổi:

1. users.status thêm 'pending' — tài khoản tự đăng ký nằm ở đây cho tới khi Quản trị
   viên duyệt và gán vai trò/phòng ban. KHÔNG đăng nhập được ở trạng thái này.
   (ISO/IEC 17025: tài khoản = quyền truy cập hồ sơ, không ai được tự cấp quyền.)

2. users.email_verified_at — mốc người dùng bấm link xác thực trong mail. Tách bạch với
   status: xác thực mail là "đúng là chủ hộp thư", duyệt là "được phép vào hệ thống".

3. users.avatar_key — object key trong MinIO. Chỉ lưu ĐƯỜNG DẪN, ảnh nằm ở MinIO;
   API trả presigned URL TTL ngắn chứ không trả link vĩnh viễn.

4. Bảng auth_tokens — token dùng-một-lần cho xác thực mail / đặt lại mật khẩu.
   Lưu SHA-256 của token chứ không lưu token thô (cùng kỷ luật với refresh_tokens):
   rò rỉ bảng DB không cho phép kẻ tấn công đặt lại mật khẩu của ai.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1718870400029"
down_revision: Union[str, None] = "1718870400028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. users.status: cho phép thêm 'pending' ──
    # Ràng buộc này ở các DB hiện có mang tên Postgres tự sinh (`users_status_check`),
    # còn model khai báo name="ck_users_status". Bỏ cả hai tên để migration chạy được
    # trên mọi môi trường, rồi tạo lại với tên tường minh.
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_status_check")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_status")
    op.create_check_constraint(
        "ck_users_status",
        "users",
        "status IN ('active', 'disabled', 'pending')",
    )

    # ── 2 & 3. Cột mới trên users ──
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("avatar_key", sa.String(512), nullable=True))

    # Người dùng đã tồn tại trước m30 do Quản trị viên tạo → coi như đã xác thực,
    # nếu không họ sẽ bị luồng mới bắt xác thực lại một cách vô lý.
    op.execute("UPDATE users SET email_verified_at = created_at WHERE status = 'active'")

    # ── 4. auth_tokens ──
    op.create_table(
        "auth_tokens",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # sha256 hex = 64 ký tự. KHÔNG lưu token thô.
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column(
            "expires_at", sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=False
        ),
        sa.Column(
            "used_at", sa.dialects.postgresql.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("ip", sa.dialects.postgresql.INET(), nullable=True),
        sa.Column(
            "created_at",
            sa.dialects.postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "purpose IN ('email_verify', 'password_reset')", name="ck_auth_tokens_purpose"
        ),
        sa.UniqueConstraint("token_hash", name="uq_auth_tokens_hash"),
    )
    # Tra cứu lúc đổi/huỷ token còn hiệu lực của một user + một mục đích.
    op.create_index(
        "ix_auth_tokens_user_purpose", "auth_tokens", ["user_id", "purpose", "used_at"]
    )
    # Job dọn token hết hạn.
    op.create_index("ix_auth_tokens_expires", "auth_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_auth_tokens_expires", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_user_purpose", table_name="auth_tokens")
    op.drop_table("auth_tokens")

    op.drop_column("users", "avatar_key")
    op.drop_column("users", "email_verified_at")

    # Không còn 'pending' → hạ về 'disabled' để không vi phạm CHECK cũ.
    op.execute("UPDATE users SET status = 'disabled' WHERE status = 'pending'")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_status")
    op.create_check_constraint(
        "ck_users_status", "users", "status IN ('active', 'disabled')"
    )
