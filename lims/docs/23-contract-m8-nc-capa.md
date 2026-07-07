# Contract M8 — NC & CAPA (Nonconformity & Corrective Action)

**Điều khoản:** ISO/IEC 17025:2017 §7.10 (công việc không phù hợp) · §8.7 (hành động khắc phục)
**Trạng thái:** APPROVED (phê duyệt triển khai — user "implement đi" 07/07/2026)
**Migration:** `1718870400008_m8_nc_capa` (chạy sau M6 `...007`)
**Phụ thuộc:** M7 (users/departments/audit_logs/notifications/permissions/roles_permissions)

> Module **trục** của EPIC-QMS: NC nhận nguồn polymorphic (`manual|complaint|qc|audit|env|sample|pt`) → mở CAPA → phân tích nguyên nhân gốc → hành động khắc phục → xác minh hiệu lực → đóng. **CAPA đã đóng = bất biến** (trigger DB, §8.7 là hồ sơ). Tách người mở NC ≠ người đóng CAPA (QM).

---

## 1. ERD (3 bảng + dedup cron)

```
nonconformities (id PK, nc_code UNIQUE [NC-YYYY-NNNN],
    source_type CHECK[manual|complaint|qc|audit|env|sample|pt], source_id UUID NULL,
    severity CHECK[minor|major|critical], title, description,
    impact_assessment TEXT NULL, affected_ref_type NULL, affected_ref_id UUID NULL,
    department_id FK→departments RESTRICT, raised_by FK→users RESTRICT, raised_at,
    status CHECK[open|in_capa|closed|cancelled] DEFAULT 'open',
    created_at, updated_at, updated_by FK→users NULL)

capa (id PK, nc_id FK→nonconformities CASCADE UNIQUE,  -- 1 CAPA / 1 NC
    capa_type CHECK[corrective|preventive] DEFAULT 'corrective', root_cause TEXT,
    owner_id FK→users RESTRICT, due_date DATE NULL,
    status CHECK[in_progress|closed] DEFAULT 'in_progress',
    effectiveness_result CHECK[effective|not_effective] NULL, effectiveness_note NULL,
    verified_by FK→users NULL, verified_at NULL, closed_by FK→users NULL, closed_at NULL,
    created_by FK→users, created_at)
    -- TRIGGER: khi OLD.status='closed' chặn UPDATE; chặn DELETE luôn (§8.7 immutable)

capa_actions (id PK, capa_id FK→capa CASCADE, action TEXT, assignee_id FK→users NULL,
    due_date DATE NULL, status CHECK[todo|done] DEFAULT 'todo', done_at NULL, note NULL,
    created_by FK→users, created_at)

capa_notification_dedup (id PK, capa_id FK→capa CASCADE, kind CHECK[CAPA_DUE],
    milestone_days CHECK IN (7,3,0), fire_date DATE, UNIQUE(capa_id,milestone_days,fire_date))
```

Bất biến: `capa` đóng rồi immutable (trigger). Audit mọi thao tác qua `audit_logs` (§8.4). Không lộ ID tuần tự (nc_code hiển thị).

---

## 2. API (`/api/v1/nonconformities`)

| # | Method | Path | RBAC | Mô tả |
|---|--------|------|------|-------|
| 1 | GET | `/nonconformities` | read | List + filter (q, status, severity, source_type, department_id) |
| 2 | POST | `/nonconformities` | create | Tạo NC (nguồn manual mặc định) |
| 3 | GET | `/nonconformities/:id` | read | Chi tiết NC + CAPA + actions |
| 4 | PATCH | `/nonconformities/:id` | create* | Sửa severity/impact/affected (khi chưa closed) |
| 5 | POST | `/nonconformities/:id/cancel` | manage | Hủy NC không hợp lệ (→ cancelled) |
| 6 | POST | `/nonconformities/:id/capa` | manage | Mở CAPA (root_cause, capa_type, owner_id, due_date) → NC=in_capa |
| 7 | POST | `/nonconformities/:id/actions` | manage | Thêm hành động khắc phục vào CAPA |
| 8 | PATCH | `/nonconformities/:id/actions/:actionId` | manage | Đánh dấu hành động done/todo |
| 9 | POST | `/nonconformities/:id/close` | manage | Xác minh hiệu lực + đóng CAPA + đóng NC (immutable) |
| 10 | GET | `/nonconformities/stats` | read | Thống kê theo status/severity/source |
| 11 | POST | `/admin/crons/capa-due/run` | admin | Chạy CRON-7 thủ công |

*PATCH NC: người tạo hoặc manage; sau `closed` → 409 `NC_CLOSED`.

**RBAC (permissions `nonconformity`):**
- `read`: admin(all), leader(all), staff(all). accountant = KHÔNG (cách ly nghiệp vụ lab).
- `create`: admin(all), leader(all), staff(department).
- `manage` (mở CAPA / actions / đóng): admin(all), leader(all), **staff nếu `is_quality_manager`** (cờ QM — app-layer). Người đóng CAPA phải ≠ người mở NC (khuyến nghị, cảnh báo mềm).

Response bọc chuẩn `{success,data,meta}`. Error code SNAKE_CASE: `NC_NOT_FOUND`, `NC_CLOSED`, `CAPA_EXISTS`, `CAPA_NOT_OPENED`, `CAPA_CLOSED_IMMUTABLE`, `ACTIONS_INCOMPLETE`, `FORBIDDEN`.

---

## 3. Acceptance Criteria (P0)

- **AC1** Tạo NC sinh `nc_code` NC-YYYY-NNNN duy nhất; status=open; audit `NC_CREATE`.
- **AC2** Mở CAPA: NC.status open→in_capa; 1 CAPA/NC (mở lần 2 → 409 `CAPA_EXISTS`).
- **AC3** Thêm/đánh dấu action chỉ khi CAPA `in_progress`; CAPA đã đóng → 409 `CAPA_CLOSED_IMMUTABLE`.
- **AC4** Đóng CAPA yêu cầu `effectiveness_result` + mọi action `done` (nếu còn todo → 422 `ACTIONS_INCOMPLETE`); set capa.status=closed, NC.status=closed; audit `CAPA_CLOSE`.
- **AC5** Sau đóng, mọi UPDATE `capa` bị **trigger DB** chặn (§8.7).
- **AC6** RBAC: accountant gọi list → 403; staff không QM gọi `/capa` → 403; staff QM → 200.
- **AC7** CRON-7: CAPA `due_date` còn 7/3/0 ngày & chưa closed → thông báo in-app cho owner, idempotent theo (capa, mốc, ngày).
- **AC8** `is_quality_manager` xuất hiện trong `/auth/me` để FE ẩn/hiện nút QM.
