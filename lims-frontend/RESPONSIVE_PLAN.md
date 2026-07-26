# Phân tích UI/UX & Kế hoạch Responsive — LIMS Frontend

> Khảo sát: React 18 + Vite 5 + TypeScript + Tailwind 3.4 + react-router 6 + recharts + lucide.
> Quy mô: 53 trang, 13 UI primitives, ~25.5k LOC.
> Ngày lập: 2026-07-26

---

## Phần I — Hiện trạng đo được

### 1. Mật độ breakpoint (đếm trên toàn bộ `src/**/*.tsx`)

| Prefix | Số lần dùng | Nhận xét |
|---|---:|---|
| `sm:` (≥640) | 126 | Gánh gần như toàn bộ logic responsive |
| `md:` (≥768) | **4** | Gần như không tồn tại |
| `lg:` (≥1024) | 66 | Chủ yếu để ẩn/hiện sidebar |
| `xl:` (≥1280) | **0** | Không tối ưu màn lớn |
| `2xl:` (≥1536) | **0** | Không tối ưu màn lớn |

**Kết luận:** hệ thống thực chất chỉ có **2 trạng thái layout** — `<640px` và `≥1024px`. Vùng 640–1024px (iPad portrait 768, tablet Android, cửa sổ chia đôi màn hình laptop) là **vùng chết**: sidebar đã bị ẩn (`lg:`) nhưng nội dung vẫn dùng lưới 2 cột bật từ `sm:`.

### 2. Nợ kỹ thuật responsive đếm được

| Vấn đề | Số lượng | File ảnh hưởng |
|---|---:|---:|
| `grid grid-cols-2/3` **không có prefix responsive** | 20 | 15 |
| `col-span-2` (vỡ khi lưới về 1 cột) | 89 | — |
| `max-w-[NNNpx]` cứng trên `<Select>` trong thanh lọc | 37 | ~15 |
| `<table>` với `min-w-[640px]`…`min-w-[760px]` | 7 | 7 |
| Trang dùng `DataTable` (đều scroll ngang trên mobile) | 27 | 27 |
| Modal `size="lg"` (`max-w-3xl` = 768px) | 21 | — |
| Trang **không có bất kỳ breakpoint nào** | 17 | 17 |
| Nút `size="sm"` (h-8 = 32px, dưới ngưỡng chạm 44px) | 95 | — |
| `useMediaQuery` / `matchMedia` | **0** | — |

### 3. Trang hoàn toàn chưa responsive

```
ActivityReports · Login · HrProfileDetail · ResearchContracts · TrainingCertificates
Customers · Notifications · Departments · RiskDetail · AuditLogs · SampleFlow
TestParameters · ChangePassword · StaffActivities · Improvements · SampleRequests
dashboards/DashCharts
```

---

## Phần II — Đánh giá UI/UX

### ✅ Điểm mạnh (nền tảng tốt, đừng đập đi)

1. **Design token đúng chuẩn** — màu định nghĩa qua CSS variable dạng `R G B` trong `:root`, map vào Tailwind với `<alpha-value>`. Đổi theme / thêm dark mode gần như miễn phí.
2. **Hệ primitive gọn và nhất quán** — `Button` / `Field` / `Card` / `Modal` / `DataTable` / `PageHeader` / `Badge` / `States`. Nghĩa là **80% việc fix responsive nằm trong ~6 file**, không phải 53 trang.
3. **Bảng màu "Botanical" có bản sắc**, tương phản chữ trắng trên primary ~5.2:1 (đạt AA).
4. **Đã tôn trọng `prefers-reduced-motion`** trong `index.css` — hiếm dự án nội bộ làm.
5. **Sidebar giàu tính năng cho power-user**: tìm chức năng, ghim (favorites), gần đây, gập nhóm, kéo giãn độ rộng — đều persist theo user vào localStorage. Rất phù hợp ERP/LIMS.
6. **Micro-interaction có chủ đích** (`sprout`, `sway`, stagger 45ms trên KPI) chứ không copy bừa.

