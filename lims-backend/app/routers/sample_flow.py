"""Router Nhận & Chuyển mẫu (GĐ2b) — /intakes, /dispatches.

- Phiếu nhận (intake): reception tạo/sửa (intake:manage); mọi vai trò liên quan đọc (intake:read).
- Phiếu chuyển (dispatch): reception thêm (intake:manage) → notify lab; lab đổi status
  (dispatch:update) → notify lại reception. File qua /attachments owner_type 'sample_intake'|'sample_dispatch'.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.request_meta import client_ip
from app.core.deps import CurrentUser, require_permission
from app.core.responses import ok, paginated, normalize_pagination
from app.db.database import get_db
from app.schemas.sample_flow import (
    ChangeIntakeStatusRequest,
    CreateDispatchBatchRequest,
    CreateDispatchRequest,
    CreateInfoRequestBody,
    CreateIntakeRequest,
    CreateTestParameterRequest,
    DecideInfoRequestBody,
    UpdateDispatchRequest,
    UpdateIntakeRequest,
    UpdatePaymentRequest,
    UpdateTestParameterRequest,
)
from app.core.deps import get_current_user
from app.services import customer_info_service as cir_svc
from app.services import test_parameter_service as tp_svc
from app.services import sample_flow_service as svc

router = APIRouter(tags=["sample-flow"])


def _cid(r: Request) -> Optional[str]:
    return getattr(r.state, "correlation_id", None)


# ===== Intakes =====
@router.get("/intakes")
def list_intakes(
    q: Optional[str] = Query(default=None),
    status_: Optional[str] = Query(default=None, alias="status"),
    page: Optional[int] = Query(default=None),
    limit: Optional[int] = Query(default=None, le=100),
    user: CurrentUser = Depends(require_permission("intake", "read")),
    db: Session = Depends(get_db),
):
    p, lim = normalize_pagination(page, limit)
    items, total = svc.list_intakes(db, user=user, q=q, status=status_, page=p, limit=lim)
    return paginated(items, page=p, limit=lim, total=total)


@router.post("/intakes", status_code=status.HTTP_201_CREATED)
def create_intake(
    body: CreateIntakeRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("intake", "manage")),
    db: Session = Depends(get_db),
):
    data = svc.create_intake(
        db, user=user, fields=body.model_dump(), correlation_id=_cid(request), ip=client_ip(request),
    )
    return ok(data)


@router.get("/intakes/{intake_id}")
def get_intake(
    intake_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("intake", "read")),
    db: Session = Depends(get_db),
):
    return ok(svc.get_intake(db, intake_id=intake_id, user=user))


@router.patch("/intakes/{intake_id}")
def update_intake(
    intake_id: uuid.UUID,
    body: UpdateIntakeRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("intake", "manage")),
    db: Session = Depends(get_db),
):
    changes = body.model_dump(exclude_unset=True)
    data = svc.update_intake(
        db, user=user, intake_id=intake_id, changes=changes,
        correlation_id=_cid(request), ip=client_ip(request),
    )
    return ok(data)


@router.post("/intakes/{intake_id}/status")
def change_intake_status(
    intake_id: uuid.UUID,
    body: ChangeIntakeStatusRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("intake", "manage")),
    db: Session = Depends(get_db),
):
    """Đổi trạng thái phiếu theo luồng: tiếp nhận → báo giá → đồng ý → thanh toán → chuyển lab → trả KQ."""
    return ok(svc.change_status(
        db, user=user, intake_id=intake_id, new_status=body.status, note=body.note,
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.patch("/intakes/{intake_id}/payment")
def update_intake_payment(
    intake_id: uuid.UUID,
    body: UpdatePaymentRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("intake", "manage")),
    db: Session = Depends(get_db),
):
    """Ghi nhận thanh toán (khách chuyển khoản): trạng thái, số tiền, ngày, mã giao dịch."""
    return ok(svc.update_payment(
        db, user=user, intake_id=intake_id, changes=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.post("/intakes/{intake_id}/dispatches", status_code=status.HTTP_201_CREATED)
def add_dispatch(
    intake_id: uuid.UUID,
    body: CreateDispatchRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("intake", "manage")),
    db: Session = Depends(get_db),
):
    data = svc.add_dispatch(
        db, user=user, intake_id=intake_id, chi_tieu=body.chi_tieu,
        target_department_id=body.target_department_id, note=body.note,
        don_vi=body.don_vi, phuong_phap=body.phuong_phap,
        test_parameter_id=body.test_parameter_id,
        sample_name=body.sample_name, quantity=body.quantity,
        correlation_id=_cid(request), ip=client_ip(request),
    )
    return ok(data)


# ===== Dispatches =====
@router.post("/intakes/{intake_id}/dispatches/batch", status_code=status.HTTP_201_CREATED)
def add_dispatches_batch(
    intake_id: uuid.UUID,
    body: CreateDispatchBatchRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("intake", "manage")),
    db: Session = Depends(get_db),
):
    """Chuyển nhiều chỉ tiêu cùng lúc (chọn nhiều từ danh mục). Nguyên tử: lỗi 1 → hủy cả lượt."""
    data = svc.add_dispatches_batch(
        db, user=user, intake_id=intake_id,
        items=[i.model_dump() for i in body.items],
        correlation_id=_cid(request), ip=client_ip(request),
    )
    return ok(data)


@router.get("/dispatches")
def list_dispatches(
    status_: Optional[str] = Query(default=None, alias="status"),
    page: Optional[int] = Query(default=None),
    limit: Optional[int] = Query(default=None, le=100),
    user: CurrentUser = Depends(require_permission("intake", "read")),
    db: Session = Depends(get_db),
):
    p, lim = normalize_pagination(page, limit)
    items, total = svc.list_dispatches(db, user=user, status=status_, page=p, limit=lim)
    return paginated(items, page=p, limit=lim, total=total)


@router.get("/dispatches/{dispatch_id}")
def get_dispatch(
    dispatch_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("intake", "read")),
    db: Session = Depends(get_db),
):
    return ok(svc.get_dispatch(db, dispatch_id=dispatch_id, user=user))


@router.patch("/dispatches/{dispatch_id}")
def update_dispatch(
    dispatch_id: uuid.UUID,
    body: UpdateDispatchRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("dispatch", "update")),
    db: Session = Depends(get_db),
):
    data = svc.update_dispatch(
        db, user=user, dispatch_id=dispatch_id, changes=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request), ip=client_ip(request),
    )
    return ok(data)


# ===== m26: Xin xem thông tin khách hàng (khối lab → Phòng nhận mẫu) =====
@router.post("/intakes/{intake_id}/info-requests", status_code=status.HTTP_201_CREATED)
def create_info_request(
    intake_id: uuid.UUID,
    body: CreateInfoRequestBody,
    request: Request,
    user: CurrentUser = Depends(require_permission("intake", "read")),
    db: Session = Depends(get_db),
):
    """Phòng lab gửi yêu cầu xin xem thông tin khách hàng của phiếu."""
    return ok(cir_svc.create_request(
        db, user=user, intake_id=intake_id, reason=body.reason,
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.get("/customer-info-requests")
def list_info_requests(
    status_: Optional[str] = Query(default=None, alias="status"),
    intake_id: Optional[uuid.UUID] = Query(default=None),
    page: Optional[int] = Query(default=None),
    limit: Optional[int] = Query(default=None, le=100),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Phòng nhận mẫu/quản trị xem tất cả; khối lab chỉ thấy yêu cầu của phòng mình."""
    p, lim = normalize_pagination(page, limit)
    items, total = cir_svc.list_requests(
        db, user=user, status=status_, intake_id=intake_id, page=p, limit=lim,
    )
    return paginated(items, page=p, limit=lim, total=total)


