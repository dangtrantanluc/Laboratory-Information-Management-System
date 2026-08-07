# PRODUCTION READINESS — LIMS Backend

> Ngày đánh giá: **2026-08-07** · Nhánh: `main` @ `3df1e6e`
> Phạm vi: backend (38.306 LOC, 296 endpoint, 68 bảng) + hạ tầng triển khai.

---

## 0. Kết luận

> ## ⚠️ **CONDITIONALLY READY — 72/140**
>
> Hệ thống **không có lỗ hổng CRITICAL** và có nền tảng kỹ thuật tốt hơn mặt bằng chung
> đáng kể (trigger append-only, refresh rotation + reuse detection, chốt chặn secret lúc
> khởi động, 250 index có chủ đích, CI 4 workflow).
>
> Nhưng có **7 vấn đề mức HIGH** phải xử lý trước khi mở ra Internet (S-01…S-05, D-11, B-01).
> Ba trong số đó (`/attachments`, `/quotations`, backup) khai thác/xảy ra được **ngay trong
> ngày đầu vận hành** và ảnh hưởng trực tiếp tới nghĩa vụ ISO/IEC 17025.
>
> **Sau khi hoàn thành nhóm P0 (ước lượng 3–4 ngày công), hệ thống đạt trạng thái READY.**

---

## 1. Bảng trạng thái theo hạng mục (bắt buộc)