### ⚠️ Vấn đề UI/UX (không phụ thuộc màn hình)

| # | Vấn đề | Vị trí | Tác động |
|---|---|---|---|
| U1 | **Ngân sách chiều dọc bị đốt** — Topbar 72px + Footer 3 cột (~110px) đều `shrink-0` nằm ngoài vùng cuộn. Trên laptop 1366×768 vùng nội dung thực chỉ còn ~500px. | `AppShell.tsx:28-48`, `Footer.tsx` | Cao |
| U2 | **Footer sai vị trí kiến trúc** — footer thông tin liên hệ/lượt truy cập được ghim cố định đáy viewport mọi trang. Đây là nội dung *website*, không phải *ứng dụng*. | `AppShell.tsx:46` | Cao |
| U3 | **Thu gọn sidebar = xoá sidebar** (`lg:w-0`), không có icon-rail. Người dùng mất hoàn toàn khả năng điều hướng nhanh, phải bấm nút mũi tên nổi ở `left-0 top-20`. | `Sidebar.tsx:212`, `194-203` | Cao |
| U4 | **Nút ghim ★ chết trên thiết bị cảm ứng** — `opacity-0 group-hover:opacity-100`, không có trạng thái hiện trên touch. | `Sidebar.tsx:527-529` | TB |
| U5 | Tương tự: nút "Đã đọc/Chưa đọc" trong popup thông báo cũng `opacity-0 group-hover`. | `Topbar.tsx:222` | TB |
| U6 | **Modal không trap focus, không trả focus về trigger, không `aria-labelledby`**. Chỉ có ESC. | `Modal.tsx` | Cao (a11y) |
| U7 | **Dropdown Topbar không đóng bằng ESC**, không `role="menu"`, không điều hướng bằng phím mũi tên. | `Topbar.tsx:104-109, 253-258` | TB (a11y) |
| U8 | **Không có skip-link** "Bỏ qua điều hướng"; sidebar có ~50 link phải Tab qua mỗi trang. | `AppShell.tsx` | TB (a11y) |
| U9 | Ô tìm trong sidebar **không có `<label>`/`aria-label`**. | `Sidebar.tsx:246` | Thấp |
| U10 | **Không có dark mode** dù hạ tầng token đã sẵn sàng 100%. | `index.css` | Cơ hội |
| U11 | Thanh lọc dùng `flex flex-wrap` + `max-w-[NNNpx]` cứng → **wrap lệch, chiều rộng không đều**, không có nút "Xoá bộ lọc", không hiện số filter đang bật. | 15 trang danh sách | TB |
| U12 | `DataTable` `pageSize` mặc định 8, các trang truyền 12 — nhưng **không cho người dùng đổi số dòng/trang**, không có tổng số trang nhảy nhanh. | `DataTable.tsx:33` | Thấp |
| U13 | Header bảng `sticky top-0` nhưng **container cuộn là `main`**, không phải wrapper bảng → sticky không hoạt động như mong đợi khi cuộn dọc trang. | `DataTable.tsx:73` | TB |

---

## Phần III — Phân tích responsive theo từng kích thước

### 📱 `<640px` — Điện thoại (360 / 390 / 414)

**Mức độ: hỏng nặng.**

- **20 chỗ lưới 2–3 cột cứng** không có prefix. Ví dụ `pages/TestParameters.tsx:246` — form modal `grid-cols-2` trên màn 360px: mỗi cột ≈ 150px sau khi trừ padding modal → `<Select>` và `<Input>` bị bóp nát, text overflow.
  Các file nặng nhất: `SampleFlow.tsx` (7 chỗ), `TestParameters`, `Chemicals`, `RiskDetail`, `ResearchContracts`, `TrainingCertificates`, `StaffActivities`, `Forms`, `DocumentDetail`, `Equipment`, `Nonconformities`, `ChemicalDetail`.
