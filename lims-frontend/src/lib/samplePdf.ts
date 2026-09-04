/**
 * Xuất PDF phiếu nhận/chuyển mẫu — render đúng layout biểu mẫu RIBE rồi mở hộp thoại in
 * (người dùng chọn "Lưu thành PDF"). Không cần thư viện PDF phía server.
 * - printIntake   → BM 7.1/01 Phiếu nhận mẫu thử nghiệm (2 mặt)
 * - printDispatch → BM 7.1/02 Phiếu chuyển mẫu và trả kết quả thử nghiệm
 * Phiếu kết quả BM 7.8/01 nằm ở resultPdf.ts.
 */
import { LOGOS, esc, printHtml, val, vnDate } from '@/lib/printCommon';
import type { SampleIntake } from '@/types';

/** Ô checkbox: `on` = true thì đánh dấu sẵn theo dữ liệu đã nhập. */
const cb = (label: string, on = false) =>
  `<span class="cb"><i class="${on ? 'bx on' : 'bx'}"></i>${esc(label)}</span>`;

/**
 * Logo lấy từ thư mục public. Cửa sổ in là about:blank nên đường dẫn tương đối
 * không giải được — phải ghép origin tuyệt đối.
 */
const ORIGIN = typeof window !== 'undefined' ? window.location.origin : '';

/** Khối đầu trang 3 cột: 2 logo · tên đơn vị · ô "Mã số mẫu". */
function head(codeBox: boolean, code?: string) {
  return `
  <table class="head">
    <tr>
      <td class="logos">
        <img src="${ORIGIN}/nlu-logo.png" alt="NLU">
        <img src="${ORIGIN}/ribe-logo.jpeg" alt="RIBE">
      </td>
      <td class="org">
        <div class="uni">TRƯỜNG ĐẠI HỌC NÔNG LÂM THÀNH PHỐ HỒ CHÍ MINH</div>
        <div class="ins">VIỆN NGHIÊN CỨU CÔNG NGHỆ SINH HỌC VÀ MÔI TRƯỜNG</div>
        <div class="en">(RESEARCH INSTITUTE FOR BIOTECHNOLOGY AND ENVIRONMENT)</div>
      </td>
      ${
        codeBox
          ? `<td class="codebox"><div class="cbt">Mã số mẫu:</div><div class="cbv">${val(code)}</div></td>`
          : '<td class="codebox-empty"></td>'
      }
    </tr>
  </table>`;
}

