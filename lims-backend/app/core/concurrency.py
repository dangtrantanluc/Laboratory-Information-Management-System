"""Hạn mức đồng thời cho tác vụ nặng RAM/CPU.

Sau khi upload chuyển sang threadpool (R1.1), 40 thread × 20MB = 800MB RAM. Semaphore
giới hạn số upload chạy cùng lúc, phần dư xếp hàng thay vì làm OOM cả container.
"""
import threading
from contextlib import contextmanager

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException

# 6 upload đồng thời × 20MB = 120MB — vừa với mem_limit 1g của lims-api
_upload_sem = threading.BoundedSemaphore(6)
# Xuất Excel/PDF là CPU-bound, giới hạn chặt hơn
_export_sem = threading.BoundedSemaphore(2)


@contextmanager
def upload_slot(timeout: float = 30.0):
    if not _upload_sem.acquire(timeout=timeout):
        raise AppException(
            ErrorCode.SERVER_BUSY, "Hệ thống đang xử lý nhiều tệp. Vui lòng thử lại sau ít phút.", 503
        )
    try:
        yield
    finally:
        _upload_sem.release()


@contextmanager
def export_slot(timeout: float = 60.0):
    if not _export_sem.acquire(timeout=timeout):
        raise AppException(
            ErrorCode.SERVER_BUSY, "Hệ thống đang xuất báo cáo khác. Vui lòng thử lại sau.", 503
        )
    try:
        yield
    finally:
        _export_sem.release()
