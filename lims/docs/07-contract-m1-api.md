# API Contract: M1 — Quản lý Mẫu & Yêu cầu thử nghiệm (Sample Lifecycle)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M1 — Sample Lifecycle
**Version:** 1.0 | **Ngày:** 19/06/2026 | **Designer:** api-designer agent
**Nguồn chân lý:** `05-srs-m1-sample.md` (v1.1 — 19 FR, 23 BR, state machine, error codes), `01-demo-scope.md` (RBAC 4 vai trò + phạm vi phòng ban)
**Đồng bộ phong cách:** `04-contract-m2-api.md` (response format, prefix, RBAC field-level/scope, error code style, pagination, correlationId, upload MinIO multipart)
**Stack:** FastAPI + PostgreSQL + Redis + MinIO + APScheduler (monolith, ~40 user)

---

## 0. Quy ước chung (đọc trước)

### 0.1 Base & versioning
- Prefix: `/api/v1`. Mọi resource là danh từ số nhiều.
- Nested tối đa 2 cấp: `/test-requests/:id/samples`, `/samples/:id/assignments`, `/assignments/:id/results`.
- ID trong URL là **UUID** (không lộ ID tuần tự — CONSTRAINT-5, BR-SAMPLE-015, rule api.md). Mã hiển thị (`request_code`, `sample_code`) chỉ để hiển thị/lọc/quét QR, KHÔNG dùng làm path param định danh resource.

### 0.2 Response format chuẩn (đồng bộ M2)
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
    "message": "Thông điệp cho người dùng/dev",
    "details": [ { "field": "deadline_at", "message": "..." } ],
    "correlationId": "c1f2..."   // luôn trả để user report support (rule logging.md)
  } }
```

### 0.3 Auth & headers
- **Mọi endpoint M1** yêu cầu `Authorization: Bearer <JWT>` (M7). Không có endpoint public.
- **`X-Correlation-Id`** (UUID): client gửi; nếu thiếu, server tự sinh và trả lại trong response header + ghi vào `audit_logs.correlation_id` (bắt buộc audit VILAS §8.4 — BR-SAMPLE-013).
- 401 nếu thiếu/sai token; 403 nếu thiếu quyền/sai phạm vi phòng ban.

### 0.4 Pagination
- Tất cả endpoint list: `page` (default 1), `limit` (default **20**, max **100**). Vượt max → ép về 100.
- **Offset-based** (quy mô ~40 user, dataset mẫu vừa phải). `meta` luôn có `page`, `limit`, `total`, `hasNext`.

### 0.5 Rate limit
- Mặc định **60 req/phút/user** cho endpoint đọc/ghi nghiệp vụ.
- Upload file: **30 req/phút/user**.
- Endpoint nặng (xuất PDF, báo cáo on-time): **10 req/phút/user**.
- Vượt giới hạn → **429** code `RATE_LIMIT_EXCEEDED`.

### 0.6 RBAC tổng quát M1 (BR-SAMPLE-014, BR-SAMPLE-022)
- **Kế toán: CẤM TOÀN BỘ M1.** Mọi endpoint trong contract này trả **403 `FORBIDDEN_ACCOUNTANT`** cho vai trò Kế toán — chặn ở **tầng API** (không chỉ ẩn FE). Cách ly nghiệp vụ lab khỏi tài chính (B03).
- **Phạm vi phòng ban:** Admin & Ban lãnh đạo = toàn hệ thống. KTV = **ghi** chỉ trong `department_id` của mình; **đọc** kết quả đã approved công khai toàn lab (mọi phòng). Thao tác ghi chéo phòng → **403 `FORBIDDEN`**.
- **Trưởng nhóm cố định theo phòng ban** (M7: `departments.lead_user_id` / `is_dept_lead` — KHÔNG phải vai trò RBAC thứ 5): chỉ trưởng nhóm phòng đó / Admin / Ban lãnh đạo có quyền `sample:assign` (phân công), `sample_result:approve` (duyệt), `sample:finalize` (chốt done). KTV thường KHÔNG có các quyền này → **403 `FORBIDDEN`**.
- **Người được giao mới nhập kết quả** phần của mình (`assignment.assigned_to` = user, hoặc Admin) — BR-SAMPLE-008.
- **Tách nhập–duyệt:** người nhập KHÔNG tự duyệt kết quả của chính mình — BR-SAMPLE-011.

### 0.7 Phạm vi xem kết quả (OQ#3 — BR-SAMPLE-021)
- Kết quả **đã `approved`**: công khai nội bộ toàn lab (mọi vai trò xem M1 đọc được, trừ Kế toán).
- Kết quả **chưa `approved`**: CHỈ người nhập (`entered_by`) + trưởng nhóm phòng đó + Admin/Ban lãnh đạo xem. Người ngoài nhóm này không thấy (FE hiển thị "chưa có kết quả công khai"). Lọc ở **tầng API**.

### 0.8 Flow file đính kèm (đồng bộ M2 §4.2)
- **Upload qua API multipart** (`Content-Type: multipart/form-data`), backend đẩy lên MinIO, lưu `file_key` trong `attachments` (polymorphic), KHÔNG lưu binary trong DB.
- Whitelist MIME: PDF, PNG, JPG, XLSX, CSV (BR-SAMPLE-012). Size ≤ giới hạn cấu hình (OQ#6, mặc định 20MB).
- **Tải file:** trả **presigned URL MinIO TTL 15 phút** (`download_url` + `url_expires_at`), không proxy binary qua API.

### 0.9 Bất biến (immutable — VILAS §8.4)
- `sample_handovers` (chain of custody): KHÔNG có endpoint PUT/PATCH/DELETE. Sửa nhầm = ghi handover mới đính chính (BR-SAMPLE-017).
- `sample_results` đã `approved`: KHÔNG có endpoint sửa/xóa trực tiếp. Sửa = tạo phiên bản mới (`version+1`) qua endpoint riêng (BR-SAMPLE-010).
- Mẫu đang được `chemical_transactions.ref_sample_id` tham chiếu hoặc đã có kết quả approved: KHÔNG hard-delete (BR-SAMPLE-016) — chỉ soft-cancel có lý do + audit.

---

## 1. Bảng tổng hợp Endpoint

| # | Method | Path | Mô tả | Vai trò (ghi) | Scope | FR |
|---|--------|------|-------|---------------|-------|-----|
| 1 | GET | `/api/v1/customers` | Tìm/liệt kê khách hàng gửi mẫu | Mọi vai trò M1 | Đọc toàn HT | FR-018 |
| 2 | POST | `/api/v1/customers` | Tạo nhanh khách hàng gửi mẫu | Admin, KTV(phòng) | Ghi | FR-018 |
| 3 | GET | `/api/v1/test-requests` | Liệt kê + lọc phiếu yêu cầu | Mọi vai trò M1 | Đọc theo phạm vi | FR-018 |
| 4 | POST | `/api/v1/test-requests` | Tạo phiếu yêu cầu thử nghiệm | Admin, KTV(phòng) | Ghi theo phòng | FR-018 |
| 5 | GET | `/api/v1/test-requests/:id` | Chi tiết phiếu + danh sách mẫu | Mọi vai trò M1 | Đọc | FR-018/001 |
| 6 | PATCH | `/api/v1/test-requests/:id` | Sửa thông tin chung phiếu | Admin, KTV(phòng) | Ghi theo phòng | FR-018 |
| 7 | GET | `/api/v1/test-requests/:id/samples` | Liệt kê mẫu của phiếu | Mọi vai trò M1 | Đọc | FR-001 |
| 8 | POST | `/api/v1/test-requests/:id/samples` | Thêm mẫu vào phiếu (sinh sample_code) | Admin, KTV(phòng) | Ghi theo phòng | FR-001/002 |
| 9 | GET | `/api/v1/samples` | Tìm/lọc mẫu (status/deadline/phòng/người giao) | Mọi vai trò M1 | Đọc theo phạm vi | FR-001/004 |
| 10 | GET | `/api/v1/samples/:id` | Chi tiết mẫu (kèm phân công, custodian) | Mọi vai trò M1 | Đọc | FR-001 |
| 11 | PATCH | `/api/v1/samples/:id` | Sửa mẫu (mô tả/deadline — trước phân công) | Admin, KTV(phòng) | Ghi theo phòng | FR-001/012 |
| 12 | PATCH | `/api/v1/samples/:id/condition` | Ghi/sửa tình trạng mẫu khi nhận | Admin, KTV(phòng) | Ghi theo phòng | FR-004 |
| 13 | PATCH | `/api/v1/samples/:id/deadline` | Đặt/sửa deadline (TAT) | Admin, KTV/TN(phòng) | Ghi theo phòng | FR-012 |
| 14 | GET | `/api/v1/samples/:id/qr` | Lấy barcode/QR payload + ảnh của mẫu | Mọi vai trò M1 | Đọc | FR-002 |
| 15 | GET | `/api/v1/samples/:id/attachments` | Liệt kê file đính kèm mẫu | Mọi vai trò M1 | Đọc | FR-003 |
| 16 | POST | `/api/v1/samples/:id/attachments` | Upload chứng từ/ảnh mẫu (MinIO) | Admin, KTV(phòng) | Ghi theo phòng | FR-003 |
| 17 | GET | `/api/v1/test-requests/:id/attachments` | Liệt kê file đính kèm phiếu | Mọi vai trò M1 | Đọc | FR-003 |
| 18 | POST | `/api/v1/test-requests/:id/attachments` | Upload chứng từ chung của phiếu | Admin, KTV(phòng) | Ghi theo phòng | FR-003 |
| 19 | GET | `/api/v1/samples/:id/assignments` | Liệt kê phân công của mẫu | Mọi vai trò M1 | Đọc | FR-005 |
| 20 | POST | `/api/v1/samples/:id/assignments` | Phân công phần việc cho KTV | **TN phòng**, LĐ, Admin | Ghi theo phòng | FR-005 |
| 21 | DELETE | `/api/v1/assignments/:id` | Hủy phân công (chưa nhập kết quả) | **TN phòng**, LĐ, Admin | Ghi theo phòng | FR-005 |
| 22 | POST | `/api/v1/samples/:id/handovers` | Chuyển giao mẫu (handover) kèm lý do | Custodian/TN/Admin | Ghi theo phòng | FR-006 |
| 23 | GET | `/api/v1/samples/:id/custody-chain` | Xem chuỗi hành trình mẫu (timeline) | Mọi vai trò M1 | Đọc | FR-007 |
| 24 | GET | `/api/v1/assignments/:id/results` | Lấy kết quả phần việc (lọc phạm vi xem) | Theo phạm vi đọc | Đọc | FR-008/011 |
| 25 | POST | `/api/v1/assignments/:id/results` | Nhập kết quả phần được giao | Assignee, Admin | Ghi (được giao) | FR-008 |
| 26 | POST | `/api/v1/results/:id/attachments` | Upload raw data cho kết quả (MinIO) | Assignee, Admin | Ghi (được giao) | FR-009 |
| 27 | GET | `/api/v1/results/:id/attachments` | Liệt kê/tải raw data của kết quả | Theo phạm vi đọc | Đọc | FR-009 |
| 28 | POST | `/api/v1/results/:id/approve` | Duyệt kết quả phần việc | **TN phòng**, LĐ, Admin | Ghi theo phòng | FR-010 |
| 29 | POST | `/api/v1/results/:id/return` | Trả lại kết quả để sửa | **TN phòng**, LĐ, Admin | Ghi theo phòng | FR-010 |
| 30 | POST | `/api/v1/results/:id/revisions` | Tạo phiên bản sửa kết quả approved | Assignee/TN, Admin | Ghi theo phòng | FR-010 |
| 31 | GET | `/api/v1/samples/:id/results` | Tổng hợp kết quả mẫu (lọc phạm vi xem) | Mọi vai trò M1 | Đọc | FR-011 |
| 32 | POST | `/api/v1/samples/:id/finalize` | Chốt hoàn thành mẫu (testing→done) | **TN phòng**, LĐ, Admin | Ghi theo phòng | FR-019 |
| 33 | POST | `/api/v1/samples/:id/overdue-reasons` | Nhập lý do trễ hạn | KTV/TN(phòng), Admin | Ghi theo phòng | FR-014 |
| 34 | GET | `/api/v1/samples/overdue` | Danh sách mẫu sắp/đã quá hạn | Mọi vai trò M1 | Đọc theo phạm vi | FR-013/014 |
| 35 | GET | `/api/v1/samples/:id/result-report.pdf` | Xuất phiếu kết quả PDF (sync) + done→returned | TN/LĐ/Admin (KTV tải) | Ghi/đọc theo phòng | FR-016 |
| 36 | GET | `/api/v1/reports/sample-on-time` | Báo cáo on-time rate | LĐ, Admin, KTV(phòng) | Đọc theo phạm vi | FR-015 |
| 37 | POST | `/api/v1/admin/crons/sample-due-soon/run` | Chạy thủ công CRON-1 (test) | Admin | Toàn HT | FR-013 |
| 38 | POST | `/api/v1/admin/crons/sample-overdue/run` | Chạy thủ công CRON-2 (test) | Admin | Toàn HT | FR-014 |

> **TN** = trưởng nhóm phòng đó · **LĐ** = Ban lãnh đạo · **Custodian** = người giữ mẫu hiện tại.
> **Kế toán**: 403 `FORBIDDEN_ACCOUNTANT` trên TẤT CẢ endpoint trên (không liệt kê lại từng dòng).

---

## 2. Chi tiết Endpoint

---

### 1. GET /api/v1/customers
**Mục đích:** Tìm/liệt kê khách hàng (đối tượng gửi mẫu) để chọn khi tạo phiếu (FR-018).
**Auth:** Bearer JWT | **Roles:** mọi vai trò M1 | **Scope:** đọc toàn HT | **Rate limit:** 60/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| q | string | ❌ | maxLength(100) | Từ khóa tên/liên hệ |
| page/limit | int | ❌ | pagination chuẩn | |

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "id": "cus-uuid", "name": "Công ty ABC", "contact": "0901234567", "type": "company" }
  ],
  "meta": { "page": 1, "limit": 20, "total": 12, "hasNext": false }
}
```
**Errors:** `FORBIDDEN_ACCOUNTANT` (403), `UNAUTHORIZED` (401).

