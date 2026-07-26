// perf/baseline.js — kịch bản 60 người dùng giờ cao điểm
// Theo REMEDIATION_PLAN.md §0.3. Chạy: k6 run perf/baseline.js
//
// ⚠ KHÔNG chạy trên production: kịch bản tạo tải đăng nhập thật và ghi access_stats.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const loginTime = new Trend('login_duration');
const errors = new Rate('errors');
const BASE = __ENV.BASE || 'http://localhost:3060/api/v1';
const PASSWORD = __ENV.LOADTEST_PASSWORD || 'LoadTest123';

export const options = {
  scenarios: {
    // Kịch bản 1: 60 người đăng nhập trong 30 giây (mô phỏng 8h sáng)
    morning_rush: { executor: 'per-vu-iterations', vus: 60, iterations: 1, maxDuration: '60s' },
    // Kịch bản 2: duyệt bình thường 100 req/phút trong 5 phút
    steady: {
      executor: 'constant-arrival-rate', rate: 100, timeUnit: '1m',
      duration: '5m', preAllocatedVUs: 20, startTime: '60s',
    },
  },
  thresholds: {
    'http_req_duration{scenario:steady}': ['p(95)<2000'], // mục tiêu p95 < 2s
    errors: ['rate<0.01'],                                 // <1% lỗi
  },
};

export default function () {
  const t0 = Date.now();
  const res = http.post(`${BASE}/auth/login`, JSON.stringify({
    email: `loadtest${__VU}@lims.local`, password: PASSWORD,
  }), { headers: { 'Content-Type': 'application/json' } });
  loginTime.add(Date.now() - t0);

  const ok = check(res, { 'login 200': (r) => r.status === 200 });
  errors.add(!ok);
  if (!ok) return;

  const h = { Authorization: `Bearer ${res.json('data.access_token')}` };
  // Dashboard gọi ~6 endpoint song song — mô phỏng đúng như vậy
  const rs = http.batch([
    ['GET', `${BASE}/reporting/dashboard`, null, { headers: h }],
    ['GET', `${BASE}/notifications/unread-count`, null, { headers: h }],
    ['GET', `${BASE}/samples?limit=20`, null, { headers: h }],
    ['GET', `${BASE}/documents?limit=20`, null, { headers: h }],
    ['GET', `${BASE}/equipments?limit=20`, null, { headers: h }],
    ['GET', `${BASE}/auth/me`, null, { headers: h }],
  ]);
  rs.forEach((r) => errors.add(r.status >= 400));
  sleep(1);
}
