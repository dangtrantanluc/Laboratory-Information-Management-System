# Kế hoạch khắc phục — LIMS Pre-Production

Đi kèm: [ARCHITECTURE_AUDIT.md](./ARCHITECTURE_AUDIT.md) (phát hiện) · tài liệu này (cách sửa).

Mỗi task có: **ID · file chính xác · code paste-được · tiêu chí nghiệm thu (DoD) · giờ công · phụ thuộc · cách xác minh**.

---

## 0. Quy ước

### 0.1 Nhánh & thứ tự merge

```
main
 └── fix/p0-blocking-io          → PR #1  (R1.*)  ⛔ CHẶN GO-LIVE
 └── fix/p0-concurrency          → PR #2  (R2.*)  ⛔
 └── fix/p0-security             → PR #3  (R3.*)  ⛔
 └── fix/p0-ops                  → PR #4  (R4.*)  ⛔
 └── fix/p1-frontend-stability   → PR #5  (R5.*)
 └── fix/p1-database             → PR #6  (R6.*)
 └── fix/p2-performance          → PR #7  (R7.*)
 └── fix/p2-security-hardening   → PR #8  (R8.*)
 └── feat/p3-infrastructure      → PR #9  (R9.*)
```

**PR #1–#4 phải merge và load-test đạt trước khi go-live.** Không thương lượng.

### 0.2 Definition of Done chung

- [ ] `npm run check` (frontend) và `pytest app/tests` (backend) xanh
- [ ] `docker compose -f docker-compose.prod.yml config` hợp lệ
- [ ] Có bước xác minh cụ thể trong task, đã chạy và dán kết quả vào PR
- [ ] Không đổi hành vi nghiệp vụ (trừ khi task nói rõ)
- [ ] Rollback được: ghi rõ cách quay lui trong mô tả PR

### 0.3 Thiết lập đo tải (làm trước tiên — cần để chứng minh mọi thứ khác)

```bash
# Cài k6 (không cần Docker)
curl -fsSL https://github.com/grafana/k6/releases/download/v0.54.0/k6-v0.54.0-linux-amd64.tar.gz \
  | tar xz --strip-components=1 -C /usr/local/bin k6-v0.54.0-linux-amd64/k6
```

```js
// perf/baseline.js — kịch bản 60 người dùng giờ cao điểm
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const loginTime = new Trend('login_duration');
const errors = new Rate('errors');
const BASE = __ENV.BASE || 'http://localhost:3060/api/v1';

export const options = {
  scenarios: {
    // Kịch bản 1: 60 người đăng nhập trong 30 giây (mô phỏng 8h sáng)
    morning_rush: { executor: 'per-vu-iterations', vus: 60, iterations: 1, maxDuration: '60s' },
    // Kịch bản 2: duyệt bình thường 100 req/phút trong 5 phút
    steady:       { executor: 'constant-arrival-rate', rate: 100, timeUnit: '1m',
                    duration: '5m', preAllocatedVUs: 20, startTime: '60s' },
  },
  thresholds: {
    'http_req_duration{scenario:steady}': ['p(95)<2000'],   // mục tiêu p95 < 2s
    errors: ['rate<0.01'],                                   // <1% lỗi
  },
};

export default function () {
  const t0 = Date.now();
  const res = http.post(`${BASE}/auth/login`, JSON.stringify({
    email: `loadtest${__VU}@lims.local`, password: 'LoadTest123',
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
```

```bash
# Tạo 60 tài khoản load-test (KHÔNG chạy trên production)
docker exec lims-postgres psql -U lims -d lims -c "
INSERT INTO users (email, password_hash, full_name, role, status, password_changed_at)
SELECT 'loadtest'||g||'@lims.local',
       (SELECT password_hash FROM users WHERE email='admin@lims.local'),
       'Load Test '||g, 'staff', 'active', now()
FROM generate_series(1,60) g
ON CONFLICT (email) DO NOTHING;"
# ⚠ Mật khẩu = mật khẩu admin hiện tại. Đổi 'LoadTest123' trong script cho khớp,
#   hoặc tạo hash riêng. XOÁ SẠCH sau khi đo xong.

k6 run perf/baseline.js
```

**Chạy baseline TRƯỚC khi sửa** để có số đối chứng. Ghi lại: p95, tỉ lệ lỗi, thời gian login.

---

## Tuần 1 — ⛔ Chặn go-live

### PR #1 · R1 — Gỡ nút chặn event loop (F-01)

#### R1.1 — Đổi 16 endpoint `async def` → `def` · **4h**

**Vì sao an toàn tuyệt đối:** tôi đã kiểm từng file — **cả 16 endpoint chỉ `await` đúng một
thứ là `file.read()`**, không có `await` nào khác. Nên không mất tính năng gì khi bỏ `async`.

| # | File | Dòng | Hàm |
|---|---|---:|---|
| 1 | `app/routers/attachments.py` | 25 | `upload_attachment` |
| 2 | `app/routers/results.py` | 105 | `upload_result_attachment` |
| 3 | `app/routers/equipments.py` | 144 | `add_attachment` |
| 4 | `app/routers/equipments.py` | 207 | `create_calibration` ⚠ có 2 file |
| 5 | `app/routers/chemicals.py` | 298 | `upload_msds` |
| 6 | `app/routers/chemical_lots.py` | 89 | `upload_coa` |
| 7 | `app/routers/forms.py` | 102 | `upload_template_file` |
| 8 | `app/routers/forms.py` | 278 | `upload_submission_file` |
| 9 | `app/routers/documents.py` | 158 | `create_document` |
| 10 | `app/routers/documents.py` | 299 | `create_version` |
| 11 | `app/routers/documents.py` | 362 | `replace_version_file` |
| 12 | `app/routers/samples.py` | 202 | `upload_sample_attachment` |
| 13 | `app/routers/test_requests.py` | 179 | `upload_request_attachment` |
| 14 | `app/routers/research.py` | 310 | `upload_publication_attachment` |
| 15 | `app/routers/hr_profiles.py` | 299 | `upload_competence_attachment` |
| 16 | `app/routers/auth.py` | 341 | `upload_my_avatar` |

