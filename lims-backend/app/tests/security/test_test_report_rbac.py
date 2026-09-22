"""Phân quyền phiếu kết quả thử nghiệm (m46) — và đường vòng qua `/attachments`.

VÌ SAO BỘ TEST NÀY QUAN TRỌNG HƠN VẺ NGOÀI CỦA NÓ

Tệp BM 7.8/01 chứa nguyên văn TÊN và ĐỊA CHỈ khách hàng ở bảng đầu phiếu — đúng những
trường m26 che với khối lab. Nếu module này lỡ dùng `intake:read` để gác (quyền đang
cấp cho staff và lab_manager với scope 'all'), toàn bộ cơ chế che PII bị vô hiệu bằng
hai lệnh gọi API. Đó chính là lỗ hổng `attachment_authz` đã phải vá một lần cho phiếu
nhận mẫu, và không có gì ngăn nó tái diễn ngoài một bài test.

Hai mặt được canh:
  · đường RIÊNG   /test-reports/...
  · đường GENERIC /attachments  (nơi lỗ hổng cũ đã sống sót vì không ai nhìn tới)

Cả hai phải cho cùng một câu trả lời — kể cả với luật khoá-sau-phát-hành, không chỉ
với luật vai trò.
"""
import uuid

import pytest

from app.tests.conftest import requires_db

pytestmark = requires_db

_INTAKES = "/api/v1/intakes"
_REPORTS = "/api/v1/test-reports"
_ATTACHMENTS = "/api/v1/attachments"

_PDF = ("kq.pdf", b"%PDF-1.4 fake", "application/pdf")

# Đúng ba vai được phép (migration m46). Bốn vai còn lại phải bị chặn sạch.
CHO_PHEP = ("reception", "leader", "admin")
BI_CHAN = ("staff", "lab_manager", "qms", "office")


@pytest.fixture(autouse=True)
def _no_minio(monkeypatch):
    monkeypatch.setattr("app.services.storage_service.put_object", lambda *a, **kw: None)
    monkeypatch.setattr(
        "app.services.storage_service.presigned_get_url",
        lambda *a, **kw: "https://minio.test/signed",
    )


@pytest.fixture
def intake(client, as_role):
    as_role("reception")
    r = client.post(_INTAKES, json={"customer_name": "Công ty Nhân Ái", "code": "26N400"})
    assert r.status_code == 201, r.text
    return r.json()["data"]


@pytest.fixture
def report(client, as_role, intake):
    """Bản nháp đã có tệp, do Phòng nhận mẫu lập."""
    as_role("reception")
    r = client.post(f"{_INTAKES}/{intake['id']}/test-reports", json={})
    assert r.status_code == 201, r.text
    rep = r.json()["data"]
    assert client.post(f"{_REPORTS}/{rep['id']}/files", files={"file": _PDF}).status_code == 201
    return client.get(f"{_REPORTS}/{rep['id']}").json()["data"]


class TestVaiTroDuocPhep:
    @pytest.mark.parametrize("role", CHO_PHEP)
    def test_doc_duoc_danh_sach(self, client, as_role, intake, role):
        as_role(role)

        r = client.get(f"{_INTAKES}/{intake['id']}/test-reports")

        assert r.status_code == 200, r.text

    @pytest.mark.parametrize("role", CHO_PHEP)
    def test_lap_duoc_phieu(self, client, as_role, intake, role):
        as_role(role)

        r = client.post(f"{_INTAKES}/{intake['id']}/test-reports", json={})

        assert r.status_code == 201, r.text


