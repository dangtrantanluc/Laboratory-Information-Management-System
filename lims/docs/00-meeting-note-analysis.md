# Phân tích Meeting Note → Yêu cầu (Requirement Extraction)

**Dự án:** Phần mềm Quản lý Phòng Thí nghiệm (LIMS) theo ISO/IEC 17025:2017
**Loại lab:** Học thuật / Trường Đại học
**Ngày phân tích:** 19/06/2026
**Trạng thái:** DRAFT — cần khách hàng xác nhận (theo rule "Verbal is Nothing")

> ⚠️ Meeting note là ghi chú miệng, nhiều ý rời rạc. Tài liệu này **diễn giải** thành yêu cầu có thể truy vết.
> Mọi dòng "diễn giải" cần KH xác nhận lại bằng văn bản trong 24h làm việc trước khi đưa vào SRS.

---

## 1. Bóc tách yêu cầu thô từ meeting note

| # | Câu gốc trong meeting note | Diễn giải thành yêu cầu | Module | Cần làm rõ |
|---|----------------------------|--------------------------|--------|------------|
| R1 | "yêu cầu 17025 - cập nhật quy trình theo 17025" | Toàn hệ thống phải tuân thủ quy trình ISO/IEC 17025:2017 (kiểm soát tài liệu, hồ sơ, năng lực, thiết bị, mẫu) | Toàn bộ | Lab đã/đang xin công nhận VILAS chưa? |
| R2 | "kèm file vào này" | Mọi bản ghi (tài liệu, mẫu, kết quả) phải đính kèm được file (PDF, ảnh, Excel...) | Tài liệu, Mẫu | Loại file & dung lượng tối đa? |
| R3 | "quy trình: tài liệu - lịch sử" | Quản lý tài liệu có **version/lịch sử** (document control 17025 §8.3) | Tài liệu | Cần duyệt tài liệu (approval workflow) không? |
| R4 | "hóa chất hôm đó xuất nhập bao nhiêu gam, trừ ra và hiển thị, xuất excel" | Quản lý tồn kho hóa chất theo **gam**, ghi nhật ký xuất/nhập, tự trừ tồn, hiển thị tồn hiện tại, **xuất Excel** | Hóa chất | Đơn vị khác gam (mL, mg)? Theo lô (lot/batch)? |
| R5 | "tạo phiếu và chuyển cho nhân sự khác" | Tạo **phiếu** (yêu cầu thử nghiệm / phiếu công việc) rồi **chuyển giao** (assign/handover) cho người khác | Mẫu | Phiếu gì? Phiếu phân tích mẫu hay phiếu nội bộ? |
| R6 | "khách hàng gửi mẫu qua phòng, điền cho từng người, sau thí nghiệm mọi người điền và gửi lại, cho mọi người thấy công khai" | KH gửi mẫu → phân công từng KTV → mỗi người điền kết quả → kết quả **hiển thị công khai** trong nội bộ lab | Mẫu | "Công khai" = công khai nội bộ hay cả KH xem được? |
| R7 | "Thông báo cron job tới hạn cho mẫu thí nghiệm" | Cron job **nhắc deadline** mẫu thí nghiệm sắp tới hạn | Mẫu + Thông báo | Kênh nhắc: in-app / email / Zalo? |
| R8 | "tổng hợp, lọc thông tin" | Màn hình tổng hợp + bộ lọc đa tiêu chí | Báo cáo | — |
| R9 | "mẫu ghi chú lý do, trường để người dùng điền lý do trễ hạn" | Khi mẫu/công việc **trễ hạn**, bắt buộc điền **lý do trễ hạn** | Mẫu | Lý do trễ có cần lãnh đạo duyệt? |
| R10 | "thống kê số mẫu, hóa chất, lọc thời gian" | Dashboard thống kê số mẫu, lượng hóa chất, lọc theo khoảng thời gian | Báo cáo | — |
| R11 | "nền tảng lưu trữ tối ưu - về giá và thời gian" | Lưu trữ file tối ưu chi phí + tốc độ → đề xuất object storage (S3/MinIO/R2) | Hạ tầng | Có chấp nhận cloud (R2/S3) hay bắt buộc on-premise? |
| R12 | "nhân sự - thêm trường thời gian ký hợp đồng, thời gian nâng lương (3 năm nâng lương xét cron job - trước 1 tuần, thêm 15 ngày bước trước, 3 ngày)" | Hồ sơ nhân sự có trường **ngày ký HĐ** và **chu kỳ nâng lương 3 năm**; cron nhắc **3 mốc**: trước 15 ngày → 7 ngày → 3 ngày | Nhân sự | Chu kỳ nâng lương cố định 3 năm cho mọi người? |
| R13 | "role: nhân sự - kế toán - ban lãnh đạo - admin, nhận mẫu (trao đổi lại về phòng ban vai trò)" | 5 vai trò: Admin, Ban lãnh đạo, Kế toán, Nhân sự/KTV, Nhận mẫu. RBAC **+ phạm vi theo phòng ban** | Phân quyền | Cơ cấu phòng ban cụ thể? (đã chốt: RBAC + scope phòng ban) |
| R14 | "build lại thì gửi demo" | Mỗi lần build/release → gửi bản demo cho KH duyệt | Quy trình | — (đưa vào quy trình bàn giao) |
| R15 | "thống kê số lượng truy cập, số lượng tải, lượng chỉnh sửa và lượt tải" | Audit/Analytics: đếm **lượt truy cập, lượt tải file, lượt chỉnh sửa** | Audit log | Thống kê theo user hay theo tài liệu? |
| R16 | "17025 vlab - thời gian nhắc việc từng phần: nhắc trước thời gian hiệu chuẩn, thời gian kiểm tra lại hóa chất" | Cron nhắc **hiệu chuẩn thiết bị** (calibration) + **kiểm tra lại/hạn dùng hóa chất** | Thiết bị, Hóa chất | Lịch hiệu chuẩn lấy từ đâu? Nhập tay? |
| R17 | "các đề tài, chủ nhiệm đề tài, bài báo, bằng sáng chế cho cá nhân/tập thể/phòng thí nghiệm" | Quản lý **thành tích NCKH**: đề tài (có chủ nhiệm), bài báo, sáng chế — gắn cho cá nhân / nhóm / lab | Nhân sự (NCKH) | Cần phân loại cấp đề tài (cấp trường/bộ/NN)? |
| R18 | "số lượng hướng dẫn sinh viên, số lần sinh viên đăng ký vào phòng thí nghiệm" | Đếm số SV được hướng dẫn + số lượt SV đăng ký vào lab | Nhân sự (NCKH) | SV đăng ký vào lab = đăng ký thực tập/sử dụng thiết bị? |
| R19 | "số môn học phụ trách giảng dạy" | Ghi nhận môn học mỗi giảng viên phụ trách | Nhân sự (NCKH) | — |
| R20 | "phục vụ cộng đồng (nội dung, thời gian thực hiện, ai thực hiện, ai là host)" | Ghi nhận hoạt động phục vụ cộng đồng: nội dung + thời gian + người thực hiện + host | Nhân sự (NCKH) | — |

