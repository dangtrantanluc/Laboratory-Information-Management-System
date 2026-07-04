# Contract — M1 Schema: Quản lý Mẫu & Yêu cầu thử nghiệm (Sample Lifecycle)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M1 — Sample Lifecycle
**Tài liệu:** Database Schema Contract (DDL + Index + Seed + Traceability)
**Version:** 1.0 | **Ngày:** 19/06/2026 | **Author:** schema-designer agent
**Stack:** PostgreSQL 15+, FastAPI + SQLAlchemy/Alembic
**Nguồn chân lý:** `05-srs-m1-sample.md` (SRS v1.1 — 19 FR, 23 BR, state machine, NFR, §ghi chú schema-designer dòng 987-998), `03-contract-m2-schema.md` (quy ước đồng bộ), `01-demo-scope.md` (ERD core, RBAC, CRON-1/2)
**Status:** DRAFT — chờ `/contract` gate / Tech Lead review

---

## 0. Quyết định thiết kế chính (đọc trước) — đồng bộ tuyệt đối với M2

| # | Quyết định | Lý do |
|---|-----------|-------|
| D1 | **PK = UUID `DEFAULT gen_random_uuid()`** cho mọi bảng nghiệp vụ M1 (`test_requests`, `samples`, `sample_assignments`, `sample_results`, `sample_handovers`, `overdue_reasons`). | CONSTRAINT-5 (không lộ ID tuần tự) + đồng bộ M2 (D1). `samples.id` UUID khớp FK mềm `chemical_transactions.ref_sample_id → samples(id)` của M2 (M2 §1, dòng 99/136/276). |
| D2 | **ENUM = CHECK constraint trên VARCHAR**, KHÔNG dùng native PG ENUM. | Đồng bộ M2 (D5): ENUM native khó migrate (ALTER TYPE không rollback gọn trong Alembic). Áp cho `samples.status`, `samples.condition_status`, `sample_assignments.status`, owner_type của attachments (M7). |
| D3 | **Thời gian = `TIMESTAMPTZ`** mọi nơi; **`deadline_at`/`received_at` NOT NULL** (BR-SAMPLE-002). `completed_at` NULL cho tới khi trưởng nhóm chốt done. | Đồng bộ M2; on-time rate so `completed_at` vs `deadline_at` (BR-SAMPLE-019). |
| D4 | **`samples.department_id` + `samples.received_by` DENORMALIZE từ phiếu** (`test_requests`) khi thêm mẫu. | SRS §989: query RBAC theo phòng + cách ly Kế toán (BR-SAMPLE-014) chạy trực tiếp trên `samples` không phải join phiếu mỗi lần → nhanh + index gọn. App phải giữ đồng bộ với phiếu khi tạo mẫu. |
| D5 | **`samples.current_custodian_id` DENORMALIZE** người giữ hiện tại (suy từ handover gần nhất; khởi tạo = `received_by`). | SRS §371/§989 cho phép. Chain of custody **nguồn chân lý vẫn là `sample_handovers`** (bất biến); cột này chỉ để truy vấn nhanh "ai đang giữ" (FR-006 validate người giữ, FR-007 hiển thị). Cập nhật trong cùng transaction với INSERT handover. |
| D6 | **Versioning kết quả approved** bằng nhiều dòng trong `sample_results` + `(assignment_id, version)` UNIQUE + cờ `is_current`. KHÔNG bảng lịch sử riêng. | SRS §991, BR-SAMPLE-010/CONSTRAINT-3. Sửa kết quả approved = INSERT version+1 (giữ bản cũ nguyên vẹn). Partial unique đảm bảo mỗi assignment chỉ 1 dòng `is_current`. |
| D7 | **Soft-delete `samples`** bằng `deleted_at TIMESTAMPTZ NULL` (không hard-delete). `sample_results`, `sample_handovers`, `overdue_reasons` **KHÔNG soft-delete, KHÔNG hard-delete** (immutable — hồ sơ pháp lý §7.4/§7.5/§8.4). | BR-SAMPLE-016/017, CONSTRAINT-2/3, NFR-AUDIT-SAMPLE-001. `samples` chỉ soft-delete khi KHÔNG bị M2 `ref_sample_id` tham chiếu & chưa có kết quả approved. |
| D8 | **`approved_by ≠ entered_by` (tách nhập-duyệt) enforce APP-LAYER**, không CHECK DB (vì là 2 cột FK so sánh + nghiệp vụ RBAC). | BR-SAMPLE-011. Đồng bộ phong cách M2 (enforce nghiệp vụ phức ở app, CHECK DB cho ràng buộc giá trị). Trả 403 `SELF_APPROVAL_FORBIDDEN`. |
| D9 | **State transition enforce APP-LAYER** (whitelist + row-lock), DB chỉ CHECK `status ∈ tập hợp lệ`. | SRS FR-017/§997: whitelist (from,to) là logic, không biểu diễn bằng CHECK đơn cột. CHECK DB là lưới an toàn cuối chống giá trị rác. |
| D10 | **Audit ghi vào bảng dùng chung `audit_logs`** (M7) — M1 KHÔNG tạo bảng audit riêng. File lưu qua `attachments` polymorphic (M7/chung) — M1 KHÔNG tạo bảng file riêng. | CONSTRAINT-4, BR-SAMPLE-013; đồng bộ M2 (D9). |
| D11 | **Trưởng nhóm = `departments.lead_user_id` (M7)** — M1 CHỈ NÊU dependency, KHÔNG tạo/sửa bảng `departments` trong migration M1. | OQ#11/BR-SAMPLE-022/CONSTRAINT-9. Chọn `departments.lead_user_id` (đúng 1 trưởng nhóm/phòng) thay vì cờ `users.is_dept_lead` — gợi ý SRS §994. M7 phải sẵn sàng trước khi M1 implement RBAC duyệt/phân công/chốt. |

> **Audit fields (rule global):** mọi bảng nghiệp vụ M1 có `created_at`. Bảng có vòng đời cập nhật (`test_requests`, `samples`, `sample_assignments`) thêm `updated_at` + `created_by`/`updated_by UUID REFERENCES users(id)`. Bảng IMMUTABLE (`sample_results`, `sample_handovers`, `overdue_reasons`) dùng cột người-thực-hiện riêng (`entered_by`/`from_user`/`by_user`) thay cặp created/updated vì không có "update" — đồng bộ cách M2 xử lý `chemical_transactions` (M2 §28).

---

## 1. ERD chi tiết M1 (ASCII)

