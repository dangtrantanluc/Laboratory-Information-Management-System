"""Model access_stats — lượt truy cập (R15, M6.3). High-volume, có thể prune."""
import uuid
from datetime import datetime

from sqlalchemy import String, SmallInteger, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, INET
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AccessStat(Base):
    __tablename__ = "access_stats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    method: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status_code: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    # M6.3/R15: phân loại lượt truy cập (login | page_view). NULL = bản ghi trước M6.
    event_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
