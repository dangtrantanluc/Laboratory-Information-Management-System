# SRS: M2 — Quản lý Hóa chất & Tồn kho (Chemical Inventory)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Module:** M2 — Quản lý Hóa chất & Tồn kho
**Version:** 1.2 | **Ngày:** 19/06/2026 | **Author:** BA agent
**Status:** DRAFT — KH đã chốt OPEN QUESTIONS #1/#2/#3/#4/#5 (19/06/2026); còn #6/#7/#8 cần confirm trước `/contract`
**Thay đổi v1.1 (19/06/2026):** cập nhật theo 4 quyết định chốt của KH — (1) quản lý đơn giá theo lô + giá trị tồn theo từng lô; (3) xuất hóa chất BẮT BUỘC gắn mẫu; (4) `adjust` do KTV phụ trách + Admin, bắt buộc lý do; (5) lô kiểm tra lại không đạt/quá hạn → cảnh báo + xác nhận mới cho xuất (không khóa cứng).
**Thay đổi v1.2 (19/06/2026):** chốt OQ#2 — **hệ thống TỰ QUY ĐỔI đơn vị** trong cùng nhóm đo (mass/volume/count). Mỗi hóa chất có 1 **đơn vị cơ sở (base unit)** để lưu trữ nội bộ (NUMERIC(18,6)); người dùng nhập/xuất/xem theo đơn vị tùy chọn cùng nhóm; hệ số quy đổi cố định, không sửa được; mỗi giao dịch lưu CẢ (qty_base, base_unit) lẫn (qty_input, input_unit) để audit/hiển thị; cấm quy đổi chéo nhóm. → FR-CHEM-001/002/005/006/008/013/014; BR-CHEM-026..030; NFR-CORRECT-CHEM-002.
**Nguồn:** `00-meeting-note-analysis.md` (R4, R16, N1, N2; quyết định chốt A03/A04/A04b/C01/C02/C03), `01-demo-scope.md` (M2.1–M2.4, RBAC matrix, ERD core)
**Chuẩn:** IEEE 830 (rút gọn) · ISO/IEC 17025:2017 §6.4, §6.6, §8.4

---

## 1. Giới thiệu

### 1.1 Mục đích

Tài liệu này đặc tả đầy đủ, không mơ hồ, kiểm thử được cho **Module M2 — Quản lý Hóa chất & Tồn kho** của hệ thống LIMS. Mục tiêu nghiệp vụ: thay thế việc ghi sổ tay/Excel rời rạc bằng một hệ thống quản lý hóa chất **theo lô (lot/batch)**, **tự động trừ tồn**, **gắn việc sử dụng hóa chất với mẫu thử nghiệm**, và **truy vết được toàn bộ giao dịch** để đáp ứng yêu cầu kiểm soát hồ sơ của ISO/IEC 17025:2017 (lab đã được công nhận VILAS).

Tài liệu dùng cho 2 đối tượng:
- **Khách hàng / Ban lãnh đạo lab:** xác nhận nghiệp vụ đúng.
- **Đội thiết kế (`schema-designer`, `api-designer`, `ux-designer`) và `feature-builder`:** đủ chi tiết để viết contract và implement mà không phải hỏi lại.

### 1.2 Phạm vi

Module M2 phủ 4 submodule (theo `01-demo-scope.md`):

| Submodule | Nội dung | Trong SRS này |
|-----------|----------|---------------|
| M2.1 Danh mục hóa chất | CRUD hóa chất (tên, CAS, NSX, đơn vị tùy loại); quản lý theo lô + hạn dùng + CoA; thông tin an toàn (MSDS, mã nguy hại) | ✅ FR-CHEM-001..004 |
| M2.2 Nhập/Xuất/Tồn | Nhật ký nhập; nhật ký xuất/sử dụng gắn mẫu; tự động trừ tồn theo lô đúng đơn vị; lịch sử giao dịch; cảnh báo tồn dưới ngưỡng | ✅ FR-CHEM-005..010 |
| M2.3 Kiểm tra lại & hạn dùng | Lịch kiểm tra lại; cron nhắc hết hạn / tới hạn kiểm tra (in-app) | ✅ FR-CHEM-011..012 |
| M2.4 Xuất Excel & báo cáo | Xuất Excel nhật ký xuất/nhập theo khoảng thời gian; báo cáo tiêu hao theo tháng/đề tài/người dùng | ✅ FR-CHEM-013..014 |