**Mẫu sửa** (áp cho từng hàm):

```python
# TRƯỚC
async def upload_attachment(request: Request, file: UploadFile = File(...), ...):
    content = await file.read()

# SAU — FastAPI tự đẩy hàm `def` sang threadpool, không chặn event loop nữa
def upload_attachment(request: Request, file: UploadFile = File(...), ...):
    # UploadFile.file là SpooledTemporaryFile — đọc đồng bộ, an toàn trong threadpool
    content = file.file.read()
```

Trường hợp đặc biệt **#4 `equipments.py:207`** có 2 file (`cert` optional):

```python
def create_calibration(..., cert: UploadFile | None = File(None), ...):
    cert_content = cert.file.read() if cert is not None else None
```

**Script hỗ trợ** (vẫn phải rà tay từng chỗ sau khi chạy):

```bash
cd lims-backend
# Bước 1: bỏ async ở đúng 16 dòng đã liệt kê
for spec in "attachments.py:25" "results.py:105" "equipments.py:144" "equipments.py:207" \
            "chemicals.py:298" "chemical_lots.py:89" "forms.py:102" "forms.py:278" \
            "documents.py:158" "documents.py:299" "documents.py:362" "samples.py:202" \
            "test_requests.py:179" "research.py:310" "hr_profiles.py:299" "auth.py:341"; do
  f="app/routers/${spec%%:*}"; ln="${spec##*:}"
  sed -i "${ln}s/^async def /def /" "$f"
done
# Bước 2: đổi await file.read() → file.file.read()
sed -i 's/await file\.read()/file.file.read()/g; s/await cert\.read()/cert.file.read()/g' app/routers/*.py
# Bước 3: xác nhận không còn async def nào trong routers
grep -rn "^async def " app/routers/ && echo "⚠ CÒN SÓT" || echo "✔ sạch"
grep -rn "await " app/routers/ && echo "⚠ còn await mồ côi" || echo "✔ không còn await"
```

**DoD**
- [ ] `grep -rn "^async def " app/routers/` → rỗng
- [ ] `grep -rn "await " app/routers/` → rỗng
- [ ] Upload thử 1 file mỗi loại (attachment, tài liệu, biểu mẫu, avatar) → 200
- [ ] **Xác minh sửa được lỗi:**

```bash
# Terminal 1
dd if=/dev/urandom of=/tmp/big.bin bs=1M count=18
time curl -X POST http://localhost:3060/api/v1/attachments -H "Authorization: Bearer $T" \
  -F owner_type=sample -F owner_id=$ID -F file=@/tmp/big.bin
# Terminal 2 (chạy song song)
while true; do curl -s -o /dev/null -w "%{time_total}\n" http://localhost:3060/api/v1/health; sleep 0.2; done
# TRƯỚC: /health nhảy lên ~1.5s   SAU: giữ nguyên ~0.01s
```

**Rollback** `git revert` PR — không có thay đổi schema/dữ liệu.

---

#### R1.2 — Giới hạn số upload đồng thời · **2h** · phụ thuộc R1.1

Sau R1.1, upload chạy trong threadpool (40 thread). 40 upload × 20MB = **800MB RAM** →
OOM. Cần semaphore.

```python
# app/core/concurrency.py  ✨ file mới
"""Hạn mức đồng thời cho tác vụ nặng RAM/CPU.

Sau khi upload chuyển sang threadpool (R1.1), 40 thread × 20MB = 800MB RAM. Semaphore
giới hạn số upload chạy cùng lúc, phần dư xếp hàng thay vì làm OOM cả container.
"""
import threading
from contextlib import contextmanager

from app.core.exceptions import AppException

# 6 upload đồng thời × 20MB = 120MB — vừa với mem_limit 1g của lims-api
_upload_sem = threading.BoundedSemaphore(6)
# Xuất Excel/PDF là CPU-bound, giới hạn chặt hơn
_export_sem = threading.BoundedSemaphore(2)


@contextmanager
def upload_slot(timeout: float = 30.0):
    if not _upload_sem.acquire(timeout=timeout):
        raise AppException(
            "SERVER_BUSY", "Hệ thống đang xử lý nhiều tệp. Vui lòng thử lại sau ít phút.", 503
        )
    try:
        yield
    finally:
        _upload_sem.release()


@contextmanager
def export_slot(timeout: float = 60.0):
    if not _export_sem.acquire(timeout=timeout):
        raise AppException(
            "SERVER_BUSY", "Hệ thống đang xuất báo cáo khác. Vui lòng thử lại sau.", 503
        )
    try:
        yield
    finally:
        _export_sem.release()
```

Áp vào từng endpoint upload:

```python
from app.core.concurrency import upload_slot

def upload_attachment(...):
    with upload_slot():
        content = file.file.read()
        data = attachment_service.create_attachment(...)
    return ok(data)
```

Và vào các endpoint xuất báo cáo (`form_service.py:373`, `chemical_report_service.py:117`,
`document_service.py:728`, `report_export_service.py`).

**DoD** Bắn 20 upload song song → 6 chạy, 14 xếp hàng, **không cái nào 500**; RAM container
không vượt 700MB (`docker stats lims-api`).

---

### PR #2 · R2 — Concurrency & connection pool (F-02, F-03)

#### R2.1 — Uvicorn nhiều worker + proxy headers · **1h**

```dockerfile
# lims-backend/Dockerfile — thay dòng 30
# --workers 4: dùng hết 4 nhân. APScheduler đã có leader-lock Redis (scheduler.py:168)
#   nên chỉ 1 worker chạy cron — đã kiểm, an toàn.
# --proxy-headers + --forwarded-allow-ips: BẮT BUỘC, xem R3.1
# --timeout-graceful-shutdown: chờ request đang chạy xong khi deploy
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8060", \
     "--workers", "4", \
     "--proxy-headers", "--forwarded-allow-ips", "*", \
     "--timeout-graceful-shutdown", "30"]
```

> `--forwarded-allow-ips *` an toàn **chỉ khi** lims-api không publish cổng ra host.
> Overlay `docker-compose.cloudflare.yml` đã gỡ ports ✔. Với `docker-compose.prod.yml`
> thuần, phải gỡ `ports: - "8060:8060"` trước.

