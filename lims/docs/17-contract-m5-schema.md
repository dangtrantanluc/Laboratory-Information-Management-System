# Contract — M5 Schema: Quản lý Thiết bị & Hiệu chuẩn (Equipment & Calibration)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M5 — Equipment & Calibration (thiết bị §6.4 / liên kết chuẩn đo lường §6.5 / kiểm soát hồ sơ §8.4)
**Tài liệu:** Database Schema Contract (DDL + Index + Seed + Traceability)
**Version:** 1.0 | **Ngày:** 20/06/2026 | **Author:** schema-designer agent
**Stack:** PostgreSQL 15+, FastAPI + SQLAlchemy/Alembic
**Nguồn chân lý:** `16-srs-m5-equipment.md` (SRS M5 — 11 FR, 14 BR, 9 NFR; §7 ghi chú schema-designer dòng 639-649), `08-contract-m7-schema.md` (bảng dùng chung users/departments/attachments/audit_logs/notifications; quy ước D1-D11), `14-contract-m3-schema.md` (đồng bộ phong cách gần nhất: immutable record, danh mục, index, vòng đời migration)
**Status:** DRAFT — chờ `/contract` gate / Tech Lead review

---

## 0. Quyết định thiết kế chính (đọc trước) — đồng bộ tuyệt đối M7/M1/M2/M4/M3

