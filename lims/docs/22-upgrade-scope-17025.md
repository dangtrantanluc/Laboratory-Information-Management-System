# LIMS 17025 — Upgrade Scope Phase 2 (Full 17025 Compliance)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm theo ISO/IEC 17025:2017
**Loại hình:** Lab học thuật / Trường Đại học (đã công nhận VILAS)
**Phiên bản:** v0.1 DRAFT — 07/07/2026
**Phạm vi:** Nâng cấp Phase 2 — bổ sung 9 module (M8–M16) phủ nốt các điều khoản còn thiếu
**Trạng thái:** Chờ KH approve scope → sau approve `/ba` viết SRS cho submodule P0

> Tài liệu này **nối tiếp** [`01-demo-scope.md`](01-demo-scope.md) (Phase 1 = M1–M7 đã build).
> Nội dung: **cây module 3 cấp + P0/P1/P2 + RBAC bổ sung + ERD core + cron mới + mapping 17025 + roadmap + effort**.
> Nguyên tắc: **tái dùng 100% hạ tầng Phase 1** (`audit_logs` §8.4, `notifications`+CRON, `attachments` polymorphic, RBAC scope, trigger immutable, MinIO) — **không** phát sinh hạ tầng mới. Vẫn **contract-first**: mỗi module qua `/contract` trước khi `/dev`.

---

## 0. Bối cảnh — Vì sao Phase 2

Phase 1 (M1–M7) phủ rất tốt phần **hồ sơ / tài liệu / dữ liệu** (§7.4, §7.5, §7.8, §8.3, §8.4 — enforce cứng ở tầng DB). Nhưng nhóm điều khoản **Hệ thống quản lý (Clause 8)** và một số **kỹ thuật (Clause 6–7)** chưa có, khiến lab chưa thể vận hành QMS đầy đủ trên phần mềm:

| Điều khoản còn thiếu (trước Phase 2) | Module Phase 2 đáp ứng |
|---|---|
| §6.3 Điều kiện môi trường/tiện nghi | **M13** |
| §7.3 Lấy mẫu | **M14** |
| §7.6 Độ không đảm bảo đo | **M15** |
| §7.7 Đảm bảo giá trị kết quả (QC/PT) | **M16** |
| §7.9 Khiếu nại | **M9** |
| §7.10 Công việc không phù hợp (nâng cấp từ mức partial) | **M8** |
| §8.5 Rủi ro & cơ hội · §8.6 Cải tiến | **M10** |
| §8.7 Hành động khắc phục (CAPA) | **M8** |
| §8.8 Đánh giá nội bộ | **M11** |
| §8.9 Xem xét lãnh đạo | **M12** |

---

## A. Cây Module 3 cấp (M8–M16)

Ký hiệu: **P0** = phải có · **P1** = nên có · **P2** = mở rộng sau.
Gom thành **2 epic** đúng cách VILAS phân loại: **EPIC-QMS** (Clause 8 + 7.9/7.10) và **EPIC-KT** (Clause 6.3, 7.3, 7.6, 7.7).

---

### ▐ EPIC-QMS — Hệ thống Quản lý Chất lượng

### M8. Không phù hợp & Hành động khắc phục (NC & CAPA) — **trục QMS**
> 17025 §7.10 (công việc không phù hợp), §8.7 (hành động khắc phục)

- **M8.1 Ghi nhận không phù hợp (Nonconformity)**
  - F8.1.1 Tạo phiếu NC (mô tả, mức độ, ngày phát hiện, người phát hiện) — **P0**
  - F8.1.2 Nguồn NC **polymorphic** (`complaint|qc|audit|env|sample|pt|manual`) — **P0**
  - F8.1.3 Đánh giá tác động + quyết định xử lý mẫu/kết quả bị ảnh hưởng (§7.10.1) — **P0**
  - F8.1.4 Đính kèm bằng chứng (`attachments`) — **P0**
- **M8.2 Hành động khắc phục (CAPA)**
  - F8.2.1 Phân tích nguyên nhân gốc (5-why/fishbone dạng text + file) — **P0** *(§8.7.2)*
  - F8.2.2 Lập hành động khắc phục: người chịu trách nhiệm + deadline — **P0**
  - F8.2.3 Xác minh thực hiện + **đánh giá hiệu lực** (effectiveness review) — **P0** *(§8.7.3)*
  - F8.2.4 Đóng CAPA — **bất biến sau đóng** (trigger immutable như §8.4) — **P0**
  - F8.2.5 Cron nhắc CAPA quá hạn/tới hạn (CRON-7) — **P0**
  - F8.2.6 Tách người **mở** NC ≠ người **duyệt đóng** CAPA — **P1**
