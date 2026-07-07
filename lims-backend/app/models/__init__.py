"""ORM models M7 — import tất cả để Alembic autogenerate / metadata thấy đầy đủ."""
from app.models.department import Department
from app.models.user import User
from app.models.permission import Permission, RolePermission
from app.models.customer import Customer
from app.models.attachment import Attachment
from app.models.refresh_token import RefreshToken
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
    ResearchProject,
    ResearchProjectLevel,
    SalaryHistory,
    StudentMentorship,
    TeachingCourse,
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

__all__ = [
    "Department",
    "User",
    "Permission",
    "RolePermission",
    "Customer",
    "Attachment",
    "RefreshToken",
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
]
