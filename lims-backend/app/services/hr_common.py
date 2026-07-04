"""M4 common helpers — field-level RBAC strip (lương/HĐ/PII), tính lương & ngày nâng
lương (Decimal + relativedelta), scope research, error factories, parse decimal.

Field-level RBAC (BR-HR-002/003, NFR-SEC-HR-001 — CỐT LÕI, đồng bộ M2 strip giá):
strip theo (role, item.user_id == current_user.id). Phức tạp hơn M2 một bậc: staff
xem được lương/HĐ/PII CỦA CHÍNH MÌNH. 3 nhóm strip độc lập:
  - SALARY: admin/leader/accountant đọc mọi người; staff chỉ của mình.
  - CONTRACT: admin/leader/accountant đọc mọi người; staff chỉ của mình.
  - PII: chỉ admin/accountant + chính chủ (leader KHÔNG xem PII).

Quyền SỬA lương/HĐ = chỉ admin + accountant (QUYẾT ĐỊNH #1). Leader chỉ XEM.

NUMERIC không float — Decimal xuyên suốt; JSON trả string (giữ precision).
"""
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException

# ===== Nhóm field strip theo quyền (BR-HR-002/003, contract §0.6/§0.7) =====
SALARY_FIELDS = frozenset(
    {
        "salary_grade",
        "salary_coefficient",
        "base_salary_amount",
        "computed_salary_amount",
        "currency",
        "salary_history",
        "next_salary_raise_date",
        "last_salary_raise_date",
        "salary_cycle_years",
    }
)
CONTRACT_FIELDS = frozenset(
    {"contract_type", "contract_signed_date", "contract_end_date"}
)
# PII: schema M4 hiện chỉ có 'phone' (không nhạy cảm cao). id_number/dob/bank_account
# CHƯA thêm cột (contract §8.6 — chờ KH chốt). Giữ tập sẵn để áp khi ALTER thêm cột.
PII_FIELDS = frozenset({"id_number", "dob", "bank_account"})

_Q_COEFF = Decimal("0.01")  # NUMERIC(6,2)
_Q_MONEY = Decimal("0.01")  # NUMERIC(14,2)


# ===== Error factories (đồng bộ danh mục error code §3 contract) =====
def err(code: str, message: str, http: int = 400, details=None) -> AppException:
    return AppException(code, message, http, details)


def forbidden(message: str = "Bạn không có quyền thực hiện thao tác này") -> AppException:
    return AppException("FORBIDDEN", message, 403)


def salary_forbidden() -> AppException:
    return AppException(
        "SALARY_FORBIDDEN",
        "Bạn không có quyền điều chỉnh lương/hợp đồng. Chỉ Kế toán và Quản trị viên "
        "được thực hiện.",
        403,
        [{"field": "salary", "required_roles": ["admin", "accountant"]}],
    )


# ===== RBAC field-level — quyết định strip theo (role, of_self) =====
def can_read_salary(user: CurrentUser, target_user_id: uuid.UUID) -> bool:
    """Đọc lương: admin/leader/accountant (toàn HT) HOẶC chính chủ (staff của mình)."""
    if user.role in ("admin", "leader", "accountant"):
        return True
    return user.id == target_user_id


def can_read_contract(user: CurrentUser, target_user_id: uuid.UUID) -> bool:
    """Đọc HĐ: như lương (admin/leader/accountant + chính chủ)."""
    return can_read_salary(user, target_user_id)


def can_read_pii(user: CurrentUser, target_user_id: uuid.UUID) -> bool:
    """Đọc PII: chỉ admin/accountant + chính chủ. Leader KHÔNG xem PII."""
    if user.role in ("admin", "accountant"):
        return True
    return user.id == target_user_id


def can_edit_salary(user: CurrentUser) -> bool:
    """Sửa lương/HĐ/chu kỳ = chỉ admin + accountant (QUYẾT ĐỊNH #1)."""
    return user.role in ("admin", "accountant")


def assert_can_edit_salary(user: CurrentUser) -> None:
    if not can_edit_salary(user):
        raise salary_forbidden()


def assert_can_manage_profile(user: CurrentUser) -> None:
    """Tạo/sửa hồ sơ (phi tài chính) = admin + accountant (contract #2/#5)."""
    if user.role not in ("admin", "accountant"):
        raise forbidden("Chỉ Kế toán và Quản trị viên được quản lý hồ sơ nhân sự")


def assert_can_manage_competence(user: CurrentUser) -> None:
    """Tạo/sửa/xóa năng lực = admin + leader (contract #11-14)."""
    if user.role not in ("admin", "leader"):
        raise forbidden("Chỉ Quản trị viên và Ban lãnh đạo được quản lý hồ sơ năng lực")


