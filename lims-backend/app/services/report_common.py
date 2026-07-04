"""M6 common helpers — Báo cáo & Thống kê (Reporting & Analytics).

Tập trung logic dùng chung cho mọi service M6:
- RBAC scope theo vai trò (BR-RPT-001/002/010): staff ép phòng mình; accountant không
  mẫu (B03); field tiền chỉ vai trò tài chính; R15 chỉ admin/leader.
- Bộ lọc thời gian thống nhất `[from, to)` nửa mở (BR-RPT-009, CONSTRAINT-5).
- Phân rã thời gian (day/week/month) cho line/bar chart.
- Cache dashboard 60s Redis (BR-RPT-011); key gồm role+scope+filter → KHÔNG rò rỉ scope.

READ-ONLY aggregate: M6 KHÔNG sửa dữ liệu nghiệp vụ. Ngoại lệ ghi = access_stats
(middleware/#14) + audit REPORT_EXPORT (export).
"""
import hashlib
import json
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.core.rbac import has_permission
from app.core.redis_client import get_redis
from app.models.department import Department
from app.models.user import User

logger = logging.getLogger("lims.report")

CACHE_TTL_SECONDS = 60  # BR-RPT-011 / §0.8
VALID_GROUP_BY = ("day", "week", "month")

# Cột tiền bị strip với vai trò KHÔNG có chemical:cost (BR-RPT-002, đồng bộ M2)
PRICE_FIELDS = frozenset(
    {
        "consumption_cost",
        "consumption_cost_month",
        "total_cost",
        "cost",
        "unit_price",
        "currency",
        "stock_value",
    }
)


# ===== Error factories (đồng bộ danh mục error code §3 contract) =====
def err(code: str, message: str, http: int = 400, details=None) -> AppException:
    return AppException(code, message, http, details)


def forbidden(message: str = "Bạn không có quyền thực hiện thao tác này") -> AppException:
    return AppException("FORBIDDEN", message, 403)


def invalid_date_range() -> AppException:
    return AppException("INVALID_DATE_RANGE", "from phải nhỏ hơn to", 422)


def invalid_group_by() -> AppException:
    return AppException("INVALID_GROUP_BY", "group_by chỉ nhận day|week|month", 422)


# ===== RBAC =====
def is_privileged(user: CurrentUser) -> bool:
    """Admin / Ban lãnh đạo = toàn hệ thống (bỏ qua scope phòng)."""
    return user.role in ("admin", "leader")


def is_accountant(user: CurrentUser) -> bool:
    return user.role == "accountant"


def can_see_cost(db: Session, user: CurrentUser) -> bool:
    """Vai trò tài chính (admin/leader/accountant) — quyền chemical:cost (BR-RPT-002)."""
    return has_permission(db, user.role, "chemical", "cost")


def deny_accountant_samples(user: CurrentUser) -> None:
    """Endpoint chuyên về mẫu (#3, export samples): accountant → 403 (B03)."""
    if is_accountant(user):
        raise forbidden("Kế toán không được truy cập báo cáo mẫu/kết quả (B03)")


def require_audit_read(db: Session, user: CurrentUser) -> None:
    """R15 (thống kê truy cập hệ thống): chỉ admin/leader (quyền audit:read, BR-RPT-010)."""
    if not has_permission(db, user.role, "audit", "read"):
        raise forbidden("Chỉ Admin/Lãnh đạo được xem thống kê truy cập hệ thống (R15)")


def resolve_scope_department(
    db: Session, user: CurrentUser, requested: Optional[uuid.UUID]
) -> Optional[uuid.UUID]:
    """Phạm vi đếm theo phòng (BR-RPT-001):
    - admin/leader/accountant: theo yêu cầu (None = toàn hệ thống). Validate tồn tại.
    - staff: ÉP về phòng mình (KHÔNG 403 dù truyền phòng khác — AC4 FR-RPT-005).
    """
    if requested is not None and not is_staff_forced(user):
        if db.get(Department, requested) is None:
            raise AppException(
                "DEPARTMENT_NOT_FOUND", "Phòng ban không tồn tại", 404
            )
        return requested
    if is_staff_forced(user):
        return user.department_id  # ép phòng mình; có thể None nếu user chưa có phòng
    return None  # toàn hệ thống


def is_staff_forced(user: CurrentUser) -> bool:
    """staff (KTV) bị ép scope phòng. admin/leader/accountant không bị ép."""
    return user.role == "staff"


