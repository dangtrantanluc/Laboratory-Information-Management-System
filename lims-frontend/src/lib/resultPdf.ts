/**
 * BM 7.8/01/RIBE — KẾT QUẢ THỬ NGHIỆM / TEST REPORT (song ngữ).
 *
 * Dựng theo hai file gốc trong `docs/layout/26N323 - … NHÂN ÁI*.docx`. Chúng là
 * HAI BIẾN THỂ của cùng biểu mẫu, khác nhau ở cách xếp cột kết quả:
 *
 *   - 'grouped'   (file không hậu tố): một cột "Kết quả" tách thành nhiều cột con,
 *     mỗi mẫu một cột. Dùng khi các mẫu chạy CÙNG bộ chỉ tiêu — so sánh theo hàng
 *     ngang rất nhanh, và tiết kiệm giấy.
 *   - 'perSample' (file "Theo hộ"): mỗi mẫu một khối riêng, bảng có thêm cột
 *     "Tên mẫu". Dùng khi mỗi mẫu một bộ chỉ tiêu khác nhau, hoặc khi cần tách
 *     phiếu để phát cho từng hộ/từng đơn vị.
 *
 * Chọn biến thể theo dữ liệu chứ không bắt người dùng đoán: xem pickMode().
 */
import { LOGOS, esc, printHtml, val, vnDate } from '@/lib/printCommon';
import type { SampleDispatch, SampleIntake } from '@/types';

export type ResultMode = 'grouped' | 'perSample';

const CSS = `
    table.rhead { width: 100%; border-collapse: collapse; }
    table.rhead td { vertical-align: middle; padding: 0; }
    table.rhead .logos { width: 18%; }
    .org { text-align: center; line-height: 1.25; }
    .org .vi { font-size: 10.5px; text-transform: uppercase; }
    .org .en { font-size: 9.5px; font-style: italic; }
    .org .ins { font-size: 11px; font-weight: bold; text-transform: uppercase; }
    .rhead .meta { width: 20%; text-align: right; font-size: 9.5px; line-height: 1.4; }
    .rhead .meta b { font-size: 10.5px; }

    h1 { text-align: center; font-size: 15px; font-weight: bold; text-transform: uppercase;
         margin: 8px 0 1px; }
    h1 .en { display: block; font-size: 11.5px; font-style: italic; font-weight: normal;
             text-transform: none; }
    .code { text-align: center; font-size: 11.5px; margin-bottom: 6px; }

    /* Bảng thông tin mẫu: nhãn song ngữ ở cột trái, tiếng Anh in nghiêng nhỏ hơn. */
    table.info { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
    table.info td { border: 1px solid #000; padding: 3px 5px; font-size: 11.5px; vertical-align: top; }
    table.info td.k { width: 20%; }
    table.info .en { display: block; font-style: italic; font-size: 10px; }

    h2 { text-align: center; font-size: 13px; font-weight: bold; text-transform: uppercase;
         margin: 8px 0 4px; }
    h2 .en { display: block; font-size: 10.5px; font-style: italic; font-weight: normal;
             text-transform: none; }

    table.grid { margin-bottom: 6px; }
    table.grid thead { display: table-header-group; }
    table.grid tr { break-inside: avoid; }
    table.grid th .en { display: block; font-style: italic; font-weight: normal; font-size: 10px; }
    table.grid td.r { text-align: center; }

    .legend { font-size: 10.5px; line-height: 1.4; margin: 4px 0 10px; }

    table.sign { width: 100%; margin-top: 6px; }
    table.sign td { width: 50%; text-align: center; vertical-align: top; font-size: 11.5px; }
    table.sign .place { font-style: italic; }
    table.sign .role { font-weight: bold; padding-top: 4px; }
    table.sign .role .en { display: block; font-style: italic; font-weight: normal; font-size: 10px; }
    table.sign .who { font-weight: bold; padding-top: 40px; text-transform: uppercase; }

    .rfoot { margin-top: 10px; border-top: 1px solid #000; padding-top: 3px;
             font-size: 8.5px; line-height: 1.35; }
    .rfoot .strong { font-weight: bold; text-align: center; }

    .block + .block { page-break-before: always; break-before: page; }`;

/** Nhãn song ngữ dùng lại nhiều chỗ. */
const bi = (vi: string, en: string) => `${esc(vi)}<span class="en">${esc(en)}</span>`;

function header(it: SampleIntake, page: number, total: number) {
  return `
  <table class="rhead">
    <tr>
      <td class="logos">${LOGOS}</td>
      <td class="org">
        <div class="vi">Trường Đại học Nông Lâm TP. Hồ Chí Minh</div>
        <div class="en">Nong Lam University - Ho Chi Minh City</div>
        <div class="ins">Viện nghiên cứu công nghệ sinh học &amp; môi trường</div>
        <div class="en">Research Institute for Biotechnology and Environment</div>
      </td>
      <td class="meta">
        <div><b>BM 7.8/01/RIBE</b></div>
        <div>Trang / Page: ${page} / ${total}</div>
        <div>Mã KH/ Customer code:<br><b>${val(it.code)}</b></div>
      </td>
    </tr>
  </table>
  <h1>Kết quả thử nghiệm<span class="en">Test report</span></h1>`;
}

