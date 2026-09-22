"""m49 — quản trị viên nhìn thấy và mở được tài khoản bị khoá đăng nhập.

Yêu cầu nghiệp vụ: một tài khoản bị khoá vì nhập sai mật khẩu nhiều lần, và cách duy
nhất để mở là gõ redis-cli trên máy chủ. Tức là việc này nằm NGOÀI phần mềm.

Ba nhóm bất biến:

1. **Nhìn thấy được.** Đang bị khoá, và đang sai liên tiếp nhưng chưa khoá — nhóm thứ
   hai là cảnh báo sớm, 4/5 lần sai trên một email lạ là dấu hiệu dò mật khẩu.
2. **Mở được, và mở cho ĐÚNG người.** Khoá đặt theo cặp (email, IP) nên một người có
   thể bị khoá ở nhiều IP; mở khoá phải quét hết, kèm cả bộ đếm sai — để lại bộ đếm
   thì người vừa được mở chỉ cần sai thêm một lần là khoá lại ngay.
3. **Chỉ Quản trị viên.** Danh sách này tiết lộ email nào đang bị tấn công.
"""
import pytest

from app.core.redis_client import get_redis, login_fail_key, login_lock_key
from app.tests.conftest import requires_db

pytestmark = requires_db

_LOCKOUTS = "/api/v1/users/lockouts"


@pytest.fixture
def redis_sach():
    """Dọn mọi khoá đăng nhập trước và sau mỗi test.

    Cả bộ test dùng CHUNG một Redis, nên khoá sót lại từ test khác sẽ làm phép đếm ở
    đây sai — và sai theo kiểu phụ thuộc thứ tự chạy, loại lỗi khó lần nhất.
    """
    r = get_redis()

    def _wipe():
        for pat in ("login:lock:*", "login:fail:*"):
            for k in list(r.scan_iter(match=pat, count=200)):
                r.delete(k)

    _wipe()
    yield r
    _wipe()


def _khoa(r, email: str, ip: str, seconds: int = 900):
    r.setex(login_lock_key(email, ip), seconds, "1")


def _dem_sai(r, email: str, ip: str, n: int, seconds: int = 900):
    r.setex(login_fail_key(email, ip), seconds, str(n))


class TestNhinThayDuoc:
    def test_liet_ke_tai_khoan_dang_bi_khoa(self, client, as_role, redis_sach, seeded_user):
        as_role("admin")
        u = seeded_user(full_name="Văn phòng", role="office")
        _khoa(redis_sach, str(u.email), "27.65.196.161")

        r = client.get(_LOCKOUTS)

        assert r.status_code == 200, r.text
        locked = r.json()["data"]["locked"]
        assert len(locked) == 1
        assert locked[0]["email"] == str(u.email).lower()
        assert locked[0]["ip"] == "27.65.196.161"
        assert locked[0]["remaining_seconds"] > 0
        assert locked[0]["is_known_account"] is True
        assert locked[0]["full_name"] == "Văn phòng"

    def test_hien_ca_nguoi_dang_sai_nhung_CHUA_khoa(self, client, as_role, redis_sach, seeded_user):
        """Cảnh báo sớm — thấy lúc đang diễn ra thì còn xử lý được."""
        as_role("admin")
        u = seeded_user(full_name="Sắp bị khoá", role="staff")
        _dem_sai(redis_sach, str(u.email), "1.2.3.4", 4)

        d = client.get(_LOCKOUTS).json()["data"]

        assert d["locked"] == []
        assert len(d["failing"]) == 1
        assert d["failing"][0]["failed_attempts"] == 4

    def test_email_khong_co_tai_khoan_van_duoc_liet_ke(self, client, as_role, redis_sach):
        """Đây là dấu hiệu DÒ EMAIL — lọc bỏ đi là giấu mất thứ cần thấy nhất."""
        as_role("admin")
        _khoa(redis_sach, "khong-ton-tai@attacker.test", "9.9.9.9")

        locked = client.get(_LOCKOUTS).json()["data"]["locked"]

        assert len(locked) == 1
        assert locked[0]["is_known_account"] is False
        assert locked[0]["user_id"] is None

    def test_ipv6_khong_bi_cat_nat(self, client, as_role, redis_sach, seeded_user):
        """Khoá là `login:lock:<email>:<ip>`; IPv6 đầy dấu hai chấm nên phải cắt ở dấu
        ĐẦU TIÊN sau tiền tố, không phải dấu cuối."""
        as_role("admin")
        u = seeded_user(full_name="IPv6", role="staff")
        _khoa(redis_sach, str(u.email), "2001:db8::1")

        locked = client.get(_LOCKOUTS).json()["data"]["locked"]

        assert locked[0]["ip"] == "2001:db8::1"
        assert locked[0]["email"] == str(u.email).lower()

    def test_khong_ai_bi_khoa_thi_tra_danh_sach_rong(self, client, as_role, redis_sach):
        as_role("admin")

        d = client.get(_LOCKOUTS).json()["data"]

        assert d == {"locked": [], "failing": []}


