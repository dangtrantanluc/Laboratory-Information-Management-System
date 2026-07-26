"""Helper tồn kho dùng chung — đọc qty_base của lô, không SUM giao dịch runtime.

Tách từ chemical_service.py (850 dòng) — M-03/T1.2.
"""
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chemical import (
    ChemicalLot,
)
from app.services import chemical_common as cc

logger_action_prefix = "CHEMICAL"




def _total_stock_base(db: Session, chemical_id: uuid.UUID) -> Decimal:
    total = db.execute(
        select(func.coalesce(func.sum(ChemicalLot.qty_base), 0)).where(
            ChemicalLot.chemical_id == chemical_id
        )
    ).scalar_one()
    return cc.q_base(Decimal(total))


def _lot_count(db: Session, chemical_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count()).select_from(ChemicalLot).where(
            ChemicalLot.chemical_id == chemical_id
        )
    ).scalar_one()
