# API Contract: M6 — Báo cáo & Thống kê (Reporting & Analytics)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M6 — Reporting & Analytics — **module CUỐI, tầng TỔNG HỢP CHÉO (READ-ONLY aggregate)**
**Version:** 1.0 | **Ngày:** 20/06/2026 | **Designer:** api-designer agent
**Nguồn chân lý:** `19-srs-m6-reporting.md` (11 FR, 14 BR, 5 UC, 10 NFR, §9.2 "M6 tổng hợp gì từ đâu")
**Đồng bộ phong cách:** `18-contract-m5-api.md` + `15-contract-m3-api.md` (prefix `/api/v1`, response `{success,data,meta}`/`{success:false,error:{code,message,details,correlationId}}`, UUID, pagination 20/100, correlationId, xuất Excel binary `Content-Disposition`, rate limit theo nhóm)
**Stack:** FastAPI + PostgreSQL + Redis + MinIO + APScheduler (monolith, ~40 user). Backend đã có **M7 + M1 + M2 + M4 + M3 + M5** (132 endpoint hiện hữu).

> **M6 KHÔNG sở hữu bảng nghiệp vụ riêng.** Đọc/tổng hợp từ M1 (`samples`), M2 (`chemical_lots`/`chemicals`/`chemical_transactions`), M3 (`document_versions`/`document_access_log`), M4 (`hr_profiles`), M5 (`equipments`), M7 (`audit_logs`/`access_stats`/`notifications`/`departments`/`users`/`roles_permissions`). **Ngoại lệ READ-ONLY duy nhất:** (a) middleware GHI `access_stats` (FR-RPT-009); (b) ghi `audit_logs` action `REPORT_EXPORT` khi xuất báo cáo (FR-RPT-010/011). **KHÔNG định nghĩa lại** các endpoint thống kê đơn-module đã có (CONSTRAINT-1 — §0.10).

---

## 0. Quy ước chung (đọc trước)

### 0.1 Base & versioning
- Prefix: `/api/v1`. M6 dùng **resource theo nhóm chức năng**: `/dashboard`, `/reports/*`, `/analytics/*` (KHÔNG phải CRUD resource số nhiều như module khác vì M6 là tầng tổng hợp READ-ONLY).
- Nested tối đa 2 cấp: `/reports/system-access/users/:userId`.
- ID trong URL là **UUID** (`userId`, `department_id`) — KHÔNG lộ ID tuần tự (rule api.md).
- Không breaking change trong cùng `v1`; deprecated báo trước ≥ 1 sprint + header `Deprecation: true`.

### 0.2 Response format chuẩn (đồng bộ M3/M5)
```jsonc
// Success — single / aggregate
{ "success": true, "data": { /* object */ }, "meta": { /* optional */ } }

// Success — list (pagination)
{ "success": true, "data": [ /* items */ ],
  "meta": { "page": 1, "limit": 20, "total": 137, "hasNext": true } }

// Error
{ "success": false,
  "error": {
    "code": "SNAKE_CASE_CODE",
    "message": "Thông điệp cho người dùng/dev (KHÔNG chứa stack trace)",
    "details": [ { "field": "from", "message": "from phải nhỏ hơn to" } ],
    "correlationId": "c1f2..."   // luôn trả để user report support (rule logging.md)
  } }
```

### 0.3 Auth & headers
- **Mọi endpoint M6** yêu cầu `Authorization: Bearer <JWT>` (M7). Không có endpoint public.
  - **Ngoại lệ:** `POST /analytics/page-view` chấp nhận user đã đăng nhập (mọi vai trò); request chưa đăng nhập (login page) được middleware ghi `user_id = NULL` (xem §0.9, FR-RPT-009).
