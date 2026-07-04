# Contract — M7 Schema: Quản trị Hệ thống & Nền tảng (Auth, Org, RBAC, Audit, Notification, Attachment)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M7 — Platform / System Administration (NỀN TẢNG — migration ĐẦU TIÊN)
**Tài liệu:** Database Schema Contract (DDL + Index + Seed + Traceability)
**Version:** 1.0 | **Ngày:** 20/06/2026 | **Author:** schema-designer agent
**Stack:** PostgreSQL 15+, FastAPI + SQLAlchemy/Alembic
**Nguồn chân lý:** `01-demo-scope.md` (ERD core mục C; RBAC matrix mục B; M7.1–M7.5; R13/R15; §8.4), `03-contract-m2-schema.md` + `06-contract-m1-schema.md` (quy ước đồng bộ + danh sách "bảng dùng chung M7" mà M1/M2 cần)
**Status:** DRAFT — chờ `/contract` gate / Tech Lead review

---

## 0. Quyết định thiết kế chính (đọc trước) — đồng bộ tuyệt đối với M1/M2

| # | Quyết định | Lý do |
|---|-----------|-------|
| D1 | **PK = UUID `DEFAULT gen_random_uuid()`** cho mọi bảng (trừ danh mục natural-key). | Đồng bộ M1 D1 / M2 D1; không lộ ID tuần tự (rule API). Cần `pgcrypto`. M7 là nơi **bật extension dùng chung** (`pgcrypto`, `pg_trgm`) vì chạy migration đầu tiên. |
| D2 | **ENUM = CHECK constraint trên VARCHAR**, KHÔNG dùng native PG ENUM. | Đồng bộ M1 D2 / M2 D5: ALTER TYPE khó rollback trong Alembic. Áp cho `users.role`, `users.status`, `roles_permissions.scope`, `customers.type`, `audit_logs`... |
| D3 | **Vòng FK `users` ↔ `departments`** (`users.department_id → departments.id` và `departments.lead_user_id → users.id`) **giải quyết bằng:** tạo `departments` trước (cột `lead_user_id` NULL, **chưa** gắn FK), rồi tạo `users` (FK `department_id → departments`), cuối cùng `ALTER TABLE departments ADD CONSTRAINT fk_dept_lead ...`. | Không thể tạo 2 FK vòng trong cùng lệnh CREATE. `department_id` và `lead_user_id` đều **NULLABLE** để phá vòng phụ thuộc dữ liệu lúc seed (tạo phòng ban trước, gán trưởng nhóm sau khi có user). Chi tiết §2. |
| D4 | **RBAC = bảng dữ liệu `permissions` + `roles_permissions`** (KHÔNG hardcode trong code). Quyền tra theo `(role, resource, action)`; **phạm vi `scope` ∈ {all, department, own}** lưu trên `roles_permissions`. | demo-scope mục C ghi `roles_permissions (role, resource, action)` + mục B "RBAC + phạm vi phòng ban". Tách `permissions` (danh mục resource×action chuẩn hóa) khỏi `roles_permissions` (gán quyền+scope theo vai trò) → seed/sửa ma trận quyền không cần đổi code; audit được "ai có quyền gì". |
| D5 | **`role` là VARCHAR + CHECK 4 giá trị** (`admin`, `leader`, `accountant`, `staff`), **KHÔNG bảng `roles` riêng**. | demo-scope chốt cứng đúng 4 vai trò (mục B, 19/06/2026). Bảng `roles` riêng là over-engineering cho 4 vai trò cố định. `roles_permissions.role` dùng cùng CHECK 4 giá trị để toàn vẹn (không FK tới bảng roles). Nếu tương lai cần vai trò động → nâng cấp thành bảng `roles` (ghi chú §8). |
| D6 | **`password_hash` = bcrypt** (cost ≥ 10), lưu chuỗi `$2b$...` trong `VARCHAR(255)`. **KHÔNG bao giờ** log/insert password hay token vào `audit_logs.detail`. | rule logging.md ("KHÔNG log password/token"), NFR-SEC-002 (bcrypt cost ≥ 10, 0 plaintext). |
| D7 | **JWT access + refresh token rotation:** lưu **hash** của refresh token trong bảng `refresh_tokens` (KHÔNG lưu token thô), có `expires_at`, `revoked_at`, `rotated_from`. Access token stateless (không lưu DB). | NFR-SEC-003 (refresh TTL ≤ 30 ngày, rotation sau mỗi lần dùng). Lưu hash để nếu DB lộ vẫn không dùng được token. Rotation = INSERT bản mới + set `revoked_at` bản cũ trong cùng transaction. |
| D8 | **`audit_logs` APPEND-ONLY** (immutable): không route UPDATE/DELETE; khuyến nghị REVOKE UPDATE/DELETE khỏi app DB role + dùng `BEFORE UPDATE/DELETE` trigger chặn (defense-in-depth). `detail` = JSONB (đã lọc sensitive). | 17025 §8.4 (kiểm soát hồ sơ — không tẩy xóa), R15. Đồng bộ tinh thần immutable của `chemical_transactions` (M2) / `sample_handovers` (M1). |
| D9 | **`attachments` polymorphic** (`owner_type` VARCHAR + `owner_id` UUID, KHÔNG FK cứng). M1/M2/M3/M5 cùng dùng. `owner_type` CHECK whitelist mở rộng dần. | demo-scope dòng 192-193/273 (polymorphic dùng chung). FK cứng polymorphic bất khả thi trong PG → toàn vẹn owner enforce app-layer; index `(owner_type, owner_id)` cho truy vấn. |
| D10 | **Soft-delete `users` = cột `status='disabled'`** (KHÔNG hard-delete; KHÔNG `deleted_at`). `departments` cũng dùng `status` active/inactive. `customers` có `deleted_at` (soft-delete danh mục). | Hồ sơ tham chiếu khắp M1/M2/M3/M4 (FK RESTRICT) → không được xóa user; "vô hiệu hóa" = `disabled`. Đồng bộ cách M2 dùng `status` cho `chemicals` (M2 D8). |
| D11 | **`access_stats` (R15 lượt truy cập) tách khỏi `audit_logs`.** access_stats = high-volume, ít giá trị pháp lý, có thể prune; audit_logs = pháp lý §8.4, giữ lâu. | R15 cần đếm lượt truy cập/tải (M6.3) — ghi nhiều, không cần immutable. Tách giúp `audit_logs` gọn + cho phép retention policy khác nhau. |

> **Audit fields (rule global):** bảng có vòng đời cập nhật (`users`, `departments`, `customers`) có `created_at`/`updated_at` + `created_by`/`updated_by UUID REFERENCES users(id)` (nullable cho bản ghi seed gốc / self-reference admin đầu tiên). Bảng append-only (`audit_logs`, `access_stats`, `notifications`, `refresh_tokens`) dùng cột người-liên-quan riêng (`user_id`) thay cặp created/updated. `permissions`/`roles_permissions` là danh mục cấu hình hệ thống → không cần audit user fields.

---

## 1. ERD chi tiết M7 (ASCII)

