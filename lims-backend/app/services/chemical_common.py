"""M2 common helpers — RBAC scope, field-level price strip, quy đổi đơn vị (Decimal),
error factories, CAS validate, parse decimal.

Quy đổi đơn vị (CỐT LÕI, chống sai số): tồn lưu base unit NUMERIC(18,6). Quy đổi
qty_input theo input_unit → base qua units.factor_to_base. KHÔNG float — dùng Decimal.
Round-trip không sai số ở NUMERIC(18,6).

Field-level RBAC (BR-CHEM-022, OWASP A01): cột giá chỉ trả cho vai trò có quyền
chemical:cost (admin/leader/accountant). KTV (staff) bị STRIP cột giá ở TẦNG API.
"""
import re
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.core.rbac import has_permission
from app.models.chemical import Unit

# Cột tiền bị strip với vai trò không có chemical:cost (contract §0.6)
PRICE_FIELDS = frozenset(
    {
        "unit_price",
        "price_unit",
        "currency",
        "stock_value",
        "total_stock_value",
        "line_value",
        "consumption_cost",
    }
)

# CAS: NNNNNNN-NN-N (2..7 digit) + checksum (số kiểm tra)
_CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")

# Lượng tử hóa theo precision DB
_Q_BASE = Decimal("0.000001")  # NUMERIC(18,6)
_Q_INPUT = Decimal("0.0001")  # NUMERIC(14,4)
_Q_MONEY = Decimal("0.01")  # NUMERIC(14,2)


# ===== Error factories (đồng bộ danh mục error code §3 contract) =====
def err(code: str, message: str, http: int = 400, details=None) -> AppException:
    return AppException(code, message, http, details)


def forbidden(message: str = "Bạn không có quyền thực hiện thao tác này") -> AppException:
    return AppException("FORBIDDEN", message, 403)


# ===== RBAC =====
def is_privileged(user: CurrentUser) -> bool:
    """Admin / Ban lãnh đạo = toàn hệ thống (bỏ qua scope phòng cho ghi)."""
    return user.role in ("admin", "leader")


def can_see_cost(db: Session, user: CurrentUser) -> bool:
    """Vai trò tài chính (admin/leader/accountant) — quyền chemical:cost (BR-CHEM-022)."""
    return has_permission(db, user.role, "chemical", "cost")


def assert_can_transact(db: Session, user: CurrentUser) -> None:
    """Quyền nhập/xuất/điều chỉnh — chemical:transact. Kế toán KHÔNG có (chỉ xem giá)."""
    if not has_permission(db, user.role, "chemical", "transact"):
        raise forbidden("Vai trò của bạn không được ghi giao dịch hóa chất")


def assert_can_create(db: Session, user: CurrentUser) -> None:
    """Quyền tạo/sửa hóa chất/lô — chemical:create (admin all; leader all; staff dept)."""
    if not has_permission(db, user.role, "chemical", "create"):
        raise forbidden("Vai trò của bạn không được tạo/sửa hóa chất")


def assert_write_scope(user: CurrentUser, dept_id: uuid.UUID) -> None:
    """Phạm vi ghi theo phòng (BR-CHEM-018): KTV chỉ ghi trong phòng mình."""
    if is_privileged(user):
        return
    if user.department_id is None or user.department_id != dept_id:
        raise forbidden("Bạn chỉ được thao tác trong phạm vi phòng ban của mình")


def resolve_write_department(user: CurrentUser, requested: Optional[uuid.UUID]) -> uuid.UUID:
    """Phòng để tạo hóa chất: KTV ép phòng mình; admin/leader theo yêu cầu (mặc định phòng mình)."""
    if is_privileged(user):
        if requested is not None:
            return requested
        if user.department_id is not None:
            return user.department_id
        raise err("VALIDATION_ERROR", "Cần chỉ định department_id", 400)
    # staff: ép phòng của user; nếu gửi phòng khác → 403
    if user.department_id is None:
        raise forbidden("Người dùng chưa thuộc phòng ban nào")
    if requested is not None and requested != user.department_id:
        raise forbidden("KTV chỉ được tạo hóa chất cho phòng của mình")
    return user.department_id


def strip_price_fields(data, can_cost: bool):
    """Strip mọi key tiền khỏi dict/list nếu user KHÔNG có quyền cost (BR-CHEM-022).

    Đệ quy: áp dụng cho object lồng (lots, lines). KHÔNG mutate input gốc.
    """
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
    from app.models.user import User

    u = db.get(User, user_id)
    return u.full_name if u else None


def dept_name(db: Session, dept_id: Optional[uuid.UUID]) -> Optional[str]:
    if dept_id is None:
        return None
    from app.models.department import Department

    d = db.get(Department, dept_id)
    return d.name if d else None


