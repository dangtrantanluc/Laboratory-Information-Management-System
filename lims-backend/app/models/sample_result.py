"""Model sample_results (M1) — kết quả phần việc + versioning immutable (FR-008/010, D6).

approved bất biến; sửa = INSERT version+1 (giữ bản cũ). approved_by ≠ entered_by enforce
app-layer (D8). Partial unique is_current đảm bảo mỗi assignment 1 version hiện hành.
"""
import uuid
from datetime import datetime

from sqlalchemy import Integer, Boolean, Text, ForeignKey, CheckConstraint, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class SampleResult(Base):
    __tablename__ = "sample_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sample_assignments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    result_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    entered_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    entered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    revision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("assignment_id", "version", name="uq_res_assignment_version"),
        CheckConstraint("version >= 1", name="ck_res_version"),
        CheckConstraint(
            "(approved_by IS NULL AND approved_at IS NULL) "
            "OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_res_approval_pair",
        ),
        CheckConstraint(
            "version = 1 OR (revision_reason IS NOT NULL AND length(btrim(revision_reason)) > 0)",
            name="ck_res_revision_reason",
        ),
    )
