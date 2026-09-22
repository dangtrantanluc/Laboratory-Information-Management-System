"""Xuất Excel DANH SÁCH cho từng mục Nghiên cứu & Đào tạo, lọc theo khoảng thời gian.

KHÁC research_report_service
File đó xuất BÁO CÁO TỔNG HỢP (§6.2) — mỗi chỉ tiêu một con số. File này xuất DANH
SÁCH CHI TIẾT: mỗi bản ghi một dòng, đủ cột để đối chiếu và nộp kèm hồ sơ.

TÁI DÙNG HÀM list_* THAY VÌ TRUY VẤN LẠI
Phạm vi xem theo vai trò nằm SẴN trong các hàm list_* (ví dụ
publication_service.list_publications ép author_filter = chính mình khi user không
phải nhóm xem-tất-cả). Viết truy vấn riêng ở đây là chép lại luật phân quyền lần thứ
hai, và hai bản sẽ lệch nhau sau vài tháng. Đổi lại, file xuất ra LUÔN khớp đúng thứ
người dùng thấy trên màn hình — cùng nguyên tắc report_export_service đang theo.

━━━ KHOẢNG THỜI GIAN LỌC THEO TRƯỜNG NÀO ━━━
Mỗi mục có một "ngày nghiệp vụ" khác nhau, và ba mục CHỈ lưu NĂM chứ không có ngày:

    Đề tài NCKH          ngày bắt đầu      start_date
    Hợp đồng NCKH        ngày ký           signed_date
    Phục vụ cộng đồng    ngày thực hiện    performed_at
    Chứng nhận đào tạo   ngày cấp          issued_date
    Công tác khác        ngày thực hiện    performed_at
    ─────────────────────────────────────────────────
    Công bố & Sáng chế   NĂM công bố       year   ← chỉ có năm
    Hướng dẫn SV         NĂM               year   ← chỉ có năm
    Môn giảng dạy        NĂM học           year   ← chỉ có năm

Với ba mục chỉ có năm, khoảng ngày được quy về khoảng NĂM mà nó phủ (ví dụ
01/06/2024 → 31/03/2025 lấy các bản ghi year ∈ {2024, 2025}). Không thể chính xác
hơn vì dữ liệu gốc không có ngày. Sheet ghi rõ điều này ở phần đầu để người đọc
không hiểu nhầm con số.

BẢN GHI KHÔNG CÓ NGÀY bị loại khi có lọc thời gian — không chứng minh được nó nằm
trong khoảng thì không đưa vào. Nhưng số lượng bị loại được GHI RÕ ở đầu sheet, vì
âm thầm bỏ bớt dòng là cách nhanh nhất làm hỏng một báo cáo.
"""
import io
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.services import activity_service, audit_service
from app.services.research import (
    community_service, mentorship_service, project_service,
    publication_service, teaching_service,
)

# Số dòng mỗi lần gọi list_*. Vòng lặp phân trang dừng theo `total` do chính hàm
# list trả về, nên con số này chỉ ảnh hưởng số round-trip chứ không ảnh hưởng kết quả.
# Dòng chứa tiêu đề cột. Khối đầu trang chiếm 4 dòng + 1 dòng trống ở trên. Khai
# thành hằng số vì cả bộ test lẫn `freeze_panes`/`auto_filter` đều bám vào nó — ba
# chỗ tự đếm lấy là ba chỗ lệch nhau khi đầu trang đổi.
_HEADER_ROW = 6

_PAGE = 200
_MAX_PAGES = 200  # chốt an toàn: 40.000 dòng, đủ xa so với quy mô thật của Viện


@dataclass(frozen=True)
class _Spec:
    """Mô tả một mục xuất: lấy dữ liệu ở đâu, lọc theo ngày nào, in ra cột gì."""

    title: str                      # tên sheet + tiêu đề trong file
    filename: str                   # tên file tải về (không dấu, không khoảng trắng)
    fetch: Callable[..., tuple]     # hàm list_* tương ứng
    columns: list[tuple[str, Callable[[dict], Any]]]
    date_key: Optional[str] = None  # khoá chứa ngày nghiệp vụ
    year_key: Optional[str] = None  # dùng khi bản ghi CHỈ có năm
    date_label: str = ""            # nhãn tiếng Việt của trường lọc
    fetch_kwargs: dict = field(default_factory=dict)
    # Hàm list_* của activity_service KHÔNG nhận `user` (không có scope theo vai trò),
    # nên phải nói rõ ở đây thay vì gọi mù.
    takes_user: bool = True
    # Luật vai trò của endpoint danh sách tương ứng. Thiếu nó thì xuất Excel trở
    # thành đường vòng qua phân quyền — hợp đồng NCKH chứa giá trị tiền.
    guard: Optional[Callable[[CurrentUser], None]] = None