- **M8.3 Thống kê NC/CAPA**
  - F8.3.1 Dashboard NC theo nguồn/mức độ/tình trạng — **P1**
  - F8.3.2 Thời gian đóng CAPA trung bình, tỷ lệ tái diễn — **P1**

### M9. Quản lý Khiếu nại (Complaints)
> 17025 §7.9

- **M9.1 Tiếp nhận khiếu nại**
  - F9.1.1 Tạo khiếu nại (khách hàng, nội dung, kênh, ngày nhận) — **P0**
  - F9.1.2 Phân loại + xác định tính hợp lệ (§7.9.3) — **P0**
  - F9.1.3 Xác nhận đã nhận cho người khiếu nại — **P1**
- **M9.2 Điều tra & xử lý**
  - F9.2.1 Điều tra — người xử lý **độc lập** với đối tượng bị khiếu nại (§7.9.6) — **P0**
  - F9.2.2 Liên kết sang NC/CAPA (M8) khi cần — **P0**
  - F9.2.3 Ra kết quả xử lý chính thức + thông báo người khiếu nại — **P0**
- **M9.3 Theo dõi**
  - F9.3.1 SLA + cron nhắc khiếu nại tồn đọng (CRON-11) — **P1**

### M10. Rủi ro & Cơ hội + Cải tiến (Risk & Improvement)
> 17025 §8.5 (rủi ro & cơ hội), §8.6 (cải tiến)

- **M10.1 Sổ đăng ký rủi ro/cơ hội**
  - F10.1.1 CRUD rủi ro/cơ hội (bối cảnh, tiến trình liên quan) — **P0**
  - F10.1.2 Đánh giá `likelihood × impact` → mức rủi ro (ma trận) — **P0**
  - F10.1.3 Biện pháp xử lý + người chịu trách nhiệm + hạn — **P0**
  - F10.1.4 Đánh giá lại định kỳ + cron nhắc (CRON-8) — **P1**
- **M10.2 Cải tiến (§8.6)**
  - F10.2.1 Ghi nhận cơ hội cải tiến / góp ý (từ khách hàng, nhân sự) — **P1**
  - F10.2.2 Liên kết cải tiến → CAPA (M8) khi triển khai — **P1**
- **M10.3 Thống kê**
  - F10.3.1 Ma trận rủi ro (heatmap recharts) + xu hướng — **P1**

### M11. Đánh giá nội bộ (Internal Audit)
> 17025 §8.8

- **M11.1 Chương trình đánh giá**
  - F11.1.1 Lập kế hoạch đánh giá năm (chu kỳ, phạm vi, đánh giá viên) — **P0**
  - F11.1.2 Checklist theo điều khoản 17025 (template) — **P0**
- **M11.2 Thực hiện đánh giá**
  - F11.2.1 Ghi nhận phát hiện (conformity/NC/observation) + bằng chứng — **P0**
  - F11.2.2 Phát hiện NC → **tự sinh phiếu NC** (M8) — **P0**
  - F11.2.3 Đánh giá viên **độc lập** với khu vực được đánh giá (§8.8.2) — **P0**
- **M11.3 Theo dõi khắc phục**
  - F11.3.1 Trạng thái khắc phục từng phát hiện + xuất báo cáo đánh giá — **P0**

### M12. Xem xét của Lãnh đạo (Management Review)
> 17025 §8.9

- **M12.1 Chuẩn bị đầu vào**
  - F12.1.1 **Tự tổng hợp đầu vào** từ NC/CAPA, khiếu nại, đánh giá nội bộ, rủi ro, QC, PT (§8.9.2) — **P0**
  - F12.1.2 Nhập đầu vào bổ sung (phản hồi KH, thay đổi khối lượng công việc…) — **P1**
- **M12.2 Cuộc họp & Biên bản**
  - F12.2.1 Tạo kỳ xem xét (ngày, thành phần tham dự) — **P0**
  - F12.2.2 Ghi biên bản + quyết định đầu ra (§8.9.3) — **P0**
- **M12.3 Hành động đầu ra**
  - F12.3.1 Quyết định → hành động có người + deadline (cron nhắc CRON-7) — **P0**
  - F12.3.2 Theo dõi hoàn thành hành động đầu ra — **P1**