**Trong scope `[SCOPE]`:**
- CRUD hóa chất, lô, giao dịch nhập/xuất/điều chỉnh.
- Tính tồn theo lô + đơn vị, lưu `balance_after` mỗi giao dịch.
- Validation không cho xuất quá tồn; gợi ý FEFO.
- Cron nhắc hết hạn / tới hạn kiểm tra lại (in-app).
- Xuất Excel nhật ký; báo cáo tiêu hao.
- Audit log mọi thao tác CRUD hóa chất/lô/giao dịch.
- Đính kèm file CoA, MSDS (qua bảng `attachments` polymorphic chung).
- **Tự quy đổi đơn vị (OQ#2 đã chốt):** mỗi hóa chất có **đơn vị cơ sở (base unit)** + **nhóm đo (measurement group)** ∈ {mass, volume, count}; lưu trữ nội bộ mọi tồn/giao dịch bằng base unit (NUMERIC(18,6)); người dùng nhập/xuất/xem theo đơn vị tùy chọn **trong cùng nhóm** (kg/g/mg; L/mL; đơn vị đếm), hệ thống quy đổi về base unit để lưu và quy đổi ngược để hiển thị. Hệ số quy đổi cố định trong bảng `units`, không cho người dùng sửa. Mỗi giao dịch lưu cả (qty_base + base_unit) lẫn (qty_input + input_unit).
- Quản lý **đơn giá nhập theo lô** (`unit_price`, `currency` mặc định VND) và **tính giá trị tồn theo từng lô** = qty còn lại × `unit_price`; cột giá trị tiền trong báo cáo tiêu hao và Excel (OQ#1 đã chốt — chỉ hiển thị cho Admin/Ban lãnh đạo/Kế toán).

**Ngoài scope `[OUT-OF-SCOPE → cần CR]`:**
- Đặt hàng / mua hàng / nhà cung cấp (purchase order, vendor management).
- Kế toán giá vốn nâng cao / bình quân gia quyền / FIFO-FEFO theo giá trị: KHÔNG áp dụng. Giá trị tồn tính **theo TỪNG LÔ** (qty còn lại × `unit_price` của lô) — xem BR-CHEM-023 (OQ#1 đã chốt).
- Thông báo qua email / Zalo (C02: chỉ in-app).
- Tích hợp barcode/QR cho lô hóa chất (mới có cho mẫu — M1; nếu muốn cho hóa chất → CR).
- Quản lý vị trí lưu kho theo tủ/kệ/nhiệt độ (cold storage mapping) — chưa có trong demo-scope.
- **Quy đổi CHÉO nhóm đo** (vd g ↔ mL, đổi khối lượng sang thể tích qua tỷ trọng/nồng độ): KHÔNG hỗ trợ — hệ thống chỉ quy đổi trong cùng nhóm đo (BR-CHEM-028). Nếu KH cần quy đổi theo tỷ trọng/nồng độ → CR.
- Người dùng tự định nghĩa đơn vị mới hoặc sửa hệ số quy đổi: KHÔNG hỗ trợ (hệ số cố định do hệ thống quản trị — BR-CHEM-029). Thêm đơn vị mới vào danh mục `units` là tác vụ quản trị (seed/migration), không phải chức năng người dùng cuối.
- Module hiệu chuẩn thiết bị (thuộc M5, không thuộc M2).

### 1.3 Định nghĩa, từ viết tắt và thuật ngữ

| Thuật ngữ | Định nghĩa |
|-----------|------------|
| **Hóa chất (Chemical)** | Mục danh mục logic, định danh bởi tên + số CAS. Có **một đơn vị cơ sở** (`base_unit`) và **nhóm đo** (`measurement_group`) cố định; mọi tồn/giao dịch của nó được LƯU TRỮ NỘI BỘ theo `base_unit`. Người dùng có thể nhập/xuất/xem theo đơn vị khác trong cùng nhóm — hệ thống tự quy đổi (OQ#2 đã chốt). |
| **Đơn vị cơ sở (Base unit)** | Đơn vị dùng để LƯU TRỮ NỘI BỘ mọi số lượng tồn/giao dịch của một hóa chất (NUMERIC(18,6)). Khuyến nghị chọn đơn vị nhỏ nhất trong nhóm: **mg** (mass), **mL** (volume), **"đơn vị"/viên/ống** (count) để hạn chế mất chính xác khi quy đổi. |
| **Đơn vị nhập/hiển thị (Input/Display unit)** | Đơn vị người dùng chọn khi nhập/xuất hoặc khi xem tồn — phải thuộc CÙNG nhóm đo với `base_unit` của hóa chất. Hệ thống quy đổi về base unit để lưu và quy đổi ngược để hiển thị. |
| **Nhóm đo (Measurement group)** | Phân loại đơn vị: **mass** (kg/g/mg), **volume** (L/mL), **count** (đơn vị/viên/ống). KHÔNG cho phép quy đổi chéo nhóm. |
| **Hệ số quy đổi (factor_to_base)** | Hệ số CỐ ĐỊNH đổi 1 đơn vị về base unit của nhóm (vd 1 kg = 1 000 000 mg; 1 g = 1000 mg; 1 L = 1000 mL). Lưu trong bảng/danh mục `units`; người dùng KHÔNG được sửa (tránh sai số/gian lận). |
| **`qty_base` / `qty_input`** | Mỗi giao dịch lưu CẢ: `qty_base` (+ `base_unit`) = giá trị chuẩn để tính tồn; `qty_input` (+ `input_unit`) = đúng những gì người dùng nhập (để audit/hiển thị). `balance_after` luôn tính theo base unit. |
| **Lô (Lot/Batch)** | Một lần nhập cụ thể của một hóa chất, có số lô riêng, hạn dùng, ngày kiểm tra lại, file CoA. Tồn kho được tính **theo lô**. |
| **CAS (CAS Registry Number)** | Mã định danh hóa chất chuẩn quốc tế (vd 7647-14-5 cho NaCl). Định dạng `NNNNNNN-NN-N`. |
| **CoA (Certificate of Analysis)** | Chứng chỉ phân tích/chất lượng đi kèm lô hóa chất từ nhà cung cấp (17025 §6.6). |
| **MSDS/SDS** | Bảng dữ liệu an toàn hóa chất (Material/Safety Data Sheet). |
| **Mã nguy hại (Hazard code)** | Mã phân loại nguy hiểm (vd GHS: H225, H314...). |
| **FEFO (First Expired, First Out)** | Nguyên tắc xuất: lô hết hạn sớm nhất xuất trước. |
| **Tồn (Balance)** | Số lượng còn lại của một lô, tính theo đơn vị của hóa chất đó. |
| **`balance_after`** | Snapshot tồn của lô **ngay sau** một giao dịch — lưu trong từng giao dịch để audit, không tính lại bằng SUM runtime. |
| **Giao dịch (Transaction)** | Một bản ghi nhập/xuất/điều chỉnh tồn của một lô. Type ∈ {in, out, adjust}. |
| **`ref_sample_id`** | Tham chiếu tới mẫu thử nghiệm (M1) mà giao dịch xuất hóa chất phục vụ. **Bắt buộc (NOT NULL) với giao dịch xuất** (OQ#3 đã chốt). |
| **`unit_price` / giá trị tồn** | Đơn giá nhập của một lô (NUMERIC(14,2), kèm `currency` mặc định VND). **Giá trị tồn của lô** = qty còn lại × `unit_price`. Tính **theo từng lô** (không bình quân gia quyền) — OQ#1 đã chốt. |
| **Xuất lô cảnh báo (warning issue)** | Giao dịch xuất từ lô có kiểm tra lại "không đạt" hoặc đã quá hạn dùng — được phép sau khi người dùng xác nhận, có cờ `warning_override=true` và lý do trong audit (OQ#5 đã chốt). |
| **VILAS** | Hệ thống công nhận phòng thí nghiệm Việt Nam (theo ISO/IEC 17025). |
| **Audit log** | Bản ghi bất biến: ai, khi nào, làm gì, trên tài nguyên nào, với `correlationId` (17025 §8.4). |
| **RBAC** | Role-Based Access Control + phạm vi theo phòng ban. |
| **NUMERIC(14,4)** | Kiểu số thập phân cố định 14 chữ số tổng, 4 chữ số thập phân — dùng cho qty người dùng nhập/hiển thị (`qty_input`). |
| **NUMERIC(18,6)** | Kiểu số thập phân cố định 18 chữ số tổng, 6 chữ số thập phân — dùng cho LƯU TRỮ NỘI BỘ theo base unit (`qty_base`, `balance_after`, `chemical_lots.qty_base`) để không mất chính xác khi quy đổi xuống đơn vị nhỏ. KHÔNG dùng float ở bất kỳ đâu. |

### 1.4 Tài liệu tham chiếu

| Tài liệu | Vai trò |
|----------|---------|
| `lims/docs/00-meeting-note-analysis.md` | Yêu cầu gốc R1–R20 + quyết định đã chốt với KH 19/06/2026 |
| `lims/docs/01-demo-scope.md` | Cây module, RBAC matrix, ERD core, cron job, mapping 17025 |
| `~/.claude/rules/nfr.md` | Template NFR chuẩn IEEE 830 |
| `~/.claude/rules/api.md` | Quy ước REST, response format, status code |
| `~/.claude/rules/logging.md` | Structured logging, correlationId, error handling |
| **ISO/IEC 17025:2017** §6.4 | Cơ sở vật chất & điều kiện môi trường, **thiết bị & vật tư/hóa chất** |
| **ISO/IEC 17025:2017** §6.6 | Sản phẩm & dịch vụ do bên ngoài cung cấp (hóa chất mua ngoài + CoA) |
| **ISO/IEC 17025:2017** §8.4 | Kiểm soát hồ sơ (lưu trữ, truy xuất, bất biến, audit) |
| **ISO/IEC 17025:2017** §7.5 | Hồ sơ kỹ thuật (bản ghi gốc của hoạt động thử nghiệm) |

---

## 2. Mô tả tổng quan

### 2.1 Bối cảnh sản phẩm

M2 là một trong 7 module của LIMS monolith (FastAPI + Next.js + PostgreSQL + Redis + MinIO + APScheduler, Docker Compose). M2 **phụ thuộc** vào:

- **M7 (Auth + RBAC + phòng ban + audit log):** mọi API M2 yêu cầu xác thực JWT và kiểm tra quyền theo vai trò + phạm vi phòng ban. Audit ghi vào bảng dùng chung `audit_logs`.
- **M7.5 (Notifications):** cron M2 (CRON-6) tạo bản ghi `notifications` in-app.
- **Bảng `attachments` polymorphic dùng chung:** lưu CoA, MSDS.
- **M1 (Mẫu) — quan hệ mềm:** giao dịch xuất hóa chất tham chiếu `ref_sample_id` tới `samples.id`. M2 không sở hữu bảng mẫu; chỉ đọc để hiển thị mã mẫu và lọc báo cáo.
- **MinIO:** lưu file CoA/MSDS; M2 lưu `file_key` không lưu binary trong DB.

### 2.2 Chức năng chính

1. Quản lý danh mục hóa chất với đơn vị mặc định tùy loại.
2. Quản lý lô: nhập lô mới (hạn dùng, kiểm tra lại, CoA), xem tồn theo lô.
3. Ghi nhật ký nhập/xuất/điều chỉnh; tự động cập nhật tồn lô và snapshot `balance_after`.
4. Gắn việc xuất hóa chất với mẫu thử nghiệm (`ref_sample_id`).
5. Cảnh báo tồn dưới ngưỡng (P1) và cron nhắc hết hạn / tới hạn kiểm tra lại (P0).
6. Xuất Excel nhật ký và báo cáo tiêu hao.
7. Ghi audit toàn bộ thao tác phục vụ duy trì công nhận VILAS.

### 2.3 Đối tượng người dùng & quyền (RBAC + phạm vi phòng ban)

Trích từ RBAC matrix `01-demo-scope.md` (4 vai trò). Phạm vi dữ liệu: theo phòng ban, trừ Admin & Ban lãnh đạo (toàn hệ thống).

| Actor | Mô tả | Quyền trong M2 |
|-------|-------|----------------|
| **Admin** | Quản trị hệ thống | Toàn quyền mọi thao tác hóa chất (mọi phòng ban). Cấu hình ngưỡng cảnh báo. |
| **Ban lãnh đạo** | Lãnh đạo lab | Xem tồn/lịch sử/báo cáo/giá trị tồn/chi phí tiêu hao toàn hệ thống (👁). Không trực tiếp nhập/xuất (👁 trên hành động nhập/xuất). |
| **Kế toán** | Tài chính | Xem tồn/lịch sử (👁) + **xem giá trị tồn (qty × đơn giá lô) và chi phí tiêu hao** (cột giá trị tiền trong báo cáo tiêu hao + Excel). Không nhập/xuất nghiệp vụ. KHÔNG thấy mẫu/kết quả. |
| **Nhân sự/KTV** | Kỹ thuật viên | Nhập/xuất hóa chất **trong phạm vi phòng ban mình** (✅ phòng); **nhập `unit_price` khi nhập lô** (giá trị tiền là input của giao dịch in nhưng KTV KHÔNG được xem báo cáo giá trị tồn/chi phí tổng hợp). KTV phụ trách được **điều chỉnh kiểm kê** (`adjust`) trong phòng mình (OQ#4). Xem tồn/lịch sử toàn hệ thống ở mức đọc. KHÔNG xem cột giá trị tiền trong báo cáo/Excel (—). |

Quy ước: ✅ = toàn quyền trong phạm vi · 👁 = chỉ xem · — = không truy cập · (phòng) = giới hạn phòng ban của user.

> **Cách ly tài chính (B03 — cập nhật OQ#1 19/06/2026):** KTV **được nhập** `unit_price` khi tạo giao dịch nhập lô (input), nhưng các trường **giá trị tồn / chi phí tiêu hao tổng hợp** (cột tiền trong lịch sử, báo cáo, Excel) chỉ trả về cho Admin / Ban lãnh đạo / Kế toán. API phải lọc field giá trị/chi phí khỏi response đọc cho KTV — không chỉ ẩn ở FE. Xem BR-CHEM-022, BR-CHEM-023.

### 2.4 Ràng buộc (Constraints)

- **CONSTRAINT-1 (Đơn vị & lưu trữ — OQ#2 đã chốt):** mỗi hóa chất có **đơn vị cơ sở** (`base_unit`) + **nhóm đo** (`measurement_group`). Mọi tồn/giao dịch LƯU TRỮ NỘI BỘ theo base unit bằng **NUMERIC(18,6)** (`qty_base`, `balance_after`); giá trị người dùng nhập/hiển thị lưu thêm bằng **NUMERIC(14,4)** (`qty_input` + `input_unit`). KHÔNG dùng float ở bất kỳ tầng nào (tránh sai số tích lũy & mất chính xác khi quy đổi). Đơn vị tùy loại (g, mg, kg, mL, L, viên, ...), KHÔNG hard-code gam.
- **CONSTRAINT-1c (Quy đổi đơn vị — OQ#2 đã chốt):** hệ thống tự quy đổi đơn vị nhập/hiển thị ↔ base unit theo **hệ số cố định** trong danh mục `units` (`code`, `group`, `factor_to_base`). Chỉ quy đổi **trong cùng nhóm đo**; cấm quy đổi chéo nhóm (BR-CHEM-028). Người dùng KHÔNG được sửa hệ số (BR-CHEM-029). Quy đổi 2 chiều phải round-trip không đổi giá trị ở mức NUMERIC(18,6) (NFR-CORRECT-CHEM-002).
- **CONSTRAINT-1b (Tiền — OQ#1 đã chốt):** đơn giá lô lưu **NUMERIC(14,2)** (`unit_price`) kèm `currency` (mặc định `VND`). Giá trị tồn/chi phí KHÔNG dùng float. Phương pháp tính giá trị tồn = **theo từng lô** (qty × `unit_price` của lô), KHÔNG bình quân gia quyền — vì tồn đã được quản lý theo lô (xem BR-CHEM-023).
- **CONSTRAINT-2 (Không cộng gộp khác đơn vị):** tồn chỉ được tổng hợp trong cùng một đơn vị. Khi báo cáo gộp nhiều hóa chất, KHÔNG cộng số lượng khác đơn vị — luôn nhóm theo (hóa chất, đơn vị).
- **CONSTRAINT-3 (Audit VILAS §8.4):** mọi thao tác CRUD hóa chất/lô/giao dịch ghi `audit_logs` (user, action, resource, resource_id, correlation_id, ip, timestamp, detail). Bản ghi audit và giao dịch **bất biến** (immutable) — không cho sửa/xóa giao dịch đã ghi; sai sót sửa bằng giao dịch `adjust`.
- **CONSTRAINT-4 (Stack):** FastAPI, PostgreSQL, Redis (cron lock), MinIO (file), APScheduler (cron). Quy mô ~40 user — monolith, không scale ngang.
- **CONSTRAINT-5 (Thông báo):** chỉ in-app (bảng `notifications`); không email/Zalo (C02).
- **CONSTRAINT-6 (ID):** không lộ ID tuần tự ra ngoài; resource định danh bằng UUID hoặc mã không đoán được (rule api.md).

### 2.5 Giả định (Assumptions) — xem chi tiết §7

- ASSUMPTION-1 → **ĐÃ CHỐT (OQ#2, 19/06/2026):** một hóa chất có **đúng một** `base_unit` + `measurement_group` cố định để lưu trữ nội bộ; người dùng **được** nhập/xuất/xem theo các đơn vị khác **trong cùng nhóm đo**, hệ thống tự quy đổi về base unit để lưu. Không quy đổi chéo nhóm; hệ số quy đổi cố định không sửa được.
- ASSUMPTION-2 → **ĐÃ CHỐT (OQ#4, 19/06/2026):** giao dịch `adjust` (điều chỉnh kiểm kê) bắt buộc có ghi chú lý do (`note` NOT NULL) và do **KTV phụ trách phòng** hoặc **Admin** thực hiện — KHÔNG cần lãnh đạo duyệt.
- ASSUMPTION-3: Cảnh báo tồn dưới ngưỡng đặt ở mức **hóa chất** (`reorder_threshold` theo đơn vị mặc định), không theo từng lô.

---

## 3. Yêu cầu chức năng chi tiết

Mỗi FR có ID dạng `FR-CHEM-NNN`. Business rule dạng `BR-CHEM-NNN` ở §4 dưới. Acceptance Criteria dạng Given–When–Then.

---

### FR-CHEM-001: CRUD danh mục hóa chất

- **Mô tả:** Tạo, xem, sửa, vô hiệu hóa (soft-delete) một hóa chất với các trường: tên, số CAS, nhà sản xuất, **đơn vị cơ sở (`base_unit`) + nhóm đo (`measurement_group`)**, mã nguy hại, phòng ban quản lý, ngưỡng cảnh báo tồn. `base_unit` là đơn vị lưu trữ nội bộ cố định; khuyến nghị chọn đơn vị nhỏ nhất trong nhóm (mg/mL/đơn vị).
- **Độ ưu tiên:** P0
- **Actor:** Admin (mọi phòng), KTV (phòng mình tạo/sửa). Ban lãnh đạo/Kế toán chỉ xem.
- **Tiền điều kiện:** user đã đăng nhập, có quyền `chemical:create`/`chemical:update` trong phạm vi phòng ban.
- **Luồng chính:**
  1. User mở danh mục hóa chất → hệ thống liệt kê hóa chất trong phạm vi (KTV: phòng mình; Admin/Lãnh đạo: tất cả).
  2. User chọn "Thêm hóa chất", nhập: tên (bắt buộc), CAS (tùy chọn, validate định dạng), NSX, **chọn `base_unit` (bắt buộc) từ danh mục `units`** — hệ thống suy ra `measurement_group` từ đơn vị đã chọn (vd chọn "mg" ⇒ group=mass); mã nguy hại, phòng ban (mặc định = phòng của user), `reorder_threshold` (tùy chọn, tính theo `base_unit`).
  3. Hệ thống validate (BR-CHEM-001, BR-CHEM-002) → lưu → ghi `audit_logs` (action=`CHEMICAL_CREATE`).
  4. Trả về hóa chất vừa tạo.
- **Luồng phụ / ngoại lệ:**
  - A1: CAS sai định dạng → 400, không lưu, thông báo "Số CAS không hợp lệ".
  - A2: Trùng (tên + CAS) trong cùng phòng ban → 409 (BR-CHEM-002).
  - A3: Sửa `base_unit` (hoặc `measurement_group`) khi hóa chất **đã có lô/giao dịch** → 422, chặn (BR-CHEM-003).
  - A4: Vô hiệu hóa hóa chất còn lô tồn > 0 → 422, yêu cầu xử lý tồn trước (BR-CHEM-004).
- **Hậu điều kiện:** danh mục cập nhật; audit ghi nhận; không thay đổi tồn.
- **Business Rules:** BR-CHEM-001, BR-CHEM-002, BR-CHEM-003, BR-CHEM-004.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN KTV phòng "Hóa lý" đã đăng nhập WHEN tạo hóa chất "NaCl", CAS "7647-14-5", `base_unit`="mg" THEN hệ thống trả 201, hóa chất gắn `department_id` = phòng Hóa lý, `measurement_group`="mass" (suy ra từ "mg"), và 1 bản ghi `audit_logs` action=`CHEMICAL_CREATE` với `correlation_id` của request.
  - AC2 (edge — CAS): GIVEN form thêm hóa chất WHEN nhập CAS "12-3-4567" (sai checksum/định dạng) THEN trả 400 code `VALIDATION_ERROR`, không tạo bản ghi.
  - AC3 (RBAC): GIVEN KTV phòng "Hóa lý" WHEN cố sửa hóa chất thuộc phòng "Vi sinh" THEN trả 403 code `FORBIDDEN`, không thay đổi dữ liệu.
  - AC4 (lỗi nghiệp vụ — đổi base unit bị khóa): GIVEN hóa chất "NaCl" (`base_unit`="mg") đã có 2 lô WHEN sửa `base_unit` sang "g" THEN trả 422 code `UNIT_LOCKED`, base unit giữ nguyên "mg". (Lưu ý: đổi base unit khác với đổi đơn vị NHẬP/HIỂN THỊ — người dùng vẫn được nhập/xem bằng "g" hay "kg" bình thường, chỉ base unit lưu trữ là cố định.)
  - AC5 (chống chọn base unit lỗi nhóm): GIVEN form thêm hóa chất WHEN chọn một đơn vị không có trong danh mục `units` hoặc không xác định được nhóm đo THEN trả 400 code `INVALID_UNIT`, không tạo bản ghi.
- **Data cần thiết (mức logic):** Chemical { id, name, cas_no, manufacturer, **base_unit (FK→units.code), measurement_group (mass/volume/count)**, hazard_code, department_id, reorder_threshold (theo base_unit, NUMERIC 18,6), status[active/inactive], created_at }. (Đơn vị `default_unit` cũ được thay bằng `base_unit` + `measurement_group` — OQ#2.)
- **API cần (ý định, không phải contract):** "liệt kê hóa chất có phân trang + lọc", "tạo hóa chất", "xem chi tiết hóa chất", "cập nhật hóa chất", "vô hiệu hóa hóa chất".

---

### FR-CHEM-002: Quản lý lô (lot/batch) của hóa chất

- **Mô tả:** Tạo và xem lô cho một hóa chất, gồm: số lô, hạn dùng, ngày kiểm tra lại, ngày nhận, file CoA. Mỗi lô có tồn riêng **lưu trữ theo `base_unit` của hóa chất (NUMERIC 18,6)**; khi hiển thị có thể quy đổi sang đơn vị người dùng chọn trong cùng nhóm.
- **Độ ưu tiên:** P0
- **Actor:** Admin, KTV (phòng mình). Lãnh đạo/Kế toán xem.
- **Tiền điều kiện:** hóa chất tồn tại và đang `active`; user có quyền `chemical_lot:create` trong phạm vi.
- **Luồng chính:**
  1. User chọn hóa chất → "Thêm lô".
  2. Nhập: số lô (bắt buộc), ngày nhận, hạn dùng (`expiry_date`), ngày kiểm tra lại (`recheck_date`), upload CoA (tùy chọn).
  3. Hệ thống validate (BR-CHEM-005, BR-CHEM-006) → tạo lô với tồn ban đầu = 0.
  4. **Lưu ý:** việc tạo lô KHÔNG tự cộng tồn. Tồn ban đầu được nạp bằng một giao dịch `in` (FR-CHEM-005) — có thể thực hiện ngay trong cùng thao tác (tạo lô + giao dịch nhập đầu tiên) như một transaction nguyên tử.
  5. Ghi `audit_logs` action=`CHEMICAL_LOT_CREATE`.
- **Luồng phụ / ngoại lệ:**
  - A1: `expiry_date` < ngày hiện tại → cho phép tạo nhưng cảnh báo (WARN) "Lô đã hết hạn" và đánh dấu `is_expired`.
  - A2: `recheck_date` > `expiry_date` → 422 (BR-CHEM-006).
  - A3: Trùng `lot_no` trong cùng hóa chất → 409 (BR-CHEM-005).
  - A4: Upload CoA lỗi (MinIO down / file quá lớn) → 422; lô vẫn tạo được, CoA gắn sau (đính kèm không chặn nghiệp vụ).
- **Hậu điều kiện:** lô được tạo với tồn = 0 (hoặc = số nhập đầu nếu gộp giao dịch `in`); CoA lưu trong MinIO + `attachments`.
- **Business Rules:** BR-CHEM-005, BR-CHEM-006.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN hóa chất "NaCl" (`base_unit`="mg") WHEN tạo lô "L2026-001", expiry 31/12/2027, recheck 31/12/2026 THEN trả 201, lô có `qty_base` = 0.000000 mg và `audit_logs` action=`CHEMICAL_LOT_CREATE`.
  - AC2 (edge — hết hạn): GIVEN ngày hiện tại 19/06/2026 WHEN tạo lô expiry 01/01/2026 THEN trả 201 kèm cờ `is_expired=true` và một WARN log "Lô đã hết hạn".
  - AC3 (lỗi nghiệp vụ): GIVEN tạo lô WHEN recheck 01/01/2028 và expiry 31/12/2027 THEN trả 422 code `INVALID_DATE_ORDER`.
  - AC4 (trùng): GIVEN lô "L2026-001" của NaCl đã tồn tại WHEN tạo lô "L2026-001" cho NaCl THEN trả 409 code `DUPLICATE_LOT`.
- **Data cần thiết:** ChemicalLot { id, chemical_id, lot_no, **qty_base(NUMERIC 18,6, = tồn hiện tại theo base unit của hóa chất)**, **unit_price(NUMERIC 14,2, ≥ 0)**, **price_unit (đơn vị NHẬP làm cơ sở đơn giá — xem BR-CHEM-023/030)**, **currency(mặc định 'VND')**, **recheck_result(pass/fail/null)**, received_at, expiry_date, recheck_date, coa_file_key, is_expired, created_at }. (Tồn lưu theo base unit — OQ#2. Đơn giá `unit_price` gắn với `price_unit` = đơn vị nhập của lô — OQ#1.)
- **API cần:** "tạo lô cho hóa chất", "liệt kê lô theo hóa chất (kèm tồn)", "xem chi tiết lô", "tải CoA của lô".

---

### FR-CHEM-003: Đính kèm thông tin an toàn (MSDS) & mã nguy hại

- **Mô tả:** Lưu mã nguy hại ở cấp hóa chất và đính kèm file MSDS/SDS cho hóa chất.
- **Độ ưu tiên:** P1
- **Actor:** Admin, KTV (phòng mình). Tất cả vai trò có quyền xem M2 được xem/tải MSDS.
- **Tiền điều kiện:** hóa chất tồn tại.
- **Luồng chính:**
  1. User mở chi tiết hóa chất → "Đính kèm MSDS" → upload PDF/ảnh.
  2. Hệ thống validate loại + dung lượng file (BR-CHEM-013) → lưu MinIO → ghi `attachments` (owner_type=`chemical`).
  3. Ghi `audit_logs` action=`CHEMICAL_MSDS_UPLOAD`.
- **Luồng phụ / ngoại lệ:**
  - A1: File không thuộc loại cho phép → 422 code `INVALID_FILE_TYPE`.
  - A2: File > giới hạn → 422 code `FILE_TOO_LARGE`.
- **Hậu điều kiện:** MSDS truy xuất được; mã nguy hại hiển thị trên chi tiết hóa chất và cảnh báo khi xuất (gợi ý an toàn).
- **Business Rules:** BR-CHEM-013.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN hóa chất "H2SO4" mã nguy hại "H314" WHEN upload "msds-h2so4.pdf" (2 MB) THEN trả 201, file lấy lại được qua link tải, audit ghi `CHEMICAL_MSDS_UPLOAD`.
  - AC2 (edge): GIVEN file "msds.exe" WHEN upload THEN trả 422 code `INVALID_FILE_TYPE`.
  - AC3 (xem): GIVEN KTV bất kỳ phòng WHEN mở chi tiết "H2SO4" THEN thấy mã nguy hại "H314" và nút tải MSDS.
- **Data cần thiết:** Chemical.hazard_code; Attachment { owner_type=`chemical`, owner_id, file_key, file_name, mime, size, uploaded_by, uploaded_at }.
- **API cần:** "upload MSDS cho hóa chất", "liệt kê file đính kèm của hóa chất", "tải file đính kèm".

---

### FR-CHEM-004: Tìm kiếm & lọc danh mục hóa chất / lô

- **Mô tả:** Tìm và lọc hóa chất theo tên/CAS, lọc lô theo trạng thái (còn tồn, sắp hết hạn, đã hết hạn, tới hạn kiểm tra lại), lọc theo phòng ban.
- **Độ ưu tiên:** P1
- **Actor:** mọi vai trò có quyền xem M2 (trong phạm vi).
- **Tiền điều kiện:** đã đăng nhập.
- **Luồng chính:**
  1. User nhập từ khóa / chọn bộ lọc.
  2. Hệ thống trả danh sách có phân trang (default 20, max 100 — rule api.md), kèm tồn hiện tại từng lô (đúng đơn vị).
- **Luồng phụ / ngoại lệ:**
  - A1: không có kết quả → trả mảng rỗng + `total=0` (không lỗi).
- **Hậu điều kiện:** không thay đổi dữ liệu.
- **Business Rules:** BR-CHEM-018 (phạm vi đọc).
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN 200 hóa chất WHEN lọc "expiring trong 30 ngày" THEN trả đúng các lô có `expiry_date` ≤ hôm nay+30, phân trang 20/trang, meta có `total`.
  - AC2 (RBAC scope): GIVEN KTV phòng "Hóa lý" WHEN xem danh sách hóa chất THEN có thể đọc cả phòng khác (quyền xem tồn/lịch sử toàn hệ thống theo RBAC), nhưng chỉ phòng mình mới hiện nút sửa/xuất.
- **Data cần thiết:** query params (q, department_id, status, expiry_within_days, recheck_due, page, limit).
- **API cần:** "tìm kiếm hóa chất có lọc + phân trang", "liệt kê lô theo bộ lọc trạng thái".

---

### FR-CHEM-005: Ghi nhật ký NHẬP hóa chất (transaction type=in)

- **Mô tả:** Ghi một giao dịch nhập làm tăng tồn của một lô. Người dùng nhập số lượng theo **đơn vị tùy chọn trong cùng nhóm đo** của hóa chất (`input_unit`); hệ thống quy đổi về `base_unit` để cộng tồn và lưu `qty_base` + `balance_after` (theo base unit), đồng thời lưu `qty_input` + `input_unit` để audit/hiển thị.
- **Độ ưu tiên:** P0
- **Actor:** Admin (mọi phòng), KTV (phòng mình). Lãnh đạo/Kế toán chỉ xem.
- **Tiền điều kiện:** lô tồn tại; user có quyền `chemical_txn:create` trong phạm vi phòng ban của hóa chất.
- **Luồng chính:**
  1. User chọn lô → "Nhập", nhập số lượng (`qty_input` NUMERIC(14,4), > 0) + **chọn `input_unit`** (mặc định = `base_unit`, chỉ liệt kê đơn vị cùng nhóm đo), **đơn giá `unit_price` (NUMERIC(14,2), ≥ 0) theo `input_unit`** và `currency` (mặc định VND), ngày, ghi chú (tùy chọn).
  2. Hệ thống validate `input_unit` cùng nhóm với `base_unit` (BR-CHEM-028) → quy đổi `qty_base = qty_input × factor_to_base(input_unit) / factor_to_base(base_unit)` (NUMERIC 18,6).
  3. Mở **transaction DB**: lock lô (row lock) → đọc tồn hiện tại (`qty_base`) → tính `balance_after = qty_base_lô + qty_base_nhập` (base unit) → ghi `chemical_transactions` (type=in, lưu CẢ qty_base/base_unit lẫn qty_input/input_unit) → cập nhật `chemical_lots.qty_base = balance_after` → commit.
  4. Ghi `audit_logs` action=`CHEMICAL_TXN_IN`.
  5. Trả về giao dịch kèm tồn mới (hiển thị theo `input_unit` hoặc base unit tùy lựa chọn xem).
- **Luồng phụ / ngoại lệ:**
  - A1: qty_input ≤ 0 → 400 (BR-CHEM-007).
  - A2: qty_input không phải số / quá 4 chữ số thập phân → 400 (BR-CHEM-008).
  - A2b: `input_unit` khác nhóm đo với `base_unit` của hóa chất → 422 code `UNIT_GROUP_MISMATCH`, không lưu (BR-CHEM-028).
  - A3: lô đã hết hạn → cho nhập nhưng cảnh báo WARN (KH có thể nhập lô về kho để xử lý/hủy).
  - A4: transaction DB fail → rollback toàn bộ, không thay đổi tồn, ghi ERROR log với correlationId; trả 500 thông điệp chung.
- **Hậu điều kiện:** tồn lô tăng đúng; có đúng 1 bản ghi giao dịch immutable với `balance_after`.
- **Business Rules:** BR-CHEM-007, BR-CHEM-008, BR-CHEM-011, BR-CHEM-012.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN lô "L2026-001" NaCl (`base_unit`="mg") tồn 0 WHEN nhập `qty_input`=0.5000 với `input_unit`="kg" THEN `qty_base`=500000.000000 mg; tồn lô `qty_base`=500000.000000, giao dịch type=in lưu (qty_base=500000.000000, base_unit=mg) và (qty_input=0.5000, input_unit=kg), `balance_after`=500000.000000, audit `CHEMICAL_TXN_IN`.
  - AC1b (quy đổi g→base mg): GIVEN cùng lô tồn 0 WHEN nhập 500.0000 g THEN `qty_base`=500000.000000 mg; hiển thị lại theo g = 500.0000 g (round-trip không đổi).
  - AC2 (edge — thập phân & quy đổi nhỏ): GIVEN lô tồn 10000.000000 mg (=10 g) WHEN nhập 0.0005 g THEN `qty_base` cộng thêm 0.500000 mg → tồn = 10000.500000 mg (giữ đúng ở NUMERIC(18,6), không sai số float).
  - AC2c (lỗi nhóm đo): GIVEN hóa chất NaCl nhóm mass WHEN nhập `input_unit`="mL" THEN trả 422 code `UNIT_GROUP_MISMATCH`, tồn không đổi.
  - AC2b (giá trị tồn theo đơn vị nhập): GIVEN nhập lô với `unit_price`=1200.00 VND/g (`price_unit`="g") WHEN nhập 500.0000 g THEN giá trị tồn lô = qty_còn_lại (quy về đơn vị nhập "g") × 1200.00 = 500.0000 × 1200.00 = 600000.00 VND; Kế toán xem chi tiết lô THẤY 600000.00 VND, KTV KHÔNG thấy trường giá trị tồn tổng hợp (BR-CHEM-022, BR-CHEM-023, BR-CHEM-030).
  - AC3 (lỗi input): GIVEN form nhập WHEN qty_input = -5 hoặc 0 THEN trả 400 code `INVALID_QUANTITY`, tồn không đổi.
  - AC4 (RBAC): GIVEN KTV phòng "Vi sinh" WHEN nhập cho lô thuộc phòng "Hóa lý" THEN trả 403, tồn không đổi.
  - AC5 (atomic): GIVEN lỗi DB xảy ra giữa ghi giao dịch và cập nhật lô WHEN nhập THEN cả hai bị rollback — tồn lô không thay đổi và không có giao dịch nào được lưu.
- **Data cần thiết:** ChemicalTransaction { id, lot_id, type=in, **qty_base(NUMERIC 18,6), base_unit**, **qty_input(NUMERIC 14,4), input_unit**, **balance_after(NUMERIC 18,6, theo base unit)**, **unit_price(NUMERIC 14,2, ≥ 0, theo `input_unit`)**, **currency(mặc định VND)**, ref_sample_id=NULL, by_user, at, note, correlation_id }. Lưu ý: `unit_price`+`currency`+`price_unit` cũng lưu ở cấp lô (`chemical_lots`) để tính giá trị tồn — schema-designer quyết đặt ở lô và/hoặc giao dịch in.
- **API cần:** "ghi giao dịch nhập cho lô kèm đơn giá" (atomic).
- **Business Rules bổ sung:** BR-CHEM-023 (giá trị tồn theo lô), BR-CHEM-022 (cách ly trường giá trị/chi phí khỏi KTV).

---

### FR-CHEM-006: Ghi nhật ký XUẤT / sử dụng hóa chất gắn mẫu (transaction type=out)

- **Mô tả:** Ghi một giao dịch xuất làm **giảm** tồn của một lô, **bắt buộc gắn với mẫu thử nghiệm** (`ref_sample_id` NOT NULL — OQ#3 đã chốt). Không cho xuất quá tồn lô. Khi xuất từ lô kiểm tra lại "không đạt" hoặc đã quá hạn → cảnh báo + yêu cầu xác nhận mới cho xuất (OQ#5 đã chốt, không khóa cứng). Lưu `balance_after`.
- **Độ ưu tiên:** P0
- **Actor:** Admin (mọi phòng), KTV (phòng mình). Lãnh đạo/Kế toán chỉ xem.
- **Tiền điều kiện:** lô tồn tại có tồn > 0; user có quyền `chemical_txn:create` trong phạm vi; **mẫu (`ref_sample_id`) phải được cung cấp và tồn tại** (bắt buộc — OQ#3).
- **Luồng chính:**
  1. User chọn hóa chất → hệ thống **gợi ý lô theo FEFO** (lô còn tồn, hết hạn sớm nhất, chưa hết hạn lên đầu) (BR-CHEM-010).
  2. User chọn lô, nhập số lượng xuất (`qty_input` > 0) + **chọn `input_unit`** (mặc định = `base_unit`, chỉ liệt kê đơn vị cùng nhóm đo), **chọn mẫu liên quan (`ref_sample_id` — bắt buộc)**, ghi chú. Hệ thống quy đổi `qty_base = qty_input` về base unit để so tồn và trừ.
  3. Nếu lô có trạng thái kiểm tra lại "không đạt" HOẶC đã quá hạn dùng → hệ thống hiển thị **cảnh báo** và **yêu cầu người dùng xác nhận** (confirm) + khuyến nghị nhập lý do; chỉ khi xác nhận mới tiếp tục, đặt cờ `warning_override=true` cho giao dịch (BR-CHEM-020, BR-CHEM-024).
  4. Hệ thống validate `input_unit` cùng nhóm với `base_unit` (BR-CHEM-028) → quy đổi `qty_base_xuất`. Mở transaction DB: lock lô → kiểm tra `ref_sample_id` NOT NULL & tồn tại (BR-CHEM-025) → kiểm tra `qty_base_xuất ≤ qty_base_lô` (BR-CHEM-009, so sánh theo base unit) → tính `balance_after = qty_base_lô − qty_base_xuất` → ghi giao dịch (type=out, lưu CẢ qty_base/base_unit lẫn qty_input/input_unit, ref_sample_id, warning_override, lý do nếu có) → cập nhật tồn lô → commit.
  5. Ghi `audit_logs` action=`CHEMICAL_TXN_OUT` (detail kèm `ref_sample_id`; nếu là xuất lô cảnh báo thì kèm `warning_override=true` + lý do).
- **Luồng phụ / ngoại lệ:**
  - A1: `qty_base_xuất > qty_base_lô` (so theo base unit) → 422 code `INSUFFICIENT_STOCK`, không xuất (BR-CHEM-009).
  - A1b: `input_unit` khác nhóm đo với `base_unit` → 422 code `UNIT_GROUP_MISMATCH`, không xuất (BR-CHEM-028).
  - A2: lô đã quá hạn dùng HOẶC kiểm tra lại "không đạt" → KHÔNG chặn cứng: trả về cảnh báo (vd 200/giai đoạn preview với cờ `requires_confirmation=true` hoặc 422 code `WARNING_NEEDS_CONFIRM` nếu request chưa kèm xác nhận) → người dùng gửi lại request với `confirm_warning=true` (+ lý do khuyến nghị) → cho xuất, ghi cờ `warning_override=true` vào giao dịch & audit (BR-CHEM-020, BR-CHEM-024).
  - A3: `ref_sample_id` không được cung cấp → 422 code `SAMPLE_REQUIRED`; không tồn tại → 422 code `SAMPLE_NOT_FOUND` (BR-CHEM-025).
  - A4: hóa chất có mã nguy hại → hiển thị cảnh báo an toàn (không chặn).
  - A5: 2 giao dịch xuất đồng thời cùng lô → row lock đảm bảo tuần tự, không cho âm tồn (BR-CHEM-014).
- **Hậu điều kiện:** tồn lô giảm đúng; 1 giao dịch immutable với `balance_after`, `ref_sample_id` (NOT NULL) và `warning_override` (true nếu xuất lô không đạt/quá hạn); tồn không bao giờ âm.
- **Business Rules:** BR-CHEM-007, BR-CHEM-008, BR-CHEM-009, BR-CHEM-010, BR-CHEM-011, BR-CHEM-012, BR-CHEM-014, BR-CHEM-015, BR-CHEM-020, BR-CHEM-024, BR-CHEM-025.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN lô NaCl (`base_unit`="mg") tồn `qty_base`=500000.000000 mg, mẫu "SP-2026-0007" tồn tại WHEN xuất `qty_input`=12.5000 g (input_unit=g) gắn mẫu đó THEN `qty_base_xuất`=12500.000000 mg, tồn lô = 487500.000000 mg, giao dịch type=out lưu (qty_base=12500.000000, base_unit=mg) + (qty_input=12.5000, input_unit=g), `balance_after`=487500.000000, `ref_sample_id`→SP-2026-0007, audit `CHEMICAL_TXN_OUT`.
  - AC2 (edge — vượt tồn quy đổi): GIVEN lô tồn 10000.000000 mg (=10 g) WHEN xuất 10.0001 g (=10000.100000 mg) THEN trả 422 code `INSUFFICIENT_STOCK`, tồn vẫn 10000.000000 mg.
  - AC2b (lỗi nhóm đo): GIVEN lô NaCl nhóm mass WHEN xuất với `input_unit`="mL" THEN trả 422 code `UNIT_GROUP_MISMATCH`, tồn không đổi.
  - AC3 (FEFO gợi ý): GIVEN NaCl có lô A (expiry 31/12/2026, tồn 100) và lô B (expiry 31/12/2027, tồn 100) WHEN mở màn hình xuất THEN lô A được gợi ý lên đầu (hết hạn trước).
  - AC4 (RBAC + tài chính): GIVEN KTV phòng mình xuất hóa chất THEN response giao dịch KHÔNG chứa trường giá trị tiền; cùng dữ liệu khi Kế toán xem lịch sử THÌ có trường chi phí.
  - AC5 (concurrency): GIVEN lô tồn 10000.000000 mg (=10 g) WHEN 2 request xuất 6.0000 g (=6000.000000 mg) gửi gần đồng thời THEN chỉ 1 thành công (tồn=4000.000000 mg), request còn lại trả 422 `INSUFFICIENT_STOCK` — tồn không bao giờ âm.
  - AC6 (mẫu không tồn tại): GIVEN ref_sample_id = mã không có thật WHEN xuất THEN trả 422 `SAMPLE_NOT_FOUND`, tồn không đổi.
  - AC7 (mẫu bắt buộc — OQ#3): GIVEN form xuất KHÔNG chọn mẫu WHEN gửi xuất THEN trả 422 code `SAMPLE_REQUIRED`, không tạo giao dịch, tồn không đổi.
  - AC8 (lô không đạt — cảnh báo + xác nhận, OQ#5): GIVEN lô có kết quả kiểm tra lại "không đạt" tồn 100.0000 g WHEN gửi xuất 5.0000 g KHÔNG kèm xác nhận THEN trả 422 code `WARNING_NEEDS_CONFIRM` (không trừ tồn); WHEN gửi lại với `confirm_warning=true` + lý do THEN xuất thành công, giao dịch có `warning_override=true`, audit ghi cờ + lý do.
  - AC9 (lô quá hạn — cảnh báo + xác nhận): GIVEN lô đã quá `expiry_date` WHEN xuất kèm `confirm_warning=true` THEN cho xuất, `warning_override=true` được ghi vào giao dịch và audit.
- **Data cần thiết:** ChemicalTransaction { ..., type=out, **qty_base(18,6), base_unit, qty_input(14,4), input_unit, balance_after(18,6 theo base unit)**, **ref_sample_id(FK→samples, NOT NULL — OQ#3 đã chốt)**, **warning_override(boolean, default false)**, note(lý do — khuyến nghị bắt buộc khi `warning_override=true`), ... }.
- **API cần:** "gợi ý lô FEFO cho hóa chất", "ghi giao dịch xuất gắn mẫu (bắt buộc), hỗ trợ xác nhận xuất lô cảnh báo" (atomic, có lock).

---

### FR-CHEM-007: Điều chỉnh tồn (transaction type=adjust) — kiểm kê

- **Mô tả:** Điều chỉnh tồn lô khi kiểm kê thực tế lệch sổ sách. Không sửa giao dịch cũ; sai lệch ghi bằng một giao dịch `adjust` có lý do bắt buộc.
- **Độ ưu tiên:** P1
- **Actor:** **KTV phụ trách hóa chất của phòng** (trong phạm vi phòng mình) + **Admin** (mọi phòng) — OQ#4 đã chốt; KHÔNG cần lãnh đạo duyệt.
- **Tiền điều kiện:** lô tồn tại; user có quyền `chemical_txn:adjust` trong phạm vi phòng ban của hóa chất.
- **Luồng chính:**
  1. User chọn lô → "Điều chỉnh kiểm kê", nhập **tồn thực tế** hoặc **lượng chênh lệch** (± delta) + **lý do bắt buộc** (`note` NOT NULL).
  2. Hệ thống tính delta = tồn_thực_tế − tồn_sổ; ghi giao dịch type=adjust (qty=delta có dấu), `balance_after = tồn_thực_tế`; cập nhật lô.
  3. Ghi `audit_logs` action=`CHEMICAL_TXN_ADJUST` (detail kèm lý do).
- **Luồng phụ / ngoại lệ:**
  - A1: thiếu lý do → 400 code `REASON_REQUIRED` (BR-CHEM-016).
  - A2: tồn thực tế < 0 → 400 (BR-CHEM-009 — tồn không âm).
- **Hậu điều kiện:** tồn lô = tồn thực tế; giao dịch điều chỉnh truy vết được.
- **Business Rules:** BR-CHEM-009, BR-CHEM-015, BR-CHEM-016.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN lô tồn sổ 100.0000 g, thực tế 98.5000 g, lý do "hao hụt bay hơi" WHEN điều chỉnh THEN giao dịch adjust qty=-1.5000, `balance_after=98.5000`, audit kèm lý do.
  - AC2 (lỗi input — lý do bắt buộc): GIVEN điều chỉnh KHÔNG nhập lý do THEN trả 400 `REASON_REQUIRED`, tồn không đổi (`note` NOT NULL với type=adjust).
  - AC3 (RBAC — OQ#4): GIVEN KTV KHÔNG phụ trách hóa chất của phòng (không có quyền `chemical_txn:adjust`) WHEN gọi điều chỉnh THEN trả 403. GIVEN KTV phụ trách phòng mình WHEN điều chỉnh lô của phòng mình THEN thành công (không cần lãnh đạo duyệt). GIVEN KTV phụ trách WHEN điều chỉnh lô phòng khác THEN trả 403.
  - AC4 (audit đầy đủ): GIVEN điều chỉnh thành công WHEN kiểm tra audit THEN có `CHEMICAL_TXN_ADJUST` với user, lô, delta, lý do, correlation_id.
- **Data cần thiết:** ChemicalTransaction { type=adjust, qty(±), balance_after, **note(lý do — NOT NULL với type=adjust)** }.
- **API cần:** "điều chỉnh tồn lô có lý do bắt buộc" (atomic).

---

### FR-CHEM-008: Hiển thị tồn hiện tại theo lô (đúng đơn vị)

- **Mô tả:** Hiển thị tồn hiện tại của từng lô và tổng tồn theo hóa chất. Tồn lưu trữ theo `base_unit`; **người dùng được chọn đơn vị xem (display unit) trong cùng nhóm đo** — hệ thống quy đổi từ base unit để hiển thị. KHÔNG cộng gộp khác nhóm đo.
- **Độ ưu tiên:** P0
- **Actor:** mọi vai trò có quyền xem M2.
- **Tiền điều kiện:** đã đăng nhập.
- **Luồng chính:**
  1. User mở chi tiết hóa chất → hệ thống đọc tồn từng lô = `chemical_lots.qty_base` (đọc trực tiếp theo base unit, đã maintain bởi giao dịch — KHÔNG SUM runtime cho hiệu năng), rồi **quy đổi sang đơn vị xem (display unit) người dùng chọn** (mặc định base unit).
  2. Tổng tồn hóa chất = tổng `qty_base` các lô (cùng base unit) → hợp lệ; có thể quy đổi tổng sang display unit để hiển thị.
- **Luồng phụ / ngoại lệ:**
  - A1: Đối soát (reconcile) — báo cáo so `chemical_lots.qty_base` với `balance_after` (base unit) của giao dịch cuối cùng của lô; lệch → cảnh báo audit (BR-CHEM-015).
- **Hậu điều kiện:** chỉ đọc.
- **Business Rules:** BR-CHEM-015, BR-CHEM-017 (không cộng gộp khác đơn vị).
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN NaCl (`base_unit`="mg") có lô A `qty_base`=487500.000000 mg, lô B `qty_base`=200000.000000 mg WHEN xem tồn với display unit="g" THEN từng lô hiện 487.5000 g / 200.0000 g, tổng = 687.5000 g.
  - AC1b (đổi đơn vị xem — round-trip): GIVEN tổng tồn NaCl = 687500.000000 mg WHEN đổi display unit sang "kg" THEN hiển thị 0.6875 kg; đổi lại "mg" hiển thị 687500.000000 mg (không đổi giá trị).
  - AC2 (không cộng khác nhóm đo): GIVEN báo cáo gộp gồm NaCl (mass) và Ethanol (volume) WHEN hiển thị tổng THEN hệ thống nhóm riêng theo nhóm đo, KHÔNG hiện một con số "tổng" gộp mass + volume; chọn display unit chỉ áp dụng trong cùng nhóm.
  - AC3 (reconcile): GIVEN `chemical_lots.qty_base` của lô A = 487500.000000 mg nhưng `balance_after` giao dịch cuối = 480000.000000 mg WHEN chạy đối soát THEN báo cáo đánh dấu lô A "lệch tồn" và ghi audit cảnh báo.
- **Data cần thiết:** đọc `chemical_lots.qty_base` + `chemicals.base_unit`/`measurement_group` + bảng `units` (factor để quy đổi sang display unit) (+ `unit_price`, `price_unit`, `currency` để tính giá trị tồn lô = qty_còn_lại quy về `price_unit` × unit_price — chỉ trả cho vai trò tài chính, BR-CHEM-022/023/030).
- **API cần:** "lấy tồn hiện tại theo lô (kèm giá trị tồn cho vai trò tài chính)", "đối soát tồn lô vs giao dịch".

---

### FR-CHEM-009: Lịch sử giao dịch đầy đủ (audit trail)

- **Mô tả:** Xem lịch sử mọi giao dịch (in/out/adjust) của một lô / một hóa chất / theo mẫu, với `balance_after`, người thực hiện, thời điểm, `ref_sample_id`, `correlation_id`.
- **Độ ưu tiên:** P0
- **Actor:** mọi vai trò có quyền xem M2. Kế toán thấy thêm cột chi phí (nếu có).
- **Tiền điều kiện:** đã đăng nhập.
- **Luồng chính:**
  1. User mở "Lịch sử giao dịch" của lô/hóa chất → hệ thống trả danh sách giao dịch theo thời gian giảm dần, phân trang.
  2. Mỗi dòng: type, qty (có dấu cho adjust), `balance_after`, người, thời điểm, mẫu liên quan (mã mẫu), ghi chú.
- **Luồng phụ / ngoại lệ:**
  - A1: lọc theo khoảng ngày / theo mẫu / theo người dùng / theo type.
- **Hậu điều kiện:** chỉ đọc; giao dịch bất biến — không có thao tác sửa/xóa.
- **Business Rules:** BR-CHEM-015 (immutable), BR-CHEM-018 (phạm vi đọc).
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN lô đã có 3 giao dịch WHEN xem lịch sử THEN trả 3 dòng đúng thứ tự thời gian giảm dần, mỗi dòng có `balance_after` khớp chuỗi.
  - AC2 (immutable): GIVEN một giao dịch đã ghi WHEN thử gọi API sửa/xóa giao dịch THEN không có endpoint cho phép (404/405) — sửa sai chỉ qua `adjust`.
  - AC3 (lọc theo mẫu): GIVEN mẫu "SP-2026-0007" đã dùng 2 hóa chất WHEN lọc lịch sử theo mẫu đó THEN trả đúng 2 giao dịch out có `ref_sample_id` = mẫu đó.
  - AC4 (tài chính): GIVEN KTV xem lịch sử THEN không có cột chi phí; Kế toán xem cùng lịch sử THÌ có cột chi phí.
- **Data cần thiết:** đọc `chemical_transactions` join `samples` (mã mẫu), `users` (người).
- **API cần:** "liệt kê giao dịch có lọc (lô/hóa chất/mẫu/người/ngày/type) + phân trang".

---

### FR-CHEM-010: Cảnh báo tồn dưới ngưỡng

- **Mô tả:** Khi tổng tồn của một hóa chất (cùng đơn vị) xuống dưới `reorder_threshold`, hệ thống tạo cảnh báo in-app cho người phụ trách hóa chất của phòng ban.
- **Độ ưu tiên:** P1
- **Actor:** hệ thống (sau giao dịch out/adjust) + người nhận: KTV phụ trách phòng, Admin.
- **Tiền điều kiện:** hóa chất có `reorder_threshold > 0`.
- **Luồng chính:**
  1. Sau mỗi giao dịch out/adjust, hệ thống tính tổng tồn hóa chất.
  2. Nếu tổng tồn < `reorder_threshold` và chưa có cảnh báo "đang mở" cho hóa chất này → tạo `notifications` (in-app) (BR-CHEM-019 — chống spam).
- **Luồng phụ / ngoại lệ:**
  - A1: tồn trở lại ≥ ngưỡng (sau giao dịch nhập) → cảnh báo cũ tự đóng/đánh dấu đã giải quyết.
- **Hậu điều kiện:** notification được tạo; không trùng lặp.
- **Business Rules:** BR-CHEM-019.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN NaCl ngưỡng 50.0000 g, tồn 55.0000 g WHEN xuất 10.0000 g (tồn còn 45) THEN tạo đúng 1 notification "Tồn dưới ngưỡng" cho KTV phụ trách.
  - AC2 (chống spam): GIVEN đã có cảnh báo mở cho NaCl WHEN xuất tiếp 5 g THEN KHÔNG tạo notification thứ 2.
  - AC3 (tự đóng): GIVEN cảnh báo đang mở WHEN nhập 100 g (tồn vượt ngưỡng) THEN cảnh báo được đánh dấu đã giải quyết.
- **Data cần thiết:** Chemical.reorder_threshold; Notification { user_id, type=`CHEM_LOW_STOCK`, ref_type=`chemical`, ref_id }.
- **API cần:** "tính & phát cảnh báo tồn thấp" (nội bộ sau giao dịch).

---

### FR-CHEM-011: Quản lý lịch kiểm tra lại hóa chất

- **Mô tả:** Lưu và cập nhật `recheck_date` của lô; ghi nhận kết quả mỗi lần kiểm tra lại (đạt/không đạt) và đính kèm bằng chứng; cập nhật `recheck_date` kỳ tiếp theo.
- **Độ ưu tiên:** P0
- **Actor:** Admin, KTV (phòng mình).
- **Tiền điều kiện:** lô tồn tại.
- **Luồng chính:**
  1. KTV mở lô tới hạn kiểm tra → ghi kết quả kiểm tra lại (đạt/không đạt), ngày kiểm tra, ghi chú, đính kèm (tùy chọn).
  2. Hệ thống cập nhật `recheck_date` mới (theo chu kỳ KH nhập) + ghi `audit_logs` action=`CHEMICAL_RECHECK`.
  3. Nếu "không đạt" → đánh dấu trạng thái kiểm tra lại của lô = "không đạt". **Lô KHÔNG bị khóa cứng** (OQ#5 đã chốt): vẫn cho xuất nhưng mọi lần xuất sau sẽ phải cảnh báo + xác nhận (FR-CHEM-006 A2/A8).
- **Luồng phụ / ngoại lệ:**
  - A1: kết quả "không đạt" → đánh dấu lô `recheck_result=fail`; giao dịch out trên lô KHÔNG bị chặn mà bị **cảnh báo + yêu cầu xác nhận** (BR-CHEM-020, BR-CHEM-024). Khuyến nghị ghi lý do khi xuất để truy vết 17025.
- **Hậu điều kiện:** lịch sử kiểm tra lại lưu lại; `recheck_date` cập nhật.
- **Business Rules:** BR-CHEM-012, BR-CHEM-020, BR-CHEM-024.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN lô tới hạn kiểm tra WHEN ghi kết quả "đạt", recheck kỳ sau 31/12/2026 THEN `recheck_date` cập nhật, `recheck_result=pass`, audit `CHEMICAL_RECHECK`.
  - AC2 (không đạt — cảnh báo, KHÔNG khóa, OQ#5): GIVEN ghi kết quả "không đạt" cho lô WHEN sau đó xuất từ lô đó KHÔNG kèm xác nhận THEN trả 422 code `WARNING_NEEDS_CONFIRM`; WHEN xuất lại với `confirm_warning=true` THEN cho xuất, giao dịch ghi `warning_override=true` + audit.
- **Data cần thiết:** ChemicalLot.recheck_date; bản ghi RecheckRecord { lot_id, checked_at, result, note, by_user } (logic — schema-designer quyết bảng).
- **API cần:** "ghi kết quả kiểm tra lại lô", "cập nhật recheck_date".

---

### FR-CHEM-012: Cron nhắc hết hạn / tới hạn kiểm tra lại (in-app) — CRON-6

- **Mô tả:** Tác vụ định kỳ hằng ngày 07:00 quét các lô có `expiry_date` hoặc `recheck_date` tới hạn (mốc 30/15/7 ngày) và tạo thông báo in-app cho người phụ trách hóa chất của phòng ban.
- **Độ ưu tiên:** P0
- **Actor:** hệ thống (APScheduler) → người nhận: KTV phụ trách phòng + Admin.
- **Tiền điều kiện:** có lô với `expiry_date`/`recheck_date`; APScheduler chạy; Redis lock khả dụng.
- **Luồng chính:**
  1. 07:00 hằng ngày, APScheduler acquire Redis lock (tránh chạy trùng nếu nhiều instance).
  2. Quét lô còn tồn > 0 có `expiry_date` còn 30/15/7 ngày HOẶC `recheck_date` còn 30/15/7 ngày.
  3. Với mỗi lô tới mốc → tạo `notifications` (type=`CHEM_EXPIRY`/`CHEM_RECHECK_DUE`) cho người phụ trách; chống trùng (mỗi lô × mỗi mốc tạo 1 lần) (BR-CHEM-021).
  4. Ghi log INFO số notification đã tạo; release lock.
- **Luồng phụ / ngoại lệ:**
  - A1: Redis lock đã bị giữ → instance khác bỏ qua lần chạy (không chạy trùng).
  - A2: lỗi giữa chừng → log ERROR với correlationId; lần chạy sau retry (idempotent nhờ chống trùng).
- **Hậu điều kiện:** thông báo in-app được tạo đúng mốc, không trùng.
- **Business Rules:** BR-CHEM-021.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN lô có `expiry_date` = hôm nay + 15 ngày, tồn > 0 WHEN cron 07:00 chạy THEN tạo đúng 1 notification `CHEM_EXPIRY` mốc-15-ngày cho KTV phụ trách.
  - AC2 (chống trùng): GIVEN cron đã tạo notification mốc-15-ngày cho lô X hôm nay WHEN cron chạy lại (thủ công) cùng ngày THEN KHÔNG tạo notification thứ 2 cho cùng lô × cùng mốc.
  - AC3 (lock): GIVEN 2 tiến trình cron khởi động đồng thời WHEN cùng 07:00 THEN chỉ 1 tiến trình thực thi (Redis lock), tiến trình kia bỏ qua.
  - AC4 (lô hết tồn): GIVEN lô tới hạn nhưng tồn = 0 WHEN cron chạy THEN KHÔNG tạo notification (lô đã dùng hết, không cần nhắc).
- **Data cần thiết:** đọc `chemical_lots`; ghi `notifications`; cờ chống trùng (bảng phụ hoặc khóa logic theo lô+mốc+ngày).
- **API cần:** không có endpoint công khai; là scheduled job. Có thể có endpoint admin "chạy thủ công cron-6" để test.

---

### FR-CHEM-013: Xuất Excel nhật ký nhập/xuất theo khoảng thời gian

- **Mô tả:** Xuất file Excel (.xlsx) toàn bộ giao dịch nhập/xuất/điều chỉnh trong một khoảng thời gian, có lọc theo phòng ban / hóa chất / mẫu / người, đúng đơn vị từng hóa chất.
- **Độ ưu tiên:** P0
- **Actor:** Admin, Ban lãnh đạo, Kế toán, KTV (phạm vi phòng). Kế toán có thêm cột chi phí.
- **Tiền điều kiện:** đã đăng nhập; chọn khoảng ngày.
- **Luồng chính:**
  1. User chọn khoảng ngày + bộ lọc → "Xuất Excel".
  2. Hệ thống truy vấn giao dịch trong phạm vi quyền của user → sinh file .xlsx với cột: ngày, hóa chất, CAS, lô, type, **`qty_input`, `input_unit` (đúng những gì người dùng nhập)**, **`qty_base`, `base_unit` (giá trị chuẩn)**, `balance_after` (theo base unit), mẫu liên quan, người thực hiện, ghi chú. Mỗi dòng ghi RÕ đơn vị; không cộng gộp khác đơn vị (BR-CHEM-017, BR-CHEM-027). **Với Kế toán/Admin/Ban lãnh đạo: bổ sung cột `unit_price`, `currency`, `giá trị` (= qty × unit_price của lô) theo từng dòng** (OQ#1 đã chốt). KTV: KHÔNG có các cột giá trị tiền này (BR-CHEM-022).
  3. Trả file tải về; ghi `audit_logs` action=`CHEMICAL_EXPORT_EXCEL` (R15 — đếm lượt tải).
- **Luồng phụ / ngoại lệ:**
  - A1: khoảng ngày không hợp lệ (from > to) → 400.
  - A2: dữ liệu lớn (xem NFR-PERF-CHEM-003) → nếu vượt ngưỡng đồng bộ thì xử lý nền + thông báo in-app khi xong (OPEN QUESTION #6).
  - A3: KTV phạm vi phòng → file chỉ chứa giao dịch phòng mình.
- **Hậu điều kiện:** file Excel phản ánh đúng dữ liệu + phạm vi quyền; lượt tải được audit.
- **Business Rules:** BR-CHEM-017 (đơn vị riêng từng dòng), BR-CHEM-018 (phạm vi), BR-CHEM-022 (cách ly chi phí), BR-CHEM-027 (ghi rõ qty_base/qty_input + đơn vị), BR-CHEM-030 (giá trị tiền theo đơn vị nhập).
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN 120 giao dịch trong tháng 5/2026 WHEN xuất Excel 01/05–31/05 THEN file .xlsx có đúng 120 dòng + dòng header, mỗi dòng ghi rõ `qty_input`+`input_unit` và `qty_base`+`base_unit` của hóa chất tương ứng (BR-CHEM-027).
  - AC2 (RBAC scope): GIVEN KTV phòng "Hóa lý" WHEN xuất Excel THEN file chỉ chứa giao dịch phòng "Hóa lý".
  - AC3 (tài chính — OQ#1): GIVEN KTV xuất Excel THEN file KHÔNG có cột `unit_price`/`giá trị`; Kế toán/Admin/Ban lãnh đạo xuất THÌ file CÓ cột `unit_price`, `currency`, `giá trị` (= qty × unit_price) đúng từng dòng.
  - AC4 (lỗi input): GIVEN from=01/06, to=01/05 WHEN xuất THEN trả 400 code `INVALID_DATE_RANGE`.
  - AC5 (audit tải): GIVEN xuất Excel thành công WHEN kiểm tra audit THEN có bản ghi `CHEMICAL_EXPORT_EXCEL` với user + khoảng ngày + correlationId.
- **Data cần thiết:** đọc `chemical_transactions` + join hóa chất/lô/mẫu/người.
- **API cần:** "xuất Excel nhật ký giao dịch theo khoảng ngày + bộ lọc".

---

### FR-CHEM-014: Báo cáo tiêu hao theo tháng / đề tài / người dùng

- **Mô tả:** Tổng hợp lượng hóa chất tiêu hao (tổng giao dịch out) theo nhóm: tháng, đề tài NCKH (qua mẫu → đề tài), người dùng — đúng đơn vị từng hóa chất. **Bổ sung cột giá trị tiền (chi phí tiêu hao = Σ(qty out × unit_price của lô xuất)) cho Admin/Ban lãnh đạo/Kế toán** (OQ#1 đã chốt).
- **Độ ưu tiên:** P1
- **Actor:** Admin, Ban lãnh đạo, Kế toán, KTV (phạm vi phòng).
- **Tiền điều kiện:** đã đăng nhập; có giao dịch out trong kỳ.
- **Luồng chính:**
  1. User chọn chiều tổng hợp (tháng / đề tài / người dùng) + khoảng ngày + bộ lọc.
  2. Hệ thống quy đổi mọi giao dịch về **base unit của từng hóa chất** rồi tổng hợp theo (hóa chất, base_unit) trong mỗi nhóm; khi hiển thị có thể quy đổi sang một display unit cùng nhóm. KHÔNG cộng gộp khác nhóm đo (BR-CHEM-027). Với vai trò tài chính: thêm cột **chi phí tiêu hao** = Σ(qty out × `unit_price` của lô tương ứng) theo `currency`; chi phí (tiền) CÓ thể cộng gộp trong cùng `currency` dù khác đơn vị đo lường vật lý (vì là giá trị tiền) — nhưng vẫn hiển thị dòng tiêu hao theo (hóa chất, đơn vị).
  3. Hiển thị bảng + cho phép xuất Excel/PDF.
- **Luồng phụ / ngoại lệ:**
  - A1: chiều "đề tài" cần liên kết mẫu→đề tài (M1/M4). Nếu mẫu không gắn đề tài → gom vào nhóm "Không gắn đề tài".
- **Hậu điều kiện:** chỉ đọc.
- **Business Rules:** BR-CHEM-017, BR-CHEM-018, BR-CHEM-022, BR-CHEM-023, BR-CHEM-027, BR-CHEM-030.
- **Acceptance Criteria:**
  - AC1 (happy): GIVEN tháng 5/2026 có các giao dịch out NaCl tổng 300 g (dù nhập rời theo g/kg) , Ethanol 500 mL WHEN báo cáo tiêu hao theo tháng THEN hệ thống quy đổi về base unit rồi hiển thị theo display unit: "NaCl: 300.0000 g", "Ethanol: 500.0000 mL" — tách dòng theo (hóa chất, nhóm đo), ghi rõ đơn vị.
  - AC0b (chi phí — OQ#1): GIVEN Kế toán xem báo cáo tiêu hao tháng 5/2026, NaCl xuất từ lô đơn giá 1200 VND/g × 300 g WHEN báo cáo THEN dòng NaCl có cột chi phí = 360000.00 VND; KTV xem cùng báo cáo THÌ KHÔNG có cột chi phí (BR-CHEM-022).
  - AC2 (theo đề tài): GIVEN mẫu gắn đề tài "DT-2026-01" dùng NaCl 120 g WHEN báo cáo theo đề tài THEN nhóm "DT-2026-01" có dòng NaCl 120.0000 g.
  - AC3 (không cộng khác đơn vị): GIVEN một nhóm có cả g và mL WHEN tổng hợp THEN không có ô "tổng" gộp khác đơn vị.
- **Data cần thiết:** aggregate `chemical_transactions` (type=out) join mẫu→đề tài / người.
- **API cần:** "báo cáo tiêu hao tổng hợp theo chiều (tháng/đề tài/người) + xuất".

---

## 4. Business Rules

| ID | Quy tắc | Lý do nghiệp vụ | Hệ quả nếu vi phạm |
|----|---------|-----------------|--------------------|
| BR-CHEM-001 | Tên hóa chất bắt buộc; `base_unit` bắt buộc, chọn từ danh mục `units` (g, mg, kg, mL, L, viên, ...); `measurement_group` suy ra từ base_unit | Đơn vị cơ sở xác định cách lưu trữ & tính tồn; không được tùy tiện | Block tạo, 400 `INVALID_UNIT` |
| BR-CHEM-002 | Không trùng (tên + CAS) trong cùng phòng ban | Tránh trùng danh mục gây nhầm tồn | 409 `DUPLICATE_CHEMICAL` |
| BR-CHEM-003 | Không cho đổi `base_unit`/`measurement_group` khi hóa chất đã có lô/giao dịch (đơn vị NHẬP/HIỂN THỊ vẫn đổi tự do trong cùng nhóm) | Đổi base unit làm sai toàn bộ tồn đã lưu theo base unit | 422 `UNIT_LOCKED` |
| BR-CHEM-004 | Không vô hiệu hóa hóa chất còn lô tồn > 0 | Tránh "mất" tồn khỏi báo cáo | 422, yêu cầu xử lý tồn trước |
| BR-CHEM-005 | `lot_no` duy nhất trong phạm vi một hóa chất | Truy vết theo lô (17025 §6.6 CoA) | 409 `DUPLICATE_LOT` |
| BR-CHEM-006 | `recheck_date` ≤ `expiry_date` | Kiểm tra lại phải trước hạn dùng | 422 `INVALID_DATE_ORDER` |
| BR-CHEM-007 | qty giao dịch in/out phải > 0 | Giao dịch 0 hoặc âm vô nghĩa | 400 `INVALID_QUANTITY` |
| BR-CHEM-008 | qty là NUMERIC tối đa 4 chữ số thập phân; KHÔNG dùng float | Tránh sai số tích lũy trên tồn (CONSTRAINT-1, N1) | 400 |
| BR-CHEM-009 | Tồn lô không bao giờ âm; xuất ≤ tồn hiện tại | Không thể xuất hóa chất không có thật | 422 `INSUFFICIENT_STOCK` |
| BR-CHEM-010 | Màn xuất gợi ý lô theo FEFO (hết hạn sớm nhất, chưa hết hạn, còn tồn lên đầu) | Giảm lãng phí do hết hạn | (gợi ý — không chặn) |
| BR-CHEM-011 | Mỗi giao dịch lưu `balance_after` = tồn lô ngay sau giao dịch | Audit tồn tại từng thời điểm; không tin SUM runtime (N1, 17025 §8.4) | Dữ liệu không audit được → fail VILAS |
| BR-CHEM-012 | Mọi CRUD hóa chất/lô/giao dịch/kiểm tra lại ghi `audit_logs` (user, action, resource, resource_id, correlation_id, ip, at, detail) | 17025 §8.4 kiểm soát hồ sơ — duy trì công nhận | Thiếu audit → vi phạm VILAS |
| BR-CHEM-013 | File đính kèm (CoA/MSDS): chỉ loại cho phép (PDF, PNG, JPG, XLSX) + ≤ giới hạn (OPEN QUESTION #7) | An toàn lưu trữ, tránh file độc hại | 422 `INVALID_FILE_TYPE`/`FILE_TOO_LARGE` |
| BR-CHEM-014 | Cập nhật tồn lô phải trong transaction DB có row-lock trên lô | Tránh race condition gây âm tồn / sai `balance_after` | Tồn sai → mất niềm tin dữ liệu |
| BR-CHEM-015 | Giao dịch là bất biến (immutable): không sửa/xóa; sửa sai chỉ qua `adjust` | Hồ sơ kỹ thuật không được tẩy xóa (17025 §7.5, §8.4) | Vi phạm tính toàn vẹn hồ sơ |
| BR-CHEM-016 | Giao dịch `adjust` bắt buộc có lý do (`note` NOT NULL); chỉ **KTV phụ trách phòng** (phạm vi phòng mình) hoặc **Admin** được thực hiện, KHÔNG cần lãnh đạo duyệt (OQ#4 chốt 19/06/2026) | Truy vết nguyên nhân lệch tồn khi audit; kiểm soát quyền điều chỉnh tồn | 400 `REASON_REQUIRED` / 403 `FORBIDDEN` |
| BR-CHEM-017 | KHÔNG cộng gộp tồn/tiêu hao của các đơn vị khác nhau; luôn nhóm theo (hóa chất, đơn vị) | Cộng g + mL là vô nghĩa (CONSTRAINT-2, N1) | Báo cáo sai → quyết định sai |
| BR-CHEM-018 | Phạm vi dữ liệu theo RBAC: KTV thao tác ghi chỉ trong phòng ban mình; đọc theo matrix; Admin/Lãnh đạo toàn hệ thống | Cách ly dữ liệu phòng ban (R13) | 403; rò rỉ dữ liệu chéo phòng |
| BR-CHEM-019 | Cảnh báo tồn thấp: chỉ tạo 1 notification "đang mở" mỗi hóa chất; đóng khi tồn ≥ ngưỡng | Tránh spam thông báo | Spam → user bỏ qua cảnh báo |
| BR-CHEM-020 | Lô có kiểm tra lại "không đạt" hoặc đã quá hạn dùng: **KHÔNG khóa cứng** — vẫn cho xuất nhưng phải **cảnh báo + người dùng xác nhận** mới thực hiện, ghi cờ `warning_override=true` + lý do (OQ#5 chốt 19/06/2026) | KH chấp nhận rủi ro vận hành nhưng phải truy vết; cảnh báo tránh dùng nhầm hóa chất không đạt | Xuất chưa xác nhận → 422 `WARNING_NEEDS_CONFIRM`; rủi ro 17025 nếu không ghi lý do |
| BR-CHEM-021 | Cron nhắc: mỗi lô × mỗi mốc (30/15/7 ngày) chỉ phát 1 notification; idempotent theo ngày | Chống trùng khi cron retry / chạy lại | Spam thông báo |
| BR-CHEM-022 | KTV **được nhập** `unit_price` khi nhập lô (input), nhưng các trường **giá trị tồn / chi phí tiêu hao tổng hợp** (cột tiền trong lịch sử/báo cáo/Excel) chỉ trả cho Admin / Ban lãnh đạo / Kế toán; lọc khỏi response đọc cho KTV ở tầng API (OQ#1 chốt 19/06/2026) | Cách ly tài chính (B03) | Rò rỉ thông tin tài chính cho KTV |
| BR-CHEM-023 | Giá trị tồn tính **theo TỪNG LÔ**: giá trị tồn lô = qty còn lại × `unit_price` của lô (`unit_price` NUMERIC(14,2), `currency` mặc định VND). KHÔNG dùng bình quân gia quyền (vì đã quản lý tồn theo lô); chi phí tiêu hao = Σ(qty out × `unit_price` lô xuất) (OQ#1 chốt 19/06/2026) | Đã quản lý theo lô nên tính giá theo lô là chính xác & truy vết được; tránh phức tạp bình quân gia quyền | Giá trị tồn/chi phí sai → báo cáo tài chính sai |
| BR-CHEM-024 | Xuất lô "không đạt"/quá hạn phải có cờ `warning_override=true`; khuyến nghị bắt buộc ghi lý do để truy vết 17025; ghi cờ + lý do vào giao dịch và audit (OQ#5 chốt 19/06/2026) | Truy vết quyết định dùng lô có rủi ro; phục vụ audit VILAS | Thiếu truy vết → rủi ro 17025 khi đánh giá lại |
| BR-CHEM-025 | Giao dịch xuất (type=out) bắt buộc `ref_sample_id` NOT NULL và mẫu phải tồn tại; cấm xuất không gắn mẫu (mọi nhu cầu xuất không-mẫu phải qua CR) (OQ#3 chốt 19/06/2026) | Gắn tiêu hao với mẫu/đề tài để báo cáo & truy vết kỹ thuật (17025 §7.5) | Thiếu mẫu → 422 `SAMPLE_REQUIRED`; báo cáo theo đề tài sai |
| BR-CHEM-026 | Mỗi hóa chất có **đúng 1 `base_unit` + `measurement_group`** cố định; mọi tồn/giao dịch LƯU TRỮ NỘI BỘ theo base unit bằng **NUMERIC(18,6)**. Người dùng nhập/xuất/xem theo đơn vị tùy chọn cùng nhóm; hệ thống quy đổi về base unit để lưu (OQ#2 chốt 19/06/2026) | Lưu trữ thống nhất, tránh mất chính xác khi quy đổi; cho phép nhập/hiển thị linh hoạt | Lưu sai đơn vị → tồn sai toàn hệ thống |
| BR-CHEM-027 | Mỗi giao dịch lưu **CẢ** (`qty_base` + `base_unit`) lẫn (`qty_input` + `input_unit`); `balance_after` luôn theo base unit; báo cáo/Excel ghi rõ đơn vị; tổng hợp quy về base unit, KHÔNG cộng gộp khác nhóm đo (OQ#2 chốt 19/06/2026) | Audit đúng những gì người dùng nhập (17025 §8.4) + tính tồn chuẩn theo base unit | Mất truy vết đơn vị nhập; báo cáo sai |
| BR-CHEM-028 | Chỉ quy đổi **trong cùng nhóm đo** (mass/volume/count); `input_unit`/display unit phải cùng nhóm với `base_unit`. CẤM quy đổi chéo nhóm (g ↔ mL) | Quy đổi chéo nhóm cần tỷ trọng/nồng độ — ngoài scope, dễ sai nghiêm trọng | 422 `UNIT_GROUP_MISMATCH` |
| BR-CHEM-029 | Hệ số quy đổi (`factor_to_base`) là **cố định** trong danh mục `units`; người dùng cuối KHÔNG được tạo đơn vị mới hay sửa hệ số (chỉ qua seed/migration quản trị) | Tránh sai số/gian lận khi sửa hệ số quy đổi | Sai hệ số → toàn bộ tồn/giá trị sai |
| BR-CHEM-030 | Đơn giá `unit_price` gắn với đơn vị NHẬP của lô (`price_unit`); giá trị tồn lô = qty còn lại (quy về `price_unit`) × `unit_price`; chi phí tiêu hao = Σ(qty out quy về `price_unit` × `unit_price`) (OQ#1 + OQ#2 chốt 19/06/2026) | Giá nhập theo đơn vị nhập; phải quy đổi tồn (base unit) về đơn vị giá khi tính tiền | Tính giá trị tồn/chi phí sai |

---

## 5. Use Case chính

### UC-CHEM-01: Nhập hóa chất (tạo lô + giao dịch nhập)
- **Actor chính:** KTV (phòng mình) / Admin.
- **Tiền điều kiện:** hóa chất đã có trong danh mục.
- **Luồng:**
  1. KTV chọn hóa chất "NaCl".
  2. Tạo lô "L2026-001" (expiry 31/12/2027, recheck 31/12/2026), upload CoA.
  3. Nhập giao dịch in 500 g cho lô vừa tạo, kèm `unit_price` = 1200 VND/g → giá trị tồn lô = 600000.00 VND.
  4. Hệ thống (atomic): tạo lô → ghi giao dịch in `balance_after=500.0000` → cập nhật tồn lô → audit `CHEMICAL_LOT_CREATE` + `CHEMICAL_TXN_IN`.
- **Hậu điều kiện:** tồn NaCl tăng 500 g; CoA truy xuất được.
- **Liên kết FR:** FR-CHEM-002, FR-CHEM-005.

### UC-CHEM-02: Xuất hóa chất gắn mẫu
- **Actor chính:** KTV (phòng mình).
- **Tiền điều kiện:** lô có tồn > 0; mẫu "SP-2026-0007" đang testing.
- **Luồng:**
  1. KTV chọn "NaCl" → hệ thống gợi ý lô theo FEFO.
  2. Chọn lô, nhập 12.5 g, **bắt buộc chọn mẫu SP-2026-0007** (OQ#3).
  3. Nếu lô "không đạt"/quá hạn → cảnh báo + xác nhận (OQ#5) mới cho xuất, ghi `warning_override`.
  4. Hệ thống kiểm tra mẫu hợp lệ + tồn đủ → ghi giao dịch out (`ref_sample_id`, `balance_after`), trừ tồn, audit `CHEMICAL_TXN_OUT`.
  4. Nếu tồn < ngưỡng → tạo cảnh báo tồn thấp.
- **Ngoại lệ:** xuất quá tồn → 422 `INSUFFICIENT_STOCK`.
- **Hậu điều kiện:** tồn lô giảm; tiêu hao truy vết được tới mẫu/đề tài.
- **Liên kết FR:** FR-CHEM-006, FR-CHEM-010.

### UC-CHEM-03: Xuất Excel nhật ký
- **Actor chính:** Kế toán / Admin / KTV (phạm vi).
- **Luồng:**
  1. Chọn khoảng 01/05–31/05/2026 + lọc phòng.
  2. Hệ thống truy vấn giao dịch trong phạm vi quyền → sinh .xlsx (đúng đơn vị từng dòng; cột chi phí chỉ cho vai trò tài chính).
  3. Tải file; audit `CHEMICAL_EXPORT_EXCEL`.
- **Liên kết FR:** FR-CHEM-013.

### UC-CHEM-04: Xử lý cảnh báo hết hạn (cron + người dùng)
- **Actor chính:** hệ thống (CRON-6) → KTV phụ trách.
- **Luồng:**
  1. Cron 07:00 quét lô tới mốc 30/15/7 ngày → tạo notification in-app.
  2. KTV mở thông báo → vào lô → quyết định: kiểm tra lại / nhập lý do / lập kế hoạch hủy.
  3. Nếu kiểm tra lại "không đạt" → đánh dấu lô; lần xuất sau sẽ cảnh báo + yêu cầu xác nhận (OQ#5), KHÔNG khóa cứng.
- **Liên kết FR:** FR-CHEM-011, FR-CHEM-012, FR-CHEM-006.

---

## 6. Yêu cầu phi chức năng (NFR)

Theo template `~/.claude/rules/nfr.md`. Con số định cỡ cho quy mô **~40 user** (C03), môi trường staging tương đương production (Docker Compose, ~2–4 vCPU/8GB). Giả định cao điểm: ~10 concurrent users.

```
NFR-PERF-CHEM-001: Ghi giao dịch nhập/xuất hóa chất
────────────────────────────────────────────────────
Mô tả:     API ghi giao dịch (POST in/out) phải phản hồi đủ nhanh để
           KTV thao tác liền mạch tại bàn thí nghiệm.
Metric:    P95 < 400ms | P99 < 700ms
Tool đo:   k6 (tests/performance/chem-transaction.js)
Điều kiện: 10 concurrent users, dataset 50,000 giao dịch, staging
Pass:      p(95) < 400ms suốt 10 phút ở 10 concurrent users, error rate < 1%
Fail:      p(95) ≥ 400ms → review index lô + row-lock contention
Ưu tiên:  Must Have
```
```
NFR-PERF-CHEM-002: Tìm kiếm / liệt kê hóa chất & lịch sử giao dịch
────────────────────────────────────────────────────
Metric:    P95 < 500ms cho danh sách phân trang 20/trang
Tool đo:   k6 (tests/performance/chem-search.js)
Điều kiện: 10 concurrent users, 5,000 hóa chất, 50,000 giao dịch
Pass:      p(95) < 500ms; query dùng index (không Sequential Scan bảng lớn)
Fail:      p(95) ≥ 500ms → thêm index (chemical_id, lot_id, at, ref_sample_id)
Ưu tiên:  Should Have
```
```
NFR-PERF-CHEM-003: Xuất Excel nhật ký
────────────────────────────────────────────────────
Metric:    Xuất ≤ 10,000 dòng đồng bộ trong < 5s (P95).
           > 10,000 dòng → xử lý nền + notify in-app khi xong.
Tool đo:   k6 + đo thời gian sinh file
Điều kiện: 3 concurrent users xuất đồng thời
Pass:      ≤ 10,000 dòng: P95 < 5s. Không OOM khi 3 user xuất song song.
Fail:      OOM hoặc timeout → chuyển ngưỡng sang async job
Ưu tiên:  Should Have
```
```
NFR-CORRECT-CHEM-001: Chính xác số học tồn kho (Must — đặc thù domain)
────────────────────────────────────────────────────
Mô tả:     Tồn lô lưu theo base unit bằng NUMERIC(18,6), qty người dùng
           NUMERIC(14,4); không sai số float.
Metric:    Sau N giao dịch ngẫu nhiên (in/out nhiều đơn vị cùng nhóm),
           tồn lô (qty_base) = balance_after giao dịch cuối
           = Σ(in_base) − Σ(out_base) ± adjust_base, sai lệch = 0 tuyệt đối
           ở mức NUMERIC(18,6) (không epsilon float).
Tool đo:   Test tự động: 10,000 giao dịch ngẫu nhiên (đơn vị trộn) rồi reconcile
Pass:      Lệch = 0.000000 trên 100% lô
Fail:      Bất kỳ lệch nào → bug nghiêm trọng, block release
Ưu tiên:  Must Have
```
```
NFR-CORRECT-CHEM-002: Quy đổi đơn vị round-trip không mất chính xác (Must — OQ#2)
────────────────────────────────────────────────────
Mô tả:     Quy đổi 2 chiều giữa đơn vị nhập/hiển thị và base unit (trong cùng
           nhóm đo) phải không làm thay đổi giá trị lưu trữ.
Metric:    Với mọi cặp đơn vị cùng nhóm và mọi qty_input ≤ NUMERIC(14,4):
           qty_input −(×factor)→ qty_base(18,6) −(÷factor)→ qty_display
           thì qty_display = qty_input đúng tuyệt đối (vd nhập kg → lưu mg →
           hiển thị kg phải bằng giá trị nhập). Sai số = 0 ở mức NUMERIC(18,6).
           Hệ số factor_to_base lấy từ bảng units (cố định), không float.
Tool đo:   Test tự động property-based: round-trip qua mọi cặp đơn vị cùng nhóm
Pass:      0 trường hợp lệch trên toàn bộ tập sinh ngẫu nhiên (≥ 100,000 cặp)
Fail:      Bất kỳ lệch nào → bug nghiêm trọng (rủi ro VILAS), block release
Ưu tiên:  Must Have
```
```
NFR-CONCUR-CHEM-001: An toàn tương tranh khi trừ tồn (Must)
────────────────────────────────────────────────────
Metric:    Với K request xuất đồng thời trên cùng lô tồn Q, tổng xuất
           thành công ≤ Q; tồn không bao giờ âm.
Tool đo:   k6 ramping-vus bắn đồng thời cùng lô + kiểm tra DB
Điều kiện: 20 request xuất song song trên 1 lô
Pass:      Tồn cuối ≥ 0; số giao dịch out thành công khớp tồn đã trừ
Fail:      Tồn âm hoặc balance_after sai → fix row-lock/transaction
Ưu tiên:  Must Have
```
```
NFR-AUDIT-CHEM-001: Đầy đủ & bất biến audit (VILAS 17025 §8.4) (Must)
────────────────────────────────────────────────────
Mô tả:     Mọi thao tác CRUD hóa chất/lô/giao dịch/kiểm tra lại ghi audit_logs.
Metric:    100% thao tác ghi (create/update/inactivate/in/out/adjust/recheck/
           export) có bản ghi audit_logs với correlation_id; 0 endpoint
           cho phép sửa/xóa giao dịch đã ghi.
Tool đo:   Test tự động đếm audit/thao tác + rà soát route (không có DELETE/PUT
           trên chemical_transactions)
Pass:      Tỷ lệ audit/thao tác = 100%; giao dịch immutable
Fail:      < 100% hoặc tồn tại route sửa giao dịch → block (vi phạm VILAS)
Ưu tiên:  Must Have
```
```
NFR-SEC-CHEM-001: Phân quyền & cách ly dữ liệu (Must)
────────────────────────────────────────────────────
Mô tả:     Enforce RBAC + phạm vi phòng ban + cách ly trường tài chính ở
           tầng API (không chỉ FE).
Metric:    Ma trận test 4 vai trò × các action M2 pass 100%; KTV không
           thấy trường chi phí trong mọi response; không thao tác ghi
           chéo phòng ban.
Tool đo:   Test RBAC tự động (security-auditor) + manual
Pass:      0 truy cập trái phép; 0 rò rỉ trường chi phí cho KTV
Fail:      Bất kỳ bypass nào → block go-live (OWASP A01)
Ưu tiên:  Must Have
```
```
NFR-SEC-CHEM-002: An toàn upload file CoA/MSDS (Must)
────────────────────────────────────────────────────
Metric:    Chỉ chấp nhận PDF/PNG/JPG/XLSX (validate MIME thực + đuôi),
           ≤ giới hạn dung lượng (OPEN QUESTION #7); không thực thi file;
           lưu MinIO, không lưu binary trong DB.
Tool đo:   Test upload file độc hại / sai loại / quá lớn
Pass:      File sai loại/quá lớn bị từ chối 422; file hợp lệ tải lại được
Ưu tiên:  Must Have
```
```
NFR-MAINT-CHEM-001: Test coverage domain hóa chất (Must)
────────────────────────────────────────────────────
Metric:    Service tính tồn / transaction / FEFO / RBAC scope coverage ≥ 85%;
           module M2 overall ≥ 70%.
Tool đo:   pytest --cov
Pass:      ≥ 85% domain, ≥ 70% module; CI block nếu drop > 5%
Ưu tiên:  Must Have
```
```
NFR-OBS-CHEM-001: Logging & truy vết (Should)
────────────────────────────────────────────────────
Metric:    Mọi request M2 có correlation_id xuyên FE→BE→audit_logs;
           giao dịch ghi log INFO; xuất quá tồn / vượt ngưỡng ghi WARN;
           lỗi transaction ghi ERROR kèm stack (không lộ ra client).
Tool đo:   Rà log + test
Pass:      Trace được 1 giao dịch từ log FE → audit DB qua correlation_id
Ưu tiên:  Should Have
```

---

## 7. Giả định & Ràng buộc (tổng hợp)

**Assumptions:**
- ASSUMPTION-1 → **ĐÃ CHỐT (OQ#2):** một hóa chất có đúng 1 `base_unit` + `measurement_group` cố định để lưu trữ nội bộ; người dùng được nhập/xuất/xem theo đơn vị khác cùng nhóm, hệ thống tự quy đổi. Cấm quy đổi chéo nhóm; hệ số cố định không sửa được.
- ASSUMPTION-2 → **ĐÃ CHỐT (OQ#4):** `adjust` cần lý do bắt buộc (`note` NOT NULL), do **KTV phụ trách phòng** (phạm vi phòng mình) hoặc **Admin**; không cần lãnh đạo duyệt.
- ASSUMPTION-3: Ngưỡng cảnh báo tồn đặt ở cấp hóa chất (theo đơn vị mặc định), không theo lô.
- ASSUMPTION-4: Tồn lô đọc trực tiếp từ `chemical_lots.qty` (đã maintain bởi giao dịch) để đạt hiệu năng; tính đúng nhờ `balance_after` + reconcile job (FR-CHEM-008 A1).
- ASSUMPTION-5: "Người phụ trách hóa chất của phòng ban" để gửi cảnh báo/cron = KTV có quyền nhập/xuất của phòng đó (nếu nhiều người → gửi tất cả) — OPEN QUESTION #8.

**Constraints:** xem §2.4 (CONSTRAINT-1..6).

**Ghi chú cấu trúc dữ liệu cho `schema-designer` (cập nhật v1.2 theo OQ#1/#2/#3/#4/#5):**
- **Bảng `units` (MỚI — OQ#2):** `code` (PK, vd 'kg','g','mg','L','mL','unit'), `group` ∈ {mass, volume, count}, `factor_to_base NUMERIC` (hệ số đổi về đơn vị nhỏ nhất của nhóm, vd kg=1000000, g=1000, mg=1 cho mass; L=1000, mL=1 cho volume; unit=1 cho count), `label`. Seed cố định; KHÔNG để người dùng cuối sửa (BR-CHEM-029).
- `chemicals`: **thay `default_unit`** bằng `base_unit VARCHAR (FK→units.code)` + `measurement_group VARCHAR(10)` (mass/volume/count, suy ra từ base_unit, lưu denormalized để chặn quy đổi chéo nhóm nhanh); `reorder_threshold NUMERIC(18,6)` theo base_unit. Khóa đổi base_unit/group khi đã có lô/giao dịch (BR-CHEM-003).
- `chemical_lots`: **tồn dùng `qty_base NUMERIC(18,6)`** (thay `qty NUMERIC(14,4)`); thêm `unit_price NUMERIC(14,2) NOT NULL DEFAULT 0`, `price_unit VARCHAR (FK→units.code, = đơn vị nhập của lô — OQ#1/#2)`, `currency VARCHAR(3) NOT NULL DEFAULT 'VND'`; thêm `recheck_result` ∈ {pass, fail, null}.
- `chemical_transactions`: **lưu CẢ** `qty_base NUMERIC(18,6)` + `base_unit VARCHAR` (chuẩn để tính tồn) lẫn `qty_input NUMERIC(14,4)` + `input_unit VARCHAR (FK→units.code)` (đúng người dùng nhập); `balance_after NUMERIC(18,6)` theo base unit; `ref_sample_id` **NOT NULL khi type='out'** (CHECK/partial constraint); `warning_override BOOLEAN NOT NULL DEFAULT false`; `note` **NOT NULL khi type='adjust'**; có thể lưu `unit_price`/`price_unit`/`currency` trên giao dịch in (đồng bộ với lô).
- **CHECK constraint nhóm đo:** đảm bảo `input_unit` (và `base_unit`) cùng `group` với `chemicals.measurement_group` (enforce ở app + DB nếu khả thi) — chặn quy đổi chéo nhóm (BR-CHEM-028).
- Giá trị tồn/chi phí KHÔNG lưu cột tính sẵn — tính runtime: quy `qty_base` về `price_unit` rồi × `unit_price` (theo lô); cân nhắc index hỗ trợ báo cáo tiêu hao có chi phí.
- Tính giá theo **từng lô** (không cần bảng/cột bình quân gia quyền).

---

## 8. OPEN QUESTIONS (cần KH trả lời trước khi `/contract`)

| # | Câu hỏi | Tại sao cần biết | Ảnh hưởng nếu chưa rõ | Người trả lời | Deadline |
|---|---------|------------------|----------------------|---------------|----------|
| 1 | ~~Hóa chất có cần quản lý **giá/chi phí**...~~ | — | — | KH (Kế toán + Lãnh đạo) | **ĐÃ CHỐT 19/06/2026** |
| | **Quyết định:** CÓ. Nhập **`unit_price` NUMERIC(14,2)** + `currency` (mặc định VND) khi nhập lô. Giá trị tồn lô = qty còn lại × `unit_price`; chi phí tiêu hao = Σ(qty out × `unit_price` lô). Tính **theo từng lô**, không bình quân gia quyền. Kế toán/Admin/Ban lãnh đạo xem cột giá trị tiền (Excel + báo cáo tiêu hao); KTV nhập giá nhưng không xem báo cáo giá trị. → FR-CHEM-005/013/014, BR-CHEM-022/023. | | | | |
| 2 | ~~Một hóa chất có thể có **nhiều đơn vị / cần quy đổi**...~~ | — | — | KH (Trưởng lab) | **ĐÃ CHỐT 19/06/2026** |
| | **Quyết định:** CÓ — hệ thống **tự quy đổi đơn vị**. Mỗi hóa chất có **`base_unit` + `measurement_group`** (mass/volume/count) cố định; tồn/giao dịch lưu nội bộ theo base unit (**NUMERIC(18,6)**, khuyến nghị mg/mL/đơn vị). Người dùng nhập/xuất/xem theo đơn vị tùy chọn **cùng nhóm**; hệ thống quy đổi qua **hệ số cố định** trong bảng `units` (không sửa được). Mỗi giao dịch lưu CẢ (qty_base+base_unit) lẫn (qty_input+input_unit); `balance_after` theo base unit. **Cấm quy đổi chéo nhóm** (g↔mL → cần CR). Quy đổi 2 chiều round-trip không đổi giá trị (sai số=0 ở NUMERIC(18,6)). Giá nhập theo đơn vị nhập (`price_unit`); giá trị tồn = qty còn lại (quy về price_unit) × unit_price. → FR-CHEM-001/002/005/006/008/013/014; BR-CHEM-026..030; NFR-CORRECT-CHEM-002; bảng `units` mới. | | | | |
| 3 | ~~Xuất hóa chất **bắt buộc** gắn mẫu...~~ | — | — | KH (KTV + Lãnh đạo) | **ĐÃ CHỐT 19/06/2026** |
| | **Quyết định:** BẮT BUỘC. `chemical_transactions.ref_sample_id` **NOT NULL** với type=out. Cấm xuất không gắn mẫu — mọi nhu cầu xuất không-mẫu (dùng chung/đào tạo/hao hụt) phải qua CR. → FR-CHEM-006 (A3, AC7), BR-CHEM-025. | | | | |
| 4 | ~~Ai được phép **điều chỉnh kiểm kê** (`adjust`)?~~ | — | — | KH (Lãnh đạo) | **ĐÃ CHỐT 19/06/2026** |
| | **Quyết định:** **KTV phụ trách hóa chất của phòng** (phạm vi phòng mình) + **Admin** được làm; **KHÔNG cần lãnh đạo duyệt**. `note` **NOT NULL** với type=adjust (lý do bắt buộc); ghi audit đầy đủ. → FR-CHEM-007, BR-CHEM-016. | | | | |
| 5 | ~~Lô kiểm tra lại **"không đạt"**...~~ | — | — | KH (Trưởng lab) | **ĐÃ CHỐT 19/06/2026** |
| | **Quyết định:** CẢNH BÁO nhưng VẪN CHO XUẤT. Lô "không đạt" hoặc quá hạn → hiển thị cảnh báo + yêu cầu **xác nhận** (`confirm_warning`) mới cho xuất; ghi cờ `warning_override=true` + lý do vào giao dịch và audit. KHÔNG khóa cứng. **Rủi ro 17025:** dùng hóa chất không đạt có thể bị nêu khi đánh giá lại — **khuyến nghị bắt buộc ghi lý do** khi xuất để truy vết. → FR-CHEM-006 (A2/A8/A9), FR-CHEM-011, BR-CHEM-020/024. | | | | |
| 6 | Ngưỡng số dòng để xuất Excel chuyển sang **xử lý nền** (async) — chấp nhận 10,000 dòng đồng bộ không? | Định cỡ NFR-PERF-CHEM-003 | Xuất bộ lớn có thể timeout/OOM | KH (IT/vận hành) | trước `/contract` (có thể chốt khi UAT) |
| 7 | **Giới hạn dung lượng & loại file** đính kèm CoA/MSDS (vd ≤ 20MB, PDF/ảnh)? | Cấu hình MinIO + validate (BR-CHEM-013) | Không validate được file; rủi ro lưu trữ | KH (IT) | trước `/contract` |
| 8 | Mỗi phòng ban có **một người phụ trách hóa chất** cố định để nhận cảnh báo/cron, hay gửi tới tất cả KTV có quyền của phòng? | Xác định người nhận `notifications` (FR-CHEM-010/012) | Cảnh báo gửi sai/thiếu người → bỏ lỡ hết hạn | KH (Lãnh đạo) | trước `/contract` |

> **Trạng thái:** #1, #2, #3, #4, #5 **đã chốt với KH 19/06/2026** (xem chi tiết trong bảng). Còn lại **#6, #7, #8** cần confirm trước/khi UAT (đều là tham số vận hành, không ảnh hưởng ERD lõi → có thể chốt khi UAT).

---

## 9. Ma trận truy vết (Traceability Matrix)

| FR ID | Yêu cầu gốc (meeting note) | Submodule (demo-scope) | Điều khoản 17025 | Business Rule | Test Case (QA sẽ tạo) | Trạng thái |
|-------|----------------------------|------------------------|------------------|---------------|------------------------|------------|
| FR-CHEM-001 | R4, A04, **OQ#2** | F2.1.1 | §6.4 | BR-001..004, 012, 018, **026, 028, 029** | TC-CHEM-001..004 | Draft |
| FR-CHEM-002 | A03, R16, **OQ#2** | F2.1.2 | §6.6 (CoA) | BR-005, 006, 012, **026** | TC-CHEM-005..008 | Draft |
| FR-CHEM-003 | R4 (file), demo F2.1.3 | F2.1.3 | §6.4 | BR-013, 012 | TC-CHEM-009..011 | Draft |
| FR-CHEM-004 | R8, R10 (lọc) | F2.1.x | §8.4 | BR-018 | TC-CHEM-012..013 | Draft |
| FR-CHEM-005 | R4, **OQ#1, OQ#2** | F2.2.1 | §6.4, §8.4 | BR-007, 008, 011, 012, 014, **022, 023, 026, 027, 028, 030** | TC-CHEM-014..018 | Draft |
| FR-CHEM-006 | R4, A04b (gắn mẫu), **OQ#2, OQ#3, OQ#5** | F2.2.2 | §6.4, §7.5, §8.4 | BR-007..012, 014, 015, **020, 024, 025, 026, 027, 028** | TC-CHEM-019..027 | Draft |
| FR-CHEM-007 | N1 (kiểm kê), **OQ#4** | F2.2.x | §8.4 | BR-009, 015, **016** | TC-CHEM-028..031 | Draft |
| FR-CHEM-008 | R4, N1, **OQ#2** | F2.2.3 | §8.4 | BR-015, 017, **026, 027, 028** | TC-CHEM-029..031 | Draft |
| FR-CHEM-009 | R4, R15 | F2.2.4 | §8.4 | BR-015, 018 | TC-CHEM-032..035 | Draft |
| FR-CHEM-010 | demo F2.2.5 | F2.2.5 | §6.4 | BR-019 | TC-CHEM-036..038 | Draft |
| FR-CHEM-011 | R16, **OQ#5** | F2.3.1 | §6.4, §6.6 | BR-012, **020, 024** | TC-CHEM-039..041 | Draft |
| FR-CHEM-012 | R16 (CRON-6) | F2.3.2 | §6.4 | BR-021 | TC-CHEM-042..045 | Draft |
| FR-CHEM-013 | R4 (xuất Excel), **OQ#1, OQ#2** | F2.4.1 | §8.4 | BR-017, 018, 022, **023, 027, 030** | TC-CHEM-046..050 | Draft |
| FR-CHEM-014 | R4, R10, **OQ#1, OQ#2** | F2.4.2 | §8.4 | BR-017, 018, **022, 023, 027, 030** | TC-CHEM-051..053 | Draft |

**Mapping cron:** FR-CHEM-012 ↔ CRON-6 (`01-demo-scope.md` mục D).
**Mapping điều khoản 17025 (demo-scope mục E):** §6.4 (vật tư/hóa chất), §6.6 (mua ngoài + CoA), §7.5 (hồ sơ kỹ thuật), §8.4 (kiểm soát hồ sơ) — phủ bởi audit + balance_after + immutable transactions.

---

*Hết SRS M2 (v1.2). KH đã chốt #1/#2/#3/#4/#5 bằng văn bản 19/06/2026 (đã cập nhật vào SRS). Còn #6/#7/#8 (ngưỡng async Excel, giới hạn file CoA/MSDS, người phụ trách nhận cảnh báo) cần xác nhận — đều là tham số vận hành, có thể chốt khi UAT, không chặn `/contract` cho ERD lõi.*
