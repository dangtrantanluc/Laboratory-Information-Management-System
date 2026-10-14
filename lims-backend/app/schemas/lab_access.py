"""Schemas Thẻ vào PTN (sinh viên) — M19."""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CreateLabAccessCardRequest(BaseModel):
    student_name: str = Field(min_length=1, max_length=255)
    class_name: Optional[str] = Field(default=None, max_length=50)
    student_code: str = Field(min_length=1, max_length=30)
    email: Optional[str] = Field(default=None, max_length=255)
    room: Optional[str] = Field(default=None, max_length=255)
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
    room: Optional[str] = Field(default=None, max_length=255)
    purpose: Optional[str] = Field(default=None, max_length=255)
    supervisor_name: Optional[str] = Field(default=None, max_length=255)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=1000)

    model_config = {"extra": "forbid"}


# ── Nhập / xuất Excel ─────────────────────────────────────────────
class LabAccessImportIssue(BaseModel):
    row: int
    student_code: Optional[str] = None
    message: str


class LabAccessImportItem(BaseModel):
    row: int
    student_code: str
    student_name: str
    action: Literal["create", "update", "unchanged"]


class LabAccessImportResult(BaseModel):
    dry_run: bool
    sheet: str
    total_rows: int
    created: int
    updated: int
    unchanged: int
    errors: list[LabAccessImportIssue]
    items: list[LabAccessImportItem]


class LabAccessImportResponse(BaseModel):
    success: bool
    data: LabAccessImportResult
