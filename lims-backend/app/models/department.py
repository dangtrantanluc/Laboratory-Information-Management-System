"""Model departments — cây phòng ban (B01). Vòng FK với users giải ở migration (D3)."""
import uuid
from datetime import datetime

from sqlalchemy import String, ForeignKey, CheckConstraint, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    # lead_user_id: FK gắn ở migration (ALTER) sau khi tạo users — phá vòng (D3)
    lead_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'active'"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_dept_code"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_dept_status"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_dept_not_self_parent"),
    )
