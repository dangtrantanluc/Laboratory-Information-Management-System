"""Thống kê Báo cáo phân tích mẫu — tab "Báo cáo phân tích mẫu" ở trang Báo cáo & Thống kê.

Nguồn số liệu là các báo cáo quý các phòng lab đã nộp (m54), KHÔNG phải bảng `samples`
của module phiếu mẫu M1: các lab chưa dùng luồng phiếu mẫu, nên bảng đó trống trên
production, còn báo cáo quý là số liệu thật Văn phòng có trong tay.

Trả về dữ liệu PHẲNG theo ô (phòng × quý × loại mẫu); giao diện tự cộng ra theo phòng,
theo loại mẫu, theo quý và bảng chéo — một truy vấn, nhiều cách nhìn.

Mặc định chỉ tính báo cáo ĐÃ CHỐT, cùng quy ước với file Excel xuất đi.
"""
import re
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import forbidden
from app.models.department import Department
from app.models.quarterly_sample_report import (
    REPORT_STATUS_LABELS, QuarterlyReport, QuarterlyReportItem, QuarterlyReportItemCriterion,
)
from app.models.sample_flow import MATRIX_LABELS
from app.services import quarterly_sample_report_service as svc

TOP_CRITERIA = 15
_SPLIT = re.compile(r"[,;]")


def stats(
    db: Session, *, user: CurrentUser, year: int, quarter: Optional[int],
    department_id: Optional[uuid.UUID], include_unlocked: bool,
) -> dict:
    if not svc.can_read_all(db, user):
        raise forbidden("Chỉ Văn phòng / Ban lãnh đạo xem được thống kê toàn Viện")

    depts = db.execute(
        select(Department)
        .where(Department.kind == "lab", Department.status == "active")
        .order_by(Department.name)
    ).scalars().all()

    conds = [QuarterlyReport.year == year]
    if quarter:
        conds.append(QuarterlyReport.quarter == quarter)
    if department_id:
        conds.append(QuarterlyReport.department_id == department_id)
    reports = db.execute(select(QuarterlyReport).where(*conds)).scalars().all()
    included = {r.id: r for r in reports if include_unlocked or r.status == "locked"}

    cells = []
    top: list[dict] = []
    if included:
        rows = db.execute(
            select(
                QuarterlyReportItem.report_id, QuarterlyReportItem.matrix,
                func.count(), func.sum(QuarterlyReportItem.quantity),
            )
            .where(QuarterlyReportItem.report_id.in_(included))
            .group_by(QuarterlyReportItem.report_id, QuarterlyReportItem.matrix)
        ).all()
        for report_id, matrix, n_items, qty in rows:
            r = included[report_id]
            cells.append({
                "department_id": r.department_id,
                "quarter": r.quarter,
                "matrix": matrix,
                # "Khác" gộp một nhóm — ghi rõ tự do từng dòng sẽ làm nổ số cột thống kê.
                "matrix_label": MATRIX_LABELS.get(matrix, matrix),
                "items": n_items,
                "quantity": int(qty or 0),
            })
        top = _top_criteria(db, list(included))

    return {
        "year": year,
        "quarter": quarter,
        "include_unlocked": include_unlocked,
        "departments": [{"id": d.id, "name": d.name, "code": d.code} for d in depts],
        "reports": [
            {
                "department_id": r.department_id,
                "quarter": r.quarter,
                "status": r.status,
                "status_label": REPORT_STATUS_LABELS[r.status],
            }
            for r in reports
        ],
        "cells": cells,
        "top_criteria": top,
    }


def _top_criteria(db: Session, report_ids: list[uuid.UUID]) -> list[dict]:
    """Chỉ tiêu được phân tích nhiều nhất — đếm SỐ DÒNG MẪU có chỉ tiêu đó.

    Gộp cả chỉ tiêu trong danh mục lẫn chỉ tiêu ngoài danh mục (tách theo dấu phẩy),
    không phân biệt hoa thường: "Tro" và "tro" là một.
    """
    items = db.execute(
        select(QuarterlyReportItem.id, QuarterlyReportItem.extra_criteria)
        .where(QuarterlyReportItem.report_id.in_(report_ids))
    ).all()
    names: dict[uuid.UUID, set[str]] = {i: set() for i, _ in items}
    display: dict[str, str] = {}

    def add(item_id, raw: str) -> None:
        name = " ".join(raw.split())
        if not name:
            return
        key = name.casefold()
        display.setdefault(key, name)
        names[item_id].add(key)

    for item_id, extra in items:
        for part in _SPLIT.split(extra or ""):
            add(item_id, part)
    for item_id, name in db.execute(
        select(QuarterlyReportItemCriterion.item_id, QuarterlyReportItemCriterion.name)
        .where(QuarterlyReportItemCriterion.item_id.in_(list(names)))
    ).all():
        add(item_id, name)

    counts: dict[str, int] = {}
    for keys in names.values():
        for k in keys:
            counts[k] = counts.get(k, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], display[kv[0]]))
    return [{"name": display[k], "items": n} for k, n in ranked[:TOP_CRITERIA]]
