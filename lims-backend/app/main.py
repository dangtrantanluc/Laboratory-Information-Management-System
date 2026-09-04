"""FastAPI app — LIMS Backend M7 (Platform).

Wiring: logging, CORS, correlationId middleware, exception handlers, routers.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import setup_logging
from app.core.metrics import MetricsMiddleware, metrics_response
from app.middleware.access_stat import AccessStatMiddleware
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.middleware.idempotency import IdempotencyMiddleware
from app.middleware.request_limits import RequestLimitsMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import (
    activities,
    activity_reports,
    assignments,
    attachments,
    audit_logs,
    auth,
    calibrations,
    chemical_crons,
    chemical_lots,
    chemicals,
    customers,
    departments,
    documents,
    equipment_crons,
    equipments,
    forms,
    health,
    sample_flow,
    hr_catalogs,
    hr_crons,
    hr_profiles,
    improvements,
    lab_access,
    nc_crons,
    nonconformities,
    notifications,
    push,
    quotations,
    rbac,
    reporting,
    research,
    results,
    risk_crons,
    risks,
    sample_crons,
    sample_reports,
    samples,
    test_requests,
    users,
)

setup_logging()
logger = logging.getLogger("lims.main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Vòng đời app (thay @app.on_event đã deprecated) — startup rồi shutdown.

    Startup: init bucket MinIO + APScheduler (không chặn nếu lỗi).
    Shutdown: dừng scheduler, drain push executor + page_view-write nền (M9/L1).
    """
    logger.info(
        "LIMS Backend starting",
        extra={"environment": settings.environment, "apiPrefix": settings.api_prefix},
    )

    # Threadpool AnyIO mặc định 40 thread, nhưng pool DB chỉ có pool_size+max_overflow
    # connection. 40 thread tranh 20 connection ⇒ 20 thread chờ tới khi pool_timeout
    # rồi ném lỗi. Đặt bằng nhau để hàng đợi nằm ở tầng HTTP (có timeout rõ ràng)
    # thay vì tầng DB (ARCHITECTURE_AUDIT.md F-03).
    try:
        import anyio.to_thread

        limit = settings.db_pool_size + settings.db_max_overflow
        anyio.to_thread.current_default_thread_limiter().total_tokens = limit
        logger.info("Threadpool limiter aligned with DB pool", extra={"threads": limit})
    except Exception as exc:  # noqa: BLE001 — không được chặn khởi động vì việc chỉnh tuning
        logger.warning("Cannot set threadpool limiter", extra={"error": str(exc)})

    # Ma trận quyền được cache Redis TTL 300s. Migration đổi quyền (m36, m37) chạy
    # ngay trước khi app khởi động, nên cache của tiến trình cũ vẫn giữ ma trận CŨ
    # thêm tới 5 phút sau deploy — vừa chưa cấp quyền mới, vừa còn cấp quyền vừa bị
    # thu hồi. `invalidate_role_cache()` đã tồn tại từ đầu nhưng KHÔNG được gọi ở
    # bất kỳ đâu; gọi ở đây khiến mọi lần deploy tự đóng cửa sổ đó.
    try:
        from app.core.rbac import invalidate_role_cache

        invalidate_role_cache()
        logger.info("RBAC cache invalidated on startup")
    except Exception as exc:  # noqa: BLE001 — cache lỗi không được chặn khởi động
        logger.warning("RBAC cache invalidate skipped", extra={"error": str(exc)})

    try:
        from app.services import storage_service

        storage_service.ensure_bucket()
    except Exception as exc:  # noqa: BLE001
        logger.warning("MinIO bucket init skipped", extra={"error": str(exc)})
    try:
        from app.scheduler import start_scheduler

        start_scheduler()
    except Exception as exc:  # noqa: BLE001
        logger.warning("APScheduler init skipped", extra={"error": str(exc)})

    yield

    try:
        from app.scheduler import shutdown_scheduler

        shutdown_scheduler()
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.services import push_service

        push_service.shutdown_executor()  # drain push đang chờ (M9)
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.middleware.access_stat import drain_background_tasks

        await drain_background_tasks()  # chờ page_view-write nền (L1)
    except Exception:  # noqa: BLE001
        pass


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# LƯU Ý thứ tự: Starlette coi add_middleware GỌI SAU CÙNG là lớp NGOÀI CÙNG. Thứ tự
# thực thi (ngoài → trong): CORS → SecurityHeaders → Idempotency → AccessStat →
# CorrelationId → route. CORS đặt ngoài cùng để MỌI response — kể cả 409/replay do
# IdempotencyMiddleware sinh ra và response lỗi — đều có header CORS (M4), đồng thời
# preflight OPTIONS được xử lý sớm nhất.

