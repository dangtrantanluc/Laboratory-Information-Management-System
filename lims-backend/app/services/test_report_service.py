"""Phát hành PHIẾU KẾT QUẢ THỬ NGHIỆM (m46) — BM 7.8/01/RIBE.

Module này quản lý CHỨNG TỪ, không quản lý số liệu. Nội dung phiếu nằm trong tệp mà
Phòng nhận mẫu soạn ngoài hệ thống rồi tải lên; ở đây kiểm soát: bản nào đã ra khỏi
Viện, lúc nào, ai chịu trách nhiệm, và bản nào đã bị thay thế.

VÌ SAO KHÔNG MƯỢN CƠ CHẾ DUYỆT CỦA M1
`sample_results` có versioning bất biến và chặn tự duyệt, và `dispatch_result_bridge`
đã nối luồng nhận mẫu vào đó. Nhưng cơ chế ấy dành cho SỐ LIỆU DO NGƯỜI TRONG HỆ THỐNG
NHẬP: nó hỏi "ai gõ con số này, ai duyệt nó". Ở đây tệp đã được soạn và ký ngoài hệ
thống; câu hỏi là "chứng từ nào đã trao cho khách". Ép hai việc khác nhau vào một cơ chế
sẽ đẻ ra một luồng duyệt hình thức mà không ai đọc.

QUY ƯỚC GIAO DỊCH
Hàm nghiệp vụ tự commit (giống sample_flow_service / intake_lifecycle_service). Hàm
`assert_*` chỉ kiểm tra, không ghi — chúng được `attachment_authz` gọi lại để đường
generic `POST /attachments` và đường riêng của module dùng CHUNG một luật.
"""
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import CurrentUser
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException, conflict, not_found, unprocessable
from app.core.rbac import has_permission
from app.models.attachment import Attachment
from app.models.sample_flow import IntakeContact, SampleIntake
from app.models.test_report import (
    DELIVERY_METHOD_LABELS,
    TEST_REPORT_NEXT,
    TEST_REPORT_STATUS_LABELS,
    TestReport,
)
from app.services import audit_service, notification_service, sample_common, storage_service

OWNER_TYPE = "test_report"

# BR-02 — đã chốt: nhận CẢ PDF LẪN DOCX ở mọi trạng thái.
#
# Rủi ro đã cân nhắc và chấp nhận: bản .docx trao cho khách là bản khách sửa được. Đổi
# lại, hai thứ dưới đây trở thành THIẾT YẾU chứ không phải tuỳ chọn — chúng là lý do
# vẫn còn một bản đối chiếu khi có tranh chấp:
#   · assert_can_write_files() khoá tệp ngay khi phiếu rời 'draft'
#   · mọi lượt tải về đều ghi TEST_REPORT_DOWNLOAD vào audit
#
# CỐ Ý khai allowlist RIÊNG thay vì nới `attachment_common.BASE_ALLOWED_MIME`: nới ở đó
# là mở docx cho cả raw data kết quả M1 lẫn chứng từ gửi mẫu, những chỗ không hỏi xin.
TEST_REPORT_ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword",  # .doc — bản Word cũ, Viện vẫn còn dùng (xem BM 7.1.02)
}

# Trạng thái phiếu nhận mà việc lập phiếu kết quả không còn ý nghĩa (BR-01).
_CLOSED_INTAKE_STATUS = ("cancelled", "rejected")

# Hậu tố bản sửa đổi ở cuối số hiệu: "26N323-R1" → tách được gốc "26N323".
_REVISION_SUFFIX = re.compile(r"-R\d+$")


# ═══════════════════════════ Tra cứu & kiểm quyền ═══════════════════════════


def _get_intake_or_404(db: Session, intake_id: uuid.UUID) -> SampleIntake:
    it = db.get(SampleIntake, intake_id)
    if it is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")
    return it


