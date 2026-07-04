# Contract — M2 Schema: Quản lý Hóa chất & Tồn kho

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M2 — Chemical Inventory
**Tài liệu:** Database Schema Contract (DDL + Index + Seed + Traceability)
**Version:** 1.0 | **Ngày:** 19/06/2026 | **Author:** schema-designer agent
**Stack:** PostgreSQL 15+, FastAPI + SQLAlchemy/Alembic
**Nguồn chân lý:** `02-srs-m2-chemical.md` (SRS v1.2 — 14 FR, 30 BR, NFR), `01-demo-scope.md` (ERD core)
**Status:** DRAFT — chờ Tech Lead / `/contract` gate review

---

## 0. Quyết định thiết kế chính (đọc trước)

| # | Quyết định | Lý do |
|---|-----------|-------|
| D1 | **PK = UUID `DEFAULT gen_random_uuid()`** cho mọi bảng nghiệp vụ (`chemicals`, `chemical_lots`, `chemical_transactions`, `chemical_recheck_records`). | CONSTRAINT-6 (không lộ ID tuần tự) + rule global. Nhất quán với `samples.id`, `users.id`, `attachments.id` của ERD core (đều `id PK` — diễn giải là UUID). Cần extension `pgcrypto` cho `gen_random_uuid()`. |
| D2 | **`units.code` = natural PK kiểu `VARCHAR(16)`** (KHÔNG UUID). | `units` là danh mục seed cố định do quản trị (BR-CHEM-029), không lộ ra như resource người dùng; `code` ('kg','g','mg','mL','L','unit') vừa là khóa vừa là giá trị nghiệp vụ dùng trực tiếp trong FK của `chemicals`/`lots`/`transactions` → join rẻ, đọc dễ. Không đoán được vì là danh mục cố định công khai. |
| D3 | **Tồn/giao dịch base unit = `NUMERIC(18,6)`**; qty người dùng nhập = `NUMERIC(14,4)`; **không FLOAT ở bất kỳ đâu**. | CONSTRAINT-1, BR-CHEM-008/026, NFR-CORRECT-CHEM-001/002. |
| D4 | **Tiền = `NUMERIC(14,2)`** cho `unit_price` (KHÔNG dùng BIGINT đồng). | SRS chốt rõ `unit_price NUMERIC(14,2)` (BR-CHEM-023, CONSTRAINT-1b). Lý do khác rule "tiền = BIGINT": đơn giá hóa chất có thể là VND/g lẻ thập phân (vd 1200.50 VND/g) và có `currency` đa tệ → NUMERIC(14,2) chuẩn xác hơn BIGINT đồng. **Điểm cần Tech Lead xác nhận** (xem §8). |
| D5 | **`measurement_group`, `recheck_result`, `transaction.type` dùng CHECK constraint trên VARCHAR**, KHÔNG dùng native PG ENUM. | ENUM native khó migrate (ALTER TYPE ... ADD VALUE không rollback gọn trong Alembic); CHECK + VARCHAR dễ thêm giá trị, dễ sửa, đủ chặt. Tuân "không magic string" qua CHECK. |
| D6 | **`measurement_group` lưu denormalized ở `chemicals`** (đồng bộ với `units.measurement_group` của `base_unit`). | SRS §756 yêu cầu để chặn quy đổi chéo nhóm nhanh (BR-CHEM-028); ràng buộc nhất quán bằng FK composite (xem §3). |
| D7 | **Tồn lô lưu trực tiếp ở `chemical_lots.qty_base`** (maintain bởi giao dịch trong transaction có row-lock), KHÔNG SUM runtime. | BR-CHEM-011/014, ASSUMPTION-4, NFR-PERF/CONCUR. Reconcile bằng `balance_after` (FR-CHEM-008 A1). |
| D8 | **Soft-delete:** `chemicals` có `status` ('active'/'inactive') thay cho `deleted_at` (SRS gọi "vô hiệu hóa" = inactive). `chemical_transactions` **immutable, KHÔNG soft-delete** (BR-CHEM-015). | Hồ sơ kỹ thuật không được tẩy xóa (17025 §7.5/§8.4). |
| D9 | **Audit ghi vào bảng dùng chung `audit_logs`** (M7) — M2 KHÔNG tạo bảng audit riêng. | CONSTRAINT-3, BR-CHEM-012. M2 chỉ INSERT vào `audit_logs`. |
| D10 | **Chống trùng cron (CRON-6)** bằng bảng phụ `chemical_notification_dedup` (lô × loại × mốc × ngày UNIQUE). | BR-CHEM-021, FR-CHEM-012 AC2 (idempotent). |

> **Audit fields:** rule global yêu cầu `created_by/updated_by UUID REFERENCES users(id)` trên bảng tài chính. M2 áp dụng `created_by` (FK→users) trên `chemicals`, `chemical_lots`. `chemical_transactions` dùng `by_user` (người thực hiện) thay cho cặp created/updated vì giao dịch là immutable (không có "update"). `units` là danh mục hệ thống → không cần audit user fields.

---

## 1. ERD chi tiết M2 (ASCII)

