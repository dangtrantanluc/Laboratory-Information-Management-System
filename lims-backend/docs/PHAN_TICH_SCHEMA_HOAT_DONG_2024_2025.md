# Phân tích schema — "TỔNG HỢP CÁC HOẠT ĐỘNG NĂM 2024–2025.xlsx"

> **TRẠNG THÁI TRIỂN KHAI** (migration **m23**): schema đã mở rộng + 3 bảng mới đã tạo +
> script import đã chạy được (đã kiểm chứng trên Postgres thật). Xem mục "Đã triển khai" cuối file.


Nguồn: `docs/TỔNG HỢP CÁC HOẠT ĐỘNG NĂM 2024-2025.xlsx` — 4 sheet, **11 bảng con**.
Mục tiêu: lấy field của từng bảng làm **nội dung cho các menu** NCKH / Giảng dạy / Công tác
khác / Phục vụ cộng đồng / Bài báo, và ánh xạ vào model M4 (HR & Research) hiện có
(`app/models/hr.py`) — chỉ rõ field nào **đã có** và field nào **còn thiếu (GAP)**.

Ký hiệu: ✅ đã có trong model · ⚠️ có nhưng khác kiểu/cần chuẩn hoá · ❌ chưa có (cần bổ sung).
Cột `STT` bỏ qua (chỉ là số thứ tự dòng, không lưu DB).

---

## Tổng quan 4 sheet → 5 menu

| Sheet Excel | Bảng con | Menu đích | Model hiện có |
|---|---|---|---|
| **NCKH** | 1. Nhiệm vụ KHCN các cấp | **NCKH → Đề tài/Dự án** | `research_projects` + `project_members` |
| **NCKH** | 2. Công bố tạp chí trong nước | **Bài báo** | `publications` (type=`paper`) + `publication_authors` |
| **NCKH** | 3. Công bố tạp chí quốc tế | **Bài báo** | `publications` (type=`paper`) + `publication_authors` |
| **NCKH** | 4. Báo cáo hội nghị/kỷ yếu | **Bài báo** (loại hội nghị) | `publications` — **cần type mới** |
| **NCKH** | 5. Danh mục hợp đồng | **NCKH → Hợp đồng** | ❌ **chưa có model** |
| **NCKH** | 6. Sáng chế/GPHI/giống | **NCKH → Sở hữu trí tuệ** | `publications` (type=`patent`) |
| **ĐÀO TẠO** | Công tác đào tạo (ĐH) | **Các môn giảng dạy** | `teaching_courses` |
| **CÔNG TÁC KHÁC** | Đảng / Công đoàn / VILAS | **Công tác khác** | ❌ **chưa có model** |
| **PHỤC VỤ CỘNG ĐỒNG** | 1. Phân tích mẫu | **Phục vụ cộng đồng** | ⚠️ 1 phần `community_services` (thực chất là mẫu M1/M2) |
| **PHỤC VỤ CỘNG ĐỒNG** | 2. Cấp GCN lớp ngắn hạn | **Phục vụ cộng đồng** | ❌ **chưa có model** |
| **PHỤC VỤ CỘNG ĐỒNG** | 3. SV tham gia tập huấn | **Phục vụ cộng đồng** | ❌ **chưa có model** |

---

## 1. MENU "NCKH" — Nhiệm vụ / Đề tài / Dự án

Nguồn: NCKH · bảng r7. Ánh xạ `research_projects` + `project_members`.

