# API Contract: M5 — Quản lý Thiết bị & Hiệu chuẩn (Equipment & Calibration)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M5 — Equipment & Calibration (§6.4 thiết bị, §6.5 liên kết chuẩn đo lường, §8.4 kiểm soát hồ sơ)
**Version:** 1.0 | **Ngày:** 20/06/2026 | **Designer:** api-designer agent
**Nguồn chân lý:** `16-srs-m5-equipment.md` (11 FR, 14 BR, 4 UC, 9 NFR, error codes)
**Đồng bộ phong cách:** `15-contract-m3-api.md` + `12-contract-m4-api.md` (prefix `/api/v1`, response `{success,data,meta}`/`{success:false,error:{code,message,details,correlationId}}`, UUID, pagination 20/100, correlationId, upload MinIO multipart, immutable record kiểu M3 version approved, `/admin/crons/.../run` kiểu M4)
**Stack:** FastAPI + PostgreSQL + Redis + MinIO + APScheduler (monolith, ~40 user). Backend đã có **M7 + M1 + M2 + M4 + M3**.

> M5 **phụ thuộc M7**: JWT auth, RBAC + phạm vi phòng ban, `departments.lead_user_id` (trưởng nhóm phòng → nhận CRON-5), `users` (người phụ trách thiết bị), `attachments` polymorphic (`owner_type ∈ {equipment, calibration}` — đã whitelist M7), `audit_logs`, `notifications` (CRON-5 type `CALIBRATION_DUE`). Bản ghi hiệu chuẩn (`calibrations`) **bất biến** (§8.4 — pattern immutable giống version approved M3; không có route PATCH/DELETE). `next_due_date` **tự tính** = `calibrated_at` + chu kỳ thiết bị, denormalize lên `equipments.next_due_date` = lần hiệu chuẩn gần nhất.

---

## 0. Quy ước chung (đọc trước)

### 0.1 Base & versioning
- Prefix: `/api/v1`. Resource danh từ số nhiều: `/equipments`, `/calibrations`.
- Nested tối đa 2 cấp: `/equipments/:id/calibrations`, `/equipments/:id/attachments`.
- ID trong URL là **UUID** — KHÔNG lộ ID tuần tự (CONSTRAINT-4, BR-EQP-014, rule api.md). `equipment_code` (vd `TB-HOA-007`) chỉ để hiển thị/tìm kiếm, KHÔNG dùng làm path param định danh.
- Không breaking change trong cùng `v1`; deprecated báo trước ≥ 1 sprint + header `Deprecation: true`.

### 0.2 Response format chuẩn (đồng bộ M3/M4)
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
    "details": [ { "field": "calibrated_at", "message": "Ngày hiệu chuẩn không được ở tương lai" } ],
    "correlationId": "c1f2..."   // luôn trả để user report support (rule logging.md)
  } }
