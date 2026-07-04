"""Dashboard service (M6.1) — KPI tổng hợp chéo module + biểu đồ (FR-RPT-001/002/006).

Đọc TRỰC TIẾP bảng module nguồn (ASSUMPTION-1) để gom KPI 1 round-trip; KHÔNG gọi lại
logic on-time/tiêu hao của module gốc (CONSTRAINT-1). Áp scope theo vai trò (BR-RPT-001):
- admin/leader: toàn hệ thống, mọi khối KPI.
- accountant: CHỈ tài chính (chemicals có tiền + hr); KHÔNG khối samples/equipments/documents (B03).
- staff: phòng mình; KHÔNG field tiền; KHÔNG khối hr.

Degrade mềm (BR-RPT-013): 1 khối lỗi → {available:false}, HTTP vẫn 200, khối khác đúng.
Cache Redis 60s (BR-RPT-011).
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.models.chemical import Chemical, ChemicalLot, ChemicalTransaction
from app.models.document import DocumentVersion
from app.models.equipment import Equipment
from app.models.hr import HrProfile
from app.models.notification import Notification
from app.models.sample import Sample, VALID_SAMPLE_STATUS
from app.services import report_common as rc

logger = logging.getLogger("lims.dashboard")


# ---------------- KPI khối: mẫu (M1) ----------------
def _kpi_samples(db: Session, dept: Optional[uuid.UUID]) -> dict:
    conditions = [Sample.deleted_at.is_(None)]
    if dept:
        conditions.append(Sample.department_id == dept)
    rows = db.execute(
        select(Sample.status, func.count())
        .where(*conditions)
        .group_by(Sample.status)
    ).all()
    by_status = {s: 0 for s in VALID_SAMPLE_STATUS}
    total = 0
    for status_val, cnt in rows:
        by_status[status_val] = cnt
        total += cnt
    overdue = by_status.get("overdue", 0)
    deep = "/samples?status=overdue"
    if dept:
        deep += f"&department_id={dept}"
    return {
        "available": True,
        "by_status": by_status,
        "total": total,
        "overdue": overdue,
        "deep_link": deep,
    }


# ---------------- KPI khối: hóa chất (M2) ----------------
def _kpi_chemicals(
    db: Session, dept: Optional[uuid.UUID], due_days: int, can_cost: bool
) -> dict:
    today = datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=due_days)

    # join lot → chemical để áp scope phòng (chemicals.department_id)
    def _lot_base(*extra):
        q = (
            select(func.count(func.distinct(ChemicalLot.id)))
            .select_from(ChemicalLot)
            .join(Chemical, Chemical.id == ChemicalLot.chemical_id)
            .where(Chemical.status == "active", *extra)
        )
        if dept:
            q = q.where(Chemical.department_id == dept)
        return q

    expiring_soon = db.execute(
        _lot_base(
            ChemicalLot.expiry_date.isnot(None),
            ChemicalLot.expiry_date >= today,
            ChemicalLot.expiry_date <= horizon,
        )
    ).scalar_one()
    recheck_due = db.execute(
        _lot_base(
            ChemicalLot.recheck_date.isnot(None),
            ChemicalLot.recheck_date >= today,
            ChemicalLot.recheck_date <= horizon,
        )
    ).scalar_one()

    # low_stock: SUM(qty_base) theo chemical < reorder_threshold (chỉ chemical có threshold)
    stock_rows = db.execute(
        select(
            Chemical.id,
            Chemical.reorder_threshold,
            func.coalesce(func.sum(ChemicalLot.qty_base), 0),
        )
        .select_from(Chemical)
        .outerjoin(ChemicalLot, ChemicalLot.chemical_id == Chemical.id)
        .where(
            Chemical.status == "active",
            Chemical.reorder_threshold.isnot(None),
            *( [Chemical.department_id == dept] if dept else [] ),
        )
        .group_by(Chemical.id, Chemical.reorder_threshold)
    ).all()
    low_stock = sum(
        1 for _cid, thr, qty in stock_rows if Decimal(qty) < Decimal(thr)
    )

    block: dict = {
        "available": True,
        "expiring_soon": expiring_soon,
        "recheck_due": recheck_due,
        "low_stock": low_stock,
        "deep_link_expiring": f"/inventory/expiring?within_days={due_days}",
        "deep_link_low_stock": "/inventory/low-stock",
    }
    if can_cost:
        # chi phí tiêu hao tháng hiện tại (vai trò tài chính)
        d_from, d_to = rc.default_period()
        dt_from, dt_to = rc.range_to_dt(d_from, d_to)
        cost_q = (
            select(
                func.coalesce(
                    func.sum(
                        ChemicalTransaction.qty_input
                        * func.coalesce(ChemicalTransaction.unit_price, 0)
                    ),
                    0,
                )
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
            cost_q = cost_q.where(Chemical.department_id == dept)
        block["consumption_cost_month"] = int(db.execute(cost_q).scalar_one())
    return block


# ---------------- KPI khối: thiết bị (M5) ----------------
def _kpi_equipments(db: Session, dept: Optional[uuid.UUID], due_days: int) -> dict:
    today = datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=due_days)
    base = [
        Equipment.deleted_at.is_(None),
        Equipment.next_due_date.isnot(None),
        Equipment.status != "retired",
    ]
    if dept:
        base.append(Equipment.department_id == dept)
    overdue = db.execute(
        select(func.count()).select_from(Equipment).where(
            *base, Equipment.next_due_date < today
        )
    ).scalar_one()
    due_soon = db.execute(
        select(func.count()).select_from(Equipment).where(
            *base, Equipment.next_due_date >= today, Equipment.next_due_date <= horizon
        )
    ).scalar_one()
    deep = "/equipments/calibration-due"
    if dept:
        deep += f"?department_id={dept}"
    return {
        "available": True,
        "calibration_overdue": overdue,
        "calibration_due_soon": due_soon,
        "deep_link": deep,
    }


# ---------------- KPI khối: nhân sự (M4) — chỉ vai trò tài chính/HR ----------------
def _kpi_hr(db: Session, due_days: int) -> dict:
    today = datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=due_days)
    salary_due = db.execute(
        select(func.count()).select_from(HrProfile).where(
            HrProfile.next_salary_raise_date.isnot(None),
            HrProfile.next_salary_raise_date >= today,
            HrProfile.next_salary_raise_date <= horizon,
        )
    ).scalar_one()
    contract_ending = db.execute(
        select(func.count()).select_from(HrProfile).where(
            HrProfile.contract_end_date.isnot(None),
            HrProfile.contract_end_date >= today,
            HrProfile.contract_end_date <= horizon,
        )
    ).scalar_one()
    return {
        "available": True,
        "salary_raise_due": salary_due,
        "contract_ending": contract_ending,
        "deep_link": "/hr/profiles?alert=upcoming",
    }


# ---------------- KPI khối: tài liệu (M3) ----------------
def _kpi_documents(db: Session) -> dict:
    pending = db.execute(
        select(func.count()).select_from(DocumentVersion).where(
            DocumentVersion.status == "review",
            DocumentVersion.deleted_at.is_(None),
        )
    ).scalar_one()
    return {
        "available": True,
        "pending_review": pending,
        "deep_link": "/documents?status=review",
    }


# ---------------- KPI khối: thông báo (M7, user hiện tại) ----------------
def _kpi_notifications(db: Session, user_id: uuid.UUID) -> dict:
    unread = db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
    ).scalar_one()
    return {
        "available": True,
        "unread": unread,
        "deep_link": "/notifications?read=false",
    }


def _safe(fn, label: str):
    """Degrade mềm (BR-RPT-013/AC4): khối lỗi → available:false, KHÔNG fail dashboard."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        logger.error("dashboard block failed", extra={"block": label, "error": str(exc)})
        return {"available": False, "error": "Tạm thời không khả dụng"}


