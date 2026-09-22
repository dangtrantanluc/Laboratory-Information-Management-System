"""m49 — phòng công tác nằm trên HỒ SƠ NHÂN SỰ, không suy từ tài khoản.

Yêu cầu nghiệp vụ: DANH SÁCH VIÊN CHỨC - NGƯỜI LAO ĐỘNG 2026 xếp từng người vào một
trong 9 phòng nghiên cứu, Ban Lãnh đạo hoặc Bộ phận văn phòng. Trước m49 phòng ban của
hồ sơ đọc qua `users.department_id`, mà từ m48 phần lớn hồ sơ không gắn tài khoản — nên
cả Viện hiện "Chưa có phòng" và bộ lọc theo phòng trả về rỗng.

Bất biến: phòng trên hồ sơ là nguồn đầu tiên; phòng của tài khoản chỉ là đường lùi cho
hồ sơ đã gắn tài khoản từ trước m49 mà chưa kịp xếp phòng. Hiển thị và bộ lọc phải
dùng CÙNG một quy tắc — lệch nhau thì người dùng thấy một người ở phòng A nhưng lọc
phòng A lại không ra họ.
"""
import uuid

import pytest

from app.tests.conftest import requires_db

pytestmark = requires_db

_HR = "/api/v1/hr-profiles"


@pytest.fixture
def phong_khac(db):
    """Phòng thứ hai — để phân biệt "lọc đúng phòng" với "lọc gì cũng ra"."""
    from app.models.department import Department

    d = Department(name=f"Phòng Vi sinh {uuid.uuid4().hex[:6]}", code=uuid.uuid4().hex[:8])
    db.add(d)
    db.flush()
    return d


def _make(client, full_name: str, **kw):
    body = {"full_name": full_name, "job_title": kw.pop("job_title", "Nghiên cứu viên"), **kw}
    return client.post(_HR, json=body)


class TestHoSoChuaGanTaiKhoanVanCoPhong:
    def test_lap_ho_so_kem_phong(self, client, as_role, department):
        as_role("admin")

        r = _make(client, "Đào Uyên Trân Đa", department_id=str(department.id))

        assert r.status_code == 201, r.text
        d = r.json()["data"]
        assert d["has_account"] is False
        assert d["department_id"] == str(department.id)
        assert d["department_name"] == department.name

    def test_loc_theo_phong_tim_ra_ho_so_chua_gan_tai_khoan(
        self, client, as_role, department, phong_khac
    ):
        """Đây là lỗi m49 sửa: lọc trên users.department_id bỏ sót mọi hồ sơ chưa gắn."""
        as_role("admin")
        _make(client, "Vũ Ngọc Khánh Như", department_id=str(department.id))
        _make(client, "Phùng Thị Ngọc Hân", department_id=str(phong_khac.id))

        rows = client.get(
            _HR, params={"department_id": str(department.id), "limit": 100}
        ).json()["data"]

        ten = {p["full_name"] for p in rows}
        assert "Vũ Ngọc Khánh Như" in ten
        assert "Phùng Thị Ngọc Hân" not in ten

    def test_doi_phong_qua_patch(self, client, as_role, department, phong_khac):
        as_role("admin")
        pid = _make(client, "Trần Thị Vân", department_id=str(department.id)).json()["data"]["id"]

        r = client.patch(f"{_HR}/{pid}", json={"department_id": str(phong_khac.id)})

        assert r.status_code == 200, r.text
        assert r.json()["data"]["department_id"] == str(phong_khac.id)

    def test_phong_khong_co_that_bi_tu_choi(self, client, as_role):
        """FK cũng chặn, nhưng lỗi FK nổi lên tầng DB thành 500 — người nhập cần 400."""
        as_role("admin")

        r = _make(client, "Lê Quang Trường", department_id=str(uuid.uuid4()))

        assert r.status_code == 400, r.text


class TestLuiVePhongCuaTaiKhoan:
    def test_ho_so_gan_tai_khoan_chua_xep_phong_lay_phong_cua_tai_khoan(
        self, client, as_role, db, department
    ):
        """Hồ sơ lập trước m49 không có phòng riêng — không được mất phòng ban đang hiện.

        Dựng đúng trạng thái sau migration: tài khoản có phòng, hồ sơ gắn tài khoản đó
        nhưng cột `department_id` của hồ sơ để trống.
        """
        from app.models.hr import HrProfile
        from app.models.user import User

        as_role("admin")
        nguoi = User(
            email=f"toan-{uuid.uuid4().hex[:8]}@test.local",
            full_name="Trương Quang Toản",
            password_hash="$2b$12$" + "x" * 53,
            role="staff",
            status="active",
            department_id=department.id,
        )
        db.add(nguoi)
        db.flush()
        ho_so = HrProfile(
            user_id=nguoi.id,
            full_name="Trương Quang Toản",
            job_title="Nghiên cứu viên",
            department_id=None,
        )
        db.add(ho_so)
        db.flush()

        d = client.get(f"{_HR}/{ho_so.id}").json()["data"]

        assert d["department_id"] == str(department.id)
        assert d["department_name"] == department.name

    def test_phong_tren_ho_so_thang_phong_cua_tai_khoan(
        self, client, as_role, db, department, phong_khac
    ):
        """Người được điều sang phòng khác mà tài khoản chưa đổi: hồ sơ nhân sự là
        nguồn cho dữ liệu nhân sự, `users.department_id` chỉ lo phân quyền."""
        from app.models.hr import HrProfile
        from app.models.user import User

        as_role("admin")
        nguoi = User(
            email=f"dai-{uuid.uuid4().hex[:8]}@test.local",
            full_name="Đặng Xuân Đài",
            password_hash="$2b$12$" + "x" * 53,
            role="staff",
            status="active",
            department_id=department.id,
        )
        db.add(nguoi)
        db.flush()
        ho_so = HrProfile(
            user_id=nguoi.id,
            full_name="Đặng Xuân Đài",
            job_title="Nghiên cứu viên",
            department_id=phong_khac.id,
        )
        db.add(ho_so)
        db.flush()

        d = client.get(f"{_HR}/{ho_so.id}").json()["data"]

        assert d["department_id"] == str(phong_khac.id)
