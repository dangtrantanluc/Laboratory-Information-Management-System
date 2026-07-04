# API Contract: M7 — Quản trị Hệ thống & Nền tảng (Auth, Org, RBAC, User, Notification)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M7 — System Administration & Platform (nền tảng dùng chung cho mọi module M1–M6)
**Version:** 1.0 | **Ngày:** 20/06/2026 | **Designer:** api-designer agent
**Nguồn chân lý:** `01-demo-scope.md` (RBAC 4 vai trò + phạm vi phòng ban, ERD core, M7.1–M7.5, R13/R15, §8.4)
**Đồng bộ phong cách:** `04-contract-m2-api.md` + `07-contract-m1-api.md` (response format, prefix `/api/v1`, UUID, pagination 20/100, correlationId, error code SNAKE_CASE, RBAC scope)
**Stack:** FastAPI + PostgreSQL + Redis + MinIO + APScheduler (monolith, ~40 user)

> M7 là **module nền tảng**: cung cấp xác thực (JWT), phân quyền (RBAC + phạm vi phòng ban), người dùng, phòng ban (+ trưởng nhóm `lead_user_id`), khách hàng dùng chung, thông báo in-app, audit log toàn hệ thống, và endpoint tải file dùng chung. Mọi error code/RBAC/scope ở M1, M2 (và các module sau) đều **dựa trên M7**. Contract này là **điều kiện tiên quyết** để implement auth + RBAC middleware trước S0.

---

## 0. Quy ước chung (đọc trước)

### 0.1 Base & versioning
- Prefix: `/api/v1`. Mọi resource là danh từ số nhiều (`/users`, `/departments`, `/customers`, `/notifications`, `/audit-logs`, `/attachments`).
- Nested tối đa 2 cấp (vd `/users/:id/password`). ID trong URL là **UUID** — KHÔNG lộ ID tuần tự (rule api.md). `code` hiển thị (department.code) chỉ để hiển thị/lọc, không dùng làm path param định danh.
- Không breaking change trong cùng `v1`; endpoint deprecated báo trước ≥ 1 sprint + header `Deprecation: true` (rule api.md).

### 0.2 Response format chuẩn (đồng bộ M1/M2)
```jsonc
// Success — single resource
{ "success": true, "data": { /* object */ } }

// Success — list (pagination)
{ "success": true, "data": [ /* items */ ],
  "meta": { "page": 1, "limit": 20, "total": 137, "hasNext": true } }

// Error
{ "success": false,
  "error": {
    "code": "SNAKE_CASE_CODE",
    "message": "Thông điệp cho người dùng/dev (KHÔNG chứa stack trace)",
    "details": [ { "field": "email", "message": "Email không hợp lệ" } ],
    "correlationId": "c1f2..."   // luôn trả để user report support (rule logging.md)
  } }
```

### 0.3 Auth & headers (M7 định nghĩa chuẩn cho toàn hệ thống)
- **Mọi endpoint yêu cầu** `Authorization: Bearer <access_token>` **TRỪ** 2 endpoint public: `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh` (refresh dùng refresh token, không cần access token).
- Header chuẩn client gửi mọi request:
  - `Authorization: Bearer <access_token>` (trừ login/refresh).
  - `X-Correlation-Id: <uuid>` — nếu thiếu, server tự sinh; **luôn trả lại** trong response header `X-Correlation-Id` + ghi vào `audit_logs.correlation_id` (bắt buộc audit VILAS §8.4 — R15).
  - `Content-Type: application/json` (trừ upload multipart — thuộc từng module).
- 401 `UNAUTHORIZED` nếu thiếu/sai token; 403 nếu thiếu quyền/sai phạm vi phòng ban.
- **Cách FE đính token:** access token lưu memory (in-memory store của app, không localStorage để giảm XSS); refresh token lưu **HttpOnly Secure SameSite=Strict cookie** (do BE set) — FE không đọc được refresh token bằng JS. FE chỉ tự gắn `Authorization` header từ access token; refresh token tự đính kèm cookie khi gọi `/auth/refresh`. (Nếu KH yêu cầu mobile/native sau này, refresh token có thể trả trong body — đánh dấu là thay đổi cấu hình, không phải mặc định.)

### 0.4 Token shape (JWT)
- **Access token:** JWT ký HS256 (secret từ env; có thể nâng RS256 nếu cần), TTL **≤ 60 phút** (mặc định 30 phút — NFR-SEC-003). Claims:
  ```jsonc
  {
    "sub": "user-uuid",         // user id
    "role": "staff",            // admin | leader | accountant | staff
    "dept": "dept-uuid",        // department_id (cho phạm vi phòng ban)
    "is_dept_lead": true,       // trưởng nhóm phòng (departments.lead_user_id == sub)
    "jti": "token-uuid",        // id token để revoke
    "iat": 1718870400,
    "exp": 1718872200
  }
  ```
  > RBAC middleware đọc `role` + `dept` + `is_dept_lead` từ claims để enforce quyền/phạm vi mà không phải query DB mỗi request (cache phân quyền). Khi role/dept đổi (admin sửa user) → access token cũ còn hiệu lực tối đa tới `exp`; thao tác nhạy cảm (disable user) revoke ngay qua denylist `jti` ở Redis (xem §4.2).
- **Refresh token:** opaque random (không phải JWT — không tự giải mã được), lưu hash ở bảng `refresh_tokens` (server-side), TTL **≤ 30 ngày** (mặc định 30 ngày). **Rotation bắt buộc:** mỗi lần `/auth/refresh` → cấp refresh token mới + thu hồi token cũ (revoke). Phát hiện dùng lại refresh token đã thu hồi (token reuse) → **thu hồi toàn bộ phiên của user** + bắt đăng nhập lại (chống đánh cắp — NFR-SEC-003).

### 0.5 Pagination
- Mọi endpoint list: `page` (default 1), `limit` (default **20**, max **100** — vượt ép về 100). **Offset-based** (quy mô ~40 user). `meta` luôn có `page`, `limit`, `total`, `hasNext`.