```
┌─────────────────────────────────────────────────────────────────────┐
│ BẢNG DÙNG CHUNG (M7 / chung — KHÔNG tạo lại trong migration M1)       │
├─────────────────────────────────────────────────────────────────────┤
│ users(id UUID PK, ...)                  ← FK người dùng mọi nơi       │
│ departments(id UUID PK, lead_user_id FK→users NULL, ...)  ← OQ#11     │
│ customers(id UUID PK, name, contact, type, ...)  ← khách gửi mẫu      │
│ attachments(id UUID PK, owner_type, owner_id, file_key, ...)          │
│   owner_type ∈ {'test_request','sample','sample_result'} cho M1       │
│ audit_logs(id, user_id, action, resource, resource_id,               │
│            correlation_id, ip, at, detail JSONB)  ← INSERT mọi thao tác│
│ notifications(id, user_id, type, title, body, ref_type, ref_id, ...)  │
└─────────────────────────────────────────────────────────────────────┘

        ┌───────────────────────────────────────────────────────┐
        │  test_requests   (PHIẾU YÊU CẦU — vùng chứa 1..n mẫu)  │
        │  id            UUID PK                                 │
        │  request_code  VARCHAR(32) UNIQUE NOT NULL  (RQ-YYYY-) │
        │  customer_id   UUID FK→customers(RESTRICT) NULL        │
        │  sender_name   VARCHAR(255) NULL                       │
        │  department_id UUID FK→departments(RESTRICT) NOT NULL  │
        │  received_by   UUID FK→users(RESTRICT) NOT NULL        │
        │  received_at   TIMESTAMPTZ NOT NULL DEFAULT now()      │
        │  note          TEXT NULL                               │
        │  deleted_at    TIMESTAMPTZ NULL  (soft-delete)         │
        │  created_by/updated_by/created_at/updated_at           │
        └───────────┬───────────────────────────────────────────┘
                    │ 1
                    │  (BR-SAMPLE-023: phiếu phải có ≥1 mẫu để hoàn tất)
                    │ N
        ┌───────────▼───────────────────────────────────────────┐
        │  samples   (MẪU — vòng đời độc lập từng mẫu)           │
        │  id              UUID PK   ◄── M2.chemical_transactions│
        │  sample_code     VARCHAR(32) UNIQUE NOT NULL (SP-YYYY-)│       .ref_sample_id
        │  request_id      UUID FK→test_requests(RESTRICT) NOT NULL
        │  department_id   UUID FK→departments(RESTRICT) NOT NULL (denorm D4)
        │  received_by     UUID FK→users(RESTRICT) NOT NULL (denorm D4)
        │  current_custodian_id UUID FK→users(RESTRICT) NOT NULL (denorm D5)
        │  received_at     TIMESTAMPTZ NOT NULL                  │
        │  deadline_at     TIMESTAMPTZ NOT NULL                  │
        │  completed_at    TIMESTAMPTZ NULL (set khi chốt done)  │
        │  status          VARCHAR(10) CHECK                     │
        │     (received|assigned|testing|done|overdue|returned)  │
        │  condition_status VARCHAR(16) NULL CHECK               │
        │     (acceptable|not_acceptable)                        │
        │  condition_note  TEXT NULL                             │
        │  deleted_at      TIMESTAMPTZ NULL (soft-delete D7)     │
        │  created_by/updated_by/created_at/updated_at           │
        │  CHECK(deadline_at > received_at)                      │
        │  CHECK(condition_status<>'not_acceptable' OR condition_note NOT NULL)
        └───┬───────────────┬──────────────────┬────────────────┘
            │ 1             │ 1                │ 1
            │ N             │ N                │ N
   ┌────────▼──────┐ ┌──────▼───────────┐ ┌──▼───────────────────┐
   │sample_handovers│ │sample_assignments│ │ overdue_reasons       │
   │(IMMUTABLE §7.4)│ │  id UUID PK       │ │  id UUID PK           │
   │ id UUID PK     │ │  sample_id FK     │ │  sample_id FK(RESTRICT)│
   │ sample_id FK   │ │  assigned_to FK   │ │  reason TEXT NOT NULL  │
   │ from_user FK   │ │  assigned_by FK   │ │  by_user FK→users      │
   │ to_user FK     │ │  part_name VARCHAR│ │  at TIMESTAMPTZ        │
   │ reason TEXT    │ │  status VARCHAR CK │ └───────────────────────┘
   │ at TIMESTAMPTZ │ │   (assigned|in_   │
   └────────────────┘ │   progress|result_│
                      │   entered|approved)│
                      │  assigned_at      │
                      │  created_by/upd... │
                      └──────┬─────────────┘
                             │ 1
                             │ N
                ┌────────────▼──────────────────────────────┐
                │ sample_results  (versioning — D6)          │
                │  id            UUID PK                      │
                │  assignment_id UUID FK→sample_assignments  │
                │  version       INT NOT NULL DEFAULT 1       │
                │  result_data   JSONB NOT NULL              │
                │  entered_by    UUID FK→users(RESTRICT)     │
                │  entered_at    TIMESTAMPTZ NOT NULL        │
                │  approved_by   UUID FK→users(RESTRICT) NULL│
                │  approved_at   TIMESTAMPTZ NULL            │
                │  is_current    BOOLEAN NOT NULL DEFAULT true│
                │  revision_reason TEXT NULL (NOT NULL khi version>1)
                │  created_at    TIMESTAMPTZ                 │
                │  UNIQUE(assignment_id, version)            │
                │  partial UNIQUE(assignment_id) WHERE is_current
                │  CHECK(approved_at NOT NULL ⇔ approved_by NOT NULL)
                │  CHECK(version=1 OR revision_reason NOT NULL)
                └────────────────────────────────────────────┘
```

### Quan hệ ngược từ M2 (chỉ đọc — KHÔNG tạo trong M1)

```
chemical_transactions.ref_sample_id  ──(FK RESTRICT)──►  samples.id
   - M2 §276: type='out' ⇒ ref_sample_id NOT NULL (BR-CHEM-025)
   - Hệ quả M1: KHÔNG hard-delete samples đang bị tham chiếu (BR-SAMPLE-016).
     → M1 dùng soft-delete (deleted_at). FK RESTRICT của M2 là lưới an toàn cuối.
```

### Bảng dùng chung tham chiếu (KHÔNG tạo lại — sở hữu bởi M7 / chung)

| Bảng | Sở hữu | M1 dùng để |
|------|--------|-----------|
| `users(id UUID PK, ...)` | M7 | FK `received_by`, `created_by`, `updated_by`, `current_custodian_id`, `assigned_to/by`, `entered_by`, `approved_by`, `from_user/to_user`, `by_user` |
| `departments(id UUID PK, lead_user_id FK→users NULL, ...)` | M7 | FK `test_requests.department_id`, `samples.department_id` (RBAC scope); đọc `lead_user_id` để enforce BR-SAMPLE-022 |
| `customers(id UUID PK, ...)` | M1 (ERD core)/chung | FK `test_requests.customer_id` (khách gửi mẫu) |
| `attachments(id, owner_type, owner_id, file_key, ...)` | dùng chung | ảnh mẫu/chứng từ (`owner_type='sample'`/`'test_request'`), raw data + phiếu PDF (`owner_type='sample_result'`/`'sample'`) — FR-003/009/016 |
| `audit_logs(...)` | M7 | INSERT mọi thao tác M1 (BR-SAMPLE-013) |
| `notifications(...)` | M7 | INSERT CRON-1/CRON-2 + thông báo phân công/handover (FR-005/006/013/014) |

