# API Contract: M2 — Quản lý Hóa chất & Tồn kho

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M2 — Chemical Inventory
**Version:** 1.0 | **Ngày:** 19/06/2026 | **Designer:** api-designer agent
**Nguồn chân lý:** `02-srs-m2-chemical.md` (v1.2 — 14 FR, 30 BR, NFR), `01-demo-scope.md` (RBAC 4 vai trò + phạm vi phòng ban)
**Stack:** FastAPI + PostgreSQL + Redis + MinIO + APScheduler (monolith, ~40 user)

---

## 0. Quy ước chung (đọc trước)

### 0.1 Base & versioning
- Prefix: `/api/v1`. Mọi resource là danh từ số nhiều.
- Nested tối đa 2 cấp: `/chemicals/:id/lots`, `/lots/:id/transactions`.
- ID trong URL là **UUID** (không lộ ID tuần tự — CONSTRAINT-6, rule api.md). Mã hiển thị (sample_code, lot_no) chỉ dùng để hiển thị/lọc, không dùng làm path param định danh resource.

### 0.2 Response format chuẩn (rule api.md)
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
    "details": [ { "field": "qty_input", "message": "..." } ],
    "correlationId": "c1f2..."   // luôn trả để user report support (rule logging.md)
  } }
```

### 0.3 Auth & headers
- **Mọi endpoint** yêu cầu `Authorization: Bearer <JWT>` (M7). Không có endpoint public trong M2.
- **`X-Correlation-Id`** (UUID): client gửi; nếu thiếu, server tự sinh và trả lại trong response header + ghi vào `audit_logs.correlation_id` (bắt buộc cho audit VILAS §8.4 — BR-CHEM-012).
- 401 nếu thiếu/sai token; 403 nếu thiếu quyền/sai phạm vi phòng ban.

### 0.4 Pagination
- Tất cả endpoint list: `page` (default 1), `limit` (default **20**, max **100**). Vượt max → ép về 100.
- **Offset-based** cho M2 (dataset ~5.000 hóa chất / ~50.000 giao dịch ở quy mô 40 user — offset đủ tốt, đơn giản hơn cursor cho FE phân trang nhảy trang). `meta` luôn có `page`, `limit`, `total`, `hasNext`.

### 0.5 Số học & đơn vị (OQ#2 — quan trọng)
- `qty_input`: NUMERIC(14,4) — số người dùng nhập theo `input_unit`.
- `qty_base`, `balance_after`, `qty_base` của lô: NUMERIC(18,6) — lưu nội bộ theo `base_unit`.
- `unit_price`: NUMERIC(14,2), gắn `currency` (default `VND`) và `price_unit` (đơn vị nhập của lô).
- Trong JSON, các số này trả về dạng **string** để tránh mất chính xác float ở client (vd `"qty_base": "500000.000000"`). Client không tự làm tròn.
- Mọi quy đổi qua bảng `units.factor_to_base` (cố định, không sửa — BR-CHEM-029). Chỉ quy đổi cùng nhóm đo (BR-CHEM-028).

### 0.6 Field-level RBAC — cách ly tài chính (BR-CHEM-022)
- Các field tiền: `unit_price`, `currency`, `price_unit`, `stock_value`, `consumption_cost` (và các cột tương ứng trong Excel).
- **Trả về cho:** Admin, Ban lãnh đạo, Kế toán.
- **Ẩn hoàn toàn (không có key trong JSON) với:** KTV — kể cả KTV vừa là người nhập `unit_price`. Lọc ở **tầng API** (không chỉ FE). Ngoại lệ: khi KTV **ghi** giao dịch nhập (POST in) thì được gửi `unit_price` trong request body (input), nhưng response đọc về không chứa field tiền.

### 0.7 Phạm vi phòng ban (BR-CHEM-018)
- Mỗi user gắn `department_id` (M7). Hóa chất/lô/giao dịch gắn `department_id` (qua hóa chất).
- **Đọc:** Admin & Ban lãnh đạo = toàn hệ thống; Kế toán = toàn hệ thống (chỉ đọc, có tiền); KTV = đọc toàn hệ thống ở mức list/tồn/lịch sử (theo RBAC matrix "xem tồn/lịch sử" = ✅ mọi vai trò).
- **Ghi (create/update/in/out/adjust/recheck):** KTV chỉ trong `department_id` của mình; thao tác chéo phòng → **403 `FORBIDDEN`**. Admin ghi mọi phòng.
- Query `department_id` chỉ là bộ lọc hiển thị; backend luôn enforce phạm vi ghi theo user.

### 0.8 Rate limit
- Mặc định **60 req/phút/user** cho endpoint đọc/ghi giao dịch.
- Endpoint nặng (export Excel, báo cáo tiêu hao): **10 req/phút/user**.
- Vượt giới hạn → **429** code `RATE_LIMIT_EXCEEDED`.

---

## 1. Bảng tổng hợp Endpoint

| # | Method | Path | Mô tả | Vai trò (ghi) | Scope | FR |
|---|--------|------|-------|---------------|-------|-----|
| 1 | GET | `/api/v1/units` | Danh mục đơn vị + nhóm đo + hệ số quy đổi | Mọi vai trò (đọc) | Toàn hệ thống | FR-001/005/006/008 |
| 2 | GET | `/api/v1/chemicals` | Liệt kê + tìm kiếm + lọc hóa chất | Mọi vai trò (đọc) | Đọc toàn HT | FR-004 |
| 3 | POST | `/api/v1/chemicals` | Tạo hóa chất | Admin, KTV(phòng) | Ghi theo phòng | FR-001 |
| 4 | GET | `/api/v1/chemicals/:id` | Chi tiết hóa chất | Mọi vai trò (đọc) | Đọc toàn HT | FR-001/003 |
| 5 | PATCH | `/api/v1/chemicals/:id` | Cập nhật hóa chất (partial) | Admin, KTV(phòng) | Ghi theo phòng | FR-001 |
| 6 | POST | `/api/v1/chemicals/:id/deactivate` | Vô hiệu hóa (soft) | Admin, KTV(phòng) | Ghi theo phòng | FR-001 |
| 7 | GET | `/api/v1/chemicals/:id/attachments` | Liệt kê file đính kèm (MSDS) | Mọi vai trò (đọc) | Đọc toàn HT | FR-003 |
| 8 | POST | `/api/v1/chemicals/:id/attachments` | Upload MSDS cho hóa chất | Admin, KTV(phòng) | Ghi theo phòng | FR-003 |
| 9 | GET | `/api/v1/chemicals/:id/lots` | Liệt kê lô của hóa chất (kèm tồn) | Mọi vai trò (đọc) | Đọc toàn HT | FR-002/004/008 |
| 10 | POST | `/api/v1/chemicals/:id/lots` | Tạo lô (có thể kèm giao dịch nhập đầu — atomic) | Admin, KTV(phòng) | Ghi theo phòng | FR-002/005 |
| 11 | GET | `/api/v1/lots/:id` | Chi tiết lô (kèm tồn + giá trị tồn*) | Mọi vai trò (đọc) | Đọc toàn HT | FR-002/008 |
| 12 | GET | `/api/v1/lots/:id/coa` | Lấy link tải CoA của lô | Mọi vai trò (đọc) | Đọc toàn HT | FR-002 |
| 13 | GET | `/api/v1/chemicals/:id/fefo-suggestion` | Gợi ý lô theo FEFO để xuất | Mọi vai trò (đọc) | Đọc toàn HT | FR-006 |
| 14 | POST | `/api/v1/lots/:id/transactions` | Ghi giao dịch in/out/adjust (atomic, row-lock) | Admin, KTV(phòng) | Ghi theo phòng | FR-005/006/007 |
| 15 | GET | `/api/v1/transactions` | Lịch sử giao dịch có lọc + phân trang | Mọi vai trò (đọc) | Đọc toàn HT | FR-009 |
| 16 | POST | `/api/v1/lots/:id/rechecks` | Ghi kết quả kiểm tra lại + cập nhật recheck_date | Admin, KTV(phòng) | Ghi theo phòng | FR-011 |
| 17 | GET | `/api/v1/chemicals/:id/stock` | Tồn hiện tại theo lô + tổng (đổi display_unit) | Mọi vai trò (đọc) | Đọc toàn HT | FR-008 |
| 18 | GET | `/api/v1/inventory/low-stock` | Danh sách hóa chất tồn dưới ngưỡng | Mọi vai trò (đọc) | Đọc toàn HT | FR-010 |
| 19 | GET | `/api/v1/inventory/reconcile` | Đối soát qty_base lô vs balance_after | Admin, Lãnh đạo | Đọc toàn HT | FR-008 |
| 20 | GET | `/api/v1/exports/transactions.xlsx` | Xuất Excel nhật ký (sync) | Admin, Lãnh đạo, Kế toán, KTV(phòng) | Đọc theo phạm vi | FR-013 |
| 21 | GET | `/api/v1/reports/consumption` | Báo cáo tiêu hao theo tháng/đề tài/người | Admin, Lãnh đạo, Kế toán, KTV(phòng) | Đọc theo phạm vi | FR-014 |
| 22 | POST | `/api/v1/admin/crons/chem-expiry/run` | Chạy thủ công CRON-6 (test/vận hành) | Admin | Toàn hệ thống | FR-012 |

\* Field tiền (`*_price`, `stock_value`, ...) chỉ trả cho vai trò tài chính (BR-CHEM-022).

---

## 2. Chi tiết Endpoint

---

### 1. GET /api/v1/units
**Mục đích:** Lấy danh mục đơn vị để FE render dropdown chọn base_unit / input_unit / display_unit; cung cấp hệ số quy đổi.
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** toàn hệ thống | **Rate limit:** 60/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| group | enum | ❌ | mass\|volume\|count | Lọc theo nhóm đo |

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "code": "kg", "group": "mass", "factor_to_base": "1000000", "label": "Kilôgam" },
    { "code": "g",  "group": "mass", "factor_to_base": "1000",    "label": "Gam" },
    { "code": "mg", "group": "mass", "factor_to_base": "1",       "label": "Miligam" },
    { "code": "L",  "group": "volume","factor_to_base": "1000",   "label": "Lít" },
    { "code": "mL", "group": "volume","factor_to_base": "1",      "label": "Mililít" },
    { "code": "unit","group": "count","factor_to_base": "1",      "label": "Đơn vị" }
  ]
}
```
**Errors:** chỉ 401. Danh mục read-only (BR-CHEM-029 — người dùng cuối không tạo/sửa đơn vị).

