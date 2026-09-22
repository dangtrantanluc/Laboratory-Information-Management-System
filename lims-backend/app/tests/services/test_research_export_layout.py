"""m48 — bố cục file Excel của Nghiên cứu & Đào tạo.

Phản hồi nghiệp vụ: "form excel hiện tại không có layout rõ ràng, dữ liệu bị rối."

Đọc file thật sinh ra từ dữ liệu production cho thấy bốn thứ khiến người nhận file phải
làm lại bằng tay, và bộ test này khoá cả bốn:

1. **Mã kỹ thuật lọt ra file** — 'national_program', 'ongoing', 'cong_doan', 'isi_q1'.
   Người đọc là cán bộ tổng hợp, không phải lập trình viên.
2. **Ngày là chuỗi ISO** "2025-03-15" — Excel coi là văn bản nên không lọc, không sắp
   xếp theo ngày, và sai quy ước dd/mm/yyyy.
3. **Tiền là chuỗi** "980000000.00 VND" — không SUM được. Một bảng kinh phí không cộng
   được thì phải gõ lại toàn bộ.
4. **Không STT, không viền, không AutoFilter, không dòng tổng** — là dữ liệu đổ ra,
   chưa phải một bảng báo cáo.

Test dựng workbook thẳng từ `_build_xlsx` với dữ liệu tự đặt: không cần DB, và khẳng
định được đúng thứ cần khẳng định — hình dạng file, không phải nội dung nghiệp vụ.
"""
import io
import uuid
from datetime import date

import pytest
from openpyxl import load_workbook

from app.core.deps import CurrentUser
from app.services import research_export_service as svc


def _user() -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(), email="a@ribe.vn", full_name="Nguyễn Văn A", role="admin",
        department_id=None, is_dept_lead=False, is_quality_manager=False,
        status="active", jti="t", token_exp=9_999_999_999,
    )


_ROWS = [
    {
        "code": "DT-01", "title": "Đề tài một", "level": "ministry",
        "lead_user_name": "Trần B", "department_name": "Ban Giám đốc",
        "start_date": "2025-01-01", "end_date": "2026-12-31",
        "academic_year": "2024-2025", "budget_amount": "460000000.00",
        "budget_currency": "VND", "member_count": 2, "status": "ongoing",
        "is_transferred": True, "transfer_product": "Chế phẩm",
        "evidence_url": "https://drive.google.com/file/d/abc",
    },
    {
        "code": "DT-02", "title": "Đề tài hai", "level": "institution",
        "lead_external_name": "Lê C", "department_name": "Ban Giám đốc",
        "start_date": "2025-06-01", "end_date": "2027-05-31",
        "academic_year": "2024-2025", "budget_amount": "100000000.00",
        "budget_currency": "VND", "member_count": 1, "status": "completed",
        "is_transferred": False, "evidence_url": None,
    },
]

_MAPS = {
    "level": {"ministry": "Cấp Bộ", "institution": "Cấp Cơ sở"},
    "status": {"ongoing": "Đang thực hiện", "completed": "Hoàn thành"},
}


@pytest.fixture
def sheet():
    spec = svc._get_spec("research-projects")
    content = svc._build_xlsx(
        spec, _ROWS, user=_user(), date_from=None, date_to=None,
        skipped=0, label_maps=_MAPS,
    )
    return load_workbook(io.BytesIO(content)).active


def _header_cells(ws) -> dict[str, int]:
    """Tiêu đề cột → chỉ số cột. Test bám theo TÊN cột, không bám vị trí."""
    return {c.value: c.column for c in ws[svc._HEADER_ROW] if c.value}


class TestKhongConMaKyThuat:
    def test_cap_de_tai_hien_tieng_viet(self, sheet):
        col = _header_cells(sheet)["Cấp"]

        vals = [sheet.cell(r, col).value for r in (7, 8)]

        assert vals == ["Cấp Bộ", "Cấp Cơ sở"], "mã danh mục vẫn lọt ra file"

    def test_trang_thai_hien_tieng_viet(self, sheet):
        col = _header_cells(sheet)["Trạng thái"]

        assert sheet.cell(7, col).value == "Đang thực hiện"

    def test_ma_ngoai_bang_nhan_thi_giu_nguyen(self):
        """Không nuốt dữ liệu: mã lạ phải hiện ra để người ta thấy mà sửa."""
        spec = svc._get_spec("research-projects")
        rows = [{**_ROWS[0], "status": "trang_thai_la"}]

        content = svc._build_xlsx(spec, rows, user=_user(), date_from=None,
                                  date_to=None, skipped=0, label_maps=_MAPS)
        ws = load_workbook(io.BytesIO(content)).active
        col = _header_cells(ws)["Trạng thái"]

        assert ws.cell(7, col).value == "trang_thai_la"


