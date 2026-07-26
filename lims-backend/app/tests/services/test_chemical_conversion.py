"""Tests cho chemical_common — quy đổi đơn vị Decimal (nền tảng tính tồn kho atomic).

Không float: round-trip base↔input phải chính xác ở NUMERIC. Sai nhóm đo → từ chối.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import AppException
from app.services import chemical_common as cc


def _unit(code, group, factor):
    return SimpleNamespace(code=code, measurement_group=group, factor_to_base=Decimal(factor))


def _db_with_units(units: dict):
    """MagicMock db mà db.get(Unit, code) trả unit tương ứng."""
    db = MagicMock()
    db.get.side_effect = lambda model, code: units.get(code)
    return db


def test_convert_to_base_kg_to_g():
    # base = g (factor 1), input = kg (factor 1000) → 2 kg = 2000 g
    units = {"g": _unit("g", "mass", "1"), "kg": _unit("kg", "mass", "1000")}
    db = _db_with_units(units)
    result = cc.convert_to_base(db, Decimal("2"), "kg", "g", "mass")
    assert result == Decimal("2000.000000")


def test_convert_from_base_g_to_kg():
    units = {"g": _unit("g", "mass", "1"), "kg": _unit("kg", "mass", "1000")}
    db = _db_with_units(units)
    result = cc.convert_from_base(db, Decimal("2500"), "g", "kg", "mass")
    assert result == Decimal("2.5000")


def test_round_trip_base_input_base_is_stable():
    units = {"g": _unit("g", "mass", "1"), "kg": _unit("kg", "mass", "1000")}
    db = _db_with_units(units)
    base = cc.convert_to_base(db, Decimal("1.2345"), "kg", "g", "mass")
    back = cc.convert_from_base(db, base, "g", "kg", "mass")
    assert back == Decimal("1.2345")


def test_convert_rejects_cross_group():
    # input = mL (volume) nhưng hóa chất nhóm mass → UNIT_GROUP_MISMATCH
    units = {
        "g": _unit("g", "mass", "1"),
        "mL": _unit("mL", "volume", "1"),
    }
    db = _db_with_units(units)
    with pytest.raises(AppException) as exc:
        cc.convert_to_base(db, Decimal("5"), "mL", "g", "mass")
    assert exc.value.code == "UNIT_GROUP_MISMATCH"
    assert exc.value.http_status == 422


def test_convert_unknown_unit_rejected():
    db = _db_with_units({"g": _unit("g", "mass", "1")})
    with pytest.raises(AppException) as exc:
        cc.convert_to_base(db, Decimal("5"), "zzz", "g", "mass")
    assert exc.value.code == "INVALID_UNIT"


def test_parse_decimal_rejects_negative_by_default():
    with pytest.raises(AppException):
        cc.parse_decimal("-5", field="qty")


def test_parse_decimal_allows_negative_when_flagged():
    assert cc.parse_decimal("-5", field="adjust", allow_negative=True) == Decimal("-5")
