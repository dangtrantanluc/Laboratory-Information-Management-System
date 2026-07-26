"""Luồng #2 — Rủi ro: đánh giá P×I → phân band → xử lý → đóng (ISO 9001 §6.1).

Chọn luồng này vì nó có TÍNH TOÁN thật (level = likelihood × impact, rồi ánh xạ
sang band), khác với CRUD thuần. Sai ngưỡng band là loại lỗi không ai phát hiện
bằng mắt: hệ thống vẫn chạy, chỉ là xếp hạng rủi ro sai.

Ngưỡng theo `risk_common.band`: ≤4 low · ≤12 medium · >12 high.
"""
import pytest

from app.core.error_codes import ErrorCode
from app.tests.conftest import requires_db

_BASE = "/api/v1/risks"


def _create(client, department, *, likelihood=3, impact=3, **kw):
    payload = {
        "title": kw.pop("title", "Rủi ro nhiễm chéo mẫu"),
        "context": kw.pop("context", "Khu vực chuẩn bị mẫu dùng chung dụng cụ"),
        "likelihood": likelihood,
        "impact": impact,
        "department_id": str(department.id),
        **kw,
    }
    return client.post(_BASE, json=payload)


@requires_db
class TestRiskScoring:
    """level = likelihood × impact, band suy ra từ level."""

    @pytest.mark.parametrize(
        "likelihood,impact,level,band",
        [
            (1, 1, 1, "low"),
            (2, 2, 4, "low"),      # biên trên của low
            (1, 5, 5, "medium"),   # biên dưới của medium
            (3, 4, 12, "medium"),  # biên trên của medium
            (5, 3, 15, "high"),    # biên dưới của high
            (5, 5, 25, "high"),
        ],
    )
    def test_band_boundaries(self, client, as_role, department, likelihood, impact, level, band):
        """Kiểm đúng các điểm BIÊN — đó là chỗ ngưỡng hay sai một đơn vị."""
        as_role("admin")
        body = _create(client, department, likelihood=likelihood, impact=impact).json()["data"]
        assert body["level"] == level
        assert body["band"] == band

    def test_likelihood_out_of_range_rejected(self, client, as_role, department):
        """Field(ge=1, le=5) — vi phạm schema trả 400, không phải 422."""
        as_role("admin")
        assert _create(client, department, likelihood=6).status_code == 400

    def test_impact_zero_rejected(self, client, as_role, department):
        as_role("admin")
        assert _create(client, department, impact=0).status_code == 400


@requires_db
class TestRiskLifecycle:
    def test_create_starts_open(self, client, as_role, department):
        as_role("admin")
        assert _create(client, department).json()["data"]["status"] == "open"

    def test_reassessment_recomputes_band(self, client, as_role, department):
        """Sửa likelihood/impact phải tính lại band, không giữ giá trị cũ."""
        as_role("admin")
        rid = _create(client, department, likelihood=1, impact=1).json()["data"]["id"]

        body = client.patch(f"{_BASE}/{rid}", json={"likelihood": 5, "impact": 5}).json()["data"]
        assert body["level"] == 25
        assert body["band"] == "high", "band không được giữ giá trị cũ sau khi đánh giá lại"

    def test_close_marks_closed(self, client, as_role, department):
        as_role("admin")
        rid = _create(client, department).json()["data"]["id"]

        res = client.post(f"{_BASE}/{rid}/close", json={"note": "Đã kiểm soát"})
        assert res.status_code in (200, 201), res.text
        assert client.get(f"{_BASE}/{rid}").json()["data"]["status"] == "closed"

    def test_stats_matrix_counts_created_risk(self, client, as_role, department):
        as_role("admin")
        _create(client, department, likelihood=5, impact=5)

        stats = client.get(f"{_BASE}/stats").json()["data"]
        assert set(stats) >= {"by_band", "by_status"}
        assert stats["by_band"]["high"] >= 1


@requires_db
class TestRiskRbac:
    def test_office_cannot_read_risks(self, client, as_role, department):
        as_role("office")
        assert client.get(_BASE).status_code == 403

    def test_unknown_risk_returns_404(self, client, as_role, department):
        as_role("admin")
        res = client.get(f"{_BASE}/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404
        assert res.json()["error"]["code"] in (ErrorCode.NOT_FOUND, ErrorCode.RISK_NOT_FOUND)
