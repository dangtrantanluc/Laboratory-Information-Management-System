"""Schemas xuất Excel Nghiên cứu & Đào tạo."""
from pydantic import BaseModel


class ExportKindOut(BaseModel):
    kind: str
    label: str
    # Nhãn trường thời gian mà mục này lọc theo ("Ngày ký", "Năm công bố"…).
    filter_field: str
    # 'date' = lọc chính xác theo ngày; 'year' = dữ liệu gốc chỉ có năm nên khoảng
    # ngày được quy về khoảng năm. Giao diện dùng để chú thích cho người dùng.
    granularity: str


class ExportKindListResponse(BaseModel):
    success: bool
    data: list[ExportKindOut]
