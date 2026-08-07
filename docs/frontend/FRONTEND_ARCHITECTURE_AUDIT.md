# FRONTEND ARCHITECTURE AUDIT — LIMS

> Ngày audit: 2026-08-07 · Phạm vi: `lims-frontend/` (30.110 LOC TS/TSX, 58 page, 34 component, 22 API module)
> Phương pháp: đọc mã nguồn thực tế, chạy `npm run build`, `npm audit`, đối chiếu với backend.
> Mã phát hiện: `FE-A-xx` (architecture).

---

## 1. Stack thực tế

| Lớp | Công nghệ | Ghi chú |
|---|---|---|
| Framework | **React 18.3.1** (không SSR) | SPA thuần |
| Ngôn ngữ | TypeScript 5.9.3, `strict` (xem `tsconfig.app.json`) | |
| Build | **Vite 5.4.11** + `@vitejs/plugin-react` | build 5,67s |
| Router | **react-router-dom 6.30.4** | `BrowserRouter`, 60 route |
| State | **KHÔNG có thư viện** — `useState` + Context (Auth, Toast) | xem FE-A-04 |
| Data fetching | **`useAsync` tự viết** (`src/lib/useAsync.ts`) — KHÔNG React Query/SWR | xem FE-A-05 |
| API client | **`src/lib/api.ts`** — wrapper `fetch` duy nhất | ✅ tập trung |
| Form | **KHÔNG có thư viện** — `useState` thủ công | xem FE-A-06 |
| UI | Tự viết (`src/components/ui/`) + **lucide-react** icons | không dùng MUI/AntD |
| Styling | **Tailwind CSS 3.4** + `clsx` + `tailwind-merge` | |
| Charts | **recharts 2.15.4** | xem FRONTEND_PERFORMANCE FE-P-02 |
| Toast | Context tự viết (`ToastContext`) | |
| Error boundary | Tự viết (`components/ErrorBoundary.tsx`) | |
| Upload | `apiUpload` / `apiUploadForm` trong api.ts | |
| Push/SW | `public/sw.js` — **chỉ Web Push, không cache gì** | ✅ xem FE-A-08 |
| WebSocket/SSE | ❌ Không có — dùng **polling** | xem FE-P-03 |
| Test | ❌ **Không có hạ tầng test nào** | xem FRONTEND_PRODUCTION_READINESS |
| Deploy | Docker multi-stage → **nginx 1.27-alpine** | |

**Runtime dependency chỉ có 7 gói.** Đây là điểm mạnh đáng kể: bề mặt tấn công chuỗi cung
ứng nhỏ, không kéo theo hàng trăm transitive dependency như dự án dùng UI kit lớn.

---

## 2. Kiến trúc thực tế

```
                         Browser
                            │
              ┌─────────────▼─────────────┐
              │  main.tsx                  │
              │   BrowserRouter            │
              │    └ ErrorBoundary         │  ← bắt lỗi render, hiện correlationId
              │       └ ToastProvider      │
              │          └ AuthProvider    │  ← GET /auth/me → CurrentUser + permissions
              │             └ App          │
              └─────────────┬─────────────┘
                            │
                    ┌───────▼────────┐
                    │  App.tsx        │  60 Route · 47 trang lazy()
                    │  <Suspense>     │
                    └───────┬────────┘
                            │
        ┌───────────────────┴────────────────────┐
        │                                         │
   Route CÔNG KHAI                        <AppShell>  ← CHỐT XÁC THỰC
   /login /register                         │  if (!user) → /login
   /forgot-password                         │  if (mustChangePassword) → /change-password
   /reset-password /verify-email            │
   /change-password  ⚠️ FE-A-03             ├─ Sidebar (nav.ts — nguồn quyền #1)
                                            ├─ Topbar  (poll 30s)
                                            └─ <Outlet>
                                                 │
                                        ┌────────▼─────────┐
                                        │ <RequireAccess    │  ← CHỐT PHÂN QUYỀN
                                        │   allow={canXxx}> │     (rbac.ts — nguồn quyền #2)
                                        └────────┬─────────┘
                                                 │
                                            Page component
                                                 │
                                     ┌───────────▼───────────┐
                                     │ useAsync(fn, deps)     │
                                     │  seq + AbortController │
                                     └───────────┬───────────┘
                                                 │
                                     ┌───────────▼───────────┐
                                     │ src/api/*.ts (22 file) │
                                     └───────────┬───────────┘
                                                 │
                                     ┌───────────▼────────────────────┐
                                     │ src/lib/api.ts                  │
                                     │  · Bearer từ localStorage        │
                                     │  · x-correlation-id mỗi request  │
                                     │  · credentials: include (cookie) │
                                     │  · 401 → doRefresh() → retry ×1  │
                                     │  · unwrap {success,data,meta}    │
                                     │  · Idempotency-Key tự sinh (POST)│
                                     └───────────┬────────────────────┘
                                                 │ same-origin /api/v1
                                     ┌───────────▼───────────┐
                                     │ nginx (lims-web)       │
                                     │  /api/ → lims-api:8060 │
                                     └────────────────────────┘
```