```
        ┌──────────────────────────────────────────────────────────┐
        │  departments  (CÂY PHÒNG BAN — parent_id self)           │
        │  id            UUID PK                                    │
        │  name          VARCHAR(255) NOT NULL                      │
        │  code          VARCHAR(32) UNIQUE NOT NULL                │
        │  parent_id     UUID FK→departments(id) NULL  (self, cây) │
        │  lead_user_id  UUID FK→users(id) NULL  ◄── OQ#11 M1      │
        │  status        VARCHAR(10) CHECK(active|inactive)         │
        │  created_by/updated_by/created_at/updated_at              │
        └───┬──────────────────────────────────────────▲──────────┘
            │ 1                       lead_user_id (FK,  │ ADD sau)
            │ N  department_id (FK)                      │
        ┌───▼──────────────────────────────────────────┴──────────┐
        │  users  (NGƯỜI DÙNG — dùng chung mọi module)             │
        │  id            UUID PK                                    │
        │  email         VARCHAR(255) UNIQUE NOT NULL (CITEXT-like) │
        │  password_hash VARCHAR(255) NOT NULL  (bcrypt $2b$, ≥10) │
        │  full_name     VARCHAR(255) NOT NULL                      │
        │  department_id UUID FK→departments(id) NULL (RESTRICT)    │
        │  role          VARCHAR(16) CHECK                          │
        │                  (admin|leader|accountant|staff)         │
        │  status        VARCHAR(10) CHECK(active|disabled)         │
        │  last_login_at TIMESTAMPTZ NULL                           │
        │  password_changed_at TIMESTAMPTZ NULL (ép đổi MK lần đầu)│
        │  created_by/updated_by/created_at/updated_at              │
        └───┬───────────────┬───────────────┬─────────────────────┘
            │ 1             │ 1             │ 1
            │ N             │ N             │ N
   ┌────────▼──────┐ ┌──────▼────────┐ ┌──▼──────────────────────┐
   │refresh_tokens │ │notifications  │ │ audit_logs (APPEND-ONLY)│
   │ id UUID PK    │ │ id UUID PK    │ │ id UUID PK              │
   │ user_id FK    │ │ user_id FK    │ │ user_id FK NULL         │
   │ token_hash    │ │ type          │ │ action VARCHAR          │
   │ expires_at    │ │ title/body    │ │ resource VARCHAR        │
   │ revoked_at    │ │ ref_type/ref_id│ │ resource_id UUID NULL  │
   │ rotated_from  │ │ read_at NULL  │ │ correlation_id          │
   │ user_agent/ip │ │ created_at    │ │ ip INET / at            │
   └───────────────┘ └───────────────┘ │ detail JSONB (no secret)│
                                        └─────────────────────────┘
            │ N (user_id FK)
   ┌────────▼──────────────────┐
   │ access_stats (R15 lượt TC)│
   │ id UUID PK, user_id FK NULL│
   │ path, method, status_code │
   │ ip INET, at TIMESTAMPTZ   │
   └───────────────────────────┘

        ┌──────────────────────────────────────────────────────────┐
        │  permissions  (DANH MỤC resource×action — seed)          │
        │  id UUID PK, resource VARCHAR, action VARCHAR             │
        │  description, UNIQUE(resource, action)                    │
        └───┬──────────────────────────────────────────────────────┘
            │ 1
            │ N  (logic: roles_permissions trỏ tới cùng resource+action)
        ┌───▼──────────────────────────────────────────────────────┐
        │  roles_permissions  (MA TRẬN QUYỀN — seed từ RBAC matrix) │
        │  id UUID PK                                               │
        │  role     VARCHAR(16) CHECK(admin|leader|accountant|staff)│
        │  resource VARCHAR(64) NOT NULL                            │
        │  action   VARCHAR(32) NOT NULL                            │
        │  scope    VARCHAR(12) CHECK(all|department|own)           │
        │  UNIQUE(role, resource, action)                          │
        │  FK(resource, action) → permissions(resource, action)    │
        └──────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────────────────┐
        │  customers  (KHÁCH GỬI MẪU — M1 tham chiếu, nullable)     │
        │  id UUID PK, name, contact, type CHECK, note, deleted_at  │
        │  created_by/updated_by/created_at/updated_at              │
        └──────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────────────────┐
        │  attachments  (POLYMORPHIC — dùng chung M1/M2/M3/M5)      │
        │  id UUID PK                                               │
        │  owner_type VARCHAR(32) CHECK(whitelist)                  │
        │  owner_id   UUID NOT NULL  (KHÔNG FK cứng — polymorphic)  │
        │  file_key   VARCHAR(512) (MinIO key) NOT NULL            │
        │  file_name  VARCHAR(255), mime VARCHAR(127), size BIGINT  │
        │  uploaded_by UUID FK→users(id), uploaded_at, deleted_at  │
        │  INDEX(owner_type, owner_id)                              │
        └──────────────────────────────────────────────────────────┘
```

### Bảng nào được module nào dùng chung

| Bảng M7 | M1 Mẫu | M2 Hóa chất | M3 Tài liệu | M4 Nhân sự/NCKH | M5 Thiết bị | M6 Báo cáo |
|---------|:------:|:-----------:|:-----------:|:---------------:|:-----------:|:----------:|
| `users` | ✅ FK người dùng mọi nơi | ✅ created_by/by_user/checked_by | ✅ created_by/approved_by | ✅ hr_profiles.user_id, mentor_id, author | ✅ phụ trách TB | ✅ lọc theo người |
| `departments` | ✅ scope + `lead_user_id` (trưởng nhóm) | ✅ `chemicals.department_id` | ✅ `documents.department_id` | ✅ phòng ban nhân sự/đề tài | ✅ `equipments.department_id` | ✅ lọc theo phòng |
| `permissions`/`roles_permissions` | ✅ RBAC assign/approve | ✅ RBAC nhập/xuất | ✅ RBAC duyệt tài liệu | ✅ RBAC HR/tài chính | ✅ RBAC hiệu chuẩn | ✅ RBAC báo cáo |
| `customers` | ✅ `test_requests.customer_id` | — | — | — | — | — |
| `attachments` | ✅ ảnh mẫu/raw data/PDF | ✅ CoA/MSDS | ✅ file tài liệu | ✅ bằng cấp/chứng chỉ | ✅ giấy hiệu chuẩn | — |
| `audit_logs` | ✅ mọi thao tác | ✅ mọi thao tác | ✅ mọi thao tác (§8.4) | ✅ thay đổi HR | ✅ hiệu chuẩn | — |
| `notifications` | ✅ CRON-1/2 + phân công | ✅ CRON-6 + tồn thấp | — | ✅ CRON-3/4 (lương/HĐ) | ✅ CRON-5 (hiệu chuẩn) | — |
| `access_stats` | — | — | (R15 lượt xem/tải tài liệu — M3 có `document_access_log` riêng chi tiết hơn) | — | — | ✅ M6.3 thống kê truy cập |
| `refresh_tokens` | (auth chung — mọi module qua login) | | | | | |

> **Ghi chú M3 `document_access_log`:** M3 có bảng riêng `document_access_log(document_id, user_id, action[view|download|edit], at)` cho thống kê chi tiết theo tài liệu (R15, demo-scope dòng 226-228). `access_stats` của M7 là thống kê truy cập **toàn hệ thống cấp đường dẫn** (R15 lượt truy cập chung, M6.3) — KHÔNG thay thế nhau. M7 cung cấp `access_stats`; M3 tự tạo `document_access_log` trong migration M3.

---

## 2. DDL đầy đủ — xử lý vòng FK `users` ↔ `departments`

> **Prereq:** M7 là migration ĐẦU TIÊN → bật extension dùng chung ở đây. **Thứ tự CREATE bắt buộc (phá vòng FK):**
> 1. `departments` (cột `lead_user_id` để NULL, **chưa** FK) → 2. `users` (FK `department_id → departments`) → 3. `ALTER TABLE departments ADD CONSTRAINT fk_dept_lead FOREIGN KEY (lead_user_id) → users` → 4. `permissions` → 5. `roles_permissions` → 6. `customers` → 7. `attachments` → 8. `refresh_tokens` → 9. `notifications` → 10. `audit_logs` → 11. `access_stats` → 12. trigger append-only → 13. indexes → 14. seed.

