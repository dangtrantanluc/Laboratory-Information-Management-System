"""ORM models M7 — import tất cả để Alembic autogenerate / metadata thấy đầy đủ."""
from app.models.department import Department
from app.models.user import User
from app.models.permission import Permission, RolePermission
from app.models.customer import Customer
from app.models.attachment import Attachment
from app.models.refresh_token import RefreshToken
from app.models.auth_token import AuthToken
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.access_stat import AccessStat

# --- M1: Sample Lifecycle ---
from app.models.test_request import TestRequest
from app.models.sample import Sample
from app.models.sample_assignment import SampleAssignment
from app.models.sample_result import SampleResult
from app.models.sample_handover import SampleHandover
from app.models.overdue_reason import OverdueReason

# --- M2: Chemical Inventory ---
from app.models.chemical import (
    Chemical,
    ChemicalLot,
    ChemicalNotificationDedup,
    ChemicalRecheckRecord,
    ChemicalTransaction,
    Unit,
)

# --- M3: Document Control ---
from app.models.document import (
    Document,
    DocumentAccessLog,
    DocumentType,
    DocumentVersion,
)

# --- M5: Equipment & Calibration ---
from app.models.equipment import (
    CalibrationRecord,
    Equipment,
    EquipmentNotificationDedup,
)

# --- M4: HR & Research Achievement ---
from app.models.hr import (
    ActivityReport,
    CommunityService,
    Competence,
    ContractType,
    HrNotificationDedup,
    HrProfile,
    LabRegistration,
    MentorshipType,
    ProjectMember,
    Publication,
    PublicationAuthor,
    PublicationCategory,
    ResearchContract,
    ResearchProject,
    ResearchProjectLevel,
    SalaryHistory,
    StaffActivity,
    StudentMentorship,
    TeachingCourse,
    TrainingCertificate,
)

# --- M8: Nonconformity & CAPA ---
from app.models.nonconformity import (
    Capa,
    CapaAction,
    CapaNotificationDedup,
    Nonconformity,
)

# --- M10: Risk & Improvement ---
from app.models.risk import (
    Improvement,
    Risk,
    RiskNotificationDedup,
    RiskTreatment,
)

# --- M11/GĐ3: Kho biểu mẫu VILAS (QLCL) ---
from app.models.form import FormTemplate, FormSubmission

# --- GĐ2b: Nhận & Chuyển mẫu (reception → lab) ---
from app.models.quotation import Quotation, QuotationItem
from app.models.sample_flow import SampleIntake, SampleDispatch, CustomerInfoRequest, TestParameter

# --- M19: Thẻ vào PTN (sinh viên, Văn phòng quản lý) ---
from app.models.lab_access import LabAccessCard

# --- M20: Web Push (popup thông báo desktop) ---
from app.models.push_subscription import PushSubscription

__all__ = [
    "Department",
    "User",
    "Permission",
    "RolePermission",
    "Customer",
    "Attachment",
    "RefreshToken",
    "AuthToken",
    "Notification",
    "AuditLog",
    "AccessStat",
    # M1
    "TestRequest",
    "Sample",
    "SampleAssignment",
    "SampleResult",
    "SampleHandover",
    "OverdueReason",
    # M2
    "Unit",
    "Chemical",
    "ChemicalLot",
    "ChemicalTransaction",
    "ChemicalRecheckRecord",
    "ChemicalNotificationDedup",
    # M3
    "DocumentType",
    "Document",
    "DocumentVersion",
    "DocumentAccessLog",
    # M5
    "Equipment",
    "CalibrationRecord",
    "EquipmentNotificationDedup",
    # M4
    "ContractType",
    "ResearchProjectLevel",
    "PublicationCategory",
    "MentorshipType",
    "HrProfile",
    "SalaryHistory",
    "Competence",
    "HrNotificationDedup",
    "ResearchProject",
    "ProjectMember",
    "Publication",
    "PublicationAuthor",
    "StudentMentorship",
    "LabRegistration",
    "TeachingCourse",
    "CommunityService",
    "ResearchContract",
    "StaffActivity",
    "TrainingCertificate",
    "ActivityReport",
    # M8
    "Nonconformity",
    "Capa",
    "CapaAction",
    "CapaNotificationDedup",
    # M10
    "Risk",
    "RiskTreatment",
    "Improvement",
    "RiskNotificationDedup",
    # M11/GĐ3
    "FormTemplate",
    "FormSubmission",
    # GĐ2b
    "SampleIntake",
    "SampleDispatch",
    "CustomerInfoRequest",
    "TestParameter",
    "Quotation",
    "QuotationItem",
    # M19
    "LabAccessCard",
    # M20
    "PushSubscription",
]
