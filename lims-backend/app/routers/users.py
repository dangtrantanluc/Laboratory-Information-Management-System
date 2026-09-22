"""Router users (M7.3) — CRUD + enable/disable + reset-password. CHỈ admin.

NGOẠI LỆ: GET /users mở thêm cho `office`. Modal "Thêm hồ sơ nhân sự" (M4.1) cần
liệt kê tài khoản để gắn 1-1, mà tạo hồ sơ = admin + office (hr_common.
assert_can_manage_profile). Trước đây list chỉ admin nên office mở modal ra thấy
dropdown rỗng. Mọi thao tác GHI trên user vẫn chỉ admin.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.request_meta import client_ip
from app.core.deps import CurrentUser, require_roles
from app.core.responses import normalize_pagination, ok, paginated
from app.db.database import get_db
from app.schemas.user import (
    ApproveUserRequest,
    CreateUserRequest,
    LockoutListResponse,
    RejectUserRequest,
    ResetPasswordRequest,
    UnlockResponse,
    UpdateUserRequest,
)
from app.services import lockout_service, user_service

router = APIRouter(prefix="/users", tags=["users"])

# Mọi endpoint user chỉ admin (RBAC matrix: quản trị user chỉ admin)
admin_only = require_roles("admin")
# Chỉ dùng cho GET /users — xem docstring module
can_list_users = require_roles("admin", "office")


def _cid(request: Request) -> Optional[str]:
    return getattr(request.state, "correlation_id", None)


@router.get("")
def list_users(
    request: Request,
    q: Optional[str] = Query(default=None, max_length=100),
    role: Optional[str] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: CurrentUser = Depends(can_list_users),
    db: Session = Depends(get_db),
):
    page, limit = normalize_pagination(page, limit)
    items, total = user_service.list_users(
        db,
        q=q,
        role=role,
        department_id=department_id,
        status=status_filter,
        page=page,
        limit=limit,
    )
    return paginated(items, page=page, limit=limit, total=total)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    data = user_service.create_user(
        db,
        actor_id=user.id,
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        department_id=body.department_id,
        password=body.password,
        is_dept_lead=body.is_dept_lead,
        correlation_id=_cid(request),
        ip=client_ip(request),
    )
    return ok(data)


# ===================== m49: tài khoản bị khoá đăng nhập =====================
#
# ĐẶT TRƯỚC `/{user_id}` là bắt buộc, không phải thói quen: FastAPI khớp tuyến theo thứ
# tự khai báo, nên nếu đứng sau thì "lockouts" bị đem đi phân giải thành UUID và trả 422.
@router.get("/lockouts", response_model=LockoutListResponse)
def list_lockouts(
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    """Ai đang bị khoá đăng nhập, và ai đang sai mật khẩu liên tiếp nhưng chưa khoá.

    Trạng thái khoá nằm ở Redis và TỰ HẾT HẠN, nên đây là ảnh chụp hiện tại. Lịch sử
    tra ở Nhật ký hệ thống với hành động ACCOUNT_LOCKED / ACCOUNT_UNLOCKED.
    """
    return ok(lockout_service.list_lockouts(db, user=user))


@router.post("/{user_id}/unlock", response_model=UnlockResponse)
def unlock_user(
    user_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    """Mở khoá ngay, không chờ hết hạn. Xoá khoá ở MỌI IP của tài khoản đó."""
    return ok(lockout_service.unlock_user(
        db, user=user, target_user_id=user_id,
        correlation_id=getattr(request.state, "correlation_id", None),
        ip=client_ip(request),
    ))


@router.get("/{user_id}")
def get_user(
    user_id: uuid.UUID,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return ok(user_service.get_user(db, user_id))


@router.patch("/{user_id}")
def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    # chỉ truyền field client thực sự gửi (phân biệt với default None)
    changes = body.model_dump(exclude_unset=True)
    data = user_service.update_user(
        db,
        actor_id=user.id,
        user_id=user_id,
        changes=changes,
        correlation_id=_cid(request),
        ip=client_ip(request),
    )
    return ok(data)


@router.post("/{user_id}/enable")
def enable_user(
    user_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return ok(
        user_service.set_status(
            db,
            actor_id=user.id,
            user_id=user_id,
            enable=True,
            correlation_id=_cid(request),
            ip=client_ip(request),
        )
    )


@router.post("/{user_id}/disable")
def disable_user(
    user_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return ok(
        user_service.set_status(
            db,
            actor_id=user.id,
            user_id=user_id,
            enable=False,
            correlation_id=_cid(request),
            ip=client_ip(request),
        )
    )


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: uuid.UUID,
    body: ResetPasswordRequest,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return ok(
        user_service.reset_password(
            db,
            actor_id=user.id,
            user_id=user_id,
            new_password=body.new_password,
            correlation_id=_cid(request),
            ip=client_ip(request),
        )
    )


# ═══════════════════ m30: duyệt tài khoản tự đăng ký (chỉ admin) ═══════════════════


@router.post("/{user_id}/approve")
def approve_registration(
    user_id: uuid.UUID,
    body: ApproveUserRequest,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    """Duyệt tài khoản đang chờ: gán vai trò + phòng ban thật rồi kích hoạt.

    Vai trò do Quản trị viên chọn ở đây, KHÔNG phải do người đăng ký khai.
    """
    data = user_service.approve_registration(
        db,
        actor_id=user.id,
        user_id=user_id,
        role=body.role,
        department_id=body.department_id,
        is_dept_lead=body.is_dept_lead,
        correlation_id=_cid(request),
        ip=client_ip(request),
    )
    return ok(data)


@router.post("/{user_id}/reject")
def reject_registration(
    user_id: uuid.UUID,
    body: RejectUserRequest,
    request: Request,
    user: CurrentUser = Depends(admin_only),
    db: Session = Depends(get_db),
):
    """Từ chối yêu cầu mở tài khoản (chuyển 'disabled', gửi mail báo lý do)."""
    data = user_service.reject_registration(
        db,
        actor_id=user.id,
        user_id=user_id,
        reason=body.reason,
        correlation_id=_cid(request),
        ip=client_ip(request),
    )
    return ok(data)
