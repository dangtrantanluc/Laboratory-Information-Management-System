"""Lô hoá chất — serialize, list, chi tiết, tạo lô (kèm nhập kho ban đầu nguyên tử).

Tách từ chemical_service.py (850 dòng) — M-03/T1.2.
"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.chemical import (
    Chemical,
    ChemicalLot,
    ChemicalTransaction,
)
from app.services import audit_service, chemical_common as cc

logger_action_prefix = "CHEMICAL"




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
            ErrorCode.INVALID_DATE_ORDER, "Ngày kiểm tra lại phải <= hạn dùng", 422
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
            raise AppException(ErrorCode.VALIDATION_ERROR, "qty_input phải > 0", 400)
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
        raise AppException(ErrorCode.DUPLICATE_LOT, "Số lô đã tồn tại trong hóa chất", 409)

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