- **Mọi bảng đều cuộn ngang** (`min-w-[640px]`), 27 trang. Không có shadow gợi ý còn nội dung bên phải, cột đầu tiên không `sticky` → cuộn ngang là mất ngữ cảnh dòng đang xem. Đây là trải nghiệm tệ nhất của hệ thống trên mobile.
- **37 `<Select>` bị `max-w-[NNNpx]`** trong thanh lọc → trên mobile không giãn full-width, xếp so le xấu.
- **Modal**: `p-4` + `my-8` + `max-h-[70vh]` body + footer không sticky → trên màn cao 640px, vùng nhập liệu thực còn ~380px, người dùng phải cuộn cả 2 lớp. Cần chuyển sang **bottom-sheet toàn màn hình**.
- **Topbar 72px** hiển thị "Trường Đại học Nông Lâm TP. Hồ Chí Minh" + "Viện Nghiên cứu Công nghệ Sinh học và Môi trường" — cả hai đều `truncate`, trên 360px chỉ đọc được vài chữ đầu. **Chiếm 11% chiều cao màn hình mà không truyền tải thông tin.**
- **Footer 3 cột → 1 cột dọc ~300px**, render dưới mọi trang, cực kỳ lãng phí.
- `PageHeader` `actions` = `flex items-center gap-2` không wrap → 3 nút (`Chờ duyệt` / `Thống kê` / `Tạo tài liệu` ở `Documents.tsx:100`) tràn ngang.
- **`h-screen` sai trên iOS Safari** (thanh URL co giãn) — cần `100dvh`.
- **Không có `viewport-fit=cover`** và không xử lý `env(safe-area-inset-*)` → nội dung chạm notch / home-indicator trên iPhone.
- Vùng chạm: nút phân trang 28×28px, nút ★ ~14px, `Button size="sm"` 32px — đều dưới khuyến nghị 44px.

### 📱 `640–767px` — Điện thoại ngang / phone lớn

**Mức độ: chật.**

- `sm:grid-cols-2` bật ngay tại 640px. Trong modal `max-w-xl` (576px), 2 cột nghĩa là **mỗi cột ~250px** — quá hẹp cho `<Select>` tiếng Việt ("Được công nhận VILAS", tên phòng lab dài).
- `DescList` (`sm:grid-cols-2`) và `KpiGrid` (`sm:grid-cols-2`) cùng bật ở đây.
- **Đề xuất then chốt: dời ngưỡng 2 cột từ `sm:` lên `md:`.**

### 💻 `768–1023px` — iPad dọc / tablet / cửa sổ chia đôi

**Mức độ: vùng chết — tệ nhất tương đối.**

- Sidebar bị ẩn hoàn toàn (điều kiện `lg:`) → mất điều hướng dù màn hình thừa chỗ cho icon-rail 64px.
- Chỉ có **4 lần dùng `md:`** trong toàn bộ codebase → không có bất kỳ xử lý riêng nào cho dải này.
- Modal `size="lg"` = `max-w-3xl` (768px) + `p-6` → **rộng hơn viewport**, dán sát mép hai bên.
- Bảng `min-w-[640px]`–`min-w-[760px]` vừa khít hoặc tràn.
- Dashboard: `lg:grid-cols-2` chưa bật → biểu đồ xếp 1 cột toàn chiều rộng 768px với `height={280}` cố định → tỉ lệ khung hình rất dẹt, khó đọc.

### 🖥 `1024–1279px` — Laptop nhỏ

**Mức độ: chấp nhận được.**

- Sidebar 256px (kéo giãn được 208–460px) + `max-w-[1400px]` + `px-8` → vùng nội dung ~700px.
- Bảng 6+ cột bắt đầu cuộn ngang.
- Thanh lọc 4 `<Select>` wrap xuống 2 hàng.
- Nếu người dùng kéo sidebar lên 460px → nội dung còn ~500px, bảng vỡ nhưng không có cơ chế tự bảo vệ.

### 🖥 `1280–1535px` — Desktop chuẩn