**Khác biệt so với sơ đồ chuẩn:** không có tầng "State/Query" tách biệt. Server state được
giữ **cục bộ trong từng page** qua `useAsync`; không có cache dùng chung, không có
invalidation chéo trang. Xem FE-A-05.

---

## 3. Cấu trúc thư mục

```
src/
├── api/         22 file — một file/module nghiệp vụ, chỉ gọi lib/api.ts   ✅
├── components/
│   ├── ui/      18 primitive (Button, Card, Modal, DataTable, States…)    ✅
│   ├── layout/  AppShell, Sidebar, Topbar, Footer, nav.ts
│   ├── forms/   FormFileManager
│   ├── hr/      HrProfileView
│   ├── sampleFlow/ IntakeCreateModal
│   ├── profile/, users/
│   ├── ErrorBoundary.tsx, RequireAccess.tsx
├── context/     AuthContext, ToastContext                                  ✅
├── lib/         api, rbac, errors, format, useAsync, useFocusTrap, …       ✅
├── pages/       58 file
├── types/       index.ts (1.949 dòng)                                      ⚠️ FE-A-02
└── main.tsx, App.tsx, index.css
```

Không có `stores/`, `schemas/`, `services/` — hợp lý cho quy mô này (không có global store,
không dùng zod).

**Đánh giá separation of concerns: TỐT.** Không tìm thấy lời gọi `fetch()` trực tiếp nào
ngoài `lib/api.ts`; mọi trang đều đi qua `src/api/*`. Đây là kỷ luật hiếm thấy ở codebase
30k dòng.

---

## 4. Phát hiện

### FE-A-01 · 🟠 HIGH — Hai nguồn sự thật cho phân quyền UI

| | |
|---|---|
| **File** | `src/components/layout/nav.ts` (thuộc tính `roles`) vs `src/lib/rbac.ts` (hàm `canXxx`) |
| **Loại** | Architectural weakness → đã sinh ra lỗ hổng thật |

`nav.ts` quyết định **menu nào hiện**; `rbac.ts` + `RequireAccess` quyết định **route nào vào
được**. Hai danh sách vai trò được viết **độc lập** và đã lệch nhau:

| Route | `nav.ts` cho thấy menu | `RequireAccess` cho vào | Backend cho phép |
|---|---|---|---|
| `/quotations` | admin, leader, reception, office | ~~`!!user` (mọi vai trò)~~ | ~~mọi vai trò~~ |
| **`/documents/stats`** | **`admin`** | `canViewDocumentStats` = mọi vai trò **trừ** office | mọi vai trò **trừ** office (`document_service.py:622`) |
| `/customers` | admin, leader, reception | `!!user && !office` | admin, leader, staff, reception, lab_manager |
| `/equipment` | admin, leader, lab_manager, office | `!!user && role !== 'staff'` | — |