---

### ▐ EPIC-KT — Kỹ thuật phòng thí nghiệm

### M13. Giám sát Điều kiện Môi trường (Environmental Monitoring)
> 17025 §6.3

- **M13.1 Khu vực & ngưỡng**
  - F13.1.1 CRUD khu vực (phòng/tủ lạnh/kho) + tham số theo dõi (nhiệt độ, độ ẩm, áp suất…) — **P0**
  - F13.1.2 Đặt ngưỡng cho phép (min/max) mỗi tham số × khu vực — **P0**
  - F13.1.3 Gắn mẫu/hóa chất lưu trong khu vực (đánh giá tác động khi vượt ngưỡng) — **P1**
- **M13.2 Ghi nhận số đọc**
  - F13.2.1 Nhập số đọc định kỳ (thủ công) + đính kèm — **P0**
  - F13.2.2 Webhook nhận datalogger/cảm biến IoT — **P2** *(CR riêng)*
- **M13.3 Vượt ngưỡng (Excursion)**
  - F13.3.1 Tự phát hiện vượt ngưỡng → tạo excursion + thông báo phụ trách — **P0**
  - F13.3.2 Excursion → **sinh NC** (M8) + đánh giá tác động lên mẫu/hóa chất bị ảnh hưởng — **P0**
  - F13.3.3 Cron cảnh báo thiếu số đọc định kỳ / excursion chưa xử lý (CRON-9) — **P1**

### M14. Kế hoạch & Hồ sơ Lấy mẫu (Sampling)
> 17025 §7.3 — *(áp dụng: lab TỰ đi lấy mẫu hiện trường — KH đã xác nhận cần)*

- **M14.1 Phương án lấy mẫu (Sampling plan)**
  - F14.1.1 CRUD phương án lấy mẫu (phương pháp, tham chiếu SOP tài liệu M3) — **P0**
  - F14.1.2 Thông số kế hoạch (điểm lấy, tần suất, số lượng) — **P1**
- **M14.2 Hồ sơ lấy mẫu (Sampling record)**
  - F14.2.1 Ghi hồ sơ lấy mẫu (người, thời gian, địa điểm, điều kiện môi trường) — **P0** *(§7.3.3)*
  - F14.2.2 Ghi **sai lệch** so với phương án — **P0**
  - F14.2.3 Liên kết hồ sơ lấy mẫu → `samples`/`test_requests` (M1) — **P0**
  - F14.2.4 Đính kèm ảnh hiện trường, sơ đồ điểm lấy — **P1**

### M15. Độ không đảm bảo đo (Measurement Uncertainty)
> 17025 §7.6 — *(áp dụng: phép thử ĐỊNH LƯỢNG — KH đã xác nhận cần)*

- **M15.1 Ngân sách độ không đảm bảo (Uncertainty budget)**
  - F15.1.1 Template budget theo phương pháp/chỉ tiêu — **P0**
  - F15.1.2 Khai báo thành phần (Type A/B, phân bố, hệ số nhạy, độ tự do) — **P0**
  - F15.1.3 Tính combined uncertainty + **expanded (k=2)** — **P0**
- **M15.2 Gắn vào kết quả**
  - F15.2.1 Gắn U vào kết quả mẫu (M1 `sample_results`) — **P0**
  - F15.2.2 Hiển thị "value ± U (k=2)" trên phiếu kết quả PDF (M1.5) — **P1**
- **M15.3 Rà soát định kỳ**
  - F15.3.1 Đánh giá lại budget khi đổi phương pháp/thiết bị — **P2**

> ⚠️ **Cần chuyên gia KH cung cấp mô hình toán từng phép thử.** Phần mềm lo template + engine tính + lưu trữ + gắn kết quả; **không** tự quyết định mô hình đo.

### M16. Đảm bảo giá trị kết quả — QC & Thử nghiệm thành thạo (QA of Results)
> 17025 §7.7

- **M16.1 Vật liệu & mẫu QC**
  - F16.1.1 CRUD vật liệu QC/CRM (giá trị quy chiếu, độ lệch chuẩn) — **P0**
