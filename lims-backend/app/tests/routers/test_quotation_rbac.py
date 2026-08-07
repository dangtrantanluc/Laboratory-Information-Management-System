"""Quyền đọc báo giá — chống lộ PII khách hàng + bảng giá.

Ba endpoint đọc của /quotations từng chỉ có `Depends(get_current_user)`, và
`quotation_service.get_quotation()` thậm chí không nhận tham số `user`. Nghĩa là mọi
tài khoản — kể cả KTV phòng lab không liên quan gì tới bán hàng — liệt kê và xuất
Excel được toàn bộ báo giá kèm tên/địa chỉ/email/điện thoại khách và đơn giá.

Danh sách vai trò dưới đây khớp `lims-frontend/src/components/layout/nav.ts` (menu
"Báo giá") — tức là bản vá enforce đúng thứ giao diện vốn đã giả định, không phải một
quy tắc mới do backend tự đặt.
"""
import pytest

from app.tests.conftest import requires_db

pytestmark = requires_db

_BASE = "/api/v1/quotations"

VAI_TRO_DUOC_DOC = ["admin", "leader", "reception", "office"]
VAI_TRO_BI_CHAN = ["staff", "qms", "lab_manager"]


@pytest.mark.parametrize("role", VAI_TRO_DUOC_DOC)
def test_vai_tro_kinh_doanh_doc_duoc(client, as_role, role):
    as_role(role)
    assert client.get(_BASE).status_code == 200


@pytest.mark.parametrize("role", VAI_TRO_BI_CHAN)
def test_vai_tro_khac_bi_chan(client, as_role, role):
    """Đây là lỗ hổng thật: `staff` đọc được PII khách + giá của mọi báo giá."""
    as_role(role)
    assert client.get(_BASE).status_code == 403


@pytest.mark.parametrize("role", VAI_TRO_BI_CHAN)
def test_vai_tro_khac_khong_xuat_duoc_excel(client, as_role, role):
    """Đường xuất Excel nguy hiểm hơn list: nó trả trọn bộ dữ liệu trong một tệp."""
    import uuid

    as_role(role)
    r = client.get(f"{_BASE}/{uuid.uuid4()}/export.xlsx")
    assert r.status_code == 403, (
        f"phải chặn ở tầng quyền TRƯỚC khi tra id — nhận {r.status_code}"
    )
