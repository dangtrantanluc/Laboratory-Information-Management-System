# Kế hoạch cải thiện Backend — theo từng giai đoạn

Nguồn: [backend-production-audit.md](./backend-production-audit.md) · Ngày 2026-07-26 · commit `959a7bd`

---

## 0. Nguyên tắc xếp thứ tự — đọc trước khi làm

### 0.1 Ưu tiên theo **bằng chứng**, không theo cảm giác nghiêm trọng

Bản audit đầu tiên xếp `/dashboard` là điểm nghẽn số một với 1.549 ms. Đo lại kỹ
thì **11 ms** — nó đã có cache Redis TTL 60s từ trước. Con số 1.549 ms là **lần
gọi nguội**, gồm chi phí import lần đầu của 51 lazy import trong codebase.

Bài học đưa thẳng vào nguyên tắc: **mọi task hiệu năng phải kèm phép đo trước và
sau, ở trạng thái ấm, lặp ít nhất 3 lần.** Không có số thì không đưa vào kế hoạch.

### 0.2 Hệ thống hiện **chưa có dữ liệu vận hành**

| Bảng | Dòng |
|---|---:|
| `access_stats` | 17.076 |
| `audit_logs` | 1.874 |
| `test_parameters` | 614 |
| `form_templates` | 384 |
| **`samples`** | **10** |

Với 10 mẫu, **không phép đo hiệu năng nào về nghiệp vụ có ý nghĩa**. Điều này chia
kế hoạch làm hai loại rõ rệt:

- **Loại A — xác minh được ngay**: kiến trúc, bảo mật, vận hành, cấu hình
- **Loại B — chỉ xác minh được khi có dữ liệu**: N+1, COUNT, phân trang, index

Loại B **không bị bỏ**, nhưng phải đi kèm bước tạo dữ liệu thử trước. Sửa mù một
N+1 rồi tuyên bố "đã tối ưu" mà không đo được là tự lừa mình.

### 0.3 Ba chỉ số theo dõi

```bash
# scripts/backend-health-metrics.sh
```

| Chỉ số | Hôm nay | Mục tiêu 3 tháng | Mục tiêu 12 tháng |
|---|---:|---:|---:|
| Năng lực đồng thời (worker × threadpool) | **80** | 160 | 160 + PgBouncer |
| Truy vấn DB trong vòng lặp | **13** | ≤4 | 0 |
| Endpoint thiếu `response_model` | **281** | ≤200 | ≤80 |
| `db.commit()` trong service | **166** | ≤120 | ≤30 |

---

# GIAI ĐOẠN 0 — An toàn vận hành · **1 ngày** · làm ngay

> Không liên quan hiệu năng. Đây là những thứ đang **mở** trên internet.

## P0.1 — Đóng lỗ đăng nhập admin công khai · **1h** · 🔴

`acc.txt` trên repo GitHub công khai liệt kê 9 tài khoản và mật khẩu dùng chung.
Đã kiểm chứng: đăng nhập admin thành công bằng đúng thông tin đó.

```bash
# 1. Gỡ khỏi git, giữ file trên máy
git rm --cached acc.txt
echo "acc.txt" >> .gitignore
git commit -m "chore(security): gỡ acc.txt khỏi repo — chứa mật khẩu dùng được"

# 2. Đổi mật khẩu MỌI tài khoản demo trên production
limsc exec -T lims-api python - <<'PY'
from sqlalchemy import text
from app.core.security import hash_password
from app.db.database import SessionLocal
import secrets

db = SessionLocal()
rows = db.execute(text("SELECT id, email FROM users WHERE email LIKE '%@lims.local'")).all()
for uid, email in rows:
    pwd = secrets.token_urlsafe(16)
    db.execute(text("UPDATE users SET password_hash=:h, password_changed_at=NULL WHERE id=:i"),
               {"h": hash_password(pwd), "i": uid})
    print(f"  {email}  →  {pwd}")
db.commit()
PY
```

`password_changed_at=NULL` ép người dùng đổi mật khẩu ở lần đăng nhập đầu.

> **Lưu ý về lịch sử git**: mật khẩu vẫn nằm trong các commit cũ đã được clone và
> lập chỉ mục. Viết lại lịch sử **không** thu hồi được. Đổi mật khẩu là biện pháp
> đúng — đã làm ở bước 2.

**DoD**: `git ls-files acc.txt` rỗng · đăng nhập bằng mật khẩu cũ thất bại.

## P0.2 — Sửa lỗi tính RAM upload · **1h** · 🟠