# ───────────────────────── helper lấy giá trị ─────────────────────────
def _g(key: str) -> Callable[[dict], Any]:
    return lambda r: r.get(key)


def _person(primary: str, external: str) -> Callable[[dict], Any]:
    """Người nội bộ hoặc người ngoài Viện — mô hình cho phép cả hai (m34)."""
    return lambda r: r.get(primary) or r.get(external) or ""


def _money(amount: str, currency: str) -> Callable[[dict], Any]:
    """Tiền là SỐ, không phải chuỗi (m48).

    Trước đây trả "980000000.00 VND" — Excel coi là văn bản, nên không cộng được,
    không định dạng phân tách hàng nghìn, và sắp xếp theo thứ tự chữ cái. Cột tổng
    kinh phí của một bảng báo cáo mà không SUM được thì bảng đó phải làm lại bằng tay.
    Đơn vị tiền tách sang cột riêng — xem `_currency`.
    """

    def _fn(r: dict):
        v = r.get(amount)
        if v in (None, ""):
            return ""
        try:
            return float(v)
        except (TypeError, ValueError):
            return str(v)

    _fn.xl_kind = "money"  # type: ignore[attr-defined]
    return _fn


def _currency(currency: str) -> Callable[[dict], Any]:
    return lambda r: r.get(currency) or ""


def _authors(r: dict) -> str:
    """Gộp danh sách tác giả thành một ô, giữ đúng thứ tự đã nhập."""
    out = []
    for a in r.get("authors") or []:
        nm = a.get("name") or a.get("external_name") or ""
        if a.get("is_corresponding"):
            nm += " (tác giả liên hệ)"
        if nm:
            out.append(nm)
    return "; ".join(out)


def _index_flags(r: dict) -> str:
    """Các danh mục chỉ mục của bài báo, gộp vào một ô cho dễ đọc."""
    flags = [c for c, k in (
        ("SCIE", "is_scie"), ("SSCI", "is_ssci"), ("Scopus", "is_scopus"), ("ACI", "is_aci"),
    ) if r.get(k)]
    return ", ".join(flags)


# m47 — nhãn tiếng Việt cho hai phân loại con. File Excel gửi ra ngoài Viện không
# được chứa mã kỹ thuật ('domestic', 'utility_solution'): người đọc là cán bộ tổng hợp,
# không phải lập trình viên.
_SCOPE_LABELS = {"domestic": "Trong nước", "international": "Quốc tế"}
_PATENT_KIND_LABELS = {
    "invention": "Sáng chế",
    "utility_solution": "Giải pháp hữu ích",
    "plant_variety": "Giống cây trồng",
}


def _scope_label(r: dict) -> str:
    # Báo cáo hội nghị không có phạm vi — để trống thay vì bịa một giá trị.
    return _SCOPE_LABELS.get(r.get("pub_scope") or "", "")


def _patent_kind_label(r: dict) -> str:
    return _PATENT_KIND_LABELS.get(r.get("patent_kind") or "", "")


def _pub_type_label(r: dict) -> str:
    return {"paper": "Tạp chí", "conference": "Hội nghị / kỷ yếu"}.get(r.get("type") or "", "")


# ═══════════════════ m48 — DỊCH MÃ KỸ THUẬT SANG TIẾNG VIỆT ═══════════════════
#
# File Excel gửi cho cán bộ tổng hợp và lãnh đạo đang in ra 'national_program',
# 'ongoing', 'cong_doan', 'isi_q1' — mã nội bộ của hệ thống, không phải tiếng Việt.
# Người nhận file phải tự tra nghĩa, hoặc tệ hơn là đoán.
#
# Nhãn giữ KHỚP với giao diện (lib/rbac.ts, types/research.ts, pages/ResearchProjects.tsx):
# cùng một trạng thái mà màn hình gọi "Đang thực hiện" còn Excel gọi "ongoing" thì người
# dùng không nối được hai thứ với nhau.
_STATIC_LABELS: dict[str, dict[str, str]] = {
    "status": {
        "ongoing": "Đang thực hiện",
        "completed": "Hoàn thành",
        "accepted": "Đã nghiệm thu",
        "cancelled": "Đã hủy",
    },
    "kind": {
        "dang": "Công tác Đảng",
        "cong_doan": "Công tác Công đoàn",
        "vilas": "Công tác VILAS",
        "khac": "Khác",
    },
    "training_level": {"undergraduate": "Đại học", "postgraduate": "Sau đại học"},
    "cert_kind": {"short_course": "Lớp ngắn hạn", "lab_safety": "Tập huấn an toàn PTN & PCCC"},
}

