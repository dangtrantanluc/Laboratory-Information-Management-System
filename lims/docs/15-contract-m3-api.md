# API Contract: M3 — Quản lý Tài liệu (Document Control)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M3 — Document Control (§8.3 kiểm soát tài liệu, §8.4 kiểm soát hồ sơ)
**Version:** 1.0 | **Ngày:** 20/06/2026 | **Designer:** api-designer agent
**Nguồn chân lý:** `13-srs-m3-document.md` (16 FR, 22 BR, state machine version, error codes)
**Đồng bộ phong cách:** `07-contract-m1-api.md` + `09-contract-m7-api.md` (response format, prefix `/api/v1`, UUID, pagination 20/100, correlationId, error code SNAKE_CASE, RBAC scope, upload MinIO multipart, presigned URL TTL 15p, state machine endpoints kiểu M1)
**Stack:** FastAPI + PostgreSQL + Redis + MinIO + APScheduler (monolith, ~40 user). Backend đã có M7+M1+M2+M4.

> M3 **phụ thuộc M7**: JWT auth, RBAC + phạm vi phòng ban, **trưởng nhóm cố định theo phòng** (`departments.lead_user_id` / claim `is_dept_lead`) làm nguồn quyền `document:approve`, `attachments` polymorphic (`owner_type='document_version'`), `audit_logs`, `notifications`. M3 tự tạo bảng riêng `document_access_log` (R15). State machine version `draft → review → approved → obsolete` theo pattern state machine M1.

---

## 0. Quy ước chung (đọc trước)

### 0.1 Base & versioning
- Prefix: `/api/v1`. Resource danh từ số nhiều: `/documents`, `/document-types`, `/confidentiality-levels`.
- Nested tối đa 2 cấp: `/documents/:id/versions`, `/documents/:id/access-stats`, `/documents/:id/history`.
- ID trong URL là **UUID** — KHÔNG lộ ID tuần tự (CONSTRAINT-5, BR-DOC-014, rule api.md). `document_code` (vd `SOP-HOA-012`) chỉ để hiển thị/tìm kiếm, KHÔNG dùng làm path param định danh.
- Không breaking change trong cùng `v1`; deprecated báo trước ≥ 1 sprint + header `Deprecation: true`.

### 0.2 Response format chuẩn (đồng bộ M1/M7)
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
    "details": [ { "field": "change_note", "message": "Bắt buộc từ phiên bản thứ 2" } ],
    "correlationId": "c1f2..."   // luôn trả để user report support (rule logging.md)
  } }