const INTAKE_CSS = `
    /* ── Đầu trang ─────────────────────────────────────────── */
    table.head { width: 100%; border-collapse: collapse; margin-bottom: 2px; }
    table.head > tbody > tr > td { vertical-align: middle; padding: 0; }
    .org { text-align: center; line-height: 1.25; }
    .org .uni { font-size: 11px; text-transform: uppercase; }
    .org .ins { font-size: 11.5px; font-weight: bold; text-transform: uppercase; }
    .org .en { font-size: 9.5px; }
    .codebox { width: 24%; border: 1px solid #000; padding: 4px 6px; height: 46px; }
    .codebox .cbt { font-weight: bold; font-size: 12px; }
    .codebox .cbv { border-bottom: 1px dotted #000; min-height: 15px; text-align: center; font-weight: bold; }
    .codebox-empty { width: 20%; }

    h1 { text-align: center; font-size: 17px; font-weight: bold; letter-spacing: .5px;
         margin: 10px 0 10px; text-transform: uppercase; }

    /* ── Dòng thông tin có gạch chấm ───────────────────────── */
    .line { display: flex; align-items: flex-end; gap: 4px; margin: 3px 0; }
    .lb { white-space: nowrap; }
    .dot { flex: 1; border-bottom: 1px dotted #000; min-height: 15px; padding: 0 3px; }
    .dot.sm { flex: 0 0 26%; }
    .dot.md { flex: 0 0 34%; }

    /* ── Bảng mẫu ──────────────────────────────────────────── */
    table.grid { width: 100%; border-collapse: collapse; margin: 8px 0 6px; table-layout: fixed; }
    table.grid th, table.grid td { border: 1px solid #000; padding: 3px 4px; font-size: 11.5px;
                                   vertical-align: top; word-wrap: break-word; }
    table.grid th { text-align: center; font-weight: bold; }
    table.grid td.c { text-align: center; }
    table.grid tbody tr { height: 22px; }

    /* ── Cụm lựa chọn (checkbox) ───────────────────────────── */
    .opts { margin-top: 4px; }
    .optrow { display: grid; grid-template-columns: 205px 0.85fr 0.85fr 1.3fr; align-items: baseline; margin: 2.5px 0; }
    .optrow > .k { white-space: nowrap; }
    .cb, .cb2 { display: inline-flex; align-items: baseline; gap: 5px; }
    .cb2 { width: 100%; white-space: nowrap; }
    .bx { display: inline-block; width: 10px; height: 10px; border: 1px solid #000;
          flex: 0 0 10px; position: relative; align-self: center; }
    .bx.on::after { content: '✓'; position: absolute; left: 0; top: -5px; font-size: 11px; line-height: 1; }
    .cb2 .tail { flex: 1; border-bottom: 1px dotted #000; min-height: 14px; padding: 0 2px;
                 white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    .free { display: flex; align-items: flex-end; gap: 4px; margin: 2.5px 0; }
    .note { font-style: italic; font-size: 11.5px; margin-top: 4px; }

    /* ── Ký tên ────────────────────────────────────────────── */
    .sign { display: flex; justify-content: space-between; margin-top: 6px; }
    .sign > div { width: 46%; text-align: center; }
    .sign .role { font-weight: bold; }
    .sign .hint { font-style: italic; }
    .sign .place { font-style: italic; margin-bottom: 2px; }
    .sign .who { margin-top: 30px; }

    /* ── Chân trang ────────────────────────────────────────── */
    .foot { display: flex; align-items: flex-start; gap: 8px; margin-top: 10px;
            border-top: 1px solid #000; padding-top: 3px; font-size: 9.5px; }
    .foot .fl { white-space: nowrap; }
    .foot .fc { flex: 1; text-align: center; line-height: 1.35; }
    .foot .fr { white-space: nowrap; }

    /* ── Mặt sau: quy định chung ────────────────────────────
       Ba mức đánh số lấy đúng theo numbering.xml của file gốc:
       lvl0 upperRoman "I." · lvl1 decimal "1." · lvl2 "(1)". */
    .terms { page-break-before: always; break-before: page; }
    .terms h2 { text-align: center; font-size: 14px; text-transform: uppercase;
                margin: 0 0 10px; }
    .terms ol { margin: 4px 0; padding-left: 22px; }
    .terms li { margin: 4px 0; text-align: justify; line-height: 1.35; }
    .terms ol.lv0 { list-style: upper-roman; padding-left: 20px; }
    .terms ol.lv0 > li > .h { font-weight: bold; text-transform: uppercase; }
    .terms ol.lv1 { list-style: decimal; }
    .terms ol.lv2 { list-style: none; counter-reset: c2; padding-left: 26px; }
    .terms ol.lv2 > li { counter-increment: c2; position: relative; }
    .terms ol.lv2 > li::before { content: "(" counter(c2) ") "; position: absolute; left: -26px; }

`;

/**
 * Mặt sau BM 7.1/01 — nguyên văn từ file gốc
 * `docs/BM 7.1.01. Phieu nhan thu nghiem (2023).docx`.
 *
 * KHÔNG bỏ khối này: các chú thích (1)(3)(4) ở mặt trước trỏ thẳng vào những
 * khoản đánh số dưới đây (numbering.xml của file gốc đặt lvlText="(%3)"), nên in
 * thiếu mặt sau là phiếu tự tham chiếu vào chỗ trống.
 */
