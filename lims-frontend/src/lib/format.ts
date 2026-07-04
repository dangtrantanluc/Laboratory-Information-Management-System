/** Formatting helpers cho UI tiếng Việt. */

export function formatDate(iso?: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export function formatDateTime(iso?: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Khoảng cách tương đối, ví dụ "2 giờ trước". */
export function timeAgo(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diff = Math.max(0, now - then);
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'vừa xong';
  if (mins < 60) return `${mins} phút trước`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} giờ trước`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} ngày trước`;
  return formatDate(iso);
}

export function formatNumber(n: number): string {
  return n.toLocaleString('vi-VN');
}

/**
 * Hiển thị số thập phân dạng STRING từ backend (qty_base, balance_after, unit_price...).
 * KHÔNG parseFloat để tính tiếp — chỉ format cho hiển thị: bỏ số 0 thừa, thêm phân tách hàng nghìn.
 */
export function formatDecimal(s?: string | null, maxFractionDigits = 6): string {
  if (s === undefined || s === null || s === '') return '—';
  const neg = s.trim().startsWith('-');
  const clean = s.trim().replace(/^-/, '');
  const [intPart, fracRaw = ''] = clean.split('.');
  // cắt theo maxFractionDigits rồi bỏ 0 đuôi
  let frac = fracRaw.slice(0, maxFractionDigits).replace(/0+$/, '');
  const intGrouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  const body = frac ? `${intGrouped},${frac}` : intGrouped;
  return (neg ? '-' : '') + body;
}

/** Hiển thị tiền (string decimal 2dp) kèm đơn vị tiền tệ. */
export function formatMoney(s?: string | null, currency = 'VND'): string {
  if (s === undefined || s === null || s === '') return '—';
  return `${formatDecimal(s, 2)} ${currency}`;
}

/** Số lượng kèm đơn vị: "487,5 g". */
export function formatQty(s?: string | null, unit?: string, maxFractionDigits = 4): string {
  if (s === undefined || s === null || s === '') return '—';
  return unit ? `${formatDecimal(s, maxFractionDigits)} ${unit}` : formatDecimal(s, maxFractionDigits);
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  // Tiếng Việt: lấy chữ cái tên cuối + tên trước cuối
  return (parts[parts.length - 2][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Số ngày từ hôm nay tới ngày iso (âm = đã qua). */
export function daysUntil(iso: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(iso);
  target.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86400000);
}

/** Màu avatar ổn định theo tên. */
export function avatarColor(seed: string): string {
  const palette = ['#2f3a55', '#5c6b8a', '#a29f76', '#3b82f6', '#0ea5e9', '#8b5cf6', '#14b8a6'];
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return palette[h % palette.length];
}
