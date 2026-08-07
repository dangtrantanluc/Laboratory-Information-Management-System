# API AUDIT — LIMS Backend

> 296 endpoint / 39 router module. Prefix `/api/v1` (trừ `/health`, `/health/ready`, `/metrics`).
> Mã phát hiện: `API-xx`.

---

## 1. Tổng quan bề mặt API

| Router | Số EP | Cơ chế phân quyền chính | Ghi chú |
|---|---:|---|---|
| `research.py` | 31 | `get_current_user` + `_guard()` trong router | Lớn nhất; 741 dòng |
| `sample_flow.py` | 21 | `require_permission("intake", ...)` ✅ | Tốt nhất về khai báo quyền |
| `documents.py` | 21 | `get_current_user` + luật ở `document_common` ✅ | RBAC sâu, có mức bảo mật |
| `forms.py` | 17 | `require_permission("form", ...)` ✅ | |
| `samples.py` | 17 | `get_current_user` + `sample_common` | |
| `auth.py` | 16 | hỗn hợp (public + self) | |
| `chemicals.py` | 16 | `get_current_user` + `chemical_common` + strip giá | |
| `hr_profiles.py` | 15 | `require_roles` (1 EP) + field-level strip | Xem API-03 |
| `activities.py` | 12 | `get_current_user` + `_assert_contract_read` | |
| `reporting.py` | 11 | `get_current_user` + `require_audit_read` | |
| `nonconformities.py` | 10 | `get_current_user` + `nc_common` | |
| `users.py` | 9 | `require_roles("admin")` ✅ | |
| `equipments.py` | 9 | `get_current_user` + `equipment_common` | |
| `quotations.py` | 8 | ⚠️ chỉ ghi có kiểm | **API-01** |
| `risks.py` | 8 | `get_current_user` + `risk_common` | |
| `test_requests.py` | 8 | `get_current_user` | |
| `chemical_lots.py` | 6 | `get_current_user` | |
| `notifications.py` | 5 | STRICT SELF ✅ | Chuẩn mực |
| `activity_reports.py` | 5 | `get_current_user` | |
| `results.py` | 5 | `get_current_user` | |
| `customers.py`, `departments.py`, `lab_access.py`, `hr_catalogs.py`, `improvements.py` | 4 mỗi | `require_roles` / `require_permission` ✅ | |
| `rbac.py`, `push.py`, `assignments.py` | 3 mỗi | | |
| `attachments.py` | 2 | ⚠️ gần như không có | **API-02** (= S-01/S-02) |
| `audit_logs.py` | 2 | `require_roles("admin","leader")` ✅ | |
| `calibrations.py`, `health.py`, `hr_crons.py`, `sample_crons.py` | 2 mỗi | | |
| `*_crons.py` (5 file) | 1 mỗi | `admin_only` ✅ | |
| `sample_reports.py` | 1 | `get_current_user` | |

**Kết quả quét tự động (`app/tests/security/test_idor_routes.py`):**
100% route có tham số `{id}` và 100% route ghi đều có dependency xác thực, ngoại trừ 14
đường dẫn trong allowlist công khai — tất cả đều chính đáng (login, refresh, register,
verify-email, forgot/reset-password, registration-config, health, metrics, docs).

→ **Không có endpoint nào quên xác thực.** Vấn đề nằm ở tầng **uỷ quyền cấp đối tượng**,
không phải xác thực.

---

## 2. Ma trận đánh giá theo tiêu chí

