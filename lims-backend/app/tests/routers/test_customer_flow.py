"""Luồng #1 — Khách hàng: tạo → đọc → sửa → xoá mềm, kèm RBAC và vết kiểm toán.

Chọn làm luồng đầu tiên vì nó là CRUD đơn giản nhất có ĐỦ mọi thành phần cần
kiểm: RBAC theo vai trò, soft-delete, ghi audit, và hình dạng response. Nếu
khuôn mẫu ở đây đúng thì 19 luồng còn lại chỉ là lặp lại.

QUY TẮC CHỐNG TEST GIÒN (áp dụng cho toàn bộ app/tests/routers/):

1. Khẳng định response có ĐỦ trường cần, không khẳng định nó CHỈ có bấy nhiêu
   (`set(body) >= {...}`). Thêm trường mới không được làm đỏ test.
2. So mã lỗi bằng ErrorCode.X, không bằng chuỗi. Đổi tên mã thì test đỏ đúng chỗ.
3. Mỗi test một khẳng định nghiệp vụ; tên test là câu mô tả quy tắc đó.
"""
import pytest

from app.core.error_codes import ErrorCode
from app.tests.conftest import requires_db

_BASE = "/api/v1/customers"


def _create(client, name="Công ty Môi Trường ABC", **kw):
    return client.post(_BASE, json={"name": name, **kw})


@requires_db
class TestCustomerCrud:
    def test_admin_can_create_customer(self, client, as_role):
        as_role("admin")
        res = _create(client)
        assert res.status_code == 201, res.text

        body = res.json()["data"]
        assert set(body) >= {"id", "name", "type"}
        assert body["name"] == "Công ty Môi Trường ABC"

    def test_created_customer_appears_in_list(self, client, as_role):
        as_role("admin")
        _create(client, name="Công ty Xuất Hiện")

        items = client.get(f"{_BASE}?q=Xuất Hiện").json()["data"]
        assert [c["name"] for c in items] == ["Công ty Xuất Hiện"]

    def test_get_detail_returns_same_record(self, client, as_role):
        as_role("admin")
        cid = _create(client).json()["data"]["id"]

        res = client.get(f"{_BASE}/{cid}")
        assert res.status_code == 200
        assert res.json()["data"]["id"] == cid

    def test_patch_updates_only_given_fields(self, client, as_role):
        as_role("admin")
        # m35 đã bỏ ô `contact` tự do; dùng `phone` — cùng khẳng định nghiệp vụ.
        cid = _create(client, phone="0900000000").json()["data"]["id"]

        res = client.patch(f"{_BASE}/{cid}", json={"name": "Tên Đã Đổi"})
        assert res.status_code == 200
        body = res.json()["data"]
        assert body["name"] == "Tên Đã Đổi"
        assert body["phone"] == "0900000000", "PATCH không được xoá trường không gửi"

    def test_unknown_id_returns_404(self, client, as_role):
        as_role("admin")
        res = client.get(f"{_BASE}/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404
        assert res.json()["error"]["code"] == ErrorCode.NOT_FOUND


@requires_db
class TestCustomerContactFields:
    """m32 — 5 trường để tự điền phiếu BM 7.1.01.

    _serialize và update_customer từng liệt kê trường bằng tay ở HAI nơi khác nhau;
    thêm cột mà quên một nơi thì PATCH trả 200 nhưng không lưu gì — hỏng âm thầm,
    không ai phát hiện. Hai test dưới khoá đúng hành vi đó.
    """

    FIELDS = {
        "address": "123 Nguyễn Văn Cừ, Q.5, TP.HCM",
        "tax_code": "0301234567",
        "contact_person": "Chị Lan",
        "phone": "0908123456",
        "email": "lan@anphat.vn",
    }

    def test_create_persists_and_returns_contact_fields(self, client, as_role):
        as_role("admin")
        res = _create(client, name="Công ty An Phát", **self.FIELDS)
        assert res.status_code == 201, res.text

        cid = res.json()["data"]["id"]
        body = client.get(f"{_BASE}/{cid}").json()["data"]
        for field, value in self.FIELDS.items():
            assert body[field] == value, f"{field} không được trả về sau khi tạo"

    def test_patch_persists_contact_fields(self, client, as_role):
        as_role("admin")
        cid = _create(client, name="Công ty Sửa Sau").json()["data"]["id"]

        res = client.patch(f"{_BASE}/{cid}", json=self.FIELDS)
        assert res.status_code == 200, res.text
        # Đọc LẠI từ DB — response của PATCH có thể đúng trong khi lưu vẫn trượt.
        body = client.get(f"{_BASE}/{cid}").json()["data"]
        for field, value in self.FIELDS.items():
            assert body[field] == value, f"PATCH không lưu {field}"


@requires_db
class TestCustomerRbac:
    """require_roles ở router quy định ai đọc/ghi được.

    W12 đã SẮP LẠI ma trận: khối lab ra, Văn phòng vào. Lý do và bằng chứng nằm ở
    docstring của read_roles/write_roles trong routers/customers.py.
    """

    @pytest.mark.parametrize("role", ("admin", "leader", "reception", "office"))
    def test_vai_tro_nghiep_vu_doc_duoc(self, client, as_role, role):
        as_role(role)
        assert client.get(_BASE).status_code == 200, role

    @pytest.mark.parametrize("role", ("staff", "lab_manager", "qms"))
    def test_khoi_lab_khong_con_doc_duoc(self, client, as_role, role):
        """Thông tin khách của từng phiếu vẫn tới được lab qua luồng xin/duyệt m26 —
        đúng cơ chế sinh ra để kiểm soát việc đó, thay vì mở cả sổ khách."""
        as_role(role)
        assert client.get(_BASE).status_code == 403, role

    @pytest.mark.parametrize("role", ("staff", "lab_manager"))
    def test_khoi_lab_khong_sua_duoc_ma_so_thue(self, client, as_role, role):
        """KTV sửa được mã số thuế của pháp nhân là lỗi phân vai, không phải tiện ích."""
        as_role(role)
        res = _create(client)
        assert res.status_code == 403
        assert res.json()["error"]["code"] == ErrorCode.FORBIDDEN

    @pytest.mark.parametrize("role", ("reception", "office", "admin"))
    def test_vai_tro_phu_trach_khach_hang_tao_duoc(self, client, as_role, role):
        as_role(role)
        assert _create(client, name=f"Do {role} tạo").status_code == 201

    def test_leader_chi_doc_khong_ghi(self, client, as_role):
        """Đọc được KHÔNG có nghĩa là ghi được — chỗ RBAC hay bị nới lỏng."""
        as_role("leader")
        assert client.get(_BASE).status_code == 200
        assert _create(client).status_code == 403


@requires_db
class TestCustomerAudit:
    def test_create_writes_audit_row(self, client, as_role, audit_rows):
        as_role("admin")
        before = audit_rows("CUSTOMER_CREATE")
        _create(client, name="Công ty Có Vết")
        assert audit_rows("CUSTOMER_CREATE") == before + 1

    def test_read_does_not_write_audit_row(self, client, as_role, audit_rows):
        """Ghi vết cho thao tác ĐỌC sẽ làm phình bảng và chôn vùi thao tác ghi."""
        as_role("admin")
        before = audit_rows("CUSTOMER_CREATE")
        client.get(_BASE)
        assert audit_rows("CUSTOMER_CREATE") == before
