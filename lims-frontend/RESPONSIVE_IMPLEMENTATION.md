# Spec triển khai Responsive — LIMS Frontend

> Tài liệu thi công. Phân tích hiện trạng xem [RESPONSIVE_PLAN.md](./RESPONSIVE_PLAN.md).
> Mỗi task có: **ID · file · thay đổi chính xác · code · tiêu chí nghiệm thu (DoD) · giờ công · phụ thuộc**.

---

## 0. Quy ước chung

### 0.1 Nhánh & commit

```
main
 └── feat/responsive
      ├── feat/responsive-p0-foundation     → PR #1  (T0.*)
      ├── feat/responsive-p1-shell          → PR #2  (T1.*)
      ├── feat/responsive-p2-primitives     → PR #3  (T2.*)  ⭐ PR lớn nhất
      ├── feat/responsive-p3a-grids         → PR #4  (T3A.*)
      ├── feat/responsive-p3b-lists         → PR #5  (T3B.*)
      ├── feat/responsive-p3c-details       → PR #6  (T3C.*)
      ├── feat/responsive-p3d-special       → PR #7  (T3D.*)
      ├── feat/responsive-p4-largescreen    → PR #8  (T4.*)
      └── feat/responsive-p5-a11y           → PR #9  (T5.*)
```

Commit prefix: `resp(scope): mô tả` — vd `resp(datatable): thêm chế độ thẻ dưới md`.

### 0.2 Definition of Done cho **mọi** PR

- [ ] `npm run lint` (`tsc --noEmit`) sạch — **0 lỗi**
- [ ] `npm run build` thành công
- [ ] Kiểm tay ở **360px** và **768px** cho mọi trang bị chạm
- [ ] `document.documentElement.scrollWidth <= window.innerWidth` ở 360px (không cuộn ngang cấp trang)
- [ ] Không thay đổi hành vi nghiệp vụ / không đổi API gọi backend
- [ ] Không đổi token màu, animation hiện có

### 0.3 Snippet kiểm tra nhanh trong DevTools Console

```js
// Phát hiện phần tử gây tràn ngang — chạy ở 360px
[...document.querySelectorAll('*')]
  .filter(el => el.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
  .forEach(el => { el.style.outline = '2px solid red'; console.log(el); });
```

---

## 1. Bảng tổng hợp task

| ID | Task | File chính | Giờ | Phụ thuộc | Ưu tiên |
|---|---|---|---:|---|:--:|
| **T0.1** | Mở rộng `screens` + keyframe `slide-up` | `tailwind.config.js` | 0.5 | — | 🔴 |
| **T0.2** | `viewport-fit=cover` | `index.html` | 0.1 | — | 🔴 |
| **T0.3** | Utility `dvh` / `safe-area` / `no-scrollbar` / touch target | `index.css` | 1.0 | — | 🔴 |
| **T0.4** | Hook `useMediaQuery` + `useBreakpoint` | `lib/useMediaQuery.ts` ✨ | 1.0 | — | 🔴 |
| **T0.5** | Hook `useFocusTrap` + `useBodyScrollLock` | `lib/useFocusTrap.ts` ✨ | 1.5 | — | 🔴 |
| **T0.6** | Codemod `sm:` → `md:` cho grid/col-span (102 token) | 30 file | 1.0 | T0.1 | 🔴 |
| **T1.1** | `100dvh` + skip-link + container `3xl` | `AppShell.tsx` | 0.5 | T0.3 | 🔴 |
| **T1.2** | Đưa `Footer` vào luồng cuộn | `AppShell.tsx` | 0.3 | — | 🔴 |
| **T1.3** | Footer thu gọn `<md` | `Footer.tsx` | 1.0 | T0.6 | 🟠 |
| **T1.4** | Sidebar: icon-rail (thay `lg:w-0`) | `Sidebar.tsx` | 3.0 | T0.4 | 🔴 |
| **T1.5** | Sidebar: rail mặc định ở dải `md` | `Sidebar.tsx`, `AppShell.tsx` | 1.5 | T1.4 | 🔴 |
| **T1.6** | Mobile drawer: scroll-lock + focus trap + ESC | `Sidebar.tsx` | 1.0 | T0.5 | 🟠 |
| **T1.7** | Nút ★ hiện trên touch | `Sidebar.tsx` | 0.3 | T0.3 | 🟠 |
| **T1.8** | Topbar rút gọn `<sm` | `Topbar.tsx` | 1.0 | — | 🔴 |
| **T1.9** | Popup thông báo → sheet `<sm` | `Topbar.tsx` | 0.7 | T0.4 | 🟠 |
| **T1.10** | UserMenu hiện danh tính `<lg` | `Topbar.tsx` | 0.3 | — | 🟡 |
| **T2.1** | ⭐ `DataTable` → chế độ thẻ + sticky col + scroll hint | `DataTable.tsx` | 6.0 | T0.4 | 🔴🔴 |
| **T2.2** | ⭐ `Modal` → bottom-sheet + focus trap + footer sticky | `Modal.tsx` | 4.0 | T0.1,T0.5 | 🔴🔴 |
| **T2.3** | `FormGrid` + `FormRow` | `ui/FormGrid.tsx` ✨ | 1.0 | — | 🔴 |
| **T2.4** | `Button` vùng chạm + `size="icon"` | `Button.tsx` | 0.5 | — | 🟠 |
| **T2.5** | `FilterBar` + sheet lọc mobile | `ui/FilterBar.tsx` ✨ | 4.0 | T2.2,T0.4 | 🔴 |
| **T2.6** | `PageHeader` actions wrap + overflow menu | `PageHeader.tsx` | 1.5 | T2.4 | 🟠 |
| **T2.7** | `DescList` md/2xl | `DescList.tsx` | 0.2 | T0.6 | 🟠 |
| **T2.8** | `Toast` full-width `<sm` + `aria-live` | `ToastContext.tsx` | 0.5 | — | 🟡 |
| **T2.9** | `TableSkeleton` khớp chế độ thẻ | `States.tsx` | 0.5 | T2.1 | 🟡 |
| **T3A** | 20 lưới cứng → `FormGrid` (12 file) | pages | 4.0 | T2.3 | 🔴 |
| **T3B** | 15 trang danh sách → `FilterBar` + `priority` cột | pages | 8.0 | T2.1,T2.5 | 🔴 |
| **T3C** | 8 trang chi tiết + 7 `<table>` thô | pages | 8.0 | T2.1 | 🟠 |
| **T3D** | 4 trang đặc thù (`SampleFlow`, `MonthlyReport`, `Reports`, auth) | pages | 10.0 | T3A | 🟠 |
| **T4.1** | `KpiGrid` + 9 dashboard lên `3xl` | dashboards | 1.5 | T0.6 | 🟡 |
| **T4.2** | Chart cao theo breakpoint + trục/legend thích ứng | `DashCharts.tsx` +2 | 3.0 | T0.4 | 🟡 |
| **T4.3** | `QuickActions` cuộn ngang snap `<sm` | `DashKit.tsx` | 0.5 | — | 🟢 |
| **T5.1** | Focus trap cho `ConfirmDialog`, dropdown Topbar | 2 file | 1.5 | T0.5 | 🟠 |
| **T5.2** | `aria-label` icon-only, label ô tìm sidebar | nhiều | 1.0 | — | 🟠 |
| **T5.3** | QA ma trận thiết bị + axe + Lighthouse | — | 4.0 | tất cả | 🔴 |
| **T6.1** | *(tuỳ chọn)* Dark mode | `index.css`, `Settings.tsx` | 4.0 | — | 🟢 |

**Tổng: ~80 giờ ≈ 10 ngày công** (chưa tính T6).

---

## 2. Giai đoạn 0 — Nền tảng

### T0.1 — `tailwind.config.js`

Thêm vào `theme.extend`:

```js
screens: {
  xs: '480px',
  // sm 640 · md 768 · lg 1024 · xl 1280 · 2xl 1536 (mặc định)
  '3xl': '1920px',
},
```

Thêm vào `theme.extend.keyframes` (cho bottom-sheet ở T2.2):

```js
'slide-up': {
  from: { transform: 'translateY(100%)' },
  to:   { transform: 'translateY(0)' },
},
'slide-down': {
  from: { transform: 'translateY(-8px)', opacity: '0' },
  to:   { transform: 'translateY(0)', opacity: '1' },
},
```

Và `theme.extend.animation`:

```js
'slide-up': 'slide-up 0.24s cubic-bezier(0.16, 1, 0.3, 1)',
'slide-down': 'slide-down 0.18s ease-out',
```

**DoD:** `npx tailwindcss -i src/index.css -o /dev/null` không cảnh báo; class `3xl:grid-cols-5` sinh ra được.

---

### T0.2 — `index.html`

```diff
- <meta name="viewport" content="width=device-width, initial-scale=1.0" />
+ <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
```

> ⚠️ Không thêm `maximum-scale=1` hoặc `user-scalable=no` — vi phạm WCAG 1.4.4.

---

### T0.3 — `src/index.css`

Thêm vào `@layer utilities`:

