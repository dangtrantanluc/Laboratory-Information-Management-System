"""Integration (Postgres thật) — m34: map trọn vẹn file "TỔNG HỢP CÁC HOẠT ĐỘNG
2024-2025" + Học kỳ 3 + mở quyền ghi NCKH cho Văn phòng.

Ba nhóm bảo chứng, mỗi nhóm ứng với một khoảng trống có thật trước m34:

  1. CỘT MINH CHỨNG & PHÂN LOẠI — 8/11 bảng của file Excel có cột "Link minh chứng"
     mà hệ thống không lưu ở đâu cả; bốn trường phân loại (số hợp đồng, loại văn
     bằng, bậc đào tạo, loại GCN) bị Excel giấu trong TIÊU ĐỀ NHÓM nên trước đây
     không ai để ý. Test ghi rồi đọc lại để cột thật sự đi hết đường service.

  2. PATCH ÂM THẦM NUỐT THAY ĐỔI — update_publication trước đây chỉ áp 8 field và
     update_teaching chỉ áp 3 field, nên số tiết và các cờ chỉ mục tuy CÓ cột, CÓ
     schema vẫn không sửa được: API trả 200 kèm dữ liệu cũ. Đây là dạng lỗi im
     lặng nhất, nên test kiểm giá trị SAU khi PATCH chứ không kiểm status code.

  3. CHÍNH SÁCH QUYỀN — Văn phòng được ghi nhóm NCKH (thay QUYẾT ĐỊNH #5). Hành vi
     CŨ (cấm) chưa từng có test nào phủ; nếu để trống tiếp thì lần sửa vô ý sau sẽ
     không ai phát hiện. staff vẫn phải bị chặn ngoài phạm vi của mình — kiểm cả
     hai chiều để test không chỉ chứng minh "đã mở" mà còn "không mở quá tay".
"""
import pytest

from app.core.exceptions import AppException
from app.services import activity_service
from app.services.research import (
    community_service,
    publication_service,
    project_service,
    teaching_service,
)


# ===================== 1. Cột minh chứng & phân loại =====================
def test_project_evidence_url_and_external_lead(db, as_role):
    """Đề tài: link minh chứng + chủ nhiệm/thành viên NGOÀI hệ thống.

    Sheet NCKH dòng 13 có chủ nhiệm và hàng chục thành viên ngoài Viện; trước m34
    `_validate_members(allow_external=False)` chặn hết, không nhập nổi một dòng.
    """
    admin = as_role("admin")
    out = project_service.create_project(
        db,
        user=admin,
        payload={
            "title": "Mô hình canh tác nông nghiệp tuần hoàn",
            "level": "national_program",  # mã mới seed ở m34
            "lead_user_id": None,
            "lead_external_name": "Trương Phước Thiên Hoàng",
            "evidence_url": "https://drive.google.com/file/d/abc123",
            "members": [
                {"external_name": "Trương Phước Thiên Hoàng", "role_in_project": "lead"},
                {"external_name": "Nguyễn Minh Quang", "role_in_project": "member"},
                {"user_id": admin.id, "role_in_project": "member"},
            ],
        },
        correlation_id=None,
        ip=None,
    )
    assert out["lead_external_name"] == "Trương Phước Thiên Hoàng"
    assert out["lead_user_id"] is None
    assert out["lead_user_name"] == "Trương Phước Thiên Hoàng"
    assert out["evidence_url"] == "https://drive.google.com/file/d/abc123"
    assert out["member_count"] == 3
    names = {m["name"] for m in out["members"]}
    assert "Nguyễn Minh Quang" in names


def test_project_lead_must_be_xor(db, as_role):
    """Chủ nhiệm: nội bộ HOẶC ngoài hệ thống — không cả hai, không để trống."""
    admin = as_role("admin")
    base = {
        "title": "Đề tài XOR",
        "level": "institution",
        "members": [{"user_id": admin.id, "role_in_project": "lead"}],
    }
    with pytest.raises(AppException) as both:
        project_service.create_project(
            db, user=admin,
            payload={**base, "lead_user_id": admin.id, "lead_external_name": "Ai Đó"},
            correlation_id=None, ip=None,
        )
    assert both.value.http_status == 400

    with pytest.raises(AppException) as neither:
        project_service.create_project(
            db, user=admin,
            payload={**base, "lead_user_id": None, "lead_external_name": None},
            correlation_id=None, ip=None,
        )
    assert neither.value.http_status == 400


