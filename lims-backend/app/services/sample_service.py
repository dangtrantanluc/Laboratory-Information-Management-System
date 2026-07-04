"""Sample service (M1) — mẫu, tình trạng, deadline, danh sách, chốt done, lý do trễ,
on-time report, QR (FR-001/002/004/012/013/014/015/016/019).

State transitions qua sample_common.change_status (whitelist + audit). Mọi thao tác ghi
trong transaction với row-lock khi đụng trạng thái (finalize). Cấm Kế toán toàn bộ.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found, validation_error
from app.models.overdue_reason import OverdueReason
from app.models.sample import Sample
from app.models.sample_assignment import SampleAssignment
from app.models.test_request import TestRequest
from app.services import audit_service, sample_common


def _is_overdue(sample: Sample) -> bool:
    if sample.status in ("done", "returned"):
        return False
    if sample.status == "overdue":
        return True
    now = datetime.now(timezone.utc)
    return sample.deadline_at < now


def _assignment_stats(db: Session, sample_id: uuid.UUID) -> tuple[int, int]:
    total = db.execute(
        select(func.count())
        .select_from(SampleAssignment)
        .where(SampleAssignment.sample_id == sample_id)
    ).scalar_one()
    approved = db.execute(
        select(func.count())
        .select_from(SampleAssignment)
        .where(
            SampleAssignment.sample_id == sample_id,
            SampleAssignment.status == "approved",
        )
    ).scalar_one()
    return total, approved


# ===== Add sample to request =====
def add_sample(
    db: Session,
    *,
    user: CurrentUser,
    request_id: uuid.UUID,
    description: str,
    deadline_at: datetime,
    condition_status: Optional[str],
    condition_note: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    req = db.execute(
        select(TestRequest).where(
            TestRequest.id == request_id, TestRequest.deleted_at.is_(None)
        )
    ).scalar_one_or_none()
    if req is None:
        raise not_found("Không tìm thấy phiếu yêu cầu")

    sample_common.assert_write_scope(user, req.department_id)

    if deadline_at <= req.received_at:
        raise AppException(
            "INVALID_DEADLINE", "Hạn hoàn thành phải sau ngày nhận mẫu", 422
        )
    if condition_status == "not_acceptable" and not (condition_note and condition_note.strip()):
        raise AppException(
            "CONDITION_REASON_REQUIRED",
            "Mẫu không đạt điều kiện phải ghi lý do",
            400,
        )

    for _ in range(5):
        code = sample_common.next_sample_code(db)
        sample = Sample(
            sample_code=code,
            request_id=req.id,
            department_id=req.department_id,
            received_by=req.received_by,
            current_custodian_id=req.received_by,
            description=description.strip(),
            received_at=req.received_at,
            deadline_at=deadline_at,
            status="received",
            condition_status=condition_status,
            condition_note=condition_note,
            created_by=user.id,
            updated_by=user.id,
        )
        db.add(sample)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            # reload req sau rollback
            req = db.get(TestRequest, request_id)
    else:
        raise AppException(
            "INTERNAL_ERROR", "Không sinh được mã mẫu, vui lòng thử lại", 500
        )

    audit_service.log_action(
        db,
        action="SAMPLE_CREATE",
        resource="sample",
        user_id=user.id,
        resource_id=sample.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"sample_code": sample.sample_code, "request_id": str(req.id)},
    )
    if condition_status is not None:
        audit_service.log_action(
            db,
            action="SAMPLE_CONDITION_RECORD",
            resource="sample",
            user_id=user.id,
            resource_id=sample.id,
            correlation_id=correlation_id,
            ip=ip,
            detail={"condition_status": condition_status},
        )
    db.commit()
    db.refresh(sample)
    return {
        "id": sample.id,
        "sample_code": sample.sample_code,
        "request_id": sample.request_id,
        "request_code": req.request_code,
        "department_id": sample.department_id,
        "received_by": sample.received_by,
        "received_at": sample.received_at,
        "deadline_at": sample.deadline_at,
        "description": sample.description,
        "status": sample.status,
        "condition_status": sample.condition_status,
        "condition_note": sample.condition_note,
        "current_custodian_id": sample.current_custodian_id,
        "qr_payload": sample.sample_code,
        "created_at": sample.created_at,
    }


# ===== List / search =====
def list_samples(
    db: Session,
    *,
    q: Optional[str],
    status_filter: Optional[str],
    department_id: Optional[uuid.UUID],
    assigned_to: Optional[uuid.UUID],
    assigned_by: Optional[uuid.UUID],
    custodian_id: Optional[uuid.UUID],
    request_id: Optional[uuid.UUID],
    deadline_from: Optional[datetime],
    deadline_to: Optional[datetime],
    overdue_only: bool,
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = [Sample.deleted_at.is_(None)]
    if q:
        conditions.append(
            (Sample.sample_code.ilike(f"%{q}%")) | (Sample.description.ilike(f"%{q}%"))
        )
    if status_filter:
        conditions.append(Sample.status == status_filter)
    if department_id:
        conditions.append(Sample.department_id == department_id)
    if custodian_id:
        conditions.append(Sample.current_custodian_id == custodian_id)
    if request_id:
        conditions.append(Sample.request_id == request_id)
    if deadline_from:
        conditions.append(Sample.deadline_at >= deadline_from)
    if deadline_to:
        conditions.append(Sample.deadline_at <= deadline_to)
    if overdue_only:
        conditions.append(Sample.status == "overdue")

    if assigned_to or assigned_by:
        sub = select(SampleAssignment.sample_id)
        if assigned_to:
            sub = sub.where(SampleAssignment.assigned_to == assigned_to)
        if assigned_by:
            sub = sub.where(SampleAssignment.assigned_by == assigned_by)
        conditions.append(Sample.id.in_(sub))

    total = db.execute(
        select(func.count()).select_from(Sample).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(Sample)
        .where(*conditions)
        .order_by(Sample.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()

    items = []
    for s in rows:
        total_a, approved_a = _assignment_stats(db, s.id)
        req = db.get(TestRequest, s.request_id)
        items.append(
            {
                "id": s.id,
                "sample_code": s.sample_code,
                "request_code": req.request_code if req else None,
                "department_name": sample_common.dept_name(db, s.department_id),
                "status": s.status,
                "deadline_at": s.deadline_at,
                "is_overdue": _is_overdue(s),
                "current_custodian_name": sample_common.user_name(
                    db, s.current_custodian_id
                ),
                "assignment_count": total_a,
                "approved_count": approved_a,
                "created_at": s.created_at,
            }
        )
    return items, total


def list_request_samples(
    db: Session, *, request_id: uuid.UUID, page: int, limit: int
) -> tuple[list[dict], int]:
    req = db.execute(
        select(TestRequest).where(
            TestRequest.id == request_id, TestRequest.deleted_at.is_(None)
        )
    ).scalar_one_or_none()
    if req is None:
        raise not_found("Không tìm thấy phiếu yêu cầu")
    conditions = [Sample.request_id == request_id, Sample.deleted_at.is_(None)]
    total = db.execute(
        select(func.count()).select_from(Sample).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(Sample)
        .where(*conditions)
        .order_by(Sample.created_at.asc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    items = [
        {
            "id": s.id,
            "sample_code": s.sample_code,
            "status": s.status,
            "deadline_at": s.deadline_at,
            "condition_status": s.condition_status,
        }
        for s in rows
    ]
    return items, total


def get_sample_detail(db: Session, sample_id: uuid.UUID) -> dict:
    sample = sample_common.get_sample_or_404(db, sample_id)
    req = db.get(TestRequest, sample.request_id)
    customer_name = None
    if req and req.customer_id:
        from app.models.customer import Customer

        c = db.get(Customer, req.customer_id)
        customer_name = c.name if c else None

    assignments = db.execute(
        select(SampleAssignment)
        .where(SampleAssignment.sample_id == sample.id)
        .order_by(SampleAssignment.assigned_at.asc())
    ).scalars().all()
    total_a, approved_a = _assignment_stats(db, sample.id)
    can_finalize = total_a > 0 and approved_a == total_a

    return {
        "id": sample.id,
        "sample_code": sample.sample_code,
        "request_id": sample.request_id,
        "request_code": req.request_code if req else None,
        "customer_name": customer_name,
        "department_id": sample.department_id,
        "department_name": sample_common.dept_name(db, sample.department_id),
        "description": sample.description,
        "received_at": sample.received_at,
        "deadline_at": sample.deadline_at,
        "status": sample.status,
        "is_overdue": _is_overdue(sample),
        "completed_at": sample.completed_at,
        "condition_status": sample.condition_status,
        "condition_note": sample.condition_note,
        "current_custodian": {
            "id": sample.current_custodian_id,
            "name": sample_common.user_name(db, sample.current_custodian_id),
        },
        "assignments": [
            {
                "id": a.id,
                "part_name": a.part_name,
                "assigned_to": a.assigned_to,
                "assigned_to_name": sample_common.user_name(db, a.assigned_to),
                "assigned_by_name": sample_common.user_name(db, a.assigned_by),
                "status": a.status,
                "assigned_at": a.assigned_at,
            }
            for a in assignments
        ],
        "can_finalize": can_finalize,
        "created_at": sample.created_at,
    }


def update_sample(
    db: Session,
    *,
    user: CurrentUser,
    sample_id: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    sample = sample_common.get_sample_or_404(db, sample_id, lock=True)
    sample_common.assert_write_scope(user, sample.department_id)
    if sample.status == "returned":
        raise sample_common.invalid_state("Không thể sửa mẫu đã trả kết quả")

    diff: dict = {}
    if "description" in changes and changes["description"] is not None:
        sample.description = changes["description"].strip()
        diff["description"] = sample.description
    if not diff:
        raise validation_error("Không có thay đổi nào hợp lệ")

    sample.updated_by = user.id
    sample.updated_at = func.now()
    audit_service.log_action(
        db,
        action="SAMPLE_UPDATE",
        resource="sample",
        user_id=user.id,
        resource_id=sample.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"diff": diff},
    )
    db.commit()
    return get_sample_detail(db, sample_id)


def update_condition(
    db: Session,
    *,
    user: CurrentUser,
    sample_id: uuid.UUID,
    condition_status: str,
    condition_note: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    sample = sample_common.get_sample_or_404(db, sample_id, lock=True)
    sample_common.assert_write_scope(user, sample.department_id)
    if condition_status == "not_acceptable" and not (condition_note and condition_note.strip()):
        raise AppException(
            "CONDITION_REASON_REQUIRED", "Mẫu không đạt điều kiện phải ghi lý do", 400
        )
    sample.condition_status = condition_status
    sample.condition_note = condition_note
    sample.updated_by = user.id
    sample.updated_at = func.now()
    audit_service.log_action(
        db,
        action="SAMPLE_CONDITION_RECORD",
        resource="sample",
        user_id=user.id,
        resource_id=sample.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"condition_status": condition_status},
    )
    db.commit()
    db.refresh(sample)
    return {
        "id": sample.id,
        "condition_status": sample.condition_status,
        "condition_note": sample.condition_note,
    }


def update_deadline(
    db: Session,
    *,
    user: CurrentUser,
    sample_id: uuid.UUID,
    deadline_at: datetime,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    sample = sample_common.get_sample_or_404(db, sample_id, lock=True)
    sample_common.assert_write_scope(user, sample.department_id)
    if sample.status == "returned":
        raise sample_common.invalid_state("Không thể sửa deadline mẫu đã trả kết quả")
    if deadline_at <= sample.received_at:
        raise AppException("INVALID_DEADLINE", "Hạn mới phải sau ngày nhận mẫu", 422)

    previous = sample.deadline_at
    sample.deadline_at = deadline_at
    sample.updated_by = user.id
    sample.updated_at = func.now()
    audit_service.log_action(
        db,
        action="SAMPLE_DEADLINE_SET",
        resource="sample",
        user_id=user.id,
        resource_id=sample.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"old": previous.isoformat(), "new": deadline_at.isoformat()},
    )
    db.commit()
    db.refresh(sample)
    return {
        "id": sample.id,
        "deadline_at": sample.deadline_at,
        "previous_deadline_at": previous,
    }


def get_qr(db: Session, *, sample_id: uuid.UUID) -> dict:
    sample = sample_common.get_sample_or_404(db, sample_id)
    return {
        "sample_code": sample.sample_code,
        "qr_payload": sample.sample_code,
        "qr_image_url": None,
        "url_expires_at": None,
    }


# ===== Overdue listing (FR-013/014) =====
def list_overdue(
    db: Session,
    *,
    mode: str,
    within_days: int,
    department_id: Optional[uuid.UUID],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    now = datetime.now(timezone.utc)
    conditions = [
        Sample.deleted_at.is_(None),
        Sample.status.notin_(["done", "returned"]),
    ]
    if department_id:
        conditions.append(Sample.department_id == department_id)
    if mode == "due_soon":
        horizon = now + timedelta(days=within_days)
        conditions.append(Sample.deadline_at >= now)
        conditions.append(Sample.deadline_at <= horizon)
    else:  # overdue
        conditions.append(Sample.deadline_at < now)

    total = db.execute(
        select(func.count()).select_from(Sample).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(Sample)
        .where(*conditions)
        .order_by(Sample.deadline_at.asc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()

    items = []
    for s in rows:
        days_overdue = max(0, (now - s.deadline_at).days) if s.deadline_at < now else 0
        has_reason = db.execute(
            select(func.count())
            .select_from(OverdueReason)
            .where(OverdueReason.sample_id == s.id)
        ).scalar_one() > 0
        assignees = db.execute(
            select(SampleAssignment.assigned_to).where(
                SampleAssignment.sample_id == s.id
            )
        ).scalars().all()
        assignee_names = [sample_common.user_name(db, a) for a in assignees]
        items.append(
            {
                "id": s.id,
                "sample_code": s.sample_code,
                "department_name": sample_common.dept_name(db, s.department_id),
                "status": s.status,
                "deadline_at": s.deadline_at,
                "days_overdue": days_overdue,
                "has_overdue_reason": has_reason,
                "assignee_names": [n for n in assignee_names if n],
            }
        )
    return items, total


# ===== Overdue reason (FR-014) =====
def add_overdue_reason(
    db: Session,
    *,
    user: CurrentUser,
    sample_id: uuid.UUID,
    reason: str,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    sample = sample_common.get_sample_or_404(db, sample_id, lock=True)
    sample_common.assert_write_scope(user, sample.department_id)
    if sample.status != "overdue":
        raise AppException(
            "SAMPLE_NOT_OVERDUE", "Mẫu không ở trạng thái trễ hạn", 422
        )
    ovr = OverdueReason(sample_id=sample.id, reason=reason.strip(), by_user=user.id)
    db.add(ovr)
    db.flush()
    audit_service.log_action(
        db,
        action="SAMPLE_OVERDUE_REASON",
        resource="sample",
        user_id=user.id,
        resource_id=sample.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"reason": reason.strip()[:200]},
    )
    db.commit()
    db.refresh(ovr)
    return {
        "id": ovr.id,
        "sample_id": ovr.sample_id,
        "reason": ovr.reason,
        "by": ovr.by_user,
        "at": ovr.at,
    }


# ===== Finalize (FR-019) =====
def finalize_sample(
    db: Session,
    *,
    user: CurrentUser,
    sample_id: uuid.UUID,
    note: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    sample = sample_common.get_sample_or_404(db, sample_id, lock=True)

    if not sample_common.can_lead_action(user, sample.department_id):
        raise sample_common.forbidden("Chỉ trưởng nhóm / lãnh đạo / admin được chốt mẫu")

    if sample.status not in ("testing", "overdue"):
        raise sample_common.invalid_state(
            "Chỉ chốt được mẫu đang thử nghiệm hoặc trễ hạn"
        )

    # 1. mọi assignment approved (BR-020) — trong transaction
    total_a, approved_a = _assignment_stats(db, sample.id)
    if total_a == 0 or approved_a != total_a:
        raise AppException(
            "RESULTS_NOT_APPROVED",
            "Còn phần việc chưa được duyệt, không thể chốt mẫu",
            422,
        )

    # 2. nếu đang overdue: phải có >=1 overdue_reason (BR-009)
    was_overdue = sample.status == "overdue"
    if was_overdue:
        has_reason = db.execute(
            select(func.count())
            .select_from(OverdueReason)
            .where(OverdueReason.sample_id == sample.id)
        ).scalar_one() > 0
        if not has_reason:
            raise AppException(
                "OVERDUE_REASON_REQUIRED",
                "Mẫu trễ hạn phải nhập lý do trễ trước khi chốt",
                422,
            )

    now = datetime.now(timezone.utc)
    sample_common.change_status(
        db,
        sample,
        "done",
        trigger="finalize",
        user_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
    )
    sample.completed_at = now
    sample.updated_by = user.id
    sample.updated_at = func.now()
    is_late = sample.completed_at > sample.deadline_at

    approved_parts = db.execute(
        select(SampleAssignment.part_name).where(
            SampleAssignment.sample_id == sample.id,
            SampleAssignment.status == "approved",
        )
    ).scalars().all()

    audit_service.log_action(
        db,
        action="SAMPLE_FINALIZE",
        resource="sample",
        user_id=user.id,
        resource_id=sample.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"approved_parts": list(approved_parts), "is_late": is_late, "note": note},
    )
    db.commit()
    db.refresh(sample)
    return {
        "id": sample.id,
        "sample_code": sample.sample_code,
        "status": sample.status,
        "completed_at": sample.completed_at,
        "was_overdue": was_overdue,
        "is_late": is_late,
        "approved_parts": list(approved_parts),
    }


# ===== On-time report (FR-015) =====
def on_time_report(
    db: Session,
    *,
    user: CurrentUser,
    date_from: datetime,
    date_to: datetime,
    group_by: str,
    department_id: Optional[uuid.UUID],
) -> dict:
    conditions = [
        Sample.completed_at.isnot(None),
        Sample.completed_at >= date_from,
        Sample.completed_at <= date_to,
    ]
    # KTV bị ép phòng mình
    if not sample_common.is_privileged(user):
        if user.department_id is not None:
            conditions.append(Sample.department_id == user.department_id)
    elif department_id:
        conditions.append(Sample.department_id == department_id)

    samples = db.execute(select(Sample).where(*conditions)).scalars().all()

    total_done = len(samples)
    on_time = sum(1 for s in samples if s.completed_at <= s.deadline_at)
    late = total_done - on_time
    rate = round(on_time / total_done * 100, 1) if total_done else 0.0

    # breakdown
    groups: dict = {}
    for s in samples:
        if group_by == "user":
            key_id = s.received_by
            key_name = sample_common.user_name(db, s.received_by) or str(s.received_by)
        else:
            key_id = s.department_id
            key_name = sample_common.dept_name(db, s.department_id) or str(s.department_id)
        g = groups.setdefault(
            key_name, {"group": key_name, "total_done": 0, "on_time": 0, "late": 0}
        )
        g["total_done"] += 1
        if s.completed_at <= s.deadline_at:
            g["on_time"] += 1
        else:
            g["late"] += 1
    breakdown = []
    for g in groups.values():
        g["on_time_rate"] = (
            round(g["on_time"] / g["total_done"] * 100, 1) if g["total_done"] else 0.0
        )
        breakdown.append(g)

    late_samples = []
    for s in samples:
        if s.completed_at > s.deadline_at:
            ovr = db.execute(
                select(OverdueReason)
                .where(OverdueReason.sample_id == s.id)
                .order_by(OverdueReason.at.desc())
                .limit(1)
            ).scalar_one_or_none()
            late_samples.append(
                {
                    "sample_code": s.sample_code,
                    "deadline_at": s.deadline_at,
                    "completed_at": s.completed_at,
                    "overdue_reason": ovr.reason if ovr else None,
                }
            )

    return {
        "period": {"from": date_from.date().isoformat(), "to": date_to.date().isoformat()},
        "summary": {
            "total_done": total_done,
            "on_time": on_time,
            "late": late,
            "on_time_rate": rate,
        },
        "breakdown": breakdown,
        "late_samples": late_samples,
    }
