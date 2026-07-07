"""Model users — người dùng hệ thống (M7.3). password_hash KHÔNG bao giờ trả ra API."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, ForeignKey, CheckConstraint, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

VALID_ROLES = ("admin", "leader", "accountant", "staff")
VALID_USER_STATUS = ("active", "disabled")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    # M8: cờ Phụ trách chất lượng (Quality Manager §5/§8.7). Đúng pattern is_dept_lead —
    # cho phép staff được ủy quyền QM: mở/đóng CAPA. admin/leader luôn có quyền QMS.
    is_quality_manager: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'active'")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint(
            "role IN ('admin', 'leader', 'accountant', 'staff')", name="ck_users_role"
        ),
        CheckConstraint("status IN ('active', 'disabled')", name="ck_users_status"),
        CheckConstraint("position('@' IN email) > 1", name="ck_users_email"),
    )
