"""m33 — Phiếu nhận mẫu liên kết master data khách hàng.

Ba nhóm khẳng định, theo đúng thứ tự rủi ro:

1. Liên kết được lưu và trả về (chức năng).
2. customer_id rác bị chặn bằng 404 tiếng Việt, không phải lỗi FK thô của Postgres.
3. Khối lab bị che PII thì KHÔNG được nhận customer_id — nếu lọt, họ cầm id gọi
   GET /customers/{id} là đọc lại đúng những field vừa che (staff và lab_manager
   đều nằm trong read_roles của router customers). Đây là nhóm quan trọng nhất:
   hai nhóm trên hỏng thì thấy ngay, nhóm này hỏng thì im lặng rò rỉ.
"""
import uuid

from app.core.error_codes import ErrorCode
from app.tests.conftest import requires_db

_INTAKES = "/api/v1/intakes"
_CUSTOMERS = "/api/v1/customers"

_CUSTOMER = {
    "name": "Công ty TNHH Nông sản An Phát",
    "address": "123 Nguyễn Văn Cừ, Q.5, TP.HCM",
    "tax_code": "0301234567",
    "contact_person": "Chị Lan",
    "phone": "0908123456",
    "email": "lan@anphat.vn",
}


def _make_customer(client) -> dict:
    res = client.post(_CUSTOMERS, json=_CUSTOMER)
    assert res.status_code == 201, res.text
    return res.json()["data"]


def _make_intake(client, **kw) -> dict:
    body = {"customer_name": _CUSTOMER["name"], **kw}
    res = client.post(_INTAKES, json=body)
    assert res.status_code == 201, res.text
    return res.json()["data"]


@requires_db
class TestIntakeCustomerLink:
    def test_intake_stores_customer_id(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        customer = _make_customer(client)

        intake = _make_intake(client, customer_id=customer["id"])
        assert intake["customer_id"] == customer["id"]

    def test_intake_without_customer_id_still_works(self, client, as_role, department):
        """Khách vãng lai: gõ tay, không vào sổ — vẫn phải nhận mẫu được."""
        as_role("reception", department_id=department.id)

        intake = _make_intake(client, customer_name="Khách lẻ không vào sổ")
        assert intake["customer_id"] is None
        assert intake["customer_name"] == "Khách lẻ không vào sổ"

    def test_unknown_customer_id_returns_404(self, client, as_role, department):
        as_role("reception", department_id=department.id)

        res = client.post(
            _INTAKES,
            json={"customer_name": "Có tên nhưng id sai", "customer_id": str(uuid.uuid4())},
        )
        assert res.status_code == 404, res.text
        assert res.json()["error"]["code"] == ErrorCode.CUSTOMER_NOT_FOUND

    def test_snapshot_fields_do_not_follow_customer_edits(self, client, as_role, department):
        """Phiếu giữ BẢN CHỤP: sửa địa chỉ trong sổ KHÔNG được đổi phiếu đã lập.

        Yêu cầu hồ sơ VILAS — phiếu đã in phải giữ nguyên thông tin lúc nhận mẫu.
        """
        as_role("reception", department_id=department.id)
        customer = _make_customer(client)
        intake = _make_intake(
            client, customer_id=customer["id"], address=_CUSTOMER["address"]
        )

        client.patch(f"{_CUSTOMERS}/{customer['id']}", json={"address": "Địa chỉ MỚI"})

        after = client.get(f"{_INTAKES}/{intake['id']}").json()["data"]
        assert after["address"] == _CUSTOMER["address"], "phiếu không được đổi theo sổ"


@requires_db
class TestIntakeCustomerIdMasking:
    """customer_id phải bị che cùng lúc với các field PII (m26)."""

    def test_masked_role_does_not_receive_customer_id(
        self, client, as_role, department, db
    ):
        as_role("reception", department_id=department.id)
        customer = _make_customer(client)
        intake = _make_intake(client, customer_id=customer["id"], **{
            k: v for k, v in _CUSTOMER.items() if k != "name"
        })

        # Chuyển 1 chỉ tiêu tới phòng lab để lab được phép THẤY phiếu (nhưng bị che PII).
        res = client.post(
            f"{_INTAKES}/{intake['id']}/dispatches",
            json={"chi_tieu": "pH", "target_department_id": str(department.id)},
        )
        assert res.status_code == 201, res.text

        as_role("lab_manager", department_id=department.id)
        seen = client.get(f"{_INTAKES}/{intake['id']}").json()["data"]

        assert seen["customer_info_masked"] is True, "tiền đề: vai trò này phải bị che"
        assert seen["customer_id"] is None, (
            "customer_id lọt qua lớp che — khối lab cầm id gọi GET /customers/{id} "
            "là đọc lại được toàn bộ thông tin khách vừa che"
        )
        assert seen["customer_name"] != _CUSTOMER["name"]

    def test_reception_still_receives_customer_id(self, client, as_role, department):
        """Đối chứng: vai trò KHÔNG bị che vẫn phải thấy liên kết, nếu không là che nhầm."""
        as_role("reception", department_id=department.id)
        customer = _make_customer(client)
        intake = _make_intake(client, customer_id=customer["id"])

        seen = client.get(f"{_INTAKES}/{intake['id']}").json()["data"]
        assert seen["customer_id"] == customer["id"]
