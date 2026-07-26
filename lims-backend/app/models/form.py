"""Models kho biểu mẫu VILAS (M11/GĐ3).

- FormTemplate: biểu mẫu gốc do Phòng QLCL quản trị (dùng chung toàn viện), phân theo
  điều khoản ISO/IEC 17025 (iso_clause) + loại (BM/QT/HD). File gắn qua attachments
  (owner_type='form_template').
- FormSubmission: minh chứng do phòng lab điền & nộp lên (owner_type='form_submission').
  Nộp xong → thông báo cho Phòng QLCL.
"""
import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Boolean, ForeignKey, CheckConstraint, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

VALID_FORM_CATEGORY = ("BM", "QT", "HD", "TL")  # Biểu mẫu / Quy trình / Hướng dẫn / Tài liệu


class FormTemplate(Base):
    __tablename__ = "form_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)  # vd "BM 6.2.01"
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    iso_clause: Mapped[str] = mapped_column(String(16), nullable=False)  # vd "6.2", "7.5"
    category: Mapped[str] = mapped_column(String(4), nullable=False, server_default=text("'BM'"))
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)  # phiên bản theo năm
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
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
        UniqueConstraint("code", name="uq_form_tpl_code"),
        CheckConstraint("category IN ('BM','QT','HD','TL')", name="ck_form_tpl_category"),
    )


class FormSubmission(Base):
    __tablename__ = "form_submissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("form_templates.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    reject_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected')", name="ck_fs_status"
        ),
        CheckConstraint(
            "(reviewed_by IS NULL AND reviewed_at IS NULL) "
            "OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_fs_review_pair",
        ),
    )