```

### 0.3 Auth & headers
- **Mọi endpoint M3** yêu cầu `Authorization: Bearer <JWT>` (M7). Không có endpoint public.
- **`X-Correlation-Id`** (UUID): client gửi; nếu thiếu, server tự sinh và trả lại trong response header + ghi vào `audit_logs.correlation_id` (audit VILAS §8.4 — BR-DOC-019).
- 401 `UNAUTHORIZED` nếu thiếu/sai token; 403 nếu thiếu quyền/sai phạm vi phòng ban/sai mức bảo mật.
- RBAC middleware đọc `role` + `dept` + `is_dept_lead` từ JWT claims (M7 §0.4) để enforce quyền + phạm vi mà không query DB mỗi request.

### 0.4 Pagination
- Tất cả endpoint list: `page` (default 1), `limit` (default **20**, max **100** — vượt ép về 100). **Offset-based** (quy mô ~40 user). `meta` luôn có `page`, `limit`, `total`, `hasNext`.

### 0.5 Rate limit
- Mặc định **60 req/phút/user** cho endpoint đọc/ghi nghiệp vụ.
- Upload file (tạo/sửa version có file): **30 req/phút/user**.
- Endpoint nặng (xuất Excel/PDF thống kê): **10 req/phút/user**.
- Vượt giới hạn → **429** code `RATE_LIMIT_EXCEEDED`.

### 0.6 RBAC tổng quát M3 (BR-DOC-004, BR-DOC-005, BR-DOC-010)
- **4 vai trò:** `admin` (toàn quyền mọi phòng), `leader` (Ban lãnh đạo — duyệt + xem mọi phòng/mọi mức bảo mật), `accountant` (Kế toán — **CHỈ XEM** version approved/current), `staff` (Nhân sự/KTV).
- **Kế toán: CHỈ XEM (👁).** Mọi endpoint **ghi** của M3 (tạo/sửa tài liệu & version, gửi duyệt, duyệt, từ chối, upload) trả **403 `FORBIDDEN`** cho Kế toán — chặn ở **tầng API**, không chỉ ẩn FE (BR-DOC-005). Kế toán chỉ thấy/tải version `approved` (không thấy `draft`/`review`).
- **Phạm vi phòng ban (staff):** staff **ghi** (tạo/sửa tài liệu & version, gửi duyệt) chỉ trong `department_id` của mình; ghi chéo phòng → **403 `FORBIDDEN`**. **Đọc/tải** version approved: toàn lab (mọi phòng) theo mức bảo mật. Admin & leader = toàn hệ thống.
- **Trưởng nhóm cố định theo phòng** (M7 `departments.lead_user_id` / claim `is_dept_lead` — KHÔNG phải vai trò RBAC thứ 5): chỉ **trưởng nhóm phòng đó** / leader / admin có quyền `document:approve` (duyệt + từ chối + ban hành). Staff thường KHÔNG có → 403 `FORBIDDEN`.
- **Tách soạn–duyệt (§8.3.2):** người **duyệt** (`approved_by`) ≠ người **soạn** version (`created_by`) — kể cả nếu người soạn là trưởng nhóm (BR-DOC-009). Vi phạm → 403 `SELF_APPROVAL_FORBIDDEN`.

### 0.7 Hai mức bảo mật (`security_level`) — enforce list/get/download (BR-DOC-006)
- Bản đầu **2 mức:** `internal` (mọi nhân sự đã đăng nhập đọc/tải bản approved), `restricted` (CHỈ user thuộc **phòng sở hữu** tài liệu + admin + leader). Kế toán đọc được `internal` approved; `restricted` → ẩn khỏi list + 403 khi truy cập trực tiếp.
- Enforce ở **3 nơi**: (1) `GET /documents` (list — tài liệu `restricted` ngoài phòng không xuất hiện), (2) `GET /documents/:id` (chi tiết — 404 ẩn sự tồn tại nếu không có quyền), (3) `GET /documents/:id/versions/:vid/download` (tải — 403 `RESTRICTED_ACCESS`).
- Bảng quyết định:

| Tài liệu | admin | leader | staff phòng sở hữu | staff phòng khác | accountant |
|----------|-------|--------|--------------------|--------------------|------------|
| `internal` (approved) | ✅ | ✅ | ✅ | ✅ | ✅ |
| `restricted` (approved) | ✅ | ✅ | ✅ | ❌ ẩn/403 | ❌ ẩn/403 |
| version `draft`/`review` | ✅ | ✅ | 👁 chỉ người soạn + trưởng nhóm phòng | ❌ | ❌ |
| version `obsolete` | ✅ tải có cảnh báo | ✅ | ✅ tải có cảnh báo (theo mức bảo mật) | theo mức bảo mật | ❌ (chỉ approved) |

### 0.8 Phạm vi hiển thị version theo trạng thái (BR-DOC-011)
- `approved` / `obsolete`: hiển thị cho mọi người có quyền xem tài liệu (theo `security_level`). `obsolete` luôn kèm cờ `is_obsolete=true` + nhãn "KHÔNG SỬ DỤNG / lỗi thời" (BR-DOC-022).
- `draft` / `review`: CHỈ người soạn (`created_by`) + người duyệt phòng đó (trưởng nhóm) + admin + leader. Người khác không thấy version này trong `GET /documents/:id` và bị 403 `VERSION_NOT_PUBLISHED` khi tải.

### 0.9 Flow file đính kèm (đồng bộ M1 §0.8 / M2)
- **Upload qua API multipart** (`Content-Type: multipart/form-data`): backend đẩy file lên MinIO (C01), lưu `file_key` trong `attachments` (`owner_type='document_version'`, `owner_id=document_versions.id`), KHÔNG lưu binary trong DB.
- Whitelist MIME (BR-DOC-013): PDF, DOCX, XLSX, PNG, JPG. CẤM file thực thi/macro (`.docm`, `.exe`, `.js`...). Validate **MIME thực + đuôi**. Size ≤ giới hạn cấu hình (mặc định 20MB).
- **Tải file:** trả **presigned URL MinIO TTL 15 phút** (`download_url` + `url_expires_at`), không proxy binary qua API.

### 0.10 Bất biến (immutable — VILAS §8.3.2 d / §8.4)
- Version `approved`/`obsolete`: KHÔNG có endpoint sửa file/change_note/xóa trực tiếp (BR-DOC-012, CONSTRAINT-3). Sửa nội dung đã ban hành = **tạo version mới** (`draft`) đi lại quy trình duyệt.
- `documents.code`: bất biến sau khi tạo (BR-DOC-014). Cố đổi → 422 `CODE_IMMUTABLE`.
- KHÔNG hard-delete version đã từng `approved`/`obsolete`, KHÔNG hard-delete tài liệu đã có version approved (BR-DOC-021). Chỉ version `draft` chưa từng gửi duyệt được soft-delete.
- Chuyển trạng thái version chỉ qua hàm transition trung tâm + whitelist (FR-DOC-013); không có endpoint set status tùy ý.

---

## 1. Bảng tổng hợp Endpoint

| # | Method | Path | Mô tả | Vai trò (ghi) | Scope | FR |
|---|--------|------|-------|---------------|-------|-----|
| **Danh mục (lookup)** ||||||
| 1 | GET | `/api/v1/document-types` | Danh mục loại tài liệu (đã seed) | Mọi vai trò (đọc) | Toàn HT | FR-002 |
| 2 | GET | `/api/v1/confidentiality-levels` | Danh mục mức bảo mật (internal/restricted) | Mọi vai trò (đọc) | Toàn HT | FR-003 |
| **Tài liệu (M3.1)** ||||||
| 3 | GET | `/api/v1/documents` | Tìm/lọc/liệt kê tài liệu (type/dept/status/security/q) | Mọi vai trò (đọc, theo mức bảo mật) | Đọc theo phạm vi | FR-004 |
| 4 | POST | `/api/v1/documents` | Tạo tài liệu (metadata + sinh `document_code`); kèm version đầu (upload file) | admin, leader, staff(phòng) | Ghi theo phòng | FR-001/003/006 |
| 5 | GET | `/api/v1/documents/:id` | Chi tiết tài liệu + version current + danh sách version (lọc theo quyền) | Mọi vai trò (đọc) | Đọc | FR-005 |
| 6 | PATCH | `/api/v1/documents/:id` | Sửa metadata tài liệu (title/type/security_level) — KHÔNG đổi code/dept | admin, leader, staff(phòng) | Ghi theo phòng | FR-002 |
| 7 | DELETE | `/api/v1/documents/:id` | Soft-delete tài liệu (chỉ khi chưa có version approved) | admin, leader, staff(phòng) | Ghi theo phòng | FR-002/BR-021 |
| **Version & Lịch sử (M3.2 — cốt lõi VILAS §8.3)** ||||||
| 8 | GET | `/api/v1/documents/:id/versions` | Liệt kê version của tài liệu (lọc theo quyền hiển thị) | Mọi vai trò (đọc) | Đọc | FR-005 |
| 9 | POST | `/api/v1/documents/:id/versions` | Tạo version mới (upload file + change_note, status=draft) | admin, leader, staff(phòng) | Ghi theo phòng | FR-006 |
| 10 | GET | `/api/v1/documents/:id/versions/:vid` | Chi tiết 1 version | Mọi vai trò (đọc, theo trạng thái) | Đọc | FR-005 |
| 11 | PATCH | `/api/v1/documents/:id/versions/:vid` | Sửa version `draft` (thay file / sửa change_note) | Người soạn, leader, admin | Ghi theo phòng | FR-007 |
| 12 | POST | `/api/v1/documents/:id/versions/:vid/submit-review` | Gửi duyệt (draft → review) | Người soạn, leader, admin | Ghi theo phòng | FR-008 |
| 13 | POST | `/api/v1/documents/:id/versions/:vid/approve` | Duyệt/ban hành (review → approved) + tự obsolete bản cũ | **TN phòng**, leader, admin | Ghi theo phòng | FR-009/011 |
| 14 | POST | `/api/v1/documents/:id/versions/:vid/reject` | Từ chối (review → draft) kèm `reject_reason` | **TN phòng**, leader, admin | Ghi theo phòng | FR-010 |
| 15 | GET | `/api/v1/documents/:id/versions/:vid/download` | Tải file version (presigned URL) + ghi access_log `download` | Mọi vai trò (đọc, theo trạng thái + mức bảo mật) | Đọc | FR-012 |
| 16 | GET | `/api/v1/documents/:id/history` | Lịch sử thay đổi (timeline version + audit) | Mọi vai trò (đọc, lọc theo quyền) | Đọc | FR-016 |
| 17 | GET | `/api/v1/documents/pending-review` | Danh sách version chờ tôi duyệt | **TN phòng**, leader, admin | Đọc theo phòng | FR-009 |
| **Thống kê truy cập (M3.3 — R15)** ||||||
| 18 | GET | `/api/v1/documents/:id/access-stats` | Thống kê view/download/edit của 1 tài liệu (theo khoảng thời gian) | admin, leader, staff(phòng) | Đọc theo phạm vi | FR-015 |
| 19 | GET | `/api/v1/documents/access-stats` | Thống kê tổng hợp + top N (lọc dept/action/at-range) | admin, leader, staff(phòng) | Đọc theo phạm vi | FR-015 |
| 20 | GET | `/api/v1/documents/access-stats/export` | Xuất Excel/PDF thống kê truy cập | admin, leader | Đọc theo phạm vi | FR-015 |

> **TN** = trưởng nhóm phòng đó (`is_dept_lead=true`) · **LĐ/leader** = Ban lãnh đạo.
> **Kế toán (accountant):** 403 `FORBIDDEN` trên TẤT CẢ endpoint **ghi** (#4, #6, #7, #9, #11, #12, #13, #14) — không liệt kê lại từng dòng. Kế toán chỉ gọi được endpoint đọc (#1, #2, #3, #5, #8, #10, #15, #16) và CHỈ thấy/tải version `approved`.
> **Append-only:** `audit_logs` + `document_access_log` ghi nội bộ bởi service (bất biến), KHÔNG có endpoint POST/PATCH/DELETE cho client ghi log. Chuyển trạng thái version chỉ qua endpoint hành động (#12/#13/#14) — không có PATCH status tùy ý.

---

## 2. Chi tiết Endpoint

---

### 1. GET /api/v1/document-types
**Mục đích:** Lấy danh mục loại tài liệu đã seed (SOP / quy trình / biểu mẫu / hướng dẫn / tiêu chuẩn) để FE render dropdown khi tạo/lọc tài liệu (FR-002, BR-DOC-002).
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc) | **Scope:** toàn HT | **Rate limit:** 60/min

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "code": "SOP", "label": "Quy trình thao tác chuẩn (SOP)", "prefix": "SOP" },
    { "code": "PROCEDURE", "label": "Quy trình", "prefix": "QT" },
    { "code": "FORM", "label": "Biểu mẫu", "prefix": "BM" },
    { "code": "GUIDE", "label": "Hướng dẫn công việc", "prefix": "HD" },
    { "code": "STANDARD", "label": "Tiêu chuẩn / Quy chuẩn", "prefix": "TC" }
  ]
}
```
> `prefix` dùng để sinh `document_code` (FR-003): `<prefix loại>-<mã phòng>-<seq>`.

**Errors:** `UNAUTHORIZED` (401).

---

