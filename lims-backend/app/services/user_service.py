"""User service — CRUD user (admin), enable/disable, reset password.

Bảo vệ: chặn self-disable, chặn hạ/vô hiệu admin cuối cùng (LAST_ADMIN_PROTECTED).
Disable → revoke toàn bộ phiên user (refresh + sẽ chặn access qua re-check status).
KHÔNG trả password_hash.
"""
import uuid
from typing import Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.core import security
from app.core.exceptions import (
    AppException,
    conflict,
    not_found,
    unprocessable,
)
from app.models.department import Department
from app.models.refresh_token import RefreshToken
from app.models.user import User, VALID_ROLES
from app.services import audit_service, avatar_service, email_service


def _get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("Không tìm thấy người dùng")
    return user


def _email_exists(db: Session, email: str, exclude_id: Optional[uuid.UUID] = None) -> bool:
    q = select(User.id).where(User.email == email)
    if exclude_id:
        q = q.where(User.id != exclude_id)
    return db.execute(q).first() is not None


def _count_active_admins(db: Session, exclude_id: Optional[uuid.UUID] = None) -> int:
    q = select(func.count()).select_from(User).where(
        User.role == "admin", User.status == "active"
    )
    if exclude_id:
        q = q.where(User.id != exclude_id)
    return db.execute(q).scalar_one()


def _validate_department(db: Session, department_id: uuid.UUID) -> Department:
    dept = db.get(Department, department_id)
    if dept is None:
        raise AppException(
            "DEPARTMENT_NOT_FOUND", "Phòng ban không tồn tại", 404
        )
    return dept


