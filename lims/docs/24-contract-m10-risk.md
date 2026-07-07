# Contract M10 — Rủi ro & Cơ hội + Cải tiến (Risk & Improvement)

**Điều khoản:** ISO/IEC 17025:2017 §8.5 (rủi ro & cơ hội) · §8.6 (cải tiến)
**Trạng thái:** APPROVED (tiếp nối "tiếp tục module" 07/07/2026)
**Migration:** `1718870400009_m10_risk` (chạy sau M8 `...008`)
**Phụ thuộc:** M7 (users/departments/audit/notifications/RBAC), tùy chọn liên kết M8 (CAPA)

> Sổ đăng ký **rủi ro/cơ hội** theo tiến trình + ma trận `likelihood × impact` → mức rủi ro,
> biện pháp xử lý có người chịu trách nhiệm, đánh giá lại định kỳ (CRON-8). **Cải tiến** (§8.6)
> là sổ nhẹ, có thể liên kết sang NC/CAPA (M8) khi triển khai thành hành động khắc phục.

---

## 1. ERD (4 bảng)

```
risks (id PK, risk_code UNIQUE [RSK-YYYY-NNNN], kind CHECK[risk|opportunity] DEFAULT 'risk',
    title, context TEXT, process_ref VARCHAR NULL,
    likelihood SMALLINT CHECK 1..5, impact SMALLINT CHECK 1..5,
    level SMALLINT GENERATED ALWAYS AS (likelihood*impact) STORED,
    status CHECK[open|treating|monitoring|closed] DEFAULT 'open',
    owner_id FK→users RESTRICT, department_id FK→departments RESTRICT,
    next_review_date DATE NULL, closed_at NULL, closed_by FK→users NULL,
    created_by FK→users, created_at, updated_at, updated_by FK→users NULL)

risk_treatments (id PK, risk_id FK→risks CASCADE, treatment TEXT,
    owner_id FK→users NULL, due_date DATE NULL, status CHECK[todo|done] DEFAULT 'todo',
    done_at NULL, created_by FK→users, created_at)

improvements (id PK, improvement_code UNIQUE [IMP-YYYY-NNNN],
    source CHECK[customer|staff|review|audit|other] DEFAULT 'other',
    title, description TEXT, owner_id FK→users NULL, department_id FK→departments NULL,
    status CHECK[open|in_progress|done|rejected] DEFAULT 'open',
    linked_nc_id FK→nonconformities SET NULL,  -- §8.6 → §8.7 khi thành CAPA
    created_by FK→users, created_at, updated_at, updated_by FK→users NULL)

risk_notification_dedup (id PK, risk_id FK→risks CASCADE, kind CHECK[RISK_REVIEW_DUE],
    milestone_days CHECK IN (30,15,7), fire_date DATE, UNIQUE(risk_id,milestone_days,fire_date))
```

`level` = GENERATED (likelihood×impact, 1..25). Band app-layer: **low** ≤4 · **medium** 5–12 · **high** ≥13. Audit mọi thao tác (§8.4).

---

## 2. API

**Risks** (`/api/v1/risks`)
| # | Method | Path | RBAC | Mô tả |
|---|--------|------|------|-------|
| 1 | GET | `/risks` | read | List + filter (q, kind, status, department_id, band) |
| 2 | POST | `/risks` | create | Tạo rủi ro/cơ hội |
| 3 | GET | `/risks/:id` | read | Chi tiết + biện pháp xử lý |
| 4 | PATCH | `/risks/:id` | create* | Sửa likelihood/impact/context/status/next_review_date |
| 5 | POST | `/risks/:id/treatments` | manage | Thêm biện pháp xử lý |
| 6 | PATCH | `/risks/:id/treatments/:tid` | manage | Đánh dấu done/todo |
| 7 | POST | `/risks/:id/close` | manage | Đóng rủi ro (đã kiểm soát) |
| 8 | GET | `/risks/stats` | read | Ma trận 5×5 (heatmap) + by status + by band |
| 9 | POST | `/admin/crons/risk-review-due/run` | admin | CRON-8 thủ công |

**Improvements** (`/api/v1/improvements`)
| # | Method | Path | RBAC | Mô tả |
|---|--------|------|------|-------|
| 10 | GET | `/improvements` | read | List + filter (q, status, source) |
| 11 | POST | `/improvements` | create | Ghi nhận cơ hội cải tiến |
| 12 | GET | `/improvements/:id` | read | Chi tiết |
| 13 | PATCH | `/improvements/:id` | create* | Cập nhật status / liên kết NC |

*PATCH: người tạo hoặc QM.

**RBAC:** resource `risk` & `improvement`, action read/create/manage. admin/leader full; staff read all + create dept; accountant KHÔNG. manage (biện pháp/đóng) = QM (admin/leader hoặc staff `is_quality_manager`).

Error code: `RISK_NOT_FOUND`, `RISK_CLOSED`, `IMPROVEMENT_NOT_FOUND`, `TREATMENT_NOT_FOUND`, `FORBIDDEN`.

---

## 3. Acceptance Criteria (P0)

- **AC1** Tạo risk sinh `RSK-YYYY-NNNN`; `level` = likelihood×impact tự tính (GENERATED).
- **AC2** PATCH likelihood/impact → level tự cập nhật; band suy ra đúng (low/medium/high).
- **AC3** Thêm/đánh dấu treatment; đóng risk khi đã kiểm soát (status=closed, ghi closed_by/at).
- **AC4** `/risks/stats` trả ma trận 5×5 đếm theo (likelihood,impact) + theo status + band.
- **AC5** RBAC: accountant list → 403; staff không QM thêm treatment → 403.
- **AC6** CRON-8: `next_review_date` còn 30/15/7 ngày → nhắc in-app owner, idempotent.
- **AC7** Tạo/sửa improvement (§8.6); liên kết `linked_nc_id` sang NC (M8) hợp lệ.