```css
@layer utilities {
  /* Chiều cao viewport đúng trên iOS Safari (thanh URL co giãn) */
  .h-screen-dvh { height: 100vh; height: 100dvh; }
  .min-h-screen-dvh { min-height: 100vh; min-height: 100dvh; }
  .max-h-sheet { max-height: 92vh; max-height: 92dvh; }

  /* Safe area — notch / home indicator iPhone */
  .pt-safe { padding-top: env(safe-area-inset-top, 0px); }
  .pb-safe { padding-bottom: env(safe-area-inset-bottom, 0px); }
  .px-safe {
    padding-left: env(safe-area-inset-left, 0px);
    padding-right: env(safe-area-inset-right, 0px);
  }
  .mb-safe { margin-bottom: env(safe-area-inset-bottom, 0px); }

  /* Cuộn ngang không hiện thanh cuộn (dùng cho tab bar / quick actions) */
  .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
  .no-scrollbar::-webkit-scrollbar { display: none; }

  /* Bóng gợi ý "còn nội dung bên phải" cho bảng cuộn ngang */
  .scroll-hint-r {
    -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 24px), transparent 100%);
            mask-image: linear-gradient(to right, #000 calc(100% - 24px), transparent 100%);
  }
}
```

Thêm vào `@layer base`:

```css
/* Vùng chạm tối thiểu trên thiết bị cảm ứng (WCAG 2.5.8 + khuyến nghị iOS 44px) */
@media (pointer: coarse) {
  button:not(.tap-exempt),
  [role='button']:not(.tap-exempt),
  a[href]:not(.tap-exempt) {
    min-height: 40px;
  }
}

/* Hiện các nút "chỉ hover" trên thiết bị cảm ứng */
@media (hover: none) {
  .touch-visible { opacity: 1 !important; }
}
```

> **Lưu ý:** `min-height: 40px` toàn cục có thể phá vỡ nút inline nhỏ (vd nút ★ trong sidebar, nút ✕ trong toast). Dùng class `tap-exempt` để loại trừ, hoặc — an toàn hơn — **bỏ rule toàn cục này và chỉ tăng ở `Button` (T2.4)**. Quyết định khi review PR #1.

**DoD:** ở iPhone Simulator, nội dung không chạm notch; `h-screen-dvh` không nhảy khi cuộn.

---

### T0.4 — `src/lib/useMediaQuery.ts` ✨ file mới

```ts
import { useEffect, useState } from 'react';

/** Theo dõi một media query. Trả false ở lần render đầu nếu chưa có window. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(query).matches : false,
  );

  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = (e: MediaQueryListEvent) => setMatches(e.matches);
    setMatches(mql.matches); // đồng bộ lại phòng khi query đổi
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [query]);

  return matches;
}

/** Các ngưỡng khớp với tailwind.config.js — sửa ở đây phải sửa cả bên kia. */
export const BP = {
  xs: 480,
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
  '3xl': 1920,
} as const;

export type BreakpointKey = keyof typeof BP;

/** true khi viewport >= ngưỡng. `useUp('md')` ⇔ Tailwind `md:` */
export function useUp(bp: BreakpointKey): boolean {
  return useMediaQuery(`(min-width: ${BP[bp]}px)`);
}

/** true khi viewport < ngưỡng. `useDown('md')` ⇔ "dưới md" */
export function useDown(bp: BreakpointKey): boolean {
  return useMediaQuery(`(max-width: ${BP[bp] - 0.02}px)`);
}

/** Thiết bị cảm ứng (không có con trỏ chính xác). */
export function useCoarsePointer(): boolean {
  return useMediaQuery('(pointer: coarse)');
}

/** Người dùng bật "giảm chuyển động" ở hệ điều hành. */
export function useReducedMotion(): boolean {
  return useMediaQuery('(prefers-reduced-motion: reduce)');
}
```

> **Nguyên tắc dùng:** ưu tiên class Tailwind (`md:grid-cols-2`) vì không tốn re-render.
> Chỉ dùng hook khi cần **đổi cấu trúc DOM** (bảng ↔ thẻ) hoặc **giá trị JS** (chiều cao chart).

**DoD:** resize cửa sổ qua ngưỡng 768px → component dùng `useUp('md')` re-render đúng 1 lần.

---

### T0.5 — `src/lib/useFocusTrap.ts` ✨ file mới

```ts
import { useEffect, type RefObject } from 'react';

const FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

/**
 * Giam focus trong `ref` khi `active`. Khi đóng, trả focus về phần tử đã mở.
 * Dùng cho Modal, ConfirmDialog, drawer sidebar, sheet bộ lọc.
 */
export function useFocusTrap(ref: RefObject<HTMLElement>, active: boolean) {
  useEffect(() => {
    if (!active || !ref.current) return;
    const root = ref.current;
    const prevActive = document.activeElement as HTMLElement | null;

    // Focus phần tử đầu tiên (bỏ qua nút Đóng nếu có phần tử khác)
    const first = root.querySelectorAll<HTMLElement>(FOCUSABLE)[0];
    (first ?? root).focus?.();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== 'Tab') return;
      const items = [...root.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
        (el) => el.offsetParent !== null, // bỏ phần tử ẩn
      );
      if (items.length === 0) return;
      const firstEl = items[0];
      const lastEl = items[items.length - 1];
      if (e.shiftKey && document.activeElement === firstEl) {
        e.preventDefault();
        lastEl.focus();
      } else if (!e.shiftKey && document.activeElement === lastEl) {
        e.preventDefault();
        firstEl.focus();
      }
    }

    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      prevActive?.focus?.();
    };
  }, [ref, active]);
}

/** Khoá cuộn `body` khi overlay mở, có đếm tham chiếu để lồng nhiều lớp. */
let lockCount = 0;
export function useBodyScrollLock(active: boolean) {
  useEffect(() => {
    if (!active) return;
    if (lockCount === 0) {
      const sbw = window.innerWidth - document.documentElement.clientWidth;
      document.body.dataset.prevOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      if (sbw > 0) document.body.style.paddingRight = `${sbw}px`; // chống giật layout
    }
    lockCount++;
    return () => {
      lockCount--;
      if (lockCount === 0) {
        document.body.style.overflow = document.body.dataset.prevOverflow ?? '';
        document.body.style.paddingRight = '';
        delete document.body.dataset.prevOverflow;
      }
    };
  }, [active]);
}
```

> ⚠️ **Quan trọng:** `Modal.tsx` hiện đang tự set `document.body.style.overflow = 'hidden'` (dòng 27). Phải **gỡ dòng đó** và dùng `useBodyScrollLock` để tránh xung đột khi mở modal lồng modal (`ConfirmDialog` bên trong một `Modal`).

**DoD:** mở modal → Tab chỉ chạy trong modal; Esc đóng → focus quay về nút đã bấm mở. Mở `ConfirmDialog` từ trong `Modal` → đóng dialog, body vẫn khoá cuộn.

---

### T0.6 — Codemod `sm:` → `md:` (102 token, 30 file)

**Lý do:** 640px chia 2 cột là quá chật cho tiếng Việt trong modal `max-w-xl` (mỗi cột ~250px).

**Phạm vi chính xác:**

| Token | Số lần | Đổi thành |
|---|---:|---|
| `sm:grid-cols-2` | 31 | `md:grid-cols-2` |
| `sm:grid-cols-3` | 6 | `md:grid-cols-3` |
| `sm:grid-cols-4` | 2 | `md:grid-cols-4` |
| `sm:col-span-*` | 63 | `md:col-span-*` |
| **Tổng** | **102** | |

**Lệnh:**

```bash
cd lims-frontend/src
grep -rl "sm:grid-cols\|sm:col-span" --include="*.tsx" . \
  | xargs sed -i 's/\bsm:grid-cols-/md:grid-cols-/g; s/\bsm:col-span-/md:col-span-/g'
```

**Ngoại lệ — KHÔNG đổi 3 chỗ sau** (đổi lại thủ công sau khi chạy sed):

| File | Vị trí | Lý do giữ `sm:` |
|---|---|---|
| `pages/dashboards/DashKit.tsx:93` | `KpiGrid` | KPI chỉ là số + nhãn ngắn → 2 cột ở 640px vẫn đọc tốt. Đổi thành `xs:grid-cols-2` (480px) — xem T4.1 |
| `pages/Dashboard.tsx:195` | Lưới KPI | Như trên |
| `pages/Reports.tsx:304` | `grid-cols-2 sm:grid-cols-4` StatCard | Đã mobile-first đúng, chỉ nâng lên `md:grid-cols-4` |

**KHÔNG đụng** các `sm:` khác (`sm:flex-row`, `sm:items-center`, `sm:px-5`, `sm:text-*`, `sm:block`, `sm:h-12`) — 24 token, đều đúng ngữ nghĩa.

**DoD:** `grep -r "sm:grid-cols\|sm:col-span" src/` chỉ còn 3 chỗ ngoại lệ đã liệt kê; build sạch; kiểm mắt 5 trang ở 700px thấy 1 cột (trước đó là 2).

---

## 3. Giai đoạn 1 — App Shell

### T1.1 + T1.2 — `AppShell.tsx`

Thay toàn bộ khối `return` (dòng 27–49):

```tsx
return (
  <div className="flex h-screen-dvh overflow-hidden bg-plate">
    {/* T1.11 — skip-link: hiện khi Tab lần đầu */}
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[100]
                 focus:rounded-lg focus:bg-blueberry focus:px-4 focus:py-2
                 focus:text-sm focus:font-medium focus:text-white focus:shadow-pop"
    >
      Bỏ qua điều hướng
    </a>

    <Sidebar
      collapsed={collapsed}
      onToggle={() => setCollapsed((c) => !c)}
      mobileOpen={mobileOpen}
      onMobileClose={() => setMobileOpen(false)}
    />

    <div className="flex min-w-0 flex-1 flex-col">
      <Topbar onMobileMenu={() => setMobileOpen(true)} />

      {/* T1.2 — Footer chuyển VÀO trong main: cuộn cùng nội dung,
          trả lại ~110px chiều cao viewport cho mọi trang */}
      <main id="main-content" className="flex flex-1 flex-col overflow-y-auto scrollbar-thin">
        <div
          key={location.pathname}
          className="mx-auto w-full max-w-[1400px] flex-1 animate-page-in px-3 py-4 sm:px-4 sm:py-6 lg:px-8 3xl:max-w-[1760px]"
        >
          <Outlet />
        </div>
        <Footer />
      </main>
    </div>
  </div>
);
```

