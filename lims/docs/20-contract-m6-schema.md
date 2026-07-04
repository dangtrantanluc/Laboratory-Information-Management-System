# Contract — M6 Schema: Báo cáo & Thống kê (Reporting & Analytics)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M6 — Báo cáo & Thống kê (module CUỐI, tầng TỔNG HỢP CHÉO — READ-ONLY)
**Tài liệu:** Database Schema Contract (ALTER nhẹ access_stats + Index + Traceability)
**Version:** 1.0 | **Ngày:** 20/06/2026 | **Author:** schema-designer agent
**Stack:** PostgreSQL 15+, FastAPI + SQLAlchemy/Alembic, Redis (cache)
**Nguồn chân lý:** `19-srs-m6-reporting.md` (FR-RPT-001..011, BR-RPT-001..014, §9.2), `08-contract-m7-schema.md` (D11 access_stats; index access_stats có sẵn), code thật `demo/lims-backend/app/models/access_stat.py` + `alembic/versions/1718870400001_m7_platform.py`
**Status:** DRAFT — chờ `/contract` gate / Tech Lead review

---

## 0. Tóm tắt quyết định (đọc trước)

| # | Quyết định | Lý do |
|---|-----------|-------|
| M6-D1 | **M6 KHÔNG tạo bảng nghiệp vụ mới, KHÔNG tạo bảng snapshot/tổng hợp.** Toàn bộ KPI/thống kê tính **runtime** từ bảng module nguồn + cache Redis. | SRS §1.2 OUT-OF-SCOPE (snapshot KPI / materialized view / data warehouse → CR). M6 là READ-ONLY aggregate (CONSTRAINT-2). |
| M6-D2 | **ALTER `access_stats`: ADD COLUMN `event_type VARCHAR(16)` (CHECK login\|page_view, NULL).** Bảng hiện có `id,user_id,path,method,status_code,ip,at` — KHÔNG có cột phân loại lượt đăng nhập vs xem trang. | Quyết định đã chốt #1: middleware ghi LOGIN + page_view, cần phân loại để đếm R15 (FR-RPT-007). Nullable → **non-breaking** với hàng cũ. |
| M6-D3 | **KHÔNG thêm cột `module`.** Dùng `path` sẵn có để suy ra module/trang (app-layer map prefix path → module). | `path` đã đủ để phân biệt trang chính (whitelist FR-RPT-009). Thêm `module` là denormalize thừa cho quy mô ~40 user; có thể derive từ path. Tránh phình schema. |
| M6-D4 | **Index mới phục vụ aggregate R15:** `(at, event_type)` (đếm theo kỳ + loại lượt truy cập) + `(event_type, at)`. Index `(user_id, at)` và `(at)` **đã có ở M7** → KHÔNG tạo lại. | FR-RPT-007/008, BR-RPT-004. SRS §9.2: lượt truy cập = access_stats + LOGIN. |
| M6-D5 | **KHÔNG bổ sung index trên bảng module nguồn** (samples/chemicals/equipments/...). Các module đã có index riêng cho query của chúng; M6 đếm/group qua các cột đã index (status, deadline_at, next_due_date, at). | CONSTRAINT-1 + nguyên tắc "không over-index". Nếu k6 (NFR-PERF-RPT-002) phát hiện Seq Scan → thêm index ở migration module tương ứng, KHÔNG ở M6. |
| M6-D6 | **R15 (thống kê truy cập hệ thống) map quyền = `audit:read`** (đã seed M7: chỉ admin/leader). KHÔNG seed permission mới. `report:business`/`report:finance` đã seed M7 đủ cho M6.1/M6.2. | BR-RPT-010 (R15 chỉ admin/leader — giám sát hành vi, đồng nghĩa quyền xem nhật ký). M7 đã có `audit:read` cho admin+leader. Tránh trùng quyền. |

> **Không có audit fields / soft-delete mới:** M6 không sở hữu entity nghiệp vụ. `access_stats` là bảng append-only high-volume (M7 D11) — dùng `user_id` + `at`, KHÔNG cặp created/updated, KHÔNG `deleted_at` (prune theo retention).

---

## 1. M6 dùng bảng nào để aggregate (xác nhận — SRS §9.2)

M6 **đọc trực tiếp** (ASSUMPTION-1) các bảng đã tồn tại; KHÔNG định nghĩa lại logic module nguồn (CONSTRAINT-1).