### 0.6 RBAC tổng quát M7 (R13)
- **4 vai trò:** `admin` (toàn quyền), `leader` (Ban lãnh đạo), `accountant` (Kế toán), `staff` (Nhân sự/KTV). Phạm vi dữ liệu **theo phòng ban** trừ admin/leader (toàn hệ thống).
- **Quản trị (users/roles/departments):** **CHỈ `admin`** (RBAC matrix dòng "Admin — user, role, phòng ban": admin ✅, các vai trò khác —). Vai trò khác gọi → 403 `FORBIDDEN`.
- **Audit log:** chỉ `admin` + `leader` (matrix dòng "Audit log").
- **Customers:** `admin` + `staff` tạo/sửa (staff nhận mẫu — quyền KTV B02); `leader` xem; `accountant` không cần (khách gửi mẫu thuộc nghiệp vụ lab).
- **Notifications:** mỗi user CHỈ thao tác thông báo **của chính mình** (`notifications.user_id == sub`) — mọi vai trò.
- **Self-service (đổi mật khẩu mình, GET /auth/me):** mọi vai trò đã đăng nhập.
- **`is_dept_lead`** (trưởng nhóm) KHÔNG phải vai trò RBAC thứ 5 — là cờ phái sinh từ `departments.lead_user_id`. M7 chỉ chịu trách nhiệm **gán** `lead_user_id` (endpoint #15) và **phát claim** `is_dept_lead`; ngữ nghĩa quyền trưởng nhóm (assign/approve/finalize) do M1 dùng (M1 OQ#11).

### 0.7 Rate limit (đặc biệt cho auth — chống brute force)
- `POST /auth/login`: **5 req/phút/IP + 5 req/phút/email** (kết hợp). Sau **5 lần đăng nhập sai liên tiếp/tài khoản** → khóa đăng nhập 15 phút (NFR-SEC-003) → trả `ACCOUNT_LOCKED`.
- `POST /auth/refresh`: 30/phút/user.
- Endpoint quản trị (CRUD user/dept): 60/phút/user.
- Endpoint đọc (list/notifications/audit): 60/phút/user.
- Vượt → **429** `RATE_LIMIT_EXCEEDED`.

### 0.8 Bảo mật dữ liệu nhạy cảm
- **KHÔNG BAO GIỜ** trả `password_hash` trong bất kỳ response nào (kể cả admin đọc user).
- Không log password/token/refresh token (rule logging.md). Audit log ghi action chứ KHÔNG ghi giá trị mật khẩu.
- Không trả stack trace ra client; lỗi 500 chỉ trả `INTERNAL_ERROR` + `correlationId` (chi tiết log ở BE — rule logging.md).
- `bcrypt` cost ≥ 10 cho password hash (NFR-SEC-002).

---

## 1. Bảng tổng hợp Endpoint

| # | Method | Path | Mô tả | Vai trò (ghi) | Scope | M7.x |
|---|--------|------|-------|---------------|-------|------|
| **Auth (M7.1)** ||||||
| 1 | POST | `/api/v1/auth/login` | Đăng nhập email+password → access+refresh token | Public | — | M7.1 |
| 2 | POST | `/api/v1/auth/refresh` | Cấp access token mới + xoay refresh token | Public (refresh token) | self | M7.1 |
| 3 | POST | `/api/v1/auth/logout` | Đăng xuất — thu hồi refresh token hiện tại | Mọi vai trò | self | M7.1 |
| 4 | GET | `/api/v1/auth/me` | Thông tin user hiện tại + quyền hiệu lực | Mọi vai trò | self | M7.1/M7.2 |
| 5 | PATCH | `/api/v1/auth/me/password` | Đổi mật khẩu của chính mình | Mọi vai trò | self | M7.1/M7.3 |
| **Users (M7.3)** ||||||
| 6 | GET | `/api/v1/users` | Liệt kê + tìm + lọc người dùng | admin | Toàn HT | M7.3 |
| 7 | POST | `/api/v1/users` | Tạo người dùng | admin | Toàn HT | M7.3 |
| 8 | GET | `/api/v1/users/:id` | Chi tiết người dùng (không có password_hash) | admin | Toàn HT | M7.3 |
| 9 | PATCH | `/api/v1/users/:id` | Cập nhật người dùng (partial) | admin | Toàn HT | M7.3 |
| 10 | POST | `/api/v1/users/:id/enable` | Kích hoạt tài khoản | admin | Toàn HT | M7.3 |
| 11 | POST | `/api/v1/users/:id/disable` | Vô hiệu hóa tài khoản + revoke phiên | admin | Toàn HT | M7.3 |
| 12 | POST | `/api/v1/users/:id/reset-password` | Admin đặt lại mật khẩu cho user | admin | Toàn HT | M7.3 |
| **Departments (M7.3)** ||||||
| 13 | GET | `/api/v1/departments` | Cây/danh sách phòng ban | Mọi vai trò (đọc) | Toàn HT | M7.3 |
| 14 | POST | `/api/v1/departments` | Tạo phòng ban | admin | Toàn HT | M7.3 |
| 15 | PATCH | `/api/v1/departments/:id` | Cập nhật phòng ban + **gán `lead_user_id`** | admin | Toàn HT | M7.3 (M1 OQ#11) |
| 16 | DELETE | `/api/v1/departments/:id` | Xóa/vô hiệu phòng ban (nếu rỗng) | admin | Toàn HT | M7.3 |
| **RBAC (M7.2)** ||||||
| 17 | GET | `/api/v1/roles` | Danh sách vai trò | Mọi vai trò (đọc) | Toàn HT | M7.2 |
| 18 | GET | `/api/v1/permissions` | Ma trận quyền (role × resource × action) | Mọi vai trò (đọc) | Toàn HT | M7.2 |
| 19 | GET | `/api/v1/roles/:role/permissions` | Quyền của một vai trò | Mọi vai trò (đọc) | Toàn HT | M7.2 |
| **Customers** ||||||
| 20 | GET | `/api/v1/customers` | Tìm/liệt kê khách gửi mẫu | admin, leader, staff | Toàn HT | M7/chung |
| 21 | POST | `/api/v1/customers` | Tạo khách gửi mẫu | admin, staff | Ghi | M7/chung |
| 22 | GET | `/api/v1/customers/:id` | Chi tiết khách | admin, leader, staff | Toàn HT | M7/chung |
| 23 | PATCH | `/api/v1/customers/:id` | Cập nhật khách | admin, staff | Ghi | M7/chung |
| **Notifications (M7.5)** ||||||
| 24 | GET | `/api/v1/notifications` | Thông báo của user hiện tại (lọc unread) | Mọi vai trò | self | M7.5 |
| 25 | GET | `/api/v1/notifications/unread-count` | Số thông báo chưa đọc | Mọi vai trò | self | M7.5 |
| 26 | PATCH | `/api/v1/notifications/:id/read` | Đánh dấu 1 thông báo đã đọc | Mọi vai trò | self | M7.5 |
| 27 | PATCH | `/api/v1/notifications/read-all` | Đánh dấu tất cả đã đọc | Mọi vai trò | self | M7.5 |
| **Audit log (M7.4)** ||||||
| 28 | GET | `/api/v1/audit-logs` | Tra cứu audit log (filter + phân trang) | admin, leader | Toàn HT | M7.4 |
| 29 | GET | `/api/v1/audit-logs/:id` | Chi tiết 1 bản ghi audit | admin, leader | Toàn HT | M7.4 |
| **Attachments (dùng chung)** ||||||
| 30 | GET | `/api/v1/attachments/:id` | Lấy presigned URL tải file (RBAC theo owner) | Theo quyền owner resource | Theo owner | M7/chung |

> **Append-only:** `audit_logs` KHÔNG có POST/PATCH/DELETE (ghi nội bộ bởi service, bất biến — §8.4). Upload file thuộc từng module (M1/M2/M3...); M7 chỉ cung cấp endpoint **tải** dùng chung (#30).

---

## 2. Chi tiết Endpoint

---

### 1. POST /api/v1/auth/login
**Mục đích:** Xác thực email + password → cấp access token (≤60p) + refresh token (≤30 ngày). **Endpoint public** (M7.1).
**Auth:** Public (không cần token) | **Rate limit:** 5/phút/IP + 5/phút/email

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| email | string | ✅ | format email, maxLength(255), lowercased | Email đăng nhập |
| password | string | ✅ | minLength(8), maxLength(128) | Mật khẩu (plaintext qua HTTPS, không log) |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 1800,
    "user": {
      "id": "user-uuid",
      "email": "ktv.a@lab.edu.vn",
      "full_name": "Nguyễn Văn A",
      "role": "staff",
      "department_id": "dept-uuid",
      "department_name": "Hóa lý",
      "is_dept_lead": false
    }
  }
}
```
> `refresh_token` **KHÔNG** trả trong body — được set qua **HttpOnly Secure cookie** `refresh_token` (Path=`/api/v1/auth`, SameSite=Strict, Max-Age=2592000). `expires_in` = TTL access token (giây). `access_token` để FE lưu memory + gắn header (§0.3).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | email sai định dạng / password rỗng |
| INVALID_CREDENTIALS | 401 | Sai email hoặc password (KHÔNG tiết lộ field nào sai — chống user enumeration) |
| ACCOUNT_LOCKED | 423 | ≥5 lần sai liên tiếp → khóa 15 phút (NFR-SEC-003); `details` chứa `locked_until` |
| ACCOUNT_DISABLED | 403 | Tài khoản `status=disabled` (admin đã vô hiệu) |
| RATE_LIMIT_EXCEEDED | 429 | Vượt 5/phút |

**Ví dụ error ACCOUNT_LOCKED:**
```json
{
  "success": false,
  "error": {
    "code": "ACCOUNT_LOCKED",
    "message": "Tài khoản tạm khóa do nhập sai mật khẩu quá nhiều lần. Vui lòng thử lại sau.",
    "details": [{ "field": "account", "locked_until": "2026-06-20T08:15:00Z", "remaining_seconds": 873 }],
    "correlationId": "c1f2..."
  }
}
```

**Side effects:**
- Thành công: reset bộ đếm `failed_login_count`; tạo bản ghi `refresh_tokens` (hash); `audit_logs` action=`AUTH_LOGIN_SUCCESS` (user, ip, correlation_id — KHÔNG ghi password).
- Thất bại: tăng `failed_login_count`; nếu chạm ngưỡng 5 → set `locked_until = now + 15m`; `audit_logs` action=`AUTH_LOGIN_FAIL` (email cố gắng, ip — để phát hiện brute force).

---

### 2. POST /api/v1/auth/refresh
**Mục đích:** Dùng refresh token (cookie) cấp access token mới + **xoay** refresh token (rotation). Public theo nghĩa không cần access token, nhưng phải có refresh token hợp lệ (M7.1, NFR-SEC-003).
**Auth:** Public (refresh token cookie) | **Rate limit:** 30/phút/user

**Request:** refresh token lấy từ **HttpOnly cookie** `refresh_token` (mặc định). Body trống. (Cấu hình native client: chấp nhận `{ "refresh_token": "..." }` trong body — đánh dấu khác mặc định.)

**Response 200:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 1800
  }
}
```
> Đồng thời set cookie `refresh_token` **MỚI** (rotation) + revoke token cũ. Access token mang claims mới nhất (role/dept cập nhật nếu admin vừa đổi).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| TOKEN_INVALID | 401 | Refresh token không tồn tại / sai / không khớp hash |
| TOKEN_EXPIRED | 401 | Refresh token quá TTL 30 ngày |
| TOKEN_REUSED | 401 | Refresh token đã bị thu hồi mà vẫn dùng lại → **revoke toàn bộ phiên user** (token theft) |
| ACCOUNT_DISABLED | 403 | User bị vô hiệu sau khi token còn hạn |

**Side effects:** Revoke refresh token cũ; tạo refresh token mới; nếu `TOKEN_REUSED` → revoke mọi `refresh_tokens` của user + `audit_logs` action=`AUTH_TOKEN_REUSE_DETECTED` (cảnh báo bảo mật). `audit_logs` action=`AUTH_TOKEN_REFRESH` cho lượt thành công.

---

### 3. POST /api/v1/auth/logout
**Mục đích:** Đăng xuất — thu hồi refresh token hiện tại + (tùy chọn) đưa `jti` access token vào denylist Redis (M7.1).
**Auth:** Bearer JWT | **Rate limit:** 60/phút

**Request Body:** rỗng (refresh token lấy từ cookie). Query `all=true` (optional) → logout mọi thiết bị (revoke tất cả refresh token của user).

**Response 204:** No content. Đồng thời xóa cookie `refresh_token` (set Max-Age=0).

**Errors:** `UNAUTHORIZED` (401) nếu thiếu access token.

**Side effects:** Revoke refresh token hiện tại (hoặc tất cả nếu `all=true`); đẩy `jti` vào Redis denylist tới khi access token hết hạn; `audit_logs` action=`AUTH_LOGOUT`.

---

### 4. GET /api/v1/auth/me
**Mục đích:** Lấy thông tin user hiện tại + **quyền hiệu lực** (để FE render menu/nút theo RBAC) (M7.1/M7.2).
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** self | **Rate limit:** 60/phút

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "user-uuid",
    "email": "ktv.a@lab.edu.vn",
    "full_name": "Nguyễn Văn A",
    "role": "staff",
    "department": { "id": "dept-uuid", "name": "Hóa lý", "code": "HL" },
    "is_dept_lead": false,
    "status": "active",
    "permissions": [
      { "resource": "sample", "action": "create" },
      { "resource": "sample_result", "action": "enter" },
      { "resource": "chemical_txn", "action": "create" }
    ],
    "created_at": "2026-05-01T03:00:00Z"
  }
}
```
> `permissions` = ma trận quyền của `role` (đọc từ `roles_permissions`) + quyền phái sinh từ `is_dept_lead` (vd `sample:assign`, `sample_result:approve`, `sample:finalize` chỉ thêm khi `is_dept_lead=true`). FE dùng để bật/tắt UI; backend vẫn re-validate mọi thao tác ghi.

**Errors:** `UNAUTHORIZED` (401).

---

### 5. PATCH /api/v1/auth/me/password
**Mục đích:** User tự đổi mật khẩu của mình (M7.1/M7.3).
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** self | **Rate limit:** 10/phút

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| current_password | string | ✅ | — | Mật khẩu hiện tại (xác minh trước khi đổi) |
| new_password | string | ✅ | minLength(8), maxLength(128), ≠ current_password, đủ độ mạnh (chữ + số) | Mật khẩu mới |

**Response 200:**
```json
{ "success": true, "data": { "id": "user-uuid", "password_changed_at": "2026-06-20T08:30:00Z" } }
```
> Sau đổi mật khẩu: **revoke toàn bộ refresh token khác** của user (buộc đăng nhập lại trên thiết bị khác) — chỉ giữ phiên hiện tại. Khuyến nghị bảo mật.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | new_password không đủ mạnh / = current_password |
| INVALID_CREDENTIALS | 401 | current_password sai |

**Side effects:** Cập nhật `password_hash` (bcrypt); revoke refresh token khác; `audit_logs` action=`PASSWORD_CHANGE_SELF` (KHÔNG ghi giá trị mật khẩu).

---

### 6. GET /api/v1/users
**Mục đích:** Liệt kê + tìm + lọc người dùng (M7.3). Chỉ admin.
**Auth:** Bearer JWT | **Roles:** admin | **Scope:** toàn HT | **Rate limit:** 60/phút

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| q | string | ❌ | maxLength(100) | Từ khóa: tên hoặc email |
| role | enum | ❌ | admin\|leader\|accountant\|staff | Lọc theo vai trò |
| department_id | uuid | ❌ | — | Lọc theo phòng ban |
| status | enum | ❌ | active\|disabled (default tất cả) | Trạng thái |
| page/limit | int | ❌ | pagination chuẩn | |

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "user-uuid",
      "email": "ktv.a@lab.edu.vn",
      "full_name": "Nguyễn Văn A",
      "role": "staff",
      "department_id": "dept-uuid",
      "department_name": "Hóa lý",
      "is_dept_lead": false,
      "status": "active",
      "last_login_at": "2026-06-20T07:50:00Z",
      "created_at": "2026-05-01T03:00:00Z"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 40, "hasNext": true }
}
```
> KHÔNG có `password_hash` (§0.8). `last_login_at` từ `audit_logs`/cột cache.