# ===== Bộ lọc thời gian thống nhất [from, to) (BR-RPT-009) =====
def default_period() -> tuple[date, date]:
    """Bộ lọc rỗng → tháng hiện tại [đầu tháng, đầu tháng kế tiếp) (OQ#9)."""
    today = datetime.now(timezone.utc).date()
    start = today.replace(day=1)
    if start.month == 12:
        nxt = start.replace(year=start.year + 1, month=1)
    else:
        nxt = start.replace(month=start.month + 1)
    return start, nxt


def resolve_range(
    date_from: Optional[date], date_to: Optional[date]
) -> tuple[date, date]:
    """Chuẩn hóa [from, to) nửa mở. Rỗng → tháng hiện tại. from >= to → 422."""
    if date_from is None and date_to is None:
        return default_period()
    if date_from is None or date_to is None:
        d_def = default_period()
        date_from = date_from or d_def[0]
        date_to = date_to or d_def[1]
    if date_from >= date_to:
        raise invalid_date_range()
    return date_from, date_to


def range_to_dt(d_from: date, d_to: date) -> tuple[datetime, datetime]:
    """date → datetime biên [00:00 from, 00:00 to) cho cột TIMESTAMPTZ.

    Bản ghi đúng 00:00 from được TÍNH; đúng 00:00 to bị LOẠI (NFR-CONSISTENCY-RPT-001).
    """
    dt_from = datetime(d_from.year, d_from.month, d_from.day, tzinfo=timezone.utc)
    dt_to = datetime(d_to.year, d_to.month, d_to.day, tzinfo=timezone.utc)
    return dt_from, dt_to


def validate_group_by(group_by: str) -> str:
    if group_by not in VALID_GROUP_BY:
        raise invalid_group_by()
    return group_by


def period_key(dt: datetime, group_by: str) -> str:
    """Khóa kỳ cho phân rã thời gian (line/bar)."""
    if group_by == "day":
        return dt.strftime("%Y-%m-%d")
    if group_by == "week":
        iso = dt.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    return dt.strftime("%Y-%m")  # month


def date_period_key(d: date, group_by: str) -> str:
    if group_by == "day":
        return d.strftime("%Y-%m-%d")
    if group_by == "week":
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    return d.strftime("%Y-%m")


# ===== Field tiền (strip cho staff) =====
def strip_price_fields(data, can_cost: bool):
    """Strip mọi key tiền nếu user KHÔNG có quyền cost (BR-RPT-002). Đệ quy, không mutate."""
    if can_cost:
        return data
    if isinstance(data, list):
        return [strip_price_fields(x, can_cost) for x in data]
    if isinstance(data, dict):
        return {
            k: strip_price_fields(v, can_cost)
            for k, v in data.items()
            if k not in PRICE_FIELDS
        }
    return data


# ===== Helpers tra cứu tên =====
def user_name(db: Session, user_id: Optional[uuid.UUID]) -> Optional[str]:
    if user_id is None:
        return None
    u = db.get(User, user_id)
    return u.full_name if u else None


def dept_name(db: Session, dept_id: Optional[uuid.UUID]) -> Optional[str]:
    if dept_id is None:
        return None
    d = db.get(Department, dept_id)
    return d.name if d else None


def get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise AppException("USER_NOT_FOUND", "Người dùng không tồn tại", 404)
    return u


# ===== Meta cho response aggregate =====
def aggregate_meta(*, cached: bool, extra: Optional[dict] = None) -> dict:
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cached": cached,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
    }
    if extra:
        meta.update(extra)
    return meta


# ===== Cache dashboard/aggregate (Redis 60s — BR-RPT-011, §0.8) =====
def cache_key(endpoint: str, user: CurrentUser, scope_dept, parts: dict) -> str:
    """Key gồm vai trò + scope phòng + bộ lọc → KHÔNG dùng chung cache giữa vai trò."""
    payload = {
        "role": user.role,
        "dept": str(scope_dept) if scope_dept else "all",
        **{k: (str(v) if v is not None else None) for k, v in sorted(parts.items())},
    }
    digest = hashlib.sha1(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return f"report:{endpoint}:{digest}"


def cache_get(key: str) -> Optional[dict]:
    try:
        raw = get_redis().get(key)
        if raw:
            return json.loads(raw)
    except Exception as exc:  # noqa: BLE001 — cache lỗi không chặn nghiệp vụ
        logger.warning("report cache read failed: %s", exc)
    return None


def cache_set(key: str, value: dict) -> None:
    try:
        get_redis().setex(key, CACHE_TTL_SECONDS, json.dumps(value, default=str))
    except Exception as exc:  # noqa: BLE001
        logger.warning("report cache write failed: %s", exc)
