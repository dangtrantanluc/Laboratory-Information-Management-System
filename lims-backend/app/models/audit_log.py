"""Model audit_logs — nhật ký kiểm toán APPEND-ONLY (D8, 17025 §8.4).

KHÔNG có route/ORM UPDATE/DELETE. Trigger DB chặn thêm 1 lớp.
"""
import uuid
from datetime import datetime

from sqlalchemy import String, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