> **Ghi chú `customers`:** ERD core (`01-demo-scope.md` dòng 174) liệt kê `customers` trong khối M1. Nếu owner thực tế là M7/danh mục chung và đã có migration riêng → M1 chỉ FK tới, KHÔNG tạo lại. Contract này **giả định `customers` đã tồn tại** (tạo ở migration danh mục/M7); nếu chưa, thêm CREATE TABLE customers tối thiểu vào migration M1 đầu (xem §8 điểm 5). `customer_id` để NULL được (khách vãng lai chỉ ghi `sender_name`).

---

## 2. DDL đầy đủ

> Migration viết SQL thuần để dev chuyển sang Alembic. **Prereq:** `pgcrypto` (gen_random_uuid) — bật ở migration M7/khởi tạo chung; nếu chưa có, bật ở migration M1 đầu. Các bảng `users`, `departments`, `customers`, `attachments`, `audit_logs`, `notifications` PHẢI tồn tại trước (M7 chạy trước M1 — xem §9 thứ tự).

```sql
-- ============================================================
-- SCHEMA: m1-sample-lifecycle
-- Feature: Quản lý Mẫu & Yêu cầu thử nghiệm (LIMS 17025)
-- Designer: schema-designer agent | Date: 2026-06-19
-- Prereq: pgcrypto; bảng users/departments/customers/attachments/
--         audit_logs/notifications (M7/chung) đã tồn tại.
-- Thứ tự CREATE: test_requests → samples → sample_assignments
--              → sample_results → sample_handovers → overdue_reasons
--              → indexes
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

-- ------------------------------------------------------------
-- [ NEW TABLE ] test_requests — phiếu yêu cầu thử nghiệm (FR-SAMPLE-018, OQ#1)
--   Vùng chứa 1..n samples (BR-SAMPLE-023).
-- ------------------------------------------------------------
CREATE TABLE test_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_code    VARCHAR(32)  NOT NULL,                    -- 'RQ-YYYY-NNNN' (FR-018, BR-015) không lộ tuần tự
    customer_id     UUID         NULL,                        -- khách gửi mẫu (NULL = khách vãng lai)
    sender_name     VARCHAR(255) NULL,                        -- người mang mẫu tới
    department_id   UUID         NOT NULL,                    -- phòng tiếp nhận (RBAC scope, BR-014)
    received_by     UUID         NOT NULL,                    -- người tiếp nhận = custodian ban đầu (ASSUMPTION-4)
    received_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    note            TEXT         NULL,
    deleted_at      TIMESTAMPTZ  NULL,                        -- soft-delete (D7)
    created_by      UUID         NOT NULL,
    updated_by      UUID         NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_req_code        UNIQUE (request_code),
    CONSTRAINT fk_req_customer    FOREIGN KEY (customer_id)   REFERENCES customers(id)    ON DELETE RESTRICT,
    CONSTRAINT fk_req_dept        FOREIGN KEY (department_id) REFERENCES departments(id)  ON DELETE RESTRICT,
    CONSTRAINT fk_req_received_by FOREIGN KEY (received_by)   REFERENCES users(id)        ON DELETE RESTRICT,
    CONSTRAINT fk_req_created     FOREIGN KEY (created_by)    REFERENCES users(id)        ON DELETE RESTRICT,
    CONSTRAINT fk_req_updated     FOREIGN KEY (updated_by)    REFERENCES users(id)        ON DELETE RESTRICT
);
COMMENT ON TABLE test_requests IS 'Phiếu yêu cầu thử nghiệm (FR-SAMPLE-018, OQ#1). Vùng chứa 1..n samples.';

-- ------------------------------------------------------------
-- [ NEW TABLE ] samples — mẫu (FR-SAMPLE-001..004, 012, 017, 019)
--   Được M2.chemical_transactions.ref_sample_id tham chiếu (id phải UUID).
-- ------------------------------------------------------------
CREATE TABLE samples (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sample_code          VARCHAR(32)  NOT NULL,               -- 'SP-YYYY-NNNN' (FR-002, BR-015)
    request_id           UUID         NOT NULL,               -- OQ#1 quan hệ 1-n (BR-023)
    department_id        UUID         NOT NULL,               -- denorm từ phiếu (D4, RBAC scope)
    received_by          UUID         NOT NULL,               -- denorm từ phiếu (D4)
    current_custodian_id UUID         NOT NULL,               -- người giữ hiện tại (denorm D5; init = received_by)
    received_at          TIMESTAMPTZ  NOT NULL,               -- denorm từ phiếu (để CHECK deadline)
    deadline_at          TIMESTAMPTZ  NOT NULL,               -- TAT riêng từng mẫu (BR-002)
    completed_at         TIMESTAMPTZ  NULL,                   -- set khi trưởng nhóm chốt done (FR-019, on-time)
    status               VARCHAR(10)  NOT NULL DEFAULT 'received'
        CHECK (status IN ('received','assigned','testing','done','overdue','returned')), -- FR-017, BR-001
    condition_status     VARCHAR(16)  NULL
        CHECK (condition_status IS NULL OR condition_status IN ('acceptable','not_acceptable')), -- FR-004
    condition_note       TEXT         NULL,
    deleted_at           TIMESTAMPTZ  NULL,                   -- soft-delete (D7, BR-016)
    created_by           UUID         NOT NULL,
    updated_by           UUID         NULL,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_sample_code      UNIQUE (sample_code),
    CONSTRAINT fk_smp_request      FOREIGN KEY (request_id)           REFERENCES test_requests(id) ON DELETE RESTRICT,
    CONSTRAINT fk_smp_dept         FOREIGN KEY (department_id)        REFERENCES departments(id)   ON DELETE RESTRICT,
    CONSTRAINT fk_smp_received_by  FOREIGN KEY (received_by)          REFERENCES users(id)         ON DELETE RESTRICT,
    CONSTRAINT fk_smp_custodian    FOREIGN KEY (current_custodian_id) REFERENCES users(id)         ON DELETE RESTRICT,
    CONSTRAINT fk_smp_created      FOREIGN KEY (created_by)           REFERENCES users(id)         ON DELETE RESTRICT,
    CONSTRAINT fk_smp_updated      FOREIGN KEY (updated_by)           REFERENCES users(id)         ON DELETE RESTRICT,
    -- deadline phải sau ngày nhận (BR-002)
    CONSTRAINT ck_smp_deadline     CHECK (deadline_at > received_at),
    -- 'không đạt' phải có lý do (BR-003)
    CONSTRAINT ck_smp_condition    CHECK (
        condition_status IS DISTINCT FROM 'not_acceptable'
        OR (condition_note IS NOT NULL AND length(btrim(condition_note)) > 0)
    )
);
COMMENT ON TABLE  samples IS 'Mẫu thử nghiệm (FR-SAMPLE-001..). status enforce qua state machine app-layer (FR-017); CHECK DB là lưới an toàn giá trị.';
COMMENT ON COLUMN samples.current_custodian_id IS 'Denormalized người giữ hiện tại (D5). Nguồn chân lý = sample_handovers (bất biến).';
COMMENT ON COLUMN samples.completed_at IS 'Set khi trưởng nhóm CHỐT done (FR-019). on-time rate: completed_at <= deadline_at (BR-019).';

-- ------------------------------------------------------------
-- [ NEW TABLE ] sample_assignments — phân công phần việc (FR-SAMPLE-005)
-- ------------------------------------------------------------
CREATE TABLE sample_assignments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sample_id       UUID         NOT NULL,
    assigned_to     UUID         NOT NULL,                    -- KTV (cùng phòng — enforce app BR-004)
    assigned_by     UUID         NOT NULL,                    -- trưởng nhóm/Admin/Lãnh đạo (BR-022)
    part_name       VARCHAR(255) NOT NULL,                    -- chỉ tiêu/hạng mục
    status          VARCHAR(16)  NOT NULL DEFAULT 'assigned'
        CHECK (status IN ('assigned','in_progress','result_entered','approved')),
    assigned_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    created_by      UUID         NOT NULL,
    updated_by      UUID         NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_asg_sample      FOREIGN KEY (sample_id)   REFERENCES samples(id) ON DELETE RESTRICT,
    CONSTRAINT fk_asg_assigned_to FOREIGN KEY (assigned_to) REFERENCES users(id)   ON DELETE RESTRICT,
    CONSTRAINT fk_asg_assigned_by FOREIGN KEY (assigned_by) REFERENCES users(id)   ON DELETE RESTRICT,
    CONSTRAINT fk_asg_created     FOREIGN KEY (created_by)  REFERENCES users(id)   ON DELETE RESTRICT,
    CONSTRAINT fk_asg_updated     FOREIGN KEY (updated_by)  REFERENCES users(id)   ON DELETE RESTRICT
    -- KHÔNG unique cứng (sample_id, part_name): OQ#7 cho phép 1 part giao nhiều người (đối chứng).
);
COMMENT ON TABLE sample_assignments IS 'Phân công phần việc cho KTV (FR-SAMPLE-005). assigned_to cùng phòng mẫu (app BR-004); assigned_by có quyền sample:assign (BR-022).';

-- ------------------------------------------------------------
-- [ NEW TABLE ] sample_results — kết quả phần việc + versioning (FR-SAMPLE-008/010)
--   IMMUTABLE sau approved: sửa = INSERT version+1 (D6, BR-010, CONSTRAINT-3).
--   KHÔNG có route PUT/PATCH/DELETE trên dòng đã approved.
-- ------------------------------------------------------------
CREATE TABLE sample_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id   UUID         NOT NULL,
    version         INT          NOT NULL DEFAULT 1
        CHECK (version >= 1),
    result_data     JSONB        NOT NULL,                    -- cấu trúc linh hoạt theo chỉ tiêu (FR-008)
    entered_by      UUID         NOT NULL,                    -- người nhập (BR-008)
    entered_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    approved_by     UUID         NULL,                        -- người duyệt ≠ entered_by (app BR-011)
    approved_at     TIMESTAMPTZ  NULL,
    is_current      BOOLEAN      NOT NULL DEFAULT true,       -- version hiện hành (D6)
    revision_reason TEXT         NULL,                        -- bắt buộc khi version>1 (BR-010)
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_res_assignment FOREIGN KEY (assignment_id) REFERENCES sample_assignments(id) ON DELETE RESTRICT,
    CONSTRAINT fk_res_entered_by FOREIGN KEY (entered_by)    REFERENCES users(id)              ON DELETE RESTRICT,
    CONSTRAINT fk_res_approved_by FOREIGN KEY (approved_by)  REFERENCES users(id)              ON DELETE RESTRICT,
    -- mỗi assignment chỉ 1 dòng cho mỗi version
    CONSTRAINT uq_res_assignment_version UNIQUE (assignment_id, version),
    -- approved_by & approved_at đồng thời NULL hoặc đồng thời NOT NULL
    CONSTRAINT ck_res_approval_pair CHECK (
        (approved_by IS NULL AND approved_at IS NULL)
        OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
    ),
    -- version sửa đổi phải có lý do (BR-010, REVISION_REASON_REQUIRED)
    CONSTRAINT ck_res_revision_reason CHECK (
        version = 1
        OR (revision_reason IS NOT NULL AND length(btrim(revision_reason)) > 0)
    )
);
-- mỗi assignment chỉ 1 dòng is_current (partial unique — đảm bảo "version hiện hành" duy nhất)
CREATE UNIQUE INDEX uq_res_assignment_current
    ON sample_results(assignment_id) WHERE is_current;
COMMENT ON TABLE sample_results IS 'Kết quả phần việc (FR-008/010). approved bất biến; sửa = version+1 giữ bản cũ (D6, BR-010). Phạm vi đọc OQ#3: approved_by IS NULL chỉ entered_by+trưởng nhóm+Admin/Lãnh đạo; approved_by NOT NULL công khai nội bộ (BR-021, enforce app-layer query).';

-- ------------------------------------------------------------
-- [ NEW TABLE ] sample_handovers — chuỗi hành trình mẫu (FR-SAMPLE-006/007)
--   IMMUTABLE (17025 §7.4, BR-017): KHÔNG route PUT/DELETE. Nhầm → ghi handover mới đính chính.
-- ------------------------------------------------------------
CREATE TABLE sample_handovers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sample_id   UUID         NOT NULL,
    from_user   UUID         NOT NULL,                        -- người giữ trước (custodian hiện tại lúc chuyển)
    to_user     UUID         NOT NULL,                        -- người nhận (cùng phòng — app)
    reason      TEXT         NULL,                            -- lý do chuyển
    at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_ho_sample    FOREIGN KEY (sample_id) REFERENCES samples(id) ON DELETE RESTRICT,
    CONSTRAINT fk_ho_from_user FOREIGN KEY (from_user) REFERENCES users(id)   ON DELETE RESTRICT,
    CONSTRAINT fk_ho_to_user   FOREIGN KEY (to_user)   REFERENCES users(id)   ON DELETE RESTRICT,
    -- chuyển cho chính người đang giữ là vô nghĩa (FR-006 A3, INVALID_HANDOVER)
    CONSTRAINT ck_ho_diff_user CHECK (from_user <> to_user)
);
COMMENT ON TABLE sample_handovers IS 'Chain of custody bất biến (17025 §7.4, BR-017). Người giữ hiện tại = to_user của bản ghi at lớn nhất; đoạn đầu = received_by (ASSUMPTION-4).';

-- ------------------------------------------------------------
-- [ NEW TABLE ] overdue_reasons — lý do trễ hạn (FR-SAMPLE-014, R9)
--   reason NOT NULL bắt buộc (BR-009). Bất biến (hồ sơ §8.4).
-- ------------------------------------------------------------
CREATE TABLE overdue_reasons (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sample_id   UUID         NOT NULL,
    reason      TEXT         NOT NULL                         -- BR-009 bắt buộc
        CHECK (length(btrim(reason)) > 0),                    -- không cho chuỗi rỗng/space
    by_user     UUID         NOT NULL,
    at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_ovr_sample  FOREIGN KEY (sample_id) REFERENCES samples(id) ON DELETE RESTRICT,
    CONSTRAINT fk_ovr_by_user FOREIGN KEY (by_user)   REFERENCES users(id)   ON DELETE RESTRICT
);
COMMENT ON TABLE overdue_reasons IS 'Lý do trễ hạn (FR-014, BR-009). Mẫu overdue phải có >=1 trước khi trưởng nhóm chốt done/returned.';
```

