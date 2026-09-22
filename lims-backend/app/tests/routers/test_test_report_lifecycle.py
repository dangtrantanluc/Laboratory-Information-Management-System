"""Vòng đời PHIẾU KẾT QUẢ THỬ NGHIỆM (m46) — BM 7.8/01/RIBE.

Bộ test này canh giữ ba thứ, theo thứ tự quan trọng:

1. **Phát hành xong là bất biến.** Nếu tệp và siêu dữ liệu vẫn sửa được sau khi
   `issued`, cả module chỉ còn là một thư mục chia sẻ có thêm vài ô nhập — mọi giá trị
   pháp lý của chứng từ nằm ở chỗ nó không đổi được sau khi trao cho khách.
2. **"Đã trả kết quả" phải có chứng từ (BR-08).** Trước m46 bước đó chỉ ghi một chuỗi
   ký tự vào cột `status`; test này khoá lại để nó không tụt về như cũ.
3. **Bản sửa đổi không viết đè bản cũ.** Khách đang cầm bản cũ trên tay.

Không đụng MinIO: `put_object` được thay bằng no-op. Mọi khẳng định ở đây thuộc tầng
nghiệp vụ, không phải tầng lưu trữ.
"""
from datetime import date

import pytest

from app.tests.conftest import requires_db

pytestmark = requires_db

_INTAKES = "/api/v1/intakes"
_REPORTS = "/api/v1/test-reports"

_PDF = ("kq.pdf", b"%PDF-1.4 fake", "application/pdf")
_XLSX = (
    "bang.xlsx",
    b"PK fake",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)


@pytest.fixture(autouse=True)
def _no_minio(monkeypatch):
    monkeypatch.setattr(
        "app.services.storage_service.put_object", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        "app.services.storage_service.presigned_get_url",
        lambda *a, **kw: "https://minio.test/signed",
    )