| Field Excel | Kiểu | Ví dụ | Map → model | TT |
|---|---|---|---|---|
| Tên nhiệm vụ/Dự án | text | "Đánh giá ảnh hưởng của than sinh học…" | `research_projects.title` | ✅ |
| Nhiệm vụ/dự án cấp?? | enum | Cấp cơ sở / Bộ / Bộ GD&ĐT / Cấp Tỉnh / Chương trình | `research_projects.level` (danh mục `research_project_levels`) | ⚠️ cần bổ sung mã danh mục (Tỉnh, Bộ GD&ĐT, Chương trình MTQG) |
| Chủ nhiệm nhiệm vụ/dự án | text (tên người) | "Trịnh Thị Phi Ly" | `research_projects.lead_user_id` | ⚠️ Excel lưu **tên**, model dùng **user_id** → cần map tên↔user, hoặc field `lead_external_name` cho người ngoài |
| Thành viên nhiệm vụ/dự án | list tên (phẩy) | "Lê Nguyễn Thanh Đông, Trần Thị Vân,…" | `project_members` (n-n) | ⚠️ tách chuỗi → nhiều dòng; cần cho phép thành viên ngoài hệ thống |
| Thời gian thực hiện | khoảng năm | "2023-2025" | `start_date` / `end_date` | ⚠️ Excel là chuỗi "YYYY-YYYY" → tách 2 mốc |
| Kinh phí | tiền (chuỗi) | "100 triệu", "120 triệu" | ❌ **chưa có** `budget_amount` (NUMERIC) + `currency` | ❌ **GAP** |
| Chuyển giao? | bool | (Có/Không) | ❌ **chưa có** `is_transferred` | ❌ **GAP** |
| Tên sản phẩm chuyển giao | text | | ❌ **chưa có** `transfer_product` | ❌ **GAP** |
| Link minh chứng | url | | dùng `attachments` (owner_type mới `research_project`) | ⚠️ hiện chưa gắn attachment cho project |

**Đề xuất bổ sung `research_projects`:** `budget_amount NUMERIC(14,2)`, `budget_currency`,
`is_transferred BOOL`, `transfer_product TEXT`, `lead_external_name` (chủ nhiệm ngoài HT).

---

## 2. MENU "BÀI BÁO" — 3 loại công bố

Gộp 3 bảng con NCKH (r21 trong nước, r40 quốc tế, r54 hội nghị) → `publications` +
`publication_authors`. Đây là phần **khác biệt lớn nhất** so với model hiện tại.

### 2a. Field chung 3 loại

| Field Excel | Kiểu | Map → `publications` | TT |
|---|---|---|---|
| Tên bài báo / báo cáo | text | `title` | ✅ |
| Tên tạp chí / kỷ yếu / hội nghị | text | `journal` | ✅ (đổi ngữ nghĩa cho hội nghị) |
| Năm công bố / báo cáo | int | `year` | ✅ |
| Tác giả/đồng tác giả (vai trò) | enum: "Tác giả liên hệ" / "ĐTG" / "TG" | `publication_authors.is_corresponding` + **role mới** | ⚠️ cần field `author_role` (main/co/corresponding) |
| Tên các thành viên | list tên (phẩy) | `publication_authors` (n-n) | ⚠️ tách chuỗi; nhiều tác giả ngoài HT → `external_name` |
| Link minh chứng | url | `attachments` (owner_type=`publication`) | ✅ |

### 2b. Field riêng — Tạp chí quốc tế (r40)

| Field Excel | Kiểu | Map | TT |
|---|---|---|---|
| SCIE/SSCI | free-text ("SCIE", "SCIE/SSCI", "SCOPUS") | ❌ **chưa có** `is_scie/is_ssci` | ❌ **GAP** |
| Scopus | dấu "X"/"x" | ❌ **chưa có** `is_scopus BOOL` | ❌ **GAP** |
| ACI | dấu | ❌ **chưa có** `is_aci BOOL` | ❌ **GAP** |

> Dữ liệu chỉ mục **rất bẩn** (lẫn "SCOPUS" vào cột SCIE/SSCI, "X"/"x") → khi import phải
> chuẩn hoá về **các cờ boolean** `is_scie, is_ssci, is_scopus, is_aci`.

### 2c. Field riêng — Loại công bố

Hiện `publications.type` chỉ có `paper | patent`. Cần thêm giá trị **`conference`** (báo cáo
hội nghị/kỷ yếu) và có thể phân biệt `domestic/international` cho paper.