---

## 3. CHECK constraints quan trọng — tổng hợp & ghi chú enforce

| Quy tắc | Constraint | DB enforce? | Ghi chú |
|---------|-----------|-------------|---------|
| `status` ∈ tập hợp lệ | `samples.CHECK (status IN (...))` | ✅ | FR-017/BR-001. **Whitelist (from,to)** enforce APP-layer (D9). CHECK chống giá trị rác. |
| `assignment.status` ∈ tập hợp lệ | `sample_assignments.CHECK (status IN (...))` | ✅ | FR-005/008/010 |
| `result.status` (draft/submitted/approved) | qua `approved_by`+`is_current` | ✅(suy) | SRS dùng `approved_by IS NULL` (=draft/chờ duyệt) vs `IS NOT NULL` (=approved). `ck_res_approval_pair` đảm bảo cặp nhất quán. "submitted" = đã nhập (`result_entered` ở assignment). |
| `deadline_at > received_at` | `ck_smp_deadline` | ✅ | BR-002, INVALID_DEADLINE |
| `condition_status='not_acceptable' ⇒ note NOT NULL` | `ck_smp_condition` | ✅ | BR-003, CONDITION_REASON_REQUIRED |
| `overdue_reasons.reason` NOT NULL & không rỗng | `NOT NULL` + `CHECK length>0` | ✅ | BR-009 |
| version sửa đổi phải có lý do | `ck_res_revision_reason` | ✅ | BR-010, REVISION_REASON_REQUIRED |
| mỗi assignment 1 version hiện hành | partial unique `uq_res_assignment_current` | ✅ | D6 — chống 2 dòng is_current cùng assignment |
| approved_by/approved_at đồng bộ | `ck_res_approval_pair` | ✅ | tránh trạng thái nửa-duyệt |
| handover không tự chuyển cho mình | `ck_ho_diff_user` | ✅ | FR-006 A3, INVALID_HANDOVER |
| `approved_by ≠ entered_by` (tách nhập-duyệt) | — | ⚠️ **app-layer** (D8) | BR-011, SELF_APPROVAL_FORBIDDEN. So 2 cột FK + RBAC → service validate, 403. |
| state transition (from,to) hợp lệ | — | ⚠️ **app-layer** (D9) | FR-017. Whitelist + row-lock trong transaction (§7). |
| assigned_to / to_user cùng phòng mẫu | — | ⚠️ **app-layer** | BR-004/007. ASSIGNEE_OUT_OF_DEPT / HANDOVER_OUT_OF_DEPT (422). |
| quyền assign/approve/finalize chỉ trưởng nhóm/Admin/Lãnh đạo | — | ⚠️ **app-layer** (đọc `departments.lead_user_id`) | BR-022. FORBIDDEN (403). |
| phạm vi đọc kết quả OQ#3 | — | ⚠️ **app-layer** (query filter) | BR-021. `approved_by IS NULL` chỉ entered_by+trưởng nhóm+Admin/Lãnh đạo. |
| mẫu chỉ done khi mọi assignment approved | — | ⚠️ **app-layer** (row-lock check) | BR-020/FR-019. Kiểm tra trong transaction, RESULTS_NOT_APPROVED (422). |
| mẫu overdue phải có overdue_reason trước done | — | ⚠️ **app-layer** | BR-009/FR-019. OVERDUE_REASON_REQUIRED (422). |
| không hard-delete mẫu bị M2 tham chiếu | FK RESTRICT (M2) + soft-delete | ✅+⚠️ | BR-016. M1 soft-delete (deleted_at); FK RESTRICT của M2 chặn hard-delete vô tình. |

