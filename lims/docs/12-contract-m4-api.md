# API Contract: M4 — Nhân sự & Thành tích NCKH (HR & Research Achievement)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M4 — HR & Research Achievement
**Version:** 1.0 | **Ngày:** 20/06/2026 | **Designer:** api-designer agent
**Nguồn chân lý:** `10-srs-m4-hr.md` (20 FR, 24 BR, RBAC field-level lương) + quyết định đã chốt với KH (OQ#1, OQ#2, OQ#8, OQ#8c, danh mục mặc định)
**Đồng bộ phong cách:** `09-contract-m7-api.md` + `04-contract-m2-api.md` (prefix `/api/v1`, response `{success,data,meta}`/`{success:false,error}`, UUID, pagination 20/100, correlationId, field-level strip giống M2 strip cột giá BR-CHEM-022)
**Stack:** FastAPI + PostgreSQL + Redis + MinIO + APScheduler (monolith, ~40 user)

> M4 **phụ thuộc M7** (đã chạy): auth JWT, RBAC, `users`/`departments`/`audit_logs`/`notifications`/`attachments` dùng chung. `hr_profiles.user_id` là **1-1 FK → users.id** — M4 KHÔNG tạo bảng người dùng riêng. Điểm cốt lõi của M4 là **cách ly trường lương ở tầng API (field-level strip)** — đồng bộ pattern M2 strip cột giá khỏi KTV.

---

## 0. Quy ước chung (đọc trước)

### 0.1 Base & versioning
- Prefix: `/api/v1`. Resource là danh từ số nhiều (`/hr-profiles`, `/research-projects`, `/publications`, `/student-mentorships`, `/lab-registrations`, `/teaching-courses`, `/community-services`).
- Nested tối đa 2 cấp: `/hr-profiles/:userId/salary-history`, `/research-projects/:id/members`, `/publications/:id/authors`.
- **Định danh hồ sơ nhân sự = `user_id` (UUID)** vì `hr_profiles` 1-1 với `users` (PK = FK). Path param `/hr-profiles/:userId` dùng `user_id`. Các resource thành tích dùng UUID `id` riêng. KHÔNG lộ ID tuần tự (rule api.md).
- Không breaking change trong cùng `v1`; deprecated báo trước ≥ 1 sprint + header `Deprecation: true`.

### 0.2 Response format chuẩn (đồng bộ M7/M2)
```jsonc
// Success — single
{ "success": true, "data": { /* object */ } }
// Success — list (pagination)
{ "success": true, "data": [ /* items */ ],
  "meta": { "page": 1, "limit": 20, "total": 137, "hasNext": true } }
// Error
{ "success": false,
  "error": {
    "code": "SNAKE_CASE_CODE",
    "message": "Thông điệp cho người dùng/dev (KHÔNG stack trace)",
    "details": [ { "field": "salary_coefficient", "message": "..." } ],
    "correlationId": "c1f2..."   // luôn trả để user report support (rule logging.md)
  } }
```

### 0.3 Auth & headers
- **Mọi endpoint** yêu cầu `Authorization: Bearer <access_token>` (M7). Không có endpoint public trong M4.
- `X-Correlation-Id` (UUID): client gửi; thiếu → server tự sinh; **luôn trả lại** trong response header + ghi `audit_logs.correlation_id` (VILAS §8.4 — BR-HR-004).
- `Content-Type: application/json` trừ upload minh chứng năng lực (multipart — endpoint #20).
- 401 `UNAUTHORIZED` (thiếu/sai token); 403 `FORBIDDEN` (thiếu quyền/sai phạm vi/sai scope).

### 0.4 Pagination
- Mọi endpoint list: `page` (default 1), `limit` (default **20**, max **100** — vượt ép về 100). Offset-based. `meta` luôn có `page`, `limit`, `total`, `hasNext`.

### 0.5 RBAC 4 vai trò (đồng bộ M7 §0.6)
- `admin` (toàn quyền), `leader` (Ban lãnh đạo), `accountant` (Kế toán), `staff` (Nhân sự/KTV). Phạm vi mặc định **theo phòng ban** trừ admin/leader/accountant (toàn hệ thống).
- Quyền M4 đã seed M7: `hr:read`, `hr:manage`, `research:manage`.
- **`is_dept_lead`** (trưởng nhóm phòng, claim phái sinh từ `departments.lead_user_id`): dùng cho **duyệt lượt SV đăng ký lab** (#34) — trưởng nhóm phòng của mentor được duyệt.

### 0.6 Field-level RBAC — cách ly LƯƠNG (CỐT LÕI M4 — đồng bộ M2 BR-CHEM-022, OQ#1+OQ#2 đã chốt)

**Quyết định đã chốt:**
- **Cấu trúc lương (OQ#2):** lương = **hệ số × lương cơ sở**. 3 field: `salary_grade` (bậc/ngạch, string danh mục), `salary_coefficient` (hệ số, NUMERIC(6,2)), `base_salary_amount` (lương cơ sở, NUMERIC(14,2), `currency` mặc định `VND`). Mức lương thực tế hiển thị = `salary_coefficient × base_salary_amount` (BE tính, trả `computed_salary_amount` chỉ cho người đủ quyền).

**Tập trường tài chính (financial fields) bị strip:**
```
salary_grade, salary_coefficient, base_salary_amount, computed_salary_amount, currency,
salary_history (toàn bộ mảng), next_salary_raise_date, last_salary_raise_date
```
> Lưu ý: `next_salary_raise_date`/`last_salary_raise_date` thuộc nhóm tài chính (gắn nghiệp vụ lương) — strip cùng nhóm. Trường hợp đồng (`contract_*`) là nhóm RIÊNG (xem 0.7).

**Quyền ĐỌC lương (OQ#1):**
| Vai trò | Đọc lương người khác | Đọc lương của chính mình |
|---------|----------------------|--------------------------|
| admin / leader / accountant | ✅ (toàn hệ thống) | ✅ |
| staff | ❌ (strip ở API) | ✅ (chính chủ — `hr_profiles.user_id == sub`) |

**Quyền SỬA lương (OQ#1 — đã chốt):**
| Vai trò | Ghi nâng lương / sửa hệ số/bậc/lương cơ sở |
|---------|-------------------------------------------|
| admin | ✅ |
| accountant | ✅ |
| leader | ❌ → 403 `SALARY_FORBIDDEN` (leader chỉ XEM lương, KHÔNG sửa) |
| staff | ❌ → 403 `SALARY_FORBIDDEN` |

**Cơ chế strip (giống M2):** khi response chứa hồ sơ của người mà người gọi KHÔNG đủ quyền xem lương → **toàn bộ key tài chính bị loại khỏi JSON** (không trả `null`, không trả key). Lọc ở **tầng API** — kiểm thử bằng NFR-SEC-HR-001. Áp dụng cho: chi tiết hồ sơ (#3), danh sách hồ sơ (#1), lịch sử lương (#9), thống kê (#37 không trả lương). Mỗi item trong list được strip ĐỘC LẬP theo `item.user_id == sub`.

### 0.7 Field-level RBAC — HỢP ĐỒNG & PII
- **Hợp đồng** (`contract_signed_date`, `contract_type`, `contract_end_date`): Kế toán quản lý (B03). ĐỌC: admin/leader/accountant (toàn HT) + chính chủ. SỬA: admin + accountant (leader/staff → 403). Strip khỏi response cho staff khi xem người khác (nhóm `contract_*`).
- **PII** (`id_number` CMND/CCCD, `dob`, `bank_account`): ĐỌC chỉ admin/accountant + chính chủ; strip cho leader/staff khi xem người khác. KHÔNG ghi giá trị PII/lương vào `audit_logs.detail`/log/Sentry (BR-HR-024, CONSTRAINT-9) — chỉ ghi fact "đã đổi trường X".

### 0.8 Scope thành tích NCKH (BR-HR-023, OQ#8c đã chốt)
- `research:manage`: admin/leader = `all`; staff = `own` (chỉ thành tích mình tham gia là thành viên/tác giả/mentor/performer). **Kế toán KHÔNG truy cập thành tích NCKH** → 403 `FORBIDDEN`.
- **Tác giả/thành viên ngoài hệ thống (OQ#8c đã chốt = CÓ):** hỗ trợ qua field `external_name` (free-text) khi `user_id = null`. Mỗi tác giả/thành viên là **HOẶC** `user_id` (FK→users) **HOẶC** `external_name` — không cả hai, không cả hai null (BR — `INVALID_AUTHOR`).
- Staff scope `own`: khi tạo thành tích, staff PHẢI là một thành viên/tác giả nội bộ của bản ghi đó; gắn người nội bộ khác làm đồng tác giả vẫn cho phép (đã chốt cho khai báo tiện lợi), nhưng tác giả ngoài hệ thống dùng `external_name`.

### 0.9 Đăng ký lab — workflow duyệt (OQ#8 đã chốt = CÓ DUYỆT)
- Tạo lượt đăng ký → `status = pending`. Mentor/trưởng nhóm phòng (`is_dept_lead` của phòng mentor)/admin **duyệt → approved** hoặc **từ chối → rejected**. **Chỉ lượt `approved`** được tính vào thống kê (#37). Đã duyệt/từ chối rồi → không duyệt lại (`REGISTRATION_ALREADY_DECIDED`).

### 0.10 Danh mục mặc định (đã seed)
- `contract_types`, `project_levels`, `pub_indexes`, `mentorship_types` đã seed giá trị mặc định; admin cấu hình thêm. M4 chỉ cung cấp **GET đọc danh mục** (#38, #39 + 2 GET danh mục còn lại) — phần CRUD danh mục thuộc admin/seed.

### 0.11 Rate limit
- Đọc/ghi thường: **60 req/phút/user**.
- Endpoint nặng (thống kê #37, xuất Excel/PDF #37b/#21b): **10 req/phút/user**.
- Badge/poll nhẹ: 120/phút. Vượt → **429** `RATE_LIMIT_EXCEEDED`.

### 0.12 Số học & tiền (đồng bộ M2 §0.5)
- `base_salary_amount`, `computed_salary_amount`, `salary_history.*_amount`: NUMERIC(14,2); `salary_coefficient`: NUMERIC(6,2). Trả về JSON dạng **string** để tránh mất chính xác (vd `"base_salary_amount": "2340000.00"`). `currency` default `VND`.

---

## 1. Bảng tổng hợp Endpoint

| # | Method | Path | Mô tả | Vai trò (ghi) | Scope | FR |
|---|--------|------|-------|---------------|-------|-----|
| **Hồ sơ nhân sự (M4.1)** ||||||
| 1 | GET | `/api/v1/hr-profiles` | Liệt kê + lọc hồ sơ nhân sự (lương/HĐ/PII strip theo quyền) | admin, leader, accountant | Toàn HT (staff không list) | FR-HR-001 |
| 2 | POST | `/api/v1/hr-profiles` | Tạo hồ sơ gắn user (1-1) | admin, accountant | Toàn HT | FR-HR-001 |
| 3 | GET | `/api/v1/hr-profiles/:userId` | Chi tiết hồ sơ (strip lương/HĐ/PII theo quyền) | admin, leader, accountant, staff(của mình) | self/Toàn HT | FR-HR-001 |
| 4 | GET | `/api/v1/hr-profiles/me` | Hồ sơ của chính mình (đầy đủ lương của mình) | mọi vai trò | self | FR-HR-001 |
| 5 | PATCH | `/api/v1/hr-profiles/:userId` | Cập nhật phi-tài-chính (chức danh, liên hệ) | admin, accountant | Toàn HT | FR-HR-002 |
| 6 | PATCH | `/api/v1/hr-profiles/:userId/contract` | Cập nhật hợp đồng (ngày ký/loại/hết hạn) | admin, accountant | Toàn HT | FR-HR-003 |
| 7 | PATCH | `/api/v1/hr-profiles/:userId/salary-cycle` | Cập nhật chu kỳ nâng lương | admin, accountant | Toàn HT | FR-HR-006 |
| 8 | POST | `/api/v1/hr-profiles/:userId/salary-raises` | Ghi nhận nâng lương (cập nhật mức + lịch sử + tự tính ngày kế tiếp) | admin, accountant | Toàn HT | FR-HR-004/005 |
| 9 | GET | `/api/v1/hr-profiles/:userId/salary-history` | Lịch sử nâng lương (chỉ người đủ quyền + chính chủ) | admin, leader, accountant, staff(của mình) | self/Toàn HT | FR-HR-004 |
| **Hồ sơ năng lực §6.2 (M4.1.4)** ||||||
| 10 | GET | `/api/v1/hr-profiles/:userId/competences` | Liệt kê bằng cấp/chứng chỉ/ủy quyền | admin, leader, staff(của mình) | self/Toàn HT | FR-HR-007 |
| 11 | POST | `/api/v1/hr-profiles/:userId/competences` | Thêm mục năng lực | admin, leader | Toàn HT | FR-HR-007 |
| 12 | PATCH | `/api/v1/competences/:id` | Sửa mục năng lực | admin, leader | Toàn HT | FR-HR-007 |
| 13 | DELETE | `/api/v1/competences/:id` | Xóa mục năng lực | admin, leader | Toàn HT | FR-HR-007 |
| 14 | POST | `/api/v1/competences/:id/attachments` | Upload minh chứng (degree/cert/authorization) | admin, leader | Toàn HT | FR-HR-007 |
| 15 | GET | `/api/v1/hr-profiles/:userId/competence-summary` | Hồ sơ năng lực tổng hợp (không lương) | admin, leader, staff(của mình) | self/Toàn HT | FR-HR-019 |
| 16 | GET | `/api/v1/hr-profiles/:userId/competence-summary.pdf` | Xuất PDF hồ sơ năng lực (§6.2) | admin, leader, staff(của mình) | self/Toàn HT | FR-HR-020 |
| **Đề tài NCKH (M4.3.1)** ||||||
| 17 | GET | `/api/v1/research-projects` | Liệt kê + lọc đề tài (phòng/cấp/năm/chủ nhiệm) | admin, leader, staff(own) | own/all | FR-HR-010 |
| 18 | POST | `/api/v1/research-projects` | Tạo đề tài + thành viên n-n | admin, leader, staff(own) | own/all | FR-HR-010 |
| 19 | GET | `/api/v1/research-projects/:id` | Chi tiết đề tài + thành viên | admin, leader, staff(own) | own/all | FR-HR-010 |
| 20 | PATCH | `/api/v1/research-projects/:id` | Cập nhật đề tài (partial) | admin, leader, staff(own) | own/all | FR-HR-010 |
| 21 | DELETE | `/api/v1/research-projects/:id` | Xóa đề tài | admin, leader, staff(own) | own/all | FR-HR-010 |
| 22 | PUT | `/api/v1/research-projects/:id/members` | Thay toàn bộ danh sách thành viên | admin, leader, staff(own) | own/all | FR-HR-010 |
| **Bài báo / Sáng chế (M4.3.2/3.3)** ||||||
| 23 | GET | `/api/v1/publications` | Liệt kê + lọc bài báo/sáng chế (năm/chỉ số/phòng/tác giả/type) | admin, leader, staff(own) | own/all | FR-HR-011/012 |
| 24 | POST | `/api/v1/publications` | Tạo bài báo/sáng chế + tác giả n-n | admin, leader, staff(own) | own/all | FR-HR-011/012 |
| 25 | GET | `/api/v1/publications/:id` | Chi tiết + tác giả (thứ tự) | admin, leader, staff(own) | own/all | FR-HR-011/012 |
| 26 | PATCH | `/api/v1/publications/:id` | Cập nhật (partial) | admin, leader, staff(own) | own/all | FR-HR-011/012 |
| 27 | DELETE | `/api/v1/publications/:id` | Xóa | admin, leader, staff(own) | own/all | FR-HR-011/012 |
| 28 | PUT | `/api/v1/publications/:id/authors` | Thay toàn bộ danh sách tác giả + thứ tự | admin, leader, staff(own) | own/all | FR-HR-011 |
| 29 | POST | `/api/v1/publications/:id/attachments` | Upload minh chứng bài báo | admin, leader, staff(own) | own/all | FR-HR-011 |
| **Hướng dẫn SV (M4.3.5)** ||||||
| 30 | GET | `/api/v1/student-mentorships` | Liệt kê + lọc (mentor/năm/loại/phòng) | admin, leader, staff(own) | own/all | FR-HR-014 |
| 31 | POST | `/api/v1/student-mentorships` | Tạo hướng dẫn SV | admin, leader, staff(own) | own/all | FR-HR-014 |
| 32 | PATCH/DELETE | `/api/v1/student-mentorships/:id` | Sửa/xóa | admin, leader, staff(own) | own/all | FR-HR-014 |
| **Đăng ký lab — có duyệt (M4.3.6)** ||||||
| 33 | GET | `/api/v1/lab-registrations` | Liệt kê + lọc theo status/mentor/phòng | admin, leader, staff(own) | own/all | FR-HR-015 |
| 34a | POST | `/api/v1/lab-registrations` | Tạo lượt đăng ký (status=pending) | admin, leader, staff(own) | own/all | FR-HR-015 |
| 34b | POST | `/api/v1/lab-registrations/:id/approve` | Duyệt → approved | admin, leader, mentor/trưởng nhóm | own/all | FR-HR-015 |
| 34c | POST | `/api/v1/lab-registrations/:id/reject` | Từ chối → rejected | admin, leader, mentor/trưởng nhóm | own/all | FR-HR-015 |
| **Giảng dạy & Cộng đồng (M4.3.7/3.8)** ||||||
| 35 | GET/POST/PATCH/DELETE | `/api/v1/teaching-courses[/:id]` | CRUD môn giảng dạy | admin, leader, staff(own) | own/all | FR-HR-016 |
| 36 | GET/POST/PATCH/DELETE | `/api/v1/community-services[/:id]` | CRUD phục vụ cộng đồng | admin, leader, staff(own) | own/all | FR-HR-017 |
| **Thống kê (M4.3.x)** ||||||
| 37 | GET | `/api/v1/research-achievements/stats` | Thống kê tổng hợp theo cá nhân/phòng/thời gian | admin, leader, staff(own) | own/all | FR-HR-018 |
| 37b | GET | `/api/v1/research-achievements/stats.xlsx` | Xuất Excel báo cáo năng lực §6.2 | admin, leader, staff(own) | own/all | FR-HR-018 |
| **Danh mục (đọc — đã seed)** ||||||
| 38 | GET | `/api/v1/catalogs/project-levels` | Danh mục cấp đề tài | mọi vai trò (đọc) | Toàn HT | FR-HR-010 |
| 39 | GET | `/api/v1/catalogs/pub-indexes` | Danh mục phân loại/chỉ số bài báo | mọi vai trò (đọc) | Toàn HT | FR-HR-011 |
| 40 | GET | `/api/v1/catalogs/contract-types` | Danh mục loại hợp đồng | admin, leader, accountant | Toàn HT | FR-HR-003 |
| 41 | GET | `/api/v1/catalogs/mentorship-types` | Danh mục loại hướng dẫn SV | mọi vai trò (đọc) | Toàn HT | FR-HR-014 |
| **Cron (vận hành/test)** ||||||
| 42 | POST | `/api/v1/admin/crons/salary-raise-due/run` | Chạy thủ công CRON-3 (test) | admin | Toàn HT | FR-HR-008 |
| 43 | POST | `/api/v1/admin/crons/contract-expiry/run` | Chạy thủ công CRON-4 (test) | admin | Toàn HT | FR-HR-009 |

> CRON-3/CRON-4 là scheduled job (APScheduler 07:00), không endpoint công khai — chỉ có endpoint admin chạy thủ công để test (#42/#43). Notifications đọc qua M7 #24–#27.

---

## 2. Chi tiết Endpoint

---

### 1. GET /api/v1/hr-profiles
**Mục đích:** Liệt kê + lọc hồ sơ nhân sự cho quản lý nhân sự (FR-HR-001). Mỗi item **strip lương/HĐ/PII** theo quyền người gọi (BR-HR-002/003).
**Auth:** Bearer JWT | **Roles:** admin, leader, accountant | **Scope:** toàn HT | **Rate limit:** 60/phút

> **Staff KHÔNG được list toàn bộ nhân sự** → 403 `FORBIDDEN` (staff chỉ xem hồ sơ của mình qua #4). Đây là quyết định scope `own` chặt: staff không liệt kê người khác.

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| q | string | ❌ | maxLength(100) | Tìm theo tên/email (join users) |
| department_id | uuid | ❌ | — | Lọc theo phòng ban (suy từ users) |
| job_title | string | ❌ | maxLength(100) | Lọc chức danh |
| contract_expiring_within_days | int | ❌ | 1..3650 | HĐ sắp hết hạn trong N ngày |
| salary_raise_within_days | int | ❌ | 1..3650 | Sắp tới hạn nâng lương trong N ngày |
| page/limit | int | ❌ | pagination chuẩn | |

**Response 200 (người gọi = accountant — CÓ lương/HĐ):**
```json
{
  "success": true,
  "data": [
    {
      "user_id": "user-uuid",
      "full_name": "Nguyễn Văn A",
      "email": "ktv.a@lab.edu.vn",
      "department_id": "dept-uuid",
      "department_name": "Hóa lý",
      "job_title": "KTV chính",
      "hired_date": "2024-01-01",
      "contract_signed_date": "2024-01-01",
      "contract_type": "fixed_term",
      "contract_end_date": "2026-12-31",
      "salary_grade": "A1.3",
      "salary_coefficient": "3.66",
      "base_salary_amount": "2340000.00",
      "computed_salary_amount": "8564400.00",
      "currency": "VND",
      "salary_cycle_years": 3,
      "last_salary_raise_date": null,
      "next_salary_raise_date": "2027-01-01"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 38, "hasNext": true }
}
```
> **Người gọi = leader:** trả lương (leader XEM được) nhưng KHÔNG có endpoint sửa lương. PII vẫn strip cho leader (chỉ admin/accountant + chính chủ xem PII — §0.7).

**Errors:** `FORBIDDEN` (403 staff), `VALIDATION_ERROR` (400).

---

### 2. POST /api/v1/hr-profiles
**Mục đích:** Tạo hồ sơ nhân sự gắn 1-1 với một `users` đã tồn tại (FR-HR-001, BR-HR-001).
**Auth:** Bearer JWT | **Roles:** admin, accountant | **Scope:** toàn HT | **Rate limit:** 60/phút

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| user_id | uuid | ✅ | tồn tại trong `users`, chưa có hồ sơ | User gắn 1-1 (cho phép user `disabled` — giữ hồ sơ, OQ#2c) |
| job_title | string | ✅ | maxLength(100), trim non-empty | Chức danh |
| hired_date | date | ❌ | ISO date | Ngày vào làm |
| phone | string | ❌ | maxLength(20) | SĐT liên hệ |
| id_number | string | ❌ | maxLength(20) | CMND/CCCD (PII — không log) |
| dob | date | ❌ | ISO date | Ngày sinh (PII) |
| bank_account | string | ❌ | maxLength(30) | Số TK NH (PII — không log) |

> `department_id` KHÔNG nhận — suy từ `users.department_id`. Lương KHÔNG nhận ở đây (ghi qua #8). `next_salary_raise_date` tự tính.

**Response 201:** object hồ sơ như #1 (đã strip theo quyền người gọi — admin/accountant CÓ đủ).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | thiếu job_title / field sai |
| HR_PROFILE_EXISTS / DUPLICATE_PROFILE | 409 | user đã có hồ sơ (1-1 — BR-HR-001) |
| USER_NOT_FOUND | 404 | user_id không tồn tại |
| FORBIDDEN | 403 | leader/staff (chỉ admin/accountant tạo) |

> **Lưu ý code:** dùng **`DUPLICATE_PROFILE`** làm code chuẩn cho trùng hồ sơ 1-1 (SRS dùng tên `HR_PROFILE_EXISTS` — coi là alias; contract chốt `DUPLICATE_PROFILE` để đồng bộ họ `DUPLICATE_*` của M7/M2). Implement trả `DUPLICATE_PROFILE`.

**Side effects:** tạo `hr_profiles`; `audit_logs` action=`HR_PROFILE_CREATE` (detail = user_id, job_title — KHÔNG PII/lương).

---

### 3. GET /api/v1/hr-profiles/:userId
**Mục đích:** Chi tiết hồ sơ (FR-HR-001). Strip lương/HĐ/PII theo quyền (BR-HR-002).
**Auth:** Bearer JWT | **Roles:** admin, leader, accountant; staff CHỈ khi `:userId == sub` | **Scope:** self/toàn HT | **Rate limit:** 60/phút

**Response 200 — người gọi = staff xem CHÍNH MÌNH (`:userId == sub`):** CÓ đủ lương/HĐ/PII của mình (giống object #1).

**Response 200 — người gọi = staff xem NGƯỜI KHÁC:** → 403 `FORBIDDEN` mặc định (OQ#1b chốt: staff chỉ xem hồ sơ của chính mình; không xem hồ sơ người khác). Nếu KH bật xem phi-tài-chính người cùng phòng sau này → response **strip** toàn bộ `salary_*`, `contract_*`, PII:
```json
{
  "success": true,
  "data": {
    "user_id": "other-uuid",
    "full_name": "Trần Thị B",
    "department_name": "Hóa lý",
    "job_title": "KTV"
  }
}
```
> Các key `salary_grade/salary_coefficient/base_salary_amount/computed_salary_amount/salary_history/next_salary_raise_date/last_salary_raise_date/contract_*/id_number/dob/bank_account` **VẮNG MẶT hoàn toàn** (strip ở API — không trả null).

**Errors:** `PROFILE_NOT_FOUND` (404), `FORBIDDEN` (403 staff xem người khác).

---

### 4. GET /api/v1/hr-profiles/me
**Mục đích:** Hồ sơ của chính người gọi — luôn đầy đủ lương/HĐ/PII của mình (FR-HR-001). Tiện cho mọi vai trò.
**Auth:** Bearer JWT | **Roles:** mọi vai trò | **Scope:** self | **Rate limit:** 60/phút

**Response 200:** object hồ sơ đầy đủ (lương/HĐ/PII của chính mình — chính chủ luôn xem được lương mình theo BR-HR-003).
**Errors:** `PROFILE_NOT_FOUND` (404 — user chưa có hồ sơ).

---

### 5. PATCH /api/v1/hr-profiles/:userId
**Mục đích:** Cập nhật **phi-tài-chính** (chức danh, liên hệ, PII theo quyền) (FR-HR-002). Lương/HĐ tách riêng (#6/#8).
**Auth:** Bearer JWT | **Roles:** admin, accountant | **Scope:** toàn HT | **Rate limit:** 60/phút

**Request Body (≥1 field):** `job_title`, `hired_date`, `phone`, `id_number`, `dob`, `bank_account` (validation như #2).

> Nếu body chứa field lương/HĐ → **bỏ qua/từ chối** (chỉ sửa qua #6/#8). Trả `VALIDATION_ERROR` nếu gửi field lương rõ ràng (hướng dẫn dùng endpoint đúng).

**Response 200:** hồ sơ cập nhật (strip theo quyền).
**Errors:** `PROFILE_NOT_FOUND` (404), `FORBIDDEN` (403 leader/staff), `VALIDATION_ERROR` (400 body rỗng / gửi field lương).
**Side effects:** `audit_logs` action=`HR_PROFILE_UPDATE` (detail = danh sách field đã đổi — KHÔNG giá trị PII, BR-HR-024).

---

### 6. PATCH /api/v1/hr-profiles/:userId/contract
**Mục đích:** Cập nhật hợp đồng (FR-HR-003). Nguồn cho CRON-4 + tính `next_salary_raise_date` khi chưa nâng lương.
**Auth:** Bearer JWT | **Roles:** admin, accountant | **Scope:** toàn HT | **Rate limit:** 60/phút

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| contract_signed_date | date | ✅ | ISO date | Ngày ký HĐ |
| contract_type | string | ✅ | ∈ danh mục `contract_types` (#40) | Loại HĐ |
| contract_end_date | date\|null | ❌ | > contract_signed_date (nếu có); null = vô thời hạn | Ngày hết hạn |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "user_id": "user-uuid",
    "contract_signed_date": "2024-01-01",
    "contract_type": "fixed_term",
    "contract_end_date": "2026-12-31",
    "next_salary_raise_date": "2027-01-01"
  }
}
```
> `next_salary_raise_date` tự tính lại nếu chưa có `last_salary_raise_date` (base = contract_signed_date — BR-HR-005). HĐ vô thời hạn (`contract_end_date=null`) → CRON-4 bỏ qua (BR-HR-009).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | thiếu ngày ký / contract_type rỗng |
| INVALID_DATE_ORDER | 422 | contract_end_date ≤ contract_signed_date (BR-HR-007) |
| INVALID_CONTRACT_TYPE | 400 | contract_type ngoài danh mục |
| SALARY_FORBIDDEN | 403 | leader/staff (HĐ = nhóm tài chính, chỉ admin/accountant sửa) |
| PROFILE_NOT_FOUND | 404 | hồ sơ không tồn tại |

**Side effects:** lưu HĐ + tự tính `next_salary_raise_date`; `audit_logs` action=`HR_CONTRACT_UPDATE`.

---

### 7. PATCH /api/v1/hr-profiles/:userId/salary-cycle
**Mục đích:** Cấu hình chu kỳ nâng lương (FR-HR-006). Đổi → tự tính lại `next_salary_raise_date`.
**Auth:** Bearer JWT | **Roles:** admin, accountant | **Scope:** toàn HT | **Rate limit:** 60/phút

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| salary_cycle_years | int | ✅ | số nguyên ≥ 1 (default 3 — C04) | Số năm/chu kỳ |

**Response 200:** `{ "success": true, "data": { "user_id": "user-uuid", "salary_cycle_years": 2, "next_salary_raise_date": "2028-01-01" } }`

**Errors:** `INVALID_CYCLE` (400 < 1 / không nguyên), `SALARY_FORBIDDEN` (403 leader/staff), `PROFILE_NOT_FOUND` (404).
**Side effects:** tự tính lại `next_salary_raise_date`; `audit_logs` action=`HR_SALARY_CYCLE_UPDATE`.

---

### 8. POST /api/v1/hr-profiles/:userId/salary-raises
**Mục đích:** Ghi nhận nâng lương — cập nhật mức hiện hành + thêm bản ghi lịch sử (append-only) + tự tính lại `next_salary_raise_date` (FR-HR-004/005). **Endpoint nhạy cảm nhất M4.**
**Auth:** Bearer JWT | **Roles:** admin, accountant **(leader/staff → 403 `SALARY_FORBIDDEN`)** | **Scope:** toàn HT | **Rate limit:** 60/phút

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| salary_grade | string | ✅ | maxLength(20) | Bậc/ngạch mới |
| salary_coefficient | string(decimal) | ✅ | > 0, NUMERIC(6,2) | Hệ số lương mới |
| base_salary_amount | string(decimal) | ✅ | > 0, NUMERIC(14,2) | Lương cơ sở mới |
| raise_date | date | ✅ | ISO date; mặc định ≤ hôm nay (OQ#1d — không cho tương lai trừ khi KH bật) | Ngày nâng lương |
| note | string | ❌ | maxLength(255) | Số quyết định/ghi chú |

**Response 201:**
```json
{
  "success": true,
  "data": {
    "user_id": "user-uuid",
    "salary_grade": "A1.4",
    "salary_coefficient": "3.99",
    "base_salary_amount": "2340000.00",
    "computed_salary_amount": "9336600.00",
    "currency": "VND",
    "last_salary_raise_date": "2026-06-01",
    "next_salary_raise_date": "2029-06-01",
    "salary_history_id": "sh-uuid"
  }
}
```
> Tính lại: `next_salary_raise_date = raise_date + salary_cycle_years` (cộng năm an toàn năm nhuận 29/02→28/02 — BR-HR-005).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | thiếu field bắt buộc |
| INVALID_SALARY | 400 | coefficient/base ≤ 0 (BR-HR — A2) |
| SALARY_FORBIDDEN | 403 | leader/staff ghi nâng lương (OQ#1 — chỉ admin/accountant) |
| FUTURE_RAISE_NOT_ALLOWED | 422 | raise_date > hôm nay (nếu OQ#1d không cho phép) |
| PROFILE_NOT_FOUND | 404 | hồ sơ không tồn tại |

**Side effects:**
- Append 1 bản ghi `salary_history` (old_grade/old_coefficient/old_base → new_*; raise_date; by_user) — **immutable, KHÔNG có endpoint sửa/xóa** (BR-HR-008).
- Cập nhật mức lương hiện hành + `last_salary_raise_date` + tự tính `next_salary_raise_date`.
- `audit_logs` action=`HR_SALARY_RAISE` (detail = fact "đã nâng lương" + user; **KHÔNG ghi giá trị tiền** ra log/Sentry — BR-HR-024; chính sách ghi old/new vào audit.detail theo OQ#2b, nếu ghi thì chỉ trong audit không ra log).

---

### 9. GET /api/v1/hr-profiles/:userId/salary-history
**Mục đích:** Lịch sử nâng lương (FR-HR-004). Chỉ người đủ quyền xem lương + chính chủ.
**Auth:** Bearer JWT | **Roles:** admin, leader, accountant; staff CHỈ `:userId == sub` | **Scope:** self/toàn HT | **Rate limit:** 60/phút

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "sh-uuid",
      "old_grade": "A1.3", "old_coefficient": "3.66", "old_base_amount": "2340000.00",
      "new_grade": "A1.4", "new_coefficient": "3.99", "new_base_amount": "2340000.00",
      "raise_date": "2026-06-01",
      "by_user_id": "kt-uuid", "by_user_name": "Kế toán K",
      "note": "QĐ 123/2026",
      "created_at": "2026-06-01T03:00:00Z"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 2, "hasNext": false }
}
```

**Errors:** `SALARY_FORBIDDEN` (403 staff xem lịch sử người khác), `PROFILE_NOT_FOUND` (404).
> KHÔNG có POST/PATCH/DELETE trên salary-history — append-only (BR-HR-008). Sửa sai = ghi nâng lương điều chỉnh mới qua #8.

---

### 10. GET /api/v1/hr-profiles/:userId/competences
**Mục đích:** Liệt kê bằng cấp / chứng chỉ / ủy quyền thử nghiệm (FR-HR-007, §6.2).
**Auth:** Bearer JWT | **Roles:** admin, leader; staff CHỈ `:userId == sub` | **Scope:** self/toàn HT | **Rate limit:** 60/phút

> Kế toán KHÔNG quản lý năng lực (năng lực không phải tài chính, OQ#1b) → nếu accountant gọi: trả 403 `FORBIDDEN` (mặc định). Năng lực KHÔNG chứa lương.

**Query params:** `kind` (enum `degree|certificate|authorization`), `status` (enum `valid|expired`).

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "comp-uuid",
      "kind": "authorization",
      "title": "Thực hiện chỉ tiêu pH theo SOP-XX",
      "issuer": "Trưởng phòng Hóa lý",
      "issued_date": "2026-01-01",
      "expiry_date": "2027-12-31",
      "scope_detail": "Chỉ tiêu pH, phương pháp SOP-XX",
      "authorized_by_user_id": "lead-uuid",
      "authorized_by_name": "Trưởng nhóm T",
      "is_expired": false,
      "attachment_id": "att-uuid"
    }
  ]
}
```

**Errors:** `PROFILE_NOT_FOUND` (404), `FORBIDDEN` (403 staff xem người khác / accountant).

---

### 11. POST /api/v1/hr-profiles/:userId/competences
**Mục đích:** Thêm mục năng lực (FR-HR-007). Kiểm soát thay đổi VILAS §6.2/§8.4.
**Auth:** Bearer JWT | **Roles:** admin, leader | **Scope:** toàn HT | **Rate limit:** 60/phút

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| kind | enum | ✅ | degree\|certificate\|authorization | Loại năng lực |
| title | string | ✅ | maxLength(255) | Tên bằng/chứng chỉ/ủy quyền |
| issuer | string | ❌ | maxLength(255) | Nơi cấp |
| issued_date | date | ❌ | ISO date | Ngày cấp |
| expiry_date | date\|null | ❌ | > issued_date (nếu có) | Ngày hết hạn |
| scope_detail | string | ⚠️ (bắt buộc khi kind=authorization) | maxLength(500) | Chỉ tiêu/phương pháp được ủy quyền |
| authorized_by | uuid | ⚠️ (bắt buộc khi kind=authorization) | user tồn tại | Người ủy quyền |

**Response 201:** object năng lực như item #10.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | thiếu title / kind sai / thiếu scope_detail khi authorization |
| INVALID_DATE_ORDER | 422 | expiry_date ≤ issued_date (ủy quyền: from > to) |
| PROFILE_NOT_FOUND | 404 | hồ sơ không tồn tại |
| FORBIDDEN | 403 | accountant/staff |

**Side effects:** tạo `competences`; `audit_logs` action=`HR_COMPETENCE_CHANGE` (BR-HR-004 — kiểm soát thay đổi bắt buộc).

---

### 12. PATCH /api/v1/competences/:id · 13. DELETE /api/v1/competences/:id
**Mục đích:** Sửa/xóa mục năng lực (FR-HR-007).
**Auth:** Bearer JWT | **Roles:** admin, leader | **Rate limit:** 60/phút

- PATCH body (≥1 field): như #11. Response 200 object năng lực.
- DELETE: Response 204.

**Errors:** `COMPETENCE_NOT_FOUND` (404), `INVALID_DATE_ORDER` (422), `FORBIDDEN` (403).
**Side effects:** `audit_logs` action=`HR_COMPETENCE_CHANGE` (mọi sửa/xóa năng lực phải audit — §8.4, BR-HR-004).

---

### 14. POST /api/v1/competences/:id/attachments
**Mục đích:** Upload minh chứng (scan bằng/chứng chỉ/quyết định ủy quyền) (FR-HR-007).
**Auth:** Bearer JWT | **Roles:** admin, leader | **Rate limit:** 60/phút | **Content-Type:** multipart/form-data

**Form fields:** `file` (binary). Validate: MIME thực ∈ {application/pdf, image/png, image/jpeg}; ≤ giới hạn (OQ#12 — mặc định 20MB, đồng bộ M2).

**Response 201:** `{ "success": true, "data": { "attachment_id": "att-uuid", "owner_type": "hr_profile", "file_name": "bang-thac-si.pdf" } }`
> Lưu MinIO (`file_key`); `attachments(owner_type='hr_profile')`. Tải file qua M7 #30 (`GET /api/v1/attachments/:id` → presigned URL, RBAC theo owner).

**Errors:** `INVALID_FILE_TYPE` (422), `FILE_TOO_LARGE` (422), `COMPETENCE_NOT_FOUND` (404), `FORBIDDEN` (403).

---

### 15. GET /api/v1/hr-profiles/:userId/competence-summary
**Mục đích:** Hồ sơ năng lực tổng hợp (bằng + chứng chỉ + ủy quyền + thành tích) phục vụ đánh giá VILAS §6.2 (FR-HR-019). **KHÔNG chứa lương** (tách field-level).
**Auth:** Bearer JWT | **Roles:** admin, leader; staff CHỈ `:userId == sub` | **Scope:** self/toàn HT | **Rate limit:** 60/phút

**Response 200:**
```json
{
  "success": true,
  "data": {
    "user_id": "user-uuid",
    "full_name": "Nguyễn Văn A",
    "department_name": "Hóa lý",
    "job_title": "KTV chính",
    "degrees": [ { "title": "Thạc sĩ Hóa phân tích", "issuer": "ĐH X", "issued_date": "2020-06-01" } ],
    "certificates": [ { "title": "Chứng chỉ ISO 17025", "expiry_date": "2025-01-01", "is_expired": true } ],
    "authorizations": [ { "title": "Chỉ tiêu pH SOP-XX", "expiry_date": "2027-12-31", "is_expired": false } ],
    "research_summary": { "projects": 2, "publications": 3, "patents": 0, "mentorships": 4 }
  }
}
```
> Tuyệt đối KHÔNG có key lương trong response này (AC3 FR-HR-019).

**Errors:** `PROFILE_NOT_FOUND` (404), `FORBIDDEN` (403 staff xem người khác).

---

### 16. GET /api/v1/hr-profiles/:userId/competence-summary.pdf
**Mục đích:** Xuất PDF hồ sơ năng lực (§6.2) — minh chứng VILAS (FR-HR-020).
**Auth:** Bearer JWT | **Roles:** admin, leader; staff CHỈ `:userId == sub` | **Scope:** self/toàn HT | **Rate limit:** 10/phút

**Response 200:** `application/pdf` (file binary, không bọc envelope JSON). PDF chứa bằng/chứng chỉ/ủy quyền/thành tích — **KHÔNG lương**.
**Errors:** `PROFILE_NOT_FOUND` (404), `FORBIDDEN` (403).
**Side effects:** `audit_logs` action=`HR_COMPETENCE_EXPORT`.

---

### 17. GET /api/v1/research-projects
**Mục đích:** Liệt kê + lọc đề tài NCKH (FR-HR-010). Staff scope `own` (chỉ đề tài mình là thành viên/chủ nhiệm).
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own) **(accountant → 403)** | **Scope:** own/all | **Rate limit:** 60/phút

**Query params:** `q` (string maxLength 100, tên), `department_id` (uuid), `level` (string ∈ project_levels), `year` (int — đề tài hoạt động trong năm), `lead_user_id` (uuid), `status` (string), `page/limit`.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "proj-uuid",
      "title": "Phát triển phương pháp đo X",
      "level": "university",
      "lead_user_id": "userA-uuid",
      "lead_user_name": "Nguyễn Văn A",
      "department_id": "dept-uuid",
      "department_name": "Hóa lý",
      "start_date": "2026-01-01",
      "end_date": "2028-12-31",
      "status": "in_progress",
      "member_count": 3
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 5, "hasNext": false }
}
```
> Staff: backend ép filter chỉ đề tài có `proj.id IN (project_members WHERE user_id = sub)` — không trả đề tài người khác (BR-HR-023).

**Errors:** `FORBIDDEN` (403 accountant), `VALIDATION_ERROR` (400).

---

### 18. POST /api/v1/research-projects
**Mục đích:** Tạo đề tài + thành viên n-n (FR-HR-010).
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own — phải tự là thành viên) **(accountant → 403)** | **Scope:** own/all | **Rate limit:** 60/phút

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| title | string | ✅ | maxLength(500), trim non-empty | Tên đề tài |
| level | string | ✅ | ∈ danh mục `project_levels` (#38) | Cấp đề tài |
| lead_user_id | uuid | ✅ | user tồn tại; có trong members | Chủ nhiệm (đúng 1) |
| department_id | uuid | ❌ | tồn tại | Phòng (suy từ lead nếu trống) |
| start_date | date | ❌ | ISO date | Bắt đầu |
| end_date | date | ❌ | > start_date | Kết thúc |
| status | string | ❌ | maxLength(30), default `in_progress` | Trạng thái |
| members | array | ✅ | ≥1; mỗi item { user_id\|external_name, role_in_project }; không trùng user | Thành viên n-n |

> **members item (OQ#8c):** mỗi item HOẶC `user_id` (FK→users) HOẶC `external_name` (free-text người ngoài hệ thống) — không cả hai/không cả hai null (`INVALID_AUTHOR`). `role_in_project` ∈ {lead, member, secretary}. `lead_user_id` PHẢI có trong members.
> **Staff own:** `sub` PHẢI là một `user_id` trong members; nếu không → 403.

**Response 201:** object đề tài + mảng `members`.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | thiếu title / field sai |
| LEAD_REQUIRED | 400 | thiếu lead_user_id / lead không trong members (BR-HR-016) |
| INVALID_PROJECT_LEVEL | 400 | level ngoài danh mục (BR-HR-015) |
| INVALID_DATE_ORDER | 422 | end_date < start_date |
| INVALID_AUTHOR | 422 | member item thiếu cả user_id lẫn external_name / có cả hai |
| DUPLICATE_MEMBER | 409 | một user xuất hiện 2 lần (BR-HR-016) |
| USER_NOT_FOUND | 404 | user_id thành viên không tồn tại |
| FORBIDDEN | 403 | accountant / staff không là thành viên |

**Side effects:** tạo `research_projects` + `project_members`; `audit_logs` action=`RESEARCH_PROJECT_CREATE`.

---

### 19. GET /api/v1/research-projects/:id · 20. PATCH · 21. DELETE
**Mục đích:** Chi tiết / cập nhật partial / xóa đề tài (FR-HR-010).
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own — chỉ đề tài mình là thành viên) | **Rate limit:** 60/phút

- **GET :id** → object đề tài + mảng `members` (mỗi member: `user_id|external_name`, `name`, `role_in_project`).
- **PATCH :id** (≥1 field): `title`, `level`, `lead_user_id`, `department_id`, `start_date`, `end_date`, `status`. Response 200.
- **DELETE :id** → 204.

**Errors:** `PROJECT_NOT_FOUND` (404), `LEAD_REQUIRED`/`INVALID_PROJECT_LEVEL`/`INVALID_DATE_ORDER` (như #18), `FORBIDDEN` (403 ngoài scope).
**Side effects:** `audit_logs` action=`RESEARCH_PROJECT_UPDATE`/`RESEARCH_PROJECT_DELETE`.

---

### 22. PUT /api/v1/research-projects/:id/members
**Mục đích:** Thay TOÀN BỘ danh sách thành viên (full replace — PUT) (FR-HR-010).
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own) | **Rate limit:** 60/phút

**Request Body:** `{ "members": [ { "user_id"|"external_name", "role_in_project" } ] }` — như #18 (lead phải nằm trong danh sách).
**Response 200:** object đề tài + `members` mới.
**Errors:** `LEAD_REQUIRED` (400 — gỡ lead khỏi members), `DUPLICATE_MEMBER` (409), `INVALID_AUTHOR` (422), `PROJECT_NOT_FOUND` (404), `FORBIDDEN` (403).
**Side effects:** xóa + thêm lại `project_members` (atomic); `audit_logs` action=`RESEARCH_PROJECT_MEMBERS_UPDATE`.

---

### 23. GET /api/v1/publications
**Mục đích:** Liệt kê + lọc bài báo/sáng chế (FR-HR-011/012). Staff scope `own` (mình là tác giả).
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own) **(accountant → 403)** | **Scope:** own/all | **Rate limit:** 60/phút

**Query params:** `q` (string maxLength 100), `type` (enum `paper|patent`), `year` (int), `index_code` (string ∈ pub_indexes), `department_id` (uuid), `author_user_id` (uuid), `page/limit`.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "pub-uuid",
      "type": "paper",
      "title": "Method X for trace metal analysis",
      "journal": "J. Anal. Chem.",
      "year": 2025,
      "doi": "10.1000/abc123",
      "index_code": "scopus_q1",
      "department_id": "dept-uuid",
      "department_name": "Hóa lý",
      "patent_no": null,
      "issuing_authority": null,
      "authors": [
        { "user_id": "userA-uuid", "name": "Nguyễn Văn A", "author_order": 1, "is_corresponding": true },
        { "user_id": null, "external_name": "GS. Smith (ĐH ngoài)", "author_order": 2, "is_corresponding": false }
      ]
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 3, "hasNext": false }
}
```

**Errors:** `FORBIDDEN` (403 accountant), `VALIDATION_ERROR` (400).

---

### 24. POST /api/v1/publications
**Mục đích:** Tạo bài báo (`type=paper`) hoặc sáng chế/giải pháp (`type=patent`) + tác giả n-n + thứ tự (FR-HR-011/012).
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own — phải tự là tác giả) **(accountant → 403)** | **Scope:** own/all | **Rate limit:** 60/phút

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| type | enum | ✅ | paper\|patent | Loại công bố |
| title | string | ✅ | maxLength(500) | Tên bài/sáng chế |
| journal | string | ⚠️ (paper) | maxLength(255) | Tạp chí/hội nghị |
| year | int | ✅ | 1900..(năm hiện tại+1) | Năm xuất bản/cấp |
| doi | string | ❌ | regex `^10\.\d{4,}/.+` (nếu có) | DOI (paper) |
| index_code | string | ⚠️ (paper) | ∈ danh mục `pub_indexes` (#39) | Chỉ số bài báo |
| patent_no | string | ⚠️ (patent) | maxLength(50), unique khi type=patent | Số bằng (patent) |
| issuing_authority | string | ⚠️ (patent) | maxLength(255) | Cơ quan cấp (patent) |
| department_id | uuid | ❌ | tồn tại | Phòng gắn thành tích |
| authors | array | ✅ | ≥1; item { user_id\|external_name, author_order, is_corresponding } | Tác giả n-n |

> **authors (OQ#8c):** mỗi item HOẶC `user_id` HOẶC `external_name`. `author_order` **duy nhất trong bài** (BR-HR-018). Staff own: `sub` phải là 1 tác giả nội bộ.

**Response 201:** object publication + mảng `authors` (như #23).

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | thiếu title/type/year / DOI sai định dạng / thiếu journal khi paper / thiếu patent_no khi patent |
| INVALID_INDEX | 400 | index_code ngoài danh mục (BR-HR-017) |
| DUPLICATE_AUTHOR_ORDER | 422 | author_order trùng trong cùng bài (BR-HR-018) |
| INVALID_AUTHOR | 422 | author item thiếu cả user_id lẫn external_name / có cả hai |
| DUPLICATE_PATENT_NO | 409 | patent_no đã tồn tại (BR-HR-019) |
| USER_NOT_FOUND | 404 | user_id tác giả không tồn tại |
| FORBIDDEN | 403 | accountant / staff không là tác giả |

**Side effects:** tạo `publications` + `publication_authors`; `audit_logs` action=`RESEARCH_PUBLICATION_CREATE` (paper) / `RESEARCH_PATENT_CREATE` (patent).

---

### 25. GET /api/v1/publications/:id · 26. PATCH · 27. DELETE
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own) | **Rate limit:** 60/phút
- **GET :id** → object publication + `authors`.
- **PATCH :id** (≥1 field): các field #24 trừ `authors` (đổi tác giả qua #28). Response 200.
- **DELETE :id** → 204.

**Errors:** `PUBLICATION_NOT_FOUND` (404), `INVALID_INDEX`/`DUPLICATE_PATENT_NO` (như #24), `FORBIDDEN` (403).
**Side effects:** `audit_logs` action=`RESEARCH_PUBLICATION_UPDATE`/`_DELETE`.

---

### 28. PUT /api/v1/publications/:id/authors
**Mục đích:** Thay toàn bộ danh sách tác giả + thứ tự (full replace) (FR-HR-011).
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own) | **Rate limit:** 60/phút

**Request Body:** `{ "authors": [ { "user_id"|"external_name", "author_order", "is_corresponding" } ] }`.
**Response 200:** object publication + `authors` mới.
**Errors:** `DUPLICATE_AUTHOR_ORDER` (422), `INVALID_AUTHOR` (422), `PUBLICATION_NOT_FOUND` (404), `FORBIDDEN` (403).
**Side effects:** xóa + thêm lại `publication_authors` (atomic); `audit_logs` action=`RESEARCH_PUBLICATION_AUTHORS_UPDATE`.

---

### 29. POST /api/v1/publications/:id/attachments
**Mục đích:** Upload minh chứng bài báo/sáng chế (FR-HR-011). multipart như #14.
**Auth:** Bearer JWT | **Roles:** admin, leader, staff(own) | **Rate limit:** 60/phút
**Response 201:** `{ "success": true, "data": { "attachment_id": "att-uuid", "owner_type": "publication" } }`
**Errors:** `INVALID_FILE_TYPE` (422), `FILE_TOO_LARGE` (422), `PUBLICATION_NOT_FOUND` (404), `FORBIDDEN` (403).

---

### 30. GET /api/v1/student-mentorships · 31. POST · 32. PATCH/DELETE :id
**Mục đích:** CRUD hướng dẫn SV (FR-HR-014).
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own — mentor = chính mình) **(accountant → 403)** | **Scope:** own/all | **Rate limit:** 60/phút

**Query (GET):** `mentor_id` (uuid), `year` (int), `type` (string ∈ mentorship_types), `department_id` (uuid), `page/limit`.

**POST Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| mentor_id | uuid | ✅ | user tồn tại; staff: = sub | Người hướng dẫn |
| student_name | string | ✅ | maxLength(255) | Tên SV |
| topic | string | ❌ | maxLength(500) | Đề tài |
| year | int | ✅ | 1900..(năm hiện tại+1) | Năm |
| type | string | ✅ | ∈ danh mục `mentorship_types` (#41) | Loại hướng dẫn |

> `department_id` suy từ mentor. Staff: `mentor_id` PHẢI = `sub` (khai của mình) — gắn người khác làm mentor → 403.

**Response 201:** object hướng dẫn SV.

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| VALIDATION_ERROR | 400 | thiếu student_name/year |
| INVALID_MENTORSHIP_TYPE | 400 | type ngoài danh mục (BR-HR-020) |
| MENTORSHIP_NOT_FOUND | 404 | (PATCH/DELETE) không tồn tại |
| FORBIDDEN | 403 | accountant / staff khai cho người khác |

**Side effects:** `audit_logs` action=`RESEARCH_MENTORSHIP_CREATE`/`_UPDATE`/`_DELETE`.

---

### 33. GET /api/v1/lab-registrations
**Mục đích:** Liệt kê + lọc lượt SV đăng ký lab theo status (FR-HR-015).
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own — mentor = mình) **(accountant → 403)** | **Scope:** own/all | **Rate limit:** 60/phút

**Query:** `status` (enum `pending|approved|rejected`), `mentor_id` (uuid), `department_id` (uuid), `page/limit`.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "reg-uuid",
      "student_name": "Lê Văn C",
      "mentor_id": "userA-uuid",
      "mentor_name": "Nguyễn Văn A",
      "registered_from": "2026-07-01",
      "registered_to": "2026-07-31",
      "purpose": "Thực tập dùng thiết bị HPLC",
      "status": "pending",
      "department_id": "dept-uuid",
      "decided_by_user_id": null,
      "decided_at": null,
      "created_at": "2026-06-20T03:00:00Z"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 12, "hasNext": false }
}
```

**Errors:** `FORBIDDEN` (403 accountant), `VALIDATION_ERROR` (400).

---

### 34a. POST /api/v1/lab-registrations
**Mục đích:** Tạo lượt đăng ký → `status=pending` (FR-HR-015, OQ#8 = có duyệt).
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own — mentor = mình) | **Scope:** own/all | **Rate limit:** 60/phút

**Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| student_name | string | ✅ | maxLength(255) | Tên SV đăng ký |
| mentor_id | uuid | ✅ | user tồn tại; staff: = sub | Người hướng dẫn |
| registered_from | date | ✅ | ISO date | Từ ngày |
| registered_to | date\|null | ❌ | ≥ registered_from | Đến ngày |
| purpose | string | ✅ | maxLength(500) | Mục đích |

**Response 201:** object lượt đăng ký với `status=pending`.
**Errors:** `VALIDATION_ERROR` (400), `INVALID_DATE_ORDER` (422 registered_to < from), `FORBIDDEN` (403 accountant / staff mentor≠mình).
**Side effects:** tạo `lab_registrations` (status=pending); `audit_logs` action=`LAB_REGISTRATION_CREATE`.

---

### 34b. POST /api/v1/lab-registrations/:id/approve · 34c. /reject
**Mục đích:** Duyệt (→approved) / từ chối (→rejected) lượt đăng ký (FR-HR-015, OQ#8 workflow).
**Auth:** Bearer JWT | **Roles:** admin, leader; **mentor của lượt** (mentor_id == sub); **trưởng nhóm phòng của mentor** (`is_dept_lead` của phòng mentor) | **Rate limit:** 60/phút

**Request Body:** `{ "reason": "..." }` (optional với approve; khuyến nghị với reject — maxLength 255).

**Response 200:**
```json
{
  "success": true,
  "data": { "id": "reg-uuid", "status": "approved", "decided_by_user_id": "lead-uuid", "decided_at": "2026-06-20T04:00:00Z" }
}
```

**Errors:**

| Code | HTTP | Điều kiện |
|------|------|-----------|
| REGISTRATION_NOT_FOUND | 404 | lượt không tồn tại |
| REGISTRATION_ALREADY_DECIDED | 409 | lượt đã `approved`/`rejected` (không quyết lại — OQ#8) |
| FORBIDDEN | 403 | không phải admin/leader/mentor/trưởng nhóm phòng mentor |

**Side effects:** cập nhật `status` + `decided_by_user_id` + `decided_at`; chỉ lượt `approved` được tính thống kê (#37); `audit_logs` action=`LAB_REGISTRATION_APPROVE`/`LAB_REGISTRATION_REJECT`.

---

### 35. /api/v1/teaching-courses[/:id] — CRUD môn giảng dạy (FR-HR-016)
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own — user = mình) **(accountant → 403)** | **Scope:** own/all | **Rate limit:** 60/phút

**GET query:** `user_id` (uuid), `year` (int), `semester` (string), `department_id` (uuid), `page/limit`.

**POST Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| user_id | uuid | ✅ | user tồn tại; staff: = sub | Người phụ trách |
| course_name | string | ✅ | maxLength(255) | Tên môn |
| semester | string | ✅ | maxLength(20) | Học kỳ |
| year | int | ✅ | 1900..(năm hiện tại+1) | Năm học |

**Response 201:** object môn học. **Errors:** `VALIDATION_ERROR` (400), `DUPLICATE_COURSE` (409 trùng user+môn+kỳ+năm — BR-HR-020), `TEACHING_COURSE_NOT_FOUND` (404), `FORBIDDEN` (403 accountant / staff khai cho người khác).
**Side effects:** `audit_logs` action=`TEACHING_COURSE_CREATE`/`_UPDATE`/`_DELETE`.

---

### 36. /api/v1/community-services[/:id] — CRUD phục vụ cộng đồng (FR-HR-017)
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own — performer = mình) **(accountant → 403)** | **Scope:** own/all | **Rate limit:** 60/phút

**GET query:** `performer_user_id` (uuid), `year`/`from`/`to` (date range trên performed_at), `department_id` (uuid), `page/limit`.

**POST Request Body:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| content | string | ✅ | maxLength(1000) | Nội dung hoạt động |
| performed_at | date | ✅ | ISO date | Thời gian thực hiện |
| host | string | ❌ | maxLength(255) | Đơn vị/tổ chức chủ trì |
| performer_user_id | uuid | ✅ | user tồn tại; staff: = sub | Người thực hiện |

**Response 201:** object hoạt động. **Errors:** `VALIDATION_ERROR` (400 thiếu content/performer), `COMMUNITY_SERVICE_NOT_FOUND` (404), `FORBIDDEN` (403 accountant / staff khai cho người khác).
**Side effects:** `audit_logs` action=`COMMUNITY_SERVICE_CREATE`/`_UPDATE`/`_DELETE`.

---

### 37. GET /api/v1/research-achievements/stats
**Mục đích:** Thống kê tổng hợp thành tích theo cá nhân / phòng / khoảng thời gian phục vụ báo cáo năng lực §6.2 (FR-HR-018).
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own) **(accountant → 403)** | **Scope:** own/all | **Rate limit:** 10/phút

**Query params:**

| Field | Type | Required | Validation | Mô tả |
|-------|------|----------|-----------|-------|
| group_by | enum | ✅ | individual\|department | Chiều tổng hợp |
| user_id | uuid | ⚠️ (khi group_by=individual) | — | Cá nhân (staff: bị ép = sub) |
| department_id | uuid | ⚠️ (khi group_by=department) | — | Phòng |
| from | date | ❌ | ≤ to | Đầu khoảng |
| to | date | ❌ | ≥ from | Cuối khoảng |
| level | string | ❌ | ∈ project_levels | Lọc cấp đề tài |
| index_code | string | ❌ | ∈ pub_indexes | Lọc chỉ số bài báo |

> **Staff scope `own`:** mọi `user_id`/`department_id` query bị **ép về dữ liệu của chính `sub`** (BR-HR-023) — staff không nhận số liệu người/phòng khác. **KHÔNG trả lương** trong thống kê (chỉ đếm thành tích).

**Response 200:**
```json
{
  "success": true,
  "data": {
    "group_by": "department",
    "department_id": "dept-uuid",
    "department_name": "Hóa lý",
    "period": { "from": "2025-01-01", "to": "2025-12-31" },
    "projects": { "total": 6, "by_level": { "university": 4, "ministry": 2 } },
    "publications": { "total": 9, "by_index": { "scopus_q1": 3, "isi": 2, "domestic": 4 } },
    "patents": 1,
    "mentorships": 12,
    "lab_registrations_approved": 8,
    "teaching_courses": 15,
    "community_services": 4
  }
}
```
> `lab_registrations_approved` chỉ đếm lượt `approved` (BR-HR-021). Thành tích không gắn phòng gom nhóm "Không gắn phòng" khi group_by=department (BR-HR-022).

**Errors:** `INVALID_DATE_RANGE` (400 from > to), `FORBIDDEN` (403 accountant), `VALIDATION_ERROR` (400 thiếu group_by).

---

### 37b. GET /api/v1/research-achievements/stats.xlsx
**Mục đích:** Xuất Excel báo cáo năng lực §6.2 (FR-HR-018).
**Auth:** Bearer JWT | **Roles:** admin, leader (all); staff (own) | **Scope:** own/all | **Rate limit:** 10/phút
**Query:** giống #37. **Response 200:** `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (file binary).
**Errors:** như #37.
**Side effects:** `audit_logs` action=`RESEARCH_REPORT_EXPORT` (đếm lượt tải — R15).

---

### 38–41. Danh mục (GET — đọc, đã seed)
**Auth:** Bearer JWT | **Rate limit:** 60/phút

| # | Path | Roles | Response data (mảng) |
|---|------|-------|----------------------|
| 38 | `/api/v1/catalogs/project-levels` | mọi vai trò | `[{ "code": "university", "label": "Cấp trường" }, { "code": "ministry", "label": "Cấp bộ" }, { "code": "national", "label": "Cấp nhà nước" }]` |
| 39 | `/api/v1/catalogs/pub-indexes` | mọi vai trò | `[{ "code": "isi", "label": "ISI" }, { "code": "scopus_q1", "label": "Scopus Q1" }, { "code": "domestic", "label": "Trong nước" }]` |
| 40 | `/api/v1/catalogs/contract-types` | admin, leader, accountant | `[{ "code": "probation", "label": "Thử việc" }, { "code": "fixed_term", "label": "Xác định thời hạn" }, { "code": "indefinite", "label": "Không xác định thời hạn" }]` |
| 41 | `/api/v1/catalogs/mentorship-types` | mọi vai trò | `[{ "code": "bachelor_thesis", "label": "Khóa luận ĐH" }, { "code": "master_thesis", "label": "Luận văn ThS" }, { "code": "phd_thesis", "label": "Luận án TS" }, { "code": "student_research", "label": "NCKH SV" }]` |

> Giá trị cụ thể do KH chốt (OQ#3/#5/#6/#7) — trên là mặc định đã seed. `contract-types` (#40) giới hạn vai trò tài chính vì gắn nghiệp vụ HĐ.
**Errors:** `UNAUTHORIZED` (401), `FORBIDDEN` (403 — #40 với staff/accountant... thực tế #40 cho admin/leader/accountant).

---

### 42. POST /api/v1/admin/crons/salary-raise-due/run · 43. /contract-expiry/run
**Mục đích:** Chạy thủ công CRON-3 (nhắc nâng lương 15/7/3 ngày) / CRON-4 (nhắc hết hạn HĐ 30/15/7 ngày) để test/vận hành (FR-HR-008/009).
**Auth:** Bearer JWT | **Roles:** admin | **Scope:** toàn HT | **Rate limit:** 6/phút

**Response 200:** `{ "success": true, "data": { "scanned": 38, "notifications_created": 4, "skipped_duplicate": 1 } }`
**Errors:** `FORBIDDEN` (403 non-admin).
**Side effects:**
- **CRON-3:** quét `next_salary_raise_date` = hôm nay+15/+7/+3 → tạo `notifications` (type=`SALARY_RAISE_DUE`, ref_type=`hr_profile`, ref_id=user_id) cho **HR (admin/leader/accountant có `hr:manage`) + chính nhân sự + lãnh đạo**; chống trùng (hồ sơ × mốc × ngày qua `idx_notif_ref` — BR-HR-013). Bỏ qua `next_salary_raise_date=NULL` (BR-HR-010).
- **CRON-4:** quét `contract_end_date` = hôm nay+30/+15/+7 → `notifications` (type=`CONTRACT_EXPIRY`) cho HR (+ nhân sự theo OQ#10); bỏ qua HĐ vô thời hạn (BR-HR-009).
- Redis lock chống chạy trùng; `audit_logs` action=`CRON_SALARY_RAISE_RUN`/`CRON_CONTRACT_EXPIRY_RUN`.

---

## 3. Danh mục Error Codes M4 (nhất quán M1/M2/M7)

| Code | HTTP | Ý nghĩa | Endpoint |
|------|------|---------|----------|
| `UNAUTHORIZED` | 401 | Thiếu/sai access token (M7) | mọi |
| `FORBIDDEN` | 403 | Thiếu quyền / sai phạm vi / sai scope (vd accountant gọi research, staff list nhân sự) | nhiều |
| `SALARY_FORBIDDEN` | 403 | KHÔNG được sửa/đọc lương-HĐ (leader/staff sửa lương; staff xem lương người khác) | #6/#7/#8/#9 |
| `VALIDATION_ERROR` | 400 | Sai/thiếu input | mọi ghi |
| `PROFILE_NOT_FOUND` | 404 | Hồ sơ nhân sự không tồn tại | #3/#5–#9/#15/#16 |
| `DUPLICATE_PROFILE` | 409 | User đã có hồ sơ (1-1 — alias `HR_PROFILE_EXISTS`) | #2 |
| `USER_NOT_FOUND` | 404 | user_id (gắn hồ sơ/tác giả/thành viên) không tồn tại | #2/#18/#24/#30 |
| `INVALID_DATE_ORDER` | 422 | Ngày kết thúc ≤ ngày bắt đầu (HĐ/đề tài/ủy quyền/đăng ký) | #6/#11/#18/#34a |
| `INVALID_CONTRACT_TYPE` | 400 | contract_type ngoài danh mục | #6 |
| `INVALID_CYCLE` | 400 | salary_cycle_years < 1 / không nguyên | #7 |
| `INVALID_SALARY` | 400 | hệ số/lương cơ sở ≤ 0 | #8 |
| `FUTURE_RAISE_NOT_ALLOWED` | 422 | raise_date trong tương lai (nếu OQ#1d không cho) | #8 |
| `COMPETENCE_NOT_FOUND` | 404 | Mục năng lực không tồn tại | #12/#13/#14 |
| `INVALID_FILE_TYPE` | 422 | File minh chứng sai loại (MIME) | #14/#29 |
| `FILE_TOO_LARGE` | 422 | File vượt giới hạn (OQ#12 ~20MB) | #14/#29 |
| `PROJECT_NOT_FOUND` | 404 | Đề tài không tồn tại | #19–#22 |
| `LEAD_REQUIRED` | 400 | Thiếu chủ nhiệm / lead không trong members | #18/#20/#22 |
| `INVALID_PROJECT_LEVEL` | 400 | Cấp đề tài ngoài danh mục | #18/#20 |
| `DUPLICATE_MEMBER` | 409 | Một user là thành viên 2 lần trong đề tài | #18/#22 |
| `INVALID_AUTHOR` | 422 | Tác giả/thành viên thiếu cả user_id lẫn external_name, hoặc có cả hai | #18/#22/#24/#28 |
| `PUBLICATION_NOT_FOUND` | 404 | Bài báo/sáng chế không tồn tại | #25–#29 |
| `INVALID_INDEX` | 400 | Chỉ số bài báo ngoài danh mục | #24/#26 |
| `DUPLICATE_AUTHOR_ORDER` | 422 | author_order trùng trong cùng bài | #24/#28 |
| `DUPLICATE_PATENT_NO` | 409 | Số bằng sáng chế đã tồn tại | #24/#26 |
| `MENTORSHIP_NOT_FOUND` | 404 | Bản ghi hướng dẫn SV không tồn tại | #32 |
| `INVALID_MENTORSHIP_TYPE` | 400 | Loại hướng dẫn ngoài danh mục | #31 |
| `REGISTRATION_NOT_FOUND` | 404 | Lượt đăng ký lab không tồn tại | #34b/#34c |
| `REGISTRATION_ALREADY_DECIDED` | 409 | Lượt đã approved/rejected — không quyết lại | #34b/#34c |
| `TEACHING_COURSE_NOT_FOUND` | 404 | Môn học không tồn tại | #35 |
| `DUPLICATE_COURSE` | 409 | Trùng user+môn+kỳ+năm | #35 |
| `COMMUNITY_SERVICE_NOT_FOUND` | 404 | Hoạt động cộng đồng không tồn tại | #36 |
| `INVALID_DATE_RANGE` | 400 | from > to (thống kê) | #37/#37b |
| `RATE_LIMIT_EXCEEDED` | 429 | Vượt rate limit | mọi |
| `INTERNAL_ERROR` | 500 | Lỗi server (không lộ stack — M7 §0.8) | mọi |

**Ví dụ error `SALARY_FORBIDDEN` (leader ghi nâng lương):**
```json
{
  "success": false,
  "error": {
    "code": "SALARY_FORBIDDEN",
    "message": "Bạn không có quyền điều chỉnh lương. Chỉ Kế toán và Quản trị viên được ghi nhận nâng lương.",
    "details": [{ "field": "salary", "required_roles": ["admin", "accountant"] }],
    "correlationId": "c1f2..."
  }
}
```

**Ví dụ error `INVALID_AUTHOR`:**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_AUTHOR",
    "message": "Mỗi tác giả phải là người nội bộ (user_id) HOẶC tên người ngoài hệ thống (external_name), không được cả hai hay để trống.",
    "details": [{ "field": "authors[1]", "message": "thiếu cả user_id và external_name" }],
    "correlationId": "c1f2..."
  }
}
```

---

## 4. Ghi chú RBAC field-level lương & workflow đăng ký lab (chi tiết)

### 4.1 Field-level lương — ma trận đầy đủ (BR-HR-002/003, OQ#1+OQ#2)

| Hành động | admin | leader | accountant | staff (của mình) | staff (người khác) |
|-----------|-------|--------|-----------|------------------|--------------------|
| Đọc lương (`salary_*`, `salary_history`, `next/last_raise_date`) | ✅ | ✅ (xem) | ✅ | ✅ | ❌ strip |
| Sửa lương / ghi nâng lương (#8) | ✅ | ❌ 403 | ✅ | ❌ 403 | ❌ 403 |
| Sửa chu kỳ lương (#7) | ✅ | ❌ 403 | ✅ | ❌ 403 | ❌ |
| Đọc hợp đồng (`contract_*`) | ✅ | ✅ | ✅ | ✅ | ❌ strip |
| Sửa hợp đồng (#6) | ✅ | ❌ 403 | ✅ | ❌ 403 | ❌ |
| Đọc PII (`id_number`, `dob`, `bank_account`) | ✅ | ❌ strip | ✅ | ✅ | ❌ strip |

**Cơ chế strip (giống M2 BR-CHEM-022):** tầng API quyết định strip theo `(role, item.user_id == sub)`. Trong list (#1), mỗi item được đánh giá độc lập. Tuyệt đối KHÔNG dựa vào FE ẩn — kiểm thử NFR-SEC-HR-001 (4 vai trò × mọi endpoint, 0 rò rỉ).

**Điểm khác M2 cần chú ý:** M2 có 3 vai trò tài chính (admin/leader/accountant) đọc giá; staff KTV không đọc giá kể cả của mình. **M4 thêm chiều "của chính mình"**: staff đọc được lương/HĐ/PII CỦA CHÍNH MÌNH (chính chủ) — phức tạp hơn M2 một bậc. Đây là điểm dễ sai nhất: strip phải so `item.user_id == sub`, không chỉ so `role`.

### 4.2 Workflow đăng ký lab (OQ#8 = có duyệt)
```
[staff/leader/admin tạo] → status=pending
        │
        ├─ approve (admin | leader | mentor của lượt | trưởng nhóm phòng mentor) → approved → tính thống kê
        └─ reject  (cùng nhóm trên) → rejected → KHÔNG tính thống kê
        │
        └─ (đã approved/rejected) → approve/reject lại → 409 REGISTRATION_ALREADY_DECIDED
```
Người duyệt = `is_dept_lead` của phòng mentor (claim M7) HOẶC mentor chính lượt HOẶC admin/leader. Chỉ `approved` vào số đếm #37.

### 4.3 Scope thành tích NCKH
- accountant: **403 toàn bộ** nhóm research (#17–#37) — research không cấp cho accountant (BR-HR-023).
- staff: scope `own` — backend ép filter theo quan hệ thành viên/tác giả/mentor/performer; ghi yêu cầu `sub` là thành viên nội bộ của bản ghi.
- Tác giả/thành viên ngoài hệ thống: `external_name` (OQ#8c) — không FK, không vào thống kê cá nhân nội bộ (chỉ đếm cho phòng nếu gắn department).

---

## 5. Ghi chú phi chức năng

- **Pagination:** mọi list `page`/`limit` (default 20, max 100), `meta.{page,limit,total,hasNext}` (đồng bộ M7/M2).
- **CorrelationId & audit:** mọi request có `X-Correlation-Id` (FE gửi/BE sinh, trả lại header); mọi thao tác ghi → `audit_logs` với `correlation_id`, `action`, `resource`, `resource_id`, `user`, `ip`, `at`. **KHÔNG ghi giá trị PII/lương ra log/Sentry** (BR-HR-024, CONSTRAINT-9) — chỉ ghi fact "đã đổi trường X".
- **Immutable lịch sử lương:** `salary_history` append-only — KHÔNG có route PATCH/DELETE (BR-HR-008, §8.4). Sửa sai = ghi nâng lương điều chỉnh mới.
- **Tính ngày nâng lương:** `next_salary_raise_date` tự tính ở tầng app trong cùng transaction (BR-HR-005), cộng năm an toàn năm nhuận (29/02→28/02). KHÔNG nhận từ client.
- **Validation:** sanitize input tầng API; số tiền NUMERIC trả dạng string (§0.12); danh mục enum validate ∈ catalog.
- **Tiền:** NUMERIC(14,2) tiền + NUMERIC(6,2) hệ số; không float (NFR-COMPAT-HR-001).
- **Upload:** chỉ PDF/PNG/JPG, validate MIME thực + đuôi, ≤ giới hạn; lưu MinIO `file_key`, tải qua M7 #30 (NFR-SEC-HR-003).
- **Performance (NFR-PERF-HR-001/002):** đọc hồ sơ P95 < 400ms, list < 500ms; thống kê P95 < 3000ms (rate limit 10/phút endpoint nặng).
- **Cron idempotent (NFR-CRON-HR-001):** Redis lock + chống trùng (hồ sơ × mốc × ngày qua `idx_notif_ref`).

---

## 6. Traceability: Endpoint → FR SRS M4

| Endpoint(s) | FR | Submodule | 17025 |
|-------------|-----|-----------|-------|
| #1, #2, #3, #4 | FR-HR-001 | M4.1.1 | §6.2 |
| #5 | FR-HR-002 | M4.1.1 | §6.2/§8.4 |
| #6, #40 | FR-HR-003 | M4.1.2 | §6.2 |
| #8, #9 | FR-HR-004 | M4.1.3 | §6.2/§8.4 |
| (tự tính trong #6/#7/#8) | FR-HR-005 | M4.1.3 | §6.2 |
| #7 | FR-HR-006 | M4.1.3 | §6.2 |
| #10, #11, #12, #13, #14 | FR-HR-007 | M4.1.4 | §6.2/§8.4 |
| #42 (CRON-3) | FR-HR-008 | M4.2.1 | §6.2 |
| #43 (CRON-4) | FR-HR-009 | M4.2.2 | §6.2 |
| #17–#22, #38 | FR-HR-010 | M4.3.1 | §6.2 |
| #23, #24, #25, #26, #28, #29, #39 | FR-HR-011 | M4.3.2 | §6.2 |
| #24, #27 (type=patent) | FR-HR-012 | M4.3.3 | §6.2 |
| (department_id + n-n trong #17–#28) | FR-HR-013 | M4.3.4 | §6.2 |
| #30, #31, #32, #41 | FR-HR-014 | M4.3.5 | §6.2 |
| #33, #34a, #34b, #34c | FR-HR-015 | M4.3.6 | §6.2 |
| #35 | FR-HR-016 | M4.3.7 | §6.2 |
| #36 | FR-HR-017 | M4.3.8 | §6.2 |
| #37, #37b | FR-HR-018 | M4.3.x | §6.2 (báo cáo năng lực) |
| #15 | FR-HR-019 | M4.1.4/M4.3.x | §6.2 |
| #16 | FR-HR-020 | M4.1.4 | §6.2 |

**Phụ thuộc M7:** `hr_profiles.user_id` FK→`users`; quyền `hr:read`/`hr:manage`/`research:manage` (seed M7); `notifications`+`idx_notif_ref` cho CRON-3/4; `attachments(owner_type='hr_profile'|'publication')`; tải file qua M7 #30; đọc notifications qua M7 #24–#27.

---

*Hết Contract M4 API (v1.0). Đồng bộ phong cách M7/M2 (response envelope, UUID, pagination, correlationId, field-level strip). Phản ánh quyết định đã chốt: lương = hệ số×lương cơ sở; đọc lương = admin/leader/accountant + chính chủ; sửa lương = admin/accountant; đăng ký lab có duyệt; tác giả ngoài hệ thống qua external_name; danh mục mặc định đã seed. Các OPEN QUESTION vận hành còn lại (OQ#1c/#1d/#4/#6b/#10/#11) không chặn implement — đánh dấu trong validation tương ứng.*