**Đề xuất bổ sung `publications`:** `pub_scope` (`domestic|international`), `is_scie`,
`is_ssci`, `is_scopus`, `is_aci` (BOOL); mở rộng CHECK `type` thêm `conference`; thêm
`author_role` vào `publication_authors`.

---

## 3. MENU "NCKH" — Hợp đồng & Sở hữu trí tuệ (2 bảng còn lại NCKH)

### 3a. Danh mục hợp đồng (r74) — ❌ **CHƯA CÓ MODEL**

| Field Excel | Kiểu | Ví dụ |
|---|---|---|
| Tên hợp đồng | text | "PHÂN TÍCH MẪU ĐẤT (BÙN)…" |
| Loại hợp đồng | enum | Nghiên cứu / Tư vấn KHCN / Tư vấn chuyển giao |
| Giá trị hợp đồng | NUMERIC | 110000000, 120000000 |
| Đơn vị phối hợp | text | "CC1" |
| Thời gian thực hiện | date/khoảng | 2025-03-01 (datetime) |
| Link minh chứng | url | |

**Đề xuất model mới `research_contracts`:** `title, contract_type (enum), value_amount
NUMERIC(14,2), currency, partner_org, start_date, end_date, department_id` + attachment.

### 3b. Sáng chế / GPHI / Giống (r83) → `publications` type=`patent`

| Field Excel | Map → `publications` | TT |
|---|---|---|
| Tên sáng chế/GPHI/giống | `title` | ✅ |
| Số bằng | `patent_no` | ✅ |
| Cơ quan cấp văn bằng | `issuing_authority` | ✅ |
| Số đơn, ngày nộp đơn | ❌ `application_no`, `application_date` | ❌ **GAP** |
| Ngày cấp văn bằng | ❌ `granted_date` | ❌ **GAP** |
| Chủ bằng | ❌ `patent_holder` | ❌ **GAP** |
| Tác giả | `publication_authors` | ✅ |

**Đề xuất bổ sung `publications`:** `application_no`, `application_date DATE`,
`granted_date DATE`, `patent_holder` (dùng khi type=`patent`).

---

## 4. MENU "CÁC MÔN GIẢNG DẠY"

Nguồn: ĐÀO TẠO r6–7 (header 2 tầng, có merge). Ánh xạ `teaching_courses`.

| Field Excel | Kiểu | Ví dụ | Map → `teaching_courses` | TT |
|---|---|---|---|---|
| Họ tên | text (giảng viên) | "Nguyễn Công Mạnh" | `user_id` | ⚠️ Excel lưu tên → map user_id |
| Tên môn học được phân công | text | "Kỹ thuật phân tích mẫu nước" | `course_name` | ✅ |
| Số tiết HKI — Lý thuyết | int | 15 | ❌ `hk1_theory_hours` | ❌ **GAP** |
| Số tiết HKI — Thực hành | int | 30 | ❌ `hk1_practice_hours` | ❌ **GAP** |
| Số tiết HKII — Lý thuyết | int | 120 | ❌ `hk2_theory_hours` | ❌ **GAP** |
| Số tiết HKII — Thực hành | int | 30 | ❌ `hk2_practice_hours` | ❌ **GAP** |
| Ghi chú | text | | ❌ `note` | ❌ **GAP** |
| Link minh chứng (TKB) | url | | attachment | ⚠️ |

> Model hiện chỉ có `course_name, semester, year` — **thiếu toàn bộ số tiết** (4 field
> LT/TH × 2 học kỳ). Đây là dữ liệu định lượng chính của menu Giảng dạy.

**Đề xuất bổ sung `teaching_courses`:** `hk1_theory_hours, hk1_practice_hours,
hk2_theory_hours, hk2_practice_hours` (SmallInteger), `note`. (Bỏ `semester` đơn lẻ hoặc
giữ để phân biệt năm học.)

---

## 5. MENU "CÔNG TÁC KHÁC" — ❌ **CHƯA CÓ MODEL**

