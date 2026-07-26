# Bộ test case Responsive — LIMS Frontend

Đi kèm: `npm run check` (typecheck + `scripts/check-responsive.mjs`).
Tài liệu này phủ phần **script tĩnh không kiểm được**: hành vi thật trên thiết bị.

---

## 0. Chuẩn bị

```bash
npm run check     # typecheck (tsc -b) + 10 luật bất biến responsive
npm run build     # bản production
npm run dev       # http://localhost:5173
```

### Ma trận thiết bị bắt buộc

| # | Thiết bị | Kích thước | Lý do có mặt trong ma trận |
|---|---|---|---|
| D1 | Galaxy S20 | **360×800** | Hẹp nhất thực tế — mọi lưới phải về 1 cột |
| D2 | iPhone SE | 375×667 | **Thấp nhất** — kiểm ngân sách chiều dọc, sheet |
| D3 | iPhone 14 Pro | 393×852 | Notch + home indicator → `env(safe-area-inset-*)` |
| D4 | iPad mini dọc | **768×1024** | Vùng chết cũ → phải thấy **rail sidebar** |
| D5 | iPad Pro ngang | 1366×1024 | Sidebar full + 2 cột |
| D6 | Laptop | **1366×768** | Chiều cao hẹp — kiểm việc bỏ footer cố định |
| D7 | Desktop | 1920×1080 | Mốc `3xl` |
| D8 | 2K | 2560×1440 | Kiểm `max-w` 1760 |

### Đoạn lệnh dán vào DevTools Console

```js
// A. Phát hiện phần tử gây tràn ngang (chạy ở 360px) — kỳ vọng: mảng rỗng
(() => {
  const w = document.documentElement.clientWidth;
  const bad = [...document.querySelectorAll('*')]
    .filter(el => el.getBoundingClientRect().right > w + 1);
  bad.forEach(el => (el.style.outline = '2px solid red'));
  console.log('Tràn ngang:', bad.length, bad);
  return bad.length === 0 ? '✔ PASS' : '✖ FAIL';
})();

// B. Trang không được cuộn ngang — kỳ vọng: true
document.documentElement.scrollWidth <= window.innerWidth;

// C. Liệt kê vùng chạm nhỏ hơn 40px (chạy ở 360px)
[...document.querySelectorAll('button,a[href],[role=button]')]
  .map(el => ({ el, r: el.getBoundingClientRect() }))
  .filter(({ r }) => r.width > 0 && (r.height < 40 || r.width < 40))
  .forEach(({ el, r }) => console.log(Math.round(r.width) + '×' + Math.round(r.height), el));

// D. Đo chiều cao vùng nội dung thực (chạy ở 1366×768)
document.querySelector('main').clientHeight;
```

---

## 1. App Shell

| ID | Thiết bị | Bước | Kỳ vọng |
|---|---|---|---|
| **AS-01** | D6 | Mở `/dashboard`, chạy đoạn D | `main` cao **≥ 600px** (trước refactor ~500px — footer cố định đã ăn mất) |
| **AS-02** | D6 | Cuộn xuống cuối trang | Footer 3 cột chỉ xuất hiện ở cuối luồng cuộn, **không ghim đáy viewport** |
| **AS-03** | D2 | Mở app, kéo cuộn lên/xuống nhanh | Layout **không nhảy** khi thanh URL Safari co giãn (`100dvh`) |
| **AS-04** | D3 | Mở app ở chế độ đứng | Nội dung **không bị notch che**; footer/sheet không đè home indicator |
| **AS-05** | bất kỳ | Tải trang, nhấn `Tab` một lần | Hiện nút **"Bỏ qua điều hướng"** ở góc trên trái; `Enter` → focus nhảy vào `#main-content` |
| **AS-06** | D8 | Mở `/dashboard` | Container rộng tối đa **1760px** (không phải 1400px); viền trống mỗi bên ≤ 400px |
| **AS-07** | D1 | Mở bất kỳ trang nào, chạy đoạn A | **0 phần tử tràn** |