# Danh mục nằm ở DB (code → label), nạp một lần mỗi lần xuất. KHÔNG chép cứng vào đây:
# quản trị viên thêm bậc xếp hạng mới thì Excel phải hiểu ngay, không chờ deploy.
_DB_CATALOGS: dict[str, str] = {
    "level": "research_project_levels",
    "category": "publication_categories",
}


def _load_label_maps(db: Session) -> dict[str, dict[str, str]]:
    from sqlalchemy import text as _sql

    maps = {k: dict(v) for k, v in _STATIC_LABELS.items()}
    for col, table in _DB_CATALOGS.items():
        rows = db.execute(_sql(f"SELECT code, label FROM {table}")).all()  # noqa: S608
        maps[col] = {r.code: r.label for r in rows}
    return maps


def _labelled(key: str) -> Callable[[dict], Any]:
    """Lấy giá trị rồi dịch sang nhãn tiếng Việt; không có trong bảng thì giữ nguyên."""

    def _fn(r: dict, _maps: Optional[dict] = None):
        v = r.get(key)
        if v in (None, ""):
            return ""
        return (_maps or {}).get(key, {}).get(str(v), v)

    _fn.needs_labels = True  # type: ignore[attr-defined]
    return _fn


def _teaching_hours(r: dict) -> Any:
    """Tổng giờ cả ba học kỳ — con số mà bảng tổng hợp cuối năm cần."""
    keys = ("hk1_theory_hours", "hk1_practice_hours", "hk2_theory_hours",
            "hk2_practice_hours", "hk3_theory_hours", "hk3_practice_hours")
    total = sum(int(r.get(k) or 0) for k in keys)
    return total or ""


_teaching_hours.xl_kind = "number"  # type: ignore[attr-defined]


