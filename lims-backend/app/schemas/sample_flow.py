"""Schemas Nhận & Chuyển mẫu (GĐ2b) — theo biểu mẫu BM 7.1.01 / BM 7.1.02."""
import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

DispatchStatus = Literal["sent", "received", "in_progress", "done", "returned"]


class CreateIntakeRequest(BaseModel):
    # Mã số mẫu do nhân viên nhận mẫu TỰ ĐẶT (khớp sổ tay/nhãn dán trên mẫu).
    # Để trống thì service sinh mã dự phòng NM-<năm>-<số thứ tự>.
    code: Optional[str] = Field(default=None, max_length=32)
    # m33 — chọn khách từ sổ (tùy chọn). Các trường bên dưới vẫn là bản chụp của
    # phiếu: FE tự điền sẵn từ khách đã chọn nhưng người dùng được sửa đè.
    customer_id: Optional[uuid.UUID] = None
    customer_name: str = Field(min_length=1, max_length=255)
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
    # m42 — ghi tình trạng & số lượng ngay lúc nhận mẫu, đó là thời điểm tự nhiên:
    # nhân viên đang cầm mẫu trên tay. Sửa sau qua PATCH /intakes/{id}/condition.
    sample_count: Optional[int] = Field(default=None, ge=1, le=100000)
    condition_status: Optional[Literal["acceptable", "not_acceptable"]] = None
    condition_note: Optional[str] = Field(default=None, max_length=4000)


class UpdateIntakeRequest(BaseModel):
    # Sửa được để chữa mã gõ nhầm — service kiểm trùng trước khi ghi.
    code: Optional[str] = Field(default=None, max_length=32)
    customer_id: Optional[uuid.UUID] = None
    customer_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    note: Optional[str] = None
    # `status` ĐÃ BỎ KHỎI ĐÂY — CỐ Ý.
    # PATCH này chỉ có require_permission("intake","manage") và service ghi bằng setattr,
    # nên nhận status ở đây là một đường đổi trạng thái THỨ HAI bỏ qua cả state machine
    # INTAKE_NEXT lẫn kiểm vai trò _privileged mà POST /intakes/{id}/status áp dụng —
    # nhảy thẳng received → completed, bỏ qua báo giá và thanh toán.
    # Đổi trạng thái: POST /intakes/{intake_id}/status
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
    intake_item_id: Optional[uuid.UUID] = None                   # m38 — dòng khách đã đặt
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
    # m38 — giao việc cho một dòng KHÁCH ĐÃ ĐẶT. Bỏ trống thì hệ thống tự sinh dòng
    # đặt hàng tương ứng (đường tương thích với giao diện cũ).
    intake_item_id: Optional[uuid.UUID] = None
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
    """Phòng nhận mẫu sửa NỘI DUNG HÀNH CHÍNH của lượt chuyển (quyền dispatch:update).

    m37 đã BỎ `status`, `ket_qua`, `don_vi`, `phuong_phap`, `can_bo` khỏi đây. Chúng
    là phần việc của người thực hiện phép thử và chuyển sang PATCH /dispatches/{id}/result
    với quyền riêng `dispatch:result`. Gộp chung chính là lý do m36 buộc phải cắt quyền
    ghi kết quả của cả khối lab để thực thi được yêu cầu "chỉ reception sửa phiếu".
    """
    sample_name: Optional[str] = Field(default=None, max_length=500)
    quantity: Optional[int] = Field(default=None, ge=1, le=10000)
    note: Optional[str] = None

    model_config = {"extra": "forbid"}


class UpdateDispatchResultRequest(BaseModel):
    """Phòng lab ghi kết quả + trạng thái thực hiện (quyền dispatch:result, m37).

    KHÔNG có `can_bo` / `performed_by`: danh tính người thực hiện lấy từ tài khoản
    đăng nhập. Nhận nó từ client thì lại đúng bằng ô text gõ hộ mà m37 sinh ra để
    loại bỏ.
    """
    status: Optional[DispatchStatus] = None
    don_vi: Optional[str] = Field(default=None, max_length=100)
    phuong_phap: Optional[str] = None
    ket_qua: Optional[str] = None

    model_config = {"extra": "forbid"}


# ── Response model (test kiến trúc test_response_contract chặn endpoint MỚI thiếu) ──
class DispatchFileOut(BaseModel):
    id: uuid.UUID
    file_name: str
    mime: Optional[str] = None
    size: Optional[int] = None
    uploaded_at: Optional[datetime] = None


