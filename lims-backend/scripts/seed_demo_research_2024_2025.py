"""Seed dữ liệu DEMO cho nhóm NCKH & Đào tạo — đủ để nhìn thấy mọi thay đổi của m34.

VÌ SAO KHÔNG DÙNG import_activities_2024_2025.py: script đó nhắm vào một bản
workbook CŨ hơn. Chạy dry-run trên "…2024-2025(1).xlsx" cho ra 8 "hợp đồng" thực
chất là các dòng báo cáo hội nghị (vùng dòng r75-83 giờ là bảng hội nghị, bảng
hợp đồng đã dời xuống r88-101). Nó cũng không ghi các cột m34. Dữ liệu lệch còn
khó soi hơn không có dữ liệu, nên demo dùng bộ mẫu tuyển chọn ở đây.

Dữ liệu lấy nguyên văn từ file Excel thật, nhưng CHỌN LỌC để mỗi cột mới và mỗi
nhánh mới đều có ít nhất một bản ghi minh hoạ:

  evidence_url        → có ở cả 6 bảng
  patent_kind         → đủ 3 nhóm: sáng chế · GPHI · giống cây trồng
  training_level      → đủ 2 bậc: đại học · sau đại học
  cert_kind           → đủ 2 danh sách: lớp ngắn hạn · tập huấn an toàn PTN
  contract_no/signed_date → 3 hợp đồng
  hk3_*               → 1 môn dạy cả ba học kỳ, 1 môn chỉ dạy HK3
  type='conference'   → 2 báo cáo kỷ yếu (trước m34 không nhập được qua giao diện)
  chủ nhiệm/thành viên/giảng viên NGOÀI hệ thống → 1 đề tài + 1 môn
  pub_scope + 4 cờ chỉ mục → công bố trong nước, SCIE, Scopus

IDEMPOTENT: mọi bản ghi demo mang dấu DEMO_TAG trong một trường văn bản. Chạy lại
sẽ xoá sạch bản ghi mang dấu đó rồi tạo lại, nên không nhân bản dữ liệu.

Chạy:
    docker exec <api> python scripts/seed_demo_research_2024_2025.py --dry-run
    docker exec <api> python scripts/seed_demo_research_2024_2025.py
    docker exec <api> python scripts/seed_demo_research_2024_2025.py --purge   # chỉ xoá
"""
import argparse
import sys
from datetime import date

sys.path.insert(0, "/app")

from sqlalchemy import select  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.models.department import Department  # noqa: E402
from app.models.hr import CatalogBase  # noqa: E402,F401  (giữ import để lỗi tách file lộ sớm)
from app.models.research import (  # noqa: E402
    CommunityService,
    ProjectMember,
    Publication,
    PublicationAuthor,
    ResearchContract,
    ResearchProject,
    StaffActivity,
    StudentMentorship,
    TeachingCourse,
    TrainingCertificate,
)
from app.models.user import User  # noqa: E402

ACADEMIC_YEAR = "2024-2025"

# Dấu nhận biết bản ghi demo. Nằm trong cột văn bản của CHÍNH bảng đó để lệnh xoá
# không phải join — quan trọng khi chạy trên DB có sẵn dữ liệu thật.
DEMO_TAG = "[DEMO-m34]"

# Giảng viên demo — tên lấy từ file Excel. Mật khẩu đặt chung, chỉ dùng để đăng nhập
# thử; script KHÔNG động vào tài khoản đã tồn tại.
DEMO_PASSWORD = "Lims@1234"
LECTURERS = [
    ("manh.demo", "Nguyễn Công Mạnh"),
    ("ly.demo", "Trịnh Thị Phi Ly"),
    ("hong.demo", "Phùng Võ Cẩm Hồng"),
    ("biet.demo", "Huỳnh Văn Biết"),
    ("van.demo", "Trần Thị Vân"),
    ("hoang.demo", "Trương Phước Thiên Hoàng"),
]