> **Vì sao state machine & tách nhập-duyệt không CHECK DB:** giống quyết định M2 (BR-CHEM-028 ở app-layer). Whitelist chuyển trạng thái và RBAC trưởng nhóm cần lookup nghiệp vụ (đọc `departments.lead_user_id`, kiểm tra tất cả assignment) — không biểu diễn được bằng CHECK đơn cột; cần trả mã lỗi nghiệp vụ rõ ràng. CHECK DB giữ vai trò lưới an toàn cho **giá trị** (enum hợp lệ, cặp nhất quán).

---

## 4. Index strategy

```sql
-- ===== test_requests =====
-- UNIQUE(request_code) đã tạo composite index — tra cứu phiếu theo mã (FR-018)
CREATE INDEX idx_req_department     ON test_requests(department_id);            -- RBAC scope (BR-014)
CREATE INDEX idx_req_customer       ON test_requests(customer_id) WHERE customer_id IS NOT NULL; -- lọc theo khách
CREATE INDEX idx_req_received_at    ON test_requests(received_at DESC);         -- liệt kê phiếu mới nhất

-- ===== samples =====
-- UNIQUE(sample_code) đã tạo index — quét QR/tra mã (FR-002 AC3)
CREATE INDEX idx_smp_request        ON samples(request_id);                     -- liệt kê mẫu của phiếu (FR-018 AC2)
-- COMPOSITE: query phổ biến nhất — danh sách mẫu theo phòng + trạng thái (RBAC + lọc, NFR-PERF-002)
CREATE INDEX idx_smp_dept_status    ON samples(department_id, status);
-- CRON-1/CRON-2: tìm mẫu sắp/đã quá hạn & CHƯA done — partial index nhỏ, nhanh, idempotent (FR-013/014)
CREATE INDEX idx_smp_deadline_open  ON samples(deadline_at)
    WHERE status NOT IN ('done','returned') AND deleted_at IS NULL;
-- on-time rate (BR-019) + báo cáo: mẫu done trong kỳ
CREATE INDEX idx_smp_completed_at   ON samples(completed_at) WHERE completed_at IS NOT NULL;
-- người giữ hiện tại (FR-006 validate / dashboard "mẫu tôi đang giữ")
CREATE INDEX idx_smp_custodian      ON samples(current_custodian_id);
-- người tiếp nhận (lọc theo người nhận)
CREATE INDEX idx_smp_received_by    ON samples(received_by);

-- ===== sample_assignments =====
CREATE INDEX idx_asg_sample         ON sample_assignments(sample_id);           -- FK
-- COMPOSITE: kiểm tra "mọi part approved" khi chốt done (FR-019, BR-020) — quét theo mẫu + status
CREATE INDEX idx_asg_sample_status  ON sample_assignments(sample_id, status);
-- COMPOSITE: "phần việc của tôi" theo trạng thái (FR-008, dashboard KTV)
CREATE INDEX idx_asg_assignee_status ON sample_assignments(assigned_to, status);

-- ===== sample_results =====
CREATE INDEX idx_res_assignment     ON sample_results(assignment_id);           -- FK + lấy lịch sử version
-- xem kết quả công khai (FR-011): lọc đã approved theo phạm vi đọc
CREATE INDEX idx_res_approved       ON sample_results(assignment_id) WHERE approved_by IS NOT NULL;
-- (uq_res_assignment_current đã là index phục vụ "lấy version hiện hành")

-- ===== sample_handovers =====
-- COMPOSITE: dựng chain of custody theo thời gian (FR-007) + lấy custodian gần nhất (FR-006)
CREATE INDEX idx_ho_sample_at       ON sample_handovers(sample_id, at DESC);

-- ===== overdue_reasons =====
-- kiểm tra mẫu overdue đã có lý do chưa (FR-019/016 precheck) + báo cáo lý do trễ (FR-015)
CREATE INDEX idx_ovr_sample         ON overdue_reasons(sample_id);
```

