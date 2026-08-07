# FRONTEND UX & ACCESSIBILITY AUDIT — LIMS

> Ngày audit: 2026-08-07 · Mã: `FE-U-xx` (UX) · `FE-AC-xx` (accessibility)

---

## 1. Phát hiện UX

### FE-U-01 · 🟠 HIGH — Lỗi API hiển thị thành "không có dữ liệu" ở 48/49 trang

| | |
|---|---|
| **Danh mục** | Loading/Error states — Correctness của thông tin hiển thị |
| **Bằng chứng** | `useAsync` trả `{data, loading, error, reload}`. `grep "const { data, loading, error"` → **1** trang. `grep -rln useAsync src/pages` → **49** trang |

`src/components/ui/States.tsx` export `EmptyState`, `Spinner`, `LoadingState`,
`CardSkeleton`, `TableSkeleton` — **không có `ErrorState`**, và không trang nào tự dựng.

Mẫu lặp lại ở gần như mọi trang (ví dụ `src/pages/Users.tsx:33`, `:118`):

```tsx
const { data, loading, reload } = useAsync(...);   // ← `error` bị bỏ
...
<DataTable rows={data?.data ?? []} loading={loading} />
```

### Chuyện gì xảy ra khi API lỗi

`useAsync` bắt lỗi, đặt `error`, để `data` nguyên `null`, `loading` về `false`.
Trang render `data?.data ?? []` → mảng rỗng → `DataTable` hiện **"Không có dữ liệu"**.

Nghĩa là các tình huống sau **trông giống hệt nhau** với người dùng:

| Thực tế | Người dùng thấy |
|---|---|
| Không có mẫu nào đang chờ | "Không có dữ liệu" |
| Backend trả 500 | "Không có dữ liệu" |
| Mất mạng | "Không có dữ liệu" |
| 403 — không đủ quyền | "Không có dữ liệu" |
| Redis chết → 500 toàn API (xem `docs/SECURITY_AUDIT.md` S-05) | "Không có dữ liệu" |

### Vì sao đây là HIGH chứ không phải "polish"

Đây là hệ thống phòng thử nghiệm. Một KTV mở "Mẫu quá hạn", thấy danh sách trống, và **kết
luận không có mẫu nào quá hạn** — trong khi thật ra API vừa lỗi. Không có tín hiệu nào để
nghi ngờ, không có nút thử lại. Với ISO/IEC 17025, đó là ra quyết định trên thông tin sai
mà hệ thống tự tin trình bày như sự thật.

Trớ trêu: hạ tầng để làm đúng **đã có sẵn và làm rất tốt** — `lib/errors.ts` có bản đồ ~150
mã lỗi → tiếng Việt, ẩn chi tiết 5xx và hiện `correlationId`. Nó chỉ được dùng cho **toast
sau mutation**, không dùng cho **lỗi khi tải trang**.

### Khắc phục

Thêm `ErrorState` vào `States.tsx` và một quy ước dùng chung:

```tsx
// components/ui/States.tsx
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { title, description } = describeError(error);
  return <EmptyState icon={<AlertTriangle/>} title={title} description={description}
                     action={onRetry && <Button onClick={onRetry}>Thử lại</Button>} />;
}

// mọi trang:
const { data, loading, error, reload } = useAsync(...);
if (error) return <ErrorState error={error} onRetry={reload} />;
```

49 trang cần sửa nhưng mỗi trang là 2 dòng. Ưu tiên các trang ra quyết định vận hành:
`SampleRequests`, `SampleFlow`, `Documents`, `Nonconformities`, `Risks`, `Equipment`.

**Ưu tiên: P0**

---

### FE-U-02 · 🟡 MEDIUM — Không có trang 404; mọi URL sai âm thầm về Dashboard

**File:** `src/App.tsx:455`

```tsx
<Route path="*" element={<Navigate to="/dashboard" replace />} />
```

Hệ quả:
- Link cũ/bookmark hỏng (`/samples/sample/<id đã xoá>` gõ sai) → về Dashboard, người dùng
  tưởng mình bấm nhầm.
- Lỗi gõ URL không phân biệt được với "không có quyền".
- Không có cách nào biết đường dẫn nào đang hỏng để báo lỗi.

**Khắc phục:** trang `NotFound` nêu rõ đường dẫn không tồn tại + nút về Dashboard + nút quay
lại. Giữ `replace` để không kẹt lịch sử.

---

### FE-U-03 · 🟡 MEDIUM — Không có xử lý mất mạng / timeout

- `lib/api.ts` **không đặt timeout** (xem FRONTEND_PERFORMANCE FE-P-06) → mất mạng giữa
  chừng làm spinner quay **vô hạn**, không có đường thoát.
- Không có `window.addEventListener('online'/'offline')`, không có banner "Mất kết nối".
- `useAsync` không tự thử lại khi mạng trở lại.