**Mức độ: tốt nhất.** Đây rõ ràng là kích thước hệ thống được thiết kế cho.

### 🖥 `≥1536px` — Màn lớn / 2K / 4K

**Mức độ: lãng phí.**

- `max-w-[1400px]` chốt cứng → trên 2560px có **~580px viền trắng mỗi bên**.
- `KpiGrid` dừng ở `lg:grid-cols-4` — trên 2560px mỗi thẻ KPI rộng ~340px chỉ để hiển thị 1 con số.
- Biểu đồ vẫn `height={280}` cố định.
- Dashboard `lg:grid-cols-2` không lên 3 cột.
- **0 lần dùng `xl:` / `2xl:`** trong toàn dự án.

---

## Phần IV — Kế hoạch triển khai

### Nguyên tắc nền

1. **Sửa ở primitive trước, sweep trang sau.** ~80% lỗi nằm trong 6 file dùng chung.
2. **Dời ngưỡng "2 cột" từ `sm:` (640) lên `md:` (768).** Một quyết định, sửa được cảm giác chật ở cả dải 640–768.
3. **Mobile-first**: mặc định 1 cột, full-width; mọi thứ nhiều cột phải có prefix.
4. **Không đập lại design system** — giữ nguyên token màu, animation, cấu trúc Sidebar.

### Thang breakpoint đề xuất

```js
// tailwind.config.js — theme.extend.screens
screens: {
  xs: '480px',   // thêm: phone lớn
  // sm: 640  (mặc định)
  // md: 768  ← NGƯỠNG 2 CỘT MỚI
  // lg: 1024 ← ngưỡng hiện sidebar (giữ nguyên)
  // xl: 1280
  // 2xl: 1536
  '3xl': '1920px', // thêm: màn lớn
}
```

| Dải | Tên | Layout mục tiêu |
|---|---|---|
| 0–479 | Phone nhỏ | 1 cột · Bảng → thẻ · Modal → bottom-sheet · Topbar rút gọn · Footer thu gọn |
| 480–767 | Phone lớn / phone ngang | 1 cột · KPI 2 cột · Bảng → thẻ |
| 768–1023 | Tablet | 2 cột · **Icon-rail sidebar 64px** · Bảng cuộn ngang có sticky cột 1 · Modal ≤ 92vw |
| 1024–1279 | Laptop | Sidebar đầy đủ · 2 cột · Bảng đầy đủ |
| 1280–1919 | Desktop | Sidebar + 3–4 cột KPI · max-w 1400 |
| ≥1920 | Màn lớn | max-w 1760 · KPI 5–6 cột · Dashboard 3 cột · Chart cao 340–380px |

---

### 🔹 Giai đoạn 0 — Nền tảng (0.5 ngày)

| # | Việc | File |
|---|---|---|
| 0.1 | Thêm `xs`, `3xl` vào `screens`; thêm plugin `container-queries` (tùy chọn) | `tailwind.config.js` |
| 0.2 | `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">` | `index.html` |
| 0.3 | Utility `.h-dvh-screen { height: 100dvh }` + fallback `100vh`; utility `.pb-safe`, `.pt-safe`, `.px-safe` dùng `env(safe-area-inset-*)` | `src/index.css` |
| 0.4 | Hook `useMediaQuery(query)` + `useBreakpoint()` trả `'xs'\|'sm'\|'md'\|'lg'\|'xl'\|'2xl'` (SSR-safe, dùng `matchMedia` + `addEventListener('change')`) | `src/lib/useMediaQuery.ts` (mới) |
| 0.5 | Ma trận thiết bị kiểm thử chuẩn: 360×640, 390×844, 414×896, 768×1024, 820×1180, 1024×768, 1366×768, 1440×900, 1920×1080, 2560×1440 | `README` |
| 0.6 | Tăng vùng chạm toàn cục ở thiết bị thô: `@media (pointer: coarse) { button, a, [role=button] { min-height: 40px } }` — hoặc xử lý ở `Button` (mục 2.4) | `src/index.css` |

