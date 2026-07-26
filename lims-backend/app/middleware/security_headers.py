"""Security-headers middleware (M7) — baseline browser hardening cho mọi response.

Trước đây stack middleware KHÔNG set header bảo mật nào (PRODUCTION_READINESS_REVIEW
§Security: "No security-headers middleware anywhere") — không HSTS/CSP/nosniff/frame
guard, khuếch đại blast radius của stored-XSS. Middleware này thêm bộ header phòng thủ
tối thiểu:

- X-Content-Type-Options: nosniff — chặn MIME-sniffing (bổ trợ fix inline attachment).
- X-Frame-Options: DENY + CSP frame-ancestors 'none' — chống clickjacking.
- Referrer-Policy — không rò rỉ URL nội bộ qua Referer.
- Content-Security-Policy — CSP tối thiểu cho API JSON; API không tự render HTML nên
  default-src 'none' đủ chặt mà không phá gì. (Frontend SPA phục vụ qua nginx riêng có
  CSP riêng — middleware này chỉ áp cho response của API backend.)
- Strict-Transport-Security — CHỈ bật ở production (tránh ghim HSTS khi dev chạy HTTP
  trên localhost).
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings

_BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
_HSTS_VALUE = "max-age=31536000; includeSubDomains"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for key, value in _BASE_HEADERS.items():
            response.headers.setdefault(key, value)
        if settings.is_production:
            response.headers.setdefault("Strict-Transport-Security", _HSTS_VALUE)
        return response
