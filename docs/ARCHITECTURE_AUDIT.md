# ARCHITECTURE AUDIT — LIMS Backend

> Ngày audit: 2026-08-07 · Phạm vi: `lims-backend/` (38.306 LOC Python), hạ tầng triển khai
> (`docker-compose*.yml`, `lims-frontend/nginx.conf`, `.github/workflows/`).
> Phương pháp: đọc mã nguồn trực tiếp (không dựa vào tài liệu có sẵn), truy vết
> request → router → service → ORM → DB, đối chiếu với cấu hình triển khai thật.
>
> **Lưu ý:** repo đã có `ARCHITECTURE_AUDIT.md` ở thư mục gốc (bản audit trước, các mã
> F-01…F-05). Tài liệu này là bản audit ĐỘC LẬP, đánh mã `A-xx`, và có ghi rõ chỗ nào
> kết luận cũ **đã được sửa**, chỗ nào **còn nguyên**, chỗ nào **sửa nửa vời**.

---

## 1. Kiến trúc hiện tại

### 1.1 Stack thực tế

| Lớp | Công nghệ | Vị trí |
|---|---|---|
| Ngôn ngữ / runtime | Python 3.11 | `lims-backend/Dockerfile:1` |
| Framework | FastAPI 0.115.6 + Uvicorn 0.34.0 (4 worker process) | `app/main.py`, `Dockerfile:43-46` |
| Entrypoint ứng dụng | `app.main:app` + `lifespan()` | `app/main.py:66-132` |
| Entrypoint container | `entrypoint.sh` (chờ Postgres → advisory-lock → alembic) | `lims-backend/entrypoint.sh` |
| API layer | 39 router module, **296 endpoint** | `app/routers/*.py` |
| Business logic | 68 service module (đồng bộ, sync) | `app/services/*.py` |
| Data access | **KHÔNG có repository layer** — service gọi thẳng SQLAlchemy Session | toàn bộ `app/services/` |
| ORM | SQLAlchemy 2.0.36 (sync, psycopg2) | `app/db/database.py` |
| Database | PostgreSQL 15 — **68 bảng**, 32 migration Alembic | `alembic/versions/` |
| Cache / coordination | Redis 7 (jti denylist, lockout, rate limit, RBAC cache, idempotency, scheduler leader-lock, cron per-job lock) | `app/core/redis_client.py` |
| Object storage | MinIO (S3-compatible qua boto3) | `app/services/storage_service.py` |
| Background jobs | APScheduler **in-process** (9 cron job) — KHÔNG có worker/queue riêng | `app/scheduler.py` |
| Email | SMTP đồng bộ (smtplib) | `app/services/email_service.py` |
| Push | Web Push VAPID (pywebpush) qua ThreadPoolExecutor riêng | `app/services/push_service.py` |
| Reverse proxy | nginx 1.27 (trong container `lims-web`, phục vụ cả SPA lẫn proxy API) | `lims-frontend/nginx.conf` |
| Ingress | Cloudflare Tunnel (`cloudflared`) — TLS kết thúc ở biên Cloudflare | `docker-compose.cloudflare.yml` |
| Observability | Prometheus client (`/metrics`), JSON log ra stdout | `app/core/metrics.py`, `app/core/logging_config.py` |
| CI/CD | GitHub Actions: backend-ci, frontend-ci, security (gitleaks + pip-audit + npm audit), architecture | `.github/workflows/` |

### 1.2 Sơ đồ kiến trúc THỰC TẾ

