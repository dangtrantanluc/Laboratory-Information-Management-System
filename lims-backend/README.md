# LIMS Backend — M7 (Nền tảng) + M1 (Quản lý Mẫu) + M2 (Hóa chất & Tồn kho) + M3 (Quản lý Tài liệu) + M4 (Nhân sự & Thành tích NCKH) + M5 (Thiết bị & Hiệu chuẩn) + M6 (Báo cáo & Thống kê)

Backend cho phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017.

- **M7 — Platform**: Auth (JWT + refresh rotation), Users, Departments, RBAC,
  Customers, Attachments (MinIO), Audit log (append-only), Notifications.
- **M1 — Sample Lifecycle**: phiếu yêu cầu, mẫu, state machine, phân công, chuyển
  giao (chain of custody), kết quả + versioning, duyệt (tách nhập-duyệt), chốt done,
  trễ hạn + CRON-1/CRON-2, xuất phiếu PDF, báo cáo on-time.
- **M2 — Chemical Inventory**: danh mục hóa chất + lô, đơn vị + quy đổi (Decimal,
  không float), giao dịch nhập/xuất/điều chỉnh (row-lock + atomic, balance_after
  snapshot), tồn kho theo lô/hóa chất, low-stock + reorder, FEFO, kiểm tra lại,
  CoA/MSDS (MinIO), xuất Excel nhật ký + báo cáo tiêu hao, CRON-6 nhắc hết hạn.
  Giao dịch IMMUTABLE (không sửa/xóa). Field-level RBAC: cột giá strip với KTV ở
  tầng API (OWASP A01).
- **M4 — HR & Research Achievement**: hồ sơ nhân sự (1-1 với users), lương = hệ số ×
  lương cơ sở (NUMERIC, không float), hợp đồng, chu kỳ + ngày nâng lương tự tính
  (relativedelta, an toàn năm nhuận 29/02→28/02), lịch sử nâng lương APPEND-ONLY,
  hồ sơ năng lực §6.2 (bằng/chứng chỉ/ủy quyền + minh chứng MinIO), thành tích NCKH
  (đề tài + thành viên n-n, bài báo/sáng chế + đồng tác giả n-n hỗ trợ tác giả ngoài
  hệ thống qua `external_name`, hướng dẫn SV, đăng ký lab CÓ duyệt, giảng dạy, cộng
  đồng), thống kê 3 chiều (cá nhân/phòng/thời gian) + xuất Excel, CRON-3 (nhắc nâng
  lương 15/7/3) + CRON-4 (nhắc hết hạn HĐ 30/15/7). **Field-level RBAC lương/HĐ/PII**:
  strip theo `(role, item.user_id == current_user)` — staff xem được lương CỦA MÌNH;
  sửa lương = admin/accountant (leader/staff → `SALARY_FORBIDDEN`); kế toán CẤM toàn
  bộ nhóm NCKH (`FORBIDDEN_ACCOUNTANT`). KHÔNG ghi giá trị lương/PII ra log/audit.
- **M6 — Reporting & Analytics** (module CUỐI, tầng TỔNG HỢP CHÉO — READ-ONLY aggregate):
  dashboard KPI chéo module 1 round-trip (mẫu/hóa chất/thiết bị/nhân sự/tài liệu/thông
  báo), biểu đồ (pie/line/bar tách nhóm đo), thống kê số mẫu + tiêu hao hóa chất theo
  bộ lọc thời gian thống nhất `[from, to)`, thống kê truy cập hệ thống R15 (lượt truy
  cập/tải/chỉnh sửa, top N user — chỉ admin/leader), xuất Excel/PDF (ghi audit
  `REPORT_EXPORT`). Cache dashboard 60s (Redis). RBAC enforce tầng API: accountant
  KHÔNG thấy khối mẫu (B03 — response không chứa `samples`); staff ép phòng mình +
  strip field tiền; R15 chỉ admin/leader (`audit:read`). Ngoại lệ ghi duy nhất:
  middleware + `POST /analytics/page-view` ghi `access_stats` (login + page_view) +
  audit `REPORT_EXPORT`. **KHÔNG** làm lại endpoint thống kê đơn-module đã có
  (sample-on-time / consumption / low-stock / documents access-stats / research stats).

Đây là module **nền tảng dùng chung** cho M1–M6: deps, RBAC, audit_service,
storage_service, notification_service được M1/M2/M4 tái sử dụng.

## Stack

- Python 3.11+, FastAPI, SQLAlchemy 2.x (sync), Alembic, Pydantic v2
- PostgreSQL 15 (pgcrypto, pg_trgm, citext)
- Redis 7 (jti denylist, lockout đăng nhập, cache RBAC)
- MinIO (S3-compatible, attachments qua boto3)
- JWT (python-jose HS256), bcrypt (passlib, cost 12)

## Chạy nhanh (Docker — khuyến nghị)

```bash
cd demo/lims-backend
docker compose up -d --build
```

Lệnh trên khởi động: `postgres` + `redis` + `minio` + `lims-api`.
Entrypoint tự **chờ Postgres** → chạy **`alembic upgrade head`** (tạo bảng + seed) → khởi động API.

Kiểm tra:

```bash
curl http://localhost:8060/health/ready
# {"success":true,"data":{"status":"ok","checks":{"db":true,"redis":true}}}
```

API docs (chỉ bật ở môi trường không phải production): http://localhost:8060/docs

### Đăng nhập admin mặc định

