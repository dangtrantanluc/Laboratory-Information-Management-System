"""Router auth (M7.1) — login, refresh, logout, me, đổi mật khẩu.

m30 bổ sung: tự đăng ký + xác thực email, quên/đặt lại mật khẩu, quản lý phiên
đăng nhập, ảnh đại diện.
"""
import uuid

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core import security
from app.core.error_codes import ErrorCode
from app.core.concurrency import upload_slot
from app.core.deps import CurrentUser, get_current_user
from app.core.exceptions import AppException
from app.core.rate_limit import rate_limit
from app.core.responses import ok
from app.db.database import get_db
from app.routers._cookies import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
    set_refresh_cookie,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordWithTokenRequest,
    UpdateMeRequest,
    VerifyEmailRequest,
)
from app.services import (
    account_service,
    auth_service,
    avatar_service,
    rbac_service,
    session_service,
    user_service,
)
from app.models.department import Department
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


# Hạn mức thuần-IP giờ chỉ là chốt chống flood THÔ: cả viện đi chung một IP NAT
# nên 20/phút là quá chặt (60 người đăng nhập lúc 8h sáng đã vượt). Giới hạn
# per-user thật nằm ở auth_service.login qua check_rate(email+IP) — 10 lần/5 phút.
@router.post("/login", dependencies=[Depends(rate_limit("login", limit=300, window_seconds=60))])
def login(
    body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
):
    cid = getattr(request.state, "correlation_id", None)
    result = auth_service.login(
        db,
        email=body.email,
        password=body.password,
        user_agent=request.headers.get("user-agent"),
        ip=_client_ip(request),
        correlation_id=cid,
    )
    refresh_raw = result.pop("refresh_token_raw")
    set_refresh_cookie(response, refresh_raw)
    return ok(result)


@router.post(
    "/refresh", dependencies=[Depends(rate_limit("refresh", limit=30, window_seconds=60))]
)
def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    db: Session = Depends(get_db),
):
    cid = getattr(request.state, "correlation_id", None)
    # Ưu tiên cookie; fallback body (native client)
    refresh_raw = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_raw and body and body.refresh_token:
        refresh_raw = body.refresh_token
    if not refresh_raw:
        raise AppException(ErrorCode.TOKEN_INVALID, "Thiếu refresh token", 401)

    result = auth_service.refresh(
        db,
        refresh_token_raw=refresh_raw,
        user_agent=request.headers.get("user-agent"),
        ip=_client_ip(request),
        correlation_id=cid,
    )
    new_refresh = result.pop("refresh_token_raw")
    set_refresh_cookie(response, new_refresh)
    return ok(result)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    all: bool = False,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cid = getattr(request.state, "correlation_id", None)
    refresh_raw = request.cookies.get(REFRESH_COOKIE_NAME)
    auth_service.logout(
        db,
        user_id=user.id,
        jti=user.jti,
        token_exp=user.token_exp,
        refresh_token_raw=refresh_raw,
        all_devices=all,
        correlation_id=cid,
        ip=_client_ip(request),
    )
    clear_refresh_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = db.get(User, user.id)
    dept = (
        db.get(Department, db_user.department_id) if db_user.department_id else None
    )
    permissions = rbac_service.get_effective_permissions_for_user(
        db, user.role, user.is_dept_lead
    )
    return ok(
        {
            "id": db_user.id,
            "email": str(db_user.email),
            "full_name": db_user.full_name,
            "role": db_user.role,
            "department": (
                {"id": dept.id, "name": dept.name, "code": dept.code} if dept else None
            ),
            "is_dept_lead": user.is_dept_lead,
            "is_quality_manager": bool(getattr(db_user, "is_quality_manager", False)),
            "status": db_user.status,
            "must_change_password": db_user.password_changed_at is None,
            # m30 — presigned URL TTL 15 phút. None nếu chưa đặt ảnh → frontend rơi
            # về avatar chữ cái đầu.
            "avatar_url": avatar_service.avatar_url(db_user.avatar_key),
            "email_verified_at": db_user.email_verified_at,
            "permissions": permissions,
            "created_at": db_user.created_at,
        }
    )


