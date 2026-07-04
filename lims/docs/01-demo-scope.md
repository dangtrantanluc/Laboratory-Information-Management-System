# LIMS 17025 — Demo Scope & Thiết kế tổng thể

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm theo ISO/IEC 17025:2017
**Loại hình:** Lab học thuật / Trường Đại học (có NCKH, giảng dạy, hướng dẫn SV)
**Phiên bản:** v0.1 DRAFT — 19/06/2026
**Phân quyền:** RBAC + phạm vi theo phòng ban
**Lab:** ĐÃ được công nhận VILAS → document/record control chặt
**Trạng thái:** Scope đã chốt với KH (19/06/2026) — sẵn sàng sang `/ba` viết SRS

> Tài liệu này là **cây module 3 cấp + phân hạng P0/P1/P2 + ERD core + RBAC matrix + mapping điều khoản 17025 + danh sách cron job**.
> Dùng làm cơ sở để KH approve scope. Sau khi approve → `/ba` viết SRS cho các submodule P0.

---

## A. Cây Module 3 cấp (Module → Submodule → Feature)

Ký hiệu ưu tiên: **P0** = phải có (bản đầu/demo) · **P1** = nên có · **P2** = mở rộng sau.

### M1. Quản lý Mẫu & Yêu cầu thử nghiệm (Sample Lifecycle)
> 17025 §7.2 (lựa chọn/kiểm tra phương pháp), §7.4 (xử lý mẫu), §7.8 (báo cáo kết quả)

- **M1.1 Tiếp nhận mẫu (Sample Intake)**
  - F1.1.1 Tạo phiếu yêu cầu thử nghiệm — khách hàng/đối tượng gửi mẫu — **P0**
  - F1.1.2 Sinh mã mẫu duy nhất (barcode/QR, không lộ ID tuần tự) — **P0**
  - F1.1.3 Đính kèm file mẫu (ảnh, chứng từ gửi mẫu) — **P0**
  - F1.1.4 Ghi nhận tình trạng mẫu khi nhận (đạt/không đạt điều kiện) — **P1**
- **M1.2 Phân công & Chuyển giao (Assignment / Handover)**
  - F1.2.1 Phân công mẫu cho KTV/người thử nghiệm — **P0**
  - F1.2.2 Tạo phiếu công việc & chuyển cho nhân sự khác (handover có lịch sử) — **P0** *(R5)*
  - F1.2.3 Chuỗi hành trình mẫu (chain of custody — ai giữ, khi nào) — **P1** *(17025 §7.4)*
- **M1.3 Thực hiện & Nhập kết quả (Testing & Results)**
  - F1.3.1 Mỗi KTV điền kết quả phần được giao — **P0** *(R6)*
  - F1.3.2 Kết quả hiển thị công khai nội bộ lab (ai cũng xem được) — **P0** *(R6)*
  - F1.3.3 Đính kèm file kết quả (raw data, ảnh, Excel) — **P0** *(R2)*
  - F1.3.4 Phê duyệt kết quả trước khi chốt (reviewer/approver) — **P1** *(17025 §7.8)*
- **M1.4 Deadline & Trễ hạn**
  - F1.4.1 Đặt turnaround time/deadline cho mẫu — **P0**
  - F1.4.2 Cron nhắc mẫu sắp tới hạn — **P0** *(R7)*
  - F1.4.3 Bắt buộc nhập lý do khi trễ hạn — **P0** *(R9)*
  - F1.4.4 Báo cáo on-time rate (tỷ lệ đúng hạn) — **P1**
- **M1.5 Trả kết quả**
  - F1.5.1 Xuất phiếu kết quả thử nghiệm (PDF có mã, logo) — **P1**
  - ~~F1.5.2 Portal khách hàng~~ — **CẮT** (A02: chỉ nội bộ)

### M2. Quản lý Hóa chất & Tồn kho (Chemical Inventory)
> 17025 §6.4 (thiết bị & vật tư), §6.6 (sản phẩm/dịch vụ cung cấp bên ngoài)