**Errors:** `FORBIDDEN` (403 non-admin), `VALIDATION_ERROR` (400).

---

### 7. POST /api/v1/users
**Mục đích:** Tạo người dùng mới (M7.3). Chỉ admin.
**Auth:** Bearer JWT | **Roles:** admin | **Scope:** toàn HT | **Rate limit:** 60/phút

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| email | string | ✅ | format email, unique (lowercased), maxLength(255) | Email đăng nhập |
| full_name | string | ✅ | maxLength(255), trim non-empty | Họ tên |
| role | enum | ✅ | admin\|leader\|accountant\|staff | Vai trò |
| department_id | uuid | ✅* | tồn tại trong `departments` | Phòng ban (*bắt buộc với staff/leader; admin có thể null/toàn HT) |
| password | string | ❌ | minLength(8); nếu trống → sinh mật khẩu tạm + buộc đổi lần đầu | Mật khẩu khởi tạo |
| is_dept_lead | bool | ❌ | default false | Đề xuất gán trưởng nhóm (thực gán qua #15 để đồng bộ `departments.lead_user_id`) |

> `password_hash`, `status` (default `active`), `id` server thiết lập — KHÔNG nhận từ client. Gán trưởng nhóm chuẩn xác **qua #15** (cập nhật `departments.lead_user_id`) để 1 phòng chỉ 1 lead; field `is_dept_lead` ở đây chỉ tiện lợi, backend ghi đồng bộ vào departments.

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "user-uuid",
    "email": "ktv.b@lab.edu.vn",
    "full_name": "Trần Thị B",
    "role": "staff",
    "department_id": "dept-uuid",
    "is_dept_lead": false,
    "status": "active",
    "must_change_password": true,
    "created_at": "2026-06-20T08:00:00Z"
  }
}
```
> `must_change_password=true` nếu admin để trống password (sinh tạm). Mật khẩu tạm KHÔNG trả qua API plaintext — bàn giao qua kênh an toàn (rule vn-docs); hoặc dùng flow reset (#12).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | email sai / full_name rỗng / role sai |
| EMAIL_EXISTS | 409 | Email đã tồn tại |
| DEPARTMENT_NOT_FOUND | 404 | department_id không tồn tại |
| FORBIDDEN | 403 | non-admin |

**Side effects:** Tạo `users` (bcrypt password); nếu `is_dept_lead=true` → cập nhật `departments.lead_user_id`; `audit_logs` action=`USER_CREATE` (detail: email, role, dept — KHÔNG mật khẩu).

---

### 8. GET /api/v1/users/:id
**Mục đích:** Chi tiết người dùng (M7.3). Chỉ admin. Không trả `password_hash`.
**Auth:** Bearer JWT | **Roles:** admin | **Scope:** toàn HT | **Rate limit:** 60/phút

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "user-uuid",
    "email": "ktv.a@lab.edu.vn",
    "full_name": "Nguyễn Văn A",
    "role": "staff",
    "department": { "id": "dept-uuid", "name": "Hóa lý", "code": "HL" },
    "is_dept_lead": false,
    "status": "active",
    "last_login_at": "2026-06-20T07:50:00Z",
    "created_at": "2026-05-01T03:00:00Z",
    "updated_at": "2026-06-15T02:00:00Z"
  }
}
```

