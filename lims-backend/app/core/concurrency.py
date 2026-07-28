"""Hạn mức đồng thời cho tác vụ nặng RAM/CPU.

Mỗi upload giữ nguyên nội dung file trong RAM (R1.1). Semaphore giới hạn số upload
chạy cùng lúc, phần dư xếp hàng thay vì làm OOM cả container.
"""
import threading
from contextlib import contextmanager

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException

# Semaphore là PER-PROCESS, không phải toàn cụm. Với UVICORN_WORKERS=4 thì trần
# thực tế là 4 × N, không phải N — con số cũ (6) cho 4×6×20MB = 480MB chứ không
# phải 120MB như comment cũ ghi, cộng baseline ~750MB đo được lúc tải cao là vượt
# mem_limit 1g.
#
#   4 worker × 3 × 20MB = 240MB  ←  còn chỗ cho baseline trong mem_limit 1g
_upload_sem = threading.BoundedSemaphore(3)
# Xuất Excel/PDF là CPU-bound. 4 × 2 = 8 tiến trình xuất đồng thời trên máy 4 nhân
# đã là quá tải, nên giữ 2 và không nới.
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