# ───────────────────────── định nghĩa 8 mục ─────────────────────────
KINDS: dict[str, _Spec] = {
    "research-projects": _Spec(
        title="Đề tài NCKH",
        filename="de-tai-nckh",
        fetch=project_service.list_projects,
        fetch_kwargs={"q": None, "department_id": None, "level": None, "year": None,
                      "lead_user_id": None, "status_filter": None},
        date_key="start_date",
        date_label="Ngày bắt đầu",
        columns=[
            ("Mã đề tài", _g("code")),
            ("Tên đề tài", _g("title")),
            ("Cấp", _labelled("level")),
            ("Chủ nhiệm", _person("lead_user_name", "lead_external_name")),
            ("Đơn vị", _g("department_name")),
            ("Ngày bắt đầu", _g("start_date")),
            ("Ngày kết thúc", _g("end_date")),
            ("Năm học", _g("academic_year")),
            ("Kinh phí", _money("budget_amount", "budget_currency")),
            ("Đơn vị tiền", _currency("budget_currency")),
            ("Số thành viên", _g("member_count")),
            ("Trạng thái", _labelled("status")),
            ("Đã chuyển giao", lambda r: "x" if r.get("is_transferred") else ""),
            ("Sản phẩm chuyển giao", _g("transfer_product")),
            ("Minh chứng", _g("evidence_url")),
        ],
    ),
    "publications": _Spec(
        title="Công bố khoa học & Sáng chế",
        filename="bai-bao-sang-che",
        fetch=publication_service.list_publications,
        fetch_kwargs={"q": None, "type_filter": None, "year": None, "category": None,
                      "department_id": None, "author_user_id": None},
        year_key="year",
        date_label="Năm công bố",
        columns=[
            ("Loại", _g("type")),
            ("Tên công trình", _g("title")),
            ("Tạp chí / Nhà xuất bản", _g("journal")),
            ("Năm", _g("year")),
            ("DOI", _g("doi")),
            ("Danh mục", _labelled("category")),
            ("Phạm vi", _g("pub_scope")),
            ("Chỉ mục", _index_flags),
            ("Tác giả", _authors),
            ("Số bằng / SC", _g("patent_no")),
            ("Cơ quan cấp", _g("issuing_authority")),
            ("Ngày nộp đơn", _g("application_date")),
            ("Ngày cấp bằng", _g("granted_date")),
            ("Loại SC/GPHI", _g("patent_kind")),
            ("Chủ sở hữu", _g("patent_holder")),
            ("Đơn vị", _g("department_name")),
            ("Năm học", _g("academic_year")),
            ("Minh chứng", _g("evidence_url")),
        ],
    ),
    # ═══ m47 — hai mục TÁCH RIÊNG ═══
    #
    # Mục "publications" gộp ở trên có 18 cột, trong đó 6 cột chỉ có nghĩa với sáng chế
    # và 4 cột chỉ có nghĩa với bài báo — nên mỗi dòng luôn bỏ trống gần nửa số cột, và
    # người nhận file phải tự tách làm hai bảng trước khi dùng được. Hai mục dưới đây
    # chỉ mang cột của chính mình.
    #
    # Mục gộp CỐ Ý giữ lại: báo cáo tổng kết năm vẫn cần một file duy nhất cho toàn bộ
    # công bố, và giữ nó không tốn gì.
    "papers": _Spec(
        title="Công bố khoa học",
        filename="bai-bao",
        fetch=publication_service.list_publications,
        # Công bố trên tạp chí VÀ báo cáo hội nghị — cùng một danh mục nghiệp vụ.
        fetch_kwargs={"q": None, "type_filter": "paper,conference", "year": None,
                      "category": None, "department_id": None, "author_user_id": None},
        year_key="year",
        date_label="Năm công bố",
        columns=[
            ("Loại", _pub_type_label),
            ("Tên công trình", _g("title")),
            ("Tác giả", _authors),
            ("Tạp chí / Kỷ yếu", _g("journal")),
            ("Năm", _g("year")),
            ("Phạm vi", _scope_label),
            ("Chỉ số", _labelled("category")),
            ("Chỉ mục", _index_flags),
            ("DOI", _g("doi")),
            ("Đơn vị", _g("department_name")),
            ("Năm học", _g("academic_year")),
            ("Minh chứng", _g("evidence_url")),
        ],
    ),
    "patents": _Spec(
        title="Sáng chế & Giải pháp hữu ích",
        filename="sang-che-gphi",
        fetch=publication_service.list_publications,
        fetch_kwargs={"q": None, "type_filter": "patent", "year": None,
                      "category": None, "department_id": None, "author_user_id": None},
        year_key="year",
        date_label="Năm công bố",
        columns=[
            # Ba mục I / II / III của bảng sáng chế trong file Excel gốc của Viện.
            ("Loại", _patent_kind_label),
            ("Tên công trình", _g("title")),
            ("Tác giả", _authors),
            ("Số bằng", _g("patent_no")),
            ("Số đơn", _g("application_no")),
            ("Ngày nộp đơn", _g("application_date")),
            ("Ngày cấp bằng", _g("granted_date")),
            ("Cơ quan cấp", _g("issuing_authority")),
            ("Chủ bằng", _g("patent_holder")),
            ("Năm", _g("year")),
            ("Đơn vị", _g("department_name")),
            ("Năm học", _g("academic_year")),
            ("Minh chứng", _g("evidence_url")),
        ],
    ),
    "research-contracts": _Spec(
        title="Hợp đồng NCKH",
        filename="hop-dong-nckh",
        fetch=activity_service.list_contracts,
        fetch_kwargs={"academic_year": None, "department_id": None, "q": None},
        takes_user=False,
        guard=activity_service.assert_contract_read,
        date_key="signed_date",
        date_label="Ngày ký",
        columns=[
            ("Tên hợp đồng", _g("title")),
            ("Loại", _g("contract_type")),
            ("Số hợp đồng", _g("contract_no")),
            ("Ngày ký", _g("signed_date")),
            ("Giá trị", _money("value_amount", "currency")),
            ("Đơn vị tiền", _currency("currency")),
            ("Đối tác", _g("partner_org")),
            ("Ngày bắt đầu", _g("start_date")),
            ("Ngày kết thúc", _g("end_date")),
            ("Năm học", _g("academic_year")),
            ("Đơn vị", _g("department_name")),
            ("Minh chứng", _g("evidence_url")),
        ],
    ),
    "community-services": _Spec(
        title="Phục vụ cộng đồng",
        filename="phuc-vu-cong-dong",
        fetch=community_service.list_community,
        fetch_kwargs={"performer_user_id": None, "year": None, "date_from": None,
                      "date_to": None, "department_id": None},
        date_key="performed_at",
        date_label="Ngày thực hiện",
        columns=[
            ("Nội dung", _g("content")),
            ("Ngày thực hiện", _g("performed_at")),
            ("Đơn vị tổ chức", _g("host")),
            ("Người thực hiện", _g("performer_name")),
            ("Đơn vị", _g("department_name")),
            ("Minh chứng", _g("evidence_url")),
        ],
    ),
    "student-mentorships": _Spec(
        title="Hướng dẫn sinh viên",
        filename="huong-dan-sinh-vien",
        fetch=mentorship_service.list_mentorships,
        fetch_kwargs={"mentor_id": None, "year": None, "type_filter": None,
                      "department_id": None},
        year_key="year",
        date_label="Năm",
        columns=[
            ("Sinh viên", _g("student_name")),
            ("Đề tài", _g("topic")),
            ("Hình thức", _g("type")),
            ("Năm", _g("year")),
            ("Người hướng dẫn", _g("mentor_name")),
            ("Đơn vị", _g("department_name")),
        ],
    ),
    "teaching-courses": _Spec(
        title="Môn giảng dạy",
        filename="mon-giang-day",
        fetch=teaching_service.list_teaching,
        fetch_kwargs={"user_id": None, "year": None, "semester": None,
                      "department_id": None},
        year_key="year",
        date_label="Năm học",
        columns=[
            ("Môn học", _g("course_name")),
            ("Bậc đào tạo", _labelled("training_level")),
            ("Học kỳ", _g("semester")),
            ("Năm", _g("year")),
            ("Năm học", _g("academic_year")),
            ("Giảng viên", _person("user_name", "lecturer_external_name")),
            ("HK1 LT", _g("hk1_theory_hours")),
            ("HK1 TH", _g("hk1_practice_hours")),
            ("HK2 LT", _g("hk2_theory_hours")),
            ("HK2 TH", _g("hk2_practice_hours")),
            ("HK3 LT", _g("hk3_theory_hours")),
            ("HK3 TH", _g("hk3_practice_hours")),
            ("Tổng giờ", _teaching_hours),
            ("Đơn vị", _g("department_name")),
            ("Ghi chú", _g("note")),
            ("Minh chứng", _g("evidence_url")),
        ],
    ),
    "training-certificates": _Spec(
        title="Chứng nhận đào tạo",
        filename="chung-nhan-dao-tao",
        fetch=activity_service.list_certificates,
        fetch_kwargs={"academic_year": None, "q": None},
        takes_user=False,
        date_key="issued_date",
        date_label="Ngày cấp",
        columns=[
            ("Người được cấp", _g("recipient_name")),
            ("Số chứng nhận", _g("certificate_no")),
            ("Loại", _labelled("cert_kind")),
            ("Khoá đào tạo", _g("course_name")),
            ("Ngày cấp", _g("issued_date")),
            ("Người phụ trách", _g("host_name")),
            ("Năm học", _g("academic_year")),
            ("Ghi chú", _g("note")),
        ],
    ),
    "staff-activities": _Spec(
        title="Công tác khác",
        filename="cong-tac-khac",
        fetch=activity_service.list_activities,
        fetch_kwargs={"kind": None, "academic_year": None},
        takes_user=False,
        date_key="performed_at",
        date_label="Ngày thực hiện",
        columns=[
            ("Loại công tác", _labelled("kind")),
            ("Nội dung", _g("content")),
            ("Ngày thực hiện", _g("performed_at")),
            ("Người thực hiện", _g("performer_name")),
            ("Năm học", _g("academic_year")),
            ("Minh chứng", _g("evidence_url")),
        ],
    ),
}


