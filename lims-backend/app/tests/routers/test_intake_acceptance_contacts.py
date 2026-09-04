"""Đợt 3 — chấp nhận/từ chối mẫu (m42), vai trò người liên hệ (m43), khoá phiếu (W14).

BA NHÓM BẤT BIẾN
· m42 — mẫu không đạt điều kiện tiếp nhận có ĐƯỜNG XỬ LÝ trong hệ thống, và quyết
  định phải ghi đủ lý do + người quyết + thời điểm (ISO/IEC 17025 §7.4.2–7.4.3).
  Hai đường song song vì Q6 chưa chốt: nhận có bảo lưu, hoặc từ chối hẳn.
· m43 — phiếu giữ được người gửi mẫu ≠ người nhận kết quả ≠ người trả tiền, dưới dạng
  BẢN CHỤP không đổi theo danh bạ.
· W14 — phiếu đã đóng thì bản chụp đứng yên, và nhật ký lưu được giá trị TRƯỚC.
"""
from app.core.error_codes import ErrorCode
from app.tests.conftest import requires_db

_INTAKES = "/api/v1/intakes"
_CUSTOMERS = "/api/v1/customers"


def _intake(client, **kw) -> dict:
    body = {"customer_name": "Cty CP Chế Biến Thuỷ Sản Sao Mai", "tax_code": "2000999888"}
    body.update(kw)
    res = client.post(_INTAKES, json=body)
    assert res.status_code == 201, res.text
    return res.json()["data"]


