# SECURITY AUDIT — LIMS Backend

> Ngày audit: 2026-08-07 · Phạm vi: `lims-backend/`, `lims-frontend/nginx.conf`,
> `docker-compose*.yml`, `.env.prod*`, `.github/workflows/`.
> Phân loại mỗi phát hiện: **[XÁC NHẬN]** = đọc mã và truy được đường khai thác cụ thể ·
> **[RỦI RO]** = điều kiện khai thác phụ thuộc cấu hình triển khai · **[KHUYẾN NGHỊ]** =
> hardening, chưa phải lỗ hổng.

---

## 0. Tóm tắt

| Mức | Số lượng | Mã |
|---|---|---|
| 🔴 CRITICAL | 0 | — |
| 🟠 HIGH | 5 | S-01, S-02, S-03, S-04, S-05 |
| 🟡 MEDIUM | 7 | S-06, S-07, S-08, S-10, S-11, S-12, S-13 |
| 🔵 LOW | 7 | S-09 (hạ mức sau khi xác minh triển khai), S-14 … S-19 |
| ⚪ INFO | 4 | S-20 … S-23 |

**Không có CRITICAL** vì: không tìm thấy đường bypass xác thực (mọi endpoint đều có
dependency auth — đã xác minh bằng quét toàn bộ 296 route), không có SQL injection
(0 chuỗi SQL nối động; toàn bộ dùng SQLAlchemy Core/ORM tham số hoá), không có RCE
(không `eval`/`exec`/`pickle`/`subprocess` trên dữ liệu người dùng), không có secret
mặc định lọt vào production (có chốt chặn lúc khởi động).

Nhóm HIGH tập trung vào **một chủ đề duy nhất: phân quyền ở cấp đối tượng (BOLA/IDOR)**
và **mất mát dữ liệu**.

---

## S-01 · 🟠 HIGH — Tải bất kỳ tệp đính kèm nào chỉ cần đăng nhập (BOLA) **[XÁC NHẬN]**

| | |
|---|---|
| **Danh mục** | Broken Object Level Authorization (OWASP API1:2023) |
| **Vị trí** | `app/routers/attachments.py:48-64` → `app/services/attachment_service.py:36-63`; luật quyền: `attachment_service.py:22-33` |

### Vấn đề

`GET /api/v1/attachments/{attachment_id}` cấp presigned URL cho **bất kỳ hàng nào** trong
bảng `attachments`. Toàn bộ kiểm quyền là:

```python
# app/services/attachment_service.py:22-33
_M1_OWNER_TYPES = {"test_request", "sample", "sample_result"}

def _check_owner_read_permission(user, owner_type):
    if owner_type in _M1_OWNER_TYPES and user.role == "office":
        raise AppException(ErrorCode.FORBIDDEN_OFFICE, ...)
```

Nghĩa là: **một luật duy nhất** — cấm vai trò `office` đọc 3 loại owner của M1. Ngoài ra
không kiểm chủ sở hữu, không kiểm phòng ban, không kiểm mức bảo mật, không kiểm trạng thái.

Bảng `attachments` là kho **dùng chung cho 20 owner_type** (`app/models/attachment.py:12-33`):
`document_version`, `form_template`, `form_submission`, `hr_profile`, `calibration`,
`chemical`, `chem_lot`, `publication`, `sample_intake`, `sample_dispatch`, `equipment`, …

### Vì sao nghiêm trọng

Mỗi module đã tự xây luật đọc riêng, và đường generic **bỏ qua tất cả**:

| Module | Luật đọc riêng của module | Bị bỏ qua ở `/attachments/{id}`? |
|---|---|---|
| Tài liệu (M3) | `security_level='restricted'` → chỉ phòng sở hữu + admin/leader (`document_common.py:96-102`) | ✅ Bỏ qua |
| Tài liệu (M3) | Bản `draft`/`review` chỉ người soạn + trưởng nhóm + admin/leader (`document_common.py:105-118`) | ✅ Bỏ qua |
| Biểu mẫu VILAS | `form:read` + phạm vi phòng (`form_file_service.py:71-78`) | ✅ Bỏ qua |
| Hồ sơ năng lực HR | `_assert_competence_read` (`hr_service.py:518`) | ✅ Bỏ qua |
| Kết quả mẫu (M1) | "RESULT_NOT_PUBLISHED nếu pending ngoài nhóm" (`sample_attachment_service.py:1-7`) | ✅ Bỏ qua |

**Chính codebase đã ghi nhận nguy cơ này mà không sửa gốc.**
`app/services/form_file_service.py:7-10`:

> *"Vì sao không dùng `POST /attachments` generic: endpoint đó chỉ yêu cầu đăng nhập
> (không kiểm quyền theo owner_type), nên bất kỳ ai biết id biểu mẫu cũng ghi đè được kho
> VILAS."*

Tác giả đã **đi vòng** quanh endpoint generic thay vì vá nó. Endpoint generic vẫn đang bật.

### Kịch bản tấn công

1. Người dùng vai trò `staff` phòng Hoá được duyệt tài khoản hợp lệ.
2. Trong thời gian còn quyền, họ mở `GET /documents/{id}/versions` của một tài liệu nội bộ
   → response chứa `attachment_id` (`document_version_service.py:54-61` — `_file_dict` trả
   thẳng `attachment_id`).
3. Sau đó tài liệu được nâng lên `restricted`, hoặc người này chuyển sang phòng khác, hoặc
   bị hạ quyền. Mọi luật ở `/documents/...` chặn họ.
4. Họ gọi `GET /attachments/{attachment_id}` → **vẫn nhận được presigned URL** → tải file.

Biến thể: vai trò `office` bị cấm ghi tài liệu (`deny_office_write`) và bị cấm đọc
attachment của mẫu, nhưng **được phép** tải mọi `hr_profile` attachment (bằng cấp, chứng
chỉ, giấy tờ cá nhân của toàn bộ nhân sự) qua đường generic.

### Yếu tố giảm nhẹ (không phải biện pháp phòng vệ)

