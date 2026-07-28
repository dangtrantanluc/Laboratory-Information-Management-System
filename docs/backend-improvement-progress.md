# Tiến độ cải thiện Backend — Giai đoạn 0 → 3

Kế hoạch: [backend-improvement-plan.md](./backend-improvement-plan.md) · Ngày 2026-07-26

> **Nguyên tắc áp dụng xuyên suốt**: đo trước khi sửa, và **task nào đo ra không cần
> thì bỏ**, không viết thêm code cho đủ kế hoạch. Bốn task đã bị loại theo cách đó.

---

## Kết quả đo được

| Endpoint | Trước | Sau | |
|---|---:|---:|---|
| `/forms/templates?limit=100` | 129 ms | **39 ms** | **−70%** |
| `/samples?limit=100` | 52 ms | **31 ms** | **−40%** |
| `/dashboard` | 11 ms | 11 ms | đã tối ưu sẵn |

| Cấu hình | Trước | Sau |
|---|---:|---:|
| Năng lực đồng thời | 80 | **160** |
| Trần RAM upload (4 worker) | 480 MB | **240 MB** |
| Cron chạy trong giờ cao điểm | 7 job | **0** |

---

## ĐÃ LÀM

### Giai đoạn 0 — cấu hình vận hành · commit `de7a480`

**RAM upload tính sai 4 lần.** [concurrency.py](../lims-backend/app/core/concurrency.py)
ghi *"6 upload × 20MB = 120MB, vừa mem_limit 1g"*, nhưng semaphore là **per-process**.
Với `UVICORN_WORKERS=4` trần thực tế là **480 MB**, cộng baseline ~750 MB đo được
lúc tải cao là **vượt `mem_limit: 1g`**. Hạ 6 → 3.

Test cũ khoá cứng con số 6 nên đỏ. Viết lại để khẳng định theo **phép tính**
(`worker × slot × max_upload_size ≤ 300MB`) thay vì con số — đổi `max_upload_size`
hay số worker thì test tự bắt.

**8/9 cron chạy đúng giờ đăng nhập.** 07:00–08:15, riêng CRON-1 và CRON-3 trùng đúng
07:00. Dời 7 job về 05:00–06:30.