---

### 2. POST /api/v1/customers
**Mục đích:** Tạo nhanh khách hàng gửi mẫu (FR-018, luồng "tạo nhanh").
**Auth:** Bearer JWT | **Roles:** Admin, KTV | **Scope:** ghi | **Rate limit:** 60/min

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
**Errors:** `VALIDATION_ERROR` (400), `FORBIDDEN_ACCOUNTANT` (403).
**Side effects:** `audit_logs` action=`CUSTOMER_CREATE`.

---

### 3. GET /api/v1/test-requests
**Mục đích:** Liệt kê + lọc phiếu yêu cầu thử nghiệm (FR-018).
**Auth:** Bearer JWT | **Roles:** mọi vai trò M1 | **Scope:** đọc theo phạm vi (KTV thấy phiếu mọi phòng ở mức đọc; FE bật nút sửa chỉ phòng mình) | **Rate limit:** 60/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| q | string | ❌ | maxLength(100) | Mã phiếu / tên khách / người gửi |
| department_id | uuid | ❌ | — | Lọc phòng tiếp nhận |
| customer_id | uuid | ❌ | — | Lọc khách hàng |
| received_from | date | ❌ | ≤ received_to | Ngày nhận từ |
| received_to | date | ❌ | — | Ngày nhận đến |
| status | enum | ❌ | draft\|active (default tất cả) | Phiếu nháp (chưa có mẫu) / đã có mẫu |
| page/limit | int | ❌ | pagination chuẩn | |

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "req-uuid",
      "request_code": "RQ-2026-0042",
      "customer_id": "cus-uuid",
      "customer_name": "Công ty ABC",
      "sender_name": "Nguyễn Văn A",
      "department_id": "dep-uuid",
      "department_name": "Hóa lý",
      "received_by": "user-uuid",
      "received_by_name": "Trần Thị B",
      "received_at": "2026-06-19T08:00:00Z",
      "sample_count": 3,
      "status": "active",
      "created_at": "2026-06-19T08:00:00Z"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 42, "hasNext": true }
}
```
**Errors:** `VALIDATION_ERROR` (400, date range sai), `FORBIDDEN_ACCOUNTANT` (403).

---

### 4. POST /api/v1/test-requests
**Mục đích:** Tạo phiếu yêu cầu thử nghiệm — thông tin chung của lô (FR-018). Sinh `request_code` duy nhất. Phiếu là vùng chứa 1..n mẫu.
**Auth:** Bearer JWT | **Roles:** Admin, KTV | **Scope:** KTV chỉ phòng mình | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| customer_id | uuid | ❌* | tồn tại trong `customers` | Khách gửi (hoặc tạo nhanh trước qua #2) |
| sender_name | string | ✅ | maxLength(255), trim non-empty | Tên người mang mẫu tới |
| department_id | uuid | ❌ | default = phòng user; **KTV bắt buộc = phòng mình** | Phòng tiếp nhận |
| received_by | uuid | ❌ | default = user hiện tại; phải cùng phòng | Người tiếp nhận (custodian ban đầu) |
| received_at | datetime | ❌ | default now; ≤ now | Ngày nhận |
| note | string | ❌ | maxLength(1000) | Ghi chú chung |

> `*` `customer_id` có thể null nếu KH nội bộ chưa tạo, nhưng `sender_name` luôn bắt buộc. `request_code` server tự sinh (BR-SAMPLE-015) — KHÔNG nhận từ client.

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "req-uuid",
    "request_code": "RQ-2026-0042",
    "customer_id": "cus-uuid",
    "sender_name": "Nguyễn Văn A",
    "department_id": "dep-uuid",
    "received_by": "user-uuid",
    "received_at": "2026-06-19T08:00:00Z",
    "note": null,
    "status": "draft",
    "sample_count": 0,
    "created_at": "2026-06-19T08:00:00Z"
  }
}
```
> `status="draft"` cho tới khi có ≥ 1 mẫu (BR-SAMPLE-023) → chuyển `active`.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | sender_name rỗng; received_at > now |
| CUSTOMER_NOT_FOUND | 404 | customer_id không tồn tại |
| FORBIDDEN | 403 | KTV tạo phiếu cho phòng khác (AC3 FR-018) |
| FORBIDDEN_ACCOUNTANT | 403 | Vai trò Kế toán (AC4 FR-018, B03) |