Và dòng 19 (màn hình loading):

```diff
- <div className="flex h-screen items-center justify-center bg-plate">
+ <div className="flex h-screen-dvh items-center justify-center bg-plate">
```

**DoD:**
- Ở 1366×768, vùng nội dung tăng từ ~500px lên ~610px (đo bằng DevTools).
- Footer chỉ thấy khi cuộn xuống cuối trang.
- Tab lần đầu trên trang bất kỳ → hiện nút "Bỏ qua điều hướng", Enter → focus vào `#main-content`.

---

### T1.3 — `Footer.tsx` thu gọn dưới `md`

Thay `<div className="relative grid gap-x-10 gap-y-4 px-4 py-3.5 text-xs lg:grid-cols-[...] lg:px-8">` bằng cấu trúc 2 chế độ:

```tsx
<div className="relative px-4 py-3.5 text-xs lg:px-8 pb-safe">
  {/* ── <md: 1 dòng gọn + accordion ── */}
  <div className="md:hidden">
    <div className="flex items-center gap-2.5">
      <img src="/ribe-logo.jpeg" alt="RIBE" className="h-8 w-8 shrink-0 rounded-full bg-white object-contain ring-1 ring-white/50" />
      <p className="min-w-0 flex-1 truncate font-bold uppercase tracking-wide text-yogurt">
        Viện CNSH &amp; Môi trường
      </p>
      <button
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="shrink-0 rounded-md bg-white/15 px-2.5 py-1 font-medium text-white"
      >
        {expanded ? 'Thu gọn' : 'Liên hệ'}
      </button>
    </div>
    {expanded && (
      <div className="mt-3 flex flex-col gap-3 border-t border-white/15 pt-3">
        {/* tái dùng <ContactList /> và <VisitCounters /> tách ra từ code cũ */}
        <ContactList />
        <VisitCounters counters={c} />
      </div>
    )}
  </div>

  {/* ── ≥md: giữ nguyên 3 cột như hiện tại ── */}
  <div className="hidden gap-x-10 gap-y-4 md:grid lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,1fr)]">
    {/* ...nội dung 3 cột hiện có, không đổi... */}
  </div>
</div>
```

Refactor: tách `<ContactList />` và `<VisitCounters />` thành 2 component nội bộ trong cùng file để không lặp JSX.

**DoD:** ở 360px, Footer cao ≤ 56px khi đóng; bấm "Liên hệ" mở ra đầy đủ thông tin; ≥768px giữ nguyên như cũ.

---

### T1.4 — `Sidebar.tsx`: icon-rail thay vì ẩn hẳn ⭐

**Vấn đề hiện tại** (`Sidebar.tsx:212`): `collapsed && 'lg:w-0 lg:min-w-0 lg:overflow-hidden lg:border-r-0'` — thu gọn = biến mất, phải bấm nút nổi để mở lại.

**Thiết kế mới — 3 chế độ:**

| Chế độ | Điều kiện | Bề rộng | Nội dung |
|---|---|---:|---|
| `drawer` | `<md` | 256px (overlay) | Đầy đủ |
| `rail` | `md`–`lg`, hoặc `≥lg` khi `collapsed` | 64px | Chỉ icon + tooltip + badge |
| `full` | `≥lg` khi `!collapsed` | 208–460px (kéo giãn) | Đầy đủ |

**Thay đổi ở `<aside>`:**

```tsx
const railMode = collapsed; // ở ≥lg. Ở md–lg luôn rail (xử lý bằng class)

<aside
  style={collapsed ? undefined : { width }}   // chỉ áp width khi full
  className={cn(
    'fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-hairline bg-surface',
    isDragging ? 'transition-none' : 'transition-all duration-200',
    // md trở lên: nằm trong luồng, luôn hiện
    'md:relative md:z-auto md:shrink-0 md:translate-x-0',
    // md–lg: LUÔN là rail 64px
    'md:w-16 lg:w-auto',
    // <md: drawer
    mobileOpen ? 'translate-x-0' : '-translate-x-full',
    // ≥lg khi collapsed: rail 64px thay vì w-0
    collapsed && 'lg:!w-16',
  )}
  data-rail={railMode ? 'true' : undefined}
>
```

**Ẩn/hiện nội dung theo rail** — thêm class có điều kiện vào các khối:

```tsx
// Brand: chỉ giữ logo ở rail
<div className="relative flex h-[72px] shrink-0 items-center justify-between overflow-hidden bg-blueberry px-4 shadow-md md:px-3 lg:px-4">
  {/* text tên viện */}
  <div className={cn('min-w-0', collapsed ? 'lg:hidden' : '', 'hidden md:hidden lg:block')}>…</div>
</div>

// Ô tìm kiếm: ẩn ở rail
<div className={cn('relative z-20 shrink-0 px-3 pt-3', 'hidden lg:block', collapsed && 'lg:hidden')}>…</div>

// Nhãn nhóm: ẩn ở rail (chỉ còn đường kẻ ngăn cách)
// Nhãn leaf: ẩn ở rail, icon căn giữa
```

**`Leaf` — thêm prop `rail`:**

```tsx
function Leaf({ leaf, count, isFav, active, onToggleFav, onNavigate, indent = 'pl-2.5', rail = false }) {
  const Icon = leaf.icon;
  return (
    <li>
      <NavLink
        to={leaf.to}
        onClick={onNavigate}
        title={rail ? leaf.label : undefined}      // tooltip gốc trình duyệt
        aria-label={rail ? leaf.label : undefined}
        className={cn(
          'group relative flex items-center gap-2.5 overflow-hidden rounded-lg py-2 text-sm font-medium transition-all duration-150 ease-out',
          rail ? 'justify-center px-0' : cn('pr-2', indent),
          active ? 'bg-gradient-to-r from-blueberry to-berry text-white shadow-sm'
                 : 'text-stem hover:translate-x-0.5 hover:bg-blueberry/10 hover:text-blueberry',
        )}
      >
        {/* thanh chỉ báo trái — giữ nguyên */}
        {Icon ? <span className="flex h-5 w-5 shrink-0 items-center justify-center …"><Icon size={18} /></span> : <span className="w-5" />}

        {!rail && <span className="flex-1 truncate">{leaf.label}</span>}

        {/* Ở rail: badge thu thành chấm nhỏ góc trên phải */}
        {count && count > 0 ? (
          rail
            ? <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-berry ring-2 ring-surface" />
            : <span className="min-w-[18px] rounded-full px-1.5 …">{count > 99 ? '99+' : count}</span>
        ) : null}

        {!rail && <button /* nút ★ */ />}
      </NavLink>
    </li>
  );
}
```

**Ở chế độ rail, nhóm gập/mở không dùng được** → phẳng hoá: render `flatLeaves(user)` (đã có sẵn ở dòng 48) thay vì `visibleGroups`, giới hạn ~14 mục đầu + mục đang active, phần còn lại nằm sau nút "⋯" mở drawer đầy đủ.

**Nút toggle:** ở rail đổi icon thành `PanelLeftOpen`, đặt trong brand bar. **Xoá nút nổi `fixed left-0 top-20`** (dòng 194–203) vì không còn cần.

**Thanh kéo giãn** (dòng 432–449): thêm điều kiện `hidden lg:block` và ẩn khi `collapsed`.

**DoD:**
- Ở 1280px bấm thu gọn → sidebar còn 64px icon, vẫn bấm được mọi mục, hover hiện tooltip tên.
- Badge vẫn thấy (dạng chấm).
- Không còn nút nổi ở góc trái.

---

### T1.5 — Rail mặc định ở dải `md` (768–1023)

Đây là fix cho **vùng chết** đã nêu trong phân tích.

**`Sidebar.tsx`** — đổi mọi điều kiện `lg:` liên quan tới hiển thị/vị trí thành `md:` (đã gộp vào code T1.4 ở trên).

**`Topbar.tsx:24`** — nút hamburger đổi `lg:hidden` → `md:hidden`:

```diff
- className="rounded-lg p-2 text-white/80 … lg:hidden"
+ className="rounded-lg p-2 text-white/80 … md:hidden"
```

**`Sidebar.tsx:190`** — overlay mobile đổi `lg:hidden` → `md:hidden`.

**DoD:** ở iPad dọc (768×1024) thấy rail icon 64px bên trái, không cần bấm hamburger; ở 767px thấy hamburger + drawer.

---

### T1.6 — Drawer chuẩn

Trong `Sidebar.tsx`, thêm:

```tsx
import { useFocusTrap, useBodyScrollLock } from '@/lib/useFocusTrap';
import { useDown } from '@/lib/useMediaQuery';

const asideRef = useRef<HTMLElement>(null);
const isMobile = useDown('md');
const drawerActive = mobileOpen && isMobile;

useBodyScrollLock(drawerActive);
useFocusTrap(asideRef as RefObject<HTMLElement>, drawerActive);

useEffect(() => {
  if (!drawerActive) return;
  const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onMobileClose();
  document.addEventListener('keydown', onKey);
  return () => document.removeEventListener('keydown', onKey);
}, [drawerActive, onMobileClose]);
```

