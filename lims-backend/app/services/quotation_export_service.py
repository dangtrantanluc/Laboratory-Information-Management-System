"""Xuất BẢNG BÁO GIÁ ra Excel — dựng theo layout chuẩn "BẢNG GIÁ PHÂN TÍCH" của Viện.

Layout gốc (docs/BẢNG GIÁ PHÂN TÍCH - 2024.xlsx):
  · Chữ Times New Roman, tiêu đề cột IN HOA đậm, canh giữa, có khung.
  · Bảng: STT · NỀN MẪU · CHỈ TIÊU THỬ NGHIỆM · PHƯƠNG PHÁP THỬ NGHIỆM · ĐƠN GIÁ (VNĐ).
  · Ô "nền mẫu" GỘP DỌC cho cả nhóm chỉ tiêu cùng một mẫu (không lặp lại tên).
  · Cuối bảng: "Ghi chú: Đơn giá chưa bao gồm VAT x%."

Phần báo giá bổ sung so với bảng giá gốc: măng-sét 2 logo (NLU + RIBE), khối
"Kính gửi", cột Số lượng/Thành tiền, dòng Cộng/VAT/Tổng cộng và khối ký tên.
"""
import io
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from openpyxl.worksheet.properties import PageSetupProperties

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

# --- Bảng màu/khung/phông thống nhất với file mẫu ---------------------------
FONT_NAME = "Times New Roman"
THIN = Side(style="thin", color="000000")
MEDIUM = Side(style="medium", color="000000")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
LEFT_TOP = Alignment(horizontal="left", vertical="top", wrap_text=True)
RIGHT = Alignment(horizontal="right", vertical="center")
MONEY = "#,##0"
HEAD_FILL = PatternFill("solid", fgColor="D9E8DE")
# Màu/cỡ chữ đo trực tiếp từ măng-sét chuẩn của Viện
# (docs/layout/26N323 …docx → word/header2.xml): tên trường đỏ tía, tên viện xanh navy.
MAROON = "660033"
NAVY = "333399"


def _f(
    size: int = 11, *, bold: bool = False, italic: bool = False,
    color: str | None = None, name: str = FONT_NAME,
) -> Font:
    """Gom việc dựng Font về một chỗ cho khỏi lệch phông giữa các khối."""
    return Font(name=name, size=size, bold=bold, italic=italic, color=color)


# Măng-sét: (nội dung, phông, chiều cao dòng) — sao y 4 dòng của văn bản chuẩn.
ORG_HEADER = (
    ("TRƯỜNG ĐẠI HỌC NÔNG LÂM TP. HỒ CHÍ MINH", _f(12, bold=True, color=MAROON), 22),
    ("NONG LAM UNIVERSITY - HO CHI MINH CITY", _f(9, italic=True, color=MAROON), 17),
    ("VIỆN NGHIÊN CỨU CÔNG NGHỆ SINH HỌC & MÔI TRƯỜNG",
     _f(11, bold=True, color=NAVY, name="Cambria"), 21),
    ("RESEARCH INSTITUTE FOR BIOTECHNOLOGY AND ENVIRONMENT",
     _f(9, italic=True, color=NAVY, name="Cambria"), 17),
)
# Địa chỉ nằm ở CHÂN trang chứ không phải măng-sét — đúng như văn bản chuẩn.
FOOTER = (
    "Địa chỉ: Tòa nhà A2, đường số 14, Trường Đại học Nông Lâm – Khu phố 22, "
    "Phường Linh Xuân, Thành phố Hồ Chí Minh",
    "Address: Building A2, 14 Street, Nong Lam University, Quarter 22, "
    "Linh Xuan Ward, Ho Chi Minh City",
    "ĐT: 028 37246019 - Email: ptm.ribe@hcmuaf.edu.vn - Web: ribe.hcmuaf.edu.vn",
)

INTRO = (
    "Theo yêu cầu của Quý Khách hàng, Viện Nghiên cứu Công nghệ Sinh học và Môi trường "
    "xin gửi đến Quý Khách hàng bảng báo giá phân tích như sau:"
)
NOTES = (
    "Thời gian trả kết quả: tùy thuộc vào chỉ tiêu và số lượng mẫu khách hàng gửi, "
    "trường hợp đặc biệt sẽ được thương lượng cụ thể.",
    "Địa chỉ gửi mẫu (trực tiếp hoặc bưu điện): Phòng 211 - Phòng nhận mẫu, Tòa nhà A2.",
)