### 2. GET /api/v1/confidentiality-levels
**Mục đích:** Lấy danh mục mức bảo mật (FR-003, BR-DOC-003). Bản đầu 2 mức.
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc) | **Scope:** toàn HT | **Rate limit:** 60/min

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "code": "internal", "label": "Nội bộ", "description": "Mọi nhân sự đã đăng nhập đọc/tải bản approved", "is_default": true },
    { "code": "restricted", "label": "Hạn chế", "description": "Chỉ phòng sở hữu + Ban lãnh đạo + Admin", "is_default": false }
  ]
}
```

**Errors:** `UNAUTHORIZED` (401).

---

### 3. GET /api/v1/documents
**Mục đích:** Tìm/lọc/liệt kê tài liệu có phân trang; mặc định hiển thị **version hiệu lực (current)** của mỗi tài liệu (FR-004). Áp RBAC + mức bảo mật (BR-DOC-006).
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc — gồm Kế toán 👁) | **Scope:** đọc theo phạm vi mức bảo mật | **Rate limit:** 60/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| q | string | ❌ | maxLength(100) | Từ khóa: `document_code` hoặc `title` |
| type | enum | ❌ | SOP\|PROCEDURE\|FORM\|GUIDE\|STANDARD | Lọc loại tài liệu |
| department_id | uuid | ❌ | tồn tại | Lọc phòng ban sở hữu |
| security_level | enum | ❌ | internal\|restricted | Lọc mức bảo mật |
| status | enum | ❌ | has_current\|no_current (default tất cả) | Đã có version approved hay chưa |
| page/limit | int | ❌ | pagination chuẩn | |

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "doc-uuid",
      "document_code": "SOP-HOA-012",
      "title": "SOP đo pH",
      "type": "SOP",
      "type_label": "Quy trình thao tác chuẩn (SOP)",
      "department_id": "dept-uuid",
      "department_name": "Hóa lý",
      "security_level": "internal",
      "status": "active",
      "current_version": {
        "id": "ver-uuid",
        "version_no": 2,
        "status": "approved",
        "approved_at": "2026-06-10T03:00:00Z",
        "approved_by_name": "Trưởng nhóm T"
      },
      "created_at": "2026-03-01T02:00:00Z"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 50, "hasNext": true }
}
```
> `current_version=null` nếu tài liệu chưa có version approved. Tài liệu chưa có current chỉ hiển thị cho người soạn/duyệt phòng đó + admin/leader (Kế toán/staff phòng khác KHÔNG thấy — BR-DOC-011). Tài liệu `restricted` ngoài phòng KHÔNG xuất hiện trong list (BR-DOC-006). Mở chi tiết (#5) mới ghi `document_access_log` action=`view`; list không ghi từng dòng.

**Errors:** `FORBIDDEN` (403 — accountant nếu lọc/truy cập restricted ngoài phạm vi), `VALIDATION_ERROR` (400 — filter sai enum), `UNAUTHORIZED` (401).

---

### 4. POST /api/v1/documents
**Mục đích:** Tạo tài liệu (metadata + sinh `document_code` duy nhất, không lộ tuần tự) **kèm version đầu (v1)** — upload file v1 trong cùng request multipart (FR-001/003/006, UC-DOC-01).
**Auth:** Bearer JWT | **Roles:** admin, leader, staff(phòng mình) | **Scope:** ghi theo phòng | **Rate limit:** 30/min (có upload)

**Content-Type:** `multipart/form-data`

**Request (multipart fields):**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| title | string | ✅ | maxLength(255), trim non-empty | Tiêu đề tài liệu |
| type | enum | ✅ | SOP\|PROCEDURE\|FORM\|GUIDE\|STANDARD | Loại tài liệu (BR-DOC-002) |
| department_id | uuid | ❌ | tồn tại; default = phòng của user | Phòng ban sở hữu (staff bắt buộc = phòng mình) |
| security_level | enum | ❌ | internal\|restricted (default `internal`) | Mức bảo mật (BR-DOC-003) |
| change_note | string | ❌ | maxLength(1000) | Ghi chú v1 (không bắt buộc cho v1 — BR-DOC-016) |
| file | binary | ✅ | MIME whitelist + ≤20MB (BR-DOC-013) | File nội dung v1 |

> `document_code`, `id` (UUID), `version_no=1`, `status` (tài liệu=`active`, version=`draft`) do server thiết lập — KHÔNG nhận từ client. Tạo tài liệu + v1 + upload trong **1 transaction**; lỗi upload → rollback cả tài liệu (không để tài liệu rỗng).

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "doc-uuid",
    "document_code": "SOP-HOA-013",
    "title": "SOP đo pH",
    "type": "SOP",
    "department_id": "dept-uuid",
    "department_name": "Hóa lý",
    "security_level": "internal",
    "status": "active",
    "current_version_id": null,
    "created_by": "user-uuid",
    "created_at": "2026-06-20T08:00:00Z",
    "first_version": {
      "id": "ver-uuid",
      "version_no": 1,
      "status": "draft",
      "change_note": null,
      "file": { "attachment_id": "att-uuid", "filename": "sop-do-ph-v1.pdf", "size": 348201, "mime": "application/pdf" },
      "created_at": "2026-06-20T08:00:00Z"
    }
  }
}
```
> `current_version_id=null` vì v1 còn `draft` (chưa duyệt). Tài liệu có version hiệu lực chỉ sau khi v1 được approve (#13).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | Thiếu title / type / file; type sai enum (BR-DOC-002) |
| INVALID_CONFIDENTIALITY | 422 | security_level ngoài danh mục (BR-DOC-003) |
| INVALID_FILE_TYPE | 422 | File ngoài whitelist MIME (BR-DOC-013) |
| FILE_TOO_LARGE | 422 | File > 20MB (BR-DOC-013) |
| DEPARTMENT_NOT_FOUND | 404 | department_id không tồn tại |
| FORBIDDEN | 403 | staff tạo tài liệu cho phòng khác (BR-DOC-004); **accountant** gọi endpoint ghi (BR-DOC-005) |
| DUPLICATE_DOCUMENT_CODE | 409 | Sinh trùng `document_code` sau N lần retry (FR-003 A1 — hiếm) |

**Side effects:**
- Tạo `documents` (`status=active`, `current_version_id=null`) + sinh `document_code` (`<prefix>-<mã phòng>-<seq>`, unique).
- Tạo `document_versions` v1 (`status=draft`, `created_by`) + đẩy file MinIO + `attachments` (`owner_type='document_version'`).
- `audit_logs` action=`DOCUMENT_CREATE` + `DOCUMENT_VERSION_CREATE`.
- `document_access_log` action=`edit` (R15 — BR-DOC-015).

---

### 5. GET /api/v1/documents/:id
**Mục đích:** Chi tiết tài liệu: metadata + version current nổi bật + danh sách version (đã lọc theo quyền hiển thị — BR-DOC-011). Ghi access_log `view` (FR-005).
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc, theo mức bảo mật) | **Scope:** đọc | **Rate limit:** 60/min

**Path:** `id` = document UUID.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "doc-uuid",
    "document_code": "SOP-HOA-012",
    "title": "SOP đo pH",
    "type": "SOP",
    "type_label": "Quy trình thao tác chuẩn (SOP)",
    "department_id": "dept-uuid",
    "department_name": "Hóa lý",
    "security_level": "internal",
    "status": "active",
    "current_version_id": "ver2-uuid",
    "created_by_name": "Nguyễn Văn A",
    "created_at": "2026-03-01T02:00:00Z",
    "current_version": {
      "id": "ver2-uuid", "version_no": 2, "status": "approved",
      "change_note": "Cập nhật ngưỡng hiệu chuẩn máy",
      "created_by_name": "Nguyễn Văn A", "created_at": "2026-06-05T02:00:00Z",
      "approved_by_name": "Trưởng nhóm T", "approved_at": "2026-06-10T03:00:00Z",
      "file": { "attachment_id": "att2-uuid", "filename": "sop-do-ph-v2.pdf", "size": 351002, "mime": "application/pdf" }
    },
    "versions": [
      { "id": "ver1-uuid", "version_no": 1, "status": "obsolete", "is_obsolete": true,
        "obsolete_label": "KHÔNG SỬ DỤNG — lỗi thời",
        "created_by_name": "Nguyễn Văn A", "created_at": "2026-03-01T02:00:00Z",
        "approved_by_name": "Trưởng nhóm T", "approved_at": "2026-03-03T03:00:00Z" },
      { "id": "ver2-uuid", "version_no": 2, "status": "approved", "is_obsolete": false,
        "created_by_name": "Nguyễn Văn A", "approved_by_name": "Trưởng nhóm T", "approved_at": "2026-06-10T03:00:00Z" },
      { "id": "ver3-uuid", "version_no": 3, "status": "draft", "is_obsolete": false,
        "change_note": "Bổ sung mục an toàn", "created_by_name": "Nguyễn Văn A", "created_at": "2026-06-19T02:00:00Z" }
    ]
  }
}
```
> `versions[]` đã **lọc theo quyền** (BR-DOC-011): staff phòng khác / Kế toán KHÔNG thấy `ver3 draft` (chỉ thấy approved + obsolete). Người soạn/trưởng nhóm phòng đó/admin/leader thấy đủ. `obsolete` luôn kèm `is_obsolete=true` + `obsolete_label` (BR-DOC-022).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| DOCUMENT_NOT_FOUND | 404 | id không tồn tại; HOẶC tài liệu `restricted` ngoài phạm vi user (ẩn sự tồn tại — BR-DOC-006); HOẶC tài liệu chưa có current + user không phải người soạn/duyệt phòng đó/admin/leader |
| FORBIDDEN | 403 | (tùy chính sách hiển thị) user truy cập trực tiếp tài liệu mức bảo mật cao hơn quyền |
| UNAUTHORIZED | 401 | Thiếu token |

