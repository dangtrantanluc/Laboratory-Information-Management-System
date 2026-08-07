# FRONTEND REMEDIATION PLAN — LIMS

> Nguồn: `FRONTEND_ARCHITECTURE_AUDIT.md` (FE-A), `FRONTEND_SECURITY_AUDIT.md` (FE-S),
> `FRONTEND_PERFORMANCE_AUDIT.md` (FE-P), `FRONTEND_UX_AUDIT.md` (FE-U/FE-AC).
> Ước lượng: **người-ngày** cho một lập trình viên đã quen codebase.
>
> **Chưa sửa gì trong đợt audit này** — đúng quy tắc "audit trước, sửa sau".

---

## P0 — MUST FIX BEFORE DEPLOY

> Tổng: **2–3 ngày**. Sau nhóm này điểm dự kiến ~104/140 (≈75/100) = CONDITIONALLY READY.

### P0-1 · Security header + CSP cho nginx (FE-S-01) — **30 phút**

Việc rẻ nhất, phạm vi bảo vệ rộng nhất trong toàn báo cáo.

```nginx
# lims-frontend/nginx.conf — cấp server, TRƯỚC các location
add_header X-Frame-Options           "DENY"                                     always;
add_header X-Content-Type-Options    "nosniff"                                  always;
add_header Referrer-Policy           "strict-origin-when-cross-origin"          always;
add_header Permissions-Policy        "geolocation=(), microphone=(), camera=()" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains"      always;
add_header Content-Security-Policy   "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'" always;

# index.html KHÔNG được cache: bundle có hash, nhưng HTML trỏ tới hash thì phải luôn mới
location = /index.html {
    add_header Cache-Control "no-cache" always;
}
```

**Ba cạm bẫy phải biết trước khi sửa:**
1. nginx **không kế thừa** `add_header` vào `location` đã có `add_header` riêng.
   `location /assets/` đang có `Cache-Control` → phải lặp lại bộ header ở đó (hoặc dùng
   module `headers-more`). **Kiểm bằng `curl -I` cho cả 3 đường:** `/`, `/assets/x.js`,
   `/lims-attachments/...`.
2. `style-src 'unsafe-inline'` là **bắt buộc** — Tailwind + React style attribute.
   `script-src` thì **không cần** `unsafe-inline`/`unsafe-eval`: đã kiểm `dist/index.html`
   chỉ có `<script type="module" src=...>`.
3. Hai host Google chỉ cần khi còn dùng Google Fonts. Làm **P1-3 trước** thì CSP siết được
   về `'self'` hoàn toàn.

**Kiểm chứng:** `curl -sI https://<domain>/ | grep -iE "content-security|x-frame|nosniff"`
và mở DevTools → Console không có CSP violation nào khi đi hết các trang chính.

---

### P0-2 · Bật server pagination cho các bảng vượt 100 dòng (FE-P-01) — **1–1,5 ngày**

Đây là mục **mất dữ liệu**, không phải mục hiệu năng.

Hạ tầng đã có sẵn cả hai đầu — chỉ thiếu dây nối:
- Backend nhận `page`/`limit`, trả `meta.total` ✅
- `DataTable.tsx:46-58` đã hỗ trợ prop `server` ✅ (và comment ở đó mô tả đúng vấn đề này)
- `apiGetPaged` trả `{data, meta}` ✅

```tsx
// Mẫu áp dụng — pages/Users.tsx
const [page, setPage] = useState(1);
const [limit, setLimit] = useState(20);
const { data, loading, error, reload } = useAsync(
  () => usersApi.listUsersPaged({ q: dq, role, page, limit }),
  [dq, role, page, limit],
);

<DataTable
  rows={data?.data ?? []}
  loading={loading}
  server={{
    page, limit,
    total: data?.meta?.total ?? 0,
    onPageChange: setPage,
    onLimitChange: (l) => { setLimit(l); setPage(1); },
  }}
/>
```

**Thứ tự ưu tiên theo mức chắc chắn vượt 100 trong năm đầu:**

| # | Trang | Vì sao |
|---|---|---|
| 1 | `SampleRequests` / `SampleDetail` | Mẫu thử nghiệm — tăng nhanh nhất |
| 2 | `TestParameters` | Bảng giá phân tích, đã có sẵn hàng trăm chỉ tiêu |
| 3 | `Documents` | Tài liệu kiểm soát ISO |
| 4 | `Chemicals` | |
| 5 | `AuditLogs` | Đã 855 dòng sau 12 ngày |
| 6 | `Users`, `Equipment`, `Customers` | Chậm hơn nhưng sẽ tới |

