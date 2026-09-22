"""Schemas PHIẾU KẾT QUẢ THỬ NGHIỆM (m46) — BM 7.8/01/RIBE.

Mọi endpoint của module khai `response_model` tường minh: test kiến trúc
`tests/architecture/test_response_contract.py` chặn endpoint MỚI thiếu hợp đồng, và
allowlist nợ cũ chỉ được phép ngắn đi. Envelope {"success", "data"} khớp
`app/core/responses.ok()`.
"""
import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

TestReportStatus = Literal["draft", "issued", "delivered", "revoked"]
DeliveryMethod = Literal["direct", "mail", "email"]


# ═══════════════════════════ Request ═══════════════════════════


class CreateTestReportRequest(BaseModel):
    """Lập bản nháp. Bỏ trống `report_no` thì service sinh theo mã phiếu nhận.

    KHÔNG nhận `status`, `version`, `issued_by`, `supersedes_id`: chúng do vòng đời
    quyết định. Nhận `status` ở đây là mở một đường phát hành THỨ HAI bỏ qua state
    machine — đúng lỗi mà UpdateIntakeRequest đã phải gỡ ra.
    """

    report_no: Optional[str] = Field(default=None, max_length=64)
    title: Optional[str] = Field(default=None, max_length=255)
    note: Optional[str] = Field(default=None, max_length=4000)
    # Ngày trả kết quả in trên phiếu. Bỏ trống lúc lập nháp cũng được — bắt buộc khi
    # phát hành (BR-04), và service điền sẵn hôm nay cho màn hình.
    issued_at: Optional[date] = None

    model_config = {"extra": "forbid"}


class UpdateTestReportRequest(BaseModel):
    """Sửa bản NHÁP. Đã phát hành thì service từ chối (BR-06)."""

    report_no: Optional[str] = Field(default=None, min_length=1, max_length=64)
    title: Optional[str] = Field(default=None, max_length=255)
    note: Optional[str] = Field(default=None, max_length=4000)
    issued_at: Optional[date] = None

    model_config = {"extra": "forbid"}


class IssueTestReportRequest(BaseModel):
    """Phát hành. `issued_at` bỏ trống thì giữ ngày đã nhập, không có thì lấy hôm nay."""

    issued_at: Optional[date] = None

    model_config = {"extra": "forbid"}


class DeliverTestReportRequest(BaseModel):
    """Ghi nhận đã trao khách — mốc "trả kết quả" thật của phiếu."""

    delivery_method: DeliveryMethod
    # Điền sẵn từ liên hệ vai 'result_recipient' của phiếu (m43), sửa đè được.
    delivered_to: Optional[str] = Field(default=None, max_length=255)
    delivered_at: Optional[datetime] = None
    delivery_note: Optional[str] = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}


class RevokeTestReportRequest(BaseModel):
    """Thu hồi. Lý do BẮT BUỘC — CHECK ck_tr_revoked chốt lại ở tầng DB."""

    reason: str = Field(min_length=1, max_length=4000)

    model_config = {"extra": "forbid"}


class ReviseTestReportRequest(BaseModel):
    """Tạo bản sửa đổi: bản ghi MỚI version+1, bản cũ chuyển 'revoked'.

    Không viết đè bản cũ — khách đang cầm nó trên tay, và ISO/IEC 17025 §7.8.8.2 đòi
    bản sửa phải nhận diện được và tham chiếu được tới bản gốc.
    """

    reason: str = Field(min_length=1, max_length=4000)
    report_no: Optional[str] = Field(default=None, max_length=64)

    model_config = {"extra": "forbid"}


# ═══════════════════════════ Response ═══════════════════════════


class TestReportFileOut(BaseModel):
    id: uuid.UUID
    file_name: str
    mime: Optional[str] = None
    size: Optional[int] = None
    uploaded_by_name: Optional[str] = None
    uploaded_at: datetime


class TestReportOut(BaseModel):
    id: uuid.UUID
    intake_id: uuid.UUID
    intake_code: Optional[str] = None
    report_no: str
    version: int
    supersedes_id: Optional[uuid.UUID] = None
    supersedes_report_no: Optional[str] = None
    revision_reason: Optional[str] = None
    status: TestReportStatus
    status_label: str
    # Bước hợp lệ kế tiếp — FE dựng đúng danh sách nút bấm được, thay vì hiện mọi nút
    # rồi để backend từ chối. Cùng quy ước `next_statuses` của phiếu nhận/chuyển mẫu.
    next_statuses: list[str] = []
    title: Optional[str] = None
    note: Optional[str] = None
    issued_at: Optional[date] = None
    issued_by: Optional[uuid.UUID] = None
    issued_by_name: Optional[str] = None
    delivered_at: Optional[datetime] = None
    delivery_method: Optional[str] = None
    delivery_method_label: Optional[str] = None
    delivered_to: Optional[str] = None
    delivery_note: Optional[str] = None
    revoked_at: Optional[datetime] = None
    revoked_by_name: Optional[str] = None
    revoked_reason: Optional[str] = None
    # BR-12 — số ngày trả trễ so với ngày hẹn trên phiếu (due_date_at, m39). None khi
    # chưa phát hành hoặc phiếu không có ngày hẹn phân giải được; âm = trả sớm.
    days_late: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    files: list[TestReportFileOut] = []


class TestReportResponse(BaseModel):
    success: bool
    data: TestReportOut


class TestReportListResponse(BaseModel):
    success: bool
    data: list[TestReportOut]


class TestReportFileResponse(BaseModel):
    success: bool
    data: TestReportFileOut


class TestReportDownloadOut(TestReportFileOut):
    """Kết quả cấp link tải — presigned URL TTL ngắn, không phát tán link vĩnh viễn."""

    download_url: str
    url_expires_at: datetime


class TestReportDownloadResponse(BaseModel):
    success: bool
    data: TestReportDownloadOut


class DeleteTestReportOut(BaseModel):
    id: uuid.UUID
    deleted: bool


class DeleteTestReportResponse(BaseModel):
    success: bool
    data: DeleteTestReportOut