const TERMS = `
  <div class="terms">
    <h2>Quy định chung về yêu cầu dịch vụ thử nghiệm</h2>
    <ol class="lv0">
      <li><span class="h">QUY ĐỊNH CHUNG</span>
        <ol class="lv1">
          <li>Khi lập và gửi phiếu nhận mẫu thử nghiệm đến Viện Nghiên cứu Công nghệ Sinh học và
            Môi trường (RIBE), Khách hàng xem như đã đọc và chấp nhận các quy định chung về yêu cầu
            dịch vụ thử nghiệm của RIBE được quy định trong văn bản này. Trường hợp có các thỏa thuận
            khác bằng văn bản giữa hai bên, Khách hàng cần đảm bảo phiếu yêu cầu thử nghiệm không vi
            phạm các thỏa thuận đó và Viện không có bất kỳ trách nhiệm nào liên quan với vi phạm của
            khách hàng (nếu có).</li>
          <li>Phiếu nhận mẫu thử nghiệm được xem như là chứng từ để khách hàng nhận Kết quả và mẫu
            lưu (nếu có). Khách hàng vui lòng mang theo phiếu nhận mẫu thử nghiệm này để nhận kết quả
            theo đúng thời gian hẹn trả kết quả.</li>
          <li>Viện Nghiên cứu Công nghệ sinh học và Môi trường không chịu trách nhiệm về các thông tin
            liên quan đến tên mẫu, ký hiệu, nguồn gốc mẫu, tên khách hàng, các chỉ tiêu thử nghiệm…do
            khách hàng cung cấp. Khách hàng cần lưu ý những nội dung trên phiếu nhận mẫu thử nghiệm:
            <ol class="lv2">
              <li>Đề nghị ghi đúng và đầy đủ tên đơn vị gửi mẫu (công ty, cơ quan, cá nhân…), mã số
                thuế, tên mẫu…(kể cả ký hiệu, tên nước ngoài…nếu có) để thuận tiện khi lập Phiếu kết
                quả thử nghiệm và Hóa đơn tài chính. Trường hợp không đủ chỗ khách hàng có thể kèm
                theo tờ rời.</li>
              <li>Đối với mẫu thử nghiệm vi sinh PTN sẽ huỷ mẫu sau khi có kết quả thử nghiệm. Mẫu thử
                nghiệm hóa và thử nghiệm SHPT PTN sẽ lưu mẫu 7 ngày sau khi trả kết quả.</li>
              <li>Khách hàng chịu trách nhiệm phần mô tả mẫu, cần chính xác và rõ ràng. Viện sẽ không
                chịu trách nhiệm về các thông tin liên quan đến ký hiệu nguồn gốc, mô tả mẫu, tên khách
                hàng, các chỉ tiêu yêu cầu thử nghiệm do bên khách hàng cung cấp. Riêng mẫu thử nghiệm
                vi sinh trong phần mô tả mẫu yêu cầu khách hàng phải ghi nhận đầy đủ (Tính nguyên vẹn
                của bao bì chứa mẫu/ Bảo quản mẫu ở điều kiện nào (nhiệt độ bao nhiêu)/ Trạng thái của
                mẫu rắn hay lỏng, màu sắc của mẫu…).</li>
              <li>Chỉ tiêu thực hiện dịch vụ có thể sử dụng nhà thầu phụ trong trường hợp cần thiết,
                Viện sẽ thông báo chi tiết cho khách hàng trước khi áp dụng.</li>
              <li>Viện sẽ không thay đổi tên khách hàng, tên mẫu sau khi đã phát hành phiếu kết quả,
                hoá đơn.</li>
            </ol>
          </li>
          <li>Trong trường hợp việc thử nghiệm có trở ngại hay cần thay đổi, hai bên sẽ thông báo bàn
            bạc để cùng nhau giải quyết.</li>
        </ol>
      </li>
      <li><span class="h">CAM KẾT CỦA KHÁCH HÀNG</span>
        <ol class="lv1">
          <li>Khách hàng thực hiện tạm ứng và thanh toán chi phí còn lại (nếu có) trước khi nhận Kết
            quả, trừ trường hợp các thỏa thuận khác bằng văn bản giữa hai bên. Khách hàng có quyền rút
            lại yêu cầu thử nghiệm bằng cách gửi thông tin chính thức về việc hủy thử nghiệm mẫu bằng
            văn bản/email/fax đến Viện trong thời gian hợp lý. Khách hàng có nghĩa vụ thanh toán chi phí
            theo khối lượng công việc mà Viện đã thực hiện tính đến thời điểm ngừng thử nghiệm.</li>
          <li>Khách hàng có quyền phản ánh /khiếu nại về Kết quả đã nhận, Viện có trách nhiệm giải quyết
            kịp thời khi nhận khiếu nại và trao đổi về cách thức sử lý trên tinh thần hợp tác trên cơ sở
            các bằng chứng tin cậy về kỹ thuật liên quan đến gửi mẫu.</li>
          <li>Khách hàng không tự ý sửa đổi phiếu kết quả mẫu thử nghiệm của Viện và tự chịu trách nhiệm
            trước pháp luật về sai phạm này. Không được trích sao toàn bộ hoặc một phần Kết quả nếu
            không có sự đồng ý bằng văn bản của Viện.</li>
        </ol>
      </li>
      <li><span class="h">CAM KẾT CỦA VIỆN NGHIÊN CỨU CÔNG NGHỆ SINH HỌC VÀ MÔI TRƯỜNG</span>
        <ol class="lv1">
          <li>Viện cam kết thực hiện đúng các thỏa thuận với Khách hàng dựa trên những kiến thức, năng
            lực kỹ thuật thực hiện có thể cung cấp dịch vụ tốt nhất cho khách hàng theo đúng quy định
            hiện hành.</li>
          <li>Viện cam kết bảo mật Kết quả và thông tin của khách hàng. Chỉ cung cấp thông tin khi có sự
            đồng ý bằng văn bản của Khách hàng, ngoại trừ yêu cầu từ các cơ quan pháp luật.</li>
        </ol>
      </li>
    </ol>
  </div>`;

