"""Người liên hệ theo VAI TRÒ trên phiếu nhận mẫu (m43).

BÀI TOÁN
Phiếu chỉ giữ được MỘT người, nên hệ thống không trả lời được hai câu hỏi mà quầy
gặp hằng ngày: *ai mang mẫu tới* và *kết quả giao cho ai* — khi đó là hai người khác
nhau. Chọn một người trong danh bạ còn GHI ĐÈ cả ba ô liên hệ của phiếu.

NGUYÊN TẮC GIỮ NGUYÊN TỪ m35
Ghi BẢN CHỤP, không giữ khoá ngoại tới danh bạ. Khách đổi người phụ trách tháng sau
không được làm đổi phiếu đã in tháng trước.

TỰ ĐIỀN TỪ SỔ KHÁCH
`suggest_from_customer()` đọc `customer_contacts.roles` để quầy không phải gõ lại.
Đó chỉ là GỢI Ý: quầy sửa đè thoải mái, và bản ghi vào phiếu là thứ quầy xác nhận,
không phải thứ sổ khách đang có.
"""
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException, not_found
from app.models.customer import CustomerContact
from app.models.sample_flow import (
    CONTACT_ROLE_LABELS, VALID_CONTACT_ROLES, IntakeContact, SampleIntake,
)
from app.services import audit_service

_CLOSED = ("completed", "cancelled", "rejected")


def _get_intake_or_404(db: Session, intake_id: uuid.UUID) -> SampleIntake:
    it = db.get(SampleIntake, intake_id)
    if it is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")
    return it


def _serialize(c: IntakeContact) -> dict:
    return {
        "id": c.id,
        "intake_id": c.intake_id,
        "role": c.role,
        "role_label": CONTACT_ROLE_LABELS.get(c.role, c.role),
        "full_name": c.full_name,
        "job_title": c.job_title,
        "phone": c.phone,
        "email": c.email,
        "note": c.note,
    }


def list_contacts(db: Session, *, intake_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(IntakeContact).where(IntakeContact.intake_id == intake_id)
        .order_by(IntakeContact.role)
    ).scalars().all()
    return [_serialize(c) for c in rows]


def suggest_from_customer(db: Session, *, customer_id: uuid.UUID) -> dict:
    """Gợi ý người cho từng vai từ sổ khách — chỉ người CÒN HIỆU LỰC.

    Không đề xuất người đã nghỉ việc: quầy điền tên họ lên phiếu mới thì kết quả sẽ
    gửi tới một người không còn ở đó.
    """
    rows = db.execute(
        select(CustomerContact).where(
            CustomerContact.customer_id == customer_id,
            CustomerContact.is_active.is_(True),
        ).order_by(CustomerContact.is_primary.desc(), CustomerContact.full_name)
    ).scalars().all()

    out: dict[str, dict] = {}
    for role in VALID_CONTACT_ROLES:
        match = next((c for c in rows if role in (c.roles or [])), None)
        # Chưa ai được phân vai thì lấy liên hệ mặc định — đa số khách chỉ có một
        # người, và bắt quầy phân vai cho từng khách trước khi dùng được là rào cản
        # không đáng có.
        if match is None and role == "technical":
            match = next((c for c in rows if c.is_primary), None)
        if match is not None:
            out[role] = {
                "full_name": match.full_name, "job_title": match.job_title,
                "phone": match.phone, "email": match.email,
            }
    return out


def set_contacts(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, contacts: list[dict],
    correlation_id: Optional[str], ip: Optional[str],
) -> list[dict]:
    """Đặt LẠI toàn bộ người liên hệ theo vai của phiếu (ghi đè cả bộ).

    Ghi đè cả bộ thay vì sửa từng dòng: màn hình quầy hiển thị cả bốn vai cùng lúc,
    nên gửi cả bộ khớp đúng thao tác người dùng vừa làm và tránh trạng thái nửa vời
    khi một vai lưu được còn vai khác thì không.
    """
    it = _get_intake_or_404(db, intake_id)
    if it.status in _CLOSED:
        raise AppException(
            ErrorCode.INVALID_STATE,
            f"Phiếu {it.code} đã đóng — không sửa được người liên hệ",
            409,
        )

    seen: set[str] = set()
    cleaned: list[dict] = []
    for raw in contacts:
        role = raw.get("role")
        if role not in VALID_CONTACT_ROLES:
            raise AppException(ErrorCode.VALIDATION_ERROR, f"Vai trò '{role}' không hợp lệ", 400)
        if role in seen:
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                f"Vai '{CONTACT_ROLE_LABELS[role]}' bị khai hai lần trong cùng một phiếu",
                400,
            )
        name = (raw.get("full_name") or "").strip()
        if not name:
            raise AppException(
                ErrorCode.VALIDATION_ERROR,
                f"Vai '{CONTACT_ROLE_LABELS[role]}': nhập họ tên người liên hệ",
                400,
            )
        seen.add(role)
        cleaned.append({**raw, "role": role, "full_name": name})

    db.query(IntakeContact).filter(IntakeContact.intake_id == intake_id).delete()
    db.flush()
    for raw in cleaned:
        db.add(IntakeContact(
            intake_id=intake_id,
            role=raw["role"],
            full_name=raw["full_name"],
            job_title=raw.get("job_title"),
            phone=raw.get("phone"),
            email=raw.get("email"),
            note=raw.get("note"),
            created_by=user.id,
        ))
    db.flush()

    audit_service.log_action(
        db, action="INTAKE_CONTACTS_SET", resource="sample_intake", user_id=user.id,
        resource_id=intake_id, correlation_id=correlation_id, ip=ip,
        detail={"code": it.code,
                "roles": {r["role"]: r["full_name"] for r in cleaned}},
    )
    db.commit()
    return list_contacts(db, intake_id=intake_id)
