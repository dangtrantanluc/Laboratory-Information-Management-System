"""m48 — hồ sơ nhân sự đứng độc lập với tài khoản đăng nhập.

Yêu cầu nghiệp vụ: "import data nhân sự lên chưa cần tạo tài khoản… nếu người đó tạo
tài khoản lần sau thì xử lý thế nào, và có thể người mới chưa có tài khoản và chưa có
trên list nhân sự này."

Ba tình huống đó là ba nhóm test dưới đây. Bất biến xuyên suốt: **một hồ sơ ↔ tối đa
một tài khoản, và việc gắn luôn do người xác nhận** — không bao giờ suy tự động theo
tên, vì trùng họ tên là chuyện bình thường và gắn nhầm sẽ nối hồ sơ lương của người
này vào tài khoản người khác.
"""
import uuid

import pytest

from app.tests.conftest import requires_db

pytestmark = requires_db

_HR = "/api/v1/hr-profiles"


def _make(client, full_name: str, **kw):
    body = {"full_name": full_name, "job_title": kw.pop("job_title", "Nghiên cứu viên"), **kw}
    return client.post(_HR, json=body)


class TestKhongCanTaiKhoan:
    """Tình huống 3: người mới, chưa có tài khoản, chưa có trong danh sách."""

    def test_lap_duoc_ho_so_khong_kem_tai_khoan(self, client, as_role):
        as_role("admin")

        r = _make(client, "Nguyễn Thị Thúy", birth_year=1969, job_title="Nhân viên phục vụ")

        assert r.status_code == 201, r.text
        d = r.json()["data"]
        assert d["user_id"] is None
        assert d["has_account"] is False
        assert d["full_name"] == "Nguyễn Thị Thúy"
        assert d["birth_year"] == 1969

    def test_nhieu_ho_so_chua_gan_cung_ton_tai(self, client, as_role):
        """UNIQUE trên user_id cho phép nhiều NULL — nếu không, người thứ hai sẽ bị chặn."""
        as_role("admin")

        a = _make(client, "Trần Phước Hên")
        b = _make(client, "Trần Thị Thanh Lịch")

        assert (a.status_code, b.status_code) == (201, 201), (a.text, b.text)

    def test_ho_so_chua_gan_van_hien_trong_danh_sach(self, client, as_role):
        """LEFT JOIN, không phải INNER: inner join sẽ lặng lẽ giấu 27/33 người."""
        as_role("admin")
        _make(client, "Vũ Đình Anh Tuấn", birth_year=2002)

        rows = client.get(_HR, params={"limit": 100}).json()["data"]

        assert "Vũ Đình Anh Tuấn" in {p["full_name"] for p in rows}

    def test_tim_theo_ten_tren_ho_so(self, client, as_role):
        as_role("admin")
        _make(client, "Phùng Thị Ngọc Hân")

        rows = client.get(_HR, params={"q": "Ngọc Hân"}).json()["data"]

        assert [p["full_name"] for p in rows] == ["Phùng Thị Ngọc Hân"]

    def test_thieu_ten_bi_tu_choi(self, client, as_role):
        as_role("admin")

        r = client.post(_HR, json={"job_title": "NCV"})

        assert r.status_code == 400, r.text


