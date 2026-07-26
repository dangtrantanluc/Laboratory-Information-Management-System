"""Quét IDOR trên toàn bộ route có tham số {id} (R8.3).

Vì sao cần test tự động: hệ thống có 294 endpoint. Rà tay từng cái để chắc rằng
user A không đọc/sửa được tài nguyên của user B là không khả thi, và mỗi module
mới lại thêm bề mặt tấn công.

Test này KHÔNG gọi database. Nó kiểm bất biến ở tầng khai báo route — thứ có thể
kiểm mà không cần dữ liệu thật:

  1. Mọi route ngoài allowlist công khai PHẢI có dependency xác thực. Route
     `/{id}` quên `Depends(get_current_user)` là IDOR nghiêm trọng nhất: bất kỳ
     ai cũng đọc được.
  2. Mọi route ghi (POST/PATCH/PUT/DELETE) phải có xác thực.

Phần "user A không đọc được tài nguyên của user B" cần fixture DB thật; đó là
việc của test tích hợp (cần TEST_DATABASE_URL). Test này là lưới chắn đầu tiên,
chạy được ở mọi môi trường kể cả CI không có Postgres.
"""
import pytest
from fastapi.routing import APIRoute

from app.main import app

# Route CỐ Ý công khai. Thêm vào đây phải kèm lý do — mỗi dòng là một quyết định
# bảo mật, không phải danh sách để nới cho test xanh.
PUBLIC_ROUTES = {
    "/health": "liveness probe, không lộ dữ liệu",
    "/health/ready": "readiness probe, chỉ trả trạng thái phụ thuộc",
    "/metrics": "Prometheus scrape — chặn ở tầng mạng, không publish ra ngoài",
    "/api/v1/auth/login": "phải công khai để đăng nhập",
    "/api/v1/auth/refresh": "xác thực bằng cookie refresh, không phải access token",
    "/api/v1/auth/register": "m30 tự đăng ký",
    "/api/v1/auth/verify-email": "xác thực bằng token dùng-một-lần trong mail",
    "/api/v1/auth/forgot-password": "phải công khai",
    "/api/v1/auth/reset-password": "xác thực bằng token dùng-một-lần trong mail",
    "/api/v1/auth/registration-config": "chỉ trả cờ bật/tắt đăng ký",
    "/openapi.json": "chỉ bật ở môi trường không phải production",
    "/docs": "chỉ bật ở môi trường không phải production",
    "/docs/oauth2-redirect": "chỉ bật ở môi trường không phải production",
    "/redoc": "chỉ bật ở môi trường không phải production",
}

WRITE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}


def _auth_dependency_names(route: APIRoute) -> set[str]:
    """Tên mọi dependency (kể cả dependency lồng) của route."""
    names = set()
    for dep in route.dependant.dependencies:
        if dep.call is not None:
            names.add(getattr(dep.call, "__name__", ""))
        for sub in dep.dependencies:
            if sub.call is not None:
                names.add(getattr(sub.call, "__name__", ""))
    # Dependency khai bằng Depends() trong chữ ký hàm (vd user: CurrentUser = Depends(...))
    for param in route.dependant.dependencies:
        names.add(getattr(param.call, "__name__", ""))
    return names


def _is_authenticated(route: APIRoute) -> bool:
    names = _auth_dependency_names(route)
    return any(
        n in names
        for n in ("get_current_user", "require_roles", "_require", "admin_only")
    ) or any("require" in n or "current_user" in n for n in names if n)


ALL_ROUTES = [r for r in app.routes if isinstance(r, APIRoute)]
ID_ROUTES = [r for r in ALL_ROUTES if "{" in r.path]
WRITE_ROUTES = [r for r in ALL_ROUTES if r.methods & WRITE_METHODS]


def test_route_inventory_is_not_empty():
    """Bảo vệ chính test này: nếu app đổi cấu trúc và không route nào được thu
    thập, các test dưới sẽ xanh một cách vô nghĩa."""
    assert len(ALL_ROUTES) > 200, f"chỉ thu được {len(ALL_ROUTES)} route — nghi ngờ sai"
    assert len(ID_ROUTES) > 50, f"chỉ thu được {len(ID_ROUTES)} route có {{id}}"


@pytest.mark.parametrize("route", ID_ROUTES, ids=lambda r: f"{sorted(r.methods)[0]} {r.path}")
def test_id_routes_require_authentication(route: APIRoute):
    """Route nhận id từ URL mà không xác thực = ai cũng đọc được tài nguyên người khác."""
    if route.path in PUBLIC_ROUTES:
        pytest.skip(f"công khai có chủ đích: {PUBLIC_ROUTES[route.path]}")
    assert _is_authenticated(route), (
        f"IDOR: {sorted(route.methods)} {route.path} nhận tham số từ URL nhưng "
        f"KHÔNG có dependency xác thực"
    )


@pytest.mark.parametrize("route", WRITE_ROUTES, ids=lambda r: f"{sorted(r.methods)[0]} {r.path}")
def test_write_routes_require_authentication(route: APIRoute):
    """Endpoint ghi không xác thực = ai cũng sửa/xoá dữ liệu."""
    if route.path in PUBLIC_ROUTES:
        pytest.skip(f"công khai có chủ đích: {PUBLIC_ROUTES[route.path]}")
    assert _is_authenticated(route), (
        f"{sorted(route.methods)} {route.path} ghi dữ liệu nhưng KHÔNG xác thực"
    )


def test_public_allowlist_has_no_stale_entries():
    """Allowlist phải phản ánh route thật. Entry cũ còn sót lại sẽ âm thầm miễn
    trừ một đường dẫn mà sau này được dùng cho việc khác."""
    # So với MỌI route của app, không chỉ APIRoute: /docs, /redoc, /openapi.json
    # do FastAPI tự sinh dưới dạng starlette.routing.Route.
    existing = {getattr(r, "path", None) for r in app.routes}
    stale = {p for p in PUBLIC_ROUTES if p not in existing}
    assert not stale, f"allowlist còn entry không tồn tại: {sorted(stale)}"