`attachment_id` là UUIDv4 → không đoán/duyệt được. Nghĩa là kẻ tấn công phải **biết** ID.
Đây là *security through obscurity*: ID rò qua listing hợp pháp, qua log, qua
`audit_logs.detail` (`attachment_service.py:81` ghi `attachment_id` vào detail), qua lịch
sử trình duyệt, qua báo cáo lỗi. Không được tính là kiểm soát truy cập.

### Ảnh hưởng

Rò rỉ tài liệu chất lượng có kiểm soát (ISO/IEC 17025 §8.3), minh chứng VILAS, hồ sơ năng
lực nhân sự, giấy chứng nhận hiệu chuẩn, dữ liệu thô kết quả thử nghiệm. Với phòng thử
nghiệm được công nhận, đây là vi phạm điều khoản kiểm soát tài liệu và bảo mật thông tin
khách hàng (§4.2).

### Khả năng khai thác

**Trung bình** — cần một tài khoản hợp lệ (bất kỳ vai trò nào) + một `attachment_id`.

### Khắc phục

Thay `_check_owner_read_permission` bằng **bộ định tuyến quyền theo owner_type**, uỷ quyền
về đúng module sở hữu:

```python
_READ_GUARDS = {
    "document_version": lambda db, user, att: document_version_service.assert_can_read_file(db, user, att.owner_id),
    "form_template":    lambda db, user, att: form_file_service.assert_can_read(db, user, OWNER_TEMPLATE, att.owner_id),
    "form_submission":  lambda db, user, att: form_file_service.assert_can_read(db, user, OWNER_SUBMISSION, att.owner_id),
    "hr_profile":       lambda db, user, att: hr_service.assert_competence_read(user, att.owner_id),
    "sample":           ..., "sample_result": ..., "test_request": ...,
}

guard = _READ_GUARDS.get(att.owner_type)
if guard is None:
    raise forbidden("Loại tài nguyên chưa khai báo luật đọc")  # deny-by-default
guard(db, user, att)
```

**Mặc định phải là TỪ CHỐI** cho owner_type chưa khai báo — nếu không, mỗi module mới lại
tái tạo lỗ hổng này.

### Ưu tiên: **P0**

---

## S-02 · 🟠 HIGH — Đính kèm tệp vào bất kỳ đối tượng nào chỉ cần đăng nhập **[XÁC NHẬN]**

| | |
|---|---|
| **Danh mục** | Broken Function/Object Level Authorization (ghi) |
| **Vị trí** | `app/routers/attachments.py:22-45` → `app/services/attachment_service.py:106-163` |

### Vấn đề

`POST /api/v1/attachments` nhận `owner_type` + `owner_id` **từ form body của client** và
chỉ kiểm:

```python
if owner_type not in VALID_OWNER_TYPES:   # whitelist 20 giá trị
    raise ...
attachment_common.check_mime(...)          # theo Content-Type client khai
attachment_common.check_size(content)
```

Docstring tự thừa nhận: *"M7 chưa có bảng owner → kiểm tra owner tồn tại sẽ được module
tương ứng bổ sung"* (`attachment_service.py:118-121`). Việc bổ sung đó **chưa xảy ra**.

Không kiểm: owner có tồn tại không, người gọi có quyền ghi lên owner đó không, owner có ở
phòng của người gọi không, owner có đang ở trạng thái khoá (đã duyệt) không.

### Kịch bản tấn công

1. Người dùng `staff` bất kỳ biết id một `form_submission` **đã được Phòng QLCL duyệt**.
2. `form_file_service._check_submission_writable` khoá tệp sau khi duyệt
   (`form_file_service.py:81-89`) — nhưng đó là đường riêng.
3. Gọi `POST /attachments` với `owner_type=form_submission`, `owner_id=<id>` → **chèn thêm
   một attachment** vào minh chứng đã duyệt. Mọi listing của module đó
   (`_current_attachments` lọc theo `owner_type` + `owner_id` + `deleted_at IS NULL`,
   `form_file_service.py:107-126`) sẽ hiển thị tệp lạ này.

Tương tự với `document_version` (chèn tệp vào bản tài liệu đã phê duyệt), `calibration`
(chèn giấy chứng nhận hiệu chuẩn giả), `sample_result`, `hr_profile`.

### Ảnh hưởng

Phá vỡ tính toàn vẹn hồ sơ ISO/IEC 17025 §8.4 — bản ghi đã phê duyệt phải bất biến. Hệ
thống có trigger Postgres bảo vệ `calibration_records` và `capa`, nhưng **tệp đính kèm
của chúng thì không**. Chữ ký phê duyệt mất giá trị.

### Khả năng khai thác

**Trung bình** — cần tài khoản hợp lệ + id owner. Nhiều id owner được trả công khai trong
list API mà mọi người dùng đăng nhập đều gọi được.

### Khắc phục

1. Bảng định tuyến quyền GHI theo `owner_type`, deny-by-default, giống S-01.
2. Kiểm owner tồn tại (`owner_id` hiện là `UUID` không FK — `attachment.py:43`, xem
   DATABASE_AUDIT D-05).
3. Nếu không muốn duy trì bảng định tuyến: **gỡ hẳn `POST /attachments` khỏi API công
   khai** và bắt mọi module dùng endpoint riêng của mình (đúng như `form_file_service` đã
   làm). Đây là phương án ít rủi ro nhất và tốn ít công nhất.

### Ưu tiên: **P0**

---

## S-03 · 🟠 HIGH — Báo giá và thông tin khách hàng đọc được bởi mọi người dùng **[XÁC NHẬN]**

| | |
|---|---|
| **Danh mục** | Broken Function Level Authorization + Excessive Data Exposure |
| **Vị trí** | `app/routers/quotations.py:34-49` (list), `:51-58` (get), `:60-80` (export xlsx) → `app/services/quotation_service.py:130-158` |

### Vấn đề

Ba endpoint đọc của module báo giá chỉ có `Depends(get_current_user)`; service **không
kiểm quyền gì cả**:

```python
# quotation_service.py:153-157
def get_quotation(db, *, quotation_id):
    q = db.get(Quotation, quotation_id)
    if q is None: raise not_found(...)
    return _serialize(db, q)          # không có tham số `user`
```

Còn các endpoint GHI thì có: `create/update/change_status/delete` đều gọi `_assert_manage(user)`
(`quotation_service.py:36-38, 189, 228`). Tức là **luật tồn tại nhưng chỉ áp cho ghi**.

