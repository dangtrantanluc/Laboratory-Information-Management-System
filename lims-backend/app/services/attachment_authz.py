"""Uỷ quyền cấp đối tượng cho bảng `attachments` (dùng chung 20 owner_type).

VÌ SAO CẦN FILE NÀY
-------------------
`attachment_service` từng chỉ có MỘT luật cho mọi loại tệp:

    if owner_type in {"test_request", "sample", "sample_result"} and user.role == "office":
        raise FORBIDDEN_OFFICE

Nghĩa là ngoài việc cấm Văn phòng đọc 3 loại của M1, `GET /attachments/{id}` cấp
presigned URL cho BẤT KỲ hàng nào trong bảng, và `POST /attachments` cho gắn tệp vào
BẤT KỲ owner_id nào. Trong khi đó mỗi module đã tự xây luật riêng và đường generic bỏ
qua tất cả:

  - tài liệu mức `restricted` chỉ phòng sở hữu được xem (document_common.can_view_restricted)
  - bản draft/review chỉ người soạn + trưởng nhóm (can_view_unpublished_version)
  - minh chứng VILAS ràng buộc phòng ban + khoá sau khi duyệt (form_file_service)
  - raw data kết quả chưa duyệt chỉ nhóm liên quan (result_service._can_view_pending)
  - hồ sơ năng lực: staff chỉ xem của mình, office bị cấm (hr_service)

`form_file_service` đã ghi nhận nguy cơ này ("bất kỳ ai biết id biểu mẫu cũng ghi đè
được kho VILAS") và ĐI VÒNG bằng endpoint riêng, nhưng đường generic vẫn mở.

NGUYÊN TẮC
----------
1. **DENY BY DEFAULT.** owner_type không khai trong bảng dưới đây thì KHÔNG ai đọc/ghi
   được. Module mới buộc phải khai quyền, thay vì thừa hưởng lỗ hổng — đây là lý do
   chính file này tồn tại, quan trọng hơn bản thân từng luật.
2. **KHÔNG viết lại luật.** Mỗi guard gọi đúng hàm mà module sở hữu đang dùng, để sửa
   một chỗ là cả hai đường (riêng + generic) cùng đổi. Trùng lặp luật uỷ quyền là cách
   chắc chắn nhất để hai đường lệch nhau sau vài tháng.
3. **Import cục bộ trong guard.** attachment_service ← authz → các service domain, mà
   nhiều service domain lại gọi attachment_service.create_attachment. Import ở thân hàm
   là cách cắt vòng đang được dùng nhất quán trong codebase.
"""
import uuid
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException, not_found

Guard = Callable[[Session, CurrentUser, uuid.UUID], None]


def _deny(owner_type: str) -> None:
    """owner_type chưa khai luật → từ chối, KHÔNG cho qua.

    Thông điệp cố ý nêu rõ nguyên nhân là thiếu khai báo (không phải "bạn thiếu quyền"),
    để lập trình viên gặp lỗi này biết ngay phải làm gì.
    """
    raise AppException(
        ErrorCode.FORBIDDEN,
        f"Loại tài nguyên '{owner_type}' chưa khai báo luật truy cập tệp đính kèm",
        403,
    )


# ═══════════════════════════ M1 — mẫu / phiếu / kết quả ═══════════════════════════