```
                    Internet (HTTPS)
                          │
                 ┌────────▼────────┐
                 │   Cloudflare    │  TLS terminate, WAF/DDoS ở biên
                 └────────┬────────┘
                          │ tunnel (outbound-only)
                 ┌────────▼────────┐
                 │  cloudflared    │  container, không mở cổng
                 └────────┬────────┘
                          │ http://lims-web:80
        ┌─────────────────▼──────────────────┐
        │  lims-web  (nginx + SPA React)     │
        │  /            → SPA index.html     │
        │  /api/        → lims-api:8060      │
        │  /lims-attachments/ → minio:9000   │   ← đường tải file presigned
        └────────┬───────────────────┬───────┘
                 │                   │
   ┌─────────────▼──────────┐        │
   │  lims-api (uvicorn ×4) │        │
   │  ┌──────────────────┐  │        │
   │  │ Middleware stack │  │        │
   │  │ CORS             │  │        │
   │  │ SecurityHeaders  │  │        │
   │  │ Idempotency      │  │        │
   │  │ AccessStat       │  │        │
   │  │ CorrelationId    │  │        │
   │  │ Metrics          │  │        │
   │  │ RequestLimits    │  │        │
   │  └────────┬─────────┘  │        │
   │           ▼            │        │
   │  Router (296 ep)       │        │
   │   └─ Depends(get_current_user / require_roles / require_permission)
   │           ▼            │        │
   │  Service (68 module)   │        │
   │           ▼            │        │
   │  SQLAlchemy Session (get_db, 1 session/request)
   │           │            │        │
   │  APScheduler (in-process, 9 cron, leader-lock Redis)
   │  ThreadPool webpush (4)│        │
   └──┬────────┬─────────┬──┘        │
      │        │         │           │
 ┌────▼───┐ ┌──▼────┐ ┌──▼──────────▼─┐
 │Postgres│ │ Redis │ │     MinIO      │
 │  15    │ │   7   │ │                │
 └────────┘ └───────┘ └────────────────┘
      ▲
      │ (thủ công, chưa tự động hoá)
 ┌────┴─────────┐
 │  Backup ???  │  ← xem A-09
 └──────────────┘
```

**Khác biệt so với sơ đồ chuẩn trong đề bài:**

1. **Không có repository/data-access layer.** Service import model và gọi
   `db.execute(select(...))` trực tiếp. Không có abstraction giữa business logic và ORM.
2. **Không có message queue / worker process riêng.** "Background processing" =
   APScheduler chạy trong chính process API + một ThreadPoolExecutor cho Web Push.
   Không có Celery/RQ/Arq, không có retry queue, không có dead-letter.
3. **Reverse proxy nằm CHUNG container với frontend.** `lims-web` vừa là web server SPA
   vừa là API gateway vừa là proxy cho MinIO. Đây là một điểm hợp nhất trách nhiệm bất
   thường (xem A-03).
4. **MinIO được proxy same-origin.** Presigned URL trỏ về `https://<domain>/lims-attachments/...`
   chứ không phải endpoint MinIO riêng — để chữ ký s3v4 khớp thì Host phải giữ nguyên.

---

## 2. Trách nhiệm từng thành phần

| Thành phần | Trách nhiệm | Đánh giá |
|---|---|---|
| `app/main.py` | Wiring: logging, middleware stack, exception handler, 39 router, lifespan | ✅ Sạch, có comment giải thích thứ tự middleware (`main.py:134-138`) — thứ tự này là chỗ rất dễ sai, việc ghi rõ là đúng |
| `app/config.py` | Pydantic Settings, **chốt an toàn từ chối khởi động ở production nếu còn secret mặc định** (`config.py:144-170`) | ✅ Thiết kế tốt. Đây là fail-fast đúng chỗ |
| `app/core/deps.py` | `get_current_user`, `require_roles`, `require_permission` | ✅ Có kiểm jti denylist + `password_changed_at` vs `iat` (`deps.py:78-81`) — thu hồi token sau đổi mật khẩu |
| `app/core/rbac.py` | Tra bảng `roles_permissions`, cache Redis 5 phút | ✅ RBAC dữ liệu hoá, không hardcode |
| `app/core/security.py` | bcrypt cost 12, JWT HS256, refresh opaque + SHA-256, jti denylist | ✅ Đúng chuẩn |
| `app/middleware/*` | 5 middleware: request limits, correlation id, access stat, idempotency, security headers | ✅ Đầy đủ hơn mức trung bình cho dự án cùng quy mô |
| `app/services/*` | Business logic + data access + serialize + audit + notify (4 trách nhiệm trong 1 lớp) | ⚠️ Xem A-01 |
| `app/scheduler.py` | 9 cron, leader-lock Redis, run-history vào Redis cho `/health/ready` | ✅ Có giám sát, có misfire_grace_time |
| `app/models/*` | 68 bảng, CHECK constraint, UNIQUE, trigger append-only (định nghĩa ở migration) | ⚠️ Có lệch model↔migration (xem DATABASE_AUDIT D-08) |

