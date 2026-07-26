"""Middleware gắn X-Correlation-Id xuyên FE→BE→DB (rule logging.md).

Nếu client không gửi → server tự sinh. Luôn trả lại trong response header.
Lưu vào request.state.correlation_id (cho exception handler + audit service) VÀ vào
ContextVar (app.core.context) để mọi log record tự gắn correlationId qua logging filter.
"""
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.context import reset_correlation_id, set_correlation_id

CORRELATION_HEADER = "X-Correlation-Id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        request.state.correlation_id = cid
        token = set_correlation_id(cid)
        try:
            response = await call_next(request)
        finally:
            reset_correlation_id(token)
        response.headers[CORRELATION_HEADER] = cid
        return response