Nguồn: CÔNG TÁC KHÁC — **3 bảng con cùng cấu trúc**: Công tác Đảng / Công đoàn / VILAS.

| Field Excel | Kiểu | Map |
|---|---|---|
| (Nhóm công tác) | enum | Đảng / Công đoàn / VILAS — lấy từ **tiêu đề bảng con** |
| HOẠT ĐỘNG | text | nội dung hoạt động |
| Link minh chứng | url | attachment |

**Đề xuất model mới `other_activities`:** `category (enum: dang|cong_doan|vilas|khac),
content TEXT, performer_user_id, department_id` + attachment. (Cấu trúc gần giống
`community_services` — có thể **gộp chung** một bảng `staff_activities` với cột `kind`.)

---

## 6. MENU "PHỤC VỤ CỘNG ĐỒNG" — 3 bảng khác nhau

Nguồn: PHỤC VỤ CỘNG ĐỒNG. **Lưu ý:** 3 bảng con **không đồng nhất** — chỉ bảng 3 (tập
huấn) đúng nghĩa "phục vụ cộng đồng"; bảng 1 & 2 thực ra là nghiệp vụ khác.

### 6a. Công tác phân tích mẫu (r6) — ⚠️ thực chất là **M1/M2 (mẫu)**, không phải M4
| Field | Map |
|---|---|
| Mã mẫu | `samples.sample_code` (M1) |
| Đơn vị gửi mẫu | `customers` / `test_requests` |
| Số lượng | số mẫu |
| Chỉ tiêu | chỉ tiêu thử nghiệm |

> **Khuyến nghị:** không đưa vào menu Phục vụ cộng đồng — đây là dịch vụ phân tích mẫu,
> thuộc M1 (Sample) + hợp đồng (§3a). Nếu muốn thống kê "phục vụ cộng đồng" thì tổng hợp
> **read-only** từ M1.

### 6b. Cấp GCN lớp ngắn hạn (r14) — ❌ **CHƯA CÓ MODEL**
| Field Excel | Kiểu |
|---|---|
| Ngày tháng | date |
| Số GCN | text (mã chứng nhận) |
| Tên người được cấp GCN | text |
| Lớp học | text |
| Ghi chú | text |

**Đề xuất model mới `training_certificates`:** `issued_date, certificate_no, recipient_name,
course_name, note, host_user_id, department_id`.

### 6c. SV tham gia tập huấn (r19) → gần với `community_services` / `student_mentorships`
| Field | Map → `community_services` | TT |
|---|---|---|
| Nội dung tập huấn | `content` | ✅ |
| Thời gian | `performed_at` | ✅ |
| Đơn vị tổ chức | `host` | ✅ |
| Người thực hiện | `performer_user_id` | ✅ |

> `community_services` (content/performed_at/host/performer_user_id) **đủ** cho bảng 6c.

---

## 7. Vấn đề chung khi import từ Excel này

1. **Tên người là chuỗi, không phải user_id** — mọi cột "Chủ nhiệm / Thành viên / Họ tên /
   Tác giả" đều ghi tên tự do → cần bảng map tên↔user, và **cho phép người ngoài hệ thống**
   (`external_name`) như `publication_authors` đã làm.
2. **Danh sách thành viên gộp 1 ô, phân tách bằng dấu phẩy** → tách thành nhiều dòng n-n.
3. **Dữ liệu bẩn:** chỉ mục tạp chí lẫn lộn ("SCOPUS" nằm ở cột SCIE), "X"/"x", "Kinh phí"
   là chuỗi "100 triệu" → chuẩn hoá về boolean/NUMERIC khi nhập.
4. **Header 2 tầng + merge** (ĐÀO TẠO: HKI/HKII × LT/TH; sheet nhiều bảng con) → parser phải
   theo từng vùng, không đọc 1 header phẳng.
5. **Link minh chứng** ở mọi bảng → thống nhất dùng `attachments` (thêm owner_type
   `research_project`, `research_contract`, `teaching_course`, `other_activity`,
   `training_certificate`).

---