| Area | Status | Severity | Finding | Action |
|---|---|---|---|---|
| **Authentication** | ✅ | - | JWT HS256 + jti denylist Redis + refresh rotation + reuse detection (`with_for_update`) + thu hồi token khi đổi mật khẩu (`deps.py:78-81`) + chống enumeration bằng hash mồi. Không tìm thấy đường bypass trên 296 endpoint | Giữ nguyên. Thêm MFA cho `admin` (P2) |
| **Authentication — brute force** | ⚠️ | MEDIUM | Lockout khoá theo (email, **IP**) → 100 IP × 5 lần = 500 lần thử/tài khoản không chạm ngưỡng (`redis_client.py:34-39`). Chính sách mật khẩu 8 ký tự, 1 chữ + 1 số | Thêm bộ đếm thứ hai theo email toàn cục (30/giờ) với hành vi mềm; nâng mật khẩu lên 12 ký tự + chặn danh sách lộ |
| **Authentication — sẵn sàng** | ❌ | HIGH | Redis chết → `is_jti_denied()` ném exception không bắt → **500 cho 100% request đã xác thực** (`security.py:95`, `deps.py:59`). Mọi thành phần khác dùng Redis đều fail-open có comment; riêng auth fail-closed không có comment → là thiếu sót | Bắt exception, quyết định có ý thức: 503 + `Retry-After`, hoặc fail-open + log SECURITY. Thêm cảnh báo Redis memory |
| **Authorization — function level** | ⚠️ | MEDIUM | 3 cơ chế song song (`require_permission` tra bảng / `require_roles` hardcode / kiểm thủ công trong service). Không có tài liệu module nào dùng cơ chế nào; không có test bao phủ ma trận `roles_permissions` | Chuẩn hoá về `require_permission` ở router; service chỉ kiểm phạm vi đối tượng |
| **Authorization — object level** | ❌ | **HIGH** | `GET /attachments/{id}` cấp presigned URL cho **bất kỳ** attachment nào; luật duy nhất là "cấm `office` với 3 owner_type M1" (`attachment_service.py:22-33`). Bỏ qua toàn bộ luật của 20 owner_type: mức `restricted` tài liệu, phạm vi phòng, hiển thị bản draft, quyền đọc năng lực HR | Bảng định tuyến quyền theo `owner_type`, **deny-by-default** |
| **Authorization — ghi** | ❌ | **HIGH** | `POST /attachments` nhận `owner_type`+`owner_id` từ client, không kiểm quyền, không kiểm owner tồn tại, không kiểm trạng thái khoá → chèn tệp vào bản tài liệu/minh chứng **đã phê duyệt** (`attachment_service.py:106-163`). Chính codebase đã ghi nhận nguy cơ ở `form_file_service.py:7-10` mà không vá | Áp cùng bảng định tuyến, hoặc **gỡ hẳn endpoint generic** |
| **Authorization — lộ dữ liệu** | ❌ | **HIGH** | `/quotations` (list/get/export.xlsx) chỉ có `get_current_user`; `get_quotation` **không nhận tham số `user`** (`quotation_service.py:153`). Mọi tài khoản đọc được PII khách hàng + bảng giá. Trong khi `/customers` — cùng dữ liệu — có `require_roles` chặt | Thêm `require_roles` cho 3 endpoint đọc + rate limit cho export |
| **Authorization — mẫu denylist** | ⚠️ | MEDIUM | `hr_service.get_profile` chỉ chặn `role == "staff"` → `reception`/`qms`/`lab_manager` đọc được hồ sơ mọi người (`hr_service.py:187`). `deps.py:71` chỉ chặn `status == "disabled"`. Vai trò/trạng thái mới **mặc định được phép** | Đảo thành allowlist ở cả hai chỗ |
| **Business logic** | ❌ | **HIGH** | `PATCH /intakes/{id}` nhận `status` trong body (`schemas/sample_flow.py:38`) và ghi bằng `setattr` mù (`sample_flow_service.py:236-238`) → **bỏ qua state machine `INTAKE_NEXT` và bỏ qua kiểm vai trò `_privileged`** mà `POST /intakes/{id}/status` áp dụng (`:514-526`). Nhảy thẳng `received → completed`, bỏ qua báo giá và thanh toán | Loại `status` khỏi `UpdateIntakeRequest`; thay `setattr` mù bằng danh sách field tường minh (như `update_quotation` đã làm đúng) |
| **Database — schema** | ✅ | - | 68 bảng, PK/FK/UNIQUE/CHECK đầy đủ, **250 index** có chủ đích kèm lý do, trigger append-only cho `audit_logs`/`calibration_records`/`capa`, NUMERIC + Decimal cho tiền, 5 bảng dedup cho cron | Giữ nguyên |
| **Database — hiệu năng** | ⚠️ | MEDIUM | N+1 ở ~20 endpoint list (170 `db.get` per-row trong 23 module). Tổng hợp báo cáo kéo toàn bộ dòng về RAM (`unified_report_service.py:81`) với cache key do client điều khiển → bypass được. Không có `statement_timeout` | Nạp trước theo lô (mẫu đã có ở `list_samples`); chuyển sang `GROUP BY date_trunc`; đặt `statement_timeout=30s` |
| **Database — đồng thời** | ⚠️ | MEDIUM | Sinh mã `COUNT()+1`: 6/8 chỗ có retry `IntegrityError`, nhưng `create_intake` và `create_quotation` **không có** → 2 người tạo phiếu cùng lúc, một người nhận **500**. Xoá cứng `quotations` làm `COUNT` giảm → trùng mã vĩnh viễn | Thêm retry ngắn hạn; chuyển sang SEQUENCE/`code_counters` dài hạn |
| **Database — backup/DR** | ❌ | **HIGH** | **Đính chính 2026-08-07:** script backup **đã có sẵn và viết tốt** (`ops/backup/lims-backup.sh` — kiểm toàn vẹn bằng `pg_restore --list`, kiểm kích thước, giải đúng tên volume qua `docker compose config`), cùng `ops/cron/lims-backup.cron` và hướng dẫn cài ở `DEPLOY_LINUX.md:329-341`. **Nhưng chưa được cài trên host đang chạy production**: `/etc/cron.d/lims-backup`, `/usr/local/bin/lims-backup`, `/var/backups/lims`, `/var/log/lims-backup.log` đều không tồn tại; `crontab -l` rỗng. → **Hiện không có bản backup nào. RPO = ∞, RTO = ∞** | P0-5: sửa 4 chỗ (`LIMS_DIR`, `LIMS_BACKUP_REMOTE`, tên tệp lệch, thiếu `-f` compose) rồi cài — **~30 phút**, không phải xây mới. Cộng mã hoá off-site + **diễn tập restore có biên bản** |
| **Concurrency** | ✅ | - | Mọi đường có tiền/tồn kho/trạng thái quan trọng đều `SELECT ... FOR UPDATE` (13 vị trí): tồn kho hoá chất, refresh token, duyệt tài liệu, đóng CAPA/rủi ro, đăng ký PTN. Có test race đăng ký | Giữ nguyên. Bổ sung khoá cho các PATCH thường (D-12) |
| **Concurrency — cron** | ⚠️ | MEDIUM | 3 lớp chống chạy trùng, nhưng leader-lock **fail-open** khi Redis lỗi (`scheduler.py:66-73`) → 4 worker cùng đăng ký 9 job. Không có retry/backoff/dead-letter: job lỗi mất hẳn cửa sổ ngày đó | Fail-closed + tách container chuyên chạy cron (`--workers 1`); thêm cảnh báo khi `scheduler_job_last_success == 0` |
| **API design** | ⚠️ | MEDIUM | Format response thống nhất ✅, status code đúng ✅, validation Pydantic tốt ✅. Nhưng: 0/296 endpoint có `response_model` (OpenAPI không có schema response, không có lưới chắn chống lộ field); rate limit phủ 8/296; idempotency opt-in chưa endpoint nào bắt buộc | `response_model` cho endpoint chạm dữ liệu nhạy cảm trước; rate limit cho export; bắt buộc `Idempotency-Key` cho POST tạo phiếu/giao dịch |
| **Performance** | ⚠️ | MEDIUM | Đủ tốt cho quy mô hiện tại (~40 người dùng). Ở 100.000 bản ghi: điểm nghẽn theo thứ tự là báo cáo tổng hợp trong RAM → N+1 → `audit_logs` chưa partition. 2 đường xuất nặng nhất (`result-report.pdf`, `quotations/export.xlsx`) **không có cả rate limit lẫn `export_slot()`** dù semaphore đã tồn tại | Áp `export_slot()` + rate limit; SQL aggregate; kế hoạch partition `audit_logs` theo năm |
| **Resource limits** | ⚠️ | MEDIUM | Có: `mem_limit`/`cpus` cho container ✅, `max_upload_size_bytes` + middleware chặn sớm ✅, semaphore upload/export ✅, pool DB căn với threadpool AnyIO ✅, log rotation ✅. Thiếu: **timeout tầng ứng dụng**, `statement_timeout`, trần cho `page` | Thêm 3 mục còn thiếu |
| **Observability — health** | ❌ | MEDIUM | nginx **không có `location /health`** → `curl https://<domain>/health` trả **200 kèm HTML của SPA**. `DEPLOY_LINUX.md:292-293` và checklist go-live dòng 457 dùng đúng lệnh đó để "xác minh backend + DB + Redis + MinIO". **Kiểm tra luôn xanh kể cả khi backend đã chết** | Thêm `location = /health` và `= /health/ready` vào nginx; sửa checklist thành kiểm tra nội dung (`grep -q '"status":"ok"'`) |
| **Observability — metrics/log** | ⚠️ | MEDIUM | Có `/metrics` Prometheus (request count/latency theo route template — tránh cardinality ✅, scheduler gauge ✅), JSON log có `correlationId` qua ContextVar ✅. **Đính chính 2026-08-07:** cấu hình giám sát **đã có sẵn** — `ops/monitoring/prometheus.yml` (scrape lims-api + node-exporter + postgres-exporter) và `ops/monitoring/alerts.yml` (5 alert: `ApiDown`, `HighErrorRate`, `SlowResponses`, `DiskAlmostFull`, `BackupMissing`). Nhưng: **không container giám sát nào đang chạy** (`docker ps -a` không có prometheus/alertmanager/exporter) và **không có compose file nào dựng chúng**; thêm nữa alert `BackupMissing` dựa trên metric `lims_backup_last_success_timestamp_seconds` mà **không thành phần nào phát ra** → alert quan trọng nhất sẽ không bao giờ kêu | P1-3: viết `docker-compose.monitoring.yml` + thêm 2 dòng ghi metric vào cuối script backup — **~0,75 ngày**, không phải viết cảnh báo từ đầu |
| **Logging & audit trail** | ✅ | - | `audit_logs` append-only bằng trigger; mọi CUD gọi `log_action` **trong cùng transaction**; `_sanitize` lọc 10 khoá nhạy cảm; không log password/token; log JSON một dòng → không log-injection được. Ghi đủ: login/logout/login-fail/token-reuse/CRUD/duyệt/đổi vai trò/đổi mật khẩu/tải tệp | Giữ nguyên. Cân nhắc gửi bản sao ra kho WORM (P2) |
| **Docker** | ⚠️ | MEDIUM | Backend chạy **non-root** ✅, healthcheck có ✅ + lý do chọn `/health` thay `/health/ready` được ghi rõ ✅, `--timeout-graceful-shutdown 30` ✅, không publish cổng DB/Redis/MinIO ✅, log rotation ✅, resource limit ✅. Thiếu: `no-new-privileges`, `cap_drop: ALL`, `read_only`; **`minio/minio:latest`** (tag động, không tái lập); không multi-stage cho backend (image chứa cả build tool) | Thêm 3 tuỳ chọn hardening; ghim tag MinIO |
| **Deployment** | ⚠️ | LOW | **Xác minh trên máy chủ 2026-08-07:** overlay Cloudflare **đang hoạt động** — `lims-web` chỉ có `80/tcp`, không publish cổng nào ra host; mạng `lims_default` chỉ gồm 6 container LIMS + `cloudflared`. Không cần IP public, không mở firewall, TLS ở biên ✅. Migration qua service one-shot + advisory lock ✅. Rủi ro còn lại là **vận hành**: `ops/RUNBOOK.md` có **0** tham chiếu tới `docker-compose.cloudflare.yml` và 15 lệnh (gồm thủ tục rollback dòng 149) chạy thiếu overlay → dựng lại `lims-web` **có cổng 3060** và **mất `cloudflared`** (hệ thống offline), đồng thời mở đường giả mạo `CF-Connecting-IP` | Sửa `ops/RUNBOOK.md` dùng alias đủ 2 file (alias đã có ở `DEPLOY_LINUX.md:360`); gỡ `ports: "3060:80"` khỏi `docker-compose.prod.yml`. **KHÔNG** dùng `set_real_ip_from` với dải IP công khai Cloudflare — sai với topology tunnel, sẽ làm hỏng nhật ký IP |
| **Secrets** | ❌ | **HIGH** | `.gitignore` chỉ có `.env.prod` (khớp chính xác). `git check-ignore` xác nhận **`.env.prod.bak.20260729` KHÔNG bị ignore** — đang untracked trong cây làm việc, chứa `JWT_SECRET`, `CLOUDFLARE_TUNNEL_TOKEN`, mọi mật khẩu hạ tầng **còn hiệu lực**. Một `git add -A` là lộ toàn bộ. Repo **đã công khai** (`.gitleaksignore` ghi lại một sự cố y hệt với khoá VAPID) | `.gitignore`: `.env.*` + `!*.example`; pre-commit hook gitleaks **cục bộ**; di chuyển file `.bak` ra ngoài cây |
| **Secrets — chốt chặn** | ✅ | - | `config.py:144-170` **từ chối khởi động** ở production/staging nếu còn `JWT_SECRET` mặc định, `JWT_SECRET < 32` ký tự, `minioadmin`, `ChangeMe@123`, hoặc `lims:lims@`. Compose dùng `${VAR:?...}` cho mọi secret — thiếu biến là container không chạy | Giữ nguyên. Đây là thiết kế đúng |
| **Dependencies** | ⚠️ | LOW | Toàn bộ được ghim phiên bản ✅; CI có `pip-audit` + `npm audit` + gitleaks ✅ (nhưng `|| true` — không chặn merge, có lý do được ghi). `python-jose 3.3.0` và `passlib 1.7.4` đều **ngừng bảo trì**. CVE-2024-33663/33664 của jose **không khai thác được** ở đây (`algorithms=["HS256"]` cố định, không dùng JWE) | Lên kế hoạch chuyển `pyjwt` + `argon2-cffi`. Không gấp |
| **Testing** | ⚠️ | MEDIUM | 29 file test, coverage gate **45%**. Có test quét tự động 296 route bắt endpoint quên xác thực ✅, test race đăng ký ✅, test RBAC HR ✅, test sanitize tên file ✅, test hợp đồng response ✅. Nhưng **`test_idor_routes.py` tự ghi rõ**: chỉ kiểm "có xác thực hay không", phần "user A không đọc được của user B" *"là việc của test tích hợp"* — **và test đó chưa tồn tại**. Chính là lý do S-01/S-02/S-03 không bị bắt | Viết test tích hợp uỷ quyền cấp đối tượng cho `/attachments`, `/quotations`, tài liệu `restricted` |
| **Data privacy** | ⚠️ | MEDIUM | Field-level strip đã có cho lương/hợp đồng/PII (`hr_common.strip_profile`) và giá hoá chất (`strip_price_fields`) ✅. Nhưng PII khách hàng lộ qua `/quotations` (HIGH), hồ sơ HR lộ một phần qua denylist role. Không có mã hoá at-rest (volume Docker trần), không có chính sách lưu trữ/xoá dữ liệu cá nhân | Vá `/quotations`; mã hoá đĩa ở host; định nghĩa chính sách retention |
| **Input validation** | ✅ | - | Pydantic khắp nơi, `Query(ge=, le=, max_length=)` nhất quán, `Email` type tự lowercase, `extra="forbid"` cho mọi schema nhạy cảm. **0 SQL injection** (không có chuỗi SQL động), **0 path traversal** (sanitize allowlist ký tự + test riêng), **0 deserialization không an toàn** | Giữ nguyên |
| **Error handling** | ✅ | - | 4 handler toàn cục, format thống nhất `{success, error:{code, message, details, correlationId}}`, stack trace **chỉ log ở BE**, `/docs` + `/redoc` tắt ở production. `except Exception` rộng có ở 40+ chỗ nhưng **hầu hết đều có `logger.warning` + comment giải thích** (best-effort có chủ đích), không phải nuốt lỗi im lặng | Giữ nguyên |
| **File upload** | ⚠️ | MEDIUM | Có: allowlist MIME, giới hạn kích thước 2 lớp, sanitize tên file bằng allowlist ký tự, semaphore chống OOM, chặn stored-XSS bằng `Content-Disposition: attachment` cưỡng bức. **Thiếu: kiểm magic bytes** — chỉ tin `Content-Type` client khai (`attachment_common.py:44-50`); không antivirus; `location /lims-attachments/` trong nginx **không có `nosniff`** | Kiểm chữ ký tệp; thêm `nosniff` cho location MinIO |
| **CORS / CSRF / headers** | ✅ | - | CORS allowlist tường minh từ env, không wildcard. CSRF **không cần** và không thiếu: Bearer token trong header + cookie `SameSite=Strict` + `Path=/api/v1/auth`. Security headers: nosniff, frame DENY, CSP `default-src 'none'`, Referrer-Policy, HSTS chỉ ở production | Giữ nguyên |
| **SSRF** | ⚠️ | MEDIUM | Endpoint Web Push do client cung cấp, server tự POST tới (`push.py:11` chỉ kiểm độ dài) → SSRF **mù** có xác thực vào mạng nội bộ | Allowlist host push service; chặn IP private/link-local |

