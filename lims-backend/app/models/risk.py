"""Models M10 — Rủi ro & Cơ hội + Cải tiến (Risk & Improvement, §8.5/§8.6/§8.4).

4 bảng theo Contract M10 (24-contract-m10-risk.md §1):
- risks: sổ đăng ký rủi ro/cơ hội theo tiến trình. level = likelihood×impact (GENERATED
  STORED, 1..25) — không tính app-layer để tránh lệch. Band suy ra khi serialize.
- risk_treatments: biện pháp xử lý có người chịu trách nhiệm + hạn.
- improvements: cơ hội cải tiến §8.6 (sổ nhẹ); linked_nc_id nối sang NC/CAPA (M8) khi
  cải tiến trở thành hành động khắc phục.
- risk_notification_dedup: chống trùng CRON-8 mốc 30/15/7 (đồng bộ M5/M8 dedup).

CHECK DB là lưới an toàn; nghiệp vụ (band, RBAC/QM, dedup) enforce app-layer. Audit §8.4.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

VALID_RISK_KIND = ("risk", "opportunity")
VALID_RISK_STATUS = ("open", "treating", "monitoring", "closed")
VALID_TREATMENT_STATUS = ("todo", "done")
VALID_IMPROVEMENT_SOURCE = ("customer", "staff", "review", "audit", "other")
VALID_IMPROVEMENT_STATUS = ("open", "in_progress", "done", "rejected")
VALID_RISK_DEDUP_KINDS = ("RISK_REVIEW_DUE",)


class Risk(Base):
    """Rủi ro/cơ hội §8.5. level = likelihood×impact (GENERATED STORED — mapped read-only)."""

    __tablename__ = "risks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    risk_code: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=text("'risk'")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    process_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    likelihood: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    impact: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # GENERATED ALWAYS AS (likelihood*impact) STORED — Computed → SQLAlchemy loại khỏi
    # INSERT/UPDATE + fetch sau (server tính, không ghi app-layer).
    level: Mapped[int] = mapped_column(
        SmallInteger, Computed("likelihood * impact", persisted=True), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=text("'open'")
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    next_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
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
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("risk_code", name="uq_risk_code"),
        CheckConstraint("kind IN ('risk','opportunity')", name="ck_risk_kind"),
        CheckConstraint("likelihood BETWEEN 1 AND 5", name="ck_risk_likelihood"),
        CheckConstraint("impact BETWEEN 1 AND 5", name="ck_risk_impact"),
        CheckConstraint(
            "status IN ('open','treating','monitoring','closed')", name="ck_risk_status"
        ),
    )


class RiskTreatment(Base):
    """Biện pháp xử lý rủi ro (§8.5.2)."""

    __tablename__ = "risk_treatments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="CASCADE"), nullable=False
    )
    treatment: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default=text("'todo'")
    )
    done_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("status IN ('todo','done')", name="ck_treatment_status"),
    )


class Improvement(Base):
    """Cơ hội cải tiến §8.6. linked_nc_id nối sang NC/CAPA (M8) khi triển khai."""

    __tablename__ = "improvements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    improvement_code: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'other'")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=text("'open'")
    )
    linked_nc_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nonconformities.id", ondelete="SET NULL"),
        nullable=True,
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
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("improvement_code", name="uq_improvement_code"),
        CheckConstraint(
            "source IN ('customer','staff','review','audit','other')",
            name="ck_improvement_source",
        ),
        CheckConstraint(
            "status IN ('open','in_progress','done','rejected')",
            name="ck_improvement_status",
        ),
    )


class RiskNotificationDedup(Base):
    """Chống trùng CRON-8 (đồng bộ equipment/capa dedup). 1 dòng/(risk, mốc, ngày)."""

    __tablename__ = "risk_notification_dedup"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    milestone_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fire_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint(
            "risk_id", "milestone_days", "fire_date", name="uq_riskdedup_risk_ms_date"
        ),
        CheckConstraint("kind IN ('RISK_REVIEW_DUE')", name="ck_riskdedup_kind"),
        CheckConstraint("milestone_days IN (30, 15, 7)", name="ck_riskdedup_milestone"),
    )
