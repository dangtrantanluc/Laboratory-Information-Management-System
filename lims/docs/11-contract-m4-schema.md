# Contract — M4 Schema: Nhân sự & Thành tích NCKH (HR & Research Achievement)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M4 — Nhân sự & Thành tích NCKH (migration NỐI TIẾP M7→M1→M2)
**Tài liệu:** Database Schema Contract (DDL + Index + Seed + Traceability)
**Version:** 1.0 | **Ngày:** 20/06/2026 | **Author:** schema-designer agent
**Stack:** PostgreSQL 15+, FastAPI + SQLAlchemy/Alembic
**Nguồn chân lý:** `10-srs-m4-hr.md` (20 FR, 24 BR, NFR, §7 ghi chú schema), `08-contract-m7-schema.md` (users/departments/attachments/notifications dùng chung; quy ước D1–D11), `03-contract-m2-schema.md` + `06-contract-m1-schema.md` (đồng bộ phong cách DDL/index/dedup)
**Status:** DRAFT — chờ `/contract` gate / Tech Lead review

---

## 0. Quyết định thiết kế chính (đọc trước) — đồng bộ tuyệt đối với M7/M1/M2

| # | Quyết định | Lý do |
|---|-----------|-------|
| D1 | **PK = UUID `DEFAULT gen_random_uuid()`** cho mọi bảng nghiệp vụ; **bảng danh mục dùng natural-key VARCHAR PK** (`code`). Quan hệ n-n thuần dùng **PK kép**. | Đồng bộ M7 D1 / M2 D1. Danh mục natural-key đồng bộ `units` (M2) — code ổn định, seed/cấu hình dễ. |
| D2 | **ENUM = CHECK trên VARCHAR**, KHÔNG dùng native PG ENUM. | Đồng bộ M7 D2 / M1 D2 / M2 D5 (ALTER TYPE khó rollback Alembic). Áp cho `competences.kind`, `publications.type`, `lab_registrations.status`. |
| D3 | **`hr_profiles` 1-1 với `users`:** `user_id` **vừa PK vừa FK → users(id)** (KHÔNG cột `id` UUID riêng). Một user tối đa 1 hồ sơ. | CONSTRAINT-1 / BR-HR-001. Hồ sơ gắn danh tính M7; PK=FK đảm bảo 1-1 ở DB-level (không cần UNIQUE phụ). M4 KHÔNG tạo bảng người dùng riêng. |
| D4 | **Lương = hệ số × lương cơ sở (QUYẾT ĐỊNH ĐÃ CHỐT #1):** `salary_grade VARCHAR` (bậc/ngạch), `salary_coefficient NUMERIC(6,2)`, `base_salary_amount NUMERIC(14,2) NULL` (lương cơ sở áp dụng tại hồ sơ). Lương thực = coefficient × base (tính ở app, KHÔNG lưu cột dẫn xuất). Lịch sử nâng lương `salary_history` lưu **snapshot** (grade/coefficient/base cũ→mới). | Phản ánh chế độ lương HCSN VN (hệ số × lương cơ sở). `base_salary_amount` lưu tại hồ sơ để snapshot tại thời điểm (lương cơ sở nhà nước đổi theo thời gian — tránh tính lại sai lịch sử). NUMERIC không float (CONSTRAINT-6, NFR-COMPAT-HR-001). Quyền sửa = accountant + admin (enforce app — §7). |
| D5 | **Danh mục = bảng riêng (QUYẾT ĐỊNH ĐÃ CHỐT #3), KHÔNG CHECK + seed:** `contract_types`, `research_project_levels`, `publication_categories`, `mentorship_types`. PK natural-key `code`; có `label`, `sort_order`, `is_active`, `created_at`. | KH yêu cầu **cấu hình được** (thêm/ẩn cấp đề tài, phân loại bài báo) mà không cần migration/đổi code → bảng danh mục thắng CHECK. Đồng bộ tinh thần `units` (M2). FK từ bảng nghiệp vụ → `code` của danh mục (RESTRICT). `is_active` để ẩn giá trị cũ mà giữ toàn vẹn bản ghi lịch sử (soft-disable thay vì xóa). |
| D6 | **Đăng ký lab CÓ duyệt (QUYẾT ĐỊNH ĐÃ CHỐT #2):** `lab_registrations.status VARCHAR CHECK(pending|approved|rejected)` DEFAULT `pending`; `approved_by FK→users NULL`, `approved_at TIMESTAMPTZ NULL`; `mentor_id FK→users` (người hướng dẫn — cũng là người duyệt cấp phòng). Chỉ `approved` được tính thống kê (BR-HR-021). | OQ#8 đã chốt = CÓ duyệt. Trạng thái pending→approved/rejected là state machine đơn giản, enforce ở app (đồng bộ tinh thần M1 state machine). |
| D7 | **Tác giả/thành viên/hướng dẫn: hỗ trợ NGƯỜI NGOÀI hệ thống (free-text).** `publication_authors.user_id NULL` + `external_name NULL` (đúng 1 trong 2 NOT NULL — CHECK XOR). `project_members.user_id` NOT NULL (thành viên đề tài bắt buộc là user nội bộ — chủ nhiệm/thành viên cần FK). `student_mentorships.student_name`/`community_services` dùng free-text (SV/đối tượng ngoài không phải user). | OQ#8c xu hướng "cho phép tác giả ngoài" cho bài báo (đồng tác giả ngoài trường rất phổ biến). Đề tài giữ FK chặt (thành viên nội bộ phục vụ thống kê năng lực §6.2). Nếu KH chốt khác → ALTER nhẹ. **Ghi chú Tech Lead §8.** |
| D8 | **`salary_history` append-only (immutable §8.4):** KHÔNG route UPDATE/DELETE (enforce app-layer, đồng bộ `chemical_transactions` M2 / `sample_handovers` M1 — KHÔNG thêm trigger riêng). Sửa sai = thêm bản ghi điều chỉnh. | BR-HR-008, NFR-AUDIT-HR-001. Đồng bộ phong cách immutable M1/M2 (app không expose route sửa/xóa) thay vì trigger DB. |
| D9 | **`next_salary_raise_date` tính ở APP-LAYER** (KHÔNG trigger/GENERATED) — lưu cột thường `DATE NULL`. App tính lại trong cùng transaction khi `last_salary_raise_date`/`contract_signed_date`/`salary_cycle_years` đổi (BR-HR-005, cộng-năm an toàn năm nhuận 29/02→28/02). | CONSTRAINT-2 + §7 SRS khuyến nghị app-layer (dễ test property-based NFR-CORRECT-HR-001; nguồn chân lý là service). GENERATED column không xử lý được logic 29/02→28/02 + fallback base sạch. Khuyến nghị giống M1/M2 (logic nghiệp vụ ở app). |
| D10 | **Dedup cron = bảng riêng `hr_notification_dedup`** (đồng bộ `chemical_notification_dedup` M2), KHÔNG chỉ dựa `idx_notif_ref`. `kind CHECK(SALARY_RAISE_DUE|CONTRACT_EXPIRY)`, `milestone_days`, `fire_date`, UNIQUE(profile_user_id, kind, milestone_days, fire_date). | CRON-3 mốc 15/7/3, CRON-4 mốc 30/15/7 — mỗi (hồ sơ × mốc × ngày) chỉ 1 notification (BR-HR-013, NFR-CRON-HR-001). Bảng dedup chuyên dụng idempotent rõ ràng + cho nhiều người nhận cùng 1 lần fire (HR + nhân sự + lãnh đạo) mà chỉ chống trùng theo hồ sơ, không theo từng người nhận. |
| D11 | **Đính kèm dùng `attachments` polymorphic của M7** (`owner_type IN ('hr_profile','publication')` đã có trong whitelist M7 §2). M4 KHÔNG tạo bảng file riêng; lưu `file_key` MinIO, không binary DB. | D9 M7 (polymorphic dùng chung). Bằng cấp/chứng chỉ/HĐ scan → `owner_type='hr_profile'`, owner_id = user_id; minh chứng bài báo/sáng chế → `owner_type='publication'`, owner_id = publication.id. |
| D12 | **`department_id` trên bảng thành tích là cột THƯỜNG FK→departments** (không suy runtime), set khi tạo (mặc định = phòng của người khai). Cho phép NULL → gom "Không gắn phòng" trong thống kê. | BR-HR-022 (thống kê 3 chiều cá nhân/tập thể/phòng). Lưu cứng để thống kê phòng nhanh + đúng tại thời điểm (người có thể đổi phòng sau). NULL hợp lệ (BR-HR-022 "thiếu phòng → gom nhóm"). |

> **Audit fields (rule global, đồng bộ M7 D-note):** bảng có vòng đời cập nhật (`hr_profiles`, `research_projects`, `publications`, và các bảng thành tích) có `created_at`/`updated_at` + `created_by`/`updated_by UUID REFERENCES users(id) ON DELETE RESTRICT`. Bảng append-only/log (`salary_history`, `hr_notification_dedup`) dùng cột người-liên-quan riêng (`by_user`/không cần updated). Bảng n-n thuần (`project_members`, `publication_authors`) không cần cặp created/updated (vòng đời theo bản ghi cha). Bảng danh mục là cấu hình hệ thống → chỉ `created_at` + `is_active`.

> **Mọi thay đổi M4 ghi `audit_logs` (M7) ở app-layer** (BR-HR-004, NFR-AUDIT-HR-001): action `HR_PROFILE_CREATE/UPDATE`, `HR_CONTRACT_UPDATE`, `HR_SALARY_RAISE`, `HR_SALARY_CYCLE_UPDATE`, `HR_COMPETENCE_CHANGE`, `RESEARCH_PROJECT_CREATE`, `RESEARCH_PUBLICATION_CREATE`, `RESEARCH_PATENT_CREATE`, `RESEARCH_MENTORSHIP_CREATE`, `LAB_REGISTRATION_CREATE/APPROVE`, `TEACHING_COURSE_CREATE`, `COMMUNITY_SERVICE_CREATE`, `RESEARCH_REPORT_EXPORT`, `HR_COMPETENCE_EXPORT`. `detail` JSONB ĐÃ LỌC PII/lương (BR-HR-024, NFR-SEC-HR-002).

---

## 1. ERD chi tiết M4 (ASCII)

Tham chiếu bảng dùng chung M7 (KHÔNG tạo lại): `users`, `departments`, `attachments`, `notifications`, `audit_logs`, `roles_permissions`.

```
   ┌──────────────────────┐        ┌────────────────────────┐
   │  users  (M7)         │        │  departments  (M7)     │
   │  id UUID PK          │◄──┐    │  id UUID PK            │
   │  department_id FK    │   │    │  lead_user_id FK       │
   │  role / status       │   │    └────────────────────────┘
   └──────────┬───────────┘   │                  ▲ department_id (FK, NULL→"không gắn phòng")
              │ 1-1           │ FK (mentor/lead/author/by_user/approved_by/performer)
              │ (user_id = PK=FK)                │
   ┌──────────▼──────────────────────────────────┴───────────────────────┐
   │  hr_profiles  (HỒ SƠ NHÂN SỰ — 1-1 với users; FR-HR-001..006)        │
   │  user_id           UUID PK / FK→users(id) ON DELETE RESTRICT         │
   │  job_title         VARCHAR(255) NOT NULL                             │
   │  hired_date        DATE NULL                                         │
   │  phone             VARCHAR(32) NULL                                  │
   │  position          VARCHAR(255) NULL                                 │
   │  ── Hợp đồng (FR-HR-003, CRON-4) ──────────────────────────────────  │
   │  contract_type     VARCHAR(32) FK→contract_types(code) NULL          │
   │  contract_signed_date DATE NULL                                      │
   │  contract_end_date DATE NULL   (NULL = vô thời hạn → CRON-4 bỏ qua) │
   │  ── Lương: hệ số × lương cơ sở (FR-HR-004, D4 — field-level RBAC) ──  │
   │  salary_grade      VARCHAR(32) NULL          (bậc/ngạch)             │
   │  salary_coefficient NUMERIC(6,2) NULL                                │
   │  base_salary_amount NUMERIC(14,2) NULL       (lương cơ sở áp dụng)  │
   │  currency          VARCHAR(3) NOT NULL DEFAULT 'VND'                 │
   │  ── Chu kỳ nâng lương (FR-HR-005/006, BR-HR-005, app-tính) ────────  │
   │  salary_cycle_years   INT NOT NULL DEFAULT 3 CHECK(>=1)              │
   │  last_salary_raise_date DATE NULL                                    │
   │  next_salary_raise_date DATE NULL   ◄── app tính (CRON-3 quét)      │
   │  created_by/updated_by/created_at/updated_at                         │
   └───┬──────────────────────────────────────────────────────────────┬──┘
       │ 1                                                             │ 1
       │ N (user_id FK)                                                │ N
   ┌───▼───────────────────────────┐               ┌──────────────────▼─────────────┐
   │ salary_history (APPEND-ONLY)  │               │ competences (NĂNG LỰC §6.2)    │
   │ id PK                         │               │ id PK                          │
   │ user_id FK→users(id) RESTRICT │               │ user_id FK→users(id) RESTRICT  │
   │ old_grade/old_coefficient/    │               │ kind CHECK(degree|certificate| │
   │   old_base_amount (snapshot)  │               │            authorization)      │
   │ new_grade/new_coefficient/    │               │ title / issuer                 │
   │   new_base_amount             │               │ issued_date / expiry_date NULL │
   │ raise_date DATE               │               │ scope_detail (chỉ tiêu — auth) │
   │ by_user FK / note / created_at│               │ authorized_by FK→users NULL    │
   └───────────────────────────────┘               │ created_by/updated_by/at       │
                                                    └────────────────────────────────┘
   ┌────────────────────────────────────────┐
   │ hr_notification_dedup (CRON-3/4 dedup) │  D10 — đồng bộ chemical_notification_dedup M2
   │ id PK                                  │
   │ profile_user_id FK→hr_profiles RESTRICT│
   │ kind CHECK(SALARY_RAISE_DUE|           │
   │            CONTRACT_EXPIRY)            │
   │ milestone_days SMALLINT                │
   │ fire_date DATE                         │
   │ UNIQUE(profile_user_id,kind,ms,fire)  │
   └────────────────────────────────────────┘

   ══════════════ THÀNH TÍCH NCKH (FR-HR-010..017) ══════════════
   ┌───────────────────────────────────────┐        ┌──────────────────────────────┐
   │ research_projects (ĐỀ TÀI — FR-HR-010)│        │ project_members (n-n)        │
   │ id PK                                 │◄───────│ project_id FK RESTRICT        │
   │ code VARCHAR UNIQUE NULL              │ 1    N │ user_id FK→users RESTRICT     │
   │ title NOT NULL                        │        │ role_in_project VARCHAR       │
   │ level FK→research_project_levels(code)│        │ PK(project_id, user_id)       │
   │ lead_user_id FK→users RESTRICT        │        └──────────────────────────────┘
   │ department_id FK→departments NULL     │
   │ start_date/end_date/status            │
   └───────────────────────────────────────┘
   ┌───────────────────────────────────────┐        ┌──────────────────────────────┐
   │ publications (BÀI BÁO/SÁNG CHẾ)       │        │ publication_authors (n-n)    │
   │ id PK   (FR-HR-011/012)               │◄───────│ publication_id FK RESTRICT    │
   │ title NOT NULL / journal / year       │ 1    N │ user_id FK→users NULL (D7)    │
   │ doi NULL                              │        │ external_name VARCHAR NULL    │
   │ category FK→publication_categories    │        │ author_order SMALLINT         │
   │ type CHECK(paper|patent)              │        │ is_corresponding BOOL         │
   │ patent_no NULL / issuing_authority    │        │ PK(publication_id,author_order│
   │ department_id FK NULL                 │        │ CHECK XOR(user_id,external)   │
   └───────────────────────────────────────┘        └──────────────────────────────┘
   ┌───────────────────────────┐ ┌───────────────────────────┐ ┌──────────────────────────┐
   │ student_mentorships       │ │ lab_registrations (DUYỆT) │ │ teaching_courses         │
   │ id PK (FR-HR-014)         │ │ id PK (FR-HR-015, D6)     │ │ id PK (FR-HR-016)        │
   │ mentor_id FK→users        │ │ student_name              │ │ user_id FK→users         │
   │ student_name/topic/year   │ │ mentor_id FK→users        │ │ course_name/semester/year│
   │ type FK→mentorship_types  │ │ registered_at/from/to     │ │ department_id FK NULL    │
   │ department_id FK NULL     │ │ purpose                   │ └──────────────────────────┘
   └───────────────────────────┘ │ status CHECK(pending|     │ ┌──────────────────────────┐
                                  │   approved|rejected)      │ │ community_services       │
                                  │ approved_by FK / approved_at│ │ id PK (FR-HR-017)        │
                                  │ department_id FK NULL     │ │ content/performed_at/host│
                                  └───────────────────────────┘ │ performer_user_id FK     │
                                                                 │ department_id FK NULL    │
   ══════════ DANH MỤC CẤU HÌNH (D5 — seed, admin sửa được) ════ └──────────────────────────┘
   contract_types │ research_project_levels │ publication_categories │ mentorship_types
   (code PK, label, sort_order, is_active, created_at)
```

### Bảng dùng chung tham chiếu (KHÔNG tạo lại — sở hữu bởi M7)

| Bảng M7 | M4 dùng làm gì |
|---------|----------------|
| `users` | `hr_profiles.user_id` (1-1), `lead_user_id`, `mentor_id`, `by_user`, `authorized_by`, `approved_by`, `performer_user_id`, `publication_authors.user_id`, `project_members.user_id`, `teaching_courses.user_id`, audit `created_by/updated_by` |
| `departments` | `department_id` trên mọi bảng thành tích + suy phòng nhân sự qua `users.department_id` |
| `attachments` | `owner_type='hr_profile'` (bằng cấp/chứng chỉ/HĐ scan, owner_id=user_id) + `owner_type='publication'` (minh chứng bài báo, owner_id=publication.id) — whitelist đã có M7 |
| `notifications` | CRON-3 (`SALARY_RAISE_DUE`) + CRON-4 (`CONTRACT_EXPIRY`), `ref_type='hr_profile'`, `ref_id=user_id` |
| `audit_logs` | Mọi thay đổi HR/năng lực/lương/HĐ/thành tích (BR-HR-004) |
| `roles_permissions` | `hr:read`/`hr:manage`/`research:manage` đã seed M7 §5.2 — M4 KHÔNG thêm quyền mới |

---

## 2. DDL đầy đủ

> **Prereq:** M7 đã bật `pgcrypto`/`pg_trgm`/`citext`; `users`/`departments`/`attachments` đã tồn tại. **Thứ tự CREATE (phá phụ thuộc FK):**
> 1. 4 bảng danh mục (`contract_types`, `research_project_levels`, `publication_categories`, `mentorship_types`) → 2. `hr_profiles` (FK→users, contract_types) → 3. `salary_history` → 4. `competences` → 5. `hr_notification_dedup` → 6. `research_projects` (FK→levels) → 7. `project_members` → 8. `publications` (FK→categories) → 9. `publication_authors` → 10. `student_mentorships` → 11. `lab_registrations` → 12. `teaching_courses` → 13. `community_services` → 14. indexes → 15. seed danh mục.

```sql
-- ============================================================
-- SCHEMA: m4-hr (Nhân sự & Thành tích NCKH — HR & Research Achievement)
-- Feature: M4 LIMS 17025 — hồ sơ nhân sự, lương (hệ số×lương cơ sở), năng lực §6.2,
--          CRON-3/4 nhắc nâng lương/hết hạn HĐ, thành tích NCKH (đề tài/bài báo/SV).
-- Designer: schema-designer agent | Date: 2026-06-20
-- Prereq: M7 (users/departments/attachments/notifications) → M1 → M2. Revision nối M2.
-- ============================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid() (đã bật M7; an toàn nếu chạy độc lập)

-- ------------------------------------------------------------
-- [ DANH MỤC 1-4 ] D5 — bảng danh mục cấu hình được (code PK natural-key, như units M2)
-- ------------------------------------------------------------
CREATE TABLE contract_types (
    code        VARCHAR(32)  PRIMARY KEY,                       -- vd 'probation','fixed_term','indefinite'
    label       VARCHAR(128) NOT NULL,
    sort_order  SMALLINT     NOT NULL DEFAULT 0,
    is_active   BOOLEAN      NOT NULL DEFAULT true,             -- ẩn giá trị cũ mà giữ toàn vẹn FK lịch sử
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE contract_types IS 'Danh mục loại hợp đồng (OQ#3, BR-HR-015). Admin cấu hình; is_active=false để ẩn không xóa (giữ FK lịch sử).';

CREATE TABLE research_project_levels (
    code        VARCHAR(32)  PRIMARY KEY,                       -- vd 'institution','university','ministry'...
    label       VARCHAR(128) NOT NULL,
    sort_order  SMALLINT     NOT NULL DEFAULT 0,
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE research_project_levels IS 'Danh mục cấp đề tài NCKH (Cơ sở/Trường/Bộ/Tỉnh/Nhà nước/Quốc tế — QUYẾT ĐỊNH #3, OQ#5, BR-HR-015).';

CREATE TABLE publication_categories (
    code        VARCHAR(32)  PRIMARY KEY,                       -- vd 'isi_q1','scopus','domestic','conference'
    label       VARCHAR(128) NOT NULL,
    sort_order  SMALLINT     NOT NULL DEFAULT 0,
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE publication_categories IS 'Danh mục phân loại/chỉ số bài báo (ISI Q1-Q4/Scopus/trong nước/hội nghị — QUYẾT ĐỊNH #3, OQ#6, BR-HR-017).';

CREATE TABLE mentorship_types (
    code        VARCHAR(32)  PRIMARY KEY,                       -- vd 'thesis_bachelor','thesis_master','phd'
    label       VARCHAR(128) NOT NULL,
    sort_order  SMALLINT     NOT NULL DEFAULT 0,
    is_active   BOOLEAN      NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE mentorship_types IS 'Danh mục loại hướng dẫn SV (khóa luận/luận văn/luận án/NCKH SV — OQ#7, BR-HR-020).';

-- ------------------------------------------------------------
-- [ TABLE 1 ] hr_profiles — hồ sơ nhân sự 1-1 với users (FR-HR-001..006, D3)
--   user_id VỪA PK VỪA FK → users(id): đảm bảo 1-1 ở DB-level.
--   Lương = hệ số × lương cơ sở (D4); next_salary_raise_date app tính (D9).
-- ------------------------------------------------------------
CREATE TABLE hr_profiles (
    user_id                 UUID         PRIMARY KEY,           -- = users.id (1-1) — KHÔNG cột id riêng
    job_title               VARCHAR(255) NOT NULL,              -- chức danh (BR-HR-006 bắt buộc)
    hired_date              DATE         NULL,                  -- ngày vào làm
    phone                   VARCHAR(32)  NULL,
    position                VARCHAR(255) NULL,                  -- vị trí công tác (bổ sung)

    -- ===== Hợp đồng (FR-HR-003; nguồn cho CRON-4 + base next_salary_raise) =====
    contract_type           VARCHAR(32)  NULL,                  -- FK danh mục
    contract_signed_date    DATE         NULL,
    contract_end_date       DATE         NULL,                  -- NULL = vô thời hạn (CRON-4 bỏ qua — BR-HR-009)

    -- ===== Lương: hệ số × lương cơ sở (FR-HR-004, D4 — field-level RBAC app strip) =====
    salary_grade            VARCHAR(32)  NULL,                  -- bậc/ngạch
    salary_coefficient      NUMERIC(6,2) NULL CHECK (salary_coefficient IS NULL OR salary_coefficient > 0),
    base_salary_amount      NUMERIC(14,2) NULL CHECK (base_salary_amount IS NULL OR base_salary_amount >= 0), -- lương cơ sở áp dụng
    currency                VARCHAR(3)   NOT NULL DEFAULT 'VND',-- CONSTRAINT-6

    -- ===== Chu kỳ nâng lương (FR-HR-005/006, BR-HR-005/011 — app tính next, D9) =====
    salary_cycle_years      INT          NOT NULL DEFAULT 3 CHECK (salary_cycle_years >= 1), -- C04 mặc định 3
    last_salary_raise_date  DATE         NULL,                  -- NULL = chưa từng nâng
    next_salary_raise_date  DATE         NULL,                  -- app tính = (last ?? signed) + cycle năm (CRON-3 quét)

    created_by              UUID         NULL,
    updated_by              UUID         NULL,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_hrp_user      FOREIGN KEY (user_id)       REFERENCES users(id)          ON DELETE RESTRICT,
    CONSTRAINT fk_hrp_contract  FOREIGN KEY (contract_type) REFERENCES contract_types(code) ON DELETE RESTRICT,
    CONSTRAINT fk_hrp_created   FOREIGN KEY (created_by)     REFERENCES users(id)          ON DELETE RESTRICT,
    CONSTRAINT fk_hrp_updated   FOREIGN KEY (updated_by)     REFERENCES users(id)          ON DELETE RESTRICT,
    CONSTRAINT ck_hrp_contract_date_order CHECK (
        contract_end_date IS NULL OR contract_signed_date IS NULL OR contract_end_date > contract_signed_date
    )  -- BR-HR-007
);
COMMENT ON TABLE  hr_profiles IS 'Hồ sơ nhân sự 1-1 với users (BR-HR-001, D3: user_id PK=FK). Lương = salary_coefficient × base_salary_amount (D4). next_salary_raise_date do APP tính (D9, BR-HR-005).';
COMMENT ON COLUMN hr_profiles.base_salary_amount IS 'Lương cơ sở áp dụng tại hồ sơ (snapshot — lương cơ sở nhà nước đổi theo thời gian). Field-level RBAC: chỉ admin/leader/accountant + chính chủ (BR-HR-002/003).';
COMMENT ON COLUMN hr_profiles.next_salary_raise_date IS 'TỰ TÍNH ở app (KHÔNG nhập tay): (last_salary_raise_date ?? contract_signed_date) + salary_cycle_years năm; 29/02→28/02 năm không nhuận (BR-HR-005). NULL→CRON-3 bỏ qua (BR-HR-010).';

-- ------------------------------------------------------------
-- [ TABLE 2 ] salary_history — lịch sử nâng lương APPEND-ONLY (FR-HR-004, BR-HR-008, D8)
--   Snapshot grade/coefficient/base cũ→mới (D4). KHÔNG route UPDATE/DELETE (app-layer §8.4).
-- ------------------------------------------------------------
CREATE TABLE salary_history (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID         NOT NULL,                  -- = hr_profiles.user_id
    old_grade           VARCHAR(32)  NULL,
    old_coefficient     NUMERIC(6,2) NULL,
    old_base_amount     NUMERIC(14,2) NULL,
    new_grade           VARCHAR(32)  NULL,
    new_coefficient     NUMERIC(6,2) NULL CHECK (new_coefficient IS NULL OR new_coefficient > 0),
    new_base_amount     NUMERIC(14,2) NULL CHECK (new_base_amount IS NULL OR new_base_amount >= 0),
    currency            VARCHAR(3)   NOT NULL DEFAULT 'VND',
    raise_date          DATE         NOT NULL,                  -- ngày nâng (→ last_salary_raise_date)
    note                TEXT         NULL,                      -- số quyết định nâng lương
    by_user             UUID         NOT NULL,                  -- người ghi nhận
    correlation_id      VARCHAR(64)  NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_sh_profile FOREIGN KEY (user_id) REFERENCES hr_profiles(user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_sh_byuser  FOREIGN KEY (by_user) REFERENCES users(id)            ON DELETE RESTRICT
);
COMMENT ON TABLE salary_history IS 'Lịch sử nâng lương APPEND-ONLY (BR-HR-008, §8.4). Snapshot grade/coefficient/base cũ→mới (D4). App KHÔNG expose route sửa/xóa (đồng bộ chemical_transactions M2). Sửa sai = thêm bản ghi điều chỉnh.';

-- ------------------------------------------------------------
-- [ TABLE 3 ] competences — hồ sơ năng lực §6.2 (FR-HR-007): bằng cấp/chứng chỉ/ủy quyền
-- ------------------------------------------------------------
CREATE TABLE competences (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID         NOT NULL,                      -- = hr_profiles.user_id
    kind            VARCHAR(16)  NOT NULL
        CHECK (kind IN ('degree', 'certificate', 'authorization')),
    title           VARCHAR(255) NOT NULL,                      -- tên bằng/chứng chỉ; với auth = chỉ tiêu ủy quyền
    issuer          VARCHAR(255) NULL,                          -- nơi cấp / người ủy quyền (tên)
    issued_date     DATE         NULL,
    expiry_date     DATE         NULL,                          -- NULL = không hết hạn; <today → app đánh dấu expired
    scope_detail    TEXT         NULL,                          -- chỉ tiêu/phương pháp được ủy quyền (kind=authorization)
    authorized_by   UUID         NULL,                          -- người ủy quyền (kind=authorization) FK→users
    created_by      UUID         NULL,
    updated_by      UUID         NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_comp_profile     FOREIGN KEY (user_id)       REFERENCES hr_profiles(user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_comp_authorized  FOREIGN KEY (authorized_by) REFERENCES users(id)            ON DELETE RESTRICT,
    CONSTRAINT fk_comp_created     FOREIGN KEY (created_by)     REFERENCES users(id)            ON DELETE RESTRICT,
    CONSTRAINT fk_comp_updated     FOREIGN KEY (updated_by)     REFERENCES users(id)            ON DELETE RESTRICT,
    CONSTRAINT ck_comp_date_order  CHECK (
        expiry_date IS NULL OR issued_date IS NULL OR expiry_date >= issued_date
    )  -- ủy quyền/chứng chỉ from>to → 422 (FR-HR-007 A2)
);
COMMENT ON TABLE  competences IS 'Hồ sơ năng lực §6.2 (FR-HR-007): bằng cấp/chứng chỉ/ủy quyền thử nghiệm. Thay đổi BẮT BUỘC audit HR_COMPETENCE_CHANGE (BR-HR-004, §8.4). Minh chứng qua attachments(owner_type=hr_profile).';
COMMENT ON COLUMN competences.scope_detail IS 'Chỉ tiêu/phương pháp được ủy quyền thực hiện (kind=authorization) — bằng chứng §6.2 "ủy quyền nhân sự".';

-- ------------------------------------------------------------
-- [ TABLE 4 ] hr_notification_dedup — chống trùng CRON-3/4 (D10, BR-HR-013)
--   Đồng bộ chemical_notification_dedup (M2). 1 bản/(hồ sơ × mốc × ngày).
-- ------------------------------------------------------------
CREATE TABLE hr_notification_dedup (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_user_id UUID         NOT NULL,                      -- = hr_profiles.user_id
    kind            VARCHAR(20)  NOT NULL
        CHECK (kind IN ('SALARY_RAISE_DUE', 'CONTRACT_EXPIRY')),
    milestone_days  SMALLINT     NOT NULL
        CHECK (milestone_days IN (3, 7, 15, 30)),              -- CRON-3: 15/7/3; CRON-4: 30/15/7
    fire_date       DATE         NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_hrdedup_profile FOREIGN KEY (profile_user_id) REFERENCES hr_profiles(user_id) ON DELETE CASCADE,
    CONSTRAINT uq_hrdedup UNIQUE (profile_user_id, kind, milestone_days, fire_date)
);
COMMENT ON TABLE hr_notification_dedup IS 'Chống trùng CRON-3/CRON-4 (D10, BR-HR-013, NFR-CRON-HR-001). UNIQUE đảm bảo 1 lần fire/(hồ sơ × mốc × ngày) dù cron retry. ON DELETE CASCADE theo hồ sơ.';

-- ------------------------------------------------------------
-- [ TABLE 5 ] research_projects — đề tài NCKH (FR-HR-010)
-- ------------------------------------------------------------
CREATE TABLE research_projects (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(64)  NULL,                          -- mã đề tài (tùy chọn, UNIQUE nếu có)
    title           VARCHAR(512) NOT NULL,
    level           VARCHAR(32)  NULL,                          -- FK danh mục cấp đề tài
    lead_user_id    UUID         NOT NULL,                      -- chủ nhiệm (BR-HR-016 đúng 1)
    department_id   UUID         NULL,                          -- gắn phòng (D12, BR-HR-022; NULL=không gắn)
    start_date      DATE         NULL,
    end_date        DATE         NULL,
    status          VARCHAR(16)  NOT NULL DEFAULT 'ongoing'
        CHECK (status IN ('ongoing', 'completed', 'accepted', 'cancelled')),
    created_by      UUID         NULL,
    updated_by      UUID         NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_rp_level    FOREIGN KEY (level)         REFERENCES research_project_levels(code) ON DELETE RESTRICT,
    CONSTRAINT fk_rp_lead     FOREIGN KEY (lead_user_id)  REFERENCES users(id)        ON DELETE RESTRICT,
    CONSTRAINT fk_rp_dept     FOREIGN KEY (department_id) REFERENCES departments(id)  ON DELETE RESTRICT,
    CONSTRAINT fk_rp_created  FOREIGN KEY (created_by)     REFERENCES users(id)        ON DELETE RESTRICT,
    CONSTRAINT fk_rp_updated  FOREIGN KEY (updated_by)     REFERENCES users(id)        ON DELETE RESTRICT,
    CONSTRAINT uq_rp_code     UNIQUE (code),                    -- NULL không vi phạm UNIQUE (nhiều NULL OK)
    CONSTRAINT ck_rp_date_order CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);
COMMENT ON TABLE research_projects IS 'Đề tài NCKH (FR-HR-010, R17). lead_user_id = chủ nhiệm (BR-HR-016). level FK danh mục cấu hình (D5). department_id thống kê phòng (D12).';

-- ------------------------------------------------------------
-- [ TABLE 6 ] project_members — thành viên đề tài n-n (FR-HR-010, BR-HR-016)
--   PK kép (project_id, user_id) chống trùng 1 user 2 lần trong cùng đề tài.
-- ------------------------------------------------------------
CREATE TABLE project_members (
    project_id      UUID         NOT NULL,
    user_id         UUID         NOT NULL,                      -- thành viên nội bộ (D7: đề tài bắt buộc FK user)
    role_in_project VARCHAR(64)  NOT NULL DEFAULT 'member',     -- chủ nhiệm/thành viên/thư ký...
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT pk_project_members PRIMARY KEY (project_id, user_id),  -- BR-HR-016 không trùng thành viên
    CONSTRAINT fk_pm_project FOREIGN KEY (project_id) REFERENCES research_projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_pm_user    FOREIGN KEY (user_id)    REFERENCES users(id)             ON DELETE RESTRICT
);
COMMENT ON TABLE project_members IS 'Thành viên đề tài n-n (FR-HR-010). PK kép chống trùng (BR-HR-016). ON DELETE CASCADE theo đề tài (xóa đề tài gỡ thành viên); user RESTRICT (giữ toàn vẹn nhân sự).';

-- ------------------------------------------------------------
-- [ TABLE 7 ] publications — bài báo / sáng chế (FR-HR-011/012)
-- ------------------------------------------------------------
CREATE TABLE publications (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    title               VARCHAR(512) NOT NULL,
    journal             VARCHAR(255) NULL,                      -- tạp chí/hội nghị (paper)
    year                SMALLINT     NULL,
    doi                 VARCHAR(255) NULL,                      -- định dạng 10.xxxx/... (validate app BR-HR-017)
    category            VARCHAR(32)  NULL,                      -- FK danh mục chỉ số (paper)
    type                VARCHAR(8)   NOT NULL DEFAULT 'paper'
        CHECK (type IN ('paper', 'patent')),
    patent_no           VARCHAR(64)  NULL,                      -- số bằng (type=patent) — UNIQUE qua partial index
    issuing_authority   VARCHAR(255) NULL,                      -- cơ quan cấp (type=patent)
    department_id       UUID         NULL,                      -- thống kê phòng (D12, BR-HR-022)
    created_by          UUID         NULL,
    updated_by          UUID         NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_pub_category FOREIGN KEY (category)      REFERENCES publication_categories(code) ON DELETE RESTRICT,
    CONSTRAINT fk_pub_dept     FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
    CONSTRAINT fk_pub_created  FOREIGN KEY (created_by)     REFERENCES users(id)      ON DELETE RESTRICT,
    CONSTRAINT fk_pub_updated  FOREIGN KEY (updated_by)     REFERENCES users(id)      ON DELETE RESTRICT,
    -- sáng chế phải có số bằng; bài báo không cần patent_no
    CONSTRAINT ck_pub_patent_no CHECK (type <> 'patent' OR (patent_no IS NOT NULL AND length(btrim(patent_no)) > 0))
);
COMMENT ON TABLE publications IS 'Bài báo (type=paper) + sáng chế/giải pháp hữu ích (type=patent) (FR-HR-011/012, R17). category FK danh mục chỉ số (D5). patent_no UNIQUE khi patent (uq_pub_patent_no partial index).';

-- ------------------------------------------------------------
-- [ TABLE 8 ] publication_authors — đồng tác giả n-n + thứ tự (FR-HR-011, BR-HR-018, D7)
--   PK(publication_id, author_order) → thứ tự duy nhất/bài. Hỗ trợ tác giả ngoài hệ thống.
-- ------------------------------------------------------------
CREATE TABLE publication_authors (
    publication_id  UUID         NOT NULL,
    author_order    SMALLINT     NOT NULL CHECK (author_order >= 1), -- 1 = tác giả chính/đầu
    user_id         UUID         NULL,                          -- tác giả nội bộ (D7)
    external_name   VARCHAR(255) NULL,                          -- tác giả ngoài hệ thống (D7, OQ#8c)
    is_corresponding BOOLEAN     NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT pk_pub_authors PRIMARY KEY (publication_id, author_order), -- BR-HR-018 thứ tự duy nhất
    CONSTRAINT fk_pa_publication FOREIGN KEY (publication_id) REFERENCES publications(id) ON DELETE CASCADE,
    CONSTRAINT fk_pa_user        FOREIGN KEY (user_id)        REFERENCES users(id)        ON DELETE RESTRICT,
    -- XOR: đúng 1 trong (user_id, external_name) NOT NULL (D7)
    CONSTRAINT ck_pa_author_xor CHECK (
        (user_id IS NOT NULL AND external_name IS NULL)
        OR (user_id IS NULL AND external_name IS NOT NULL)
    )
);
COMMENT ON TABLE publication_authors IS 'Đồng tác giả n-n + thứ tự (FR-HR-011/012). PK(publication_id, author_order) đảm bảo author_order duy nhất/bài (BR-HR-018). XOR user_id/external_name hỗ trợ tác giả ngoài hệ thống (D7, OQ#8c).';

-- ------------------------------------------------------------
-- [ TABLE 9 ] student_mentorships — hướng dẫn SV (FR-HR-014)
-- ------------------------------------------------------------
CREATE TABLE student_mentorships (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    mentor_id       UUID         NOT NULL,                      -- người hướng dẫn (FK→users)
    student_name    VARCHAR(255) NOT NULL,                      -- SV ngoài hệ thống → free-text
    topic           VARCHAR(512) NULL,
    year            SMALLINT     NULL,
    type            VARCHAR(32)  NULL,                          -- FK danh mục loại hướng dẫn
    department_id   UUID         NULL,                          -- suy từ mentor (D12)
    created_by      UUID         NULL,
    updated_by      UUID         NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_sm_mentor  FOREIGN KEY (mentor_id)     REFERENCES users(id)            ON DELETE RESTRICT,
    CONSTRAINT fk_sm_type    FOREIGN KEY (type)          REFERENCES mentorship_types(code) ON DELETE RESTRICT,
    CONSTRAINT fk_sm_dept    FOREIGN KEY (department_id) REFERENCES departments(id)      ON DELETE RESTRICT,
    CONSTRAINT fk_sm_created FOREIGN KEY (created_by)     REFERENCES users(id)            ON DELETE RESTRICT,
    CONSTRAINT fk_sm_updated FOREIGN KEY (updated_by)     REFERENCES users(id)            ON DELETE RESTRICT
);
COMMENT ON TABLE student_mentorships IS 'Hướng dẫn SV (FR-HR-014, R18). student_name free-text (SV không phải user nội bộ). type FK danh mục (BR-HR-020).';

-- ------------------------------------------------------------
-- [ TABLE 10 ] lab_registrations — lượt SV đăng ký lab CÓ DUYỆT (FR-HR-015, D6)
-- ------------------------------------------------------------
CREATE TABLE lab_registrations (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    student_name    VARCHAR(255) NOT NULL,                      -- người đăng ký (SV) free-text
    mentor_id       UUID         NOT NULL,                      -- người hướng dẫn phụ trách (FK→users)
    registered_at   DATE         NOT NULL DEFAULT CURRENT_DATE, -- ngày đăng ký
    registered_from DATE         NULL,                          -- khoảng thời gian thực tập (tùy chọn)
    registered_to   DATE         NULL,
    purpose         TEXT         NULL,                          -- mục đích (thực tập/dùng thiết bị)
    status          VARCHAR(12)  NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')), -- D6 CÓ duyệt (QUYẾT ĐỊNH #2)
    approved_by     UUID         NULL,                          -- người duyệt (lãnh đạo/trưởng nhóm)
    approved_at     TIMESTAMPTZ  NULL,
    department_id   UUID         NULL,                          -- suy từ mentor (D12)
    created_by      UUID         NULL,
    updated_by      UUID         NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_lr_mentor   FOREIGN KEY (mentor_id)     REFERENCES users(id)       ON DELETE RESTRICT,
    CONSTRAINT fk_lr_approved FOREIGN KEY (approved_by)   REFERENCES users(id)       ON DELETE RESTRICT,
    CONSTRAINT fk_lr_dept     FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
    CONSTRAINT fk_lr_created  FOREIGN KEY (created_by)     REFERENCES users(id)       ON DELETE RESTRICT,
    CONSTRAINT fk_lr_updated  FOREIGN KEY (updated_by)     REFERENCES users(id)       ON DELETE RESTRICT,
    CONSTRAINT ck_lr_date_order CHECK (registered_to IS NULL OR registered_from IS NULL OR registered_to >= registered_from),
    -- nhất quán: approved/rejected phải có người duyệt + thời điểm
    CONSTRAINT ck_lr_approval CHECK (
        (status = 'pending'  AND approved_by IS NULL AND approved_at IS NULL)
        OR (status IN ('approved', 'rejected') AND approved_by IS NOT NULL AND approved_at IS NOT NULL)
    )
);
COMMENT ON TABLE lab_registrations IS 'Lượt SV đăng ký lab CÓ DUYỆT (FR-HR-015, D6 QUYẾT ĐỊNH #2). status pending→approved/rejected (state machine app). Chỉ approved tính thống kê (BR-HR-021). ck_lr_approval đảm bảo nhất quán approved_by/at.';

-- ------------------------------------------------------------
-- [ TABLE 11 ] teaching_courses — môn học giảng dạy (FR-HR-016)
-- ------------------------------------------------------------
CREATE TABLE teaching_courses (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID         NOT NULL,                      -- giảng viên/nhân sự phụ trách
    course_name     VARCHAR(255) NOT NULL,
    semester        VARCHAR(32)  NULL,                          -- học kỳ (vd 'HK1')
    year            SMALLINT     NULL,
    department_id   UUID         NULL,                          -- suy từ user (D12)
    created_by      UUID         NULL,
    updated_by      UUID         NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_tc_user    FOREIGN KEY (user_id)       REFERENCES users(id)       ON DELETE RESTRICT,
    CONSTRAINT fk_tc_dept    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
    CONSTRAINT fk_tc_created FOREIGN KEY (created_by)     REFERENCES users(id)       ON DELETE RESTRICT,
    CONSTRAINT fk_tc_updated FOREIGN KEY (updated_by)     REFERENCES users(id)       ON DELETE RESTRICT,
    -- tránh trùng (user + môn + học kỳ + năm) — BR-HR-020
    CONSTRAINT uq_tc_user_course_term UNIQUE (user_id, course_name, semester, year)
);
COMMENT ON TABLE teaching_courses IS 'Môn học giảng dạy (FR-HR-016, R19). UNIQUE(user,course,semester,year) tránh đếm trùng (BR-HR-020).';

-- ------------------------------------------------------------
-- [ TABLE 12 ] community_services — phục vụ cộng đồng (FR-HR-017)
-- ------------------------------------------------------------
CREATE TABLE community_services (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    content             TEXT         NOT NULL,                  -- nội dung hoạt động
    performed_at        DATE         NULL,                      -- thời gian thực hiện
    host                VARCHAR(255) NULL,                      -- đơn vị/tổ chức chủ trì
    performer_user_id   UUID         NOT NULL,                  -- người thực hiện (FK→users)
    department_id       UUID         NULL,                      -- suy từ performer (D12)
    created_by          UUID         NULL,
    updated_by          UUID         NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_cs_performer FOREIGN KEY (performer_user_id) REFERENCES users(id)       ON DELETE RESTRICT,
    CONSTRAINT fk_cs_dept      FOREIGN KEY (department_id)     REFERENCES departments(id) ON DELETE RESTRICT,
    CONSTRAINT fk_cs_created   FOREIGN KEY (created_by)        REFERENCES users(id)       ON DELETE RESTRICT,
    CONSTRAINT fk_cs_updated   FOREIGN KEY (updated_by)        REFERENCES users(id)       ON DELETE RESTRICT
);
COMMENT ON TABLE community_services IS 'Phục vụ cộng đồng (FR-HR-017, R20). performer_user_id = người thực hiện; host = đơn vị chủ trì.';
```

---

## 3. CHECK constraints & toàn vẹn quan trọng — tổng hợp & ghi chú enforce

| Quy tắc (BR/FR) | Constraint | DB enforce? | Ghi chú |
|---------|-----------|:-----------:|---------|
| 1-1 hồ sơ ↔ user (BR-HR-001) | `hr_profiles.user_id` PK = FK→users | ✅ | PK đảm bảo 1-1; không cần UNIQUE phụ (D3). 409 `HR_PROFILE_EXISTS` ở app khi INSERT trùng PK. |
| Chức danh bắt buộc (BR-HR-006) | `job_title NOT NULL` | ✅ | 400 `VALIDATION_ERROR`. |
| Tiền NUMERIC không float (CONSTRAINT-6) | `NUMERIC(6,2)`/`NUMERIC(14,2)` | ✅ | NFR-COMPAT-HR-001. coefficient(6,2), base/lịch sử(14,2). |
| Hệ số/lương ≥ 0 (FR-HR-004 A2) | CHECK coefficient>0, base_amount≥0 | ✅ | 400 `INVALID_SALARY` ở app khi ≤ 0. |
| HĐ end > signed (BR-HR-007) | `ck_hrp_contract_date_order` | ✅ | 422 `INVALID_DATE_ORDER`. |
| `salary_cycle_years` ≥ 1, default 3 (BR-HR-011, C04) | CHECK ≥1 + DEFAULT 3 | ✅ | 400 `INVALID_CYCLE`. |
| `next_salary_raise_date` tự tính (BR-HR-005, CONSTRAINT-2) | — cột thường | ⚠️ **app-layer** | D9: app tính trong txn; 29/02→28/02; NULL nếu thiếu base (BR-HR-010). KHÔNG trigger (dễ test NFR-CORRECT-HR-001). |
| Lịch sử lương immutable (BR-HR-008, §8.4) | — không route UPDATE/DELETE | ⚠️ **app-layer** | D8 đồng bộ M2 (không trigger; app không expose route). 404/405. |
| Năng lực date order (FR-HR-007 A2) | `ck_comp_date_order` | ✅ | 422 `INVALID_DATE_ORDER`. |
| Năng lực hết hạn (FR-HR-007 A1) | — | ⚠️ **app-layer** | expiry_date < today → app đánh dấu `expired` (không cron — OQ#11 nếu thêm cron = CR). |
| Cron dedup 1/(hồ sơ×mốc×ngày) (BR-HR-013) | `uq_hrdedup` | ✅ | Idempotent NFR-CRON-HR-001. INSERT ... ON CONFLICT DO NOTHING ở cron. |
| Đề tài có đúng 1 chủ nhiệm (BR-HR-016) | `lead_user_id NOT NULL` | ✅ | 400 `LEAD_REQUIRED`. "Đúng 1" enforce bởi cột đơn (1 lead/đề tài). |
| Không trùng thành viên đề tài (BR-HR-016) | `pk_project_members(project_id,user_id)` | ✅ | 409 trùng thành viên. |
| Đề tài date order | `ck_rp_date_order` | ✅ | 422 `INVALID_DATE_ORDER`. |
| Cấp đề tài/chỉ số/loại HD ∈ danh mục (BR-HR-015) | FK→danh mục(code) RESTRICT | ✅ | 400 `INVALID_PROJECT_LEVEL`/`INVALID_INDEX`/`INVALID_MENTORSHIP_TYPE` ở app trước INSERT. |
| `author_order` duy nhất/bài (BR-HR-018) | `pk_pub_authors(publication_id,author_order)` | ✅ | 422 `DUPLICATE_AUTHOR_ORDER`. |
| Tác giả nội bộ HOẶC ngoài (D7) | `ck_pa_author_xor` | ✅ | Đúng 1 trong (user_id, external_name). |
| Số bằng sáng chế bắt buộc + duy nhất (BR-HR-019) | `ck_pub_patent_no` + `uq_pub_patent_no` (partial index §4) | ✅ | 409 `DUPLICATE_PATENT_NO`. |
| Đăng ký lab có duyệt nhất quán (D6) | `ck_lr_approval` | ✅ | approved/rejected ⟺ approved_by+at NOT NULL. |
| Tránh trùng môn học (BR-HR-020) | `uq_tc_user_course_term` | ✅ | 409/cảnh báo. |
| Field-level RBAC lương + PII (BR-HR-002/003, CONSTRAINT-3) | — | ⚠️ **app-layer** | NFR-SEC-HR-001 cốt lõi: strip cột lương/PII ở serializer theo người gọi (đồng bộ M2 BR-CHEM-022). Quyền SỬA lương = accountant+admin (QUYẾT ĐỊNH #1). |
| Audit mọi thay đổi + lọc PII (BR-HR-004/024) | — | ⚠️ **app-layer** | NFR-AUDIT/SEC-HR-002: service ghi audit_logs, detail KHÔNG chứa giá trị lương/PII. |
| Scope đọc thành tích (BR-HR-023) | — | ⚠️ **app-layer** | Admin/leader=all, staff=own; accountant KHÔNG research. RBAC guard thêm WHERE. |
| Validate DOI/file (BR-HR-012/017) | — | ⚠️ **app-layer** | DOI `10.xxxx/`; file PDF/PNG/JPG ≤ giới hạn (OQ#12) — NFR-SEC-HR-003 (đồng bộ M2 BR-CHEM-013). |

> **Tinh thần đồng bộ M7/M1/M2:** CHECK DB giữ ràng buộc **giá trị** (NOT NULL, enum, date order, XOR, UNIQUE, n-n PK kép). Logic nghiệp vụ/bảo mật phức (tính ngày nâng lương, field-level lương, immutable lịch sử, dedup ON CONFLICT, scope) enforce **app-layer** với mã lỗi rõ ràng — giống M2 (BR-CHEM-028) và M1 (state machine).

---

## 4. Index strategy

```sql
-- ===== hr_profiles =====
-- CRON-3: quét hồ sơ tới hạn nâng lương — partial bỏ NULL (BR-HR-010) → index nhỏ, đúng đối tượng quét
CREATE INDEX idx_hrp_next_raise   ON hr_profiles(next_salary_raise_date) WHERE next_salary_raise_date IS NOT NULL;
-- CRON-4: quét hồ sơ hết hạn HĐ — partial bỏ NULL (HĐ vô thời hạn — BR-HR-009)
CREATE INDEX idx_hrp_contract_end ON hr_profiles(contract_end_date)      WHERE contract_end_date IS NOT NULL;
CREATE INDEX idx_hrp_contract_type ON hr_profiles(contract_type)         WHERE contract_type IS NOT NULL;  -- FK + lọc loại HĐ
-- (phòng ban nhân sự suy qua users.department_id — idx_users_department đã có ở M7; không nhân bản ở đây)

-- ===== salary_history =====
CREATE INDEX idx_sh_user_date ON salary_history(user_id, raise_date DESC);  -- FK + xem lịch sử lương 1 người mới nhất trước

-- ===== competences =====
CREATE INDEX idx_comp_user        ON competences(user_id);                   -- FK + năng lực của 1 nhân sự
CREATE INDEX idx_comp_kind        ON competences(user_id, kind);             -- lọc bằng/chứng chỉ/ủy quyền của 1 người
CREATE INDEX idx_comp_expiry      ON competences(expiry_date) WHERE expiry_date IS NOT NULL; -- soát năng lực hết hạn (OQ#11 nếu thêm cron)
CREATE INDEX idx_comp_authorized  ON competences(authorized_by) WHERE authorized_by IS NOT NULL; -- FK

-- ===== hr_notification_dedup =====
-- uq_hrdedup (profile_user_id, kind, milestone_days, fire_date) đã là composite index — đủ cho cron check "đã fire chưa"

-- ===== research_projects =====
CREATE INDEX idx_rp_lead       ON research_projects(lead_user_id);            -- FK + thống kê chủ nhiệm (cá nhân)
CREATE INDEX idx_rp_dept       ON research_projects(department_id) WHERE department_id IS NOT NULL;  -- thống kê phòng (BR-HR-022)
CREATE INDEX idx_rp_level      ON research_projects(level) WHERE level IS NOT NULL;  -- FK + thống kê theo cấp
CREATE INDEX idx_rp_dept_dates ON research_projects(department_id, start_date);      -- thống kê phòng × khoảng thời gian (FR-HR-018)
-- uq_rp_code đã tạo unique index (mã đề tài)

-- ===== project_members =====
-- pk_project_members(project_id, user_id) phủ join từ đề tài. Thêm chiều ngược cho "đề tài của 1 user" (thống kê cá nhân):
CREATE INDEX idx_pm_user ON project_members(user_id);

-- ===== publications =====
CREATE INDEX idx_pub_dept     ON publications(department_id) WHERE department_id IS NOT NULL;  -- thống kê phòng
CREATE INDEX idx_pub_category ON publications(category) WHERE category IS NOT NULL;            -- FK + thống kê theo chỉ số
CREATE INDEX idx_pub_year     ON publications(year) WHERE year IS NOT NULL;                    -- thống kê theo năm (FR-HR-018)
CREATE INDEX idx_pub_type     ON publications(type);                                           -- tách bài báo / sáng chế
-- số bằng sáng chế duy nhất (chỉ áp khi type=patent — partial unique, BR-HR-019)
CREATE UNIQUE INDEX uq_pub_patent_no ON publications(patent_no) WHERE type = 'patent' AND patent_no IS NOT NULL;

-- ===== publication_authors =====
-- pk_pub_authors(publication_id, author_order) phủ join từ bài. Chiều ngược "bài của 1 tác giả" (thống kê cá nhân):
CREATE INDEX idx_pa_user ON publication_authors(user_id) WHERE user_id IS NOT NULL;

-- ===== student_mentorships =====
CREATE INDEX idx_sm_mentor_year ON student_mentorships(mentor_id, year);                   -- thống kê hướng dẫn theo người + năm
CREATE INDEX idx_sm_dept        ON student_mentorships(department_id) WHERE department_id IS NOT NULL;  -- theo phòng
CREATE INDEX idx_sm_type        ON student_mentorships(type) WHERE type IS NOT NULL;        -- FK

-- ===== lab_registrations =====
CREATE INDEX idx_lr_mentor      ON lab_registrations(mentor_id);                            -- FK + lượt của 1 người hướng dẫn
CREATE INDEX idx_lr_dept_status ON lab_registrations(department_id, status);                -- thống kê phòng (chỉ approved — BR-HR-021)
CREATE INDEX idx_lr_status      ON lab_registrations(status) WHERE status = 'pending';      -- hàng chờ duyệt (D6)
CREATE INDEX idx_lr_registered  ON lab_registrations(registered_at);                        -- thống kê theo kỳ

-- ===== teaching_courses =====
CREATE INDEX idx_tc_user_year ON teaching_courses(user_id, year);                           -- thống kê giảng dạy theo người + năm
CREATE INDEX idx_tc_dept      ON teaching_courses(department_id) WHERE department_id IS NOT NULL;

-- ===== community_services =====
CREATE INDEX idx_cs_performer ON community_services(performer_user_id);                      -- FK + thống kê cá nhân
CREATE INDEX idx_cs_dept      ON community_services(department_id) WHERE department_id IS NOT NULL;
CREATE INDEX idx_cs_performed ON community_services(performed_at) WHERE performed_at IS NOT NULL;  -- theo kỳ
```

**Lý do nhóm index trọng yếu (theo yêu cầu):**
- **`hr_profiles.next_salary_raise_date`** — `idx_hrp_next_raise` (partial NOT NULL): **CRON-3** quét hằng ngày hồ sơ tới mốc 15/7/3 ngày. Partial loại hồ sơ NULL (chưa có base — BR-HR-010) → index nhỏ, quét đúng đối tượng (NFR-CRON-HR-001).
- **`hr_profiles.contract_end_date`** — `idx_hrp_contract_end` (partial NOT NULL): **CRON-4** quét mốc 30/15/7 ngày; partial bỏ HĐ vô thời hạn (BR-HR-009).
- **`lead_user_id` / `project_members.user_id` / `publication_authors.user_id` / `performer_user_id` / `mentor_id`** — thống kê **cá nhân** (FR-HR-013/018): "đề tài/bài báo/hoạt động của 1 người" join nhanh. PK kép n-n đã phủ chiều từ cha → thêm index chiều ngược cho thống kê cá nhân.
- **`department_id` (mọi bảng thành tích)** — thống kê **phòng** (BR-HR-022); partial NOT NULL gom riêng "không gắn phòng". Composite `(department_id, start_date/year/status)` cho thống kê phòng × thời gian/trạng thái (FR-HR-018).
- **`year` (publications, qua composite mentor/tc/lr)** — thống kê theo **khoảng thời gian** (FR-HR-018 chiều thời gian).
- **`uq_pub_patent_no` partial (type='patent')** — số bằng duy nhất chỉ áp cho sáng chế, không chặn bài báo (BR-HR-019).

> **Không over-index:** KHÔNG index `title`/`journal`/`doi`/`note`/`purpose`/`content`/`scope_detail` (text dài, không WHERE chọn lọc cao). KHÔNG index cột lương (không dùng làm điều kiện lọc; bảo mật). Quy mô ~40 user (C03): thành tích vài nghìn bản ghi — index trên đủ; thống kê nặng (FR-HR-018) có thể cache/materialized view nếu NFR-PERF-HR-002 vượt 3s (ghi chú §8). Cân nhắc `pg_trgm` cho tìm `publications.title`/`student_name` nếu KH cần search free-text (chưa thêm — chờ xác nhận).

---

## 5. Seed data — 4 bảng danh mục (D5; giá trị mặc định QUYẾT ĐỊNH #3, cấu hình được)

> **Lưu ý:** giá trị chính xác do KH chốt (OQ#3/#5/#6/#7); seed dưới là **mặc định hợp lý** theo QUYẾT ĐỊNH #3, admin thêm/ẩn sau (is_active). Idempotent `ON CONFLICT (code) DO NOTHING` (đồng bộ seed units M2).

```sql
-- ===== contract_types (OQ#3) =====
INSERT INTO contract_types (code, label, sort_order) VALUES
    ('probation',   'Hợp đồng thử việc',                 1),
    ('fixed_term',  'Hợp đồng xác định thời hạn',        2),
    ('indefinite',  'Hợp đồng không xác định thời hạn',  3),
    ('civil_servant','Viên chức / biên chế',             4),
    ('collaborator','Cộng tác viên / thỉnh giảng',       5)
ON CONFLICT (code) DO NOTHING;

-- ===== research_project_levels — cấp đề tài (QUYẾT ĐỊNH #3, OQ#5) =====
INSERT INTO research_project_levels (code, label, sort_order) VALUES
    ('institution', 'Cấp Cơ sở',        1),
    ('university',  'Cấp Trường',       2),
    ('ministry',    'Cấp Bộ',           3),
    ('province',    'Cấp Tỉnh',         4),
    ('national',    'Cấp Nhà nước',     5),
    ('international','Cấp Quốc tế / Hợp tác quốc tế', 6)
ON CONFLICT (code) DO NOTHING;

-- ===== publication_categories — phân loại/chỉ số bài báo (QUYẾT ĐỊNH #3, OQ#6) =====
INSERT INTO publication_categories (code, label, sort_order) VALUES
    ('isi_q1',    'ISI Q1',              1),
    ('isi_q2',    'ISI Q2',              2),
    ('isi_q3',    'ISI Q3',              3),
    ('isi_q4',    'ISI Q4',              4),
    ('scopus',    'Scopus',              5),
    ('domestic',  'Tạp chí trong nước',  6),
    ('conference','Kỷ yếu hội nghị',     7)
ON CONFLICT (code) DO NOTHING;

-- ===== mentorship_types — loại hướng dẫn SV (OQ#7) =====
INSERT INTO mentorship_types (code, label, sort_order) VALUES
    ('thesis_bachelor', 'Khóa luận tốt nghiệp (ĐH)',  1),
    ('thesis_master',   'Luận văn Thạc sĩ',           2),
    ('thesis_phd',      'Luận án Tiến sĩ',            3),
    ('student_research','NCKH sinh viên',             4),
    ('project',         'Đồ án môn học / chuyên ngành',5)
ON CONFLICT (code) DO NOTHING;
```

> **Lương cơ sở:** KHÔNG seed bảng cấu hình lương cơ sở riêng. Theo D4, `base_salary_amount` lưu **tại từng hồ sơ** (snapshot — lương cơ sở nhà nước đổi theo nghị định, mỗi hồ sơ chốt mức áp dụng tại thời điểm nâng lương). Nếu KH muốn 1 mức lương cơ sở dùng chung toàn hệ thống tự áp → cần CR thêm bảng `salary_base_config(effective_from, amount)` (ghi chú §8). Mặc định mức lương cơ sở do accountant nhập khi tạo/sửa hồ sơ.
> **Quyền M4 (`hr:read`/`hr:manage`/`research:manage`)** đã seed đủ ở M7 §5.2 — M4 **KHÔNG** thêm `roles_permissions` (khác M2 phải bổ sung `chemical:create`). RBAC field-level lương + scope research enforce app-layer.

---

## 6. Traceability — Map bảng/cột → FR/BR

| Bảng / cột | FR | BR | QUYẾT ĐỊNH chốt |
|------------|-----|-----|------|
| `hr_profiles` (1-1 user_id PK=FK) | FR-HR-001/002 | BR-HR-001 | D3 |
| `hr_profiles.job_title` | FR-HR-001 | BR-HR-006 | |
| `hr_profiles.contract_type/signed/end` | FR-HR-003 | BR-HR-007/009 | #2 (đăng ký) không liên quan; CRON-4 nguồn |
| `hr_profiles.salary_grade/coefficient/base_salary_amount/currency` | FR-HR-004 | BR-HR-002/003 | **#1 (lương = hệ số × cơ sở, D4)** |
| `hr_profiles.salary_cycle_years/last/next_salary_raise_date` | FR-HR-005/006 | BR-HR-005/010/011 | C04 default 3; D9 app tính |
| `salary_history` (append-only, snapshot) | FR-HR-004 | BR-HR-008 | D4/D8 |
| `competences` (degree/certificate/authorization) | FR-HR-007/019/020 | BR-HR-004/012 | §6.2 |
| `competences.scope_detail/authorized_by` | FR-HR-007 | BR-HR-004 | ủy quyền thử nghiệm §6.2 |
| `hr_notification_dedup` | FR-HR-008/009 | BR-HR-013 | D10 (đồng bộ M2) |
| `research_projects` + `project_members` | FR-HR-010/013 | BR-HR-015/016/022 | #3 (level danh mục) |
| `publications` + `publication_authors` | FR-HR-011/012/013 | BR-HR-017/018/019/022 | **#3 (category danh mục); D7 (tác giả ngoài)** |
| `student_mentorships` | FR-HR-014 | BR-HR-020/022 | #3 (type danh mục) |
| `lab_registrations` (status/approved_by/approved_at/mentor_id) | FR-HR-015 | BR-HR-021/022 | **#2 (CÓ duyệt, D6)** |
| `teaching_courses` | FR-HR-016 | BR-HR-020/022 | |
| `community_services` | FR-HR-017 | BR-HR-022 | |
| `*.department_id` (mọi bảng thành tích) | FR-HR-013/018 | BR-HR-022/023 | D12 |
| `contract_types`/`research_project_levels`/`publication_categories`/`mentorship_types` | FR-HR-003/010/011/014 | BR-HR-015 | **#3 (bảng danh mục cấu hình được, D5)** |
| Field-level strip lương/PII (serializer) | FR-HR-001/004/018 | BR-HR-002/003/024 | #1 quyền sửa; app-layer |
| Thống kê 3 chiều (cá nhân/phòng/năm) | FR-HR-018/019/020 | BR-HR-022/023 | index §4 |

**Mapping cron:** FR-HR-008 ↔ CRON-3 (`SALARY_RAISE_DUE`, mốc 15/7/3, quét `next_salary_raise_date`); FR-HR-009 ↔ CRON-4 (`CONTRACT_EXPIRY`, mốc 30/15/7, quét `contract_end_date`). Dedup qua `hr_notification_dedup` + `ON CONFLICT DO NOTHING`.
**Mapping 17025:** §6.2 (năng lực/ủy quyền) → `competences` + audit `HR_COMPETENCE_CHANGE`; §8.4 (kiểm soát hồ sơ) → `salary_history` append-only + audit mọi thay đổi.

---

## 7. Ghi chú cho dev (BẮT BUỘC đọc)

### 7.1 Revision Alembic
- **File:** `alembic/versions/1718870400004_m4_hr.py`
- `revision = "1718870400004"`, `down_revision = "1718870400003"` (M7→M1→M2→**M4**).
- DDL raw SQL `op.execute("...")` khớp chính xác contract (đồng bộ phong cách M7/M1/M2). `CREATE EXTENSION IF NOT EXISTS pgcrypto` đầu file (an toàn nếu chạy độc lập; đã bật M7).
- Seed danh mục dùng `ON CONFLICT (code) DO NOTHING` (idempotent — như units M2). **KHÔNG** seed `roles_permissions` (M7 đã đủ quyền M4).
- Model ORM mới: thêm vào `app/models/__init__.py` (`HrProfile, SalaryHistory, Competence, HrNotificationDedup, ResearchProject, ProjectMember, Publication, PublicationAuthor, StudentMentorship, LabRegistration, TeachingCourse, CommunityService, ContractType, ResearchProjectLevel, PublicationCategory, MentorshipType`) để Alembic metadata thấy đầy đủ.

### 7.2 Tính `next_salary_raise_date` ở app-layer (D9, BR-HR-005 — KHÔNG trigger)
```python
from dateutil.relativedelta import relativedelta  # xử lý cộng-năm an toàn 29/02 → 28/02

def compute_next_salary_raise_date(profile) -> date | None:
    base = profile.last_salary_raise_date or profile.contract_signed_date
    if base is None:
        return None                                  # BR-HR-010 → CRON-3 bỏ qua
    return base + relativedelta(years=profile.salary_cycle_years)  # 29/02 + n năm → 28/02 tự động
```
- Gọi trong **cùng transaction** mỗi khi đổi `last_salary_raise_date` (ghi nâng lương FR-HR-004), `contract_signed_date` (FR-HR-003), `salary_cycle_years` (FR-HR-006). Test property-based theo NFR-CORRECT-HR-001 (gồm 29/02 × cycle 1..5).

### 7.3 Field-level RBAC lương/PII (BR-HR-002/003, NFR-SEC-HR-001 — CỐT LÕI, đồng bộ M2 strip giá)
- **Cột tài chính cần strip:** `salary_grade`, `salary_coefficient`, `base_salary_amount`, + toàn bộ `salary_history`. Strip ở **serializer/response layer**, không chỉ ẩn FE.
- **Người được xem lương:** admin / leader / accountant (toàn hệ thống) + **chính chủ** (staff xem `user_id == current_user.id`). Mọi trường hợp khác → response KHÔNG chứa cột lương (kể cả trong danh sách + thống kê + export).
- **Quyền SỬA lương (ghi `salary_history`, đổi grade/coefficient/base) = chỉ accountant + admin** (QUYẾT ĐỊNH #1 đã chốt). Leader chỉ XEM. Enforce ở guard/service, 403 nếu vi phạm. (SRS để OQ#1, nhưng task đã chốt accountant+admin → áp luôn.)
- Audit `HR_SALARY_RAISE` ghi fact, **KHÔNG ghi giá trị lương** vào `audit_logs.detail`/log/Sentry (BR-HR-024, NFR-SEC-HR-002).

### 7.4 Immutable `salary_history` (D8, §8.4) — đồng bộ M2 `chemical_transactions`
- KHÔNG tạo route PUT/PATCH/DELETE cho `salary_history`. Sửa sai = thêm bản ghi điều chỉnh mới. (Không thêm trigger DB — giữ nhất quán phong cách M1/M2 enforce app-layer.)

### 7.5 Cron dedup (D10, NFR-CRON-HR-001)
- CRON-3/4 INSERT vào `hr_notification_dedup` với `ON CONFLICT (profile_user_id, kind, milestone_days, fire_date) DO NOTHING` TRƯỚC khi tạo `notifications`; chỉ tạo notification nếu INSERT trả về row (idempotent + Redis lock như M2 CRON-6). Người nhận CRON-3 = HR + chính nhân sự + lãnh đạo; CRON-4 = HR (BR-HR-014) — dedup chỉ theo hồ sơ, fan-out nhiều `notifications` cho từng người nhận trong cùng lần fire.

### 7.6 Đính kèm (D11)
- Bằng cấp/chứng chỉ/HĐ scan → `attachments(owner_type='hr_profile', owner_id=user_id)`. Minh chứng bài báo/sáng chế → `attachments(owner_type='publication', owner_id=publications.id)`. Whitelist đã có trong M7. App kiểm tra owner tồn tại trước khi gắn (polymorphic không FK cứng). Validate file PDF/PNG/JPG ≤ giới hạn (OQ#12, NFR-SEC-HR-003).

---

## 8. Điểm cần Tech Lead chú ý (review trước APPROVED)

1. **Cấu trúc lương = hệ số × lương cơ sở (D4 — đã chốt QUYẾT ĐỊNH #1).** `base_salary_amount` lưu **tại từng hồ sơ** (snapshot). Nếu KH muốn 1 mức lương cơ sở dùng chung toàn hệ thống (tự áp + đổi theo nghị định) → **CR thêm bảng `salary_base_config(effective_from DATE, amount NUMERIC(14,2))`** và app resolve mức theo ngày. SRS OQ#2 vẫn để ngỏ "số tuyệt đối vs hệ số" — task đã chốt hệ số; cần KH ký xác nhận trước APPROVED.
2. **Quyền SỬA lương = accountant + admin (đã chốt #1), leader chỉ xem.** SRS để OQ#1 ngỏ. Đã phản ánh app-layer (§7.3). Cần confirm KH ký để khớp SRS.
3. **Tác giả ngoài hệ thống (D7):** `publication_authors` cho phép `external_name` free-text (OQ#8c). Đề tài (`project_members`) giữ FK chặt (chỉ user nội bộ). Nếu KH muốn đề tài cũng có thành viên ngoài → cần mở rộng tương tự (ALTER thêm cột + đổi PK). Đợi OQ#8c.
4. **Đăng ký lab có duyệt (D6 — đã chốt #2):** state machine pending→approved/rejected enforce app. Người duyệt (lãnh đạo/trưởng nhóm phòng) xác định qua `departments.lead_user_id` + RBAC — confirm ai duyệt (OQ#8 đã chốt CÓ duyệt; ai duyệt cần khớp RBAC).
5. **`next_salary_raise_date` app-tính, không trigger (D9):** nếu Tech Lead muốn defense-in-depth có thể thêm GENERATED/trigger, nhưng sẽ phá test property-based + khó xử lý 29/02. Khuyến nghị giữ app-layer (đồng bộ M1/M2).
6. **PII (OQ#2b chưa chốt):** schema hiện CHƯA thêm cột CMND/CCCD/số TK NH/ngày sinh (chờ KH chốt cột nào + chính sách mã hóa). Khi chốt → ALTER thêm cột nhạy cảm + áp field-level strip như lương. Hiện chỉ có `phone` (không nhạy cảm cao). Non-breaking khi thêm sau.
7. **Thống kê nặng (FR-HR-018, NFR-PERF-HR-002 < 3s):** với ~40 user/vài nghìn bản ghi, index §4 đủ. Nếu vượt → materialized view tổng hợp theo (department_id, year) refresh định kỳ. Không làm sớm (YAGNI).
8. **`competences` hết hạn:** chỉ đánh dấu `expired` ở app (FR-HR-007 A1). Cron nhắc năng lực hết hạn (OQ#11) = **CR mới** (cron mới ngoài CRON-3/4) — đã chừa `idx_comp_expiry`.

---

## 9. Migration & Rollback

### New tables (16): thứ tự CREATE
`contract_types`, `research_project_levels`, `publication_categories`, `mentorship_types` (4 danh mục) → `hr_profiles` → `salary_history` → `competences` → `hr_notification_dedup` → `research_projects` → `project_members` → `publications` → `publication_authors` → `student_mentorships` → `lab_registrations` → `teaching_courses` → `community_services`.

### Existing table changes
**KHÔNG** — M4 không ALTER bảng M7/M1/M2. `attachments.owner_type` whitelist đã có `'hr_profile'`/`'publication'` (M7 §2); `roles_permissions` đã đủ quyền M4 (M7 §5.2). **Non-breaking** với module hiện có.

### Rollback (downgrade) — drop NGƯỢC thứ tự FK
```sql
DROP TABLE IF EXISTS community_services       CASCADE;
DROP TABLE IF EXISTS teaching_courses         CASCADE;
DROP TABLE IF EXISTS lab_registrations        CASCADE;
DROP TABLE IF EXISTS student_mentorships      CASCADE;
DROP TABLE IF EXISTS publication_authors      CASCADE;
DROP TABLE IF EXISTS publications             CASCADE;
DROP TABLE IF EXISTS project_members          CASCADE;
DROP TABLE IF EXISTS research_projects        CASCADE;
DROP TABLE IF EXISTS hr_notification_dedup    CASCADE;
DROP TABLE IF EXISTS competences              CASCADE;
DROP TABLE IF EXISTS salary_history           CASCADE;
DROP TABLE IF EXISTS hr_profiles              CASCADE;
DROP TABLE IF EXISTS mentorship_types         CASCADE;
DROP TABLE IF EXISTS publication_categories   CASCADE;
DROP TABLE IF EXISTS research_project_levels  CASCADE;
DROP TABLE IF EXISTS contract_types           CASCADE;
-- KHÔNG drop extension dùng chung (pgcrypto). KHÔNG đụng roles_permissions/attachments (không sửa).
```

### Data dependencies
- **Seed trước:** 4 bảng danh mục phải seed TRƯỚC khi tạo dữ liệu nghiệp vụ tham chiếu (FK RESTRICT). Migration seed luôn trong cùng upgrade.
- **Phụ thuộc:** mọi bảng M4 phụ thuộc `users` (M7); thành tích phụ thuộc `departments` (M7). Phải chạy SAU M7. Không phụ thuộc M1/M2 (đề tài↔mẫu là liên kết mềm OQ#9 — chưa làm).

---

*Hết Contract M4 Schema (v1.0). 16 bảng mới (4 danh mục + 12 nghiệp vụ), 0 bảng sửa. Đồng bộ tuyệt đối quy ước M7/M1/M2 (UUID PK, CHECK thay ENUM, NUMERIC không float, audit, append-only enforce app-layer, dedup table như M2). Đã phản ánh 3 QUYẾT ĐỊNH ĐÃ CHỐT: #1 lương = hệ số × lương cơ sở (quyền sửa accountant+admin), #2 đăng ký lab có duyệt, #3 danh mục dùng bảng cấu hình được. Cần Tech Lead confirm: cấu trúc lương cơ sở (snapshot vs config dùng chung), cột PII (OQ#2b), tác giả ngoài cho đề tài (OQ#8c).*