---

### 2. GET /api/v1/chemicals
**Mục đích:** Liệt kê, tìm kiếm, lọc hóa chất + lô theo trạng thái (FR-004).
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc) | **Scope:** đọc toàn hệ thống | **Rate limit:** 60/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| q | string | ❌ | maxLength(100) | Từ khóa: tên hoặc CAS |
| department_id | uuid | ❌ | — | Lọc theo phòng ban |
| status | enum | ❌ | active\|inactive (default active) | Trạng thái hóa chất |
| measurement_group | enum | ❌ | mass\|volume\|count | Nhóm đo |
| expiry_within_days | int | ❌ | 1..3650 | Có lô hết hạn trong N ngày |
| recheck_due | bool | ❌ | — | Có lô tới hạn kiểm tra lại |
| has_stock | bool | ❌ | — | Chỉ hóa chất còn tồn > 0 |
| page | int | ❌ | ≥1 (default 1) | |
| limit | int | ❌ | 1..100 (default 20) | |

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "9c3f...uuid",
      "name": "NaCl",
      "cas_no": "7647-14-5",
      "manufacturer": "Merck",
      "base_unit": "mg",
      "measurement_group": "mass",
      "hazard_code": null,
      "department_id": "dep-uuid",
      "department_name": "Hóa lý",
      "reorder_threshold": "50000.000000",
      "total_stock_base": "687500.000000",
      "status": "active",
      "lot_count": 2,
      "has_expiring_lot": false,
      "created_at": "2026-05-01T03:12:00Z"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 200, "hasNext": true }
}
```
> Không có field tiền ở list (giá thuộc cấp lô). KTV thấy danh sách mọi phòng nhưng FE chỉ bật nút sửa/xuất với phòng của KTV (AC2 FR-004).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | Query param sai kiểu/khoảng |
| UNAUTHORIZED | 401 | Thiếu/sai token |

---

### 3. POST /api/v1/chemicals
**Mục đích:** Tạo hóa chất mới (FR-001).
**Auth:** Bearer JWT | **Roles:** Admin, KTV | **Scope:** KTV chỉ phòng mình | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| name | string | ✅ | maxLength(255), trim non-empty | Tên hóa chất |
| cas_no | string | ❌ | regex `^\d{2,7}-\d{2}-\d$` + checksum | Số CAS |
| manufacturer | string | ❌ | maxLength(255) | Nhà sản xuất |
| base_unit | string | ✅ | tồn tại trong `units.code` | Đơn vị cơ sở (suy ra group) |
| hazard_code | string | ❌ | maxLength(50) | Mã GHS (vd H314) |
| department_id | uuid | ❌ | default = phòng của user; KTV bắt buộc = phòng mình | Phòng quản lý |
| reorder_threshold | string(decimal) | ❌ | ≥0, ≤ NUMERIC(18,6) theo base_unit | Ngưỡng cảnh báo tồn |

> `measurement_group` **không nhận từ client** — server suy ra từ `base_unit` (BR-CHEM-001).

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "9c3f...uuid",
    "name": "NaCl",
    "cas_no": "7647-14-5",
    "base_unit": "mg",
    "measurement_group": "mass",
    "department_id": "dep-uuid",
    "reorder_threshold": "50000.000000",
    "status": "active",
    "created_at": "2026-06-19T08:00:00Z"
  }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | CAS sai định dạng/checksum; name rỗng (BR-CHEM-001, AC2) |
| INVALID_UNIT | 400 | base_unit không có trong `units` / không xác định nhóm đo (AC5) |
| DUPLICATE_CHEMICAL | 409 | Trùng (name + cas_no) trong cùng phòng ban (BR-CHEM-002) |
| FORBIDDEN | 403 | KTV tạo cho phòng khác (AC3) |

**Side effects:** Ghi `audit_logs` action=`CHEMICAL_CREATE` (user, resource=chemical, resource_id, correlation_id, ip).

---

### 4. GET /api/v1/chemicals/:id
**Mục đích:** Chi tiết hóa chất + mã nguy hại + đính kèm (FR-001/003).
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** đọc toàn HT | **Rate limit:** 60/min

**Path:** `id` = UUID hóa chất.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "9c3f...uuid",
    "name": "H2SO4",
    "cas_no": "7664-93-9",
    "manufacturer": "Merck",
    "base_unit": "mL",
    "measurement_group": "volume",
    "hazard_code": "H314",
    "department_id": "dep-uuid",
    "department_name": "Hóa lý",
    "reorder_threshold": "1000.000000",
    "total_stock_base": "5000.000000",
    "status": "active",
    "attachments": [
      { "id": "att-uuid", "file_name": "msds-h2so4.pdf", "mime": "application/pdf", "size": 2097152, "uploaded_at": "2026-06-10T02:00:00Z" }
    ],
    "created_at": "2026-05-01T03:12:00Z"
  }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| NOT_FOUND | 404 | Không có hóa chất với id |

---

### 5. PATCH /api/v1/chemicals/:id
**Mục đích:** Cập nhật partial hóa chất (FR-001). Dùng PATCH vì sửa từng phần.
**Auth:** Bearer JWT | **Roles:** Admin, KTV | **Scope:** KTV chỉ phòng của hóa chất | **Rate limit:** 60/min

**Request Body (mọi field optional, ≥1 field):**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| name | string | ❌ | maxLength(255) | |
| cas_no | string | ❌ | regex + checksum | |
| manufacturer | string | ❌ | maxLength(255) | |
| hazard_code | string | ❌ | maxLength(50) | |
| reorder_threshold | string(decimal) | ❌ | ≥0 | |
| base_unit | string | ❌ | tồn tại trong `units`; **bị khóa nếu đã có lô/giao dịch** | Chỉ đổi khi chưa có lô |

> KHÔNG cho đổi `base_unit`/`measurement_group` khi hóa chất đã có lô/giao dịch (BR-CHEM-003). Đơn vị NHẬP/HIỂN THỊ vẫn tự do trong cùng nhóm — không liên quan field này.

**Response 200:** giống endpoint #4.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | Field sai định dạng; body rỗng |
| INVALID_UNIT | 400 | base_unit mới không hợp lệ |
| UNIT_LOCKED | 422 | Đổi base_unit khi đã có lô/giao dịch (AC4 FR-001, BR-CHEM-003) |
| DUPLICATE_CHEMICAL | 409 | Đổi tên/CAS gây trùng trong phòng |
| FORBIDDEN | 403 | KTV sửa hóa chất phòng khác (AC3) |
| NOT_FOUND | 404 | id không tồn tại |

**Side effects:** `audit_logs` action=`CHEMICAL_UPDATE` (detail = diff field thay đổi).

---

### 6. POST /api/v1/chemicals/:id/deactivate
**Mục đích:** Vô hiệu hóa (soft-delete) hóa chất (FR-001). Dùng POST action thay DELETE vì không xóa cứng (giữ truy vết VILAS).
**Auth:** Bearer JWT | **Roles:** Admin, KTV | **Scope:** KTV phòng mình | **Rate limit:** 60/min

**Request Body:** rỗng.

**Response 200:**
```json
{ "success": true, "data": { "id": "9c3f...uuid", "status": "inactive" } }
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| CHEMICAL_HAS_STOCK | 422 | Còn lô tồn > 0 — phải xử lý tồn trước (BR-CHEM-004) |
| FORBIDDEN | 403 | KTV phòng khác |
| NOT_FOUND | 404 | id không tồn tại |