```bash
curl -X POST http://localhost:8060/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@lims.local","password":"ChangeMe@123"}'
```

Response trả `access_token` (gắn `Authorization: Bearer <token>`) và set cookie
`refresh_token` (HttpOnly). Trường `must_change_password: true` → **app FE phải ép
đổi mật khẩu lần đầu** (admin seed có `password_changed_at = NULL`).

> ⚠️ **BẢO MẬT:** `admin@lims.local` / `ChangeMe@123` CHỈ để khởi tạo. Đổi mật khẩu
> ngay lần đăng nhập đầu. KHÔNG để mật khẩu mặc định trên production (NFR-SEC A05).

## Cổng (port) — không đụng dịch vụ khác

| Dịch vụ | Cổng host | Ghi chú |
|---------|-----------|---------|
| API | **8060** | FastAPI |
| PostgreSQL | 5460 | → container 5432 |
| Redis | 6460 | → container 6379 |
| MinIO S3 | 9460 | API S3 |
| MinIO Console | 9461 | UI quản trị (minioadmin/minioadmin) |

## Chạy local (không Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # chỉnh DATABASE_URL/REDIS_URL/MINIO_* về localhost
# cần Postgres + Redis + MinIO đang chạy
alembic upgrade head          # tạo bảng + seed
uvicorn app.main:app --reload --port 8060
```

## Migration

```bash
alembic upgrade head      # áp migration + seed (permissions, roles_permissions, 4 phòng ban, admin)
alembic downgrade base    # rollback hoàn toàn (drop 10 bảng, giữ extension dùng chung)
alembic current           # xem revision hiện tại
```

Migration gốc: `alembic/versions/1718870400001_m7_platform.py` — tạo đúng 10 bảng theo
contract, xử lý vòng FK `users` ↔ `departments`, trigger append-only `audit_logs`,
toàn bộ index, và seed. Bcrypt hash của admin được **sinh runtime** lúc seed (không
commit mật khẩu vào repo).

Migration M1: `alembic/versions/1718870400002_m1_sample_lifecycle.py` (revises M7) —
tạo 6 bảng `test_requests`, `samples`, `sample_assignments`, `sample_results`,
`sample_handovers`, `overdue_reasons` + index. PK UUID, CHECK enum, partial unique
`is_current`, FK RESTRICT.

Migration M2: `alembic/versions/1718870400003_m2_chemical_inventory.py` (revises M1) —
tạo 6 bảng `units`, `chemicals`, `chemical_lots`, `chemical_transactions`,
`chemical_recheck_records`, `chemical_notification_dedup` + index (partial `qty_base>0`,
trigram tên, composite FK `(base_unit, measurement_group)`). Seed `units` (mass/volume/
count) + bổ sung `chemical:create` cho leader/staff (idempotent `ON CONFLICT`).
FK `chemical_transactions.ref_sample_id → samples.id` (ON DELETE RESTRICT).
NUMERIC: tồn/base `(18,6)`, nhập `(14,4)`, tiền `(14,2)` — không float.

Migration M4: `alembic/versions/1718870400004_m4_hr.py` (revises M2) — tạo 16 bảng:
4 danh mục (`contract_types`, `research_project_levels`, `publication_categories`,
`mentorship_types`) + 12 nghiệp vụ (`hr_profiles` 1-1 user_id PK=FK, `salary_history`
append-only, `competences`, `hr_notification_dedup`, `research_projects`,
`project_members`, `publications`, `publication_authors` XOR user_id/external_name,
`student_mentorships`, `lab_registrations` có duyệt, `teaching_courses`,
`community_services`) + index (partial `next_salary_raise_date`/`contract_end_date`
cho cron, partial unique `patent_no` khi patent) + seed danh mục (idempotent
`ON CONFLICT`). NUMERIC: hệ số `(6,2)`, tiền `(14,2)`. **KHÔNG** ALTER bảng M7/M1/M2;
quyền `hr:*`/`research:*` đã seed đủ ở M7 → M4 không thêm `roles_permissions`.

Migration M3: `alembic/versions/1718870400005_m3_document_control.py` (revises M4) —
tạo 4 bảng: `document_types` (danh mục natural-key code, seed 6 loại sop/process/
form/guide/standard/other + `prefix` sinh mã), `documents` (vùng chứa version,
`current_version_id` vòng FK giải bằng nullable + ALTER ADD `fk_doc_current` như M7
`users↔departments`), `document_versions` (state machine draft→review→approved→
obsolete), `document_access_log` (R15 high-volume). Bất biến QUAN TRỌNG NHẤT enforce
**DB-level**: partial unique `uq_doc_one_approved ON document_versions(document_id)
WHERE status='approved'` (≤1 approved/tài liệu, chống race). UNIQUE(document_id,
version_no), cặp submit/review/approve nhất quán (CHECK). State machine + tách soạn–
duyệt + immutable enforce app-layer (như M1/M4). **KHÔNG** ALTER bảng M7 — quyền
`document:*` đã seed đủ ở M7; `attachments.owner_type` đã có `document_version` ở M7.

Migration M5: `alembic/versions/1718870400006_m5_equipment_calibration.py` (revises M3) —
tạo 3 bảng: `equipments` (thiết bị §6.4; `next_due_date` denormalize = lần hiệu chuẩn gần
nhất; chu kỳ `value`+`unit` cả 2 NULL = không diện hiệu chuẩn; `code` bất biến app),
`calibration_records` (lần hiệu chuẩn §6.4/§6.5 — **IMMUTABLE**), `equipment_notification_dedup`
(CRON-5 idempotent mốc 30/15/7). Bất biến QUAN TRỌNG NHẤT enforce **DB-level**: trigger
`calibration_records_no_update/delete` chặn mọi UPDATE/DELETE (như `audit_logs` M7) +
KHÔNG route PATCH/DELETE. KHÔNG vòng FK (`next_due_date` là DATE denormalize) → thứ tự
CREATE tuyến tính. **M5 seed bổ sung** `permissions` + `roles_permissions` (action mịn
`equipment:read/create/update`, `calibration:create`; idempotent ON CONFLICT) vì M7 chỉ có
`equipment:manage` coarse — guard M5 chỉ kiểm action mịn, `equipment:manage` của leader thành
no-op (leader = 👁 chỉ xem, KHÁC M3). `attachments.owner_type` đã có `equipment`/`calibration`
ở M7 → KHÔNG ALTER.

Migration M6: `alembic/versions/1718870400007_m6_reporting.py` (revises M5) — **KHÔNG tạo
bảng nghiệp vụ/snapshot mới** (M6 READ-ONLY aggregate, tính runtime). Chỉ **ALTER
`access_stats` ADD COLUMN `event_type` VARCHAR(16)** (CHECK login|page_view, NULLABLE →
non-breaking với hàng cũ) để phân loại lượt đăng nhập vs xem trang (R15) + **2 index**
`idx_access_at_event (at,event_type)` và `idx_access_event_at (event_type,at) WHERE NOT NULL`
phục vụ đếm R15. Index `(user_id,at)`/`(at)` đã có ở M7 → KHÔNG tạo lại. **KHÔNG seed
permission mới**: `report:business`/`report:finance`/`audit:read` đã seed đủ ở M7 (R15 dùng
`audit:read` = admin/leader). Model `access_stat.py` thêm `event_type`. Downgrade drop 2
index + drop column (đã verify roundtrip M6↔M5).

Thứ tự migration tổng thể: **M7 → M1 → M2 → M4 → M3 → M5 → M6**. `alembic upgrade head` chạy sạch;
downgrade từng bậc rollback hoàn toàn (đã verify roundtrip M6↔M5 + M5↔M3 — drop bảng + thu hồi
seed; KHÔNG đụng seed M7; không phá module cũ).

## M5 — Equipment & Calibration (12 endpoint, FR-EQP-001..011, §6.4/§6.5/§8.4)

| # | Method | Path | Mô tả |
|---|--------|------|-------|
| 1 | GET | `/equipments` | Tìm/lọc thiết bị (q/status/department/responsible/calibration_status/overdue) + badge |
| 2 | GET | `/equipments/calibration-due` | Thiết bị sắp/đã quá hạn/không đạt (within_days/bucket) |
| 3 | GET | `/equipments/{id}` | Chi tiết + tài liệu + lần hiệu chuẩn gần nhất + badge |
| 4 | POST | `/equipments` | Tạo thiết bị (sinh `equipment_code` TB-<phòng>-<seq>) |
| 5 | PATCH | `/equipments/{id}` | Sửa metadata/tình trạng/chu kỳ (KHÔNG đổi code/dept) |
| 6 | POST | `/equipments/{id}/attachments` | Đính kèm tài liệu (multipart, MinIO) |
| 7 | GET | `/equipments/{id}/attachments/{attId}/download` | Tải tài liệu (presigned 15p) |
| 8 | GET | `/equipments/{id}/calibrations` | Lịch sử hiệu chuẩn (immutable, desc, is_latest) |
| 9 | POST | `/equipments/{id}/calibrations` | Ghi hiệu chuẩn (multipart CoC, tự tính next_due) |
| 10 | GET | `/calibrations/{id}` | Chi tiết 1 bản ghi hiệu chuẩn |
| 14 | GET | `/calibrations/{id}/cert/download` | Tải CoC/cert (presigned 15p) |
| 15 | POST | `/admin/crons/equipment-calibration-due/run` | Chạy thủ công CRON-5 (admin) |

**RBAC M5 (KHÁC M3):** `leader` = **👁 CHỈ XEM** (không ghi/duyệt thiết bị); `accountant`
= **👁 read only**; `staff` = đọc **toàn lab** + ghi **CHỈ phòng mình** (create/update/
calibration:create scope department); `admin` = full. Mọi endpoint ghi (#4/#5/#6/#9/#15) →
403 cho leader/accountant; staff ghi chéo phòng → 403.

**Ghi hiệu chuẩn (#9, CỐT LÕI) — 1 transaction + row-lock thiết bị:** insert
`calibration_records` (immutable) → upload CoC MinIO (`attachments owner_type='calibration'`)
→ tính `next_due = calibrated_at + chu kỳ` (`dateutil.relativedelta` — an toàn năm nhuận
29/02→28/02; cho `next_due_date_override` + reason) → cập nhật `equipments.next_due_date`
NẾU là lần gần nhất (ghi bổ sung lần cũ KHÔNG ghi đè) → audit. Lỗi upload → rollback.
CoC bắt buộc khi `result=pass`. Bản ghi **bất biến** — đính chính = bản ghi mới (`correction_of`).

**Badge cảnh báo (runtime, KHÔNG khóa cứng):** `calibration_status` ∈ {not_applicable,
never_calibrated, ok, due_soon (≤30 ngày), overdue, failed (lần gần nhất fail)} + `is_overdue`
+ `days_to_due` + `warning_label`. Thiết bị `retired`/chu kỳ NULL → not_applicable. Quá hạn/
không đạt **chỉ cảnh báo** — vẫn cho ghi hiệu chuẩn mới (badge cập nhật runtime sau khi pass).

**CRON-5 (07:45 UTC):** quét `next_due_date - today ∈ {30,15,7}` (chu kỳ ≠ NULL, ∉ retired,
chưa xóa) → nhắc in-app người phụ trách + trưởng nhóm phòng. Idempotent qua
`equipment_notification_dedup` (UNIQUE thiết bị×mốc×ngày) + Redis lock (`CRON_ALREADY_RUNNING`
nếu đang chạy). Endpoint #15 nhận `as_of_date` (dev/staging) để test mốc.

## M5 — Data shape cho Frontend (tóm tắt)
- **Equipment summary/detail:** `{ id, equipment_code, name, location, department_id,
  department_name, responsible_user_id, responsible_user_name, purchase_date, status,
  calibration_cycle_value, calibration_cycle_unit, next_due_date, last_calibrated_at,
  last_calibration_result, calibration_status, is_overdue, days_to_due, warning_label }`.
  Detail thêm `last_calibration{...}`, `calibration_count`, `attachments[]`, `created_by_name`.
- **Calibration record:** `{ id, equipment_id, calibrated_at, provider, result, next_due_date,
  next_due_overridden, override_reason, is_latest, cert_attachment_id, cert_file_name, note,
  correction_of, created_by_name, created_at }`. #9 trả thêm `cert{attachment_id,...}` +
  `equipment{ id, next_due_date, calibration_status, is_overdue, warning_label }`.
- **Download (#7/#14):** `{ download_url (presigned 15p), url_expires_at, file_name, mime, size }`.
- **CRON-5 (#15):** `{ run_at, as_of_date, scanned_equipments, notifications_created,
  by_milestone{30,15,7}, recipients, skipped_no_recipient, skipped_retired_or_no_cycle, deduped }`.
- Notification CRON-5: `type='CALIBRATION_DUE'`, `ref_type='equipment'`, `ref_id=equipment.id`
  (đọc qua API `notifications` M7).

## M6 — Reporting & Analytics (9 endpoint, FR-RPT-001..011, READ-ONLY aggregate)

| # | Method | Path | Mô tả | Vai trò |
|---|--------|------|-------|---------|
| 1 | GET | `/dashboard` | Gói KPI tổng hợp chéo module (cache 60s, scope vai trò) | admin/leader/accountant/staff |
| 2 | GET | `/dashboard/charts` | Pie (mẫu/trạng thái) + line (mẫu/thời gian) + bar (tiêu hao tách nhóm đo) | admin/leader/accountant(chỉ hóa chất)/staff |
| 3 | GET | `/reports/samples` | Đếm số mẫu theo bộ lọc + phân rã (status/time/department) | admin/leader/staff — **accountant 403** |
| 4 | GET | `/reports/chemicals` | Tiêu hao/tồn tách nhóm đo; field tiền theo vai trò | admin/leader/accountant/staff(no tiền) |
| 10 | GET | `/reports/system-access` | R15: lượt truy cập/tải/chỉnh sửa + top N user + timeline | **admin/leader CHỈ** |
| 11 | GET | `/reports/system-access/users/{userId}` | Chi tiết hoạt động 1 user + recent_actions | **admin/leader CHỈ** |
| 12 | GET | `/reports/{reportType}/export.xlsx` | Xuất Excel (dashboard/samples/chemicals/system-access), RBAC scope + audit | theo reportType |
| 13 | GET | `/reports/{reportType}/export.pdf` | Xuất PDF (chỉ `dashboard`; khác → 422 PDF_NOT_SUPPORTED) | theo reportType |
| 14 | POST | `/analytics/page-view` | FE ghi 1 lượt xem trang (whitelist) → 204 best-effort | mọi vai trò |

Bộ lọc thời gian thống nhất `from`/`to` (ISO date, khoảng nửa mở `[from, to)`, rỗng = tháng
hiện tại, `from >= to` → 422 `INVALID_DATE_RANGE`); `group_by` ∈ day|week|month (khác → 422
`INVALID_GROUP_BY`); `department_id` (staff truyền phòng khác → **ÉP về phòng mình**, không
403). `due_within_days` (1..90, default 30) cho ngưỡng "sắp tới hạn" trên dashboard.

**RBAC enforce TẦNG API (CONSTRAINT-3):** (1) **B03** — accountant KHÔNG nhận khối `samples`/
`equipments`/`documents` ở `/dashboard` (response không chứa), gọi endpoint chuyên mẫu (#3,
export samples) → **403**; (2) **field tiền** (`consumption_cost*`/`total_cost`/`cost`) chỉ
admin/leader/accountant (`chemical:cost`), staff bị strip ở serializer; (3) **R15** (#10/#11 +
export system-access) chỉ admin/leader (`audit:read`), accountant/staff → **403 cứng**;
(4) **scope phòng staff** — ép phòng mình ở #1–#4, #12.

**Nguồn đếm R15 cố định (BR-RPT-004):** lượt truy cập = `access_stats` (event_type login +
page_view); lượt tải = `document_access_log.action='download'`; lượt chỉnh sửa = action CUD
trong `audit_logs` (loại trừ AUTH_*/DOWNLOAD/EXPORT/VIEW). Login đếm 1 nguồn (`access_stats.
event_type='login'`) — KHÔNG đếm trùng audit LOGIN.

**Ghi access_stats (ngoại lệ READ-ONLY duy nhất):** middleware `AccessStatMiddleware` ghi
`page_view` cho GET whitelist (best-effort, không chặn request, lọc query nhạy cảm); auth
login thành công ghi `event_type='login'` (cùng commit login flow); `POST /analytics/page-view`
cho SPA navigation. Xuất báo cáo ghi `audit_logs` action `REPORT_EXPORT` (report_type/format/
kỳ/scope) sau khi commit (BR-RPT-012).

**Chống trùng (CONSTRAINT-1):** M6 KHÔNG làm lại `/reports/sample-on-time` (M1),
`/inventory/low-stock` + `/reports/consumption` + `/exports/transactions.xlsx` (M2),
`/documents/access-stats` (M3), `/research-achievements/stats` (M4) — chỉ ĐẾM tổng hợp chéo.

## M6 — Data shape cho Frontend (tóm tắt)
- **Dashboard (#1):** `{ scope{role,department_id,department_name}, samples{available,
  by_status{received,assigned,testing,done,overdue,returned},total,overdue,deep_link},
  chemicals{available,expiring_soon,recheck_due,low_stock,deep_link_*[,consumption_cost_month]},
  equipments{available,calibration_overdue,calibration_due_soon,deep_link},
  hr{available,salary_raise_due,contract_ending,deep_link}, documents{available,pending_review,
  deep_link}, notifications{available,unread,deep_link} }` + `meta{generated_at,cached,
  cache_ttl_seconds}`. Accountant: chỉ `chemicals`(có cost)+`hr`+`notifications` (no samples/
  equipments/documents). Staff: scope phòng, no `consumption_cost_month`, no `hr`. Khối lỗi →
  `{available:false,error}` (degrade mềm, HTTP vẫn 200).
- **Charts (#2):** `{ samples_by_status{data:[{status,count}]}, samples_over_time{group_by,
  metric,data:[{period,count}]}, chemical_consumption{group_by,by_measurement_group:[{measurement_group,
  base_unit,data:[{period,qty[,cost]}]}]} }` + `meta{...,from,to}`.
- **Reports samples (#3):** `{ filter{from,to,department_id,time_field}, total, breakdown_by,
  by_status{...}, by_time:[{period,count}][, by_department:[{department_id,department_name,count}]] }`.
- **Reports chemicals (#4):** `{ filter{...,metric}, by_measurement_group:[{measurement_group,
  base_unit,total_qty[,consumption_cost]}][, total_cost] }` (tách nhóm đo, KHÔNG cộng gộp g+mL).
- **System-access (#10):** `{ filter{from,to}, totals{access_count,download_count,edit_count},
  breakdown_definition{...}, top_users{access[],download[],edit[]}[, timeline:[{period,access_count,
  download_count,edit_count}]] }`. User chi tiết (#11): `{ user{id,name,role,department_name},
  filter, totals{...}, recent_actions:[{at,action,resource,resource_id,correlation_id}] }`.
- **Export (#12/#13):** binary `attachment` (xlsx: openpyxl; pdf: reportlab) + `X-Correlation-Id`
  header. Nội dung file = đúng scope user (accountant không xuất samples; staff no tiền).

## M3 — Document Control (20 endpoint, FR-DOC-001..016, §8.3/§8.4)

Danh mục: `GET /document-types`, `GET /confidentiality-levels`.
Tài liệu: `GET/POST /documents` (POST multipart — tạo tài liệu + version đầu, sinh
`document_code` <prefix>-<mã phòng>-<NNN> server-side), `GET/PATCH/DELETE /documents/{id}`
(soft-delete chỉ khi chưa có version approved — giữ hồ sơ §8.4).
Phiên bản: `GET/POST /documents/{id}/versions` (POST multipart + change_note bắt buộc
từ v2), `GET/PATCH /documents/{id}/versions/{vid}` (+ `PUT .../file` thay file draft),
`POST .../submit-review` (draft→review, cần file), `POST .../approve` (review→approved,
**1 transaction + row-lock document**: tự obsolete bản approved cũ + set
`current_version_id`), `POST .../reject` (review→draft + reject_reason),
`GET .../download` (presigned URL TTL 15p + ghi access_log), `GET /documents/{id}/history`
(timeline từ audit_logs), `GET /documents/pending-review` (hàng chờ duyệt, `can_approve`/item).
Thống kê R15: `GET /documents/{id}/access-stats`, `GET /documents/access-stats` (top N),
`GET /documents/access-stats/export` (xlsx).

**RBAC M3:** Kế toán **CHỈ XEM** version approved — mọi endpoint ghi → 403 `FORBIDDEN`.
Staff ghi/tạo trong phòng mình (`assert_write_scope`); duyệt CHỈ trưởng nhóm phòng
(`is_dept_lead && dept==doc.dept`) / leader / admin (`can_approve`). Tách soạn–duyệt:
`approved_by != created_by` → 403 `SELF_APPROVAL_FORBIDDEN`. **2 mức bảo mật**:
`internal` (mọi nhân sự đọc approved) / `restricted` (chỉ phòng sở hữu + admin/leader)
enforce 3 lớp: list (ẩn), get/history (404 ẩn tồn tại), download (403 `RESTRICTED_ACCESS`).
Hiển thị version draft/review chỉ người soạn + trưởng nhóm phòng + admin/leader.

Error codes: `INVALID_STATE_TRANSITION`, `SELF_APPROVAL_FORBIDDEN`, `DOCUMENT_NOT_FOUND`,
`VERSION_NOT_FOUND`, `VERSION_NOT_PUBLISHED`, `RESTRICTED_ACCESS`, `DUPLICATE_DOCUMENT_CODE`,
`DRAFT_ALREADY_EXISTS`, `CHANGE_NOTE_REQUIRED`, `REJECT_REASON_REQUIRED`, `VERSION_FILE_REQUIRED`,
`VERSION_LOCKED`, `DOCUMENT_HAS_APPROVED_VERSION`, `INVALID_DOC_TYPE`, `INVALID_CONFIDENTIALITY`,
`INVALID_FILE_TYPE`, `FILE_TOO_LARGE`, `VERSION_CONFLICT`, `STORAGE_UNAVAILABLE`.

## M1 — Sample Lifecycle (38 endpoint, FR-SAMPLE-001..019)

- **Phiếu:** `GET/POST /test-requests`, `GET/PATCH /test-requests/:id`,
  `GET/POST /test-requests/:id/samples`, `GET/POST /test-requests/:id/attachments`
- **Mẫu:** `GET /samples`, `GET /samples/overdue`, `GET /samples/:id`,
  `PATCH /samples/:id`, `PATCH /samples/:id/{condition,deadline}`, `GET /samples/:id/qr`,
  `GET/POST /samples/:id/attachments`
- **Phân công / handover:** `GET/POST /samples/:id/assignments`,
  `DELETE /assignments/:id`, `POST /samples/:id/handovers`, `GET /samples/:id/custody-chain`
- **Kết quả:** `GET/POST /assignments/:id/results`, `GET /samples/:id/results`,
  `POST /results/:id/{approve,return,revisions}`, `GET/POST /results/:id/attachments`
- **Chốt / trễ hạn / phiếu:** `POST /samples/:id/finalize`,
  `POST /samples/:id/overdue-reasons`, `GET /samples/:id/result-report.pdf` (reportlab)
- **Báo cáo / cron:** `GET /reports/sample-on-time`,
  `POST /admin/crons/{sample-due-soon,sample-overdue}/run` (Admin)

**RBAC M1:** Kế toán cấm toàn bộ (`FORBIDDEN_ACCOUNTANT`). Phạm vi ghi theo phòng;
phân công/duyệt/chốt chỉ trưởng nhóm phòng (`departments.lead_user_id`)/Admin/Lãnh đạo.
Tách nhập-duyệt (`SELF_APPROVAL_FORBIDDEN`). Kết quả approved bất biến (sửa = version mới).

**CRON (APScheduler, UTC):** CRON-2 00:30 đánh dấu `overdue` (idempotent qua status filter);
CRON-1 07:00 nhắc sắp tới hạn (dedup Redis theo mẫu×mốc×ngày). Cả hai dưới Redis lock.

## M2 — Chemical Inventory (22 endpoint, FR-CHEM-001..014)

- **Đơn vị:** `GET /units` (mass/volume/count + factor_to_base, read-only)
- **Hóa chất:** `GET/POST /chemicals`, `GET/PATCH /chemicals/:id`,
  `POST /chemicals/:id/deactivate`, `GET/POST /chemicals/:id/attachments` (MSDS)
- **Lô:** `GET/POST /chemicals/:id/lots` (tạo + nhập đầu atomic),
  `GET /lots/:id`, `GET /lots/:id/coa`, `GET /chemicals/:id/fefo-suggestion`
- **Giao dịch:** `POST /lots/:id/transactions` (in/out/adjust — row-lock + atomic),
  `GET /transactions` (lọc, phân trang). **Không có PUT/PATCH/DELETE** (immutable).
- **Tồn kho:** `GET /chemicals/:id/stock` (đổi display_unit), `GET /inventory/low-stock`,
  `GET /inventory/reconcile` (Admin/Lãnh đạo)
- **Kiểm tra lại:** `POST /lots/:id/rechecks`
- **Excel / báo cáo:** `GET /exports/transactions.xlsx` (openpyxl, sync ≤10K dòng),
  `GET /reports/consumption` (month/project/user)
- **Cron:** `POST /admin/crons/chem-expiry/run` (Admin)

**RBAC M2 (dữ liệu hóa qua `roles_permissions`):** `chemical:read` (mọi vai trò đọc tồn/
lịch sử toàn HT); `chemical:transact` (admin/leader all, staff theo phòng — **kế toán
KHÔNG có**, chỉ xem); `chemical:create` (admin/leader all, staff theo phòng);
`chemical:cost` (admin/leader/accountant xem giá). **Field-level price strip:** vai trò
không có `chemical:cost` (KTV) bị **xóa hoàn toàn** các key `unit_price`/`price_unit`/
`currency`/`stock_value`/`line_value`/`consumption_cost` khỏi mọi response + cột Excel —
ở TẦNG API (OWASP A01, không chỉ ẩn FE). KTV vẫn được **gửi** `unit_price` khi nhập.

**Quy đổi đơn vị:** tồn lưu base unit `NUMERIC(18,6)`; nhập/xuất theo input_unit cùng
nhóm → quy đổi `qty_base = qty_input × factor(in) / factor(base)` bằng `Decimal` (không
float, round-trip chính xác). Quy đổi chéo nhóm → `UNIT_GROUP_MISMATCH`.

**Concurrency:** `POST /lots/:id/transactions` dùng `SELECT ... FOR UPDATE` trên lô +
1 DB transaction (INSERT giao dịch + UPDATE `qty_base` + audit) → tồn không bao giờ âm.
`balance_after` snapshot tồn sau giao dịch (không SUM runtime); CHECK `qty_base>=0` là
lưới an toàn cuối.

**CRON-6 (07:30 UTC):** quét lô `qty_base>0` có `expiry_date`/`recheck_date` tới mốc
30/15/7 ngày → notify (trưởng phòng + admin), idempotent qua bảng
`chemical_notification_dedup` (UNIQUE lô×kind×mốc×ngày) + Redis lock.

## M4 — HR & Research Achievement (43 endpoint, FR-HR-001..020)

- **Hồ sơ nhân sự:** `GET/POST /hr-profiles`, `GET /hr-profiles/me`,
  `GET/PATCH /hr-profiles/:userId`, `PATCH /hr-profiles/:userId/{contract,salary-cycle}`,
  `POST /hr-profiles/:userId/salary-raises`, `GET /hr-profiles/:userId/salary-history`
- **Năng lực §6.2:** `GET/POST /hr-profiles/:userId/competences`,
  `PATCH/DELETE /competences/:id`, `POST /competences/:id/attachments` (MinIO),
  `GET /hr-profiles/:userId/competence-summary`
- **Đề tài:** `GET/POST /research-projects`, `GET/PATCH/DELETE /research-projects/:id`,
  `PUT /research-projects/:id/members` (n-n full replace)
- **Bài báo/Sáng chế:** `GET/POST /publications`, `GET/PATCH/DELETE /publications/:id`,
  `PUT /publications/:id/authors`, `POST /publications/:id/attachments`
- **Hướng dẫn SV / Đăng ký lab / Giảng dạy / Cộng đồng:** `/student-mentorships[/:id]`,
  `/lab-registrations` + `POST /lab-registrations/:id/{approve,reject}`,
  `/teaching-courses[/:id]`, `/community-services[/:id]`
- **Thống kê:** `GET /research-achievements/stats` (group_by individual|department),
  `GET /research-achievements/stats.xlsx` (openpyxl)
- **Danh mục:** `GET /catalogs/{project-levels,pub-indexes,contract-types,mentorship-types}`
- **Cron:** `POST /admin/crons/{salary-raise-due,contract-expiry}/run` (Admin)

**Field-level RBAC (CỐT LÕI, OWASP A01 — đồng bộ M2 strip giá, phức tạp hơn 1 bậc):**
strip theo `(role, item.user_id == current_user)`. 3 nhóm độc lập:
- **Lương** (`salary_grade/coefficient/base_salary_amount/computed_salary_amount/
  currency/salary_history/next|last_salary_raise_date/salary_cycle_years`): admin/leader/
  accountant đọc mọi người; **staff chỉ của mình**. Sửa lương = **admin + accountant**
  (leader/staff → `SALARY_FORBIDDEN`).
- **Hợp đồng** (`contract_*`): đọc như lương; sửa = admin + accountant.
- **PII** (`id_number/dob/bank_account` — schema hiện chưa thêm cột, §8.6; tập strip
  sẵn sàng): đọc chỉ admin/accountant + chính chủ (leader KHÔNG xem PII).

Trong list, mỗi item strip ĐỘC LẬP theo `user_id`. **Kế toán CẤM toàn bộ nhóm NCKH**
(#17–#37 → `FORBIDDEN_ACCOUNTANT`). Staff scope `own` ở NCKH (chỉ bản ghi mình là
thành viên/tác giả/mentor/performer).

**Lương = hệ số × lương cơ sở:** `salary_coefficient NUMERIC(6,2)` × `base_salary_amount
NUMERIC(14,2)` = `computed_salary_amount` (tính khi hiển thị, không lưu). `salary_history`
APPEND-ONLY (không route sửa/xóa — sửa sai = ghi bản ghi mới). `next_salary_raise_date`
tự tính app-layer = `(last_salary_raise_date ?? contract_signed_date) + cycle năm` bằng
`relativedelta` (29/02 + n năm → 28/02 năm không nhuận). KHÔNG ghi giá trị lương/PII vào
`audit_logs.detail`/log (BR-HR-024 — chỉ fact + ngày + `salary_history_id`).

**Đăng ký lab có duyệt:** `pending → approved/rejected`; duyệt bởi admin/leader/mentor
của lượt/trưởng nhóm phòng mentor; đã quyết → `REGISTRATION_ALREADY_DECIDED`; chỉ
`approved` vào thống kê.

**Tác giả/thành viên ngoài hệ thống:** `publication_authors`/`project_members` hỗ trợ
`external_name` (XOR với `user_id`; cả hai/không có → `INVALID_AUTHOR`). Đề tài giữ FK
chặt (members chỉ user nội bộ).

**CRON-3 (07:00) / CRON-4 (07:15) UTC:** quét `next_salary_raise_date` (mốc 15/7/3) /
`contract_end_date` (mốc 30/15/7, bỏ HĐ vô thời hạn) → notify HR (admin/leader/accountant)
+ chính nhân sự (CRON-3). Idempotent qua `hr_notification_dedup`
(UNIQUE hồ sơ×kind×mốc×ngày, dedup theo hồ sơ + fan-out nhiều người nhận) + Redis lock.

## M4 — Data shape cho Frontend (tóm tắt)

```jsonc
// GET /hr-profiles/:userId (accountant/leader/admin/chính chủ — có đủ; staff người khác → 403)
{ "user_id","full_name","email","department_id","department_name","job_title",
  "hired_date","phone","position",
  "contract_type","contract_signed_date","contract_end_date",          // nhóm contract (strip)
  "salary_grade","salary_coefficient","base_salary_amount",            // nhóm lương (strip)
  "computed_salary_amount","currency","salary_cycle_years",
  "last_salary_raise_date","next_salary_raise_date" }