---

## 2. Câu hỏi BẮT BUỘC làm rõ với khách hàng (trước khi viết SRS)

Theo workflow Contract-First, các điểm sau **phải có câu trả lời bằng văn bản** trước khi `/contract` → `/dev`:

### Nhóm A — Phạm vi & nghiệp vụ
1. **A01** — Lab đang/sắp xin công nhận **VILAS theo 17025** hay chỉ "vận hành theo tinh thần 17025"? (quyết định độ chặt của document/record control)
2. **A02** — "Công khai kết quả" (R6): công khai **nội bộ lab** hay khách hàng cũng đăng nhập xem được? (ảnh hưởng có cần portal khách hàng không)
3. **A03** — Hóa chất quản lý theo **lô (lot/batch)** + hạn dùng, hay chỉ tổng theo tên hóa chất? (ảnh hưởng ERD)
4. **A04** — Đơn vị hóa chất: chỉ **gam**, hay đa đơn vị (mg, g, kg, mL, L)?
5. **A05** — "Phiếu" (R5) là **phiếu yêu cầu thử nghiệm** (gắn với mẫu) hay phiếu công việc nội bộ chung?

### Nhóm B — Cơ cấu tổ chức & quyền
6. **B01** — Danh sách **phòng ban** thực tế (để thiết kế scope dữ liệu).
7. **B02** — Vai trò **"Nhận mẫu"** là vị trí riêng hay là một quyền của KTV? Ai được tạo phiếu mẫu?
8. **B03** — Kế toán cần thấy gì? (chỉ chi phí hóa chất, hay cả hóa đơn dịch vụ thử nghiệm?)