---

## 3. Quan hệ phụ thuộc

### 3.1 Hướng phụ thuộc (đúng chiều)

```
routers  ──→  services  ──→  models  ──→  db.database (Base, engine)
   │             │
   └──→ core ────┘   (deps, rbac, security, exceptions, responses, concurrency)
```

Không phát hiện **circular import ở cấp module**. Tuy nhiên có **nhiều import cục bộ trong
hàm để né vòng import** — dấu hiệu coupling ngầm:

| Vị trí | Import cục bộ | Lý do |
|---|---|---|
| `app/services/attachment_service.py:66` | `from app.models.user import User` | comment ghi rõ "local import tránh vòng import" |
| `app/services/hr_common.py:232,241,250,257` | `from app.models.user import User` ×4 | như trên |
| `app/routers/hr_profiles.py:253,306` | `from app.services.research import competence_service`, `hr_common` | router ↔ service chéo |
| `app/services/auth_service.py:198` | `from app.services import access_stat_service` | trong thân hàm `login()` |
| `app/scheduler.py:153` | `importlib.import_module(...)` động | né vòng import lúc load module |

→ **A-02 (KIẾN TRÚC, MEDIUM):** 20+ import cục bộ để né vòng import. Không phải lỗi chạy,
nhưng là bằng chứng cụm `services/` đã coupling đủ chặt để đồ thị import có chu trình ở
cấp package. Mỗi lần thêm service mới, rủi ro vòng import tăng.

### 3.2 Phụ thuộc ra ngoài (runtime)

| Phụ thuộc | Bắt buộc? | Hành vi khi hỏng |
|---|---|---|
| **PostgreSQL** | Có | 500 toàn bộ. Đúng — không thể làm gì khác |
| **Redis** | **Có, ngầm** | ⚠️ **A-04** — `get_current_user` → `is_jti_denied()` → `redis.exists()` ném exception → 500 cho **mọi request đã xác thực**. Rate limit / RBAC cache / idempotency đều fail-open, nhưng auth **fail-closed**. Redis chết = API chết |
| **MinIO** | Không (một phần) | Upload/download hỏng, phần còn lại chạy. `/health/ready` báo degraded. `lims-api` healthcheck cố ý dùng `/health` (liveness) để không restart-loop — quyết định đúng (`docker-compose.prod.yml:153-157`) |
| **SMTP** | Không | `smtp_host` rỗng → chế độ dev, ghi link ra log. Ở production `SMTP_HOST` là biến bắt buộc (`docker-compose.prod.yml:211`) |
| **Push service trình duyệt** | Không | best-effort, thread nền, timeout 5s, drop khi hàng đợi > 500 |

---

## 4. Luồng dữ liệu

### 4.1 Ghi (ví dụ: tạo giao dịch xuất hoá chất)

```
POST /api/v1/chemicals/lots/{lot_id}/transactions
  → RequestLimits (bỏ qua: không phải multipart)
  → Metrics (start timer)
  → CorrelationId (sinh/đọc X-Correlation-Id, đặt ContextVar)
  → AccessStat (bỏ qua: không phải GET)
  → Idempotency (kích hoạt NẾU client gửi Idempotency-Key → SET NX Redis)
  → SecurityHeaders
  → CORS
  → router chemical_lots.create_transaction
      Depends(get_current_user) → JWT verify → jti denylist (Redis) → SELECT users
      Depends(get_db) → SessionLocal()
      → chemical_txn_service.create_transaction
          cc.assert_can_transact(db, user)        ← RBAC
          cc.get_lot_or_404(lot_id, lock=True)    ← SELECT ... FOR UPDATE
          _do_out(): validate → convert unit (Decimal) → check tồn
                   → INSERT chemical_transactions
                   → UPDATE chemical_lots.qty_base
                   → _reorder_check() trong SAVEPOINT → notification
                   → audit_service.log_action() (INSERT audit_logs, chưa commit)
          db.commit()                             ← 1 transaction duy nhất
      → strip_price_fields(result, can_cost)      ← field-level RBAC ở response
```