### So sánh cho thấy đây là lỗi, không phải quyết định

Module `customers` — chứa **cùng loại dữ liệu** — có phân quyền chặt:

```python
# app/routers/customers.py:17-18
read_roles  = require_roles("admin", "leader", "staff", "reception", "lab_manager")  # office CẤM
write_roles = require_roles("admin", "staff", "reception")
```

Báo giá chứa `customer_name`, `customer_address`, `customer_email`, `customer_phone`,
đơn giá từng chỉ tiêu, `subtotal`, `vat_amount`, `total`. Vai trò `office` bị cấm đọc
`customers` nhưng **đọc được toàn bộ dữ liệu đó qua `/quotations`**.

### Kịch bản tấn công

Người dùng `staff`/`qms`/`office` bất kỳ:
```
GET /api/v1/quotations?limit=100&page=1     → toàn bộ danh sách báo giá
GET /api/v1/quotations/{id}/export.xlsx     → file Excel đầy đủ giá + thông tin khách
```
Không cần biết id (list phân trang trả sẵn), không có rate limit trên đường export này.

### Ảnh hưởng

Rò rỉ dữ liệu thương mại (bảng giá thoả thuận với từng khách) và PII khách hàng
(tên, địa chỉ, email, điện thoại người liên hệ). Vi phạm ISO/IEC 17025 §4.2 (bảo mật
thông tin khách hàng).

### Khả năng khai thác

**Cao** — bất kỳ tài khoản hợp lệ nào, 2 lệnh HTTP, không cần biết id trước.

### Khắc phục

```python
# app/routers/quotations.py
quotation_read = require_roles("admin", "leader", "reception", "office")  # theo nghiệp vụ thật
```
và thêm `user` vào `get_quotation`/`list_quotations` để áp phạm vi nếu cần. Áp cả cho
`export.xlsx`, đồng thời thêm `Depends(rate_limit("report-export", ...))` như các export
khác đã có.

### Ưu tiên: **P0**

---

## S-04 · 🟠 HIGH — File `.env.prod.bak.*` chứa secret production KHÔNG được gitignore **[XÁC NHẬN]**

| | |
|---|---|
| **Danh mục** | Secrets Management |
| **Vị trí** | `.gitignore:2`, file `.env.prod.bak.20260729` (untracked, quyền `-rw-------`) |

### Vấn đề

```
$ git check-ignore -v .env.prod .env.prod.bak.20260729
.gitignore:2:.env.prod    .env.prod
                          ← .env.prod.bak.20260729 KHÔNG khớp mẫu nào
```

`.gitignore` chỉ có `.env.prod` (khớp chính xác), không có `.env.prod*` hay `.env*.bak`.
File `.env.prod.bak.20260729` đang nằm trong working tree ở trạng thái **untracked nhưng
không bị ignore** — `git status` liệt kê nó, và `git add -A` / `git add .` sẽ commit nó.

Nội dung (đã kiểm tra không in giá trị): `POSTGRES_PASSWORD`, `REDIS_PASSWORD`,
`MINIO_ROOT_PASSWORD`, `JWT_SECRET` (64 ký tự), `CLOUDFLARE_TUNNEL_TOKEN` (184 ký tự),
`SEED_ADMIN_PASSWORD`, `SMTP_PASSWORD`, `VAPID_PRIVATE_KEY` — **secret production đang
còn hiệu lực**.

Đây không phải giả định: `scripts/init-env-prod.sh` sinh bản sao lưu có dấu thời gian mỗi
lần chạy lại → mỗi lần đổi cấu hình lại tạo thêm một file secret ngoài vòng bảo vệ.

### Vì sao nghiêm trọng đặc biệt với repo này

`.gitleaksignore` ghi rõ repo **đã công khai** và đã từng lộ khoá VAPID:

> *"repo đã public, các commit này đã được clone và lập chỉ mục. `git filter-repo` chỉ làm
> lịch sử của ta sạch chứ không thu hồi được thứ đã phát tán."*

Một lần `git add -A` là lộ toàn bộ hạ tầng: DB, Redis, MinIO, chữ ký JWT (giả mạo được
token của bất kỳ ai, kể cả admin), và **token Cloudflare Tunnel** (dựng được tunnel giả
trỏ vào tên miền).

gitleaks trong CI chỉ chạy **sau khi đã push** — nó phát hiện, không ngăn chặn.

### Khắc phục (ngay)

```gitignore
.env
.env.*
!.env.example
!.env.prod.example
```
Cộng thêm `pre-commit` hook gitleaks chạy **cục bộ** (`CONTRIBUTING.md` nên bắt buộc).
Và xoá/di chuyển các file `.bak` hiện có ra ngoài cây làm việc.

### Ưu tiên: **P0**

---

## S-05 · 🟠 HIGH — Redis là điểm hỏng đơn lẻ của toàn bộ xác thực **[XÁC NHẬN]**

| | |
|---|---|
| **Danh mục** | Availability / Reliability |
| **Vị trí** | `app/core/security.py:95-96`, `app/core/deps.py:59`, `app/services/auth_service.py:39-43` |

### Vấn đề

```python
# security.py:95
def is_jti_denied(jti: str) -> bool:
    return get_redis().exists(jti_denylist_key(jti)) == 1   # ném ConnectionError nếu Redis chết
```

`get_current_user` gọi hàm này cho **mọi request đã xác thực** (`deps.py:59`). Không có
`try/except`. Redis không phản hồi → `redis.exceptions.ConnectionError` → rơi vào
`unhandled_exception_handler` → **HTTP 500 cho 100% API đã đăng nhập**.

`_check_lockout` (`auth_service.py:39-43`) cũng vậy → login cũng 500.

### Bất đối xứng đáng chú ý

Toàn bộ phần còn lại của hệ thống **fail-open** khi Redis lỗi và có comment giải thích:
rate limit (`rate_limit.py:49-54`), RBAC cache (`rbac.py:47-48`), idempotency
(`idempotency.py:62-64`), access-stats, push. Chỉ auth là fail-closed — **và đó là chỗ
duy nhất không có `try/except`, tức là fail-closed do quên chứ không do thiết kế.**

