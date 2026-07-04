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


class UpdateCustomerRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    contact: Optional[str] = Field(default=None, max_length=255)
    type: Optional[CustomerType] = None
    note: Optional[str] = None

    model_config = {"extra": "forbid"}