```
                      ┌──────────────────────────────────────────────┐
                      │  units  (DANH MỤC SEED — không sửa runtime)   │
                      │  code            VARCHAR(16) PK               │
                      │  label           VARCHAR(64)                  │
                      │  measurement_group VARCHAR(10) CHECK          │
                      │                  (mass|volume|count)          │
                      │  factor_to_base  NUMERIC(20,6)  (>0)          │
                      │  UNIQUE(code)                                 │
                      └──────────────────────────────────────────────┘
                          ▲ base_unit        ▲ price_unit   ▲ input_unit/base_unit
                          │ (FK code)        │ (FK code)    │ (FK code)
        ┌─────────────────┴────────┐         │              │
        │  chemicals               │         │              │
        │  id            UUID PK   │         │              │
        │  name          VARCHAR   │         │              │
        │  cas_no        VARCHAR    NULL      │              │
        │  manufacturer  VARCHAR    NULL      │              │
        │  base_unit     VARCHAR(16) FK→units │              │
        │  measurement_group VARCHAR(10)  ────┼── composite FK (base_unit, measurement_group)
        │  hazard_code   VARCHAR    NULL      │   → units(code, measurement_group)
        │  reorder_threshold NUMERIC(18,6) NULL (>=0)        │
        │  department_id UUID FK→departments(RESTRICT)       │
        │  status        VARCHAR(10) (active|inactive)       │
        │  created_by    UUID FK→users      created_at/updated_at/updated_by
        │  UNIQUE(department_id, name, cas_no)               │
        └───────────┬────────────────────────────────────────┘
                    │ 1
                    │
                    │ N
        ┌───────────▼────────────────────────────────────────┐
        │  chemical_lots                                      │
        │  id            UUID PK                              │
        │  chemical_id   UUID FK→chemicals(RESTRICT)          │
        │  lot_no        VARCHAR(64)                          │
        │  qty_base      NUMERIC(18,6) (>=0)  ← tồn hiện tại  │
        │  unit_price    NUMERIC(14,2) (>=0) DEFAULT 0        │
        │  price_unit    VARCHAR(16) FK→units(RESTRICT)       │
        │  currency      VARCHAR(3) DEFAULT 'VND'             │
        │  received_at   DATE                                │
        │  expiry_date   DATE NULL                            │
        │  recheck_date  DATE NULL                            │
        │  recheck_result VARCHAR(4) NULL (pass|fail)         │
        │  is_expired    BOOLEAN DEFAULT false                │
        │  coa_file_key  VARCHAR NULL  (MinIO key)            │
        │  created_by    UUID FK→users  created_at/updated_at/updated_by
        │  UNIQUE(chemical_id, lot_no)                        │
        │  CHECK(recheck_date <= expiry_date)                │
        └───────────┬────────────────────────────────────────┘
                    │ 1
                    │
                    │ N
        ┌───────────▼────────────────────────────────────────────────────┐
        │  chemical_transactions   (IMMUTABLE — không UPDATE/DELETE)       │
        │  id            UUID PK                                           │
        │  lot_id        UUID FK→chemical_lots(RESTRICT)                   │
        │  type          VARCHAR(8) (in|out|adjust)                        │
        │  qty_base      NUMERIC(18,6)   (in:>0, out:>0, adjust:≠0 có dấu) │
        │  base_unit     VARCHAR(16) FK→units(RESTRICT)                    │
        │  qty_input     NUMERIC(14,4)                                     │
        │  input_unit    VARCHAR(16) FK→units(RESTRICT)                    │
        │  balance_after NUMERIC(18,6) (>=0)                               │
        │  unit_price    NUMERIC(14,2) NULL (>=0)  (đồng bộ lô khi type=in)│
        │  price_unit    VARCHAR(16) FK→units NULL                         │
        │  currency      VARCHAR(3) NULL                                   │
        │  ref_sample_id UUID FK→samples NULL                              │
        │                  CHECK: type='out' ⇒ NOT NULL                    │
        │  warning_override BOOLEAN DEFAULT false                         │
        │  note          TEXT NULL  (CHECK: type='adjust' ⇒ NOT NULL)      │
        │  by_user       UUID FK→users(RESTRICT)                          │
        │  correlation_id VARCHAR(64) NULL                                │
        │  at            TIMESTAMPTZ DEFAULT now()                         │
        └─────────────────────────────────────────────────────────────────┘
                    │ ref_sample_id (soft ref tới M1)
                    ▼
        ┌──────────────────────────┐        ┌──────────────────────────────┐
        │ samples (M1 — chỉ đọc)   │        │ chemical_recheck_records      │
        │ id UUID PK, sample_code  │        │ id UUID PK                    │
        └──────────────────────────┘        │ lot_id UUID FK→chemical_lots  │
                                            │ checked_at DATE               │
        ┌──────────────────────────┐        │ result VARCHAR(4)(pass|fail)  │
        │ attachments (dùng chung) │        │ note TEXT NULL                │
        │ owner_type='chemical'    │        │ attachment_id UUID FK NULL    │
        │   (MSDS) hoặc 'chem_lot' │        │ next_recheck_date DATE NULL   │
        │   (CoA — nếu dùng bảng)  │        │ checked_by UUID FK→users      │
        └──────────────────────────┘        │ created_at TIMESTAMPTZ        │
                                            └──────────────────────────────┘
        ┌──────────────────────────────────────────────────────────┐
        │ chemical_notification_dedup  (chống trùng CRON-6)         │
        │ id UUID PK, lot_id FK→chemical_lots, kind VARCHAR         │
        │   (CHEM_EXPIRY|CHEM_RECHECK_DUE), milestone_days SMALLINT │
        │   (30|15|7), fire_date DATE                               │
        │ UNIQUE(lot_id, kind, milestone_days, fire_date)          │
        └──────────────────────────────────────────────────────────┘
```

### Bảng dùng chung tham chiếu (KHÔNG tạo lại — sở hữu bởi M7/M1)

| Bảng | Sở hữu | M2 dùng để |
|------|--------|-----------|
| `users(id UUID PK, ...)` | M7 | FK `created_by`, `updated_by`, `by_user`, `checked_by` |
| `departments(id UUID PK, ...)` | M7 | FK `chemicals.department_id` (phạm vi RBAC) |
| `samples(id UUID PK, sample_code, ...)` | M1 | FK mềm `chemical_transactions.ref_sample_id` |
| `attachments(id, owner_type, owner_id, file_key, ...)` | dùng chung | CoA + MSDS (polymorphic) |
| `audit_logs(id, user_id, action, resource, resource_id, correlation_id, ip, at, detail)` | M7 | INSERT mọi thao tác M2 (BR-CHEM-012) |
| `notifications(id, user_id, type, title, body, ref_type, ref_id, read_at, created_at)` | M7 | INSERT cảnh báo tồn thấp + cron (FR-CHEM-010/012) |

---

## 2. DDL đầy đủ

> Migration viết SQL thuần để dev chuyển sang Alembic (`op.execute(...)` hoặc tách `op.create_table`). **Lưu ý dev:** với native PG, `gen_random_uuid()` cần `CREATE EXTENSION IF NOT EXISTS pgcrypto;` (PG 13+) — đặt ở migration M7/khởi tạo chung; nếu chưa có thì bật trong migration M2 đầu tiên.