def test_patent_kind_three_groups(db, as_role):
    """Bảng sáng chế chia ba mục I/II/III bằng dòng tiêu đề, không phải cột."""
    admin = as_role("admin")
    for kind, no in (
        ("invention", "VN-1-0001"),
        ("utility_solution", "VN-2-0002"),
        ("plant_variety", "VN-3-0003"),
    ):
        out = publication_service.create_publication(
            db, user=admin,
            payload={
                "type": "patent", "title": f"Văn bằng {kind}", "year": 2025,
                "patent_no": no, "issuing_authority": "Cục Sở hữu trí tuệ",
                "patent_kind": kind,
                "application_no": "1-2023-00123", "patent_holder": "Trường ĐH Nông Lâm",
                "evidence_url": "https://ipvietnam.gov.vn/abc",
                "authors": [{"user_id": admin.id, "author_order": 1}],
            },
            correlation_id=None, ip=None,
        )
        assert out["patent_kind"] == kind
        assert out["evidence_url"] == "https://ipvietnam.gov.vn/abc"
        assert out["application_no"] == "1-2023-00123"


def test_patent_kind_rejected_on_non_patent(db, as_role):
    """patent_kind trên bài báo phải bị chặn ở service, không để Postgres ném 500."""
    admin = as_role("admin")
    with pytest.raises(AppException) as e:
        publication_service.create_publication(
            db, user=admin,
            payload={
                "type": "paper", "title": "Bài báo thường", "year": 2025,
                "journal": "JAD", "category": "domestic", "patent_kind": "invention",
                "authors": [{"user_id": admin.id, "author_order": 1}],
            },
            correlation_id=None, ip=None,
        )
    assert e.value.http_status == 400


def test_contract_number_and_signed_date(db, as_role):
    """Excel cột D gộp "PUR.2024.00618 ký ngày 23/9/2024" → tách hai trường."""
    from datetime import date

    out = activity_service.create_contract(
        db, user=as_role("office"),
        payload={
            "title": "Nghiên cứu Phân tích mẫu củ khoai tây",
            "contract_type": "Nghiên cứu KHCN",
            "contract_no": "PUR.2024.00618",
            "signed_date": date(2024, 9, 23),
            "value_amount": "304776000",
            "partner_org": "CÔNG TY TNHH THỰC PHẨM PEPSICO VIỆT NAM",
            "evidence_url": "https://drive.google.com/hd-pepsico",
        },
        correlation_id=None, ip=None,
    )
    assert out["contract_no"] == "PUR.2024.00618"
    assert out["signed_date"] == "2024-09-23"
    assert out["evidence_url"] == "https://drive.google.com/hd-pepsico"


def test_certificate_kind_splits_two_lists(db, as_role):
    """Hai danh sách GCN cùng cấu trúc, trước m34 trộn làm một."""
    office = as_role("office")
    for kind, name in (("short_course", "Học viên A"), ("lab_safety", "Sinh viên B")):
        out = activity_service.create_certificate(
            db, user=office,
            payload={"recipient_name": name, "certificate_no": f"GCN-{kind}",
                     "course_name": "Lớp ngắn hạn", "cert_kind": kind,
                     "academic_year": "2024-2025"},
            correlation_id=None, ip=None,
        )
        assert out["cert_kind"] == kind


def test_staff_activity_and_community_evidence(db, as_role):
    from datetime import date

    admin = as_role("admin")
    act = activity_service.create_activity(
        db, user=admin,
        payload={"kind": "cong_doan", "content": "Hội chợ ẩm thực 20/10/2024",
                 "evidence_url": "https://photos.example/cd-2024"},
        correlation_id=None, ip=None,
    )
    assert act["evidence_url"] == "https://photos.example/cd-2024"

    com = community_service.create_community(
        db, user=admin,
        payload={"content": "Tập huấn cộng đồng", "performer_user_id": admin.id,
                 "performed_at": date(2025, 6, 5),
                 "evidence_url": "https://photos.example/pvcd"},
        correlation_id=None, ip=None,
    )
    assert com["evidence_url"] == "https://photos.example/pvcd"