```sql
-- ============================================================
-- SCHEMA: m7-platform (Auth, Org, RBAC, Audit, Notification, Attachment)
-- Feature: Quản trị Hệ thống & Nền tảng (LIMS 17025) — MIGRATION ĐẦU TIÊN
-- Designer: schema-designer agent | Date: 2026-06-20
-- Prereq: KHÔNG (đây là migration nền tảng — bật extension dùng chung tại đây).
-- Thứ tự tổng thể: M7 (file này) → M1 (samples) → M2 (chemicals) → M3/M4/M5/M6.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid() — dùng chung toàn hệ thống
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- tìm kiếm ILIKE tên user/customer (M7) + tên hóa chất (M2)
CREATE EXTENSION IF NOT EXISTS citext;     -- email case-insensitive UNIQUE (xem ck_users_email)

-- ------------------------------------------------------------
-- [ NEW TABLE 1 ] departments — cây phòng ban (B01, demo-scope mục C)
--   lead_user_id để NULL & CHƯA gắn FK (phá vòng users↔departments — D3).
-- ------------------------------------------------------------
CREATE TABLE departments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    code            VARCHAR(32)  NOT NULL,                     -- mã phòng (vd 'LAB-HOA')
    parent_id       UUID         NULL,                         -- cây phòng ban linh hoạt (B01)
    lead_user_id    UUID         NULL,                         -- trưởng nhóm (OQ#11 M1, BR-SAMPLE-022) — FK ADD sau
    status          VARCHAR(10)  NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive')),
    created_by      UUID         NULL,                         -- NULL cho phòng ban seed gốc
    updated_by      UUID         NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_dept_code   UNIQUE (code),
    CONSTRAINT fk_dept_parent FOREIGN KEY (parent_id) REFERENCES departments(id) ON DELETE RESTRICT,
    -- không cho phòng làm cha của chính nó (cây 1 cấp tự tham chiếu; vòng sâu hơn enforce app-layer)
    CONSTRAINT ck_dept_not_self_parent CHECK (parent_id IS NULL OR parent_id <> id)
);
COMMENT ON TABLE  departments IS 'Cây phòng ban (B01). parent_id = cây linh hoạt; lead_user_id = trưởng nhóm cho RBAC assign/approve/finalize của M1 (OQ#11).';
COMMENT ON COLUMN departments.lead_user_id IS 'Trưởng nhóm phòng ban (BR-SAMPLE-022). FK gắn sau khi tạo users (D3).';

-- ------------------------------------------------------------
-- [ NEW TABLE 2 ] users — người dùng (M7.3; dùng chung mọi module)
--   FK department_id → departments (đã tồn tại ở bước 1).
-- ------------------------------------------------------------
CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email               CITEXT       NOT NULL,                 -- case-insensitive UNIQUE (a@x = A@x)
    password_hash       VARCHAR(255) NOT NULL,                 -- bcrypt $2b$... cost>=10 (D6, NFR-SEC-002)
    full_name           VARCHAR(255) NOT NULL,
    department_id       UUID         NULL,                     -- NULL = chưa gán phòng (vd admin hệ thống)
    role                VARCHAR(16)  NOT NULL
        CHECK (role IN ('admin', 'leader', 'accountant', 'staff')),  -- 4 vai trò (demo-scope B)
    status              VARCHAR(10)  NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'disabled')),               -- soft-delete = disabled (D10)
    last_login_at       TIMESTAMPTZ  NULL,
    password_changed_at TIMESTAMPTZ  NULL,                     -- NULL ⇒ ép đổi MK lần đầu (admin seed)
    created_by          UUID         NULL,                     -- NULL cho admin gốc (self/seed)
    updated_by          UUID         NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_users_email     UNIQUE (email),
    CONSTRAINT fk_users_dept      FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
    CONSTRAINT fk_users_created   FOREIGN KEY (created_by)    REFERENCES users(id)       ON DELETE RESTRICT,
    CONSTRAINT fk_users_updated   FOREIGN KEY (updated_by)    REFERENCES users(id)       ON DELETE RESTRICT,
    -- email tối thiểu phải có '@' (validate đầy đủ ở app — class-validator/pydantic)
    CONSTRAINT ck_users_email     CHECK (position('@' IN email) > 1)
);
COMMENT ON TABLE  users IS 'Người dùng hệ thống (M7.3). role 4 giá trị; status=disabled là soft-delete (D10).';
COMMENT ON COLUMN users.password_changed_at IS 'NULL = chưa đổi mật khẩu lần đầu → app ép đổi (admin seed mặc định).';

-- ------------------------------------------------------------
-- [ ALTER 1 ] Gắn FK lead_user_id sau khi users đã tồn tại (PHÁ VÒNG FK — D3)
--   ON DELETE SET NULL: xóa/disable user trưởng nhóm không làm hỏng phòng ban
--   (thực tế users không hard-delete; SET NULL là lưới an toàn).
-- ------------------------------------------------------------
ALTER TABLE departments
    ADD CONSTRAINT fk_dept_lead FOREIGN KEY (lead_user_id)
    REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE departments
    ADD CONSTRAINT fk_dept_created FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT;
ALTER TABLE departments
    ADD CONSTRAINT fk_dept_updated FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT;

-- ------------------------------------------------------------
-- [ NEW TABLE 3 ] permissions — danh mục resource × action chuẩn hóa (M7.2, D4)
--   Seed cố định; định nghĩa "quyền nào tồn tại trong hệ thống".
-- ------------------------------------------------------------
CREATE TABLE permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource    VARCHAR(64)  NOT NULL,                         -- vd 'sample','chemical','document','report','user'
    action      VARCHAR(32)  NOT NULL,                         -- vd 'create','read','update','delete','approve'
    description VARCHAR(255) NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_perm_resource_action UNIQUE (resource, action)
);
COMMENT ON TABLE permissions IS 'Danh mục quyền (resource,action) chuẩn hóa (D4). Seed cố định; roles_permissions FK tới đây.';

-- ------------------------------------------------------------
-- [ NEW TABLE 4 ] roles_permissions — ma trận quyền theo vai trò + phạm vi (M7.2, R13)
--   demo-scope mục C: roles_permissions(role, resource, action) + scope (mục B "phạm vi phòng ban").
-- ------------------------------------------------------------
CREATE TABLE roles_permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role        VARCHAR(16)  NOT NULL
        CHECK (role IN ('admin', 'leader', 'accountant', 'staff')),
    resource    VARCHAR(64)  NOT NULL,
    action      VARCHAR(32)  NOT NULL,
    scope       VARCHAR(12)  NOT NULL DEFAULT 'all'
        CHECK (scope IN ('all', 'department', 'own')),          -- phạm vi dữ liệu (R13)
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_rp_role_res_act UNIQUE (role, resource, action),
    -- chỉ gán được quyền đã khai báo trong permissions (toàn vẹn)
    CONSTRAINT fk_rp_permission FOREIGN KEY (resource, action)
        REFERENCES permissions(resource, action) ON DELETE CASCADE
);
COMMENT ON TABLE  roles_permissions IS 'Ma trận quyền (role × resource × action × scope) — R13. Seed từ RBAC matrix demo-scope mục B. Tra quyền: WHERE role=? AND resource=? AND action=?.';
COMMENT ON COLUMN roles_permissions.scope IS 'all = toàn hệ thống; department = trong phòng ban user; own = chỉ dữ liệu cá nhân. App áp scope vào WHERE của truy vấn.';

-- ------------------------------------------------------------
-- [ NEW TABLE 5 ] customers — khách gửi mẫu (M1 tham chiếu, nullable; demo-scope dòng 174)
-- ------------------------------------------------------------
CREATE TABLE customers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    contact     VARCHAR(255) NULL,                             -- SĐT/email/người liên hệ (gộp, app format)
    type        VARCHAR(16)  NOT NULL DEFAULT 'external'
        CHECK (type IN ('internal', 'external', 'individual', 'organization')), -- loại khách
    note        TEXT         NULL,
    deleted_at  TIMESTAMPTZ  NULL,                             -- soft-delete danh mục (D10)
    created_by  UUID         NULL,
    updated_by  UUID         NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_cust_created FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT fk_cust_updated FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);
COMMENT ON TABLE customers IS 'Khách gửi mẫu (M1 test_requests.customer_id, nullable). Khách vãng lai chỉ ghi sender_name ở phiếu, không cần record này.';

-- ------------------------------------------------------------
-- [ NEW TABLE 6 ] attachments — file polymorphic dùng chung M1/M2/M3/M5 (D9, R2/R11)
--   owner_id KHÔNG FK cứng (polymorphic) — toàn vẹn owner enforce app-layer.
-- ------------------------------------------------------------
CREATE TABLE attachments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_type  VARCHAR(32)  NOT NULL
        CHECK (owner_type IN (
            'test_request', 'sample', 'sample_result',         -- M1
            'chemical', 'chem_lot',                            -- M2 (MSDS / CoA)
            'document', 'document_version',                    -- M3
            'equipment', 'calibration',                        -- M5
            'hr_profile', 'publication'                        -- M4
        )),
    owner_id    UUID         NOT NULL,                         -- id của bản ghi sở hữu (no FK — polymorphic)
    file_key    VARCHAR(512) NOT NULL,                         -- MinIO object key (CHỐT C01)
    file_name   VARCHAR(255) NOT NULL,                         -- tên hiển thị gốc
    mime        VARCHAR(127) NULL,
    size        BIGINT       NULL CHECK (size IS NULL OR size >= 0),  -- byte
    uploaded_by UUID         NOT NULL,
    uploaded_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ  NULL,                             -- soft-delete (gỡ liên kết, file MinIO dọn riêng)

    CONSTRAINT fk_att_uploaded_by FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE RESTRICT
);
COMMENT ON TABLE  attachments IS 'File đính kèm polymorphic dùng chung (R2). owner_type whitelist mở rộng dần khi thêm module. owner_id KHÔNG FK cứng — app phải kiểm tra owner tồn tại trước khi gắn.';
COMMENT ON COLUMN attachments.owner_id IS 'ID bản ghi sở hữu theo owner_type. KHÔNG FK (polymorphic) — toàn vẹn enforce app-layer.';

-- ------------------------------------------------------------
-- [ NEW TABLE 7 ] refresh_tokens — JWT refresh rotation (M7.1, D7, NFR-SEC-003)
--   Lưu HASH token (không lưu token thô). Access token stateless không lưu DB.
-- ------------------------------------------------------------
CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         NOT NULL,
    token_hash  VARCHAR(255) NOT NULL,                         -- sha256(refresh_token) hex — KHÔNG token thô (D7)
    expires_at  TIMESTAMPTZ  NOT NULL,                         -- TTL ≤ 30 ngày (NFR-SEC-003)
    revoked_at  TIMESTAMPTZ  NULL,                             -- set khi rotate/logout/revoke
    rotated_from UUID        NULL,                             -- token trước trong chuỗi rotation (audit reuse)
    user_agent  VARCHAR(255) NULL,
    ip          INET         NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_rt_token_hash  UNIQUE (token_hash),
    CONSTRAINT fk_rt_user        FOREIGN KEY (user_id)      REFERENCES users(id)          ON DELETE CASCADE,
    CONSTRAINT fk_rt_rotated_from FOREIGN KEY (rotated_from) REFERENCES refresh_tokens(id) ON DELETE SET NULL,
    CONSTRAINT ck_rt_expiry      CHECK (expires_at > created_at)
);
COMMENT ON TABLE  refresh_tokens IS 'Refresh token JWT (D7, NFR-SEC-003). token_hash = sha256 token thô. Rotation: INSERT mới + set revoked_at bản cũ trong 1 txn. ON DELETE CASCADE theo user.';
COMMENT ON COLUMN refresh_tokens.rotated_from IS 'Phát hiện token reuse: nếu refresh token đã revoked được dùng lại → revoke toàn chuỗi user (bảo mật).';

-- ------------------------------------------------------------
-- [ NEW TABLE 8 ] notifications — thông báo in-app dùng chung (M7.5, C02)
--   M1 CRON-1/2, M2 CRON-6, M4 CRON-3/4, M5 CRON-5 đều INSERT vào đây.
-- ------------------------------------------------------------
CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         NOT NULL,                         -- người nhận
    type        VARCHAR(48)  NOT NULL,                         -- vd 'SAMPLE_DEADLINE','CHEM_EXPIRY','SALARY_RAISE'
    title       VARCHAR(255) NOT NULL,
    body        TEXT         NULL,
    ref_type    VARCHAR(32)  NULL,                             -- loại bản ghi liên quan (vd 'sample','chem_lot')
    ref_id      UUID         NULL,                             -- id bản ghi liên quan (deep-link FE)
    read_at     TIMESTAMPTZ  NULL,                             -- NULL = chưa đọc
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
COMMENT ON TABLE notifications IS 'Thông báo in-app dùng chung (M7.5, C02 chỉ in-app). read_at NULL = chưa đọc. ON DELETE CASCADE theo user (thông báo cá nhân, không phải hồ sơ pháp lý).';

-- ------------------------------------------------------------
-- [ NEW TABLE 9 ] audit_logs — nhật ký kiểm toán APPEND-ONLY (M7.4, R15, §8.4)
--   IMMUTABLE: không UPDATE/DELETE (D8). detail JSONB đã LỌC sensitive (no password/token).
-- ------------------------------------------------------------
CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID         NULL,                         -- NULL cho thao tác hệ thống/cron/đăng nhập thất bại
    action          VARCHAR(64)  NOT NULL,                     -- vd 'SAMPLE_FINALIZE','CHEMICAL_TXN_OUT','LOGIN'
    resource        VARCHAR(64)  NOT NULL,                     -- 'sample','chemical_lot','user'...
    resource_id     UUID         NULL,                         -- id đối tượng tác động
    correlation_id  VARCHAR(64)  NULL,                         -- trace FE→BE→DB (logging.md)
    ip              INET         NULL,
    detail          JSONB        NULL,                         -- ngữ cảnh đã LỌC sensitive (D6/D8)
    at              TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
COMMENT ON TABLE  audit_logs IS 'Nhật ký kiểm toán APPEND-ONLY (17025 §8.4, R15). KHÔNG UPDATE/DELETE (trigger chặn + REVOKE). user_id ON DELETE SET NULL để giữ log khi user bị xóa cứng (hiếm).';
COMMENT ON COLUMN audit_logs.detail IS 'JSONB ngữ cảnh ĐÃ LỌC: KHÔNG chứa password_hash, token, refresh_token, secret (rule logging.md / D6).';

-- ------------------------------------------------------------
-- [ NEW TABLE 10 ] access_stats — lượt truy cập (R15, M6.3) — high-volume, có thể prune
-- ------------------------------------------------------------
CREATE TABLE access_stats (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         NULL,                             -- NULL = ẩn danh / chưa đăng nhập
    path        VARCHAR(512) NOT NULL,                         -- đường dẫn truy cập
    method      VARCHAR(8)   NULL,                             -- GET/POST...
    status_code SMALLINT     NULL,
    ip          INET         NULL,
    at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_access_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
COMMENT ON TABLE access_stats IS 'Lượt truy cập toàn hệ thống cấp đường dẫn (R15, M6.3). High-volume; cho phép retention/prune khác audit_logs (D11). KHÔNG thay document_access_log của M3.';

-- ------------------------------------------------------------
-- [ TRIGGER ] audit_logs APPEND-ONLY — chặn UPDATE/DELETE ở DB-level (D8, §8.4)
--   Defense-in-depth: kết hợp với REVOKE UPDATE/DELETE khỏi app DB role (xem §7).
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_audit_logs_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only (ISO/IEC 17025 §8.4): % not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_logs_no_update
    BEFORE UPDATE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION trg_audit_logs_immutable();

CREATE TRIGGER audit_logs_no_delete
    BEFORE DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION trg_audit_logs_immutable();
```