Gắn `ref={asideRef}` và `aria-hidden={!mobileOpen && isMobile}` vào `<aside>`; overlay thêm `aria-hidden="true"`.

**DoD:** mở drawer trên mobile → cuộn nền bị khoá, Tab không thoát ra ngoài, Esc đóng, focus trả về nút hamburger.

---

### T1.7 — Nút ★ trên touch (`Sidebar.tsx:518-533`)

```diff
  className={cn(
-   'text-sm leading-none transition-all duration-150 hover:scale-125',
+   'tap-exempt -m-1 p-1 text-sm leading-none transition-all duration-150 hover:scale-125',
    isFav
      ? cn('opacity-100', active ? 'text-white' : 'text-warning')
-     : cn('opacity-0 group-hover:opacity-100', …),
+     : cn('opacity-0 group-hover:opacity-100 touch-visible', …),
  )}
+ aria-label={isFav ? `Bỏ ghim ${leaf.label}` : `Ghim ${leaf.label}`}
```

`-m-1 p-1` mở rộng vùng chạm từ ~14px lên ~26px mà không đẩy layout. Áp cùng cách cho nút "Đã đọc/Chưa đọc" ở `Topbar.tsx:222`.

---

### T1.8 — Topbar rút gọn `<sm` (`Topbar.tsx:21-48`)

```tsx
<div className="flex h-14 items-center gap-3 bg-gradient-to-r from-blueberry to-berry px-3 text-white shadow-md sm:h-[72px] sm:px-4 lg:px-6">
  <button onClick={onMobileMenu} className="… md:hidden" aria-label="Mở menu">
    <Menu size={20} />
  </button>

  <img
    src="/nlu-logo.png"
    alt="Logo Trường Đại học Nông Lâm TP. Hồ Chí Minh"
    className="h-9 w-9 shrink-0 rounded-full bg-white object-contain p-0.5 ring-2 ring-white/70 sm:h-12 sm:w-12"
  />

  <div className="min-w-0 leading-tight">
    {/* Tên trường: ẩn hẳn dưới sm — bị truncate mất nghĩa trên 360px */}
    <p className="hidden truncate text-[13px] font-bold uppercase tracking-wide text-white sm:block sm:text-[15px]">
      Trường Đại học Nông Lâm TP. Hồ Chí Minh
    </p>
    {/* Tên viện: rút gọn dưới sm */}
    <p className="truncate text-[12px] font-bold uppercase tracking-wide text-yogurt sm:text-[13px]">
      <span className="sm:hidden">Viện CNSH &amp; Môi trường</span>
      <span className="hidden sm:inline">Viện Nghiên cứu Công nghệ Sinh học và Môi trường</span>
    </p>
    {user?.department && (
      <span className="mt-0.5 hidden rounded bg-white/20 px-1.5 py-0.5 text-[10px] font-semibold text-white sm:inline-block">
        {user.department.name}
      </span>
    )}
  </div>
  …
</div>
```

**Lợi ích:** 72px → 56px trên mobile (+16px), và dòng chữ còn lại đọc được trọn vẹn.

---

### T1.9 — Popup thông báo → sheet `<sm` (`Topbar.tsx:182`)

```tsx
const isMobile = useDown('sm');

{open && (
  <div className={cn(
    'z-50 animate-scale-in rounded-xl border border-hairline bg-surface shadow-pop',
    isMobile
      ? 'fixed inset-x-2 top-[3.75rem] max-h-[75dvh] overflow-hidden'
      : 'absolute right-0 mt-2 w-96 max-w-[calc(100vw-2rem)]',
  )}>
    …
    <div className={cn('overflow-y-auto p-1.5 scrollbar-thin', isMobile ? 'max-h-[calc(75dvh-3.5rem)]' : 'max-h-[26rem]')}>
```

---

### T1.10 — UserMenu `<lg` (`Topbar.tsx:266-273`)

Hiện `hidden lg:block` che tên + vai trò ở trigger. Ở rail-mode (md–lg) người dùng vẫn cần biết mình là ai:

```diff
- <div className="hidden text-left lg:block">
+ <div className="hidden text-left xl:block">
```

Và luôn hiện đầy đủ trong dropdown (đã có sẵn, không đổi). Ở `<xl` chỉ hiện avatar — đủ, vì bấm vào là thấy tên.

---

## 4. Giai đoạn 2 — Primitives ⭐

### T2.1 — `DataTable.tsx`: chế độ thẻ mobile ⭐⭐ *tác động 27 trang*

#### API mở rộng (tương thích ngược 100%)

```ts
export interface Column<T> {
  key: string;
  header: ReactNode;
  sortValue?: (row: T) => string | number;
  render: (row: T, index: number) => ReactNode;
  className?: string;
  headerClassName?: string;
  align?: 'left' | 'right' | 'center';

  /** ── MỚI ── */
  /** Dùng làm tiêu đề thẻ ở chế độ mobile. Nếu không cột nào đặt → dùng cột đầu. */
  primary?: boolean;
  /** 1 = hiện trên thẻ · 2 = ẩn sau "Xem thêm" (mặc định) · 3 = chỉ hiện ở bảng desktop */
  priority?: 1 | 2 | 3;
  /** Nhãn hiển thị ở chế độ thẻ (mặc định lấy `header` nếu là string). */
  mobileLabel?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  pageSize?: number;
  loading?: boolean;
  empty?: ReactNode;

  /** ── MỚI ── */
  /** 'card' (mặc định) = dưới md đổi sang danh sách thẻ · 'scroll' = luôn giữ bảng */
  mobileMode?: 'card' | 'scroll';
  /** Ghim cột đầu khi cuộn ngang ở desktop. Mặc định true. */
  stickyFirstCol?: boolean;
  /** Cho người dùng đổi số dòng/trang. */
  pageSizeOptions?: number[];
}
```

#### Cấu trúc mới

```tsx
export function DataTable<T>({
  columns, rows, rowKey, onRowClick,
  pageSize: initialPageSize = 8, loading, empty,
  mobileMode = 'card', stickyFirstCol = true, pageSizeOptions,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<SortState>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const isMobile = useDown('md');
  const asCards = mobileMode === 'card' && isMobile;

  // …logic sorted / totalPages / pageRows giữ nguyên…

  if (loading)  return asCards ? <CardSkeleton rows={pageSize} /> : <TableSkeleton … />;
  if (pageRows.length === 0) return empty ?? <EmptyState />;

  return (
    <div className="flex flex-col">
      {asCards
        ? <MobileCardList … />
        : <DesktopTable … />}
      <Pagination … />
    </div>
  );
}
```

#### `MobileCardList`

```tsx
function MobileCardList<T>({ columns, rows, rowKey, onRowClick, offset }: …) {
  const primaryCol = columns.find((c) => c.primary) ?? columns[0];
  const shown  = columns.filter((c) => c !== primaryCol && (c.priority ?? 2) === 1);
  const hidden = columns.filter((c) => c !== primaryCol && (c.priority ?? 2) === 2);

  return (
    <ul className="divide-y divide-hairline">
      {rows.map((row, i) => (
        <MobileCard
          key={rowKey(row)}
          row={row} index={offset + i}
          primaryCol={primaryCol} shown={shown} hidden={hidden}
          onClick={onRowClick}
        />
      ))}
    </ul>
  );
}

function MobileCard<T>({ row, index, primaryCol, shown, hidden, onClick }: …) {
  const [expanded, setExpanded] = useState(false);
  return (
    <li>
      <div
        role={onClick ? 'button' : undefined}
        tabIndex={onClick ? 0 : undefined}
        onClick={onClick ? () => onClick(row) : undefined}
        onKeyDown={onClick ? (e) => (e.key === 'Enter' || e.key === ' ') && onClick(row) : undefined}
        className={cn(
          'flex flex-col gap-2 bg-surface px-4 py-3.5 transition-colors',
          onClick && 'cursor-pointer active:bg-plate/70',
        )}
      >
        <div className="text-sm font-semibold text-ink">{primaryCol.render(row, index)}</div>

        {shown.length > 0 && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
            {shown.map((c) => (
              <Fragment key={c.key}>
                <dt className="text-xs font-medium uppercase tracking-wide text-stem">
                  {c.mobileLabel ?? (typeof c.header === 'string' ? c.header : c.key)}
                </dt>
                <dd className="min-w-0 text-ink">{c.render(row, index)}</dd>
              </Fragment>
            ))}
          </dl>
        )}

        {hidden.length > 0 && (
          <>
            {expanded && (
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 border-t border-hairline pt-2 text-sm">
                {hidden.map((c) => (…giống trên…))}
              </dl>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
              className="tap-exempt self-start text-xs font-medium text-blueberry"
              aria-expanded={expanded}
            >
              {expanded ? 'Thu gọn' : `Xem thêm (${hidden.length})`}
            </button>
          </>
        )}
      </div>
    </li>
  );
}
```

#### `DesktopTable` — sticky cột 1 + gợi ý cuộn

```tsx
function DesktopTable<T>({ …, stickyFirstCol }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [hasMoreRight, setHasMoreRight] = useState(false);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const update = () => setHasMoreRight(el.scrollWidth - el.clientWidth - el.scrollLeft > 4);
    update();
    el.addEventListener('scroll', update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => { el.removeEventListener('scroll', update); ro.disconnect(); };
  }, []);

  const stickyCell = (idx: number, isHeader: boolean) =>
    stickyFirstCol && idx === 0
      ? cn('sticky left-0 z-[2]', isHeader ? 'bg-plate' : 'bg-surface',
           'after:absolute after:inset-y-0 after:-right-px after:w-px after:bg-hairline')
      : undefined;

  return (
    <div className="relative">
      <div ref={scrollRef} className="overflow-x-auto scrollbar-thin">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          {/* …thead/tbody như cũ, thêm cn(stickyCell(idx, true/false), …) vào th/td… */}
        </table>
      </div>
      {/* Gợi ý còn nội dung bên phải */}
      {hasMoreRight && (
        <div aria-hidden className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-surface to-transparent" />
      )}
    </div>
  );
}
```