## 2. Sidebar — 3 chế độ

| ID | Thiết bị | Bước | Kỳ vọng |
|---|---|---|---|
| **SB-01** | D4 (768px) | Mở app | **Thấy rail icon 64px** bên trái, không phải chỉ hamburger. Đây là hồi quy chính cần canh. |
| **SB-02** | D4 | Rê chuột lên icon trong rail | Hiện tooltip tên chức năng (thuộc tính `title`) |
| **SB-03** | D4 | Mục có badge (vd Thông báo) | Badge thu thành **chấm tròn** góc trên phải icon, vẫn nhìn thấy |
| **SB-04** | D4 | Bấm nút `⇥` (PanelLeftOpen) ở đầu rail | Mở **drawer đầy đủ** phủ lên; bấm ra ngoài / `Esc` → đóng |
| **SB-05** | D5/D7 | Bấm nút thu gọn ở thanh brand | Sidebar còn **64px icon**, KHÔNG biến mất; mọi mục vẫn bấm được |
| **SB-06** | D7 | Ở chế độ rail, bấm `⇥` | Bung lại full, giữ đúng bề rộng đã kéo trước đó |
| **SB-07** | D7 | Kéo mép phải sidebar | Đổi bề rộng 208–460px; nháy đúp → về 256px; tải lại trang vẫn nhớ |
| **SB-08** | D1 | Bấm hamburger | Drawer trượt vào; **nền không cuộn được**; `Esc` đóng; focus quay về nút hamburger |
| **SB-09** | D1 | Mở drawer, nhấn `Tab` liên tục ~30 lần | Focus **không thoát khỏi drawer** (focus trap) |
| **SB-10** | D1 | Drawer đóng, nhấn `Tab` từ đầu trang | **Không** Tab được vào link trong drawer (`inert`) |
| **SB-11** | D1/D3 (touch) | Chạm vào một mục menu | Nút **★ ghim hiện rõ** (trước đây `opacity-0 group-hover` → chết trên touch) |
| **SB-12** | D1 | Chạm nút ★ | Ghim/bỏ ghim hoạt động, **không** điều hướng sang trang đó |

## 3. DataTable — chế độ thẻ ⭐ *ảnh hưởng 27 trang*

| ID | Thiết bị | Trang | Kỳ vọng |
|---|---|---|---|
| **DT-01** | D1 | `/documents` | Hiện **danh sách thẻ**, không phải bảng; **không cuộn ngang** |
| **DT-02** | D1 | `/documents` | Mỗi thẻ: tiêu đề = Mã/Tiêu đề; 2 dòng `Loại`, `Hiệu lực`; nút **"Xem thêm (3)"** |
| **DT-03** | D1 | Bấm "Xem thêm" | Mở thêm Phòng/Bảo mật/Ngày tạo; **KHÔNG điều hướng sang trang chi tiết** (`stopPropagation`) |
| **DT-04** | D1 | Bấm vào thân thẻ | Điều hướng đúng như bấm dòng bảng ở desktop |
| **DT-05** | D1 | Focus thẻ bằng `Tab`, nhấn `Enter`/`Space` | Điều hướng (thẻ có `role="button"` + `tabIndex`) |
| **DT-06** | D4 (768px) | `/documents` | **Quay lại chế độ bảng** (ngưỡng md) |
| **DT-07** | D5 | Bảng nhiều cột, cuộn ngang | **Cột đầu dính trái**; thấy **gradient mờ** mép phải khi còn nội dung |
| **DT-08** | D5 | Cuộn hết sang phải | Gradient mép phải **biến mất** |
| **DT-09** | D5 | Rê chuột lên một dòng | Ô cột đầu (dính) **đổi màu cùng** phần còn lại của dòng, không lệch |
| **DT-10** | D7 | Bấm header cột có sort | `aria-sort` đổi `none → ascending → descending → none` (kiểm trong Elements) |
| **DT-11** | D1 | Trang có dữ liệu rỗng | Hiện `EmptyState`, không hiện khung bảng trống |
| **DT-12** | D7 | Trang đang tải | Hiện skeleton **có thead** (giữ hành vi cũ) |
| **DT-13** | D1 | Trang đang tải | Hiện `CardSkeleton` (skeleton dạng thẻ), không phải skeleton bảng |
| **DT-14** | D1 | Phân trang | Nút trước/sau **≥36×36px**; thông tin "Hiển thị x–y" xếp trên nút |