⚠ **Số worker phải khớp số nhân host.** Máy 2 nhân → `--workers 2`. Tham số hoá:

```dockerfile
ENV UVICORN_WORKERS=4
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port 8060 \
     --workers ${UVICORN_WORKERS} --proxy-headers --forwarded-allow-ips '*' \
     --timeout-graceful-shutdown 30"]
```

#### R2.2 — Chỉnh pool cho khớp số worker · **2h**

**Phép tính bắt buộc:**
```
tổng kết nối = workers × (pool_size + max_overflow) + dự phòng
             = 4 × (8 + 12) + 20 (migrate/psql/backup)
             = 100  →  cần max_connections ≥ 120
```

```bash
# .env / .env.prod
DB_POOL_SIZE=8
DB_MAX_OVERFLOW=12
DB_POOL_TIMEOUT=5          # fail nhanh còn hơn treo 10s rồi vẫn lỗi
UVICORN_WORKERS=4
```

```yaml
# docker-compose.prod.yml
postgres:
  command:
    - postgres
    - -c
    - max_connections=200
    - -c
    - shared_buffers=512MB
    - -c
    - work_mem=16MB
    - -c
    - log_min_duration_statement=500ms    # bắt slow query, phục vụ R6.3
  mem_limit: 2g                            # đã có ✔
```

Thêm giới hạn threadpool cho khớp pool (mặc định 40 > 20 connection/worker):

```python
# app/main.py — trong lifespan/startup
import anyio
@app.on_event("startup")
def _limit_threadpool():
    # Threadpool 40 thread tranh 20 connection → 20 thread chờ vô ích.
    # Đặt bằng pool để hàng đợi nằm ở tầng HTTP (có timeout rõ ràng) thay vì tầng DB.
    anyio.to_thread.current_default_thread_limiter().total_tokens = (
        settings.db_pool_size + settings.db_max_overflow
    )
```

**DoD**
```bash
k6 run perf/baseline.js
# Kỳ vọng: errors < 1%, p95 < 2000ms, 0 lỗi "QueuePool limit ... reached"
docker exec lims-postgres psql -U lims -d lims -c \
  "SELECT count(*), state FROM pg_stat_activity WHERE datname='lims' GROUP BY state;"
# Kỳ vọng: tổng < 120
docker logs lims-api 2>&1 | grep -c "QueuePool limit"   # phải = 0
```

---

### PR #3 · R3 — Bảo mật chặn go-live (F-04, F-05)

#### R3.1 — Sửa IP thật cho rate limit + audit log · **3h** · phụ thuộc R2.1

**3 phần, thiếu phần nào cũng vô hiệu.**

**(a)** `Dockerfile` — `--proxy-headers` (đã làm ở R2.1) ✔

**(b)** `lims-frontend/nginx.conf` — chuyển tiếp IP thật:

```nginx
location /api/ {
    proxy_pass http://lims-api:8060/api/;
    proxy_http_version 1.1;

    # Cloudflare đặt IP người dùng ở CF-Connecting-IP; nếu gọi trực tiếp trong LAN
    # thì dùng $remote_addr. KHÔNG dùng $proxy_add_x_forwarded_for vì nó cộng dồn
    # chuỗi và uvicorn sẽ lấy phần tử đầu — có thể bị client giả mạo.
    set $real_client $remote_addr;
    if ($http_cf_connecting_ip) { set $real_client $http_cf_connecting_ip; }
    proxy_set_header X-Forwarded-For  $real_client;
    proxy_set_header X-Real-IP        $real_client;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Host $host;
    client_max_body_size 25m;
}
```

**(c)** `app/core/rate_limit.py` — key theo IP thật + tách hạn mức theo tài khoản:

```python
def _client_ip(request: Request) -> str:
    """IP thật của người dùng.

    Tin X-Real-IP vì nginx GHI ĐÈ header này (không cộng dồn) và lims-api không
    publish cổng ra host — không ai gọi thẳng được để giả mạo.
    """
    return (
        request.headers.get("x-real-ip")
        or (request.client.host if request.client else "unknown")
    )


def rate_limit(key_prefix: str, *, limit: int, window_seconds: int, by_body_email: bool = False):
    def _dep(request: Request) -> None:
        ip = _client_ip(request)
        key = f"ratelimit:{key_prefix}:{ip}"
        ...
```

Với `/auth/login`, `/auth/forgot-password`, `/auth/register` — **nên key theo cả email**
để một IP văn phòng chung không khoá lẫn nhau. Vì body đã được đọc bởi Pydantic, làm
trong service thay vì dependency:

```python
# app/services/auth_service.py — trong login(), sau _check_lockout
_check_rate("login", f"{email_norm}|{ip}", limit=10, window=300)
```

**DoD**
```bash
# 1. IP thật đã tới backend chưa
curl -s http://localhost:3060/api/v1/auth/login -X POST -H 'Content-Type: application/json' \
  -d '{"email":"a@b.c","password":"x"}' >/dev/null
docker exec lims-postgres psql -U lims -d lims -tAc \
  "SELECT ip FROM audit_logs ORDER BY created_at DESC LIMIT 1;"
# TRƯỚC: 172.21.0.6    SAU: IP thật của máy bạn

# 2. Rate limit không còn khoá chéo
for i in $(seq 1 25); do
  curl -s -o /dev/null -w "%{http_code} " -X POST http://localhost:3060/api/v1/auth/login \
    -H 'Content-Type: application/json' -H "X-Real-IP: 10.0.0.$i" \
    -d '{"email":"a@b.c","password":"x"}'
done; echo
# Kỳ vọng: 401 ×25 (mỗi IP một rổ), KHÔNG có 429
```

#### R3.2 — Redis bền vững · **1h**

