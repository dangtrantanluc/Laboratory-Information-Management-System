"""Context-local correlation ID — nguồn duy nhất để mọi log record tự gắn correlationId.

Trước đây correlationId chỉ nằm ở request.state và phải truyền tay qua `extra=` ở từng
call site (~5/hàng trăm nơi thực sự làm) → điều tra sự cố theo 1 correlationId bỏ sót gần
hết log của request đó (PRODUCTION_READINESS_REVIEW §Reliability: "Correlation ID is
manual/opt-in rather than auto-attached to every log record"). ContextVar này được
CorrelationIdMiddleware set đầu mỗi request; CorrelationIdLogFilter đọc nó và chèn vào
MỌI LogRecord tự động — không cần truyền `extra=` nữa.
"""
from contextvars import ContextVar
from typing import Optional

correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def set_correlation_id(cid: Optional[str]):
    return correlation_id_var.set(cid)


def get_correlation_id() -> Optional[str]:
    return correlation_id_var.get()


def reset_correlation_id(token) -> None:
    correlation_id_var.reset(token)
