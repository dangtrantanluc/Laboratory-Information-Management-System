"""Business exceptions + global handlers — response format chuẩn (rule api.md / logging.md).

Mọi lỗi ra client theo dạng:
{ "success": false, "error": { code, message, details, correlationId } }
KHÔNG bao giờ lộ stack trace ra client (chỉ log ở BE).
"""
import logging
from typing import Any, List, Optional

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("lims.exceptions")


class AppException(Exception):
    """Lỗi nghiệp vụ có mã rõ ràng (SNAKE_CASE) + HTTP status."""

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[List[dict]] = None,
    ):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details
        super().__init__(message)


# --- Shortcut factory cho các lỗi M7 hay dùng (đồng bộ danh mục error code §3 contract) ---


def unauthorized(message: str = "Chưa xác thực hoặc token không hợp lệ") -> AppException:
    return AppException("UNAUTHORIZED", message, status.HTTP_401_UNAUTHORIZED)


def forbidden(message: str = "Bạn không có quyền thực hiện thao tác này") -> AppException:
    return AppException("FORBIDDEN", message, status.HTTP_403_FORBIDDEN)


def not_found(message: str = "Không tìm thấy dữ liệu") -> AppException:
    return AppException("NOT_FOUND", message, status.HTTP_404_NOT_FOUND)


def validation_error(message: str, details: Optional[List[dict]] = None) -> AppException:
    return AppException(
        "VALIDATION_ERROR", message, status.HTTP_400_BAD_REQUEST, details
    )


def conflict(code: str, message: str) -> AppException:
    return AppException(code, message, status.HTTP_409_CONFLICT)


def unprocessable(code: str, message: str, details: Optional[List[dict]] = None) -> AppException:
    return AppException(code, message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "") or ""


def _error_body(
    code: str, message: str, correlation_id: str, details: Optional[List[Any]] = None
) -> dict:
    error: dict = {"code": code, "message": message, "correlationId": correlation_id}
    if details:
        error["details"] = details
    return {"success": False, "error": error}


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    cid = _correlation_id(request)
    if exc.http_status >= 500:
        logger.error(
            "AppException 5xx",
            extra={"correlationId": cid, "code": exc.code, "path": request.url.path},
        )
    return JSONResponse(
        status_code=exc.http_status,
        content=_error_body(exc.code, exc.message, cid, exc.details),
        headers={"X-Correlation-Id": cid},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    cid = _correlation_id(request)
    details = [
        {
            "field": ".".join(str(p) for p in err.get("loc", []) if p != "body"),
            "message": err.get("msg", "Giá trị không hợp lệ"),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=_error_body(
            "VALIDATION_ERROR", "Dữ liệu đầu vào không hợp lệ", cid, details
        ),
        headers={"X-Correlation-Id": cid},
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    cid = _correlation_id(request)
    code_map = {
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        429: "RATE_LIMIT_EXCEEDED",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(code, str(exc.detail), cid),
        headers={"X-Correlation-Id": cid},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    cid = _correlation_id(request)
    # Log đầy đủ (kèm stack) ở BE — KHÔNG trả ra client (rule logging.md)
    logger.error(
        "Unhandled exception",
        exc_info=exc,
        extra={
            "correlationId": cid,
            "path": request.url.path,
            "method": request.method,
        },
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body(
            "INTERNAL_ERROR", "Lỗi hệ thống, vui lòng thử lại sau", cid
        ),
        headers={"X-Correlation-Id": cid},
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