**Errors:** `NOT_FOUND` (404), `FORBIDDEN` (403 non-admin).

---

### 9. PATCH /api/v1/users/:id
**Mục đích:** Cập nhật partial người dùng (đổi tên/role/phòng) (M7.3). Chỉ admin.
**Auth:** Bearer JWT | **Roles:** admin | **Scope:** toàn HT | **Rate limit:** 60/phút

**Request Body (≥1 field):**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| full_name | string | ❌ | maxLength(255) | |
| role | enum | ❌ | admin\|leader\|accountant\|staff | Đổi vai trò |
| department_id | uuid | ❌ | tồn tại | Đổi phòng ban |
| email | string | ❌ | format email, unique | Đổi email (cẩn trọng — ghi audit) |

> KHÔNG đổi password ở đây (dùng #12 reset). Đổi `role`/`department_id` làm claims access token cũ lệch → buộc cấp lại ở lần `/auth/refresh` kế (claims mới); thao tác nhạy cảm (đổi role lên admin) ghi audit rõ. Không cho admin tự hạ vai trò mình nếu là admin cuối cùng (tránh khóa hệ thống) → `LAST_ADMIN_PROTECTED`.

**Response 200:** giống #8.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | body rỗng / field sai |
| EMAIL_EXISTS | 409 | Đổi email gây trùng |
| DEPARTMENT_NOT_FOUND | 404 | department_id không tồn tại |
| LAST_ADMIN_PROTECTED | 422 | Hạ vai trò admin cuối cùng |
| FORBIDDEN | 403 | non-admin |
| NOT_FOUND | 404 | id không tồn tại |

**Side effects:** `audit_logs` action=`USER_UPDATE` (detail = diff field, đặc biệt đánh dấu đổi role/dept).

---

### 10. POST /api/v1/users/:id/enable
**Mục đích:** Kích hoạt tài khoản đang `disabled` (M7.3). Chỉ admin.
**Auth:** Bearer JWT | **Roles:** admin | **Rate limit:** 60/phút

**Request Body:** rỗng.

**Response 200:** `{ "success": true, "data": { "id": "user-uuid", "status": "active" } }`

**Errors:** `NOT_FOUND` (404), `FORBIDDEN` (403 non-admin).
**Side effects:** `audit_logs` action=`USER_ENABLE`.

---

### 11. POST /api/v1/users/:id/disable
**Mục đích:** Vô hiệu hóa tài khoản — chặn đăng nhập + **revoke toàn bộ phiên** (M7.3). Soft (không xóa, giữ truy vết VILAS). Chỉ admin.
**Auth:** Bearer JWT | **Roles:** admin | **Rate limit:** 60/phút

**Request Body:** rỗng.

**Response 200:** `{ "success": true, "data": { "id": "user-uuid", "status": "disabled" } }`

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| LAST_ADMIN_PROTECTED | 422 | Vô hiệu admin cuối cùng |
| SELF_DISABLE_FORBIDDEN | 422 | Admin tự vô hiệu chính mình |
| NOT_FOUND | 404 | id không tồn tại |
| FORBIDDEN | 403 | non-admin |

**Side effects:** Set `status=disabled`; **revoke mọi `refresh_tokens`** của user + đẩy `jti` access token vào denylist (cắt phiên ngay — §4.2); `audit_logs` action=`USER_DISABLE`. Nếu user là `lead_user_id` của phòng nào → cảnh báo (không tự gỡ; admin nên gán lead mới qua #15).

---

### 12. POST /api/v1/users/:id/reset-password
**Mục đích:** Admin đặt lại mật khẩu cho user (quên mật khẩu) (M7.3). Chỉ admin.
**Auth:** Bearer JWT | **Roles:** admin | **Rate limit:** 30/phút

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| new_password | string | ❌ | minLength(8); nếu trống → sinh tạm + buộc đổi lần đầu | Mật khẩu mới |

**Response 200:**
```json
{ "success": true, "data": { "id": "user-uuid", "must_change_password": true, "reset_at": "2026-06-20T08:40:00Z" } }
```
> Mật khẩu tạm KHÔNG trả plaintext qua API; bàn giao qua kênh an toàn (1Password/Bitwarden — rule vn-docs §D). `must_change_password=true` buộc user đổi ở lần đăng nhập kế.

**Errors:** `VALIDATION_ERROR` (400 password yếu), `NOT_FOUND` (404), `FORBIDDEN` (403 non-admin).
**Side effects:** Cập nhật `password_hash`; revoke toàn bộ refresh token của user (buộc đăng nhập lại); `audit_logs` action=`PASSWORD_RESET_ADMIN` (admin id + target user — KHÔNG ghi mật khẩu).

---

### 13. GET /api/v1/departments
**Mục đích:** Lấy danh sách/cây phòng ban (M7.3). Đọc cho mọi vai trò (FE chọn phòng khi tạo user/phiếu).
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc) | **Scope:** toàn HT | **Rate limit:** 60/phút

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| tree | bool | ❌ | default false | true → trả cây lồng nhau (children); false → phẳng |
| include_inactive | bool | ❌ | default false | Gồm phòng đã vô hiệu |

**Response 200 (phẳng):**
```json
{
  "success": true,
  "data": [
    {
      "id": "dept-uuid",
      "name": "Hóa lý",
      "code": "HL",
      "parent_id": null,
      "lead_user_id": "userT-uuid",
      "lead_user_name": "Trưởng nhóm T",
      "member_count": 8,
      "status": "active"
    }
  ]
}
```
> `tree=true` → mỗi node thêm `"children": [ ... ]` lồng theo `parent_id` (cây phòng ban — B01).

**Errors:** `UNAUTHORIZED` (401).

---

### 14. POST /api/v1/departments
**Mục đích:** Tạo phòng ban (M7.3). Chỉ admin.
**Auth:** Bearer JWT | **Roles:** admin | **Scope:** toàn HT | **Rate limit:** 60/phút

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| name | string | ✅ | maxLength(255), trim non-empty | Tên phòng |
| code | string | ✅ | maxLength(50), unique, regex `^[A-Z0-9_-]+$` | Mã phòng (hiển thị/lọc) |
| parent_id | uuid | ❌ | tồn tại; không tạo vòng lặp | Phòng cha (cây) |
| lead_user_id | uuid | ❌ | user tồn tại + thuộc phòng này | Trưởng nhóm |

**Response 201:**
```json
{
  "success": true,
  "data": { "id": "dept-uuid", "name": "Hóa lý", "code": "HL", "parent_id": null,
    "lead_user_id": null, "status": "active", "created_at": "2026-06-20T08:00:00Z" }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | name rỗng / code sai định dạng |
| DUPLICATE_CODE | 409 | code đã tồn tại |
| PARENT_NOT_FOUND | 404 | parent_id không tồn tại |
| INVALID_PARENT | 422 | parent_id tạo vòng lặp cây |
| FORBIDDEN | 403 | non-admin |

**Side effects:** `audit_logs` action=`DEPARTMENT_CREATE`.

---

### 15. PATCH /api/v1/departments/:id
**Mục đích:** Cập nhật phòng ban + **gán trưởng nhóm `lead_user_id`** (M7.3, **quan trọng cho M1 OQ#11** — quyền assign/approve/finalize). Partial.
**Auth:** Bearer JWT | **Roles:** admin | **Scope:** toàn HT | **Rate limit:** 60/phút

**Request Body (≥1 field):**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| name | string | ❌ | maxLength(255) | |
| code | string | ❌ | unique, regex | |
| parent_id | uuid\|null | ❌ | tồn tại; không vòng lặp | Đổi/gỡ phòng cha |
| lead_user_id | uuid\|null | ❌ | user tồn tại + `department_id == :id` + `status=active` | Gán/đổi/gỡ trưởng nhóm |

> **Quy tắc lead:** `lead_user_id` phải là user **thuộc đúng phòng này** và `active`. Một phòng chỉ 1 lead. Gán lead → user đó nhận `is_dept_lead=true` trong claims ở lần refresh kế (hoặc ngay nếu re-issue). Gỡ lead (`null`) → user mất quyền trưởng nhóm M1.

**Response 200:**
```json
{
  "success": true,
  "data": { "id": "dept-uuid", "name": "Hóa lý", "code": "HL", "parent_id": null,
    "lead_user_id": "userT-uuid", "lead_user_name": "Trưởng nhóm T", "status": "active" }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | body rỗng / field sai |
| DUPLICATE_CODE | 409 | đổi code gây trùng |
| INVALID_PARENT | 422 | parent_id gây vòng lặp |
| LEAD_NOT_IN_DEPARTMENT | 422 | lead_user_id không thuộc phòng này (M1 OQ#11) |
| LEAD_USER_INACTIVE | 422 | lead_user_id đang `disabled` |
| USER_NOT_FOUND | 404 | lead_user_id không tồn tại |
| FORBIDDEN | 403 | non-admin |
| NOT_FOUND | 404 | department id không tồn tại |

**Side effects:** `audit_logs` action=`DEPARTMENT_UPDATE` (diff); nếu đổi `lead_user_id` → action riêng `DEPARTMENT_LEAD_ASSIGN` (old_lead → new_lead) — phục vụ truy vết quyền trưởng nhóm; re-issue/invalidate claims của user liên quan.

---

### 16. DELETE /api/v1/departments/:id
**Mục đích:** Xóa/vô hiệu phòng ban (M7.3). Chỉ admin. Chỉ cho khi phòng rỗng (không user, không phòng con, không dữ liệu nghiệp vụ tham chiếu).
**Auth:** Bearer JWT | **Roles:** admin | **Rate limit:** 60/phút

**Response 204:** No content (nếu xóa cứng được) **hoặc** 200 với `status=inactive` (soft — mặc định, giữ truy vết).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| DEPARTMENT_NOT_EMPTY | 422 | Còn user / phòng con / dữ liệu nghiệp vụ tham chiếu |
| FORBIDDEN | 403 | non-admin |
| NOT_FOUND | 404 | id không tồn tại |

**Side effects:** Soft-deactivate (mặc định) → `status=inactive`; `audit_logs` action=`DEPARTMENT_DELETE`.

---

### 17. GET /api/v1/roles
**Mục đích:** Danh sách 4 vai trò + mô tả (M7.2). Dùng cho dropdown gán role.
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc) | **Scope:** toàn HT | **Rate limit:** 60/phút

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "role": "admin", "label": "Quản trị viên", "description": "Toàn quyền hệ thống", "scope": "global" },
    { "role": "leader", "label": "Ban lãnh đạo", "description": "Xem toàn hệ thống, duyệt nghiệp vụ", "scope": "global" },
    { "role": "accountant", "label": "Kế toán", "description": "Tài chính; không xem mẫu/kết quả", "scope": "global" },
    { "role": "staff", "label": "Nhân sự/KTV", "description": "Nghiệp vụ lab theo phòng ban", "scope": "department" }
  ]
}
```

**Errors:** `UNAUTHORIZED` (401).

---

### 18. GET /api/v1/permissions
**Mục đích:** Ma trận quyền đầy đủ `role × resource × action` (M7.2, R13). Đọc từ `roles_permissions` (seed sẵn). Không có endpoint ghi — quyền quản lý chủ yếu qua seed/migration.
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc) | **Scope:** toàn HT | **Rate limit:** 60/phút

**Query params:** `resource` (optional, lọc theo resource), `role` (optional).

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "role": "admin",      "resource": "user",          "action": "manage",  "scope": "global" },
    { "role": "admin",      "resource": "audit_log",     "action": "read",    "scope": "global" },
    { "role": "leader",     "resource": "audit_log",     "action": "read",    "scope": "global" },
    { "role": "staff",      "resource": "sample",        "action": "create",  "scope": "department" },
    { "role": "staff",      "resource": "sample_result", "action": "enter",   "scope": "assigned" },
    { "role": "accountant", "resource": "chemical_cost", "action": "read",    "scope": "global" },
    { "role": "accountant", "resource": "sample",        "action": "none",    "scope": "none" }
  ],
  "meta": { "page": 1, "limit": 100, "total": 64, "hasNext": false }
}
```
> Quyền trưởng nhóm (`sample:assign`, `sample_result:approve`, `sample:finalize`) là **phái sinh từ `is_dept_lead`**, không nằm trong matrix theo role — ghi chú rõ ở đây để FE/dev hiểu (M1 dùng).