| Nguồn | Bảng (đã có) | Cột M6 dùng | KPI / Thống kê | FR |
|-------|--------------|-------------|----------------|----|
| M1 Mẫu | `samples` | `status`, `deadline_at`, `completed_at`, `received_at`, `department_id` | số mẫu theo trạng thái, overdue, theo thời gian | FR-RPT-001/002/003, BR-RPT-003 |
| M2 Hóa chất | `chemical_lots`, `chemicals`, `chemical_transactions` | lot: `expiry_date`, `recheck_date`; chemical: tồn/`reorder_threshold`; txn: `type='out'`, `qty_base`, `base_unit`, `measurement_group`, `at`, `department`, `unit_price` | lô sắp hết hạn, tồn thấp, tiêu hao theo nhóm đo | FR-RPT-001/002/004, BR-RPT-006/014 |
| M3 Tài liệu | `documents`/`document_versions`, `document_access_log` | version `status='review'`; dal: `action='download'`, `user_id`, `at` | tài liệu chờ duyệt; lượt tải file (R15) | FR-RPT-001/007, BR-RPT-004 |
| M4 Nhân sự/NCKH | `hr_profiles` | `next_salary_raise_date`, `contract_end_date` | nâng lương / hết hạn HĐ sắp tới hạn | FR-RPT-006, BR-RPT-007 |
| M5 Thiết bị | `equipments`, `calibration_records` | `next_due_date`, `status`, `department_id` | thiết bị quá hạn / sắp tới hạn hiệu chuẩn | FR-RPT-001, BR-RPT-008 |
| M7 Audit | `audit_logs` | `user_id`, `action` (LOGIN; CUD), `at` | lượt đăng nhập + lượt chỉnh sửa (R15) | FR-RPT-007, BR-RPT-004 |
| M7 Thông báo | `notifications` | `user_id`, `read_at IS NULL` | KPI thông báo chưa đọc | FR-RPT-001 |
| M7 Truy cập | **`access_stats`** (ALTER ở M6) | `user_id`, `path`, `event_type`(mới), `at` | lượt truy cập = page_view + login (R15) | FR-RPT-007/008/009, BR-RPT-004 |

> **Lượt truy cập (R15) = `access_stats` (page_view) + `audit_logs` action `LOGIN`** (hoặc `access_stats.event_type='login'` nếu middleware ghi cả login vào access_stats — chốt dev §4). **Lượt tải = `document_access_log.action='download'`.** **Lượt chỉnh sửa = action CUD trong `audit_logs`.** Nguồn đếm cố định (BR-RPT-004 / CONSTRAINT-4).

---

## 2. DDL — ALTER access_stats + Index mới

```sql
-- ============================================================
-- SCHEMA: m6-reporting (Báo cáo & Thống kê — READ-ONLY aggregate)
-- Feature: M6 LIMS 17025 — chỉ ALTER access_stats (event_type) + CREATE INDEX.
-- Designer: schema-designer agent | Date: 2026-06-20
-- Prereq: M7..M5 (revises 1718870400006). KHÔNG tạo bảng nghiệp vụ/snapshot mới.
-- Thứ tự tổng thể: M7 → M1 → M2 → M4 → M3 → M5 → M6 (file này).
-- ============================================================

-- ------------------------------------------------------------
-- [ EXISTING TABLE CHANGE ] access_stats: ADD event_type (M6-D2)
--   Bảng access_stats đã có (M7): id,user_id,path,method,status_code,ip,at.
--   Thiếu cột phân loại lượt đăng nhập vs xem trang → thêm event_type.
--   NULLABLE → NON-BREAKING (hàng cũ event_type=NULL; middleware mới luôn set).
-- ------------------------------------------------------------
ALTER TABLE access_stats
    ADD COLUMN event_type VARCHAR(16) NULL
        CHECK (event_type IS NULL OR event_type IN ('login', 'page_view'));

COMMENT ON COLUMN access_stats.event_type IS
    'Loại lượt truy cập (M6.3/R15): login = đăng nhập; page_view = xem trang chính. '
    'NULL = bản ghi cũ trước M6 (non-breaking). Middleware M6 luôn set (FR-RPT-009).';

-- ------------------------------------------------------------
-- [ INDEXES ] phục vụ aggregate R15 (M6-D4)
--   Đã có ở M7: idx_access_user_at (user_id, at DESC), idx_access_at (at DESC).
--   Thêm: đếm theo kỳ + phân loại event_type (FR-RPT-007 lượt truy cập/login).
-- ------------------------------------------------------------
-- Đếm lượt truy cập theo khoảng [from,to) + tách login/page_view (R15 tổng + theo loại)
CREATE INDEX idx_access_at_event   ON access_stats(at DESC, event_type);
-- Lọc nhanh theo loại sự kiện rồi theo thời gian (vd chỉ đếm 'login' trong kỳ)
CREATE INDEX idx_access_event_at   ON access_stats(event_type, at DESC) WHERE event_type IS NOT NULL;
```

