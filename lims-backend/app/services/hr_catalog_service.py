"""Catalog service M4 (#38-#41) — đọc danh mục đã seed (chỉ active, sort_order).

GET danh mục cấp đề tài / chỉ số bài báo / loại HĐ / loại hướng dẫn SV.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hr import (
    ContractType,
    MentorshipType,
    PublicationCategory,
    ResearchProjectLevel,
)


def _list(db: Session, model) -> list[dict]:
    rows = db.execute(
        select(model)
        .where(model.is_active.is_(True))
        .order_by(model.sort_order.asc(), model.code.asc())
    ).scalars().all()
    return [{"code": r.code, "label": r.label} for r in rows]


def project_levels(db: Session) -> list[dict]:
    return _list(db, ResearchProjectLevel)


def pub_indexes(db: Session) -> list[dict]:
    return _list(db, PublicationCategory)


def contract_types(db: Session) -> list[dict]:
    return _list(db, ContractType)


def mentorship_types(db: Session) -> list[dict]:
    return _list(db, MentorshipType)
