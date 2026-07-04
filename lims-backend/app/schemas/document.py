"""Schemas M3 — Quản lý Tài liệu (request bodies).

KHÔNG nhận từ client: code (document_code), id, version_no, status, created_by,
approved_by, current_version_id — server tự thiết lập (rule security: giá/định danh
server-side). File qua multipart (UploadFile), không qua body.
"""
from typing import Optional

from pydantic import BaseModel, Field


class UpdateDocumentRequest(BaseModel):
    """PATCH /documents/:id — chỉ sửa metadata (title/type/security_level).
    KHÔNG cho đổi code/department_id (gửi → 422 CODE_IMMUTABLE / 403)."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=512)
    type: Optional[str] = Field(default=None, max_length=32)
    security_level: Optional[str] = Field(default=None, max_length=12)

    model_config = {"extra": "forbid"}


class UpdateVersionRequest(BaseModel):
    """PATCH /documents/:id/versions/:vid — sửa change_note (chỉ draft).
    File thay qua multipart endpoint riêng (không trong body JSON)."""

    change_note: Optional[str] = Field(default=None, max_length=1000)

    model_config = {"extra": "forbid"}


class RejectVersionRequest(BaseModel):
    """POST .../reject — reject_reason bắt buộc (BR-DOC-020)."""

    reject_reason: str = Field(min_length=1, max_length=1000)


class ApproveVersionRequest(BaseModel):
    """POST .../approve — body rỗng hoặc note ghi chú duyệt (optional)."""

    note: Optional[str] = Field(default=None, max_length=1000)

    model_config = {"extra": "forbid"}
