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
    CreateIntakeItemsRequest,
    CreateTestParameterRequest,
    DecideInfoRequestBody,
    DispatchResponse,
    IntakeItemListResponse,
    IntakeItemResponse,
    IntakeResponse,
    IntakeContactListResponse,
    RecordIntakeConditionRequest,
    SetIntakeContactsRequest,
    UpdateIntakeItemRequest,
    SubmitDispatchResultRequest,
    SubmitDispatchResultResponse,
    UpdateDispatchRequest,
    UpdateDispatchResultRequest,
    UpdateIntakeRequest,
    UpdatePaymentRequest,
    UpdateTestParameterRequest,
)
from app.core.deps import get_current_user
from app.services import customer_info_service as cir_svc
from app.services import dispatch_result_bridge as result_bridge
from app.services import intake_item_service as item_svc
from app.services import intake_contact_service as contact_svc
from app.services import intake_lifecycle_service as lifecycle_svc
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
    return ok(lifecycle_svc.change_status(
        db, user=user, intake_id=intake_id, new_status=body.status, note=body.note,
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.patch("/intakes/{intake_id}/condition", response_model=IntakeResponse)
def record_intake_condition(
    intake_id: uuid.UUID,
    body: RecordIntakeConditionRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("intake", "manage")),
    db: Session = Depends(get_db),
):
    """Ghi nhận tình trạng & số lượng mẫu lúc tiếp nhận (m42).

    Nhận mẫu không đạt vẫn hợp lệ — nhưng phải mô tả sai lệch (ISO/IEC 17025 §7.4.2).
    Từ chối hẳn thì dùng POST /intakes/{id}/status với status='rejected'.
    """
    return ok(lifecycle_svc.record_condition(
        db, user=user, intake_id=intake_id, changes=body.model_dump(exclude_unset=True),
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
    return ok(lifecycle_svc.update_payment(
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
        intake_item_id=body.intake_item_id,
        correlation_id=_cid(request), ip=client_ip(request),
    )
    return ok(data)


# ===== m43: NGƯỜI LIÊN HỆ THEO VAI TRÒ =====
# Người mang mẫu tới ≠ người nhận kết quả ≠ người trả tiền. Bản chụp trên phiếu,
# không giữ khoá ngoại tới danh bạ (phiếu đã in không đổi theo sổ khách).
@router.get("/intakes/{intake_id}/contacts", response_model=IntakeContactListResponse)
def list_intake_contacts(
    intake_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("intake", "read")),
    db: Session = Depends(get_db),
):
    return ok(contact_svc.list_contacts(db, intake_id=intake_id))


@router.put("/intakes/{intake_id}/contacts", response_model=IntakeContactListResponse)
def set_intake_contacts(
    intake_id: uuid.UUID,
    body: SetIntakeContactsRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("intake", "manage")),
    db: Session = Depends(get_db),
):
    """Đặt lại CẢ BỘ người liên hệ theo vai — khớp thao tác trên màn hình quầy."""
    return ok(contact_svc.set_contacts(
        db, user=user, intake_id=intake_id,
        contacts=[c.model_dump() for c in body.contacts],
        correlation_id=_cid(request), ip=client_ip(request),
    ))


# ===== m38: CHỈ TIÊU KHÁCH ĐẶT (nguồn để lập báo giá) =====
# Tách khỏi phiếu giao việc: thêm chỉ tiêu ở đây KHÔNG chuyển mẫu cho phòng lab và
# KHÔNG đổi trạng thái phiếu, nên báo giá lập được trước khi giao việc.
@router.get("/intakes/{intake_id}/items", response_model=IntakeItemListResponse)
def list_intake_items(
    intake_id: uuid.UUID,
    user: CurrentUser = Depends(require_permission("intake", "read")),
    db: Session = Depends(get_db),
):
    return ok(item_svc.list_items(db, intake_id=intake_id))


@router.post(
    "/intakes/{intake_id}/items",
    status_code=status.HTTP_201_CREATED,
    response_model=IntakeItemListResponse,
)
def add_intake_items(
    intake_id: uuid.UUID,
    body: CreateIntakeItemsRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("intake", "manage")),
    db: Session = Depends(get_db),
):
    """Ghi nhận khách đặt những chỉ tiêu nào — chưa giao việc cho phòng lab."""
    return ok(item_svc.add_items(
        db, user=user, intake_id=intake_id,
        items=[i.model_dump(exclude_unset=True) for i in body.items],
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.patch("/intakes/{intake_id}/items/{item_id}", response_model=IntakeItemResponse)
def update_intake_item(
    intake_id: uuid.UUID,
    item_id: uuid.UUID,
    body: UpdateIntakeItemRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("intake", "manage")),
    db: Session = Depends(get_db),
):
    return ok(item_svc.update_item(
        db, user=user, intake_id=intake_id, item_id=item_id,
        changes=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.delete(
    "/intakes/{intake_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_intake_item(
    intake_id: uuid.UUID,
    item_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(require_permission("intake", "manage")),
    db: Session = Depends(get_db),
):
    """Xoá dòng đặt hàng — chặn nếu đã giao cho phòng lab."""
    item_svc.delete_item(
        db, user=user, intake_id=intake_id, item_id=item_id,
        correlation_id=_cid(request), ip=client_ip(request),
    )


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
    """Phòng nhận mẫu sửa nội dung HÀNH CHÍNH của lượt chuyển (ghi chú, tên mẫu, số lượng)."""
    data = svc.update_dispatch(
        db, user=user, dispatch_id=dispatch_id, changes=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request), ip=client_ip(request),
    )
    return ok(data)


@router.patch("/dispatches/{dispatch_id}/result", response_model=DispatchResponse)
def update_dispatch_result(
    dispatch_id: uuid.UUID,
    body: UpdateDispatchResultRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("dispatch", "result")),
    db: Session = Depends(get_db),
):
    """Phòng lab ghi KẾT QUẢ và trạng thái thực hiện (m37).

    Endpoint riêng với quyền riêng `dispatch:result`. Người thực hiện lấy từ tài
    khoản đăng nhập — body KHÔNG nhận `can_bo`/`performed_by`.
    """
    data = svc.update_dispatch_result(
        db, user=user, dispatch_id=dispatch_id, changes=body.model_dump(exclude_unset=True),
        correlation_id=_cid(request), ip=client_ip(request),
    )
    return ok(data)


@router.post(
    "/dispatches/{dispatch_id}/result/submit",
    status_code=status.HTTP_201_CREATED,
    response_model=SubmitDispatchResultResponse,
)
def submit_dispatch_result(
    dispatch_id: uuid.UUID,
    body: SubmitDispatchResultRequest,
    request: Request,
    user: CurrentUser = Depends(require_permission("dispatch", "result")),
    db: Session = Depends(get_db),
):
    """Gửi kết quả đi DUYỆT (m40).

    Từ đây kết quả đi theo luật của module M1: có phiên bản, bản đã duyệt là bất
    biến, và người duyệt phải khác người nhập. Duyệt / trả lại / tạo phiên bản sửa
    dùng các endpoint sẵn có: POST /results/{id}/approve | /return | /revisions.
    """
    return ok(result_bridge.submit_from_dispatch(
        db, user=user, dispatch_id=dispatch_id, note=body.note,
        correlation_id=_cid(request), ip=client_ip(request),
    ))


@router.delete("/dispatches/{dispatch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dispatch(
    dispatch_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(require_permission("intake", "manage")),
    db: Session = Depends(get_db),
):
    """Xoá dòng chỉ tiêu chuyển nhầm — chỉ khi phòng lab CHƯA tiếp nhận."""
    svc.delete_dispatch(
        db, user=user, dispatch_id=dispatch_id,
        correlation_id=_cid(request), ip=client_ip(request),
    )


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