def _get_or_404(db: Session, report_id: uuid.UUID) -> TestReport:
    r = db.get(TestReport, report_id)
    if r is None or r.deleted_at is not None:
        raise not_found("Không tìm thấy phiếu kết quả")
    return r


def _assert_permission(db: Session, user: CurrentUser, action: str) -> None:
    """Quyền của module. CỐ Ý không tái dùng `intake:read`.

    `intake:read` đang được cấp cho staff và lab_manager với scope 'all'. Tệp BM 7.8/01
    chứa nguyên văn tên và địa chỉ khách hàng ở ngay bảng đầu phiếu — đúng những trường
    m26 che với khối lab. Gác module này bằng `intake:read` là vô hiệu hoá m26 qua một
    đường vòng hai lệnh gọi, đúng loại lỗ hổng `attachment_authz` sinh ra để chặn.
    """
    if not has_permission(db, user.role, OWNER_TYPE, action):
        raise AppException(
            ErrorCode.FORBIDDEN,
            "Bạn không có quyền trên phiếu kết quả thử nghiệm",
            403,
        )


def assert_can_read_files(db: Session, *, user: CurrentUser, report_id: uuid.UUID) -> None:
    """Quyền ĐỌC tệp. `attachment_authz` gọi lại hàm này cho đường generic."""
    _assert_permission(db, user, "read")
    _get_or_404(db, report_id)


def assert_can_write_files(db: Session, *, user: CurrentUser, report_id: uuid.UUID) -> None:
    """Quyền GẮN/XOÁ tệp — chỉ khi phiếu còn là bản nháp (BR-06).

    Tách ra khỏi `upload_file` để đường generic `POST /attachments` (attachment_authz)
    dùng CHUNG một luật. Hai đường lệch nhau là cách lỗ hổng cũ hình thành: một bên khoá
    tệp sau khi phát hành, bên kia vẫn cho ghi đè.
    """
    _assert_permission(db, user, "manage")
    report = _get_or_404(db, report_id)
    if report.status != "draft":
        raise unprocessable(
            ErrorCode.RESULT_LOCKED,
            f"Phiếu kết quả {report.report_no} đã phát hành — muốn đổi nội dung "
            "phải tạo bản sửa đổi",
        )


def _assert_draft(report: TestReport) -> None:
    if report.status != "draft":
        raise unprocessable(
            ErrorCode.RESULT_LOCKED,
            f"Phiếu kết quả {report.report_no} đã phát hành — không sửa được nữa",
        )


def _assert_transition(report: TestReport, new_status: str) -> None:
    allowed = TEST_REPORT_NEXT.get(report.status, ())
    if new_status not in allowed:
        raise AppException(
            ErrorCode.INVALID_TRANSITION,
            f"Không thể chuyển phiếu kết quả từ "
            f"'{TEST_REPORT_STATUS_LABELS.get(report.status, report.status)}' sang "
            f"'{TEST_REPORT_STATUS_LABELS.get(new_status, new_status)}'",
            409,
        )


# ═══════════════════════════ Số hiệu phiếu ═══════════════════════════


def _report_no_taken(
    db: Session, code: str, *, exclude_id: Optional[uuid.UUID] = None
) -> bool:
    conds = [TestReport.report_no == code, TestReport.deleted_at.is_(None)]
    if exclude_id is not None:
        conds.append(TestReport.id != exclude_id)
    return db.execute(select(TestReport.id).where(*conds).limit(1)).first() is not None