**Đánh giá:** đây là luồng ghi được thiết kế **tốt** — row lock, Decimal, savepoint cho
phần best-effort, audit trong cùng transaction, strip field theo quyền. Dùng làm chuẩn
tham chiếu cho các module khác.

### 4.2 Đọc + tải file

```
GET /api/v1/attachments/{id}
  → get_current_user
  → attachment_service.get_download()
      SELECT attachments WHERE id=? AND deleted_at IS NULL
      _check_owner_read_permission(user, owner_type)   ← ⚠️ CHỈ chặn role 'office' cho 3 owner_type
      storage_service.presigned_get_url(...)           ← ký URL TTL 900s
      audit_service.log_action(ATTACHMENT_DOWNLOAD)
  → trả download_url cho client
  → browser GET https://<domain>/lims-attachments/... → nginx → minio
```

→ **Đây là lỗ hổng phân quyền nghiêm trọng nhất của hệ thống.** Chi tiết: SECURITY_AUDIT
S-01/S-02.

### 4.3 Ghi nền (page_view)

```
GET /api/v1/samples  (whitelist)
  → AccessStatMiddleware.dispatch (sau response)
      asyncio.create_task(_record_page_view)
        → run_in_threadpool(_record_sync)
            SessionLocal() riêng → INSERT access_stats → commit → close
  → task giữ strong-ref trong _background_tasks, drain lúc shutdown
```

✅ Thiết kế đúng: không chặn event loop bằng psycopg2 sync, có drain lúc tắt.
⚠️ Nhưng: mỗi GET whitelist = **1 connection DB thêm** ngoài pool của request → xem A-06.

---

## 5. Luồng request (chi tiết middleware)

Thứ tự thực thi **ngoài → trong** (Starlette: `add_middleware` gọi sau cùng = lớp ngoài cùng):

```
CORS → SecurityHeaders → Idempotency → AccessStat → CorrelationId → Metrics → RequestLimits → route
```

`main.py:134-138` ghi rõ ý đồ và nó đúng: CORS ngoài cùng nên **mọi** response — kể cả
409 do Idempotency sinh và response lỗi — đều có header CORS.

**Vấn đề:** 5/7 middleware kế thừa `BaseHTTPMiddleware` của Starlette. `BaseHTTPMiddleware`
buộc response phải đi qua `body_iterator`, phá vỡ streaming và thêm một task-group mỗi
request. Với response file/export lớn (`report_export_service` trả bytes), toàn bộ thân
response bị giữ trong RAM ít nhất 2 lần (`IdempotencyMiddleware.dispatch:92-97` cộng dồn
`body += chunk` **không dừng lại khi vượt ngưỡng** — chỉ đặt cờ `too_large=True` rồi vẫn
đọc tiếp toàn bộ).

→ **A-05 (HIỆU NĂNG, MEDIUM):** `IdempotencyMiddleware` đọc trọn thân response vào RAM
ngay cả khi đã biết là quá lớn. Chỉ kích hoạt khi client gửi `Idempotency-Key`, nhưng khi
đó một request export 50MB sẽ ngốn 50MB RAM/worker mà không cần thiết.
Vị trí: `app/middleware/idempotency.py:92-98`.

---

## 6. Luồng xác thực

```
1. POST /auth/login (rate_limit IP 300/60s)
     _check_lockout(email, ip)            → Redis TTL
     check_rate("login_identity", email|ip, 10/300s)
     SELECT users WHERE email = lower(email)
     verify_password (bcrypt cost 12; hash "mồi" nếu email không tồn tại → chống timing)
     status disabled → 403 / pending → 403 (chỉ SAU khi mật khẩu đúng — không lộ trạng thái)
     _issue_tokens: JWT HS256 (sub, role, dept, is_dept_lead, jti, iat, exp)
                  + refresh opaque 48 byte, DB lưu SHA-256
     audit AUTH_LOGIN_SUCCESS + access_stats login
     → access_token trong body, refresh_token trong cookie
       HttpOnly + Secure(production) + SameSite=Strict + Path=/api/v1/auth

2. Mỗi request: Authorization: Bearer <jwt>
     decode (verify chữ ký + exp)
     jti ∈ denylist? → 401
     SELECT users (status, password_changed_at)
     iat < password_changed_at → 401
     is_dept_lead xác thực LẠI từ DB (không tin claim)

3. POST /auth/refresh
     SELECT refresh_tokens WHERE token_hash = ? FOR UPDATE   ← tuần tự hoá refresh song song
     revoked_at != NULL → REUSE DETECTED → revoke toàn chuỗi của user + 401
     rotation: revoke cũ, cấp mới (rotated_from = id cũ)

4. POST /auth/logout
     revoke refresh (1 hoặc all) + deny_jti(jti, exp) → cắt phiên ngay
```

