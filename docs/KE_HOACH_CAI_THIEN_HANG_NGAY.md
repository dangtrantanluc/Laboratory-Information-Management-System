# KẾ HOẠCH CẢI THIỆN THEO NGÀY — LIMS

> Lập ngày 2026-08-07 · Nguồn: 7 báo cáo backend (`docs/*.md`) + 6 báo cáo frontend
> (`docs/frontend/*.md`).
> Giả định: **một lập trình viên, ~5 giờ tập trung/ngày**. Ngày = ngày làm việc, không phải
> ngày lịch.
>
> Nguyên tắc sắp xếp: **rủi ro ÷ công sức**, tôn trọng phụ thuộc kỹ thuật, và mỗi ngày kết
> thúc bằng **một thứ kiểm chứng được** — không phải "đã sửa xong".

---

## 0. Điểm xuất phát (chốt trạng thái thật)

**Đã làm xong, CHƯA COMMIT** — 20 file sửa + 16 file mới đang nằm trên nhánh `main`:

| Nhóm | Nội dung |
|---|---|
| Backend P0 | `attachment_authz.py` (14 guard, deny-by-default) · quyền đọc `/quotations` · bỏ `status` khỏi PATCH intake · `.gitignore` `.env.*` |
| Backend cron | `_sanitize` chịu khoá số · `run_cleanup(db)` · 2 chỗ `except` im lặng nay có log |
| Hạ tầng | `test-backend.sh` có chốt an toàn · `test-backend-isolated.sh` mới · `ops/backup/lims-backup.sh` sửa 4 lỗi + phát metric |
| Frontend | `Forms.tsx` dùng `replaceFormFile` · `canViewQuotations` siết theo nav |
| Test | 26 test bảo mật/RBAC + 30 test hợp đồng cron |
| Tài liệu | 13 báo cáo audit |

**Kiểm chứng đã có:** `609 passed, 0 failed` · coverage 49,3% · `ruff` sạch · `tsc` 0 lỗi ·
production `/health/ready` → `db/redis/minio: true`.

**Rủi ro lớn nhất lúc này không phải lỗ hổng nào — mà là 36 file chưa commit.** Một `git
checkout` nhầm là mất toàn bộ. Ngày 1 giải quyết việc đó trước tiên.

---

## Nhịp hằng ngày (5 phút, làm trước khi bắt đầu)

Cho tới khi có monitoring (Ngày 10), đây là cách duy nhất phát hiện sự cố:

```bash
alias limsc='docker compose -f /home/tanluc/workspace/lims/docker-compose.prod.yml \
             -f /home/tanluc/workspace/lims/docker-compose.cloudflare.yml \
             --env-file /home/tanluc/workspace/lims/.env.prod'

limsc ps                                              # 6 container, không cổng nào publish
docker exec lims-api curl -fsS localhost:8060/health/ready | python3 -m json.tool | head -20
tail -3 /var/log/lims-backup.log                      # có dòng "HOÀN TẤT" của đêm qua
```

Ba dấu hiệu phải dừng lại xử lý ngay: có cổng `0.0.0.0:*` trong `limsc ps` · bất kỳ
`checks` nào `false` · bất kỳ cron nào `status: failed`.

---

# TUẦN 0 — Chốt việc đã làm & bịt hai lỗ mất dữ liệu

## Ngày 1 · Đưa việc đã làm lên production + có bản backup đầu tiên

**Mục tiêu:** không còn dòng code nào chỉ tồn tại trong working tree, và tồn tại ít nhất một
bản sao lưu đã được restore thử.

**Sáng — tách 3 PR** (đừng gộp 36 file vào một PR, sẽ không ai review nổi):

```bash
git checkout -b fix/p0-authorization
# attachment_authz.py, attachment_service.py, sample_attachment_service.py,
# quotations.py, sample_flow.py (schema+service), 3 file test bảo mật, .gitignore
```
```bash
git checkout -b fix/cron-audit-sanitize
# audit_service.py, cleanup_cron_service.py, nc/risk/equipment/hr_cron_service.py,
# test_cron_contract.py
```
```bash
git checkout -b chore/ops-and-docs
# ops/backup/*, ops/cron/*, scripts/test-backend*.sh, docs/**
```