```yaml
# docker-compose.prod.yml VÀ docker-compose.yml
redis:
  command:
    - redis-server
    - --requirepass
    - ${REDIS_PASSWORD:?}
    # AOF: jti denylist phải sống sót qua restart, nếu không token đã thu hồi dùng lại được
    - --appendonly
    - "yes"
    - --appendfsync
    - everysec
    - --maxmemory
    - 384mb
    # noeviction, KHÔNG dùng allkeys-lru: khi đầy, LRU sẽ xoá jti denylist để lấy chỗ
    # → chính xác là lỗ hổng ta đang bịt.
    - --maxmemory-policy
    - noeviction
```

Bổ sung thu hẹp cửa sổ rủi ro:
```bash
ACCESS_TOKEN_TTL_MINUTES=10      # từ 30 → 10
```

**DoD**
```bash
T=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
    -d '{"email":"admin@lims.local","password":"..."}' | jq -r .data.access_token)
curl -s -o /dev/null -w "%{http_code}\n" -X POST $API/auth/logout -H "Authorization: Bearer $T"  # 204
curl -s -o /dev/null -w "%{http_code}\n" $API/auth/me -H "Authorization: Bearer $T"              # 401
docker restart lims-redis && sleep 6
curl -s -o /dev/null -w "%{http_code}\n" $API/auth/me -H "Authorization: Bearer $T"              # PHẢI 401
docker exec lims-redis ls -la /data/    # phải thấy appendonlydir/
```

---

### PR #4 · R4 — Vận hành chặn go-live (F-06, F-14)

#### R4.1 — Backup + diễn tập phục hồi · **4h**

```bash
sudo tee /usr/local/bin/lims-backup >/dev/null <<'EOF'
#!/bin/bash
# Sao lưu LIMS. Chạy hằng ngày qua cron. Thoát != 0 nếu có lỗi (để cron gửi cảnh báo).
set -euo pipefail
D=/var/backups/lims
REMOTE="${LIMS_BACKUP_REMOTE:-}"    # vd: user@backup-host:/lims
mkdir -p "$D"
TS=$(date +%F_%H%M)

# -Fc = custom format: nén sẵn, restore chọn lọc được từng bảng
docker exec lims-postgres pg_dump -U lims -Fc lims > "$D/db-$TS.dump"
docker run --rm -v lims_miniodata:/data -v "$D":/backup alpine \
  tar czf "/backup/files-$TS.tar.gz" -C /data .

# Kiểm tra dump đọc được — dump hỏng mà không biết còn tệ hơn không có dump
docker exec -i lims-postgres pg_restore --list < "$D/db-$TS.dump" > /dev/null

find "$D" -name '*.dump' -mtime +14 -delete
find "$D" -name '*.tar.gz' -mtime +14 -delete

# BẮT BUỘC: đưa ra khỏi host. Backup cùng máy không phải backup.
[ -n "$REMOTE" ] && rsync -a --delete "$D/" "$REMOTE/"
echo "[lims-backup] OK $TS"
EOF
sudo chmod +x /usr/local/bin/lims-backup
echo "0 2 * * * root LIMS_BACKUP_REMOTE=user@backup:/lims /usr/local/bin/lims-backup >> /var/log/lims-backup.log 2>&1" \
  | sudo tee /etc/cron.d/lims-backup
```

**Diễn tập phục hồi — bắt buộc làm 1 lần, ghi lại thời gian:**

```bash
# Trên máy KHÁC (hoặc compose project khác), KHÔNG phải máy production
docker run -d --name lims-restore-test -e POSTGRES_USER=lims \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=lims -p 55432:5432 postgres:15-alpine
sleep 10
docker exec -i lims-restore-test pg_restore -U lims -d lims --clean --if-exists \
  < /var/backups/lims/db-<TS>.dump
docker exec lims-restore-test psql -U lims -d lims -c \
  "SELECT count(*) FROM users; SELECT count(*) FROM samples; SELECT max(version_num) FROM alembic_version;"
docker rm -f lims-restore-test
```

**DoD** Ghi vào PR: **RTO đo được** (bao lâu để khôi phục), **RPO** (mất tối đa bao nhiêu
giờ dữ liệu = 24h với cron hằng ngày). Nếu RPO 24h không chấp nhận được → thêm WAL archiving.

#### R4.2 — Healthcheck + restart policy + log rotation · **2h**

```yaml
# docker-compose.prod.yml
lims-api:
  restart: unless-stopped
  healthcheck:
    # /health/ready chạm DB+Redis+MinIO — đúng cho readiness
    test: ["CMD-SHELL", "curl -fsS http://localhost:8060/api/v1/health/ready || exit 1"]
    interval: 15s
    timeout: 5s
    retries: 3
    start_period: 90s        # chờ migrate xong, tránh restart loop
  logging:
    driver: json-file
    options: { max-size: "50m", max-file: "5" }   # chặn log phình vô hạn

lims-web:
  restart: unless-stopped
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost/ >/dev/null || exit 1"]
    interval: 30s
    timeout: 5s
    retries: 3
  logging:
    driver: json-file
    options: { max-size: "20m", max-file: "3" }
```

Áp `logging` cho **cả 5 service** (postgres/redis/minio nữa).

> ⚠ `/health/ready` phụ thuộc MinIO. Nếu MinIO chết, API bị đánh unhealthy và restart —
> nhưng restart không cứu được MinIO, thành **restart loop**. Cân nhắc dùng `/health`
> (liveness thuần) cho healthcheck, và để `/health/ready` cho load balancer / cảnh báo.
> **Khuyến nghị:** healthcheck dùng `/health`, cảnh báo dựa trên `/health/ready`.

**DoD**
```bash
docker compose -f docker-compose.prod.yml ps    # cột STATUS hiện (healthy)
docker stop lims-postgres && sleep 60
docker compose -f docker-compose.prod.yml ps    # lims-api → (unhealthy)
docker start lims-postgres
```

---

### 🚦 Cổng go-live

Chỉ deploy khi **tất cả** đạt:

| # | Điều kiện | Cách kiểm |
|---|---|---|
| 1 | `k6 run perf/baseline.js` → p95 < 2s, lỗi < 1% | Dán output vào PR |
| 2 | Upload 18MB không làm `/health` chậm | Test 2 terminal ở R1.1 |
| 3 | 25 IP khác nhau đăng nhập → 0 lỗi 429 | Test ở R3.1 |
| 4 | Restart Redis → token đã logout vẫn 401 | Test ở R3.2 |
| 5 | Đã restore thử backup thành công, có RTO/RPO | Biên bản diễn tập |
| 6 | `docker compose ps` mọi service `(healthy)` | — |
| 7 | 0 lỗi `QueuePool limit` trong log dưới tải | `docker logs \| grep -c` |