> **KHÔNG có DDL nào khác.** Không thêm cột `module` (M6-D3). Không tạo bảng. Không index bảng module nguồn (M6-D5). Không seed permission mới (M6-D6).

---

## 3. Migration M6

```python
"""m6_reporting — Báo cáo & Thống kê (M6.3 R15 hạ tầng access_stats).

M6 READ-ONLY aggregate: KHÔNG tạo bảng nghiệp vụ/snapshot mới (SRS OUT-OF-SCOPE).
Chỉ:
  - ALTER access_stats ADD COLUMN event_type (login|page_view, NULL — non-breaking)
    để middleware M6 phân loại lượt đăng nhập vs xem trang (FR-RPT-009, BR-RPT-004).
  - CREATE INDEX (at,event_type) + (event_type,at) phục vụ thống kê truy cập R15
    (FR-RPT-007). Index (user_id,at)/(at) đã có ở M7 → KHÔNG tạo lại.

KHÔNG seed permission mới: report:business/report:finance đã seed ở M7;
R15 (thống kê truy cập hệ thống) map quyền audit:read (admin/leader) — đã có M7.

Revision ID: 1718870400007
Revises: 1718870400006 (M5 Equipment Calibration)
Create Date: 2026-06-20

Thứ tự migration tổng thể: M7 → M1 → M2 → M4 → M3 → M5 → M6 (file này).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1718870400007"
down_revision: Union[str, None] = "1718870400006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER access_stats: ADD event_type (non-breaking, nullable + CHECK) — M6-D2
    op.execute(
        """
        ALTER TABLE access_stats
            ADD COLUMN IF NOT EXISTS event_type VARCHAR(16) NULL
                CHECK (event_type IS NULL OR event_type IN ('login', 'page_view'));
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN access_stats.event_type IS
            'Loại lượt truy cập (M6.3/R15): login | page_view. NULL = bản ghi trước M6.';
        """
    )

    # Index aggregate R15 — (at,event_type) + (event_type,at) — M6-D4
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_access_at_event "
        "ON access_stats(at DESC, event_type);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_access_event_at "
        "ON access_stats(event_type, at DESC) WHERE event_type IS NOT NULL;"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_access_event_at;")
    op.execute("DROP INDEX IF EXISTS idx_access_at_event;")
    op.execute("ALTER TABLE access_stats DROP COLUMN IF EXISTS event_type;")
```

> **`alembic upgrade head` sạch:** chuỗi 1718870400001 → ...006 → **007** tuyến tính. `down_revision='1718870400006'` khớp head hiện tại. Cập nhật model `app/models/access_stat.py` thêm field `event_type` (Mapped[str | None], String(16)) để ORM đồng bộ.

### ROLLBACK PLAN
- `alembic downgrade 1718870400006` → DROP 2 index + DROP COLUMN event_type. An toàn vì cột nullable, không bảng nào FK tới nó, dữ liệu cũ không phụ thuộc.

### DATA DEPENDENCIES
- Phụ thuộc: M7 (access_stats, audit_logs, notifications, users, permissions/roles_permissions), M1–M5 (samples/chemicals/.../document_access_log/equipments/hr_profiles).
- Cần seed trước: KHÔNG — M6 không seed gì (quyền đã seed M7).

---

## 4. Ghi chú cho dev (feature-builder)

1. **Middleware ghi access_stats (FR-RPT-009, BR-RPT-005):**
   - Ghi `event_type='page_view'` cho GET trang chính trong **whitelist** (vd `/dashboard`, `/samples`, `/chemicals`, `/reports`...); KHÔNG ghi static/asset/`/health`/health-check (blacklist).
   - Ghi `event_type='login'` khi đăng nhập thành công (đồng bộ với `audit_logs` action `LOGIN`). **Chốt nguồn đếm:** nếu middleware ghi login vào `access_stats.event_type='login'` thì R15 đếm login từ access_stats; nếu chỉ ghi page_view thì đếm login từ `audit_logs.action='LOGIN'`. **Không đếm trùng cả hai nguồn** (BR-RPT-004) — chọn 1, ưu tiên access_stats vì đã có index `(event_type, at)`.
   - Ghi **không chặn** request (async / sau response), lỗi ghi → log WARN, KHÔNG fail request (BR-RPT-013, AC3).
   - **Lọc query string nhạy cảm** khỏi `path` trước khi ghi (token/secret — rule logging.md, AC4).
   - Overhead < 5ms/request (NFR-PERF-RPT-003).