> **Trang cần kiểm DT-01…04 tối thiểu:** `/documents` · `/chemicals` · `/equipment` · `/users` · `/risks` · `/nonconformities` · `/test-parameters` · `/sample-requests`

## 4. Modal / bottom-sheet ⭐ *ảnh hưởng 36 chỗ*

| ID | Thiết bị | Bước | Kỳ vọng |
|---|---|---|---|
| **MD-01** | D2 (375×667) | `/test-parameters` → "Thêm chỉ tiêu" | Sheet **trượt lên từ đáy**, bo góc trên, có tay nắm |
| **MD-02** | D2 | Trong sheet đó | **Thấy đồng thời** tiêu đề và 2 nút Hủy/Thêm mà không cần cuộn |
| **MD-03** | D2 | Cuộn nội dung sheet | Header + footer **đứng yên**, chỉ thân cuộn |
| **MD-04** | D2 | 2 nút ở footer | **Chia đôi chiều ngang** đều nhau |
| **MD-05** | D3 | Mở sheet bất kỳ | Nút đáy **không bị home indicator che** (`pb-safe`) |
| **MD-06** | D4 (768px) | Mở modal `size="lg"` (vd `/documents` → Tạo tài liệu) | Modal **không dán sát 2 mép**; chừa lề rõ ràng |
| **MD-07** | bất kỳ | Mở modal, nhấn `Tab` liên tục | Focus **quẩn trong modal**, không ra nền sau |
| **MD-08** | bất kỳ | Mở modal, `Esc` | Đóng, **focus quay về đúng nút đã mở** |
| **MD-09** | bất kỳ | Kiểm Elements của modal | Có `role="dialog"`, `aria-modal="true"`, `aria-labelledby` trỏ tới `<h2>` |
| **MD-10** ⚠ | bất kỳ | Mở một Modal → bên trong mở `ConfirmDialog` → **đóng ConfirmDialog** | **Nền vẫn khoá cuộn** (Modal cha còn mở). *Đây là bug thật của bản cũ.* |
| **MD-11** | bất kỳ | Đóng nốt Modal cha | Cuộn nền **được khôi phục**; `body.style.paddingRight` trả về rỗng |
| **MD-12** | D7 | Mở/đóng modal | Layout nền **không giật ngang** (bù bề rộng thanh cuộn) |

## 5. Form & lưới

| ID | Thiết bị | Trang | Kỳ vọng |
|---|---|---|---|
| **FM-01** | D1 | `/test-parameters` → modal thêm | Mọi `<Input>`/`<Select>` **1 cột, full-width** |
| **FM-02** | D4 (768px) | Cũng modal đó | Chuyển sang **2 cột** |
| **FM-03** | D1 | `/sample-flow` → Tạo phiếu nhận | 3 ô (MST/Người liên hệ/ĐT) xếp **dọc**, không phải 3 cột |
| **FM-04** | D1 | `/quotations` → hàng nhập liệu | Các ô lưới 12 cột **stack full-width** (`col-span-12`) |
| **FM-05** | D1 | `/risks` | Ma trận 5×5 **cuộn ngang riêng**, không làm tràn trang |
| **FM-06** | D1 | Chạy đoạn C ở mọi trang form | Không có control nhập liệu nào < 40px chiều cao |

## 6. Thanh lọc (FilterBar)

