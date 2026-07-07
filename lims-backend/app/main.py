"""FastAPI app — LIMS Backend M7 (Platform).

Wiring: logging, CORS, correlationId middleware, exception handlers, routers.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import setup_logging
from app.middleware.access_stat import AccessStatMiddleware
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.routers import (
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
    health,
    hr_catalogs,
    hr_crons,
    hr_profiles,
    improvements,
    nc_crons,
    nonconformities,
    notifications,
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

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# --- CORS (cho phép frontend) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,  # cookie refresh token
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-Id"],
)

# --- Correlation Id (sau CORS để mọi response có header) ---
app.add_middleware(CorrelationIdMiddleware)

# --- Access stats (M6.3): ghi page_view whitelist, best-effort, không chặn request ---
app.add_middleware(AccessStatMiddleware)

# --- Exception handlers (response format chuẩn) ---
register_exception_handlers(app)

# --- Routers ---
api = settings.api_prefix
app.include_router(health.router)  # /health (no prefix)
app.include_router(auth.router, prefix=api)
app.include_router(users.router, prefix=api)
app.include_router(departments.router, prefix=api)
app.include_router(rbac.router, prefix=api)
app.include_router(customers.router, prefix=api)
app.include_router(notifications.router, prefix=api)
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
# --- M6: Reporting & Analytics (module cuối, tầng tổng hợp chéo) ---
app.include_router(reporting.router, prefix=api)


@app.on_event("startup")
def on_startup() -> None:
    logger.info(
        "LIMS Backend starting",
        extra={"environment": settings.environment, "apiPrefix": api},
    )
    # Tạo bucket MinIO nếu chưa có (không chặn startup nếu MinIO chưa sẵn sàng)
    try:
        from app.services import storage_service

        storage_service.ensure_bucket()
    except Exception as exc:  # noqa: BLE001
        logger.warning("MinIO bucket init skipped", extra={"error": str(exc)})

    # M1 CRON-1/CRON-2 (APScheduler). Không chặn startup nếu lỗi.
    try:
        from app.scheduler import start_scheduler

        start_scheduler()
    except Exception as exc:  # noqa: BLE001
        logger.warning("APScheduler init skipped", extra={"error": str(exc)})


@app.on_event("shutdown")
def on_shutdown() -> None:
    try:
        from app.scheduler import shutdown_scheduler

        shutdown_scheduler()
    except Exception:  # noqa: BLE001
        pass
