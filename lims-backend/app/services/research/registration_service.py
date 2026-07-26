"""Đăng ký sử dụng lab (#33-#34c) — có bước duyệt.

Tách từ research_service.py (1.736 dòng, 9 domain) — M-03/T1.1.
Xem app/services/research/__init__.py để biết vì sao có mặt tiền tương thích.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.hr import (
    LabRegistration,
)
from app.services import audit_service, hr_common as hc


def _registration_dict(db: Session, r: LabRegistration) -> dict:
    return {
        "id": r.id,
        "student_name": r.student_name,
        "mentor_id": r.mentor_id,
        "mentor_name": hc.user_name(db, r.mentor_id),
        "registered_at": r.registered_at.isoformat() if r.registered_at else None,
        "registered_from": r.registered_from.isoformat() if r.registered_from else None,
        "registered_to": r.registered_to.isoformat() if r.registered_to else None,
        "purpose": r.purpose,
        "status": r.status,
        "department_id": r.department_id,
        "decided_by_user_id": r.approved_by,
        "decided_at": r.approved_at,
        "created_at": r.created_at,
    }


def list_registrations(
    db: Session,
    *,
    user: CurrentUser,
    status_filter: Optional[str],
    mentor_id: Optional[uuid.UUID],
    department_id: Optional[uuid.UUID],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    if status_filter:
        conditions.append(LabRegistration.status == status_filter)
    eff_mentor = mentor_id
    if not hc.is_research_all(user):
        eff_mentor = user.id
    if eff_mentor:
        conditions.append(LabRegistration.mentor_id == eff_mentor)
    if department_id:
        conditions.append(LabRegistration.department_id == department_id)
    total = db.execute(
        select(func.count()).select_from(LabRegistration).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(LabRegistration)
        .where(*conditions)
        .order_by(LabRegistration.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return [_registration_dict(db, r) for r in rows], total


def create_registration(
    db: Session,
    *,
    user: CurrentUser,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    mentor_id = payload.get("mentor_id")
    if not mentor_id:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu mentor_id", 400)
    if user.role == "staff" and mentor_id != user.id:
        raise hc.forbidden("Bạn chỉ tạo đăng ký với mentor là chính mình")
    hc.assert_user_exists(db, mentor_id)
    if not payload.get("student_name"):
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu student_name", 400)
    if not payload.get("registered_from"):
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu registered_from", 400)
    if not payload.get("purpose"):
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu purpose", 400)
    reg_from = payload.get("registered_from")
    reg_to = payload.get("registered_to")
    if reg_to and reg_from and reg_to < reg_from:
        raise AppException(ErrorCode.INVALID_DATE_ORDER, "registered_to < registered_from", 422)
    r = LabRegistration(
        student_name=str(payload["student_name"]).strip(),
        mentor_id=mentor_id,
        registered_from=reg_from,
        registered_to=reg_to,
        purpose=payload.get("purpose"),
        status="pending",
        department_id=hc.user_dept(db, mentor_id),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(r)
    db.flush()
    audit_service.log_action(
        db,
        action="LAB_REGISTRATION_CREATE",
        resource="lab_registration",
        user_id=user.id,
        resource_id=r.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"mentor_id": str(mentor_id)},
    )
    db.commit()
    db.refresh(r)
    return _registration_dict(db, r)


def _can_decide_registration(db: Session, user: CurrentUser, r: LabRegistration) -> bool:
    """admin/leader; mentor của lượt; trưởng nhóm phòng của mentor (is_dept_lead)."""
    if user.role in ("admin", "leader"):
        return True
    if r.mentor_id == user.id:
        return True
    # trưởng nhóm phòng mentor
    mentor_dept = hc.user_dept(db, r.mentor_id)
    if user.is_dept_lead and mentor_dept is not None and user.department_id == mentor_dept:
        return True
    return False


def decide_registration(
    db: Session,
    *,
    user: CurrentUser,
    reg_id: uuid.UUID,
    decision: str,  # 'approved' | 'rejected'
    reason: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    # Khoá hàng trước khi check-then-act để 2 request duyệt/từ chối đồng thời KHÔNG cùng
    # vượt qua guard 'pending' → double-decision (PRODUCTION_READINESS_REVIEW M6). Không có
    # ràng buộc DB nào chặn việc này, nên FOR UPDATE là cơ chế duy nhất đảm bảo tuần tự hoá.
    r = db.execute(
        select(LabRegistration).where(LabRegistration.id == reg_id).with_for_update()
    ).scalar_one_or_none()
    if r is None:
        raise AppException(ErrorCode.REGISTRATION_NOT_FOUND, "Lượt đăng ký không tồn tại", 404)
    if not _can_decide_registration(db, user, r):
        raise hc.forbidden("Bạn không có quyền duyệt lượt đăng ký này")
    if r.status != "pending":
        raise AppException(
            ErrorCode.REGISTRATION_ALREADY_DECIDED,
            "Lượt đăng ký đã được duyệt/từ chối, không thể quyết lại",
            409,
        )
    r.status = decision
    r.approved_by = user.id
    r.approved_at = datetime.now(timezone.utc)
    r.updated_by = user.id
    r.updated_at = func.now()
    db.flush()
    action = "LAB_REGISTRATION_APPROVE" if decision == "approved" else "LAB_REGISTRATION_REJECT"
    audit_service.log_action(
        db,
        action=action,
        resource="lab_registration",
        user_id=user.id,
        resource_id=r.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"decision": decision, "reason": (reason or "")[:255]},
    )
    db.commit()
    db.refresh(r)
    return {
        "id": r.id,
        "status": r.status,
        "decided_by_user_id": r.approved_by,
        "decided_at": r.approved_at,
    }
