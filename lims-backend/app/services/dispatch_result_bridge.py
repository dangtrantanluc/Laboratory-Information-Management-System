"""Cầu nối phiếu chuyển mẫu → cơ chế DUYỆT KẾT QUẢ bất biến của M1 (m40).

VÌ SAO KHÔNG XÂY LẠI CƠ CHẾ DUYỆT
`sample_results` của M1 đã làm đúng toàn bộ những gì luồng nhận mẫu đang thiếu:
phiên bản bất biến (`version` + `is_current`), bắt buộc lý do khi sửa bản đã duyệt
(`ck_res_revision_reason`), approved_by/approved_at đi cùng nhau (`ck_res_approval_pair`),
và chặn tự duyệt (`SELF_APPROVAL_FORBIDDEN` trong result_service). Viết lại lần thứ
hai là trả giá hai lần cho cùng một thứ, và bản thứ hai chắc chắn sẽ lệch dần.

BẢN ĐỒ THỰC THỂ

    sample_intakes    ─1:1─▶ test_requests        phiếu yêu cầu (1 phiếu nhận = 1 yêu cầu)
    (phiếu × phòng)   ─1:1─▶ samples              MẪU VẬT LÝ ở một phòng lab
    sample_dispatches ─1:1─▶ sample_assignments   PHẦN VIỆC = một chỉ tiêu
                                   └──▶ sample_results  kết quả có phiên bản + duyệt

Một `Sample` cho mỗi (phiếu × phòng lab), KHÔNG phải mỗi chỉ tiêu: năm chỉ tiêu của
cùng một phiếu gửi tới cùng một phòng là cùng MỘT mẫu vật lý. Đây đúng là ngữ nghĩa
M1 đã định nghĩa — `sample_assignments.part_name` sinh ra để chứa "phần việc".

TẠO LƯỜI
Bản ghi M1 chỉ sinh khi phòng lab lần đầu GỬI KẾT QUẢ ĐI DUYỆT. Phiếu mới nhận, đã
chuyển lab nhưng chưa ai làm thì không sinh gì — tránh đổ rác vào bảng `samples` và
làm sai KPI của module M1.

HẠN TRẢ — không bịa
`samples.deadline_at` là NOT NULL với CHECK `> received_at`. Lấy theo thứ tự:
  1. `sample_intakes.due_date_at`      — ngày quầy đã hẹn với khách (m39)
  2. `test_parameters.turnaround_days` — thời gian trả kết quả đã công bố trong bảng giá
Không có nguồn nào thì TỪ CHỐI và yêu cầu điền ngày hẹn trả. Một hạn bịa ra sẽ chảy
thẳng vào KPI "mẫu quá hạn" và làm số liệu điều hành sai — đúng loại lỗi mà cả đợt
sửa này sinh ra để loại bỏ.
"""
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException, not_found
from app.models.sample import Sample
from app.models.sample_assignment import SampleAssignment
from app.models.sample_flow import SampleDispatch, SampleIntake, TestParameter
from app.models.sample_result import SampleResult
from app.models.test_request import TestRequest
from app.services import audit_service, result_service, sample_common


def _resolve_deadline(db: Session, it: SampleIntake, d: SampleDispatch) -> datetime:
    """Hạn trả kết quả — chỉ từ số liệu nghiệp vụ có thật (xem docstring module)."""
    received = it.received_at or datetime.now(timezone.utc)

    if it.due_date_at is not None:
        # Cuối ngày hẹn, không phải 00:00 — hẹn "trả ngày 5/3" nghĩa là hết ngày 5/3.
        deadline = datetime.combine(it.due_date_at, time(23, 59, 59), tzinfo=timezone.utc)
        if deadline > received:
            return deadline

    if d.test_parameter_id is not None:
        tp = db.get(TestParameter, d.test_parameter_id)
        if tp is not None and tp.turnaround_days:
            return received + timedelta(days=int(tp.turnaround_days))

    raise AppException(
        ErrorCode.VALIDATION_ERROR,
        f"Phiếu {it.code} chưa có ngày hẹn trả kết quả, và chỉ tiêu "
        f"'{d.chi_tieu}' cũng không có thời gian trả trong bảng giá. "
        "Phòng nhận mẫu cần điền 'Ngày hẹn trả kết quả' trước khi gửi kết quả đi duyệt.",
        400,
    )


def _ensure_test_request(db: Session, *, user: CurrentUser, it: SampleIntake) -> TestRequest:
    if it.test_request_id is not None:
        req = db.get(TestRequest, it.test_request_id)
        if req is not None:
            return req
    req = TestRequest(
        request_code=sample_common.next_request_code(db),
        customer_id=it.customer_id,
        sender_name=it.contact_person,
        # Phiếu nhận mẫu có thể chưa gắn phòng (khách vãng lai) — dùng phòng của quầy
        # đã nhận, đó là nơi chịu trách nhiệm hồ sơ.
        department_id=it.department_id,
        received_by=it.received_by,
        received_at=it.received_at,
        note=f"Sinh từ phiếu nhận mẫu {it.code}",
        created_by=user.id,
    )
    db.add(req)
    db.flush()
    it.test_request_id = req.id
    return req