// Số tiền/hệ số trả dạng STRING ("8564400.00","3.66") — không float.
// Khi bị strip: key VẮNG MẶT hoàn toàn (không null).

// GET /publications/:id
{ "id","type":"paper|patent","title","journal","year","doi","category",
  "department_id","department_name","patent_no","issuing_authority",
  "authors":[{ "user_id"|null,"external_name"|null,"name","author_order","is_corresponding" }] }

// GET /research-achievements/stats?group_by=individual|department
{ "group_by","period":{"from","to"},
  "projects":{"total","by_level":{}},"publications":{"total","by_index":{}},
  "patents","mentorships","lab_registrations_approved","teaching_courses","community_services",
  "user_id"|"department_id","user_name"|"department_name" }
```

## Biến môi trường (xem `.env.example`)

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `DATABASE_URL` | postgresql+psycopg2://lims:lims@postgres:5432/lims | Postgres DSN |
| `REDIS_URL` | redis://redis:6379/0 | Redis |
| `JWT_SECRET` | (đổi production) | Khóa ký JWT, ≥ 32 ký tự |
| `ACCESS_TOKEN_TTL_MINUTES` | 30 | ≤ 60 (NFR-SEC-003) |
| `REFRESH_TOKEN_TTL_DAYS` | 30 | ≤ 30 |
| `LOGIN_MAX_FAILED` / `LOGIN_LOCKOUT_MINUTES` | 5 / 15 | Khóa đăng nhập |
| `MINIO_ENDPOINT` | http://minio:9000 | Endpoint nội bộ (BE → MinIO) |
| `MINIO_PUBLIC_ENDPOINT` | http://localhost:9460 | Endpoint FE truy cập presigned URL |
| `MAX_UPLOAD_SIZE_BYTES` | 20971520 | 20MB |
| `CORS_ORIGINS` | localhost:3000,3050 | Origin frontend |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` | admin@lims.local / ChangeMe@123 | Admin khởi tạo |

