"""Uỷ quyền cấp đối tượng cho tệp đính kèm — lưới chắn cho lỗ hổng BOLA đã vá.

VÌ SAO CẦN BỘ TEST NÀY

`test_idor_routes.py` quét 296 route và khẳng định mọi route đều CÓ xác thực. Nó tự
ghi trong docstring rằng phần "user A không đọc được tài nguyên của user B" là việc
của test tích hợp. Test tích hợp đó chưa từng được viết — và đó chính là lý do một
lỗ hổng cỡ này sống sót: `GET /attachments/{id}` có `Depends(get_current_user)` nên
bài quét khai báo báo xanh, trong khi luật uỷ quyền duy nhất bên trong là "cấm office
đọc 3 owner_type của M1".

Mỗi test dưới đây tương ứng một đường tấn công cụ thể đã xác nhận được trên mã nguồn,
KHÔNG phải một quy tắc chung chung.
"""
import uuid

from app.tests.conftest import requires_db

pytestmark = requires_db


# ═══════════════════════════ Helper dựng dữ liệu ═══════════════════════════


def _attachment(db, *, owner_type: str, owner_id: uuid.UUID, uploaded_by: uuid.UUID):
    """Hàng attachments trỏ tới owner cho trước. Không đụng MinIO — mọi test ở đây
    dừng ở tầng uỷ quyền, chưa tới bước ký URL."""
    from app.models.attachment import Attachment

    att = Attachment(
        owner_type=owner_type,
        owner_id=owner_id,
        file_key=f"{owner_type}/{owner_id}/{uuid.uuid4().hex}_f.pdf",
        file_name="f.pdf",
        mime="application/pdf",
        size=10,
        uploaded_by=uploaded_by,
    )
    db.add(att)
    db.flush()
    return att


def _document(db, *, department_id, created_by, security_level: str, status: str = "approved"):
    from app.models.document import Document, DocumentType, DocumentVersion

    dtype = db.get(DocumentType, "QT")
    if dtype is None:
        dtype = DocumentType(code="QT", label="Quy trình", prefix="QT")
        db.add(dtype)
        db.flush()

    doc = Document(
        code=f"QT-{uuid.uuid4().hex[:8]}",
        title="Tài liệu thử",
        type=dtype.code,
        department_id=department_id,
        security_level=security_level,
        created_by=created_by,
    )
    db.add(doc)
    db.flush()
    version = DocumentVersion(
        document_id=doc.id, version_no=1, status=status, created_by=created_by
    )
    if status == "approved":
        # CHECK ck_dv_approved_has_approver: bản đã ban hành BẮT BUỘC có người + thời
        # điểm duyệt. Ràng buộc ở tầng DB, không chỉ ở tầng ứng dụng.
        from datetime import datetime, timezone

        version.approved_by = created_by
        version.approved_at = datetime.now(timezone.utc)
    db.add(version)
    db.flush()
    return doc, version


def _form_submission(db, *, department_id, submitted_by, status: str):
    from app.models.form import FormSubmission, FormTemplate

    tpl = FormTemplate(
        code=f"BM-{uuid.uuid4().hex[:8]}",
        title="Biểu mẫu thử",
        iso_clause="7.5",
        created_by=submitted_by,
    )
    db.add(tpl)
    db.flush()
    sub = FormSubmission(
        template_id=tpl.id,
        department_id=department_id,
        submitted_by=submitted_by,
        status=status,
    )
    db.add(sub)
    db.flush()
    return tpl, sub


def _department(db, name: str):
    from app.models.department import Department

    d = Department(name=name, code=uuid.uuid4().hex[:8])
    db.add(d)
    db.flush()
    return d


# ═══════════════════════════ 1. Deny by default ═══════════════════════════