Chờ CI xanh từng PR (`backend-ci`, `security`, `architecture`), merge tuần tự.

**Chiều — cài backup (cần `sudo`).** Sửa 3 giá trị trước khi cài:

```bash
# 1. LIMS_DIR phải đúng thư mục deploy thật
docker inspect lims-api --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'
#   → /home/tanluc/workspace/lims   (KHÔNG phải /opt/lims như file cron mặc định)

# 2. LIMS_BACKUP_REMOTE — đặt đích off-site THẬT (NAS/máy khác/S3).
#    Để nguyên 'user@backup-host' thì rsync thất bại mỗi đêm.

# 3. Cài (tên KHÔNG có .sh — file cron gọi đúng tên đó)
sudo cp ops/backup/lims-backup.sh /usr/local/bin/lims-backup
sudo chmod +x /usr/local/bin/lims-backup
sudo cp ops/cron/lims-backup.cron /etc/cron.d/lims-backup   # đã sửa LIMS_DIR + REMOTE
sudo LIMS_DIR=/home/tanluc/workspace/lims /usr/local/bin/lims-backup
```

**Deploy:** `limsc up -d --build` (nhớ **đủ hai file** `-f`).

**Xong khi:**
- [ ] `git status` sạch trên `main`, 3 PR đã merge
- [ ] `ls -lh /var/backups/lims/` có `db-*.dump` **và** `files-*.tar.gz`, cả hai > 1 KB
- [ ] `limsc ps` → 6 container healthy, **không** cổng nào publish
- [ ] `docker exec lims-api curl -fsS localhost:8060/health/ready` → 3 `true`

---

## Ngày 2 · Diễn tập restore + bốn việc nhỏ, hiệu quả cao

**Mục tiêu:** chứng minh backup dùng được, và đóng 3 lỗ nhỏ nhất-nhưng-rộng-nhất.

**Sáng — diễn tập restore (1 giờ, bắt buộc có biên bản).** Đây là bước biến "có backup"
thành "có khả năng khôi phục":

```bash
docker run -d --name pg-restore-test -e POSTGRES_PASSWORD=x postgres:15-alpine
docker exec -i pg-restore-test psql -U postgres -c "CREATE DATABASE lims_restore_test;"
docker exec -i pg-restore-test pg_restore -U postgres -d lims_restore_test \
    < /var/backups/lims/db-<ngày>.dump
docker exec pg-restore-test psql -U postgres -d lims_restore_test \
  -c "SELECT version_num FROM alembic_version;" \
  -c "SELECT count(*) FROM audit_logs;" -c "SELECT count(*) FROM users;"
```
Đối chiếu số dòng với production, **ghi RTO đo được vào `ops/RUNBOOK.md`**, tick 2 dòng
checklist trong `DEPLOY_LINUX.md`. Rồi `docker rm -f pg-restore-test`.

**Chiều — 4 việc nhỏ:**

| Việc | Nguồn | Thời gian |
|---|---|---|
| Security header + CSP vào `lims-frontend/nginx.conf` | FE-S-01 | 30 phút |
| Cảnh báo *"Chỉ hiển thị 100 bản ghi đầu — hãy dùng bộ lọc"* trong `DataTable` khi `rows.length === 100` | FE-P-01 (chốt tạm) | 15 phút |
| `AbortSignal.timeout(30_000)` trong `lib/api.ts` | FE-P-06 | 1 giờ |
| Sửa `ops/RUNBOOK.md` dùng alias `limsc` đủ 2 file compose (15 lệnh) | S-09/T-06 | 30 phút |

> **Vì sao dòng thứ 2 quan trọng dù chỉ 15 phút:** nó không sửa được gốc, nhưng **xoá bỏ
> ngay tình trạng mất dữ liệu âm thầm**. Từ giờ người dùng biết mình đang nhìn danh sách bị
> cắt. Bản đầy đủ làm ở Ngày 6-7.
>
> **Vì sao sửa RUNBOOK:** thủ tục rollback ở dòng 149 chạy thiếu overlay Cloudflare sẽ **làm
> mất `cloudflared`** (hệ thống offline) — chính lỗi này đã xảy ra thật trong phiên audit.