def _next_report_no(db: Session, base: str) -> str:
    """Số hiệu còn trống, bắt đầu từ `base` rồi `base-2`, `base-3`…

    Phiếu song song (tách theo hộ) là chuyện có thật, nên đụng số hiệu không phải lỗi —
    chỉ cần một số kế tiếp có thể đoán ra khi nhìn vào sổ.
    """
    base = (base or "").strip() or "KQ"
    if not _report_no_taken(db, base):
        return base
    for n in range(2, 1000):
        candidate = f"{base}-{n}"
        if not _report_no_taken(db, candidate):
            return candidate
    # Không có lối thoát hợp lý ở đây: 999 phiếu cùng một mã nghĩa là dữ liệu đã sai
    # từ trước, và sinh bừa một mã nữa chỉ giấu vấn đề đi.
    raise conflict(
        ErrorCode.DUPLICATE_CODE,
        f"Không sinh được số hiệu còn trống từ '{base}' — kiểm tra lại mã phiếu nhận",
    )


def _resolve_report_no(
    db: Session, raw: Optional[str], *, fallback: str, exclude_id: Optional[uuid.UUID] = None
) -> str:
    """Chuẩn hoá số hiệu nhân viên nhập; bỏ trống thì sinh theo mã phiếu nhận.

    Kiểm trùng ở tầng service để trả 409 có thông báo tiếng Việt, thay vì để
    `uq_tr_report_no` nổ IntegrityError thành 500 — cùng cách `_resolve_intake_code`
    đang xử lý mã phiếu nhận.
    """
    code = (raw or "").strip()
    if not code:
        return _next_report_no(db, fallback)
    if _report_no_taken(db, code, exclude_id=exclude_id):
        raise conflict(
            ErrorCode.DUPLICATE_CODE, f"Số hiệu phiếu kết quả '{code}' đã tồn tại"
        )
    return code


# ═══════════════════════════ Serialize ═══════════════════════════


def _files_of(db: Session, report_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(Attachment)
        .where(
            Attachment.owner_type == OWNER_TYPE,
            Attachment.owner_id == report_id,
            Attachment.deleted_at.is_(None),
        )
        .order_by(Attachment.uploaded_at.asc())
    ).scalars().all()
    return [
        {
            "id": a.id,
            "file_name": a.file_name,
            "mime": a.mime,
            "size": a.size,
            "uploaded_by_name": sample_common.user_name(db, a.uploaded_by),
            "uploaded_at": a.uploaded_at,
        }
        for a in rows
    ]


def _days_late(db: Session, report: TestReport, intake: Optional[SampleIntake]) -> Optional[int]:
    """BR-12 — trả trễ bao nhiêu ngày so với ngày hẹn trên phiếu (m39).

    None khi chưa phát hành hoặc ô "Ngày hẹn trả kết quả" không phân giải nổi (m39 cố ý
    để NULL thay vì đoán). Số âm = trả sớm. Chỉ HIỂN THỊ, không chặn gì — nhưng đây là
    KPI thật đầu tiên hệ thống có về việc trả kết quả đúng hẹn.
    """
    if report.issued_at is None or intake is None or intake.due_date_at is None:
        return None
    return (report.issued_at - intake.due_date_at).days


def _serialize(
    db: Session, report: TestReport, *, intake: Optional[SampleIntake] = None
) -> dict:
    if intake is None:
        intake = db.get(SampleIntake, report.intake_id)
    superseded = (
        db.get(TestReport, report.supersedes_id) if report.supersedes_id else None
    )
    return {
        "id": report.id,
        "intake_id": report.intake_id,
        "intake_code": intake.code if intake else None,
        "report_no": report.report_no,
        "version": report.version,
        "supersedes_id": report.supersedes_id,
        "supersedes_report_no": superseded.report_no if superseded else None,
        "revision_reason": report.revision_reason,
        "status": report.status,
        "status_label": TEST_REPORT_STATUS_LABELS.get(report.status, report.status),
        "next_statuses": list(TEST_REPORT_NEXT.get(report.status, ())),
        "title": report.title,
        "note": report.note,
        "issued_at": report.issued_at,
        "issued_by": report.issued_by,
        "issued_by_name": sample_common.user_name(db, report.issued_by),
        "delivered_at": report.delivered_at,
        "delivery_method": report.delivery_method,
        "delivery_method_label": DELIVERY_METHOD_LABELS.get(report.delivery_method or ""),
        "delivered_to": report.delivered_to,
        "delivery_note": report.delivery_note,
        "revoked_at": report.revoked_at,
        "revoked_by_name": sample_common.user_name(db, report.revoked_by),
        "revoked_reason": report.revoked_reason,
        "days_late": _days_late(db, report, intake),
        "created_by_name": sample_common.user_name(db, report.created_by),
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "files": _files_of(db, report.id),
    }


