"""Assignment + handover service (M1) — phân công (FR-005), chuyển giao (FR-006/007).

Phân công/hủy: chỉ trưởng nhóm phòng / Admin / Lãnh đạo (BR-022). Handover: custodian
hiện tại / trưởng nhóm / Admin (BR-007), chain of custody bất biến.
"""
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found
from app.models.sample_assignment import SampleAssignment
from app.models.sample_handover import SampleHandover
from app.models.sample_result import SampleResult
from app.models.user import User
from app.services import audit_service, notification_service, sample_common


def list_assignments(db: Session, *, sample_id: uuid.UUID) -> list[dict]:
    sample_common.get_sample_or_404(db, sample_id)
    rows = db.execute(
        select(SampleAssignment)
        .where(SampleAssignment.sample_id == sample_id)
        .order_by(SampleAssignment.assigned_at.asc())
    ).scalars().all()
    items = []
    for a in rows:
        has_result = db.execute(
            select(func.count())
            .select_from(SampleResult)
            .where(SampleResult.assignment_id == a.id)
        ).scalar_one() > 0
        items.append(
            {
                "id": a.id,
                "sample_id": a.sample_id,
                "part_name": a.part_name,
                "assigned_to": a.assigned_to,
                "assigned_to_name": sample_common.user_name(db, a.assigned_to),
                "assigned_by": a.assigned_by,
                "assigned_by_name": sample_common.user_name(db, a.assigned_by),
                "status": a.status,
                "assigned_at": a.assigned_at,
                "has_result": has_result,
            }
        )
    return items