def kind_options() -> list[dict]:
    """Danh mục mục xuất được — giao diện dựng nút từ đây, không hard-code."""
    return [
        {"kind": k, "label": s.title, "filter_field": s.date_label,
         "granularity": "year" if s.year_key else "date"}
        for k, s in KINDS.items()
    ]


def _get_spec(kind: str) -> _Spec:
    spec = KINDS.get(kind)
    if spec is None:
        raise AppException(
            ErrorCode.NOT_FOUND,
            f"Không có mục '{kind}' để xuất. Hợp lệ: {', '.join(KINDS)}",
            404,
        )
    return spec


def _fetch_all(db: Session, user: CurrentUser, spec: _Spec) -> list[dict]:
    """Gom hết bản ghi trong PHẠM VI XEM của người dùng, lần theo `total` của list_*."""
    out: list[dict] = []
    page = 1
    extra = {"user": user} if spec.takes_user else {}
    while page <= _MAX_PAGES:
        rows, total = spec.fetch(db, page=page, limit=_PAGE, **extra, **spec.fetch_kwargs)
        out.extend(rows)
        if not rows or len(out) >= total:
            break
        page += 1
    return out


def _as_date(v) -> Optional[date]:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    return None


def _filter_period(
    rows: list[dict], spec: _Spec, date_from: Optional[date], date_to: Optional[date]
) -> tuple[list[dict], int]:
    """Lọc theo khoảng thời gian. Trả (dòng giữ lại, số dòng bị loại vì thiếu ngày)."""
    if date_from is None and date_to is None:
        return rows, 0

    kept, skipped = [], 0
    for r in rows:
        if spec.year_key:
            # Bản ghi chỉ có NĂM: quy khoảng ngày về khoảng năm mà nó phủ.
            y = r.get(spec.year_key)
            if y in (None, ""):
                skipped += 1
                continue
            y = int(y)
            if date_from and y < date_from.year:
                continue
            if date_to and y > date_to.year:
                continue
        else:
            d = _as_date(r.get(spec.date_key))
            if d is None:
                # Không chứng minh được nằm trong khoảng → loại, nhưng có ĐẾM.
                skipped += 1
                continue
            if date_from and d < date_from:
                continue
            if date_to and d > date_to:
                continue
        kept.append(r)
    return kept, skipped


