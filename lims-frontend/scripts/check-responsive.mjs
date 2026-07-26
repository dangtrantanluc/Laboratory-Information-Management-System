#!/usr/bin/env node
/**
 * Kiểm tra tĩnh các BẤT BIẾN responsive của LIMS frontend.
 *
 * Không cần dependency — chạy bằng `npm run check:responsive`.
 * Mục đích: chặn hồi quy. Mỗi luật ở đây tương ứng một lỗi đã thực sự tồn tại
 * trong codebase trước đợt refactor responsive.
 *
 * Đây KHÔNG thay thế kiểm thử thủ công trên thiết bị — xem RESPONSIVE_TESTPLAN.md.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(fileURLToPath(new URL('.', import.meta.url)), '..');
const SRC = join(ROOT, 'src');

/* ─────────────────────── tiện ích ─────────────────────── */

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.tsx?$/.test(p)) out.push(p);
  }
  return out;
}

const files = walk(SRC);
const rel = (p) => relative(ROOT, p);
const failures = [];
const warnings = [];

function fail(file, line, rule, msg) {
  failures.push({ file: rel(file), line, rule, msg });
}
function warn(file, line, rule, msg) {
  warnings.push({ file: rel(file), line, rule, msg });
}

/** Duyệt từng dòng của từng file. */
function eachLine(cb) {
  for (const file of files) {
    const lines = readFileSync(file, 'utf8').split('\n');
    lines.forEach((text, i) => cb({ file, line: i + 1, text, lines }));
  }
}

const BP_PREFIX = /(?:xs|sm|md|lg|xl|2xl|3xl):/;

/* ─────────────────────── R1: lưới cứng ───────────────────────
 * `grid grid-cols-N` (N≥2) không kèm breakpoint ⇒ N cột kể cả trên 360px.
 * Ngoại lệ: ô thống kê nhỏ (label + số) — 2–3 cột trên mobile là đúng.
 */
const R1_ALLOW = [
  // file : lý do
  ['pages/Equipment.tsx', 'ô thống kê kết quả cron — label + số ngắn'],
  ['pages/Nonconformities.tsx', 'ô thống kê kết quả cron — label + số ngắn'],
  ['pages/DocumentDetail.tsx', 'ô thống kê lượt xem/tải/sửa — label + số ngắn'],
];
eachLine(({ file, line, text }) => {
  if (!/className=/.test(text)) return;
  const m = text.match(/\bgrid\s+grid-cols-([2-9])\b/);
  if (!m) return;
  // Phải có biến thể grid-cols THEO BREAKPOINT (vd md:grid-cols-2).
  // `sm:gap-3` không tính — nó không đổi số cột.
  if (new RegExp(BP_PREFIX.source + 'grid-cols-').test(text)) return;
  const allowed = R1_ALLOW.some(([f]) => rel(file).endsWith(f));
  if (allowed) {
    warn(file, line, 'R1', `lưới ${m[0]} cố định (đã cho phép: ô thống kê)`);
  } else {
    fail(file, line, 'R1', `\`${m[0]}\` không có biến thể breakpoint → ${m[1]} cột trên màn 360px`);
  }
});

/* ─────────────────────── R2: col-span trần ───────────────────────
 * `col-span-N` không prefix sẽ sai ngay khi lưới cha đổi số cột theo breakpoint.
 */
const R2_ALLOW = [
  ['pages/Risks.tsx', 'ma trận rủi ro 5×5 — lưới cố định, đã bọc overflow-x-auto'],
];
eachLine(({ file, line, text }) => {
  const m = text.match(/className="[^"]*?(?<![:-])\bcol-span-([0-9]+|full)\b/);
  if (!m) return;
  // Mobile-first hợp lệ: `col-span-12 sm:col-span-3` — giá trị trần là bậc mobile,
  // đã có biến thể theo breakpoint cho màn rộng hơn. Chỉ báo lỗi khi KHÔNG có biến thể nào.
  if (new RegExp(BP_PREFIX.source + 'col-span-').test(text)) return;
  const allowed = R2_ALLOW.some(([f]) => rel(file).endsWith(f));
  if (allowed) warn(file, line, 'R2', `col-span-${m[1]} trần (đã cho phép)`);
  else fail(file, line, 'R2', `\`col-span-${m[1]}\` không có biến thể breakpoint nào`);
});

/* ─────────────────────── R3: control lọc bị ghim bề rộng ───────────────────────
 * `max-w-[NNNpx]` trần khiến <Select> không giãn full-width trên mobile.
 */
eachLine(({ file, line, text }) => {
  if (/className="max-w-\[\d+px\]"/.test(text)) {
    fail(file, line, 'R3', 'max-w cứng không kèm `w-full` → control không giãn trên mobile');
  }
});

/* ─────────────────────── R4: 100vh trên iOS ───────────────────────
 * h-screen/min-h-screen dùng 100vh — sai khi thanh URL iOS Safari co giãn.
 */
eachLine(({ file, line, text }) => {
  const m = text.match(/className="[^"]*\b(h-screen|min-h-screen)\b(?!-dvh)/);
  if (m) fail(file, line, 'R4', `\`${m[1]}\` dùng 100vh → dùng \`${m[1]}-dvh\` cho iOS Safari`);
});

/* ─────────────────────── R5: khoá cuộn body thủ công ───────────────────────
 * Overlay lồng nhau (ConfirmDialog trong Modal) sẽ mở khoá sớm nếu mỗi lớp tự set.
 */
