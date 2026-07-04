"""Schemas M4 — HR & Research Achievement (request bodies).

KHÔNG nhận từ client: next_salary_raise_date (server tự tính), department_id của hồ sơ
(suy từ users), created_by/updated_by, status duyệt (qua endpoint approve/reject).
Số tiền/hệ số nhận STRING-decimal để KHÔNG mất chính xác float (contract §0.12);
validate + Decimal ở service.
"""
import uuid
from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

CompetenceKind = Literal["degree", "certificate", "authorization"]
PublicationType = Literal["paper", "patent"]


# ===================== Hồ sơ nhân sự =====================
class CreateProfileRequest(BaseModel):
    user_id: uuid.UUID
    job_title: str = Field(min_length=1, max_length=255)
    hired_date: Optional[date] = None
    phone: Optional[str] = Field(default=None, max_length=32)

    model_config = {"extra": "forbid"}


class UpdateProfileRequest(BaseModel):
    job_title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    hired_date: Optional[date] = None
    phone: Optional[str] = Field(default=None, max_length=32)
    position: Optional[str] = Field(default=None, max_length=255)

    model_config = {"extra": "forbid"}


class UpdateContractRequest(BaseModel):
    contract_signed_date: date
    contract_type: str = Field(min_length=1, max_length=32)
    contract_end_date: Optional[date] = None

    model_config = {"extra": "forbid"}


class UpdateSalaryCycleRequest(BaseModel):
    salary_cycle_years: int = Field(ge=1, le=50)

    model_config = {"extra": "forbid"}


class CreateSalaryRaiseRequest(BaseModel):
    salary_grade: str = Field(min_length=1, max_length=32)
    salary_coefficient: str = Field(min_length=1, max_length=20)
    base_salary_amount: str = Field(min_length=1, max_length=20)
    raise_date: date
    note: Optional[str] = Field(default=None, max_length=255)

    model_config = {"extra": "forbid"}


# ===================== Năng lực =====================
class CreateCompetenceRequest(BaseModel):
    kind: CompetenceKind
    title: str = Field(min_length=1, max_length=255)
    issuer: Optional[str] = Field(default=None, max_length=255)
    issued_date: Optional[date] = None
    expiry_date: Optional[date] = None
    scope_detail: Optional[str] = Field(default=None, max_length=2000)
    authorized_by: Optional[uuid.UUID] = None

    model_config = {"extra": "forbid"}


class UpdateCompetenceRequest(BaseModel):
    kind: Optional[CompetenceKind] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    issuer: Optional[str] = Field(default=None, max_length=255)
    issued_date: Optional[date] = None
    expiry_date: Optional[date] = None
    scope_detail: Optional[str] = Field(default=None, max_length=2000)
    authorized_by: Optional[uuid.UUID] = None

    model_config = {"extra": "forbid"}


# ===================== Đề tài =====================
class MemberItem(BaseModel):
    user_id: Optional[uuid.UUID] = None
    external_name: Optional[str] = Field(default=None, max_length=255)
    role_in_project: Optional[str] = Field(default="member", max_length=64)

    model_config = {"extra": "forbid"}


class CreateProjectRequest(BaseModel):
    code: Optional[str] = Field(default=None, max_length=64)
    title: str = Field(min_length=1, max_length=512)
    level: str = Field(min_length=1, max_length=32)
    lead_user_id: uuid.UUID
    department_id: Optional[uuid.UUID] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = Field(default="ongoing", max_length=16)
    members: List[MemberItem] = Field(min_length=1)

    model_config = {"extra": "forbid"}


class UpdateProjectRequest(BaseModel):
    code: Optional[str] = Field(default=None, max_length=64)
    title: Optional[str] = Field(default=None, min_length=1, max_length=512)
    level: Optional[str] = Field(default=None, max_length=32)
    lead_user_id: Optional[uuid.UUID] = None
    department_id: Optional[uuid.UUID] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = Field(default=None, max_length=16)

    model_config = {"extra": "forbid"}