**Side effects:** `audit_logs` action=`CHEMICAL_DEACTIVATE`.

---

### 7. GET /api/v1/chemicals/:id/attachments
**Mục đích:** Liệt kê file MSDS/đính kèm của hóa chất (FR-003).
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** đọc toàn HT | **Rate limit:** 60/min

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "id": "att-uuid", "file_name": "msds-h2so4.pdf", "mime": "application/pdf",
      "size": 2097152, "download_url": "https://minio.../presigned?...", "url_expires_at": "2026-06-19T08:15:00Z",
      "uploaded_by": "user-uuid", "uploaded_at": "2026-06-10T02:00:00Z" }
  ]
}
```
> `download_url` = presigned URL MinIO TTL 15 phút (xem mục 4.2 về flow file).

**Errors:** `NOT_FOUND` (404) nếu hóa chất không tồn tại.

---

### 8. POST /api/v1/chemicals/:id/attachments
**Mục đích:** Upload MSDS cho hóa chất (FR-003).
**Auth:** Bearer JWT | **Roles:** Admin, KTV(phòng) | **Scope:** ghi theo phòng | **Rate limit:** 30/min

**Flow file — chọn: upload qua API (multipart)** (giải thích mục 4.2). `Content-Type: multipart/form-data`.

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| file | binary | ✅ | MIME thực ∈ {PDF, PNG, JPG, XLSX}; size ≤ giới hạn (OQ#7, mặc định 20MB) | File MSDS |

**Response 201:**
```json
{
  "success": true,
  "data": { "id": "att-uuid", "owner_type": "chemical", "owner_id": "9c3f...uuid",
    "file_name": "msds-h2so4.pdf", "mime": "application/pdf", "size": 2097152, "uploaded_at": "2026-06-19T08:00:00Z" }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| INVALID_FILE_TYPE | 422 | MIME không thuộc whitelist (AC2 FR-003, BR-CHEM-013) |
| FILE_TOO_LARGE | 422 | Vượt giới hạn dung lượng (BR-CHEM-013) |
| FORBIDDEN | 403 | KTV phòng khác |
| NOT_FOUND | 404 | hóa chất không tồn tại |

**Side effects:** Lưu MinIO (`file_key`) + bản ghi `attachments` (owner_type=`chemical`); `audit_logs` action=`CHEMICAL_MSDS_UPLOAD`.

---

### 9. GET /api/v1/chemicals/:id/lots
**Mục đích:** Liệt kê lô của một hóa chất kèm tồn hiện tại (FR-002/004/008).
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** đọc toàn HT | **Rate limit:** 60/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| status | enum | ❌ | in_stock\|expiring\|expired\|recheck_due | Bộ lọc trạng thái lô |
| display_unit | string | ❌ | cùng nhóm với base_unit (BR-CHEM-028) | Đơn vị hiển thị tồn |
| page/limit | int | ❌ | pagination chuẩn | |

**Response 200 (vai trò tài chính — có field tiền):**
```json
{
  "success": true,
  "data": [
    {
      "id": "lot-uuid",
      "chemical_id": "9c3f...uuid",
      "lot_no": "L2026-001",
      "qty_base": "487500.000000",
      "base_unit": "mg",
      "qty_display": "487.5000",
      "display_unit": "g",
      "recheck_result": "pass",
      "received_at": "2026-05-01",
      "expiry_date": "2027-12-31",
      "recheck_date": "2026-12-31",
      "is_expired": false,
      "has_coa": true,
      "unit_price": "1200.00",
      "price_unit": "g",
      "currency": "VND",
      "stock_value": "585000.00"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 2, "hasNext": false }
}
```
> **KTV nhận response giống hệt nhưng KHÔNG có các key** `unit_price`, `price_unit`, `currency`, `stock_value` (BR-CHEM-022). `stock_value` = qty còn lại (quy về `price_unit`) × `unit_price` (BR-CHEM-030).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| INVALID_UNIT | 400 | display_unit không tồn tại |
| UNIT_GROUP_MISMATCH | 422 | display_unit khác nhóm đo với base_unit (BR-CHEM-028) |
| NOT_FOUND | 404 | hóa chất không tồn tại |

---

### 10. POST /api/v1/chemicals/:id/lots
**Mục đích:** Tạo lô mới; tùy chọn nhập tồn ban đầu trong cùng transaction nguyên tử (FR-002 + FR-005, UC-CHEM-01).
**Auth:** Bearer JWT | **Roles:** Admin, KTV(phòng) | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| lot_no | string | ✅ | maxLength(100); duy nhất trong hóa chất | Số lô |
| received_at | date | ❌ | ISO date | Ngày nhận |
| expiry_date | date | ❌ | ISO date | Hạn dùng |
| recheck_date | date | ❌ | ≤ expiry_date (BR-CHEM-006) | Ngày kiểm tra lại kế |
| initial_intake | object | ❌ | xem dưới | Giao dịch nhập đầu (gộp atomic) |
| initial_intake.qty_input | string(decimal) | ✅ nếu có intake | >0, ≤4 thập phân | Lượng nhập |
| initial_intake.input_unit | string | ✅ nếu có intake | cùng nhóm với base_unit | Đơn vị nhập |
| initial_intake.unit_price | string(decimal) | ❌ | ≥0, NUMERIC(14,2) | Đơn giá theo input_unit |
| initial_intake.currency | string | ❌ | default VND | |
| initial_intake.note | string | ❌ | maxLength(500) | Ghi chú |

> CoA upload riêng qua endpoint #8-style cho lô (hoặc field `coa_file_key` sau khi presign) — đính kèm KHÔNG chặn nghiệp vụ tạo lô (AC4 FR-002).

**Response 201:**
```json
{
  "success": true,
  "data": {
    "lot": {
      "id": "lot-uuid", "chemical_id": "9c3f...uuid", "lot_no": "L2026-001",
      "qty_base": "500000.000000", "base_unit": "mg",
      "expiry_date": "2027-12-31", "recheck_date": "2026-12-31",
      "is_expired": false, "recheck_result": null, "created_at": "2026-06-19T08:00:00Z",
      "unit_price": "1200.00", "price_unit": "g", "currency": "VND"
    },
    "transaction": {
      "id": "txn-uuid", "type": "in",
      "qty_input": "500.0000", "input_unit": "g",
      "qty_base": "500000.000000", "base_unit": "mg",
      "balance_after": "500000.000000"
    }
  }
}
```
> Nếu không gửi `initial_intake`: `transaction` = null, lô tạo với `qty_base` = "0.000000".

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | qty_input ≤0 / sai thập phân; thiếu lot_no |
| INVALID_DATE_ORDER | 422 | recheck_date > expiry_date (AC3 FR-002, BR-CHEM-006) |
| DUPLICATE_LOT | 409 | lot_no trùng trong hóa chất (AC4, BR-CHEM-005) |
| INVALID_UNIT | 400 | input_unit không tồn tại |
| UNIT_GROUP_MISMATCH | 422 | input_unit khác nhóm với base_unit (BR-CHEM-028) |
| FORBIDDEN | 403 | KTV phòng khác |
| NOT_FOUND | 404 | hóa chất không tồn tại |

**Warnings (không chặn):** nếu `expiry_date` < hôm nay → tạo lô với `is_expired=true` + WARN log "Lô đã hết hạn" (AC2 FR-002), response trả 201 kèm `data.warnings: ["LOT_ALREADY_EXPIRED"]`.

**Side effects:** Trong **1 transaction DB**: tạo lô (+ nếu có intake: ghi `chemical_transactions` type=in, cập nhật `qty_base`); `audit_logs` actions `CHEMICAL_LOT_CREATE` (+ `CHEMICAL_TXN_IN` nếu có intake). Rollback toàn bộ nếu lỗi.

---

### 11. GET /api/v1/lots/:id
**Mục đích:** Chi tiết một lô + tồn + giá trị tồn (FR-002/008).
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** đọc toàn HT | **Rate limit:** 60/min

**Query:** `display_unit` (optional, cùng nhóm).

**Response 200:** giống item trong #9 (1 object). Field tiền ẩn với KTV.

**Errors:** `NOT_FOUND` (404); `UNIT_GROUP_MISMATCH` (422) nếu display_unit sai nhóm.

---

### 12. GET /api/v1/lots/:id/coa
**Mục đích:** Lấy link tải file CoA của lô (FR-002).
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** đọc toàn HT | **Rate limit:** 60/min

**Response 200:**
```json
{ "success": true, "data": { "file_name": "coa-L2026-001.pdf", "mime": "application/pdf",
  "download_url": "https://minio.../presigned?...", "url_expires_at": "2026-06-19T08:15:00Z" } }
```

**Errors:** `NOT_FOUND` (404) nếu lô không có CoA / lô không tồn tại.

---

### 13. GET /api/v1/chemicals/:id/fefo-suggestion
**Mục đích:** Gợi ý thứ tự lô để xuất theo FEFO (FR-006, BR-CHEM-010). Chỉ gợi ý, không chặn.
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** đọc toàn HT | **Rate limit:** 60/min

**Query:** `display_unit` (optional).

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "lot_id": "lotA-uuid", "lot_no": "L2026-001", "qty_base": "100000.000000",
      "qty_display": "100.0000", "display_unit": "g", "expiry_date": "2026-12-31",
      "is_expired": false, "recheck_result": "pass", "fefo_rank": 1, "requires_warning_confirm": false },
    { "lot_id": "lotB-uuid", "lot_no": "L2026-002", "qty_base": "100000.000000",
      "qty_display": "100.0000", "display_unit": "g", "expiry_date": "2027-12-31",
      "is_expired": false, "recheck_result": null, "fefo_rank": 2, "requires_warning_confirm": false }
  ]
}
```
> Thứ tự: lô còn tồn > 0, chưa hết hạn, `expiry_date` sớm nhất lên đầu (AC3 FR-006). `requires_warning_confirm=true` nếu lô fail/quá hạn (FE cảnh báo trước).

---

### 14. POST /api/v1/lots/:id/transactions
**Mục đích:** Ghi MỘT giao dịch tồn kho cho lô: `in` (nhập, FR-005), `out` (xuất gắn mẫu, FR-006), `adjust` (kiểm kê, FR-007). Atomic + row-lock trên lô (BR-CHEM-014). Đây là endpoint phức tạp nhất của module.
**Auth:** Bearer JWT | **Roles:** Admin, KTV(phòng) | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body — chung:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| type | enum | ✅ | in\|out\|adjust | Loại giao dịch |
| at | datetime | ❌ | default now | Thời điểm |
| note | string | ❌* | maxLength(500); **bắt buộc khi type=adjust** | Ghi chú/lý do |

**Bổ sung khi `type=in`:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| qty_input | string(decimal) | ✅ | >0, ≤4 thập phân (BR-CHEM-007/008) | Lượng nhập |
| input_unit | string | ✅ | cùng nhóm với base_unit (BR-CHEM-028) | Đơn vị nhập |
| unit_price | string(decimal) | ❌ | ≥0, NUMERIC(14,2) | Đơn giá theo input_unit (KTV được nhập) |
| currency | string | ❌ | default VND | |

**Bổ sung khi `type=out`:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| qty_input | string(decimal) | ✅ | >0, ≤4 thập phân | Lượng xuất |
| input_unit | string | ✅ | cùng nhóm với base_unit | Đơn vị xuất |
| ref_sample_id | uuid | ✅ | NOT NULL + tồn tại (BR-CHEM-025, OQ#3) | Mẫu liên quan |
| confirm_warning | bool | ❌ | default false | Xác nhận xuất lô fail/quá hạn (OQ#5) |

**Bổ sung khi `type=adjust`:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| actual_qty_input | string(decimal) | ✅(một trong hai) | ≥0 | Tồn thực tế (server tính delta = thực tế − sổ) |
| delta_input | string(decimal) | ✅(một trong hai) | có dấu ± | Chênh lệch trực tiếp |
| input_unit | string | ✅ | cùng nhóm với base_unit | Đơn vị |
| note | string | ✅ | NOT NULL (BR-CHEM-016) | Lý do bắt buộc |

> Gửi đúng MỘT trong `actual_qty_input` / `delta_input`. Kết quả tồn không được âm.

**Response 201 (type=out, vai trò tài chính):**
```json
{
  "success": true,
  "data": {
    "id": "txn-uuid",
    "lot_id": "lot-uuid",
    "type": "out",
    "qty_input": "12.5000",
    "input_unit": "g",
    "qty_base": "12500.000000",
    "base_unit": "mg",
    "balance_after": "487500.000000",
    "ref_sample_id": "sample-uuid",
    "ref_sample_code": "SP-2026-0007",
    "warning_override": false,
    "note": null,
    "by_user": "user-uuid",
    "at": "2026-06-19T08:30:00Z",
    "correlation_id": "c1f2..."
  }
}
```
> KTV: response KHÔNG có `unit_price`/`currency` (AC4 FR-006). type=in của KTV cũng ẩn các field tiền trong response dù KTV vừa gửi `unit_price` ở request.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| INVALID_QUANTITY | 400 | qty_input ≤ 0 (BR-CHEM-007, AC3 FR-005) |
| VALIDATION_ERROR | 400 | qty quá 4 thập phân / không phải số (BR-CHEM-008); type sai |
| REASON_REQUIRED | 400 | type=adjust thiếu `note` (BR-CHEM-016, AC2 FR-007) |
| INVALID_UNIT | 400 | input_unit không tồn tại trong `units` |
| UNIT_GROUP_MISMATCH | 422 | input_unit khác nhóm đo với base_unit (BR-CHEM-028, AC2c) |
| SAMPLE_REQUIRED | 422 | type=out không có `ref_sample_id` (BR-CHEM-025, AC7 FR-006) |
| SAMPLE_NOT_FOUND | 422 | `ref_sample_id` không tồn tại (AC6 FR-006) |
| INSUFFICIENT_STOCK | 422 | type=out: qty_base_xuất > qty_base_lô (BR-CHEM-009, AC2/AC5) |
| WARNING_NEEDS_CONFIRM | 422 | type=out từ lô `recheck_result=fail` hoặc quá hạn, chưa gửi `confirm_warning=true` (OQ#5, AC8/AC9) |
| NEGATIVE_BALANCE | 422 | type=adjust dẫn đến tồn < 0 (BR-CHEM-009) |
| FORBIDDEN | 403 | KTV thao tác lô phòng khác (AC4 FR-005); adjust mà không có quyền `chemical_txn:adjust` (AC3 FR-007) |
| NOT_FOUND | 404 | Lô không tồn tại |
| INTERNAL_ERROR | 500 | Transaction DB fail → rollback, tồn không đổi (AC5 atomic) |

**Ví dụ error WARNING_NEEDS_CONFIRM (lựa chọn HTTP 422 — xem giải thích 4.3):**
```json
{
  "success": false,
  "error": {
    "code": "WARNING_NEEDS_CONFIRM",
    "message": "Lô này có kết quả kiểm tra lại 'không đạt' hoặc đã quá hạn. Xác nhận để tiếp tục xuất.",
    "details": [
      { "field": "lot", "reason": "RECHECK_FAILED", "recheck_result": "fail" },
      { "hint": "Gửi lại với confirm_warning=true và note (lý do) để truy vết 17025." }
    ],
    "correlationId": "c1f2..."
  }
}
```
> Client gửi lại cùng body + `confirm_warning: true` (+ `note` khuyến nghị) → 201, giao dịch có `warning_override: true`.

**Side effects (type=out, happy):**
- Row-lock lô → trừ `qty_base` → ghi `chemical_transactions` immutable (qty_base/base_unit + qty_input/input_unit + balance_after + ref_sample_id + warning_override).
- Cập nhật `chemical_lots.qty_base`.
- `audit_logs` action=`CHEMICAL_TXN_OUT` (detail kèm ref_sample_id; nếu warning_override → kèm cờ + lý do — BR-CHEM-024).
- Sau giao dịch: tính tổng tồn hóa chất; nếu < `reorder_threshold` và chưa có cảnh báo mở → tạo `notifications` type=`CHEM_LOW_STOCK` (FR-010, BR-CHEM-019). Nếu nhập làm tồn ≥ ngưỡng → đóng cảnh báo mở.
- type=in: action=`CHEMICAL_TXN_IN`. type=adjust: action=`CHEMICAL_TXN_ADJUST` (detail kèm delta + lý do).

---

### 15. GET /api/v1/transactions
**Mục đích:** Lịch sử giao dịch có lọc + phân trang (FR-009). Giao dịch bất biến — KHÔNG có endpoint PUT/PATCH/DELETE trên giao dịch (BR-CHEM-015, AC2 FR-009).
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** đọc toàn HT | **Rate limit:** 60/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| chemical_id | uuid | ❌ | — | Lọc theo hóa chất |
| lot_id | uuid | ❌ | — | Lọc theo lô |
| ref_sample_id | uuid | ❌ | — | Lọc theo mẫu (AC3 FR-009) |
| by_user | uuid | ❌ | — | Lọc theo người thực hiện |
| type | enum | ❌ | in\|out\|adjust | |
| date_from | date | ❌ | ≤ date_to | |
| date_to | date | ❌ | — | |
| department_id | uuid | ❌ | — | |
| display_unit | string | ❌ | cùng nhóm | Đơn vị hiển thị qty |
| page/limit | int | ❌ | pagination chuẩn | |

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "txn-uuid", "lot_id": "lot-uuid", "lot_no": "L2026-001",
      "chemical_id": "chem-uuid", "chemical_name": "NaCl",
      "type": "out",
      "qty_input": "12.5000", "input_unit": "g",
      "qty_base": "12500.000000", "base_unit": "mg",
      "balance_after": "487500.000000",
      "ref_sample_code": "SP-2026-0007",
      "warning_override": false,
      "by_user_name": "Nguyễn Văn A",
      "at": "2026-06-19T08:30:00Z",
      "note": null,
      "unit_price": "1200.00", "currency": "VND", "line_value": "15000.00"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 3, "hasNext": false }
}
```
> Sắp xếp thời gian giảm dần (AC1). `line_value` (= qty × unit_price lô) + `unit_price`/`currency`: chỉ vai trò tài chính (AC4, BR-CHEM-022). KTV không có 3 key này.

