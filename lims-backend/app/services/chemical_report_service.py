"""Chemical report service (M2) — xuất Excel nhật ký (FR-013) + báo cáo tiêu hao (FR-014).

Cột tiền (unit_price/currency/line_value/consumption_cost) CHỈ cho vai trò có quyền
chemical:cost (admin/leader/accountant). KTV (staff) bị STRIP cột giá ở TẦNG API — đây là
biện pháp bảo mật OWASP A01 (không chỉ ẩn FE).

Sync: ≤ EXPORT_MAX_ROWS dòng (contract §4.4); vượt → EXPORT_TOO_LARGE.
"""
import io
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.chemical import Chemical, ChemicalLot, ChemicalTransaction
from app.models.sample import Sample
from app.services import audit_service, chemical_common as cc

EXPORT_MAX_ROWS = 10000

_BASE_COLUMNS = [
    "Ngày", "Hóa chất", "CAS", "Lô", "Loại", "SL nhập", "Đơn vị nhập",
    "SL (base)", "Đơn vị base", "Tồn sau", "Mẫu", "Người", "Ghi chú",
]
_COST_COLUMNS = ["Đơn giá", "Tiền tệ", "Thành tiền"]


def _scope_department(user: CurrentUser, requested: Optional[uuid.UUID]) -> Optional[uuid.UUID]:
    """KTV bị ép phòng mình; admin/leader/accountant theo yêu cầu."""
    if cc.is_privileged(user) or user.role == "accountant":
        return requested
    return user.department_id


def _txn_query(
    *,
    date_from: date,
    date_to: date,
    chemical_id: Optional[uuid.UUID],
    ref_sample_id: Optional[uuid.UUID],
    by_user: Optional[uuid.UUID],
    txn_type: Optional[str],
    department_id: Optional[uuid.UUID],
):
    conditions = [
        func.date(ChemicalTransaction.at) >= date_from,
        func.date(ChemicalTransaction.at) <= date_to,
    ]
    if chemical_id:
        sub = select(ChemicalLot.id).where(ChemicalLot.chemical_id == chemical_id)
        conditions.append(ChemicalTransaction.lot_id.in_(sub))
    if department_id:
        sub = (
            select(ChemicalLot.id)
            .join(Chemical, Chemical.id == ChemicalLot.chemical_id)
            .where(Chemical.department_id == department_id)
        )
        conditions.append(ChemicalTransaction.lot_id.in_(sub))
    if ref_sample_id:
        conditions.append(ChemicalTransaction.ref_sample_id == ref_sample_id)
    if by_user:
        conditions.append(ChemicalTransaction.by_user == by_user)
    if txn_type:
        conditions.append(ChemicalTransaction.type == txn_type)
    return conditions