def create_assignment(
    db: Session,
    *,
    user: CurrentUser,
    sample_id: uuid.UUID,
    part_name: str,
    assigned_to: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    sample = sample_common.get_sample_or_404(db, sample_id, lock=True)

    if not sample_common.can_lead_action(user, sample.department_id):
        raise sample_common.forbidden(
            "Chỉ trưởng nhóm / lãnh đạo / admin được phân công"
        )
    if sample.status in ("done", "returned"):
        raise sample_common.invalid_state("Mẫu đã hoàn tất, không thể phân công thêm")

    assignee = db.get(User, assigned_to)
    if assignee is None or assignee.status != "active":
        raise AppException("ASSIGNEE_NOT_FOUND", "Không tìm thấy người được giao", 404)
    if assignee.department_id != sample.department_id:
        raise AppException(
            "ASSIGNEE_OUT_OF_DEPT",
            "Người được giao phải cùng phòng ban với mẫu",
            422,
        )

    assignment = SampleAssignment(
        sample_id=sample.id,
        assigned_to=assigned_to,
        assigned_by=user.id,
        part_name=part_name.strip(),
        status="assigned",
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(assignment)
    db.flush()

    # received → assigned
    if sample.status == "received":
        sample_common.change_status(
            db,
            sample,
            "assigned",
            trigger="assign",
            user_id=user.id,
            correlation_id=correlation_id,
            ip=ip,
        )

    notification_service.create_notification(
        db,
        user_id=assigned_to,
        type="SAMPLE_ASSIGNED",
        title="Bạn được phân công phần việc mới",
        body=f"Mẫu {sample.sample_code} — {part_name.strip()}",
        ref_type="sample",
        ref_id=sample.id,
    )
    audit_service.log_action(
        db,
        action="SAMPLE_ASSIGN",
        resource="sample_assignment",
        user_id=user.id,
        resource_id=assignment.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"sample_id": str(sample.id), "part_name": part_name.strip()},
    )
    db.commit()
    db.refresh(assignment)
    db.refresh(sample)
    return {
        "id": assignment.id,
        "sample_id": assignment.sample_id,
        "part_name": assignment.part_name,
        "assigned_to": assignment.assigned_to,
        "assigned_by": assignment.assigned_by,
        "status": assignment.status,
        "assigned_at": assignment.assigned_at,
        "sample_status_after": sample.status,
    }


def cancel_assignment(
    db: Session,
    *,
    user: CurrentUser,
    assignment_id: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> None:
    assignment = db.execute(
        select(SampleAssignment)
        .where(SampleAssignment.id == assignment_id)
    ).scalar_one_or_none()
    if assignment is None:
        raise not_found("Không tìm thấy phân công")

    sample = sample_common.get_sample_or_404(db, assignment.sample_id, lock=True)
    if not sample_common.can_lead_action(user, sample.department_id):
        raise sample_common.forbidden("Chỉ trưởng nhóm / lãnh đạo / admin được hủy phân công")

    has_result = db.execute(
        select(func.count())
        .select_from(SampleResult)
        .where(SampleResult.assignment_id == assignment.id)
    ).scalar_one() > 0
    if has_result:
        raise AppException(
            "RESULT_EXISTS", "Phân công đã có kết quả, không thể hủy", 422
        )

    db.delete(assignment)
    db.flush()

    audit_service.log_action(
        db,
        action="SAMPLE_ASSIGN_CANCEL",
        resource="sample_assignment",
        user_id=user.id,
        resource_id=assignment_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"sample_id": str(sample.id), "part_name": assignment.part_name},
    )
    # Nếu mẫu không còn assignment nào & đang 'assigned' → quay về 'received'
    remaining = db.execute(
        select(func.count())
        .select_from(SampleAssignment)
        .where(SampleAssignment.sample_id == sample.id)
    ).scalar_one()
    if remaining == 0 and sample.status == "assigned":
        sample_common.change_status(
            db,
            sample,
            "received",
            trigger="assign_cancel",
            user_id=user.id,
            correlation_id=correlation_id,
            ip=ip,
        )
    db.commit()


# ===== Handover (FR-006/007) =====
def create_handover(
    db: Session,
    *,
    user: CurrentUser,
    sample_id: uuid.UUID,
    to_user: uuid.UUID,
    reason: str,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    sample = sample_common.get_sample_or_404(db, sample_id, lock=True)

    if sample.status == "returned":
        raise sample_common.invalid_state("Mẫu đã trả kết quả, không thể chuyển giao")

    # custodian hiện tại / trưởng nhóm / Admin / Lãnh đạo
    is_custodian = sample.current_custodian_id == user.id
    if not (is_custodian or sample_common.can_lead_action(user, sample.department_id)):
        raise AppException(
            "NOT_CURRENT_CUSTODIAN",
            "Bạn không phải người giữ mẫu hiện tại",
            403,
        )

    recipient = db.get(User, to_user)
    if recipient is None or recipient.status != "active":
        raise not_found("Không tìm thấy người nhận")
    if recipient.department_id != sample.department_id:
        raise AppException(
            "HANDOVER_OUT_OF_DEPT", "Người nhận phải cùng phòng ban với mẫu", 422
        )
    if to_user == sample.current_custodian_id:
        raise AppException(
            "INVALID_HANDOVER", "Người nhận đang là người giữ mẫu hiện tại", 422
        )

    from_user = sample.current_custodian_id
    handover = SampleHandover(
        sample_id=sample.id,
        from_user=from_user,
        to_user=to_user,
        reason=reason.strip(),
    )
    db.add(handover)
    sample.current_custodian_id = to_user
    sample.updated_by = user.id
    sample.updated_at = func.now()
    db.flush()

    notification_service.create_notification(
        db,
        user_id=to_user,
        type="SAMPLE_HANDOVER",
        title="Bạn được chuyển giao mẫu",
        body=f"Mẫu {sample.sample_code} — {reason.strip()}",
        ref_type="sample",
        ref_id=sample.id,
    )
    audit_service.log_action(
        db,
        action="SAMPLE_HANDOVER",
        resource="sample",
        user_id=user.id,
        resource_id=sample.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"from_user": str(from_user), "to_user": str(to_user)},
    )
    db.commit()
    db.refresh(handover)
    return {
        "id": handover.id,
        "sample_id": handover.sample_id,
        "from_user": handover.from_user,
        "from_user_name": sample_common.user_name(db, handover.from_user),
        "to_user": handover.to_user,
        "to_user_name": sample_common.user_name(db, handover.to_user),
        "reason": handover.reason,
        "at": handover.at,
        "current_custodian_id": to_user,
    }


def get_custody_chain(db: Session, *, sample_id: uuid.UUID) -> list[dict]:
    sample = sample_common.get_sample_or_404(db, sample_id)
    handovers = db.execute(
        select(SampleHandover)
        .where(SampleHandover.sample_id == sample_id)
        .order_by(SampleHandover.at.asc())
    ).scalars().all()

    chain: list[dict] = []
    # Đoạn đầu: received_by giữ từ received_at
    seg_user = sample.received_by
    seg_from = sample.received_at
    seg_reason = "Tiếp nhận ban đầu"
    for ho in handovers:
        chain.append(
            {
                "custodian_id": seg_user,
                "custodian_name": sample_common.user_name(db, seg_user),
                "from": seg_from,
                "to": ho.at,
                "reason": seg_reason,
            }
        )
        seg_user = ho.to_user
        seg_from = ho.at
        seg_reason = ho.reason
    # Đoạn hiện tại
    chain.append(
        {
            "custodian_id": seg_user,
            "custodian_name": sample_common.user_name(db, seg_user),
            "from": seg_from,
            "to": None,
            "reason": seg_reason,
            "is_current": True,
        }
    )
    return chain