**Đánh giá: luồng xác thực là phần mạnh nhất của hệ thống.** Có đủ: refresh rotation,
reuse detection, row lock chống race, denylist jti, thu hồi theo `password_changed_at`,
chống user enumeration bằng cả thông điệp lẫn timing, lockout theo (email, IP).

**Điểm yếu còn lại:** xem SECURITY_AUDIT S-08 (lockout theo IP → credential stuffing phân
tán), S-05 (Redis là SPOF của auth).

---

## 7. Luồng xử lý nền

### 7.1 APScheduler (9 job)

| Job | Giờ (UTC) | Service |
|---|---|---|
| data-cleanup | 03:00 | `cleanup_cron_service.run_cleanup` |
| sample-overdue | 00:30 | `sample_cron_service.run_overdue` |
| sample-due-soon | 05:00 | `sample_cron_service.run_due_soon` |
| hr-salary-raise | 05:15 | `hr_cron_service.run_salary_raise_due` |
| hr-contract-expiry | 05:30 | `hr_cron_service.run_contract_expiry` |
| chem-expiry | 05:45 | `chemical_cron_service.run_chem_expiry` |
| equipment-calibration-due | 06:00 | `equipment_cron_service.run_calibration_due` |
| capa-due | 06:15 | `nc_cron_service.run_capa_due` |
| risk-review-due | 06:30 | `risk_cron_service.run_risk_review_due` |

Cơ chế chống chạy trùng **3 lớp**: `SCHEDULER_ENABLED` → leader-lock Redis (SET NX,
TTL 90s, heartbeat 30s bằng Lua compare-and-extend) → per-job Redis lock trong service.

⚠️ **A-07 (ĐỘ TIN CẬY, MEDIUM):** `_acquire_leader_lock()` **fail-open** — Redis lỗi thì
trả `True` (`scheduler.py:66-73`). Với `UVICORN_WORKERS=4`, mỗi worker process chạy
`lifespan` riêng → nếu Redis không sẵn sàng lúc khởi động, **cả 4 worker cùng đăng ký 9
cron**. Lớp phòng thủ cuối (per-job lock) cũng cần Redis. Kịch bản: Redis khởi động chậm
hơn API → 4 scheduler × 9 job. Với job gửi thông báo/mail, đây là 4× thông báo trùng.

⚠️ **A-08 (ĐỘ TIN CẬY, MEDIUM):** Không có **retry / backoff / dead-letter** cho cron.
`_run_tracked` bắt mọi exception, ghi `status=failed` vào Redis rồi thôi (`scheduler.py:100-112`).
Job thất bại → mất hẳn cửa sổ ngày đó; chỉ phát hiện được nếu ai đó đọc `/health/ready`
hoặc metric `scheduler_job_last_success`. Với hệ ISO/IEC 17025 mà cron là nguồn nhắc hạn
hiệu chuẩn / hạn CAPA, bỏ lỡ một ngày là mất bằng chứng tuân thủ.

### 7.2 Web Push

`ThreadPoolExecutor(max_workers=4)` riêng, session DB riêng, timeout 5s/lần gọi,
trần 500 task in-flight, drain lúc shutdown. ✅ Thiết kế đúng — tách hẳn khỏi transaction
của caller (caller thường đang giữ `with_for_update`).

---

## 8. Tích hợp bên ngoài

