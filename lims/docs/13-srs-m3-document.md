# SRS: M3 — Quản lý Tài liệu (Document Control)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M3 — Quản lý Tài liệu (Document Control)
**Version:** 1.0 | **Ngày:** 20/06/2026 | **Author:** BA agent
**Status:** DRAFT — bối cảnh đã chốt (4 vai trò, RBAC + phạm vi phòng ban, MinIO C01, in-app only C02, ~40 user C03, lab ĐÃ công nhận VILAS → document/record control CHẶT). Còn 8 OPEN QUESTIONS (§8) — phần lớn là tham số cấu hình/biến thể luồng có default, không chặn ERD/state machine lõi.
**Nguồn:** `00-meeting-note-analysis.md` (R2 "kèm file", R3 "tài liệu — lịch sử/version + approval workflow", R11 "lưu trữ tối ưu → object storage", R15 "thống kê lượt truy cập/tải/chỉnh sửa"; quyết định chốt C01/C02/C03, B03), `01-demo-scope.md` (M3.1–M3.3, RBAC matrix mục B, ERD core M3 mục C, mapping 17025 §8.3/§8.4 mục E), `08-contract-m7-schema.md` (users/departments/attachments/audit_logs/notifications dùng chung; quyền `document:create`/`document:read`/`document:approve` đã seed; M3 tự tạo `document_access_log` riêng)
**Chuẩn:** IEEE 830 (rút gọn) · ISO/IEC 17025:2017 §8.3 (kiểm soát tài liệu), §8.4 (kiểm soát hồ sơ)

---

## Changelog

| Version | Ngày | Thay đổi |
|---------|------|----------|
| 1.0 | 20/06/2026 | Bản DRAFT đầu tiên — 16 FR, 22 BR, 5 UC, 13 NFR, 8 OPEN QUESTIONS. Đồng bộ phong cách SRS M1/M4: state machine version (draft→review→approved→obsolete) theo pattern state machine mẫu M1; tách quyền soạn–duyệt theo pattern `SELF_APPROVAL_FORBIDDEN` của M1 (BR-SAMPLE-011); immutable version đã approved theo pattern kết quả approved bất biến M1 (BR-SAMPLE-010); trưởng nhóm cố định theo phòng ban (`departments.lead_user_id`) tái dùng OQ#11 M1. |

---

## 1. Giới thiệu

### 1.1 Mục đích

Tài liệu này đặc tả đầy đủ, không mơ hồ, kiểm thử được cho **Module M3 — Quản lý Tài liệu (Document Control)** của hệ thống LIMS. Mục tiêu nghiệp vụ:

1. **Số hóa kho tài liệu hệ thống quản lý chất lượng (QMS) của lab:** SOP, quy trình, biểu mẫu, hướng dẫn công việc, tiêu chuẩn/quy chuẩn — thay tủ hồ sơ giấy + thư mục file rời rạc bằng kho tập trung, phân loại, tìm kiếm được, đính kèm file lưu MinIO (R2, R11).
2. **Kiểm soát tài liệu theo ISO/IEC 17025:2017 §8.3 (VILAS BẮT BUỘC):** mọi tài liệu có **quy trình duyệt/ban hành** chuẩn (draft → review → approved → obsolete); người soạn ≠ người duyệt (tách trách nhiệm §8.3.2); **chỉ phiên bản "hiệu lực" (approved/current) được sử dụng**; phiên bản cũ tự động chuyển obsolete khi ban hành phiên bản mới; **không sửa phiên bản đã approved** (bất biến — sửa = tạo phiên bản mới); **lịch sử thay đổi đầy đủ** (ai tạo/sửa version nào, khi nào, change_note) (R3, §8.3).
3. **Kiểm soát hồ sơ §8.4 + thống kê truy cập (R15):** mọi thao tác tạo/sửa/duyệt/ban hành/obsolete/tải được audit; đếm **lượt xem / lượt tải / lượt chỉnh sửa** mỗi tài liệu (`document_access_log`) để báo cáo và truy vết khi đánh giá VILAS.

Tài liệu dùng cho 2 đối tượng:
- **Khách hàng / Ban lãnh đạo lab:** xác nhận nghiệp vụ đúng — đặc biệt **state machine duyệt/ban hành**, **quy tắc tách soạn–duyệt**, **chỉ bản approved được dùng**, **bản cũ obsolete tự động**.
- **Đội thiết kế (`schema-designer`, `api-designer`, `ux-designer`) và `feature-builder`:** đủ chi tiết để viết contract và implement mà không phải hỏi lại.

### 1.2 Phạm vi

Module M3 phủ 3 submodule (theo `01-demo-scope.md`):

| Submodule | Nội dung | Trong SRS này |
|-----------|----------|---------------|
| M3.1 Kho tài liệu | CRUD tài liệu (SOP, quy trình, biểu mẫu, hướng dẫn, tiêu chuẩn); đính kèm file + lưu MinIO (R2); phân loại tài liệu (loại, phòng ban, mức bảo mật) | ✅ FR-DOC-001..005 |
| M3.2 Version & Lịch sử (CỐT LÕI VILAS §8.3) | Quản lý phiên bản (v1, v2…) — mỗi version có file riêng + change_note (R3); lịch sử thay đổi (ai tạo/sửa version nào, khi nào, sửa gì); quy trình duyệt/ban hành (draft→review→approved→obsolete); người soạn ≠ người duyệt; chỉ version approved/current được dùng; approve mới → cũ obsolete tự động; version approved bất biến | ✅ FR-DOC-006..013 |
| M3.3 Thống kê truy cập tài liệu (R15) | Đếm lượt xem / lượt tải / lượt chỉnh sửa mỗi tài liệu (`document_access_log`); báo cáo thống kê truy cập | ✅ FR-DOC-014..016 |

