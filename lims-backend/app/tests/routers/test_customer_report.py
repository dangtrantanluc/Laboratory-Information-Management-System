"""m50 — báo cáo tổng hợp khách hàng theo kỳ, phục vụ Văn phòng.

Yêu cầu nghiệp vụ: "role văn phòng cần báo cáo tổng thể tất cả các hoạt động của Viện…
cần số liệu tổng hợp hàng tháng về Khách hàng, và truy cập vào master data khách hàng."

Master data thì Văn phòng ĐÃ có quyền (routers/customers.py read_roles). Thứ thiếu là
số liệu tổng hợp — đó là phần test ở đây.

Hai bất biến dễ vỡ nhất, và vì sao:

1. **Văn phòng phải xem được.** Họ bị chặn ở báo cáo MẪU (B03) vì đó là dữ liệu thử
   nghiệm; báo cáo này là dữ liệu thương mại. Nhầm hai thứ đó là chặn đúng người đang
   phải làm báo cáo.
2. **"Khách mới" ≠ "khách hoạt động".** Một khách tạo từ năm ngoái mà tháng này gửi mẫu
   thì hoạt động chứ không mới; cộng hai con số vào nhau là thổi phồng số liệu.
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.tests.conftest import requires_db

pytestmark = requires_db

_URL = "/api/v1/reports/customers"


def _iso(d: date) -> str:
    return d.isoformat()


@pytest.fixture(autouse=True)
def cache_sach():
    """Xoá cache báo cáo trước mỗi test.

    `report_common` cache kết quả 60 giây trên Redis, khoá gồm vai trò + bộ lọc. Cả bộ
    test chạy cùng vai "office" với kỳ mặc định nên DÙNG CHUNG một khoá: không dọn thì
    test sau đọc số liệu của test trước, và đỏ/xanh phụ thuộc thứ tự chạy.
    """
    from app.core.redis_client import get_redis

    r = get_redis()
    for k in list(r.scan_iter(match="report:*", count=200)):
        r.delete(k)
    yield


@pytest.fixture
def ky():
    """Kỳ báo cáo = tháng hiện tại, khớp mặc định của report_common.resolve_range()."""
    today = datetime.now(timezone.utc).date()
    dau = today.replace(day=1)
    sau = (dau.replace(day=28) + timedelta(days=4)).replace(day=1)
    return dau, sau


@pytest.fixture
def khach(client, as_role, db):
    """Một khách trong sổ + một phiếu nhận mẫu của khách đó trong kỳ."""
    as_role("reception")
    c = client.post("/api/v1/customers", json={"name": "Công ty Nhân Ái", "type": "external"})
    assert c.status_code == 201, c.text
    cus = c.json()["data"]
    i = client.post("/api/v1/intakes", json={
        "customer_id": cus["id"], "customer_name": "Công ty Nhân Ái", "code": "BC-001",
    })
    assert i.status_code == 201, i.text
    return cus, i.json()["data"]


class TestVanPhongXemDuoc:
    def test_van_phong_xem_duoc_bao_cao_khach_hang(self, client, as_role):
        """Bất biến số 1 — đây chính là yêu cầu nghiệp vụ."""
        as_role("office")

        r = client.get(_URL)

        assert r.status_code == 200, r.text
        assert {"summary", "series", "top_customers"} <= set(r.json()["data"])

    def test_van_phong_van_bi_chan_o_bao_cao_mau(self, client, as_role):
        """Đối trọng: mở báo cáo này KHÔNG được nới luôn dữ liệu thử nghiệm (B03)."""
        as_role("office")

        assert client.get("/api/v1/reports/samples").status_code == 403

    @pytest.mark.parametrize("role", ["admin", "leader", "reception", "office"])
    def test_cac_vai_quan_ly_deu_xem_duoc(self, client, as_role, role):
        as_role(role)

        assert client.get(_URL).status_code == 200

    @pytest.mark.parametrize("role", ["staff", "lab_manager", "qms"])
    def test_khoi_lab_khong_xem_duoc(self, client, as_role, role):
        """Khối lab bị che PII khách hàng (m26) — bảng xếp hạng khách theo doanh số
        sẽ là đường vòng qua chính cơ chế đó."""
        as_role(role)

        assert client.get(_URL).status_code == 403


class TestSoLieu:
    def test_dem_khach_moi_va_khach_hoat_dong(self, client, as_role, khach):
        as_role("office")

        s = client.get(_URL).json()["data"]["summary"]

        assert s["new_customers"] >= 1
        assert s["active_customers"] >= 1
        assert s["intakes"] >= 1

    def test_khach_cu_gui_mau_thi_HOAT_DONG_chu_khong_MOI(self, client, as_role, db, ky):
        """Bất biến số 2. Dựng một khách có created_at TRƯỚC kỳ rồi cho phát sinh
        phiếu trong kỳ — phải đếm vào 'hoạt động', không đếm vào 'mới'."""
        from sqlalchemy import text as _sql

        as_role("reception")
        cus = client.post("/api/v1/customers",
                          json={"name": "Khách cũ", "type": "external"}).json()["data"]
        db.execute(_sql("UPDATE customers SET created_at = :t WHERE id = :i"),
                   {"t": datetime(2020, 1, 1, tzinfo=timezone.utc), "i": cus["id"]})
        client.post("/api/v1/intakes", json={
            "customer_id": cus["id"], "customer_name": "Khách cũ", "code": "BC-CU",
        })

        as_role("office")
        d = client.get(_URL).json()["data"]

        ten = [c["name"] for c in d["top_customers"]]
        assert "Khách cũ" in ten, "khách có phát sinh phải nằm trong bảng xếp hạng"
        assert d["summary"]["new_customers"] == 0, "khách tạo từ 2020 không phải khách mới"
        assert d["summary"]["active_customers"] >= 1

    def test_khach_vang_lai_khong_bien_mat(self, client, as_role):
        """Phiếu không gắn sổ khách (khách vãng lai) vẫn phải được tổng hợp theo tên,
        nếu không doanh số của họ bốc hơi khỏi báo cáo."""
        as_role("reception")
        client.post("/api/v1/intakes",
                    json={"customer_name": "Khách vãng lai", "code": "BC-VL"})

        as_role("office")
        top = client.get(_URL).json()["data"]["top_customers"]

        vl = [c for c in top if c["name"] == "Khách vãng lai"]
        assert len(vl) == 1
        assert vl[0]["is_walk_in"] is True
        assert vl[0]["customer_id"] is None

    def test_tien_tra_ve_dang_chuoi_khong_mat_do_chinh_xac(self, client, as_role, khach):
        as_role("office")

        s = client.get(_URL).json()["data"]["summary"]

        assert isinstance(s["quoted_total"], str)
        assert isinstance(s["paid_total"], str)

    def test_ky_rong_van_tra_ve_cau_truc_day_du(self, client, as_role):
        """Tháng chưa có hoạt động là chuyện bình thường — không được nổ, không trả None."""
        as_role("office")

        r = client.get(_URL, params={"from": "2019-01-01", "to": "2019-02-01"})

        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["summary"]["intakes"] == 0
        assert d["series"] == [] and d["top_customers"] == []


class TestBoLoc:
    def test_khoang_ngay_nguoc_bi_tu_choi(self, client, as_role):
        as_role("office")

        r = client.get(_URL, params={"from": "2026-03-01", "to": "2026-01-01"})

        assert r.status_code in (400, 422), r.text

    def test_group_by_khong_hop_le_bi_tu_choi(self, client, as_role):
        as_role("office")

        assert client.get(_URL, params={"group_by": "quarter"}).status_code in (400, 422)

    def test_meta_noi_ro_ky_va_cach_gop(self, client, as_role, ky):
        """Người đọc phải biết con số đang nói về khoảng nào — nếu không thì không
        dùng được cho báo cáo tháng."""
        as_role("office")

        meta = client.get(_URL).json()["meta"]

        assert meta["from"] == _iso(ky[0]) and meta["to"] == _iso(ky[1])
        assert meta["group_by"] == "month"