| Tiêu chí | Trạng thái | Bằng chứng |
|---|---|---|
| **Authentication** | ✅ Đầy đủ | 296/296, có test tự động chống hồi quy |
| **Authorization (function level)** | ⚠️ Không đồng nhất | 3 cơ chế song song: `require_roles`, `require_permission` (tra bảng), và kiểm thủ công trong service. Xem API-04 |
| **Authorization (object level)** | ❌ Có lỗ hổng | `/attachments/{id}`, `/quotations/{id}` — xem API-01, API-02 |
| **Input validation** | ✅ Tốt | Pydantic khắp nơi; `Query(..., ge=, le=, max_length=)` nhất quán; `Email` type tự lowercase |
| **Output schema** | ⚠️ Không khai báo | Xem API-05 |
| **Error handling** | ✅ Tốt | 4 handler toàn cục, format `{success, error:{code, message, details, correlationId}}` thống nhất; có test kiến trúc (`test_response_contract.py`) |
| **Status code** | ✅ Đúng | 201 cho create, 204 cho delete, 409 conflict, 422 nghiệp vụ, 423 locked, 429 rate limit |
| **Pagination** | ⚠️ Có lỗ hổng | Xem API-06 |
| **Filtering/Sorting** | ⚠️ Hạn chế | Filter theo query param tường minh (an toàn — không có `order_by` động từ client). Chỉ `documents.py:78 sort_by` nhận chuỗi, nhưng so khớp bằng `if/elif` (`document_service.py:665-669`) → an toàn |
| **Rate limiting** | ⚠️ Chỉ 8/296 EP | Xem API-07 |
| **Idempotency** | ⚠️ Opt-in, không EP nào bắt buộc | Xem API-08 |
| **Transaction** | ⚠️ Do service tự quyết (166 `db.commit()`) | Xem DATABASE_AUDIT D-01 |
| **Logging/Audit** | ✅ Tốt | Mọi thao tác CUD gọi `audit_service.log_action` trong cùng transaction |
| **Sensitive data exposure** | ⚠️ Có | API-01; field-level strip đã có ở HR (`strip_profile`) và hoá chất (`strip_price_fields`) nhưng không áp cho báo giá |

---

## 3. Phát hiện

### API-01 · 🟠 HIGH — `/quotations` đọc không kiểm quyền

Xem SECURITY_AUDIT **S-03**. Tóm tắt: `GET /quotations`, `GET /quotations/{id}`,
`GET /quotations/{id}/export.xlsx` chỉ có `get_current_user`; `quotation_service.get_quotation`
thậm chí **không nhận tham số `user`** (`quotation_service.py:153`). Ghi thì có `_assert_manage`.
Rò rỉ PII khách hàng + bảng giá cho mọi tài khoản.

### API-02 · 🟠 HIGH — `/attachments` không có uỷ quyền cấp đối tượng

Xem SECURITY_AUDIT **S-01** (đọc) và **S-02** (ghi).

### API-03 · 🟡 MEDIUM — Phân quyền HR khai ở 2 nơi không khớp nhau

`GET /hr-profiles` (list) dùng `require_roles("admin","leader","office")` ở tầng router
(`hr_profiles.py:50`). Nhưng **14 endpoint HR còn lại** chỉ có `get_current_user` và dựa
hoàn toàn vào kiểm tra trong service:

| Endpoint | Kiểm ở service | Cơ chế |
|---|---|---|
| `GET /hr-profiles/{user_id}` | `if user.role == "staff" and ...` | ❌ denylist (S-13) |
| `PATCH /hr-profiles/{user_id}` | `assert_can_manage_profile` | ✅ allowlist |
| `PATCH /.../contract` | `assert_can_edit_salary` | ✅ |
| `POST /.../salary-raises` | `assert_can_edit_salary` | ✅ |
| `GET /.../salary-history` | `can_read_salary` | ✅ |
| `GET /.../competences` | `_assert_competence_read` | ✅ |
| `POST /competences/{id}/attachments` | `assert_can_manage_competence` ở **router** (`hr_profiles.py:308`) | ⚠️ lệch tầng |

Hệ quả: người đọc code không biết endpoint nào được bảo vệ ở đâu, và endpoint mới rất dễ
bị quên. Nên chuẩn hoá về **một tầng duy nhất** (khuyến nghị: `require_permission` ở router
cho quyền chức năng, service chỉ kiểm phạm vi đối tượng).

### API-04 · 🟡 MEDIUM — Ba cơ chế phân quyền song song

