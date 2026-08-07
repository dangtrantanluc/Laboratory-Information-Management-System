"""Quyền xem thống kê truy cập tài liệu — chống lộ dữ liệu giám sát người dùng.

`GET /documents/access-stats` trả về ai đã xem/tải tài liệu kiểm soát nào, theo phòng
ban, theo thời gian. Trước bản vá, `aggregate_access_stats` chỉ chặn vai trò `office`,
nên `staff`/`qms`/`lab_manager`/`reception` đều đọc được — trong khi menu ở frontend
(`nav.ts`) chỉ hiện mục này cho `admin`.

Đây là ca THỨ HAI của cùng một mẫu lỗi đã gây ra lỗ hổng `/quotations`: danh sách vai
trò ở menu và ở luật thật là hai nguồn viết độc lập. Bộ test này khoá lại luật thật.

Mốc chọn admin/leader lấy từ chính module đó, không phải luật mới:
  · export_access_stats_xlsx() vốn đã yêu cầu is_privileged — xuất Excel chỉ là một
    định dạng của CÙNG dữ liệu, không thể chặt hơn đường xem.
  · report_common.require_audit_read (thống kê truy cập hệ thống R15) = admin/leader.
"""
import pytest

from app.tests.conftest import requires_db

pytestmark = requires_db

_AGGREGATE = "/api/v1/documents/access-stats"
_EXPORT = "/api/v1/documents/access-stats/export"

DUOC_XEM = ["admin", "leader"]
BI_CHAN = ["staff", "qms", "lab_manager", "reception", "office"]


@pytest.mark.parametrize("role", DUOC_XEM)
def test_admin_va_lanh_dao_xem_duoc(client, as_role, role):
    as_role(role)
    assert client.get(_AGGREGATE).status_code == 200


@pytest.mark.parametrize("role", BI_CHAN)
def test_vai_tro_khac_bi_chan(client, as_role, role):
    """Đây là lỗ hổng thật: 4/5 vai trò này trước đây đọc được toàn bộ thống kê."""
    as_role(role)
    assert client.get(_AGGREGATE).status_code == 403


@pytest.mark.parametrize("role", BI_CHAN)
def test_duong_xuat_excel_cung_bi_chan(client, as_role, role):
    """Đường xuất vốn đã chặt — khẳng định bản vá không nới lỏng nó."""
    as_role(role)
    assert client.get(_EXPORT).status_code == 403


def test_thong_ke_theo_TUNG_tai_lieu_van_giu_pham_vi_phong_ban(client, db, as_role, seeded_user):
    """Đối trọng: bản vá chỉ siết bản TỔNG HỢP chéo phòng.

    Trưởng phòng lab vẫn phải xem được thống kê của tài liệu phòng mình
    (`_assert_stats_scope`) — nếu test này đỏ nghĩa là đã siết quá tay.
    """
    import uuid

    from app.models.department import Department
    from app.models.document import Document, DocumentType, DocumentVersion

    dept = Department(name=f"Phòng {uuid.uuid4().hex[:6]}", code=uuid.uuid4().hex[:8])
    db.add(dept)
    db.flush()
    author = seeded_user(role="staff", department_id=dept.id)

    if db.get(DocumentType, "QT") is None:
        db.add(DocumentType(code="QT", label="Quy trình", prefix="QT"))
        db.flush()
    doc = Document(
        code=f"QT-{uuid.uuid4().hex[:8]}",
        title="Tài liệu thử",
        type="QT",
        department_id=dept.id,
        security_level="internal",
        created_by=author.id,
    )
    db.add(doc)
    db.flush()
    db.add(DocumentVersion(document_id=doc.id, version_no=1, status="draft", created_by=author.id))
    db.flush()

    as_role("lab_manager", department_id=dept.id)
    r = client.get(f"/api/v1/documents/{doc.id}/access-stats")

    assert r.status_code == 200, (
        f"trưởng phòng lab phải xem được thống kê tài liệu phòng mình — nhận {r.status_code}"
    )