- **M16.2 Biểu đồ kiểm soát (Control chart)**
  - F16.2.1 Nhập đo QC (blank/duplicate/spike/CRM) — **P0**
  - F16.2.2 Biểu đồ **Levey-Jennings/Shewhart** (recharts, đã có trong stack) — **P0**
  - F16.2.3 **Luật Westgard** (1-3s, 2-2s, R-4s, 4-1s, 10x) tự đánh giá in/out-of-control — **P0**
  - F16.2.4 QC out-of-control → **sinh NC** (M8) — **P0**
- **M16.3 Thử nghiệm thành thạo (PT/ILC)**
  - F16.3.1 Hồ sơ vòng PT/ILC (nhà cung cấp, chỉ tiêu, z-score, kết quả đạt/không) — **P0**
  - F16.3.2 PT không đạt → **sinh NC** (M8) — **P0**
  - F16.3.3 Cron nhắc vòng PT tới hạn (CRON-10) — **P1**

---

## B. RBAC — Vai trò & bổ sung

**Không thêm role mới trong DB.** Tái dùng 4 vai trò Phase 1 + **thêm 1 cờ** `is_quality_manager` trên `users` (đúng pattern `is_dept_lead` sẵn có) để chỉ định **Phụ trách chất lượng (QM)** — người sở hữu quy trình QMS.

> **QM (Quality Manager)** — theo 17025 là vai trò bắt buộc: duyệt đóng CAPA, chủ trì đánh giá nội bộ, chủ sổ rủi ro, chốt biên bản xem xét lãnh đạo. Thường gán cho một `leader` hoặc `staff` được ủy quyền.

### RBAC Matrix — module mới × vai trò

| Module / Hành động | Admin | Lãnh đạo | QM (cờ) | Kế toán | Nhân sự/KTV |
|---|:---:|:---:|:---:|:---:|:---:|
| **NC** — tạo/ghi nhận | ✅ | ✅ | ✅ | — | ✅(phòng) |
| **CAPA** — lập & thực hiện | ✅ | ✅ | ✅ | — | ✅(được giao) |
| **CAPA** — duyệt đóng / hiệu lực | ✅ | ✅ | ✅ | — | — |
| **Khiếu nại** — tiếp nhận/xử lý | ✅ | ✅ | ✅ | — | 👁 |
| **Rủi ro** — quản lý sổ | ✅ | ✅ | ✅ | 👁 | 👁(phòng) |
| **Đánh giá nội bộ** — lập KH/thực hiện | ✅ | ✅ | ✅ | — | ✅(đánh giá viên) |
| **Xem xét lãnh đạo** | ✅ | ✅ | ✅ | 👁 | — |
| **Môi trường** — nhập số đọc | ✅ | 👁 | 👁 | — | ✅(phòng) |
| **Môi trường** — cấu hình ngưỡng | ✅ | ✅ | ✅ | — | ✅(trưởng nhóm) |
| **Lấy mẫu** — phương án/hồ sơ | ✅ | 👁 | 👁 | — | ✅(phòng) |
| **Uncertainty** — budget/gắn KQ | ✅ | 👁 | ✅ | — | ✅(được giao) |
| **QC/PT** — nhập đo & biểu đồ | ✅ | 👁 | ✅ | — | ✅(phòng) |

Chú thích: ✅ = toàn quyền (trong phạm vi) · 👁 = chỉ xem · — = không truy cập · (phòng) = giới hạn phòng ban.
Cột **giá/PII** vẫn strip ở tầng API cho vai trò không đủ quyền (giữ nguyên field-level RBAC Phase 1).

---

## C. ERD Core (bảng mới M8–M16)

