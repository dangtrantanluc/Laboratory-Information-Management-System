"""Models M3 — Quản lý Tài liệu (Document Control, §8.3/§8.4).

4 bảng: document_types (danh mục natural-key code) · documents (vùng chứa version,
vòng FK current_version_id giải ở migration — D3) · document_versions (state machine
draft→review→approved→obsolete; immutable approved/obsolete + tách soạn–duyệt
enforce app-layer — D6/D8/D9) · document_access_log (R15 high-volume — D11).

≤1 version approved/tài liệu enforce DB-level (partial unique uq_doc_one_approved
ở migration — D7). File qua attachments polymorphic owner_type='document_version'.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class DocumentType(Base):
    """Danh mục loại tài liệu (D4). Natural-key code PK; cấu hình được qua is_active."""

    __tablename__ = "document_types"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_order: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class Document(Base):
    """Tài liệu QMS (FR-DOC-001..005). Vùng chứa 1..n version; KHÔNG chứa file.

    code bất biến (BR-DOC-014); current_version_id trỏ version approved hoặc NULL.
    fk_doc_current gắn ở migration (phá vòng FK — D3).
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    type: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("document_types.code", ondelete="RESTRICT"),
        nullable=False,
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    security_level: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=text("'internal'")
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'active'")
    )
    # current_version_id: FK gắn ở migration (ALTER) — phá vòng (D3)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
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
        UniqueConstraint("code", name="uq_doc_code"),
        CheckConstraint(
            "security_level IN ('internal', 'restricted')", name="ck_doc_security"
        ),
        CheckConstraint(
            "status IN ('active', 'archived', 'deleted')", name="ck_doc_status"
        ),
    )


class DocumentVersion(Base):
    """Phiên bản tài liệu (FR-DOC-006..013). State machine app-layer (D9); immutable
    khi approved/obsolete (D6); approved_by ≠ created_by app-layer (D8).
    ≤1 approved/tài liệu enforce partial unique DB-level (D7, migration)."""

    __tablename__ = "document_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'draft'")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("document_id", "version_no", name="uq_dv_doc_version"),
        CheckConstraint("version_no >= 1", name="ck_dv_version_no"),
        CheckConstraint(
            "status IN ('draft', 'review', 'approved', 'obsolete')", name="ck_dv_status"
        ),
        CheckConstraint(
            "(approved_by IS NULL AND approved_at IS NULL) "
            "OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_dv_approval_pair",
        ),
        CheckConstraint(
            "(reviewed_by IS NULL AND reviewed_at IS NULL) "
            "OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_dv_review_pair",
        ),
        CheckConstraint(
            "(submitted_by IS NULL AND submitted_at IS NULL) "
            "OR (submitted_by IS NOT NULL AND submitted_at IS NOT NULL)",
            name="ck_dv_submit_pair",
        ),
        CheckConstraint(
            "status <> 'approved' OR approved_by IS NOT NULL",
            name="ck_dv_approved_has_approver",
        ),
    )


class DocumentAccessLog(Base):
    """Lượt truy cập tài liệu (R15, FR-DOC-014/015). High-volume; KHÔNG immutable (D11)
    — ghi best-effort. Đếm chỉ lượt HỢP LỆ (403 không ghi). KHÁC audit_logs (pháp lý)."""

    __tablename__ = "document_access_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('view', 'download', 'edit')", name="ck_dal_action"
        ),
    )