---

## Tuần 2 — Ổn định

### PR #5 · R5 — Frontend (F-15, F-16, F-10, F-11)

#### R5.1 — Error Boundary · **3h**

```tsx
// src/components/ErrorBoundary.tsx ✨
import { Component, type ReactNode, type ErrorInfo } from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { getLastCorrelationId } from '@/lib/api';

interface State { error: Error | null }

/**
 * Chặn lỗi render lan ra toàn cây. Không có nó, một `user.department.name` với
 * department=null sẽ unmount toàn bộ app → màn hình trắng, người dùng không có
 * nút nào để bấm.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // TODO(R9.3): gửi về Sentry/backend khi có hạ tầng giám sát
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    const cid = getLastCorrelationId();
    return (
      <div className="flex min-h-screen-dvh flex-col items-center justify-center gap-4 bg-plate px-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-overdue/10 text-overdue">
          <AlertTriangle size={26} />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-ink">Đã xảy ra lỗi hiển thị</h1>
          <p className="mt-1 text-sm text-subink">
            Trang không tải được. Dữ liệu của bạn không bị ảnh hưởng.
          </p>
          {cid && (
            <p className="mt-2 text-xs text-stem">
              Mã sự cố: <code className="font-mono text-ink">{cid}</code>
              <br />Vui lòng gửi mã này cho quản trị viên.
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button onClick={() => window.location.reload()}>
            <RotateCcw size={16} /> Tải lại trang
          </Button>
          <Button variant="secondary" onClick={() => (window.location.href = '/dashboard')}>
            Về trang chủ
          </Button>
        </div>
      </div>
    );
  }
}
```

```tsx
// main.tsx — bọc ngoài cùng, TRONG BrowserRouter để nút "Về trang chủ" hoạt động
<BrowserRouter>
  <ErrorBoundary>
    <ToastProvider><AuthProvider><App /></AuthProvider></ToastProvider>
  </ErrorBoundary>
</BrowserRouter>
```

Thêm vào `lib/api.ts`: lưu correlation-id gần nhất từ header `X-Correlation-Id`.

**DoD** Thêm tạm `throw new Error('test')` vào một trang → thấy màn hình lỗi có mã sự cố,
không phải màn hình trắng. Gỡ dòng test.

#### R5.2 — `useAsync` chống race + huỷ request · **4h** · ảnh hưởng **135 lượt dùng / 55 file**

```ts
// src/lib/useAsync.ts — viết lại
import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Gọi API có chống race condition.
 *
 * Bản cũ có cờ `active` nhưng `reload()` VỨT BỎ hàm cleanup mà `run()` trả về → hai
 * request chồng nhau đều "active", cái về sau đè cái về trước. Bản này dùng số thứ tự
 * tăng dần: chỉ response của lần gọi MỚI NHẤT được ghi vào state.
 *
 * Kèm AbortController để huỷ thật ở tầng mạng, không chỉ phớt lờ kết quả.
 */
export function useAsync<T>(fn: (signal?: AbortSignal) => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const seqRef = useRef(0);
  const acRef = useRef<AbortController | null>(null);

  const run = useCallback(() => {
    acRef.current?.abort();                 // huỷ lần gọi trước
    const ac = new AbortController();
    acRef.current = ac;
    const seq = ++seqRef.current;

    setLoading(true);
    setError(null);
    fn(ac.signal)
      .then((d) => { if (seq === seqRef.current) setData(d); })
      .catch((e) => {
        if (seq !== seqRef.current) return;
        if (e?.name === 'AbortError') return;   // huỷ chủ động, không phải lỗi
        setError(e);
      })
      .finally(() => { if (seq === seqRef.current) setLoading(false); });

    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => run(), [run]);

  return { data, loading, error, reload: run };
}
```

> **Tương thích ngược:** chữ ký `fn` đổi từ `() => Promise<T>` sang `(signal?) => Promise<T>`.
> Tham số optional nên **135 lượt dùng hiện tại vẫn biên dịch được** — không phải sửa gì.
> Chỉ những chỗ muốn huỷ thật mới truyền `signal` xuống `apiGet(path, { signal })`.

**DoD** Mở Network tab, bấm "Làm mới" 5 lần liên tiếp → 4 request đầu ở trạng thái
`canceled`, chỉ request cuối hoàn tất. Dữ liệu hiển thị luôn là của lần cuối.

#### R5.3 — Debounce ô tìm kiếm · **3h**

```ts
// src/lib/useDebounced.ts ✨
import { useEffect, useState } from 'react';

/** Trì hoãn giá trị cho tới khi người dùng ngừng gõ `ms` mili-giây. */
export function useDebounced<T>(value: T, ms = 350): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}
```

Áp cho mọi trang danh sách — mẫu:

```tsx
const [q, setQ] = useState('');
const dq = useDebounced(q);                    // ← thêm dòng này
const { data, loading } = useAsync(
  () => api.listDocuments({ q: dq || undefined, ... }),
  [dq, type, securityLevel],                   // ← dùng dq, KHÔNG dùng q
);
// SearchInput vẫn nhận `q` để gõ mượt
<SearchInput value={q} onChange={setQ} />
```

**Danh sách trang cần sửa** (mọi trang có `SearchInput` + `useAsync` phụ thuộc `q`):
`Documents · Chemicals · Equipment · Users · Risks · Nonconformities · TestParameters ·
SampleRequests · Publications · ResearchProjects · Forms · ActivityReports ·
LabRegistrations · Customers · TrainingCertificates · SampleFlow · Quotations · HrProfiles`

**DoD** Gõ "chloroform" (10 ký tự) → Network tab hiện **1 request**, không phải 10.

#### R5.4 — Phân trang server-side · **8h** · 🔴 sửa lỗi mất dữ liệu