**Trong scope `[SCOPE]`:**
- CRUD **tài liệu (`documents`)**: mã tài liệu (`code`), tiêu đề, loại (SOP/quy trình/biểu mẫu/hướng dẫn/tiêu chuẩn — danh mục, OQ#2), phòng ban sở hữu (`department_id`), mức bảo mật (`confidentiality_level` — danh mục, OQ#3), trạng thái tài liệu.
- **Phân loại tài liệu** theo loại + phòng ban + mức bảo mật; tìm kiếm / lọc / phân trang theo các tiêu chí này.
- **Quản lý phiên bản (`document_versions`)**: mỗi tài liệu có 1..n version (v1, v2…); **mỗi version có file riêng** (`file_key` lưu MinIO qua `attachments`) + `change_note` (mô tả thay đổi so với version trước) + người tạo + thời điểm tạo (R3).
- **Lịch sử thay đổi đầy đủ**: timeline các version (ai tạo, khi nào, change_note, ai duyệt, khi nào duyệt, khi nào chuyển obsolete) — dựng từ `document_versions` + `audit_logs` (R3, §8.3/§8.4).
- **Quy trình duyệt/ban hành** (state machine version): `draft → review → approved → obsolete`; reject ở review → quay lại `draft`; **người soạn ≠ người duyệt** (tách trách nhiệm §8.3.2).
- **Chỉ version "approved/current" là hiệu lực**: được tải/dùng bởi mọi người có quyền xem; version `draft`/`review` chỉ người soạn + người duyệt (trưởng nhóm/leader/admin) xem; **khi approve version mới → version approved cũ TỰ ĐỘNG chuyển obsolete** (đảm bảo tại 1 thời điểm chỉ 1 version current cho mỗi tài liệu).
- **Version approved bất biến (immutable)**: không sửa file/nội dung version đã approved; sửa = **tạo version mới** (draft) + change_note + đi lại quy trình duyệt.
- Đính kèm file lên **MinIO** qua bảng `attachments` polymorphic chung (`owner_type='document_version'` cho file của từng phiên bản; `owner_type='document'` cho file phụ trợ ở mức tài liệu nếu cần).
- **Thống kê truy cập (R15)**: đếm lượt **view / download / edit** mỗi tài liệu qua bảng riêng `document_access_log`; báo cáo tổng hợp theo tài liệu / khoảng thời gian / loại hành động.
- **Audit log §8.4**: mọi tạo/sửa/duyệt/ban hành/obsolete/tải tài liệu ghi `audit_logs` (user, action, resource, resource_id, correlation_id, ip, at, detail).

**Ngoài scope `[OUT-OF-SCOPE → cần CR]`:**
- **Chữ ký số có CA (digital signature)** trên tài liệu/version đã duyệt: hệ thống chỉ ghi **tên + chức danh + thời điểm** người soạn/người duyệt; chữ ký số PKI → CR.
- **Soạn thảo / chỉnh sửa nội dung tài liệu trực tuyến (online editor, co-authoring)**: M3 quản lý **file đính kèm** của từng version (upload bản DOCX/PDF do người dùng soạn ngoài hệ thống), KHÔNG cung cấp trình soạn thảo trong app → CR.
- **So sánh khác biệt nội dung (diff) giữa 2 version**: M3 lưu file riêng từng version + `change_note` văn bản; diff nội dung tự động → CR.
- **Workflow duyệt đa cấp / nhiều người duyệt tuần tự** (review → QA → director multi-step): bản đầu là **1 bước duyệt** bởi trưởng nhóm/leader/admin (OQ#5); đa cấp → CR.
- **Phân phối tài liệu có kiểm soát (controlled copy / acknowledgement)**: yêu cầu người dùng "đã đọc và xác nhận" SOP mới ban hành → ngoài scope bản đầu → CR (OQ#7).
- **Lịch xem xét định kỳ tài liệu (periodic review reminder)** kiểu cron nhắc rà soát SOP hằng năm: ngoài scope bản đầu → CR (OQ#8).
- **Liên kết tài liệu ↔ mẫu/phương pháp (method library của M1)**: M1 tham chiếu SOP/phương pháp ở M3 ở mức đọc; ràng buộc "mẫu phải dùng SOP version nào" → ngoài scope M3 bản đầu → CR.
- **Thông báo qua email / Zalo**: chỉ in-app (C02). Email/Zalo → CR.
- **Versioning nhị phân/khôi phục file đã xóa khỏi MinIO (object versioning bucket)**: M3 quản lý version ở tầng nghiệp vụ (DB), không bật MinIO object versioning bản đầu → CR.

### 1.3 Định nghĩa, từ viết tắt và thuật ngữ

| Thuật ngữ | Định nghĩa |
|-----------|------------|
| **Tài liệu (Document)** | Một mục tài liệu QMS của lab (`documents`): SOP, quy trình, biểu mẫu, hướng dẫn, tiêu chuẩn. Định danh bởi `code` (mã tài liệu) + tiêu đề. Là **vùng chứa của 1..n phiên bản** (`document_versions`). Bản thân tài liệu KHÔNG chứa file; file gắn vào từng version. |
| **Phiên bản (Version)** | Một lần ban hành/sửa đổi của tài liệu (`document_versions`): có số version (v1, v2…), **file riêng** (`file_key` MinIO), `change_note`, người tạo, thời điểm, trạng thái version (state machine), người duyệt. Quan hệ `documents` 1-n `document_versions`. |
| **Mã tài liệu (`code`)** | Mã hiển thị duy nhất của tài liệu (vd `SOP-HOA-012` — định dạng OQ#1), không lộ ID tuần tự nội bộ (ID thật là UUID — CONSTRAINT-5). |
| **Số phiên bản (`version`)** | Số nguyên tăng dần trong phạm vi 1 tài liệu (1, 2, 3…). Duy nhất theo `(document_id, version)`. |
| **Phiên bản hiệu lực / hiện hành (Current / Approved version)** | Phiên bản duy nhất đang ở trạng thái `approved` của một tài liệu — được phép sử dụng/tải bởi mọi người có quyền xem. `documents.current_version_id` trỏ tới version này. **Tại 1 thời điểm chỉ có TỐI ĐA 1 version approved/current cho mỗi tài liệu** (BR-DOC-008). |
| **State machine version** | Tập trạng thái hợp lệ của một version + các phép chuyển hợp lệ: `draft → review → approved → obsolete`; `review → draft` (reject). Xem §3 FR-DOC-013 và §4 BR-DOC-007. |
| **`draft` (bản nháp)** | Version đang soạn/sửa bởi người soạn; chưa gửi duyệt; chỉ người soạn + người duyệt (trưởng nhóm/leader/admin) phòng đó + Admin/Ban lãnh đạo xem được. |
| **`review` (chờ duyệt)** | Version đã gửi đi duyệt; chờ người duyệt (trưởng nhóm/leader/admin) phê duyệt hoặc từ chối. Người soạn không tự duyệt được (§8.3.2). |
| **`approved` (đã ban hành / hiệu lực)** | Version đã được duyệt, **bất biến**, là phiên bản hiệu lực; được dùng/tải. Khi approve → version approved cũ (nếu có) tự chuyển `obsolete`. |
| **`obsolete` (hết hiệu lực / lỗi thời)** | Version cũ không còn hiệu lực; **giữ lại** trong lịch sử (không xóa — §8.4) nhưng đánh dấu rõ "KHÔNG SỬ DỤNG" + chặn/đánh dấu khi tải (OQ#4). |
| **Người soạn (Author / Creator)** | Người tạo/sửa version (`document_versions.created_by`) — staff trong phòng (hoặc Admin/leader). |
| **Người duyệt (Approver)** | Người phê duyệt/ban hành version (`document_versions.approved_by`) — **trưởng nhóm phòng đó / Ban lãnh đạo / Admin** (quyền `document:approve`). KHÁC người soạn (BR-DOC-009). |
| **Trưởng nhóm (Department lead)** | Người cố định theo từng phòng ban (M7: `departments.lead_user_id`). Mặc định có quyền `document:approve` **trong phòng ban mình** (tái dùng cơ chế OQ#11 của M1 — BR-DOC-010). |
| **Bất biến (Immutable)** | Version đã `approved` không được sửa file/nội dung/change_note; sửa = tạo version mới (draft) + đi lại quy trình duyệt + giữ bản cũ (17025 §8.3.2 d, §8.4). |
| **Phân loại tài liệu** | Bộ thuộc tính dùng để xếp loại + lọc: `type` (loại tài liệu — OQ#2), `department_id` (phòng ban sở hữu), `confidentiality_level` (mức bảo mật — OQ#3). |
| **Mức bảo mật (Confidentiality level)** | Cấp độ hạn chế xem tài liệu (vd `public_internal` / `restricted` / `confidential` — danh mục, OQ#3). Ảnh hưởng ai được xem/tải (BR-DOC-006). |
| **`document_access_log`** | Bảng riêng của M3 ghi mỗi **lượt xem / tải / chỉnh sửa** một tài liệu (R15): `document_id`, `user_id`, `action ∈ {view, download, edit}`, `at`. Phục vụ thống kê M3.3 + M6.3. KHÁC `access_stats` (M7 — lượt truy cập toàn hệ thống cấp đường dẫn) và KHÁC `audit_logs` (pháp lý §8.4). |
| **VILAS** | Hệ thống công nhận phòng thí nghiệm Việt Nam (theo ISO/IEC 17025). |
| **Audit log** | Bản ghi bất biến trong `audit_logs` (M7): ai, khi nào, làm gì, trên tài nguyên nào, với `correlation_id` (17025 §8.4). |
| **RBAC** | Role-Based Access Control + phạm vi theo phòng ban. |
| **MinIO** | Object storage self-host (C01) lưu file đính kèm; M3 lưu `file_key`, không lưu binary trong DB. |

### 1.4 Tài liệu tham chiếu

| Tài liệu | Vai trò |
|----------|---------|
| `lims/docs/00-meeting-note-analysis.md` | Yêu cầu gốc R2 (kèm file), R3 (tài liệu — lịch sử/version + approval workflow), R11 (lưu trữ tối ưu → object storage), R15 (thống kê lượt truy cập/tải/chỉnh sửa) + quyết định chốt với KH (C01/C02/C03, B03) |
| `lims/docs/01-demo-scope.md` | Cây module M3.1–M3.3, RBAC matrix mục B, ERD core M3 mục C (`documents`/`document_versions`/`document_access_log`), mapping 17025 §8.3/§8.4 mục E |
| `lims/docs/05-srs-m1-sample.md` | Chuẩn phong cách FR/BR/UC/NFR/AC; **pattern state machine** (whitelist + hàm transition trung tâm); **tách soạn–duyệt** (`SELF_APPROVAL_FORBIDDEN`); **immutable** bản đã approved; "trưởng nhóm cố định theo phòng ban" (`departments.lead_user_id`) |
| `lims/docs/10-srs-m4-hr.md` | Chuẩn phong cách; pattern audit/đính kèm `attachments` polymorphic; field-level/scope RBAC |
| `lims/docs/08-contract-m7-schema.md` | `users`/`departments`/`attachments`/`audit_logs`/`notifications` dùng chung; quyền `document:create`/`document:read`/`document:approve` đã seed (roles_permissions); M3 tự tạo `document_access_log` trong migration M3; MinIO lưu file qua `attachments.file_key` |
| `~/.claude/rules/nfr.md` | Template NFR chuẩn IEEE 830 |
| `~/.claude/rules/api.md` | Quy ước REST, response format, status code, không lộ ID tuần tự |
| `~/.claude/rules/logging.md` | Structured logging, correlationId, error handling |
| **ISO/IEC 17025:2017** §8.3 | **Kiểm soát tài liệu (hệ thống quản lý)** — phê duyệt trước ban hành, soát xét/cập nhật & phê duyệt lại, nhận biết thay đổi & tình trạng phiên bản hiện hành, bản hiện hành sẵn có tại nơi sử dụng, ngăn sử dụng tài liệu lỗi thời |
| **ISO/IEC 17025:2017** §8.4 | **Kiểm soát hồ sơ** — lập, lưu trữ, bảo vệ, sao lưu, truy xuất, lưu giữ; ngăn thay đổi/mất mát trái phép (bất biến, audit, versioning) |

---

## 2. Mô tả tổng quan

### 2.1 Bối cảnh sản phẩm

M3 là một trong 7 module của LIMS monolith (FastAPI + Next.js + PostgreSQL + Redis + MinIO + APScheduler, Docker Compose). M3 **phụ thuộc** vào M7:

- **M7 (Auth + RBAC + phòng ban + audit log):** mọi API M3 yêu cầu xác thực JWT và kiểm tra quyền theo vai trò + phạm vi phòng ban. **M7 cung cấp `trưởng nhóm cố định theo phòng ban`** (`departments.lead_user_id`) — nguồn cấp quyền `document:approve` (tái dùng cơ chế OQ#11 của M1). Audit ghi vào `audit_logs`. Quyền `document:create`/`document:read`/`document:approve` đã seed trong `roles_permissions` (08-contract-m7-schema §5.1/§5.2).
- **`departments` (M7):** mỗi tài liệu thuộc 1 phòng ban (`documents.department_id`); phạm vi soạn/sửa giới hạn theo phòng (staff phòng nào soạn tài liệu phòng đó); phạm vi đọc theo mức bảo mật (BR-DOC-006).
- **Bảng `attachments` polymorphic dùng chung (M7, D9):** lưu **file của từng version** (`owner_type='document_version'`, `owner_id`=document_versions.id). `attachments.owner_type` whitelist đã có `'document'` và `'document_version'` (08-contract-m7-schema dòng 293).
- **MinIO (C01):** lưu file; M3 lưu `file_key` không lưu binary trong DB.
- **M7.5 (Notifications):** gửi thông báo in-app cho người duyệt khi có version `review` chờ duyệt; cho người soạn khi version được approve/reject (in-app, C02).

M3 **được tham chiếu / cung cấp cho**:
- **M6 (Báo cáo & Thống kê):** M6.3 (thống kê truy cập hệ thống) tổng hợp số liệu từ `document_access_log` (R15) cùng `access_stats` của M7.
- **M1 (Mẫu):** tham chiếu SOP/phương pháp/tài liệu của M3 ở mức đọc (§7.2 — phương pháp gắn tài liệu). Ràng buộc cứng "mẫu dùng SOP version nào" ngoài scope M3 bản đầu (xem §1.2 OUT-OF-SCOPE).

### 2.2 Chức năng chính

1. Quản lý kho tài liệu: tạo/sửa/tìm/lọc tài liệu với phân loại (loại, phòng ban, mức bảo mật); sinh mã tài liệu duy nhất không lộ ID tuần tự.
2. Quản lý phiên bản: mỗi tài liệu có 1..n version, mỗi version có file riêng + change_note + lịch sử ai tạo/khi nào (R3).
3. Quy trình duyệt/ban hành (state machine `draft→review→approved→obsolete`); người soạn ≠ người duyệt (§8.3.2); reject ở review → draft.
4. Đảm bảo "chỉ bản approved được dùng": tải chỉ cho version approved (trừ người soạn/duyệt xem draft/review); approve version mới → version approved cũ tự obsolete; tối đa 1 version current/tài liệu.
5. Bất biến version đã approved: sửa = tạo version mới + đi lại quy trình; giữ toàn bộ lịch sử (§8.3.2 d, §8.4).
6. Đính kèm file lên MinIO qua `attachments`; tải file với kiểm soát quyền + ghi `document_access_log`.
7. Thống kê truy cập (R15): đếm lượt view / download / edit mỗi tài liệu; báo cáo tổng hợp.
8. Audit toàn bộ thao tác phục vụ duy trì công nhận VILAS (§8.3/§8.4).

### 2.3 Đối tượng người dùng & quyền (RBAC + phạm vi phòng ban)

Trích từ RBAC matrix `01-demo-scope.md` (4 vai trò; các dòng "Tài liệu — tạo/sửa", "Tài liệu — duyệt/ban hành", "Tài liệu — xem"). Phạm vi dữ liệu: theo phòng ban cho thao tác ghi của staff; Admin & Ban lãnh đạo toàn hệ thống. **Kế toán CHỈ XEM (👁)** tài liệu, KHÔNG tạo/sửa/duyệt.

**Khái niệm "trưởng nhóm" (tái dùng OQ#11 của M1):** "Trưởng nhóm" KHÔNG phải vai trò RBAC thứ 5 mà là **thuộc tính cố định gắn cho đúng 1 user mỗi phòng ban** trong M7 (`departments.lead_user_id`). Người này thuộc vai trò "Nhân sự/KTV (staff)" nhưng được cấp thêm quyền `document:approve` **giới hạn trong phòng ban mình**. Staff thường KHÔNG có quyền duyệt.

| Actor | Mô tả | Quyền trong M3 |
|-------|-------|----------------|
| **Admin** | Quản trị hệ thống | Toàn quyền mọi thao tác tài liệu (mọi phòng ban): tạo/sửa tài liệu & version, gửi duyệt, **duyệt/ban hành**, obsolete, xem/tải mọi version (kể cả draft/obsolete), xem thống kê. |
| **Ban lãnh đạo (leader)** | Lãnh đạo lab | Tạo/sửa tài liệu (✅, mọi phòng), **duyệt/ban hành** (✅ `document:approve` mọi phòng), xem/tải mọi version, xem thống kê truy cập. |
| **Kế toán (accountant)** | Tài chính | **CHỈ XEM** (👁) tài liệu — chỉ **version approved/current** mà mức bảo mật cho phép. KHÔNG tạo/sửa/duyệt/obsolete; KHÔNG xem draft/review. Mọi API ghi của M3 trả 403 cho Kế toán. |
| **Nhân sự/KTV (staff)** | Kỹ thuật viên | **Tạo/sửa tài liệu & version (✅ trong phòng mình)**; **xem/tải version approved** (✅ mọi phòng, theo mức bảo mật — `document:read` scope `all`); gửi duyệt version mình soạn. **Nếu là trưởng nhóm phòng mình (`departments.lead_user_id`):** thêm **duyệt/ban hành** (`document:approve`) **trong phòng mình**. Staff thường: KHÔNG duyệt; KHÔNG sửa tài liệu phòng khác. |

Quy ước: ✅ = toàn quyền trong phạm vi · 👁 = chỉ xem · — = không truy cập · (phòng) = giới hạn phòng ban của user.

> **Kế toán chỉ xem (matrix demo-scope mục B):** dòng "Tài liệu — xem" của Kế toán = 👁; dòng "tạo/sửa" và "duyệt/ban hành" = — (trống). Kế toán chỉ thấy **version approved** (không thấy bản nháp/chờ duyệt) và bị chặn mọi endpoint ghi ở **tầng API** (BR-DOC-005).
> **Trưởng nhóm là THUỘC TÍNH cố định theo phòng ban**, không phải vai trò riêng (tái dùng OQ#11 M1). Quyền `document:approve` chỉ cấp cho trưởng nhóm phòng đó / Ban lãnh đạo / Admin — xem BR-DOC-010. Dòng seed `('staff','document','create','department')` + `('staff','document','read','all')` (08-contract-m7-schema §5.2) là điều kiện cần; quyền duyệt cho staff = chỉ khi là trưởng nhóm (app check).
> **Tách soạn–duyệt (§8.3.2):** người **soạn/sửa** version (`created_by`) KHÔNG được **tự duyệt** version đó (BR-DOC-009) — kể cả khi người đó là trưởng nhóm (phải có người duyệt khác — xem OQ#6).

### 2.4 Ràng buộc (Constraints)

- **CONSTRAINT-1 (State machine version):** trạng thái version chỉ chuyển theo các phép hợp lệ định nghĩa ở §3 FR-DOC-013 / §4 BR-DOC-007. Mọi chuyển trạng thái không hợp lệ bị chặn (422 `INVALID_STATE_TRANSITION`).
- **CONSTRAINT-2 (Chỉ 1 current/tài liệu — §8.3):** tại 1 thời điểm mỗi tài liệu có TỐI ĐA 1 version `approved` (current). Khi approve version mới, version approved cũ TỰ ĐỘNG chuyển `obsolete` trong cùng transaction (BR-DOC-008).
- **CONSTRAINT-3 (Version approved bất biến — §8.3.2 d/§8.4):** không sửa file/nội dung/change_note của version đã `approved` hoặc `obsolete`; sửa = tạo version mới (draft). Không có endpoint hard-delete version đã từng approved.
- **CONSTRAINT-4 (Tách soạn–duyệt — §8.3.2):** người duyệt (`approved_by`) ≠ người soạn (`created_by`) của cùng version. Enforce app-layer (`SELF_APPROVAL_FORBIDDEN`).
- **CONSTRAINT-5 (Mã không lộ tuần tự):** `id` nội bộ là UUID; `documents.code` hiển thị duy nhất, không đoán được tuần tự (rule api.md).
- **CONSTRAINT-6 (Audit VILAS §8.3/§8.4):** mọi thao tác tạo/sửa/gửi duyệt/duyệt/reject/ban hành/obsolete/tải tài liệu ghi `audit_logs` (user, action, resource, resource_id, correlation_id, ip, at, detail).
- **CONSTRAINT-7 (Thống kê truy cập R15):** mỗi lượt view/download/edit ghi `document_access_log` — bảng riêng của M3 (KHÔNG dùng `audit_logs` để đếm; tách high-volume khỏi pháp lý §8.4, đồng bộ tinh thần `access_stats` M7 D11).
- **CONSTRAINT-8 (Lưu file):** file lưu MinIO (C01) qua `attachments` polymorphic (`owner_type='document_version'`); M3 lưu `file_key`, không lưu binary trong DB.
- **CONSTRAINT-9 (Thông báo):** chỉ in-app (bảng `notifications`); không email/Zalo (C02).
- **CONSTRAINT-10 (Stack & quy mô):** FastAPI, PostgreSQL, Redis, MinIO; quy mô ~40 user (C03) — monolith, không scale ngang.
- **CONSTRAINT-11 (Phụ thuộc M7 — trưởng nhóm):** RBAC duyệt tài liệu phụ thuộc M7 cung cấp trưởng nhóm cố định theo phòng ban (`departments.lead_user_id`). **M7 phải sẵn sàng trước khi `/contract` M3 implement RBAC duyệt.**

### 2.5 Giả định (Assumptions) — xem chi tiết §7

- ASSUMPTION-1: 1 tài liệu (`documents`) có 1..n phiên bản (`document_versions`) — quan hệ 1-n; mỗi version có file/change_note/trạng thái/người duyệt riêng.
- ASSUMPTION-2: Tách soạn–duyệt theo §8.3.2 — người soạn version KHÔNG tự duyệt; người duyệt = trưởng nhóm phòng đó / leader / admin (tái dùng cơ chế trưởng nhóm OQ#11 M1).
- ASSUMPTION-3: Bản đầu là **1 bước duyệt** (review → approved bởi 1 người duyệt). Duyệt đa cấp/nhiều người → OQ#5 (default 1 bước, không chặn contract).
- ASSUMPTION-4: Khi approve version mới → version approved cũ tự obsolete; tối đa 1 current/tài liệu (§8.3).
- ASSUMPTION-5: Version `obsolete` GIỮ LẠI (không xóa — §8.4) nhưng đánh dấu "KHÔNG SỬ DỤNG". Có cho tải lại bản obsolete (có cảnh báo) hay chặn hoàn toàn → OQ#4 (default: cho người có quyền xem lịch sử tải có cảnh báo "tài liệu lỗi thời", người thường chỉ thấy current).
- ASSUMPTION-6: Mã tài liệu default `<LOAI>-<MAPHONG>-<seq>` (vd `SOP-HOA-012`); danh mục loại tài liệu + mức bảo mật default theo §3/§8 — cấu hình được (OQ#1/#2/#3).

---

## 3. Yêu cầu chức năng chi tiết

Mỗi FR có ID dạng `FR-DOC-NNN`. Business rule dạng `BR-DOC-NNN` ở §4. Acceptance Criteria dạng Given–When–Then (cover happy path + edge + RBAC + lỗi input).

---

### FR-DOC-001: Tạo tài liệu (metadata + phân loại)

- **Mô tả:** Tạo một **tài liệu (`documents`)** với metadata: tiêu đề, loại (`type` — SOP/quy trình/biểu mẫu/hướng dẫn/tiêu chuẩn), phòng ban sở hữu (`department_id`), mức bảo mật (`confidentiality_level`). Khi lưu, hệ thống sinh `code` duy nhất (FR-DOC-003) và đặt trạng thái tài liệu = `active`. Tài liệu mới chưa có version hiệu lực cho tới khi tạo + duyệt version đầu (FR-DOC-006/011).
- **Độ ưu tiên:** P0
- **Actor:** staff (phòng mình), leader (mọi phòng), Admin (mọi phòng). Kế toán không truy cập (ghi).
- **Tiền điều kiện:** user đã đăng nhập, có quyền `document:create` trong phạm vi phòng ban.
- **Luồng chính:**
  1. User mở "Kho tài liệu" → "Tạo tài liệu".
  2. Nhập tiêu đề, chọn loại (danh mục — OQ#2), phòng ban sở hữu (mặc định = phòng của user), mức bảo mật (danh mục — OQ#3).
  3. Hệ thống validate quyền + phạm vi phòng (BR-DOC-004) → sinh `code` (FR-DOC-003) → lưu `documents` (status=`active`, `current_version_id`=NULL) → ghi `audit_logs` action=`DOCUMENT_CREATE`.
  4. Gợi ý tạo version đầu (FR-DOC-006).
- **Luồng phụ / ngoại lệ:**
  - A1: phòng ban sở hữu ≠ phòng của user (và user không phải Admin/leader) → 403 `FORBIDDEN`.
  - A2: thiếu tiêu đề / loại → 400 `VALIDATION_ERROR`.
- **Hậu điều kiện:** tài liệu tồn tại với `code` duy nhất, chưa có current version; audit ghi nhận.
- **Business Rules:** BR-DOC-001, BR-DOC-004, BR-DOC-005, BR-DOC-014.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN staff phòng "Hóa" đã đăng nhập WHEN tạo tài liệu tiêu đề "SOP đo pH", loại=SOP, phòng=Hóa, mức bảo mật=public_internal THEN trả 201, tài liệu có `code` duy nhất, `department_id`=Hóa, status=`active`, `current_version_id`=NULL, audit `DOCUMENT_CREATE`.
  - AC2 (RBAC scope): GIVEN staff phòng "Hóa" WHEN tạo tài liệu cho phòng "Sinh" THEN trả 403 `FORBIDDEN`, không tạo.
  - AC3 (RBAC — Kế toán chặn ghi): GIVEN Kế toán WHEN gọi API tạo tài liệu THEN trả 403 `FORBIDDEN` (matrix: Kế toán chỉ 👁).
  - AC4 (lỗi input): GIVEN form tạo tài liệu WHEN không nhập tiêu đề THEN trả 400 `VALIDATION_ERROR`, không tạo.
- **Data cần thiết (mức logic):** Document { id(UUID), code(UNIQUE), title, type, department_id(FK NOT NULL), confidentiality_level, status(active), current_version_id(FK→document_versions NULL), created_by(FK→users), created_at }.
- **API cần (ý định):** "tạo tài liệu", "lấy danh mục loại tài liệu / mức bảo mật".

---

### FR-DOC-002: Sửa metadata tài liệu

- **Mô tả:** Sửa metadata cấp tài liệu (tiêu đề, loại, mức bảo mật). **KHÔNG đổi `code`** (mã cố định sau khi tạo — BR-DOC-014) và **KHÔNG đổi `department_id`** trừ Admin (chuyển sở hữu phòng — OQ ngoài bản đầu). Sửa metadata KHÔNG ảnh hưởng nội dung version (file/nội dung tài liệu sửa qua version mới — FR-DOC-006).
- **Độ ưu tiên:** P1
- **Actor:** staff (tài liệu phòng mình), leader, Admin. Kế toán không truy cập (ghi).
- **Tiền điều kiện:** tài liệu tồn tại; user có quyền `document:create`/`update` trong phạm vi phòng.
- **Luồng chính:**
  1. User mở chi tiết tài liệu → "Sửa thông tin".
  2. Sửa tiêu đề/loại/mức bảo mật → lưu → ghi `audit_logs` action=`DOCUMENT_UPDATE` (detail: trường thay đổi before/after).
- **Luồng phụ / ngoại lệ:**
  - A1: cố đổi `code` → 422 `CODE_IMMUTABLE` (BR-DOC-014).
  - A2: sửa tài liệu phòng khác (không Admin/leader) → 403 `FORBIDDEN`.
- **Hậu điều kiện:** metadata cập nhật; audit ghi before/after.
- **Business Rules:** BR-DOC-004, BR-DOC-005, BR-DOC-014.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN tài liệu `SOP-HOA-012` WHEN staff phòng Hóa đổi mức bảo mật `public_internal`→`restricted` THEN lưu, audit `DOCUMENT_UPDATE` ghi before/after mức bảo mật.
  - AC2 (edge — code bất biến): GIVEN tài liệu đã có `code` WHEN gửi request đổi `code` THEN trả 422 `CODE_IMMUTABLE`, code không đổi.
  - AC3 (RBAC scope): GIVEN staff phòng Hóa WHEN sửa tài liệu phòng Sinh THEN trả 403 `FORBIDDEN`.
- **Data cần thiết:** Document.title, type, confidentiality_level (mutable); code, id (immutable).
- **API cần:** "sửa metadata tài liệu".

---

### FR-DOC-003: Sinh mã tài liệu duy nhất (không lộ ID tuần tự)

- **Mô tả:** Khi tạo tài liệu, hệ thống sinh `code` duy nhất, human-readable, không lộ ID tuần tự nội bộ (default `<LOAI>-<MAPHONG>-<seq>` vd `SOP-HOA-012`; định dạng cấu hình — OQ#1). ID thật là UUID; không expose serial id liên tiếp.
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (trong giao dịch tạo tài liệu FR-DOC-001).
- **Tiền điều kiện:** đang tạo tài liệu.
- **Luồng chính:**
  1. Hệ thống sinh `code` theo định dạng cấu hình, đảm bảo duy nhất (unique constraint + retry nếu trùng).
  2. Lưu `code` cùng tài liệu.
- **Luồng phụ / ngoại lệ:**
  - A1: trùng `code` (race) → retry trong cùng transaction; fail sau N lần → 500 + log ERROR.
- **Hậu điều kiện:** tài liệu có `code` duy nhất.
- **Business Rules:** BR-DOC-014 (mã duy nhất, bất biến, không lộ tuần tự).
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN tạo tài liệu loại SOP phòng Hóa WHEN lưu THEN `code` khớp định dạng cấu hình + duy nhất toàn hệ thống; API trả `code` nhưng KHÔNG trả id UUID dạng số tuần tự.
  - AC2 (duy nhất): GIVEN 2 tài liệu tạo gần đồng thời WHEN cả hai sinh mã THEN 2 `code` khác nhau (unique constraint đảm bảo).
  - AC3 (không lộ tuần tự): GIVEN 2 tài liệu tạo liên tiếp WHEN so sánh định danh dùng ngoài THEN không suy ra được số thứ tự nội bộ liên tiếp (CONSTRAINT-5).
- **Data cần thiết:** Document.code (UNIQUE); cấu hình định dạng mã (OQ#1).
- **API cần:** nội bộ (trong tạo tài liệu).

---

### FR-DOC-004: Tìm kiếm / lọc / liệt kê tài liệu (theo phân loại)

- **Mô tả:** Liệt kê tài liệu có phân trang, lọc theo loại + phòng ban + mức bảo mật + từ khóa (tiêu đề/code) + trạng thái (có current version hay chưa). Kết quả mặc định hiển thị **phiên bản hiệu lực (current)** của mỗi tài liệu; người không có quyền xem draft chỉ thấy tài liệu đã có version approved (OQ#4 chi phối hiển thị tài liệu chưa có current).
- **Độ ưu tiên:** P0
- **Actor:** mọi vai trò có quyền `document:read` (Admin, leader, staff) + Kế toán (👁, chỉ tài liệu có current). Phạm vi đọc theo mức bảo mật (BR-DOC-006).
- **Tiền điều kiện:** đã đăng nhập.
- **Luồng chính:**
  1. User mở "Kho tài liệu" → nhập bộ lọc (loại/phòng/mức bảo mật/từ khóa) + phân trang.
  2. Hệ thống áp RBAC + mức bảo mật (BR-DOC-006) → trả danh sách tài liệu kèm `code`, tiêu đề, loại, phòng, mức bảo mật, version current (số + ngày ban hành) nếu có.
  3. Ghi `document_access_log` action=`view` cho từng tài liệu mở chi tiết (FR-DOC-014).
- **Luồng phụ / ngoại lệ:**
  - A1: tài liệu mức bảo mật cao hơn quyền user → không xuất hiện trong danh sách (BR-DOC-006).
  - A2: tài liệu chưa có version approved → Kế toán/staff phòng khác không thấy (chỉ người soạn/duyệt phòng đó + Admin/leader thấy — OQ#4).
- **Hậu điều kiện:** chỉ đọc; lượt view được ghi nhận khi mở chi tiết.
- **Business Rules:** BR-DOC-006, BR-DOC-015 (R15 ghi view).
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN có 50 tài liệu WHEN lọc loại=SOP, phòng=Hóa, phân trang 20/trang THEN trả đúng các SOP phòng Hóa user được phép xem, có version current (số + ngày ban hành).
  - AC2 (RBAC mức bảo mật): GIVEN tài liệu mức `confidential` mà staff thường không có quyền WHEN staff liệt kê THEN tài liệu đó KHÔNG xuất hiện (BR-DOC-006).
  - AC3 (RBAC — Kế toán chỉ thấy current): GIVEN tài liệu chỉ có version `draft` (chưa approved) WHEN Kế toán liệt kê THEN tài liệu đó KHÔNG xuất hiện.
  - AC4 (performance): GIVEN 5,000 tài liệu / 20,000 version WHEN lọc + phân trang THEN P95 < 500ms, query dùng index (NFR-PERF-DOC-002).
- **Data cần thiết:** Document(list) + current version summary; bộ lọc type/department_id/confidentiality_level/keyword/status.
- **API cần:** "liệt kê/tìm tài liệu (lọc + phân trang)".

---

### FR-DOC-005: Xem chi tiết tài liệu + danh sách phiên bản

- **Mô tả:** Hiển thị chi tiết một tài liệu: metadata + **version hiệu lực (current)** nổi bật + danh sách toàn bộ version (số, trạng thái, người tạo, ngày tạo, change_note, người duyệt, ngày duyệt). Người không có quyền xem draft/review chỉ thấy version approved/obsolete (theo OQ#4); người soạn/duyệt phòng đó + Admin/leader thấy mọi version.
- **Độ ưu tiên:** P0
- **Actor:** Admin, leader, staff (theo mức bảo mật + scope hiển thị version). Kế toán (👁) chỉ thấy version approved/current.
- **Tiền điều kiện:** tài liệu tồn tại; user có quyền xem theo mức bảo mật (BR-DOC-006).
- **Luồng chính:**
  1. User mở chi tiết tài liệu.
  2. Hệ thống áp RBAC + phạm vi hiển thị version (BR-DOC-011) → trả metadata + current version + danh sách version (đã lọc theo quyền).
  3. Ghi `document_access_log` action=`view`.
- **Luồng phụ / ngoại lệ:**
  - A1: user không đủ quyền mức bảo mật → 403 `FORBIDDEN` (BR-DOC-006).
  - A2: tài liệu chưa có current version + user không phải người soạn/duyệt phòng đó/Admin/leader → 404 (ẩn sự tồn tại) hoặc 403 (OQ#4 chốt cách hiển thị).
- **Hậu điều kiện:** chỉ đọc; lượt view ghi nhận.
- **Business Rules:** BR-DOC-006, BR-DOC-011, BR-DOC-015.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN tài liệu `SOP-HOA-012` có v1 obsolete + v2 approved + v3 draft WHEN trưởng nhóm phòng Hóa mở chi tiết THEN thấy v2 nổi bật (current) + danh sách [v1 obsolete, v2 approved, v3 draft], audit/access_log `view` ghi.
  - AC2 (RBAC hiển thị version): GIVEN cùng tài liệu trên WHEN staff phòng Sinh (không soạn/duyệt) mở chi tiết THEN chỉ thấy v2 (approved) + v1 (obsolete, đánh dấu lỗi thời); KHÔNG thấy v3 draft (BR-DOC-011).
  - AC3 (RBAC — Kế toán): GIVEN cùng tài liệu WHEN Kế toán mở chi tiết THEN chỉ thấy v2 approved (current); KHÔNG thấy v3 draft.
- **Data cần thiết:** Document + danh sách DocumentVersion (lọc theo quyền).
- **API cần:** "lấy chi tiết tài liệu + danh sách phiên bản".

---

### FR-DOC-006: Tạo phiên bản mới (version) + đính kèm file + change_note

- **Mô tả:** Tạo một version mới cho tài liệu ở trạng thái `draft`: số version = (max version hiện có) + 1; đính kèm **1 file chính** lưu MinIO (R2, R11) + `change_note` (mô tả thay đổi so với version trước — bắt buộc từ version thứ 2). Version đầu (v1) tạo cùng/sau khi tạo tài liệu. Tạo version mới KHÔNG làm thay đổi version approved hiện hành (chỉ thay khi version mới được approve — FR-DOC-011).
- **Độ ưu tiên:** P0
- **Actor:** staff (tài liệu phòng mình), leader, Admin. Kế toán không truy cập (ghi).
- **Tiền điều kiện:** tài liệu tồn tại; user có quyền `document:create` trong phạm vi phòng; **KHÔNG đang tồn tại version `draft`/`review` chưa kết thúc của tài liệu này** (OQ#6 — default: cho phép tối đa 1 version đang soạn/chờ duyệt/tài liệu để tránh nhiều bản nháp song song).
- **Luồng chính:**
  1. User mở tài liệu → "Tạo phiên bản mới".
  2. Upload file chính (validate loại + dung lượng — BR-DOC-013), nhập `change_note` (bắt buộc từ v2 — BR-DOC-016).
  3. Hệ thống tính `version` = max+1 → lưu `document_versions` (status=`draft`, created_by=user, created_at) → lưu file MinIO + `attachments` (owner_type=`document_version`) → ghi `audit_logs` action=`DOCUMENT_VERSION_CREATE` + `document_access_log` action=`edit` (R15).
- **Luồng phụ / ngoại lệ:**
  - A1: thiếu `change_note` ở v≥2 → 400 `CHANGE_NOTE_REQUIRED` (BR-DOC-016).
  - A2: file sai loại / quá lớn → 422 `INVALID_FILE_TYPE` / `FILE_TOO_LARGE` (BR-DOC-013).
  - A3: đã tồn tại version `draft`/`review` chưa kết thúc → 409 `DRAFT_ALREADY_EXISTS` (OQ#6 default).
  - A4: tạo version cho tài liệu phòng khác (không Admin/leader) → 403 `FORBIDDEN`.
- **Hậu điều kiện:** version mới ở `draft` với file + change_note; lượt edit ghi nhận; version approved hiện hành KHÔNG đổi.
- **Business Rules:** BR-DOC-001, BR-DOC-004, BR-DOC-012, BR-DOC-013, BR-DOC-016, BR-DOC-021.
- **Acceptance Criteria:**
  - AC1 (happy v1): GIVEN tài liệu `SOP-HOA-012` chưa có version WHEN staff upload file "sop-do-ph-v1.pdf" THEN tạo version số=1 status=`draft`, file lấy lại được, audit `DOCUMENT_VERSION_CREATE` + access_log `edit`.
  - AC2 (happy v2 + change_note): GIVEN tài liệu đã có v1 approved WHEN staff tạo v2 với change_note "Cập nhật ngưỡng hiệu chuẩn máy" THEN version số=2 status=`draft`, change_note lưu; v1 vẫn approved/current (chưa đổi).
  - AC3 (lỗi input — thiếu change_note v2): GIVEN tạo version thứ 2 WHEN không nhập change_note THEN trả 400 `CHANGE_NOTE_REQUIRED`, không tạo.
  - AC4 (edge — đã có draft): GIVEN tài liệu đang có v3 `draft` WHEN tạo thêm version mới THEN trả 409 `DRAFT_ALREADY_EXISTS` (OQ#6 default).
  - AC5 (RBAC scope): GIVEN staff phòng Hóa WHEN tạo version cho tài liệu phòng Sinh THEN trả 403 `FORBIDDEN`.
  - AC6 (lỗi file): GIVEN upload "macro.docm" không thuộc whitelist WHEN tạo version THEN trả 422 `INVALID_FILE_TYPE`.
- **Data cần thiết (mức logic):** DocumentVersion { id(UUID), document_id(FK), version(INT), file_key(qua attachments), change_note, status(draft), created_by(FK→users), created_at, approved_by(FK NULL), approved_at(NULL) }. UNIQUE(document_id, version).
- **API cần:** "tạo phiên bản mới (upload file + change_note)", "sửa version draft (file/change_note)".

---

### FR-DOC-007: Sửa phiên bản đang ở trạng thái draft

- **Mô tả:** Trong khi version còn ở `draft`, người soạn (hoặc Admin/leader) được sửa file đính kèm và `change_note`. **Chỉ sửa được version `draft`** — version `review`/`approved`/`obsolete` bất biến với thao tác sửa (BR-DOC-012).
- **Độ ưu tiên:** P1
- **Actor:** người soạn version (`created_by`) trong phòng mình, leader, Admin.
- **Tiền điều kiện:** version ở `draft`; user là người soạn hoặc Admin/leader.
- **Luồng chính:**
  1. User mở version `draft` → "Sửa" → thay file mới / sửa change_note.
  2. Hệ thống validate version đang `draft` (BR-DOC-012) → cập nhật file/change_note → ghi `audit_logs` action=`DOCUMENT_VERSION_UPDATE` + `document_access_log` action=`edit`.
- **Luồng phụ / ngoại lệ:**
  - A1: version không ở `draft` → 422 `VERSION_LOCKED` (BR-DOC-012).
  - A2: user không phải người soạn và không Admin/leader → 403 `FORBIDDEN`.
- **Hậu điều kiện:** version draft cập nhật; lượt edit ghi nhận.
- **Business Rules:** BR-DOC-012, BR-DOC-013, BR-DOC-016.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN version v3 `draft` do staff A soạn WHEN A thay file mới + sửa change_note THEN cập nhật, audit `DOCUMENT_VERSION_UPDATE` + access_log `edit`.
  - AC2 (edge — sửa version approved): GIVEN version v2 `approved` WHEN cố sửa file THEN trả 422 `VERSION_LOCKED` (CONSTRAINT-3).
  - AC3 (RBAC): GIVEN version v3 draft do A soạn WHEN staff B (không soạn, không trưởng nhóm) cố sửa THEN trả 403 `FORBIDDEN`.
- **Data cần thiết:** DocumentVersion (status=draft) — file_key, change_note (mutable khi draft).
- **API cần:** "sửa version draft".

---

### FR-DOC-008: Gửi phiên bản đi duyệt (draft → review)

- **Mô tả:** Người soạn gửi version `draft` đi duyệt → chuyển trạng thái `draft → review`. Khi vào `review`, hệ thống tạo `notifications` in-app cho (các) người duyệt đủ quyền (trưởng nhóm phòng đó / leader / admin). Version `review` KHÓA sửa (chỉ reject về draft mới sửa lại được).
- **Độ ưu tiên:** P0
- **Actor:** người soạn version (`created_by`), Admin/leader (thay mặt).
- **Tiền điều kiện:** version ở `draft`; có file đính kèm; user là người soạn hoặc Admin/leader.
- **Luồng chính:**
  1. User mở version `draft` → "Gửi duyệt".
  2. Hệ thống validate (from=`draft`, to=`review`) ∈ whitelist (BR-DOC-007) + version có file (BR-DOC-017) → chuyển `review` → tạo notification cho người duyệt → ghi `audit_logs` action=`DOCUMENT_VERSION_SUBMIT`.
- **Luồng phụ / ngoại lệ:**
  - A1: version không ở `draft` → 422 `INVALID_STATE_TRANSITION`.
  - A2: version chưa có file đính kèm → 422 `VERSION_FILE_REQUIRED` (BR-DOC-017).
- **Hậu điều kiện:** version ở `review`, khóa sửa; người duyệt nhận thông báo.
- **Business Rules:** BR-DOC-007, BR-DOC-012, BR-DOC-017, BR-DOC-018 (notify chống trùng).
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN version v3 `draft` có file WHEN người soạn gửi duyệt THEN chuyển `review`, trưởng nhóm phòng nhận notification, audit `DOCUMENT_VERSION_SUBMIT`.
  - AC2 (edge — không có file): GIVEN version draft chưa upload file WHEN gửi duyệt THEN trả 422 `VERSION_FILE_REQUIRED`.
  - AC3 (state — gửi lại khi đã review): GIVEN version đang `review` WHEN gửi duyệt lần nữa THEN trả 422 `INVALID_STATE_TRANSITION`.
- **Data cần thiết:** DocumentVersion.status (draft→review); notifications cho người duyệt.
- **API cần:** "gửi version đi duyệt".

---

### FR-DOC-009: Duyệt phiên bản (review → approved) — người soạn ≠ người duyệt (§8.3.2)

- **Mô tả:** Người duyệt (trưởng nhóm phòng đó / leader / admin) phê duyệt version `review` → chuyển `review → approved`, set `approved_by` + `approved_at`. **Người duyệt PHẢI KHÁC người soạn** version đó (tách trách nhiệm §8.3.2 — BR-DOC-009). Khi approve thành công → **version approved cũ của tài liệu (nếu có) TỰ ĐỘNG chuyển `obsolete`** + cập nhật `documents.current_version_id` = version vừa approve (FR-DOC-011 / BR-DOC-008).
- **Độ ưu tiên:** P0
- **Actor:** **trưởng nhóm phòng đó** (`document:approve` — BR-DOC-010), leader, Admin. Staff thường / người soạn KHÔNG duyệt được.
- **Tiền điều kiện:** version ở `review`; user có quyền `document:approve` trong phạm vi phòng (trưởng nhóm phòng đó / leader / Admin); user ≠ người soạn version.
- **Luồng chính:**
  1. Người duyệt mở version `review` → xem file + change_note → "Duyệt/Ban hành".
  2. Hệ thống validate quyền duyệt (BR-DOC-010) + người duyệt ≠ người soạn (BR-DOC-009) + (from=`review`, to=`approved`) ∈ whitelist (BR-DOC-007).
  3. **Trong 1 transaction có row-lock trên tài liệu:** chuyển version → `approved` (set approved_by/approved_at); nếu tài liệu đang có version `approved` khác → chuyển nó `obsolete`; set `documents.current_version_id` = version mới.
  4. Tạo notification cho người soạn ("đã được ban hành"); ghi `audit_logs` action=`DOCUMENT_VERSION_APPROVE` (+ action=`DOCUMENT_VERSION_OBSOLETE` cho bản cũ).
- **Luồng phụ / ngoại lệ:**
  - A1: người duyệt = người soạn → 403 `SELF_APPROVAL_FORBIDDEN` (BR-DOC-009).
  - A2: user không có quyền duyệt (staff thường) → 403 `FORBIDDEN` (BR-DOC-010).
  - A3: version không ở `review` → 422 `INVALID_STATE_TRANSITION`.
  - A4: 2 yêu cầu approve đồng thời 2 version khác nhau của cùng tài liệu → chỉ 1 thành công làm current; bản kia bị từ chối/giữ trạng thái nhất quán (NFR-CONCUR-DOC-001).
- **Hậu điều kiện:** version `approved` (current, bất biến); version approved cũ `obsolete`; `documents.current_version_id` cập nhật; người soạn nhận thông báo; audit ghi nhận.
- **Business Rules:** BR-DOC-007, BR-DOC-008, BR-DOC-009, BR-DOC-010, BR-DOC-012, BR-DOC-019.
- **Acceptance Criteria:**
  - AC1 (happy + obsolete cũ): GIVEN tài liệu có v1 `approved` (current) + v2 `review` (do staff A soạn) WHEN trưởng nhóm T (≠ A) duyệt v2 THEN v2→`approved` + current_version_id=v2; v1→`obsolete` tự động; A nhận notification; audit `DOCUMENT_VERSION_APPROVE` + `DOCUMENT_VERSION_OBSOLETE`(v1).
  - AC2 (tách soạn–duyệt §8.3.2): GIVEN version v2 `review` do A soạn WHEN A tự duyệt v2 THEN trả 403 `SELF_APPROVAL_FORBIDDEN`, v2 vẫn `review`.
  - AC3 (RBAC — staff thường không duyệt): GIVEN staff thường B (không phải trưởng nhóm) phòng Hóa WHEN duyệt v2 THEN trả 403 `FORBIDDEN`; GIVEN trưởng nhóm phòng Hóa THEN thành công.
  - AC4 (chỉ 1 current): GIVEN sau khi v2 approved WHEN truy vấn version approved của tài liệu THEN đúng 1 version `approved` (v2), v1 đã `obsolete` (BR-DOC-008).
  - AC5 (state): GIVEN version `draft` WHEN cố duyệt trực tiếp THEN trả 422 `INVALID_STATE_TRANSITION` (phải qua review).
- **Data cần thiết:** DocumentVersion (review→approved, approved_by/approved_at); Document.current_version_id; version cũ → obsolete.
- **API cần:** "duyệt/ban hành version", "lấy danh sách version chờ duyệt của tôi".

---

### FR-DOC-010: Từ chối phiên bản (review → draft) kèm lý do

- **Mô tả:** Người duyệt từ chối version `review` → chuyển `review → draft` kèm `reject_reason` (bắt buộc). Người soạn được sửa lại (FR-DOC-007) rồi gửi duyệt lại (FR-DOC-008). Không có trạng thái "rejected" riêng — reject = quay về `draft` (state machine gọn).
- **Độ ưu tiên:** P0
- **Actor:** trưởng nhóm phòng đó / leader / Admin (người có quyền duyệt). KHÁC người soạn (BR-DOC-009).
- **Tiền điều kiện:** version ở `review`; user có quyền `document:approve`; user ≠ người soạn.
- **Luồng chính:**
  1. Người duyệt mở version `review` → "Từ chối" → nhập `reject_reason` (bắt buộc).
  2. Hệ thống validate quyền + (from=`review`, to=`draft`) ∈ whitelist → chuyển `draft`, lưu `reject_reason` (vào lịch sử/audit detail) → tạo notification cho người soạn → ghi `audit_logs` action=`DOCUMENT_VERSION_REJECT`.
- **Luồng phụ / ngoại lệ:**
  - A1: thiếu `reject_reason` → 400 `REJECT_REASON_REQUIRED` (BR-DOC-020).
  - A2: version không ở `review` → 422 `INVALID_STATE_TRANSITION`.
  - A3: user không quyền duyệt → 403 `FORBIDDEN`.
- **Hậu điều kiện:** version về `draft`, mở lại để sửa; người soạn nhận thông báo + lý do.
- **Business Rules:** BR-DOC-007, BR-DOC-010, BR-DOC-020.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN version v2 `review` WHEN trưởng nhóm từ chối với lý do "Thiếu mục an toàn hóa chất" THEN v2→`draft`, người soạn nhận notification kèm lý do, audit `DOCUMENT_VERSION_REJECT` lưu reason.
  - AC2 (lỗi input — thiếu lý do): GIVEN từ chối version WHEN không nhập reject_reason THEN trả 400 `REJECT_REASON_REQUIRED`, trạng thái không đổi.
  - AC3 (RBAC): GIVEN staff thường WHEN từ chối version THEN trả 403 `FORBIDDEN`.
- **Data cần thiết:** DocumentVersion.status (review→draft); reject_reason (lưu audit detail / cột tùy schema-designer).
- **API cần:** "từ chối version (kèm lý do)".

---

### FR-DOC-011: Ban hành & tự động obsolete bản cũ — đảm bảo chỉ 1 version hiệu lực (§8.3)

- **Mô tả:** Quy tắc nền tảng của document control §8.3: tại 1 thời điểm mỗi tài liệu có **tối đa 1 version `approved` (current)**. Khi version mới được approve (FR-DOC-009), version approved cũ tự động `obsolete` + `documents.current_version_id` trỏ version mới. Logic này nằm **trong transaction approve** (không tách thành thao tác riêng) để đảm bảo nguyên tử + chống race. FR này đặc tả ràng buộc bất biến hệ thống (không phải endpoint riêng).
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (trong giao dịch approve FR-DOC-009).
- **Tiền điều kiện:** đang approve một version `review`.
- **Luồng chính:**
  1. Trong transaction approve (FR-DOC-009 bước 3), trước khi commit: tìm version `approved` hiện tại của tài liệu (row-lock).
  2. Nếu tồn tại → set `obsolete` + audit `DOCUMENT_VERSION_OBSOLETE`.
  3. Set `documents.current_version_id` = version vừa approve.
- **Luồng phụ / ngoại lệ:**
  - A1: tài liệu chưa có version approved nào (lần ban hành đầu) → không có bản cũ để obsolete; chỉ set current_version_id.
  - A2: race 2 approve song song → row-lock đảm bảo tuần tự; cuối cùng đúng 1 current (NFR-CONCUR-DOC-001).
- **Hậu điều kiện:** đúng 1 version `approved`/tài liệu; bản cũ `obsolete` giữ trong lịch sử (§8.4).
- **Business Rules:** BR-DOC-008, BR-DOC-019, BR-DOC-021.
- **Acceptance Criteria:**
  - AC1 (happy chuỗi): GIVEN tài liệu approve lần lượt v1, v2, v3 WHEN mỗi lần approve THEN sau v2: v1 obsolete + current=v2; sau v3: v2 obsolete + current=v3; mọi thời điểm đúng 1 version approved.
  - AC2 (lần đầu): GIVEN tài liệu chưa có version approved WHEN approve v1 THEN current=v1, không có bản nào bị obsolete.
  - AC3 (immutable obsolete): GIVEN v1 đã obsolete WHEN cố sửa v1 THEN trả 422 `VERSION_LOCKED` (CONSTRAINT-3); v1 vẫn truy xuất được trong lịch sử.
  - AC4 (concurrency): GIVEN 2 request approve 2 version khác nhau của cùng tài liệu đồng thời WHEN xử lý THEN kết thúc đúng 1 version `approved` là current; không có 2 current (NFR-CONCUR-DOC-001).
- **Data cần thiết:** Document.current_version_id; DocumentVersion.status (approved↔obsolete); transaction + row-lock trên document.
- **API cần:** nội bộ (hệ quả của approve FR-DOC-009).

---

### FR-DOC-012: Tải file phiên bản tài liệu — chỉ bản approved (trừ người soạn/duyệt) + ghi access log (R15)

- **Mô tả:** Tải file của một version. **Mặc định chỉ tải được version `approved` (current)**; version `draft`/`review` chỉ người soạn + người duyệt phòng đó + Admin/leader tải được; version `obsolete` tải có cảnh báo "tài liệu lỗi thời — không sử dụng" cho người có quyền xem lịch sử (OQ#4 chốt chính sách obsolete). **Mỗi lượt tải ghi `document_access_log` action=`download`** (R15) + audit.
- **Độ ưu tiên:** P0
- **Actor:** Admin, leader, staff (theo mức bảo mật + trạng thái version), Kế toán (👁 — chỉ approved/current).
- **Tiền điều kiện:** version tồn tại; user có quyền xem theo mức bảo mật (BR-DOC-006) + theo trạng thái version (BR-DOC-011).
- **Luồng chính:**
  1. User mở chi tiết tài liệu → "Tải" version current (mặc định).
  2. Hệ thống validate quyền (mức bảo mật + trạng thái version — BR-DOC-006/011) → trả presigned URL / stream file từ MinIO.
  3. Ghi `document_access_log` action=`download` + `audit_logs` action=`DOCUMENT_DOWNLOAD`.
- **Luồng phụ / ngoại lệ:**
  - A1: cố tải version `draft`/`review` mà không phải người soạn/duyệt/Admin/leader → 403 `VERSION_NOT_PUBLISHED` (BR-DOC-011).
  - A2: cố tải version `obsolete` (chính sách OQ#4): default cho người có quyền xem lịch sử + cảnh báo; nếu KH chốt chặn → 403 `OBSOLETE_DOWNLOAD_FORBIDDEN`.
  - A3: mức bảo mật cao hơn quyền user → 403 `FORBIDDEN` (BR-DOC-006).
  - A4: MinIO down → 503; ghi log ERROR (không lộ stack ra client).
- **Hậu điều kiện:** file tải được; lượt download ghi `document_access_log` (R15); audit ghi nhận.
- **Business Rules:** BR-DOC-006, BR-DOC-011, BR-DOC-015, BR-DOC-022 (obsolete đánh dấu).
- **Acceptance Criteria:**
  - AC1 (happy — approved): GIVEN tài liệu có v2 `approved` (current) WHEN staff tải v2 THEN trả file đúng, `document_access_log` ghi action=`download` (document_id, user_id, at), audit `DOCUMENT_DOWNLOAD`.
  - AC2 (chặn tải draft): GIVEN version v3 `draft` WHEN staff phòng khác (không soạn/duyệt) cố tải v3 THEN trả 403 `VERSION_NOT_PUBLISHED`, không ghi download.
  - AC3 (obsolete có cảnh báo — OQ#4 default): GIVEN v1 `obsolete` WHEN người có quyền xem lịch sử tải v1 THEN trả file kèm metadata cảnh báo "lỗi thời — không sử dụng", access_log ghi download (BR-DOC-022).
  - AC4 (R15 đếm đúng): GIVEN tài liệu được tải 5 lần bởi 3 user khác nhau WHEN xem thống kê (FR-DOC-015) THEN lượt download = 5 (BR-DOC-015).
  - AC5 (RBAC — Kế toán chỉ approved): GIVEN Kế toán WHEN cố tải version draft THEN trả 403; WHEN tải version approved THEN thành công + ghi download.
- **Data cần thiết:** DocumentVersion.file_key (qua attachments); document_access_log(document_id, user_id, action=download, at).
- **API cần:** "tải file version (presigned URL)".

---

### FR-DOC-013: State machine trạng thái phiên bản (nền tảng §8.3)

- **Mô tả:** Tập trạng thái version hợp lệ + phép chuyển hợp lệ (whitelist), enforce bởi 1 hàm transition trung tâm. Mọi chuyển trạng thái version đi qua hàm này; hàm kiểm tra (from, to) ∈ whitelist + quyền + tách soạn–duyệt trước khi cập nhật + ghi audit.

```
            ┌──────────────────────────────────────────────────────────────┐
            │            STATE MACHINE — DOCUMENT VERSION (§8.3)            │
            └──────────────────────────────────────────────────────────────┘

   [tạo version mới — FR-006]
            │
            ▼
      ┌───────────┐   gửi duyệt (FR-008)        ┌───────────┐
      │   draft   │ ──────────────────────────► │  review   │
      │ (bản nháp)│ ◄────────────────────────── │ (chờ duyệt)│
      └───────────┘   từ chối + lý do (FR-010)  └─────┬─────┘
            ▲          [review → draft]               │
            │                                          │ DUYỆT (FR-009)
            │  (sửa khi draft — FR-007)                │ người duyệt ≠ người soạn (§8.3.2)
            │                                          ▼
            │                                    ┌───────────┐
            │   tạo VERSION MỚI (FR-006) để sửa  │ approved  │  ◄── version HIỆU LỰC (current)
            └─ ── ── ── ── (KHÔNG sửa trực tiếp) │(đã ban hành)│      documents.current_version_id
                          approved là bất biến   └─────┬─────┘
                                                       │ approve version MỚI của cùng tài liệu
                                                       │ → bản approved cũ TỰ ĐỘNG obsolete (FR-011)
                                                       ▼
                                                 ┌───────────┐
                                                 │ obsolete  │  (giữ lịch sử §8.4 — KHÔNG xóa;
                                                 │ (lỗi thời)│   đánh dấu "KHÔNG SỬ DỤNG")
                                                 └───────────┘   (trạng thái cuối)
```

- **Phép chuyển HỢP LỆ (whitelist):**
  - `draft → review` (gửi duyệt — FR-008; cần có file đính kèm)
  - `review → approved` (duyệt — FR-009; người duyệt ≠ người soạn; có quyền `document:approve`)
  - `review → draft` (từ chối kèm lý do — FR-010)
  - `approved → obsolete` (**TỰ ĐỘNG** khi approve version mới của cùng tài liệu — FR-011; KHÔNG có thao tác obsolete thủ công độc lập ở bản đầu — xem OQ#4)
- **Phép chuyển KHÔNG hợp lệ (bị chặn 422 `INVALID_STATE_TRANSITION`):** mọi cặp ngoài whitelist, vd `draft → approved` (bỏ qua review), `obsolete → *` (obsolete là trạng thái cuối — muốn dùng lại thì tạo version mới), `approved → draft` (sửa trực tiếp bản đã ban hành — phải tạo version mới), `review → obsolete`.
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (gọi bởi FR-008/009/010/011).
- **Business Rules:** BR-DOC-007, BR-DOC-008, BR-DOC-009, BR-DOC-019.
- **Acceptance Criteria:**
  - AC1 (happy chuỗi chuẩn): GIVEN version mới WHEN đi draft→review→approved theo hành động hợp lệ THEN mỗi bước thành công + audit `DOCUMENT_VERSION_STATE_CHANGE` (from→to).
  - AC2 (chặn bỏ bước): GIVEN version `draft` WHEN cố chuyển thẳng `approved` THEN trả 422 `INVALID_STATE_TRANSITION`.
  - AC3 (obsolete là cuối): GIVEN version `obsolete` WHEN cố chuyển sang bất kỳ trạng thái nào THEN trả 422 `INVALID_STATE_TRANSITION` (tạo version mới để thay).
  - AC4 (approved không sửa trực tiếp): GIVEN version `approved` WHEN cố chuyển `approved→draft` THEN trả 422 `INVALID_STATE_TRANSITION` (CONSTRAINT-3).
  - AC5 (audit): GIVEN bất kỳ chuyển trạng thái nào WHEN xảy ra THEN có audit `DOCUMENT_VERSION_STATE_CHANGE` với from, to, trigger, user, correlation_id.
- **Data cần thiết:** DocumentVersion.status ENUM[draft, review, approved, obsolete]; hàm transition trung tâm + whitelist.
- **API cần:** không expose chuyển trạng thái tùy ý; là hệ quả của FR-008/009/010/011.

---

### FR-DOC-014: Ghi nhận lượt truy cập (view / download / edit) — R15

- **Mô tả:** Ghi mỗi lượt tương tác với tài liệu vào `document_access_log` (R15): `view` (mở chi tiết tài liệu — FR-005), `download` (tải file version — FR-012), `edit` (tạo/sửa version — FR-006/007). Bảng riêng high-volume, tách khỏi `audit_logs` (pháp lý §8.4) và `access_stats` (toàn hệ thống — M7). Ghi không chặn nghiệp vụ (best-effort, async/fire-and-forget được phép).
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (kèm theo các hành động view/download/edit của mọi user có quyền).
- **Tiền điều kiện:** user đã đăng nhập, thực hiện một trong các hành động trên với tài liệu được phép.
- **Luồng chính:**
  1. Khi user mở chi tiết / tải / tạo–sửa version → hệ thống ghi 1 dòng `document_access_log` (document_id, user_id, action, at).
- **Luồng phụ / ngoại lệ:**
  - A1: hành động bị 403 (không quyền) → KHÔNG ghi access_log (chỉ ghi audit truy cập trái phép nếu cần) — đếm chỉ lượt hợp lệ.
  - A2: ghi access_log lỗi → không rollback nghiệp vụ (best-effort); log WARN.
- **Hậu điều kiện:** lượt truy cập tích lũy phục vụ thống kê (FR-DOC-015).
- **Business Rules:** BR-DOC-015.
- **Acceptance Criteria:**
  - AC1 (view): GIVEN user mở chi tiết tài liệu `SOP-HOA-012` THEN ghi 1 dòng access_log action=`view` (document_id, user_id, at).
  - AC2 (download): GIVEN user tải version approved THEN ghi 1 dòng action=`download`.
  - AC3 (edit): GIVEN user tạo/sửa version THEN ghi 1 dòng action=`edit`.
  - AC4 (không đếm 403): GIVEN user bị 403 khi cố tải draft THEN KHÔNG có dòng access_log `download` cho lượt đó.
- **Data cần thiết:** DocumentAccessLog { id, document_id(FK), user_id(FK), action ∈ {view, download, edit}, at }.
- **API cần:** nội bộ (ghi kèm các hành động); không endpoint riêng cho client ghi.

---

### FR-DOC-015: Thống kê truy cập tài liệu (R15)

- **Mô tả:** Báo cáo tổng hợp số **lượt xem / lượt tải / lượt chỉnh sửa** mỗi tài liệu (R15) theo bộ lọc: khoảng thời gian, phòng ban, loại hành động, top N tài liệu được truy cập/tải nhiều nhất. Dữ liệu từ `document_access_log`. Cung cấp số liệu cho M6.3 (thống kê hệ thống).
- **Độ ưu tiên:** P0
- **Actor:** Admin, leader (toàn hệ thống). Staff/Kế toán: theo OQ (default: leader/admin xem thống kê; staff xem thống kê tài liệu phòng mình — OQ#3 phạm vi). 
- **Tiền điều kiện:** đã đăng nhập, có quyền xem thống kê.
- **Luồng chính:**
  1. User mở "Thống kê tài liệu" → chọn khoảng thời gian + phòng ban + loại hành động.
  2. Hệ thống tổng hợp từ `document_access_log` (COUNT theo document_id × action) → trả bảng: tài liệu, lượt view, lượt download, lượt edit + top N.
  3. Cho phép xuất Excel/PDF (đồng bộ M6.4).
- **Luồng phụ / ngoại lệ:**
  - A1: khoảng thời gian quá rộng (dataset lớn) → giới hạn/cảnh báo; query dùng index `(document_id, action, at)`.
- **Hậu điều kiện:** chỉ đọc.
- **Business Rules:** BR-DOC-015, BR-DOC-005 (RBAC thống kê).
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN trong tháng tài liệu `SOP-HOA-012` có 30 view, 12 download, 3 edit WHEN leader xem thống kê tháng đó THEN bảng hiển thị đúng view=30, download=12, edit=3.
  - AC2 (lọc thời gian): GIVEN dữ liệu 2 tháng WHEN lọc chỉ tháng 6 THEN chỉ tính lượt trong tháng 6.
  - AC3 (top N): GIVEN nhiều tài liệu WHEN xem "top 10 tài liệu được tải nhiều nhất" THEN trả đúng 10 tài liệu sắp xếp giảm dần theo lượt download.
  - AC4 (RBAC): GIVEN staff thường WHEN xem thống kê toàn hệ thống THEN bị giới hạn theo phạm vi (OQ#3 default phòng mình) hoặc 403 nếu KH chốt chỉ leader/admin.
- **Data cần thiết:** Aggregate(document_access_log) GROUP BY document_id, action; bộ lọc at-range, department_id, action.
- **API cần:** "thống kê truy cập tài liệu (lọc + top N)", "xuất Excel/PDF thống kê".

---

### FR-DOC-016: Xem lịch sử thay đổi tài liệu (audit trail version — R3, §8.3)

- **Mô tả:** Hiển thị **lịch sử thay đổi đầy đủ** của một tài liệu (R3, §8.3 "nhận biết thay đổi"): timeline mọi version với ai tạo / khi nào / change_note / ai duyệt / khi nào duyệt / khi nào reject (+ lý do) / khi nào obsolete — dựng từ `document_versions` + `audit_logs` (action `DOCUMENT_VERSION_*`). Phục vụ truy vết khi đánh giá VILAS.
- **Độ ưu tiên:** P0
- **Actor:** Admin, leader, staff (theo phạm vi xem version — BR-DOC-011). Kế toán (👁) chỉ thấy các mốc của version approved/obsolete.
- **Tiền điều kiện:** tài liệu tồn tại; user có quyền xem.
- **Luồng chính:**
  1. User mở chi tiết tài liệu → tab "Lịch sử thay đổi".
  2. Hệ thống dựng timeline từ `document_versions` + `audit_logs` (lọc theo quyền hiển thị version) → hiển thị: v1 [tạo bởi A, 01/03; duyệt bởi T, 03/03; obsolete 10/06], v2 [...], v3 [...].
- **Luồng phụ / ngoại lệ:**
  - A1: user không quyền xem draft → timeline ẩn các version draft/review (chỉ approved/obsolete) (BR-DOC-011).
- **Hậu điều kiện:** chỉ đọc; (tùy chọn) ghi access_log `view`.
- **Business Rules:** BR-DOC-011, BR-DOC-019 (audit đầy đủ), BR-DOC-001.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN tài liệu có v1 (tạo bởi A, duyệt bởi T, obsolete) + v2 (tạo bởi A, reject bởi T với lý do, sửa lại, duyệt bởi T) WHEN trưởng nhóm xem lịch sử THEN timeline hiển thị đầy đủ ai/khi nào/change_note/lý do reject/người duyệt cho cả 2 version.
  - AC2 (RBAC hiển thị): GIVEN tài liệu có v3 draft WHEN staff phòng khác xem lịch sử THEN không thấy v3 trong timeline; thấy v1/v2 approved/obsolete.
  - AC3 (truy vết §8.3): GIVEN mọi chuyển trạng thái version WHEN xem lịch sử THEN mỗi mốc khớp với 1 bản ghi audit_logs (from→to, user, at).
- **Data cần thiết:** join document_versions + audit_logs (resource=document/document_version, resource_id).
- **API cần:** "lấy lịch sử thay đổi tài liệu (timeline version + audit)".

---

## 4. Business Rules

| ID | Quy tắc | Lý do nghiệp vụ | Hệ quả nếu vi phạm |
|----|---------|-----------------|--------------------|
| BR-DOC-001 | 1 tài liệu (`documents`) chứa 1..n phiên bản (`document_versions`); quan hệ 1-n. Tài liệu KHÔNG chứa file trực tiếp — file gắn vào từng version. UNIQUE(document_id, version) | Tách metadata tài liệu khỏi nội dung từng phiên bản (R3, §8.3) | Version mồ côi / trùng số version |
| BR-DOC-002 | Tài liệu có loại (`type`) thuộc danh mục cho phép (SOP/quy trình/biểu mẫu/hướng dẫn/tiêu chuẩn — OQ#2) | Phân loại chuẩn để tìm/lọc/báo cáo | 422 `INVALID_DOC_TYPE` |
| BR-DOC-003 | Tài liệu có mức bảo mật (`confidentiality_level`) thuộc danh mục cho phép (OQ#3); mặc định `public_internal` | Kiểm soát ai được xem/tải (§8.3 "bản hiện hành sẵn có tại nơi sử dụng" + hạn chế truy cập) | 422 `INVALID_CONFIDENTIALITY` |
| BR-DOC-004 | Tạo/sửa tài liệu & version chỉ trong **phạm vi phòng ban** của user (staff); Admin/leader mọi phòng | Cách ly dữ liệu phòng ban (R13); staff chỉ quản tài liệu phòng mình | 403 `FORBIDDEN` |
| BR-DOC-005 | **Kế toán CHỈ XEM** (👁) tài liệu **version approved/current**, KHÔNG tạo/sửa/duyệt/obsolete; mọi endpoint ghi M3 trả 403 cho Kế toán ở **tầng API** (không chỉ ẩn FE). Staff thường KHÔNG duyệt | Matrix RBAC demo-scope (Kế toán 👁 xem tài liệu); tách quyền duyệt | 403 `FORBIDDEN`; rò rỉ/sửa trái phép |
| BR-DOC-006 | Phạm vi **đọc/tải** version approved theo `confidentiality_level`: user chỉ xem/tải tài liệu ở mức bảo mật ≤ quyền của mình (ánh xạ cấp ↔ vai trò — OQ#3). Mức cao hơn quyền → không hiển thị + 403 khi truy cập trực tiếp | Bảo vệ tài liệu nhạy cảm (§8.3 hạn chế truy cập) | 403 `FORBIDDEN` / ẩn khỏi danh sách |
| BR-DOC-007 | Trạng thái version chỉ chuyển theo whitelist state machine (FR-013): draft→review, review→approved, review→draft, approved→obsolete (tự động khi approve bản mới). Mọi cặp ngoài whitelist bị chặn | Quy trình duyệt/ban hành phải nhất quán, không bỏ bước duyệt (§8.3.2 — phê duyệt trước ban hành) | 422 `INVALID_STATE_TRANSITION` |
| BR-DOC-008 | Tại 1 thời điểm mỗi tài liệu có **TỐI ĐA 1 version `approved` (current)**; approve version mới → version approved cũ TỰ ĐỘNG `obsolete` + `current_version_id` trỏ bản mới, **trong cùng transaction có row-lock** | §8.3 "chỉ phiên bản hiện hành được dùng; ngăn sử dụng tài liệu lỗi thời" — VILAS bắt buộc | 2 bản hiệu lực cùng lúc → dùng nhầm tài liệu; vi phạm VILAS |
| BR-DOC-009 | Người **duyệt** version (`approved_by`) PHẢI KHÁC người **soạn** version đó (`created_by`); người soạn KHÔNG tự duyệt — kể cả nếu là trưởng nhóm (cần người duyệt khác — OQ#6) | Tách trách nhiệm soạn–duyệt (§8.3.2 — phê duyệt bởi nhân sự được ủy quyền, khách quan) | 403 `SELF_APPROVAL_FORBIDDEN` |
| BR-DOC-010 | Quyền `document:approve` (duyệt/từ chối/ban hành) chỉ cấp cho **TRƯỞNG NHÓM CỐ ĐỊNH của phòng ban đó** (M7: `departments.lead_user_id`), Ban lãnh đạo, Admin. Staff thường KHÔNG có. M3 đọc thuộc tính trưởng nhóm từ M7 để enforce ở tầng API | Phê duyệt là quyền của nhân sự được ủy quyền (§8.3.2); tái dùng cơ chế trưởng nhóm OQ#11 M1 | 403 `FORBIDDEN` |
| BR-DOC-011 | Phạm vi **hiển thị version** theo trạng thái: `approved`/`obsolete` hiển thị cho mọi người có quyền xem tài liệu (theo mức bảo mật); `draft`/`review` chỉ người soạn + người duyệt (trưởng nhóm phòng đó) + Admin/leader thấy. Kế toán chỉ thấy approved/current | Tránh lan truyền bản nháp chưa duyệt; chỉ bản đã ban hành được dùng (§8.3) | Lộ bản nháp chưa duyệt → dùng nhầm tài liệu chưa hiệu lực |
| BR-DOC-012 | Chỉ version `draft` được sửa (file/change_note). Version `review`/`approved`/`obsolete` **bất biến** với thao tác sửa; sửa nội dung đã ban hành = tạo version mới | Bản đã gửi duyệt/ban hành không được tẩy xóa âm thầm (§8.3.2 d, §8.4) | 422 `VERSION_LOCKED` |
| BR-DOC-013 | File đính kèm version: chỉ loại cho phép (PDF, DOCX, XLSX, PNG, JPG — OQ; KHÔNG cho phép file thực thi/macro nguy hại) + ≤ giới hạn dung lượng (OQ); validate MIME thực + đuôi; lưu MinIO, không lưu binary trong DB | An toàn lưu trữ, tránh file độc hại (R2/R11, C01) | 422 `INVALID_FILE_TYPE` / `FILE_TOO_LARGE` |
| BR-DOC-014 | `documents.code` duy nhất toàn hệ thống, human-readable, **bất biến sau khi tạo**, không lộ ID tuần tự; `id` thật là UUID | Mã tài liệu là định danh kiểm soát ổn định (§8.3 nhận biết tài liệu); không lộ tuần tự (rule api.md) | 422 `CODE_IMMUTABLE`; trùng mã → retry; lộ tuần tự → rủi ro bảo mật |
| BR-DOC-015 | Mỗi lượt **view/download/edit** hợp lệ ghi 1 dòng `document_access_log` (document_id, user_id, action, at); lượt bị 403 KHÔNG đếm; thống kê (FR-015) tổng hợp từ bảng này, KHÔNG từ `audit_logs` | Đếm chính xác lượt truy cập/tải/chỉnh sửa (R15); tách high-volume khỏi audit pháp lý (đồng bộ M7 D11) | Thống kê sai; phình audit_logs |
| BR-DOC-016 | `change_note` bắt buộc từ version thứ 2 trở đi (mô tả thay đổi so với version trước); v1 có thể để trống | §8.3 "nhận biết thay đổi" — phải ghi rõ đổi gì giữa các phiên bản | 400 `CHANGE_NOTE_REQUIRED` |
| BR-DOC-017 | Version phải có **≥ 1 file đính kèm** trước khi gửi duyệt (`draft→review`) | Không duyệt tài liệu rỗng (nội dung là file) | 422 `VERSION_FILE_REQUIRED` |
| BR-DOC-018 | Thông báo in-app (gửi duyệt / approve / reject): mỗi version × mỗi sự kiện chỉ gửi 1 notification tới đúng người liên quan; idempotent (dùng `idx_notif_ref` M7) | Chống spam thông báo (C02) | Spam thông báo |
| BR-DOC-019 | Mọi thao tác tạo/sửa/gửi duyệt/duyệt/reject/ban hành/obsolete/tải/đổi metadata ghi `audit_logs` (user, action, resource, resource_id, correlation_id, ip, at, detail before/after khi sửa) | §8.3/§8.4 kiểm soát tài liệu & hồ sơ — duy trì công nhận VILAS | Thiếu audit → vi phạm VILAS |
| BR-DOC-020 | Từ chối version (`review→draft`) bắt buộc nhập `reject_reason` | Truy vết lý do trả về sửa (§8.3 soát xét) | 400 `REJECT_REASON_REQUIRED` |
| BR-DOC-021 | KHÔNG hard-delete version đã từng `approved`/`obsolete` (giữ vĩnh viễn hồ sơ §8.4); chỉ version `draft` chưa từng gửi duyệt được xóa (soft-delete + audit). KHÔNG hard-delete tài liệu đã có version approved | §8.4 lưu giữ hồ sơ — bản đã ban hành/lỗi thời phải giữ để truy vết | Mất hồ sơ ban hành; vi phạm §8.4 |
| BR-DOC-022 | Version `obsolete` phải được **đánh dấu rõ ràng "KHÔNG SỬ DỤNG / lỗi thời"** ở mọi nơi hiển thị + khi tải (metadata cảnh báo); chính sách cho/chặn tải bản obsolete theo OQ#4 | §8.3 "ngăn việc sử dụng ngoài ý muốn tài liệu lỗi thời" | Dùng nhầm tài liệu lỗi thời |

---

## 5. Use Case chính

### UC-DOC-01: Tạo tài liệu + phiên bản đầu (v1)
- **Actor chính:** staff (phòng mình) / leader / Admin.
- **Tiền điều kiện:** cần số hóa một SOP mới của phòng.
- **Luồng:**
  1. Staff phòng Hóa tạo tài liệu (FR-001): tiêu đề "SOP đo pH", loại=SOP, phòng=Hóa, mức bảo mật=public_internal → sinh `code`=`SOP-HOA-012`, status=`active`, current=NULL.
  2. Staff tạo version đầu v1 (FR-006): upload file "sop-do-ph-v1.pdf" → version số=1 status=`draft` (change_note v1 có thể trống).
  3. Audit `DOCUMENT_CREATE` + `DOCUMENT_VERSION_CREATE`; access_log `edit`.
- **Hậu điều kiện:** tài liệu + v1 draft sẵn sàng gửi duyệt.
- **Liên kết FR:** FR-DOC-001, 003, 006.

### UC-DOC-02: Tạo phiên bản mới + gửi duyệt
- **Actor chính:** staff (người soạn).
- **Tiền điều kiện:** tài liệu đã có v1 approved (current); cần cập nhật nội dung.
- **Luồng:**
  1. Staff A tạo version mới v2 (FR-006): upload file mới + change_note "Cập nhật ngưỡng hiệu chuẩn" → v2 `draft`. v1 vẫn approved/current.
  2. (Tùy) A sửa v2 draft vài lần (FR-007).
  3. A gửi v2 đi duyệt (FR-008): v2 `draft→review`; trưởng nhóm phòng nhận notification.
- **Ngoại lệ:** gửi duyệt khi v2 chưa có file → 422 `VERSION_FILE_REQUIRED`; thiếu change_note v2 → 400 `CHANGE_NOTE_REQUIRED`; đã có draft khác → 409 `DRAFT_ALREADY_EXISTS` (OQ#6).
- **Hậu điều kiện:** v2 `review` chờ duyệt; v1 vẫn current.
- **Liên kết FR:** FR-DOC-006, 007, 008.

### UC-DOC-03: Duyệt/ban hành + tự động obsolete bản cũ (CỐT LÕI §8.3)
- **Actor chính:** trưởng nhóm phòng (người duyệt, ≠ người soạn).
- **Tiền điều kiện:** v2 ở `review`; trưởng nhóm có quyền `document:approve`; trưởng nhóm ≠ người soạn v2.
- **Luồng:**
  1. Trưởng nhóm T mở v2 `review`, xem file + change_note.
  2. T duyệt v2 (FR-009): trong 1 transaction → v2 `review→approved` (approved_by=T, approved_at); v1 `approved→obsolete` tự động; `current_version_id`=v2.
  3. Người soạn A nhận notification "v2 đã ban hành"; audit `DOCUMENT_VERSION_APPROVE` + `DOCUMENT_VERSION_OBSOLETE`(v1).
  4. (Biến thể reject — FR-010): nếu T thấy thiếu sót → từ chối với lý do → v2 `review→draft`; A sửa lại rồi gửi duyệt lại.
- **Ngoại lệ:** A tự duyệt v2 → 403 `SELF_APPROVAL_FORBIDDEN`; staff thường duyệt → 403 `FORBIDDEN`; duyệt khi v2 không ở review → 422 `INVALID_STATE_TRANSITION`; reject thiếu lý do → 400 `REJECT_REASON_REQUIRED`.
- **Hậu điều kiện:** đúng 1 version current (v2); v1 obsolete giữ trong lịch sử (§8.4).
- **Liên kết FR:** FR-DOC-009, 010, 011, 013.

### UC-DOC-04: Tải tài liệu hiệu lực + ghi access log (R15)
- **Actor chính:** mọi user có quyền xem (staff/leader/Kế toán 👁).
- **Tiền điều kiện:** tài liệu có version approved; mức bảo mật cho phép user.
- **Luồng:**
  1. User mở chi tiết tài liệu (FR-005) → access_log `view`.
  2. User tải version current/approved (FR-012) → nhận presigned URL/file từ MinIO; access_log `download` + audit `DOCUMENT_DOWNLOAD`.
- **Ngoại lệ:** cố tải version draft (không phải người soạn/duyệt) → 403 `VERSION_NOT_PUBLISHED`; mức bảo mật cao hơn quyền → 403 `FORBIDDEN`; tải bản obsolete → cảnh báo "lỗi thời" (OQ#4 default cho phép có cảnh báo).
- **Hậu điều kiện:** file tải được; lượt download tích lũy cho thống kê.
- **Liên kết FR:** FR-DOC-005, 012, 014.

### UC-DOC-05: Xem thống kê truy cập tài liệu (R15)
- **Actor chính:** leader / Admin (toàn hệ thống); staff (phòng mình — OQ#3 default).
- **Tiền điều kiện:** đã có dữ liệu `document_access_log`.
- **Luồng:**
  1. Leader mở "Thống kê tài liệu" → chọn tháng + phòng ban + loại hành động.
  2. Hệ thống tổng hợp từ `document_access_log` → bảng: mỗi tài liệu có lượt view/download/edit + top N được tải nhiều nhất (FR-015).
  3. Xuất Excel/PDF (đồng bộ M6.4).
- **Hậu điều kiện:** báo cáo phục vụ rà soát VILAS + quản lý.
- **Liên kết FR:** FR-DOC-014, 015, 016.

---

## 6. Yêu cầu phi chức năng (NFR)

Theo template `~/.claude/rules/nfr.md`. Con số định cỡ cho quy mô **~40 user** (C03), môi trường staging tương đương production (Docker Compose, ~2–4 vCPU/8GB). Giả định cao điểm: ~10 concurrent users. Lượng dữ liệu giả định: ~5,000 tài liệu + ~20,000 version + ~500,000 dòng `document_access_log` (R15 high-volume).

```
NFR-PERF-DOC-001: Tạo/sửa tài liệu, version & chuyển trạng thái
────────────────────────────────────────────────────
Mô tả:     API tạo tài liệu/version, gửi duyệt, duyệt/ban hành (gồm obsolete
           bản cũ trong transaction) phải phản hồi đủ nhanh để soạn–duyệt liền mạch.
Metric:    P95 < 400ms | P99 < 700ms (không tính thời gian upload file)
Tool đo:   k6 (tests/performance/document-version-workflow.js)
Điều kiện: 10 concurrent users, dataset 5,000 tài liệu / 20,000 version, staging
Pass:      p(95) < 400ms suốt 10 phút ở 10 concurrent users, error rate < 1%
Fail:      p(95) ≥ 400ms → review index (documents.code, document_id, status,
           current_version_id; document_versions(document_id, version))
Ưu tiên:  Must Have
```
```
NFR-PERF-DOC-002: Tìm kiếm / liệt kê tài liệu
────────────────────────────────────────────────────
Metric:    P95 < 500ms cho danh sách phân trang 20/trang (lọc loại/phòng/
           mức bảo mật/từ khóa)
Tool đo:   k6 (tests/performance/document-search.js)
Điều kiện: 10 concurrent users, 5,000 tài liệu
Pass:      p(95) < 500ms; query dùng index (không Sequential Scan bảng lớn)
Fail:      p(95) ≥ 500ms → thêm index (type, department_id, confidentiality_level)
           + GIN trgm cho title/code
Ưu tiên:  Should Have
```
```
NFR-PERF-DOC-003: Tải file & thống kê truy cập
────────────────────────────────────────────────────
Metric:    Tải file version (presigned URL từ MinIO) bắt đầu trong < 1s (P95);
           báo cáo thống kê truy cập (FR-015) 1 tháng < 3s (P95).
Tool đo:   k6 + đo thời gian sinh presigned URL + aggregate query
Điều kiện: 5 concurrent users; document_access_log 500,000 dòng
Pass:      P95 tải < 1s; P95 thống kê < 3s; aggregate dùng index (document_id, action, at)
Fail:      timeout → cache/aggregate trước (materialized) + job nền
Ưu tiên:  Should Have
```
```
NFR-CONCUR-DOC-001: An toàn tương tranh khi duyệt/ban hành (Must)
────────────────────────────────────────────────────
Mô tả:     Approve version (gồm obsolete bản cũ + set current) phải an toàn
           tương tranh — không tạo 2 version approved/current cùng lúc cho 1 tài liệu.
Metric:    Với K request approve đồng thời các version khác nhau của cùng tài liệu,
           kết thúc đúng 1 version approved là current; 0 trường hợp 2 current.
Tool đo:   k6 ramping-vus + kiểm tra DB + audit
Điều kiện: 20 request song song trên 1 tài liệu (approve nhiều version)
Pass:      Luôn đúng 1 version approved/current; trạng thái nhất quán state machine
Fail:      Có > 1 current → fix row-lock/transaction trên document (BR-DOC-008)
Ưu tiên:  Must Have
```
```
NFR-AUDIT-DOC-001: Đầy đủ & bất biến audit + lịch sử version (VILAS §8.3/§8.4) (Must)
────────────────────────────────────────────────────
Mô tả:     Mọi thao tác tạo/sửa/gửi duyệt/duyệt/reject/ban hành/obsolete/tải/đổi
           metadata ghi audit_logs; version approved/obsolete bất biến; lịch sử
           thay đổi dựng lại đầy đủ cho mọi tài liệu.
Metric:    100% thao tác ghi có bản ghi audit_logs với correlation_id;
           0 endpoint sửa/xóa version đã approved/obsolete; 0 endpoint hard-delete
           version đã từng approved; lịch sử version (R3) dựng đủ cho 100% tài liệu.
Tool đo:   Test tự động đếm audit/thao tác + rà route (không PATCH/DELETE version
           approved/obsolete; không hard-delete tài liệu có version approved)
Pass:      Tỷ lệ audit/thao tác = 100%; version approved/obsolete immutable
Fail:      < 100% hoặc tồn tại route sửa/xóa bản đã ban hành → block (VILAS §8.3/§8.4)
Ưu tiên:  Must Have
```
```
NFR-INTEG-DOC-001: Toàn vẹn phiên bản — chỉ 1 hiệu lực (VILAS §8.3) (Must)
────────────────────────────────────────────────────
Mô tả:     Bất biến hệ thống: mỗi tài liệu luôn có ≤ 1 version approved; bản cũ
           obsolete khi ban hành bản mới; current_version_id luôn trỏ đúng bản approved.
Metric:    Với toàn bộ tài liệu: COUNT(version WHERE status='approved') ≤ 1/tài liệu
           tại MỌI thời điểm; current_version_id IS NULL hoặc trỏ version approved.
Tool đo:   Invariant check (test + query định kỳ) + concurrency test
Pass:      0 tài liệu có > 1 version approved; 0 current_version_id trỏ version không-approved
Fail:      Bất kỳ vi phạm → fix logic approve/obsolete (BR-DOC-008, FR-011)
Ưu tiên:  Must Have
```
```
NFR-SEC-DOC-001: Phân quyền & tách soạn–duyệt (Must)
────────────────────────────────────────────────────
Mô tả:     Enforce RBAC + phạm vi phòng ban + mức bảo mật ở tầng API (không chỉ FE);
           Kế toán chỉ xem approved; staff thường không duyệt; quyền approve chỉ
           trưởng nhóm phòng/leader/admin; người soạn không tự duyệt; bản nháp/chờ
           duyệt không lộ ra ngoài người soạn+người duyệt.
Metric:    Ma trận test 4 vai trò × action M3 (gồm trưởng nhóm vs staff thường) pass
           100%; Kế toán 403 ở 100% endpoint ghi + không thấy draft; người soạn không
           tự duyệt được; 0 lần lộ draft/review cho người ngoài; mức bảo mật cao hơn
           quyền → 0 lần truy cập được.
Tool đo:   Test RBAC tự động (security-auditor) + manual
Pass:      0 truy cập trái phép; 0 self-approval; 0 staff thường duyệt; 0 lộ draft
Fail:      Bất kỳ bypass nào → block go-live (OWASP A01)
Ưu tiên:  Must Have
```
```
NFR-SEC-DOC-002: An toàn upload/lưu file tài liệu (Must)
────────────────────────────────────────────────────
Metric:    Chỉ chấp nhận loại file whitelist (PDF/DOCX/XLSX/PNG/JPG — OQ; KHÔNG
           file thực thi/macro) validate MIME thực + đuôi, ≤ giới hạn dung lượng;
           không thực thi file; lưu MinIO, không lưu binary trong DB; tải qua
           presigned URL có hạn / kiểm soát quyền.
Tool đo:   Test upload file độc hại/sai loại/quá lớn + kiểm tra access control URL
Pass:      File sai loại/quá lớn bị 422; file hợp lệ tải lại đúng; URL không bypass quyền
Ưu tiên:  Must Have
```
```
NFR-SEC-DOC-003: Mã tài liệu không lộ định danh tuần tự (Should)
────────────────────────────────────────────────────
Metric:    ID nội bộ là UUID; định danh dùng ngoài là code/UUID, không expose serial
           id liên tiếp; 2 tài liệu liên tiếp không suy ra thứ tự nội bộ.
Tool đo:   Rà response API + định dạng định danh
Pass:      Không lộ serial id; documents.code duy nhất
Ưu tiên:  Should Have
```
```
NFR-MAINT-DOC-001: Test coverage domain tài liệu (Must)
────────────────────────────────────────────────────
Metric:    Service state machine version / approve+obsolete (chỉ 1 current) /
           tách soạn–duyệt / RBAC scope + mức bảo mật / immutable version /
           ghi access_log coverage ≥ 85%; module M3 overall ≥ 70%.
Tool đo:   pytest --cov
Pass:      ≥ 85% domain, ≥ 70% module; CI block nếu drop > 5%
Ưu tiên:  Must Have
```
```
NFR-OBS-DOC-001: Logging & truy vết (Should)
────────────────────────────────────────────────────
Metric:    Mọi request M3 có correlation_id xuyên FE→BE→audit_logs; chuyển trạng
           thái/duyệt/ban hành ghi log INFO; chuyển sai whitelist / self-approval /
           tải bản chưa publish ghi WARN; lỗi MinIO/transaction ghi ERROR kèm stack
           (không lộ ra client).
Tool đo:   Rà log + test
Pass:      Trace được 1 tài liệu từ log FE → audit DB qua correlation_id
Ưu tiên:  Should Have
```
```
NFR-DATA-DOC-001: Thống kê truy cập tách high-volume (Should)
────────────────────────────────────────────────────
Mô tả:     document_access_log (R15) ghi nhiều → tách khỏi audit_logs (pháp lý);
           cho phép retention/prune riêng; ghi best-effort không chặn nghiệp vụ.
Metric:    Ghi access_log không làm tăng P95 thao tác > 10%; aggregate thống kê
           dùng index; có chính sách retention (vd giữ 24 tháng — OQ vận hành).
Tool đo:   So sánh P95 có/không ghi access_log + EXPLAIN aggregate
Pass:      P95 tăng ≤ 10%; aggregate không Sequential Scan bảng access_log lớn
Ưu tiên:  Should Have
```

---

## 7. Giả định & Ràng buộc (tổng hợp)

**Assumptions:** xem §2.5 (ASSUMPTION-1..6).

**Constraints:** xem §2.4 (CONSTRAINT-1..11).

**Ghi chú cấu trúc dữ liệu cho `schema-designer`:**
- **`documents`:** `id UUID PK`, `code VARCHAR UNIQUE NOT NULL` (bất biến — BR-DOC-014), `title VARCHAR NOT NULL`, `type VARCHAR` (CHECK danh mục — OQ#2), `department_id FK→departments NOT NULL`, `confidentiality_level VARCHAR` (CHECK danh mục — OQ#3, default `public_internal`), `status VARCHAR` (CHECK active|archived), `current_version_id UUID FK→document_versions NULL`, `created_by/updated_by FK→users`, `created_at/updated_at`. Lưu ý vòng FK `documents.current_version_id ↔ document_versions.document_id`: tạo `documents` (current_version_id NULL, chưa FK) → `document_versions` → ALTER ADD FK current_version_id (giống cách M7 xử lý vòng departments↔users). `current_version_id` luôn trỏ version `approved` hoặc NULL (BR-DOC-008 / NFR-INTEG-DOC-001).
- **`document_versions`:** `id UUID PK`, `document_id FK→documents NOT NULL`, `version INT NOT NULL`, `change_note TEXT NULL` (bắt buộc app-level từ v2 — BR-DOC-016), `status VARCHAR` CHECK(draft|review|approved|obsolete), `created_by FK→users NOT NULL`, `created_at`, `approved_by FK→users NULL`, `approved_at TIMESTAMPTZ NULL`, `reject_reason TEXT NULL` (hoặc lưu trong audit detail), `created_at/updated_at`. **UNIQUE(document_id, version)**. **Partial unique đảm bảo ≤1 approved/tài liệu:** `CREATE UNIQUE INDEX uq_doc_one_approved ON document_versions(document_id) WHERE status='approved';` (DB-level enforce BR-DOC-008 — mạnh hơn app-only). approved_by ≠ created_by enforce app-level (BR-DOC-009). File gắn qua `attachments` (owner_type='document_version', owner_id=version.id) — không lưu file_key trực tiếp trên bảng để đồng bộ polymorphic M7 (hoặc denormalize `primary_file_key` nếu schema-designer thấy cần — 1 file chính/version).
- **`document_access_log` (R15 — M3 tự tạo, demo-scope dòng 235-237):** `id UUID PK`, `document_id FK→documents NOT NULL`, `user_id FK→users NOT NULL`, `action VARCHAR` CHECK(view|download|edit), `at TIMESTAMPTZ DEFAULT now()`. High-volume; cho phép retention/prune (NFR-DATA-DOC-001). KHÔNG immutable trigger như audit_logs (không phải hồ sơ pháp lý — D11 tinh thần access_stats).
- **Trưởng nhóm (phụ thuộc M7):** đọc `departments.lead_user_id` để cấp `document:approve` trong phòng (BR-DOC-010) — đã có ở M7 (08-contract-m7-schema). M3 KHÔNG tạo cột trưởng nhóm mới.
- **`attachments` (dùng chung M7):** owner_type ∈ {`document`, `document_version`} cho M3 — whitelist đã có (08-contract-m7-schema dòng 293). 1 file chính/version (bản đầu); nhiều file phụ trợ tùy OQ.
- **`roles_permissions` (M7 đã seed):** `document:create` (staff scope department, leader/admin all), `document:read` (mọi vai trò + accountant scope all), `document:approve` (admin/leader all; staff = chỉ trưởng nhóm — app check). Phù hợp BR-DOC-004/005/006/010.
- **Index gợi ý:** `documents(code)` unique, `documents(department_id, type)`, `documents(confidentiality_level)`, GIN trgm `documents(title)`/`documents(code)` cho tìm kiếm, `documents(current_version_id)`; `document_versions(document_id, version)` unique, `document_versions(document_id, status)` (lấy current + danh sách), partial `uq_doc_one_approved (document_id) WHERE status='approved'`, `document_versions(status) WHERE status='review'` (hàng đợi chờ duyệt — FR-009), `document_versions(created_by)`; `document_access_log(document_id, action, at)` (thống kê FR-015), `document_access_log(at)` (lọc kỳ), `document_access_log(user_id, at)` (tùy báo cáo).
- **State transition:** hàm trung tâm + whitelist (FR-DOC-013); approve (FR-009/011) chạy trong transaction + row-lock trên `documents` để đảm bảo ≤1 current (NFR-CONCUR-DOC-001 / NFR-INTEG-DOC-001).
- **Soft-delete:** chỉ version `draft` chưa từng gửi duyệt được soft-delete (cột `deleted_at` + audit); version đã từng approved/obsolete KHÔNG xóa (BR-DOC-021); tài liệu có version approved KHÔNG hard-delete.

---

## 8. OPEN QUESTIONS (cần KH trả lời — phần lớn KHÔNG chặn `/contract`)

| # | Câu hỏi | Tại sao cần biết | Ảnh hưởng nếu chưa rõ (default đề xuất) | Người trả lời | Deadline | Chặn contract? |
|---|---------|------------------|------------------------------------------|---------------|----------|----------------|
| 1 | **Định dạng mã tài liệu (`code`)** mong muốn? (vd `SOP-HOA-012`, `QT-01`, mã theo hệ thống tài liệu QMS sẵn có của lab) | Sinh mã (FR-003) | Default `<LOAI>-<MAPHONG>-<seq>`; đổi format cấu hình, KHÔNG đổi schema | Trưởng phòng QA/Quản lý chất lượng | Khi UAT | **Không** — cấu hình |
| 2 | **Danh mục LOẠI tài liệu** đầy đủ? (SOP, quy trình, biểu mẫu, hướng dẫn công việc, tiêu chuẩn/quy chuẩn, chính sách, sổ tay chất lượng…) | Phân loại (FR-001, BR-DOC-002) | Default 5 loại (SOP/quy trình/biểu mẫu/hướng dẫn/tiêu chuẩn); thêm vào CHECK/danh mục | Quản lý chất lượng | Trước `/contract` (ưu tiên) | **Không** — danh mục cấu hình, nhưng nên chốt sớm |
| 3 | **Các MỨC BẢO MẬT** có những cấp nào + ánh xạ cấp ↔ vai trò ai được xem? | Kiểm soát đọc/tải (BR-DOC-006); ai xem thống kê (FR-015) | Default 3 cấp (`public_internal` mọi vai trò; `restricted` staff phòng+leader+admin; `confidential` leader+admin). Cần KH xác nhận ánh xạ | Ban lãnh đạo + QA | Trước `/contract` (ưu tiên) | ⚠️ **Nên chốt** — ảnh hưởng RBAC đọc lõi (default an toàn nhưng cần xác nhận pháp lý/nội bộ) |
| 4 | **Tài liệu obsolete CÓ cho tải lại không?** (chặn hoàn toàn / cho người có quyền tải kèm cảnh báo "lỗi thời") | Chính sách tải bản cũ (FR-012, BR-DOC-022) | Default: cho người có quyền xem lịch sử tải kèm cảnh báo rõ "KHÔNG SỬ DỤNG"; người thường chỉ thấy current. §8.3 yêu cầu "ngăn sử dụng ngoài ý muốn" | Quản lý chất lượng | Khi UAT | **Không** — biến thể luồng có default §8.3-safe |
| 5 | **Duyệt 1 bước hay NHIỀU NGƯỜI/đa cấp?** (review → approved 1 người; hay review → QA → director tuần tự) | Số bước state machine (FR-009) | Default **1 bước** (1 người duyệt = trưởng nhóm/leader/admin). Đa cấp → mở rộng state machine (CR) | Ban lãnh đạo | Trước `/contract` (ưu tiên) | ⚠️ **Nên chốt** — nếu cần đa cấp sẽ đổi state machine (mặc định 1 bước) |
| 6 | **Nếu người soạn LÀ trưởng nhóm (người duyệt duy nhất của phòng) thì ai duyệt?** + cho phép nhiều draft song song không? | Tách soạn–duyệt (BR-DOC-009) khi trùng người; ràng buộc 1 draft/tài liệu (FR-006) | Default: khi người soạn = trưởng nhóm → người duyệt phải là leader/admin (cấp trên); chỉ 1 draft/tài liệu tại 1 thời điểm | Ban lãnh đạo | Trước `/contract` (ưu tiên) | ⚠️ **Nên chốt** — quy tắc tách trách nhiệm khi lab nhỏ (default an toàn) |
| 7 | Có cần **xác nhận "đã đọc" tài liệu mới ban hành** (controlled distribution / acknowledgement) không? | Mở rộng scope phân phối có kiểm soát | Default: KHÔNG (ngoài scope bản đầu → CR) | Quản lý chất lượng | Khi UAT | **Không** — ngoài scope, CR nếu cần |
| 8 | Có cần **nhắc rà soát định kỳ tài liệu** (vd review SOP hằng năm) bằng cron không? | Thêm cron + trường review_due_date | Default: KHÔNG (ngoài scope bản đầu → CR); có thể thêm sau như CRON nhắc | Quản lý chất lượng | Khi UAT | **Không** — ngoài scope, CR nếu cần |

> **Kết luận:** #1/#4/#7/#8 là tham số cấu hình/biến thể có default rõ → KHÔNG chặn `/contract`. **#2 (danh mục loại), #3 (mức bảo mật + ánh xạ vai trò), #5 (1 bước hay đa cấp duyệt), #6 (ai duyệt khi người soạn là trưởng nhóm)** NÊN chốt với KH trước `/contract` vì ảnh hưởng **RBAC đọc lõi** (#3) và **state machine duyệt lõi** (#5/#6). Các mục này đã có **default an toàn theo §8.3**, có thể vào contract với default nếu KH chưa kịp chốt, nhưng mọi thay đổi default sau đó cần văn bản xác nhận KH ("Verbal is Nothing").

---

## 9. Ma trận truy vết (Traceability Matrix)

| FR ID | Yêu cầu gốc (meeting note) | Submodule (demo-scope) | Điều khoản 17025 | Business Rule | Test Case (QA sẽ tạo) | Trạng thái |
|-------|----------------------------|------------------------|------------------|---------------|------------------------|------------|
| FR-DOC-001 | (kho tài liệu QMS) | F3.1.1 | §8.3 | BR-001, 004, 005, 014 | TC-DOC-001..006 | Draft |
| FR-DOC-002 | (sửa metadata) | F3.1.1 | §8.3, §8.4 | BR-004, 005, 014 | TC-DOC-007..010 | Draft |
| FR-DOC-003 | (không lộ ID — rule api) | F3.1.1 | §8.3 | BR-014 | TC-DOC-011..013 | Draft |
| FR-DOC-004 | (phân loại — lọc/tìm) | F3.1.3 | §8.3 | BR-006, 015 | TC-DOC-014..018 | Draft |
| FR-DOC-005 | R3 (xem version) | F3.1.3, F3.2.1 | §8.3 | BR-006, 011, 015 | TC-DOC-019..023 | Draft |
| FR-DOC-006 | **R2 (kèm file), R3 (version)** | F3.1.2, F3.2.1 | §8.3.2, §8.4 | BR-001, 004, 012, 013, 016, 021 | TC-DOC-024..032 | Draft |
| FR-DOC-007 | R3 (sửa nháp) | F3.2.1 | §8.3.2 | BR-012, 013, 016 | TC-DOC-033..036 | Draft |
| FR-DOC-008 | R3 (quy trình duyệt) | F3.2.3 | **§8.3.2** | BR-007, 012, 017, 018 | TC-DOC-037..041 | Draft |
| FR-DOC-009 | R3 (duyệt/ban hành — tách soạn-duyệt) | F3.2.3 | **§8.3.2** | BR-007, 008, 009, 010, 012, 019 | TC-DOC-042..050 | Draft |
| FR-DOC-010 | R3 (từ chối) | F3.2.3 | §8.3.2 | BR-007, 010, 020 | TC-DOC-051..054 | Draft |
| FR-DOC-011 | R3 (chỉ bản hiệu lực được dùng) | F3.2.4 | **§8.3 (VILAS)** | BR-008, 019, 021 | TC-DOC-055..061 | Draft |
| FR-DOC-012 | **R2 (kèm file), R15 (lượt tải)** | F3.1.2, F3.2.4 | §8.3, §8.4 | BR-006, 011, 015, 022 | TC-DOC-062..069 | Draft |
| FR-DOC-013 | R3 (state machine duyệt/obsolete) | F3.2.3, F3.2.4 | §8.3 (xuyên suốt) | BR-007, 008, 009, 019 | TC-DOC-070..077 | Draft |
| FR-DOC-014 | **R15 (lượt truy cập/tải/chỉnh sửa)** | F3.3.1 | §8.4 | BR-015 | TC-DOC-078..082 | Draft |
| FR-DOC-015 | **R15 (thống kê truy cập)** | F3.3.1 | §8.4 | BR-015, 005 | TC-DOC-083..088 | Draft |
| FR-DOC-016 | **R3 (tài liệu — lịch sử)** | F3.2.2 | §8.3, §8.4 | BR-001, 011, 019 | TC-DOC-089..093 | Draft |

**Mapping điều khoản 17025 (demo-scope mục E):**
- **§8.3 Kiểm soát tài liệu** (cốt lõi M3): phê duyệt trước ban hành (FR-008/009), soát xét & phê duyệt lại (FR-006→009 version mới), nhận biết thay đổi & tình trạng phiên bản hiện hành (FR-016 lịch sử + `change_note`, FR-011 current), bản hiện hành sẵn có tại nơi sử dụng (FR-012 chỉ tải approved), ngăn sử dụng tài liệu lỗi thời (FR-011 auto-obsolete + BR-DOC-022 đánh dấu).
- **§8.3.2 Tách trách nhiệm**: người soạn ≠ người duyệt (BR-DOC-009 `SELF_APPROVAL_FORBIDDEN`); phê duyệt bởi nhân sự được ủy quyền (BR-DOC-010 trưởng nhóm/leader/admin).
- **§8.4 Kiểm soát hồ sơ**: audit đầy đủ + bất biến (BR-DOC-019, NFR-AUDIT-DOC-001), giữ version obsolete/approved không xóa (BR-DOC-021), versioning (BR-DOC-001).

**Liên kết liên module:**
- **M7 (nền tảng):** `users`/`departments`/`attachments`/`audit_logs`/`notifications` dùng chung; `departments.lead_user_id` cấp `document:approve` (CONSTRAINT-11, BR-DOC-010); quyền `document:*` đã seed (`roles_permissions`).
- **M6 (Báo cáo):** M6.3 tổng hợp `document_access_log` (R15, FR-DOC-015).
- **M1 (Mẫu):** tham chiếu SOP/phương pháp M3 ở mức đọc (§7.2) — ràng buộc cứng version ngoài scope bản đầu (§1.2 OUT-OF-SCOPE).

---

*Hết SRS M3 (v1.0). 16 FR · 22 BR · 5 UC · 13 NFR · 8 OPEN QUESTIONS. State machine version (draft→review→approved→obsolete) + tách soạn–duyệt (§8.3.2) + chỉ 1 version hiệu lực (auto-obsolete §8.3) + immutable bản approved (§8.4) + thống kê truy cập (R15) đã đặc tả đầy đủ, kiểm thử được. 4 OPEN QUESTIONS NÊN chốt trước `/contract` (#2 loại tài liệu, #3 mức bảo mật, #5 duyệt 1 bước/đa cấp, #6 ai duyệt khi soạn=trưởng nhóm) vì ảnh hưởng RBAC đọc + state machine duyệt lõi — đều có default an toàn theo §8.3. Mọi xác nhận tiếp theo phải bằng văn bản theo rule "Verbal is Nothing".*
