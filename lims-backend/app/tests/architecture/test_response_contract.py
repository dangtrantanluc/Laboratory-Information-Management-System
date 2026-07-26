"""Chặn nợ hợp đồng API (M-01).

294 endpoint hiện KHÔNG khai báo `response_model`, nên OpenAPI không mô tả gì về
dữ liệu trả về và frontend phải viết tay 1.964 dòng type để đoán. Đổi tên một
trường ở backend không gây lỗi biên dịch ở đâu — nó hỏng lúc chạy, trên máy
người dùng.

Test này KHÔNG bắt sửa 294 endpoint cũ. Nó chỉ bảo đảm không có cái thứ 295.

`response_model_legacy.txt` chỉ được phép NGẮN ĐI:
  - `test_no_new_endpoint_without_response_model` chặn endpoint mới thiếu schema
  - `test_allowlist_only_shrinks` buộc xoá entry khi nợ đã trả

Xem MAINTAINABILITY_PLAN.md §T0.1.
"""
import pathlib

from fastapi.routing import APIRoute

from app.main import app

_ALLOWLIST_FILE = pathlib.Path(__file__).parent / "response_model_legacy.txt"


def _load_allowlist() -> set[str]:
    if not _ALLOWLIST_FILE.exists():
        return set()
    return {
        line.strip()
        for line in _ALLOWLIST_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _endpoint_key(route: APIRoute) -> str:
    """Khoá ổn định cho một endpoint: 'METHOD /đường/dẫn'."""
    method = sorted(route.methods - {"HEAD", "OPTIONS"})[0]
    return f"{method} {route.path}"


def _needs_contract(route: APIRoute) -> bool:
    """Endpoint có trả JSON body thì phải khai response_model."""
    if route.status_code == 204:  # No Content — không có body
        return False
    return route.response_model is None


def _current_offenders() -> set[str]:
    return {
        _endpoint_key(r)
        for r in app.routes
        if isinstance(r, APIRoute) and r.methods - {"HEAD", "OPTIONS"} and _needs_contract(r)
    }


def test_no_new_endpoint_without_response_model():
    """Endpoint MỚI bắt buộc có response_model."""
    offenders = sorted(_current_offenders() - _load_allowlist())
    assert not offenders, (
        f"{len(offenders)} endpoint mới thiếu response_model.\n"
        "Khai một schema Pydantic và dùng response_model=... "
        "(xem MAINTAINABILITY_PLAN.md §T0.1).\n"
        "KHÔNG thêm vào response_model_legacy.txt — danh sách đó chỉ được ngắn đi.\n"
        + "\n".join(f"  - {o}" for o in offenders)
    )


def test_allowlist_only_shrinks():
    """Entry trỏ tới endpoint đã có response_model = nợ đã trả, phải xoá.

    Giữ lại sẽ che mất lần hồi quy sau: nếu ai đó gỡ response_model của endpoint
    đó, allowlist cũ sẽ âm thầm cho qua.
    """
    stale = sorted(_load_allowlist() - _current_offenders())
    assert not stale, (
        f"{len(stale)} endpoint đã có response_model — xoá khỏi "
        "response_model_legacy.txt:\n" + "\n".join(f"  - {s}" for s in stale)
    )


def test_allowlist_file_exists():
    """Xoá nhầm file allowlist sẽ làm hai test trên vô hiệu một cách im lặng."""
    assert _ALLOWLIST_FILE.exists(), (
        f"Thiếu {_ALLOWLIST_FILE.name}. Sinh lại theo MAINTAINABILITY_PLAN.md §T0.1."
    )