**Side effects:** `document_access_log` action=`view` (BR-DOC-015) — best-effort, không chặn nghiệp vụ nếu ghi lỗi.

---

### 6. PATCH /api/v1/documents/:id
**Mục đích:** Sửa metadata cấp tài liệu (`title`, `type`, `security_level`). KHÔNG đổi `document_code` (bất biến — BR-DOC-014) và KHÔNG đổi `department_id` (trừ admin — ngoài bản đầu). Không ảnh hưởng nội dung version (FR-002).
**Auth:** Bearer JWT | **Roles:** admin, leader, staff(phòng mình) | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body (≥1 field):**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| title | string | ❌ | maxLength(255), trim non-empty | Tiêu đề |
| type | enum | ❌ | SOP\|PROCEDURE\|FORM\|GUIDE\|STANDARD | Loại tài liệu |
| security_level | enum | ❌ | internal\|restricted | Mức bảo mật |

> Gửi `document_code` hoặc `department_id` (non-admin) trong body → 422 `CODE_IMMUTABLE` / 403.

**Response 200:** object tài liệu như #5 (không có `versions`).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | body rỗng / field sai enum |
| CODE_IMMUTABLE | 422 | Cố đổi `document_code` (BR-DOC-014) |
| INVALID_CONFIDENTIALITY | 422 | security_level ngoài danh mục |
| FORBIDDEN | 403 | staff sửa tài liệu phòng khác (BR-DOC-004); accountant (BR-DOC-005) |
| DOCUMENT_NOT_FOUND | 404 | id không tồn tại |

**Side effects:** `audit_logs` action=`DOCUMENT_UPDATE` (detail = diff before/after từng trường, đặc biệt đổi `security_level`).

---

### 7. DELETE /api/v1/documents/:id
**Mục đích:** Soft-delete tài liệu — CHỈ khi **chưa có version approved** (mọi version đều `draft`/chưa từng ban hành). Tài liệu đã có version approved/obsolete KHÔNG được xóa (giữ hồ sơ §8.4 — BR-DOC-021).
**Auth:** Bearer JWT | **Roles:** admin, leader, staff(phòng mình) | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Response 200:** `{ "success": true, "data": { "id": "doc-uuid", "status": "deleted" } }`

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| DOCUMENT_HAS_APPROVED_VERSION | 422 | Tài liệu đã có version từng approved/obsolete (BR-DOC-021) |
| FORBIDDEN | 403 | staff phòng khác (BR-DOC-004); accountant (BR-DOC-005) |
| DOCUMENT_NOT_FOUND | 404 | id không tồn tại |

**Side effects:** `documents.status=deleted` (soft); `audit_logs` action=`DOCUMENT_DELETE`. KHÔNG xóa file MinIO của các draft (giữ truy vết).

---

### 8. GET /api/v1/documents/:id/versions
**Mục đích:** Liệt kê toàn bộ version của tài liệu, đã lọc theo quyền hiển thị (BR-DOC-011) — FR-005.
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc) | **Scope:** đọc | **Rate limit:** 60/min

**Query params:** `status` (optional enum `draft|review|approved|obsolete`), `page/limit`.

**Response 200:**
```json
{
  "success": true,
  "data": [
    { "id": "ver1-uuid", "version_no": 1, "status": "obsolete", "is_obsolete": true,
      "obsolete_label": "KHÔNG SỬ DỤNG — lỗi thời",
      "change_note": null, "created_by_name": "Nguyễn Văn A", "created_at": "2026-03-01T02:00:00Z",
      "approved_by_name": "Trưởng nhóm T", "approved_at": "2026-03-03T03:00:00Z" },
    { "id": "ver2-uuid", "version_no": 2, "status": "approved", "is_obsolete": false,
      "change_note": "Cập nhật ngưỡng hiệu chuẩn máy", "created_by_name": "Nguyễn Văn A",
      "approved_by_name": "Trưởng nhóm T", "approved_at": "2026-06-10T03:00:00Z" }
  ],
  "meta": { "page": 1, "limit": 20, "total": 2, "hasNext": false }
}
```
> Sắp xếp `version_no` giảm dần. Kế toán / staff phòng khác KHÔNG thấy `draft`/`review` (chỉ approved/obsolete).

**Errors:** `DOCUMENT_NOT_FOUND` (404), `FORBIDDEN` (403 restricted ngoài phạm vi), `UNAUTHORIZED` (401).

---

### 9. POST /api/v1/documents/:id/versions
**Mục đích:** Tạo version mới cho tài liệu (`version_no` = max+1, `status=draft`) + upload **1 file chính** + `change_note` (bắt buộc từ v2 — BR-DOC-016). KHÔNG đổi version current hiện hành (FR-006, UC-DOC-02).
**Auth:** Bearer JWT | **Roles:** admin, leader, staff(phòng mình) | **Scope:** ghi theo phòng | **Rate limit:** 30/min (upload)

**Content-Type:** `multipart/form-data`

**Request (multipart fields):**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| change_note | string | ✅* | maxLength(1000) | Mô tả thay đổi so với version trước (*bắt buộc nếu đã có version trước — BR-DOC-016) |
| file | binary | ✅ | MIME whitelist + ≤20MB (BR-DOC-013) | File nội dung version |

> `version_no`, `status=draft`, `created_by` do server thiết lập. Mặc định cho phép **tối đa 1 version đang soạn/chờ duyệt** (`draft`/`review`) cho mỗi tài liệu (OQ#6) → tạo thêm khi đang có draft/review → 409.

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "ver3-uuid",
    "document_id": "doc-uuid",
    "version_no": 3,
    "status": "draft",
    "change_note": "Bổ sung mục an toàn hóa chất",
    "created_by": "user-uuid",
    "created_by_name": "Nguyễn Văn A",
    "created_at": "2026-06-20T08:10:00Z",
    "file": { "attachment_id": "att3-uuid", "filename": "sop-do-ph-v3.pdf", "size": 360112, "mime": "application/pdf" }
  }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| CHANGE_NOTE_REQUIRED | 400 | Thiếu change_note ở version ≥ 2 (BR-DOC-016) |
