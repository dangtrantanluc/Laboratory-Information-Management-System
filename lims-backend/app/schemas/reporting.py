"""Schemas M6 — Báo cáo & Thống kê."""
import re
import uuid
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Path nội bộ hợp lệ (chống ghi URL ngoài / injection — §0.9, FR-RPT-009)
_PATH_RE = re.compile(r"^/[a-zA-Z0-9/_\-]*$")


class PageViewRequest(BaseModel):
    """FE ghi 1 lượt xem trang chính (#14). Chỉ path nội bộ, không query nhạy cảm."""

    path: str = Field(min_length=1, max_length=255)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, v: str) -> str:
        v = v.strip()
        # bỏ query string nếu có (server tự lấy; path-only theo contract)
        base = v.split("?", 1)[0]
        if not _PATH_RE.match(base):
            raise ValueError("path không hợp lệ (chỉ path nội bộ)")
        return base


# ═══════════ m50: báo cáo tổng hợp khách hàng (Văn phòng) ═══════════
class CustomerReportRow(BaseModel):
    period: str
    new_customers: int
    active_customers: int
    intakes: int
    # Tiền là CHUỖI, không phải float: Decimal qua float mất độ chính xác, và con số
    # này đi thẳng vào báo cáo tháng gửi lãnh đạo.
    quoted_total: str
    paid_total: str


class TopCustomerOut(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    name: str
    intakes: int
    quoted_total: str
    paid_total: str
    # Phiếu không gắn sổ khách — gộp theo tên đã chụp trên phiếu, nên không tra ngược
    # sang master data được. Nói rõ để người làm báo cáo không tưởng là thiếu dữ liệu.
    is_walk_in: bool


class CustomerReportSummary(BaseModel):
    new_customers: int
    active_customers: int
    total_customers: int
    intakes: int
    quoted_total: str
    paid_total: str


class CustomerReportData(BaseModel):
    summary: CustomerReportSummary
    series: list[CustomerReportRow]
    top_customers: list[TopCustomerOut]


class CustomerReportResponse(BaseModel):
    success: bool
    data: CustomerReportData
    meta: dict