def _build_xlsx(
    spec: _Spec, rows: list[dict], *, user: CurrentUser,
    date_from: Optional[date], date_to: Optional[date], skipped: int,
    label_maps: Optional[dict] = None,
) -> bytes:
    """Dựng file Excel (m48 — làm lại bố cục).

    NHỮNG GÌ BẢN CŨ LÀM KHÓ NGƯỜI DÙNG, và cách sửa:

    · Ngày là CHUỖI "2025-03-15" → Excel không lọc/sắp xếp theo ngày được, và sai quy
      ước Việt Nam. Nay ghi kiểu ngày thật, hiển thị dd/mm/yyyy.
    · Tiền là CHUỖI "980000000.00 VND" → không SUM được. Nay là số, định dạng
      #,##0, đơn vị tiền tách sang cột riêng, và có DÒNG TỔNG ở cuối.
    · Không có STT → cán bộ tổng hợp phải tự đánh số khi trích dẫn "dòng số mấy".
    · Không viền, không AutoFilter, không dòng tổng → nhìn như một khối dữ liệu đổ ra
      chứ không phải một bảng báo cáo.
    · 6 dòng siêu dữ liệu xếp dọc ở cột A/B đẩy bảng xuống tận dòng 8 mà vẫn khó đọc.
      Nay gộp ô thành khối đầu trang 4 dòng, đọc như đầu một văn bản.
    · Link minh chứng in nguyên URL dài → nay là siêu liên kết chữ "Xem".
    """
    from openpyxl import Workbook  # local import — openpyxl chỉ cần khi xuất Excel
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    maps = label_maps or {}
    wb = Workbook()
    ws = wb.active
    ws.title = spec.title[:31]  # Excel giới hạn 31 ký tự tên sheet

    # ── Bảng màu: cùng tông xanh của giao diện, để file in ra nhận ra là của Viện ──
    INK = "1A6E4A"
    HEAD_BG = "E1EDE7"
    BAND_BG = "F5F8F6"
    LINE = "C0CCC5"
    thin = Side(style="thin", color=LINE)
    box = Border(left=thin, right=thin, top=thin, bottom=thin)

    n_cols = len(spec.columns) + 1  # +1 cho cột STT
    last_col = get_column_letter(n_cols)

    def _period_text() -> str:
        if date_from is None and date_to is None:
            return "Toàn bộ"
        f = date_from.strftime("%d/%m/%Y") if date_from else "…"
        t = date_to.strftime("%d/%m/%Y") if date_to else "…"
        return f"{f} → {t}"

    # ═══ Khối đầu trang: 4 dòng gộp ô, không phải 7 dòng nhãn/giá trị rời ═══
    ws["A1"] = "VIỆN NGHIÊN CỨU CÔNG NGHỆ SINH HỌC VÀ MÔI TRƯỜNG"
    ws["A1"].font = Font(bold=True, size=10, color="6B7A72")
    ws["A2"] = spec.title.upper()
    ws["A2"].font = Font(bold=True, size=16, color=INK)

    # Nói rõ lọc theo trường nào: mỗi mục một ngày nghiệp vụ khác nhau, không nói thì
    # người đọc phải đoán vì sao một bản ghi có mặt hay vắng mặt.
    dong3 = f"Kỳ báo cáo: {_period_text()}   ·   Lọc theo: {spec.date_label}   ·   {len(rows)} bản ghi"
    if spec.year_key and (date_from or date_to):
        dong3 += "   ·   dữ liệu gốc chỉ lưu NĂM nên khoảng ngày được quy về khoảng năm"
    if skipped:
        dong3 += f"   ·   {skipped} bản ghi bị loại vì thiếu dữ liệu thời gian"
    ws["A3"] = dong3
    ws["A3"].font = Font(size=10, color="3D4B44")

    ws["A4"] = (
        f"Người xuất: {user.full_name}   ·   "
        f"Thời điểm: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} (UTC)"
    )
    ws["A4"].font = Font(size=9, italic=True, color="6B7A72")

    for r in (1, 2, 3, 4):
        ws.merge_cells(f"A{r}:{last_col}{r}")
        ws[f"A{r}"].alignment = Alignment(vertical="center")
    ws.row_dimensions[2].height = 24
    ws.append([])  # dòng 5 để trống, tách đầu trang khỏi bảng

    # ═══ Tiêu đề cột ═══
    header_row = _HEADER_ROW
    headers = ["STT"] + [c[0] for c in spec.columns]
    ws.append(headers)
    ws.row_dimensions[header_row].height = 30
    for i in range(1, n_cols + 1):
        c = ws.cell(header_row, i)
        c.font = Font(bold=True, size=10, color=INK)
        c.fill = PatternFill("solid", fgColor=HEAD_BG)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = box

    # ═══ Dữ liệu ═══
    money_cols: list[int] = []
    number_cols: list[int] = []
    for i, (_h, getter) in enumerate(spec.columns, start=2):  # +1 vì đã có cột STT
        kind = getattr(getter, "xl_kind", None)
        if kind == "money":
            money_cols.append(i)
        elif kind == "number":
            number_cols.append(i)
    sum_cols = sorted(money_cols + number_cols)

    band = PatternFill("solid", fgColor=BAND_BG)
    for n, r in enumerate(rows, start=1):
        excel_row = header_row + n
        ws.cell(excel_row, 1, n)  # STT
        for i, (_h, getter) in enumerate(spec.columns, start=2):
            raw = getter(r, maps) if getattr(getter, "needs_labels", False) else getter(r)
            cell = ws.cell(excel_row, i)
            _write_cell(cell, raw)
        for i in range(1, n_cols + 1):
            c = ws.cell(excel_row, i)
            c.border = box
            c.alignment = Alignment(
                vertical="top", wrap_text=True,
                horizontal="center" if i == 1 else None,
            )
            if n % 2 == 0:  # kẻ sọc nhẹ — mắt không lạc dòng trên bảng rộng
                c.fill = band
            if i in money_cols:
                c.number_format = "#,##0"
                c.alignment = Alignment(vertical="top", horizontal="right")

    # ═══ Dòng TỔNG cho các cột tiền ═══
    if rows and sum_cols:
        total_row = header_row + len(rows) + 1
        ws.cell(total_row, 1, "TỔNG").font = Font(bold=True, color=INK)
        # Gộp nhãn "TỔNG" chạy tới ngay trước cột cộng đầu tiên. Chỉ gộp khi có từ hai
        # ô trở lên — openpyxl từ chối vùng gộp 1x1.
        if min(sum_cols) - 1 > 1:
            ws.merge_cells(start_row=total_row, start_column=1,
                           end_row=total_row, end_column=min(sum_cols) - 1)
        ws.cell(total_row, 1).alignment = Alignment(horizontal="right", vertical="center")
        for i in sum_cols:
            col = get_column_letter(i)
            c = ws.cell(total_row, i)
            # Công thức SUM chứ không phải số đã tính sẵn: người dùng lọc bớt dòng thì
            # tổng phải đổi theo, đó là điều họ mong đợi ở một bảng Excel.
            c.value = f"=SUM({col}{header_row + 1}:{col}{header_row + len(rows)})"
            c.number_format = "#,##0" if i in money_cols else "0"
            c.font = Font(bold=True, color=INK)
            c.alignment = Alignment(horizontal="right", vertical="center")
        for i in range(1, n_cols + 1):
            ws.cell(total_row, i).border = box
            if not ws.cell(total_row, i).fill.fgColor.rgb:
                ws.cell(total_row, i).fill = PatternFill("solid", fgColor=HEAD_BG)

    # ═══ Bề rộng cột ═══
    ws.column_dimensions["A"].width = 6  # STT
    for i, (h, getter) in enumerate(spec.columns, start=2):
        vals = []
        for r in rows[:300]:
            raw = getter(r, maps) if getattr(getter, "needs_labels", False) else getter(r)
            vals.append(len(str(raw or "")))
        longest = max([len(h)] + vals) if vals else len(h)
        # Trần 45 (không phải 60): cột quá rộng đẩy các cột sau ra ngoài trang in.
        # Ô đã bật wrap_text nên nội dung dài xuống dòng thay vì bị cắt.
        ws.column_dimensions[get_column_letter(i)].width = min(max(longest + 2, 10), 45)

    # Lọc + cố định tiêu đề: hai thứ đầu tiên người dùng cần trên một bảng báo cáo.
    ws.auto_filter.ref = f"A{header_row}:{last_col}{header_row + len(rows)}"
    ws.freeze_panes = ws.cell(header_row + 1, 2)  # giữ cả tiêu đề lẫn cột STT

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _write_cell(cell, raw) -> None:
    """Ghi một ô ĐÚNG KIỂU, để Excel lọc/sắp xếp/tính toán được (m48).

    Suy kiểu từ HÌNH DẠNG giá trị, không từ tên cột: tên cột do người viết spec đặt và
    sẽ đổi, còn "chuỗi 2025-03-15" thì luôn là một ngày.
    """
    if raw is None or raw == "":
        cell.value = ""
        return

    if isinstance(raw, datetime):
        cell.value = raw.replace(tzinfo=None)
        cell.number_format = "dd/mm/yyyy"
        return
    if isinstance(raw, date):
        cell.value = raw
        cell.number_format = "dd/mm/yyyy"
        return

    if isinstance(raw, str):
        if _ISO_DATE.match(raw):
            try:
                cell.value = date.fromisoformat(raw[:10])
                cell.number_format = "dd/mm/yyyy"
                return
            except ValueError:
                pass
        if raw.startswith(("http://", "https://")):
            # URL dài làm vỡ bề rộng cột và không ai đọc nó bằng mắt — hiện chữ "Xem",
            # giữ đường dẫn ở siêu liên kết. Excel giới hạn 255 ký tự cho hyperlink.
            if len(raw) <= 255:
                cell.value = "Xem"
                cell.hyperlink = raw
                cell.style = "Hyperlink"
                return
        cell.value = raw
        return

    if isinstance(raw, (int, float)):
        cell.value = raw
        return

    cell.value = _cell(raw)


