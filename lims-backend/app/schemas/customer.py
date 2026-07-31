"""Schemas customers (M7/chung)."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

# Contract #21 dùng company|individual|internal; DB CHECK gồm rộng hơn.
# Map theo contract API cho input; lưu thẳng (DB cho phép).
CustomerType = Literal["internal", "external", "individual", "organization"]


class CreateCustomerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    contact: Optional[str] = Field(default=None, max_length=255)
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
    contact: Optional[str] = Field(default=None, max_length=255)
    type: Optional[CustomerType] = None
    note: Optional[str] = None
    address: Optional[str] = Field(default=None, max_length=500)
    tax_code: Optional[str] = Field(default=None, max_length=50)
    contact_person: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)

    model_config = {"extra": "forbid"}
