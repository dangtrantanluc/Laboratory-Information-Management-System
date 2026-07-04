"""Model sample_assignments (M1) — phân công phần việc cho KTV (FR-005)."""
import uuid
from datetime import datetime

from sqlalchemy import String, ForeignKey, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

VALID_ASSIGNMENT_STATUS = ("assigned", "in_progress", "result_entered", "approved")


class SampleAssignment(Base):
    __tablename__ = "sample_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    sample_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("samples.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_to: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    part_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'assigned'")
    )
    assigned_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
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
        CheckConstraint(
            "status IN ('assigned', 'in_progress', 'result_entered', 'approved')",
            name="ck_asg_status",
        ),
    )