function infoTable(it: SampleIntake, sampleName: string, qty: number) {
  const received = vnDate(it.received_at);
  return `
  <table class="info">
    <tr><td class="k">${bi('Tên khách hàng:', 'Customer:')}</td><td colspan="3">${val(it.customer_name)}</td></tr>
    <tr><td class="k">${bi('Địa chỉ:', 'Address:')}</td><td colspan="3">${val(it.address)}</td></tr>
    <tr><td class="k">${bi('Loại/ Tên mẫu:', 'Type/ Name of sample:')}</td><td colspan="3">${val(sampleName)}</td></tr>
    <tr>
      <td class="k">${bi('Mô tả mẫu:', 'Sample description:')}</td><td>${val(it.description)}</td>
      <td class="k">${bi('Số lượng mẫu:', 'Quantity:')}</td><td>${qty ? String(qty).padStart(2, '0') : ''}</td>
    </tr>
    <tr>
      <td class="k">${bi('Ngày nhận mẫu:', 'Date of receiving:')}</td><td>${esc(received)}</td>
      <td class="k">${bi('Ngày trả kết quả:', 'Date of reporting:')}</td><td>${val(it.due_date)}</td>
    </tr>
  </table>
  <h2>Kết quả<span class="en">Result</span></h2>`;
}

const TH_STT = '<th style="width:6%">Stt<span class="en">No.</span></th>';
const TH_PARAM = '<th style="width:26%">Chỉ tiêu thử<span class="en">Parameter</span></th>';
const TH_UNIT = '<th style="width:11%">Đơn vị<span class="en">Unit</span></th>';
const TH_METHOD = '<th style="width:22%">Phương pháp thử<span class="en">Method</span></th>';

/** Tên mẫu của một lượt chuyển; rỗng thì rơi về mô tả chung của phiếu. */
const nameOf = (d: SampleDispatch, it: SampleIntake) => d.sample_name || it.description || 'Mẫu';

/**
 * Bảng gộp: hàng = chỉ tiêu, cột = từng mẫu. Cột "Kết quả" là ô gộp phía trên,
 * bên dưới tách thành N cột con mang tên mẫu — đúng như file gốc.
 */
function groupedTable(it: SampleIntake, ds: SampleDispatch[]) {
  const samples = [...new Set(ds.map((d) => nameOf(d, it)))];
  // Giữ thứ tự chỉ tiêu theo lần xuất hiện đầu tiên, không sắp xếp lại: thứ tự
  // trên phiếu phải khớp thứ tự nhân viên đã nhập.
  const params = [...new Set(ds.map((d) => d.chi_tieu))];
  const at = (param: string, sample: string) =>
    ds.find((d) => d.chi_tieu === param && nameOf(d, it) === sample);

  const rows = params
    .map((param, i) => {
      const any = ds.find((d) => d.chi_tieu === param);
      const cells = samples
        .map((s) => `<td class="r">${esc(at(param, s)?.ket_qua ?? '')}</td>`)
        .join('');
      return (
        `<tr><td class="c">${i + 1}</td><td>${esc(param)}</td>` +
        `<td class="c">${esc(any?.don_vi)}</td>${cells}` +
        `<td>${esc(any?.phuong_phap)}</td></tr>`
      );
    })
    .join('');

  return `
  <table class="grid">
    <thead>
      <tr>
        <th rowspan="2" style="width:6%">Stt<span class="en">No.</span></th>
        <th rowspan="2" style="width:22%">Chỉ tiêu thử<span class="en">Parameter</span></th>
        <th rowspan="2" style="width:12%">Đơn vị<span class="en">Unit</span></th>
        <th colspan="${samples.length}">Kết quả<span class="en">Result</span></th>
        <th rowspan="2" style="width:20%">Phương pháp thử<span class="en">Method</span></th>
      </tr>
      <tr>${samples.map((s) => `<th>${esc(s)}</th>`).join('')}</tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>`;
}

/** Bảng tách: một khối cho mỗi mẫu, có thêm cột "Tên mẫu" như bản "Theo hộ". */
function perSampleTable(it: SampleIntake, ds: SampleDispatch[]) {
  const rows = ds
    .map(
      (d, i) =>
        `<tr><td class="c">${i + 1}</td><td>${esc(nameOf(d, it))}</td>` +
        `<td>${esc(d.chi_tieu)}</td><td class="c">${esc(d.don_vi)}</td>` +
        `<td class="r">${esc(d.ket_qua)}</td><td>${esc(d.phuong_phap)}</td></tr>`,
    )
    .join('');
  return `
  <table class="grid">
    <thead>
      <tr>
        ${TH_STT}
        <th style="width:20%">Tên mẫu<span class="en">Name of sample</span></th>
        ${TH_PARAM}${TH_UNIT}
        <th style="width:15%">Kết quả<span class="en">Result</span></th>
        ${TH_METHOD}
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>`;
}

