"""Models M4 — Nhân sự (HR).

TÁCH ĐÔI (m34): file này từng chứa cả 16 bảng và chạm trần 800 dòng khi thêm cột
map file Excel hoạt động. Ranh giới tách là ranh giới nghiệp vụ có sẵn, không phải
cắt cho vừa số dòng: 4 bảng nhân sự (hồ sơ, lương, năng lực, dedup thông báo) ở lại
đây; 12 bảng thành tích NCKH & hoạt động sang app/models/research.py.

CatalogBase dùng chung cho danh mục hai bên (natural-key code PK, D5) nên để ở đây —
research.py import lại.

NUMERIC không float (Decimal). hr_profiles 1-1 với users (user_id PK=FK, D3).
salary_history APPEND-ONLY — không expose route sửa/xóa (D8, enforce app-layer).
next_salary_raise_date tính ở app-layer (D9). CHECK DB là lưới an toàn; field-level
RBAC lương/PII + dedup cron enforce ở app-layer.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

VALID_COMPETENCE_KINDS = ("degree", "certificate", "authorization")
VALID_PUBLICATION_TYPES = ("paper", "patent")
VALID_REGISTRATION_STATUS = ("pending", "approved", "rejected")
VALID_PROJECT_STATUS = ("ongoing", "completed", "accepted", "cancelled")
VALID_DEDUP_KINDS = ("SALARY_RAISE_DUE", "CONTRACT_EXPIRY")


# ===================== DANH MỤC (natural-key code PK, D5) =====================
class CatalogBase:
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class ContractType(CatalogBase, Base):
    __tablename__ = "contract_types"


# ===================== TABLE 1: hr_profiles =====================
class HrProfile(Base):
    """Hồ sơ nhân sự 1-1 với users (user_id PK=FK, D3). Lương = coefficient × base (D4)."""

    __tablename__ = "hr_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    hired_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)

    contract_type: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("contract_types.code", ondelete="RESTRICT"), nullable=True
    )
    contract_signed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    salary_grade: Mapped[str | None] = mapped_column(String(32), nullable=True)
    salary_coefficient: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    base_salary_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'VND'")
    )

    salary_cycle_years: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("3")
    )
    last_salary_raise_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_salary_raise_date: Mapped[date | None] = mapped_column(Date, nullable=True)

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
            "salary_coefficient IS NULL OR salary_coefficient > 0", name="ck_hrp_coeff"
        ),
        CheckConstraint(
            "base_salary_amount IS NULL OR base_salary_amount >= 0", name="ck_hrp_base"
        ),
        CheckConstraint("salary_cycle_years >= 1", name="ck_hrp_cycle"),
        CheckConstraint(
            "contract_end_date IS NULL OR contract_signed_date IS NULL "
            "OR contract_end_date > contract_signed_date",
            name="ck_hrp_contract_date_order",
        ),
    )


# ===================== TABLE 2: salary_history (APPEND-ONLY) =====================
class SalaryHistory(Base):
    __tablename__ = "salary_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr_profiles.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    old_grade: Mapped[str | None] = mapped_column(String(32), nullable=True)
    old_coefficient: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    old_base_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    new_grade: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_coefficient: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    new_base_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'VND'")
    )
    raise_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    by_user: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "new_coefficient IS NULL OR new_coefficient > 0", name="ck_sh_coeff"
        ),
        CheckConstraint(
            "new_base_amount IS NULL OR new_base_amount >= 0", name="ck_sh_base"
        ),
    )


# ===================== TABLE 3: competences =====================
class Competence(Base):
    __tablename__ = "competences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr_profiles.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issued_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    scope_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    authorized_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
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
            "kind IN ('degree', 'certificate', 'authorization')", name="ck_comp_kind"
        ),
        CheckConstraint(
            "expiry_date IS NULL OR issued_date IS NULL OR expiry_date >= issued_date",
            name="ck_comp_date_order",
        ),
    )


# ===================== TABLE 4: hr_notification_dedup =====================
class HrNotificationDedup(Base):
    __tablename__ = "hr_notification_dedup"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    profile_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    milestone_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fire_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint(
            "profile_user_id", "kind", "milestone_days", "fire_date", name="uq_hrdedup"
        ),
        CheckConstraint(
            "kind IN ('SALARY_RAISE_DUE', 'CONTRACT_EXPIRY')", name="ck_hrdedup_kind"
        ),
        CheckConstraint("milestone_days IN (3, 7, 15, 30)", name="ck_hrdedup_milestone"),
    )