---

### 🔹 Giai đoạn 1 — App Shell (1.5 ngày) — *tác động lớn nhất*

| # | Việc | File | Chi tiết |
|---|---|---|---|
| 1.1 | Đổi `h-screen` → `h-[100dvh]` | `AppShell.tsx:28` | Sửa lỗi iOS Safari |
| 1.2 | **Chuyển `Footer` vào trong `<main>`** (cuối luồng cuộn), bỏ khỏi flex column cố định | `AppShell.tsx:37-46` | Trả lại ~110px chiều cao viewport cho mọi trang |
| 1.3 | Footer: `<640px` chỉ hiện logo + tên viện + link "Liên hệ ▾" (accordion); cột "Lượt truy cập" ẩn dưới `sm` | `Footer.tsx` | |
| 1.4 | **Icon-rail sidebar**: thay `lg:w-0` bằng `lg:w-16` — chỉ icon + tooltip khi hover, badge vẫn hiện | `Sidebar.tsx:212` | Giữ điều hướng khi thu gọn |
| 1.5 | **Bật rail mặc định ở dải `md`** (768–1023) thay vì ẩn hẳn: đổi điều kiện `lg:` → `md:` cho `<aside>` + `md:w-16`, mở rộng full từ `lg:` | `Sidebar.tsx:205-213` | Lấp vùng chết tablet |
| 1.6 | Mobile drawer chuẩn: khoá cuộn `body`, **focus trap**, đóng bằng `ESC`, trả focus về nút hamburger | `Sidebar.tsx`, `AppShell.tsx` | a11y |
| 1.7 | Nút ★ ghim: thêm `@media (pointer: coarse) → opacity-100`, tăng vùng chạm lên 32×32 | `Sidebar.tsx:518-533` | Sửa U4 |
| 1.8 | Topbar `<sm`: ẩn dòng "Trường Đại học Nông Lâm…", chỉ giữ logo + "Viện CNSH & Môi trường" 1 dòng; giảm chiều cao `h-14 sm:h-[72px]` | `Topbar.tsx:21-48` | Trả 16px + hết truncate vô nghĩa |
| 1.9 | Popup thông báo: `<sm` chuyển sang full-width sheet (`fixed inset-x-2 top-16`) thay vì `w-96 absolute right-0` | `Topbar.tsx:182` | |
| 1.10 | UserMenu `<lg`: hiện tên/vai trò trong dropdown (hiện đang `hidden lg:block` cả ở trigger) — đảm bảo người dùng mobile vẫn biết đang đăng nhập bằng tài khoản nào | `Topbar.tsx:266-273` | |
| 1.11 | Thêm skip-link `Bỏ qua điều hướng → #main` | `AppShell.tsx` | a11y U8 |
| 1.12 | Container: `max-w-[1400px]` → `max-w-[1400px] 3xl:max-w-[1760px]`; padding `px-3 sm:px-4 lg:px-8` | `AppShell.tsx:41` | |

---

### 🔹 Giai đoạn 2 — Primitives (2.5 ngày) — *đòn bẩy cao nhất*

#### 2.1 `DataTable` → chế độ thẻ trên mobile ⭐ **ưu tiên #1**

Ảnh hưởng **27 trang** chỉ với 1 file.

```ts
export interface Column<T> {
  // ...giữ nguyên
  /** Ưu tiên hiển thị khi thu hẹp: 1 = luôn hiện, 2 = từ md, 3 = từ lg */
  priority?: 1 | 2 | 3;
  /** Dùng làm tiêu đề thẻ ở chế độ mobile card */
  primary?: boolean;
}

interface DataTableProps<T> {
  // ...
  /** 'card' (mặc định) = <md đổi sang danh sách thẻ; 'scroll' = giữ bảng cuộn ngang */
  mobileMode?: 'card' | 'scroll';
  pageSizeOptions?: number[];
}
```