# ===== CAS validate (regex + checksum) =====
def validate_cas(cas_no: Optional[str]) -> Optional[str]:
    """CAS Registry Number: NNNNNNN-NN-N + checksum. None/empty → None. Sai → VALIDATION_ERROR."""
    if cas_no is None:
        return None
    cas = cas_no.strip()
    if not cas:
        return None
    if not _CAS_RE.match(cas):
        raise err(
            "VALIDATION_ERROR",
            "Số CAS không đúng định dạng (NNNNNNN-NN-N)",
            400,
            [{"field": "cas_no", "message": "Định dạng CAS không hợp lệ"}],
        )
    digits = cas.replace("-", "")
    body, check = digits[:-1], int(digits[-1])
    total = sum((i + 1) * int(d) for i, d in enumerate(reversed(body)))
    if total % 10 != check:
        raise err(
            "VALIDATION_ERROR",
            "Số CAS sai số kiểm tra (checksum)",
            400,
            [{"field": "cas_no", "message": "Checksum CAS không hợp lệ"}],
        )
    return cas


# ===== Parse decimal an toàn =====
def parse_decimal(value: Optional[str], *, field: str, allow_negative: bool = False) -> Optional[Decimal]:
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
    if not allow_negative and d < 0:
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


def q_base(d: Decimal) -> Decimal:
    return d.quantize(_Q_BASE, rounding=ROUND_HALF_UP)


def q_money(d: Decimal) -> Decimal:
    return d.quantize(_Q_MONEY, rounding=ROUND_HALF_UP)


# ===== Quy đổi đơn vị (Decimal, cùng nhóm đo) =====
def get_unit(db: Session, code: str) -> Unit:
    u = db.get(Unit, code)
    if u is None:
        raise err("INVALID_UNIT", f"Đơn vị '{code}' không tồn tại", 400)
    return u


def assert_same_group(db: Session, unit_code: str, measurement_group: str) -> Unit:
    """input/display unit phải cùng nhóm đo với base_unit của hóa chất (BR-CHEM-028).

    Trả Unit nếu hợp lệ; sai nhóm → 422 UNIT_GROUP_MISMATCH; không tồn tại → 400 INVALID_UNIT.
    """
    u = get_unit(db, unit_code)
    if u.measurement_group != measurement_group:
        raise err(
            "UNIT_GROUP_MISMATCH",
            f"Đơn vị '{unit_code}' ({u.measurement_group}) khác nhóm đo với hóa chất ({measurement_group})",
            422,
            [{"field": "input_unit", "message": "Khác nhóm đo, không thể quy đổi"}],
        )
    return u


def convert_to_base(
    db: Session, qty_input: Decimal, input_unit: str, base_unit: str, measurement_group: str
) -> Decimal:
    """qty_base = qty_input * factor(input) / factor(base). Decimal — không float.

    Validate input_unit cùng nhóm. Round-trip chính xác ở NUMERIC(18,6).
    """
    u_in = assert_same_group(db, input_unit, measurement_group)
    u_base = get_unit(db, base_unit)
    qty_base = (qty_input * u_in.factor_to_base) / u_base.factor_to_base
    return q_base(qty_base)


def convert_from_base(
    db: Session, qty_base: Decimal, base_unit: str, display_unit: str, measurement_group: str
) -> Decimal:
    """Hiển thị: qty_display = qty_base * factor(base) / factor(display). Decimal."""
    u_disp = assert_same_group(db, display_unit, measurement_group)
    u_base = get_unit(db, base_unit)
    qty_display = (qty_base * u_base.factor_to_base) / u_disp.factor_to_base
    return qty_display.quantize(_Q_INPUT, rounding=ROUND_HALF_UP)


# ===== Decimal → string (giữ precision cho JSON, contract §0.5) =====
def s_base(d: Optional[Decimal]) -> Optional[str]:
    if d is None:
        return None
    return f"{q_base(Decimal(d)):.6f}"


def s_input(d: Optional[Decimal]) -> Optional[str]:
    if d is None:
        return None
    return f"{Decimal(d).quantize(_Q_INPUT, rounding=ROUND_HALF_UP):.4f}"


def s_money(d: Optional[Decimal]) -> Optional[str]:
    if d is None:
        return None
    return f"{q_money(Decimal(d)):.2f}"


# ===== Get-or-404 với row-lock =====
def get_chemical_or_404(db: Session, chemical_id: uuid.UUID, *, include_inactive: bool = True):
    from app.models.chemical import Chemical

    c = db.get(Chemical, chemical_id)
    if c is None or (not include_inactive and c.status != "active"):
        raise AppException("NOT_FOUND", "Không tìm thấy hóa chất", 404)
    return c


def get_lot_or_404(db: Session, lot_id: uuid.UUID, *, lock: bool = False):
    from app.models.chemical import ChemicalLot

    stmt = select(ChemicalLot).where(ChemicalLot.id == lot_id)
    if lock:
        stmt = stmt.with_for_update()
    lot = db.execute(stmt).scalar_one_or_none()
    if lot is None:
        raise AppException("NOT_FOUND", "Không tìm thấy lô hóa chất", 404)
    return lot