2. **Cache dashboard 60s Redis (BR-RPT-011, NFR-PERF-RPT-001):** cache key = `dashboard:{role}:{department_id}:{filter_hash}`; TTL ~60s (default OQ#2, khoảng 60–300s); invalidate theo TTL (không realtime). Đạt P95 < 2s lần đầu, < 300ms khi trúng cache.
3. **RBAC scope aggregate (CONSTRAINT-3, BR-RPT-001/002/010):**
   - `report:business`/`report:finance` → áp scope `all`/`department` vào WHERE đếm (staff = phòng mình; ép scope nếu lọc phòng khác).
   - **Accountant KHÔNG nhận KPI mẫu/kết quả** (B03) — lọc ở backend, không chỉ FE.
   - **Field tiền** (unit_price, lương) chỉ vai trò có `chemical:cost` (admin/leader/accountant) — strip ở serializer (đồng bộ M2).
   - **R15 thống kê truy cập hệ thống → chỉ admin/leader** (quyền `audit:read` đã seed M7); staff/accountant gọi → 403 (BR-RPT-010).
4. **Permission seed — KHÔNG bổ sung:** đã kiểm M7 (`1718870400001_m7_platform.py` dòng 333-336, 356-390): `report:business`, `report:finance`, `audit:read` đã seed đủ cho 4 vai trò theo matrix. KHÔNG có/KHÔNG cần `report:analytics`. R15 dùng `audit:read` (admin/leader). Nếu Tech Lead muốn tách quyền riêng cho R15 (vd `report:access_log`) → seed idempotent `ON CONFLICT (resource,action) DO NOTHING` + `ON CONFLICT (role,resource,action) DO NOTHING` (theo pattern M5 dòng 189/210), chỉ gán admin+leader; nhưng mặc định M6-D6 dùng lại `audit:read` để tránh trùng quyền.
5. **Xuất báo cáo (FR-RPT-010/011):** ghi `audit_logs` action=`REPORT_EXPORT` (user, report type, kỳ, scope — BR-RPT-012); KHÔNG cần bảng mới, KHÔNG cần ALTER audit_logs (action là VARCHAR tự do).
6. **Đọc trực tiếp bảng nguồn (ASSUMPTION-1):** dùng index sẵn có của module nguồn. Nếu k6 phát hiện Seq Scan trên đếm CUD `audit_logs` theo `(action, at)` → thêm index ở migration M7 (audit), KHÔNG ở M6 (M6-D5).

---

## 5. Traceability → FR M6

| FR / BR SRS M6 | Hiện thực schema M6 |
|----------------|---------------------|
| FR-RPT-001/002/003/006 (dashboard KPI/biểu đồ/thống kê mẫu/nhân sự) | Dùng bảng nguồn có sẵn (samples/chemicals/equipments/hr_profiles/notifications) — KHÔNG schema mới (M6-D1) |
| FR-RPT-004 (tiêu hao hóa chất) | `chemical_transactions` có sẵn — KHÔNG schema mới |
| FR-RPT-007 (thống kê truy cập R15) | `access_stats.event_type` (mới) + index `(at,event_type)`/`(event_type,at)`; `audit_logs`, `document_access_log` có sẵn |
| FR-RPT-008 (chi tiết 1 user) | index `idx_access_user_at` (đã có M7) + `event_type` mới |
| FR-RPT-009 (middleware ghi access_stats) | ALTER `access_stats` ADD `event_type` (M6-D2) — ngoại lệ ghi duy nhất (CONSTRAINT-2) |
| FR-RPT-010/011 (xuất Excel/PDF + audit) | `audit_logs` action `REPORT_EXPORT` (có sẵn) — KHÔNG schema mới |
| BR-RPT-004 (nguồn đếm R15 cố định) | `event_type` phân loại login/page_view + index hỗ trợ đếm |
| BR-RPT-010 (R15 chỉ admin/leader) | quyền `audit:read` đã seed M7 (M6-D6) — KHÔNG seed mới |
| BR-RPT-011 (cache 60s) | Redis (app-layer §4) — KHÔNG schema |
| OUT-OF-SCOPE (snapshot KPI / data warehouse) | KHÔNG tạo bảng tổng hợp/snapshot (M6-D1) |
```
