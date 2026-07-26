"""APScheduler wiring (M1/M2/M4/M5/M8/M10) — 8 cron nhắc hạn.

Background scheduler chạy trong process API. Mỗi job mở session riêng + dùng Redis lock
(idempotent) trong service. KHÔNG chặn startup nếu Redis/DB tạm lỗi (job sẽ tự retry kỳ sau).

Giám sát run-history (PRODUCTION_READINESS_REVIEW §Reliability: "Scheduler jobs have no
misfire/catch-up handling and no run-history monitoring"): mỗi lần chạy ghi
last-run-timestamp + trạng thái (ok/failed) vào Redis; endpoint /health/ready đọc lại để
on-call phát hiện job bị bỏ lỡ (vd deploy đúng cửa sổ 07:00–08:15 làm skip 1 ngày nhắc
hạn ISO17025). Trigger thêm misfire_grace_time + coalesce để bù 1 lần chạy trễ sau khi
container up lại thay vì mất hẳn.
"""
import logging
import uuid
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.db.database import SessionLocal

logger = logging.getLogger("lims.scheduler")

_scheduler: BackgroundScheduler | None = None

# Token định danh RIÊNG process này — dùng làm "chủ sở hữu" leader-lock để heartbeat chỉ
# gia hạn lock CỦA MÌNH, không đè lock của replica khác (PRODUCTION_READINESS_REVIEW M5).
_INSTANCE_TOKEN = uuid.uuid4().hex

# Cho phép bù tối đa 1 giờ nếu job lỡ giờ trigger (container down đúng lúc); coalesce=True
# gộp nhiều lần lỡ thành 1 lần chạy.
_MISFIRE_GRACE_SECONDS = 3600

# Redis key cho run-history (đọc bởi health.py).
_LASTRUN_KEY = "scheduler:lastrun"
_LASTSTATUS_KEY = "scheduler:laststatus"

# Leader-lock: chỉ 1 replica giữ lock này mới đăng ký cron. Giá trị lock = _INSTANCE_TOKEN
# (chủ sở hữu). TTL dài hơn chu kỳ heartbeat để leader tự gia hạn; nếu leader chết, lock
# hết hạn và replica khác giành ở lần thử sau.
_LEADER_LOCK_KEY = "scheduler:leader"
_LEADER_LOCK_TTL_SECONDS = 90
_LEADER_HEARTBEAT_SECONDS = 30

# Chỉ gia hạn (PEXPIRE) nếu lock VẪN thuộc về mình — compare-and-extend nguyên tử (Lua),
# tránh heartbeat của replica này đè/kéo dài lock của replica khác.
_REFRESH_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('pexpire', KEYS[1], ARGV[2]) else return 0 end"
)


def _acquire_leader_lock() -> bool:
    """Thử giành leader-lock (SET NX EX với giá trị = token của process này). Redis lỗi →
    KHÔNG fail-open nữa: để tránh nhiều replica cùng chạy cron khi Redis chập chờn, chỉ
    replica được cấu hình SCHEDULER_ENABLED mới nên bật (per-job lock vẫn chống chạy trùng).
    """
    try:
        from app.core.redis_client import get_redis

        return bool(
            get_redis().set(_LEADER_LOCK_KEY, _INSTANCE_TOKEN, nx=True, ex=_LEADER_LOCK_TTL_SECONDS)
        )
    except Exception as exc:  # noqa: BLE001
        # Redis không tới được: single-replica dev vẫn cần chạy cron. Rủi ro chạy trùng khi
        # multi-replica + Redis down được chặn ở lớp cuối bởi per-job Redis lock trong service.
        logger.warning(
            "scheduler leader-lock unavailable — starting on this replica (per-job locks guard duplicates)",
            extra={"error": str(exc)},
        )
        return True