class TestDenyByDefault:
    """Bất biến quan trọng nhất của attachment_authz.

    Nếu bất biến này hỏng, mọi owner_type thêm sau sẽ âm thầm mở lại đúng lỗ hổng cũ —
    kể cả khi 14 guard hiện có vẫn đúng.
    """

    def test_owner_type_chua_khai_luat_thi_khong_ai_doc_duoc(self, client, db, as_role):
        """`staff_activity` nằm trong CHECK constraint nhưng chưa module nào dùng.

        Trước khi vá, nó rơi vào nhánh "mọi vai trò đã đăng nhập được đọc".
        """
        admin = as_role("admin")
        att = _attachment(
            db, owner_type="staff_activity", owner_id=uuid.uuid4(), uploaded_by=admin.id
        )

        r = client.get(f"/api/v1/attachments/{att.id}")

        assert r.status_code == 403, (
            "owner_type chưa khai luật phải bị TỪ CHỐI, kể cả với admin — "
            f"nhận {r.status_code}"
        )

    def test_owner_type_chua_khai_luat_thi_khong_gan_duoc_tep(self, client, as_role):
        as_role("admin")
        r = client.post(
            "/api/v1/attachments",
            data={"owner_type": "staff_activity", "owner_id": str(uuid.uuid4())},
            files={"file": ("x.pdf", b"%PDF-1.4 x", "application/pdf")},
        )
        assert r.status_code == 403

    def test_moi_owner_type_dang_dung_deu_da_khai_luat(self):
        """Chặn lỗi ngược lại: khai thiếu guard làm hỏng tính năng đang chạy.

        Danh sách này là các owner_type thực sự được ghi trong backend/frontend. Thêm
        owner_type mới vào luồng ghi mà quên khai guard sẽ làm test này đỏ NGAY, thay
        vì để người dùng phát hiện bằng lỗi 403 lúc tải tệp.
        """
        from app.services import attachment_authz as authz

        dang_dung = {
            "sample", "test_request", "sample_result", "document_version",
            "form_template", "form_submission", "hr_profile", "publication",
            "chemical", "chem_lot", "equipment", "calibration",
            "sample_intake", "sample_dispatch",
        }
        assert dang_dung <= set(authz._READ_GUARDS)
        assert dang_dung <= set(authz._WRITE_GUARDS)


# ═══════════════════════════ 2. Tài liệu mức restricted ═══════════════════════════


class TestTaiLieuRestricted:
    """Đường tấn công chính: lấy attachment_id từ lúc còn quyền, dùng lại sau khi mất."""

    def test_staff_phong_khac_khong_tai_duoc_tai_lieu_restricted(
        self, client, db, as_role, seeded_user
    ):
        phong_a = _department(db, "Phòng A")
        phong_b = _department(db, "Phòng B")
        chu_tai_lieu = seeded_user(role="staff", department_id=phong_a.id)
        _doc, version = _document(
            db,
            department_id=phong_a.id,
            created_by=chu_tai_lieu.id,
            security_level="restricted",
        )
        att = _attachment(
            db,
            owner_type="document_version",
            owner_id=version.id,
            uploaded_by=chu_tai_lieu.id,
        )

        as_role("staff", department_id=phong_b.id)
        r = client.get(f"/api/v1/attachments/{att.id}")

        assert r.status_code == 403, (
            "tài liệu 'restricted' của phòng khác phải bị chặn ở đường generic "
            f"/attachments — nhận {r.status_code}"
        )

    def test_staff_dung_phong_van_tai_duoc(self, client, db, as_role, seeded_user):
        """Đối trọng: bản vá không được chặn nhầm người có quyền thật."""
        phong_a = _department(db, "Phòng A")
        chu_tai_lieu = seeded_user(role="staff", department_id=phong_a.id)
        _doc, version = _document(
            db,
            department_id=phong_a.id,
            created_by=chu_tai_lieu.id,
            security_level="restricted",
        )
        att = _attachment(
            db,
            owner_type="document_version",
            owner_id=version.id,
            uploaded_by=chu_tai_lieu.id,
        )

        as_role("staff", department_id=phong_a.id)
        r = client.get(f"/api/v1/attachments/{att.id}")

        assert r.status_code == 200, (
            f"người đúng phòng phải tải được — nhận {r.status_code}: {r.text[:200]}"
        )

    def test_ban_nhap_cua_nguoi_khac_khong_lo_ra(self, client, db, as_role, seeded_user):
        """Bản draft chỉ người soạn + trưởng nhóm thấy (can_view_unpublished_version)."""
        phong = _department(db, "Phòng A")
        nguoi_soan = seeded_user(role="staff", department_id=phong.id)
        _doc, version = _document(
            db,
            department_id=phong.id,
            created_by=nguoi_soan.id,
            security_level="internal",
            status="draft",
        )
        att = _attachment(
            db, owner_type="document_version", owner_id=version.id, uploaded_by=nguoi_soan.id
        )

        as_role("staff", department_id=phong.id)  # cùng phòng nhưng KHÔNG phải người soạn
        r = client.get(f"/api/v1/attachments/{att.id}")

        assert r.status_code == 404, (
            f"bản nháp của người khác phải ẩn (404), nhận {r.status_code}"
        )