```sql
-- ============================================================
-- SCHEMA: m2-chemical-inventory
-- Feature: Quản lý Hóa chất & Tồn kho (LIMS 17025)
-- Designer: schema-designer agent | Date: 2026-06-19
-- Prereq: pgcrypto, bảng users/departments/samples/attachments/
--         audit_logs/notifications (M7/M1) đã tồn tại.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

-- ------------------------------------------------------------
-- [ NEW TABLE ] units — danh mục đơn vị + hệ số quy đổi (seed cố định)
--   BR-CHEM-029: người dùng cuối KHÔNG sửa; chỉ seed/migration quản trị.
-- ------------------------------------------------------------
CREATE TABLE units (
    code                VARCHAR(16)  PRIMARY KEY,                 -- 'kg','g','mg','mL','L','unit'
    label               VARCHAR(64)  NOT NULL,                    -- nhãn hiển thị
    measurement_group   VARCHAR(10)  NOT NULL
        CHECK (measurement_group IN ('mass', 'volume', 'count')), -- nhóm đo (BR-CHEM-028)
    factor_to_base      NUMERIC(20,6) NOT NULL
        CHECK (factor_to_base > 0),                               -- hệ số đổi về base nhỏ nhất của nhóm
    -- composite unique để chemicals tham chiếu (code, measurement_group) — chặn quy đổi chéo nhóm
    UNIQUE (code, measurement_group)
);
COMMENT ON TABLE  units IS 'Danh mục đơn vị + hệ số quy đổi cố định (BR-CHEM-029). Seed-only.';
COMMENT ON COLUMN units.factor_to_base IS 'Số base-unit cho 1 đơn vị này. VD mass(base=mg): kg=1000000, g=1000, mg=1.';

-- ------------------------------------------------------------
-- [ NEW TABLE ] chemicals — danh mục hóa chất (FR-CHEM-001)
-- ------------------------------------------------------------
CREATE TABLE chemicals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(255) NOT NULL,                    -- BR-CHEM-001 bắt buộc
    cas_no              VARCHAR(20)  NULL,                        -- định dạng NNNNNNN-NN-N (validate app layer)
    manufacturer        VARCHAR(255) NULL,
    base_unit           VARCHAR(16)  NOT NULL,                    -- FK→units.code (BR-CHEM-026)
    measurement_group   VARCHAR(10)  NOT NULL                     -- denormalized từ units (D6, BR-CHEM-028)
        CHECK (measurement_group IN ('mass', 'volume', 'count')),
    hazard_code         VARCHAR(64)  NULL,                        -- GHS vd 'H314' (FR-CHEM-003)
    reorder_threshold   NUMERIC(18,6) NULL
        CHECK (reorder_threshold IS NULL OR reorder_threshold >= 0), -- theo base_unit (FR-CHEM-010)
    department_id       UUID         NOT NULL,                    -- phạm vi RBAC (BR-CHEM-018)
    status              VARCHAR(10)  NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive')),                 -- soft-delete = inactive (BR-CHEM-004)
    created_by          UUID         NOT NULL,
    updated_by          UUID         NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_chem_dept     FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
    CONSTRAINT fk_chem_created  FOREIGN KEY (created_by)    REFERENCES users(id)       ON DELETE RESTRICT,
    CONSTRAINT fk_chem_updated  FOREIGN KEY (updated_by)    REFERENCES users(id)       ON DELETE RESTRICT,
    -- composite FK: base_unit phải khớp đúng measurement_group đã ghi (BR-CHEM-026/028)
    CONSTRAINT fk_chem_baseunit FOREIGN KEY (base_unit, measurement_group)
        REFERENCES units(code, measurement_group) ON DELETE RESTRICT,
    -- không trùng (tên + CAS) trong cùng phòng ban (BR-CHEM-002).
    -- Lưu ý: NULL cas_no không bị UNIQUE chặn -> bổ sung partial unique cho cas_no IS NULL ở phần INDEX.
    CONSTRAINT uq_chem_dept_name_cas UNIQUE (department_id, name, cas_no)
);
COMMENT ON TABLE chemicals IS 'Danh mục hóa chất (FR-CHEM-001). status=inactive là soft-delete.';

-- ------------------------------------------------------------
-- [ NEW TABLE ] chemical_lots — lô hóa chất (FR-CHEM-002)
-- ------------------------------------------------------------
CREATE TABLE chemical_lots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chemical_id         UUID         NOT NULL,
    lot_no              VARCHAR(64)  NOT NULL,                    -- BR-CHEM-005 unique trong hóa chất
    qty_base            NUMERIC(18,6) NOT NULL DEFAULT 0
        CHECK (qty_base >= 0),                                    -- tồn hiện tại, base unit (BR-CHEM-009)
    unit_price          NUMERIC(14,2) NOT NULL DEFAULT 0
        CHECK (unit_price >= 0),                                  -- đơn giá theo price_unit (BR-CHEM-023)
    price_unit          VARCHAR(16)  NOT NULL,                    -- đơn vị tính giá = đơn vị nhập (BR-CHEM-030)
    currency            VARCHAR(3)   NOT NULL DEFAULT 'VND',
    received_at         DATE         NULL,
    expiry_date         DATE         NULL,
    recheck_date        DATE         NULL,
    recheck_result      VARCHAR(4)   NULL
        CHECK (recheck_result IS NULL OR recheck_result IN ('pass', 'fail')), -- FR-CHEM-011
    is_expired          BOOLEAN      NOT NULL DEFAULT false,      -- FR-CHEM-002 A1
    coa_file_key        VARCHAR(512) NULL,                        -- MinIO key (CoA, 17025 §6.6)
    created_by          UUID         NOT NULL,
    updated_by          UUID         NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_lot_chemical  FOREIGN KEY (chemical_id) REFERENCES chemicals(id)  ON DELETE RESTRICT,
    CONSTRAINT fk_lot_priceunit FOREIGN KEY (price_unit)  REFERENCES units(code)    ON DELETE RESTRICT,
    CONSTRAINT fk_lot_created   FOREIGN KEY (created_by)  REFERENCES users(id)      ON DELETE RESTRICT,
    CONSTRAINT fk_lot_updated   FOREIGN KEY (updated_by)  REFERENCES users(id)      ON DELETE RESTRICT,
    CONSTRAINT uq_lot_chem_lotno UNIQUE (chemical_id, lot_no),                       -- BR-CHEM-005
    -- recheck_date <= expiry_date (BR-CHEM-006); NULL ở 1 trong 2 thì bỏ qua
    CONSTRAINT ck_lot_date_order CHECK (
        recheck_date IS NULL OR expiry_date IS NULL OR recheck_date <= expiry_date
    )
);
COMMENT ON TABLE chemical_lots IS 'Lô hóa chất (FR-CHEM-002). qty_base = tồn hiện tại theo base unit, maintain bởi giao dịch trong txn có row-lock (D7).';

-- ------------------------------------------------------------
-- [ NEW TABLE ] chemical_transactions — giao dịch (FR-CHEM-005/006/007)
--   IMMUTABLE: KHÔNG có endpoint UPDATE/DELETE (BR-CHEM-015, NFR-AUDIT-CHEM-001)
-- ------------------------------------------------------------
CREATE TABLE chemical_transactions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_id              UUID         NOT NULL,
    type                VARCHAR(8)   NOT NULL
        CHECK (type IN ('in', 'out', 'adjust')),
    qty_base            NUMERIC(18,6) NOT NULL,                   -- in:>0 out:>0 adjust:≠0 (CHECK bên dưới)
    base_unit           VARCHAR(16)  NOT NULL,
    qty_input           NUMERIC(14,4) NOT NULL,                   -- đúng người dùng nhập (BR-CHEM-027)
    input_unit          VARCHAR(16)  NOT NULL,
    balance_after       NUMERIC(18,6) NOT NULL
        CHECK (balance_after >= 0),                               -- tồn sau giao dịch (BR-CHEM-009/011)
    unit_price          NUMERIC(14,2) NULL
        CHECK (unit_price IS NULL OR unit_price >= 0),            -- đồng bộ lô khi type=in (FR-CHEM-005)
    price_unit          VARCHAR(16)  NULL,
    currency            VARCHAR(3)   NULL,
    ref_sample_id       UUID         NULL,                        -- type=out: NOT NULL (CHECK bên dưới)
    warning_override    BOOLEAN      NOT NULL DEFAULT false,      -- xuất lô fail/quá hạn (BR-CHEM-024)
    note                TEXT         NULL,                        -- type=adjust: NOT NULL (CHECK bên dưới)
    by_user             UUID         NOT NULL,                    -- người thực hiện
    correlation_id      VARCHAR(64)  NULL,                        -- trace FE→BE→audit (NFR-OBS)
    at                  TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_txn_lot        FOREIGN KEY (lot_id)        REFERENCES chemical_lots(id) ON DELETE RESTRICT,
    CONSTRAINT fk_txn_baseunit   FOREIGN KEY (base_unit)     REFERENCES units(code)       ON DELETE RESTRICT,
    CONSTRAINT fk_txn_inputunit  FOREIGN KEY (input_unit)    REFERENCES units(code)       ON DELETE RESTRICT,
    CONSTRAINT fk_txn_priceunit  FOREIGN KEY (price_unit)    REFERENCES units(code)       ON DELETE RESTRICT,
    CONSTRAINT fk_txn_sample     FOREIGN KEY (ref_sample_id) REFERENCES samples(id)       ON DELETE RESTRICT,
    CONSTRAINT fk_txn_byuser     FOREIGN KEY (by_user)       REFERENCES users(id)         ON DELETE RESTRICT,

    -- qty_base theo loại giao dịch (BR-CHEM-007)
    CONSTRAINT ck_txn_qty_sign CHECK (
        (type IN ('in', 'out') AND qty_base > 0)
        OR (type = 'adjust' AND qty_base <> 0)
    ),
    -- type=out ⇒ ref_sample_id NOT NULL (BR-CHEM-025, OQ#3) — enforce ở DB
    CONSTRAINT ck_txn_out_sample CHECK (
        type <> 'out' OR ref_sample_id IS NOT NULL
    ),
    -- type=adjust ⇒ note NOT NULL & không rỗng (BR-CHEM-016, OQ#4)
    CONSTRAINT ck_txn_adjust_note CHECK (
        type <> 'adjust' OR (note IS NOT NULL AND length(btrim(note)) > 0)
    )
);
COMMENT ON TABLE chemical_transactions IS 'Giao dịch hóa chất IMMUTABLE (BR-CHEM-015). qty_base luôn base unit; balance_after snapshot tồn lô sau giao dịch.';
COMMENT ON COLUMN chemical_transactions.qty_input IS 'Đúng giá trị người dùng nhập theo input_unit (audit 17025 §8.4, BR-CHEM-027).';

-- ------------------------------------------------------------
-- [ NEW TABLE ] chemical_recheck_records — lịch sử kiểm tra lại (FR-CHEM-011)
-- ------------------------------------------------------------
CREATE TABLE chemical_recheck_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_id              UUID         NOT NULL,
    checked_at          DATE         NOT NULL,
    result              VARCHAR(4)   NOT NULL
        CHECK (result IN ('pass', 'fail')),
    note                TEXT         NULL,
    attachment_id       UUID         NULL,                        -- bằng chứng (attachments dùng chung)
    next_recheck_date   DATE         NULL,                        -- recheck_date kỳ tiếp theo
    checked_by          UUID         NOT NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_recheck_lot     FOREIGN KEY (lot_id)        REFERENCES chemical_lots(id) ON DELETE RESTRICT,
    CONSTRAINT fk_recheck_attach  FOREIGN KEY (attachment_id) REFERENCES attachments(id)   ON DELETE SET NULL,
    CONSTRAINT fk_recheck_byuser  FOREIGN KEY (checked_by)    REFERENCES users(id)         ON DELETE RESTRICT
);
COMMENT ON TABLE chemical_recheck_records IS 'Lịch sử kiểm tra lại lô (FR-CHEM-011). Cập nhật chemical_lots.recheck_result + recheck_date theo bản ghi mới nhất.';

-- ------------------------------------------------------------
-- [ NEW TABLE ] chemical_notification_dedup — chống trùng CRON-6 (BR-CHEM-021)
-- ------------------------------------------------------------
CREATE TABLE chemical_notification_dedup (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_id              UUID         NOT NULL,
    kind                VARCHAR(20)  NOT NULL
        CHECK (kind IN ('CHEM_EXPIRY', 'CHEM_RECHECK_DUE')),
    milestone_days      SMALLINT     NOT NULL
        CHECK (milestone_days IN (30, 15, 7)),
    fire_date           DATE         NOT NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_dedup_lot FOREIGN KEY (lot_id) REFERENCES chemical_lots(id) ON DELETE CASCADE,
    CONSTRAINT uq_dedup_lot_kind_ms_date UNIQUE (lot_id, kind, milestone_days, fire_date)  -- idempotent
);
COMMENT ON TABLE chemical_notification_dedup IS 'Chống trùng notification cron (FR-CHEM-012 AC2). ON DELETE CASCADE vì chỉ là cờ phụ trợ, không phải hồ sơ pháp lý.';
```

