"""Model samples (M1) — mẫu thử nghiệm, vòng đời độc lập (FR-001..019).

status enforce qua state machine app-layer (FR-017); CHECK DB là lưới an toàn giá trị.
current_custodian_id denorm (D5) — nguồn chân lý chain of custody là sample_handovers.
description lưu trong note để giữ schema gọn (contract dùng "description" ở API layer).
"""
import uuid
from datetime import datetime

from sqlalchemy import String, Text, ForeignKey, CheckConstraint, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

VALID_SAMPLE_STATUS = (
    "received",
    "assigned",
    "testing",
    "done",
    "overdue",
    "returned",
)
VALID_CONDITION_STATUS = ("acceptable", "not_acceptable")


class Sample(Base):
    __tablename__ = "samples"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    sample_code: Mapped[str] = mapped_column(String(32), nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_requests.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    received_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    current_custodian_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    deadline_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'received'")
    )
    condition_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    condition_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
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
        UniqueConstraint("sample_code", name="uq_sample_code"),
        CheckConstraint(
            "status IN ('received', 'assigned', 'testing', 'done', 'overdue', 'returned')",
            name="ck_smp_status",
        ),
        CheckConstraint(
            "condition_status IS NULL OR condition_status IN ('acceptable', 'not_acceptable')",
            name="ck_smp_condition_status",
        ),
        CheckConstraint("deadline_at > received_at", name="ck_smp_deadline"),
        CheckConstraint(
            "condition_status IS DISTINCT FROM 'not_acceptable' "
            "OR (condition_note IS NOT NULL AND length(btrim(condition_note)) > 0)",
            name="ck_smp_condition",
        ),
    )