| ID | Thiết bị | Trang | Kỳ vọng |
|---|---|---|---|
| **FB-01** | D1 | `/equipment` | Chỉ thấy ô tìm + nút **"Lọc"**; 3 select **không** chiếm 3 dòng |
| **FB-02** | D1 | Chọn 2 filter | Nút hiện **"Lọc (2)"** |
| **FB-03** | D1 | Bấm "Lọc" | Mở sheet có nhãn tiếng Việt cho từng filter |
| **FB-04** | D1 | Trong sheet bấm "Xoá lọc" | Mọi filter về mặc định, sheet đóng, danh sách tải lại |
| **FB-05** | D7 | `/equipment` | Các select **bề rộng đều nhau** (`clamp(150px,18vw,220px)`), không so le |
| **FB-06** | D7 | Bật ≥1 filter | Hiện nút **"Xoá lọc (n)"** |
| **FB-07** | D1 | `/documents`, `/risks`, `/chemicals` | Cùng hành vi FB-01…04 |

## 7. Biểu đồ & màn lớn

| ID | Thiết bị | Trang | Kỳ vọng |
|---|---|---|---|
| **CH-01** | D1 | `/dashboard` | Chart cao **200px**; nhãn trục X **xoay −40°**, không chồng nhau |
| **CH-02** | D1 | Biểu đồ tròn | **Không hiện nhãn** quanh vòng (tránh chồng); tooltip vẫn hoạt động; bán kính nhỏ hơn |
| **CH-03** | D7 | `/dashboard` | Chart cao **280px**, nhãn trục ngang |
| **CH-04** | D7 (1920px) | `/dashboard` | Chart cao **360px**; khối biểu đồ **3 cột** |
| **CH-05** | D1 | `/dashboard` | KPI **2 cột** (≥480px); dưới 480px → 1 cột |
| **CH-06** | D8 (2560px) | `/dashboard` | KPI **5 cột** |
| **CH-07** | D1 | Dashboard có Quick Actions | Hàng nút **cuộn ngang 1 dòng**, không wrap nhiều dòng; không hiện thanh cuộn |

## 8. Bảng thô (không qua DataTable)

| ID | Thiết bị | Trang | Kỳ vọng |
|---|---|---|---|
| **RT-01** | D1 | `/equipment/:id` (lịch sử hiệu chuẩn) | Bảng cuộn ngang **trong khung riêng**, trang không cuộn ngang |
| **RT-02** | D1 | Cuộn ngang bảng đó | **Cột "Ngày hiệu chuẩn" dính trái**, có đường phân cách |
| **RT-03** | D1 | `/chemicals/:id` (2 bảng) | Như RT-01/02 |
| **RT-04** | D1 | `/documents/:id` tab thống kê | Bảng có `min-w` → cuộn được, **không bị bóp nát** (trước đây không có min-w) |
| **RT-05** | D1 | `/reports` bảng chi tiết | Như RT-04 |

## 9. Topbar / Footer / Toast

| ID | Thiết bị | Bước | Kỳ vọng |
|---|---|---|---|
| **TB-01** | D1 | Xem topbar | Cao **56px** (không phải 72px); **ẩn** dòng "Trường Đại học Nông Lâm…"; hiện "Viện CNSH & Môi trường" **đọc trọn vẹn** |
| **TB-02** | D7 | Xem topbar | Cao 72px, hiện đủ 2 dòng tên đầy đủ như thiết kế gốc |
| **TB-03** | D1 | Bấm chuông thông báo | Popup **full-width** neo dưới topbar, không phải hộp 384px bị cắt mép |
| **TB-04** | D1 (touch) | Chạm 1 thông báo trong popup | Nút "Đã đọc/Chưa đọc" **hiện rõ** (không còn phụ thuộc hover) |
| **TB-05** | bất kỳ | Mở popup chuông, nhấn `Esc` | Đóng |
| **TB-06** | bất kỳ | Mở menu người dùng, nhấn `Esc` | Đóng |
| **TB-07** | D5 (1366px) | Xem avatar góc phải | Chỉ avatar (tên hiện từ `xl`); bấm vào → dropdown hiện **đủ tên + email + vai trò** |
| **TB-08** | D1 | Cuộn tới cuối trang | Footer chỉ **1 dòng ~52px** (logo + tên viện + nút "Liên hệ") |
| **TB-09** | D1 | Bấm "Liên hệ" | Bung đầy đủ địa chỉ / SĐT / email / lượt truy cập |
| **TB-10** | D4+ | Cuộn tới cuối trang | Footer **3 cột** như thiết kế gốc |
| **TB-11** | D1 | Kích hoạt một toast (vd lưu thành công) | Toast **full-width** (trừ lề 12px), không phải hộp 384px lệch phải |