class TestKieuDuLieuThat:
    def test_ngay_la_kieu_ngay_khong_phai_chuoi(self, sheet):
        col = _header_cells(sheet)["Ngày bắt đầu"]
        cell = sheet.cell(7, col)

        assert not isinstance(cell.value, str), "ngày vẫn là chuỗi — Excel không lọc được"
        assert cell.value.date() == date(2025, 1, 1)
        assert cell.number_format == "dd/mm/yyyy", "phải theo quy ước ngày Việt Nam"

    def test_tien_la_so_cong_duoc(self, sheet):
        col = _header_cells(sheet)["Kinh phí"]
        cell = sheet.cell(7, col)

        assert isinstance(cell.value, (int, float))
        assert cell.value == 460000000
        assert cell.number_format == "#,##0"

    def test_don_vi_tien_tach_sang_cot_rieng(self, sheet):
        """Nhập "460000000 VND" vào một ô là lý do khiến cột tiền không cộng được."""
        col = _header_cells(sheet)["Đơn vị tiền"]

        assert sheet.cell(7, col).value == "VND"

    def test_minh_chung_la_sieu_lien_ket(self, sheet):
        col = _header_cells(sheet)["Minh chứng"]
        cell = sheet.cell(7, col)

        assert cell.value == "Xem", "URL dài làm vỡ bề rộng cột"
        assert cell.hyperlink.target.startswith("https://drive.google.com")

    def test_o_trong_khong_sinh_lien_ket_rong(self, sheet):
        col = _header_cells(sheet)["Minh chứng"]

        # openpyxl quy ô chuỗi rỗng về None khi đọc lại — cả hai đều là "ô trống".
        assert not sheet.cell(8, col).value
        assert sheet.cell(8, col).hyperlink is None


class TestBangBaoCao:
    def test_co_cot_stt(self, sheet):
        assert sheet.cell(svc._HEADER_ROW, 1).value == "STT"
        assert [sheet.cell(r, 1).value for r in (7, 8)] == [1, 2]

    def test_co_autofilter_va_dong_bang_tieu_de(self, sheet):
        assert sheet.auto_filter.ref is not None, "thiếu bộ lọc — bảng dài không dùng nổi"
        # Đóng băng DƯỚI tiêu đề và SAU cột STT: cuộn ngang vẫn biết đang ở dòng nào.
        assert sheet.freeze_panes == f"B{svc._HEADER_ROW + 1}"

    def test_dong_tong_dung_cong_thuc_sum(self, sheet):
        col = _header_cells(sheet)["Kinh phí"]
        total_row = svc._HEADER_ROW + len(_ROWS) + 1
        cell = sheet.cell(total_row, col)

        # Công thức, không phải số tính sẵn: lọc bớt dòng thì tổng phải đổi theo.
        assert str(cell.value).startswith("=SUM(")
        assert sheet.cell(total_row, 1).value == "TỔNG"

    def test_khoi_dau_trang_gon_bon_dong(self, sheet):
        assert sheet["A2"].value == "ĐỀ TÀI NCKH"
        assert "Kỳ báo cáo" in sheet["A3"].value
        assert "2 bản ghi" in sheet["A3"].value
        assert "Người xuất" in sheet["A4"].value
        # Dòng 5 để trống, bảng bắt đầu ngay sau — không đẩy xuống tận dòng 8 như cũ.
        assert sheet["A5"].value is None

    def test_tieu_de_cot_co_vien_va_nen(self, sheet):
        c = sheet.cell(svc._HEADER_ROW, 1)

        assert c.font.bold
        assert c.fill.fgColor.rgb.endswith("E1EDE7")
        assert c.border.bottom.style == "thin"


class TestKhongCoBanGhi:
    def test_van_xuat_duoc_file_hop_le(self):
        """Kỳ báo cáo rỗng là chuyện bình thường — không được nổ."""
        spec = svc._get_spec("research-projects")

        content = svc._build_xlsx(spec, [], user=_user(), date_from=date(2020, 1, 1),
                                  date_to=date(2020, 12, 31), skipped=0, label_maps={})
        ws = load_workbook(io.BytesIO(content)).active

        assert "0 bản ghi" in ws["A3"].value
        assert ws.cell(svc._HEADER_ROW, 1).value == "STT"


class TestMoiMucDeuDungDuoc:
    @pytest.mark.parametrize("kind", sorted(svc.KINDS))
    def test_dung_duoc_voi_du_lieu_rong(self, kind):
        """Mỗi spec phải qua được đường dựng file — kể cả khi không có dòng nào."""
        spec = svc._get_spec(kind)

        content = svc._build_xlsx(spec, [], user=_user(), date_from=None,
                                  date_to=None, skipped=0, label_maps={})
        ws = load_workbook(io.BytesIO(content)).active

        assert ws.cell(svc._HEADER_ROW, 1).value == "STT"
        assert ws.max_column == len(spec.columns) + 1