Kết hợp với FE-U-01 (lỗi hiện thành "không có dữ liệu"), trải nghiệm khi Wi-Fi chập chờn
trong phòng lab là: hoặc quay mãi, hoặc báo "không có dữ liệu" sai sự thật.

**Khắc phục tối thiểu:** `AbortSignal.timeout(30_000)` trong `api.ts` + `ErrorState` có nút
"Thử lại" (FE-U-01) đã giải quyết phần lớn. Banner offline là bổ sung.

---

### FE-U-04 · 🔵 LOW — Validate form không đồng nhất

Không dùng thư viện form/schema (FE-A-06). Mỗi form tự kiểm bằng `if`. Kết quả:
- Một số form kiểm trước khi gửi, một số dựa hẳn vào lỗi 400 từ backend rồi hiện toast.
- `Field` có prop `error` nhưng nhiều form không truyền — lỗi hiện ở toast thay vì cạnh ô nhập.

Không phải lỗ hổng (backend luôn validate lại), nhưng người dùng phải đoán ô nào sai.

---

### FE-U-05 · 🔵 LOW — Chặn double-submit có nhưng chưa phủ hết

Đã có: 57 vị trí `disabled={submitting}` / `loading={submitting}` trên nút gửi, và
`apiPost` tự sinh `Idempotency-Key` để lần retry sau `401 → refresh` không tạo bản ghi trùng.

Giới hạn được ghi rõ trong chính comment `api.ts:206-213`: mỗi lần bấm là **một `apiPost`
mới** → **key mới** → idempotency **không chặn được double-click**; chỉ cờ `submitting` chặn.
Trang nào quên cờ đó thì hai cú click nhanh = hai bản ghi.

**Khắc phục đúng:** với các POST tạo bản ghi nghiệp vụ (phiếu nhận mẫu, báo giá, giao dịch
kho), sinh key **một lần** trong `useRef` khi mở form và dùng lại cho mọi lần gửi của form đó.

---

## 2. Hành động phá huỷ — kiểm tra riêng

| Yêu cầu | Trạng thái |
|---|---|
| Có hộp xác nhận | ✅ `ConfirmDialog` dùng ở ≥10 trang (xoá tài liệu, xoá chứng nhận, xoá tệp biểu mẫu…) |
| Cảnh báo rõ ràng | ✅ Nội dung nêu đúng đối tượng bị xoá |
| Trạng thái đang xử lý | ✅ `ConfirmDialog` có prop `loading` |
| Chặn bấm lặp | ✅ qua `loading` |
| Phản hồi thành công | ✅ toast |
| Phản hồi lỗi | ✅ toast qua `describeError` |

**Đây là phần được làm tốt.** Không tìm thấy hành động xoá nào thiếu xác nhận.

---

## 3. Accessibility

### FE-AC-01 · 🟡 MEDIUM — `<label>` không nối với ô nhập (ảnh hưởng MỌI form)

**File:** `src/components/ui/Field.tsx:26-30`

```tsx
{label && (
  <label className="text-sm font-medium text-ink">   {/* ← không có htmlFor */}
    {label}
  </label>
)}
{children}                                            {/* ← input không có id */}
```

`grep -rn "htmlFor" src/` → **0 kết quả** trên 25 `<input>`.

Hệ quả (WCAG 2.1 — 1.3.1 Info & Relationships, 3.3.2 Labels or Instructions):
- Trình đọc màn hình không đọc nhãn khi focus vào ô → người khiếm thị không biết đang nhập gì.
- Bấm vào nhãn không focus ô (mất tiện ích chuột).
- Thông báo lỗi (`<p className="text-xs text-overdue">`) không nối bằng `aria-describedby`,
  không có `aria-invalid`, không có `role="alert"` → lỗi validate **không được thông báo**.

**Khắc phục — một chỗ, phủ toàn bộ form:**

```tsx
export function Field({ label, required, error, hint, children, className }) {
  const id = useId();
  const msgId = `${id}-msg`;
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {label && <label htmlFor={id} className="...">{label}{required && <span aria-hidden>*</span>}</label>}
      {cloneElement(children as ReactElement, {
        id,
        'aria-invalid': error ? true : undefined,
        'aria-describedby': error || hint ? msgId : undefined,
      })}
      {error ? <p id={msgId} role="alert" className="...">{error}</p>
             : hint ? <p id={msgId} className="...">{hint}</p> : null}
    </div>
  );
}
```

Đây là **sửa một file, cải thiện ~30 form** — tỉ lệ lợi ích/công sức cao nhất trong nhóm a11y.

---

### FE-AC-02 · 🔵 LOW — 18 chỗ `<div onClick>`

`grep -rnE "<(div|span)[^>]*onClick" src/` → 18.