# (tiêu đề, độ rộng cột) — thứ tự đúng như file mẫu, chèn thêm SL/Thành tiền.
COLUMNS = (
    ("STT", 5.5),
    ("NỀN MẪU", 19),
    ("CHỈ TIÊU THỬ NGHIỆM", 27),
    ("PHƯƠNG PHÁP THỬ NGHIỆM", 24),
    ("SỐ\nLƯỢNG", 7),
    ("ĐƠN GIÁ\n(VNĐ)", 13),
    ("THÀNH TIỀN\n(VNĐ)", 15),
)
NCOL = len(COLUMNS)
LAST_COL = get_column_letter(NCOL)


def _merge(ws, row: int, c1: int, c2: int, value, *, font: Font, align: Alignment):
    ws.merge_cells(start_row=row, start_column=c1, end_row=row, end_column=c2)
    cell = ws.cell(row, c1, value)
    cell.font = font
    cell.alignment = align
    return cell


def _col_px(width: float) -> int:
    """Đổi bề rộng cột của Excel (đơn vị "ký tự") sang pixel — công thức của Excel."""
    return int(width * 7) + 5


def _split_x(x_px: int) -> tuple[int, int]:
    """Hoành độ tuyệt đối → (chỉ số cột, offset TRONG cột đó).

    colOff phải nằm gọn trong bề rộng cột được neo. Excel vẫn vẽ đúng khi offset
    tràn sang cột kế, nhưng LibreOffice thì gói lại — hai logo đè lên nhau. Nên
    phải tự tìm cột chứa điểm neo thay vì luôn neo vào cột A.
    """
    left = 0
    for i, (_, width) in enumerate(COLUMNS):
        w = _col_px(width)
        if x_px < left + w or i == len(COLUMNS) - 1:
            return i, x_px - left
        left += w
    return 0, x_px


def _add_logos(ws, top_row: int) -> None:
    """Măng-sét 2 logo (NLU + RIBE) neo ở góc trái, giống đầu trang phiếu in.

    Bọc try/except: openpyxl cần Pillow để nhúng ảnh. Thiếu ảnh hay thiếu Pillow
    thì bỏ logo chứ KHÔNG làm hỏng cả file báo giá.
    """
    try:
        from openpyxl.drawing.image import Image as XLImage
        from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, OneCellAnchor
        from openpyxl.drawing.xdr import XDRPositiveSize2D
        from openpyxl.utils.units import pixels_to_EMU
    except ImportError:
        return

    # Toạ độ/kích thước quy từ bản chuẩn: cả khối 2 logo rộng 1.64in ≈ 157px,
    # cao 0.95in ≈ 91px. Giữ đúng tỉ lệ gốc từng ảnh (NLU 1:1, RIBE 424:408).
    for name, x_px, w_px, h_px in (
        ("nlu-logo.png", 6, 78, 78),
        ("ribe-logo.jpeg", 90, 81, 78),
    ):
        path = ASSETS_DIR / name
        if not path.is_file():
            continue
        try:
            img = XLImage(str(path))
        except Exception:  # Pillow vắng mặt / ảnh hỏng — bỏ qua, không chặn xuất file
            continue
        img.width, img.height = w_px, h_px
        col, off = _split_x(x_px)
        img.anchor = OneCellAnchor(
            _from=AnchorMarker(
                col=col, colOff=pixels_to_EMU(off), row=top_row - 1, rowOff=pixels_to_EMU(4)
            ),
            ext=XDRPositiveSize2D(pixels_to_EMU(w_px), pixels_to_EMU(h_px)),
        )
        ws.add_image(img)


def _fmt_date(value) -> str:
    """'2026-08-03' → '03/08/2026'. Trả chuỗi rỗng nếu không có ngày."""
    if not value:
        return ""
    parts = str(value)[:10].split("-")
    if len(parts) != 3:
        return str(value)
    return f"{parts[2]}/{parts[1]}/{parts[0]}"