# ────────────────────────────────────────────────────────── tiện ích

def _ensure_users(db, domain: str, dry_run: bool) -> dict:
    """Trả {tên đầy đủ: user_id}. Tạo tài khoản còn thiếu, bỏ qua tài khoản đã có."""
    from app.services import user_service

    admin = db.execute(select(User).where(User.role == "admin").limit(1)).scalar_one_or_none()
    if admin is None:
        raise SystemExit(
            "Không tìm thấy tài khoản admin nào — chạy sau khi API đã khởi động lần đầu "
            "(SEED_ADMIN_EMAIL) hoặc chạy scripts/seed_role_accounts.py trước."
        )
    dept = db.execute(select(Department).limit(1)).scalar_one_or_none()

    out, created = {}, 0
    for local, full_name in LECTURERS:
        email = f"{local}@{domain}"
        u = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if u is None:
            if dry_run:
                out[full_name] = None
                created += 1
                continue
            user_service.create_user(
                db, actor_id=admin.id, email=email, full_name=full_name,
                role="staff", department_id=dept.id if dept else None,
                password=DEMO_PASSWORD, is_dept_lead=False,
                correlation_id=None, ip=None,
            )
            u = db.execute(select(User).where(User.email == email)).scalar_one()
            created += 1
        out[full_name] = u.id
    return {"map": out, "created": created, "admin_id": admin.id,
            "dept_id": dept.id if dept else None}


def purge(db) -> dict:
    """Xoá mọi bản ghi mang DEMO_TAG. Con trước cha để không vướng khoá ngoại."""
    counts = {}

    pub_ids = [r[0] for r in db.execute(
        select(Publication.id).where(Publication.title.contains(DEMO_TAG))).all()]
    proj_ids = [r[0] for r in db.execute(
        select(ResearchProject.id).where(ResearchProject.title.contains(DEMO_TAG))).all()]

    if pub_ids:
        db.query(PublicationAuthor).filter(PublicationAuthor.publication_id.in_(pub_ids)).delete(
            synchronize_session=False)
    if proj_ids:
        db.query(ProjectMember).filter(ProjectMember.project_id.in_(proj_ids)).delete(
            synchronize_session=False)

    for model, col in (
        (Publication, Publication.title),
        (ResearchProject, ResearchProject.title),
        (ResearchContract, ResearchContract.title),
        (TeachingCourse, TeachingCourse.course_name),
        (StaffActivity, StaffActivity.content),
        (TrainingCertificate, TrainingCertificate.recipient_name),
        (CommunityService, CommunityService.content),
        (StudentMentorship, StudentMentorship.student_name),
    ):
        n = db.query(model).filter(col.contains(DEMO_TAG)).delete(synchronize_session=False)
        counts[model.__tablename__] = n
    return counts


def _tag(text: str) -> str:
    return f"{text} {DEMO_TAG}"


# ────────────────────────────────────────────────────────── dữ liệu demo

