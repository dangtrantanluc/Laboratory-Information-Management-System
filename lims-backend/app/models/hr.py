"""Models M4 — Nhân sự & Thành tích NCKH (HR & Research Achievement).

16 bảng theo Contract M4 Schema (11-contract-m4-schema.md §2): 4 danh mục
(ContractType/ResearchProjectLevel/PublicationCategory/MentorshipType) + 12 nghiệp vụ.

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
class _CatalogBase:
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


class ContractType(_CatalogBase, Base):
    __tablename__ = "contract_types"


class ResearchProjectLevel(_CatalogBase, Base):
    __tablename__ = "research_project_levels"


class PublicationCategory(_CatalogBase, Base):
    __tablename__ = "publication_categories"


class MentorshipType(_CatalogBase, Base):
    __tablename__ = "mentorship_types"


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


# ===================== TABLE 5: research_projects =====================
class ResearchProject(Base):
    __tablename__ = "research_projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    level: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("research_project_levels.code", ondelete="RESTRICT"),
        nullable=True,
    )
    lead_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ongoing'")
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
        UniqueConstraint("code", name="uq_rp_code"),
        CheckConstraint(
            "status IN ('ongoing', 'completed', 'accepted', 'cancelled')",
            name="ck_rp_status",
        ),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_rp_date_order",
        ),
    )


# ===================== TABLE 6: project_members =====================
class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    role_in_project: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'member'")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (PrimaryKeyConstraint("project_id", "user_id", name="pk_project_members"),)


# ===================== TABLE 7: publications =====================
class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    journal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("publication_categories.code", ondelete="RESTRICT"),
        nullable=True,
    )
    type: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default=text("'paper'")
    )
    patent_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issuing_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
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
        CheckConstraint("type IN ('paper', 'patent')", name="ck_pub_type"),
        CheckConstraint(
            "type <> 'patent' OR (patent_no IS NOT NULL AND length(btrim(patent_no)) > 0)",
            name="ck_pub_patent_no",
        ),
    )


# ===================== TABLE 8: publication_authors =====================
class PublicationAuthor(Base):
    __tablename__ = "publication_authors"

    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    external_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_corresponding: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        PrimaryKeyConstraint("publication_id", "author_order", name="pk_pub_authors"),
        CheckConstraint("author_order >= 1", name="ck_pa_order"),
        CheckConstraint(
            "(user_id IS NOT NULL AND external_name IS NULL) "
            "OR (user_id IS NULL AND external_name IS NOT NULL)",
            name="ck_pa_author_xor",
        ),
    )


# ===================== TABLE 9: student_mentorships =====================
class StudentMentorship(Base):
    __tablename__ = "student_mentorships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    mentor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    student_name: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(512), nullable=True)
    year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    type: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("mentorship_types.code", ondelete="RESTRICT"), nullable=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
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


# ===================== TABLE 10: lab_registrations =====================
class LabRegistration(Base):
    __tablename__ = "lab_registrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    student_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mentor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    registered_at: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=text("CURRENT_DATE")
    )
    registered_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    registered_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=text("'pending'")
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
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
            "status IN ('pending', 'approved', 'rejected')", name="ck_lr_status"
        ),
        CheckConstraint(
            "registered_to IS NULL OR registered_from IS NULL "
            "OR registered_to >= registered_from",
            name="ck_lr_date_order",
        ),
        CheckConstraint(
            "(status = 'pending' AND approved_by IS NULL AND approved_at IS NULL) "
            "OR (status IN ('approved', 'rejected') AND approved_by IS NOT NULL "
            "AND approved_at IS NOT NULL)",
            name="ck_lr_approval",
        ),
    )


# ===================== TABLE 11: teaching_courses =====================
class TeachingCourse(Base):
    __tablename__ = "teaching_courses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    semester: Mapped[str | None] = mapped_column(String(32), nullable=True)
    year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
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
        UniqueConstraint(
            "user_id", "course_name", "semester", "year", name="uq_tc_user_course_term"
        ),
    )


# ===================== TABLE 12: community_services =====================
class CommunityService(Base):
    __tablename__ = "community_services"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    performed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    performer_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
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
