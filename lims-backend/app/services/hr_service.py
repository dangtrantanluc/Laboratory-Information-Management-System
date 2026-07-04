"""HR profile service (M4.1) — hồ sơ nhân sự, lương (hệ số×cơ sở), HĐ, chu kỳ, lịch sử
lương append-only, năng lực §6.2.

Field-level RBAC strip (lương/HĐ/PII) ở response (hr_common.strip_profile). Nâng lương
trong 1 transaction: append salary_history immutable + cập nhật mức hiện hành +
last_salary_raise_date + tính lại next_salary_raise_date + audit HR_SALARY_RAISE
(KHÔNG log giá trị tiền — BR-HR-024).
"""
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.models.department import Department
from app.models.hr import (
    Competence,
    ContractType,
    HrProfile,
    SalaryHistory,
)
from app.models.user import User
from app.services import audit_service, hr_common as hc


# ===================== Serialize hồ sơ (đầy đủ — strip ở router/sau) =====================
def _profile_dict(db: Session, p: HrProfile) -> dict:
    u = db.get(User, p.user_id)
    computed = hc.compute_salary_amount(p.salary_coefficient, p.base_salary_amount)
    return {
        "user_id": p.user_id,
        "full_name": u.full_name if u else None,
        "email": str(u.email) if u else None,
        "department_id": u.department_id if u else None,
        "department_name": hc.dept_name(db, u.department_id) if u else None,
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


def _get_profile_or_404(db: Session, user_id: uuid.UUID) -> HrProfile:
    p = db.get(HrProfile, user_id)
    if p is None:
        raise AppException("PROFILE_NOT_FOUND", "Hồ sơ nhân sự không tồn tại", 404)
    return p


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
    join_user = select(HrProfile).join(User, User.id == HrProfile.user_id)
    if q:
        like = f"%{q.strip()}%"
        conditions.append(or_(User.full_name.ilike(like), User.email.ilike(like)))
    if department_id:
        conditions.append(User.department_id == department_id)
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
        .join(User, User.id == HrProfile.user_id)
        .where(*conditions)
    ).scalar_one()
    rows = db.execute(
        join_user.where(*conditions)
        .order_by(User.full_name.asc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()

    return [hc.strip_profile(_profile_dict(db, p), user) for p in rows], total


# ===================== #2 CREATE =====================
def create_profile(
    db: Session,
    *,
    user: CurrentUser,
    target_user_id: uuid.UUID,
    job_title: str,
    hired_date: Optional[date],
    phone: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    hc.assert_can_manage_profile(user)
    target = db.get(User, target_user_id)
    if target is None:
        raise AppException("USER_NOT_FOUND", "Người dùng không tồn tại", 404)
    if db.get(HrProfile, target_user_id) is not None:
        raise AppException(
            "DUPLICATE_PROFILE", "Người dùng đã có hồ sơ nhân sự (1-1)", 409
        )
    if not job_title or not job_title.strip():
        raise AppException("VALIDATION_ERROR", "Thiếu chức danh (job_title)", 400)

    p = HrProfile(
        user_id=target_user_id,
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
        resource_id=target_user_id,
        correlation_id=correlation_id,
        ip=ip,
        detail={"target_user_id": str(target_user_id), "job_title": job_title.strip()},
    )
    db.commit()
    db.refresh(p)
    return hc.strip_profile(_profile_dict(db, p), user)


# ===================== #3 / #4 GET =====================
def get_profile(db: Session, *, user: CurrentUser, target_user_id: uuid.UUID) -> dict:
    # Staff chỉ xem hồ sơ của chính mình (contract #3)
    if user.role == "staff" and user.id != target_user_id:
        raise hc.forbidden("Bạn chỉ được xem hồ sơ của chính mình")
    p = _get_profile_or_404(db, target_user_id)
    return hc.strip_profile(_profile_dict(db, p), user)


def get_my_profile(db: Session, *, user: CurrentUser) -> dict:
    p = _get_profile_or_404(db, user.id)
    # Chính chủ luôn xem đầy đủ — strip vẫn áp nhưng of_self=True nên giữ nguyên
    return hc.strip_profile(_profile_dict(db, p), user)


# ===================== #5 PATCH (phi tài chính) =====================
def update_profile(
    db: Session,
    *,
    user: CurrentUser,
    target_user_id: uuid.UUID,
    changes: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    hc.assert_can_manage_profile(user)
    p = _get_profile_or_404(db, target_user_id)

    forbidden_fields = (hc.SALARY_FIELDS | hc.CONTRACT_FIELDS) - {"phone"}
    if any(k in forbidden_fields for k in changes):
        raise AppException(
            "VALIDATION_ERROR",
            "Lương/hợp đồng phải sửa qua endpoint riêng (/contract, /salary-raises, "
            "/salary-cycle)",
            400,
        )

    changed_fields = []
    for field in ("job_title", "hired_date", "phone", "position"):
        if field in changes:
            value = changes[field]
            if field == "job_title" and (not value or not str(value).strip()):
                raise AppException("VALIDATION_ERROR", "job_title không được rỗng", 400)
            setattr(p, field, value.strip() if isinstance(value, str) else value)
            changed_fields.append(field)
    if not changed_fields:
        raise AppException("VALIDATION_ERROR", "Body rỗng", 400)
    p.updated_by = user.id
    p.updated_at = func.now()
    db.flush()
    audit_service.log_action(
        db,
        action="HR_PROFILE_UPDATE",
        resource="hr_profile",
        user_id=user.id,
        resource_id=target_user_id,
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
    target_user_id: uuid.UUID,
    contract_signed_date: date,
    contract_type: str,
    contract_end_date: Optional[date],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    hc.assert_can_edit_salary(user)  # HĐ = nhóm tài chính → admin/accountant
    p = _get_profile_or_404(db, target_user_id)
    if not contract_type:
        raise AppException("VALIDATION_ERROR", "Thiếu contract_type", 400)
    if db.get(ContractType, contract_type) is None:
        raise AppException(
            "INVALID_CONTRACT_TYPE", "Loại hợp đồng ngoài danh mục", 400
        )
    if contract_end_date and contract_end_date <= contract_signed_date:
        raise AppException(
            "INVALID_DATE_ORDER",
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
        resource_id=target_user_id,
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
    target_user_id: uuid.UUID,
    salary_cycle_years: int,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    hc.assert_can_edit_salary(user)
    p = _get_profile_or_404(db, target_user_id)
    if not isinstance(salary_cycle_years, int) or salary_cycle_years < 1:
        raise AppException("INVALID_CYCLE", "salary_cycle_years phải là số nguyên >= 1", 400)
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
        resource_id=target_user_id,
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
    target_user_id: uuid.UUID,
    salary_grade: str,
    salary_coefficient: str,
    base_salary_amount: str,
    raise_date: date,
    note: Optional[str],
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    hc.assert_can_edit_salary(user)  # leader/staff → SALARY_FORBIDDEN
    p = _get_profile_or_404(db, target_user_id)

    if not salary_grade or not salary_grade.strip():
        raise AppException("VALIDATION_ERROR", "Thiếu salary_grade", 400)
    coeff = hc.parse_decimal(salary_coefficient, field="salary_coefficient", positive=True)
    hc.assert_max_decimals(coeff, field="salary_coefficient", places=2)
    base = hc.parse_decimal(base_salary_amount, field="base_salary_amount", positive=True)
    hc.assert_max_decimals(base, field="base_salary_amount", places=2)
    coeff = hc.q_coeff(coeff)
    base = hc.q_money(base)

    if raise_date > date.today():
        raise AppException(
            "FUTURE_RAISE_NOT_ALLOWED", "Ngày nâng lương không được ở tương lai", 422
        )

    # Snapshot mức cũ → bản ghi lịch sử immutable
    sh = SalaryHistory(
        user_id=target_user_id,
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
        resource_id=target_user_id,
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
    target_user_id: uuid.UUID,
    page: int,
    limit: int,
) -> tuple[list[dict], int]:
    _get_profile_or_404(db, target_user_id)
    if not hc.can_read_salary(user, target_user_id):
        raise hc.salary_forbidden()

    total = db.execute(
        select(func.count())
        .select_from(SalaryHistory)
        .where(SalaryHistory.user_id == target_user_id)
    ).scalar_one()
    rows = db.execute(
        select(SalaryHistory)
        .where(SalaryHistory.user_id == target_user_id)
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
        "user_id": c.user_id,
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


def _assert_competence_read(user: CurrentUser, target_user_id: uuid.UUID) -> None:
    """Đọc năng lực: admin/leader (all); staff của mình. Accountant → 403 (không tài chính)."""
    if user.role == "accountant":
        raise hc.forbidden("Kế toán không quản lý hồ sơ năng lực")
    if user.role == "staff" and user.id != target_user_id:
        raise hc.forbidden("Bạn chỉ được xem năng lực của chính mình")


def list_competences(
    db: Session,
    *,
    user: CurrentUser,
    target_user_id: uuid.UUID,
    kind: Optional[str],
    status_filter: Optional[str],
) -> list[dict]:
    _get_profile_or_404(db, target_user_id)
    _assert_competence_read(user, target_user_id)
    conditions = [Competence.user_id == target_user_id]
    if kind:
        if kind not in ("degree", "certificate", "authorization"):
            raise AppException("VALIDATION_ERROR", "kind không hợp lệ", 400)
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
    target_user_id: uuid.UUID,
    payload: dict,
    correlation_id: Optional[str],
    ip: Optional[str],
) -> dict:
    hc.assert_can_manage_competence(user)
    _get_profile_or_404(db, target_user_id)
    c = _build_competence(db, target_user_id, payload, user)
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
        detail={"op": "create", "kind": c.kind, "target_user_id": str(target_user_id)},
    )
    db.commit()
    db.refresh(c)
    return _competence_dict(db, c)


def _build_competence(
    db: Session, target_user_id: uuid.UUID, payload: dict, user: CurrentUser
) -> Competence:
    kind = payload.get("kind")
    if kind not in ("degree", "certificate", "authorization"):
        raise AppException("VALIDATION_ERROR", "kind không hợp lệ", 400)
    title = payload.get("title")
    if not title or not str(title).strip():
        raise AppException("VALIDATION_ERROR", "Thiếu title", 400)
    issued = payload.get("issued_date")
    expiry = payload.get("expiry_date")
    if expiry and issued and expiry < issued:
        raise AppException("INVALID_DATE_ORDER", "expiry_date phải >= issued_date", 422)
    scope_detail = payload.get("scope_detail")
    authorized_by = payload.get("authorized_by")
    if kind == "authorization":
        if not scope_detail or not str(scope_detail).strip():
            raise AppException(
                "VALIDATION_ERROR", "Thiếu scope_detail (bắt buộc khi ủy quyền)", 400
            )
        if not authorized_by:
            raise AppException(
                "VALIDATION_ERROR", "Thiếu authorized_by (bắt buộc khi ủy quyền)", 400
            )
        hc.assert_user_exists(db, authorized_by)
    return Competence(
        user_id=target_user_id,
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
        raise AppException("COMPETENCE_NOT_FOUND", "Mục năng lực không tồn tại", 404)
    if not changes:
        raise AppException("VALIDATION_ERROR", "Body rỗng", 400)
    new_issued = changes.get("issued_date", c.issued_date)
    new_expiry = changes.get("expiry_date", c.expiry_date)
    if new_expiry and new_issued and new_expiry < new_issued:
        raise AppException("INVALID_DATE_ORDER", "expiry_date phải >= issued_date", 422)
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
                raise AppException("VALIDATION_ERROR", "kind không hợp lệ", 400)
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
        raise AppException("COMPETENCE_NOT_FOUND", "Mục năng lực không tồn tại", 404)
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
        detail={"op": "delete", "target_user_id": str(target)},
    )
    db.commit()


def get_competence_or_404(db: Session, competence_id: uuid.UUID) -> Competence:
    c = db.get(Competence, competence_id)
    if c is None:
        raise AppException("COMPETENCE_NOT_FOUND", "Mục năng lực không tồn tại", 404)
    return c
