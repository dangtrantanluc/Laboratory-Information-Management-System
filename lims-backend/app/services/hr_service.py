"""HR profile service (M4.1) — hồ sơ nhân sự, lương (hệ số×cơ sở), HĐ, chu kỳ, lịch sử
lương append-only, năng lực §6.2.

Field-level RBAC strip (lương/HĐ/PII) ở response (hr_common.strip_profile). Nâng lương
trong 1 transaction: append salary_history immutable + cập nhật mức hiện hành +
last_salary_raise_date + tính lại next_salary_raise_date + audit HR_SALARY_RAISE
(KHÔNG log giá trị tiền — BR-HR-024).
"""
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.db_helpers import get_or_404
from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.hr import Competence, ContractType, HrProfile, SalaryHistory
from app.models.user import User
from app.services import audit_service, hr_common as hc


# ===================== Serialize hồ sơ (đầy đủ — strip ở router/sau) =====================
def _profile_dict(db: Session, p: HrProfile) -> dict:
    # m48 — `user_id` có thể NULL (người trong sổ nhân sự, chưa có tài khoản). Tên lấy
    # từ CHÍNH HỒ SƠ, không từ `users`: hồ sơ chưa gắn thì không có hàng users nào.
    u = db.get(User, p.user_id) if p.user_id else None
    computed = hc.compute_salary_amount(p.salary_coefficient, p.base_salary_amount)
    # m49 — phòng công tác nằm TRÊN HỒ SƠ. Đường lùi về phòng của tài khoản giữ cho
    # những hồ sơ gắn tài khoản trước m49 (chưa kịp xếp phòng) không mất phòng ban.
    dept_id = p.department_id or (u.department_id if u else None)
    return {
        "id": p.id,
        "user_id": p.user_id,
        "has_account": u is not None,
        "full_name": p.full_name,
        "birth_year": p.birth_year,
        "email": str(u.email) if u else None,
        "department_id": dept_id,
        "department_name": hc.dept_name(db, dept_id) if dept_id else None,
        "job_title": p.job_title,
        "hired_date": p.hired_date.isoformat() if p.hired_date else None,
        "phone": p.phone,
        "position": p.position,
        # contract group
        "contract_type": p.contract_type,
        "contract_signed_date": p.contract_signed_date.isoformat()
        if p.contract_signed_date
        else None,
        "contract_end_date": p.contract_end_date.isoformat()
        if p.contract_end_date
        else None,
        # salary group
        "salary_grade": p.salary_grade,
        "salary_coefficient": hc.s_coeff(p.salary_coefficient),
        "base_salary_amount": hc.s_money(p.base_salary_amount),
        "computed_salary_amount": hc.s_money(computed),
        "currency": p.currency,
        "salary_cycle_years": p.salary_cycle_years,
        "last_salary_raise_date": p.last_salary_raise_date.isoformat()
        if p.last_salary_raise_date
        else None,
        "next_salary_raise_date": p.next_salary_raise_date.isoformat()
        if p.next_salary_raise_date
        else None,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _assert_department_exists(db: Session, department_id: Optional[uuid.UUID]) -> None:
    """Phòng phải có thật. FK cũng chặn, nhưng lỗi FK bật lên ở tầng DB thành 500 —
    người nhập cần biết "phòng không tồn tại", không phải một lỗi máy chủ."""
    if department_id is None:
        return
    from app.models.department import Department

    if db.get(Department, department_id) is None:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Phòng ban không tồn tại", 400)


def _get_profile_or_404(db: Session, user_id: uuid.UUID) -> HrProfile:
    return get_or_404(db, HrProfile, user_id, "Hồ sơ nhân sự không tồn tại", code=ErrorCode.PROFILE_NOT_FOUND)


def _recompute_next(p: HrProfile) -> None:
    p.next_salary_raise_date = hc.compute_next_salary_raise_date(
        last_salary_raise_date=p.last_salary_raise_date,
        contract_signed_date=p.contract_signed_date,
        salary_cycle_years=p.salary_cycle_years,
    )


# ===================== #1 LIST =====================
def list_profiles(
    db: Session,
    *,
    user: CurrentUser,
    q: Optional[str],
    department_id: Optional[uuid.UUID],
    job_title: Optional[str],
    contract_expiring_within_days: Optional[int],
    salary_raise_within_days: Optional[int],
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    conditions = []
    # LEFT JOIN, KHÔNG phải INNER: hồ sơ chưa gắn tài khoản không có hàng `users` nào,
    # inner join sẽ lặng lẽ loại 27/33 người khỏi màn hình danh sách.
    join_user = select(HrProfile).outerjoin(User, User.id == HrProfile.user_id)
    if q:
        like = f"%{q.strip()}%"
        # Tìm theo tên trên HỒ SƠ (luôn có), email chỉ là điều kiện phụ khi đã gắn.
        conditions.append(or_(HrProfile.full_name.ilike(like), User.email.ilike(like)))
    if department_id:
        # Khớp theo cùng quy tắc mà _profile_dict hiển thị: phòng trên hồ sơ trước,
        # phòng của tài khoản chỉ tính khi hồ sơ chưa xếp phòng. Lọc thẳng trên
        # User.department_id sẽ bỏ sót toàn bộ hồ sơ chưa gắn tài khoản.
        conditions.append(
            or_(
                HrProfile.department_id == department_id,
                and_(
                    HrProfile.department_id.is_(None),
                    User.department_id == department_id,
                ),
            )
        )
    if job_title:
        conditions.append(HrProfile.job_title.ilike(f"%{job_title.strip()}%"))
    today = date.today()
    if contract_expiring_within_days:
        from datetime import timedelta

        limit_date = today + timedelta(days=contract_expiring_within_days)
        conditions.append(HrProfile.contract_end_date.is_not(None))
        conditions.append(HrProfile.contract_end_date <= limit_date)
        conditions.append(HrProfile.contract_end_date >= today)
    if salary_raise_within_days:
        from datetime import timedelta

        limit_date = today + timedelta(days=salary_raise_within_days)
        conditions.append(HrProfile.next_salary_raise_date.is_not(None))
        conditions.append(HrProfile.next_salary_raise_date <= limit_date)
        conditions.append(HrProfile.next_salary_raise_date >= today)

    total = db.execute(
        select(func.count())
        .select_from(HrProfile)
        .outerjoin(User, User.id == HrProfile.user_id)
        .where(*conditions)
    ).scalar_one()
    rows = db.execute(
        join_user.where(*conditions)
        .order_by(HrProfile.full_name.asc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()

    return [hc.strip_profile(_profile_dict(db, p), user) for p in rows], total


# ===================== #2 CREATE =====================
def create_profile(
    db: Session,
    *,
    user: CurrentUser,
    full_name: str,
    job_title: str,
    hired_date: Optional[date],
    phone: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
    link_user_id: Optional[uuid.UUID] = None,
    birth_year: Optional[int] = None,
    department_id: Optional[uuid.UUID] = None,
) -> dict:
    hc.assert_can_manage_profile(user)
    if not full_name or not full_name.strip():
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu họ và tên", 400)
    if not job_title or not job_title.strip():
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu chức danh (job_title)", 400)

    # m48 — gắn tài khoản là TUỲ CHỌN. Người chưa có tài khoản vẫn phải vào được sổ
    # nhân sự; đó là lý do lược đồ đổi khoá.
    if link_user_id is not None:
        target = db.get(User, link_user_id)
        if target is None:
            raise AppException(ErrorCode.USER_NOT_FOUND, "Người dùng không tồn tại", 404)
        existing = db.execute(
            select(HrProfile).where(HrProfile.user_id == link_user_id)
        ).scalar_one_or_none()
        if existing is not None:
            raise AppException(
                ErrorCode.DUPLICATE_PROFILE,
                f"Tài khoản này đã gắn với hồ sơ '{existing.full_name}'",
                409,
            )

    _assert_department_exists(db, department_id)

    p = HrProfile(
        user_id=link_user_id,
        full_name=full_name.strip(),
        birth_year=birth_year,
        department_id=department_id,
        job_title=job_title.strip(),
        hired_date=hired_date,
        phone=phone,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(p)
    db.flush()
    audit_service.log_action(
        db,
        action="HR_PROFILE_CREATE",
        resource="hr_profile",
        user_id=user.id,
        resource_id=p.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"full_name": p.full_name, "job_title": p.job_title,
                "linked_user": str(link_user_id) if link_user_id else None},
    )
    db.commit()
    db.refresh(p)
    return hc.strip_profile(_profile_dict(db, p), user)


# ===================== #3 / #4 GET =====================
def get_profile(db: Session, *, user: CurrentUser, profile_id: uuid.UUID) -> dict:
    p = _get_profile_or_404(db, profile_id)
    # Staff chỉ xem hồ sơ của chính mình (contract #3). m48: so với TÀI KHOẢN ĐÃ GẮN
    # của hồ sơ — khoá hồ sơ giờ là id riêng, không còn trùng với id người dùng.
    if user.role == "staff" and p.user_id != user.id:
        raise hc.forbidden("Bạn chỉ được xem hồ sơ của chính mình")
    return hc.strip_profile(_profile_dict(db, p), user)


def get_my_profile(db: Session, *, user: CurrentUser) -> dict:
    p = db.execute(select(HrProfile).where(HrProfile.user_id == user.id)).scalar_one_or_none()
    if p is None:
        raise AppException(
            ErrorCode.PROFILE_NOT_FOUND, "Bạn chưa có hồ sơ nhân sự", 404
        )
    # Chính chủ luôn xem đầy đủ — strip vẫn áp nhưng of_self=True nên giữ nguyên
    return hc.strip_profile(_profile_dict(db, p), user)


# ============ m48: GẮN HỒ SƠ ↔ TÀI KHOẢN ============
#
# Ba tình huống có thật, và đây là cách xử lý từng cái:
#
#  1. Có hồ sơ trước, sau mới có tài khoản (phần lớn danh sách CBVC 2026)
#     → `suggest_profiles_for_user` gợi ý hồ sơ chưa gắn TRÙNG TÊN khi tạo/duyệt tài
#       khoản; người duyệt bấm `link_account`.
#  2. Có tài khoản trước, chưa có hồ sơ (người mới được cấp tài khoản ngay)
#     → tạo hồ sơ với `link_user_id` trỏ sang tài khoản đó.
#  3. Người mới, không tài khoản và không có trong danh sách
#     → chỉ tạo hồ sơ, `user_id` để trống. Không cần thao tác gì thêm.
#
# VÌ SAO KHÔNG TỰ ĐỘNG GẮN THEO TÊN
# Trùng họ tên là chuyện bình thường ở Việt Nam. Gắn tự động sẽ nối hồ sơ lương và
# bằng cấp của người này vào tài khoản người khác — một lỗi âm thầm, phát hiện ra thì
# đã lan sang bảng lương. Vì vậy hệ thống chỉ GỢI Ý, người duyệt xác nhận.


def _norm_name(v: str) -> str:
    """Chuẩn hoá tên để so khớp: bỏ hoa/thường và khoảng trắng thừa."""
    return " ".join((v or "").split()).lower()


def suggest_profiles_for_user(db: Session, *, user: CurrentUser, target_user_id: uuid.UUID) -> list[dict]:
    """Hồ sơ CHƯA GẮN có tên trùng với một tài khoản — để người duyệt chọn."""
    hc.assert_can_manage_profile(user)
    target = db.get(User, target_user_id)
    if target is None:
        raise AppException(ErrorCode.USER_NOT_FOUND, "Người dùng không tồn tại", 404)
    rows = db.execute(
        select(HrProfile).where(HrProfile.user_id.is_(None))
    ).scalars().all()
    want = _norm_name(target.full_name)
    return [
        {"id": p.id, "full_name": p.full_name, "birth_year": p.birth_year,
         "job_title": p.job_title, "contract_type": p.contract_type}
        for p in rows if _norm_name(p.full_name) == want
    ]


def link_account(
    db: Session, *, user: CurrentUser, profile_id: uuid.UUID, target_user_id: uuid.UUID,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Gắn một hồ sơ nhân sự với một tài khoản. Quan hệ một-một, hai chiều."""
    hc.assert_can_manage_profile(user)
    p = _get_profile_or_404(db, profile_id)
    if p.user_id is not None:
        raise AppException(
            ErrorCode.DUPLICATE_PROFILE,
            f"Hồ sơ '{p.full_name}' đã gắn tài khoản khác — gỡ trước khi gắn lại",
            409,
        )
    target = db.get(User, target_user_id)
    if target is None:
        raise AppException(ErrorCode.USER_NOT_FOUND, "Người dùng không tồn tại", 404)
    taken = db.execute(
        select(HrProfile).where(HrProfile.user_id == target_user_id)
    ).scalar_one_or_none()
    if taken is not None:
        raise AppException(
            ErrorCode.DUPLICATE_PROFILE,
            f"Tài khoản này đã gắn với hồ sơ '{taken.full_name}'",
            409,
        )

    p.user_id = target_user_id
    p.updated_by = user.id
    p.updated_at = func.now()
    audit_service.log_action(
        db, action="HR_PROFILE_LINK", resource="hr_profile", user_id=user.id,
        resource_id=p.id, correlation_id=correlation_id, ip=ip,
        detail={"full_name": p.full_name, "linked_user": str(target_user_id)},
    )
    db.commit()
    db.refresh(p)
    return hc.strip_profile(_profile_dict(db, p), user)


def unlink_account(
    db: Session, *, user: CurrentUser, profile_id: uuid.UUID,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Gỡ liên kết. Hồ sơ Ở LẠI sổ nhân sự — người vẫn làm ở Viện, chỉ là thôi dùng
    phần mềm hoặc gắn nhầm tài khoản."""
    hc.assert_can_manage_profile(user)
    p = _get_profile_or_404(db, profile_id)
    if p.user_id is None:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Hồ sơ chưa gắn tài khoản nào", 400)
    old = p.user_id
    p.user_id = None
    p.updated_by = user.id
    p.updated_at = func.now()
    audit_service.log_action(
        db, action="HR_PROFILE_UNLINK", resource="hr_profile", user_id=user.id,
        resource_id=p.id, correlation_id=correlation_id, ip=ip,
        detail={"full_name": p.full_name, "unlinked_user": str(old)},
    )
    db.commit()
    db.refresh(p)
    return hc.strip_profile(_profile_dict(db, p), user)


# ===================== #5 PATCH (phi tài chính) =====================
def update_profile(
    db: Session,
    *,
    user: CurrentUser,
    profile_id: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    hc.assert_can_manage_profile(user)
    p = _get_profile_or_404(db, profile_id)

    forbidden_fields = (hc.SALARY_FIELDS | hc.CONTRACT_FIELDS) - {"phone"}
    if any(k in forbidden_fields for k in changes):
        raise AppException(
            ErrorCode.VALIDATION_ERROR,
            "Lương/hợp đồng phải sửa qua endpoint riêng (/contract, /salary-raises, "
            "/salary-cycle)",
            400,
        )

    if "department_id" in changes:
        _assert_department_exists(db, changes["department_id"])

    changed_fields = []
    for field in ("full_name", "job_title", "hired_date", "phone", "position",
                  "birth_year", "department_id"):
        if field in changes:
            value = changes[field]
            if field in ("job_title", "full_name") and (not value or not str(value).strip()):
                raise AppException(ErrorCode.VALIDATION_ERROR, f"{field} không được rỗng", 400)
            setattr(p, field, value.strip() if isinstance(value, str) else value)
            changed_fields.append(field)
    if not changed_fields:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Body rỗng", 400)
    p.updated_by = user.id
    p.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="HR_PROFILE_UPDATE",
        resource="hr_profile",
        user_id=user.id,
        resource_id=profile_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"changed_fields": changed_fields},  # KHÔNG giá trị PII
    )
    db.commit()
    db.refresh(p)
    return hc.strip_profile(_profile_dict(db, p), user)


# ===================== #6 PATCH contract =====================
def update_contract(
    db: Session,
    *,
    user: CurrentUser,
    profile_id: uuid.UUID,
    contract_signed_date: date,
    contract_type: str,
    contract_end_date: Optional[date],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    hc.assert_can_edit_salary(user)  # HĐ = nhóm tài chính → admin/office
    p = _get_profile_or_404(db, profile_id)
    if not contract_type:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu contract_type", 400)
    if db.get(ContractType, contract_type) is None:
        raise AppException(
            ErrorCode.INVALID_CONTRACT_TYPE, "Loại hợp đồng ngoài danh mục", 400
        )
    if contract_end_date and contract_end_date <= contract_signed_date:
        raise AppException(
            ErrorCode.INVALID_DATE_ORDER,
            "Ngày hết hạn HĐ phải sau ngày ký",
            422,
            [{"field": "contract_end_date", "message": "<= contract_signed_date"}],
        )
    p.contract_signed_date = contract_signed_date
    p.contract_type = contract_type
    p.contract_end_date = contract_end_date
    _recompute_next(p)
    p.updated_by = user.id
    p.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="HR_CONTRACT_UPDATE",
        resource="hr_profile",
        user_id=user.id,
        resource_id=profile_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"contract_type": contract_type},
    )
    db.commit()
    db.refresh(p)
    return {
        "user_id": p.user_id,
        "contract_signed_date": p.contract_signed_date.isoformat(),
        "contract_type": p.contract_type,
        "contract_end_date": p.contract_end_date.isoformat()
        if p.contract_end_date
        else None,
        "next_salary_raise_date": p.next_salary_raise_date.isoformat()
        if p.next_salary_raise_date
        else None,
    }


# ===================== #7 PATCH salary-cycle =====================
def update_salary_cycle(
    db: Session,
    *,
    user: CurrentUser,
    profile_id: uuid.UUID,
    salary_cycle_years: int,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    hc.assert_can_edit_salary(user)
    p = _get_profile_or_404(db, profile_id)
    if not isinstance(salary_cycle_years, int) or salary_cycle_years < 1:
        raise AppException(ErrorCode.INVALID_CYCLE, "salary_cycle_years phải là số nguyên >= 1", 400)
    p.salary_cycle_years = salary_cycle_years
    _recompute_next(p)
    p.updated_by = user.id
    p.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="HR_SALARY_CYCLE_UPDATE",
        resource="hr_profile",
        user_id=user.id,
        resource_id=profile_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"salary_cycle_years": salary_cycle_years},
    )
    db.commit()
    db.refresh(p)
    return {
        "user_id": p.user_id,
        "salary_cycle_years": p.salary_cycle_years,
        "next_salary_raise_date": p.next_salary_raise_date.isoformat()
        if p.next_salary_raise_date
        else None,
    }


# ===================== #8 POST salary-raises =====================
def create_salary_raise(
    db: Session,
    *,
    user: CurrentUser,
    profile_id: uuid.UUID,
    salary_grade: str,
    salary_coefficient: str,
    base_salary_amount: str,
    raise_date: date,
    note: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    hc.assert_can_edit_salary(user)  # leader/staff → SALARY_FORBIDDEN
    p = _get_profile_or_404(db, profile_id)

    if not salary_grade or not salary_grade.strip():
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu salary_grade", 400)
    coeff = hc.parse_decimal(salary_coefficient, field="salary_coefficient", positive=True)
    hc.assert_max_decimals(coeff, field="salary_coefficient", places=2)
    base = hc.parse_decimal(base_salary_amount, field="base_salary_amount", positive=True)
    hc.assert_max_decimals(base, field="base_salary_amount", places=2)
    coeff = hc.q_coeff(coeff)
    base = hc.q_money(base)

    if raise_date > date.today():
        raise AppException(
            ErrorCode.FUTURE_RAISE_NOT_ALLOWED, "Ngày nâng lương không được ở tương lai", 422
        )

    # Snapshot mức cũ → bản ghi lịch sử immutable
    sh = SalaryHistory(
        user_id=profile_id,
        old_grade=p.salary_grade,
        old_coefficient=p.salary_coefficient,
        old_base_amount=p.base_salary_amount,
        new_grade=salary_grade.strip(),
        new_coefficient=coeff,
        new_base_amount=base,
        currency=p.currency,
        raise_date=raise_date,
        note=note,
        by_user=user.id,
        correlation_id=correlation_id,
    )
    db.add(sh)

    # Cập nhật mức hiện hành + last + tính lại next (cùng transaction)
    p.salary_grade = salary_grade.strip()
    p.salary_coefficient = coeff
    p.base_salary_amount = base
    p.last_salary_raise_date = raise_date
    _recompute_next(p)
    p.updated_by = user.id
    p.updated_at = func.now()
    db.flush()

    # Audit: KHÔNG ghi giá trị tiền (BR-HR-024) — chỉ fact + ngày
    audit_service.log_action(
        db,
        action="HR_SALARY_RAISE",
        resource="hr_profile",
        user_id=user.id,
        resource_id=profile_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"raise_date": raise_date.isoformat(), "salary_history_id": str(sh.id)},
    )
    db.commit()
    db.refresh(p)
    db.refresh(sh)
    computed = hc.compute_salary_amount(p.salary_coefficient, p.base_salary_amount)
    return {
        "user_id": p.user_id,
        "salary_grade": p.salary_grade,
        "salary_coefficient": hc.s_coeff(p.salary_coefficient),
        "base_salary_amount": hc.s_money(p.base_salary_amount),
        "computed_salary_amount": hc.s_money(computed),
        "currency": p.currency,
        "last_salary_raise_date": p.last_salary_raise_date.isoformat(),
        "next_salary_raise_date": p.next_salary_raise_date.isoformat()
        if p.next_salary_raise_date
        else None,
        "salary_history_id": sh.id,
    }


# ===================== #9 GET salary-history =====================
def list_salary_history(
    db: Session,
    *,
    user: CurrentUser,
    profile_id: uuid.UUID,
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    p = _get_profile_or_404(db, profile_id)
    if not hc.can_read_salary(user, p.user_id):
        raise hc.salary_forbidden()

    total = db.execute(
        select(func.count())
        .select_from(SalaryHistory)
        .where(SalaryHistory.profile_id == profile_id)
    ).scalar_one()
    rows = db.execute(
        select(SalaryHistory)
        .where(SalaryHistory.profile_id == profile_id)
        .order_by(SalaryHistory.raise_date.desc(), SalaryHistory.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    items = [
        {
            "id": sh.id,
            "old_grade": sh.old_grade,
            "old_coefficient": hc.s_coeff(sh.old_coefficient),
            "old_base_amount": hc.s_money(sh.old_base_amount),
            "new_grade": sh.new_grade,
            "new_coefficient": hc.s_coeff(sh.new_coefficient),
            "new_base_amount": hc.s_money(sh.new_base_amount),
            "currency": sh.currency,
            "raise_date": sh.raise_date.isoformat(),
            "by_user_id": sh.by_user,
            "by_user_name": hc.user_name(db, sh.by_user),
            "note": sh.note,
            "created_at": sh.created_at,
        }
        for sh in rows
    ]
    return items, total


# ===================== Competences (#10-#13) =====================
def _competence_dict(db: Session, c: Competence) -> dict:
    is_expired = bool(c.expiry_date and c.expiry_date < date.today())
    return {
        "id": c.id,
        "profile_id": c.profile_id,
        "kind": c.kind,
        "title": c.title,
        "issuer": c.issuer,
        "issued_date": c.issued_date.isoformat() if c.issued_date else None,
        "expiry_date": c.expiry_date.isoformat() if c.expiry_date else None,
        "scope_detail": c.scope_detail,
        "authorized_by_user_id": c.authorized_by,
        "authorized_by_name": hc.user_name(db, c.authorized_by),
        "is_expired": is_expired,
        "created_at": c.created_at,
    }


def _assert_competence_read(user: CurrentUser, linked_user_id: Optional[uuid.UUID]) -> None:
    """Đọc năng lực: admin/leader (all); staff của mình. Office → 403 (không tài chính).

    m48 — tham số là TÀI KHOẢN ĐÃ GẮN của hồ sơ (có thể None khi hồ sơ chưa gắn). Với
    hồ sơ chưa gắn, không tồn tại "chính mình" nào cả, nên staff không xem được.
    """
    if user.role == "office":
        raise hc.forbidden("Văn phòng không quản lý hồ sơ năng lực")
    if user.role == "staff" and linked_user_id != user.id:
        raise hc.forbidden("Bạn chỉ được xem năng lực của chính mình")


def list_competences(
    db: Session,
    *,
    user: CurrentUser,
    profile_id: uuid.UUID,
    kind: Optional[str],
    status_filter: Optional[str],
) -> list[dict]:
    p = _get_profile_or_404(db, profile_id)
    _assert_competence_read(user, p.user_id)
    conditions = [Competence.profile_id == profile_id]
    if kind:
        if kind not in ("degree", "certificate", "authorization"):
            raise AppException(ErrorCode.VALIDATION_ERROR, "kind không hợp lệ", 400)
        conditions.append(Competence.kind == kind)
    rows = db.execute(
        select(Competence).where(*conditions).order_by(Competence.created_at.desc())
    ).scalars().all()
    items = [_competence_dict(db, c) for c in rows]
    if status_filter in ("valid", "expired"):
        want_expired = status_filter == "expired"
        items = [i for i in items if i["is_expired"] == want_expired]
    return items


def create_competence(
    db: Session,
    *,
    user: CurrentUser,
    profile_id: uuid.UUID,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    hc.assert_can_manage_competence(user)
    _get_profile_or_404(db, profile_id)
    c = _build_competence(db, profile_id, payload, user)
    db.add(c)
    db.flush()
    audit_service.log_action(
        db,
        action="HR_COMPETENCE_CHANGE",
        resource="competence",
        user_id=user.id,
        resource_id=c.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"op": "create", "kind": c.kind, "profile_id": str(profile_id)},
    )
    db.commit()
    db.refresh(c)
    return _competence_dict(db, c)


def _build_competence(
    db: Session, profile_id: uuid.UUID, payload: dict, user: CurrentUser
) -> Competence:
    kind = payload.get("kind")
    if kind not in ("degree", "certificate", "authorization"):
        raise AppException(ErrorCode.VALIDATION_ERROR, "kind không hợp lệ", 400)
    title = payload.get("title")
    if not title or not str(title).strip():
        raise AppException(ErrorCode.VALIDATION_ERROR, "Thiếu title", 400)
    issued = payload.get("issued_date")
    expiry = payload.get("expiry_date")
    if expiry and issued and expiry < issued:
        raise AppException(ErrorCode.INVALID_DATE_ORDER, "expiry_date phải >= issued_date", 422)
    scope_detail = payload.get("scope_detail")
    authorized_by = payload.get("authorized_by")
    if kind == "authorization":
        if not scope_detail or not str(scope_detail).strip():
            raise AppException(
                ErrorCode.VALIDATION_ERROR, "Thiếu scope_detail (bắt buộc khi ủy quyền)", 400
            )
        if not authorized_by:
            raise AppException(
                ErrorCode.VALIDATION_ERROR, "Thiếu authorized_by (bắt buộc khi ủy quyền)", 400
            )
        hc.assert_user_exists(db, authorized_by)
    return Competence(
        user_id=profile_id,
        kind=kind,
        title=str(title).strip(),
        issuer=payload.get("issuer"),
        issued_date=issued,
        expiry_date=expiry,
        scope_detail=scope_detail,
        authorized_by=authorized_by,
        created_by=user.id,
        updated_by=user.id,
    )


def update_competence(
    db: Session,
    *,
    user: CurrentUser,
    competence_id: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    hc.assert_can_manage_competence(user)
    c = db.get(Competence, competence_id)
    if c is None:
        raise AppException(ErrorCode.COMPETENCE_NOT_FOUND, "Mục năng lực không tồn tại", 404)
    if not changes:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Body rỗng", 400)
    new_issued = changes.get("issued_date", c.issued_date)
    new_expiry = changes.get("expiry_date", c.expiry_date)
    if new_expiry and new_issued and new_expiry < new_issued:
        raise AppException(ErrorCode.INVALID_DATE_ORDER, "expiry_date phải >= issued_date", 422)
    for field in (
        "kind",
        "title",
        "issuer",
        "issued_date",
        "expiry_date",
        "scope_detail",
        "authorized_by",
    ):
        if field in changes:
            value = changes[field]
            if field == "kind" and value not in (
                "degree",
                "certificate",
                "authorization",
            ):
                raise AppException(ErrorCode.VALIDATION_ERROR, "kind không hợp lệ", 400)
            if field == "authorized_by" and value is not None:
                hc.assert_user_exists(db, value)
            setattr(c, field, value)
    c.updated_by = user.id
    c.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="HR_COMPETENCE_CHANGE",
        resource="competence",
        user_id=user.id,
        resource_id=c.id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"op": "update", "changed_fields": list(changes.keys())},
    )
    db.commit()
    db.refresh(c)
    return _competence_dict(db, c)


def delete_competence(
    db: Session,
    *,
    user: CurrentUser,
    competence_id: uuid.UUID,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> None:
    hc.assert_can_manage_competence(user)
    c = db.get(Competence, competence_id)
    if c is None:
        raise AppException(ErrorCode.COMPETENCE_NOT_FOUND, "Mục năng lực không tồn tại", 404)
    target = c.user_id
    db.delete(c)
    audit_service.log_action(
        db,
        action="HR_COMPETENCE_CHANGE",
        resource="competence",
        user_id=user.id,
        resource_id=competence_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"op": "delete", "profile_id": str(target)},
    )
    db.commit()


def get_competence_or_404(db: Session, competence_id: uuid.UUID) -> Competence:
    c = db.get(Competence, competence_id)
    if c is None:
        raise AppException(ErrorCode.COMPETENCE_NOT_FOUND, "Mục năng lực không tồn tại", 404)
    return c