---

## 2. Audit nghiệp vụ (Business Logic)

### 2.1 Vòng đời các thực thể chính

| Thực thể | Vòng đời | State machine? | Enforce? |
|---|---|---|---|
| **Sample Intake** (phiếu nhận mẫu) | `received → quoted → quote_accepted → paid → dispatched → completed` / `cancelled` | ✅ `INTAKE_NEXT` | ⚠️ **Bypass được** — xem B-01 |
| **Document Version** | `draft → review → approved → obsolete` (+ `review → draft`) | ✅ `VERSION_STATE_WHITELIST` (`document_common.py:35-41`) | ✅ Qua `change_version_status` tập trung; approve tự động `obsolete` bản cũ |
| **Quotation** (báo giá) | `draft → sent → accepted/rejected/expired`; `rejected/expired → draft` | ✅ `QUOTATION_NEXT` | ✅ Chỉ qua `change_status`; `update_quotation` khoá khi `accepted` (`quotation_service.py:310`) |
| **Nonconformity / CAPA** | `open → ... → closed` | ✅ | ✅ + **trigger DB** chặn UPDATE khi `closed` |
| **Risk** | `open → ... → closed` | ✅ | ✅ `with_for_update` |
| **Sample** | trạng thái mẫu M1 | ✅ `VALID_SAMPLE_STATUS` | ✅ |
| **Form Submission** | `submitted → approved/rejected` | ✅ | ✅ + khoá tệp sau khi duyệt (`_check_submission_writable`) — **nhưng bypass qua `POST /attachments`** (S-02) |
| **User** | `pending → active` / `disabled` | ⚠️ Ngầm | ✅ Chỉ admin đổi; đăng ký luôn vào `pending` |
| **Calibration Record** | append-only | — | ✅ **Trigger DB** chặn UPDATE + DELETE |

