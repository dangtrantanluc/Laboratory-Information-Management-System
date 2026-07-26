"""Schemas — báo cáo hoạt động hàng tháng (m25). Form nhẹ, mỗi section là danh sách dòng."""
import uuid
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class TeachingEntry(BaseModel):
    course_name: str = Field(min_length=1, max_length=255)
    semester: Optional[str] = Field(default=None, max_length=32)
    hk1_theory_hours: Optional[int] = Field(default=None, ge=0, le=10000)
    hk1_practice_hours: Optional[int] = Field(default=None, ge=0, le=10000)
    hk2_theory_hours: Optional[int] = Field(default=None, ge=0, le=10000)
    hk2_practice_hours: Optional[int] = Field(default=None, ge=0, le=10000)
    note: Optional[str] = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}


class ProjectEntry(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    level: Optional[str] = Field(default=None, max_length=32)
    role: Optional[str] = Field(default=None, max_length=32)  # lead|member
    task_status: Optional[str] = Field(default=None, max_length=16)
    budget_amount: Optional[str] = Field(default=None, max_length=32)

    model_config = {"extra": "forbid"}


class PublicationEntry(BaseModel):
    pub_kind: Literal["domestic", "international", "conference"] = "domestic"
    title: str = Field(min_length=1, max_length=512)
    journal: Optional[str] = Field(default=None, max_length=255)
    year: Optional[int] = Field(default=None, ge=1900, le=2100)
    doi: Optional[str] = Field(default=None, max_length=255)
    is_scie: Optional[bool] = None
    is_ssci: Optional[bool] = None
    is_scopus: Optional[bool] = None
    is_aci: Optional[bool] = None

    model_config = {"extra": "forbid"}


class ContractEntry(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    contract_type: Optional[str] = Field(default=None, max_length=64)
    value_amount: Optional[str] = Field(default=None, max_length=32)
    partner_org: Optional[str] = Field(default=None, max_length=255)

    model_config = {"extra": "forbid"}


class OtherEntry(BaseModel):
    kind: Literal["dang", "cong_doan", "vilas", "khac"] = "khac"
    content: str = Field(min_length=1, max_length=4000)

    model_config = {"extra": "forbid"}


class CreateReportRequest(BaseModel):
    period_label: str = Field(min_length=1, max_length=32)  # "01/2026"
    period_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    academic_year: Optional[str] = Field(default=None, max_length=16)
    department_id: Optional[uuid.UUID] = None
    note: Optional[str] = Field(default=None, max_length=2000)
    teaching: List[TeachingEntry] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)
    publications: List[PublicationEntry] = Field(default_factory=list)
    contracts: List[ContractEntry] = Field(default_factory=list)
    activities: List[OtherEntry] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