**Xong khi:**
- [ ] `ops/RUNBOOK.md` có RTO đo được, và 0 lệnh nào thiếu overlay
- [ ] `curl -sI https://<domain>/` có `Content-Security-Policy`, `X-Frame-Options`, `nosniff`
- [ ] `curl -sI https://<domain>/assets/index-*.js` **cũng có** (nginx không kế thừa
      `add_header` vào location đã có header riêng — đây là cạm bẫy hay quên nhất)
- [ ] DevTools Console: 0 CSP violation khi đi Dashboard → Mẫu → Tài liệu → Báo cáo

---

## Ngày 3 · Lỗi API không được giả dạng "không có dữ liệu"

**Mục tiêu:** người dùng phân biệt được "trống" với "hỏng".

Thêm `ErrorState` vào `src/components/ui/States.tsx` (dùng `describeError` đã có sẵn ~150
mã lỗi), rồi áp vào trang theo thứ tự ảnh hưởng quyết định vận hành:

```
SampleRequests · SampleFlow · Documents · DocumentPendingReview
Nonconformities · Risks · Equipment · Chemicals · Users · AuditLogs
```

10 trang hôm nay, 39 trang còn lại rải vào các ngày sau (mỗi trang 2 dòng).

> Phụ thuộc: **phải làm sau timeout của Ngày 2**. Không có timeout, `useAsync` không bao giờ
> settle khi mất mạng → `ErrorState` không bao giờ hiện, trang quay vô hạn.

**Xong khi:**
- [ ] `limsc stop lims-api` → 10 trang trên hiện **thông báo lỗi + nút "Thử lại"**,
      không trang nào hiện "Không có dữ liệu"
- [ ] Bật lại `lims-api`, bấm "Thử lại" → dữ liệu về, không cần F5

---

# TUẦN 1 — Frontend P0 còn lại

## Ngày 4 · Hết đăng xuất ngẫu nhiên giữa giờ làm

**Mục tiêu:** hai tab mở song song không còn làm người dùng bị thu hồi toàn bộ phiên.

- Khoá refresh chéo tab bằng **Web Locks API** trong `lib/api.ts` (FE-S-02)
- Đồng bộ token giữa tab qua sự kiện `storage`
- Dừng polling khi tab ẩn: `Topbar.tsx:106` (30s) và `useNavBadges.ts:34` (60s) (FE-P-03)

> Làm hai việc cùng ngày vì chúng cùng một nguyên nhân: chính hai nhịp polling bảo đảm mọi
> tab chạm 401 gần như cùng lúc khi access token hết hạn.

**Xong khi:**
- [ ] Tạm đặt `ACCESS_TOKEN_TTL_MINUTES=1`, mở 2 tab, đợi 3 phút → **không** xuất hiện
      *"Phát hiện dùng lại phiên cũ"*; cả hai tab vẫn dùng được
- [ ] Trả `ACCESS_TOKEN_TTL_MINUTES` về 10, deploy lại
- [ ] Tab để nền 5 phút → DevTools Network không có request nào mới

---

## Ngày 5 · Vá lỗ hổng phân quyền còn lại + chặn lớp lỗi

**Mục tiêu:** `/documents/stats` không còn lộ, và mẫu lỗi "hai nguồn sự thật" bị chặn ở gốc.

**Sáng:** chốt danh sách vai trò được xem thống kê truy cập tài liệu với nghiệp vụ, rồi áp
**đồng thời ba nơi** (BE là authority — siết trước):
1. `lims-backend/app/services/document_service.py:622` (hiện **chỉ chặn `office`**)
2. `lims-frontend/src/lib/rbac.ts` → `canViewDocumentStats`
3. `lims-frontend/src/components/layout/nav.ts`