| Cơ chế | Nơi khai | Số router dùng | Ưu / nhược |
|---|---|---|---|
| `require_permission(resource, action)` | router, tra bảng `roles_permissions` | 3 (`forms`, `sample_flow`, `lab_access`) | ✅ Sửa ma trận quyền không cần deploy. Đây là thiết kế được nêu trong tài liệu (D4) |
| `require_roles(...)` | router, hardcode vai trò | ~8 | ⚠️ Đổi quyền = sửa code + deploy |
| Kiểm thủ công trong service | service | ~28 | ⚠️ Không thấy được từ OpenAPI; không quét tự động được |

Ba cơ chế cùng tồn tại là hợp lý ở giai đoạn chuyển đổi, nhưng hiện **không có tài liệu nào
nói module nào dùng cơ chế nào**, và không có test nào kiểm tính đầy đủ của ma trận
`roles_permissions` với các resource mới. Nếu ai đó xoá một dòng trong bảng
`roles_permissions`, 3 router kia mất quyền âm thầm (`find_permission` trả `None` → 403)
và cache Redis giữ trạng thái đó 5 phút.

### API-05 · 🟡 MEDIUM — Không khai báo `response_model`

Không endpoint nào dùng `response_model=`. Tất cả trả `dict` qua helper `ok()`/`paginated()`.
Hệ quả:

1. **OpenAPI không có schema response** → client (SPA) không sinh type được, mọi thay đổi
   shape là breaking change ngầm.
2. **Không có lưới chắn chống lộ field.** Serializer viết tay (`_profile_dict`,
   `_serialize_intake`, `_txn_dict`, …) trả nguyên dict; thêm một cột nhạy cảm vào model và
   quên sửa serializer sẽ lộ ngay. Hiện đã có `strip_profile` và `strip_price_fields` bù
   lại ở 2 module, nhưng đó là phòng vệ theo module chứ không phải theo nền tảng.

Với 296 endpoint, thêm `response_model` toàn bộ là việc lớn. Khuyến nghị: áp cho các
endpoint chạm dữ liệu nhạy cảm trước (HR, quotation, customer, audit, document).

### API-06 · 🟡 MEDIUM — Phân trang: 3 khiếm khuyết

1. **Phân trang trong bộ nhớ (offset giả).**
   `document_version_service.list_versions:53-70` — `SELECT` **toàn bộ** version của tài
   liệu, lọc bằng Python, rồi `visible[start:start+limit]`. Với tài liệu có nhiều phiên
   bản thì tải hết về app. Cùng mẫu ở `hr_service.list_competences` (không phân trang) và
   `chemical` FEFO.

2. **Endpoint không phân trang trả toàn bộ bảng.**
   `GET /hr-profiles/{user_id}/competences` (`hr_profiles.py:212`) trả `list` không giới
   hạn. `GET /forms/templates` trước đây là N+1 (đã sửa ở commit `7e5883b`).

3. **`limit` tối đa 100 nhưng `page` không có trần** → `?page=999999999` tạo
   `OFFSET 19999999980`. Postgres vẫn phải quét. Không nguy hiểm với dữ liệu hiện tại,
   nhưng là chi phí tuyến tính miễn phí cho kẻ tấn công.
   `normalize_pagination` (`app/core/responses.py`) nên chặn `page` khi `offset > total`.

### API-07 · 🟡 MEDIUM — Rate limiting phủ 8/296 endpoint

Có rate limit:

| Endpoint | Hạn mức | Khoá |
|---|---|---|
| `/auth/login` | 300/60s | IP |
| `/auth/login` (tầng service) | 10/300s | email + IP |
| `/auth/refresh` | 30/60s | IP |
| `/auth/register` | 5/600s | IP |
| `/auth/verify-email` | 20/600s | IP |
| `/auth/forgot-password` | 5/600s | IP |
| `/auth/reset-password` | 10/600s | IP |
| `/chemicals/reports/transactions/export` | 10/60s | IP |
| `/forms/submissions/export` | 10/60s | IP |
| `/reports/{type}/export.xlsx` và `.pdf` | 10/60s | IP |
| `/forms/templates/{id}/file` (upload) | 30/60s | IP |

**Không có rate limit:**
- `GET /samples/{id}/result-report.pdf` — sinh PDF bằng ReportLab (CPU-bound), **không có
  `export_slot()`** (`samples.py:341-362`).
