"""M5 common helpers — RBAC scope, sinh mã thiết bị, tính next_due (relativedelta năm
nhuận), badge cảnh báo runtime, người phụ trách cùng phòng, error factories, MIME whitelist.

Tập trung logic dùng chung mọi service M5 để khớp contract (18-contract-m5-api.md):
- RBAC: đọc roles_permissions M5 (leader=👁 / accountant=read / staff=read all + ghi
  phòng mình / admin=full). Endpoint ghi → has_permission(equipment:create/update,
  calibration:create); scope phòng (staff chỉ phòng mình — BR-EQP-003).
- Badge cảnh báo (FR-EQP-010, BR-EQP-009/010): runtime từ next_due_date vs today +
  result lần gần nhất; KHÔNG khóa cứng (OQ#3, CONSTRAINT-3).
- next_due = calibrated_at + chu kỳ (relativedelta — an toàn năm nhuận 29/02→28/02, D7).
- Sinh equipment_code <TB>-<mã phòng>-<seq> idempotent + UNIQUE chống trùng (BR-EQP-014).
- Người phụ trách phải cùng phòng thiết bị (BR-EQP-013, 422 RESPONSIBLE_NOT_IN_DEPARTMENT).
"""
import re
import uuid
from datetime import date
from typing import Optional

from dateutil.relativedelta import relativedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.core.rbac import has_permission
from app.models.department import Department
from app.models.equipment import CalibrationRecord, Equipment
from app.models.user import User

_CODE_PREFIX = "TB"
_DUE_SOON_DAYS = 30  # badge due_soon: còn ≤ 30 ngày (FR-EQP-010)
_CRON_MILESTONES = (30, 15, 7)

# Whitelist MIME tài liệu thiết bị (BR-EQP-012): PDF/DOCX/XLSX/PNG/JPG
ALLOWED_DOC_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword",
    "application/vnd.ms-excel",
    "image/png",
    "image/jpeg",
    "image/jpg",
}
# Whitelist MIME CoC/cert (BR-EQP-012): PDF/PNG/JPG
ALLOWED_CERT_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
}


# ===== Error factories (đồng bộ danh mục error code §3 contract) =====
def err(code: str, message: str, http: int = 400, details=None) -> AppException:
    return AppException(code, message, http, details)


def forbidden(message: str = "Bạn không có quyền thực hiện thao tác này") -> AppException:
    return AppException("FORBIDDEN", message, 403)


def equipment_not_found() -> AppException:
    return AppException("EQUIPMENT_NOT_FOUND", "Không tìm thấy thiết bị", 404)


def calibration_not_found() -> AppException:
    return AppException(
        "CALIBRATION_NOT_FOUND", "Không tìm thấy bản ghi hiệu chuẩn", 404
    )


# ===== RBAC =====
def is_privileged(user: CurrentUser) -> bool:
    """Admin = toàn hệ thống. (leader ở M5 CHỈ XEM — KHÁC M3 — nên KHÔNG privileged ghi.)"""
    return user.role == "admin"


def assert_can_create(db: Session, user: CurrentUser) -> None:
    """Quyền tạo thiết bị — equipment:create (admin all; staff dept). leader/accountant KHÔNG."""
    if not has_permission(db, user.role, "equipment", "create"):
        raise forbidden("Vai trò của bạn không được tạo thiết bị")


def assert_can_update(db: Session, user: CurrentUser) -> None:
    """Quyền sửa thiết bị — equipment:update (admin all; staff dept). leader/accountant KHÔNG."""
    if not has_permission(db, user.role, "equipment", "update"):
        raise forbidden("Vai trò của bạn không được sửa thiết bị")


def assert_can_calibrate(db: Session, user: CurrentUser) -> None:
    """Quyền ghi hiệu chuẩn — calibration:create (admin all; staff dept). leader/accountant KHÔNG."""
    if not has_permission(db, user.role, "calibration", "create"):
        raise forbidden("Vai trò của bạn không được ghi hiệu chuẩn")


def assert_write_scope(user: CurrentUser, dept_id: uuid.UUID) -> None:
    """Phạm vi ghi theo phòng (BR-EQP-003): staff chỉ ghi trong phòng mình; admin = all."""
    if is_privileged(user):
        return
    if user.department_id is None or user.department_id != dept_id:
        raise forbidden("Bạn chỉ được thao tác thiết bị trong phạm vi phòng của mình")


