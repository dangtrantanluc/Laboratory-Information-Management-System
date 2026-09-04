"""Service CHỈ TIÊU KHÁCH ĐẶT trên phiếu nhận mẫu (m38).

VÌ SAO LÀ FILE RIÊNG
Hai lý do, và lý do thứ hai mới là lý do thật:
1. `sample_flow_service.py` đã ở 771/800 dòng (xem scripts/check-file-size.mjs).
2. Đây là ranh giới nghiệp vụ khác hẳn: dòng đặt hàng thuộc về quan hệ với KHÁCH
   (báo giá, tiền), còn phiếu chuyển thuộc về điều phối NỘI BỘ (giao việc cho lab).
   Gộp hai thứ này chung một bảng chính là lỗi mà m38 sinh ra để sửa — gộp chúng
   chung một service là lặp lại đúng lỗi đó ở tầng khác.

LUỒNG ĐÚNG SAU m38

    Tiếp nhận → thêm chỉ tiêu ĐẶT → báo giá → khách đồng ý → thanh toán → giao lab
                     (ở đây)                                                (dispatch)

Trước m38, "thêm chỉ tiêu" và "giao lab" là một thao tác, nên bốn bước giữa không
bao giờ chạy được.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException, not_found
from app.models.sample_flow import IntakeItem, SampleDispatch, SampleIntake, TestParameter
from app.services import audit_service

# Trạng thái phiếu KHÔNG còn nhận thay đổi đơn hàng.
_CLOSED = ("completed", "cancelled")

_WRITABLE = ("parameter_name", "method", "unit", "sample_name", "quantity", "note")


def _get_intake_or_404(db: Session, intake_id: uuid.UUID) -> SampleIntake:
    it = db.get(SampleIntake, intake_id)
    if it is None:
        raise not_found("Không tìm thấy phiếu nhận mẫu")
    return it


def _assert_open(it: SampleIntake) -> None:
    from app.models.sample_flow import INTAKE_STATUS_LABELS

    if it.status in _CLOSED:
        raise AppException(
            ErrorCode.INVALID_STATE,
            f"Phiếu {it.code} đã ở trạng thái "
            f"'{INTAKE_STATUS_LABELS.get(it.status, it.status)}' — không sửa được đơn hàng",
            409,
        )


def serialize(db: Session, i: IntakeItem) -> dict:
    """`dispatch_count` cho FE biết dòng nào đã giao lab — dòng đã giao thì không xoá."""
    n = db.execute(
        select(func.count()).select_from(SampleDispatch)
        .where(SampleDispatch.intake_item_id == i.id)
    ).scalar_one()
    return {
        "id": i.id,
        "intake_id": i.intake_id,
        "sort_order": i.sort_order,
        "test_parameter_id": i.test_parameter_id,
        "parameter_name": i.parameter_name,
        "method": i.method,
        "unit": i.unit,
        "sample_name": i.sample_name,
        "quantity": i.quantity,
        "unit_price": str(i.unit_price) if i.unit_price is not None else None,
        "note": i.note,
        "dispatch_count": int(n),
        "created_at": i.created_at,
    }


def list_items(db: Session, *, intake_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(IntakeItem).where(IntakeItem.intake_id == intake_id)
        .order_by(IntakeItem.sort_order, IntakeItem.created_at)
    ).scalars().all()
    return [serialize(db, i) for i in rows]


def _next_sort_order(db: Session, intake_id: uuid.UUID) -> int:
    cur = db.execute(
        select(func.max(IntakeItem.sort_order)).where(IntakeItem.intake_id == intake_id)
    ).scalar_one_or_none()
    return 0 if cur is None else int(cur) + 1


def build_item(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, fields: dict
) -> IntakeItem:
    """Dựng một dòng đặt hàng (CHƯA commit). Dùng chung cho tạo lẻ, tạo loạt và
    đường tương thích của add_dispatch.

    Chọn từ danh mục thì CHỤP tên/phương pháp/đơn vị/đơn giá vào dòng này — không
    giữ khoá ngoại làm nguồn hiển thị. Bảng giá sửa về sau không được làm đổi báo
    giá đã gửi khách, cùng nguyên tắc snapshot mà sample_intakes đang dùng.
    """
    tp_id = fields.get("test_parameter_id")
    name = (fields.get("parameter_name") or "").strip()
    method = fields.get("method")
    unit = fields.get("unit")
    price: Optional[Decimal] = None

    if tp_id is not None:
        tp = db.get(TestParameter, tp_id)
        if tp is None:
            raise AppException(ErrorCode.PARAM_NOT_FOUND, "Chỉ tiêu thử nghiệm không tồn tại", 404)
        if not tp.is_active:
            raise AppException(
                ErrorCode.PARAM_INACTIVE, f"Chỉ tiêu '{tp.name}' đã ngưng sử dụng", 400
            )
        name = name or tp.name
        method = method or tp.method
        unit = unit or tp.unit
        price = tp.unit_price
    if not name:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, "Nhập chỉ tiêu hoặc chọn từ danh mục chỉ tiêu", 400
        )

    qty = fields.get("quantity") or 1
    i = IntakeItem(
        intake_id=intake_id,
        sort_order=fields.get("sort_order", _next_sort_order(db, intake_id)),
        test_parameter_id=tp_id,
        parameter_name=name,
        method=method,
        unit=unit,
        sample_name=(fields.get("sample_name") or "").strip() or None,
        quantity=int(qty),
        unit_price=price,
        note=fields.get("note"),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(i)
    return i


def add_items(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, items: list[dict],
    correlation_id: Optional[str], ip: Optional[str],
) -> list[dict]:
    """Thêm chỉ tiêu khách đặt — KHÔNG giao việc cho phòng lab, KHÔNG đổi trạng thái phiếu.

    Đây là thao tác mà trước m38 không tồn tại, và vì nó không tồn tại nên không ai
    lập được báo giá trước khi chuyển mẫu.
    """
    if not items:
        raise AppException(ErrorCode.VALIDATION_ERROR, "Chưa có chỉ tiêu nào", 400)
    it = _get_intake_or_404(db, intake_id)
    _assert_open(it)

    created = [build_item(db, user=user, intake_id=intake_id, fields=raw) for raw in items]
    db.flush()
    audit_service.log_action(
        db, action="INTAKE_ITEM_ADD", resource="sample_intake", user_id=user.id,
        resource_id=intake_id, correlation_id=correlation_id, ip=ip,
        detail={"code": it.code, "count": len(created),
                "names": [i.parameter_name for i in created][:20]},
    )
    db.commit()
    for i in created:
        db.refresh(i)
    return [serialize(db, i) for i in created]


def update_item(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, item_id: uuid.UUID,
    changes: dict, correlation_id: Optional[str], ip: Optional[str],
) -> dict:
    it = _get_intake_or_404(db, intake_id)
    _assert_open(it)
    i = db.get(IntakeItem, item_id)
    if i is None or i.intake_id != intake_id:
        raise not_found("Không tìm thấy chỉ tiêu của phiếu này")

    for f in _WRITABLE:
        if f in changes and changes[f] is not None:
            setattr(i, f, changes[f])
    if changes.get("unit_price") is not None:
        # Cho phép thương lượng giá — nhưng luôn qua Decimal, không nhận float.
        i.unit_price = Decimal(str(changes["unit_price"]))
    i.updated_by = user.id
    i.updated_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db, action="INTAKE_ITEM_UPDATE", resource="sample_intake", user_id=user.id,
        resource_id=intake_id, correlation_id=correlation_id, ip=ip,
        detail={"item": str(item_id), "changes": {k: str(v) for k, v in changes.items()}},
    )
    db.commit()
    db.refresh(i)
    return serialize(db, i)


def delete_item(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID, item_id: uuid.UUID,
    correlation_id: Optional[str], ip: Optional[str],
) -> None:
    """Xoá dòng đặt hàng — chặn nếu đã giao việc cho phòng lab.

    Xoá dòng đã giao sẽ để lại phiếu chuyển mồ côi (FK là SET NULL), tức là phòng
    lab vẫn còn việc trong hàng đợi mà không truy được nó thuộc đơn hàng nào.
    """
    it = _get_intake_or_404(db, intake_id)
    _assert_open(it)
    i = db.get(IntakeItem, item_id)
    if i is None or i.intake_id != intake_id:
        raise not_found("Không tìm thấy chỉ tiêu của phiếu này")

    n = db.execute(
        select(func.count()).select_from(SampleDispatch)
        .where(SampleDispatch.intake_item_id == item_id)
    ).scalar_one()
    if n:
        raise AppException(
            ErrorCode.INVALID_STATE,
            f"Chỉ tiêu '{i.parameter_name}' đã chuyển cho phòng lab — huỷ lượt chuyển trước",
            409,
        )

    audit_service.log_action(
        db, action="INTAKE_ITEM_DELETE", resource="sample_intake", user_id=user.id,
        resource_id=intake_id, correlation_id=correlation_id, ip=ip,
        detail={"code": it.code, "parameter_name": i.parameter_name},
    )
    db.delete(i)
    db.commit()


def resolve_for_dispatch(
    db: Session, *, user: CurrentUser, intake_id: uuid.UUID,
    intake_item_id: Optional[uuid.UUID], fields: dict,
) -> IntakeItem:
    """Lấy dòng đặt hàng cho một lượt giao việc; chưa có thì tạo (CHƯA commit).

    Đường tương thích: `POST /intakes/{id}/dispatches` cũ không biết tới đơn hàng.
    Thay vì bắt toàn bộ giao diện đổi cùng lúc, giao việc mà chưa có dòng đặt hàng
    thì tự sinh dòng đó — nên báo giá LUÔN có nguồn dữ liệu, kể cả khi quầy vẫn thao
    tác theo thói quen cũ.
    """
    if intake_item_id is not None:
        i = db.get(IntakeItem, intake_item_id)
        if i is None or i.intake_id != intake_id:
            raise not_found("Không tìm thấy chỉ tiêu của phiếu này")
        return i
    return build_item(db, user=user, intake_id=intake_id, fields=fields)
