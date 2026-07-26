"""Model Thẻ vào PTN (sinh viên) — M19.

Danh sách quản trị (CRUD, không qua duyệt) do Văn phòng quản lý, đối chiếu
theo file "DANH SÁCH SINH VIÊN ĐÃ ĐƯỢC CẤP THẺ VÀO PTN". Không liên quan tới
LabRegistration (NCKH, có quy trình duyệt) ở models/hr.py.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class LabAccessCard(Base):
    __tablename__ = "lab_access_cards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    student_name: Mapped[str] = mapped_column(String(255), nullable=False)
    class_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    student_code: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    room: Mapped[str] = mapped_column(String(255), nullable=False)  # đăng ký sử dụng PTN
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supervisor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # giáo viên hướng dẫn
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
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
        CheckConstraint(
            "valid_to IS NULL OR valid_to >= valid_from", name="ck_lab_access_period"
        ),
    )
