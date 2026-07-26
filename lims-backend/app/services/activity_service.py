"""Service — hợp đồng NCKH, công tác khác, chứng nhận đào tạo (menu mới m23).

CRUD đơn giản + phân trang + audit. RBAC: đọc cho mọi user đã đăng nhập (trừ office bị
chặn khối NCKH hợp đồng); ghi cho admin/leader/office. Giá trị tiền nhận string-decimal.
"""
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found
from app.models.hr import ResearchContract, StaffActivity, TrainingCertificate
from app.services import audit_service, hr_common as hc


def _assert_can_write(user: CurrentUser) -> None:
    if user.role not in ("admin", "leader", "office"):
        raise hc.forbidden("Chỉ Admin/Lãnh đạo/Văn phòng được thêm/sửa/xóa mục này")


# ===================== research_contracts =====================
def _contract_dict(db: Session, c: ResearchContract) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "contract_type": c.contract_type,
        "value_amount": str(c.value_amount) if c.value_amount is not None else None,
        "currency": c.currency,
        "partner_org": c.partner_org,
        "start_date": c.start_date.isoformat() if c.start_date else None,
        "end_date": c.end_date.isoformat() if c.end_date else None,
        "academic_year": c.academic_year,
        "department_id": c.department_id,
        "department_name": hc.dept_name(db, c.department_id),
        "created_at": c.created_at,
    }


def list_contracts(
    db: Session, *, academic_year: Optional[str], department_id: Optional[uuid.UUID],
    q: Optional[str], page: int, limit: int,
) -> tuple[list[dict], int]:
    conds = []
    if academic_year:
        conds.append(ResearchContract.academic_year == academic_year)
    if department_id:
        conds.append(ResearchContract.department_id == department_id)
    if q:
        conds.append(ResearchContract.title.ilike(f"%{q}%"))
    total = db.execute(select(func.count()).select_from(ResearchContract).where(*conds)).scalar_one()
    rows = db.execute(
        select(ResearchContract).where(*conds)
        .order_by(ResearchContract.created_at.desc())
        .offset((page - 1) * limit).limit(limit)
    ).scalars().all()
    return [_contract_dict(db, c) for c in rows], total


def create_contract(db: Session, *, user: CurrentUser, payload: dict, correlation_id, ip) -> dict:
    _assert_can_write(user)
    start, end = payload.get("start_date"), payload.get("end_date")
    if start and end and end < start:
        raise AppException("INVALID_DATE_ORDER", "end_date < start_date", 422)
    c = ResearchContract(
        title=str(payload["title"]).strip(),
        contract_type=payload.get("contract_type"),
        value_amount=hc.parse_decimal(payload.get("value_amount"), field="value_amount"),
        currency=payload.get("currency") or "VND",
        partner_org=payload.get("partner_org"),
        start_date=start, end_date=end,
        academic_year=payload.get("academic_year"),
        department_id=payload.get("department_id"),
        created_by=user.id, updated_by=user.id,
    )
    db.add(c)
    db.flush()
    audit_service.log_action(
        db, action="RESEARCH_CONTRACT_CREATE", resource="research_contract",
        user_id=user.id, resource_id=c.id, correlation_id=correlation_id, ip=ip,
        detail={"title": c.title},
    )
    db.commit()
    db.refresh(c)
    return _contract_dict(db, c)


def update_contract(db: Session, *, user: CurrentUser, contract_id, changes: dict, correlation_id, ip) -> dict:
    _assert_can_write(user)
    c = db.get(ResearchContract, contract_id)
    if c is None:
        raise not_found("Không tìm thấy hợp đồng")
    for k, v in changes.items():
        if k == "value_amount":
            c.value_amount = hc.parse_decimal(v, field="value_amount")
        else:
            setattr(c, k, v)
    c.updated_by = user.id
    c.updated_at = func.now()
    audit_service.log_action(
        db, action="RESEARCH_CONTRACT_UPDATE", resource="research_contract",
        user_id=user.id, resource_id=c.id, correlation_id=correlation_id, ip=ip, detail={},
    )
    db.commit()
    db.refresh(c)
    return _contract_dict(db, c)


def delete_contract(db: Session, *, user: CurrentUser, contract_id, correlation_id, ip) -> None:
    _assert_can_write(user)
    c = db.get(ResearchContract, contract_id)
    if c is None:
        raise not_found("Không tìm thấy hợp đồng")
    db.delete(c)
    audit_service.log_action(
        db, action="RESEARCH_CONTRACT_DELETE", resource="research_contract",
        user_id=user.id, resource_id=contract_id, correlation_id=correlation_id, ip=ip, detail={},
    )
    db.commit()


# ===================== staff_activities =====================
def _activity_dict(db: Session, a: StaffActivity) -> dict:
    return {
        "id": a.id,
        "kind": a.kind,
        "content": a.content,
        "performed_at": a.performed_at.isoformat() if a.performed_at else None,
        "academic_year": a.academic_year,
        "performer_user_id": a.performer_user_id,
        "performer_name": hc.user_name(db, a.performer_user_id),
        "department_id": a.department_id,
        "created_at": a.created_at,
    }


def list_activities(
    db: Session, *, kind: Optional[str], academic_year: Optional[str], page: int, limit: int,
) -> tuple[list[dict], int]:
    conds = []
    if kind:
        conds.append(StaffActivity.kind == kind)
    if academic_year:
        conds.append(StaffActivity.academic_year == academic_year)
    total = db.execute(select(func.count()).select_from(StaffActivity).where(*conds)).scalar_one()
    rows = db.execute(
        select(StaffActivity).where(*conds)
        .order_by(StaffActivity.created_at.desc())
        .offset((page - 1) * limit).limit(limit)
    ).scalars().all()
    return [_activity_dict(db, a) for a in rows], total