> **Bỏ `sticky top-0` ở `<thead>`** (dòng 73) — container cuộn dọc là `<main>`, không phải wrapper bảng, nên sticky hiện không hoạt động đúng. Nếu vẫn muốn header dính, phải giới hạn chiều cao wrapper (`max-h-[70vh] overflow-y-auto`) — cân nhắc riêng, **không** làm trong PR này.

#### `Pagination` — mobile-friendly

```tsx
<div className="flex flex-col gap-2 border-t border-hairline px-4 py-3 text-xs text-subink sm:flex-row sm:items-center sm:justify-between">
  <span>Hiển thị <strong className="text-ink">{from}–{to}</strong> / {total} bản ghi</span>
  <div className="flex items-center gap-2">
    {pageSizeOptions && (
      <select value={pageSize} onChange={…} aria-label="Số dòng mỗi trang"
        className="h-8 rounded-md border border-hairline bg-surface px-2 text-xs">
        {pageSizeOptions.map((n) => <option key={n} value={n}>{n} / trang</option>)}
      </select>
    )}
    <button className="flex h-9 w-9 … sm:h-7 sm:w-7" aria-label="Trang trước">…</button>
    <span className="px-2 font-medium text-ink">{safePage} / {totalPages}</span>
    <button className="flex h-9 w-9 … sm:h-7 sm:w-7" aria-label="Trang sau">…</button>
  </div>
</div>
```

**DoD T2.1:**
- Ở 360px, **không trang nào** còn cuộn ngang trong bảng (trừ trang cố ý đặt `mobileMode="scroll"`).
- Ở 1024px, cuộn ngang bảng 8 cột → cột đầu vẫn dính trái, thấy gradient bên phải.
- `onRowClick` hoạt động ở cả 2 chế độ; bấm "Xem thêm" **không** kích hoạt `onRowClick`.
- 27 trang cũ chưa khai báo `priority` vẫn chạy được (mặc định: cột đầu = tiêu đề, phần còn lại nằm sau "Xem thêm").

---

### T2.2 — `Modal.tsx`: bottom-sheet + a11y ⭐⭐ *tác động 36 chỗ*

```tsx
import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useDown } from '@/lib/useMediaQuery';
import { useFocusTrap, useBodyScrollLock } from '@/lib/useFocusTrap';

export function Modal({
  open, onClose, title, description, children, footer, size = 'md',
}: {
  open: boolean; onClose: () => void;
  title: ReactNode; description?: ReactNode;
  children: ReactNode; footer?: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';   // ← thêm 'xl'
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const isMobile = useDown('sm');

  useBodyScrollLock(open);                    // ← thay dòng 27 cũ
  useFocusTrap(panelRef, open);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  // Dùng w-[min(92vw,…)] thay max-w-* để không bao giờ tràn viewport ở dải md
  const widths = {
    sm: 'sm:w-[min(92vw,28rem)]',
    md: 'sm:w-[min(92vw,36rem)]',
    lg: 'sm:w-[min(92vw,48rem)]',
    xl: 'sm:w-[min(94vw,64rem)]',
  };

  return createPortal(
    <div className={cn(
      'fixed inset-0 z-50 flex overflow-y-auto',
      isMobile ? 'items-end' : 'items-start justify-center p-4 sm:p-6',
    )}>
      <div className="fixed inset-0 animate-fade-in bg-blueberry/30 backdrop-blur-[2px]" onClick={onClose} />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={cn(
          'relative z-10 flex w-full flex-col border-hairline bg-surface shadow-pop',
          isMobile
            ? 'max-h-sheet animate-slide-up rounded-t-2xl border-t pb-safe'
            : cn('my-8 animate-scale-in rounded-xl border', widths[size]),
        )}
      >
        {/* Tay nắm kéo — tín hiệu "đây là sheet" trên mobile */}
        {isMobile && (
          <div aria-hidden className="mx-auto mt-2.5 h-1 w-10 shrink-0 rounded-full bg-hairline" />
        )}

        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-hairline px-4 py-3.5 sm:px-5 sm:py-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-base font-semibold text-ink">{title}</h2>
            {description && <p className="mt-0.5 text-sm text-subink">{description}</p>}
          </div>
          <button onClick={onClose} className="-mr-1 shrink-0 rounded-lg p-2 text-stem hover:bg-plate hover:text-ink" aria-label="Đóng">
            <X size={18} />
          </button>
        </div>

        {/* Body co giãn — trên mobile chiếm hết phần còn lại của sheet */}
        <div className={cn(
          'min-h-0 flex-1 overflow-y-auto px-4 py-4 scrollbar-thin sm:px-5',
          !isMobile && 'max-h-[70vh]',
        )}>
          {children}
        </div>

        {footer && (
          <div className={cn(
            'flex shrink-0 items-center gap-2 border-t border-hairline bg-plate/60 px-4 py-3 sm:px-5 sm:py-3.5',
            // Mobile: nút chiếm đều chiều ngang, dễ bấm
            'max-sm:[&>button]:flex-1 justify-end',
          )}>
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
```

**Điểm then chốt:**
- `flex flex-col` + `min-h-0 flex-1` trên body → footer **luôn dính đáy**, không cần `position: sticky`.
- `max-h-sheet` = `92dvh` → sheet không bao giờ vượt màn hình.
- `w-[min(92vw, …)]` sửa lỗi modal `lg` (768px) tràn trên iPad dọc.
- `max-sm:[&>button]:flex-1` → 2 nút Hủy/Lưu chia đôi chiều ngang trên mobile.

**Kiểm tra hồi quy bắt buộc** (Modal là điểm chạm của 36 nơi):
- `ConfirmDialog` mở **bên trong** một `Modal` → cả 2 hiển thị đúng thứ tự z-index, đóng dialog không mở khoá cuộn body.
- `FormFileManager`, `AttachmentPanel` đặt trong modal → vẫn cuộn được.
- Modal có `<Select>` mở dropdown gốc trình duyệt trên iOS → không bị cắt.

---

### T2.3 — `src/components/ui/FormGrid.tsx` ✨ file mới

```tsx
import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

/**
 * Lưới form responsive chuẩn. Mobile 1 cột, chia cột từ `md` (768px).
 * Dùng thay cho mọi `grid grid-cols-2/3` viết tay.
 */
export function FormGrid({
  cols = 2,
  gap = 4,
  children,
  className,
}: {
  cols?: 2 | 3 | 4;
  gap?: 3 | 4;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'grid grid-cols-1',
        gap === 3 ? 'gap-3' : 'gap-4',
        cols === 2 && 'md:grid-cols-2',
        cols === 3 && 'md:grid-cols-2 lg:grid-cols-3',
        cols === 4 && 'md:grid-cols-2 lg:grid-cols-4',
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Ô chiếm trọn chiều ngang lưới (thay cho `col-span-2` viết tay). */
export function FormFull({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('md:col-span-2 lg:col-span-full', className)}>{children}</div>;
}

/** Lưới hiển thị read-only dạng label/value (không phải form nhập). */
export function InfoGrid({ cols = 2, children, className }: {
  cols?: 2 | 3; children: ReactNode; className?: string;
}) {
  return (
    <div className={cn(
      'grid grid-cols-1 gap-x-4 gap-y-2 text-sm',
      cols === 2 ? 'sm:grid-cols-2' : 'sm:grid-cols-2 lg:grid-cols-3',
      className,
    )}>{children}</div>
  );
}
```

> `InfoGrid` giữ ngưỡng `sm:` (không phải `md:`) vì nội dung read-only ngắn, 2 cột ở 640px vẫn đọc tốt — khác với form có `<Select>`/`<Input>`.

---

### T2.4 — `Button.tsx`

```diff
  const SIZES: Record<Size, string> = {
-   sm: 'h-8 px-3 text-xs gap-1.5',
-   md: 'h-10 px-4 text-sm gap-2',
+   sm: 'h-9 px-3 text-xs gap-1.5 sm:h-8',
+   md: 'h-11 px-4 text-sm gap-2 sm:h-10',
+   icon: 'h-10 w-10 p-0 sm:h-9 sm:w-9',
  };
- type Size = 'sm' | 'md';
+ type Size = 'sm' | 'md' | 'icon';
```

Thêm prop tiện dụng cho mobile:

```diff
  interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: Variant;
    size?: Size;
    loading?: boolean;
+   /** Chiếm trọn chiều ngang dưới sm — dùng cho nút chính trong form/modal. */
+   fullWidthMobile?: boolean;
  }
```

```diff
        VARIANTS[variant],
        SIZES[size],
+       fullWidthMobile && 'w-full sm:w-auto',
        className,
```

---

### T2.5 — `src/components/ui/FilterBar.tsx` ✨ file mới *(thay pattern lặp ở 15 trang)*