- **M2.1 Danh mục hóa chất**
  - F2.1.1 CRUD hóa chất (tên, CAS, nhà sản xuất, **đơn vị tùy loại**) — **P0** *(A04)*
  - F2.1.2 Quản lý theo lô (lot/batch) + hạn dùng + chứng chỉ CoA — **P0** *(A03)*
  - F2.1.3 Thông tin an toàn (MSDS đính kèm, mã nguy hại) — **P1**
- **M2.2 Nhập / Xuất / Tồn (theo đơn vị của hóa chất)**
  - F2.2.1 Ghi nhật ký nhập hóa chất (số lượng, lô, ngày) — **P0** *(R4)*
  - F2.2.2 Ghi nhật ký xuất/sử dụng — **gắn với mẫu** (`ref_sample_id`) — **P0** *(R4, A04b)*
  - F2.2.3 Tự động trừ tồn + hiển thị tồn hiện tại theo lô (đúng đơn vị) — **P0** *(R4, N1)*
  - F2.2.4 Lịch sử giao dịch đầy đủ (audit) — **P0** *(R4)*
  - F2.2.5 Cảnh báo tồn dưới ngưỡng — **P1**
- **M2.3 Kiểm tra lại & Hạn dùng**
  - F2.3.1 Lịch kiểm tra lại/đánh giá lại hóa chất — **P0** *(R16)*
  - F2.3.2 Cron nhắc hóa chất sắp hết hạn / tới hạn kiểm tra — **P0** *(R16)*
- **M2.4 Xuất Excel & Báo cáo hóa chất**
  - F2.4.1 Xuất Excel nhật ký xuất/nhập theo khoảng thời gian — **P0** *(R4)*
  - F2.4.2 Báo cáo tiêu hao theo tháng/đề tài/người dùng — **P1**

### M3. Quản lý Tài liệu (Document Control)
> 17025 §8.3 (kiểm soát tài liệu), §8.4 (kiểm soát hồ sơ)

- **M3.1 Kho tài liệu**
  - F3.1.1 CRUD tài liệu (SOP, quy trình, biểu mẫu, hướng dẫn) — **P0**
  - F3.1.2 Đính kèm file + lưu object storage — **P0** *(R2, R11)*
  - F3.1.3 Phân loại tài liệu (loại, phòng ban, mức bảo mật) — **P0**
- **M3.2 Version & Lịch sử**
  - F3.2.1 Quản lý phiên bản tài liệu (v1, v2...) — **P0** *(R3)*
  - F3.2.2 Lịch sử thay đổi (ai sửa, khi nào, sửa gì) — **P0** *(R3)*
  - F3.2.3 Quy trình duyệt/ban hành tài liệu (draft→review→approved→obsolete) — **P0** *(17025 §8.3.2 — VILAS bắt buộc)*
  - F3.2.4 Chỉ phiên bản "hiệu lực" được dùng; bản cũ đánh dấu obsolete — **P0** *(VILAS)*
- **M3.3 Thống kê truy cập tài liệu**
  - F3.3.1 Đếm lượt xem / lượt tải / lượt chỉnh sửa mỗi tài liệu — **P0** *(R15)*

### M4. Nhân sự & Thành tích NCKH (HR & Research Achievement)
> 17025 §6.2 (nhân sự, năng lực, ủy quyền)

- **M4.1 Hồ sơ nhân sự**
  - F4.1.1 CRUD nhân sự (thông tin, phòng ban, chức danh) — **P0**
  - F4.1.2 Trường ngày ký hợp đồng + loại HĐ + ngày hết hạn HĐ — **P0** *(R12)*
  - F4.1.3 Chu kỳ nâng lương (mặc định 3 năm, cấu hình được) — **P0** *(R12)*
  - F4.1.4 Hồ sơ năng lực: bằng cấp, chứng chỉ, ủy quyền thử nghiệm — **P1** *(17025 §6.2)*