**Side effects:** Sinh `request_code` (unique, retry nếu trùng); ghi `audit_logs` action=`REQUEST_CREATE`.

---

### 5. GET /api/v1/test-requests/:id
**Mục đích:** Chi tiết phiếu kèm danh sách mẫu (FR-018/001).
**Auth:** Bearer JWT | **Roles:** mọi vai trò M1 | **Scope:** đọc | **Rate limit:** 60/min

**Path:** `id` = UUID phiếu.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "req-uuid",
    "request_code": "RQ-2026-0042",
    "customer": { "id": "cus-uuid", "name": "Công ty ABC", "contact": "0901234567" },
    "sender_name": "Nguyễn Văn A",
    "department_id": "dep-uuid",
    "department_name": "Hóa lý",
    "received_by_name": "Trần Thị B",
    "received_at": "2026-06-19T08:00:00Z",
    "note": null,
    "status": "active",
    "samples": [
      { "id": "sample-uuid", "sample_code": "SP-2026-0007", "status": "assigned",
        "deadline_at": "2026-06-25T17:00:00Z", "condition_status": "acceptable" },
      { "id": "sample-uuid2", "sample_code": "SP-2026-0008", "status": "received",
        "deadline_at": "2026-06-26T17:00:00Z", "condition_status": null }
    ],
    "created_at": "2026-06-19T08:00:00Z"
  }
}
```
**Errors:** `NOT_FOUND` (404), `FORBIDDEN_ACCOUNTANT` (403).

---

### 6. PATCH /api/v1/test-requests/:id
**Mục đích:** Sửa thông tin chung phiếu (FR-018). Partial update.
**Auth:** Bearer JWT | **Roles:** Admin, KTV | **Scope:** KTV chỉ phòng của phiếu | **Rate limit:** 60/min

**Request Body (≥1 field):** `customer_id`, `sender_name`, `received_by`, `received_at`, `note` — validation như #4. KHÔNG cho đổi `department_id` nếu phiếu đã có mẫu (tránh lệch scope mẫu).

**Response 200:** giống #5 (không kèm `samples` chi tiết, hoặc kèm tùy FE).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | body rỗng / field sai |
| DEPT_CHANGE_LOCKED | 422 | Đổi department_id khi phiếu đã có mẫu |
| FORBIDDEN | 403 | KTV sửa phiếu phòng khác |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán |
| NOT_FOUND | 404 | id không tồn tại |

**Side effects:** `audit_logs` action=`REQUEST_UPDATE` (detail = diff).

---

### 7. GET /api/v1/test-requests/:id/samples
**Mục đích:** Liệt kê mẫu của một phiếu (FR-001).
**Auth:** Bearer JWT | **Roles:** mọi vai trò M1 | **Scope:** đọc | **Rate limit:** 60/min

**Response 200:** list item như mảng `samples` trong #5, có pagination `meta`.
**Errors:** `NOT_FOUND` (404 nếu phiếu không tồn tại), `FORBIDDEN_ACCOUNTANT` (403).

---

### 8. POST /api/v1/test-requests/:id/samples
**Mục đích:** Thêm mẫu vào phiếu; sinh `sample_code` + barcode/QR; khởi tạo `status=received`, custodian = `received_by` của phiếu (FR-001/002).
**Auth:** Bearer JWT | **Roles:** Admin, KTV | **Scope:** KTV chỉ phòng của phiếu | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| description | string | ✅ | maxLength(500), trim non-empty | Mô tả mẫu |
| deadline_at | datetime | ✅ | **bắt buộc** (BR-SAMPLE-002); > phiếu.received_at | Hạn hoàn thành (TAT) |
| parts | string[] | ❌ | mỗi part maxLength(150) | Danh sách chỉ tiêu cần thử (phân công sau cũng được) |
| condition_status | enum | ❌ | acceptable\|not_acceptable | Tình trạng khi nhận (FR-004) |
| condition_note | string | ❌* | maxLength(500); **bắt buộc nếu not_acceptable** | Ghi chú tình trạng |

> `sample_code`, `request_id`, `department_id`, `received_by`, `status` server tự thiết lập — KHÔNG nhận từ client.

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "sample-uuid",
    "sample_code": "SP-2026-0007",
    "request_id": "req-uuid",
    "request_code": "RQ-2026-0042",
    "department_id": "dep-uuid",
    "received_by": "user-uuid",
    "received_at": "2026-06-19T08:00:00Z",
    "deadline_at": "2026-06-25T17:00:00Z",
    "description": "Mẫu nước thải đầu vào",
    "status": "received",
    "condition_status": "acceptable",
    "condition_note": null,
    "current_custodian_id": "user-uuid",
    "qr_payload": "SP-2026-0007",
    "created_at": "2026-06-19T08:05:00Z"
  }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| DEADLINE_REQUIRED | 400 | Thiếu `deadline_at` (AC6 FR-001, BR-SAMPLE-002) |
| INVALID_DEADLINE | 422 | `deadline_at` ≤ phiếu.received_at (AC3 FR-001) |
| CONDITION_REASON_REQUIRED | 400 | not_acceptable nhưng thiếu `condition_note` (BR-SAMPLE-003) |
| VALIDATION_ERROR | 400 | description rỗng |
| FORBIDDEN | 403 | KTV thêm mẫu vào phiếu phòng khác (AC4 FR-001) |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán (AC5 FR-001) |
| NOT_FOUND | 404 | phiếu không tồn tại |

**Side effects:** Sinh `sample_code` unique (retry nếu race — FR-002); khởi tạo chain of custody (custodian = received_by); nếu phiếu `draft` → chuyển `active` (BR-SAMPLE-023); `audit_logs` action=`SAMPLE_CREATE` (+ `SAMPLE_CONDITION_RECORD` nếu có tình trạng).

---

### 9. GET /api/v1/samples
**Mục đích:** Tìm/lọc mẫu đa tiêu chí: status / deadline / phòng ban / người giao (FR-001/004).
**Auth:** Bearer JWT | **Roles:** mọi vai trò M1 | **Scope:** đọc theo phạm vi | **Rate limit:** 60/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| q | string | ❌ | maxLength(100) | sample_code / mô tả |
| status | enum | ❌ | received\|assigned\|testing\|done\|overdue\|returned | Trạng thái mẫu |
| department_id | uuid | ❌ | — | Phòng ban |
| assigned_to | uuid | ❌ | — | Lọc theo người được giao |
| assigned_by | uuid | ❌ | — | Lọc theo người giao việc |
| custodian_id | uuid | ❌ | — | Người giữ hiện tại |
| request_id | uuid | ❌ | — | Mẫu thuộc phiếu nào |
| deadline_from | date | ❌ | ≤ deadline_to | Hạn từ |
| deadline_to | date | ❌ | — | Hạn đến |
| overdue_only | bool | ❌ | — | Chỉ mẫu overdue |
| page/limit | int | ❌ | pagination chuẩn | |

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "sample-uuid",
      "sample_code": "SP-2026-0007",
      "request_code": "RQ-2026-0042",
      "department_name": "Hóa lý",
      "status": "testing",
      "deadline_at": "2026-06-25T17:00:00Z",
      "is_overdue": false,
      "current_custodian_name": "KTV B",
      "assignment_count": 2,
      "approved_count": 1,
      "created_at": "2026-06-19T08:05:00Z"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 57, "hasNext": true }
}
```
**Errors:** `VALIDATION_ERROR` (400 date range), `FORBIDDEN_ACCOUNTANT` (403).

---

