"""Metrics Prometheus (/metrics) — quan sát định lượng request + scheduler (Phase D3).

Trước đây KHÔNG có metrics/tracing → sự cố chỉ chẩn đoán bằng grep log sau khi xảy ra
(PRODUCTION_READINESS_REVIEW §Observability). Module này cung cấp:
- http_requests_total{method,path,status} — đếm request theo route template (KHÔNG theo
  path thật để tránh cardinality bùng nổ với UUID).
- http_request_duration_seconds — histogram độ trễ.
- scheduler_job_last_run_timestamp{job} / scheduler_job_last_status{job} — đọc từ Redis
  run-history lúc scrape để phát hiện job cron bị bỏ lỡ.
Best-effort: lỗi thu thập KHÔNG ảnh hưởng request.
"""
import logging
import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("lims.metrics")

_REQUESTS = Counter(
    "http_requests_total", "Tổng số HTTP request", ["method", "path", "status"]
)
_LATENCY = Histogram(
    "http_request_duration_seconds", "Độ trễ HTTP request (giây)", ["method", "path"]
)
_SCHED_LAST_RUN = Gauge(
    "scheduler_job_last_run_timestamp", "Epoch lần chạy cron gần nhất", ["job"]
)
_SCHED_LAST_OK = Gauge(
    "scheduler_job_last_success", "1=lần chạy cron gần nhất thành công, 0=thất bại", ["job"]
)


def _route_template(request: Request) -> str:
    """Lấy path template ('/api/v1/samples/{sample_id}') thay vì path thật → tránh
    cardinality cao. Không match route → 'other'."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or "other"


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        try:
            path = _route_template(request)
            if path != "/metrics":
                elapsed = time.perf_counter() - start
                _REQUESTS.labels(request.method, path, str(response.status_code)).inc()
                _LATENCY.labels(request.method, path).observe(elapsed)
        except Exception:  # noqa: BLE001 — metrics KHÔNG được làm hỏng request
            pass
        return response


def _refresh_scheduler_gauges() -> None:
    """Đổ run-history scheduler từ Redis vào gauge (gọi lúc scrape /metrics)."""
    from datetime import datetime

    try:
        from app.scheduler import get_scheduler_status

        for job_id, info in (get_scheduler_status() or {}).items():
            last_run = info.get("last_run")
            if last_run:
                try:
                    ts = datetime.fromisoformat(last_run).timestamp()
                    _SCHED_LAST_RUN.labels(job_id).set(ts)
                except ValueError:
                    # last_run sai định dạng thì BỎ QUA metric của job này thay vì
                    # làm hỏng cả /metrics. Không log: hàm này chạy mỗi lần
                    # Prometheus scrape (15s), log ở đây sẽ ngập file log.
                    pass
            status = info.get("status")
            if status is not None:
                _SCHED_LAST_OK.labels(job_id).set(1.0 if status == "ok" else 0.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("scheduler gauge refresh skipped", extra={"error": str(exc)})


def metrics_response() -> Response:
    _refresh_scheduler_gauges()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
