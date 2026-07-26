/**
 * Xuất PDF phiếu nhận/chuyển mẫu — render đúng layout biểu mẫu RIBE rồi mở hộp thoại in
 * (người dùng chọn "Lưu thành PDF"). Không cần thư viện PDF phía server.
 * - printIntake  → BM 7.1/01 Phiếu nhận mẫu thử nghiệm
 * - printDispatch → BM 7.1/02 Phiếu chuyển mẫu và trả kết quả thử nghiệm
 */
import type { SampleIntake } from '@/types';

function esc(v: unknown): string {
  return String(v ?? '').replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c] as string));
}
const val = (v: unknown) => esc(v ?? '……………');

const HEAD = `
  <div class="head">
    <div class="org">
      <div>TRƯỜNG ĐẠI HỌC NÔNG LÂM TP. HCM</div>
      <div class="ins">VIỆN NGHIÊN CỨU CÔNG NGHỆ SINH HỌC VÀ MÔI TRƯỜNG</div>
      <div class="en">(RESEARCH INSTITUTE FOR BIOTECHNOLOGY AND ENVIRONMENT — RIBE)</div>
    </div>
  </div>`;

const STYLE = `
  <style>
    @page { size: A4; margin: 14mm; }
    * { box-sizing: border-box; }
    body { font-family: 'Times New Roman', serif; color: #000; font-size: 13px; margin: 0; }
    .head { text-align: center; border-bottom: 1.5px solid #000; padding-bottom: 6px; margin-bottom: 8px; }
    .org { font-size: 12px; }
    .ins { font-weight: bold; font-size: 13px; }
    .en { font-style: italic; font-size: 11px; }
    h1 { text-align: center; font-size: 16px; margin: 10px 0 12px; text-transform: uppercase; }
    .row { margin: 3px 0; }
    .row b { font-weight: normal; }
    .lbl { font-weight: 600; }
    table { width: 100%; border-collapse: collapse; margin: 8px 0; }
    th, td { border: 1px solid #000; padding: 4px 6px; font-size: 12px; vertical-align: top; }
    th { background: #f0f0f0; text-align: center; }
    .sign { display: flex; justify-content: space-around; margin-top: 24px; text-align: center; }
    .sign > div { min-width: 30%; }
    .sign .role { font-weight: 600; }
    .sign .hint { font-size: 11px; font-style: italic; color: #333; }
    .foot { margin-top: 18px; border-top: 1px solid #000; padding-top: 4px; font-size: 10px; color: #333; }
    .opts { margin: 6px 0; font-size: 12px; }
    .note { font-size: 11px; font-style: italic; }
  </style>`;

function printHtml(title: string, inner: string) {
  const w = window.open('', '_blank');
  if (!w) return;
  w.document.write(`<html><head><meta charset="utf-8"><title>${esc(title)}</title>${STYLE}</head><body>${inner}</body></html>`);
  w.document.close();
  w.focus();
  w.print();
}

const LANG: Record<string, string> = { vi: 'Tiếng Việt', en: 'Tiếng Anh' };
const RET: Record<string, string> = { direct: 'Trả trực tiếp', mail: 'Thư', email: 'E-mail' };

