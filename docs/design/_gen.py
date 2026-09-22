import pathlib
D = pathlib.Path('.')
CSS = (D/'_shared.css').read_text()
IC = dict(l.split('|', 1) for l in (D/'_icons.txt').read_text().strip().split('\n'))

def shell(body, extra_css=''):
    return (
        '<!doctype html>\n<html>\n<head>\n  <meta charset="utf-8">\n'
        '  <script src="./support.js"></script>\n</head>\n<body>\n<x-dc>\n<helmet>\n'
        '  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=Inter:wght@400;500;600;700&display=swap">\n'
        '  <style>\n' + CSS + extra_css + '\n  </style>\n</helmet>\n'
        + body + '\n</x-dc>\n</body>\n</html>\n')

def bar(right=''):
    return ('<div class="bar">'
            '<div class="inp" style="width:260px">' + IC['SEARCH'] + 'Số báo giá / khách hàng…</div>'
            '<div class="inp" style="width:180px;justify-content:space-between">'
            '<span>— Mọi trạng thái —</span>' + IC['CHEVRON'] + '</div>'
            '<div style="flex:1"></div>' + (right or '<span style="font-size:13px;color:var(--stem)">3 báo giá</span>')
            + '</div>')

# Dữ liệu lấy từ chính DB demo đang chạy (khách + mã phiếu có thật).
ROWS = [
    ('BG-2026-0023', 'Công ty CP Dược Hậu Giang', 'NM-2026-0105', '04/09/2026', '04/10/2026',
     '1.425.600 VND', 'b-draft', 'Nháp', True),
    ('BG-2026-0021', 'Công ty TNHH Thủy sản Minh Phú', 'NM-2026-0102', '03/09/2026', '03/10/2026',
     '1.944.000 VND', 'b-sent', 'Đã gửi khách', True),
    ('BG-2026-0022', 'Viện Kiểm nghiệm ATVSTP Quốc gia', 'NM-2026-0103', '01/09/2026', '01/10/2026',
     '550.800 VND', 'b-ok', 'Khách đồng ý', False),
]

def cells(r):
    code, cust, phieu, d1, d2, money, cls, label, _ = r
    return ('<td><div class="code">' + code + '</div></td>'
            '<td><div>' + cust + '</div><div class="sub">Phiếu: ' + phieu + '</div></td>'
            '<td style="white-space:nowrap">' + d1 + '</td>'
            '<td style="white-space:nowrap">' + d2 + '</td>'
            '<td class="money">' + money + '</td>'
            '<td><span class="badge ' + cls + '">' + label + '</span></td>')

HEAD = ('<thead><tr><th>Số báo giá</th><th>Khách hàng</th><th>Ngày lập</th>'
        '<th>Hiệu lực đến</th><th style="text-align:right">Tổng cộng</th>'
        '<th>Trạng thái</th><th></th></tr></thead>')

def title(t, note):
    return ('<div style="margin-bottom:14px">'
            '<div style="font-size:16px;font-weight:700">' + t + '</div>'
            '<div style="font-size:13px;color:var(--stem);margin-top:2px">' + note + '</div></div>')

# ── Trước khi sửa: 4 icon 38×32 cách nhau 4px ────────────────────────────
body = title('Trước khi sửa', 'Bốn icon 38×32 px, cách nhau 4 px — “Sửa” nằm ngay cạnh “Xóa”.')
body += '<div class="card">' + bar() + '<table>' + HEAD + '<tbody>'
for r in ROWS:
    acts = '<div class="acts"><span class="icon">' + IC['EYE'] + '</span><span class="icon" style="color:var(--success)">' + IC['SHEET'] + '</span>'
    if r[8]:
        acts += '<span class="icon">' + IC['PENCIL'] + '</span><span class="icon" style="color:var(--overdue)">' + IC['TRASH'] + '</span>'
    acts += '</div>'
    body += '<tr>' + cells(r) + '<td>' + acts + '</td></tr>'
body += '</tbody></table></div>'
(D/'Current.dc.html').write_text(shell(body))

# ── A: nút có nhãn + menu ⋯ (đã triển khai) ──────────────────────────────
body = title('Phương án A · Nút “Sửa” có nhãn + menu ⋯',
             'Hành động chính hiện rõ; xem / xuất / xóa gom vào menu. Luôn đúng 2 control mỗi hàng.')