**Errors:** `VALIDATION_ERROR` (400) nếu date_from > date_to.

---

### 16. POST /api/v1/lots/:id/rechecks
**Mục đích:** Ghi kết quả kiểm tra lại lô + cập nhật `recheck_date` kế tiếp (FR-011). Không khóa cứng lô fail (OQ#5).
**Auth:** Bearer JWT | **Roles:** Admin, KTV(phòng) | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| result | enum | ✅ | pass\|fail | Kết quả kiểm tra lại |
| checked_at | date | ✅ | ≤ hôm nay | Ngày kiểm tra |
| next_recheck_date | date | ❌ | ≤ expiry_date của lô | Kỳ kiểm tra kế |
| note | string | ❌ | maxLength(500) | Ghi chú |
| attachment_file_key | string | ❌ | — | File bằng chứng (presigned trước) |

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "recheck-uuid", "lot_id": "lot-uuid",
    "result": "pass", "checked_at": "2026-12-31",
    "next_recheck_date": "2027-06-30",
    "lot_recheck_result": "pass"
  }
}
```
> `result=fail` → cập nhật `chemical_lots.recheck_result=fail`; lô KHÔNG khóa, nhưng mọi xuất sau cần `confirm_warning` (FR-006 A8). 

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | result/checked_at sai |
| INVALID_DATE_ORDER | 422 | next_recheck_date > expiry_date (BR-CHEM-006) |
| FORBIDDEN | 403 | KTV phòng khác |
| NOT_FOUND | 404 | lô không tồn tại |

**Side effects:** `audit_logs` action=`CHEMICAL_RECHECK`; cập nhật recheck_date + recheck_result.

---

### 17. GET /api/v1/chemicals/:id/stock
**Mục đích:** Tồn hiện tại theo từng lô + tổng tồn hóa chất, hỗ trợ đổi `display_unit` (FR-008). Đọc trực tiếp `chemical_lots.qty_base` (không SUM runtime — hiệu năng).
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** đọc toàn HT | **Rate limit:** 60/min

**Query:** `display_unit` (optional, cùng nhóm — BR-CHEM-028).

**Response 200 (vai trò tài chính):**
```json
{
  "success": true,
  "data": {
    "chemical_id": "chem-uuid",
    "chemical_name": "NaCl",
    "base_unit": "mg",
    "measurement_group": "mass",
    "display_unit": "g",
    "total_stock_base": "687500.000000",
    "total_stock_display": "687.5000",
    "total_stock_value": "825000.00",
    "currency": "VND",
    "lots": [
      { "lot_id": "lotA", "lot_no": "L2026-001", "qty_base": "487500.000000", "qty_display": "487.5000",
        "unit_price": "1200.00", "price_unit": "g", "stock_value": "585000.00" },
      { "lot_id": "lotB", "lot_no": "L2026-002", "qty_base": "200000.000000", "qty_display": "200.0000",
        "unit_price": "1200.00", "price_unit": "g", "stock_value": "240000.00" }
    ]
  }
}
```
> KTV: bỏ `total_stock_value`, `currency`, và các `unit_price`/`price_unit`/`stock_value` trong từng lô (BR-CHEM-022). KHÔNG cộng gộp khác nhóm đo (AC2 FR-008).

**Errors:** `UNIT_GROUP_MISMATCH` (422) nếu display_unit sai nhóm; `NOT_FOUND` (404).

---

### 18. GET /api/v1/inventory/low-stock
**Mục đích:** Danh sách hóa chất có tổng tồn < `reorder_threshold` (FR-010, hiển thị/lọc).
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** đọc toàn HT | **Rate limit:** 60/min

**Query:** `department_id` (optional), pagination.

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "chemical_id": "chem-uuid", "chemical_name": "NaCl", "base_unit": "mg",
      "total_stock_base": "45000.000000", "reorder_threshold": "50000.000000",
      "department_name": "Hóa lý", "alert_open": true }
  ],
  "meta": { "page": 1, "limit": 20, "total": 3, "hasNext": false }
}
```