def create_activity(db: Session, *, user: CurrentUser, payload: dict, correlation_id, ip) -> dict:
    _assert_can_write(user)
    a = StaffActivity(
        kind=payload["kind"], content=str(payload["content"]).strip(),
        performed_at=payload.get("performed_at"), academic_year=payload.get("academic_year"),
        performer_user_id=payload.get("performer_user_id") or user.id,
        department_id=payload.get("department_id"),
        created_by=user.id, updated_by=user.id,
    )
    db.add(a)
    db.flush()
    audit_service.log_action(
        db, action="STAFF_ACTIVITY_CREATE", resource="staff_activity",
        user_id=user.id, resource_id=a.id, correlation_id=correlation_id, ip=ip, detail={"kind": a.kind},
    )
    db.commit()
    db.refresh(a)
    return _activity_dict(db, a)


def update_activity(db: Session, *, user: CurrentUser, activity_id, changes: dict, correlation_id, ip) -> dict:
    _assert_can_write(user)
    a = db.get(StaffActivity, activity_id)
    if a is None:
        raise not_found("Không tìm thấy hoạt động")
    for k, v in changes.items():
        setattr(a, k, v)
    a.updated_by = user.id
    a.updated_at = func.now()
    audit_service.log_action(
        db, action="STAFF_ACTIVITY_UPDATE", resource="staff_activity",
        user_id=user.id, resource_id=a.id, correlation_id=correlation_id, ip=ip, detail={},
    )
    db.commit()
    db.refresh(a)
    return _activity_dict(db, a)


def delete_activity(db: Session, *, user: CurrentUser, activity_id, correlation_id, ip) -> None:
    _assert_can_write(user)
    a = db.get(StaffActivity, activity_id)
    if a is None:
        raise not_found("Không tìm thấy hoạt động")
    db.delete(a)
    audit_service.log_action(
        db, action="STAFF_ACTIVITY_DELETE", resource="staff_activity",
        user_id=user.id, resource_id=activity_id, correlation_id=correlation_id, ip=ip, detail={},
    )
    db.commit()


# ===================== training_certificates =====================
def _cert_dict(db: Session, c: TrainingCertificate) -> dict:
    return {
        "id": c.id,
        "recipient_name": c.recipient_name,
        "certificate_no": c.certificate_no,
        "course_name": c.course_name,
        "issued_date": c.issued_date.isoformat() if c.issued_date else None,
        "note": c.note,
        "academic_year": c.academic_year,
        "host_user_id": c.host_user_id,
        "host_name": hc.user_name(db, c.host_user_id),
        "department_id": c.department_id,
        "created_at": c.created_at,
    }


def list_certificates(
    db: Session, *, academic_year: Optional[str], q: Optional[str], page: int, limit: int,
) -> tuple[list[dict], int]:
    conds = []
    if academic_year:
        conds.append(TrainingCertificate.academic_year == academic_year)
    if q:
        conds.append(TrainingCertificate.recipient_name.ilike(f"%{q}%"))
    total = db.execute(select(func.count()).select_from(TrainingCertificate).where(*conds)).scalar_one()
    rows = db.execute(
        select(TrainingCertificate).where(*conds)
        .order_by(TrainingCertificate.created_at.desc())
        .offset((page - 1) * limit).limit(limit)
    ).scalars().all()
    return [_cert_dict(db, c) for c in rows], total


def create_certificate(db: Session, *, user: CurrentUser, payload: dict, correlation_id, ip) -> dict:
    _assert_can_write(user)
    c = TrainingCertificate(
        recipient_name=str(payload["recipient_name"]).strip(),
        certificate_no=payload.get("certificate_no"), course_name=payload.get("course_name"),
        issued_date=payload.get("issued_date"), note=payload.get("note"),
        academic_year=payload.get("academic_year"),
        host_user_id=payload.get("host_user_id") or user.id,
        department_id=payload.get("department_id"),
        created_by=user.id, updated_by=user.id,
    )
    db.add(c)
    db.flush()
    audit_service.log_action(
        db, action="TRAINING_CERT_CREATE", resource="training_certificate",
        user_id=user.id, resource_id=c.id, correlation_id=correlation_id, ip=ip, detail={},
    )
    db.commit()
    db.refresh(c)
    return _cert_dict(db, c)


def update_certificate(db: Session, *, user: CurrentUser, cert_id, changes: dict, correlation_id, ip) -> dict:
    _assert_can_write(user)
    c = db.get(TrainingCertificate, cert_id)
    if c is None:
        raise not_found("Không tìm thấy chứng nhận")
    for k, v in changes.items():
        setattr(c, k, v)
    c.updated_by = user.id
    c.updated_at = func.now()
    audit_service.log_action(
        db, action="TRAINING_CERT_UPDATE", resource="training_certificate",
        user_id=user.id, resource_id=c.id, correlation_id=correlation_id, ip=ip, detail={},
    )
    db.commit()
    db.refresh(c)
    return _cert_dict(db, c)


def delete_certificate(db: Session, *, user: CurrentUser, cert_id, correlation_id, ip) -> None:
    _assert_can_write(user)
    c = db.get(TrainingCertificate, cert_id)
    if c is None:
        raise not_found("Không tìm thấy chứng nhận")
    db.delete(c)
    audit_service.log_action(
        db, action="TRAINING_CERT_DELETE", resource="training_certificate",
        user_id=user.id, resource_id=cert_id, correlation_id=correlation_id, ip=ip, detail={},
    )
    db.commit()