- **M4.2 Cron nhắc nhân sự**
  - F4.2.1 Cron nhắc tới hạn nâng lương: trước 15 ngày → 7 ngày → 3 ngày — **P0** *(R12)*
  - F4.2.2 Cron nhắc hết hạn hợp đồng — **P1**
- **M4.3 Thành tích NCKH**
  - F4.3.1 Đề tài NCKH (tên, chủ nhiệm, thành viên, cấp, thời gian, phòng) — **P0** *(R17)*
  - F4.3.2 Bài báo khoa học (tác giả, tạp chí, năm, chỉ số) — **P0** *(R17)*
  - F4.3.3 Bằng sáng chế / giải pháp hữu ích — **P0** *(R17)*
  - F4.3.4 Gắn thành tích cho cá nhân / tập thể / phòng thí nghiệm — **P0** *(R17)*
  - F4.3.5 Hướng dẫn sinh viên (số lượng, tên SV, đề tài) — **P0** *(R18)*
  - F4.3.6 Lượt SV đăng ký vào lab (thực tập/dùng thiết bị) — **P1** *(R18)*
  - F4.3.7 Môn học phụ trách giảng dạy — **P1** *(R19)*
  - F4.3.8 Phục vụ cộng đồng (nội dung, thời gian, người thực hiện, host) — **P1** *(R20)*

### M5. Quản lý Thiết bị & Hiệu chuẩn (Equipment) — hỗ trợ 17025
> 17025 §6.4 (thiết bị), §6.5 (liên kết chuẩn đo lường)

- **M5.1 Danh mục thiết bị**
  - F5.1.1 CRUD thiết bị (tên, mã, vị trí, tình trạng) — **P1**
- **M5.2 Hiệu chuẩn**
  - F5.2.1 Lịch hiệu chuẩn + đính kèm giấy chứng nhận — **P1** *(R16)*
  - F5.2.2 Cron nhắc trước thời gian hiệu chuẩn — **P0** *(R16 — "vlab")*

### M6. Báo cáo & Thống kê (Reporting & Analytics)
- **M6.1 Dashboard tổng hợp** — số mẫu, lượng hóa chất, lọc thời gian — **P0** *(R8, R10)*
- **M6.2 Bộ lọc đa tiêu chí** (phòng ban, người, loại mẫu, khoảng ngày) — **P0** *(R8)*
- **M6.3 Thống kê hệ thống** — lượt truy cập, lượt tải, lượt chỉnh sửa — **P1** *(R15)*
- **M6.4 Xuất Excel/PDF mọi báo cáo** — **P0** *(R4)*

### M7. Quản trị Hệ thống (Admin & Auth)
- **M7.1 Auth** — đăng nhập, JWT + refresh token — **P0**
- **M7.2 RBAC + phạm vi phòng ban** — **P0** *(R13)*
- **M7.3 Quản lý phòng ban & người dùng** — **P0**
- **M7.4 Audit log toàn hệ thống** (correlationId, ai làm gì) — **P0** *(R15, 17025 §8.4)*
- **M7.5 Thông báo (in-app + email)** — **P0** *(R7, R12, R16)*

---

## B. RBAC Matrix — Vai trò × Quyền

**4 vai trò** (chốt với KH 19/06/2026). Phạm vi dữ liệu: **theo phòng ban** trừ Admin/Lãnh đạo (toàn hệ thống). "Nhận mẫu" là **quyền của KTV** (B02), không phải vai trò riêng. Kế toán **chỉ thấy tài chính, không thấy mẫu/kết quả** (B03).

