"""Router customers + danh bạ liên hệ (M7/chung, m35).

admin/leader/staff/reception/lab_manager đọc; admin/staff/reception ghi; office CẤM.
Danh bạ dùng ĐÚNG bộ quyền của khách hàng: nó là PII cùng loại với các ô liên hệ
đã nằm sẵn trong GET /customers/{id}, nên tách quyền riêng chỉ tạo ảo giác an toàn.
(Che PII với khối lab là ở tầng PHIẾU — xem customer_info_service.)
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.request_meta import client_ip
from app.core.deps import CurrentUser, require_roles
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.customer import (
    CreateCustomerContactRequest,
    DuplicateCustomerListResponse,
    CreateCustomerRequest,
    CustomerContactListResponse,
    CustomerContactResponse,
    UpdateCustomerContactRequest,
    UpdateCustomerRequest,
)
from app.services import customer_contact_service, customer_service

router = APIRouter(prefix="/customers", tags=["customers"])

# m43/W12 — SẮP LẠI THEO ĐÚNG VAI TRÒ NGHIỆP VỤ.
#
# TRƯỚC:  đọc  = admin, leader, staff, reception, lab_manager   (office CẤM)
#         ghi  = admin, staff, reception
# SAU:    đọc  = admin, leader, reception, office
#         ghi  = admin, reception, office
#
# Hai điều vô lý được sửa cùng lúc:
#   · `staff` — kỹ thuật viên phòng lab — tạo/sửa được tên pháp nhân, mã số thuế và
#     toàn bộ danh bạ, kể cả xoá hẳn một dòng liên hệ. Không có phần việc nào của KTV
#     cần tới điều đó, và nó mở rộng phạm vi tiếp xúc PII ra cả khối lab.
#   · `office` — bộ phận CÓ trách nhiệm nghiệp vụ với khách hàng (hợp đồng, hoá đơn)
#     — bị chặn cả đọc lẫn ghi, trong khi vẫn đọc được đúng dữ liệu đó qua màn hình
#     Báo giá (routers/quotations.quotation_read gồm 'office'). Hai luật không thể
#     cùng đúng.
#
# Khối lab KHÔNG mất gì trong phần việc của họ: thông tin khách của từng phiếu vẫn
# đọc được qua luồng xin/duyệt của m26 (customer_info_service), đúng cơ chế sinh ra
# để kiểm soát việc đó.
read_roles = require_roles("admin", "leader", "reception", "office")
write_roles = require_roles("admin", "reception", "office")


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


@router.get("")
def list_customers(
    q: Optional[str] = Query(default=None, max_length=100),
    type_filter: Optional[str] = Query(default=None, alias="type"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(read_roles),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = customer_service.list_customers(
        db, q=q, type_filter=type_filter, page=page, limit=limit
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.get("/duplicates", response_model=DuplicateCustomerListResponse)
def check_duplicate_customers(
    name: Optional[str] = Query(default=None, max_length=255),
    tax_code: Optional[str] = Query(default=None, max_length=50),
    exclude_id: Optional[uuid.UUID] = Query(default=None),
    user: CurrentUser = Depends(read_roles),
    db: Session = Depends(get_db),
):
    """Khách có khả năng trùng — CẢNH BÁO cho quầy, không chặn (m44).

    Đặt TRƯỚC route /{customer_id} vì "duplicates" sẽ khớp vào tham số đường dẫn nếu
    khai sau.
    """
    return ok(customer_service.find_duplicates(
        db, name=name, tax_code=tax_code, exclude_id=exclude_id
    ))


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
        fields=body.model_dump(),
        correlation_id=_cid(request),
        ip=client_ip(request),
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
        ip=client_ip(request),
    )
    return ok(data)


# ── m35: danh bạ liên hệ ─────────────────────────────────────────
# Các endpoint dưới đây khai response_model tường minh (test kiến trúc
# test_response_contract chặn endpoint MỚI thiếu nó).


@router.get(
    "/{customer_id}/contacts",
    response_model=CustomerContactListResponse,
)
def list_customer_contacts(
    customer_id: uuid.UUID,
    include_inactive: bool = Query(default=True),
    user: CurrentUser = Depends(read_roles),
    db: Session = Depends(get_db),
):
    """Danh bạ của một khách. Mặc định trả cả người đã tắt để màn hình quản lý thấy.

    Quầy nhận mẫu gọi kèm `include_inactive=false` — không được phép chọn người đã
    nghỉ việc vào phiếu mới.
    """
    return ok(customer_contact_service.list_contacts(
        db, customer_id=customer_id, include_inactive=include_inactive,
    ))


@router.post(
    "/{customer_id}/contacts",
    status_code=status.HTTP_201_CREATED,
    response_model=CustomerContactResponse,
)
def create_customer_contact(
    customer_id: uuid.UUID,
    body: CreateCustomerContactRequest,
    request: Request,
    user: CurrentUser = Depends(write_roles),
    db: Session = Depends(get_db),
):
    return ok(customer_contact_service.create_contact(
        db, actor_id=user.id, customer_id=customer_id, fields=body.model_dump(),
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.patch(
    "/{customer_id}/contacts/{contact_id}",
    response_model=CustomerContactResponse,
)
def update_customer_contact(
    customer_id: uuid.UUID,
    contact_id: uuid.UUID,
    body: UpdateCustomerContactRequest,
    request: Request,
    user: CurrentUser = Depends(write_roles),
    db: Session = Depends(get_db),
):
    return ok(customer_contact_service.update_contact(
        db, actor_id=user.id, customer_id=customer_id, contact_id=contact_id,
        changes=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.delete("/{customer_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer_contact(
    customer_id: uuid.UUID,
    contact_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(write_roles),
    db: Session = Depends(get_db),
):
    """Xoá hẳn dòng nhập nhầm. Người nghỉ việc: PATCH is_active=false để giữ lịch sử."""
    customer_contact_service.delete_contact(
        db, actor_id=user.id, customer_id=customer_id, contact_id=contact_id,
        correlation_id=_cid(request), ip=client_ip(request),
    )