class DispatchOut(BaseModel):
    """Khớp sample_flow_service._serialize_dispatch().

    `customer_name` và `customer_info_masked` phản ánh cơ chế che PII với khối lab
    (m26) nên đều là tuỳ chọn — payload của người bị che thiếu/đổi giá trị.
    """
    id: uuid.UUID
    intake_id: uuid.UUID
    intake_code: Optional[str] = None
    customer_name: Optional[str] = None
    customer_info_masked: Optional[bool] = None
    sample_name: Optional[str] = None
    quantity: int
    chi_tieu: str
    don_vi: Optional[str] = None
    phuong_phap: Optional[str] = None
    ket_qua: Optional[str] = None
    can_bo: Optional[str] = None
    performed_by: Optional[uuid.UUID] = None
    performed_by_name: Optional[str] = None
    performed_at: Optional[datetime] = None
    # m40 — trạng thái duyệt, suy từ sample_results của phần việc tương ứng.
    result_id: Optional[uuid.UUID] = None
    result_version: Optional[int] = None
    result_approval_status: Optional[str] = None
    result_approved_by_name: Optional[str] = None
    result_approved_at: Optional[datetime] = None
    test_parameter_id: Optional[uuid.UUID] = None
    unit_price: Optional[str] = None
    target_department_id: uuid.UUID
    target_department_name: Optional[str] = None
    status: str
    next_statuses: list[str] = []
    note: Optional[str] = None
    dispatched_by: Optional[uuid.UUID] = None
    dispatched_by_name: Optional[str] = None
    dispatched_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    files: list[DispatchFileOut] = []


class DispatchResponse(BaseModel):
    success: bool
    data: DispatchOut


class SubmitDispatchResultOut(BaseModel):
    """Khớp result_service.enter_result() — phiên bản kết quả vừa tạo."""
    id: uuid.UUID
    assignment_id: uuid.UUID
    version: int
    result_data: dict
    entered_by: uuid.UUID
    entered_at: datetime
    approval_status: str
    is_current: bool
    assignment_status_after: str
    sample_status_after: str


class SubmitDispatchResultResponse(BaseModel):
    success: bool
    data: SubmitDispatchResultOut


class SubmitDispatchResultRequest(BaseModel):
    """Gửi kết quả đi duyệt (m40). Nội dung lấy từ chính cột đã điền trên phiếu."""
    note: Optional[str] = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}


# ===== m38: CHỈ TIÊU KHÁCH ĐẶT (tách khỏi phiếu giao việc cho lab) =====
class IntakeItemInput(BaseModel):
    """Một dòng khách đặt. Chọn từ danh mục (test_parameter_id) HOẶC gõ tên tự do."""
    test_parameter_id: Optional[uuid.UUID] = None
    parameter_name: Optional[str] = Field(default=None, max_length=500)
    method: Optional[str] = Field(default=None, max_length=500)
    unit: Optional[str] = Field(default=None, max_length=50)
    sample_name: Optional[str] = Field(default=None, max_length=500)
    quantity: Optional[int] = Field(default=1, ge=1, le=10000)
    note: Optional[str] = None

    model_config = {"extra": "forbid"}


class CreateIntakeItemsRequest(BaseModel):
    items: list[IntakeItemInput] = Field(min_length=1, max_length=100)

    model_config = {"extra": "forbid"}


class UpdateIntakeItemRequest(BaseModel):
    parameter_name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    method: Optional[str] = Field(default=None, max_length=500)
    unit: Optional[str] = Field(default=None, max_length=50)
    sample_name: Optional[str] = Field(default=None, max_length=500)
    quantity: Optional[int] = Field(default=None, ge=1, le=10000)
    # Chuỗi số — tránh sai số float trên tiền, cùng quy ước với test_parameters.
    unit_price: Optional[str] = Field(default=None, max_length=24)
    note: Optional[str] = None

    model_config = {"extra": "forbid"}


class IntakeItemOut(BaseModel):
    id: uuid.UUID
    intake_id: uuid.UUID
    sort_order: int
    test_parameter_id: Optional[uuid.UUID] = None
    parameter_name: str
    method: Optional[str] = None
    unit: Optional[str] = None
    sample_name: Optional[str] = None
    quantity: int
    unit_price: Optional[str] = None
    note: Optional[str] = None
    # Số lượt đã giao cho phòng lab — FE khoá nút xoá khi > 0.
    dispatch_count: int
    created_at: datetime


