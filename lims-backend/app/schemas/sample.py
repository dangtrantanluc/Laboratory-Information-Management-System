"""Schemas M1 — Sample Lifecycle (request bodies).

KHÔNG nhận từ client: request_code, sample_code, status, department_id (mẫu),
received_by (mẫu), version, approved_by, entered_by — server tự thiết lập.
"""
import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

ConditionStatus = Literal["acceptable", "not_acceptable"]


# ===== test_requests =====
class CreateTestRequestRequest(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    sender_name: str = Field(min_length=1, max_length=255)
    department_id: Optional[uuid.UUID] = None
    received_by: Optional[uuid.UUID] = None
    received_at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=1000)


class UpdateTestRequestRequest(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    sender_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    received_by: Optional[uuid.UUID] = None
    received_at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=1000)

    model_config = {"extra": "forbid"}


# ===== samples =====
class CreateSampleRequest(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    deadline_at: datetime
    condition_status: Optional[ConditionStatus] = None
    condition_note: Optional[str] = Field(default=None, max_length=500)


class UpdateSampleRequest(BaseModel):
    description: Optional[str] = Field(default=None, min_length=1, max_length=500)

    model_config = {"extra": "forbid"}


class UpdateConditionRequest(BaseModel):
    condition_status: ConditionStatus
    condition_note: Optional[str] = Field(default=None, max_length=500)


class UpdateDeadlineRequest(BaseModel):
    deadline_at: datetime


# ===== assignments =====
class CreateAssignmentRequest(BaseModel):
    part_name: str = Field(min_length=1, max_length=150)
    assigned_to: uuid.UUID


# ===== handovers =====
class CreateHandoverRequest(BaseModel):
    to_user: uuid.UUID
    reason: str = Field(min_length=1, max_length=500)


# ===== results =====
class CreateResultRequest(BaseModel):
    result_data: dict
    note: Optional[str] = Field(default=None, max_length=1000)


class ApproveResultRequest(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)


class ReturnResultRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class ReviseResultRequest(BaseModel):
    result_data: dict
    reason: str = Field(min_length=1, max_length=500)


# ===== finalize / overdue =====
class FinalizeRequest(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)


class OverdueReasonRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
