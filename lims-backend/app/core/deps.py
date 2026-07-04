"""FastAPI dependencies: get_current_user, require_role, require_permission, scope.

Auth flow: Bearer access token → verify chữ ký/exp → check jti denylist (Redis) →
load user từ DB (kiểm status active) → trả CurrentUser.
"""
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Request
from jose import ExpiredSignatureError, JWTError
from sqlalchemy.orm import Session

from app.core import security
from app.core.exceptions import AppException, forbidden, unauthorized
from app.core.rbac import find_permission
from app.db.database import get_db
from app.models.department import Department
from app.models.user import User

logger = logging.getLogger("lims.deps")


@dataclass
class CurrentUser:
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    department_id: Optional[uuid.UUID]
    is_dept_lead: bool
    status: str
    jti: str
    token_exp: int


def _extract_bearer(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise unauthorized("Thiếu access token")
    return auth[7:].strip()


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> CurrentUser:
    token = _extract_bearer(request)
    try:
        payload = security.decode_access_token(token)
    except ExpiredSignatureError:
        raise AppException("TOKEN_EXPIRED", "Access token đã hết hạn", 401)
    except JWTError:
        raise AppException("TOKEN_INVALID", "Access token không hợp lệ", 401)

    jti = payload.get("jti", "")
    if not jti or security.is_jti_denied(jti):
        raise AppException("TOKEN_INVALID", "Phiên đã bị thu hồi", 401)

    sub = payload.get("sub")
    try:
        user_id = uuid.UUID(sub)
    except (TypeError, ValueError):
        raise AppException("TOKEN_INVALID", "Token không hợp lệ", 401)

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized("Người dùng không tồn tại")
    if user.status == "disabled":
        raise AppException("ACCOUNT_DISABLED", "Tài khoản đã bị vô hiệu hóa", 403)

    # is_dept_lead xác thực lại từ DB (claim có thể cũ; bảo mật ưu tiên DB cho thao tác lead)
    is_lead = False
    if user.department_id is not None:
        dept = db.get(Department, user.department_id)
        is_lead = bool(dept and dept.lead_user_id == user.id)

    return CurrentUser(
        id=user.id,
        email=str(user.email),
        full_name=user.full_name,
        role=user.role,
        department_id=user.department_id,
        is_dept_lead=is_lead,
        status=user.status,
        jti=jti,
        token_exp=int(payload.get("exp", 0)),
    )


def require_roles(*roles: str):
    """Dependency factory: chỉ cho các vai trò chỉ định (RBAC tầng API)."""

    def _checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            logger.warning(
                "RBAC role denied",
                extra={"userId": str(user.id), "role": user.role, "allowed": roles},
            )
            raise forbidden()
        return user

    return _checker


def require_permission(resource: str, action: str):
    """Dependency factory: yêu cầu quyền (resource, action) trong roles_permissions."""

    def _checker(
        user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> CurrentUser:
        perm = find_permission(db, user.role, resource, action)
        if perm is None:
            logger.warning(
                "RBAC permission denied",
                extra={
                    "userId": str(user.id),
                    "role": user.role,
                    "resource": resource,
                    "action": action,
                },
            )
            raise forbidden()
        return user

    return _checker