class TestGanTaiKhoanSauKhiDaCoHoSo:
    """Tình huống 1 — phổ biến nhất với danh sách CBVC 2026."""

    @pytest.fixture
    def ho_so(self, client, as_role):
        as_role("admin")
        r = _make(client, "Lê Quang Trường", birth_year=2001)
        assert r.status_code == 201, r.text
        return r.json()["data"]

    def test_goi_y_ho_so_trung_ten_khi_co_tai_khoan_moi(self, client, as_role, ho_so, seeded_user):
        u = seeded_user(full_name="Lê Quang Trường", role="staff")

        r = client.get(f"/api/v1/users/{u.id}/profile-suggestions")

        assert r.status_code == 200, r.text
        assert [s["id"] for s in r.json()["data"]] == [ho_so["id"]]

    def test_chi_goi_y_ho_so_CHUA_gan(self, client, as_role, ho_so, seeded_user):
        """Hồ sơ đã gắn rồi thì không còn là ứng viên — tránh gợi ý gỡ nhầm."""
        u1 = seeded_user(full_name="Lê Quang Trường", role="staff")
        client.post(f"{_HR}/{ho_so['id']}/link", json={"user_id": str(u1.id)})
        u2 = seeded_user(full_name="Lê Quang Trường", role="staff")

        r = client.get(f"/api/v1/users/{u2.id}/profile-suggestions")

        assert r.json()["data"] == []

    def test_khong_tu_dong_gan(self, client, as_role, ho_so, seeded_user):
        """Bất biến quan trọng nhất: gợi ý KHÔNG phải là gắn."""
        seeded_user(full_name="Lê Quang Trường", role="staff")

        d = client.get(f"{_HR}/{ho_so['id']}").json()["data"]

        assert d["user_id"] is None, "trùng tên không được tự nối hồ sơ vào tài khoản"

    def test_gan_xong_thi_ho_so_co_email_va_phong_ban(self, client, as_role, ho_so, seeded_user):
        u = seeded_user(full_name="Lê Quang Trường", role="staff")

        r = client.post(f"{_HR}/{ho_so['id']}/link", json={"user_id": str(u.id)})

        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["has_account"] is True
        assert d["user_id"] == str(u.id)
        assert d["email"] == u.email

    def test_mot_tai_khoan_khong_gan_hai_ho_so(self, client, as_role, ho_so, seeded_user):
        u = seeded_user(full_name="Lê Quang Trường", role="staff")
        client.post(f"{_HR}/{ho_so['id']}/link", json={"user_id": str(u.id)})
        khac = _make(client, "Người Khác").json()["data"]

        r = client.post(f"{_HR}/{khac['id']}/link", json={"user_id": str(u.id)})

        assert r.status_code == 409, r.text

    def test_ho_so_da_gan_thi_khong_gan_de(self, client, as_role, ho_so, seeded_user):
        u1 = seeded_user(full_name="A", role="staff")
        u2 = seeded_user(full_name="B", role="staff")
        client.post(f"{_HR}/{ho_so['id']}/link", json={"user_id": str(u1.id)})

        r = client.post(f"{_HR}/{ho_so['id']}/link", json={"user_id": str(u2.id)})

        assert r.status_code == 409, r.text

    def test_go_lien_ket_thi_ho_so_O_LAI_so_nhan_su(self, client, as_role, ho_so, seeded_user):
        """Gỡ tài khoản ≠ nghỉ việc. Người vẫn làm ở Viện."""
        u = seeded_user(full_name="Lê Quang Trường", role="staff")
        client.post(f"{_HR}/{ho_so['id']}/link", json={"user_id": str(u.id)})

        r = client.post(f"{_HR}/{ho_so['id']}/unlink")

        assert r.status_code == 200, r.text
        assert r.json()["data"]["user_id"] is None
        assert client.get(f"{_HR}/{ho_so['id']}").status_code == 200

    def test_gan_tai_khoan_khong_ton_tai(self, client, as_role, ho_so):
        r = client.post(f"{_HR}/{ho_so['id']}/link", json={"user_id": str(uuid.uuid4())})

        assert r.status_code == 404, r.text


class TestCoTaiKhoanTruoc:
    """Tình huống 2: tài khoản có trước, hồ sơ lập sau và gắn ngay."""

    def test_lap_ho_so_gan_luon_tai_khoan(self, client, as_role, seeded_user):
        as_role("admin")
        u = seeded_user(full_name="Đặng Xuân Đài", role="staff")

        r = _make(client, "Đặng Xuân Đài", user_id=str(u.id), birth_year=2000)

        assert r.status_code == 201, r.text
        assert r.json()["data"]["user_id"] == str(u.id)

    def test_tai_khoan_da_co_ho_so_thi_bi_chan(self, client, as_role, seeded_user):
        as_role("admin")
        u = seeded_user(full_name="Trùng", role="staff")
        _make(client, "Trùng", user_id=str(u.id))

        r = _make(client, "Trùng lần hai", user_id=str(u.id))

        assert r.status_code == 409, r.text


class TestQuyenXem:
    """Quyền của KTV bám theo TÀI KHOẢN ĐÃ GẮN của hồ sơ.

    Trước m48 khoá hồ sơ trùng với id người dùng nên phép so `user.id != profile_id`
    vừa đủ. Nay khoá hồ sơ là id riêng — so thẳng như cũ thì KTV nào cũng trượt, kể cả
    hồ sơ của chính mình.
    """

    def test_ktv_xem_duoc_ho_so_cua_chinh_minh(self, client, as_role, seeded_user):
        """Đây là hồi quy trực tiếp của m48, nên phải đăng nhập ĐÚNG bằng tài khoản
        đã gắn — `as_role` luôn tạo người mới, nên tự dựng CurrentUser cho user đó."""
        from app.core.deps import CurrentUser, get_current_user
        from app.main import app

        as_role("admin")
        ktv = seeded_user(full_name="KTV A", role="staff")
        cua_minh = _make(client, "KTV A", user_id=str(ktv.id)).json()["data"]

        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=ktv.id, email=str(ktv.email), full_name=ktv.full_name, role="staff",
            department_id=None, is_dept_lead=False, is_quality_manager=False,
            status="active", jti="t", token_exp=9_999_999_999,
        )
        r = client.get(f"{_HR}/{cua_minh['id']}")

        assert r.status_code == 200, r.text
        assert r.json()["data"]["user_id"] == str(ktv.id)

    def test_ktv_khong_xem_duoc_ho_so_nguoi_khac(self, client, as_role):
        as_role("admin")
        cua_nguoi_khac = _make(client, "KTV B").json()["data"]

        as_role("staff")                             # KTV chưa gắn hồ sơ nào
        r = client.get(f"{_HR}/{cua_nguoi_khac['id']}")

        assert r.status_code == 403, r.text