# ===================== 2. Học kỳ 3 + PATCH không còn nuốt thay đổi =====================
def test_teaching_three_semesters_roundtrip(db, as_role):
    """Một dòng = một môn của một năm học, số tiết trải trên HK1/HK2/HK3."""
    admin = as_role("admin")
    out = teaching_service.create_teaching(
        db, user=admin,
        payload={
            "user_id": admin.id,
            "course_name": "Hệ thống quản lý chất lượng",
            "academic_year": "2024-2025", "year": 2025,
            "training_level": "undergraduate",
            "hk1_theory_hours": 120, "hk1_practice_hours": 0,
            "hk2_theory_hours": 30, "hk2_practice_hours": 0,
            "hk3_theory_hours": 45, "hk3_practice_hours": 15,
            "note": "Dạy cả ba học kỳ",
            "evidence_url": "https://drive.google.com/tkb",
        },
        correlation_id=None, ip=None,
    )
    assert (out["hk1_theory_hours"], out["hk2_theory_hours"], out["hk3_theory_hours"]) == (120, 30, 45)
    assert out["hk3_practice_hours"] == 15
    assert out["training_level"] == "undergraduate"
    assert out["evidence_url"] == "https://drive.google.com/tkb"


def test_teaching_patch_actually_persists_hours(db, as_role):
    """Trước m34 update_teaching chỉ áp 3 field — số tiết PATCH xong vẫn nguyên cũ."""
    admin = as_role("admin")
    created = teaching_service.create_teaching(
        db, user=admin,
        payload={"user_id": admin.id, "course_name": "Sinh học phân tử",
                 "year": 2025, "hk1_theory_hours": 45},
        correlation_id=None, ip=None,
    )
    updated = teaching_service.update_teaching(
        db, user=admin, tid=created["id"],
        changes={"hk1_theory_hours": 60, "hk3_theory_hours": 30,
                 "training_level": "postgraduate", "note": "đã điều chỉnh"},
        correlation_id=None, ip=None,
    )
    assert updated["hk1_theory_hours"] == 60
    assert updated["hk3_theory_hours"] == 30
    assert updated["training_level"] == "postgraduate"
    assert updated["note"] == "đã điều chỉnh"


def test_teaching_external_lecturer(db, as_role):
    """Giảng viên thỉnh giảng ngoài hệ thống — XOR với user_id."""
    admin = as_role("admin")
    out = teaching_service.create_teaching(
        db, user=admin,
        payload={"user_id": None, "lecturer_external_name": "GV Thỉnh Giảng",
                 "course_name": "Bộ gen học", "year": 2025, "hk2_theory_hours": 30},
        correlation_id=None, ip=None,
    )
    assert out["user_id"] is None
    assert out["user_name"] == "GV Thỉnh Giảng"

    with pytest.raises(AppException):
        teaching_service.create_teaching(
            db, user=admin,
            payload={"user_id": admin.id, "lecturer_external_name": "Cả Hai",
                     "course_name": "Môn lỗi", "year": 2025},
            correlation_id=None, ip=None,
        )


def test_publication_patch_persists_index_flags(db, as_role):
    """Trước m34 update_publication chỉ áp 8 field — cờ chỉ mục PATCH xong mất trắng."""
    admin = as_role("admin")
    created = publication_service.create_publication(
        db, user=admin,
        payload={"type": "paper", "title": "Cellulose nanofibers", "year": 2025,
                 "journal": "Catena", "category": "isi_q1",
                 "authors": [{"user_id": admin.id, "author_order": 1}]},
        correlation_id=None, ip=None,
    )
    assert created["pub_scope"] is None and created["is_scie"] is False

    updated = publication_service.update_publication(
        db, user=admin, pub_id=created["id"],
        changes={"pub_scope": "international", "is_scie": True, "is_scopus": True,
                 "academic_year": "2024-2025",
                 "evidence_url": "https://sciencedirect.com/S0341816225003005"},
        correlation_id=None, ip=None,
    )
    assert updated["pub_scope"] == "international"
    assert updated["is_scie"] is True and updated["is_scopus"] is True
    assert updated["academic_year"] == "2024-2025"
    assert updated["evidence_url"].endswith("S0341816225003005")