**Errors:** `UNAUTHORIZED` (401).

---

### 19. GET /api/v1/roles/:role/permissions
**Mục đích:** Quyền của MỘT vai trò (tiện cho FE/màn cấu hình) (M7.2).
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc) | **Scope:** toàn HT | **Rate limit:** 60/phút

**Path:** `role` ∈ `admin|leader|accountant|staff`.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "role": "staff",
    "label": "Nhân sự/KTV",
    "scope": "department",
    "permissions": [
      { "resource": "sample", "action": "create", "scope": "department" },
      { "resource": "sample_result", "action": "enter", "scope": "assigned" },
      { "resource": "chemical_txn", "action": "create", "scope": "department" }
    ],
    "derived_lead_permissions": [
      { "resource": "sample", "action": "assign", "condition": "is_dept_lead" },
      { "resource": "sample_result", "action": "approve", "condition": "is_dept_lead" },
      { "resource": "sample", "action": "finalize", "condition": "is_dept_lead" }
    ]
  }
}
```

**Errors:** `ROLE_NOT_FOUND` (404 nếu role ngoài 4 giá trị), `UNAUTHORIZED` (401).

---

### 20. GET /api/v1/customers
**Mục đích:** Tìm/liệt kê khách gửi mẫu dùng chung (M7/chung). Đồng bộ với M1 #1.
**Auth:** Bearer JWT | **Roles:** admin, leader, staff | **Scope:** đọc toàn HT | **Rate limit:** 60/phút

> **Kế toán** không truy cập customers (thuộc nghiệp vụ lab/mẫu — B03) → 403 `FORBIDDEN`.

**Query params:** `q` (string, maxLength 100), `type` (enum company\|individual\|internal), `page/limit`.

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "id": "cus-uuid", "name": "Công ty ABC", "contact": "0901234567", "type": "company", "created_at": "2026-05-10T02:00:00Z" }
  ],
  "meta": { "page": 1, "limit": 20, "total": 12, "hasNext": false }
}
```

