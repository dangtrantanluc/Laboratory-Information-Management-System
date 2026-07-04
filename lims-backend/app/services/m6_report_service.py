"""M6 report service (M6.2) — thống kê số mẫu (#3) + tiêu hao hóa chất (#4).

ĐẾM tổng hợp chéo theo bộ lọc thống nhất `[from, to)` (BR-RPT-009). KHÔNG tính lại
on-time rate (M1) / consumption chi tiết (M2) — chỉ đếm/tổng hợp (CONSTRAINT-1, §0.10).
RBAC: accountant 403 ở #3 (B03); staff ép phòng + strip tiền ở #4 (BR-RPT-001/002).
Cache 60s (BR-RPT-011).
"""
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.models.chemical import Chemical, ChemicalLot, ChemicalTransaction
from app.models.sample import Sample, VALID_SAMPLE_STATUS
from app.services import report_common as rc

VALID_TIME_FIELDS = ("received_at", "completed_at")
VALID_BREAKDOWN = ("status", "time", "department")


# ======================= #3: thống kê số mẫu =======================
def report_samples(
    db: Session,
    *,
    user: CurrentUser,
    date_from,
    date_to,
    department_id: Optional[uuid.UUID],
    group_by: str,
    status_filter: Optional[str],
    time_field: str,
    breakdown: str,
) -> tuple[dict, dict]:
    rc.deny_accountant_samples(user)  # B03 — accountant 403
    rc.validate_group_by(group_by)
    if time_field not in VALID_TIME_FIELDS:
        raise rc.err("VALIDATION_ERROR", "time_field chỉ nhận received_at|completed_at")
    if breakdown not in VALID_BREAKDOWN:
        raise rc.err("VALIDATION_ERROR", "breakdown chỉ nhận status|time|department")
    if status_filter is not None and status_filter not in VALID_SAMPLE_STATUS:
        raise rc.err("VALIDATION_ERROR", "status không hợp lệ")

    d_from, d_to = rc.resolve_range(date_from, date_to)
    dept = rc.resolve_scope_department(db, user, department_id)
    dt_from, dt_to = rc.range_to_dt(d_from, d_to)

    col = Sample.received_at if time_field == "received_at" else Sample.completed_at
    conditions = [Sample.deleted_at.is_(None), col.isnot(None), col >= dt_from, col < dt_to]
    if dept:
        conditions.append(Sample.department_id == dept)
    if status_filter:
        conditions.append(Sample.status == status_filter)

    ckey = rc.cache_key(
        "reports_samples", user, dept,
        {
            "from": d_from, "to": d_to, "group_by": group_by,
            "status": status_filter, "time_field": time_field, "breakdown": breakdown,
        },
    )
    cached = rc.cache_get(ckey)
    if cached is not None:
        return cached, rc.aggregate_meta(
            cached=True, extra={"from": d_from.isoformat(), "to": d_to.isoformat()}
        )

    total = db.execute(
        select(func.count()).select_from(Sample).where(*conditions)
    ).scalar_one()

    by_status = {s: 0 for s in VALID_SAMPLE_STATUS}
    for s, c in db.execute(
        select(Sample.status, func.count()).where(*conditions).group_by(Sample.status)
    ).all():
        by_status[s] = c

    # phân rã thời gian luôn trả (line); column = trục thời gian theo time_field
    time_rows = db.execute(select(col).where(*conditions)).scalars().all()
    buckets: dict[str, int] = {}
    for at in time_rows:
        key = rc.period_key(at, group_by)
        buckets[key] = buckets.get(key, 0) + 1
    by_time = [{"period": k, "count": buckets[k]} for k in sorted(buckets.keys())]

    data: dict = {
        "filter": {
            "from": d_from.isoformat(),
            "to": d_to.isoformat(),
            "department_id": str(dept) if dept else None,
            "time_field": time_field,
        },
        "total": total,
        "breakdown_by": breakdown,
        "by_status": by_status,
        "by_time": by_time,
    }
    if breakdown == "department":
        dept_rows = db.execute(
            select(Sample.department_id, func.count())
            .where(*conditions)
            .group_by(Sample.department_id)
        ).all()
        data["by_department"] = [
            {
                "department_id": str(did),
                "department_name": rc.dept_name(db, did),
                "count": c,
            }
            for did, c in dept_rows
        ]

    rc.cache_set(ckey, data)
    return data, rc.aggregate_meta(
        cached=False, extra={"from": d_from.isoformat(), "to": d_to.isoformat()}
    )