class TestVaiTroBiChan:
    """Khối lab, QLCL và Văn phòng không có việc gì với chứng từ đã phát hành."""

    @pytest.mark.parametrize("role", BI_CHAN)
    def test_khong_xem_duoc_danh_sach(self, client, as_role, intake, role):
        as_role(role)

        r = client.get(f"{_INTAKES}/{intake['id']}/test-reports")

        assert r.status_code == 403, r.text

    @pytest.mark.parametrize("role", BI_CHAN)
    def test_khong_lap_duoc_phieu(self, client, as_role, intake, role):
        as_role(role)

        r = client.post(f"{_INTAKES}/{intake['id']}/test-reports", json={})

        assert r.status_code == 403, r.text

    @pytest.mark.parametrize("role", BI_CHAN)
    def test_khong_xem_duoc_chi_tiet(self, client, as_role, report, role):
        as_role(role)

        r = client.get(f"{_REPORTS}/{report['id']}")

        assert r.status_code == 403, r.text

    @pytest.mark.parametrize("role", BI_CHAN)
    def test_khong_tai_duoc_tep(self, client, as_role, report, role):
        """Đây là đường rò PII trực tiếp nhất — tệp chứa tên và địa chỉ khách."""
        as_role(role)
        file_id = report["files"][0]["id"]

        r = client.get(f"{_REPORTS}/{report['id']}/files/{file_id}")

        assert r.status_code == 403, r.text

    @pytest.mark.parametrize("role", BI_CHAN)
    def test_khong_gan_duoc_tep(self, client, as_role, report, role):
        as_role(role)

        r = client.post(f"{_REPORTS}/{report['id']}/files", files={"file": _PDF})

        assert r.status_code == 403, r.text

    @pytest.mark.parametrize("role", BI_CHAN)
    def test_khong_phat_hanh_duoc(self, client, as_role, report, role):
        as_role(role)

        r = client.post(f"{_REPORTS}/{report['id']}/issue", json={})

        assert r.status_code == 403, r.text


class TestDuongVongQuaAttachmentsGeneric:
    """`/attachments` phải trả lời GIỐNG HỆT đường riêng. Lỗ hổng cũ sống sót ở đây."""

    @pytest.mark.parametrize("role", BI_CHAN)
    def test_khong_tai_duoc_tep_qua_duong_generic(self, client, as_role, report, role):
        """Kịch bản tấn công hai lệnh gọi: lấy id tệp rồi tải qua đường generic."""
        as_role(role)
        file_id = report["files"][0]["id"]

        r = client.get(f"{_ATTACHMENTS}/{file_id}")

        assert r.status_code == 403, r.text

    @pytest.mark.parametrize("role", BI_CHAN)
    def test_khong_gan_duoc_tep_qua_duong_generic(self, client, as_role, report, role):
        as_role(role)

        r = client.post(
            _ATTACHMENTS,
            data={"owner_type": "test_report", "owner_id": str(report["id"])},
            files={"file": _PDF},
        )

        assert r.status_code == 403, r.text

    def test_duong_generic_cung_ton_trong_khoa_sau_phat_hanh(
        self, client, as_role, report
    ):
        """Vai ĐƯỢC PHÉP, nhưng phiếu đã phát hành → vẫn phải bị từ chối.

        Đây là test then chốt của cả file: nếu guard trong `attachment_authz` chỉ kiểm
        quyền mà quên gọi lại luật của module, `POST /attachments` sẽ ghi đè được tệp
        của một chứng từ đã trao cho khách — mà không vai trò nào bị vi phạm.
        """
        as_role("reception")
        assert client.post(f"{_REPORTS}/{report['id']}/issue", json={}).status_code == 200

        r = client.post(
            _ATTACHMENTS,
            data={"owner_type": "test_report", "owner_id": str(report["id"])},
            files={"file": _PDF},
        )

        assert r.status_code == 422, r.text
        assert r.json()["error"]["code"] == "RESULT_LOCKED"

    def test_owner_khong_ton_tai_bi_tu_choi(self, client, as_role):
        """Guard ghi cũng xác nhận owner TỒN TẠI — owner_id không có FK cứng."""
        as_role("reception")

        r = client.post(
            _ATTACHMENTS,
            data={"owner_type": "test_report", "owner_id": str(uuid.uuid4())},
            files={"file": _PDF},
        )

        assert r.status_code == 404, r.text