/** BM 7.1/01 — Phiếu nhận mẫu thử nghiệm. */
export function printIntake(it: SampleIntake) {
  const ds = it.dispatches ?? [];
  const rows =
    ds.length > 0
      ? ds
          .map(
            (d, i) =>
              `<tr><td>${i + 1}</td><td>${esc(it.description)}</td><td></td>` +
              `<td>${esc(d.chi_tieu)}</td><td>${esc(d.phuong_phap)}</td><td></td></tr>`,
          )
          .join('')
      : `<tr><td>1</td><td>${esc(it.description)}</td><td></td><td></td><td></td><td></td></tr>`;

  const inner = `
    ${HEAD}
    <div class="row" style="text-align:right">Mã số mẫu: <b>${esc(it.code)}</b></div>
    <h1>Phiếu nhận mẫu thử nghiệm</h1>
    <div class="row"><span class="lbl">Tên khách hàng/Tên đơn vị:</span> ${val(it.customer_name)}</div>
    <div class="row"><span class="lbl">Địa chỉ:</span> ${val(it.address)}</div>
    <div class="row"><span class="lbl">Mã số thuế:</span> ${val(it.tax_code)}
        &nbsp;&nbsp;<span class="lbl">Người liên hệ:</span> ${val(it.contact_person ?? it.contact)}
        &nbsp;&nbsp;<span class="lbl">Điện thoại:</span> ${val(it.phone)}</div>
    <div class="row"><span class="lbl">Mail:</span> ${val(it.email)}
        &nbsp;&nbsp;<span class="lbl">Ngày hẹn trả kết quả:</span> ${val(it.due_date)}</div>
    <table>
      <thead><tr><th style="width:6%">Stt</th><th>Tên mẫu</th><th style="width:8%">Số lượng</th>
        <th>Chỉ tiêu kiểm nghiệm</th><th>Phương pháp thử</th><th>Mô tả mẫu</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="opts">
      <div>• Phiếu kết quả: <b>${esc(LANG[it.result_language ?? ''] ?? '……')}</b>
           &nbsp;&nbsp;• Trả kết quả: <b>${esc(RET[it.return_method ?? ''] ?? '……')}</b></div>
      <div>• Lệ phí / Ứng trước / Còn lại: ${val(it.fee_note)}</div>
      <div>• Những yêu cầu khác: ${val(it.other_request)}</div>
    </div>
    <div class="sign">
      <div><div class="role">Người gửi mẫu</div><div class="hint">(Họ và tên)</div></div>
      <div><div>Tp. Hồ Chí Minh, ngày …… tháng …… năm ……</div>
           <div class="role" style="margin-top:6px">Người nhận mẫu</div>
           <div>${val(it.received_by_name)}</div></div>
    </div>
    <div class="foot">BM 7.1/01/RIBE — Lần ban hành 4 · Địa chỉ: Nhà A2, Trường ĐH Nông Lâm, Kp22, P. Linh Xuân, TP.HCM ·
      Tel: 028 37246019 · ptm.ribe@hcmuaf.edu.vn</div>`;
  printHtml(`Phieu nhan mau ${it.code}`, inner);
}

/** BM 7.1/02 — Phiếu chuyển mẫu và trả kết quả thử nghiệm (nội bộ PTN). */
export function printDispatch(it: SampleIntake) {
  const ds = it.dispatches ?? [];
  // Đủ 8 cột như BM 7.1.02: STT · Loại/Tên mẫu · Chỉ tiêu · Đơn vị · Kết quả · Phương pháp · Cán bộ · Ghi chú
  const rows = ds
    .map((d, i) => {
      const name = d.sample_name || it.description || '';
      const qty = (d.quantity ?? 1) > 1 ? ` (SL: ${d.quantity})` : '';
      return (
        `<tr><td style="text-align:center">${i + 1}</td><td>${esc(name)}${qty}</td>` +
        `<td>${esc(d.chi_tieu)}</td><td>${esc(d.don_vi)}</td>` +
        `<td>${esc(d.ket_qua)}</td><td>${esc(d.phuong_phap)}</td><td>${esc(d.can_bo)}</td><td>${esc(d.note)}</td></tr>`
      );
    })
    .join('');

  const inner = `
    ${HEAD}
    <div class="row" style="text-align:right">Mã số: <b>${esc(it.code)}</b></div>
    <h1>Phiếu chuyển mẫu và trả kết quả thử nghiệm</h1>
    <div class="row"><span class="lbl">Loại/Tên mẫu:</span> ${val(it.description)}
        &nbsp;&nbsp;<span class="lbl">Tổng số:</span> ${ds.reduce((n, d) => n + (d.quantity ?? 1), 0)}</div>
    <div class="row"><span class="lbl">Ngày nhận mẫu:</span> ${esc(new Date(it.received_at).toLocaleDateString('vi-VN'))}
        &nbsp;&nbsp;<span class="lbl">Ngày hẹn:</span> ${val(it.due_date)}</div>
    <div class="row"><span class="lbl">Lưu ý:</span> ${val(it.dispatch_note || it.note)}</div>
    <table>
      <thead><tr><th style="width:5%">Stt</th><th>Loại/Tên mẫu</th><th>Chỉ tiêu thử nghiệm</th>
        <th style="width:8%">Đơn vị</th><th>Kết quả</th><th>Phương pháp</th>
        <th>Cán bộ phân tích</th><th>Ghi chú</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="8" style="text-align:center">Chưa có chỉ tiêu</td></tr>'}</tbody>
    </table>
    <div class="sign">
      <div class="role">Người nhận</div>
      <div class="role">Người chuyển mẫu</div>
      <div class="role">Trưởng PTN/Phụ trách kỹ thuật</div>
    </div>
    <div class="foot">BM 7.1/02/RIBE — Lần ban hành 3 · <span class="note">Biểu này chỉ sử dụng trong nội bộ,
      không có giá trị khi sử dụng ngoài PTN.</span></div>`;
  printHtml(`Phieu chuyen mau ${it.code}`, inner);
}