/** Số dòng của bảng mẫu — đếm từ file gốc BM 7.1.01 (.docx): 15 hàng, 1 tiêu đề + 14. */
const MIN_ROWS = 14;

/** BM 7.1/01 — Phiếu nhận mẫu thử nghiệm (mặt trước + mặt sau quy định chung). */
export function printIntake(it: SampleIntake) {
  const ds = it.dispatches ?? [];
  const filled = ds.map(
    (d, i) =>
      `<tr><td class="c">${i + 1}</td><td>${esc(d.sample_name || it.description)}</td>` +
      `<td class="c">${esc(d.quantity ?? '')}</td><td>${esc(d.chi_tieu)}</td>` +
      `<td>${esc(d.phuong_phap)}</td><td></td></tr>`,
  );
  if (filled.length === 0 && it.description) {
    filled.push(`<tr><td class="c">1</td><td>${esc(it.description)}</td><td></td><td></td><td></td><td></td></tr>`);
  }
  const blanks = Array.from(
    { length: Math.max(0, MIN_ROWS - filled.length) },
    (_, i) => `<tr><td class="c">${filled.length + i + 1}</td><td></td><td></td><td></td><td></td><td></td></tr>`,
  );

  const lang = it.result_language ?? '';
  const ret = it.return_method ?? '';

  const inner = `
    ${head(true, it.code)}
    <h1>Phiếu nhận mẫu thử nghiệm</h1>

    <div class="line"><span class="lb">Tên khách hàng/Tên đơn vị:</span><span class="dot">${val(it.customer_name)}</span></div>
    <div class="line"><span class="lb">Địa chỉ:</span><span class="dot">${val(it.address)}</span></div>
    <div class="line">
      <span class="lb">Mã số thuế <sup>(1)</sup>:</span><span class="dot sm">${val(it.tax_code)}</span>
      <span class="lb">Người liên hệ:</span><span class="dot sm">${val(it.contact_person)}</span>
      <span class="lb">Điện thoại:</span><span class="dot">${val(it.phone)}</span>
    </div>
    <div class="line"><span class="lb">Mail:</span><span class="dot">${val(it.email)}</span></div>
    <div class="line"><span class="lb">Ngày hẹn trả kết quả:</span><span class="dot">${val(it.due_date)}</span></div>

    <table class="grid">
      <thead>
        <tr>
          <th style="width:7%">Stt</th>
          <th style="width:20%">Tên mẫu <sup>(1)</sup></th>
          <th style="width:10%">Số lượng</th>
          <th style="width:20%">Chỉ tiêu kiểm nghiệm</th>
          <th style="width:21%">Phương pháp thử</th>
          <th style="width:22%">Mô tả mẫu <sup>(3)</sup></th>
        </tr>
      </thead>
      <tbody>${filled.join('')}${blanks.join('')}</tbody>
    </table>

    <div class="opts">
      <div class="optrow">
        <span class="k">- Phương pháp thử nghiệm của:</span>
        ${cb('Ribe')}${cb('Khách hàng')}${cb('Khác')}
      </div>
      <div class="optrow">
        <span class="k">- Sử dụng nhà thầu phụ <sup>(4)</sup>:</span>
        ${cb('Yêu cầu')}${cb('Không yêu cầu')}<span></span>
      </div>
      <div class="optrow">
        <span class="k">- Phiếu kết quả thử nghiệm:</span>
        ${cb('Tiếng Việt', lang === 'vi')}${cb('Tiếng Anh', lang === 'en')}
        <span class="cb2"><i class="bx"></i>Fax:<span class="tail"></span></span>
      </div>
      <div class="optrow">
        <span class="k">- Trả kết quả thử nghiệm:</span>
        ${cb('Trả trực tiếp', ret === 'direct')}${cb('Thư', ret === 'mail')}
        <span class="cb2"><i class="bx${ret === 'email' ? ' on' : ''}"></i>E-mail:<span class="tail">${
          ret === 'email' ? val(it.email) : ''
        }</span></span>
      </div>
      <div class="optrow">
        <span class="k">- Yêu cầu của khách hàng:</span>
        <span style="grid-column: 2 / -1">${cb('Nhận lại mẫu sau khi thử nghiệm')}</span>
      </div>

      <div class="free"><span class="lb">- Những yêu cầu khác (nếu có):</span><span class="dot">${val(it.other_request)}</span></div>
      <div class="free"><span class="dot"></span></div>
      <div class="free"><span class="lb">- Thông tin xuất hóa đơn:</span><span class="dot"></span></div>
      <div class="free"><span class="lb">- Địa chỉ gửi thư:</span><span class="dot">${val(it.address)}</span></div>
      <div class="free"><span class="lb">- Tên/ Số điện thoại người nhận:</span><span class="dot"></span></div>
      <div class="free">
        <span class="lb">- Lệ phí:</span><span class="dot">${val(it.fee_note)}</span>
        <span class="lb">Ứng trước:</span><span class="dot sm">${val(it.paid_amount)}</span>
        <span class="lb">Còn lại:</span><span class="dot sm"></span>
      </div>
      <div class="note">(Quy định chung về yêu cầu dịch vụ thử nghiệm ở mặt sau)</div>
    </div>

    <div class="sign">
      <div><div class="role">Người gửi mẫu</div><div class="hint">Họ và tên</div></div>
      <div>
        <div class="place">Tp. Hồ Chí Minh, ngày …… tháng …… năm ……</div>
        <div class="role">Người nhận mẫu</div>
        <div class="hint">Họ và tên</div>
        <div class="who">${val(it.received_by_name)}</div>
      </div>
    </div>

    <div class="foot">
      <div class="fl">BM 7.1/01/RIBE</div>
      <div class="fc">
        <div>Địa chỉ: Nhà A2, Trường Đại học Nông Lâm, khu phố 22, phường Linh Xuân, Tp. Hồ Chí Minh</div>
        <div>Tel: 028 37246019 &nbsp;·&nbsp; Website: ribe.hcmuaf.edu.vn &nbsp;·&nbsp; Email: ptm.ribe@hcmuaf.edu.vn</div>
        <div>Số tài khoản: 3140920664 - Ngân hàng: Đầu Tư và Phát Triển Việt Nam - CN Đông Sài Gòn</div>
      </div>
      <div class="fr">Lần ban hành: 4</div>
    </div>
    ${TERMS}`;
  printHtml(`Phieu nhan mau ${it.code}`, inner, INTAKE_CSS);
}


