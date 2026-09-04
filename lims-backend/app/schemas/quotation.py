"""Schemas BÁO GIÁ (m29). Số tiền là STRING để tránh sai số float; server dùng Decimal."""
import uuid
from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class QuotationItemBody(BaseModel):
    sort_order: Optional[int] = None
    sample_name: Optional[str] = Field(default=None, max_length=500)
    test_parameter_id: Optional[uuid.UUID] = None
    parameter_name: Optional[str] = Field(default=None, max_length=500)
    method: Optional[str] = Field(default=None, max_length=500)
    unit: Optional[str] = Field(default=None, max_length=50)
    quantity: Optional[int] = Field(default=1, ge=1, le=100000)
    unit_price: Optional[str] = Field(default=None, max_length=24)
    note: Optional[str] = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}


class CreateQuotationRequest(BaseModel):
    intake_id: Optional[uuid.UUID] = None
    customer_name: str = Field(min_length=1, max_length=255)
    customer_address: Optional[str] = Field(default=None, max_length=500)
    customer_email: Optional[str] = Field(default=None, max_length=255)
    customer_tax_code: Optional[str] = Field(default=None, max_length=50)
    customer_phone: Optional[str] = Field(default=None, max_length=50)
    issue_date: Optional[date] = None
    valid_until: Optional[date] = None
    vat_rate: Optional[str] = Field(default="8", max_length=8)
    note: Optional[str] = Field(default=None, max_length=4000)
    items: List[QuotationItemBody] = Field(default_factory=list, max_length=500)

    model_config = {"extra": "forbid"}


class UpdateQuotationRequest(BaseModel):
    intake_id: Optional[uuid.UUID] = None
    customer_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    customer_address: Optional[str] = Field(default=None, max_length=500)
    customer_email: Optional[str] = Field(default=None, max_length=255)
    customer_tax_code: Optional[str] = Field(default=None, max_length=50)
    customer_phone: Optional[str] = Field(default=None, max_length=50)
    issue_date: Optional[date] = None
    valid_until: Optional[date] = None
    vat_rate: Optional[str] = Field(default=None, max_length=8)
    note: Optional[str] = Field(default=None, max_length=4000)
    items: Optional[List[QuotationItemBody]] = Field(default=None, max_length=500)
    # m41 — lý do sửa, lưu kèm bản chụp phiên bản trước. Tuỳ chọn với bản nháp
    # (chưa gửi ai), nhưng là thứ duy nhất giải thích được vì sao bản khách đang
    # cầm khác bản trong hệ thống.
    revision_reason: Optional[str] = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}


class QuotationVersionOut(BaseModel):
    id: uuid.UUID
    version: int
    reason: Optional[str] = None
    created_at: datetime
    snapshot: dict


class QuotationVersionListResponse(BaseModel):
    success: bool
    data: list[QuotationVersionOut]


class ChangeQuotationStatusRequest(BaseModel):
    status: Literal["draft", "sent", "accepted", "rejected", "expired"]

    model_config = {"extra": "forbid"}