### 2.2 Phát hiện nghiệp vụ

#### B-01 · 🟠 HIGH — Hai đường đổi trạng thái phiếu nhận mẫu, chỉ một đường có kiểm

**Vị trí:** `app/routers/sample_flow.py:79-93` (PATCH) vs `:95-108` (POST status);
`app/services/sample_flow_service.py:228-245` vs `:514-540`; `app/schemas/sample_flow.py:38`

| | `POST /intakes/{id}/status` | `PATCH /intakes/{id}` |
|---|---|---|
| Quyền | `require_permission("intake","manage")` + **`_privileged(user)`** (admin/leader/qms/reception) | `require_permission("intake","manage")` |
| State machine | ✅ `INTAKE_NEXT.get(it.status)` → 422 nếu nhảy bậc | ❌ **Không kiểm** |
| Ghi | có kiểm soát | `for k, v in changes.items(): setattr(it, k, v)` |
| Audit | `INTAKE_STATUS_CHANGE` | `INTAKE_UPDATE` (mờ hơn) |

`UpdateIntakeRequest` khai `status: Optional[Literal["received","quoted","quote_accepted","paid","dispatched","completed","cancelled"]]` — nghĩa là **PATCH nhận status hợp lệ về kiểu dữ liệu nhưng không hợp lệ về quy trình**.