| INVALID_FILE_TYPE | 422 | File ngoài whitelist (BR-DOC-013) |
| FILE_TOO_LARGE | 422 | File > 20MB |
| DRAFT_ALREADY_EXISTS | 409 | Đã tồn tại version `draft`/`review` chưa kết thúc (OQ#6 default) |
| FORBIDDEN | 403 | staff tạo version tài liệu phòng khác (BR-DOC-004); accountant (BR-DOC-005) |
| DOCUMENT_NOT_FOUND | 404 | document id không tồn tại |

**Side effects:** Tạo `document_versions` (`status=draft`) + file MinIO + `attachments`; `audit_logs` action=`DOCUMENT_VERSION_CREATE`; `document_access_log` action=`edit` (BR-DOC-015). Version current hiện hành KHÔNG đổi.

---

### 10. GET /api/v1/documents/:id/versions/:vid
**Mục đích:** Chi tiết 1 version (metadata + file + mốc duyệt) (FR-005).
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc, theo trạng thái + mức bảo mật) | **Scope:** đọc | **Rate limit:** 60/min

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "ver3-uuid",
    "document_id": "doc-uuid",
    "document_code": "SOP-HOA-012",
    "version_no": 3,
    "status": "review",
    "is_obsolete": false,
    "change_note": "Bổ sung mục an toàn hóa chất",
    "created_by_name": "Nguyễn Văn A",
    "created_at": "2026-06-19T02:00:00Z",
    "submitted_at": "2026-06-20T02:00:00Z",
    "approved_by_name": null,
    "approved_at": null,
    "reject_reason": null,
    "file": { "attachment_id": "att3-uuid", "filename": "sop-do-ph-v3.pdf", "size": 360112, "mime": "application/pdf" }
  }
}
```

**Errors:** `VERSION_NOT_FOUND` (404), `VERSION_NOT_PUBLISHED` (403 — xem version draft/review không có quyền, BR-DOC-011), `RESTRICTED_ACCESS` (403 — restricted ngoài phạm vi), `DOCUMENT_NOT_FOUND` (404).

---

### 11. PATCH /api/v1/documents/:id/versions/:vid
**Mục đích:** Sửa version đang `draft` (thay file / sửa `change_note`). CHỈ version `draft`; `review`/`approved`/`obsolete` bất biến với thao tác sửa (BR-DOC-012, CONSTRAINT-3) — FR-007.
**Auth:** Bearer JWT | **Roles:** người soạn (`created_by`) phòng mình, leader, admin | **Scope:** ghi theo phòng | **Rate limit:** 30/min (nếu thay file)

**Content-Type:** `multipart/form-data` (nếu thay file) hoặc `application/json` (chỉ sửa change_note).

**Request (≥1 field):**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| change_note | string | ❌ | maxLength(1000) | Sửa ghi chú thay đổi |
| file | binary | ❌ | MIME whitelist + ≤20MB | File mới thay thế (đẩy MinIO; attachment cũ của version này được thay/đánh dấu) |

**Response 200:** object version như #10.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VERSION_LOCKED | 422 | Version không ở `draft` (đã review/approved/obsolete — BR-DOC-012) |
| INVALID_FILE_TYPE | 422 | File ngoài whitelist |
| FILE_TOO_LARGE | 422 | File > 20MB |
| VALIDATION_ERROR | 400 | body rỗng |
| FORBIDDEN | 403 | Không phải người soạn và không trưởng nhóm/admin/leader (FR-007 A2); accountant |
| VERSION_NOT_FOUND | 404 | vid không tồn tại |

**Side effects:** Cập nhật file/change_note; `audit_logs` action=`DOCUMENT_VERSION_UPDATE` (diff); `document_access_log` action=`edit` (BR-DOC-015).

---

### 12. POST /api/v1/documents/:id/versions/:vid/submit-review
**Mục đích:** Gửi version đi duyệt (`draft → review`). Tạo notification cho người duyệt (trưởng nhóm phòng / leader / admin). Version `review` khóa sửa (FR-008, state machine FR-013).
**Auth:** Bearer JWT | **Roles:** người soạn (`created_by`), leader, admin | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body:** rỗng.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "ver3-uuid", "version_no": 3, "status": "review",
    "submitted_at": "2026-06-20T08:20:00Z",
    "state_change": { "from": "draft", "to": "review" }
  }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| INVALID_STATE_TRANSITION | 422 | Version không ở `draft` (vd đang `review`/`approved`) — không nằm trong whitelist `draft→review` (BR-DOC-007) |
| VERSION_FILE_REQUIRED | 422 | Version chưa có file đính kèm (BR-DOC-017) |
| FORBIDDEN | 403 | Không phải người soạn/admin/leader; accountant |
| VERSION_NOT_FOUND | 404 | vid không tồn tại |

**Side effects:**
- Chuyển `draft → review` (set `submitted_at`); khóa sửa version.
- Tạo `notifications` cho người duyệt đủ quyền (trưởng nhóm phòng đó / leader / admin), idempotent theo `(version_id, event)` (BR-DOC-018).
- `audit_logs` action=`DOCUMENT_VERSION_SUBMIT` + `DOCUMENT_VERSION_STATE_CHANGE` (from=draft, to=review).

---

### 13. POST /api/v1/documents/:id/versions/:vid/approve
**Mục đích:** Duyệt/ban hành version (`review → approved`); set `approved_by`/`approved_at`; **trong cùng transaction (row-lock trên document):** version approved cũ (nếu có) tự động `obsolete` + `documents.current_version_id` = version vừa approve (FR-009/011, UC-DOC-03 — CỐT LÕI §8.3).
**Auth:** Bearer JWT | **Roles:** **trưởng nhóm phòng đó** (`is_dept_lead`), leader, admin | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body:** rỗng (hoặc optional `note` ghi chú duyệt).

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "ver3-uuid",
    "version_no": 3,
    "status": "approved",
    "approved_by": "userT-uuid",
    "approved_by_name": "Trưởng nhóm T",
    "approved_at": "2026-06-20T08:30:00Z",
    "state_change": { "from": "review", "to": "approved" },
    "document": {
      "id": "doc-uuid",
      "current_version_id": "ver3-uuid",
      "obsoleted_version": { "id": "ver2-uuid", "version_no": 2, "status": "obsolete" }
    }
  }
}
```
> `obsoleted_version=null` nếu đây là lần ban hành đầu (FR-011 A1). Sau approve: đúng **1 version `approved` (current)** cho tài liệu (BR-DOC-008).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| SELF_APPROVAL_FORBIDDEN | 403 | Người duyệt = người soạn version (`approved_by==created_by`) — tách trách nhiệm §8.3.2 (BR-DOC-009) |
| FORBIDDEN | 403 | Không có quyền `document:approve` (staff thường không phải trưởng nhóm phòng đó); accountant (BR-DOC-010/005) |
| INVALID_STATE_TRANSITION | 422 | Version không ở `review` (vd `draft` — duyệt thẳng bỏ review) (BR-DOC-007) |
| VERSION_CONFLICT | 409 | 2 request approve 2 version khác nhau của cùng tài liệu đồng thời — chỉ 1 thắng làm current; request thua nhận lỗi (NFR-CONCUR-DOC-001, FR-009 A4) |
| VERSION_NOT_FOUND | 404 | vid không tồn tại |

**Side effects (trong 1 transaction):**
- Version `review → approved` (set approved_by/approved_at); `audit_logs` action=`DOCUMENT_VERSION_APPROVE` + `DOCUMENT_VERSION_STATE_CHANGE`.
- Version approved cũ (nếu có) → `obsolete`; `audit_logs` action=`DOCUMENT_VERSION_OBSOLETE` (auto).
- Set `documents.current_version_id` = version vừa approve.
- Tạo `notifications` cho người soạn ("phiên bản đã được ban hành") — idempotent (BR-DOC-018).

---

### 14. POST /api/v1/documents/:id/versions/:vid/reject
**Mục đích:** Từ chối version đang `review` (`review → draft`) kèm `reject_reason` bắt buộc; mở lại để người soạn sửa rồi gửi duyệt lại (FR-010). Không có trạng thái "rejected" riêng (state machine gọn).
**Auth:** Bearer JWT | **Roles:** **trưởng nhóm phòng đó**, leader, admin | **Scope:** ghi theo phòng | **Rate limit:** 60/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| reject_reason | string | ✅ | maxLength(1000), trim non-empty | Lý do từ chối (BR-DOC-020) |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "ver3-uuid", "version_no": 3, "status": "draft",
    "reject_reason": "Thiếu mục an toàn hóa chất",
    "state_change": { "from": "review", "to": "draft" }
  }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| REJECT_REASON_REQUIRED | 400 | Thiếu reject_reason (BR-DOC-020) |
| INVALID_STATE_TRANSITION | 422 | Version không ở `review` (BR-DOC-007) |
| FORBIDDEN | 403 | Không có quyền `document:approve`; accountant (BR-DOC-010/005) |
| VERSION_NOT_FOUND | 404 | vid không tồn tại |

> **Lưu ý:** `reject` KHÔNG check `SELF_APPROVAL_FORBIDDEN` (người soạn không tự gửi mình → không tự reject; nhưng nếu cần, trưởng nhóm = người soạn vẫn không nên reject chính mình — app cho phép vì reject không phải "phê duyệt ban hành"). Theo SRS reject là quyền `document:approve`.