| Module / Hành động | Admin | Ban lãnh đạo | Kế toán | Nhân sự/KTV |
|---|:---:|:---:|:---:|:---:|
| **Mẫu** — tạo phiếu nhận (nhận mẫu) | ✅ | 👁 | — | ✅(phòng) |
| **Mẫu** — phân công / chuyển giao | ✅ | ✅ | — | ✅(phòng) |
| **Mẫu** — nhập kết quả | ✅ | 👁 | — | ✅(được giao) |
| **Mẫu** — xem công khai nội bộ | ✅ | ✅ | — | ✅ |
| **Mẫu** — duyệt kết quả | ✅ | ✅ | — | ✅(trưởng nhóm) |
| **Hóa chất** — nhập/xuất | ✅ | 👁 | 👁 | ✅(phòng) |
| **Hóa chất** — xem tồn/lịch sử | ✅ | ✅ | ✅ | ✅ |
| **Hóa chất** — chi phí (giá trị tiền) | ✅ | ✅ | ✅ | — |
| **Tài liệu** — tạo/sửa | ✅ | ✅ | — | ✅(phòng) |
| **Tài liệu** — duyệt/ban hành | ✅ | ✅ | — | — |
| **Tài liệu** — xem | ✅ | ✅ | 👁 | ✅ |
| **Nhân sự** — hồ sơ, HĐ | ✅ | ✅ | 👁(HĐ) | 👁(của mình) |
| **Nhân sự** — lương, nâng lương | ✅ | ✅ | ✅ | 👁(của mình) |
| **Nhân sự** — thành tích NCKH | ✅ | ✅ | — | ✅(của mình) |
| **Thiết bị** — hiệu chuẩn | ✅ | 👁 | — | ✅(phòng) |
| **Báo cáo** — nghiệp vụ (mẫu/hóa chất) | ✅ | ✅ | 👁(hóa chất) | 👁(phòng) |
| **Báo cáo** — tài chính | ✅ | ✅ | ✅ | — |
| **Admin** — user, role, phòng ban | ✅ | — | — | — |
| **Audit log** | ✅ | ✅ | — | — |

Chú thích: ✅ = toàn quyền (trong phạm vi) · 👁 = chỉ xem · — = không truy cập · (phòng) = giới hạn phòng ban · (của mình) = chỉ dữ liệu cá nhân.

> **Kế toán** (B03): thấy chi phí hóa chất + lương/HĐ + báo cáo tài chính; **KHÔNG** xem mẫu/kết quả thử nghiệm (cách ly nghiệp vụ lab khỏi tài chính).
> **Phòng ban** (B01): bảng `departments` có `parent_id` cho phép cấu hình cây phòng ban linh hoạt; KH tự nhập danh sách thật sau.

---

## C. ERD Core (các bảng chính)

