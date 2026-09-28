"""m51 — công bố khoa học ghi được THÁNG, không chỉ năm.

Yêu cầu nghiệp vụ: màn hình chi tiết phải nói "Thời gian công bố (tháng, năm)" thay vì
chỉ "Năm công bố". Bìa tạp chí và quyết định cấp bằng đều ghi tháng; gộp về một con số
năm là mất thông tin ngay từ lúc nhập.

Bất biến quan trọng nhất ở đây là bất biến thứ hai: **tháng TUỲ CHỌN**. Dữ liệu sẵn có
của Viện (file "TỔNG HỢP CÁC HOẠT ĐỘNG 2024-2025") chỉ ghi năm, nên ép bắt buộc sẽ chặn
đúng những bản ghi đang có thật. NULL ở đây có nghĩa đọc được: "chỉ biết năm".
"""
import pytest

from app.tests.conftest import requires_db

pytestmark = requires_db

_PUBS = "/api/v1/publications"

_TAC_GIA = [{"external_name": "Nguyễn Văn A", "author_order": 1, "is_corresponding": True}]


def _tao(client, **kw):
    body = {
        "type": "paper", "title": "Bài báo kiểm tra tháng", "journal": "Catena",
        "year": 2025, "pub_scope": "international", "authors": _TAC_GIA, **kw,
    }
    return client.post(_PUBS, json=body)


class TestGhiThangCongBo:
    def test_tao_kem_thang(self, client, as_role):
        as_role("admin")

        r = _tao(client, month=3)

        assert r.status_code == 201, r.text
        assert r.json()["data"]["month"] == 3

    def test_thang_la_TUY_CHON(self, client, as_role):
        """Dữ liệu Excel cũ chỉ có năm — bắt buộc tháng sẽ chặn chính chúng."""
        as_role("admin")

        r = _tao(client)

        assert r.status_code == 201, r.text
        assert r.json()["data"]["month"] is None

    def test_sua_thang_qua_patch(self, client, as_role):
        as_role("admin")
        pid = _tao(client).json()["data"]["id"]

        r = client.patch(f"{_PUBS}/{pid}", json={"month": 11})

        assert r.status_code == 200, r.text
        assert r.json()["data"]["month"] == 11

    def test_go_thang_ve_khong_ro(self, client, as_role):
        """Sửa nhầm thì phải quay lại được trạng thái "chỉ biết năm"."""
        as_role("admin")
        pid = _tao(client, month=6).json()["data"]["id"]

        r = client.patch(f"{_PUBS}/{pid}", json={"month": None})

        assert r.status_code == 200, r.text
        assert r.json()["data"]["month"] is None

    @pytest.mark.parametrize("thang", [0, 13, -1, 99])
    def test_thang_khong_co_that_bi_tu_choi(self, client, as_role, thang):
        as_role("admin")

        r = _tao(client, month=thang)

        assert r.status_code in (400, 422), r.text

    def test_nam_van_bat_buoc(self, client, as_role):
        """m51 thêm tháng chứ KHÔNG nới lỏng năm — năm vẫn là trục lọc và xuất Excel."""
        as_role("admin")

        r = client.post(_PUBS, json={
            "type": "paper", "title": "Thiếu năm", "journal": "Catena",
            "pub_scope": "international", "month": 5, "authors": _TAC_GIA,
        })

        assert r.status_code in (400, 422), r.text

    def test_loc_theo_nam_khong_doi_hanh_vi(self, client, as_role):
        """Bản ghi có tháng và bản ghi chỉ có năm đều phải ra khi lọc theo năm đó."""
        as_role("admin")
        _tao(client, title="Có tháng", month=4)
        _tao(client, title="Không tháng")

        rows = client.get(_PUBS, params={"year": 2025, "limit": 100}).json()["data"]

        ten = {p["title"] for p in rows}
        assert {"Có tháng", "Không tháng"} <= ten
