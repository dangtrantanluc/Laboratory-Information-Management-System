#!/usr/bin/env node
/**
 * Trần kích thước file (M-03, M-07).
 *
 * research_service.py đã đạt 1.736 dòng và chứa 9 domain riêng biệt. Không có
 * trần cứng thì mọi service đều đi theo con đường đó, vì tiện nhất luôn là thêm
 * hàm vào file sẵn có thay vì tạo file mới.
 *
 * 800 dòng không phải con số thẩm mỹ — nó là ngưỡng mà nhiều người sửa nhiều
 * domain trong cùng một file bắt đầu conflict merge liên tục.
 *
 * CƠ CHẾ MỘT CHIỀU: file trong GRANDFATHERED có trần riêng, và khi nó giảm đủ
 * nhiều thì script BÁO LỖI buộc phải hạ trần xuống. Nợ không bao giờ đi ngược.
 *
 * Xem MAINTAINABILITY_PLAN.md §T0.2.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const LIMIT = 800;
const ROOT = process.cwd();

/**
 * File vượt trần TẠI THỜI ĐIỂM đặt luật (2026-07-26).
 * Danh sách này CHỈ ĐƯỢC NGẮN ĐI và các trần CHỈ ĐƯỢC HẠ XUỐNG.
 */
const GRANDFATHERED = new Map([
  // research_service.py: 1.736 dòng → tách thành research/* (T1.1 xong)
  // chemical_service.py:   850 dòng → tách thành chemical/* (T1.2 xong)
  ['lims-frontend/src/types/index.ts', 1949], // T4.3 thay bằng bản sinh từ OpenAPI; m33 tách ./customer
  ['lims-frontend/src/pages/SampleFlow.tsx', 1208], // T5.1 tách theo tab; m33 tách IntakeCreateModal
  ['lims-frontend/src/pages/SampleDetail.tsx', 948], // T5.1 tách theo panel
]);

/** Ngưỡng buộc hạ trần: giảm hơn ngần này dòng mà chưa cập nhật GRANDFATHERED. */
const SLACK = 100;

/** File sinh tự động — con người không đọc chúng nên trần vô nghĩa. */
const GENERATED = [/\.gen\.(ts|tsx|py)$/, /src[/\\]types[/\\]api\.ts$/];

const SKIP_DIRS = new Set([
  'node_modules', 'dist', 'build', '__pycache__', '.git',
  'alembic', '.venv', 'venv', 'coverage',
]);

function walk(dir, out = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const name of entries) {
    if (SKIP_DIRS.has(name)) continue;
    const p = join(dir, name);
    let st;
    try {
      st = statSync(p);
    } catch {
      continue;
    }
    if (st.isDirectory()) walk(p, out);
    else if (/\.(py|ts|tsx)$/.test(p)) out.push(p);
  }
  return out;
}

/** Đếm dòng theo đúng ngữ nghĩa `wc -l`: không tính phần tử rỗng sau \n cuối. */
function countLines(abs) {
  const text = readFileSync(abs, 'utf8');
  if (text === '') return 0;
  const parts = text.split('\n');
  if (parts[parts.length - 1] === '') parts.pop();
  return parts.length;
}

const files = [
  ...walk(join(ROOT, 'lims-backend', 'app')),
  ...walk(join(ROOT, 'lims-frontend', 'src')),
];

const violations = [];
const shouldTighten = [];
const seenGrandfathered = new Set();

for (const abs of files) {
  const rel = relative(ROOT, abs).split(sep).join('/');
  if (GENERATED.some((re) => re.test(rel))) continue;

  const lines = countLines(abs);
  const cap = GRANDFATHERED.get(rel);

  if (cap === undefined) {
    if (lines > LIMIT) violations.push(`${rel}: ${lines} dòng (trần ${LIMIT})`);
    continue;
  }

  seenGrandfathered.add(rel);
  if (lines > cap) {
    violations.push(`${rel}: ${lines} dòng (trần chuyển tiếp ${cap})`);
  } else if (lines <= LIMIT) {
    shouldTighten.push(`${rel}: còn ${lines} dòng — đã dưới ${LIMIT}, BỎ khỏi GRANDFATHERED`);
  } else if (lines < cap - SLACK) {
    shouldTighten.push(`${rel}: còn ${lines} dòng — hạ trần GRANDFATHERED từ ${cap} xuống ${lines}`);
  }
}

for (const rel of GRANDFATHERED.keys()) {
  if (!seenGrandfathered.has(rel)) {
    shouldTighten.push(`${rel}: không còn tồn tại — BỎ khỏi GRANDFATHERED`);
  }
}

if (violations.length || shouldTighten.length) {
  if (violations.length) {
    console.error('✖ Vượt trần kích thước file:');
    for (const v of violations) console.error('    ' + v);
    console.error('\n  Tách theo ranh giới domain, đừng nới trần.');
  }
  if (shouldTighten.length) {
    console.error((violations.length ? '\n' : '') + '✖ Nợ đã trả nhưng trần chưa hạ:');
    for (const s of shouldTighten) console.error('    ' + s);
    console.error('\n  GRANDFATHERED chỉ đi một chiều — cập nhật scripts/check-file-size.mjs.');
  }
  console.error('\n  Xem MAINTAINABILITY_PLAN.md §T0.2 và CONTRIBUTING.md §2.');
  process.exit(1);
}

console.log(
  `✔ ${files.length} file — không file nào vượt ${LIMIT} dòng ` +
    `(${GRANDFATHERED.size} file đang trong diện chuyển tiếp)`,
);