@requires_db
class TestTinhTrangVaSoLuongMau:
    def test_ghi_nhan_duoc_so_luong_va_tinh_trang(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _intake(client)

        res = client.patch(f"{_INTAKES}/{it['id']}/condition", json={
            "sample_count": 5, "condition_status": "acceptable",
        })
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["sample_count"] == 5
        assert data["condition_status"] == "acceptable"

    def test_mau_khong_dat_phai_mo_ta_sai_lech(self, client, as_role, department):
        """Nhận mẫu không đạt vẫn hợp lệ — nhưng phải bảo lưu trách nhiệm bằng mô tả."""
        as_role("reception", department_id=department.id)
        it = _intake(client)

        res = client.patch(f"{_INTAKES}/{it['id']}/condition", json={
            "condition_status": "not_acceptable",
        })
        assert res.status_code == 400, res.text
        assert res.json()["error"]["code"] == ErrorCode.VALIDATION_ERROR

    def test_nhan_co_bao_luu_thi_phieu_chay_tiep(self, client, as_role, department):
        """Đường 1 của Q6: mẫu không đạt nhưng khách vẫn muốn làm."""
        as_role("reception", department_id=department.id)
        it = _intake(client)

        assert client.patch(f"{_INTAKES}/{it['id']}/condition", json={
            "condition_status": "not_acceptable",
            "condition_note": "Mẫu về ở 12°C, yêu cầu bảo quản 2–8°C",
        }).status_code == 200
        # Vẫn chuyển lab được — quyết định là của khách, hệ thống chỉ ghi nhận.
        assert client.post(
            f"{_INTAKES}/{it['id']}/dispatches",
            json={"chi_tieu": "Histamine", "target_department_id": str(department.id)},
        ).status_code == 201


@requires_db
class TestTuChoiTiepNhan:
    def test_tu_choi_bat_buoc_neu_ly_do(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _intake(client)

        res = client.post(f"{_INTAKES}/{it['id']}/status", json={"status": "rejected"})
        assert res.status_code == 400, res.text
        assert "lý do" in res.json()["error"]["message"].lower()

    def test_tu_choi_ghi_du_ai_luc_nao_vi_sao(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _intake(client)

        res = client.post(f"{_INTAKES}/{it['id']}/status", json={
            "status": "rejected", "note": "Thiếu mẫu: nhận 1/3 đơn vị theo phiếu",
        })
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["status"] == "rejected"
        assert data["rejected_reason"] == "Thiếu mẫu: nhận 1/3 đơn vị theo phiếu"
        assert data["decided_by_name"]
        assert data["decided_at"]

    def test_huy_van_khong_bat_buoc_ly_do(self, client, as_role, department):
        """'Huỷ' là thao tác hành chính, khác 'từ chối' là quyết định kỹ thuật."""
        as_role("reception", department_id=department.id)
        it = _intake(client)
        assert client.post(
            f"{_INTAKES}/{it['id']}/status", json={"status": "cancelled"}
        ).status_code == 200

    def test_phieu_bi_tu_choi_khong_chuyen_lab_duoc(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _intake(client)
        client.post(f"{_INTAKES}/{it['id']}/status", json={
            "status": "rejected", "note": "Sai bao bì",
        })

        res = client.post(
            f"{_INTAKES}/{it['id']}/dispatches",
            json={"chi_tieu": "pH", "target_department_id": str(department.id)},
        )
        assert res.status_code == 409, res.text

    def test_da_chuyen_lab_thi_khong_tu_choi_tiep_nhan_duoc(
        self, client, as_role, department
    ):
        """Mẫu đã ở phòng lab thì không còn là "từ chối TIẾP NHẬN" nữa."""
        as_role("reception", department_id=department.id)
        it = _intake(client)
        client.post(
            f"{_INTAKES}/{it['id']}/dispatches",
            json={"chi_tieu": "pH", "target_department_id": str(department.id)},
        )
        res = client.post(f"{_INTAKES}/{it['id']}/status", json={
            "status": "rejected", "note": "x",
        })
        assert res.status_code == 409, res.text


@requires_db
class TestNguoiLienHeTheoVaiTro:
    def test_nguoi_gui_khac_nguoi_nhan_ket_qua(self, client, as_role, department):
        """Tình huống SR02 của bản kiểm toán — trước m43 không biểu diễn được."""
        as_role("reception", department_id=department.id)
        it = _intake(client)

        res = client.put(f"{_INTAKES}/{it['id']}/contacts", json={"contacts": [
            {"role": "courier", "full_name": "Nguyễn Văn A", "job_title": "Nhân viên QA"},
            {"role": "result_recipient", "full_name": "Trần Thị B",
             "job_title": "Trưởng phòng QA", "email": "qa.head@saomai.vn"},
            {"role": "billing", "full_name": "Lê Văn C", "job_title": "Kế toán"},
        ]})
        assert res.status_code == 200, res.text
        by_role = {c["role"]: c for c in res.json()["data"]}
        assert by_role["courier"]["full_name"] == "Nguyễn Văn A"
        assert by_role["result_recipient"]["full_name"] == "Trần Thị B"
        assert by_role["billing"]["full_name"] == "Lê Văn C"

    def test_mot_vai_khai_hai_lan_bi_tu_choi(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _intake(client)
        res = client.put(f"{_INTAKES}/{it['id']}/contacts", json={"contacts": [
            {"role": "courier", "full_name": "A"},
            {"role": "courier", "full_name": "B"},
        ]})
        assert res.status_code == 400, res.text

    def test_ban_chup_khong_doi_theo_danh_ba(self, client, as_role, department, db):
        """Nguyên tắc snapshot của m35: sổ khách đổi không làm sai phiếu đã in."""
        from app.models.customer import Customer, CustomerContact

        as_role("reception", department_id=department.id)
        kh = Customer(name="Cty Đổi Người", type="external")
        db.add(kh)
        db.flush()
        lh = CustomerContact(
            customer_id=kh.id, full_name="Người Cũ", is_primary=True,
            roles=["result_recipient"],
        )
        db.add(lh)
        db.flush()

        it = _intake(client, customer_id=str(kh.id))
        client.put(f"{_INTAKES}/{it['id']}/contacts", json={"contacts": [
            {"role": "result_recipient", "full_name": "Người Cũ"},
        ]})

        lh.full_name = "Người Mới"
        db.flush()

        rows = client.get(f"{_INTAKES}/{it['id']}/contacts").json()["data"]
        assert rows[0]["full_name"] == "Người Cũ", "phiếu đã lập bị đổi theo danh bạ"

    def test_danh_ba_luu_duoc_vai_tro_mac_dinh(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        kh = client.post(_CUSTOMERS, json={"name": "Cty Phân Vai"}).json()["data"]
        res = client.post(f"{_CUSTOMERS}/{kh['id']}/contacts", json={
            "full_name": "Phạm Thị D", "roles": ["courier", "technical"],
        })
        assert res.status_code == 201, res.text
        assert set(res.json()["data"]["roles"]) == {"courier", "technical"}


@requires_db
class TestKhoaPhieuSauKhiDong:
    def test_phieu_da_tra_ket_qua_khong_sua_duoc_thong_tin_khach(
        self, client, as_role, department
    ):
        """Bản chụp mà sửa được sau khi phát hành thì không còn giá trị pháp lý."""
        as_role("reception", department_id=department.id)
        it = _intake(client)
        client.post(
            f"{_INTAKES}/{it['id']}/dispatches",
            json={"chi_tieu": "pH", "target_department_id": str(department.id)},
        )
        client.post(f"{_INTAKES}/{it['id']}/status", json={"status": "completed"})

        res = client.patch(f"{_INTAKES}/{it['id']}", json={"customer_name": "Tên Khác"})
        assert res.status_code == 409, res.text
        assert res.json()["error"]["code"] == ErrorCode.LOCKED

    def test_ghi_chu_van_sua_duoc_sau_khi_dong(self, client, as_role, department):
        """Ghi chú bổ sung sau khi trả kết quả là nghiệp vụ bình thường."""
        as_role("reception", department_id=department.id)
        it = _intake(client)
        client.post(f"{_INTAKES}/{it['id']}/status", json={"status": "cancelled"})

        assert client.patch(
            f"{_INTAKES}/{it['id']}", json={"note": "Khách rút yêu cầu qua điện thoại"}
        ).status_code == 200

    def test_da_chuyen_lab_thi_khong_doi_ma_phieu(self, client, as_role, department):
        """Mã đã dán lên mẫu vật lý và phòng lab đang cầm nhãn đó."""
        as_role("reception", department_id=department.id)
        it = _intake(client)
        client.post(
            f"{_INTAKES}/{it['id']}/dispatches",
            json={"chi_tieu": "pH", "target_department_id": str(department.id)},
        )
        res = client.patch(f"{_INTAKES}/{it['id']}", json={"code": "NM-KHAC-0001"})
        assert res.status_code == 409, res.text

    def test_audit_luu_ca_gia_tri_truoc(self, client, as_role, department, db):
        """Không có giá trị TRƯỚC thì không tái dựng được hồ sơ lúc in cho khách."""
        from sqlalchemy import text as sa_text

        as_role("reception", department_id=department.id)
        it = _intake(client)
        client.patch(f"{_INTAKES}/{it['id']}", json={"customer_name": "Tên Đã Sửa"})

        row = db.execute(sa_text(
            "SELECT detail FROM audit_logs WHERE action='INTAKE_UPDATE' "
            "AND resource_id = :rid ORDER BY at DESC LIMIT 1"
        ), {"rid": it["id"]}).scalar_one()
        assert row["before"]["customer_name"] == "Cty CP Chế Biến Thuỷ Sản Sao Mai"
        assert row["after"]["customer_name"] == "Tên Đã Sửa"


@requires_db
class TestTraCuuKhachHang:
    def test_tim_duoc_theo_ma_so_thue_va_dien_thoai(self, client, as_role):
        as_role("reception")
        client.post(_CUSTOMERS, json={
            "name": "Cty Tra Cứu", "tax_code": "0312345678", "phone": "0908777666",
        })
        for q in ("0312345678", "0908777666"):
            rows = client.get(_CUSTOMERS, params={"q": q}).json()["data"]
            assert len(rows) == 1, f"tìm theo '{q}' không ra khách"

    def test_canh_bao_trung_ma_so_thue(self, client, as_role):
        as_role("reception")
        client.post(_CUSTOMERS, json={"name": "Cty Gốc", "tax_code": "0399999999"})

        rows = client.get(_CUSTOMERS + "/duplicates", params={
            "name": "Cty Nhập Lại", "tax_code": "0399999999",
        }).json()["data"]
        assert len(rows) == 1
        assert rows[0]["matched_on"] == "tax_code"

    def test_khong_chan_tao_trung(self, client, as_role):
        """Cảnh báo, KHÔNG chặn — Q3 chưa chốt khách là pháp nhân hay địa điểm."""
        as_role("reception")
        client.post(_CUSTOMERS, json={"name": "Nhà máy 1", "tax_code": "0388888888"})
        res = client.post(_CUSTOMERS, json={"name": "Nhà máy 2", "tax_code": "0388888888"})
        assert res.status_code == 201, res.text