[concurrency.py:13](../lims-backend/app/core/concurrency.py#L13) ghi:

```python
_upload_sem = threading.BoundedSemaphore(6)   # 6 × 20MB = 120MB, vừa mem_limit 1g
```

Semaphore là **per-process**. Với `UVICORN_WORKERS=4`, thực tế là **24 × 20 MB =
480 MB**, không phải 120 MB. Comment sai gấp 4 lần, và 480 MB cộng baseline
~750 MB đo được lúc tải cao là **vượt `mem_limit: 1g`**.

```python
# Semaphore là PER-PROCESS. Với UVICORN_WORKERS=4 thì trần thực tế là
# 4 × N × 20MB, không phải N × 20MB. Đặt 3 để 4×3×20 = 240MB, còn chỗ cho
# baseline ~750MB trong mem_limit 1g.
_upload_sem = threading.BoundedSemaphore(3)
```

**DoD**: tải 12 file 20 MB đồng thời · `docker stats` không vượt 900 MB.

## P0.3 — Dời cron khỏi giờ cao điểm · **30 phút** · 🟠

[scheduler.py:134-143](../lims-backend/app/scheduler.py#L134) — 8/9 job chạy
07:00–08:15, đúng giờ người dùng đăng nhập. CRON-1 và CRON-3 cùng **07:00**.

| Job | Hiện tại | Đổi thành |
|---|---|---|
| CRON-1 due-soon | 07:00 | **05:00** |
| CRON-3 salary-raise | 07:00 | **05:15** |
| CRON-4 contract-expiry | 07:15 | **05:30** |
| CRON-6 chem-expiry | 07:30 | **05:45** |
| CRON-5 calibration-due | 07:45 | **06:00** |
| CRON-7 capa-due | 08:00 | **06:15** |
| CRON-8 risk-review-due | 08:15 | **06:30** |

**DoD**: `limsc logs lims-api | grep APScheduler` hiện lịch mới.

## P0.4 — Nâng pool DB · **30 phút** · 🔴

Đo tải trước đây hỏng ở 60 VU với `8/12`. Quyết định này đã treo từ lâu.

```bash
# .env.prod
DB_POOL_SIZE=12
DB_MAX_OVERFLOW=28
```

4 × 40 = **160 kết nối** < `max_connections=200`. Threadpool tự lên 40/worker
theo công thức ở `main.py:86` → **160 chỗ đồng thời** thay vì 80.

**DoD**: `limsc logs lims-api | grep "Threadpool limiter"` báo `threads: 40` ·
`SELECT count(*) FROM pg_stat_activity` < 200 khi tải.

---

# GIAI ĐOẠN 1 — Đo được trước khi tối ưu · **3 ngày**

> Không sửa hiệu năng nào ở giai đoạn này. Chỉ dựng khả năng **nhìn thấy**.

## P1.1 — Bộ dữ liệu thử có quy mô thật · **1,5 ngày** · 🔴

Đây là **điều kiện tiên quyết của toàn bộ Giai đoạn 2**. Không có dữ liệu thì
không đo được N+1, không biết index nào thiếu, không xác nhận được bản sửa có tác
dụng.

**File**: `lims-backend/scripts/seed_perf_data.py` ✨

Sinh dữ liệu ở quy mô 3 năm vận hành dự kiến:

| Bảng | Số dòng | Căn cứ |
|---|---:|---|
| `test_requests` | 6.000 | ~2.000 phiếu/năm × 3 năm |
| `samples` | 30.000 | ~5 mẫu/phiếu |
| `sample_assignments` | 60.000 | ~2 chỉ tiêu/mẫu |
| `sample_results` | 60.000 | |
| `chemical_txns` | 20.000 | |
| `audit_logs` | 200.000 | append-only, không xoá |
| `access_stats` | 500.000 | trước khi CRON-9 dọn |

Yêu cầu bắt buộc của script:
- Chỉ chạy khi `ENVIRONMENT != production` — **chặn cứng**, không phải cảnh báo
- Dùng `bulk_insert_mappings`, không `db.add()` từng dòng
- Idempotent theo tiền tố mã (`PERF-`), chạy lại không nhân đôi
- Có `--purge` để dọn sạch dữ liệu thử

**DoD**: chạy trên DB thử · `samples` ≥ 30.000 · thời gian sinh < 5 phút.

## P1.2 — Kịch bản đo chuẩn · **0,5 ngày** · 🔴

**File**: `perf/endpoint-latency.sh` ✨

Đo **ở trạng thái ấm**, lặp 5 lần, lấy trung vị. Đây là phản ứng trực tiếp với
sai lầm đo nguội của bản audit đầu.

```bash
#!/usr/bin/env bash
# Đo độ trễ endpoint — LÀM ẤM trước, lặp 5 lần, lấy trung vị.
#
# Bản audit đầu báo /dashboard 1.549 ms vì đo lần gọi NGUỘI (gồm chi phí import
# lần đầu của 51 lazy import). Đo lại ở trạng thái ấm cho 11 ms. Sai lệch 140 lần.
set -euo pipefail
warm() { for _ in 1 2 3; do curl -s -o /dev/null "$1" -H "Authorization: Bearer $TOK"; done; }
median() { sort -n | awk '{a[NR]=$1} END{print (NR%2)?a[(NR+1)/2]:(a[NR/2]+a[NR/2+1])/2}'; }
for ep in "$@"; do
  warm "$BASE$ep"
  ms=$(for _ in $(seq 5); do
        curl -s -o /dev/null -w '%{time_total}\n' "$BASE$ep" -H "Authorization: Bearer $TOK"
      done | awk '{print $1*1000}' | median)
  printf "  %-46s %7.0f ms\n" "$ep" "$ms"
done
```

**DoD**: chạy 2 lần liên tiếp, chênh lệch < 15%.

## P1.3 — Grafana + cảnh báo · **1 ngày** · 🟠

`/metrics` Prometheus đã có ([main.py:172](../lims-backend/app/main.py#L172)) nhưng
**không có dashboard và không có cảnh báo**. Metrics không ai xem thì bằng không.

Bốn cảnh báo tối thiểu:

| Cảnh báo | Ngưỡng | Vì sao |
|---|---|---|
| p95 request | > 2 s trong 5 phút | Ngưỡng go-live đã định |
| Tỉ lệ lỗi 5xx | > 1% trong 5 phút | |
| Kết nối pool đang dùng | > 80% trần | Cảnh báo **trước** khi cạn |
| Cron job thất bại | bất kỳ | Job lỗi hiện chỉ nằm trong log |

**DoD**: tắt Postgres → cảnh báo nổ trong 5 phút.

---

# GIAI ĐOẠN 2 — Tối ưu có bằng chứng · **5 ngày**

> Mỗi task: **đo trước → sửa → đo sau**. Không cải thiện đo được thì **hoàn tác**.

## P2.1 — Sửa N+1 trong endpoint danh sách · **2 ngày** · 🟠

13 chỗ truy vấn trong vòng lặp (xác nhận bằng AST). Ba chỗ nằm trong endpoint
danh sách nên bị nhân theo `limit`:

| Vị trí | Hàm |
|---|---|
| [sample_service.py:214](../lims-backend/app/services/sample_service.py#L214) | `list_samples()` |
| [sample_service.py:488](../lims-backend/app/services/sample_service.py#L488) | `list_overdue()` |
| [sample_service.py:697](../lims-backend/app/services/sample_service.py#L697) | `on_time_report()` |

Ví dụ `list_samples()`:

```python
# TRƯỚC — 1 + N truy vấn
for s in rows:
    req = db.get(TestRequest, s.request_id)

# SAU — 2 truy vấn, bất kể N
req_ids = {s.request_id for s in rows if s.request_id}
reqs = {
    r.id: r
    for r in db.execute(select(TestRequest).where(TestRequest.id.in_(req_ids))).scalars()
}
for s in rows:
    req = reqs.get(s.request_id)
```

> `db.get()` tra identity map trước nên **nhiều dòng cùng `request_id` chỉ tốn một
> truy vấn**. N+1 chỉ tệ khi các dòng trỏ tới bản ghi khác nhau. Đây là lý do phải
> đo trên dữ liệu thật (P1.1) chứ không sửa mù.

**DoD**: trên 30.000 mẫu, `/samples?limit=100` giảm ≥ 40% · số truy vấn đếm bằng
`pg_stat_statements` giảm từ ~100 xuống ≤ 3 · nếu không đạt thì **revert**.

## P2.2 — Index theo truy vấn chậm thật · **1 ngày** · 🟠

`pg_stat_statements` đã bật sẵn trong `docker-compose.prod.yml`.

```sql
SELECT substring(query,1,90), calls, round(total_exec_time) ms, round(mean_exec_time,1) avg
FROM pg_stat_statements WHERE query NOT LIKE '%pg_stat%'
ORDER BY total_exec_time DESC LIMIT 20;
```

Chỉ thêm index cho truy vấn **thật sự xuất hiện trong top 20**. Hiện đã có 401
index / 188 FK — thêm mù sẽ làm chậm ghi mà không giúp đọc.

Bắt buộc dùng `CREATE INDEX CONCURRENTLY` trong `autocommit_block()` để không
khoá bảng.

**DoD**: mỗi index mới kèm `EXPLAIN ANALYZE` trước/sau trong mô tả migration.

## P2.3 — Cache danh mục ít đổi · **1 ngày** · 🟡

`report_common.cache_get/cache_set` đã có sẵn và hoạt động tốt (dashboard 201 →
11 ms). Mở rộng cho các danh mục gần như không đổi:

| Dữ liệu | TTL đề xuất | Vô hiệu hoá khi |
|---|---|---|
| Phòng ban | 300 s | CRUD phòng ban |
| Đơn vị đo | 3600 s | hiếm khi đổi |
| Danh mục chỉ tiêu (614 dòng) | 300 s | CRUD chỉ tiêu |

**Bắt buộc kèm chống stampede** — 160 người cùng vào lúc cache hết hạn sẽ tạo 160
lượt tính lại:

```python
# Chỉ MỘT request tính lại; số còn lại dùng bản cũ thêm 10 giây.
if not r.set(f"{key}:lock", "1", nx=True, ex=10):
    return stale_or_none(key)
```

**DoD**: đo 3 lần ấm giảm ≥ 50% · sửa một phòng ban thì cache mất trong 1 giây.

## P2.4 — Nén response · **0,5 ngày** · 🟡

**[THIẾU DỮ LIỆU]** — cần kiểm nginx trước:

```bash
curl -s -H "Accept-Encoding: gzip" -o /dev/null -D- \
  https://lims.dangtrantanluc.id.vn/api/v1/forms/templates?limit=100 | grep -i content-encoding
```

Có `gzip` thì **bỏ task này**. Không có thì thêm `GZipMiddleware(minimum_size=1024)`.

**DoD**: JSON 100 KB giảm ≥ 60% dung lượng truyền.

---

# GIAI ĐOẠN 3 — Độ bền · **6 ngày**

## P3.1 — Hàng đợi nền cho export và mail · **4 ngày** · 🟠

Hiện **không có** Celery/RQ/Dramatiq/arq, và **0 chỗ** dùng `BackgroundTasks`.
Xuất Excel/PDF chạy trong request với semaphore `_export_sem = 2` (thực tế 8 với
4 worker). Cloudflare timeout 100 giây — vượt là mất kết quả dù server vẫn tính.

Dùng **arq** (Redis-based, async, nhẹ — Redis đã có sẵn nên không thêm hạ tầng):

```
POST /reports/export  →  đẩy job vào arq  →  trả 202 + job_id
GET  /reports/export/{job_id}  →  trạng thái | presigned URL khi xong
```

Mail cũng vào hàng đợi: hiện `email_service` gọi đồng bộ, timeout 10 giây, lỗi thì
**mất luôn** — không có thử lại.

**DoD**: export 50.000 dòng trả 202 trong < 500 ms · giết worker giữa chừng, job
được nhận lại · gửi mail khi SMTP tắt → job retry 3 lần rồi vào dead-letter.

## P3.2 — Retry + circuit breaker cho phụ thuộc ngoài · **1,5 ngày** · 🟡

Đo được: **0 file** dùng `tenacity`/retry, **0 file** có circuit breaker.

| Phụ thuộc | Hiện tại | Thêm |
|---|---|---|
| SMTP | timeout 10 s, lỗi thì bỏ | 3 lần thử, backoff 1/2/4 s |
| MinIO | boto3 mặc định | `max_attempts=3` trong `Config` |
| Redis | lỗi → fail-open | Giữ nguyên — fail-open là **đúng** cho rate limit |

Circuit breaker chỉ cho MinIO: hỏng thì mở mạch 30 giây thay vì để 160 request
cùng chờ timeout.

**DoD**: chặn cổng MinIO → request lỗi nhanh < 1 s thay vì treo.

## P3.3 — Rà 13 chỗ `except: pass` · **0,5 ngày** · 🟡

`except Exception` 59 chỗ · `except: ... pass` **13 chỗ**. Phần lớn có comment
giải thích hợp lý, nhưng 13 chỗ `pass` là nơi lỗi biến mất hoàn toàn.

Mỗi chỗ phải rơi vào một trong hai: thêm `logger.warning` kèm ngữ cảnh, **hoặc**
comment giải thích vì sao im lặng là đúng.

**DoD**: 0 chỗ `pass` không có log lẫn comment · thêm test kiến trúc chặn tái diễn.

---

# GIAI ĐOẠN 4 — Kiến trúc · **25 ngày** · 6–12 tháng

> Đây là các thay đổi lớn. Không bắt đầu khi Giai đoạn 1–3 chưa xong.

## P4.1 — `response_model` cho 281 endpoint · **20 ngày** · 🔴

Đã có test chặn nợ tăng thêm. Nay trả nợ cũ theo từng router, và sinh type
frontend từ OpenAPI thay cho 1.964 dòng viết tay.

Chi tiết đầy đủ: [MAINTAINABILITY_PLAN.md §T4](../MAINTAINABILITY_PLAN.md).

**Cạm bẫy**: FastAPI **lọc bỏ** trường không khai trong `response_model` — thiếu
một trường mà frontend đang dùng thì nó biến mất **im lặng**. Mỗi router bắt buộc
kèm test `set(body) == set(Schema.model_fields)`.

## P4.2 — Unit of Work · **25 ngày** · 🟠 · Rủi ro **cao**

Gỡ 166 `db.commit()` khỏi service. Điều kiện tiên quyết — lưới test — **đã có**
sau Giai đoạn 2 của kế hoạch bảo trì.

Chi tiết: [MAINTAINABILITY_PLAN.md §T3](../MAINTAINABILITY_PLAN.md).

## P4.3 — PgBouncer · **5 ngày** · 🟠

**Điều kiện kích hoạt**: trước khi scale ngang, hoặc khi vượt 200 người dùng.

Hiện threadpool bị buộc bằng pool DB (`main.py:86`), nên **không thể tăng năng lực
xử lý mà không tăng kết nối DB** — và kết nối DB bị `max_connections=200` chặn.
3 replica × 4 worker × 40 = 480 > 200.

PgBouncer (transaction pooling) tách hai con số đó ra.

**DoD**: 3 replica cùng chạy · `pg_stat_activity` < 100 · k6 300 VU không có lỗi
QueuePool.

---

## Tổng hợp

| GĐ | Nội dung | Ngày | Thời điểm | Chặn GĐ sau |
|---|---|---:|---|:--:|
| 0 | An toàn vận hành | **1** | Ngay | — |
| 1 | Đo được trước khi tối ưu | **3** | Tuần này | ✅ chặn GĐ2 |
| 2 | Tối ưu có bằng chứng | **5** | Tháng 1 | — |
| 3 | Độ bền | **6** | Tháng 2–3 | — |
| 4 | Kiến trúc | **50** | Tháng 6–12 | — |
| | **Tổng** | **65** | | |

## Nếu chỉ làm được 5 ngày

1. **Giai đoạn 0 trọn vẹn** (1 ngày) — `acc.txt`, RAM upload, cron, pool DB
2. **P1.1 + P1.2** (2 ngày) — dữ liệu thử + kịch bản đo
3. **P1.3** (1 ngày) — Grafana + 4 cảnh báo
4. **P2.4** (0,5 ngày) — kiểm gzip

Bốn việc này biến hệ thống từ "không biết gì đang xảy ra" thành "thấy được vấn đề
trước khi người dùng phàn nàn". Mọi tối ưu sau đó mới có cơ sở.

## Khả năng chịu tải

| Mốc | Đồng thời | Trạng thái ổn định | Giới hạn |
|---|---:|---:|---|
| **Hiện tại** | 80 | ~200 người | Threadpool = pool DB |
| **Sau GĐ0** (P0.4) | 160 | ~500 người | Threadpool = pool DB |
| **Sau GĐ3** (hàng đợi) | 160 | ~800 người | Export không còn chiếm thread |
| **Sau P4.3** (PgBouncer) | tuỳ replica | **2.000+** | Postgres |

## Rủi ro của chính kế hoạch

| Rủi ro | Dấu hiệu sớm | Giảm thiểu |
|---|---|---|
| Tối ưu mù vì bỏ qua GĐ1 | Task GĐ2 không có số trước/sau | **Điều kiện cứng**: không vào GĐ2 khi chưa xong P1.1 |
| Seed dữ liệu chạy nhầm production | — | Script **chặn cứng** khi `ENVIRONMENT=production` |
| P4.2 làm hỏng dữ liệu | Test tính nguyên tử đỏ | Không bắt đầu khi lưới test chưa đủ |
| `response_model` làm mất trường im lặng | FE thiếu dữ liệu sau deploy | Test đối chiếu bắt buộc mỗi router |
| Kế hoạch chết sau 3 tháng | 3 chỉ số §0.3 đứng yên 2 sprint | Đưa vào Definition of Done của sprint |
