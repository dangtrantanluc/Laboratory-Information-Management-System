"""Router customers (M7/chung) — admin/leader/staff đọc; admin/staff ghi; accountant CẤM."""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_roles
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.customer import CreateCustomerRequest, UpdateCustomerRequest
from app.services import customer_service

router = APIRouter(prefix="/customers", tags=["customers"])

read_roles = require_roles("admin", "leader", "staff")  # accountant cấm (B03)
write_roles = require_roles("admin", "staff")


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("")
def list_customers(
    q: Optional[str] = Query(default=None, max_length=100),
    type_filter: Optional[str] = Query(default=None, alias="type"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1),
    user: CurrentUser = Depends(read_roles),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = customer_service.list_customers(
        db, q=q, type_filter=type_filter, page=page, limit=limit
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_customer(
    body: CreateCustomerRequest,
    request: Request,
    user: CurrentUser = Depends(write_roles),
    db: Session = Depends(get_db),
):
    data = customer_service.create_customer(
        db,
        actor_id=user.id,
        name=body.name,
        contact=body.contact,
        type=body.type,
        note=body.note,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)


@router.get("/{customer_id}")
def get_customer(
    customer_id: uuid.UUID,
    user: CurrentUser = Depends(read_roles),
    db: Session = Depends(get_db),
):
    return ok(customer_service.get_customer(db, customer_id))


@router.patch("/{customer_id}")
def update_customer(
    customer_id: uuid.UUID,
    body: UpdateCustomerRequest,
    request: Request,
    user: CurrentUser = Depends(write_roles),
    db: Session = Depends(get_db),
):
    changes = body.model_dump(exclude_unset=True)
    data = customer_service.update_customer(
        db,
        actor_id=user.id,
        customer_id=customer_id,
        changes=changes,
        correlation_id=_cid(request),
        ip=_ip(request),
    )
    return ok(data)
