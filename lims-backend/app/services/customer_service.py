"""Customer service — CRUD khách gửi mẫu dùng chung (M1 tham chiếu)."""
import uuid
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db_helpers import get_active_or_404
from app.core.error_codes import ErrorCode
from app.models.customer import Customer
from app.services import audit_service


def _get_or_404(db: Session, customer_id: uuid.UUID) -> Customer:
    return get_active_or_404(db, Customer, customer_id, "Không tìm thấy khách hàng")


# Trường người dùng được sửa qua PATCH /customers/{id}. Dùng chung cho _serialize
# và update_customer để thêm cột mới chỉ phải sửa MỘT chỗ — trước đây hai nơi liệt
# kê tay riêng, quên nơi nào thì hỏng âm thầm (PATCH trả 200 mà không lưu gì).
EDITABLE_FIELDS = (
    "name",
    "type",
    "note",
    "address",
    "tax_code",
    "contact_person",
    "phone",
    "email",
)


def _serialize(customer: Customer) -> dict:
    data = {f: getattr(customer, f) for f in EDITABLE_FIELDS}
    data["id"] = customer.id
    data["created_at"] = customer.created_at
    return data


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
        # m44 — tìm ĐA TRƯỜNG. Trước đây chỉ khớp `name`, nên khách đọc mã số thuế
        # hay số điện thoại qua điện thoại là nhân viên gõ vào không ra gì rồi bấm
        # "thêm vào sổ" — đó chính là cách khách trùng được sinh ra ngay tại quầy.
        like = f"%{q.strip()}%"
        conditions.append(or_(
            Customer.name.ilike(like),
            Customer.tax_code.ilike(like),
            Customer.phone.ilike(like),
            Customer.email.ilike(like),
            Customer.contact_person.ilike(like),
        ))
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


def find_duplicates(
    db: Session, *, name: Optional[str], tax_code: Optional[str],
    exclude_id: Optional[uuid.UUID] = None,
) -> list[dict]:
    """Khách có khả năng TRÙNG với thông tin đang nhập.

    CẢNH BÁO, KHÔNG CHẶN. Lý do không đặt ràng buộc duy nhất trên `tax_code` nằm ở
    docstring migration m44: chưa chốt "khách hàng" là pháp nhân hay địa điểm (Q3),
    mà nếu là địa điểm thì ba nhà máy của cùng một công ty PHẢI trùng mã số thuế.
    Người ở quầy nhìn danh sách này rồi tự quyết là đúng vai hơn.
    """
    conds = []
    tc = (tax_code or "").strip()
    nm = (name or "").strip()
    if tc:
        conds.append(func.btrim(Customer.tax_code) == tc)
    if nm:
        conds.append(func.lower(func.btrim(Customer.name)) == nm.lower())
    if not conds:
        return []

    where = [Customer.deleted_at.is_(None), or_(*conds)]
    if exclude_id is not None:
        where.append(Customer.id != exclude_id)
    rows = db.execute(
        select(Customer).where(*where).order_by(Customer.created_at.desc()).limit(10)
    ).scalars().all()
    return [
        {"id": c.id, "name": c.name, "tax_code": c.tax_code, "phone": c.phone,
         "address": c.address,
         "matched_on": "tax_code" if tc and (c.tax_code or "").strip() == tc else "name"}
        for c in rows
    ]


def create_customer(
    db: Session,
    *,
    actor_id: uuid.UUID,
    fields: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    """fields: đã qua CreateCustomerRequest nên các khoá là tập con của EDITABLE_FIELDS."""
    values = {f: fields.get(f) for f in EDITABLE_FIELDS if f in fields}
    values["name"] = str(values.get("name", "")).strip()
    customer = Customer(
        **values,
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
    # W14 — chụp giá trị TRƯỚC khi ghi. `detail={"diff": ...}` cũ chỉ có giá trị mới,
    # nên không trả lời được "hồ sơ lúc in cho khách ghi gì".
    detail = audit_service.diff_detail(
        customer,
        {f: changes[f] for f in EDITABLE_FIELDS if f in changes and changes[f] is not None},
    )
    diff: dict = {}
    for field in EDITABLE_FIELDS:
        if field in changes and changes[field] is not None:
            value = changes[field]
            if field == "name":
                value = value.strip()
            setattr(customer, field, value)
            diff[field] = value
    if not diff:
        from app.core.exceptions import AppException

        raise AppException(ErrorCode.VALIDATION_ERROR, "Không có thay đổi nào hợp lệ", 400)

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
        detail=detail,
    )
    db.commit()
    db.refresh(customer)
    return _serialize(customer)