```

### 0.3 Auth & headers
- **Mọi endpoint M5** yêu cầu `Authorization: Bearer <JWT>` (M7). Không có endpoint public.
- **`X-Correlation-Id`** (UUID): client gửi; nếu thiếu, server tự sinh và **trả lại** trong response header + ghi vào `audit_logs.correlation_id` (audit VILAS §6.4/§8.4 — BR-EQP-014).
- 401 `UNAUTHORIZED` nếu thiếu/sai token; 403 nếu thiếu quyền/sai phạm vi phòng ban.
- RBAC middleware đọc `role` + `dept` (department_id) + `is_dept_lead` từ JWT claims (M7) để enforce quyền + phạm vi mà không query DB mỗi request.
- `Content-Type: application/json` trừ các endpoint upload file (multipart — #4 đính kèm tài liệu thiết bị, #9 ghi hiệu chuẩn kèm CoC).

### 0.4 Pagination
- Tất cả endpoint list: `page` (default 1), `limit` (default **20**, max **100** — vượt ép về 100). **Offset-based** (quy mô ~40 user, ~2,000 thiết bị). `meta` luôn có `page`, `limit`, `total`, `hasNext`.

### 0.5 Rate limit
- Mặc định **60 req/phút/user** cho endpoint đọc/ghi nghiệp vụ.
- Upload file (đính kèm tài liệu #4, ghi hiệu chuẩn kèm CoC #9): **30 req/phút/user**.
- Tải file presigned (#7, #14): **60 req/phút/user**.
- Cron thủ công (#15): chỉ admin, không rate limit người dùng (idempotent + Redis lock).
- Vượt giới hạn → **429** code `RATE_LIMIT_EXCEEDED`.

### 0.6 RBAC tổng quát M5 (BR-EQP-003, §2.3 SRS, OQ#2/#5 đã chốt theo đề bài)
- **4 vai trò:** `admin` (toàn quyền mọi phòng), `leader` (Ban lãnh đạo — **CHỈ XEM 👁** thiết bị/hiệu chuẩn/cảnh báo/thống kê, KHÔNG CRUD, KHÔNG ghi hiệu chuẩn), `accountant` (Kế toán — **CHỈ XEM 👁** theo quyết định đã chốt đề bài, KHÔNG sửa/duyệt), `staff` (Nhân sự/KTV).
- **Khác biệt M5 vs M3:** ở M3 `leader` ghi/duyệt được; ở **M5 `leader` CHỈ XEM** (matrix demo-scope dòng "Thiết bị — hiệu chuẩn" = 👁). Mọi endpoint **ghi** M5 (#4 tạo/#5 sửa thiết bị, #6 đính kèm, #9 ghi hiệu chuẩn) trả **403 `FORBIDDEN`** cho `leader` và `accountant`.
- **Quyết định đã chốt (đề bài):**
  1. **Kế toán XEM được** thiết bị/hiệu chuẩn (👁), KHÔNG sửa/duyệt (sửa mâu thuẫn OQ#5 SRS theo hướng "Kế toán xem 👁").
  2. Thiết bị quá hạn/không đạt: **chỉ CẢNH BÁO** (cờ `is_overdue` + badge `calibration_status`), **KHÔNG khóa cứng** (OQ#3 = cảnh báo — CONSTRAINT-3).
  3. **Chu kỳ hiệu chuẩn theo từng thiết bị** (`calibration_cycle_value` + `calibration_cycle_unit`); `next_due_date` tự tính + cho **override** khi ghi hiệu chuẩn (OQ#1).
  4. **Staff: XEM toàn lab (mọi phòng)**; **THÊM/SỬA thiết bị + ghi hiệu chuẩn CHỈ phòng mình** (OQ#2 = staff đọc toàn lab, ghi phòng mình). Ghi chéo phòng → 403 `FORBIDDEN`.
- **Phạm vi phòng ban (staff — BR-EQP-003):**
  - **Đọc** (`equipment:read`): staff xem **toàn lab** (mọi phòng) — list/chi tiết/lịch sử hiệu chuẩn/tải file.
  - **Ghi** (`equipment:create`, `equipment:update`, `calibration:create`): staff CHỈ trong `department_id` của mình; ghi/đính kèm/ghi hiệu chuẩn cho thiết bị **phòng khác** → **403 `FORBIDDEN`**. Admin = toàn hệ thống.
- **Bảng quyết định RBAC × action:**

| Hành động | admin | leader | accountant | staff (phòng mình) | staff (phòng khác) |
|-----------|-------|--------|-----------|--------------------|--------------------|
| Xem list/chi tiết thiết bị (#1, #3) | ✅ | ✅ 👁 | ✅ 👁 | ✅ 👁 (toàn lab) | ✅ 👁 (toàn lab) |
| Xem lịch sử hiệu chuẩn (#8) / tải file (#7, #14) | ✅ | ✅ 👁 | ✅ 👁 | ✅ 👁 | ✅ 👁 |
| Tạo thiết bị (#4) | ✅ | ❌ 403 | ❌ 403 | ✅ | ❌ 403 |
| Sửa thiết bị / cấu hình chu kỳ (#5) | ✅ | ❌ 403 | ❌ 403 | ✅ | ❌ 403 |
| Đính kèm tài liệu thiết bị (#6) | ✅ | ❌ 403 | ❌ 403 | ✅ | ❌ 403 |
| Ghi lần hiệu chuẩn (#9) | ✅ | ❌ 403 | ❌ 403 | ✅ | ❌ 403 |
| Sửa/xóa bản ghi hiệu chuẩn | ❌ (immutable — không route) | ❌ | ❌ | ❌ | ❌ |
| Chạy CRON-5 thủ công (#15) | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 403 |

> **Người phụ trách thiết bị** (`responsible_user_id`) là **thuộc tính dữ liệu**, KHÔNG phải vai trò RBAC; nhận CRON-5. Quyền ghi vẫn theo RBAC phòng ban (staff phòng đó / admin).

### 0.7 Cảnh báo hiệu chuẩn — cờ `calibration_status` + `is_overdue` (FR-EQP-010, BR-EQP-009/010 — KHÔNG khóa cứng)
Mọi response chứa thiết bị (list #1, chi tiết #3) đính kèm các trường cảnh báo **tính runtime** từ `equipments.next_due_date` so với `CURRENT_DATE` + kết quả lần hiệu chuẩn gần nhất:

| Trường | Kiểu | Ý nghĩa |
|--------|------|---------|
| `calibration_status` | enum | `not_applicable` (chu kỳ NULL — không diện hiệu chuẩn) \| `never_calibrated` (diện hiệu chuẩn nhưng chưa có lần nào) \| `ok` (còn hạn) \| `due_soon` (còn ≤ 30 ngày) \| `overdue` (`next_due_date` < hôm nay) \| `failed` (lần gần nhất `fail`) |
| `is_overdue` | boolean | `next_due_date < CURRENT_DATE` và diện hiệu chuẩn |
| `days_to_due` | int\|null | số ngày tới `next_due_date` (âm nếu quá hạn; null nếu không diện hiệu chuẩn / chưa hiệu chuẩn) |
| `warning_label` | string\|null | nhãn hiển thị: `"Quá hạn hiệu chuẩn — khuyến nghị không sử dụng"` / `"Hiệu chuẩn KHÔNG ĐẠT — khuyến nghị không sử dụng"` / `"Sắp tới hạn hiệu chuẩn (còn N ngày)"` / null |

- **Ưu tiên hiển thị:** `failed` (lần gần nhất fail) ≥ `overdue` ≥ `due_soon` ≥ `ok`. `calibration_status` trả trạng thái ưu tiên cao nhất; nếu vừa `overdue` vừa `failed`, trả `failed` + `warning_label` ghép cả hai (chi tiết #3).
- **KHÔNG khóa cứng (CONSTRAINT-3):** thiết bị `overdue`/`failed` VẪN cho ghi hiệu chuẩn mới (#9), sửa metadata (#5)... — chỉ cảnh báo. Ghi hiệu chuẩn mới `pass` → badge biến mất.
- **Thiết bị `status = retired`** (ngưng sử dụng): KHÔNG sinh badge `overdue`/`due_soon` (BR-EQP-010, FR-EQP-010 A2) — `calibration_status = not_applicable`.
- **Thiết bị chu kỳ NULL** (không diện hiệu chuẩn): `calibration_status = not_applicable`; badge `failed` chỉ khi có lần hiệu chuẩn `fail`.

### 0.8 Flow file đính kèm (đồng bộ M3 §0.9 / M4)
- **Upload qua API multipart** (`Content-Type: multipart/form-data`): backend đẩy file lên MinIO (C01), lưu `file_key` trong `attachments` (`owner_type ∈ {equipment, calibration}`, `owner_id = equipment.id` hoặc `calibration.id`), KHÔNG lưu binary trong DB.
- Whitelist MIME (BR-EQP-012): PDF, DOCX, XLSX, PNG, JPG. CẤM file thực thi/macro (`.docm`, `.exe`, `.js`...). Validate **MIME thực + đuôi**. Size ≤ giới hạn cấu hình (mặc định 20MB — đồng bộ M3/M4).
- **Tải file:** trả **presigned URL MinIO TTL 15 phút** (`download_url` + `url_expires_at`), không proxy binary qua API.

### 0.9 Bất biến (immutable — VILAS §8.4)
- Bản ghi `calibrations` đã tạo: **KHÔNG có endpoint PATCH/DELETE** (CONSTRAINT-1, BR-EQP-007). Đính chính = tạo bản ghi hiệu chuẩn mới (#9) + audit ghi lý do (`note`/`correction_of`). Gọi PATCH/DELETE `/calibrations/:id` → 405 `METHOD_NOT_ALLOWED` (không có route) — DB nên có trigger chặn UPDATE/DELETE để enforce mạnh (schema-designer).
- `equipments.code`: bất biến sau khi tạo (BR-EQP-014). Cố đổi → 422 `CODE_IMMUTABLE`.
- `equipments.department_id`: KHÔNG đổi qua #5 (trừ admin — chuyển sở hữu phòng, ngoài bản đầu). Gửi `department_id` (non-admin) trong #5 → 403 `FORBIDDEN`.
- Thiết bị đã có ≥1 lần hiệu chuẩn: KHÔNG hard-delete (giữ hồ sơ §8.4); dùng `status=retired` hoặc soft-delete + audit.

### 0.10 next_due_date — bất biến dữ liệu (FR-EQP-006/008, BR-EQP-006/008)
- Khi ghi lần hiệu chuẩn (#9): `next_due_date` = `calibrated_at` + chu kỳ thiết bị (cộng tháng/năm an toàn năm nhuận 29/02→28/02), **tự tính**; cho phép **override** thủ công có lý do (`next_due_date_override` + `override_reason` — OQ#1) nếu cert ghi ngày khác.
- `equipments.next_due_date` luôn = `next_due_date` của lần hiệu chuẩn có `calibrated_at` **GẦN NHẤT**; ghi bổ sung lần cũ (calibrated_at < lần gần nhất) KHÔNG ghi đè (BR-EQP-008).
- Cập nhật trong **cùng transaction** với insert `calibrations`. KHÔNG nhận `equipments.next_due_date` trực tiếp từ client.

---

## 1. Bảng tổng hợp Endpoint

| # | Method | Path | Mô tả | Vai trò (ghi) | Scope | FR |
|---|--------|------|-------|---------------|-------|-----|
| **Thiết bị (M5.1)** ||||||
| 1 | GET | `/api/v1/equipments` | Tìm/lọc/liệt kê thiết bị (q/status/department/calibration_status/overdue) + badge cảnh báo | Mọi vai trò (đọc) | Đọc toàn lab | FR-EQP-004/010 |
| 2 | GET | `/api/v1/equipments/calibration-due` | Danh sách thiết bị sắp/đã quá hạn hiệu chuẩn (cảnh báo tập trung) | Mọi vai trò (đọc) | Đọc toàn lab | FR-EQP-010 |
| 3 | GET | `/api/v1/equipments/:id` | Chi tiết thiết bị (metadata + tài liệu + lần hiệu chuẩn gần nhất + badge) | Mọi vai trò (đọc) | Đọc toàn lab | FR-EQP-004 |
| 4 | POST | `/api/v1/equipments` | Tạo thiết bị (sinh `equipment_code`, cấu hình chu kỳ) | admin, staff(phòng) | Ghi theo phòng | FR-EQP-001/003/005 |
| 5 | PATCH | `/api/v1/equipments/:id` | Sửa metadata + tình trạng + chu kỳ (KHÔNG đổi code/dept) | admin, staff(phòng) | Ghi theo phòng | FR-EQP-002/005 |
| 6 | POST | `/api/v1/equipments/:id/attachments` | Đính kèm tài liệu thiết bị (HDSD/ảnh) lên MinIO | admin, staff(phòng) | Ghi theo phòng | FR-EQP-004 |
| 7 | GET | `/api/v1/equipments/:id/attachments/:attId/download` | Tải tài liệu thiết bị (presigned URL) | Mọi vai trò (đọc) | Đọc | FR-EQP-004 |
| **Hiệu chuẩn (M5.2 — §6.4/§6.5)** ||||||
| 8 | GET | `/api/v1/equipments/:id/calibrations` | Lịch sử hiệu chuẩn của thiết bị (immutable, timeline) | Mọi vai trò (đọc) | Đọc toàn lab | FR-EQP-009 |
| 9 | POST | `/api/v1/equipments/:id/calibrations` | Ghi lần hiệu chuẩn (calibrated_at/provider/result + upload CoC, tự tính next_due) | admin, staff(phòng) | Ghi theo phòng | FR-EQP-006/008 |
| 10 | GET | `/api/v1/calibrations/:id` | Chi tiết 1 bản ghi hiệu chuẩn (+ link tải CoC) | Mọi vai trò (đọc) | Đọc toàn lab | FR-EQP-009 |
| 14 | GET | `/api/v1/calibrations/:id/cert/download` | Tải giấy chứng nhận hiệu chuẩn CoC/cert (presigned URL) | Mọi vai trò (đọc) | Đọc toàn lab | FR-EQP-009 |
| **Cron (vận hành/test) — CRON-5** ||||||
| 15 | POST | `/api/v1/admin/crons/equipment-calibration-due/run` | Chạy thủ công CRON-5 (nhắc 30/15/7 ngày, in-app) | admin | Toàn HT | FR-EQP-011 |

> **Lookup:** Danh mục tình trạng (`status`) & đơn vị chu kỳ (`unit`) là enum cố định — KHÔNG cần endpoint danh mục riêng (FE hardcode hoặc lấy từ OpenAPI schema). `departments` & `users` (chọn phòng + người phụ trách) đọc qua API M7.
> **Append-only / immutable:** `audit_logs` + `notifications` ghi nội bộ bởi service — KHÔNG có endpoint POST/PATCH/DELETE cho client. `calibrations` **KHÔNG có route PATCH/DELETE** (§8.4, BR-EQP-007). `equipments.next_due_date` KHÔNG set trực tiếp — chỉ hệ quả của #9.
> **leader / accountant:** 403 `FORBIDDEN` trên TẤT CẢ endpoint **ghi** (#4, #5, #6, #9) và cron (#15) — chỉ gọi được endpoint đọc (#1, #2, #3, #7, #8, #10, #14).

---

## 2. Chi tiết Endpoint

---

### 1. GET /api/v1/equipments
**Mục đích:** Tìm/lọc/liệt kê thiết bị có phân trang, kèm **badge cảnh báo** (`calibration_status`, `is_overdue`) tính runtime (FR-EQP-004/010). Staff đọc **toàn lab** (OQ#2 chốt).
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc — gồm leader 👁, accountant 👁) | **Scope:** đọc toàn lab | **Rate limit:** 60/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| q | string | ❌ | maxLength(100) | Từ khóa: `equipment_code` hoặc `name` (GIN trgm) |
| status | enum | ❌ | active\|maintenance\|broken\|retired | Lọc tình trạng thiết bị (BR-EQP-002) |
| department_id | uuid | ❌ | tồn tại | Lọc phòng ban sở hữu |
| responsible_user_id | uuid | ❌ | tồn tại | Lọc theo người phụ trách |
| calibration_status | enum | ❌ | ok\|due_soon\|overdue\|failed\|never_calibrated\|not_applicable | Lọc theo trạng thái hiệu chuẩn (badge) |
| overdue | boolean | ❌ | true\|false | Lối tắt: chỉ thiết bị quá hạn (= calibration_status `overdue`) |
| page/limit | int | ❌ | pagination chuẩn | |

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "eq-uuid",
      "equipment_code": "TB-HOA-007",
      "name": "Máy đo pH Mettler",
      "location": "Phòng Hóa lý - Bàn 3",
      "department_id": "dept-uuid",
      "department_name": "Hóa lý",
      "responsible_user_id": "user-uuid",
      "responsible_user_name": "Nguyễn Văn A",
      "purchase_date": "2024-01-15",
      "status": "active",
      "calibration_cycle_value": 12,
      "calibration_cycle_unit": "month",
      "next_due_date": "2027-06-20",
      "last_calibrated_at": "2026-06-20",
      "last_calibration_result": "pass",
      "calibration_status": "ok",
      "is_overdue": false,
      "days_to_due": 365,
      "warning_label": null,
      "created_at": "2024-01-15T02:00:00Z"
    },
    {
      "id": "eq2-uuid",
      "equipment_code": "TB-HOA-003",
      "name": "Cân phân tích",
      "department_name": "Hóa lý",
      "status": "active",
      "calibration_cycle_value": 6,
      "calibration_cycle_unit": "month",
      "next_due_date": "2026-06-01",
      "last_calibration_result": "pass",
      "calibration_status": "overdue",
      "is_overdue": true,
      "days_to_due": -19,
      "warning_label": "Quá hạn hiệu chuẩn — khuyến nghị không sử dụng"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 50, "hasNext": true }
}
```
> Badge tính runtime từ `next_due_date` vs `CURRENT_DATE` + `last_calibration_result` (NFR-PERF-EQP-002 — index `equipments(next_due_date)`, `equipments(department_id, status)`). Thiết bị `status=retired` hoặc chu kỳ NULL → `calibration_status` ∈ {`not_applicable`} (BR-EQP-010).