**Errors:** `FORBIDDEN` (403 accountant), `UNAUTHORIZED` (401).

---

### 21. POST /api/v1/customers
**Mục đích:** Tạo khách gửi mẫu (M7/chung). Admin + staff (KTV nhận mẫu — B02).
**Auth:** Bearer JWT | **Roles:** admin, staff | **Scope:** ghi | **Rate limit:** 60/phút

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| name | string | ✅ | maxLength(255), trim non-empty | Tên khách/đối tượng gửi |
| contact | string | ❌ | maxLength(100) | SĐT/email liên hệ |
| type | enum | ❌ | company\|individual\|internal (default company) | Loại đối tượng |

**Response 201:**
```json
{ "success": true, "data": { "id": "cus-uuid", "name": "Công ty ABC", "contact": "0901234567", "type": "company" } }
```

**Errors:** `VALIDATION_ERROR` (400), `FORBIDDEN` (403 leader/accountant), `DUPLICATE_CUSTOMER` (409 nếu enforce trùng name+contact — tùy cấu hình).
**Side effects:** `audit_logs` action=`CUSTOMER_CREATE`.

---

### 22. GET /api/v1/customers/:id
**Mục đích:** Chi tiết khách (M7/chung).
**Auth:** Bearer JWT | **Roles:** admin, leader, staff | **Scope:** đọc toàn HT | **Rate limit:** 60/phút

**Response 200:** 1 object như item #20.
**Errors:** `NOT_FOUND` (404), `FORBIDDEN` (403 accountant).

---

### 23. PATCH /api/v1/customers/:id
**Mục đích:** Cập nhật khách (M7/chung). Partial. Admin + staff.
**Auth:** Bearer JWT | **Roles:** admin, staff | **Scope:** ghi | **Rate limit:** 60/phút

**Request Body (≥1 field):** `name`, `contact`, `type` — validation như #21.
**Response 200:** giống #22.
**Errors:** `VALIDATION_ERROR` (400), `FORBIDDEN` (403 leader/accountant), `NOT_FOUND` (404).
**Side effects:** `audit_logs` action=`CUSTOMER_UPDATE`.

---

### 24. GET /api/v1/notifications
**Mục đích:** Lấy thông báo in-app **của user hiện tại** (M7.5, R7/R12/R16). Mỗi user chỉ thấy notification của mình.
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** self (`user_id == sub`) | **Rate limit:** 60/phút

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| unread | bool | ❌ | true → chỉ chưa đọc | Lọc chưa đọc |
| type | string | ❌ | maxLength(50) | Lọc loại (vd SAMPLE_DUE_SOON, SALARY_RAISE_DUE...) |
| page/limit | int | ❌ | pagination chuẩn | |

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "noti-uuid",
      "type": "SAMPLE_DUE_SOON",
      "title": "Mẫu SP-2026-0007 sắp tới hạn",
      "body": "Mẫu sẽ đến hạn ngày 25/06/2026. Bạn được giao phần 'kim loại nặng'.",
      "ref_type": "sample",
      "ref_id": "sample-uuid",
      "read_at": null,
      "created_at": "2026-06-20T07:00:00Z"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 5, "hasNext": false }
}
```
> `ref_type` + `ref_id` để FE deep-link tới resource (sample/lot/contract...). Sắp xếp `created_at` giảm dần. **Không thể** xem notification của user khác (backend luôn lọc `user_id == sub`, không nhận query `user_id`).

**Errors:** `UNAUTHORIZED` (401), `VALIDATION_ERROR` (400).

---

### 25. GET /api/v1/notifications/unread-count
**Mục đích:** Đếm thông báo chưa đọc (M7.5) — cho badge FE (polling nhẹ).
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** self | **Rate limit:** 120/phút (badge poll thường xuyên)

**Response 200:**
```json
{ "success": true, "data": { "unread_count": 5 } }
```

**Errors:** `UNAUTHORIZED` (401).

---

### 26. PATCH /api/v1/notifications/:id/read
**Mục đích:** Đánh dấu MỘT thông báo của mình là đã đọc (M7.5).
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** self | **Rate limit:** 60/phút

**Request Body:** rỗng (idempotent — đọc lại không lỗi).

**Response 200:**
```json
{ "success": true, "data": { "id": "noti-uuid", "read_at": "2026-06-20T08:30:00Z" } }
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| NOT_FOUND | 404 | Notification không tồn tại **hoặc** không thuộc user (không tiết lộ tồn tại của người khác) |
| UNAUTHORIZED | 401 | Thiếu token |

> Nếu notification thuộc user khác → trả **404 NOT_FOUND** (không phải 403) để tránh lộ sự tồn tại notification người khác (IDOR-safe).

---

### 27. PATCH /api/v1/notifications/read-all
**Mục đích:** Đánh dấu TẤT CẢ thông báo chưa đọc của mình là đã đọc (M7.5).
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** self | **Rate limit:** 30/phút

**Request Body:** rỗng. Query `type` (optional) → chỉ đánh dấu nhóm loại đó.

**Response 200:**
```json
{ "success": true, "data": { "marked_read": 5 } }
```

**Errors:** `UNAUTHORIZED` (401).

---