| Hệ thống | Chiều | Xác thực | Timeout | Retry |
|---|---|---|---|---|
| MinIO / S3 | outbound | access/secret key | connect 3s, read 10s | 3 lần (botocore standard) ✅ |
| SMTP | outbound | user/password (App Password) | `smtp_timeout_seconds=10` | ❌ Không |
| Web Push (FCM/Mozilla/Apple) | outbound | VAPID | 5s | ❌ Không (drop, xoá sub khi 404/410) |
| Cloudflare Tunnel | inbound | tunnel token | — | cloudflared tự quản |
| Redis | outbound | password (prod) | socket 2s, connect 2s ✅ | — |

⚠️ **A-10 (BẢO MẬT, MEDIUM):** Endpoint Web Push **do client cung cấp** và server POST
tới đó (`app/schemas/push.py:11` chỉ kiểm `min_length=1, max_length=2048`; không kiểm
scheme/host). Đây là **SSRF mù có xác thực**. Chi tiết: SECURITY_AUDIT S-07.

---

## 9. Điểm hỏng đơn lẻ (Single Points of Failure)

| # | SPOF | Bán kính ảnh hưởng | Có dự phòng? |
|---|---|---|---|
| 1 | **Redis** | Toàn bộ API 500 (auth fail-closed) | ❌ Không. 1 container, không sentinel/cluster |
| 2 | **PostgreSQL** | Toàn bộ | ❌ 1 instance, không replica, **không backup tự động** |
| 3 | **lims-web (nginx)** | Toàn bộ (vừa SPA vừa API gateway vừa proxy MinIO) | ❌ 1 container |
| 4 | **cloudflared** | Toàn bộ đường vào | ❌ 1 replica (Cloudflare khuyến nghị ≥2 cho HA) |
| 5 | **MinIO** | Mọi file đính kèm | ❌ 1 node, không erasure coding |
| 6 | **Máy chủ vật lý** | Tất cả — mọi service nằm trên 1 host, 1 docker network | ❌ |
| 7 | **Leader replica của scheduler** | 9 cron nhắc hạn ISO17025 | ⚠️ Lock hết hạn sau 90s thì replica khác giành — nhưng chỉ khi có replica khác |

→ **A-09 (VẬN HÀNH, HIGH):** Toàn hệ thống là **một host, một instance mỗi service, không
backup tự động**. `lims-backend/docs/DISASTER_RECOVERY.md` mô tả quy trình backup/restore
rất đúng, nhưng **không có gì trong repo thực thi nó**: không có service backup trong
`docker-compose.prod.yml`, không có cron/systemd unit, không có bằng chứng đã restore thử.
Tài liệu ≠ backup.

---

## 10. Rủi ro kiến trúc

### A-01 · Service layer gánh 4 trách nhiệm (MEDIUM)

Mỗi service module vừa là business logic, vừa là data access, vừa là serializer, vừa gọi
audit + notification. Hệ quả đo được:

- `document_service.py` 773 dòng, `document_version_service.py` 768, `sample_service.py` 755,
  `hr_service.py` 690, `form_service.py` 678, `dashboard_service.py` 619.
- **166 lời gọi `db.commit()` nằm rải trong service** (`app/tests/conftest.py:15` ghi nhận
  con số này) → biên transaction do service tự quyết định, router không kiểm soát được.
  Muốn gộp 2 thao tác vào 1 transaction là phải sửa service.
- Test phải dựng Postgres thật + `join_transaction_mode="create_savepoint"` để dọn sạch
  sau khi app đã commit (`conftest.py:11-19`). Rào cản này chính là lý do "0/41 router
  từng có test" như conftest tự ghi nhận.

**Không phải lỗi**, nhưng là nợ kiến trúc quyết định trần khả năng test và trần tốc độ
thêm tính năng.

### A-03 · nginx gộp 3 vai trò (MEDIUM)

`lims-web` phục vụ SPA + proxy API + proxy MinIO. Hệ quả cụ thể, không phải lý thuyết:

- **Không có `location /health`** trong `nginx.conf` → `GET https://<domain>/health` rơi
  vào `try_files ... /index.html` và trả **200 kèm HTML của SPA**.
  `DEPLOY_LINUX.md:292-293` và checklist go-live dòng 457 dùng `curl -fsS .../health` và
  `.../health/ready` để "xác minh backend sống". **Hai lệnh này luôn thành công kể cả khi
  `lims-api` đã chết.** → xem PRODUCTION_READINESS mục Observability.