Dòng `/quotations` đã được vá trong phiên làm việc trước (cả FE lẫn BE). **Mẫu lỗi thì
chưa** — `/documents/stats` là ca giống hệt còn nguyên: menu chỉ hiện cho `admin`, nhưng
`staff`/`qms`/`lab_manager`/`reception` gõ thẳng URL vẫn vào được **và backend cũng cho
qua**, đọc được thống kê ai tải tài liệu nào, khi nào.

**Vì sao là vấn đề kiến trúc chứ không phải 2 lỗi rời rạc:** mỗi khi thêm một trang, lập
trình viên phải nhớ khai quyền ở **ba** nơi (nav.ts, RequireAccess, backend) và không có gì
đối chiếu chúng. Xác suất lệch tăng tuyến tính theo số trang.

**Khắc phục:** để `nav.ts` **dùng lại chính hàm `canXxx`** thay vì tự khai `roles`:
```ts
{ to: '/documents/stats', label: 'Thống kê truy cập TL', can: canViewDocumentStats }
```
Một nguồn sự thật cho UI; backend vẫn là authority. Kèm test đối chiếu mọi mục nav có route
tương ứng và cùng vị từ quyền.

**Ưu tiên: P1** (bản thân việc lộ `/documents/stats` cần vá ở backend — P1).

---

### FE-A-02 · 🟡 MEDIUM — File quá lớn ở 3 chỗ

| File | Dòng | Vấn đề |
|---|---:|---|
| `src/types/index.ts` | **1.949** | Mọi type của 12 module trong một file. Sửa type của module A làm invalidate build cache của tất cả |
| `src/pages/SampleFlow.tsx` | **1.208** | Một trang chứa 3 tab nghiệp vụ (intake / dispatch / info-request) + nhiều modal |
| `src/pages/SampleDetail.tsx` | 948 | |

Dự án **đã có** `scripts/check-file-size.mjs` chạy trong CI (workflow `architecture.yml`) và
`IntakeCreateModal` đã được tách ra khỏi `SampleFlow` (commit `da54b51`) — nghĩa là cơ chế
tồn tại và đang được dùng, chỉ chưa áp hết.

**Không phải lỗi**, không đề nghị refactor vì "gọn hơn". Chỉ nêu vì `SampleFlow.tsx` là
trang nghiệp vụ trung tâm (nhận & chuyển mẫu) — nơi mọi thay đổi đều rủi ro nhất.

---

### FE-A-03 · 🔵 LOW — `/change-password` nằm ngoài `AppShell`

`src/App.tsx:110` đặt route này cùng nhóm với `/login`, `/register` — tức **ngoài chốt xác
thực**. Người chưa đăng nhập mở `/change-password` sẽ thấy form, gõ xong bấm gửi và nhận
lỗi 401 khó hiểu thay vì bị đưa về trang đăng nhập.

Không phải lỗ hổng (backend từ chối), nhưng là đường dẫn tới trạng thái UI vô nghĩa.

---

### FE-A-04 · 🔵 LOW — Không có global store: đánh đổi hợp lý, có chi phí

Chỉ 2 Context (Auth, Toast). Mọi state server nằm trong page. Với 58 trang chủ yếu là
CRUD + bảng, đây là lựa chọn **đúng** — thêm Redux/Zustand sẽ là phức tạp không cần thiết.

Chi phí phải chấp nhận: dữ liệu dùng chung được fetch lại ở nhiều trang. Ví dụ
`usersApi.listUsers({ limit: 100 })` xuất hiện ở **≥6 trang** (Users, ResearchProjects,
Equipment, …) — mỗi lần vào trang là một request mới, không cache.

---

### FE-A-05 · 🟡 MEDIUM — Không có cache/invalidation chéo trang

`useAsync` (`src/lib/useAsync.ts`) được viết rất tốt cho phạm vi của nó: số thứ tự tăng dần
chống race + `AbortController` huỷ thật ở tầng mạng + bỏ qua `AbortError`. Nhưng nó chỉ
quản lý **một lời gọi trong một component**.

