"""m37 (W6) — phiếu đã đóng không sinh thêm việc cho phòng lab, và xoá dòng nhầm.

HAI LỖ HỔNG ĐƯỢC CHẶN Ở ĐÂY

1. `add_dispatch` không hề kiểm trạng thái phiếu. Câu `if it.status in (...)` trong
   hàm đó chỉ dùng để NÂNG trạng thái lên 'dispatched', nên với phiếu đã hủy dòng
   chỉ tiêu vẫn được tạo VÀ phòng lab vẫn nhận thông báo "Mẫu mới được chuyển đến
   phòng". Phòng lab làm việc trên một phiếu đã hủy mà không ai biết.

2. Không có đường xoá dòng chỉ tiêu. Chuyển nhầm phòng hoặc nhầm chỉ tiêu thì dòng
   đó tồn tại vĩnh viễn, chỉ sửa được nội dung — và vẫn nằm trong hàng đợi của
   phòng lab nhận nhầm.
"""
from app.core.error_codes import ErrorCode
from app.models.notification import Notification
from app.tests.conftest import requires_db

_INTAKES = "/api/v1/intakes"
_DISPATCHES = "/api/v1/dispatches"


def _intake(client) -> dict:
    res = client.post(_INTAKES, json={"customer_name": "Cty Vòng Đời"})
    assert res.status_code == 201, res.text
    return res.json()["data"]


def _add_dispatch(client, intake_id: str, department) -> "object":
    return client.post(
        f"{_INTAKES}/{intake_id}/dispatches",
        json={"chi_tieu": "Độ ẩm", "target_department_id": str(department.id)},
    )


@requires_db
class TestKhongGiaoViecTrenPhieuDaDong:
    def test_phieu_da_huy_khong_them_duoc_chi_tieu(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _intake(client)
        assert client.post(
            f"{_INTAKES}/{it['id']}/status", json={"status": "cancelled"}
        ).status_code == 200

        res = _add_dispatch(client, it["id"], department)
        assert res.status_code == 409, res.text
        assert res.json()["error"]["code"] == ErrorCode.INVALID_STATE

    def test_phieu_da_huy_khong_ban_thong_bao_cho_lab(
        self, client, as_role, department, db
    ):
        """Bất biến quan trọng hơn mã lỗi: phòng lab KHÔNG được nhận việc ma."""
        as_role("reception", department_id=department.id)
        it = _intake(client)
        client.post(f"{_INTAKES}/{it['id']}/status", json={"status": "cancelled"})

        truoc = db.query(Notification).filter(
            Notification.type == "SAMPLE_DISPATCHED"
        ).count()
        _add_dispatch(client, it["id"], department)
        sau = db.query(Notification).filter(
            Notification.type == "SAMPLE_DISPATCHED"
        ).count()
        assert sau == truoc, "phiếu đã hủy vẫn bắn thông báo giao việc cho phòng lab"

    def test_phieu_da_tra_ket_qua_khong_them_duoc_chi_tieu(
        self, client, as_role, department
    ):
        as_role("reception", department_id=department.id)
        it = _intake(client)
        assert _add_dispatch(client, it["id"], department).status_code == 201
        # received → (dispatched khi thêm chỉ tiêu) → completed
        assert client.post(
            f"{_INTAKES}/{it['id']}/status", json={"status": "completed"}
        ).status_code == 200

        res = _add_dispatch(client, it["id"], department)
        assert res.status_code == 409, res.text

    def test_chuyen_loat_cung_bi_chan(self, client, as_role, department):
        """Đường batch dùng chung guard — dễ quên vì nó là hàm riêng."""
        as_role("reception", department_id=department.id)
        it = _intake(client)
        client.post(f"{_INTAKES}/{it['id']}/status", json={"status": "cancelled"})

        res = client.post(
            f"{_INTAKES}/{it['id']}/dispatches/batch",
            json={"items": [
                {"chi_tieu": "pH", "target_department_id": str(department.id)},
            ]},
        )
        assert res.status_code == 409, res.text

    def test_phieu_da_huy_khong_ghi_duoc_ket_qua(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _intake(client)
        did = _add_dispatch(client, it["id"], department).json()["data"]["id"]
        client.post(f"{_INTAKES}/{it['id']}/status", json={"status": "cancelled"})

        as_role("staff", department_id=department.id)
        res = client.patch(f"{_DISPATCHES}/{did}/result", json={"ket_qua": "7.2"})
        assert res.status_code == 409, res.text
        assert res.json()["error"]["code"] == ErrorCode.RESULT_LOCKED


@requires_db
class TestXoaDongChuyenNham:
    def test_xoa_duoc_khi_lab_chua_tiep_nhan(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _intake(client)
        did = _add_dispatch(client, it["id"], department).json()["data"]["id"]

        assert client.delete(f"{_DISPATCHES}/{did}").status_code == 204
        assert client.get(f"{_DISPATCHES}/{did}").status_code == 404

    def test_khong_xoa_duoc_sau_khi_lab_tiep_nhan(self, client, as_role, department):
        """Đã tiếp nhận là đã có công việc thật — xoá đi là mất vết việc của lab."""
        as_role("reception", department_id=department.id)
        it = _intake(client)
        did = _add_dispatch(client, it["id"], department).json()["data"]["id"]

        as_role("staff", department_id=department.id)
        assert client.patch(
            f"{_DISPATCHES}/{did}/result", json={"status": "received"}
        ).status_code == 200

        as_role("reception", department_id=department.id)
        res = client.delete(f"{_DISPATCHES}/{did}")
        assert res.status_code == 409, res.text
        assert res.json()["error"]["code"] == ErrorCode.INVALID_STATE

    def test_lab_khong_xoa_duoc(self, client, as_role, department):
        """Xoá là thao tác của Phòng nhận mẫu (intake:manage), không phải của lab."""
        as_role("reception", department_id=department.id)
        it = _intake(client)
        did = _add_dispatch(client, it["id"], department).json()["data"]["id"]

        as_role("staff", department_id=department.id)
        assert client.delete(f"{_DISPATCHES}/{did}").status_code == 403

    def test_xoa_co_ghi_audit(self, client, as_role, department, audit_rows):
        as_role("reception", department_id=department.id)
        it = _intake(client)
        did = _add_dispatch(client, it["id"], department).json()["data"]["id"]

        truoc = audit_rows()
        client.delete(f"{_DISPATCHES}/{did}")
        assert audit_rows() > truoc, "xoá dòng chỉ tiêu phải để lại vết"