| # | Quyết định | Lý do |
|---|-----------|-------|
| D1 | **PK = UUID `DEFAULT gen_random_uuid()`** cho cả 3 bảng nghiệp vụ M5 (`equipments`, `calibration_records`, `equipment_notification_dedup`). | CONSTRAINT-4 / BR-EQP-014 (không lộ ID tuần tự) + đồng bộ M7 D1 / M3 D1. `id` thật UUID; `equipments.code` mới là định danh dùng ngoài. |
| D2 | **ENUM = CHECK constraint trên VARCHAR**, KHÔNG native PG ENUM. Áp cho `equipments.status`, `equipments.calibration_cycle_unit`, `calibration_records.result`, `equipment_notification_dedup.milestone_days`. | Đồng bộ M7 D2 / M3 D2: ALTER TYPE khó rollback trong Alembic. |
| D3 | **KHÔNG có vòng FK** trong M5. `equipments` 1→n `calibration_records` (FK 1 chiều). `equipments.next_due_date` denormalize (cột thường, KHÔNG FK tới calibration record gần nhất) — đồng bộ BR-EQP-008. → Thứ tự CREATE tuyến tính, không cần ALTER phá vòng (KHÁC M7/M3). | SRS §7 (`equipments.next_due_date` denormalize = next_due của lần gần nhất). Lưu giá trị DATE thay FK để CRON-5/cảnh báo/lọc chạy nhanh + tránh vòng FK. App đảm bảo nhất quán trong transaction (FR-EQP-008). |
| D4 | **Chu kỳ hiệu chuẩn lưu trên TỪNG thiết bị**: `calibration_cycle_value INT NULL CHECK(>0)` + `calibration_cycle_unit VARCHAR NULL CHECK(month\|year)`. Cả 2 NULL = thiết bị KHÔNG thuộc diện hiệu chuẩn (không nhắc/không badge quá hạn). | OQ#1 default + ASSUMPTION-2 + BR-EQP-004/010. Mỗi thiết bị một chu kỳ riêng; thiết bị không hiệu chuẩn để NULL. Tách value+unit (thay tổng số tháng) để hiển thị đúng "12 tháng" / "1 năm" theo cách KH cấu hình. |
| D5 | **`calibration_records` IMMUTABLE — enforce DB-LEVEL bằng trigger BEFORE UPDATE/DELETE** (KHÁC M3 dùng app-only cho version). | CONSTRAINT-1 / BR-EQP-007 / NFR-INTEG-EQP-001 / NFR-AUDIT-EQP-001 (§8.4 VILAS — hồ sơ hiệu chuẩn là bằng chứng truy xuất nguồn gốc). SRS §7 dòng 641 + §6.4/§6.5 **khuyến nghị rõ trigger DB chặn UPDATE/DELETE** (đồng bộ `audit_logs` append-only M7 D8). Mạnh hơn app-only: chống cả sửa trực tiếp DB. App KHÔNG expose route PATCH/DELETE; trigger là lưới an toàn cuối. |
| D6 | **`equipments.code` UNIQUE + bất biến** (BR-EQP-014). UNIQUE enforce DB (`uq_equip_code`); bất biến enforce app-layer (422 `CODE_IMMUTABLE`). `id` UUID không lộ tuần tự. | CONSTRAINT-4 / BR-EQP-014 + đồng bộ M3 (`documents.code`) / M2. Mã sinh app-layer `<TB>-<MAPHONG>-<seq>` (OQ — định dạng cấu hình); UNIQUE là lưới chống trùng (retry nếu race — FR-EQP-003 A1). |
| D7 | **`next_due_date` cho phép override** (lưu cột trên cả `equipments` và `calibration_records`). App mặc định tính = `calibrated_at` + chu kỳ; cho sửa có lý do nếu cert ghi khác (OQ#1 default). KHÔNG CHECK liên cột (next_due vs calibrated) — override hợp lệ. | ASSUMPTION-3 / BR-EQP-006 + đề bài "next_due_date cho phép override". `calibration_records.next_due_date NOT NULL` (mỗi lần hiệu chuẩn phải có ngày kế tiếp); `equipments.next_due_date NULL` (NULL khi chưa có lần hiệu chuẩn nào). |
| D8 | **CRON-5 idempotency = bảng `equipment_notification_dedup`** (đồng bộ `chemical_notification_dedup` M2 / `hr_notification_dedup` M4) thay vì unique index trên `notifications` hay cột cờ trên `equipments`. | BR-EQP-011 + SRS §7 dòng 643 + đề bài "tạo equipment_notification_dedup cho đồng bộ". Cùng pattern M2/M4 → feature-builder tái dùng logic CRON dedup. UNIQUE(equipment_id, milestone_days, fire_date) chống gửi trùng mốc; gửi cho cả người phụ trách + trưởng nhóm vẫn idempotent theo thiết bị×mốc×ngày. |
| D9 | **Soft-delete thiết bị = `deleted_at TIMESTAMPTZ NULL`** + `status='retired'` (ngưng sử dụng). KHÔNG hard-delete thiết bị đã có lần hiệu chuẩn (§8.4). | SRS §7 dòng 649 + audit fields rule global. `calibration_records.equipment_id` FK RESTRICT → DB chặn xóa cứng thiết bị còn hồ sơ hiệu chuẩn (giữ hồ sơ §8.4). `deleted_at` cho soft-delete; `status=retired` cho "ngưng sử dụng" (2 khái niệm khác nhau, xem §3). |
| D10 | **File qua `attachments` polymorphic (M7 D9)** — `owner_type='equipment'` (tài liệu thiết bị: hướng dẫn/ảnh) + `owner_type='calibration'` (CoC/cert). M5 KHÔNG lưu file_key trực tiếp; KHÔNG tạo bảng file riêng. | CONSTRAINT-6 / BR-EQP-012 + đồng bộ M3 D10. Whitelist `'equipment'`/`'calibration'` ĐÃ có trong M7 (`attachments.owner_type` — 08-contract-m7-schema dòng 293, đã chạy migration `1718870400001`) → **M5 KHÔNG ALTER attachments**. |
| D11 | **`responsible_user_id` (người phụ trách)** = cột FK→users NULL trên `equipments`, **KHÔNG phải vai trò RBAC**. Phải thuộc cùng phòng ban thiết bị (BR-EQP-013) — enforce app-layer (422 `RESPONSIBLE_NOT_IN_DEPARTMENT`), KHÔNG CHECK liên bảng. | SRS §2.3 + BR-EQP-013. Người phụ trách nhận CRON-5 (BR-EQP-011). So 2 phòng (user.department_id vs equipment.department_id) là lookup nghiệp vụ → app-layer, giống M1/M3 tách-quyền app-layer. |

> **Audit fields (rule global):** `equipments` có vòng đời cập nhật → `created_at`/`updated_at` + `created_by`/`updated_by UUID REFERENCES users(id)` + `deleted_at` (soft-delete, D9). `calibration_records` là **bản ghi bất biến append-only** → chỉ `created_by` (người ghi) + `created_at`; KHÔNG `updated_at`/`updated_by`/`deleted_at` (không sửa/không xóa — D5). `equipment_notification_dedup` là bảng kỹ thuật chống trùng cron → chỉ `created_at` (không cặp created/updated by — đồng bộ `chemical_notification_dedup` M2).

---

## 1. ERD chi tiết M5 (ASCII)

```
┌─────────────────────────────────────────────────────────────────────┐
│ BẢNG DÙNG CHUNG (M7 — KHÔNG tạo lại trong migration M5)               │
├─────────────────────────────────────────────────────────────────────┤
│ users(id UUID PK, role, department_id, ...)   ← FK người dùng         │
│   → equipments.responsible_user_id (người phụ trách, nhận CRON-5)     │
│   → equipments.created_by/updated_by ; calibration_records.created_by │
│ departments(id UUID PK, lead_user_id FK→users NULL, ...)              │
│   → equipments.department_id (RBAC scope, BR-EQP-003)                 │
│   → đọc lead_user_id để gửi CRON-5 (trưởng nhóm — BR-EQP-011)         │
│ attachments(id, owner_type, owner_id, file_key, ...)                  │
│   → owner_type ∈ {'equipment','calibration'} (whitelist ĐÃ có M7)    │
│   → tài liệu TB: owner_type='equipment', owner_id=equipments.id (D10) │
│   → CoC/cert:    owner_type='calibration', owner_id=calib_record.id   │
│ audit_logs(id, user_id, action, resource, resource_id,               │
│            correlation_id, ip, at, detail JSONB)  ← INSERT mọi thao tác│
│ notifications(id, user_id, type, title, body, ref_type, ref_id, ...)  │
│   → CRON-5 type='CALIBRATION_DUE', ref_type='equipment', ref_id=eq.id │
│ roles_permissions: equipment:* / calibration:* CẦN SEED BỔ SUNG ở M5 │
│   (M7 mới có equipment:manage cho admin/leader — xem §5, §8)          │
└─────────────────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────────────────────┐
        │  equipments  (THIẾT BỊ §6.4 — vùng chứa 0..n lần hiệu chuẩn)  │
        │  id                     UUID PK                                │
        │  code                   VARCHAR(64) UNIQUE NOT NULL (TB-HOA-7) │ ◄─ BR-EQP-014
        │  name                   VARCHAR(255) NOT NULL                  │   bất biến app
        │  location               VARCHAR(255) NULL                      │
        │  department_id          UUID FK→departments(RESTRICT) NOT NULL │ ◄─ RBAC scope
        │  responsible_user_id    UUID FK→users(SET NULL) NULL           │ ◄─ người phụ trách
        │  purchase_date          DATE NULL                              │   (CRON-5, D11)
        │  status                 VARCHAR(12) CHECK                      │
        │     (active|maintenance|broken|retired)  DEFAULT 'active'      │ ◄─ BR-EQP-002
        │  calibration_cycle_value INT NULL CHECK(>0)                    │ ◄─ chu kỳ (D4)
        │  calibration_cycle_unit  VARCHAR(8) CHECK(month|year) NULL     │   cả 2 NULL =
        │  next_due_date          DATE NULL  (denormalize lần gần nhất)  │   không hiệu chuẩn
        │  note                   TEXT NULL                              │ ◄─ BR-EQP-008 (D3)
        │  created_by/updated_by  FK→users ; created_at/updated_at       │
        │  deleted_at             TIMESTAMPTZ NULL  (soft-delete, D9)    │
        └───┬───────────────────────────────────────────────────────────┘
            │ 1
            │ N  equipment_id (FK RESTRICT — giữ hồ sơ §8.4, D9)
            ▼
        ┌──────────────────────────────────────────────────────────────┐
        │  calibration_records  (LẦN HIỆU CHUẨN §6.4/§6.5 — IMMUTABLE)  │ ◄─ D5
        │  id              UUID PK                                       │   trigger DB chặn
        │  equipment_id    UUID FK→equipments(RESTRICT) NOT NULL         │   UPDATE/DELETE
        │  calibrated_at   DATE NOT NULL  (≤ today — BR-EQP-005)         │
        │  provider        VARCHAR(255) NULL  (text bản đầu — OQ#4)      │
        │  result          VARCHAR(8) CHECK(pass|fail) NOT NULL          │ ◄─ BR-EQP-006
        │  next_due_date   DATE NOT NULL  (tự tính, cho override — D7)   │
        │  cert_file_key   VARCHAR(512) NULL  (MinIO — xem ghi chú D10)  │
        │  note            TEXT NULL                                     │
        │  created_by      UUID FK→users(RESTRICT) NOT NULL  (người ghi) │
        │  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()            │
        │  (KHÔNG updated_at/updated_by/deleted_at — bất biến append-only)│
        └───────────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────────────────────┐
        │  equipment_notification_dedup  (CRON-5 idempotency — D8)      │
        │  id              UUID PK                                       │   đồng bộ
        │  equipment_id    UUID FK→equipments(CASCADE) NOT NULL          │   chemical_
        │  kind            VARCHAR(20) CHECK(CALIBRATION_DUE) NOT NULL   │   notification_
        │  milestone_days  SMALLINT CHECK(30|15|7) NOT NULL             │   dedup (M2)
        │  fire_date       DATE NOT NULL                                 │
        │  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()            │
        │  UNIQUE(equipment_id, milestone_days, fire_date)              │ ◄─ chống trùng mốc
        └──────────────────────────────────────────────────────────────┘
```

### Quan hệ & quyết định không-vòng-FK (KHÁC M7/M3)

```
equipments 1 ──< calibration_records      (FK equipment_id → equipments RESTRICT)
equipments 1 ──< equipment_notification_dedup (FK equipment_id → equipments CASCADE)

KHÔNG vòng FK: equipments.next_due_date là DATE denormalize (BR-EQP-008, D3),
KHÔNG FK trỏ tới "calibration_record gần nhất". App cập nhật next_due_date trong
transaction ghi hiệu chuẩn (FR-EQP-006/008) = next_due của MAX(calibrated_at).
→ Thứ tự CREATE tuyến tính: equipments → calibration_records →
  equipment_notification_dedup → trigger immutable → indexes → (seed tùy chọn).
```

### Bảng dùng chung tham chiếu (KHÔNG tạo lại — sở hữu M7)

| Bảng | Sở hữu | M5 dùng để |
|------|--------|-----------|
| `users(id, role, department_id)` | M7 | FK `responsible_user_id` (equipments), `created_by`/`updated_by` (equipments), `created_by` (calibration_records); đọc `department_id` kiểm BR-EQP-013 |
| `departments(id, lead_user_id)` | M7 | FK `equipments.department_id` (RBAC scope BR-EQP-003); đọc `lead_user_id` gửi CRON-5 cho trưởng nhóm (BR-EQP-011) |
| `attachments(owner_type, owner_id, file_key)` | M7 | tài liệu thiết bị (`owner_type='equipment'`, `owner_id=equipments.id`); CoC/cert (`owner_type='calibration'`, `owner_id=calibration_records.id`) — D10. Whitelist ĐÃ có. |
| `audit_logs` | M7 | INSERT mọi thao tác M5 (BR-EQP-014, §6.4/§8.4): `EQUIPMENT_CREATE/UPDATE/ATTACH`, `CALIBRATION_RECORD`, `CRON_CALIBRATION_REMINDER` |
| `notifications` | M7 | CRON-5 INSERT type=`CALIBRATION_DUE`, ref_type='equipment', ref_id=equipments.id (BR-EQP-011) |
| `roles_permissions` | M7 | `equipment:*`/`calibration:*` — M7 mới seed `equipment:manage` cho admin/leader. **M5 PHẢI seed bổ sung** (xem §5 + §8) vì leader=👁 chỉ xem, staff=ghi phòng mình, accountant=read only |

---

## 2. DDL đầy đủ — thứ tự tuyến tính (không vòng FK) + trigger immutable

> Migration viết raw SQL (`op.execute`) đồng bộ phong cách M7/M1/M2/M4/M3. **Prereq:** `pgcrypto` (gen_random_uuid); bảng `users`, `departments`, `attachments`, `audit_logs`, `notifications` (M7) PHẢI tồn tại trước (M7→M1→M2→M4→M3→M5). **`attachments.owner_type` whitelist ĐÃ có `'equipment'`/`'calibration'` (M7) → M5 KHÔNG ALTER.** **Thứ tự CREATE bắt buộc:** `equipments` → `calibration_records` → `equipment_notification_dedup` → trigger immutable trên `calibration_records` → indexes → seed `roles_permissions` (equipment:*/calibration:*).

```sql
-- ============================================================
-- SCHEMA: m5-equipment-calibration (Equipments, Calibration Records, Cron Dedup)
-- Feature: Quản lý Thiết bị & Hiệu chuẩn — §6.4 thiết bị / §6.5 liên kết chuẩn /
--          §8.4 kiểm soát hồ sơ (LIMS 17025)
-- Designer: schema-designer agent | Date: 2026-06-20
-- Prereq: pgcrypto; bảng users/departments/attachments/audit_logs/notifications
--         (M7) đã tồn tại. attachments.owner_type whitelist ĐÃ có
--         'equipment' + 'calibration' (M7) → M5 KHÔNG ALTER.
-- Thứ tự CREATE: equipments → calibration_records → equipment_notification_dedup
--              → trigger immutable (calibration_records) → indexes
--              → seed roles_permissions (equipment:*/calibration:*)
-- Thứ tự migration tổng thể: M7 → M1 → M2 → M4 → M3 → M5 (file này).
-- KHÔNG vòng FK (D3) → thứ tự tuyến tính, không ALTER phá vòng (KHÁC M7/M3).
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()
-- pg_trgm đã bật ở M7 (dùng cho GIN trgm name/code)

-- ------------------------------------------------------------
-- [ NEW TABLE 1 ] equipments — thiết bị §6.4 (FR-EQP-001..005, 008, 010)
--   Vùng chứa 0..n lần hiệu chuẩn. next_due_date denormalize = lần gần nhất (D3, BR-EQP-008).
--   chu kỳ NULL = thiết bị KHÔNG diện hiệu chuẩn (D4, BR-EQP-010).
-- ------------------------------------------------------------
CREATE TABLE equipments (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code                    VARCHAR(64)  NOT NULL,                  -- 'TB-HOA-007' (BR-EQP-014) bất biến app, không lộ tuần tự
    name                    VARCHAR(255) NOT NULL,
    location                VARCHAR(255) NULL,                      -- vị trí đặt thiết bị
    department_id           UUID         NOT NULL,                  -- phòng sở hữu (RBAC scope, BR-EQP-003)
    responsible_user_id     UUID         NULL,                      -- người phụ trách (CRON-5, D11); cùng phòng app-check
    purchase_date           DATE         NULL,
    status                  VARCHAR(12)  NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'maintenance', 'broken', 'retired')), -- BR-EQP-002
    calibration_cycle_value INT          NULL
        CHECK (calibration_cycle_value IS NULL OR calibration_cycle_value > 0), -- BR-EQP-004
    calibration_cycle_unit  VARCHAR(8)   NULL
        CHECK (calibration_cycle_unit IS NULL OR calibration_cycle_unit IN ('month', 'year')), -- D4
    next_due_date           DATE         NULL,                      -- denormalize next_due của lần hiệu chuẩn gần nhất (BR-EQP-008)
    note                    TEXT         NULL,
    created_by              UUID         NOT NULL,
    updated_by              UUID         NULL,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
    deleted_at              TIMESTAMPTZ  NULL,                      -- soft-delete (D9); thiết bị có hồ sơ KHÔNG hard-delete

    CONSTRAINT uq_equip_code     UNIQUE (code),
    CONSTRAINT fk_equip_dept     FOREIGN KEY (department_id)       REFERENCES departments(id) ON DELETE RESTRICT,
    CONSTRAINT fk_equip_resp     FOREIGN KEY (responsible_user_id) REFERENCES users(id)       ON DELETE SET NULL, -- người phụ trách rời/disable → để NULL, không hỏng thiết bị
    CONSTRAINT fk_equip_created  FOREIGN KEY (created_by)          REFERENCES users(id)       ON DELETE RESTRICT,
    CONSTRAINT fk_equip_updated  FOREIGN KEY (updated_by)          REFERENCES users(id)       ON DELETE RESTRICT,
    -- chu kỳ value & unit phải đi cùng nhau: cả 2 NULL (không diện hiệu chuẩn) hoặc cả 2 NOT NULL
    CONSTRAINT ck_equip_cycle_pair CHECK (
        (calibration_cycle_value IS NULL AND calibration_cycle_unit IS NULL)
        OR (calibration_cycle_value IS NOT NULL AND calibration_cycle_unit IS NOT NULL)
    )
);
COMMENT ON TABLE  equipments IS 'Thiết bị §6.4 (FR-EQP-001..005). Vùng chứa 0..n calibration_records. code bất biến (BR-EQP-014, app); next_due_date denormalize = next_due của lần hiệu chuẩn gần nhất (BR-EQP-008, NFR-INTEG-EQP-001). Chu kỳ NULL = không diện hiệu chuẩn (BR-EQP-010).';
COMMENT ON COLUMN equipments.next_due_date IS 'Denormalize (D3): = next_due_date của calibration_record có MAX(calibrated_at). NULL khi chưa có lần hiệu chuẩn. App cập nhật trong transaction ghi hiệu chuẩn (FR-EQP-008). Dùng cho CRON-5 + badge cảnh báo + lọc (NFR-PERF).';
COMMENT ON COLUMN equipments.status IS 'Tình trạng vận hành (BR-EQP-002): active/maintenance/broken/retired. KHÁC cảnh báo hiệu chuẩn (badge tính runtime từ next_due_date + result lần gần nhất — FR-EQP-010).';
COMMENT ON COLUMN equipments.responsible_user_id IS 'Người phụ trách (D11) — THUỘC TÍNH dữ liệu, không phải vai trò RBAC. Phải cùng phòng thiết bị (BR-EQP-013, app-check). Nhận CRON-5 (BR-EQP-011).';
COMMENT ON COLUMN equipments.deleted_at IS 'Soft-delete (D9). Thiết bị có ≥1 calibration_record KHÔNG hard-delete (FK RESTRICT giữ hồ sơ §8.4); dùng deleted_at hoặc status=retired.';

-- ------------------------------------------------------------
-- [ NEW TABLE 2 ] calibration_records — lần hiệu chuẩn §6.4/§6.5 (FR-EQP-006..009)
--   IMMUTABLE (D5, CONSTRAINT-1, BR-EQP-007): trigger DB chặn UPDATE/DELETE.
--   CoC/cert gắn qua attachments(owner_type='calibration', owner_id=this.id) — D10.
-- ------------------------------------------------------------
CREATE TABLE calibration_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id    UUID         NOT NULL,                          -- thiết bị (BR-EQP-001)
    calibrated_at   DATE         NOT NULL,                          -- ngày hiệu chuẩn (≤ today — BR-EQP-005, app)
    provider        VARCHAR(255) NULL,                              -- đơn vị hiệu chuẩn, text bản đầu (OQ#4)
    result          VARCHAR(8)   NOT NULL
        CHECK (result IN ('pass', 'fail')),                        -- BR-EQP-006
    next_due_date   DATE         NOT NULL,                          -- tự tính = calibrated_at + chu kỳ; cho override (D7, BR-EQP-006)
    cert_file_key   VARCHAR(512) NULL,                              -- MinIO key CoC/cert (xem ghi chú D10 — nguồn chính qua attachments)
    note            TEXT         NULL,
    created_by      UUID         NOT NULL,                          -- người ghi bản ghi hiệu chuẩn
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    -- KHÔNG updated_at/updated_by/deleted_at: bản ghi BẤT BIẾN append-only (D5, §8.4)

    CONSTRAINT fk_cal_equipment FOREIGN KEY (equipment_id) REFERENCES equipments(id) ON DELETE RESTRICT, -- giữ hồ sơ §8.4 (D9)
    CONSTRAINT fk_cal_created   FOREIGN KEY (created_by)   REFERENCES users(id)      ON DELETE RESTRICT
);
COMMENT ON TABLE  calibration_records IS 'Lần hiệu chuẩn §6.4/§6.5 (FR-EQP-006..009). BẤT BIẾN (D5, BR-EQP-007, §8.4): trigger DB chặn UPDATE/DELETE + KHÔNG route PATCH/DELETE. Đính chính = bản ghi mới (FR-EQP-007). next_due tự tính (cho override D7); CoC/cert qua attachments owner_type=calibration (D10).';
COMMENT ON COLUMN calibration_records.next_due_date IS 'Ngày hiệu chuẩn kế tiếp = calibrated_at + chu kỳ thiết bị (BR-EQP-006). NOT NULL: mỗi lần hiệu chuẩn phải có ngày kế tiếp. Cho override thủ công (D7) nếu cert ghi khác.';
COMMENT ON COLUMN calibration_records.cert_file_key IS 'MinIO key của CoC/cert (tiện tra nhanh 1 file chính). Nguồn ĐẦY ĐỦ file đính kèm qua attachments(owner_type=calibration, owner_id=this.id) — D10. Để NULL nếu file chỉ lưu attachments.';

-- ------------------------------------------------------------
-- [ NEW TABLE 3 ] equipment_notification_dedup — CRON-5 chống trùng mốc (D8, BR-EQP-011)
--   Đồng bộ chemical_notification_dedup (M2) / hr_notification_dedup (M4).
-- ------------------------------------------------------------
CREATE TABLE equipment_notification_dedup (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id    UUID         NOT NULL,
    kind            VARCHAR(20)  NOT NULL
        CHECK (kind IN ('CALIBRATION_DUE')),                       -- chỉ 1 loại bản đầu (mở rộng nếu thêm cron)
    milestone_days  SMALLINT     NOT NULL
        CHECK (milestone_days IN (30, 15, 7)),                     -- mốc nhắc (BR-EQP-011)
    fire_date       DATE         NOT NULL,                          -- ngày CRON-5 chạy gửi mốc này
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT fk_eqdedup_equipment FOREIGN KEY (equipment_id) REFERENCES equipments(id) ON DELETE CASCADE, -- dedup theo thiết bị, xóa cứng dedup khi thiết bị bị xóa cứng (hiếm)
    -- chống gửi trùng: mỗi thiết bị × mỗi mốc × mỗi ngày chỉ 1 lần (BR-EQP-011 idempotent)
    CONSTRAINT uq_eqdedup_eq_ms_date UNIQUE (equipment_id, milestone_days, fire_date)
);
COMMENT ON TABLE equipment_notification_dedup IS 'Chống trùng CRON-5 (D8, BR-EQP-011) — đồng bộ chemical_notification_dedup (M2) / hr_notification_dedup (M4). 1 dòng/(thiết bị, mốc, ngày). Gửi cho cả người phụ trách + trưởng nhóm vẫn idempotent theo thiết bị×mốc×ngày (cron INSERT dòng dedup trước → nếu UNIQUE violation thì đã gửi). Cho phép prune.';

-- ------------------------------------------------------------
-- [ TRIGGER ] calibration_records IMMUTABLE — chặn UPDATE/DELETE ở DB-level (D5, §8.4)
--   Defense-in-depth: + KHÔNG expose route PATCH/DELETE ở app (BR-EQP-007).
--   Đồng bộ tinh thần audit_logs append-only (M7 D8). KHÁC M3 (M3 dùng app-only cho version)
--   — M5 chọn DB-level vì hồ sơ hiệu chuẩn là bằng chứng VILAS §6.5/§8.4 (NFR-INTEG/AUDIT-EQP-001).
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_calibration_records_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'calibration_records is immutable (ISO/IEC 17025 §8.4): % not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER calibration_records_no_update
    BEFORE UPDATE ON calibration_records
    FOR EACH ROW EXECUTE FUNCTION trg_calibration_records_immutable();

CREATE TRIGGER calibration_records_no_delete
    BEFORE DELETE ON calibration_records
    FOR EACH ROW EXECUTE FUNCTION trg_calibration_records_immutable();
```

> **Ghi chú `cert_file_key` (D10):** cột `cert_file_key` trên `calibration_records` là **tiện ích** (quick-link 1 file CoC chính, hiển thị nhanh trong timeline FR-EQP-009 không cần JOIN). **Nguồn đầy đủ** file CoC/cert vẫn qua `attachments(owner_type='calibration', owner_id=calibration_record.id)` — cho phép nhiều file/lần hiệu chuẩn. Nếu Tech Lead muốn 1 nguồn duy nhất (KISS) → BỎ `cert_file_key`, chỉ dùng `attachments` (đồng bộ tuyệt đối M3 D10 không lưu file_key trên bảng). Xem §8 điểm 4 — **cần Tech Lead chốt**.

---

## 3. CHECK constraints & toàn vẹn quan trọng — tổng hợp

| Quy tắc | Constraint | DB enforce? | Ghi chú |
|---------|-----------|-------------|---------|
| `equipments.code` UNIQUE, bất biến | `uq_equip_code` + app | ✅ (UNIQUE) / ⚠️ (bất biến app) | BR-EQP-014. Đổi code → 422 `CODE_IMMUTABLE` (app). Không lộ tuần tự (UUID id, D6). |
| `equipments.status` ∈ 4 giá trị | CHECK | ✅ | BR-EQP-002. active/maintenance/broken/retired. |
| chu kỳ value > 0 | CHECK `calibration_cycle_value` | ✅ | BR-EQP-004. 422 `INVALID_CALIBRATION_CYCLE` (app validate trước). |
| chu kỳ unit ∈ {month,year} | CHECK `calibration_cycle_unit` | ✅ | BR-EQP-004, D4. |
| chu kỳ value & unit đi cùng nhau | `ck_equip_cycle_pair` | ✅ | D4: cả 2 NULL (không diện hiệu chuẩn) hoặc cả 2 NOT NULL. Tránh nửa cấu hình. |
| `department_id` ∈ phòng tồn tại | `fk_equip_dept → departments(id)` RESTRICT | ✅ | BR-EQP-003 (RBAC scope). |
| `result` ∈ {pass,fail} | CHECK `calibration_records.result` | ✅ | BR-EQP-006. 422 `INVALID_CALIBRATION_RESULT`. |
| `calibration_records.next_due_date` NOT NULL | NOT NULL | ✅ | D7: mỗi lần hiệu chuẩn phải có ngày kế tiếp (tự tính/override). |
| `dedup.milestone_days` ∈ {30,15,7} | CHECK | ✅ | BR-EQP-011, D8. |
| `dedup.kind` = CALIBRATION_DUE | CHECK | ✅ | D8. |
| chống trùng CRON-5 mốc | `uq_eqdedup_eq_ms_date (equipment_id, milestone_days, fire_date)` | ✅ **DB-LEVEL (D8)** | BR-EQP-011 idempotent. Cron INSERT dedup trước; UNIQUE violation = đã gửi. |
| **calibration_records bất biến** | **trigger `calibration_records_no_update/delete`** | ✅ **DB-LEVEL (D5)** | **CONSTRAINT-1 / BR-EQP-007 / §8.4 VILAS — bất biến quan trọng nhất M5.** + KHÔNG route PATCH/DELETE (app). KHÁC M3 (app-only). |
| giữ hồ sơ hiệu chuẩn (không xóa cứng thiết bị) | `fk_cal_equipment` RESTRICT | ✅ | D9, §8.4. Thiết bị có hồ sơ → hard-delete bị chặn; dùng deleted_at/retired. |
| `calibrated_at` ≤ hôm nay | — | ⚠️ **app-layer** | BR-EQP-005. 422 `INVALID_CALIBRATION_DATE`. CHECK (calibrated_at <= CURRENT_DATE) KHÔNG dùng (CURRENT_DATE không immutable trong CHECK PG) → app validate. |
| `next_due_date` = calibrated_at + chu kỳ | — | ⚠️ **app-layer (D7)** | BR-EQP-006. App tính mặc định; cho override (không CHECK liên cột để cho override hợp lệ). |
| `equipments.next_due_date` = lần gần nhất | — | ⚠️ **app-layer (D3)** | BR-EQP-008 / NFR-INTEG-EQP-001. App cập nhật trong transaction (FR-EQP-008) = next_due của MAX(calibrated_at); ghi bổ sung lần cũ KHÔNG ghi đè. |
| người phụ trách cùng phòng thiết bị | — | ⚠️ **app-layer (D11)** | BR-EQP-013. 422 `RESPONSIBLE_NOT_IN_DEPARTMENT`. So user.department_id vs equipment.department_id. |
| chu kỳ bắt buộc khi ghi hiệu chuẩn (nếu không override next_due) | — | ⚠️ **app-layer** | BR-EQP-006. 422 `CALIBRATION_CYCLE_REQUIRED` (FR-EQP-006 A1). |
| RBAC scope phòng + leader 👁 + accountant read | — | ⚠️ **app-layer** | BR-EQP-003 (đọc roles_permissions M5). 403 `FORBIDDEN`. Xem §5 ma trận. |
| badge cảnh báo (quá hạn/sắp hạn/không đạt) | — | ⚠️ **app-layer (runtime)** | FR-EQP-010 / BR-EQP-009. Tính runtime từ next_due_date so CURRENT_DATE + result lần gần nhất (đủ nhanh ở 2,000 TB — NFR §647). KHÔNG khóa cứng (CONSTRAINT-3). |
| file loại whitelist + dung lượng | — | ⚠️ **app-layer** | BR-EQP-012. 422 `INVALID_FILE_TYPE`/`FILE_TOO_LARGE`. |
| immutable calibration (không route mutate) | — | ⚠️ **app-layer** (+ trigger DB) | BR-EQP-007. KHÔNG expose PATCH/DELETE; 405/403 `IMMUTABLE_RECORD`. |

> **Tinh thần đồng bộ M7/M1/M2/M3/M4:** CHECK DB giữ ràng buộc **giá trị** (enum, UNIQUE, cặp nhất quán `ck_equip_cycle_pair`) + bất biến QUAN TRỌNG (trigger immutable `calibration_records` như `audit_logs` M7 + UNIQUE dedup như M2). Logic nghiệp vụ phức (tính next_due, denormalize lần gần nhất, RBAC scope, badge, người phụ trách cùng phòng) enforce **app-layer** với mã lỗi rõ ràng — giống M1/M3/M4.

---

## 4. Index strategy

```sql
-- ===== equipments =====
-- uq_equip_code đã tạo unique index — tra/tìm theo mã (BR-EQP-014 không lộ tuần tự, FR-EQP-003)
CREATE INDEX idx_equip_department    ON equipments(department_id) WHERE deleted_at IS NULL;  -- FK + RBAC scope (BR-EQP-003)
CREATE INDEX idx_equip_status        ON equipments(status) WHERE deleted_at IS NULL;          -- lọc theo tình trạng (FR-EQP-004)
-- COMPOSITE: lọc phổ biến nhất (FR-EQP-004) phòng + tình trạng + RBAC scope — NFR-PERF-EQP-002
CREATE INDEX idx_equip_dept_status   ON equipments(department_id, status) WHERE deleted_at IS NULL;
-- CRON-5 + lọc quá hạn/sắp tới hạn: thiết bị diện hiệu chuẩn (chu kỳ ≠ NULL) sắp tới hạn
--   PARTIAL: chỉ thiết bị còn hạn theo dõi (next_due_date NOT NULL + chưa xóa) → index nhỏ, đúng query CRON-5/badge
CREATE INDEX idx_equip_next_due      ON equipments(next_due_date)
    WHERE next_due_date IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_equip_responsible   ON equipments(responsible_user_id) WHERE responsible_user_id IS NOT NULL; -- FK + "thiết bị tôi phụ trách" (CRON-5)
CREATE INDEX idx_equip_name_trgm     ON equipments USING gin (name gin_trgm_ops);  -- tìm theo tên (FR-EQP-004) — pg_trgm bật ở M7
CREATE INDEX idx_equip_code_trgm     ON equipments USING gin (code gin_trgm_ops);  -- tìm gần đúng theo mã (FR-EQP-004)

-- ===== calibration_records =====
-- COMPOSITE quan trọng nhất: lịch sử hiệu chuẩn theo thiết bị giảm dần + LẤY LẦN GẦN NHẤT (FR-EQP-008/009)
--   phục vụ cả timeline (FR-EQP-009) và tìm MAX(calibrated_at) cập nhật next_due (BR-EQP-008)
CREATE INDEX idx_cal_equip_date      ON calibration_records(equipment_id, calibrated_at DESC);
CREATE INDEX idx_cal_created_by      ON calibration_records(created_by);  -- FK + "ai ghi hiệu chuẩn" (audit/báo cáo)
-- (lọc theo result để tính badge "không đạt" thường đi kèm lần gần nhất → idx_cal_equip_date đủ;
--  KHÔNG thêm index riêng result — chọn lọc thấp, đã có composite theo equipment)

-- ===== equipment_notification_dedup =====
-- uq_eqdedup_eq_ms_date (equipment_id, milestone_days, fire_date) đã là composite index —
--   đủ cho CRON-5 kiểm "đã gửi (thiết bị, mốc, ngày) chưa" (BR-EQP-011). KHÔNG cần index thêm.
-- (tùy chọn dọn dữ liệu cũ theo fire_date — prune cron; index fire_date không cần ở quy mô này)
```

**Lý do nhóm index trọng yếu (theo yêu cầu):**
- **`equipments.code`** — `uq_equip_code` (unique): tra mã thiết bị là lookup chính, không lộ tuần tự (BR-EQP-014). Một index lo cả UNIQUE + lookup.
- **`equipments(department_id, status)`** — `idx_equip_dept_status` (composite, partial `deleted_at IS NULL`): query liệt kê/lọc phổ biến nhất (FR-EQP-004) luôn kèm RBAC scope phòng (BR-EQP-003) + lọc tình trạng. Đáp ứng NFR-PERF-EQP-002 (P95 < 500ms, không Sequential Scan). Giữ thêm `idx_equip_department`/`idx_equip_status` đơn cho query chỉ-1-chiều (vd báo cáo theo tình trạng toàn lab).
- **`equipments.next_due_date`** — `idx_equip_next_due` (PARTIAL `next_due_date IS NOT NULL AND deleted_at IS NULL`): chính cho **CRON-5** (quét thiết bị sắp tới hạn 30/15/7 ngày — FR-EQP-011) + **lọc quá hạn/sắp tới hạn** (FR-EQP-004/010). Partial giữ index nhỏ (bỏ thiết bị không diện hiệu chuẩn / đã xóa) — đúng yêu cầu đề bài "partial cho CRON-5 tìm thiết bị sắp tới hạn".
- **`calibration_records(equipment_id, calibrated_at DESC)`** — `idx_cal_equip_date` (composite): query nóng nhất bảng hiệu chuẩn — (a) timeline lịch sử giảm dần (FR-EQP-009); (b) tìm lần gần nhất `MAX(calibrated_at)` để cập nhật `equipments.next_due_date` (BR-EQP-008, FR-EQP-008) + tính badge "không đạt". Đáp ứng NFR-PERF-EQP-001 (ghi hiệu chuẩn P95 < 400ms). Đúng yêu cầu đề bài "calibration theo equipment_id + calibrated_at".
- **`uq_eqdedup_eq_ms_date`** (composite unique): vừa **enforce idempotent CRON-5** (BR-EQP-011, D8) vừa phục vụ truy vấn "đã gửi mốc này chưa" — index 2 trong 1 (như `uq_doc_one_approved` của M3).

> **Không over-index:** KHÔNG index `location`, `note`, `purchase_date`, `provider`, `calibration_records.result` (chọn lọc thấp / không dùng WHERE độc lập), `cert_file_key`, `equipment_notification_dedup.fire_date` (UNIQUE composite đã đủ). Quy mô ~2,000 thiết bị / ~20,000 bản ghi hiệu chuẩn (NFR §522) → KHÔNG cần partition; `equipment_notification_dedup` cho phép prune theo `fire_date` cũ. Badge cảnh báo tính runtime (NFR §647) — KHÔNG cần index/cờ riêng ở quy mô này.

---

## 5. Seed — roles_permissions (equipment:* / calibration:*) — BẮT BUỘC bổ sung ở M5

> **Khác M3:** M3 KHÔNG seed (quyền document:* đã đủ ở M7). **M5 PHẢI seed bổ sung** vì M7 §5.1/§5.2 mới có `equipment:manage` cho **admin** + **leader** (`('admin','equipment','manage','all')`, `('leader','equipment','manage','all')`) — KHÔNG phản ánh đúng ma trận M5 (leader = 👁 chỉ xem; staff = ghi phòng mình; accountant = read only). M5 seed bổ sung **idempotent `ON CONFLICT DO NOTHING`** (như M2 thêm `chemical:create` cho leader/staff) để khớp contract mà KHÔNG sửa migration M7.

> **Thứ tự seed:** chỉ `roles_permissions` (equipment:*/calibration:*). Trước đó cần INSERT `permissions` (resource×action) còn thiếu — M7 mới khai `('equipment','manage',...)`; M5 dùng resource/action mịn hơn (`equipment:read/create/update`, `calibration:create`) → phải INSERT `permissions` mới trước (FK `fk_rp_permission`). `equipments`/`calibration_records` là dữ liệu nghiệp vụ runtime — KHÔNG seed (vài thiết bị mẫu là tùy chọn, xem cuối §5).

### 5.1 Ma trận quyền M5 (chốt — phản ánh RBAC matrix demo-scope + quyết định đã chốt)

Quy ước scope: `all` = toàn lab · `department` = trong phòng ban user · `own` = chỉ dữ liệu cá nhân.
**Quyết định đã chốt áp vào seed:** (1) accountant = **read only** (M5 cho Kế toán XEM — theo đề bài "Kế toán XEM được M5 chỉ view"; ghi đè default-matrix "—" của SRS OQ#5); (2) leader = **read only** (👁 — matrix M5, KHÁC M3); (3) staff = **read toàn lab + ghi phòng mình** (OQ#2 default xem toàn lab); (4) admin = full.

| Vai trò | equipment:read | equipment:create | equipment:update | calibration:create | Ghi chú |
|---------|:--------------:|:----------------:|:----------------:|:------------------:|---------|
| **admin** | all | all | all | all | toàn quyền mọi phòng |
| **leader** | all | — | — | — | **👁 CHỈ XEM** (matrix M5, KHÁC M3 nơi leader ghi được) |
| **accountant** | all | — | — | — | **read only** (đề bài: Kế toán XEM được M5, chỉ view) |
| **staff** | all | department | department | department | xem toàn lab; CRUD + ghi hiệu chuẩn CHỈ phòng mình (BR-EQP-003); người phụ trách cùng phòng (BR-EQP-013) |

> `equipment:read` cấp `all` cho cả staff (OQ#2 default "staff xem toàn lab"). Nếu KH chốt OQ#2 = "staff chỉ xem phòng mình" → đổi staff `equipment:read` scope `department` (1 dòng seed). Mọi thay đổi default cần văn bản KH ("Verbal is Nothing").

### 5.2 Seed permissions (resource×action còn thiếu) — idempotent

```sql
-- M7 mới khai ('equipment','manage'). M5 dùng action mịn hơn → INSERT permissions mới
-- (FK fk_rp_permission yêu cầu (resource,action) tồn tại trong permissions trước khi gán).
INSERT INTO permissions (resource, action, description) VALUES
    ('equipment',   'read',   'Xem thiết bị / lịch sử hiệu chuẩn / cảnh báo'),
    ('equipment',   'create', 'Tạo thiết bị + đính kèm tài liệu thiết bị'),
    ('equipment',   'update', 'Sửa thiết bị / tình trạng / cấu hình chu kỳ hiệu chuẩn'),
    ('calibration', 'create', 'Ghi lần hiệu chuẩn (CoC + tự tính next_due)')
ON CONFLICT (resource, action) DO NOTHING;
```

### 5.3 Seed roles_permissions (ma trận §5.1) — idempotent

```sql
INSERT INTO roles_permissions (role, resource, action, scope) VALUES
    -- ===== ADMIN: full, scope all =====
    ('admin','equipment','read','all'),
    ('admin','equipment','create','all'),
    ('admin','equipment','update','all'),
    ('admin','calibration','create','all'),

    -- ===== LEADER (Ban lãnh đạo): CHỈ XEM (👁) — KHÁC M3 (leader KHÔNG ghi M5) =====
    ('leader','equipment','read','all'),

    -- ===== ACCOUNTANT (Kế toán): read only (đề bài: Kế toán XEM được M5) =====
    ('accountant','equipment','read','all'),

    -- ===== STAFF (KTV): xem toàn lab (OQ#2) + ghi phòng mình (BR-EQP-003) =====
    ('staff','equipment','read','all'),            -- xem toàn lab (OQ#2 default)
    ('staff','equipment','create','department'),   -- tạo thiết bị phòng mình
    ('staff','equipment','update','department'),   -- sửa/cấu hình chu kỳ phòng mình
    ('staff','calibration','create','department')  -- ghi hiệu chuẩn phòng mình
ON CONFLICT (role, resource, action) DO NOTHING;
```

> **Lưu ý quyền `equipment:manage` (M7) vs `equipment:read/create/update` (M5):** M7 đã seed `equipment:manage` (all) cho admin/leader. M5 chuyển sang action mịn (read/create/update + calibration:create). **Tech Lead chốt (§8 điểm 3):** (a) GIỮ `equipment:manage` cho admin (coarse) + thêm fine cho M5 — app dùng fine; HOẶC (b) coi `equipment:manage` của leader là dư thừa cần thu hồi (leader chỉ 👁). Khuyến nghị: **app RBAC guard chỉ kiểm action mịn của M5** (`equipment:read/create/update`, `calibration:create`); dòng `('leader','equipment','manage','all')` của M7 KHÔNG cấp quyền ghi M5 vì guard không kiểm action `manage`. Nếu muốn sạch → migration M5 có thể `DELETE FROM roles_permissions WHERE resource='equipment' AND action='manage'` (cân nhắc — xem §8).

### 5.4 (Tùy chọn) Seed vài thiết bị mẫu — KHÔNG bắt buộc

> Bản đầu **KHÔNG seed thiết bị** (dữ liệu nghiệp vụ runtime). Nếu cần demo: INSERT vài `equipments` (phụ thuộc có sẵn `departments` + `users` seed M7) với `created_by` = admin seed. Bỏ qua trong migration chính thức; để feature-builder/demo seed riêng nếu cần.

---

## 6. Traceability — Map bảng/cột → FR/BR SRS M5

| Bảng / Cột | FR | BR |
|------------|----|----|
| `equipments` (toàn bộ) | FR-EQP-001, 002, 003, 004, 005, 008, 010 | BR-EQP-001, 002, 003, 004, 006, 008, 010, 013, 014 |
| `equipments.code` (UNIQUE, bất biến app) | FR-EQP-003, 001 | BR-EQP-014 |
| `equipments.name` / `location` / `purchase_date` | FR-EQP-001, 002, 004 | BR-EQP-014 |
| `equipments.department_id` (FK RESTRICT) | FR-EQP-001, 004 | BR-EQP-003 (scope) |
| `equipments.responsible_user_id` (FK SET NULL) | FR-EQP-001, 011 | BR-EQP-011, 013 |
| `equipments.status` (CHECK 4 giá trị) | FR-EQP-001, 002 | BR-EQP-002 |
| `equipments.calibration_cycle_value/unit` (+ ck_equip_cycle_pair) | FR-EQP-005, 006 | BR-EQP-004, 006, 010 |
| `equipments.next_due_date` (denormalize) | FR-EQP-008, 010, 011 | BR-EQP-006, 008 |
| `calibration_records` (toàn bộ — IMMUTABLE) | FR-EQP-006, 007, 008, 009 | BR-EQP-001, 005, 006, 007, 008 |
| `calibration_records.calibrated_at` (≤today app) | FR-EQP-006 | BR-EQP-005 |
| `calibration_records.provider` | FR-EQP-006, 009 | (OQ#4) |
| `calibration_records.result` (CHECK pass/fail) | FR-EQP-006, 010 | BR-EQP-006, 009 |
| `calibration_records.next_due_date` (NOT NULL, override D7) | FR-EQP-006, 008 | BR-EQP-006 |
| `calibration_records.cert_file_key` + attachments(calibration) | FR-EQP-006, 009 | BR-EQP-012 |
| `calibration_records.created_by/created_at` (append-only) | FR-EQP-006, 009 | BR-EQP-007 |
| trigger `calibration_records_no_update/delete` (immutable) | FR-EQP-007 | BR-EQP-007 |
| `fk_cal_equipment` RESTRICT (giữ hồ sơ) | FR-EQP-007 | BR-EQP-007, 008 |
| `equipment_notification_dedup` (toàn bộ) | FR-EQP-011 | BR-EQP-009, 010, 011 |
| `uq_eqdedup_eq_ms_date` (idempotent CRON-5) | FR-EQP-011 | BR-EQP-011 |
| `idx_equip_next_due` (partial — CRON-5 + lọc quá hạn) | FR-EQP-010, 011 | BR-EQP-009, 010 |
| `idx_cal_equip_date` (lịch sử + lần gần nhất) | FR-EQP-008, 009 | BR-EQP-008 |
| FK `attachments` (owner_type='equipment'/'calibration') | FR-EQP-004, 006, 009 | BR-EQP-012 |
| INSERT `audit_logs` (mọi thao tác) | tất cả FR | BR-EQP-014 |
| INSERT `notifications` (CRON-5 CALIBRATION_DUE) | FR-EQP-011 | BR-EQP-011 |
| đọc `departments.lead_user_id` (gửi CRON-5 trưởng nhóm) | FR-EQP-011 | BR-EQP-011 |
| seed `roles_permissions` (equipment:*/calibration:*) | FR-EQP-001..006 | BR-EQP-003 |
| (badge cảnh báo — runtime từ next_due + result) | FR-EQP-010 | BR-EQP-009, 010 |

**Mapping điều khoản ISO/IEC 17025:**
- **§6.4 Thiết bị (cốt lõi M5):** nhận biết & hồ sơ thiết bị (`equipments` — code, status, người phụ trách, tài liệu qua attachments); trạng thái hiệu chuẩn & ngăn dùng thiết bị không phù hợp (`next_due_date` + badge runtime FR-EQP-010 + CRON-5 FR-EQP-011 — cảnh báo, KHÔNG khóa cứng OQ#3); hiệu chuẩn định kỳ (`calibration_cycle_*` + `next_due_date` FR-EQP-005/006/008).
- **§6.5 Liên kết chuẩn đo lường:** hiệu chuẩn có truy xuất nguồn gốc qua **CoC/cert** (`calibration_records.cert_file_key` + attachments owner_type=calibration — FR-EQP-006/009).
- **§8.4 Kiểm soát hồ sơ:** bản ghi hiệu chuẩn **bất biến** (trigger DB `calibration_records_no_update/delete` + KHÔNG route mutate — FR-EQP-007, BR-EQP-007, NFR-INTEG/AUDIT-EQP-001); giữ hồ sơ (FK RESTRICT chặn xóa cứng thiết bị có hồ sơ — D9); audit đầy đủ mọi thao tác (BR-EQP-014, `audit_logs`).

---

## 7. Ghi chú cho dev (BẮT BUỘC đọc) — revision, transaction, next_due, immutable, CRON-5

### 7.1 Revision & thứ tự migration
- **File:** `1718870400006_m5_equipment_calibration.py`. `revision = "1718870400006"`, `down_revision = "1718870400005"` (M3 Document Control).
- **Thứ tự tổng thể:** M7 (`...001`) → M1 (`...002`) → M2 (`...003`) → M4 (`...004`) → M3 (`...005`) → **M5 (`...006`)**. M5 phụ thuộc users/departments/attachments/audit_logs/notifications + permissions/roles_permissions (M7) — đã có.
- **KHÔNG vòng FK (D3)** → thứ tự CREATE tuyến tính, KHÔNG ALTER phá vòng (KHÁC M7/M3). Đơn giản hơn M3.
- **Model file:** tạo `app/models/equipment.py` (3 class: `Equipment`, `CalibrationRecord`, `EquipmentNotificationDedup`) theo style M3 (`document.py`); import vào `app/models/__init__.py` mục "--- M5: Equipment & Calibration ---" + thêm vào `__all__`.

### 7.2 Ghi lần hiệu chuẩn + tự tính next_due + cập nhật thiết bị (FR-EQP-006/008, BR-EQP-006/008) — CỐT LÕI
**NFR-INTEG-EQP-001:** ghi hiệu chuẩn PHẢI atomic; `equipments.next_due_date` luôn khớp lần gần nhất.
```python
async with session.begin():
    eq = (await session.execute(
        select(Equipment).where(Equipment.id == equipment_id).with_for_update()
    )).scalar_one()                                  # row-lock thiết bị → tuần tự hóa ghi cùng thiết bị

    # 1. RBAC: user có calibration:create scope department (phòng thiết bị) — BR-EQP-003 → else 403 FORBIDDEN
    # 2. validate calibrated_at <= today — BR-EQP-005 → else 422 INVALID_CALIBRATION_DATE
    # 3. tính next_due: nếu không override:
    #      cần eq.calibration_cycle_value/unit ≠ NULL — else 422 CALIBRATION_CYCLE_REQUIRED (BR-EQP-006)
    #      next_due = calibrated_at + (value tháng | value năm)   (dùng dateutil.relativedelta)
    #    nếu override (D7): dùng next_due_date người nhập + ghi lý do vào audit detail
    # 4. INSERT calibration_records (immutable — trigger DB chặn sửa sau)
    # 5. upload CoC MinIO + INSERT attachments(owner_type='calibration', owner_id=record.id) (D10)
    #    (+ set record.cert_file_key nếu giữ cột tiện ích — §8 điểm 4)
    # 6. cập nhật eq.next_due_date NẾU record là lần gần nhất:
    latest = (await session.execute(
        select(func.max(CalibrationRecord.calibrated_at))
        .where(CalibrationRecord.equipment_id == equipment_id)
    )).scalar_one()
    if record.calibrated_at >= latest:               # ghi bổ sung lần cũ KHÔNG ghi đè (BR-EQP-008)
        eq.next_due_date = record.next_due_date
    # 7. INSERT audit_logs action='CALIBRATION_RECORD' (+ correlation_id); badge cập nhật runtime (FR-010)
```
- **`equipments.next_due_date` = next_due của MAX(calibrated_at)** (BR-EQP-008): ghi bổ sung lần cũ (calibrated_at < lần gần nhất) KHÔNG ghi đè. NFR-INTEG-EQP-001: invariant check sau mỗi ghi.

### 7.3 Immutable calibration_records (D5, BR-EQP-007, CONSTRAINT-1, §8.4)
- **Trigger DB** `calibration_records_no_update/delete` chặn mọi UPDATE/DELETE (defense-in-depth — KHÁC M3 app-only). **App KHÔNG expose route PATCH/DELETE** `calibration_records/:id` (BR-EQP-007 — 405/403 `IMMUTABLE_RECORD`).
- Đính chính sai sót = **tạo bản ghi mới** (FR-EQP-007) + audit ghi lý do trong `detail`. (Tùy chọn cột `correction_of UUID FK→calibration_records` — SRS §7 OQ, KHÔNG đưa vào bản đầu để giữ đơn giản; đính chính truy vết qua audit + timeline.)
- **Hệ quả:** mọi cập nhật cột trên `calibration_records` (kể cả set `cert_file_key` sau khi tạo) PHẢI làm trong cùng INSERT — trigger chặn UPDATE sau. Nếu upload CoC tách bước → upload MinIO TRƯỚC, rồi INSERT record với `cert_file_key` đã có (không UPDATE sau).

### 7.4 CRON-5 nhắc trước hiệu chuẩn (FR-EQP-011, BR-EQP-010/011) — idempotent + Redis lock
- APScheduler trong app, **07:00 hằng ngày**, Redis lock (đồng bộ CRON-1..6 — CONSTRAINT-8). Chỉ in-app (C02).
- **Query thiết bị cần nhắc:** `next_due_date - CURRENT_DATE ∈ {30, 15, 7}` AND `calibration_cycle_value IS NOT NULL` (diện hiệu chuẩn — BR-EQP-010) AND `status NOT IN ('retired')` (OQ default bỏ retired; broken theo OQ) AND `deleted_at IS NULL`. Dùng `idx_equip_next_due` (partial).
- **Idempotent (D8):** với mỗi (thiết bị, mốc): INSERT `equipment_notification_dedup(equipment_id, kind='CALIBRATION_DUE', milestone_days, fire_date=CURRENT_DATE)` — nếu `uq_eqdedup_eq_ms_date` violation (đã gửi) → bỏ qua, KHÔNG gửi lại (BR-EQP-011). Nếu INSERT thành công → tạo `notifications` cho `responsible_user_id` + `departments.lead_user_id` (ref_type='equipment', ref_id=eq.id, type='CALIBRATION_DUE').
- **Không người phụ trách** → chỉ gửi trưởng nhóm; nếu cũng không có → log WARN, không lỗi job (BR-EQP-011, FR-EQP-011 A4).
- Audit `CRON_CALIBRATION_REMINDER` (số thông báo tạo). Redis lock giữ → instance khác bỏ qua (FR-EQP-011 A6).

### 7.5 File qua attachments (D10, BR-EQP-012, CONSTRAINT-6)
- Tài liệu thiết bị (FR-EQP-004): upload MinIO → INSERT `attachments(owner_type='equipment', owner_id=equipment.id, ...)`. CoC/cert (FR-EQP-006): `owner_type='calibration', owner_id=calibration_record.id`.
- App validate MIME thực + đuôi whitelist (PDF/DOCX/XLSX/PNG/JPG — OQ) + dung lượng (BR-EQP-012) trước khi lưu. `attachments.owner_type` whitelist `'equipment'`/`'calibration'` ĐÃ có ở M7 → **M5 KHÔNG ALTER attachments**.
- Tải file (FR-EQP-009): kiểm quyền (`equipment:read` + RBAC scope) → presigned URL MinIO → audit `CALIBRATION_DOWNLOAD`/`EQUIPMENT_ATTACH`.

### 7.6 Badge cảnh báo (FR-EQP-010, BR-EQP-009/010) — runtime, KHÔNG khóa cứng
- Tính **runtime** khi liệt kê/chi tiết (đủ nhanh ở 2,000 thiết bị — NFR §647): **quá hạn** = `next_due_date < CURRENT_DATE`; **sắp tới hạn** = `next_due_date - CURRENT_DATE ≤ 30`; **không đạt** = result lần hiệu chuẩn gần nhất = `fail` (đọc qua `idx_cal_equip_date`). Chỉ áp cho thiết bị diện hiệu chuẩn (chu kỳ ≠ NULL — BR-EQP-010); ẩn cảnh báo quá hạn cho `status=retired` (FR-EQP-010 A2).
- **CONSTRAINT-3:** KHÔNG khóa cứng — badge chỉ cảnh báo + khuyến nghị; KHÔNG chặn thao tác/luồng M1 (khóa cứng = CR). Bộ lọc "quá hạn / sắp tới hạn / không đạt" trong list (FR-EQP-004/010).

### 7.7 RBAC (BR-EQP-003) — app-layer (đọc M7 + §5)
- **Kế toán:** `equipment:read` all (đề bài: Kế toán XEM được M5, chỉ view); mọi endpoint ghi → 403.
- **Leader:** `equipment:read` all (👁 — KHÁC M3 nơi leader ghi được); mọi endpoint ghi M5 → 403 (FR-EQP-001 AC3, FR-EQP-006 AC6).
- **Staff:** `equipment:read` all (xem toàn lab — OQ#2 default); create/update/calibration:create scope `department` (ghi CHỈ phòng mình — BR-EQP-003); người phụ trách phải cùng phòng (BR-EQP-013, 422 `RESPONSIBLE_NOT_IN_DEPARTMENT`).
- **Admin:** full all.
- **Lưu ý `equipment:manage` (M7):** app guard kiểm action mịn M5 (`equipment:read/create/update`, `calibration:create`) — KHÔNG kiểm `manage`. Dòng `('leader','equipment','manage','all')` của M7 KHÔNG cấp quyền ghi M5 (xem §5.3 + §8 điểm 3).

### 7.8 Quy ước chung (đồng bộ M7/M1/M2/M3/M4)
- Mọi thao tác ghi kèm `correlation_id` vào `audit_logs` (NFR-AUDIT-EQP-001, NFR-OBS-EQP-001).
- Thông báo CRON-5 idempotent qua `equipment_notification_dedup` (D8) — KHÔNG dựa `idx_notif_ref` (M5 chọn bảng dedup riêng cho rõ mốc 30/15/7, đồng bộ M2/M4).
- KHÔNG expose endpoint sửa/xóa `calibration_records` (immutable).

---

## 8. Điểm cần Tech Lead chú ý (review trước APPROVED)

1. **KHÔNG vòng FK (D3) — đơn giản hơn M7/M3.** `equipments.next_due_date` là DATE denormalize (BR-EQP-008), KHÔNG FK trỏ "calibration gần nhất". App đảm bảo nhất quán trong transaction (§7.2) + invariant check (NFR-INTEG-EQP-001). **Cần xác nhận** chấp nhận denormalize (đánh đổi: nhanh cho CRON-5/badge/lọc, phải giữ nhất quán app-layer).
2. **`calibration_records` IMMUTABLE enforce DB-LEVEL bằng trigger (D5) — KHÁC M3.** M3 dùng app-only cho `document_versions`; M5 chọn **trigger DB** (đồng bộ `audit_logs` append-only M7 D8) vì hồ sơ hiệu chuẩn là bằng chứng VILAS §6.5/§8.4 (NFR-INTEG/AUDIT-EQP-001) — SRS §7 dòng 641 khuyến nghị rõ. **Cần Tech Lead xác nhận** lựa chọn DB-level (mạnh hơn, nhưng cản đính chính → đính chính = bản ghi mới, FR-EQP-007). Hệ quả: set `cert_file_key` phải trong INSERT (không UPDATE sau — §7.3).
3. **Quyền `equipment:manage` (M7) vs action mịn M5 (read/create/update + calibration:create).** M7 đã seed `equipment:manage` (all) cho **admin + leader**. M5 dùng action mịn để phân biệt leader=👁 vs staff=ghi-phòng-mình vs accountant=read. **Cần Tech Lead chốt:** (a) **khuyến nghị** — app guard chỉ kiểm action mịn M5; `equipment:manage` của M7 thành no-op cho M5 (không gây hại, giữ nguyên); HOẶC (b) migration M5 `DELETE FROM roles_permissions WHERE resource='equipment' AND action='manage'` để sạch (lưu ý: idempotent rollback). Khuyến nghị (a) — KHÔNG đụng seed M7.
4. **Cột `cert_file_key` trên `calibration_records` (D10) — GIỮ hay BỎ?** GIỮ = quick-link 1 CoC chính không cần JOIN attachments (tiện timeline FR-EQP-009); BỎ = đồng bộ tuyệt đối M3 (file CHỈ qua attachments, 1 nguồn). **Cần Tech Lead chốt.** Nếu GIỮ: set trong INSERT (trigger immutable chặn UPDATE sau). Đề bài SRS §7 dòng 641 + ERD ghi `cert_file_key (MinIO) NULL` → bản này GIỮ theo đề bài, đánh dấu nguồn đầy đủ vẫn là attachments.
5. **`accountant` XEM M5 (đề bài) vs matrix demo-scope "—" (SRS OQ#5).** Đề bài chốt "Kế toán XEM được M5 (chỉ view)" → seed `('accountant','equipment','read','all')`. SRS §2.3/OQ#5 default theo matrix = không truy cập. **Bản này theo ĐỀ BÀI (Kế toán read only).** Cần ghi vào biên bản KH xác nhận (mâu thuẫn matrix — "Verbal is Nothing").
6. **`status` (vận hành) vs `deleted_at` (soft-delete) vs badge cảnh báo — 3 khái niệm tách biệt (D9).** `status` ∈ active/maintenance/broken/retired (BR-EQP-002); `deleted_at` = soft-delete (ẩn khỏi danh sách); badge = tính runtime từ `next_due_date`/result (FR-EQP-010). Thiết bị quá hạn KHÔNG đổi `status` tự động (chỉ badge — không khóa cứng OQ#3). **Cần xác nhận** không gộp 3 khái niệm.
7. **`pg_trgm` cho GIN trgm name/code** đã bật ở M7 → M5 KHÔNG `CREATE EXTENSION pg_trgm` lại (chỉ `pgcrypto` cho gen_random_uuid, idempotent IF NOT EXISTS).
8. **OPEN QUESTIONS ảnh hưởng schema (SRS §8):** #1 (chu kỳ theo thiết bị + tự tính/override) → đã giải (D4 chu kỳ trên thiết bị; D7 next_due override); #2 (staff xem toàn lab) → seed `equipment:read` all (đổi 1 dòng nếu KH chốt khác); #3 (cảnh báo không khóa cứng) → runtime badge, KHÔNG schema khóa; #5 (Kế toán xem) → theo đề bài read only. Mọi thay đổi default cần văn bản KH.

---

## 9. Migration & Rollback

```
-- [ MIGRATION FILE NAME ] (Alembic)
-- 1718870400006_m5_equipment_calibration.py
--   revision = "1718870400006" ; down_revision = "1718870400005" (M3)
-- Thứ tự CREATE: equipments → calibration_records → equipment_notification_dedup
--              → trigger immutable (calibration_records) → indexes
--              → seed permissions (equipment:*/calibration:*) → seed roles_permissions
-- KHÔNG vòng FK → KHÔNG ALTER phá vòng (KHÁC M7/M3).

-- [ THỨ TỰ MIGRATION TỔNG THỂ ]
--   M7 (...001) → M1 (...002) → M2 (...003) → M4 (...004) → M3 (...005) → M5 (...006)
--   M5 phụ thuộc users/departments/attachments/audit_logs/notifications/permissions/
--   roles_permissions (M7) + đọc departments.lead_user_id (CRON-5).
--   M5 KHÔNG bị module nào phụ thuộc ngược (M6 chỉ đọc equipments runtime cho dashboard).

-- [ ROLLBACK PLAN ] (downgrade) — drop ngược thứ tự; gỡ trigger + function:
DROP TRIGGER IF EXISTS calibration_records_no_delete ON calibration_records;
DROP TRIGGER IF EXISTS calibration_records_no_update ON calibration_records;
DROP FUNCTION IF EXISTS trg_calibration_records_immutable();
DROP TABLE IF EXISTS equipment_notification_dedup CASCADE;
DROP TABLE IF EXISTS calibration_records          CASCADE;  -- trigger drop theo bảng (đã drop ở trên cho rõ)
DROP TABLE IF EXISTS equipments                   CASCADE;
-- Thu hồi seed M5 (idempotent — chỉ xóa dòng M5 thêm, KHÔNG đụng seed M7):
DELETE FROM roles_permissions WHERE (role, resource, action) IN (
    ('admin','equipment','read'), ('admin','equipment','create'), ('admin','equipment','update'),
    ('admin','calibration','create'),
    ('leader','equipment','read'),
    ('accountant','equipment','read'),
    ('staff','equipment','read'), ('staff','equipment','create'),
    ('staff','equipment','update'), ('staff','calibration','create')
);
DELETE FROM permissions WHERE (resource, action) IN (
    ('equipment','read'), ('equipment','create'), ('equipment','update'), ('calibration','create')
);
-- KHÔNG drop extension pgcrypto/pg_trgm (dùng chung M7).
-- KHÔNG drop/đụng users/departments/attachments/audit_logs/notifications (M7).

-- [ EXISTING TABLE CHANGES ]
-- M5 KHÔNG ALTER bảng M7. attachments.owner_type whitelist ('equipment','calibration')
--   ĐÃ có sẵn ở M7 (1718870400001 dòng 293) → KHÔNG breaking change.
-- M5 THÊM permissions + roles_permissions (equipment:*/calibration:*) — non-breaking
--   (idempotent ON CONFLICT DO NOTHING; M7 chỉ có equipment:manage coarse).

-- [ DATA DEPENDENCIES ]
-- Seed TRƯỚC (trong migration M5): permissions (equipment:read/create/update, calibration:create)
--   → roles_permissions (ma trận §5.3). KHÔNG seed thiết bị (runtime; mẫu tùy chọn).
-- Phụ thuộc bảng có sẵn (M7): users, departments(+lead_user_id), attachments,
--   audit_logs, notifications, permissions, roles_permissions.
-- Bảng phụ thuộc vào M5 (đọc runtime, KHÔNG FK): M6 báo cáo (số thiết bị theo tình trạng,
--   số quá hạn hiệu chuẩn từ equipments.next_due_date/status).
```

---

*Hết Contract M5 Schema v1.0. Tuân thủ: PK UUID gen_random_uuid, TIMESTAMPTZ, CHECK thay native ENUM, FK rõ ON DELETE (RESTRICT giữ hồ sơ §8.4 / SET NULL người phụ trách / CASCADE dedup), KHÔNG vòng FK (denormalize next_due — BR-EQP-008), trigger DB immutable calibration_records (§8.4 VILAS — như audit_logs M7), equipment_notification_dedup idempotent CRON-5 (như chemical/hr dedup M2/M4), index mọi FK + query pattern + GIN trgm tìm kiếm + partial next_due cho CRON-5 + composite calibration(equipment_id, calibrated_at DESC), seed bổ sung roles_permissions equipment:*/calibration:* (leader=👁, accountant=read, staff=ghi phòng — idempotent), rollback + thứ tự migration đầy đủ, traceability FR/BR. Đồng bộ tuyệt đối quy ước M7/M1/M2/M4/M3. Chờ `/contract` gate APPROVED trước khi feature-builder implement.*
</content>
</invoke>
