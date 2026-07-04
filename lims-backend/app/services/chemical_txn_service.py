"""Chemical transaction service (M2) — in/out/adjust (FR-005/006/007) + rechecks (FR-011)
+ lịch sử (FR-009).

GIAO DỊCH KHO trong 1 DB transaction + SELECT FOR UPDATE trên lô (chống race trừ tồn,
BR-CHEM-014). Quy đổi đơn vị Decimal. balance_after snapshot. Immutable — không sửa/xóa.

- in:     tăng qty_base, lưu unit_price.
- out:    ref_sample_id BẮT BUỘC; không xuất quá tồn; lô fail/quá hạn → WARNING_NEEDS_CONFIRM.
- adjust: KTV(transact)+Admin; note BẮT BUỘC; tồn không âm.
"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.chemical import (
    Chemical,
    ChemicalLot,
    ChemicalRecheckRecord,
    ChemicalTransaction,
)
from app.models.sample import Sample
from app.services import audit_service, chemical_common as cc, notification_service


def _lot_is_expired(lot: ChemicalLot) -> bool:
    return bool(lot.expiry_date and lot.expiry_date < date.today())


def _reorder_check(
    db: Session, chem: Chemical, *, correlation_id: Optional[str]
) -> None:
    """Sau out/adjust: nếu tổng tồn < reorder_threshold → notify (best-effort, BR-CHEM-019).

    Chạy sau khi cập nhật qty_base nhưng trong cùng transaction (commit chung). Lỗi notify
    không được làm hỏng giao dịch chính → bọc try.
    """
    if chem.reorder_threshold is None:
        return
    total = db.execute(
        select(func.coalesce(func.sum(ChemicalLot.qty_base), 0)).where(
            ChemicalLot.chemical_id == chem.id
        )
    ).scalar_one()
    if Decimal(total) >= chem.reorder_threshold:
        return
    try:
        from app.models.department import Department

        dept = db.get(Department, chem.department_id)
        recipients: set[uuid.UUID] = set()
        if dept and dept.lead_user_id:
            recipients.add(dept.lead_user_id)
        # thêm admin (mọi admin) để không sót cảnh báo
        from app.models.user import User

        admins = db.execute(
            select(User.id).where(User.role == "admin", User.status == "active")
        ).scalars().all()
        recipients.update(admins)
        for uid in recipients:
            notification_service.create_notification(
                db,
                user_id=uid,
                type="CHEM_LOW_STOCK",
                title="Hóa chất dưới ngưỡng tồn",
                body=f"{chem.name} còn {cc.s_base(Decimal(total))} {chem.base_unit} "
                f"(ngưỡng {cc.s_base(chem.reorder_threshold)})",
                ref_type="chemical",
                ref_id=chem.id,
            )
    except Exception:  # noqa: BLE001 — notify lỗi không chặn giao dịch
        pass


def create_transaction(
    db: Session,
    *,
    user: CurrentUser,
    lot_id: uuid.UUID,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
    can_cost: bool,
) -> dict:
    cc.assert_can_transact(db, user)
    txn_type = payload["type"]
    at = payload.get("at") or datetime.now(timezone.utc)

    # ====== TRANSACTION + ROW-LOCK ======
    lot = cc.get_lot_or_404(db, lot_id, lock=True)
    chem = db.get(Chemical, lot.chemical_id)
    cc.assert_write_scope(user, chem.department_id)

    if txn_type == "in":
        result = _do_in(db, user, lot, chem, payload, at, correlation_id, ip)
    elif txn_type == "out":
        result = _do_out(db, user, lot, chem, payload, at, correlation_id, ip)
    elif txn_type == "adjust":
        result = _do_adjust(db, user, lot, chem, payload, at, correlation_id, ip)
    else:
        raise AppException("VALIDATION_ERROR", "Loại giao dịch không hợp lệ", 400)

    db.commit()
    return cc.strip_price_fields(result, can_cost)


def _do_in(db, user, lot, chem, payload, at, correlation_id, ip) -> dict:
    qty_input = cc.parse_decimal(payload.get("qty_input"), field="qty_input")
    if qty_input is None or qty_input <= 0:
        raise AppException("INVALID_QUANTITY", "qty_input phải > 0", 400)
    cc.assert_max_decimals(qty_input, field="qty_input", places=4)
    input_unit = payload.get("input_unit")
    if not input_unit:
        raise AppException("VALIDATION_ERROR", "Thiếu input_unit", 400)
    qty_base = cc.convert_to_base(
        db, qty_input, input_unit, chem.base_unit, chem.measurement_group
    )
    unit_price = cc.parse_decimal(payload.get("unit_price"), field="unit_price")
    if unit_price is not None:
        cc.assert_max_decimals(unit_price, field="unit_price", places=2)
        unit_price = cc.q_money(unit_price)
    currency = payload.get("currency") or "VND"

    balance_after = cc.q_base(lot.qty_base + qty_base)
    txn = ChemicalTransaction(
        lot_id=lot.id,
        type="in",
        qty_base=qty_base,
        base_unit=chem.base_unit,
        qty_input=qty_input,
        input_unit=input_unit,
        balance_after=balance_after,
        unit_price=unit_price,
        price_unit=input_unit if unit_price is not None else None,
        currency=currency if unit_price is not None else None,
        note=payload.get("note"),
        by_user=user.id,
        correlation_id=correlation_id,
        at=at,
    )
    db.add(txn)
    lot.qty_base = balance_after
    if unit_price is not None:
        lot.unit_price = unit_price
        lot.price_unit = input_unit
        lot.currency = currency
    lot.updated_by = user.id
    lot.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="CHEMICAL_TXN_IN",
        resource="chem_lot",
        user_id=user.id,
        resource_id=lot.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"qty_input": cc.s_input(qty_input), "input_unit": input_unit},
    )
    return _txn_dict(db, txn)


def _do_out(db, user, lot, chem, payload, at, correlation_id, ip) -> dict:
    qty_input = cc.parse_decimal(payload.get("qty_input"), field="qty_input")
    if qty_input is None or qty_input <= 0:
        raise AppException("INVALID_QUANTITY", "qty_input phải > 0", 400)
    cc.assert_max_decimals(qty_input, field="qty_input", places=4)
    input_unit = payload.get("input_unit")
    if not input_unit:
        raise AppException("VALIDATION_ERROR", "Thiếu input_unit", 400)

    ref_sample_id = payload.get("ref_sample_id")
    if ref_sample_id is None:
        raise AppException(
            "SAMPLE_REQUIRED", "Giao dịch xuất bắt buộc gắn mẫu (ref_sample_id)", 422
        )
    sample = db.get(Sample, ref_sample_id)
    if sample is None or sample.deleted_at is not None:
        raise AppException("SAMPLE_NOT_FOUND", "Mẫu liên quan không tồn tại", 422)

    qty_base = cc.convert_to_base(
        db, qty_input, input_unit, chem.base_unit, chem.measurement_group
    )

    # Cảnh báo lô fail / quá hạn (BR-CHEM-024) — cần confirm_warning
    expired = _lot_is_expired(lot)
    failed = lot.recheck_result == "fail"
    confirm = bool(payload.get("confirm_warning"))
    warning_override = False
    if (expired or failed) and not confirm:
        reason = "RECHECK_FAILED" if failed else "LOT_EXPIRED"
        raise AppException(
            "WARNING_NEEDS_CONFIRM",
            "Lô có kết quả kiểm tra lại 'không đạt' hoặc đã quá hạn. Xác nhận để tiếp tục xuất.",
            422,
            [
                {"field": "lot", "reason": reason, "recheck_result": lot.recheck_result},
                {"hint": "Gửi lại với confirm_warning=true và note (lý do) để truy vết 17025."},
            ],
        )
    if expired or failed:
        warning_override = True

    if qty_base > lot.qty_base:
        raise AppException(
            "INSUFFICIENT_STOCK",
            f"Xuất {cc.s_base(qty_base)} {chem.base_unit} vượt tồn {cc.s_base(lot.qty_base)}",
            422,
        )

    balance_after = cc.q_base(lot.qty_base - qty_base)
    txn = ChemicalTransaction(
        lot_id=lot.id,
        type="out",
        qty_base=qty_base,
        base_unit=chem.base_unit,
        qty_input=qty_input,
        input_unit=input_unit,
        balance_after=balance_after,
        ref_sample_id=ref_sample_id,
        warning_override=warning_override,
        note=payload.get("note"),
        by_user=user.id,
        correlation_id=correlation_id,
        at=at,
    )
    db.add(txn)
    lot.qty_base = balance_after
    lot.updated_by = user.id
    lot.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="CHEMICAL_TXN_OUT",
        resource="chem_lot",
        user_id=user.id,
        resource_id=lot.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={
            "qty_input": cc.s_input(qty_input),
            "input_unit": input_unit,
            "ref_sample_id": str(ref_sample_id),
            "warning_override": warning_override,
            "note": payload.get("note"),
        },
    )
    _reorder_check(db, chem, correlation_id=correlation_id)
    return _txn_dict(db, txn)


def _do_adjust(db, user, lot, chem, payload, at, correlation_id, ip) -> dict:
    note = payload.get("note")
    if not note or not note.strip():
        raise AppException("REASON_REQUIRED", "Điều chỉnh phải ghi lý do (note)", 400)
    input_unit = payload.get("input_unit")
    if not input_unit:
        raise AppException("VALIDATION_ERROR", "Thiếu input_unit", 400)

    actual = payload.get("actual_qty_input")
    delta = payload.get("delta_input")
    if (actual is None) == (delta is None):
        raise AppException(
            "VALIDATION_ERROR",
            "Gửi đúng MỘT trong actual_qty_input / delta_input",
            400,
        )

    if actual is not None:
        actual_d = cc.parse_decimal(actual, field="actual_qty_input")
        cc.assert_max_decimals(actual_d, field="actual_qty_input", places=4)
        actual_base = cc.convert_to_base(
            db, actual_d, input_unit, chem.base_unit, chem.measurement_group
        )
        delta_base = cc.q_base(actual_base - lot.qty_base)
        # qty_input báo cáo = giá trị thực tế đã nhập (để audit 17025)
        qty_input_report = actual_d
    else:
        delta_d = cc.parse_decimal(delta, field="delta_input", allow_negative=True)
        cc.assert_max_decimals(abs(delta_d), field="delta_input", places=4)
        # quy đổi delta (giữ dấu) sang base
        sign = Decimal("-1") if delta_d < 0 else Decimal("1")
        delta_base = sign * cc.convert_to_base(
            db, abs(delta_d), input_unit, chem.base_unit, chem.measurement_group
        )
        qty_input_report = abs(delta_d)

    if delta_base == 0:
        raise AppException("VALIDATION_ERROR", "Điều chỉnh không thay đổi tồn", 400)

    balance_after = cc.q_base(lot.qty_base + delta_base)
    if balance_after < 0:
        raise AppException("NEGATIVE_BALANCE", "Điều chỉnh khiến tồn < 0", 422)

    txn = ChemicalTransaction(
        lot_id=lot.id,
        type="adjust",
        qty_base=delta_base,  # có dấu
        base_unit=chem.base_unit,
        qty_input=qty_input_report,
        input_unit=input_unit,
        balance_after=balance_after,
        note=note.strip(),
        by_user=user.id,
        correlation_id=correlation_id,
        at=at,
    )
    db.add(txn)
    lot.qty_base = balance_after
    lot.updated_by = user.id
    lot.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="CHEMICAL_TXN_ADJUST",
        resource="chem_lot",
        user_id=user.id,
        resource_id=lot.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"delta_base": cc.s_base(delta_base), "note": note.strip()[:200]},
    )
    _reorder_check(db, chem, correlation_id=correlation_id)
    return _txn_dict(db, txn)


def _txn_dict(db: Session, txn: ChemicalTransaction) -> dict:
    ref_code = None
    if txn.ref_sample_id:
        s = db.get(Sample, txn.ref_sample_id)
        ref_code = s.sample_code if s else None
    return {
        "id": txn.id,
        "lot_id": txn.lot_id,
        "type": txn.type,
        "qty_input": cc.s_input(txn.qty_input),
        "input_unit": txn.input_unit,
        "qty_base": cc.s_base(txn.qty_base),
        "base_unit": txn.base_unit,
        "balance_after": cc.s_base(txn.balance_after),
        "ref_sample_id": txn.ref_sample_id,
        "ref_sample_code": ref_code,
        "warning_override": txn.warning_override,
        "note": txn.note,
        "by_user": txn.by_user,
        "at": txn.at,
        "correlation_id": txn.correlation_id,
        "unit_price": cc.s_money(txn.unit_price),
        "currency": txn.currency,
    }


# ===== Lịch sử giao dịch (FR-009) =====
def list_transactions(
    db: Session,
    *,
    chemical_id: Optional[uuid.UUID],
    lot_id: Optional[uuid.UUID],
    ref_sample_id: Optional[uuid.UUID],
    by_user: Optional[uuid.UUID],
    txn_type: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
    department_id: Optional[uuid.UUID],
    display_unit: Optional[str],
    page: int,
    limit: int,
    can_cost: bool,
) -> tuple[list[dict], int]:
    if date_from and date_to and date_from > date_to:
        raise AppException("VALIDATION_ERROR", "date_from phải <= date_to", 400)

    conditions = []
    if lot_id:
        conditions.append(ChemicalTransaction.lot_id == lot_id)
    if chemical_id:
        sub = select(ChemicalLot.id).where(ChemicalLot.chemical_id == chemical_id)
        conditions.append(ChemicalTransaction.lot_id.in_(sub))
    if department_id:
        sub = select(ChemicalLot.id).join(
            Chemical, Chemical.id == ChemicalLot.chemical_id
        ).where(Chemical.department_id == department_id)
        conditions.append(ChemicalTransaction.lot_id.in_(sub))
    if ref_sample_id:
        conditions.append(ChemicalTransaction.ref_sample_id == ref_sample_id)
    if by_user:
        conditions.append(ChemicalTransaction.by_user == by_user)
    if txn_type:
        conditions.append(ChemicalTransaction.type == txn_type)
    if date_from:
        conditions.append(func.date(ChemicalTransaction.at) >= date_from)
    if date_to:
        conditions.append(func.date(ChemicalTransaction.at) <= date_to)

    total = db.execute(
        select(func.count()).select_from(ChemicalTransaction).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(ChemicalTransaction)
        .where(*conditions)
        .order_by(ChemicalTransaction.at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()

    items = []
    for txn in rows:
        lot = db.get(ChemicalLot, txn.lot_id)
        chem = db.get(Chemical, lot.chemical_id) if lot else None
        ref_code = None
        if txn.ref_sample_id:
            s = db.get(Sample, txn.ref_sample_id)
            ref_code = s.sample_code if s else None
        line_value = None
        if txn.unit_price is not None and chem:
            qty_price_unit = cc.convert_from_base(
                db, txn.qty_base, chem.base_unit, txn.input_unit, chem.measurement_group
            )
            line_value = cc.s_money(qty_price_unit * txn.unit_price)
        entry = {
            "id": txn.id,
            "lot_id": txn.lot_id,
            "lot_no": lot.lot_no if lot else None,
            "chemical_id": chem.id if chem else None,
            "chemical_name": chem.name if chem else None,
            "type": txn.type,
            "qty_input": cc.s_input(txn.qty_input),
            "input_unit": txn.input_unit,
            "qty_base": cc.s_base(txn.qty_base),
            "base_unit": txn.base_unit,
            "balance_after": cc.s_base(txn.balance_after),
            "ref_sample_code": ref_code,
            "warning_override": txn.warning_override,
            "by_user_name": cc.user_name(db, txn.by_user),
            "at": txn.at,
            "note": txn.note,
            "unit_price": cc.s_money(txn.unit_price),
            "currency": txn.currency,
            "line_value": line_value,
        }
        items.append(entry)
    return cc.strip_price_fields(items, can_cost), total


# ===== Rechecks (FR-011) =====
def create_recheck(
    db: Session,
    *,
    user: CurrentUser,
    lot_id: uuid.UUID,
    result: str,
    checked_at: date,
    next_recheck_date: Optional[date],
    note: Optional[str],
    attachment_file_key: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    cc.assert_can_create(db, user)
    lot = cc.get_lot_or_404(db, lot_id, lock=True)
    chem = db.get(Chemical, lot.chemical_id)
    cc.assert_write_scope(user, chem.department_id)

    if checked_at > date.today():
        raise AppException("VALIDATION_ERROR", "Ngày kiểm tra không được ở tương lai", 400)
    if next_recheck_date and lot.expiry_date and next_recheck_date > lot.expiry_date:
        raise AppException(
            "INVALID_DATE_ORDER", "Ngày kiểm tra kế tiếp phải <= hạn dùng", 422
        )

    rec = ChemicalRecheckRecord(
        lot_id=lot.id,
        checked_at=checked_at,
        result=result,
        note=note,
        next_recheck_date=next_recheck_date,
        checked_by=user.id,
    )
    db.add(rec)
    lot.recheck_result = result
    if next_recheck_date:
        lot.recheck_date = next_recheck_date
    lot.updated_by = user.id
    lot.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="CHEMICAL_RECHECK",
        resource="chem_lot",
        user_id=user.id,
        resource_id=lot.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"result": result, "checked_at": checked_at.isoformat()},
    )
    db.commit()
    db.refresh(rec)
    return {
        "id": rec.id,
        "lot_id": rec.lot_id,
        "result": rec.result,
        "checked_at": rec.checked_at.isoformat(),
        "next_recheck_date": rec.next_recheck_date.isoformat()
        if rec.next_recheck_date
        else None,
        "lot_recheck_result": lot.recheck_result,
    }