---

## 3. CHECK constraints & toàn vẹn quan trọng — tổng hợp

| Quy tắc | Constraint | DB enforce? | Ghi chú |
|---------|-----------|-------------|---------|
| email UNIQUE case-insensitive | `email CITEXT` + `uq_users_email` | ✅ | a@x = A@x là trùng. Cần extension `citext`. |
| email có '@' | `ck_users_email` | ✅ | Validate đầy đủ (RFC) ở app (pydantic EmailStr). |
| `role` ∈ 4 vai trò | CHECK `users.role` + `roles_permissions.role` | ✅ | demo-scope B. Cùng tập giá trị 2 bảng (D5). |
| `users.status` ∈ {active,disabled} | CHECK | ✅ | soft-delete = disabled (D10). |
| `scope` ∈ {all,department,own} | CHECK `roles_permissions.scope` | ✅ | R13 phạm vi dữ liệu. |
| quyền gán phải tồn tại trong danh mục | `fk_rp_permission (resource,action)→permissions` | ✅ | Chống gán quyền "ma". |
| 1 quyền/vai trò duy nhất | `uq_rp_role_res_act` | ✅ | Tránh dòng trùng (role,resource,action). |
| phòng ban không tự làm cha | `ck_dept_not_self_parent` | ✅ | Vòng cây sâu (A→B→A) enforce app-layer (CHECK đơn cột không làm được). |
| `code` phòng ban UNIQUE | `uq_dept_code` | ✅ | |
| refresh token hash UNIQUE | `uq_rt_token_hash` | ✅ | Một token chỉ tồn tại 1 lần. |
| refresh token TTL hợp lệ | `ck_rt_expiry (expires_at>created_at)` | ✅ | App set ≤ 30 ngày (NFR-SEC-003). |
| attachment size ≥ 0 | CHECK | ✅ | |
| owner_type ∈ whitelist | CHECK `attachments.owner_type` | ✅ | Mở rộng whitelist khi thêm module (ALTER CHECK). |
| audit_logs append-only | trigger `audit_logs_no_update/delete` | ✅ | + REVOKE app role (§7). 17025 §8.4. |
| password bcrypt cost ≥ 10 | — | ⚠️ **app-layer** | DB chỉ lưu hash; cost enforce ở service (passlib/bcrypt). NFR-SEC-002. |
| KHÔNG log password/token vào detail | — | ⚠️ **app-layer** | rule logging.md; service phải lọc trước khi INSERT audit_logs (D6). |
| scope `department`/`own` áp vào query | — | ⚠️ **app-layer** | RBAC guard đọc roles_permissions → thêm WHERE department_id=? / user_id=? (R13). |
| owner_id polymorphic tồn tại | — | ⚠️ **app-layer** | Không FK cứng (D9); service kiểm tra owner trước khi gắn attachment. |
| token reuse detection | — | ⚠️ **app-layer** | Dùng `rotated_from`: refresh token đã revoked bị dùng lại → revoke toàn chuỗi (D7). |
| vòng cây phòng ban (A→B→A) | — | ⚠️ **app-layer** | Đệ quy kiểm tra khi đổi parent_id. |

