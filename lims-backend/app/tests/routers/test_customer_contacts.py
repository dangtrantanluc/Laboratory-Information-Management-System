"""m35 — danh bạ liên hệ khách hàng (1 khách – n người).

Bốn nhóm khẳng định, theo thứ tự rủi ro:

1. CRUD cơ bản chạy (chức năng).
2. Bất biến "mỗi khách đúng 1 liên hệ mặc định" không bao giờ vỡ — đây là thứ quầy
   nhận mẫu dựa vào để tự điền phiếu; vỡ thì phiếu điền sai người mà không ai thấy.
3. Người đã tắt (nghỉ việc) không được là mặc định, và không lọt vào danh sách mà
   quầy dùng để chọn.
4. Không đọc/ghi chéo được danh bạ của khách khác qua id.
"""
from app.tests.conftest import requires_db

_CUSTOMERS = "/api/v1/customers"


def _customer(client, name="Công ty TNHH Thực phẩm An Bình") -> dict:
    res = client.post(_CUSTOMERS, json={"name": name})
    assert res.status_code == 201, res.text
    return res.json()["data"]


def _add(client, cid, **kw):
    body = {"full_name": "Trần Thị Mai", **kw}
    return client.post(f"{_CUSTOMERS}/{cid}/contacts", json=body)


def _list(client, cid, **params):
    res = client.get(f"{_CUSTOMERS}/{cid}/contacts", params=params)
    assert res.status_code == 200, res.text
    return res.json()["data"]


@requires_db
class TestCustomerContactsCrud:
    def test_create_and_list(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        cid = _customer(client)["id"]

        res = _add(client, cid, job_title="Trưởng phòng QA", email="mai@ab.vn", phone="0909123456")
        assert res.status_code == 201, res.text
        c = res.json()["data"]
        assert c["full_name"] == "Trần Thị Mai"
        assert c["job_title"] == "Trưởng phòng QA"
        assert _list(client, cid)[0]["id"] == c["id"]

    def test_update_and_delete(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        cid = _customer(client)["id"]
        c = _add(client, cid).json()["data"]

        res = client.patch(f"{_CUSTOMERS}/{cid}/contacts/{c['id']}", json={"phone": "0988"})
        assert res.status_code == 200, res.text
        assert res.json()["data"]["phone"] == "0988"

        assert client.delete(f"{_CUSTOMERS}/{cid}/contacts/{c['id']}").status_code == 204
        assert _list(client, cid) == []


@requires_db
class TestPrimaryInvariant:
    def test_first_contact_is_primary_automatically(self, client, as_role, department):
        """Khách có đúng 1 liên hệ mà không ai mặc định thì quầy không tự điền được."""
        as_role("reception", department_id=department.id)
        cid = _customer(client)["id"]

        c = _add(client, cid).json()["data"]
        assert c["is_primary"] is True

    def test_setting_new_primary_clears_the_old_one(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        cid = _customer(client)["id"]
        first = _add(client, cid, full_name="Người A").json()["data"]
        second = _add(client, cid, full_name="Người B").json()["data"]
        assert first["is_primary"] is True and second["is_primary"] is False

        res = client.patch(f"{_CUSTOMERS}/{cid}/contacts/{second['id']}", json={"is_primary": True})
        assert res.status_code == 200, res.text

        rows = {r["id"]: r["is_primary"] for r in _list(client, cid)}
        assert rows[second["id"]] is True
        assert rows[first["id"]] is False
        assert sum(rows.values()) == 1

    def test_create_with_primary_clears_the_old_one(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        cid = _customer(client)["id"]
        first = _add(client, cid, full_name="Người A").json()["data"]

        second = _add(client, cid, full_name="Người B", is_primary=True).json()["data"]
        rows = {r["id"]: r["is_primary"] for r in _list(client, cid)}
        assert rows[second["id"]] is True and rows[first["id"]] is False
        assert sum(rows.values()) == 1


@requires_db
class TestInactiveContacts:
    def test_deactivating_primary_drops_the_primary_flag(self, client, as_role, department):
        """Nếu không gỡ cờ, quầy sẽ tự điền tên một người đã nghỉ việc."""
        as_role("reception", department_id=department.id)
        cid = _customer(client)["id"]
        c = _add(client, cid).json()["data"]
        assert c["is_primary"] is True

        res = client.patch(f"{_CUSTOMERS}/{cid}/contacts/{c['id']}", json={"is_active": False})
        assert res.status_code == 200, res.text
        assert res.json()["data"]["is_active"] is False
        assert res.json()["data"]["is_primary"] is False

    def test_cannot_make_inactive_contact_primary(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        cid = _customer(client)["id"]
        _add(client, cid, full_name="Người A")
        b = _add(client, cid, full_name="Người B", is_active=False).json()["data"]

        res = client.patch(f"{_CUSTOMERS}/{cid}/contacts/{b['id']}", json={"is_primary": True})
        assert res.status_code == 400, res.text

    def test_include_inactive_false_hides_them(self, client, as_role, department):
        """Quầy nhận mẫu gọi include_inactive=false — không được chọn người đã nghỉ."""
        as_role("reception", department_id=department.id)
        cid = _customer(client)["id"]
        _add(client, cid, full_name="Đang làm")
        _add(client, cid, full_name="Đã nghỉ", is_active=False)

        assert len(_list(client, cid)) == 2
        active = _list(client, cid, include_inactive=False)
        assert [r["full_name"] for r in active] == ["Đang làm"]


@requires_db
class TestCrossCustomerIsolation:
    def test_cannot_read_contact_of_another_customer(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        a = _customer(client, "Khách A")["id"]
        b = _customer(client, "Khách B")["id"]
        contact_of_a = _add(client, a).json()["data"]

        res = client.patch(f"{_CUSTOMERS}/{b}/contacts/{contact_of_a['id']}", json={"phone": "1"})
        assert res.status_code == 404, res.text

    def test_contacts_of_unknown_customer_return_404(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        res = client.get(f"{_CUSTOMERS}/00000000-0000-0000-0000-000000000000/contacts")
        assert res.status_code == 404, res.text