# --- Request limits (chặn sớm upload quá cỡ theo Content-Length) ---
app.add_middleware(RequestLimitsMiddleware)

# --- Metrics (đếm request + độ trễ theo route template) ---
app.add_middleware(MetricsMiddleware)

# --- Correlation Id ---
app.add_middleware(CorrelationIdMiddleware)

# --- Access stats (M6.3): ghi page_view whitelist, best-effort, không chặn request ---
app.add_middleware(AccessStatMiddleware)

# --- Idempotency (opt-in header Idempotency-Key trên POST — chống tạo trùng khi retry) ---
app.add_middleware(IdempotencyMiddleware)

# --- Security headers (áp cho MỌI response app kể cả replay) ---
app.add_middleware(SecurityHeadersMiddleware)

# --- CORS (thêm sau cùng → lớp NGOÀI CÙNG) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,  # cookie refresh token
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-Id"],
)

# --- Exception handlers (response format chuẩn) ---
register_exception_handlers(app)

# --- Metrics endpoint (Prometheus scrape — no prefix, no auth: chỉ expose nội bộ) ---
@app.get("/metrics", include_in_schema=False)
def metrics():
    return metrics_response()


# --- Routers ---
api = settings.api_prefix
app.include_router(health.router)  # /health (no prefix)
app.include_router(auth.router, prefix=api)
app.include_router(users.router, prefix=api)
app.include_router(departments.router, prefix=api)
app.include_router(rbac.router, prefix=api)
app.include_router(customers.router, prefix=api)
app.include_router(notifications.router, prefix=api)
app.include_router(push.router, prefix=api)
app.include_router(audit_logs.router, prefix=api)
app.include_router(attachments.router, prefix=api)
# --- M1: Sample Lifecycle ---
app.include_router(test_requests.router, prefix=api)
app.include_router(samples.router, prefix=api)
app.include_router(assignments.router, prefix=api)
app.include_router(results.router, prefix=api)
app.include_router(sample_reports.router, prefix=api)
app.include_router(sample_crons.router, prefix=api)
# --- M2: Chemical Inventory ---
app.include_router(chemicals.router, prefix=api)
app.include_router(chemical_lots.router, prefix=api)
app.include_router(chemical_crons.router, prefix=api)
# --- M3: Document Control ---
app.include_router(documents.lookup_router, prefix=api)
app.include_router(documents.router, prefix=api)
# --- M4: HR & Research Achievement ---
app.include_router(hr_profiles.router, prefix=api)
app.include_router(research.router, prefix=api)
app.include_router(activities.router, prefix=api)  # m23: hợp đồng/công tác khác/chứng nhận
app.include_router(activity_reports.router, prefix=api)  # m25: báo cáo hoạt động tháng
app.include_router(hr_catalogs.router, prefix=api)
app.include_router(hr_crons.router, prefix=api)
# --- M5: Equipment & Calibration ---
app.include_router(equipments.router, prefix=api)
app.include_router(calibrations.router, prefix=api)
app.include_router(equipment_crons.router, prefix=api)
# --- M8: Nonconformity & CAPA (EPIC-QMS §7.10/§8.7) ---
app.include_router(nonconformities.router, prefix=api)
app.include_router(nc_crons.router, prefix=api)
# --- M10: Risk & Improvement (EPIC-QMS §8.5/§8.6) ---
app.include_router(risks.router, prefix=api)
app.include_router(improvements.router, prefix=api)
app.include_router(risk_crons.router, prefix=api)
# --- M11/GĐ3: Kho biểu mẫu VILAS (QLCL) ---
app.include_router(forms.router, prefix=api)
# --- GĐ2b: Nhận & Chuyển mẫu (reception → lab) ---
app.include_router(sample_flow.router, prefix=api)
# --- m29: Báo giá (quotation) — Phòng nhận mẫu lập, xuất Excel theo mẫu Viện ---
app.include_router(quotations.router, prefix=api)
# --- M19: Thẻ vào PTN (sinh viên, Văn phòng quản lý) ---
app.include_router(lab_access.router, prefix=api)
# --- M6: Reporting & Analytics (module cuối, tầng tổng hợp chéo) ---
app.include_router(reporting.router, prefix=api)
