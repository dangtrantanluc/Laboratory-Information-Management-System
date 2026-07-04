"""Schemas M5 — Quản lý Thiết bị & Hiệu chuẩn (request bodies).

KHÔNG nhận từ client (server tự thiết lập — rule security): code (equipment_code), id,
next_due_date (chỉ qua ghi hiệu chuẩn #9), created_by, updated_by, status badge cảnh báo.
File CoC/tài liệu qua multipart (UploadFile), không qua body JSON.
"""
import uuid
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

EquipmentStatus = Literal["active", "maintenance", "broken", "retired"]
CycleUnit = Literal["month", "year"]
CalibrationResult = Literal["pass", "fail"]


# ===== #4 POST /equipments =====
class CreateEquipmentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    location: Optional[str] = Field(default=None, max_length=255)
    department_id: Optional[uuid.UUID] = None
    responsible_user_id: Optional[uuid.UUID] = None
    purchase_date: Optional[date] = None
    status: Optional[EquipmentStatus] = None
    calibration_cycle_value: Optional[int] = Field(default=None, gt=0, le=600)
    calibration_cycle_unit: Optional[CycleUnit] = None

    model_config = {"extra": "forbid"}


# ===== #5 PATCH /equipments/:id =====
class UpdateEquipmentRequest(BaseModel):
    """≥1 field. KHÔNG cho đổi code (→ 422 CODE_IMMUTABLE) / department_id non-admin (→ 403).
    null cho responsible_user_id = bỏ người phụ trách; null cho cycle = bỏ diện hiệu chuẩn.

    KHÔNG dùng extra='forbid' để service nhận diện code/department_id và trả mã lỗi đúng
    contract (CODE_IMMUTABLE / FORBIDDEN) thay vì VALIDATION_ERROR chung từ Pydantic."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    location: Optional[str] = Field(default=None, max_length=255)
    responsible_user_id: Optional[uuid.UUID] = None
    purchase_date: Optional[date] = None
    status: Optional[EquipmentStatus] = None
    calibration_cycle_value: Optional[int] = Field(default=None, gt=0, le=600)
    calibration_cycle_unit: Optional[CycleUnit] = None

    model_config = {"extra": "allow"}
