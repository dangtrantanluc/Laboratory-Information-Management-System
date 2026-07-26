"""Service master data CHỈ TIÊU THỬ NGHIỆM (m27) — bảng giá phân tích.

RBAC: Phòng nhận mẫu + Ban lãnh đạo + Quản trị = TOÀN QUYỀN (thêm/sửa/xóa).
Các vai trò khác: CHỈ ĐỌC (để chọn chỉ tiêu khi chuyển mẫu / tham chiếu đơn giá).
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found
from app.models.department import Department
from app.models.sample_flow import MATRIX_LABELS, SampleDispatch, TestParameter
from app.services import audit_service

# Toàn quyền quản lý master data
MANAGE_ROLES = ("reception", "leader", "admin")


def _forbidden(msg: str = "Bạn không có quyền quản lý danh mục chỉ tiêu thử nghiệm") -> AppException:
    return AppException("FORBIDDEN", msg, 403)


def can_manage(user: CurrentUser) -> bool:
    return user.role in MANAGE_ROLES


def _assert_manage(user: CurrentUser) -> None:
    if not can_manage(user):
        raise _forbidden()


def _to_decimal(v) -> Optional[Decimal]:
    if v is None or v == "":
        return None
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        raise AppException("VALIDATION_ERROR", "Đơn giá không hợp lệ", 400)
    if d < 0:
        raise AppException("VALIDATION_ERROR", "Đơn giá không được âm", 400)
    return d


def _serialize(db: Session, p: TestParameter) -> dict:
    dept = db.get(Department, p.department_id) if p.department_id else None
    return {
        "id": p.id,
        "matrix": p.matrix,
        "matrix_label": MATRIX_LABELS.get(p.matrix, p.matrix),
        "sample_matrix": p.sample_matrix,
        "name": p.name,
        "method": p.method,
        "unit": p.unit,
        "unit_price": str(p.unit_price) if p.unit_price is not None else None,
        "currency": p.currency,
        "turnaround_days": p.turnaround_days,
        "in_charge": p.in_charge,
        "note": p.note,
        "department_id": p.department_id,
        "department_name": dept.name if dept else None,
        "is_accredited": p.is_accredited,
        "is_active": p.is_active,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def list_parameters(
    db: Session, *, q: Optional[str], matrix: Optional[str], department_id: Optional[uuid.UUID],
    is_active: Optional[bool], unassigned: bool, page: int, limit: int,
) -> tuple[list[dict], int]:
    """Mọi user đã đăng nhập đều đọc được (dùng để chọn chỉ tiêu khi chuyển mẫu)."""
    conds = []
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(TestParameter.name.ilike(like), TestParameter.method.ilike(like)))
    if matrix:
        conds.append(TestParameter.matrix == matrix)
    if department_id:
        conds.append(TestParameter.department_id == department_id)
    if is_active is not None:
        conds.append(TestParameter.is_active.is_(is_active))
    if unassigned:
        conds.append(TestParameter.department_id.is_(None))

    base = select(TestParameter)
    cq = select(func.count()).select_from(TestParameter)
    for c in conds:
        base = base.where(c)
        cq = cq.where(c)

    total = db.execute(cq).scalar_one()
    rows = db.execute(
        base.order_by(
            TestParameter.matrix,
            TestParameter.sort_order.nulls_last(),
            TestParameter.name,
        ).offset((page - 1) * limit).limit(limit)
    ).scalars().all()
    return [_serialize(db, p) for p in rows], total


def get_parameter(db: Session, *, parameter_id: uuid.UUID) -> dict:
    p = db.get(TestParameter, parameter_id)
    if p is None:
        raise not_found("Không tìm thấy chỉ tiêu thử nghiệm")
    return _serialize(db, p)


_EDITABLE = (
    "matrix", "sample_matrix", "name", "method", "unit", "currency",
    "turnaround_days", "in_charge", "note", "department_id",
    "is_accredited", "is_active", "sort_order",
)


def create_parameter(
    db: Session, *, user: CurrentUser, fields: dict, correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    _assert_manage(user)
    name = (fields.get("name") or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "Tên chỉ tiêu không được để trống", 400)

    p = TestParameter(name=name, created_by=user.id)
    for f in _EDITABLE:
        if f == "name":
            continue
        if f in fields and fields[f] is not None:
            setattr(p, f, fields[f])
    p.unit_price = _to_decimal(fields.get("unit_price"))
    db.add(p)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppException(
            "DUPLICATE_PARAMETER",
            "Chỉ tiêu này đã tồn tại trong cùng nhóm nền mẫu (cùng tên + phương pháp)",
            409,
        )
    audit_service.log_action(
        db, action="TEST_PARAMETER_CREATE", resource="test_parameter", user_id=user.id,
        resource_id=p.id, correlation_id=correlation_id, ip=ip,
        detail={"name": p.name, "matrix": p.matrix},
    )
    db.commit()
    db.refresh(p)
    return _serialize(db, p)


def update_parameter(
    db: Session, *, user: CurrentUser, parameter_id: uuid.UUID, changes: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    _assert_manage(user)
    p = db.get(TestParameter, parameter_id)
    if p is None:
        raise not_found("Không tìm thấy chỉ tiêu thử nghiệm")

    for f in _EDITABLE:
        if f in changes:
            val = changes[f]
            if f == "name":
                val = (val or "").strip()
                if not val:
                    raise AppException("VALIDATION_ERROR", "Tên chỉ tiêu không được để trống", 400)
            setattr(p, f, val)
    if "unit_price" in changes:
        p.unit_price = _to_decimal(changes["unit_price"])
    p.updated_by = user.id
    p.updated_at = datetime.now(timezone.utc)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppException(
            "DUPLICATE_PARAMETER",
            "Chỉ tiêu này đã tồn tại trong cùng nhóm nền mẫu (cùng tên + phương pháp)",
            409,
        )
    audit_service.log_action(
        db, action="TEST_PARAMETER_UPDATE", resource="test_parameter", user_id=user.id,
        resource_id=p.id, correlation_id=correlation_id, ip=ip,
        detail={"changed": sorted(set(changes.keys()))},
    )
    db.commit()
    db.refresh(p)
    return _serialize(db, p)


def delete_parameter(
    db: Session, *, user: CurrentUser, parameter_id: uuid.UUID,
    correlation_id: Optional[str], ip: Optional[str],
) -> None:
    """Xóa chỉ tiêu. Nếu đã dùng trong phiếu chuyển mẫu → chỉ NGƯNG dùng (is_active=false)
    để không phá dữ liệu lịch sử."""
    _assert_manage(user)
    p = db.get(TestParameter, parameter_id)
    if p is None:
        raise not_found("Không tìm thấy chỉ tiêu thử nghiệm")

    used = db.execute(
        select(func.count()).select_from(SampleDispatch).where(
            SampleDispatch.test_parameter_id == parameter_id
        )
    ).scalar_one()
    if used:
        p.is_active = False
        p.updated_by = user.id
        p.updated_at = datetime.now(timezone.utc)
        action = "TEST_PARAMETER_DEACTIVATE"
    else:
        db.delete(p)
        action = "TEST_PARAMETER_DELETE"

    audit_service.log_action(
        db, action=action, resource="test_parameter", user_id=user.id,
        resource_id=parameter_id, correlation_id=correlation_id, ip=ip,
        detail={"name": p.name, "used_in_dispatches": int(used)},
    )
    db.commit()


def matrix_options() -> list[dict]:
    return [{"value": k, "label": v} for k, v in MATRIX_LABELS.items()]