@router.patch("/me")
def update_me(
    body: UpdateMeRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tự cập nhật hồ sơ (họ tên/email). actor == chính chủ; chỉ field an toàn."""
    changes = body.model_dump(exclude_unset=True)
    data = user_service.update_user(
        db,
        actor_id=user.id,
        user_id=user.id,
        changes=changes,
        correlation_id=getattr(request.state, "correlation_id", None),
        ip=_client_ip(request),
    )
    return ok(data)


@router.patch("/me/password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cid = getattr(request.state, "correlation_id", None)
    refresh_raw = request.cookies.get(REFRESH_COOKIE_NAME)
    keep_hash = security.hash_refresh_token(refresh_raw) if refresh_raw else None
    changed_at = auth_service.change_own_password(
        db,
        user_id=user.id,
        current_password=body.current_password,
        new_password=body.new_password,
        keep_token_hash=keep_hash,
        correlation_id=cid,
        ip=_client_ip(request),
    )
    return ok({"id": user.id, "password_changed_at": changed_at})


# ═══════════════════════ m30: tự đăng ký & xác thực email ═══════════════════════
#
# Rate limit chặt hơn login: đây là endpoint không cần xác thực mà lại GỬI MAIL,
# nên là mục tiêu spam lý tưởng (bơm mail tới địa chỉ người khác).


@router.get("/registration-config")
def registration_config():
    """Frontend hỏi trước khi hiện form: có mở đăng ký không, giới hạn tên miền nào."""
    return ok(
        {
            "enabled": settings.self_registration_enabled,
            "allowed_domains": settings.self_registration_domain_list,
        }
    )


@router.post(
    "/register",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("register", limit=5, window_seconds=600))],
)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Đăng ký tài khoản. Luôn trả 202 + thông điệp chung — không tiết lộ email nào
    đã tồn tại. Tài khoản vào trạng thái 'pending', chưa đăng nhập được."""
    data = account_service.register(
        db,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        correlation_id=getattr(request.state, "correlation_id", None),
        ip=_client_ip(request),
    )
    return ok(data)


@router.post(
    "/verify-email",
    dependencies=[Depends(rate_limit("verify_email", limit=20, window_seconds=600))],
)
def verify_email(body: VerifyEmailRequest, request: Request, db: Session = Depends(get_db)):
    data = account_service.verify_email(
        db,
        raw_token=body.token,
        correlation_id=getattr(request.state, "correlation_id", None),
        ip=_client_ip(request),
    )
    return ok(data)


# ═══════════════════════ m30: quên / đặt lại mật khẩu ═══════════════════════


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("forgot_password", limit=5, window_seconds=600))],
)
def forgot_password(
    body: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)
):
    """Luôn trả 202 + thông điệp chung, dù email có tồn tại hay không."""
    data = account_service.forgot_password(
        db,
        email=body.email,
        correlation_id=getattr(request.state, "correlation_id", None),
        ip=_client_ip(request),
    )
    return ok(data)


@router.post(
    "/reset-password",
    dependencies=[Depends(rate_limit("reset_password", limit=10, window_seconds=600))],
)
def reset_password(
    body: ResetPasswordWithTokenRequest, request: Request, db: Session = Depends(get_db)
):
    data = account_service.reset_password(
        db,
        raw_token=body.token,
        new_password=body.new_password,
        correlation_id=getattr(request.state, "correlation_id", None),
        ip=_client_ip(request),
    )
    return ok(data)


# ═══════════════════════ m30: quản lý phiên đăng nhập ═══════════════════════


@router.get("/me/sessions")
def list_my_sessions(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Danh sách thiết bị đang đăng nhập. Phiên hiện tại được đánh dấu is_current."""
    refresh_raw = request.cookies.get(REFRESH_COOKIE_NAME)
    current_hash = security.hash_refresh_token(refresh_raw) if refresh_raw else None
    return ok(session_service.list_sessions(db, user_id=user.id, current_token_hash=current_hash))


@router.delete("/me/sessions/{session_id}")
def revoke_my_session(
    session_id: uuid.UUID,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = session_service.revoke_session(
        db,
        user_id=user.id,
        session_id=session_id,
        correlation_id=getattr(request.state, "correlation_id", None),
        ip=_client_ip(request),
    )
    return ok(data)


@router.post("/me/sessions/revoke-others")
def revoke_my_other_sessions(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Đăng xuất khỏi mọi thiết bị khác, giữ phiên hiện tại."""
    refresh_raw = request.cookies.get(REFRESH_COOKIE_NAME)
    keep_hash = security.hash_refresh_token(refresh_raw) if refresh_raw else None
    data = session_service.revoke_other_sessions(
        db,
        user_id=user.id,
        keep_token_hash=keep_hash,
        correlation_id=getattr(request.state, "correlation_id", None),
        ip=_client_ip(request),
    )
    return ok(data)


# ═══════════════════════ m30: ảnh đại diện ═══════════════════════


@router.post("/me/avatar")
def upload_my_avatar(
    request: Request,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tải ảnh đại diện lên MinIO. DB chỉ lưu object key; trả về presigned URL."""
    with upload_slot():
        content = file.file.read()
        data = avatar_service.upload_avatar(
            db,
            user_id=user.id,
            content=content,
            file_name=file.filename or "avatar",
            declared_mime=file.content_type,
            correlation_id=getattr(request.state, "correlation_id", None),
            ip=_client_ip(request),
        )
        return ok(data)


@router.delete("/me/avatar")
def remove_my_avatar(
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = avatar_service.remove_avatar(
        db,
        user_id=user.id,
        correlation_id=getattr(request.state, "correlation_id", None),
        ip=_client_ip(request),
    )
    return ok(data)
