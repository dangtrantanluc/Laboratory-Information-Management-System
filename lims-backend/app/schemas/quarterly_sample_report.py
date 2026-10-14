"""Schemas Báo cáo mẫu phân tích theo quý — m54."""
import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

ReportStatus = Literal["draft", "submitted", "returned", "locked"]
Matrix = Literal["soil", "water", "fertilizer", "feed", "food", "quarantine", "molecular", "other"]


# ── Requests ──────────────────────────────────────────────────────
class EnsureSampleReportRequest(BaseModel):
    year: int = Field(ge=2000, le=2100)
    quarter: int = Field(ge=1, le=4)


class SampleReportItemRequest(BaseModel):
    sample_code: str = Field(min_length=1, max_length=50)
    received_date: date
    matrix: Matrix
    matrix_other: Optional[str] = Field(default=None, max_length=255)
    quantity: int = Field(ge=1, le=100000)
    test_parameter_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    extra_criteria: Optional[str] = Field(default=None, max_length=2000)
    note: Optional[str] = Field(default=None, max_length=2000)

    model_config = {"extra": "forbid"}


class BatchSampleReportItemsRequest(BaseModel):
    """Nhập nhiều mẫu một lần — tất cả hoặc không dòng nào (xem create_items_batch)."""
    items: list[SampleReportItemRequest] = Field(min_length=1, max_length=500)

    model_config = {"extra": "forbid"}


class SubmitSampleReportRequest(BaseModel):
    lab_note: Optional[str] = Field(default=None, max_length=2000)
    # Nộp báo cáo không có dòng nào = xác nhận "quý này không phát sinh mẫu".
    confirm_empty: bool = False


class ReasonRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


# ── Responses ─────────────────────────────────────────────────────
class CriterionOut(BaseModel):
    test_parameter_id: Optional[uuid.UUID]
    name: str


class SampleReportItemOut(BaseModel):
    id: uuid.UUID
    sample_code: str
    received_date: date
    matrix: str
    matrix_label: str
    matrix_other: Optional[str]
    quantity: int
    criteria: list[CriterionOut]
    extra_criteria: Optional[str]
    criteria_text: str
    note: Optional[str]
    created_by_name: Optional[str]
    updated_at: datetime


class SampleReportOut(BaseModel):
    id: uuid.UUID
    department_id: uuid.UUID
    department_name: str
    department_code: str
    year: int
    quarter: int
    status: ReportStatus
    status_label: str
    lab_note: Optional[str]
    submitted_by_name: Optional[str]
    submitted_at: Optional[datetime]
    returned_by_name: Optional[str]
    returned_at: Optional[datetime]
    return_reason: Optional[str]
    locked_by_name: Optional[str]
    locked_at: Optional[datetime]
    item_count: int
    total_quantity: int
    items: list[SampleReportItemOut]
    # Quyền của NGƯỜI ĐANG XEM trên báo cáo này — giao diện dựa vào đây để hiện nút.
    can_edit: bool
    can_review: bool


class DepartmentRef(BaseModel):
    id: uuid.UUID
    name: str
    code: str


class CurrentSampleReportOut(BaseModel):
    department: DepartmentRef
    year: int
    quarter: int
    report: Optional[SampleReportOut]
    can_edit: bool


class OverviewRow(BaseModel):
    department: DepartmentRef
    report_id: Optional[uuid.UUID]
    status: Optional[ReportStatus]
    status_label: str
    item_count: int
    total_quantity: int
    submitted_at: Optional[datetime]
    locked_at: Optional[datetime]


class SampleReportResponse(BaseModel):
    success: bool
    data: SampleReportOut


class SampleReportItemResponse(BaseModel):
    success: bool
    data: SampleReportItemOut


class CurrentSampleReportResponse(BaseModel):
    success: bool
    data: CurrentSampleReportOut


class SampleReportOverviewResponse(BaseModel):
    success: bool
    data: list[OverviewRow]


# ── Thống kê (tab "Báo cáo phân tích mẫu" ở trang Báo cáo & Thống kê) ──
class StatsReportRef(BaseModel):
    department_id: uuid.UUID
    quarter: int
    status: ReportStatus
    status_label: str


class StatsCell(BaseModel):
    department_id: uuid.UUID
    quarter: int
    matrix: str
    matrix_label: str
    items: int
    quantity: int


class TopCriterion(BaseModel):
    name: str
    items: int


class SampleReportStatsOut(BaseModel):
    year: int
    quarter: Optional[int]
    include_unlocked: bool
    departments: list[DepartmentRef]
    reports: list[StatsReportRef]
    cells: list[StatsCell]
    top_criteria: list[TopCriterion]


class SampleReportStatsResponse(BaseModel):
    success: bool
    data: SampleReportStatsOut