**Chiều:** `nav.ts` **dùng lại chính hàm `canXxx`** thay vì tự khai mảng `roles` (FE-A-01):
```ts
{ to: '/documents/stats', label: 'Thống kê truy cập TL', can: canViewDocumentStats }
```
Kèm test đối chiếu: mọi mục nav phải có route tương ứng và **cùng vị từ quyền**.

> Đây là việc quan trọng nhất tuần này. Hai nguồn sự thật đã sinh ra **hai** lỗ hổng
> (`/quotations` đã vá, `/documents/stats` chưa). Không chặn ở gốc thì sẽ có lỗ thứ ba.

**Xong khi:**
- [ ] Đăng nhập bằng tài khoản `staff`, gõ thẳng `/documents/stats` → 403 ở **backend**
- [ ] Test đối chiếu nav ↔ rbac chạy xanh trong CI

---

## Ngày 6–7 · Phân trang server cho các bảng sẽ vượt 100 dòng

**Mục tiêu:** không còn bản ghi nào vô hình.

Hạ tầng đã có cả hai đầu (backend nhận `page`/`limit` + trả `meta.total`; `DataTable.tsx:46`
đã hỗ trợ prop `server`) — chỉ thiếu dây nối. **51 vị trí `limit: 100`, 0 vị trí dùng
`server`.**

Thứ tự theo mức chắc chắn vượt 100 trong năm đầu:

| Ngày | Trang |
|---|---|
| Ngày 6 | `SampleRequests` · `TestParameters` · `Documents` |
| Ngày 7 | `Chemicals` · `AuditLogs` · `Users` · `Equipment` · `Customers` |

Cạm bẫy: đổi `q`/filter **phải** `setPage(1)`, nếu không người ở trang 5 lọc lại sẽ thấy
trống.

**Xong khi:**
- [ ] Tạo > 100 bản ghi thử ở 1 bảng (hoặc hạ `limit` xuống 5 để mô phỏng) → chuyển trang
      lấy đúng dữ liệu tiếp theo, `meta.total` hiển thị đúng tổng thật
- [ ] Gỡ cảnh báo tạm "chỉ hiển thị 100 bản ghi" ở các bảng đã chuyển

---

# TUẦN 2 — Độ tin cậy backend & quan sát được

## Ngày 8 · Backend không sập vì Redis, không treo vì truy vấn chậm

| Việc | Nguồn | Ghi chú |
|---|---|---|
| Xử lý Redis-down **có chủ đích** ở `is_jti_denied` + `_check_lockout` | S-05 | Chọn 503+`Retry-After` hoặc fail-open + log SECURITY. **Ghi lý do vào code** — hiện fail-closed là do quên, không phải do chọn |
| `statement_timeout=30s` + `idle_in_transaction_session_timeout=60s` cho Postgres | D-09 | Đặt riêng giá trị cao hơn cho vai trò `migrate` |
| Retry `IntegrityError` cho `create_intake` + `create_quotation` | D-03 | Sao chép mẫu 5-lần đã dùng ở `risk_service.py:113` |
| `export_slot()` + rate limit cho `result-report.pdf` và `quotations/export.xlsx` | API-07 | Semaphore đã tồn tại, 2 đường xuất nặng nhất không dùng |

**Xong khi:**
- [ ] `limsc stop redis` → API trả **503 có thông điệp rõ**, không phải 500 trần; bật lại → hồi phục
- [ ] Hai người tạo phiếu nhận mẫu cùng lúc → cả hai thành công, mã khác nhau

---

## Ngày 9 · Health check nói thật + upload không tin lời khai của client

| Việc | Nguồn |
|---|---|
| Thêm `location = /health` và `= /health/ready` vào `nginx.conf`; `/health/ready` trả **503** khi degraded và **không** kèm `errors` ra ngoài | S-10, S-11 |
| Sửa `DEPLOY_LINUX.md` checklist thành kiểm nội dung: `curl -fsS .../health \| grep -q '"status":"ok"'` | S-11 |
| Kiểm **magic bytes** khi upload + `add_header X-Content-Type-Options nosniff` cho `location /lims-attachments/` | S-06 |
| Allowlist host cho endpoint Web Push; chặn IP literal + dải private | S-07 |