---

## 3. CHECK constraints quan trọng — tổng hợp & ghi chú enforce

| Quy tắc | Constraint | DB enforce được? | Ghi chú |
|---------|-----------|------------------|---------|
| `qty_base >= 0` (tồn lô) | `chemical_lots.CHECK (qty_base >= 0)` | ✅ | BR-CHEM-009 |
| `balance_after >= 0` | `chemical_transactions.CHECK (balance_after >= 0)` | ✅ | BR-CHEM-009/011 |
| qty giao dịch in/out > 0 | `ck_txn_qty_sign` | ✅ | BR-CHEM-007 |
| `type='out' ⇒ ref_sample_id NOT NULL` | `ck_txn_out_sample` | ✅ | BR-CHEM-025, OQ#3 — **enforce ở DB** (CHECK làm được) |
| `type='adjust' ⇒ note NOT NULL` | `ck_txn_adjust_note` | ✅ | BR-CHEM-016, OQ#4 |
| `recheck_date <= expiry_date` | `ck_lot_date_order` | ✅ | BR-CHEM-006 |
| base_unit khớp measurement_group | composite FK `fk_chem_baseunit` | ✅ | BR-CHEM-026 — đảm bảo group denormalized luôn đúng |
| `input_unit` cùng nhóm với base_unit | ❌ DB không có FK tới `chemicals` từ txn | ⚠️ **app layer** | BR-CHEM-028. Lý do: `chemical_transactions` chỉ FK tới `chemical_lots`, không trực tiếp tới `chemicals.measurement_group`. App phải validate `units(input_unit).measurement_group == chemicals(lot.chemical_id).measurement_group` trước khi INSERT → 422 `UNIT_GROUP_MISMATCH`. (Có thể thêm trigger nếu QA yêu cầu enforce DB-level, nhưng app validate đủ + rẻ hơn.) |
| `qty_base` không bao giờ âm khi concurrent out | `CHECK (qty_base>=0)` + row-lock app | ✅ + ⚠️ | NFR-CONCUR-CHEM-001. CHECK là lưới an toàn cuối; chính enforce qua `SELECT ... FOR UPDATE` (xem §7). |
| không trùng (name+cas) khi cas NULL | partial unique index (xem §4) | ✅ | BR-CHEM-002 — UNIQUE thường bỏ qua NULL nên cần partial index riêng |