Với `socket_timeout=2s`, Redis treo (chứ không chết hẳn) còn tệ hơn: mỗi request chờ 2s
trước khi 500 → 160 worker-slot bị chiếm → sập dây chuyền.

### Ảnh hưởng

Mất toàn bộ dịch vụ. Redis chạy 1 container, không sentinel, không cluster,
`maxmemory-policy noeviction` + `maxmemory 384mb` → khi Redis đầy, `SET` bị từ chối →
`deny_jti` khi logout ném lỗi.

### Khắc phục

Quyết định **có ý thức** giữa hai lựa chọn và ghi lại lý do:

- **(a) Fail-closed có kiểm soát** (giữ mức bảo mật): bắt exception, trả **503 + `Retry-After`**
  kèm mã lỗi rõ ràng thay vì 500, để client và monitoring phân biệt được "Redis chết" với
  "bug ứng dụng".
- **(b) Fail-open có giới hạn** (giữ tính sẵn sàng): Redis lỗi → bỏ qua kiểm denylist,
  nhưng **rút `ACCESS_TOKEN_TTL_MINUTES` xuống 10 phút** (hiện đã là 10 ở production —
  `docker-compose.prod.yml:210`) và ghi log `SECURITY` mức ERROR + cảnh báo. Cửa sổ rủi ro
  = TTL còn lại của token đã đăng xuất.

Bổ sung: bật Redis persistence đã có AOF ✅, thêm healthcheck alert, cân nhắc Redis Sentinel
nếu SLA yêu cầu.

### Ưu tiên: **P1**

---

## S-06 · 🟡 MEDIUM — Không xác thực chữ ký tệp (magic bytes); chỉ tin `Content-Type` client khai **[XÁC NHẬN]**

**Vị trí:** `app/services/attachment_common.py:44-50`

```python
def check_mime(mime, *, allowed=None):
    if mime is None or mime.lower() not in allowed_set:
        raise unprocessable(...)
```

`mime` đến từ `file.content_type` — **header do client tự đặt**, không phải nội dung tệp.
Không có kiểm magic bytes, không có kiểm phần mở rộng, không có antivirus.

**Khai thác:** upload `payload.html` (hoặc `.exe`, `.svg`) với header
`Content-Type: application/pdf` → lưu vào MinIO với `ContentType: application/pdf`
(`storage_service.py:89-94`).

**Giới hạn thiệt hại (đã có phòng vệ):**
- Presigned URL luôn kèm `ResponseContentDisposition: attachment` trừ khi mime nằm trong
  allowlist inline (`attachment_service.py:58-60`, `attachment_common.py:63-72`) → chặn
  stored-XSS. Phòng vệ này đúng và có chủ đích.
- `SecurityHeadersMiddleware` đặt `X-Content-Type-Options: nosniff` cho response API —
  **nhưng KHÔNG áp cho `location /lims-attachments/`** trong nginx (`nginx.conf:33-41`).

**Ảnh hưởng thực tế:** malware phát tán trong nội bộ (người dùng tải "báo cáo.pdf" là file
thực thi), và tính toàn vẹn hồ sơ ISO 17025 (bản ghi được khai sai loại).

**Khắc phục:** kiểm magic bytes (`python-magic` hoặc bảng signature tự viết cho 8 loại đã
allowlist), đối chiếu với `Content-Type` khai báo và phần mở rộng; thêm
`add_header X-Content-Type-Options nosniff always;` vào `location /lims-attachments/`.

**Ưu tiên: P1**

---

## S-07 · 🟡 MEDIUM — SSRF mù qua endpoint đăng ký Web Push **[XÁC NHẬN]**

**Vị trí:** `app/schemas/push.py:10-14`, `app/routers/push.py:20-35`, `app/services/push_service.py:132-141`

```python
class PushSubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2048)   # không kiểm scheme/host
```

Server lưu URL này rồi **tự POST tới đó** mỗi khi có thông báo (`push_service.py:132`),
từ bên trong docker network.

**Khai thác:** người dùng đã đăng nhập gửi
`{"endpoint": "http://minio:9000/lims-attachments/", "keys": {...}}` → mỗi notification
sinh một POST tới dịch vụ nội bộ. Đích khả dụng: `minio:9000`, `lims-api:8060`,
`lims-web:80`, `169.254.169.254` (metadata cloud nếu chạy trên VM cloud), bất kỳ host nào
trong LAN.

**Giới hạn:** SSRF **mù** — response không trả về cho kẻ tấn công; body là payload đã mã
hoá theo VAPID; timeout 5s; cần tài khoản hợp lệ. Không đọc được dữ liệu, nhưng dò được
port (qua thời gian phản hồi/log) và kích hoạt được các endpoint nội bộ nhận POST.

**Khắc phục:** allowlist host push service hợp lệ:
```python
_ALLOWED_PUSH_HOSTS = {"fcm.googleapis.com", "updates.push.services.mozilla.com",
                       "web.push.apple.com", "wns2-*.notify.windows.com"}
```
bắt buộc `https://`, từ chối IP literal và địa chỉ private/link-local sau khi phân giải DNS.

**Ưu tiên: P1**

---

## S-08 · 🟡 MEDIUM — Lockout khoá theo (email, IP) → credential stuffing phân tán không bị chặn **[XÁC NHẬN]**

**Vị trí:** `app/core/redis_client.py:34-39`, `app/services/auth_service.py:60-69, 127-132`

```python
def login_fail_key(email, ip=None): return f"login:fail:{email.lower()}:{ip or 'noip'}"
```

Bộ đếm sai mật khẩu và bộ rate-limit `login_identity` (10 lần/5 phút) **đều gắn IP vào
khoá**. Kẻ tấn công dùng 100 IP (botnet/proxy rẻ tiền) có **100 × 5 = 500 lần thử** cho
**mỗi tài khoản** mà không chạm ngưỡng nào.

Rate limit thuần IP ở tầng router là 300/phút (`auth.py:58`) — cố tình nới rộng vì cả viện
đi chung một IP NAT. Nên không có lớp nào giới hạn theo **tài khoản trên toàn hệ thống**.

