"""m49/m50 — phòng công tác nằm trên HỒ SƠ NHÂN SỰ, và một người có thể KIÊM NHIỆM.

Yêu cầu nghiệp vụ: DANH SÁCH VIÊN CHỨC - NGƯỜI LAO ĐỘNG 2026 có 33 dòng người nhưng
chỉ 32 người — Huỳnh Văn Biết đứng ở cả mục "Ban Lãnh đạo" lẫn mục I "Phòng nghiên cứu
Sinh học Phân tử". Trước m49 phòng ban đọc qua `users.department_id`, mà từ m48 phần
lớn hồ sơ không gắn tài khoản; m49 cho hồ sơ một cột phòng, nhưng cột đơn lại ép người
kiêm nhiệm phải bỏ bớt một phòng.

Hai bất biến được khoá ở đây:
  1. Hiển thị và BỘ LỌC dùng cùng một quy tắc — lệch nhau thì người dùng thấy một người
     ở phòng A nhưng lọc phòng A lại không ra họ.
  2. Tối đa MỘT phòng chính mỗi hồ sơ — báo cáo đếm đầu người theo phòng dựa vào đó để
     tổng các phòng không vượt sĩ số Viện.
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


def _nguoi_co_tai_khoan(db, ten: str, dept_id):
    """Tài khoản + hồ sơ đã gắn, hồ sơ CHƯA xếp phòng — trạng thái của dữ liệu cũ."""
    from app.models.hr import HrProfile
    from app.models.user import User

    u = User(
        email=f"{uuid.uuid4().hex[:8]}@test.local",
        full_name=ten,
        password_hash="$2b$12$" + "x" * 53,
        role="staff",
        status="active",
        department_id=dept_id,
    )
    db.add(u)
    db.flush()
    p = HrProfile(user_id=u.id, full_name=ten, job_title="Nghiên cứu viên")
    db.add(p)
    db.flush()
    return p


class TestHoSoChuaGanTaiKhoanVanCoPhong:
    def test_lap_ho_so_kem_phong(self, client, as_role, department):
        as_role("admin")

        r = _make(client, "Đào Uyên Trân Đa", department_ids=[str(department.id)])

        assert r.status_code == 201, r.text
        d = r.json()["data"]
        assert d["has_account"] is False
        assert d["department_id"] == str(department.id)
        assert d["department_name"] == department.name
        assert [x["id"] for x in d["departments"]] == [str(department.id)]
        assert d["departments"][0]["is_primary"] is True

    def test_loc_theo_phong_tim_ra_ho_so_chua_gan_tai_khoan(
        self, client, as_role, department, phong_khac
    ):
        """Đây là lỗi m49 sửa: lọc trên users.department_id bỏ sót mọi hồ sơ chưa gắn."""
        as_role("admin")
        _make(client, "Vũ Ngọc Khánh Như", department_ids=[str(department.id)])
        _make(client, "Phùng Thị Ngọc Hân", department_ids=[str(phong_khac.id)])

        rows = client.get(
            _HR, params={"department_id": str(department.id), "limit": 100}
        ).json()["data"]

        ten = {p["full_name"] for p in rows}
        assert "Vũ Ngọc Khánh Như" in ten
        assert "Phùng Thị Ngọc Hân" not in ten

    def test_phong_khong_co_that_bi_tu_choi(self, client, as_role):
        """FK cũng chặn, nhưng vi phạm FK nổi lên tầng DB thành 500 — người nhập cần 400."""
        as_role("admin")

        r = _make(client, "Lê Quang Trường", department_ids=[str(uuid.uuid4())])

        assert r.status_code == 400, r.text


class TestKiemNhiem:
    """Huỳnh Văn Biết: Ban Lãnh đạo + phòng Sinh học phân tử."""

    def test_giu_ca_hai_phong_phan_tu_dau_la_chinh(
        self, client, as_role, department, phong_khac
    ):
        as_role("admin")

        r = _make(
            client, "Huỳnh Văn Biết",
            job_title="Giảng viên chính",
            department_ids=[str(department.id), str(phong_khac.id)],
        )

        assert r.status_code == 201, r.text
        d = r.json()["data"]
        assert [x["id"] for x in d["departments"]] == [
            str(department.id), str(phong_khac.id)
        ]
        assert [x["is_primary"] for x in d["departments"]] == [True, False]
        # Chỗ chỉ chứa được một phòng thì kể phòng chính.
        assert d["department_id"] == str(department.id)

    def test_hien_ra_o_CA_HAI_phong_khi_loc(
        self, client, as_role, department, phong_khac
    ):
        """Phòng nghiên cứu mở danh sách nhân sự của mình phải thấy người kiêm nhiệm,
        dù phòng chính của họ là nơi khác."""
        as_role("admin")
        _make(client, "Huỳnh Văn Biết",
              department_ids=[str(department.id), str(phong_khac.id)])

        for d_id in (department.id, phong_khac.id):
            rows = client.get(
                _HR, params={"department_id": str(d_id), "limit": 100}
            ).json()["data"]
            assert "Huỳnh Văn Biết" in {p["full_name"] for p in rows}, d_id

    def test_khong_dem_trung_khi_loc_mot_phong(
        self, client, as_role, department, phong_khac
    ):
        """Hai dòng kiêm nhiệm không được làm hồ sơ hiện hai lần trong cùng một trang."""
        as_role("admin")
        _make(client, "Huỳnh Văn Biết",
              department_ids=[str(department.id), str(phong_khac.id)])

        rows = client.get(
            _HR, params={"department_id": str(department.id), "limit": 100}
        ).json()["data"]

        assert [p["full_name"] for p in rows].count("Huỳnh Văn Biết") == 1

    def test_thay_ca_cum_khi_patch(self, client, as_role, department, phong_khac):
        """Gửi danh sách mới là THAY, không phải thêm — gỡ kiêm nhiệm phải làm được."""
        as_role("admin")
        pid = _make(
            client, "Huỳnh Văn Biết",
            department_ids=[str(department.id), str(phong_khac.id)],
        ).json()["data"]["id"]

        r = client.patch(f"{_HR}/{pid}", json={"department_ids": [str(phong_khac.id)]})

        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert [x["id"] for x in d["departments"]] == [str(phong_khac.id)]
        assert d["departments"][0]["is_primary"] is True

    def test_doi_phong_chinh_khong_vi_pham_rang_buoc(
        self, client, as_role, department, phong_khac
    ):
        """Đảo thứ tự = đổi phòng chính. Nếu không xoá dòng cũ trước khi chèn, chỉ mục
        uq_hrpd_primary sẽ thấy hai phòng chính và lệnh chèn đổ vỡ."""
        as_role("admin")
        pid = _make(
            client, "Huỳnh Văn Biết",
            department_ids=[str(department.id), str(phong_khac.id)],
        ).json()["data"]["id"]

        r = client.patch(
            f"{_HR}/{pid}",
            json={"department_ids": [str(phong_khac.id), str(department.id)]},
        )

        assert r.status_code == 200, r.text
        assert r.json()["data"]["department_id"] == str(phong_khac.id)

    def test_go_het_phong(self, client, as_role, department):
        as_role("admin")
        pid = _make(
            client, "Trần Thị Vân", department_ids=[str(department.id)]
        ).json()["data"]["id"]

        r = client.patch(f"{_HR}/{pid}", json={"department_ids": []})

        assert r.status_code == 200, r.text
        d = r.json()["data"]
        assert d["departments"] == []
        assert d["department_id"] is None


class TestLuiVePhongCuaTaiKhoan:
    def test_ho_so_chua_xep_phong_lay_phong_cua_tai_khoan(
        self, client, as_role, db, department
    ):
        """Hồ sơ lập trước m49 không có phòng riêng — không được mất phòng ban đang hiện."""
        as_role("admin")
        p = _nguoi_co_tai_khoan(db, "Trương Quang Toản", department.id)

        d = client.get(f"{_HR}/{p.id}").json()["data"]

        assert d["department_id"] == str(department.id)
        assert d["department_name"] == department.name

    def test_loc_van_tim_ra_ho_so_chi_co_phong_qua_tai_khoan(
        self, client, as_role, db, department
    ):
        as_role("admin")
        _nguoi_co_tai_khoan(db, "Trương Quang Toản", department.id)

        rows = client.get(
            _HR, params={"department_id": str(department.id), "limit": 100}
        ).json()["data"]

        assert "Trương Quang Toản" in {p["full_name"] for p in rows}

    def test_phong_tren_ho_so_thang_phong_cua_tai_khoan(
        self, client, as_role, db, department, phong_khac
    ):
        """Người được điều sang phòng khác mà tài khoản chưa đổi: hồ sơ nhân sự là
        nguồn cho dữ liệu nhân sự, `users.department_id` chỉ lo phân quyền."""
        as_role("admin")
        p = _nguoi_co_tai_khoan(db, "Đặng Xuân Đài", department.id)
        client.patch(f"{_HR}/{p.id}", json={"department_ids": [str(phong_khac.id)]})

        d = client.get(f"{_HR}/{p.id}").json()["data"]

        assert d["department_id"] == str(phong_khac.id)