```tsx
import { useState, type ReactNode } from 'react';
import { SlidersHorizontal, X } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Button } from './Button';
import { Modal } from './Modal';
import { useDown } from '@/lib/useMediaQuery';

export interface FilterSpec {
  /** Khoá duy nhất — dùng để đếm filter đang bật. */
  key: string;
  /** Control (thường là <Select>). */
  node: ReactNode;
  /** Nhãn hiện trong sheet lọc mobile. */
  label: string;
  /** true nếu filter này đang có giá trị (≠ mặc định). */
  active: boolean;
}

export function FilterBar({
  search,
  filters = [],
  onClear,
  className,
}: {
  search?: ReactNode;
  filters?: FilterSpec[];
  onClear?: () => void;
  className?: string;
}) {
  const isMobile = useDown('md');
  const [sheetOpen, setSheetOpen] = useState(false);
  const activeCount = filters.filter((f) => f.active).length;

  if (isMobile) {
    return (
      <>
        <div className={cn('flex items-center gap-2 border-b border-hairline p-3', className)}>
          {search && <div className="min-w-0 flex-1">{search}</div>}
          {filters.length > 0 && (
            <Button variant="secondary" onClick={() => setSheetOpen(true)} className="shrink-0">
              <SlidersHorizontal size={15} />
              Lọc
              {activeCount > 0 && (
                <span className="ml-0.5 rounded-full bg-blueberry px-1.5 text-[11px] font-bold text-white">
                  {activeCount}
                </span>
              )}
            </Button>
          )}
        </div>

        <Modal
          open={sheetOpen}
          onClose={() => setSheetOpen(false)}
          title="Bộ lọc"
          footer={
            <>
              {onClear && activeCount > 0 && (
                <Button variant="ghost" onClick={() => { onClear(); setSheetOpen(false); }}>
                  <X size={15} /> Xoá lọc
                </Button>
              )}
              <Button onClick={() => setSheetOpen(false)}>Áp dụng</Button>
            </>
          }
        >
          <div className="flex flex-col gap-4">
            {filters.map((f) => (
              <label key={f.key} className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-ink">{f.label}</span>
                {f.node}
              </label>
            ))}
          </div>
        </Modal>
      </>
    );
  }

  // ≥md — lưới đều, KHÔNG dùng max-w-[NNNpx] cứng nữa
  return (
    <div className={cn('flex flex-wrap items-center gap-3 border-b border-hairline p-4', className)}>
      {search && <div className="min-w-[220px] max-w-sm flex-1">{search}</div>}
      {filters.map((f) => (
        <div key={f.key} className="w-[clamp(150px,18vw,220px)]">{f.node}</div>
      ))}
      {onClear && activeCount > 0 && (
        <Button variant="ghost" size="sm" onClick={onClear} className="ml-auto">
          <X size={14} /> Xoá lọc ({activeCount})
        </Button>
      )}
    </div>
  );
}
```

**Cách migrate 1 trang** (ví dụ `Documents.tsx:121-152`):

```tsx
// TRƯỚC — 32 dòng, 3 max-w cứng
<div className="flex flex-wrap items-center gap-3 border-b border-hairline p-4">
  <SearchInput … className="max-w-xs flex-1" />
  <Select … className="max-w-[200px]">…</Select>
  <Select … className="max-w-[160px]">…</Select>
  <Select … className="max-w-[200px]">…</Select>
</div>

// SAU
<FilterBar
  search={<SearchInput value={q} onChange={setQ} placeholder="Mã hoặc tiêu đề…" />}
  filters={[
    { key: 'type',     label: 'Loại tài liệu', active: !!type,
      node: <Select value={type} onChange={(e) => setType(e.target.value)}>…</Select> },
    { key: 'security', label: 'Mức bảo mật',   active: !!securityLevel,
      node: <Select value={securityLevel} onChange={(e) => setSecurityLevel(e.target.value)}>…</Select> },
    { key: 'dept',     label: 'Phòng ban',     active: !!departmentId,
      node: <Select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>…</Select> },
  ]}
  onClear={() => { setType(''); setSecurityLevel(''); setDepartmentId(''); }}
/>
```

> ⚠️ Bỏ `className="max-w-[...]"` khỏi mọi `<Select>` khi đưa vào `FilterBar` — chiều rộng do `FilterBar` quyết định.

---

### T2.6 — `PageHeader.tsx`

```diff
- <div className="relative flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
+ <div className="relative flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
    <div className="flex animate-sprout items-center gap-3">
      …
      <div className="min-w-0">
-       <h1 className="text-xl font-bold tracking-tight text-ink">{title}</h1>
+       <h1 className="text-lg font-bold tracking-tight text-ink sm:text-xl">{title}</h1>
-       {description && <p className="mt-0.5 text-sm text-subink">{description}</p>}
+       {description && <p className="mt-0.5 line-clamp-2 text-xs text-subink sm:text-sm">{description}</p>}
      </div>
    </div>
-   {actions && <div className="relative flex shrink-0 items-center gap-2">{actions}</div>}
+   {actions && (
+     <div className="relative flex shrink-0 flex-wrap items-center gap-2 max-sm:w-full max-sm:[&>*]:flex-1">
+       {actions}
+     </div>
+   )}
  </div>
```

Ngoài ra giảm hoạ tiết lá trên mobile:

```diff
- className="pointer-events-none absolute -right-6 -top-8 h-36 w-36 animate-sway text-blueberry/[0.07]"
+ className="pointer-events-none absolute -right-6 -top-8 h-24 w-24 animate-sway text-blueberry/[0.07] sm:h-36 sm:w-36"
```

> **Với trang có ≥3 nút** (`Documents`, `Risks`, `Chemicals`, `Dashboard`): giữ nút chính, gom nút phụ vào menu `⋯` dưới `sm`. Xử lý riêng trong T3B.

---

### T2.7 — `DescList.tsx`

```diff
- <dl className={cn('grid grid-cols-1 gap-x-6 gap-y-3.5 sm:grid-cols-2', className)}>
+ <dl className={cn('grid grid-cols-1 gap-x-6 gap-y-3.5 sm:grid-cols-2 2xl:grid-cols-3', className)}>

- <div className={full ? 'sm:col-span-2' : undefined}>
+ <div className={full ? 'sm:col-span-2 2xl:col-span-3' : undefined}>
```

> Đây là ngoại lệ của T0.6 — read-only, giữ `sm:`.

---

### T2.8 — `ToastContext.tsx`

```diff
- <div className="pointer-events-none fixed right-4 top-4 z-[100] flex w-full max-w-sm flex-col gap-2">
+ <div
+   aria-live="polite"
+   aria-atomic="false"
+   className="pointer-events-none fixed inset-x-3 top-3 z-[100] flex flex-col gap-2 pt-safe
+              sm:inset-x-auto sm:right-4 sm:top-4 sm:w-full sm:max-w-sm"
+ >
```

---

### T2.9 — `States.tsx`: thêm `CardSkeleton`

```tsx
/** Skeleton cho DataTable ở chế độ thẻ (dưới md). */
export function CardSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="divide-y divide-hairline">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex flex-col gap-2 px-4 py-3.5">
          <div className="h-4 w-2/3 animate-pulse rounded bg-hairline/70" />
          <div className="h-3 w-1/2 animate-pulse rounded bg-hairline/50" />
          <div className="h-3 w-2/5 animate-pulse rounded bg-hairline/50" />
        </div>
      ))}
    </div>
  );
}
```

---

## 5. Giai đoạn 3 — Sweep trang

### T3A — 20 lưới cứng → `FormGrid` (12 file, 4h)

| # | File:dòng | Hiện tại | Thay bằng | Ghi chú |
|---|---|---|---|---|
| 1 | `SampleFlow.tsx:258` | `grid-cols-3 gap-3` | `<FormGrid cols={3} gap={3}>` | Mã số thuế / Người liên hệ / Điện thoại |
| 2 | `SampleFlow.tsx:263` | `grid-cols-2 gap-3` | `<FormGrid gap={3}>` | Mail / Ngày hẹn |
| 3 | `SampleFlow.tsx:270` | `grid-cols-3 gap-3` | `<FormGrid cols={3} gap={3}>` | Phiếu KQ / … |
| 4 | `SampleFlow.tsx:392` | `grid-cols-2 gap-x-4 gap-y-2 text-sm` | `<InfoGrid>` | read-only |
| 5 | `SampleFlow.tsx:401` | như trên | `<InfoGrid>` | read-only |
| 6 | `SampleFlow.tsx:746` | `grid-cols-2 gap-3` | `<FormGrid gap={3}>` | |
| 7 | `SampleFlow.tsx:986` | `grid-cols-2 … bg-plate p-4` | `<InfoGrid className="rounded-xl border border-hairline bg-plate p-4">` | |
| 8 | `SampleFlow.tsx:997` | `grid-cols-2 gap-x-4 gap-y-2` | `<InfoGrid>` | |
| 9 | `SampleFlow.tsx:1009` | `grid-cols-2 … border p-4` | `<InfoGrid className="rounded-xl border border-hairline p-4">` | |
| 10 | `TestParameters.tsx:246` | `grid-cols-2 gap-4` | `<FormGrid>` | 5 `col-span-2` bên trong → `<FormFull>` |
| 11 | `Chemicals.tsx:262` | `grid-cols-2 gap-4` | `<FormGrid>` | 2 `col-span-2` |
| 12 | `RiskDetail.tsx:225` | `grid-cols-2 gap-4` | `<FormGrid>` | |
| 13 | `ResearchContracts.tsx:180` | `grid-cols-2 gap-4` | `<FormGrid>` | 1 `col-span-2` |
| 14 | `TrainingCertificates.tsx:130` | `grid-cols-2 gap-4` | `<FormGrid>` | 2 `col-span-2` |
| 15 | `StaffActivities.tsx:146` | `grid-cols-2 gap-4` | `<FormGrid>` | 1 `col-span-2` |
| 16 | `Forms.tsx:432` | `grid-cols-3 gap-3` | `<FormGrid cols={3} gap={3}>` | |
| 17 | `DocumentDetail.tsx:591` | `grid-cols-3 gap-3` | `<FormGrid cols={3} gap={3}>` | |
| 18 | `Equipment.tsx:399` | `grid-cols-2 gap-3 text-sm` | `<InfoGrid>` | read-only |
| 19 | `Nonconformities.tsx:355` | `grid-cols-2 gap-3 text-sm` | `<InfoGrid>` | read-only |
| 20 | `ChemicalDetail.tsx:538` | `grid-cols-2 gap-4` | `<FormGrid>` | 3 `col-span-2` |

