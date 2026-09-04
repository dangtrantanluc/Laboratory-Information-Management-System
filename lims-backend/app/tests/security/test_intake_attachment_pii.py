"""W1/W2 — hai đường vòng qua cơ chế che thông tin khách hàng (m26).

ĐƯỜNG 1 — TỆP ĐÍNH KÈM
m26 che customer_name/address/tax_code/contact_person/phone/email với khối lab, và
đã xoá cả `customer_id` để chặn GET /customers/{id}. Nhưng guard đọc tệp trước đây
chỉ kiểm quyền `intake:read` — staff và lab_manager đều có với scope 'all' — nên
không hề tham chiếu cơ chế che. Tệp của phiếu chính là bản scan BM 7.1.01 ĐÃ ĐIỀN:

    GET /intakes/{id}      → lấy files[].id
    GET /attachments/{id}  → presigned URL → tải về → đọc lại toàn bộ PII

ĐƯỜNG 2 — Ô TÌM KIẾM
`list_intakes` áp bộ lọc `customer_name.ilike(q)` TRƯỚC khi che, nên gửi
`?q=<tên công ty>` rồi xem phiếu nào trả về là xác nhận được chủ mẫu.

Bộ test cũ (test_attachment_authz.py) chỉ khẳng định guard TỒN TẠI, không khẳng định
guard áp đúng luật — nên cả hai lỗ hổng đều không làm test nào đỏ.

GHI CHÚ KỸ THUẬT: không đi qua POST /attachments vì bước lưu trữ cần MinIO (môi
trường test không có). Hàng attachments chèn thẳng vào DB, và trường hợp ĐƯỢC PHÉP
kiểm bằng chính hàm uỷ quyền thay vì gọi endpoint tải — cùng quy ước với
test_attachment_authz.py.
"""
import uuid

import pytest

from app.tests.conftest import requires_db

_INTAKES = "/api/v1/intakes"
_ATTACHMENTS = "/api/v1/attachments"


def _att_row(db, *, owner_type: str, owner_id, uploaded_by):
    """Hàng attachments trỏ tới owner cho trước. Không đụng MinIO."""
    from app.models.attachment import Attachment

    att = Attachment(
        owner_type=owner_type,
        owner_id=owner_id,
        file_key=f"{owner_type}/{owner_id}/{uuid.uuid4().hex}_f.pdf",
        file_name="BM-7.1.01-da-dien.pdf",
        mime="application/pdf",
        size=10,
        uploaded_by=uploaded_by,
    )
    db.add(att)
    db.flush()
    return att


def _phieu_co_pii(client) -> dict:
    return client.post(_INTAKES, json={
        "customer_name": "Cty CP Thực Phẩm Minh Long",
        "tax_code": "0301234567",
        "address": "12 Nguyễn Huệ, Q1, TP.HCM",
        "contact_person": "Trần Thị B",
        "phone": "0903111222",
        "email": "qa@minhlong.vn",
    }).json()["data"]


def _duyet_xem_thong_tin(client, as_role, department, intake_id: str) -> None:
    """Khối lab xin xem thông tin khách hàng và được Phòng nhận mẫu duyệt."""
    as_role("staff", department_id=department.id)
    req = client.post(f"{_INTAKES}/{intake_id}/info-requests", json={"reason": "Cần biết nền mẫu"})
    assert req.status_code == 201, req.text
    as_role("reception", department_id=department.id)
    assert client.post(
        f"/api/v1/customer-info-requests/{req.json()['data']['id']}/approve", json={}
    ).status_code == 200


@requires_db
class TestTepPhieuNhanMauChiuCungLuatChe:
    def test_khoi_lab_khong_tai_duoc_ban_scan_phieu(
        self, client, as_role, department, db
    ):
        """Lỗ hổng chính: hai lệnh gọi API là đọc lại toàn bộ PII vừa bị che."""
        rc = as_role("reception", department_id=department.id)
        it = _phieu_co_pii(client)
        att = _att_row(db, owner_type="sample_intake", owner_id=it["id"], uploaded_by=rc.id)

        as_role("staff", department_id=department.id)
        res = client.get(f"{_ATTACHMENTS}/{att.id}")
        assert res.status_code == 403, (
            f"khối lab tải được bản scan BM 7.1.01 → đọc lại PII đã che: {res.text}"
        )

    @pytest.mark.parametrize("role", ("staff", "lab_manager"))
    def test_ca_hai_vai_tro_bi_che_deu_bi_chan(
        self, client, as_role, department, db, role
    ):
        rc = as_role("reception", department_id=department.id)
        it = _phieu_co_pii(client)
        att = _att_row(db, owner_type="sample_intake", owner_id=it["id"], uploaded_by=rc.id)

        as_role(role, department_id=department.id)
        assert client.get(f"{_ATTACHMENTS}/{att.id}").status_code == 403, role

    def test_payload_phieu_khong_trao_id_tep(self, client, as_role, department, db):
        """Chặn từ đầu: không đưa id thì không có gì để thử."""
        rc = as_role("reception", department_id=department.id)
        it = _phieu_co_pii(client)
        _att_row(db, owner_type="sample_intake", owner_id=it["id"], uploaded_by=rc.id)

        as_role("staff", department_id=department.id)
        data = client.get(f"{_INTAKES}/{it['id']}").json()["data"]
        assert data["customer_info_masked"] is True
        assert data["files"] == [], f"payload bị che vẫn trao id tệp: {data['files']}"

    def test_duoc_duyet_thi_mo_lai(self, client, as_role, department, db):
        """Che PII không được biến thành chặn vĩnh viễn — duyệt xong phải mở."""
        from app.services import attachment_authz as authz

        rc = as_role("reception", department_id=department.id)
        it = _phieu_co_pii(client)
        att = _att_row(db, owner_type="sample_intake", owner_id=it["id"], uploaded_by=rc.id)

        _duyet_xem_thong_tin(client, as_role, department, it["id"])

        ktv = as_role("staff", department_id=department.id)
        data = client.get(f"{_INTAKES}/{it['id']}").json()["data"]
        assert data["customer_info_masked"] is False
        assert len(data["files"]) == 1
        # Trường hợp ĐƯỢC PHÉP kiểm ở tầng uỷ quyền: đường tải cần MinIO.
        authz.assert_can_read(db, ktv, owner_type="sample_intake", owner_id=att.owner_id)

    @pytest.mark.parametrize("role", ("reception", "admin", "leader", "qms"))
    def test_vai_tro_khong_bi_che_van_doc_duoc(
        self, client, as_role, department, db, role
    ):
        from app.services import attachment_authz as authz

        rc = as_role("reception", department_id=department.id)
        it = _phieu_co_pii(client)
        att = _att_row(db, owner_type="sample_intake", owner_id=it["id"], uploaded_by=rc.id)

        cu = as_role(role, department_id=department.id)
        authz.assert_can_read(db, cu, owner_type="sample_intake", owner_id=att.owner_id)