### 10. GET /api/v1/samples/:id
**Mục đích:** Chi tiết mẫu kèm phân công, custodian, tình trạng (FR-001).
**Auth:** Bearer JWT | **Roles:** mọi vai trò M1 | **Scope:** đọc | **Rate limit:** 60/min

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "sample-uuid",
    "sample_code": "SP-2026-0007",
    "request_id": "req-uuid",
    "request_code": "RQ-2026-0042",
    "customer_name": "Công ty ABC",
    "department_id": "dep-uuid",
    "department_name": "Hóa lý",
    "description": "Mẫu nước thải đầu vào",
    "received_at": "2026-06-19T08:00:00Z",
    "deadline_at": "2026-06-25T17:00:00Z",
    "status": "testing",
    "is_overdue": false,
    "completed_at": null,
    "condition_status": "acceptable",
    "condition_note": null,
    "current_custodian": { "id": "user-uuid", "name": "KTV B" },
    "assignments": [
      { "id": "assign-uuid", "part_name": "độ ẩm", "assigned_to": "userA-uuid",
        "assigned_to_name": "KTV A", "assigned_by_name": "Trưởng nhóm T",
        "status": "approved", "assigned_at": "2026-06-19T09:00:00Z" },
      { "id": "assign-uuid2", "part_name": "kim loại nặng", "assigned_to": "userB-uuid",
        "assigned_to_name": "KTV B", "assigned_by_name": "Trưởng nhóm T",
        "status": "result_entered", "assigned_at": "2026-06-19T09:00:00Z" }
    ],
    "can_finalize": false,
    "created_at": "2026-06-19T08:05:00Z"
  }
}
```
> `can_finalize` = true khi mọi assignment `approved` và user có quyền `sample:finalize` (gợi ý FE bật nút chốt — backend vẫn re-validate ở #32).

**Errors:** `NOT_FOUND` (404), `FORBIDDEN_ACCOUNTANT` (403).

---

### 11. PATCH /api/v1/samples/:id
**Mục đích:** Sửa mô tả/parts mẫu trước khi phân công (FR-001). Partial update.
**Auth:** Bearer JWT | **Roles:** Admin, KTV | **Scope:** KTV phòng của mẫu | **Rate limit:** 60/min

**Request Body (≥1 field):** `description`, `parts` (chỉ sửa khi chưa có assignment cho part bị xóa). `deadline_at` đổi qua #13.

**Response 200:** giống #10.

**Errors:** `VALIDATION_ERROR` (400), `FORBIDDEN` (403 phòng khác), `FORBIDDEN_ACCOUNTANT` (403), `NOT_FOUND` (404), `INVALID_STATE_TRANSITION` (422 nếu sửa mẫu đã `returned`).

**Side effects:** `audit_logs` action=`SAMPLE_UPDATE`.

---

### 12. PATCH /api/v1/samples/:id/condition
**Mục đích:** Ghi/cập nhật tình trạng mẫu khi nhận (FR-004).
**Auth:** Bearer JWT | **Roles:** Admin, KTV | **Scope:** KTV phòng của mẫu | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| condition_status | enum | ✅ | acceptable\|not_acceptable | Đạt/không đạt điều kiện |
| condition_note | string | ❌* | maxLength(500); **bắt buộc nếu not_acceptable** | Lý do |

**Response 200:**
```json
{ "success": true, "data": { "id": "sample-uuid", "condition_status": "not_acceptable", "condition_note": "Bao bì rách" } }
```
**Errors:** `CONDITION_REASON_REQUIRED` (400, AC2 FR-004), `FORBIDDEN` (403), `FORBIDDEN_ACCOUNTANT` (403), `NOT_FOUND` (404).
**Side effects:** `audit_logs` action=`SAMPLE_CONDITION_RECORD`.

---

### 13. PATCH /api/v1/samples/:id/deadline
**Mục đích:** Đặt/sửa deadline (TAT) mẫu, có audit giá trị cũ→mới (FR-012).
**Auth:** Bearer JWT | **Roles:** Admin, KTV(phòng), TN, LĐ | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| deadline_at | datetime | ✅ | > received_at (BR-SAMPLE-002) | Hạn mới |

**Response 200:**
```json
{ "success": true, "data": { "id": "sample-uuid", "deadline_at": "2026-06-28T17:00:00Z", "previous_deadline_at": "2026-06-25T17:00:00Z" } }
```
> Nếu mẫu đang `overdue` và `deadline_at` mới > now: gia hạn được; lý do trễ đã ghi vẫn giữ. Việc có đưa về `assigned/testing` hay không tùy OQ#9 (chưa chốt) — mặc định giữ `overdue`, backend ghi chú.

**Errors:** `INVALID_DEADLINE` (422, AC2 FR-012), `FORBIDDEN` (403), `FORBIDDEN_ACCOUNTANT` (403), `NOT_FOUND` (404), `INVALID_STATE_TRANSITION` (422 nếu mẫu `returned`).
**Side effects:** `audit_logs` action=`SAMPLE_DEADLINE_SET` (detail: old→new).

---

### 14. GET /api/v1/samples/:id/qr
**Mục đích:** Lấy payload barcode/QR + ảnh để dán/quét (FR-002). Payload encode `sample_code`, KHÔNG encode UUID.
**Auth:** Bearer JWT | **Roles:** mọi vai trò M1 | **Scope:** đọc | **Rate limit:** 60/min

**Query:** `format` (optional: `png` để nhận ảnh; mặc định JSON payload).

**Response 200 (JSON):**
```json
{ "success": true, "data": { "sample_code": "SP-2026-0007", "qr_payload": "SP-2026-0007", "qr_image_url": "https://minio.../presigned?...", "url_expires_at": "2026-06-19T08:15:00Z" } }
```
**Errors:** `NOT_FOUND` (404), `FORBIDDEN_ACCOUNTANT` (403).

---

### 15. GET /api/v1/samples/:id/attachments
**Mục đích:** Liệt kê file đính kèm của mẫu (FR-003).
**Auth:** Bearer JWT | **Roles:** mọi vai trò M1 | **Scope:** đọc | **Rate limit:** 60/min

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "id": "att-uuid", "owner_type": "sample", "owner_id": "sample-uuid",
      "file_name": "bien-ban-giao-mau.pdf", "mime": "application/pdf", "size": 2097152,
      "download_url": "https://minio.../presigned?...", "url_expires_at": "2026-06-19T08:15:00Z",
      "uploaded_by_name": "KTV A", "uploaded_at": "2026-06-19T08:10:00Z" }
  ]
}
```
**Errors:** `NOT_FOUND` (404), `FORBIDDEN_ACCOUNTANT` (403).
**Side effects:** Mỗi lượt tải (qua presigned URL) ghi `audit_logs` action=`SAMPLE_ATTACH_DOWNLOAD` (R15) — backend ghi khi cấp presigned URL.

---

### 16. POST /api/v1/samples/:id/attachments
**Mục đích:** Upload ảnh mẫu / chứng từ gửi mẫu (FR-003). Multipart → MinIO.
**Auth:** Bearer JWT | **Roles:** Admin, KTV(phòng) | **Scope:** ghi theo phòng | **Rate limit:** 30/min

`Content-Type: multipart/form-data`.

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| file | binary | ✅ | MIME ∈ {PDF, PNG, JPG, XLSX, CSV}; size ≤ giới hạn (BR-SAMPLE-012) | File đính kèm |

**Response 201:**
```json
{ "success": true, "data": { "id": "att-uuid", "owner_type": "sample", "owner_id": "sample-uuid",
  "file_name": "bien-ban-giao-mau.pdf", "mime": "application/pdf", "size": 2097152, "uploaded_at": "2026-06-19T08:10:00Z" } }
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| INVALID_FILE_TYPE | 422 | MIME ngoài whitelist (AC2 FR-003) |
| FILE_TOO_LARGE | 422 | Vượt giới hạn (AC4 FR-003) |
| FORBIDDEN | 403 | KTV phòng khác (AC3 FR-003) |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán |
| NOT_FOUND | 404 | mẫu không tồn tại |

**Side effects:** Lưu MinIO + `attachments` (owner_type=`sample`); `audit_logs` action=`SAMPLE_ATTACH_UPLOAD`.

---

### 17. GET /api/v1/test-requests/:id/attachments
**Mục đích:** Liệt kê file đính kèm chung của phiếu (FR-003). Giống #15 nhưng `owner_type=test_request`.
**Auth/Roles/Scope:** như #15.
**Errors:** `NOT_FOUND` (404), `FORBIDDEN_ACCOUNTANT` (403).

---

### 18. POST /api/v1/test-requests/:id/attachments
**Mục đích:** Upload chứng từ chung của lô (FR-003). Giống #16 nhưng `owner_type=test_request`.
**Auth:** Admin, KTV(phòng của phiếu) | **Rate limit:** 30/min
**Errors/Side effects:** như #16 (`audit_logs` action=`REQUEST_ATTACH_UPLOAD`).

---

### 19. GET /api/v1/samples/:id/assignments
**Mục đích:** Liệt kê phân công của mẫu (FR-005).
**Auth:** Bearer JWT | **Roles:** mọi vai trò M1 | **Scope:** đọc | **Rate limit:** 60/min

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "id": "assign-uuid", "sample_id": "sample-uuid", "part_name": "độ ẩm",
      "assigned_to": "userA-uuid", "assigned_to_name": "KTV A",
      "assigned_by": "userT-uuid", "assigned_by_name": "Trưởng nhóm T",
      "status": "approved", "assigned_at": "2026-06-19T09:00:00Z",
      "has_result": true }
  ]
}
```
**Errors:** `NOT_FOUND` (404), `FORBIDDEN_ACCOUNTANT` (403).

---

### 20. POST /api/v1/samples/:id/assignments
**Mục đích:** Phân công phần việc cho KTV (FR-005). Mẫu `received` → `assigned`.
**Auth:** Bearer JWT | **Roles:** **Trưởng nhóm phòng đó**, Ban lãnh đạo, Admin (`sample:assign`) | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| part_name | string | ✅ | maxLength(150), trim non-empty | Chỉ tiêu/hạng mục |
| assigned_to | uuid | ✅ | tồn tại; **cùng phòng ban với mẫu** (BR-SAMPLE-006) | KTV được giao |

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "assign-uuid", "sample_id": "sample-uuid", "part_name": "độ ẩm",
    "assigned_to": "userA-uuid", "assigned_by": "userT-uuid",
    "status": "assigned", "assigned_at": "2026-06-19T09:00:00Z",
    "sample_status_after": "assigned"
  }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | part_name rỗng |