- **`X-Correlation-Id`** (UUID): client gửi; nếu thiếu, server tự sinh và **trả lại** trong response header. Với thao tác **xuất báo cáo**, correlation_id được ghi vào `audit_logs.correlation_id` (truy vết §8.4 — BR-RPT-012). Mọi request M6 có correlation_id để trace FE → BE → DB (NFR-OBS-RPT-001).
- 401 `UNAUTHORIZED` nếu thiếu/sai token; 403 `FORBIDDEN` nếu thiếu quyền / sai phạm vi phòng ban / sai cách ly tài chính-nghiệp vụ.
- RBAC middleware đọc `role` + `dept` (department_id) từ JWT claims (M7) để enforce quyền + scope mà không query DB mỗi request.
- `Content-Type: application/json` cho request; response xuất file là binary (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` / `application/pdf`) + `Content-Disposition: attachment`.

### 0.4 Pagination
- Endpoint list (thống kê theo user #11, top N khi `limit` lớn): `page` (default 1), `limit` (default **20**, max **100** — vượt ép về 100). **Offset-based** (~40 user). `meta` luôn có `page`, `limit`, `total`, `hasNext`.
- Endpoint **aggregate KPI/chart/summary** (#1–#6) KHÔNG phân trang — trả 1 gói số liệu; `meta` chứa `generated_at` + `cached` (xem §0.8).

### 0.5 Rate limit
- Mặc định **60 req/phút/user** cho dashboard + chart + thống kê (đọc, có cache).
- **Thống kê truy cập hệ thống R15** (#10, #11) + **xuất báo cáo** (#12, #13): **10 req/phút/user** (query nặng audit/access_stats + sinh file). Vượt → **429** `RATE_LIMIT_EXCEEDED`.
- `POST /analytics/page-view` (#14): **120 req/phút/user** (sự kiện nhẹ, gọi mỗi lần vào trang).

### 0.6 Bộ lọc thời gian thống nhất (BR-RPT-009, FR-RPT-005, CONSTRAINT-5)

Tập query params **dùng chung** cho mọi báo cáo M6. Quy ước nhất quán toàn module:

| Param | Type | Default | Validation | Mô tả |
|-------|------|---------|-----------|-------|
| `from` | date (ISO `YYYY-MM-DD`) | đầu tháng hiện tại | ISO date | Mốc đầu khoảng — **bao gồm** (≥ from). Múi giờ hệ thống (Asia/Ho_Chi_Minh). |
| `to` | date (ISO `YYYY-MM-DD`) | đầu tháng kế tiếp | ISO date; `from < to` | Mốc cuối khoảng — **loại trừ** (< to). Khoảng **nửa mở `[from, to)`**. |
| `department_id` | uuid | — (toàn hệ thống) | tồn tại; trong scope vai trò | Lọc phòng ban. **Staff** truyền phòng khác → **ép về phòng mình** (KHÔNG 403 — BR-RPT-001). |
| `group_by` | enum | `month` | `day` \| `week` \| `month` | Đơn vị phân rã trục thời gian (chart/line). Khác → 422 `INVALID_GROUP_BY`. |
| `type` | string/enum | — | tùy báo cáo | Loại mẫu / nhóm đo hóa chất / loại hành động — ý nghĩa theo từng endpoint. |

- **Quy ước biên (off-by-one):** bản ghi đúng `00:00 from` được TÍNH; bản ghi đúng `00:00 to` bị LOẠI (NFR-CONSISTENCY-RPT-001).
- **Bộ lọc rỗng** → mặc định kỳ = **tháng hiện tại** (`[đầu tháng, đầu tháng kế tiếp)`) (OQ#9 default).
- `from >= to` → **422 `INVALID_DATE_RANGE`** ở MỌI endpoint dùng bộ lọc.

### 0.7 RBAC tổng quát M6 (BR-RPT-001/002/010, NFR-SEC-RPT-001, §2.3 SRS)

**4 vai trò** (M7): `admin`, `leader` (Ban lãnh đạo), `accountant` (Kế toán), `staff` (Nhân sự/KTV). M6 enforce scope ở **TẦNG API** (không chỉ FE — CONSTRAINT-3, OWASP A01).

| Khía cạnh | admin | leader | accountant | staff |
|-----------|-------|--------|-----------|-------|
| **Phạm vi dữ liệu** | Toàn hệ thống | Toàn hệ thống | Toàn hệ thống (chỉ phần tài chính) | **Chỉ phòng mình** (ép scope) |
| **KPI/báo cáo mẫu & kết quả** (M1) | ✅ | ✅ | ❌ **403 / lọc khỏi response** (B03) | ✅ 👁 (phòng mình) |
| **KPI/báo cáo hóa chất nghiệp vụ** (M2) | ✅ | ✅ | ✅ 👁 (có field tiền) | ✅ 👁 (KHÔNG field tiền) |
| **Field tiền** (giá/giá trị hóa chất, lương) | ✅ | ✅ | ✅ (`chemical:cost`) | ❌ **strip ở serializer** |
| **KPI nhân sự** (nâng lương/HĐ — M4) | ✅ | ✅ | ✅ | ❌ không trả |
| **Thống kê truy cập hệ thống R15** (#10, #11) | ✅ | ✅ | ❌ **403** | ❌ **403** |
| **Xuất báo cáo** (#12, #13) | ✅ mọi báo cáo | ✅ mọi báo cáo | ✅ chỉ báo cáo tài chính/hóa chất | ✅ chỉ phòng mình + không tiền |

- **Quyền M7 sử dụng:** `report:business` (admin/leader scope all; staff scope department; accountant: app lọc resource — chỉ hóa chất, KHÔNG mẫu), `report:finance` (admin/leader/accountant scope all; staff KHÔNG), **`audit:read`** (chỉ admin/leader — dùng cho thống kê truy cập hệ thống R15, đồng bộ matrix "Audit log: Admin ✅ / Lãnh đạo ✅ / Kế toán — / KTV —"). Các quyền này đã seed ở M7 (`08-contract-m7-schema`).
- **Đặc thù B03 (cách ly nghiệp vụ–tài chính):** accountant **KHÔNG nhận KPI/báo cáo mẫu/kết quả** — backend phải LỌC khỏi response (response shape của accountant **không chứa** khối `samples`), KHÔNG chỉ ẩn ở FE.
- **Ép scope staff:** staff truyền `department_id` khác phòng mình → backend **âm thầm ép về phòng mình** (không 403) — đồng bộ AC4 FR-RPT-005.

### 0.8 Cache dashboard (Redis — BR-RPT-011, NFR-PERF-RPT-001)
- Endpoint dashboard/chart/summary cache ở Redis. **TTL mặc định 60s** (OQ#2 default 60–300s; chốt 60s cho dashboard quản lý — số liệu trễ tối đa 60s, chấp nhận được).
- **Cache key** = `(endpoint, role, department_scope, from, to, group_by, type)` — KHÔNG dùng chung cache giữa các vai trò (tránh rò rỉ scope).
- `meta` của response aggregate luôn kèm:
  ```jsonc
  "meta": { "generated_at": "2026-06-20T08:00:00Z", "cached": true, "cache_ttl_seconds": 60 }
  ```
- Invalidate theo TTL (không realtime). Snapshot KPI lịch sử theo ngày = OUT-OF-SCOPE/CR (ASSUMPTION-2, OQ#4).

### 0.9 Middleware ghi access_stats (FR-RPT-009, hạ tầng M6.3)
- **Middleware** (KHÔNG phải endpoint nghiệp vụ) ghi tự động vào `access_stats`(`user_id`, `path`, `method`, `status_code`, `ip`, `at`) cho **whitelist trang chính** (default: `GET` các trang chính của ứng dụng + login — OQ#1). KHÔNG ghi static/asset/health-check (BR-RPT-005).
- Ghi **không chặn request** (background/non-blocking) — overhead < 5ms/request, lỗi ghi → log WARN, KHÔNG fail request chính (NFR-PERF-RPT-003, BR-RPT-013).
- **Lọc sensitive:** query string chứa `token`/`secret`/`password` được strip khỏi `path` trước khi ghi (logging.md).
- FE SPA gọi `POST /analytics/page-view` (#14) để ghi "xem trang chính" cho điều hướng client-side (vì middleware HTTP chỉ thấy 1 request load đầu) — đây là **bổ sung** cho middleware, không thay thế.

### 0.10 Ranh giới CHỐNG TRÙNG (CONSTRAINT-1) — endpoint ĐÃ CÓ, M6 KHÔNG làm lại

| Số liệu | Endpoint ĐÃ CÓ (module khác) | M6 làm gì khác |
|---------|------------------------------|----------------|
| On-time rate mẫu | `GET /reports/sample-on-time` (M1) | M6 chỉ **ĐẾM** số mẫu theo trạng thái/kỳ/phòng (#3) — KHÔNG tính lại on-time rate |
| Hóa chất tồn thấp | `GET /inventory/low-stock` (M2) | M6 chỉ **ĐẾM** số hóa chất tồn thấp làm KPI (#1) |
| Tiêu hao chi tiết | `GET /reports/consumption` (M2) | M6 cung cấp **bộ lọc thống nhất** + tách nhóm đo cho dashboard (#4) |
| Xuất nhật ký GD hóa chất | `GET /exports/transactions.xlsx` (M2) | M6 xuất **báo cáo tổng hợp** (#12), không phải nhật ký giao dịch |
| Thống kê view/download per-tài-liệu | `GET /documents/access-stats` + `/:id/access-stats` + `/access-stats/export` (M3) | M6 đếm `download` cho **lượt tải HỆ THỐNG R15** (#10) — cấp hệ thống, KHÁC per-tài-liệu |
| Thống kê thành tích NCKH | `GET /research-achievements/stats` (M4) | M6 chỉ **ĐẾM** KPI nâng lương/HĐ (#6, gộp dashboard) |

> **Nguyên tắc:** nếu KH cần báo cáo chi tiết hơn báo cáo module hiện có → CR ở **module tương ứng**, KHÔNG phải M6 (CONSTRAINT-1, §9.2 SRS).

---

## 1. Bảng tổng hợp Endpoint

| # | Method | Path | Mô tả | Vai trò | Scope | Tổng hợp từ | FR |
|---|--------|------|-------|---------|-------|-------------|-----|
| **M6.1 Dashboard tổng hợp** ||||||||
| 1 | GET | `/api/v1/dashboard` | Gói KPI tổng hợp chéo module (1 lần gọi), scope theo vai trò, cache 60s | admin, leader, accountant, staff | Theo vai trò | M1,M2,M3,M4,M5,M7 | FR-RPT-001/006 |
| 2 | GET | `/api/v1/dashboard/charts` | Dữ liệu biểu đồ: mẫu theo trạng thái (pie), mẫu theo thời gian (line), tiêu hao hóa chất theo tháng (bar) | admin, leader, accountant(chỉ hóa chất), staff | Theo vai trò | M1, M2 | FR-RPT-002 |
| **M6.2 Bộ lọc + thống kê theo thời gian** ||||||||
| 3 | GET | `/api/v1/reports/samples` | Thống kê **đếm** số mẫu theo bộ lọc (thời gian/phòng/trạng thái/loại) + phân rã | admin, leader, staff(phòng) | Theo vai trò | M1 (`samples`) | FR-RPT-003/005 |
| 4 | GET | `/api/v1/reports/chemicals` | Thống kê **tiêu hao/tồn** hóa chất theo bộ lọc, tách nhóm đo; field tiền theo vai trò | admin, leader, accountant, staff(phòng, không tiền) | Theo vai trò | M2 | FR-RPT-004/005 |
| **M6.3 Thống kê truy cập hệ thống (R15)** ||||||||
| 10 | GET | `/api/v1/reports/system-access` | Lượt truy cập + tải + chỉnh sửa toàn HT, theo thời gian + top N user | **admin, leader CHỈ** | Toàn HT | M7 (`access_stats`,`audit_logs`) + M3 (`document_access_log`) | FR-RPT-007 |
| 11 | GET | `/api/v1/reports/system-access/users/:userId` | Chi tiết hoạt động 1 user (truy cập/tải/chỉnh sửa + timeline) | **admin, leader CHỈ** | Toàn HT | như #10 lọc user | FR-RPT-008 |
| **M6.4 Xuất báo cáo** ||||||||
| 12 | GET | `/api/v1/reports/:reportType/export.xlsx` | Xuất Excel báo cáo tổng hợp (theo bộ lọc, RBAC scope), ghi audit | Theo báo cáo | Theo vai trò | tùy reportType | FR-RPT-010 |
| 13 | GET | `/api/v1/reports/:reportType/export.pdf` | Xuất PDF báo cáo trình bày (tập con báo cáo), ghi audit | Theo báo cáo | Theo vai trò | tùy reportType | FR-RPT-011 |
| **Hạ tầng access_stats** ||||||||
| 14 | POST | `/api/v1/analytics/page-view` | FE (SPA) ghi 1 lượt xem trang chính (bổ sung middleware) | Mọi vai trò (đã đăng nhập) | — | ghi `access_stats` | FR-RPT-009 |

> **KHÔNG có endpoint riêng cho FR-RPT-006 (KPI nhân sự):** gộp trong `/dashboard` (#1) cho vai trò tài chính/HR (admin/leader/accountant) — staff không nhận.
> **Middleware ghi access_stats (FR-RPT-009)** là hạ tầng — KHÔNG phải endpoint client (§0.9). #14 là bổ sung cho SPA navigation.
> **`reportType`** (#12/#13) ∈ `dashboard` | `samples` | `chemicals` | `system-access` (xem §2 #12). Mỗi reportType áp đúng RBAC + bộ lọc của báo cáo gốc tương ứng.
> **leader đọc R15 được** (khác M5 nơi leader chỉ xem nghiệp vụ): R15 dùng quyền `audit:read` mà admin+leader có. **accountant + staff → 403** ở #10/#11.

---

## 2. Chi tiết Endpoint

---

### 1. GET /api/v1/dashboard
**Mục đích:** Trả **một gói KPI tổng hợp chéo module** (1 round-trip) cho màn dashboard, **đã áp scope theo vai trò** (FR-RPT-001/006). Cache Redis 60s. Mỗi KPI kèm **deep-link** sang module nguồn.
**Auth:** Bearer JWT | **Roles:** admin, leader (toàn HT), accountant (chỉ tài chính), staff (phòng mình) | **Scope:** theo vai trò (§0.7) | **Rate limit:** 60/min | **Cache:** 60s (§0.8)

**Query params:** (tùy chọn — dashboard chủ yếu dùng "now" cho KPI tới-hạn; bộ lọc thời gian áp cho phần đếm theo kỳ nếu có)

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| `department_id` | uuid | ❌ | trong scope; staff ép phòng mình | Giới hạn phòng (admin/leader xem 1 phòng). Bỏ trống = toàn HT (admin/leader) / phòng mình (staff). |
| `due_within_days` | int | ❌ | 1..90 (default 30) | Ngưỡng "sắp tới hạn" cho hóa chất/thiết bị/nhân sự (đồng bộ định nghĩa badge module nguồn). |

**Response 200 — leader/admin (toàn bộ KPI):**
```json
{
  "success": true,
  "data": {
    "scope": { "role": "leader", "department_id": null, "department_name": null },
    "samples": {
      "available": true,
      "by_status": { "received": 12, "assigned": 8, "testing": 15, "done": 120, "returned": 95, "overdue": 10 },
      "total": 165,
      "overdue": 10,
      "deep_link": "/samples?status=overdue"
    },
    "chemicals": {
      "available": true,
      "expiring_soon": 3,
      "recheck_due": 2,
      "low_stock": 5,
      "deep_link_expiring": "/inventory/expiring?within_days=30",
      "deep_link_low_stock": "/inventory/low-stock"
    },
    "equipments": {
      "available": true,
      "calibration_overdue": 2,
      "calibration_due_soon": 4,
      "deep_link": "/equipments/calibration-due"
    },
    "hr": {
      "available": true,
      "salary_raise_due": 3,
      "contract_ending": 2,
      "deep_link": "/hr/profiles?alert=upcoming"
    },
    "documents": {
      "available": true,
      "pending_review": 7,
      "deep_link": "/documents?status=review"
    },
    "notifications": {
      "available": true,
      "unread": 4,
      "deep_link": "/notifications?read=false"
    }
  },
  "meta": { "generated_at": "2026-06-20T08:00:00Z", "cached": false, "cache_ttl_seconds": 60 }
}
```

**Response 200 — accountant (B03: KHÔNG có khối `samples`; CHỈ tài chính):**
```json
{
  "success": true,
  "data": {
    "scope": { "role": "accountant", "department_id": null },
    "chemicals": {
      "available": true,
      "expiring_soon": 3,
      "recheck_due": 2,
      "low_stock": 5,
      "consumption_cost_month": 12500000,
      "deep_link_expiring": "/inventory/expiring?within_days=30"
    },
    "hr": { "available": true, "salary_raise_due": 3, "contract_ending": 2, "deep_link": "/hr/profiles?alert=upcoming" },
    "notifications": { "available": true, "unread": 1 }
  },
  "meta": { "generated_at": "2026-06-20T08:00:00Z", "cached": true, "cache_ttl_seconds": 60 }
}
```
> Response accountant **KHÔNG chứa** `samples`, `documents`, `equipments` nghiệp vụ (B03 — chỉ tài chính). `chemicals` CÓ `consumption_cost_month` (field tiền — vai trò tài chính).

**Response 200 — staff (phòng mình; KHÔNG field tiền; KHÔNG khối `hr`):**
```json
{
  "success": true,
  "data": {
    "scope": { "role": "staff", "department_id": "dept-hoa-uuid", "department_name": "Hóa lý" },
    "samples": { "available": true, "by_status": { "received": 5, "testing": 3, "done": 12, "overdue": 2 }, "total": 22, "overdue": 2, "deep_link": "/samples?status=overdue&department_id=dept-hoa-uuid" },
    "chemicals": { "available": true, "expiring_soon": 1, "low_stock": 2 },
    "equipments": { "available": true, "calibration_overdue": 1, "calibration_due_soon": 0, "deep_link": "/equipments/calibration-due?department_id=dept-hoa-uuid" },
    "documents": { "available": true, "pending_review": 1 },
    "notifications": { "available": true, "unread": 2 }
  },
  "meta": { "generated_at": "2026-06-20T08:00:00Z", "cached": false, "cache_ttl_seconds": 60 }
}
```
> Staff: mọi KPI giới hạn phòng mình; `chemicals` **KHÔNG có** `consumption_cost_month` (strip tiền — BR-RPT-002); **KHÔNG có khối `hr`** (BR-RPT-007).

**Degrade mềm (BR-RPT-013, AC4):** nếu 1 module nguồn lỗi/timeout, khối KPI đó trả `{ "available": false, "error": "Tạm thời không khả dụng" }`, các khối khác vẫn đúng, HTTP vẫn **200**:
```json
"equipments": { "available": false, "error": "Tạm thời không khả dụng" }
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | `due_within_days` ngoài 1..90 |
| DEPARTMENT_NOT_FOUND | 404 | `department_id` không tồn tại |
| UNAUTHORIZED | 401 | Thiếu/sai token |

**Side effects:** chỉ đọc (qua cache). Lượt truy cập trang dashboard ghi `access_stats` qua middleware/#14 (§0.9).

---

### 2. GET /api/v1/dashboard/charts
**Mục đích:** Dữ liệu **biểu đồ** dashboard (FE render — M6 trả số liệu, ASSUMPTION-7): (a) mẫu theo trạng thái (pie); (b) số mẫu theo thời gian (line, `group_by`); (c) tiêu hao hóa chất theo tháng (bar, **tách nhóm đo — KHÔNG cộng gộp**). Áp scope vai trò + bộ lọc thống nhất (§0.6).
**Auth:** Bearer JWT | **Roles:** admin, leader, accountant (chỉ chart hóa chất), staff (phòng) | **Scope:** theo vai trò | **Rate limit:** 60/min | **Cache:** 60s

**Query params:** bộ lọc thống nhất §0.6 (`from`, `to`, `department_id`, `group_by`) +

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| `charts` | csv enum | ❌ | `samples_by_status` \| `samples_over_time` \| `chemical_consumption` (default tất cả theo quyền) | Chọn biểu đồ cần lấy |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "samples_by_status": {
      "available": true,
      "data": [
        { "status": "received", "count": 5 },
        { "status": "testing", "count": 3 },
        { "status": "done", "count": 12 }
      ]
    },
    "samples_over_time": {
      "available": true,
      "group_by": "month",
      "metric": "received_at",
      "data": [
        { "period": "2026-04", "count": 18 },
        { "period": "2026-05", "count": 22 },
        { "period": "2026-06", "count": 14 }
      ]
    },
    "chemical_consumption": {
      "available": true,
      "group_by": "month",
      "by_measurement_group": [
        { "measurement_group": "mass", "base_unit": "g", "data": [ { "period": "2026-05", "qty": 500 } ] },
        { "measurement_group": "volume", "base_unit": "mL", "data": [ { "period": "2026-05", "qty": 2000 } ] }
      ]
    }
  },
  "meta": { "generated_at": "2026-06-20T08:00:00Z", "cached": false, "cache_ttl_seconds": 60, "from": "2026-04-01", "to": "2026-07-01" }
}
```
> `chemical_consumption` **tách theo nhóm đo** (mass/volume/count) + base_unit — KHÔNG cộng g + mL (BR-RPT-014, AC3). Vai trò tài chính có thêm `cost` mỗi điểm: `{ "period": "2026-05", "qty": 500, "cost": 1500000 }`; staff KHÔNG có `cost` (BR-RPT-002). **Accountant** gọi với `charts=samples_by_status` → **403** (B03, AC3 FR-RPT-002): backend bỏ khối mẫu khỏi response hoặc trả 403 nếu chỉ xin chart mẫu.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| INVALID_DATE_RANGE | 422 | `from >= to` (FR-RPT-002 AC4) |
| INVALID_GROUP_BY | 422 | `group_by` ∉ {day, week, month} |
| VALIDATION_ERROR | 400 | `charts` chứa giá trị ngoài enum |
| FORBIDDEN | 403 | accountant xin chart mẫu (B03, BR-RPT-001) |
| DEPARTMENT_NOT_FOUND | 404 | `department_id` không tồn tại |

**Side effects:** chỉ đọc.

---

### 3. GET /api/v1/reports/samples
**Mục đích:** Thống kê **đếm số mẫu** theo bộ lọc đa tiêu chí + thời gian (FR-RPT-003) — tổng + phân rã (theo trạng thái / theo thời gian / theo phòng). **ĐẾM số lượng** — KHÁC `/reports/sample-on-time` của M1 (on-time rate), M6 KHÔNG tính lại on-time (§0.10).
**Auth:** Bearer JWT | **Roles:** admin, leader (mọi phòng), staff (phòng mình) | **Accountant → 403 (B03)** | **Scope:** theo vai trò | **Rate limit:** 60/min | **Cache:** 60s

**Query params:** bộ lọc thống nhất §0.6 +

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| `status` | enum | ❌ | received\|assigned\|testing\|done\|returned\|overdue | Lọc 1 trạng thái (đồng bộ M1) |
| `time_field` | enum | ❌ | `received_at` (default) \| `completed_at` | Trục thời gian áp bộ lọc (OQ#9 default received_at) |
| `breakdown` | enum | ❌ | `status` (default) \| `time` \| `department` | Chiều phân rã trả về |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "filter": { "from": "2026-05-01", "to": "2026-06-01", "department_id": "dept-hoa-uuid", "time_field": "received_at" },
    "total": 20,
    "breakdown_by": "status",
    "by_status": { "received": 0, "assigned": 0, "testing": 5, "done": 8, "returned": 0, "overdue": 7 },
    "by_time": [
      { "period": "2026-05", "count": 20 }
    ]
  },
  "meta": { "generated_at": "2026-06-20T08:00:00Z", "cached": false, "from": "2026-05-01", "to": "2026-06-01" }
}
```
> `breakdown=department` → trả `by_department: [{ "department_id": "...", "department_name": "Hóa lý", "count": 20 }]` (admin/leader). **Staff** lọc `department_id` phòng khác → backend **ép về phòng mình** (AC4 FR-RPT-003).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| INVALID_DATE_RANGE | 422 | `from >= to` (AC5) |
| INVALID_GROUP_BY | 422 | `group_by` không hợp lệ |
| VALIDATION_ERROR | 400 | `status`/`time_field`/`breakdown` ngoài enum |
| FORBIDDEN | 403 | **accountant** gọi (B03, BR-RPT-001, AC3) |
| DEPARTMENT_NOT_FOUND | 404 | `department_id` không tồn tại |

