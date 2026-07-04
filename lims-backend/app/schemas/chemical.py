"""Schemas M2 — Chemical Inventory (request bodies).

KHÔNG nhận từ client: measurement_group (suy ra từ base_unit), qty_base, balance_after,
status, created_by, by_user — server tự thiết lập (rule security).

Số thập phân nhận dạng STRING-decimal để KHÔNG mất chính xác float (contract §0.5):
qty_input NUMERIC(14,4), unit_price NUMERIC(14,2), reorder_threshold NUMERIC(18,6).
Validate + quy đổi sang Decimal ở service.
"""
import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

MeasurementGroup = Literal["mass", "volume", "count"]
TxnType = Literal["in", "out", "adjust"]
RecheckResult = Literal["pass", "fail"]


# ===== chemicals =====
class CreateChemicalRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    cas_no: Optional[str] = Field(default=None, max_length=20)
    manufacturer: Optional[str] = Field(default=None, max_length=255)
    base_unit: str = Field(min_length=1, max_length=16)
    hazard_code: Optional[str] = Field(default=None, max_length=64)
    department_id: Optional[uuid.UUID] = None
    reorder_threshold: Optional[str] = Field(default=None, max_length=40)

    model_config = {"extra": "forbid"}


class UpdateChemicalRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    cas_no: Optional[str] = Field(default=None, max_length=20)
    manufacturer: Optional[str] = Field(default=None, max_length=255)
    hazard_code: Optional[str] = Field(default=None, max_length=64)
    reorder_threshold: Optional[str] = Field(default=None, max_length=40)
    base_unit: Optional[str] = Field(default=None, min_length=1, max_length=16)

    model_config = {"extra": "forbid"}


# ===== lots =====
class InitialIntake(BaseModel):
    qty_input: str = Field(min_length=1, max_length=40)
    input_unit: str = Field(min_length=1, max_length=16)
    unit_price: Optional[str] = Field(default=None, max_length=40)
    currency: Optional[str] = Field(default=None, max_length=3)
    note: Optional[str] = Field(default=None, max_length=500)

    model_config = {"extra": "forbid"}


class CreateLotRequest(BaseModel):
    lot_no: str = Field(min_length=1, max_length=64)
    received_at: Optional[date] = None
    expiry_date: Optional[date] = None
    recheck_date: Optional[date] = None
    initial_intake: Optional[InitialIntake] = None

    model_config = {"extra": "forbid"}


# ===== transactions =====
class CreateTransactionRequest(BaseModel):
    type: TxnType
    at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=500)

    # in / out
    qty_input: Optional[str] = Field(default=None, max_length=40)
    input_unit: Optional[str] = Field(default=None, max_length=16)

    # in
    unit_price: Optional[str] = Field(default=None, max_length=40)
    currency: Optional[str] = Field(default=None, max_length=3)

    # out
    ref_sample_id: Optional[uuid.UUID] = None
    confirm_warning: bool = False

    # adjust (one of actual_qty_input / delta_input)
    actual_qty_input: Optional[str] = Field(default=None, max_length=40)
    delta_input: Optional[str] = Field(default=None, max_length=40)

    model_config = {"extra": "forbid"}


# ===== rechecks =====
class CreateRecheckRequest(BaseModel):
    result: RecheckResult
    checked_at: date
    next_recheck_date: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=500)
    attachment_file_key: Optional[str] = Field(default=None, max_length=512)

    model_config = {"extra": "forbid"}