- `<md`: render danh sách thẻ — cột `primary` làm tiêu đề, các cột `priority: 1` làm dòng `label — value`, phần còn lại ẩn sau nút "Xem thêm". Mỗi thẻ vẫn nhận `onRowClick`.
- `≥md` giữ nguyên bảng, nhưng bổ sung:
  - cột đầu `sticky left-0 bg-surface` khi cuộn ngang,
  - shadow gradient bên phải khi còn nội dung (`onScroll` → state),
  - sửa `sticky top-0` của `<thead>` (mục U13) bằng cách đặt `max-h` + `overflow-y-auto` cho wrapper bảng, hoặc bỏ sticky nếu không dùng.
- Phân trang: `<sm` xếp dọc, thêm chọn số dòng/trang.

#### 2.2 `Modal` → bottom-sheet trên mobile ⭐ **ưu tiên #2**

Ảnh hưởng **36 chỗ dùng**.

- `<sm`: `fixed inset-x-0 bottom-0 top-auto max-h-[92dvh] rounded-t-2xl rounded-b-none` + animation trượt lên; padding `pb-safe`.
- `≥sm`: giữ nguyên hành vi hiện tại nhưng `max-w-3xl` → `w-[min(92vw,48rem)]`.
- Body: `max-h-[70vh]` → `max-h-[calc(92dvh-8.5rem)] sm:max-h-[70vh]`.
- **Footer sticky** đáy sheet (hiện đang nằm cuối luồng).
- Thêm **focus trap** + `aria-labelledby` + trả focus về trigger (sửa U6).

#### 2.3 `FormGrid` — primitive mới

Thay thế 20 chỗ `grid grid-cols-2/3` cứng:

```tsx
// src/components/ui/FormGrid.tsx
export function FormGrid({ cols = 2, children, className }: {
  cols?: 2 | 3; children: ReactNode; className?: string;
}) {
  return (
    <div className={cn(
      'grid grid-cols-1 gap-4',
      cols === 2 ? 'md:grid-cols-2' : 'sm:grid-cols-2 lg:grid-cols-3',
      className,
    )}>{children}</div>
  );
}
// kèm helper class: FormGrid.full = 'md:col-span-2' (thay col-span-2 trần)
```

> ⚠️ 89 chỗ `col-span-2` phải rà: khi lưới về 1 cột trên mobile, `col-span-2` là vô hại; nhưng phải đổi thành `md:col-span-2` để không dính khi cấu hình lưới thay đổi.

#### 2.4 `Button` — vùng chạm

- `SIZES.sm`: `h-8` → `h-9 sm:h-8` (36px trên mobile).
- `SIZES.md`: `h-10` → `h-11 sm:h-10` (44px trên mobile).
- Thêm `size="icon"` chuẩn 40×40 cho các nút chỉ có icon.

#### 2.5 `FilterBar` — primitive mới

Thay thế pattern `flex flex-wrap items-center gap-3 border-b border-hairline p-4` lặp ở **15 trang**:

```tsx
<FilterBar
  search={<SearchInput ... />}
  filters={[<Select .../>, <Select .../>]}
  activeCount={n}
  onClear={() => ...}
/>
```

- `<md`: search full-width; các filter thu vào nút **"Bộ lọc (2)"** mở sheet từ dưới lên.
- `≥md`: lưới `grid-cols-[minmax(0,1fr)_repeat(auto-fit,minmax(160px,200px))]` — bỏ toàn bộ 37 `max-w-[NNNpx]` cứng, chiều rộng đều nhau.
- Nút "Xoá bộ lọc" + đếm filter đang bật (sửa U11).

#### 2.6 `PageHeader`

- `actions`: thêm `flex-wrap` + `w-full sm:w-auto`; `<sm` nút primary full-width, các nút phụ gom vào menu "⋯".
- Tiêu đề `text-xl` → `text-lg sm:text-xl`.
- Ẩn hoạ tiết lá thứ 2 dưới `sm` (đã làm) — kiểm lại hoạ tiết 1 `h-36 w-36` có tràn trên 360px không.

