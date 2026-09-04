/**
 * Hạ tầng dùng chung cho các biểu mẫu in của RIBE (BM 7.1/01, 7.1/02, 7.8/01).
 *
 * Tách khỏi samplePdf.ts vì mỗi biểu mẫu là vài trăm dòng HTML+CSS; gộp cả ba vào
 * một file sẽ chạm trần kích thước (scripts/check-file-size.mjs — trần chỉ được HẠ).
 * Phần thực sự dùng chung chỉ có: thoát ký tự, logo, mở cửa sổ in, và bộ CSS nền.
 */

export function esc(v: unknown): string {
  return String(v ?? '').replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c] as string));
}

/** Giá trị điền lên dòng chấm — rỗng thì để trống cho người dùng viết tay. */
export const val = (v: unknown) => (v == null || v === '' ? '' : esc(v));

/**
 * Ngày dạng dd/mm/yyyy. KHÔNG dùng toLocaleDateString('vi-VN'): nó bỏ số 0 đứng
 * đầu ("23/7/2026") trong khi biểu mẫu giấy luôn ghi đủ hai chữ số.
 */
export function vnDate(iso: string | Date): string {
  const d = typeof iso === 'string' ? new Date(iso) : iso;
  const p2 = (n: number) => String(n).padStart(2, '0');
  return `${p2(d.getDate())}/${p2(d.getMonth() + 1)}/${d.getFullYear()}`;
}

/**
 * Logo lấy từ thư mục public. Cửa sổ in là about:blank nên đường dẫn tương đối
 * không giải được — phải ghép origin tuyệt đối.
 */
export const ORIGIN = typeof window !== 'undefined' ? window.location.origin : '';

export const LOGOS =
  `<img src="${ORIGIN}/nlu-logo.png" alt="NLU">` +
  `<img src="${ORIGIN}/ribe-logo.jpeg" alt="RIBE">`;

/**
 * CSS nền cho mọi biểu mẫu. Mỗi biểu mẫu nối thêm CSS riêng của nó vào sau.
 *
 * `@page { margin: 0 }` là CỐ Ý: trình duyệt vẽ tiêu đề tài liệu + URL vào vùng lề
 * của @page, hết lề thì không còn chỗ vẽ nên hai dòng đó biến mất. Lề thật trả lại
 * bằng padding của body.
 */
export const BASE_CSS = `
    @page { size: A4; margin: 0; }
    * { box-sizing: border-box; }
    body { font-family: 'Times New Roman', serif; color: #000; font-size: 12.5px;
           margin: 0; padding: 10mm 12mm; }

    .logos { white-space: nowrap; }
    .logos img { height: 40px; vertical-align: middle; }
    .logos img + img { margin-left: 6px; }

    table.grid { width: 100%; border-collapse: collapse; table-layout: fixed; }
    table.grid th, table.grid td { border: 1px solid #000; padding: 3px 4px; font-size: 11.5px;
                                   vertical-align: top; word-wrap: break-word; }
    table.grid th { text-align: center; font-weight: bold; }
    table.grid td.c { text-align: center; }
    table.grid tbody tr { height: 22px; }

    .line { display: flex; align-items: flex-end; gap: 4px; margin: 3px 0; }
    .lb { white-space: nowrap; }
    .dot { flex: 1; border-bottom: 1px dotted #000; min-height: 15px; padding: 0 3px; }
    .dot.sm { flex: 0 0 26%; }

    .note { font-style: italic; font-size: 11.5px; }`;

/**
 * Mở cửa sổ in — chỉ gọi print() sau khi logo tải xong, nếu không ảnh sẽ trắng.
 *
 * @param css CSS riêng của biểu mẫu, nối sau BASE_CSS.
 */
export function printHtml(title: string, inner: string, css = '') {
  const w = window.open('', '_blank');
  if (!w) return;
  w.document.write(
    `<html><head><meta charset="utf-8"><title>${esc(title)}</title>` +
      `<style>${BASE_CSS}${css}</style></head><body>${inner}</body></html>`,
  );
  w.document.close();

  const go = () => {
    w.focus();
    w.print();
  };
  const pending = Array.from(w.document.images).filter((i) => !i.complete);
  if (pending.length === 0) return go();

  let left = pending.length;
  let fired = false;
  const done = () => {
    if (!fired) {
      fired = true;
      go();
    }
  };
  pending.forEach((img) => {
    let counted = false;
    const once = () => {
      if (counted) return;
      counted = true;
      if (--left <= 0) done();
    };
    img.addEventListener('load', once);
    img.addEventListener('error', once);
  });
  // Chốt chặn: ảnh hỏng/mạng chậm không được phép treo hộp thoại in.
  setTimeout(done, 3000);
}
