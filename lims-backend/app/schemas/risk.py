"""Schemas M10 — Risk & Improvement (request bodies).

KHÔNG nhận từ client: risk_code/improvement_code, id, level (server tính GENERATED),
status closed timestamps, created_by. likelihood/impact 1..5.
"""
import uuid
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

RiskKind = Literal["risk", "opportunity"]
RiskStatus = Literal["open", "treating", "monitoring", "closed"]
ImprovementSource = Literal["customer", "staff", "review", "audit", "other"]
ImprovementStatus = Literal["open", "in_progress", "done", "rejected"]


# ===== #2 POST /risks =====
class CreateRiskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    context: str = Field(min_length=1)
    likelihood: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    kind: RiskKind = "risk"
    process_ref: Optional[str] = Field(default=None, max_length=255)
    owner_id: Optional[uuid.UUID] = None
    department_id: Optional[uuid.UUID] = None
    next_review_date: Optional[date] = None

    model_config = {"extra": "forbid"}


# ===== #4 PATCH /risks/:id =====
class UpdateRiskRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    context: Optional[str] = Field(default=None, min_length=1)
    likelihood: Optional[int] = Field(default=None, ge=1, le=5)
    impact: Optional[int] = Field(default=None, ge=1, le=5)
    process_ref: Optional[str] = Field(default=None, max_length=255)
    status: Optional[RiskStatus] = None
    owner_id: Optional[uuid.UUID] = None
    next_review_date: Optional[date] = None

    model_config = {"extra": "forbid"}


# ===== #5 POST /risks/:id/treatments =====
class AddTreatmentRequest(BaseModel):
    treatment: str = Field(min_length=1)
    owner_id: Optional[uuid.UUID] = None
    due_date: Optional[date] = None

    model_config = {"extra": "forbid"}


# ===== #6 PATCH /risks/:id/treatments/:tid =====
class UpdateTreatmentRequest(BaseModel):
    status: Literal["todo", "done"]

    model_config = {"extra": "forbid"}


# ===== #7 POST /risks/:id/close =====
class CloseRiskRequest(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)

    model_config = {"extra": "forbid"}


# ===== #11 POST /improvements =====
class CreateImprovementRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    source: ImprovementSource = "other"
    owner_id: Optional[uuid.UUID] = None
    department_id: Optional[uuid.UUID] = None

    model_config = {"extra": "forbid"}


# ===== #13 PATCH /improvements/:id =====
class UpdateImprovementRequest(BaseModel):
    status: Optional[ImprovementStatus] = None
    owner_id: Optional[uuid.UUID] = None
    linked_nc_id: Optional[uuid.UUID] = None

    model_config = {"extra": "forbid"}