> Hiện `curl https://<domain>/health/ready` trả **200 kèm HTML của SPA** vì nginx không proxy
> đường đó — checklist go-live **luôn xanh kể cả khi backend đã chết**. Đây là kiểm tra an
> toàn giả, nguy hiểm hơn không có kiểm tra.

**Xong khi:**
- [ ] `curl -fsS https://<domain>/health/ready` trả **JSON**, không phải HTML
- [ ] `limsc stop minio` → endpoint đó trả **503**; bật lại → 200
- [ ] Upload file `.html` đổi tên thành `.pdf` → bị từ chối

---

## Ngày 10–11 · Có mắt để nhìn

**Mục tiêu:** sự cố được phát hiện bởi hệ thống, không phải bởi điện thoại của người dùng.

**Ngày 10 — Backend monitoring.** `ops/monitoring/prometheus.yml` và `alerts.yml` (5 alert)
**đã viết sẵn**, chỉ thiếu compose để dựng:
- Viết `docker-compose.monitoring.yml`: Prometheus + Alertmanager + node-exporter + postgres-exporter
- **Bật textfile collector** cho node-exporter — script backup đã phát metric
  `lims_backup_last_success_timestamp_seconds`, nhưng alert `BackupMissing` sẽ không bao giờ
  kêu nếu không có collector đọc nó
- Thêm alert `scheduler_job_last_success == 0` — **ca kiểm chứng đầu tiên**: 3 cron đã hỏng
  5 ngày mà không ai biết

**Ngày 11 — Frontend error tracking.** GlitchTip (tương thích SDK Sentry, self-host được
trong cùng compose):
- Nối `correlationId` sẵn có của `lib/api.ts` vào scope → ghép được với log backend
- **Bắt buộc lọc trước khi gửi:** `Authorization`, body chứa mật khẩu, PII
- Bắt `unhandledrejection` ở `main.tsx`

**Xong khi:**
- [ ] Tắt `lims-api` 3 phút → nhận cảnh báo `ApiDown`
- [ ] Ném lỗi thử ở frontend → thấy trong GlitchTip **kèm correlationId**, và **không** thấy token

---

## Ngày 12 · Dọn phần còn lại của tuần

| Việc | Nguồn |
|---|---|
| Tự host font Inter, gỡ 2 `<link>` Google → siết CSP về `'self'` hoàn toàn | FE-S-05 |
| `npm audit fix` (patch bump `react-router-dom` + `postcss`; **không** `--force`) | FE-S-04 |
| `lazy()` Dashboard + prefetch sau login → bỏ 110 kB gzip recharts khỏi lần tải đầu | FE-P-02 |
| Sửa `ui/Field.tsx`: `useId` + `htmlFor` + `aria-describedby` + `role="alert"` | FE-AC-01 |
| Trang 404 thay `Navigate to="/dashboard"` · `robots.txt` · bỏ mặc định `localhost` trong `Dockerfile` | FE-U-02, FE-S-10, FE-S-11 |

> `Field.tsx` là **một file, phủ ~30 form**. Hiện `grep htmlFor` → 0 kết quả trên 25
> `<input>`: trình đọc màn hình không đọc được nhãn ô nhập nào.

**Xong khi:**
- [ ] `npm run build` → chunk khởi động giảm ~110 kB gzip
- [ ] CSP không còn `https://fonts.*`
- [ ] Bấm vào nhãn → focus vào ô nhập tương ứng

---

# TUẦN 3 — Lưới chắn

## Ngày 13 · Test tích hợp uỷ quyền (backend)

Đây là loại test **lẽ ra đã bắt được 3 lỗi HIGH** của đợt audit. `test_idor_routes.py` tự ghi
trong docstring rằng phần "user A không đọc được của user B" là việc của test tích hợp — và
test đó chưa từng được viết.

Bao phủ: `/attachments` chéo phòng ban · tài liệu `restricted` · minh chứng đã duyệt ·
`/quotations` theo vai trò · `/documents/stats` theo vai trò.