def _refresh_leader_lock() -> None:
    """Heartbeat: CHỈ gia hạn lock nếu vẫn thuộc về process này (compare-and-extend)."""
    try:
        from app.core.redis_client import get_redis

        get_redis().eval(
            _REFRESH_LUA, 1, _LEADER_LOCK_KEY, _INSTANCE_TOKEN, _LEADER_LOCK_TTL_SECONDS * 1000
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("scheduler leader-lock refresh skipped", extra={"error": str(exc)})


def _record_run(job_id: str, ok: bool) -> None:
    """Ghi last-run-timestamp + trạng thái vào Redis (best-effort)."""
    try:
        from app.core.redis_client import get_redis

        r = get_redis()
        r.hset(_LASTRUN_KEY, job_id, datetime.now(timezone.utc).isoformat())
        r.hset(_LASTSTATUS_KEY, job_id, "ok" if ok else "failed")
    except Exception as exc:  # noqa: BLE001 — giám sát KHÔNG được làm sập job
        logger.warning("scheduler run-history write skipped", extra={"jobId": job_id, "error": str(exc)})


def _run_tracked(job_id: str, label: str, service_call) -> None:
    """Chạy 1 job cron: mở session riêng, gọi service, ghi run-history. Không raise
    (job lỗi KHÔNG được làm sập scheduler)."""
    db = SessionLocal()
    ok = False
    try:
        service_call(db)
        ok = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s failed: %s", label, exc)
    finally:
        db.close()
        _record_run(job_id, ok)


def get_scheduler_status() -> dict:
    """Trả run-history mọi job (cho /health/ready). {job_id: {last_run, status}}."""
    try:
        from app.core.redis_client import get_redis

        r = get_redis()
        last_run = r.hgetall(_LASTRUN_KEY) or {}
        last_status = r.hgetall(_LASTSTATUS_KEY) or {}
    except Exception:  # noqa: BLE001
        return {}
    return {
        job_id: {"last_run": last_run.get(job_id), "status": last_status.get(job_id)}
        for job_id in set(last_run) | set(last_status)
    }


# (job_id, label, cron kwargs, tên module service, tên hàm service) — import lazy trong
# closure để tránh vòng import lúc load module + giữ nguyên hành vi cũ.
_JOBS = [
    ("sample-overdue", "CRON-2 overdue", {"hour": 0, "minute": 30}, "sample_cron_service", "run_overdue"),
    ("sample-due-soon", "CRON-1 due-soon", {"hour": 7, "minute": 0}, "sample_cron_service", "run_due_soon"),
    ("chem-expiry", "CRON-6 chem-expiry", {"hour": 7, "minute": 30}, "chemical_cron_service", "run_chem_expiry"),
    ("hr-salary-raise", "CRON-3 salary-raise", {"hour": 7, "minute": 0}, "hr_cron_service", "run_salary_raise_due"),
    ("hr-contract-expiry", "CRON-4 contract-expiry", {"hour": 7, "minute": 15}, "hr_cron_service", "run_contract_expiry"),
    ("equipment-calibration-due", "CRON-5 calibration-due", {"hour": 7, "minute": 45}, "equipment_cron_service", "run_calibration_due"),
    ("capa-due", "CRON-7 capa-due", {"hour": 8, "minute": 0}, "nc_cron_service", "run_capa_due"),
    ("risk-review-due", "CRON-8 risk-review-due", {"hour": 8, "minute": 15}, "risk_cron_service", "run_risk_review_due"),
]


def _make_job(job_id: str, label: str, module_name: str, fn_name: str):
    def _job() -> None:
        import importlib

        module = importlib.import_module(f"app.services.{module_name}")
        service_fn = getattr(module, fn_name)
        _run_tracked(job_id, label, service_fn)

    return _job


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return

    # 1) Opt-out tường minh: replica được cấu hình KHÔNG chạy cron thì bỏ qua hẳn.
    if not settings.scheduler_enabled:
        logger.info("APScheduler disabled on this replica (SCHEDULER_ENABLED=false)")
        return

    # 2) Leader-lock: khi lỡ bật nhiều replica, chỉ replica giành được lock mới đăng ký
    #    cron (per-job lock trong service vẫn là lớp bảo vệ cuối chống chạy trùng).
    if not _acquire_leader_lock():
        logger.info("APScheduler not started — another replica holds the scheduler leader lock")
        return

    sched = BackgroundScheduler(timezone="UTC")
    for job_id, label, cron_kwargs, module_name, fn_name in _JOBS:
        sched.add_job(
            _make_job(job_id, label, module_name, fn_name),
            CronTrigger(**cron_kwargs),
            id=job_id,
            replace_existing=True,
            misfire_grace_time=_MISFIRE_GRACE_SECONDS,
            coalesce=True,
        )
    # Heartbeat gia hạn leader-lock để replica này giữ quyền leader.
    sched.add_job(
        _refresh_leader_lock,
        IntervalTrigger(seconds=_LEADER_HEARTBEAT_SECONDS),
        id="scheduler-leader-heartbeat",
        replace_existing=True,
    )
    sched.start()
    _scheduler = sched
    logger.info(
        "APScheduler started (CRON-1..8: M1/M2/M4/M5 + M8 CRON-7 + M10 CRON-8)"
    )


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