> **Tinh thần đồng bộ M1/M2:** CHECK DB giữ ràng buộc **giá trị** (enum hợp lệ, UNIQUE, NOT NULL, cặp nhất quán). Logic nghiệp vụ/bảo mật phức (RBAC scope, bcrypt cost, lọc sensitive, token reuse, vòng cây) enforce **app-layer** với mã lỗi rõ ràng — giống M2 (BR-CHEM-028) và M1 (state machine, tách nhập-duyệt).

---

## 4. Index strategy

```sql
-- ===== users =====
-- uq_users_email đã tạo unique index (CITEXT) — tra cứu đăng nhập (M7.1, NFR login P95<200ms)
CREATE INDEX idx_users_department   ON users(department_id) WHERE department_id IS NOT NULL;  -- FK + RBAC scope (R13)
CREATE INDEX idx_users_role         ON users(role);                              -- lọc theo vai trò (admin quản lý user)
CREATE INDEX idx_users_status       ON users(status);                            -- lọc active/disabled
CREATE INDEX idx_users_fullname_trgm ON users USING gin (full_name gin_trgm_ops); -- tìm tên user (admin) — cần pg_trgm

-- ===== departments =====
-- uq_dept_code đã tạo index — tra mã phòng
CREATE INDEX idx_dept_parent        ON departments(parent_id) WHERE parent_id IS NOT NULL;  -- dựng cây
CREATE INDEX idx_dept_lead          ON departments(lead_user_id) WHERE lead_user_id IS NOT NULL; -- tra trưởng nhóm (BR-SAMPLE-022)

-- ===== roles_permissions =====
-- uq_rp_role_res_act (role,resource,action) đã là composite index — đủ cho TRA QUYỀN nóng nhất:
--   WHERE role=? AND resource=? AND action=?  (mọi request đều check → cache Redis thêm)
CREATE INDEX idx_rp_role            ON roles_permissions(role);                  -- nạp toàn bộ quyền 1 vai trò (cache warm-up)

-- ===== permissions =====
-- uq_perm_resource_action đã tạo composite index — đủ cho FK lookup từ roles_permissions.

-- ===== customers =====
CREATE INDEX idx_cust_name_trgm     ON customers USING gin (name gin_trgm_ops) ; -- tìm khách theo tên (M1 nhận mẫu)
-- (không index type/contact — chọn lọc thấp)

-- ===== attachments =====
-- COMPOSITE quan trọng nhất: lấy mọi file của 1 bản ghi (M1/M2/M3 đều dùng) — D9 yêu cầu
CREATE INDEX idx_att_owner          ON attachments(owner_type, owner_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_att_uploaded_by    ON attachments(uploaded_by);                 -- FK + "file tôi tải lên"

-- ===== refresh_tokens =====
-- uq_rt_token_hash đã tạo index — verify refresh token theo hash (auth hot path)
CREATE INDEX idx_rt_user            ON refresh_tokens(user_id);                  -- FK + liệt kê/revoke phiên của user
-- dọn token hết hạn (cron cleanup) — chỉ token còn hiệu lực
CREATE INDEX idx_rt_expires_active  ON refresh_tokens(expires_at) WHERE revoked_at IS NULL;

-- ===== notifications =====
-- COMPOSITE quan trọng nhất: "thông báo chưa đọc của tôi, mới nhất trước" (polling/SSE FE — C02)
CREATE INDEX idx_notif_user_unread  ON notifications(user_id, created_at DESC) WHERE read_at IS NULL;
-- liệt kê toàn bộ thông báo của user (đã đọc + chưa đọc)
CREATE INDEX idx_notif_user_created ON notifications(user_id, created_at DESC);
-- chống trùng cron theo (ref + type) — hỗ trợ M1/M2/M4/M5 kiểm tra "đã gửi chưa"
CREATE INDEX idx_notif_ref          ON notifications(ref_type, ref_id, type) WHERE ref_id IS NOT NULL;

-- ===== audit_logs =====
-- correlation_id: trace 1 request xuyên suốt (logging.md, debug < 10 phút) — partial bỏ NULL
CREATE INDEX idx_audit_correlation  ON audit_logs(correlation_id) WHERE correlation_id IS NOT NULL;
-- lọc theo thời gian (xem nhật ký mới nhất — M7.4)
CREATE INDEX idx_audit_at           ON audit_logs(at DESC);
-- COMPOSITE: "ai làm gì với đối tượng X" (truy vết theo resource) — §8.4
CREATE INDEX idx_audit_resource     ON audit_logs(resource, resource_id, at DESC) WHERE resource_id IS NOT NULL;
-- lọc theo người thực hiện + thời gian (M7.4 "user X đã làm gì")
CREATE INDEX idx_audit_user_at      ON audit_logs(user_id, at DESC) WHERE user_id IS NOT NULL;

-- ===== access_stats =====
CREATE INDEX idx_access_user_at     ON access_stats(user_id, at DESC) WHERE user_id IS NOT NULL;  -- thống kê theo user
CREATE INDEX idx_access_at          ON access_stats(at DESC);                    -- thống kê theo kỳ (M6.3)
```

