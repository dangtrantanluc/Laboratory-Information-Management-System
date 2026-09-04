"""m41 (W3) — báo giá đã gửi khách là chứng từ: có phiên bản, không xoá cứng, tự hết hạn.

BA LỖ HỔNG ĐƯỢC CHẶN
1. `update_quotation` chỉ khoá ở 'accepted' → bản 'sent' (ĐÃ GỬI KHÁCH) sửa đè được
   mà không giữ bản cũ, nhật ký chỉ ghi code + total.
2. `delete_quotation` dùng `db.delete()` → xoá cứng, cascade cả dòng chi tiết.
3. `valid_until` qua rồi vẫn nằm ở 'sent' vì 'expired' chỉ đổi được bằng tay.
"""
from datetime import date, timedelta

from app.core.error_codes import ErrorCode
from app.tests.conftest import requires_db

_QUOTATIONS = "/api/v1/quotations"


def _bao_gia(client, **kw) -> dict:
    body = {
        "customer_name": "Cty TNHH Thuỷ Sản Cà Mau",
        "customer_tax_code": "2000123456",
        "items": [
            {"parameter_name": "Histamine", "quantity": 2, "unit_price": "450000"},
        ],
    }
    body.update(kw)
    res = client.post(_QUOTATIONS, json=body)
    assert res.status_code == 201, res.text
    return res.json()["data"]


@requires_db
class TestBanDaGuiKhachCoPhienBan:
    def test_sua_ban_nhap_khong_sinh_phien_ban(self, client, as_role):
        """Nháp chưa gửi ai — lưu lịch sử của nó chỉ tạo nhiễu."""
        as_role("reception")
        q = _bao_gia(client)
        assert q["version"] == 1

        client.patch(f"{_QUOTATIONS}/{q['id']}", json={"note": "sửa nháp"})
        assert client.get(f"{_QUOTATIONS}/{q['id']}/versions").json()["data"] == []

    def test_sua_ban_da_gui_thi_chup_lai_ban_cu(self, client, as_role):
        as_role("reception")
        q = _bao_gia(client)
        client.post(f"{_QUOTATIONS}/{q['id']}/status", json={"status": "sent"})

        res = client.patch(f"{_QUOTATIONS}/{q['id']}", json={
            "items": [{"parameter_name": "Histamine", "quantity": 2, "unit_price": "500000"}],
            "revision_reason": "Khách xin điều chỉnh đơn giá",
        })
        assert res.status_code == 200, res.text
        assert res.json()["data"]["version"] == 2

        versions = client.get(f"{_QUOTATIONS}/{q['id']}/versions").json()["data"]
        assert len(versions) == 1
        v1 = versions[0]
        assert v1["version"] == 1
        assert v1["reason"] == "Khách xin điều chỉnh đơn giá"
        # Bản chụp phải đọc lại NGUYÊN VẸN thứ khách đã nhận, gồm cả dòng chi tiết.
        assert v1["snapshot"]["items"][0]["unit_price"] == "450000.00"
        assert v1["snapshot"]["total"] != res.json()["data"]["total"]

    def test_moi_lan_sua_la_mot_phien_ban(self, client, as_role):
        as_role("reception")
        q = _bao_gia(client)
        client.post(f"{_QUOTATIONS}/{q['id']}/status", json={"status": "sent"})

        for i in range(3):
            client.patch(f"{_QUOTATIONS}/{q['id']}", json={"note": f"lần {i}"})

        versions = client.get(f"{_QUOTATIONS}/{q['id']}/versions").json()["data"]
        assert [v["version"] for v in versions] == [3, 2, 1]

    def test_ban_khach_da_dong_y_van_khoa_han(self, client, as_role):
        as_role("reception")
        q = _bao_gia(client)
        client.post(f"{_QUOTATIONS}/{q['id']}/status", json={"status": "sent"})
        client.post(f"{_QUOTATIONS}/{q['id']}/status", json={"status": "accepted"})

        res = client.patch(f"{_QUOTATIONS}/{q['id']}", json={"note": "x"})
        assert res.status_code == 409
        assert res.json()["error"]["code"] == ErrorCode.LOCKED