## 10. Trang đăng nhập

| ID | Thiết bị | Kỳ vọng |
|---|---|---|
| **LG-01** | D2 (375×667) | Toàn bộ form nằm gọn, không cuộn ngang; logo 64px (không phải 80px) |
| **LG-02** | D1 | Hoạ tiết `Microscope` **ẩn** (trước đây chèn lên form) |
| **LG-03** | D3 | Form không bị notch che (`px-safe`, `py-8`) |
| **LG-04** | D2 | Bàn phím ảo bật lên → vẫn cuộn tới được nút Đăng nhập |

## 11. Khả năng truy cập (chạy 1 lần trên 5 trang đại diện)

Trang đại diện: `/dashboard` · `/documents` · `/documents/:id` · `/sample-flow` · `/login`

| ID | Bước | Kỳ vọng |
|---|---|---|
| **A11Y-01** | `npx @axe-core/cli http://localhost:5173/<trang> --exit` | **0 lỗi** mức `serious` / `critical` |
| **A11Y-02** | `npx lighthouse <trang> --form-factor=mobile` | Điểm Accessibility **≥ 90** |
| **A11Y-03** | Chỉ dùng bàn phím đi hết trang | Focus ring **luôn nhìn thấy**; không có bẫy focus |
| **A11Y-04** | Zoom trình duyệt 200% ở 1280px | **Không mất nội dung**, không cuộn ngang |
| **A11Y-05** | Bật "Giảm chuyển động" ở OS | Sheet/animation gần như tức thì, không nhấp nháy |

## 12. Hồi quy — thứ KHÔNG được đổi

| ID | Kỳ vọng |
|---|---|
| **RG-01** | Không có lời gọi API nào đổi (so `Network` trước/sau trên `/dashboard`, `/documents`) |
| **RG-02** | Bảng màu, animation `sprout`/`sway`, khoảng cách ở desktop **giữ nguyên** |
| **RG-03** | Sidebar: tìm kiếm, ghim, gần đây, gập nhóm, kéo giãn — **hoạt động y như cũ** ở chế độ full |
| **RG-04** | Phân quyền RBAC: nút/menu ẩn-hiện theo vai trò **không đổi** |
| **RG-05** | `npm run build` thành công; kích thước bundle không tăng > 5% |

---

## Bảng ghi kết quả

| Nhóm | Số case | Đạt | Hỏng | Ghi chú |
|---|---:|---:|---:|---|
| 1. App Shell | 7 | | | |
| 2. Sidebar | 12 | | | |
| 3. DataTable | 14 | | | |
| 4. Modal | 12 | | | |
| 5. Form & lưới | 6 | | | |
| 6. FilterBar | 7 | | | |
| 7. Biểu đồ | 7 | | | |
| 8. Bảng thô | 5 | | | |
| 9. Topbar/Footer | 11 | | | |
| 10. Đăng nhập | 4 | | | |
| 11. A11y | 5 | | | |
| 12. Hồi quy | 5 | | | |
| **Tổng** | **95** | | | |

### Case ưu tiên cao nhất nếu thiếu thời gian

`DT-01` · `DT-03` · `DT-07` · `MD-01` · `MD-02` · `MD-10` · `SB-01` · `SB-05` · `AS-01` · `FM-01` · `TB-01`