**Lưu ý khi sửa:** `q`/filter đổi phải `setPage(1)`, nếu không người dùng ở trang 5 lọc lại
sẽ thấy trống. Và `useAsync` đã có `AbortController` nên đổi trang nhanh không gây race.

**Chốt an toàn tạm thời (15 phút, làm ngay cả khi chưa xong toàn bộ):** khi
`rows.length === 100`, hiện cảnh báo trong `DataTable`:
*"Chỉ hiển thị 100 bản ghi đầu — hãy dùng bộ lọc để thu hẹp."* Không sửa được gốc nhưng
**xoá bỏ tình trạng mất dữ liệu âm thầm** ngay lập tức.

---

### P0-3 · `ErrorState` + xử lý `error` ở mọi trang (FE-U-01) — **0,5 ngày**

```tsx
// src/components/ui/States.tsx
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { title, description } = describeError(error);   // đã có sẵn, ~150 mã lỗi
  return (
    <EmptyState
      icon={<AlertTriangle size={22} className="text-overdue" />}
      title={title}
      description={description ?? 'Không tải được dữ liệu. Vui lòng thử lại.'}
      action={onRetry && <Button variant="secondary" onClick={onRetry}>Thử lại</Button>}
    />
  );
}
```

Rồi ở mỗi trang (2 dòng):
```tsx
const { data, loading, error, reload } = useAsync(...);
if (error) return <ErrorState error={error} onRetry={reload} />;
```

49 trang. Ưu tiên trang ra quyết định vận hành trước: `SampleRequests`, `SampleFlow`,
`Documents`, `DocumentPendingReview`, `Nonconformities`, `Risks`, `Equipment`, `Chemicals`.

**Kiểm chứng:** tắt `lims-api` (`docker compose ... stop lims-api`) rồi mở từng trang — phải
thấy thông báo lỗi + nút Thử lại, **không** thấy "Không có dữ liệu".

---

### P0-4 · Khoá refresh chéo tab (FE-S-02) — **0,5 ngày**

```ts
// src/lib/api.ts
async function doRefresh(): Promise<boolean> {
  const tokenAtCall = getToken();

  const run = async (): Promise<boolean> => {
    // Tab khác vừa refresh xong → token đã đổi, không cần gọi lại.
    if (getToken() !== tokenAtCall) return true;
    return doRefreshOnce();          // phần thân hiện tại
  };

  if (!('locks' in navigator)) return run();          // fallback trình duyệt cũ
  return navigator.locks.request('lims-token-refresh', run);
}
```

Bổ sung đồng bộ token giữa các tab:
```ts
window.addEventListener('storage', (e) => {
  if (e.key === TOKEN_KEY && e.newValue === null) onSessionExpired?.();
});
```

**Vì sao đây là P0 chứ không phải P1:** lặp **mỗi 10 phút** (TTL access token production) với
bất kỳ ai mở ≥2 tab, và hậu quả là **thu hồi toàn bộ phiên trên mọi thiết bị** — mất dữ liệu
đang nhập dở.

**Kiểm chứng:** mở 2 tab, đợi token hết hạn (hoặc tạm hạ `ACCESS_TOKEN_TTL_MINUTES=1`), xác
nhận **không** xuất hiện thông báo *"Phát hiện dùng lại phiên cũ"*.

Làm cùng lúc **P1-5** (dừng polling khi tab ẩn) sẽ giảm mạnh xác suất đua ngay cả trước khi
khoá có tác dụng.

---

### P0-5 · Timeout cho mọi request (FE-U-03 / FE-P-06) — **1 giờ**

```ts
// src/lib/api.ts — trong rawRequest()
const timeout = AbortSignal.timeout(30_000);
const signal = opts.signal ? AbortSignal.any([opts.signal, timeout]) : timeout;
```
Kèm thông điệp riêng trong `errors.ts` cho `TimeoutError` → *"Máy chủ không phản hồi. Vui
lòng kiểm tra kết nối và thử lại."*

Không có mục này, `ErrorState` ở P0-3 **không bao giờ hiện** khi mất mạng — trang cứ quay
mãi vì `useAsync` không bao giờ settle.

---

## P1 — FIX BEFORE PRODUCTION (2–3 tuần đầu)

