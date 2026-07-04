"""Test request service (M1) — CRUD phiếu yêu cầu thử nghiệm (FR-018).

Phiếu là vùng chứa 1..n mẫu. status (draft/active) suy theo số mẫu. Soft-delete.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found, validation_error
from app.models.customer import Customer
from app.models.sample import Sample
from app.models.test_request import TestRequest
from app.services import audit_service, sample_common


def _sample_count(db: Session, request_id: uuid.UUID) -> int:
    return db.execute(
        select(func.count())
        .select_from(Sample)
        .where(Sample.request_id == request_id, Sample.deleted_at.is_(None))
    ).scalar_one()


def _serialize_list_item(db: Session, req: TestRequest) -> dict:
    count = _sample_count(db, req.id)
    customer_name = None
    if req.customer_id:
        c = db.get(Customer, req.customer_id)
        customer_name = c.name if c else None
    return {
        "id": req.id,
        "request_code": req.request_code,
        "customer_id": req.customer_id,
        "customer_name": customer_name,
        "sender_name": req.sender_name,
        "department_id": req.department_id,
        "department_name": sample_common.dept_name(db, req.department_id),
        "received_by": req.received_by,
        "received_by_name": sample_common.user_name(db, req.received_by),
        "received_at": req.received_at,
        "note": req.note,
        "sample_count": count,
        "status": "active" if count > 0 else "draft",
        "created_at": req.created_at,
    }


def _get_or_404(db: Session, request_id: uuid.UUID) -> TestRequest:
    req = db.execute(
        select(TestRequest).where(
            TestRequest.id == request_id, TestRequest.deleted_at.is_(None)
        )
    ).scalar_one_or_none()
    if req is None:
        raise not_found("Không tìm thấy phiếu yêu cầu")
    return req


def list_requests(
    db: Session,
    *,
    q: Optional[str],
    department_id: Optional[uuid.UUID],
    customer_id: Optional[uuid.UUID],
    received_from: Optional[datetime],
    received_to: Optional[datetime],
    status_filter: Optional[str],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = [TestRequest.deleted_at.is_(None)]
    if q:
        conditions.append(
            (TestRequest.request_code.ilike(f"%{q}%"))
            | (TestRequest.sender_name.ilike(f"%{q}%"))
        )
    if department_id:
        conditions.append(TestRequest.department_id == department_id)
    if customer_id:
        conditions.append(TestRequest.customer_id == customer_id)
    if received_from:
        conditions.append(TestRequest.received_at >= received_from)
    if received_to:
        conditions.append(TestRequest.received_at <= received_to)

    total = db.execute(
        select(func.count()).select_from(TestRequest).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(TestRequest)
        .where(*conditions)
        .order_by(TestRequest.received_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    items = [_serialize_list_item(db, r) for r in rows]
    # Lọc draft/active sau khi tính count (status không lưu DB)
    if status_filter in ("draft", "active"):
        items = [i for i in items if i["status"] == status_filter]
    return items, total


def get_request_detail(db: Session, request_id: uuid.UUID) -> dict:
    req = _get_or_404(db, request_id)
    samples = db.execute(
        select(Sample)
        .where(Sample.request_id == req.id, Sample.deleted_at.is_(None))
        .order_by(Sample.created_at.asc())
    ).scalars().all()
    customer = db.get(Customer, req.customer_id) if req.customer_id else None
    return {
        "id": req.id,
        "request_code": req.request_code,
        "customer": (
            {"id": customer.id, "name": customer.name, "contact": customer.contact}
            if customer
            else None
        ),
        "customer_id": req.customer_id,
        "sender_name": req.sender_name,
        "department_id": req.department_id,
        "department_name": sample_common.dept_name(db, req.department_id),
        "received_by": req.received_by,
        "received_by_name": sample_common.user_name(db, req.received_by),
        "received_at": req.received_at,
        "note": req.note,
        "status": "active" if samples else "draft",
        "samples": [
            {
                "id": s.id,
                "sample_code": s.sample_code,
                "status": s.status,
                "deadline_at": s.deadline_at,
                "condition_status": s.condition_status,
            }
            for s in samples
        ],
        "created_at": req.created_at,
    }


def create_request(
    db: Session,
    *,
    user: CurrentUser,
    customer_id: Optional[uuid.UUID],
    sender_name: str,
    department_id: Optional[uuid.UUID],
    received_by: Optional[uuid.UUID],
    received_at: Optional[datetime],
    note: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    now = datetime.now(timezone.utc)
    if received_at and received_at > now:
        raise validation_error("Ngày nhận không được ở tương lai")

    # department: default phòng user; KTV bắt buộc phòng mình
    dept = department_id or user.department_id
    if dept is None:
        raise validation_error("Thiếu phòng tiếp nhận (department_id)")
    if not sample_common.is_privileged(user):
        if user.department_id != dept:
            raise sample_common.forbidden("KTV chỉ được tạo phiếu cho phòng của mình")

    if customer_id is not None:
        c = db.execute(
            select(Customer).where(
                Customer.id == customer_id, Customer.deleted_at.is_(None)
            )
        ).scalar_one_or_none()
        if c is None:
            raise AppException("CUSTOMER_NOT_FOUND", "Không tìm thấy khách hàng", 404)

    recv_by = received_by or user.id

    # Sinh request_code + retry nếu trùng
    for _ in range(5):
        code = sample_common.next_request_code(db)
        req = TestRequest(
            request_code=code,
            customer_id=customer_id,
            sender_name=sender_name.strip(),
            department_id=dept,
            received_by=recv_by,
            received_at=received_at or now,
            note=note,
            created_by=user.id,
            updated_by=user.id,
        )
        db.add(req)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
    else:
        raise AppException(
            "INTERNAL_ERROR", "Không sinh được mã phiếu, vui lòng thử lại", 500
        )

    audit_service.log_action(
        db,
        action="REQUEST_CREATE",
        resource="test_request",
        user_id=user.id,
        resource_id=req.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"request_code": req.request_code, "department_id": str(dept)},
    )
    db.commit()
    db.refresh(req)
    return _serialize_list_item(db, req)


def update_request(
    db: Session,
    *,
    user: CurrentUser,
    request_id: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    req = _get_or_404(db, request_id)
    sample_common.assert_write_scope(user, req.department_id)

    diff: dict = {}
    if "customer_id" in changes:
        cid = changes["customer_id"]
        if cid is not None:
            c = db.execute(
                select(Customer).where(
                    Customer.id == cid, Customer.deleted_at.is_(None)
                )
            ).scalar_one_or_none()
            if c is None:
                raise AppException("CUSTOMER_NOT_FOUND", "Không tìm thấy khách hàng", 404)
        req.customer_id = cid
        diff["customer_id"] = str(cid) if cid else None
    if "sender_name" in changes and changes["sender_name"] is not None:
        req.sender_name = changes["sender_name"].strip()
        diff["sender_name"] = req.sender_name
    if "received_by" in changes and changes["received_by"] is not None:
        req.received_by = changes["received_by"]
        diff["received_by"] = str(req.received_by)
    if "received_at" in changes and changes["received_at"] is not None:
        req.received_at = changes["received_at"]
        diff["received_at"] = req.received_at.isoformat()
    if "note" in changes:
        req.note = changes["note"]
        diff["note"] = req.note

    if not diff:
        raise validation_error("Không có thay đổi nào hợp lệ")

    req.updated_by = user.id
    req.updated_at = func.now()
    audit_service.log_action(
        db,
        action="REQUEST_UPDATE",
        resource="test_request",
        user_id=user.id,
        resource_id=req.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"diff": diff},
    )
    db.commit()
    db.refresh(req)
    return _serialize_list_item(db, req)