class ReplaceMembersRequest(BaseModel):
    members: List[MemberItem] = Field(min_length=1)

    model_config = {"extra": "forbid"}


# ===================== Bài báo / Sáng chế =====================
class AuthorItem(BaseModel):
    user_id: Optional[uuid.UUID] = None
    external_name: Optional[str] = Field(default=None, max_length=255)
    author_order: int = Field(ge=1)
    is_corresponding: bool = False

    model_config = {"extra": "forbid"}


class CreatePublicationRequest(BaseModel):
    type: PublicationType
    title: str = Field(min_length=1, max_length=512)
    journal: Optional[str] = Field(default=None, max_length=255)
    year: int = Field(ge=1900, le=2100)
    doi: Optional[str] = Field(default=None, max_length=255)
    index_code: Optional[str] = Field(default=None, max_length=32)  # alias category
    category: Optional[str] = Field(default=None, max_length=32)
    patent_no: Optional[str] = Field(default=None, max_length=64)
    issuing_authority: Optional[str] = Field(default=None, max_length=255)
    department_id: Optional[uuid.UUID] = None
    authors: List[AuthorItem] = Field(min_length=1)

    model_config = {"extra": "forbid"}


class UpdatePublicationRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=512)
    journal: Optional[str] = Field(default=None, max_length=255)
    year: Optional[int] = Field(default=None, ge=1900, le=2100)
    doi: Optional[str] = Field(default=None, max_length=255)
    index_code: Optional[str] = Field(default=None, max_length=32)
    category: Optional[str] = Field(default=None, max_length=32)
    patent_no: Optional[str] = Field(default=None, max_length=64)
    issuing_authority: Optional[str] = Field(default=None, max_length=255)
    department_id: Optional[uuid.UUID] = None

    model_config = {"extra": "forbid"}


class ReplaceAuthorsRequest(BaseModel):
    authors: List[AuthorItem] = Field(min_length=1)

    model_config = {"extra": "forbid"}


# ===================== Hướng dẫn SV =====================
class CreateMentorshipRequest(BaseModel):
    mentor_id: uuid.UUID
    student_name: str = Field(min_length=1, max_length=255)
    topic: Optional[str] = Field(default=None, max_length=512)
    year: int = Field(ge=1900, le=2100)
    type: str = Field(min_length=1, max_length=32)

    model_config = {"extra": "forbid"}


class UpdateMentorshipRequest(BaseModel):
    student_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    topic: Optional[str] = Field(default=None, max_length=512)
    year: Optional[int] = Field(default=None, ge=1900, le=2100)
    type: Optional[str] = Field(default=None, max_length=32)

    model_config = {"extra": "forbid"}


# ===================== Đăng ký lab =====================
class CreateRegistrationRequest(BaseModel):
    student_name: str = Field(min_length=1, max_length=255)
    mentor_id: uuid.UUID
    registered_from: date
    registered_to: Optional[date] = None
    purpose: str = Field(min_length=1, max_length=2000)

    model_config = {"extra": "forbid"}


class DecideRegistrationRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=255)

    model_config = {"extra": "forbid"}


# ===================== Giảng dạy =====================
class CreateTeachingRequest(BaseModel):
    user_id: uuid.UUID
    course_name: str = Field(min_length=1, max_length=255)
    semester: str = Field(min_length=1, max_length=32)
    year: int = Field(ge=1900, le=2100)

    model_config = {"extra": "forbid"}


class UpdateTeachingRequest(BaseModel):
    course_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    semester: Optional[str] = Field(default=None, max_length=32)
    year: Optional[int] = Field(default=None, ge=1900, le=2100)

    model_config = {"extra": "forbid"}


# ===================== Cộng đồng =====================
class CreateCommunityRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    performed_at: date
    host: Optional[str] = Field(default=None, max_length=255)
    performer_user_id: uuid.UUID

    model_config = {"extra": "forbid"}


class UpdateCommunityRequest(BaseModel):
    content: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    performed_at: Optional[date] = None
    host: Optional[str] = Field(default=None, max_length=255)

    model_config = {"extra": "forbid"}
