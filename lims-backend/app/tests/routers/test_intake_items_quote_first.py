"""m38 — báo giá lập được TRƯỚC khi giao mẫu cho phòng lab.

BẤT BIẾN CHÍNH CỦA CẢ MIGRATION
m28 thiết kế luồng `tiếp nhận → báo giá → khách đồng ý → thanh toán → chuyển lab`,
nhưng `create_from_intake()` lại đọc `sample_dispatches`, nên muốn báo giá thì phải
giao việc cho lab trước — và giao việc đẩy phiếu thẳng sang 'dispatched'. Ba trạng
thái ở giữa là mã chết: giao diện vẽ 6 bước, thực tế đi được 2.

`test_lap_bao_gia_khi_chua_giao_lab` và `test_di_tron_sau_buoc_cua_m28` là hai test
mô tả đúng thứ trước m38 KHÔNG làm được. Nếu ai đó trỏ create_from_intake về lại
sample_dispatches, hai test này đỏ ngay.
"""
from app.core.error_codes import ErrorCode
from app.models.notification import Notification
from app.tests.conftest import requires_db

_INTAKES = "/api/v1/intakes"
_QUOTATIONS = "/api/v1/quotations"


def _intake(client) -> dict:
    res = client.post(_INTAKES, json={"customer_name": "Cty CP Nông Sản An Bình"})
    assert res.status_code == 201, res.text
    return res.json()["data"]


def _add_items(client, intake_id: str, items: list[dict]):
    return client.post(f"{_INTAKES}/{intake_id}/items", json={"items": items})


