"""Kiểm helper truy vấn dùng chung (M-09/T1.4).

Điểm quan trọng nhất là `get_active_or_404` THẬT SỰ loại bản ghi đã xoá mềm.
Đó chính là loại lỗi mà 13 bản sao chép tay có nguy cơ mắc: quên điều kiện
`deleted_at IS NULL` ở một bản, và bản đó trả về dữ liệu đã xoá mà không ai
nhận ra cho tới khi người dùng báo.
"""
import uuid

import pytest

from app.core.db_helpers import get_active_or_404, get_or_404
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.models.customer import Customer


def _make_customer(db, **kw) -> Customer:
    c = Customer(name=kw.pop("name", "Công ty Thử Nghiệm"), **kw)
    db.add(c)
    db.flush()
    return c


def test_get_or_404_returns_object(db):
    c = _make_customer(db)
    assert get_or_404(db, Customer, c.id, "không thấy") is c


def test_get_or_404_raises_with_generic_code(db):
    with pytest.raises(AppException) as e:
        get_or_404(db, Customer, uuid.uuid4(), "Không tìm thấy khách hàng")
    assert e.value.http_status == 404
    assert e.value.code == ErrorCode.NOT_FOUND
    assert e.value.message == "Không tìm thấy khách hàng"


def test_get_or_404_keeps_domain_specific_code(db):
    """4/13 service ném mã riêng theo domain thay vì NOT_FOUND chung.

    Đó là cách làm tốt hơn vì client phân biệt được, nên helper phải giữ được —
    ép tất cả về một mã sẽ là bước lùi.
    """
    with pytest.raises(AppException) as e:
        get_or_404(
            db, Customer, uuid.uuid4(), "Đề tài không tồn tại",
            code=ErrorCode.PROJECT_NOT_FOUND,
        )
    assert e.value.code == ErrorCode.PROJECT_NOT_FOUND


def test_get_active_or_404_excludes_soft_deleted(db):
    """Bản ghi đã xoá mềm phải coi như không tồn tại."""
    from datetime import datetime, timezone

    c = _make_customer(db, name="Khách đã xoá")
    # get_or_404 (không lọc) VẪN thấy — đúng theo thiết kế của nó
    assert get_or_404(db, Customer, c.id, "x") is c

    c.deleted_at = datetime.now(timezone.utc)
    db.flush()

    with pytest.raises(AppException) as e:
        get_active_or_404(db, Customer, c.id, "Không tìm thấy khách hàng")
    assert e.value.http_status == 404


def test_get_active_or_404_returns_live_row(db):
    c = _make_customer(db, name="Khách còn hoạt động")
    assert get_active_or_404(db, Customer, c.id, "x").id == c.id