| # | Việc | Nguồn | Công |
|---|---|---|---|
| **P1-1** | **Vá `/documents/stats`.** Chốt danh sách vai trò với nghiệp vụ rồi áp **đồng thời** ở `nav.ts` + `rbac.canViewDocumentStats` + backend `document_service.aggregate_access_stats:622` (hiện chỉ chặn `office`). Ưu tiên siết **backend trước** — nơi duy nhất là authority | FE-S-06, FE-A-01 | 0,25đ |
| **P1-2** | **`nav.ts` dùng lại hàm `canXxx` thay vì tự khai `roles`** → một nguồn sự thật. Kèm test đối chiếu: mọi mục nav phải có route tương ứng và cùng vị từ quyền. Đây là biện pháp chặn **lớp lỗi** đã gây ra `/quotations` và `/documents/stats` | FE-A-01 | 0,5đ |
| **P1-3** | **Tự host font Inter** (`@fontsource/inter` hoặc chép `.woff2` vào `public/`). Gỡ 2 `<link>` Google khỏi `index.html`. Cho phép siết CSP về `'self'` hoàn toàn | FE-S-05 | 0,25đ |
| **P1-4** | **`npm audit fix`** — patch bump `react-router-dom` và `postcss`. **Không** `--force` (sẽ nhảy react-router 7 = breaking). Chạy `npm run build` + đi hết luồng chính sau khi bump | FE-S-04 | 0,25đ |
| **P1-5** | **Dừng polling khi tab ẩn.** Bọc `Topbar.tsx:106` (30s) và `useNavBadges.ts:34` (60s) bằng `document.visibilityState`; chạy ngay một lần khi tab hiện lại | FE-P-03 | 0,25đ |
| **P1-6** | **`lazy()` Dashboard + prefetch sau login.** Bỏ 110 kB gzip recharts khỏi lần tải đầu (−50% payload khởi động) mà vẫn giữ trải nghiệm mượt | FE-P-02 | 0,25đ |
| **P1-7** | **Sửa `ui/Field.tsx`**: `useId()` + `htmlFor` + `aria-describedby` + `aria-invalid` + `role="alert"` cho thông báo lỗi. **Một file, phủ ~30 form** | FE-AC-01 | 0,5đ |
| **P1-8** | **Trang 404** thay cho `Navigate to="/dashboard"`; nêu rõ đường dẫn không tồn tại | FE-U-02 | 0,25đ |
| **P1-9** | **Error tracking self-hosted** (GlitchTip — tương thích SDK Sentry, chạy được trong compose). Nối `correlationId` sẵn có của `lib/api.ts` vào scope để ghép với log backend. **Bắt buộc lọc** `Authorization`, body có mật khẩu, và PII trước khi gửi | Observability | 1đ |
| **P1-10** | **Bắt `unhandledrejection`** ở `main.tsx` → gửi error tracking + toast chung | Observability | 0,25đ |
| **P1-11** | **`robots.txt`** `Disallow: /` | FE-S-10 | 5 phút |
| **P1-12** | **Bỏ mặc định `localhost` của build arg** trong `Dockerfile`; thất bại tường minh khi thiếu `VITE_API_BASE_URL` | FE-S-11 | 15 phút |
| **P1-13** | **Tự `reload()` sau 409** `VERSION_CONFLICT` — thông điệp đã đúng nhưng người dùng phải tự F5 | Concurrency | 0,25đ |

---

## P2 — FIX AFTER DEPLOY

| # | Việc | Nguồn | Công |
|---|---|---|---|
| **P2-1** | **Hạ tầng test: Vitest + Testing Library.** Ưu tiên tuyệt đối cho `lib/rbac.ts` — 40+ hàm quyền thuần, không cần DOM, test cực rẻ và bảo vệ đúng thứ đã hai lần lọt lỗi | Testing | 1đ |
| **P2-2** | **Playwright E2E cho 6 luồng**: đăng nhập → dashboard · nhận mẫu → chuyển mẫu · nhập → duyệt kết quả · duyệt tài liệu · quản trị tài khoản · **`staff` KHÔNG vào được `/users`, `/audit`, `/quotations`** (âm tính) | Testing | 2đ |
| **P2-3** | **Test mạng hỏng**: chặn API bằng `page.route()`, khẳng định hiện `ErrorState` chứ không phải "không có dữ liệu" | Testing | 0,5đ |
| **P2-4** | **Dọn `localStorage` khi logout** — xoá mọi khoá `lims_activity_report_draft:*` | FE-S-07 | 0,25đ |
| **P2-5** | **Bỏ `\|\| !!user`** trong `canViewChemicals`/`canViewNC`/`canViewRisk`/`canViewImprovement`. Nếu ma trận `roles_permissions` chưa đủ thì **sửa ma trận**, không nới điều kiện | FE-A-01 | 0,5đ |
| **P2-6** | **Escape 2 điểm còn lại trong `samplePdf.ts`** (dòng 114, 128) | FE-S-08 | 15 phút |
| **P2-7** | **`apiUpload` gọi `onSessionExpired()`** khi refresh hỏng — đồng bộ với 3 hàm còn lại | FE-S-09 | 15 phút |
| **P2-8** | **`Idempotency-Key` một lần/form**: `useRef` sinh key khi mở form tạo phiếu nhận mẫu / báo giá / giao dịch kho, dùng lại cho mọi lần gửi | FE-U-05 | 0,5đ |
| **P2-9** | **`/change-password` vào trong `AppShell`** (hoặc guard riêng) | FE-A-03 | 15 phút |
| **P2-10** | **`Dashboard.tsx:514`** → `<button>` thay `<div onClick>` | FE-AC-02 | 15 phút |
| **P2-11** | **nginx chạy non-root** (`nginxinc/nginx-unprivileged` hoặc `USER nginx`) | Deployment | 0,5đ |
| **P2-12** | **Token vào memory-only** thay localStorage; refresh khi mở tab mới. Chỉ nên làm **sau** P0-1 (CSP) và P0-4 (khoá refresh) vì cả hai đã hạ phần lớn rủi ro | FE-S-03 | 1đ |
| **P2-13** | **Banner offline** + tự thử lại khi `online` | FE-U-03 | 0,5đ |