# ═══════════════════════════ 3. Ghi đè minh chứng đã duyệt ═══════════════════════════


class TestGhiDeMinhChungDaDuyet:
    """form_file_service khoá tệp sau khi duyệt — nhưng đường generic thì không.

    `form_file_service` ghi rõ trong docstring: "bất kỳ ai biết id biểu mẫu cũng ghi
    đè được kho VILAS". Nhóm test này khoá lại lời cảnh báo đó.
    """

    def test_khong_dinh_kem_duoc_vao_minh_chung_da_duyet(
        self, client, db, as_role, seeded_user
    ):
        phong = _department(db, "Phòng A")
        nguoi_nop = seeded_user(role="staff", department_id=phong.id)
        _tpl, sub = _form_submission(
            db, department_id=phong.id, submitted_by=nguoi_nop.id, status="approved"
        )

        as_role("admin")  # kể cả admin cũng không được phá chữ ký duyệt
        r = client.post(
            "/api/v1/attachments",
            data={"owner_type": "form_submission", "owner_id": str(sub.id)},
            files={"file": ("gia.pdf", b"%PDF-1.4 x", "application/pdf")},
        )

        assert r.status_code in (403, 422), (
            f"minh chứng đã duyệt phải khoá tệp — nhận {r.status_code}"
        )

    def test_staff_phong_khac_khong_dinh_kem_duoc(self, client, db, as_role, seeded_user):
        phong_a = _department(db, "Phòng A")
        phong_b = _department(db, "Phòng B")
        nguoi_nop = seeded_user(role="staff", department_id=phong_a.id)
        _tpl, sub = _form_submission(
            db, department_id=phong_a.id, submitted_by=nguoi_nop.id, status="pending"
        )

        as_role("staff", department_id=phong_b.id)
        r = client.post(
            "/api/v1/attachments",
            data={"owner_type": "form_submission", "owner_id": str(sub.id)},
            files={"file": ("x.pdf", b"%PDF-1.4 x", "application/pdf")},
        )

        assert r.status_code == 403


# ═══════════════════════════ 4. Owner không tồn tại ═══════════════════════════


def test_khong_gan_duoc_tep_vao_owner_khong_ton_tai(client, as_role):
    """`attachments.owner_id` KHÔNG có khoá ngoại (mẫu polymorphic), nên tầng ứng dụng
    là nơi duy nhất chặn được attachment mồ côi. Trước khi vá, request này trả 201."""
    as_role("admin")

    r = client.post(
        "/api/v1/attachments",
        data={"owner_type": "sample", "owner_id": str(uuid.uuid4())},
        files={"file": ("x.pdf", b"%PDF-1.4 x", "application/pdf")},
    )

    assert r.status_code == 404, f"owner không tồn tại phải 404 — nhận {r.status_code}"