**Đây là đánh đổi có chủ ý được ghi trong `redis_client.py:32-33`** (chống DoS nhắm nạn
nhân: kẻ tấn công không khoá được tài khoản người khác). Đánh đổi hợp lý, nhưng **hiện chỉ
có một vế** — thiếu vế thứ hai.

**Khắc phục:** thêm bộ đếm **thứ hai** theo email toàn cục với ngưỡng cao và hành vi mềm:
- `login:fail:global:{email}` — 30 lần/giờ → **không khoá tài khoản** (tránh DoS), mà bật
  yêu cầu CAPTCHA / delay tăng dần (exponential backoff) / cảnh báo cho admin + gửi mail
  cho chủ tài khoản.
- Ghi metric `authentication_failures_total{email_hash}` để cảnh báo phát hiện.

**Ưu tiên: P1**

---

## S-09 · 🔵 LOW — nginx tin `CF-Connecting-IP` vô điều kiện (an toàn với tunnel, hở nếu chạy sai profile) **[RỦI RO CÓ ĐIỀU KIỆN]**

> **ĐÍNH CHÍNH 2026-08-07:** bản đầu của tài liệu này xếp S-09 ở mức MEDIUM/P1 và đề xuất
> `set_real_ip_from` với **dải IP công khai của Cloudflare**. Sau khi kiểm tra triển khai
> thực tế: (a) mức đúng là **LOW**, (b) **khuyến nghị đó SAI với kiến trúc tunnel và sẽ
> làm hỏng nhật ký IP nếu áp dụng** — giải thích ở mục "Khắc phục" bên dưới.

**Vị trí:** `lims-frontend/nginx.conf:20-21`

```nginx
set $real_client $remote_addr;
if ($http_cf_connecting_ip) { set $real_client $http_cf_connecting_ip; }
proxy_set_header X-Real-IP       $real_client;
proxy_set_header X-Forwarded-For $real_client;
```

nginx tin `CF-Connecting-IP` mà **không kiểm `$remote_addr` có phải hop tin cậy hay không**.

### Vì sao KHÔNG khai thác được với triển khai hiện tại

Xác minh trên máy chủ đang chạy (2026-08-07):

```
$ docker ps
lims-web           lims-lims-web                   80/tcp          ← KHÔNG có ánh xạ ra host
lims-cloudflared   cloudflare/cloudflared:2025.2.1                 ← chỉ kết nối ra ngoài
(đối chiếu: tmdt-postgres  0.0.0.0:5432->5432/tcp  ← đây mới là cổng đã publish)

$ docker network inspect lims_default
lims-cloudflared 172.22.0.3 · lims-web 172.22.0.2 · lims-api 172.22.0.5
lims-postgres 172.22.0.6 · lims-redis 172.22.0.4 · lims-minio 172.22.0.7
(6 container LIMS + cloudflared; các project khác trên cùng host nằm ở mạng riêng)
```

Nghĩa là overlay `docker-compose.cloudflare.yml` đang hoạt động (`ports: !reset []`), và:

1. **Không ai gọi thẳng nginx được.** Đường vào duy nhất là `cloudflared`, và cloudflared
   chỉ kết nối **hướng ra** tới biên Cloudflare — không lắng nghe cổng nào.
2. **`CF-Connecting-IP` không phải header pass-through.** Biên Cloudflare **ghi đè** nó
   bằng IP thật của client trên mọi request. Client tự đặt header này thì giá trị bị thay
   thế trước khi vào tunnel.

→ Với topology hiện tại, cấu hình `if ($http_cf_connecting_ip)` là **đúng và tin cậy được**.
Đây là lý do hạ từ MEDIUM xuống LOW.

### Rủi ro còn lại — và nó là rủi ro VẬN HÀNH, không phải mã nguồn

Phòng vệ phụ thuộc hoàn toàn vào việc **luôn ghép đủ 2 file compose**. Và tài liệu vận
hành của chính dự án lại không làm thế:

```
$ grep -c "cloudflare.yml" ops/RUNBOOK.md
0
```

`ops/RUNBOOK.md` có **15 lệnh** dùng `docker compose -f docker-compose.prod.yml` mà **không
có overlay**, trong đó có thủ tục rollback ở dòng 149:

```bash
docker compose -f docker-compose.prod.yml up -d --build      # ← RUNBOOK §6 Rollback
```

Chạy đúng lệnh này — vào đúng lúc căng thẳng nhất, khi đang rollback một bản deploy lỗi —
sẽ **dựng lại `lims-web` với `ports: "3060:80"` và không có `cloudflared`**. Khi đó:

- Cổng 3060 mở trên host → ai trong LAN cũng gửi được `CF-Connecting-IP: 1.2.3.4` tự chọn.
- Né mọi rate limit theo IP; làm giả `audit_logs.ip` và `access_stats.ip`; vô hiệu hoá
  lockout đăng nhập (khuếch đại S-08).
- Và tệ hơn: **tunnel biến mất** → hệ thống offline với người dùng thật.

`DEPLOY_LINUX.md` thì làm đúng (dòng 275 và 360 đều export biến/alias có đủ 2 file).
`scripts/preflight-deploy.sh:171` cũng in ra lệnh đúng. Chỉ RUNBOOK lệch.

### Khắc phục

**1. Sửa `ops/RUNBOOK.md`** (đây mới là việc cần làm, ưu tiên P2):
```bash
# Đặt ở đầu RUNBOOK, dùng cho MỌI lệnh phía dưới
alias limsc='docker compose -f /opt/lims/docker-compose.prod.yml \
                            -f /opt/lims/docker-compose.cloudflare.yml \
                            --env-file /opt/lims/.env.prod'
```
Thay toàn bộ 15 chỗ `docker compose -f docker-compose.prod.yml` bằng `limsc`.
Alias này **đã tồn tại** ở `DEPLOY_LINUX.md:360` — chỉ cần dùng nhất quán.

**2. KHÔNG dùng `set_real_ip_from` với dải IP công khai của Cloudflare.**
Với tunnel, `$remote_addr` mà nginx thấy là **IP container của `cloudflared` (172.22.0.3)**,
không bao giờ là IP biên Cloudflare. `set_real_ip_from 173.245.48.0/20;` sẽ **không bao giờ
khớp** → module `real_ip` không kích hoạt → `X-Real-IP` rơi về IP container → tái tạo đúng
lỗi mà `app/core/request_meta.py` được viết ra để sửa (docstring của nó ghi nhận
545/1.442 dòng `audit_logs` từng ghi `172.21.0.6`).