```
┌─────────────────────────────────────────────────────────────────────┐
│ M8. NC & CAPA (trục — nhiều nguồn đổ về)                              │
├─────────────────────────────────────────────────────────────────────┤
│ nonconformities (id PK, nc_code UNIQUE [NC-YYYY-…], source_type       │
│        ENUM[complaint|qc|audit|env|sample|pt|manual], source_id,      │
│        severity ENUM[minor|major|critical], description,              │
│        impact_assessment TEXT, affected_ref_type, affected_ref_id,    │
│        raised_by FK→users, raised_at, status ENUM[open|in_capa|closed])│
│ capa (id PK, nc_id FK→nonconformities, root_cause TEXT,               │
│        capa_type ENUM[corrective|preventive], owner_id FK→users,      │
│        due_date, verified_by FK NULL, effectiveness_result,           │
│        closed_by FK NULL, closed_at)  -- closed → IMMUTABLE (trigger) │
│ capa_actions (id PK, capa_id FK, action TEXT, assignee_id FK,         │
│        due_date, done_at, status)                                     │
│   -- polymorphic source_type: complaint/qc/audit/env/sample/pt (§8.7) │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ M9. KHIẾU NẠI                                                         │
├─────────────────────────────────────────────────────────────────────┤
│ complaints (id PK, complaint_code UNIQUE, customer_id FK→customers    │
│        NULL, channel, content TEXT, received_at, received_by FK,      │
│        is_valid BOOL NULL, handler_id FK→users, resolution TEXT,      │
│        nc_id FK→nonconformities NULL, status, resolved_at)            │
│ complaint_actions (id PK, complaint_id FK, action TEXT, by FK, at)    │
│   -- handler_id độc lập với người bị khiếu nại (§7.9.6)               │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ M10. RỦI RO & CƠ HỘI + CẢI TIẾN                                       │
├─────────────────────────────────────────────────────────────────────┤
│ risks (id PK, risk_code, kind ENUM[risk|opportunity], context,       │
│        process_ref, likelihood SMALLINT, impact SMALLINT,            │
│        level SMALLINT GENERATED (likelihood*impact), owner_id FK,     │
│        next_review_date, status)                                     │
│ risk_treatments (id PK, risk_id FK, treatment TEXT, owner_id FK,      │
│        due_date, done_at)                                             │
│ improvements (id PK, source, description, owner_id FK,                │
│        capa_id FK NULL, status, created_at)  -- §8.6                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ M11. ĐÁNH GIÁ NỘI BỘ                                                  │
├─────────────────────────────────────────────────────────────────────┤
│ internal_audits (id PK, audit_code, scope, planned_date, auditor_id  │
│        FK→users, status ENUM[planned|ongoing|reported|closed])       │
│ audit_checklist_items (id PK, audit_id FK, clause_ref, question,      │
│        result ENUM[conform|nc|observation|na], note)                 │
│ audit_findings (id PK, audit_id FK, checklist_item_id FK NULL,        │
│        finding TEXT, nc_id FK→nonconformities NULL, status)           │
│   -- auditor_id độc lập với khu vực được đánh giá (§8.8.2)            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ M12. XEM XÉT LÃNH ĐẠO                                                 │
├─────────────────────────────────────────────────────────────────────┤
│ management_reviews (id PK, review_code, review_date, chaired_by FK,   │
│        attendees JSONB, minutes TEXT, status)                        │
│ mr_inputs (id PK, review_id FK, input_type, summary TEXT,             │
│        ref_type, ref_id)  -- tổng hợp NC/CAPA/audit/risk/QC/PT §8.9.2 │
│ mr_actions (id PK, review_id FK, action TEXT, owner_id FK, due_date,  │
│        done_at, status)  -- §8.9.3 đầu ra                            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ M13. ĐIỀU KIỆN MÔI TRƯỜNG                                             │
├─────────────────────────────────────────────────────────────────────┤
│ env_zones (id PK, name, code, department_id FK, kind[room|fridge|…])  │
│ env_limits (id PK, zone_id FK, parameter ENUM[temp|humidity|pressure],│
│        unit, min_value NUMERIC, max_value NUMERIC, reading_freq_hours)│
│ env_readings (id PK, zone_id FK, parameter, value NUMERIC(10,4),      │
│        recorded_by FK→users, recorded_at, source[manual|sensor])     │
│ env_excursions (id PK, zone_id FK, parameter, value, limit_min,       │
│        limit_max, detected_at, nc_id FK→nonconformities NULL)         │
│   -- vượt ngưỡng → excursion → NC (M8); NUMERIC không float           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ M14. LẤY MẪU                                                          │
├─────────────────────────────────────────────────────────────────────┤
│ sampling_plans (id PK, plan_code, method_doc_id FK→documents NULL,    │
│        description, points JSONB, department_id FK, status)           │
│ sampling_records (id PK, plan_id FK NULL, request_id FK→test_requests,│
│        sampled_by FK→users, sampled_at, location, env_conditions,     │
│        deviation TEXT NULL)  -- §7.3.3 điều kiện + sai lệch           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ M15. ĐỘ KHÔNG ĐẢM BẢO ĐO                                              │
├─────────────────────────────────────────────────────────────────────┤
│ uncertainty_budgets (id PK, method_name, parameter, coverage_k        │
│        NUMERIC DEFAULT 2, created_by FK, status)                     │
│ uncertainty_components (id PK, budget_id FK, name, type[A|B],         │
│        distribution, value NUMERIC(18,8), divisor NUMERIC,           │
│        sensitivity NUMERIC, dof NUMERIC NULL)                        │
│ result_uncertainty (id PK, sample_result_id FK→sample_results,        │
│        budget_id FK, combined_u NUMERIC, expanded_u NUMERIC,          │
│        computed_at)  -- gắn U vào kết quả M1; NUMERIC precision cao   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ M16. QC & THỬ NGHIỆM THÀNH THẠO                                       │
├─────────────────────────────────────────────────────────────────────┤
│ qc_materials (id PK, name, lot_no, parameter, ref_value NUMERIC,      │
│        ref_sd NUMERIC, department_id FK, expiry_date)                │
│ qc_measurements (id PK, qc_material_id FK, qc_type[blank|dup|spike|   │
│        crm], value NUMERIC(18,6), measured_by FK, measured_at,       │
│        z_score NUMERIC, westgard_flags JSONB, is_out_of_control BOOL, │
│        nc_id FK→nonconformities NULL)                                │
│ proficiency_tests (id PK, provider, round_code, parameter,           │
│        assigned_value NUMERIC, our_value NUMERIC, z_score NUMERIC,   │
│        result ENUM[satisfactory|questionable|unsatisfactory],       │
│        due_next_date, nc_id FK NULL)  -- không đạt → NC (M8)         │
└─────────────────────────────────────────────────────────────────────┘
```

