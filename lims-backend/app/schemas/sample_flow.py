"""Schemas Nhận & Chuyển mẫu (GĐ2b) — theo biểu mẫu BM 7.1.01 / BM 7.1.02."""
import uuid
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

DispatchStatus = Literal["sent", "received", "in_progress", "done", "returned"]


class CreateIntakeRequest(BaseModel):
    # m33 — chọn khách từ sổ (tùy chọn). Các trường bên dưới vẫn là bản chụp của
    # phiếu: FE tự điền sẵn từ khách đã chọn nhưng người dùng được sửa đè.
    customer_id: Optional[uuid.UUID] = None
    customer_name: str = Field(min_length=1, max_length=255)
    contact: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    note: Optional[str] = None
    # BM 7.1.01
    address: Optional[str] = Field(default=None, max_length=500)
    tax_code: Optional[str] = Field(default=None, max_length=50)
    contact_person: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    due_date: Optional[str] = Field(default=None, max_length=30)
    result_language: Optional[str] = Field(default=None, max_length=10)
    return_method: Optional[str] = Field(default=None, max_length=20)
    fee_note: Optional[str] = Field(default=None, max_length=500)
    other_request: Optional[str] = None


class UpdateIntakeRequest(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    customer_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    contact: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    note: Optional[str] = None
    status: Optional[Literal["received", "quoted", "quote_accepted", "paid", "dispatched", "completed", "cancelled"]] = None
    dispatch_note: Optional[str] = None
    address: Optional[str] = Field(default=None, max_length=500)
    tax_code: Optional[str] = Field(default=None, max_length=50)
    contact_person: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    due_date: Optional[str] = Field(default=None, max_length=30)
    result_language: Optional[str] = Field(default=None, max_length=10)
    return_method: Optional[str] = Field(default=None, max_length=20)
    fee_note: Optional[str] = Field(default=None, max_length=500)
    other_request: Optional[str] = None

    model_config = {"extra": "forbid"}


class CreateDispatchRequest(BaseModel):
    """Chỉ tiêu: CHỌN từ master data (test_parameter_id) HOẶC nhập tự do (chi_tieu).

    Nếu có test_parameter_id → tự lấy tên/phương pháp/đơn giá từ bảng giá (m27);
    chi_tieu khi đó là tùy chọn (dùng để ghi đè tên nếu muốn).
    """
    chi_tieu: Optional[str] = Field(default=None, min_length=1)  # chỉ tiêu — text tự do
    test_parameter_id: Optional[uuid.UUID] = None                # chọn từ danh mục
    sample_name: Optional[str] = Field(default=None, max_length=500)  # Loại/Tên mẫu (BM 7.1.02)
    quantity: Optional[int] = Field(default=1, ge=1, le=10000)        # Số lượng
    target_department_id: uuid.UUID
    note: Optional[str] = None
    don_vi: Optional[str] = Field(default=None, max_length=100)
    phuong_phap: Optional[str] = None


class DispatchItem(BaseModel):
    """1 dòng chỉ tiêu trong lượt chuyển nhiều chỉ tiêu (m27)."""
    chi_tieu: Optional[str] = Field(default=None, min_length=1)
    test_parameter_id: Optional[uuid.UUID] = None
    sample_name: Optional[str] = Field(default=None, max_length=500)
    quantity: Optional[int] = Field(default=1, ge=1, le=10000)
    target_department_id: uuid.UUID
    note: Optional[str] = None
    don_vi: Optional[str] = Field(default=None, max_length=100)
    phuong_phap: Optional[str] = None

    model_config = {"extra": "forbid"}


class CreateDispatchBatchRequest(BaseModel):
    """Chuyển NHIỀU chỉ tiêu cùng lúc — nguyên tử, gộp thông báo theo phòng."""
    items: list[DispatchItem] = Field(min_length=1, max_length=100)

    model_config = {"extra": "forbid"}


class UpdateDispatchRequest(BaseModel):
    """Lab cập nhật trạng thái và/hoặc kết quả (BM 7.1.02)."""
    status: Optional[DispatchStatus] = None
    sample_name: Optional[str] = Field(default=None, max_length=500)
    quantity: Optional[int] = Field(default=None, ge=1, le=10000)
    note: Optional[str] = None
    don_vi: Optional[str] = Field(default=None, max_length=100)
    phuong_phap: Optional[str] = None
    ket_qua: Optional[str] = None
    can_bo: Optional[str] = Field(default=None, max_length=255)

    model_config = {"extra": "forbid"}


class CreateInfoRequestBody(BaseModel):
    """Khối lab xin xem thông tin khách hàng của phiếu nhận mẫu (m26)."""

    reason: Optional[str] = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}


class DecideInfoRequestBody(BaseModel):
    """Phòng nhận mẫu duyệt/từ chối yêu cầu."""

    note: Optional[str] = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}


# ===== m27: Master data chỉ tiêu thử nghiệm =====
_MATRIX = Literal["soil", "water", "fertilizer", "feed", "food", "quarantine", "molecular", "other"]


class CreateTestParameterRequest(BaseModel):
    matrix: _MATRIX = "other"
    sample_matrix: Optional[str] = Field(default=None, max_length=500)
    name: str = Field(min_length=1, max_length=500)
    method: Optional[str] = Field(default=None, max_length=500)
    unit: Optional[str] = Field(default=None, max_length=50)
    unit_price: Optional[str] = Field(default=None, max_length=24)  # chuỗi số — tránh sai số float
    currency: Optional[str] = Field(default="VND", max_length=8)
    turnaround_days: Optional[int] = Field(default=None, ge=0, le=3650)
    in_charge: Optional[str] = Field(default=None, max_length=255)
    note: Optional[str] = Field(default=None, max_length=4000)
    department_id: Optional[uuid.UUID] = None
    is_accredited: Optional[bool] = False
    is_active: Optional[bool] = True
    sort_order: Optional[int] = None

    model_config = {"extra": "forbid"}


class UpdateTestParameterRequest(BaseModel):
    matrix: Optional[_MATRIX] = None
    sample_matrix: Optional[str] = Field(default=None, max_length=500)
    name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    method: Optional[str] = Field(default=None, max_length=500)
    unit: Optional[str] = Field(default=None, max_length=50)
    unit_price: Optional[str] = Field(default=None, max_length=24)
    currency: Optional[str] = Field(default=None, max_length=8)
    turnaround_days: Optional[int] = Field(default=None, ge=0, le=3650)
    in_charge: Optional[str] = Field(default=None, max_length=255)
    note: Optional[str] = Field(default=None, max_length=4000)
    department_id: Optional[uuid.UUID] = None
    is_accredited: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

    model_config = {"extra": "forbid"}


# ===== m28: Trạng thái phiếu + thanh toán =====
class ChangeIntakeStatusRequest(BaseModel):
    status: Literal[
        "received", "quoted", "quote_accepted", "paid", "dispatched", "completed", "cancelled"
    ]
    note: Optional[str] = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}


class UpdatePaymentRequest(BaseModel):
    payment_status: Optional[Literal["unpaid", "partial", "paid", "waived"]] = None
    paid_amount: Optional[str] = Field(default=None, max_length=24)
    payment_date: Optional[date] = None
    payment_ref: Optional[str] = Field(default=None, max_length=120)
    payment_note: Optional[str] = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}