**Errors:** `VALIDATION_ERROR` (400 — filter sai enum), `UNAUTHORIZED` (401).

---

### 2. GET /api/v1/equipments/calibration-due
**Mục đích:** Danh sách tập trung thiết bị **sắp tới hạn / đã quá hạn / không đạt** hiệu chuẩn — phục vụ màn hình cảnh báo & dashboard (FR-EQP-010). Tương đương #1 với bộ lọc cố định + sắp xếp theo độ khẩn cấp.
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc) | **Scope:** đọc toàn lab | **Rate limit:** 60/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| within_days | int | ❌ | 1..365 (default 30) | Tới hạn trong N ngày (gồm cả đã quá hạn) |
| department_id | uuid | ❌ | tồn tại | Lọc phòng ban |
| bucket | enum | ❌ | overdue\|due_soon\|failed\|all (default all) | Lọc nhóm cảnh báo |
| page/limit | int | ❌ | pagination chuẩn | |

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "eq2-uuid",
      "equipment_code": "TB-HOA-003",
      "name": "Cân phân tích",
      "department_name": "Hóa lý",
      "responsible_user_name": "Nguyễn Văn A",
      "next_due_date": "2026-06-01",
      "calibration_status": "overdue",
      "is_overdue": true,
      "days_to_due": -19,
      "warning_label": "Quá hạn hiệu chuẩn — khuyến nghị không sử dụng"
    },
    {
      "id": "eq3-uuid",
      "equipment_code": "TB-SINH-002",
      "name": "Tủ ấm CO2",
      "department_name": "Sinh học",
      "next_due_date": "2026-07-05",
      "calibration_status": "due_soon",
      "is_overdue": false,
      "days_to_due": 15,
      "warning_label": "Sắp tới hạn hiệu chuẩn (còn 15 ngày)"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 7, "hasNext": false }
}
```
> Chỉ thiết bị **diện hiệu chuẩn** (chu kỳ ≠ NULL) và `status ∉ {retired}` (BR-EQP-010). Sắp xếp: `overdue` (days_to_due tăng dần, quá hạn lâu nhất trước) → `failed` → `due_soon`. `bucket=failed` lọc thiết bị có lần gần nhất `fail` bất kể next_due.

**Errors:** `VALIDATION_ERROR` (400 — within_days ngoài khoảng), `UNAUTHORIZED` (401).

---

### 3. GET /api/v1/equipments/:id
**Mục đích:** Chi tiết thiết bị: metadata + tài liệu đính kèm + lần hiệu chuẩn gần nhất + badge cảnh báo (FR-EQP-004). Lịch sử hiệu chuẩn đầy đủ lấy qua #8.
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc) | **Scope:** đọc toàn lab | **Rate limit:** 60/min

**Path:** `id` = equipment UUID.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "eq-uuid",
    "equipment_code": "TB-HOA-007",
    "name": "Máy đo pH Mettler",
    "location": "Phòng Hóa lý - Bàn 3",
    "department_id": "dept-uuid",
    "department_name": "Hóa lý",
    "responsible_user_id": "user-uuid",
    "responsible_user_name": "Nguyễn Văn A",
    "purchase_date": "2024-01-15",
    "status": "active",
    "calibration_cycle_value": 12,
    "calibration_cycle_unit": "month",
    "next_due_date": "2027-06-20",
    "calibration_status": "ok",
    "is_overdue": false,
    "days_to_due": 365,
    "warning_label": null,
    "last_calibration": {
      "id": "cal-uuid",
      "calibrated_at": "2026-06-20",
      "provider": "Trung tâm Đo lường ABC",
      "result": "pass",
      "next_due_date": "2027-06-20",
      "cert_attachment_id": "att-uuid"
    },
    "calibration_count": 3,
    "attachments": [
      { "attachment_id": "att2-uuid", "file_name": "huong-dan-may-do-ph.pdf", "mime": "application/pdf", "size": 348201, "uploaded_by_name": "Nguyễn Văn A", "uploaded_at": "2024-01-16T02:00:00Z" }
    ],
    "created_by_name": "Nguyễn Văn A",
    "created_at": "2024-01-15T02:00:00Z",
    "updated_at": "2026-06-20T03:00:00Z"
  }
}
```
> `last_calibration=null` nếu chưa có lần hiệu chuẩn → `calibration_status` ∈ {`never_calibrated`, `not_applicable`}. `attachments[]` là tài liệu thiết bị (`owner_type='equipment'`); CoC/cert nằm trong từng bản ghi hiệu chuẩn (#8/#10).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| EQUIPMENT_NOT_FOUND | 404 | id không tồn tại hoặc đã soft-delete |
| UNAUTHORIZED | 401 | Thiếu token |

---

### 4. POST /api/v1/equipments
**Mục đích:** Tạo thiết bị (metadata + sinh `equipment_code` duy nhất không lộ tuần tự + tùy chọn cấu hình chu kỳ hiệu chuẩn) (FR-EQP-001/003/005, UC-EQP-01). Thiết bị mới chưa có lần hiệu chuẩn → `next_due_date=null`.
**Auth:** Bearer JWT | **Roles:** admin, staff(phòng mình) | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| name | string | ✅ | maxLength(255), trim non-empty | Tên thiết bị |
| location | string | ❌ | maxLength(255) | Vị trí đặt |
| department_id | uuid | ❌ | tồn tại; default = phòng của user; staff bắt buộc = phòng mình | Phòng ban sở hữu (BR-EQP-003) |
| responsible_user_id | uuid | ❌ | user tồn tại; phải cùng phòng với thiết bị (BR-EQP-013) | Người phụ trách (nhận CRON-5) |
| purchase_date | date | ❌ | ISO date; ≤ hôm nay | Ngày mua |
| status | enum | ❌ | active\|maintenance\|broken\|retired (default `active`) | Tình trạng (BR-EQP-002) |
| calibration_cycle_value | int | ❌ | > 0 (bắt buộc nếu có `calibration_cycle_unit`) | Chu kỳ hiệu chuẩn — số (BR-EQP-004) |
| calibration_cycle_unit | enum | ❌ | month\|year (bắt buộc nếu có value) | Đơn vị chu kỳ (BR-EQP-004) |

> `equipment_code`, `id` (UUID), `next_due_date` (=null) do server thiết lập — KHÔNG nhận từ client (FR-EQP-003). Bỏ trống cả `calibration_cycle_*` = thiết bị không thuộc diện hiệu chuẩn (chu kỳ NULL — không nhắc/không badge quá hạn).

**Response 201:** object thiết bị như #3 (`last_calibration=null`, `calibration_count=0`, `attachments=[]`).
```json
{
  "success": true,
  "data": {
    "id": "eq-uuid",
    "equipment_code": "TB-HOA-008",
    "name": "Máy đo pH",
    "department_id": "dept-uuid",
    "department_name": "Hóa lý",
    "responsible_user_id": "user-uuid",
    "status": "active",
    "calibration_cycle_value": 12,
    "calibration_cycle_unit": "month",
    "next_due_date": null,
    "calibration_status": "never_calibrated",
    "is_overdue": false,
    "days_to_due": null,
    "warning_label": null,
    "created_by": "user-uuid",
    "created_at": "2026-06-20T08:00:00Z"
  }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | Thiếu `name` / field sai kiểu (FR-EQP-001 A2) |
| INVALID_STATUS | 422 | `status` ngoài enum (BR-EQP-002) |
| INVALID_CALIBRATION_CYCLE | 422 | `calibration_cycle_value` ≤ 0 hoặc `unit` ngoài {month, year} hoặc chỉ điền 1 trong 2 (BR-EQP-004, FR-EQP-001 A3) |
| RESPONSIBLE_NOT_IN_DEPARTMENT | 422 | `responsible_user_id` không cùng phòng với thiết bị (BR-EQP-013, FR-EQP-001 A5) |
| DEPARTMENT_NOT_FOUND | 404 | `department_id` không tồn tại |
| USER_NOT_FOUND | 404 | `responsible_user_id` không tồn tại |
| FORBIDDEN | 403 | staff tạo cho phòng khác (BR-EQP-003); leader/accountant gọi endpoint ghi (§0.6) |
| DUPLICATE_EQUIPMENT_CODE | 409 | Sinh trùng `equipment_code` sau N lần retry (FR-EQP-003 A1 — hiếm) |

**Side effects:**
- Tạo `equipments` (`next_due_date=null`, `status`) + sinh `equipment_code` (`TB-<MAPHONG>-<seq>`, unique — FR-EQP-003).
- `audit_logs` action=`EQUIPMENT_CREATE` (detail = code, name, department_id — VILAS §6.4/§8.4, BR-EQP-014).

---

### 5. PATCH /api/v1/equipments/:id
**Mục đích:** Sửa metadata thiết bị (`name`, `location`, `responsible_user_id`, `purchase_date`, **`status`**, **chu kỳ hiệu chuẩn** — gộp cấu hình chu kỳ FR-EQP-005). KHÔNG đổi `equipment_code` (bất biến — BR-EQP-014) và KHÔNG đổi `department_id` (trừ admin). Đổi chu kỳ KHÔNG hồi tố `next_due_date` lần hiệu chuẩn đã có — chỉ áp lần TIẾP THEO (BR-EQP-006) (FR-EQP-002/005, UC-EQP-04).
**Auth:** Bearer JWT | **Roles:** admin, staff(phòng mình) | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body (≥1 field):**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| name | string | ❌ | maxLength(255), trim non-empty | Tên |
| location | string | ❌ | maxLength(255) | Vị trí |
| responsible_user_id | uuid\|null | ❌ | user tồn tại + cùng phòng (BR-EQP-013); null = bỏ người phụ trách | Người phụ trách |
| purchase_date | date | ❌ | ≤ hôm nay | Ngày mua |
| status | enum | ❌ | active\|maintenance\|broken\|retired | Tình trạng (BR-EQP-002) |
| calibration_cycle_value | int\|null | ❌ | > 0; null = bỏ diện hiệu chuẩn | Chu kỳ — số (BR-EQP-004) |
| calibration_cycle_unit | enum\|null | ❌ | month\|year; đi cùng value | Đơn vị chu kỳ |

> Gửi `equipment_code` trong body → 422 `CODE_IMMUTABLE`. Gửi `department_id` (non-admin) → 403 `FORBIDDEN`. `next_due_date` KHÔNG nhận trực tiếp (chỉ qua ghi hiệu chuẩn #9).

**Response 200:** object thiết bị như #3.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | body rỗng / field sai kiểu |
| CODE_IMMUTABLE | 422 | Cố đổi `equipment_code` (BR-EQP-014, FR-EQP-002 A1) |
| INVALID_STATUS | 422 | `status` ngoài enum (FR-EQP-002 A3) |
| INVALID_CALIBRATION_CYCLE | 422 | chu kỳ sai (value ≤ 0 / unit sai / chỉ 1 trong 2) (BR-EQP-004) |
| RESPONSIBLE_NOT_IN_DEPARTMENT | 422 | người phụ trách khác phòng (BR-EQP-013) |
| FORBIDDEN | 403 | staff sửa thiết bị phòng khác / đổi `department_id` non-admin (BR-EQP-003); leader/accountant (§0.6) |
| EQUIPMENT_NOT_FOUND | 404 | id không tồn tại |

**Side effects:** cập nhật metadata; `audit_logs` action=`EQUIPMENT_UPDATE` (detail = diff before/after từng trường — đặc biệt đổi `status` và chu kỳ). Đổi chu kỳ KHÔNG ghi đè `next_due_date` hiện tại (BR-EQP-006).

---

### 6. POST /api/v1/equipments/:id/attachments
**Mục đích:** Đính kèm tài liệu thiết bị (hướng dẫn sử dụng, ảnh, hồ sơ) lên MinIO qua `attachments` (`owner_type='equipment'`) (FR-EQP-004, R2/R11).
**Auth:** Bearer JWT | **Roles:** admin, staff(phòng mình) | **Scope:** ghi theo phòng | **Rate limit:** 30/min (upload)

**Content-Type:** `multipart/form-data`

**Request (multipart fields):**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| file | binary | ✅ | MIME whitelist (PDF/DOCX/XLSX/PNG/JPG) + ≤20MB, validate MIME thực + đuôi (BR-EQP-012) | File tài liệu |
| doc_type | enum | ❌ | manual\|image\|other (default `other`) | Phân loại tài liệu (hiển thị) |

**Response 201:**
```json
{
  "success": true,
  "data": {
    "attachment_id": "att-uuid",
    "owner_type": "equipment",
    "owner_id": "eq-uuid",
    "file_name": "huong-dan-may-do-ph.pdf",
    "mime": "application/pdf",
    "size": 348201,
    "doc_type": "manual",
    "uploaded_by": "user-uuid",
    "uploaded_at": "2026-06-20T08:05:00Z"
  }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| INVALID_FILE_TYPE | 422 | File ngoài whitelist MIME (BR-EQP-012, FR-EQP-004 A4) |
| FILE_TOO_LARGE | 422 | File > 20MB (BR-EQP-012) |
| FORBIDDEN | 403 | staff đính kèm thiết bị phòng khác (BR-EQP-003, FR-EQP-004 A3); leader/accountant (§0.6) |
| EQUIPMENT_NOT_FOUND | 404 | id không tồn tại |
| STORAGE_UNAVAILABLE | 503 | MinIO down — log ERROR, không lộ stack |

**Side effects:** đẩy file MinIO + `attachments` (`owner_type='equipment'`, `owner_id=equipment.id`, `file_key`); `audit_logs` action=`EQUIPMENT_ATTACH`.

---

### 7. GET /api/v1/equipments/:id/attachments/:attId/download
**Mục đích:** Tải tài liệu thiết bị — trả presigned URL MinIO TTL 15p (FR-EQP-004).
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc) | **Scope:** đọc toàn lab | **Rate limit:** 60/min

**Response 200:**
```json
{
  "success": true,
  "data": {
    "attachment_id": "att-uuid",
    "file_name": "huong-dan-may-do-ph.pdf",
    "mime": "application/pdf",
    "size": 348201,
    "download_url": "https://minio.lims.internal/lims/equipment/...?X-Amz-Expires=900&...",
    "url_expires_at": "2026-06-20T08:20:00Z"
  }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| ATTACHMENT_NOT_FOUND | 404 | attId không thuộc thiết bị này / không tồn tại |
| EQUIPMENT_NOT_FOUND | 404 | id không tồn tại |
| STORAGE_UNAVAILABLE | 503 | MinIO down |

**Side effects:** `audit_logs` action=`EQUIPMENT_ATTACH_DOWNLOAD` (best-effort).

---

### 8. GET /api/v1/equipments/:id/calibrations
**Mục đích:** Lịch sử hiệu chuẩn đầy đủ của thiết bị — timeline các lần hiệu chuẩn (ngày, provider, kết quả, next_due, link tải CoC, người ghi), **bất biến** (§6.4/§6.5/§8.4) (FR-EQP-009, UC-EQP-02).
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc) | **Scope:** đọc toàn lab | **Rate limit:** 60/min

**Query params:** `result` (optional enum `pass|fail`), `page/limit`.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "cal3-uuid",
      "equipment_id": "eq-uuid",
      "calibrated_at": "2026-06-20",
      "provider": "Trung tâm Đo lường ABC",
      "result": "pass",
      "next_due_date": "2027-06-20",
      "next_due_overridden": false,
      "override_reason": null,
      "is_latest": true,
      "cert_attachment_id": "att-uuid",
      "cert_file_name": "coc-tb-hoa-007-2026.pdf",
      "note": null,
      "correction_of": null,
      "created_by_name": "Nguyễn Văn A",
      "created_at": "2026-06-20T08:30:00Z"
    },
    {
      "id": "cal2-uuid",
      "calibrated_at": "2025-06-20",
      "provider": "Trung tâm Đo lường ABC",
      "result": "pass",
      "next_due_date": "2026-06-20",
      "is_latest": false,
      "cert_attachment_id": "att-prev-uuid",
      "created_by_name": "Nguyễn Văn A",
      "created_at": "2025-06-20T08:30:00Z"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 3, "hasNext": false }
}
```
> Sắp xếp `calibrated_at` giảm dần (lần gần nhất trước). `is_latest=true` cho bản ghi có `calibrated_at` lớn nhất (nguồn của `equipments.next_due_date` — BR-EQP-008). Danh sách rỗng nếu thiết bị chưa hiệu chuẩn (FR-EQP-009 A3). KHÔNG có PATCH/DELETE — immutable (§0.9).

**Errors:** `EQUIPMENT_NOT_FOUND` (404), `UNAUTHORIZED` (401).

---

### 9. POST /api/v1/equipments/:id/calibrations
**Mục đích:** Ghi một **lần hiệu chuẩn** cho thiết bị (ngày, provider, kết quả pass/fail, upload CoC/cert) → **tự tính `next_due_date`** = `calibrated_at` + chu kỳ (cho override) → cập nhật `equipments.next_due_date` (nếu là lần gần nhất) + cập nhật badge cảnh báo. Bản ghi **bất biến** sau khi tạo (FR-EQP-006/008, UC-EQP-02 — CỐT LÕI §6.4/§6.5).
**Auth:** Bearer JWT | **Roles:** admin, staff(phòng mình) | **Scope:** ghi theo phòng | **Rate limit:** 30/min (upload CoC)

**Content-Type:** `multipart/form-data`

**Request (multipart fields):**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| calibrated_at | date | ✅ | ISO date; **≤ hôm nay** (BR-EQP-005) | Ngày hiệu chuẩn |
| provider | string | ❌ | maxLength(255) | Đơn vị/provider hiệu chuẩn (text bản đầu — OQ#4) |
| result | enum | ✅ | pass\|fail | Kết quả (BR-EQP-009) |
| next_due_date_override | date | ❌ | > calibrated_at (nếu có) | Override ngày kế tiếp nếu cert ghi khác chu kỳ (OQ#1) — kèm `override_reason` |
| override_reason | string | ⚠️ (bắt buộc nếu có override) | maxLength(255) | Lý do override (audit) |
| note | string | ❌ | maxLength(500) | Ghi chú (vd lý do đính chính) |
| correction_of | uuid | ❌ | bản ghi calibration cùng thiết bị | Đính chính bản ghi cũ (immutable — tạo mới thay vì sửa, BR-EQP-007) |
| cert | binary | ⚠️ (bắt buộc khi result=pass — OQ#4 default) | MIME whitelist (PDF/PNG/JPG) + ≤20MB (BR-EQP-012) | Giấy chứng nhận CoC/cert |

> `next_due_date` mặc định **tự tính** = `calibrated_at` + (`calibration_cycle_value` × `unit`), cộng năm an toàn năm nhuận (29/02→28/02). Nếu có `next_due_date_override` → dùng giá trị override (kèm reason + audit). `created_by`, `created_at`, `id` do server thiết lập. Toàn bộ (insert calibration + upload CoC MinIO + cập nhật equipment.next_due_date + audit) trong **1 transaction**; lỗi upload → rollback (FR-EQP-006 luồng chính bước 3).

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "cal-uuid",
    "equipment_id": "eq-uuid",
    "equipment_code": "TB-HOA-007",
    "calibrated_at": "2026-06-20",
    "provider": "Trung tâm Đo lường ABC",
    "result": "pass",
    "next_due_date": "2027-06-20",
    "next_due_overridden": false,
    "override_reason": null,
    "is_latest": true,
    "cert": { "attachment_id": "att-uuid", "file_name": "coc-tb-hoa-007-2026.pdf", "mime": "application/pdf", "size": 251002 },
    "note": null,
    "correction_of": null,
    "created_by": "user-uuid",
    "created_by_name": "Nguyễn Văn A",
    "created_at": "2026-06-20T08:30:00Z",
    "equipment": {
      "id": "eq-uuid",
      "next_due_date": "2027-06-20",
      "calibration_status": "ok",
      "is_overdue": false,
      "warning_label": null
    }
  }
}
```
> Nếu `result=fail`: bản ghi vẫn tạo; `equipment.calibration_status="failed"`, `warning_label="Hiệu chuẩn KHÔNG ĐẠT — khuyến nghị không sử dụng"` — **KHÔNG khóa cứng** (CONSTRAINT-3, FR-EQP-006 AC3). Nếu ghi bổ sung lần CŨ (calibrated_at < lần gần nhất hiện có): `is_latest=false`, `equipment.next_due_date` KHÔNG đổi (BR-EQP-008, FR-EQP-008 A1).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | thiếu `calibrated_at` / `result` (FR-EQP-006) |
| CALIBRATION_CERT_REQUIRED | 400 | thiếu CoC khi `result=pass` (OQ#4 default bắt buộc, FR-EQP-006 A4) |
| INVALID_CALIBRATION_DATE | 422 | `calibrated_at` ở tương lai (BR-EQP-005, FR-EQP-006 A2/AC4) |
| INVALID_CALIBRATION_RESULT | 422 | `result` ∉ {pass, fail} (FR-EQP-006 A3) |
| CALIBRATION_CYCLE_REQUIRED | 422 | thiết bị chưa cấu hình chu kỳ VÀ không có `next_due_date_override` (BR-EQP-006, FR-EQP-006 A1/AC5) |
| INVALID_DATE_ORDER | 422 | `next_due_date_override` ≤ `calibrated_at` |
| OVERRIDE_REASON_REQUIRED | 400 | có `next_due_date_override` nhưng thiếu `override_reason` (OQ#1) |
| INVALID_FILE_TYPE | 422 | CoC ngoài whitelist (BR-EQP-012, FR-EQP-006 A7) |
| FILE_TOO_LARGE | 422 | CoC > 20MB |
| FORBIDDEN | 403 | staff ghi hiệu chuẩn thiết bị phòng khác (BR-EQP-003, FR-EQP-006 A5/AC6); leader/accountant (§0.6) |
| EQUIPMENT_NOT_FOUND | 404 | id không tồn tại |
| CALIBRATION_NOT_FOUND | 404 | `correction_of` không thuộc thiết bị / không tồn tại |
| STORAGE_UNAVAILABLE | 503 | MinIO down — rollback transaction, log ERROR |

**Side effects (trong 1 transaction):**
- Insert `calibrations` (**immutable** — không cột mutable nghiệp vụ; KHÔNG route sửa/xóa — BR-EQP-007).
- Đẩy CoC MinIO + `attachments` (`owner_type='calibration'`, `owner_id=calibration.id`).
- Nếu lần này là gần nhất (calibrated_at lớn nhất) → cập nhật `equipments.next_due_date` = `next_due_date` lần này (BR-EQP-008, FR-EQP-008) → badge cảnh báo cập nhật (badge quá hạn cũ biến mất nếu pass — FR-EQP-010 AC4).
- `audit_logs` action=`CALIBRATION_RECORD` (detail = calibrated_at, result, next_due_date, override flag — VILAS §6.4/§6.5).

---

### 10. GET /api/v1/calibrations/:id
**Mục đích:** Chi tiết 1 bản ghi hiệu chuẩn (metadata + link tải CoC) (FR-EQP-009).
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc) | **Scope:** đọc toàn lab | **Rate limit:** 60/min

**Response 200:** object như item #8 + `equipment` (code, name, department_name).

**Errors:** `CALIBRATION_NOT_FOUND` (404), `UNAUTHORIZED` (401).

> **KHÔNG có** `PATCH /calibrations/:id` và `DELETE /calibrations/:id` — bản ghi hiệu chuẩn bất biến (§8.4, BR-EQP-007, FR-EQP-007). Gọi → 405 `METHOD_NOT_ALLOWED` (không có route). Đính chính = tạo bản ghi mới qua #9 với `correction_of`.

---

### 14. GET /api/v1/calibrations/:id/cert/download
**Mục đích:** Tải giấy chứng nhận hiệu chuẩn CoC/cert của bản ghi hiệu chuẩn — presigned URL MinIO TTL 15p (FR-EQP-009, truy xuất nguồn gốc §6.5).
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc) | **Scope:** đọc toàn lab | **Rate limit:** 60/min

**Response 200:**
```json
{
  "success": true,
  "data": {
    "calibration_id": "cal-uuid",
    "cert_attachment_id": "att-uuid",
    "file_name": "coc-tb-hoa-007-2026.pdf",
    "mime": "application/pdf",
    "size": 251002,
    "download_url": "https://minio.lims.internal/lims/calibration/...?X-Amz-Expires=900&...",
    "url_expires_at": "2026-06-20T08:45:00Z"
  }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| CERT_NOT_FOUND | 404 | bản ghi hiệu chuẩn không có CoC đính kèm |
| CALIBRATION_NOT_FOUND | 404 | id không tồn tại |
| STORAGE_UNAVAILABLE | 503 | MinIO down |

**Side effects:** `audit_logs` action=`CALIBRATION_DOWNLOAD` (best-effort — truy vết tải cert phục vụ VILAS).

---

### 15. POST /api/v1/admin/crons/equipment-calibration-due/run
**Mục đích:** Chạy thủ công **CRON-5** (nhắc trước hiệu chuẩn 30/15/7 ngày, in-app) để test/vận hành (FR-EQP-011, R16). Đồng bộ pattern `/admin/crons/.../run` của M4 (#42/#43). Job thật chạy APScheduler 07:00 hằng ngày + Redis lock (CONSTRAINT-8).
**Auth:** Bearer JWT | **Roles:** **admin** | **Scope:** toàn HT | **Rate limit:** —

**Request Body:** rỗng (tùy chọn `as_of_date` để test mốc — chỉ dev/staging).

**Response 200:**
```json
{
  "success": true,
  "data": {
    "run_at": "2026-06-20T07:00:00Z",
    "as_of_date": "2026-06-20",
    "scanned_equipments": 312,
    "notifications_created": 9,
    "by_milestone": { "30": 4, "15": 3, "7": 2 },
    "recipients": 14,
    "skipped_no_recipient": 1,
    "skipped_retired_or_no_cycle": 28,
    "deduped": 5
  }
}
```
> Idempotent: mỗi (thiết bị × mốc 30/15/7) chỉ gửi 1 lần (chống trùng qua idempotency key trên `notifications` hoặc cờ mốc đã nhắc — BR-EQP-011). `recipients` = người phụ trách (`responsible_user_id`) + trưởng nhóm phòng (`departments.lead_user_id`). Thiết bị không người phụ trách → gửi trưởng nhóm; không trưởng nhóm → `skipped_no_recipient` + log WARN (FR-EQP-011 A1/A4). Bỏ qua thiết bị `status=retired` / chu kỳ NULL (BR-EQP-010).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| FORBIDDEN | 403 | không phải admin (leader/accountant/staff) |
| CRON_ALREADY_RUNNING | 409 | job đang chạy (Redis lock đang giữ — chống chạy trùng, CONSTRAINT-8, FR-EQP-011 A2/AC6) |

**Side effects:**
- Tạo `notifications` type=`CALIBRATION_DUE` (ref_type='equipment', ref_id=equipment.id) cho người phụ trách + trưởng nhóm — in-app only (C02), idempotent theo mốc (BR-EQP-011).
- `audit_logs` action=`CRON_CALIBRATION_REMINDER` (detail = số thông báo tạo, mốc).
- Đọc thông báo qua API `notifications` của M7.

---

## 3. Danh mục Error Codes M5

Nhất quán họ code SNAKE_CASE với M3/M4/M7 (`*_NOT_FOUND`, `DUPLICATE_*`, `INVALID_*`, `FORBIDDEN`, `*_REQUIRED`, `*_IMMUTABLE`).

| Code | HTTP | Endpoint | Điều kiện |
|------|------|----------|-----------|
| `UNAUTHORIZED` | 401 | tất cả | Thiếu/sai JWT |
| `FORBIDDEN` | 403 | #4, #5, #6, #9, #15 | staff ghi thiết bị/hiệu chuẩn phòng khác; leader/accountant gọi endpoint ghi; non-admin gọi cron (BR-EQP-003) |
| `VALIDATION_ERROR` | 400 | #1, #2, #4, #5, #9 | Thiếu field bắt buộc / sai kiểu / body rỗng / filter sai enum |
| `EQUIPMENT_NOT_FOUND` | 404 | #3, #5, #6, #7, #8, #9 | thiết bị không tồn tại hoặc đã soft-delete |
| `CALIBRATION_NOT_FOUND` | 404 | #9 (correction_of), #10, #14 | bản ghi hiệu chuẩn không tồn tại |
| `DEPARTMENT_NOT_FOUND` | 404 | #4 | `department_id` không tồn tại |
| `USER_NOT_FOUND` | 404 | #4, #5 | `responsible_user_id` không tồn tại |
| `ATTACHMENT_NOT_FOUND` | 404 | #7 | tài liệu không thuộc thiết bị / không tồn tại |
| `CERT_NOT_FOUND` | 404 | #14 | bản ghi hiệu chuẩn không có CoC đính kèm |
| `DUPLICATE_EQUIPMENT_CODE` | 409 | #4 | sinh trùng `equipment_code` sau N retry (FR-EQP-003 A1) |
| `CODE_IMMUTABLE` | 422 | #5 | cố đổi `equipment_code` (BR-EQP-014) |
| `INVALID_STATUS` | 422 | #4, #5 | `status` ngoài {active, maintenance, broken, retired} (BR-EQP-002) |
| `INVALID_CALIBRATION_CYCLE` | 422 | #4, #5 | `value` ≤ 0 / `unit` ∉ {month, year} / chỉ điền 1 trong 2 (BR-EQP-004) |
| `RESPONSIBLE_NOT_IN_DEPARTMENT` | 422 | #4, #5 | người phụ trách khác phòng thiết bị (BR-EQP-013) |
| `INVALID_CALIBRATION_DATE` | 422 | #9 | `calibrated_at` ở tương lai (BR-EQP-005) |
| `INVALID_CALIBRATION_RESULT` | 422 | #9 | `result` ∉ {pass, fail} |
| `CALIBRATION_CYCLE_REQUIRED` | 422 | #9 | thiết bị chưa có chu kỳ + không override next_due (BR-EQP-006) |
| `INVALID_DATE_ORDER` | 422 | #9 | `next_due_date_override` ≤ `calibrated_at` |
| `OVERRIDE_REASON_REQUIRED` | 400 | #9 | có override next_due nhưng thiếu lý do (OQ#1) |
| `CALIBRATION_CERT_REQUIRED` | 400 | #9 | thiếu CoC khi `result=pass` (OQ#4 default) |
| `CALIBRATION_IMMUTABLE` | 405/403 | (PATCH/DELETE `/calibrations/:id`) | cố sửa/xóa bản ghi hiệu chuẩn — KHÔNG có route (BR-EQP-007, §8.4) |
| `INVALID_FILE_TYPE` | 422 | #6, #9 | file ngoài whitelist MIME (BR-EQP-012) |
| `FILE_TOO_LARGE` | 422 | #6, #9 | file > 20MB (BR-EQP-012) |
| `STORAGE_UNAVAILABLE` | 503 | #6, #7, #9, #14 | MinIO down (log ERROR, không lộ stack) |
| `CRON_ALREADY_RUNNING` | 409 | #15 | CRON-5 đang chạy (Redis lock — CONSTRAINT-8) |
| `RATE_LIMIT_EXCEEDED` | 429 | tất cả | vượt rate limit (§0.5) |

**Ví dụ error `INVALID_CALIBRATION_DATE`:**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_CALIBRATION_DATE",
    "message": "Ngày hiệu chuẩn không được ở tương lai. Hiệu chuẩn là sự kiện đã xảy ra.",
    "details": [{ "field": "calibrated_at", "value": "2026-06-21", "max": "2026-06-20" }],
    "correlationId": "c1f2..."
  }
}
```

**Ví dụ error `CALIBRATION_CYCLE_REQUIRED`:**
```json
{
  "success": false,
  "error": {
    "code": "CALIBRATION_CYCLE_REQUIRED",
    "message": "Thiết bị chưa cấu hình chu kỳ hiệu chuẩn. Hãy cấu hình chu kỳ hoặc nhập ngày hiệu chuẩn kế tiếp thủ công (next_due_date_override).",
    "details": [{ "field": "calibration_cycle_value", "message": "thiết bị chưa thuộc diện hiệu chuẩn" }],
    "correlationId": "c1f2..."
  }
}
```

**Ví dụ error `CALIBRATION_IMMUTABLE` (cố sửa bản ghi hiệu chuẩn):**
```json
{
  "success": false,
  "error": {
    "code": "CALIBRATION_IMMUTABLE",
    "message": "Bản ghi hiệu chuẩn không thể sửa/xóa (hồ sơ bất biến theo ISO/IEC 17025 §8.4). Để đính chính, hãy tạo bản ghi hiệu chuẩn mới với trường correction_of.",
    "details": [],
    "correlationId": "c1f2..."
  }
}
```

---

## 4. Ghi chú RBAC (chi tiết)

### 4.1 Ma trận đầy đủ (BR-EQP-003, §2.3 SRS, quyết định đề bài)

| Hành động | admin | leader | accountant | staff (phòng mình) | staff (phòng khác) |
|-----------|-------|--------|-----------|--------------------|--------------------|
| Đọc list/chi tiết thiết bị + badge | ✅ | ✅ 👁 | ✅ 👁 | ✅ 👁 (toàn lab) | ✅ 👁 (toàn lab) |
| Đọc lịch sử hiệu chuẩn + tải CoC/tài liệu | ✅ | ✅ 👁 | ✅ 👁 | ✅ 👁 | ✅ 👁 |
| Tạo / sửa thiết bị, cấu hình chu kỳ | ✅ | ❌ 403 | ❌ 403 | ✅ | ❌ 403 |
| Đính kèm tài liệu thiết bị | ✅ | ❌ 403 | ❌ 403 | ✅ | ❌ 403 |
| Ghi lần hiệu chuẩn | ✅ | ❌ 403 | ❌ 403 | ✅ | ❌ 403 |
| Sửa/xóa bản ghi hiệu chuẩn | ❌ (immutable — không route) | ❌ | ❌ | ❌ | ❌ |
| Đổi `equipment_code` / `department_id` | ❌ code; chỉ admin dept | ❌ | ❌ | ❌ | ❌ |
| Chạy CRON-5 thủ công | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 403 |

### 4.2 Điểm khác biệt cần chú ý (so với M3)
- **leader ở M5 = CHỈ XEM (👁)** — KHÁC M3 (leader ghi/duyệt được). Seed `roles_permissions` M5: leader KHÔNG có `equipment:create`/`equipment:update`/`calibration:create`. Dễ sai nhất khi copy logic từ M3.
- **accountant XEM được M5** (👁, theo quyết định đề bài) — KHÁC SRS OQ#5 mặc định "—" (không truy cập). Contract chốt theo đề bài: accountant có `equipment:read`, KHÔNG ghi.
- **staff đọc toàn lab, ghi phòng mình** (OQ#2 chốt): scope `equipment:read` = all; scope `equipment:create/update`/`calibration:create` = department. Backend ép phạm vi ghi theo `equipments.department_id == sub.department_id`.
- **Cảnh báo KHÔNG khóa cứng (OQ#3):** badge `overdue`/`failed` chỉ hiển thị — không endpoint nào trả 4xx vì lý do thiết bị quá hạn. Ghi hiệu chuẩn mới (#9) trên thiết bị quá hạn vẫn cho phép (FR-EQP-010 AC4).

### 4.3 Seed `roles_permissions` cần (M7)
- `equipment:read` — admin/leader/accountant/staff (scope all — đọc toàn lab).
- `equipment:create`, `equipment:update` — admin (all), staff (department). leader/accountant KHÔNG.
- `calibration:create` — admin (all), staff (department). leader/accountant KHÔNG.
- Cron CRON-5 thủ công — chỉ admin.

---

## 5. Ghi chú phi chức năng

- **Pagination:** mọi list `page`/`limit` (default 20, max 100), `meta.{page,limit,total,hasNext}` (đồng bộ M3/M4).
- **CorrelationId & audit (VILAS §6.4/§8.4 — BR-EQP-014, NFR-AUDIT-EQP-001):** mọi request có `X-Correlation-Id` (FE gửi/BE sinh, trả lại header); mọi thao tác ghi (tạo/sửa/xóa thiết bị, đính kèm, ghi hiệu chuẩn, tải cert) → `audit_logs` với `correlation_id`, `action`, `resource`, `resource_id`, `user`, `ip`, `at`. 100% thao tác ghi có bản ghi audit.
- **Immutable hiệu chuẩn (§8.4 — BR-EQP-007, NFR-INTEG-EQP-001):** `calibrations` append-only — KHÔNG route PATCH/DELETE; DB nên có trigger chặn UPDATE/DELETE. Đính chính = tạo bản ghi mới (`correction_of`).
- **Toàn vẹn next_due (NFR-INTEG-EQP-001):** `equipments.next_due_date` luôn = `next_due_date` của lần hiệu chuẩn `MAX(calibrated_at)`; cập nhật trong cùng transaction với #9; cộng tháng/năm an toàn năm nhuận (29/02→28/02). KHÔNG nhận trực tiếp từ client.
- **Badge cảnh báo:** tính runtime từ `equipments.next_due_date` vs `CURRENT_DATE` + `last_calibration_result` (đủ nhanh cho ~2,000 thiết bị với index `equipments(next_due_date)` — NFR-PERF-EQP-002). KHÔNG khóa cứng (CONSTRAINT-3).
- **Validation:** sanitize input tầng API; enum (`status`, `unit`, `result`) validate ở schema; `calibrated_at ≤ hôm nay`; `purchase_date ≤ hôm nay`; chu kỳ value > 0.
- **Upload (NFR-SEC-EQP-002):** chỉ PDF/DOCX/XLSX/PNG/JPG (CoC: PDF/PNG/JPG), validate MIME thực + đuôi, ≤ 20MB; lưu MinIO `file_key` (không binary trong DB); tải qua presigned URL TTL 15p kiểm soát quyền.
- **Performance (NFR-PERF-EQP-001/002):** ghi hiệu chuẩn (gồm tính next_due + cập nhật equipment + badge trong transaction, không tính upload) P95 < 400ms; list thiết bị + badge P95 < 500ms.
- **Cron idempotent (NFR-CRON-EQP-001):** CRON-5 APScheduler 07:00 + Redis lock (CONSTRAINT-8); idempotent mỗi (thiết bị × mốc 30/15/7); endpoint thủ công #15 chỉ admin để test.
- **Logging (NFR-OBS-EQP-001):** ghi hiệu chuẩn/cấu hình chu kỳ → INFO; ghi sai (ngày tương lai, thiếu chu kỳ, cố sửa immutable) → WARN; lỗi MinIO/transaction → ERROR kèm stack (không lộ ra client). KHÔNG log binary/PII.

---

## 6. Traceability: Endpoint → FR SRS M5

| Endpoint(s) | FR | Submodule | 17025 |
|-------------|-----|-----------|-------|
| #1, #3 | FR-EQP-004 (list/chi tiết + badge) | M5.1 | §6.4 |
| #1 (q lọc), #2 | FR-EQP-010 (cảnh báo quá hạn/không đạt) | M5.2 | §6.4 |
| #4 | FR-EQP-001 (tạo thiết bị) + FR-EQP-003 (sinh code) + FR-EQP-005 (chu kỳ) | M5.1/M5.2 | §6.4 |
| #5 | FR-EQP-002 (sửa thiết bị/tình trạng) + FR-EQP-005 (chu kỳ) | M5.1/M5.2 | §6.4/§8.4 |
| #6, #7 | FR-EQP-004 (đính kèm/tải tài liệu thiết bị) | M5.1 | §6.4 |
| #8, #10, #14 | FR-EQP-009 (lịch sử hiệu chuẩn + tải CoC) | M5.2 | §6.4/§6.5/§8.4 |
| #9 | FR-EQP-006 (ghi hiệu chuẩn + tự tính next_due) + FR-EQP-008 (cập nhật next_due theo lần gần nhất) | M5.2 | §6.4/§6.5 |
| (không route PATCH/DELETE calibrations) | FR-EQP-007 (bản ghi bất biến §8.4) | M5.2 | §8.4 |
| #15 | FR-EQP-011 (CRON-5 nhắc 30/15/7 ngày) | M5.2 | §6.4 |

**Mapping ISO/IEC 17025 (demo-scope mục E):**
- **§6.4 Thiết bị:** nhận biết & hồ sơ (#4/#5 mã+tình trạng+người phụ trách, #6 tài liệu); trạng thái hiệu chuẩn & ngăn dùng thiết bị không phù hợp (#1/#2/#3 badge + #15 nhắc trước); hiệu chuẩn định kỳ (#4/#5 chu kỳ + #9 ghi hiệu chuẩn + next_due).
- **§6.5 Liên kết chuẩn đo lường:** truy xuất nguồn gốc qua CoC/cert (#9 đính kèm cert, #8/#10/#14 lịch sử + tải cert).
- **§8.4 Kiểm soát hồ sơ:** bản ghi hiệu chuẩn **bất biến** (FR-EQP-007 — không route sửa/xóa); audit đầy đủ mọi thao tác (BR-EQP-014); giữ hồ sơ hiệu chuẩn không xóa.

**Phụ thuộc M7:** `users` (`responsible_user_id`); `departments.lead_user_id` (CRON-5 — BR-EQP-011); `attachments(owner_type ∈ {equipment, calibration})` (đã whitelist M7); `notifications` type=`CALIBRATION_DUE` + idempotency (CRON-5); `audit_logs`; quyền `equipment:read`/`equipment:create`/`equipment:update`/`calibration:create` (seed M7 — leader = 👁 chỉ xem, KHÁC M3). Đọc notifications qua API M7.

---

*Hết Contract M5 API (v1.0). 12 endpoint (5 ghi + 6 đọc + 1 cron). Đồng bộ phong cách M3/M4 (response envelope, UUID, pagination 20/100, correlationId, upload MinIO multipart + presigned 15p, immutable record, `/admin/crons/.../run`). Phản ánh quyết định đã chốt: leader & accountant CHỈ XEM (👁); staff đọc toàn lab + ghi phòng mình; cảnh báo (badge `calibration_status`/`is_overdue`) KHÔNG khóa cứng; chu kỳ theo từng thiết bị + next_due tự tính có override; bản ghi hiệu chuẩn bất biến (§8.4); CoC/cert lên MinIO (§6.5); CRON-5 nhắc 30/15/7 ngày in-app (R16). Side effect phức tạp nhất: #9 ghi hiệu chuẩn (1 transaction: insert immutable calibration + upload CoC MinIO + tính/cập nhật equipments.next_due_date theo lần gần nhất + cập nhật badge + audit).*
