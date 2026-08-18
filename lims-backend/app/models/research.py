"""Models M4 — Thành tích NCKH & hoạt động (Research Achievement).

Tách từ models/hr.py ở m34 — xem ghi chú ranh giới tách ở đầu tệp đó.

12 bảng: 3 danh mục NCKH + đề tài/thành viên, công bố/tác giả, hướng dẫn SV,
đăng ký lab, giảng dạy, phục vụ cộng đồng, hợp đồng NCKH, công tác khác,
chứng nhận đào tạo, báo cáo hoạt động tháng.

Cột thêm ở m34 để khớp file "TỔNG HỢP CÁC HOẠT ĐỘNG NĂM 2024-2025":
evidence_url (6 bảng), patent_kind, contract_no/signed_date, training_level,
cert_kind, hk3_theory_hours/hk3_practice_hours.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
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
from app.models.hr import CatalogBase


# ===================== DANH MỤC NCKH (natural-key code PK, D5) =====================
class ResearchProjectLevel(CatalogBase, Base):
    __tablename__ = "research_project_levels"


class PublicationCategory(CatalogBase, Base):
    __tablename__ = "publication_categories"


class MentorshipType(CatalogBase, Base):
    __tablename__ = "mentorship_types"


# ===================== TABLE 5: research_projects =====================
class ResearchProject(Base):
    __tablename__ = "research_projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_reports.id", ondelete="SET NULL"), nullable=True
    )
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    level: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("research_project_levels.code", ondelete="RESTRICT"),
        nullable=True,
    )
    # Chủ nhiệm: user_id HOẶC lead_external_name (người ngoài hệ thống) — theo pattern D1.
    lead_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    lead_external_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(16), nullable=True)  # "2024-2025"
    # Kinh phí (Excel: "100 triệu" → chuẩn hoá NUMERIC). Chuyển giao sản phẩm.
    budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    budget_currency: Mapped[str | None] = mapped_column(
        String(8), nullable=True, server_default=text("'VND'")
    )
    is_transferred: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    transfer_product: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Excel cột J "Link minh chứng" — URL ngoài (Drive/DOI/trang tạp chí). KHÁC
    # attachments (tệp upload): file Excel chỉ lưu đường dẫn, không lưu tệp.
    evidence_url: Mapped[str | None] = mapped_column(Text, nullable=True)
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
        CheckConstraint(
            "lead_user_id IS NOT NULL OR lead_external_name IS NOT NULL",
            name="ck_rp_lead_present",
        ),
    )


# ===================== TABLE 6: project_members =====================
class ProjectMember(Base):
    __tablename__ = "project_members"

    # PK là id riêng (không phải (project_id,user_id)) để cho phép thành viên NGOÀI hệ
    # thống (user_id NULL, external_name) — theo pattern D1 giống publication_authors.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    external_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role_in_project: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'member'")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND external_name IS NULL) "
            "OR (user_id IS NULL AND external_name IS NOT NULL)",
            name="ck_pm_member_xor",
        ),
    )


# ===================== TABLE 7: publications =====================
class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_reports.id", ondelete="SET NULL"), nullable=True
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
        String(12), nullable=False, server_default=text("'paper'")
    )
    # paper: phạm vi trong nước / quốc tế + cờ chỉ mục (Excel cột SCIE/SSCI, Scopus, ACI).
    pub_scope: Mapped[str | None] = mapped_column(String(16), nullable=True)  # domestic|international
    is_scie: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_ssci: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_scopus: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_aci: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    academic_year: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # patent: bổ sung số đơn/ngày nộp, ngày cấp, chủ bằng (Excel bảng sáng chế).
    patent_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issuing_authority: Mapped[str | None] = mapped_column(String(255), nullable=True)
    application_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    application_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    granted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    patent_holder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Excel bảng sáng chế chia ba mục I/II/III bằng dòng tiêu đề, không phải cột:
    # sáng chế | giải pháp hữu ích | giống cây trồng.
    patent_kind: Mapped[str | None] = mapped_column(String(24), nullable=True)
    evidence_url: Mapped[str | None] = mapped_column(Text, nullable=True)
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
        CheckConstraint("type IN ('paper', 'patent', 'conference')", name="ck_pub_type"),
        CheckConstraint(
            "type <> 'patent' OR (patent_no IS NOT NULL AND length(btrim(patent_no)) > 0)",
            name="ck_pub_patent_no",
        ),
        CheckConstraint(
            "pub_scope IS NULL OR pub_scope IN ('domestic', 'international')",
            name="ck_pub_scope",
        ),
        CheckConstraint(
            "patent_kind IS NULL OR (type = 'patent' AND patent_kind IN "
            "('invention', 'utility_solution', 'plant_variety'))",
            name="ck_pub_patent_kind",
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
    # Vai trò tác giả (Excel: "Tác giả liên hệ" / "ĐTG" / "TG"): corresponding|main|co.
    author_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
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
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_reports.id", ondelete="SET NULL"), nullable=True
    )
    # Giảng viên: user_id (nội bộ) HOẶC lecturer_external_name (ngoài HT) — XOR.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    lecturer_external_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    semester: Mapped[str | None] = mapped_column(String(32), nullable=True)
    year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(16), nullable=True)  # "2024-2025"
    # Số tiết theo học kỳ × loại (Excel: HKI/HKII × Lý thuyết/Thực hành).
    hk1_theory_hours: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    hk1_practice_hours: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    hk2_theory_hours: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    hk2_practice_hours: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # HK3 (m34): Viện dạy cả học kỳ hè — Excel 2024-2025 mới có 2 cặp cột nên
    # bảng gốc dừng ở HKII; cấu trúc giữ đối xứng để năm sau bổ sung cột là khớp.
    hk3_theory_hours: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    hk3_practice_hours: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Excel tách HAI bảng "ĐẠI HỌC" (dòng 6) và "SAU ĐẠI HỌC" (dòng 33) cùng cấu
    # trúc cột — phân biệt bằng tiêu đề, nên cần cột riêng mới dựng lại được.
    training_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_url: Mapped[str | None] = mapped_column(Text, nullable=True)
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
        CheckConstraint(
            "(user_id IS NOT NULL AND lecturer_external_name IS NULL) "
            "OR (user_id IS NULL AND lecturer_external_name IS NOT NULL)",
            name="ck_tc_lecturer_xor",
        ),
        CheckConstraint(
            "training_level IS NULL OR training_level IN "
            "('undergraduate', 'postgraduate')",
            name="ck_tc_training_level",
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
    evidence_url: Mapped[str | None] = mapped_column(Text, nullable=True)
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


# ===================== TABLE 13: research_contracts (mới — menu NCKH > Hợp đồng) =====================
class ResearchContract(Base):
    __tablename__ = "research_contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_reports.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    contract_type: Mapped[str | None] = mapped_column(String(64), nullable=True)  # Nghiên cứu|Tư vấn KHCN|...
    # Excel cột D gộp "PUR.2024.00618 ký ngày 23/9/2024" — tách số hiệu và ngày ký.
    contract_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    signed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    value_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(
        String(8), nullable=True, server_default=text("'VND'")
    )
    partner_org: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(16), nullable=True)
    evidence_url: Mapped[str | None] = mapped_column(Text, nullable=True)
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
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_rc_date_order",
        ),
    )


# ===================== TABLE 14: staff_activities (mới — menu Công tác khác) =====================
class StaffActivity(Base):
    """Đảng / Công đoàn / VILAS / khác — mỗi dòng 1 hoạt động + minh chứng."""

    __tablename__ = "staff_activities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activity_reports.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # dang|cong_doan|vilas|khac
    content: Mapped[str] = mapped_column(Text, nullable=False)
    performed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Excel cột C: "Link minh chứng (hình ảnh, khen thưởng, quyết định, chứng nhận)".
    evidence_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    performer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
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
            "kind IN ('dang', 'cong_doan', 'vilas', 'khac')", name="ck_sa_kind"
        ),
    )


# ===================== TABLE 15: training_certificates (mới — Phục vụ CĐ > Cấp GCN) =====================
class TrainingCertificate(Base):
    __tablename__ = "training_certificates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    issued_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    certificate_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Sheet PHỤC VỤ CỘNG ĐỒNG có HAI danh sách cùng cấu trúc, phân biệt bằng tiêu
    # đề: "học viên lớp ngắn hạn" (dòng 12) và "SV tập huấn an toàn PTN & PCCC"
    # (dòng 19). Không có cột này thì hai danh sách trộn làm một.
    cert_kind: Mapped[str | None] = mapped_column(String(24), nullable=True)
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    course_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(16), nullable=True)
    host_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
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
            "cert_kind IS NULL OR cert_kind IN ('short_course', 'lab_safety')",
            name="ck_cert_kind",
        ),
    )


# ===================== TABLE 16: activity_reports (báo cáo hoạt động tháng) =====================
class ActivityReport(Base):
    """Gói báo cáo hoạt động 1 kỳ (tháng) của 1 người. Các dòng hoạt động tạo thẳng vào
    bảng thành tích (research_projects/publications/teaching_courses/research_contracts/
    staff_activities) gắn report_id → hiện ở module tương ứng; văn phòng xem danh sách này."""

    __tablename__ = "activity_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True
    )
    period_label: Mapped[str] = mapped_column(String(32), nullable=False)  # "01/2026"
    period_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'submitted'")
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("status IN ('draft','submitted','reviewed')", name="ck_ar_status"),
        UniqueConstraint("reporter_user_id", "period_label", name="uq_ar_reporter_period"),
    )
