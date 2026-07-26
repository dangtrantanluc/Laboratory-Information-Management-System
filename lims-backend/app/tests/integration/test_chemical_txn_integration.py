"""Integration test (Postgres THẬT) cho giao dịch kho hóa chất.

Chứng minh 2 điều cần DB thật:
- H3: khi tạo notification trong _reorder_check LỖI, giao dịch kho (adjust) VẪN được commit
  nhờ SAVEPOINT — không bị PendingRollbackError nuốt mất.
- Tính atomic + CHECK: adjust không cho tồn < 0 (NEGATIVE_BALANCE), balance snapshot đúng.
"""
import uuid
from decimal import Decimal

import pytest

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.chemical import Chemical, ChemicalLot, ChemicalTransaction
from app.services import chemical_txn_service, notification_service

_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
_DEPT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000d4")


def _admin() -> CurrentUser:
    return CurrentUser(
        id=_ADMIN_ID, email="admin@lims.local", full_name="Admin", role="admin",
        department_id=_DEPT_ID, is_dept_lead=False, is_quality_manager=False,
        status="active", jti="jti", token_exp=9999999999,
    )


def _seed_chem_lot(db, *, qty_base="1000.000000", reorder_threshold="500"):
    chem = Chemical(
        name=f"TestChem-{uuid.uuid4().hex[:8]}", base_unit="g", measurement_group="mass",
        department_id=_DEPT_ID, status="active", created_by=_ADMIN_ID,
        reorder_threshold=Decimal(reorder_threshold),
    )
    db.add(chem)
    db.flush()
    lot = ChemicalLot(
        chemical_id=chem.id, lot_no=f"LOT-{uuid.uuid4().hex[:6]}",
        qty_base=Decimal(qty_base), unit_price=Decimal("10.00"), price_unit="g",
        currency="VND", is_expired=False, created_by=_ADMIN_ID,
    )
    db.add(lot)
    db.flush()
    return chem, lot


def test_h3_stock_txn_survives_notification_failure(db, monkeypatch):
    """H3: _reorder_check tạo notification lỗi → giao dịch adjust VẪN commit (SAVEPOINT)."""
    chem, lot = _seed_chem_lot(db, qty_base="1000.000000", reorder_threshold="900")

    # Ép create_notification ném lỗi → mô phỏng lỗi trong _reorder_check
    def _boom(*a, **k):
        raise RuntimeError("notify DB error")

    monkeypatch.setattr(notification_service, "create_notification", _boom)

    # adjust giảm tồn xuống 800 (< ngưỡng 900) → reorder-check kích hoạt → notify lỗi
    result = chemical_txn_service.create_transaction(
        db, user=_admin(), lot_id=lot.id,
        payload={"type": "adjust", "input_unit": "g", "actual_qty_input": "800", "note": "kiểm kê"},
        correlation_id=None, ip=None, can_cost=True,
    )

    # Giao dịch kho PHẢI thành công dù notify lỗi
    assert result["type"] == "adjust"
    db.refresh(lot)
    assert lot.qty_base == Decimal("800.000000")  # tồn đã cập nhật
    txns = db.query(ChemicalTransaction).filter(ChemicalTransaction.lot_id == lot.id).all()
    assert len(txns) == 1  # bản ghi giao dịch được ghi (không bị rollback)


def test_adjust_cannot_go_negative(db):
    """CHECK qty_base >= 0 + guard NEGATIVE_BALANCE: adjust xuống dưới 0 bị từ chối."""
    chem, lot = _seed_chem_lot(db, qty_base="100.000000", reorder_threshold="0")
    with pytest.raises(AppException) as exc:
        chemical_txn_service.create_transaction(
            db, user=_admin(), lot_id=lot.id,
            payload={"type": "adjust", "input_unit": "g", "delta_input": "-500", "note": "sai số"},
            correlation_id=None, ip=None, can_cost=True,
        )
    assert exc.value.code == "NEGATIVE_BALANCE"


def test_adjust_balance_snapshot_correct(db):
    chem, lot = _seed_chem_lot(db, qty_base="1000.000000", reorder_threshold="0")
    result = chemical_txn_service.create_transaction(
        db, user=_admin(), lot_id=lot.id,
        payload={"type": "adjust", "input_unit": "g", "delta_input": "-250", "note": "hao hụt"},
        correlation_id=None, ip=None, can_cost=True,
    )
    assert result["balance_after"] == "750.000000"
