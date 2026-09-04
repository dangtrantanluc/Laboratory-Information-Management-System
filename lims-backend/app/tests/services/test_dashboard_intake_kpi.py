"""m39 — dashboard đếm đúng bảng mà quầy thực sự ghi vào.

LỖI ĐƯỢC CHẶN
`_kpi_samples` đếm bảng `samples` của module M1, còn quầy nhận mẫu ghi vào
`sample_intakes` — hai bảng không có khoá ngoại nào nối nhau. Nên ô KPI của Phòng
nhận mẫu ghi "Phiếu chờ chuyển lab" nhưng lấy số từ `samples`, rồi bấm vào lại dẫn
sang /sample-flow đọc `sample_intakes`. Con số và màn hình đích khác nguồn dữ liệu.

Bất biến kiểm ở đây: TẠO N PHIẾU THÌ KPI PHẢI RA ĐÚNG N. Trước m39 nó ra 0.
"""
from datetime import date, timedelta

from app.tests.conftest import requires_db

_INTAKES = "/api/v1/intakes"
_DASHBOARD = "/api/v1/dashboard"


def _intake(client, **kw) -> dict:
    body = {"customer_name": "Cty Kiểm Số Liệu"}
    body.update(kw)
    res = client.post(_INTAKES, json=body)
    assert res.status_code == 201, res.text
    return res.json()["data"]


def _dash(client) -> dict:
    """Đọc dashboard sau khi XOÁ cache.

    `report_common.cache_key()` băm theo (vai trò, phòng, bộ lọc) chứ KHÔNG theo id
    người dùng, và TTL 60s. Nên trong một test, lần gọi thứ hai sẽ đọc lại số của
    lần thứ nhất, còn giữa các test thì hai vai 'reception' cùng phòng dùng chung
    một khoá. Ở đây ta kiểm phép ĐẾM, không kiểm cache — nên xoá trước mỗi lần đọc.
    """
    from app.core.redis_client import get_redis

    r = get_redis()
    for k in r.scan_iter("report:*"):
        r.delete(k)

    res = client.get(_DASHBOARD)
    assert res.status_code == 200, res.text
    return res.json()["data"]


@requires_db
class TestKpiPhieuNhanMau:
    def test_tao_phieu_thi_kpi_tang(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        assert _dash(client)["intakes"]["total"] == 0

        for _ in range(3):
            _intake(client)

        block = _dash(client)["intakes"]
        assert block["total"] == 3
        assert block["by_status"]["received"] == 3
        assert block["awaiting_dispatch"] == 3

    def test_kpi_phan_biet_voi_khoi_samples_cua_m1(self, client, as_role, department):
        """Hai khối phải TỒN TẠI SONG SONG và đếm khác nhau.

        Gộp chúng dưới một nhãn là cách tạo ra đúng nhầm lẫn mà m39 sinh ra để sửa.
        """
        as_role("reception", department_id=department.id)
        _intake(client)

        data = _dash(client)
        assert data["intakes"]["total"] == 1
        # samples (M1) không được ăn theo — quầy không ghi vào bảng đó.
        assert data["samples"]["total"] == 0

    def test_dem_qua_han_theo_ngay_that(self, client, as_role, department):
        """Quá hạn tính trên due_date_at (kiểu ngày), không phải ô text due_date."""
        as_role("reception", department_id=department.id)
        hom_qua = (date.today() - timedelta(days=3)).strftime("%d/%m/%Y")
        ngay_mai = (date.today() + timedelta(days=3)).strftime("%d/%m/%Y")

        _intake(client, due_date=hom_qua)
        _intake(client, due_date=ngay_mai)
        _intake(client, due_date="cuối tháng 3")  # không phân giải được → không tính

        assert _dash(client)["intakes"]["overdue"] == 1

    def test_phieu_da_dong_khong_con_tinh_qua_han(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        hom_qua = (date.today() - timedelta(days=3)).strftime("%d/%m/%Y")
        it = _intake(client, due_date=hom_qua)
        assert _dash(client)["intakes"]["overdue"] == 1

        client.post(f"{_INTAKES}/{it['id']}/status", json={"status": "cancelled"})
        assert _dash(client)["intakes"]["overdue"] == 0

    def test_sua_ngay_hen_thi_dong_bo_cot_ngay(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _intake(client, due_date="cuối tháng 3")
        assert _dash(client)["intakes"]["overdue"] == 0

        hom_qua = (date.today() - timedelta(days=1)).strftime("%d/%m/%Y")
        assert client.patch(f"{_INTAKES}/{it['id']}", json={"due_date": hom_qua}).status_code == 200
        assert _dash(client)["intakes"]["overdue"] == 1

    def test_giu_nguyen_o_text_da_in_ra_phieu(self, client, as_role, department):
        """`due_date` là bản chụp thứ nhân viên gõ — chuẩn hoá không được ghi đè nó."""
        as_role("reception", department_id=department.id)
        it = _intake(client, due_date="5/3/2026")

        data = client.get(f"{_INTAKES}/{it['id']}").json()["data"]
        assert data["due_date"] == "5/3/2026"
        assert data["due_date_at"] == "2026-03-05"


@requires_db
class TestKpiLuotChuyen:
    def test_hang_doi_theo_phong(self, client, as_role, department, db):
        import uuid as _uuid

        from app.models.department import Department

        as_role("reception", department_id=department.id)
        it = _intake(client)
        phong_b = Department(name="Phòng B", code=_uuid.uuid4().hex[:8])
        db.add(phong_b)
        db.flush()

        for dept_id in (department.id, department.id, phong_b.id):
            client.post(
                f"{_INTAKES}/{it['id']}/dispatches",
                json={"chi_tieu": "pH", "target_department_id": str(dept_id)},
            )

        # KTV phòng A chỉ thấy hàng đợi của phòng mình.
        as_role("staff", department_id=department.id)
        block = _dash(client)["dispatches"]
        assert block["total"] == 2
        assert block["waiting"] == 2

    def test_lab_tiep_nhan_thi_hang_doi_doi(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _intake(client)
        did = client.post(
            f"{_INTAKES}/{it['id']}/dispatches",
            json={"chi_tieu": "pH", "target_department_id": str(department.id)},
        ).json()["data"]["id"]

        as_role("staff", department_id=department.id)
        assert _dash(client)["dispatches"]["waiting"] == 1

        client.patch(f"/api/v1/dispatches/{did}/result", json={"status": "received"})
        block = _dash(client)["dispatches"]
        assert block["waiting"] == 0
        assert block["in_progress"] == 1
