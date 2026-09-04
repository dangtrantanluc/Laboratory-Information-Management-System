"""m37 — ai sửa được gì trên phiếu chuyển mẫu (BM 7.1/02).

LỊCH SỬ (đọc trước khi sửa test này)
m36 chốt "chỉ admin/leader/reception được sửa phiếu chuyển mẫu" và, vì cả nội dung
hành chính lẫn cột kết quả đi chung `PATCH /dispatches/{id}`, đã phải cắt luôn quyền
ghi kết quả của khối lab. m37 tách endpoint nên hai yêu cầu không còn xung đột:

    PATCH /dispatches/{id}         dispatch:update  admin · leader · reception
                                   → note, sample_name, quantity
    PATCH /dispatches/{id}/result  dispatch:result  admin · lab_manager · staff
                                   → ket_qua, don_vi, phuong_phap, status

Yêu cầu nghiệp vụ của m36 GIỮ NGUYÊN: khối lab vẫn không sửa được nội dung hành
chính của phiếu. Cái được trả lại chỉ là phần việc của người thực hiện phép thử.

Vì sao đáng có test riêng: quyền nằm trong bảng roles_permissions chứ không trong
mã nguồn, nên không compiler nào bắt được khi ai đó chạy một migration khác thêm
lại quyền. Nới quyền thì không ai thấy, còn siết quyền thì người dùng báo ngay.
"""
import pytest

from app.core.error_codes import ErrorCode
from app.tests.conftest import requires_db

_INTAKES = "/api/v1/intakes"
_DISPATCHES = "/api/v1/dispatches"

# Sửa nội dung HÀNH CHÍNH của phiếu (ghi chú, tên mẫu, số lượng).
ADMIN_ALLOWED = ("admin", "reception", "leader")
ADMIN_DENIED = ("staff", "lab_manager", "office")

# Ghi KẾT QUẢ + trạng thái thực hiện.
RESULT_ALLOWED = ("admin", "staff", "lab_manager")
RESULT_DENIED = ("reception", "leader", "office", "qms")


