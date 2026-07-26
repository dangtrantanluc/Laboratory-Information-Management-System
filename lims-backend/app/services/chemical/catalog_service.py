"""Danh mục hoá chất + đơn vị đo — list/search/create/update/deactivate.

Tách từ chemical_service.py (850 dòng) — M-03/T1.2.
"""
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.chemical import (
    Chemical,
    Unit,
)
from app.services import audit_service, chemical_common as cc

logger_action_prefix = "CHEMICAL"


from app.services.chemical._shared import _lot_count, _total_stock_base


def list_units(db: Session, *, group: Optional[str]) -> list[dict]:
    stmt = select(Unit)
    if group:
        stmt = stmt.where(Unit.measurement_group == group)
    stmt = stmt.order_by(Unit.measurement_group, Unit.factor_to_base)
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "code": u.code,
            "group": u.measurement_group,
            "factor_to_base": f"{u.factor_to_base.normalize():f}",
            "label": u.label,
        }
        for u in rows
    ]

def list_chemicals(
    db: Session,
    *,
    q: Optional[str],
    department_id: Optional[uuid.UUID],
    status_filter: Optional[str],
    measurement_group: Optional[str],
    has_stock: Optional[bool],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    if q:
        like = f"%{q}%"
        conditions.append((Chemical.name.ilike(like)) | (Chemical.cas_no.ilike(like)))
    if department_id:
        conditions.append(Chemical.department_id == department_id)
    if status_filter:
        conditions.append(Chemical.status == status_filter)
    else:
        conditions.append(Chemical.status == "active")
    if measurement_group:
        conditions.append(Chemical.measurement_group == measurement_group)

    total = db.execute(
        select(func.count()).select_from(Chemical).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(Chemical)
        .where(*conditions)
        .order_by(Chemical.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()

    items = []
    for c in rows:
        total_stock = _total_stock_base(db, c.id)
        if has_stock and total_stock <= 0:
            continue
        items.append(
            {
                "id": c.id,
                "name": c.name,
                "cas_no": c.cas_no,
                "manufacturer": c.manufacturer,
                "base_unit": c.base_unit,
                "measurement_group": c.measurement_group,
                "hazard_code": c.hazard_code,
                "department_id": c.department_id,
                "department_name": cc.dept_name(db, c.department_id),
                "reorder_threshold": cc.s_base(c.reorder_threshold),
                "total_stock_base": cc.s_base(total_stock),
                "status": c.status,
                "lot_count": _lot_count(db, c.id),
                "created_at": c.created_at,
            }
        )
    # has_stock lọc post-aggregation: total đã tính theo điều kiện gốc; nếu lọc thì total xấp xỉ
    if has_stock:
        total = len(items)
    return items, total


def create_chemical(
    db: Session,
    *,
    user: CurrentUser,
    name: str,
    cas_no: Optional[str],
    manufacturer: Optional[str],
    base_unit: str,
    hazard_code: Optional[str],
    department_id: Optional[uuid.UUID],
    reorder_threshold: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    cc.assert_can_create(db, user)
    dept_id = cc.resolve_write_department(user, department_id)
    cc.assert_write_scope(user, dept_id)

    cas = cc.validate_cas(cas_no)
    unit = cc.get_unit(db, base_unit)  # INVALID_UNIT nếu không tồn tại
    threshold = cc.parse_decimal(reorder_threshold, field="reorder_threshold")
    if threshold is not None:
        cc.assert_max_decimals(threshold, field="reorder_threshold", places=6)
        threshold = cc.q_base(threshold)

    chem = Chemical(
        name=name.strip(),
        cas_no=cas,
        manufacturer=manufacturer.strip() if manufacturer else None,
        base_unit=base_unit,
        measurement_group=unit.measurement_group,  # server suy ra, không nhận client
        hazard_code=hazard_code.strip() if hazard_code else None,
        reorder_threshold=threshold,
        department_id=dept_id,
        status="active",
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(chem)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppException(
            "DUPLICATE_CHEMICAL",
            "Hóa chất (tên + CAS) đã tồn tại trong phòng ban này",
            409,
        )

    audit_service.log_action(
        db,
        action="CHEMICAL_CREATE",
        resource="chemical",
        user_id=user.id,
        resource_id=chem.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"name": chem.name, "cas_no": chem.cas_no, "base_unit": base_unit},
    )
    db.commit()
    db.refresh(chem)
    return _chemical_brief(db, chem)


def _chemical_brief(db: Session, chem: Chemical) -> dict:
    return {
        "id": chem.id,
        "name": chem.name,
        "cas_no": chem.cas_no,
        "manufacturer": chem.manufacturer,
        "base_unit": chem.base_unit,
        "measurement_group": chem.measurement_group,
        "hazard_code": chem.hazard_code,
        "department_id": chem.department_id,
        "reorder_threshold": cc.s_base(chem.reorder_threshold),
        "status": chem.status,
        "created_at": chem.created_at,
    }


def get_chemical_detail(db: Session, chemical_id: uuid.UUID) -> dict:
    chem = cc.get_chemical_or_404(db, chemical_id)
    from app.models.attachment import Attachment

    atts = db.execute(
        select(Attachment).where(
            Attachment.owner_type == "chemical",
            Attachment.owner_id == chem.id,
            Attachment.deleted_at.is_(None),
        )
    ).scalars().all()
    return {
        "id": chem.id,
        "name": chem.name,
        "cas_no": chem.cas_no,
        "manufacturer": chem.manufacturer,
        "base_unit": chem.base_unit,
        "measurement_group": chem.measurement_group,
        "hazard_code": chem.hazard_code,
        "department_id": chem.department_id,
        "department_name": cc.dept_name(db, chem.department_id),
        "reorder_threshold": cc.s_base(chem.reorder_threshold),
        "total_stock_base": cc.s_base(_total_stock_base(db, chem.id)),
        "status": chem.status,
        "attachments": [
            {
                "id": a.id,
                "file_name": a.file_name,
                "mime": a.mime,
                "size": a.size,
                "uploaded_at": a.uploaded_at,
            }
            for a in atts
        ],
        "created_at": chem.created_at,
    }


def update_chemical(
    db: Session,
    *,
    user: CurrentUser,
    chemical_id: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    chem = cc.get_chemical_or_404(db, chemical_id)
    cc.assert_can_create(db, user)
    cc.assert_write_scope(user, chem.department_id)

    diff: dict = {}
    if changes.get("name") is not None:
        chem.name = changes["name"].strip()
        diff["name"] = chem.name
    if "cas_no" in changes and changes["cas_no"] is not None:
        chem.cas_no = cc.validate_cas(changes["cas_no"])
        diff["cas_no"] = chem.cas_no
    if "manufacturer" in changes and changes["manufacturer"] is not None:
        chem.manufacturer = changes["manufacturer"].strip()
        diff["manufacturer"] = chem.manufacturer
    if "hazard_code" in changes and changes["hazard_code"] is not None:
        chem.hazard_code = changes["hazard_code"].strip()
        diff["hazard_code"] = chem.hazard_code
    if "reorder_threshold" in changes and changes["reorder_threshold"] is not None:
        t = cc.parse_decimal(changes["reorder_threshold"], field="reorder_threshold")
        cc.assert_max_decimals(t, field="reorder_threshold", places=6)
        chem.reorder_threshold = cc.q_base(t)
        diff["reorder_threshold"] = cc.s_base(chem.reorder_threshold)
    if changes.get("base_unit") is not None and changes["base_unit"] != chem.base_unit:
        # Đổi base_unit chỉ khi chưa có lô/giao dịch (BR-CHEM-003 → UNIT_LOCKED)
        if _lot_count(db, chem.id) > 0:
            raise AppException(
                "UNIT_LOCKED",
                "Không thể đổi đơn vị cơ sở khi hóa chất đã có lô/giao dịch",
                422,
            )
        new_unit = cc.get_unit(db, changes["base_unit"])
        chem.base_unit = new_unit.code
        chem.measurement_group = new_unit.measurement_group
        diff["base_unit"] = new_unit.code

    if not diff:
        raise AppException("VALIDATION_ERROR", "Không có thay đổi nào hợp lệ", 400)

    chem.updated_by = user.id
    chem.updated_at = func.now()
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppException(
            "DUPLICATE_CHEMICAL", "Tên/CAS gây trùng trong phòng ban", 409
        )
    audit_service.log_action(
        db,
        action="CHEMICAL_UPDATE",
        resource="chemical",
        user_id=user.id,
        resource_id=chem.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"diff": diff},
    )
    db.commit()
    return get_chemical_detail(db, chemical_id)


def deactivate_chemical(
    db: Session,
    *,
    user: CurrentUser,
    chemical_id: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    chem = cc.get_chemical_or_404(db, chemical_id)
    cc.assert_can_create(db, user)
    cc.assert_write_scope(user, chem.department_id)
    if _total_stock_base(db, chem.id) > 0:
        raise AppException(
            "CHEMICAL_HAS_STOCK",
            "Còn lô tồn > 0 — phải xử lý tồn trước khi vô hiệu hóa",
            422,
        )
    chem.status = "inactive"
    chem.updated_by = user.id
    chem.updated_at = func.now()
    audit_service.log_action(
        db,
        action="CHEMICAL_DEACTIVATE",
        resource="chemical",
        user_id=user.id,
        resource_id=chem.id,
        correlation_id=correlation_id,
        ip=ip,
    )
    db.commit()
    return {"id": chem.id, "status": "inactive"}
