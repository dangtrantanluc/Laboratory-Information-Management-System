"""M5 calibration service — ghi lần hiệu chuẩn (#9) + lịch sử (#8) + chi tiết (#10) +
tải CoC (#14) (FR-EQP-006..009, §6.4/§6.5/§8.4).

GHI HIỆU CHUẨN trong 1 DB transaction + SELECT FOR UPDATE trên thiết bị (tuần tự hóa ghi
cùng thiết bị). Insert calibration IMMUTABLE → upload CoC MinIO (attachments
owner_type='calibration') → tính next_due (relativedelta năm nhuận) → cập nhật
equipments.next_due_date NẾU là lần gần nhất (BR-EQP-008) → audit. Lỗi upload → rollback.

calibration_records BẤT BIẾN (D5, §8.4): trigger DB chặn UPDATE/DELETE + KHÔNG route
PATCH/DELETE. Đính chính = bản ghi mới (correction_of). Badge cảnh báo runtime — KHÔNG
khóa cứng: ghi hiệu chuẩn trên thiết bị quá hạn/fail vẫn cho phép (OQ#3, CONSTRAINT-3).
"""
import logging
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.attachment import Attachment
from app.models.equipment import CalibrationRecord, Equipment
from app.services import audit_service, equipment_common as ec, storage_service

logger = logging.getLogger("lims.calibration")


# ===== Serialize =====
def _cert_attachment(db: Session, calibration_id: uuid.UUID) -> Optional[Attachment]:
    return db.execute(
        select(Attachment)
        .where(
            Attachment.owner_type == "calibration",
            Attachment.owner_id == calibration_id,
            Attachment.deleted_at.is_(None),
        )
        .order_by(Attachment.uploaded_at.desc())
    ).scalars().first()


def _record_dict(db: Session, rec: CalibrationRecord, *, latest_at: Optional[date]) -> dict:
    cert = _cert_attachment(db, rec.id)
    return {
        "id": rec.id,
        "equipment_id": rec.equipment_id,
        "calibrated_at": rec.calibrated_at,
        "provider": rec.provider,
        "result": rec.result,
        "next_due_date": rec.next_due_date,
        "next_due_overridden": rec.next_due_overridden,
        "override_reason": rec.override_reason,
        "is_latest": latest_at is not None and rec.calibrated_at == latest_at,
        "cert_attachment_id": cert.id if cert else None,
        "cert_file_name": cert.file_name if cert else None,
        "note": rec.note,
        "correction_of": rec.correction_of,
        "created_by_name": ec.user_name(db, rec.created_by),
        "created_at": rec.created_at,
    }