**Lý do nhóm index trọng yếu (theo yêu cầu):**
- **`email`** — `uq_users_email` (CITEXT unique): login là hot path P95 < 200ms (NFR login). Một index lo cả UNIQUE + lookup.
- **`department_id`** — `idx_users_department`: RBAC scope `department` (R13) lọc user theo phòng; partial bỏ user chưa gán phòng.
- **`owner_type + owner_id`** — `idx_att_owner` (composite, partial `deleted_at IS NULL`): query phổ biến nhất của attachments — "lấy mọi file của bản ghi này" mà M1/M2/M3/M5 gọi liên tục (D9). Đây là index quan trọng nhất bảng attachments.
- **`audit_logs.correlation_id + at`** — `idx_audit_correlation` (trace 1 request) + `idx_audit_at` (nhật ký mới nhất) + `idx_audit_resource` (truy vết đối tượng): đáp ứng "tìm root cause < 10 phút" (logging.md) và truy xuất hồ sơ §8.4.
- **`notifications.user_id + read_at`** — `idx_notif_user_unread` (partial `read_at IS NULL`, composite với `created_at DESC`): FE polling/SSE đếm + hiển thị thông báo chưa đọc — query nóng nhất của notifications, partial giữ index nhỏ.

> **Không over-index:** KHÔNG index `password_hash`, `body`, `note`, `mime`, `user_agent`, `status_code`, `customers.contact`, `audit_logs.detail` (không dùng WHERE chọn lọc cao). Quy mô ~40 user (C03): `audit_logs`/`access_stats` tăng nhanh nhất — đặt **retention/prune** thay vì partition (xem §7). Cache `roles_permissions` ở Redis (warm-up bằng `idx_rp_role`) để tránh query mỗi request.

---

## 5. Seed data

> **Thứ tự seed:** permissions → roles_permissions → departments (mẫu) → admin user → ALTER lead_user_id (gán trưởng nhóm nếu cần). Mật khẩu admin **PHẢI đổi lần đầu** (`password_changed_at` = NULL → app ép đổi).

### 5.1 `permissions` — danh mục resource × action (suy từ RBAC matrix demo-scope mục B)

```sql
INSERT INTO permissions (resource, action, description) VALUES
    -- Mẫu (M1)
    ('sample',       'create',  'Tạo phiếu nhận / nhận mẫu'),
    ('sample',       'read',    'Xem mẫu / kết quả công khai nội bộ'),
    ('sample',       'assign',  'Phân công / chuyển giao mẫu'),
    ('sample',       'result',  'Nhập kết quả phần được giao'),
    ('sample',       'approve', 'Duyệt kết quả / chốt hoàn thành mẫu'),
    -- Hóa chất (M2)
    ('chemical',     'create',  'CRUD hóa chất / lô'),
    ('chemical',     'read',    'Xem tồn / lịch sử hóa chất'),
    ('chemical',     'transact','Nhập / xuất / điều chỉnh hóa chất'),
    ('chemical',     'cost',    'Xem giá trị tiền hóa chất'),
    -- Tài liệu (M3)
    ('document',     'create',  'Tạo / sửa tài liệu'),
    ('document',     'read',    'Xem tài liệu'),
    ('document',     'approve', 'Duyệt / ban hành tài liệu'),
    -- Nhân sự & NCKH (M4)
    ('hr',           'read',    'Xem hồ sơ nhân sự / hợp đồng'),
    ('hr',           'manage',  'Quản lý hồ sơ / lương / nâng lương'),
    ('research',     'manage',  'Quản lý thành tích NCKH'),
    -- Thiết bị (M5)
    ('equipment',    'manage',  'Quản lý thiết bị / hiệu chuẩn'),
    -- Báo cáo (M6)
    ('report',       'business','Báo cáo nghiệp vụ (mẫu / hóa chất)'),
    ('report',       'finance', 'Báo cáo tài chính'),
    -- Quản trị (M7)
    ('user',         'manage',  'Quản lý user / role / phòng ban'),
    ('audit',        'read',    'Xem nhật ký kiểm toán');
```

### 5.2 `roles_permissions` — ma trận quyền (map từ bảng RBAC demo-scope mục B)

Quy ước scope: `all` = toàn hệ thống (Admin/Lãnh đạo) · `department` = trong phòng ban · `own` = chỉ dữ liệu cá nhân. ✅(phòng)→department, ✅(của mình)→own, ✅/👁 toàn hệ thống→all.

```sql
INSERT INTO roles_permissions (role, resource, action, scope) VALUES
    -- ===== ADMIN: toàn quyền, scope all =====
    ('admin','sample','create','all'), ('admin','sample','read','all'),
    ('admin','sample','assign','all'), ('admin','sample','result','all'),
    ('admin','sample','approve','all'),
    ('admin','chemical','create','all'), ('admin','chemical','read','all'),
    ('admin','chemical','transact','all'), ('admin','chemical','cost','all'),
    ('admin','document','create','all'), ('admin','document','read','all'),
    ('admin','document','approve','all'),
    ('admin','hr','read','all'), ('admin','hr','manage','all'),
    ('admin','research','manage','all'),
    ('admin','equipment','manage','all'),
    ('admin','report','business','all'), ('admin','report','finance','all'),
    ('admin','user','manage','all'), ('admin','audit','read','all'),

    -- ===== LEADER (Ban lãnh đạo): xem toàn hệ thống + duyệt, scope all =====
    ('leader','sample','read','all'), ('leader','sample','assign','all'),
    ('leader','sample','approve','all'),
    ('leader','chemical','read','all'), ('leader','chemical','transact','all'),
    ('leader','chemical','cost','all'),
    ('leader','document','create','all'), ('leader','document','read','all'),
    ('leader','document','approve','all'),
    ('leader','hr','read','all'), ('leader','hr','manage','all'),
    ('leader','research','manage','all'),
    ('leader','equipment','manage','all'),
    ('leader','report','business','all'), ('leader','report','finance','all'),
    ('leader','audit','read','all'),

    -- ===== ACCOUNTANT (Kế toán): CHỈ tài chính, KHÔNG mẫu/kết quả (B03) =====
    ('accountant','chemical','read','all'), ('accountant','chemical','cost','all'),
    ('accountant','document','read','all'),
    ('accountant','hr','read','all'),       -- xem HĐ
    ('accountant','hr','manage','all'),     -- lương / nâng lương (tài chính)
    ('accountant','report','business','all'), -- chỉ phần hóa chất (app lọc resource)
    ('accountant','report','finance','all'),

    -- ===== STAFF (Nhân sự / KTV): scope department / own =====
    ('staff','sample','create','department'),   -- nhận mẫu (B02 quyền KTV)
    ('staff','sample','read','all'),            -- xem công khai nội bộ lab (R6)
    ('staff','sample','assign','department'),   -- phân công trong phòng
    ('staff','sample','result','own'),          -- nhập kết quả phần được giao
    ('staff','sample','approve','department'),  -- chỉ trưởng nhóm (app check departments.lead_user_id)
    ('staff','chemical','read','all'),
    ('staff','chemical','transact','department'),
    ('staff','document','create','department'),
    ('staff','document','read','all'),
    ('staff','hr','read','own'),                -- chỉ hồ sơ của mình
    ('staff','research','manage','own'),        -- thành tích của mình
    ('staff','equipment','manage','department'),
    ('staff','report','business','department');
```

> **Ghi chú enforce app-layer:** (1) "duyệt kết quả" của staff chỉ áp dụng cho **trưởng nhóm** (`departments.lead_user_id = user.id`) — RBAC guard kiểm tra thêm (BR-SAMPLE-022), dòng `staff/sample/approve/department` là điều kiện cần, không đủ. (2) Kế toán `report/business` chỉ thấy **phần hóa chất** (không mẫu) — app lọc theo resource con. (3) Quyền `chemical/cost` của staff = không có dòng ⇒ staff KHÔNG xem giá trị tiền (đúng matrix dòng 138).

### 5.3 `departments` — phòng ban mẫu (KH tự nhập thật sau — B01)