def build_xlsx(quotation: dict) -> bytes:
    """quotation: dict từ quotation_service._serialize (kèm items)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Báo giá"

    for i, (_, width) in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    # ── Măng-sét: 2 logo bên trái, tên đơn vị + liên hệ canh giữa ───────────
    _add_logos(ws, top_row=1)
    for row, (text, font, height) in enumerate(ORG_HEADER, start=1):
        _merge(ws, row, 3, NCOL, text, font=font, align=CENTER)
        ws.row_dimensions[row].height = height
    # Gạch chân măng-sét — tách đầu trang khỏi phần nội dung.
    rule_row = len(ORG_HEADER) + 1
    for c in range(1, NCOL + 1):
        ws.cell(rule_row, c).border = Border(bottom=MEDIUM)
    ws.row_dimensions[rule_row].height = 8

    r = 7
    # ── Tiêu đề ────────────────────────────────────────────────────────────
    _merge(ws, r, 1, NCOL, "BẢNG BÁO GIÁ", font=_f(16, bold=True, color=NAVY), align=CENTER)
    ws.row_dimensions[r].height = 26
    r += 1
    _merge(ws, r, 1, NCOL, f"Số: {quotation.get('code') or ''}", font=_f(11, italic=True), align=CENTER)
    r += 2

    # ── Kính gửi ───────────────────────────────────────────────────────────
    for label, key in (
        ("Kính gửi:", "customer_name"),
        ("Địa chỉ:", "customer_address"),
        ("Mã số thuế:", "customer_tax_code"),
        ("Email:", "customer_email"),
        ("Điện thoại:", "customer_phone"),
    ):
        head = ws.cell(r, 1, label)
        head.font = _f(11, bold=(key == "customer_name"))
        head.alignment = LEFT
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
        value = _merge(
            ws, r, 3, NCOL, quotation.get(key) or "",
            font=_f(11, bold=(key == "customer_name")), align=LEFT,
        )
        value.alignment = LEFT
        r += 1

    valid = _fmt_date(quotation.get("valid_until"))
    if valid:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
        ws.cell(r, 1, "Hiệu lực đến:").font = _f(11)
        ws.cell(r, 1).alignment = LEFT
        _merge(ws, r, 3, NCOL, valid, font=_f(11), align=LEFT)
        r += 1
    r += 1

    # ── Câu mở đầu ─────────────────────────────────────────────────────────
    _merge(ws, r, 1, NCOL, f"     {INTRO}", font=_f(11), align=LEFT_TOP)
    ws.row_dimensions[r].height = 30
    r += 2

    # ── Tiêu đề bảng ───────────────────────────────────────────────────────
    head_row = r
    for i, (title, _) in enumerate(COLUMNS, start=1):
        cell = ws.cell(head_row, i, title)
        cell.font = _f(11, bold=True)
        cell.alignment = CENTER
        cell.border = BOX
        cell.fill = HEAD_FILL
    ws.row_dimensions[head_row].height = 32
    r += 1

    # ── Dòng chi tiết ──────────────────────────────────────────────────────
    items = quotation.get("items") or []
    # (dòng bắt đầu, dòng kết thúc) của từng nhóm cùng nền mẫu — để gộp dọc cột B.
    groups: list[list[int]] = []
    prev_sample = object()

    for i, it in enumerate(items, start=1):
        sample = (it.get("sample_name") or "").strip()
        qty = int(it.get("quantity") or 1)
        price = Decimal(str(it.get("unit_price") or 0))
        amount = Decimal(str(it.get("amount") or (price * qty)))

        # Tên mẫu chỉ ghi ở dòng ĐẦU nhóm; các dòng sau để trống rồi gộp dọc.
        if sample != prev_sample:
            groups.append([r, r])
            ws.cell(r, 2, sample)
        else:
            groups[-1][1] = r
        prev_sample = sample

        values = (
            (1, i), (3, it.get("parameter_name") or ""), (4, it.get("method") or ""),
            (5, qty), (6, float(price)), (7, float(amount)),
        )
        for ci, v in values:
            ws.cell(r, ci, v)
        for ci in range(1, NCOL + 1):
            cell = ws.cell(r, ci)
            cell.border = BOX
            cell.font = _f(11)
            if ci in (1, 5):
                cell.alignment = CENTER
            elif ci in (6, 7):
                cell.alignment = RIGHT
                cell.number_format = MONEY
            else:
                cell.alignment = LEFT
        r += 1

    # Gộp dọc ô nền mẫu cho từng nhóm (đúng cách file mẫu trình bày).
    for start, end in groups:
        if end > start:
            ws.merge_cells(start_row=start, start_column=2, end_row=end, end_column=2)
        ws.cell(start, 2).alignment = Alignment(
            horizontal="left", vertical="center", wrap_text=True
        )

    if not items:  # bảng rỗng vẫn phải có khung, đừng để cột tổng lơ lửng
        for ci in range(1, NCOL + 1):
            ws.cell(r, ci).border = BOX
        r += 1

    # ── Cộng / VAT / Tổng cộng ─────────────────────────────────────────────
    def total_row(label: str, value, *, bold: bool = False):
        nonlocal r
        cell = _merge(
            ws, r, 1, NCOL - 1, label,
            font=_f(11, bold=bold), align=Alignment(horizontal="right", vertical="center"),
        )
        cell.border = BOX
        for ci in range(2, NCOL):
            ws.cell(r, ci).border = BOX
        vc = ws.cell(r, NCOL, float(Decimal(str(value or 0))))
        vc.number_format = MONEY
        vc.alignment = RIGHT
        vc.font = _f(11, bold=bold)
        vc.border = BOX
        r += 1

    # Định dạng % gọn: 8.00 → "8", 10.50 → "10.5" (KHÔNG dùng normalize() vì ra 1E+1)
    vat_rate = Decimal(str(quotation.get("vat_rate") or 0))
    vat_txt = f"{vat_rate:f}".rstrip("0").rstrip(".") or "0"
    total_row("Cộng:", quotation.get("subtotal"))
    total_row(f"VAT {vat_txt}%:", quotation.get("vat_amount"))
    total_row("Tổng cộng:", quotation.get("total"), bold=True)
    r += 1

    # ── Ghi chú ────────────────────────────────────────────────────────────
    ws.cell(r, 1, "Ghi chú:").font = _f(11, bold=True)
    r += 1
    notes = [f"Đơn giá trên chưa bao gồm VAT {vat_txt}%.", *NOTES]
    if quotation.get("note"):
        notes.append(str(quotation["note"]))
    for line in notes:
        text = f"     - {line}"
        _merge(ws, r, 1, NCOL, text, font=_f(11), align=LEFT_TOP)
        # Ô đã gộp thì Excel KHÔNG tự giãn chiều cao — phải tự ước lượng số dòng
        # theo bề rộng bảng (~110 ký tự) để ghi chú dài không bị cắt mất.
        ws.row_dimensions[r].height = 15 * max(1, -(-len(text) // 110))
        r += 1
    r += 2

    # ── Ngày + người lập ───────────────────────────────────────────────────
    issue = str(quotation.get("issue_date") or "")[:10].split("-")
    day, month, year = (issue[2], issue[1], issue[0]) if len(issue) == 3 else ("", "", "")
    _merge(
        ws, r, NCOL - 2, NCOL, f"Tp.HCM, ngày {day} tháng {month} năm {year}",
        font=_f(11, italic=True), align=CENTER,
    )
    r += 1
    _merge(ws, r, NCOL - 2, NCOL, "NGƯỜI LẬP", font=_f(11, bold=True), align=CENTER)
    r += 4
    _merge(
        ws, r, NCOL - 2, NCOL, quotation.get("created_by_name") or "",
        font=_f(11, bold=True), align=CENTER,
    )

    # ── Chân trang: khối liên hệ Việt/Anh, đặt dưới cùng như văn bản chuẩn ──
    r += 3
    for c in range(1, NCOL + 1):
        ws.cell(r, c).border = Border(bottom=THIN)
    ws.row_dimensions[r].height = 6
    r += 1
    for line in FOOTER:
        _merge(ws, r, 1, NCOL, line, font=_f(8, italic=True), align=CENTER)
        ws.row_dimensions[r].height = 12
        r += 1

    # ── Thiết lập in: A4 dọc, vừa 1 trang ngang, lặp tiêu đề bảng mỗi trang ─
    ws.page_setup.orientation = "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.page_margins = PageMargins(left=0.4, right=0.4, top=0.5, bottom=0.5)
    ws.print_title_rows = f"{head_row}:{head_row}"
    ws.print_area = f"A1:{LAST_COL}{r}"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