def seed(db, users: dict, dept_id) -> dict:
    uid = users.__getitem__
    rep = {}

    # ═══ ĐỀ TÀI NCKH — kinh phí, chuyển giao, minh chứng, chủ nhiệm ngoài HT ═══
    projects = [
        dict(
            title=_tag("Đánh giá ảnh hưởng của sản phẩm than sinh học (Biochar) từ vỏ sầu riêng "
                       "đến sinh trưởng cây trồng"),
            level="institution", lead=uid("Nguyễn Công Mạnh"), lead_ext=None,
            start=date(2025, 1, 1), end=date(2027, 12, 31), budget="100000000",
            transferred=False, product=None,
            evidence="https://drive.google.com/drive/folders/demo-biochar",
            members=[(uid("Nguyễn Công Mạnh"), None, "lead")],
        ),
        dict(
            # Chủ nhiệm VÀ phần lớn thành viên đều ngoài hệ thống — nhánh trước m34 chặn.
            title=_tag("Mô hình canh tác nông nghiệp tuần hoàn quy mô nông hộ tại tỉnh Tây Ninh"),
            level="national_program", lead=None, lead_ext="Trương Phước Thiên Hoàng",
            start=date(2024, 1, 1), end=date(2025, 12, 31), budget="980000000",
            transferred=True, product="Quy trình canh tác tuần hoàn quy mô nông hộ",
            evidence="https://drive.google.com/drive/folders/demo-tuanhoan",
            members=[(None, "Trương Phước Thiên Hoàng", "lead"),
                     (None, "Nguyễn Phú Hoà", "member"),
                     (None, "Phan Thị Xuân Trang", "member"),
                     (uid("Trần Thị Vân"), None, "member")],
        ),
        dict(
            title=_tag("Nghiên cứu tạo chế phẩm vi sinh vật vùng rễ kiểm soát tuyến trùng "
                       "Meloidogyne spp. trên cây rau"),
            level="ministry", lead=uid("Trần Thị Vân"), lead_ext=None,
            start=date(2025, 1, 1), end=date(2026, 12, 31), budget="460000000",
            transferred=True, product="Chế phẩm vi sinh vật vùng rễ",
            evidence="https://drive.google.com/drive/folders/demo-tuyentrung",
            members=[(uid("Trần Thị Vân"), None, "lead"),
                     (uid("Trương Phước Thiên Hoàng"), None, "member")],
        ),
        dict(
            title=_tag("Phát triển quy trình sản xuất phân hữu cơ tận dụng phế phụ phẩm "
                       "nông nghiệp tại huyện Cần Đước"),
            level="province", lead=uid("Huỳnh Văn Biết"), lead_ext=None,
            start=date(2025, 1, 1), end=date(2026, 12, 31), budget="803952000",
            transferred=False, product=None,
            evidence="https://drive.google.com/drive/folders/demo-phanhuuco",
            members=[(uid("Huỳnh Văn Biết"), None, "lead")],
        ),
    ]
    for p in projects:
        proj = ResearchProject(
            title=p["title"], level=p["level"],
            lead_user_id=p["lead"], lead_external_name=p["lead_ext"],
            department_id=dept_id, start_date=p["start"], end_date=p["end"],
            academic_year=ACADEMIC_YEAR, budget_amount=p["budget"], budget_currency="VND",
            is_transferred=p["transferred"], transfer_product=p["product"],
            evidence_url=p["evidence"], status="ongoing",
        )
        db.add(proj)
        db.flush()
        for u, ext, role in p["members"]:
            db.add(ProjectMember(project_id=proj.id, user_id=u, external_name=ext,
                                 role_in_project=role))
    rep["research_projects"] = len(projects)

    # ═══ CÔNG BỐ — trong nước / quốc tế (cờ chỉ mục) / hội nghị / 3 loại văn bằng ═══
    pubs = [
        dict(type="paper", scope="domestic", category="domestic",
             title=_tag("Optimization of alkali-catalyzed organosolv treatment of spent coffee "
                        "grounds for obtaining polysaccharides"),
             journal="The Journal of Agriculture and Development 23(6), 38-49", year=2025,
             doi="10.52997/jad.6.06.2025",
             evidence="https://jad.hcmuaf.edu.vn/index.php/jad/article/view/1139",
             authors=[(uid("Trịnh Thị Phi Ly"), None, True, "corresponding"),
                      (None, "Duong T. T. Nguyen", False, "co")]),
        dict(type="paper", scope="international", category="isi_q1",
             title=_tag("Cellulose nanofibers boost soil water availability, plant growth, and "
                        "irrigation water use efficiency under deficit irrigation"),
             journal="Catena", year=2025, scie=True,
             evidence="https://www.sciencedirect.com/science/article/pii/S0341816225003005",
             authors=[(uid("Nguyễn Công Mạnh"), None, False, "co"),
                      (None, "An Thuy Ngo", False, "co")]),
        dict(type="paper", scope="international", category="scopus",
             title=_tag("Enhancing bioactive compounds from coffee cascara via enzymatic "
                        "treatment and microbial fermentation"),
             journal="Coffee Science", year=2025, scopus=True,
             evidence="https://doi.org/10.25186/demo-coffee",
             authors=[(uid("Trịnh Thị Phi Ly"), None, True, "corresponding")]),
        dict(type="conference", scope=None, category=None,
             title=_tag("Đánh giá tác động môi trường đất và nước dưới đất tại khu vực thi công "
                        "cọc khoan nhồi — Sân bay Quốc tế Long Thành"),
             journal="Hội thảo khoa học Quốc gia lần thứ V “Môi trường và phát triển bền vững "
                     "— CESD 2025”, ĐHQG Hà Nội",
             year=2025, evidence="https://cres.edu.vn/cesd-2025/",
             authors=[(uid("Nguyễn Công Mạnh"), None, False, "main")]),
        dict(type="conference", scope=None, category=None,
             title=_tag("Hiệu quả ức chế Fusarium oxysporum của cao chiết lá Điều giàu polyphenol"),
             journal="Kỷ yếu Hội nghị Khoa học toàn quốc về Công nghệ sinh học 2024",
             year=2024,
             evidence="https://huib.hueuni.edu.vn/hoi-nghi/nam-2024/bao-cao-khoa-hoc/toan-van/",
             authors=[(uid("Trịnh Thị Phi Ly"), None, True, "corresponding")]),
        dict(type="patent", kind="invention",
             title=_tag("Chủng vi khuẩn Bacillus subtilis B5 chuyển hóa Nitơ trong môi trường "
                        "nước mặn"),
             year=2025, patent_no="VN 1-0038521", authority="Cục Sở hữu trí tuệ",
             app_no="1-2022-04521", app_date=date(2022, 8, 15), granted=date(2025, 3, 20),
             holder="Trường Đại học Nông Lâm TP.HCM",
             evidence="https://ipvietnam.gov.vn/demo/1-0038521",
             authors=[(uid("Trương Phước Thiên Hoàng"), None, False, "main")]),
        dict(type="patent", kind="utility_solution",
             title=_tag("Quy trình sản xuất chế phẩm nấm nội cộng sinh AM dạng bột"),
             year=2025, patent_no="VN 2-0002914", authority="Cục Sở hữu trí tuệ",
             app_no="2-2023-00187", app_date=date(2023, 4, 6), granted=date(2025, 6, 10),
             holder="Viện NC Công nghệ Sinh học và Môi trường",
             evidence="https://ipvietnam.gov.vn/demo/2-0002914",
             authors=[(uid("Trương Phước Thiên Hoàng"), None, False, "main"),
                      (uid("Trần Thị Vân"), None, False, "co")]),
        dict(type="patent", kind="plant_variety",
             title=_tag("Giống bưởi da xanh BĐX-01 kháng bệnh vàng lá thối rễ"),
             year=2025, patent_no="BVTG 2025-014",
             authority="Cục Trồng trọt — Bộ Nông nghiệp và Phát triển nông thôn",
             app_no="TT-2022-0091", app_date=date(2022, 11, 2), granted=date(2025, 5, 28),
             holder="Trường Đại học Nông Lâm TP.HCM",
             evidence="https://pvpo.mard.gov.vn/demo/2025-014",
             authors=[(uid("Huỳnh Văn Biết"), None, False, "main")]),
    ]
    for p in pubs:
        pub = Publication(
            type=p["type"], title=p["title"], journal=p.get("journal"), year=p["year"],
            doi=p.get("doi"), category=p.get("category"), pub_scope=p.get("scope"),
            is_scie=p.get("scie", False), is_ssci=p.get("ssci", False),
            is_scopus=p.get("scopus", False), is_aci=p.get("aci", False),
            academic_year=ACADEMIC_YEAR, department_id=dept_id,
            patent_no=p.get("patent_no"), patent_kind=p.get("kind"),
            issuing_authority=p.get("authority"), application_no=p.get("app_no"),
            application_date=p.get("app_date"), granted_date=p.get("granted"),
            patent_holder=p.get("holder"), evidence_url=p.get("evidence"),
        )
        db.add(pub)
        db.flush()
        for order, (u, ext, corr, role) in enumerate(p["authors"], start=1):
            db.add(PublicationAuthor(publication_id=pub.id, author_order=order,
                                     user_id=u, external_name=ext,
                                     is_corresponding=corr, author_role=role))
    rep["publications"] = len(pubs)

    # ═══ HỢP ĐỒNG — số hợp đồng + ngày ký (Excel gộp chung một ô) ═══
    contracts = [
        ("Nghiên cứu Phân tích mẫu củ khoai tây", "Nghiên cứu KHCN", "PUR.2024.00618",
         date(2024, 9, 23), "304776000", "CÔNG TY TNHH THỰC PHẨM PEPSICO VIỆT NAM",
         date(2024, 9, 1), date(2024, 10, 31), "https://drive.google.com/demo/hd-pepsico"),
        ("Tư vấn giám sát vận hành thử nghiệm công trình xử lý chất thải", "Tư vấn KHCN",
         "04/HĐDVMT/2025", date(2025, 5, 5), "52000000",
         "CÔNG TY CỔ PHẦN GIẢI PHÁP TOÀN DIỆN HKM",
         date(2025, 5, 1), date(2025, 6, 30), "https://drive.google.com/demo/hd-hkm"),
        ("Tư vấn xây dựng trại nấm và chuyển giao quy trình sản xuất nấm Linh Chi",
         "Tư vấn chuyển giao", "0408/HĐCG-2025", date(2025, 8, 4), "120000000",
         "Công ty Cổ phần Nông Nghiệp The Moshav Farm",
         date(2025, 8, 1), date(2026, 8, 31), "https://drive.google.com/demo/hd-moshav"),
    ]
    for title, ctype, no, signed, val, partner, start, end, ev in contracts:
        db.add(ResearchContract(
            title=_tag(title), contract_type=ctype, contract_no=no, signed_date=signed,
            value_amount=val, currency="VND", partner_org=partner,
            start_date=start, end_date=end, academic_year=ACADEMIC_YEAR,
            evidence_url=ev, department_id=dept_id))
    rep["research_contracts"] = len(contracts)

    # ═══ GIẢNG DẠY — bậc ĐH/SĐH, học kỳ 3, giảng viên thỉnh giảng ═══
    #      (giảng viên, môn, bậc, hk1_lt, hk1_th, hk2_lt, hk2_th, hk3_lt, hk3_th)
    courses = [
        ("Nguyễn Công Mạnh", "PP lấy mẫu môi trường", "undergraduate", None, 30, None, None, None, None),
        ("Nguyễn Công Mạnh", "Công nghệ xử lý chất thải rắn", "undergraduate", None, None, None, 30, None, None),
        # Môn dạy CẢ BA học kỳ — trường hợp mà mô hình cột-theo-kỳ sinh ra để phục vụ.
        ("Phùng Võ Cẩm Hồng", "Hệ thống quản lý chất lượng", "undergraduate", 120, None, 30, None, 45, 15),
        ("Phùng Võ Cẩm Hồng", "Phương pháp xét nghiệm sinh hóa", "undergraduate", None, 60, None, 120, None, None),
        ("Huỳnh Văn Biết", "Sinh học phân tử", "undergraduate", 45, 30, None, None, None, None),
        ("Trần Thị Vân", "Phát triển sản phẩm sinh học", "undergraduate", None, None, None, 120, None, None),
        ("Trịnh Thị Phi Ly", "Năng lượng sinh học", "postgraduate", None, None, 30, None, None, None),
        ("Huỳnh Văn Biết", "Bộ gen học", "postgraduate", None, None, 30, None, None, None),
        # Môn CHỈ dạy học kỳ hè — trước m34 không khai được ở đâu cả.
        ("Trương Phước Thiên Hoàng", "Thực hành kiểm nghiệm vi sinh (học kỳ hè)",
         "undergraduate", None, None, None, None, 30, 60),
    ]
    for name, course, level, h1t, h1p, h2t, h2p, h3t, h3p in courses:
        db.add(TeachingCourse(
            user_id=uid(name), course_name=_tag(course), training_level=level,
            year=2025, academic_year=ACADEMIC_YEAR,
            hk1_theory_hours=h1t, hk1_practice_hours=h1p,
            hk2_theory_hours=h2t, hk2_practice_hours=h2p,
            hk3_theory_hours=h3t, hk3_practice_hours=h3p,
            department_id=dept_id,
            evidence_url="https://drive.google.com/demo/thoi-khoa-bieu-2024-2025"))
    # Giảng viên thỉnh giảng (ngoài hệ thống) — nhánh XOR lecturer_external_name.
    db.add(TeachingCourse(
        user_id=None, lecturer_external_name="TS. Lê Phước Thọ (thỉnh giảng)",
        course_name=_tag("Công nghệ lên men công nghiệp"), training_level="postgraduate",
        year=2025, academic_year=ACADEMIC_YEAR, hk3_theory_hours=30,
        note="Giảng viên mời từ đơn vị ngoài",
        evidence_url="https://drive.google.com/demo/tkb-thinh-giang"))
    rep["teaching_courses"] = len(courses) + 1

    # ═══ HƯỚNG DẪN SINH VIÊN ═══
    mentorships = [
        ("Nguyễn Thị Ngọc Ánh", "Khảo sát khả năng đối kháng của Trichoderma spp.",
         "thesis_bachelor", uid("Trần Thị Vân")),
        ("Phạm Minh Tâm", "Đánh giá đa dạng di truyền Chlorella sp. tại Nam Bộ",
         "thesis_master", uid("Huỳnh Văn Biết")),
        ("Vũ Ngọc Khánh Như", "Nấm nội cộng sinh AM trên cây bưởi da xanh",
         "student_research", uid("Trương Phước Thiên Hoàng")),
    ]
    for student, topic, mtype, mentor in mentorships:
        db.add(StudentMentorship(mentor_id=mentor, student_name=_tag(student), topic=topic,
                                 year=2025, type=mtype, department_id=dept_id))
    rep["student_mentorships"] = len(mentorships)

    # ═══ CÔNG TÁC KHÁC — Đảng / Công đoàn / VILAS, kèm minh chứng ═══
    activities = [
        ("dang", "Tổ chức sinh hoạt chi bộ định kỳ và học tập nghị quyết năm 2025",
         date(2025, 3, 15), "https://photos.google.com/demo/chi-bo"),
        ("cong_doan", "Giải nhất Hội thi “Mâm cơm Đoàn viên Ngày Tết” 2025",
         date(2025, 2, 3), "https://photos.google.com/demo/mam-com-doan-vien"),
        ("cong_doan", "Bằng khen của Liên đoàn Lao động TP.HCM cho tập thể Công đoàn Viện",
         date(2025, 7, 28), "https://drive.google.com/demo/bang-khen-ldld"),
        ("vilas", "Duy trì và mở rộng phạm vi công nhận ISO/IEC 17025 — đợt đánh giá 2025",
         date(2025, 6, 12), "https://drive.google.com/demo/vilas-2025"),
    ]
    for kind, content, when, ev in activities:
        db.add(StaffActivity(kind=kind, content=_tag(content), performed_at=when,
                             academic_year=ACADEMIC_YEAR, evidence_url=ev,
                             department_id=dept_id))
    rep["staff_activities"] = len(activities)

    # ═══ CHỨNG NHẬN ĐÀO TẠO — hai danh sách tách bằng cert_kind ═══
    certs = [
        ("Nguyễn Thị Mai Anh", "GCN-2025-018", "short_course",
         "Lớp ngắn hạn: Kỹ thuật PCR ứng dụng", date(2025, 4, 18)),
        ("Trần Quốc Bảo", "GCN-2025-019", "short_course",
         "Lớp ngắn hạn: Kỹ thuật PCR ứng dụng", date(2025, 4, 18)),
        ("Lê Hoàng Nam", "ATPTN-2025-104", "lab_safety",
         "Tập huấn an toàn phòng thí nghiệm và PCCC", date(2025, 9, 6)),
        ("Đỗ Thuỳ Linh", "ATPTN-2025-105", "lab_safety",
         "Tập huấn an toàn phòng thí nghiệm và PCCC", date(2025, 9, 6)),
    ]
    for name, no, kind, course, when in certs:
        db.add(TrainingCertificate(
            recipient_name=_tag(name), certificate_no=no, cert_kind=kind,
            course_name=course, issued_date=when, academic_year=ACADEMIC_YEAR,
            department_id=dept_id))
    rep["training_certificates"] = len(certs)

    # ═══ PHỤC VỤ CỘNG ĐỒNG ═══
    community = [
        ("Tập huấn kỹ thuật ủ phân hữu cơ cho nông hộ tại huyện Cần Đước",
         date(2025, 5, 20), "UBND huyện Cần Đước", uid("Huỳnh Văn Biết")),
        ("Hoạt động vệ sinh môi trường nhân Ngày Môi trường Thế giới 5/6/2025",
         date(2025, 6, 5), "Công đoàn Viện", uid("Nguyễn Công Mạnh")),
    ]
    for content, when, host, performer in community:
        db.add(CommunityService(
            content=_tag(content), performed_at=when, host=host,
            performer_user_id=performer, department_id=dept_id,
            evidence_url="https://photos.google.com/demo/phuc-vu-cong-dong"))
    rep["community_services"] = len(community)

    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="Chỉ in số lượng, không ghi DB")
    ap.add_argument("--purge", action="store_true", help="Chỉ xoá bản ghi demo rồi thoát")
    ap.add_argument("--domain", default="lims.local", help="Tên miền email giảng viên demo")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        if args.purge:
            counts = purge(db)
            db.commit()
            print("=== ĐÃ XOÁ dữ liệu demo ===")
            for k, v in counts.items():
                print(f"  {k}: {v}")
            return 0

        info = _ensure_users(db, args.domain, args.dry_run)
        if args.dry_run:
            db.rollback()
            print("=== DRY-RUN — không ghi DB ===")
            print(f"  tài khoản giảng viên sẽ tạo: {info['created']}")
            print("  bản ghi sẽ tạo: 4 đề tài · 8 công bố · 3 hợp đồng · 10 môn giảng dạy ·")
            print("                  3 hướng dẫn SV · 4 công tác khác · 4 GCN · 2 phục vụ CĐ")
            return 0

        removed = purge(db)  # chạy lại không nhân bản
        rep = seed(db, info["map"], info["dept_id"])
        db.commit()

        print("=== ĐÃ SEED dữ liệu demo NCKH & Đào tạo ===")
        if sum(removed.values()):
            print(f"  (dọn {sum(removed.values())} bản ghi demo của lần chạy trước)")
        print(f"  tài khoản giảng viên mới: {info['created']} (mật khẩu {DEMO_PASSWORD})")
        for k, v in rep.items():
            print(f"  {k}: {v}")
        print(f"\n  Mọi bản ghi mang dấu {DEMO_TAG} — xoá sạch bằng --purge.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