**Pool DB quyết định năng lực toàn hệ thống.** [main.py:86](../lims-backend/app/main.py#L86)
căn threadpool AnyIO bằng **đúng** `pool_size + max_overflow`. Nâng 8+12 → 12+28
cho `4 × 40 = 160` chỗ đồng thời; 160 < `max_connections=200`. Cập nhật đồng bộ ở
`.env.prod.example`, comment postgres và `DEPLOY_LINUX.md` để ba nơi không lệch.

### Giai đoạn 1 — công cụ đo · commit `7e5883b`

[`perf/endpoint-latency.sh`](../perf/endpoint-latency.sh) — làm ấm 3 lần, đo 5 lần,
lấy **trung vị**.

Đây là phản ứng trực tiếp với sai lầm của bản audit đầu: nó báo `/dashboard`
**1.549 ms** và kết luận đó là điểm nghẽn số một. Đo ở trạng thái ấm cho **11 ms**
— sai lệch **140 lần**. Lần gọi đầu gồm chi phí import của 51 lazy import, cache
Redis chưa có, trang DB chưa nằm trong bộ nhớ.

### Giai đoạn 2 — N+1, đo được bằng dữ liệu thật · `7e5883b`, `2c6c552`

**`/forms/templates` — N+1 đầu tiên chứng minh được bằng số.** Sau khi nạp 384 biểu
mẫu VILAS, độ trễ tăng tuyến tính `26 → 71 → 129 ms` theo `limit` `10 → 50 → 100`,
tức **~1,15 ms mỗi dòng** — chữ ký của N+1.

Nguyên nhân: `_serialize_template()` gọi `_files_of()` cho **từng dòng**, và
`list_templates` dùng **list comprehension** nên máy quét AST của tôi bỏ sót — nó
chỉ tìm câu lệnh `for`.

Sửa bằng `_files_of_many()`. Đây đúng kiểu mẫu **đã có sẵn** trong chính file đó:
`_batch_submission_refs()` đã làm vậy cho submission từ trước nhưng bỏ sót template.

**`/samples` — 3 truy vấn mỗi dòng.** `_assignment_stats` (2 truy vấn đếm) +
`db.get(TestRequest)`. Ở `limit=100` là ~300 truy vấn.

Điểm mấu chốt: **truy vấn tổng hợp không được identity map của SQLAlchemy phục vụ**,
nên `_assignment_stats` lặp lại là thật sự xuống database mỗi lần — khác `db.get`
vốn được cache khi id trùng. Thay bằng một `GROUP BY` + một `IN(...)`.

### Giai đoạn 3 — `except: pass` · commit `2c6c552`

13/14 chỗ **đã có chú thích giải thích từ trước**. Chỗ còn lại
([metrics.py:71](../lims-backend/app/core/metrics.py#L71)) nay ghi rõ vì sao im lặng
là đúng: hàm chạy mỗi lần Prometheus scrape 15 giây, log ở đó sẽ ngập file log.

---

## ĐÃ BỎ — và vì sao

> Đây là phần quan trọng nhất của tài liệu. Bốn task trong kế hoạch **không được
> làm**, vì đo đạc cho thấy chúng không cần thiết. Viết thêm code cho đủ kế hoạch
> là làm phình hệ thống mà không đổi được gì.

### ✂ P2.4 — Nén response

**Đã có sẵn.** [nginx.conf:52-54](../lims-frontend/nginx.conf#L52):

```nginx
gzip on;
gzip_types text/css application/javascript application/json image/svg+xml;
gzip_min_length 1024;
```

Có cả `application/json`. Thêm `GZipMiddleware` vào FastAPI sẽ **nén hai lần** —
tốn CPU mà không giảm thêm byte nào.

### ✂ P3.2 — Retry cho MinIO

**Đã có sẵn.** [storage_service.py](../lims-backend/app/services/storage_service.py):

```python
retries={"max_attempts": 3, "mode": "standard"}
```

### ✂ P3.2 — Retry cho SMTP

**Cố ý không làm.** Retry trong request sẽ giữ thread tới `3 × 10s = 30 giây` cho
một lần gửi mail — làm **xấu đi** chính vấn đề đồng thời mà kế hoạch đang cố sửa.

Retry mail chỉ đúng khi có hàng đợi nền, mà hàng đợi thì đã quyết định chưa cần
(xem dưới). Hiện `email_service` có timeout 10 giây và `logger.error` khi lỗi —
mail mất thì có dấu vết, chỉ là không tự gửi lại.

### ✂ P3.1 — Hàng đợi nền (arq)

**Chưa cần.** Đo export thật:

| Endpoint | Thời gian |
|---|---:|
| `/forms/submissions/export` | 46 ms |
| `/documents/access-stats/export` | 22 ms |

Và đã có hai lớp bảo vệ sẵn: `EXPORT_MAX_ROWS = 10000` (vượt → `EXPORT_TOO_LARGE`)
và `_export_sem = 2`.

Thêm arq nghĩa là: một dependency mới, một container worker mới, một API mới để
hỏi trạng thái job, và frontend phải xử lý luồng bất đồng bộ. Đó là chi phí thật
cho một vấn đề **chưa xảy ra**.

**Điều kiện kích hoạt** — làm khi *một trong hai* điều sau đúng:
- Có endpoint export vượt **10 giây** trên dữ liệu thật
- Cloudflare bắt đầu trả 524 (timeout 100 giây) cho export

### ✂ P1.1 — Seed 30.000 mẫu

**Không làm, có điều kiện.** Kế hoạch coi đây là tiền đề bắt buộc của Giai đoạn 2.
Thực tế việc nạp **384 biểu mẫu VILAS thật** đã đủ để phát hiện và chứng minh N+1
bằng số — mục đích của seed đã đạt bằng dữ liệu thật.

Viết một script sinh dữ liệu ~200 dòng để chứng minh thứ đã chứng minh được là
**nhiều code hơn cả bản sửa**.

**Điều kiện kích hoạt**: khi cần đo tải ở quy mô 40+ người dùng đồng thời, hoặc khi
`samples` vượt 1.000 dòng mà muốn kiểm index trước.

### ✂ P1.3 — Prometheus + Grafana

**Không làm, đề xuất cách khác.** `/metrics` Prometheus **đã có**
([main.py:172](../lims-backend/app/main.py#L172)). Thứ thiếu là dashboard và cảnh báo.

Nhưng thêm Prometheus + Grafana là **2 container, ~500 MB RAM** trên máy mà
`lims-api` đã dùng 750 MB lúc tải cao. Đó là cái giá thật.

**Đề xuất rẻ hơn**: trỏ một Prometheus **bên ngoài** (hoặc Grafana Cloud gói free)
vào `/metrics` qua Cloudflare Tunnel. Không tốn RAM của máy chủ, và cảnh báo vẫn
chạy khi chính máy đó chết — điều mà Prometheus chạy cùng máy **không làm được**.

---

## Còn lại, chưa làm được vì thiếu dữ liệu

### P2.2 — Index theo truy vấn chậm thật

`pg_stat_statements` **chỉ được nạp trong `docker-compose.prod.yml`**
(`shared_preload_libraries`), không có trong compose dev. Nên không đo được trên
máy phát triển.

**Việc cần làm trên production**:

```sql
SELECT round(mean_exec_time::numeric,1) AS ms, calls,
       substring(regexp_replace(query,'\s+',' ','g'), 1, 90)
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat%' AND calls > 20
ORDER BY total_exec_time DESC LIMIT 20;
```

Chỉ thêm index cho truy vấn **thật sự** trong top 20. Hiện đã có 401 index / 188 FK
— thêm mù sẽ làm chậm ghi mà không giúp đọc.

### P2.3 — Cache danh mục

Sau khi sửa N+1, endpoint danh mục đo được **28–39 ms**. Chưa đủ chậm để đánh đổi
lấy độ phức tạp của cache (phải xử lý vô hiệu hoá khi CRUD, và chống stampede).

**Điều kiện kích hoạt**: một endpoint danh mục vượt **200 ms** ở trạng thái ấm.

### 11 N+1 còn lại

Đã sửa 2/13 — đúng hai chỗ **đo được**. 11 chỗ còn lại nằm trong cron job và luồng
ít người dùng, chưa có dữ liệu để chứng minh mức độ.

---

## Việc bạn cần làm trên production

```bash
cd ~/workspace/lims
git pull
limsc up -d --build           # áp pool 12+28 và bản sửa N+1

# xác nhận năng lực đồng thời đã tăng
limsc logs lims-api | grep "Threadpool limiter"      # phải báo threads: 40

# đo lại trên chính production
BASE=https://lims.dangtrantanluc.id.vn/api/v1 \
  EMAIL=admin@lims.dangtrantanluc.id.vn PASSWORD=<mật-khẩu> \
  ./perf/endpoint-latency.sh > perf/prod-$(date +%F).txt
```

Rồi chạy truy vấn `pg_stat_statements` ở phần P2.2 và gửi kết quả — đó là dữ liệu
duy nhất còn thiếu để quyết định có cần thêm index không.