## Cấu trúc

```
app/
  main.py            # FastAPI app, middleware, exception handlers, routers
  config.py          # Settings từ .env
  db/database.py     # engine + session + Base (SQLAlchemy 2.x sync)
  models/            # 10 ORM models M7
  schemas/           # Pydantic request schemas
  routers/           # auth, users, departments, rbac, customers,
                     #   notifications, audit_logs, attachments, health
  services/          # auth, user, department, customer, rbac, audit,
                     #   audit_read, notification, storage, attachment
  core/
    security.py      # bcrypt, JWT, refresh hash, jti denylist
    deps.py          # get_current_user, require_roles, require_permission
    rbac.py          # enforce RBAC (đọc roles_permissions + cache Redis)
    exceptions.py    # AppException + handlers (response format chuẩn)
    redis_client.py  # Redis pool + key helpers
    responses.py     # ok() / paginated() helper
    logging_config.py# structured JSON logging
  middleware/
    correlation_id.py# X-Correlation-Id xuyên FE→BE→DB
alembic/             # migration + seed
```

## 30 endpoint (theo contract M7 API)

- **Auth:** `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`,
  `GET /auth/me`, `PATCH /auth/me/password`
- **Users (admin):** `GET/POST /users`, `GET/PATCH /users/:id`,
  `POST /users/:id/{enable,disable,reset-password}`