class IntakeItemResponse(BaseModel):
    success: bool
    data: IntakeItemOut


class IntakeItemListResponse(BaseModel):
    success: bool
    data: list[IntakeItemOut]


# ===== m43: người liên hệ theo VAI TRÒ trên phiếu =====
ContactRole = Literal["courier", "technical", "result_recipient", "billing"]


class IntakeContactInput(BaseModel):
    role: ContactRole
    full_name: str = Field(min_length=1, max_length=255)
    job_title: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    note: Optional[str] = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}


class SetIntakeContactsRequest(BaseModel):
    """Đặt LẠI cả bộ — màn hình quầy hiển thị cả bốn vai cùng lúc."""
    contacts: list[IntakeContactInput] = Field(default_factory=list, max_length=4)

    model_config = {"extra": "forbid"}


class IntakeContactOut(BaseModel):
    id: uuid.UUID
    intake_id: uuid.UUID
    role: str
    role_label: str
    full_name: str
    job_title: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    note: Optional[str] = None


class IntakeContactListResponse(BaseModel):
    success: bool
    data: list[IntakeContactOut]


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
        "received", "quoted", "quote_accepted", "paid", "dispatched", "completed",
        "cancelled", "rejected",
    ]
    # m42 — BẮT BUỘC khi status='rejected'. Service enforce, không để ở đây, vì điều
    # kiện phụ thuộc giá trị trường khác và thông báo lỗi cần nói rõ nghiệp vụ.
    note: Optional[str] = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}


class IntakeOut(BaseModel):
    """Khớp sample_flow_service._serialize_intake().

    Trường PII là tuỳ chọn vì m26 che chúng với khối lab; `dispatches` chỉ có ở đường
    list/detail (with_dispatches=True). Khai đủ để response_model không cắt mất field
    mà giao diện đang dùng.
    """
    id: uuid.UUID
    code: str
    customer_id: Optional[uuid.UUID] = None
    customer_name: Optional[str] = None
    customer_info_masked: Optional[bool] = None
    customer_info_request_status: Optional[str] = None
    description: Optional[str] = None
    note: Optional[str] = None
    status: str
    status_label: Optional[str] = None
    next_statuses: list[str] = []
    payment_status: Optional[str] = None
    paid_amount: Optional[str] = None
    payment_date: Optional[date] = None
    payment_ref: Optional[str] = None
    payment_note: Optional[str] = None
    dispatch_note: Optional[str] = None
    address: Optional[str] = None
    tax_code: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    due_date: Optional[str] = None
    due_date_at: Optional[date] = None
    result_language: Optional[str] = None
    return_method: Optional[str] = None
    fee_note: Optional[str] = None
    other_request: Optional[str] = None
    # m42 — tình trạng & số lượng mẫu, dấu vết quyết định từ chối.
    sample_count: Optional[int] = None
    condition_status: Optional[str] = None
    condition_note: Optional[str] = None
    rejected_reason: Optional[str] = None
    decided_by_name: Optional[str] = None
    decided_at: Optional[datetime] = None
    department_id: Optional[uuid.UUID] = None
    department_name: Optional[str] = None
    received_by: Optional[uuid.UUID] = None
    received_by_name: Optional[str] = None
    received_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    files: list[DispatchFileOut] = []
    dispatches: Optional[list[DispatchOut]] = None


class IntakeResponse(BaseModel):
    success: bool
    data: IntakeOut


class RecordIntakeConditionRequest(BaseModel):
    """Tình trạng & số lượng mẫu lúc tiếp nhận (m42, BM 7.1.01)."""
    sample_count: Optional[int] = Field(default=None, ge=1, le=100000)
    condition_status: Optional[Literal["acceptable", "not_acceptable"]] = None
    condition_note: Optional[str] = Field(default=None, max_length=4000)

    model_config = {"extra": "forbid"}


class UpdatePaymentRequest(BaseModel):
    payment_status: Optional[Literal["unpaid", "partial", "paid", "waived"]] = None
    paid_amount: Optional[str] = Field(default=None, max_length=24)
    payment_date: Optional[date] = None
    payment_ref: Optional[str] = Field(default=None, max_length=120)
    payment_note: Optional[str] = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}
