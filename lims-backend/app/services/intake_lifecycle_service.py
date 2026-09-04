"""Vòng đời PHIẾU NHẬN MẪU — trạng thái, chấp nhận/từ chối, thanh toán (m28 + m42).

TÁCH RA VÌ ĐÂY LÀ RANH GIỚI THẬT
`sample_flow_service` trả lời "phiếu và chỉ tiêu chứa gì"; file này trả lời "phiếu
đang ở đâu trong quy trình và ai quyết". Hai câu hỏi đổi vì lý do khác nhau: nội dung
phiếu đổi theo biểu mẫu VILAS, còn vòng đời đổi theo quy trình vận hành.

QUYẾT ĐỊNH TẠI QUẦY — HAI ĐƯỜNG, KHÔNG PHẢI MỘT (m42)
Câu hỏi nghiệp vụ Q6 chưa chốt ("từ chối hẳn, hay nhận có bảo lưu?"), nên cả hai
đường đều mở, vì trong thực tế phòng thử nghiệm chúng cùng tồn tại:

  · nhận có bảo lưu → condition_status='not_acceptable' + condition_note, phiếu chạy tiếp
  · từ chối hẳn     → status='rejected' + lý do + người quyết + thời điểm

Cả hai đều bắt buộc mô tả sai lệch (CHECK ở tầng DB), vì ISO/IEC 17025 §7.4.2–7.4.3
đòi ghi nhận sai lệch điều kiện mẫu và bảo lưu trách nhiệm khi vẫn nhận.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException, not_found
from app.models.sample_flow import (
    INTAKE_NEXT, INTAKE_STATUS_LABELS, VALID_PAYMENT_STATUS, SampleIntake,
)
from app.services import audit_service, sample_flow_service as flow

# Trạng thái đòi phải nêu lý do. 'cancelled' là thao tác hành chính (nhập nhầm, khách
# rút) nên lý do là tuỳ chọn; 'rejected' là QUYẾT ĐỊNH KỸ THUẬT nên bắt buộc.
_REASON_REQUIRED = ("rejected",)


def _get_or_404(db: Session, intake_id: uuid.UUID) -> SampleIntake:
    it = db.get(SampleIntake, intake_id)
    if it is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")
    return it


def _assert_can_decide(user: CurrentUser) -> None:
    if not flow._privileged(user):
        raise AppException(
            ErrorCode.FORBIDDEN,
            "Chỉ Phòng nhận mẫu / lãnh đạo được đổi trạng thái phiếu",
            403,
        )


def change_status(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, new_status: str,
    note: Optional[str], correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Chuyển trạng thái phiếu theo state machine (chặn nhảy bậc không hợp lệ)."""
    _assert_can_decide(user)
    it = _get_or_404(db, intake_id)

    allowed = INTAKE_NEXT.get(it.status, ())
    if new_status not in allowed:
        raise AppException(
            ErrorCode.INVALID_TRANSITION,
            f"Không thể chuyển từ '{INTAKE_STATUS_LABELS.get(it.status, it.status)}' sang "
            f"'{INTAKE_STATUS_LABELS.get(new_status, new_status)}'",
            409,
        )

    reason = (note or "").strip()
    if new_status in _REASON_REQUIRED and not reason:
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            "Từ chối tiếp nhận mẫu phải nêu lý do (thiếu mẫu, sai bao bì, "
            "sai nhiệt độ bảo quản…) — hồ sơ cần giải trình được",
            400,
        )

    old = it.status
    it.status = new_status
    now = datetime.now(timezone.utc)
    if new_status == "rejected":
        # Ghi rõ AI quyết và LÚC NÀO, không chỉ nối vào ô ghi chú chung.
        it.rejected_reason = reason
        it.decided_by = user.id
        it.decided_at = now
    if reason:
        it.note = f"{it.note}\n{reason}" if it.note else reason
    it.updated_by = user.id
    it.updated_at = now

    audit_service.log_action(
        db, action="INTAKE_STATUS_CHANGE", resource="sample_intake", user_id=user.id,
        resource_id=it.id, correlation_id=correlation_id, ip=ip,
        detail={"code": it.code, "from": old, "to": new_status, "reason": reason or None},
    )
    db.commit()
    db.refresh(it)
    return flow._serialize_intake(db, it, user=user)


def record_condition(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, changes: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Ghi nhận TÌNH TRẠNG và SỐ LƯỢNG mẫu lúc tiếp nhận (m42).

    Nhận mẫu không đạt vẫn hợp lệ — nhưng phải mô tả sai lệch. CHECK ở tầng DB
    (`ck_intake_condition_note`) chốt lại, nên không có đường nào ghi 'not_acceptable'
    mà bỏ trống mô tả, kể cả khi ai đó gọi thẳng service.
    """
    _assert_can_decide(user)
    it = _get_or_404(db, intake_id)
    if it.status in ("completed", "cancelled", "rejected"):
        raise AppException(
            ErrorCode.INVALID_STATE,
            f"Phiếu {it.code} đã đóng — không sửa được tình trạng mẫu",
            409,
        )

    cs = changes.get("condition_status")
    if cs is not None:
        if cs not in ("acceptable", "not_acceptable"):
            raise AppException(ErrorCode.VALIDATION_ERROR, "Tình trạng mẫu không hợp lệ", 400)
        note = (changes.get("condition_note") or it.condition_note or "").strip()
        if cs == "not_acceptable" and not note:
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                "Mẫu không đạt điều kiện tiếp nhận phải mô tả sai lệch "
                "(thiếu mẫu, sai bao bì, sai nhiệt độ bảo quản…)",
                400,
            )
        it.condition_status = cs
    for f in ("condition_note", "sample_count"):
        if f in changes and changes[f] is not None:
            setattr(it, f, changes[f])
    it.updated_by = user.id
    it.updated_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db, action="INTAKE_CONDITION", resource="sample_intake", user_id=user.id,
        resource_id=it.id, correlation_id=correlation_id, ip=ip,
        detail={"code": it.code, "condition_status": it.condition_status,
                "sample_count": it.sample_count},
    )
    db.commit()
    db.refresh(it)
    return flow._serialize_intake(db, it, user=user)


def update_payment(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, changes: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Ghi nhận thanh toán (khách chuyển khoản): trạng thái + số tiền + mã giao dịch."""
    if not flow._privileged(user):
        raise AppException(
            ErrorCode.FORBIDDEN, "Chỉ Phòng nhận mẫu / lãnh đạo được ghi nhận thanh toán", 403
        )
    it = _get_or_404(db, intake_id)

    ps = changes.get("payment_status")
    if ps is not None:
        if ps not in VALID_PAYMENT_STATUS:
            raise AppException(ErrorCode.VALIDATION_ERROR, "Trạng thái thanh toán không hợp lệ", 400)
        it.payment_status = ps
    for f in ("paid_amount", "payment_date", "payment_ref", "payment_note"):
        if f in changes:
            setattr(it, f, changes[f])
    it.updated_by = user.id
    it.updated_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db, action="INTAKE_PAYMENT_UPDATE", resource="sample_intake", user_id=user.id,
        resource_id=it.id, correlation_id=correlation_id, ip=ip,
        detail={"code": it.code, "payment_status": it.payment_status,
                "paid_amount": str(it.paid_amount) if it.paid_amount is not None else None},
    )
    db.commit()
    db.refresh(it)
    return flow._serialize_intake(db, it, user=user)
