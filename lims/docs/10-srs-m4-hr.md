# SRS: M4 — Nhân sự & Thành tích NCKH (HR & Research Achievement)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M4 — Nhân sự & Thành tích NCKH
**Version:** 1.0 | **Ngày:** 20/06/2026 | **Author:** BA agent
**Status:** DRAFT — bối cảnh đã chốt (4 vai trò, RBAC field-level lương, chu kỳ nâng lương 3 năm cố định C04, in-app only C02, ~40 user C03). Còn 9 OPEN QUESTIONS (§8) cần KH chốt trước/khi `/contract` — phần lớn là tham số nghiệp vụ/danh mục, không chặn ERD lõi.
**Nguồn:** `00-meeting-note-analysis.md` (R12, R17, R18, R19, R20; quyết định chốt C02/C03/C04, B03), `01-demo-scope.md` (M4.1–M4.3, RBAC matrix mục B, ERD core M4 mục C, CRON-3/CRON-4 mục D, mapping 17025 §6.2 mục E), `08-contract-m7-schema.md` (users/departments/audit_logs/notifications/attachments dùng chung; `hr_profiles.user_id` FK→users; quyền `hr:read`/`hr:manage`/`research:manage` đã seed)
**Chuẩn:** IEEE 830 (rút gọn) · ISO/IEC 17025:2017 §6.2 (nhân sự, năng lực, ủy quyền), §8.4 (kiểm soát hồ sơ)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| 1.0 | 20/06/2026 | Bản DRAFT đầu tiên — 20 FR, 24 BR, 6 UC, 13 NFR, 9 OPEN QUESTIONS. Đồng bộ phong cách SRS M1/M2; field-level RBAC lương theo cùng pattern strip cột giá của M2 (BR-CHEM-022). |

---

## 1. Giới thiệu

### 1.1 Mục đích

Tài liệu này đặc tả đầy đủ, không mơ hồ, kiểm thử được cho **Module M4 — Nhân sự & Thành tích NCKH** của hệ thống LIMS. Mục tiêu nghiệp vụ:

1. **Số hóa hồ sơ nhân sự** (gắn `user_id` của M7): thông tin cá nhân, phòng ban, chức danh, hợp đồng lao động, chu kỳ nâng lương — thay sổ tay/Excel rời rạc, **nhắc tự động** tới hạn nâng lương và hết hạn hợp đồng (R12, CRON-3/CRON-4).
2. **Hồ sơ năng lực nhân sự (17025 §6.2):** bằng cấp, chứng chỉ, ủy quyền thử nghiệm — bằng chứng năng lực để duy trì công nhận VILAS; kiểm soát thay đổi có audit (§8.4).
3. **Quản lý thành tích NCKH** (R17–R20): đề tài, bài báo, sáng chế/giải pháp hữu ích (gắn cá nhân/tập thể/phòng), hướng dẫn sinh viên, lượt SV đăng ký vào lab, môn học giảng dạy, phục vụ cộng đồng; **thống kê/tổng hợp năng lực** theo cá nhân/phòng/khoảng thời gian phục vụ báo cáo §6.2.

Tài liệu dùng cho 2 đối tượng:
- **Khách hàng / Ban lãnh đạo lab + Kế toán:** xác nhận nghiệp vụ đúng — đặc biệt **ai được xem/sửa lương & hợp đồng**, **chu kỳ nâng lương**, **danh mục cấp đề tài / chỉ số bài báo**.
- **Đội thiết kế (`schema-designer`, `api-designer`, `ux-designer`) và `feature-builder`:** đủ chi tiết để viết contract và implement mà không phải hỏi lại.

### 1.2 Phạm vi

Module M4 phủ 3 submodule (theo `01-demo-scope.md`):

| Submodule | Nội dung | Trong SRS này |
|-----------|----------|---------------|
| M4.1 Hồ sơ nhân sự | CRUD hồ sơ nhân sự (gắn `user_id`); ngày ký HĐ + loại HĐ + ngày hết hạn HĐ; chu kỳ nâng lương (mặc định 3 năm, cấu hình được) + ngày nâng lương gần nhất/kế tiếp (tự tính); hồ sơ năng lực (bằng cấp, chứng chỉ, ủy quyền thử nghiệm — §6.2) | ✅ FR-HR-001..007 |
| M4.2 Cron nhắc nhân sự | CRON-3 nhắc tới hạn nâng lương (15/7/3 ngày, in-app, gửi HR + lãnh đạo + chính nhân sự); CRON-4 nhắc hết hạn HĐ (30/15/7 ngày, in-app) | ✅ FR-HR-008..009 |
| M4.3 Thành tích NCKH | Đề tài NCKH (lead + thành viên n-n); bài báo (đồng tác giả + thứ tự); sáng chế/giải pháp hữu ích; gắn thành tích cá nhân/tập thể/phòng; hướng dẫn SV; lượt SV đăng ký lab; môn học giảng dạy; phục vụ cộng đồng; thống kê/tổng hợp năng lực | ✅ FR-HR-010..020 |

**Trong scope `[SCOPE]`:**
- CRUD **hồ sơ nhân sự** (`hr_profiles`) gắn 1-1 với `users` của M7: chức danh, ngày vào làm, hợp đồng (ngày ký, loại, ngày hết hạn), chu kỳ nâng lương (`salary_cycle_years`, mặc định 3), ngày nâng lương gần nhất (`last_salary_raise_date`), **ngày nâng lương kế tiếp (`next_salary_raise_date`) TỰ TÍNH** (BR-HR-005).
- **Lương (mức lương / bậc lương / hệ số):** trường tài chính — **RBAC field-level**: chỉ admin/leader/accountant xem; staff chỉ xem hồ sơ + thành tích **của chính mình**, KHÔNG xem lương người khác, KHÔNG xem lương người khác cùng phòng (B03 — Kế toán quản lý tài chính nhân sự).
- **Hồ sơ năng lực (§6.2):** bằng cấp, chứng chỉ (kèm ngày cấp/hết hạn, đính kèm bản scan qua `attachments`), **ủy quyền thử nghiệm** (authorization: được ủy quyền thực hiện chỉ tiêu/phương pháp nào, hiệu lực từ–đến) — bằng chứng năng lực VILAS.
- **CRON-3 / CRON-4:** nhắc in-app tới hạn nâng lương (mốc 15/7/3 ngày) và hết hạn hợp đồng (mốc 30/15/7 ngày); chống trùng theo bản ghi × mốc × ngày.
- **Thành tích NCKH:** đề tài NCKH (tên, **chủ nhiệm = lead**, **thành viên n-n**, cấp đề tài, thời gian, phòng, trạng thái); bài báo (tên, tạp chí, năm, DOI, chỉ số ISI/Scopus..., **đồng tác giả n-n + thứ tự tác giả**); bằng sáng chế / giải pháp hữu ích; **gắn thành tích cho cá nhân / tập thể (nhóm) / phòng thí nghiệm**; hướng dẫn SV (tên SV, đề tài, năm, loại khóa luận/luận văn...); lượt SV đăng ký vào lab (người đăng ký, người hướng dẫn, thời gian, mục đích); môn học phụ trách (tên môn, học kỳ, năm); phục vụ cộng đồng (nội dung, thời gian, người thực hiện, host).
- **Thống kê/tổng hợp thành tích** theo cá nhân / phòng / khoảng thời gian (phục vụ báo cáo năng lực §6.2) + xuất Excel/PDF.
- **Audit log mọi thay đổi** hồ sơ nhân sự / năng lực / lương / hợp đồng / thành tích (VILAS §6.2 + §8.4 — hồ sơ năng lực phải kiểm soát).
- Đính kèm file (bằng cấp, chứng chỉ, quyết định nâng lương, hợp đồng scan) qua bảng `attachments` polymorphic chung (`owner_type='hr_profile'`/`'publication'`).

**Ngoài scope `[OUT-OF-SCOPE → cần CR]`:**
- **Tính lương / bảng lương / payroll** (tính thực lĩnh, thuế TNCN, BHXH, phụ cấp, thưởng): M4 chỉ **lưu mức lương hiện tại + lịch sử nâng lương + nhắc tới hạn**, KHÔNG tính bảng lương. Payroll → CR.
- **Chấm công / nghỉ phép / OT (timesheet & leave management):** ngoài scope bản đầu → CR.
- **Tuyển dụng / onboarding workflow / đánh giá KPI:** ngoài scope → CR.
- **Tự động phê duyệt nâng lương / sinh quyết định nâng lương:** M4 chỉ NHẮC tới hạn; quyết định nâng lương thực tế do người có quyền nhập tay (cập nhật `last_salary_raise_date` + mức lương mới). Workflow duyệt nâng lương đa cấp → CR.
- **Thông báo qua email / Zalo:** chỉ in-app (C02). Email/Zalo → CR.
- **Tích hợp HRM/ERP ngoài, đồng bộ SSO với hệ thống trường:** ngoài scope → CR.
- **Đồng bộ tự động dữ liệu NCKH từ Scopus/Web of Science/CSDL trường:** M4 nhập tay/ import file; crawl/ API ngoài → CR.
- **Quản lý đề tài NCKH ở mức quản lý ngân sách/giải ngân/nghiệm thu chi tiết:** M4 chỉ lưu **thành tích** (metadata đề tài để thống kê năng lực), KHÔNG quản lý tài chính đề tài → CR.

### 1.3 Định nghĩa, từ viết tắt và thuật ngữ

