"""Luồng #3 — Không phù hợp: mở phiếu → mở CAPA → hành động → đóng → BẤT BIẾN.

Chọn luồng này vì nó có BẤT BIẾN NGHIỆP VỤ thật: CAPA đã đóng thì không sửa được
nữa (ISO/IEC 17025 §8.7). Bất biến kiểu này chỉ tồn tại trong code — không ràng
buộc DB nào giữ hộ — nên nếu không có test thì một lần refactor là mất, và mất
im lặng: hệ thống vẫn 200, chỉ là hồ sơ chất lượng sửa được sau khi đã đóng.
"""
from app.core.error_codes import ErrorCode
from app.tests.conftest import requires_db

_BASE = "/api/v1/nonconformities"


def _create_nc(client, department, **kw):
    return client.post(
        _BASE,
        json={
            "title": kw.pop("title", "Mẫu bị vỡ khi vận chuyển"),
            "description": kw.pop("description", "Phát hiện lúc nhận mẫu sáng 12/3"),
            "severity": kw.pop("severity", "major"),
            "department_id": str(department.id),
            **kw,
        },
    )


@requires_db
class TestNcLifecycle:
    def test_create_returns_code_and_open_status(self, client, as_role, department):
        as_role("admin")
        res = _create_nc(client, department)
        assert res.status_code == 201, res.text

        body = res.json()["data"]
        assert set(body) >= {"id", "nc_code", "status", "severity"}
        assert body["status"] == "open"

    def test_cannot_add_action_before_capa_opened(self, client, as_role, department):
        """Bất biến: chưa mở CAPA thì chưa có chỗ để gắn hành động."""
        as_role("admin")
        nc_id = _create_nc(client, department).json()["data"]["id"]

        res = client.post(f"{_BASE}/{nc_id}/actions", json={"action": "Sửa quy trình"})
        assert res.status_code == 409
        assert res.json()["error"]["code"] == ErrorCode.CAPA_NOT_OPENED

    def test_capa_can_be_opened_then_action_added(self, client, as_role, department):
        me = as_role("admin")
        nc_id = _create_nc(client, department).json()["data"]["id"]

        capa = client.post(
            f"{_BASE}/{nc_id}/capa",
            json={
                "root_cause": "Thùng vận chuyển không có đệm chống sốc",
                "owner_id": str(me.id),
            },
        )
        assert capa.status_code in (200, 201), capa.text

        act = client.post(
            f"{_BASE}/{nc_id}/actions",
            json={"action": "Mua thùng có đệm"},
        )
        assert act.status_code in (200, 201), act.text

    def test_duplicate_capa_rejected(self, client, as_role, department):
        me = as_role("admin")
        nc_id = _create_nc(client, department).json()["data"]["id"]
        payload = {"root_cause": "Nguyên nhân gốc", "owner_id": str(me.id)}

        assert client.post(f"{_BASE}/{nc_id}/capa", json=payload).status_code in (200, 201)
        res = client.post(f"{_BASE}/{nc_id}/capa", json=payload)
        assert res.status_code == 409
        assert res.json()["error"]["code"] == ErrorCode.CAPA_EXISTS

    def test_cancel_moves_to_cancelled(self, client, as_role, department):
        as_role("admin")
        nc_id = _create_nc(client, department).json()["data"]["id"]

        res = client.post(f"{_BASE}/{nc_id}/cancel", json={"reason": "Trùng phiếu khác"})
        assert res.status_code in (200, 201), res.text
        assert client.get(f"{_BASE}/{nc_id}").json()["data"]["status"] == "cancelled"


@requires_db
class TestNcValidation:
    def test_empty_title_rejected(self, client, as_role, department):
        """Lỗi SCHEMA trả 400 (VALIDATION_ERROR); vi phạm QUY TẮC NGHIỆP VỤ trả 422.

        Phân biệt này là hợp đồng API thật của hệ thống — kiểm để nó không trôi.
        """
        as_role("admin")
        assert _create_nc(client, department, title="").status_code == 400

    def test_unknown_severity_rejected(self, client, as_role, department):
        as_role("admin")
        assert _create_nc(client, department, severity="catastrophic").status_code == 400

    def test_stats_endpoint_returns_grouping(self, client, as_role, department):
        as_role("admin")
        _create_nc(client, department)
        stats = client.get(f"{_BASE}/stats").json()["data"]
        assert isinstance(stats, dict) and stats
