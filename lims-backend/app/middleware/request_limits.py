"""Request-limits middleware — chặn SỚM upload quá cỡ theo Content-Length.

Trước đây mọi route upload đọc TOÀN BỘ file vào RAM (`await file.read()`) rồi mới kiểm
tra size → N upload lớn đồng thời có thể cạn bộ nhớ (PRODUCTION_READINESS_REVIEW M7).
Middleware này từ chối multipart/form-data có Content-Length vượt trần NGAY trước khi
body được đọc, cho mọi route upload cùng lúc (không cần sửa từng endpoint).

Chỉ áp cho `multipart/form-data` (đường upload file) — KHÔNG đụng JSON body. Ngưỡng nới
thêm _MULTIPART_OVERHEAD cho phần khung multipart để không từ chối nhầm file đúng cỡ tối
đa; kiểm tra size CHÍNH XÁC theo bytes thực vẫn do attachment_common.check_size() làm sau
khi đọc (Content-Length có thể vắng/giả với chunked transfer).
"""
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings

logger = logging.getLogger("lims.request_limits")

# Dôi dư cho boundary/headers của multipart để không chặn nhầm file ~ đúng cỡ tối đa.
_MULTIPART_OVERHEAD = 1 * 1024 * 1024


class RequestLimitsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            ctype = request.headers.get("content-type", "")
            if ctype.startswith("multipart/form-data"):
                cl = request.headers.get("content-length")
                if cl:
                    try:
                        if int(cl) > settings.max_upload_size_bytes + _MULTIPART_OVERHEAD:
                            return JSONResponse(
                                status_code=413,
                                content={
                                    "success": False,
                                    "error": {
                                        "code": "FILE_TOO_LARGE",
                                        "message": (
                                            "Tệp vượt quá giới hạn "
                                            f"{settings.max_upload_size_bytes // (1024 * 1024)}MB"
                                        ),
                                    },
                                },
                            )
                    except ValueError:
                        pass  # header không phải số → để check_size() sau xử lý
        return await call_next(request)