**Ghi chú thiết kế DB:**
- Số đo (QC, uncertainty, môi trường) dùng `NUMERIC` precision cao — **không float** (nhất quán rule Phase 1).
- Bản ghi đã đóng/duyệt (`capa` closed, `audit_findings` closed, đo QC/PT) → **immutable trigger** như `audit_logs` §8.4.
- `source_type/source_id` (M8) + `nc_id` (M9/M11/M13/M16) = liên kết đa nguồn về **một** engine CAPA.
- Dùng lại `attachments` polymorphic cho mọi bằng chứng (NC, audit, PT, excursion…).

---

## D. Cron Job mới (nối tiếp CRON-1..6)

| Cron | Tần suất | Logic | Output | Module |
|------|----------|-------|--------|--------|
| CRON-7 Nhắc CAPA/hành động quá hạn | hằng ngày 07:00 | `capa.due_date`/`capa_actions.due_date`/`mr_actions.due_date` tới hạn hoặc quá hạn & chưa done | **in-app** người chịu trách nhiệm | M8, M12 |
| CRON-8 Nhắc đánh giá lại rủi ro | hằng ngày 07:00 | `risks.next_review_date` tới hạn | **in-app** chủ rủi ro + QM | M10 |
| CRON-9 Cảnh báo môi trường | mỗi giờ | thiếu số đọc theo `reading_freq_hours` hoặc excursion chưa xử lý | **in-app** phụ trách khu vực | M13 |
| CRON-10 Nhắc vòng PT tới hạn | hằng ngày 07:00 | `proficiency_tests.due_next_date` còn 30/15/7 ngày | **in-app** QM + phụ trách | M16 |
| CRON-11 Nhắc khiếu nại/đánh giá tồn đọng | hằng ngày 07:00 | khiếu nại quá SLA; đánh giá nội bộ tới `planned_date` | **in-app** handler + QM | M9, M11 |

> Vẫn **chỉ in-app** (giữ chốt C02), APScheduler in-process, **lock Redis** tránh chạy trùng. CRON-9 chạy theo giờ (môi trường cần realtime hơn).

---

## E. Mapping 17025 sau Phase 2 (độ phủ mục tiêu)

| Điều khoản | Trước (P1) | Sau Phase 2 | Module |
|---|:---:|:---:|---|
| §6.3 Điều kiện môi trường | ⚪ 0% | 🟢 ~75% | M13 |
| §7.3 Lấy mẫu | ⚪ 15% | 🟢 ~75% | M14 |
| §7.6 Độ không đảm bảo đo | ⚪ 0% | 🟡 ~70%* | M15 |
| §7.7 Đảm bảo giá trị kết quả (QC/PT) | ⚪ 10% | 🟢 ~80% | M16 |
| §7.9 Khiếu nại | ⚪ 0% | 🟢 ~85% | M9 |
| §7.10 Công việc không phù hợp | 🟠 20% | 🟢 ~85% | M8 |
| §8.5 Rủi ro & cơ hội | ⚪ 0% | 🟢 ~85% | M10 |
| §8.6 Cải tiến | ⚪ 0% | 🟡 ~70% | M10.2 |
| §8.7 Hành động khắc phục (CAPA) | ⚪ 0% | 🟢 ~85% | M8 |
| §8.8 Đánh giá nội bộ | ⚪ 5% | 🟢 ~85% | M11 |
| §8.9 Xem xét lãnh đạo | ⚪ 0% | 🟢 ~85% | M12 |

