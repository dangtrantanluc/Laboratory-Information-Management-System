"""Result service (M1) — nhập (FR-008), xem theo phạm vi (FR-011, OQ#3), duyệt (FR-010),
trả lại, tạo phiên bản sửa (versioning immutable, D6).

Tách nhập-duyệt (approved_by ≠ entered_by, D8). approved → bất biến + công khai nội bộ.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found, validation_error
from app.models.sample import Sample
from app.models.sample_assignment import SampleAssignment
from app.models.sample_result import SampleResult
from app.services import audit_service, sample_common


def _get_assignment_or_404(db: Session, assignment_id: uuid.UUID) -> SampleAssignment:
    a = db.get(SampleAssignment, assignment_id)
    if a is None:
        raise not_found("Không tìm thấy phân công")
    return a


def _get_result_or_404(db: Session, result_id: uuid.UUID) -> SampleResult:
    r = db.get(SampleResult, result_id)
    if r is None:
        raise not_found("Không tìm thấy kết quả")
    return r


def _current_result(db: Session, assignment_id: uuid.UUID) -> Optional[SampleResult]:
    return db.execute(
        select(SampleResult).where(
            SampleResult.assignment_id == assignment_id,
            SampleResult.is_current.is_(True),
        )
    ).scalar_one_or_none()


def _can_view_pending(
    db: Session, user: CurrentUser, assignment: SampleAssignment, result: SampleResult
) -> bool:
    """Phạm vi xem kết quả CHƯA approved (OQ#3, BR-021):
    entered_by + trưởng nhóm phòng + Admin/Lãnh đạo.
    """
    if sample_common.is_privileged(user):
        return True
    if result.entered_by == user.id:
        return True
    sample = db.get(Sample, assignment.sample_id)
    if sample and sample_common.can_lead_action(user, sample.department_id):
        return True
    return False


def _approval_status(result: SampleResult) -> str:
    return "approved" if result.approved_by is not None else "pending"


# ===== Get result of an assignment (scoped) =====
def get_assignment_result(
    db: Session, *, user: CurrentUser, assignment_id: uuid.UUID
) -> Optional[dict]:
    assignment = _get_assignment_or_404(db, assignment_id)
    result = _current_result(db, assignment_id)
    if result is None:
        return None

    is_approved = result.approved_by is not None
    if not is_approved and not _can_view_pending(db, user, assignment, result):
        # Không lộ nội dung (BR-021)
        return {"_not_published": True}

    return {
        "id": result.id,
        "assignment_id": result.assignment_id,
        "part_name": assignment.part_name,
        "version": result.version,
        "is_current": result.is_current,
        "result_data": result.result_data,
        "entered_by_name": sample_common.user_name(db, result.entered_by),
        "entered_at": result.entered_at,
        "approved_by_name": sample_common.user_name(db, result.approved_by),
        "approved_at": result.approved_at,
        "approval_status": _approval_status(result),
    }


# ===== Enter result (FR-008) =====
def enter_result(
    db: Session,
    *,
    user: CurrentUser,
    assignment_id: uuid.UUID,
    result_data: dict,
    note: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    assignment = _get_assignment_or_404(db, assignment_id)
    sample = sample_common.get_sample_or_404(db, assignment.sample_id, lock=True)

    # chỉ assignee hoặc Admin
    if not (assignment.assigned_to == user.id or user.role == "admin"):
        raise AppException(
            "NOT_ASSIGNEE", "Bạn không phải người được giao phần việc này", 403
        )
    if sample.status in ("done", "returned"):
        raise sample_common.invalid_state("Mẫu đã hoàn tất, không thể nhập kết quả")

    # Đã có kết quả approved → phải revise
    current = _current_result(db, assignment_id)
    if current is not None and current.approved_by is not None:
        raise AppException(
            "RESULT_LOCKED",
            "Kết quả đã duyệt — sửa phải tạo phiên bản mới (revise)",
            422,
        )
    if not result_data:
        raise validation_error("Dữ liệu kết quả không được rỗng")

    # Nếu đã có bản pending hiện hành (nhập lại) → ghi đè bản đó để giữ 1 is_current/version1
    if current is not None and current.approved_by is None:
        current.result_data = result_data
        current.note = note
        current.entered_by = user.id
        current.entered_at = func.now()
        result = current
    else:
        result = SampleResult(
            assignment_id=assignment_id,
            version=1,
            result_data=result_data,
            note=note,
            entered_by=user.id,
            is_current=True,
        )
        db.add(result)
    db.flush()

    assignment.status = "result_entered"
    assignment.updated_by = user.id
    assignment.updated_at = func.now()

    # assigned → testing (lần đầu nhập)
    if sample.status == "assigned":
        sample_common.change_status(
            db,
            sample,
            "testing",
            trigger="result_enter",
            user_id=user.id,
            correlation_id=correlation_id,
            ip=ip,
        )

    audit_service.log_action(
        db,
        action="SAMPLE_RESULT_ENTER",
        resource="sample_result",
        user_id=user.id,
        resource_id=result.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"assignment_id": str(assignment_id), "version": result.version},
    )
    db.commit()
    db.refresh(result)
    db.refresh(sample)
    return {
        "id": result.id,
        "assignment_id": result.assignment_id,
        "version": result.version,
        "result_data": result.result_data,
        "entered_by": result.entered_by,
        "entered_at": result.entered_at,
        "approval_status": "pending",
        "is_current": result.is_current,
        "assignment_status_after": assignment.status,
        "sample_status_after": sample.status,
    }


# ===== Approve (FR-010) =====
def approve_result(
    db: Session,
    *,
    user: CurrentUser,
    result_id: uuid.UUID,
    note: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    result = _get_result_or_404(db, result_id)
    assignment = _get_assignment_or_404(db, result.assignment_id)
    sample = sample_common.get_sample_or_404(db, assignment.sample_id, lock=True)

    if not sample_common.can_lead_action(user, sample.department_id):
        raise sample_common.forbidden("Chỉ trưởng nhóm / lãnh đạo / admin được duyệt")
    if result.approved_by is not None:
        raise AppException("RESULT_ALREADY_APPROVED", "Kết quả đã được duyệt", 422)
    if not result.is_current:
        raise AppException("NO_RESULT_TO_APPROVE", "Không có kết quả hiện hành để duyệt", 422)
    # Tách nhập-duyệt (BR-011)
    if result.entered_by == user.id:
        raise AppException(
            "SELF_APPROVAL_FORBIDDEN", "Không được tự duyệt kết quả của chính mình", 403
        )

    result.approved_by = user.id
    result.approved_at = func.now()
    assignment.status = "approved"
    assignment.updated_by = user.id
    assignment.updated_at = func.now()
    db.flush()

    audit_service.log_action(
        db,
        action="SAMPLE_RESULT_APPROVE",
        resource="sample_result",
        user_id=user.id,
        resource_id=result.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"assignment_id": str(assignment.id), "note": note},
    )
    db.commit()

    total_a, approved_a = (
        db.execute(
            select(func.count())
            .select_from(SampleAssignment)
            .where(SampleAssignment.sample_id == sample.id)
        ).scalar_one(),
        db.execute(
            select(func.count())
            .select_from(SampleAssignment)
            .where(
                SampleAssignment.sample_id == sample.id,
                SampleAssignment.status == "approved",
            )
        ).scalar_one(),
    )
    return {
        "id": result.id,
        "assignment_id": result.assignment_id,
        "version": result.version,
        "approval_status": "approved",
        "approved_by": user.id,
        "approved_at": result.approved_at,
        "is_published": True,
        "assignment_status_after": "approved",
        "sample_status_after": sample.status,
        "sample_can_finalize": total_a > 0 and approved_a == total_a,
    }


# ===== Return for revision (chưa approved) (FR-010 A5) =====
def return_result(
    db: Session,
    *,
    user: CurrentUser,
    result_id: uuid.UUID,
    reason: str,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    result = _get_result_or_404(db, result_id)
    assignment = _get_assignment_or_404(db, result.assignment_id)
    sample = sample_common.get_sample_or_404(db, assignment.sample_id, lock=True)

    if not sample_common.can_lead_action(user, sample.department_id):
        raise sample_common.forbidden("Chỉ trưởng nhóm / lãnh đạo / admin được trả lại")
    if result.approved_by is not None:
        raise AppException(
            "RESULT_ALREADY_APPROVED",
            "Kết quả đã duyệt — phải tạo phiên bản sửa (revise)",
            422,
        )

    assignment.status = "assigned"
    assignment.updated_by = user.id
    assignment.updated_at = func.now()
    db.flush()

    audit_service.log_action(
        db,
        action="SAMPLE_RESULT_RETURN",
        resource="sample_result",
        user_id=user.id,
        resource_id=result.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"reason": reason.strip()},
    )
    db.commit()
    return {
        "id": result.id,
        "assignment_status_after": "assigned",
        "approval_status": "returned",
    }


# ===== Revise approved (versioning) (FR-010) =====
def revise_result(
    db: Session,
    *,
    user: CurrentUser,
    result_id: uuid.UUID,
    result_data: dict,
    reason: str,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    result = _get_result_or_404(db, result_id)
    assignment = _get_assignment_or_404(db, result.assignment_id)
    sample = sample_common.get_sample_or_404(db, assignment.sample_id, lock=True)

    # người nhập / trưởng nhóm / Admin
    is_owner = result.entered_by == user.id
    if not (is_owner or sample_common.can_lead_action(user, sample.department_id)):
        raise AppException(
            "RESULT_NOT_OWNER", "Bạn không có quyền sửa kết quả này", 403
        )
    if result.approved_by is None:
        raise AppException(
            "RESULT_NOT_APPROVED",
            "Kết quả chưa duyệt — sửa trực tiếp được, không cần tạo phiên bản",
            422,
        )
    if not (reason and reason.strip()):
        raise AppException(
            "REVISION_REASON_REQUIRED", "Tạo phiên bản sửa phải có lý do", 400
        )
    if not result_data:
        raise validation_error("Dữ liệu kết quả không được rỗng")

    # đóng bản cũ, mở version mới
    result.is_current = False
    db.flush()
    new_result = SampleResult(
        assignment_id=assignment.id,
        version=result.version + 1,
        result_data=result_data,
        entered_by=user.id,
        is_current=True,
        revision_reason=reason.strip(),
    )
    db.add(new_result)
    assignment.status = "result_entered"
    assignment.updated_by = user.id
    assignment.updated_at = func.now()
    db.flush()

    audit_service.log_action(
        db,
        action="SAMPLE_RESULT_REVISE",
        resource="sample_result",
        user_id=user.id,
        resource_id=new_result.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={
            "assignment_id": str(assignment.id),
            "previous_version": result.version,
            "new_version": new_result.version,
            "reason": reason.strip(),
        },
    )
    db.commit()
    db.refresh(new_result)
    return {
        "id": new_result.id,
        "assignment_id": new_result.assignment_id,
        "version": new_result.version,
        "is_current": True,
        "approval_status": "pending",
        "is_published": False,
        "previous_version_id": result.id,
        "previous_version": result.version,
        "revision_reason": new_result.revision_reason,
    }


# ===== Sample results summary (FR-011) =====
def sample_results_summary(
    db: Session, *, user: CurrentUser, sample_id: uuid.UUID
) -> dict:
    sample = sample_common.get_sample_or_404(db, sample_id)
    assignments = db.execute(
        select(SampleAssignment)
        .where(SampleAssignment.sample_id == sample_id)
        .order_by(SampleAssignment.assigned_at.asc())
    ).scalars().all()

    results = []
    for a in assignments:
        result = _current_result(db, a.id)
        if result is None:
            results.append(
                {
                    "assignment_id": a.id,
                    "part_name": a.part_name,
                    "approval_status": "pending",
                    "is_published": False,
                    "result_data": None,
                    "note": "Chưa có kết quả",
                }
            )
            continue
        is_approved = result.approved_by is not None
        can_view = is_approved or _can_view_pending(db, user, a, result)
        results.append(
            {
                "assignment_id": a.id,
                "part_name": a.part_name,
                "version": result.version,
                "approval_status": _approval_status(result),
                "is_published": is_approved,
                "result_data": result.result_data if can_view else None,
                "entered_by_name": sample_common.user_name(db, result.entered_by)
                if can_view
                else None,
                "approved_by_name": sample_common.user_name(db, result.approved_by),
                "note": None if can_view else "Chưa có kết quả công khai",
            }
        )
    return {
        "sample_id": sample.id,
        "sample_code": sample.sample_code,
        "results": results,
    }


def get_result_for_attachment(db: Session, result_id: uuid.UUID) -> SampleResult:
    return _get_result_or_404(db, result_id)