> **Quyết định enforce BR-CHEM-028 ở app layer** (không trigger DB) là cố ý: tránh trigger phức tạp cho lookup chéo bảng, và app cần kiểm tra trước để trả mã lỗi nghiệp vụ `UNIT_GROUP_MISMATCH` rõ ràng (FR-CHEM-005 A2b / FR-CHEM-006 A1b). CHECK base_unit↔group ở `chemicals` đã chặn nguồn gốc sai nhóm.

---

## 4. Index strategy

```sql
-- ===== chemicals =====
-- FK + phạm vi RBAC theo phòng ban (BR-CHEM-018) — lọc danh sách thường xuyên (FR-CHEM-004)
CREATE INDEX idx_chemicals_department    ON chemicals(department_id);
-- lọc theo trạng thái active/inactive
CREATE INDEX idx_chemicals_status        ON chemicals(status);
-- tìm theo CAS (FR-CHEM-004 search)
CREATE INDEX idx_chemicals_cas           ON chemicals(cas_no) WHERE cas_no IS NOT NULL;
-- tìm theo tên (ILIKE) — trigram cho search "q" (FR-CHEM-004); cần pg_trgm
CREATE INDEX idx_chemicals_name_trgm     ON chemicals USING gin (name gin_trgm_ops);
-- partial unique: chặn trùng (dept,name) khi cas_no IS NULL (UNIQUE thường bỏ qua NULL) — BR-CHEM-002
CREATE UNIQUE INDEX uq_chemicals_dept_name_nullcas
    ON chemicals(department_id, name) WHERE cas_no IS NULL;
-- FK base_unit phục vụ join units (đã có composite FK, thêm index cho join nhanh)
CREATE INDEX idx_chemicals_base_unit     ON chemicals(base_unit);

-- ===== chemical_lots =====
-- FK chemical_id — liệt kê lô theo hóa chất + FEFO (FR-CHEM-002/006)
CREATE INDEX idx_lots_chemical           ON chemical_lots(chemical_id);
-- FEFO + tìm lô sắp hết hạn cho CRON-6 (FR-CHEM-006/012): còn tồn, hết hạn sớm lên đầu
--   partial: chỉ index lô CÒN TỒN (cron + FEFO chỉ quan tâm qty_base>0) → index nhỏ, nhanh
CREATE INDEX idx_lots_expiry_active
    ON chemical_lots(expiry_date) WHERE qty_base > 0;
-- CRON-6 quét recheck_date tới hạn (FR-CHEM-012) — chỉ lô còn tồn
CREATE INDEX idx_lots_recheck_active
    ON chemical_lots(recheck_date) WHERE qty_base > 0;
-- lọc lô theo trạng thái kiểm tra lại (cảnh báo xuất lô fail — FR-CHEM-006)
CREATE INDEX idx_lots_recheck_result     ON chemical_lots(recheck_result) WHERE recheck_result IS NOT NULL;
CREATE INDEX idx_lots_price_unit         ON chemical_lots(price_unit);

-- ===== chemical_transactions =====
-- FK lot_id — lịch sử giao dịch theo lô (FR-CHEM-009)
CREATE INDEX idx_txn_lot                 ON chemical_transactions(lot_id);
-- lọc theo mẫu (FR-CHEM-009 AC3, báo cáo theo đề tài FR-CHEM-014) — chỉ giao dịch out có mẫu
CREATE INDEX idx_txn_ref_sample          ON chemical_transactions(ref_sample_id) WHERE ref_sample_id IS NOT NULL;
-- lọc theo người thực hiện (báo cáo tiêu hao theo người FR-CHEM-014)
CREATE INDEX idx_txn_by_user             ON chemical_transactions(by_user);
-- lọc theo loại + thời gian (lịch sử, Excel theo khoảng ngày FR-CHEM-009/013)
CREATE INDEX idx_txn_type_at             ON chemical_transactions(type, at DESC);
-- COMPOSITE: query pattern phổ biến nhất — lịch sử 1 lô theo thời gian giảm dần (FR-CHEM-009 AC1)
CREATE INDEX idx_txn_lot_at              ON chemical_transactions(lot_id, at DESC);
-- Excel/báo cáo theo khoảng thời gian toàn hệ thống (FR-CHEM-013/014)
CREATE INDEX idx_txn_at                  ON chemical_transactions(at DESC);

-- ===== chemical_recheck_records =====
CREATE INDEX idx_recheck_lot             ON chemical_recheck_records(lot_id, checked_at DESC);

-- ===== chemical_notification_dedup =====
-- UNIQUE(lot_id, kind, milestone_days, fire_date) đã tạo composite index — đủ cho lookup chống trùng.
```

