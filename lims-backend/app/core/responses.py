"""Helper tạo response format chuẩn success (rule api.md)."""
from typing import Any, Optional


def ok(data: Any) -> dict:
    return {"success": True, "data": data}


def paginated(
    items: list, *, page: int, limit: int, total: int
) -> dict:
    return {
        "success": True,
        "data": items,
        "meta": {
            "page": page,
            "limit": limit,
            "total": total,
            "hasNext": page * limit < total,
        },
    }


def normalize_pagination(page: Optional[int], limit: Optional[int]) -> tuple[int, int]:
    """Default 20, max 100 (rule api.md)."""
    p = page if page and page > 0 else 1
    lim = limit if limit and limit > 0 else 20
    if lim > 100:
        lim = 100
    return p, lim