# ===================== 3. Chính sách quyền =====================
@pytest.mark.parametrize("role", ["admin", "leader", "office"])
def test_three_roles_can_write_research(db, as_role, role):
    """admin / lãnh đạo / VĂN PHÒNG đều thêm-sửa-xoá được nhóm NCKH.

    'office' là vế mới (m34). Trước đây assert_research_access ném FORBIDDEN_OFFICE
    và is_research_all không có office — kể cả khi bỏ chặn ở cổng, Văn phòng vẫn
    rơi vào nhánh "chỉ bản ghi của mình" và 403 ở mọi thao tác vì họ không phải
    tác giả/thành viên của bản ghi nào.
    """
    actor = as_role(role)
    author = as_role("staff")  # tác giả nội bộ, KHÁC người thao tác

    created = publication_service.create_publication(
        db, user=actor,
        payload={"type": "paper", "title": f"Bài báo do {role} nhập", "year": 2025,
                 "journal": "JAD", "category": "domestic", "pub_scope": "domestic",
                 "evidence_url": "https://jad.hcmuaf.edu.vn/1139",
                 "authors": [{"user_id": author.id, "author_order": 1}]},
        correlation_id=None, ip=None,
    )
    assert created["title"] == f"Bài báo do {role} nhập"

    updated = publication_service.update_publication(
        db, user=actor, pub_id=created["id"],
        changes={"journal": "Tạp chí Nông nghiệp và Phát triển"},
        correlation_id=None, ip=None,
    )
    assert updated["journal"] == "Tạp chí Nông nghiệp và Phát triển"

    publication_service.delete_publication(
        db, user=actor, pub_id=created["id"], correlation_id=None, ip=None,
    )


def test_office_can_write_project_and_teaching(db, as_role):
    """Văn phòng ghi được cả đề tài lẫn môn giảng dạy của người khác."""
    office = as_role("office")
    lecturer = as_role("staff")

    proj = project_service.create_project(
        db, user=office,
        payload={"title": "Đề tài do Văn phòng tổng hợp", "level": "institution",
                 "lead_user_id": lecturer.id,
                 "members": [{"user_id": lecturer.id, "role_in_project": "lead"}]},
        correlation_id=None, ip=None,
    )
    assert proj["lead_user_id"] == lecturer.id

    course = teaching_service.create_teaching(
        db, user=office,
        payload={"user_id": lecturer.id, "course_name": "Kiểm nghiệm vi sinh",
                 "year": 2025, "hk3_practice_hours": 540},
        correlation_id=None, ip=None,
    )
    assert course["hk3_practice_hours"] == 540

    teaching_service.delete_teaching(
        db, user=office, tid=course["id"], correlation_id=None, ip=None,
    )
    project_service.delete_project(
        db, user=office, project_id=proj["id"], correlation_id=None, ip=None,
    )


def test_staff_still_scoped_to_own_records(db, as_role):
    """Mở quyền cho Văn phòng KHÔNG được nới lỏng phạm vi của staff."""
    owner = as_role("staff")
    course = teaching_service.create_teaching(
        db, user=owner,
        payload={"user_id": owner.id, "course_name": "Môn của owner", "year": 2025},
        correlation_id=None, ip=None,
    )
    intruder = as_role("staff")
    with pytest.raises(AppException) as e:
        teaching_service.update_teaching(
            db, user=intruder, tid=course["id"],
            changes={"hk3_theory_hours": 999}, correlation_id=None, ip=None,
        )
    assert e.value.http_status == 403

    with pytest.raises(AppException):
        teaching_service.create_teaching(
            db, user=intruder,
            payload={"user_id": owner.id, "course_name": "Khai hộ", "year": 2025},
            correlation_id=None, ip=None,
        )