**Lý do từng nhóm index:**
- **Lọc theo deadline cho CRON (FR-013/014):** `idx_smp_deadline_open` — **partial** chỉ index mẫu CHƯA done/returned & chưa xóa. CRON-1 (sắp hạn) và CRON-2 (quá hạn) chỉ quan tâm tập này → index nhỏ, quét nhanh, idempotent (BR-018). Đây là index quan trọng nhất cho cron (SRS §996).
- **Lọc theo status + phòng:** `idx_smp_dept_status` — query danh sách mẫu mặc định luôn kèm RBAC phòng + lọc trạng thái (NFR-PERF-SAMPLE-002, BR-014).
- **Theo `request_id`:** `idx_smp_request` — liệt kê mẫu của 1 phiếu (FR-018 AC2).
- **Theo `assigned_to`:** `idx_asg_assignee_status` — KTV xem "phần việc của tôi" (FR-008).
- **Kiểm tra "mọi part approved":** `idx_asg_sample_status` — FR-019 chốt done quét tất cả assignment của mẫu lọc theo status (trong transaction row-lock).
- **`sample_code` / `request_code`:** UNIQUE index — quét QR/tra mã không lộ tuần tự (FR-002/018, BR-015).
- **Chain of custody:** `idx_ho_sample_at` — composite `(sample_id, at DESC)` lấy custodian gần nhất (1 row) + dựng timeline (FR-006/007).
- **on-time rate:** `idx_smp_completed_at` — partial mẫu done (FR-015, BR-019).
- **Quan hệ ngược M2:** `chemical_transactions(ref_sample_id)` đã được tạo trong contract M2 (`idx_txn_ref_sample`) — M1 KHÔNG tạo lại.

> **Không over-index:** KHÔNG index `condition_status`, `note`, `sender_name`, `reason` (không dùng WHERE chọn lọc cao). Quy mô ~40 user, ~50K mẫu / ~200K kết quả (NFR §834) → không cần partition. `result_data` JSONB chưa cần GIN index (chưa có yêu cầu truy vấn trong JSON ở M1; thêm sau nếu báo cáo M6 cần).

---

## 5. Seed / khởi tạo

**Không bắt buộc seed cho M1.** Các bảng M1 đều là dữ liệu nghiệp vụ phát sinh runtime (phiếu/mẫu/phân công/kết quả). Không có danh mục cố định nào thuộc M1 (khác M2 có `units`).

Phụ thuộc dữ liệu khởi tạo (do M7/danh mục chung seed TRƯỚC):
- `departments` (kèm `lead_user_id` trỏ trưởng nhóm) — cần cho RBAC assign/approve/finalize (BR-022).
- `users` (ít nhất 1 Admin + KTV mỗi phòng).
- `customers` (có thể tạo nhanh runtime khi nhận mẫu — FR-018; không cần seed).