**Side effects:** Version `review → draft`; lưu `reject_reason` (cột version + audit detail); `audit_logs` action=`DOCUMENT_VERSION_REJECT` (reason) + `DOCUMENT_VERSION_STATE_CHANGE`; `notifications` cho người soạn (kèm lý do, idempotent — BR-DOC-018).

---

### 15. GET /api/v1/documents/:id/versions/:vid/download
**Mục đích:** Tải file của version (trả presigned URL MinIO TTL 15p). Mặc định chỉ tải được `approved`; `draft`/`review` chỉ người soạn/duyệt phòng đó/admin/leader; `obsolete` tải kèm cảnh báo cho người có quyền xem lịch sử (OQ#4 default). Ghi `document_access_log` action=`download` (FR-012, R15).
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc, theo trạng thái + mức bảo mật) | **Scope:** đọc | **Rate limit:** 60/min

**Response 200:**
```json
{
  "success": true,
  "data": {
    "version_id": "ver2-uuid",
    "version_no": 2,
    "status": "approved",
    "is_obsolete": false,
    "obsolete_warning": null,
    "filename": "sop-do-ph-v2.pdf",
    "mime": "application/pdf",
    "size": 351002,
    "download_url": "https://minio.lims.internal/lims/documents/...?X-Amz-Expires=900&...",
    "url_expires_at": "2026-06-20T08:45:00Z"
  }
}
```
> Tải version `obsolete` (người có quyền xem lịch sử): `is_obsolete=true`, `obsolete_warning="Tài liệu lỗi thời — KHÔNG SỬ DỤNG"` (BR-DOC-022). Nếu KH chốt chặn tải obsolete → trả 403 `OBSOLETE_DOWNLOAD_FORBIDDEN` (OQ#4 biến thể).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VERSION_NOT_PUBLISHED | 403 | Tải version `draft`/`review` mà không phải người soạn/duyệt/admin/leader (BR-DOC-011) |
| RESTRICTED_ACCESS | 403 | Tài liệu `restricted`, user ngoài phòng sở hữu (không admin/leader) (BR-DOC-006) |
| OBSOLETE_DOWNLOAD_FORBIDDEN | 403 | (Nếu KH chốt chặn) tải bản obsolete (OQ#4 biến thể) |
| VERSION_NOT_FOUND | 404 | vid không tồn tại |
| STORAGE_UNAVAILABLE | 503 | MinIO down (FR-012 A4) — log ERROR, không lộ stack |

**Side effects:** `document_access_log` action=`download` (document_id, user_id, version_id, at — BR-DOC-015); `audit_logs` action=`DOCUMENT_DOWNLOAD`. Lượt bị 403 KHÔNG ghi download (BR-DOC-015).

---

### 16. GET /api/v1/documents/:id/history
**Mục đích:** Lịch sử thay đổi đầy đủ (R3, §8.3) — timeline mọi version với ai tạo / khi nào / change_note / ai duyệt / khi nào duyệt / khi nào reject (+lý do) / khi nào obsolete; dựng từ `document_versions` + `audit_logs`. Lọc theo quyền hiển thị version (FR-016).
**Auth:** Bearer JWT | **Roles:** mọi vai trò (đọc, lọc theo quyền) | **Scope:** đọc | **Rate limit:** 60/min

**Response 200:**
```json
{
  "success": true,
  "data": {
    "document_id": "doc-uuid",
    "document_code": "SOP-HOA-012",
    "timeline": [
      { "version_no": 1, "events": [
        { "action": "DOCUMENT_VERSION_CREATE", "by_name": "Nguyễn Văn A", "at": "2026-03-01T02:00:00Z", "detail": null },
        { "action": "DOCUMENT_VERSION_SUBMIT", "by_name": "Nguyễn Văn A", "at": "2026-03-02T02:00:00Z" },
        { "action": "DOCUMENT_VERSION_APPROVE", "by_name": "Trưởng nhóm T", "at": "2026-03-03T03:00:00Z" },
        { "action": "DOCUMENT_VERSION_OBSOLETE", "by_name": "hệ thống", "at": "2026-06-10T03:00:00Z", "detail": "thay bởi v2" }
      ] },
      { "version_no": 2, "events": [
        { "action": "DOCUMENT_VERSION_CREATE", "by_name": "Nguyễn Văn A", "at": "2026-06-05T02:00:00Z", "detail": "change_note: Cập nhật ngưỡng hiệu chuẩn máy" },
        { "action": "DOCUMENT_VERSION_REJECT", "by_name": "Trưởng nhóm T", "at": "2026-06-07T02:00:00Z", "detail": "reason: Thiếu mục an toàn" },
        { "action": "DOCUMENT_VERSION_SUBMIT", "by_name": "Nguyễn Văn A", "at": "2026-06-09T02:00:00Z" },
        { "action": "DOCUMENT_VERSION_APPROVE", "by_name": "Trưởng nhóm T", "at": "2026-06-10T03:00:00Z" }
      ] }
    ]
  }
}
```
> Staff phòng khác / Kế toán: timeline ẩn version `draft`/`review` (chỉ approved/obsolete) — BR-DOC-011. Mỗi mốc khớp 1 bản ghi `audit_logs` (truy vết §8.3 — FR-016 AC3).

**Errors:** `DOCUMENT_NOT_FOUND` (404), `RESTRICTED_ACCESS` (403), `UNAUTHORIZED` (401).

---

### 17. GET /api/v1/documents/pending-review
**Mục đích:** Danh sách version `review` đang **chờ tôi duyệt** (trong phòng tôi phụ trách) — FR-009, hỗ trợ trưởng nhóm. Đồng bộ pattern M1 "version chờ duyệt của tôi".
**Auth:** Bearer JWT | **Roles:** **trưởng nhóm phòng** (`is_dept_lead`), leader, admin | **Scope:** đọc theo phòng | **Rate limit:** 60/min

**Query params:** `department_id` (optional — leader/admin lọc phòng), `page/limit`.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "document_id": "doc-uuid", "document_code": "SOP-HOA-012", "title": "SOP đo pH",
      "department_name": "Hóa lý",
      "version_id": "ver3-uuid", "version_no": 3, "status": "review",
      "change_note": "Bổ sung mục an toàn hóa chất",
      "created_by_name": "Nguyễn Văn A", "submitted_at": "2026-06-20T02:00:00Z",
      "can_approve": true
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 1, "hasNext": false }
}
```
> `can_approve=false` nếu version do chính user soạn (sẽ bị `SELF_APPROVAL_FORBIDDEN` khi approve — FE disable nút). Trưởng nhóm chỉ thấy version `review` của phòng mình; leader/admin thấy mọi phòng.

**Errors:** `FORBIDDEN` (403 — staff thường không phải trưởng nhóm; accountant), `UNAUTHORIZED` (401).

---

### 18. GET /api/v1/documents/:id/access-stats
**Mục đích:** Thống kê lượt **view / download / edit** của MỘT tài liệu theo khoảng thời gian (R15) — FR-015.
**Auth:** Bearer JWT | **Roles:** admin, leader (toàn HT), staff (tài liệu phòng mình — OQ#3 default) | **Scope:** đọc theo phạm vi | **Rate limit:** 60/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| from | date | ❌ | ≤ to | Từ ngày (default: 30 ngày trước) |
| to | date | ❌ | — | Đến ngày (default: hôm nay) |
| group_by | enum | ❌ | day\|week\|month (default tổng) | Nhóm theo thời gian (optional cho biểu đồ) |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "document_id": "doc-uuid",
    "document_code": "SOP-HOA-012",
    "range": { "from": "2026-06-01", "to": "2026-06-20" },
    "totals": { "view": 30, "download": 12, "edit": 3 },
    "series": [
      { "period": "2026-06-01", "view": 5, "download": 2, "edit": 1 },
      { "period": "2026-06-02", "view": 8, "download": 3, "edit": 0 }
    ]
  }
}
```
> `series` chỉ trả khi có `group_by`. Dữ liệu từ `document_access_log` GROUP BY action (BR-DOC-015), KHÔNG từ `audit_logs`.

