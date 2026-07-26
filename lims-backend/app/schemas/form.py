"""Schemas kho biểu mẫu VILAS (GĐ3)."""
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field

FormCategory = Literal["BM", "QT", "HD", "TL"]


class CreateFormTemplateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=500)
    iso_clause: str = Field(min_length=1, max_length=16)
    category: FormCategory = "BM"
    year: Optional[int] = Field(default=None, ge=2000, le=2100)
    note: Optional[str] = Field(default=None, max_length=1000)


class UpdateFormTemplateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    iso_clause: Optional[str] = Field(default=None, min_length=1, max_length=16)
    category: Optional[FormCategory] = None
    year: Optional[int] = Field(default=None, ge=2000, le=2100)
    is_active: Optional[bool] = None
    note: Optional[str] = Field(default=None, max_length=1000)

    model_config = {"extra": "forbid"}


class CreateFormSubmissionRequest(BaseModel):
    template_id: uuid.UUID
    # Nếu None: ép phòng của người nộp (KTV/trưởng phòng). Admin/QLCL có thể chỉ định.
    department_id: Optional[uuid.UUID] = None
    year: Optional[int] = Field(default=None, ge=2000, le=2100)
    note: Optional[str] = Field(default=None, max_length=1000)


class RejectFormSubmissionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