# ═══════════════════════════ Thông báo ═══════════════════════════


def _notify_issued(db: Session, *, user: CurrentUser, report: TestReport, it: SampleIntake) -> None:
    """Báo người đã nhận mẫu của phiếu, nếu người phát hành là người khác.

    Không commit — chạy trong cùng giao dịch với thao tác phát hành, đúng quy ước
    `sample_flow_notify`: phát hành thất bại thì thông báo cũng phải biến mất.
    """
    if it.received_by == user.id:
        return
    notification_service.create_notification(
        db,
        user_id=it.received_by,
        type="TEST_REPORT_ISSUED",
        title="Đã phát hành phiếu kết quả",
        body=f"{report.report_no} · phiếu {it.code}",
        ref_type=OWNER_TYPE,
        ref_id=report.id,
    )


def _notify_revoked(db: Session, *, user: CurrentUser, report: TestReport, it: SampleIntake) -> None:
    """Báo MỌI NGƯỜI ĐÃ TỪNG TẢI TỆP NÀY VỀ — họ có thể đã gửi bản sai đi rồi.

    Đây là lúc duy nhất trong module mà thông báo thực sự khẩn, nên người nhận lấy từ
    dấu vết tải về (BR-13) chứ không phải từ cơ cấu tổ chức.
    """
    from app.models.audit_log import AuditLog

    downloaders = db.execute(
        select(AuditLog.user_id).where(
            AuditLog.action == "TEST_REPORT_DOWNLOAD",
            AuditLog.resource_id == report.id,
            AuditLog.user_id.isnot(None),
        ).distinct()
    ).scalars().all()

    targets = {uid for uid in downloaders if uid and uid != user.id}
    targets.add(it.received_by)
    targets.discard(user.id)
    for uid in targets:
        notification_service.create_notification(
            db,
            user_id=uid,
            type="TEST_REPORT_REVOKED",
            title="Phiếu kết quả đã bị thu hồi",
            body=f"{report.report_no} · phiếu {it.code} — kiểm tra lại bản đã gửi khách",
            ref_type=OWNER_TYPE,
            ref_id=report.id,
        )


# ═══════════════════════════ Đọc ═══════════════════════════


def list_reports(db: Session, *, user: CurrentUser, intake_id: uuid.UUID) -> list[dict]:
    _assert_permission(db, user, "read")
    it = _get_intake_or_404(db, intake_id)
    rows = db.execute(
        select(TestReport)
        .where(TestReport.intake_id == intake_id, TestReport.deleted_at.is_(None))
        .order_by(TestReport.created_at.asc())
    ).scalars().all()
    return [_serialize(db, r, intake=it) for r in rows]


def get_report(db: Session, *, user: CurrentUser, report_id: uuid.UUID) -> dict:
    _assert_permission(db, user, "read")
    return _serialize(db, _get_or_404(db, report_id))


def has_issued_report(db: Session, intake_id: uuid.UUID) -> bool:
    """BR-08 — phiếu đã có chứng từ phát hành chưa.

    'revoked' KHÔNG tính: một chứng từ đã thu hồi nghĩa là kết quả chưa được trao hợp lệ,
    nên phiếu không được coi là đã trả kết quả.
    """
    return db.execute(
        select(TestReport.id).where(
            TestReport.intake_id == intake_id,
            TestReport.deleted_at.is_(None),
            TestReport.status.in_(("issued", "delivered")),
        ).limit(1)
    ).first() is not None