## 8. Tóm tắt GAP schema cần bổ sung (theo độ ưu tiên)

| # | Đối tượng | Thay đổi | Menu |
|---|---|---|---|
| 1 | `publications` | +`pub_scope`, +`is_scie/is_ssci/is_scopus/is_aci`, +type `conference`; +`author_role` (bảng authors) | Bài báo |
| 2 | `teaching_courses` | +4 cột số tiết (HKI/HKII × LT/TH) + `note` | Giảng dạy |
| 3 | `research_projects` | +`budget_amount/currency`, +`is_transferred`, +`transfer_product`, +`lead_external_name` | NCKH |
| 4 | **model mới** `research_contracts` | Hợp đồng KHCN (giá trị, loại, đối tác, thời gian) | NCKH |
| 5 | **model mới** `other_activities` (hoặc gộp `staff_activities`) | Đảng/Công đoàn/VILAS | Công tác khác |
| 6 | `publications` (patent) | +`application_no/date`, +`granted_date`, +`patent_holder` | NCKH/SHTT |
| 7 | **model mới** `training_certificates` | Cấp GCN lớp ngắn hạn | Phục vụ cộng đồng |
| 8 | `attachments` | +owner_type cho project/contract/teaching/other/certificate | tất cả |

> Các mục 5 (Phân tích mẫu) không cần model mới — tổng hợp read-only từ M1/hợp đồng.

---

## 9. ĐÃ TRIỂN KHAI (migration m23 + import script)

### Schema (migration `1718870400022_m23_activities_2024_2025.py` — đã test up/down/up trên PG thật)
- `research_projects`: +`lead_external_name`, `academic_year`, `budget_amount`, `budget_currency`,
  `is_transferred`, `transfer_product`; `lead_user_id` → nullable + CHECK lead-present.
- `project_members`: PK đổi sang `id`, +`external_name` (thành viên ngoài HT, XOR user_id),
  unique index (project_id,user_id) cho thành viên nội bộ.
- `publications`: +`pub_scope`, `is_scie/is_ssci/is_scopus/is_aci`, `academic_year`,
  `application_no/date`, `granted_date`, `patent_holder`; `type` += `conference`.
- `publication_authors`: +`author_role`.
- `teaching_courses`: +`academic_year`, `hk1/hk2_theory/practice_hours`, `note`.
- **Bảng mới**: `research_contracts`, `staff_activities`, `training_certificates`.
- `attachments`: mở owner_type cho 5 loại mới.

### Import (`scripts/import_activities_2024_2025.py` — dry-run + ghi thật)
```bash
# Xem trước (không ghi):
python scripts/import_activities_2024_2025.py --file "docs/TỔNG HỢP...xlsx" --dry-run
# Ghi thật:
DATABASE_URL=... python scripts/import_activities_2024_2025.py --file "..." --academic-year 2024-2025
```
Kết quả kiểm chứng (PG thật, DB test 1 user): 7 đề tài · 33 công bố (17 paper + 16 hội nghị)
· 4 hợp đồng · 20 dòng giảng dạy. Làm sạch đúng: `100 triệu`→100000000, chỉ mục
SCIE/Scopus/SSCI từ ô bẩn, vai trò tác giả (corresponding/co/main), tách thành viên.
Helper làm sạch có 15 unit test (`app/tests/services/test_activity_import.py`).

> Lưu ý: 2 bảng con **Công tác khác** và **Cấp GCN** trong file nguồn HIỆN CHƯA có dữ liệu
> (chỉ có header) → import 0 dòng (đúng). Giảng dạy chỉ ghi khi giảng viên khớp user nội bộ
> (FK NOT NULL) — chạy trên DB thật có đủ nhân sự sẽ vào đủ.

### CHƯA làm (bước tiếp theo — Phase 3 & 5)
- **API + RBAC** cho 3 bảng mới (contracts/staff_activities/training_certificates) và mở rộng
  serializer research/publications/teaching để trả field mới.
- **Frontend** 5 menu.