| Thuật ngữ | Định nghĩa |
|-----------|------------|
| **Hồ sơ nhân sự (HR profile)** | Bản ghi mở rộng thông tin nhân sự của một `users`, quan hệ **1-1** với `users` (`hr_profiles.user_id` PK/FK → `users.id`). Chứa chức danh, ngày vào làm, hợp đồng, chu kỳ nâng lương, mức lương. M4 KHÔNG tạo bảng người dùng mới — dùng `users` của M7. |
| **Hợp đồng lao động (Contract)** | Thông tin hợp đồng của nhân sự: `contract_signed_date` (ngày ký), `contract_type` (loại HĐ — danh mục, xem OQ#3), `contract_end_date` (ngày hết hạn, NULL nếu HĐ không xác định thời hạn). (R12) |
| **Chu kỳ nâng lương (`salary_cycle_years`)** | Số năm giữa 2 lần nâng lương. Mặc định **3 năm** cho mọi ngạch (C04 đã chốt), nhưng **cấu hình được** ở từng hồ sơ (cho ngoại lệ — OQ#4). |
| **Ngày nâng lương gần nhất (`last_salary_raise_date`)** | Ngày nâng lương được thực hiện gần đây nhất. NULL nếu chưa từng nâng. |
| **Ngày nâng lương kế tiếp (`next_salary_raise_date`)** | Mốc tới hạn nâng lương tiếp theo, **TỰ TÍNH** = (`last_salary_raise_date` nếu có, ngược lại `contract_signed_date`) + `salary_cycle_years` năm (BR-HR-005). Là mốc CRON-3 dùng để nhắc. |
| **Mức lương (Salary)** | Trường tài chính của hồ sơ (mức lương/bậc/hệ số — xem OQ#2 về cấu trúc). **Field-level RBAC:** chỉ admin/leader/accountant xem; staff chỉ xem của chính mình (BR-HR-002, BR-HR-003). |
| **Trường tài chính (Financial field)** | Tập trường gồm: mức lương/bậc/hệ số + lịch sử nâng lương (giá trị tiền). Bị **strip khỏi response API** cho staff khi xem người khác — giống cách M2 strip cột giá khỏi KTV (BR-CHEM-022). |
| **Hồ sơ năng lực (Competence record)** | Bằng chứng năng lực nhân sự theo 17025 §6.2: bằng cấp, chứng chỉ, **ủy quyền thử nghiệm**. |
| **Ủy quyền thử nghiệm (Test authorization)** | Bản ghi nhân sự được **ủy quyền thực hiện một chỉ tiêu/phương pháp thử nghiệm** cụ thể, có hiệu lực từ–đến, người ủy quyền. Là yêu cầu §6.2 ("ủy quyền nhân sự thực hiện hoạt động phòng thí nghiệm"). |
| **Đề tài NCKH (Research project)** | Một công trình nghiên cứu: tên, **chủ nhiệm (lead)**, **thành viên (n-n)**, **cấp đề tài** (trường/bộ/nhà nước... — danh mục, OQ#5), thời gian (từ–đến), phòng, trạng thái. (R17) |
| **Chủ nhiệm đề tài (Lead)** | Người chịu trách nhiệm chính của đề tài (`research_projects.lead_user_id`). Một đề tài có đúng 1 chủ nhiệm; chủ nhiệm cũng là 1 thành viên. |
| **Thành viên đề tài (Project member)** | Quan hệ **n-n** giữa đề tài và nhân sự (`project_members`): một đề tài nhiều thành viên, một người tham gia nhiều đề tài; mỗi quan hệ có `role_in_project` (chủ nhiệm/thành viên/thư ký...). |
| **Bài báo khoa học (Publication — paper)** | Công bố khoa học: tên, tạp chí/hội nghị, năm, DOI, **chỉ số** (ISI/Scopus/SCIE/ESCI/trong nước... — danh mục, OQ#6), **đồng tác giả (n-n) + thứ tự tác giả** (`author_order`). (R17) |
| **Sáng chế / giải pháp hữu ích (Patent / utility solution)** | Loại `publication` với `type='patent'`: tên, số bằng, năm cấp, cơ quan cấp. (R17) |
| **Đồng tác giả + thứ tự (`publication_authors`, `author_order`)** | Quan hệ **n-n** giữa bài báo và nhân sự; `author_order` = thứ tự tác giả (1 = tác giả chính/đầu); hỗ trợ đánh dấu tác giả liên hệ (corresponding). |
| **Gắn thành tích cá nhân / tập thể / phòng** | Một thành tích có thể quy cho: cá nhân (qua quan hệ tác giả/thành viên), tập thể (nhóm thành viên), hoặc **phòng thí nghiệm** (`department_id`). Thống kê tổng hợp được theo cả 3 chiều (R17). |
| **Hướng dẫn sinh viên (Student mentorship)** | Bản ghi nhân sự hướng dẫn SV: tên SV, đề tài, năm, **loại** (khóa luận/luận văn/luận án/NCKH SV... — danh mục, OQ#7). (R18) |
| **Lượt SV đăng ký vào lab (Lab registration)** | Bản ghi SV đăng ký vào lab để thực tập / dùng thiết bị: người đăng ký (SV), người hướng dẫn (nhân sự), thời gian, mục đích. Có thể cần duyệt (OQ#8). (R18) |
| **Môn học giảng dạy (Teaching course)** | Bản ghi nhân sự phụ trách giảng dạy một môn: tên môn, học kỳ, năm. (R19) |
| **Phục vụ cộng đồng (Community service)** | Hoạt động phục vụ cộng đồng: nội dung, thời gian thực hiện, người thực hiện, **host** (đơn vị/tổ chức chủ trì). (R20) |
| **VILAS** | Hệ thống công nhận phòng thí nghiệm Việt Nam (theo ISO/IEC 17025). |
| **Audit log** | Bản ghi bất biến trong `audit_logs` (M7): ai, khi nào, làm gì, trên tài nguyên nào, với `correlation_id` (17025 §8.4). |
| **RBAC** | Role-Based Access Control + phạm vi theo phòng ban + **cách ly trường tài chính (field-level)**. |
| **NUMERIC(14,2)** | Kiểu số thập phân cố định cho **giá trị tiền lương** (VND); KHÔNG dùng float (đồng bộ M2). |

### 1.4 Tài liệu tham chiếu

| Tài liệu | Vai trò |
|----------|---------|
| `lims/docs/00-meeting-note-analysis.md` | Yêu cầu gốc R12, R17, R18, R19, R20 + quyết định chốt với KH 19/06/2026 (C02/C03/C04, B03) |
| `lims/docs/01-demo-scope.md` | Cây module M4.1–M4.3, RBAC matrix mục B, ERD core M4 mục C, CRON-3/CRON-4 mục D, mapping 17025 §6.2 mục E |
| `lims/docs/02-srs-m2-chemical.md` | Chuẩn phong cách FR/BR/UC/NFR/AC; **pattern field-level RBAC** (strip cột tài chính — BR-CHEM-022) áp tương tự cho lương |
| `lims/docs/05-srs-m1-sample.md` | Chuẩn phong cách; pattern audit/immutable; "trưởng nhóm cố định theo phòng ban" (`departments.lead_user_id`) |
| `lims/docs/08-contract-m7-schema.md` | `users`/`departments`/`audit_logs`/`notifications`/`attachments` dùng chung; `hr_profiles.user_id` FK→users; quyền `hr:read`/`hr:manage`/`research:manage` đã seed; CRON dùng `notifications` + `idx_notif_ref` chống trùng |
| `~/.claude/rules/nfr.md` | Template NFR chuẩn IEEE 830 |
| `~/.claude/rules/api.md` | Quy ước REST, response format, status code, không lộ ID tuần tự |
| `~/.claude/rules/logging.md` | Structured logging, correlationId, **KHÔNG log PII** (CMND/CCCD, số tài khoản) |
| **ISO/IEC 17025:2017** §6.2 | **Nhân sự** — năng lực, bằng cấp/chứng chỉ, **ủy quyền** thực hiện hoạt động lab, hồ sơ năng lực được kiểm soát |
| **ISO/IEC 17025:2017** §8.4 | Kiểm soát hồ sơ — lưu trữ, truy xuất, bất biến audit cho thay đổi hồ sơ năng lực |

---

## 2. Mô tả tổng quan

### 2.1 Bối cảnh sản phẩm

M4 là một trong 7 module của LIMS monolith (FastAPI + Next.js + PostgreSQL + Redis + MinIO + APScheduler, Docker Compose). M4 **phụ thuộc** vào M7:

- **M7 (Auth + RBAC + phòng ban + audit log):** mọi API M4 yêu cầu xác thực JWT và kiểm tra quyền theo vai trò + phạm vi phòng ban + **field-level cho lương**. `hr_profiles.user_id` là **1-1 FK → `users.id`** (M4 KHÔNG tạo bảng người dùng riêng). Audit ghi vào `audit_logs`.
- **M7.5 (Notifications):** CRON-3 (nhắc nâng lương) và CRON-4 (nhắc hết hạn HĐ) tạo bản ghi `notifications` in-app. Chống trùng theo `idx_notif_ref (ref_type, ref_id, type)` + mốc + ngày.
- **`departments` (M7):** mỗi hồ sơ thuộc 1 phòng ban (qua `users.department_id`); đề tài/thành tích có `department_id` để gắn cấp phòng và thống kê. `departments.lead_user_id` = trưởng nhóm (dùng cho phạm vi đọc thành tích phòng).
- **Bảng `attachments` polymorphic dùng chung:** lưu bằng cấp, chứng chỉ, hợp đồng scan, quyết định nâng lương (`owner_type='hr_profile'`); minh chứng bài báo/sáng chế (`owner_type='publication'`).
- **MinIO:** lưu file; M4 lưu `file_key` không lưu binary trong DB.

M4 **được tham chim bởi**:
- **M2 (Hóa chất) / M6 (Báo cáo):** báo cáo tiêu hao hóa chất "theo đề tài" cần liên kết mẫu → đề tài NCKH của M4 (M2 FR-CHEM-014 chiều "đề tài"). Mối liên kết mẫu↔đề tài là **mềm** (OQ#9 — cần KH chốt có gắn mẫu vào đề tài không).

### 2.2 Chức năng chính

1. Quản lý hồ sơ nhân sự gắn `user_id`: thông tin cá nhân, chức danh, phòng ban, hợp đồng, chu kỳ nâng lương; **tự tính `next_salary_raise_date`**.
2. Quản lý mức lương + lịch sử nâng lương với **RBAC field-level** (chỉ admin/leader/accountant + chính chủ).
3. Quản lý hồ sơ năng lực: bằng cấp, chứng chỉ, ủy quyền thử nghiệm (§6.2), đính kèm minh chứng.
4. CRON-3 nhắc tới hạn nâng lương (15/7/3 ngày) gửi HR + lãnh đạo + chính nhân sự; CRON-4 nhắc hết hạn HĐ (30/15/7 ngày) gửi HR.
5. Quản lý thành tích NCKH: đề tài (lead + thành viên n-n), bài báo (đồng tác giả n-n + thứ tự), sáng chế; gắn cá nhân/tập thể/phòng.
6. Quản lý hướng dẫn SV, lượt SV đăng ký lab, môn học giảng dạy, phục vụ cộng đồng.
7. Thống kê/tổng hợp thành tích theo cá nhân/phòng/khoảng thời gian + xuất Excel/PDF (báo cáo năng lực §6.2).
8. Ghi audit mọi thay đổi hồ sơ/năng lực/lương/HĐ/thành tích (§6.2 + §8.4).

### 2.3 Đối tượng người dùng & quyền (RBAC + phạm vi phòng ban + field-level lương)

Trích từ RBAC matrix `01-demo-scope.md` (mục B, dòng 142–144) và quyền M7 đã seed. Phạm vi dữ liệu: theo phòng ban, trừ Admin & Ban lãnh đạo (toàn hệ thống). **Điểm quan trọng nhất của M4 là cách ly trường lương ở tầng API (field-level).**

| Actor | Mô tả | Quyền trong M4 |
|-------|-------|----------------|
| **Admin** | Quản trị hệ thống | Toàn quyền: CRUD hồ sơ nhân sự (mọi phòng), xem/sửa **lương + hợp đồng**, quản lý năng lực, quản lý mọi thành tích NCKH, xem mọi thống kê. (`hr:manage` all + `research:manage` all) |
| **Ban lãnh đạo** | Lãnh đạo lab | Xem **toàn bộ** hồ sơ nhân sự + **lương + hợp đồng** (toàn hệ thống); quản lý/duyệt thành tích NCKH; xem mọi thống kê năng lực. Sửa lương: theo OQ#1 (ai được sửa lương). (`hr:read`+`hr:manage` all, `research:manage` all) |
| **Kế toán** | Tài chính nhân sự (B03) | **Xem + quản lý phần tài chính nhân sự: LƯƠNG + HỢP ĐỒNG** (toàn hệ thống) — Kế toán là vai trò quản lý tài chính nhân sự (B03). **KHÔNG** truy cập mẫu/kết quả (M1). **KHÔNG** quản lý thành tích NCKH (`research:manage` không cấp cho accountant — demo-scope dòng 144 "Nhân sự — thành tích NCKH: Kế toán = —"). (`hr:read`+`hr:manage` all) |
| **Nhân sự/KTV (staff)** | Kỹ thuật viên / nhân sự thường | **Chỉ xem hồ sơ + thành tích CỦA CHÍNH MÌNH** (scope `own`); **xem lương của chính mình** (👁 của mình); **KHÔNG xem lương/hợp đồng người khác** (kể cả cùng phòng); **quản lý thành tích NCKH của chính mình** (`research:manage` scope `own` — tự khai báo bài báo/đề tài/hướng dẫn SV mình tham gia, có thể cần duyệt OQ#8b). (`hr:read` own, `research:manage` own) |

Quy ước: ✅ = toàn quyền trong phạm vi · 👁 = chỉ xem · — = không truy cập · (phòng) = giới hạn phòng ban · (của mình) = chỉ dữ liệu cá nhân (scope `own`).

> **Cách ly trường tài chính lương (field-level — cốt lõi M4, đồng bộ pattern M2 BR-CHEM-022):**
> - **Trường lương** (mức lương/bậc/hệ số + lịch sử nâng lương giá trị tiền) chỉ trả về cho **Admin / Ban lãnh đạo / Kế toán** (toàn hệ thống) và **chính chủ** (staff xem lương của chính mình).
> - Khi **staff xem hồ sơ người khác** (nếu được phép xem thông tin phi-tài-chính — xem OQ#1b) HOẶC khi danh sách nhân sự trả nhiều người, response API **PHẢI strip trường lương** của những người không phải chính chủ — **lọc ở tầng API, không chỉ ẩn ở FE** (BR-HR-002, BR-HR-003). Đây là yêu cầu bảo mật, kiểm thử bằng NFR-SEC-HR-001.
> - **Hợp đồng (HĐ):** Kế toán quản lý (B03). Staff xem HĐ của chính mình; KHÔNG xem HĐ người khác.
> - **PII nhạy cảm (CMND/CCCD, số tài khoản ngân hàng, ngày sinh):** xem OQ#2b — mặc định chỉ admin/accountant + chính chủ; KHÔNG log ra `audit_logs.detail` / Sentry (rule logging.md).

> **Thành tích NCKH — quyền khai báo:** demo-scope dòng 144 ghi staff "thành tích NCKH: ✅(của mình)". Staff tự khai thành tích **của mình** (scope `own`). Việc khai thành tích **tập thể/phòng** hoặc gắn người khác làm đồng tác giả → cần admin/leader (OQ#8b — staff tự gắn người khác có cần duyệt không).

### 2.4 Ràng buộc (Constraints)

- **CONSTRAINT-1 (1-1 với users):** `hr_profiles.user_id` là **PK đồng thời FK → `users.id`** (1-1). M4 KHÔNG tạo bảng người dùng/đăng nhập riêng; mọi nhân sự phải là một `users` của M7 trước (BR-HR-001).
- **CONSTRAINT-2 (Tự tính ngày nâng lương):** `next_salary_raise_date` KHÔNG nhập tay; luôn = base + `salary_cycle_years` năm và **tự tính lại** mỗi khi `last_salary_raise_date`, `contract_signed_date` hoặc `salary_cycle_years` thay đổi (BR-HR-005). Tính ở tầng app trong cùng transaction cập nhật (không tin trigger DB để dễ test — schema-designer có thể thêm GENERATED column nếu phù hợp, nhưng nguồn chân lý logic là app).
- **CONSTRAINT-3 (Field-level RBAC lương):** trường lương + lịch sử lương phải được **lọc ở tầng API** theo người gọi; staff chỉ nhận trường lương của chính mình (CONSTRAINT cốt lõi — BR-HR-002, BR-HR-003).
- **CONSTRAINT-4 (Audit §6.2 + §8.4):** mọi thay đổi hồ sơ nhân sự / năng lực / lương / hợp đồng / ủy quyền / thành tích ghi `audit_logs` (user, action, resource, resource_id, correlation_id, ip, timestamp, detail đã LỌC PII). Hồ sơ năng lực là bằng chứng VILAS → kiểm soát thay đổi bắt buộc (BR-HR-004).
- **CONSTRAINT-5 (Quan hệ n-n thành tích):** đề tài–thành viên (`project_members`) và bài báo–tác giả (`publication_authors`) là **n-n**; cấp đề tài, chỉ số bài báo, loại HĐ, loại hướng dẫn SV là **enum/danh mục** (giá trị do KH chốt — OQ#3/#5/#6/#7).
- **CONSTRAINT-6 (Tiền):** giá trị lương lưu **NUMERIC(14,2)** kèm `currency` (mặc định VND); KHÔNG dùng float (đồng bộ M2).
- **CONSTRAINT-7 (Thông báo):** chỉ in-app (bảng `notifications`); không email/Zalo (C02).
- **CONSTRAINT-8 (Stack & quy mô):** FastAPI, PostgreSQL, Redis (cron lock), MinIO (file), APScheduler (CRON-3/4). Quy mô ~40 user (C03) — monolith, không scale ngang; cron chạy nhẹ.
- **CONSTRAINT-9 (PII — rule logging.md):** KHÔNG log CMND/CCCD đầy đủ, số tài khoản ngân hàng đầy đủ, lương vào log/`audit_logs.detail`/Sentry. Audit ghi "đã thay đổi trường lương" (fact) chứ KHÔNG ghi giá trị lương cụ thể vào `detail` (OQ#2b xác nhận chính sách ghi giá trị cũ/mới).

### 2.5 Giả định (Assumptions) — xem chi tiết §7

- ASSUMPTION-1: Mọi nhân sự cần quản lý đều đã/được tạo là `users` của M7 (kể cả người không đăng nhập hệ thống — có thể tạo user `status='disabled'` để giữ hồ sơ). Cần KH xác nhận có nhân sự "chỉ hồ sơ, không tài khoản" không (OQ#2c).
- ASSUMPTION-2 → **CHỐT C04:** chu kỳ nâng lương mặc định 3 năm cho mọi ngạch; `salary_cycle_years` cấu hình được ở từng hồ sơ cho ngoại lệ (OQ#4 xác nhận có ngoại lệ thực tế không).
- ASSUMPTION-3: Người nhận CRON-3 = HR (admin/leader có `hr:manage`) + chính nhân sự đó; người nhận CRON-4 = HR. "HR" ánh xạ tới ai cụ thể cần chốt (OQ#10).
- ASSUMPTION-4: Thành tích NCKH là **nhập tay/import**; không crawl tự động (ngoài scope).
- ASSUMPTION-5: Mức lương lưu là **mức hiện hành**; lịch sử nâng lương lưu các mốc thay đổi (giá trị + ngày + người duyệt). Cấu trúc lương (số tiền tuyệt đối hay hệ số×lương cơ sở) cần chốt (OQ#2).

---

## 3. Yêu cầu chức năng chi tiết

Mỗi FR có ID dạng `FR-HR-NNN`. Business rule dạng `BR-HR-NNN` ở §4. Acceptance Criteria dạng Given–When–Then (cover happy path + edge + RBAC/field-level + lỗi input).

---

### FR-HR-001: Tạo / xem hồ sơ nhân sự (gắn user_id)

- **Mô tả:** Tạo hồ sơ nhân sự (`hr_profiles`) gắn **1-1** với một `users` đã tồn tại của M7: chức danh, ngày vào làm, phòng ban (lấy từ `users.department_id`), số điện thoại liên hệ, các trường PII (theo OQ#2b). Một user chỉ có tối đa 1 hồ sơ.
- **Độ ưu tiên:** P0
- **Actor:** Admin (mọi phòng), Kế toán (quản lý tài chính nhân sự — `hr:manage`). Ban lãnh đạo xem (+ sửa theo OQ#1). Staff xem hồ sơ của chính mình.
- **Tiền điều kiện:** user (`users`) đích đã tồn tại; người gọi có quyền `hr:manage`.
- **Luồng chính:**
  1. Người có quyền mở "Hồ sơ nhân sự" → "Thêm hồ sơ" → chọn một `users` chưa có hồ sơ.
  2. Nhập chức danh, ngày vào làm, liên hệ, PII (theo chính sách OQ#2b).
  3. Hệ thống validate (BR-HR-001, BR-HR-006) → tạo `hr_profiles` (user_id = user đã chọn) → ghi `audit_logs` action=`HR_PROFILE_CREATE`.
  4. Trả về hồ sơ vừa tạo (response **đã lọc trường lương** theo quyền người gọi — BR-HR-002).
- **Luồng phụ / ngoại lệ:**
  - A1: user đã có hồ sơ → 409 code `HR_PROFILE_EXISTS` (1-1 — BR-HR-001).
  - A2: user_id không tồn tại / đã `disabled` → 422 code `USER_NOT_FOUND` / cảnh báo (cho phép tạo hồ sơ cho user disabled nếu KH muốn giữ hồ sơ — OQ#2c).
  - A3: thiếu trường bắt buộc (chức danh) → 400.
- **Hậu điều kiện:** hồ sơ tồn tại 1-1 với user; audit ghi nhận; KHÔNG có trường lương trong response nếu người gọi không đủ quyền.
- **Business Rules:** BR-HR-001, BR-HR-002, BR-HR-004, BR-HR-006.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN user "Nguyễn Văn A" (đã có tài khoản, phòng Hóa) chưa có hồ sơ, người gọi là Kế toán WHEN tạo hồ sơ chức danh "KTV chính", ngày vào làm 01/01/2024 THEN trả 201, `hr_profiles.user_id` = A, `department_id` suy từ `users` = Hóa, audit `HR_PROFILE_CREATE` với `correlation_id`.
  - AC2 (1-1): GIVEN A đã có hồ sơ WHEN tạo hồ sơ thứ 2 cho A THEN trả 409 code `HR_PROFILE_EXISTS`, không tạo.
  - AC3 (RBAC — staff không tạo được): GIVEN staff WHEN gọi API tạo hồ sơ THEN trả 403 code `FORBIDDEN`.
  - AC4 (field-level — staff xem của mình không lương người khác): GIVEN staff B xem hồ sơ của chính B THEN response CÓ trường lương của B; GIVEN staff B gọi xem hồ sơ của A THEN response (nếu được phép theo OQ#1b) KHÔNG chứa trường lương của A (strip ở API — BR-HR-002).
  - AC5 (lỗi input): GIVEN form tạo hồ sơ WHEN thiếu chức danh THEN trả 400 code `VALIDATION_ERROR`.
- **Data cần thiết (mức logic):** HrProfile { user_id (PK/FK→users), job_title, hired_date, phone, [PII: id_number?, dob?, bank_account? — theo OQ#2b], created_at, updated_at }. (phòng ban suy từ `users.department_id`.)
- **API cần (ý định):** "tạo hồ sơ nhân sự gắn user", "xem chi tiết hồ sơ (đã lọc trường lương theo quyền)", "liệt kê hồ sơ có phân trang + lọc phòng ban".

---

### FR-HR-002: Cập nhật hồ sơ nhân sự

- **Mô tả:** Cập nhật thông tin phi-tài-chính của hồ sơ (chức danh, liên hệ, PII theo quyền). Cập nhật lương tách riêng ở FR-HR-004 để kiểm soát quyền chặt hơn.
- **Độ ưu tiên:** P0
- **Actor:** Admin, Kế toán (`hr:manage`); Ban lãnh đạo (OQ#1). Staff: KHÔNG sửa hồ sơ (kể cả của mình) trừ khi KH cho phép tự cập nhật liên hệ (OQ#1c).
- **Tiền điều kiện:** hồ sơ tồn tại; người gọi có quyền `hr:manage`.
- **Luồng chính:**
  1. Người có quyền mở hồ sơ → sửa trường phi-tài-chính → lưu.
  2. Hệ thống validate → cập nhật → ghi `audit_logs` action=`HR_PROFILE_UPDATE` (detail = danh sách field đã đổi, **KHÔNG ghi giá trị PII/lương** — CONSTRAINT-9).
- **Luồng phụ / ngoại lệ:**
  - A1: sửa trường lương qua endpoint này → từ chối, hướng dẫn dùng FR-HR-004 (tách quyền).
- **Hậu điều kiện:** hồ sơ cập nhật; thay đổi truy vết qua audit.
- **Business Rules:** BR-HR-002, BR-HR-004.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN Kế toán WHEN sửa chức danh A từ "KTV" thành "KTV chính" THEN cập nhật, audit `HR_PROFILE_UPDATE` ghi field `job_title` đã đổi (không ghi PII).
  - AC2 (RBAC): GIVEN staff WHEN sửa hồ sơ của người khác THEN trả 403.
  - AC3 (tách lương): GIVEN người gọi gửi field lương qua endpoint cập nhật hồ sơ THEN field lương bị bỏ qua/từ chối (chỉ cập nhật qua FR-HR-004).
  - AC4 (audit không lộ PII): GIVEN cập nhật số điện thoại WHEN kiểm tra `audit_logs.detail` THEN có "phone changed" nhưng KHÔNG có giá trị số cụ thể nếu thuộc danh sách PII (CONSTRAINT-9).
- **Data cần thiết:** như FR-HR-001 (trừ lương).
- **API cần:** "cập nhật hồ sơ nhân sự (phi-tài-chính)".

---

### FR-HR-003: Quản lý hợp đồng lao động (ngày ký, loại, ngày hết hạn)

- **Mô tả:** Nhập/cập nhật thông tin hợp đồng của hồ sơ: `contract_signed_date`, `contract_type` (danh mục — OQ#3), `contract_end_date` (NULL nếu HĐ không xác định thời hạn). Là dữ liệu nguồn cho CRON-4 và cho tính `next_salary_raise_date` khi chưa từng nâng lương (R12).
- **Độ ưu tiên:** P0
- **Actor:** Admin, Kế toán (`hr:manage` — B03 Kế toán quản lý hợp đồng). Ban lãnh đạo xem (+ sửa OQ#1). Staff xem HĐ của chính mình.
- **Tiền điều kiện:** hồ sơ tồn tại; người gọi có quyền `hr:manage`.
- **Luồng chính:**
  1. Người có quyền mở hồ sơ → tab "Hợp đồng" → nhập ngày ký, loại HĐ, ngày hết hạn (tùy chọn).
  2. Hệ thống validate (BR-HR-007) → lưu → **tự tính lại `next_salary_raise_date`** nếu chưa có `last_salary_raise_date` (base = `contract_signed_date`, BR-HR-005) → ghi `audit_logs` action=`HR_CONTRACT_UPDATE`.
- **Luồng phụ / ngoại lệ:**
  - A1: `contract_end_date` ≤ `contract_signed_date` → 422 code `INVALID_DATE_ORDER` (BR-HR-007).
  - A2: HĐ không xác định thời hạn → `contract_end_date` = NULL; CRON-4 bỏ qua hồ sơ này (BR-HR-009).
- **Hậu điều kiện:** thông tin HĐ lưu; `next_salary_raise_date` cập nhật nếu cần; CRON-4 dùng `contract_end_date`.
- **Business Rules:** BR-HR-005, BR-HR-007, BR-HR-009.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN hồ sơ A chưa từng nâng lương WHEN nhập `contract_signed_date`=01/01/2024, `salary_cycle_years`=3 THEN `next_salary_raise_date` tự tính = 01/01/2027, audit `HR_CONTRACT_UPDATE`.
  - AC2 (edge — HĐ vô thời hạn): GIVEN nhập HĐ với `contract_end_date`=NULL THEN lưu thành công; CRON-4 sau đó KHÔNG nhắc hồ sơ này (BR-HR-009).
  - AC3 (lỗi input): GIVEN `contract_signed_date`=01/01/2024 WHEN nhập `contract_end_date`=31/12/2023 THEN trả 422 code `INVALID_DATE_ORDER`.
  - AC4 (RBAC): GIVEN staff WHEN sửa HĐ của chính mình THEN trả 403 (chỉ HR quản lý HĐ — B03); GIVEN staff xem HĐ của chính mình THEN được xem (👁).
- **Data cần thiết:** HrProfile { contract_signed_date, contract_type (FK danh mục), contract_end_date (NULL = vô thời hạn) }.
- **API cần:** "cập nhật hợp đồng nhân sự", "xem hợp đồng (theo quyền)".

---

### FR-HR-004: Quản lý lương & lịch sử nâng lương (field-level RBAC)

- **Mô tả:** Nhập/cập nhật **mức lương** hiện hành của hồ sơ và ghi **lịch sử nâng lương** (mỗi lần nâng = 1 bản ghi: ngày nâng, mức cũ→mức mới, người thực hiện, ghi chú/quyết định). Khi ghi nhận một lần nâng lương → cập nhật `last_salary_raise_date` và **tự tính lại `next_salary_raise_date`** (BR-HR-005). Trường lương bị **strip khỏi response cho người không đủ quyền** (BR-HR-002, BR-HR-003).
- **Độ ưu tiên:** P0
- **Actor:** **Ai được sửa lương — OQ#1 (cần KH chốt).** Mặc định đề xuất: Admin + Kế toán (`hr:manage`). Xem lương: Admin/Ban lãnh đạo/Kế toán (toàn hệ thống) + chính chủ (staff xem của mình).
- **Tiền điều kiện:** hồ sơ tồn tại; người gọi có quyền sửa lương (OQ#1).
- **Luồng chính:**
  1. Người có quyền mở hồ sơ → tab "Lương" → ghi nhận nâng lương: nhập mức lương mới + ngày nâng (`raise_date`) + ghi chú (số quyết định).
  2. Hệ thống ghi `salary_history` (old_amount, new_amount, raise_date, by_user) (BR-HR-008) → cập nhật mức lương hiện hành + `last_salary_raise_date`=`raise_date` → **tự tính lại** `next_salary_raise_date` (BR-HR-005).
  3. Ghi `audit_logs` action=`HR_SALARY_RAISE` (detail: fact "đã nâng lương", **KHÔNG ghi giá trị tiền** nếu chính sách OQ#2b yêu cầu, hoặc ghi old/new tùy chính sách — CONSTRAINT-9).
- **Luồng phụ / ngoại lệ:**
  - A1: `raise_date` trong tương lai > hôm nay → cảnh báo (cho phép đặt lịch?) hoặc 422 (OQ#1d — cho ghi nâng lương tương lai không).
  - A2: mức lương mới ≤ 0 → 400 code `INVALID_SALARY`.
  - A3: người gọi không đủ quyền sửa lương → 403 (OQ#1).
- **Hậu điều kiện:** mức lương cập nhật; lịch sử bất biến (append-only — BR-HR-008); `next_salary_raise_date` tự tính lại; audit ghi nhận.
- **Business Rules:** BR-HR-002, BR-HR-003, BR-HR-005, BR-HR-008, BR-HR-004.
- **Acceptance Criteria:**
  - AC1 (happy + tự tính ngày): GIVEN hồ sơ A `salary_cycle_years`=3, lần nâng này `raise_date`=01/06/2026 WHEN ghi nâng lương THEN `last_salary_raise_date`=01/06/2026, `next_salary_raise_date` tự tính = 01/06/2029, 1 bản ghi `salary_history`, audit `HR_SALARY_RAISE`.
  - AC2 (field-level — staff không thấy lương người khác): GIVEN staff B gọi xem hồ sơ A (nếu được phép xem phi-tài-chính) THEN response KHÔNG có trường `current_salary`/`salary_history` của A; GIVEN staff B xem hồ sơ của chính B THEN response CÓ trường lương của B (BR-HR-002, BR-HR-003).
  - AC3 (field-level — danh sách): GIVEN Kế toán liệt kê nhân sự THEN có cột lương; GIVEN staff (nếu được liệt kê) THEN danh sách KHÔNG có cột lương của bất kỳ ai khác ngoài chính mình.
  - AC4 (RBAC sửa — OQ#1): GIVEN người gọi KHÔNG có quyền sửa lương (theo quyết định OQ#1) WHEN ghi nâng lương THEN trả 403.
  - AC5 (lịch sử bất biến): GIVEN đã có 2 bản ghi nâng lương WHEN thử sửa/xóa 1 bản ghi lịch sử THEN không có endpoint cho phép (404/405) — sửa sai = thêm bản ghi điều chỉnh (BR-HR-008).
  - AC6 (lỗi input): GIVEN mức lương mới = 0 hoặc âm WHEN ghi THEN trả 400 code `INVALID_SALARY`.
- **Data cần thiết:** HrProfile.current_salary (NUMERIC(14,2)), currency (DEFAULT 'VND'); SalaryHistory { id, user_id(FK), old_amount, new_amount, raise_date, by_user, note, created_at } (append-only).
- **API cần:** "ghi nhận nâng lương (cập nhật mức + lịch sử, tự tính ngày kế tiếp)", "xem lịch sử lương (chỉ người đủ quyền + chính chủ)".

---

### FR-HR-005: Tự tính ngày nâng lương kế tiếp (`next_salary_raise_date`)

- **Mô tả:** Tính `next_salary_raise_date` = (`last_salary_raise_date` nếu có, ngược lại `contract_signed_date`) + `salary_cycle_years` năm. Tự chạy lại khi bất kỳ input nào thay đổi (ghi nâng lương, sửa HĐ, sửa chu kỳ). Không cho nhập tay.
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (trong các transaction của FR-HR-003, FR-HR-004, FR-HR-006-chu-kỳ).
- **Tiền điều kiện:** hồ sơ có ít nhất `contract_signed_date` (để có base nếu chưa nâng).
- **Luồng chính:**
  1. Sau khi cập nhật `last_salary_raise_date`/`contract_signed_date`/`salary_cycle_years`, hệ thống tính lại `next_salary_raise_date` trong cùng transaction.
  2. Lưu giá trị mới; CRON-3 dùng giá trị này để nhắc.
- **Luồng phụ / ngoại lệ:**
  - A1: chưa có cả `last_salary_raise_date` lẫn `contract_signed_date` → `next_salary_raise_date` = NULL; CRON-3 bỏ qua (BR-HR-010).
  - A2: ngày tính rơi vào 29/02 (năm nhuận) khi cộng năm ra năm không nhuận → quy về 28/02 (chuẩn cộng năm an toàn — BR-HR-005).
- **Hậu điều kiện:** `next_salary_raise_date` luôn nhất quán với input.
- **Business Rules:** BR-HR-005, BR-HR-010.
- **Acceptance Criteria:**
  - AC1 (base = contract khi chưa nâng): GIVEN `contract_signed_date`=01/03/2023, chưa nâng, cycle=3 THEN `next_salary_raise_date`=01/03/2026.
  - AC2 (base = last raise khi đã nâng): GIVEN `last_salary_raise_date`=01/03/2026, cycle=3 THEN `next_salary_raise_date`=01/03/2029.
  - AC3 (đổi chu kỳ tự tính lại): GIVEN `last_salary_raise_date`=01/03/2026, cycle đổi từ 3→2 THEN `next_salary_raise_date` tự tính lại = 01/03/2028.
  - AC4 (edge — năm nhuận): GIVEN base=29/02/2024, cycle=3 (2027 không nhuận) THEN `next_salary_raise_date`=28/02/2027 (không lỗi).
  - AC5 (NULL khi thiếu base): GIVEN hồ sơ chưa có `contract_signed_date` và chưa nâng THEN `next_salary_raise_date`=NULL, CRON-3 không nhắc.
- **Data cần thiết:** HrProfile.{contract_signed_date, last_salary_raise_date, salary_cycle_years, next_salary_raise_date}.
- **API cần:** nội bộ (tính trong các transaction cập nhật); không endpoint riêng.

---

### FR-HR-006: Cấu hình chu kỳ nâng lương (`salary_cycle_years`)

- **Mô tả:** Cho phép cấu hình `salary_cycle_years` cho từng hồ sơ (mặc định 3 — C04). Khi đổi → tự tính lại `next_salary_raise_date` (FR-HR-005).
- **Độ ưu tiên:** P0
- **Actor:** Admin, Kế toán (`hr:manage`); Ban lãnh đạo (OQ#1).
- **Tiền điều kiện:** hồ sơ tồn tại; quyền `hr:manage`.
- **Luồng chính:**
  1. Người có quyền sửa `salary_cycle_years` (số nguyên ≥ 1).
  2. Hệ thống validate (BR-HR-011) → lưu → tự tính lại `next_salary_raise_date` → audit `HR_SALARY_CYCLE_UPDATE`.
- **Luồng phụ / ngoại lệ:**
  - A1: `salary_cycle_years` < 1 hoặc không phải số nguyên → 400 code `INVALID_CYCLE`.
- **Hậu điều kiện:** chu kỳ cập nhật; ngày kế tiếp tự tính lại.
- **Business Rules:** BR-HR-005, BR-HR-011.
- **Acceptance Criteria:**
  - AC1 (happy + mặc định): GIVEN hồ sơ mới THEN `salary_cycle_years` mặc định = 3 (C04).
  - AC2 (đổi hợp lệ): GIVEN cycle=3 WHEN đổi sang 2 THEN lưu + `next_salary_raise_date` tự tính lại (FR-HR-005 AC3).
  - AC3 (lỗi input): GIVEN WHEN đổi cycle = 0 hoặc -1 THEN trả 400 code `INVALID_CYCLE`.
  - AC4 (RBAC): GIVEN staff WHEN đổi cycle THEN trả 403.
- **Data cần thiết:** HrProfile.salary_cycle_years (INT, DEFAULT 3, ≥ 1).
- **API cần:** "cập nhật chu kỳ nâng lương".

---

### FR-HR-007: Quản lý hồ sơ năng lực — bằng cấp, chứng chỉ, ủy quyền thử nghiệm (17025 §6.2)

- **Mô tả:** Quản lý bằng chứng năng lực của nhân sự theo §6.2: (a) **bằng cấp** (tên, nơi cấp, năm); (b) **chứng chỉ** (tên, nơi cấp, ngày cấp, **ngày hết hạn** nếu có); (c) **ủy quyền thử nghiệm** (được ủy quyền chỉ tiêu/phương pháp nào, hiệu lực từ–đến, người ủy quyền). Mỗi mục đính kèm minh chứng (scan) qua `attachments` (`owner_type='hr_profile'`).
- **Độ ưu tiên:** P1 (theo demo-scope F4.1.4) — nhưng là yêu cầu §6.2; khuyến nghị làm sớm để phục vụ VILAS.
- **Actor:** Admin, Ban lãnh đạo (quản lý năng lực — `hr:manage`/leader). Staff xem năng lực của chính mình. (Kế toán: theo OQ#1b — năng lực không phải tài chính; mặc định Kế toán không quản lý năng lực.)
- **Tiền điều kiện:** hồ sơ tồn tại; quyền quản lý năng lực.
- **Luồng chính:**
  1. Người có quyền mở hồ sơ → tab "Năng lực" → thêm bằng cấp / chứng chỉ / ủy quyền.
  2. Nhập thông tin + đính kèm file minh chứng (tùy chọn).
  3. Hệ thống validate (BR-HR-012) → lưu → ghi `audit_logs` action=`HR_COMPETENCE_CHANGE` (§6.2 + §8.4 — kiểm soát thay đổi hồ sơ năng lực, BR-HR-004).
- **Luồng phụ / ngoại lệ:**
  - A1: chứng chỉ/ủy quyền có ngày hết hạn < hôm nay → đánh dấu `expired` (cảnh báo năng lực hết hiệu lực — gợi ý OQ#11 có cron nhắc năng lực hết hạn không).
  - A2: ủy quyền hiệu lực `from` > `to` → 422 `INVALID_DATE_ORDER`.
  - A3: file minh chứng sai loại/quá lớn → 422 (BR-HR-012).
- **Hậu điều kiện:** hồ sơ năng lực lưu; minh chứng truy xuất được; thay đổi audit đầy đủ.
- **Business Rules:** BR-HR-004, BR-HR-012.
- **Acceptance Criteria:**
  - AC1 (happy — bằng cấp): GIVEN hồ sơ A WHEN thêm bằng "Thạc sĩ Hóa phân tích", nơi cấp, năm 2020 THEN lưu, audit `HR_COMPETENCE_CHANGE`.
  - AC2 (ủy quyền §6.2): GIVEN hồ sơ A WHEN thêm ủy quyền "Thực hiện chỉ tiêu pH theo SOP-XX", hiệu lực 01/01/2026–31/12/2027, người ủy quyền = trưởng phòng THEN lưu; chi tiết hồ sơ hiển thị nhân sự được ủy quyền chỉ tiêu pH.
  - AC3 (edge — hết hạn): GIVEN chứng chỉ ngày hết hạn 01/01/2025 WHEN xem hôm nay (2026) THEN đánh dấu `expired`.
  - AC4 (RBAC — staff xem của mình): GIVEN staff A xem năng lực của chính A THEN được xem; xem năng lực người khác THEN theo phạm vi (mặc định không, OQ#1b).
  - AC5 (audit §8.4): GIVEN thêm/sửa/xóa bằng chứng năng lực WHEN kiểm tra audit THEN luôn có `HR_COMPETENCE_CHANGE` (kiểm soát thay đổi hồ sơ năng lực bắt buộc — BR-HR-004).
- **Data cần thiết:** Competence { id, user_id(FK), kind ∈ {degree, certificate, authorization}, title, issuer, issued_date, expiry_date(NULL), scope_detail (chỉ tiêu/phương pháp với authorization), authorized_by(FK→users, với authorization), created_at }; Attachment(owner_type='hr_profile').
- **API cần:** "thêm/sửa/xóa mục năng lực", "liệt kê năng lực của nhân sự", "tải minh chứng".

---

### FR-HR-008: CRON-3 — Nhắc tới hạn nâng lương (in-app, mốc 15/7/3 ngày)

- **Mô tả:** Tác vụ định kỳ hằng ngày 07:00 quét hồ sơ có `next_salary_raise_date` còn **15 / 7 / 3 ngày** và tạo thông báo in-app cho **HR (admin/leader có `hr:manage`) + chính nhân sự đó**. Chống trùng theo (hồ sơ × mốc × ngày). (R12, CRON-3)
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (APScheduler) → người nhận: HR + chính nhân sự + lãnh đạo.
- **Tiền điều kiện:** có hồ sơ với `next_salary_raise_date` NOT NULL; APScheduler chạy; Redis lock khả dụng.
- **Luồng chính:**
  1. 07:00 hằng ngày, APScheduler acquire Redis lock (tránh chạy trùng).
  2. Quét hồ sơ có `next_salary_raise_date` = hôm nay + 15 / +7 / +3 ngày.
  3. Với mỗi hồ sơ tới mốc → tạo `notifications` (type=`SALARY_RAISE_DUE`, ref_type=`hr_profile`, ref_id=user_id) cho **HR + chính nhân sự + lãnh đạo**; chống trùng theo (hồ sơ × mốc × ngày) (BR-HR-013).
  4. Ghi log INFO số notification đã tạo; release lock.
- **Luồng phụ / ngoại lệ:**
  - A1: Redis lock đã bị giữ → instance khác bỏ qua lần chạy.
  - A2: lỗi giữa chừng → log ERROR với correlationId; lần sau retry (idempotent nhờ chống trùng).
  - A3: `next_salary_raise_date` = NULL → bỏ qua (BR-HR-010).
- **Hậu điều kiện:** thông báo in-app đúng mốc, không trùng, đúng người nhận.
- **Business Rules:** BR-HR-013, BR-HR-010, BR-HR-014 (người nhận).
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN hồ sơ A `next_salary_raise_date` = hôm nay + 7 ngày WHEN cron 07:00 chạy THEN tạo notification `SALARY_RAISE_DUE` mốc-7-ngày cho HR + cho chính A + lãnh đạo.
  - AC2 (chống trùng): GIVEN cron đã tạo mốc-7-ngày cho A hôm nay WHEN cron chạy lại cùng ngày THEN KHÔNG tạo notification thứ 2 cùng (hồ sơ × mốc).
  - AC3 (3 mốc độc lập): GIVEN A tới hạn WHEN lần lượt còn 15, 7, 3 ngày THEN mỗi mốc tạo đúng 1 lần (3 notification qua 3 ngày khác nhau).
  - AC4 (lock): GIVEN 2 tiến trình cron khởi động đồng thời lúc 07:00 THEN chỉ 1 thực thi (Redis lock).
  - AC5 (NULL bỏ qua): GIVEN hồ sơ thiếu `next_salary_raise_date` WHEN cron chạy THEN không tạo notification cho hồ sơ đó.
- **Data cần thiết:** đọc `hr_profiles.next_salary_raise_date`; ghi `notifications`; cờ chống trùng (qua `idx_notif_ref` + mốc + ngày, theo M7 §8 mục 6).
- **API cần:** không có endpoint công khai; scheduled job. Có thể có endpoint admin "chạy thủ công CRON-3" để test.

---

### FR-HR-009: CRON-4 — Nhắc hết hạn hợp đồng (in-app, mốc 30/15/7 ngày)

- **Mô tả:** Tác vụ định kỳ hằng ngày 07:00 quét hồ sơ có `contract_end_date` còn **30 / 15 / 7 ngày** và tạo thông báo in-app cho **HR** (+ chính nhân sự — theo OQ#10). Bỏ qua HĐ vô thời hạn (`contract_end_date` NULL). Chống trùng theo (hồ sơ × mốc × ngày). (R12, CRON-4)
- **Độ ưu tiên:** P1 (demo-scope F4.2.2) — nhưng CRON-4 đã liệt kê trong danh sách cron P0-level vận hành; khuyến nghị làm cùng CRON-3.
- **Actor:** hệ thống (APScheduler) → người nhận: HR (+ nhân sự theo OQ#10).
- **Tiền điều kiện:** có hồ sơ với `contract_end_date` NOT NULL; APScheduler chạy; Redis lock.
- **Luồng chính:**
  1. 07:00 hằng ngày, acquire Redis lock.
  2. Quét hồ sơ có `contract_end_date` = hôm nay + 30 / +15 / +7 ngày.
  3. Tạo `notifications` (type=`CONTRACT_EXPIRY`, ref_type=`hr_profile`, ref_id=user_id) cho HR (+ nhân sự theo OQ#10); chống trùng (BR-HR-013).
  4. Log INFO; release lock.
- **Luồng phụ / ngoại lệ:**
  - A1: `contract_end_date` = NULL (HĐ vô thời hạn) → bỏ qua (BR-HR-009).
  - A2: lock đã giữ → bỏ qua lần chạy; lỗi → log ERROR, retry idempotent.
- **Hậu điều kiện:** thông báo in-app đúng mốc, không trùng.
- **Business Rules:** BR-HR-009, BR-HR-013, BR-HR-014.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN hồ sơ A `contract_end_date` = hôm nay + 30 ngày WHEN cron 07:00 chạy THEN tạo notification `CONTRACT_EXPIRY` mốc-30-ngày cho HR.
  - AC2 (vô thời hạn bỏ qua): GIVEN hồ sơ `contract_end_date`=NULL WHEN cron chạy THEN KHÔNG tạo notification.
  - AC3 (chống trùng): GIVEN đã tạo mốc-30-ngày cho A hôm nay WHEN cron chạy lại cùng ngày THEN không tạo lần 2.
  - AC4 (3 mốc): GIVEN A WHEN còn 30/15/7 ngày THEN mỗi mốc nhắc 1 lần.
- **Data cần thiết:** đọc `hr_profiles.contract_end_date`; ghi `notifications`; chống trùng.
- **API cần:** scheduled job; endpoint admin chạy thủ công để test.

---

### FR-HR-010: CRUD đề tài NCKH (chủ nhiệm + thành viên n-n + cấp đề tài)

- **Mô tả:** Tạo/sửa/xem đề tài NCKH: tên, **chủ nhiệm (`lead_user_id`)**, **thành viên (n-n qua `project_members`)** với `role_in_project`, **cấp đề tài** (danh mục — OQ#5), thời gian (từ–đến), phòng (`department_id`), trạng thái (đang thực hiện/nghiệm thu/...). (R17)
- **Độ ưu tiên:** P0
- **Actor:** Admin, Ban lãnh đạo (`research:manage` all). Staff khai đề tài **mình tham gia** (scope `own`); gắn người khác làm thành viên → theo OQ#8b. Kế toán: KHÔNG (research không cấp cho accountant).
- **Tiền điều kiện:** người gọi có quyền `research:manage`; lead + thành viên là `users` tồn tại.
- **Luồng chính:**
  1. Người có quyền mở "Đề tài NCKH" → "Thêm đề tài".
  2. Nhập tên, chọn chủ nhiệm, thêm thành viên (n-n) + vai trò, cấp đề tài, thời gian, phòng, trạng thái.
  3. Hệ thống validate (BR-HR-015, BR-HR-016) → lưu `research_projects` + `project_members` → ghi `audit_logs` action=`RESEARCH_PROJECT_CREATE`.
- **Luồng phụ / ngoại lệ:**
  - A1: thiếu chủ nhiệm → 400 code `LEAD_REQUIRED` (BR-HR-016).
  - A2: `end_date` < `start_date` → 422 `INVALID_DATE_ORDER`.
  - A3: cấp đề tài không thuộc danh mục → 400 code `INVALID_PROJECT_LEVEL` (BR-HR-015).
  - A4: thêm cùng một user 2 lần làm thành viên → 409/cảnh báo (BR-HR-016).
- **Hậu điều kiện:** đề tài + danh sách thành viên lưu; thống kê quy được cho cá nhân/tập thể/phòng.
- **Business Rules:** BR-HR-015, BR-HR-016, BR-HR-022.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN Ban lãnh đạo WHEN tạo đề tài "Phát triển phương pháp đo X", chủ nhiệm = A, thành viên = {A (chủ nhiệm), B, C}, cấp = "Cấp trường", 2026–2028, phòng Hóa THEN trả 201, 3 bản ghi `project_members`, audit `RESEARCH_PROJECT_CREATE`.
  - AC2 (n-n): GIVEN B đã là thành viên đề tài X WHEN B cũng được thêm vào đề tài Y THEN B thuộc cả 2 đề tài (n-n hợp lệ).
  - AC3 (lỗi — thiếu chủ nhiệm): GIVEN form đề tài WHEN không chọn chủ nhiệm THEN trả 400 `LEAD_REQUIRED`.
  - AC4 (lỗi — cấp ngoài danh mục): GIVEN cấp = "Cấp xã" (không có trong danh mục) THEN trả 400 `INVALID_PROJECT_LEVEL`.
  - AC5 (RBAC — staff own): GIVEN staff WHEN tạo đề tài mà mình KHÔNG phải thành viên/chủ nhiệm THEN trả 403 (scope `own` — chỉ khai đề tài mình tham gia, OQ#8b).
- **Data cần thiết:** ResearchProject { id, title, level (FK danh mục), lead_user_id(FK→users), department_id(FK), start_date, end_date, status, created_at }; ProjectMember { project_id(FK), user_id(FK), role_in_project } (PK kép, n-n).
- **API cần:** "CRUD đề tài", "thêm/xóa thành viên đề tài", "liệt kê đề tài có lọc (phòng/cấp/năm/người)".

---

### FR-HR-011: CRUD bài báo khoa học (đồng tác giả n-n + thứ tự + chỉ số)

- **Mô tả:** Tạo/sửa/xem bài báo: tên, tạp chí/hội nghị, năm, DOI, **chỉ số** (ISI/Scopus/SCIE/... — danh mục OQ#6), **đồng tác giả (n-n qua `publication_authors`) + `author_order`** + cờ corresponding (tùy chọn), phòng (`department_id`), `type='paper'`. (R17)
- **Độ ưu tiên:** P0
- **Actor:** Admin, Ban lãnh đạo (`research:manage` all). Staff khai bài báo **mình là tác giả** (scope `own`); gắn đồng tác giả khác → OQ#8b.
- **Tiền điều kiện:** người gọi có quyền `research:manage`; tác giả là `users` tồn tại (hoặc tác giả ngoài hệ thống — OQ#8c: cho phép tác giả không phải user nội bộ?).
- **Luồng chính:**
  1. Người có quyền mở "Bài báo" → "Thêm bài báo".
  2. Nhập tên, tạp chí, năm, DOI, chỉ số; thêm danh sách tác giả + thứ tự (`author_order`).
  3. Hệ thống validate (BR-HR-017, BR-HR-018) → lưu `publications` + `publication_authors` → audit `RESEARCH_PUBLICATION_CREATE`.
- **Luồng phụ / ngoại lệ:**
  - A1: DOI sai định dạng → 400 (validate cơ bản — BR-HR-017) (định dạng DOI: `10.xxxx/...`).
  - A2: chỉ số ngoài danh mục → 400 `INVALID_INDEX` (BR-HR-017).
  - A3: trùng `author_order` trong cùng bài → 422 `DUPLICATE_AUTHOR_ORDER` (BR-HR-018).
  - A4: năm > năm hiện tại + 1 → cảnh báo (bài chưa xuất bản — OQ#6b cho phép không).
- **Hậu điều kiện:** bài báo + danh sách tác giả (có thứ tự) lưu; thống kê quy cho cá nhân/phòng.
- **Business Rules:** BR-HR-017, BR-HR-018, BR-HR-022.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN Ban lãnh đạo WHEN tạo bài báo "Method X for ...", tạp chí "J. Anal.", năm 2025, DOI "10.1000/abc", chỉ số "Scopus Q1", tác giả [A#1, B#2, C#3] THEN trả 201, 3 `publication_authors` với `author_order` 1/2/3, audit `RESEARCH_PUBLICATION_CREATE`.
  - AC2 (n-n + thứ tự): GIVEN A là tác giả nhiều bài WHEN thống kê bài của A THEN gồm tất cả bài A là tác giả, kèm thứ tự tác giả của A trong từng bài.
  - AC3 (lỗi — trùng thứ tự): GIVEN thêm 2 tác giả cùng `author_order`=1 THEN trả 422 `DUPLICATE_AUTHOR_ORDER`.
  - AC4 (lỗi — chỉ số ngoài danh mục): GIVEN chỉ số = "ABCD" THEN trả 400 `INVALID_INDEX`.
  - AC5 (RBAC — staff own): GIVEN staff WHEN tạo bài báo mà mình KHÔNG phải tác giả THEN trả 403 (scope `own`, OQ#8b).
- **Data cần thiết:** Publication { id, title, journal, year, doi, index_code (FK danh mục), type='paper', department_id(FK), created_at }; PublicationAuthor { publication_id(FK), user_id(FK), author_order, is_corresponding } (n-n).
- **API cần:** "CRUD bài báo", "quản lý danh sách tác giả + thứ tự", "liệt kê bài báo có lọc (năm/chỉ số/phòng/tác giả)".

---

### FR-HR-012: CRUD bằng sáng chế / giải pháp hữu ích

- **Mô tả:** Tạo/sửa/xem bằng sáng chế / giải pháp hữu ích: tên, số bằng, năm cấp, cơ quan cấp, đồng tác giả (n-n như bài báo). Lưu chung bảng `publications` với `type='patent'`. (R17)
- **Độ ưu tiên:** P0
- **Actor:** như FR-HR-011.
- **Tiền điều kiện:** quyền `research:manage`.
- **Luồng chính:**
  1. Người có quyền mở "Sáng chế/Giải pháp" → "Thêm".
  2. Nhập tên, số bằng, năm cấp, cơ quan cấp; thêm tác giả (n-n).
  3. Validate → lưu `publications` (type='patent') + `publication_authors` → audit `RESEARCH_PATENT_CREATE`.
- **Luồng phụ / ngoại lệ:**
  - A1: trùng số bằng → 409 `DUPLICATE_PATENT_NO` (BR-HR-019).
- **Hậu điều kiện:** sáng chế lưu; thống kê quy cho cá nhân/phòng.
- **Business Rules:** BR-HR-018, BR-HR-019, BR-HR-022.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN WHEN tạo giải pháp hữu ích "Thiết bị Y", số bằng "GPHI-123", năm 2024, cơ quan "Cục SHTT", tác giả [A#1] THEN trả 201, audit `RESEARCH_PATENT_CREATE`.
  - AC2 (lỗi — trùng số bằng): GIVEN số bằng "GPHI-123" đã tồn tại WHEN tạo lại THEN trả 409 `DUPLICATE_PATENT_NO`.
  - AC3 (RBAC): GIVEN staff khai sáng chế mình không phải tác giả THEN 403 (scope `own`).
- **Data cần thiết:** Publication(type='patent') { ..., patent_no (UNIQUE khi type=patent), issuing_authority }.
- **API cần:** "CRUD sáng chế/giải pháp", "quản lý tác giả".

---

### FR-HR-013: Gắn thành tích cho cá nhân / tập thể (nhóm) / phòng thí nghiệm

- **Mô tả:** Đảm bảo mỗi thành tích (đề tài/bài báo/sáng chế) quy được cho: **cá nhân** (qua quan hệ thành viên/tác giả), **tập thể/nhóm** (tập hợp các thành viên/tác giả), và **phòng thí nghiệm** (`department_id`). Cho phép lọc/thống kê theo cả 3 chiều. (R17)
- **Độ ưu tiên:** P0
- **Actor:** mọi vai trò có quyền `research:manage`/`research:read` trong phạm vi.
- **Tiền điều kiện:** thành tích đã tồn tại.
- **Luồng chính:**
  1. Khi tạo thành tích, người dùng gắn phòng (`department_id`) + danh sách cá nhân (thành viên/tác giả).
  2. Hệ thống lưu các liên kết; truy vấn thống kê join theo cá nhân / nhóm thành viên / phòng.
- **Luồng phụ / ngoại lệ:**
  - A1: thành tích không gắn phòng → gom nhóm "Không gắn phòng" trong thống kê (BR-HR-022).
- **Hậu điều kiện:** thành tích truy vết được theo 3 chiều.
- **Business Rules:** BR-HR-022.
- **Acceptance Criteria:**
  - AC1 (cá nhân): GIVEN A là đồng tác giả 3 bài + thành viên 2 đề tài WHEN xem hồ sơ thành tích của A THEN liệt kê đủ 3 bài + 2 đề tài.
  - AC2 (phòng): GIVEN phòng Hóa có 5 bài báo gắn `department_id`=Hóa WHEN thống kê theo phòng Hóa THEN đếm đúng 5 bài.
  - AC3 (tập thể): GIVEN đề tài X có 4 thành viên WHEN xem đề tài X THEN hiển thị đủ 4 thành viên (tập thể).
- **Data cần thiết:** `research_projects.department_id`, `publications.department_id`, `project_members`, `publication_authors`.
- **API cần:** "lọc thành tích theo cá nhân/phòng/nhóm".

---

### FR-HR-014: Quản lý hướng dẫn sinh viên

- **Mô tả:** Ghi nhận nhân sự hướng dẫn SV: tên SV, đề tài, năm, **loại** (khóa luận/luận văn/luận án/NCKH SV... — danh mục OQ#7), (tùy chọn) đồng hướng dẫn. (R18)
- **Độ ưu tiên:** P0
- **Actor:** Admin, Ban lãnh đạo; Staff khai hướng dẫn **của mình** (scope `own`).
- **Tiền điều kiện:** quyền `research:manage`; mentor là `users` tồn tại.
- **Luồng chính:**
  1. Người có quyền mở "Hướng dẫn SV" → "Thêm".
  2. Nhập tên SV, đề tài, năm, loại, người hướng dẫn (mặc định = chính mình với staff).
  3. Validate (BR-HR-020) → lưu `student_mentorships` → audit `RESEARCH_MENTORSHIP_CREATE`.
- **Luồng phụ / ngoại lệ:**
  - A1: loại ngoài danh mục → 400 `INVALID_MENTORSHIP_TYPE`.
- **Hậu điều kiện:** bản ghi hướng dẫn lưu; thống kê số lượng SV hướng dẫn theo người/phòng/năm.
- **Business Rules:** BR-HR-020, BR-HR-022.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN staff A WHEN khai hướng dẫn "SV Trần B", đề tài "...", năm 2025, loại "Khóa luận" THEN lưu với mentor=A, audit `RESEARCH_MENTORSHIP_CREATE`.
  - AC2 (thống kê): GIVEN A hướng dẫn 4 SV năm 2025 WHEN thống kê THEN đếm đúng 4.
  - AC3 (lỗi — loại ngoài danh mục): GIVEN loại = "Đồ án ABC" không có trong danh mục THEN 400 `INVALID_MENTORSHIP_TYPE`.
  - AC4 (RBAC — staff own): GIVEN staff A khai hướng dẫn với mentor = người khác THEN theo OQ#8b (mặc định 403 nếu không phải mình).
- **Data cần thiết:** StudentMentorship { id, mentor_id(FK→users), student_name, topic, year, type (FK danh mục), department_id(FK, suy từ mentor), created_at }.
- **API cần:** "CRUD hướng dẫn SV", "thống kê hướng dẫn SV theo người/phòng/năm".

---

### FR-HR-015: Quản lý lượt SV đăng ký vào lab

- **Mô tả:** Ghi nhận lượt SV đăng ký vào lab (thực tập / dùng thiết bị): tên SV (người đăng ký), người hướng dẫn (nhân sự phụ trách), thời gian (từ–đến hoặc ngày đăng ký), mục đích. **Có thể cần duyệt** (OQ#8 — lượt đăng ký lab có cần duyệt không). (R18)
- **Độ ưu tiên:** P1 (demo-scope F4.3.6)
- **Actor:** Admin, Ban lãnh đạo; Staff (người hướng dẫn) tạo lượt đăng ký mình phụ trách. Duyệt (nếu cần) theo OQ#8.
- **Tiền điều kiện:** quyền `research:manage`; người hướng dẫn là `users` tồn tại.
- **Luồng chính:**
  1. Người có quyền mở "SV đăng ký lab" → "Thêm".
  2. Nhập tên SV, người hướng dẫn, thời gian, mục đích.
  3. Validate → lưu `lab_registrations` (trạng thái theo OQ#8: nếu cần duyệt → `pending`; nếu không → `recorded`) → audit `LAB_REGISTRATION_CREATE`.
- **Luồng phụ / ngoại lệ:**
  - A1 (nếu OQ#8 = cần duyệt): lượt `pending` cần Ban lãnh đạo/trưởng nhóm duyệt → `approved`/`rejected`; chỉ lượt `approved` được tính vào thống kê.
- **Hậu điều kiện:** lượt đăng ký lưu; đếm được số lượt SV đăng ký theo người/phòng/kỳ.
- **Business Rules:** BR-HR-021, BR-HR-022.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN staff A WHEN tạo lượt "SV Lê C đăng ký dùng thiết bị HPLC, 01/07–31/07/2026, mục đích thực tập", người hướng dẫn=A THEN lưu, audit `LAB_REGISTRATION_CREATE`.
  - AC2 (thống kê): GIVEN 12 lượt đăng ký phòng Hóa trong 2026 WHEN thống kê THEN đếm đúng 12 (chỉ tính `approved` nếu OQ#8 = cần duyệt).
  - AC3 (duyệt — nếu OQ#8 bật): GIVEN lượt `pending` WHEN Ban lãnh đạo duyệt THEN chuyển `approved`, audit `LAB_REGISTRATION_APPROVE`.
- **Data cần thiết:** LabRegistration { id, student_name, mentor_id(FK→users), registered_from, registered_to (NULL), purpose, status (theo OQ#8), department_id(FK), created_at }.
- **API cần:** "CRUD lượt SV đăng ký lab", "(tùy chọn) duyệt lượt đăng ký", "thống kê lượt đăng ký".

---

### FR-HR-016: Quản lý môn học phụ trách giảng dạy

- **Mô tả:** Ghi nhận môn học mỗi giảng viên/nhân sự phụ trách: tên môn, học kỳ, năm. (R19)
- **Độ ưu tiên:** P1 (demo-scope F4.3.7)
- **Actor:** Admin, Ban lãnh đạo; Staff khai môn của chính mình (scope `own`).
- **Tiền điều kiện:** quyền `research:manage`; user tồn tại.
- **Luồng chính:**
  1. Người có quyền mở "Giảng dạy" → "Thêm môn".
  2. Nhập tên môn, học kỳ, năm (mặc định người phụ trách = chính mình với staff).
  3. Validate → lưu `teaching_courses` → audit `TEACHING_COURSE_CREATE`.
- **Luồng phụ / ngoại lệ:**
  - A1: trùng (user + môn + học kỳ + năm) → 409/cảnh báo (BR-HR-020).
- **Hậu điều kiện:** môn học lưu; thống kê số môn theo người/phòng/kỳ.
- **Business Rules:** BR-HR-020, BR-HR-022.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN staff A WHEN khai "Hóa phân tích, HK1, 2025" THEN lưu với user=A, audit `TEACHING_COURSE_CREATE`.
  - AC2 (thống kê): GIVEN A dạy 3 môn HK1/2025 WHEN thống kê THEN đếm đúng 3.
  - AC3 (RBAC — staff own): GIVEN staff khai môn cho người khác THEN 403 (scope `own`).
- **Data cần thiết:** TeachingCourse { id, user_id(FK→users), course_name, semester, year, department_id(FK), created_at }.
- **API cần:** "CRUD môn học giảng dạy", "thống kê giảng dạy".

---

### FR-HR-017: Quản lý hoạt động phục vụ cộng đồng

- **Mô tả:** Ghi nhận hoạt động phục vụ cộng đồng: nội dung, thời gian thực hiện, **người thực hiện** (nhân sự), **host** (đơn vị/tổ chức chủ trì). (R20)
- **Độ ưu tiên:** P1 (demo-scope F4.3.8)
- **Actor:** Admin, Ban lãnh đạo; Staff khai hoạt động của chính mình (scope `own`).
- **Tiền điều kiện:** quyền `research:manage`; người thực hiện là `users` tồn tại.
- **Luồng chính:**
  1. Người có quyền mở "Phục vụ cộng đồng" → "Thêm".
  2. Nhập nội dung, thời gian thực hiện, người thực hiện, host.
  3. Validate → lưu `community_services` → audit `COMMUNITY_SERVICE_CREATE`.
- **Luồng phụ / ngoại lệ:**
  - A1: thiếu nội dung/người thực hiện → 400.
- **Hậu điều kiện:** hoạt động lưu; thống kê theo người/phòng/kỳ.
- **Business Rules:** BR-HR-022.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN staff A WHEN khai "Tập huấn an toàn hóa chất cho trường THPT X, 10/05/2026, host = Sở GD" người thực hiện=A THEN lưu, audit `COMMUNITY_SERVICE_CREATE`.
  - AC2 (thống kê): GIVEN A có 2 hoạt động 2026 WHEN thống kê THEN đếm đúng 2.
  - AC3 (RBAC — staff own): GIVEN staff khai hoạt động cho người khác THEN 403 (scope `own`).
- **Data cần thiết:** CommunityService { id, content, performed_at, host, performer_user_id(FK→users), department_id(FK), created_at }.
- **API cần:** "CRUD phục vụ cộng đồng", "thống kê phục vụ cộng đồng".

---

### FR-HR-018: Thống kê / tổng hợp thành tích (cá nhân / phòng / khoảng thời gian) + xuất

- **Mô tả:** Tổng hợp số liệu thành tích NCKH (đề tài, bài báo theo chỉ số, sáng chế, hướng dẫn SV, lượt SV đăng ký lab, môn học, phục vụ cộng đồng) theo các chiều: **cá nhân / phòng thí nghiệm / khoảng thời gian**. Xuất Excel/PDF phục vụ **báo cáo năng lực 17025 §6.2** và báo cáo thành tích đơn vị. (R17–R20)
- **Độ ưu tiên:** P1 (cốt lõi giá trị §6.2; có thể tách dashboard sang M6)
- **Actor:** Admin, Ban lãnh đạo (toàn hệ thống); Staff xem thống kê **của chính mình**. Kế toán: KHÔNG (research không cấp cho accountant).
- **Tiền điều kiện:** đã đăng nhập; có dữ liệu thành tích.
- **Luồng chính:**
  1. User chọn chiều tổng hợp (cá nhân/phòng/thời gian) + bộ lọc (năm, cấp đề tài, chỉ số bài báo, loại...).
  2. Hệ thống đếm/tổng hợp theo phạm vi quyền (Admin/Lãnh đạo all; staff own) → hiển thị bảng + biểu đồ.
  3. Cho phép xuất Excel/PDF; ghi `audit_logs` action=`RESEARCH_REPORT_EXPORT` (đếm lượt tải — R15).
- **Luồng phụ / ngoại lệ:**
  - A1: khoảng thời gian không hợp lệ (from > to) → 400 `INVALID_DATE_RANGE`.
  - A2: staff cố xem thống kê người khác/phòng → chỉ trả dữ liệu của chính mình (scope `own` — BR-HR-023).
- **Hậu điều kiện:** chỉ đọc; lượt xuất được audit.
- **Business Rules:** BR-HR-022, BR-HR-023.
- **Acceptance Criteria:**
  - AC1 (happy — phòng): GIVEN Ban lãnh đạo WHEN thống kê phòng Hóa năm 2025 THEN trả: số đề tài (theo cấp), số bài báo (theo chỉ số), số sáng chế, số SV hướng dẫn, số lượt SV đăng ký, số môn dạy, số hoạt động cộng đồng — đúng số.
  - AC2 (cá nhân): GIVEN xem thống kê cá nhân A năm 2025 THEN tổng hợp đúng các mục của A.
  - AC3 (RBAC — staff own): GIVEN staff B WHEN gọi thống kê phòng/người khác THEN chỉ nhận dữ liệu của chính B (scope `own` — BR-HR-023).
  - AC4 (xuất + audit): GIVEN xuất Excel báo cáo năng lực WHEN kiểm tra audit THEN có `RESEARCH_REPORT_EXPORT` với user + bộ lọc + correlationId.
  - AC5 (lỗi input): GIVEN from > to WHEN thống kê THEN 400 `INVALID_DATE_RANGE`.
- **Data cần thiết:** aggregate `research_projects`/`publications`/`student_mentorships`/`lab_registrations`/`teaching_courses`/`community_services` join `users`/`departments`.
- **API cần:** "thống kê thành tích theo chiều + bộ lọc", "xuất Excel/PDF báo cáo năng lực".

---

### FR-HR-019: Xem hồ sơ năng lực tổng hợp của một nhân sự (bằng chứng §6.2)

- **Mô tả:** Trang tổng hợp **hồ sơ năng lực** của một nhân sự phục vụ đánh giá VILAS: bằng cấp, chứng chỉ (còn hiệu lực / hết hạn), ủy quyền thử nghiệm (chỉ tiêu được ủy quyền + hiệu lực), kèm danh sách thành tích NCKH. Dùng khi đánh giá viên VILAS yêu cầu chứng minh năng lực người thực hiện một phép thử.
- **Độ ưu tiên:** P1
- **Actor:** Admin, Ban lãnh đạo; Staff xem của chính mình.
- **Tiền điều kiện:** hồ sơ tồn tại; đã đăng nhập.
- **Luồng chính:**
  1. User mở hồ sơ nhân sự → tab "Năng lực tổng hợp".
  2. Hệ thống hiển thị: bằng cấp, chứng chỉ (đánh dấu hết hạn), ủy quyền thử nghiệm (chỉ tiêu + hiệu lực), thành tích. (KHÔNG hiển thị lương ở tab năng lực — tách riêng.)
- **Luồng phụ / ngoại lệ:**
  - A1: nhân sự có ủy quyền hết hiệu lực → đánh dấu rõ "hết hiệu lực" (đánh giá VILAS cần biết).
- **Hậu điều kiện:** chỉ đọc.
- **Business Rules:** BR-HR-004 (kiểm soát năng lực), BR-HR-023 (phạm vi).
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN nhân sự A có 1 bằng, 2 chứng chỉ (1 hết hạn), 1 ủy quyền pH còn hiệu lực WHEN xem tab năng lực tổng hợp THEN hiển thị đủ, chứng chỉ hết hạn đánh dấu, ủy quyền pH "còn hiệu lực".
  - AC2 (RBAC — staff own): GIVEN staff B xem năng lực tổng hợp của A THEN theo phạm vi (mặc định không, OQ#1b); xem của chính B THEN được.
  - AC3 (không lộ lương): GIVEN tab năng lực tổng hợp WHEN render THEN KHÔNG chứa trường lương (tách field-level).
- **Data cần thiết:** join `competences` + `publications`/`project_members`/... của user.
- **API cần:** "lấy hồ sơ năng lực tổng hợp của nhân sự".

---

### FR-HR-020: Xuất hồ sơ năng lực nhân sự (PDF) — minh chứng §6.2

- **Mô tả:** Xuất PDF "Hồ sơ năng lực nhân sự" gồm thông tin cơ bản (KHÔNG lương), bằng cấp, chứng chỉ, ủy quyền thử nghiệm, thành tích NCKH — phục vụ lưu hồ sơ và xuất trình khi đánh giá VILAS §6.2.
- **Độ ưu tiên:** P2 (nice — nâng cao trải nghiệm audit VILAS)
- **Actor:** Admin, Ban lãnh đạo; Staff xuất của chính mình.
- **Tiền điều kiện:** hồ sơ + năng lực tồn tại.
- **Luồng chính:**
  1. User mở hồ sơ năng lực tổng hợp → "Xuất PDF".
  2. Hệ thống sinh PDF (template có logo lab) → trả file → audit `HR_COMPETENCE_EXPORT`.
- **Luồng phụ / ngoại lệ:**
  - A1: hồ sơ thiếu năng lực → vẫn xuất, ghi "chưa có dữ liệu năng lực" (không chặn).
- **Hậu điều kiện:** PDF phản ánh đúng dữ liệu; lượt xuất audit.
- **Business Rules:** BR-HR-004, BR-HR-023.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN nhân sự A có năng lực WHEN xuất PDF THEN PDF chứa bằng/chứng chỉ/ủy quyền/thành tích, KHÔNG chứa lương, audit `HR_COMPETENCE_EXPORT`.
  - AC2 (RBAC — staff own): GIVEN staff B xuất PDF của A THEN theo phạm vi (mặc định không, OQ#1b); của chính B THEN được.
- **Data cần thiết:** như FR-HR-019.
- **API cần:** "xuất PDF hồ sơ năng lực nhân sự".

---

## 4. Business Rules

| ID | Quy tắc | Lý do nghiệp vụ | Hệ quả nếu vi phạm |
|----|---------|-----------------|--------------------|
| BR-HR-001 | `hr_profiles` quan hệ **1-1** với `users` (`user_id` PK/FK); mỗi user tối đa 1 hồ sơ; M4 KHÔNG tạo bảng người dùng riêng | Hồ sơ gắn danh tính đăng nhập M7; tránh trùng nhân sự | 409 `HR_PROFILE_EXISTS` / 422 `USER_NOT_FOUND` |
| BR-HR-002 | **Trường lương + lịch sử lương bị strip khỏi response API** cho người không đủ quyền; staff chỉ nhận trường lương của **chính mình**; lọc ở tầng API (không chỉ ẩn FE) | Cách ly tài chính nhân sự (B03); lương là dữ liệu nhạy cảm | Rò rỉ lương → vi phạm bảo mật/quyền riêng tư (OWASP A01) |
| BR-HR-003 | Người được xem lương: Admin / Ban lãnh đạo / Kế toán (toàn hệ thống) + **chính chủ** (staff xem lương của mình). Staff KHÔNG xem lương người khác kể cả cùng phòng | demo-scope dòng 143 (Nhân sự — lương: staff = 👁 của mình) | 403 / strip field |
| BR-HR-004 | Mọi thay đổi hồ sơ nhân sự / năng lực / lương / HĐ / ủy quyền / thành tích ghi `audit_logs` (user, action, resource, resource_id, correlation_id, ip, at, detail đã LỌC PII) | 17025 §6.2 (hồ sơ năng lực kiểm soát) + §8.4 (kiểm soát hồ sơ) — duy trì VILAS | Thiếu audit → vi phạm VILAS khi đánh giá lại |
| BR-HR-005 | `next_salary_raise_date` = (`last_salary_raise_date` ?? `contract_signed_date`) + `salary_cycle_years` năm; **tự tính lại** khi bất kỳ input thay đổi; KHÔNG nhập tay; cộng-năm an toàn năm nhuận (29/02 → 28/02) | R12 — nhắc nâng lương đúng chu kỳ; tránh người dùng nhập sai mốc | Nhắc sai/thiếu → bỏ lỡ nâng lương |
| BR-HR-006 | Chức danh bắt buộc; trường PII (CMND/CCCD, tài khoản NH, ngày sinh) chỉ admin/accountant + chính chủ xem (theo OQ#2b) | Thông tin tối thiểu hồ sơ; bảo vệ PII (logging.md) | 400 thiếu chức danh; rò rỉ PII nếu không lọc |
| BR-HR-007 | `contract_end_date` (nếu có) phải > `contract_signed_date` | Logic thời gian hợp đồng | 422 `INVALID_DATE_ORDER` |
| BR-HR-008 | Lịch sử nâng lương **append-only** (immutable): không sửa/xóa bản ghi; sửa sai = thêm bản ghi điều chỉnh; mỗi bản ghi có old/new + ngày + người | Truy vết quá trình lương; hồ sơ không tẩy xóa (§8.4) | Không có endpoint sửa/xóa (404/405); vi phạm toàn vẹn hồ sơ |
| BR-HR-009 | HĐ vô thời hạn (`contract_end_date` NULL) → CRON-4 bỏ qua | Không có mốc hết hạn để nhắc | Nhắc sai cho HĐ vô thời hạn |
| BR-HR-010 | `next_salary_raise_date` NULL (thiếu cả last raise lẫn contract_signed_date) → CRON-3 bỏ qua | Không có base để tính mốc | Nhắc sai/lỗi cron |
| BR-HR-011 | `salary_cycle_years` là số nguyên ≥ 1, mặc định 3 (C04), cấu hình được mỗi hồ sơ | Cho ngoại lệ chu kỳ (OQ#4) mà vẫn mặc định 3 | 400 `INVALID_CYCLE` |
| BR-HR-012 | File minh chứng năng lực: chỉ loại cho phép (PDF/PNG/JPG) + ≤ giới hạn (OQ#12) | An toàn lưu trữ (đồng bộ M2 BR-CHEM-013) | 422 `INVALID_FILE_TYPE`/`FILE_TOO_LARGE` |
| BR-HR-013 | Cron (CRON-3/CRON-4): mỗi (hồ sơ × mốc × ngày) chỉ phát 1 notification; idempotent | Chống trùng khi cron retry/chạy lại (đồng bộ M2 BR-CHEM-021) | Spam thông báo → user bỏ qua |
| BR-HR-014 | Người nhận: CRON-3 = HR (admin/leader có `hr:manage`) + **chính nhân sự** + lãnh đạo; CRON-4 = HR (+ nhân sự theo OQ#10) | R12 — đúng người cần biết để xử lý | Nhắc sai người → bỏ lỡ |
| BR-HR-015 | Cấp đề tài / chỉ số bài báo / loại HĐ / loại hướng dẫn SV là **danh mục (enum)**; giá trị nhập phải thuộc danh mục đã cấu hình | Chuẩn hóa thống kê (R17–R19); danh mục do KH chốt (OQ#3/#5/#6/#7) | 400 `INVALID_*` |
| BR-HR-016 | Đề tài bắt buộc có **đúng 1 chủ nhiệm** (`lead_user_id`); thành viên n-n; không trùng 1 user 2 lần trong cùng đề tài | R17 — chủ nhiệm là bắt buộc; tránh đếm trùng thành viên | 400 `LEAD_REQUIRED` / 409 trùng thành viên |
| BR-HR-017 | Bài báo: DOI (nếu có) đúng định dạng `10.xxxx/...`; chỉ số thuộc danh mục | Chuẩn hóa truy vết bài báo (R17) | 400 `INVALID_INDEX` / DOI sai |
| BR-HR-018 | `author_order` duy nhất trong một bài báo/sáng chế; tác giả là quan hệ n-n | Thứ tự tác giả không trùng (R17) | 422 `DUPLICATE_AUTHOR_ORDER` |
| BR-HR-019 | Số bằng sáng chế (`patent_no`) duy nhất (khi type=patent) | Tránh trùng bằng sáng chế | 409 `DUPLICATE_PATENT_NO` |
| BR-HR-020 | Loại hướng dẫn SV / môn học theo danh mục; tránh trùng (mentor/user + nội dung + năm/kỳ) | Chuẩn hóa + tránh đếm trùng (R18/R19) | 400/409 |
| BR-HR-021 | Lượt SV đăng ký lab: cấu trúc đầy đủ (SV, người hướng dẫn, thời gian, mục đích); cần duyệt hay không theo OQ#8; chỉ lượt `approved` (nếu bật duyệt) được tính thống kê | R18 — đếm đúng lượt hợp lệ | Đếm sai số lượt |
| BR-HR-022 | Mọi thành tích gắn được cho cá nhân (thành viên/tác giả) + phòng (`department_id`); thống kê quy theo cá nhân/tập thể/phòng; thiếu phòng → gom "Không gắn phòng" | R17 — yêu cầu thống kê 3 chiều | Báo cáo năng lực §6.2 sai/thiếu |
| BR-HR-023 | Phạm vi đọc thành tích/năng lực theo RBAC scope: Admin/Lãnh đạo `all`; staff `own` (chỉ của mình). Kế toán KHÔNG truy cập thành tích NCKH | demo-scope dòng 144 (thành tích: Kế toán = —, staff = của mình) | 403; rò rỉ dữ liệu chéo |
| BR-HR-024 | KHÔNG ghi giá trị PII (CMND/CCCD, số tài khoản) và lương cụ thể vào `audit_logs.detail`/log/Sentry; chỉ ghi fact "đã thay đổi trường X" (chính sách old/new theo OQ#2b) | rule logging.md (không log PII); bảo vệ dữ liệu nhạy cảm | Rò rỉ PII qua log → vi phạm |

---

## 5. Use Case chính

### UC-HR-01: Tạo hồ sơ nhân sự + tính ngày nâng lương kế tiếp
- **Actor chính:** Kế toán / Admin.
- **Tiền điều kiện:** user "A" đã có tài khoản M7.
- **Luồng:**
  1. Kế toán tạo hồ sơ cho A: chức danh "KTV chính", ngày vào làm.
  2. Nhập hợp đồng: `contract_signed_date`=01/01/2024, loại HĐ, `contract_end_date`=31/12/2026.
  3. Để `salary_cycle_years`=3 (mặc định C04); chưa nâng lương → hệ thống tự tính `next_salary_raise_date`=01/01/2027 (base = contract_signed_date).
  4. Audit `HR_PROFILE_CREATE` + `HR_CONTRACT_UPDATE`.
- **Hậu điều kiện:** hồ sơ sẵn sàng; CRON-3 sẽ nhắc khi gần 01/01/2027; CRON-4 nhắc gần 31/12/2026.
- **Liên kết FR:** FR-HR-001, FR-HR-003, FR-HR-005, FR-HR-006.

### UC-HR-02: Cron nhắc tới hạn nâng lương (CRON-3)
- **Actor chính:** hệ thống (CRON-3) → HR + chính nhân sự + lãnh đạo.
- **Luồng:**
  1. 07:00 hằng ngày, cron acquire Redis lock.
  2. Quét hồ sơ `next_salary_raise_date` còn 15/7/3 ngày.
  3. Với hồ sơ A còn 7 ngày → tạo notification `SALARY_RAISE_DUE` mốc-7 cho HR + A + lãnh đạo; chống trùng (hồ sơ × mốc × ngày).
  4. HR mở thông báo → vào hồ sơ A → ghi nhận nâng lương (FR-HR-004) → `last_salary_raise_date` cập nhật → `next_salary_raise_date` tự tính lại +3 năm.
- **Liên kết FR:** FR-HR-008, FR-HR-004, FR-HR-005.

### UC-HR-03: Cron nhắc hết hạn hợp đồng (CRON-4)
- **Actor chính:** hệ thống (CRON-4) → HR.
- **Luồng:**
  1. 07:00 cron quét `contract_end_date` còn 30/15/7 ngày (bỏ qua HĐ vô thời hạn).
  2. Tạo notification `CONTRACT_EXPIRY` cho HR; chống trùng.
  3. HR xử lý: gia hạn HĐ (cập nhật `contract_end_date` mới — FR-HR-003) hoặc chuẩn bị tái ký.
- **Liên kết FR:** FR-HR-009, FR-HR-003.

### UC-HR-04: Thêm bài báo gắn đồng tác giả (n-n + thứ tự)
- **Actor chính:** Ban lãnh đạo / Admin (hoặc staff khai bài của mình).
- **Luồng:**
  1. Tạo bài báo: tên, tạp chí, năm, DOI, chỉ số "Scopus Q1".
  2. Thêm tác giả theo thứ tự: A (#1, corresponding), B (#2), C (#3) — quan hệ n-n.
  3. Hệ thống validate chỉ số ∈ danh mục + `author_order` không trùng → lưu `publications` + `publication_authors` → audit.
- **Ngoại lệ:** trùng thứ tự → 422 `DUPLICATE_AUTHOR_ORDER`.
- **Hậu điều kiện:** bài báo quy được cho A/B/C (cá nhân) + phòng (tập thể) để thống kê.
- **Liên kết FR:** FR-HR-011, FR-HR-013.

### UC-HR-05: Thêm đề tài NCKH gắn chủ nhiệm + thành viên
- **Actor chính:** Ban lãnh đạo / Admin.
- **Luồng:**
  1. Tạo đề tài: tên, chủ nhiệm = A, cấp "Cấp trường", 2026–2028, phòng Hóa.
  2. Thêm thành viên: A (chủ nhiệm), B, C (n-n) với `role_in_project`.
  3. Validate cấp ∈ danh mục + có chủ nhiệm → lưu → audit `RESEARCH_PROJECT_CREATE`.
- **Liên kết FR:** FR-HR-010, FR-HR-013.

### UC-HR-06: Thống kê thành tích cá nhân/phòng phục vụ báo cáo năng lực §6.2
- **Actor chính:** Ban lãnh đạo (toàn hệ thống) / Staff (của mình).
- **Luồng:**
  1. Chọn chiều "phòng" + năm 2025 + bộ lọc.
  2. Hệ thống tổng hợp: đề tài (theo cấp), bài báo (theo chỉ số), sáng chế, hướng dẫn SV, lượt SV đăng ký lab, môn học, phục vụ cộng đồng — theo phạm vi quyền.
  3. Xuất Excel/PDF báo cáo năng lực → audit `RESEARCH_REPORT_EXPORT`.
- **Ngoại lệ:** staff cố xem phòng/người khác → chỉ trả dữ liệu của chính mình.
- **Liên kết FR:** FR-HR-018, FR-HR-019, FR-HR-020.

---

## 6. Yêu cầu phi chức năng (NFR)

Theo template `~/.claude/rules/nfr.md`. Con số định cỡ cho quy mô **~40 user** (C03), môi trường staging tương đương production (Docker Compose, ~2–4 vCPU/8GB). Giả định cao điểm: ~10 concurrent users. M4 ít ghi nóng (không như POS/giao dịch hóa chất) — chủ yếu CRUD + thống kê + cron nhẹ.

```
NFR-PERF-HR-001: Đọc hồ sơ nhân sự & danh sách
────────────────────────────────────────────────────
Mô tả:     API xem chi tiết hồ sơ + liệt kê nhân sự (đã lọc trường lương
           theo quyền) phải nhanh cho thao tác quản lý hằng ngày.
Metric:    P95 < 400ms cho chi tiết; P95 < 500ms cho danh sách phân trang 20/trang
Tool đo:   k6 (tests/performance/hr-read.js)
Điều kiện: 10 concurrent users, dataset ~200 hồ sơ (đệm cho mở rộng), staging
Pass:      p(95) < 500ms; query dùng index (department_id, user_id)
Fail:      p(95) ≥ 500ms → thêm index / tối ưu join lọc field
Ưu tiên:  Should Have
```
```
NFR-PERF-HR-002: Thống kê / tổng hợp thành tích
────────────────────────────────────────────────────
Metric:    P95 < 3000ms cho thống kê 1 năm, 1 phòng (đề tài/bài báo/SV/...)
Tool đo:   k6 (tests/performance/hr-report.js)
Điều kiện: 5 concurrent users (lãnh đạo), dataset đầy đủ ~ vài nghìn bản ghi thành tích
Pass:      p(95) < 3000ms; nếu vượt → cân nhắc cache/materialized view
Fail:      p(95) ≥ 3000ms → tối ưu aggregate / async export
Ưu tiên:  Should Have
```
```
NFR-CRON-HR-001: Đúng giờ & idempotent CRON-3/CRON-4
────────────────────────────────────────────────────
Mô tả:     Cron nhắc nâng lương / hết hạn HĐ chạy đúng 07:00, không trùng,
           không sót, không spam.
Metric:    Với tập hồ sơ tới mốc 15/7/3 (lương) & 30/15/7 (HĐ): tạo đúng
           1 notification/(hồ sơ × mốc × ngày); chạy lại cùng ngày KHÔNG sinh thêm.
Tool đo:   Test tự động: seed hồ sơ tới mốc, chạy cron 2 lần/ngày, đếm notification
Điều kiện: Redis lock; nhiều instance giả lập
Pass:      Số notification = số (hồ sơ × mốc) tới hạn; 0 trùng; lock đảm bảo 1 instance chạy
Fail:      Trùng/sót/không lock → fix dedup + lock (đồng bộ M2 CRON-6)
Ưu tiên:  Must Have
```
```
NFR-CORRECT-HR-001: Chính xác tính ngày nâng lương (Must — đặc thù domain)
────────────────────────────────────────────────────
Mô tả:     next_salary_raise_date tính đúng theo BR-HR-005, kể cả năm nhuận.
Metric:    Với mọi (base_date, cycle): next = base + cycle năm; 29/02 + n năm
           (năm đích không nhuận) → 28/02; tự tính lại khi input đổi. Sai = 0.
Tool đo:   Test tự động property-based: nhiều base_date (gồm 29/02) × cycle 1..5
Pass:      0 trường hợp sai ngày trên toàn bộ tập sinh
Fail:      Bất kỳ sai ngày nào → bug (nhắc sai mốc) → block release
Ưu tiên:  Must Have
```
```
NFR-SEC-HR-001: Cách ly trường lương + PII field-level (Must — cốt lõi)
────────────────────────────────────────────────────
Mô tả:     Trường lương + lịch sử lương + PII bị strip ở tầng API cho người
           không đủ quyền; staff chỉ thấy của chính mình.
Metric:    Ma trận test 4 vai trò × các endpoint M4 pass 100%; trong MỌI response
           (chi tiết + danh sách + thống kê + export), staff KHÔNG nhận trường
           lương/PII của người khác; Kế toán KHÔNG truy cập thành tích NCKH.
Tool đo:   Test RBAC tự động (security-auditor) + manual; kiểm tra body response
Pass:      0 rò rỉ trường lương/PII cho người không đủ quyền; 0 bypass scope
Fail:      Bất kỳ rò rỉ/bypass → block go-live (OWASP A01)
Ưu tiên:  Must Have
```
```
NFR-SEC-HR-002: Không log PII/lương (Must)
────────────────────────────────────────────────────
Metric:    0 bản ghi audit_logs.detail / log / Sentry chứa CMND/CCCD đầy đủ,
           số tài khoản đầy đủ, giá trị lương cụ thể (trừ chính sách old/new
           chốt ở OQ#2b — nếu ghi thì chỉ trong audit, không ra log/Sentry).
Tool đo:   Rà log + test ghi audit khi đổi PII/lương
Pass:      Audit ghi fact "đã đổi trường X" không kèm giá trị nhạy cảm ra log
Fail:      Tồn tại PII/lương trong log → fix lọc (rule logging.md)
Ưu tiên:  Must Have
```
```
NFR-AUDIT-HR-001: Đầy đủ audit thay đổi hồ sơ năng lực (VILAS §6.2/§8.4) (Must)
────────────────────────────────────────────────────
Mô tả:     Mọi thay đổi hồ sơ/năng lực/lương/HĐ/ủy quyền/thành tích ghi audit.
Metric:    100% thao tác ghi (create/update/raise/competence change/...) có bản
           ghi audit_logs với correlation_id; lịch sử lương immutable (0 endpoint
           sửa/xóa salary_history).
Tool đo:   Test tự động đếm audit/thao tác + rà route
Pass:      Tỷ lệ audit/thao tác = 100%; salary_history append-only
Fail:      < 100% hoặc có route sửa lịch sử lương → block (vi phạm §6.2/§8.4)
Ưu tiên:  Must Have
```
```
NFR-CORRECT-HR-002: Tính toàn vẹn quan hệ n-n thành tích (Should)
────────────────────────────────────────────────────
Metric:    Đếm thành tích theo cá nhân/phòng không trùng/không sót: 1 bài báo
           n tác giả đếm đúng cho từng tác giả & đúng 1 lần cho phòng; author_order
           duy nhất/bài; thành viên không trùng/đề tài.
Tool đo:   Test tự động: seed thành tích n-n, đối chiếu thống kê
Pass:      Số liệu thống kê khớp seed; 0 trùng đếm
Fail:      Đếm trùng/sót → fix join/constraint
Ưu tiên:  Should Have
```
```
NFR-COMPAT-HR-001: Tiền lương NUMERIC không float (Must)
────────────────────────────────────────────────────
Metric:    current_salary + salary_history dùng NUMERIC(14,2); 0 dùng float;
           hiển thị/định dạng VND đúng (đồng bộ M2 quy ước tiền).
Tool đo:   Rà schema + test định dạng
Pass:      0 cột tiền dùng float; làm tròn nhất quán
Ưu tiên:  Must Have
```
```
NFR-MAINT-HR-001: Test coverage domain HR (Must)
────────────────────────────────────────────────────
Metric:    Service tính ngày nâng lương / field-level RBAC lương / cron dedup /
           thống kê n-n coverage ≥ 85%; module M4 overall ≥ 70%.
Tool đo:   pytest --cov
Pass:      ≥ 85% domain, ≥ 70% module; CI block nếu drop > 5%
Ưu tiên:  Must Have
```
```
NFR-SEC-HR-003: An toàn upload minh chứng năng lực (Must)
────────────────────────────────────────────────────
Metric:    Chỉ chấp nhận PDF/PNG/JPG (validate MIME thực + đuôi), ≤ giới hạn
           (OQ#12); lưu MinIO; không lưu binary DB; không thực thi file.
Tool đo:   Test upload file độc hại/sai loại/quá lớn
Pass:      File sai loại/quá lớn bị từ chối 422; file hợp lệ tải lại được
Ưu tiên:  Must Have
```
```
NFR-OBS-HR-001: Logging & truy vết (Should)
────────────────────────────────────────────────────
Metric:    Mọi request M4 có correlation_id xuyên FE→BE→audit_logs; thao tác
           nghiệp vụ ghi INFO; thay đổi lương/HĐ/năng lực ghi audit; lỗi ghi ERROR
           kèm stack (không lộ ra client; không kèm PII/lương).
Tool đo:   Rà log + test
Pass:      Trace được 1 thao tác đổi hồ sơ từ log FE → audit DB qua correlation_id
Ưu tiên:  Should Have
```

---

## 7. Giả định & Ràng buộc (tổng hợp)

**Assumptions:**
- ASSUMPTION-1: Mọi nhân sự cần quản lý đều là `users` của M7 (kể cả người không đăng nhập — tạo user `disabled` để giữ hồ sơ). Xác nhận có nhân sự "chỉ hồ sơ" không (OQ#2c).
- ASSUMPTION-2 → **CHỐT C04:** chu kỳ nâng lương mặc định 3 năm cho mọi ngạch; cấu hình được mỗi hồ sơ (OQ#4 xác nhận ngoại lệ).
- ASSUMPTION-3: Người nhận CRON-3 = HR + chính nhân sự + lãnh đạo; CRON-4 = HR (+ nhân sự theo OQ#10). "HR" = user có quyền `hr:manage` (admin/leader/accountant) — xác nhận ánh xạ (OQ#10).
- ASSUMPTION-4: Thành tích NCKH nhập tay/import file; không crawl tự động (ngoài scope).
- ASSUMPTION-5: Mức lương lưu là mức hiện hành; cấu trúc lương (số tiền tuyệt đối hay hệ số × lương cơ sở) chốt ở OQ#2.

**Constraints:** xem §2.4 (CONSTRAINT-1..9).

**Ghi chú cấu trúc dữ liệu cho `schema-designer` (đồng bộ ERD core demo-scope M4 + M7 contract):**
- `hr_profiles`: `user_id UUID PK/FK → users(id)` (1-1); `job_title`, `hired_date`, PII (theo OQ#2b — cân nhắc mã hóa/cột riêng quyền truy cập); `contract_signed_date`, `contract_type` (FK danh mục), `contract_end_date NULL`; `salary_cycle_years INT DEFAULT 3 CHECK(≥1)`; `last_salary_raise_date NULL`; `next_salary_raise_date` (tính ở app; có thể GENERATED nhưng nguồn chân lý là service); `current_salary NUMERIC(14,2) NULL`, `currency VARCHAR(3) DEFAULT 'VND'`.
- `salary_history` (MỚI — append-only): `id PK, user_id FK, old_amount NUMERIC(14,2) NULL, new_amount NUMERIC(14,2), raise_date DATE, by_user FK, note, created_at`. KHÔNG route UPDATE/DELETE (đồng bộ tinh thần immutable §8.4).
- `competences` (MỚI — gộp bằng/chứng chỉ/ủy quyền): `id PK, user_id FK, kind CHECK(degree|certificate|authorization), title, issuer, issued_date, expiry_date NULL, scope_detail (chỉ tiêu/phương pháp với authorization), authorized_by FK NULL, created_at`. Minh chứng qua `attachments(owner_type='hr_profile')`.
- `research_projects`: `id PK, title, level (FK danh mục project_levels), lead_user_id FK, department_id FK, start_date, end_date, status, created_at`.
- `project_members`: `project_id FK, user_id FK, role_in_project` — PK kép (n-n).
- `publications`: `id PK, title, journal, year, doi, index_code (FK danh mục pub_indexes) NULL, type CHECK(paper|patent), patent_no NULL (UNIQUE khi patent), issuing_authority NULL, department_id FK, created_at`.
- `publication_authors`: `publication_id FK, user_id FK, author_order, is_corresponding` — PK (publication_id, author_order) đảm bảo thứ tự duy nhất (n-n).
- `student_mentorships`: `id PK, mentor_id FK, student_name, topic, year, type (FK danh mục), department_id FK, created_at`.
- `lab_registrations`: `id PK, student_name, mentor_id FK, registered_from, registered_to NULL, purpose, status (NULL/pending/approved/rejected theo OQ#8), department_id FK, created_at`.
- `teaching_courses`: `id PK, user_id FK, course_name, semester, year, department_id FK, created_at`.
- `community_services`: `id PK, content, performed_at, host, performer_user_id FK, department_id FK, created_at`.
- **Bảng danh mục (MỚI — enum dữ liệu):** `contract_types`, `project_levels`, `pub_indexes`, `mentorship_types` — seed giá trị do KH chốt (OQ#3/#5/#6/#7); cho admin cấu hình thêm (đồng bộ tinh thần danh mục `units` M2).
- Index gợi ý: `hr_profiles(next_salary_raise_date)` partial NOT NULL (CRON-3); `hr_profiles(contract_end_date)` partial NOT NULL (CRON-4); `project_members(user_id)`, `publication_authors(user_id)` (thống kê cá nhân); `*_department_id` (thống kê phòng); `*(year)` (thống kê theo năm).

---

## 8. OPEN QUESTIONS (cần KH trả lời trước/khi `/contract`)

| # | Câu hỏi | Tại sao cần biết | Ảnh hưởng nếu chưa rõ | Người trả lời | Deadline |
|---|---------|------------------|----------------------|---------------|----------|
| 1 | **AI được phép SỬA lương / ghi nâng lương?** Chỉ Kế toán? Kế toán + Admin? Ban lãnh đạo có sửa được không hay chỉ xem? | Quyết định RBAC ghi của FR-HR-004 (rủi ro tài chính — không tự quyết) | Sai người sửa lương → rủi ro tài chính/pháp lý | KH (Ban lãnh đạo + Kế toán) | **trước `/contract`** |
| 1b | Staff có được xem **thông tin phi-tài-chính** (chức danh, năng lực) của **người khác cùng phòng** không, hay chỉ của chính mình hoàn toàn? | Quyết định scope đọc hồ sơ/năng lực (BR-HR-003, BR-HR-023) | Lộ/giấu thông tin sai phạm vi | KH (Ban lãnh đạo) | trước `/contract` |
| 1c | Staff có được **tự cập nhật** thông tin liên hệ của chính mình (SĐT) không? | Phạm vi ghi của FR-HR-002 | Quyền tự sửa không rõ | KH (HR) | có thể chốt khi UAT |
| 1d | Cho phép ghi nhận **nâng lương ngày trong tương lai** (đặt lịch) không? | Validate FR-HR-004 A1 | Logic ngày nâng lương | KH (Kế toán) | có thể chốt khi UAT |
| 2 | **Cấu trúc lương:** lưu số tiền tuyệt đối (NUMERIC VND) hay theo hệ số × lương cơ sở (ngạch/bậc)? Có cần ngạch/bậc lương nhà nước không? | Quyết định schema lương (FR-HR-004) | Schema lương sai → làm lại | KH (Kế toán) | **trước `/contract`** |
| 2b | **Chính sách PII & audit lương:** trường PII nào lưu (CMND/CCCD, ngày sinh, số TK NH)? Ai xem? Audit có ghi giá trị lương cũ/mới không hay chỉ ghi "đã đổi"? | Bảo vệ PII (logging.md, BR-HR-024); xác định cột nhạy cảm | Rò rỉ PII / audit thiếu | KH (Ban lãnh đạo + Kế toán) | **trước `/contract`** |
| 2c | Có nhân sự **"chỉ hồ sơ, không tài khoản đăng nhập"** không? (ảnh hưởng cách tạo user disabled để giữ hồ sơ) | ASSUMPTION-1, FR-HR-001 A2 | Quy trình tạo hồ sơ | KH (HR) | trước `/contract` |
| 3 | **Danh mục loại hợp đồng** (HĐ thử việc / xác định thời hạn / không xác định thời hạn / hợp đồng làm việc viên chức / ...)? | Seed danh mục `contract_types` (BR-HR-015) | Không seed được danh mục | KH (HR) | trước `/contract` (có thể bổ sung khi UAT) |
| 4 | **Chu kỳ nâng lương** có ngoại lệ thực tế không (ngạch nào khác 3 năm)? Nếu có thì những giá trị nào? | Mặc định 3 (C04) đã chốt; xác nhận có cấu hình khác | Cấu hình `salary_cycle_years` thừa/thiếu | KH (Kế toán) | có thể chốt khi UAT |
| 5 | **Danh mục cấp đề tài NCKH** có những mức nào? (cấp cơ sở/trường, cấp bộ, cấp tỉnh, cấp nhà nước, hợp tác quốc tế, ...) | Seed `project_levels` (BR-HR-015) | Thống kê đề tài theo cấp sai | KH (Phòng NCKH) | trước `/contract` (có thể bổ sung khi UAT) |
| 6 | **Danh mục chỉ số bài báo** (ISI/SCIE/SSCI/ESCI, Scopus + phân hạng Q1–Q4, trong nước có/không tính điểm HĐ GS, ...)? | Seed `pub_indexes` (BR-HR-017) | Thống kê bài báo theo chỉ số sai | KH (Phòng NCKH) | trước `/contract` (có thể bổ sung khi UAT) |
| 6b | Cho phép nhập bài báo **chưa xuất bản / năm tương lai** (accepted) không? | Validate FR-HR-011 A4 | Logic năm bài báo | KH (Phòng NCKH) | có thể chốt khi UAT |
| 7 | **Danh mục loại hướng dẫn SV** (khóa luận ĐH, luận văn ThS, luận án TS, NCKH SV, đồ án, ...)? | Seed `mentorship_types` (BR-HR-020) | Thống kê hướng dẫn SV sai | KH (Phòng đào tạo) | trước `/contract` (có thể bổ sung khi UAT) |
| 8 | **Lượt SV đăng ký vào lab có cần DUYỆT không?** (chỉ ghi nhận, hay pending→approved bởi lãnh đạo/trưởng nhóm?) | Quyết định trạng thái + workflow FR-HR-015 | Có/không workflow duyệt | KH (Ban lãnh đạo) | trước `/contract` |
| 8b | Staff khai thành tích có được **gắn người khác** làm đồng tác giả/thành viên không, hay chỉ khai phần mình & admin/leader mới gắn người khác? Khai thành tích staff có cần **duyệt** trước khi tính thống kê không? | Quyết định scope ghi `research:manage own` + workflow duyệt | Đếm thành tích sai/khai khống | KH (Phòng NCKH) | trước `/contract` |
| 8c | Tác giả/thành viên/hướng dẫn có thể là **người NGOÀI hệ thống** (không phải user nội bộ) không? (vd đồng tác giả ngoài trường) | Quyết định cho phép lưu tên tự do hay bắt buộc FK user | Schema tác giả (FK vs free-text) | KH (Phòng NCKH) | trước `/contract` |
| 9 | Báo cáo tiêu hao hóa chất "theo đề tài" (M2 FR-CHEM-014) cần **gắn mẫu vào đề tài NCKH** — có quản lý liên kết mẫu↔đề tài không? Nếu có, gắn ở đâu (mẫu chọn đề tài khi tạo)? | Liên kết M1↔M4 cho báo cáo theo đề tài | Báo cáo "theo đề tài" của M2 không chạy được | KH (Ban lãnh đạo) | trước khi làm M2 báo cáo đề tài |
| 10 | CRON-4 (hết hạn HĐ) **gửi cho ai** — chỉ HR, hay cả chính nhân sự + lãnh đạo? "HR" ánh xạ cụ thể tới vai trò/người nào? | Người nhận FR-HR-009 (BR-HR-014) | Nhắc sai/thiếu người | KH (HR + Ban lãnh đạo) | có thể chốt khi UAT |
| 11 | Có cần **cron nhắc chứng chỉ/ủy quyền năng lực sắp hết hạn** không (§6.2 — năng lực hết hiệu lực ảnh hưởng VILAS)? | Mở rộng cron cho năng lực (FR-HR-007 A1) | Bỏ lỡ chứng chỉ/ủy quyền hết hạn → rủi ro VILAS | KH (Ban lãnh đạo/QA lab) | có thể chốt khi UAT (CR nếu thêm cron mới) |
| 12 | **Giới hạn dung lượng & loại file** minh chứng năng lực (bằng/chứng chỉ) (vd ≤ 20MB, PDF/ảnh)? | Cấu hình MinIO + validate (BR-HR-012) | Không validate file | KH (IT) | trước `/contract` (đồng bộ M2 OQ#7) |

> **Trạng thái:** Các câu **#1, #2, #2b, #5, #6, #7, #8, #8b, #8c, #12** ảnh hưởng **schema/RBAC lõi** → nên chốt **trước `/contract`**. Các câu danh mục (#3/#5/#6/#7) có thể **seed bổ sung khi UAT** nếu chốt được cấu trúc bảng danh mục trước. Các câu vận hành (#1c/#1d/#4/#6b/#10/#11) có thể chốt khi UAT, không chặn ERD lõi.

---

## 9. Ma trận truy vết (Traceability Matrix)

| FR ID | Yêu cầu gốc (meeting note) | Submodule (demo-scope) | Điều khoản 17025 | Business Rule | Test Case (QA sẽ tạo) | Trạng thái |
|-------|----------------------------|------------------------|------------------|---------------|------------------------|------------|
| FR-HR-001 | R12 | F4.1.1 | §6.2 | BR-001, 002, 004, 006 | TC-HR-001..005 | Draft |
| FR-HR-002 | R12 | F4.1.1 | §6.2, §8.4 | BR-002, 004, 024 | TC-HR-006..009 | Draft |
| FR-HR-003 | R12 | F4.1.2 | §6.2 | BR-005, 007, 009 | TC-HR-010..014 | Draft |
| FR-HR-004 | R12 | F4.1.3 | §6.2, §8.4 | BR-002, 003, 005, 008, 004, 024 | TC-HR-015..022 | Draft |
| FR-HR-005 | R12 | F4.1.3 | §6.2 | BR-005, 010 | TC-HR-023..028 | Draft |
| FR-HR-006 | R12, **C04** | F4.1.3 | §6.2 | BR-005, 011 | TC-HR-029..032 | Draft |
| FR-HR-007 | 17025 §6.2 (năng lực) | F4.1.4 | **§6.2**, §8.4 | BR-004, 012 | TC-HR-033..038 | Draft |
| FR-HR-008 | R12 (CRON-3) | F4.2.1 | §6.2 | BR-010, 013, 014 | TC-HR-039..044 | Draft |
| FR-HR-009 | R12 (CRON-4) | F4.2.2 | §6.2 | BR-009, 013, 014 | TC-HR-045..049 | Draft |
| FR-HR-010 | R17 | F4.3.1 | §6.2 | BR-015, 016, 022 | TC-HR-050..056 | Draft |
| FR-HR-011 | R17 | F4.3.2 | §6.2 | BR-017, 018, 022 | TC-HR-057..063 | Draft |
| FR-HR-012 | R17 | F4.3.3 | §6.2 | BR-018, 019, 022 | TC-HR-064..067 | Draft |
| FR-HR-013 | R17 | F4.3.4 | §6.2 | BR-022 | TC-HR-068..071 | Draft |
| FR-HR-014 | R18 | F4.3.5 | §6.2 | BR-020, 022 | TC-HR-072..076 | Draft |
| FR-HR-015 | R18 | F4.3.6 | §6.2 | BR-021, 022 | TC-HR-077..082 | Draft |
| FR-HR-016 | R19 | F4.3.7 | §6.2 | BR-020, 022 | TC-HR-083..086 | Draft |
| FR-HR-017 | R20 | F4.3.8 | §6.2 | BR-022 | TC-HR-087..090 | Draft |
| FR-HR-018 | R17, R18, R19, R20 | F4.3.x | **§6.2** (báo cáo năng lực) | BR-022, 023 | TC-HR-091..097 | Draft |
| FR-HR-019 | 17025 §6.2 | F4.1.4, F4.3.x | **§6.2** | BR-004, 023 | TC-HR-098..101 | Draft |
| FR-HR-020 | 17025 §6.2 | F4.1.4 | **§6.2** | BR-004, 023 | TC-HR-102..104 | Draft |

**Mapping cron:** FR-HR-008 ↔ CRON-3, FR-HR-009 ↔ CRON-4 (`01-demo-scope.md` mục D).
**Mapping điều khoản 17025 (demo-scope mục E):** §6.2 (nhân sự, năng lực, ủy quyền) — phủ bởi FR-HR-007/019/020 (hồ sơ năng lực) + FR-HR-018 (báo cáo năng lực) + audit mọi thay đổi (BR-HR-004); §8.4 (kiểm soát hồ sơ) — phủ bởi audit append-only + lịch sử lương immutable.
**Phụ thuộc M7:** `hr_profiles.user_id` FK→`users`; quyền `hr:read`/`hr:manage`/`research:manage` đã seed trong `roles_permissions` (M7 §5.2); `notifications` + `idx_notif_ref` cho CRON-3/4 chống trùng; `attachments(owner_type='hr_profile'|'publication')` đã có trong whitelist M7 (M7 §2 attachments CHECK).

---

*Hết SRS M4 (v1.0). Bối cảnh đã chốt (4 vai trò, RBAC field-level lương, chu kỳ 3 năm C04, in-app C02, ~40 user C03). Còn 9 OPEN QUESTIONS — quan trọng nhất cần KH chốt TRƯỚC `/contract`: (#1) ai được sửa lương; (#2/#2b) cấu trúc lương + chính sách PII/audit lương; (#5/#6/#7) danh mục cấp đề tài / chỉ số bài báo / loại hướng dẫn SV; (#8) lượt SV đăng ký lab có cần duyệt; (#8b/#8c) staff gắn người khác/tác giả ngoài hệ thống. Các câu còn lại là tham số vận hành/danh mục, có thể chốt khi UAT.*