**Khai thác nghiệp vụ:** người có `intake:manage` nhưng **không** thuộc `_privileged` gọi
`PATCH /intakes/{id} {"status": "completed"}` → phiếu nhảy thẳng từ `received` sang
`completed`, **bỏ qua báo giá, bỏ qua xác nhận thanh toán, bỏ qua điều phối mẫu**. Vết
kiểm toán chỉ ghi "INTAKE_UPDATE" nên khó phát hiện khi rà soát.

**Đây rõ ràng là lỗi, không phải quyết định:** `update_quotation` cùng dự án làm **đúng** —
liệt kê tường minh 8 field được sửa, loại `status`, và khoá khi `accepted`.

**Khắc phục:** bỏ `status` khỏi `UpdateIntakeRequest`; thay `setattr` mù bằng danh sách
field tường minh; nếu cần đổi trạng thái qua PATCH thì uỷ quyền về `change_status`.

#### B-02 · 🟡 MEDIUM — Đặt lại mật khẩu bởi admin sinh mật khẩu mà không ai biết

**Vị trí:** `app/services/user_service.py:326-366`, `app/schemas/user.py:33-34`

`ResetPasswordRequest.new_password` là `Optional`. Khi admin gửi body rỗng:
```python
must_change = new_password is None or new_password == ""
raw = new_password if not must_change else security.generate_temp_password()
user.password_hash = security.hash_password(raw)
...
return {"id": ..., "must_change_password": must_change, "reset_at": ...}
```
`raw` (mật khẩu tạm 14 ký tự ngẫu nhiên) **không được trả về, không được gửi mail, không
được log** — đúng theo nguyên tắc bảo mật (`security.py:35` ghi *"bàn giao qua kênh an
toàn, KHÔNG trả API"*), **nhưng kênh an toàn đó chưa được xây**.

Kết quả: mọi refresh token bị thu hồi, mật khẩu bị đổi thành chuỗi không ai biết →
**người dùng bị khoá khỏi hệ thống**. Cách thoát duy nhất là "Quên mật khẩu" (cần
`status == "active"` và SMTP hoạt động) hoặc admin gọi lại API với mật khẩu tường minh.

**Khắc phục:** gửi mật khẩu tạm qua mail (hạ tầng SMTP + `email_service` đã có sẵn), hoặc
gửi link đặt lại mật khẩu (tái dùng `_issue_token` + `PURPOSE_PASSWORD_RESET`) — phương án
thứ hai tốt hơn vì không truyền mật khẩu qua mail.

#### B-03 · 🔵 LOW — Sinh mã theo `COUNT()` mâu thuẫn với xoá cứng

`quotations` và `sample_intakes` có endpoint DELETE (xoá cứng, không soft delete) trong khi
mã được sinh từ `COUNT()`/`MAX()`. Xoá `BG-2026-0005` → mã tiếp theo lại là `BG-2026-0005`
→ trùng với bản ghi cũ nếu chưa xoá hết. Với `quotation`, `_next_code` dùng `MAX` nên miễn
nhiễm phần này nhưng **sai khi vượt 9999** (so sánh chuỗi: `'BG-2026-10000' < 'BG-2026-9999'`).

#### ✅ Những đường nghiệp vụ đã kiểm và ĐÚNG

- Không xuất kho quá tồn (row lock + CHECK không âm + `balance_after` snapshot).
- Không sửa CAPA đã đóng (trigger DB, không chỉ tầng ứng dụng).
- Không sửa giấy chứng nhận hiệu chuẩn (trigger DB chặn UPDATE + DELETE).
- Không sửa báo giá khách đã đồng ý (`status == "accepted"` → 409).
- Không đổi mã thiết bị (`CODE_IMMUTABLE`).
- Không nâng lương ngày tương lai (`FUTURE_RAISE_NOT_ALLOWED`).
- Không tự cấp vai trò khi đăng ký (`extra="forbid"`, luôn `pending`, admin gán vai trò).
- Không tự đổi vai trò/phòng ban qua `PATCH /auth/me` (`extra="forbid"`, chỉ tên + email).
- Xác thực email **không** tự kích hoạt tài khoản — vẫn chờ admin duyệt.
- Lịch sử lương append-only (snapshot mức cũ + mức mới).

---

## 3. Audit kiểm thử

| Loại test | Có? | Tệp | Nhận xét |
|---|---|---|---|
| Kiến trúc (hợp đồng API, mã lỗi) | ✅ | `tests/architecture/` (2 file) | Chạy không cần DB, fail sớm trong CI |
| Bảo mật — quét xác thực toàn route | ✅ | `tests/security/test_idor_routes.py` | 296 route; allowlist công khai có lý do từng dòng |
| **Bảo mật — uỷ quyền cấp đối tượng** | ❌ | — | **Khoảng trống chính.** File trên tự ghi: *"Phần user A không đọc được của user B cần fixture DB thật; đó là việc của test tích hợp"* — test đó chưa được viết |
| RBAC theo vai trò | ⚠️ | `tests/services/test_hr_rbac_scope.py` | Chỉ HR. Không có cho tài liệu `restricted`, báo giá, biểu mẫu |
| Đồng thời / race | ⚠️ | `tests/integration/test_registration_race.py` | Chỉ đăng ký. **Không có** cho sinh mã trùng, xuất kho song song, refresh token song song |
| Transaction / atomicity | ✅ | `tests/integration/test_chemical_txn_integration.py` | Postgres thật, savepoint isolation |
| Router / API | ⚠️ | 5 file (`customer`, `intake_customer_link`, `nonconformity`, `risk`, `user_admin`) | 5/39 router có test |
| Upload | ⚠️ | `test_attachment_common.py`, `test_storage_sanitize.py` | Kiểm MIME allowlist + sanitize tên file. **Không** kiểm quyền upload |
| Chuyển trạng thái không hợp lệ | ⚠️ | rải rác trong `test_risk_flow`, `test_nonconformity_flow` | **Không** có cho intake (nơi có B-01) |
| Middleware | ✅ | `test_idempotency.py` | |
| Cấu hình | ✅ | `test_config_guard.py` | Kiểm chốt chặn secret |
| Thu hồi token | ✅ | `test_auth_token_revocation.py` | |
| Giám sát scheduler | ✅ | `test_scheduler_monitoring.py` | |
| Tải / hiệu năng | ⚠️ | `loadtest/locustfile.py`, `perf/baseline.js`, `perf/endpoint-latency.sh` | Có kịch bản, chưa thấy ngưỡng gác trong CI |

**Coverage:** cổng CI ở **45%** (đo được 47,8%). Có ghi chú đính chính trung thực về một
phép đo sai trước đó — dấu hiệu kỷ luật tốt.

**Kết luận:** bộ test có **chiều rộng ở tầng khai báo** (quét route, hợp đồng response) và
**chiều sâu ở vài module** (hoá chất, HR, rủi ro, NC), nhưng **thiếu đúng loại test lẽ ra
bắt được 3 lỗi HIGH của audit này**: uỷ quyền cấp đối tượng qua DB thật.

---

## 4. Data privacy

| Dữ liệu | Bảng | Nhạy cảm | Kiểm soát hiện có | Thiếu |
|---|---|---|---|---|
| Email, họ tên, phòng ban | `users` | 🟡 | RBAC; `GET /users` = admin + office | — |
| Lương (bậc, hệ số, lương cơ sở, lịch sử) | `hr_profiles`, `salary_history` | 🔴 | Field-level strip 3 nhóm; đọc = admin/leader/office + chính chủ; sửa = admin/office; audit **không ghi giá trị tiền** (BR-HR-024) ✅ | Không mã hoá at-rest |
| Điện thoại, chức danh, ngày vào làm | `hr_profiles` | 🟡 | ⚠️ `reception`/`qms`/`lab_manager` đọc được của mọi người (S-13) | Đảo sang allowlist |
| Bằng cấp, chứng chỉ (tệp) | `attachments` (`hr_profile`) | 🔴 | ⚠️ **Bypass được qua `/attachments/{id}`** (S-01) | Vá S-01 |
| PII khách hàng | `customers` | 🟠 | `require_roles`, cấm `office` ✅ | — |
| PII khách hàng + giá | `quotations` | 🟠 | ❌ **Không kiểm quyền đọc** (S-03) | Vá S-03 |
| Kết quả thử nghiệm + dữ liệu thô | `sample_results`, `attachments` | 🔴 | Phạm vi phòng + trạng thái công bố | ⚠️ Bypass qua `/attachments/{id}` |
| Nhật ký truy cập | `access_stats`, `audit_logs` | 🟠 | Đọc = admin/leader; `access_stats` xoá sau 90 ngày ✅ | `audit_logs` chưa có chính sách lưu trữ dài hạn/partition |
| Mật khẩu | `users.password_hash` | 🔴 | bcrypt cost 12 ✅ | ⚠️ Cắt cụt ở 72 byte trong khi `max_length=128` |
| Token phiên | `refresh_tokens`, `auth_tokens` | 🔴 | Chỉ lưu SHA-256 ✅ | — |

**Encryption in transit:** ✅ HTTPS ở biên Cloudflare. ⚠️ Nội bộ docker network là HTTP thuần
(chấp nhận được cho single-host).
**Encryption at rest:** ❌ Không có. Volume Docker trần trên đĩa host.
**Retention/deletion:** ⚠️ Chỉ `access_stats` (90 ngày) và `auth_tokens` (7 ngày). Không có
chính sách cho dữ liệu cá nhân khi nhân viên nghỉ việc.

---

## 5. Checklist cấu hình production

| Mục | Trạng thái | Ghi chú |
|---|---|---|
| `DEBUG=false` / `ENVIRONMENT=production` | ✅ | Cứng trong `docker-compose.prod.yml:190`; `/docs`+`/redoc` tự tắt |
| Production logging (JSON, có correlationId) | ✅ | `logging_config.py`; log rotation 50MB×5 |
| Secure CORS | ✅ | Allowlist từ `CORS_ORIGINS`, biến bắt buộc |
| HTTPS | ✅ | Cloudflare Tunnel; HSTS bật ở production |
| Secure cookies | ✅ | HttpOnly + Secure(prod) + SameSite=Strict + Path hẹp |
| Strong secrets | ✅ | JWT 64 ký tự; chốt chặn từ chối khởi động nếu yếu |
| **Secrets không lọt vào git** | ❌ | `.env.prod.bak.*` không được ignore — **P0** |
| Database credentials | ✅ | Không mặc định; `${VAR:?}` bắt buộc |
| **DB user least-privilege** | ❌ | App dùng user sở hữu schema → DROP được trigger audit |
| Connection pool | ✅ | 4×(12+28)=160 < `max_connections=200`; threadpool AnyIO căn đúng |
| Timeouts — Redis/S3/SMTP/push | ✅ | 2s / 3+10s / 10s / 5s |
| **Timeout — HTTP request** | ❌ | Không có |
| **Timeout — `statement_timeout` DB** | ❌ | Không có |
| Rate limiting | ⚠️ | 8/296 endpoint; export nặng nhất không có |
| File size limit | ✅ | 2 lớp (middleware + service) + nginx `client_max_body_size 25m` |
| Request size limit | ⚠️ | Chỉ multipart; JSON body không giới hạn ở tầng app (nginx chặn ở 25m) |
| **Health check dùng được** | ❌ | nginx không proxy `/health` — checklist go-live luôn xanh giả |
| **Backup** | ❌ | Không có gì tự động — **P0** |
| **Monitoring** | ❌ | Có `/metrics` nhưng không có Prometheus/Grafana triển khai |
| **Alerting** | ❌ | Không có |
| Migration strategy | ✅ | Service one-shot + advisory lock + dry-run CI |
| Graceful shutdown | ✅ | `--timeout-graceful-shutdown 30` + drain push + drain page_view |
| Container non-root | ✅ | Backend. ⚠️ nginx master vẫn root |
| Image pinning | ⚠️ | `minio/minio:latest` |
| CI/CD | ✅ | 4 workflow: lint, test, integration+coverage, migration dry-run, docker build, security scan |

---

## 6. Giám sát & cảnh báo cần có trước khi go-live

| Chỉ số | Ngưỡng | Vì sao |
|---|---|---|
| `up{job="lims-api"}` | == 0 trong 1 phút | Dịch vụ chết |
| `redis_memory_used_bytes / maxmemory` | > 80% | `noeviction` → `SET` bị từ chối → logout hỏng, và Redis chết = API chết (T-02) |
| `rate(http_requests_total{status=~"5.."}[5m])` | > 1% | Lỗi hệ thống |
| `histogram_quantile(0.95, http_request_duration_seconds)` | > 2s | Suy giảm hiệu năng |
| `scheduler_job_last_success` | == 0 với bất kỳ job nào | Cron ISO 17025 thất bại (hiện chỉ ghi Redis, không ai đọc) |
| `time() - scheduler_job_last_run_timestamp` | > 26h | Cron bỏ lỡ cửa sổ |
| `pg_stat_activity` count | > 160 | Sắp cạn pool |
| Kích thước bản backup gần nhất | == 0 hoặc > 26h tuổi | Backup hỏng thầm lặng |
| `rate(http_requests_total{path="/api/v1/auth/login",status="401"}[5m])` | tăng đột biến | Credential stuffing (T-05) |
| Dung lượng đĩa host | > 85% | MinIO + Postgres + log |

---

## 7. Điểm số

| Hạng mục | Điểm | Lý do |
|---|---:|---|
| **Architecture** | **7**/10 | Phân lớp rõ, middleware đầy đủ, quyết định có tài liệu. Trừ: không có repository layer, 166 `db.commit()` rải rác, Redis là SPOF, background job trong process API |
| **Security** | **5**/10 | Nền tảng tốt (không SQLi/RCE/path traversal/XSS, chống enumeration, security headers, chốt secret). Trừ nặng: 3 lỗ HIGH về uỷ quyền + secret có thể lọt vào git công khai |
| **Authentication** | **9**/10 | Xuất sắc. Trừ: chính sách mật khẩu yếu, không MFA cho admin |
| **Authorization** | **4**/10 | Có ma trận RBAC dữ liệu hoá và field-level strip tốt, nhưng 2 endpoint bỏ qua toàn bộ + mẫu denylist lặp lại + 3 cơ chế song song không đồng nhất |
| **Database** | **7**/10 | Schema rất tốt (250 index, trigger append-only, constraint đầy đủ). Trừ: N+1 diện rộng, sinh mã `COUNT()+1`, không `statement_timeout` |
| **Business Logic** | **6**/10 | Phần lớn state machine được enforce, nhiều chỗ enforce tận tầng DB. Trừ: B-01 bypass state machine phiếu nhận mẫu, B-02 reset password khoá người dùng |
| **Concurrency** | **8**/10 | Row lock đúng chỗ ở mọi đường quan trọng, leader-lock có compare-and-extend Lua. Trừ: fail-open scheduler, 2 chỗ sinh mã không retry |
| **API Design** | **6**/10 | Format thống nhất, status code đúng, validation tốt. Trừ: 0 `response_model`, rate limit 8/296, phân trang trong bộ nhớ |
| **Performance** | **6**/10 | Đủ cho quy mô hiện tại, có đo đạc và tối ưu N+1 ở 2 chỗ. Trừ: tổng hợp báo cáo trong RAM, export không giới hạn, không timeout |
| **Observability** | **4**/10 | Có metrics + JSON log + correlation id + scheduler run-history. Trừ nặng: **không triển khai monitoring/alerting nào**, và health check qua nginx luôn xanh giả |
| **Testing** | **5**/10 | Có test kiến trúc + quét route + race + coverage gate. Trừ: thiếu đúng loại test lẽ ra bắt được 3 lỗ HIGH; 5/39 router có test |
| **Docker** | **7**/10 | Non-root, healthcheck có lý do, resource limit, graceful shutdown, không publish cổng DB. Trừ: thiếu hardening flags, `minio:latest` |
| **Deployment** | **7**/10 | Cloudflare Tunnel gọn và **đã xác minh đang chạy đúng** (không publish cổng nào), migration an toàn, tài liệu triển khai chi tiết. Trừ: `ops/RUNBOOK.md` thiếu overlay ở toàn bộ 15 lệnh (rollback sẽ làm mất tunnel), `ports 3060` vẫn nằm trong profile prod, checklist xác minh `/health` sai |
| **Backup/Recovery** | **1**/10 | Tài liệu DR viết tốt. Nhưng **không có gì được thực thi**. RPO=∞, RTO=∞. Điểm 1 (không phải 0) vì tài liệu tồn tại và volume có persistence |

### Tổng: **72 / 140** (≈ 51/100 quy đổi)

> Cập nhật 2026-08-07: Deployment 6→7 sau khi xác minh overlay Cloudflare đang chạy đúng
> (không publish cổng nào ra host) — S-09 hạ từ MEDIUM/P1 xuống LOW/P2.

```
Production Status:  ⚠️  CONDITIONALLY READY
```

**Điều kiện:** hoàn thành **toàn bộ nhóm P0** trong REMEDIATION_PLAN. Ba trong sáu vấn đề
HIGH (S-01, S-02, S-03) là **uỷ quyền cấp đối tượng — khai thác được bằng một tài khoản hợp
lệ và một lệnh curl**, và một (D-11) là **mất dữ liệu không hồi phục**. Không mục nào trong
đó chấp nhận được cho hệ thống chịu ISO/IEC 17025 mở ra Internet.

**Điểm số cao ở Authentication (9) và Concurrency (8) không bù được cho Authorization (4)
và Backup (1)** — đúng theo nguyên tắc: một lỗ hổng HIGH về phân quyền làm hệ thống NOT
READY bất kể tổng điểm.