**Đây là lỗi nghiệp vụ, không phải hiệu năng.** `test_parameters` có 614 dòng, UI chỉ nạp
100 → 514 dòng vô hình, không cảnh báo.

Backend đã trả sẵn `paginated(items, page, limit, total)` ✔ — chỉ cần frontend dùng đúng.

```tsx
// DataTable — thêm chế độ server
interface DataTableProps<T> {
  // ...giữ nguyên
  /** Bật phân trang server: cha tự nạp dữ liệu theo page/limit. */
  server?: {
    page: number;
    limit: number;
    total: number;
    onPageChange: (page: number) => void;
    onLimitChange?: (limit: number) => void;
  };
}
```

Khi có `server`, bỏ qua `sorted.slice()` nội bộ và dùng `server.total` cho phần "Hiển thị x–y / N".
Sắp xếp cũng phải chuyển xuống server (`?sort=col&dir=asc`) — nếu không, sort chỉ áp cho
trang hiện tại, gây hiểu nhầm. **Giai đoạn 1: tắt sort khi `server` bật**, làm sort server ở R7.

Mẫu áp dụng:

```tsx
const [page, setPage] = useState(1);
const [limit, setLimit] = useState(20);
const { data, loading } = useAsync(
  () => docsApi.listDocuments({ q: dq, page, limit }),
  [dq, type, page, limit],
);
useEffect(() => setPage(1), [dq, type]);   // đổi bộ lọc → về trang 1

<DataTable
  columns={columns}
  rows={data?.data ?? []}
  loading={loading}
  server={{ page, limit, total: data?.meta.total ?? 0,
            onPageChange: setPage, onLimitChange: setLimit }}
/>
```

**Thứ tự làm** (ưu tiên bảng có nhiều dữ liệu nhất):
1. `TestParameters` (614 dòng — đang mất dữ liệu ngay hôm nay)
2. `Documents`, `Equipment`, `Chemicals`, `Samples`
3. `AuditLogs`, `Users`, phần còn lại

**DoD** `/test-parameters` hiện đúng **614** ở "… / N bản ghi"; sang trang 6 vẫn có dữ liệu.

---

### PR #6 · R6 — Database (F-12, F-13)

#### R6.1 — Index cho 76 khoá ngoại · **3h**

**Chia 2 nhóm theo mức khẩn:**

**Nhóm A — đường truy vấn (làm trước, 5 cột):** những cột thực sự dùng để lọc/join
```
staff_activities.department_id
quotation_items.test_parameter_id
customer_info_requests.requester_user_id
customer_info_requests.decided_by
training_certificates.host_user_id
```

**Nhóm B — cột audit (71 cột):** `created_by`, `updated_by`, `approved_by`, `reviewed_by`,
`closed_by`, `verified_by`, `entered_by`, `submitted_by`, `checked_by`.
Chỉ ảnh hưởng khi **xoá/vô hiệu user** (FK `ON DELETE RESTRICT` phải seq scan).

```python
# alembic/versions/1718870400030_m31_fk_indexes.py ✨
"""m31: Index cho khoá ngoại.

Postgres KHÔNG tự tạo index cho FK (khác MySQL/InnoDB). 76 cột FK đang thiếu index →
mọi thao tác vô hiệu hoá user phải seq scan toàn bộ bảng tham chiếu để kiểm RESTRICT.

Dùng CONCURRENTLY để không khoá bảng khi chạy trên production đang có tải.
"""
from alembic import op

revision = "1718870400030"
down_revision = "1718870400029"

# (bảng, cột) — sinh từ pg_constraint, xem ARCHITECTURE_AUDIT.md §F-13
_FK_INDEXES = [
    # ── Nhóm A: đường truy vấn ──
    ("staff_activities", "department_id"),
    ("quotation_items", "test_parameter_id"),
    ("customer_info_requests", "requester_user_id"),
    ("customer_info_requests", "decided_by"),
    ("training_certificates", "host_user_id"),
    # ── Nhóm B: cột audit ──
    ("users", "created_by"), ("users", "updated_by"),
    ("departments", "created_by"), ("departments", "updated_by"),
    ("customers", "created_by"), ("customers", "updated_by"),
    ("test_requests", "created_by"), ("test_requests", "updated_by"),
    ("samples", "created_by"), ("samples", "updated_by"),
    ("sample_assignments", "created_by"), ("sample_assignments", "updated_by"),
    ("sample_results", "entered_by"), ("sample_results", "approved_by"),
    ("sample_intakes", "created_by"),
    ("chemicals", "created_by"), ("chemicals", "updated_by"),
    ("chemical_lots", "created_by"), ("chemical_lots", "updated_by"),
    ("chemical_recheck_records", "checked_by"),
    ("equipments", "created_by"), ("equipments", "updated_by"),
    ("documents", "created_by"), ("documents", "updated_by"),
    ("document_versions", "submitted_by"), ("document_versions", "reviewed_by"),
    ("document_versions", "approved_by"),
    ("form_templates", "created_by"), ("form_templates", "updated_by"),
    ("form_submissions", "submitted_by"), ("form_submissions", "reviewed_by"),
    ("hr_profiles", "created_by"), ("hr_profiles", "updated_by"),
    ("competences", "created_by"), ("competences", "updated_by"),
    ("risks", "created_by"), ("risks", "updated_by"), ("risks", "closed_by"),
    ("risk_treatments", "created_by"),
    ("capa", "created_by"), ("capa", "closed_by"), ("capa", "verified_by"),
    ("capa_actions", "created_by"),
    ("nonconformities", "updated_by"),
    ("improvements", "created_by"), ("improvements", "updated_by"),
    ("publications", "created_by"), ("publications", "updated_by"),
    ("research_projects", "created_by"), ("research_projects", "updated_by"),
    ("research_contracts", "created_by"), ("research_contracts", "updated_by"),
    ("teaching_courses", "created_by"), ("teaching_courses", "updated_by"),
    ("student_mentorships", "created_by"), ("student_mentorships", "updated_by"),
    ("community_services", "created_by"), ("community_services", "updated_by"),
    ("staff_activities", "created_by"), ("staff_activities", "updated_by"),
    ("training_certificates", "created_by"), ("training_certificates", "updated_by"),
    ("activity_reports", "created_by"), ("activity_reports", "reviewed_by"),
    ("lab_access_cards", "created_by"), ("lab_access_cards", "updated_by"),
    ("lab_registrations", "created_by"), ("lab_registrations", "updated_by"),
    ("lab_registrations", "approved_by"),
    ("quotations", "created_by"),
    ("test_parameters", "created_by"),
]


def upgrade() -> None:
    # CREATE INDEX CONCURRENTLY KHÔNG chạy được trong transaction → phải autocommit
    with op.get_context().autocommit_block():
        for table, col in _FK_INDEXES:
            op.execute(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_{table}_{col} "
                f"ON {table} ({col})"
            )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for table, col in _FK_INDEXES:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS ix_{table}_{col}")
```

