"""Customer service — CRUD khách gửi mẫu dùng chung (M1 tham chiếu)."""
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import not_found
from app.models.customer import Customer
from app.services import audit_service


def _get_or_404(db: Session, customer_id: uuid.UUID) -> Customer:
    customer = db.execute(
        select(Customer).where(
            Customer.id == customer_id, Customer.deleted_at.is_(None)
        )
    ).scalar_one_or_none()
    if customer is None:
        raise not_found("Không tìm thấy khách hàng")
    return customer


def _serialize(customer: Customer) -> dict:
    return {
        "id": customer.id,
        "name": customer.name,
        "contact": customer.contact,
        "type": customer.type,
        "note": customer.note,
        "created_at": customer.created_at,
    }


def list_customers(
    db: Session,
    *,
    q: Optional[str],
    type_filter: Optional[str],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = [Customer.deleted_at.is_(None)]
    if q:
        conditions.append(Customer.name.ilike(f"%{q}%"))
    if type_filter:
        conditions.append(Customer.type == type_filter)

    total = db.execute(
        select(func.count()).select_from(Customer).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(Customer)
        .where(*conditions)
        .order_by(Customer.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return [_serialize(c) for c in rows], total


def get_customer(db: Session, customer_id: uuid.UUID) -> dict:
    return _serialize(_get_or_404(db, customer_id))


def create_customer(
    db: Session,
    *,
    actor_id: uuid.UUID,
    name: str,
    contact: Optional[str],
    type: str,
    note: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    customer = Customer(
        name=name.strip(),
        contact=contact,
        type=type,
        note=note,
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(customer)
    db.flush()
    audit_service.log_action(
        db,
        action="CUSTOMER_CREATE",
        resource="customer",
        user_id=actor_id,
        resource_id=customer.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"name": customer.name, "type": customer.type},
    )
    db.commit()
    db.refresh(customer)
    return _serialize(customer)


def update_customer(
    db: Session,
    *,
    actor_id: uuid.UUID,
    customer_id: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    customer = _get_or_404(db, customer_id)
    diff: dict = {}
    for field in ("name", "contact", "type", "note"):
        if field in changes and changes[field] is not None:
            value = changes[field]
            if field == "name":
                value = value.strip()
            setattr(customer, field, value)
            diff[field] = value
    if not diff:
        from app.core.exceptions import AppException

        raise AppException("VALIDATION_ERROR", "Không có thay đổi nào hợp lệ", 400)

    customer.updated_by = actor_id
    customer.updated_at = func.now()
    audit_service.log_action(
        db,
        action="CUSTOMER_UPDATE",
        resource="customer",
        user_id=actor_id,
        resource_id=customer.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"diff": diff},
    )
    db.commit()
    db.refresh(customer)
    return _serialize(customer)