def list_users(
    db: Session,
    *,
    q: Optional[str],
    role: Optional[str],
    department_id: Optional[uuid.UUID],
    status: Optional[str],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    if q:
        like = f"%{q}%"
        conditions.append(or_(User.full_name.ilike(like), User.email.ilike(like)))
    if role:
        conditions.append(User.role == role)
    if department_id:
        conditions.append(User.department_id == department_id)
    if status:
        conditions.append(User.status == status)

    total = db.execute(
        select(func.count()).select_from(User).where(*conditions)
    ).scalar_one()

    rows = db.execute(
        select(User)
        .where(*conditions)
        .order_by(User.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()

    # nạp tên phòng + cờ lead
    result = [_serialize_user_list(db, u) for u in rows]
    return result, total


def _serialize_user_list(db: Session, user: User) -> dict:
    dept = db.get(Department, user.department_id) if user.department_id else None
    return {
        "id": user.id,
        "email": str(user.email),
        "full_name": user.full_name,
        "role": user.role,
        "department_id": user.department_id,
        "department_name": dept.name if dept else None,
        "is_dept_lead": bool(dept and dept.lead_user_id == user.id),
        "status": user.status,
        "email_verified_at": user.email_verified_at,
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
    }


def serialize_user_detail(db: Session, user: User) -> dict:
    dept = db.get(Department, user.department_id) if user.department_id else None
    return {
        "id": user.id,
        "email": str(user.email),
        "full_name": user.full_name,
        "role": user.role,
        "department": (
            {"id": dept.id, "name": dept.name, "code": dept.code} if dept else None
        ),
        "is_dept_lead": bool(dept and dept.lead_user_id == user.id),
        "status": user.status,
        "email_verified_at": user.email_verified_at,
        "avatar_url": avatar_service.avatar_url(user.avatar_key),
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def get_user(db: Session, user_id: uuid.UUID) -> dict:
    return serialize_user_detail(db, _get_user_or_404(db, user_id))


def create_user(
    db: Session,
    *,
    actor_id: uuid.UUID,
    email: str,
    full_name: str,
    role: str,
    department_id: Optional[uuid.UUID],
    password: Optional[str],
    is_dept_lead: bool,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    email_norm = email.strip().lower()
    if _email_exists(db, email_norm):
        raise conflict("EMAIL_EXISTS", "Email đã tồn tại trong hệ thống")
    if role not in VALID_ROLES:
        raise AppException("VALIDATION_ERROR", "Vai trò không hợp lệ", 400)

    dept = None
    if department_id is not None:
        dept = _validate_department(db, department_id)

    # Nếu admin để trống password → sinh tạm + buộc đổi lần đầu (password_changed_at NULL)
    must_change = password is None or password == ""
    raw_password = password if not must_change else security.generate_temp_password()

    user = User(
        email=email_norm,
        password_hash=security.hash_password(raw_password),
        full_name=full_name.strip(),
        department_id=department_id,
        role=role,
        status="active",
        password_changed_at=None if must_change else func.now(),
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(user)
    db.flush()

    if is_dept_lead and dept is not None:
        dept.lead_user_id = user.id
        dept.updated_by = actor_id

    audit_service.log_action(
        db,
        action="USER_CREATE",
        resource="user",
        user_id=actor_id,
        resource_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"email": email_norm, "role": role, "department_id": str(department_id) if department_id else None},
    )
    db.commit()
    db.refresh(user)

    data = serialize_user_detail(db, user)
    data["must_change_password"] = must_change
    return data


def update_user(
    db: Session,
    *,
    actor_id: uuid.UUID,
    user_id: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    user = _get_user_or_404(db, user_id)
    diff: dict = {}

    if "email" in changes and changes["email"] is not None:
        email_norm = changes["email"].strip().lower()
        if email_norm != str(user.email):
            if _email_exists(db, email_norm, exclude_id=user.id):
                raise conflict("EMAIL_EXISTS", "Email đã tồn tại")
            diff["email"] = {"from": str(user.email), "to": email_norm}
            user.email = email_norm

    if "full_name" in changes and changes["full_name"] is not None:
        user.full_name = changes["full_name"].strip()
        diff["full_name"] = user.full_name

    if "role" in changes and changes["role"] is not None:
        new_role = changes["role"]
        if new_role != user.role:
            # Chặn hạ vai trò admin cuối cùng
            if user.role == "admin" and new_role != "admin":
                if _count_active_admins(db, exclude_id=user.id) == 0:
                    raise unprocessable(
                        "LAST_ADMIN_PROTECTED",
                        "Không thể hạ vai trò admin cuối cùng của hệ thống",
                    )
            diff["role"] = {"from": user.role, "to": new_role}
            user.role = new_role

    if "department_id" in changes:
        new_dept = changes["department_id"]
        if new_dept is not None:
            _validate_department(db, new_dept)
        if new_dept != user.department_id:
            diff["department_id"] = {
                "from": str(user.department_id) if user.department_id else None,
                "to": str(new_dept) if new_dept else None,
            }
            user.department_id = new_dept

    if not diff:
        raise AppException("VALIDATION_ERROR", "Không có thay đổi nào hợp lệ", 400)

    user.updated_by = actor_id
    user.updated_at = func.now()

    audit_service.log_action(
        db,
        action="USER_UPDATE",
        resource="user",
        user_id=actor_id,
        resource_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"diff": diff},
    )
    db.commit()
    db.refresh(user)
    return serialize_user_detail(db, user)


def set_status(
    db: Session,
    *,
    actor_id: uuid.UUID,
    user_id: uuid.UUID,
    enable: bool,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    user = _get_user_or_404(db, user_id)

    if not enable:
        # Chặn self-disable
        if user.id == actor_id:
            raise unprocessable(
                "SELF_DISABLE_FORBIDDEN", "Không thể tự vô hiệu hóa chính mình"
            )
        # Chặn vô hiệu admin cuối cùng
        if user.role == "admin" and user.status == "active":
            if _count_active_admins(db, exclude_id=user.id) == 0:
                raise unprocessable(
                    "LAST_ADMIN_PROTECTED",
                    "Không thể vô hiệu hóa admin cuối cùng của hệ thống",
                )

    user.status = "active" if enable else "disabled"
    user.updated_by = actor_id
    user.updated_at = func.now()

    if not enable:
        # Revoke toàn bộ phiên user (cắt phiên ngay — refresh token)
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=func.now())
        )
        # Access token còn hạn bị chặn bởi re-check status trong get_current_user.

    audit_service.log_action(
        db,
        action="USER_ENABLE" if enable else "USER_DISABLE",
        resource="user",
        user_id=actor_id,
        resource_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
    )
    db.commit()
    db.refresh(user)
    return {"id": user.id, "status": user.status}


def reset_password(
    db: Session,
    *,
    actor_id: uuid.UUID,
    user_id: uuid.UUID,
    new_password: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    user = _get_user_or_404(db, user_id)
    must_change = new_password is None or new_password == ""
    raw = new_password if not must_change else security.generate_temp_password()

    user.password_hash = security.hash_password(raw)
    # must_change=True → password_changed_at NULL ép đổi lần kế
    user.password_changed_at = None if must_change else func.now()
    user.updated_by = actor_id
    user.updated_at = func.now()

    # Revoke toàn bộ refresh token user (buộc đăng nhập lại)
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=func.now())
    )

    audit_service.log_action(
        db,
        action="PASSWORD_RESET_ADMIN",
        resource="user",
        user_id=actor_id,
        resource_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
    )
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "must_change_password": must_change,
        "reset_at": user.updated_at,
    }


# ──────────────────────── m30: duyệt tài khoản tự đăng ký ────────────────────────

ROLE_LABELS_VI = {
    "admin": "Quản trị viên",
    "leader": "Ban lãnh đạo",
    "office": "Văn phòng",
    "staff": "Nhân viên / KTV",
    "reception": "Phòng nhận mẫu",
    "qms": "Quản lý chất lượng",
    "lab_manager": "Trưởng phòng lab",
}


def approve_registration(
    db: Session,
    *,
    actor_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
    department_id: Optional[uuid.UUID],
    is_dept_lead: bool = False,
    correlation_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> dict:
    """Kích hoạt tài khoản đang chờ, gán vai trò + phòng ban thật.

    Đây là điểm DUY NHẤT biến 'pending' → 'active'. Vai trò do Quản trị viên chọn ở
    bước này, không phải do người đăng ký khai — chặn tự cấp quyền.
    """
    user = _get_user_or_404(db, user_id)

    if user.status != "pending":
        raise unprocessable(
            "NOT_PENDING", "Tài khoản này không ở trạng thái chờ duyệt"
        )
    if user.email_verified_at is None:
        raise unprocessable(
            "EMAIL_NOT_VERIFIED",
            "Người dùng chưa xác thực địa chỉ email. Chưa thể duyệt tài khoản.",
        )
    if role not in VALID_ROLES:
        raise unprocessable("INVALID_ROLE", "Vai trò không hợp lệ")

    dept = _validate_department(db, department_id) if department_id else None

    user.role = role
    user.department_id = department_id
    user.status = "active"
    user.updated_by = actor_id
    user.updated_at = func.now()

    # is_dept_lead không phải cột của users — nó là quan hệ departments.lead_user_id
    # (giữ đúng mô hình hiện có, không nhân bản trạng thái).
    if dept is not None and is_dept_lead:
        dept.lead_user_id = user.id

    audit_service.log_action(
        db,
        action="APPROVE_REGISTRATION",
        resource="user",
        user_id=actor_id,
        resource_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"role": role, "department_id": str(department_id) if department_id else None},
    )
    db.commit()
    db.refresh(user)

    email_service.send_account_approved(
        to=str(user.email),
        full_name=user.full_name,
        role_label=ROLE_LABELS_VI.get(role, role),
        login_url=f"{settings.app_public_url}/login",
    )
    return serialize_user_detail(db, user)


def reject_registration(
    db: Session,
    *,
    actor_id: uuid.UUID,
    user_id: uuid.UUID,
    reason: str,
    correlation_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> dict:
    """Từ chối yêu cầu mở tài khoản → chuyển sang 'disabled'.

    Cố ý KHÔNG xoá bản ghi: audit trail của ISO/IEC 17025 cần lưu vết ai đã yêu cầu
    và ai đã từ chối. Ngoài ra giữ hàng users cũng chặn đăng ký lại spam cùng email.
    """
    user = _get_user_or_404(db, user_id)
    if user.status != "pending":
        raise unprocessable(
            "NOT_PENDING", "Tài khoản này không ở trạng thái chờ duyệt"
        )

    user.status = "disabled"
    user.updated_by = actor_id
    user.updated_at = func.now()

    audit_service.log_action(
        db,
        action="REJECT_REGISTRATION",
        resource="user",
        user_id=actor_id,
        resource_id=user.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"reason": reason},
    )
    db.commit()

    email_service.send_account_rejected(
        to=str(user.email), full_name=user.full_name, reason=reason
    )
    return {"id": user.id, "status": "disabled"}
