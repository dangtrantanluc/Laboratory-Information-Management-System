"""Phiếu nhận mẫu chỉ có MỘT đường đổi trạng thái.

`POST /intakes/{id}/status` đi qua state machine INTAKE_NEXT và kiểm vai trò
`_privileged`. Nhưng `PATCH /intakes/{id}` từng nhận luôn `status` trong body rồi ghi
bằng `for k, v in changes.items(): setattr(it, k, v)` — một đường thứ hai bỏ qua cả
hai chốt, cho phép nhảy thẳng `received → completed`, bỏ qua báo giá và thanh toán,
và chỉ để lại vết audit mờ ("INTAKE_UPDATE" thay vì "INTAKE_STATUS_CHANGE").
"""
import pytest

from app.tests.conftest import requires_db

pytestmark = requires_db

_BASE = "/api/v1/intakes"


@pytest.fixture
def intake(client, as_role, db):
    """Tạo phiếu qua API thật để đi đúng đường sinh mã + audit."""
    as_role("reception")
    r = client.post(_BASE, json={"customer_name": "Khách thử nghiệm"})
    assert r.status_code == 201, r.text
    return r.json()["data"]


class TestKhongDoiTrangThaiQuaPatch:
    def test_patch_kem_status_bi_tu_choi(self, client, as_role, intake):
        as_role("reception")

        r = client.patch(f"{_BASE}/{intake['id']}", json={"status": "completed"})

        assert r.status_code == 400, (
            f"PATCH không được nhận 'status' (extra=forbid) — nhận {r.status_code}"
        )

    def test_trang_thai_khong_bi_thay_doi(self, client, as_role, intake):
        """Khẳng định mạnh hơn mã lỗi: dữ liệu phải nguyên vẹn sau khi bị từ chối."""
        as_role("reception")
        client.patch(f"{_BASE}/{intake['id']}", json={"status": "completed"})

        sau = client.get(f"{_BASE}/{intake['id']}").json()["data"]
        assert sau["status"] == "received"

    def test_patch_field_thuong_van_chay(self, client, as_role, intake):
        """Đối trọng: bản vá không được chặn nhầm việc sửa thông tin bình thường."""
        as_role("reception")

        r = client.patch(f"{_BASE}/{intake['id']}", json={"note": "ghi chú mới"})

        assert r.status_code == 200, r.text
        assert r.json()["data"]["note"] == "ghi chú mới"

    def test_doi_trang_thai_qua_dung_endpoint_van_chay(self, client, as_role, intake):
        """Đường hợp lệ phải còn nguyên tác dụng."""
        as_role("reception")

        r = client.post(f"{_BASE}/{intake['id']}/status", json={"status": "quoted"})

        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "quoted"

    def test_nhay_bac_van_bi_state_machine_chan(self, client, as_role, intake):
        """Xác nhận state machine — thứ mà PATCH từng bỏ qua — thật sự có tác dụng."""
        as_role("reception")

        r = client.post(f"{_BASE}/{intake['id']}/status", json={"status": "completed"})

        # 409 INVALID_TRANSITION (không phải 422): đây là xung đột trạng thái hiện tại,
        # không phải dữ liệu gửi lên sai định dạng.
        assert r.status_code == 409, (
            f"received → completed là nhảy bậc, phải bị chặn — nhận {r.status_code}"
        )
        assert r.json()["error"]["code"] == "INVALID_TRANSITION"