def suggested_recipient(db: Session, intake_id: uuid.UUID) -> Optional[str]:
    """Người nhận kết quả theo vai trên phiếu (m43) — FE điền sẵn ô "đã gửi cho ai"."""
    row = db.execute(
        select(IntakeContact).where(
            IntakeContact.intake_id == intake_id,
            IntakeContact.role == "result_recipient",
        ).limit(1)
    ).scalars().first()
    return row.full_name if row else None


# ═══════════════════════════ Ghi ═══════════════════════════


def create_report(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, fields: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Lập bản NHÁP cho một phiếu nhận mẫu (BR-01)."""
    _assert_permission(db, user, "manage")
    it = _get_intake_or_404(db, intake_id)
    if it.status in _CLOSED_INTAKE_STATUS:
        raise AppException(
            ErrorCode.INVALID_STATE,
            f"Phiếu {it.code} đã {'huỷ' if it.status == 'cancelled' else 'bị từ chối tiếp nhận'}"
            " — không lập phiếu kết quả được",
            409,
        )

    report = TestReport(
        intake_id=it.id,
        report_no=_resolve_report_no(db, fields.get("report_no"), fallback=it.code),
        version=1,
        status="draft",
        title=fields.get("title"),
        note=fields.get("note"),
        issued_at=fields.get("issued_at"),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(report)
    db.flush()
    audit_service.log_action(
        db, action="TEST_REPORT_CREATE", resource=OWNER_TYPE, user_id=user.id,
        resource_id=report.id, correlation_id=correlation_id, ip=ip,
        detail={"intake_code": it.code, "report_no": report.report_no},
    )
    db.commit()
    db.refresh(report)
    return _serialize(db, report, intake=it)


def update_report(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, changes: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Sửa bản nháp. Đã phát hành thì từ chối (BR-06)."""
    _assert_permission(db, user, "manage")
    report = _get_or_404(db, report_id)
    _assert_draft(report)

    if "report_no" in changes:
        report.report_no = _resolve_report_no(
            db, changes["report_no"], fallback=report.report_no, exclude_id=report.id
        )
    for f in ("title", "note", "issued_at"):
        if f in changes:
            setattr(report, f, changes[f])
    report.updated_by = user.id
    report.updated_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db, action="TEST_REPORT_UPDATE", resource=OWNER_TYPE, user_id=user.id,
        resource_id=report.id, correlation_id=correlation_id, ip=ip,
        detail={"report_no": report.report_no, "fields": sorted(changes.keys())},
    )
    db.commit()
    db.refresh(report)
    return _serialize(db, report)


