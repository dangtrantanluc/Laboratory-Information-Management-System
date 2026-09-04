"""Danh bạ liên hệ khách hàng (m35) — 1 khách, n người liên hệ, KHÔNG phân vai trò.

Quy tắc nghiệp vụ đáng chú ý:

- **Mặc định là duy nhất.** Đặt một dòng làm mặc định sẽ tự gỡ cờ của dòng cũ.
  DB còn có unique index từng phần `uq_customer_contacts_primary` chốt lại, vì
  hai request song song đều kiểm "chưa có ai mặc định" xong rồi cùng ghi được.

- **Tắt thay cho xoá.** Người nghỉ việc → `is_active=false`; phiếu cũ đã in tên họ
  nên phải tra ngược được (hồ sơ VILAS). Xoá hẳn chỉ dành cho dòng nhập nhầm.

- **Tắt dòng đang mặc định thì gỡ luôn cờ mặc định.** Nếu không, quầy nhận mẫu sẽ
  tự điền tên một người đã nghỉ việc mà không ai nhận ra.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.db_helpers import get_active_or_404, get_or_404
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.models.customer import Customer, CustomerContact
from app.services import audit_service

# Field người dùng được ghi. Liệt kê tường minh thay vì lặp qua changes.items():
# vòng lặp mở sẽ ghi được mọi khoá lọt qua schema, kể cả khoá thêm sau này.
_WRITABLE = ("full_name", "job_title", "email", "phone", "is_active", "note", "roles")


def _serialize(c: CustomerContact) -> dict:
    return {
        "id": c.id,
        "customer_id": c.customer_id,
        "full_name": c.full_name,
        "job_title": c.job_title,
        "email": c.email,
        "phone": c.phone,
        "is_primary": c.is_primary,
        "is_active": c.is_active,
        "roles": list(c.roles or []),
        "note": c.note,
        "created_at": c.created_at,
    }


def _assert_customer(db: Session, customer_id: uuid.UUID) -> Customer:
    return get_active_or_404(
        db, Customer, customer_id, "Không tìm thấy khách hàng",
        code=ErrorCode.CUSTOMER_NOT_FOUND,
    )


def _get_contact(db: Session, customer_id: uuid.UUID, contact_id: uuid.UUID) -> CustomerContact:
    c = get_or_404(db, CustomerContact, contact_id, "Không tìm thấy người liên hệ")
    # Chặn đọc chéo: id hợp lệ nhưng thuộc khách khác thì coi như không có.
    if c.customer_id != customer_id:
        raise AppException(ErrorCode.NOT_FOUND, "Không tìm thấy người liên hệ", 404)
    return c


def _clear_primary(db: Session, customer_id: uuid.UUID, *, keep_id: Optional[uuid.UUID]) -> None:
    """Gỡ cờ mặc định của mọi dòng khác — giữ đúng bất biến 1 mặc định/khách."""
    conds = [CustomerContact.customer_id == customer_id, CustomerContact.is_primary.is_(True)]
    if keep_id is not None:
        conds.append(CustomerContact.id != keep_id)
    db.execute(update(CustomerContact).where(*conds).values(is_primary=False))
    # Đẩy UPDATE xuống DB TRƯỚC khi bật cờ mới, nếu không unique index từng phần
    # sẽ thấy hai dòng cùng is_primary trong một câu lệnh và từ chối.
    db.flush()


def list_contacts(
    db: Session, *, customer_id: uuid.UUID, include_inactive: bool = True
) -> list[dict]:
    _assert_customer(db, customer_id)
    conds = [CustomerContact.customer_id == customer_id]
    if not include_inactive:
        conds.append(CustomerContact.is_active.is_(True))
    rows = db.execute(
        select(CustomerContact).where(*conds).order_by(
            # Mặc định lên đầu, rồi người còn hiệu lực, rồi theo tên.
            CustomerContact.is_primary.desc(),
            CustomerContact.is_active.desc(),
            CustomerContact.full_name.asc(),
        )
    ).scalars().all()
    return [_serialize(c) for c in rows]


def create_contact(
    db: Session, *, actor_id: uuid.UUID, customer_id: uuid.UUID, fields: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    _assert_customer(db, customer_id)
    name = str(fields.get("full_name", "")).strip()
    if not name:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Nhập họ tên người liên hệ", 400)

    # Người đầu tiên của khách luôn là mặc định — nếu không, khách chỉ có đúng 1
    # liên hệ mà quầy nhận mẫu vẫn không tự điền được, tức là vô dụng.
    has_any = db.execute(
        select(CustomerContact.id).where(CustomerContact.customer_id == customer_id).limit(1)
    ).first() is not None
    is_primary = bool(fields.get("is_primary")) or not has_any
    is_active = bool(fields.get("is_active", True))
    # Không cho vừa tắt vừa làm mặc định: quầy sẽ tự điền người đã nghỉ việc.
    if is_primary and not is_active:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, "Người liên hệ mặc định phải còn hiệu lực", 400
        )
    if is_primary:
        _clear_primary(db, customer_id, keep_id=None)

    c = CustomerContact(
        customer_id=customer_id,
        full_name=name,
        job_title=fields.get("job_title"),
        email=fields.get("email"),
        phone=fields.get("phone"),
        is_primary=is_primary,
        is_active=is_active,
        roles=list(fields.get("roles") or []),
        note=fields.get("note"),
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(c)
    db.flush()
    audit_service.log_action(
        db, action="CUSTOMER_CONTACT_CREATE", resource="customer_contact", user_id=actor_id,
        resource_id=c.id, correlation_id=correlation_id, ip=ip,
        detail={"customer_id": str(customer_id), "full_name": c.full_name},
    )
    db.commit()
    db.refresh(c)
    return _serialize(c)


def update_contact(
    db: Session, *, actor_id: uuid.UUID, customer_id: uuid.UUID, contact_id: uuid.UUID,
    changes: dict, correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    _assert_customer(db, customer_id)
    c = _get_contact(db, customer_id, contact_id)

    for f in _WRITABLE:
        if f in changes and changes[f] is not None:
            v = changes[f]
            if f == "full_name":
                v = str(v).strip()
                if not v:
                    raise AppException(ErrorCode.VALIDATION_ERROR, "Nhập họ tên người liên hệ", 400)
            setattr(c, f, v)

    want_primary = changes.get("is_primary")
    if want_primary is True:
        if not c.is_active:
            raise AppException(
                ErrorCode.VALIDATION_ERROR, "Người liên hệ mặc định phải còn hiệu lực", 400
            )
        _clear_primary(db, customer_id, keep_id=c.id)
        c.is_primary = True
    elif want_primary is False:
        c.is_primary = False

    # Tắt người đang là mặc định thì phải gỡ cờ, nếu không quầy nhận mẫu sẽ tự điền
    # tên một người đã nghỉ việc.
    if not c.is_active:
        c.is_primary = False

    c.updated_by = actor_id
    c.updated_at = datetime.now(timezone.utc)
    audit_service.log_action(
        db, action="CUSTOMER_CONTACT_UPDATE", resource="customer_contact", user_id=actor_id,
        resource_id=c.id, correlation_id=correlation_id, ip=ip,
        detail={"customer_id": str(customer_id), "changes": {k: changes[k] for k in changes}},
    )
    db.commit()
    db.refresh(c)
    return _serialize(c)


def delete_contact(
    db: Session, *, actor_id: uuid.UUID, customer_id: uuid.UUID, contact_id: uuid.UUID,
    correlation_id: Optional[str], ip: Optional[str],
) -> None:
    """Xoá HẲN — chỉ dành cho dòng nhập nhầm. Người nghỉ việc phải dùng is_active=false."""
    _assert_customer(db, customer_id)
    c = _get_contact(db, customer_id, contact_id)
    audit_service.log_action(
        db, action="CUSTOMER_CONTACT_DELETE", resource="customer_contact", user_id=actor_id,
        resource_id=c.id, correlation_id=correlation_id, ip=ip,
        detail={"customer_id": str(customer_id), "full_name": c.full_name},
    )
    db.delete(c)
    db.commit()
