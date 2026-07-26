"""Tests cho scheduler run-history — job thành công/thất bại đều ghi last-run + status,
và _run_tracked KHÔNG bao giờ raise (job lỗi không làm sập scheduler)."""
from unittest.mock import MagicMock, patch

from app import scheduler


def test_run_tracked_records_ok_on_success():
    recorded = {}

    def fake_record(job_id, ok):
        recorded[job_id] = ok

    with patch.object(scheduler, "_record_run", side_effect=fake_record), \
         patch.object(scheduler, "SessionLocal", return_value=MagicMock()):
        scheduler._run_tracked("job-x", "CRON-X", lambda db: None)

    assert recorded == {"job-x": True}


def test_run_tracked_records_failed_and_does_not_raise():
    recorded = {}

    def fake_record(job_id, ok):
        recorded[job_id] = ok

    def boom(db):
        raise RuntimeError("service exploded")

    with patch.object(scheduler, "_record_run", side_effect=fake_record), \
         patch.object(scheduler, "SessionLocal", return_value=MagicMock()):
        # KHÔNG raise dù service ném lỗi
        scheduler._run_tracked("job-y", "CRON-Y", boom)

    assert recorded == {"job-y": False}


def test_run_tracked_closes_session():
    session = MagicMock()
    with patch.object(scheduler, "_record_run"), \
         patch.object(scheduler, "SessionLocal", return_value=session):
        scheduler._run_tracked("job-z", "CRON-Z", lambda db: None)
    session.close.assert_called_once()


def test_get_scheduler_status_merges_run_and_status():
    fake_redis = MagicMock()
    fake_redis.hgetall.side_effect = [
        {"job-a": "2026-01-01T00:00:00+00:00"},  # last_run
        {"job-a": "ok"},                          # last_status
    ]
    with patch("app.core.redis_client.get_redis", return_value=fake_redis):
        status = scheduler.get_scheduler_status()
    assert status == {"job-a": {"last_run": "2026-01-01T00:00:00+00:00", "status": "ok"}}


def test_get_scheduler_status_redis_down_returns_empty():
    with patch("app.core.redis_client.get_redis", side_effect=RuntimeError("down")):
        assert scheduler.get_scheduler_status() == {}


# ===================== Leader-lock / opt-out flag =====================

def test_scheduler_skips_when_disabled():
    scheduler._scheduler = None
    with patch.object(scheduler.settings, "scheduler_enabled", False), \
         patch.object(scheduler, "BackgroundScheduler") as mock_sched:
        scheduler.start_scheduler()
    mock_sched.assert_not_called()
    assert scheduler._scheduler is None


def test_scheduler_skips_when_leader_lock_not_acquired():
    scheduler._scheduler = None
    with patch.object(scheduler.settings, "scheduler_enabled", True), \
         patch.object(scheduler, "_acquire_leader_lock", return_value=False), \
         patch.object(scheduler, "BackgroundScheduler") as mock_sched:
        scheduler.start_scheduler()
    mock_sched.assert_not_called()
    assert scheduler._scheduler is None


def test_scheduler_starts_when_leader_lock_acquired():
    scheduler._scheduler = None
    fake_sched = MagicMock()
    with patch.object(scheduler.settings, "scheduler_enabled", True), \
         patch.object(scheduler, "_acquire_leader_lock", return_value=True), \
         patch.object(scheduler, "BackgroundScheduler", return_value=fake_sched):
        scheduler.start_scheduler()
    fake_sched.start.assert_called_once()
    # Số job cron (_JOBS) + 1 heartbeat leader-lock. Lấy từ scheduler._JOBS thay vì
    # hard-code: thêm cron mới không nên làm test này đỏ một cách vô nghĩa.
    assert fake_sched.add_job.call_count == len(scheduler._JOBS) + 1
    scheduler._scheduler = None  # dọn state cho test khác


def test_acquire_leader_lock_fail_open_when_redis_down():
    with patch("app.core.redis_client.get_redis", side_effect=RuntimeError("down")):
        assert scheduler._acquire_leader_lock() is True