### 28. GET /api/v1/audit-logs
**Mục đích:** Tra cứu audit log toàn hệ thống (M7.4, R15, §8.4). **Append-only** — không có ghi/sửa/xóa. Chỉ admin + leader.
**Auth:** Bearer JWT | **Roles:** admin, leader | **Scope:** toàn HT | **Rate limit:** 60/phút

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| user_id | uuid | ❌ | — | Lọc theo người thực hiện |
| action | string | ❌ | maxLength(80) | Lọc theo action (vd SAMPLE_RESULT_ENTER) |
| resource | string | ❌ | maxLength(50) | Lọc theo loại resource (sample, chemical, user...) |
| resource_id | uuid | ❌ | — | Lọc theo resource cụ thể |
| correlation_id | string | ❌ | — | Trace 1 request xuyên suốt (rule logging.md) |
| date_from | datetime | ❌ | ≤ date_to | Khoảng thời gian từ |
| date_to | datetime | ❌ | — | Đến |
| ip | string | ❌ | — | Lọc theo IP (điều tra brute force) |
| page/limit | int | ❌ | pagination chuẩn | |

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "audit-uuid",
      "user_id": "user-uuid",
      "user_name": "Nguyễn Văn A",
      "action": "SAMPLE_RESULT_ENTER",
      "resource": "sample_result",
      "resource_id": "result-uuid",
      "correlation_id": "c1f2...",
      "ip": "10.0.0.23",
      "at": "2026-06-20T08:15:00Z",
      "detail": { "assignment_id": "assign-uuid", "version": 1 }
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 1284, "hasNext": true }
}
```
> `detail` (JSONB) chứa diff/ngữ cảnh nghiệp vụ — KHÔNG chứa password/token (rule logging.md). Sắp xếp `at` giảm dần. Cần index `(user_id, at)`, `(resource, resource_id)`, `(correlation_id)`, `(action, at)` (schema-designer enforce — NFR list/search P95 < 500ms).

**Errors:** `FORBIDDEN` (403 staff/accountant), `VALIDATION_ERROR` (400 date range), `UNAUTHORIZED` (401).

---

### 29. GET /api/v1/audit-logs/:id
**Mục đích:** Chi tiết 1 bản ghi audit (M7.4).
**Auth:** Bearer JWT | **Roles:** admin, leader | **Scope:** toàn HT | **Rate limit:** 60/phút

**Response 200:** 1 object như item #28 (kèm `detail` đầy đủ).
**Errors:** `NOT_FOUND` (404), `FORBIDDEN` (403 staff/accountant).

---

### 30. GET /api/v1/attachments/:id
**Mục đích:** Endpoint **tải file dùng chung** — trả presigned URL MinIO TTL 15 phút cho mọi loại attachment (mẫu, kết quả, CoA, MSDS, tài liệu...). RBAC enforce theo **owner resource** (M7/chung).
**Auth:** Bearer JWT | **Roles:** chỉ user có quyền ĐỌC owner resource | **Scope:** theo owner | **Rate limit:** 60/phút

**Path:** `id` = UUID bản ghi `attachments`.

**Cơ chế RBAC theo owner (quan trọng):**
- Đọc `attachments.owner_type` + `owner_id` → kiểm tra quyền đọc owner đó theo RBAC module tương ứng:
  - `owner_type=sample|sample_result|test_request` → áp RBAC M1 (Kế toán bị cấm M1 → 403 `FORBIDDEN_ACCOUNTANT`; kết quả `pending` chỉ entered_by/lead/admin/leader xem — BR-SAMPLE-021).
  - `owner_type=chemical|chemical_lot` (CoA/MSDS) → áp RBAC M2 (đọc toàn HT cho mọi vai trò M2).
  - `owner_type=document` → áp RBAC M3.
- Không có quyền đọc owner → 403. Không tồn tại → 404.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "att-uuid",
    "owner_type": "sample",
    "owner_id": "sample-uuid",
    "file_name": "bien-ban-giao-mau.pdf",
    "mime": "application/pdf",
    "size": 2097152,
    "download_url": "https://minio.../presigned?X-Amz-Expires=900&...",
    "url_expires_at": "2026-06-20T08:45:00Z",
    "uploaded_by_name": "KTV A",
    "uploaded_at": "2026-06-19T08:10:00Z"
  }
}
```
> Không proxy binary qua API — FE tải trực tiếp từ MinIO bằng `download_url` (giảm tải BE — đồng bộ M1 §0.8). Query `disposition=inline` (optional) để xem trên trình duyệt thay vì tải.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| NOT_FOUND | 404 | attachment không tồn tại / owner đã xóa |
| FORBIDDEN | 403 | Không có quyền đọc owner resource |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán tải file thuộc M1 (mẫu/kết quả) |
| RESULT_NOT_PUBLISHED | 403 | File raw data của kết quả chưa approved, ngoài nhóm xem trước (M1 BR-021) |

**Side effects:** Mỗi lần cấp presigned URL → `audit_logs` action=`ATTACHMENT_DOWNLOAD` (owner_type/owner_id + user — R15, đếm lượt tải cho M3.3/thống kê).

---

## 3. Danh mục Error Codes đầy đủ (Module M7)

