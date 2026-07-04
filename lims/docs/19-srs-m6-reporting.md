# SRS: M6 — Báo cáo & Thống kê (Reporting & Analytics)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M6 — Báo cáo & Thống kê (Reporting & Analytics) — **module CUỐI, tầng TỔNG HỢP CHÉO**
**Version:** 1.0 | **Ngày:** 20/06/2026 | **Author:** BA agent
**Status:** DRAFT — bối cảnh đã chốt (4 vai trò, RBAC + phạm vi phòng ban, MinIO C01, in-app only C02, ~40 user C03, lab ĐÃ công nhận VILAS → audit §8.4). Còn 9 OPEN QUESTIONS (§8) — phần lớn là tham số cấu hình (cache TTL, phạm vi ghi access_stats, danh sách báo cáo cần PDF) có default, KHÔNG chặn ERD/luồng lõi.
**Nguồn:** `00-meeting-note-analysis.md` (R8 "tổng hợp, lọc thông tin"; R10 "thống kê số mẫu/hóa chất, lọc thời gian"; R15 "thống kê lượt truy cập/tải/chỉnh sửa"; quyết định chốt C01/C02/C03, B03), `01-demo-scope.md` (M6.1–M6.4, RBAC matrix mục B dòng "Báo cáo", ERD core `access_stats`/`audit_logs`/`notifications` M7 mục C, mapping 17025 mục E), `08-contract-m7-schema.md` (`access_stats`/`audit_logs`/`notifications` đã có ở M7; D11 access_stats tách khỏi audit_logs), SRS các module nguồn (M1 on-time/overdue, M2 tồn/tiêu hao/hết hạn, M3 `document_access_log`, M4 thành tích NCKH, M5 thiết bị quá hạn).
**Chuẩn:** IEEE 830 (rút gọn) · ISO/IEC 17025:2017 §8.4 (kiểm soát hồ sơ — audit là nguồn đếm "lượt chỉnh sửa")

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| 1.0 | 20/06/2026 | Bản DRAFT đầu tiên — 11 FR, 14 BR, 5 UC, 10 NFR, 9 OPEN QUESTIONS. Đồng bộ phong cách SRS M5: READ-ONLY aggregate (trừ hạ tầng ghi `access_stats` middleware — M6.3); RBAC + phạm vi phòng ban (staff=phòng mình, accountant=tài chính KHÔNG mẫu/kết quả, admin/leader=toàn bộ; thống kê truy cập hệ thống R15 chỉ admin/leader); KHÔNG làm lại endpoint thống kê riêng lẻ đã có ở M1/M2/M3/M4 — M6 chỉ TỔNG HỢP CHÉO module + bộ lọc thời gian thống nhất + thống kê truy cập HỆ THỐNG (R15). |

---

## 1. Giới thiệu

### 1.1 Mục đích

Tài liệu này đặc tả đầy đủ, không mơ hồ, kiểm thử được cho **Module M6 — Báo cáo & Thống kê** của hệ thống LIMS. M6 là **module cuối**, **tầng tổng hợp chéo** dữ liệu từ M1 (mẫu), M2 (hóa chất), M3 (tài liệu), M4 (nhân sự/NCKH), M5 (thiết bị) thành **một màn dashboard** + **bộ lọc thời gian thống nhất** + **thống kê truy cập hệ thống**. Mục tiêu nghiệp vụ:

1. **Dashboard tổng hợp một màn (R8, R10):** Ban lãnh đạo / Admin mở 1 màn thấy toàn cảnh phòng thí nghiệm: số mẫu theo trạng thái + số mẫu trễ hạn (M1), hóa chất sắp hết hạn + tồn thấp (M2), thiết bị quá hạn hiệu chuẩn (M5), hợp đồng / nâng lương sắp tới hạn (M4), tài liệu chờ duyệt (M3), thông báo chưa đọc (M7) — kèm biểu đồ (mẫu theo trạng thái, mẫu theo thời gian, tiêu hao hóa chất theo tháng). Thay vì mở từng module để xem rời rạc, lãnh đạo có một điểm vào duy nhất; staff thấy phần phòng mình; kế toán thấy phần tài chính.
2. **Bộ lọc đa tiêu chí + thống kê theo thời gian thống nhất (R8, R10):** thống kê số mẫu / lượng hóa chất tiêu hao... với **bộ lọc thời gian + phòng ban + loại** dùng chung cho mọi báo cáo tổng hợp — chuẩn hóa cách lọc thời gian (cùng quy ước khoảng `[from, to)`, cùng quy ước phòng ban/loại) trên toàn dashboard.
3. **Thống kê truy cập hệ thống (R15):** đếm **lượt truy cập** (đăng nhập / xem trang), **lượt tải file**, **lượt chỉnh sửa** — **toàn hệ thống**, theo user / theo thời gian. KHÁC thống kê truy cập của riêng tài liệu (M3 `document_access_log`): M6.3 là cấp **hệ thống**. Bao gồm cả **hạ tầng ghi `access_stats`** (middleware ghi lượt truy cập tự động — hiện M7 đã có bảng nhưng chưa ghi tự động).
4. **Xuất báo cáo (R4):** xuất Excel / PDF các báo cáo tổng hợp để báo cáo nội bộ / phục vụ đánh giá VILAS.

Tài liệu dùng cho 2 đối tượng:
- **Khách hàng / Ban lãnh đạo lab:** xác nhận đúng các **chỉ số (KPI) trên dashboard**, **scope theo vai trò** (đặc biệt: kế toán không thấy mẫu/kết quả; thống kê truy cập hệ thống chỉ admin/leader), **quy ước bộ lọc thời gian**, **báo cáo nào cần PDF**.
- **Đội thiết kế (`schema-designer`, `api-designer`, `ux-designer`) và `feature-builder`:** đủ chi tiết để viết contract và implement mà không phải hỏi lại — **đặc biệt là ranh giới KHÔNG trùng endpoint thống kê đã có ở các module khác** (§2.4 CONSTRAINT-1, §9).

### 1.2 Phạm vi

Module M6 phủ 4 submodule (theo `01-demo-scope.md` M6.1–M6.4):

| Submodule | Nội dung | Trong SRS này |
|-----------|----------|---------------|
| M6.1 Dashboard tổng hợp | KPI chéo module 1 màn (mẫu/hóa chất/thiết bị/nhân sự/tài liệu/thông báo) + biểu đồ; scope theo vai trò | ✅ FR-RPT-001..004 |
| M6.2 Bộ lọc đa tiêu chí + thống kê theo thời gian (R8, R10) | Thống kê số mẫu / lượng hóa chất tiêu hao... lọc theo khoảng thời gian + phòng ban + loại (bộ lọc thống nhất) | ✅ FR-RPT-005..006 |
| M6.3 Thống kê truy cập hệ thống (R15) | Lượt truy cập / tải file / chỉnh sửa toàn hệ thống, theo user/thời gian; **hạ tầng ghi `access_stats` (middleware)** | ✅ FR-RPT-007..009 |
| M6.4 Xuất báo cáo | Xuất Excel/PDF các báo cáo tổng hợp | ✅ FR-RPT-010..011 |

**Trong scope `[SCOPE]`:**
- **Dashboard tổng hợp (M6.1):** một endpoint/màn trả gói KPI gom từ nhiều module: (a) **mẫu** — số mẫu theo trạng thái (`received`/`assigned`/`testing`/`done`/`overdue`/`returned`) + số mẫu trễ hạn; (b) **hóa chất** — số lô sắp hết hạn / tới hạn kiểm tra lại + số hóa chất tồn dưới ngưỡng; (c) **thiết bị** — số thiết bị quá hạn hiệu chuẩn + số sắp tới hạn; (d) **nhân sự** — số người nâng lương / hết hạn HĐ sắp tới hạn; (e) **tài liệu** — số tài liệu/version đang chờ duyệt (`review`); (f) **thông báo** — số thông báo chưa đọc của user hiện tại. Mỗi KPI có **deep-link** sang module nguồn.
- **Biểu đồ dashboard:** mẫu theo trạng thái (pie), số mẫu theo thời gian (line theo ngày/tuần/tháng), tiêu hao hóa chất theo tháng (bar) — dữ liệu biểu đồ trả cùng dashboard hoặc qua endpoint biểu đồ riêng.
- **Scope dashboard theo vai trò (BR-RPT-001):** Admin/leader = toàn hệ thống; staff = **phòng mình** (chỉ KPI nghiệp vụ phòng mình); accountant = **chỉ phần tài chính** (chi phí hóa chất, lương/HĐ), **KHÔNG thấy KPI mẫu/kết quả** (B03).
- **Bộ lọc đa tiêu chí + thống kê theo thời gian thống nhất (M6.2):** số mẫu (theo trạng thái / theo thời gian) + lượng hóa chất tiêu hao... lọc theo **khoảng thời gian** (`from`/`to`), **phòng ban**, **loại** (loại mẫu / nhóm đo hóa chất). Quy ước bộ lọc dùng chung toàn M6.
- **Thống kê truy cập hệ thống (M6.3 — R15):**
  - **Lượt truy cập** (đăng nhập + xem trang) — đếm từ **`access_stats`** (M7) + sự kiện `LOGIN` từ `audit_logs`.
  - **Lượt tải file** — đếm từ **`document_access_log` action=`download`** (M3) + (tùy chọn) sự kiện tải attachment các module khác nếu được ghi access_stats.
  - **Lượt chỉnh sửa** — đếm các action CUD (create/update/delete) từ **`audit_logs`** (M7, §8.4).
  - Thống kê **theo user** + **theo khoảng thời gian**; **top N** user truy cập/tải/chỉnh sửa nhiều nhất.
