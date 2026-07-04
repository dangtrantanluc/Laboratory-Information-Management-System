"""Model overdue_reasons (M1) — lý do trễ hạn (FR-014, BR-009). Bất biến (hồ sơ §8.4)."""
import uuid
from datetime import datetime

from sqlalchemy import Text, ForeignKey, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class OverdueReason(Base):
    __tablename__ = "overdue_reasons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    sample_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("samples.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    by_user: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("length(btrim(reason)) > 0", name="ck_ovr_reason"),
    )