**Errors:** `DOCUMENT_NOT_FOUND` (404), `FORBIDDEN` (403 — staff xem thống kê tài liệu ngoài phòng; accountant), `VALIDATION_ERROR` (400 — from>to), `UNAUTHORIZED` (401).

---

### 19. GET /api/v1/documents/access-stats
**Mục đích:** Thống kê tổng hợp truy cập tài liệu toàn hệ thống + **top N** (R15) — FR-015. Cung cấp số liệu cho M6.3.
**Auth:** Bearer JWT | **Roles:** admin, leader (toàn HT), staff (phòng mình — OQ#3 default) | **Scope:** đọc theo phạm vi | **Rate limit:** 60/min

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| from | date | ❌ | ≤ to | Từ ngày (default 30 ngày trước) |
| to | date | ❌ | — | Đến ngày |
| department_id | uuid | ❌ | tồn tại | Lọc phòng ban (staff ép = phòng mình) |
| action | enum | ❌ | view\|download\|edit | Lọc loại hành động |
| top | int | ❌ | 1..100 (default 10) | Top N tài liệu được truy cập/tải nhiều nhất |
| sort_by | enum | ❌ | view\|download\|edit\|total (default download) | Tiêu chí xếp hạng top N |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "range": { "from": "2026-05-21", "to": "2026-06-20" },
    "summary": { "total_view": 1240, "total_download": 412, "total_edit": 58, "document_count": 50 },
    "top_documents": [
      { "document_id": "doc-uuid", "document_code": "SOP-HOA-012", "title": "SOP đo pH",
        "department_name": "Hóa lý", "view": 30, "download": 12, "edit": 3, "total": 45 }
    ]
  }
}
```

**Errors:** `FORBIDDEN` (403 — accountant; staff vượt phạm vi phòng), `VALIDATION_ERROR` (400 — from>to / top ngoài 1..100), `UNAUTHORIZED` (401).

---

### 20. GET /api/v1/documents/access-stats/export
**Mục đích:** Xuất Excel/PDF báo cáo thống kê truy cập (đồng bộ M6.4) — FR-015. Endpoint nặng (sync).
**Auth:** Bearer JWT | **Roles:** admin, leader | **Scope:** đọc theo phạm vi | **Rate limit:** 10/min

**Query params:** giống #19 + `format` (enum `xlsx|pdf`, default `xlsx`).

**Response 200:** file binary (`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` hoặc `application/pdf`), `Content-Disposition: attachment; filename="document-access-stats-2026-06.xlsx"`.

**Errors:** `FORBIDDEN` (403 — staff/accountant), `VALIDATION_ERROR` (400 — format/range sai), `UNAUTHORIZED` (401).

**Side effects:** `audit_logs` action=`DOCUMENT_STATS_EXPORT`.

---

## 3. Danh mục Error Codes M3

Nhất quán với M1/M7 (SNAKE_CASE, không lộ stack trace, kèm `correlationId`).

| Code | HTTP | Ý nghĩa / điều kiện | Endpoint |
|------|------|---------------------|----------|
| `VALIDATION_ERROR` | 400 | Input sai/thiếu (thiếu title/type/file, filter sai enum, body rỗng) | #3,4,6,11,18,19,20 |
| `CHANGE_NOTE_REQUIRED` | 400 | Thiếu `change_note` ở version ≥ 2 (BR-DOC-016) | #9 |
| `REJECT_REASON_REQUIRED` | 400 | Thiếu `reject_reason` khi từ chối (BR-DOC-020) | #14 |
| `UNAUTHORIZED` | 401 | Thiếu/sai JWT | tất cả |
| `FORBIDDEN` | 403 | Sai phạm vi phòng (staff ghi chéo phòng — BR-DOC-004); **accountant gọi endpoint ghi** (BR-DOC-005); staff thường gọi approve/reject (BR-DOC-010) | #4,6,7,9,11,12,13,14,17,18,19,20 |
| `SELF_APPROVAL_FORBIDDEN` | 403 | Người duyệt = người soạn version — tách trách nhiệm §8.3.2 (BR-DOC-009) | #13 |
| `VERSION_NOT_PUBLISHED` | 403 | Xem/tải version `draft`/`review` không có quyền (BR-DOC-011) | #10,15 |
| `RESTRICTED_ACCESS` | 403 | Tài liệu `restricted`, user ngoài phòng sở hữu (BR-DOC-006) | #5,10,15,16 |
| `OBSOLETE_DOWNLOAD_FORBIDDEN` | 403 | (Biến thể OQ#4) chặn tải bản obsolete | #15 |
| `DOCUMENT_NOT_FOUND` | 404 | document id không tồn tại HOẶC ẩn (restricted/chưa current ngoài quyền) | #5,6,7,8,9,16,18 |
| `VERSION_NOT_FOUND` | 404 | version id không tồn tại | #10,11,12,13,14,15 |
| `DEPARTMENT_NOT_FOUND` | 404 | department_id không tồn tại | #4 |
| `DUPLICATE_DOCUMENT_CODE` | 409 | Sinh trùng `document_code` sau N lần retry (FR-003 A1) | #4 |
| `DRAFT_ALREADY_EXISTS` | 409 | Đã có version `draft`/`review` chưa kết thúc (OQ#6 default) | #9 |
| `VERSION_CONFLICT` | 409 | Race: 2 approve song song khác version cùng tài liệu (NFR-CONCUR-DOC-001) | #13 |
| `INVALID_STATE_TRANSITION` | 422 | Chuyển trạng thái version ngoài whitelist (vd draft→approved, obsolete→*, approved→draft) (BR-DOC-007) | #12,13,14 |
| `VERSION_LOCKED` | 422 | Sửa version không ở `draft` (review/approved/obsolete bất biến) (BR-DOC-012) | #11 |
| `VERSION_FILE_REQUIRED` | 422 | Gửi duyệt version chưa có file (BR-DOC-017) | #12 |
| `CODE_IMMUTABLE` | 422 | Cố đổi `document_code` (BR-DOC-014) | #6 |
| `DOCUMENT_HAS_APPROVED_VERSION` | 422 | Xóa tài liệu đã có version approved/obsolete (BR-DOC-021) | #7 |
| `INVALID_DOC_TYPE` | 422 | `type` ngoài danh mục (BR-DOC-002) | #4,6 |
| `INVALID_CONFIDENTIALITY` | 422 | `security_level` ngoài danh mục (BR-DOC-003) | #4,6 |
| `INVALID_FILE_TYPE` | 422 | File ngoài whitelist MIME (BR-DOC-013) | #4,9,11 |
| `FILE_TOO_LARGE` | 422 | File > 20MB (BR-DOC-013) | #4,9,11 |
| `RATE_LIMIT_EXCEEDED` | 429 | Vượt rate limit (§0.5) | tất cả |
| `STORAGE_UNAVAILABLE` | 503 | MinIO down khi tải/upload (FR-012 A4) | #4,9,11,15 |
| `INTERNAL_ERROR` | 500 | Lỗi server không xử lý được — chỉ trả code + correlationId (rule logging.md) | tất cả |

**Ví dụ error `SELF_APPROVAL_FORBIDDEN` (#13):**
```json
{
  "success": false,
  "error": {
    "code": "SELF_APPROVAL_FORBIDDEN",
    "message": "Người duyệt phải khác người soạn phiên bản (tách trách nhiệm theo ISO/IEC 17025 §8.3.2).",
    "details": [{ "field": "approved_by", "created_by": "userA-uuid" }],
    "correlationId": "c1f2-8a90-..."
  }
}
```

**Ví dụ error `INVALID_STATE_TRANSITION` (#13 — duyệt thẳng từ draft):**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_STATE_TRANSITION",
    "message": "Không thể duyệt phiên bản đang ở trạng thái 'draft'. Phải gửi duyệt (draft → review) trước.",
    "details": [{ "field": "status", "from": "draft", "attempted": "approved", "allowed_from": ["review"] }],
    "correlationId": "c1f2-8a90-..."
  }
}
```

---

## 4. Ghi chú RBAC (tổng hợp — đọc kèm §0.6–0.8)