def resolve_write_department(user: CurrentUser, requested: Optional[uuid.UUID]) -> uuid.UUID:
    """Phòng để tạo thiết bị: staff ép phòng mình; admin theo yêu cầu (mặc định phòng mình)."""
    if is_privileged(user):
        if requested is not None:
            return requested
        if user.department_id is not None:
            return user.department_id
        raise err("VALIDATION_ERROR", "Cần chỉ định department_id", 400)
    if user.department_id is None:
        raise forbidden("Người dùng chưa thuộc phòng ban nào")
    if requested is not None and requested != user.department_id:
        raise forbidden("Bạn chỉ được tạo thiết bị cho phòng của mình")
    return user.department_id


# ===== Helpers tra cứu (response shape contract) =====
def user_name(db: Session, user_id: Optional[uuid.UUID]) -> Optional[str]:
    if user_id is None:
        return None
    u = db.get(User, user_id)
    return u.full_name if u else None


def dept_name(db: Session, dept_id: Optional[uuid.UUID]) -> Optional[str]:
    if dept_id is None:
        return None
    d = db.get(Department, dept_id)
    return d.name if d else None


# ===== Get-or-404 với row-lock =====
def get_equipment_or_404(
    db: Session, equipment_id: uuid.UUID, *, lock: bool = False
) -> Equipment:
    stmt = select(Equipment).where(
        Equipment.id == equipment_id, Equipment.deleted_at.is_(None)
    )
    if lock:
        stmt = stmt.with_for_update()
    eq = db.execute(stmt).scalar_one_or_none()
    if eq is None:
        raise equipment_not_found()
    return eq


# ===== Validate người phụ trách cùng phòng (BR-EQP-013) =====
def validate_responsible(
    db: Session, responsible_user_id: Optional[uuid.UUID], dept_id: uuid.UUID
) -> None:
    if responsible_user_id is None:
        return
    u = db.get(User, responsible_user_id)
    if u is None:
        raise AppException("USER_NOT_FOUND", "Người phụ trách không tồn tại", 404)
    if u.department_id != dept_id:
        raise AppException(
            "RESPONSIBLE_NOT_IN_DEPARTMENT",
            "Người phụ trách phải thuộc cùng phòng với thiết bị",
            422,
            [{"field": "responsible_user_id", "message": "Khác phòng với thiết bị"}],
        )


# ===== Validate chu kỳ value/unit đi cùng nhau (BR-EQP-004) =====
def validate_cycle_pair(value: Optional[int], unit: Optional[str]) -> None:
    if (value is None) != (unit is None):
        raise AppException(
            "INVALID_CALIBRATION_CYCLE",
            "Chu kỳ hiệu chuẩn cần đủ cả giá trị và đơn vị (hoặc bỏ trống cả hai)",
            422,
            [{"field": "calibration_cycle_value", "message": "value & unit phải đi cùng nhau"}],
        )
    if value is not None and value <= 0:
        raise AppException(
            "INVALID_CALIBRATION_CYCLE",
            "Giá trị chu kỳ phải > 0",
            422,
            [{"field": "calibration_cycle_value", "message": "phải > 0"}],
        )


# ===== Tính next_due = calibrated_at + chu kỳ (relativedelta — an toàn năm nhuận, D7) =====
def compute_next_due(
    calibrated_at: date, cycle_value: Optional[int], cycle_unit: Optional[str]
) -> Optional[date]:
    """next_due = calibrated_at + (value tháng | value năm). relativedelta xử lý
    cộng-tháng/năm an toàn năm nhuận (29/02 + 1 năm → 28/02). None nếu chưa cấu hình chu kỳ."""
    if cycle_value is None or cycle_unit is None:
        return None
    if cycle_unit == "month":
        return calibrated_at + relativedelta(months=cycle_value)
    if cycle_unit == "year":
        return calibrated_at + relativedelta(years=cycle_value)
    return None