**Cần extension:** `pg_trgm` cho `idx_chemicals_name_trgm` (search tên). Nếu KH không muốn trgm, fallback `CREATE INDEX ... (lower(name))` + `ILIKE 'x%'` prefix-only. → Bật `CREATE EXTENSION IF NOT EXISTS pg_trgm;`.

**Lý do từng index (tóm tắt):**
- Lọc thời gian giao dịch: `idx_txn_at`, `idx_txn_type_at`, `idx_txn_lot_at` (NFR-PERF-CHEM-002, Excel FR-CHEM-013).
- Theo `chemical_id`: `idx_lots_chemical` (liệt kê lô + FEFO).
- Theo `lot_id`: `idx_txn_lot`, `idx_txn_lot_at` (lịch sử lô).
- Theo `department_id`: `idx_chemicals_department` (RBAC scope BR-CHEM-018).
- Theo `ref_sample_id`: `idx_txn_ref_sample` (báo cáo theo mẫu/đề tài).
- Lô sắp hết hạn cho CRON-6: `idx_lots_expiry_active`, `idx_lots_recheck_active` (partial `qty_base>0` — FR-CHEM-012 AC4 không nhắc lô hết tồn).

> Không over-index: KHÔNG index `unit_price`/`currency`/`is_expired` (không dùng trong WHERE chọn lọc cao). Quy mô ~40 user, 50K giao dịch → không cần partition.

---

## 5. Seed data — bảng `units` (tối thiểu, BR-CHEM-029)

Base unit mỗi nhóm = đơn vị nhỏ nhất (factor_to_base = 1): **mg** (mass), **mL** (volume), **unit** (count).

```sql
INSERT INTO units (code, label, measurement_group, factor_to_base) VALUES
    -- mass (base = mg)
    ('mg',   'Miligam',   'mass',   1),
    ('g',    'Gam',       'mass',   1000),
    ('kg',   'Kilogam',   'mass',   1000000),
    -- volume (base = mL)
    ('mL',   'Mililit',   'volume', 1),
    ('L',    'Lit',       'volume', 1000),
    -- count (base = unit)
    ('unit', 'Đơn vị',    'count',  1),
    ('vien', 'Viên',      'count',  1),
    ('ong',  'Ống',       'count',  1);
```

> **Ghi chú count:** 'vien'/'ong'/'unit' đều factor=1 — chúng KHÔNG quy đổi lẫn nhau theo hệ số (1 viên ≠ 1 ống về mặt vật lý). Với nhóm count, khuyến nghị mỗi hóa chất chọn đúng 1 đơn vị count làm base và chỉ dùng đơn vị đó (app layer nên hạn chế đổi đơn vị trong nhóm count, hoặc coi mọi đơn vị count cùng base là "đơn vị đếm trừu tượng"). **Điểm cần Tech Lead/BA xác nhận** (xem §8). Nếu KH cần phân biệt viên/ống không quy đổi → mỗi hóa chất count chỉ một đơn vị, factor=1, app cấm đổi đơn vị nhóm count.

---

## 6. Traceability — Map bảng/cột → FR/BR