- Đổi cấu hình proxy API buộc phải build lại image frontend.

### A-06 · Áp lực connection pool từ ghi nền (LOW-MEDIUM)

`AccessStatMiddleware` mở `SessionLocal()` **riêng** cho mỗi GET whitelist, ngoài session
của request. Cấu hình production: 4 worker × (pool 12 + overflow 28) = 160 connection,
`max_connections=200`. Threadpool AnyIO được căn đúng bằng 40/worker (`main.py:85-86`) —
tính toán này chỉ tính session của request, **chưa tính session của middleware nền**.
Ở đỉnh tải, số connection thực tế có thể vượt 160.

### A-11 · Không có chiến lược mở rộng ngang (LOW)

`upload_slot`/`export_slot` là `threading.BoundedSemaphore` **per-process**
(`app/core/concurrency.py:12-21` — comment đã thừa nhận). Trần thực tế = 4 × 3 upload và
4 × 2 export, không phải 3 và 2. Nếu scale lên nhiều host, các trần này mất hoàn toàn ý
nghĩa (cần Redis semaphore).

---

## 11. Tổng hợp mã phát hiện kiến trúc

| ID | Mức | Vấn đề | Vị trí |
|---|---|---|---|
| A-01 | 🟡 MEDIUM | Service gánh 4 trách nhiệm; 166 `db.commit()` rải rác | `app/services/*` |
| A-02 | 🟡 MEDIUM | 20+ import cục bộ né vòng import | `attachment_service.py:66`, `hr_common.py:232+`… |
| A-03 | 🟡 MEDIUM | nginx gộp SPA + API GW + MinIO proxy; thiếu `location /health` | `lims-frontend/nginx.conf` |
| A-04 | 🟠 HIGH | Redis là SPOF của xác thực (fail-closed) | `app/core/security.py:95`, `deps.py:59` |
| A-05 | 🟡 MEDIUM | Idempotency đọc trọn body kể cả khi quá ngưỡng | `app/middleware/idempotency.py:92-98` |
| A-06 | 🔵 LOW | Session nền ngoài tính toán pool | `app/middleware/access_stat.py:79` |
| A-07 | 🟡 MEDIUM | Leader-lock scheduler fail-open → 4 worker cùng chạy cron khi Redis down | `app/scheduler.py:66-73` |
| A-08 | 🟡 MEDIUM | Cron không retry/backoff/dead-letter | `app/scheduler.py:100-112` |
| A-09 | 🟠 HIGH | Không có backup tự động; DR chỉ là tài liệu | `docker-compose.prod.yml`, `docs/DISASTER_RECOVERY.md` |
| A-10 | 🟡 MEDIUM | SSRF mù qua endpoint Web Push | `app/schemas/push.py:11` |
| A-11 | 🔵 LOW | Semaphore per-process, không mở rộng ngang được | `app/core/concurrency.py:18-21` |

---

## 12. Điều audit này XÁC NHẬN là đã làm tốt

Để không tạo ấn tượng sai: nhiều thứ ở đây tốt hơn mặt bằng chung.

- Chốt an toàn secret lúc khởi động (`config.py:144-170`) — từ chối chạy production với
  giá trị mặc định. Rất ít dự án cùng quy mô có thứ này.
- `audit_logs` **append-only bằng trigger Postgres** (`alembic/versions/..._m7_platform.py:251-265`),
  `calibration_records` immutable, `capa` khoá sau khi đóng.
- Refresh token rotation + reuse detection + row lock.
- Advisory lock cho migration (`entrypoint.sh:39-55`) — chống race khi rolling deploy.
- Redis AOF `appendonly yes` + `maxmemory-policy noeviction` với lý do được ghi rõ: LRU sẽ
  xoá chính jti denylist (`docker-compose.prod.yml:71-83`).
- Postgres/Redis/MinIO **không publish cổng ra host** ở profile production.
- Test kiến trúc tự động quét 296 route để bắt endpoint quên xác thực
  (`app/tests/security/test_idor_routes.py`).
- CI có gitleaks + pip-audit + npm audit + migration dry-run + coverage gate 45%.