Nếu vẫn muốn siết ở tầng nginx thì hop tin cậy phải là **mạng docker**, không phải Cloudflare:
```nginx
set_real_ip_from 172.22.0.0/16;      # chỉ cloudflared tới được nginx trong topology này
real_ip_header   CF-Connecting-IP;
```
Nhưng lợi ích thêm là **rất nhỏ** so với việc sửa RUNBOOK: nếu ai đó chạy sai profile,
mạng docker vẫn là 172.x nên `set_real_ip_from` vẫn khớp và vẫn tin header. **Biện pháp
có tác dụng thật là (1) và (3).**

**3. Gỡ `ports: "3060:80"` khỏi `docker-compose.prod.yml`**, chuyển sang một overlay riêng
(`docker-compose.lan.yml`) cho trường hợp cần truy cập LAN. Mặc định phải an toàn: chạy
thiếu file không được biến thành mở cổng.

**Ưu tiên: P2** (hạ từ P1 — không khai thác được với triển khai hiện tại)

---

## S-10 · 🟡 MEDIUM — `/health/ready` trả nguyên văn thông báo lỗi hạ tầng **[RỦI RO]**

**Vị trí:** `app/routers/health.py:25-69`

```python
errors["db"] = _truncate(str(exc))       # 200 ký tự đầu của exception
errors["redis"] = _truncate(str(exc))
errors["minio"] = _truncate(str(exc))
```

`psycopg2.OperationalError` thường chứa host/port/user/tên database;
`botocore.ClientError` chứa endpoint URL và mã lỗi credential.

**Giới hạn thiệt hại:** nginx **không có `location /health`** → endpoint này không tiếp cận
được từ Internet, chỉ trong docker network. Vì vậy xếp MEDIUM chứ không HIGH.

Nhưng cùng sự thật đó tạo ra một vấn đề vận hành nặng hơn — xem S-11.

**Khắc phục:** phân tách rõ:
- `/health` — liveness, không đụng phụ thuộc (đã đúng).
- `/health/ready` — trả `{"status": "degraded", "checks": {...}}` **không kèm `errors`**;
  trả **HTTP 503** khi degraded (hiện luôn trả 200, khiến LB/orchestrator không dùng được).
- `/health/detail` — có `errors`, **yêu cầu xác thực admin** hoặc chỉ bind localhost.

**Ưu tiên: P2**

---

## S-11 · 🟡 MEDIUM — Quy trình xác minh go-live luôn "xanh" kể cả khi backend đã chết **[XÁC NHẬN]**

**Vị trí:** `lims-frontend/nginx.conf` (thiếu `location /health`), `DEPLOY_LINUX.md:292-293, 378, 419, 457`

nginx chỉ proxy `/api/` và `/lims-attachments/`. Mọi path khác rơi vào
`try_files $uri $uri/ /index.html` → trả **200 + HTML của SPA**.

`DEPLOY_LINUX.md` hướng dẫn xác minh sau deploy:
```bash
curl -fsS https://lims.tenmien.com/health && echo
curl -fsS https://lims.tenmien.com/health/ready && echo   # "kiểm cả DB, Redis, MinIO"
```
và checklist dòng 457: `[ ] https://lims.tenmien.com/health/ready → 200`.

**Cả ba lệnh này trả 200 với nội dung `<!doctype html>` ngay cả khi `lims-api` không chạy.**
`curl -fsS` chỉ fail khi HTTP ≥ 400, nên nó thành công. Người vận hành tick vào checklist
và tin rằng backend + DB + Redis + MinIO đều khoẻ.

Đây là **kiểm tra an toàn giả** — nguy hiểm hơn không có kiểm tra, vì nó tạo niềm tin sai.

**Khắc phục:**
```nginx
location = /health       { proxy_pass http://lims-api:8060/health; }
location = /health/ready { proxy_pass http://lims-api:8060/health/ready; }
```
(kèm S-10: `/health/ready` không được lộ `errors` ra ngoài, hoặc chỉ mở `/health`).
Và sửa checklist thành kiểm tra có xác nhận nội dung:
`curl -fsS https://.../health | grep -q '"status":"ok"'`.

**Ưu tiên: P1**

---

## S-12 · 🟡 MEDIUM — Chính sách mật khẩu yếu, không kiểm mật khẩu lộ **[XÁC NHẬN]**

**Vị trí:** `app/schemas/auth.py:9, 25, 41, 69`

```python
_PWD_STRENGTH = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).+$")   # chỉ cần 1 chữ + 1 số
new_password: str = Field(min_length=8, max_length=128)
```

`Password1`, `12345678a`, `lims2026` đều hợp lệ. Không kiểm danh sách mật khẩu phổ biến,
không kiểm trùng với email/tên, không có lịch sử mật khẩu (đổi mật khẩu chỉ cấm trùng
**mật khẩu hiện tại** — `auth_service.py:382-386`).

Kết hợp S-08 (không giới hạn theo tài khoản toàn cục), đây là đường vào khả thi nhất.

**Bổ sung (LOW, gộp vào đây):** bcrypt cắt cụt input ở **72 byte**. `max_length=128` cho
phép người dùng nhập passphrase 100 ký tự và tin rằng nó mạnh hơn, trong khi 56 ký tự cuối
bị bỏ. Nên hoặc hạ `max_length=72`, hoặc pre-hash SHA-256 trước bcrypt.

**Khắc phục:** tối thiểu 12 ký tự cho tài khoản mới; chặn danh sách 10.000 mật khẩu phổ
biến (offline, không cần gọi API); chặn mật khẩu chứa local-part của email.

**Ưu tiên: P2**

---

## S-13 · 🟡 MEDIUM — Đọc hồ sơ nhân sự dùng danh sách CẤM thay vì danh sách CHO PHÉP **[XÁC NHẬN]**

**Vị trí:** `app/services/hr_service.py:185-190`

```python
def get_profile(db, *, user, target_user_id):
    if user.role == "staff" and user.id != target_user_id:
        raise hc.forbidden("Bạn chỉ được xem hồ sơ của chính mình")
```