#### 2.7 `DescList`

- `sm:grid-cols-2` → `md:grid-cols-2 2xl:grid-cols-3`; `DescItem.full` → `md:col-span-2 2xl:col-span-3`.

---

### 🔹 Giai đoạn 3 — Sweep 53 trang (3–4 ngày)

Chia 4 lô, làm theo thứ tự tác động:

**Lô A — 20 chỗ lưới cứng (nửa ngày, sửa lỗi vỡ layout mobile)**
`SampleFlow` (7 chỗ: L258,263,270,392,401,746,986,997,1009) · `TestParameters:246` · `Chemicals:262` · `RiskDetail:225` · `ResearchContracts:180` · `TrainingCertificates:130` · `StaffActivities:146` · `Forms:432` · `DocumentDetail:591` · `Equipment:399` · `Nonconformities:355` · `ChemicalDetail:538`
→ thay bằng `<FormGrid>`, đổi `col-span-2` → `md:col-span-2`.

**Lô B — 15 trang danh sách (1 ngày)**
Áp `FilterBar` + khai báo `priority`/`primary` cho cột `DataTable`:
`Documents · Chemicals · Equipment · Users · Risks · Nonconformities · TestParameters · SampleRequests · Publications · ResearchProjects · Forms · ActivityReports · LabRegistrations · Customers · TrainingCertificates`

**Lô C — 8 trang chi tiết (1 ngày)**
`SampleDetail · DocumentDetail · EquipmentDetail · ChemicalDetail · RiskDetail · NonconformityDetail · HrProfileDetail · SampleRequestDetail`
→ tab/section xếp dọc `<md`; các `<table>` thô (7 file) bọc `overflow-x-auto` + sticky cột 1 + shadow gợi ý; thanh hành động xếp dọc `<sm`.

**Lô D — trang đặc thù (1–1.5 ngày)**
- `SampleFlow.tsx` (~1000 dòng, phức tạp nhất) — luồng nhiều bước, cần thiết kế riêng cho mobile (stepper dọc).
- `MonthlyReport.tsx` — thanh sticky đáy (`L431`) cần `pb-safe`, form dài cần section thu gọn.
- `Reports.tsx` — `grid-cols-5` (L135) → `grid-cols-2 md:grid-cols-3 xl:grid-cols-5`.
- `Login.tsx` / `ChangePassword.tsx` — `max-w-md` đã ổn, chỉ cần `min-h-[100dvh]` + `px-safe` + hạ kích thước logo 20→16 dưới `sm`.
- `Notifications` · `AuditLogs` · `Departments` · `Improvements` — chuẩn hoá theo Lô B.

---

### 🔹 Giai đoạn 4 — Màn lớn & Dashboard (0.5–1 ngày)

| # | Việc |
|---|---|
| 4.1 | `KpiGrid`: `grid-cols-1 xs:grid-cols-2 lg:grid-cols-4 3xl:grid-cols-5` |
| 4.2 | Dashboard: `lg:grid-cols-2` → `lg:grid-cols-2 3xl:grid-cols-3` (9 file dashboard) |
| 4.3 | Chart: `height={280}` cố định → `height` theo breakpoint qua `useBreakpoint()` (220 mobile / 280 desktop / 360 ở 3xl); `XAxis` xoay nhãn `-35°` + `interval="preserveStartEnd"` khi hẹp; `Legend` ẩn dưới `sm` |
| 4.4 | `PieChart` (`QmsDashboard`): giảm `outerRadius` dưới `sm`, chuyển legend xuống dưới |
| 4.5 | `QuickActions`: `<sm` cuộn ngang 1 hàng (`overflow-x-auto snap-x`) thay vì wrap nhiều hàng |

---

### 🔹 Giai đoạn 5 — A11y & QA (1 ngày)