@requires_db
class TestThuHoiThayViXoaCung:
    def test_thu_hoi_giu_lai_ban_ghi(self, client, as_role, db):
        from app.models.quotation import Quotation

        as_role("reception")
        q = _bao_gia(client)
        client.post(f"{_QUOTATIONS}/{q['id']}/status", json={"status": "sent"})

        assert client.delete(f"{_QUOTATIONS}/{q['id']}").status_code == 204
        # Biến mất với người dùng…
        assert client.get(f"{_QUOTATIONS}/{q['id']}").status_code == 404
        assert client.get(_QUOTATIONS).json()["data"] == []
        # …nhưng vẫn còn trong DB để tra ngược.
        db.expire_all()
        row = db.get(Quotation, q["id"])
        assert row is not None and row.deleted_at is not None

    def test_dong_chi_tiet_khong_bi_cascade_mat(self, client, as_role, db):
        from app.models.quotation import QuotationItem

        as_role("reception")
        q = _bao_gia(client)
        client.delete(f"{_QUOTATIONS}/{q['id']}")

        db.expire_all()
        n = db.query(QuotationItem).filter(QuotationItem.quotation_id == q["id"]).count()
        assert n == 1, "xoá cứng cascade mất dòng chi tiết của chứng từ"

    def test_thu_hoi_co_ghi_audit(self, client, as_role, audit_rows):
        as_role("reception")
        q = _bao_gia(client)
        truoc = audit_rows("QUOTATION_REVOKE")
        client.delete(f"{_QUOTATIONS}/{q['id']}")
        assert audit_rows("QUOTATION_REVOKE") == truoc + 1


@requires_db
class TestTuHetHieuLuc:
    def test_cron_chuyen_ban_qua_han_sang_expired(self, client, as_role, db):
        from app.services import quotation_cron_service

        as_role("reception")
        hom_qua = (date.today() - timedelta(days=1)).isoformat()
        con_han = (date.today() + timedelta(days=10)).isoformat()
        qua_han = _bao_gia(client, valid_until=hom_qua)
        con_hieu_luc = _bao_gia(client, valid_until=con_han)
        for q in (qua_han, con_hieu_luc):
            client.post(f"{_QUOTATIONS}/{q['id']}/status", json={"status": "sent"})

        assert quotation_cron_service.run_quotation_expiry(db) == {"expired": 1}
        assert client.get(f"{_QUOTATIONS}/{qua_han['id']}").json()["data"]["status"] == "expired"
        assert client.get(f"{_QUOTATIONS}/{con_hieu_luc['id']}").json()["data"]["status"] == "sent"

    def test_khong_dung_toi_ban_nhap(self, client, as_role, db):
        """Nháp chưa gửi ai — hết hạn không có nghĩa."""
        from app.services import quotation_cron_service

        as_role("reception")
        hom_qua = (date.today() - timedelta(days=1)).isoformat()
        q = _bao_gia(client, valid_until=hom_qua)

        quotation_cron_service.run_quotation_expiry(db)
        assert client.get(f"{_QUOTATIONS}/{q['id']}").json()["data"]["status"] == "draft"

    def test_chay_lai_khong_doi_them_gi(self, client, as_role, db):
        from app.services import quotation_cron_service

        as_role("reception")
        q = _bao_gia(client, valid_until=(date.today() - timedelta(days=1)).isoformat())
        client.post(f"{_QUOTATIONS}/{q['id']}/status", json={"status": "sent"})

        assert quotation_cron_service.run_quotation_expiry(db)["expired"] == 1
        assert quotation_cron_service.run_quotation_expiry(db)["expired"] == 0