- **Hạ tầng ghi `access_stats` (M6.3 — middleware):** đặc tả **middleware ghi lượt truy cập tự động** vào `access_stats` (path, method, status_code, user_id, ip, at) cho các request đủ điều kiện (theo whitelist trang chính — OQ#1). Đây là **phần hạ tầng của M6.3** vì bảng đã có (M7) nhưng chưa được ghi tự động.
- **Xuất báo cáo (M6.4 — R4):** xuất **Excel** các báo cáo tổng hợp (dashboard snapshot, thống kê mẫu/hóa chất theo thời gian, thống kê truy cập hệ thống); xuất **PDF** cho các báo cáo cần định dạng trình bày (danh sách báo cáo cần PDF — OQ#3). Xuất tôn trọng RBAC scope (chỉ xuất dữ liệu user được phép xem).
- **Audit/observability:** thao tác **xuất báo cáo** ghi `audit_logs` (ai xuất báo cáo gì, khoảng thời gian nào — phục vụ truy vết §8.4).

**Ngoài scope `[OUT-OF-SCOPE → cần CR]`:**
- **Làm lại các endpoint thống kê riêng lẻ đã có ở từng module** (CONSTRAINT-1): M1 `/reports/sample-on-time`; M2 `/reports/consumption` + `/inventory/low-stock` + `/exports/transactions.xlsx`; M3 `/documents/access-stats` (+ `/:id/access-stats` + `/access-stats/export`); M4 `/research-achievements/stats` (+ `.xlsx`). M6 **gọi/tổng hợp lại** dữ liệu các module này (đếm số liệu cho dashboard/bộ lọc thống nhất), **KHÔNG** định nghĩa lại logic on-time rate / tiêu hao / access-stats chi tiết theo tài liệu / thành tích NCKH. Nếu KH muốn báo cáo chi tiết hơn các báo cáo module hiện có → CR ở module tương ứng, không phải M6.
- **Báo cáo tài chính kế toán đầy đủ** (hóa đơn, công nợ, sổ cái, doanh thu dịch vụ thử nghiệm): M6 chỉ tổng hợp **chi phí hóa chất** + **lương/HĐ** ở mức KPI; báo cáo tài chính kế toán chuyên sâu → CR.
- **Dashboard tùy biến (drag-drop widget, người dùng tự cấu hình KPI / lưu layout)**: bản đầu dashboard cố định theo vai trò → CR.
- **Báo cáo lập lịch tự động + gửi định kỳ qua email** (scheduled report email): chỉ in-app + xuất thủ công (C02); gửi email định kỳ → CR.
- **BI/OLAP, data warehouse, materialized view phức tạp, export tới Power BI/Metabase**: bản đầu query trực tiếp Postgres + cache nhẹ (Redis); BI nâng cao → CR.
- **Thống kê truy cập real-time (live dashboard / streaming)**: bản đầu là tổng hợp theo kỳ (query), không realtime → CR.
- **Lưu lịch sử snapshot KPI theo ngày (time-series KPI store) để xem lại dashboard quá khứ chính xác từng ngày**: bản đầu tính runtime theo bộ lọc thời gian; snapshot KPI theo ngày → CR (OQ#4).
- **Thông báo qua email / Zalo**: chỉ in-app (C02).

### 1.3 Định nghĩa, từ viết tắt và thuật ngữ

| Thuật ngữ | Định nghĩa |
|-----------|------------|
| **Dashboard tổng hợp** | Màn/endpoint trả gói **KPI chéo module** + dữ liệu biểu đồ, đã áp scope theo vai trò (M6.1). |
| **KPI (chỉ số)** | Một con số tổng hợp (vd "số mẫu overdue", "số lô hóa chất sắp hết hạn") hiển thị trên dashboard, có deep-link sang module nguồn. |
| **Bộ lọc thống nhất (Unified filter)** | Tập tham số lọc dùng chung toàn M6: `from`, `to` (khoảng thời gian `[from, to)`), `department_id` (phòng ban), `type` (loại mẫu / nhóm đo hóa chất...). Quy ước nhất quán (BR-RPT-009). |
| **Scope theo vai trò** | Phạm vi dữ liệu báo cáo theo RBAC: admin/leader = toàn hệ thống; staff = phòng mình; accountant = chỉ tài chính, không mẫu/kết quả (BR-RPT-001, B03). |
| **Thống kê truy cập hệ thống (R15)** | Đếm lượt truy cập (login + xem trang) / lượt tải file / lượt chỉnh sửa, **toàn hệ thống**, theo user/thời gian (M6.3). KHÁC `document_access_log` của riêng tài liệu (M3). |
| **`access_stats`** | Bảng M7 (đã có): lượt truy cập **cấp đường dẫn toàn hệ thống** (`user_id`, `path`, `method`, `status_code`, `ip`, `at`). High-volume, có thể prune (M7 D11). M6.3 ghi (middleware) + đọc (thống kê). |
| **`audit_logs`** | Bảng M7 (append-only §8.4): nhật ký mọi thao tác (`action`, `resource`, `resource_id`, `user_id`, `correlation_id`, `at`, `detail`). M6.3 đếm action CUD = **lượt chỉnh sửa**; đếm `LOGIN` = lượt đăng nhập. |
| **`document_access_log`** | Bảng riêng M3: lượt `view`/`download`/`edit` mỗi **tài liệu** (R15). M6.3 đếm `download` = **lượt tải file**. M6 KHÔNG thay thế thống kê chi tiết theo tài liệu của M3. |
| **Lượt chỉnh sửa (Edit count)** | Số action CUD (create/update/delete) trong `audit_logs` theo user/kỳ (R15 "lượt chỉnh sửa"). |
| **Lượt truy cập (Access/visit count)** | Số lần đăng nhập (`LOGIN`) + số lần xem trang (record `access_stats`) theo user/kỳ (R15). |
| **Lượt tải (Download count)** | Số lần tải file (`document_access_log.action='download'` + tùy chọn tải attachment khác) theo user/kỳ (R15). |
| **Middleware ghi access_stats** | Lớp chặn request HTTP ghi tự động vào `access_stats` cho các request đủ điều kiện (whitelist trang chính — OQ#1). Hạ tầng của M6.3. |
| **Deep-link** | Liên kết từ KPI dashboard sang màn chi tiết module nguồn (vd "5 mẫu overdue" → danh sách mẫu overdue M1, đã áp bộ lọc). |
| **READ-ONLY aggregate** | M6 KHÔNG tạo/sửa/xóa dữ liệu nghiệp vụ; chỉ đọc + tổng hợp. Ngoại lệ duy nhất: middleware GHI `access_stats` (hạ tầng M6.3) + ghi `audit_logs` khi xuất báo cáo. |
| **VILAS** | Hệ thống công nhận phòng thí nghiệm Việt Nam (theo ISO/IEC 17025). |
| **RBAC** | Role-Based Access Control + phạm vi theo phòng ban. |

### 1.4 Tài liệu tham chiếu

| Tài liệu | Vai trò |
|----------|---------|
| `lims/docs/00-meeting-note-analysis.md` | Yêu cầu gốc **R8** (tổng hợp/lọc), **R10** (thống kê số mẫu/hóa chất, lọc thời gian), **R15** (lượt truy cập/tải/chỉnh sửa); R4 (xuất Excel); quyết định chốt C01/C02/C03, B03 |
| `lims/docs/01-demo-scope.md` | Cây module M6.1–M6.4, RBAC matrix mục B (dòng "Báo cáo — nghiệp vụ" / "Báo cáo — tài chính"), ERD core `access_stats`/`audit_logs`/`notifications` (M7, mục C), mapping 17025 (mục E) |
| `lims/docs/08-contract-m7-schema.md` | `access_stats`/`audit_logs`/`notifications` đã có ở M7 (DDL + index); **D11** access_stats tách khỏi audit_logs (retention khác nhau); ghi chú M3 `document_access_log` KHÔNG thay `access_stats` (dòng 130-133); index `access_stats(user_id, at)` / `access_stats(at)` đã có (dòng 495-497) |
| `lims/docs/05-srs-m1-sample.md` + `07-contract-m1-api.md` | Nguồn dữ liệu mẫu: trạng thái mẫu, `completed_at`/`deadline_at` (on-time/overdue); endpoint đã có `/reports/sample-on-time` (M6 KHÔNG làm lại) |
| `lims/docs/02-srs-m2-chemical.md` + `04-contract-m2-api.md` | Nguồn dữ liệu hóa chất: tồn/hết hạn/kiểm tra lại/tiêu hao; endpoint đã có `/inventory/low-stock`, `/reports/consumption`, `/exports/transactions.xlsx` (M6 KHÔNG làm lại); response serializer ẩn field tiền theo vai trò (KTV không thấy giá) |
| `lims/docs/13-srs-m3-document.md` + `15-contract-m3-api.md` | Nguồn dữ liệu tài liệu: `document_access_log` (view/download/edit), version `review` chờ duyệt; endpoint đã có `/documents/access-stats` (M6 KHÔNG làm lại — chỉ tổng hợp lượt tải hệ thống) |
| `lims/docs/10-srs-m4-hr.md` + `12-contract-m4-api.md` | Nguồn dữ liệu nhân sự: nâng lương/HĐ sắp tới hạn, thành tích NCKH; endpoint đã có `/research-achievements/stats` (M6 KHÔNG làm lại) |
| `lims/docs/16-srs-m5-equipment.md` | Nguồn dữ liệu thiết bị: `equipments.next_due_date` (quá hạn / sắp tới hạn hiệu chuẩn), tình trạng thiết bị; chuẩn phong cách FR/BR/UC/NFR/AC |
| `~/.claude/rules/nfr.md` | Template NFR chuẩn IEEE 830 (perf dashboard, RBAC) |
| `~/.claude/rules/api.md` | Quy ước REST, response format, status code, pagination, không lộ ID tuần tự |
| `~/.claude/rules/logging.md` | Structured logging, correlationId, slow query log, response time SLA |
| **ISO/IEC 17025:2017** §8.4 | **Kiểm soát hồ sơ** — audit là nguồn đếm "lượt chỉnh sửa" (R15) và truy vết thao tác xuất báo cáo |

---

## 2. Mô tả tổng quan

### 2.1 Bối cảnh sản phẩm — module TỔNG HỢP, không sở hữu dữ liệu nghiệp vụ

M6 là module cuối trong 7 module của LIMS monolith (FastAPI + Next.js + PostgreSQL + Redis + MinIO + APScheduler, Docker Compose). Khác mọi module khác, **M6 không sở hữu bảng nghiệp vụ riêng**: nó **đọc và tổng hợp** dữ liệu từ M1–M5 + M7. M6 **phụ thuộc**:

- **M7 (Auth + RBAC + phòng ban + audit + access_stats):** mọi API M6 yêu cầu JWT + kiểm tra quyền `report:business` / `report:finance` theo vai trò + phạm vi phòng ban. M6 đọc `audit_logs` (đếm lượt chỉnh sửa + LOGIN), `access_stats` (đếm lượt truy cập), `notifications` (KPI thông báo chưa đọc). M6.3 cung cấp **middleware ghi `access_stats`** (bảng M7 đã có nhưng chưa được ghi — đây là hạ tầng M6.3).
- **M1 (Mẫu):** đọc `samples` (trạng thái, `deadline_at`, `completed_at`) để đếm số mẫu theo trạng thái / overdue / theo thời gian. **KHÔNG làm lại** on-time rate (đã có `/reports/sample-on-time`).
- **M2 (Hóa chất):** đọc tồn/lô/hạn dùng/giao dịch để đếm lô sắp hết hạn, hóa chất tồn thấp, tiêu hao theo tháng. **KHÔNG làm lại** `/reports/consumption`, `/inventory/low-stock`, `/exports/transactions.xlsx`. Field tiền tuân theo serializer ẩn giá của M2 (KTV không thấy giá — BR-RPT-002).
- **M3 (Tài liệu):** đọc `document_access_log` (đếm `download` = lượt tải hệ thống), số version `review` (KPI tài liệu chờ duyệt). **KHÔNG làm lại** `/documents/access-stats` chi tiết theo tài liệu.
- **M4 (Nhân sự/NCKH):** đọc `hr_profiles` (nâng lương/HĐ sắp tới hạn → KPI), thành tích NCKH (chỉ tổng hợp cấp cao nếu cần). **KHÔNG làm lại** `/research-achievements/stats`.
- **M5 (Thiết bị):** đọc `equipments` (`next_due_date` quá hạn/sắp tới hạn, tình trạng) → KPI thiết bị.
- **Redis (cache):** cache kết quả dashboard/KPI (TTL ngắn — OQ#2) để đạt NFR < 2s (~40 user); cache phân quyền.
- **MinIO + thư viện xuất file:** xuất Excel/PDF (M6.4).

M6 **không được tham chiếu bởi module nào khác** (là module cuối, lá của đồ thị phụ thuộc).

> **Nguyên tắc chống trùng (CONSTRAINT-1):** M6 = **tầng tổng hợp chéo module + bộ lọc thời gian thống nhất + thống kê truy cập hệ thống**. Mọi báo cáo **đơn-module chi tiết** đã thuộc module đó. Danh sách rõ ràng "M6 tổng hợp gì từ đâu" ở **§9**.

### 2.2 Chức năng chính

1. **Dashboard tổng hợp 1 màn** (M6.1): gom KPI chéo module (mẫu/hóa chất/thiết bị/nhân sự/tài liệu/thông báo) + biểu đồ; áp scope theo vai trò.
2. **Bộ lọc đa tiêu chí + thống kê theo thời gian** (M6.2): số mẫu / tiêu hao hóa chất... lọc theo khoảng thời gian + phòng ban + loại (bộ lọc thống nhất).
3. **Thống kê truy cập hệ thống** (M6.3, R15): lượt truy cập / tải / chỉnh sửa toàn hệ thống, theo user/thời gian + top N. **Chỉ admin/leader.**
4. **Hạ tầng ghi `access_stats`** (M6.3): middleware ghi lượt truy cập tự động.
5. **Xuất báo cáo Excel/PDF** (M6.4, R4): xuất các báo cáo tổng hợp, tôn trọng RBAC scope; ghi audit thao tác xuất.

### 2.3 Đối tượng người dùng & quyền (RBAC + phạm vi phòng ban)

Trích từ RBAC matrix `01-demo-scope.md` mục B — dòng "**Báo cáo — nghiệp vụ (mẫu/hóa chất)**" (Admin ✅, Lãnh đạo ✅, Kế toán 👁 chỉ hóa chất, KTV 👁 phòng) và "**Báo cáo — tài chính**" (Admin ✅, Lãnh đạo ✅, Kế toán ✅, KTV —). Quyền M7: `report:business` + `report:finance` (08-contract-m7-schema dòng 541-542, đã seed).

| Actor | Mô tả | Quyền trong M6 |
|-------|-------|----------------|
| **Admin** | Quản trị hệ thống | Toàn quyền: dashboard toàn hệ thống (mọi KPI), bộ lọc thống kê mọi phòng, **thống kê truy cập hệ thống (R15)**, xuất mọi báo cáo. |
| **Ban lãnh đạo (leader)** | Lãnh đạo lab | Dashboard **toàn hệ thống** (mọi KPI nghiệp vụ + tài chính), bộ lọc thống kê mọi phòng, **thống kê truy cập hệ thống (R15)**, xuất báo cáo. (Đây là người dùng chính của M6.) |
| **Kế toán (accountant)** | Tài chính | Dashboard **chỉ phần tài chính**: chi phí hóa chất (`report:finance` + `chemical:cost`) + lương/HĐ sắp tới hạn (M4). **KHÔNG thấy KPI mẫu/kết quả thử nghiệm** (B03 — cách ly nghiệp vụ lab khỏi tài chính). **KHÔNG** xem thống kê truy cập hệ thống R15 (OQ#5 — default theo matrix: R15 chỉ admin/leader). Xuất báo cáo tài chính. |
| **Nhân sự/KTV (staff)** | Kỹ thuật viên | Dashboard **phạm vi phòng mình** (KPI nghiệp vụ mẫu/hóa chất/thiết bị/tài liệu phòng mình; `report:business` scope department, 👁 — chỉ xem). **KHÔNG** xem field tiền (giá hóa chất, lương — BR-RPT-002, đồng bộ serializer ẩn giá M2). **KHÔNG** xem thống kê truy cập hệ thống R15. **KHÔNG** xem báo cáo tài chính. |

Quy ước: ✅ = toàn quyền (trong phạm vi) · 👁 = chỉ xem · — = không truy cập · (phòng) = giới hạn phòng ban.

> **Đặc thù M6 quan trọng:**
> - **Thống kê truy cập hệ thống (R15 / M6.3) chỉ admin/leader** (giám sát hành vi người dùng toàn hệ thống — nhạy cảm; tách khỏi `report:business`). Staff/accountant gọi → 403 (BR-RPT-010).
> - **Kế toán không thấy mẫu/kết quả** trên dashboard (B03) — backend phải LỌC KPI mẫu khỏi response của accountant, không chỉ ẩn ở FE (BR-RPT-001, đồng bộ serializer M2).
> - **Field tiền** (chi phí hóa chất, lương) chỉ vai trò tài chính (admin/leader/accountant); KTV không thấy (BR-RPT-002).

### 2.4 Ràng buộc (Constraints)

- **CONSTRAINT-1 (KHÔNG trùng endpoint module khác — quan trọng nhất):** M6 KHÔNG định nghĩa lại các báo cáo đơn-module đã có: M1 `/reports/sample-on-time`; M2 `/reports/consumption`, `/inventory/low-stock`, `/exports/transactions.xlsx`; M3 `/documents/access-stats` (+ `/:id/access-stats`, `/access-stats/export`); M4 `/research-achievements/stats` (+ `.xlsx`). M6 chỉ **tổng hợp chéo** (đếm KPI cho dashboard + bộ lọc thời gian thống nhất + thống kê truy cập HỆ THỐNG R15). Chi tiết §9.
- **CONSTRAINT-2 (READ-ONLY nghiệp vụ):** M6 KHÔNG tạo/sửa/xóa dữ liệu nghiệp vụ của M1–M5. Ngoại lệ hạ tầng: (a) **middleware GHI `access_stats`** (M6.3 — FR-RPT-009); (b) **ghi `audit_logs`** khi xuất báo cáo (FR-RPT-011). Không ngoại lệ nào khác.
- **CONSTRAINT-3 (RBAC scope ở tầng API):** mọi báo cáo áp scope theo vai trò + phòng ban ở **tầng API** (không chỉ FE). Accountant không nhận KPI mẫu/kết quả; KTV không nhận field tiền; R15 chỉ admin/leader (đồng bộ NFR-SEC, OWASP A01).
- **CONSTRAINT-4 (Nguồn đếm R15 cố định):** lượt truy cập = `access_stats` + `audit_logs` action `LOGIN`; lượt tải = `document_access_log.action='download'` (+ tùy chọn attachment khác nếu ghi access_stats); lượt chỉnh sửa = action CUD trong `audit_logs`. M6 KHÔNG tạo bảng đếm riêng (D11 — dùng access_stats + audit_logs của M7, document_access_log của M3).
- **CONSTRAINT-5 (Bộ lọc thời gian thống nhất):** mọi thống kê M6 dùng quy ước khoảng `[from, to)` (bao gồm from, loại trừ to), múi giờ hệ thống thống nhất (BR-RPT-009). Nhất quán với cách M1/M2 đã lọc thời gian.
- **CONSTRAINT-6 (Hiệu năng dashboard):** dashboard P95 < 2s với ~40 user (NFR-PERF-RPT-001); dùng cache Redis (TTL OQ#2) + index có sẵn ở module nguồn; không truy vấn nặng đồng bộ làm nghẽn (báo cáo nặng → có thể async/cache).
- **CONSTRAINT-7 (Lưu file & xuất):** file xuất (Excel/PDF) sinh runtime; file lớn/cố định lưu MinIO nếu cần (C01); xuất sync ưu tiên (báo cáo lớn → cân nhắc async — OQ#7).
- **CONSTRAINT-8 (Thông báo):** chỉ in-app (C02) — M6 không gửi báo cáo định kỳ qua email.
- **CONSTRAINT-9 (Stack & quy mô):** FastAPI, PostgreSQL, Redis, MinIO; ~40 user (C03) — monolith, query trực tiếp + cache nhẹ, không cần data warehouse.
- **CONSTRAINT-10 (Phụ thuộc M1–M5 + M7):** M6 chỉ build sau khi M1–M5 + M7 sẵn sàng (đọc bảng/endpoint của chúng). Là module cuối roadmap (S4, đồng bộ demo-scope mục G).

### 2.5 Giả định (Assumptions) — xem chi tiết §7

- ASSUMPTION-1: M6 đọc **trực tiếp các bảng** của module nguồn (samples, chemical_lots, equipments, hr_profiles, document_versions, audit_logs, access_stats...) cho dashboard/KPI để đạt hiệu năng (1 query gom), thay vì gọi HTTP nội bộ tới từng endpoint module. Logic nghiệp vụ phức (on-time rate, tiêu hao) vẫn ở module gốc; M6 chỉ **đếm/tổng hợp** (OQ#8 — đọc bảng trực tiếp vs gọi service).
- ASSUMPTION-2: Dashboard tính **runtime** theo bộ lọc thời gian + cache Redis ngắn (TTL OQ#2). Không lưu snapshot KPI lịch sử theo ngày (snapshot → OQ#4/CR).
- ASSUMPTION-3: **Middleware ghi `access_stats`** ghi cho các request đủ điều kiện (default: request GET trang chính + login — whitelist OQ#1), không ghi mọi request (tránh phình bảng); access_stats có retention/prune riêng (M7 D11).
- ASSUMPTION-4: "Lượt chỉnh sửa" (R15) = số action CUD trong `audit_logs` (mọi module đã ghi audit theo §8.4) — không cần bảng đếm riêng.
- ASSUMPTION-5: "Lượt tải file" (R15) chủ yếu từ `document_access_log` (M3 — tài liệu); tải attachment các module khác (CoA, CoC, file mẫu) chỉ đếm nếu được ghi vào access_stats/audit (OQ#6 — phạm vi "lượt tải").
- ASSUMPTION-6: Báo cáo cần **PDF** là tập con (báo cáo trình bày — danh sách OQ#3); phần lớn báo cáo dữ liệu xuất **Excel** (R4).
- ASSUMPTION-7: Biểu đồ dashboard dùng dữ liệu tổng hợp đã áp scope; render ở FE (M6 trả số liệu, không render ảnh biểu đồ).

---

## 3. Yêu cầu chức năng chi tiết

Mỗi FR có ID dạng `FR-RPT-NNN`. Business rule dạng `BR-RPT-NNN` ở §4. Acceptance Criteria dạng Given–When–Then (cover happy path + edge + RBAC + lỗi input).

---

### FR-RPT-001: Dashboard tổng hợp KPI chéo module — scope theo vai trò (R8, R10)

- **Mô tả:** Trả một **gói KPI tổng hợp** cho dashboard, gom từ nhiều module, **đã áp scope theo vai trò + phòng ban** (BR-RPT-001): (a) **mẫu (M1)** — số mẫu theo từng trạng thái + số mẫu trễ hạn (`overdue`); (b) **hóa chất (M2)** — số lô sắp hết hạn / tới hạn kiểm tra lại + số hóa chất tồn dưới ngưỡng; (c) **thiết bị (M5)** — số thiết bị quá hạn hiệu chuẩn + sắp tới hạn; (d) **nhân sự (M4)** — số người nâng lương / hết hạn HĐ sắp tới hạn (chỉ vai trò có quyền HR/tài chính); (e) **tài liệu (M3)** — số version `review` chờ duyệt; (f) **thông báo (M7)** — số thông báo chưa đọc của user hiện tại. Mỗi KPI kèm **deep-link** sang module nguồn. **Accountant KHÔNG nhận KPI mẫu/kết quả** (B03); **staff** chỉ KPI phòng mình; **field tiền** chỉ vai trò tài chính (BR-RPT-002).
- **Độ ưu tiên:** P0
- **Actor:** Admin, leader (toàn hệ thống), staff (phòng mình, 👁), accountant (chỉ tài chính, 👁 — không KPI mẫu).
- **Tiền điều kiện:** user đã đăng nhập, có quyền `report:business` hoặc `report:finance`.
- **Luồng chính:**
  1. User mở Dashboard.
  2. Hệ thống xác định vai trò + phòng ban → chọn tập KPI được phép (BR-RPT-001) → áp scope (toàn hệ thống / phòng mình / chỉ tài chính).
  3. Truy vấn (qua cache Redis nếu còn hạn — BR-RPT-011) đếm các KPI từ bảng module nguồn (BR-RPT-003..008).
  4. Trả gói KPI + deep-link; ghi `access_stats` (qua middleware FR-RPT-009).
- **Luồng phụ / ngoại lệ:**
  - A1: accountant → response **không chứa** KPI mẫu/kết quả (chỉ chi phí hóa chất + nâng lương/HĐ) (BR-RPT-001).
  - A2: staff → KPI giới hạn phòng mình; không có KPI tài chính/lương (BR-RPT-001, BR-RPT-002).
  - A3: một module nguồn lỗi/timeout → KPI module đó trả "không khả dụng" (degrade mềm), các KPI khác vẫn hiển thị (BR-RPT-013).
- **Hậu điều kiện:** dashboard hiển thị KPI đúng scope; chỉ đọc (trừ ghi access_stats).
- **Business Rules:** BR-RPT-001, BR-RPT-002, BR-RPT-003..008, BR-RPT-011, BR-RPT-013.
- **Acceptance Criteria:**
  - AC1 (happy — leader toàn hệ thống): GIVEN leader, hệ thống có 10 mẫu overdue, 3 lô hóa chất sắp hết hạn, 2 thiết bị quá hạn hiệu chuẩn WHEN mở dashboard THEN response chứa các KPI đúng số (mẫu overdue=10, lô sắp hết hạn=3, thiết bị quá hạn=2), mỗi KPI có deep-link.
  - AC2 (RBAC — accountant không thấy mẫu): GIVEN accountant WHEN mở dashboard THEN response **KHÔNG chứa** bất kỳ KPI mẫu/kết quả nào; CÓ chi phí hóa chất + nâng lương/HĐ sắp tới hạn (B03, BR-RPT-001).
  - AC3 (RBAC scope phòng — staff): GIVEN staff phòng "Hóa" WHEN mở dashboard THEN KPI mẫu/hóa chất/thiết bị chỉ tính cho phòng Hóa; KHÔNG có field tiền (giá/lương) (BR-RPT-001, BR-RPT-002).
  - AC4 (degrade mềm): GIVEN module M5 lỗi tạm thời WHEN mở dashboard THEN KPI thiết bị hiển thị "không khả dụng", các KPI khác vẫn trả đúng, HTTP 200 (BR-RPT-013).
  - AC5 (performance + cache): GIVEN dataset quy mô thật (~10K mẫu, ~2K thiết bị) WHEN 10 user mở dashboard đồng thời THEN P95 < 2s; lần gọi thứ 2 trong TTL cache trả từ cache (NFR-PERF-RPT-001, BR-RPT-011).
- **Data cần thiết (mức logic, READ-ONLY):** đếm từ `samples`(status, deadline_at, department_id), `chemical_lots`(expiry_date, recheck_date) + `chemicals`(reorder_threshold, tồn), `equipments`(next_due_date, status), `hr_profiles`(next_salary_raise_date, contract_end_date), `document_versions`(status='review'), `notifications`(read_at IS NULL, user hiện tại). KHÔNG ghi bảng nghiệp vụ.
- **API cần (ý định):** "lấy dashboard KPI tổng hợp (đã áp scope vai trò)".

---

### FR-RPT-002: Dữ liệu biểu đồ dashboard (pie / line / bar)

- **Mô tả:** Cung cấp dữ liệu **biểu đồ** cho dashboard, đã áp scope vai trò: (a) **mẫu theo trạng thái** (pie — đếm `samples` nhóm theo `status`); (b) **số mẫu theo thời gian** (line — đếm mẫu nhận/hoàn thành theo ngày/tuần/tháng trong khoảng `[from, to)`); (c) **tiêu hao hóa chất theo tháng** (bar — tổng lượng `out` theo tháng, theo base_unit, KHÔNG cộng gộp khác nhóm đo — đồng bộ M2 BR-CHEM-027). Field tiền (giá trị tiêu hao) chỉ vai trò tài chính (BR-RPT-002). M6 trả **số liệu**; FE render biểu đồ (ASSUMPTION-7).
- **Độ ưu tiên:** P0
- **Actor:** như FR-RPT-001 (accountant không có biểu đồ mẫu; staff phạm vi phòng).
- **Tiền điều kiện:** đã đăng nhập, có quyền báo cáo.
- **Luồng chính:**
  1. User chọn biểu đồ + khoảng thời gian + (tùy) phòng ban.
  2. Hệ thống áp scope + bộ lọc thời gian thống nhất (BR-RPT-009) → tổng hợp số liệu → trả.
- **Luồng phụ / ngoại lệ:**
  - A1: khoảng thời gian rỗng / `from > to` → 422 `INVALID_DATE_RANGE` (BR-RPT-009).
  - A2: tiêu hao hóa chất — nhiều nhóm đo → trả tách theo nhóm đo (KHÔNG cộng gộp — BR-RPT-014).
  - A3: accountant gọi biểu đồ mẫu → 403 (BR-RPT-001).
- **Hậu điều kiện:** trả số liệu biểu đồ; chỉ đọc.
- **Business Rules:** BR-RPT-001, BR-RPT-002, BR-RPT-009, BR-RPT-014.
- **Acceptance Criteria:**
  - AC1 (pie mẫu theo trạng thái): GIVEN phòng Hóa có 5 received, 3 testing, 12 done WHEN lấy biểu đồ trạng thái mẫu THEN trả {received:5, testing:3, done:12} đúng scope phòng.
  - AC2 (line theo thời gian): GIVEN khoảng 01–31/05/2026 group=month WHEN lấy biểu đồ số mẫu theo thời gian THEN trả 1 điểm tháng 5 với đúng số mẫu nhận trong khoảng `[01/05, 01/06)` (BR-RPT-009).
  - AC3 (bar tiêu hao không gộp nhóm đo): GIVEN hóa chất nhóm mass (g) và volume (mL) tiêu hao trong tháng WHEN lấy biểu đồ tiêu hao THEN trả tách 2 nhóm đo, KHÔNG cộng gộp g+mL (BR-RPT-014).
  - AC4 (lỗi input): GIVEN `from=2026-06-30`, `to=2026-06-01` WHEN lấy biểu đồ THEN trả 422 `INVALID_DATE_RANGE`.
  - AC5 (RBAC tiền): GIVEN staff WHEN lấy biểu đồ tiêu hao THEN response KHÔNG có giá trị tiền (chỉ số lượng theo đơn vị) (BR-RPT-002).
- **Data cần thiết:** `samples`(status, received_at/completed_at, department_id); `chemical_transactions`(type='out', qty_base, base_unit, at, department) + giá (chỉ vai trò tài chính).
- **API cần:** "lấy dữ liệu biểu đồ dashboard (pie/line/bar) theo bộ lọc".

---

### FR-RPT-003: Thống kê số mẫu theo bộ lọc đa tiêu chí + thời gian (R8, R10)

- **Mô tả:** Thống kê **số mẫu** theo bộ lọc đa tiêu chí thống nhất: khoảng thời gian (`[from, to)` theo `received_at`/`completed_at` — OQ#9), **phòng ban**, **trạng thái**, **loại mẫu** (nếu M1 có phân loại). Trả tổng + phân rã theo nhóm (theo trạng thái / theo phòng / theo thời gian). Đây là **thống kê đếm tổng hợp** (KHÁC `/reports/sample-on-time` của M1 — on-time rate; M6 chỉ đếm số lượng theo bộ lọc, không tính lại on-time). Tôn trọng scope vai trò (accountant không truy cập — B03).
- **Độ ưu tiên:** P0
- **Actor:** Admin, leader (mọi phòng), staff (phòng mình, 👁). Accountant → 403 (B03).
- **Tiền điều kiện:** đã đăng nhập, có `report:business`.
- **Luồng chính:**
  1. User chọn bộ lọc (thời gian + phòng + trạng thái + loại).
  2. Hệ thống áp scope (staff = phòng mình) + bộ lọc thống nhất (BR-RPT-009) → đếm `samples` → trả tổng + phân rã.
- **Luồng phụ / ngoại lệ:**
  - A1: bộ lọc rỗng → mặc định kỳ hiện tại (vd tháng này — OQ#9) hoặc yêu cầu nhập khoảng (chốt UX).
  - A2: accountant gọi → 403 (BR-RPT-001).
  - A3: staff lọc phòng khác phòng mình → ép về phòng mình hoặc 403 (BR-RPT-001 — chốt: ép scope).
- **Hậu điều kiện:** trả số liệu; chỉ đọc.
- **Business Rules:** BR-RPT-001, BR-RPT-009, BR-RPT-012.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN tháng 5/2026, phòng Hóa có 20 mẫu (8 done, 5 testing, 7 overdue) WHEN thống kê số mẫu lọc tháng 5 + phòng Hóa THEN trả tổng=20 + phân rã theo trạng thái đúng.
  - AC2 (phân rã theo thời gian): GIVEN khoảng quý 2/2026 group=month WHEN thống kê THEN trả 3 điểm (tháng 4/5/6) với số mẫu mỗi tháng.
  - AC3 (RBAC — accountant chặn): GIVEN accountant WHEN gọi thống kê số mẫu THEN trả 403 (B03, BR-RPT-001).
  - AC4 (RBAC scope — staff): GIVEN staff phòng Hóa WHEN lọc phòng=Sinh THEN kết quả vẫn chỉ phòng Hóa (ép scope) (BR-RPT-001).
  - AC5 (lỗi input): GIVEN `from > to` WHEN thống kê THEN trả 422 `INVALID_DATE_RANGE`.
- **Data cần thiết:** `samples`(status, received_at, completed_at, department_id, type?) — READ-ONLY.
- **API cần:** "thống kê số mẫu theo bộ lọc đa tiêu chí + thời gian".

---

### FR-RPT-004: Thống kê lượng hóa chất tiêu hao theo bộ lọc + thời gian (R10)

- **Mô tả:** Thống kê **lượng hóa chất tiêu hao** (giao dịch `out`) theo bộ lọc thống nhất: khoảng thời gian, phòng ban, hóa chất/nhóm đo. Trả tổng lượng theo **base_unit từng hóa chất**, **tách theo nhóm đo** (mass/volume/count — KHÔNG cộng gộp chéo nhóm, đồng bộ M2 BR-CHEM-027 / N1). Giá trị tiền tiêu hao chỉ vai trò tài chính (BR-RPT-002). **KHÁC `/reports/consumption` của M2** (báo cáo tiêu hao theo tháng/đề tài/người — chi tiết M2): M6 cung cấp **bộ lọc thống nhất chéo dashboard**; nếu KH cần đúng báo cáo tiêu hao chi tiết → dùng endpoint M2 (CONSTRAINT-1, §9). M6.2 ở đây là lớp lọc tổng hợp thống nhất — có thể **gọi/tổng hợp** số liệu M2.
- **Độ ưu tiên:** P0
- **Actor:** Admin, leader (mọi phòng), staff (phòng mình, 👁 — không tiền), accountant (👁 — có tiền, theo matrix "Báo cáo nghiệp vụ: Kế toán 👁 hóa chất").
- **Tiền điều kiện:** đã đăng nhập, có `report:business` (hóa chất); tiền cần `chemical:cost`.
- **Luồng chính:**
  1. User chọn bộ lọc (thời gian + phòng + hóa chất/nhóm).
  2. Hệ thống áp scope + bộ lọc thống nhất → tổng hợp tiêu hao (tách nhóm đo) → trả; field tiền chỉ vai trò tài chính.
- **Luồng phụ / ngoại lệ:**
  - A1: nhiều nhóm đo → trả tách (BR-RPT-014).
  - A2: staff → response không có field tiền (BR-RPT-002).
  - A3: `from > to` → 422 `INVALID_DATE_RANGE`.
- **Hậu điều kiện:** trả số liệu tiêu hao; chỉ đọc.
- **Business Rules:** BR-RPT-001, BR-RPT-002, BR-RPT-009, BR-RPT-014.
- **Acceptance Criteria:**
  - AC1 (happy + tách nhóm): GIVEN tháng 5 phòng Hóa tiêu hao 500 g (mass) + 2 L (volume) WHEN thống kê tiêu hao THEN trả tách {mass: 500 g, volume: 2 L} KHÔNG cộng gộp (BR-RPT-014).
  - AC2 (tiền chỉ tài chính): GIVEN accountant WHEN thống kê tiêu hao THEN response có `consumption_cost`; GIVEN staff cùng truy vấn THEN response KHÔNG có `consumption_cost` (BR-RPT-002, đồng bộ serializer M2).
  - AC3 (RBAC scope): GIVEN staff phòng Hóa WHEN lọc phòng Sinh THEN ép về phòng Hóa.
  - AC4 (lỗi input): GIVEN khoảng thời gian không hợp lệ THEN 422 `INVALID_DATE_RANGE`.
- **Data cần thiết:** `chemical_transactions`(type='out', qty_base, base_unit, measurement_group, at, department, unit_price) — READ-ONLY; tiền theo vai trò.
- **API cần:** "thống kê lượng hóa chất tiêu hao theo bộ lọc + thời gian" (có thể tổng hợp từ M2).

---

### FR-RPT-005: Bộ lọc thời gian + phòng ban + loại thống nhất (R8)

- **Mô tả:** Định nghĩa **bộ lọc thống nhất** dùng chung cho mọi báo cáo M6: `from`, `to` (khoảng `[from, to)`), `department_id` (phòng ban — áp scope theo vai trò), `type` (loại mẫu / nhóm đo / loại tài liệu tùy báo cáo), `group_by` (day/week/month cho phân rã thời gian). Quy ước nhất quán: khoảng nửa mở `[from, to)`, múi giờ hệ thống, default kỳ (OQ#9). FR này đặc tả **chuẩn bộ lọc** áp cho FR-RPT-002/003/004/006/010.
- **Độ ưu tiên:** P0
- **Actor:** mọi vai trò có quyền báo cáo (áp scope).
- **Tiền điều kiện:** đã đăng nhập.
- **Luồng chính:**
  1. FE gửi bộ lọc theo chuẩn (from/to/department_id/type/group_by).
  2. BE validate (from < to, department trong scope, group_by hợp lệ) → áp vào WHERE truy vấn báo cáo.
- **Luồng phụ / ngoại lệ:**
  - A1: `from >= to` → 422 `INVALID_DATE_RANGE`.
  - A2: `department_id` ngoài scope của staff → ép về phòng mình (hoặc 403 — chốt: ép) (BR-RPT-001).
  - A3: `group_by` không ∈ {day, week, month} → 422 `INVALID_GROUP_BY`.
- **Hậu điều kiện:** bộ lọc hợp lệ áp đồng nhất mọi báo cáo.
- **Business Rules:** BR-RPT-001, BR-RPT-009.
- **Acceptance Criteria:**
  - AC1 (nửa mở): GIVEN `from=2026-05-01, to=2026-06-01` WHEN lọc THEN bao gồm bản ghi 31/05, loại trừ bản ghi 01/06 (BR-RPT-009).
  - AC2 (group_by hợp lệ): GIVEN group_by=month WHEN báo cáo theo thời gian THEN phân rã theo tháng.
  - AC3 (lỗi group_by): GIVEN group_by="year-quarter" WHEN báo cáo THEN 422 `INVALID_GROUP_BY`.
  - AC4 (ép scope staff): GIVEN staff phòng Hóa truyền department=Sinh THEN áp phòng Hóa (BR-RPT-001).
- **Data cần thiết:** tham số lọc (không bảng mới).
- **API cần:** chuẩn query params dùng chung các endpoint báo cáo.

---

### FR-RPT-006: KPI nhân sự (nâng lương / hết hạn HĐ sắp tới hạn) — vai trò tài chính/HR

- **Mô tả:** KPI tổng hợp **nhân sự** cho dashboard tài chính/HR: số người **nâng lương sắp tới hạn** (`next_salary_raise_date` trong N ngày — đồng bộ CRON-3 mốc 15/7/3) + số người **hết hạn HĐ sắp tới hạn** (`contract_end_date` trong N ngày — CRON-4). Deep-link sang M4. Chỉ vai trò có quyền HR/tài chính (admin/leader/accountant); staff không thấy (BR-RPT-002). **KHÁC** quản lý hồ sơ/cron của M4 — M6 chỉ **đếm** cho dashboard.
- **Độ ưu tiên:** P1
- **Actor:** Admin, leader, accountant. Staff → không có KPI này.
- **Tiền điều kiện:** đã đăng nhập, có `hr:read` / `report:finance`.
- **Luồng chính:**
  1. Dashboard (FR-RPT-001) gom KPI nhân sự cho vai trò tài chính/HR.
  2. Đếm `hr_profiles` có `next_salary_raise_date` / `contract_end_date` trong ngưỡng → trả + deep-link.
- **Luồng phụ / ngoại lệ:**
  - A1: staff → không nhận KPI nhân sự (BR-RPT-002).
- **Hậu điều kiện:** KPI nhân sự hiển thị cho vai trò phù hợp; chỉ đọc.
- **Business Rules:** BR-RPT-001, BR-RPT-002, BR-RPT-007.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN 3 người nâng lương trong 30 ngày, 2 người hết hạn HĐ trong 30 ngày WHEN leader mở dashboard THEN KPI nâng lương=3, hết hạn HĐ=2, deep-link M4.
  - AC2 (RBAC — staff không thấy): GIVEN staff WHEN mở dashboard THEN KHÔNG có KPI nâng lương/HĐ (BR-RPT-002).
  - AC3 (accountant thấy): GIVEN accountant WHEN mở dashboard THEN CÓ KPI nâng lương/HĐ (tài chính, B03).
- **Data cần thiết:** `hr_profiles`(next_salary_raise_date, contract_end_date) — READ-ONLY.
- **API cần:** gộp trong dashboard (FR-RPT-001) cho vai trò tài chính/HR.

---

### FR-RPT-007: Thống kê truy cập hệ thống — lượt truy cập / tải / chỉnh sửa (R15)

- **Mô tả:** Thống kê truy cập **toàn hệ thống** (R15): (a) **lượt truy cập** = số `access_stats` (xem trang) + số `LOGIN` trong `audit_logs`; (b) **lượt tải file** = `document_access_log.action='download'` (+ tùy chọn attachment khác — OQ#6); (c) **lượt chỉnh sửa** = số action CUD trong `audit_logs`. Thống kê **theo user** + **theo khoảng thời gian** (bộ lọc thống nhất) + **theo loại hành động**; có **top N** user nhiều nhất mỗi loại. **CHỈ admin/leader** (BR-RPT-010 — nhạy cảm, giám sát hành vi). **KHÁC M3 `/documents/access-stats`** (chi tiết theo từng tài liệu) — M6.3 là cấp hệ thống (CONSTRAINT-1, §9).
- **Độ ưu tiên:** P1
- **Actor:** **Admin, leader CHỈ** (BR-RPT-010). Staff/accountant → 403.
- **Tiền điều kiện:** đã đăng nhập; vai trò ∈ {admin, leader}.
- **Luồng chính:**
  1. Admin/leader chọn bộ lọc (thời gian + user + loại hành động).
  2. Hệ thống đếm từ `access_stats` + `audit_logs` (+ `document_access_log` cho tải) theo bộ lọc → trả tổng + theo user + top N + (tùy) phân rã thời gian.
- **Luồng phụ / ngoại lệ:**
  - A1: staff/accountant gọi → 403 `FORBIDDEN` (BR-RPT-010).
  - A2: khoảng thời gian quá rộng (vd > 1 năm) → cảnh báo / phân trang / giới hạn (NFR-PERF-RPT-002; OQ#7 async cho kỳ lớn).
  - A3: `from > to` → 422 `INVALID_DATE_RANGE`.
- **Hậu điều kiện:** trả thống kê truy cập; chỉ đọc (đếm).
- **Business Rules:** BR-RPT-004, BR-RPT-009, BR-RPT-010.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN tháng 5 có 1200 lượt truy cập, 80 lượt tải, 350 lượt chỉnh sửa WHEN admin thống kê tháng 5 THEN trả đúng 3 con số + top N user.
  - AC2 (lượt chỉnh sửa = CUD audit): GIVEN trong kỳ có 350 action create/update/delete trong audit_logs WHEN tính lượt chỉnh sửa THEN = 350 (BR-RPT-004); action `read`/`LOGIN`/`download` KHÔNG tính vào "chỉnh sửa".
  - AC3 (RBAC — chỉ admin/leader): GIVEN staff WHEN gọi thống kê truy cập hệ thống THEN trả 403; GIVEN accountant THEN trả 403 (BR-RPT-010).
  - AC4 (theo user): GIVEN user X có 200 lượt truy cập, 30 chỉnh sửa WHEN lọc user=X THEN trả đúng số của X.
  - AC5 (lỗi input): GIVEN `from > to` THEN 422 `INVALID_DATE_RANGE`.
  - AC6 (KHÁC M3): GIVEN admin xem thống kê truy cập hệ thống WHEN so với `/documents/access-stats` của M3 THEN M6.3 là tổng hợp hệ thống (login/xem trang/CUD), KHÔNG thay thế thống kê view/download per-tài-liệu của M3.
- **Data cần thiết:** `access_stats`(user_id, path, at), `audit_logs`(user_id, action, at — đếm LOGIN + CUD), `document_access_log`(action='download', user_id, at) — READ-ONLY.
- **API cần:** "thống kê truy cập hệ thống (lượt truy cập/tải/chỉnh sửa) theo user/thời gian + top N".

---

### FR-RPT-008: Thống kê truy cập theo user (chi tiết 1 người)

- **Mô tả:** Xem chi tiết hoạt động của **một user**: lượt truy cập / tải / chỉnh sửa của user đó theo thời gian; (tùy) timeline action gần nhất. Chỉ admin/leader (BR-RPT-010). Phục vụ giám sát / điều tra khi cần (đồng bộ §8.4 truy vết).
- **Độ ưu tiên:** P2
- **Actor:** Admin, leader. Khác → 403.
- **Tiền điều kiện:** đã đăng nhập; vai trò ∈ {admin, leader}.
- **Luồng chính:**
  1. Admin/leader chọn user + khoảng thời gian.
  2. Hệ thống đếm/lấy hoạt động user đó từ access_stats + audit_logs (+ document_access_log) → trả.
- **Luồng phụ / ngoại lệ:**
  - A1: staff/accountant → 403 (BR-RPT-010).
  - A2: user không tồn tại → 404.
- **Hậu điều kiện:** trả hoạt động của user; chỉ đọc.
- **Business Rules:** BR-RPT-004, BR-RPT-009, BR-RPT-010.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN user X trong tháng 5 WHEN leader xem chi tiết X THEN trả lượt truy cập/tải/chỉnh sửa của X + (tùy) timeline.
  - AC2 (RBAC): GIVEN staff WHEN xem chi tiết user khác THEN 403 (BR-RPT-010).
  - AC3 (không tồn tại): GIVEN user_id sai WHEN xem THEN 404.
- **Data cần thiết:** như FR-RPT-007 lọc theo `user_id`.
- **API cần:** "thống kê truy cập chi tiết theo 1 user".

---

### FR-RPT-009: Hạ tầng ghi access_stats — middleware lượt truy cập (R15)

- **Mô tả:** **Middleware** ghi tự động vào `access_stats` (M7) mỗi lượt truy cập đủ điều kiện: `user_id` (NULL nếu chưa đăng nhập), `path`, `method`, `status_code`, `ip`, `at`. Ghi cho **whitelist trang chính** (default: GET các trang chính + login — OQ#1), KHÔNG ghi mọi request (tránh phình bảng + nhiễu tài nguyên tĩnh/health-check). Ghi **bất đồng bộ / không chặn** request (không làm chậm response — NFR-PERF-RPT-003). Đây là **hạ tầng của M6.3** (bảng đã có ở M7 nhưng chưa được ghi tự động). KHÔNG ghi sensitive (query string nhạy cảm lọc — đồng bộ logging.md).
- **Độ ưu tiên:** P1
- **Actor:** hệ thống (middleware), áp cho mọi request đủ điều kiện.
- **Tiền điều kiện:** ứng dụng đang xử lý request.
- **Luồng chính:**
  1. Request đến → middleware kiểm tra có thuộc whitelist ghi access_stats không (BR-RPT-005).
  2. Nếu có → sau khi xử lý, ghi (không chặn) `access_stats`(user_id, path, method, status_code, ip, at).
- **Luồng phụ / ngoại lệ:**
  - A1: request thuộc blacklist (static, health-check, asset) → KHÔNG ghi (BR-RPT-005).
  - A2: lỗi ghi access_stats → log WARN, KHÔNG làm fail request chính (BR-RPT-013 — degrade mềm).
  - A3: query string chứa token/secret → lọc trước khi ghi `path` (logging.md).
- **Hậu điều kiện:** lượt truy cập được ghi cho thống kê M6.3; request chính không bị ảnh hưởng.
- **Business Rules:** BR-RPT-004, BR-RPT-005, BR-RPT-013.
- **Acceptance Criteria:**
  - AC1 (happy ghi): GIVEN user đăng nhập mở trang dashboard WHEN request hoàn tất THEN có 1 bản ghi `access_stats`(user_id, path=/dashboard, method=GET, status_code=200).
  - AC2 (không ghi static/health): GIVEN request tới `/health` hoặc asset tĩnh WHEN xử lý THEN KHÔNG ghi access_stats (BR-RPT-005).
  - AC3 (không chặn request): GIVEN ghi access_stats lỗi (DB tạm lỗi) WHEN request chính THEN request chính vẫn trả bình thường, lỗi ghi → log WARN (BR-RPT-013).
  - AC4 (không log sensitive): GIVEN path có query `?token=...` WHEN ghi access_stats THEN `path` đã lọc bỏ token (logging.md).
  - AC5 (performance): GIVEN middleware bật WHEN đo response các endpoint THEN overhead trung bình < 5ms / request (NFR-PERF-RPT-003).
- **Data cần thiết:** GHI `access_stats`(user_id, path, method, status_code, ip, at) — **ngoại lệ READ-ONLY duy nhất ở tầng dữ liệu hệ thống** (CONSTRAINT-2).
- **API cần:** middleware (không endpoint nghiệp vụ); cấu hình whitelist trang chính.

---

### FR-RPT-010: Xuất báo cáo Excel (R4)

- **Mô tả:** Xuất **Excel** các báo cáo tổng hợp M6: (a) snapshot dashboard KPI; (b) thống kê số mẫu theo bộ lọc (FR-RPT-003); (c) thống kê tiêu hao hóa chất (FR-RPT-004); (d) thống kê truy cập hệ thống (FR-RPT-007 — chỉ admin/leader). Xuất tôn trọng **RBAC scope** (chỉ xuất dữ liệu user được phép xem — accountant không xuất được báo cáo mẫu; staff chỉ phòng mình + không field tiền; R15 chỉ admin/leader). File Excel có header + kỳ báo cáo + người xuất + thời điểm. Thao tác xuất ghi `audit_logs` (FR-RPT-011).
- **Độ ưu tiên:** P0
- **Actor:** theo từng báo cáo (mẫu/tiêu hao: admin/leader/staff phòng; tài chính: + accountant; truy cập hệ thống: admin/leader).
- **Tiền điều kiện:** đã đăng nhập, có quyền với báo cáo tương ứng.
- **Luồng chính:**
  1. User chọn báo cáo + bộ lọc → "Xuất Excel".
  2. Hệ thống áp RBAC scope + bộ lọc → tổng hợp → sinh file Excel (sync) → trả binary (`Content-Disposition: attachment`) → ghi `audit_logs` `REPORT_EXPORT`.
- **Luồng phụ / ngoại lệ:**
  - A1: user xuất báo cáo ngoài quyền (accountant xuất báo cáo mẫu; staff xuất R15) → 403 (BR-RPT-001/010).
  - A2: dữ liệu rất lớn (kỳ rộng) → cân nhắc async + thông báo khi xong (OQ#7); bản đầu sync với giới hạn.
  - A3: bộ lọc không hợp lệ → 422.
- **Hậu điều kiện:** file Excel tải về đúng scope; audit ghi thao tác xuất.
- **Business Rules:** BR-RPT-001, BR-RPT-002, BR-RPT-009, BR-RPT-010, BR-RPT-012.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN leader chọn thống kê số mẫu tháng 5 WHEN xuất Excel THEN tải file `.xlsx` đúng số liệu + header (kỳ, người xuất, thời điểm); audit `REPORT_EXPORT`.
  - AC2 (RBAC scope xuất): GIVEN accountant WHEN xuất báo cáo số mẫu THEN 403; GIVEN staff phòng Hóa xuất tiêu hao THEN file chỉ phòng Hóa + KHÔNG field tiền (BR-RPT-001/002).
  - AC3 (RBAC R15): GIVEN staff WHEN xuất thống kê truy cập hệ thống THEN 403 (BR-RPT-010).
  - AC4 (audit): GIVEN bất kỳ lần xuất thành công WHEN hoàn tất THEN `audit_logs` có `REPORT_EXPORT` (report type, kỳ, user) (BR-RPT-012).
- **Data cần thiết:** dữ liệu tổng hợp các FR trên; sinh file (không lưu binary DB; lưu MinIO nếu cần — C01).
- **API cần:** "xuất Excel báo cáo <loại> theo bộ lọc".

---

### FR-RPT-011: Xuất báo cáo PDF + audit thao tác xuất (R4, §8.4)

- **Mô tả:** Xuất **PDF** cho các báo cáo cần định dạng trình bày (danh sách báo cáo cần PDF — OQ#3; vd báo cáo tổng hợp dashboard kỳ, báo cáo phục vụ đánh giá VILAS). PDF có logo/header chuẩn + kỳ + người xuất + thời điểm. Mọi thao tác xuất (Excel + PDF) ghi `audit_logs` action=`REPORT_EXPORT` (ai xuất báo cáo gì, kỳ nào — truy vết §8.4). Tôn trọng RBAC scope như FR-RPT-010.
- **Độ ưu tiên:** P1
- **Actor:** như FR-RPT-010 theo từng báo cáo.
- **Tiền điều kiện:** đã đăng nhập, có quyền với báo cáo + báo cáo nằm trong danh sách hỗ trợ PDF (OQ#3).
- **Luồng chính:**
  1. User chọn báo cáo hỗ trợ PDF + bộ lọc → "Xuất PDF".
  2. Hệ thống áp RBAC scope → tổng hợp → render PDF → trả binary → ghi `audit_logs` `REPORT_EXPORT`.
- **Luồng phụ / ngoại lệ:**
  - A1: báo cáo không hỗ trợ PDF → 422 `PDF_NOT_SUPPORTED` (hoặc fallback Excel — chốt OQ#3).
  - A2: ngoài quyền → 403.
- **Hậu điều kiện:** PDF tải về đúng scope; audit ghi.
- **Business Rules:** BR-RPT-001, BR-RPT-009, BR-RPT-010, BR-RPT-012.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN leader chọn báo cáo dashboard kỳ tháng 5 WHEN xuất PDF THEN tải PDF có logo/header + số liệu đúng; audit `REPORT_EXPORT` type=PDF.
  - AC2 (không hỗ trợ PDF): GIVEN báo cáo chưa cấu hình PDF WHEN xuất PDF THEN 422 `PDF_NOT_SUPPORTED` (hoặc fallback theo OQ#3).
  - AC3 (RBAC): GIVEN accountant WHEN xuất PDF báo cáo mẫu THEN 403.
  - AC4 (audit đầy đủ): GIVEN nhiều lần xuất (Excel + PDF) WHEN rà audit THEN mỗi lần có 1 `REPORT_EXPORT` (BR-RPT-012).
- **Data cần thiết:** dữ liệu tổng hợp + template PDF; ghi `audit_logs`.
- **API cần:** "xuất PDF báo cáo <loại> theo bộ lọc".

---

## 4. Business Rules

| ID | Quy tắc | Lý do nghiệp vụ | Hệ quả nếu vi phạm |
|----|---------|-----------------|--------------------|
| BR-RPT-001 | **Scope theo vai trò ở tầng API:** admin/leader = toàn hệ thống; staff = chỉ phòng mình (👁); **accountant = chỉ tài chính (chi phí hóa chất + lương/HĐ), KHÔNG nhận KPI/báo cáo mẫu/kết quả** (B03). Truyền phòng ngoài scope → ép về phòng mình (staff). | Cách ly dữ liệu phòng ban (R13) + cách ly nghiệp vụ lab khỏi tài chính (B03); RBAC matrix demo-scope "Báo cáo" | 403 / dữ liệu rò rỉ ngoài quyền (OWASP A01) |
| BR-RPT-002 | **Field tiền** (giá/giá trị hóa chất, lương) chỉ trả cho vai trò tài chính (admin/leader/accountant với `chemical:cost`); **KTV/staff KHÔNG nhận field tiền** ở mọi báo cáo (strip ở serializer, đồng bộ M2 NFR-SEC-CHEM-001) | Bảo mật thông tin tài chính; đồng bộ ẩn giá của M2 | KTV đọc được giá → rò rỉ tài chính |
| BR-RPT-003 | **KPI mẫu** đếm từ `samples`: số theo `status` + số `overdue` (status=overdue hoặc `completed_at > deadline_at`); đồng bộ định nghĩa trạng thái/overdue của M1 (KHÔNG định nghĩa lại on-time rate) | Dùng đúng định nghĩa nguồn (M1); tránh số liệu lệch giữa dashboard và M1 | Số liệu dashboard ≠ M1 → mất tin cậy |
| BR-RPT-004 | **R15 nguồn đếm cố định:** lượt truy cập = `access_stats` (xem trang) + `audit_logs` action `LOGIN`; lượt tải = `document_access_log.action='download'` (+ tùy chọn attachment khác — OQ#6); lượt chỉnh sửa = action CUD (create/update/delete) trong `audit_logs` | R15; tách high-volume (access_stats) khỏi pháp lý (audit_logs) — M7 D11; không tạo bảng đếm mới | Đếm sai / trùng nguồn |
| BR-RPT-005 | **Middleware access_stats** chỉ ghi whitelist trang chính (default: GET trang chính + login); KHÔNG ghi static/asset/health-check; ghi không chặn request; lọc query nhạy cảm | Tránh phình bảng access_stats + nhiễu; không làm chậm request (logging.md) | Bảng phình / response chậm / log sensitive |
| BR-RPT-006 | **KPI hóa chất** đếm từ `chemical_lots`/`chemicals`: lô sắp hết hạn (`expiry_date` trong N ngày) / tới hạn kiểm tra lại (`recheck_date`) + hóa chất tồn < `reorder_threshold`; đồng bộ định nghĩa M2 (KHÔNG làm lại `/inventory/low-stock`) | Dùng đúng định nghĩa nguồn M2 | Số liệu lệch M2 |
| BR-RPT-007 | **KPI nhân sự** đếm từ `hr_profiles`: nâng lương (`next_salary_raise_date` trong N ngày, mốc đồng bộ CRON-3) + hết hạn HĐ (`contract_end_date`, CRON-4); chỉ vai trò tài chính/HR | Dùng đúng định nghĩa M4; KPI tài chính | Số liệu lệch M4 / rò rỉ cho staff |
| BR-RPT-008 | **KPI thiết bị** đếm từ `equipments`: quá hạn hiệu chuẩn (`next_due_date < today`) + sắp tới hạn (≤ 30 ngày); đồng bộ định nghĩa badge M5 (BR-EQP-009/010) | Dùng đúng định nghĩa M5 | Số liệu lệch M5 |
| BR-RPT-009 | **Bộ lọc thời gian thống nhất:** khoảng nửa mở `[from, to)` (bao gồm from, loại trừ to), múi giờ hệ thống; `from < to`; `group_by` ∈ {day, week, month}; default kỳ khi rỗng (OQ#9) | Nhất quán mọi báo cáo M6; tránh lệch biên (off-by-one ngày) | Số liệu sai biên / không nhất quán giữa báo cáo |
| BR-RPT-010 | **Thống kê truy cập hệ thống (R15 / M6.3) CHỈ admin/leader**; staff/accountant gọi → 403 | Giám sát hành vi người dùng toàn hệ thống là dữ liệu nhạy cảm; tách khỏi `report:business` | Rò rỉ thông tin giám sát người dùng |
| BR-RPT-011 | **Cache dashboard/KPI** ở Redis với TTL ngắn (OQ#2 — default ~60–300s); cache key gồm vai trò + phòng + bộ lọc; invalidate theo TTL (không realtime) | Đạt P95 < 2s với ~40 user (NFR-PERF-RPT-001); giảm tải DB | Dashboard chậm > 2s / số liệu cũ quá hạn TTL |
| BR-RPT-012 | **Mọi thao tác xuất báo cáo** (Excel + PDF) ghi `audit_logs` action=`REPORT_EXPORT` (user, report type, kỳ, scope) | Truy vết ai xuất dữ liệu gì (§8.4 + bảo mật rò rỉ dữ liệu) | Không truy vết được rò rỉ dữ liệu qua export |
| BR-RPT-013 | **Degrade mềm:** lỗi/timeout 1 module nguồn (hoặc lỗi ghi access_stats) → KPI module đó "không khả dụng" / log WARN, KHÔNG làm fail toàn dashboard/request | Dashboard tổng hợp nhiều nguồn — 1 nguồn lỗi không nên sập cả màn | Cả dashboard sập vì 1 KPI lỗi |
| BR-RPT-014 | **KHÔNG cộng gộp lượng hóa chất chéo nhóm đo** (mass/volume/count) — tách theo nhóm đo + theo base_unit (đồng bộ M2 BR-CHEM-027 / N1) | Cộng g + mL là vô nghĩa (sai số đo lường); đồng bộ M2 | Số liệu tiêu hao sai bản chất |

---

## 5. Use Case chính

### UC-RPT-01: Ban lãnh đạo xem dashboard tổng hợp toàn hệ thống (R8, R10)
- **Actor chính:** leader / Admin.
- **Tiền điều kiện:** cần nắm toàn cảnh phòng thí nghiệm 1 màn.
- **Luồng:**
  1. Leader mở Dashboard (FR-RPT-001).
  2. Hệ thống áp scope toàn hệ thống → gom KPI: mẫu theo trạng thái + overdue (BR-RPT-003), lô hóa chất sắp hết hạn + tồn thấp (BR-RPT-006), thiết bị quá hạn hiệu chuẩn (BR-RPT-008), nâng lương/HĐ sắp tới hạn (BR-RPT-007), tài liệu chờ duyệt, thông báo chưa đọc — qua cache Redis (BR-RPT-011).
  3. Hiển thị biểu đồ (FR-RPT-002): pie trạng thái mẫu, line mẫu theo thời gian, bar tiêu hao hóa chất.
  4. Leader click KPI "mẫu overdue" → deep-link sang danh sách mẫu overdue (M1).
- **Ngoại lệ:** 1 module nguồn lỗi → KPI đó "không khả dụng", phần còn lại vẫn hiển thị (BR-RPT-013).
- **Hậu điều kiện:** leader nắm toàn cảnh; lượt truy cập ghi access_stats (FR-RPT-009).
- **Liên kết FR:** FR-RPT-001, 002, 006.

### UC-RPT-02: Staff xem dashboard phòng mình (scope phòng)
- **Actor chính:** staff (KTV).
- **Tiền điều kiện:** staff cần theo dõi công việc phòng mình.
- **Luồng:**
  1. Staff phòng Hóa mở Dashboard (FR-RPT-001).
  2. Hệ thống áp scope phòng Hóa → KPI mẫu/hóa chất/thiết bị/tài liệu chỉ phòng Hóa; KHÔNG field tiền (BR-RPT-002); KHÔNG KPI nhân sự/tài chính.
- **Ngoại lệ:** staff cố lọc phòng khác → ép về phòng Hóa (BR-RPT-001).
- **Hậu điều kiện:** staff thấy đúng phạm vi phòng.
- **Liên kết FR:** FR-RPT-001, 003, 004.

### UC-RPT-03: Lọc thống kê số mẫu / tiêu hao hóa chất theo thời gian (R8, R10)
- **Actor chính:** leader / Admin / staff (phòng) / accountant (chỉ hóa chất).
- **Tiền điều kiện:** cần thống kê theo kỳ.
- **Luồng:**
  1. User chọn bộ lọc thống nhất (FR-RPT-005): from/to + phòng + loại + group_by.
  2. Thống kê số mẫu (FR-RPT-003) hoặc tiêu hao hóa chất (FR-RPT-004) → trả tổng + phân rã (theo trạng thái / thời gian / nhóm đo — không gộp chéo nhóm BR-RPT-014).
  3. (Tùy) xuất Excel (FR-RPT-010).
- **Ngoại lệ:** accountant gọi thống kê mẫu → 403 (B03); `from > to` → 422; staff lọc phòng khác → ép scope.
- **Hậu điều kiện:** số liệu đúng bộ lọc + scope; (tùy) file xuất + audit.
- **Liên kết FR:** FR-RPT-003, 004, 005, 010.

### UC-RPT-04: Admin xem thống kê truy cập hệ thống (R15)
- **Actor chính:** Admin / leader (CHỈ).
- **Tiền điều kiện:** middleware access_stats đang ghi (FR-RPT-009); có audit_logs + document_access_log.
- **Luồng:**
  1. Admin chọn bộ lọc (thời gian + user + loại hành động) (FR-RPT-007).
  2. Hệ thống đếm: lượt truy cập (access_stats + LOGIN), lượt tải (document_access_log download), lượt chỉnh sửa (CUD audit_logs) (BR-RPT-004) → trả tổng + theo user + top N.
  3. (Tùy) xem chi tiết 1 user (FR-RPT-008) hoặc xuất Excel (FR-RPT-010).
- **Ngoại lệ:** staff/accountant gọi → 403 (BR-RPT-010); kỳ quá rộng → async/giới hạn (OQ#7).
- **Hậu điều kiện:** admin có số liệu giám sát truy cập; KHÁC thống kê per-tài-liệu của M3.
- **Liên kết FR:** FR-RPT-007, 008, 009, 010.

### UC-RPT-05: Xuất báo cáo tổng hợp (Excel/PDF) phục vụ báo cáo nội bộ / VILAS (R4)
- **Actor chính:** leader / Admin (accountant cho báo cáo tài chính).
- **Tiền điều kiện:** đã có dữ liệu trong kỳ; có quyền với báo cáo.
- **Luồng:**
  1. User chọn báo cáo + bộ lọc → xuất Excel (FR-RPT-010) hoặc PDF (FR-RPT-011) nếu hỗ trợ.
  2. Hệ thống áp RBAC scope (chỉ dữ liệu được phép) → sinh file (header: kỳ, người xuất, thời điểm) → tải về.
  3. Ghi `audit_logs` `REPORT_EXPORT` (BR-RPT-012).
- **Ngoại lệ:** ngoài quyền → 403; báo cáo không hỗ trợ PDF → 422 / fallback (OQ#3); dữ liệu lớn → async (OQ#7).
- **Hậu điều kiện:** file đúng scope tải về; thao tác xuất truy vết được (§8.4).
- **Liên kết FR:** FR-RPT-010, 011.

---

## 6. Yêu cầu phi chức năng (NFR)

Theo template `~/.claude/rules/nfr.md`. Con số định cỡ cho quy mô **~40 user** (C03), staging tương đương production (Docker Compose, ~2–4 vCPU/8GB). Giả định cao điểm: ~5–10 concurrent users mở dashboard. Dataset giả định: ~10,000 mẫu, ~2,000 thiết bị, ~50,000 bản ghi audit_logs, ~100,000 bản ghi access_stats.

```
NFR-PERF-RPT-001: Dashboard tổng hợp < 2s (Must)
────────────────────────────────────────────────────
Mô tả:     Dashboard KPI tổng hợp (gom mẫu/hóa chất/thiết bị/nhân sự/tài liệu/
           thông báo) phản hồi đủ nhanh để dùng hằng ngày (~40 user).
Metric:    P95 < 2000ms | P99 < 3000ms (lần đầu, không cache); P95 < 300ms khi
           trúng cache Redis (BR-RPT-011)
Tool đo:   k6 (tests/performance/dashboard.js)
Điều kiện: 10 concurrent users, dataset thật (~10K mẫu, ~2K thiết bị, ~50K audit),
           staging
Pass:      p(95) < 2000ms suốt 10 phút ở 10 concurrent users, error rate < 1%
Fail:      p(95) ≥ 2000ms → tối ưu query (dùng index module nguồn) + tăng cache TTL
           + gom query (1 round-trip) / tính KPI nặng async
Ưu tiên:  Must Have — yêu cầu hiệu năng chốt với KH (đề bài)
```
```
NFR-PERF-RPT-002: Thống kê theo bộ lọc + truy cập hệ thống (Should)
────────────────────────────────────────────────────
Metric:    P95 < 2000ms cho thống kê số mẫu/tiêu hao kỳ 1 năm; thống kê truy cập
           hệ thống (R15) kỳ 1 tháng P95 < 3000ms (audit/access_stats lớn)
Tool đo:   k6 (tests/performance/report-stats.js)
Điều kiện: 5 concurrent users, dataset thật
Pass:      đạt ngưỡng; query dùng index (access_stats(at)/(user_id,at);
           audit_logs(at)/(user_id,at) — đã có ở M7)
Fail:      vượt ngưỡng → index thêm theo (action, at) cho đếm CUD; kỳ rộng → async (OQ#7)
Ưu tiên:  Should Have
```
```
NFR-PERF-RPT-003: Middleware access_stats không làm chậm request (Must)
────────────────────────────────────────────────────
Mô tả:     Ghi access_stats không được làm chậm request chính (ghi không chặn).
Metric:    Overhead trung bình < 5ms/request; không tăng P95 endpoint quá 5%
Tool đo:   k6 so sánh có/không middleware
Pass:      overhead < 5ms; P95 không tăng > 5%; lỗi ghi không fail request (BR-RPT-013)
Fail:      overhead ≥ 5ms → ghi bất đồng bộ (queue/background) thay vì inline
Ưu tiên:  Must Have
```
```
NFR-SEC-RPT-001: RBAC scope + cách ly tài chính ở tầng API (Must)
────────────────────────────────────────────────────
Mô tả:     Enforce scope theo vai trò ở API (không chỉ FE): accountant KHÔNG nhận
           KPI/báo cáo mẫu/kết quả (B03); KTV/staff KHÔNG nhận field tiền; staff
           chỉ phòng mình; thống kê truy cập hệ thống (R15) chỉ admin/leader.
Metric:    Ma trận test 4 vai trò × mọi endpoint M6 pass 100%; 0 rò rỉ KPI mẫu cho
           accountant; 0 field tiền trả cho staff; 100% staff/accountant bị 403 ở R15
Tool đo:   Test RBAC tự động (security-auditor) + manual + kiểm tra response shape
Pass:      0 truy cập/rò rỉ trái phép (KPI mẫu, field tiền, R15)
Fail:      bất kỳ rò rỉ → block go-live (OWASP A01)
Ưu tiên:  Must Have
```
```
NFR-SEC-RPT-002: Xuất báo cáo an toàn + truy vết (Must)
────────────────────────────────────────────────────
Metric:    File xuất chỉ chứa dữ liệu trong scope user; mọi lần xuất ghi audit
           REPORT_EXPORT (user, report, kỳ); không lộ field tiền/mẫu ngoài quyền
           trong file; không lộ access_stats R15 cho non-admin/leader
Tool đo:   Test xuất theo từng vai trò + rà nội dung file + đếm audit
Pass:      file đúng scope 100%; audit/lần xuất = 100% (BR-RPT-012)
Ưu tiên:  Must Have
```
```
NFR-INTEG-RPT-001: Số liệu dashboard khớp module nguồn (Must)
────────────────────────────────────────────────────
Mô tả:     KPI trên dashboard phải khớp số liệu module nguồn (không định nghĩa lại
           sai lệch): số mẫu overdue = M1; lô sắp hết hạn = M2; thiết bị quá hạn = M5.
Metric:    Với cùng bộ lọc + scope: KPI M6 = số liệu endpoint/định nghĩa module nguồn
           (sai khác = 0 bản ghi)
Tool đo:   Test đối chiếu KPI M6 vs định nghĩa M1/M2/M5
Pass:      0 sai lệch số liệu (BR-RPT-003/006/008)
Fail:      sai lệch → đồng bộ định nghĩa với module nguồn
Ưu tiên:  Must Have
```
```
NFR-AVAIL-RPT-001: Degrade mềm khi 1 nguồn lỗi (Should)
────────────────────────────────────────────────────
Metric:    Lỗi/timeout 1 module nguồn → KPI đó "không khả dụng", dashboard vẫn trả
           HTTP 200 với các KPI còn lại; lỗi ghi access_stats không fail request chính
Tool đo:   Chaos test (giả lập lỗi 1 nguồn) + test middleware lỗi ghi
Pass:      dashboard không sập khi 1 KPI lỗi; request chính không fail (BR-RPT-013)
Ưu tiên:  Should Have
```
```
NFR-CONSISTENCY-RPT-001: Bộ lọc thời gian nhất quán (Must)
────────────────────────────────────────────────────
Metric:    Mọi báo cáo dùng khoảng nửa mở [from, to) + cùng múi giờ; cùng bộ lọc cho
           kết quả nhất quán giữa dashboard, thống kê, file xuất (0 lệch biên ngày)
Tool đo:   Test biên (boundary): bản ghi đúng 00:00 from / 00:00 to
Pass:      bản ghi tại from được tính, tại to bị loại; nhất quán mọi endpoint (BR-RPT-009)
Ưu tiên:  Must Have
```
```
NFR-MAINT-RPT-001: Test coverage domain báo cáo (Must)
────────────────────────────────────────────────────
Metric:    Service tính KPI/scope vai trò/bộ lọc thời gian/đếm R15 (CUD vs LOGIN vs
           download)/cache/degrade mềm coverage ≥ 85%; module M6 overall ≥ 70%
Tool đo:   pytest --cov
Pass:      ≥ 85% domain, ≥ 70% module; CI block nếu drop > 5%
Ưu tiên:  Must Have
```
```
NFR-OBS-RPT-001: Logging & slow query (Should)
────────────────────────────────────────────────────
Metric:    Mọi request M6 có correlation_id; query aggregate > 1s log WARN (slow
           query — logging.md); xuất báo cáo log INFO; lỗi nguồn/cache/MinIO log
           ERROR kèm stack (không lộ ra client); middleware lỗi ghi log WARN
Tool đo:   Rà log + test slow query
Pass:      truy được 1 request dashboard từ FE → query DB qua correlation_id;
           slow query aggregate được ghi
Ưu tiên:  Should Have
```

---

## 7. Giả định & Ràng buộc (tổng hợp)

**Assumptions:** xem §2.5 (ASSUMPTION-1..7).

**Constraints:** xem §2.4 (CONSTRAINT-1..10) — đặc biệt **CONSTRAINT-1 (KHÔNG trùng endpoint module khác)** và **CONSTRAINT-2 (READ-ONLY, ngoại lệ duy nhất = middleware ghi access_stats + audit export)**.

**Ghi chú cấu trúc dữ liệu cho `schema-designer` / `api-designer`** (mức logic — M6 KHÔNG sở hữu bảng nghiệp vụ riêng):
- **M6 KHÔNG tạo bảng nghiệp vụ mới.** Đọc bảng có sẵn: `samples` (M1), `chemical_lots`/`chemicals`/`chemical_transactions` (M2), `document_versions`/`document_access_log` (M3), `hr_profiles` (M4), `equipments` (M5), `audit_logs`/`access_stats`/`notifications` (M7).
- **`access_stats` (M7 — đã có DDL, dòng 375-385 của 08-contract-m7-schema):** M6.3 GHI qua middleware (FR-RPT-009) + ĐỌC để thống kê (FR-RPT-007/008). Index `idx_access_user_at (user_id, at DESC)` + `idx_access_at (at DESC)` đã có (M7 dòng 495-497) — đủ cho M6.3. Cân nhắc thêm index `access_stats(at)` đã có; nếu thống kê theo path nhiều → cân nhắc index path (OQ — không bắt buộc bản đầu).
- **`audit_logs` (M7 — append-only §8.4):** đếm action CUD = lượt chỉnh sửa (R15); đếm `LOGIN` = lượt đăng nhập; index `idx_audit_at`, `idx_audit_user_at` đã có. Đếm theo (action, at) — nếu nặng, schema-designer cân nhắc index `audit_logs(action, at)` (gợi ý, không bắt buộc cho ~40 user).
- **`document_access_log` (M3):** đếm `action='download'` = lượt tải hệ thống (R15). M6 đọc, KHÔNG tạo/sửa bảng này.
- **Cache (Redis):** key dashboard/KPI = (role, department_scope, filter); TTL OQ#2; M6 cần Redis (đã có ở stack).
- **Xuất file:** Excel (openpyxl/xlsxwriter) + PDF (weasyprint/reportlab — chốt ở contract); file lớn → MinIO + async (OQ#7).
- **`roles_permissions` (M7 — cần seed/dùng cho M6):** `report:business` (admin/leader scope all; staff scope department; accountant — chỉ phần hóa chất, app lọc resource), `report:finance` (admin/leader/accountant scope all; staff KHÔNG) — đã seed (08-contract-m7-schema dòng 565/578/586-587). **Thống kê truy cập hệ thống R15 cần quyền riêng** (vd `report:system_access` hoặc dùng `audit:read` — chỉ admin/leader; 08 đã seed `audit:read` cho admin/leader) → **api-designer/schema chốt**: dùng `audit:read` (chỉ admin/leader) cho M6.3 là phù hợp (đồng bộ tinh thần audit chỉ admin/leader, demo-scope matrix "Audit log: Admin ✅, Lãnh đạo ✅").

---

## 8. OPEN QUESTIONS (cần KH / Tech Lead trả lời — phần lớn KHÔNG chặn `/contract`)

| # | Câu hỏi | Tại sao cần biết | Ảnh hưởng nếu chưa rõ (default đề xuất) | Người trả lời | Deadline | Chặn contract? |
|---|---------|------------------|------------------------------------------|---------------|----------|----------------|
| 1 | **Middleware access_stats ghi MỌI request hay chỉ trang chính?** (whitelist nào?) | Phạm vi ghi R15 (FR-RPT-009, BR-RPT-005); phình bảng | Default: **chỉ whitelist trang chính (GET) + login**, KHÔNG ghi static/health/asset | Tech Lead + KH | Trước `/contract` (ưu tiên) | ⚠️ **Nên chốt** — ảnh hưởng định nghĩa "lượt truy cập" + dung lượng (default an toàn) |
| 2 | **Cache dashboard TTL bao lâu?** (số liệu "mới" tới mức nào KH chấp nhận) | Cache dashboard (BR-RPT-011, NFR-PERF-RPT-001) | Default: **TTL 60–300s** (số liệu trễ tối đa vài phút — chấp nhận cho dashboard quản lý) | Ban lãnh đạo | Trước `/contract` | ⚠️ **Nên chốt** — ảnh hưởng độ "tươi" số liệu vs hiệu năng (default 60–300s) |
| 3 | **Báo cáo nào cần PDF (ngoài Excel)?** | Phạm vi FR-RPT-011 (PDF có template) | Default: **chỉ báo cáo tổng hợp dashboard kỳ + báo cáo phục vụ VILAS** cần PDF; còn lại Excel (R4). Báo cáo chưa cấu hình PDF → 422/fallback Excel | Ban lãnh đạo + QA | Khi UAT | **Không** — có default (Excel mặc định, PDF tập con) |
| 4 | **Có cần lưu snapshot KPI lịch sử theo ngày** (xem lại dashboard quá khứ chính xác) hay tính runtime theo bộ lọc là đủ? | Kiến trúc dữ liệu KPI (ASSUMPTION-2) | Default: **tính runtime** theo bộ lọc (không snapshot). Snapshot lịch sử → CR | Ban lãnh đạo | Sau UAT | **Không** — default runtime; snapshot = CR |
| 5 | **Kế toán có được xem thống kê truy cập hệ thống (R15) không?** | RBAC R15 (BR-RPT-010, §2.3) | Default: **CHỈ admin/leader** (R15 nhạy cảm; matrix "Audit log: Kế toán —"). Kế toán/staff → 403 | Ban lãnh đạo | Trước `/contract` | ⚠️ **Nên chốt** — ảnh hưởng RBAC R15 (default chỉ admin/leader) |
| 6 | **"Lượt tải file" (R15) chỉ tính tải tài liệu (M3) hay cả tải attachment khác** (CoA, CoC, file mẫu, ảnh)? | Nguồn đếm lượt tải (BR-RPT-004, ASSUMPTION-5) | Default: **bản đầu chỉ tải tài liệu (`document_access_log`)**; tải attachment khác cần ghi access_stats/audit (mở rộng/CR) | Ban lãnh đạo | Trước `/contract` | ⚠️ **Nên chốt** — ảnh hưởng độ phủ "lượt tải" (default chỉ tài liệu) |
| 7 | **Báo cáo kỳ lớn xuất sync hay async** (sinh file nền + thông báo khi xong)? | Hiệu năng xuất (FR-RPT-010/011, CONSTRAINT-7) | Default: **sync với giới hạn kỳ/kích thước**; kỳ rất lớn → async (background + in-app notify khi xong) — mở rộng | Tech Lead | Khi load test | **Không** — default sync + giới hạn |
| 8 | **M6 đọc bảng module nguồn TRỰC TIẾP hay gọi service/endpoint nội bộ** của từng module? | Kiến trúc tổng hợp (ASSUMPTION-1) | Default: **đọc bảng trực tiếp** cho đếm KPI (hiệu năng 1 query); logic phức (on-time/tiêu hao chi tiết) vẫn ở module gốc. Cần thống nhất với CTO/Tech Lead | CTO / Tech Lead | Trước `/contract` | ⚠️ **Nên chốt** — ảnh hưởng coupling + maintainability (default đọc trực tiếp, có rủi ro coupling) |
| 9 | **Thống kê số mẫu theo thời gian dựa trên `received_at` hay `completed_at`?** (và default kỳ khi bộ lọc rỗng) | Định nghĩa trục thời gian (FR-RPT-003, BR-RPT-009) | Default: cho **chọn cả 2** (param), default `received_at` (mẫu nhận trong kỳ); default kỳ rỗng = tháng hiện tại | Ban lãnh đạo | Trước `/contract` | ⚠️ **Nên chốt** — ảnh hưởng ý nghĩa số liệu (default received_at + tháng hiện tại) |

> **Kết luận:** #3, #4, #7 có default rõ → KHÔNG chặn `/contract`. **#1 (phạm vi ghi access_stats), #2 (cache TTL), #5 (Kế toán R15), #6 (phạm vi lượt tải), #8 (đọc trực tiếp vs service), #9 (trục thời gian mẫu)** NÊN chốt trước `/contract` vì ảnh hưởng **định nghĩa số liệu R15 (#1/#6)**, **hiệu năng/độ tươi (#2)**, **RBAC (#5)**, **kiến trúc coupling (#8)**, **ý nghĩa thống kê (#9)**. Tất cả có **default an toàn**; mọi thay đổi default sau đó phải có văn bản xác nhận KH ("Verbal is Nothing").

---

## 9. Ma trận truy vết (Traceability Matrix) + DANH SÁCH RÕ "M6 tổng hợp gì từ đâu"

### 9.1 FR → Yêu cầu gốc → Submodule → Business Rule → Test Case

| FR ID | Yêu cầu gốc (meeting note) | Submodule (demo-scope) | Điều khoản 17025 | Business Rule | Test Case (QA sẽ tạo) | Trạng thái |
|-------|----------------------------|------------------------|------------------|---------------|------------------------|------------|
| FR-RPT-001 | **R8** (tổng hợp/lọc), **R10** (thống kê số mẫu/hóa chất) | M6.1 | — | BR-001, 002, 003, 004, 005, 006, 007, 008, 011, 013 | TC-RPT-001..010 | Draft |
| FR-RPT-002 | **R10** (thống kê + biểu đồ) | M6.1 | — | BR-001, 002, 009, 014 | TC-RPT-011..016 | Draft |
| FR-RPT-003 | **R8, R10** (số mẫu, lọc thời gian) | M6.2 | — | BR-001, 009, 012 | TC-RPT-017..023 | Draft |
| FR-RPT-004 | **R10** (lượng hóa chất, lọc thời gian) | M6.2 | — | BR-001, 002, 009, 014 | TC-RPT-024..030 | Draft |
| FR-RPT-005 | **R8** (lọc đa tiêu chí) | M6.2 | — | BR-001, 009 | TC-RPT-031..035 | Draft |
| FR-RPT-006 | (KPI nhân sự — R12 lương/HĐ) | M6.1 | — | BR-001, 002, 007 | TC-RPT-036..039 | Draft |
| FR-RPT-007 | **R15** (lượt truy cập/tải/chỉnh sửa) | M6.3 | **§8.4** | BR-004, 009, 010 | TC-RPT-040..048 | Draft |
| FR-RPT-008 | **R15** (theo user) | M6.3 | **§8.4** | BR-004, 009, 010 | TC-RPT-049..052 | Draft |
| FR-RPT-009 | **R15** (hạ tầng ghi lượt truy cập) | M6.3 | — | BR-004, 005, 013 | TC-RPT-053..058 | Draft |
| FR-RPT-010 | **R4** (xuất Excel) | M6.4 | §8.4 | BR-001, 002, 009, 010, 012 | TC-RPT-059..065 | Draft |
| FR-RPT-011 | **R4** (xuất PDF) | M6.4 | **§8.4** | BR-001, 009, 010, 012 | TC-RPT-066..070 | Draft |

### 9.2 DANH SÁCH RÕ — M6 TỔNG HỢP GÌ TỪ MODULE NÀO (để contract/build KHÔNG trùng)

| KPI / Số liệu M6 | Nguồn dữ liệu (bảng) | Module nguồn | Endpoint riêng lẻ ĐÃ CÓ (M6 KHÔNG làm lại) | M6 làm gì |
|------------------|----------------------|--------------|---------------------------------------------|-----------|
| Số mẫu theo trạng thái + overdue; số mẫu theo thời gian | `samples`(status, deadline_at, received_at, completed_at, department_id) | **M1** | `GET /reports/sample-on-time` (on-time rate) | **Chỉ ĐẾM** số lượng theo trạng thái/kỳ/phòng cho dashboard + bộ lọc thống nhất. KHÔNG tính lại on-time rate. |
| Lô hóa chất sắp hết hạn / tới hạn kiểm tra lại; hóa chất tồn thấp; tiêu hao theo tháng | `chemical_lots`(expiry_date, recheck_date), `chemicals`(reorder_threshold), `chemical_transactions`(type=out, qty_base, base_unit, at) | **M2** | `GET /inventory/low-stock`, `GET /reports/consumption`, `GET /exports/transactions.xlsx` | **ĐẾM/TỔNG HỢP** cho dashboard + bộ lọc thống nhất (tách nhóm đo). KHÔNG làm lại low-stock/consumption/export nhật ký của M2. Field tiền theo serializer M2. |
| Số tài liệu/version chờ duyệt; **lượt tải file** (R15) | `document_versions`(status=review), `document_access_log`(action=download) | **M3** | `GET /documents/access-stats` (+ `/:id/access-stats`, `/access-stats/export`) | KPI "chờ duyệt" + đếm `download` cho **lượt tải HỆ THỐNG** (R15). KHÔNG làm lại thống kê view/download **per-tài-liệu** của M3. |
| Số người nâng lương / hết hạn HĐ sắp tới hạn | `hr_profiles`(next_salary_raise_date, contract_end_date) | **M4** | `GET /research-achievements/stats` (thành tích NCKH) | **ĐẾM** KPI tài chính/HR cho dashboard. KHÔNG làm lại thống kê thành tích NCKH của M4. |
| Số thiết bị quá hạn / sắp tới hạn hiệu chuẩn; theo tình trạng | `equipments`(next_due_date, status, department_id) | **M5** | (M5 không có endpoint report riêng — M6 là nơi tổng hợp số liệu thiết bị) | **ĐẾM** KPI thiết bị (đồng bộ định nghĩa badge M5 BR-EQP-009/010). |
| **Lượt truy cập** (login + xem trang); **lượt chỉnh sửa** (CUD); thông báo chưa đọc | `access_stats`(path, at), `audit_logs`(action LOGIN + CUD), `notifications`(read_at) | **M7** | (M7 cung cấp bảng; chưa có endpoint thống kê R15 cấp hệ thống) | **GHI** access_stats (middleware FR-RPT-009) + **ĐẾM** lượt truy cập/chỉnh sửa (R15) — đây là **phần độc quyền của M6.3**, không trùng module nào. |

**Mapping điều khoản ISO/IEC 17025 (demo-scope mục E):**
- **§8.4 Kiểm soát hồ sơ:** `audit_logs` là nguồn đếm "lượt chỉnh sửa" (R15, FR-RPT-007) và truy vết thao tác **xuất báo cáo** (`REPORT_EXPORT`, BR-RPT-012, FR-RPT-010/011) — phục vụ chứng minh kiểm soát hồ sơ khi đánh giá VILAS. M6 KHÔNG sửa/xóa audit_logs (append-only — M7 D8).

**Liên kết liên module (M6 là module CUỐI — chỉ đọc/tổng hợp, không bị tham chiếu):**
- **M7 (nền tảng):** `access_stats` (ghi + đọc R15), `audit_logs` (đếm CUD/LOGIN + ghi REPORT_EXPORT), `notifications` (KPI chưa đọc), `roles_permissions` (`report:business`/`report:finance`/`audit:read` cho R15), `departments`/`users` (scope + lọc).
- **M1/M2/M3/M4/M5:** đọc bảng nguồn để đếm KPI + thống kê (KHÔNG làm lại endpoint riêng — §9.2).
- **Phụ thuộc build:** M6 build sau M1–M5 + M7 (module cuối, roadmap S4 — demo-scope mục G).

---

*Hết SRS M6 (v1.0). 11 FR · 14 BR · 5 UC · 10 NFR · 9 OPEN QUESTIONS. M6 là tầng TỔNG HỢP CHÉO module (READ-ONLY, ngoại lệ duy nhất = middleware ghi access_stats + audit export): dashboard KPI gom M1–M5+M7 với scope theo vai trò (accountant không thấy mẫu/kết quả — B03; KTV không thấy tiền; R15 chỉ admin/leader) + bộ lọc thời gian thống nhất (R8/R10) + thống kê truy cập hệ thống (R15, FR-RPT-007/008/009 — đếm từ access_stats/audit_logs/document_access_log, KHÁC thống kê per-tài-liệu M3) + xuất Excel/PDF có audit (R4). §9.2 liệt kê RÕ M6 tổng hợp gì từ module nào để contract/build KHÔNG trùng các endpoint thống kê riêng lẻ đã có (M1 sample-on-time, M2 consumption/low-stock/export, M3 access-stats, M4 research-stats). 6/9 OPEN QUESTIONS NÊN chốt trước `/contract` (#1 phạm vi ghi access_stats, #2 cache TTL, #5 Kế toán R15, #6 phạm vi lượt tải, #8 đọc trực tiếp vs service, #9 trục thời gian mẫu) — đều có default an toàn. Mọi xác nhận tiếp theo phải bằng văn bản theo rule "Verbal is Nothing".*