body += '<div class="card">' + bar() + '<table>' + HEAD + '<tbody>'
for i, r in enumerate(ROWS):
    acts = '<div class="acts">'
    if r[8]:
        acts += '<span class="btn btn-2">' + IC['PENCIL'] + 'Sửa</span>'
    acts += '<span class="icon">' + IC['DOTS'] + '</span></div>'
    open_menu = ''
    if i == 1:
        open_menu = ('<div style="position:relative"><div class="menu" style="position:absolute;right:0;top:6px;z-index:5">'
                     '<div class="mi">' + IC['EYE'] + 'Xem chi tiết</div>'
                     '<div class="mi">' + IC['SHEET'] + 'Xuất Excel</div>'
                     '<div class="sep"></div>'
                     '<div class="mi mi-d">' + IC['TRASH'] + 'Xóa báo giá</div></div></div>')
    body += ('<tr' + (' style="background:var(--plate)"' if i == 1 else '') + '>' + cells(r)
             + '<td style="position:relative">' + acts + open_menu + '</td></tr>')
body += '</tbody></table></div>'
(D/'Main.dc.html').write_text(shell(body))
print('Current + Main xong')

# ── B: sửa tại chỗ trong hàng ────────────────────────────────────────────
body = title('Phương án B · Sửa tại chỗ trong hàng',
             'Bấm “Sửa” biến chính hàng đó thành các ô nhập. Không mở modal, không mất ngữ cảnh danh sách.')
body += '<div class="card">' + bar() + '<table>' + HEAD + '<tbody>'
for i, r in enumerate(ROWS):
    if i == 1:
        cell = ('height:34px;border:1px solid var(--blueberry);border-radius:8px;'
                'background:var(--surface);display:flex;align-items:center;padding:0 10px;font-size:13px')
        body += ('<tr style="background:rgba(26,110,74,.05);box-shadow:inset 3px 0 0 var(--blueberry)">'
                 '<td><div class="code">' + r[0] + '</div></td>'
                 '<td><div style="' + cell + '">' + r[1] + '</div>'
                 '<div class="sub">Phiếu: ' + r[2] + '</div></td>'
                 '<td><div style="' + cell + '">' + r[3] + '</div></td>'
                 '<td><div style="' + cell + '">' + r[4] + '</div></td>'
                 '<td><div style="' + cell + ';justify-content:flex-end;font-weight:600">' + r[5] + '</div></td>'
                 '<td><div style="' + cell + ';justify-content:space-between">Đã gửi khách' + IC['CHEVRON'] + '</div></td>'
                 '<td><div class="acts"><span class="btn btn-1">' + IC['CHECK'] + 'Lưu</span>'
                 '<span class="btn btn-g">Hủy</span></div></td></tr>')
    else:
        acts = '<div class="acts">'
        if r[8]:
            acts += '<span class="btn btn-2">' + IC['PENCIL'] + 'Sửa</span>'
        acts += '<span class="icon">' + IC['DOTS'] + '</span></div>'
        body += '<tr>' + cells(r) + '<td>' + acts + '</td></tr>'
body += '</tbody></table></div>'
(D/'OptionB.dc.html').write_text(shell(body))

# ── C: ngăn kéo bên phải ─────────────────────────────────────────────────
extra = ('\n    .drawer{width:420px;flex:0 0 420px;border:1px solid var(--hairline);border-radius:12px;'
         'background:var(--surface);box-shadow:0 8px 24px rgba(16,24,40,.12);display:flex;flex-direction:column}'
         '\n    .dh{padding:16px;border-bottom:1px solid var(--hairline)}'
         '\n    .db{padding:16px;display:flex;flex-direction:column;gap:14px;flex:1}'
         '\n    .df{padding:14px 16px;border-top:1px solid var(--hairline);display:flex;gap:8px;justify-content:flex-end}'
         '\n    .kv{display:grid;grid-template-columns:120px 1fr;gap:4px 12px;font-size:13px}'
         '\n    .kv dt{color:var(--stem)} .kv dd{margin:0;color:var(--ink)}')
body = title('Phương án C · Ngăn kéo bên phải',
             'Bấm vào hàng mở ngăn kéo: xem và sửa cùng một chỗ, danh sách vẫn nhìn thấy để đối chiếu.')
body += '<div style="display:flex;gap:16px;align-items:flex-start">'
body += '<div class="card" style="flex:1;min-width:0">' + bar('') + '<table>' + HEAD.replace('<th></th>', '') + '<tbody>'
for i, r in enumerate(ROWS):
    sel = ' style="background:rgba(26,110,74,.06);box-shadow:inset 3px 0 0 var(--blueberry)"' if i == 1 else ''
    body += '<tr' + sel + '>' + cells(r) + '</tr>'
