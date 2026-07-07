"""M10 service — Risk & Improvement (§8.5/§8.6).

- Risk: sổ đăng ký, ma trận, biện pháp xử lý, đóng. level GENERATED (không ghi app-layer).
- Improvement: sổ cải tiến nhẹ; liên kết linked_nc_id sang NC (M8).
Mọi thao tác 1 transaction + audit (§8.4). Risk đã closed → app-layer chặn sửa.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.nonconformity import Nonconformity
from app.models.risk import Improvement, Risk, RiskTreatment
from app.services import audit_service, notification_service, risk_common as rc

logger = logging.getLogger("lims.risk")


# ===== #1 GET /risks =====
def list_risks(
    db: Session,
    *,
    q: Optional[str],
    kind: Optional[str],
    status_filter: Optional[str],
    department_id: Optional[uuid.UUID],
    band: Optional[str],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    if q:
        conditions.append(
            func.lower(Risk.title).like(f"%{q.lower()}%")
            | func.lower(Risk.risk_code).like(f"%{q.lower()}%")
        )
    if kind:
        conditions.append(Risk.kind == kind)
    if status_filter:
        conditions.append(Risk.status == status_filter)
    if department_id:
        conditions.append(Risk.department_id == department_id)
    if band == "low":
        conditions.append(Risk.level <= 4)
    elif band == "medium":
        conditions.append(Risk.level.between(5, 12))
    elif band == "high":
        conditions.append(Risk.level >= 13)

    total = db.execute(
        select(func.count()).select_from(Risk).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(Risk)
        .where(*conditions)
        .order_by(Risk.level.desc(), Risk.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return [rc.risk_list_dict(db, r) for r in rows], total


# ===== #8 GET /risks/stats (ma trận 5×5 + by status + by band) =====
def risk_stats(db: Session) -> dict:
    matrix = [[0] * 6 for _ in range(6)]  # [likelihood][impact], 1..5
    rows = db.execute(
        select(Risk.likelihood, Risk.impact, func.count())
        .where(Risk.status != "closed")
        .group_by(Risk.likelihood, Risk.impact)
    ).all()
    for lk, im, cnt in rows:
        matrix[lk][im] = cnt

    by_status = dict(
        db.execute(select(Risk.status, func.count()).group_by(Risk.status)).all()
    )
    by_band = {"low": 0, "medium": 0, "high": 0}
    for level, cnt in db.execute(
        select(Risk.level, func.count()).where(Risk.status != "closed").group_by(Risk.level)
    ).all():
        by_band[rc.band(level)] += cnt

    return {
        "matrix": matrix,  # matrix[likelihood][impact]
        "by_status": by_status,
        "by_band": by_band,
        "total": sum(by_status.values()),
        "open_high": by_band["high"],
    }


# ===== #3 GET /risks/:id =====
def get_risk(db: Session, *, risk_id: uuid.UUID) -> dict:
    return rc.risk_detail_dict(db, rc.get_risk_or_404(db, risk_id))


# ===== #2 POST /risks =====
def create_risk(
    db: Session, *, user: CurrentUser, payload: dict, correlation_id, ip
) -> dict:
    rc.assert_can_create(db, user, "risk")
    department_id = rc.resolve_create_department(user, payload.get("department_id"))
    owner_id = payload.get("owner_id") or user.id

    entity: Optional[Risk] = None
    for attempt in range(5):
        entity = Risk(
            risk_code=rc.next_code(db, Risk, Risk.risk_code, "RSK"),
            kind=payload.get("kind") or "risk",
            title=payload["title"].strip(),
            context=payload["context"].strip(),
            process_ref=payload.get("process_ref"),
            likelihood=payload["likelihood"],
            impact=payload["impact"],
            status="open",
            owner_id=owner_id,
            department_id=department_id,
            next_review_date=payload.get("next_review_date"),
            created_by=user.id,
        )
        db.add(entity)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            entity = None
            if attempt == 4:
                raise AppException("RISK_CODE_CONFLICT", "Không sinh được mã, thử lại", 409)
    assert entity is not None

    audit_service.log_action(
        db, action="RISK_CREATE", resource="risk", user_id=user.id,
        resource_id=entity.id, correlation_id=correlation_id, ip=ip,
        detail={"risk_code": entity.risk_code, "kind": entity.kind},
    )
    db.commit()
    db.refresh(entity)
    return rc.risk_detail_dict(db, entity)


# ===== #4 PATCH /risks/:id =====
def update_risk(
    db: Session, *, user: CurrentUser, risk_id: uuid.UUID, changes: dict, correlation_id, ip
) -> dict:
    entity = rc.get_risk_or_404(db, risk_id, lock=True)
    if not (entity.created_by == user.id or rc.is_quality_manager(user)):
        raise rc.forbidden("Chỉ người tạo hoặc QM được sửa")
    if entity.status == "closed":
        raise AppException("RISK_CLOSED", "Rủi ro đã đóng — không thể sửa", 409)

    for field in ("title", "context", "likelihood", "impact", "process_ref", "status", "owner_id", "next_review_date"):
        if field in changes:
            setattr(entity, field, changes[field])
    entity.updated_by = user.id
    entity.updated_at = func.now()
    audit_service.log_action(
        db, action="RISK_UPDATE", resource="risk", user_id=user.id,
        resource_id=entity.id, correlation_id=correlation_id, ip=ip,
        detail={"risk_code": entity.risk_code, "fields": list(changes.keys())},
    )
    db.commit()
    db.refresh(entity)
    return rc.risk_detail_dict(db, entity)


# ===== #5 POST /risks/:id/treatments =====
def add_treatment(
    db: Session, *, user: CurrentUser, risk_id: uuid.UUID, payload: dict, correlation_id, ip
) -> dict:
    rc.assert_can_manage(user)
    entity = rc.get_risk_or_404(db, risk_id)
    if entity.status == "closed":
        raise AppException("RISK_CLOSED", "Rủi ro đã đóng — không thể thêm biện pháp", 409)

    t = RiskTreatment(
        risk_id=entity.id,
        treatment=payload["treatment"].strip(),
        owner_id=payload.get("owner_id"),
        due_date=payload.get("due_date"),
        created_by=user.id,
    )
    db.add(t)
    if entity.status == "open":
        entity.status = "treating"
    db.flush()
    if t.owner_id and t.owner_id != user.id:
        notification_service.create_notification(
            db, user_id=t.owner_id, type="RISK_TREATMENT_ASSIGNED",
            title=f"Bạn được giao biện pháp xử lý rủi ro ({entity.risk_code})",
            body=t.treatment[:200], ref_type="risk", ref_id=entity.id,
        )
    audit_service.log_action(
        db, action="RISK_TREATMENT_ADD", resource="risk", user_id=user.id,
        resource_id=entity.id, correlation_id=correlation_id, ip=ip,
        detail={"risk_code": entity.risk_code, "treatment_id": str(t.id)},
    )
    db.commit()
    db.refresh(entity)
    return rc.risk_detail_dict(db, entity)


# ===== #6 PATCH /risks/:id/treatments/:tid =====
def update_treatment(
    db: Session, *, user: CurrentUser, risk_id: uuid.UUID, treatment_id: uuid.UUID,
    new_status: str, correlation_id, ip,
) -> dict:
    rc.assert_can_manage(user)
    entity = rc.get_risk_or_404(db, risk_id)
    t = db.get(RiskTreatment, treatment_id)
    if t is None or t.risk_id != entity.id:
        raise AppException("TREATMENT_NOT_FOUND", "Không tìm thấy biện pháp", 404)
    t.status = new_status
    t.done_at = datetime.now(timezone.utc) if new_status == "done" else None
    audit_service.log_action(
        db, action="RISK_TREATMENT_UPDATE", resource="risk", user_id=user.id,
        resource_id=entity.id, correlation_id=correlation_id, ip=ip,
        detail={"risk_code": entity.risk_code, "treatment_id": str(treatment_id), "status": new_status},
    )
    db.commit()
    db.refresh(entity)
    return rc.risk_detail_dict(db, entity)


# ===== #7 POST /risks/:id/close =====
def close_risk(
    db: Session, *, user: CurrentUser, risk_id: uuid.UUID, note: Optional[str], correlation_id, ip
) -> dict:
    rc.assert_can_manage(user)
    entity = rc.get_risk_or_404(db, risk_id, lock=True)
    if entity.status == "closed":
        raise AppException("RISK_CLOSED", "Rủi ro đã đóng", 409)
    entity.status = "closed"
    entity.closed_by = user.id
    entity.closed_at = datetime.now(timezone.utc)
    entity.updated_by = user.id
    entity.updated_at = func.now()
    audit_service.log_action(
        db, action="RISK_CLOSE", resource="risk", user_id=user.id,
        resource_id=entity.id, correlation_id=correlation_id, ip=ip,
        detail={"risk_code": entity.risk_code, "note": note},
    )
    db.commit()
    db.refresh(entity)
    return rc.risk_detail_dict(db, entity)


# ===================== IMPROVEMENTS (§8.6) =====================
def list_improvements(
    db: Session, *, q: Optional[str], status_filter: Optional[str],
    source: Optional[str], page: int, limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    if q:
        conditions.append(
            func.lower(Improvement.title).like(f"%{q.lower()}%")
            | func.lower(Improvement.improvement_code).like(f"%{q.lower()}%")
        )
    if status_filter:
        conditions.append(Improvement.status == status_filter)
    if source:
        conditions.append(Improvement.source == source)
    total = db.execute(
        select(func.count()).select_from(Improvement).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(Improvement).where(*conditions)
        .order_by(Improvement.created_at.desc())
        .offset((page - 1) * limit).limit(limit)
    ).scalars().all()
    return [rc.improvement_dict(db, i) for i in rows], total


def get_improvement(db: Session, *, imp_id: uuid.UUID) -> dict:
    return rc.improvement_dict(db, rc.get_improvement_or_404(db, imp_id))


def create_improvement(
    db: Session, *, user: CurrentUser, payload: dict, correlation_id, ip
) -> dict:
    rc.assert_can_create(db, user, "improvement")
    department_id = payload.get("department_id") or user.department_id

    entity: Optional[Improvement] = None
    for attempt in range(5):
        entity = Improvement(
            improvement_code=rc.next_code(db, Improvement, Improvement.improvement_code, "IMP"),
            source=payload.get("source") or "other",
            title=payload["title"].strip(),
            description=payload["description"].strip(),
            owner_id=payload.get("owner_id"),
            department_id=department_id,
            status="open",
            created_by=user.id,
        )
        db.add(entity)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            entity = None
            if attempt == 4:
                raise AppException("IMP_CODE_CONFLICT", "Không sinh được mã, thử lại", 409)
    assert entity is not None
    audit_service.log_action(
        db, action="IMPROVEMENT_CREATE", resource="improvement", user_id=user.id,
        resource_id=entity.id, correlation_id=correlation_id, ip=ip,
        detail={"improvement_code": entity.improvement_code, "source": entity.source},
    )
    db.commit()
    db.refresh(entity)
    return rc.improvement_dict(db, entity)


def update_improvement(
    db: Session, *, user: CurrentUser, imp_id: uuid.UUID, changes: dict, correlation_id, ip
) -> dict:
    entity = rc.get_improvement_or_404(db, imp_id)
    if not (entity.created_by == user.id or rc.is_quality_manager(user)):
        raise rc.forbidden("Chỉ người tạo hoặc QM được sửa")
    if "linked_nc_id" in changes and changes["linked_nc_id"] is not None:
        if db.get(Nonconformity, changes["linked_nc_id"]) is None:
            raise AppException("NC_NOT_FOUND", "Phiếu NC liên kết không tồn tại", 404)
    for field in ("status", "owner_id", "linked_nc_id"):
        if field in changes:
            setattr(entity, field, changes[field])
    entity.updated_by = user.id
    entity.updated_at = func.now()
    audit_service.log_action(
        db, action="IMPROVEMENT_UPDATE", resource="improvement", user_id=user.id,
        resource_id=entity.id, correlation_id=correlation_id, ip=ip,
        detail={"improvement_code": entity.improvement_code, "fields": list(changes.keys())},
    )
    db.commit()
    db.refresh(entity)
    return rc.improvement_dict(db, entity)
