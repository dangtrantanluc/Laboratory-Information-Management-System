"""M5 equipment service — CRUD thiết bị + tìm/lọc + chi tiết + cảnh báo (calibration-due)
+ đính kèm tài liệu thiết bị (FR-EQP-001..005, 010).

RBAC: đọc toàn lab (staff/leader/accountant 👁); ghi theo phòng (staff phòng mình; admin
all; leader/accountant cấm — equipment_common). Mã equipment_code sinh server-side
(BR-EQP-014, không lộ tuần tự). Badge cảnh báo tính runtime, KHÔNG khóa cứng (OQ#3).
Soft-delete qua deleted_at; thiết bị có hồ sơ hiệu chuẩn KHÔNG hard-delete (§8.4).
"""
import logging
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException, validation_error
from app.models.attachment import Attachment
from app.models.department import Department
from app.models.equipment import CalibrationRecord, Equipment
from app.services import audit_service, attachment_service
from app.services import equipment_common as ec

logger = logging.getLogger("lims.equipment")

_VALID_STATUS = ("active", "maintenance", "broken", "retired")
_VALID_CAL_STATUS = (
    "ok", "due_soon", "overdue", "failed", "never_calibrated", "not_applicable",
)


# ===== Serialize =====
def _equipment_badge(db: Session, eq: Equipment, *, as_of: Optional[date] = None) -> dict:
    last = ec.latest_calibration(db, eq.id)
    return ec.compute_badge(eq, last_result=last.result if last else None, as_of=as_of)


def _equipment_summary(db: Session, eq: Equipment) -> dict:
    last = ec.latest_calibration(db, eq.id)
    badge = ec.compute_badge(eq, last_result=last.result if last else None)
    return {
        "id": eq.id,
        "equipment_code": eq.code,
        "name": eq.name,
        "location": eq.location,
        "department_id": eq.department_id,
        "department_name": ec.dept_name(db, eq.department_id),
        "responsible_user_id": eq.responsible_user_id,
        "responsible_user_name": ec.user_name(db, eq.responsible_user_id),
        "purchase_date": eq.purchase_date,
        "status": eq.status,
        "calibration_cycle_value": eq.calibration_cycle_value,
        "calibration_cycle_unit": eq.calibration_cycle_unit,
        "next_due_date": eq.next_due_date,
        "last_calibrated_at": last.calibrated_at if last else None,
        "last_calibration_result": last.result if last else None,
        "created_at": eq.created_at,
        **badge,
    }


def _equipment_detail(db: Session, eq: Equipment) -> dict:
    last = ec.latest_calibration(db, eq.id)
    badge = ec.compute_badge(eq, last_result=last.result if last else None)
    last_block = None
    if last is not None:
        cert_att = _latest_cert_attachment(db, last.id)
        last_block = {
            "id": last.id,
            "calibrated_at": last.calibrated_at,
            "provider": last.provider,
            "result": last.result,
            "next_due_date": last.next_due_date,
            "cert_attachment_id": cert_att.id if cert_att else None,
        }
    atts = db.execute(
        select(Attachment)
        .where(
            Attachment.owner_type == "equipment",
            Attachment.owner_id == eq.id,
            Attachment.deleted_at.is_(None),
        )
        .order_by(Attachment.uploaded_at.desc())
    ).scalars().all()
    return {
        "id": eq.id,
        "equipment_code": eq.code,
        "name": eq.name,
        "location": eq.location,
        "department_id": eq.department_id,
        "department_name": ec.dept_name(db, eq.department_id),
        "responsible_user_id": eq.responsible_user_id,
        "responsible_user_name": ec.user_name(db, eq.responsible_user_id),
        "purchase_date": eq.purchase_date,
        "status": eq.status,
        "calibration_cycle_value": eq.calibration_cycle_value,
        "calibration_cycle_unit": eq.calibration_cycle_unit,
        "next_due_date": eq.next_due_date,
        **badge,
        "last_calibration": last_block,
        "calibration_count": ec.calibration_count(db, eq.id),
        "attachments": [
            {
                "attachment_id": a.id,
                "file_name": a.file_name,
                "mime": a.mime,
                "size": a.size,
                "uploaded_by_name": ec.user_name(db, a.uploaded_by),
                "uploaded_at": a.uploaded_at,
            }
            for a in atts
        ],
        "created_by_name": ec.user_name(db, eq.created_by),
        "created_at": eq.created_at,
        "updated_at": eq.updated_at,
    }