| Bảng / Cột | FR | BR |
|------------|----|----|
| `units` (toàn bộ) | FR-CHEM-001/005/006/008/013/014 | BR-CHEM-026, 028, 029 |
| `units.factor_to_base` | quy đổi đơn vị | BR-CHEM-029, NFR-CORRECT-CHEM-002 |
| `chemicals` (CRUD) | FR-CHEM-001 | BR-CHEM-001, 002, 012, 018 |
| `chemicals.base_unit` + `measurement_group` (composite FK) | FR-CHEM-001 | BR-CHEM-001, 003, 026, 028 |
| `chemicals.reorder_threshold` | FR-CHEM-010 | BR-CHEM-019 |
| `chemicals.status` | FR-CHEM-001 (vô hiệu hóa) | BR-CHEM-004 |
| `chemicals.hazard_code` + `attachments(owner_type='chemical')` | FR-CHEM-003 | BR-CHEM-013 |
| `chemical_lots` | FR-CHEM-002 | BR-CHEM-005, 006, 012 |
| `chemical_lots.qty_base` | FR-CHEM-008 (tồn) | BR-CHEM-009, 011, 026 |
| `chemical_lots.unit_price/price_unit/currency` | FR-CHEM-005 (nhập giá), 008/013/014 (giá trị tồn) | BR-CHEM-022, 023, 030 |
| `chemical_lots.recheck_result/recheck_date` | FR-CHEM-011 | BR-CHEM-020, 024 |
| `chemical_lots.expiry_date/is_expired/coa_file_key` | FR-CHEM-002, 012 | BR-CHEM-006, 021 |
| `chemical_transactions` (type=in) | FR-CHEM-005 | BR-CHEM-007, 008, 011, 014, 027 |
| `chemical_transactions` (type=out) | FR-CHEM-006 | BR-CHEM-009, 010, 014, 020, 024, 025, 027, 028 |
| `chemical_transactions` (type=adjust) | FR-CHEM-007 | BR-CHEM-016 |
| `chemical_transactions.qty_base/base_unit + qty_input/input_unit` | FR-CHEM-005/006/008/013 | BR-CHEM-026, 027, 028 |
| `chemical_transactions.balance_after` | FR-CHEM-005/006/008/009 | BR-CHEM-011, 015 |
| `chemical_transactions.ref_sample_id` (CHECK out NOT NULL) | FR-CHEM-006 | BR-CHEM-025 |
| `chemical_transactions.warning_override + note` | FR-CHEM-006/007 | BR-CHEM-016, 024 |
| `chemical_transactions.correlation_id` | tất cả (audit trace) | BR-CHEM-012, NFR-OBS-CHEM-001 |
| immutable (không UPDATE/DELETE route) | FR-CHEM-009 AC2 | BR-CHEM-015, NFR-AUDIT-CHEM-001 |
| `chemical_recheck_records` | FR-CHEM-011 | BR-CHEM-012, 020, 024 |
| `chemical_notification_dedup` | FR-CHEM-012 | BR-CHEM-021 |
| INSERT `audit_logs` (mọi thao tác) | tất cả FR | BR-CHEM-012, NFR-AUDIT-CHEM-001 |
| INSERT `notifications` | FR-CHEM-010/012 | BR-CHEM-019, 021 |

---

## 7. Ghi chú cho dev (BẮT BUỘC đọc) — transaction & concurrency

**FR-CHEM-005/006/007 + BR-CHEM-014 + NFR-CONCUR-CHEM-001:** ghi giao dịch và cập nhật `qty_base` của lô PHẢI atomic + row-lock.

### Mẫu ghi giao dịch out (chống race condition trừ tồn)

```python
# Trong 1 DB transaction (SQLAlchemy session.begin()):
async with session.begin():
    # 1. LOCK lô — chặn 2 request xuất cùng lô chạy song song (BR-CHEM-014, AC5)
    lot = await session.execute(
        select(ChemicalLot)
        .where(ChemicalLot.id == lot_id)
        .with_for_update()          # → SELECT ... FOR UPDATE
    )
    lot = lot.scalar_one()

    # 2. Validate nhóm đo (BR-CHEM-028) — app layer, trước khi tính
    #    units[input_unit].measurement_group == chemical.measurement_group
    #    else: raise 422 UNIT_GROUP_MISMATCH

    # 3. Quy đổi qty_input → qty_base (NUMERIC(18,6), KHÔNG float — dùng Decimal)
    qty_base = (Decimal(qty_input)
                * units[input_unit].factor_to_base
                / units[lot.base_unit_of_chemical].factor_to_base)

    # 4. Kiểm tra tồn (BR-CHEM-009) — so theo base unit
    if qty_base > lot.qty_base:
        raise HTTP 422 INSUFFICIENT_STOCK   # rollback, tồn không đổi

    # 5. Tính balance_after + INSERT giao dịch + UPDATE lô
    balance_after = lot.qty_base - qty_base
    session.add(ChemicalTransaction(..., balance_after=balance_after, ...))
    lot.qty_base = balance_after            # UPDATE trong cùng txn

    # 6. INSERT audit_logs (action=CHEMICAL_TXN_OUT, correlation_id)
    # commit tự động khi thoát begin(); lỗi → rollback toàn bộ (AC5/atomic)
```