```sql
INSERT INTO departments (id, name, code, status) VALUES
    ('00000000-0000-0000-0000-0000000000d1', 'Ban Giám đốc',          'BGD',     'active'),
    ('00000000-0000-0000-0000-0000000000d2', 'Phòng Thí nghiệm Hóa',  'LAB-HOA', 'active'),
    ('00000000-0000-0000-0000-0000000000d3', 'Phòng Thí nghiệm Sinh', 'LAB-SINH','active'),
    ('00000000-0000-0000-0000-0000000000d4', 'Phòng Kế toán',         'KT',      'active');
-- parent_id để NULL (cây phẳng ban đầu); KH cấu hình cây thật sau.
```

### 5.4 Admin mặc định (PHẢI ĐỔI MẬT KHẨU LẦN ĐẦU)

```sql
-- password_hash dưới đây là bcrypt của 'ChangeMe@123' (cost=12) — VÍ DỤ.
-- BẮT BUỘC: tạo hash thật bằng passlib khi seed; KHÔNG commit mật khẩu thật vào repo.
-- password_changed_at = NULL ⇒ app ép đổi mật khẩu ngay lần đăng nhập đầu.
INSERT INTO users (id, email, password_hash, full_name, department_id, role, status, password_changed_at)
VALUES (
    '00000000-0000-0000-0000-0000000000a1',
    'admin@lims.local',
    '$2b$12$REPLACE_WITH_REAL_BCRYPT_HASH_GENERATED_AT_SEED_TIME......',
    'Quản trị hệ thống',
    '00000000-0000-0000-0000-0000000000d1',
    'admin',
    'active',
    NULL  -- ⚠️ ép đổi mật khẩu lần đầu
);

-- (Tùy chọn) gán trưởng nhóm cho phòng lab sau khi có user leader/staff thật:
-- UPDATE departments SET lead_user_id = '<user_id>' WHERE code = 'LAB-HOA';
```

> **CẢNH BÁO BẢO MẬT (bàn giao):** mật khẩu admin mặc định CHỈ để khởi tạo. Tài liệu vận hành phải ghi rõ: đổi mật khẩu admin ngay lần đăng nhập đầu (app ép qua `password_changed_at IS NULL`); KHÔNG để `admin@lims.local` với mật khẩu mặc định trên production (NFR-SEC A05 "không default credentials").

---

## 6. Traceability — Map bảng/cột → Module M7.x + R13/R15 + 17025 §8.4

| Bảng / Cột | Module M7.x | Yêu cầu R / 17025 |
|------------|-------------|-------------------|
| `users` (toàn bộ) | M7.3 (quản lý người dùng) | — |
| `users.password_hash` (bcrypt) | M7.1 (auth) | NFR-SEC-002 |
| `users.role` + `roles_permissions` | M7.2 (RBAC) | R13, demo-scope B |
| `roles_permissions.scope` | M7.2 (phạm vi phòng ban) | R13 |
| `permissions` | M7.2 (danh mục quyền) | R13 |
| `departments` (cây) | M7.3 | B01 |
| `departments.lead_user_id` | M7.3 (hỗ trợ M1) | OQ#11 M1, BR-SAMPLE-022 |
| `refresh_tokens` | M7.1 (JWT + refresh rotation) | NFR-SEC-003 |
| `audit_logs` (append-only + trigger) | M7.4 (audit toàn hệ thống) | R15, **17025 §8.4** |
| `audit_logs.correlation_id` | M7.4 | logging.md (trace request) |
| `notifications` | M7.5 (thông báo in-app) | R7/R12/R16 (cron M1/M2/M4/M5), C02 |
| `access_stats` | M7.4 / hỗ trợ M6.3 | R15 (lượt truy cập) |
| `customers` | M7 (danh mục dùng chung) | hỗ trợ M1 |
| `attachments` (polymorphic) | M7 (file dùng chung) | R2, R11, 17025 §7.5 (hồ sơ kỹ thuật) |

---

## 7. Ghi chú cho dev (BẮT BUỘC đọc)

### 7.1 Thứ tự migration tổng thể
```
1. M7 (file này)  → pgcrypto/pg_trgm/citext + departments → users → ALTER fk_dept_lead
                    → permissions → roles_permissions → customers → attachments
                    → refresh_tokens → notifications → audit_logs → access_stats
                    → trigger append-only → indexes → seed
2. M1 (samples...) → FK tới users/departments/customers/attachments/audit_logs/notifications
3. M2 (chemicals)  → FK ref_sample_id → samples(id) (SAU M1)
4. M3/M4/M5/M6     → mở rộng attachments.owner_type CHECK khi cần (ALTER ... DROP/ADD CHECK)
```
**Lý do M7 đầu tiên:** M1/M2 đều khai "bảng dùng chung M7 phải tồn tại trước" (M1 §9, M2 §8.5). Vòng FK `users`↔`departments` chỉ giải được trong migration M7 (D3).

### 7.2 Bảo mật auth (NFR-SEC-002/003)
- **bcrypt cost ≥ 10** (khuyến nghị 12) qua `passlib.hash.bcrypt`. KHÔNG tự cài thuật toán.
- **Access token TTL ≤ 60 phút** (NFR-SEC-003), stateless (KHÔNG lưu DB).
- **Refresh token TTL ≤ 30 ngày, ROTATION mỗi lần dùng (D7):** trong 1 transaction — verify `token_hash` còn hiệu lực (`revoked_at IS NULL AND expires_at > now()`) → set `revoked_at=now()` bản cũ → INSERT bản mới (`rotated_from`=id cũ). Token reuse: nếu nhận refresh token đã `revoked_at IS NOT NULL` → **revoke toàn bộ token của user** (nghi ngờ đánh cắp) + audit `TOKEN_REUSE_DETECTED`.
- **Lưu HASH** (`sha256` hex) chứ KHÔNG token thô — DB lộ vẫn an toàn.
- **Cron cleanup** refresh token hết hạn (dùng `idx_rt_expires_active`) — chạy hàng ngày.

### 7.3 Audit append-only (17025 §8.4, D8)
- KHÔNG tạo route PUT/PATCH/DELETE cho `audit_logs`. Trigger DB đã chặn UPDATE/DELETE (lưới an toàn).
- **Defense-in-depth khuyến nghị:** tạo DB role riêng cho app và `REVOKE UPDATE, DELETE ON audit_logs FROM <app_role>;` (migration hạ tầng). Trigger + REVOKE = 2 lớp.
- **Lọc sensitive trước khi INSERT detail** (D6, logging.md): service ghi audit phải loại bỏ `password`, `password_hash`, `token`, `refresh_token`, `secret`, `authorization` khỏi `detail` JSONB. Không dump nguyên request body.
- `correlation_id` lấy từ header `x-correlation-id` (middleware) — ghi vào mọi audit + notification liên quan để trace xuyên suốt.

### 7.4 RBAC enforce (R13, M7.2)
- Guard đọc `roles_permissions WHERE role=user.role AND resource=? AND action=?` (cache Redis, warm bằng `idx_rp_role`). Không có dòng → 403 `FORBIDDEN`.
- Áp **scope** vào truy vấn: `all` → không filter; `department` → `WHERE department_id = user.department_id`; `own` → `WHERE <owner_col> = user.id`. Trưởng nhóm (`sample/approve`) kiểm tra thêm `departments.lead_user_id = user.id` (BR-SAMPLE-022).
- KHÔNG hardcode quyền trong code — luôn tra bảng (D4) để admin sửa ma trận không cần deploy.

### 7.5 Attachments polymorphic (D9)
- Trước khi INSERT attachment: service kiểm tra `owner_id` tồn tại theo `owner_type` (không có FK cứng). Sai → 422 `OWNER_NOT_FOUND`.
- File thật ở MinIO (`file_key`); `deleted_at` chỉ gỡ liên kết logic — dọn object MinIO bằng job riêng (tránh xóa nhầm khi rollback).
- Mở rộng module mới: `ALTER TABLE attachments DROP CONSTRAINT ...; ADD CONSTRAINT ... CHECK (owner_type IN (...thêm...))` (non-breaking, chỉ nới whitelist).

