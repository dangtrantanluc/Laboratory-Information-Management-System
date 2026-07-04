# SRS: M5 — Quản lý Thiết bị & Hiệu chuẩn (Equipment & Calibration)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M5 — Quản lý Thiết bị & Hiệu chuẩn (Equipment & Calibration)
**Version:** 1.0 | **Ngày:** 20/06/2026 | **Author:** BA agent
**Status:** DRAFT — bối cảnh đã chốt (4 vai trò, RBAC + phạm vi phòng ban, MinIO C01, in-app only C02, ~40 user C03, lab ĐÃ công nhận VILAS → record control CHẶT §8.4). Còn 5 OPEN QUESTIONS (§8) — phần lớn là tham số cấu hình/biến thể luồng có default, không chặn ERD/luồng lõi.
**Nguồn:** `00-meeting-note-analysis.md` (R16 "17025 vlab — nhắc trước thời gian hiệu chuẩn"; quyết định chốt C01/C02/C03), `01-demo-scope.md` (M5.1–M5.2, RBAC matrix dòng "Thiết bị — hiệu chuẩn", ERD core M5 `equipments`/`calibrations`, CRON-5, mapping 17025 §6.4/§6.5 mục E), `08-contract-m7-schema.md` (users/departments/attachments/audit_logs/notifications dùng chung; `attachments.owner_type` đã whitelist `'equipment'`/`'calibration'`; `notifications` cho CRON-5)
**Chuẩn:** IEEE 830 (rút gọn) · ISO/IEC 17025:2017 §6.4 (thiết bị), §6.5 (liên kết chuẩn đo lường), §8.4 (kiểm soát hồ sơ)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| 1.0 | 20/06/2026 | Bản DRAFT đầu tiên — 11 FR, 14 BR, 4 UC, 9 NFR, 5 OPEN QUESTIONS. Đồng bộ phong cách SRS M3: bản ghi hiệu chuẩn immutable (§8.4 — pattern version approved bất biến M3); RBAC + phạm vi phòng ban + Kế toán chỉ xem (👁); cảnh báo (badge) không khóa cứng theo tinh thần "lô fail M2"; CRON-5 dùng `notifications` chung (M7); attachments polymorphic cho CoC/cert lên MinIO. |

---

## 1. Giới thiệu

### 1.1 Mục đích

Tài liệu này đặc tả đầy đủ, không mơ hồ, kiểm thử được cho **Module M5 — Quản lý Thiết bị & Hiệu chuẩn** của hệ thống LIMS. Mục tiêu nghiệp vụ:

1. **Số hóa danh mục thiết bị (17025 §6.4):** mỗi thiết bị đo lường/thử nghiệm của lab có hồ sơ điện tử (tên, mã, vị trí, phòng ban, người phụ trách, ngày mua, tình trạng), đính kèm tài liệu (hướng dẫn sử dụng, ảnh) lưu MinIO — thay sổ tay thiết bị giấy bằng kho tập trung, tìm kiếm được (R2, R11).
2. **Quản lý hiệu chuẩn & liên kết chuẩn đo lường (§6.4/§6.5 — VILAS bắt buộc):** mỗi thiết bị có **lịch hiệu chuẩn định kỳ** (chu kỳ tháng/năm); ghi nhận **từng lần hiệu chuẩn** (ngày hiệu chuẩn, đơn vị hiệu chuẩn/provider, kết quả đạt/không đạt, ngày hiệu chuẩn kế tiếp `next_due_date`, đính kèm **giấy chứng nhận hiệu chuẩn CoC/cert** lên MinIO). **Bản ghi hiệu chuẩn bất biến** (immutable — §8.4) để truy vết khi đánh giá VILAS.
3. **Nhắc trước & cảnh báo quá hạn hiệu chuẩn (R16):** **CRON-5** nhắc trước khi `next_due_date` còn 30/15/7 ngày (in-app cho người phụ trách thiết bị + trưởng nhóm); **cảnh báo (badge)** thiết bị **quá hạn hiệu chuẩn** hoặc kết quả hiệu chuẩn gần nhất **"không đạt"** → khuyến nghị **không dùng cho thử nghiệm** (tinh thần §6.4 — thiết bị phải được hiệu chuẩn; cảnh báo rõ, KHÔNG khóa cứng — OQ#3).

Tài liệu dùng cho 2 đối tượng:
- **Khách hàng / Ban lãnh đạo lab:** xác nhận nghiệp vụ đúng — đặc biệt **cách tính `next_due_date`**, **bản ghi hiệu chuẩn bất biến**, **chính sách cảnh báo quá hạn (không khóa cứng)**, **các mốc nhắc CRON-5**.
- **Đội thiết kế (`schema-designer`, `api-designer`, `ux-designer`) và `feature-builder`:** đủ chi tiết để viết contract và implement mà không phải hỏi lại.

### 1.2 Phạm vi

Module M5 phủ 2 submodule (theo `01-demo-scope.md`):

| Submodule | Nội dung | Trong SRS này |
|-----------|----------|---------------|
| M5.1 Danh mục thiết bị | CRUD thiết bị (tên, mã, vị trí, phòng ban, người phụ trách, ngày mua, tình trạng [hoạt động\|bảo trì\|hỏng\|ngưng sử dụng]); đính kèm tài liệu thiết bị (hướng dẫn, ảnh) lên MinIO | ✅ FR-EQP-001..004 |
| M5.2 Hiệu chuẩn (§6.4/§6.5) | Lịch hiệu chuẩn định kỳ (chu kỳ tháng/năm); ghi nhận lần hiệu chuẩn (ngày, provider, kết quả đạt/không đạt, `next_due_date`, đính kèm CoC/cert); lịch sử hiệu chuẩn bất biết; CRON-5 nhắc 30/15/7 ngày; cảnh báo quá hạn | ✅ FR-EQP-005..011 |

**Trong scope `[SCOPE]`:**
- CRUD **thiết bị (`equipments`)**: tên, `code` (mã thiết bị duy nhất, không lộ ID tuần tự), vị trí (`location`), phòng ban sở hữu (`department_id`), người phụ trách (`responsible_user_id`), ngày mua (`purchase_date`), tình trạng (`status` ∈ {`active` hoạt động, `maintenance` bảo trì, `broken` hỏng, `retired` ngưng sử dụng}).
- **Đính kèm tài liệu thiết bị** (hướng dẫn sử dụng, ảnh, hồ sơ) lên **MinIO** qua `attachments` polymorphic (`owner_type='equipment'`).
- **Lịch hiệu chuẩn định kỳ**: mỗi thiết bị có **chu kỳ hiệu chuẩn** (`calibration_cycle_value` + `calibration_cycle_unit` ∈ {tháng, năm}); từ chu kỳ + lần hiệu chuẩn gần nhất → tính `next_due_date`.
- **Ghi nhận lần hiệu chuẩn (`calibrations`)**: ngày hiệu chuẩn (`calibrated_at`), đơn vị/provider hiệu chuẩn (`provider`), kết quả (`result` ∈ {`pass` đạt, `fail` không đạt}), ngày hiệu chuẩn kế tiếp (`next_due_date`), đính kèm **giấy chứng nhận CoC/cert** lên MinIO (`attachments` `owner_type='calibration'`).
- **Tự tính `next_due_date`** = `calibrated_at` + chu kỳ (tháng/năm) khi ghi lần hiệu chuẩn mới (FR-EQP-008 / BR-EQP-006); cập nhật `equipments.next_due_date` = `next_due_date` của lần hiệu chuẩn **gần nhất**.
- **Lịch sử hiệu chuẩn bất biến (immutable — §8.4)**: bản ghi `calibrations` đã tạo **KHÔNG sửa/không xóa**; sai sót → tạo bản ghi mới / bản đính chính (audit). Timeline đầy đủ các lần hiệu chuẩn của một thiết bị.
- **CRON-5 nhắc trước hiệu chuẩn** (R16): hằng ngày 07:00, thiết bị có `next_due_date` còn 30/15/7 ngày → in-app cho **người phụ trách thiết bị** + **trưởng nhóm phòng** (qua `notifications` M7).
- **Cảnh báo quá hạn / không đạt (badge)**: thiết bị có `next_due_date` < hôm nay (quá hạn) hoặc kết quả hiệu chuẩn gần nhất `fail` → đánh dấu cảnh báo "**Quá hạn hiệu chuẩn — khuyến nghị không sử dụng**" / "**Hiệu chuẩn KHÔNG ĐẠT — khuyến nghị không sử dụng**" ở mọi nơi hiển thị thiết bị; **bộ lọc** "thiết bị quá hạn / không đạt".
- **Audit log §8.4**: mọi tạo/sửa/xóa thiết bị + tạo bản ghi hiệu chuẩn ghi `audit_logs`.

**Ngoài scope `[OUT-OF-SCOPE → cần CR]`:**
- **Lịch bảo trì/sửa chữa thiết bị (maintenance schedule)** ngoài hiệu chuẩn: bản đầu chỉ có `status=maintenance` và hiệu chuẩn; lịch bảo trì định kỳ riêng + nhật ký bảo trì → CR.
- **Khóa cứng (block) thiết bị quá hạn khỏi luồng thử nghiệm M1**: bản đầu chỉ **cảnh báo (badge) + khuyến nghị**; ràng buộc cứng "mẫu không được dùng thiết bị quá hạn" (chặn ở M1) → CR (OQ#3).
- **Liên kết thiết bị ↔ mẫu/phép thử của M1** (thiết bị nào dùng cho mẫu nào, traceability đo lường ở mức mẫu): ngoài scope M5 bản đầu → CR.
- **Quản lý phụ kiện/linh kiện con của thiết bị (sub-asset, bảo hành chi tiết)**: bản đầu thiết bị là 1 cấp → CR.
- **Hiệu chuẩn nội bộ với chuẩn đo lường có truy xuất nguồn gốc đầy đủ (intermediate checks, độ không đảm bảo đo)** ở mức số liệu kỹ thuật: bản đầu ghi nhận kết quả đạt/không đạt + lưu cert; tính toán độ không đảm bảo đo / liên kết chuẩn chi tiết §6.5 → CR.
- **Thông báo qua email / Zalo**: chỉ in-app (C02). Email/Zalo → CR.
- **Theo dõi vị trí thiết bị real-time / IoT integration**: ngoài scope.

### 1.3 Định nghĩa, từ viết tắt và thuật ngữ

| Thuật ngữ | Định nghĩa |
|-----------|------------|
| **Thiết bị (Equipment)** | Một thiết bị đo lường/thử nghiệm của lab (`equipments`): định danh bởi `code` (mã thiết bị) + tên; thuộc 1 phòng ban; có người phụ trách; có tình trạng và (nếu thuộc diện hiệu chuẩn) chu kỳ + ngày hiệu chuẩn kế tiếp. |
| **Mã thiết bị (`code`)** | Mã hiển thị duy nhất của thiết bị (vd `TB-HOA-007` — định dạng OQ#1), không lộ ID tuần tự nội bộ (ID thật là UUID — CONSTRAINT-4). |
| **Người phụ trách (Responsible / Custodian)** | User chịu trách nhiệm thiết bị (`equipments.responsible_user_id`) — nhận thông báo nhắc hiệu chuẩn (CRON-5). |
| **Tình trạng thiết bị (`status`)** | `active` (hoạt động) / `maintenance` (bảo trì) / `broken` (hỏng) / `retired` (ngưng sử dụng). KHÁC với cảnh báo hiệu chuẩn (badge tính từ `next_due_date`/kết quả — BR-EQP-009). |
| **Chu kỳ hiệu chuẩn (Calibration cycle)** | Khoảng thời gian giữa 2 lần hiệu chuẩn của thiết bị: `calibration_cycle_value` (số) + `calibration_cycle_unit` ∈ {month, year}. Dùng để tính `next_due_date`. |
| **Lần hiệu chuẩn (Calibration record)** | Một bản ghi `calibrations`: ngày hiệu chuẩn (`calibrated_at`), provider, kết quả (`result` ∈ {pass, fail}), ngày kế tiếp (`next_due_date`), giấy chứng nhận đính kèm. **Bất biến** sau khi tạo (§8.4). |
| **`next_due_date` (Ngày hiệu chuẩn kế tiếp)** | Ngày đến hạn hiệu chuẩn lần sau = `calibrated_at` + chu kỳ. Lưu cả ở bản ghi hiệu chuẩn (`calibrations.next_due_date`) và denormalize ở thiết bị (`equipments.next_due_date` = của lần hiệu chuẩn gần nhất) để CRON-5 + cảnh báo + lọc chạy nhanh. |
| **Quá hạn hiệu chuẩn (Overdue)** | Thiết bị có `equipments.next_due_date` < ngày hiện tại và chưa có lần hiệu chuẩn mới. Sinh cảnh báo (badge) BR-EQP-009. |
| **Kết quả "không đạt" (Fail)** | Lần hiệu chuẩn gần nhất có `result='fail'` → cảnh báo (badge) khuyến nghị không sử dụng (BR-EQP-009). |
| **Cảnh báo (Badge)** | Nhãn cảnh báo hiển thị trên thiết bị: "Quá hạn hiệu chuẩn" / "Hiệu chuẩn không đạt" — khuyến nghị không dùng cho thử nghiệm. **KHÔNG khóa cứng** thao tác (OQ#3 default — tinh thần "lô fail" M2). |
| **CoC / Cert (Giấy chứng nhận hiệu chuẩn)** | File chứng nhận hiệu chuẩn (Certificate of Calibration) do provider cấp, đính kèm vào bản ghi hiệu chuẩn (MinIO, `attachments` `owner_type='calibration'`). |
| **Bất biến (Immutable)** | Bản ghi `calibrations` đã tạo không được sửa/xóa; đính chính = tạo bản ghi mới (§8.4). |
| **Provider (Đơn vị hiệu chuẩn)** | Đơn vị thực hiện hiệu chuẩn (ngoài hoặc nội bộ) — lưu dạng text (`provider`) ở bản đầu (OQ#4 có cần danh mục provider riêng). |
| **VILAS** | Hệ thống công nhận phòng thí nghiệm Việt Nam (theo ISO/IEC 17025). |
| **Audit log** | Bản ghi bất biến trong `audit_logs` (M7): ai, khi nào, làm gì, trên tài nguyên nào, với `correlation_id` (§8.4). |
| **RBAC** | Role-Based Access Control + phạm vi theo phòng ban. |
| **MinIO** | Object storage self-host (C01) lưu file đính kèm; M5 lưu `file_key`, không lưu binary trong DB. |

### 1.4 Tài liệu tham chiếu

| Tài liệu | Vai trò |
|----------|---------|
| `lims/docs/00-meeting-note-analysis.md` | Yêu cầu gốc **R16** ("17025 vlab — nhắc trước thời gian hiệu chuẩn") + R2 (kèm file), R11 (object storage); quyết định chốt C01/C02/C03 |
| `lims/docs/01-demo-scope.md` | Cây module M5.1/M5.2, RBAC matrix dòng "Thiết bị — hiệu chuẩn" (mục B), ERD core M5 `equipments`/`calibrations` (mục C), **CRON-5** (mục D), mapping 17025 §6.4/§6.5 (mục E) |
| `lims/docs/13-srs-m3-document.md` | Chuẩn phong cách FR/BR/UC/NFR/AC Given–When–Then; pattern **immutable bản ghi** (§8.4); RBAC scope phòng ban + Kế toán chỉ xem (👁); attachments polymorphic; audit |
| `lims/docs/08-contract-m7-schema.md` | `users`/`departments`/`attachments`/`audit_logs`/`notifications` dùng chung; `attachments.owner_type` đã whitelist `'equipment'`/`'calibration'` (dòng 293); `notifications` cho CRON-5 (dòng 335) |
| `~/.claude/rules/nfr.md` | Template NFR chuẩn IEEE 830 |
| `~/.claude/rules/api.md` | Quy ước REST, response format, status code, không lộ ID tuần tự |
| `~/.claude/rules/logging.md` | Structured logging, correlationId, error handling |
| **ISO/IEC 17025:2017** §6.4 | **Thiết bị** — nhận biết, hồ sơ thiết bị, hiệu chuẩn/kiểm tra trước sử dụng, trạng thái hiệu chuẩn, ngăn sử dụng thiết bị không phù hợp |
| **ISO/IEC 17025:2017** §6.5 | **Liên kết chuẩn đo lường** — hiệu chuẩn có truy xuất nguồn gốc, lưu giấy chứng nhận hiệu chuẩn |
| **ISO/IEC 17025:2017** §8.4 | **Kiểm soát hồ sơ** — lưu trữ, bảo vệ, truy xuất; ngăn thay đổi/mất mát trái phép (bất biến, audit) |

---

## 2. Mô tả tổng quan

### 2.1 Bối cảnh sản phẩm

M5 là một trong 7 module của LIMS monolith (FastAPI + Next.js + PostgreSQL + Redis + MinIO + APScheduler, Docker Compose). M5 **phụ thuộc** vào M7:

- **M7 (Auth + RBAC + phòng ban + audit log):** mọi API M5 yêu cầu xác thực JWT và kiểm tra quyền theo vai trò + phạm vi phòng ban. Audit ghi vào `audit_logs`. Quyền `equipment:*` (xem mục §2.3) cấp theo RBAC matrix.
- **`departments` (M7):** mỗi thiết bị thuộc 1 phòng ban (`equipments.department_id`); phạm vi quản lý giới hạn theo phòng (staff phòng nào quản thiết bị phòng đó); **`departments.lead_user_id`** = trưởng nhóm phòng → nhận CRON-5 cùng người phụ trách (BR-EQP-011).
- **`users` (M7):** `equipments.responsible_user_id` = người phụ trách thiết bị (nhận CRON-5).
- **Bảng `attachments` polymorphic (M7):** lưu tài liệu thiết bị (`owner_type='equipment'`) + giấy chứng nhận hiệu chuẩn (`owner_type='calibration'`). Whitelist đã có (08-contract-m7-schema dòng 293).
- **MinIO (C01):** lưu file; M5 lưu `file_key` không lưu binary trong DB.
- **`notifications` (M7.5):** CRON-5 INSERT thông báo in-app (in-app only — C02).
- **APScheduler (M7):** chạy CRON-5 hằng ngày 07:00, có Redis lock chống chạy trùng (đồng bộ CRON-1..6).

M5 **được tham chiếu / cung cấp cho**:
- **M6 (Báo cáo & Thống kê):** dashboard số thiết bị theo tình trạng, số thiết bị quá hạn hiệu chuẩn, lịch hiệu chuẩn sắp tới.
- **M1 (Mẫu):** bản đầu CHƯA ràng buộc cứng "mẫu dùng thiết bị nào / thiết bị quá hạn không được dùng"; chỉ cảnh báo ở M5 (xem §1.2 OUT-OF-SCOPE, OQ#3).

### 2.2 Chức năng chính

1. Quản lý danh mục thiết bị: CRUD thiết bị (tên, mã, vị trí, phòng ban, người phụ trách, ngày mua, tình trạng); sinh mã thiết bị duy nhất không lộ ID tuần tự; đính kèm tài liệu thiết bị (MinIO).
2. Tìm kiếm / lọc / liệt kê thiết bị theo phòng ban, tình trạng, **trạng thái hiệu chuẩn** (sắp tới hạn / quá hạn / không đạt).
3. Cấu hình **chu kỳ hiệu chuẩn** cho thiết bị (tháng/năm).
4. Ghi nhận **lần hiệu chuẩn** (ngày, provider, kết quả đạt/không đạt, đính kèm CoC/cert) → **tự tính `next_due_date`** + cập nhật cảnh báo thiết bị.
5. **Lịch sử hiệu chuẩn bất biến** (immutable §8.4): timeline các lần hiệu chuẩn; bản ghi không sửa/xóa.
6. **CRON-5** nhắc trước hiệu chuẩn (30/15/7 ngày) → in-app cho người phụ trách + trưởng nhóm (R16).
7. **Cảnh báo (badge)** thiết bị quá hạn hiệu chuẩn / kết quả không đạt → khuyến nghị không sử dụng (KHÔNG khóa cứng — OQ#3).
8. Audit toàn bộ thao tác phục vụ duy trì công nhận VILAS (§6.4/§8.4).

### 2.3 Đối tượng người dùng & quyền (RBAC + phạm vi phòng ban)

Trích từ RBAC matrix `01-demo-scope.md` (4 vai trò; dòng "**Thiết bị — hiệu chuẩn**": Admin ✅, Ban lãnh đạo 👁, Kế toán —, Nhân sự/KTV ✅(phòng)). Phạm vi dữ liệu: theo phòng ban cho thao tác ghi của staff; Admin toàn hệ thống. **Lưu ý đặc thù M5 (theo matrix):** Ban lãnh đạo (leader) = **👁 chỉ xem** thiết bị/hiệu chuẩn (KHÁC các module tài liệu/mẫu nơi leader có quyền ghi); **Kế toán = không truy cập** (theo dòng matrix "—"). Đề bài chốt: "accountant: xem thiết bị (👁), KHÔNG quản lý" — xem OQ#5 để KH chốt dứt khoát Kế toán **xem được** hay **không truy cập** (matrix ghi "—").

| Actor | Mô tả | Quyền trong M5 |
|-------|-------|----------------|
| **Admin** | Quản trị hệ thống | Toàn quyền mọi thao tác thiết bị & hiệu chuẩn (mọi phòng ban): CRUD thiết bị, đính kèm tài liệu, cấu hình chu kỳ, ghi lần hiệu chuẩn, xem lịch sử/thống kê, xem mọi cảnh báo. |
| **Ban lãnh đạo (leader)** | Lãnh đạo lab | **CHỈ XEM (👁)** thiết bị + lịch sử hiệu chuẩn + cảnh báo + thống kê (mọi phòng). KHÔNG CRUD thiết bị, KHÔNG ghi lần hiệu chuẩn (theo matrix dòng "Thiết bị — hiệu chuẩn": leader 👁). Cũng là **trưởng nhóm tiềm năng** (nếu `departments.lead_user_id`) → nhận CRON-5. |
| **Kế toán (accountant)** | Tài chính | **Theo matrix demo-scope: KHÔNG truy cập M5 ("—")** → mọi API M5 trả 403. (Đề bài nêu "xem 👁" → mâu thuẫn nhẹ với matrix → **OQ#5** để KH chốt: nếu KH chọn "Kế toán xem 👁" thì áp như leader chỉ xem; bản đầu **default theo matrix = không truy cập** để an toàn). |
| **Nhân sự/KTV (staff)** | Kỹ thuật viên | **Quản lý thiết bị & hiệu chuẩn trong phòng mình (✅ scope phòng)**: CRUD thiết bị phòng mình, đính kèm tài liệu, cấu hình chu kỳ, ghi lần hiệu chuẩn, xem lịch sử + cảnh báo. **Xem (👁) thiết bị mọi phòng** (đọc, OQ#2 — default chỉ phòng mình hay toàn lab). KHÔNG sửa thiết bị phòng khác. |

Quy ước: ✅ = toàn quyền trong phạm vi · 👁 = chỉ xem · — = không truy cập · (phòng) = giới hạn phòng ban của user.

> **Người phụ trách thiết bị** (`equipments.responsible_user_id`) là **thuộc tính dữ liệu**, không phải vai trò RBAC. Người phụ trách thường là một staff trong phòng; nhận CRON-5. Quyền ghi vẫn theo RBAC phòng ban (staff phòng đó / Admin).
> **Bản ghi hiệu chuẩn bất biến (§8.4):** không vai trò nào (kể cả Admin) có endpoint sửa/xóa bản ghi `calibrations` đã tạo; đính chính = tạo bản ghi mới (BR-EQP-007).

### 2.4 Ràng buộc (Constraints)

- **CONSTRAINT-1 (Bản ghi hiệu chuẩn bất biến — §8.4):** `calibrations` đã tạo KHÔNG sửa/xóa; không có endpoint PATCH/DELETE bản ghi hiệu chuẩn. Đính chính = tạo bản ghi mới (BR-EQP-007).
- **CONSTRAINT-2 (`next_due_date` tự tính):** khi ghi lần hiệu chuẩn mới, hệ thống tự tính `next_due_date` = `calibrated_at` + chu kỳ và cập nhật `equipments.next_due_date` = của lần gần nhất (BR-EQP-006). Người dùng KHÔNG nhập tay `next_due_date` (trừ override có lý do — OQ#1).
- **CONSTRAINT-3 (Cảnh báo không khóa cứng — OQ#3):** thiết bị quá hạn / kết quả không đạt → cảnh báo (badge) + khuyến nghị không dùng; bản đầu KHÔNG chặn cứng thao tác/luồng M1. (Khóa cứng → CR.)
- **CONSTRAINT-4 (Mã không lộ tuần tự):** `id` nội bộ là UUID; `equipments.code` hiển thị duy nhất, không đoán được tuần tự (rule api.md).
- **CONSTRAINT-5 (Audit VILAS §6.4/§8.4):** mọi tạo/sửa/xóa thiết bị + tạo bản ghi hiệu chuẩn ghi `audit_logs` (user, action, resource, resource_id, correlation_id, ip, at, detail).
- **CONSTRAINT-6 (Lưu file):** file (tài liệu thiết bị + CoC/cert) lưu MinIO (C01) qua `attachments` polymorphic (`owner_type` ∈ {equipment, calibration}); M5 lưu `file_key`, không lưu binary trong DB.
- **CONSTRAINT-7 (Thông báo):** chỉ in-app (bảng `notifications`); không email/Zalo (C02).
- **CONSTRAINT-8 (Cron):** CRON-5 chạy APScheduler trong app, hằng ngày 07:00, có Redis lock chống chạy trùng (đồng bộ CRON-1..6); chỉ in-app.
- **CONSTRAINT-9 (Stack & quy mô):** FastAPI, PostgreSQL, Redis, MinIO; quy mô ~40 user (C03) — monolith, không scale ngang.
- **CONSTRAINT-10 (Phụ thuộc M7):** `users`/`departments`/`attachments`/`audit_logs`/`notifications` của M7 phải sẵn sàng trước khi `/contract` M5 (đặc biệt `departments.lead_user_id` cho CRON-5).

### 2.5 Giả định (Assumptions) — xem chi tiết §7

- ASSUMPTION-1: 1 thiết bị (`equipments`) có 0..n bản ghi hiệu chuẩn (`calibrations`) — quan hệ 1-n; mỗi bản ghi 1 lần hiệu chuẩn (ngày, provider, kết quả, next_due, cert).
- ASSUMPTION-2: **Chu kỳ hiệu chuẩn lưu trên từng thiết bị** (`calibration_cycle_value` + `unit`), không cố định toàn hệ thống (OQ#1: cho phép mỗi thiết bị một chu kỳ; có thể có thiết bị không thuộc diện hiệu chuẩn → chu kỳ NULL).
- ASSUMPTION-3: `next_due_date` **tự tính** = `calibrated_at` + chu kỳ; cho phép override thủ công có lý do nếu nhà cung cấp ghi ngày khác trên cert (OQ#1 default: tự tính, cho override + audit).
- ASSUMPTION-4: Cảnh báo quá hạn / không đạt là **badge + khuyến nghị**, KHÔNG khóa cứng (OQ#3 default — tinh thần "lô fail" M2).
- ASSUMPTION-5: CRON-5 nhắc các mốc **30/15/7 ngày** (theo demo-scope CRON-5) trước `next_due_date`, in-app cho người phụ trách + trưởng nhóm; idempotent (mỗi thiết bị × mỗi mốc chỉ 1 thông báo).
- ASSUMPTION-6: Mã thiết bị default `<TB>-<MAPHONG>-<seq>` (vd `TB-HOA-007`); định dạng cấu hình (OQ#... — đồng bộ M3 OQ#1).

---

## 3. Yêu cầu chức năng chi tiết

Mỗi FR có ID dạng `FR-EQP-NNN`. Business rule dạng `BR-EQP-NNN` ở §4. Acceptance Criteria dạng Given–When–Then (cover happy path + edge + RBAC + lỗi input).

---

### FR-EQP-001: Tạo thiết bị

- **Mô tả:** Tạo một **thiết bị (`equipments`)** với metadata: tên, vị trí, phòng ban sở hữu (`department_id`), người phụ trách (`responsible_user_id`), ngày mua (`purchase_date`), tình trạng (`status`, default `active`), và (tùy chọn) chu kỳ hiệu chuẩn (`calibration_cycle_value` + `unit`). Khi lưu, hệ thống sinh `code` duy nhất (FR-EQP-003). Thiết bị mới chưa có lần hiệu chuẩn → `next_due_date` = NULL (chưa cảnh báo quá hạn cho tới khi có lần hiệu chuẩn hoặc theo chính sách OQ#... thiết bị mua chưa hiệu chuẩn).
- **Độ ưu tiên:** P0
- **Actor:** staff (phòng mình), Admin (mọi phòng). Leader chỉ xem (👁). Kế toán không truy cập (theo matrix — OQ#5).
- **Tiền điều kiện:** user đã đăng nhập, có quyền `equipment:create` trong phạm vi phòng ban.
- **Luồng chính:**
  1. User mở "Danh mục thiết bị" → "Thêm thiết bị".
  2. Nhập tên, vị trí, phòng ban (mặc định = phòng của user), người phụ trách (trong phòng), ngày mua, tình trạng; (tùy chọn) chu kỳ hiệu chuẩn.
  3. Hệ thống validate quyền + phạm vi phòng (BR-EQP-003) + người phụ trách thuộc phòng (BR-EQP-013) → sinh `code` (FR-EQP-003) → lưu `equipments` (status, next_due_date=NULL) → ghi `audit_logs` action=`EQUIPMENT_CREATE`.
- **Luồng phụ / ngoại lệ:**
  - A1: phòng ban sở hữu ≠ phòng của user (và không phải Admin) → 403 `FORBIDDEN`.
  - A2: thiếu tên / tình trạng không hợp lệ → 400 `VALIDATION_ERROR` / 422 `INVALID_STATUS`.
  - A3: chu kỳ hiệu chuẩn có giá trị nhưng đơn vị không ∈ {month, year} → 422 `INVALID_CALIBRATION_CYCLE`.
- **Hậu điều kiện:** thiết bị tồn tại với `code` duy nhất; audit ghi nhận.
- **Business Rules:** BR-EQP-001, BR-EQP-002, BR-EQP-003, BR-EQP-013, BR-EQP-014.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN staff phòng "Hóa" WHEN tạo thiết bị tên "Máy đo pH", phòng=Hóa, người phụ trách=user X (phòng Hóa), tình trạng=active, chu kỳ=12 tháng THEN trả 201, thiết bị có `code` duy nhất, status=active, next_due_date=NULL, audit `EQUIPMENT_CREATE`.
  - AC2 (RBAC scope): GIVEN staff phòng "Hóa" WHEN tạo thiết bị cho phòng "Sinh" THEN trả 403 `FORBIDDEN`, không tạo.
  - AC3 (RBAC — leader chỉ xem): GIVEN leader WHEN gọi API tạo thiết bị THEN trả 403 `FORBIDDEN` (matrix: leader 👁).
  - AC4 (lỗi input): GIVEN form tạo thiết bị WHEN không nhập tên THEN trả 400 `VALIDATION_ERROR`, không tạo.
  - AC5 (người phụ trách khác phòng): GIVEN staff phòng Hóa WHEN chọn người phụ trách thuộc phòng Sinh THEN trả 422 `RESPONSIBLE_NOT_IN_DEPARTMENT` (BR-EQP-013).
- **Data cần thiết (mức logic):** Equipment { id(UUID), code(UNIQUE), name, location, department_id(FK NOT NULL), responsible_user_id(FK→users), purchase_date(DATE NULL), status(enum), calibration_cycle_value(INT NULL), calibration_cycle_unit(enum month|year NULL), next_due_date(DATE NULL), created_by(FK), created_at }.
- **API cần (ý định):** "tạo thiết bị", "lấy danh sách user trong phòng (chọn người phụ trách)".

---

### FR-EQP-002: Sửa / cập nhật thiết bị (metadata + tình trạng + chu kỳ)

- **Mô tả:** Sửa metadata thiết bị (tên, vị trí, người phụ trách, ngày mua, **tình trạng**, **chu kỳ hiệu chuẩn**). **KHÔNG đổi `code`** (bất biến — BR-EQP-014); **KHÔNG đổi `department_id`** trừ Admin (chuyển sở hữu phòng — OQ ngoài bản đầu). Đổi chu kỳ hiệu chuẩn KHÔNG hồi tố `next_due_date` của bản ghi hiệu chuẩn đã có, nhưng áp dụng cho lần hiệu chuẩn TIẾP THEO (BR-EQP-006).
- **Độ ưu tiên:** P1
- **Actor:** staff (thiết bị phòng mình), Admin. Leader chỉ xem. Kế toán không truy cập.
- **Tiền điều kiện:** thiết bị tồn tại; user có quyền `equipment:update` trong phạm vi phòng.
- **Luồng chính:**
  1. User mở chi tiết thiết bị → "Sửa".
  2. Sửa các trường cho phép → lưu → ghi `audit_logs` action=`EQUIPMENT_UPDATE` (detail before/after các trường thay đổi).
- **Luồng phụ / ngoại lệ:**
  - A1: cố đổi `code` → 422 `CODE_IMMUTABLE` (BR-EQP-014).
  - A2: sửa thiết bị phòng khác (không Admin) → 403 `FORBIDDEN`.
  - A3: đổi tình trạng sang giá trị không hợp lệ → 422 `INVALID_STATUS`.
- **Hậu điều kiện:** metadata cập nhật; audit ghi before/after.
- **Business Rules:** BR-EQP-002, BR-EQP-003, BR-EQP-006, BR-EQP-014.
- **Acceptance Criteria:**
  - AC1 (happy — đổi tình trạng): GIVEN thiết bị `TB-HOA-007` active WHEN staff phòng Hóa đổi tình trạng → maintenance THEN lưu, audit `EQUIPMENT_UPDATE` ghi before/after status.
  - AC2 (edge — code bất biến): GIVEN thiết bị đã có `code` WHEN gửi request đổi `code` THEN trả 422 `CODE_IMMUTABLE`, code không đổi.
  - AC3 (RBAC scope): GIVEN staff phòng Hóa WHEN sửa thiết bị phòng Sinh THEN trả 403 `FORBIDDEN`.
  - AC4 (đổi chu kỳ không hồi tố): GIVEN thiết bị có lần hiệu chuẩn next_due tính theo chu kỳ 12 tháng WHEN đổi chu kỳ → 6 tháng THEN `next_due_date` hiện tại KHÔNG đổi; lần hiệu chuẩn tiếp theo dùng chu kỳ 6 tháng (BR-EQP-006).
- **Data cần thiết:** Equipment.name, location, responsible_user_id, purchase_date, status, calibration_cycle_* (mutable); code, id (immutable).
- **API cần:** "sửa thiết bị".

---

### FR-EQP-003: Sinh mã thiết bị duy nhất (không lộ ID tuần tự)

- **Mô tả:** Khi tạo thiết bị, hệ thống sinh `code` duy nhất, human-readable, không lộ ID tuần tự nội bộ (default `<TB>-<MAPHONG>-<seq>` vd `TB-HOA-007`; định dạng cấu hình). ID thật là UUID; không expose serial id liên tiếp.
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (trong giao dịch tạo thiết bị FR-EQP-001).
- **Tiền điều kiện:** đang tạo thiết bị.
- **Luồng chính:**
  1. Hệ thống sinh `code` theo định dạng cấu hình, đảm bảo duy nhất (unique constraint + retry nếu trùng).
  2. Lưu `code` cùng thiết bị.
- **Luồng phụ / ngoại lệ:**
  - A1: trùng `code` (race) → retry trong cùng transaction; fail sau N lần → 500 + log ERROR.
- **Hậu điều kiện:** thiết bị có `code` duy nhất.
- **Business Rules:** BR-EQP-014.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN tạo thiết bị phòng Hóa WHEN lưu THEN `code` khớp định dạng cấu hình + duy nhất toàn hệ thống; API trả `code` nhưng KHÔNG trả id UUID dạng số tuần tự.
  - AC2 (duy nhất): GIVEN 2 thiết bị tạo gần đồng thời WHEN cả hai sinh mã THEN 2 `code` khác nhau (unique constraint).
  - AC3 (không lộ tuần tự): GIVEN 2 thiết bị tạo liên tiếp WHEN so sánh định danh dùng ngoài THEN không suy ra được số thứ tự nội bộ liên tiếp (CONSTRAINT-4).
- **Data cần thiết:** Equipment.code (UNIQUE); cấu hình định dạng mã.
- **API cần:** nội bộ (trong tạo thiết bị).

---

### FR-EQP-004: Đính kèm / tải tài liệu thiết bị (MinIO) + tìm/lọc/xem chi tiết

- **Mô tả:** (a) Đính kèm tài liệu thiết bị (hướng dẫn sử dụng, ảnh, hồ sơ) lên MinIO qua `attachments` (`owner_type='equipment'`) (R2, R11); (b) Tìm kiếm / lọc / liệt kê thiết bị phân trang theo phòng ban + tình trạng + **trạng thái hiệu chuẩn** (sắp tới hạn/quá hạn/không đạt) + từ khóa (tên/code); (c) Xem chi tiết thiết bị (metadata + tài liệu đính kèm + lịch sử hiệu chuẩn — FR-EQP-009 + cảnh báo).
- **Độ ưu tiên:** P0
- **Actor:** Admin (mọi), staff (👁 mọi phòng — OQ#2; ghi/đính kèm chỉ phòng mình), leader (👁). Kế toán theo OQ#5.
- **Tiền điều kiện:** đã đăng nhập, có quyền `equipment:read`; đính kèm cần `equipment:update` phạm vi phòng.
- **Luồng chính:**
  1. User mở "Danh mục thiết bị" → nhập bộ lọc (phòng/tình trạng/trạng thái hiệu chuẩn/từ khóa) + phân trang.
  2. Hệ thống áp RBAC → trả danh sách thiết bị kèm `code`, tên, phòng, người phụ trách, tình trạng, `next_due_date`, **cảnh báo (badge)** nếu quá hạn/không đạt (BR-EQP-009).
  3. (Đính kèm) User mở chi tiết → "Thêm tài liệu" → upload file (validate loại + dung lượng — BR-EQP-012) → lưu MinIO + `attachments` → audit `EQUIPMENT_ATTACH`.
- **Luồng phụ / ngoại lệ:**
  - A1: đính kèm cho thiết bị phòng khác (không Admin) → 403 `FORBIDDEN`.
  - A2: file sai loại / quá lớn → 422 `INVALID_FILE_TYPE` / `FILE_TOO_LARGE` (BR-EQP-012).
- **Hậu điều kiện:** tài liệu lưu MinIO + liên kết thiết bị; danh sách/chi tiết hiển thị đúng RBAC + cảnh báo.
- **Business Rules:** BR-EQP-003, BR-EQP-009, BR-EQP-012.
- **Acceptance Criteria:**
  - AC1 (happy liệt kê + badge): GIVEN có 50 thiết bị (5 quá hạn) WHEN lọc phòng=Hóa, trạng thái hiệu chuẩn=quá hạn THEN trả đúng các thiết bị quá hạn phòng Hóa, mỗi cái có badge "Quá hạn hiệu chuẩn".
  - AC2 (happy đính kèm): GIVEN thiết bị `TB-HOA-007` WHEN staff phòng Hóa upload "huong-dan-may-do-ph.pdf" THEN file lưu MinIO + attachments(owner_type=equipment), audit `EQUIPMENT_ATTACH`, file tải lại được.
  - AC3 (RBAC đính kèm): GIVEN staff phòng Hóa WHEN đính kèm tài liệu cho thiết bị phòng Sinh THEN trả 403 `FORBIDDEN`.
  - AC4 (lỗi file): GIVEN upload "macro.docm" không thuộc whitelist WHEN đính kèm THEN trả 422 `INVALID_FILE_TYPE`.
  - AC5 (performance): GIVEN 2,000 thiết bị WHEN lọc + phân trang 20/trang THEN P95 < 500ms, query dùng index (NFR-PERF-EQP-002).
- **Data cần thiết:** Equipment(list) + badge cảnh báo; attachments(owner_type=equipment, owner_id=equipment.id, file_key, file_name, mime, size, uploaded_by).
- **API cần:** "liệt kê/tìm thiết bị (lọc + phân trang)", "lấy chi tiết thiết bị", "đính kèm tài liệu thiết bị", "tải tài liệu thiết bị (presigned URL)".

---

### FR-EQP-005: Cấu hình chu kỳ hiệu chuẩn cho thiết bị

- **Mô tả:** Thiết lập / thay đổi **chu kỳ hiệu chuẩn** của thiết bị: `calibration_cycle_value` (số nguyên dương) + `calibration_cycle_unit` ∈ {month, year}. Thiết bị không thuộc diện hiệu chuẩn → chu kỳ NULL (không sinh nhắc/cảnh báo hiệu chuẩn). Chu kỳ dùng để tự tính `next_due_date` khi ghi lần hiệu chuẩn (FR-EQP-008).
- **Độ ưu tiên:** P0
- **Actor:** staff (thiết bị phòng mình), Admin. Leader chỉ xem.
- **Tiền điều kiện:** thiết bị tồn tại; user có quyền `equipment:update` phạm vi phòng.
- **Luồng chính:**
  1. User mở chi tiết thiết bị → "Cấu hình hiệu chuẩn" → nhập chu kỳ (vd 12 tháng / 1 năm).
  2. Hệ thống validate (value > 0, unit ∈ {month, year}) → lưu → audit `EQUIPMENT_UPDATE` (chu kỳ).
- **Luồng phụ / ngoại lệ:**
  - A1: value ≤ 0 hoặc unit không hợp lệ → 422 `INVALID_CALIBRATION_CYCLE` (BR-EQP-004).
- **Hậu điều kiện:** chu kỳ lưu; áp dụng cho lần hiệu chuẩn tiếp theo (không hồi tố — BR-EQP-006).
- **Business Rules:** BR-EQP-004, BR-EQP-006.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN thiết bị `TB-HOA-007` WHEN staff đặt chu kỳ = 1 năm THEN lưu calibration_cycle_value=1, unit=year, audit ghi.
  - AC2 (lỗi input): GIVEN cấu hình chu kỳ WHEN nhập value=0 hoặc unit="week" THEN trả 422 `INVALID_CALIBRATION_CYCLE`.
  - AC3 (thiết bị không hiệu chuẩn): GIVEN thiết bị để chu kỳ NULL WHEN chạy CRON-5 THEN thiết bị này KHÔNG bị nhắc/cảnh báo hiệu chuẩn (BR-EQP-010).
- **Data cần thiết:** Equipment.calibration_cycle_value (INT NULL > 0), calibration_cycle_unit (enum month|year NULL).
- **API cần:** "cấu hình chu kỳ hiệu chuẩn" (có thể gộp vào FR-EQP-002 sửa thiết bị).

---

### FR-EQP-006: Ghi nhận lần hiệu chuẩn + tự tính next_due_date (§6.4/§6.5)

- **Mô tả:** Ghi một **lần hiệu chuẩn (`calibrations`)** cho thiết bị: ngày hiệu chuẩn (`calibrated_at`), đơn vị/provider hiệu chuẩn (`provider`), kết quả (`result` ∈ {pass, fail}), **đính kèm giấy chứng nhận CoC/cert** lên MinIO (`attachments` `owner_type='calibration'` — bắt buộc nếu result=pass, OQ#... default khuyến nghị/bắt buộc). Hệ thống **tự tính `next_due_date`** = `calibrated_at` + chu kỳ thiết bị (BR-EQP-006) (cho phép override + lý do nếu cert ghi khác — OQ#1). Sau khi ghi: cập nhật `equipments.next_due_date` = `next_due_date` của lần này (nếu là lần gần nhất) + cập nhật cảnh báo (FR-EQP-010). **Bản ghi hiệu chuẩn bất biến** sau khi tạo (§8.4 — BR-EQP-007).
- **Độ ưu tiên:** P0
- **Actor:** staff (thiết bị phòng mình), Admin. Leader chỉ xem. Kế toán không truy cập.
- **Tiền điều kiện:** thiết bị tồn tại; thiết bị có chu kỳ hiệu chuẩn (nếu để tự tính next_due — BR-EQP-006); user có quyền `calibration:create` phạm vi phòng.
- **Luồng chính:**
  1. User mở chi tiết thiết bị → "Ghi hiệu chuẩn" → nhập ngày hiệu chuẩn, provider, kết quả (pass/fail), upload CoC/cert.
  2. Hệ thống validate (file CoC theo BR-EQP-012; calibrated_at ≤ hôm nay — BR-EQP-005) → tính `next_due_date` = calibrated_at + chu kỳ (BR-EQP-006).
  3. **Trong 1 transaction:** lưu `calibrations` (immutable) → lưu CoC vào MinIO + `attachments` (owner_type=calibration) → cập nhật `equipments.next_due_date` (nếu lần này là gần nhất theo calibrated_at) → cập nhật cảnh báo (FR-EQP-010) → ghi `audit_logs` action=`CALIBRATION_RECORD`.
- **Luồng phụ / ngoại lệ:**
  - A1: thiết bị chưa cấu hình chu kỳ và không override next_due thủ công → 422 `CALIBRATION_CYCLE_REQUIRED` (BR-EQP-006).
  - A2: `calibrated_at` ở tương lai → 422 `INVALID_CALIBRATION_DATE` (BR-EQP-005).
  - A3: result không ∈ {pass, fail} → 422 `INVALID_CALIBRATION_RESULT`.
  - A4: thiếu CoC/cert khi result=pass (nếu KH chốt bắt buộc — OQ#...) → 400 `CALIBRATION_CERT_REQUIRED`.
  - A5: ghi hiệu chuẩn cho thiết bị phòng khác (không Admin) → 403 `FORBIDDEN`.
- **Hậu điều kiện:** bản ghi hiệu chuẩn (bất biến) tạo; `equipments.next_due_date` cập nhật; cảnh báo cập nhật; CoC lưu MinIO; audit ghi.
- **Business Rules:** BR-EQP-003, BR-EQP-005, BR-EQP-006, BR-EQP-007, BR-EQP-008, BR-EQP-009, BR-EQP-012.
- **Acceptance Criteria:**
  - AC1 (happy + tự tính): GIVEN thiết bị chu kỳ 12 tháng WHEN ghi lần hiệu chuẩn calibrated_at=2026-06-20, result=pass, kèm CoC THEN bản ghi tạo, `next_due_date`=2027-06-20, `equipments.next_due_date`=2027-06-20, audit `CALIBRATION_RECORD`.
  - AC2 (đơn vị năm): GIVEN thiết bị chu kỳ 1 năm WHEN ghi calibrated_at=2026-06-20 THEN next_due_date=2027-06-20 (BR-EQP-006).
  - AC3 (kết quả không đạt → cảnh báo): GIVEN ghi lần hiệu chuẩn result=fail THEN bản ghi tạo, thiết bị nhận badge "Hiệu chuẩn KHÔNG ĐẠT — khuyến nghị không sử dụng" (BR-EQP-009), KHÔNG khóa cứng thao tác.
  - AC4 (lỗi — ngày tương lai): GIVEN ghi hiệu chuẩn WHEN calibrated_at = ngày mai THEN trả 422 `INVALID_CALIBRATION_DATE`.
  - AC5 (lỗi — chưa có chu kỳ): GIVEN thiết bị chu kỳ NULL WHEN ghi hiệu chuẩn không override next_due THEN trả 422 `CALIBRATION_CYCLE_REQUIRED`.
  - AC6 (RBAC): GIVEN staff phòng Hóa WHEN ghi hiệu chuẩn cho thiết bị phòng Sinh THEN trả 403 `FORBIDDEN`; GIVEN leader WHEN ghi hiệu chuẩn THEN trả 403 (👁).
  - AC7 (lỗi file CoC): GIVEN upload CoC sai loại WHEN ghi hiệu chuẩn THEN trả 422 `INVALID_FILE_TYPE`.
- **Data cần thiết (mức logic):** Calibration { id(UUID), equipment_id(FK NOT NULL), calibrated_at(DATE NOT NULL), provider(VARCHAR), result(enum pass|fail), next_due_date(DATE NOT NULL), cert via attachments(owner_type=calibration), created_by(FK→users), created_at(immutable) }.
- **API cần:** "ghi lần hiệu chuẩn (upload CoC + tính next_due)".

---

### FR-EQP-007: Bản ghi hiệu chuẩn bất biến (immutable — §8.4)

- **Mô tả:** Bản ghi `calibrations` đã tạo **KHÔNG được sửa hay xóa**. Không có endpoint PATCH/DELETE bản ghi hiệu chuẩn. Sai sót → tạo bản ghi mới / bản đính chính (có ghi chú lý do trong audit). FR này đặc tả ràng buộc bất biến hệ thống phục vụ §8.4 (hồ sơ hiệu chuẩn là bằng chứng truy xuất nguồn gốc — VILAS).
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (chính sách enforce ở tầng API + DB).
- **Tiền điều kiện:** bản ghi hiệu chuẩn tồn tại.
- **Luồng chính:**
  1. Mọi yêu cầu sửa/xóa bản ghi hiệu chuẩn → bị từ chối.
  2. Đính chính = tạo bản ghi hiệu chuẩn mới (FR-EQP-006) + audit (lý do đính chính trong detail).
- **Luồng phụ / ngoại lệ:**
  - A1: gọi PATCH/DELETE `calibrations/:id` → 405 `METHOD_NOT_ALLOWED` / 403 `IMMUTABLE_RECORD` (không có route).
- **Hậu điều kiện:** lịch sử hiệu chuẩn nguyên vẹn (§8.4).
- **Business Rules:** BR-EQP-007.
- **Acceptance Criteria:**
  - AC1 (immutable — sửa): GIVEN bản ghi hiệu chuẩn đã tạo WHEN cố sửa kết quả/ngày THEN trả 405/403, bản ghi không đổi.
  - AC2 (immutable — xóa): GIVEN bản ghi hiệu chuẩn đã tạo WHEN cố xóa THEN trả 405/403, bản ghi vẫn còn.
  - AC3 (đính chính): GIVEN cần sửa sai THEN tạo bản ghi hiệu chuẩn mới + audit ghi lý do; bản cũ vẫn truy xuất được trong lịch sử.
- **Data cần thiết:** Không có route mutate/delete `calibrations`; (tùy schema) cột `correction_of` tham chiếu bản ghi được đính chính (OQ).
- **API cần:** không expose sửa/xóa bản ghi hiệu chuẩn.

---

### FR-EQP-008: Tự cập nhật next_due_date thiết bị theo lần hiệu chuẩn gần nhất

- **Mô tả:** Quy tắc nền tảng: `equipments.next_due_date` luôn = `next_due_date` của **lần hiệu chuẩn gần nhất** (theo `calibrated_at` lớn nhất) của thiết bị đó. Cập nhật trong transaction ghi hiệu chuẩn (FR-EQP-006). Denormalize để CRON-5 + cảnh báo + lọc chạy nhanh, không phải tính runtime mỗi lần. FR này đặc tả bất biến dữ liệu (không phải endpoint riêng).
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (trong giao dịch ghi hiệu chuẩn FR-EQP-006).
- **Tiền điều kiện:** đang ghi lần hiệu chuẩn.
- **Luồng chính:**
  1. Sau khi insert `calibrations`, tìm lần hiệu chuẩn có `calibrated_at` lớn nhất của thiết bị.
  2. Set `equipments.next_due_date` = `next_due_date` của lần đó.
- **Luồng phụ / ngoại lệ:**
  - A1: ghi bổ sung một lần hiệu chuẩn cũ (calibrated_at < lần gần nhất hiện có) → KHÔNG ghi đè `equipments.next_due_date` (vẫn theo lần gần nhất).
- **Hậu điều kiện:** `equipments.next_due_date` nhất quán với lần hiệu chuẩn gần nhất.
- **Business Rules:** BR-EQP-006, BR-EQP-008.
- **Acceptance Criteria:**
  - AC1 (happy chuỗi): GIVEN thiết bị hiệu chuẩn lần 1 (2025-06, next_due=2026-06) rồi lần 2 (2026-06, next_due=2027-06) WHEN ghi lần 2 THEN `equipments.next_due_date`=2027-06.
  - AC2 (ghi bổ sung lần cũ): GIVEN thiết bị đã có lần gần nhất 2026-06 (next_due=2027-06) WHEN ghi bổ sung lần cũ 2024-06 THEN `equipments.next_due_date` vẫn = 2027-06 (BR-EQP-008).
- **Data cần thiết:** Equipment.next_due_date = MAX(calibrated_at)→next_due_date; transaction.
- **API cần:** nội bộ (hệ quả của FR-EQP-006).

---

### FR-EQP-009: Xem lịch sử hiệu chuẩn (timeline bất biến — §6.4/§8.4)

- **Mô tả:** Hiển thị **lịch sử hiệu chuẩn đầy đủ** của một thiết bị: timeline các lần hiệu chuẩn (ngày, provider, kết quả pass/fail, next_due_date, link tải CoC/cert, người ghi). Phục vụ truy vết khi đánh giá VILAS (§6.4 trạng thái hiệu chuẩn, §6.5 truy xuất nguồn gốc qua cert).
- **Độ ưu tiên:** P0
- **Actor:** Admin, staff (👁 — đọc theo OQ#2), leader (👁). Kế toán theo OQ#5.
- **Tiền điều kiện:** thiết bị tồn tại; user có quyền `equipment:read`.
- **Luồng chính:**
  1. User mở chi tiết thiết bị → tab "Lịch sử hiệu chuẩn".
  2. Hệ thống trả danh sách `calibrations` của thiết bị (sắp xếp giảm dần theo calibrated_at) kèm link tải CoC.
- **Luồng phụ / ngoại lệ:**
  - A1: thiết bị chưa có lần hiệu chuẩn nào → trả danh sách rỗng + (nếu chu kỳ NULL) "thiết bị không thuộc diện hiệu chuẩn".
- **Hậu điều kiện:** chỉ đọc.
- **Business Rules:** BR-EQP-007, BR-EQP-008.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN thiết bị có 3 lần hiệu chuẩn WHEN mở lịch sử THEN timeline hiển thị 3 lần (ngày, provider, kết quả, next_due, link CoC, người ghi) giảm dần theo ngày.
  - AC2 (truy vết cert): GIVEN một lần hiệu chuẩn có CoC WHEN tải CoC THEN file lấy lại đúng từ MinIO, audit `EQUIPMENT_ATTACH`/`CALIBRATION_DOWNLOAD`.
  - AC3 (rỗng): GIVEN thiết bị chưa hiệu chuẩn WHEN mở lịch sử THEN danh sách rỗng, hiển thị trạng thái phù hợp.
- **Data cần thiết:** list Calibration(equipment_id) + attachments(owner_type=calibration).
- **API cần:** "lấy lịch sử hiệu chuẩn của thiết bị", "tải giấy chứng nhận hiệu chuẩn".

---

### FR-EQP-010: Cảnh báo thiết bị quá hạn / không đạt hiệu chuẩn (badge — §6.4)

- **Mô tả:** Hệ thống tính **trạng thái cảnh báo (badge)** cho thiết bị: (a) **Quá hạn** nếu `equipments.next_due_date` < ngày hiện tại; (b) **Sắp tới hạn** nếu `next_due_date` còn ≤ 30 ngày; (c) **Không đạt** nếu kết quả lần hiệu chuẩn gần nhất `fail`. Badge hiển thị ở danh sách + chi tiết thiết bị; có **bộ lọc** theo trạng thái cảnh báo. Khuyến nghị "**không sử dụng cho thử nghiệm**" cho quá hạn/không đạt (tinh thần §6.4). **KHÔNG khóa cứng** (OQ#3 — bản đầu chỉ cảnh báo; khóa cứng/chặn luồng M1 → CR).
- **Độ ưu tiên:** P0
- **Actor:** mọi vai trò có `equipment:read` (hiển thị badge); tính toán = hệ thống.
- **Tiền điều kiện:** thiết bị có chu kỳ hiệu chuẩn (badge quá hạn/sắp hạn chỉ áp cho thiết bị diện hiệu chuẩn — BR-EQP-010).
- **Luồng chính:**
  1. Khi liệt kê/xem chi tiết thiết bị → hệ thống tính badge từ `next_due_date` (so với hôm nay) + kết quả lần hiệu chuẩn gần nhất.
  2. Hiển thị badge + (lọc) cho phép lọc "quá hạn / sắp tới hạn / không đạt".
- **Luồng phụ / ngoại lệ:**
  - A1: thiết bị chu kỳ NULL (không diện hiệu chuẩn) → KHÔNG có badge quá hạn/sắp hạn (BR-EQP-010); badge "không đạt" chỉ khi có lần hiệu chuẩn fail.
  - A2: thiết bị `status=retired` (ngưng sử dụng) → không cảnh báo quá hạn (OQ — default ẩn cảnh báo cho thiết bị đã ngưng/hỏng).
- **Hậu điều kiện:** trạng thái cảnh báo hiển thị nhất quán; KHÔNG chặn thao tác (CONSTRAINT-3).
- **Business Rules:** BR-EQP-009, BR-EQP-010.
- **Acceptance Criteria:**
  - AC1 (quá hạn): GIVEN thiết bị `next_due_date`=hôm qua WHEN liệt kê THEN badge "Quá hạn hiệu chuẩn — khuyến nghị không sử dụng".
  - AC2 (sắp tới hạn): GIVEN thiết bị `next_due_date` còn 20 ngày WHEN xem chi tiết THEN badge "Sắp tới hạn hiệu chuẩn (còn 20 ngày)".
  - AC3 (không đạt): GIVEN lần hiệu chuẩn gần nhất result=fail WHEN liệt kê THEN badge "Hiệu chuẩn KHÔNG ĐẠT — khuyến nghị không sử dụng".
  - AC4 (không khóa cứng): GIVEN thiết bị quá hạn WHEN staff thực hiện thao tác hợp lệ trên thiết bị (vd ghi hiệu chuẩn mới) THEN KHÔNG bị chặn vì lý do quá hạn (CONSTRAINT-3); ghi hiệu chuẩn mới pass → badge quá hạn biến mất.
  - AC5 (thiết bị không diện hiệu chuẩn): GIVEN thiết bị chu kỳ NULL WHEN liệt kê THEN KHÔNG có badge quá hạn/sắp hạn (BR-EQP-010).
- **Data cần thiết:** tính từ Equipment.next_due_date + Equipment.status + result lần hiệu chuẩn gần nhất; bộ lọc badge.
- **API cần:** badge tính trong "liệt kê/chi tiết thiết bị" (FR-EQP-004); bộ lọc trạng thái hiệu chuẩn.

---

### FR-EQP-011: CRON-5 — nhắc trước hiệu chuẩn (30/15/7 ngày, in-app) — R16

- **Mô tả:** Job nền **CRON-5** (R16, demo-scope mục D): hằng ngày 07:00, quét thiết bị diện hiệu chuẩn (chu kỳ ≠ NULL, status ∉ {retired}) có `next_due_date` còn **30 / 15 / 7 ngày** → tạo thông báo in-app (`notifications`) cho **người phụ trách thiết bị** (`responsible_user_id`) + **trưởng nhóm phòng** (`departments.lead_user_id`). Idempotent: mỗi thiết bị × mỗi mốc (30/15/7) chỉ gửi 1 lần (chống trùng). Chạy APScheduler trong app + Redis lock (CONSTRAINT-8). Chỉ in-app (C02).
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (scheduler).
- **Tiền điều kiện:** có thiết bị diện hiệu chuẩn với `next_due_date` trong các mốc.
- **Luồng chính:**
  1. 07:00 hằng ngày: lấy Redis lock CRON-5.
  2. Query thiết bị có `next_due_date - hôm nay` ∈ {30, 15, 7} ngày, chu kỳ ≠ NULL, status ∉ {retired}.
  3. Với mỗi thiết bị: kiểm tra chưa gửi cho (thiết bị, mốc) → tạo `notifications` type=`CALIBRATION_DUE` cho người phụ trách + trưởng nhóm (ref_type='equipment', ref_id=equipment.id).
  4. Ghi `audit_logs` action=`CRON_CALIBRATION_REMINDER` (số thông báo tạo).
- **Luồng phụ / ngoại lệ:**
  - A1: thiết bị không có người phụ trách → gửi cho trưởng nhóm phòng (BR-EQP-011); nếu cũng không có → log WARN.
  - A2: lock đang giữ (instance khác chạy) → bỏ qua (chống chạy trùng — CONSTRAINT-8).
  - A3: thiết bị `status=retired`/`broken` → KHÔNG nhắc (OQ — default bỏ qua retired; broken theo OQ).
- **Hậu điều kiện:** người phụ trách + trưởng nhóm nhận thông báo in-app; không trùng.
- **Business Rules:** BR-EQP-009, BR-EQP-010, BR-EQP-011.
- **Acceptance Criteria:**
  - AC1 (happy 30 ngày): GIVEN thiết bị `next_due_date` đúng còn 30 ngày, có người phụ trách + trưởng nhóm WHEN CRON-5 chạy THEN tạo notification `CALIBRATION_DUE` cho cả 2 (ref_id=equipment.id), audit ghi.
  - AC2 (idempotent): GIVEN CRON-5 đã gửi mốc 30 ngày cho thiết bị X WHEN chạy lại trong ngày / hôm sau (vẫn 30 ngày do lệch) THEN KHÔNG gửi trùng mốc 30 (BR-EQP-011).
  - AC3 (3 mốc): GIVEN thời gian trôi tới còn 15 ngày, rồi 7 ngày WHEN CRON-5 chạy các ngày tương ứng THEN gửi thêm thông báo mốc 15 và mốc 7 (mỗi mốc 1 lần).
  - AC4 (không người phụ trách): GIVEN thiết bị `responsible_user_id`=NULL WHEN CRON-5 THEN gửi cho trưởng nhóm phòng; nếu không có trưởng nhóm → log WARN, không lỗi job.
  - AC5 (bỏ qua không diện hiệu chuẩn): GIVEN thiết bị chu kỳ NULL hoặc status=retired WHEN CRON-5 THEN KHÔNG nhắc.
  - AC6 (lock): GIVEN 2 instance app WHEN CRON-5 trùng giờ THEN chỉ 1 instance chạy (Redis lock), không gửi trùng.
- **Data cần thiết:** query equipments(next_due_date, status, calibration_cycle, responsible_user_id, department_id→lead_user_id); notifications(user_id, type=CALIBRATION_DUE, ref_type=equipment, ref_id); bảng/cờ chống trùng mốc (vd notifications idempotency key hoặc cột `cal_reminder_sent` theo mốc — schema-designer chốt).
- **API cần:** nội bộ (scheduler); thông báo hiển thị qua API notifications của M7.

---

## 4. Business Rules

| ID | Quy tắc | Lý do nghiệp vụ | Hệ quả nếu vi phạm |
|----|---------|-----------------|--------------------|
| BR-EQP-001 | 1 thiết bị (`equipments`) có 0..n bản ghi hiệu chuẩn (`calibrations`); quan hệ 1-n | Tách hồ sơ thiết bị khỏi từng lần hiệu chuẩn (§6.4) | Bản ghi hiệu chuẩn mồ côi |
| BR-EQP-002 | Tình trạng thiết bị (`status`) ∈ {active (hoạt động), maintenance (bảo trì), broken (hỏng), retired (ngưng sử dụng)} | Phân loại trạng thái vận hành để lọc/báo cáo (§6.4) | 422 `INVALID_STATUS` |
| BR-EQP-003 | Tạo/sửa thiết bị & ghi hiệu chuẩn chỉ trong **phạm vi phòng ban** của user (staff); Admin mọi phòng. Leader chỉ xem (👁); Kế toán không truy cập (matrix — OQ#5) | Cách ly dữ liệu phòng ban (R13); RBAC matrix demo-scope dòng "Thiết bị — hiệu chuẩn" | 403 `FORBIDDEN` |
| BR-EQP-004 | Chu kỳ hiệu chuẩn: `calibration_cycle_value` > 0 (INT) + `calibration_cycle_unit` ∈ {month, year}; có thể NULL (thiết bị không diện hiệu chuẩn) | Chu kỳ định kỳ theo tháng/năm (đề bài); thiết bị không hiệu chuẩn không cần chu kỳ | 422 `INVALID_CALIBRATION_CYCLE` |
| BR-EQP-005 | `calibrated_at` (ngày hiệu chuẩn) KHÔNG được ở tương lai (≤ ngày hiện tại) | Hiệu chuẩn là sự kiện đã xảy ra (truy vết §6.5) | 422 `INVALID_CALIBRATION_DATE` |
| BR-EQP-006 | `next_due_date` = `calibrated_at` + chu kỳ thiết bị (`cycle_value` × `unit`); **tự tính** khi ghi lần hiệu chuẩn; cho phép override thủ công có lý do (OQ#1). Đổi chu kỳ KHÔNG hồi tố bản ghi cũ, chỉ áp lần tiếp theo | Đảm bảo ngày đến hạn nhất quán + truy xuất (§6.4 trạng thái hiệu chuẩn) | next_due sai → nhắc/cảnh báo sai thời điểm |
| BR-EQP-007 | Bản ghi `calibrations` **bất biến**: KHÔNG sửa/xóa sau khi tạo; không có endpoint PATCH/DELETE; đính chính = tạo bản ghi mới + audit | §8.4 kiểm soát hồ sơ — hồ sơ hiệu chuẩn là bằng chứng truy xuất nguồn gốc (VILAS) | 405/403 `IMMUTABLE_RECORD`; mất bằng chứng → vi phạm §8.4 |
| BR-EQP-008 | `equipments.next_due_date` luôn = `next_due_date` của lần hiệu chuẩn có `calibrated_at` GẦN NHẤT; ghi bổ sung lần cũ KHÔNG ghi đè | CRON-5 + cảnh báo + lọc dựa trên ngày đến hạn thực tế (lần gần nhất) | Nhắc/cảnh báo sai; 2 nguồn next_due mâu thuẫn |
| BR-EQP-009 | Thiết bị **quá hạn** (`next_due_date` < hôm nay) hoặc kết quả lần hiệu chuẩn gần nhất **`fail`** → cảnh báo (badge) "khuyến nghị không sử dụng"; **KHÔNG khóa cứng** thao tác/luồng (OQ#3) | §6.4 thiết bị phải được hiệu chuẩn — cảnh báo rõ để tránh dùng nhầm; không khóa cứng để linh hoạt vận hành (tinh thần "lô fail" M2) | Dùng nhầm thiết bị chưa hiệu chuẩn/không đạt → kết quả thử nghiệm không tin cậy |
| BR-EQP-010 | Chỉ thiết bị **diện hiệu chuẩn** (chu kỳ ≠ NULL) mới sinh nhắc CRON-5 + badge quá hạn/sắp hạn; thiết bị chu kỳ NULL hoặc `status=retired` KHÔNG nhắc/không badge quá hạn | Tránh nhắc nhiễu cho thiết bị không cần hiệu chuẩn / đã ngưng | Spam thông báo / cảnh báo sai |
| BR-EQP-011 | CRON-5 nhắc các mốc **30/15/7 ngày** trước `next_due_date`; gửi cho **người phụ trách** (`responsible_user_id`) + **trưởng nhóm phòng** (`departments.lead_user_id`); idempotent mỗi (thiết bị, mốc) gửi 1 lần; không người phụ trách → chỉ trưởng nhóm | R16 "nhắc trước thời gian hiệu chuẩn"; CRON-5 demo-scope; chống spam (C02) | Bỏ sót hạn hiệu chuẩn / spam thông báo |
| BR-EQP-012 | File đính kèm (tài liệu thiết bị + CoC/cert): chỉ loại cho phép (PDF, DOCX, XLSX, PNG, JPG — OQ; KHÔNG file thực thi/macro) validate MIME thực + đuôi + ≤ giới hạn dung lượng; lưu MinIO, không lưu binary trong DB | An toàn lưu trữ, tránh file độc hại (R2/R11, C01) | 422 `INVALID_FILE_TYPE` / `FILE_TOO_LARGE` |
| BR-EQP-013 | Người phụ trách (`responsible_user_id`) phải thuộc cùng phòng ban với thiết bị (bản đầu); Admin có thể gán linh hoạt hơn (OQ) | Người phụ trách thực tế quản thiết bị tại phòng; nhận CRON-5 đúng người | 422 `RESPONSIBLE_NOT_IN_DEPARTMENT` |
| BR-EQP-014 | `equipments.code` duy nhất toàn hệ thống, human-readable, **bất biến sau khi tạo**, không lộ ID tuần tự; `id` thật là UUID. Mọi tạo/sửa/xóa thiết bị + ghi hiệu chuẩn ghi `audit_logs` (§6.4/§8.4) | Mã thiết bị là định danh ổn định (§6.4 nhận biết thiết bị); không lộ tuần tự (rule api.md); audit duy trì VILAS | 422 `CODE_IMMUTABLE`; thiếu audit → vi phạm §8.4 |

---

## 5. Use Case chính

### UC-EQP-01: Tạo thiết bị + cấu hình chu kỳ hiệu chuẩn
- **Actor chính:** staff (phòng mình) / Admin.
- **Tiền điều kiện:** cần đưa một thiết bị mới vào quản lý.
- **Luồng:**
  1. Staff phòng Hóa tạo thiết bị (FR-001): tên "Máy đo pH", phòng=Hóa, người phụ trách=X, ngày mua, tình trạng=active → sinh `code`=`TB-HOA-007`.
  2. Cấu hình chu kỳ hiệu chuẩn (FR-005): 12 tháng.
  3. (Tùy) đính kèm hướng dẫn sử dụng (FR-004) lên MinIO.
  4. Audit `EQUIPMENT_CREATE` (+ `EQUIPMENT_UPDATE` chu kỳ, `EQUIPMENT_ATTACH`).
- **Ngoại lệ:** tạo cho phòng khác → 403; người phụ trách khác phòng → 422 `RESPONSIBLE_NOT_IN_DEPARTMENT`; leader gọi tạo → 403.
- **Hậu điều kiện:** thiết bị sẵn sàng để ghi hiệu chuẩn; `next_due_date`=NULL cho tới lần hiệu chuẩn đầu.
- **Liên kết FR:** FR-EQP-001, 003, 005, 004.

### UC-EQP-02: Ghi lần hiệu chuẩn + tự tính next_due (CỐT LÕI §6.4/§6.5)
- **Actor chính:** staff (thiết bị phòng mình) / Admin.
- **Tiền điều kiện:** thiết bị có chu kỳ hiệu chuẩn; provider đã hiệu chuẩn xong, có CoC.
- **Luồng:**
  1. Staff mở thiết bị `TB-HOA-007` → "Ghi hiệu chuẩn" (FR-006): ngày=2026-06-20, provider="Trung tâm Đo lường ABC", kết quả=pass, upload CoC.
  2. Hệ thống tính `next_due_date`=2027-06-20 (chu kỳ 12 tháng), lưu bản ghi (immutable), cập nhật `equipments.next_due_date`=2027-06-20 (FR-008), cập nhật cảnh báo (badge quá hạn cũ — nếu có — biến mất, FR-010).
  3. Audit `CALIBRATION_RECORD`; CoC lưu MinIO.
- **Ngoại lệ:** ngày tương lai → 422 `INVALID_CALIBRATION_DATE`; chưa cấu hình chu kỳ → 422 `CALIBRATION_CYCLE_REQUIRED`; CoC sai loại → 422 `INVALID_FILE_TYPE`; ghi cho thiết bị phòng khác → 403.
- **Biến thể (không đạt):** kết quả=fail → bản ghi tạo, thiết bị nhận badge "Hiệu chuẩn KHÔNG ĐẠT — khuyến nghị không sử dụng" (FR-010), không khóa cứng.
- **Hậu điều kiện:** lịch sử hiệu chuẩn cập nhật (bất biến); `next_due_date` + cảnh báo nhất quán.
- **Liên kết FR:** FR-EQP-006, 008, 010, 007.

### UC-EQP-03: CRON-5 nhắc trước hiệu chuẩn (R16)
- **Actor chính:** hệ thống (scheduler).
- **Tiền điều kiện:** có thiết bị diện hiệu chuẩn với `next_due_date` còn 30/15/7 ngày.
- **Luồng:**
  1. 07:00 hằng ngày, CRON-5 lấy Redis lock, quét thiết bị (chu kỳ ≠ NULL, status ∉ retired) có `next_due_date` còn 30/15/7 ngày (FR-011).
  2. Với mỗi thiết bị/mốc chưa nhắc → tạo notification `CALIBRATION_DUE` cho người phụ trách + trưởng nhóm phòng (idempotent — BR-EQP-011).
  3. Audit `CRON_CALIBRATION_REMINDER`.
- **Ngoại lệ:** không người phụ trách → chỉ trưởng nhóm (+ WARN nếu không có); lock đang giữ → bỏ qua; thiết bị retired/chu kỳ NULL → bỏ qua.
- **Hậu điều kiện:** người liên quan nhận thông báo in-app, không trùng; CRON-6 hóa chất chạy độc lập.
- **Liên kết FR:** FR-EQP-011, 008, 010.

### UC-EQP-04: Xử lý thiết bị quá hạn hiệu chuẩn
- **Actor chính:** người phụ trách / staff (phòng mình) / leader (👁 theo dõi).
- **Tiền điều kiện:** thiết bị có badge "Quá hạn hiệu chuẩn" (FR-010).
- **Luồng:**
  1. Người phụ trách thấy badge "Quá hạn" (qua danh sách lọc / CRON-5 / chi tiết) (FR-004/010).
  2. (Tùy) đổi tình trạng thiết bị → maintenance trong thời gian gửi hiệu chuẩn (FR-002).
  3. Gửi thiết bị đi hiệu chuẩn (ngoài hệ thống) → nhận CoC → ghi lần hiệu chuẩn mới (FR-006) → `next_due_date` cập nhật → **badge quá hạn biến mất** (nếu result=pass) (FR-010/008).
- **Ngoại lệ (không đạt):** kết quả=fail → badge "KHÔNG ĐẠT" giữ; khuyến nghị không dùng; lặp lại hiệu chuẩn/sửa chữa. Bản đầu KHÔNG khóa cứng luồng thử nghiệm (OQ#3 — khóa cứng = CR).
- **Hậu điều kiện:** thiết bị trở lại trạng thái hiệu chuẩn hợp lệ (nếu pass); lịch sử đầy đủ.
- **Liên kết FR:** FR-EQP-004, 010, 002, 006, 008.

---

## 6. Yêu cầu phi chức năng (NFR)

Theo template `~/.claude/rules/nfr.md`. Con số định cỡ cho quy mô **~40 user** (C03), môi trường staging tương đương production (Docker Compose, ~2–4 vCPU/8GB). Giả định cao điểm: ~5–10 concurrent users. Lượng dữ liệu giả định: ~2,000 thiết bị + ~20,000 bản ghi hiệu chuẩn.

```
NFR-PERF-EQP-001: Ghi hiệu chuẩn & cập nhật next_due/cảnh báo
────────────────────────────────────────────────────
Mô tả:     API ghi lần hiệu chuẩn (gồm tính next_due + cập nhật equipment +
           cảnh báo trong transaction) phản hồi đủ nhanh.
Metric:    P95 < 400ms | P99 < 700ms (không tính thời gian upload CoC)
Tool đo:   k6 (tests/performance/calibration-record.js)
Điều kiện: 10 concurrent users, 2,000 thiết bị / 20,000 bản ghi, staging
Pass:      p(95) < 400ms suốt 10 phút ở 10 concurrent users, error rate < 1%
Fail:      p(95) ≥ 400ms → review index (calibrations(equipment_id, calibrated_at),
           equipments(next_due_date))
Ưu tiên:  Must Have
```
```
NFR-PERF-EQP-002: Tìm kiếm / liệt kê thiết bị (gồm tính badge)
────────────────────────────────────────────────────
Metric:    P95 < 500ms cho danh sách phân trang 20/trang (lọc phòng/tình trạng/
           trạng thái hiệu chuẩn/từ khóa)
Tool đo:   k6 (tests/performance/equipment-search.js)
Điều kiện: 10 concurrent users, 2,000 thiết bị
Pass:      p(95) < 500ms; query dùng index (không Sequential Scan)
Fail:      p(95) ≥ 500ms → index (department_id, status, next_due_date) +
           GIN trgm cho name/code
Ưu tiên:  Should Have
```
```
NFR-CRON-EQP-001: CRON-5 nhắc hiệu chuẩn đúng & không trùng (Must)
────────────────────────────────────────────────────
Mô tả:     CRON-5 nhắc đúng thiết bị/mốc (30/15/7 ngày), gửi đúng người
           (phụ trách + trưởng nhóm), idempotent, có Redis lock chống chạy trùng.
Metric:    100% thiết bị diện hiệu chuẩn còn 30/15/7 ngày được nhắc đúng 1 lần/mốc;
           0 thông báo trùng; 0 nhắc thiết bị retired/chu kỳ NULL.
Tool đo:   Test cron với dataset giả lập các mốc + chạy lặp + kiểm tra notifications
Pass:      Đúng người + đúng mốc + không trùng; lock hoạt động với 2 instance
Fail:      Trùng/bỏ sót → fix idempotency key + Redis lock (BR-EQP-010/011)
Ưu tiên:  Must Have
```
```
NFR-INTEG-EQP-001: Toàn vẹn next_due & immutable hiệu chuẩn (VILAS §6.4/§8.4) (Must)
────────────────────────────────────────────────────
Mô tả:     equipments.next_due_date luôn khớp lần hiệu chuẩn gần nhất; bản ghi
           hiệu chuẩn bất biến (không sửa/xóa).
Metric:    Với toàn bộ thiết bị có ≥1 lần hiệu chuẩn: equipments.next_due_date =
           next_due_date của MAX(calibrated_at); 0 endpoint PATCH/DELETE calibrations.
Tool đo:   Invariant check (test + query) + rà route
Pass:      0 thiết bị lệch next_due; 0 route sửa/xóa bản ghi hiệu chuẩn
Fail:      Bất kỳ vi phạm → fix transaction FR-008 / chặn route (BR-EQP-007/008)
Ưu tiên:  Must Have
```
```
NFR-AUDIT-EQP-001: Đầy đủ & bất biến audit (VILAS §6.4/§8.4) (Must)
────────────────────────────────────────────────────
Mô tả:     Mọi tạo/sửa/xóa thiết bị + ghi hiệu chuẩn + đính kèm/tải file ghi
           audit_logs với correlation_id; bản ghi hiệu chuẩn không bị sửa/xóa.
Metric:    100% thao tác ghi có bản ghi audit_logs; 0 endpoint mutate/delete
           bản ghi hiệu chuẩn đã tạo.
Tool đo:   Test đếm audit/thao tác + rà route
Pass:      Tỷ lệ audit/thao tác = 100%; calibrations immutable
Fail:      < 100% hoặc tồn tại route sửa/xóa bản ghi hiệu chuẩn → block (§8.4)
Ưu tiên:  Must Have
```
```
NFR-SEC-EQP-001: Phân quyền RBAC + phạm vi phòng ban (Must)
────────────────────────────────────────────────────
Mô tả:     Enforce RBAC + phạm vi phòng ban ở tầng API (không chỉ FE); staff chỉ
           ghi thiết bị/hiệu chuẩn phòng mình; leader chỉ xem; Kế toán theo OQ#5
           (default không truy cập); người phụ trách thuộc phòng thiết bị.
Metric:    Ma trận test 4 vai trò × action M5 pass 100%; leader 403 ở 100% endpoint
           ghi; staff 403 khi ghi thiết bị phòng khác; 0 truy cập trái phép.
Tool đo:   Test RBAC tự động (security-auditor) + manual
Pass:      0 truy cập/ghi trái phép; 0 leader ghi; staff không ghi phòng khác
Fail:      Bất kỳ bypass → block go-live (OWASP A01)
Ưu tiên:  Must Have
```
```
NFR-SEC-EQP-002: An toàn upload/lưu file (tài liệu + CoC/cert) (Must)
────────────────────────────────────────────────────
Metric:    Chỉ chấp nhận loại file whitelist (PDF/DOCX/XLSX/PNG/JPG — OQ; KHÔNG
           file thực thi/macro) validate MIME thực + đuôi, ≤ giới hạn dung lượng;
           lưu MinIO, không lưu binary trong DB; tải qua presigned URL kiểm soát quyền.
Tool đo:   Test upload file độc hại/sai loại/quá lớn + kiểm tra access control URL
Pass:      File sai loại/quá lớn bị 422; file hợp lệ tải lại đúng; URL không bypass quyền
Ưu tiên:  Must Have
```
```
NFR-MAINT-EQP-001: Test coverage domain thiết bị/hiệu chuẩn (Must)
────────────────────────────────────────────────────
Metric:    Service tính next_due / cập nhật next_due theo lần gần nhất / tính badge
           cảnh báo / immutable hiệu chuẩn / RBAC scope / CRON-5 idempotent
           coverage ≥ 85%; module M5 overall ≥ 70%.
Tool đo:   pytest --cov
Pass:      ≥ 85% domain, ≥ 70% module; CI block nếu drop > 5%
Ưu tiên:  Must Have
```
```
NFR-OBS-EQP-001: Logging & truy vết (Should)
────────────────────────────────────────────────────
Metric:    Mọi request M5 có correlation_id xuyên FE→BE→audit_logs; ghi hiệu chuẩn/
           cấu hình chu kỳ ghi log INFO; ghi sai (ngày tương lai, thiếu chu kỳ,
           sửa bản ghi immutable) ghi WARN; lỗi MinIO/transaction ghi ERROR kèm
           stack (không lộ ra client); CRON-5 ghi INFO (số thông báo) + WARN
           (thiết bị không người nhận).
Tool đo:   Rà log + test
Pass:      Trace được 1 thiết bị/lần hiệu chuẩn từ log FE → audit DB qua correlation_id
Ưu tiên:  Should Have
```

---

## 7. Giả định & Ràng buộc (tổng hợp)

**Assumptions:** xem §2.5 (ASSUMPTION-1..6).

**Constraints:** xem §2.4 (CONSTRAINT-1..10).

**Ghi chú cấu trúc dữ liệu cho `schema-designer`** (mức logic — DDL chi tiết thuộc `/contract`):
- **`equipments`:** `id UUID PK`, `code VARCHAR UNIQUE NOT NULL` (bất biến — BR-EQP-014), `name VARCHAR NOT NULL`, `location VARCHAR NULL`, `department_id FK→departments NOT NULL`, `responsible_user_id FK→users NULL`, `purchase_date DATE NULL`, `status VARCHAR` CHECK(active|maintenance|broken|retired) default `active`, `calibration_cycle_value INT NULL` CHECK(>0), `calibration_cycle_unit VARCHAR NULL` CHECK(month|year), `next_due_date DATE NULL` (denormalize = next_due của lần hiệu chuẩn gần nhất — BR-EQP-008), `created_by/updated_by FK→users`, `created_at/updated_at`, `deleted_at NULL` (soft-delete). `next_due_date` luôn khớp MAX(calibrated_at) (NFR-INTEG-EQP-001).
- **`calibrations` (BẤT BIẾN — §8.4):** `id UUID PK`, `equipment_id FK→equipments NOT NULL`, `calibrated_at DATE NOT NULL` (≤ today — BR-EQP-005), `provider VARCHAR NULL` (text bản đầu — OQ#4), `result VARCHAR NOT NULL` CHECK(pass|fail), `next_due_date DATE NOT NULL` (tự tính BR-EQP-006), `created_by FK→users NOT NULL`, `created_at TIMESTAMPTZ`, (tùy) `correction_of UUID FK→calibrations NULL` (đính chính). **KHÔNG cột mutable nghiệp vụ; KHÔNG route PATCH/DELETE** (BR-EQP-007). CoC/cert gắn qua `attachments` (owner_type='calibration', owner_id=calibration.id). Cân nhắc trigger DB chặn UPDATE/DELETE (đồng bộ audit_logs append-only M7) để enforce immutable mạnh hơn app-only.
- **`attachments` (dùng chung M7):** owner_type ∈ {`equipment` (tài liệu thiết bị), `calibration` (CoC/cert)} — whitelist đã có (08-contract-m7-schema dòng 293). M5 KHÔNG tạo bảng file riêng.
- **`notifications` (dùng chung M7):** CRON-5 INSERT type=`CALIBRATION_DUE`, ref_type='equipment', ref_id=equipment.id (08-contract-m7-schema dòng 335). Cần cơ chế **chống trùng mốc** (idempotency): hoặc unique index trên (user_id, type, ref_id, mốc) hoặc cột riêng theo dõi mốc đã nhắc — schema-designer chốt (BR-EQP-011).
- **Trưởng nhóm (phụ thuộc M7):** đọc `departments.lead_user_id` để gửi CRON-5 (BR-EQP-011); đã có ở M7. M5 KHÔNG tạo cột trưởng nhóm mới.
- **`roles_permissions` (M7 — cần seed cho M5):** `equipment:read` (admin/leader/staff scope all hoặc department theo OQ#2; accountant theo OQ#5), `equipment:create`/`equipment:update` (staff scope department, admin all; leader KHÔNG), `calibration:create` (staff scope department, admin all; leader KHÔNG). Phù hợp BR-EQP-003. **Lưu ý:** matrix demo-scope cho leader = 👁 (chỉ xem) ở M5 — KHÁC M3 (leader ghi được) → seed quyền M5 phải phản ánh đúng.
- **Index gợi ý:** `equipments(code)` unique, `equipments(department_id, status)`, `equipments(next_due_date)` (CRON-5 + lọc quá hạn/sắp hạn), `equipments(responsible_user_id)`, GIN trgm `equipments(name)`/`equipments(code)`; `calibrations(equipment_id, calibrated_at DESC)` (lịch sử + lấy lần gần nhất), `calibrations(equipment_id, result)`.
- **Tính badge cảnh báo (FR-010):** tính từ `equipments.next_due_date` so với CURRENT_DATE + `result` lần hiệu chuẩn gần nhất; có thể tính runtime (query nhẹ với index) hoặc denormalize cờ — schema-designer/api-designer chốt (bản đầu runtime đủ cho 2,000 thiết bị).
- **CRON-5:** APScheduler trong app, 07:00 hằng ngày, Redis lock (đồng bộ CRON-1..6); chỉ in-app (C02).
- **Soft-delete:** thiết bị KHÔNG hard-delete nếu đã có lần hiệu chuẩn (giữ hồ sơ §8.4 — đồng bộ tinh thần BR M3); dùng `status=retired` hoặc soft-delete + audit.

---

## 8. OPEN QUESTIONS (cần KH trả lời — phần lớn KHÔNG chặn `/contract`)

| # | Câu hỏi | Tại sao cần biết | Ảnh hưởng nếu chưa rõ (default đề xuất) | Người trả lời | Deadline | Chặn contract? |
|---|---------|------------------|------------------------------------------|---------------|----------|----------------|
| 1 | **Chu kỳ hiệu chuẩn cố định toàn hệ thống hay theo từng thiết bị/loại?** + `next_due_date` tự tính hay cho nhập tay theo cert? | Tính next_due (FR-006/008, BR-EQP-006) | Default: **chu kỳ lưu trên TỪNG thiết bị** (tháng/năm); next_due **tự tính** = calibrated_at + chu kỳ, **cho override** thủ công có lý do + audit nếu cert ghi khác | Trưởng phòng QA/Quản lý chất lượng | Trước `/contract` (ưu tiên) | ⚠️ **Nên chốt** — ảnh hưởng logic tính next_due lõi (default an toàn) |
| 2 | **Phạm vi XEM thiết bị của staff:** chỉ thiết bị phòng mình hay xem toàn lab (đọc)? | RBAC đọc (FR-004/009, BR-EQP-003) | Default: staff **xem toàn lab** (đọc, `equipment:read` scope all), **ghi chỉ phòng mình**. Nếu KH muốn xem chỉ phòng mình → scope department | Ban lãnh đạo | Trước `/contract` | ⚠️ **Nên chốt** — ảnh hưởng scope quyền đọc (default xem toàn lab) |
| 3 | **Thiết bị quá hạn / không đạt: chỉ CẢNH BÁO hay KHÓA CỨNG?** (chặn ghi thao tác / chặn dùng cho mẫu ở M1) | Chính sách cảnh báo (FR-010, BR-EQP-009, CONSTRAINT-3) | Default: **chỉ cảnh báo (badge) + khuyến nghị**, KHÔNG khóa cứng (tinh thần "lô fail" M2). Khóa cứng / chặn luồng M1 → **CR** | Ban lãnh đạo + QA | Trước `/contract` (ưu tiên) | ⚠️ **Nên chốt** — ảnh hưởng nghiệp vụ §6.4 (mặc định cảnh báo, an toàn vận hành; khóa cứng = CR) |
| 4 | **Provider (đơn vị hiệu chuẩn) lưu text tự do hay cần DANH MỤC provider riêng?** + CoC/cert có **bắt buộc** khi kết quả pass không? | Ghi hiệu chuẩn (FR-006) | Default: provider **text tự do** bản đầu (danh mục → mở rộng sau/CR); CoC **khuyến nghị bắt buộc khi pass** (xác nhận với KH) | Quản lý chất lượng | Khi UAT | **Không** — biến thể có default (danh mục provider = mở rộng/CR) |
| 5 | **Kế toán có XEM thiết bị (👁) không?** (matrix demo-scope ghi "—" = không truy cập; nhưng yêu cầu nêu "accountant xem 👁 KHÔNG quản lý" → mâu thuẫn cần chốt) | RBAC Kế toán (BR-EQP-003, §2.3) | Default theo **matrix = Kế toán KHÔNG truy cập M5** (an toàn). Nếu KH xác nhận "Kế toán xem 👁" → cấp `equipment:read` chỉ xem (không ghi) | Ban lãnh đạo | Trước `/contract` | ⚠️ **Nên chốt** — sửa mâu thuẫn matrix vs đề bài (default theo matrix) |

> **Kết luận:** #4 là biến thể cấu hình có default rõ → KHÔNG chặn `/contract`. **#1 (chu kỳ + tự tính next_due), #2 (phạm vi xem staff), #3 (cảnh báo hay khóa cứng), #5 (Kế toán xem/không xem — mâu thuẫn matrix)** NÊN chốt với KH trước `/contract` vì ảnh hưởng **logic tính next_due lõi (#1)**, **RBAC đọc/quyền (#2/#5)**, **nghiệp vụ §6.4 cảnh báo/khóa (#3)**. Tất cả đã có **default an toàn**, có thể vào contract với default nếu KH chưa kịp chốt, nhưng mọi thay đổi default sau đó phải có văn bản xác nhận KH ("Verbal is Nothing").

---

## 9. Ma trận truy vết (Traceability Matrix)

| FR ID | Yêu cầu gốc (meeting note) | Submodule (demo-scope) | Điều khoản 17025 | Business Rule | Test Case (QA sẽ tạo) | Trạng thái |
|-------|----------------------------|------------------------|------------------|---------------|------------------------|------------|
| FR-EQP-001 | (danh mục thiết bị §6.4) | F5.1.1 | §6.4 | BR-001, 002, 003, 013, 014 | TC-EQP-001..006 | Draft |
| FR-EQP-002 | (sửa thiết bị/tình trạng) | F5.1.1 | §6.4, §8.4 | BR-002, 003, 006, 014 | TC-EQP-007..011 | Draft |
| FR-EQP-003 | (không lộ ID — rule api) | F5.1.1 | §6.4 | BR-014 | TC-EQP-012..014 | Draft |
| FR-EQP-004 | **R2 (kèm file), R11 (object storage)** | F5.1.1 | §6.4 | BR-003, 009, 012 | TC-EQP-015..021 | Draft |
| FR-EQP-005 | (lịch hiệu chuẩn định kỳ) | F5.2.1 | **§6.4** | BR-004, 006 | TC-EQP-022..025 | Draft |
| FR-EQP-006 | **R16 (hiệu chuẩn), R2 (CoC)** | F5.2.1 | **§6.4, §6.5** | BR-003, 005, 006, 007, 008, 009, 012 | TC-EQP-026..035 | Draft |
| FR-EQP-007 | (hồ sơ hiệu chuẩn bất biến) | F5.2.1 | **§8.4** | BR-007 | TC-EQP-036..039 | Draft |
| FR-EQP-008 | (tự tính next_due) | F5.2.1 | §6.4 | BR-006, 008 | TC-EQP-040..043 | Draft |
| FR-EQP-009 | **R16, R2 (lịch sử + cert §6.5)** | F5.2.1 | **§6.4, §6.5, §8.4** | BR-007, 008 | TC-EQP-044..047 | Draft |
| FR-EQP-010 | (cảnh báo quá hạn §6.4) | F5.2.1, F5.2.2 | **§6.4** | BR-009, 010 | TC-EQP-048..053 | Draft |
| FR-EQP-011 | **R16 ("vlab" — nhắc trước hiệu chuẩn), CRON-5** | F5.2.2 | **§6.4** | BR-009, 010, 011 | TC-EQP-054..060 | Draft |

**Mapping điều khoản ISO/IEC 17025 (demo-scope mục E):**
- **§6.4 Thiết bị** (cốt lõi M5): nhận biết & hồ sơ thiết bị (FR-001/002/003/004 — mã, tình trạng, người phụ trách, tài liệu); trạng thái hiệu chuẩn & ngăn sử dụng thiết bị không phù hợp (FR-010 cảnh báo quá hạn/không đạt + FR-011 nhắc trước); hiệu chuẩn định kỳ (FR-005/006/008 chu kỳ + next_due).
- **§6.5 Liên kết chuẩn đo lường**: hiệu chuẩn có truy xuất nguồn gốc qua **giấy chứng nhận CoC/cert** (FR-006 đính kèm cert, FR-009 lịch sử + tải cert).
- **§8.4 Kiểm soát hồ sơ**: bản ghi hiệu chuẩn **bất biến** (FR-007, BR-EQP-007, NFR-AUDIT-EQP-001 / NFR-INTEG-EQP-001); audit đầy đủ mọi thao tác (BR-EQP-014); giữ hồ sơ hiệu chuẩn không xóa.

**Liên kết liên module:**
- **M7 (nền tảng):** `users`/`departments`/`attachments`/`audit_logs`/`notifications` dùng chung; `departments.lead_user_id` → CRON-5 (BR-EQP-011); `attachments.owner_type` ∈ {equipment, calibration} đã whitelist; quyền `equipment:*`/`calibration:*` cần seed `roles_permissions` (leader = 👁 chỉ xem, KHÁC M3).
- **CRON-5 (M7.5 + APScheduler):** in-app `notifications` type=`CALIBRATION_DUE` (R16; chạy độc lập CRON-6 hóa chất).
- **M6 (Báo cáo):** dashboard số thiết bị theo tình trạng + số thiết bị quá hạn hiệu chuẩn (từ `equipments.next_due_date`/status).
- **M1 (Mẫu):** bản đầu CHƯA ràng buộc cứng "mẫu dùng thiết bị quá hạn" (chỉ cảnh báo M5 — §1.2 OUT-OF-SCOPE, OQ#3).

---

*Hết SRS M5 (v1.0). 11 FR · 14 BR · 4 UC · 9 NFR · 5 OPEN QUESTIONS. Tự tính next_due (calibrated_at + chu kỳ) + bản ghi hiệu chuẩn bất biến (§8.4) + CRON-5 nhắc 30/15/7 ngày in-app (R16) + cảnh báo quá hạn/không đạt (badge, không khóa cứng — §6.4) + lưu CoC/cert lên MinIO (§6.5) đã đặc tả đầy đủ, kiểm thử được. 4 OPEN QUESTIONS NÊN chốt trước `/contract` (#1 chu kỳ + tự tính next_due, #2 phạm vi xem staff, #3 cảnh báo hay khóa cứng, #5 Kế toán xem/không xem — mâu thuẫn matrix vs đề bài) vì ảnh hưởng logic next_due + RBAC + nghiệp vụ §6.4 — đều có default an toàn. Mọi xác nhận tiếp theo phải bằng văn bản theo rule "Verbal is Nothing".*