@pytest.fixture
def intake(client, as_role):
    """Phiếu nhận mẫu thật, tạo qua API để đi đúng đường sinh mã + audit."""
    as_role("reception")
    r = client.post(
        _INTAKES,
        json={"customer_name": "Công ty CP Đầu tư Xây dựng Nhân Ái", "code": "26N323"},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _create(client, intake_id, **body):
    return client.post(f"{_INTAKES}/{intake_id}/test-reports", json=body)


def _upload(client, report_id, file=_PDF):
    return client.post(f"{_REPORTS}/{report_id}/files", files={"file": file})


def _ready_report(client, intake_id, **body):
    """Bản nháp đã có tệp — sẵn sàng phát hành."""
    r = _create(client, intake_id, **body)
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert _upload(client, data["id"]).status_code == 201
    return data


class TestSoHieuPhieu:
    def test_mac_dinh_lay_ma_phieu_nhan(self, client, as_role, intake):
        """Header biểu mẫu ghi "Mã KH/Customer code: 26N323" — đúng mã phiếu nhận."""
        as_role("reception")

        r = _create(client, intake["id"])

        assert r.status_code == 201, r.text
        assert r.json()["data"]["report_no"] == "26N323"

    def test_phieu_song_song_duoc_so_ke_tiep(self, client, as_role, intake):
        """Tách phiếu theo hộ là việc có thật — đụng số hiệu không phải lỗi."""
        as_role("reception")
        _create(client, intake["id"])

        r = _create(client, intake["id"])

        assert r.status_code == 201, r.text
        assert r.json()["data"]["report_no"] == "26N323-2"

    def test_so_hieu_trung_tay_bi_tu_choi_409(self, client, as_role, intake):
        as_role("reception")
        _create(client, intake["id"])

        r = _create(client, intake["id"], report_no="26N323")

        # 409 chứ không phải 500: kiểm ở service để người dùng nhận thông báo nghiệp
        # vụ, thay vì để uq_tr_report_no nổ IntegrityError.
        assert r.status_code == 409, r.text


class TestPhatHanh:
    def test_khong_co_tep_thi_khong_phat_hanh_duoc(self, client, as_role, intake):
        as_role("reception")
        rep = _create(client, intake["id"]).json()["data"]

        r = client.post(f"{_REPORTS}/{rep['id']}/issue", json={})

        assert r.status_code == 422, r.text

    def test_tu_choi_dinh_dang_ngoai_pdf_word(self, client, as_role, intake):
        """Allowlist RIÊNG của module — không thừa hưởng allowlist nền tảng."""
        as_role("reception")
        rep = _create(client, intake["id"]).json()["data"]

        r = _upload(client, rep["id"], file=_XLSX)

        assert r.status_code == 422, r.text
        assert r.json()["error"]["code"] == "INVALID_FILE_TYPE"

    def test_nhan_ca_pdf_lan_docx(self, client, as_role, intake):
        """Q3 đã chốt: nhận cả Word, vì Viện soạn phiếu trong Word."""
        as_role("reception")
        rep = _create(client, intake["id"]).json()["data"]

        r = _upload(
            client, rep["id"],
            file=("kq.docx", b"PK fake",
                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        )

        assert r.status_code == 201, r.text

    def test_phat_hanh_ghi_nguoi_va_ngay(self, client, as_role, intake):
        as_role("reception")
        rep = _ready_report(client, intake["id"])
        # Phiếu được nhận HÔM NAY, và BR-11 cấm ngày trên giấy tờ sớm hơn ngày nhận
        # mẫu — nên mốc hợp lệ gần nhất là hôm nay, không phải một ngày cố định.
        hom_nay = date.today().isoformat()

        r = client.post(f"{_REPORTS}/{rep['id']}/issue", json={"issued_at": hom_nay})

        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["status"] == "issued"
        assert data["issued_at"] == hom_nay
        assert data["issued_by_name"] is not None

    def test_bo_trong_ngay_thi_lay_hom_nay(self, client, as_role, intake):
        as_role("reception")
        rep = _ready_report(client, intake["id"])

        r = client.post(f"{_REPORTS}/{rep['id']}/issue", json={})

        assert r.status_code == 200, r.text
        assert r.json()["data"]["issued_at"] == date.today().isoformat()

    def test_ngay_phat_hanh_truoc_ngay_nhan_mau_bi_tu_choi(self, client, as_role, intake):
        """BR-11 — một ngày trên giấy tờ không thể sớm hơn ngày nhận mẫu."""
        as_role("reception")
        rep = _ready_report(client, intake["id"])

        r = client.post(f"{_REPORTS}/{rep['id']}/issue", json={"issued_at": "2020-01-01"})

        assert r.status_code == 422, r.text


class TestBatBienSauPhatHanh:
    """BR-06 — thứ làm nên giá trị của cả module."""

    @pytest.fixture
    def issued(self, client, as_role, intake):
        as_role("reception")
        rep = _ready_report(client, intake["id"])
        assert client.post(f"{_REPORTS}/{rep['id']}/issue", json={}).status_code == 200
        return rep

    def test_khong_sua_duoc_sieu_du_lieu(self, client, issued):
        r = client.patch(f"{_REPORTS}/{issued['id']}", json={"note": "sửa lén"})

        assert r.status_code == 422, r.text
        assert r.json()["error"]["code"] == "RESULT_LOCKED"

    def test_khong_gan_them_tep_duoc(self, client, issued):
        r = _upload(client, issued["id"])

        assert r.status_code == 422, r.text
        assert r.json()["error"]["code"] == "RESULT_LOCKED"

    def test_khong_go_tep_duoc(self, client, issued):
        files = client.get(f"{_REPORTS}/{issued['id']}").json()["data"]["files"]

        r = client.delete(f"{_REPORTS}/{issued['id']}/files/{files[0]['id']}")

        assert r.status_code == 422, r.text

    def test_khong_xoa_duoc_ma_phai_thu_hoi(self, client, issued):
        r = client.delete(f"{_REPORTS}/{issued['id']}")

        assert r.status_code == 422, r.text

    def test_ban_nhap_thi_van_sua_duoc(self, client, as_role, intake):
        """Đối trọng: bản vá không được chặn nhầm việc sửa bản nháp."""
        as_role("reception")
        rep = _create(client, intake["id"]).json()["data"]

        r = client.patch(f"{_REPORTS}/{rep['id']}", json={"note": "ghi chú"})

        assert r.status_code == 200, r.text
        assert r.json()["data"]["note"] == "ghi chú"


class TestStateMachine:
    def test_nhap_khong_nhay_thang_sang_da_gui(self, client, as_role, intake):
        as_role("reception")
        rep = _ready_report(client, intake["id"])

        r = client.post(
            f"{_REPORTS}/{rep['id']}/deliver", json={"delivery_method": "email"}
        )

        assert r.status_code == 409, r.text
        assert r.json()["error"]["code"] == "INVALID_TRANSITION"

    def test_nhap_khong_thu_hoi_duoc(self, client, as_role, intake):
        """Chưa phát hành thì không có gì để thu hồi — bản nháp sai thì xoá."""
        as_role("reception")
        rep = _create(client, intake["id"]).json()["data"]

        r = client.post(f"{_REPORTS}/{rep['id']}/revoke", json={"reason": "sai"})

        assert r.status_code == 409, r.text

    def test_da_thu_hoi_la_diem_dung(self, client, as_role, intake):
        as_role("reception")
        rep = _ready_report(client, intake["id"])
        client.post(f"{_REPORTS}/{rep['id']}/issue", json={})
        client.post(f"{_REPORTS}/{rep['id']}/revoke", json={"reason": "sai đơn vị đo"})

        r = client.post(
            f"{_REPORTS}/{rep['id']}/deliver", json={"delivery_method": "direct"}
        )

        assert r.status_code == 409, r.text

    def test_ghi_nhan_da_gui_khach(self, client, as_role, intake):
        as_role("reception")
        rep = _ready_report(client, intake["id"])
        client.post(f"{_REPORTS}/{rep['id']}/issue", json={})

        r = client.post(
            f"{_REPORTS}/{rep['id']}/deliver",
            json={"delivery_method": "email", "delivered_to": "Chị Hoa"},
        )

        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["status"] == "delivered"
        assert data["delivered_to"] == "Chị Hoa"
        assert data["delivered_at"] is not None


class TestBanSuaDoi:
    @pytest.fixture
    def issued(self, client, as_role, intake):
        as_role("reception")
        rep = _ready_report(client, intake["id"])
        assert client.post(f"{_REPORTS}/{rep['id']}/issue", json={}).status_code == 200
        return rep

    def test_sinh_ban_ghi_moi_khong_viet_de(self, client, issued):
        r = client.post(
            f"{_REPORTS}/{issued['id']}/revisions", json={"reason": "Sai đơn vị Clorua"}
        )

        assert r.status_code == 201, r.text
        new = r.json()["data"]
        assert new["id"] != issued["id"]
        assert new["version"] == 2
        assert new["report_no"] == "26N323-R1"
        assert new["supersedes_report_no"] == "26N323"
        assert new["status"] == "draft"

    def test_ban_cu_chuyen_thu_hoi_va_van_doc_duoc(self, client, issued):
        """Bản cũ phải còn nguyên hiện vật — khách đang cầm nó."""
        client.post(f"{_REPORTS}/{issued['id']}/revisions", json={"reason": "Sai đơn vị"})

        old = client.get(f"{_REPORTS}/{issued['id']}").json()["data"]
        assert old["status"] == "revoked"
        assert "26N323-R1" in (old["revoked_reason"] or "")
        assert len(old["files"]) == 1

    def test_tep_khong_duoc_sao_chep_sang_ban_moi(self, client, issued):
        """Phải tải tệp ĐÃ SỬA lên — đó là điều duy nhất bảo đảm bản mới thật sự mới."""
        new = client.post(
            f"{_REPORTS}/{issued['id']}/revisions", json={"reason": "Sai đơn vị"}
        ).json()["data"]

        assert new["files"] == []
        assert client.post(f"{_REPORTS}/{new['id']}/issue", json={}).status_code == 422

    def test_sua_cua_ban_sua_khong_chong_hau_to(self, client, issued):
        new = client.post(
            f"{_REPORTS}/{issued['id']}/revisions", json={"reason": "lần 1"}
        ).json()["data"]
        _upload(client, new["id"])
        client.post(f"{_REPORTS}/{new['id']}/issue", json={})

        r2 = client.post(f"{_REPORTS}/{new['id']}/revisions", json={"reason": "lần 2"})

        assert r2.status_code == 201, r2.text
        # "26N323-R2", KHÔNG phải "26N323-R1-R2".
        assert r2.json()["data"]["report_no"] == "26N323-R2"

    def test_ban_nhap_thi_sua_truc_tiep_khong_tao_ban_sua_doi(
        self, client, as_role, intake
    ):
        as_role("reception")
        rep = _create(client, intake["id"]).json()["data"]

        r = client.post(f"{_REPORTS}/{rep['id']}/revisions", json={"reason": "x"})

        assert r.status_code == 422, r.text


class TestBR08ChanTraKetQuaKhongChungTu:
    """"Đã trả kết quả" phải là một sự kiện có chứng từ, không phải một cái nhãn."""

    def _to_dispatched(self, client, intake_id):
        r = client.post(f"{_INTAKES}/{intake_id}/status", json={"status": "dispatched"})
        assert r.status_code == 200, r.text

    def test_chua_phat_hanh_thi_khong_completed_duoc(self, client, as_role, intake):
        as_role("reception")
        self._to_dispatched(client, intake["id"])

        r = client.post(f"{_INTAKES}/{intake['id']}/status", json={"status": "completed"})

        assert r.status_code == 409, r.text
        assert "phiếu kết quả" in r.json()["error"]["message"].lower()

    def test_ban_nhap_chua_du_dieu_kien(self, client, as_role, intake):
        """Nháp không tính — chứng từ chưa phát hành thì chưa trao cho ai."""
        as_role("reception")
        _ready_report(client, intake["id"])
        self._to_dispatched(client, intake["id"])

        r = client.post(f"{_INTAKES}/{intake['id']}/status", json={"status": "completed"})

        assert r.status_code == 409, r.text

    def test_da_phat_hanh_thi_di_qua_duoc(self, client, as_role, intake):
        as_role("reception")
        rep = _ready_report(client, intake["id"])
        client.post(f"{_REPORTS}/{rep['id']}/issue", json={})
        self._to_dispatched(client, intake["id"])

        r = client.post(f"{_INTAKES}/{intake['id']}/status", json={"status": "completed"})

        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "completed"

    def test_chung_tu_da_thu_hoi_khong_tinh(self, client, as_role, intake):
        """Thu hồi nghĩa là kết quả chưa được trao hợp lệ."""
        as_role("reception")
        rep = _ready_report(client, intake["id"])
        client.post(f"{_REPORTS}/{rep['id']}/issue", json={})
        client.post(f"{_REPORTS}/{rep['id']}/revoke", json={"reason": "sai kết quả pH"})
        self._to_dispatched(client, intake["id"])

        r = client.post(f"{_INTAKES}/{intake['id']}/status", json={"status": "completed"})

        assert r.status_code == 409, r.text

    def test_co_badge_tren_phieu_de_nhin_so_la_biet(self, client, as_role, intake):
        as_role("reception")
        truoc = client.get(f"{_INTAKES}/{intake['id']}").json()["data"]
        assert truoc["has_test_report"] is False

        rep = _ready_report(client, intake["id"])
        client.post(f"{_REPORTS}/{rep['id']}/issue", json={})

        sau = client.get(f"{_INTAKES}/{intake['id']}").json()["data"]
        assert sau["has_test_report"] is True


class TestVetKiemToan:
    def test_moi_luot_tai_ve_deu_de_lai_vet(self, client, as_role, intake, audit_rows):
        """BR-13 — đây là hồ sơ khách hàng; phải biết ai đã lấy nó ra khỏi hệ thống.

        Cũng là nguồn để `revoke` biết phải báo cho ai: người đã tải bản sai về có thể
        đã gửi nó cho khách rồi.
        """
        as_role("reception")
        rep = _ready_report(client, intake["id"])
        file_id = client.get(f"{_REPORTS}/{rep['id']}").json()["data"]["files"][0]["id"]
        truoc = audit_rows("TEST_REPORT_DOWNLOAD")

        r = client.get(f"{_REPORTS}/{rep['id']}/files/{file_id}")

        assert r.status_code == 200, r.text
        assert r.json()["data"]["download_url"]
        assert audit_rows("TEST_REPORT_DOWNLOAD") == truoc + 1

    def test_phat_hanh_ghi_audit(self, client, as_role, intake, audit_rows):
        as_role("reception")
        rep = _ready_report(client, intake["id"])
        truoc = audit_rows("TEST_REPORT_ISSUE")

        client.post(f"{_REPORTS}/{rep['id']}/issue", json={})

        assert audit_rows("TEST_REPORT_ISSUE") == truoc + 1


class TestXoaMem:
    def test_xoa_ban_nhap_tra_lai_so_hieu(self, client, as_role, intake):
        """Partial unique index — gõ nhầm một lần không được mất số hiệu vĩnh viễn."""
        as_role("reception")
        rep = _create(client, intake["id"]).json()["data"]

        assert client.delete(f"{_REPORTS}/{rep['id']}").status_code == 200
        lai = _create(client, intake["id"])

        assert lai.status_code == 201, lai.text
        assert lai.json()["data"]["report_no"] == "26N323"

    def test_ban_da_xoa_khong_con_trong_danh_sach(self, client, as_role, intake):
        as_role("reception")
        rep = _create(client, intake["id"]).json()["data"]
        client.delete(f"{_REPORTS}/{rep['id']}")

        rows = client.get(f"{_INTAKES}/{intake['id']}/test-reports").json()["data"]

        assert rows == []