# ======================= ENTRYPOINT: dashboard =======================
def get_dashboard(
    db: Session,
    *,
    user: CurrentUser,
    department_id: Optional[uuid.UUID],
    due_within_days: int,
) -> tuple[dict, dict]:
    """Trả (data, meta). Áp scope vai trò + cache 60s. Caller bọc ok()."""
    dept = rc.resolve_scope_department(db, user, department_id)
    can_cost = rc.can_see_cost(db, user)

    ckey = rc.cache_key(
        "dashboard", user, dept, {"due": due_within_days}
    )
    cached = rc.cache_get(ckey)
    if cached is not None:
        return cached, rc.aggregate_meta(cached=True)

    scope = {
        "role": user.role,
        "department_id": str(dept) if dept else None,
        "department_name": rc.dept_name(db, dept),
    }
    data: dict = {"scope": scope}

    if rc.is_accountant(user):
        # B03: accountant CHỈ tài chính — KHÔNG khối samples/equipments/documents.
        data["chemicals"] = _safe(
            lambda: _kpi_chemicals(db, dept, due_within_days, can_cost), "chemicals"
        )
        data["hr"] = _safe(lambda: _kpi_hr(db, due_within_days), "hr")
        data["notifications"] = _safe(
            lambda: _kpi_notifications(db, user.id), "notifications"
        )
    else:
        data["samples"] = _safe(lambda: _kpi_samples(db, dept), "samples")
        data["chemicals"] = _safe(
            lambda: _kpi_chemicals(db, dept, due_within_days, can_cost), "chemicals"
        )
        data["equipments"] = _safe(
            lambda: _kpi_equipments(db, dept, due_within_days), "equipments"
        )
        if not rc.is_staff_forced(user):
            # KPI nhân sự chỉ vai trò tài chính/HR (admin/leader) — staff KHÔNG (BR-RPT-007).
            data["hr"] = _safe(lambda: _kpi_hr(db, due_within_days), "hr")
        data["documents"] = _safe(lambda: _kpi_documents(db), "documents")
        data["notifications"] = _safe(
            lambda: _kpi_notifications(db, user.id), "notifications"
        )

    # strip field tiền nếu staff (BR-RPT-002) — chemicals.consumption_cost_month
    data = rc.strip_price_fields(data, can_cost)
    rc.cache_set(ckey, data)
    return data, rc.aggregate_meta(cached=False)