def issue_report(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, issued_at: Optional[date],
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Phát hành: khoá tệp lại và ghi ai chịu trách nhiệm (BR-04, BR-06)."""
    _assert_permission(db, user, "manage")
    report = _get_or_404(db, report_id)
    _assert_transition(report, "issued")

    if not _files_of(db, report.id):
        raise unprocessable(
            ErrorCode.VALIDATION_ERROR,
            "Chưa có tệp phiếu kết quả — tải tệp lên trước khi phát hành",
        )

    it = _get_intake_or_404(db, report.intake_id)
    when = issued_at or report.issued_at or datetime.now(timezone.utc).date()
    # BR-11 — ngày trên giấy tờ không được sớm hơn ngày nhận mẫu.
    if it.received_at is not None and when < it.received_at.date():
        raise unprocessable(
            ErrorCode.VALIDATION_ERROR,
            f"Ngày phát hành không được trước ngày nhận mẫu "
            f"({it.received_at.date().strftime('%d/%m/%Y')})",
        )

    report.issued_at = when
    report.issued_by = user.id
    report.status = "issued"
    report.updated_by = user.id
    report.updated_at = datetime.now(timezone.utc)

    _notify_issued(db, user=user, report=report, it=it)
    audit_service.log_action(
        db, action="TEST_REPORT_ISSUE", resource=OWNER_TYPE, user_id=user.id,
        resource_id=report.id, correlation_id=correlation_id, ip=ip,
        detail={
            "intake_code": it.code, "report_no": report.report_no,
            "version": report.version, "issued_at": when.isoformat(),
        },
    )
    db.commit()
    db.refresh(report)
    return _serialize(db, report, intake=it)


def deliver_report(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, fields: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Ghi nhận đã trao khách — mốc "trả kết quả" thật của phiếu."""
    _assert_permission(db, user, "manage")
    report = _get_or_404(db, report_id)
    _assert_transition(report, "delivered")

    when = fields.get("delivered_at") or datetime.now(timezone.utc)
    report.delivered_at = when
    report.delivery_method = fields.get("delivery_method")
    report.delivered_to = (
        fields.get("delivered_to") or suggested_recipient(db, report.intake_id)
    )
    report.delivery_note = fields.get("delivery_note")
    report.status = "delivered"
    report.updated_by = user.id
    report.updated_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db, action="TEST_REPORT_DELIVER", resource=OWNER_TYPE, user_id=user.id,
        resource_id=report.id, correlation_id=correlation_id, ip=ip,
        detail={
            "report_no": report.report_no,
            "delivery_method": report.delivery_method,
            "delivered_to": report.delivered_to,
        },
    )
    db.commit()
    db.refresh(report)
    return _serialize(db, report)


