"""Trích thông tin người gọi từ request (M-09/T1.5).

VÌ SAO CẦN FILE NÀY: 25/26 router tự viết một hàm `_ip()` giống hệt nhau:

    def _ip(request: Request) -> Optional[str]:
        return request.client.host if request.client else None

Nó đọc thẳng `request.client.host`, tức là IP của **nginx**, không phải của người
dùng. Bản sửa F-04 (ARCHITECTURE_AUDIT) đã dạy `rate_limit.client_ip()` đọc
X-Real-IP, nhưng 25 bản sao trong router không được sửa theo — trùng lặp là thế:
sửa một chỗ không sửa được 25 chỗ kia.

Hệ quả đo được trên dữ liệu thật: 545/1.442 dòng `audit_logs` ghi `172.21.0.6`
(container nginx) và 869 dòng ghi `172.21.0.1` (gateway docker). Với hệ thống
chịu ISO/IEC 17025, cột IP của nhật ký kiểm toán gần như không truy vết được ai.

Trả `None` chứ không phải chuỗi "unknown": `audit_logs.ip` là cột INET, nhận NULL
nhưng KHÔNG nhận chuỗi tuỳ ý — ghi "unknown" vào đó là DataError lúc chạy.
"""
from typing import Optional

from fastapi import Request


def client_ip(request: Request) -> Optional[str]:
    """IP thật của người dùng cuối, hoặc None nếu không xác định được.

    Tin X-Real-IP vì nginx GHI ĐÈ header này bằng giá trị nó tự xác định (không
    cộng dồn như $proxy_add_x_forwarded_for), và lims-api không publish cổng ra
    host nên không ai gọi thẳng để giả mạo được.
    """
    raw = request.headers.get("x-real-ip")
    if raw:
        # Phòng trường hợp proxy phía trước nối chuỗi — lấy hop đầu tiên.
        return raw.split(",")[0].strip() or None
    return request.client.host if request.client else None