# ======================= ENTRYPOINT: charts =======================
def get_charts(
    db: Session,
    *,
    user: CurrentUser,
    date_from,
    date_to,
    department_id: Optional[uuid.UUID],
    group_by: str,
    charts: Optional[list[str]],
) -> tuple[dict, dict]:
    rc.validate_group_by(group_by)
    d_from, d_to = rc.resolve_range(date_from, date_to)
    dept = rc.resolve_scope_department(db, user, department_id)
    can_cost = rc.can_see_cost(db, user)

    requested = set(charts) if charts else None
    accountant = rc.is_accountant(user)

    # accountant xin chart mẫu → 403 (B03, AC3 FR-RPT-002)
    if accountant and requested and (
        "samples_by_status" in requested or "samples_over_time" in requested
    ):
        raise rc.forbidden("Kế toán không được xem biểu đồ mẫu (B03)")

    ckey = rc.cache_key(
        "charts", user, dept,
        {
            "from": d_from, "to": d_to, "group_by": group_by,
            "charts": ",".join(sorted(requested)) if requested else "all",
        },
    )
    cached = rc.cache_get(ckey)
    if cached is not None:
        return cached, rc.aggregate_meta(
            cached=True, extra={"from": d_from.isoformat(), "to": d_to.isoformat()}
        )

    data: dict = {}
    want = lambda name: (requested is None or name in requested)

    if not accountant and want("samples_by_status"):
        data["samples_by_status"] = _safe(
            lambda: _chart_samples_by_status(db, dept), "samples_by_status"
        )
    if not accountant and want("samples_over_time"):
        data["samples_over_time"] = _safe(
            lambda: _chart_samples_over_time(db, dept, d_from, d_to, group_by),
            "samples_over_time",
        )
    if want("chemical_consumption"):
        data["chemical_consumption"] = _safe(
            lambda: _chart_chemical_consumption(
                db, dept, d_from, d_to, group_by, can_cost
            ),
            "chemical_consumption",
        )

    data = rc.strip_price_fields(data, can_cost)
    rc.cache_set(ckey, data)
    return data, rc.aggregate_meta(
        cached=False, extra={"from": d_from.isoformat(), "to": d_to.isoformat()}
    )


def _chart_samples_by_status(db: Session, dept: Optional[uuid.UUID]) -> dict:
    conditions = [Sample.deleted_at.is_(None)]
    if dept:
        conditions.append(Sample.department_id == dept)
    rows = db.execute(
        select(Sample.status, func.count()).where(*conditions).group_by(Sample.status)
    ).all()
    return {
        "available": True,
        "data": [{"status": s, "count": c} for s, c in rows],
    }


def _chart_samples_over_time(
    db: Session, dept: Optional[uuid.UUID], d_from, d_to, group_by: str
) -> dict:
    dt_from, dt_to = rc.range_to_dt(d_from, d_to)
    conditions = [
        Sample.deleted_at.is_(None),
        Sample.received_at >= dt_from,
        Sample.received_at < dt_to,
    ]
    if dept:
        conditions.append(Sample.department_id == dept)
    rows = db.execute(
        select(Sample.received_at).where(*conditions)
    ).scalars().all()
    buckets: dict[str, int] = {}
    for at in rows:
        key = rc.period_key(at, group_by)
        buckets[key] = buckets.get(key, 0) + 1
    return {
        "available": True,
        "group_by": group_by,
        "metric": "received_at",
        "data": [
            {"period": k, "count": buckets[k]} for k in sorted(buckets.keys())
        ],
    }


def _chart_chemical_consumption(
    db: Session, dept: Optional[uuid.UUID], d_from, d_to, group_by: str, can_cost: bool
) -> dict:
    dt_from, dt_to = rc.range_to_dt(d_from, d_to)
    q = (
        select(
            ChemicalTransaction.at,
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
    rows = db.execute(q).all()

    # groups[measurement_group] = {base_unit, periods{key:{qty,cost}}}
    groups: dict = {}
    for at, qty_base, qty_input, unit_price, mgroup, base_unit in rows:
        g = groups.setdefault(mgroup, {"base_unit": base_unit, "periods": {}})
        key = rc.period_key(at, group_by)
        cell = g["periods"].setdefault(key, {"qty": Decimal("0"), "cost": Decimal("0")})
        cell["qty"] += Decimal(qty_base)
        if unit_price is not None:
            cell["cost"] += Decimal(qty_input) * Decimal(unit_price)

    out = []
    for mgroup in sorted(groups.keys()):
        g = groups[mgroup]
        points = []
        for key in sorted(g["periods"].keys()):
            cell = g["periods"][key]
            point = {"period": key, "qty": float(cell["qty"])}
            if can_cost:
                point["cost"] = int(cell["cost"])
            points.append(point)
        out.append(
            {
                "measurement_group": mgroup,
                "base_unit": g["base_unit"],
                "data": points,
            }
        )
    return {"available": True, "group_by": group_by, "by_measurement_group": out}
