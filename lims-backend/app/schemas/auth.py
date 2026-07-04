"""Schemas auth (M7.1). password đi qua HTTPS, KHÔNG log."""
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas._email import Email

_PWD_STRENGTH = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).+$")


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """Body optional cho native client; mặc định refresh token lấy từ cookie."""

    refresh_token: str | None = Field(default=None, max_length=512)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _strength(cls, v: str) -> str:
        if not _PWD_STRENGTH.match(v):
            raise ValueError("Mật khẩu phải có cả chữ và số, tối thiểu 8 ký tự")
        return v


class UpdateMeRequest(BaseModel):
    """Tự cập nhật hồ sơ cá nhân. CHỈ họ tên + email — vai trò/phòng ban do admin
    quản lý (chặn leo thang đặc quyền), KHÔNG nhận ở đây."""

    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    email: Optional[Email] = None

    model_config = {"extra": "forbid"}
