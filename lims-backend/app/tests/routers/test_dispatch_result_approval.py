"""m40 — kết quả của luồng nhận mẫu đi qua cơ chế DUYỆT bất biến của M1.

TRƯỚC m40
`sample_dispatches.ket_qua` là cột Text sửa tự do: không phiên bản, không người
duyệt, không lý do sửa. Kết quả đã trả cho khách vẫn viết đè được và nhật ký chỉ
lưu giá trị MỚI — không tái dựng được nội dung đã phát hành.

BA BẤT BIẾN KIỂM Ở ĐÂY
1. Người duyệt ≠ người nhập (`test_nguoi_nhap_khong_tu_duyet_duoc`).
2. Duyệt xong thì cột kết quả trên phiếu KHOÁ (`test_duyet_xong_thi_khoa_o_ket_qua`).
3. Sửa sau khi duyệt sinh phiên bản mới có lý do, bản cũ đọc lại nguyên vẹn
   (`test_sua_sau_duyet_sinh_phien_ban_moi`).
"""
from datetime import date, timedelta

from app.core.error_codes import ErrorCode
from app.tests.conftest import requires_db

_INTAKES = "/api/v1/intakes"
_DISPATCHES = "/api/v1/dispatches"
_RESULTS = "/api/v1/results"


def _setup(client, as_role, department, *, due_days: int = 7) -> str:
    """Phiếu + 1 chỉ tiêu chuyển tới `department`, có ngày hẹn trả. Trả dispatch id."""
    as_role("reception", department_id=department.id)
    hen = (date.today() + timedelta(days=due_days)).strftime("%d/%m/%Y")
    it = client.post(
        _INTAKES, json={"customer_name": "Cty Duyệt Kết Quả", "due_date": hen}
    ).json()["data"]
    res = client.post(
        f"{_INTAKES}/{it['id']}/dispatches",
        json={"chi_tieu": "Hàm lượng Nitơ tổng số", "target_department_id": str(department.id)},
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


def _relogin(cu):
    """Đăng nhập lại ĐÚNG tài khoản đó.

    `as_role` tạo một user MỚI mỗi lần gọi, nên "quay lại vai KTV" bằng as_role sẽ
    là một người khác — và `revise_result` phân biệt chủ sở hữu kết quả theo id.
    """
    from app.core.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: cu


def _nhap_va_gui_duyet(client, did: str) -> dict:
    assert client.patch(
        f"{_DISPATCHES}/{did}/result", json={"status": "received"}
    ).status_code == 200
    assert client.patch(
        f"{_DISPATCHES}/{did}/result", json={"ket_qua": "1,82 %"}
    ).status_code == 200
    res = client.post(f"{_DISPATCHES}/{did}/result/submit", json={})
    assert res.status_code == 201, res.text
    return res.json()["data"]


@requires_db
class TestGuiKetQuaDiDuyet:
    def test_gui_duyet_sinh_phien_ban_ket_qua(self, client, as_role, department):
        did = _setup(client, as_role, department)
        as_role("staff", department_id=department.id)
        data = _nhap_va_gui_duyet(client, did)

        assert data["version"] == 1
        assert data["approval_status"] == "pending"

        d = client.get(f"{_DISPATCHES}/{did}").json()["data"]
        assert d["result_approval_status"] == "pending"
        assert d["result_version"] == 1

    def test_chua_co_ket_qua_thi_khong_gui_duyet_duoc(self, client, as_role, department):
        did = _setup(client, as_role, department)
        as_role("staff", department_id=department.id)

        res = client.post(f"{_DISPATCHES}/{did}/result/submit", json={})
        assert res.status_code == 400, res.text

    def test_phong_khac_khong_gui_duyet_duoc(self, client, as_role, department, db):
        import uuid as _uuid

        from app.models.department import Department

        did = _setup(client, as_role, department)
        as_role("staff", department_id=department.id)
        client.patch(f"{_DISPATCHES}/{did}/result", json={"ket_qua": "1,82 %"})

        phong_khac = Department(name="Phòng C", code=_uuid.uuid4().hex[:8])
        db.add(phong_khac)
        db.flush()
        as_role("staff", department_id=phong_khac.id)
        assert client.post(f"{_DISPATCHES}/{did}/result/submit", json={}).status_code == 403

    def test_thieu_ngay_hen_va_khong_co_TAT_thi_bao_ro(self, client, as_role, department):
        """Không bịa hạn trả: hạn sai sẽ chảy thẳng vào KPI 'quá hạn'."""
        as_role("reception", department_id=department.id)
        it = client.post(
            _INTAKES, json={"customer_name": "Cty Không Hẹn Ngày"}
        ).json()["data"]
        did = client.post(
            f"{_INTAKES}/{it['id']}/dispatches",
            json={"chi_tieu": "pH", "target_department_id": str(department.id)},
        ).json()["data"]["id"]

        as_role("staff", department_id=department.id)
        client.patch(f"{_DISPATCHES}/{did}/result", json={"ket_qua": "6,8"})
        res = client.post(f"{_DISPATCHES}/{did}/result/submit", json={})
        assert res.status_code == 400, res.text
        assert "Ngày hẹn trả" in res.json()["error"]["message"]


@requires_db
class TestTachNhapVaDuyet:
    def test_nguoi_nhap_khong_tu_duyet_duoc(self, client, as_role, department):
        """Bất biến của cả ISO 17025 lẫn M1 — người duyệt phải khác người nhập."""
        did = _setup(client, as_role, department)
        # is_dept_lead=True: người này CÓ quyền duyệt nói chung — nếu không, test sẽ
        # dừng ở FORBIDDEN và không chạm tới luật chặn tự duyệt cần kiểm.
        as_role("staff", department_id=department.id, is_dept_lead=True)
        data = _nhap_va_gui_duyet(client, did)

        res = client.post(f"{_RESULTS}/{data['id']}/approve", json={})
        assert res.status_code == 403, res.text
        assert res.json()["error"]["code"] == ErrorCode.SELF_APPROVAL_FORBIDDEN

    def test_truong_phong_lab_duyet_duoc(self, client, as_role, department):
        did = _setup(client, as_role, department)
        as_role("staff", department_id=department.id)
        data = _nhap_va_gui_duyet(client, did)

        as_role("lab_manager", department_id=department.id, is_dept_lead=True)
        res = client.post(f"{_RESULTS}/{data['id']}/approve", json={})
        assert res.status_code == 200, res.text

        d = client.get(f"{_DISPATCHES}/{did}").json()["data"]
        assert d["result_approval_status"] == "approved"
        assert d["result_approved_by_name"]
        assert d["result_approved_at"]

    def test_tra_lai_de_lam_lai(self, client, as_role, department):
        did = _setup(client, as_role, department)
        as_role("staff", department_id=department.id)
        data = _nhap_va_gui_duyet(client, did)

        as_role("lab_manager", department_id=department.id, is_dept_lead=True)
        res = client.post(
            f"{_RESULTS}/{data['id']}/return", json={"reason": "Thiếu số liệu thô"}
        )
        assert res.status_code == 200, res.text
        assert client.get(f"{_DISPATCHES}/{did}").json()["data"][
            "result_approval_status"
        ] == "pending"


@requires_db
class TestKetQuaDaDuyetLaBatBien:
    def test_duyet_xong_thi_khoa_o_ket_qua(self, client, as_role, department):
        """Đây là lỗ hổng chính của P0-2: trước m40 vẫn PATCH đè được."""
        did = _setup(client, as_role, department)
        ktv = as_role("staff", department_id=department.id)
        data = _nhap_va_gui_duyet(client, did)

        as_role("lab_manager", department_id=department.id, is_dept_lead=True)
        assert client.post(f"{_RESULTS}/{data['id']}/approve", json={}).status_code == 200

        _relogin(ktv)
        res = client.patch(f"{_DISPATCHES}/{did}/result", json={"ket_qua": "9,99 %"})
        assert res.status_code == 409, res.text
        assert res.json()["error"]["code"] == ErrorCode.RESULT_LOCKED

    def test_sua_sau_duyet_sinh_phien_ban_moi(self, client, as_role, department):
        did = _setup(client, as_role, department)
        ktv = as_role("staff", department_id=department.id)
        v1 = _nhap_va_gui_duyet(client, did)

        as_role("lab_manager", department_id=department.id, is_dept_lead=True)
        assert client.post(f"{_RESULTS}/{v1['id']}/approve", json={}).status_code == 200

        _relogin(ktv)
        res = client.post(
            f"{_RESULTS}/{v1['id']}/revisions",
            json={
                "result_data": {"chi_tieu": "Hàm lượng Nitơ tổng số", "ket_qua": "1,90 %"},
                "reason": "Tính lại theo hệ số pha loãng đúng",
            },
        )
        assert res.status_code == 201, res.text
        v2 = res.json()["data"]
        assert v2["version"] == 2
        assert v2["approval_status"] == "pending"
        assert v2["previous_version"] == 1

        d = client.get(f"{_DISPATCHES}/{did}").json()["data"]
        assert d["result_version"] == 2
        assert d["result_approval_status"] == "pending"

    def test_sua_sau_duyet_bat_buoc_co_ly_do(self, client, as_role, department):
        did = _setup(client, as_role, department)
        ktv = as_role("staff", department_id=department.id)
        v1 = _nhap_va_gui_duyet(client, did)

        as_role("lab_manager", department_id=department.id, is_dept_lead=True)
        assert client.post(f"{_RESULTS}/{v1['id']}/approve", json={}).status_code == 200

        _relogin(ktv)
        res = client.post(
            f"{_RESULTS}/{v1['id']}/revisions",
            json={"result_data": {"ket_qua": "1,90 %"}, "reason": "   "},
        )
        assert res.status_code in (400, 422), res.text


@requires_db
class TestMotMauChoMoiPhieuVaPhong:
    def test_nhieu_chi_tieu_cung_phong_dung_chung_mot_mau(
        self, client, as_role, department, db
    ):
        """Năm chỉ tiêu cùng phiếu gửi cùng phòng là CÙNG một mẫu vật lý."""
        from app.models.sample import Sample
        from app.models.sample_assignment import SampleAssignment
        from app.models.sample_flow import SampleDispatch

        as_role("reception", department_id=department.id)
        hen = (date.today() + timedelta(days=7)).strftime("%d/%m/%Y")
        it = client.post(
            _INTAKES, json={"customer_name": "Cty Nhiều Chỉ Tiêu", "due_date": hen}
        ).json()["data"]
        dids = []
        for ct in ("pH", "Độ ẩm", "Chì (Pb)"):
            dids.append(client.post(
                f"{_INTAKES}/{it['id']}/dispatches",
                json={"chi_tieu": ct, "target_department_id": str(department.id)},
            ).json()["data"]["id"])

        as_role("staff", department_id=department.id)
        for did in dids:
            client.patch(f"{_DISPATCHES}/{did}/result", json={"ket_qua": "x"})
            assert client.post(
                f"{_DISPATCHES}/{did}/result/submit", json={}
            ).status_code == 201

        rows = db.execute(
            SampleDispatch.__table__.select().where(
                SampleDispatch.intake_id == it["id"]
            )
        ).fetchall()
        asg_ids = {r.assignment_id for r in rows}
        assert len(asg_ids) == 3, "mỗi chỉ tiêu phải là một PHẦN VIỆC riêng"

        sample_ids = {
            db.get(SampleAssignment, a).sample_id for a in asg_ids
        }
        assert len(sample_ids) == 1, "cùng phiếu + cùng phòng phải là MỘT mẫu"
        assert db.get(Sample, next(iter(sample_ids))) is not None
