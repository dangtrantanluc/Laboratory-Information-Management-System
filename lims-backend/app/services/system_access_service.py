"""System-access service (M6.3 / R15) — thống kê truy cập hệ thống (#10, #11).

Nguồn đếm cố định (BR-RPT-004 / CONSTRAINT-4):
- Lượt truy cập = access_stats (event_type IN login,page_view). Login đếm từ access_stats
  (event_type='login') — KHÔNG đếm thêm audit LOGIN để tránh trùng (chốt dev §6).
- Lượt tải   = document_access_log.action='download'.
- Lượt chỉnh sửa = action CUD trong audit_logs (loại trừ LOGIN/read/download/export).

CHỈ admin/leader (quyền audit:read, BR-RPT-010) — enforce ở router. Cache 60s (#10).
"""
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.models.access_stat import AccessStat
from app.models.audit_log import AuditLog
from app.models.document import DocumentAccessLog
from app.services import report_common as rc

VALID_ACTION_TYPES = ("access", "download", "edit", "all")

# Action audit KHÔNG tính là "chỉnh sửa" (CUD) — login/logout/token/download/export/view
# (BR-RPT-004). Đếm edit = mọi audit action NGOẠI TRỪ các action non-CUD này.
_NON_EDIT_PREFIXES = ("AUTH_",)
_NON_EDIT_CONTAINS = ("DOWNLOAD", "EXPORT", "_VIEW", "STATS_EXPORT")


def _is_edit_action(action: str) -> bool:
    a = action.upper()
    if a.startswith(_NON_EDIT_PREFIXES):  # AUTH_* (login/logout/token/refresh)
        return False
    for token in _NON_EDIT_CONTAINS:
        if token in a:
            return False
    return True


# ======================= #10: thống kê truy cập hệ thống =======================
def system_access(
    db: Session,
    *,
    user: CurrentUser,
    date_from,
    date_to,
    group_by: str,
    filter_user_id: Optional[uuid.UUID],
    action_type: str,
    top_n: int,
    include_timeline: bool,
) -> tuple[dict, dict]:
    rc.validate_group_by(group_by)
    if action_type not in VALID_ACTION_TYPES:
        raise rc.err("VALIDATION_ERROR", "action_type chỉ nhận access|download|edit|all")
    if top_n < 1 or top_n > 50:
        raise rc.err("VALIDATION_ERROR", "top_n trong khoảng 1..50")
    if filter_user_id is not None:
        rc.get_user_or_404(db, filter_user_id)

    d_from, d_to = rc.resolve_range(date_from, date_to)
    dt_from, dt_to = rc.range_to_dt(d_from, d_to)

    ckey = rc.cache_key(
        "system_access", user, None,
        {
            "from": d_from, "to": d_to, "group_by": group_by,
            "user_id": filter_user_id, "action_type": action_type,
            "top_n": top_n, "timeline": include_timeline,
        },
    )
    cached = rc.cache_get(ckey)
    if cached is not None:
        return cached, rc.aggregate_meta(
            cached=True, extra={"from": d_from.isoformat(), "to": d_to.isoformat()}
        )

    want = lambda t: action_type == "all" or action_type == t

    totals = {"access_count": 0, "download_count": 0, "edit_count": 0}
    top_users: dict = {}

    if want("access"):
        totals["access_count"] = _count_access(db, dt_from, dt_to, filter_user_id)
        top_users["access"] = _top_access(db, dt_from, dt_to, filter_user_id, top_n)
    if want("download"):
        totals["download_count"] = _count_download(db, dt_from, dt_to, filter_user_id)
        top_users["download"] = _top_download(db, dt_from, dt_to, filter_user_id, top_n)
    if want("edit"):
        totals["edit_count"] = _count_edit(db, dt_from, dt_to, filter_user_id)
        top_users["edit"] = _top_edit(db, dt_from, dt_to, filter_user_id, top_n)

    data: dict = {
        "filter": {"from": d_from.isoformat(), "to": d_to.isoformat()},
        "totals": totals,
        "breakdown_definition": {
            "access_count": "access_stats (page_view + login)",
            "download_count": "document_access_log action=download",
            "edit_count": "audit_logs actions create/update/delete (exclude login/read/download/export)",
        },
        "top_users": top_users,
    }
    if include_timeline:
        data["timeline"] = _timeline(db, dt_from, dt_to, group_by, filter_user_id, want)

    rc.cache_set(ckey, data)
    return data, rc.aggregate_meta(
        cached=False, extra={"from": d_from.isoformat(), "to": d_to.isoformat()}
    )


# ---------------- counters ----------------
def _count_access(db, dt_from, dt_to, uid) -> int:
    conds = [AccessStat.at >= dt_from, AccessStat.at < dt_to]
    if uid:
        conds.append(AccessStat.user_id == uid)
    return db.execute(
        select(func.count()).select_from(AccessStat).where(*conds)
    ).scalar_one()


def _count_download(db, dt_from, dt_to, uid) -> int:
    conds = [
        DocumentAccessLog.action == "download",
        DocumentAccessLog.at >= dt_from,
        DocumentAccessLog.at < dt_to,
    ]
    if uid:
        conds.append(DocumentAccessLog.user_id == uid)
    return db.execute(
        select(func.count()).select_from(DocumentAccessLog).where(*conds)
    ).scalar_one()