**Quy tắc chuyển `col-span-2` bên trong:**
- Nếu nằm trong `FormGrid cols={2}` → `<FormFull>` hoặc class `md:col-span-2`
- Nếu nằm trong `FormGrid cols={3}` → `md:col-span-2 lg:col-span-3`
- **Không được để `col-span-2` trần** (sẽ sai khi lưới về 1 cột nếu sau này đổi cấu hình).

**DoD T3A:** mở 20 modal/khối tương ứng ở 360px → mọi `<Input>`/`<Select>` full-width, không có 2 cột.

---

### T3B — 15 trang danh sách (8h)

Mỗi trang làm 3 việc:

1. **Thay khối lọc** → `<FilterBar>` (bỏ toàn bộ `max-w-[NNNpx]`)
2. **Khai báo `primary` + `priority`** cho `columns`
3. **Kiểm `PageHeader actions`** — ≥3 nút thì gom nút phụ

Bảng khai báo cột đề xuất:

| Trang | `primary` | `priority: 1` (hiện trên thẻ) | `priority: 3` (chỉ desktop) |
|---|---|---|---|
| `Documents` | `document_code` | `type`, `version` | `department`, `security` |
| `Chemicals` | tên hoá chất | tồn kho, hạn dùng | nhóm, nhà cung cấp |
| `Equipment` | tên/mã thiết bị | trạng thái, hạn hiệu chuẩn | vị trí, phòng |
| `Users` | họ tên | vai trò, trạng thái | phòng ban, email |
| `Risks` | mô tả rủi ro | band, trạng thái | loại, người phụ trách |
| `Nonconformities` | mã NC | trạng thái, hạn xử lý | nguồn, phòng |
| `TestParameters` | tên chỉ tiêu | nền mẫu, đơn giá | phương pháp, đơn vị, TAT |
| `SampleRequests` | mã yêu cầu | trạng thái, ngày | khách hàng, số mẫu |
| `Publications` | tiêu đề | năm, loại | tạp chí, tác giả |
| `ResearchProjects` | tên đề tài | cấp, trạng thái | kinh phí, chủ nhiệm |
| `Forms` | mã form | phiên bản | phòng, năm |
| `ActivityReports` | kỳ báo cáo | trạng thái | người nộp, ngày nộp |
| `LabRegistrations` | mã đăng ký | trạng thái, ngày | phòng lab, người ĐK |
| `Customers` | tên khách hàng | điện thoại | địa chỉ, MST, email |
| `TrainingCertificates` | tên chứng nhận | hạn hiệu lực | tổ chức cấp, ngày cấp |

**Trang cần gom nút** (`PageHeader actions` ≥3): `Documents` (3 nút), `Chemicals` (2+), `Risks` (2+), `Dashboard` (2+).

Mẫu gom nút:

```tsx
actions={
  <>
    {/* Nút chính — luôn hiện */}
    {canManage && <Button onClick={…} fullWidthMobile><Plus size={16} /> Tạo tài liệu</Button>}
    {/* Nút phụ — chỉ hiện từ sm, dưới sm nằm trong menu ⋯ */}
    <div className="hidden items-center gap-2 sm:flex">
      {canApprove && <Button variant="secondary" onClick={…}><ClipboardCheck size={16} /> Chờ duyệt</Button>}
      {canViewStats && <Button variant="secondary" onClick={…}><BarChart3 size={16} /> Thống kê</Button>}
    </div>
    <OverflowMenu className="sm:hidden" items={[…]} />
  </>
}
```

> `OverflowMenu` là component nhỏ mới (~40 dòng) trong `ui/OverflowMenu.tsx` — nút `⋯` + dropdown. Tính vào T2.6.

---

### T3C — 8 trang chi tiết + 7 `<table>` thô (8h)

**Bọc mọi `<table>` thô** theo mẫu:

```tsx
<div className="relative">
  <div className="overflow-x-auto scrollbar-thin">
    <table className="w-full min-w-[640px] text-sm">
      {/* th/td đầu tiên thêm: sticky left-0 bg-surface z-[2] */}
    </table>
  </div>
</div>
```

| File | Dòng | `min-w` hiện tại | Xử lý |
|---|---|---|---|
| `EquipmentDetail.tsx` | 245 | 760px | bọc + sticky cột 1 |
| `ChemicalDetail.tsx` | 138 | 700px | bọc + sticky cột 1 |
| `ChemicalDetail.tsx` | 250 | 760px | bọc + sticky cột 1 |
| `HrProfileView.tsx` | 252 | 640px | bọc + sticky cột 1 |
| `Reports.tsx` | 445 | (không có) | thêm `min-w-[560px]` + bọc |
| `DocumentDetail.tsx` | — | — | kiểm tra & bọc |
| `SampleDetail.tsx` | 650 | (bảng nhỏ `text-xs`) | **giữ nguyên** — bảng phụ trong cell, không cần |

**Các trang chi tiết** — checklist chung:
- [ ] Thanh hành động đầu trang: `flex flex-wrap gap-2`, nút chính `fullWidthMobile`
- [ ] Khối tab (nếu có): `<sm` cuộn ngang `overflow-x-auto no-scrollbar snap-x`
- [ ] `DescList` đã tự responsive (T2.7) — chỉ kiểm mắt
- [ ] Timeline/lịch sử: `<sm` bỏ cột trái, dùng dấu chấm inline
- [ ] `AttachmentPanel` / `FormFileManager`: nút tải/xoá đủ 40px

---

### T3D — 4 trang đặc thù (10h)

#### `SampleFlow.tsx` (~1000 dòng — nặng nhất, 4h)

Cấu trúc: 3 tab (`intakes` / `dispatches` / `requests`) + 4 modal lớn.

- **Tab bar** (dòng 88–99): 3 `<Button>` ngang → `<sm` chuyển thành thanh cuộn ngang:
  ```tsx
  <div className="-mx-3 flex gap-2 overflow-x-auto px-3 pb-1 no-scrollbar sm:mx-0 sm:overflow-visible sm:px-0">
    <Button className="shrink-0" …>Phiếu nhận mẫu</Button>
    …
  </div>
  ```
