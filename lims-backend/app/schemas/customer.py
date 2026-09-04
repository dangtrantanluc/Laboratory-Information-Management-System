"""Schemas customers + danh bạ liên hệ (M7/chung, m35)."""
import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# m43 — vai trò mặc định của người liên hệ trong sổ khách.
ContactRole = Literal["courier", "technical", "result_recipient", "billing"]

# Contract #21 dùng company|individual|internal; DB CHECK gồm rộng hơn.
# Map theo contract API cho input; lưu thẳng (DB cho phép).
CustomerType = Literal["internal", "external", "individual", "organization"]


class CreateCustomerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: CustomerType = "external"
    note: Optional[str] = None
    # m32 — tự điền phiếu nhận mẫu BM 7.1.01
    address: Optional[str] = Field(default=None, max_length=500)
    tax_code: Optional[str] = Field(default=None, max_length=50)
    contact_person: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)


class UpdateCustomerRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    type: Optional[CustomerType] = None
    note: Optional[str] = None
    address: Optional[str] = Field(default=None, max_length=500)
    tax_code: Optional[str] = Field(default=None, max_length=50)
    contact_person: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)

    model_config = {"extra": "forbid"}


# ── m35: danh bạ liên hệ (1 khách – n người) ─────────────────────
class CreateCustomerContactRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    job_title: Optional[str] = Field(default=None, max_length=255)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    # Đặt mặc định: service tự gỡ cờ của dòng mặc định cũ, KHÔNG để hai dòng cùng bật.
    is_primary: bool = False
    is_active: bool = True
    note: Optional[str] = None
    roles: Optional[list[ContactRole]] = Field(default=None, max_length=4)


class UpdateCustomerContactRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    job_title: Optional[str] = Field(default=None, max_length=255)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None
    note: Optional[str] = None
    roles: Optional[list[ContactRole]] = Field(default=None, max_length=4)

    model_config = {"extra": "forbid"}


class CustomerContactOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    full_name: str
    job_title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_primary: bool
    is_active: bool
    roles: list[str] = []
    note: Optional[str] = None
    created_at: datetime


# Envelope {"success": true, "data": ...} theo app/core/responses.py. Khai tường minh
# vì test kiến trúc test_response_contract chặn endpoint MỚI thiếu response_model.
class CustomerContactResponse(BaseModel):
    success: bool
    data: CustomerContactOut


class CustomerContactListResponse(BaseModel):
    success: bool
    data: list[CustomerContactOut]


# ── m44: cảnh báo trùng khách ────────────────────────────────────
class DuplicateCustomerOut(BaseModel):
    id: uuid.UUID
    name: str
    tax_code: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    # 'tax_code' | 'name' — cho quầy biết TRÙNG Ở ĐÂU để tự quyết.
    matched_on: str


class DuplicateCustomerListResponse(BaseModel):
    success: bool
    data: list[DuplicateCustomerOut]