def _count_edit(db, dt_from, dt_to, uid) -> int:
    conds = [AuditLog.at >= dt_from, AuditLog.at < dt_to]
    if uid:
        conds.append(AuditLog.user_id == uid)
    # đếm theo action rồi lọc CUD ở app-layer (action names mô tả; KHÔNG hardcode SQL list)
    rows = db.execute(
        select(AuditLog.action, func.count()).where(*conds).group_by(AuditLog.action)
    ).all()
    return sum(c for action, c in rows if _is_edit_action(action))


# ---------------- top users ----------------
def _top_access(db, dt_from, dt_to, uid, top_n) -> list[dict]:
    conds = [AccessStat.at >= dt_from, AccessStat.at < dt_to, AccessStat.user_id.isnot(None)]
    if uid:
        conds.append(AccessStat.user_id == uid)
    rows = db.execute(
        select(AccessStat.user_id, func.count().label("c"))
        .where(*conds)
        .group_by(AccessStat.user_id)
        .order_by(func.count().desc())
        .limit(top_n)
    ).all()
    return [_user_count(db, u, c) for u, c in rows]


def _top_download(db, dt_from, dt_to, uid, top_n) -> list[dict]:
    conds = [
        DocumentAccessLog.action == "download",
        DocumentAccessLog.at >= dt_from,
        DocumentAccessLog.at < dt_to,
    ]
    if uid:
        conds.append(DocumentAccessLog.user_id == uid)
    rows = db.execute(
        select(DocumentAccessLog.user_id, func.count())
        .where(*conds)
        .group_by(DocumentAccessLog.user_id)
        .order_by(func.count().desc())
        .limit(top_n)
    ).all()
    return [_user_count(db, u, c) for u, c in rows]


def _top_edit(db, dt_from, dt_to, uid, top_n) -> list[dict]:
    conds = [AuditLog.at >= dt_from, AuditLog.at < dt_to, AuditLog.user_id.isnot(None)]
    if uid:
        conds.append(AuditLog.user_id == uid)
    rows = db.execute(
        select(AuditLog.user_id, AuditLog.action, func.count())
        .where(*conds)
        .group_by(AuditLog.user_id, AuditLog.action)
    ).all()
    agg: dict = {}
    for u, action, c in rows:
        if _is_edit_action(action):
            agg[u] = agg.get(u, 0) + c
    ordered = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return [_user_count(db, u, c) for u, c in ordered]


def _user_count(db, user_id, count) -> dict:
    return {
        "user_id": str(user_id),
        "user_name": rc.user_name(db, user_id),
        "count": count,
    }


# ---------------- timeline ----------------
def _timeline(db, dt_from, dt_to, group_by, uid, want) -> list[dict]:
    buckets: dict = {}

    def _b(key):
        return buckets.setdefault(
            key, {"period": key, "access_count": 0, "download_count": 0, "edit_count": 0}
        )

    if want("access"):
        conds = [AccessStat.at >= dt_from, AccessStat.at < dt_to]
        if uid:
            conds.append(AccessStat.user_id == uid)
        for (at,) in db.execute(select(AccessStat.at).where(*conds)):
            _b(rc.period_key(at, group_by))["access_count"] += 1
    if want("download"):
        conds = [
            DocumentAccessLog.action == "download",
            DocumentAccessLog.at >= dt_from,
            DocumentAccessLog.at < dt_to,
        ]
        if uid:
            conds.append(DocumentAccessLog.user_id == uid)
        for (at,) in db.execute(select(DocumentAccessLog.at).where(*conds)):
            _b(rc.period_key(at, group_by))["download_count"] += 1
    if want("edit"):
        conds = [AuditLog.at >= dt_from, AuditLog.at < dt_to]
        if uid:
            conds.append(AuditLog.user_id == uid)
        for at, action in db.execute(select(AuditLog.at, AuditLog.action).where(*conds)):
            if _is_edit_action(action):
                _b(rc.period_key(at, group_by))["edit_count"] += 1

    return [buckets[k] for k in sorted(buckets.keys())]


# ======================= #11: chi tiết 1 user =======================
def user_detail(
    db: Session,
    *,
    user: CurrentUser,
    target_user_id: uuid.UUID,
    date_from,
    date_to,
    recent_actions: int,
) -> tuple[dict, dict]:
    target = rc.get_user_or_404(db, target_user_id)
    if recent_actions < 1 or recent_actions > 100:
        raise rc.err("VALIDATION_ERROR", "recent_actions trong khoảng 1..100")

    d_from, d_to = rc.resolve_range(date_from, date_to)
    dt_from, dt_to = rc.range_to_dt(d_from, d_to)

    totals = {
        "access_count": _count_access(db, dt_from, dt_to, target_user_id),
        "download_count": _count_download(db, dt_from, dt_to, target_user_id),
        "edit_count": _count_edit(db, dt_from, dt_to, target_user_id),
    }

    recent_rows = db.execute(
        select(AuditLog)
        .where(
            AuditLog.user_id == target_user_id,
            AuditLog.at >= dt_from,
            AuditLog.at < dt_to,
        )
        .order_by(AuditLog.at.desc())
        .limit(recent_actions)
    ).scalars().all()
    recent = [
        {
            "at": r.at.isoformat(),
            "action": r.action,
            "resource": r.resource,
            "resource_id": str(r.resource_id) if r.resource_id else None,
            "correlation_id": r.correlation_id,
        }
        for r in recent_rows
    ]

    data = {
        "user": {
            "id": str(target.id),
            "name": target.full_name,
            "role": target.role,
            "department_name": rc.dept_name(db, target.department_id),
        },
        "filter": {"from": d_from.isoformat(), "to": d_to.isoformat()},
        "totals": totals,
        "recent_actions": recent,
    }
    return data, rc.aggregate_meta(cached=False)