@router.post("/customer-info-requests/{request_id}/approve")
def approve_info_request(
    request_id: uuid.UUID,
    body: DecideInfoRequestBody,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(cir_svc.decide_request(
        db, user=user, request_id=request_id, approve=True, note=body.note,
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.post("/customer-info-requests/{request_id}/reject")
def reject_info_request(
    request_id: uuid.UUID,
    body: DecideInfoRequestBody,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(cir_svc.decide_request(
        db, user=user, request_id=request_id, approve=False, note=body.note,
        correlation_id=_cid(request), ip=client_ip(request),
    ))


# ===== m27: Master data CHỈ TIÊU THỬ NGHIỆM (bảng giá phân tích) =====
# Phòng nhận mẫu + Ban lãnh đạo + Quản trị: toàn quyền. Vai trò khác: chỉ đọc.
@router.get("/test-parameters/matrices")
def list_test_matrices(user: CurrentUser = Depends(get_current_user)):
    """Danh sách nhóm nền mẫu (đất/nước/phân bón/…)."""
    return ok(tp_svc.matrix_options())


@router.get("/test-parameters")
def list_test_parameters(
    q: Optional[str] = Query(default=None),
    matrix: Optional[str] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    unassigned: bool = Query(default=False, description="Chỉ lấy chỉ tiêu chưa gán phòng lab"),
    page: Optional[int] = Query(default=None),
    limit: Optional[int] = Query(default=None, le=200),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p, lim = normalize_pagination(page, limit)
    items, total = tp_svc.list_parameters(
        db, q=q, matrix=matrix, department_id=department_id,
        is_active=is_active, unassigned=unassigned, page=p, limit=lim,
    )
    return paginated(items, page=p, limit=lim, total=total)


@router.get("/test-parameters/{parameter_id}")
def get_test_parameter(
    parameter_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(tp_svc.get_parameter(db, parameter_id=parameter_id))


@router.post("/test-parameters", status_code=status.HTTP_201_CREATED)
def create_test_parameter(
    body: CreateTestParameterRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(tp_svc.create_parameter(
        db, user=user, fields=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.patch("/test-parameters/{parameter_id}")
def update_test_parameter(
    parameter_id: uuid.UUID,
    body: UpdateTestParameterRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(tp_svc.update_parameter(
        db, user=user, parameter_id=parameter_id, changes=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.delete("/test-parameters/{parameter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_test_parameter(
    parameter_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tp_svc.delete_parameter(
        db, user=user, parameter_id=parameter_id, correlation_id=_cid(request), ip=client_ip(request),
    )