**Side effects:** chỉ đọc.

---

### 4. GET /api/v1/reports/chemicals
**Mục đích:** Thống kê **lượng hóa chất tiêu hao** (+ tồn ở mức tổng hợp) theo bộ lọc thống nhất, **tách theo nhóm đo** (FR-RPT-004). Field tiền chỉ vai trò tài chính. Lớp lọc tổng hợp thống nhất cho dashboard — KHÁC `/reports/consumption` chi tiết của M2 (§0.10).
**Auth:** Bearer JWT | **Roles:** admin, leader (mọi phòng), accountant (có tiền), staff (phòng mình, **không tiền**) | **Scope:** theo vai trò | **Rate limit:** 60/min | **Cache:** 60s

**Query params:** bộ lọc thống nhất §0.6 (`type` = `measurement_group` filter: mass\|volume\|count) +

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| `chemical_id` | uuid | ❌ | tồn tại | Lọc 1 hóa chất cụ thể |
| `metric` | enum | ❌ | `consumption` (default) \| `stock` | Tiêu hao (GD out) hay tồn hiện tại |

**Response 200 (accountant — có tiền):**
```json
{
  "success": true,
  "data": {
    "filter": { "from": "2026-05-01", "to": "2026-06-01", "department_id": "dept-hoa-uuid", "metric": "consumption" },
    "by_measurement_group": [
      { "measurement_group": "mass", "base_unit": "g", "total_qty": 500, "consumption_cost": 1500000 },
      { "measurement_group": "volume", "base_unit": "mL", "total_qty": 2000, "consumption_cost": 800000 }
    ],
    "total_cost": 2300000
  },
  "meta": { "generated_at": "2026-06-20T08:00:00Z", "cached": false, "from": "2026-05-01", "to": "2026-06-01" }
}
```