def _cell(v):
    """openpyxl không ghi được UUID/list — ép về chuỗi, giữ nguyên số và ngày."""
    if v is None:
        return ""
    if isinstance(v, (int, float, date, datetime, str)):
        return v
    if isinstance(v, uuid.UUID):
        return str(v)
    return str(v)


def export_xlsx(
    db: Session, *, user: CurrentUser, kind: str,
    date_from: Optional[date], date_to: Optional[date],
    correlation_id: Optional[str], ip: Optional[str],
) -> tuple[bytes, str]:
    """Xuất một mục Nghiên cứu & Đào tạo ra Excel. Trả (nội dung, tên file)."""
    spec = _get_spec(kind)
    if spec.guard is not None:
        spec.guard(user)  # cùng luật với endpoint danh sách tương ứng
    if date_from and date_to and date_from > date_to:
        raise AppException(
            ErrorCode.VALIDATION_ERROR, "Ngày bắt đầu phải trước ngày kết thúc", 400
        )

    rows = _fetch_all(db, user, spec)
    rows, skipped = _filter_period(rows, spec, date_from, date_to)
    content = _build_xlsx(
        spec, rows, user=user, date_from=date_from, date_to=date_to, skipped=skipped,
        # Nhãn danh mục nạp từ DB tại đây — `_build_xlsx` không giữ Session.
        label_maps=_load_label_maps(db),
    )

    suffix = ""
    if date_from or date_to:
        suffix = f"_{(date_from or date.min).isoformat()}_{(date_to or date.max).isoformat()}"
    filename = f"{spec.filename}{suffix}.xlsx"

    audit_service.log_action(
        db, action="RESEARCH_LIST_EXPORT", resource="research_achievement",
        user_id=user.id, resource_id=None, correlation_id=correlation_id, ip=ip,
        detail={"kind": kind, "rows": len(rows), "skipped_no_date": skipped,
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None},
    )
    db.commit()
    return content, filename