---

### 19. GET /api/v1/inventory/reconcile
**Mục đích:** Đối soát `chemical_lots.qty_base` với `balance_after` của giao dịch cuối mỗi lô; báo lô lệch (FR-008 A1, AC3).
**Auth:** Bearer JWT | **Roles:** Admin, Ban lãnh đạo | **Scope:** toàn HT | **Rate limit:** 10/min

**Query:** `chemical_id` (optional), `department_id` (optional), pagination.

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "lot_id": "lotA", "lot_no": "L2026-001", "chemical_name": "NaCl",
      "lot_qty_base": "487500.000000", "last_txn_balance_after": "480000.000000",
      "diff_base": "7500.000000", "status": "MISMATCH" }
  ],
  "meta": { "page": 1, "limit": 20, "total": 1, "hasNext": false }
}
```
> Lô lệch → ghi `audit_logs` cảnh báo (BR-CHEM-015). Chỉ trả lô có `status=MISMATCH` mặc định; query `include_ok=true` để trả cả lô khớp.

**Errors:** `FORBIDDEN` (403) nếu KTV/Kế toán gọi.

---

### 20. GET /api/v1/exports/transactions.xlsx
**Mục đích:** Xuất Excel nhật ký nhập/xuất/điều chỉnh theo khoảng thời gian (FR-013). **Trả file đồng bộ** (≤10.000 dòng — xem giải thích 4.4).
**Auth:** Bearer JWT | **Roles:** Admin, Ban lãnh đạo, Kế toán, KTV(phạm vi phòng) | **Scope:** KTV chỉ phòng mình | **Rate limit:** 10/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| date_from | date | ✅ | ≤ date_to | Bắt đầu |
| date_to | date | ✅ | — | Kết thúc |
| chemical_id | uuid | ❌ | — | |
| ref_sample_id | uuid | ❌ | — | |
| by_user | uuid | ❌ | — | |
| type | enum | ❌ | in\|out\|adjust | |
| department_id | uuid | ❌ | KTV bị ép = phòng mình | |

**Response 200:** `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `Content-Disposition: attachment; filename="chem-journal-2026-05.xlsx"`. Body = binary .xlsx.