⚠ **Rủi ro:** `CONCURRENTLY` có thể để lại index `INVALID` nếu bị ngắt giữa chừng.
Kiểm sau khi chạy:
```sql
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;
-- Nếu có: DROP INDEX <tên>; rồi tạo lại
```

**DoD**
```bash
docker exec lims-postgres psql -U lims -d lims -tAc "
SELECT count(*) FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=ANY(c.conkey)
WHERE c.contype='f' AND NOT EXISTS
  (SELECT 1 FROM pg_index i WHERE i.indrelid=c.conrelid AND a.attnum=ANY(i.indkey));"
# TRƯỚC: 76    SAU: 0
```

#### R6.2 — Sửa N+1 · **8h**

Ưu tiên theo tần suất gọi: `user_service` → `activity_service` → `audit_read_service` →
`activity_report_service` → `nc_common`.

```python
# Mẫu: user_service.list_users — thay vì db.get(Department) cho từng dòng
def list_users(db, *, q, role, department_id, status, page, limit):
    # ...conditions như cũ...
    rows = db.execute(
        select(User).where(*conditions)
        .order_by(User.created_at.desc()).offset((page-1)*limit).limit(limit)
    ).scalars().all()

    # Nạp phòng ban MỘT LƯỢT thay vì N lượt
    dept_ids = {u.department_id for u in rows if u.department_id}
    depts = (
        {d.id: d for d in db.scalars(select(Department).where(Department.id.in_(dept_ids)))}
        if dept_ids else {}
    )
    return [_serialize_user_list(u, depts.get(u.department_id)) for u in rows], total


def _serialize_user_list(user: User, dept: Department | None) -> dict:
    return { ..., "department_name": dept.name if dept else None, ... }
```

**DoD** Bật `DB_ECHO=true`, gọi `GET /users?limit=100`, đếm dòng `SELECT` trong log:
**trước 101 → sau ≤3**.

#### R6.3 — Slow query log + phân tích · **2h**

```yaml
postgres:
  command: [postgres, -c, log_min_duration_statement=500ms, -c, log_line_prefix='%t [%p] %u@%d ']
```
```sql
-- Bật pg_stat_statements để tìm truy vấn tốn nhất
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
SELECT calls, round(mean_exec_time::numeric,1) AS ms, round(total_exec_time::numeric) AS total, query
FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 20;
```

---

## Tuần 3 — Hiệu năng & bảo mật

### PR #7 · R7 — Hiệu năng (F-09, F-18)

#### R7.1 — Code splitting + lazy 58 trang · **6h**

```ts
// vite.config.ts
export default defineConfig({
  // ...
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-charts': ['recharts'],       // ~400KB, chỉ dashboard/báo cáo dùng
          'vendor-icons': ['lucide-react'],
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
});
```

```tsx
// App.tsx — thay 50 import tĩnh bằng lazy
import { lazy, Suspense } from 'react';
import { LoadingState } from '@/components/ui/States';

// Giữ TĨNH các trang vào app đầu tiên (tránh nháy màn hình lúc đăng nhập)
import { Login } from '@/pages/Login';
import { Dashboard } from '@/pages/Dashboard';

// Lazy phần còn lại
const Reports = lazy(() => import('@/pages/Reports').then(m => ({ default: m.Reports })));
const SampleFlow = lazy(() => import('@/pages/SampleFlow').then(m => ({ default: m.SampleFlow })));
// ...48 trang còn lại

<Suspense fallback={<div className="py-20"><LoadingState /></div>}>
  <Routes>...</Routes>
</Suspense>
```

> Các trang export **named** (`export function Reports`) nên phải `.then(m => ({default: m.X}))`.
> Muốn gọn hơn thì đổi sang `export default` — nhưng đó là refactor 58 file, cân nhắc.

**DoD** `ls -la dist/assets/*.js` → chunk lớn nhất < 400KB (hiện 1.185KB);
chunk vào app đầu < 250KB. Lighthouse "Total Blocking Time" giảm rõ.

#### R7.2 — Cache boto3 client · **0,5h**

```python
# app/services/storage_service.py
from functools import lru_cache

@lru_cache(maxsize=4)
def _client(endpoint: Optional[str] = None):
    """Client boto3 dùng lại.

    Trước đây tạo mới mỗi lần gọi — botocore phải nạp JSON service model (~50ms).
    Với avatar_url() gọi trong serializer, chi phí này nhân theo số dòng.
    boto3 client an toàn thread ✔ (session mới không an toàn, client thì có).
    """
    return boto3.client("s3", endpoint_url=endpoint or settings.minio_endpoint, ...)
```

**DoD** Đo `presigned_get_url` 100 lần: trước ~5s, sau <0,2s.

### PR #8 · R8 — Bảo mật nâng cao (F-07, F-08, F-17, IDOR)

#### R8.1 — Access token in-memory · **6h** · ⚠ rủi ro hồi quy cao

```ts
// lib/api.ts
let _accessToken: string | null = null;      // KHÔNG dùng localStorage nữa
export function getToken() { return _accessToken; }
export function setToken(t: string | null) { _accessToken = t; }
```

Hệ quả: **F5 là mất token**. Phải bootstrap bằng `/auth/refresh` (cookie HttpOnly còn):