**Phần lớn là vô hại**: 15/18 là `<div onClick={(e) => e.stopPropagation()}>` bọc nhóm nút
trong hàng bảng — không phải phần tử tương tác, chỉ chặn nổi bọt sự kiện.

Thực sự cần sửa: `src/pages/Dashboard.tsx:514` — `<div onClick={onClick}>` là một thẻ số
liệu bấm được, không focus được bằng bàn phím, không có `role`.

Con số 18 nghe nhiều nhưng thực tế chỉ **1** vấn đề. Nêu rõ để không sửa nhầm 15 chỗ đúng.

---

### Đã làm ĐÚNG về accessibility

| Hạng mục | Bằng chứng |
|---|---|
| Skip link | ✅ `AppShell.tsx:31-36` — "Bỏ qua điều hướng", có lý do ghi trong comment (sidebar ~50 link) |
| Focus trap | ✅ `lib/useFocusTrap.ts` — đếm tham chiếu, trả focus về phần tử mở, lọc phần tử ẩn qua `offsetParent` |
| Zoom | ✅ `index.html:12` **không** đặt `maximum-scale`/`user-scalable=no`, có comment nêu rõ WCAG 1.4.4 |
| `lang` | ✅ `<html lang="vi">` |
| Landmark | ✅ `<main id="main-content">` |
| aria-* | ✅ 53 chỗ dùng |
| Semantic button | ✅ Có `components/ui/Button.tsx` dùng `<button>` thật, được dùng rộng khắp |

Mức a11y nền tảng **trên trung bình**; khoảng trống lớn duy nhất là FE-AC-01.

---

## 4. Responsive

| Hạng mục | Trạng thái |
|---|---|
| Công cụ kiểm | ✅ `scripts/check-responsive.mjs` — kiểm **bất biến tĩnh**, chạy trong `npm run check`. Mỗi luật tương ứng một lỗi đã từng có thật |
| Tài liệu | ✅ `RESPONSIVE_PLAN.md`, `RESPONSIVE_IMPLEMENTATION.md`, `RESPONSIVE_TESTPLAN.md` |
| Sidebar mobile | ✅ Drawer riêng (`mobileOpen`) + focus trap |
| Safe area iPhone | ✅ `viewport-fit=cover` + `env(safe-area-inset-*)` |
| Breakpoint | ✅ Tailwind chuẩn + `3xl` tuỳ chỉnh cho màn rộng |

**Đây là hạng mục được đầu tư nghiêm túc nhất của frontend** — có kế hoạch, có triển khai,
có test plan, và có script chặn hồi quy trong CI.

**Giới hạn cần nói rõ:** `check-responsive.mjs` là kiểm **tĩnh trên mã nguồn**, không phải
kiểm thật trên thiết bị. Chính docstring của nó ghi: *"Đây KHÔNG thay thế kiểm thử thủ công
trên thiết bị"*. Audit này không có trình duyệt để xác minh → **UNKNOWN** cho hiển thị thực
tế trên tablet/mobile.

---

## 5. Tổng hợp

| ID | Mức | Vấn đề | Vị trí | Ưu tiên |
|---|---|---|---|---|
| FE-U-01 | 🟠 HIGH | Lỗi API hiện thành "không có dữ liệu" ở 48/49 trang | `States.tsx` + `pages/*` | **P0** |
| FE-U-02 | 🟡 MEDIUM | Không có 404, mọi URL sai về Dashboard | `App.tsx:455` | P1 |
| FE-U-03 | 🟡 MEDIUM | Không xử lý mất mạng/timeout → spinner vô hạn | `lib/api.ts` | P1 |
| FE-AC-01 | 🟡 MEDIUM | `<label>` không nối ô nhập, lỗi không được thông báo | `ui/Field.tsx:26` | P1 |
| FE-U-04 | 🔵 LOW | Validate form không đồng nhất | `pages/*` | P2 |
| FE-U-05 | 🔵 LOW | Idempotency-Key không chặn double-click | `lib/api.ts:206` | P2 |
| FE-AC-02 | 🔵 LOW | 1 thẻ bấm được không phải `<button>` | `Dashboard.tsx:514` | P3 |

## 6. Điều làm ĐÚNG

- **Bản đồ ~150 mã lỗi → tiếng Việt** (`lib/errors.ts`), 5xx ẩn chi tiết + hiện correlationId
  8 ký tự để người dùng đọc cho quản trị viên. Hiếm dự án nào làm tới mức này.
- **ConfirmDialog phủ hết hành động phá huỷ**, có trạng thái loading.
- **Skip link + focus trap + không chặn zoom** — ba thứ hay bị bỏ qua nhất.
- **Bộ công cụ responsive có kỷ luật** (plan → implementation → testplan → script CI).
- **`ErrorBoundary` hiện correlationId** để tra log khi UI crash.