**Cột Excel:** ngày | hóa chất | CAS | lô | type | qty_input | input_unit | qty_base | base_unit | balance_after | mẫu (mã) | người | ghi chú. **Vai trò tài chính bổ sung:** unit_price | currency | line_value (BR-CHEM-030). **KTV: không có 3 cột tiền** (AC3 FR-013, BR-CHEM-022).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| INVALID_DATE_RANGE | 400 | date_from > date_to (AC4, BR-CHEM-013 luồng A1) |
| EXPORT_TOO_LARGE | 422 | Kết quả > 10.000 dòng → đề nghị thu hẹp khoảng/lọc (ngưỡng async OQ#6) |

**Side effects:** `audit_logs` action=`CHEMICAL_EXPORT_EXCEL` (user + khoảng ngày + correlationId — R15, AC5).

---

### 21. GET /api/v1/reports/consumption
**Mục đích:** Báo cáo tiêu hao (tổng out) theo chiều tháng/đề tài/người dùng (FR-014).
**Auth:** Bearer JWT | **Roles:** Admin, Ban lãnh đạo, Kế toán, KTV(phạm vi phòng) | **Scope:** KTV chỉ phòng mình | **Rate limit:** 10/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| group_by | enum | ✅ | month\|project\|user | Chiều tổng hợp |
| date_from | date | ✅ | ≤ date_to | |
| date_to | date | ✅ | — | |
| chemical_id | uuid | ❌ | — | |
| department_id | uuid | ❌ | KTV ép phòng mình | |
| format | enum | ❌ | json (default)\|xlsx | json hoặc tải file |

**Response 200 (group_by=month, vai trò tài chính):**
```json
{
  "success": true,
  "data": [
    {
      "group_key": "2026-05",
      "group_label": "Tháng 5/2026",
      "lines": [
        { "chemical_name": "NaCl", "measurement_group": "mass", "base_unit": "mg",
          "consumed_base": "300000.000000", "consumed_display": "300.0000", "display_unit": "g",
          "consumption_cost": "360000.00", "currency": "VND" },
        { "chemical_name": "Ethanol", "measurement_group": "volume", "base_unit": "mL",
          "consumed_base": "500.000000", "consumed_display": "500.0000", "display_unit": "mL",
          "consumption_cost": "250000.00", "currency": "VND" }
      ]
    }
  ]
}
```
> Quy đổi về base unit từng hóa chất rồi tổng hợp; KHÔNG cộng gộp khác nhóm đo (AC1/AC3, BR-CHEM-027). `consumption_cost` = Σ(qty out × unit_price lô) — chỉ vai trò tài chính (AC0b, BR-CHEM-022/030); KTV không có key này. Mẫu không gắn đề tài → nhóm "Không gắn đề tài" (A1 FR-014).

**Errors:** `INVALID_DATE_RANGE` (400); `VALIDATION_ERROR` (400) nếu group_by sai.

---

### 22. POST /api/v1/admin/crons/chem-expiry/run
**Mục đích:** Chạy thủ công CRON-6 (nhắc hết hạn/kiểm tra lại) để test/vận hành (FR-012). Endpoint quản trị.
**Auth:** Bearer JWT | **Roles:** Admin | **Scope:** toàn HT | **Rate limit:** 5/min

**Response 200:**
```json
{ "success": true, "data": { "scanned_lots": 124, "notifications_created": 8, "skipped_duplicate": 15, "ran_at": "2026-06-19T09:00:00Z" } }
```
> Idempotent: mỗi lô × mỗi mốc (30/15/7 ngày) chỉ tạo 1 notification/ngày (BR-CHEM-021, AC2). Lô tồn=0 bị bỏ qua (AC4 FR-012). Dùng Redis lock tránh chạy trùng (AC3).

**Errors:** `FORBIDDEN` (403) nếu không phải Admin; `CRON_ALREADY_RUNNING` (409) nếu Redis lock đang giữ.

---

## 3. Danh mục Error Codes đầy đủ (Module M2)

| Code | HTTP | Ý nghĩa | Endpoint áp dụng |
|------|------|---------|------------------|
| `UNAUTHORIZED` | 401 | Thiếu/sai/hết hạn JWT | Tất cả |
| `FORBIDDEN` | 403 | Sai vai trò hoặc thao tác ghi chéo phòng ban | 3,5,6,8,10,14,16,19,22 |
| `NOT_FOUND` | 404 | Resource (hóa chất/lô/file) không tồn tại | 4–17 |
| `VALIDATION_ERROR` | 400 | Input sai kiểu/định dạng/CAS/thập phân/body rỗng | 2,3,5,10,14,15,16,21 |
| `INVALID_UNIT` | 400 | Đơn vị không có trong `units` / không xác định nhóm | 3,5,9,10,14,17 |
| `INVALID_QUANTITY` | 400 | qty_input ≤ 0 | 14 |
| `REASON_REQUIRED` | 400 | type=adjust thiếu `note` | 14 |
| `INVALID_DATE_RANGE` | 400 | date_from > date_to (export/report) | 20,21 |
| `DUPLICATE_CHEMICAL` | 409 | Trùng (name+cas) trong phòng | 3,5 |
| `DUPLICATE_LOT` | 409 | Trùng lot_no trong hóa chất | 10 |
| `CRON_ALREADY_RUNNING` | 409 | Redis lock CRON-6 đang giữ | 22 |
| `RATE_LIMIT_EXCEEDED` | 429 | Vượt giới hạn request | Tất cả |
| `UNIT_LOCKED` | 422 | Đổi base_unit khi đã có lô/giao dịch | 5 |
| `UNIT_GROUP_MISMATCH` | 422 | input/display unit khác nhóm đo base_unit | 9,10,11,14,17 |
| `INVALID_DATE_ORDER` | 422 | recheck_date > expiry_date | 10,16 |
| `CHEMICAL_HAS_STOCK` | 422 | Vô hiệu hóa hóa chất còn tồn > 0 | 6 |
| `SAMPLE_REQUIRED` | 422 | type=out thiếu ref_sample_id | 14 |
| `SAMPLE_NOT_FOUND` | 422 | ref_sample_id không tồn tại | 14 |
| `INSUFFICIENT_STOCK` | 422 | Xuất quá tồn lô | 14 |
| `WARNING_NEEDS_CONFIRM` | 422 | Xuất lô fail/quá hạn chưa xác nhận | 14 |
| `NEGATIVE_BALANCE` | 422 | adjust khiến tồn < 0 | 14 |
| `INVALID_FILE_TYPE` | 422 | File CoA/MSDS sai loại MIME | 8 |
| `FILE_TOO_LARGE` | 422 | File vượt giới hạn dung lượng | 8 |
| `EXPORT_TOO_LARGE` | 422 | Excel > 10.000 dòng (ngưỡng sync) | 20 |
| `INTERNAL_ERROR` | 500 | Transaction DB fail → rollback | 10,14 |

---

## 4. Ghi chú thiết kế (giải thích quyết định cho ~40 user)

### 4.1 RBAC field-level — cột giá ẩn với KTV
- Backend áp dụng một **response serializer theo vai trò**: nếu `user.role == KTV` thì strip toàn bộ key tiền (`unit_price`, `price_unit`, `currency`, `stock_value`, `total_stock_value`, `line_value`, `consumption_cost`) khỏi mọi response đọc (endpoint 9,11,14-response,15,17,20,21). Đây là yêu cầu **bảo mật tầng API** (NFR-SEC-CHEM-001) — không chỉ ẩn ở FE, để tránh KTV gọi API trực tiếp đọc giá.
- Ngoại lệ duy nhất: KTV **gửi** `unit_price` trong body khi POST giao dịch nhập (input giá là nghiệp vụ của KTV — BR-CHEM-022), nhưng response trả về đã strip.

### 4.2 Flow upload file CoA/MSDS — chọn UPLOAD QUA API (multipart)
- **Quyết định:** upload trực tiếp qua API endpoint (`multipart/form-data`), backend nhận file → validate MIME thực + size → đẩy MinIO → lưu `attachments`. **Tải về** dùng **presigned URL** (TTL 15 phút) để FE tải trực tiếp từ MinIO, giảm tải backend.
- **Lý do (so với presigned-upload 2 bước):** quy mô ~40 user, file CoA/MSDS nhỏ (vài MB), tần suất thấp. Upload 1 bước đơn giản hơn cho FE và **cho phép backend validate MIME thực + quét an toàn trước khi lưu** (NFR-SEC-CHEM-002) — presigned-upload thì client đẩy thẳng MinIO, backend khó validate nội dung. Trade-off: backend chịu băng thông upload, nhưng không đáng kể ở quy mô này.

### 4.3 WARNING_NEEDS_CONFIRM — chọn HTTP 422 (không 409)
- **Quyết định:** trả **422 Unprocessable Entity** cho lần xuất đầu chưa xác nhận (lô fail/quá hạn).
- **Lý do:** request cú pháp hợp lệ nhưng **không xử lý được do điều kiện nghiệp vụ** (lô có rủi ro) — đúng ngữ nghĩa 422 (giống `INSUFFICIENT_STOCK`, `SAMPLE_REQUIRED`). 409 dành cho xung đột trạng thái/duplicate (vd lot trùng). Client xử lý đồng nhất: nhận 422 → đọc `error.code` → nếu `WARNING_NEEDS_CONFIRM` thì hiện dialog xác nhận → gửi lại với `confirm_warning=true`. Đây không phải lỗi cuối cùng mà là "cần thêm xác nhận" → 422 + code rõ ràng là đủ.

### 4.4 Export Excel & báo cáo — chọn ĐỒNG BỘ (sync)
- **Quyết định:** trả file đồng bộ ngay trong response cho ≤ **10.000 dòng** (NFR-PERF-CHEM-003: P95 < 5s). Vượt 10.000 dòng → trả **422 `EXPORT_TOO_LARGE`** đề nghị thu hẹp khoảng ngày/bộ lọc.
- **Lý do:** quy mô ~40 user, ~50.000 giao dịch/toàn hệ thống; một khoảng tháng + lọc phòng hiếm khi vượt 10.000 dòng. Sync đơn giản cho cả BE lẫn FE (không cần job queue, polling, notify). Ngưỡng async (OQ#6) để dành — khi UAT thấy thực tế vượt thì nâng cấp sang job nền + notify in-app (đã chừa sẵn `EXPORT_TOO_LARGE`).

### 4.5 Tính bất biến giao dịch (VILAS §8.4)
- **KHÔNG có** route `PUT/PATCH/DELETE /transactions/:id` (BR-CHEM-015, NFR-AUDIT-CHEM-001). Sửa sai chỉ qua giao dịch `adjust` (endpoint 14, type=adjust). Mọi endpoint ghi đều tạo `audit_logs` với `correlation_id`.

### 4.6 Phi chức năng tóm tắt
- **Rate limit:** đọc/ghi giao dịch 60/min; export/report 10/min; cron admin 5/min. Vượt → 429.
- **Pagination:** offset-based, limit default 20 / max 100, meta đủ `page/limit/total/hasNext`.
- **CorrelationId:** header `X-Correlation-Id` xuyên FE→BE→audit_logs (NFR-OBS-CHEM-001).
- **Validation đầu vào:** sanitize ở tầng API; số dùng string-decimal NUMERIC; không float; CAS validate regex+checksum; file validate MIME thực.
- **Concurrency:** endpoint 14 dùng row-lock + transaction (NFR-CONCUR-CHEM-001) — tồn không bao giờ âm.
- **Số học:** qty_input NUMERIC(14,4), qty_base/balance_after NUMERIC(18,6), unit_price NUMERIC(14,2); JSON trả string để không mất chính xác.

---

## 5. Traceability: Endpoint → FR (SRS)

| Endpoint | FR | Business Rules chính |
|----------|-----|----------------------|
| GET /units | FR-001/005/006/008 | BR-026, 028, 029 |
| GET /chemicals (list/search) | FR-004 | BR-018 |
| POST /chemicals | FR-001 | BR-001, 002, 026, 028, 029 |
| GET /chemicals/:id | FR-001/003 | BR-013 |
| PATCH /chemicals/:id | FR-001 | BR-003 (UNIT_LOCKED) |
| POST /chemicals/:id/deactivate | FR-001 | BR-004 |
| GET/POST /chemicals/:id/attachments | FR-003 | BR-013 |
| GET /chemicals/:id/lots | FR-002/004/008 | BR-005, 022, 030 |
| POST /chemicals/:id/lots | FR-002 (+FR-005) | BR-005, 006, 014, 026, 027, 028 |
| GET /lots/:id, /lots/:id/coa | FR-002/008 | BR-022, 023, 030 |
| GET /chemicals/:id/fefo-suggestion | FR-006 | BR-010 |
| POST /lots/:id/transactions | FR-005/006/007 | BR-007..012, 014, 015, 016, 020, 022..030 |
| GET /transactions | FR-009 | BR-015, 018, 022 |
| POST /lots/:id/rechecks | FR-011 | BR-012, 020, 024 |
| GET /chemicals/:id/stock | FR-008 | BR-015, 017, 022, 023, 026, 027 |
| GET /inventory/low-stock | FR-010 | BR-019 |
| GET /inventory/reconcile | FR-008 | BR-015 |
| GET /exports/transactions.xlsx | FR-013 | BR-017, 018, 022, 027, 030 |
| GET /reports/consumption | FR-014 | BR-017, 018, 022, 023, 027, 030 |
| POST /admin/crons/chem-expiry/run | FR-012 | BR-021 |

---

## 6. Checklist tự review

- [x] Mọi endpoint có roles + scope phòng ban rõ ràng
- [x] Response shape nhất quán (success wrapper + meta cho list)
- [x] Mọi error code là SNAKE_CASE string + HTTP status chuẩn
- [x] Side effects (audit_logs, notifications, row-lock, presigned) liệt kê đầy đủ
- [x] Pagination có meta.total/page/limit/hasNext, limit default 20 / max 100
- [x] Không expose sequential ID — dùng UUID trong URL
- [x] Field-level RBAC: cột giá ẩn với KTV ở tầng API
- [x] Giao dịch bất biến: không có PUT/PATCH/DELETE /transactions
- [x] WARNING_NEEDS_CONFIRM flow (confirm_warning) cho lô fail/quá hạn
- [x] Quy đổi đơn vị + UNIT_GROUP_MISMATCH theo OQ#2
- [x] Traceability endpoint → FR đầy đủ 14 FR

**Tham số chờ chốt (OQ#6/#7/#8 — không chặn implement ERD lõi):** ngưỡng async Excel (mặc định 10.000 dòng), giới hạn file CoA/MSDS (mặc định 20MB, PDF/PNG/JPG/XLSX), người nhận cảnh báo (mặc định mọi KTV có quyền của phòng + Admin).

*Hết API Contract M2 v1.0.*