@requires_db
class TestTepKetQuaThuocVePhongThucHien:
    """Siết PII không được chặn phòng lab đọc lại việc của chính mình."""

    def _dispatch(self, client, department) -> tuple[str, str]:
        it = _phieu_co_pii(client)
        did = client.post(
            f"{_INTAKES}/{it['id']}/dispatches",
            json={"chi_tieu": "pH", "target_department_id": str(department.id)},
        ).json()["data"]["id"]
        return it["id"], did

    def test_lab_gan_va_doc_lai_duoc_tep_ket_qua(self, client, as_role, department, db):
        """m37 giao việc ghi kết quả cho lab → lab phải đính kèm được số liệu thô.

        Nếu guard ghi chỉ chấp nhận `intake:manage`, ô "Đính kèm kết quả" trên chính
        màn hình nhập kết quả sẽ 403 với đúng người được giao nhập.
        """
        from app.services import attachment_authz as authz

        as_role("reception", department_id=department.id)
        _it_id, did = self._dispatch(client, department)

        ktv = as_role("staff", department_id=department.id)
        authz.assert_can_write(db, ktv, owner_type="sample_dispatch", owner_id=uuid.UUID(did))
        authz.assert_can_read(db, ktv, owner_type="sample_dispatch", owner_id=uuid.UUID(did))

    def test_phong_khac_khong_doc_duoc(self, client, as_role, department, db):
        from app.core.exceptions import AppException
        from app.models.department import Department
        from app.services import attachment_authz as authz

        as_role("reception", department_id=department.id)
        _it_id, did = self._dispatch(client, department)

        phong_khac = Department(name="Phòng D", code=uuid.uuid4().hex[:8])
        db.add(phong_khac)
        db.flush()
        nguoi_ngoai = as_role("staff", department_id=phong_khac.id)
        with pytest.raises(AppException):
            authz.assert_can_read(
                db, nguoi_ngoai, owner_type="sample_dispatch", owner_id=uuid.UUID(did)
            )

    def test_lab_khong_gan_duoc_cho_phong_khac(self, client, as_role, department, db):
        from app.core.exceptions import AppException
        from app.models.department import Department
        from app.services import attachment_authz as authz

        as_role("reception", department_id=department.id)
        _it_id, did = self._dispatch(client, department)

        phong_khac = Department(name="Phòng E", code=uuid.uuid4().hex[:8])
        db.add(phong_khac)
        db.flush()
        nguoi_ngoai = as_role("staff", department_id=phong_khac.id)
        with pytest.raises(AppException):
            authz.assert_can_write(
                db, nguoi_ngoai, owner_type="sample_dispatch", owner_id=uuid.UUID(did)
            )


@requires_db
class TestOTimKiemKhongPhaiOracle:
    def test_lab_khong_do_duoc_ten_khach_qua_q(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        it = _phieu_co_pii(client)
        client.post(
            f"{_INTAKES}/{it['id']}/dispatches",
            json={"chi_tieu": "pH", "target_department_id": str(department.id)},
        )

        as_role("staff", department_id=department.id)
        rows = client.get(_INTAKES, params={"q": "Minh Long"}).json()["data"]
        assert rows == [], (
            "gửi ?q=<tên khách> vẫn lọc ra phiếu → xác nhận được chủ mẫu dù đã che"
        )

    def test_lab_van_tim_duoc_theo_ma_phieu(self, client, as_role, department):
        """Che không được biến thành mất khả năng tra cứu — mã phiếu vẫn tìm được."""
        as_role("reception", department_id=department.id)
        it = _phieu_co_pii(client)
        client.post(
            f"{_INTAKES}/{it['id']}/dispatches",
            json={"chi_tieu": "pH", "target_department_id": str(department.id)},
        )

        as_role("staff", department_id=department.id)
        rows = client.get(_INTAKES, params={"q": it["code"]}).json()["data"]
        assert len(rows) == 1 and rows[0]["id"] == it["id"]

    def test_reception_van_tim_duoc_theo_ten(self, client, as_role, department):
        as_role("reception", department_id=department.id)
        _phieu_co_pii(client)
        rows = client.get(_INTAKES, params={"q": "Minh Long"}).json()["data"]
        assert len(rows) == 1
