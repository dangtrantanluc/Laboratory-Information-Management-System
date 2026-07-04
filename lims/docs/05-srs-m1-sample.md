# SRS: M1 — Quản lý Mẫu & Yêu cầu thử nghiệm (Sample Lifecycle)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M1 — Quản lý Mẫu & Yêu cầu thử nghiệm
**Version:** 1.1 | **Ngày:** 19/06/2026 | **Author:** BA agent
**Status:** DRAFT — 4 OPEN QUESTIONS lõi (#1, #2, #3, #11) **ĐÃ CHỐT 19/06/2026**; còn #4–#10 treo (không chặn `/contract` — xem §8)
**Nguồn:** `00-meeting-note-analysis.md` (R5, R6, R7, R9; quyết định chốt A01/A02/A04b/AS6/B02/C02/C03; **chốt OQ#1/#2/#3/#11 ngày 19/06/2026**), `01-demo-scope.md` (M1.1–M1.5, RBAC matrix, ERD core, CRON-1/CRON-2, mapping 17025)
**Chuẩn:** IEEE 830 (rút gọn) · ISO/IEC 17025:2017 §7.2, §7.4, §7.5, §7.8, §8.4
**Liên kết module:** samples (bảng do M1 sở hữu) được M2 tham chiếu qua `chemical_transactions.ref_sample_id` (xem SRS M2 §2.1, BR-CHEM-025). **Phụ thuộc M7:** trưởng nhóm cố định theo phòng ban (`departments.lead_user_id` / `is_dept_lead`) cấp quyền `sample:assign` + `sample_result:approve` (OQ#11 đã chốt).

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| 1.0 | 19/06/2026 | Bản DRAFT đầu tiên — 17 FR, 19 BR, 5 UC, 11 OPEN QUESTIONS. |
| 1.1 | 19/06/2026 | **Cập nhật theo 4 OQ lõi KH đã chốt 19/06/2026:** (OQ#1) tách `test_requests` 1-n `samples` — thêm FR-SAMPLE-018, sửa FR-001/002/005/016; (OQ#2) mẫu `done` do **trưởng nhóm chốt thủ công** — thêm FR-SAMPLE-019, sửa state machine FR-017, BR-001, BR-020, UC-03; (OQ#3) kết quả **chỉ công khai sau approved** — sửa FR-008/011, BR-014, thêm BR-021; (OQ#11) **trưởng nhóm cố định theo phòng ban** — sửa §2.3 RBAC, BR-008/011, thêm BR-022. Cập nhật state machine diagram, Data Dictionary, Traceability. |

---

## 1. Giới thiệu

### 1.1 Mục đích

Tài liệu này đặc tả đầy đủ, không mơ hồ, kiểm thử được cho **Module M1 — Quản lý Mẫu & Yêu cầu thử nghiệm** của hệ thống LIMS. Mục tiêu nghiệp vụ: thay thế việc ghi sổ giấy/Excel rời rạc trong quản lý vòng đời mẫu bằng một hệ thống số hóa **toàn bộ hành trình của mẫu** — từ tiếp nhận (intake) → phân công (assignment) → chuyển giao (handover) → thực hiện & nhập kết quả (testing) → phê duyệt (review/approve) → **trưởng nhóm chốt hoàn thành mẫu** → trả kết quả (return) — kèm **chuỗi hành trình mẫu (chain of custody)**, **kiểm soát hồ sơ kết quả bất biến**, và **truy vết deadline/trễ hạn** để đáp ứng yêu cầu của ISO/IEC 17025:2017 (lab đã được công nhận VILAS — A01 đã chốt).

Tài liệu dùng cho 2 đối tượng:
- **Khách hàng / Ban lãnh đạo lab:** xác nhận nghiệp vụ đúng, đặc biệt state machine trạng thái mẫu và quy tắc bất biến kết quả.
- **Đội thiết kế (`schema-designer`, `api-designer`, `ux-designer`) và `feature-builder`:** đủ chi tiết để viết contract và implement mà không phải hỏi lại.

### 1.2 Phạm vi

Module M1 phủ 5 submodule (theo `01-demo-scope.md`):

| Submodule | Nội dung | Trong SRS này |
|-----------|----------|---------------|
| M1.1 Tiếp nhận mẫu (Intake) | Tạo **phiếu yêu cầu thử nghiệm (test_request)** chứa thông tin chung + thêm **1..n mẫu (sample)** vào phiếu; sinh mã mẫu duy nhất (barcode/QR, không lộ ID tuần tự); đính kèm file (ảnh, chứng từ gửi mẫu); ghi tình trạng mẫu khi nhận (đạt/không đạt điều kiện) | ✅ FR-SAMPLE-001..004, 018 |
| M1.2 Phân công & Chuyển giao | Phân công mẫu/phần việc cho KTV; tạo phiếu công việc & chuyển giao cho nhân sự khác (có lịch sử); chuỗi hành trình mẫu (chain of custody — ai giữ, khi nào) | ✅ FR-SAMPLE-005..007 |
| M1.3 Thực hiện & Nhập kết quả | Mỗi KTV nhập kết quả phần được giao; kết quả **công khai nội bộ lab CHỈ SAU KHI approved**; đính kèm file kết quả (raw data, ảnh, Excel); phê duyệt kết quả trước khi chốt (reviewer/approver) | ✅ FR-SAMPLE-008..011 |
| M1.4 Deadline & Trễ hạn | Đặt turnaround time/deadline; cron nhắc mẫu sắp tới hạn (CRON-1); cron đánh dấu trễ hạn (CRON-2); bắt buộc nhập lý do khi trễ hạn; báo cáo on-time rate | ✅ FR-SAMPLE-012..015 |
| M1.5 Trả kết quả | **Trưởng nhóm chốt hoàn thành mẫu (`done`)** rồi xuất phiếu kết quả thử nghiệm (PDF có mã). Portal khách hàng đã CẮT (A02) | ✅ FR-SAMPLE-016, 019 |

**Trong scope `[SCOPE]`:**
- Tạo **phiếu yêu cầu thử nghiệm (`test_requests`)** gắn khách hàng/đối tượng gửi mẫu + người gửi + ngày nhận + người tiếp nhận + phòng ban tiếp nhận, chứa **1..n mẫu (`samples`)** — mỗi mẫu có mã riêng, trạng thái riêng, deadline riêng, phân công riêng (OQ#1 đã chốt).
- Sinh **mã mẫu duy nhất** dạng human-readable (vd `SP-2026-0007`) + barcode/QR; **không lộ ID tuần tự nội bộ** (ID thật là UUID — CONSTRAINT-6).
- Đính kèm file (ảnh mẫu, chứng từ gửi mẫu, raw data, kết quả) qua bảng `attachments` polymorphic chung lên MinIO.
- Ghi tình trạng mẫu khi nhận (`condition_note` + cờ đạt/không đạt điều kiện tiếp nhận).
- Phân công mẫu/phần việc (`sample_assignments`) cho từng KTV trong phạm vi phòng ban.
- **Chuyển giao (handover)** mẫu giữa người giữ, có **lịch sử bất biến** (`sample_handovers`: from_user, to_user, at, lý do).
- **Chuỗi hành trình mẫu (chain of custody)** — truy vết ai giữ mẫu vào thời điểm nào (17025 §7.4).
- Mỗi KTV nhập kết quả **phần được giao** (immutable sau khi approved); đính kèm raw data.
- **Phê duyệt kết quả** (reviewer/approver §7.8) trước khi chốt mẫu; kết quả approved bất biến (sửa = tạo phiên bản mới + audit — §8.4).
- Hiển thị kết quả **công khai nội bộ lab CHỈ SAU KHI approved** (mọi vai trò có quyền xem M1, trừ Kế toán); trước approved chỉ người nhập + người duyệt (trưởng nhóm) + Admin/Ban lãnh đạo xem (OQ#3 đã chốt).
- State machine trạng thái mẫu: `received → assigned → testing → done → returned`; nhánh `overdue`. **Chuyển `testing → done` do trưởng nhóm chốt thủ công** (không auto — OQ#2 đã chốt).
- Đặt `deadline_at` (turnaround time); CRON-1 nhắc sắp tới hạn; CRON-2 đánh dấu `overdue`; bắt buộc nhập lý do trễ (`overdue_reasons`).
- Báo cáo **on-time rate** (tỷ lệ đúng hạn).
- Xuất **phiếu kết quả thử nghiệm PDF** có mã mẫu + barcode/QR.
- Audit log mọi thao tác CRUD phiếu/mẫu/phân công/handover/kết quả/duyệt/chốt mẫu (17025 §8.4).

**Ngoài scope `[OUT-OF-SCOPE → cần CR]`:**
- **Portal khách hàng** (khách tự đăng nhập xem/tải kết quả): CẮT — A02 đã chốt "công khai = nội bộ lab".
- Thông báo qua email / Zalo: chỉ in-app (C02). Email/Zalo → CR.
- Tính phí dịch vụ thử nghiệm / hóa đơn cho khách gửi mẫu (Kế toán không thấy mẫu — B03): không thuộc M1.
- Lấy mẫu hiện trường / sampling plan (thu mẫu tại hiện trường): chưa trong demo-scope.
- Tính bất định đo (measurement uncertainty), kiểm soát chất lượng nội bộ (QC charts), so sánh liên phòng: ngoài scope bản đầu → CR.
- Quản lý phương pháp thử nghiệm như một thực thể riêng (method library): trong M1 phương pháp tham chiếu tài liệu/SOP của M3, không tự CRUD method.
- Lưu mẫu vật lý theo vị trí tủ/kệ/nhiệt độ (sample storage location mapping): ngoài scope.
- Chữ ký số (digital signature có CA) trên phiếu kết quả PDF: phiếu chỉ ghi tên/chức danh người duyệt; chữ ký số → CR.

### 1.3 Định nghĩa, từ viết tắt và thuật ngữ

| Thuật ngữ | Định nghĩa |
|-----------|------------|
| **Phiếu yêu cầu thử nghiệm (Test Request)** | Bản ghi tiếp nhận chứa **thông tin chung của một lần gửi mẫu**: khách hàng/đối tượng gửi, người gửi, ngày nhận, người tiếp nhận, phòng ban tiếp nhận. **Một phiếu chứa 1..n mẫu** (`test_requests` 1-n `samples` — OQ#1 đã chốt 19/06/2026). Định danh bởi `request_code`. |
| **Mẫu (Sample)** | Đối tượng thử nghiệm cụ thể thuộc một phiếu, định danh bởi `sample_code` duy nhất. Mỗi mẫu có **vòng đời (state machine), trạng thái, deadline, phân công và chuỗi hành trình RIÊNG** — độc lập với các mẫu khác cùng phiếu. |
| **Mã phiếu (`request_code`)** | Mã hiển thị duy nhất của phiếu yêu cầu (vd `RQ-2026-0042`), không lộ ID tuần tự nội bộ. |
| **Mã mẫu (`sample_code`)** | Mã hiển thị duy nhất, human-readable, không đoán được tuần tự (vd `SP-2026-0007`). Gắn barcode/QR. KHÁC với `id` (UUID nội bộ) — không lộ ID tuần tự (CONSTRAINT-6). |
| **Phân công (Assignment)** | Giao một **phần việc/chỉ tiêu** của mẫu cho một KTV (`sample_assignments`): assigned_to, assigned_by, part_name (chỉ tiêu/hạng mục), status. Một mẫu có thể có nhiều assignment cho nhiều KTV (R6). |
| **Phần việc (Part / chỉ tiêu)** | Một hạng mục thử nghiệm cụ thể của mẫu (vd "độ ẩm", "pH", "hàm lượng kim loại nặng"). Mỗi part được giao cho 1 KTV và có 1 kết quả riêng. |
| **Chuyển giao (Handover)** | Hành động chuyển **quyền giữ mẫu vật lý** (current custodian) từ người này sang người khác (`sample_handovers`: from_user, to_user, at, lý do). Khác với phân công (assignment giao việc; handover giao mẫu vật lý). |
| **Người giữ hiện tại (Current custodian)** | Người đang giữ mẫu vật lý tại thời điểm hiện tại — suy ra từ handover gần nhất; ban đầu là người nhận mẫu (`received_by` của phiếu). |
| **Chuỗi hành trình mẫu (Chain of custody)** | Lịch sử **bất biến** mọi lần đổi người giữ mẫu (17025 §7.4) — ai giữ, từ khi nào đến khi nào, vì sao chuyển. Dựng từ `sample_handovers` + bản ghi tiếp nhận ban đầu. |
| **Kết quả (Result)** | Dữ liệu kết quả của một phần việc (`sample_results`): result_data (JSONB), người nhập, thời điểm, người duyệt, file đính kèm. |
| **Phê duyệt kết quả (Review/Approve)** | Bước reviewer/approver (trưởng nhóm) xác nhận **kết quả của một phần việc** trước khi chốt (17025 §7.8). Sau khi `approved` → kết quả **bất biến** và mới **công khai nội bộ** (OQ#3). |
| **Chốt hoàn thành mẫu (Finalize / Mark done)** | Hành động **thủ công của trưởng nhóm** xác nhận cả mẫu đã xong và chuyển trạng thái mẫu `testing → done`. Chỉ thực hiện được khi **mọi phần việc đã approved** nhưng **KHÔNG tự động** — phải có hành động chốt của trưởng nhóm (OQ#2 đã chốt 19/06/2026). |
| **Trưởng nhóm (Department lead)** | **Người cố định theo từng phòng ban** (gắn ở M7: `departments.lead_user_id` hoặc cờ `is_dept_lead` trên hồ sơ nhân sự). Mặc định có quyền `sample:assign` (phân công) + `sample_result:approve` (duyệt kết quả) + chốt hoàn thành mẫu **trong phòng ban mình** (OQ#11 đã chốt 19/06/2026). |
| **Bất biến (Immutable)** | Kết quả đã `approved` không được sửa trực tiếp; sửa = tạo **phiên bản mới** (`version` tăng) + giữ bản cũ + ghi audit (17025 §8.4). |
| **Deadline / Turnaround time (TAT)** | `deadline_at` = thời điểm phải hoàn thành mẫu (done). TAT = khoảng từ `received_at` đến `deadline_at`. Deadline riêng cho từng mẫu. |
| **Trễ hạn (Overdue)** | Mẫu quá `deadline_at` mà chưa `done` → CRON-2 chuyển sang nhánh trạng thái `overdue`; bắt buộc nhập lý do trễ (`overdue_reasons`). |
| **On-time rate** | Tỷ lệ % mẫu hoàn thành đúng hạn = (số mẫu done với `completed_at ≤ deadline_at`) / (tổng mẫu done trong kỳ). |
| **State machine** | Tập trạng thái mẫu hợp lệ + các phép chuyển hợp lệ (xem §3 FR-SAMPLE-017 và §4 BR-SAMPLE-001). |
| **VILAS** | Hệ thống công nhận phòng thí nghiệm Việt Nam (theo ISO/IEC 17025). |
| **Audit log** | Bản ghi bất biến: ai, khi nào, làm gì, trên tài nguyên nào, với `correlationId` (17025 §8.4). |
| **RBAC** | Role-Based Access Control + phạm vi theo phòng ban. |
| **JSONB** | Kiểu dữ liệu PostgreSQL lưu cấu trúc kết quả linh hoạt (`result_data`) — vì mỗi chỉ tiêu có cấu trúc khác nhau. |

### 1.4 Tài liệu tham chiếu

| Tài liệu | Vai trò |
|----------|---------|
| `lims/docs/00-meeting-note-analysis.md` | Yêu cầu gốc R1–R20 + quyết định đã chốt với KH 19/06/2026 (gồm OQ#1/#2/#3/#11) |
| `lims/docs/01-demo-scope.md` | Cây module, RBAC matrix, ERD core, cron job (CRON-1/CRON-2), mapping 17025 |
| `lims/docs/02-srs-m2-chemical.md` | SRS M2 — quan hệ liên kết `ref_sample_id`; chuẩn phong cách FR/BR/AC |
| `~/.claude/rules/nfr.md` | Template NFR chuẩn IEEE 830 |
| `~/.claude/rules/api.md` | Quy ước REST, response format, status code, không lộ ID tuần tự |
| `~/.claude/rules/logging.md` | Structured logging, correlationId, error handling |
| **ISO/IEC 17025:2017** §7.2 | Lựa chọn, kiểm tra xác nhận & xác nhận giá trị sử dụng của phương pháp (mẫu tham chiếu SOP/phương pháp ở M3) |
| **ISO/IEC 17025:2017** §7.4 | Xử lý đối tượng thử nghiệm: tiếp nhận, bảo quản, **chuỗi hành trình (chain of custody)**, tình trạng mẫu khi nhận |
| **ISO/IEC 17025:2017** §7.5 | Hồ sơ kỹ thuật — bản ghi kết quả gốc (raw data đính kèm) |
| **ISO/IEC 17025:2017** §7.8 | Báo cáo kết quả — phiếu kết quả, phê duyệt trước khi ban hành |
| **ISO/IEC 17025:2017** §8.4 | Kiểm soát hồ sơ — lưu trữ, truy xuất, bất biến, audit, versioning |

---

## 2. Mô tả tổng quan

### 2.1 Bối cảnh sản phẩm

M1 là một trong 7 module của LIMS monolith (FastAPI + Next.js + PostgreSQL + Redis + MinIO + APScheduler, Docker Compose). M1 là **module trung tâm nghiệp vụ lab** và **sở hữu bảng `test_requests` + `samples`** mà các module khác tham chiếu. M1 **phụ thuộc** vào:

- **M7 (Auth + RBAC + phòng ban + audit log):** mọi API M1 yêu cầu xác thực JWT và kiểm tra quyền theo vai trò + phạm vi phòng ban. **M7 cung cấp `trưởng nhóm cố định theo phòng ban`** (`departments.lead_user_id` / `is_dept_lead`) — nguồn cấp quyền `sample:assign` + `sample_result:approve` + chốt mẫu (OQ#11). Audit ghi vào bảng dùng chung `audit_logs`.
- **M7.5 (Notifications):** CRON-1 (nhắc sắp tới hạn) và CRON-2 (đánh dấu trễ hạn) tạo bản ghi `notifications` in-app.
- **Bảng `attachments` polymorphic dùng chung:** lưu file ảnh mẫu, chứng từ gửi mẫu, raw data, file kết quả.
- **MinIO:** lưu file; M1 lưu `file_key` không lưu binary trong DB.

M1 **được tham chiếu bởi**:
- **M2 (Hóa chất):** `chemical_transactions.ref_sample_id` (NOT NULL khi xuất) tham chiếu `samples.id`. M2 đọc mẫu để hiển thị mã mẫu và lọc báo cáo tiêu hao theo mẫu/đề tài (xem SRS M2 BR-CHEM-025). **Hệ quả:** không được hard-delete mẫu đang được giao dịch hóa chất tham chiếu (BR-SAMPLE-016).
- **M6 (Báo cáo):** đếm số mẫu, on-time rate, lọc đa tiêu chí (R8, R10).

### 2.2 Chức năng chính

1. Tiếp nhận mẫu: tạo **phiếu yêu cầu thử nghiệm (thông tin chung)** rồi thêm **1..n mẫu** vào phiếu, sinh mã mẫu duy nhất + barcode/QR cho từng mẫu, đính kèm file, ghi tình trạng mẫu khi nhận.
2. Phân công phần việc cho KTV; chuyển giao mẫu vật lý giữa người giữ với lịch sử bất biến (chain of custody).
3. Nhập kết quả từng phần (mỗi KTV phần được giao), đính kèm raw data.
4. Phê duyệt kết quả (reviewer/approver = trưởng nhóm) trước khi chốt; kết quả approved bất biến + mới công khai nội bộ; sửa = tạo phiên bản mới.
5. **Trưởng nhóm chốt hoàn thành mẫu (`done`) thủ công** sau khi mọi phần việc approved.
6. Quản lý deadline/TAT; cron nhắc sắp tới hạn (CRON-1) và đánh dấu trễ hạn (CRON-2); bắt buộc nhập lý do trễ.
7. Báo cáo on-time rate.
8. Xuất phiếu kết quả thử nghiệm PDF có mã mẫu.
9. Ghi audit toàn bộ thao tác phục vụ duy trì công nhận VILAS (§8.4).

### 2.3 Đối tượng người dùng & quyền (RBAC + phạm vi phòng ban)

Trích từ RBAC matrix `01-demo-scope.md` (4 vai trò). Phạm vi dữ liệu: theo phòng ban, trừ Admin & Ban lãnh đạo (toàn hệ thống). **Kế toán KHÔNG truy cập mẫu/kết quả** (B03 — cách ly nghiệp vụ lab khỏi tài chính).

**Khái niệm "trưởng nhóm" (OQ#11 đã chốt 19/06/2026):** "Trưởng nhóm" **KHÔNG phải vai trò RBAC thứ 5** mà là **thuộc tính cố định gắn cho đúng 1 user mỗi phòng ban** trong M7 (`departments.lead_user_id` hoặc cờ `is_dept_lead`). Người này vẫn thuộc vai trò "Nhân sự/KTV" nhưng được cấp thêm các quyền điều phối **giới hạn trong phòng ban mình**: `sample:assign`, `sample_result:approve`, chốt hoàn thành mẫu (`sample:finalize`). KTV thường KHÔNG có các quyền này.

| Actor | Mô tả | Quyền trong M1 |
|-------|-------|----------------|
| **Admin** | Quản trị hệ thống | Toàn quyền mọi thao tác mẫu (mọi phòng ban): tạo phiếu/mẫu, phân công, chuyển giao, nhập/duyệt kết quả, **chốt hoàn thành mẫu**, xử lý trễ hạn, xuất phiếu. |
| **Ban lãnh đạo** | Lãnh đạo lab | Xem toàn hệ thống (👁) + **phân công/chuyển giao** (✅) + **duyệt kết quả** (✅) + **chốt hoàn thành mẫu** (✅). Không trực tiếp nhập kết quả phần việc (👁 trên nhập kết quả). Xuất phiếu kết quả. |
| **Kế toán** | Tài chính | **KHÔNG truy cập** mẫu/kết quả (—). Mọi API M1 trả 403 cho Kế toán. |
| **Nhân sự/KTV** | Kỹ thuật viên (gồm quyền "nhận mẫu" — B02) | **Tạo phiếu/mẫu** (✅ phòng); **xem công khai nội bộ kết quả ĐÃ approved** (✅, mọi phòng ở mức đọc); **nhập kết quả phần được giao cho mình** (✅ được giao). **Nếu là trưởng nhóm phòng mình (OQ#11):** thêm **phân công/chuyển giao** (✅ phòng), **duyệt kết quả** (✅ `sample_result:approve`), **chốt hoàn thành mẫu** (✅ `sample:finalize`). KTV thường: KHÔNG phân công/duyệt/chốt. |

Quy ước: ✅ = toàn quyền trong phạm vi · 👁 = chỉ xem · — = không truy cập · (phòng) = giới hạn phòng ban của user · (được giao) = chỉ phần việc được phân cho mình.

> **"Nhận mẫu" là QUYỀN của KTV (B02), không phải vai trò riêng.** KTV có quyền `sample:create` (tạo phiếu/mẫu nhận) trong phạm vi phòng mình.
> **"Trưởng nhóm" là THUỘC TÍNH cố định theo phòng ban (OQ#11), không phải vai trò riêng.** Quyền `sample:assign` / `sample_result:approve` / `sample:finalize` chỉ cấp cho trưởng nhóm phòng đó / Admin / Ban lãnh đạo — xem BR-SAMPLE-022.
> **Cách ly tài chính (B03):** Kế toán bị chặn mọi endpoint M1 ở **tầng API** (không chỉ ẩn FE) — xem BR-SAMPLE-014, NFR-SEC-SAMPLE-001.
> **Duyệt kết quả (§7.8):** Người **nhập** kết quả KHÔNG được **tự duyệt** kết quả của chính mình (tách biệt nhập–duyệt, BR-SAMPLE-011).
> **Chốt hoàn thành mẫu (OQ#2):** mẫu chỉ `done` khi **trưởng nhóm thực hiện hành động chốt** — không tự động dù mọi phần việc đã approved (BR-SAMPLE-020).

### 2.4 Ràng buộc (Constraints)

- **CONSTRAINT-1 (State machine):** trạng thái mẫu chỉ chuyển theo các phép hợp lệ định nghĩa ở §3 FR-SAMPLE-017 / §4 BR-SAMPLE-001. Mọi chuyển trạng thái không hợp lệ bị chặn (422 `INVALID_STATE_TRANSITION`).
- **CONSTRAINT-2 (Chain of custody — 17025 §7.4):** mọi lần đổi người giữ mẫu phải ghi `sample_handovers` (from_user, to_user, at, lý do); bản ghi **bất biến**. Người giữ hiện tại luôn truy vết được tại mọi thời điểm.
- **CONSTRAINT-3 (Kết quả bất biến — VILAS §8.4):** kết quả đã `approved` không được sửa/xóa trực tiếp; sửa = tạo **phiên bản mới** (`version` tăng), giữ bản cũ, ghi audit. Không có endpoint hard-delete kết quả.
- **CONSTRAINT-4 (Audit VILAS §8.4):** mọi thao tác CRUD phiếu/mẫu/phân công/handover/kết quả/duyệt/chốt mẫu/trễ hạn ghi `audit_logs` (user, action, resource, resource_id, correlation_id, ip, timestamp, detail).
- **CONSTRAINT-5 (Mã không lộ tuần tự — CONSTRAINT-6 demo-scope):** `id` nội bộ là UUID; `request_code`/`sample_code` hiển thị duy nhất, không đoán được tuần tự ra ngoài (rule api.md).
- **CONSTRAINT-6 (Thông báo):** chỉ in-app (bảng `notifications`); không email/Zalo (C02).
- **CONSTRAINT-7 (Stack & quy mô):** FastAPI, PostgreSQL, Redis (cron lock), MinIO (file), APScheduler (cron). Quy mô ~40 user (C03) — monolith, không scale ngang.
- **CONSTRAINT-8 (Liên kết M2):** không hard-delete mẫu đang được `chemical_transactions.ref_sample_id` tham chiếu (toàn vẹn tham chiếu — BR-SAMPLE-016).
- **CONSTRAINT-9 (Phụ thuộc M7 — trưởng nhóm):** RBAC duyệt/phân công/chốt mẫu phụ thuộc M7 cung cấp trưởng nhóm cố định theo phòng ban (`departments.lead_user_id` / `is_dept_lead`). M1 đọc thuộc tính này để enforce BR-SAMPLE-022. **M7 phải sẵn sàng trước khi `/contract` M1 implement RBAC duyệt/phân công.**

### 2.5 Giả định (Assumptions) — xem chi tiết §7

- ASSUMPTION-1 (**OQ#1 — ĐÃ CHỐT 19/06/2026**): 1 phiếu yêu cầu thử nghiệm (`test_requests`) chứa **1..n mẫu** (`samples`) — quan hệ 1-n. Mỗi mẫu có mã/trạng thái/deadline/phân công riêng.
- ASSUMPTION-2 (**OQ#2 — ĐÃ CHỐT 19/06/2026**): mẫu chuyển `done` do **trưởng nhóm chốt thủ công** (không auto), điều kiện tiên quyết là mọi phần việc đã `approved`.
- ASSUMPTION-3 (**OQ#3 — ĐÃ CHỐT 19/06/2026**): kết quả **chỉ công khai nội bộ toàn lab SAU KHI approved**. Trước approved: chỉ người nhập + người duyệt (trưởng nhóm) + Admin/Ban lãnh đạo xem.
- ASSUMPTION-4: Người giữ mẫu ban đầu = `received_by` của phiếu (người tiếp nhận). Chain of custody bắt đầu từ bản ghi tiếp nhận.
- ASSUMPTION-5 → **OPEN QUESTION #4 (còn treo):** mốc nhắc CRON-1 trước hạn (mặc định còn ≤ 3 ngày và ≤ 1 ngày) — cấu hình được; chốt khi UAT, không chặn contract.
- ASSUMPTION-6 (**OQ#11 — ĐÃ CHỐT 19/06/2026**): "trưởng nhóm" là thuộc tính cố định theo phòng ban ở M7 (`departments.lead_user_id` / `is_dept_lead`); cấp quyền `sample:assign` + `sample_result:approve` + `sample:finalize` trong phòng ban mình.

---

## 3. Yêu cầu chức năng chi tiết

Mỗi FR có ID dạng `FR-SAMPLE-NNN`. Business rule dạng `BR-SAMPLE-NNN` ở §4. Acceptance Criteria dạng Given–When–Then (cover happy path + edge + RBAC + lỗi input).

---

### FR-SAMPLE-018: Tạo phiếu yêu cầu thử nghiệm (thông tin chung của lô) — OQ#1

- **Mô tả:** Tạo một **phiếu yêu cầu thử nghiệm (`test_requests`)** chứa thông tin chung của một lần gửi mẫu: khách hàng/đối tượng gửi, người gửi, ngày nhận (`received_at`), người tiếp nhận (`received_by`), phòng ban tiếp nhận. Phiếu là vùng chứa của **1..n mẫu** (FR-SAMPLE-001). Khi lưu, sinh `request_code` duy nhất. Một phiếu phải có **ít nhất 1 mẫu** trước khi coi là hoàn tất tiếp nhận.
- **Độ ưu tiên:** P0
- **Actor:** KTV (quyền "nhận mẫu" — phòng mình), Admin (mọi phòng). Ban lãnh đạo xem. Kế toán không truy cập.
- **Tiền điều kiện:** user đã đăng nhập, có quyền `sample:create` trong phạm vi phòng ban.
- **Luồng chính:**
  1. User mở "Tiếp nhận mẫu" → "Tạo phiếu yêu cầu".
  2. Nhập thông tin chung: khách hàng/đối tượng gửi (chọn từ `customers` hoặc tạo nhanh), người gửi (tên người mang mẫu tới), phòng ban tiếp nhận (mặc định = phòng của user), người tiếp nhận (mặc định = user hiện tại → `received_by`), `received_at` (mặc định now).
  3. Hệ thống validate → sinh `request_code` (không lộ tuần tự) → lưu `test_requests` → ghi `audit_logs` action=`REQUEST_CREATE`.
  4. User thêm **1..n mẫu** vào phiếu (FR-SAMPLE-001), mỗi mẫu có deadline riêng.
- **Luồng phụ / ngoại lệ:**
  - A1: phòng ban tiếp nhận ≠ phòng của user (và user không phải Admin) → 403 `FORBIDDEN`.
  - A2: lưu phiếu nhưng chưa thêm mẫu nào → phiếu ở trạng thái "nháp"; cảnh báo phải thêm ≥ 1 mẫu để hoàn tất (BR-SAMPLE-023).
- **Hậu điều kiện:** phiếu tồn tại với `request_code` duy nhất; sẵn sàng thêm mẫu; audit ghi nhận.
- **Business Rules:** BR-SAMPLE-013, BR-SAMPLE-014, BR-SAMPLE-015, BR-SAMPLE-023.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN KTV phòng "Hóa lý" đã đăng nhập WHEN tạo phiếu cho khách "Cty ABC", người gửi "Nguyễn Văn A", phòng = Hóa lý THEN trả 201, phiếu có `request_code` duy nhất, `department_id`=Hóa lý, `received_by`=KTV, audit `REQUEST_CREATE`.
  - AC2 (1-n): GIVEN phiếu vừa tạo WHEN thêm 3 mẫu (FR-SAMPLE-001) THEN cả 3 mẫu có `request_id` trỏ về phiếu, mỗi mẫu có `sample_code` riêng và deadline riêng.
  - AC3 (RBAC scope): GIVEN KTV phòng "Hóa lý" WHEN tạo phiếu cho phòng "Vi sinh" THEN trả 403 `FORBIDDEN`.
  - AC4 (RBAC — Kế toán chặn): GIVEN Kế toán WHEN gọi API tạo phiếu THEN trả 403 `FORBIDDEN` (B03).
  - AC5 (phiếu rỗng): GIVEN phiếu chưa có mẫu nào WHEN hoàn tất tiếp nhận THEN cảnh báo/từ chối hoàn tất (cần ≥ 1 mẫu — BR-SAMPLE-023).
- **Data cần thiết (mức logic):** TestRequest { id(UUID), request_code(UNIQUE), customer_id(FK), sender_name, department_id(FK NOT NULL), received_by(FK→users), received_at, note, created_at }.
- **API cần (ý định):** "tạo phiếu yêu cầu thử nghiệm", "thêm mẫu vào phiếu", "liệt kê mẫu của phiếu", "tìm/tạo nhanh khách hàng gửi mẫu".

---

### FR-SAMPLE-001: Thêm mẫu vào phiếu (tiếp nhận từng mẫu) — sửa theo OQ#1

- **Mô tả:** Thêm một mẫu vào **phiếu yêu cầu thử nghiệm** (FR-SAMPLE-018): mô tả mẫu, deadline (TAT) **riêng cho mẫu này**, danh sách phần việc/chỉ tiêu cần thử. Khi lưu, hệ thống sinh mã mẫu duy nhất (FR-SAMPLE-002), khởi tạo trạng thái `received`, thừa kế khách hàng/phòng ban/người tiếp nhận từ phiếu. Một phiếu có thể chứa nhiều mẫu (1-n).
- **Độ ưu tiên:** P0
- **Actor:** KTV (phòng mình), Admin (mọi phòng). Ban lãnh đạo xem. Kế toán không truy cập.
- **Tiền điều kiện:** phiếu (`test_requests`) tồn tại; user có quyền `sample:create` trong phạm vi phòng ban của phiếu.
- **Luồng chính:**
  1. Trong phiếu vừa tạo (FR-SAMPLE-018), user chọn "Thêm mẫu".
  2. Nhập: mô tả mẫu, `deadline_at` (bắt buộc — BR-SAMPLE-002), danh sách phần việc (part_name) cần thử (tùy chọn, có thể phân công sau), tình trạng mẫu khi nhận (FR-SAMPLE-004).
  3. Hệ thống validate (BR-SAMPLE-002, BR-SAMPLE-003) → sinh `sample_code` (FR-SAMPLE-002) → lưu `samples` với `request_id`=phiếu, `department_id`=phòng của phiếu, `status='received'`, người giữ ban đầu = `received_by` của phiếu → ghi `audit_logs` action=`SAMPLE_CREATE`.
  4. Trả về mẫu vừa tạo kèm `sample_code` + dữ liệu barcode/QR. Lặp lại để thêm mẫu khác trong cùng phiếu.
- **Luồng phụ / ngoại lệ:**
  - A1: thiếu `deadline_at` → 400 code `DEADLINE_REQUIRED` (BR-SAMPLE-002).
  - A2: `deadline_at` ≤ `received_at` (của phiếu) → 422 code `INVALID_DEADLINE` (BR-SAMPLE-002).
  - A3: thêm mẫu vào phiếu của phòng khác (user không Admin) → 403 `FORBIDDEN`.
- **Hậu điều kiện:** mẫu tồn tại với `status='received'`, `request_id` trỏ phiếu, `sample_code` duy nhất, chain of custody khởi tạo (người giữ = `received_by`); audit ghi nhận.
- **Business Rules:** BR-SAMPLE-002, BR-SAMPLE-003, BR-SAMPLE-013, BR-SAMPLE-015, BR-SAMPLE-023.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN phiếu `RQ-2026-0042` (phòng Hóa lý) WHEN thêm mẫu deadline 25/06/2026 THEN trả 201, mẫu có `status='received'`, `request_id`=phiếu, `department_id`=Hóa lý, `received_by`=KTV của phiếu, `sample_code` duy nhất, audit `SAMPLE_CREATE` với `correlation_id`.
  - AC2 (nhiều mẫu/phiếu): GIVEN phiếu có sẵn 2 mẫu WHEN thêm mẫu thứ 3 THEN 3 mẫu cùng `request_id`, 3 `sample_code` khác nhau, 3 deadline độc lập, 3 trạng thái độc lập.
  - AC3 (edge — deadline trước ngày nhận): GIVEN phiếu `received_at`=19/06/2026 WHEN thêm mẫu `deadline_at`=18/06/2026 THEN trả 422 code `INVALID_DEADLINE`, không tạo mẫu.
  - AC4 (RBAC scope): GIVEN KTV phòng "Hóa lý" WHEN thêm mẫu vào phiếu phòng "Vi sinh" THEN trả 403 code `FORBIDDEN`, không tạo mẫu.
  - AC5 (RBAC — Kế toán chặn): GIVEN Kế toán WHEN gọi API thêm mẫu THEN trả 403 `FORBIDDEN` (B03).
  - AC6 (lỗi input — thiếu deadline): GIVEN form thêm mẫu WHEN không nhập `deadline_at` THEN trả 400 code `DEADLINE_REQUIRED`, không tạo mẫu.
- **Data cần thiết (mức logic):** Sample { id(UUID), sample_code(UNIQUE), request_id(FK→test_requests), department_id(FK), received_by(FK→users), received_at, deadline_at, status(received), condition_note, created_at }. (customer/sender suy từ phiếu qua `request_id`.)
- **API cần (ý định):** "thêm mẫu vào phiếu", "sửa thông tin mẫu (trước khi phân công)".

---

### FR-SAMPLE-002: Sinh mã mẫu duy nhất + barcode/QR

- **Mô tả:** Khi thêm mẫu vào phiếu, hệ thống sinh `sample_code` duy nhất, human-readable, không lộ ID tuần tự nội bộ (vd `SP-<năm>-<sequence-per-year>` hoặc mã ngẫu nhiên có kiểm tra trùng). Sinh dữ liệu barcode/QR encode `sample_code` để dán/quét. (Phiếu cũng có `request_code` sinh tương tự ở FR-SAMPLE-018.)
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (trong giao dịch thêm mẫu FR-SAMPLE-001).
- **Tiền điều kiện:** đang thêm mẫu vào phiếu.
- **Luồng chính:**
  1. Hệ thống sinh `sample_code` theo định dạng cấu hình (OPEN QUESTION #5 — định dạng cụ thể), đảm bảo duy nhất (unique constraint + retry nếu trùng).
  2. Sinh payload barcode/QR encode `sample_code` (không encode UUID nội bộ).
  3. Lưu `sample_code` cùng mẫu.
- **Luồng phụ / ngoại lệ:**
  - A1: trùng `sample_code` (race condition) → retry sinh mã khác trong cùng transaction; nếu vẫn fail sau N lần → 500 + log ERROR.
- **Hậu điều kiện:** mẫu có `sample_code` duy nhất + barcode/QR truy xuất được.
- **Business Rules:** BR-SAMPLE-015 (mã duy nhất, không lộ tuần tự).
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN thêm mẫu mới WHEN lưu THEN mẫu có `sample_code` khớp định dạng đã cấu hình và duy nhất trong toàn hệ thống; API trả `sample_code` nhưng KHÔNG trả `id` UUID tuần tự dạng số liên tiếp.
  - AC2 (duy nhất): GIVEN 2 mẫu thêm gần đồng thời (kể cả cùng phiếu) WHEN cả hai sinh mã THEN 2 mã khác nhau (unique constraint đảm bảo), không có 2 mẫu trùng `sample_code`.
  - AC3 (quét QR): GIVEN mẫu có `sample_code`=`SP-2026-0007` WHEN quét QR của mẫu THEN payload decode ra đúng `SP-2026-0007` (không lộ UUID/ID tuần tự).
  - AC4 (không lộ tuần tự): GIVEN 2 mẫu tạo liên tiếp WHEN so sánh URL/định danh dùng ngoài THEN không suy ra được số thứ tự nội bộ liên tiếp từ định danh dùng ngoài (dùng UUID/`sample_code`, không expose serial id) (CONSTRAINT-5).
- **Data cần thiết:** Sample.sample_code (UNIQUE); TestRequest.request_code (UNIQUE); cấu hình định dạng mã (OPEN QUESTION #5).
- **API cần:** nội bộ (trong tạo phiếu/thêm mẫu); "lấy barcode/QR của mẫu (ảnh/payload)".

---

### FR-SAMPLE-003: Đính kèm file mẫu (ảnh, chứng từ gửi mẫu)

- **Mô tả:** Đính kèm file vào mẫu: ảnh mẫu, chứng từ/biên bản giao nhận mẫu của khách. Lưu MinIO qua bảng `attachments` polymorphic (owner_type=`sample`). (Chứng từ chung của cả lô có thể đính kèm ở mức phiếu — owner_type=`test_request`.)
- **Độ ưu tiên:** P0
- **Actor:** KTV (phòng mình), Admin. Ban lãnh đạo/KTV có quyền xem M1 được xem/tải. Kế toán không truy cập.
- **Tiền điều kiện:** mẫu tồn tại; user có quyền trong phạm vi.
- **Luồng chính:**
  1. User mở chi tiết mẫu → "Đính kèm file" → upload PDF/ảnh.
  2. Hệ thống validate loại + dung lượng (BR-SAMPLE-012) → lưu MinIO → ghi `attachments` (owner_type=`sample`, owner_id=sample.id).
  3. Ghi `audit_logs` action=`SAMPLE_ATTACH_UPLOAD`.
- **Luồng phụ / ngoại lệ:**
  - A1: file không thuộc loại cho phép → 422 code `INVALID_FILE_TYPE`.
  - A2: file > giới hạn (OPEN QUESTION #6) → 422 code `FILE_TOO_LARGE`.
  - A3: MinIO down → 422; mẫu vẫn tồn tại, file đính kèm sau (không chặn nghiệp vụ).
- **Hậu điều kiện:** file truy xuất được; lượt tải sau này được audit (R15).
- **Business Rules:** BR-SAMPLE-012.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN mẫu `SP-2026-0007` WHEN upload "bien-ban-giao-mau.pdf" (2 MB) THEN trả 201, file lấy lại được qua link tải, audit ghi `SAMPLE_ATTACH_UPLOAD`.
  - AC2 (edge — sai loại): GIVEN file "mau.exe" WHEN upload THEN trả 422 code `INVALID_FILE_TYPE`, không lưu.
  - AC3 (RBAC scope): GIVEN KTV phòng "Vi sinh" WHEN upload file cho mẫu thuộc phòng "Hóa lý" THEN trả 403, không lưu.
  - AC4 (lỗi input — quá lớn): GIVEN file > giới hạn cấu hình WHEN upload THEN trả 422 code `FILE_TOO_LARGE`.
- **Data cần thiết:** Attachment { owner_type ∈ {`sample`,`test_request`}, owner_id, file_key, file_name, mime, size, uploaded_by, uploaded_at }.
- **API cần:** "upload file đính kèm mẫu", "liệt kê file đính kèm của mẫu", "tải file đính kèm".

---

### FR-SAMPLE-004: Ghi tình trạng mẫu khi nhận (đạt/không đạt điều kiện tiếp nhận)

- **Mô tả:** Ghi nhận tình trạng mẫu tại thời điểm tiếp nhận: đạt hay không đạt điều kiện tiếp nhận (vd bao bì rách, nhiệt độ không phù hợp, thiếu nhãn) + ghi chú. Mẫu không đạt điều kiện được đánh dấu để truy vết và quyết định (tiếp nhận có lưu ý / từ chối).
- **Độ ưu tiên:** P1
- **Actor:** KTV (phòng mình), Admin.
- **Tiền điều kiện:** mẫu tồn tại (đang `received`).
- **Luồng chính:**
  1. Khi thêm mẫu hoặc ngay sau, user chọn tình trạng tiếp nhận: `acceptable` / `not_acceptable` + `condition_note`.
  2. Hệ thống lưu `condition_note` + cờ; nếu `not_acceptable` → đánh dấu nổi bật + ghi audit `SAMPLE_CONDITION_RECORD`.
- **Luồng phụ / ngoại lệ:**
  - A1: `not_acceptable` nhưng thiếu ghi chú lý do → 400 code `CONDITION_REASON_REQUIRED` (BR-SAMPLE-003).
- **Hậu điều kiện:** tình trạng mẫu lưu lại, hiển thị trên chi tiết mẫu và phiếu kết quả.
- **Business Rules:** BR-SAMPLE-003.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN mẫu `SP-2026-0007` WHEN ghi tình trạng "đạt" THEN lưu `acceptable`, audit `SAMPLE_CONDITION_RECORD`.
  - AC2 (lỗi input — không đạt thiếu lý do): GIVEN ghi tình trạng "không đạt" WHEN không nhập `condition_note` THEN trả 400 code `CONDITION_REASON_REQUIRED`, không lưu.
  - AC3 (hiển thị): GIVEN mẫu ghi "không đạt — bao bì rách" WHEN mở chi tiết mẫu hoặc xuất phiếu kết quả THEN tình trạng "không đạt — bao bì rách" hiển thị rõ.
- **Data cần thiết:** Sample.condition_note, Sample.condition_status ∈ {acceptable, not_acceptable, null}.
- **API cần:** "ghi/cập nhật tình trạng mẫu khi nhận".

---

### FR-SAMPLE-005: Phân công mẫu / phần việc cho KTV

- **Mô tả:** Giao một (hoặc nhiều) phần việc/chỉ tiêu của mẫu cho KTV cụ thể. Một mẫu có nhiều phần việc cho nhiều người (R6). Khi mẫu có ≥ 1 assignment → chuyển `received → assigned`.
- **Độ ưu tiên:** P0
- **Actor:** **Trưởng nhóm phòng mình** (quyền `sample:assign` — OQ#11), Ban lãnh đạo, Admin. Người được giao là KTV cùng phòng. (KTV thường KHÔNG phân công được.)
- **Tiền điều kiện:** mẫu ở trạng thái `received` hoặc `assigned`; user có quyền `sample:assign` trong phạm vi phòng ban (là trưởng nhóm phòng đó / Admin / Ban lãnh đạo — BR-SAMPLE-022).
- **Luồng chính:**
  1. User mở mẫu → "Phân công" → chọn phần việc (part_name) + chọn người được giao (`assigned_to`, KTV cùng phòng).
  2. Hệ thống validate quyền `sample:assign` (BR-SAMPLE-022) + người được giao cùng phòng (BR-SAMPLE-006) → tạo `sample_assignments` (assigned_by=user, assigned_to, part_name, status='assigned', assigned_at).
  3. Nếu mẫu đang `received` → chuyển `status='assigned'` (BR-SAMPLE-001).
  4. Tạo `notifications` in-app cho người được giao; ghi `audit_logs` action=`SAMPLE_ASSIGN`.
- **Luồng phụ / ngoại lệ:**
  - A1: `assigned_to` không thuộc phòng ban của mẫu → 422 code `ASSIGNEE_OUT_OF_DEPT` (BR-SAMPLE-006).
  - A2: phân công khi mẫu đã `done`/`returned` → 422 code `INVALID_STATE_TRANSITION` (BR-SAMPLE-001).
  - A3: phân trùng cùng part_name cho 2 người → cảnh báo; cho phép nếu KH muốn 2 người cùng làm (OPEN QUESTION #7).
- **Hậu điều kiện:** assignment tồn tại; mẫu ≥ `assigned`; người được giao nhận thông báo; audit ghi nhận.
- **Business Rules:** BR-SAMPLE-001, BR-SAMPLE-006, BR-SAMPLE-013, BR-SAMPLE-022.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN mẫu `SP-2026-0007` (`received`, phòng Hóa lý) WHEN trưởng nhóm phòng Hóa lý phân công phần "độ ẩm" cho KTV A cùng phòng THEN tạo assignment, mẫu chuyển `assigned`, KTV A nhận notification, audit `SAMPLE_ASSIGN`.
  - AC2 (edge — người ngoài phòng): GIVEN mẫu phòng Hóa lý WHEN phân công cho KTV thuộc phòng Vi sinh THEN trả 422 code `ASSIGNEE_OUT_OF_DEPT`, không tạo assignment.
  - AC3 (RBAC — KTV thường không phân công): GIVEN KTV thường (không phải trưởng nhóm) phòng Hóa lý WHEN phân công THEN trả 403 code `FORBIDDEN`; GIVEN trưởng nhóm phòng Hóa lý THEN thành công.
  - AC4 (state — không phân khi done): GIVEN mẫu đã `done` WHEN phân công thêm THEN trả 422 code `INVALID_STATE_TRANSITION`.
- **Data cần thiết:** SampleAssignment { id, sample_id(FK), assigned_to(FK→users), assigned_by(FK→users), part_name, status ∈ {assigned, in_progress, result_entered, approved}, assigned_at }.
- **API cần:** "phân công phần việc cho KTV", "liệt kê phân công theo mẫu", "hủy/đổi phân công (chưa nhập kết quả)".

---

### FR-SAMPLE-006: Tạo phiếu công việc & chuyển giao mẫu (handover) có lịch sử

- **Mô tả:** Chuyển **quyền giữ mẫu vật lý** từ người này sang người khác (vd KTV bàn giao mẫu cho KTV khác hoặc về kho). Mỗi lần chuyển ghi `sample_handovers` (from_user, to_user, at, lý do) — **bất biến**; cập nhật người giữ hiện tại. (R5)
- **Độ ưu tiên:** P0
- **Actor:** KTV (phòng mình — người đang giữ mẫu), trưởng nhóm/Ban lãnh đạo (điều phối), Admin.
- **Tiền điều kiện:** mẫu tồn tại, chưa `returned`; user là **người giữ hiện tại** của mẫu hoặc có quyền điều phối (trưởng nhóm/Admin) trong phạm vi phòng ban (BR-SAMPLE-007).
- **Luồng chính:**
  1. User mở mẫu → "Chuyển giao" → chọn người nhận (`to_user` cùng phòng) + lý do chuyển.
  2. Hệ thống validate người chuyển là người giữ hiện tại (hoặc có quyền điều phối) + người nhận cùng phòng (BR-SAMPLE-007).
  3. Ghi `sample_handovers` (from_user=người giữ hiện tại, to_user, at=now, reason); cập nhật người giữ hiện tại = `to_user`.
  4. Tạo notification cho người nhận; ghi `audit_logs` action=`SAMPLE_HANDOVER`.
- **Luồng phụ / ngoại lệ:**
  - A1: user không phải người giữ hiện tại và không có quyền điều phối → 403 code `NOT_CURRENT_CUSTODIAN` (BR-SAMPLE-007).
  - A2: `to_user` ngoài phòng ban của mẫu → 422 code `HANDOVER_OUT_OF_DEPT`.
  - A3: chuyển cho chính người đang giữ → 422 code `INVALID_HANDOVER` (vô nghĩa).
  - A4: mẫu đã `returned` → 422 code `INVALID_STATE_TRANSITION`.
- **Hậu điều kiện:** chain of custody cập nhật; người giữ hiện tại = `to_user`; lịch sử bất biến.
- **Business Rules:** BR-SAMPLE-007, BR-SAMPLE-013, BR-SAMPLE-017 (immutable handover).
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN mẫu `SP-2026-0007` đang do KTV A giữ WHEN KTV A chuyển cho KTV B cùng phòng kèm lý do "chuyển sang đo phổ" THEN ghi 1 `sample_handovers` (from=A, to=B, at, reason), người giữ hiện tại = B, B nhận notification, audit `SAMPLE_HANDOVER`.
  - AC2 (edge — không phải người giữ): GIVEN mẫu do KTV A giữ WHEN KTV C (không phải A, không trưởng nhóm) cố chuyển mẫu THEN trả 403 code `NOT_CURRENT_CUSTODIAN`, người giữ không đổi.
  - AC3 (RBAC scope): GIVEN mẫu phòng Hóa lý WHEN chuyển cho người phòng Vi sinh THEN trả 422 code `HANDOVER_OUT_OF_DEPT`.
  - AC4 (immutable): GIVEN một bản ghi handover đã tạo WHEN thử gọi API sửa/xóa handover THEN không có endpoint cho phép (404/405) — lịch sử chain of custody bất biến.
- **Data cần thiết:** SampleHandover { id, sample_id(FK), from_user(FK→users), to_user(FK→users), reason, at }; người giữ hiện tại suy ra từ handover gần nhất (hoặc cột denormalized `current_custodian_id` để truy vấn nhanh — schema-designer quyết).
- **API cần:** "chuyển giao mẫu (handover) kèm lý do", "lấy người giữ hiện tại của mẫu".

---

### FR-SAMPLE-007: Xem chuỗi hành trình mẫu (chain of custody) — 17025 §7.4

- **Mô tả:** Hiển thị toàn bộ hành trình giữ mẫu theo thời gian: ai giữ, từ khi nào đến khi nào, lý do chuyển — dựng từ bản ghi tiếp nhận (người giữ ban đầu = `received_by`) + chuỗi `sample_handovers`. Bất biến, truy xuất khi audit VILAS.
- **Độ ưu tiên:** P1
- **Actor:** mọi vai trò có quyền xem M1 (Admin, Ban lãnh đạo, KTV). Kế toán không truy cập.
- **Tiền điều kiện:** mẫu tồn tại; đã đăng nhập.
- **Luồng chính:**
  1. User mở chi tiết mẫu → tab "Chuỗi hành trình".
  2. Hệ thống dựng timeline: [received_at → handover1.at] giữ bởi received_by; [handover1.at → handover2.at] giữ bởi to_user1; ... ; đoạn cuối tới hiện tại giữ bởi người giữ hiện tại.
- **Luồng phụ / ngoại lệ:**
  - A1: chưa có handover → timeline chỉ 1 đoạn: từ `received_at` tới hiện tại, giữ bởi `received_by`.
- **Hậu điều kiện:** chỉ đọc.
- **Business Rules:** BR-SAMPLE-017, BR-SAMPLE-014 (phạm vi đọc, Kế toán chặn).
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN mẫu có received_by=A và 2 handover (A→B lúc t1, B→C lúc t2) WHEN xem chuỗi hành trình THEN hiển thị đúng 3 đoạn: A (received_at→t1), B (t1→t2), C (t2→hiện tại), đúng thứ tự thời gian.
  - AC2 (chưa chuyển): GIVEN mẫu chưa handover WHEN xem chuỗi THEN 1 đoạn duy nhất: received_by giữ từ received_at tới hiện tại.
  - AC3 (RBAC — Kế toán chặn): GIVEN Kế toán WHEN gọi API chuỗi hành trình THEN trả 403 (B03).
- **Data cần thiết:** đọc Sample.received_by/received_at + danh sách `sample_handovers` theo `at`.
- **API cần:** "lấy chuỗi hành trình mẫu (timeline người giữ)".

---

### FR-SAMPLE-008: Nhập kết quả phần việc được giao

- **Mô tả:** KTV được giao một phần việc nhập kết quả của phần đó (`result_data` JSONB linh hoạt theo chỉ tiêu) + đính kèm raw data (FR-SAMPLE-009). Chỉ người được giao phần việc mới nhập được phần đó. Khi assignment có kết quả → chuyển mẫu `assigned → testing` (lần đầu) và đánh dấu assignment `result_entered`. **Kết quả vừa nhập (chưa approved) CHƯA công khai toàn lab** — chỉ người nhập + người duyệt (trưởng nhóm) + Admin/Ban lãnh đạo xem (OQ#3 — BR-SAMPLE-021).
- **Độ ưu tiên:** P0
- **Actor:** KTV được giao phần việc đó (✅ được giao), Admin. Ban lãnh đạo xem. Kế toán không truy cập.
- **Tiền điều kiện:** assignment tồn tại, `assigned_to` = user hiện tại (hoặc Admin); kết quả phần đó chưa `approved` (BR-SAMPLE-010).
- **Luồng chính:**
  1. KTV mở phần việc được giao → "Nhập kết quả" → nhập `result_data` (theo biểu mẫu chỉ tiêu) + ghi chú.
  2. Hệ thống validate người nhập = người được giao (BR-SAMPLE-008) → lưu `sample_results` (version=1 nếu lần đầu) với `entered_by`, `entered_at`, `approved_by=null`.
  3. Cập nhật assignment.status='result_entered'; nếu mẫu đang `assigned` → chuyển `testing` (BR-SAMPLE-001).
  4. Kết quả ở trạng thái **chờ duyệt — chưa công khai toàn lab** (BR-SAMPLE-021); ghi `audit_logs` action=`SAMPLE_RESULT_ENTER`.
- **Luồng phụ / ngoại lệ:**
  - A1: user không phải người được giao phần đó → 403 code `NOT_ASSIGNEE` (BR-SAMPLE-008).
  - A2: phần việc đã có kết quả `approved` → 422 code `RESULT_LOCKED` (sửa = tạo phiên bản mới qua FR-SAMPLE-010 — BR-SAMPLE-010).
  - A3: `result_data` rỗng/không hợp lệ theo biểu mẫu chỉ tiêu → 400 code `VALIDATION_ERROR`.
- **Hậu điều kiện:** kết quả lưu (trạng thái chờ duyệt, chưa công khai); assignment `result_entered`; mẫu ≥ `testing`; audit ghi nhận.
- **Business Rules:** BR-SAMPLE-001, BR-SAMPLE-008, BR-SAMPLE-010, BR-SAMPLE-013, BR-SAMPLE-021.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN KTV A được giao phần "độ ẩm" mẫu `SP-2026-0007` (`assigned`) WHEN A nhập kết quả độ ẩm = 12.5% THEN lưu `sample_results` version=1 entered_by=A, assignment='result_entered', mẫu chuyển `testing`, audit `SAMPLE_RESULT_ENTER`.
  - AC2 (RBAC — không phải người được giao): GIVEN phần "độ ẩm" giao cho A WHEN KTV B (không được giao phần đó) nhập kết quả phần đó THEN trả 403 code `NOT_ASSIGNEE`, không lưu.
  - AC3 (immutable — đã approved): GIVEN phần "độ ẩm" đã `approved` WHEN A sửa trực tiếp kết quả phần đó THEN trả 422 code `RESULT_LOCKED` (phải tạo phiên bản mới — FR-SAMPLE-010).
  - AC4 (lỗi input): GIVEN form nhập kết quả WHEN `result_data` rỗng THEN trả 400 code `VALIDATION_ERROR`, không lưu.
  - AC5 (RBAC — Kế toán chặn): GIVEN Kế toán WHEN gọi API nhập/xem kết quả THEN trả 403 (B03).
  - AC6 (chưa công khai trước duyệt — OQ#3): GIVEN kết quả "độ ẩm" vừa nhập (chưa approved) WHEN KTV phòng KHÁC (không phải người nhập/người duyệt/Admin/Lãnh đạo) mở tab Kết quả THEN KHÔNG thấy kết quả này (hiển thị "chưa có kết quả công khai") — BR-SAMPLE-021.
- **Data cần thiết:** SampleResult { id, assignment_id(FK), version(int, default 1), result_data(JSONB), entered_by(FK→users), entered_at, approved_by(FK→users null), approved_at, is_current(bool) }.
- **API cần:** "nhập kết quả phần việc", "xem kết quả phần việc / cả mẫu (theo phạm vi đọc)".

---

### FR-SAMPLE-009: Đính kèm file kết quả (raw data, ảnh, Excel) — 17025 §7.5

- **Mô tả:** Đính kèm bản ghi gốc (raw data) cho kết quả phần việc: file máy đo xuất ra, ảnh, Excel. Hồ sơ kỹ thuật gốc theo §7.5. Lưu MinIO qua `attachments` (owner_type=`sample_result`).
- **Độ ưu tiên:** P0
- **Actor:** KTV được giao phần đó, Admin. Ban lãnh đạo/KTV xem được (tải) **theo phạm vi đọc kết quả — BR-SAMPLE-021**. Kế toán không truy cập.
- **Tiền điều kiện:** kết quả phần việc tồn tại; user là người nhập phần đó hoặc Admin.
- **Luồng chính:**
  1. KTV mở kết quả phần việc → "Đính kèm raw data" → upload file.
  2. Hệ thống validate loại + dung lượng (BR-SAMPLE-012) → lưu MinIO → ghi `attachments` (owner_type=`sample_result`, owner_id=result.id).
  3. Ghi `audit_logs` action=`SAMPLE_RESULT_ATTACH`.
- **Luồng phụ / ngoại lệ:**
  - A1: file sai loại/quá lớn → 422 (BR-SAMPLE-012).
  - A2: đính kèm vào kết quả đã `approved` → tạo phiên bản mới hoặc chặn (BR-SAMPLE-010 — OPEN QUESTION #8: có cho thêm raw data sau approve không).
- **Hậu điều kiện:** raw data truy xuất được (theo phạm vi đọc); lượt tải audit (R15).
- **Business Rules:** BR-SAMPLE-010, BR-SAMPLE-012, BR-SAMPLE-021.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN kết quả phần "kim loại nặng" mẫu `SP-2026-0007` WHEN upload "raw-icp.xlsx" (3 MB) THEN trả 201, file tải lại được, audit `SAMPLE_RESULT_ATTACH`.
  - AC2 (edge — sai loại): GIVEN file "data.bin" WHEN upload THEN trả 422 code `INVALID_FILE_TYPE`.
  - AC3 (RBAC): GIVEN KTV không phải người nhập phần đó WHEN upload raw data phần đó THEN trả 403.
- **Data cần thiết:** Attachment { owner_type=`sample_result`, owner_id, file_key, file_name, mime, size, uploaded_by, uploaded_at }.
- **API cần:** "upload raw data cho kết quả", "liệt kê/tải raw data của kết quả".

---

### FR-SAMPLE-010: Phê duyệt kết quả & versioning (immutable) — 17025 §7.8, §8.4

- **Mô tả:** Reviewer/approver (**trưởng nhóm** phòng đó/Admin/Ban lãnh đạo) duyệt kết quả phần việc trước khi chốt. Sau khi `approved`, kết quả **bất biến** VÀ **mới được công khai nội bộ toàn lab** (OQ#3 — BR-SAMPLE-021). Muốn sửa phải tạo **phiên bản mới** (version+1), giữ bản cũ, ghi audit. Người **nhập** kết quả KHÔNG được tự duyệt kết quả của chính mình.
- **Độ ưu tiên:** P1 (theo demo-scope F1.3.4) — nhưng là **P0 về tính bất biến/audit** vì VILAS §8.4 yêu cầu.
- **Actor:** **Trưởng nhóm phòng đó** (quyền `sample_result:approve` — OQ#11), Ban lãnh đạo, Admin. KTV nhập KHÔNG tự duyệt; KTV thường không có quyền duyệt.
- **Tiền điều kiện:** kết quả phần việc đã được nhập (`result_entered`); user có quyền `sample_result:approve` trong phạm vi (là trưởng nhóm phòng đó / Admin / Ban lãnh đạo — BR-SAMPLE-022); user ≠ người nhập kết quả đó (BR-SAMPLE-011).
- **Luồng chính:**
  1. Approver mở kết quả → review → "Duyệt" (hoặc "Trả lại để sửa").
  2. **Duyệt:** hệ thống validate quyền `sample_result:approve` (BR-SAMPLE-022) + approver ≠ entered_by (BR-SAMPLE-011) → set `approved_by`, `approved_at`, đánh dấu kết quả `is_current=true`, khóa bất biến, **mở công khai nội bộ** (BR-SAMPLE-021); assignment.status='approved'; ghi `audit_logs` action=`SAMPLE_RESULT_APPROVE`.
  3. Khi **tất cả** assignment của mẫu đều `approved` → mẫu **đủ điều kiện** chuyển `done`, nhưng **chỉ chuyển khi trưởng nhóm chốt thủ công** (FR-SAMPLE-019, OQ#2 — KHÔNG auto-done).
  4. **Sửa sau approve (tạo phiên bản mới):** approver/KTV mở kết quả approved → "Tạo phiên bản sửa" → hệ thống tạo `sample_results` mới version+1 (đưa về trạng thái chờ duyệt — tạm rút công khai cho tới khi duyệt lại), giữ nguyên bản cũ; ghi audit `SAMPLE_RESULT_REVISE` với lý do bắt buộc.
- **Luồng phụ / ngoại lệ:**
  - A1: approver = người nhập kết quả → 403 code `SELF_APPROVAL_FORBIDDEN` (BR-SAMPLE-011).
  - A2: duyệt kết quả chưa nhập → 422 code `NO_RESULT_TO_APPROVE`.
  - A3: cố sửa trực tiếp kết quả `approved` (PUT/PATCH) → 422 code `RESULT_LOCKED`; chỉ cho phép qua "tạo phiên bản mới" (BR-SAMPLE-010).
  - A4: tạo phiên bản sửa thiếu lý do → 400 code `REVISION_REASON_REQUIRED`.
  - A5: "Trả lại để sửa" → assignment về `in_progress`/`assigned`, KTV nhập lại (không tạo version mới vì chưa từng approved).
  - A6: user không có quyền `sample_result:approve` (KTV thường) → 403 `FORBIDDEN` (BR-SAMPLE-022).
- **Hậu điều kiện:** kết quả approved bất biến + công khai nội bộ; mọi sửa tạo version mới truy vết được; mẫu đủ điều kiện `done` khi mọi part approved (chốt ở FR-SAMPLE-019).
- **Business Rules:** BR-SAMPLE-001, BR-SAMPLE-010, BR-SAMPLE-011, BR-SAMPLE-013, BR-SAMPLE-021, BR-SAMPLE-022.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN kết quả phần "độ ẩm" do KTV A nhập (`result_entered`) WHEN trưởng nhóm T (≠ A, phòng đó) duyệt THEN `approved_by`=T, `approved_at` set, assignment='approved', kết quả **mở công khai nội bộ**, audit `SAMPLE_RESULT_APPROVE`.
  - AC2 (tách nhập–duyệt): GIVEN KTV A nhập kết quả phần "độ ẩm" WHEN A tự duyệt kết quả đó THEN trả 403 code `SELF_APPROVAL_FORBIDDEN`.
  - AC3 (immutable — sửa sau approve tạo version): GIVEN kết quả "độ ẩm" đã approved version=1 WHEN tạo phiên bản sửa kèm lý do "phát hiện sai số hiệu chuẩn" THEN có `sample_results` version=2 (chờ duyệt, tạm rút công khai), bản version=1 vẫn tồn tại nguyên vẹn, audit `SAMPLE_RESULT_REVISE` với lý do.
  - AC4 (immutable — chặn sửa trực tiếp): GIVEN kết quả approved WHEN gọi PATCH sửa trực tiếp `result_data` THEN trả 422 code `RESULT_LOCKED`.
  - AC5 (lỗi input — version thiếu lý do): GIVEN tạo phiên bản sửa WHEN không nhập lý do THEN trả 400 code `REVISION_REASON_REQUIRED`.
  - AC6 (đủ điều kiện done KHÔNG auto): GIVEN mẫu có 2 phần việc đều approved WHEN duyệt phần cuối THEN mẫu **vẫn ở `testing`** (đủ điều kiện nhưng chưa `done`); chỉ `done` khi trưởng nhóm chốt (FR-SAMPLE-019).
  - AC7 (RBAC — KTV thường không duyệt): GIVEN KTV thường không có quyền `sample_result:approve` WHEN duyệt THEN trả 403; GIVEN trưởng nhóm phòng đó THEN cho duyệt.
- **Data cần thiết:** SampleResult { ..., version, is_current, approved_by, approved_at }; bản ghi revision giữ lịch sử version; lý do revise lưu (note/audit detail).
- **API cần:** "duyệt kết quả phần việc", "trả lại kết quả để sửa", "tạo phiên bản sửa kết quả (kèm lý do)".

---

### FR-SAMPLE-019: Trưởng nhóm chốt hoàn thành mẫu (finalize `testing → done`) — OQ#2

- **Mô tả:** Sau khi **mọi phần việc của mẫu đã `approved`**, mẫu chỉ chuyển `done` khi **trưởng nhóm (hoặc Admin/Ban lãnh đạo) thực hiện hành động chốt thủ công**. Hệ thống KHÔNG tự động chuyển `done` (OQ#2 đã chốt 19/06/2026). Khi chốt, hệ thống set `completed_at`, chuyển `status='done'` và ghi audit.
- **Độ ưu tiên:** P0
- **Actor:** **Trưởng nhóm phòng đó** (quyền `sample:finalize` — OQ#11), Ban lãnh đạo, Admin. KTV thường KHÔNG chốt được.
- **Tiền điều kiện:** mẫu ở `testing` hoặc `overdue`; **mọi assignment của mẫu đã `approved`** (BR-SAMPLE-020); nếu mẫu từng `overdue` thì đã nhập lý do trễ (BR-SAMPLE-009); user có quyền `sample:finalize` trong phạm vi (BR-SAMPLE-022).
- **Luồng chính:**
  1. Trưởng nhóm mở mẫu (mọi phần việc đã approved) → nút "Chốt hoàn thành mẫu" được kích hoạt.
  2. Hệ thống validate: tất cả assignment `approved` (BR-SAMPLE-020) + quyền `sample:finalize` (BR-SAMPLE-022) + (nếu overdue) đã có lý do trễ (BR-SAMPLE-009).
  3. Set `completed_at`=now, chuyển `status='done'` (BR-SAMPLE-001); ghi `audit_logs` action=`SAMPLE_FINALIZE` (kèm danh sách part approved tại thời điểm chốt).
- **Luồng phụ / ngoại lệ:**
  - A1: còn ≥ 1 assignment chưa `approved` → 422 code `RESULTS_NOT_APPROVED` (không cho chốt — BR-SAMPLE-020).
  - A2: mẫu `overdue` chưa nhập lý do trễ → 422 code `OVERDUE_REASON_REQUIRED` (BR-SAMPLE-009).
  - A3: user không có quyền `sample:finalize` (KTV thường) → 403 `FORBIDDEN` (BR-SAMPLE-022).
  - A4: mẫu đã `done`/`returned` → 422 code `INVALID_STATE_TRANSITION`.
- **Hậu điều kiện:** mẫu `done`, `completed_at` set (phục vụ on-time rate); sẵn sàng xuất phiếu (FR-SAMPLE-016).
- **Business Rules:** BR-SAMPLE-001, BR-SAMPLE-009, BR-SAMPLE-013, BR-SAMPLE-020, BR-SAMPLE-022.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN mẫu `SP-2026-0007` (`testing`) có 2 phần việc đều `approved` WHEN trưởng nhóm phòng đó bấm "Chốt hoàn thành mẫu" THEN mẫu chuyển `done`, `completed_at` set, audit `SAMPLE_FINALIZE`.
  - AC2 (KHÔNG auto-done — OQ#2): GIVEN trưởng nhóm vừa duyệt phần việc cuối (mọi part approved) NHƯNG chưa bấm chốt WHEN kiểm tra trạng thái mẫu THEN mẫu **vẫn `testing`** (không tự `done`).
  - AC3 (chặn chốt khi chưa approved hết): GIVEN mẫu còn 1 phần việc `result_entered` (chưa approved) WHEN trưởng nhóm bấm chốt THEN trả 422 code `RESULTS_NOT_APPROVED`, mẫu giữ `testing`.
  - AC4 (RBAC — KTV thường không chốt): GIVEN KTV thường phòng đó WHEN bấm chốt THEN trả 403 `FORBIDDEN`; GIVEN trưởng nhóm phòng đó THEN cho chốt.
  - AC5 (overdue chưa nhập lý do): GIVEN mẫu `overdue` mọi part approved nhưng chưa nhập lý do trễ WHEN chốt THEN trả 422 code `OVERDUE_REASON_REQUIRED`.
- **Data cần thiết:** Sample.status (done), Sample.completed_at; đọc tất cả `sample_assignments.status` của mẫu.
- **API cần:** "chốt hoàn thành mẫu (finalize)".

---

### FR-SAMPLE-011: Xem kết quả công khai nội bộ lab (CHỈ SAU KHI approved) — OQ#3

- **Mô tả:** Hiển thị kết quả mẫu (theo từng phần việc) cho người dùng trong lab. **Phạm vi xem theo OQ#3 đã chốt 19/06/2026:** kết quả **đã `approved`** công khai nội bộ toàn lab (mọi vai trò có quyền xem M1, đọc); kết quả **chưa `approved`** CHỈ hiện cho **người nhập (entered_by) + người duyệt (trưởng nhóm phòng đó) + Admin/Ban lãnh đạo**. **Kế toán bị chặn** (B03). "Công khai" = nội bộ lab, KHÔNG có portal khách hàng (A02).
- **Độ ưu tiên:** P0
- **Actor:** Admin, Ban lãnh đạo, KTV (mọi phòng, đọc kết quả đã approved). Kế toán không truy cập.
- **Tiền điều kiện:** đã đăng nhập; có quyền xem M1.
- **Luồng chính:**
  1. User mở mẫu → tab "Kết quả".
  2. Hệ thống lọc theo phạm vi đọc (BR-SAMPLE-021): hiển thị các phần việc có kết quả **đã approved** (chỉ tiêu, `result_data`, người nhập, người duyệt, version hiện tại, raw data đính kèm). Kết quả chưa approved chỉ hiện nếu user là người nhập/người duyệt/Admin/Lãnh đạo.
- **Luồng phụ / ngoại lệ:**
  - A1: phần việc chưa có kết quả approved và user không thuộc nhóm được xem trước → hiển thị "chưa có kết quả công khai".
  - A2: mẫu chưa có phần việc nào approved → màn công khai trống với người ngoài (chỉ người nhập/duyệt/Admin/Lãnh đạo thấy bản chờ duyệt).
- **Hậu điều kiện:** chỉ đọc; kết quả chưa duyệt KHÔNG xuất hiện ở màn công khai với người không có quyền xem trước.
- **Business Rules:** BR-SAMPLE-014 (phạm vi đọc, Kế toán chặn), BR-SAMPLE-021 (chỉ công khai sau approved).
- **Acceptance Criteria:**
  - AC1 (happy — đã approved công khai): GIVEN mẫu `SP-2026-0007` có 2 phần việc đã `approved` WHEN KTV phòng KHÁC mở tab Kết quả THEN xem được cả 2 kết quả (công khai nội bộ) ở mức đọc, không có nút sửa.
  - AC2 (chưa approved KHÔNG công khai — OQ#3): GIVEN phần "độ ẩm" mới `result_entered` (chưa approved) WHEN KTV phòng KHÁC (không phải người nhập/duyệt/Admin/Lãnh đạo) mở tab Kết quả THEN KHÔNG thấy kết quả "độ ẩm" (hiển thị "chưa có kết quả công khai").
  - AC3 (người nhập xem được bản chờ duyệt): GIVEN KTV A nhập kết quả "độ ẩm" chưa approved WHEN A mở tab Kết quả THEN A thấy kết quả mình nhập kèm trạng thái "chờ duyệt".
  - AC4 (trưởng nhóm/Lãnh đạo xem trước): GIVEN kết quả chưa approved WHEN trưởng nhóm phòng đó / Ban lãnh đạo / Admin mở THEN xem được (để duyệt).
  - AC5 (RBAC — Kế toán chặn): GIVEN Kế toán WHEN gọi API xem kết quả mẫu THEN trả 403 (B03).
  - AC6 (không có portal khách): GIVEN không có tài khoản khách hàng trong hệ thống (A02) WHEN khách muốn xem kết quả THEN không có cơ chế đăng nhập khách — chỉ nội bộ lab xem.
- **Data cần thiết:** đọc `sample_results` (is_current) join assignments + users; lọc theo `approved_by IS NOT NULL` cho người không thuộc nhóm xem trước.
- **API cần:** "xem tổng hợp kết quả mẫu (mọi phần việc — lọc theo phạm vi đọc)".

---

### FR-SAMPLE-012: Đặt deadline / turnaround time cho mẫu

- **Mô tả:** Đặt và cập nhật `deadline_at` (hạn hoàn thành mẫu) — **riêng cho từng mẫu**. Có thể đặt khi thêm mẫu (FR-SAMPLE-001) và cập nhật sau (có audit). TAT = `deadline_at − received_at`.
- **Độ ưu tiên:** P0
- **Actor:** KTV (phòng mình), trưởng nhóm, Ban lãnh đạo, Admin.
- **Tiền điều kiện:** mẫu tồn tại, chưa `returned`.
- **Luồng chính:**
  1. User mở mẫu → "Đặt/Sửa deadline" → chọn `deadline_at`.
  2. Hệ thống validate `deadline_at > received_at` (BR-SAMPLE-002) → cập nhật → ghi `audit_logs` action=`SAMPLE_DEADLINE_SET` (lưu giá trị cũ→mới).
- **Luồng phụ / ngoại lệ:**
  - A1: `deadline_at ≤ received_at` → 422 code `INVALID_DEADLINE`.
  - A2: sửa deadline khi mẫu đã `overdue` → cho phép (vd gia hạn), nhưng vẫn giữ lý do trễ đã ghi (BR-SAMPLE-009); audit lưu thay đổi.
- **Hậu điều kiện:** deadline cập nhật; lịch sử thay đổi audit.
- **Business Rules:** BR-SAMPLE-002, BR-SAMPLE-013.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN mẫu received_at 19/06/2026 WHEN đặt deadline 25/06/2026 THEN cập nhật, audit `SAMPLE_DEADLINE_SET` ghi giá trị mới.
  - AC2 (lỗi input): GIVEN received_at 19/06/2026 WHEN đặt deadline 18/06/2026 THEN trả 422 code `INVALID_DEADLINE`.
  - AC3 (audit thay đổi): GIVEN sửa deadline từ 25/06 sang 28/06 WHEN lưu THEN audit ghi cũ=25/06, mới=28/06, user, correlation_id.
- **Data cần thiết:** Sample.deadline_at.
- **API cần:** "đặt/sửa deadline mẫu".

---

### FR-SAMPLE-013: Cron nhắc mẫu sắp tới hạn (in-app) — CRON-1

- **Mô tả:** Tác vụ định kỳ hằng ngày 07:00 quét mẫu có `deadline_at` trong N ngày tới và **chưa done** → tạo thông báo in-app cho người được giao + người giữ hiện tại + trưởng nhóm phòng.
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (APScheduler) → người nhận: assignee(s), người giữ hiện tại, trưởng nhóm/Admin.
- **Tiền điều kiện:** có mẫu với `deadline_at`; APScheduler chạy; Redis lock khả dụng.
- **Luồng chính:**
  1. 07:00 hằng ngày, APScheduler acquire Redis lock (tránh chạy trùng).
  2. Quét mẫu `status ∈ {received, assigned, testing}` (chưa done/returned) có `deadline_at` trong các mốc nhắc (mặc định còn ≤ 3 ngày và ≤ 1 ngày — OPEN QUESTION #4).
  3. Với mỗi mẫu tới mốc → tạo `notifications` (type=`SAMPLE_DUE_SOON`) cho người liên quan; chống trùng mỗi mẫu × mỗi mốc/ngày (BR-SAMPLE-018).
  4. Ghi log INFO số notification; release lock.
- **Luồng phụ / ngoại lệ:**
  - A1: Redis lock đã giữ → instance khác bỏ qua lần chạy.
  - A2: lỗi giữa chừng → log ERROR với correlationId; lần sau retry (idempotent nhờ chống trùng).
- **Hậu điều kiện:** thông báo in-app đúng mốc, không trùng.
- **Business Rules:** BR-SAMPLE-018.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN mẫu `deadline_at`=hôm nay+1 ngày, `status='testing'` WHEN cron 07:00 chạy THEN tạo notification `SAMPLE_DUE_SOON` (mốc-1-ngày) cho assignee + người giữ hiện tại.
  - AC2 (chống trùng): GIVEN cron đã tạo notification mốc-1-ngày cho mẫu X hôm nay WHEN chạy lại cùng ngày THEN KHÔNG tạo notification thứ 2 cho cùng mẫu × cùng mốc.
  - AC3 (lock): GIVEN 2 tiến trình cron khởi động đồng thời WHEN cùng 07:00 THEN chỉ 1 thực thi (Redis lock).
  - AC4 (mẫu đã done): GIVEN mẫu tới hạn nhưng đã `done` WHEN cron chạy THEN KHÔNG tạo notification.
- **Data cần thiết:** đọc `samples`; ghi `notifications`; cờ chống trùng (mẫu+mốc+ngày).
- **API cần:** không có endpoint công khai; scheduled job. Có thể có endpoint admin "chạy thủ công CRON-1" để test.

---

### FR-SAMPLE-014: Cron đánh dấu trễ hạn + bắt buộc nhập lý do trễ — CRON-2 (R9)

- **Mô tả:** Tác vụ định kỳ hằng ngày 00:30 quét mẫu quá `deadline_at` mà chưa `done` → chuyển `status='overdue'` và tạo thông báo. Khi mẫu `overdue`, hệ thống **bắt buộc nhập lý do trễ** (`overdue_reasons`: lý do, người nhập, thời điểm) trước khi trưởng nhóm chốt mẫu (FR-SAMPLE-019) / trả kết quả.
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (CRON-2) đánh dấu; KTV/trưởng nhóm nhập lý do trễ.
- **Tiền điều kiện:** có mẫu quá hạn chưa done; APScheduler + Redis lock.
- **Luồng chính (cron):**
  1. 00:30 hằng ngày, acquire Redis lock.
  2. Quét mẫu `status ∈ {received, assigned, testing}` có `deadline_at < now` → chuyển `status='overdue'` (BR-SAMPLE-001).
  3. Tạo `notifications` (type=`SAMPLE_OVERDUE`) cho assignee + người giữ + trưởng nhóm; ghi `audit_logs` action=`SAMPLE_MARK_OVERDUE`.
  4. Release lock.
- **Luồng nhập lý do trễ (người dùng):**
  1. Mẫu `overdue` hiển thị yêu cầu "Nhập lý do trễ hạn".
  2. User nhập lý do → hệ thống ghi `overdue_reasons` (reason, by, at) → audit `SAMPLE_OVERDUE_REASON`.
  3. Mẫu vẫn tiếp tục được làm; khi hoàn thành (mọi part approved) → **trưởng nhóm chốt** chuyển `done` (FR-SAMPLE-019, BR-SAMPLE-020); `done` từ nhánh overdue được đánh dấu "hoàn thành trễ" để báo cáo on-time rate.
- **Luồng phụ / ngoại lệ:**
  - A1: cố chốt `done` (FR-SAMPLE-019)/`returned` mẫu `overdue` mà chưa nhập lý do trễ → 422 code `OVERDUE_REASON_REQUIRED` (BR-SAMPLE-009).
  - A2: deadline được gia hạn (FR-SAMPLE-012) sau khi overdue → trạng thái có thể trở lại testing nếu deadline mới > now (OPEN QUESTION #9); lý do trễ đã ghi vẫn giữ.
- **Hậu điều kiện:** mẫu quá hạn được đánh dấu `overdue`; lý do trễ bắt buộc & truy vết.
- **Business Rules:** BR-SAMPLE-001, BR-SAMPLE-009, BR-SAMPLE-018.
- **Acceptance Criteria:**
  - AC1 (happy — cron đánh dấu): GIVEN mẫu `deadline_at`=hôm qua, `status='testing'` WHEN CRON-2 00:30 chạy THEN mẫu chuyển `overdue`, tạo notification `SAMPLE_OVERDUE`, audit `SAMPLE_MARK_OVERDUE`.
  - AC2 (bắt buộc lý do): GIVEN mẫu `overdue` chưa có lý do trễ WHEN trưởng nhóm cố chốt `done`/`returned` THEN trả 422 code `OVERDUE_REASON_REQUIRED`; WHEN nhập lý do trễ rồi chốt THEN cho phép.
  - AC3 (lý do trễ audit đầy đủ): GIVEN nhập lý do trễ "máy đo hỏng chờ sửa" WHEN lưu THEN `overdue_reasons` có reason + by + at, audit `SAMPLE_OVERDUE_REASON` với correlation_id.
  - AC4 (idempotent): GIVEN mẫu đã `overdue` WHEN CRON-2 chạy lại THEN không tạo notification trùng cùng ngày, không đổi trạng thái sai.
  - AC5 (đánh dấu hoàn thành trễ): GIVEN mẫu từng `overdue` rồi được trưởng nhóm chốt `done` WHEN chuyển `done` THEN `completed_at > deadline_at` → mẫu tính là "trễ" trong on-time rate (FR-SAMPLE-015).
- **Data cần thiết:** Sample.status (overdue), Sample.completed_at; OverdueReason { id, sample_id(FK), reason, by(FK→users), at }.
- **API cần:** scheduled CRON-2; "nhập lý do trễ hạn cho mẫu"; endpoint admin "chạy thủ công CRON-2".

---

### FR-SAMPLE-015: Báo cáo on-time rate (tỷ lệ đúng hạn)

- **Mô tả:** Báo cáo tỷ lệ mẫu hoàn thành đúng hạn theo kỳ/phòng ban/người: on-time rate = (mẫu done với `completed_at ≤ deadline_at`) / (tổng mẫu done trong kỳ). Hiển thị kèm số mẫu trễ và lý do trễ.
- **Độ ưu tiên:** P1
- **Actor:** Ban lãnh đạo, Admin, KTV (phạm vi phòng, đọc). Kế toán không truy cập.
- **Tiền điều kiện:** đã đăng nhập; có mẫu done trong kỳ.
- **Luồng chính:**
  1. User chọn khoảng ngày + chiều tổng hợp (phòng/người) + bộ lọc.
  2. Hệ thống tính on-time rate trong phạm vi quyền; liệt kê mẫu trễ kèm lý do (`overdue_reasons`).
  3. Cho xuất Excel/PDF (qua M6).
- **Luồng phụ / ngoại lệ:**
  - A1: không có mẫu done trong kỳ → on-time rate hiển thị "không có dữ liệu".
- **Hậu điều kiện:** chỉ đọc.
- **Business Rules:** BR-SAMPLE-014, BR-SAMPLE-019.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN tháng 5/2026 có 20 mẫu done, 18 đúng hạn WHEN báo cáo on-time rate tháng 5 THEN hiển thị 90.0% (18/20), liệt kê 2 mẫu trễ kèm lý do.
  - AC2 (RBAC scope): GIVEN KTV phòng "Hóa lý" WHEN xem báo cáo THEN chỉ tính mẫu phòng "Hóa lý".
  - AC3 (RBAC — Kế toán chặn): GIVEN Kế toán WHEN gọi báo cáo on-time THEN trả 403 (B03).
- **Data cần thiết:** aggregate `samples` (status=done, completed_at vs deadline_at) join phòng/người + `overdue_reasons`.
- **API cần:** "báo cáo on-time rate theo kỳ/phòng/người + xuất".

---

### FR-SAMPLE-016: Xuất phiếu kết quả thử nghiệm (PDF có mã)

- **Mô tả:** Sinh phiếu kết quả thử nghiệm PDF của mẫu: header (logo, tên lab, thông tin công nhận), `sample_code` + barcode/QR, mã phiếu (`request_code`), khách gửi, tình trạng mẫu khi nhận, danh sách chỉ tiêu + kết quả (chỉ kết quả `approved`), người thực hiện, người duyệt, ngày. Mẫu phải đã được trưởng nhóm chốt `done` (FR-SAMPLE-019) trước khi xuất. Khi xuất → chuyển/đánh dấu mẫu `returned` (trả kết quả). Portal khách hàng đã CẮT (A02) — phiếu PDF lưu/in nội bộ và gửi khách ngoài hệ thống.
- **Độ ưu tiên:** P1
- **Actor:** Trưởng nhóm/Ban lãnh đạo/Admin (người có quyền ban hành phiếu). KTV xem/tải nếu có quyền. Kế toán không truy cập.
- **Tiền điều kiện:** mẫu ở `done` (đã được trưởng nhóm chốt — FR-SAMPLE-019; mọi chỉ tiêu cần báo cáo đã `approved`); nếu từng `overdue` thì đã nhập lý do trễ (BR-SAMPLE-009).
- **Luồng chính:**
  1. User mở mẫu `done` → "Xuất phiếu kết quả".
  2. Hệ thống tổng hợp chỉ tiêu + kết quả `approved` (version hiện tại) → sinh PDF có `sample_code` + `request_code` + barcode/QR + người duyệt.
  3. Đánh dấu mẫu `returned` (BR-SAMPLE-001); lưu file PDF vào `attachments` (owner_type=`sample`, loại "result_report"); ghi `audit_logs` action=`SAMPLE_REPORT_EXPORT` (R15 — đếm lượt tải).
- **Luồng phụ / ngoại lệ:**
  - A1: mẫu chưa `done` (chưa được trưởng nhóm chốt / còn chỉ tiêu chưa approved) → 422 code `SAMPLE_NOT_FINALIZED`, không xuất.
  - A2: mẫu `overdue` chưa nhập lý do trễ → 422 code `OVERDUE_REASON_REQUIRED`.
  - A3: xuất lại phiếu sau khi đã returned → cho phép (in lại bản sao), audit ghi lần tải; nếu kết quả đã tạo version mới sau returned → phiếu phản ánh version hiện tại + đánh dấu "bản sửa đổi".
- **Hậu điều kiện:** PDF sinh ra phản ánh đúng kết quả approved; mẫu `returned`; lượt xuất audit.
- **Business Rules:** BR-SAMPLE-001, BR-SAMPLE-009, BR-SAMPLE-010, BR-SAMPLE-013, BR-SAMPLE-014, BR-SAMPLE-020.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN mẫu `done` (đã chốt) với 2 chỉ tiêu đều approved WHEN xuất phiếu THEN PDF chứa `sample_code` + `request_code` + QR, đủ 2 chỉ tiêu + kết quả approved + người duyệt; mẫu chuyển `returned`; audit `SAMPLE_REPORT_EXPORT`.
  - AC2 (edge — chưa done): GIVEN mẫu `testing` (mọi part approved nhưng trưởng nhóm chưa chốt) WHEN xuất phiếu THEN trả 422 code `SAMPLE_NOT_FINALIZED`, không xuất.
  - AC3 (overdue chưa nhập lý do): GIVEN mẫu `overdue` chưa nhập lý do trễ WHEN xuất phiếu THEN trả 422 code `OVERDUE_REASON_REQUIRED`.
  - AC4 (RBAC — Kế toán chặn): GIVEN Kế toán WHEN gọi xuất phiếu THEN trả 403 (B03).
  - AC5 (audit lượt tải): GIVEN xuất phiếu thành công WHEN kiểm tra audit THEN có `SAMPLE_REPORT_EXPORT` với user + sample_code + correlation_id.
- **Data cần thiết:** đọc Sample + TestRequest (request_code, customer) + condition + `sample_results` (approved, is_current) + người nhập/duyệt; sinh PDF (mã + QR).
- **API cần:** "xuất phiếu kết quả PDF của mẫu", "tải lại phiếu kết quả".

---

### FR-SAMPLE-017: State machine trạng thái mẫu (chuyển trạng thái hợp lệ)

- **Mô tả:** Quản lý trạng thái mẫu theo state machine xác định; chỉ cho phép chuyển trạng thái hợp lệ; mọi chuyển trạng thái ghi audit. Đây là FR nền cho FR-SAMPLE-005/008/010/014/016/019. **Lưu ý OQ#2:** chuyển `testing → done` (và `overdue → done`) KHÔNG tự động — chỉ xảy ra khi **trưởng nhóm chốt thủ công** qua FR-SAMPLE-019.
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (do các hành động nghiệp vụ kích hoạt) + trưởng nhóm (hành động chốt `done` — FR-019) + Admin (sửa trạng thái ngoại lệ có audit — OPEN QUESTION #10).
- **Tiền điều kiện:** mẫu tồn tại.

**Sơ đồ trạng thái (state machine):**

```
          thêm mẫu vào phiếu (FR-018 → FR-001)
                │
                ▼
          ┌───────────┐   phân công ≥1 part (FR-005)   ┌───────────┐
          │ received  │ ─────────────────────────────► │ assigned  │
          └───────────┘                                 └───────────┘
                │                                              │
                │                            nhập kết quả part đầu tiên (FR-008)
                │                                              ▼
                │                                        ┌───────────┐
                │                                        │  testing  │
                │                                        └───────────┘
                │                                              │
                │          mọi part approved (FR-010) ─► ĐỦ ĐIỀU KIỆN done
                │                                              │
                │              TRƯỞNG NHÓM CHỐT THỦ CÔNG (FR-019, OQ#2)
                │                       — KHÔNG auto —          ▼
                │                                        ┌───────────┐
                │            xuất phiếu kết quả (FR-016)  │   done    │
                │                                  ┌──────└───────────┘
                │                                  ▼
                │                            ┌───────────┐
                │                            │ returned  │ (trạng thái cuối)
                │                            └───────────┘
                │
                │  [NHÁNH NGOÀI LỀ — bất kỳ trạng thái chưa-done nào]
                ▼
  quá deadline_at & chưa done (CRON-2, FR-014)
                │
                ▼
          ┌───────────┐  nhập lý do trễ + mọi part approved + TRƯỞNG NHÓM CHỐT (FR-019)   ┌──────┐
          │  overdue  │ ───────────────────────────────────────────────────────────────► │ done │
          └───────────┘                                                                   └──────┘
                │  gia hạn deadline > now (FR-012, OQ#9 — tùy chốt)
                └──────────────► quay lại {assigned | testing} theo tiến độ
```

- **Phép chuyển HỢP LỆ (whitelist):**
  - `received → assigned` (khi có assignment đầu tiên — FR-005)
  - `received → overdue` / `assigned → overdue` / `testing → overdue` (CRON-2 khi quá hạn chưa done — FR-014)
  - `assigned → testing` (khi nhập kết quả part đầu tiên — FR-008)
  - `testing → done` (**chỉ khi trưởng nhóm chốt thủ công** sau khi mọi part approved — FR-019; OQ#2 — KHÔNG auto)
  - `overdue → done` (**chỉ khi trưởng nhóm chốt thủ công**, đã nhập lý do trễ + mọi part approved — FR-019/FR-010/FR-014)
  - `done → returned` (khi xuất phiếu kết quả — FR-016)
  - `overdue → {assigned|testing}` (chỉ khi gia hạn deadline > now — FR-012; OPEN QUESTION #9, tùy KH chốt)
- **Phép chuyển KHÔNG hợp lệ (bị chặn 422 `INVALID_STATE_TRANSITION`):** mọi cặp ngoài whitelist, vd `returned → *` (returned là trạng thái cuối), `done → testing` trực tiếp, `received → done` (bỏ qua nhập/duyệt kết quả), **`testing → done` TỰ ĐỘNG khi mọi part approved mà không có hành động chốt của trưởng nhóm** (OQ#2), v.v.
- **Luồng chính:** mọi hành động nghiệp vụ gọi hàm chuyển trạng thái trung tâm; hàm kiểm tra (from, to) ∈ whitelist trước khi cập nhật + ghi `audit_logs` action=`SAMPLE_STATE_CHANGE` (from→to, lý do/trigger).
- **Business Rules:** BR-SAMPLE-001, BR-SAMPLE-013, BR-SAMPLE-020.
- **Acceptance Criteria:**
  - AC1 (happy chuỗi chuẩn): GIVEN mẫu mới WHEN đi qua received→assigned→testing→(trưởng nhóm chốt)→done→returned theo các hành động hợp lệ THEN mỗi bước thành công và có audit `SAMPLE_STATE_CHANGE` đúng (from→to).
  - AC2 (chặn chuyển sai): GIVEN mẫu `returned` WHEN cố chuyển sang `testing` THEN trả 422 code `INVALID_STATE_TRANSITION`, trạng thái không đổi.
  - AC3 (chặn bỏ bước): GIVEN mẫu `received` WHEN cố chuyển thẳng `done` THEN trả 422 code `INVALID_STATE_TRANSITION`.
  - AC4 (KHÔNG auto-done — OQ#2): GIVEN mẫu `testing` mọi part approved WHEN không có hành động chốt của trưởng nhóm THEN mẫu **vẫn `testing`** (không tự `done`).
  - AC5 (nhánh overdue): GIVEN mẫu `testing` quá hạn WHEN CRON-2 chạy THEN chuyển `overdue` (hợp lệ); GIVEN `overdue` đã nhập lý do + mọi part approved WHEN trưởng nhóm chốt THEN chuyển `done` (hợp lệ).
  - AC6 (audit): GIVEN bất kỳ chuyển trạng thái nào WHEN xảy ra THEN có audit `SAMPLE_STATE_CHANGE` với from, to, trigger, user/hệ thống, correlation_id.
- **Data cần thiết:** Sample.status ENUM[received, assigned, testing, done, overdue, returned]; hàm transition trung tâm + whitelist.
- **API cần:** không expose chuyển trạng thái tùy ý ra client; chuyển trạng thái là hệ quả của các API nghiệp vụ (gồm FR-019 cho `done`). (Tùy OQ#10: endpoint admin sửa trạng thái ngoại lệ có audit.)

---

## 4. Business Rules

| ID | Quy tắc | Lý do nghiệp vụ | Hệ quả nếu vi phạm |
|----|---------|-----------------|--------------------|
| BR-SAMPLE-001 | Trạng thái mẫu chỉ chuyển theo whitelist state machine (FR-SAMPLE-017): received→assigned→testing→done→returned; nhánh overdue từ {received,assigned,testing}; overdue→done. **`testing→done` và `overdue→done` chỉ qua hành động chốt thủ công của trưởng nhóm (FR-019, KHÔNG auto)**; (overdue→assigned/testing chỉ khi gia hạn). Mọi cặp ngoài whitelist bị chặn | Vòng đời mẫu phải nhất quán, không nhảy bước (bỏ nhập/duyệt kết quả); chốt hoàn thành phải có người chịu trách nhiệm (OQ#2) | 422 `INVALID_STATE_TRANSITION` |
| BR-SAMPLE-002 | `deadline_at` bắt buộc khi thêm mẫu và phải > `received_at`; deadline riêng từng mẫu | Mọi mẫu có TAT để theo dõi đúng hạn (AS6) | 400 `DEADLINE_REQUIRED` / 422 `INVALID_DEADLINE` |
| BR-SAMPLE-003 | Tình trạng mẫu "không đạt" (`not_acceptable`) bắt buộc có `condition_note` (lý do) | Truy vết điều kiện tiếp nhận (17025 §7.4) | 400 `CONDITION_REASON_REQUIRED` |
| BR-SAMPLE-004 | Người được giao phần việc (`assigned_to`) phải thuộc cùng phòng ban với mẫu | Cách ly dữ liệu phòng ban (R13); KTV chỉ làm trong phòng mình | 422 `ASSIGNEE_OUT_OF_DEPT` |
| BR-SAMPLE-006 | (= BR-SAMPLE-004, nhấn lại cho FR-005) Phân công chỉ trong phạm vi phòng ban của mẫu | Cách ly phòng ban | 422 `ASSIGNEE_OUT_OF_DEPT` |
| BR-SAMPLE-007 | Chỉ **người giữ hiện tại** của mẫu (hoặc trưởng nhóm/Admin có quyền điều phối) được chuyển giao; người nhận phải cùng phòng ban | Chain of custody chính xác (17025 §7.4) — không ai "chuyển hộ" mẫu mình không giữ | 403 `NOT_CURRENT_CUSTODIAN` / 422 `HANDOVER_OUT_OF_DEPT` |
| BR-SAMPLE-008 | Chỉ **người được giao** (`assigned_to`) phần việc đó (hoặc Admin) được nhập/sửa kết quả phần đó | Trách nhiệm cá nhân với kết quả (R6, 17025 §6.2) | 403 `NOT_ASSIGNEE` |
| BR-SAMPLE-009 | Mẫu `overdue` bắt buộc nhập lý do trễ (`overdue_reasons`: reason+by+at) trước khi trưởng nhóm chốt `done` (FR-019) / xuất phiếu `returned` | Truy vết nguyên nhân trễ khi audit (R9, 17025 §8.4) | 422 `OVERDUE_REASON_REQUIRED` |
| BR-SAMPLE-010 | Kết quả đã `approved` **bất biến**: không sửa/xóa trực tiếp; sửa = tạo phiên bản mới (version+1) giữ bản cũ + lý do bắt buộc | Hồ sơ kỹ thuật/kết quả không được tẩy xóa (17025 §7.5, §8.4 — duy trì VILAS) | 422 `RESULT_LOCKED` / 400 `REVISION_REASON_REQUIRED` |
| BR-SAMPLE-011 | Người **nhập** kết quả KHÔNG được **tự duyệt** kết quả của chính mình; quyền duyệt (`sample_result:approve`) chỉ cấp cho trưởng nhóm phòng đó/Ban lãnh đạo/Admin | Tách biệt nhập–duyệt đảm bảo tính khách quan (17025 §7.8) | 403 `SELF_APPROVAL_FORBIDDEN` |
| BR-SAMPLE-012 | File đính kèm (ảnh/chứng từ/raw data/Excel): chỉ loại cho phép (PDF, PNG, JPG, XLSX, CSV) + ≤ giới hạn (OPEN QUESTION #6); lưu MinIO, không lưu binary trong DB | An toàn lưu trữ, tránh file độc hại | 422 `INVALID_FILE_TYPE` / `FILE_TOO_LARGE` |
| BR-SAMPLE-013 | Mọi thao tác CRUD phiếu/mẫu/phân công/handover/kết quả/duyệt/chốt mẫu/trễ hạn/xuất phiếu/chuyển trạng thái ghi `audit_logs` (user, action, resource, resource_id, correlation_id, ip, at, detail) | 17025 §8.4 kiểm soát hồ sơ — duy trì công nhận VILAS | Thiếu audit → vi phạm VILAS |
| BR-SAMPLE-014 | Kế toán **KHÔNG truy cập** mẫu/kết quả ở **tầng API** (không chỉ ẩn FE); KTV đọc kết quả **đã approved** công khai nội bộ (mọi phòng), thao tác ghi chỉ trong phòng mình; Admin/Ban lãnh đạo toàn hệ thống | Cách ly nghiệp vụ lab khỏi tài chính (B03) | 403 `FORBIDDEN`; rò rỉ dữ liệu mẫu/kết quả |
| BR-SAMPLE-015 | `sample_code` và `request_code` duy nhất toàn hệ thống, human-readable, không lộ ID tuần tự nội bộ; `id` thật là UUID; barcode/QR encode `sample_code` không encode UUID/serial | Không lộ thông tin nội bộ qua định danh; truy vết bằng mã (CONSTRAINT-5, rule api.md) | Trùng mã → 500/retry; lộ tuần tự → rủi ro bảo mật |
| BR-SAMPLE-016 | KHÔNG hard-delete mẫu đang được `chemical_transactions.ref_sample_id` tham chiếu hoặc đã có kết quả approved; chỉ soft-delete/hủy có lý do + audit | Toàn vẹn tham chiếu với M2; hồ sơ kết quả phải giữ (§8.4) | Mất tham chiếu hóa chất; vi phạm §8.4 |
| BR-SAMPLE-017 | Bản ghi `sample_handovers` (chain of custody) bất biến: không sửa/xóa; nhầm thì ghi handover mới đính chính | Chuỗi hành trình mẫu không được tẩy xóa (17025 §7.4) | Vi phạm tính toàn vẹn chain of custody |
| BR-SAMPLE-018 | Cron (CRON-1 nhắc, CRON-2 trễ hạn): mỗi mẫu × mỗi mốc/ngày chỉ phát 1 notification; idempotent; chạy dưới Redis lock | Chống trùng khi cron retry / nhiều instance | Spam thông báo |
| BR-SAMPLE-019 | On-time rate chỉ tính trên mẫu đã `done`; mẫu hoàn thành với `completed_at > deadline_at` (kể cả từng overdue) tính là "trễ" | Đo lường đúng hiệu suất đúng hạn | Báo cáo hiệu suất sai |
| **BR-SAMPLE-020** | **(OQ#2) Mẫu chỉ chuyển `done` khi TRƯỞNG NHÓM (hoặc Admin/Ban lãnh đạo) thực hiện hành động CHỐT THỦ CÔNG (FR-019); điều kiện tiên quyết là MỌI assignment của mẫu đã `approved`. Hệ thống KHÔNG tự động chuyển `done` dù mọi part đã approved** | Trưởng nhóm chịu trách nhiệm cuối cùng về tính hoàn chỉnh của mẫu trước khi ra phiếu (17025 §7.8); tránh chốt sớm khi còn thiếu chỉ tiêu | 422 `RESULTS_NOT_APPROVED` (chốt khi chưa approved hết) / mẫu giữ `testing` (không auto) |
| **BR-SAMPLE-021** | **(OQ#3) Kết quả CHỈ công khai nội bộ toàn lab SAU KHI `approved`. Trước approved: chỉ người nhập (`entered_by`) + người duyệt (trưởng nhóm phòng đó) + Admin/Ban lãnh đạo xem được; màn công khai (FR-011) KHÔNG hiển thị kết quả chưa duyệt cho người ngoài nhóm này** | Tránh lan truyền kết quả chưa kiểm chứng trong lab; bảo vệ tính chính xác của dữ liệu công bố nội bộ | Lộ kết quả chưa duyệt → rủi ro dùng nhầm số liệu chưa xác nhận |
| **BR-SAMPLE-022** | **(OQ#11) Quyền `sample:assign`, `sample_result:approve`, `sample:finalize` chỉ cấp cho TRƯỞNG NHÓM CỐ ĐỊNH của phòng ban đó (M7: `departments.lead_user_id` / `is_dept_lead`), Admin, Ban lãnh đạo. KTV thường KHÔNG có các quyền này. M1 đọc thuộc tính trưởng nhóm từ M7 để enforce ở tầng API** | Phân công/duyệt/chốt là quyền điều phối cố định theo phòng (OQ#11), tránh KTV tự phân/tự duyệt/tự chốt | 403 `FORBIDDEN` |
| **BR-SAMPLE-023** | **(OQ#1) Phiếu yêu cầu (`test_requests`) là vùng chứa 1..n mẫu; một phiếu phải có ≥ 1 mẫu để hoàn tất tiếp nhận. Mỗi mẫu (`samples.request_id` FK NOT NULL) độc lập về trạng thái/deadline/phân công/chuỗi hành trình** | Tách thông tin chung của lô khỏi từng mẫu; hỗ trợ gửi lô nhiều mẫu (OQ#1) | Phiếu rỗng không hợp lệ; mẫu không gắn phiếu → mồ côi dữ liệu |

> Ghi chú đánh số: BR-SAMPLE-005 cố ý gộp vào BR-SAMPLE-004 (cùng quy tắc phạm vi phòng ban cho phân công) — giữ BR-SAMPLE-006 là tham chiếu lại cho FR-005 để traceability rõ. Schema-designer/QA dùng BR-SAMPLE-004 làm rule chính.

---

## 5. Use Case chính

### UC-SAMPLE-01: Tiếp nhận lô mẫu (intake — phiếu + nhiều mẫu) — cập nhật OQ#1
- **Actor chính:** KTV (quyền nhận mẫu, phòng mình) / Admin.
- **Tiền điều kiện:** khách hàng gửi một lô mẫu tới phòng.
- **Luồng:**
  1. KTV mở "Tiếp nhận mẫu" → tạo **phiếu yêu cầu** (FR-018): khách "Cty ABC", người gửi "Nguyễn Văn A", phòng = Hóa lý → `request_code`=`RQ-2026-0042`.
  2. KTV **thêm 3 mẫu** vào phiếu (FR-001): mỗi mẫu sinh `sample_code` riêng (`SP-2026-0007/0008/0009`) + QR, deadline riêng, trạng thái `received`, người giữ ban đầu = KTV.
  3. KTV đính kèm ảnh mẫu + biên bản giao nhận (chung ở phiếu hoặc riêng từng mẫu); ghi tình trạng từng mẫu.
  4. Audit `REQUEST_CREATE` + nhiều `SAMPLE_CREATE` + `SAMPLE_ATTACH_UPLOAD` + `SAMPLE_CONDITION_RECORD`.
- **Hậu điều kiện:** 3 mẫu thuộc 1 phiếu, sẵn sàng phân công độc lập; chain of custody từng mẫu khởi tạo.
- **Liên kết FR:** FR-SAMPLE-018, 001, 002, 003, 004.

### UC-SAMPLE-02: Phân công & chuyển giao mẫu
- **Actor chính:** Trưởng nhóm (phân việc) + KTV (giữ mẫu).
- **Tiền điều kiện:** mẫu `received`; user phân công là trưởng nhóm phòng đó (OQ#11).
- **Luồng:**
  1. Trưởng nhóm phòng Hóa lý phân công phần "độ ẩm" cho KTV A, phần "kim loại nặng" cho KTV B (cùng phòng) → mẫu `assigned`.
  2. KTV A (đang giữ mẫu) chuyển giao mẫu vật lý cho KTV B để đo phổ → ghi `sample_handovers` (A→B, lý do), người giữ hiện tại = B.
  3. Mọi người xem được chuỗi hành trình mẫu (A giữ → B giữ).
- **Ngoại lệ:** KTV thường (không trưởng nhóm) cố phân công → 403 `FORBIDDEN`; chuyển cho người ngoài phòng → 422 `HANDOVER_OUT_OF_DEPT`; người không giữ mẫu chuyển → 403 `NOT_CURRENT_CUSTODIAN`.
- **Hậu điều kiện:** phần việc được giao; chain of custody cập nhật.
- **Liên kết FR:** FR-SAMPLE-005, 006, 007.

### UC-SAMPLE-03: Nhập, duyệt & chốt hoàn thành mẫu — cập nhật OQ#2, OQ#3
- **Actor chính:** KTV được giao (nhập) + Trưởng nhóm (duyệt + chốt).
- **Tiền điều kiện:** mẫu `assigned`/`testing`; KTV được giao phần việc.
- **Luồng:**
  1. KTV A nhập kết quả "độ ẩm" + đính kèm raw data → mẫu `testing`, assignment `result_entered`. **Kết quả CHƯA công khai toàn lab** (chỉ A + trưởng nhóm + Admin/Lãnh đạo thấy — OQ#3).
  2. KTV B nhập kết quả "kim loại nặng" + raw data (cũng chưa công khai).
  3. Trưởng nhóm T (≠ người nhập) duyệt cả 2 kết quả → mỗi assignment `approved`; **kết quả approved mới công khai nội bộ toàn lab** (OQ#3).
  4. Mọi part approved → mẫu **ĐỦ ĐIỀU KIỆN** done nhưng **vẫn `testing`** (không auto — OQ#2).
  5. Trưởng nhóm bấm **"Chốt hoàn thành mẫu"** (FR-019) → mẫu chuyển `done`, `completed_at` set.
  6. Phát hiện sai số → tạo phiên bản sửa (version 2) kèm lý do; bản version 1 vẫn giữ.
- **Ngoại lệ:** A tự duyệt kết quả của A → 403 `SELF_APPROVAL_FORBIDDEN`; sửa trực tiếp kết quả approved → 422 `RESULT_LOCKED`; trưởng nhóm chốt khi còn part chưa approved → 422 `RESULTS_NOT_APPROVED`; KTV thường cố chốt → 403 `FORBIDDEN`; KTV phòng khác xem kết quả chưa approved → không thấy (OQ#3).
- **Hậu điều kiện:** kết quả approved bất biến + công khai; mẫu `done` (do trưởng nhóm chốt).
- **Liên kết FR:** FR-SAMPLE-008, 009, 010, 011, 019.

### UC-SAMPLE-04: Xử lý trễ hạn
- **Actor chính:** hệ thống (CRON-2) → KTV/Trưởng nhóm.
- **Tiền điều kiện:** mẫu chưa done, quá `deadline_at`.
- **Luồng:**
  1. CRON-2 00:30 đánh dấu mẫu quá hạn → `overdue` + notification.
  2. KTV mở mẫu `overdue` → bắt buộc nhập lý do trễ "máy đo hỏng chờ sửa" → `overdue_reasons` ghi nhận.
  3. Mẫu được hoàn thành (mọi part approved) → **trưởng nhóm chốt** chuyển `done` (đánh dấu hoàn thành trễ).
  4. CRON-1 (07:00) trước đó đã nhắc khi còn ≤ 3 và ≤ 1 ngày.
- **Ngoại lệ:** cố chốt mẫu overdue chưa nhập lý do → 422 `OVERDUE_REASON_REQUIRED`.
- **Hậu điều kiện:** lý do trễ truy vết; on-time rate phản ánh đúng.
- **Liên kết FR:** FR-SAMPLE-012, 013, 014, 015, 019.

### UC-SAMPLE-05: Trả kết quả (xuất phiếu PDF)
- **Actor chính:** Trưởng nhóm / Ban lãnh đạo / Admin.
- **Tiền điều kiện:** mẫu `done` (trưởng nhóm đã chốt — FR-019; mọi chỉ tiêu approved; nếu từng overdue đã nhập lý do).
- **Luồng:**
  1. Mở mẫu `done` → "Xuất phiếu kết quả".
  2. Hệ thống sinh PDF có `sample_code` + `request_code` + QR + chỉ tiêu/kết quả approved + người duyệt.
  3. Mẫu chuyển `returned`; PDF lưu vào attachments; audit `SAMPLE_REPORT_EXPORT`.
  4. Phiếu gửi khách ngoài hệ thống (không có portal — A02).
- **Ngoại lệ:** mẫu chưa được chốt `done` → 422 `SAMPLE_NOT_FINALIZED`.
- **Liên kết FR:** FR-SAMPLE-016, 019.

---

## 6. Yêu cầu phi chức năng (NFR)

Theo template `~/.claude/rules/nfr.md`. Con số định cỡ cho quy mô **~40 user** (C03), môi trường staging tương đương production (Docker Compose, ~2–4 vCPU/8GB). Giả định cao điểm: ~10 concurrent users. Lượng mẫu giả định: tới ~50,000 mẫu lịch sử + ~200,000 kết quả/attachments.

```
NFR-PERF-SAMPLE-001: Tạo phiếu/mẫu & nhập kết quả
────────────────────────────────────────────────────
Mô tả:     API tạo phiếu/thêm mẫu (POST request/sample) và nhập/duyệt/chốt
           kết quả phải phản hồi đủ nhanh để KTV thao tác liền mạch tại bàn TN.
Metric:    P95 < 400ms | P99 < 700ms
Tool đo:   k6 (tests/performance/sample-create-result.js)
Điều kiện: 10 concurrent users, dataset 50,000 mẫu / 200,000 kết quả, staging
Pass:      p(95) < 400ms suốt 10 phút ở 10 concurrent users, error rate < 1%
Fail:      p(95) ≥ 400ms → review index (sample_code, request_id, department_id, status)
Ưu tiên:  Must Have
```
```
NFR-PERF-SAMPLE-002: Tìm kiếm / liệt kê mẫu & lịch sử
────────────────────────────────────────────────────
Metric:    P95 < 500ms cho danh sách phân trang 20/trang (lọc đa tiêu chí)
Tool đo:   k6 (tests/performance/sample-search.js)
Điều kiện: 10 concurrent users, 50,000 mẫu
Pass:      p(95) < 500ms; query dùng index (không Sequential Scan bảng lớn)
Fail:      p(95) ≥ 500ms → thêm index (department_id, status, deadline_at, received_at, request_id)
Ưu tiên:  Should Have
```
```
NFR-PERF-SAMPLE-003: Xuất phiếu kết quả PDF
────────────────────────────────────────────────────
Metric:    Sinh phiếu PDF 1 mẫu (≤ 30 chỉ tiêu) trong < 3s (P95).
Tool đo:   k6 + đo thời gian sinh PDF
Điều kiện: 3 concurrent users xuất đồng thời
Pass:      P95 < 3s; không OOM khi 3 user xuất song song
Fail:      timeout/OOM → chuyển sinh PDF sang job nền + notify in-app
Ưu tiên:  Should Have
```
```
NFR-CONCUR-SAMPLE-001: An toàn tương tranh khi chuyển trạng thái / duyệt / chốt (Must)
────────────────────────────────────────────────────
Mô tả:     Chuyển trạng thái mẫu, duyệt kết quả và chốt hoàn thành mẫu phải
           an toàn tương tranh, không tạo trạng thái không nhất quán (vd done
           2 lần, approve trùng, chốt khi part chưa approved do race).
Metric:    Với K request chuyển trạng thái / duyệt / chốt đồng thời trên cùng
           mẫu, chỉ 1 thành công cho mỗi phép chuyển; không có trạng thái sai
           whitelist; chốt done chỉ thành công khi mọi part approved tại thời điểm.
Tool đo:   k6 ramping-vus + kiểm tra DB + audit
Điều kiện: 20 request song song trên 1 mẫu (duyệt + chốt + chuyển trạng thái)
Pass:      Trạng thái cuối hợp lệ theo state machine; 0 chuyển sai whitelist;
           0 mẫu done khi còn part chưa approved
Fail:      Trạng thái không nhất quán → fix row-lock/transaction trên sample
Ưu tiên:  Must Have
```
```
NFR-AUDIT-SAMPLE-001: Đầy đủ & bất biến audit + chain of custody (VILAS §7.4/§7.5/§8.4) (Must)
────────────────────────────────────────────────────
Mô tả:     Mọi thao tác CRUD phiếu/mẫu/phân công/handover/kết quả/duyệt/chốt
           mẫu/trễ hạn/xuất phiếu/chuyển trạng thái ghi audit_logs; handover &
           kết quả approved bất biến.
Metric:    100% thao tác ghi có bản ghi audit_logs với correlation_id;
           0 endpoint cho phép sửa/xóa sample_handovers; 0 endpoint sửa/xóa
           kết quả approved (sửa chỉ qua version mới); chain of custody dựng
           lại được đầy đủ cho 100% mẫu.
Tool đo:   Test tự động đếm audit/thao tác + rà route (không DELETE/PUT trên
           sample_handovers, không PATCH result đã approved)
Pass:      Tỷ lệ audit/thao tác = 100%; handover & kết quả approved immutable
Fail:      < 100% hoặc tồn tại route sửa handover/kết quả approved → block (VILAS)
Ưu tiên:  Must Have
```
```
NFR-SEC-SAMPLE-001: Phân quyền & cách ly dữ liệu (Must)
────────────────────────────────────────────────────
Mô tả:     Enforce RBAC + phạm vi phòng ban + cách ly Kế toán khỏi mẫu/kết quả
           ở tầng API (không chỉ FE); tách biệt nhập–duyệt kết quả; quyền
           assign/approve/finalize chỉ cho trưởng nhóm phòng đó/Admin/Lãnh đạo
           (OQ#11); kết quả chưa approved không lộ ra ngoài nhóm xem trước (OQ#3).
Metric:    Ma trận test 4 vai trò × các action M1 (gồm trưởng nhóm vs KTV thường)
           pass 100%; Kế toán nhận 403 ở 100% endpoint M1; KTV thường nhận 403
           khi assign/approve/finalize; người nhập không tự duyệt được; kết quả
           chưa approved 0 lần lộ cho người ngoài nhóm xem trước.
Tool đo:   Test RBAC tự động (security-auditor) + manual
Pass:      0 truy cập trái phép; 0 self-approval; 0 ghi chéo phòng/người;
           0 KTV thường assign/approve/finalize; 0 lộ kết quả chưa approved
Fail:      Bất kỳ bypass nào → block go-live (OWASP A01)
Ưu tiên:  Must Have
```
```
NFR-SEC-SAMPLE-002: Mã mẫu/phiếu không lộ định danh tuần tự (Must)
────────────────────────────────────────────────────
Mô tả:     ID nội bộ là UUID; định danh dùng ngoài là sample_code/request_code/
           UUID, không expose serial id liên tiếp; QR encode sample_code.
Metric:    0 endpoint trả id tuần tự liên tiếp; 2 mẫu liên tiếp không suy ra
           được thứ tự nội bộ từ định danh dùng ngoài.
Tool đo:   Rà response API + kiểm tra định dạng định danh
Pass:      Không lộ serial id; sample_code/request_code duy nhất
Ưu tiên:  Must Have
```
```
NFR-SEC-SAMPLE-003: An toàn upload file mẫu/kết quả (Must)
────────────────────────────────────────────────────
Metric:    Chỉ chấp nhận PDF/PNG/JPG/XLSX/CSV (validate MIME thực + đuôi),
           ≤ giới hạn dung lượng (OPEN QUESTION #6); không thực thi file;
           lưu MinIO, không lưu binary trong DB.
Tool đo:   Test upload file độc hại / sai loại / quá lớn
Pass:      File sai loại/quá lớn bị từ chối 422; file hợp lệ tải lại được
Ưu tiên:  Must Have
```
```
NFR-CRON-SAMPLE-001: Độ tin cậy & idempotent cron deadline/trễ hạn (Must)
────────────────────────────────────────────────────
Mô tả:     CRON-1 (07:00 nhắc) và CRON-2 (00:30 trễ hạn) chạy đúng giờ,
           không trùng (Redis lock), idempotent.
Metric:    Mỗi mẫu × mỗi mốc/ngày tạo ≤ 1 notification; CRON-2 không đánh dấu
           overdue sai (chỉ mẫu chưa done quá deadline); chạy lại cùng ngày
           không tạo hệ quả trùng.
Tool đo:   Test chạy cron 2 lần/ngày + kiểm tra notification & state
Pass:      0 notification trùng; 0 đánh dấu overdue sai; lock hoạt động
Fail:      Trùng/sai trạng thái → fix lock/idempotency key
Ưu tiên:  Must Have
```
```
NFR-MAINT-SAMPLE-001: Test coverage domain mẫu (Must)
────────────────────────────────────────────────────
Metric:    Service state machine / chốt mẫu (finalize) / chain of custody /
           RBAC scope (gồm trưởng nhóm) / versioning kết quả / phạm vi đọc
           (OQ#3) coverage ≥ 85%; module M1 overall ≥ 70%.
Tool đo:   pytest --cov
Pass:      ≥ 85% domain, ≥ 70% module; CI block nếu drop > 5%
Ưu tiên:  Must Have
```
```
NFR-OBS-SAMPLE-001: Logging & truy vết (Should)
────────────────────────────────────────────────────
Metric:    Mọi request M1 có correlation_id xuyên FE→BE→audit_logs;
           chuyển trạng thái/duyệt/chốt ghi log INFO; chuyển sai whitelist /
           chốt khi chưa approved / xuất khi chưa done ghi WARN; lỗi transaction
           ghi ERROR kèm stack (không lộ ra client).
Tool đo:   Rà log + test
Pass:      Trace được 1 mẫu từ log FE → audit DB qua correlation_id
Ưu tiên:  Should Have
```

---

## 7. Giả định & Ràng buộc (tổng hợp)

**Assumptions:**
- ASSUMPTION-1 (**OQ#1 — ĐÃ CHỐT 19/06/2026**): 1 phiếu yêu cầu (`test_requests`) chứa 1..n mẫu (`samples`) — quan hệ 1-n; mỗi mẫu độc lập trạng thái/deadline/phân công.
- ASSUMPTION-2 (**OQ#2 — ĐÃ CHỐT 19/06/2026**): mẫu chuyển `done` do trưởng nhóm chốt thủ công (không auto), tiền đề mọi part approved.
- ASSUMPTION-3 (**OQ#3 — ĐÃ CHỐT 19/06/2026**): kết quả chỉ công khai toàn lab sau approved; trước approved chỉ người nhập + người duyệt + Admin/Lãnh đạo xem.
- ASSUMPTION-4: Người giữ mẫu ban đầu = `received_by` (của phiếu); chain of custody bắt đầu từ bản ghi tiếp nhận.
- ASSUMPTION-5 → **OPEN QUESTION #4 (còn treo):** mốc nhắc CRON-1 mặc định còn ≤ 3 ngày và ≤ 1 ngày (vì TAT mẫu thường ngắn) — cấu hình được; chốt khi UAT.
- ASSUMPTION-6 (**OQ#11 — ĐÃ CHỐT 19/06/2026**): "trưởng nhóm" là thuộc tính cố định theo phòng ban ở M7 (`departments.lead_user_id` / `is_dept_lead`); cấp quyền `sample:assign` + `sample_result:approve` + `sample:finalize` trong phòng ban mình.

**Constraints:** xem §2.4 (CONSTRAINT-1..9).

**Ghi chú cấu trúc dữ liệu cho `schema-designer`:**
- **`test_requests` (MỚI — OQ#1):** `id UUID PK`, `request_code VARCHAR UNIQUE NOT NULL`, `customer_id FK`, `sender_name VARCHAR`, `department_id FK NOT NULL`, `received_by FK→users`, `received_at TIMESTAMPTZ`, `note TEXT`, `created_at`. Một phiếu có 1..n `samples` (BR-SAMPLE-023).
- `samples`: `id UUID PK`, `sample_code VARCHAR UNIQUE NOT NULL`, **`request_id FK→test_requests NOT NULL` (OQ#1 — quan hệ 1-n)**, `department_id FK NOT NULL`, `received_by FK→users`, `received_at TIMESTAMPTZ`, `deadline_at TIMESTAMPTZ NOT NULL`, `completed_at TIMESTAMPTZ NULL` (set khi trưởng nhóm chốt done — để tính on-time), `status` ENUM[received, assigned, testing, done, overdue, returned], `condition_status` ENUM[acceptable, not_acceptable, null], `condition_note TEXT`, `current_custodian_id FK→users` (denormalized, suy từ handover gần nhất — tùy chọn), `created_at`. CHECK: `deadline_at > received_at`. (customer/sender đọc qua `request_id`; `department_id`/`received_by` có thể denormalize từ phiếu để query nhanh + cách ly.)
- `sample_assignments`: `id`, `sample_id FK`, `assigned_to FK→users`, `assigned_by FK→users`, `part_name`, `status` ENUM[assigned, in_progress, result_entered, approved], `assigned_at`. (assigned_to phải cùng department với sample — enforce app-level; assigned_by phải có quyền `sample:assign` — BR-SAMPLE-022.)
- `sample_results`: `id`, `assignment_id FK`, `version INT NOT NULL DEFAULT 1`, `result_data JSONB`, `entered_by FK→users`, `entered_at`, `approved_by FK→users NULL`, `approved_at NULL`, `is_current BOOLEAN`. UNIQUE(assignment_id, version). Không PATCH khi approved; sửa = insert version mới. approved_by ≠ entered_by (enforce app-level — BR-SAMPLE-011). **Phạm vi đọc (OQ#3 — BR-SAMPLE-021):** kết quả `approved_by IS NULL` chỉ trả cho entered_by + trưởng nhóm phòng/Admin/Lãnh đạo; `approved_by IS NOT NULL` công khai nội bộ.
- `sample_handovers`: `id`, `sample_id FK`, `from_user FK→users`, `to_user FK→users`, `reason TEXT`, `at TIMESTAMPTZ`. **Immutable** — không có route PUT/DELETE (BR-SAMPLE-017).
- `overdue_reasons`: `id`, `sample_id FK`, `reason TEXT NOT NULL`, `by FK→users`, `at TIMESTAMPTZ`. Mẫu overdue phải có ≥ 1 trước khi trưởng nhóm chốt (BR-SAMPLE-009).
- **Trưởng nhóm (OQ#11 — phụ thuộc M7):** `departments.lead_user_id FK→users NULL` (1 trưởng nhóm/phòng) HOẶC cờ `users.is_dept_lead BOOLEAN` (gắn hồ sơ nhân sự). M1 đọc thuộc tính này để cấp `sample:assign`/`sample_result:approve`/`sample:finalize` trong phòng — schema-designer phối hợp owner M7 chọn 1 phương án (gợi ý `departments.lead_user_id` để đảm bảo đúng 1 trưởng nhóm/phòng).
- `attachments` (dùng chung): owner_type ∈ {`test_request`, `sample`, `sample_result`} cho M1.
- Index gợi ý: `samples(request_id)`, `samples(department_id, status)`, `samples(deadline_at) WHERE status NOT IN (done, returned)` (phục vụ CRON), `samples(sample_code)` unique, `test_requests(request_code)` unique, `sample_assignments(assigned_to, status)`, `sample_assignments(sample_id, status)` (kiểm tra "mọi part approved" khi chốt — FR-019), `chemical_transactions(ref_sample_id)` (M2 — đã có).
- State transition: hàm trung tâm + whitelist (FR-SAMPLE-017); transaction + row-lock trên sample khi chuyển trạng thái/duyệt/chốt (NFR-CONCUR-SAMPLE-001). Hàm chốt done (FR-019) phải kiểm tra mọi assignment `approved` TRONG transaction có row-lock để tránh race.
- Không hard-delete sample/result/handover; soft-delete sample chỉ khi không bị M2 tham chiếu & chưa có kết quả approved (BR-SAMPLE-016).

---

## 8. OPEN QUESTIONS

### 8.1 ĐÃ CHỐT (19/06/2026) — văn bản xác nhận KH

| # | Câu hỏi | Quyết định chốt | Ảnh hưởng đã cập nhật trong SRS v1.1 |
|---|---------|-----------------|--------------------------------------|
| 1 | 1 phiếu = 1 mẫu hay nhiều mẫu (lô)? | **1 phiếu (`test_requests`) chứa NHIỀU mẫu (`samples`) — quan hệ 1-n.** Phiếu giữ thông tin chung; mỗi mẫu có mã/trạng thái/deadline/phân công riêng | Thêm FR-018; sửa FR-001/002/003/016; BR-023; §1.3, §2, §6, §7 (ERD `test_requests` + `samples.request_id`); UC-01 |
| 2 | Mẫu `done` tự động hay trưởng nhóm chốt? | **Trưởng nhóm CHỐT THỦ CÔNG.** Dù mọi chỉ tiêu approved, mẫu chỉ `done` khi trưởng nhóm thực hiện hành động chốt. KHÔNG auto-done | Thêm FR-019; sửa FR-010 (AC6), FR-016, FR-017 (state machine + diagram), FR-014; BR-020; UC-03/04/05 |
| 3 | Công khai kết quả ngay khi nhập hay chỉ sau approved? | **CHỈ công khai nội bộ toàn lab SAU KHI approved.** Trước approved: chỉ người nhập + người duyệt (trưởng nhóm) + Admin/Lãnh đạo xem | Sửa FR-008 (AC6), FR-011 (đổi tiêu đề + AC2-4), FR-009; BR-021; BR-014; §1.2, §2.3 |
| 11 | "Trưởng nhóm" xác định thế nào? | **CỐ ĐỊNH THEO PHÒNG BAN** (M7: `departments.lead_user_id` / `is_dept_lead`). Người này mặc định có `sample:assign` + `sample_result:approve` (+ `sample:finalize`) trong phòng mình | Sửa §2.3 RBAC, FR-005/010/019; BR-022; BR-011; CONSTRAINT-9; §7 (ghi chú M7) |

> Tất cả 4 quyết định trên đã có **văn bản xác nhận KH** (rule "Verbal is Nothing"). Đủ điều kiện đưa vào `/contract`.

### 8.2 Còn treo (KHÔNG chặn `/contract` — phần lớn là tham số vận hành / biến thể luồng)

| # | Câu hỏi | Tại sao cần biết | Ảnh hưởng nếu chưa rõ | Người trả lời | Deadline | Chặn contract? |
|---|---------|------------------|----------------------|---------------|----------|----------------|
| 4 | Mốc nhắc CRON-1 trước hạn (mặc định ≤3 và ≤1 ngày) có phù hợp TAT thực tế? | Cấu hình CRON-1 (FR-013) | Dùng default; tinh chỉnh được runtime | KH (vận hành) | Khi UAT | **Không** — default an toàn, cấu hình được |
| 5 | Định dạng `sample_code`/`request_code` mong muốn? | Sinh mã (FR-002/018) | Dùng `SP-YYYY-NNNN` / `RQ-YYYY-NNNN` default | KH (Trưởng lab) | Khi UAT | **Không** — đổi format cấu hình, không đổi schema |
| 6 | Giới hạn dung lượng & loại file đính kèm? | Cấu hình MinIO + validate (BR-012) | Dùng default (PDF/PNG/JPG/XLSX/CSV, ≤ 50MB raw data) | KH (IT/vận hành) | Khi UAT | **Không** — tham số cấu hình |
| 7 | Một part có giao cho NHIỀU người (đối chứng) không? | Ràng buộc unique assignment theo part | Default: cho phép nhiều (không unique cứng) | KH (Trưởng lab) | Khi UAT | **Không** — default linh hoạt, không đổi schema lõi |
| 8 | Sau approved có cho ĐÍNH KÈM THÊM raw data (không sửa số liệu)? | Logic FR-009 với kết quả approved | Default: chặn; bổ sung file = tạo version mới | KH (Trưởng lab) | Khi UAT | **Không** — đã có quy tắc version mặc định |
| 9 | Mẫu `overdue` được gia hạn → quay lại `testing` hay giữ `overdue`? | Phép chuyển `overdue→testing` | Default: cho quay lại testing nếu deadline mới > now | KH (Trưởng lab) | Khi UAT | **Không** — biến thể state machine, có default |
| 10 | Admin được override trạng thái thủ công (có audit) không? | Có/không endpoint override | Default: có endpoint admin override + audit bắt buộc | KH (Lãnh đạo) | Khi UAT | **Không** — feature phụ trợ vận hành |

> **Kết luận:** sau khi chốt #1/#2/#3/#11 (ảnh hưởng ERD/RBAC lõi), **các câu còn lại #4–#10 KHÔNG chặn `/contract`** — đều là tham số cấu hình hoặc biến thể luồng có default hợp lý, có thể chốt khi UAT mà không thay đổi schema/RBAC lõi. Khi chốt #4–#10 vẫn cần văn bản xác nhận KH trước khi đổi default.

---

## 9. Ma trận truy vết (Traceability Matrix)

| FR ID | Yêu cầu gốc (meeting note) | Submodule (demo-scope) | Điều khoản 17025 | Business Rule | Test Case (QA sẽ tạo) | Trạng thái |
|-------|----------------------------|------------------------|------------------|---------------|------------------------|------------|
| FR-SAMPLE-018 | R5 (phiếu lô nhiều mẫu), **OQ#1 chốt** | F1.1.1 | §7.4 | BR-013, 014, 015, 023 | TC-SAMPLE-081..085 | Draft |
| FR-SAMPLE-001 | R5, R6 (KH gửi mẫu qua phòng), B02, **OQ#1** | F1.1.1 | §7.4 | BR-002, 003, 013, 015, 023 | TC-SAMPLE-001..005 | Draft |
| FR-SAMPLE-002 | (không lộ ID — rule api) | F1.1.2 | §8.4 | BR-015 | TC-SAMPLE-006..009 | Draft |
| FR-SAMPLE-003 | R2 (kèm file) | F1.1.3 | §7.4, §8.4 | BR-012, 013 | TC-SAMPLE-010..013 | Draft |
| FR-SAMPLE-004 | (điều kiện tiếp nhận) | F1.1.4 | §7.4 | BR-003, 013 | TC-SAMPLE-014..016 | Draft |
| FR-SAMPLE-005 | R5, R6 (phân công từng người), **OQ#11** | F1.2.1 | §6.2, §7.4 | BR-001, 004/006, 013, 022 | TC-SAMPLE-017..021 | Draft |
| FR-SAMPLE-006 | R5 (tạo phiếu & chuyển cho người khác) | F1.2.2 | §7.4 | BR-007, 013, 017 | TC-SAMPLE-022..026 | Draft |
| FR-SAMPLE-007 | R5 (chain of custody) | F1.2.3 | §7.4 | BR-014, 017 | TC-SAMPLE-027..029 | Draft |
| FR-SAMPLE-008 | R6 (mỗi người điền kết quả), **OQ#3** | F1.3.1 | §6.2, §7.5 | BR-001, 008, 010, 013, 021 | TC-SAMPLE-030..035 | Draft |
| FR-SAMPLE-009 | R2 (raw data đính kèm) | F1.3.3 | §7.5, §8.4 | BR-010, 012, 021 | TC-SAMPLE-036..039 | Draft |
| FR-SAMPLE-010 | R6 (duyệt trước khi chốt), **OQ#3, OQ#11** | F1.3.4 | §7.8, §8.4 | BR-001, 010, 011, 013, 021, 022 | TC-SAMPLE-040..047 | Draft |
| FR-SAMPLE-019 | R6 (chốt hoàn thành), **OQ#2, OQ#11 chốt** | F1.5 (chốt mẫu) | §7.8, §8.4 | BR-001, 009, 013, 020, 022 | TC-SAMPLE-086..092 | Draft |
| FR-SAMPLE-011 | R6 (công khai nội bộ), A02, **OQ#3** | F1.3.2 | §7.8 | BR-014, 021 | TC-SAMPLE-048..050 | Draft |
| FR-SAMPLE-012 | AS6 (deadline) | F1.4.1 | §7.4 | BR-002, 013 | TC-SAMPLE-051..053 | Draft |
| FR-SAMPLE-013 | R7 (CRON-1 nhắc tới hạn) | F1.4.2 | §7.4 | BR-018 | TC-SAMPLE-054..057 | Draft |
| FR-SAMPLE-014 | R9 (lý do trễ hạn, CRON-2) | F1.4.3 | §7.4, §8.4 | BR-001, 009, 018 | TC-SAMPLE-058..064 | Draft |
| FR-SAMPLE-015 | R8, R10 (on-time rate) | F1.4.4 | §8.4 | BR-014, 019 | TC-SAMPLE-065..067 | Draft |
| FR-SAMPLE-016 | R6 (trả kết quả), A02 (không portal), **OQ#2** | F1.5.1 | §7.8, §8.4 | BR-001, 009, 010, 013, 014, 020 | TC-SAMPLE-068..073 | Draft |
| FR-SAMPLE-017 | (state machine — nền tảng), **OQ#2** | M1 (xuyên suốt) | §7.4, §8.4 | BR-001, 013, 020 | TC-SAMPLE-074..080 | Draft |

**Mapping cron:** FR-SAMPLE-013 ↔ CRON-1 (nhắc tới hạn, 07:00); FR-SAMPLE-014 ↔ CRON-2 (đánh dấu trễ hạn, 00:30) — `01-demo-scope.md` mục D.
**Mapping điều khoản 17025 (demo-scope mục E):** §7.2 (phương pháp — qua SOP/tài liệu M3), §7.4 (xử lý mẫu, chain of custody), §7.5 (hồ sơ kỹ thuật — raw data), §7.8 (báo cáo kết quả, phê duyệt + chốt hoàn thành), §8.4 (kiểm soát hồ sơ — audit, immutable, versioning).
**Liên kết liên module:** `samples.id` ← `chemical_transactions.ref_sample_id` (M2, BR-CHEM-025) — không hard-delete mẫu được tham chiếu (BR-SAMPLE-016). **Phụ thuộc M7:** trưởng nhóm cố định theo phòng (`departments.lead_user_id` / `is_dept_lead`) — CONSTRAINT-9, BR-SAMPLE-022.

---

*Hết SRS M1 (v1.1). 4 OPEN QUESTIONS lõi (#1 lô nhiều mẫu, #2 chốt mẫu thủ công, #3 công khai sau duyệt, #11 trưởng nhóm cố định theo phòng) ĐÃ CHỐT 19/06/2026 và đã đồng bộ toàn bộ FR/BR/UC/NFR/state machine/Traceability. Còn #4–#10 treo nhưng KHÔNG chặn `/contract` (tham số vận hành/biến thể luồng có default, chốt khi UAT). Mọi xác nhận tiếp theo phải bằng văn bản theo rule "Verbal is Nothing".*