# ===== Strip dict hồ sơ theo người gọi (item-level, BR-HR-002/003) =====
def strip_profile(item: dict, user: CurrentUser) -> dict:
    """Strip nhóm lương/HĐ/PII khỏi 1 dict hồ sơ theo quyền người gọi.

    item PHẢI có 'user_id' để đánh giá chính chủ. Strip = LOẠI key (không trả null),
    đồng bộ M2. KHÔNG mutate input gốc.
    """
    target = item.get("user_id")
    if isinstance(target, str):
        target = uuid.UUID(target)
    out = dict(item)
    if not can_read_salary(user, target):
        for k in SALARY_FIELDS:
            out.pop(k, None)
    if not can_read_contract(user, target):
        for k in CONTRACT_FIELDS:
            out.pop(k, None)
    if not can_read_pii(user, target):
        for k in PII_FIELDS:
            out.pop(k, None)
    return out


# ===== Tính lương thực & ngày nâng lương kế tiếp =====
def compute_salary_amount(
    coefficient: Optional[Decimal], base: Optional[Decimal]
) -> Optional[Decimal]:
    """Lương thực = hệ số × lương cơ sở (D4). Tính khi hiển thị, KHÔNG lưu cột dẫn xuất."""
    if coefficient is None or base is None:
        return None
    return q_money(Decimal(coefficient) * Decimal(base))


def compute_next_salary_raise_date(
    *,
    last_salary_raise_date,
    contract_signed_date,
    salary_cycle_years: int,
):
    """next = (last_salary_raise_date ?? contract_signed_date) + cycle năm (D9, BR-HR-005).

    relativedelta xử lý cộng-năm an toàn năm nhuận: 29/02 + n năm → 28/02 khi năm đích
    không nhuận. NULL base → None (CRON-3 bỏ qua, BR-HR-010).
    """
    base = last_salary_raise_date or contract_signed_date
    if base is None:
        return None
    return base + relativedelta(years=salary_cycle_years)


# ===== Decimal helpers =====
def parse_decimal(
    value, *, field: str, positive: bool = False, allow_negative: bool = False
) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise err(
            "VALIDATION_ERROR",
            f"Giá trị '{field}' không phải số hợp lệ",
            400,
            [{"field": field, "message": "Không phải số"}],
        )
    if d.is_nan() or d.is_infinite():
        raise err("VALIDATION_ERROR", f"Giá trị '{field}' không hợp lệ", 400)
    if positive and d <= 0:
        raise err(
            "INVALID_SALARY",
            f"Giá trị '{field}' phải lớn hơn 0",
            400,
            [{"field": field, "message": "Phải > 0"}],
        )
    if not allow_negative and not positive and d < 0:
        raise err("VALIDATION_ERROR", f"Giá trị '{field}' không được âm", 400)
    return d


def assert_max_decimals(value: Decimal, *, field: str, places: int) -> None:
    exp = value.as_tuple().exponent
    if isinstance(exp, int) and exp < -places:
        raise err(
            "VALIDATION_ERROR",
            f"'{field}' vượt quá {places} chữ số thập phân",
            400,
            [{"field": field, "message": f"Tối đa {places} chữ số thập phân"}],
        )


def q_money(d: Decimal) -> Decimal:
    return Decimal(d).quantize(_Q_MONEY, rounding=ROUND_HALF_UP)


def q_coeff(d: Decimal) -> Decimal:
    return Decimal(d).quantize(_Q_COEFF, rounding=ROUND_HALF_UP)


def s_money(d: Optional[Decimal]) -> Optional[str]:
    if d is None:
        return None
    return f"{q_money(d):.2f}"


def s_coeff(d: Optional[Decimal]) -> Optional[str]:
    if d is None:
        return None
    return f"{q_coeff(d):.2f}"


# ===== Tra cứu tên =====
def user_name(db: Session, user_id: Optional[uuid.UUID]) -> Optional[str]:
    if user_id is None:
        return None
    from app.models.user import User

    u = db.get(User, user_id)
    return u.full_name if u else None


def user_dept(db: Session, user_id: Optional[uuid.UUID]) -> Optional[uuid.UUID]:
    if user_id is None:
        return None
    from app.models.user import User

    u = db.get(User, user_id)
    return u.department_id if u else None


def dept_name(db: Session, dept_id: Optional[uuid.UUID]) -> Optional[str]:
    if dept_id is None:
        return None
    from app.models.department import Department

    d = db.get(Department, dept_id)
    return d.name if d else None


def assert_user_exists(db: Session, user_id: uuid.UUID) -> None:
    from app.models.user import User

    if db.get(User, user_id) is None:
        raise err("USER_NOT_FOUND", "Người dùng không tồn tại", 404)


# ===== Scope research (BR-HR-023) =====
def assert_research_access(user: CurrentUser) -> None:
    """Kế toán KHÔNG truy cập nhóm NCKH (QUYẾT ĐỊNH #5) → 403 FORBIDDEN_ACCOUNTANT."""
    if user.role == "accountant":
        raise AppException(
            "FORBIDDEN_ACCOUNTANT",
            "Kế toán không được truy cập thành tích NCKH",
            403,
        )


def is_research_all(user: CurrentUser) -> bool:
    """admin/leader = all; staff = own."""
    return user.role in ("admin", "leader")