def export_transactions_xlsx(
    db: Session,
    *,
    user: CurrentUser,
    date_from: date,
    date_to: date,
    chemical_id: Optional[uuid.UUID],
    ref_sample_id: Optional[uuid.UUID],
    by_user: Optional[uuid.UUID],
    txn_type: Optional[str],
    department_id: Optional[uuid.UUID],
    can_cost: bool,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> bytes:
    if date_from > date_to:
        raise AppException("INVALID_DATE_RANGE", "date_from phải <= date_to", 400)

    dept = _scope_department(user, department_id)
    conditions = _txn_query(
        date_from=date_from,
        date_to=date_to,
        chemical_id=chemical_id,
        ref_sample_id=ref_sample_id,
        by_user=by_user,
        txn_type=txn_type,
        department_id=dept,
    )

    total = db.execute(
        select(func.count()).select_from(ChemicalTransaction).where(*conditions)
    ).scalar_one()
    if total > EXPORT_MAX_ROWS:
        raise AppException(
            "EXPORT_TOO_LARGE",
            f"Kết quả {total} dòng vượt ngưỡng {EXPORT_MAX_ROWS}. Thu hẹp khoảng/lọc.",
            422,
        )

    rows = db.execute(
        select(ChemicalTransaction)
        .where(*conditions)
        .order_by(ChemicalTransaction.at.asc())
    ).scalars().all()

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Nhat ky hoa chat"
    columns = _BASE_COLUMNS + (_COST_COLUMNS if can_cost else [])
    ws.append(columns)

    for txn in rows:
        lot = db.get(ChemicalLot, txn.lot_id)
        chem = db.get(Chemical, lot.chemical_id) if lot else None
        ref_code = None
        if txn.ref_sample_id:
            s = db.get(Sample, txn.ref_sample_id)
            ref_code = s.sample_code if s else None
        row = [
            txn.at.strftime("%Y-%m-%d %H:%M"),
            chem.name if chem else "",
            chem.cas_no if chem else "",
            lot.lot_no if lot else "",
            txn.type,
            cc.s_input(txn.qty_input),
            txn.input_unit,
            cc.s_base(txn.qty_base),
            txn.base_unit,
            cc.s_base(txn.balance_after),
            ref_code or "",
            cc.user_name(db, txn.by_user) or "",
            txn.note or "",
        ]
        if can_cost:
            line_value = None
            if txn.unit_price is not None and chem:
                qty_pu = cc.convert_from_base(
                    db, txn.qty_base, chem.base_unit, txn.input_unit, chem.measurement_group
                )
                line_value = cc.s_money(qty_pu * txn.unit_price)
            row += [cc.s_money(txn.unit_price) or "", txn.currency or "", line_value or ""]
        ws.append(row)

    audit_service.log_action(
        db,
        action="CHEMICAL_EXPORT_EXCEL",
        resource="chemical",
        user_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "rows": total,
            "with_cost": can_cost,
        },
    )
    db.commit()

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def consumption_report(
    db: Session,
    *,
    user: CurrentUser,
    group_by: str,
    date_from: date,
    date_to: date,
    chemical_id: Optional[uuid.UUID],
    department_id: Optional[uuid.UUID],
    can_cost: bool,
) -> list[dict]:
    """Báo cáo tiêu hao (tổng out) theo month/project/user. Quy đổi về base từng hóa chất;
    KHÔNG cộng gộp khác nhóm đo. consumption_cost chỉ vai trò tài chính."""
    if date_from > date_to:
        raise AppException("INVALID_DATE_RANGE", "date_from phải <= date_to", 400)
    if group_by not in ("month", "project", "user"):
        raise AppException("VALIDATION_ERROR", "group_by không hợp lệ", 400)

    dept = _scope_department(user, department_id)
    conditions = _txn_query(
        date_from=date_from,
        date_to=date_to,
        chemical_id=chemical_id,
        ref_sample_id=None,
        by_user=None,
        txn_type="out",
        department_id=dept,
    )
    rows = db.execute(
        select(ChemicalTransaction).where(*conditions)
    ).scalars().all()

    # groups[group_key][chemical_id] = {consumed_base, cost, chem}
    groups: dict = {}
    for txn in rows:
        lot = db.get(ChemicalLot, txn.lot_id)
        chem = db.get(Chemical, lot.chemical_id) if lot else None
        if chem is None:
            continue
        gk, gl = _group_key(db, txn, group_by)
        bucket = groups.setdefault(gk, {"label": gl, "chems": {}})
        cell = bucket["chems"].setdefault(
            chem.id, {"chem": chem, "consumed_base": Decimal("0"), "cost": Decimal("0")}
        )
        cell["consumed_base"] += txn.qty_base
        if txn.unit_price is not None:
            qty_pu = cc.convert_from_base(
                db, txn.qty_base, chem.base_unit, txn.input_unit, chem.measurement_group
            )
            cell["cost"] += qty_pu * txn.unit_price

    out = []
    for gk in sorted(groups.keys()):
        bucket = groups[gk]
        lines = []
        for cell in bucket["chems"].values():
            chem = cell["chem"]
            line = {
                "chemical_name": chem.name,
                "measurement_group": chem.measurement_group,
                "base_unit": chem.base_unit,
                "consumed_base": cc.s_base(cell["consumed_base"]),
                "consumed_display": cc.s_input(cell["consumed_base"]),
                "display_unit": chem.base_unit,
                "consumption_cost": cc.s_money(cell["cost"]),
                "currency": "VND",
            }
            lines.append(line)
        out.append({"group_key": gk, "group_label": bucket["label"], "lines": lines})

    return cc.strip_price_fields(out, can_cost)


def _group_key(db: Session, txn: ChemicalTransaction, group_by: str) -> tuple[str, str]:
    if group_by == "month":
        key = txn.at.strftime("%Y-%m")
        return key, f"Tháng {txn.at.month}/{txn.at.year}"
    if group_by == "user":
        name = cc.user_name(db, txn.by_user) or str(txn.by_user)
        return str(txn.by_user), name
    # project = theo mẫu (đề tài) — dùng request_id của mẫu; mẫu không gắn → "Không gắn đề tài"
    if txn.ref_sample_id:
        s = db.get(Sample, txn.ref_sample_id)
        if s:
            from app.models.test_request import TestRequest

            req = db.get(TestRequest, s.request_id)
            if req:
                return str(req.id), req.request_code
    return "none", "Không gắn đề tài"