| # | Việc |
|---|---|
| 5.1 | Focus trap cho `Modal` + `ConfirmDialog` + drawer sidebar (dùng chung 1 hook `useFocusTrap`) |
| 5.2 | ESC + `role="menu"` + điều hướng phím mũi tên cho 2 dropdown Topbar |
| 5.3 | `aria-label` cho ô tìm sidebar, các nút icon-only, `aria-live` cho toast |
| 5.4 | Kiểm tra tương phản toàn bộ token ở cả nền `plate` và `surface` (đặc biệt `text-stem` `#52564C` trên `#F6F7F1`) |
| 5.5 | Chạy axe DevTools + Lighthouse mobile trên 10 trang đại diện |
| 5.6 | Kiểm thử tay theo ma trận thiết bị (mục 0.5); test cả zoom 200% trên desktop |
| 5.7 | Kiểm tra `prefers-reduced-motion` vẫn đúng sau khi thêm animation sheet |

### 🔹 Giai đoạn 6 — Tuỳ chọn (nếu có thời gian)

- **Dark mode** — hạ tầng token đã 100% sẵn sàng, chỉ cần thêm `:root[data-theme=dark]` với 14 biến + nút toggle trong `Settings`. Ước tính 0.5 ngày, giá trị cảm nhận rất cao.
- **Container queries** cho `Card` — để card tự thích nghi theo chiều rộng vùng chứa thay vì viewport (hữu ích khi sidebar kéo giãn 208–460px).
- **Bảo vệ khi kéo sidebar rộng**: khi `width > 380px` và viewport `< 1440px`, tự động cảnh báo hoặc giới hạn.

---

## Phần V — Tổng hợp công sức & thứ tự ưu tiên

| GĐ | Nội dung | Ngày | Tác động |
|---|---|---:|---|
| 0 | Nền tảng | 0.5 | Bắt buộc |
| 1 | App Shell | 1.5 | 🔴 Rất cao |
| 2 | Primitives | 2.5 | 🔴 Rất cao |
| 3 | Sweep 53 trang | 3.5 | 🟠 Cao |
| 4 | Màn lớn & chart | 1.0 | 🟡 TB |
| 5 | A11y & QA | 1.0 | 🟠 Cao |
| **Tổng** | | **~10 ngày công** | |
| 6 | Dark mode (tuỳ chọn) | +0.5 | 🟢 Bonus |

### Nếu chỉ có 3 ngày — làm đúng 5 việc này (được ~70% giá trị)

1. **`DataTable` → chế độ thẻ mobile** (mục 2.1) — sửa 27 trang bằng 1 file.
2. **`Modal` → bottom-sheet** (mục 2.2) — sửa 36 chỗ bằng 1 file.
3. **20 chỗ lưới cứng → `FormGrid`** (Lô A) — hết vỡ form trên mobile.
4. **Footer vào luồng cuộn + `100dvh` + Topbar rút gọn `<sm`** (1.1–1.3, 1.8).
5. **Icon-rail sidebar bật từ `md`** (1.4–1.5) — lấp vùng chết tablet.

---

## Phụ lục — Checklist review cho mỗi trang sau khi sửa

- [ ] Ở 360px: không có thanh cuộn ngang ở cấp trang (`document.body.scrollWidth <= innerWidth`)
- [ ] Ở 360px: mọi `<Input>`/`<Select>` rộng ≥ 260px hoặc full-width
- [ ] Ở 360px: mọi nút bấm được có vùng chạm ≥ 40×40px
- [ ] Ở 768px: nội dung dùng 2 cột, không phải 1 cột kéo dài
- [ ] Ở 1920px: nội dung không bị co về giữa với viền trống > 400px/bên
- [ ] Bảng: hoặc là thẻ, hoặc cuộn ngang có sticky cột 1 + gợi ý cuộn
- [ ] Modal: mở được, cuộn được, nút Lưu/Huỷ luôn nhìn thấy ở 360×640
- [ ] Tab-only: đi hết trang được, focus ring luôn nhìn thấy, không bẫy focus
- [ ] Zoom 200% ở 1280px: không mất nội dung
