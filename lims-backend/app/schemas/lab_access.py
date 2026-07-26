"""Schemas Thẻ vào PTN (sinh viên) — M19."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class CreateLabAccessCardRequest(BaseModel):
    student_name: str = Field(min_length=1, max_length=255)
    class_name: Optional[str] = Field(default=None, max_length=50)
    student_code: str = Field(min_length=1, max_length=30)
    email: Optional[str] = Field(default=None, max_length=255)
    room: str = Field(min_length=1, max_length=255)
    purpose: Optional[str] = Field(default=None, max_length=255)
    supervisor_name: Optional[str] = Field(default=None, max_length=255)
    valid_from: date
    valid_to: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=1000)


class UpdateLabAccessCardRequest(BaseModel):
    student_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    class_name: Optional[str] = Field(default=None, max_length=50)
    student_code: Optional[str] = Field(default=None, min_length=1, max_length=30)
    email: Optional[str] = Field(default=None, max_length=255)
    room: Optional[str] = Field(default=None, min_length=1, max_length=255)
    purpose: Optional[str] = Field(default=None, max_length=255)
    supervisor_name: Optional[str] = Field(default=None, max_length=255)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=1000)

    model_config = {"extra": "forbid"}