# ===== Sinh equipment_code <TB>-<mã phòng>-<seq> (BR-EQP-014) =====
def _short_dept_code(dept: Department) -> str:
    parts = [p for p in re.split(r"[-_\s]+", dept.code.upper()) if p]
    return parts[-1] if parts else dept.code.upper()


def next_equipment_code(db: Session, *, dept: Department) -> str:
    """Sinh TB-<mã phòng>-<NNN>. UNIQUE uq_equip_code là lưới chống trùng;
    caller retry khi IntegrityError (FR-EQP-003 A1)."""
    dept_part = _short_dept_code(dept)
    like = f"{_CODE_PREFIX}-{dept_part}-%"
    count = db.execute(
        select(func.count()).select_from(Equipment).where(Equipment.code.like(like))
    ).scalar_one()
    seq = count + 1
    return f"{_CODE_PREFIX}-{dept_part}-{seq:03d}"


# ===== Lần hiệu chuẩn gần nhất (BR-EQP-008) =====
def latest_calibration(
    db: Session, equipment_id: uuid.UUID
) -> Optional[CalibrationRecord]:
    return db.execute(
        select(CalibrationRecord)
        .where(CalibrationRecord.equipment_id == equipment_id)
        .order_by(CalibrationRecord.calibrated_at.desc(), CalibrationRecord.created_at.desc())
    ).scalars().first()


def calibration_count(db: Session, equipment_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count())
        .select_from(CalibrationRecord)
        .where(CalibrationRecord.equipment_id == equipment_id)
    ).scalar_one()


# ===== Badge cảnh báo runtime (FR-EQP-010, BR-EQP-009/010) — KHÔNG khóa cứng =====
def compute_badge(
    eq: Equipment,
    *,
    last_result: Optional[str],
    as_of: Optional[date] = None,
) -> dict:
    """Tính trạng thái cảnh báo runtime từ next_due_date so với today + result lần gần nhất.

    Ưu tiên hiển thị: failed ≥ overdue ≥ due_soon ≥ ok (FR-EQP-010 §0.7).
    Thiết bị retired / chu kỳ NULL → not_applicable (không sinh overdue/due_soon).
    """
    today = as_of or date.today()
    applicable = (
        eq.calibration_cycle_value is not None and eq.status != "retired"
    )

    days_to_due: Optional[int] = None
    is_overdue = False
    status_badge = "not_applicable"
    label: Optional[str] = None

    if not applicable:
        # Thiết bị không diện hiệu chuẩn / đã ngưng dùng: badge failed chỉ khi result fail
        if last_result == "fail":
            status_badge = "failed"
            label = "Hiệu chuẩn KHÔNG ĐẠT — khuyến nghị không sử dụng"
        return {
            "calibration_status": status_badge,
            "is_overdue": False,
            "days_to_due": None,
            "warning_label": label,
        }

    if eq.next_due_date is None:
        # Diện hiệu chuẩn nhưng chưa có lần nào
        status_badge = "never_calibrated"
        if last_result == "fail":
            status_badge = "failed"
            label = "Hiệu chuẩn KHÔNG ĐẠT — khuyến nghị không sử dụng"
        return {
            "calibration_status": status_badge,
            "is_overdue": False,
            "days_to_due": None,
            "warning_label": label,
        }

    days_to_due = (eq.next_due_date - today).days
    is_overdue = days_to_due < 0

    # Tính badge cơ bản theo ngày
    if is_overdue:
        status_badge = "overdue"
        label = "Quá hạn hiệu chuẩn — khuyến nghị không sử dụng"
    elif days_to_due <= _DUE_SOON_DAYS:
        status_badge = "due_soon"
        label = f"Sắp tới hạn hiệu chuẩn (còn {days_to_due} ngày)"
    else:
        status_badge = "ok"
        label = None

    # Ưu tiên failed (lần gần nhất fail) — ghép cảnh báo nếu cũng overdue
    if last_result == "fail":
        fail_label = "Hiệu chuẩn KHÔNG ĐẠT — khuyến nghị không sử dụng"
        if status_badge == "overdue":
            label = f"{fail_label}; {label}"
        else:
            label = fail_label
        status_badge = "failed"

    return {
        "calibration_status": status_badge,
        "is_overdue": is_overdue,
        "days_to_due": days_to_due,
        "warning_label": label,
    }
