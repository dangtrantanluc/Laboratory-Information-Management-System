"""Tồn kho — gợi ý FEFO, tồn theo hoá chất, cảnh báo tồn thấp, kiểm kê (FR-008/FR-010).

Tách từ chemical_service.py (850 dòng) — M-03/T1.2.
"""
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chemical import (
    Chemical,
    ChemicalLot,
    ChemicalTransaction,
)
from app.services import chemical_common as cc

logger_action_prefix = "CHEMICAL"


from app.services.chemical._shared import _total_stock_base
from app.services.chemical.lot_service import _is_expired


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