```
┌─────────────────────────────────────────────────────────────────────┐
│ M7. AUTH & NỀN TẢNG (migration chạy ĐẦU TIÊN — chi tiết: 08-contract) │
├─────────────────────────────────────────────────────────────────────┤
│ departments (id PK, name, code UNIQUE, parent_id FK self,             │
│        lead_user_id FK→users NULL)  -- trưởng nhóm OQ#11 (M1)         │
│ users (id PK, email UNIQUE, password_hash[bcrypt], full_name,         │
│        department_id FK, role[admin|leader|accountant|staff], status) │
│ permissions / roles_permissions (role, resource, action, scope)       │
│   -- RBAC matrix seed sẵn; scope ∈ {all|department|own}              │
│ customers (id PK, name, contact, type)  -- khách gửi mẫu (M1 dùng)    │
│ attachments (id PK, owner_type, owner_id, file_key, file_name, mime,  │
│        size, uploaded_by FK)  -- polymorphic dùng chung M1/M2/M3     │
│ audit_logs (id PK, user_id FK, action, resource, resource_id,         │
│        correlation_id, ip, at, detail JSONB)  -- append-only §8.4    │
│ notifications (id PK, user_id FK, type, title, body, ref_type,        │
│        ref_id, read_at, created_at)  -- in-app, cron dùng            │
│ refresh_tokens (id PK, user_id FK, token_hash, expires_at, rotated)   │
│ access_stats (id PK, user_id FK, path, at)  -- R15 lượt truy cập     │
│   -- vòng FK users↔departments: tạo departments→users→ALTER FK lead  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ M1. MẪU                                                               │
├─────────────────────────────────────────────────────────────────────┤
│ (customers, attachments, audit_logs → định nghĩa ở M7)               │
│ test_requests (id PK, request_code UNIQUE, customer_id FK NULL,        │
│          department_id FK, received_by FK→users, received_at)          │
│   -- 1 phiếu = nhiều mẫu (OQ#1)                                       │
│ samples (id PK, sample_code UNIQUE [SP-YYYY-…], request_id FK NOT NULL,│
│          department_id FK, deadline_at, current_custodian_id FK→users, │
│          status[received|assigned|testing|done|overdue|returned],     │
│          condition_status, finalized_by FK NULL, finalized_at,        │
│          deleted_at)  -- done do trưởng nhóm chốt (OQ#2)              │
│ sample_assignments (id PK, sample_id FK, assigned_to FK→users,        │
│          assigned_by FK→users, part_name, status, assigned_at)        │
│ sample_results (id PK, assignment_id FK, result_data JSONB,           │
│          entered_by FK→users, entered_at, approved_by FK, approved_at, │
│          is_current)  -- approved immutable, sửa = bản mới; công khai  │
│          chỉ sau approved (OQ#3)                                       │
│ sample_handovers (id PK, sample_id FK, from_user FK, to_user FK, at)  │
│          -- chain of custody bất biến §7.4                            │
│ overdue_reasons (id PK, sample_id FK, reason TEXT NOT NULL, by FK, at) │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ M2. HÓA CHẤT                                                          │
├─────────────────────────────────────────────────────────────────────┤
│ units (code PK, name, measurement_group[mass|volume|count],           │
│            factor_to_base NUMERIC)  -- seed cố định, không sửa        │
│ chemicals (id PK, name, cas_no, manufacturer, base_unit FK→units,     │
│            measurement_group, reorder_threshold, hazard_code,         │
│            department_id FK, status)  -- mọi tồn lưu theo base_unit   │
│ chemical_lots (id PK, chemical_id FK, lot_no, qty_base NUMERIC(18,6), │
│            unit_price NUMERIC(14,2), price_unit FK→units, currency,   │
│            received_at, expiry_date, recheck_date, recheck_result,    │
│            coa_file_key)  -- giá trị tồn = qty × unit_price theo lô   │
│ chemical_transactions (id PK, lot_id FK, type[in|out|adjust],         │
│            qty_base NUMERIC(18,6), base_unit, qty_input NUMERIC(14,4),│
│            input_unit, balance_after NUMERIC(18,6), warning_override, │
│            ref_sample_id FK (NOT NULL khi out), by FK→users, at, note)│
│ chemical_recheck_records (id PK, lot_id FK, checked_at, result, by)   │
│   -- base_unit chống sai số quy đổi; balance_after audit (VILAS §8.4) │
│   -- KHÔNG quy đổi/cộng gộp chéo nhóm đo (N1); chi tiết: 03-contract  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ M3. TÀI LIỆU                                                          │
├─────────────────────────────────────────────────────────────────────┤
│ documents (id PK, code, title, type, department_id FK,                │
│            current_version_id FK→document_versions, status)           │
│ document_versions (id PK, document_id FK, version, file_key,          │
│            change_note, created_by FK, created_at,                    │
│            approved_by FK NULL, status ENUM[draft,review,approved,    │
│            obsolete])                                                  │
│ document_access_log (id PK, document_id FK, user_id FK,               │
│            action ENUM[view,download,edit], at)  -- R15               │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ M4. NHÂN SỰ & NCKH                                                    │
├─────────────────────────────────────────────────────────────────────┤
│ hr_profiles (user_id PK/FK, contract_signed_date, contract_type,      │
│            contract_end_date, salary_cycle_years DEFAULT 3,           │
│            last_salary_raise_date, next_salary_raise_date)            │
│ research_projects (id PK, title, level, lead_user_id FK,              │
│            department_id FK, start_date, end_date, status)            │
│ project_members (project_id FK, user_id FK, role_in_project)          │
│ publications (id PK, title, journal, year, doi, type ENUM[paper,      │
│            patent], department_id FK)                                  │
│ publication_authors (publication_id FK, user_id FK, author_order)     │
│ student_mentorships (id PK, mentor_id FK→users, student_name,         │
│            topic, year, type)                                         │
│ lab_registrations (id PK, student_name, mentor_id FK, registered_at,  │
│            purpose)  -- R18 số lần SV đăng ký vào lab                  │
│ teaching_courses (id PK, user_id FK, course_name, semester, year)     │
│ community_services (id PK, content, performed_at, host,               │
│            performer_user_id FK)  -- R20                              │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ M5. THIẾT BỊ                                                          │
├─────────────────────────────────────────────────────────────────────┤
│ equipments (id PK, name, code, location, department_id FK, status)    │
│ calibrations (id PK, equipment_id FK, calibrated_at, next_due_date,   │
│            cert_file_key, provider)                                   │
└─────────────────────────────────────────────────────────────────────┘

(M7 Hệ thống — notifications, audit_logs, access_stats… đã gom lên khối
 M7 ở đầu phần ERD; chi tiết DDL: 08-contract-m7-schema.md)
```