<sub>*§7.6 phụ thuộc chuyên gia KH cung cấp mô hình toán; phần mềm phủ hạ tầng tính+lưu+gắn kết quả.</sub>

→ Sau Phase 2, độ phủ **toàn tiêu chuẩn** nâng từ ~45–50% lên **~80–85%** (phần còn lại là hoạt động ngoài phần mềm: năng lực thực tế của nhân sự, hiệu chuẩn vật lý, xác nhận giá trị phương pháp thực tế).

---

## F. Roadmap (nối tiếp S5 của Phase 1)

| Sprint | Nội dung | Vì sao thứ tự này | Deliverable demo |
|--------|----------|-------------------|------------------|
| **S6** | **M8** NC/CAPA (trục) + CRON-7 | Nền tảng — mọi module sau cắm vào | Luồng NC → CAPA → đóng |
| **S7** | **M10** Rủi ro + **M11** Đánh giá nội bộ + **M12** Xem xét lãnh đạo | Hoàn tất **Clause 8** — bắt buộc duy trì công nhận | QMS backbone chạy |
| **S8** | **M16** QC/PT (control chart + Westgard) + **M9** Khiếu nại + CRON-10/11 | Giá trị kỹ thuật cao, assessor kiểm QC | Levey-Jennings + PT |
| **S9** | **M13** Môi trường + **M14** Lấy mẫu + CRON-8/9 | Kỹ thuật theo phạm vi công nhận | Excursion → NC |
| **S10** | **M15** Uncertainty + NFR + security audit + UAT | Cần input chuyên môn, làm cuối | value ± U(k=2) |

> Mỗi sprint build xong → **gửi demo** cho KH duyệt (R14). Migration mới: M8→M9→M10→M11→M12→M13→M14→M15→M16 (chạy **sau** 7 migration Phase 1).

---

## G. Ước lượng Effort & Team

| Module | BE (d) | FE (d) | Test (d) | Tổng |
|--------|:---:|:---:|:---:|:---:|
| M8 NC/CAPA | 6 | 5 | 2 | **13** |
| M9 Khiếu nại | 3 | 2 | 1 | **6** |
| M10 Rủi ro + Cải tiến | 3 | 3 | 1 | **7** |
| M11 Đánh giá nội bộ | 4 | 4 | 1 | **9** |
| M12 Xem xét lãnh đạo | 3 | 2 | 1 | **6** |
| M13 Môi trường | 5 | 4 | 2 | **11** |
| M14 Lấy mẫu | 3 | 3 | 1 | **7** |
| M15 Uncertainty | 6 | 3 | 2 | **11** |
| M16 QC/PT | 6 | 6 | 2 | **14** |
| **Tổng** | **39** | **32** | **13** | **~84 dev-days** |

- **Giả định**: 1 dev mid-level, đã trừ phần tái dùng pattern Phase 1; **chưa** gồm buffer PM/review (~15%) và UAT.
- **Team đề xuất**: 2 dev (1 BE + 1 FE) → **~5 sprint (10 tuần)** + 1 QA part-time.
- **Chi phí**: `84 × (1 + 15%) ≈ 97 giờ-ngày × đơn giá hợp đồng` → lập **CR chính thức** trước khi bắt đầu (vn-docs §4 — Change Request bắt buộc ký trước khi làm).

---

## H. Gate tiếp theo

1. **KH approve scope Phase 2 này** + ký **Change Request** (ngoài scope hợp đồng Phase 1).
2. **Xác nhận với chuyên gia KH**: mô hình toán uncertainty (§7.6) từng phép thử — đầu vào bắt buộc cho M15.
3. `/ba` viết SRS chi tiết cho submodule P0 (bắt đầu **M8 NC/CAPA**).
4. `/contract <feature>` — ERD + API + AC cho từng submodule.
5. `/dev` implement (CHỈ sau khi contract APPROVED).

**KHÔNG code khi chưa có contract APPROVED.**