const LEGEND = `
  <div class="legend">
    <div>Ghi chú: KPH — Không phát hiện; LOQ — Giới hạn định lượng; LOD — Giới hạn phát hiện.</div>
    <div>(*): Chỉ tiêu được VILAS công nhận ISO/IEC 17025:2017 &nbsp;·&nbsp;
         (**): Chỉ tiêu gửi nhà thầu phụ.</div>
  </div>`;

function signature(it: SampleIntake) {
  return `
  <table class="sign">
    <tr>
      <td></td>
      <td class="place">Tp. Hồ Chí Minh, ngày …… tháng …… năm ……<br>
        Ho Chi Minh City, date… month… year…</td>
    </tr>
    <tr>
      <td class="role">Trưởng PTN/QLKT<span class="en">Lab/Tech Manager</span></td>
      <td class="role">Viện trưởng<span class="en">Director</span></td>
    </tr>
    <tr>
      <td class="who">${val(it.received_by_name)}</td>
      <td class="who"></td>
    </tr>
  </table>`;
}

const FOOT = `
  <div class="rfoot">
    <div class="strong">KẾT QUẢ NÀY CHỈ CÓ GIÁ TRỊ TRÊN MẪU THỬ / THIS RESULT IS ONLY VALID ON TESTED SAMPLE</div>
    <div>Thông tin về mẫu được ghi theo yêu cầu của Khách hàng/ The sample information is written as the client’s request.</div>
    <div>Thời gian lưu mẫu: 7 ngày kể từ ngày trả kết quả (ngoại trừ mẫu vi sinh)/ Time-limit of storage: 7 days from reporting date (except Microbiology samples).</div>
    <div>Mọi khiếu nại về kết quả phân tích sẽ không được giải quyết sau khi hết thời gian lưu mẫu/ All complaints about result are not be resolved after the storage period is over.</div>
    <div>Không được sao chép từng phần kết quả này, nếu không được sự đồng ý bằng văn bản của RIBE/ A part of the result is not allowed to copy except RIBE’s permission by issuing document.</div>
    <div>Địa chỉ: Tòa nhà A2, đường số 14, Trường Đại học Nông Lâm – Khu phố 22, Phường Linh Xuân, Thành phố Hồ Chí Minh</div>
    <div>Address: Building A2, 14 Street, Nong Lam University, Quarter 22, Linh Xuan Ward, Ho Chi Minh City</div>
    <div>ĐT: 028 37246019 - Email: ptm.ribe@hcmuaf.edu.vn</div>
  </div>`;

/**
 * Chọn biến thể theo hình dạng dữ liệu, thay vì bắt người dùng đoán:
 * các mẫu chạy CÙNG bộ chỉ tiêu → gộp thành cột; khác nhau → tách từng khối.
 */
export function pickMode(it: SampleIntake): ResultMode {
  const ds = it.dispatches ?? [];
  const bySample = new Map<string, Set<string>>();
  for (const d of ds) {
    const k = nameOf(d, it);
    if (!bySample.has(k)) bySample.set(k, new Set());
    bySample.get(k)!.add(d.chi_tieu);
  }
  if (bySample.size <= 1) return 'grouped';
  const sets = [...bySample.values()].map((s) => [...s].sort().join('|'));
  return sets.every((x) => x === sets[0]) ? 'grouped' : 'perSample';
}

/** In phiếu kết quả BM 7.8/01. `mode` bỏ trống thì tự chọn theo pickMode(). */
export function printResult(it: SampleIntake, mode?: ResultMode) {
  const ds = (it.dispatches ?? []).filter((d) => d.status !== 'returned');
  const chosen = mode ?? pickMode(it);

  let blocks: string[];
  if (chosen === 'grouped') {
    const names = [...new Set(ds.map((d) => nameOf(d, it)))];
    // "Số lượng mẫu" là số MẪU chứ không phải số dòng kết quả: 4 mẫu × 5 chỉ tiêu
    // vẫn là 4 mẫu.
    const qty = names.length;
    blocks = [
      infoTable(it, names.join(', '), qty) + groupedTable(it, ds) + LEGEND + signature(it),
    ];
  } else {
    const names = [...new Set(ds.map((d) => nameOf(d, it)))];
    blocks = names.map((name) => {
      const rows = ds.filter((d) => nameOf(d, it) === name);
      const qty = Math.max(...rows.map((d) => d.quantity ?? 1));
      return infoTable(it, name, qty) + perSampleTable(it, rows) + LEGEND + signature(it);
    });
  }

  const inner = blocks
    .map((b, i) => `<div class="block">${header(it, i + 1, blocks.length)}${b}${FOOT}</div>`)
    .join('');
  printHtml(`Ket qua thu nghiem ${it.code}`, inner, CSS);
}
