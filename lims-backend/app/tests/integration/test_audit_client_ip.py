"""Nhật ký kiểm toán phải ghi IP THẬT của người dùng (M-09/T1.5).

Trước bản sửa: 25/26 router tự viết `_ip()` đọc thẳng `request.client.host`, tức
là IP của nginx. Trên dữ liệu thật, 545/1.442 dòng audit_logs ghi 172.21.0.6
(container nginx) và 869 dòng ghi 172.21.0.1 (gateway docker) — với hệ thống chịu
ISO/IEC 17025, cột IP của nhật ký kiểm toán gần như không truy vết được ai.

Bản sửa F-04 đã dạy rate_limit đọc X-Real-IP nhưng 25 bản sao trong router không
được sửa theo. Đó chính là cái giá của trùng lặp: sửa một chỗ không sửa 25 chỗ kia.
"""
from sqlalchemy import text

from app.tests.conftest import requires_db


@requires_db
def test_audit_log_records_real_client_ip(client, as_role, db):
    """IP ghi vào audit_logs phải là X-Real-IP, không phải IP của proxy."""
    as_role("admin")
    res = client.post(
        "/api/v1/customers",
        json={"name": "Công ty Kiểm Tra IP"},
        headers={"X-Real-IP": "203.0.113.45"},
    )
    assert res.status_code == 201, res.text

    ip = db.execute(
        text(
            "SELECT ip FROM audit_logs WHERE action = 'CUSTOMER_CREATE' "
            "ORDER BY at DESC LIMIT 1"
        )
    ).scalar_one()
    assert str(ip) == "203.0.113.45", (
        f"audit_logs.ip = {ip!r} — router đang ghi IP của proxy thay vì của người dùng"
    )


@requires_db
def test_no_router_defines_its_own_ip_helper():
    """Chặn hồi quy: không router nào được tự viết lại _ip().

    Bản sao mới sẽ lại bỏ qua X-Real-IP và làm hỏng nhật ký kiểm toán một cách
    im lặng — không lỗi, không log, chỉ là dữ liệu sai.
    """
    import pathlib

    routers = pathlib.Path(__file__).resolve().parents[2] / "routers"
    offenders = [
        p.name for p in routers.glob("*.py") if "def _ip(" in p.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        "Router tự viết _ip() thay vì dùng app.core.request_meta.client_ip: "
        f"{offenders}"
    )