### Nhóm C — Hạ tầng & phi chức năng
9. **C01** — Chấp nhận **cloud object storage** (Cloudflare R2 / AWS S3) hay bắt buộc **on-premise/MinIO**? (R11 — "tối ưu giá & thời gian")
10. **C02** — Kênh thông báo cron: **in-app + email** đủ chưa, hay cần **Zalo OA**?
11. **C03** — Số người dùng đồng thời dự kiến? Lượng mẫu/tháng? (để định NFR performance)
12. **C04** — Chu kỳ nâng lương (R12): cố định **3 năm** cho mọi ngạch, hay khác nhau theo ngạch/chức danh?

---

## 3. Quyết định đã CHỐT (KH xác nhận 19/06/2026)

| ID | Quyết định | Cơ sở |
|----|------------|-------|
| ✅ A01 | **Lab ĐÃ được công nhận VILAS theo 17025** → document/record control phải CHẶT: approval workflow tài liệu (draft→review→approved→obsolete) là **P0**, không phải P1 | A01 |
| ✅ A02 | "Công khai" = **nội bộ lab** (không có portal khách hàng) → cắt M1.5.2 | A02 |
| ✅ A03 | Hóa chất quản lý **theo lô (lot/batch)** + hạn dùng + kiểm tra lại | A03 |
| ✅ A04 | Đơn vị hóa chất **tùy loại** (lưu `default_unit` mỗi hóa chất, không hard-code gam) | A04 |
| ✅ A04b | Giao dịch hóa chất **gắn với mẫu** (`ref_sample_id`) là quan hệ chính | R6 + KH |
| ✅ C01 | Lưu trữ file: **MinIO self-host** (chốt, không dùng cloud giai đoạn này) | C01 |
| ✅ C02 | Thông báo: **chỉ in-app notification** (bỏ email/Zalo khỏi P0) | C02 |
| ✅ C03 | Quy mô **~40 người dùng** → NFR nhẹ, không cần scale ngang phức tạp | C03 |
| ✅ C04 | Nâng lương **3 năm/lần cho mọi ngạch** (`salary_cycle_years = 3`) | C04 |
| ✅ AS6 | Mỗi mẫu có **deadline**; trễ hạn bắt buộc nhập lý do | R7, R9 |

### Điểm MỚI phát sinh từ quyết định trên — cần KH lưu ý
- **N1 — Đơn vị tùy loại + cộng tồn:** vì đơn vị khác nhau (g, mg, mL, viên...), tồn kho tính **theo từng lô + theo đơn vị của hóa chất đó**, KHÔNG cộng gộp khác đơn vị. Cột số lượng đổi từ `qty_gram` → `qty` (NUMERIC) + lấy đơn vị từ `chemicals.default_unit`.
- **N2 — VILAS = audit chặt:** mọi thao tác trên tài liệu/kết quả/hóa chất phải ghi `audit_logs` đầy đủ (17025 §8.4). Đây là điều kiện duy trì công nhận, không phải nice-to-have.

---

## 4. Liên kết tới các tài liệu tiếp theo

- `01-demo-scope.md` — Cây module 3 cấp + P0/P1/P2 + RBAC + ERD core + mapping 17025 + cron jobs
- (sau khi KH duyệt scope) → `/ba` viết SRS cho từng submodule P0
- → `/contract <feature>` cho từng submodule
- → `/dev` implement
