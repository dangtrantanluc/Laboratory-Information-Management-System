"""Schemas M8 — NC & CAPA (request bodies).

KHÔNG nhận từ client (server tự thiết lập): nc_code, id, status, raised_by, timestamps.
Nguồn (source_type/source_id) nhận khi tạo từ module khác; mặc định 'manual'.
"""
import uuid
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

NcSource = Literal["manual", "complaint", "qc", "audit", "env", "sample", "pt"]
NcSeverity = Literal["minor", "major", "critical"]
CapaType = Literal["corrective", "preventive"]
Effectiveness = Literal["effective", "not_effective"]


# ===== #2 POST /nonconformities =====
class CreateNcRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    severity: NcSeverity
    source_type: NcSource = "manual"
    source_id: Optional[uuid.UUID] = None
    department_id: Optional[uuid.UUID] = None
    impact_assessment: Optional[str] = None
    affected_ref_type: Optional[str] = Field(default=None, max_length=32)
    affected_ref_id: Optional[uuid.UUID] = None

    model_config = {"extra": "forbid"}


# ===== #4 PATCH /nonconformities/:id =====
class UpdateNcRequest(BaseModel):
    severity: Optional[NcSeverity] = None
    impact_assessment: Optional[str] = None
    affected_ref_type: Optional[str] = Field(default=None, max_length=32)
    affected_ref_id: Optional[uuid.UUID] = None

    model_config = {"extra": "forbid"}


# ===== #5 POST /nonconformities/:id/cancel =====
class CancelNcRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    model_config = {"extra": "forbid"}


# ===== #6 POST /nonconformities/:id/capa =====
class OpenCapaRequest(BaseModel):
    root_cause: str = Field(min_length=1)
    owner_id: uuid.UUID
    capa_type: CapaType = "corrective"
    due_date: Optional[date] = None

    model_config = {"extra": "forbid"}


# ===== #7 POST /nonconformities/:id/actions =====
class AddActionRequest(BaseModel):
    action: str = Field(min_length=1)
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[date] = None

    model_config = {"extra": "forbid"}


# ===== #8 PATCH /nonconformities/:id/actions/:actionId =====
class UpdateActionRequest(BaseModel):
    status: Literal["todo", "done"]
    note: Optional[str] = None

    model_config = {"extra": "forbid"}


# ===== #9 POST /nonconformities/:id/close =====
class CloseCapaRequest(BaseModel):
    effectiveness_result: Effectiveness
    effectiveness_note: Optional[str] = None

    model_config = {"extra": "forbid"}