eachLine(({ file, line, text }) => {
  if (rel(file).endsWith('lib/useFocusTrap.ts')) return; // nơi cài đặt hợp lệ
  if (/document\.body\.style\.overflow\s*=/.test(text)) {
    fail(file, line, 'R5', 'set body.style.overflow trực tiếp → dùng useBodyScrollLock (có đếm tham chiếu)');
  }
});

/* ─────────────────────── R6: bảng thô phải cuộn ngang được ───────────────────────
 * <table> có min-w mà cha không overflow-x-auto ⇒ tràn ra ngoài trang.
 */
eachLine(({ file, line, text, lines }) => {
  if (!/<table\b/.test(text)) return;
  if (rel(file).endsWith('components/ui/DataTable.tsx')) return; // đã xử lý nội bộ
  const ctx = lines.slice(Math.max(0, line - 4), line).join(' ');
  if (!/overflow-x-auto/.test(ctx)) {
    // bảng nhỏ không đặt min-w thì co giãn tự nhiên được → chỉ cảnh báo
    if (/min-w-\[/.test(text)) {
      fail(file, line, 'R6', '<table> có min-w nhưng cha không có overflow-x-auto → tràn trang');
    } else {
      warn(file, line, 'R6', '<table> không nằm trong vùng cuộn ngang — kiểm tra thủ công');
    }
  }
});

/* ─────────────────────── R7: ngưỡng JS phải khớp Tailwind ─────────────────────── */
{
  const tw = readFileSync(join(ROOT, 'tailwind.config.js'), 'utf8');
  const hook = readFileSync(join(SRC, 'lib/useMediaQuery.ts'), 'utf8');
  for (const [name, px] of [
    ['xs', 480],
    ['3xl', 1920],
  ]) {
    const inTw = new RegExp(`['"]?${name}['"]?\\s*:\\s*['"]${px}px['"]`).test(tw);
    const inHook = new RegExp(`['"]?${name}['"]?\\s*:\\s*${px}\\b`).test(hook);
    if (!inTw) fail(join(ROOT, 'tailwind.config.js'), 0, 'R7', `thiếu breakpoint ${name}=${px}px`);
    if (!inHook) fail(join(SRC, 'lib/useMediaQuery.ts'), 0, 'R7', `BP.${name} không khớp ${px}`);
  }
}

/* ─────────────────────── R8: thẻ meta viewport ─────────────────────── */
{
  const html = readFileSync(join(ROOT, 'index.html'), 'utf8');
  const meta = html.match(/<meta\s+name="viewport"[^>]*>/)?.[0] ?? '';
  if (!meta) fail(join(ROOT, 'index.html'), 0, 'R8', 'thiếu thẻ meta viewport');
  else {
    if (!/viewport-fit=cover/.test(meta))
      fail(join(ROOT, 'index.html'), 0, 'R8', 'thiếu viewport-fit=cover → env(safe-area-inset-*) vô hiệu');
    if (/user-scalable\s*=\s*no|maximum-scale\s*=\s*1/.test(meta))
      fail(join(ROOT, 'index.html'), 0, 'R8', 'chặn zoom → vi phạm WCAG 1.4.4');
  }
}

/* ─────────────────────── R9: DataTable giữ đủ năng lực ─────────────────────── */
{
  const dt = readFileSync(join(SRC, 'components/ui/DataTable.tsx'), 'utf8');
  for (const token of ['mobileMode', 'priority', 'stickyFirstCol', 'aria-sort']) {
    if (!dt.includes(token))
      fail(join(SRC, 'components/ui/DataTable.tsx'), 0, 'R9', `mất khả năng: \`${token}\``);
  }
}

/* ─────────────────────── R10: Modal giữ đủ năng lực ─────────────────────── */
{
  const md = readFileSync(join(SRC, 'components/ui/Modal.tsx'), 'utf8');
  for (const token of ['useFocusTrap', 'useBodyScrollLock', 'aria-labelledby', 'max-h-sheet']) {
    if (!md.includes(token))
      fail(join(SRC, 'components/ui/Modal.tsx'), 0, 'R10', `mất khả năng: \`${token}\``);
  }
}

/* ─────────────────────── báo cáo ─────────────────────── */

const RULE_NAMES = {
  R1: 'Lưới cố định nhiều cột',
  R2: 'col-span thiếu breakpoint',
  R3: 'Control lọc ghim bề rộng',
  R4: '100vh trên iOS',
  R5: 'Khoá cuộn body thủ công',
  R6: 'Bảng thô không cuộn ngang được',
  R7: 'Ngưỡng JS lệch Tailwind',
  R8: 'Thẻ meta viewport',
  R9: 'Năng lực DataTable',
  R10: 'Năng lực Modal',
};

function print(list, icon) {
  const byRule = new Map();
  for (const f of list) {
    if (!byRule.has(f.rule)) byRule.set(f.rule, []);
    byRule.get(f.rule).push(f);
  }
  for (const [rule, items] of [...byRule].sort()) {
    console.log(`\n${icon} ${rule} — ${RULE_NAMES[rule]} (${items.length})`);
    for (const it of items) {
      console.log(`   ${it.file}${it.line ? ':' + it.line : ''}  ${it.msg}`);
    }
  }
}

console.log(`Đã quét ${files.length} file trong src/`);
if (warnings.length) print(warnings, '⚠');
if (failures.length) {
  print(failures, '✖');
  console.log(`\n✖ ${failures.length} vi phạm, ${warnings.length} cảnh báo\n`);
  process.exit(1);
}
console.log(`\n✔ Tất cả bất biến responsive đạt (${warnings.length} cảnh báo đã được chấp nhận)\n`);