Hệ thống có **7 vai trò**: `admin, leader, office, staff, reception, qms, lab_manager`
(`app/schemas/user.py:9-11`). Điều kiện chỉ chặn `staff` → `reception`, `qms`,
`lab_manager` đọc được hồ sơ nhân sự **của bất kỳ ai**.

Nhóm lương/hợp đồng/PII vẫn bị strip đúng (`hc.strip_profile` — `hr_common.py:119-138`),
nên phần rò rỉ giới hạn ở: họ tên, email, phòng ban, chức danh, ngày vào làm, điện thoại,
vị trí. Không phải thảm hoạ, **nhưng cơ chế thì sai**: mỗi vai trò mới thêm vào hệ thống
sẽ **mặc định có quyền** thay vì mặc định bị từ chối.

Cùng dạng lỗi ở `attachment_service._check_owner_read_permission` (S-01) — cả hai đều là
denylist. Đây là mẫu lặp lại, không phải sự cố đơn lẻ.

**Khắc phục:** đảo thành allowlist:
```python
if user.id != target_user_id and user.role not in ("admin", "leader", "office"):
    raise hc.forbidden(...)
```

**Ưu tiên: P2**

---

## S-14 · 🔵 LOW — `get_current_user` chỉ chặn `status == "disabled"`

`app/core/deps.py:71-72`. Cột `users.status` có 3 giá trị hợp lệ (`active|disabled|pending`).
Kiểm tra hiện tại là denylist: bất kỳ trạng thái mới nào (`suspended`, `locked`, …) sẽ
**mặc định được phép**. Hiện chưa khai thác được vì `pending` không đăng nhập được
(`auth_service.py:163-175`), nhưng cùng mẫu lỗi với S-13.
→ Đổi thành `if user.status != "active": raise ...`.

## S-15 · 🔵 LOW — `python-jose` 3.3.0 và `passlib` 1.7.4 đều đã ngừng bảo trì

- `python-jose==3.3.0` (2021): CVE-2024-33663 (algorithm confusion), CVE-2024-33664
  (JWE decompression bomb). **Không khai thác được ở đây**: `decode_access_token` truyền
  `algorithms=[settings.jwt_algorithm]` = `["HS256"]` cố định (`security.py:69`) → chặn
  algorithm confusion; hệ thống không dùng JWE. Rủi ro thực tế: thấp. Rủi ro tồn kho: dự
  án không còn phát hành bản vá.
- `passlib==1.7.4` (2020): không tương thích `bcrypt>=4.1` — chính vì thế `bcrypt` bị ghim
  ở `4.0.1`. Cả hai đều đóng băng.
- `ecdsa` (transitive của `python-jose[cryptography]`): CVE-2024-23342 (Minerva timing).
  Không dùng ECDSA ở đây.

→ Chuyển sang `pyjwt` + `argon2-cffi` (hoặc `bcrypt` trực tiếp) trong một sprint riêng, có
kế hoạch di trú hash. Không gấp, nhưng đừng để quên.

## S-16 · 🔵 LOW — Container thiếu hardening cơ bản

`docker-compose.prod.yml`: không có `security_opt: [no-new-privileges:true]`, không
`cap_drop: [ALL]`, không `read_only: true` + `tmpfs`. Image `minio/minio:**latest**`
(`:93`) — tag động, bản build khác nhau giữa các lần deploy, không tái lập được.
Backend đã chạy non-root ✅ (`Dockerfile:23-25`); `lims-web` (nginx) master process vẫn root.

## S-17 · 🔵 LOW — `/metrics` không xác thực

`app/main.py:172-174`. Lộ route template, phân bố status code, độ trễ, trạng thái cron.
Hiện không tiếp cận được từ ngoài (nginx không proxy). Nếu sau này thêm scrape từ xa, phải
bảo vệ bằng network policy hoặc basic auth.

## S-18 · 🔵 LOW — Ứng dụng kết nối Postgres bằng chính user sở hữu schema

`DATABASE_URL` dùng `lims` — cũng là `POSTGRES_USER` và owner của mọi bảng
(`docker-compose.prod.yml:46, 182`). User này **DROP được trigger append-only** bảo vệ
`audit_logs`, `calibration_records`, `capa`. Với ISO/IEC 17025, tính bất biến của nhật ký
kiểm toán là yêu cầu; một RCE hoặc SQL injection trong tương lai sẽ vô hiệu hoá nó.
→ Tách vai trò: `lims_migrate` (owner, chỉ dùng bởi service `migrate`) và `lims_app`
(chỉ `SELECT/INSERT/UPDATE/DELETE` trên bảng nghiệp vụ, không `TRIGGER`, không `DDL`).

## S-19 · 🔵 LOW — `.env.prod` khai `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY` hai lần

Lần đầu là placeholder `CHANGE_ME` (9 ký tự), lần sau là khoá thật. Docker Compose lấy giá
trị cuối nên hiện chạy đúng, nhưng đây là loại nhầm lẫn dễ gây sự cố khi ai đó sắp xếp lại
file. → `scripts/init-env-prod.sh` nên **thay thế** biến tại chỗ thay vì nối thêm.

---

## S-20…S-23 · ⚪ INFO

- **S-20** — Không có CSRF token. **Đúng và không cần**: API dùng Bearer token trong header
  (không tự động gửi kèm), cookie refresh có `SameSite=Strict` + `Path=/api/v1/auth`, CORS
  dùng allowlist tường minh từ `CORS_ORIGINS`. Ghi lại để không ai "sửa" nhầm.
- **S-21** — CORS: `allow_origins=settings.cors_origin_list` (allowlist), `allow_credentials=True`,
  `allow_methods/headers=["*"]`. Không có wildcard origin. ✅ Đúng.
  Lưu ý: `allow_headers=["*"]` với `allow_credentials=True` là hợp lệ trong Starlette nhưng
  nên liệt kê tường minh để bản đặc tả rõ ràng hơn.