@requires_db
class TestDonHangTachKhoiGiaoViec:
    def test_them_chi_tieu_khong_giao_lab_va_khong_doi_trang_thai(
        self, client, as_role, department, db
    ):
        as_role("reception", department_id=department.id)
        it = _intake(client)

        truoc = db.query(Notification).filter(
            Notification.type == "SAMPLE_DISPATCHED"
        ).count()
        res = _add_items(client, it["id"], [
            {"parameter_name": "Độ ẩm", "quantity": 2},
            {"parameter_name": "Hàm lượng đạm tổng số"},
        ])
        assert res.status_code == 201, res.text
        assert len(res.json()["data"]) == 2

        # Phiếu VẪN ở 'received' — thêm đơn hàng không phải là giao việc.
        assert client.get(f"{_INTAKES}/{it['id']}").json()["data"]["status"] == "received"
        sau = db.query(Notification).filter(
            Notification.type == "SAMPLE_DISPATCHED"
        ).count()
        assert sau == truoc, "thêm chỉ tiêu đặt không được bắn thông báo cho phòng lab"

    def test_lap_bao_gia_khi_chua_giao_lab(self, client, as_role, department):
        """Điều mà trước m38 không làm được."""
        as_role("reception", department_id=department.id)
        it = _intake(client)
        _add_items(client, it["id"], [{"parameter_name": "Độ ẩm", "quantity": 3}])

        res = client.post(f"{_QUOTATIONS}/from-intake/{it['id']}")
        assert res.status_code == 201, res.text
        q = res.json()["data"]
        assert q["item_count"] == 1
        assert q["items"][0]["parameter_name"] == "Độ ẩm"
        assert q["items"][0]["quantity"] == 3
        # Vẫn chưa giao cho phòng lab nào.
        assert client.get(f"{_INTAKES}/{it['id']}").json()["data"]["status"] == "received"

    def test_phieu_chua_co_chi_tieu_thi_bao_loi_ro_rang(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _intake(client)

        res = client.post(f"{_QUOTATIONS}/from-intake/{it['id']}")
        assert res.status_code == 400, res.text
        assert res.json()["error"]["code"] == ErrorCode.NO_ITEMS

    def test_di_tron_sau_buoc_cua_m28(self, client, as_role, department):
        """tiếp nhận → báo giá → khách đồng ý → thanh toán → chuyển lab → trả KQ."""
        as_role("reception", department_id=department.id)
        it = _intake(client)
        _add_items(client, it["id"], [{"parameter_name": "pH"}])
        q = client.post(f"{_QUOTATIONS}/from-intake/{it['id']}").json()["data"]

        # Gửi báo giá → phiếu tự sang 'quoted'
        assert client.post(f"{_QUOTATIONS}/{q['id']}/status", json={"status": "sent"}).status_code == 200
        assert client.get(f"{_INTAKES}/{it['id']}").json()["data"]["status"] == "quoted"

        # Khách đồng ý → 'quote_accepted'
        assert client.post(
            f"{_QUOTATIONS}/{q['id']}/status", json={"status": "accepted"}
        ).status_code == 200
        assert client.get(f"{_INTAKES}/{it['id']}").json()["data"]["status"] == "quote_accepted"

        # Thanh toán → chuyển lab → trả kết quả
        for nxt in ("paid", "dispatched", "completed"):
            res = client.post(f"{_INTAKES}/{it['id']}/status", json={"status": nxt})
            assert res.status_code == 200, f"{nxt}: {res.text}"
        assert client.get(f"{_INTAKES}/{it['id']}").json()["data"]["status"] == "completed"

    def test_gia_chup_tu_danh_muc_khong_doi_khi_bang_gia_doi(
        self, client, as_role, department, db
    ):
        """Snapshot giá: sửa bảng giá sau đó không được làm lệch đơn hàng đã chốt."""
        from app.models.sample_flow import TestParameter

        as_role("reception", department_id=department.id)
        tp = TestParameter(
            matrix="water", name="Asen (As)", unit="mg/L", unit_price=350000,
            department_id=department.id,
        )
        db.add(tp)
        db.flush()

        it = _intake(client)
        res = _add_items(client, it["id"], [{"test_parameter_id": str(tp.id)}])
        assert res.status_code == 201, res.text
        assert res.json()["data"][0]["unit_price"] == "350000.00"

        tp.unit_price = 900000
        db.flush()

        items = client.get(f"{_INTAKES}/{it['id']}/items").json()["data"]
        assert items[0]["unit_price"] == "350000.00", "đơn hàng đã chốt bị bảng giá mới ghi đè"


@requires_db
class TestGiaoViecVanNoiVeDonHang:
    def test_duong_cu_tu_sinh_dong_dat_hang(self, client, as_role, department):
        """Tương thích ngược: giao việc trực tiếp vẫn sinh đơn hàng để báo giá có nguồn.

        Quan trọng vì giao diện quầy hiện vẫn thao tác theo đường cũ — nếu đường này
        không sinh đơn hàng thì báo giá của các phiếu đó lại rỗng.
        """
        as_role("reception", department_id=department.id)
        it = _intake(client)
        res = client.post(
            f"{_INTAKES}/{it['id']}/dispatches",
            json={"chi_tieu": "Chì (Pb)", "target_department_id": str(department.id)},
        )
        assert res.status_code == 201, res.text

        items = client.get(f"{_INTAKES}/{it['id']}/items").json()["data"]
        assert len(items) == 1
        assert items[0]["parameter_name"] == "Chì (Pb)"
        assert items[0]["dispatch_count"] == 1

    def test_mot_chi_tieu_giao_cho_hai_phong(self, client, as_role, department, db):
        """Quan hệ 1–n mà mô hình cũ không diễn tả được."""
        import uuid as _uuid

        from app.models.department import Department

        as_role("reception", department_id=department.id)
        it = _intake(client)
        item = _add_items(client, it["id"], [{"parameter_name": "Vi sinh tổng số"}]).json()["data"][0]

        phong_b = Department(name="Phòng Vi sinh", code=_uuid.uuid4().hex[:8])
        db.add(phong_b)
        db.flush()

        for dept_id in (department.id, phong_b.id):
            res = client.post(
                f"{_INTAKES}/{it['id']}/dispatches",
                json={"intake_item_id": item["id"], "target_department_id": str(dept_id)},
            )
            assert res.status_code == 201, res.text

        items = client.get(f"{_INTAKES}/{it['id']}/items").json()["data"]
        assert len(items) == 1, "giao cho 2 phòng không được nhân đôi dòng đặt hàng"
        assert items[0]["dispatch_count"] == 2

    def test_khong_xoa_duoc_dong_da_giao_lab(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _intake(client)
        item = _add_items(client, it["id"], [{"parameter_name": "Độ ẩm"}]).json()["data"][0]
        client.post(
            f"{_INTAKES}/{it['id']}/dispatches",
            json={"intake_item_id": item["id"], "target_department_id": str(department.id)},
        )

        res = client.delete(f"{_INTAKES}/{it['id']}/items/{item['id']}")
        assert res.status_code == 409, res.text
        assert res.json()["error"]["code"] == ErrorCode.INVALID_STATE

    def test_xoa_duoc_dong_chua_giao(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _intake(client)
        item = _add_items(client, it["id"], [{"parameter_name": "Độ ẩm"}]).json()["data"][0]

        assert client.delete(f"{_INTAKES}/{it['id']}/items/{item['id']}").status_code == 204
        assert client.get(f"{_INTAKES}/{it['id']}/items").json()["data"] == []

    def test_lab_khong_sua_duoc_don_hang(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _intake(client)

        as_role("staff", department_id=department.id)
        res = _add_items(client, it["id"], [{"parameter_name": "Độ ẩm"}])
        assert res.status_code == 403, res.text
