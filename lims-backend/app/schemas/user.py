"""Schemas users (M7.3). KHÔNG nhận status/password_hash/id từ client."""
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas._email import Email

Role = Literal["admin", "leader", "accountant", "staff"]
UserStatus = Literal["active", "disabled"]


class CreateUserRequest(BaseModel):
    email: Email
    full_name: str = Field(min_length=1, max_length=255)
    role: Role
    department_id: Optional[uuid.UUID] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    is_dept_lead: bool = False


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role: Optional[Role] = None
    department_id: Optional[uuid.UUID] = None
    email: Optional[Email] = None

    model_config = {"extra": "forbid"}


class ResetPasswordRequest(BaseModel):
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=128)