Hệ quả cụ thể:
- Không có cache → mỗi lần điều hướng là fetch lại từ đầu (không có `staleTime`).
- **Không có invalidation chéo màn hình.** Tạo phiếu chuyển mẫu ở `SampleFlow` không làm mới
  badge "Chờ duyệt" ở Sidebar — badge tự làm mới sau tối đa 60 giây (`useNavBadges.ts:12`).
- Mỗi trang tự gọi `reload()` sau mutation. Nếu quên, dữ liệu cũ nằm lại cho tới khi F5.

**Không đề nghị đưa React Query vào ngay** — đó là thay đổi lớn. Nêu ra để biết giới hạn:
hệ thống hiện đúng ở mức "mỗi trang tự lo", và mọi tính năng cần đồng bộ nhiều màn hình sẽ
phải tự dựng cơ chế.

---

### FE-A-06 · 🔵 LOW — Form thủ công, không có schema validation

Không dùng react-hook-form/formik/zod. Mỗi form tự `useState` + validate bằng `if`.
Với ~30 form, việc này tạo ra kiểm tra không đồng nhất (xem FRONTEND_UX_AUDIT FE-U-04).

Đánh đổi chấp nhận được ở quy mô này, nhưng chi phí tăng theo số form.

---

### FE-A-07 · ✅ Không có circular dependency

`npm run build` (Vite/Rollup) hoàn tất **không cảnh báo vòng phụ thuộc**. Hướng phụ thuộc
sạch: `pages → api → lib/api`, `pages → components/ui`, `lib/rbac` không import ngược.

---

### FE-A-08 · ✅ Service Worker phạm vi tối thiểu — đúng

`public/sw.js` chỉ đăng ký `push` + `notificationclick`, **không cache gì**
(dòng 2 ghi rõ). Với hệ thống có dữ liệu nhạy cảm, đây là quyết định đúng: không có rủi ro
cache response API chứa dữ liệu cá nhân/kết quả thử nghiệm vào Cache Storage rồi còn lại
sau khi đăng xuất.

`notificationclick` chỉ dùng URL nội bộ cố định (`data: { url: '/notifications' }`), không
nhận URL từ payload push → không có đường mở URL tuỳ ý.

---

## 5. Tổng hợp

| ID | Mức | Vấn đề | Vị trí | Ưu tiên |
|---|---|---|---|---|
| FE-A-01 | 🟠 HIGH | Hai nguồn sự thật phân quyền UI; `/documents/stats` lệch | `nav.ts` vs `lib/rbac.ts` | P1 |
| FE-A-02 | 🟡 MEDIUM | 3 file quá lớn (types 1.949, SampleFlow 1.208) | `types/index.ts`, `pages/SampleFlow.tsx` | P2 |
| FE-A-05 | 🟡 MEDIUM | Không cache/invalidation chéo trang | `lib/useAsync.ts` | P2 |
| FE-A-03 | 🔵 LOW | `/change-password` ngoài chốt xác thực | `App.tsx:110` | P2 |
| FE-A-04 | 🔵 LOW | Fetch trùng dữ liệu dùng chung ở ≥6 trang | `pages/*` | P3 |
| FE-A-06 | 🔵 LOW | Form thủ công, không schema | `pages/*` | P3 |

## 6. Điều làm ĐÚNG (ghi nhận để không phá)

- **Một API client duy nhất.** 0 lời gọi `fetch()` ngoài `lib/api.ts`.
- **Phân quyền lấy từ `/auth/me`, KHÔNG giải mã JWT ở client.** Không tìm thấy `atob`,
  `jwt-decode` hay bất kỳ chỗ nào đọc payload token để quyết định quyền — đúng nguyên tắc.
- **`useAsync` chống race đúng cách** (sequence + AbortController), có comment giải thích
  lỗi cũ mà nó sửa.
- **Bản đồ mã lỗi → tiếng Việt** (`lib/errors.ts`, ~150 mã), 5xx ẩn chi tiết + hiện
  correlationId để tra log. Trên mức trung bình ngành rõ rệt.
- **Lazy-load 47/58 trang** với lý do được ghi trong code.
- **Service worker không cache** — quyết định đúng cho dữ liệu nhạy cảm.
- **Chỉ 7 runtime dependency.**