# ===== #8 GET /equipments/:id/calibrations =====
def list_calibrations(
    db: Session,
    *,
    equipment_id: uuid.UUID,
    result: Optional[str],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    ec.get_equipment_or_404(db, equipment_id)
    if result and result not in ("pass", "fail"):
        raise AppException("VALIDATION_ERROR", "result không hợp lệ", 400)

    conditions = [CalibrationRecord.equipment_id == equipment_id]
    if result:
        conditions.append(CalibrationRecord.result == result)

    latest_at = db.execute(
        select(func.max(CalibrationRecord.calibrated_at)).where(
            CalibrationRecord.equipment_id == equipment_id
        )
    ).scalar_one()

    total = db.execute(
        select(func.count()).select_from(CalibrationRecord).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(CalibrationRecord)
        .where(*conditions)
        .order_by(
            CalibrationRecord.calibrated_at.desc(), CalibrationRecord.created_at.desc()
        )
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return [_record_dict(db, r, latest_at=latest_at) for r in rows], total


# ===== #10 GET /calibrations/:id =====
def get_calibration(db: Session, *, calibration_id: uuid.UUID) -> dict:
    rec = db.get(CalibrationRecord, calibration_id)
    if rec is None:
        raise ec.calibration_not_found()
    latest_at = db.execute(
        select(func.max(CalibrationRecord.calibrated_at)).where(
            CalibrationRecord.equipment_id == rec.equipment_id
        )
    ).scalar_one()
    data = _record_dict(db, rec, latest_at=latest_at)
    eq = db.get(Equipment, rec.equipment_id)
    data["equipment"] = {
        "id": eq.id,
        "equipment_code": eq.code,
        "name": eq.name,
        "department_name": ec.dept_name(db, eq.department_id),
    } if eq else None
    return data


# ===== #14 GET /calibrations/:id/cert/download =====
def download_cert(
    db: Session,
    *,
    user: CurrentUser,
    calibration_id: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    rec = db.get(CalibrationRecord, calibration_id)
    if rec is None:
        raise ec.calibration_not_found()
    cert = _cert_attachment(db, rec.id)
    if cert is None:
        raise AppException(
            "CERT_NOT_FOUND", "Bản ghi hiệu chuẩn không có giấy chứng nhận", 404
        )

    from datetime import datetime, timedelta, timezone

    download_url = storage_service.presigned_get_url(
        cert.file_key, file_name=cert.file_name, inline=False
    )
    audit_service.log_action(
        db,
        action="CALIBRATION_DOWNLOAD",
        resource="calibration",
        user_id=user.id,
        resource_id=rec.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"cert_attachment_id": str(cert.id), "file_name": cert.file_name},
    )
    db.commit()
    return {
        "calibration_id": rec.id,
        "cert_attachment_id": cert.id,
        "file_name": cert.file_name,
        "mime": cert.mime,
        "size": cert.size,
        "download_url": download_url,
        "url_expires_at": datetime.now(timezone.utc)
        + timedelta(seconds=settings.presigned_url_ttl_seconds),
    }


# ===== #9 POST /equipments/:id/calibrations (CỐT LÕI) =====
def create_calibration(
    db: Session,
    *,
    user: CurrentUser,
    equipment_id: uuid.UUID,
    calibrated_at: date,
    result: str,
    provider: Optional[str],
    next_due_date_override: Optional[date],
    override_reason: Optional[str],
    note: Optional[str],
    correction_of: Optional[uuid.UUID],
    cert_file_name: Optional[str],
    cert_content: Optional[bytes],
    cert_mime: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    # RBAC + scope (kiểm trước khi mở transaction)
    ec.assert_can_calibrate(db, user)

    # Validate result
    if result not in ("pass", "fail"):
        raise AppException(
            "INVALID_CALIBRATION_RESULT", "Kết quả phải là pass hoặc fail", 422
        )
    # Validate calibrated_at ≤ today (BR-EQP-005)
    if calibrated_at > date.today():
        raise AppException(
            "INVALID_CALIBRATION_DATE",
            "Ngày hiệu chuẩn không được ở tương lai. Hiệu chuẩn là sự kiện đã xảy ra.",
            422,
            [{"field": "calibrated_at", "value": calibrated_at.isoformat()}],
        )
    # CoC bắt buộc khi result=pass (OQ#4 default)
    if result == "pass" and not cert_content:
        raise AppException(
            "CALIBRATION_CERT_REQUIRED",
            "Cần đính kèm giấy chứng nhận (CoC) khi kết quả là 'đạt'",
            400,
        )
    # MIME CoC whitelist (nếu có file)
    if cert_content:
        if cert_mime is None or cert_mime.lower() not in ec.ALLOWED_CERT_MIME:
            raise AppException(
                "INVALID_FILE_TYPE", "CoC chỉ chấp nhận PDF/PNG/JPG", 422
            )
        if len(cert_content) > settings.max_upload_size_bytes:
            raise AppException(
                "FILE_TOO_LARGE",
                f"CoC vượt quá {settings.max_upload_size_bytes // (1024 * 1024)}MB",
                422,
            )
    # Override next_due cần lý do + > calibrated_at
    if next_due_date_override is not None:
        if not override_reason or not override_reason.strip():
            raise AppException(
                "OVERRIDE_REASON_REQUIRED",
                "Cần lý do khi override ngày hiệu chuẩn kế tiếp",
                400,
            )
        if next_due_date_override <= calibrated_at:
            raise AppException(
                "INVALID_DATE_ORDER",
                "Ngày kế tiếp phải sau ngày hiệu chuẩn",
                422,
            )

    # ====== TRANSACTION + ROW-LOCK thiết bị ======
    eq = ec.get_equipment_or_404(db, equipment_id, lock=True)
    ec.assert_write_scope(user, eq.department_id)

    # correction_of (đính chính) phải thuộc cùng thiết bị
    if correction_of is not None:
        prev = db.get(CalibrationRecord, correction_of)
        if prev is None or prev.equipment_id != eq.id:
            raise AppException(
                "CALIBRATION_NOT_FOUND",
                "Bản ghi cần đính chính không thuộc thiết bị này",
                404,
            )

    # Tính next_due
    if next_due_date_override is not None:
        next_due = next_due_date_override
        overridden = True
    else:
        next_due = ec.compute_next_due(
            calibrated_at, eq.calibration_cycle_value, eq.calibration_cycle_unit
        )
        overridden = False
        if next_due is None:
            raise AppException(
                "CALIBRATION_CYCLE_REQUIRED",
                "Thiết bị chưa cấu hình chu kỳ hiệu chuẩn. Hãy cấu hình chu kỳ hoặc "
                "nhập ngày hiệu chuẩn kế tiếp thủ công (next_due_date_override).",
                422,
                [{"field": "calibration_cycle_value", "message": "thiết bị chưa thuộc diện hiệu chuẩn"}],
            )

    # Upload CoC MinIO TRƯỚC (trigger immutable chặn UPDATE sau → set cert_file_key trong INSERT)
    cert_file_key: Optional[str] = None
    cert_att_dict: Optional[dict] = None
    rec_id = uuid.uuid4()
    if cert_content:
        try:
            cert_file_key = storage_service.build_object_key(
                "calibration", rec_id, cert_file_name or "coc"
            )
            storage_service.put_object(cert_file_key, cert_content, content_type=cert_mime)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.error(
                "Calibration cert upload failed — rolled back",
                extra={"correlationId": correlation_id, "error": str(exc)},
            )
            raise AppException(
                "STORAGE_UNAVAILABLE", "Không thể tải CoC lên kho lưu trữ", 503
            )

    rec = CalibrationRecord(
        id=rec_id,
        equipment_id=eq.id,
        calibrated_at=calibrated_at,
        provider=provider,
        result=result,
        next_due_date=next_due,
        cert_file_key=cert_file_key,
        note=note,
        correction_of=correction_of,
        override_reason=override_reason.strip() if override_reason else None,
        next_due_overridden=overridden,
        created_by=user.id,
    )
    db.add(rec)
    db.flush()

    # Gắn attachments cho CoC (owner_type='calibration', owner_id=rec.id) — D10
    if cert_file_key:
        att = Attachment(
            owner_type="calibration",
            owner_id=rec.id,
            file_key=cert_file_key,
            file_name=cert_file_name or "coc",
            mime=cert_mime,
            size=len(cert_content) if cert_content else None,
            uploaded_by=user.id,
        )
        db.add(att)
        db.flush()
        cert_att_dict = {
            "attachment_id": att.id,
            "file_name": att.file_name,
            "mime": att.mime,
            "size": att.size,
        }

    # Cập nhật equipments.next_due_date NẾU lần này là gần nhất (BR-EQP-008)
    latest_at = db.execute(
        select(func.max(CalibrationRecord.calibrated_at)).where(
            CalibrationRecord.equipment_id == eq.id
        )
    ).scalar_one()
    is_latest = latest_at is not None and calibrated_at >= latest_at
    if is_latest:
        eq.next_due_date = next_due
        eq.updated_by = user.id
        eq.updated_at = func.now()
        db.flush()

    audit_service.log_action(
        db,
        action="CALIBRATION_RECORD",
        resource="calibration",
        user_id=user.id,
        resource_id=rec.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={
            "equipment_id": str(eq.id),
            "equipment_code": eq.code,
            "calibrated_at": calibrated_at.isoformat(),
            "result": result,
            "next_due_date": next_due.isoformat(),
            "next_due_overridden": overridden,
            "override_reason": override_reason.strip() if override_reason else None,
            "is_latest": is_latest,
            "correction_of": str(correction_of) if correction_of else None,
        },
    )
    db.commit()
    db.refresh(rec)
    db.refresh(eq)

    badge = ec.compute_badge(eq, last_result=eq_last_result(db, eq.id))
    logger.info(
        "Calibration recorded",
        extra={
            "correlationId": correlation_id,
            "equipmentCode": eq.code,
            "result": result,
            "nextDue": next_due.isoformat(),
            "isLatest": is_latest,
        },
    )
    return {
        "id": rec.id,
        "equipment_id": rec.equipment_id,
        "equipment_code": eq.code,
        "calibrated_at": rec.calibrated_at,
        "provider": rec.provider,
        "result": rec.result,
        "next_due_date": rec.next_due_date,
        "next_due_overridden": rec.next_due_overridden,
        "override_reason": rec.override_reason,
        "is_latest": is_latest,
        "cert": cert_att_dict,
        "note": rec.note,
        "correction_of": rec.correction_of,
        "created_by": rec.created_by,
        "created_by_name": ec.user_name(db, rec.created_by),
        "created_at": rec.created_at,
        "equipment": {
            "id": eq.id,
            "next_due_date": eq.next_due_date,
            "calibration_status": badge["calibration_status"],
            "is_overdue": badge["is_overdue"],
            "warning_label": badge["warning_label"],
        },
    }


def eq_last_result(db: Session, equipment_id: uuid.UUID) -> Optional[str]:
    last = ec.latest_calibration(db, equipment_id)
    return last.result if last else None