**Xong khi:** coverage gate CI nâng từ 45% → 50%, và các test trên chạy xanh.

## Ngày 14 · Vitest + test `lib/rbac.ts` (frontend)

`lib/rbac.ts` có 40+ hàm quyền **thuần, không cần DOM** — test cực rẻ và bảo vệ đúng thứ đã
hai lần lọt lỗi. Bảng ma trận 7 vai trò × ~20 hành động, mỗi ô một assert.

## Ngày 15 · Playwright E2E — 6 luồng

```
đăng nhập → dashboard
nhận mẫu → chuyển mẫu → phòng lab
nhập kết quả → duyệt
duyệt tài liệu
quản trị tài khoản
staff KHÔNG vào được /users, /audit, /quotations, /documents/stats   ← âm tính, quan trọng nhất
```
Cộng một test mạng hỏng: chặn API bằng `page.route()`, khẳng định hiện `ErrorState` chứ
không phải "không có dữ liệu".

---

# Sau Ngày 15

Chuyển sang nhịp **1 mục P2/tuần**, xen kẽ giữa hai plan:

| Thứ tự | Việc | Nguồn |
|---|---|---|
| 1 | Tách vai trò DB (`lims_migrate` owner / `lims_app` chỉ DML) — trigger append-only không bị credential ứng dụng gỡ được | S-18 |
| 2 | Gom lô N+1 ở 5 endpoint list nặng nhất | D-02 |
| 3 | `GROUP BY date_trunc` thay tổng hợp trong RAM | D-04 |
| 4 | Dọn `localStorage` khi logout · escape 2 điểm `samplePdf.ts` · `apiUpload` gọi `onSessionExpired` | FE-S-07/08/09 |
| 5 | Hardening container (`no-new-privileges`, `cap_drop`, ghim `minio` tag) | S-16 |
| 6 | Chính sách mật khẩu ≥12 ký tự + chặn danh sách phổ biến | S-12 |
| 7 | Chuẩn hoá 3 cơ chế phân quyền backend về `require_permission` | API-04 |
| 8 | `response_model` cho endpoint chạm dữ liệu nhạy cảm | API-05 |

---

## Quy tắc khi tụt tiến độ

Sẽ có ngày vỡ kế hoạch. Khi đó:

1. **Không bao giờ hoãn Ngày 1–2.** Backup và commit không phải tính năng, chúng là điều
   kiện để mọi ngày sau có ý nghĩa.
2. **Ưu tiên việc "xoá bỏ thông tin sai" trước việc "thêm tính năng đúng".** Cảnh báo 100
   bản ghi (15 phút) quan trọng hơn phân trang server đầy đủ (2 ngày) — vì cái đầu chấm dứt
   việc người dùng ra quyết định trên dữ liệu thiếu.
3. **Mỗi ngày phải kết thúc bằng trạng thái deploy được.** Không để nhánh dang dở qua đêm ở
   giữa một thay đổi phân quyền.
4. Nếu chỉ còn **3 ngày** trước khi bắt buộc go-live: làm Ngày 1, Ngày 2, Ngày 3. Ba ngày đó
   đóng được: không có backup · không có security header · mất dữ liệu âm thầm · lỗi giả dạng
   trống. Bốn thứ còn lại (đăng xuất ngẫu nhiên, `/documents/stats`, phân trang, monitoring)
   là rủi ro chấp nhận được **có ý thức** trong ngắn hạn — và phải ghi lại là đã chấp nhận.

---

## Mốc đo tiến độ

| Mốc | Sau ngày | Backend | Frontend |
|---|---|---|---|
| Hiện tại | — | 72/140 (P0 xong 4/5) | 82/140 |
| Có backup + đã commit | 2 | **~85/140** | ~88/140 |
| Frontend P0 xong | 7 | ~85/140 | **~104/140** ⚠️ CONDITIONALLY READY |
| Backend P1 xong | 12 | **~105/140** ⚠️ CONDITIONALLY READY | ~112/140 |
| Có test + monitoring | 15 | **~115/140** ✅ | **~120/140** ✅ |