/** Số hàng bảng của BM 7.1/02 — đếm từ file gốc .doc: 26 hàng = 1 tiêu đề + 25. */
const DISPATCH_ROWS = 25;

const DISPATCH_CSS = `
    table.dhead { width: 100%; border-collapse: collapse; margin-bottom: 6px; }
    table.dhead td { vertical-align: middle; padding: 0; }
    table.dhead .logos { width: 22%; }
    .org { text-align: center; line-height: 1.3; }
    .org .uni { font-size: 11px; text-transform: uppercase; }
    .org .ins { font-size: 11.5px; font-weight: bold; text-transform: uppercase; }
    .org .addr { font-size: 10px; }

    h1 { text-align: center; font-size: 15px; font-weight: bold; text-transform: uppercase;
         margin: 10px 0 8px; }

    /* Bảng chỉ tiêu kéo dài nhiều trang: lặp lại hàng tiêu đề ở mỗi trang, nếu không
       trang 2 chỉ còn các ô trống không biết cột nào là cột nào. */
    table.grid { margin: 8px 0 6px; }
    table.grid thead { display: table-header-group; }
    table.grid tr { break-inside: avoid; }

    table.sign2 { width: 100%; margin-top: 14px; }
    table.sign2 td { width: 50%; text-align: center; font-weight: bold; padding-bottom: 28px; }
    .chief { text-align: center; font-weight: bold; margin-top: 4px; }
    .internal { font-style: italic; font-size: 11px; margin-top: 14px; }

    /* Cả cụm ký tên + chân trang giữ nguyên khối: tách ra sẽ đẩy mỗi phần chú
       thích mã số sang một trang trắng riêng. */
    table.sign2, .chief, .internal, .dfoot { break-inside: avoid; }
    .tail { break-inside: avoid; }

    .dfoot { margin-top: 6px; border-top: 1px solid #000; padding-top: 3px; font-size: 9.5px; }
    .dfoot .drow { display: flex; justify-content: space-between; font-weight: bold; }
    .dfoot .conv { margin-top: 2px; line-height: 1.3; }`;