- `GET /quotations/{id}/export.xlsx` — sinh Excel bằng openpyxl, **không có `export_slot()`**
  (`quotations.py:60-80`).
- `POST /attachments` và mọi endpoint upload khác (có `upload_slot` nhưng không rate limit).
- Toàn bộ endpoint đọc/báo cáo tổng hợp.

Một người dùng đã đăng nhập gọi liên tục `result-report.pdf` sẽ chiếm CPU của cả 4 worker
mà không chạm ngưỡng nào. `export_slot` (semaphore 2/process) tồn tại nhưng **2 đường xuất
nặng nhất không dùng nó**.

### API-08 · 🔵 LOW — Idempotency là opt-in, không endpoint nào yêu cầu

`IdempotencyMiddleware` chỉ kích hoạt khi client gửi header `Idempotency-Key`
(`idempotency.py:46-48`). Không endpoint POST nào **bắt buộc** header này, và tài liệu API
không nêu. Nghĩa là: cơ chế chống tạo trùng đã xây xong nhưng **frontend phải chủ động dùng
mới có tác dụng**. Cần kiểm tra SPA có gửi header này cho các POST tạo phiếu/giao dịch
không; nếu không, cơ chế đang nằm im.

Các POST đáng bắt buộc: `/sample-flow/intakes`, `/quotations`, `/chemicals/lots/{id}/transactions`,
`/test-requests`, `/samples/{id}/assignments`.

### API-09 · 🔵 LOW — Không có timeout ở tầng ứng dụng

Không có middleware timeout, không có `--timeout-keep-alive` tuỳ chỉnh. Chỉ có:
`db_pool_timeout=5s` (chờ lấy connection), `redis socket_timeout=2s`, boto3 `read_timeout=10s`,
webpush `5s`, SMTP `10s`.

Một truy vấn Postgres chậm (báo cáo tổng hợp trên bảng lớn) chạy **không giới hạn** và giữ
cả worker slot lẫn DB connection. `_PENDING_TTL_SECONDS = 300` trong idempotency giả định
"trần request-timeout thực tế 5 phút" — nhưng **không có gì thực thi con số đó**.

→ Đặt `statement_timeout` ở tầng Postgres (ví dụ 30s cho vai trò ứng dụng) và/hoặc middleware
timeout trả 504.

### API-10 · 🔵 LOW — Tính nhất quán trong lấy IP người gọi

`app/routers/auth.py:49-52` tự định nghĩa `_client_ip()` đọc `request.client.host`, trong
khi 25 router khác dùng `app/core/request_meta.client_ip()` (ưu tiên header `X-Real-IP`).

Hiện **cả hai cho cùng kết quả** vì uvicorn chạy với `--proxy-headers --forwarded-allow-ips '*'`
(`Dockerfile:43-46`), nên `request.client.host` đã được ghi đè bằng `X-Forwarded-For` mà
nginx đặt. Không phải lỗi đang hoạt động.

Nhưng đây là phụ thuộc ngầm: gỡ `--proxy-headers` (hoặc chạy uvicorn bằng lệnh khác lúc
gỡ lỗi) sẽ làm **riêng module auth** ghi sai IP vào `audit_logs` và khoá lockout theo IP
của nginx — đúng cái lỗi mà `request_meta.py` được viết ra để sửa (docstring của nó ghi
"545/1.442 dòng audit_logs ghi IP container"). Nên dùng chung một nguồn sự thật.

---

## 4. Kiểm tra "đường xấu" (malicious / unexpected path)