### 7.6 Retention (quy mô ~40 user, C03)
- `audit_logs`: GIỮ LÂU (pháp lý §8.4) — không prune trong thời gian warranty; archive sang cold storage nếu cần.
- `access_stats`: high-volume, ít giá trị pháp lý → prune > 12 tháng (cron). `refresh_tokens` revoked/expired → cleanup hàng ngày.

---

## 8. Điểm cần Tech Lead chú ý (review trước APPROVED)

1. **D5 — không bảng `roles` riêng (CHECK 4 vai trò):** `roles_permissions.role` dùng CHECK thay FK. Đồng bộ demo-scope (4 vai trò cố định). Nếu tương lai KH cần **vai trò động** (thêm/bớt vai trò runtime) → nâng cấp: tạo bảng `roles(code PK)`, đổi CHECK thành FK ở `users.role`/`roles_permissions.role`. **Cần xác nhận 4 vai trò cố định là đủ** (CR nếu đổi).
2. **Extension `citext`:** dùng cho email case-insensitive UNIQUE. Nếu KH/DBA không muốn thêm extension → fallback: `email VARCHAR(255)` + `UNIQUE INDEX ON users(lower(email))` + app luôn lowercase email trước khi lưu/tra. **Cần chốt** (citext sạch hơn, fallback tránh extension).
3. **Vòng FK `users`↔`departments` (D3):** giải bằng tạo departments trước (lead NULL, chưa FK) → users → ALTER ADD fk_dept_lead. `department_id` và `lead_user_id` đều NULLABLE. **Cần xác nhận chấp nhận nullable** (cần thiết để seed: phòng ban trước, user sau).
4. **Audit append-only bằng trigger + REVOKE (D8):** trigger đã có trong DDL; REVOKE cần DB role riêng cho app (việc của devops migration hạ tầng). **Cần Tech Lead chốt** có tạo DB role app riêng không (khuyến nghị có — defense-in-depth §8.4).
5. **`scope` 3 giá trị {all, department, own}:** đủ cho RBAC matrix hiện tại. Nếu cần scope phức tạp hơn (vd "department + descendants" theo cây) → mở rộng giá trị + logic guard. Hiện cây phòng ban dùng cho hiển thị, scope `department` = đúng phòng user (không gồm phòng con) — **cần xác nhận** đúng kỳ vọng KH.
6. **Dedup cron chung (liên quan M1 §8.4):** M1 đề xuất thống nhất 1 cơ chế dedup cho mọi cron. M7 cung cấp `idx_notif_ref (ref_type, ref_id, type)` cho phép kiểm tra "đã gửi thông báo loại X cho bản ghi Y chưa". **Đề xuất:** dùng truy vấn trên `notifications` theo `(ref_type, ref_id, type, ngày)` làm dedup chung thay vì bảng dedup riêng mỗi module (M2 đã có `chemical_notification_dedup` — có thể giữ cho mốc-ngày chi tiết, hoặc thống nhất sau). **Cần Tech Lead chốt** cơ chế dedup chung.
7. **`customers` thuộc M7 (chốt):** M1 §8.5 để ngỏ owner của `customers`. Contract này **nhận `customers` về M7** (tạo trong migration M7) → M1 chỉ FK tới, KHÔNG tạo lại. Đồng bộ với ERD core (demo-scope đặt customers trong khối M1 nhưng đánh dấu "M7/chung" dòng 174). **Xác nhận:** M1 KHÔNG tạo `customers`.

---

## 9. Migration & Rollback

```
-- [ MIGRATION FILE NAME ] (Alembic)
-- <revision>_m7_platform.py  (depends_on: KHÔNG — đây là migration gốc)
-- Thứ tự CREATE: (xem §2 / §7.1) departments → users → ALTER fk_dept_lead/created/updated
--   → permissions → roles_permissions → customers → attachments
--   → refresh_tokens → notifications → audit_logs → access_stats
--   → trigger append-only → indexes → seed (permissions, roles_permissions, departments, admin)

-- [ EXISTING TABLE CHANGES ]
-- KHÔNG ALTER bảng có sẵn (M7 là migration đầu tiên — chưa có bảng nào).
-- ALTER nội bộ M7 (gắn FK vòng) là một phần của migration M7, KHÔNG phải breaking change với module khác.

-- [ ROLLBACK PLAN ] (downgrade) — drop ngược thứ tự FK:
DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs;
DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs;
DROP FUNCTION IF EXISTS trg_audit_logs_immutable();
DROP TABLE IF EXISTS access_stats        CASCADE;
DROP TABLE IF EXISTS audit_logs          CASCADE;
DROP TABLE IF EXISTS notifications        CASCADE;
DROP TABLE IF EXISTS refresh_tokens       CASCADE;
DROP TABLE IF EXISTS attachments          CASCADE;
DROP TABLE IF EXISTS customers            CASCADE;
DROP TABLE IF EXISTS roles_permissions    CASCADE;
DROP TABLE IF EXISTS permissions          CASCADE;
-- gỡ FK vòng trước khi drop users/departments
ALTER TABLE departments DROP CONSTRAINT IF EXISTS fk_dept_lead;
ALTER TABLE departments DROP CONSTRAINT IF EXISTS fk_dept_created;
ALTER TABLE departments DROP CONSTRAINT IF EXISTS fk_dept_updated;
DROP TABLE IF EXISTS users                CASCADE;
DROP TABLE IF EXISTS departments          CASCADE;
-- KHÔNG drop extension pgcrypto/pg_trgm/citext (dùng chung toàn hệ thống).
-- CẢNH BÁO: rollback M7 chỉ khi đã rollback M1/M2/M3... trước (chúng FK tới M7).

-- [ DATA DEPENDENCIES ]
-- Seed TRƯỚC (trong chính migration M7): permissions → roles_permissions → departments mẫu → admin.
-- Phụ thuộc M7 (tạo SAU): users/departments dùng bởi M1/M2/M3/M4/M5/M6;
--   customers/attachments/audit_logs/notifications dùng chung; samples (M1) → chemical_transactions (M2).
-- KHÔNG có circular FK ngoài cặp users↔departments (đã giải bằng D3 trong cùng migration M7).
```

### Cập nhật ERD master (`01-demo-scope.md` mục C — khối AUTH & HỆ THỐNG)
So với ERD core, contract này BỔ SUNG/CHUẨN HÓA:
- `users`: thêm `status`, `last_login_at`, `password_changed_at`, audit fields; `role` đổi từ native ENUM → CHECK VARCHAR.
- `departments`: thêm `status`, audit fields; `lead_user_id` + `parent_id` đã có trong ERD core (giữ).
- Tách `permissions` (mới) khỏi `roles_permissions`; `roles_permissions` thêm `scope`.
- Bảng MỚI: `refresh_tokens`, `attachments` (ERD core đặt ở khối M1 — chuyển về M7/chung), `audit_logs`/`notifications`/`access_stats` (ERD core đặt ở khối M7 — giữ, bổ sung cột), `customers` (chuyển về M7/chung).
→ Đề nghị Tech Lead cập nhật ERD master sau khi APPROVED.

---

*Hết Contract M7 Schema v1.0. Tuân thủ: PK UUID gen_random_uuid, CHECK thay native ENUM, NUMERIC/TIMESTAMPTZ/INET không float, FK rõ ON DELETE, vòng FK users↔departments giải bằng nullable + ALTER, audit append-only (trigger + REVOKE), bcrypt cost ≥10, refresh token rotation lưu hash, index mọi FK + query pattern nóng, seed RBAC matrix + admin ép đổi MK, rollback + thứ tự migration M7→M1→M2 đầy đủ, traceability M7.x + R13/R15 + §8.4. Đồng bộ tuyệt đối quy ước với Contract M1 & M2. Chờ `/contract` gate APPROVED trước khi feature-builder implement.*