/**
 * BM 7.1/02 — Phiếu chuyển mẫu và trả kết quả thử nghiệm (nội bộ PTN).
 *
 * Dựng theo file gốc `docs/layout/BM 7.1.02. ok Phieu chuyen mau thu nghiem.doc`:
 * bảng 26 hàng × 8 cột, đầu trang lấy từ header1.xml, chân trang từ footer1.xml
 * (gồm cả quy ước đặt mã số XXNYYY-ABC — thứ nhân viên cần khi tự đặt mã phiếu).
 */
export function printDispatch(it: SampleIntake) {
  const ds = it.dispatches ?? [];
  const filled = ds.map(
    (d, i) =>
      `<tr><td class="c">${i + 1}</td><td>${esc(d.sample_name || it.description)}</td>` +
      `<td>${esc(d.chi_tieu)}</td><td class="c">${esc(d.don_vi)}</td>` +
      `<td>${esc(d.ket_qua)}</td><td>${esc(d.phuong_phap)}</td>` +
      `<td>${esc(d.can_bo)}</td><td>${esc(d.note)}</td></tr>`,
  );
  const blanks = Array.from(
    { length: Math.max(0, DISPATCH_ROWS - filled.length) },
    (_, i) =>
      `<tr><td class="c">${filled.length + i + 1}</td>` +
      '<td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>',
  );
  // "Tổng số" trên biểu mẫu là số MẪU, không phải số dòng chỉ tiêu: một mẫu chạy
  // 5 chỉ tiêu vẫn là một mẫu. Đếm theo tên mẫu rồi cộng số lượng của từng mẫu.
  const perSample = new Map<string, number>();
  for (const d of ds) {
    const k = d.sample_name || it.description || 'Mẫu';
    perSample.set(k, Math.max(perSample.get(k) ?? 0, d.quantity ?? 1));
  }
  const total = [...perSample.values()].reduce((a, b) => a + b, 0);
  // "Loại/ Tên mẫu" là TÊN các mẫu, không phải mô tả tình trạng mẫu.
  const sampleNames = [...perSample.keys()].join(', ') || (it.description ?? '');

  const inner = `
    <table class="dhead">
      <tr>
        <td class="logos">${LOGOS}</td>
        <td class="org">
          <div class="uni">TRƯỜNG ĐẠI HỌC NÔNG LÂM TP. HCM</div>
          <div class="ins">VIỆN NGHIÊN CỨU CÔNG NGHỆ SINH HỌC &amp; MÔI TRƯỜNG</div>
          <div class="addr">Kp22, P. Linh Xuân, Thành phố Hồ Chí Minh, Việt Nam</div>
          <div class="addr">ĐT: 028 37246019 &nbsp;·&nbsp; Email: ptm.ribe@hcmuaf.edu.vn</div>
        </td>
      </tr>
    </table>

    <h1>Phiếu chuyển mẫu và trả kết quả thử nghiệm</h1>
    <div class="line"><span class="lb">Mã số:</span><span class="dot">${val(it.code)}</span></div>
    <div class="line">
      <span class="lb">Loại/ Tên mẫu:</span><span class="dot">${val(sampleNames)}</span>
      <span class="lb">Tổng số:</span><span class="dot sm">${total || ''}</span>
    </div>
    <div class="line">
      <span class="lb">Ngày nhận mẫu:</span>
      <span class="dot">${esc(vnDate(it.received_at))}</span>
      <span class="lb">Ngày hẹn:</span><span class="dot">${val(it.due_date)}</span>
    </div>
    <div class="line"><span class="lb">* Lưu ý:</span><span class="dot">${val(it.dispatch_note || it.note)}</span></div>

    <table class="grid">
      <thead>
        <tr>
          <th style="width:5%">Stt</th>
          <th style="width:16%">Loại/ Tên mẫu</th>
          <th style="width:17%">Chỉ tiêu<br>thử nghiệm</th>
          <th style="width:8%">Đơn vị</th>
          <th style="width:13%">Kết quả</th>
          <th style="width:16%">Phương pháp</th>
          <th style="width:13%">Cán bộ<br>phân tích</th>
          <th style="width:12%">Ghi chú</th>
        </tr>
      </thead>
      <tbody>${filled.join('')}${blanks.join('')}</tbody>
    </table>

    <div class="tail">
    <table class="sign2">
      <tr><td>Người nhận</td><td>Người chuyển mẫu</td></tr>
    </table>
    <div class="chief">Trưởng PTN/ Phụ trách kỹ thuật</div>
    <div class="internal">Ghi chú: Biểu này chỉ sử dụng trong nội bộ, không có giá trị khi sử dụng ngoài PTN</div>

    <div class="dfoot">
      <div class="drow"><span>BM 7.1/02/RIBE</span><span>Lần ban hành: 3</span></div>
      <div class="conv">
        <div>* Ghi chú: Mã số: <b>XXNYYY-ABC</b></div>
        <div>- XX: Số năm hiện tại;</div>
        <div>- N: Ký hiệu viết tắt của chữ “Nhận”.</div>
        <div>- YYY: Số thứ tự của mẫu trong sổ nhập;</div>
        <div>- ABC: Ký hiệu tên mẫu chuyển PT.</div>
      </div>
    </div>
    </div>`;
  printHtml(`Phieu chuyen mau ${it.code}`, inner, DISPATCH_CSS);
}