def revoke_report(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, reason: str,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Thu hồi bản đã phát hành. Lý do bắt buộc — `ck_tr_revoked` chốt lại ở DB."""
    _assert_permission(db, user, "manage")
    report = _get_or_404(db, report_id)
    _assert_transition(report, "revoked")

    text_reason = (reason or "").strip()
    if not text_reason:
        raise unprocessable(
            ErrorCode.VALIDATION_ERROR,
            "Thu hồi phiếu kết quả phải nêu lý do — hồ sơ cần giải trình được",
        )

    it = _get_intake_or_404(db, report.intake_id)
    report.status = "revoked"
    report.revoked_at = datetime.now(timezone.utc)
    report.revoked_by = user.id
    report.revoked_reason = text_reason
    report.updated_by = user.id
    report.updated_at = report.revoked_at

    _notify_revoked(db, user=user, report=report, it=it)
    audit_service.log_action(
        db, action="TEST_REPORT_REVOKE", resource=OWNER_TYPE, user_id=user.id,
        resource_id=report.id, correlation_id=correlation_id, ip=ip,
        detail={"report_no": report.report_no, "reason": text_reason},
    )
    db.commit()
    db.refresh(report)
    return _serialize(db, report, intake=it)


def create_revision(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, reason: str,
    report_no: Optional[str], correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Bản sửa đổi = bản ghi MỚI version+1; bản cũ chuyển 'revoked'.

    KHÔNG viết đè bản cũ: khách đang cầm nó trên tay, và ISO/IEC 17025 §7.8.8.2 đòi bản
    sửa phải nhận diện được và tham chiếu được tới bản gốc. Tệp KHÔNG được sao chép sang
    bản mới — người soạn phải tải lên bản đã sửa, và việc phải làm thao tác đó là điều
    duy nhất bảo đảm bản mới thật sự là bản mới.
    """
    _assert_permission(db, user, "manage")
    old = _get_or_404(db, report_id)
    if old.status == "draft":
        raise unprocessable(
            ErrorCode.INVALID_STATE,
            "Bản nháp thì sửa trực tiếp, không cần tạo bản sửa đổi",
        )
    if old.status == "revoked":
        raise unprocessable(
            ErrorCode.INVALID_STATE,
            f"Phiếu {old.report_no} đã thu hồi — tạo bản sửa đổi từ bản đang có hiệu lực",
        )

    text_reason = (reason or "").strip()
    if not text_reason:
        raise unprocessable(
            ErrorCode.VALIDATION_ERROR, "Tạo bản sửa đổi phải nêu lý do sửa"
        )

    it = _get_intake_or_404(db, old.intake_id)
    new_version = old.version + 1
    # Gốc số hiệu = bỏ hậu tố -R cũ, để bản sửa của bản sửa vẫn ra "26N323-R2" chứ
    # không phải "26N323-R1-R2".
    base = _REVISION_SUFFIX.sub("", old.report_no)
    fallback = f"{base}-R{new_version - 1}"

    new = TestReport(
        intake_id=old.intake_id,
        report_no=_resolve_report_no(db, report_no, fallback=fallback),
        version=new_version,
        supersedes_id=old.id,
        revision_reason=text_reason,
        status="draft",
        title=old.title,
        note=old.note,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(new)
    db.flush()

    now = datetime.now(timezone.utc)
    old.status = "revoked"
    old.revoked_at = now
    old.revoked_by = user.id
    old.revoked_reason = f"Thay thế bởi bản sửa đổi {new.report_no}: {text_reason}"
    old.updated_by = user.id
    old.updated_at = now

    _notify_revoked(db, user=user, report=old, it=it)
    audit_service.log_action(
        db, action="TEST_REPORT_REVISE", resource=OWNER_TYPE, user_id=user.id,
        resource_id=new.id, correlation_id=correlation_id, ip=ip,
        detail={
            "supersedes_id": str(old.id), "supersedes_report_no": old.report_no,
            "report_no": new.report_no, "version": new_version, "reason": text_reason,
        },
    )
    db.commit()
    db.refresh(new)
    return _serialize(db, new, intake=it)


def delete_report(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Xoá MỀM, chỉ bản nháp (BR-07). Đã phát hành thì thu hồi, không xoá."""
    _assert_permission(db, user, "manage")
    report = _get_or_404(db, report_id)
    if report.status != "draft":
        raise unprocessable(
            ErrorCode.RESULT_LOCKED,
            f"Phiếu kết quả {report.report_no} đã phát hành — dùng chức năng thu hồi "
            "thay vì xoá",
        )

    now = datetime.now(timezone.utc)
    report.deleted_at = now
    report.updated_by = user.id
    report.updated_at = now
    # Tệp đi theo phiếu: để lại thì chúng thành mồ côi, và `uq_tr_report_no` là
    # partial index nên số hiệu được trả lại cho lần lập sau.
    for att in db.execute(
        select(Attachment).where(
            Attachment.owner_type == OWNER_TYPE,
            Attachment.owner_id == report.id,
            Attachment.deleted_at.is_(None),
        )
    ).scalars().all():
        att.deleted_at = now

    audit_service.log_action(
        db, action="TEST_REPORT_DELETE", resource=OWNER_TYPE, user_id=user.id,
        resource_id=report.id, correlation_id=correlation_id, ip=ip,
        detail={"report_no": report.report_no},
    )
    db.commit()
    return {"id": report.id, "deleted": True}


# ═══════════════════════════ Tệp ═══════════════════════════


def _check_mime(mime: Optional[str]) -> None:
    if mime is None or mime.lower() not in TEST_REPORT_ALLOWED_MIME:
        raise unprocessable(
            ErrorCode.INVALID_FILE_TYPE,
            "Phiếu kết quả chỉ nhận tệp PDF hoặc Word (.doc/.docx)",
        )


def upload_file(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, file_name: str,
    content: bytes, mime: Optional[str], correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    assert_can_write_files(db, user=user, report_id=report_id)
    _check_mime(mime)
    if len(content) > settings.max_upload_size_bytes:
        raise unprocessable(
            ErrorCode.FILE_TOO_LARGE,
            f"Tệp vượt quá giới hạn {settings.max_upload_size_bytes // (1024 * 1024)}MB",
        )

    report = _get_or_404(db, report_id)
    file_key = storage_service.build_object_key(OWNER_TYPE, report_id, file_name)
    storage_service.put_object(file_key, content, content_type=mime)
    att = Attachment(
        owner_type=OWNER_TYPE,
        owner_id=report_id,
        file_key=file_key,
        file_name=file_name,
        mime=mime,
        size=len(content),
        uploaded_by=user.id,
    )
    db.add(att)
    db.flush()
    audit_service.log_action(
        db, action="TEST_REPORT_UPLOAD", resource=OWNER_TYPE, user_id=user.id,
        resource_id=report_id, correlation_id=correlation_id, ip=ip,
        detail={
            "report_no": report.report_no, "attachment_id": str(att.id),
            "file_name": file_name, "size": len(content),
        },
    )
    db.commit()
    db.refresh(att)
    return {
        "id": att.id,
        "file_name": att.file_name,
        "mime": att.mime,
        "size": att.size,
        "uploaded_by_name": user.full_name,
        "uploaded_at": att.uploaded_at,
    }


def delete_file(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, attachment_id: uuid.UUID,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Gỡ tệp khỏi bản nháp (xoá mềm). Đã phát hành thì `assert_can_write_files` chặn."""
    assert_can_write_files(db, user=user, report_id=report_id)
    att = db.execute(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.owner_type == OWNER_TYPE,
            Attachment.owner_id == report_id,
            Attachment.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if att is None:
        raise not_found("Không tìm thấy tệp đính kèm của phiếu kết quả")

    att.deleted_at = datetime.now(timezone.utc)
    audit_service.log_action(
        db, action="TEST_REPORT_FILE_DELETE", resource=OWNER_TYPE, user_id=user.id,
        resource_id=report_id, correlation_id=correlation_id, ip=ip,
        detail={"attachment_id": str(att.id), "file_name": att.file_name},
    )
    db.commit()
    return {"id": attachment_id, "deleted": True}


def download_file(
    db: Session, *, user: CurrentUser, report_id: uuid.UUID, attachment_id: uuid.UUID,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Cấp presigned URL và GHI VẾT (BR-13).

    Đường tải riêng của module tồn tại chính vì cái vết này: `GET /attachments/{id}`
    ghi audit dưới action chung ATTACHMENT_DOWNLOAD, không phân biệt được lượt tải một
    chứng từ đã trao khách với lượt tải một ảnh chụp mẫu. `_notify_revoked` đọc đúng
    vết này để biết phải báo cho ai khi phiếu bị thu hồi.
    """
    assert_can_read_files(db, user=user, report_id=report_id)
    att = db.execute(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.owner_type == OWNER_TYPE,
            Attachment.owner_id == report_id,
            Attachment.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if att is None:
        raise not_found("Không tìm thấy tệp đính kèm của phiếu kết quả")

    # PDF xem thẳng trên trình duyệt được; .doc/.docx thì luôn tải xuống (không có
    # trình xem, và phục vụ inline một mime ngoài allowlist an toàn là đường stored-XSS).
    inline = (att.mime or "").lower() == "application/pdf"
    url = storage_service.presigned_get_url(
        att.file_key, file_name=att.file_name, inline=inline
    )
    audit_service.log_action(
        db, action="TEST_REPORT_DOWNLOAD", resource=OWNER_TYPE, user_id=user.id,
        resource_id=report_id, correlation_id=correlation_id, ip=ip,
        detail={"attachment_id": str(att.id), "file_name": att.file_name},
    )
    db.commit()
    return {
        "id": att.id,
        "file_name": att.file_name,
        "mime": att.mime,
        "size": att.size,
        "download_url": url,
        "url_expires_at": datetime.now(timezone.utc)
        + timedelta(seconds=settings.presigned_url_ttl_seconds),
        "uploaded_by_name": sample_common.user_name(db, att.uploaded_by),
        "uploaded_at": att.uploaded_at,
    }