# ======================= #4: thống kê tiêu hao hóa chất =======================
def report_chemicals(
    db: Session,
    *,
    user: CurrentUser,
    date_from,
    date_to,
    department_id: Optional[uuid.UUID],
    group_by: str,
    measurement_group: Optional[str],
    chemical_id: Optional[uuid.UUID],
    metric: str,
) -> tuple[dict, dict]:
    rc.validate_group_by(group_by)
    if metric not in ("consumption", "stock"):
        raise rc.err("VALIDATION_ERROR", "metric chỉ nhận consumption|stock")
    if measurement_group is not None and measurement_group not in ("mass", "volume", "count"):
        raise rc.err("VALIDATION_ERROR", "type (nhóm đo) không hợp lệ")
    if chemical_id is not None and db.get(Chemical, chemical_id) is None:
        raise rc.err("CHEMICAL_NOT_FOUND", "Hóa chất không tồn tại", 404)

    d_from, d_to = rc.resolve_range(date_from, date_to)
    dept = rc.resolve_scope_department(db, user, department_id)
    can_cost = rc.can_see_cost(db, user)

    ckey = rc.cache_key(
        "reports_chemicals", user, dept,
        {
            "from": d_from, "to": d_to, "group_by": group_by,
            "mgroup": measurement_group, "chemical_id": chemical_id, "metric": metric,
        },
    )
    cached = rc.cache_get(ckey)
    if cached is not None:
        return cached, rc.aggregate_meta(
            cached=True, extra={"from": d_from.isoformat(), "to": d_to.isoformat()}
        )

    filter_meta = {
        "from": d_from.isoformat(),
        "to": d_to.isoformat(),
        "department_id": str(dept) if dept else None,
        "metric": metric,
    }

    if metric == "stock":
        data = _chemicals_stock(db, dept, measurement_group, chemical_id, can_cost, filter_meta)
    else:
        data = _chemicals_consumption(
            db, dept, d_from, d_to, measurement_group, chemical_id, can_cost, filter_meta
        )

    data = rc.strip_price_fields(data, can_cost)
    rc.cache_set(ckey, data)
    return data, rc.aggregate_meta(
        cached=False, extra={"from": d_from.isoformat(), "to": d_to.isoformat()}
    )


def _chemicals_consumption(
    db, dept, d_from, d_to, measurement_group, chemical_id, can_cost, filter_meta
) -> dict:
    dt_from, dt_to = rc.range_to_dt(d_from, d_to)
    q = (
        select(
            ChemicalTransaction.qty_base,
            ChemicalTransaction.qty_input,
            ChemicalTransaction.unit_price,
            Chemical.measurement_group,
            Chemical.base_unit,
        )
        .select_from(ChemicalTransaction)
        .join(ChemicalLot, ChemicalLot.id == ChemicalTransaction.lot_id)
        .join(Chemical, Chemical.id == ChemicalLot.chemical_id)
        .where(
            ChemicalTransaction.type == "out",
            ChemicalTransaction.at >= dt_from,
            ChemicalTransaction.at < dt_to,
        )
    )
    if dept:
        q = q.where(Chemical.department_id == dept)
    if measurement_group:
        q = q.where(Chemical.measurement_group == measurement_group)
    if chemical_id:
        q = q.where(Chemical.id == chemical_id)
    rows = db.execute(q).all()

    groups: dict = {}
    total_cost = Decimal("0")
    for qty_base, qty_input, unit_price, mgroup, base_unit in rows:
        g = groups.setdefault(
            mgroup, {"base_unit": base_unit, "qty": Decimal("0"), "cost": Decimal("0")}
        )
        g["qty"] += Decimal(qty_base)
        if unit_price is not None:
            line = Decimal(qty_input) * Decimal(unit_price)
            g["cost"] += line
            total_cost += line

    by_group = []
    for mgroup in sorted(groups.keys()):
        g = groups[mgroup]
        item = {
            "measurement_group": mgroup,
            "base_unit": g["base_unit"],
            "total_qty": float(g["qty"]),
        }
        if can_cost:
            item["consumption_cost"] = int(g["cost"])
        by_group.append(item)

    data = {"filter": filter_meta, "by_measurement_group": by_group}
    if can_cost:
        data["total_cost"] = int(total_cost)
    return data


def _chemicals_stock(
    db, dept, measurement_group, chemical_id, can_cost, filter_meta
) -> dict:
    """Tồn hiện tại tổng hợp theo nhóm đo (SUM qty_base các lô). Không phụ thuộc kỳ."""
    q = (
        select(
            Chemical.measurement_group,
            Chemical.base_unit,
            func.coalesce(func.sum(ChemicalLot.qty_base), 0),
        )
        .select_from(Chemical)
        .outerjoin(ChemicalLot, ChemicalLot.chemical_id == Chemical.id)
        .where(Chemical.status == "active")
        .group_by(Chemical.measurement_group, Chemical.base_unit)
    )
    if dept:
        q = q.where(Chemical.department_id == dept)
    if measurement_group:
        q = q.where(Chemical.measurement_group == measurement_group)
    if chemical_id:
        q = q.where(Chemical.id == chemical_id)
    rows = db.execute(q).all()
    by_group = [
        {
            "measurement_group": mgroup,
            "base_unit": base_unit,
            "total_qty": float(Decimal(qty)),
        }
        for mgroup, base_unit, qty in rows
    ]
    return {"filter": filter_meta, "by_measurement_group": by_group}
