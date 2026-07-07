"""Router auth (M7.1) — login, refresh, logout, me, đổi mật khẩu."""
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core import security
from app.core.deps import CurrentUser, get_current_user
from app.core.exceptions import AppException
from app.core.responses import ok
from app.db.database import get_db
from app.routers._cookies import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
    set_refresh_cookie,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    UpdateMeRequest,
)
from app.services import auth_service, rbac_service, user_service
from app.models.department import Department
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


@router.post("/login")
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


@router.post("/refresh")
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
        raise AppException("TOKEN_INVALID", "Thiếu refresh token", 401)

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
