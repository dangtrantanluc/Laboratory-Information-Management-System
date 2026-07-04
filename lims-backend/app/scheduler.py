"""APScheduler wiring (M1) — CRON-1 due-soon (07:00) + CRON-2 overdue (00:30).

Background scheduler chạy trong process API. Mỗi job mở session riêng + dùng Redis lock
(idempotent) trong service. KHÔNG chặn startup nếu Redis/DB tạm lỗi (job sẽ tự retry kỳ sau).
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db.database import SessionLocal

logger = logging.getLogger("lims.scheduler")

_scheduler: BackgroundScheduler | None = None


def _job_due_soon() -> None:
    from app.services import sample_cron_service

    db = SessionLocal()
    try:
        sample_cron_service.run_due_soon(db)
    except Exception as exc:  # noqa: BLE001 — job không được làm sập scheduler
        logger.warning("CRON-1 due-soon failed: %s", exc)
    finally:
        db.close()


def _job_overdue() -> None:
    from app.services import sample_cron_service

    db = SessionLocal()
    try:
        sample_cron_service.run_overdue(db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("CRON-2 overdue failed: %s", exc)
    finally:
        db.close()


def _job_chem_expiry() -> None:
    from app.services import chemical_cron_service

    db = SessionLocal()
    try:
        chemical_cron_service.run_chem_expiry(db)
    except Exception as exc:  # noqa: BLE001 — job không được làm sập scheduler
        logger.warning("CRON-6 chem-expiry failed: %s", exc)
    finally:
        db.close()


def _job_salary_raise_due() -> None:
    from app.services import hr_cron_service

    db = SessionLocal()
    try:
        hr_cron_service.run_salary_raise_due(db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("CRON-3 salary-raise failed: %s", exc)
    finally:
        db.close()


def _job_contract_expiry() -> None:
    from app.services import hr_cron_service

    db = SessionLocal()
    try:
        hr_cron_service.run_contract_expiry(db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("CRON-4 contract-expiry failed: %s", exc)
    finally:
        db.close()


def _job_calibration_due() -> None:
    from app.services import equipment_cron_service

    db = SessionLocal()
    try:
        equipment_cron_service.run_calibration_due(db)
    except Exception as exc:  # noqa: BLE001
        logger.warning("CRON-5 calibration-due failed: %s", exc)
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    sched = BackgroundScheduler(timezone="UTC")
    # CRON-2: 00:30 đánh dấu overdue
    sched.add_job(
        _job_overdue,
        CronTrigger(hour=0, minute=30),
        id="sample-overdue",
        replace_existing=True,
    )
    # CRON-1: 07:00 nhắc sắp tới hạn
    sched.add_job(
        _job_due_soon,
        CronTrigger(hour=7, minute=0),
        id="sample-due-soon",
        replace_existing=True,
    )
    # CRON-6: 07:30 nhắc lô hóa chất sắp hết hạn / tới hạn kiểm tra lại (M2 FR-012)
    sched.add_job(
        _job_chem_expiry,
        CronTrigger(hour=7, minute=30),
        id="chem-expiry",
        replace_existing=True,
    )
    # CRON-3: 07:00 nhắc nâng lương (mốc 15/7/3 ngày) — M4 FR-HR-008
    sched.add_job(
        _job_salary_raise_due,
        CronTrigger(hour=7, minute=0),
        id="hr-salary-raise",
        replace_existing=True,
    )
    # CRON-4: 07:15 nhắc hết hạn HĐ (mốc 30/15/7 ngày) — M4 FR-HR-009
    sched.add_job(
        _job_contract_expiry,
        CronTrigger(hour=7, minute=15),
        id="hr-contract-expiry",
        replace_existing=True,
    )
    # CRON-5: 07:45 nhắc thiết bị sắp tới hạn hiệu chuẩn (mốc 30/15/7 ngày) — M5 FR-EQP-011
    sched.add_job(
        _job_calibration_due,
        CronTrigger(hour=7, minute=45),
        id="equipment-calibration-due",
        replace_existing=True,
    )
    sched.start()
    _scheduler = sched
    logger.info(
        "APScheduler started (M1 CRON-1/CRON-2 + M2 CRON-6 + M4 CRON-3/CRON-4 + M5 CRON-5)"
    )


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