- **S-22** — Không log secret: `audit_service._sanitize` lọc 10 khoá nhạy cảm
  (`audit_service.py:17-29`); `logging_config.JsonFormatter` merge `record.__dict__` nên
  **phụ thuộc call-site không truyền password vào `extra`** — hiện không chỗ nào truyền.
  Log injection: log là JSON một dòng (`json.dumps`), ký tự xuống dòng bị escape → không
  chèn được dòng log giả. ✅
- **S-23** — Chống user enumeration làm rất kỹ: hash bcrypt "mồi" để cân bằng thời gian
  (`auth_service.py:35, 141`), thông điệp chung cho `register`/`forgot-password`, chỉ báo
  trạng thái `pending`/`disabled` **sau khi** mật khẩu đã đúng. Trên mức trung bình ngành.

---

## Phụ lục A — Những gì đã KIỂM và KHÔNG tìm thấy vấn đề

| Hạng mục | Kết quả |
|---|---|
| SQL injection | ❌ Không có. 0 chuỗi SQL nối động; `text()` chỉ dùng cho `SELECT 1`, `server_default`, và 2 câu DELETE theo lô có bind param (`cleanup_service.py:64-71, 86-92`) |
| NoSQL / command injection | ❌ Không có NoSQL; không `subprocess`/`os.system` trên input người dùng |
| Deserialization không an toàn | ❌ Không `pickle`, không `yaml.load`, không `eval`/`exec` (chỉ `redis.eval` — Lua script cố định, `scheduler.py:81`) |
| Path traversal (tên file) | ❌ `_sanitize_file_name` dùng **allowlist** `[A-Za-z0-9._-]`, strip `._`, cắt 120 ký tự (`storage_service.py:73-80`). Chặn cả null byte, CR/LF (header injection ở Content-Disposition). Có test riêng: `test_storage_sanitize.py` |
| Endpoint quên xác thực | ❌ Không có. Đã quét 296 route; allowlist công khai 14 đường dẫn đều có lý do chính đáng (`test_idor_routes.py:26-41`) |
| Mass assignment | ❌ Không tìm thấy đường khai thác. `UpdateIntakeRequest` có `extra="forbid"` (`sample_flow.py:51`); `UpdateEquipmentRequest` dùng `extra="allow"` **có chủ đích** nhưng service xử lý từng field tường minh (`equipment_service.py:322+`) và chặn `code`/`department_id` |
| Leo thang đặc quyền qua self-service | ❌ `RegisterRequest` `extra="forbid"`, không nhận `role`/`department_id`; tài khoản luôn vào `pending`; admin gán vai trò lúc duyệt (`account_service.py:43-45, 175-184`) |
| `UpdateMeRequest` | ❌ Chỉ `full_name` + `email`, `extra="forbid"` (`auth.py:87-94`) |
| Token đặt lại mật khẩu | ❌ 48 byte ngẫu nhiên, DB lưu SHA-256, dùng-một-lần, vô hiệu token cũ khi phát hành mới, TTL 30 phút, thu hồi mọi phiên sau khi reset (`account_service.py:52-105, 306-349`) |
| Stack trace ra client | ❌ `unhandled_exception_handler` log stack ở BE, trả `{"code":"INTERNAL_ERROR"}` (`exceptions.py:131-149`). `/docs`, `/redoc`, `/openapi.json` tắt ở production (`main.py:129-130`) |
| Timing attack đăng nhập | ❌ Đã xử lý bằng hash mồi |
| Race trên refresh token | ❌ `with_for_update()` (`auth_service.py:244`) |
| Race trên tồn kho hoá chất | ❌ `SELECT ... FOR UPDATE` trên lô (`chemical_txn_service.py:127`) |

## Phụ lục B — Bảng tổng hợp

| ID | Mức | Danh mục | Loại | Vị trí | Ưu tiên |
|---|---|---|---|---|---|
| S-01 | 🟠 HIGH | BOLA (đọc) | XÁC NHẬN | `attachment_service.py:22-63` | P0 |
| S-02 | 🟠 HIGH | BOLA (ghi) | XÁC NHẬN | `attachment_service.py:106-163` | P0 |
| S-03 | 🟠 HIGH | BFLA + lộ dữ liệu | XÁC NHẬN | `quotation_service.py:130-158` | P0 |
| S-04 | 🟠 HIGH | Secrets | XÁC NHẬN | `.gitignore:2` | P0 |
| S-05 | 🟠 HIGH | Availability | XÁC NHẬN | `security.py:95`, `deps.py:59` | P1 |
| S-06 | 🟡 MEDIUM | Upload | XÁC NHẬN | `attachment_common.py:44` | P1 |
| S-07 | 🟡 MEDIUM | SSRF | XÁC NHẬN | `push.py:11`, `push_service.py:132` | P1 |
| S-08 | 🟡 MEDIUM | Brute-force | XÁC NHẬN | `redis_client.py:34-39` | P1 |
| S-09 | 🔵 LOW | Spoofing IP | RỦI RO CÓ ĐK | `nginx.conf:20-21` + `ops/RUNBOOK.md` | P2 |
| S-10 | 🟡 MEDIUM | Lộ thông tin | RỦI RO | `health.py:35-52` | P2 |
| S-11 | 🟡 MEDIUM | Xác minh giả | XÁC NHẬN | `nginx.conf`, `DEPLOY_LINUX.md:292` | P1 |
| S-12 | 🟡 MEDIUM | Chính sách mật khẩu | XÁC NHẬN | `schemas/auth.py:9` | P2 |
| S-13 | 🟡 MEDIUM | Denylist RBAC | XÁC NHẬN | `hr_service.py:185-190` | P2 |
| S-14 | 🔵 LOW | Denylist status | XÁC NHẬN | `deps.py:71` | P2 |
| S-15 | 🔵 LOW | Dependency | KHUYẾN NGHỊ | `requirements.txt` | P3 |
| S-16 | 🔵 LOW | Container | KHUYẾN NGHỊ | `docker-compose.prod.yml` | P2 |
| S-17 | 🔵 LOW | Observability | KHUYẾN NGHỊ | `main.py:172` | P3 |
| S-18 | 🔵 LOW | Least privilege DB | KHUYẾN NGHỊ | `docker-compose.prod.yml:182` | P2 |
| S-19 | 🔵 LOW | Cấu hình | XÁC NHẬN | `.env.prod` | P3 |
