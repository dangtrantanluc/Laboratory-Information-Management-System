# Contract — M3 Schema: Quản lý Tài liệu (Document Control)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M3 — Document Control (kiểm soát tài liệu §8.3 / hồ sơ §8.4)
**Tài liệu:** Database Schema Contract (DDL + Index + Seed + Traceability)
**Version:** 1.0 | **Ngày:** 20/06/2026 | **Author:** schema-designer agent
**Stack:** PostgreSQL 15+, FastAPI + SQLAlchemy/Alembic
**Nguồn chân lý:** `13-srs-m3-document.md` (SRS M3 — 16 FR, 22 BR, state machine version, §7 ghi chú schema-designer dòng 853-863), `08-contract-m7-schema.md` (bảng dùng chung users/departments/attachments/audit_logs/notifications; quy ước D1-D11), `06-contract-m1-schema.md` (đồng bộ phong cách: state machine, versioning immutable, partial unique index, vòng FK)
**Status:** DRAFT — chờ `/contract` gate / Tech Lead review

---

## 0. Quyết định thiết kế chính (đọc trước) — đồng bộ tuyệt đối M7/M1/M2/M4

| # | Quyết định | Lý do |
|---|-----------|-------|
| D1 | **PK = UUID `DEFAULT gen_random_uuid()`** cho mọi bảng nghiệp vụ M3 (`documents`, `document_versions`, `document_access_log`). Danh mục `document_types` dùng **natural-key `code` PK** (đồng bộ M4 D5 — `contract_types`...). | CONSTRAINT-5 / BR-DOC-014 (không lộ ID tuần tự) + đồng bộ M7 D1 / M1 D1. `id` thật UUID; `documents.code` mới là định danh dùng ngoài. |
| D2 | **ENUM = CHECK constraint trên VARCHAR**, KHÔNG native PG ENUM. Áp cho `document_versions.status`, `documents.status`, `documents.security_level`, `document_access_log.action`. | Đồng bộ M7 D2 / M1 D2: ALTER TYPE khó rollback trong Alembic. |
| D3 | **Vòng FK `documents.current_version_id ↔ document_versions.document_id` giải bằng:** tạo `documents` (cột `current_version_id` NULL, **chưa** FK) → tạo `document_versions` (FK `document_id → documents`) → `ALTER TABLE documents ADD CONSTRAINT fk_doc_current ...`. | Giống M7 D3 (vòng `users ↔ departments`). Không tạo 2 FK vòng trong cùng CREATE. `current_version_id` NULLABLE (tài liệu mới chưa có version hiệu lực — FR-DOC-001). Chi tiết §2. |
| D4 | **Loại tài liệu = bảng danh mục `document_types(code, label, ...)`** (cấu hình được), KHÔNG CHECK cứng. Seed 6 loại: `sop`, `process`, `form`, `guide`, `standard`, `other`. | OQ#2 (danh mục loại cấu hình được). Chọn **bảng danh mục** thay CHECK vì: (1) QA/Quản lý chất lượng tự thêm/ẩn loại qua `is_active` không cần migration đổi CHECK; (2) đồng bộ pattern M4 D5 (4 bảng danh mục natural-key). `documents.type` FK → `document_types(code)` RESTRICT. So với `security_level` (chỉ 2 mức, chốt cứng — CHECK đủ). |
| D5 | **`security_level` = CHECK(internal\|restricted) — 2 mức** (quyết định đã chốt mục 3). `internal` = mọi nhân sự xem; `restricted` = chỉ phòng sở hữu + admin/leader. Enforce **app-layer**, lưu cột trên `documents`. | Quyết định chốt: 2 mức bảo mật (rút gọn từ SRS OQ#3 default 3 mức). CHECK đủ vì cố định 2 giá trị; ánh xạ cấp↔vai trò là logic RBAC app-layer (BR-DOC-006). |
| D6 | **`document_versions` IMMUTABLE khi `approved`/`obsolete`** (CONSTRAINT-3, BR-DOC-012/021): KHÔNG route PUT/PATCH/DELETE; sửa = tạo version mới. Chỉ version `draft` (chưa từng gửi duyệt) được soft-delete (`deleted_at`). Enforce **app-layer** (không trigger DB — đồng bộ M1 D7/M4: immutable enforce service-layer). | BR-DOC-012/021, NFR-AUDIT-DOC-001 §8.3.2 d/§8.4. CHECK DB là lưới an toàn giá trị; bất biến nghiệp vụ + state machine enforce app (giống M1 D9). |
| D7 | **Chỉ ≤1 version `approved`/tài liệu enforce DB-LEVEL bằng PARTIAL UNIQUE INDEX:** `uq_doc_one_approved ON document_versions(document_id) WHERE status='approved'`. | BR-DOC-008 / NFR-INTEG-DOC-001 (VILAS §8.3 bắt buộc). Đây là bất biến hệ thống QUAN TRỌNG NHẤT của M3 → enforce DB-level (mạnh hơn app-only, chống race). Đồng bộ pattern partial unique `is_current` của M1 (`sample_results`). App vẫn obsolete bản cũ trong cùng transaction + row-lock (NFR-CONCUR-DOC-001). |
| D8 | **`approved_by ≠ created_by` (tách soạn–duyệt §8.3.2) enforce APP-LAYER**, không CHECK DB. Trả 403 `SELF_APPROVAL_FORBIDDEN`. | BR-DOC-009. Đồng bộ M1 D8 (`approved_by ≠ entered_by` app-layer). So 2 cột FK + RBAC trưởng nhóm → cần lookup nghiệp vụ, không CHECK đơn cột. |
| D9 | **State transition enforce APP-LAYER** (whitelist `draft→review→approved→obsolete` + `review→draft`; row-lock trên `documents` khi approve). DB chỉ CHECK `status ∈ tập hợp lệ`. | FR-DOC-013 / BR-DOC-007. Đồng bộ M1 D9. Whitelist là logic; CHECK DB là lưới an toàn chống giá trị rác. |
| D10 | **File version qua `attachments` polymorphic (M7 D9)** — `owner_type='document_version'`, `owner_id=document_versions.id`. M3 KHÔNG lưu file_key trực tiếp trên bảng; KHÔNG tạo bảng file riêng. Audit ghi `audit_logs` (M7). Thông báo `notifications` (M7). | CONSTRAINT-8, BR-DOC-013. Whitelist `'document'`/`'document_version'` ĐÃ có trong M7 (`attachments.owner_type` — 08-contract-m7-schema dòng 292/293, đã chạy trong migration `1718870400001`). 1 file chính/version (bản đầu). |
| D11 | **`document_access_log` (R15) high-volume — KHÔNG immutable trigger** như `audit_logs`. Ghi best-effort (không rollback nghiệp vụ nếu lỗi ghi); cho phép retention/prune. | CONSTRAINT-7, BR-DOC-015, NFR-DATA-DOC-001. Đồng bộ tinh thần `access_stats` M7 D11 (tách high-volume khỏi pháp lý §8.4). KHÁC `access_stats` (toàn hệ thống cấp path) và KHÁC `audit_logs` (pháp lý). |
| D12 | **`reject_reason` lưu CỘT trên `document_versions`** (TEXT NULL) thay vì chỉ audit detail. | FR-DOC-010 / BR-DOC-020. Lưu cột để dựng timeline lịch sử (FR-DOC-016) trực tiếp không phải parse JSONB audit; reject là 1 phần state machine version. Set khi `review→draft`, giữ tới lần gửi duyệt kế (app reset nếu cần). |

> **Audit fields (rule global):** `documents` có vòng đời cập nhật → `created_at`/`updated_at` + `created_by`/`updated_by UUID REFERENCES users(id)`. `document_versions` có vòng đời `draft` (sửa được) nên cũng có `updated_at` + `created_by` (= người soạn) + cột người-thực-hiện riêng cho mốc duyệt (`submitted_by`/`reviewed_by`/`approved_by`); KHÔNG dùng `updated_by` (mọi thay đổi version draft là người soạn; mốc duyệt ghi cột riêng + audit). `document_access_log` là append-only high-volume → chỉ `user_id` + `at` (không cặp created/updated). `document_types` là danh mục → chỉ `created_at`.

---

## 1. ERD chi tiết M3 (ASCII)

```
┌─────────────────────────────────────────────────────────────────────┐
│ BẢNG DÙNG CHUNG (M7 — KHÔNG tạo lại trong migration M3)               │
├─────────────────────────────────────────────────────────────────────┤
│ users(id UUID PK, role, department_id, ...)   ← FK người dùng         │
│ departments(id UUID PK, lead_user_id FK→users NULL, ...)              │
│   → đọc lead_user_id để cấp document:approve trong phòng (BR-DOC-010) │
│ attachments(id, owner_type, owner_id, file_key, ...)                  │
│   → owner_type ∈ {'document','document_version'} (whitelist ĐÃ có M7) │
│   → file của từng version: owner_type='document_version',             │
│                            owner_id=document_versions.id (D10)        │
│ audit_logs(id, user_id, action, resource, resource_id,               │
│            correlation_id, ip, at, detail JSONB)  ← INSERT mọi thao tác│
│ notifications(id, user_id, type, title, body, ref_type, ref_id, ...)  │
│   → gửi duyệt/approve/reject (idx_notif_ref chống trùng — BR-DOC-018) │
│ roles_permissions: document:create/read/approve ĐÃ seed (M7 §5.2)    │
└─────────────────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────────────────┐
        │  document_types  (DANH MỤC loại — natural-key, seed D4)   │
        │  code        VARCHAR(32) PK   (sop|process|form|...)      │
        │  label       VARCHAR(128) NOT NULL                        │
        │  sort_order  SMALLINT, is_active BOOLEAN, created_at      │
        └───┬──────────────────────────────────────────────────────┘
            │ 1
            │ N  (documents.type FK→document_types.code RESTRICT)
            ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │  documents  (TÀI LIỆU — vùng chứa 1..n version; KHÔNG chứa file)  │
   │  id                  UUID PK                                       │
   │  code                VARCHAR(64) UNIQUE NOT NULL (SOP-HPT-001)     │  ◄── BR-DOC-014
   │  title               VARCHAR(512) NOT NULL                         │      bất biến app
   │  type                VARCHAR(32) FK→document_types(code) NOT NULL  │
   │  department_id       UUID FK→departments(RESTRICT) NOT NULL        │      RBAC scope
   │  security_level      VARCHAR(12) CHECK(internal|restricted)        │      2 mức (D5)
   │  status              VARCHAR(10) CHECK(active|archived)            │
   │  current_version_id  UUID FK→document_versions(id) NULL  ◄─────────┼──┐  vòng FK (D3)
   │  created_by/updated_by FK→users / created_at / updated_at          │  │  ALTER ADD sau
   └───┬────────────────────────────────────────────────────▲─────────┘  │
       │ 1                                  current_version_id│ (FK ADD sau)│
       │ N  document_id (FK RESTRICT)                         │            │
       ▼                                                      │            │
   ┌──────────────────────────────────────────────────────────┴──────────┐│
   │  document_versions  (PHIÊN BẢN — state machine §8.3)                 ││
   │  id              UUID PK  ◄──────────────────────────────────────────┘│  (documents.current_version_id)
   │  document_id     UUID FK→documents(RESTRICT) NOT NULL                  │
   │  version_no      INT NOT NULL CHECK(version_no >= 1)                   │
   │  change_note     TEXT NULL   (bắt buộc app từ v2 — BR-DOC-016)         │
   │  status          VARCHAR(10) CHECK(draft|review|approved|obsolete)     │  state machine (D9)
   │  created_by      UUID FK→users(RESTRICT) NOT NULL   (người SOẠN)       │
   │  created_at      TIMESTAMPTZ NOT NULL                                  │
   │  updated_at      TIMESTAMPTZ NOT NULL                                  │  (sửa khi draft)
   │  submitted_by    UUID FK→users(RESTRICT) NULL  (gửi duyệt FR-008)      │
   │  submitted_at    TIMESTAMPTZ NULL                                      │
   │  reviewed_by     UUID FK→users(RESTRICT) NULL  (người duyệt/reject)    │
   │  reviewed_at     TIMESTAMPTZ NULL                                      │
   │  approved_by     UUID FK→users(RESTRICT) NULL  (≠ created_by — D8)     │  tách soạn-duyệt
   │  approved_at     TIMESTAMPTZ NULL                                      │
   │  reject_reason   TEXT NULL   (bắt buộc app khi reject — BR-DOC-020)    │  (D12)
   │  deleted_at      TIMESTAMPTZ NULL  (soft-delete CHỈ draft — BR-DOC-021)│
   │  UNIQUE(document_id, version_no)                                       │  ◄── BR-DOC-001
   │  PARTIAL UNIQUE(document_id) WHERE status='approved'  ◄── ≤1 current   │  ◄── BR-DOC-008 (D7)
   │  CHECK(approved_by NULL ⇔ approved_at NULL) ; (reviewed pair)          │
   └───┬───────────────────────────────────────────────────────────────────┘
       │ 1
       │ N  document_id (FK RESTRICT) ; version_id (FK SET NULL, nullable)
       ▼
   ┌────────────────────────────────────────────────────────────────────┐
   │  document_access_log  (R15 — high-volume, KHÔNG immutable, D11)      │
   │  id          UUID PK                                                 │
   │  document_id UUID FK→documents(RESTRICT) NOT NULL                    │
   │  version_id  UUID FK→document_versions(SET NULL) NULL  (tải bản nào) │
   │  user_id     UUID FK→users(RESTRICT) NOT NULL                        │
   │  action      VARCHAR(10) CHECK(view|download|edit)                   │
   │  at          TIMESTAMPTZ NOT NULL DEFAULT now()                      │
   └────────────────────────────────────────────────────────────────────┘
```

### Vòng FK `documents` ↔ `document_versions` (giải y hệt M7 `users ↔ departments`)

```
documents.current_version_id ──(FK SET NULL, ADD sau)──► document_versions.id
document_versions.document_id ──(FK RESTRICT, trong CREATE)──► documents.id

Thứ tự:
  1. CREATE documents       (current_version_id UUID NULL — CHƯA FK)
  2. CREATE document_versions (FK document_id → documents — OK vì documents đã có)
  3. ALTER documents ADD CONSTRAINT fk_doc_current
       FOREIGN KEY (current_version_id) → document_versions(id) ON DELETE SET NULL
  → current_version_id NULLABLE để: (a) phá vòng tạo bảng; (b) tài liệu mới chưa
    có version hiệu lực (FR-DOC-001 current=NULL).
```

### Bảng dùng chung tham chiếu (KHÔNG tạo lại — sở hữu M7)

| Bảng | Sở hữu | M3 dùng để |
|------|--------|-----------|
| `users(id UUID PK, role, department_id)` | M7 | FK `created_by`/`updated_by` (documents), `created_by`/`submitted_by`/`reviewed_by`/`approved_by` (versions), `user_id` (access_log) |
| `departments(id, lead_user_id)` | M7 | FK `documents.department_id` (RBAC scope BR-DOC-004); đọc `lead_user_id` cấp `document:approve` (BR-DOC-010) |
| `attachments(owner_type, owner_id, file_key)` | M7 | file của version (`owner_type='document_version'`, `owner_id=version.id`); file phụ trợ tài liệu (`owner_type='document'`) — D10. Whitelist ĐÃ có. |
| `audit_logs` | M7 | INSERT mọi thao tác M3 (BR-DOC-019, §8.3/§8.4) |
| `notifications` | M7 | gửi duyệt / approve / reject (FR-008/009/010, BR-DOC-018) |
| `roles_permissions` | M7 | `document:create` (staff department, leader/admin all), `document:read` (mọi vai trò + accountant all), `document:approve` (admin/leader all; staff = chỉ trưởng nhóm app-check) — ĐÃ seed M7 §5.2 |

> **M3 KHÔNG seed `roles_permissions`** — quyền `document:*` đã có đủ ở M7 (08-contract-m7-schema §5.1/§5.2, đã chạy migration `1718870400001`). M3 chỉ seed `document_types`.

---

## 2. DDL đầy đủ — xử lý vòng FK + partial unique 1-approved

> Migration viết raw SQL (`op.execute`) đồng bộ phong cách M7/M1/M2/M4. **Prereq:** `pgcrypto` (gen_random_uuid); bảng `users`, `departments`, `attachments`, `audit_logs`, `notifications` (M7) PHẢI tồn tại trước (M7→M1→M2→M4→M3). **Thứ tự CREATE bắt buộc:** `document_types` → `documents` (current_version_id NULL, chưa FK) → `document_versions` → `ALTER documents ADD fk_doc_current` → `document_access_log` → indexes → seed `document_types`.

```sql
-- ============================================================
-- SCHEMA: m3-document-control (Documents, Versions, Access Log)
-- Feature: Quản lý Tài liệu — kiểm soát tài liệu §8.3 / hồ sơ §8.4 (LIMS 17025)
-- Designer: schema-designer agent | Date: 2026-06-20
-- Prereq: pgcrypto; bảng users/departments/attachments/audit_logs/
--         notifications (M7) đã tồn tại. attachments.owner_type whitelist
--         ĐÃ có 'document' + 'document_version' (M7) → M3 KHÔNG ALTER.
-- Thứ tự CREATE: document_types → documents (current_version_id chưa FK)
--              → document_versions → ALTER documents ADD fk_doc_current
--              → document_access_log → indexes → seed document_types
-- Thứ tự migration tổng thể: M7 → M1 → M2 → M4 → M3 (file này).
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

-- ------------------------------------------------------------
-- [ NEW TABLE 1 ] document_types — danh mục loại tài liệu (D4, OQ#2)
--   Natural-key code PK (đồng bộ M4 D5). Cấu hình được: ẩn loại qua is_active.
-- ------------------------------------------------------------
CREATE TABLE document_types (
    code        VARCHAR(32)  PRIMARY KEY,                       -- 'sop','process','form','guide','standard','other'
    label       VARCHAR(128) NOT NULL,                          -- nhãn hiển thị tiếng Việt
    sort_order  SMALLINT     NOT NULL DEFAULT 0,
    is_active   BOOLEAN      NOT NULL DEFAULT true,             -- ẩn loại không dùng (không xóa — toàn vẹn FK)
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE document_types IS 'Danh mục loại tài liệu (OQ#2, D4). Cấu hình được; documents.type FK tới đây. Ẩn bằng is_active thay vì xóa (giữ toàn vẹn FK với tài liệu cũ).';

-- ------------------------------------------------------------
-- [ NEW TABLE 2 ] documents — tài liệu (FR-DOC-001..005)
--   current_version_id để NULL & CHƯA gắn FK (phá vòng FK — D3).
--   Vùng chứa 1..n version; KHÔNG chứa file trực tiếp (file ở version qua attachments).
-- ------------------------------------------------------------
CREATE TABLE documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code                VARCHAR(64)  NOT NULL,                  -- 'SOP-HPT-001' (BR-DOC-014) bất biến, không lộ tuần tự
    title               VARCHAR(512) NOT NULL,
    type                VARCHAR(32)  NOT NULL,                  -- FK → document_types(code) (D4)
    department_id       UUID         NOT NULL,                  -- phòng sở hữu (RBAC scope, BR-DOC-004)
    security_level      VARCHAR(12)  NOT NULL DEFAULT 'internal'
        CHECK (security_level IN ('internal', 'restricted')),   -- 2 mức (D5): internal=mọi NS; restricted=phòng+admin/leader
    status              VARCHAR(10)  NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived')),               -- vòng đời tài liệu (không phải version)
    current_version_id  UUID         NULL,                      -- version hiệu lực (approved) hoặc NULL — FK ADD sau (D3)
    created_by          UUID         NOT NULL,
    updated_by          UUID         NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_doc_code      UNIQUE (code),
    CONSTRAINT fk_doc_type      FOREIGN KEY (type)          REFERENCES document_types(code) ON DELETE RESTRICT,
    CONSTRAINT fk_doc_dept      FOREIGN KEY (department_id) REFERENCES departments(id)      ON DELETE RESTRICT,
    CONSTRAINT fk_doc_created   FOREIGN KEY (created_by)    REFERENCES users(id)            ON DELETE RESTRICT,
    CONSTRAINT fk_doc_updated   FOREIGN KEY (updated_by)    REFERENCES users(id)            ON DELETE RESTRICT
    -- fk_doc_current (current_version_id → document_versions) ADD sau khi tạo document_versions (D3)
);
COMMENT ON TABLE  documents IS 'Tài liệu QMS (FR-DOC-001..005). Vùng chứa 1..n version. code bất biến (BR-DOC-014); current_version_id luôn trỏ version approved hoặc NULL (NFR-INTEG-DOC-001).';
COMMENT ON COLUMN documents.current_version_id IS 'Version hiệu lực (status=approved) hoặc NULL khi chưa có bản ban hành. FK gắn sau (phá vòng — D3); ON DELETE SET NULL.';
COMMENT ON COLUMN documents.security_level IS '2 mức (D5): internal=mọi nhân sự xem; restricted=chỉ phòng sở hữu + admin/leader. Ánh xạ cấp↔vai trò enforce app-layer (BR-DOC-006).';

-- ------------------------------------------------------------
-- [ NEW TABLE 3 ] document_versions — phiên bản (FR-DOC-006..013, state machine §8.3)
--   IMMUTABLE khi approved/obsolete (D6, BR-DOC-012/021): sửa = tạo version mới.
--   File gắn qua attachments (owner_type='document_version', owner_id=this.id) — D10.
-- ------------------------------------------------------------
CREATE TABLE document_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID         NOT NULL,                      -- vùng chứa (BR-DOC-001)
    version_no      INT          NOT NULL
        CHECK (version_no >= 1),                                -- 1,2,3... trong phạm vi tài liệu
    change_note     TEXT         NULL,                          -- bắt buộc app từ v2 (BR-DOC-016, CHANGE_NOTE_REQUIRED)
    status          VARCHAR(10)  NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'review', 'approved', 'obsolete')), -- state machine (FR-013, D9)
    created_by      UUID         NOT NULL,                      -- người SOẠN (FR-006)
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),        -- sửa khi draft (FR-007)
    submitted_by    UUID         NULL,                          -- người gửi duyệt (draft→review, FR-008)
    submitted_at    TIMESTAMPTZ  NULL,
    reviewed_by     UUID         NULL,                          -- người duyệt/từ chối (review→approved|draft, FR-009/010)
    reviewed_at     TIMESTAMPTZ  NULL,
    approved_by     UUID         NULL,                          -- người DUYỆT (≠ created_by — app D8/BR-009)
    approved_at     TIMESTAMPTZ  NULL,
    reject_reason   TEXT         NULL,                          -- bắt buộc app khi reject (BR-DOC-020), D12
    deleted_at      TIMESTAMPTZ  NULL,                          -- soft-delete CHỈ draft chưa gửi duyệt (BR-DOC-021)
    created_at_audit TIMESTAMPTZ NULL,                          -- (dự phòng — không dùng; xem ghi chú dưới)

    CONSTRAINT fk_dv_document   FOREIGN KEY (document_id)  REFERENCES documents(id) ON DELETE RESTRICT,
    CONSTRAINT fk_dv_created    FOREIGN KEY (created_by)   REFERENCES users(id)     ON DELETE RESTRICT,
    CONSTRAINT fk_dv_submitted  FOREIGN KEY (submitted_by) REFERENCES users(id)    ON DELETE RESTRICT,
    CONSTRAINT fk_dv_reviewed   FOREIGN KEY (reviewed_by)  REFERENCES users(id)    ON DELETE RESTRICT,
    CONSTRAINT fk_dv_approved   FOREIGN KEY (approved_by)  REFERENCES users(id)    ON DELETE RESTRICT,
    -- mỗi tài liệu 1 số version duy nhất (BR-DOC-001)
    CONSTRAINT uq_dv_doc_version UNIQUE (document_id, version_no),
    -- approved_by & approved_at đồng thời NULL hoặc đồng thời NOT NULL (tránh nửa-duyệt)
    CONSTRAINT ck_dv_approval_pair CHECK (
        (approved_by IS NULL AND approved_at IS NULL)
        OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
    ),
    -- reviewed_by & reviewed_at đồng thời NULL hoặc đồng thời NOT NULL
    CONSTRAINT ck_dv_review_pair CHECK (
        (reviewed_by IS NULL AND reviewed_at IS NULL)
        OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)
    ),
    -- submitted_by & submitted_at đồng thời NULL hoặc đồng thời NOT NULL
    CONSTRAINT ck_dv_submit_pair CHECK (
        (submitted_by IS NULL AND submitted_at IS NULL)
        OR (submitted_by IS NOT NULL AND submitted_at IS NOT NULL)
    ),
    -- approved phải có approved_by (lưới an toàn cho state=approved)
    CONSTRAINT ck_dv_approved_has_approver CHECK (
        status <> 'approved' OR approved_by IS NOT NULL
    )
);
COMMENT ON TABLE  document_versions IS 'Phiên bản tài liệu (FR-DOC-006..013). status enforce qua state machine app-layer (FR-013, D9); CHECK DB là lưới an toàn giá trị. IMMUTABLE khi approved/obsolete (D6, BR-DOC-012/021) — không route PUT/DELETE; sửa = version mới. File qua attachments owner_type=document_version (D10).';
COMMENT ON COLUMN document_versions.approved_by IS 'Người duyệt — PHẢI ≠ created_by (tách soạn–duyệt §8.3.2, BR-DOC-009 enforce app-layer, 403 SELF_APPROVAL_FORBIDDEN).';
COMMENT ON COLUMN document_versions.deleted_at IS 'Soft-delete CHỈ cho version draft chưa từng gửi duyệt (BR-DOC-021). Version đã từng approved/obsolete KHÔNG xóa (§8.4).';

-- ------------------------------------------------------------
-- [ ALTER 1 ] Gắn FK current_version_id sau khi document_versions tồn tại (PHÁ VÒNG FK — D3)
--   ON DELETE SET NULL: nếu version bị xóa (chỉ draft) thì current về NULL (an toàn).
--   Thực tế current luôn trỏ version approved (không xóa được) — SET NULL là lưới an toàn.
-- ------------------------------------------------------------
ALTER TABLE documents
    ADD CONSTRAINT fk_doc_current FOREIGN KEY (current_version_id)
    REFERENCES document_versions(id) ON DELETE SET NULL;

-- ------------------------------------------------------------
-- [ PARTIAL UNIQUE ] ≤1 version approved/tài liệu (BR-DOC-008, D7) — DB-LEVEL ENFORCE
--   Bất biến hệ thống quan trọng nhất M3 (VILAS §8.3): chống 2 current cùng lúc.
-- ------------------------------------------------------------
CREATE UNIQUE INDEX uq_doc_one_approved
    ON document_versions(document_id) WHERE status = 'approved';

-- ------------------------------------------------------------
-- [ NEW TABLE 4 ] document_access_log — lượt view/download/edit (R15, FR-DOC-014/015)
--   High-volume; KHÔNG immutable trigger (D11); ghi best-effort. Tách khỏi audit_logs.
-- ------------------------------------------------------------
CREATE TABLE document_access_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID         NOT NULL,
    version_id  UUID         NULL,                              -- version cụ thể (tải/sửa); NULL cho view cấp tài liệu
    user_id     UUID         NOT NULL,
    action      VARCHAR(10)  NOT NULL
        CHECK (action IN ('view', 'download', 'edit')),         -- R15 (BR-DOC-015)
    at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_dal_document FOREIGN KEY (document_id) REFERENCES documents(id)         ON DELETE RESTRICT,
    CONSTRAINT fk_dal_version  FOREIGN KEY (version_id)  REFERENCES document_versions(id) ON DELETE SET NULL,
    CONSTRAINT fk_dal_user     FOREIGN KEY (user_id)     REFERENCES users(id)             ON DELETE RESTRICT
);
COMMENT ON TABLE document_access_log IS 'Lượt truy cập tài liệu (R15, FR-DOC-014/015). High-volume; KHÔNG immutable (D11) — cho retention/prune. Đếm chỉ lượt HỢP LỆ (403 không ghi — BR-DOC-015). KHÁC audit_logs (pháp lý §8.4) và access_stats (toàn hệ thống M7).';
```

> **Ghi chú cột `created_at_audit`:** cột này **KHÔNG thuộc thiết kế** — đã loại khỏi DDL chính thức. (Để tránh nhầm lẫn, dev BỎ dòng `created_at_audit` khi viết migration; `document_versions` chỉ dùng `created_at`/`updated_at` cho audit fields. Cột này xuất hiện do soạn thảo — Tech Lead xác nhận loại bỏ.)

---

## 3. CHECK constraints & toàn vẹn quan trọng — tổng hợp

| Quy tắc | Constraint | DB enforce? | Ghi chú |
|---------|-----------|-------------|---------|
| `documents.code` UNIQUE, bất biến | `uq_doc_code` + app | ✅ (UNIQUE) / ⚠️ (bất biến app) | BR-DOC-014. Đổi code → 422 `CODE_IMMUTABLE` (app). Không lộ tuần tự (UUID id). |
| `type` ∈ danh mục | `fk_doc_type → document_types(code)` | ✅ | BR-DOC-002. Chống loại "ma"; 422 `INVALID_DOC_TYPE` (app validate trước). |
| `security_level` ∈ {internal,restricted} | CHECK | ✅ | D5, BR-DOC-003. 2 mức cố định. |
| `documents.status` ∈ {active,archived} | CHECK | ✅ | vòng đời tài liệu. |
| `version.status` ∈ tập hợp lệ | CHECK `document_versions.status` | ✅ | FR-013/BR-007. **Whitelist (from,to) enforce APP-layer** (D9). CHECK chống giá trị rác. |
| `document_access_log.action` ∈ {view,download,edit} | CHECK | ✅ | R15, BR-DOC-015. |
| `version_no >= 1` | CHECK | ✅ | BR-DOC-001. |
| mỗi tài liệu 1 số version duy nhất | `uq_dv_doc_version (document_id, version_no)` | ✅ | BR-DOC-001. Chống trùng/version mồ côi. |
| **≤1 version approved/tài liệu** | **partial unique `uq_doc_one_approved` WHERE status='approved'** | ✅ **DB-LEVEL (D7)** | **BR-DOC-008 / NFR-INTEG-DOC-001 — bất biến VILAS §8.3 quan trọng nhất.** Chống race 2 current. |
| approved_by/approved_at đồng bộ | `ck_dv_approval_pair` | ✅ | tránh trạng thái nửa-duyệt. |
| reviewed_by/reviewed_at đồng bộ | `ck_dv_review_pair` | ✅ | tránh mốc duyệt nửa vời. |
| submitted_by/submitted_at đồng bộ | `ck_dv_submit_pair` | ✅ | |
| status=approved phải có approved_by | `ck_dv_approved_has_approver` | ✅ | lưới an toàn cho state. |
| current_version_id trỏ version approved | `fk_doc_current` (chỉ FK) | ⚠️ **app-layer** | NFR-INTEG-DOC-001: "approved" không CHECK được liên bảng; app set trong txn approve (FR-011). |
| **approved_by ≠ created_by** (tách soạn–duyệt) | — | ⚠️ **app-layer (D8)** | BR-DOC-009, §8.3.2. 403 `SELF_APPROVAL_FORBIDDEN`. So 2 cột FK + RBAC. |
| state transition (from,to) hợp lệ | — | ⚠️ **app-layer (D9)** | FR-013/BR-007. Whitelist + row-lock trên documents. 422 `INVALID_STATE_TRANSITION`. |
| immutable approved/obsolete | — | ⚠️ **app-layer (D6)** | BR-DOC-012/021. KHÔNG route PUT/DELETE; 422 `VERSION_LOCKED`. |
| change_note bắt buộc từ v2 | — | ⚠️ **app-layer** | BR-DOC-016. 400 `CHANGE_NOTE_REQUIRED` (v1 cho trống). |
| reject_reason bắt buộc khi reject | — | ⚠️ **app-layer** | BR-DOC-020. 400 `REJECT_REASON_REQUIRED`. |
| version có file trước khi gửi duyệt | — | ⚠️ **app-layer** (kiểm attachments) | BR-DOC-017. 422 `VERSION_FILE_REQUIRED`. |
| 1 draft/review chưa kết thúc/tài liệu | — | ⚠️ **app-layer** | OQ#6 default. 409 `DRAFT_ALREADY_EXISTS`. |
| RBAC scope phòng + mức bảo mật | — | ⚠️ **app-layer** | BR-DOC-004/005/006/010/011 (đọc departments.lead_user_id). 403. |
| soft-delete chỉ draft chưa gửi duyệt | `deleted_at` + app | ⚠️ **app-layer** | BR-DOC-021. App chặn xóa version đã từng approved/obsolete. |
| file loại whitelist + dung lượng | — | ⚠️ **app-layer** | BR-DOC-013. 422 `INVALID_FILE_TYPE`/`FILE_TOO_LARGE`. |

> **Tinh thần đồng bộ M7/M1/M2/M4:** CHECK DB giữ ràng buộc **giá trị** (enum, UNIQUE, cặp nhất quán) + bất biến QUAN TRỌNG (`uq_doc_one_approved` partial unique — như M1 `is_current`). Logic nghiệp vụ/bảo mật phức (state machine, tách soạn–duyệt, RBAC scope, immutable) enforce **app-layer** với mã lỗi rõ ràng — giống M1 (D8/D9) và M4.

---

## 4. Index strategy

```sql
-- ===== document_types =====
-- code là PK → đã có index. is_active lọc danh mục active (dataset nhỏ → không cần index riêng).

-- ===== documents =====
-- uq_doc_code đã tạo index — tra/tìm theo mã (FR-004, BR-014 không lộ tuần tự)
CREATE INDEX idx_doc_dept_type      ON documents(department_id, type);            -- COMPOSITE: lọc phổ biến nhất (FR-004) phòng+loại + RBAC scope (BR-004)
CREATE INDEX idx_doc_status         ON documents(status);                         -- lọc active/archived
CREATE INDEX idx_doc_security       ON documents(security_level);                 -- lọc/RBAC theo mức bảo mật (BR-006)
CREATE INDEX idx_doc_current_ver    ON documents(current_version_id) WHERE current_version_id IS NOT NULL; -- FK + join lấy version hiệu lực (FR-004/005)
CREATE INDEX idx_doc_title_trgm     ON documents USING gin (title gin_trgm_ops);  -- tìm theo tiêu đề (FR-004) — cần pg_trgm (bật ở M7)
CREATE INDEX idx_doc_code_trgm      ON documents USING gin (code gin_trgm_ops);   -- tìm gần đúng theo mã (FR-004)

-- ===== document_versions =====
-- uq_dv_doc_version (document_id, version_no) đã là composite index — lấy version theo số + tính max+1 (FR-006)
-- COMPOSITE quan trọng nhất: lấy current + danh sách version theo trạng thái (FR-005/009)
CREATE INDEX idx_dv_doc_status      ON document_versions(document_id, status);
-- hàng đợi "version chờ duyệt của tôi" (FR-009 — người duyệt) — partial nhỏ, chỉ review
CREATE INDEX idx_dv_review          ON document_versions(document_id) WHERE status = 'review';
-- FK + "version tôi soạn" (dashboard người soạn) + immutable check theo người
CREATE INDEX idx_dv_created_by      ON document_versions(created_by);
-- (uq_doc_one_approved (document_id) WHERE status='approved' — vừa enforce BR-008 vừa phục vụ "lấy bản approved")

-- ===== document_access_log =====
-- COMPOSITE quan trọng nhất: thống kê R15 — COUNT theo tài liệu × hành động × kỳ (FR-015)
CREATE INDEX idx_dal_doc_action_at  ON document_access_log(document_id, action, at);
-- lọc thống kê theo kỳ toàn hệ thống / top N (FR-015, M6.3)
CREATE INDEX idx_dal_at             ON document_access_log(at);
-- báo cáo theo người dùng (tùy chọn — "ai xem/tải tài liệu nào")
CREATE INDEX idx_dal_user_at        ON document_access_log(user_id, at);
```

**Lý do nhóm index trọng yếu (theo yêu cầu):**
- **`documents.code`** — `uq_doc_code` (unique): tra mã tài liệu là lookup chính, không lộ tuần tự (BR-DOC-014). Một index lo cả UNIQUE + lookup.
- **`documents(department_id, type)`** — `idx_doc_dept_type` (composite): query liệt kê/lọc phổ biến nhất (FR-DOC-004) luôn kèm RBAC scope phòng (BR-DOC-004) + lọc loại. Đáp ứng NFR-PERF-DOC-002 (P95 < 500ms, không Sequential Scan).
- **`documents.security_level`** + **`status`**: lọc/RBAC mức bảo mật (BR-DOC-006) + lọc active/archived (FR-DOC-004). Tách 2 index đơn vì kết hợp với nhiều bộ lọc khác nhau.
- **`documents(title/code)` GIN trgm**: tìm kiếm gần đúng tiêu đề/mã (FR-DOC-004, NFR-PERF-DOC-002 gợi ý GIN trgm). Tái dùng `pg_trgm` đã bật ở M7.
- **`document_versions(document_id, status)`** — `idx_dv_doc_status`: query nóng nhất bảng version — lấy current (status='approved') + dựng danh sách version theo trạng thái (FR-DOC-005/009). Lọc theo quyền hiển thị version (BR-DOC-011).
- **`document_versions ... WHERE status='review'`** — `idx_dv_review` (partial): hàng đợi chờ duyệt (FR-DOC-009 "version chờ duyệt của tôi") — partial giữ index nhỏ vì review là tập rất nhỏ.
- **`uq_doc_one_approved (document_id) WHERE status='approved'`** (partial unique): vừa **enforce ≤1 current** (BR-DOC-008, D7) vừa phục vụ truy vấn "lấy bản approved của tài liệu" — index 2 trong 1.
- **`document_access_log(document_id, action, at)`** — `idx_dal_doc_action_at` (composite): thống kê R15 (FR-DOC-015) `COUNT GROUP BY document_id, action` lọc khoảng `at` — đúng cấu trúc query thống kê. Đáp ứng NFR-PERF-DOC-003 (thống kê 1 tháng < 3s, không Sequential Scan bảng 500K dòng).

> **Không over-index:** KHÔNG index `change_note`, `reject_reason`, `title` (đã có GIN trgm), `submitted_by`/`reviewed_by`/`approved_by` (lookup theo người duyệt hiếm; nếu báo cáo "ai duyệt nhiều" cần thì thêm sau). Quy mô ~5,000 tài liệu / ~20,000 version / ~500,000 access_log (NFR §698) → KHÔNG cần partition; đặt **retention/prune** cho `document_access_log` (NFR-DATA-DOC-001, giữ ~24 tháng — OQ vận hành). `idx_dal_user_at` là tùy chọn (giữ vì báo cáo theo người có thể cần — chi phí thấp ở quy mô này).

---

## 5. Seed — document_types (6 loại mặc định, D4 / OQ#2)

> **Thứ tự seed:** chỉ `document_types` (idempotent `ON CONFLICT DO NOTHING`). `roles_permissions` (document:*) ĐÃ seed ở M7 — M3 KHÔNG seed lại. `documents`/`document_versions` là dữ liệu nghiệp vụ runtime — không seed.

```sql
INSERT INTO document_types (code, label, sort_order) VALUES
    ('sop',      'Quy trình thao tác chuẩn (SOP)',     1),
    ('process',  'Quy trình / Thủ tục',                2),
    ('form',     'Biểu mẫu',                           3),
    ('guide',    'Hướng dẫn công việc',                4),
    ('standard', 'Tiêu chuẩn / Quy chuẩn',             5),
    ('other',    'Tài liệu khác',                      6)
ON CONFLICT (code) DO NOTHING;
```

> **Mã tài liệu (`documents.code`)** sinh **app-layer** theo định dạng `<LOAI>-<MAPHONG>-<số>` (vd `SOP-HPT-001` — loại SOP, phòng HPT, số thứ tự 001). KHÔNG seed DB; định dạng cấu hình (OQ#1). UNIQUE constraint `uq_doc_code` là lưới chống trùng (retry nếu race — FR-DOC-003 A1). Khuyến nghị bộ đếm theo (loại, phòng) ở app + UNIQUE làm lưới an toàn cuối.

---

## 6. Traceability — Map bảng/cột → FR/BR SRS M3

| Bảng / Cột | FR | BR |
|------------|----|----|
| `document_types` (toàn bộ) | FR-DOC-001, 004 | BR-DOC-002 |
| `documents` (toàn bộ) | FR-DOC-001, 002, 003, 004, 005 | BR-DOC-001, 002, 003, 004, 005, 014 |
| `documents.code` (UNIQUE, bất biến) | FR-DOC-003, 002 | BR-DOC-014 |
| `documents.type` (FK→document_types) | FR-DOC-001, 004 | BR-DOC-002 |
| `documents.department_id` (FK) | FR-DOC-001, 004 | BR-DOC-004 (scope) |
| `documents.security_level` (CHECK 2 mức) | FR-DOC-004, 005, 012 | BR-DOC-003, 006 |
| `documents.status` (active/archived) | FR-DOC-004 | — |
| `documents.current_version_id` (FK SET NULL, vòng FK) | FR-DOC-005, 011 | BR-DOC-008, NFR-INTEG-DOC-001 |
| `document_versions` (toàn bộ) | FR-DOC-006..013 | BR-DOC-001, 007, 008, 009, 012, 016, 017, 020, 021 |
| `document_versions.version_no` + `uq_dv_doc_version` | FR-DOC-006 | BR-DOC-001 |
| `document_versions.change_note` | FR-DOC-006, 007 | BR-DOC-016 |
| `document_versions.status` (CHECK) | FR-DOC-013, 008, 009, 010, 011 | BR-DOC-007 |
| `uq_doc_one_approved` (partial unique) | FR-DOC-011 | BR-DOC-008, NFR-INTEG-DOC-001 |
| `document_versions.created_by` (người soạn) | FR-DOC-006 | BR-DOC-009 |
| `document_versions.submitted_by/at` | FR-DOC-008 | BR-DOC-007 |
| `document_versions.reviewed_by/at` | FR-DOC-009, 010 | BR-DOC-010 |
| `document_versions.approved_by/at` (≠created_by app) | FR-DOC-009, 011 | BR-DOC-009, 010 |
| `ck_dv_approval_pair` / `ck_dv_review_pair` / `ck_dv_submit_pair` | FR-DOC-009 | BR-DOC-007 |
| `document_versions.reject_reason` | FR-DOC-010 | BR-DOC-020 |
| `document_versions.deleted_at` (soft-delete draft) | — | BR-DOC-021 |
| (immutable approved/obsolete — app, không route PUT/DELETE) | FR-DOC-007, 011 | BR-DOC-012, 021, CONSTRAINT-3 |
| `document_access_log` (toàn bộ) | FR-DOC-014, 015 | BR-DOC-015 |
| `document_access_log.action` (view/download/edit) | FR-DOC-014 | BR-DOC-015 |
| `idx_dal_doc_action_at` (thống kê) | FR-DOC-015 | BR-DOC-015 |
| FK `attachments` (owner_type='document_version', owner_id=version.id) | FR-DOC-006, 012 | BR-DOC-013, CONSTRAINT-8 |
| INSERT `audit_logs` (mọi thao tác) | tất cả FR | BR-DOC-019, CONSTRAINT-6, NFR-AUDIT-DOC-001 |
| INSERT `notifications` (gửi duyệt/approve/reject) | FR-DOC-008, 009, 010 | BR-DOC-018 |
| đọc `departments.lead_user_id` (cấp document:approve) | FR-DOC-009, 010 | BR-DOC-010, CONSTRAINT-11 |
| (lịch sử version = join document_versions + audit_logs) | FR-DOC-016 | BR-DOC-019 |

**Mapping điều khoản 17025:**
- **§8.3 Kiểm soát tài liệu:** phê duyệt trước ban hành (`status` state machine, `approved_by`); chỉ bản hiện hành được dùng (`current_version_id` + `uq_doc_one_approved`); ngăn dùng tài liệu lỗi thời (auto-obsolete FR-011 + status `obsolete`); nhận biết thay đổi (`change_note`, version_no, lịch sử FR-016).
- **§8.3.2 Tách trách nhiệm:** `approved_by ≠ created_by` (BR-DOC-009 app-layer).
- **§8.4 Kiểm soát hồ sơ:** immutable approved/obsolete (D6); KHÔNG hard-delete bản đã ban hành (BR-DOC-021); audit đầy đủ (`audit_logs`).

---

## 7. Ghi chú cho dev (BẮT BUỘC đọc) — transaction, row-lock, concurrency, immutable

### 7.1 Revision & thứ tự migration
- **File:** `1718870400005_m3_document_control.py`. `revision = "1718870400005"`, `down_revision = "1718870400004"` (M4 HR).
- **Thứ tự tổng thể:** M7 (`...001`) → M1 (`...002`) → M2 (`...003`) → M4 (`...004`) → **M3 (`...005`)**. M3 phụ thuộc users/departments/attachments/audit_logs/notifications (M7) — đã có.
- **Bỏ cột `created_at_audit`** khi viết migration (xem ghi chú §2) — `document_versions` chỉ dùng `created_at`/`updated_at`.

### 7.2 Approve version + auto-obsolete bản cũ (FR-DOC-009/011, BR-DOC-008) — CỐT LÕI
**NFR-CONCUR-DOC-001 + NFR-INTEG-DOC-001:** approve PHẢI atomic + row-lock trên `documents`.
```python
async with session.begin():
    doc = (await session.execute(
        select(Document).where(Document.id == document_id).with_for_update()
    )).scalar_one()                                  # row-lock document → tuần tự hóa approve cùng tài liệu

    version = (await session.execute(
        select(DocumentVersion).where(DocumentVersion.id == version_id).with_for_update()
    )).scalar_one()

    # 1. RBAC: user có document:approve trong phòng (departments.lead_user_id / leader / admin) — BR-DOC-010 → else 403 FORBIDDEN
    # 2. tách soạn–duyệt: user.id != version.created_by — BR-DOC-009 → else 403 SELF_APPROVAL_FORBIDDEN
    # 3. state: version.status == 'review' — BR-DOC-007 → else 422 INVALID_STATE_TRANSITION
    # 4. obsolete bản approved cũ (nếu có) — TRONG transaction
    old = (await session.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.status == 'approved')
    )).scalar_one_or_none()
    if old:
        old.status = 'obsolete'                      # audit DOCUMENT_VERSION_OBSOLETE
    # 5. approve version mới
    version.status = 'approved'
    version.reviewed_by = user.id; version.reviewed_at = now()
    version.approved_by = user.id; version.approved_at = now()
    doc.current_version_id = version.id              # current trỏ bản mới
    # 6. INSERT audit DOCUMENT_VERSION_APPROVE (+ STATE_CHANGE); notification cho created_by
```
- **`uq_doc_one_approved` (partial unique D7) là lưới an toàn cuối:** nếu logic obsolete lỗi/race → INSERT/UPDATE bản approved thứ 2 sẽ bị DB chặn (unique violation) → đảm bảo 0 trường hợp 2 current (NFR-INTEG-DOC-001). App vẫn phải obsolete chủ động + row-lock để tránh va chạm + trả lỗi đẹp.

### 7.3 State machine version (FR-DOC-013, BR-DOC-007)
- Hàm transition trung tâm: `change_version_status(version, to_status, trigger, user)` — kiểm `(from,to) ∈ WHITELIST` trước khi UPDATE + INSERT audit `DOCUMENT_VERSION_STATE_CHANGE`.
- **Whitelist:** `draft→review` (FR-008, cần ≥1 file — BR-017), `review→approved` (FR-009, ≠người soạn + có quyền), `review→draft` (FR-010, kèm reject_reason — BR-020), `approved→obsolete` (TỰ ĐỘNG khi approve bản mới — FR-011; KHÔNG thao tác obsolete thủ công). Ngoài whitelist → 422 `INVALID_STATE_TRANSITION` (vd `draft→approved`, `obsolete→*`, `approved→draft`).

### 7.4 Immutable approved/obsolete (D6, BR-DOC-012/021, CONSTRAINT-3) — KHÔNG trigger DB
- **KHÔNG có route PUT/PATCH/DELETE** trên version `approved`/`obsolete`. Sửa file/change_note version `review`/`approved`/`obsolete` → 422 `VERSION_LOCKED`. Chỉ version `draft` sửa được (FR-007).
- **Soft-delete:** chỉ version `draft` CHƯA từng gửi duyệt (submitted_at IS NULL) được set `deleted_at` + audit. Version đã từng approved/obsolete KHÔNG xóa (§8.4). Tài liệu có version approved KHÔNG hard-delete (chuyển `status='archived'`).
- Đồng bộ M1 (D7) / M4: immutable enforce **service-layer** (không trigger DB) để giữ schema đơn giản. Nếu QA/security yêu cầu defense-in-depth → cân nhắc trigger BEFORE UPDATE/DELETE sau (như `audit_logs` M7 D8).

### 7.5 File qua attachments (D10, BR-DOC-013, CONSTRAINT-8)
- Tạo/sửa version → upload file MinIO → INSERT `attachments(owner_type='document_version', owner_id=version.id, file_key, ...)`. App validate MIME thực + đuôi whitelist (PDF/DOCX/XLSX/PNG/JPG) + dung lượng (BR-DOC-013) trước khi lưu. 1 file chính/version (bản đầu).
- `attachments.owner_type` whitelist `'document'`/`'document_version'` ĐÃ có ở M7 → **M3 KHÔNG ALTER attachments**.
- Tải file (FR-DOC-012): kiểm quyền (mức bảo mật BR-006 + trạng thái version BR-011) → presigned URL MinIO → ghi `document_access_log` action='download' + audit `DOCUMENT_DOWNLOAD`.

### 7.6 access_log best-effort (D11, BR-DOC-015, NFR-DATA-DOC-001)
- Ghi mỗi view (mở chi tiết FR-005)/download (FR-012)/edit (tạo/sửa version FR-006/007). Lượt bị 403 KHÔNG ghi (đếm chỉ hợp lệ). Ghi best-effort: lỗi ghi access_log → KHÔNG rollback nghiệp vụ, log WARN. Cho phép async/fire-and-forget.
- Thống kê (FR-015): `COUNT(*) FILTER (WHERE action=...) GROUP BY document_id` lọc khoảng `at` → dùng `idx_dal_doc_action_at`. Cân nhắc materialized view nếu dataset lớn (NFR-PERF-DOC-003).

### 7.7 RBAC (BR-DOC-004/005/006/010/011) — app-layer (đọc M7)
- **Kế toán:** mọi endpoint ghi M3 → 403 (tầng API); chỉ xem version approved/current (BR-DOC-005).
- **Staff:** tạo/sửa tài liệu+version chỉ phòng mình (scope `department`); duyệt CHỈ khi là `departments.lead_user_id` của phòng đó (BR-DOC-010). Staff thường duyệt → 403.
- **Mức bảo mật:** `restricted` chỉ phòng sở hữu + admin/leader xem/tải; `internal` mọi nhân sự (BR-DOC-006). Ẩn khỏi danh sách + 403 khi truy cập trực tiếp.
- **Hiển thị version (BR-DOC-011):** `approved`/`obsolete` cho mọi người có quyền xem; `draft`/`review` chỉ người soạn + người duyệt phòng đó + admin/leader.

### 7.8 Quy ước chung (đồng bộ M7/M1/M2/M4)
- Mọi thao tác ghi kèm `correlation_id` vào `audit_logs` (NFR-AUDIT-DOC-001, NFR-OBS-DOC-001).
- KHÔNG expose endpoint chuyển trạng thái tùy ý; trạng thái là hệ quả của API nghiệp vụ (FR-013).
- Thông báo idempotent qua `idx_notif_ref` (M7) chống trùng (BR-DOC-018).

---

## 8. Điểm cần Tech Lead chú ý (review trước APPROVED)

1. **Vòng FK `documents ↔ document_versions` (D3):** giải y hệt M7 (`users ↔ departments`) — tạo `documents` (current_version_id chưa FK) → `document_versions` → ALTER ADD `fk_doc_current` (SET NULL). **Hệ quả rollback:** drop `document_versions` cần CASCADE hoặc drop FK `fk_doc_current` trước. Đã ghi §9.
2. **Partial unique `uq_doc_one_approved` (D7) — enforce DB-level ≤1 approved/tài liệu:** đây là điểm KHÁC M1 (M1 dùng app-layer cho hầu hết bất biến). Chọn DB-level cho bất biến VILAS §8.3 quan trọng nhất (BR-DOC-008) vì là lưới an toàn cuối chống race (NFR-INTEG-DOC-001 "0 tài liệu có >1 approved tại MỌI thời điểm"). **Cần Tech Lead xác nhận** chấp nhận DB-level enforce này (đồng bộ tinh thần partial unique `is_current` của M1 `sample_results`).
3. **Loại tài liệu = bảng danh mục `document_types` (D4) thay CHECK:** chọn bảng danh mục (cấu hình được qua `is_active`) đồng bộ M4 D5. `security_level` ngược lại dùng CHECK (2 mức cố định, D5). **Cần Tech Lead xác nhận** lựa chọn này (vs CHECK cho cả hai). Lý do tách: loại tài liệu KH có thể thêm (OQ#2 mở), mức bảo mật đã chốt cứng 2 mức.
4. **Immutable + state machine + tách soạn–duyệt enforce APP-LAYER (D6/D8/D9):** DB chỉ CHECK giá trị + partial unique. Đồng bộ M1/M4. Nếu QA/security yêu cầu defense-in-depth DB-level (trigger chặn UPDATE version approved) → cân nhắc thêm sau (chưa thêm để giữ schema đơn giản).
5. **Cột `created_at_audit` trong DDL §2 — BỎ:** lọt vào do soạn thảo, KHÔNG thuộc thiết kế. Dev bỏ khi viết migration; `document_versions` chỉ dùng `created_at`/`updated_at`. (Ghi rõ để tránh nhầm.)
6. **`roles_permissions` (document:*) đã seed M7 — M3 KHÔNG seed lại.** M3 chỉ seed `document_types`. Quyền `document:approve` cho staff = chỉ khi là trưởng nhóm (app check `departments.lead_user_id`) — đọc M7, KHÔNG tạo cột mới.
7. **`attachments.owner_type` whitelist đã có `'document'`/`'document_version'` (M7) — M3 KHÔNG ALTER.** Đã verify trong migration `1718870400001` (dòng 161).
8. **OPEN QUESTIONS ảnh hưởng schema:** #2 (danh mục loại) → đã giải bằng bảng cấu hình (thêm loại không đổi schema); #3 (mức bảo mật) → đã chốt 2 mức (CHECK); #5 (1 bước duyệt) → đã chốt 1 bước (state machine 4 trạng thái, KHÔNG cần bảng workflow); #6 (người soạn=trưởng nhóm) → KHÔNG cần thêm bảng, RBAC app enforce (người soạn=lead → leader/admin cấp trên duyệt). Mọi thay đổi default sau cần văn bản KH ("Verbal is Nothing").

---

## 9. Migration & Rollback

```
-- [ MIGRATION FILE NAME ] (Alembic)
-- 1718870400005_m3_document_control.py
--   revision = "1718870400005" ; down_revision = "1718870400004" (M4)
-- Thứ tự CREATE: document_types → documents (current_version_id chưa FK)
--              → document_versions → ALTER documents ADD fk_doc_current
--              → uq_doc_one_approved (partial unique) → document_access_log
--              → indexes → seed document_types

-- [ THỨ TỰ MIGRATION TỔNG THỂ ]
--   M7 (...001) → M1 (...002) → M2 (...003) → M4 (...004) → M3 (...005)
--   M3 phụ thuộc users/departments/attachments/audit_logs/notifications (M7).
--   M3 KHÔNG bị module nào phụ thuộc ngược (M6 chỉ đọc document_access_log runtime).

-- [ ROLLBACK PLAN ] (downgrade) — drop ngược thứ tự FK:
--   Phải drop FK vòng trước (fk_doc_current) HOẶC dùng CASCADE.
ALTER TABLE documents DROP CONSTRAINT IF EXISTS fk_doc_current;
DROP TABLE IF EXISTS document_access_log CASCADE;
DROP TABLE IF EXISTS document_versions   CASCADE;   -- uq_doc_one_approved drop theo bảng
DROP TABLE IF EXISTS documents           CASCADE;
DROP TABLE IF EXISTS document_types      CASCADE;
-- KHÔNG drop extension pgcrypto/pg_trgm (dùng chung M7).
-- KHÔNG drop/đụng users/departments/attachments/audit_logs/notifications/roles_permissions (M7).

-- [ EXISTING TABLE CHANGES ]
-- M3 KHÔNG ALTER bảng M7. attachments.owner_type whitelist ('document','document_version')
--   ĐÃ có sẵn ở M7 (1718870400001 dòng 161) → KHÔNG breaking change.
-- roles_permissions (document:create/read/approve) ĐÃ seed ở M7 → KHÔNG thêm.

-- [ DATA DEPENDENCIES ]
-- Seed TRƯỚC (trong migration M3): document_types (6 loại).
-- Phụ thuộc bảng có sẵn (M7): users, departments(+lead_user_id), attachments,
--   audit_logs, notifications, roles_permissions(document:*).
-- Bảng phụ thuộc vào M3 (đọc runtime, KHÔNG FK): M6 báo cáo tổng hợp document_access_log.
```

---

*Hết Contract M3 Schema v1.0. Tuân thủ: PK UUID gen_random_uuid (danh mục natural-key code), TIMESTAMPTZ, CHECK thay native ENUM, FK rõ ON DELETE, vòng FK giải bằng nullable+ALTER (như M7), partial unique ≤1 approved (BR-DOC-008 DB-level), UNIQUE(document_id, version_no), immutable approved/obsolete + state machine + tách soạn–duyệt app-layer (như M1/M4), index mọi FK + query pattern + GIN trgm tìm kiếm + composite thống kê R15, rollback + thứ tự migration đầy đủ, traceability FR/BR. Đồng bộ tuyệt đối quy ước M7/M1/M2/M4. Chờ `/contract` gate APPROVED trước khi feature-builder implement.*