> Định dạng `sample_code`/`request_code` (`SP-YYYY-NNNN`/`RQ-YYYY-NNNN`) là tham số cấu hình app, KHÔNG seed DB (OPEN QUESTION #5 — chốt khi UAT, không đổi schema). Khuyến nghị bộ đếm theo năm: bảng đếm riêng hoặc sequence per-year ở app + UNIQUE constraint làm lưới chống trùng (FR-002 A1 retry).

---

## 6. Traceability — Map bảng/cột → FR/BR

| Bảng / Cột | FR | BR |
|------------|----|----|
| `test_requests` (toàn bộ) | FR-SAMPLE-018 | BR-013, 014, 015, 023 |
| `test_requests.request_code` (UNIQUE) | FR-018, FR-002 | BR-015 |
| `test_requests.department_id / received_by` | FR-018 | BR-014 (scope), ASSUMPTION-4 |
| `samples` (toàn bộ) | FR-001, 002, 004, 012, 016, 017, 019 | BR-001, 002, 003, 013, 015, 016, 023 |
| `samples.sample_code` (UNIQUE) | FR-002 | BR-015 |
| `samples.request_id` (FK NOT NULL) | FR-001, 018 | BR-023 (OQ#1) |
| `samples.department_id / received_by` (denorm D4) | FR-001 | BR-004, 014 |
| `samples.current_custodian_id` (denorm D5) | FR-006, 007 | BR-007, 017 |
| `samples.deadline_at` + `ck_smp_deadline` | FR-001, 012 | BR-002 |
| `samples.completed_at` | FR-019, 015 | BR-019, 020 |
| `samples.status` (CHECK) | FR-017 | BR-001 |
| `samples.condition_status/note` + `ck_smp_condition` | FR-004 | BR-003 |
| `samples.deleted_at` (soft-delete) | — | BR-016 (toàn vẹn với M2) |
| `sample_assignments` (toàn bộ) | FR-005 | BR-004, 006, 013, 022 |
| `sample_assignments.status` | FR-005, 008, 010, 019 | BR-001, 020 |
| `sample_assignments.assigned_to/by` | FR-005 | BR-004, 022 |
| `sample_results` (toàn bộ) | FR-008, 010, 011 | BR-008, 010, 011, 013, 021 |
| `sample_results.version + uq(assignment,version) + uq is_current` | FR-010 | BR-010 (versioning immutable, CONSTRAINT-3) |
| `sample_results.result_data` (JSONB) | FR-008 | — |
| `sample_results.entered_by / approved_by` (≠ enforce app) | FR-008, 010 | BR-008, 011 |
| `sample_results.approved_by IS NULL/NOT NULL` (phạm vi đọc) | FR-011 | BR-021 (OQ#3) |
| `sample_results.revision_reason` + `ck_res_revision_reason` | FR-010 | BR-010 |
| `sample_handovers` (IMMUTABLE) | FR-006, 007 | BR-007, 017, CONSTRAINT-2 |
| `sample_handovers.from_user/to_user` + `ck_ho_diff_user` | FR-006 | BR-007 |
| `overdue_reasons` (reason NOT NULL) | FR-014 | BR-009 |
| INSERT `audit_logs` (mọi thao tác) | tất cả FR | BR-013, CONSTRAINT-4, NFR-AUDIT-SAMPLE-001 |
| INSERT `notifications` | FR-005, 006, 013, 014 | BR-018 |
| `attachments` (owner_type='test_request'/'sample'/'sample_result') | FR-003, 009, 016 | BR-012 |
| FK mềm M2 `chemical_transactions.ref_sample_id → samples(id)` | (M2 FR-CHEM-006) | BR-016, BR-CHEM-025 |

---

## 7. Ghi chú cho dev (BẮT BUỘC đọc) — transaction, row-lock, concurrency

**NFR-CONCUR-SAMPLE-001 + BR-SAMPLE-001/011/020:** chuyển trạng thái, duyệt, chốt PHẢI atomic + row-lock trên `samples`.

### 7.1 Chuyển trạng thái mẫu (state machine — FR-017)
- Hàm transition trung tâm: `change_status(sample_id, to_status, trigger, user)`.
- Trong 1 transaction: `SELECT ... FROM samples WHERE id=:id FOR UPDATE` → kiểm tra `(from,to) ∈ WHITELIST` (D9) → UPDATE status → INSERT `audit_logs` action=`SAMPLE_STATE_CHANGE` (from→to, trigger, correlation_id).
- Whitelist (FR-017 §715): `received→assigned`, `{received,assigned,testing}→overdue`, `assigned→testing`, `testing→done`, `overdue→done`, `done→returned`, `overdue→{assigned,testing}` (chỉ khi gia hạn deadline > now — OQ#9). Ngoài whitelist → 422 `INVALID_STATE_TRANSITION`.

### 7.2 Chốt hoàn thành mẫu (FR-019, OQ#2 — KHÔNG auto-done)
```python
async with session.begin():
    sample = (await session.execute(
        select(Sample).where(Sample.id == sample_id).with_for_update()
    )).scalar_one()

    # 1. RBAC: user là trưởng nhóm phòng sample (departments.lead_user_id) / Admin / Lãnh đạo (BR-022)
    #    else -> 403 FORBIDDEN
    # 2. state: sample.status in ('testing','overdue') else -> 422 INVALID_STATE_TRANSITION
    # 3. mọi assignment đã approved (BR-020) — TRONG transaction để tránh race
    pending = (await session.execute(
        select(func.count()).select_from(SampleAssignment)
        .where(SampleAssignment.sample_id == sample_id,
               SampleAssignment.status != 'approved')
    )).scalar_one()
    if pending > 0:
        raise HTTP422("RESULTS_NOT_APPROVED")
    # 4. nếu từng overdue: phải có >=1 overdue_reason (BR-009) else -> 422 OVERDUE_REASON_REQUIRED
    # 5. set completed_at=now, status='done'; INSERT audit SAMPLE_FINALIZE (kèm list part approved)
```
- **KHÔNG auto-done:** sau khi duyệt part cuối (FR-010), mẫu **giữ `testing`** — chỉ chuyển `done` qua hành động chốt này (BR-020, AC2/AC6 FR-010).

### 7.3 Duyệt kết quả (FR-010)
- Transaction + lock dòng `sample_results` (hoặc assignment): validate `user có sample_result:approve` (BR-022) + `user ≠ entered_by` (D8/BR-011 → 403 `SELF_APPROVAL_FORBIDDEN`) → set `approved_by/approved_at`, `is_current=true`; UPDATE assignment.status='approved'; audit `SAMPLE_RESULT_APPROVE`.
- **Sửa sau approve (versioning, D6/BR-010):** trong transaction: set dòng cũ `is_current=false` → INSERT dòng mới `version = old.version+1`, `approved_by=NULL`, `is_current=true`, `revision_reason=` lý do (bắt buộc, else 400 `REVISION_REASON_REQUIRED`); audit `SAMPLE_RESULT_REVISE`. Dòng cũ giữ NGUYÊN (bất biến). Mẫu/kết quả tạm rút công khai cho tới khi duyệt lại (vì `approved_by IS NULL`).
- **Chặn sửa trực tiếp:** KHÔNG route PUT/PATCH/DELETE trên `sample_results` đã approved → 422 `RESULT_LOCKED`.

### 7.4 Chuyển giao mẫu (handover — FR-006)
- Transaction + lock `samples`: validate `from_user = sample.current_custodian_id` (hoặc trưởng nhóm/Admin điều phối — BR-007 → 403 `NOT_CURRENT_CUSTODIAN`) + `to_user` cùng phòng (422 `HANDOVER_OUT_OF_DEPT`) + `to_user ≠ from_user` (422 `INVALID_HANDOVER`, cũng có CHECK DB) → INSERT `sample_handovers` → UPDATE `samples.current_custodian_id = to_user` (denorm D5) → INSERT `notifications` cho to_user → audit `SAMPLE_HANDOVER`.
- **Immutable:** KHÔNG route sửa/xóa handover (BR-017). Nhầm → ghi handover đính chính mới.

### 7.5 CRON-1 / CRON-2 (idempotent + Redis lock — BR-018)
- **CRON-2 (00:30 đánh dấu overdue):** acquire Redis lock → quét `samples WHERE status IN ('received','assigned','testing') AND deadline_at < now() AND deleted_at IS NULL` (dùng `idx_smp_deadline_open`) → mỗi mẫu: transaction lock → đổi `status='overdue'` (qua hàm transition 7.1) → INSERT notification (chống trùng theo mẫu×ngày) → audit `SAMPLE_MARK_OVERDUE`. Chạy lại cùng ngày: mẫu đã `overdue` không bị quét lại (status filter) → idempotent.
- **CRON-1 (07:00 nhắc sắp hạn):** quét cùng partial index, `deadline_at` trong mốc (≤3 và ≤1 ngày — OQ#4 cấu hình) & chưa done → INSERT notification cho assignee + custodian + trưởng nhóm; **chống trùng mỗi mẫu × mỗi mốc × ngày** (BR-018). Gợi ý: dùng bảng dedup tương tự M2 (`chemical_notification_dedup`) hoặc kiểm tra `notifications` theo (ref_id, type, ngày) — thống nhất với M7. **Nếu dùng bảng dedup riêng cho M1**, đặt tên `sample_notification_dedup(sample_id, kind, milestone, fire_date)` UNIQUE — nhưng nên tái dùng cơ chế M7 nếu có (xem §8 điểm 4).

### 7.6 Soft-delete & toàn vẹn M2 (BR-016)
- KHÔNG hard-delete `samples`/`sample_results`/`sample_handovers`/`overdue_reasons`.
- Soft-delete `samples` (set `deleted_at`) CHỈ khi: không có dòng `chemical_transactions` nào `ref_sample_id=sample.id` (kiểm tra app-layer) VÀ chưa có kết quả approved. FK RESTRICT phía M2 là lưới an toàn cuối (hard-delete sẽ bị DB chặn).

### 7.7 Quy ước chung (đồng bộ logging.md / M2)
- Dùng `Decimal`/NUMERIC nếu kết quả có số (trong `result_data` JSONB tùy chỉ tiêu) — KHÔNG float cho số đo lường lưu lâu dài.
- Mọi thao tác ghi kèm `correlation_id` vào `audit_logs` (NFR-AUDIT-SAMPLE-001).
- KHÔNG expose endpoint chuyển trạng thái tùy ý ra client; trạng thái là hệ quả của API nghiệp vụ (FR-017 §734).

---

## 8. Điểm cần Tech Lead chú ý (review trước APPROVED)

1. **`samples.id` UUID khớp FK M2 — đã đảm bảo (D1).** `chemical_transactions.ref_sample_id → samples(id)` (M2 §276, ON DELETE RESTRICT). **Hệ quả thứ tự migration:** `samples` PHẢI tồn tại TRƯỚC khi M2 tạo `chemical_transactions`. Xem §9.
2. **Denormalize `department_id`/`received_by`/`current_custodian_id` trên `samples` (D4/D5):** đánh đổi — app phải giữ đồng bộ (set khi tạo mẫu từ phiếu; cập nhật custodian khi handover). Lợi: RBAC scope + "ai đang giữ" query không cần join. Nguồn chân lý custody vẫn là `sample_handovers` bất biến. **Cần Tech Lead xác nhận chấp nhận denorm.**
3. **State machine, tách nhập-duyệt, RBAC trưởng nhóm, phạm vi đọc OQ#3, "mọi part approved" — enforce APP-LAYER** (D8/D9, §3). DB chỉ CHECK giá trị. Đồng bộ phong cách M2 (BR-CHEM-028 app-layer). Nếu QA/security yêu cầu defense-in-depth DB-level → cân nhắc trigger cho state transition (chưa thêm để giữ schema đơn giản).
4. **Dedup CRON-1 (BR-018):** contract chưa tạo bảng dedup riêng cho M1 — đề xuất **tái dùng cơ chế dedup của M7/notifications** hoặc tạo `sample_notification_dedup` tương tự M2. **Cần Tech Lead chốt** thống nhất 1 cơ chế dedup chung cho mọi cron (M1/M2/M4/M5). CRON-2 idempotent nhờ status filter (không cần dedup table).
5. **Bảng `customers`:** ERD core đặt trong khối M1 nhưng có thể thuộc danh mục chung/M7. Contract **giả định `customers` đã tồn tại** trước M1. **Nếu chưa có owner rõ ràng**, Tech Lead quyết: (a) thêm CREATE TABLE customers tối thiểu vào migration M1, hoặc (b) M7/danh mục tạo trước. `customer_id` của phiếu để NULLABLE (khách vãng lai chỉ ghi `sender_name`).
6. **`departments.lead_user_id` (M7, OQ#11):** M1 KHÔNG tạo/sửa `departments`. **M7 PHẢI bổ sung cột `lead_user_id UUID FK→users NULL` vào `departments`** trước khi M1 implement RBAC assign/approve/finalize (CONSTRAINT-9). Ghi chú để owner M7 cập nhật ERD master.
7. **`result_data` JSONB không validate cấu trúc ở DB:** mỗi chỉ tiêu có schema khác nhau (FR-008). Validate theo biểu mẫu chỉ tiêu ở app-layer (400 `VALIDATION_ERROR`). Chưa cần GIN index.
8. **Cập nhật ERD master (`01-demo-scope.md` mục C — M1):** so với ERD core, contract này BỔ SUNG: bảng mới `test_requests`; `samples` thêm `request_id`, denorm `department_id/received_by/current_custodian_id`, `completed_at`, `condition_status`, `deleted_at`, audit fields; `sample_results` thêm `version`/`is_current`/`revision_reason`; `overdue_reasons.reason` đổi thành NOT NULL. ERD core dùng native ENUM → đổi sang CHECK VARCHAR (đồng bộ M2). → Đề nghị Tech Lead cập nhật ERD master sau APPROVED.

---

## 9. Migration & Rollback

```
-- [ MIGRATION FILE NAME ] (Alembic)
-- <revision>_m1_sample_lifecycle.py  (depends_on: M7 auth/org/customers)
-- Thứ tự CREATE: test_requests → samples → sample_assignments
--               → sample_results → sample_handovers → overdue_reasons
--               → indexes

-- [ THỨ TỰ MIGRATION TỔNG THỂ ]
--   1. M7  (users, departments[+lead_user_id], customers, attachments,
--           audit_logs, notifications, pgcrypto)
--   2. M1  (contract này — tạo samples + các bảng phụ)         ← SAU M7
--   3. M2  (chemical_*; FK ref_sample_id → samples(id))         ← SAU M1
--   Lý do: M2.chemical_transactions FK tới samples(id) → samples phải có trước.
--          M1 FK tới users/departments/customers → M7 phải có trước.
--   M1 và M2 không vòng (M2 phụ thuộc M1 một chiều, không ngược lại).

-- [ ROLLBACK PLAN ] (downgrade) — drop ngược thứ tự FK:
DROP TABLE IF EXISTS overdue_reasons    CASCADE;
DROP TABLE IF EXISTS sample_handovers   CASCADE;
DROP TABLE IF EXISTS sample_results     CASCADE;
DROP TABLE IF EXISTS sample_assignments CASCADE;
DROP TABLE IF EXISTS samples            CASCADE;   -- LƯU Ý: nếu M2 đã tạo & có FK ref_sample_id,
                                                   -- phải rollback M2 trước (DROP chemical_transactions).
DROP TABLE IF EXISTS test_requests      CASCADE;
-- KHÔNG drop extension pgcrypto (dùng chung). KHÔNG drop users/departments/customers (M7).

-- [ EXISTING TABLE CHANGES ]
-- M1 KHÔNG ALTER bảng đã tồn tại của M1.
-- PHỤ THUỘC (do M7 thực hiện, KHÔNG trong migration M1):
--   ALTER TABLE departments ADD COLUMN lead_user_id UUID NULL
--     REFERENCES users(id) ON DELETE SET NULL;   -- OQ#11, BR-022 (non-breaking)

-- [ DATA DEPENDENCIES ]
-- Seed TRƯỚC: KHÔNG có seed bắt buộc của M1.
-- Phụ thuộc bảng có sẵn (M7/chung): users, departments(+lead_user_id),
--   customers, attachments, audit_logs, notifications.
-- Bảng phụ thuộc vào M1 (tạo SAU): chemical_transactions (M2) qua ref_sample_id.
```

---

*Hết Contract M1 Schema v1.0. Tuân thủ: PK UUID gen_random_uuid, NUMERIC/TIMESTAMPTZ không float, CHECK thay native ENUM, FK rõ ON DELETE, immutable cho handover/result approved/overdue_reason, index mọi FK + query pattern + partial index cron, rollback + thứ tự migration đầy đủ, traceability FR/BR. Đồng bộ tuyệt đối quy ước với Contract M2. Chờ `/contract` gate APPROVED trước khi feature-builder implement.*
