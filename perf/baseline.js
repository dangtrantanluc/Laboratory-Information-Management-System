// perf/baseline.js — kịch bản 60 người dùng giờ cao điểm
// Theo REMEDIATION_PLAN.md §0.3. Chạy: k6 run perf/baseline.js
//
// ⚠ KHÔNG chạy trên production: tạo tải đăng nhập thật và ghi access_stats.
//
// ─────────────────────────────────────────────────────────────────────────────
// SỬA SO VỚI BẢN TRONG PLAN (bắt buộc, nếu không phép đo vô nghĩa):
//
// 1. Bản gốc đăng nhập LẠI ở mỗi vòng lặp. Với 100 iter/phút × 5 phút chia cho
//    20 VU, mỗi tài khoản đăng nhập ~25 lần trong 5 phút — vượt giới hạn
//    10 lần/5 phút/tài khoản (R3.1c) nên 54% request trả 429. Nó đo throughput
//    của /auth/login chứ không đo throughput của ứng dụng.
//    Người dùng thật đăng nhập MỘT lần rồi dùng token suốt buổi làm việc.
//    → `morning_rush` giữ nguyên phần bùng nổ đăng nhập (đó mới là thứ cần đo),
//      `steady` lấy token một lần trong setup rồi tái sử dụng.
//
// 2. Plan bảo tạo 60 tài khoản nhưng vus_max = 60 + 20 = 80, nên VU 61–80 đăng
//    nhập bằng email không tồn tại → sai 5 lần → lockout. Phải tạo đủ 80.
// ─────────────────────────────────────────────────────────────────────────────
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const loginTime = new Trend('login_duration');
const errors = new Rate('errors');
const BASE = __ENV.BASE || 'http://localhost:3060/api/v1';
const PASSWORD = __ENV.LOADTEST_PASSWORD || 'LoadTest123';

export const options = {
  scenarios: {
    // Kịch bản 1: 60 người đăng nhập trong vòng 1 phút (mô phỏng 8h sáng).
    // Đây là phép đo F-04: cả 60 người PHẢI vào được, không ai bị 429.
    morning_rush: { executor: 'per-vu-iterations', vus: 60, iterations: 1, maxDuration: '60s' },
    // Kịch bản 2: duyệt bình thường 100 req/phút trong 5 phút, dùng token có sẵn.
    steady: {
      executor: 'constant-arrival-rate', rate: 100, timeUnit: '1m',
      duration: '5m', preAllocatedVUs: 20, startTime: '60s',
      exec: 'browse',
    },
  },
  thresholds: {
    'http_req_duration{scenario:steady}': ['p(95)<2000'], // mục tiêu p95 < 2s
    errors: ['rate<0.01'],                                 // <1% lỗi
  },
};

/** Lấy một token dùng chung cho pha `steady` — mô phỏng phiên đã đăng nhập. */
export function setup() {
  const res = http.post(`${BASE}/auth/login`, JSON.stringify({
    email: 'loadtest1@lims.local', password: PASSWORD,
  }), { headers: { 'Content-Type': 'application/json' } });
  if (res.status !== 200) throw new Error(`setup login thất bại: ${res.status} ${res.body}`);
  return { token: res.json('data.access_token') };
}

/** Pha 1 — bùng nổ đăng nhập lúc 8h sáng. Mỗi VU một tài khoản riêng. */
export default function () {
  const t0 = Date.now();
  const res = http.post(`${BASE}/auth/login`, JSON.stringify({
    email: `loadtest${__VU}@lims.local`, password: PASSWORD,
  }), { headers: { 'Content-Type': 'application/json' } });
  loginTime.add(Date.now() - t0);

  const ok = check(res, { 'login 200': (r) => r.status === 200 });
  errors.add(!ok);
  if (!ok) return;

  hitDashboard(res.json('data.access_token'));
}

/** Pha 2 — duyệt bình thường bằng token đã có. */
export function browse(data) {
  hitDashboard(data.token);
  sleep(1);
}

/** Dashboard gọi ~6 endpoint song song — mô phỏng đúng như vậy. */
function hitDashboard(token) {
  const h = { Authorization: `Bearer ${token}` };
  const rs = http.batch([
    ['GET', `${BASE}/dashboard`, null, { headers: h }],
    ['GET', `${BASE}/notifications/unread-count`, null, { headers: h }],
    ['GET', `${BASE}/samples?limit=20`, null, { headers: h }],
    ['GET', `${BASE}/documents?limit=20`, null, { headers: h }],
    ['GET', `${BASE}/equipments?limit=20`, null, { headers: h }],
    ['GET', `${BASE}/auth/me`, null, { headers: h }],
  ]);
  rs.forEach((r) => errors.add(r.status >= 400));
}