| ASSIGNEE_OUT_OF_DEPT | 422 | `assigned_to` khác phòng mẫu (AC2 FR-005, BR-SAMPLE-006) |
| ASSIGNEE_NOT_FOUND | 404 | `assigned_to` không tồn tại |
| INVALID_STATE_TRANSITION | 422 | Mẫu đã `done`/`returned` (AC4 FR-005, BR-SAMPLE-001) |
| FORBIDDEN | 403 | KTV thường (không phải TN) phân công (AC3 FR-005, BR-SAMPLE-022) |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán |
| NOT_FOUND | 404 | mẫu không tồn tại |

**Side effects:** Tạo `sample_assignments` (status=assigned); nếu mẫu `received` → chuyển `assigned` (audit `SAMPLE_STATE_CHANGE`); `notifications` type=`SAMPLE_ASSIGNED` cho assignee; `audit_logs` action=`SAMPLE_ASSIGN`.

---

### 21. DELETE /api/v1/assignments/:id
**Mục đích:** Hủy phân công khi chưa nhập kết quả (FR-005).
**Auth:** Bearer JWT | **Roles:** Trưởng nhóm phòng đó, LĐ, Admin | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Response 204:** No content.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| RESULT_EXISTS | 422 | Phân công đã có kết quả nhập — không hủy được (sửa = revise) |
| FORBIDDEN | 403 | Không có quyền `sample:assign` |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán |
| NOT_FOUND | 404 | assignment không tồn tại |

**Side effects:** `audit_logs` action=`SAMPLE_ASSIGN_CANCEL`. Nếu mẫu không còn assignment nào → cân nhắc đưa về `received` (backend quyết, có audit state change).

---

### 22. POST /api/v1/samples/:id/handovers
**Mục đích:** Chuyển giao mẫu vật lý (handover) kèm lý do; ghi chain of custody bất biến; cập nhật custodian (FR-006).
**Auth:** Bearer JWT | **Roles:** người giữ hiện tại / Trưởng nhóm / Admin | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| to_user | uuid | ✅ | tồn tại; **cùng phòng ban mẫu**; ≠ custodian hiện tại | Người nhận mẫu |
| reason | string | ✅ | maxLength(500), trim non-empty | Lý do chuyển |

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "handover-uuid", "sample_id": "sample-uuid",
    "from_user": "userA-uuid", "from_user_name": "KTV A",
    "to_user": "userB-uuid", "to_user_name": "KTV B",
    "reason": "Chuyển sang đo phổ", "at": "2026-06-20T10:00:00Z",
    "current_custodian_id": "userB-uuid"
  }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| NOT_CURRENT_CUSTODIAN | 403 | User không phải custodian hiện tại & không có quyền điều phối (AC2 FR-006, BR-SAMPLE-007) |
| HANDOVER_OUT_OF_DEPT | 422 | `to_user` ngoài phòng mẫu (AC3 FR-006) |
| INVALID_HANDOVER | 422 | `to_user` = custodian hiện tại (chuyển vô nghĩa) |
| INVALID_STATE_TRANSITION | 422 | Mẫu đã `returned` (A4 FR-006) |
| VALIDATION_ERROR | 400 | reason rỗng |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán |
| NOT_FOUND | 404 | mẫu / to_user không tồn tại |

**Side effects:** Ghi `sample_handovers` (immutable); cập nhật `current_custodian_id`; `notifications` type=`SAMPLE_HANDOVER` cho người nhận; `audit_logs` action=`SAMPLE_HANDOVER`.
**Lưu ý immutable:** KHÔNG có PUT/PATCH/DELETE trên handover (BR-SAMPLE-017) — sửa nhầm = handover đính chính mới.

---