**Response 200 (staff — KHÔNG có field tiền):**
```json
{
  "success": true,
  "data": {
    "filter": { "from": "2026-05-01", "to": "2026-06-01", "department_id": "dept-hoa-uuid", "metric": "consumption" },
    "by_measurement_group": [
      { "measurement_group": "mass", "base_unit": "g", "total_qty": 500 },
      { "measurement_group": "volume", "base_unit": "mL", "total_qty": 2000 }
    ]
  },
  "meta": { "generated_at": "2026-06-20T08:00:00Z", "cached": false }
}
```
> **KHÔNG cộng gộp chéo nhóm đo** (g + mL) — tách `by_measurement_group` (BR-RPT-014, AC1). `consumption_cost`/`total_cost` chỉ trả cho vai trò tài chính (BR-RPT-002, AC2). Staff lọc phòng khác → ép phòng mình (AC3).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| INVALID_DATE_RANGE | 422 | `from >= to` (AC4) |
| INVALID_GROUP_BY | 422 | `group_by` không hợp lệ |
| VALIDATION_ERROR | 400 | `metric`/`type` ngoài enum |
| CHEMICAL_NOT_FOUND | 404 | `chemical_id` không tồn tại |
| DEPARTMENT_NOT_FOUND | 404 | `department_id` không tồn tại |

