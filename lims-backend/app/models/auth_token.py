"""Model auth_tokens — token dùng-một-lần cho xác thực email / đặt lại mật khẩu (m30).

Chỉ lưu SHA-256 của token, KHÔNG lưu token thô — cùng kỷ luật với refresh_tokens (D7).
Rò rỉ nội dung bảng không cho phép kẻ tấn công đặt lại mật khẩu của bất kỳ ai.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import INET, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

PURPOSE_EMAIL_VERIFY = "email_verify"
PURPOSE_PASSWORD_RESET = "password_reset"
VALID_PURPOSES = (PURPOSE_EMAIL_VERIFY, PURPOSE_PASSWORD_RESET)


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "purpose IN ('email_verify', 'password_reset')", name="ck_auth_tokens_purpose"
        ),
        UniqueConstraint("token_hash", name="uq_auth_tokens_hash"),
    )
