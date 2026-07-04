"""Middleware gắn X-Correlation-Id xuyên FE→BE→DB (rule logging.md).

Nếu client không gửi → server tự sinh. Luôn trả lại trong response header.
Lưu vào request.state.correlation_id để exception handler + audit service dùng.
"""
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

CORRELATION_HEADER = "X-Correlation-Id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        request.state.correlation_id = cid
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = cid
        return response