def _read_sample(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import sample_common

    sample_common.deny_office(user)
    sample = sample_common.get_sample_or_404(db, owner_id)
    sample_common.assert_read_scope(user, sample.department_id)


def _write_sample(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import sample_common

    sample_common.deny_office(user)
    sample = sample_common.get_sample_or_404(db, owner_id)
    sample_common.assert_write_scope(user, sample.department_id)


def _get_request_or_404(db: Session, owner_id: uuid.UUID):
    from app.models.test_request import TestRequest

    req = db.get(TestRequest, owner_id)
    if req is None or req.deleted_at is not None:
        raise not_found("Không tìm thấy phiếu yêu cầu")
    return req


def _read_test_request(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import sample_common

    sample_common.deny_office(user)
    req = _get_request_or_404(db, owner_id)
    sample_common.assert_read_scope(user, req.department_id)


def _write_test_request(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import sample_common

    sample_common.deny_office(user)
    req = _get_request_or_404(db, owner_id)
    sample_common.assert_write_scope(user, req.department_id)


def _read_sample_result(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import sample_attachment_service, sample_common

    sample_common.deny_office(user)
    # Cùng luật với GET /results/{id}/attachments: kết quả chưa duyệt chỉ nhóm liên quan.
    sample_attachment_service.assert_can_read_result_files(db, user=user, result_id=owner_id)


def _write_sample_result(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import sample_attachment_service, sample_common

    sample_common.deny_office(user)
    sample_attachment_service.assert_can_write_result_files(db, user=user, result_id=owner_id)


# ═══════════════════════════ M3 — tài liệu ═══════════════════════════


def _read_document_version(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.models.document import DocumentVersion
    from app.services import document_common as dc

    version = db.get(DocumentVersion, owner_id)
    if version is None or version.deleted_at is not None:
        raise dc.version_not_found()
    doc = dc.get_document_or_404(db, version.document_id)
    if not dc.can_view_restricted(user, doc):
        raise dc.restricted_access()
    if not dc.can_view_unpublished_version(user, doc, version):
        # Mirror hành vi của module: bản chưa ban hành thì coi như không tồn tại với
        # người ngoài nhóm soạn thảo — không tiết lộ là nó đang được soạn.
        raise dc.version_not_found()


def _write_document_version(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.core.exceptions import unprocessable
    from app.models.document import DocumentVersion
    from app.services import document_common as dc

    version = db.get(DocumentVersion, owner_id)
    if version is None or version.deleted_at is not None:
        raise dc.version_not_found()
    doc = dc.get_document_or_404(db, version.document_id)
    dc.deny_office_write(user)
    if not (version.created_by == user.id or dc.can_approve(user, doc.department_id)):
        raise dc.forbidden("Bạn không có quyền sửa phiên bản này")
    if version.status != "draft":
        raise unprocessable(
            ErrorCode.VERSION_LOCKED,
            "Chỉ phiên bản nháp được sửa (đã gửi duyệt/ban hành thì bất biến)",
        )


# ═══════════════════════════ Kho biểu mẫu VILAS ═══════════════════════════


def _assert_form_permission(db: Session, user: CurrentUser, action: str) -> None:
    from app.core.rbac import has_permission

    if not has_permission(db, user.role, "form", action):
        raise AppException(ErrorCode.FORBIDDEN, "Bạn không có quyền trên kho biểu mẫu", 403)


def _read_form_template(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import form_file_service as ffs

    _assert_form_permission(db, user, "read")
    ffs._get_template_or_404(db, owner_id)


def _write_form_template(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import form_file_service as ffs

    _assert_form_permission(db, user, "manage")
    ffs._get_template_or_404(db, owner_id)


def _read_form_submission(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import form_file_service as ffs

    _assert_form_permission(db, user, "read")
    sub = ffs._get_submission_or_404(db, owner_id)
    ffs._check_submission_scope(user, sub)


def _write_form_submission(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import form_file_service as ffs

    _assert_form_permission(db, user, "submit")
    sub = ffs._get_submission_or_404(db, owner_id)
    ffs._check_submission_scope(user, sub)
    ffs._check_submission_writable(sub)  # đã duyệt → khoá tệp


# ═══════════════════════════ M4 — nhân sự & NCKH ═══════════════════════════


def _read_hr_profile(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    # owner_id của tệp năng lực là user_id của chủ hồ sơ (xem hr_profiles.py).
    from app.services import hr_service

    hr_service._assert_competence_read(user, owner_id)


def _write_hr_profile(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import hr_common as hc

    hc.assert_can_manage_competence(user)


def _read_publication(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    # Đọc NCKH mở cho cả Văn phòng (research._guard_read), nhưng phạm vi bài báo do
    # get_publication quyết định — nó raise 403/404 nếu ngoài scope.
    from app.services.research import publication_service

    publication_service.get_publication(db, user=user, pub_id=owner_id)


def _write_publication(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import hr_common as hc
    from app.services.research import publication_service

    hc.assert_research_access(user)  # ghi NCKH: chặn office
    publication_service.get_publication(db, user=user, pub_id=owner_id)


# ═══════════════════════════ M2 — hoá chất ═══════════════════════════


def _read_chemical(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import chemical_common as cc

    cc.get_chemical_or_404(db, owner_id)  # đọc MSDS mở cho mọi vai trò đã đăng nhập


def _write_chemical(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import chemical_common as cc

    chem = cc.get_chemical_or_404(db, owner_id)
    cc.assert_can_create(db, user)
    cc.assert_write_scope(user, chem.department_id)


def _read_chem_lot(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import chemical_common as cc

    cc.get_lot_or_404(db, owner_id)


def _write_chem_lot(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.models.chemical import Chemical
    from app.services import chemical_common as cc

    lot = cc.get_lot_or_404(db, owner_id)
    cc.assert_can_transact(db, user)
    chem = db.get(Chemical, lot.chemical_id)
    if chem is not None:
        cc.assert_write_scope(user, chem.department_id)


# ═══════════════════════════ M5 — thiết bị ═══════════════════════════


def _read_equipment(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import equipment_common as ec

    ec.get_equipment_or_404(db, owner_id)


def _write_equipment(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.services import equipment_common as ec

    # CỐ Ý dùng assert_can_create (equipment:create) chứ không phải assert_can_update:
    # đây là luật mà endpoint riêng POST /equipments/{id}/attachments đang áp
    # (equipment_service.add_attachment). Đổi sang :update ở đây sẽ tạo ra hai luật
    # khác nhau cho cùng một hành động — đúng thứ file này sinh ra để tránh.
    eq = ec.get_equipment_or_404(db, owner_id)
    ec.assert_can_create(db, user)
    ec.assert_write_scope(user, eq.department_id)


def _read_calibration(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.models.equipment import CalibrationRecord

    if db.get(CalibrationRecord, owner_id) is None:
        raise not_found("Không tìm thấy bản ghi hiệu chuẩn")


def _write_calibration(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.models.equipment import CalibrationRecord
    from app.services import equipment_common as ec

    rec = db.get(CalibrationRecord, owner_id)
    if rec is None:
        raise not_found("Không tìm thấy bản ghi hiệu chuẩn")
    ec.assert_can_calibrate(db, user)
    eq = ec.get_equipment_or_404(db, rec.equipment_id)
    ec.assert_write_scope(user, eq.department_id)


# ═══════════════════════════ Nhận & chuyển mẫu ═══════════════════════════


def _assert_intake_permission(db: Session, user: CurrentUser, action: str) -> None:
    from app.core.rbac import has_permission

    if not has_permission(db, user.role, "intake", action):
        raise AppException(ErrorCode.FORBIDDEN, "Bạn không có quyền trên phiếu nhận mẫu", 403)


def _read_intake(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.models.sample_flow import SampleIntake

    _assert_intake_permission(db, user, "read")
    if db.get(SampleIntake, owner_id) is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")


def _write_intake(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.models.sample_flow import SampleIntake

    _assert_intake_permission(db, user, "manage")
    if db.get(SampleIntake, owner_id) is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")


def _read_dispatch(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.models.sample_flow import SampleDispatch

    _assert_intake_permission(db, user, "read")
    if db.get(SampleDispatch, owner_id) is None:
        raise not_found("Không tìm thấy phiếu chuyển mẫu")


def _write_dispatch(db: Session, user: CurrentUser, owner_id: uuid.UUID) -> None:
    from app.models.sample_flow import SampleDispatch

    _assert_intake_permission(db, user, "manage")
    if db.get(SampleDispatch, owner_id) is None:
        raise not_found("Không tìm thấy phiếu chuyển mẫu")


# ═══════════════════════════ Bảng định tuyến ═══════════════════════════
#
# CHỈ những owner_type có mặt ở đây mới truy cập được. 8 giá trị còn lại trong
# Attachment.VALID_OWNER_TYPES (research_project, research_contract, teaching_course,
# staff_activity, training_certificate, document, ...) chưa từng được ghi ở bất kỳ đâu
# trong backend — cố ý để rơi vào _deny() cho tới khi có module thật sự dùng.

_READ_GUARDS: dict[str, Guard] = {
    "sample": _read_sample,
    "test_request": _read_test_request,
    "sample_result": _read_sample_result,
    "document_version": _read_document_version,
    "form_template": _read_form_template,
    "form_submission": _read_form_submission,
    "hr_profile": _read_hr_profile,
    "publication": _read_publication,
    "chemical": _read_chemical,
    "chem_lot": _read_chem_lot,
    "equipment": _read_equipment,
    "calibration": _read_calibration,
    "sample_intake": _read_intake,
    "sample_dispatch": _read_dispatch,
}

_WRITE_GUARDS: dict[str, Guard] = {
    "sample": _write_sample,
    "test_request": _write_test_request,
    "sample_result": _write_sample_result,
    "document_version": _write_document_version,
    "form_template": _write_form_template,
    "form_submission": _write_form_submission,
    "hr_profile": _write_hr_profile,
    "publication": _write_publication,
    "chemical": _write_chemical,
    "chem_lot": _write_chem_lot,
    "equipment": _write_equipment,
    "calibration": _write_calibration,
    "sample_intake": _write_intake,
    "sample_dispatch": _write_dispatch,
}


def assert_can_read(db: Session, user: CurrentUser, *, owner_type: str, owner_id: uuid.UUID) -> None:
    """Kiểm quyền ĐỌC tệp theo đúng luật của module sở hữu. Raise nếu không được phép."""
    guard: Optional[Guard] = _READ_GUARDS.get(owner_type)
    if guard is None:
        _deny(owner_type)
    guard(db, user, owner_id)


def assert_can_write(db: Session, user: CurrentUser, *, owner_type: str, owner_id: uuid.UUID) -> None:
    """Kiểm quyền GẮN/THAY tệp. Cũng xác nhận owner TỒN TẠI — trước đây không kiểm,
    nên tạo được attachment trỏ tới owner_id không có thật (owner_id không có FK)."""
    guard: Optional[Guard] = _WRITE_GUARDS.get(owner_type)
    if guard is None:
        _deny(owner_type)
    guard(db, user, owner_id)