def _make_dispatch(client, department) -> str:
    """Tạo phiếu nhận + 1 lượt chuyển. Cần intake:manage nên chạy dưới vai reception."""
    intake = client.post(_INTAKES, json={"customer_name": "Cty Thử Quyền"}).json()["data"]
    res = client.post(
        f"{_INTAKES}/{intake['id']}/dispatches",
        json={"chi_tieu": "pH", "target_department_id": str(department.id)},
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


@requires_db
class TestSuaNoiDungHanhChinh:
    """PATCH /dispatches/{id} — phần của Phòng nhận mẫu."""

    @pytest.mark.parametrize("role", ADMIN_ALLOWED)
    def test_allowed_roles_can_update(self, client, as_role, department, role):
        as_role("reception", department_id=department.id)
        did = _make_dispatch(client, department)

        as_role(role, department_id=department.id)
        res = client.patch(f"{_DISPATCHES}/{did}", json={"note": "Mẫu giao lúc 9h"})
        assert res.status_code == 200, f"{role} phải sửa được: {res.text}"
        assert res.json()["data"]["note"] == "Mẫu giao lúc 9h"

    @pytest.mark.parametrize("role", ADMIN_DENIED)
    def test_lab_and_office_cannot_update(self, client, as_role, department, role):
        """Khối lab vẫn KHÔNG sửa được nội dung hành chính — nguyên vẹn ý m36."""
        as_role("reception", department_id=department.id)
        did = _make_dispatch(client, department)

        as_role(role, department_id=department.id)
        res = client.patch(f"{_DISPATCHES}/{did}", json={"note": "x"})
        assert res.status_code == 403, f"{role} không được sửa: {res.text}"
        assert res.json()["error"]["code"] == ErrorCode.FORBIDDEN

    def test_khong_con_ghi_duoc_ket_qua_qua_duong_hanh_chinh(
        self, client, as_role, department
    ):
        """Đường cũ KHÔNG còn nhận cột kết quả.

        Đây là bất biến chính của m37: nếu ai đó thêm lại `ket_qua` vào
        UpdateDispatchRequest thì Phòng nhận mẫu lại ghi hộ kết quả được, và
        `performed_by` quay về vô nghĩa.
        """
        as_role("reception", department_id=department.id)
        did = _make_dispatch(client, department)

        res = client.patch(f"{_DISPATCHES}/{did}", json={"ket_qua": "7.2"})
        assert res.status_code == 400, res.text
        assert res.json()["error"]["code"] == ErrorCode.VALIDATION_ERROR

    @pytest.mark.parametrize("role", ("staff", "lab_manager"))
    def test_lab_roles_can_still_read(self, client, as_role, department, role):
        """Mất quyền SỬA không được kéo theo mất quyền ĐỌC."""
        as_role("reception", department_id=department.id)
        did = _make_dispatch(client, department)

        as_role(role, department_id=department.id)
        assert client.get(f"{_DISPATCHES}/{did}").status_code == 200


@requires_db
class TestGhiKetQua:
    """PATCH /dispatches/{id}/result — phần của người thực hiện phép thử."""

    @pytest.mark.parametrize("role", RESULT_ALLOWED)
    def test_lab_roles_can_write_result(self, client, as_role, department, role):
        as_role("reception", department_id=department.id)
        did = _make_dispatch(client, department)

        as_role(role, department_id=department.id)
        res = client.patch(f"{_DISPATCHES}/{did}/result", json={"ket_qua": "7.2"})
        assert res.status_code == 200, f"{role} phải ghi được kết quả: {res.text}"
        assert res.json()["data"]["ket_qua"] == "7.2"

    @pytest.mark.parametrize("role", RESULT_DENIED)
    def test_non_lab_roles_cannot_write_result(self, client, as_role, department, role):
        """Phòng nhận mẫu KHÔNG còn nhập hộ kết quả — mục đích của cả m37."""
        as_role("reception", department_id=department.id)
        did = _make_dispatch(client, department)

        as_role(role, department_id=department.id)
        res = client.patch(f"{_DISPATCHES}/{did}/result", json={"ket_qua": "7.2"})
        assert res.status_code == 403, f"{role} không được ghi kết quả: {res.text}"

    def test_performed_by_lay_tu_tai_khoan_dang_nhap(
        self, client, as_role, department
    ):
        """Danh tính người thực hiện KHÔNG nhận từ client.

        ISO/IEC 17025 §7.8.2 đòi kết quả truy về được người thực hiện. Trước m37 ô
        `can_bo` là text tự do do người khác gõ, nên truy xuất chỉ là hình thức.
        """
        as_role("reception", department_id=department.id)
        did = _make_dispatch(client, department)

        ktv = as_role("staff", department_id=department.id)
        res = client.patch(f"{_DISPATCHES}/{did}/result", json={"ket_qua": "7.2"})
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["performed_by"] == str(ktv.id)
        assert data["performed_by_name"] == ktv.full_name
        assert data["performed_at"] is not None

    def test_body_khong_nhan_performed_by(self, client, as_role, department):
        """Gửi thẳng performed_by phải bị từ chối, không được âm thầm bỏ qua."""
        as_role("reception", department_id=department.id)
        did = _make_dispatch(client, department)

        as_role("staff", department_id=department.id)
        for field in ("performed_by", "can_bo"):
            res = client.patch(f"{_DISPATCHES}/{did}/result", json={field: "ai đó"})
            assert res.status_code == 400, f"{field} phải bị từ chối: {res.text}"

    def test_ktv_phong_khac_bi_chan(self, client, as_role, department, db):
        """Phạm vi phòng ban: KTV chỉ ghi kết quả cho lượt chuyển tới phòng mình."""
        import uuid as _uuid

        from app.models.department import Department

        as_role("reception", department_id=department.id)
        did = _make_dispatch(client, department)

        phong_khac = Department(
            name="Phòng B", code=_uuid.uuid4().hex[:8]  # code là duy nhất
        )
        db.add(phong_khac)
        db.flush()

        as_role("staff", department_id=phong_khac.id)
        res = client.patch(f"{_DISPATCHES}/{did}/result", json={"ket_qua": "7.2"})
        assert res.status_code == 403, res.text


@requires_db
class TestStateMachineLuotChuyen:
    """Trạng thái thực hiện đi theo DISPATCH_NEXT, không lùi bước được."""

    def test_di_dung_thu_tu(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        did = _make_dispatch(client, department)

        as_role("staff", department_id=department.id)
        for nxt in ("received", "in_progress", "done"):
            res = client.patch(f"{_DISPATCHES}/{did}/result", json={"status": nxt})
            assert res.status_code == 200, f"{nxt}: {res.text}"
            assert res.json()["data"]["status"] == nxt

    def test_khong_lui_duoc_tu_done(self, client, as_role, department):
        """`done → sent` từng hợp lệ, nên kết quả đã trả khách viết đè được không để vết."""
        as_role("reception", department_id=department.id)
        did = _make_dispatch(client, department)

        as_role("staff", department_id=department.id)
        client.patch(f"{_DISPATCHES}/{did}/result", json={"status": "received"})
        client.patch(f"{_DISPATCHES}/{did}/result", json={"status": "done"})

        res = client.patch(f"{_DISPATCHES}/{did}/result", json={"status": "sent"})
        assert res.status_code == 409, res.text
        assert res.json()["error"]["code"] == ErrorCode.INVALID_TRANSITION

    def test_khong_nhay_coc_tu_sent_sang_done(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        did = _make_dispatch(client, department)

        as_role("staff", department_id=department.id)
        res = client.patch(f"{_DISPATCHES}/{did}/result", json={"status": "done"})
        assert res.status_code == 409, res.text

    def test_next_statuses_khop_state_machine(self, client, as_role, department):
        """FE dựng nút từ next_statuses — phải khớp đúng luật backend áp."""
        as_role("reception", department_id=department.id)
        did = _make_dispatch(client, department)

        res = client.get(f"{_DISPATCHES}/{did}")
        assert res.json()["data"]["next_statuses"] == ["received", "returned"]
