"""Schemas users (M7.3). KHÔNG nhận status/password_hash/id từ client."""
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas._email import Email

Role = Literal[
    "admin", "leader", "office", "staff", "reception", "qms", "lab_manager"
]
UserStatus = Literal["active", "disabled", "pending"]


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


class ApproveUserRequest(BaseModel):
    """Duyệt tài khoản tự đăng ký (m30) — Quản trị viên gán vai trò thật ở bước này."""

    role: Role
    department_id: Optional[uuid.UUID] = None
    is_dept_lead: bool = False

    model_config = {"extra": "forbid"}


class RejectUserRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)

    model_config = {"extra": "forbid"}
