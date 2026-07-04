"""Schemas M6 — Báo cáo & Thống kê."""
import re

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