### 4.1 Hai mức bảo mật (`security_level`) — enforce thế nào
- `internal`: mọi vai trò (gồm Kế toán) đọc/tải **version approved**. `draft`/`review` vẫn chỉ người soạn/duyệt phòng đó/admin/leader.
- `restricted`: chỉ user thuộc **phòng sở hữu** (`documents.department_id == user.dept`) + admin + leader. Enforce **3 lớp**: list (#3 — ẩn), get/history (#5/#16 — `DOCUMENT_NOT_FOUND` ẩn sự tồn tại hoặc `RESTRICTED_ACCESS`), download (#15 — `RESTRICTED_ACCESS`). Backend áp filter ở tầng query + tầng service; không tin FE.
- Quyết định ẩn (404) vs từ chối (403): **list ẩn** hoàn toàn; **truy cập trực tiếp** dùng `DOCUMENT_NOT_FOUND` (404) để không tiết lộ sự tồn tại của tài liệu restricted (chống enumeration), hoặc `RESTRICTED_ACCESS` (403) khi đã biết tài liệu tồn tại (vd qua link cũ). Implement nhất quán theo schema-designer chốt.

### 4.2 Tách soạn–duyệt (§8.3.2 — BR-DOC-009)
- `approve` (#13): backend kiểm `version.created_by != current_user.id` → vi phạm 403 `SELF_APPROVAL_FORBIDDEN` (kể cả trưởng nhóm tự soạn). Nếu người soạn LÀ trưởng nhóm duy nhất → cần người duyệt khác (leader/admin) — OQ#6.
- Quyền `document:approve` = **trưởng nhóm phòng đó** (`is_dept_lead && version.document.department_id == user.dept`) HOẶC leader HOẶC admin. Staff thường → 403 `FORBIDDEN`.
- `#17 pending-review` trả `can_approve=false` cho version user tự soạn → FE disable nút duyệt (UX), backend vẫn re-check (defense in depth).

### 4.3 Kế toán (accountant) — chỉ xem
- Đọc được: #1,2 (danh mục), #3,5,8,10,15,16 (CHỈ version `approved`/current; ẩn `draft`/`review`/`obsolete`).
- Bị 403 trên: #4,6,7,9,11,12,13,14 (mọi ghi) + #17,18,19,20 (pending-review + thống kê — nghiệp vụ quản lý). Chặn ở **tầng API** (BR-DOC-005).

### 4.4 Khi nào ghi `document_access_log` (R15 — BR-DOC-015)
- `view`: khi mở **chi tiết tài liệu** (#5) hoặc history (#16, optional). KHÔNG ghi cho từng dòng list (#3).
- `download`: khi tải file version thành công (#15) — lượt bị 403 KHÔNG đếm.
- `edit`: khi tạo/sửa version (#4 v1, #9, #11).
- Ghi **best-effort** (async/fire-and-forget được phép): lỗi ghi access_log KHÔNG rollback nghiệp vụ, chỉ log WARN. Tách high-volume khỏi `audit_logs` (pháp lý §8.4) và `access_stats` (M7).

---

## 5. Ghi chú phi chức năng

- **Pagination:** mọi list (#3,8,17,19 top) dùng offset-based, default 20 / max 100, `meta` đủ `page/limit/total/hasNext` (§0.4). Thống kê (#18,19) không phân trang theo dòng log (aggregate sẵn) trừ `top_documents` (giới hạn `top` ≤ 100).
- **CorrelationId & Audit:** mọi request kèm/sinh `X-Correlation-Id`; mọi thao tác ghi (tạo/sửa/submit/approve/reject/obsolete/download/export/delete) ghi `audit_logs` (user, action, resource, resource_id, correlation_id, ip, at, detail before/after khi sửa) — VILAS §8.3/§8.4 (BR-DOC-019). Audit append-only, không endpoint sửa/xóa.
- **State machine:** chuyển trạng thái chỉ qua endpoint hành động #12/#13/#14, đi qua **hàm transition trung tâm** kiểm `(from,to) ∈ whitelist` + quyền + tách soạn–duyệt + ghi `DOCUMENT_VERSION_STATE_CHANGE` (FR-013). Không expose PATCH status tùy ý.
- **Transaction & concurrency:** `approve` (#13) chạy trong 1 transaction với **row-lock trên document** (`SELECT ... FOR UPDATE`) để đảm bảo nguyên tử: approve version mới + obsolete bản cũ + set `current_version_id` → đúng 1 current (BR-DOC-008). Race 2 approve → 1 thắng, bên kia `VERSION_CONFLICT` 409 (NFR-CONCUR-DOC-001).
- **Validation:** sanitize input tầng API (class-validator/pydantic); validate enum (type/security_level/action), độ dài chuỗi, MIME thực + đuôi file (không tin Content-Type client), size ≤ 20MB (BR-DOC-013).
- **Upload MinIO:** multipart → backend đẩy MinIO (C01) → lưu `file_key` trong `attachments` (`owner_type='document_version'`); KHÔNG lưu binary DB. Tải = presigned URL TTL 15p (không proxy binary). Upload thất bại trong tạo tài liệu (#4) → rollback toàn transaction (không để tài liệu rỗng).
- **Performance (NFR-PERF-DOC):** ghi/duyệt version P95 < 400ms (không tính upload); list/search P95 < 500ms với 5,000 tài liệu / 20,000 version; thống kê (#18,19) dựa index `document_access_log(document_id, action, at)` để chịu ~500,000 dòng (R15 high-volume).
- **Bảo mật:** không trả stack trace ra client (500 → `INTERNAL_ERROR` + correlationId); không log file binary; presigned URL có TTL ngắn; restricted filter ở tầng query.

---

## 6. Traceability — Endpoint → FR SRS M3

| Endpoint | FR | BR chính |
|----------|-----|----------|
| #1 GET /document-types | FR-DOC-002 | BR-DOC-002 |
| #2 GET /confidentiality-levels | FR-DOC-003 | BR-DOC-003 |
| #3 GET /documents | FR-DOC-004 | BR-DOC-006, 011, 015 |
| #4 POST /documents (+v1 upload) | FR-DOC-001, 003, 006 | BR-DOC-001, 004, 013, 014, 016 |
| #5 GET /documents/:id | FR-DOC-005 | BR-DOC-006, 011, 015 |
| #6 PATCH /documents/:id | FR-DOC-002 | BR-DOC-004, 014 |
| #7 DELETE /documents/:id | FR-DOC-002 | BR-DOC-021 |
| #8 GET /documents/:id/versions | FR-DOC-005 | BR-DOC-001, 011 |
| #9 POST /documents/:id/versions | FR-DOC-006 | BR-DOC-001, 012, 013, 016 |
| #10 GET /documents/:id/versions/:vid | FR-DOC-005 | BR-DOC-011 |
| #11 PATCH /documents/:id/versions/:vid | FR-DOC-007 | BR-DOC-012, 013 |
| #12 POST .../submit-review | FR-DOC-008, 013 | BR-DOC-007, 012, 017, 018 |
| #13 POST .../approve | FR-DOC-009, 011, 013 | BR-DOC-007, 008, 009, 010, 019 |
| #14 POST .../reject | FR-DOC-010, 013 | BR-DOC-007, 010, 020 |
| #15 GET .../download | FR-DOC-012, 014 | BR-DOC-006, 011, 015, 022 |
| #16 GET /documents/:id/history | FR-DOC-016 | BR-DOC-011, 019 |
| #17 GET /documents/pending-review | FR-DOC-009 | BR-DOC-009, 010 |
| #18 GET /documents/:id/access-stats | FR-DOC-014, 015 | BR-DOC-015 |
| #19 GET /documents/access-stats | FR-DOC-015 | BR-DOC-015, 005 |
| #20 GET /documents/access-stats/export | FR-DOC-015 | BR-DOC-015 |
| (nội bộ) state machine transition | FR-DOC-013 | BR-DOC-007, 008, 009 |
| (nội bộ) ghi access_log | FR-DOC-014 | BR-DOC-015 |
| (nội bộ) auto-obsolete trong approve | FR-DOC-011 | BR-DOC-008 |

> **Phủ 16/16 FR SRS M3.** FR-013 (state machine), FR-011 (auto-obsolete), FR-014 (ghi access_log) là hành vi nội bộ trong các endpoint hành động (#12/#13/#14/#15), không phải endpoint riêng — đúng tinh thần SRS ("API cần: nội bộ").