**Ghi chú thiết kế DB:**
- Số gam hóa chất: `NUMERIC(12,4)` — không dùng float (tránh sai số tích lũy).
- `balance_after` lưu trong mỗi giao dịch → audit được tồn tại từng thời điểm (không tin vào SUM runtime).
- `attachments` polymorphic dùng chung cho mẫu/tài liệu/CoA → đúng R2 ("kèm file vào này").
- `id` dùng UUID hoặc bigint + sample_code hiển thị riêng (không lộ ID tuần tự — rule API).

---

## D. Danh sách Cron Job (Scheduled Tasks)

| Cron | Tần suất | Logic | Output | Nguồn |
|------|----------|-------|--------|-------|
| CRON-1 Nhắc mẫu tới hạn | hằng ngày 07:00 | mẫu có `deadline_at` trong N ngày & chưa done | **in-app** cho người được giao | R7 |
| CRON-2 Đánh dấu trễ hạn | hằng ngày 00:30 | mẫu quá `deadline_at` & chưa done → status=overdue | yêu cầu nhập lý do | R9 |
| CRON-3 Nhắc nâng lương | hằng ngày 07:00 | `next_salary_raise_date` còn 15/7/3 ngày | **in-app** HR + lãnh đạo | R12 |
| CRON-4 Nhắc hết hạn HĐ | hằng ngày 07:00 | `contract_end_date` còn 30/15/7 ngày | **in-app** HR | R12 |
| CRON-5 Nhắc hiệu chuẩn TB | hằng ngày 07:00 | `next_due_date` còn 30/15/7 ngày | **in-app** phụ trách TB | R16 |
| CRON-6 Nhắc hóa chất hết hạn/kiểm tra lại | hằng ngày 07:00 | `expiry_date` hoặc `recheck_date` tới hạn | **in-app** phụ trách hóa chất | R16 |

> Tất cả thông báo: **chỉ in-app notification** (C02). Email/Zalo để giai đoạn sau nếu KH cần.
> Mốc nhắc nâng lương **15/7/3 ngày** (C04 chốt: 3 năm/lần cho mọi ngạch).
> Quy mô ~40 người (C03) → cron chạy nhẹ, dùng APScheduler trong app, có lock Redis tránh chạy trùng.

---

## E. Mapping Điều khoản ISO/IEC 17025:2017 → Module

