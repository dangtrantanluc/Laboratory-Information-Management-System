"""Schemas departments (M7.3). code regex ^[A-Z0-9_-]+$."""
import uuid
from typing import Optional

from pydantic import BaseModel, Field


class CreateDepartmentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    parent_id: Optional[uuid.UUID] = None
    lead_user_id: Optional[uuid.UUID] = None


class UpdateDepartmentRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    code: Optional[str] = Field(default=None, min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    # dùng dict raw để phân biệt "không truyền" với "truyền null" cho parent_id/lead_user_id
    parent_id: Optional[uuid.UUID] = None
    lead_user_id: Optional[uuid.UUID] = None

    model_config = {"extra": "forbid"}