**Side effects:** chỉ đọc.

---

### 10. GET /api/v1/reports/system-access
**Mục đích:** Thống kê **truy cập hệ thống** toàn HT (R15, FR-RPT-007): (a) lượt truy cập = `access_stats` (xem trang) + `audit_logs` action `LOGIN`; (b) lượt tải = `document_access_log.action='download'`; (c) lượt chỉnh sửa = action CUD trong `audit_logs`. Theo thời gian + **top N user**. **CHỈ admin/leader** (BR-RPT-010). KHÁC `/documents/access-stats` per-tài-liệu của M3 (§0.10).
**Auth:** Bearer JWT (quyền `audit:read`) | **Roles:** **admin, leader CHỈ** | **accountant/staff → 403** | **Scope:** toàn HT | **Rate limit:** 10/min | **Cache:** 60s

**Query params:** bộ lọc thống nhất §0.6 (`from`, `to`, `group_by`) +

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| `user_id` | uuid | ❌ | tồn tại | Lọc 1 user (toàn HT nếu bỏ trống) |
| `action_type` | enum | ❌ | `access` \| `download` \| `edit` \| `all` (default all) | Lọc loại hành động |
| `top_n` | int | ❌ | 1..50 (default 10) | Số user top mỗi loại |
| `include_timeline` | boolean | ❌ | default false | Có trả phân rã theo thời gian không |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "filter": { "from": "2026-05-01", "to": "2026-06-01" },
    "totals": {
      "access_count": 1200,
      "download_count": 80,
      "edit_count": 350
    },
    "breakdown_definition": {
      "access_count": "access_stats (page views) + audit_logs LOGIN",
      "download_count": "document_access_log action=download",
      "edit_count": "audit_logs actions create/update/delete"
    },
    "top_users": {
      "access": [
        { "user_id": "u1-uuid", "user_name": "Nguyễn Văn A", "count": 200 },
        { "user_id": "u2-uuid", "user_name": "Trần Thị B", "count": 150 }
      ],
      "download": [ { "user_id": "u1-uuid", "user_name": "Nguyễn Văn A", "count": 30 } ],
      "edit": [ { "user_id": "u3-uuid", "user_name": "Lê Văn C", "count": 90 } ]
    },
    "timeline": [
      { "period": "2026-05", "access_count": 1200, "download_count": 80, "edit_count": 350 }
    ]
  },
  "meta": { "generated_at": "2026-06-20T08:05:00Z", "cached": false, "from": "2026-05-01", "to": "2026-06-01" }
}
```
> `edit_count` = đúng action CUD; `LOGIN`/`read`/`download` KHÔNG tính vào edit (BR-RPT-004, AC2). `timeline` chỉ trả khi `include_timeline=true`. Kỳ rất rộng (> 1 năm) → cảnh báo qua `meta.warning` hoặc gợi ý async (OQ#7); bản đầu giới hạn kỳ.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| FORBIDDEN | 403 | **accountant / staff** gọi (BR-RPT-010, AC3) — chỉ admin/leader |
| INVALID_DATE_RANGE | 422 | `from >= to` (AC5) |
| INVALID_GROUP_BY | 422 | `group_by` không hợp lệ |
| VALIDATION_ERROR | 400 | `action_type`/`top_n` ngoài giới hạn |
| USER_NOT_FOUND | 404 | `user_id` không tồn tại |

**Side effects:** chỉ đọc (đếm). Truy cập trang này có thể log INFO (giám sát).

---

### 11. GET /api/v1/reports/system-access/users/:userId
**Mục đích:** Chi tiết hoạt động của **một user** (FR-RPT-008): lượt truy cập/tải/chỉnh sửa theo kỳ + (tùy) timeline action gần nhất. Phục vụ giám sát/điều tra (§8.4). **CHỈ admin/leader**.
**Auth:** Bearer JWT (`audit:read`) | **Roles:** **admin, leader CHỈ** | **Scope:** toàn HT | **Rate limit:** 10/min

**Path:** `userId` = user UUID (M7).
**Query params:** bộ lọc §0.6 (`from`, `to`) + `recent_actions` (int, default 20, max 100 — số action gần nhất trong timeline).

**Response 200:**
```json
{
  "success": true,
  "data": {
    "user": { "id": "u1-uuid", "name": "Nguyễn Văn A", "role": "staff", "department_name": "Hóa lý" },
    "filter": { "from": "2026-05-01", "to": "2026-06-01" },
    "totals": { "access_count": 200, "download_count": 30, "edit_count": 28 },
    "recent_actions": [
      { "at": "2026-05-31T09:12:00Z", "action": "SAMPLE_UPDATE", "resource": "sample", "resource_id": "s-uuid", "correlation_id": "c1f2..." },
      { "at": "2026-05-31T08:40:00Z", "action": "DOCUMENT_DOWNLOAD", "resource": "document_version", "resource_id": "dv-uuid" }
    ]
  },
  "meta": { "generated_at": "2026-06-20T08:06:00Z", "cached": false }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| FORBIDDEN | 403 | accountant / staff gọi (BR-RPT-010, AC2) |
| USER_NOT_FOUND | 404 | `userId` không tồn tại (AC3) |
| INVALID_DATE_RANGE | 422 | `from >= to` |

**Side effects:** chỉ đọc.

---

### 12. GET /api/v1/reports/:reportType/export.xlsx
**Mục đích:** Xuất **Excel** báo cáo tổng hợp M6 theo bộ lọc, **tôn trọng RBAC scope** (chỉ dữ liệu user được phép — accountant không xuất báo cáo mẫu; staff chỉ phòng mình + không tiền; R15 chỉ admin/leader). File có header (kỳ, người xuất, thời điểm). Ghi `audit_logs` `REPORT_EXPORT` (FR-RPT-010, BR-RPT-012).
**Auth:** Bearer JWT | **Roles:** theo `reportType` (xem bảng) | **Scope:** theo vai trò | **Rate limit:** 10/min

**Path:** `reportType` ∈

| reportType | Nội dung | Vai trò được xuất |
|------------|----------|-------------------|
| `dashboard` | Snapshot KPI dashboard kỳ | admin, leader, accountant (chỉ phần tài chính), staff (phòng mình) |
| `samples` | Thống kê số mẫu (#3) | admin, leader, staff (phòng) — **accountant 403** |
| `chemicals` | Thống kê tiêu hao hóa chất (#4) | admin, leader, accountant, staff (không tiền) |
| `system-access` | Thống kê truy cập hệ thống (#10) | **admin, leader CHỈ** — accountant/staff 403 |

**Query params:** bộ lọc thống nhất §0.6 + params riêng của báo cáo gốc (vd `status`, `time_field` cho `samples`; `metric` cho `chemicals`).

**Response 200:** binary Excel
```
HTTP/1.1 200 OK
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="bao-cao-so-mau-2026-05.xlsx"
X-Correlation-Id: c1f2...
<binary .xlsx>
```
> File chỉ chứa dữ liệu **trong scope** user (NFR-SEC-RPT-002). File mẫu xuất bởi staff phòng Hóa = chỉ phòng Hóa, KHÔNG cột tiền. File `chemicals` của staff KHÔNG có cột giá/giá trị.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| REPORT_TYPE_NOT_FOUND | 404 | `reportType` ngoài danh sách hỗ trợ |
| FORBIDDEN | 403 | accountant xuất `samples`; staff/accountant xuất `system-access` (BR-RPT-001/010, AC2/AC3) |
| INVALID_DATE_RANGE | 422 | `from >= to` |
| VALIDATION_ERROR | 400 | params lọc sai |
| EXPORT_RANGE_TOO_LARGE | 422 | Kỳ vượt giới hạn xuất sync (gợi ý thu hẹp kỳ — OQ#7) |
| STORAGE_UNAVAILABLE | 503 | MinIO down (nếu lưu file trung gian) |

**Side effects:**
- Sinh file Excel runtime (lưu MinIO nếu cần — C01).
- `audit_logs` action=`REPORT_EXPORT` (detail = `report_type`, `format=xlsx`, kỳ `from/to`, scope, `user_id` — BR-RPT-012, §8.4). Log INFO.

---

### 13. GET /api/v1/reports/:reportType/export.pdf
**Mục đích:** Xuất **PDF** báo cáo trình bày (tập con báo cáo có template — OQ#3: `dashboard` kỳ + báo cáo phục vụ VILAS). Logo/header chuẩn + kỳ + người xuất + thời điểm. RBAC scope như #12. Ghi `audit_logs` `REPORT_EXPORT` (FR-RPT-011, BR-RPT-012).
**Auth:** Bearer JWT | **Roles:** theo `reportType` (như #12) | **Scope:** theo vai trò | **Rate limit:** 10/min

**Path:** `reportType` — **chỉ tập con hỗ trợ PDF** (default: `dashboard`; báo cáo khác → 422 `PDF_NOT_SUPPORTED` hoặc fallback Excel — chốt OQ#3, bản đầu 422).
**Query params:** như #12.

**Response 200:** binary PDF
```
HTTP/1.1 200 OK
Content-Type: application/pdf
Content-Disposition: attachment; filename="bao-cao-tong-hop-2026-05.pdf"
X-Correlation-Id: c1f2...
<binary .pdf>
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| PDF_NOT_SUPPORTED | 422 | `reportType` chưa cấu hình template PDF (AC2) |
| REPORT_TYPE_NOT_FOUND | 404 | `reportType` ngoài danh sách |
| FORBIDDEN | 403 | ngoài quyền (như #12, AC3) |
| INVALID_DATE_RANGE | 422 | `from >= to` |
| EXPORT_RANGE_TOO_LARGE | 422 | kỳ vượt giới hạn sync |

**Side effects:** sinh PDF runtime; `audit_logs` `REPORT_EXPORT` (`format=pdf`) — BR-RPT-012.

---

### 14. POST /api/v1/analytics/page-view
**Mục đích:** FE (SPA) ghi **1 lượt xem trang chính** vào `access_stats` (R15, FR-RPT-009) cho điều hướng client-side — **bổ sung** middleware HTTP (§0.9). Nhẹ, không chặn, không trả dữ liệu.
**Auth:** Bearer JWT (mọi vai trò đã đăng nhập; trang login chưa auth do middleware ghi `user_id=NULL`) | **Rate limit:** 120/min

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| `path` | string | ✅ | maxLength(255); chỉ path nội bộ (regex `^/[a-zA-Z0-9/_-]*`); **không chứa query nhạy cảm** | Đường dẫn trang chính (vd `/dashboard`, `/samples`) |

> Server lấy `user_id` từ JWT, `ip` từ request, `at` = now, `method='PAGE_VIEW'`, `status_code=200`. Server **strip query string nhạy cảm** trước khi ghi (logging.md). Chỉ ghi nếu `path` thuộc whitelist trang chính (BR-RPT-005) — path ngoài whitelist bị bỏ qua âm thầm (vẫn 204).

**Response 204:** No Content (sự kiện ghi nhận, không trả body).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | `path` thiếu / sai định dạng |
| UNAUTHORIZED | 401 | thiếu token (trang đã auth) |

**Side effects:** GHI `access_stats` (ngoại lệ READ-ONLY hợp lệ — CONSTRAINT-2). Lỗi ghi → log WARN, KHÔNG fail (BR-RPT-013); vẫn trả 204 để không chặn FE (best-effort, FR-RPT-009 AC3).

---

## 3. Danh mục Error Codes M6

| Code | HTTP | Nghĩa | Endpoint |
|------|------|-------|----------|
| `VALIDATION_ERROR` | 400 | Param sai kiểu/enum/giới hạn | mọi endpoint |
| `INVALID_DATE_RANGE` | 422 | `from >= to` (khoảng `[from, to)` không hợp lệ) — BR-RPT-009 | #2,#3,#4,#10,#11,#12,#13 |
| `INVALID_GROUP_BY` | 422 | `group_by` ∉ {day, week, month} | #2,#3,#4,#10 |
| `FORBIDDEN` | 403 | Vi phạm RBAC scope: accountant xin KPI/báo cáo mẫu (B03); staff/accountant gọi R15 (#10/#11/#12 system-access); staff lọc ngoài scope (ở mức cấm — nhưng M6 ép scope thay vì cấm) | #2,#3,#10,#11,#12,#13 |
| `REPORT_TYPE_NOT_FOUND` | 404 | `reportType` ngoài danh sách hỗ trợ | #12,#13 |
| `PDF_NOT_SUPPORTED` | 422 | `reportType` chưa cấu hình template PDF (OQ#3) | #13 |
| `EXPORT_RANGE_TOO_LARGE` | 422 | Kỳ xuất vượt giới hạn sync (gợi ý thu hẹp / async — OQ#7) | #12,#13 |
| `DEPARTMENT_NOT_FOUND` | 404 | `department_id` không tồn tại | #1,#2,#3,#4 |
| `USER_NOT_FOUND` | 404 | `user_id`/`userId` không tồn tại | #10,#11 |
| `CHEMICAL_NOT_FOUND` | 404 | `chemical_id` không tồn tại | #4 |
| `STORAGE_UNAVAILABLE` | 503 | MinIO down khi lưu file xuất | #12,#13 |
| `RATE_LIMIT_EXCEEDED` | 429 | Vượt rate limit (10/min cho R15+export) | #10,#11,#12,#13 |
| `UNAUTHORIZED` | 401 | Thiếu/sai JWT | mọi endpoint |

> **Lưu ý cách ly tài chính (B03):** với accountant, KPI/báo cáo mẫu được **lọc khỏi response** (response không chứa khối `samples`) ở `/dashboard` (#1); ở endpoint **chuyên về mẫu** (#3, #12 `samples`) accountant nhận **403 `FORBIDDEN`** (không có dữ liệu hợp lệ để trả). Field tiền cho staff được **strip ở serializer** (không lỗi, chỉ vắng field — BR-RPT-002).

---

## 4. RBAC scope chi tiết + Cache (tóm tắt enforce)

### 4.1 Ma trận RBAC × endpoint (enforce ở TẦNG API — NFR-SEC-RPT-001)

| Endpoint | admin | leader | accountant | staff |
|----------|-------|--------|-----------|-------|
| #1 `/dashboard` | ✅ full | ✅ full | ✅ chỉ tài chính (no `samples`/`equipments`) | ✅ phòng mình, no tiền, no `hr` |
| #2 `/dashboard/charts` | ✅ | ✅ | ✅ chỉ chart hóa chất (chart mẫu → 403) | ✅ phòng mình, no tiền |
| #3 `/reports/samples` | ✅ mọi phòng | ✅ mọi phòng | ❌ **403** (B03) | ✅ ép phòng mình |
| #4 `/reports/chemicals` | ✅ + tiền | ✅ + tiền | ✅ + tiền | ✅ ép phòng mình, no tiền |
| #10 `/reports/system-access` | ✅ | ✅ | ❌ **403** | ❌ **403** |
| #11 `/system-access/users/:id` | ✅ | ✅ | ❌ **403** | ❌ **403** |
| #12 export.xlsx `samples` | ✅ | ✅ | ❌ **403** | ✅ phòng mình, no tiền |
| #12/#13 export `system-access` | ✅ | ✅ | ❌ **403** | ❌ **403** |
| #14 `/analytics/page-view` | ✅ | ✅ | ✅ | ✅ |

**Quy tắc enforce (CONSTRAINT-3):**
1. **B03 — cách ly nghiệp vụ/tài chính:** accountant KHÔNG nhận khối `samples`/`equipments`/`documents` nghiệp vụ ở #1; gọi endpoint chuyên mẫu (#3, #12-samples) → 403. Lọc ở backend, KHÔNG ở FE.
2. **Field tiền (BR-RPT-002):** chỉ admin/leader/accountant (`chemical:cost`). Staff/KTV → strip `consumption_cost`/`total_cost`/`cost`/`consumption_cost_month` ở serializer.
3. **R15 (BR-RPT-010):** #10/#11 và export `system-access` chỉ admin/leader (quyền `audit:read`). accountant/staff → 403 cứng.
4. **Scope phòng staff (BR-RPT-001):** staff truyền `department_id` ngoài phòng mình → **ép về phòng mình** (không 403) ở #1–#4, #12.

### 4.2 Cache (BR-RPT-011, §0.8)
- Áp cho #1, #2, #3, #4, #10 (đọc aggregate). **TTL 60s** (OQ#2). Key gồm vai trò + scope phòng + bộ lọc → KHÔNG dùng chung cache giữa vai trò khác scope (tránh rò rỉ).
- #11 (chi tiết 1 user), #12/#13 (xuất file), #14 (ghi) **KHÔNG cache**.
- `meta.cached` + `meta.generated_at` + `meta.cache_ttl_seconds` trả về để FE biết độ tươi.

---

## 5. Ghi chú phi chức năng

| NFR | Cam kết M6 | Áp dụng |
|-----|-----------|---------|
| **Perf dashboard** (NFR-PERF-RPT-001) | `/dashboard` P95 < **2000ms** (no cache) / < 300ms (cache), 10 concurrent users; gom KPI 1 round-trip + cache 60s | #1, #2 |
| **Perf thống kê/R15** (NFR-PERF-RPT-002) | #3/#4 kỳ 1 năm P95 < 2000ms; #10 R15 kỳ 1 tháng P95 < 3000ms (dùng index `access_stats(at)/(user_id,at)`, `audit_logs(at)/(user_id,at)` đã có ở M7); kỳ rộng → async (OQ#7) | #3,#4,#10 |
| **Middleware overhead** (NFR-PERF-RPT-003) | Ghi access_stats không chặn — overhead < 5ms/request, P95 endpoint không tăng > 5%; lỗi ghi → WARN, không fail | §0.9, #14 |
| **Pagination** | List (#10 top users khi limit lớn, #11 timeline, #12 nếu cần) offset-based, default 20/max 100; aggregate KHÔNG phân trang | §0.4 |
| **CorrelationId** (NFR-OBS-RPT-001) | Mọi request M6 có correlation_id (FE → BE → DB); query aggregate > 1s log WARN slow query; xuất báo cáo log INFO; lỗi nguồn/cache/MinIO log ERROR (không lộ stack ra client) | mọi endpoint |
| **Degrade mềm** (NFR-AVAIL-RPT-001) | 1 module nguồn lỗi → KPI khối đó `available:false`, dashboard vẫn 200; lỗi ghi access_stats không fail request | #1, #14 |
| **Consistency thời gian** (NFR-CONSISTENCY-RPT-001) | Mọi báo cáo dùng `[from, to)` nửa mở + cùng múi giờ; số liệu nhất quán giữa dashboard/thống kê/file xuất (0 lệch biên) | §0.6, mọi báo cáo |
| **Integrity** (NFR-INTEG-RPT-001) | KPI M6 = số liệu định nghĩa module nguồn (overdue = M1, expiring = M2, calibration_overdue = M5) — 0 sai lệch | #1, #2, #3, #4 |
| **Security RBAC** (NFR-SEC-RPT-001/002) | Ma trận 4 vai trò × mọi endpoint pass 100%; 0 rò rỉ KPI mẫu cho accountant; 0 field tiền cho staff; 100% R15 chặn non-admin/leader; file xuất đúng scope; mọi lần xuất ghi audit | §4, #10–#13 |

---

## 6. Traceability — Endpoint → FR SRS M6 → Yêu cầu gốc (R8/R10/R15/R4) → BR

| Endpoint | FR | Submodule | Yêu cầu gốc | Business Rule | Tổng hợp từ (§9.2 SRS) |
|----------|-----|-----------|-------------|---------------|------------------------|
| #1 `GET /dashboard` | FR-RPT-001, FR-RPT-006 | M6.1 | **R8, R10** (R12 KPI nhân sự) | BR-001,002,003,004,006,007,008,011,013 | M1,M2,M3,M4,M5,M7 (đếm KPI) |
| #2 `GET /dashboard/charts` | FR-RPT-002 | M6.1 | **R10** | BR-001,002,009,014 | M1 (`samples`), M2 (`chemical_transactions`) |
| #3 `GET /reports/samples` | FR-RPT-003, FR-RPT-005 | M6.2 | **R8, R10** | BR-001,009,012 | M1 (`samples`) — KHÔNG trùng `/reports/sample-on-time` |
| #4 `GET /reports/chemicals` | FR-RPT-004, FR-RPT-005 | M6.2 | **R10** | BR-001,002,009,014 | M2 — KHÔNG trùng `/reports/consumption`,`/inventory/low-stock` |
| #10 `GET /reports/system-access` | FR-RPT-007 | M6.3 | **R15** (§8.4) | BR-004,009,010 | M7 (`access_stats`,`audit_logs`) + M3 (`document_access_log`) — độc quyền M6 |
| #11 `GET /system-access/users/:id` | FR-RPT-008 | M6.3 | **R15** (§8.4) | BR-004,009,010 | như #10 lọc user |
| #12 `GET /reports/:type/export.xlsx` | FR-RPT-010 | M6.4 | **R4** (§8.4) | BR-001,002,009,010,012 | tùy reportType; audit `REPORT_EXPORT` |
| #13 `GET /reports/:type/export.pdf` | FR-RPT-011 | M6.4 | **R4** (§8.4) | BR-001,009,010,012 | tùy reportType; audit `REPORT_EXPORT` |
| #14 `POST /analytics/page-view` | FR-RPT-009 | M6.3 | **R15** | BR-004,005,013 | GHI `access_stats` (hạ tầng) |
| (middleware) ghi access_stats | FR-RPT-009 | M6.3 | **R15** | BR-004,005,013 | GHI `access_stats` (§0.9, không endpoint) |

**Mapping ISO/IEC 17025 §8.4 (kiểm soát hồ sơ):**
- `audit_logs` là nguồn đếm "lượt chỉnh sửa" (R15 — #10/#11) và truy vết thao tác **xuất báo cáo** (`REPORT_EXPORT` — #12/#13, BR-RPT-012). M6 KHÔNG sửa/xóa `audit_logs` (append-only — M7).

---

*Hết Contract M6 API (v1.0). 9 endpoint client (1 dashboard + 1 charts + 2 thống kê thời gian + 2 R15 + 2 export + 1 page-view) + 1 middleware ghi access_stats. READ-ONLY aggregate, ngoại lệ duy nhất = ghi access_stats (#14 + middleware) + audit `REPORT_EXPORT` (#12/#13). KHÔNG trùng endpoint module khác (§0.10 liệt kê rõ 6 endpoint đã có không làm lại). RBAC enforce tầng API: accountant không thấy mẫu (B03), staff không thấy tiền + ép phòng mình, R15 chỉ admin/leader (`audit:read`). Cache dashboard 60s; bộ lọc thời gian thống nhất `[from, to)`. Đồng bộ phong cách M5/M3. Default OQ phản ánh: #1 whitelist trang chính, #2 cache 60s, #5 R15 chỉ admin/leader, #6 lượt tải = document_access_log, #9 received_at + tháng hiện tại.*
