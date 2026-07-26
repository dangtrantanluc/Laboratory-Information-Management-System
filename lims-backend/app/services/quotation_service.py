"""Service BÁO GIÁ (m29).

Quyền: Phòng nhận mẫu + Quản trị + Ban lãnh đạo (theo chốt nghiệp vụ).
Tiền LUÔN tính ở server bằng Decimal: amount = qty × unit_price; VAT theo vat_rate (mặc định 8%).
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException, not_found
from app.models.quotation import (
    QUOTATION_NEXT, QUOTATION_STATUS_LABELS, Quotation, QuotationItem,
)
from app.models.sample_flow import SampleDispatch, SampleIntake, TestParameter
from app.models.user import User
from app.services import audit_service

MANAGE_ROLES = ("reception", "admin", "leader")
CENT = Decimal("0.01")


def _forbidden(msg: str = "Chỉ Phòng nhận mẫu / Quản trị / Ban lãnh đạo được lập báo giá") -> AppException:
    return AppException(ErrorCode.FORBIDDEN, msg, 403)


def can_manage(user: CurrentUser) -> bool:
    return user.role in MANAGE_ROLES


def _assert_manage(user: CurrentUser) -> None:
    if not can_manage(user):
        raise _forbidden()


def _dec(v, field: str = "số tiền") -> Decimal:
    if v is None or v == "":
        return Decimal("0")
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        raise AppException(ErrorCode.VALIDATION_ERROR, f"{field} không hợp lệ", 400)
    if d < 0:
        raise AppException(ErrorCode.VALIDATION_ERROR, f"{field} không được âm", 400)
    return d


def _next_code(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"BG-{year}-"
    last = db.execute(
        select(Quotation.code).where(Quotation.code.like(f"{prefix}%"))
        .order_by(Quotation.code.desc()).limit(1)
    ).scalar_one_or_none()
    seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def _recalc(db: Session, q: Quotation) -> None:
    """Tính lại Cộng / VAT / Tổng cộng từ các dòng (nguồn sự thật duy nhất)."""
    items = db.execute(
        select(QuotationItem).where(QuotationItem.quotation_id == q.id)
    ).scalars().all()
    subtotal = Decimal("0")
    for it in items:
        it.amount = (Decimal(it.unit_price) * Decimal(it.quantity)).quantize(CENT)
        subtotal += it.amount
    q.subtotal = subtotal.quantize(CENT)
    q.vat_amount = (subtotal * Decimal(q.vat_rate) / Decimal(100)).quantize(CENT)
    q.total = (q.subtotal + q.vat_amount).quantize(CENT)


def _serialize_item(it: QuotationItem) -> dict:
    return {
        "id": it.id,
        "sort_order": it.sort_order,
        "sample_name": it.sample_name,
        "test_parameter_id": it.test_parameter_id,
        "parameter_name": it.parameter_name,
        "method": it.method,
        "unit": it.unit,
        "quantity": it.quantity,
        "unit_price": str(it.unit_price),
        "amount": str(it.amount),
        "note": it.note,
    }


def _serialize(db: Session, q: Quotation, with_items: bool = True) -> dict:
    intake = db.get(SampleIntake, q.intake_id) if q.intake_id else None
    creator = db.get(User, q.created_by) if q.created_by else None
    data = {
        "id": q.id,
        "code": q.code,
        "intake_id": q.intake_id,
        "intake_code": intake.code if intake else None,
        "customer_name": q.customer_name,
        "customer_address": q.customer_address,
        "customer_email": q.customer_email,
        "customer_phone": q.customer_phone,
        "issue_date": q.issue_date,
        "valid_until": q.valid_until,
        "vat_rate": str(q.vat_rate),
        "subtotal": str(q.subtotal),
        "vat_amount": str(q.vat_amount),
        "total": str(q.total),
        "status": q.status,
        "status_label": QUOTATION_STATUS_LABELS.get(q.status, q.status),
        "next_statuses": list(QUOTATION_NEXT.get(q.status, ())),
        "note": q.note,
        "created_by_name": creator.full_name if creator else None,
        "created_at": q.created_at,
        "updated_at": q.updated_at,
    }
    if with_items:
        rows = db.execute(
            select(QuotationItem).where(QuotationItem.quotation_id == q.id)
            .order_by(QuotationItem.sort_order)
        ).scalars().all()
        data["items"] = [_serialize_item(r) for r in rows]
        data["item_count"] = len(rows)
    return data


def list_quotations(
    db: Session, *, user: CurrentUser, q: Optional[str], status: Optional[str],
    intake_id: Optional[uuid.UUID], page: int, limit: int,
) -> tuple[list[dict], int]:
    conds = []
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(Quotation.code.ilike(like), Quotation.customer_name.ilike(like)))
    if status:
        conds.append(Quotation.status == status)
    if intake_id:
        conds.append(Quotation.intake_id == intake_id)

    base, cq = select(Quotation), select(func.count()).select_from(Quotation)
    for c in conds:
        base, cq = base.where(c), cq.where(c)
    total = db.execute(cq).scalar_one()
    rows = db.execute(
        base.order_by(Quotation.created_at.desc()).offset((page - 1) * limit).limit(limit)
    ).scalars().all()
    return [_serialize(db, r, with_items=False) for r in rows], total


def get_quotation(db: Session, *, quotation_id: uuid.UUID) -> dict:
    q = db.get(Quotation, quotation_id)
    if q is None:
        raise not_found("Không tìm thấy báo giá")
    return _serialize(db, q)


def _apply_items(db: Session, q: Quotation, items: list[dict]) -> None:
    """Ghi đè toàn bộ dòng chi tiết; lấy tên/phương pháp/đơn giá từ danh mục nếu có."""
    db.query(QuotationItem).filter(QuotationItem.quotation_id == q.id).delete()
    for i, raw in enumerate(items):
        tp = db.get(TestParameter, raw["test_parameter_id"]) if raw.get("test_parameter_id") else None
        name = (raw.get("parameter_name") or (tp.name if tp else "")).strip()
        if not name:
            raise AppException(ErrorCode.VALIDATION_ERROR, f"Dòng {i + 1}: thiếu tên chỉ tiêu", 400)
        # Đơn giá: ưu tiên giá nhập tay (cho phép thương lượng), không có thì lấy bảng giá
        price = raw.get("unit_price")
        unit_price = _dec(price, "Đơn giá") if price not in (None, "") else Decimal(tp.unit_price or 0) if tp else Decimal("0")
        db.add(QuotationItem(
            quotation_id=q.id,
            sort_order=raw.get("sort_order", i),
            sample_name=(raw.get("sample_name") or "").strip() or None,
            test_parameter_id=raw.get("test_parameter_id"),
            parameter_name=name,
            method=(raw.get("method") or (tp.method if tp else None)),
            unit=(raw.get("unit") or (tp.unit if tp else None)),
            quantity=int(raw.get("quantity") or 1),
            unit_price=unit_price,
            note=(raw.get("note") or "").strip() or None,
        ))
    db.flush()


def create_quotation(
    db: Session, *, user: CurrentUser, fields: dict, correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    _assert_manage(user)
    name = (fields.get("customer_name") or "").strip()
    if not name:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Nhập tên khách hàng", 400)

    today = date.today()
    q = Quotation(
        code=_next_code(db),
        intake_id=fields.get("intake_id"),
        customer_name=name,
        customer_address=fields.get("customer_address"),
        customer_email=fields.get("customer_email"),
        customer_phone=fields.get("customer_phone"),
        issue_date=fields.get("issue_date") or today,
        # Mẫu báo giá: "có giá trị trong vòng 1 tháng"
        valid_until=fields.get("valid_until") or (today + timedelta(days=30)),
        vat_rate=_dec(fields.get("vat_rate", 8), "VAT"),
        note=fields.get("note"),
        status="draft",
        created_by=user.id,
    )
    db.add(q)
    db.flush()
    _apply_items(db, q, fields.get("items") or [])
    _recalc(db, q)
    audit_service.log_action(
        db, action="QUOTATION_CREATE", resource="quotation", user_id=user.id, resource_id=q.id,
        correlation_id=correlation_id, ip=ip, detail={"code": q.code, "total": str(q.total)},
    )
    db.commit()
    db.refresh(q)
    return _serialize(db, q)


def create_from_intake(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """Tạo báo giá TỰ ĐỘNG từ các chỉ tiêu đã chọn của phiếu nhận mẫu."""
    _assert_manage(user)
    it = db.get(SampleIntake, intake_id)
    if it is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")

    dispatches = db.execute(
        select(SampleDispatch).where(SampleDispatch.intake_id == intake_id)
        .order_by(SampleDispatch.dispatched_at)
    ).scalars().all()
    if not dispatches:
        raise AppException(
            ErrorCode.NO_ITEMS,
            "Phiếu chưa có chỉ tiêu nào — hãy phân chỉ tiêu trước khi lập báo giá",
            400,
        )
    items = [
        {
            "sort_order": i,
            "sample_name": d.sample_name or it.description,
            "test_parameter_id": d.test_parameter_id,
            "parameter_name": d.chi_tieu,
            "method": d.phuong_phap,
            "unit": d.don_vi,
            "quantity": d.quantity or 1,
            "unit_price": str(d.unit_price) if d.unit_price is not None else None,
        }
        for i, d in enumerate(dispatches)
    ]
    return create_quotation(
        db, user=user,
        fields={
            "intake_id": intake_id,
            "customer_name": it.customer_name,
            "customer_address": it.address,
            "customer_email": it.email,
            "customer_phone": it.phone,
            "items": items,
        },
        correlation_id=correlation_id, ip=ip,
    )


def update_quotation(
    db: Session, *, user: CurrentUser, quotation_id: uuid.UUID, changes: dict,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    _assert_manage(user)
    q = db.get(Quotation, quotation_id)
    if q is None:
        raise not_found("Không tìm thấy báo giá")
    if q.status == "accepted":
        raise AppException(ErrorCode.LOCKED, "Báo giá đã được khách đồng ý — không sửa được", 409)

    for f in ("customer_name", "customer_address", "customer_email", "customer_phone",
              "issue_date", "valid_until", "note", "intake_id"):
        if f in changes:
            setattr(q, f, changes[f])
    if "vat_rate" in changes and changes["vat_rate"] is not None:
        q.vat_rate = _dec(changes["vat_rate"], "VAT")
    if "items" in changes and changes["items"] is not None:
        _apply_items(db, q, changes["items"])
    q.updated_by = user.id
    q.updated_at = datetime.now(timezone.utc)
    _recalc(db, q)

    audit_service.log_action(
        db, action="QUOTATION_UPDATE", resource="quotation", user_id=user.id, resource_id=q.id,
        correlation_id=correlation_id, ip=ip, detail={"code": q.code, "total": str(q.total)},
    )
    db.commit()
    db.refresh(q)
    return _serialize(db, q)


def change_status(
    db: Session, *, user: CurrentUser, quotation_id: uuid.UUID, new_status: str,
    correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    """draft → sent → accepted/rejected/expired (state machine)."""
    _assert_manage(user)
    q = db.get(Quotation, quotation_id)
    if q is None:
        raise not_found("Không tìm thấy báo giá")
    allowed = QUOTATION_NEXT.get(q.status, ())
    if new_status not in allowed:
        raise AppException(
            ErrorCode.INVALID_TRANSITION,
            f"Không thể chuyển báo giá từ '{QUOTATION_STATUS_LABELS.get(q.status)}' sang "
            f"'{QUOTATION_STATUS_LABELS.get(new_status)}'",
            409,
        )
    q.status = new_status
    now = datetime.now(timezone.utc)
    if new_status == "sent":
        q.sent_at = now
    if new_status in ("accepted", "rejected"):
        q.decided_at = now
    q.updated_by = user.id
    q.updated_at = now

    # Đồng bộ trạng thái phiếu nhận mẫu: gửi báo giá → 'quoted'; khách đồng ý → 'quote_accepted'
    if q.intake_id:
        it = db.get(SampleIntake, q.intake_id)
        if it is not None:
            if new_status == "sent" and it.status == "received":
                it.status = "quoted"
            elif new_status == "accepted" and it.status in ("received", "quoted"):
                it.status = "quote_accepted"

    audit_service.log_action(
        db, action="QUOTATION_STATUS", resource="quotation", user_id=user.id, resource_id=q.id,
        correlation_id=correlation_id, ip=ip, detail={"code": q.code, "to": new_status},
    )
    db.commit()
    db.refresh(q)
    return _serialize(db, q)


def delete_quotation(
    db: Session, *, user: CurrentUser, quotation_id: uuid.UUID,
    correlation_id: Optional[str], ip: Optional[str],
) -> None:
    _assert_manage(user)
    q = db.get(Quotation, quotation_id)
    if q is None:
        raise not_found("Không tìm thấy báo giá")
    if q.status == "accepted":
        raise AppException(ErrorCode.LOCKED, "Báo giá đã được khách đồng ý — không xóa được", 409)
    code = q.code
    db.delete(q)  # items CASCADE
    audit_service.log_action(
        db, action="QUOTATION_DELETE", resource="quotation", user_id=user.id,
        resource_id=quotation_id, correlation_id=correlation_id, ip=ip, detail={"code": code},
    )
    db.commit()