class TestMoKhoa:
    def test_mo_khoa_xoa_MOI_ip_cua_tai_khoan(self, client, as_role, redis_sach, seeded_user):
        """Khoá theo cặp (email, IP) nên một người có thể bị khoá ở nhiều IP."""
        as_role("admin")
        u = seeded_user(full_name="Nhiều IP", role="office")
        _khoa(redis_sach, str(u.email), "1.1.1.1")
        _khoa(redis_sach, str(u.email), "2.2.2.2")

        r = client.post(f"/api/v1/users/{u.id}/unlock")

        assert r.status_code == 200, r.text
        assert client.get(_LOCKOUTS).json()["data"]["locked"] == []

    def test_mo_khoa_xoa_luon_bo_dem_sai(self, client, as_role, redis_sach, seeded_user):
        """Để lại bộ đếm thì người vừa được mở chỉ cần sai thêm MỘT lần là khoá lại —
        và họ sẽ tưởng việc mở khoá không có tác dụng."""
        as_role("admin")
        u = seeded_user(full_name="Còn bộ đếm", role="office")
        _khoa(redis_sach, str(u.email), "1.1.1.1")
        _dem_sai(redis_sach, str(u.email), "1.1.1.1", 4)

        client.post(f"/api/v1/users/{u.id}/unlock")

        d = client.get(_LOCKOUTS).json()["data"]
        assert d["locked"] == [] and d["failing"] == []

    def test_khong_dong_cham_tai_khoan_khac(self, client, as_role, redis_sach, seeded_user):
        as_role("admin")
        a = seeded_user(full_name="A", role="office")
        b = seeded_user(full_name="B", role="office")
        _khoa(redis_sach, str(a.email), "1.1.1.1")
        _khoa(redis_sach, str(b.email), "1.1.1.1")

        client.post(f"/api/v1/users/{a.id}/unlock")

        con_lai = client.get(_LOCKOUTS).json()["data"]["locked"]
        assert [x["email"] for x in con_lai] == [str(b.email).lower()]

    def test_mo_khoa_nguoi_khong_bi_khoa_van_ok(self, client, as_role, redis_sach, seeded_user):
        """Thao tác phải bình thản: quản trị viên không biết trước ai đang bị khoá."""
        as_role("admin")
        u = seeded_user(full_name="Bình thường", role="staff")

        r = client.post(f"/api/v1/users/{u.id}/unlock")

        assert r.status_code == 200, r.text
        assert r.json()["data"]["keys_removed"] == 0

    def test_de_lai_vet_kiem_toan(self, client, as_role, redis_sach, seeded_user, audit_rows):
        """Mở khoá là can thiệp vào kiểm soát an toàn — phải truy được ai làm."""
        as_role("admin")
        u = seeded_user(full_name="Có vết", role="office")
        _khoa(redis_sach, str(u.email), "1.1.1.1")
        truoc = audit_rows("ACCOUNT_UNLOCKED")

        client.post(f"/api/v1/users/{u.id}/unlock")

        assert audit_rows("ACCOUNT_UNLOCKED") == truoc + 1

    def test_tai_khoan_khong_ton_tai(self, client, as_role, redis_sach):
        import uuid as _u

        as_role("admin")

        r = client.post(f"/api/v1/users/{_u.uuid4()}/unlock")

        assert r.status_code == 404, r.text


class TestChiQuanTriVien:
    @pytest.mark.parametrize("role", ["office", "leader", "staff", "reception", "qms", "lab_manager"])
    def test_vai_khac_khong_xem_duoc(self, client, as_role, redis_sach, role):
        """Danh sách tiết lộ email nào đang bị tấn công."""
        as_role(role)

        assert client.get(_LOCKOUTS).status_code == 403

    @pytest.mark.parametrize("role", ["office", "leader", "staff"])
    def test_vai_khac_khong_mo_khoa_duoc(self, client, as_role, redis_sach, seeded_user, role):
        u = seeded_user(full_name="X", role="office")
        as_role(role)

        assert client.post(f"/api/v1/users/{u.id}/unlock").status_code == 403


class TestVetKhiBiKhoa:
    def test_bi_khoa_thi_ghi_ACCOUNT_LOCKED(self, client, redis_sach, seeded_user, audit_rows):
        """Trước m49 việc khoá chỉ để lại một khoá Redis có hạn — hết hạn là mất sạch
        dấu vết, không trả lời được "hôm qua ai bị khoá, từ IP nào"."""
        from app.config import settings

        u = seeded_user(full_name="Sẽ bị khoá", role="office")
        truoc = audit_rows("ACCOUNT_LOCKED")

        for _ in range(settings.login_max_failed):
            client.post("/api/v1/auth/login",
                        json={"email": str(u.email), "password": "sai-mat-khau"})

        assert audit_rows("ACCOUNT_LOCKED") == truoc + 1, "phải ghi ĐÚNG MỘT vết khoá"

    def test_dang_nhap_sai_chua_du_nguong_thi_chua_ghi(self, client, redis_sach, seeded_user, audit_rows):
        """Đối trọng: mỗi lần sai không được sinh một vết khoá."""
        from app.config import settings

        u = seeded_user(full_name="Sai ít", role="office")
        truoc = audit_rows("ACCOUNT_LOCKED")

        for _ in range(max(settings.login_max_failed - 1, 1)):
            client.post("/api/v1/auth/login",
                        json={"email": str(u.email), "password": "sai-mat-khau"})

        assert audit_rows("ACCOUNT_LOCKED") == truoc