def _ensure_sample(
    db: Session, *, user: CurrentUser, it: SampleIntake, d: SampleDispatch, req: TestRequest
) -> Sample:
    """Một mẫu cho mỗi (phiếu × phòng lab) — tìm lại qua các lượt chuyển cùng phòng."""
    sibling = db.execute(
        select(SampleDispatch).where(
            SampleDispatch.intake_id == it.id,
            SampleDispatch.target_department_id == d.target_department_id,
            SampleDispatch.assignment_id.isnot(None),
        ).limit(1)
    ).scalars().first()
    if sibling is not None:
        asg = db.get(SampleAssignment, sibling.assignment_id)
        if asg is not None:
            existing = db.get(Sample, asg.sample_id)
            if existing is not None:
                return existing

    sample = Sample(
        sample_code=sample_common.next_sample_code(db),
        request_id=req.id,
        department_id=d.target_department_id,
        received_by=it.received_by,
        # Mẫu đang ở phòng lab thực hiện — người giữ mẫu là người đang làm.
        current_custodian_id=user.id,
        description=it.description,
        received_at=it.received_at,
        deadline_at=_resolve_deadline(db, it, d),
        status="received",
        created_by=user.id,
    )
    db.add(sample)
    db.flush()
    return sample


def ensure_assignment(
    db: Session, *, user: CurrentUser, d: SampleDispatch
) -> SampleAssignment:
    """Dựng (hoặc lấy lại) phần việc M1 cho một lượt chuyển. CHƯA commit."""
    if d.assignment_id is not None:
        asg = db.get(SampleAssignment, d.assignment_id)
        if asg is not None:
            return asg

    it = db.get(SampleIntake, d.intake_id)
    if it is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")

    req = _ensure_test_request(db, user=user, it=it)
    sample = _ensure_sample(db, user=user, it=it, d=d, req=req)

    asg = SampleAssignment(
        sample_id=sample.id,
        # Người GỬI kết quả là người thực hiện phần việc — đây là mấu chốt để
        # result_service chặn tự duyệt về sau (approved_by phải khác entered_by).
        assigned_to=user.id,
        assigned_by=user.id,
        part_name=d.chi_tieu[:255],
        status="assigned",
        created_by=user.id,
    )
    db.add(asg)
    db.flush()
    d.assignment_id = asg.id

    if sample.status == "received":
        sample_common.change_status(
            db, sample, "assigned", trigger="dispatch_result_submit",
            user_id=user.id, correlation_id=None, ip=None,
        )
    return asg


def current_result(db: Session, assignment_id: Optional[uuid.UUID]) -> Optional[SampleResult]:
    if assignment_id is None:
        return None
    return db.execute(
        select(SampleResult).where(
            SampleResult.assignment_id == assignment_id,
            SampleResult.is_current.is_(True),
        )
    ).scalar_one_or_none()


def is_approved(db: Session, d: SampleDispatch) -> bool:
    r = current_result(db, d.assignment_id)
    return r is not None and r.approved_by is not None


def approval_state(db: Session, d: SampleDispatch) -> dict:
    """Trạng thái duyệt của kết quả, suy TỪ sample_results — không nhân bản dữ liệu.

    Cố ý không lưu cờ "đã duyệt" trên sample_dispatches: hai nguồn cho cùng một sự
    thật là cách chắc chắn nhất để chúng lệch nhau.
    """
    r = current_result(db, d.assignment_id)
    if r is None:
        return {
            "result_id": None, "result_version": None,
            "result_approval_status": "draft",
            "result_approved_by_name": None, "result_approved_at": None,
        }
    return {
        "result_id": r.id,
        "result_version": r.version,
        "result_approval_status": "approved" if r.approved_by else "pending",
        "result_approved_by_name": sample_common.user_name(db, r.approved_by),
        "result_approved_at": r.approved_at,
    }


def submit_from_dispatch(
    db: Session, *, user: CurrentUser, dispatch_id: uuid.UUID, note: Optional[str],
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Điểm vào của router: tra lượt chuyển, kiểm phạm vi phòng, rồi gửi duyệt.

    Phạm vi trùng khớp update_dispatch_result: chỉ người của PHÒNG NHẬN lượt chuyển
    (hoặc admin) mới gửi được — người gửi duyệt cũng là người sẽ đứng tên thực hiện.
    """
    d = db.get(SampleDispatch, dispatch_id)
    if d is None:
        raise not_found("Không tìm thấy phiếu chuyển mẫu")
    if user.role != "admin" and user.department_id != d.target_department_id:
        raise AppException(
            ErrorCode.FORBIDDEN,
            "Bạn chỉ được gửi duyệt kết quả của phiếu chuyển tới phòng của mình",
            403,
        )
    return submit_for_approval(
        db, user=user, d=d, note=note, correlation_id=correlation_id, ip=ip
    )


def submit_for_approval(
    db: Session, *, user: CurrentUser, d: SampleDispatch, note: Optional[str],
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Phòng lab gửi kết quả đi duyệt — từ đây kết quả đi theo luật của M1.

    Nội dung lấy từ chính các cột BM 7.1/02 mà lab vừa điền, nên người dùng không
    phải gõ lại: màn hình vẫn là phiếu chuyển mẫu, chỉ có cơ chế phía sau đổi.
    """
    if not (d.ket_qua and d.ket_qua.strip()):
        raise AppException(
            ErrorCode.VALIDATION_ERROR, "Chưa có kết quả để gửi duyệt", 400
        )
    asg = ensure_assignment(db, user=user, d=d)

    data = result_service.enter_result(
        db, user=user, assignment_id=asg.id,
        result_data={
            "chi_tieu": d.chi_tieu,
            "ket_qua": d.ket_qua,
            "don_vi": d.don_vi,
            "phuong_phap": d.phuong_phap,
            "dispatch_id": str(d.id),
        },
        note=note, correlation_id=correlation_id, ip=ip,
    )
    audit_service.log_action(
        db, action="DISPATCH_RESULT_SUBMIT", resource="sample_dispatch", user_id=user.id,
        resource_id=d.id, correlation_id=correlation_id, ip=ip,
        detail={"assignment_id": str(asg.id), "result_id": str(data["id"])},
    )
    db.commit()
    return data
