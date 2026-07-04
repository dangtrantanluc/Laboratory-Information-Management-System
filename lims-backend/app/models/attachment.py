"""Model attachments — file polymorphic dùng chung M1/M2/M3/M5 (D9). owner_id KHÔNG FK cứng."""
import uuid
from datetime import datetime

from sqlalchemy import String, BigInteger, ForeignKey, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

# Whitelist owner_type — nới rộng (ALTER CHECK) khi thêm module
VALID_OWNER_TYPES = (
    "test_request",
    "sample",
    "sample_result",
    "chemical",
    "chem_lot",
    "document",
    "document_version",
    "equipment",
    "calibration",
    "hr_profile",
    "publication",
)


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_type: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    file_key: Mapped[str] = mapped_column(String(512), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str | None] = mapped_column(String(127), nullable=True)
    size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "owner_type IN ('test_request', 'sample', 'sample_result', 'chemical', "
            "'chem_lot', 'document', 'document_version', 'equipment', 'calibration', "
            "'hr_profile', 'publication')",
            name="ck_att_owner_type",
        ),
        CheckConstraint("size IS NULL OR size >= 0", name="ck_att_size"),
    )
