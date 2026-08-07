"""Hợp đồng giữa scheduler và 9 cron service.

Sự cố thật (phát hiện 2026-08-07, đọc từ /health/ready trên production):

    failed  2026-08-02T06:15  capa-due          ← ISO 17025 §8.7
    failed  2026-08-02T06:30  risk-review-due   ← §8.5
    failed  2026-08-06T03:00  data-cleanup

Ba lỗi, hai nguyên nhân, không cái nào bị test hiện có bắt được:

1. `cleanup_cron_service.run_cleanup()` khai 0 tham số trong khi
   `scheduler._run_tracked` gọi `service_call(db)` cho mọi job → TypeError mỗi lần
   chạy. CRON-9 chưa từng chạy được kể từ khi thêm vào.

2. `audit_service._sanitize()` gọi `key.lower()` nên nổ với khoá SỐ, mà 3 cron truyền
   `by_milestone = {7: 0, 3: 0, ...}`. CRON-7/CRON-8 hỏng hẳn (mất luôn notification
   của lô đó vì db.commit() không tới); CRON-5 thì "ok" nhưng dòng audit im lặng biến
   mất — production có 0 dòng CRON_CALIBRATION_REMINDER.

Điểm chung: cả hai chỉ lộ ra khi THỰC SỰ GỌI hàm đúng cách scheduler gọi. Bộ test cũ
kiểm từng service bằng lời gọi viết tay với đối số đúng, nên không bao giờ chạm tới.
"""
import inspect

import pytest

from app.scheduler import _JOBS
from app.services import audit_service
from app.tests.conftest import requires_db


def _service_fn(module_name: str, fn_name: str):
    import importlib

    return getattr(importlib.import_module(f"app.services.{module_name}"), fn_name)


JOB_IDS = [j[0] for j in _JOBS]


# ═══════════════ 1. Chữ ký — chạy được không cần DB ═══════════════


@pytest.mark.parametrize("job", _JOBS, ids=JOB_IDS)
def test_nhan_duoc_db_lam_tham_so_dau(job):
    """`_run_tracked` gọi `service_call(db)`. Mọi cron phải nhận đúng kiểu gọi đó."""
    _job_id, _label, _cron, module_name, fn_name = job
    fn = _service_fn(module_name, fn_name)
    params = list(inspect.signature(fn).parameters.values())

    assert params, f"{module_name}.{fn_name}() không nhận tham số nào — scheduler truyền db"
    assert params[0].kind in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ), f"{module_name}.{fn_name}: tham số đầu phải nhận được theo vị trí"


@pytest.mark.parametrize("job", _JOBS, ids=JOB_IDS)
def test_moi_tham_so_con_lai_deu_co_mac_dinh(job):
    """Scheduler chỉ truyền `db`. Tham số bắt buộc thứ hai = TypeError lúc chạy."""
    _job_id, _label, _cron, module_name, fn_name = job
    fn = _service_fn(module_name, fn_name)
    thieu_mac_dinh = [
        p.name
        for p in list(inspect.signature(fn).parameters.values())[1:]
        if p.default is inspect.Parameter.empty
        and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    ]
    assert not thieu_mac_dinh, (
        f"{module_name}.{fn_name}: tham số {thieu_mac_dinh} không có giá trị mặc định"
    )


# ═══════════════ 2. _sanitize phải chịu được mọi dict caller đưa vào ═══════════════


class TestSanitizeChiuDuocKhoaKhongPhaiChuoi:
    """Ghi nhật ký là mối quan tâm CẮT NGANG — nó không được làm đổ vỡ nghiệp vụ."""

    def test_khoa_so_o_cap_long_nhau(self):
        """Đúng hình dạng đã làm hỏng CRON-7/8: dict lồng có khoá số."""
        out = audit_service._sanitize(
            {"scanned": 3, "by_milestone": {7: 1, 3: 0, 0: 2}}
        )
        assert out == {"scanned": 3, "by_milestone": {"7": 1, "3": 0, "0": 2}}

    def test_khoa_so_o_cap_ngoai(self):
        assert audit_service._sanitize({1: "a"}) == {"1": "a"}

    def test_van_che_field_nhay_cam(self):
        """Bản vá không được làm mất tác dụng lọc secret."""
        out = audit_service._sanitize({"password": "abc", "nested": {"token": "xyz"}})
        assert out == {"password": "***", "nested": {"token": "***"}}


# ═══════════════ 3. Chạy thật cả 9 cron trên DB thật ═══════════════


@requires_db
@pytest.mark.parametrize("job", _JOBS, ids=JOB_IDS)
def test_chay_that_khong_nem_ngoai_le(job, db):
    """Gọi ĐÚNG cách `_run_tracked` gọi. Đây là bài kiểm duy nhất bắt được cả hai lỗi.

    DB rỗng nên không job nào có việc để làm — nhưng chính đường "không có gì để làm"
    mới là đường đã hỏng trên production: lỗi nằm ở bước ghi audit tổng kết cuối hàm,
    chạy bất kể quét được bao nhiêu dòng.
    """
    _job_id, _label, _cron, module_name, fn_name = job
    fn = _service_fn(module_name, fn_name)

    fn(db)  # không assert gì thêm: ném exception là fail
