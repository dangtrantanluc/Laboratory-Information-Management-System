"""M8 service — NC & CAPA (§7.10/§8.7). Vòng đời open→in_capa→closed (+cancelled).

Nghiệp vụ chính:
- create_nc: sinh nc_code, status=open, audit.
- open_capa: 1 CAPA/NC (409 CAPA_EXISTS), NC open→in_capa, thông báo owner.
- add_action / update_action: chỉ khi CAPA in_progress (409 CAPA_CLOSED_IMMUTABLE).
- close_capa: cần effectiveness + mọi action done (422 ACTIONS_INCOMPLETE); capa→closed
  (trigger DB khóa sửa sau đó), NC→closed; cảnh báo mềm nếu người đóng == người mở NC.

Mọi thao tác qua 1 transaction + audit (§8.4). NC đã closed/cancelled → app-layer chặn sửa.
"""
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.nonconformity import Capa, CapaAction, Nonconformity
from app.services import audit_service, nc_common as nc, notification_service

logger = logging.getLogger("lims.nc")


# ===== #1 GET /nonconformities =====
def list_ncs(
    db: Session,
    *,
    q: Optional[str],
    status_filter: Optional[str],
    severity: Optional[str],
    source_type: Optional[str],
    department_id: Optional[uuid.UUID],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    if q:
        conditions.append(
            func.lower(Nonconformity.title).like(f"%{q.lower()}%")
            | func.lower(Nonconformity.nc_code).like(f"%{q.lower()}%")
        )
    if status_filter:
        conditions.append(Nonconformity.status == status_filter)
    if severity:
        conditions.append(Nonconformity.severity == severity)
    if source_type:
        conditions.append(Nonconformity.source_type == source_type)
    if department_id:
        conditions.append(Nonconformity.department_id == department_id)

    total = db.execute(
        select(func.count()).select_from(Nonconformity).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(Nonconformity)
        .where(*conditions)
        .order_by(Nonconformity.raised_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()

    # có CAPA hay chưa (1 query gọn)
    ids = [r.id for r in rows]
    capa_ncids = set()
    if ids:
        capa_ncids = set(
            db.execute(select(Capa.nc_id).where(Capa.nc_id.in_(ids))).scalars().all()
        )
    return [nc.nc_list_dict(db, r, has_capa=r.id in capa_ncids) for r in rows], total


# ===== #10 GET /nonconformities/stats =====
def stats(db: Session) -> dict:
    def _count_by(col):
        return dict(
            db.execute(
                select(col, func.count()).select_from(Nonconformity).group_by(col)
            ).all()
        )

    by_status = _count_by(Nonconformity.status)
    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "by_severity": _count_by(Nonconformity.severity),
        "by_source": _count_by(Nonconformity.source_type),
        "open_capa": by_status.get("in_capa", 0),
    }


# ===== #3 GET /nonconformities/:id =====
def get_nc(db: Session, *, nc_id: uuid.UUID) -> dict:
    entity = nc.get_nc_or_404(db, nc_id)
    return nc.nc_detail_dict(db, entity)


# ===== #2 POST /nonconformities =====
def create_nc(
    db: Session,
    *,
    user: CurrentUser,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    nc.assert_can_create(db, user)
    department_id = nc.resolve_create_department(user, payload.get("department_id"))

    entity: Optional[Nonconformity] = None
    for attempt in range(5):  # retry chống đua nc_code (UNIQUE là lưới an toàn)
        code = nc.next_nc_code(db)
        entity = Nonconformity(
            nc_code=code,
            source_type=payload.get("source_type") or "manual",
            source_id=payload.get("source_id"),
            severity=payload["severity"],
            title=payload["title"].strip(),
            description=payload["description"].strip(),
            impact_assessment=(payload.get("impact_assessment") or None),
            affected_ref_type=payload.get("affected_ref_type"),
            affected_ref_id=payload.get("affected_ref_id"),
            department_id=department_id,
            raised_by=user.id,
        )
        db.add(entity)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            entity = None
            if attempt == 4:
                raise AppException(
                    "NC_CODE_CONFLICT", "Không sinh được mã NC, thử lại", 409
                )
    assert entity is not None

    audit_service.log_action(
        db,
        action="NC_CREATE",
        resource="nonconformity",
        user_id=user.id,
        resource_id=entity.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={
            "nc_code": entity.nc_code,
            "severity": entity.severity,
            "source_type": entity.source_type,
        },
    )
    db.commit()
    db.refresh(entity)
    logger.info("NC created", extra={"correlationId": correlation_id, "ncCode": entity.nc_code})
    return nc.nc_detail_dict(db, entity)


# ===== #4 PATCH /nonconformities/:id =====
def update_nc(
    db: Session,
    *,
    user: CurrentUser,
    nc_id: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    entity = nc.get_nc_or_404(db, nc_id, lock=True)
    # người tạo hoặc QM được sửa; accountant đã bị chặn ở read/create
    if not (entity.raised_by == user.id or nc.is_quality_manager(user)):
        raise nc.forbidden("Chỉ người tạo hoặc QM được sửa phiếu này")
    if entity.status in ("closed", "cancelled"):
        raise AppException("NC_CLOSED", "Phiếu đã đóng/hủy — không thể sửa", 409)

    for field in ("severity", "impact_assessment", "affected_ref_type", "affected_ref_id"):
        if field in changes:
            setattr(entity, field, changes[field])
    entity.updated_by = user.id
    entity.updated_at = func.now()
    audit_service.log_action(
        db,
        action="NC_UPDATE",
        resource="nonconformity",
        user_id=user.id,
        resource_id=entity.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"nc_code": entity.nc_code, "fields": list(changes.keys())},
    )
    db.commit()
    db.refresh(entity)
    return nc.nc_detail_dict(db, entity)


# ===== #5 POST /nonconformities/:id/cancel =====
def cancel_nc(
    db: Session,
    *,
    user: CurrentUser,
    nc_id: uuid.UUID,
    reason: str,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    nc.assert_can_manage(db, user)
    entity = nc.get_nc_or_404(db, nc_id, lock=True)
    if entity.status == "closed":
        raise AppException("NC_CLOSED", "Phiếu đã đóng — không thể hủy", 409)
    if entity.status == "in_capa":
        raise AppException(
            "NC_HAS_CAPA", "Phiếu đang có CAPA — không thể hủy. Hãy đóng CAPA.", 409
        )
    entity.status = "cancelled"
    entity.updated_by = user.id
    entity.updated_at = func.now()
    audit_service.log_action(
        db,
        action="NC_CANCEL",
        resource="nonconformity",
        user_id=user.id,
        resource_id=entity.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"nc_code": entity.nc_code, "reason": reason},
    )
    db.commit()
    db.refresh(entity)
    return nc.nc_detail_dict(db, entity)


# ===== #6 POST /nonconformities/:id/capa =====
def open_capa(
    db: Session,
    *,
    user: CurrentUser,
    nc_id: uuid.UUID,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    nc.assert_can_manage(db, user)
    entity = nc.get_nc_or_404(db, nc_id, lock=True)
    if entity.status in ("closed", "cancelled"):
        raise AppException("NC_CLOSED", "Phiếu đã đóng/hủy — không thể mở CAPA", 409)
    if nc.get_capa_for_nc(db, nc_id) is not None:
        raise AppException("CAPA_EXISTS", "Phiếu này đã có CAPA", 409)

    owner_id = payload["owner_id"]
    capa = Capa(
        nc_id=nc_id,
        capa_type=payload.get("capa_type") or "corrective",
        root_cause=payload["root_cause"].strip(),
        owner_id=owner_id,
        due_date=payload.get("due_date"),
        created_by=user.id,
    )
    db.add(capa)
    entity.status = "in_capa"
    entity.updated_by = user.id
    entity.updated_at = func.now()
    db.flush()

    # Thông báo owner được giao CAPA (nếu khác người thao tác)
    if owner_id != user.id:
        notification_service.create_notification(
            db,
            user_id=owner_id,
            type="CAPA_ASSIGNED",
            title=f"Bạn được giao CAPA cho {entity.nc_code}",
            body=entity.title,
            ref_type="nonconformity",
            ref_id=entity.id,
        )
    audit_service.log_action(
        db,
        action="CAPA_OPEN",
        resource="nonconformity",
        user_id=user.id,
        resource_id=entity.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"nc_code": entity.nc_code, "owner_id": str(owner_id)},
    )
    db.commit()
    db.refresh(entity)
    return nc.nc_detail_dict(db, entity)


# ===== #7 POST /nonconformities/:id/actions =====
def add_action(
    db: Session,
    *,
    user: CurrentUser,
    nc_id: uuid.UUID,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    nc.assert_can_manage(db, user)
    entity = nc.get_nc_or_404(db, nc_id)
    capa = _capa_editable_or_raise(db, nc_id)

    action = CapaAction(
        capa_id=capa.id,
        action=payload["action"].strip(),
        assignee_id=payload.get("assignee_id"),
        due_date=payload.get("due_date"),
        created_by=user.id,
    )
    db.add(action)
    db.flush()
    if action.assignee_id and action.assignee_id != user.id:
        notification_service.create_notification(
            db,
            user_id=action.assignee_id,
            type="CAPA_ACTION_ASSIGNED",
            title=f"Bạn được giao hành động khắc phục ({entity.nc_code})",
            body=action.action[:200],
            ref_type="nonconformity",
            ref_id=entity.id,
        )
    audit_service.log_action(
        db,
        action="CAPA_ACTION_ADD",
        resource="nonconformity",
        user_id=user.id,
        resource_id=entity.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"nc_code": entity.nc_code, "action_id": str(action.id)},
    )
    db.commit()
    db.refresh(entity)
    return nc.nc_detail_dict(db, entity)


# ===== #8 PATCH /nonconformities/:id/actions/:actionId =====
def update_action(
    db: Session,
    *,
    user: CurrentUser,
    nc_id: uuid.UUID,
    action_id: uuid.UUID,
    new_status: str,
    note: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    nc.assert_can_manage(db, user)
    entity = nc.get_nc_or_404(db, nc_id)
    capa = _capa_editable_or_raise(db, nc_id)

    action = db.get(CapaAction, action_id)
    if action is None or action.capa_id != capa.id:
        raise AppException("ACTION_NOT_FOUND", "Không tìm thấy hành động", 404)
    action.status = new_status
    action.done_at = datetime.now(timezone.utc) if new_status == "done" else None
    if note is not None:
        action.note = note
    audit_service.log_action(
        db,
        action="CAPA_ACTION_UPDATE",
        resource="nonconformity",
        user_id=user.id,
        resource_id=entity.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"nc_code": entity.nc_code, "action_id": str(action_id), "status": new_status},
    )
    db.commit()
    db.refresh(entity)
    return nc.nc_detail_dict(db, entity)


# ===== #9 POST /nonconformities/:id/close =====
def close_capa(
    db: Session,
    *,
    user: CurrentUser,
    nc_id: uuid.UUID,
    effectiveness_result: str,
    effectiveness_note: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    nc.assert_can_manage(db, user)
    entity = nc.get_nc_or_404(db, nc_id, lock=True)
    capa = nc.get_capa_for_nc(db, nc_id)
    if capa is None:
        raise AppException("CAPA_NOT_OPENED", "Phiếu chưa mở CAPA", 409)
    if capa.status == "closed":
        raise AppException("CAPA_CLOSED_IMMUTABLE", "CAPA đã đóng — bất biến", 409)

    # mọi action phải done (§8.7 — không đóng khi còn việc dở)
    open_actions = db.execute(
        select(func.count())
        .select_from(CapaAction)
        .where(CapaAction.capa_id == capa.id, CapaAction.status != "done")
    ).scalar_one()
    if open_actions > 0:
        raise AppException(
            "ACTIONS_INCOMPLETE",
            f"Còn {open_actions} hành động chưa hoàn thành — không thể đóng CAPA",
            422,
        )

    now = datetime.now(timezone.utc)
    capa.status = "closed"
    capa.effectiveness_result = effectiveness_result
    capa.effectiveness_note = effectiveness_note
    capa.verified_by = user.id
    capa.verified_at = now
    capa.closed_by = user.id
    capa.closed_at = now
    entity.status = "closed"
    entity.updated_by = user.id
    entity.updated_at = func.now()

    # Cảnh báo mềm: người đóng == người mở NC (khuyến nghị tách vai — §8.7)
    same_person = entity.raised_by == user.id
    audit_service.log_action(
        db,
        action="CAPA_CLOSE",
        resource="nonconformity",
        user_id=user.id,
        resource_id=entity.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={
            "nc_code": entity.nc_code,
            "effectiveness_result": effectiveness_result,
            "closer_is_raiser": same_person,
        },
    )
    # Thông báo người mở NC rằng phiếu đã được đóng
    if entity.raised_by != user.id:
        notification_service.create_notification(
            db,
            user_id=entity.raised_by,
            type="NC_CLOSED",
            title=f"Phiếu {entity.nc_code} đã được khắc phục & đóng",
            body=f"Hiệu lực: {'Đạt' if effectiveness_result == 'effective' else 'Chưa đạt'}",
            ref_type="nonconformity",
            ref_id=entity.id,
        )
    db.commit()
    db.refresh(entity)
    data = nc.nc_detail_dict(db, entity)
    data["warning"] = (
        "Người đóng CAPA trùng người mở NC — khuyến nghị tách vai (§8.7)"
        if same_person
        else None
    )
    return data


# ===== Helper: CAPA phải tồn tại + đang mở =====
def _capa_editable_or_raise(db: Session, nc_id: uuid.UUID) -> Capa:
    capa = nc.get_capa_for_nc(db, nc_id)
    if capa is None:
        raise AppException("CAPA_NOT_OPENED", "Phiếu chưa mở CAPA", 409)
    if capa.status == "closed":
        raise AppException("CAPA_CLOSED_IMMUTABLE", "CAPA đã đóng — bất biến", 409)
    return capa