### 23. GET /api/v1/samples/:id/custody-chain
**Mục đích:** Xem chuỗi hành trình mẫu — timeline ai giữ, từ khi nào đến khi nào, lý do (FR-007, 17025 §7.4).
**Auth:** Bearer JWT | **Roles:** mọi vai trò M1 | **Scope:** đọc | **Rate limit:** 60/min

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "custodian_id": "recv-uuid", "custodian_name": "Trần Thị B (tiếp nhận)",
      "from": "2026-06-19T08:00:00Z", "to": "2026-06-20T10:00:00Z", "reason": "Tiếp nhận ban đầu" },
    { "custodian_id": "userA-uuid", "custodian_name": "KTV A",
      "from": "2026-06-20T10:00:00Z", "to": "2026-06-21T14:00:00Z", "reason": "Chuyển sang đo phổ" },
    { "custodian_id": "userB-uuid", "custodian_name": "KTV B",
      "from": "2026-06-21T14:00:00Z", "to": null, "reason": "Đo kim loại nặng", "is_current": true }
  ]
}
```
> `to=null` + `is_current=true` = đoạn hiện tại. Nếu chưa handover → 1 đoạn duy nhất (received_by giữ từ received_at tới hiện tại — AC2 FR-007).

**Errors:** `NOT_FOUND` (404), `FORBIDDEN_ACCOUNTANT` (403, AC3 FR-007).

---

### 24. GET /api/v1/assignments/:id/results
**Mục đích:** Lấy kết quả (version hiện tại) của một phần việc, lọc theo phạm vi xem (FR-008/011).
**Auth:** Bearer JWT | **Roles:** theo phạm vi đọc (§0.7) | **Scope:** đọc | **Rate limit:** 60/min

**Response 200 (user có quyền xem):**
```json
{
  "success": true,
  "data": {
    "id": "result-uuid", "assignment_id": "assign-uuid", "part_name": "độ ẩm",
    "version": 1, "is_current": true,
    "result_data": { "value": 12.5, "unit": "%", "method": "TCVN-xxx" },
    "entered_by_name": "KTV A", "entered_at": "2026-06-20T11:00:00Z",
    "approved_by_name": "Trưởng nhóm T", "approved_at": "2026-06-21T09:00:00Z",
    "approval_status": "approved",
    "attachments": [ { "id": "att-uuid", "file_name": "raw-icp.xlsx", "mime": "...", "size": 3145728 } ]
  }
}
```
> `approval_status` ∈ `pending` (chưa duyệt) / `approved`. Nếu kết quả `pending` và user KHÔNG thuộc nhóm xem trước (người nhập/TN/Admin/LĐ) → 200 với `data: null` + `meta.reason="NOT_PUBLISHED"` (BR-SAMPLE-021), KHÔNG lộ nội dung.

**Errors:** `NOT_FOUND` (404), `FORBIDDEN_ACCOUNTANT` (403).

---

### 25. POST /api/v1/assignments/:id/results
**Mục đích:** Nhập kết quả phần việc được giao (FR-008). Chỉ assignee/Admin. Mẫu `assigned` → `testing` (lần đầu).
**Auth:** Bearer JWT | **Roles:** assignee (`assigned_to`), Admin | **Scope:** ghi (được giao) | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| result_data | object(JSONB) | ✅ | non-empty; hợp lệ theo biểu mẫu chỉ tiêu | Dữ liệu kết quả |
| note | string | ❌ | maxLength(1000) | Ghi chú |

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "result-uuid", "assignment_id": "assign-uuid", "version": 1,
    "result_data": { "value": 12.5, "unit": "%" },
    "entered_by": "userA-uuid", "entered_at": "2026-06-20T11:00:00Z",
    "approval_status": "pending", "is_current": true,
    "assignment_status_after": "result_entered",
    "sample_status_after": "testing"
  }
}
```
> Kết quả ở `pending` — CHƯA công khai toàn lab (BR-SAMPLE-021).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| NOT_ASSIGNEE | 403 | User không phải người được giao part (AC2 FR-008, BR-SAMPLE-008) |
| RESULT_LOCKED | 422 | Part đã có kết quả `approved` — sửa = revise (#30) (AC3 FR-008, BR-SAMPLE-010) |
| VALIDATION_ERROR | 400 | `result_data` rỗng/sai (AC4 FR-008) |
| INVALID_STATE_TRANSITION | 422 | Mẫu `done`/`returned` |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán (AC5 FR-008) |
| NOT_FOUND | 404 | assignment không tồn tại |

**Side effects:** Lưu `sample_results` (version=1, approved_by=null, is_current=true); assignment → `result_entered`; nếu mẫu `assigned` → `testing` (audit `SAMPLE_STATE_CHANGE`); `audit_logs` action=`SAMPLE_RESULT_ENTER`.

---

### 26. POST /api/v1/results/:id/attachments
**Mục đích:** Upload raw data cho kết quả phần việc (FR-009, §7.5). Multipart → MinIO.
**Auth:** Bearer JWT | **Roles:** người nhập kết quả đó (entered_by), Admin | **Scope:** ghi (được giao) | **Rate limit:** 30/min

`Content-Type: multipart/form-data`. Field `file` — whitelist + size như #16.

**Response 201:**
```json
{ "success": true, "data": { "id": "att-uuid", "owner_type": "sample_result", "owner_id": "result-uuid",
  "file_name": "raw-icp.xlsx", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "size": 3145728, "uploaded_at": "2026-06-20T11:05:00Z" } }
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| INVALID_FILE_TYPE | 422 | MIME ngoài whitelist (AC2 FR-009) |
| FILE_TOO_LARGE | 422 | Vượt giới hạn |
| RESULT_LOCKED | 422 | Đính kèm vào kết quả `approved` (OQ#8 — mặc định chặn, sửa = revise) |
| FORBIDDEN | 403 | Không phải người nhập kết quả (AC3 FR-009) |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán |
| NOT_FOUND | 404 | kết quả không tồn tại |

**Side effects:** Lưu MinIO + `attachments` (owner_type=`sample_result`); `audit_logs` action=`SAMPLE_RESULT_ATTACH`.

---

### 27. GET /api/v1/results/:id/attachments
**Mục đích:** Liệt kê/tải raw data của kết quả (FR-009), lọc theo phạm vi đọc kết quả (§0.7).
**Auth:** Bearer JWT | **Roles:** theo phạm vi đọc | **Scope:** đọc | **Rate limit:** 60/min

**Response 200:** list attachments với `download_url` presigned (như #15).
> Nếu kết quả `pending` và user ngoài nhóm xem trước → 403 `RESULT_NOT_PUBLISHED` (không lộ raw data chưa duyệt).

**Errors:** `RESULT_NOT_PUBLISHED` (403), `NOT_FOUND` (404), `FORBIDDEN_ACCOUNTANT` (403).
**Side effects:** Mỗi lượt tải ghi `audit_logs` action=`SAMPLE_RESULT_ATTACH_DOWNLOAD` (R15).

---

### 28. POST /api/v1/results/:id/approve
**Mục đích:** Duyệt kết quả phần việc (FR-010, §7.8). Sau approve: bất biến + công khai nội bộ. Tách nhập–duyệt.
**Auth:** Bearer JWT | **Roles:** **Trưởng nhóm phòng đó**, Ban lãnh đạo, Admin (`sample_result:approve`) | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| note | string | ❌ | maxLength(500) | Ghi chú duyệt |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "result-uuid", "assignment_id": "assign-uuid",
    "version": 1, "approval_status": "approved",
    "approved_by": "userT-uuid", "approved_at": "2026-06-21T09:00:00Z",
    "is_published": true,
    "assignment_status_after": "approved",
    "sample_status_after": "testing",
    "sample_can_finalize": true
  }
}
```
> `sample_status_after` vẫn `testing` dù mọi part approved (KHÔNG auto-done — OQ#2). `sample_can_finalize=true` báo FE bật nút chốt (#32).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| SELF_APPROVAL_FORBIDDEN | 403 | Approver = người nhập kết quả (AC2 FR-010, BR-SAMPLE-011) |
| NO_RESULT_TO_APPROVE | 422 | Phần việc chưa có kết quả (A2 FR-010) |
| RESULT_ALREADY_APPROVED | 422 | Kết quả version này đã approved |
| FORBIDDEN | 403 | KTV thường không có `sample_result:approve` (AC7 FR-010, BR-SAMPLE-022) |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán |
| NOT_FOUND | 404 | kết quả không tồn tại |

**Side effects:** Set `approved_by`/`approved_at`/`is_current=true`; khóa bất biến; **mở công khai nội bộ** (BR-SAMPLE-021); assignment → `approved`; `audit_logs` action=`SAMPLE_RESULT_APPROVE`.

---

### 29. POST /api/v1/results/:id/return
**Mục đích:** Trả lại kết quả để KTV sửa (FR-010, A5) — khi chưa từng approved. Đưa assignment về `in_progress`/`assigned`.
**Auth:** Bearer JWT | **Roles:** Trưởng nhóm phòng đó, LĐ, Admin | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| reason | string | ✅ | maxLength(500), trim non-empty | Lý do trả lại |

**Response 200:**
```json
{ "success": true, "data": { "id": "result-uuid", "assignment_status_after": "assigned", "approval_status": "returned" } }
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| RESULT_ALREADY_APPROVED | 422 | Đã approved — phải dùng revise (#30) thay vì return |
| VALIDATION_ERROR | 400 | reason rỗng |
| FORBIDDEN | 403 | Không có quyền duyệt |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán |
| NOT_FOUND | 404 | kết quả không tồn tại |

**Side effects:** `audit_logs` action=`SAMPLE_RESULT_RETURN` (kèm lý do). Không tạo version mới (chưa từng approved).

---

### 30. POST /api/v1/results/:id/revisions
**Mục đích:** Tạo phiên bản sửa của kết quả đã approved (FR-010, immutable §8.4). Version+1, giữ bản cũ, lý do bắt buộc.
**Auth:** Bearer JWT | **Roles:** người nhập kết quả / Trưởng nhóm phòng đó, Admin | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| result_data | object(JSONB) | ✅ | non-empty | Dữ liệu kết quả mới |
| reason | string | ✅ | maxLength(500), trim non-empty | **Lý do sửa bắt buộc** (§8.4) |

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "result-uuid-v2", "assignment_id": "assign-uuid",
    "version": 2, "is_current": true,
    "approval_status": "pending", "is_published": false,
    "previous_version_id": "result-uuid", "previous_version": 1,
    "revision_reason": "Phát hiện sai số hiệu chuẩn"
  }
}
```
> Version mới ở `pending` (tạm rút công khai cho tới khi duyệt lại #28). Bản version cũ giữ nguyên vẹn, `is_current=false`.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| REVISION_REASON_REQUIRED | 400 | Thiếu `reason` (AC5 FR-010, BR-SAMPLE-010) |
| RESULT_NOT_APPROVED | 422 | Bản hiện tại chưa approved — sửa trực tiếp được, không cần revise |
| RESULT_NOT_OWNER | 403 | Không phải người nhập/TN/Admin |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán |
| NOT_FOUND | 404 | kết quả không tồn tại |

**Side effects:** Tạo `sample_results` version+1; bản cũ giữ; assignment → `result_entered`; mẫu nếu `done`/`returned` cần xét lại (tùy nghiệp vụ — phiếu in lại đánh dấu "bản sửa đổi"); `audit_logs` action=`SAMPLE_RESULT_REVISE` (kèm lý do).

> **Lưu ý:** KHÔNG có endpoint PUT/PATCH/DELETE sửa kết quả approved (BR-SAMPLE-010). Mọi sửa qua endpoint này.

---

### 31. GET /api/v1/samples/:id/results
**Mục đích:** Tổng hợp kết quả toàn mẫu (mọi phần việc), lọc theo phạm vi xem (FR-011, OQ#3).
**Auth:** Bearer JWT | **Roles:** mọi vai trò M1 | **Scope:** đọc theo phạm vi (§0.7) | **Rate limit:** 60/min

**Response 200:**
```json
{
  "success": true,
  "data": {
    "sample_id": "sample-uuid", "sample_code": "SP-2026-0007",
    "results": [
      { "assignment_id": "assign-uuid", "part_name": "độ ẩm", "version": 1,
        "approval_status": "approved", "is_published": true,
        "result_data": { "value": 12.5, "unit": "%" },
        "entered_by_name": "KTV A", "approved_by_name": "Trưởng nhóm T" },
      { "assignment_id": "assign-uuid2", "part_name": "kim loại nặng",
        "approval_status": "pending", "is_published": false,
        "result_data": null, "note": "Chưa có kết quả công khai" }
    ]
  }
}
```
> Phần `pending` chỉ hiện `result_data` cho người nhập/TN/Admin/LĐ; người ngoài nhóm nhận `result_data: null` + ghi chú "chưa có kết quả công khai" (AC2 FR-011, BR-SAMPLE-021).

**Errors:** `NOT_FOUND` (404), `FORBIDDEN_ACCOUNTANT` (403, AC5 FR-011).

---

### 32. POST /api/v1/samples/:id/finalize
**Mục đích:** Trưởng nhóm chốt hoàn thành mẫu — `testing/overdue → done` thủ công (FR-019, OQ#2). KHÔNG auto.
**Auth:** Bearer JWT | **Roles:** **Trưởng nhóm phòng đó**, Ban lãnh đạo, Admin (`sample:finalize`) | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| note | string | ❌ | maxLength(500) | Ghi chú chốt |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "sample-uuid", "sample_code": "SP-2026-0007",
    "status": "done", "completed_at": "2026-06-21T10:00:00Z",
    "was_overdue": false, "is_late": false,
    "approved_parts": ["độ ẩm", "kim loại nặng"]
  }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| RESULTS_NOT_APPROVED | 422 | Còn ≥1 assignment chưa `approved` (AC3 FR-019, BR-SAMPLE-020) |
| OVERDUE_REASON_REQUIRED | 422 | Mẫu `overdue` chưa nhập lý do trễ (AC5 FR-019, BR-SAMPLE-009) |
| INVALID_STATE_TRANSITION | 422 | Mẫu đã `done`/`returned` (A4 FR-019, BR-SAMPLE-001) |
| FORBIDDEN | 403 | KTV thường không có `sample:finalize` (AC4 FR-019, BR-SAMPLE-022) |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán |
| NOT_FOUND | 404 | mẫu không tồn tại |

**Side effects:** Set `completed_at`=now, `status='done'` (audit `SAMPLE_STATE_CHANGE` from→to); `audit_logs` action=`SAMPLE_FINALIZE` (kèm danh sách part approved). `is_late = completed_at > deadline_at` (cho on-time rate — BR-SAMPLE-019).

---

### 33. POST /api/v1/samples/:id/overdue-reasons
**Mục đích:** Nhập lý do trễ hạn cho mẫu `overdue` (FR-014, R9). Bắt buộc trước khi finalize/xuất phiếu.
**Auth:** Bearer JWT | **Roles:** KTV(phòng)/TN, Admin | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| reason | string | ✅ | maxLength(1000), trim non-empty (NOT NULL) | Lý do trễ |

**Response 201:**
```json
{ "success": true, "data": { "id": "reason-uuid", "sample_id": "sample-uuid",
  "reason": "Máy đo hỏng chờ sửa", "by": "user-uuid", "at": "2026-06-26T09:00:00Z" } }
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | reason rỗng |
| SAMPLE_NOT_OVERDUE | 422 | Mẫu không ở trạng thái `overdue` (không cần lý do) |
| FORBIDDEN | 403 | KTV phòng khác |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán |
| NOT_FOUND | 404 | mẫu không tồn tại |

**Side effects:** Ghi `overdue_reasons` (reason+by+at); `audit_logs` action=`SAMPLE_OVERDUE_REASON`.

---

### 34. GET /api/v1/samples/overdue
**Mục đích:** Danh sách mẫu sắp tới hạn / đã quá hạn để theo dõi (FR-013/014).
**Auth:** Bearer JWT | **Roles:** mọi vai trò M1 | **Scope:** đọc theo phạm vi | **Rate limit:** 60/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| mode | enum | ❌ | due_soon\|overdue (default overdue) | Sắp hạn / đã quá hạn |
| within_days | int | ❌ | 1..30 (default 3) | Khi mode=due_soon: trong N ngày |
| department_id | uuid | ❌ | — | |
| page/limit | int | ❌ | pagination chuẩn | |

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "id": "sample-uuid", "sample_code": "SP-2026-0007", "department_name": "Hóa lý",
      "status": "overdue", "deadline_at": "2026-06-25T17:00:00Z", "days_overdue": 1,
      "has_overdue_reason": false, "assignee_names": ["KTV A", "KTV B"] }
  ],
  "meta": { "page": 1, "limit": 20, "total": 4, "hasNext": false }
}
```
**Errors:** `VALIDATION_ERROR` (400), `FORBIDDEN_ACCOUNTANT` (403).

---

### 35. GET /api/v1/samples/:id/result-report.pdf
**Mục đích:** Xuất phiếu kết quả thử nghiệm PDF (sync) — mã phiếu/mã mẫu/QR, chỉ kết quả approved; đánh dấu mẫu `done → returned` (FR-016, §7.8).
**Auth:** Bearer JWT | **Roles:** Trưởng nhóm/LĐ/Admin (ban hành); KTV tải nếu có quyền | **Scope:** ghi/đọc theo phòng | **Rate limit:** 10/min

**Query:** `reissue` (bool, optional — in lại bản sao sau khi đã returned, AC A3 FR-016).

**Response 200:** `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="result-SP-2026-0007.pdf"`. Body = binary PDF chứa: header lab + công nhận, `sample_code`+QR, `request_code`, khách gửi, tình trạng mẫu, danh sách chỉ tiêu + kết quả approved (version hiện tại), người thực hiện, người duyệt, ngày.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| SAMPLE_NOT_FINALIZED | 422 | Mẫu chưa `done` (chưa chốt / còn part chưa approved) (AC2 FR-016) |
| OVERDUE_REASON_REQUIRED | 422 | Mẫu từng `overdue` chưa nhập lý do trễ (AC3 FR-016) |
| FORBIDDEN | 403 | KTV không có quyền ban hành (tùy cấu hình) |
| FORBIDDEN_ACCOUNTANT | 403 | Kế toán (AC4 FR-016) |
| NOT_FOUND | 404 | mẫu không tồn tại |

**Side effects:** Lần đầu xuất → mẫu `done → returned` (audit `SAMPLE_STATE_CHANGE`); lưu PDF vào `attachments` (owner_type=`sample`, loại `result_report`); `audit_logs` action=`SAMPLE_REPORT_EXPORT` (đếm lượt tải — R15, AC5). `reissue=true` không đổi trạng thái, chỉ ghi audit lượt tải.

---

### 36. GET /api/v1/reports/sample-on-time
**Mục đích:** Báo cáo on-time rate theo kỳ/phòng/người (FR-015).
**Auth:** Bearer JWT | **Roles:** Ban lãnh đạo, Admin, KTV(phòng) | **Scope:** đọc theo phạm vi | **Rate limit:** 10/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| date_from | date | ✅ | ≤ date_to | Kỳ từ (theo completed_at) |
| date_to | date | ✅ | — | Kỳ đến |
| group_by | enum | ❌ | department\|user (default department) | Chiều tổng hợp |
| department_id | uuid | ❌ | KTV bị ép = phòng mình | Lọc phòng |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "period": { "from": "2026-05-01", "to": "2026-05-31" },
    "summary": { "total_done": 20, "on_time": 18, "late": 2, "on_time_rate": 90.0 },
    "breakdown": [
      { "group": "Hóa lý", "total_done": 12, "on_time": 11, "late": 1, "on_time_rate": 91.7 }
    ],
    "late_samples": [
      { "sample_code": "SP-2026-0003", "deadline_at": "2026-05-20T17:00:00Z",
        "completed_at": "2026-05-22T10:00:00Z", "overdue_reason": "Máy đo hỏng chờ sửa" }
    ]
  }
}
```
> `on_time_rate` = on_time / total_done × 100, làm tròn 1 chữ số. Mẫu `completed_at > deadline_at` tính "late" (BR-SAMPLE-019). Không có dữ liệu → `summary` với `total_done=0` + thông báo (AC1 FR-015 A1).

**Errors:** `VALIDATION_ERROR` (400 date range), `FORBIDDEN_ACCOUNTANT` (403, AC3 FR-015).

---

### 37. POST /api/v1/admin/crons/sample-due-soon/run
**Mục đích:** Chạy thủ công CRON-1 (nhắc mẫu sắp tới hạn) để test/vận hành (FR-013).
**Auth:** Bearer JWT | **Roles:** Admin | **Scope:** toàn HT | **Rate limit:** 10/min

**Response 200:**
```json
{ "success": true, "data": { "scanned": 120, "notifications_created": 8, "skipped_duplicate": 3, "ran_at": "2026-06-19T07:00:00Z" } }
```
> Idempotent: chống trùng mỗi mẫu × mốc/ngày (BR-SAMPLE-018); chạy dưới Redis lock.
**Errors:** `FORBIDDEN` (403 non-Admin), `LOCK_HELD` (409 nếu cron đang chạy).

---

### 38. POST /api/v1/admin/crons/sample-overdue/run
**Mục đích:** Chạy thủ công CRON-2 (đánh dấu trễ hạn) để test/vận hành (FR-014).
**Auth:** Bearer JWT | **Roles:** Admin | **Scope:** toàn HT | **Rate limit:** 10/min

**Response 200:**
```json
{ "success": true, "data": { "scanned": 120, "marked_overdue": 4, "notifications_created": 4, "ran_at": "2026-06-19T00:30:00Z" } }
```
> Chuyển `{received,assigned,testing} → overdue` cho mẫu quá `deadline_at` chưa done; idempotent; Redis lock.
**Errors:** `FORBIDDEN` (403 non-Admin), `LOCK_HELD` (409).

---

## 3. Danh mục Error Codes M1

| Code | HTTP | Ý nghĩa | FR/BR |
|------|------|---------|-------|
| UNAUTHORIZED | 401 | Thiếu/sai JWT | §0.3 |
| FORBIDDEN | 403 | Thiếu quyền / sai phạm vi phòng ban (KTV thường phân/duyệt/chốt; ghi chéo phòng) | BR-022, BR-014 |
| FORBIDDEN_ACCOUNTANT | 403 | Vai trò Kế toán truy cập M1 (cấm toàn bộ) | BR-014, B03 |
| NOT_FOUND | 404 | Resource (phiếu/mẫu/assignment/result/customer) không tồn tại | nhiều FR |
| VALIDATION_ERROR | 400 | Sai kiểu/khoảng/rỗng field, body rỗng, date range sai | nhiều FR |
| RATE_LIMIT_EXCEEDED | 429 | Vượt rate limit | §0.5 |
| INTERNAL_ERROR | 500 | Lỗi server / transaction rollback / sinh mã thất bại sau N retry | FR-002 |
| **State machine** | | | |
| INVALID_STATE_TRANSITION | 422 | Chuyển trạng thái ngoài whitelist (vd received→done, returned→*, auto-done) | FR-017, BR-001 |
| **Tiếp nhận / mẫu** | | | |
| CUSTOMER_NOT_FOUND | 404 | customer_id không tồn tại khi tạo phiếu | FR-018 |
| DEPT_CHANGE_LOCKED | 422 | Đổi phòng phiếu khi đã có mẫu | FR-018 |
| DEADLINE_REQUIRED | 400 | Thiếu deadline khi thêm mẫu | FR-001, BR-002 |
| INVALID_DEADLINE | 422 | deadline ≤ received_at | FR-001/012, BR-002 |
| CONDITION_REASON_REQUIRED | 400 | not_acceptable thiếu condition_note | FR-004, BR-003 |
| **File** | | | |
| INVALID_FILE_TYPE | 422 | MIME ngoài whitelist | FR-003/009, BR-012 |
| FILE_TOO_LARGE | 422 | Vượt giới hạn dung lượng | FR-003/009, BR-012 |
| **Phân công / handover** | | | |
| ASSIGNEE_OUT_OF_DEPT | 422 | Người được giao khác phòng mẫu | FR-005, BR-006 |
| ASSIGNEE_NOT_FOUND | 404 | assigned_to không tồn tại | FR-005 |
| RESULT_EXISTS | 422 | Hủy phân công đã có kết quả | FR-005 |
| NOT_CURRENT_CUSTODIAN | 403 | Không phải người giữ mẫu hiện tại | FR-006, BR-007 |
| HANDOVER_OUT_OF_DEPT | 422 | Người nhận handover ngoài phòng | FR-006 |
| INVALID_HANDOVER | 422 | Chuyển cho chính custodian hiện tại | FR-006 |
| **Kết quả / duyệt** | | | |
| NOT_ASSIGNEE | 403 | Không phải người được giao nhập kết quả | FR-008, BR-008 |
| RESULT_LOCKED | 422 | Sửa trực tiếp kết quả approved (phải revise) | FR-008/010, BR-010 |
| RESULT_NOT_PUBLISHED | 403 | Xem kết quả/raw data chưa approved ngoài nhóm xem trước | FR-009/011, BR-021 |
| SELF_APPROVAL_FORBIDDEN | 403 | Người nhập tự duyệt kết quả của mình | FR-010, BR-011 |
| NO_RESULT_TO_APPROVE | 422 | Duyệt khi chưa có kết quả | FR-010 |
| RESULT_ALREADY_APPROVED | 422 | Duyệt/return kết quả đã approved | FR-010 |
| RESULT_NOT_APPROVED | 422 | Revise kết quả chưa approved (sửa trực tiếp được) | FR-010 |
| RESULT_NOT_OWNER | 403 | Revise kết quả không phải của mình / không phải TN | FR-010 |
| REVISION_REASON_REQUIRED | 400 | Tạo phiên bản sửa thiếu lý do | FR-010, BR-010 |
| **Chốt / trễ hạn / xuất phiếu** | | | |
| RESULTS_NOT_APPROVED | 422 | Chốt mẫu khi còn part chưa approved | FR-019, BR-020 |
| OVERDUE_REASON_REQUIRED | 422 | Chốt/xuất phiếu mẫu overdue chưa nhập lý do trễ | FR-014/019/016, BR-009 |
| SAMPLE_NOT_OVERDUE | 422 | Nhập lý do trễ cho mẫu không overdue | FR-014 |
| SAMPLE_NOT_FINALIZED | 422 | Xuất phiếu khi mẫu chưa done | FR-016 |
| **Cron** | | | |
| LOCK_HELD | 409 | Cron đang chạy (Redis lock) khi gọi chạy thủ công | FR-013/014, BR-018 |

---

## 4. Ghi chú RBAC (tóm tắt — chi tiết §0.6/§0.7)

1. **Kế toán cấm toàn M1:** mọi endpoint trả `FORBIDDEN_ACCOUNTANT` (403) ở tầng API (B03, BR-SAMPLE-014). KHÔNG có ngoại lệ.
2. **Trưởng nhóm phòng đó / Admin / Ban lãnh đạo** mới có:
   - `sample:assign` → #20 (phân công), #21 (hủy phân công)
   - `sample_result:approve` → #28 (duyệt), #29 (trả lại), một phần #30 (revise)
   - `sample:finalize` → #32 (chốt done), #35 (ban hành phiếu PDF)
   KTV thường gọi các endpoint này → 403 `FORBIDDEN`.
3. **Phạm vi phòng ban:** KTV ghi (tạo phiếu/mẫu, đính kèm, deadline, handover, nhập kết quả, lý do trễ) chỉ trong phòng mình → ghi chéo phòng = 403 `FORBIDDEN`. Đọc: kết quả approved công khai toàn lab.
4. **Người được giao mới nhập kết quả** (#25/#26): `assignment.assigned_to` = user hoặc Admin → ngược lại 403 `NOT_ASSIGNEE`.
5. **Tách nhập–duyệt** (#28): approver ≠ entered_by → ngược lại 403 `SELF_APPROVAL_FORBIDDEN`.
6. **Người giữ mẫu hiện tại** (#22): chỉ custodian/TN/Admin chuyển giao → ngược lại 403 `NOT_CURRENT_CUSTODIAN`.
7. **Phạm vi xem kết quả** (OQ#3, #24/#27/#31): approved = công khai; pending = chỉ entered_by/TN/Admin/LĐ.

---

## 5. Ghi chú phi chức năng

- **Pagination:** mọi list (`page`/`limit` default 20/max 100), `meta` luôn có `total`/`page`/`limit`/`hasNext` (§0.4).
- **CorrelationId / Audit:** mọi request gắn `X-Correlation-Id`; mọi thao tác ghi (CRUD phiếu/mẫu/phân công/handover/kết quả/duyệt/chốt/trễ hạn/xuất phiếu/chuyển trạng thái) ghi `audit_logs` với `user, action, resource, resource_id, correlation_id, ip, at, detail` (BR-SAMPLE-013, §8.4). Lượt tải file/PDF cũng audit (R15).
- **Rate limit:** 60/min nghiệp vụ; 30/min upload; 10/min xuất PDF + báo cáo + cron thủ công (§0.5).
- **Validation:** sanitize input ở tầng API; số trong JSONB result_data theo biểu mẫu chỉ tiêu; date theo ISO 8601; field bắt buộc kiểm trước khi xử lý (rule api.md).
- **Upload MinIO:** multipart qua API; whitelist MIME (PDF/PNG/JPG/XLSX/CSV); size ≤ giới hạn (OQ#6); tải về qua presigned URL TTL 15 phút; không lưu binary trong DB (§0.8).
- **Immutable:** handover & kết quả approved không có endpoint sửa/xóa trực tiếp (§0.9, BR-010/017).
- **Mã không lộ tuần tự:** `request_code`/`sample_code` hiển thị; `id` (UUID) định danh URL; QR encode `sample_code` không encode UUID (BR-SAMPLE-015, CONSTRAINT-5).
- **Hiệu năng (NFR):** list/search P95 < 500ms; xuất PDF sync < 3000ms; cần index trên `samples(status, deadline_at)`, `samples(department_id)`, `sample_assignments(assigned_to)`, `samples(request_id)`, unique trên `sample_code`/`request_code` (schema-designer enforce).
- **Cron:** CRON-1 (07:00 due-soon) + CRON-2 (00:30 overdue) chạy APScheduler dưới Redis lock, idempotent (BR-SAMPLE-018); chạy thủ công qua #37/#38 cho test.

---

## 6. Traceability: Endpoint → FR SRS M1

| FR | Mô tả FR | Endpoint(s) |
|----|----------|-------------|
| FR-SAMPLE-018 | Tạo phiếu yêu cầu (thông tin chung lô) | #1, #2, #3, #4, #5, #6 |
| FR-SAMPLE-001 | Thêm mẫu vào phiếu | #7, #8, #9, #10, #11 |
| FR-SAMPLE-002 | Sinh mã mẫu + barcode/QR | #8 (sinh), #14 (lấy QR) |
| FR-SAMPLE-003 | Đính kèm file mẫu/phiếu | #15, #16, #17, #18 |
| FR-SAMPLE-004 | Tình trạng mẫu khi nhận | #8 (kèm), #12 |
| FR-SAMPLE-005 | Phân công phần việc | #19, #20, #21 |
| FR-SAMPLE-006 | Chuyển giao mẫu (handover) | #22 |
| FR-SAMPLE-007 | Chuỗi hành trình (chain of custody) | #23 |
| FR-SAMPLE-008 | Nhập kết quả phần được giao | #24, #25 |
| FR-SAMPLE-009 | Đính kèm raw data kết quả | #26, #27 |
| FR-SAMPLE-010 | Duyệt kết quả + versioning immutable | #28, #29, #30 |
| FR-SAMPLE-011 | Xem kết quả công khai (sau approved) | #24, #31 |
| FR-SAMPLE-012 | Đặt deadline / TAT | #11, #13 |
| FR-SAMPLE-013 | CRON-1 nhắc sắp tới hạn | #34 (xem), #37 (chạy thủ công) |
| FR-SAMPLE-014 | CRON-2 trễ hạn + nhập lý do | #33, #34, #38 |
| FR-SAMPLE-015 | Báo cáo on-time rate | #36 |
| FR-SAMPLE-016 | Xuất phiếu kết quả PDF | #35 |
| FR-SAMPLE-017 | State machine (nền) | enforce trong #8/#20/#25/#28/#32/#35 + #38 |
| FR-SAMPLE-019 | Trưởng nhóm chốt done thủ công | #32 |

---

**Trạng thái contract:** DRAFT — chờ User APPROVED trước khi `/dev` implement.
**Open Questions còn treo không chặn implement:** #4 (mốc nhắc CRON-1 — cấu hình), #6 (giới hạn file size — mặc định 20MB), #7 (phân trùng part), #8 (thêm raw data sau approve — mặc định chặn), #9 (overdue→testing khi gia hạn — mặc định giữ overdue), #10 (admin sửa trạng thái ngoại lệ — chưa expose endpoint).
