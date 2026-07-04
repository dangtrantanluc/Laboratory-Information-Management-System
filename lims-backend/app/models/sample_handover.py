"""Model sample_handovers (M1) — chain of custody bất biến (FR-006/007, 17025 §7.4).

IMMUTABLE: KHÔNG có route/ORM UPDATE/DELETE. Nhầm = ghi handover đính chính mới.
"""
import uuid
from datetime import datetime

from sqlalchemy import Text, ForeignKey, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class SampleHandover(Base):
    __tablename__ = "sample_handovers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    sample_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("samples.id", ondelete="RESTRICT"), nullable=False
    )
    from_user: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    to_user: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("from_user <> to_user", name="ck_ho_diff_user"),
    )