- **Departments:** `GET /departments` (mọi vai trò), `POST/PATCH/DELETE` (admin)
- **RBAC:** `GET /roles`, `GET /permissions`, `GET /roles/:role/permissions`
- **Customers:** `GET/POST/GET:id/PATCH:id` (admin/staff ghi, accountant cấm)
- **Notifications (self):** `GET /notifications`, `GET /notifications/unread-count`,
  `PATCH /notifications/:id/read`, `PATCH /notifications/read-all`
- **Audit (admin/leader):** `GET /audit-logs`, `GET /audit-logs/:id`
- **Attachments:** `POST /attachments` (upload generic), `GET /attachments/:id` (presigned URL)

## Bảo mật đã triển khai

- Mật khẩu bcrypt cost 12; không bao giờ trả/log `password_hash`.
- Access token JWT stateless TTL 30p; refresh token opaque (hash sha256 lưu DB),
  rotation mỗi lần dùng, **phát hiện reuse → revoke toàn chuỗi phiên**.
- Lockout 5 lần sai/15 phút (Redis); revoke tức thời qua jti denylist (logout/disable).
- RBAC dữ liệu hóa (`roles_permissions`) + scope (all/department/own), enforce tầng API.
- `audit_logs` append-only (trigger DB chặn UPDATE/DELETE + service chỉ INSERT).
- Response error chuẩn `{success,error:{code,message,details,correlationId}}`,
  không lộ stack trace; correlationId xuyên suốt.