| Điều khoản 17025 | Nội dung | Module đáp ứng |
|------------------|----------|----------------|
| §6.2 Nhân sự | Năng lực, ủy quyền, hồ sơ | M4.1, M4.3 (hồ sơ năng lực) |
| §6.4 Thiết bị | Quản lý, hiệu chuẩn | M5, M2 (vật tư/hóa chất) |
| §6.5 Liên kết chuẩn | Hiệu chuẩn truy xuất nguồn gốc | M5.2 |
| §6.6 SP/DV bên ngoài | Hóa chất mua ngoài + CoA | M2.1.2 |
| §7.2 Phương pháp | Lựa chọn/kiểm tra phương pháp | M1.3 (SOP gắn tài liệu) |
| §7.4 Xử lý mẫu | Tiếp nhận, bảo quản, chain of custody | M1.1, M1.2.3 |
| §7.5 Hồ sơ kỹ thuật | Bản ghi kết quả gốc | M1.3.3, attachments |
| §7.8 Báo cáo kết quả | Phiếu kết quả, phê duyệt | M1.3.4, M1.5 |
| §8.3 Kiểm soát tài liệu | Version, ban hành, obsolete | M3.2 |
| §8.4 Kiểm soát hồ sơ | Lưu trữ, truy xuất, audit | M7.4, document_access_log |
| §8.5 Rủi ro & cơ hội | (P2 — module quản lý rủi ro) | — (đề xuất sau) |

---

## F. Đề xuất Hạ tầng & Stack (R11 — tối ưu giá & thời gian)

| Thành phần | Đề xuất | Lý do |
|-----------|---------|-------|
| Backend | **FastAPI (Python)** | Đồng bộ stack spendlens trong repo; tái dùng pattern MinIO/Docker sẵn có |
| Frontend | Next.js + TailwindCSS | Stack chuẩn công ty |
| Database | PostgreSQL | NUMERIC(14,4) chính xác cho số lượng hóa chất, JSONB cho result_data |
| Object storage | **MinIO self-host** (CHỐT C01) | Lưu file mẫu, CoA, tài liệu, MSDS |
| Cache/Lock | Redis (session + cron lock) | ~40 user nên nhẹ; Redis chỉ để khóa cron + cache phân quyền |
| Cron | **APScheduler** trong FastAPI app | 6 cron job nhẹ, không cần worker riêng cho 40 user |
| Thông báo | **chỉ in-app notification** (CHỐT C02) | Bảng `notifications` + polling/SSE FE |
| Deploy | Docker Compose trên VPS Ubuntu | Theo chuẩn devops công ty |

> Quy mô ~40 người (C03): **không cần** scale ngang, message queue riêng, hay microservice. Một FastAPI monolith + Postgres + Redis + MinIO là đủ và rẻ.

---

## G. Roadmap đề xuất (Sprint)

| Sprint | Nội dung | Deliverable demo |
|--------|----------|------------------|
| S0 | Setup hạ tầng, Auth, RBAC, phòng ban, audit log | Đăng nhập + phân quyền chạy |
| S1 | M2 Hóa chất (nhập/xuất/tồn/Excel) + CRON-6 | Demo quản lý hóa chất theo gam |
| S2 | M1 Mẫu (nhận→phân công→kết quả công khai) + CRON-1,2 | Demo luồng mẫu đầy đủ |
| S3 | M3 Tài liệu (version + thống kê truy cập) + M4.1/4.2 Nhân sự + CRON-3,4 | Demo tài liệu + nhắc nâng lương |
| S4 | M4.3 NCKH + M5 Thiết bị + CRON-5 + M6 Báo cáo | Demo thành tích + dashboard |
| S5 | NFR (performance, security audit), hoàn thiện, UAT | Bản nghiệm thu |

> Mỗi sprint build xong → **gửi demo** cho KH duyệt *(R14)*.

---

## H. Gate tiếp theo

1. **KH duyệt scope này** (đặc biệt: 12 câu hỏi A/B/C trong `00-meeting-note-analysis.md`).
2. `/ba` viết SRS chi tiết cho submodule P0 (bắt đầu M2 Hóa chất + M1 Mẫu).
3. `/contract <feature>` — ERD + API + AC cho từng submodule.
4. `/dev` implement (CHỈ sau khi contract APPROVED).

**KHÔNG code khi chưa có contract APPROVED.**
