"""Mã phiếu nhận mẫu do nhân viên tự đặt (không sinh tự động).

Mã trên phiếu phải khớp nhãn đã dán lên mẫu và sổ tay tại quầy nhận, nên số thứ
tự của hệ thống không dùng được. Ba khẳng định, theo thứ tự rủi ro:

1. Mã nhân viên gõ được lưu nguyên văn (chức năng).
2. Trùng mã trả 409 DUPLICATE_CODE — nếu lọt xuống DB thì UniqueConstraint
   uq_intake_code nổ IntegrityError thành 500 và nhân viên không biết vì sao.
3. Bỏ trống vẫn nhận mẫu được bằng mã dự phòng — quầy không được đứng hình.
"""
from app.core.error_codes import ErrorCode
from app.tests.conftest import requires_db

_INTAKES = "/api/v1/intakes"


def _post(client, **kw):
    return client.post(_INTAKES, json={"customer_name": "Công ty TNHH Thử Nghiệm", **kw})


@requires_db
class TestIntakeManualCode:
    def test_staff_code_is_stored_verbatim(self, client, as_role, department):
        as_role("reception", department_id=department.id)

        res = _post(client, code="PNM-2026/0457")
        assert res.status_code == 201, res.text
        assert res.json()["data"]["code"] == "PNM-2026/0457"

    def test_whitespace_is_trimmed(self, client, as_role, department):
        as_role("reception", department_id=department.id)

        res = _post(client, code="  PNM-2026/0458  ")
        assert res.status_code == 201, res.text
        assert res.json()["data"]["code"] == "PNM-2026/0458"

    def test_duplicate_code_returns_409(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        assert _post(client, code="PNM-TRUNG").status_code == 201

        res = _post(client, code="PNM-TRUNG")
        assert res.status_code == 409, res.text
        assert res.json()["error"]["code"] == ErrorCode.DUPLICATE_CODE

    def test_blank_code_falls_back_to_generated(self, client, as_role, department):
        """Bỏ trống không được chặn quầy nhận mẫu — vẫn có mã NM-<năm>-<số>."""
        as_role("reception", department_id=department.id)

        res = _post(client, code="   ")
        assert res.status_code == 201, res.text
        assert res.json()["data"]["code"].startswith("NM-")

    def test_code_can_be_corrected_by_patch(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        intake = _post(client, code="PNM-GO-NHAM").json()["data"]

        res = client.patch(f"{_INTAKES}/{intake['id']}", json={"code": "PNM-2026/0459"})
        assert res.status_code == 200, res.text
        assert res.json()["data"]["code"] == "PNM-2026/0459"

    def test_patch_to_existing_code_returns_409(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        _post(client, code="PNM-DA-CO")
        intake = _post(client, code="PNM-KHAC").json()["data"]

        res = client.patch(f"{_INTAKES}/{intake['id']}", json={"code": "PNM-DA-CO"})
        assert res.status_code == 409, res.text
        assert res.json()["error"]["code"] == ErrorCode.DUPLICATE_CODE