---

## P3 — NICE TO HAVE

| # | Việc | Nguồn |
|---|---|---|
| P3-1 | Tách `src/types/index.ts` (1.949 dòng) theo module | FE-A-02 |
| P3-2 | Tách `SampleFlow.tsx` (1.208 dòng) theo tab nghiệp vụ | FE-A-02 |
| P3-3 | Cân nhắc React Query/SWR cho cache + invalidation chéo trang — **chỉ khi** nhu cầu đồng bộ nhiều màn hình xuất hiện thật, không làm vì "chuẩn" | FE-A-05 |
| P3-4 | Chuẩn hoá validate form (zod + react-hook-form) | FE-U-04 / FE-A-06 |
| P3-5 | Virtualization cho bảng > 200 dòng — **chỉ sau** P0-2 | FE-P-04 |
| P3-6 | Nén ảnh `public/` (apple-touch-icon 66 kB → ~10 kB) | FE-P-05 |
| P3-7 | Đo Core Web Vitals thật (`web-vitals` → error tracking) | Observability |
| P3-8 | Thêm ESLint thật — script `lint` hiện chỉ là `tsc -b --force` (type-check) | Maintainability |

---

## Lịch trình

```
Tuần 0 (trước deploy)  ██████     P0-1 … P0-5        2–3 ngày   → điều kiện go-live
Tuần 1–3               ████████   P1-1 … P1-13      ~4 ngày    → vận hành an toàn
Tháng 2–3              ██████     P2-1 … P2-13      ~8 ngày    → test + củng cố
Quý 2+                 ████       P3-1 … P3-8        dài hạn
```

**Thứ tự trong P0 theo tỉ lệ lợi ích/công sức:**

| # | Mục | Công | Vì sao ở vị trí này |
|---|---|---|---|
| 1 | **P0-1** security header | 30 phút | Rẻ nhất, phạm vi rộng nhất |
| 2 | **P0-2 (chốt tạm)** cảnh báo "chỉ hiển thị 100 bản ghi đầu" | 15 phút | Xoá bỏ **mất dữ liệu âm thầm** ngay, trước khi làm bản đầy đủ |
| 3 | **P0-5** timeout | 1 giờ | Điều kiện tiên quyết để P0-3 có tác dụng khi mất mạng |
| 4 | **P0-3** ErrorState | 0,5đ | |
| 5 | **P0-4** khoá refresh chéo tab | 0,5đ | |
| 6 | **P0-2 (đầy đủ)** server pagination | 1–1,5đ | Lớn nhất, làm sau khi các mục rẻ đã xong |

---

## Định nghĩa "xong" cho P0

- [ ] `curl -sI https://<domain>/` trả về `Content-Security-Policy`, `X-Frame-Options: DENY`,
      `X-Content-Type-Options: nosniff` — **và** kiểm cả `/assets/*.js` (nginx không kế thừa
      `add_header` vào location đã có header riêng)
- [ ] DevTools Console: **0** CSP violation khi đi hết Dashboard → Mẫu → Tài liệu → Báo cáo
- [ ] Bảng có > 100 bản ghi: hoặc phân trang server đúng, hoặc **có cảnh báo rõ ràng** rằng
      danh sách bị cắt
- [ ] `docker compose ... stop lims-api` → mọi trang chính hiện **thông báo lỗi + nút Thử
      lại**, không trang nào hiện "Không có dữ liệu"
- [ ] Ngắt mạng giữa lúc tải → sau ≤30 giây hiện lỗi timeout, **không** quay vô hạn
- [ ] Mở 2 tab, đợi hết TTL access token → **không** xuất hiện *"Phát hiện dùng lại phiên cũ"*;
      cả hai tab tiếp tục hoạt động
- [ ] `npm run build` sạch; `dist/` không có `.map`
