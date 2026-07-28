"""Test hạn mức đồng thời (R1.2).

Kiểm 3 tính chất mà semaphore phải bảo đảm:
  1. Không bao giờ có quá N slot được giữ cùng lúc.
  2. Hết slot và quá timeout → AppException SERVER_BUSY 503, KHÔNG treo vô hạn.
  3. Slot luôn được trả lại kể cả khi thân `with` ném exception (nếu không, chỉ vài
     lỗi upload là khoá chết endpoint vĩnh viễn).
"""
import threading
import time

import pytest

from app.config import settings
from app.core import concurrency
from app.core.concurrency import export_slot, upload_slot
from app.core.exceptions import AppException


def _drain(sem: threading.BoundedSemaphore) -> int:
    """Chiếm hết slot còn trống, trả về số slot đã chiếm."""
    n = 0
    while sem.acquire(blocking=False):
        n += 1
    return n


def test_upload_slot_permits_fit_container_memory():
    """Số slot phải khớp phép tính RAM cho TOÀN CỤM, không phải một worker.

    Semaphore là per-process. Với UVICORN_WORKERS=4, trần RAM thực tế là
    4 × slot × max_upload_size. Con số cũ (6) cho 480MB chứ không phải 120MB như
    comment cũ ghi, cộng baseline ~750MB lúc tải cao là vượt mem_limit 1g.

    Khẳng định theo PHÉP TÍNH chứ không theo con số cứng, để lần sau đổi
    max_upload_size hay số worker thì test tự bắt.
    """
    taken = _drain(concurrency._upload_sem)
    try:
        workers = 4  # UVICORN_WORKERS mặc định trong Dockerfile
        total_mb = workers * taken * (settings.max_upload_size_bytes / 1024 / 1024)
        assert total_mb <= 300, (
            f"{workers} worker × {taken} slot × "
            f"{settings.max_upload_size_bytes // 1024 // 1024}MB = {total_mb:.0f}MB "
            "— vượt ngân sách RAM cho upload trong mem_limit 1g"
        )
        assert taken >= 2, "quá ít slot thì upload xếp hàng vô ích"
    finally:
        for _ in range(taken):
            concurrency._upload_sem.release()


def test_export_slot_has_two_permits():
    taken = _drain(concurrency._export_sem)
    try:
        assert taken == 2
    finally:
        for _ in range(taken):
            concurrency._export_sem.release()


def test_upload_slot_rejects_with_503_when_exhausted():
    """Hết slot → 503 SERVER_BUSY sau timeout, không treo."""
    taken = _drain(concurrency._upload_sem)
    try:
        t0 = time.monotonic()
        with pytest.raises(AppException) as exc:
            with upload_slot(timeout=0.2):
                pytest.fail("không được vào được khối khi đã hết slot")
        elapsed = time.monotonic() - t0

        assert exc.value.code == "SERVER_BUSY"
        assert exc.value.http_status == 503
        # Phải fail-fast quanh timeout, không chờ vô hạn
        assert 0.2 <= elapsed < 2.0
    finally:
        for _ in range(taken):
            concurrency._upload_sem.release()


def test_export_slot_rejects_with_503_when_exhausted():
    taken = _drain(concurrency._export_sem)
    try:
        with pytest.raises(AppException) as exc:
            with export_slot(timeout=0.2):
                pytest.fail("không được vào được khối khi đã hết slot")
        assert exc.value.code == "SERVER_BUSY"
        assert exc.value.http_status == 503
    finally:
        for _ in range(taken):
            concurrency._export_sem.release()


def test_slot_released_when_body_raises():
    """Rò rỉ slot là lỗi chí mạng: sau vài upload lỗi, endpoint sẽ khoá chết vĩnh viễn."""
    before = _drain(concurrency._upload_sem)
    for _ in range(before):
        concurrency._upload_sem.release()

    with pytest.raises(ValueError):
        with upload_slot(timeout=1.0):
            raise ValueError("lỗi giả lập trong lúc ghi MinIO")

    after = _drain(concurrency._upload_sem)
    for _ in range(after):
        concurrency._upload_sem.release()
    assert after == before, "slot bị rò rỉ sau khi thân with ném exception"


def test_never_exceeds_six_concurrent_uploads():
    """Chạy 20 thread tranh slot, theo dõi số slot bị giữ đồng thời — không được vượt 6."""
    peak = 0
    current = 0
    lock = threading.Lock()
    errors: list[Exception] = []

    def worker():
        nonlocal peak, current
        try:
            with upload_slot(timeout=10.0):
                with lock:
                    current += 1
                    peak = max(peak, current)
                time.sleep(0.05)  # giả lập ghi MinIO
                with lock:
                    current -= 1
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"có worker lỗi: {errors}"
    assert peak <= 6, f"đồng thời đạt {peak}, vượt hạn mức 6"
    assert peak > 1, "test không thực sự chạy song song"