def _latest_cert_attachment(db: Session, calibration_id: uuid.UUID) -> Optional[Attachment]:
    return db.execute(
        select(Attachment)
        .where(
            Attachment.owner_type == "calibration",
            Attachment.owner_id == calibration_id,
            Attachment.deleted_at.is_(None),
        )
        .order_by(Attachment.uploaded_at.desc())
    ).scalars().first()


# ===== #1 GET /equipments =====
def list_equipments(
    db: Session,
    *,
    q: Optional[str],
    status_filter: Optional[str],
    department_id: Optional[uuid.UUID],
    responsible_user_id: Optional[uuid.UUID],
    calibration_status: Optional[str],
    overdue: Optional[bool],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    if status_filter and status_filter not in _VALID_STATUS:
        raise validation_error("status không hợp lệ")
    if calibration_status and calibration_status not in _VALID_CAL_STATUS:
        raise validation_error("calibration_status không hợp lệ")

    conditions = [Equipment.deleted_at.is_(None)]
    if q:
        like = f"%{q}%"
        conditions.append(or_(Equipment.code.ilike(like), Equipment.name.ilike(like)))
    if status_filter:
        conditions.append(Equipment.status == status_filter)
    if department_id is not None:
        conditions.append(Equipment.department_id == department_id)
    if responsible_user_id is not None:
        conditions.append(Equipment.responsible_user_id == responsible_user_id)

    # Lọc badge (overdue / calibration_status) cần tính runtime → lấy rộng rồi lọc Python.
    # Quy mô ~2,000 thiết bị (NFR §647) → chấp nhận; nếu filter badge thì bỏ phân trang SQL.
    badge_filter = overdue or calibration_status
    if badge_filter:
        rows = db.execute(
            select(Equipment).where(*conditions).order_by(Equipment.created_at.desc())
        ).scalars().all()
        items_all = [_equipment_summary(db, eq) for eq in rows]
        if overdue:
            items_all = [i for i in items_all if i["is_overdue"]]
        if calibration_status:
            items_all = [
                i for i in items_all if i["calibration_status"] == calibration_status
            ]
        total = len(items_all)
        start = (page - 1) * limit
        return items_all[start : start + limit], total

    total = db.execute(
        select(func.count()).select_from(Equipment).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(Equipment)
        .where(*conditions)
        .order_by(Equipment.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return [_equipment_summary(db, eq) for eq in rows], total


# ===== #2 GET /equipments/calibration-due =====
def list_calibration_due(
    db: Session,
    *,
    within_days: int,
    department_id: Optional[uuid.UUID],
    bucket: str,
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    if within_days < 1 or within_days > 365:
        raise validation_error("within_days phải trong khoảng 1..365")
    if bucket not in ("overdue", "due_soon", "failed", "all"):
        raise validation_error("bucket không hợp lệ")

    # Chỉ thiết bị diện hiệu chuẩn + chưa retired (BR-EQP-010).
    conditions = [
        Equipment.deleted_at.is_(None),
        Equipment.calibration_cycle_value.is_not(None),
        Equipment.status != "retired",
    ]
    if department_id is not None:
        conditions.append(Equipment.department_id == department_id)

    rows = db.execute(select(Equipment).where(*conditions)).scalars().all()

    today = date.today()
    out: list[dict] = []
    for eq in rows:
        last = ec.latest_calibration(db, eq.id)
        badge = ec.compute_badge(eq, last_result=last.result if last else None)
        cs = badge["calibration_status"]
        days = badge["days_to_due"]
        is_failed = cs == "failed"
        # within_days áp cho overdue/due_soon (gồm quá hạn). failed không phụ thuộc next_due.
        in_window = days is not None and days <= within_days
        keep = False
        if bucket == "all":
            keep = is_failed or (cs in ("overdue", "due_soon") and in_window)
        elif bucket == "overdue":
            keep = cs == "overdue"
        elif bucket == "due_soon":
            keep = cs == "due_soon" and in_window
        elif bucket == "failed":
            keep = is_failed
        if not keep:
            continue
        out.append(
            {
                "id": eq.id,
                "equipment_code": eq.code,
                "name": eq.name,
                "department_id": eq.department_id,
                "department_name": ec.dept_name(db, eq.department_id),
                "responsible_user_name": ec.user_name(db, eq.responsible_user_id),
                "next_due_date": eq.next_due_date,
                **badge,
            }
        )

    # Sắp xếp: overdue (days tăng dần — quá hạn lâu nhất trước) → failed → due_soon
    def _sort_key(item: dict):
        cs = item["calibration_status"]
        order = {"overdue": 0, "failed": 1, "due_soon": 2}.get(cs, 3)
        days = item["days_to_due"]
        return (order, days if days is not None else 999999)

    out.sort(key=_sort_key)
    total = len(out)
    start = (page - 1) * limit
    return out[start : start + limit], total


# ===== #3 GET /equipments/:id =====
def get_equipment_detail(db: Session, *, equipment_id: uuid.UUID) -> dict:
    eq = ec.get_equipment_or_404(db, equipment_id)
    return _equipment_detail(db, eq)


# ===== #4 POST /equipments =====
def create_equipment(
    db: Session,
    *,
    user: CurrentUser,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    ec.assert_can_create(db, user)

    dept_id = ec.resolve_write_department(user, payload.get("department_id"))
    ec.assert_write_scope(user, dept_id)
    dept = db.get(Department, dept_id)
    if dept is None:
        raise AppException("DEPARTMENT_NOT_FOUND", "Phòng ban không tồn tại", 404)

    cycle_value = payload.get("calibration_cycle_value")
    cycle_unit = payload.get("calibration_cycle_unit")
    ec.validate_cycle_pair(cycle_value, cycle_unit)

    purchase_date = payload.get("purchase_date")
    if purchase_date and purchase_date > date.today():
        raise validation_error("Ngày mua không được ở tương lai")

    ec.validate_responsible(db, payload.get("responsible_user_id"), dept_id)

    status_val = payload.get("status") or "active"

    # Sinh code + retry nếu trùng UNIQUE (FR-EQP-003 A1)
    last_exc: Optional[Exception] = None
    for _ in range(5):
        code = ec.next_equipment_code(db, dept=dept)
        eq = Equipment(
            code=code,
            name=payload["name"],
            location=payload.get("location"),
            department_id=dept_id,
            responsible_user_id=payload.get("responsible_user_id"),
            purchase_date=purchase_date,
            status=status_val,
            calibration_cycle_value=cycle_value,
            calibration_cycle_unit=cycle_unit,
            next_due_date=None,
            note=payload.get("note"),
            created_by=user.id,
        )
        db.add(eq)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            last_exc = None
            eq = None  # type: ignore
    else:
        logger.warning("Cannot generate unique equipment_code after retries")
        raise AppException(
            "DUPLICATE_EQUIPMENT_CODE", "Không thể sinh mã thiết bị duy nhất", 409
        )

    audit_service.log_action(
        db,
        action="EQUIPMENT_CREATE",
        resource="equipment",
        user_id=user.id,
        resource_id=eq.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"code": eq.code, "name": eq.name, "department_id": str(dept_id)},
    )
    db.commit()
    db.refresh(eq)
    logger.info(
        "Equipment created", extra={"correlationId": correlation_id, "code": eq.code}
    )
    return _equipment_detail(db, eq)


# ===== #5 PATCH /equipments/:id =====
def update_equipment(
    db: Session,
    *,
    user: CurrentUser,
    equipment_id: uuid.UUID,
    raw_body: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    ec.assert_can_update(db, user)

    # Chặn đổi code/department_id (bất biến / chỉ admin) — kiểm tra raw body
    if "code" in raw_body or "equipment_code" in raw_body:
        raise AppException(
            "CODE_IMMUTABLE", "Không thể đổi mã thiết bị (bất biến §6.4)", 422
        )
    if "department_id" in raw_body and not ec.is_privileged(user):
        raise ec.forbidden("Không được đổi phòng ban thiết bị")

    eq = ec.get_equipment_or_404(db, equipment_id, lock=True)
    ec.assert_write_scope(user, eq.department_id)

    before: dict = {}
    after: dict = {}

    if "name" in raw_body and raw_body["name"] is not None:
        before["name"], after["name"] = eq.name, raw_body["name"]
        eq.name = raw_body["name"]
    if "location" in raw_body:
        before["location"], after["location"] = eq.location, raw_body["location"]
        eq.location = raw_body["location"]
    if "purchase_date" in raw_body:
        pd = raw_body["purchase_date"]
        if pd and pd > date.today():
            raise validation_error("Ngày mua không được ở tương lai")
        before["purchase_date"] = str(eq.purchase_date) if eq.purchase_date else None
        after["purchase_date"] = str(pd) if pd else None
        eq.purchase_date = pd
    if "status" in raw_body and raw_body["status"] is not None:
        if raw_body["status"] not in _VALID_STATUS:
            raise AppException("INVALID_STATUS", "Tình trạng không hợp lệ", 422)
        before["status"], after["status"] = eq.status, raw_body["status"]
        eq.status = raw_body["status"]
    if "responsible_user_id" in raw_body:
        ru = raw_body["responsible_user_id"]
        ec.validate_responsible(db, ru, eq.department_id)
        before["responsible_user_id"] = (
            str(eq.responsible_user_id) if eq.responsible_user_id else None
        )
        after["responsible_user_id"] = str(ru) if ru else None
        eq.responsible_user_id = ru

    # Chu kỳ — đổi KHÔNG hồi tố next_due hiện tại (BR-EQP-006); chỉ áp lần TIẾP THEO
    cycle_touched = (
        "calibration_cycle_value" in raw_body or "calibration_cycle_unit" in raw_body
    )
    if cycle_touched:
        new_value = raw_body.get("calibration_cycle_value", eq.calibration_cycle_value)
        new_unit = raw_body.get("calibration_cycle_unit", eq.calibration_cycle_unit)
        ec.validate_cycle_pair(new_value, new_unit)
        before["calibration_cycle"] = f"{eq.calibration_cycle_value} {eq.calibration_cycle_unit}"
        after["calibration_cycle"] = f"{new_value} {new_unit}"
        eq.calibration_cycle_value = new_value
        eq.calibration_cycle_unit = new_unit

    if not after:
        raise validation_error("Không có trường nào để cập nhật")

    eq.updated_by = user.id
    eq.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="EQUIPMENT_UPDATE",
        resource="equipment",
        user_id=user.id,
        resource_id=eq.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"before": before, "after": after},
    )
    db.commit()
    db.refresh(eq)
    return _equipment_detail(db, eq)


# ===== #6 POST /equipments/:id/attachments =====
def add_attachment(
    db: Session,
    *,
    user: CurrentUser,
    equipment_id: uuid.UUID,
    file_name: str,
    content: bytes,
    mime: Optional[str],
    doc_type: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    ec.assert_can_create(db, user)
    eq = ec.get_equipment_or_404(db, equipment_id)
    ec.assert_write_scope(user, eq.department_id)

    if mime is None or mime.lower() not in ec.ALLOWED_DOC_MIME:
        raise AppException(
            "INVALID_FILE_TYPE",
            "Định dạng tệp không hợp lệ (chỉ PDF/DOCX/XLSX/PNG/JPG)",
            422,
        )

    data = attachment_service.create_attachment(
        db,
        user=user,
        owner_type="equipment",
        owner_id=equipment_id,
        file_name=file_name,
        content=content,
        mime=mime,
        correlation_id=correlation_id,
        ip=ip,
    )
    return {
        "attachment_id": data["id"],
        "owner_type": data["owner_type"],
        "owner_id": data["owner_id"],
        "file_name": data["file_name"],
        "mime": data["mime"],
        "size": data["size"],
        "doc_type": doc_type or "other",
        "uploaded_by": user.id,
        "uploaded_at": data["uploaded_at"],
    }


# ===== #7 GET /equipments/:id/attachments/:attId/download =====
def download_attachment(
    db: Session,
    *,
    user: CurrentUser,
    equipment_id: uuid.UUID,
    attachment_id: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    eq = ec.get_equipment_or_404(db, equipment_id)
    att = db.execute(
        select(Attachment).where(
            Attachment.id == attachment_id,
            Attachment.owner_type == "equipment",
            Attachment.owner_id == eq.id,
            Attachment.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if att is None:
        raise AppException(
            "ATTACHMENT_NOT_FOUND", "Tài liệu không thuộc thiết bị này", 404
        )
    return attachment_service.get_download(
        db,
        user=user,
        attachment_id=att.id,
        inline=False,
        correlation_id=correlation_id,
        ip=ip,
    )
