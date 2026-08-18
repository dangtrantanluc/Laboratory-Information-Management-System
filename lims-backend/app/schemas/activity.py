"""Schemas — hợp đồng NCKH, công tác khác, chứng nhận đào tạo (menu mới, migration m23)."""
import uuid
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

StaffActivityKind = Literal["dang", "cong_doan", "vilas", "khac"]
# Sheet PHỤC VỤ CỘNG ĐỒNG có hai danh sách GCN cùng cấu trúc, phân biệt bằng tiêu đề.
CertKind = Literal["short_course", "lab_safety"]


# ===================== research_contracts =====================
class CreateContractRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    contract_type: Optional[str] = Field(default=None, max_length=64)
    # Excel cột D gộp số hiệu và ngày ký: "PUR.2024.00618 ký ngày 23/9/2024".
    contract_no: Optional[str] = Field(default=None, max_length=128)
    signed_date: Optional[date] = None
    value_amount: Optional[str] = Field(default=None, max_length=32)  # decimal-string
    currency: Optional[str] = Field(default=None, max_length=8)
    partner_org: Optional[str] = Field(default=None, max_length=255)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    academic_year: Optional[str] = Field(default=None, max_length=16)
    evidence_url: Optional[str] = Field(default=None, max_length=2000)
    department_id: Optional[uuid.UUID] = None

    model_config = {"extra": "forbid"}


class UpdateContractRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=512)
    contract_type: Optional[str] = Field(default=None, max_length=64)
    contract_no: Optional[str] = Field(default=None, max_length=128)
    signed_date: Optional[date] = None
    value_amount: Optional[str] = Field(default=None, max_length=32)
    currency: Optional[str] = Field(default=None, max_length=8)
    partner_org: Optional[str] = Field(default=None, max_length=255)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    academic_year: Optional[str] = Field(default=None, max_length=16)
    evidence_url: Optional[str] = Field(default=None, max_length=2000)
    department_id: Optional[uuid.UUID] = None

    model_config = {"extra": "forbid"}


# ===================== staff_activities =====================
class CreateStaffActivityRequest(BaseModel):
    kind: StaffActivityKind
    content: str = Field(min_length=1, max_length=4000)
    performed_at: Optional[date] = None
    academic_year: Optional[str] = Field(default=None, max_length=16)
    evidence_url: Optional[str] = Field(default=None, max_length=2000)
    performer_user_id: Optional[uuid.UUID] = None
    department_id: Optional[uuid.UUID] = None

    model_config = {"extra": "forbid"}


class UpdateStaffActivityRequest(BaseModel):
    kind: Optional[StaffActivityKind] = None
    content: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    performed_at: Optional[date] = None
    academic_year: Optional[str] = Field(default=None, max_length=16)
    evidence_url: Optional[str] = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}


# ===================== training_certificates =====================
class CreateCertificateRequest(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=255)
    certificate_no: Optional[str] = Field(default=None, max_length=64)
    cert_kind: Optional[CertKind] = None
    course_name: Optional[str] = Field(default=None, max_length=255)
    issued_date: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=2000)
    academic_year: Optional[str] = Field(default=None, max_length=16)
    host_user_id: Optional[uuid.UUID] = None
    department_id: Optional[uuid.UUID] = None

    model_config = {"extra": "forbid"}


class UpdateCertificateRequest(BaseModel):
    recipient_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    certificate_no: Optional[str] = Field(default=None, max_length=64)
    cert_kind: Optional[CertKind] = None
    course_name: Optional[str] = Field(default=None, max_length=255)
    issued_date: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=2000)
    academic_year: Optional[str] = Field(default=None, max_length=16)

    model_config = {"extra": "forbid"}