| Code | HTTP | Ý nghĩa | Endpoint áp dụng |
|------|------|---------|------------------|
| `UNAUTHORIZED` | 401 | Thiếu/sai/hết hạn access token | Tất cả (trừ login/refresh khi chưa có token) |
| `INVALID_CREDENTIALS` | 401 | Sai email/password (login) hoặc current_password (đổi mk) | 1, 5 |
| `TOKEN_EXPIRED` | 401 | Access/refresh token quá TTL | 2 (refresh); access token hết hạn ở mọi endpoint |
| `TOKEN_INVALID` | 401 | Token sai chữ ký / sai định dạng / refresh không khớp | 2, mọi endpoint khi token hỏng |
| `TOKEN_REUSED` | 401 | Refresh token đã thu hồi vẫn dùng lại → revoke toàn bộ phiên | 2 |
| `ACCOUNT_LOCKED` | 423 | ≥5 lần đăng nhập sai → khóa 15 phút (NFR-SEC-003) | 1 |
| `ACCOUNT_DISABLED` | 403 | Tài khoản bị admin vô hiệu | 1, 2 |
| `FORBIDDEN` | 403 | Sai vai trò / sai phạm vi phòng ban / không phải admin | 6–16, 20–23, 28–30 |
| `FORBIDDEN_ACCOUNTANT` | 403 | Kế toán truy cập tài nguyên M1 (qua attachments/customers) | 20–23, 30 |
| `NOT_FOUND` | 404 | Resource (user/dept/customer/notification/audit/attachment) không tồn tại | 8–16, 22–30 |
| `VALIDATION_ERROR` | 400 | Input sai kiểu/định dạng/rỗng/date range | 1, 5, 6, 7, 9, 12, 14, 15, 21, 23, 24, 28 |
| `EMAIL_EXISTS` | 409 | Email user đã tồn tại | 7, 9 |
| `DUPLICATE_CODE` | 409 | Mã phòng ban đã tồn tại | 14, 15 |
| `DUPLICATE_CUSTOMER` | 409 | Khách trùng (name+contact) — nếu enforce | 21 |
| `DEPARTMENT_NOT_FOUND` | 404 | department_id không tồn tại khi tạo/sửa user | 7, 9 |
| `PARENT_NOT_FOUND` | 404 | parent_id phòng cha không tồn tại | 14, 15 |
| `INVALID_PARENT` | 422 | parent_id tạo vòng lặp cây phòng ban | 14, 15 |
| `USER_NOT_FOUND` | 404 | lead_user_id không tồn tại | 15 |
| `LEAD_NOT_IN_DEPARTMENT` | 422 | lead_user_id không thuộc phòng (M1 OQ#11) | 15 |
| `LEAD_USER_INACTIVE` | 422 | lead_user_id đang disabled | 15 |
| `LAST_ADMIN_PROTECTED` | 422 | Hạ vai trò / vô hiệu admin cuối cùng | 9, 11 |
| `SELF_DISABLE_FORBIDDEN` | 422 | Admin tự vô hiệu chính mình | 11 |
| `DEPARTMENT_NOT_EMPTY` | 422 | Xóa phòng còn user/con/tham chiếu | 16 |
| `ROLE_NOT_FOUND` | 404 | Role ngoài 4 giá trị hợp lệ | 19 |
| `RESULT_NOT_PUBLISHED` | 403 | Tải file kết quả chưa approved ngoài nhóm xem (M1 BR-021) | 30 |
| `RATE_LIMIT_EXCEEDED` | 429 | Vượt rate limit (đặc biệt login) | Tất cả |
| `INTERNAL_ERROR` | 500 | Lỗi server / transaction rollback (không trả stack trace) | Tất cả |

> **Lưu ý mã 423 `ACCOUNT_LOCKED`:** dùng HTTP 423 (Locked) để FE phân biệt rõ "khóa tạm" với 401 "sai mật khẩu". Nếu KH/FE muốn đồng bộ tối giản, có thể map về 403 — đánh dấu là tùy chọn cấu hình; mặc định 423 cho ngữ nghĩa rõ ràng. Đồng bộ với M1/M2: các code chung (`UNAUTHORIZED`, `FORBIDDEN`, `FORBIDDEN_ACCOUNTANT`, `VALIDATION_ERROR`, `NOT_FOUND`, `RATE_LIMIT_EXCEEDED`, `INTERNAL_ERROR`) giữ NGUYÊN HTTP status.

---

## 4. Ghi chú bảo mật (theo rules — bắt buộc cho dev implement auth/RBAC)

### 4.1 Mật khẩu & lưu trữ
- `bcrypt` cost ≥ 10 (NFR-SEC-002). KHÔNG lưu/log/trả password plaintext hay `password_hash`.
- Đổi mật khẩu mới phải khác mật khẩu cũ, đủ độ mạnh (≥8 ký tự, có chữ + số). Reset bởi admin → `must_change_password=true` buộc đổi lần đầu. Mật khẩu tạm bàn giao qua kênh an toàn (1Password/Bitwarden — rule vn-docs §D), KHÔNG email plaintext.

### 4.2 Token & phiên — quyết định kiến trúc
- **Access token JWT TTL ≤ 60 phút** (mặc định 30p — NFR-SEC-003). Stateless: RBAC middleware giải mã claims (`role`/`dept`/`is_dept_lead`/`jti`) để enforce nhanh, không query DB mỗi request → đạt NFR-PERF (auth P95 < 200ms).
- **Refresh token opaque, hash server-side, TTL ≤ 30 ngày, rotation mỗi lần dùng** (NFR-SEC-003). Lưu HttpOnly Secure SameSite=Strict cookie (chống XSS đọc token). Phát hiện reuse → revoke toàn bộ phiên (token theft mitigation).
- **Revoke tức thời** (disable user, đổi mật khẩu, logout): refresh token revoke ở bảng `refresh_tokens`; access token còn hạn được chặn bằng **Redis denylist theo `jti`** (TTL = thời gian còn lại của access token) → user bị vô hiệu không thao tác được ngay cả khi access token chưa hết hạn. Đây là lý do chọn `jti` trong claims.
- **Failed login lockout:** đếm theo tài khoản; ≥5 lần sai liên tiếp → `locked_until = now + 15m`; reset đếm khi đăng nhập thành công. Kết hợp rate limit theo IP + email chống brute force (NFR-SEC-003).

### 4.3 Không lộ thông tin
- `INVALID_CREDENTIALS` KHÔNG nói rõ "sai email" hay "sai mật khẩu" (chống user enumeration).
- Notification/attachment của người khác → trả `404 NOT_FOUND` thay vì 403 (chống IDOR enumeration — #26, một phần #30).
- Lỗi 500 chỉ trả `INTERNAL_ERROR` + `correlationId`; stack trace chỉ ở BE log (rule logging.md).

### 4.4 Audit & observability (VILAS §8.4 / R15)
- **Mọi thao tác ghi** (login/logout/refresh/đổi-reset mật khẩu/CRUD user-dept-customer/gán lead/disable/enable/tải file) đều ghi `audit_logs` với `user_id, action, resource, resource_id, correlation_id, ip, at, detail`. **Append-only** — không có endpoint sửa/xóa audit (#28/#29 chỉ đọc).
- `X-Correlation-Id` xuyên FE → BE → `audit_logs.correlation_id` → trace 1 request trong < 10 phút khi có sự cố (rule logging.md). Luôn trả `correlationId` trong error response để user report support.
- `AUTH_LOGIN_FAIL` ghi cả email cố gắng + IP để admin/leader điều tra brute force qua #28 (filter `action=AUTH_LOGIN_FAIL` + `ip`).

### 4.5 RBAC enforcement (R13)
- Quản trị (users/roles/departments) chỉ `admin`; audit log chỉ `admin`+`leader`; customers cấm `accountant`; notifications strict self (`user_id == sub`, không nhận query `user_id`).
- Phạm vi phòng ban dùng claim `dept`; trưởng nhóm dùng claim `is_dept_lead` (phái sinh từ `departments.lead_user_id`). RBAC enforce ở **tầng API** (middleware), không chỉ ẩn FE.

---

## 5. Header chuẩn & cách FE đính token (tóm tắt cho dev)

| Header | Hướng | Bắt buộc | Mô tả |
|--------|-------|----------|-------|
| `Authorization: Bearer <access_token>` | request | Có (trừ login/refresh) | FE lấy access token từ memory store, gắn mọi request |
| `X-Correlation-Id: <uuid>` | request + response | Khuyến nghị | FE sinh UUID/request; BE trả lại + ghi audit |
| `Content-Type: application/json` | request | Có (trừ multipart upload module khác) | |
| `Cookie: refresh_token=...` (HttpOnly) | request (chỉ `/auth/*`) | Tự động | Trình duyệt tự gửi; FE không đọc được bằng JS |
| `Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Strict` | response | — | BE set khi login/refresh; xóa khi logout |

**Luồng FE chuẩn:**
1. `POST /auth/login` → lưu `access_token` vào memory; refresh token tự nằm trong cookie.
2. Mọi request gắn `Authorization: Bearer <access_token>` + `X-Correlation-Id`.
3. Khi nhận `401 TOKEN_EXPIRED` → gọi `POST /auth/refresh` (cookie tự gửi) → nhận access token mới → retry request gốc 1 lần.
4. Nếu refresh trả `401 TOKEN_INVALID/TOKEN_EXPIRED/TOKEN_REUSED` → xóa access token, chuyển về màn đăng nhập.
5. `POST /auth/logout` → BE revoke + xóa cookie; FE xóa access token.

---

## 6. Traceability: Endpoint → M7.x + R13/R15

| Endpoint | M7.x | Yêu cầu KH / 17025 |
|----------|------|---------------------|
| #1 login, #2 refresh, #3 logout, #4 me, #5 đổi mk | M7.1 | NFR-SEC-003 (TTL token, lockout, rotation, bcrypt) |
| #6–#12 users (CRUD + enable/disable + reset) | M7.3 | Quản lý người dùng; §6.2 nhân sự (tài khoản gắn năng lực) |
| #13–#16 departments (+ `lead_user_id`) | M7.3 | B01 cây phòng ban; **M1 OQ#11** (trưởng nhóm assign/approve/finalize) |
| #17 roles, #18 permissions, #19 role detail | M7.2 | **R13** RBAC + phạm vi phòng ban |
| #20–#23 customers | M7/chung | Khách gửi mẫu dùng chung (M1 §7.4) |
| #24–#27 notifications | M7.5 | **R7/R12/R16** nhắc việc in-app (CRON-1..6) |
| #28–#29 audit logs | M7.4 | **R15** + 17025 **§8.4** kiểm soát hồ sơ (append-only, correlationId) |
| #30 attachments download | M7/chung | **R2** đính kèm file; R15 đếm lượt tải (M3.3); §7.5 hồ sơ kỹ thuật |

---

## 7. Checklist tự review

- [x] Mọi endpoint có roles + scope rõ ràng; quản trị chỉ admin; audit chỉ admin+leader
- [x] Response shape nhất quán (success wrapper + meta cho list) — đồng bộ M1/M2
- [x] Mọi error code SNAKE_CASE + HTTP status chuẩn (INVALID_CREDENTIALS/TOKEN_EXPIRED/TOKEN_INVALID/ACCOUNT_LOCKED/ACCOUNT_DISABLED/EMAIL_EXISTS/FORBIDDEN...)
- [x] Auth flow rõ: token shape (claims), refresh rotation + reuse detection, lockout, bcrypt
- [x] KHÔNG trả password_hash; không log password/token; không stack trace ra client
- [x] Access token TTL ≤ 60p; refresh ≤ 30 ngày + rotation; rate limit chặt cho /auth/login
- [x] Pagination meta.total/page/limit/hasNext; limit default 20 / max 100
- [x] UUID trong URL — không lộ sequential ID; QR/code chỉ hiển thị
- [x] correlationId xuyên suốt + trả về client; audit_logs append-only
- [x] `departments.lead_user_id` gán qua #15 (validate thuộc phòng + active) — phục vụ M1 OQ#11
- [x] Notifications strict self (user_id==sub); IDOR-safe trả 404
- [x] Attachments RBAC theo owner resource (kế thừa RBAC M1/M2/M3)
- [x] Traceability endpoint → M7.x + R13/R15 đầy đủ

**Trạng thái contract:** DRAFT — chờ User APPROVED trước khi `/dev` implement (S0: Auth + RBAC + phòng ban + audit log).
**Tham số chờ chốt (không chặn implement nền tảng):** access token TTL (mặc định 30p, ≤60p), giới hạn file size dùng chung (mặc định 20MB — đồng bộ M1/M2), HTTP code cho ACCOUNT_LOCKED (mặc định 423, có thể map 403 nếu KH yêu cầu), có expose endpoint ghi permissions hay chỉ seed (mặc định chỉ seed + đọc).

*Hết API Contract M7 v1.0.*