| Thử nghiệm | Kết quả |
|---|---|
| Gọi endpoint ghi không có token | 401 ✅ (đã quét tự động toàn bộ 296 route) |
| Token hết hạn | 401 `TOKEN_EXPIRED` ✅ |
| Token đã logout (jti denylist) | 401 `TOKEN_INVALID` ✅ |
| Token cấp trước khi đổi mật khẩu | 401 ✅ (`deps.py:78-81`) |
| Sửa `role` trong JWT | ❌ Chữ ký HS256 không khớp → 401 ✅ |
| `alg: none` / algorithm confusion | ❌ `algorithms=["HS256"]` cố định ✅ |
| Gửi `role` trong `POST /auth/register` | 400 (`extra="forbid"`) ✅ |
| Gửi `status` trong `PATCH /users/{id}` | 400 (`extra="forbid"`) ✅ |
| Đọc thông báo của người khác | 404 (không lộ tồn tại) ✅ |
| Đổi mã thiết bị | 422 `CODE_IMMUTABLE` ✅ |
| Xuất kho quá tồn | 422 ✅ + row lock chống race ✅ |
| Sửa tệp minh chứng đã duyệt (đường riêng) | 422 `INVALID_STATE` ✅ |
| **Sửa tệp minh chứng đã duyệt (qua `POST /attachments`)** | ❌ **THÀNH CÔNG** — API-02 |
| **Tải tài liệu `restricted` của phòng khác (qua `/attachments/{id}`)** | ❌ **THÀNH CÔNG** — API-02 |
| **Đọc toàn bộ báo giá bằng tài khoản staff** | ❌ **THÀNH CÔNG** — API-01 |
| Tên file `../../etc/passwd` | Sanitize thành `.._.._etc_passwd` ✅ |
| Tên file có CR/LF | Bị loại bởi allowlist ký tự ✅ |
| Upload 100MB | 413 sớm theo `Content-Length` ✅ |
| Upload 100MB với `Transfer-Encoding: chunked` | Middleware bỏ qua, nhưng `check_size()` sau khi đọc chặn ⚠️ — vẫn đọc hết vào RAM trước |
| `?page=99999999` | 200, offset khổng lồ ⚠️ API-06 |

**Lưu ý về dòng "chunked":** `RequestLimitsMiddleware` chỉ chặn khi có `Content-Length`
(`request_limits.py:33`). Với `Transfer-Encoding: chunked`, `file.file.read()` vẫn đọc toàn
bộ vào RAM rồi mới kiểm size. `upload_slot` giới hạn 3 upload đồng thời/process → trần
thiệt hại 4 × 3 × (kích thước tuỳ ý). Đây là khe hở còn lại của phòng vệ RAM.
→ Nên đọc theo chunk và dừng khi vượt ngưỡng, hoặc từ chối request chunked ở nginx
(`client_max_body_size 25m` đã có ở nginx — nginx **sẽ** chặn chunked vượt ngưỡng, nên
rủi ro thực tế thấp khi đi qua nginx; chỉ hở nếu gọi thẳng lims-api).

---

## 5. Tổng hợp

| ID | Mức | Vấn đề | Vị trí | Ưu tiên |
|---|---|---|---|---|
| API-01 | 🟠 HIGH | `/quotations` đọc không kiểm quyền | `quotation_service.py:130-158` | P0 |
| API-02 | 🟠 HIGH | `/attachments` không uỷ quyền cấp đối tượng (đọc + ghi) | `attachment_service.py:22-163` | P0 |
| API-03 | 🟡 MEDIUM | Phân quyền HR khai ở 2 tầng, không khớp | `hr_profiles.py` + `hr_service.py` | P2 |
| API-04 | 🟡 MEDIUM | 3 cơ chế phân quyền song song, không có tài liệu/test bao phủ | toàn bộ router | P2 |
| API-05 | 🟡 MEDIUM | Không có `response_model` → không lưới chắn chống lộ field | 296/296 EP | P2 |
| API-06 | 🟡 MEDIUM | Phân trang trong bộ nhớ + EP không phân trang + `page` không trần | `document_version_service.py:53-70` … | P1 |
| API-07 | 🟡 MEDIUM | Rate limit phủ 8/296; 2 đường xuất nặng nhất không có cả rate limit lẫn `export_slot` | `samples.py:341`, `quotations.py:60` | P1 |
| API-08 | 🔵 LOW | Idempotency opt-in, chưa endpoint nào bắt buộc | `middleware/idempotency.py:46` | P2 |
| API-09 | 🔵 LOW | Không có timeout tầng ứng dụng / `statement_timeout` | — | P1 |
| API-10 | 🔵 LOW | Hai nguồn sự thật cho IP người gọi | `auth.py:49` vs `request_meta.py:25` | P3 |