- **`IntakeCreateModal`** (204): `size="lg"` → giữ, dùng `FormGrid` (T3A #1–3)
- **`IntakeDetailModal`** (296): dài nhất — chia section có thể gập trên mobile
- **`DispatchesTab`** (608): `<Select>` `min-w-[150px]` dòng 652 → `w-full sm:w-auto sm:min-w-[150px]`
- **Dòng 517**: `min-w-[220px] flex-1` → `w-full sm:min-w-[220px] sm:flex-1`
- **`DispatchDetailModal`** (947): các `InfoGrid` (T3A #7–9)

#### `MonthlyReport.tsx` (3h)

- **Thanh sticky đáy** (dòng 431):
  ```diff
  - <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-hairline bg-surface/95 p-4 shadow-sm backdrop-blur">
  + <div className="sticky bottom-0 z-20 -mx-3 flex flex-col gap-3 border-t border-hairline bg-surface/95 p-3 shadow-sm backdrop-blur pb-safe sm:mx-0 sm:flex-row sm:items-center sm:justify-between sm:rounded-xl sm:border sm:p-4">
  ```
  Và nhóm nút: `<div className="flex gap-2 max-sm:[&>button]:flex-1">`
- **`RowShell`** (component lặp cho từng dòng hoạt động): kiểm tra lưới bên trong, chuyển sang `FormGrid`
- **`Section`**: `<sm` cho phép gập (form dài, cuộn mệt)
- 6 `col-span-2` → `md:col-span-2` (đã xử lý ở T0.6)

#### `Reports.tsx` (2h)

| Dòng | Hiện tại | Đổi thành |
|---|---|---|
| 135 | `grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5` *(sau T0.6)* | `grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5` — 5 ô lọc ngày/select |
| 304 | `grid-cols-2 gap-4 md:grid-cols-4` | `grid-cols-2 gap-3 lg:grid-cols-4` |
| 431 | `grid-cols-1 gap-4 md:grid-cols-3` | giữ |
| 445 | `<table className="w-full text-sm">` | bọc + `min-w-[560px]` |
| 553 | `grid-cols-1 gap-4 md:grid-cols-3` | giữ |
| 558 | `grid-cols-1 gap-4 lg:grid-cols-3` | giữ |
| 318 | `<ResponsiveContainer width="100%" height={300}>` | `height={chartH}` (T4.2) |

#### `Login.tsx` + `ChangePassword.tsx` (1h)

```diff
- <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-plate px-4">
+ <div className="relative flex min-h-screen-dvh items-center justify-center overflow-hidden bg-plate px-4 py-8 px-safe">
```
```diff
- className="h-20 w-20 rounded-full bg-white object-contain shadow-card ring-2 ring-blueberry/20"
+ className="h-16 w-16 rounded-full bg-white object-contain shadow-card ring-2 ring-blueberry/20 sm:h-20 sm:w-20"
```
- Hoạ tiết nền (dòng 43–47): thêm `hidden sm:block` cho `Microscope` (h-40 w-40 ở góc → chèn lên form trên màn nhỏ)
- `<form className="… p-6">` → `p-5 sm:p-6`
- Nút submit đã `w-full` — tốt.

---

## 6. Giai đoạn 4 — Màn lớn & biểu đồ

### T4.1 — KPI & dashboard

```diff
// DashKit.tsx:93 (KpiGrid)
- <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
+ <div className="grid grid-cols-1 gap-3 xs:grid-cols-2 sm:gap-4 lg:grid-cols-4 3xl:grid-cols-5">

// Dashboard.tsx:195
- <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
+ <div className="grid grid-cols-1 gap-3 xs:grid-cols-2 sm:gap-4 lg:grid-cols-4 3xl:grid-cols-5">
```

7 file dashboard có `grid grid-cols-1 gap-6 lg:grid-cols-2`:
```diff
- <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
+ <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-6 3xl:grid-cols-3">
```
Áp cho: `StaffDashboard:50` · `OfficeDashboard:75` · `LeaderDashboard:68` · `LabManagerDashboard:60` · `QmsDashboard:67` · `ReceptionDashboard:47` · `Dashboard:360`

`KpiTile` thu gọn `<sm`:
```diff
- <div className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-xl', TONE_ICON[tone])}>
+ <div className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-xl sm:h-11 sm:w-11', TONE_ICON[tone])}>
- <p className="text-2xl font-bold leading-tight text-ink">{value}</p>
+ <p className="text-xl font-bold leading-tight text-ink sm:text-2xl">{value}</p>
- className="flex w-full items-center gap-4 px-5 py-4 text-left disabled:cursor-default"
+ className="flex w-full items-center gap-3 px-4 py-3.5 text-left disabled:cursor-default sm:gap-4 sm:px-5 sm:py-4"
```

### T4.2 — Biểu đồ thích ứng

Thêm hook dùng chung vào `DashCharts.tsx` và export:

```tsx
import { useDown, useUp } from '@/lib/useMediaQuery';

export function useChartHeight() {
  const isMobile = useDown('sm');
  const isHuge = useUp('3xl');
  return isMobile ? 200 : isHuge ? 360 : 280;
}
```

Áp dụng cho **9 chỗ** `<ResponsiveContainer height={280|300}>`:
- `Dashboard.tsx` — 4 chỗ (370, 404, 427, 464)
- `Reports.tsx` — 1 chỗ (318)
- `DashCharts.tsx` — 3 chỗ (24, 47, 84)
- `QmsDashboard.tsx` — PieChart

Trục X thích ứng:
```tsx
<XAxis
  dataKey="label"
  tick={{ fontSize: isMobile ? 10 : 12 }}
  angle={isMobile ? -40 : 0}
  textAnchor={isMobile ? 'end' : 'middle'}
  height={isMobile ? 56 : 30}
  interval={isMobile ? 'preserveStartEnd' : 0}
/>
<Legend wrapperStyle={{ fontSize: isMobile ? 11 : 12 }} {...(isMobile && { layout: 'horizontal', align: 'center' })} />
```

`PieChart` (`QmsDashboard`): `outerRadius={isMobile ? 70 : 100}`, legend xuống dưới.

### T4.3 — `QuickActions` (`DashKit.tsx:115`)

```diff
- <div className="flex flex-wrap gap-2">
+ <div className="-mx-3 flex gap-2 overflow-x-auto px-3 pb-1 no-scrollbar sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0">
    {actions.map((a) => (
      <button
        key={a.label}
-       className="inline-flex items-center gap-2 rounded-lg border border-hairline bg-surface px-3.5 py-2 …"
+       className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-hairline bg-surface px-3.5 py-2 …"
```

---

## 7. Giai đoạn 5 — A11y & QA

### T5.1 — Focus trap phần còn lại

- `ConfirmDialog` — tự động có nhờ `Modal` (T2.2) ✔
- `NotificationBell` dropdown (`Topbar.tsx:167`): thêm ESC + `role="menu"` / `role="menuitem"`
- `UserMenu` dropdown (`Topbar.tsx:259`): như trên
- Dropdown "Gần đây" trong sidebar (`Sidebar.tsx:276`): thêm điều hướng ↑↓ + Enter

### T5.2 — Nhãn

| Vị trí | Thêm |
|---|---|
| `Sidebar.tsx:246` ô tìm | `aria-label="Tìm chức năng trong menu"` |
| `Sidebar.tsx:265` nút ✕ | `aria-label="Xoá từ khoá tìm"` |
| `Sidebar.tsx:518` nút ★ | `aria-label={isFav ? 'Bỏ ghim …' : 'Ghim …'}` |
| `Topbar.tsx:217` nút đã đọc | `aria-label` mô tả rõ |
| `DataTable` nút sort | `aria-sort="ascending"/"descending"/"none"` trên `<th>` |
| Mọi `<Button size="icon">` | `aria-label` bắt buộc (thêm ESLint rule nếu có eslint) |

### T5.3 — QA (4h)

#### Ma trận thiết bị bắt buộc

| Thiết bị | Kích thước | Điểm kiểm chính |
|---|---|---|
| iPhone SE | 375×667 | Màn nhỏ nhất thực tế — form, modal sheet |
| iPhone 14 Pro | 393×852 | Safe area / notch / home indicator |
| Galaxy S20 | 360×800 | **Hẹp nhất** — mọi lưới phải 1 cột |
| iPad mini dọc | 768×1024 | **Rail sidebar** — vùng chết cũ |
| iPad Pro ngang | 1366×1024 | Sidebar full + 2 cột |
| Laptop | 1366×768 | **Chiều cao hẹp** — ngân sách dọc sau khi bỏ footer cố định |
| Desktop | 1920×1080 | Chuẩn |
| 2K | 2560×1440 | `3xl` — kiểm max-w 1760 |

#### Checklist mỗi trang (9 điểm)

- [ ] 360px: `document.documentElement.scrollWidth <= window.innerWidth`
- [ ] 360px: mọi `<Input>`/`<Select>` rộng ≥ 260px hoặc full-width
- [ ] 360px: mọi phần tử bấm được ≥ 40×40px
- [ ] 360px: bảng ở chế độ thẻ, không cuộn ngang
- [ ] 768px: nội dung 2 cột, sidebar là rail
- [ ] 1920px: viền trống mỗi bên ≤ 400px
- [ ] Modal mở ở 360×640: thấy được cả tiêu đề và nút Lưu/Huỷ
- [ ] Tab-only: đi hết trang, focus ring luôn thấy, không bẫy focus
- [ ] Zoom 200% ở 1280px: không mất nội dung

#### Công cụ

```bash
npx @axe-core/cli http://localhost:5173/dashboard --exit
npx lighthouse http://localhost:5173/dashboard --preset=desktop --view
npx lighthouse http://localhost:5173/dashboard --form-factor=mobile --view
```

Mục tiêu: Lighthouse Accessibility ≥ 90, không có lỗi axe mức `serious`/`critical`.

---

## 8. Giai đoạn 6 (tuỳ chọn) — Dark mode

Hạ tầng đã sẵn sàng 100% (token CSS variable). Chỉ cần:

**`index.css`:**
```css
:root[data-theme='dark'] {
  --c-blueberry: 74 160 118;
  --c-berry: 120 168 138;
  --c-stem: 156 160 150;
  --c-yogurt: 206 182 134;
  --c-plate: 18 22 19;
  --c-surface: 26 31 27;
  --c-surface2: 34 40 35;
  --c-ink: 235 238 232;
  --c-subink: 168 173 163;
  --c-hairline: 52 58 50;
  --c-success: 74 175 110;
  --c-pending: 96 152 240;
  --c-warning: 214 148 70;
  --c-overdue: 226 96 88;
}
```

**`tailwind.config.js`:** `darkMode: ['selector', '[data-theme="dark"]']`

**Toggle:** thêm mục trong `Settings.tsx`, lưu `localStorage['lims_theme']`, đọc trong `main.tsx` trước khi render, mặc định theo `prefers-color-scheme`.

**Cần rà thủ công:** ~10 chỗ dùng màu cứng (`bg-white`, `text-white/70` trên nền gradient) — grep `bg-white\b` và `shadow-` để kiểm.

---

## 9. Lộ trình rút gọn — nếu chỉ có 3 ngày (24h)

| Thứ tự | Task | Giờ | Được gì |
|:--:|---|---:|---|
| 1 | T0.1 + T0.2 + T0.3 + T0.4 | 2.6 | Nền tảng |
| 2 | **T2.1** DataTable thẻ | 6.0 | Sửa 27 trang |
| 3 | **T2.2** Modal sheet | 4.0 | Sửa 36 chỗ |
| 4 | T0.6 codemod `sm:`→`md:` | 1.0 | Sửa 102 token |
| 5 | **T3A** 20 lưới cứng | 4.0 | Hết vỡ form |
| 6 | T1.1 + T1.2 + T1.8 | 1.8 | +110px dọc, topbar gọn |
| 7 | T2.3 FormGrid + T2.4 Button | 1.5 | Hạ tầng + vùng chạm |
| 8 | T5.3 QA rút gọn (5 trang) | 2.0 | Xác nhận |
| | **Tổng** | **22.9** | **≈70% giá trị** |

Hoãn lại: rail sidebar (T1.4–1.5), FilterBar (T2.5), sweep T3B/T3C/T3D, màn lớn (T4).