```tsx
// AuthContext — khi khởi động
useEffect(() => {
  (async () => {
    try { await authApi.refresh(); await loadMe(); }   // cookie tự gửi
    catch { setUser(null); }
    finally { setLoading(false); }
  })();
}, []);
```

⚠ **Kiểm kỹ:** mở nhiều tab, F5 liên tục, refresh token rotation + reuse detection có
báo nhầm "reuse" khi 2 tab cùng refresh không. Đây là phần dễ gây lỗi nhất trong plan.

#### R8.2 — Bật Idempotency-Key · **3h**

```ts
// lib/api.ts — trong apiPost
export async function apiPost<T>(path: string, body?: unknown, query?) {
  return request<T>(path, {
    method: 'POST', body, query,
    headers: { 'Idempotency-Key': crypto.randomUUID() },
  });
}
```
⚠ Key phải **ổn định qua các lần retry của cùng một thao tác**. Sinh trong `apiPost`
nghĩa là retry ở tầng api.ts (sau 401) dùng lại đúng key ✔, nhưng người dùng bấm nút
2 lần thì ra 2 key khác → không chặn được double-click. Muốn chặn double-click phải
sinh key ở component và giữ trong ref.

#### R8.3 — Test IDOR tự động · **8h**

```python
# app/tests/security/test_idor.py ✨
"""Quét IDOR: user A không được đọc/sửa tài nguyên của user B.

294 endpoint, không thể rà tay. Test này liệt kê mọi route có tham số {id} và thử
truy cập chéo, kỳ vọng 403/404 (KHÔNG phải 200).
"""
import pytest
from app.main import app

ID_ROUTES = [
    r for r in app.routes
    if hasattr(r, "path") and "{" in r.path and "GET" in getattr(r, "methods", set())
]

@pytest.mark.parametrize("route", ID_ROUTES, ids=lambda r: r.path)
def test_cross_user_access_denied(client, route, user_a_token, fixture_owned_by_b):
    path = route.path.format(**fixture_owned_by_b.path_params)
    res = client.get(path, headers={"Authorization": f"Bearer {user_a_token}"})
    assert res.status_code in (403, 404), (
        f"IDOR: {route.path} trả {res.status_code} cho tài nguyên của người khác"
    )
```

#### R8.4 — Secret + quét bảo mật trong CI · **4h**

```yaml
# .github/workflows/security.yml ✨
name: Security
on: [push, pull_request]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2        # quét secret trong lịch sử git
      - run: pip install pip-audit && pip-audit -r lims-backend/requirements.txt
      - run: cd lims-frontend && npm ci && npm audit --audit-level=high
```

Đồng thời chuyển secret dev khỏi `docker-compose.yml` sang `${VAR:?}` + `.env`.

---

## Tuần 4 — Bền vững

| ID | Task | Giờ | Ghi chú |
|---|---|---:|---|
| **R9.1** | Queue nền (arq + Redis) cho xuất Excel/PDF + gửi mail | 12h | Gỡ tác vụ CPU/IO dài khỏi request; có retry + dead-letter |
| **R9.2** | PgBouncer (transaction pooling) | 4h | Cho phép tăng worker mà không đụng `max_connections` |
| **R9.3** | Prometheus + Grafana + Alertmanager | 8h | `/metrics` đã có ✔, chỉ thiếu scraper. Cảnh báo: đĩa >85%, 5xx >1%, p95 >2s, backup fail |
| **R9.4** | E2E Playwright — 10 luồng chính | 12h | Đăng nhập · nhận mẫu → báo giá → chuyển lab → trả KQ · duyệt tài liệu · CAPA · xuất báo cáo |
| **R9.5** | Chaos test | 6h | Giết Redis/MinIO/Postgres giữa lúc k6 chạy, kiểm hành vi suy giảm |
| **R9.6** | Job dọn dữ liệu | 3h | `auth_tokens` hết hạn, `access_stats` cũ (>90 ngày), attachment mồ côi |
| **R9.7** | Runbook + tài liệu DR | 4h | Ai gọi ai, khôi phục thế nào, RTO/RPO cam kết |

---

## Tổng hợp công sức

| Tuần | Nội dung | Giờ | Bắt buộc trước go-live |
|---|---|---:|:---:|
| 1 | R1–R4: chặn event loop, concurrency, bảo mật, vận hành | **26h** | ⛔ Có |
| 2 | R5–R6: frontend ổn định, database | **31h** | Không |
| 3 | R7–R8: hiệu năng, bảo mật nâng cao | **28h** | Không |
| 4 | R9: hạ tầng bền vững | **49h** | Không |
| | **Tổng** | **134h ≈ 17 ngày công** | |

**Nếu chỉ có 1 ngày:** R1.1 (4h) + R3.2 (1h) + R4.1 (4h). Ba việc này gỡ nút thắt lớn
nhất, bịt lỗ hổng auth, và bảo vệ dữ liệu — thứ duy nhất không sửa được sau khi mất.

---

## Rủi ro của chính kế hoạch này

| Task | Rủi ro | Giảm thiểu |
|---|---|---|
| R1.1 | Bỏ sót một `await` → lỗi runtime | `grep -rn "await " app/routers/` phải rỗng; test upload từng loại |
| R2.1 | 4 worker trên host 1–2 nhân → tranh CPU, chậm hơn | Đặt `UVICORN_WORKERS` theo `nproc` |
| R2.2 | Pool nhỏ quá → 503 sớm | Chạy k6 sau mỗi lần chỉnh, không đoán |
| R3.1 | Tin nhầm header → **kẻ tấn công giả IP để né rate limit** | Chỉ tin `X-Real-IP` khi nginx ghi đè và lims-api không mở cổng ra host |
| R5.4 | Đổi phân trang có thể làm hỏng bộ lọc/sort | Làm từng trang một, mỗi trang một commit |
| R6.1 | `CONCURRENTLY` bị ngắt → index INVALID | Kiểm `pg_index WHERE NOT indisvalid` sau khi chạy |
| R8.1 | Refresh rotation báo nhầm reuse khi nhiều tab | Test đa tab kỹ; cân nhắc hoãn nếu chưa chắc |