body += '</tbody></table></div>'
body += ('<div class="drawer">'
         '<div class="dh"><div style="display:flex;align-items:center;justify-content:space-between">'
         '<div><div style="font-size:15px;font-weight:700">BG-2026-0021</div>'
         '<div class="sub">Phiếu NM-2026-0102</div></div>'
         '<span class="icon">' + IC['CLOSE'] + '</span></div></div>'
         '<div class="db">'
         '<span class="badge b-sent" style="align-self:flex-start">Đã gửi khách</span>'
         '<dl class="kv"><dt>Khách hàng</dt><dd>Công ty TNHH Thủy sản Minh Phú</dd>'
         '<dt>Mã số thuế</dt><dd>2000103546</dd>'
         '<dt>Địa chỉ</dt><dd>KCN Khánh An, H. U Minh, Cà Mau</dd>'
         '<dt>Ngày lập</dt><dd>03/09/2026</dd><dt>Hiệu lực đến</dt><dd>03/10/2026</dd></dl>'
         '<div style="border-top:1px solid var(--hairline);padding-top:12px">'
         '<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.025em;'
         'color:var(--stem);margin-bottom:8px">2 chỉ tiêu</div>'
         '<div style="display:flex;flex-direction:column;gap:6px;font-size:13px">'
         '<div style="display:flex;justify-content:space-between"><span>Cadimi (Cd) × 2</span>'
         '<span style="font-weight:600">900.000</span></div>'
         '<div style="display:flex;justify-content:space-between"><span>Chì (Pb) × 2</span>'
         '<span style="font-weight:600">900.000</span></div>'
         '<div style="display:flex;justify-content:space-between;border-top:1px solid var(--hairline);'
         'padding-top:6px;margin-top:2px"><span>Tổng cộng (VAT 8%)</span>'
         '<span style="font-weight:700">1.944.000</span></div></div></div></div>'
         '<div class="df"><span class="btn btn-2">' + IC['SHEET'] + 'Xuất Excel</span>'
         '<span class="btn btn-1">' + IC['PENCIL'] + 'Sửa báo giá</span></div></div>')
body += '</div>'
(D/'OptionC.dc.html').write_text(shell(body, extra))
print('B + C xong')

# ── D: thẻ thay bảng ─────────────────────────────────────────────────────
extra = ('\n    .tile{border:1px solid var(--hairline);border-radius:12px;background:var(--surface);'
         'padding:16px;display:flex;flex-direction:column;gap:12px;'
         'box-shadow:0 1px 2px rgba(16,24,40,.04),0 1px 3px rgba(16,24,40,.06)}'
         '\n    .tile .top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}'
         '\n    .tile .meta{display:grid;grid-template-columns:1fr 1fr;gap:6px 12px;font-size:12px;color:var(--stem)}'
         '\n    .tile .foot{display:flex;align-items:center;justify-content:space-between;gap:8px;'
         'border-top:1px solid var(--hairline);padding-top:12px}')
body = title('Phương án D · Thẻ thay bảng',
             'Mỗi báo giá là một thẻ; hành động là nút đầy đủ 32–36 px. Hợp màn hẹp, máy tính bảng và thao tác chạm.')
body += '<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px">'
for r in ROWS:
    body += ('<div class="tile"><div class="top">'
             '<div><div style="font-size:15px;font-weight:700">' + r[0] + '</div>'
             '<div class="sub" style="margin-top:3px">' + r[1] + '</div></div>'
             '<span class="badge ' + r[6] + '" style="flex:0 0 auto">' + r[7] + '</span></div>'
             '<div style="font-size:22px;font-weight:700;letter-spacing:-.01em">' + r[5] + '</div>'
             '<div class="meta"><div>Phiếu</div><div style="color:var(--ink)">' + r[2] + '</div>'
             '<div>Ngày lập</div><div style="color:var(--ink)">' + r[3] + '</div>'
             '<div>Hiệu lực đến</div><div style="color:var(--ink)">' + r[4] + '</div></div>'
             '<div class="foot">'
             + ('<span class="btn btn-2" style="flex:1">' + IC['PENCIL'] + 'Sửa</span>' if r[8]
                else '<span class="btn btn-2" style="flex:1">' + IC['EYE'] + 'Xem</span>')
             + '<span class="btn btn-2">' + IC['SHEET'] + 'Excel</span>'
             '<span class="icon" style="border:1px solid var(--hairline);border-radius:8px;width:32px">'
             + IC['DOTS'] + '</span></div></div>')
body += '</div>'
(D/'OptionD.dc.html').write_text(shell(body, extra))
print('D xong')