**Nguyên tắc bắt buộc:**
1. **Luôn `SELECT ... FOR UPDATE` trên `chemical_lots`** trước khi đọc `qty_base` để tính → tuần tự hóa các giao dịch trên cùng lô. CHECK `qty_base >= 0` là lưới an toàn cuối nếu logic sai.
2. **Dùng `Decimal` (Python) / `NUMERIC` (DB)** xuyên suốt — KHÔNG `float`. Quy đổi: `qty_base = qty_input * factor(input) / factor(base)`. Round-trip phải đúng tuyệt đối ở NUMERIC(18,6) (NFR-CORRECT-CHEM-002).
3. **Một transaction DB** bao trọn: INSERT giao dịch + UPDATE `lot.qty_base` + INSERT `audit_logs`. Lỗi giữa chừng → rollback all (FR-CHEM-005 AC5, FR-CHEM-006 AC5).
4. **Tạo lô + giao dịch nhập đầu tiên** (UC-CHEM-01) nên gói chung 1 transaction nguyên tử (FR-CHEM-002 luồng chính #4).
5. **Cảnh báo xuất lô fail/quá hạn** (FR-CHEM-006 A2/A8/A9): nếu `recheck_result='fail'` HOẶC `expiry_date < today` và request chưa kèm `confirm_warning=true` → trả 422 `WARNING_NEEDS_CONFIRM` (KHÔNG ghi giao dịch). Khi có `confirm_warning=true` → set `warning_override=true` + ghi `note` (lý do) vào giao dịch & `audit_logs.detail`.
6. **Reorder threshold** (FR-CHEM-010): sau khi commit giao dịch out/adjust, tính tổng `qty_base` các lô của hóa chất; nếu `< reorder_threshold` và chưa có notification "đang mở" → INSERT `notifications` (BR-CHEM-019 chống spam). Có thể chạy ngoài transaction chính (best-effort, không rollback giao dịch nếu notify lỗi).
7. **Immutable:** KHÔNG tạo route PUT/PATCH/DELETE cho `chemical_transactions` (NFR-AUDIT-CHEM-001). Sửa sai → tạo giao dịch `adjust`.
8. **Cập nhật `recheck_result`/`recheck_date` của lô** khi ghi `chemical_recheck_records` (FR-CHEM-011) — cũng trong transaction; ghi audit `CHEMICAL_RECHECK`.
9. **CRON-6** (FR-CHEM-012): acquire Redis lock trước; quét lô `qty_base > 0` có `expiry_date`/`recheck_date` tới mốc 30/15/7 ngày; INSERT `chemical_notification_dedup` (ON CONFLICT DO NOTHING nhờ UNIQUE) → nếu insert thành công thì INSERT `notifications`; nếu conflict thì skip (chống trùng BR-CHEM-021).

---

## 8. Điểm cần Tech Lead chú ý (review trước APPROVED)

1. **D4 — kiểu tiền `NUMERIC(14,2)` (không BIGINT):** lệch rule global "tiền VNĐ = BIGINT đồng". Lý do: SRS chốt cứng `unit_price NUMERIC(14,2)` + có `currency` đa tệ + đơn giá có thể lẻ thập phân theo đơn vị (VND/g). Cần xác nhận chấp nhận ngoại lệ này (đã ghi rõ trade-off).
2. **BR-CHEM-028 enforce ở app layer** (không trigger DB): `input_unit` cùng nhóm với `base_unit` được validate ở service. CHECK base_unit↔group ở `chemicals` chặn nguồn gốc. Nếu QA/security yêu cầu defense-in-depth ở DB → bổ sung trigger (chưa thêm để giữ schema đơn giản).
3. **Nhóm count (§5):** 'vien'/'ong'/'unit' cùng factor=1 nhưng không quy đổi lẫn nhau về vật lý. Cần BA/KH xác nhận: mỗi hóa chất count chỉ dùng đúng 1 đơn vị count làm base + app cấm đổi đơn vị trong nhóm count (tránh hiểu nhầm "1 viên = 1 ống").
4. **OPEN QUESTIONS #6/#7/#8 chưa chốt** (async Excel threshold, giới hạn file CoA/MSDS, người phụ trách nhận cảnh báo) — không ảnh hưởng ERD lõi này, nhưng #8 ảnh hưởng logic chọn `user_id` khi INSERT `notifications` (FR-CHEM-010/012). Schema đã sẵn sàng cho cả 2 phương án.
5. **Bảng dùng chung cần có trước:** `users`, `departments`, `samples`, `attachments`, `audit_logs`, `notifications` (M7/M1). Migration M2 phải chạy SAU migration M7 (auth/org) và M1 (samples). Nếu M1 chưa xong, FK `ref_sample_id → samples(id)` sẽ fail → cần thứ tự migration đúng.
6. **`attachments.owner_type` cho CoA:** ERD core dùng `attachments` polymorphic cho MSDS (owner_type='chemical'). CoA hiện lưu `coa_file_key` trực tiếp trên `chemical_lots` (đơn giản, 1 CoA/lô). Nếu cần nhiều file CoA/lô → chuyển sang `attachments(owner_type='chem_lot')`. Đã ghi cả 2 hướng trong ERD.

---

## 9. Migration & Rollback

```
-- [ MIGRATION FILE NAME ] (Alembic)
-- <revision>_m2_chemical_inventory.py  (depends_on: M7 auth/org + M1 samples)
-- Thứ tự CREATE: units → chemicals → chemical_lots → chemical_transactions
--               → chemical_recheck_records → chemical_notification_dedup
--               → indexes → seed units

-- [ ROLLBACK PLAN ] (downgrade) — drop ngược thứ tự FK:
DROP TABLE IF EXISTS chemical_notification_dedup CASCADE;
DROP TABLE IF EXISTS chemical_recheck_records   CASCADE;
DROP TABLE IF EXISTS chemical_transactions      CASCADE;
DROP TABLE IF EXISTS chemical_lots              CASCADE;
DROP TABLE IF EXISTS chemicals                  CASCADE;
DROP TABLE IF EXISTS units                      CASCADE;
-- KHÔNG drop extension pgcrypto/pg_trgm (dùng chung toàn hệ thống).

-- [ DATA DEPENDENCIES ]
-- Seed TRƯỚC: units (8 dòng) — bắt buộc trước khi tạo bất kỳ chemical nào.
-- Phụ thuộc bảng có sẵn: users, departments (M7); samples (M1);
--                        attachments, audit_logs, notifications (dùng chung).
```

### Existing table changes
**KHÔNG có ALTER bảng đã tồn tại.** ERD core (`01-demo-scope.md`) mô tả `chemicals`/`chemical_lots`/`chemical_transactions` ở dạng đơn giản (unit VARCHAR, qty NUMERIC(14,4)) — đây là phiên bản **chưa implement**, contract này là bản chuẩn thay thế theo SRS v1.2 (OQ#1..#5). **Cần cập nhật ERD master** (`01-demo-scope.md` mục C — M2) cho khớp:
- `chemicals`: bỏ `unit VARCHAR`; thêm `base_unit`, `measurement_group`, `reorder_threshold`, `status`, audit fields.
- `chemical_lots`: `qty NUMERIC(14,4)` → `qty_base NUMERIC(18,6)`; thêm `unit_price/price_unit/currency/recheck_result/is_expired`.
- `chemical_transactions`: thêm `qty_base/base_unit/qty_input/input_unit`, `warning_override`, `correlation_id`; `ref_sample_id` NOT NULL khi out.
- Thêm bảng mới: `units`, `chemical_recheck_records`, `chemical_notification_dedup`.

→ Đề nghị Tech Lead cập nhật ERD master sau khi APPROVED contract này.

---

*Hết Contract M2 Schema v1.0. Tuân thủ: NUMERIC không float, FK rõ ON DELETE, index mọi FK + query pattern, rollback plan đầy đủ, traceability FR/BR. Chờ `/contract` gate APPROVED trước khi `feature-builder` implement.*
