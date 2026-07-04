"""Chemical service (M2) — CRUD hóa chất, lô, tồn kho, low-stock, reconcile, FEFO,
đính kèm MSDS/CoA, units (FR-001/002/003/004/008/010).

Quy đổi đơn vị qua chemical_common (Decimal). Field-level price strip theo quyền cost.
Tạo lô + giao dịch nhập đầu (initial_intake) atomic trong 1 transaction.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found
from app.models.chemical import (
    Chemical,
    ChemicalLot,
    ChemicalTransaction,
    Unit,
)
from app.services import audit_service, chemical_common as cc

logger_action_prefix = "CHEMICAL"


# ===== units =====
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


# ===== total stock helper (đọc qty_base lô — không SUM giao dịch runtime) =====
def _total_stock_base(db: Session, chemical_id: uuid.UUID) -> Decimal:
    total = db.execute(
        select(func.coalesce(func.sum(ChemicalLot.qty_base), 0)).where(
            ChemicalLot.chemical_id == chemical_id
        )
    ).scalar_one()
    return cc.q_base(Decimal(total))


def _lot_count(db: Session, chemical_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count()).select_from(ChemicalLot).where(
            ChemicalLot.chemical_id == chemical_id
        )
    ).scalar_one()


# ===== chemicals: list / search =====
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


# ===== chemicals: create =====
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


# ===== chemicals: detail =====
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


# ===== chemicals: update =====
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


# ===== chemicals: deactivate =====
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


# ===== lots: serialize =====
def _lot_dict(
    db: Session, lot: ChemicalLot, *, measurement_group: str, display_unit: Optional[str]
) -> dict:
    data = {
        "id": lot.id,
        "chemical_id": lot.chemical_id,
        "lot_no": lot.lot_no,
        "qty_base": cc.s_base(lot.qty_base),
        "base_unit": None,  # set below from chemical base_unit
        "recheck_result": lot.recheck_result,
        "received_at": lot.received_at.isoformat() if lot.received_at else None,
        "expiry_date": lot.expiry_date.isoformat() if lot.expiry_date else None,
        "recheck_date": lot.recheck_date.isoformat() if lot.recheck_date else None,
        "is_expired": _is_expired(lot),
        "has_coa": bool(lot.coa_file_key),
        "unit_price": cc.s_money(lot.unit_price),
        "price_unit": lot.price_unit,
        "currency": lot.currency,
    }
    chem = db.get(Chemical, lot.chemical_id)
    data["base_unit"] = chem.base_unit if chem else None
    if display_unit:
        qty_disp = cc.convert_from_base(
            db, lot.qty_base, chem.base_unit, display_unit, measurement_group
        )
        data["qty_display"] = cc.s_input(qty_disp)
        data["display_unit"] = display_unit
    # stock_value = qty (quy về price_unit) × unit_price (BR-CHEM-030)
    if chem and lot.unit_price is not None:
        qty_in_price_unit = cc.convert_from_base(
            db, lot.qty_base, chem.base_unit, lot.price_unit, measurement_group
        )
        data["stock_value"] = cc.s_money(qty_in_price_unit * lot.unit_price)
    return data


def _is_expired(lot: ChemicalLot) -> bool:
    if lot.expiry_date is None:
        return False
    return lot.expiry_date < date.today()


def list_lots(
    db: Session,
    *,
    chemical_id: uuid.UUID,
    status_filter: Optional[str],
    display_unit: Optional[str],
    page: int,
    limit: int,
) -> tuple[list[dict], dict, int]:
    chem = cc.get_chemical_or_404(db, chemical_id)
    if display_unit:
        cc.assert_same_group(db, display_unit, chem.measurement_group)

    conditions = [ChemicalLot.chemical_id == chemical_id]
    today = date.today()
    if status_filter == "in_stock":
        conditions.append(ChemicalLot.qty_base > 0)
    elif status_filter == "expired":
        conditions.append(ChemicalLot.expiry_date < today)
    elif status_filter == "recheck_due":
        conditions.append(ChemicalLot.recheck_date <= today)

    total = db.execute(
        select(func.count()).select_from(ChemicalLot).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(ChemicalLot)
        .where(*conditions)
        .order_by(ChemicalLot.expiry_date.asc().nulls_last(), ChemicalLot.created_at.asc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    items = [
        _lot_dict(db, lot, measurement_group=chem.measurement_group, display_unit=display_unit)
        for lot in rows
    ]
    return items, {"measurement_group": chem.measurement_group}, total


def get_lot_detail(
    db: Session, *, lot_id: uuid.UUID, display_unit: Optional[str]
) -> dict:
    lot = cc.get_lot_or_404(db, lot_id)
    chem = db.get(Chemical, lot.chemical_id)
    if display_unit:
        cc.assert_same_group(db, display_unit, chem.measurement_group)
    return _lot_dict(
        db, lot, measurement_group=chem.measurement_group, display_unit=display_unit
    )


# ===== lots: create (+ optional initial intake atomic) =====
def create_lot(
    db: Session,
    *,
    user: CurrentUser,
    chemical_id: uuid.UUID,
    lot_no: str,
    received_at: Optional[date],
    expiry_date: Optional[date],
    recheck_date: Optional[date],
    initial_intake: Optional[dict],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    chem = cc.get_chemical_or_404(db, chemical_id)
    cc.assert_can_create(db, user)
    cc.assert_write_scope(user, chem.department_id)

    if recheck_date and expiry_date and recheck_date > expiry_date:
        raise AppException(
            "INVALID_DATE_ORDER", "Ngày kiểm tra lại phải <= hạn dùng", 422
        )

    warnings: list[str] = []
    is_expired = bool(expiry_date and expiry_date < date.today())
    if is_expired:
        warnings.append("LOT_ALREADY_EXPIRED")

    # Quy đổi initial intake (nếu có) — trước khi tạo, để fail sớm
    intake_qty_base: Optional[Decimal] = None
    intake_qty_input: Optional[Decimal] = None
    intake_price: Optional[Decimal] = None
    intake_unit: Optional[str] = None
    intake_currency = "VND"
    intake_note: Optional[str] = None
    if initial_intake:
        intake_qty_input = cc.parse_decimal(
            initial_intake.get("qty_input"), field="qty_input"
        )
        if intake_qty_input is None or intake_qty_input <= 0:
            raise AppException("VALIDATION_ERROR", "qty_input phải > 0", 400)
        cc.assert_max_decimals(intake_qty_input, field="qty_input", places=4)
        intake_unit = initial_intake.get("input_unit")
        intake_qty_base = cc.convert_to_base(
            db, intake_qty_input, intake_unit, chem.base_unit, chem.measurement_group
        )
        intake_price = cc.parse_decimal(
            initial_intake.get("unit_price"), field="unit_price"
        )
        if intake_price is not None:
            cc.assert_max_decimals(intake_price, field="unit_price", places=2)
            intake_price = cc.q_money(intake_price)
        intake_currency = initial_intake.get("currency") or "VND"
        intake_note = initial_intake.get("note")

    price_unit = intake_unit if intake_unit else chem.base_unit
    lot = ChemicalLot(
        chemical_id=chem.id,
        lot_no=lot_no.strip(),
        qty_base=intake_qty_base if intake_qty_base else Decimal("0"),
        unit_price=intake_price if intake_price is not None else Decimal("0"),
        price_unit=price_unit,
        currency=intake_currency,
        received_at=received_at,
        expiry_date=expiry_date,
        recheck_date=recheck_date,
        is_expired=is_expired,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(lot)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppException("DUPLICATE_LOT", "Số lô đã tồn tại trong hóa chất", 409)

    audit_service.log_action(
        db,
        action="CHEMICAL_LOT_CREATE",
        resource="chem_lot",
        user_id=user.id,
        resource_id=lot.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"lot_no": lot.lot_no, "chemical_id": str(chem.id)},
    )

    txn_data = None
    if intake_qty_base is not None:
        txn = ChemicalTransaction(
            lot_id=lot.id,
            type="in",
            qty_base=intake_qty_base,
            base_unit=chem.base_unit,
            qty_input=intake_qty_input,
            input_unit=intake_unit,
            balance_after=intake_qty_base,
            unit_price=intake_price,
            price_unit=intake_unit if intake_price is not None else None,
            currency=intake_currency if intake_price is not None else None,
            note=intake_note,
            by_user=user.id,
            correlation_id=correlation_id,
        )
        db.add(txn)
        db.flush()
        audit_service.log_action(
            db,
            action="CHEMICAL_TXN_IN",
            resource="chem_lot",
            user_id=user.id,
            resource_id=lot.id,
            correlation_id=correlation_id,
            ip=ip,
            detail={"qty_input": cc.s_input(intake_qty_input), "input_unit": intake_unit},
        )
        txn_data = {
            "id": txn.id,
            "type": "in",
            "qty_input": cc.s_input(txn.qty_input),
            "input_unit": txn.input_unit,
            "qty_base": cc.s_base(txn.qty_base),
            "base_unit": txn.base_unit,
            "balance_after": cc.s_base(txn.balance_after),
        }

    db.commit()
    db.refresh(lot)

    lot_data = {
        "id": lot.id,
        "chemical_id": lot.chemical_id,
        "lot_no": lot.lot_no,
        "qty_base": cc.s_base(lot.qty_base),
        "base_unit": chem.base_unit,
        "expiry_date": lot.expiry_date.isoformat() if lot.expiry_date else None,
        "recheck_date": lot.recheck_date.isoformat() if lot.recheck_date else None,
        "is_expired": lot.is_expired,
        "recheck_result": lot.recheck_result,
        "created_at": lot.created_at,
        "unit_price": cc.s_money(lot.unit_price),
        "price_unit": lot.price_unit,
        "currency": lot.currency,
    }
    result = {"lot": lot_data, "transaction": txn_data}
    if warnings:
        result["warnings"] = warnings
    return result


# ===== FEFO suggestion =====
def fefo_suggestion(
    db: Session, *, chemical_id: uuid.UUID, display_unit: Optional[str]
) -> list[dict]:
    chem = cc.get_chemical_or_404(db, chemical_id)
    if display_unit:
        cc.assert_same_group(db, display_unit, chem.measurement_group)
    rows = db.execute(
        select(ChemicalLot)
        .where(ChemicalLot.chemical_id == chemical_id, ChemicalLot.qty_base > 0)
        .order_by(ChemicalLot.expiry_date.asc().nulls_last(), ChemicalLot.created_at.asc())
    ).scalars().all()
    out = []
    rank = 1
    for lot in rows:
        expired = _is_expired(lot)
        requires_warn = expired or lot.recheck_result == "fail"
        entry = {
            "lot_id": lot.id,
            "lot_no": lot.lot_no,
            "qty_base": cc.s_base(lot.qty_base),
            "expiry_date": lot.expiry_date.isoformat() if lot.expiry_date else None,
            "is_expired": expired,
            "recheck_result": lot.recheck_result,
            "fefo_rank": rank,
            "requires_warning_confirm": requires_warn,
        }
        if display_unit:
            entry["qty_display"] = cc.s_input(
                cc.convert_from_base(
                    db, lot.qty_base, chem.base_unit, display_unit, chem.measurement_group
                )
            )
            entry["display_unit"] = display_unit
        out.append(entry)
        rank += 1
    return out


# ===== stock (FR-008) =====
def get_stock(
    db: Session, *, chemical_id: uuid.UUID, display_unit: Optional[str], can_cost: bool
) -> dict:
    chem = cc.get_chemical_or_404(db, chemical_id)
    if display_unit:
        cc.assert_same_group(db, display_unit, chem.measurement_group)
    lots = db.execute(
        select(ChemicalLot)
        .where(ChemicalLot.chemical_id == chemical_id)
        .order_by(ChemicalLot.expiry_date.asc().nulls_last())
    ).scalars().all()

    total_base = Decimal("0")
    total_value = Decimal("0")
    lot_list = []
    for lot in lots:
        total_base += lot.qty_base
        lot_entry = {
            "lot_id": lot.id,
            "lot_no": lot.lot_no,
            "qty_base": cc.s_base(lot.qty_base),
            "unit_price": cc.s_money(lot.unit_price),
            "price_unit": lot.price_unit,
        }
        qty_in_price_unit = cc.convert_from_base(
            db, lot.qty_base, chem.base_unit, lot.price_unit, chem.measurement_group
        )
        sv = qty_in_price_unit * lot.unit_price
        total_value += sv
        lot_entry["stock_value"] = cc.s_money(sv)
        if display_unit:
            lot_entry["qty_display"] = cc.s_input(
                cc.convert_from_base(
                    db, lot.qty_base, chem.base_unit, display_unit, chem.measurement_group
                )
            )
        lot_list.append(lot_entry)

    data = {
        "chemical_id": chem.id,
        "chemical_name": chem.name,
        "base_unit": chem.base_unit,
        "measurement_group": chem.measurement_group,
        "display_unit": display_unit,
        "total_stock_base": cc.s_base(total_base),
        "total_stock_display": cc.s_input(
            cc.convert_from_base(
                db, total_base, chem.base_unit, display_unit, chem.measurement_group
            )
        )
        if display_unit
        else None,
        "total_stock_value": cc.s_money(total_value),
        "currency": "VND",
        "lots": lot_list,
    }
    return cc.strip_price_fields(data, can_cost)


# ===== low-stock (FR-010) =====
def list_low_stock(
    db: Session, *, department_id: Optional[uuid.UUID], page: int, limit: int
) -> tuple[list[dict], int]:
    conditions = [
        Chemical.status == "active",
        Chemical.reorder_threshold.isnot(None),
    ]
    if department_id:
        conditions.append(Chemical.department_id == department_id)
    chems = db.execute(select(Chemical).where(*conditions)).scalars().all()
    items = []
    for c in chems:
        total = _total_stock_base(db, c.id)
        if total < c.reorder_threshold:
            items.append(
                {
                    "chemical_id": c.id,
                    "chemical_name": c.name,
                    "base_unit": c.base_unit,
                    "total_stock_base": cc.s_base(total),
                    "reorder_threshold": cc.s_base(c.reorder_threshold),
                    "department_name": cc.dept_name(db, c.department_id),
                    "alert_open": True,
                }
            )
    total_count = len(items)
    start = (page - 1) * limit
    return items[start : start + limit], total_count


# ===== reconcile (FR-008 A1) =====
def reconcile(
    db: Session,
    *,
    chemical_id: Optional[uuid.UUID],
    department_id: Optional[uuid.UUID],
    include_ok: bool,
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    if chemical_id:
        conditions.append(ChemicalLot.chemical_id == chemical_id)
    if department_id:
        sub = select(Chemical.id).where(Chemical.department_id == department_id)
        conditions.append(ChemicalLot.chemical_id.in_(sub))
    lots = db.execute(select(ChemicalLot).where(*conditions)).scalars().all()

    items = []
    for lot in lots:
        last_txn = db.execute(
            select(ChemicalTransaction)
            .where(ChemicalTransaction.lot_id == lot.id)
            .order_by(ChemicalTransaction.at.desc())
            .limit(1)
        ).scalar_one_or_none()
        last_balance = last_txn.balance_after if last_txn else Decimal("0")
        diff = cc.q_base(lot.qty_base - last_balance)
        is_mismatch = diff != 0
        if not is_mismatch and not include_ok:
            continue
        chem = db.get(Chemical, lot.chemical_id)
        items.append(
            {
                "lot_id": lot.id,
                "lot_no": lot.lot_no,
                "chemical_name": chem.name if chem else None,
                "lot_qty_base": cc.s_base(lot.qty_base),
                "last_txn_balance_after": cc.s_base(last_balance),
                "diff_base": cc.s_base(diff),
                "status": "MISMATCH" if is_mismatch else "OK",
            }
        )
    total_count = len(items)
    start = (page - 1) * limit
    return items[start : start + limit], total_count


# ===== attachments (MSDS) =====
_COA_ALLOWED_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
_COA_MAX_BYTES = 20 * 1024 * 1024  # 20MB


def upload_coa(
    db: Session,
    *,
    user,
    lot_id: uuid.UUID,
    file_name: str,
    content: bytes,
    mime,
    correlation_id=None,
    ip=None,
) -> dict:
    """Upload chứng chỉ phân tích (CoA) cho lô — gắn theo lô (mỗi lô 1 CoA, ghi đè nếu có).

    RBAC: chỉ vai trò được ghi hóa chất + trong phạm vi phòng của hóa chất (BR-CHEM-018).
    """
    from app.models.chemical import Chemical
    from app.services import audit_service, storage_service

    lot = cc.get_lot_or_404(db, lot_id)
    chem = db.get(Chemical, lot.chemical_id)
    cc.assert_can_create(db, user)
    cc.assert_write_scope(user, chem.department_id)

    if mime is None or mime.lower() not in _COA_ALLOWED_MIME:
        raise cc.err("INVALID_FILE_TYPE", "Chỉ chấp nhận PDF/PNG/JPG/XLSX", 422)
    if len(content) > _COA_MAX_BYTES:
        raise cc.err("FILE_TOO_LARGE", "File vượt quá 20MB", 422)

    file_key = storage_service.build_object_key("chem_lot_coa", lot_id, file_name)
    storage_service.put_object(file_key, content, content_type=mime)
    lot.coa_file_key = file_key
    db.flush()
    audit_service.log_action(
        db,
        action="CHEMICAL_LOT_COA_UPLOAD",
        resource="chemical_lot",
        user_id=user.id,
        resource_id=lot_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"file_name": file_name, "size": len(content)},
    )
    db.commit()
    return {"lot_id": lot_id, "has_coa": True, "file_name": file_name}


def get_coa(db: Session, *, lot_id: uuid.UUID) -> dict:
    lot = cc.get_lot_or_404(db, lot_id)
    if not lot.coa_file_key:
        raise not_found("Lô chưa có file CoA")
    from app.config import settings
    from app.services import storage_service

    file_name = lot.coa_file_key.split("_", 1)[-1]
    url = storage_service.presigned_get_url(lot.coa_file_key, file_name=file_name)
    return {
        "file_name": file_name,
        "mime": "application/pdf",
        "download_url": url,
        "url_expires_at": (
            datetime.now(timezone.utc).timestamp() + settings.presigned_url_ttl_seconds
        ),
    }
