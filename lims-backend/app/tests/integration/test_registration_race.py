"""Integration test (Postgres THẬT) cho M6 — khóa hàng chống double-decision.

Chứng minh FOR UPDATE trong decide_registration tuần tự hoá 2 request duyệt/từ chối
đồng thời: chỉ 1 request thắng, request kia thấy trạng thái đã đổi → 409
REGISTRATION_ALREADY_DECIDED. KHÔNG dùng fixture rollback (cần 2 connection độc lập,
commit thật) → tự seed + cleanup.
"""
import threading
import uuid

from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.hr import LabRegistration
from app.services import research_service

_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


def _admin() -> CurrentUser:
    return CurrentUser(
        id=_ADMIN_ID, email="admin@lims.local", full_name="Admin", role="admin",
        department_id=None, is_dept_lead=False, is_quality_manager=False,
        status="active", jti="jti", token_exp=9999999999,
    )


def test_concurrent_decide_only_one_wins(engine):
    reg_id = uuid.uuid4()
    # Seed (commit thật) 1 lượt đăng ký pending
    seed = Session(bind=engine)
    seed.add(LabRegistration(
        id=reg_id, student_name="SV Test", mentor_id=_ADMIN_ID, status="pending",
    ))
    seed.commit()
    seed.close()

    results: list = []
    barrier = threading.Barrier(2)

    def _decide(decision):
        s = Session(bind=engine)
        try:
            barrier.wait(timeout=5)  # đồng bộ 2 thread cùng lao vào
            research_service.decide_registration(
                s, user=_admin(), reg_id=reg_id, decision=decision, reason="r",
                correlation_id=None, ip=None,
            )
            results.append(("ok", decision))
        except AppException as e:
            results.append(("err", e.code))
        finally:
            s.close()

    t1 = threading.Thread(target=_decide, args=("approved",))
    t2 = threading.Thread(target=_decide, args=("rejected",))
    t1.start(); t2.start()
    t1.join(); t2.join()

    try:
        oks = [r for r in results if r[0] == "ok"]
        errs = [r for r in results if r[0] == "err"]
        # Đúng 1 thắng, 1 bị chặn bởi guard 409 (nhờ FOR UPDATE tuần tự hoá)
        assert len(oks) == 1, f"expected exactly 1 success, got {results}"
        assert len(errs) == 1 and errs[0][1] == "REGISTRATION_ALREADY_DECIDED", results
    finally:
        # cleanup bản ghi seed
        cleanup = Session(bind=engine)
        cleanup.query(LabRegistration).filter(LabRegistration.id == reg_id).delete()
        cleanup.commit()
        cleanup.close()
