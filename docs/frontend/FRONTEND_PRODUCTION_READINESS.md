# FRONTEND PRODUCTION READINESS — LIMS

> Ngày đánh giá: **2026-08-07** · Nhánh `main` @ `3df1e6e`
> Phạm vi: `lims-frontend/` (30.110 LOC, 58 page, 60 route) + `Dockerfile` + `nginx.conf`.
> Đối chiếu với backend: `docs/SECURITY_AUDIT.md`, `docs/API_AUDIT.md`.

---

## 0. Kết luận

> ## ❌ **NOT READY FOR PRODUCTION — 82/140 (≈ 59/100)**
>
> **Không tìm thấy lỗ hổng CRITICAL.** Bề mặt XSS gần bằng không, không có secret trong
> bundle, phân quyền lấy từ server chứ không giải mã JWT, API client tập trung và viết tốt.
>
> Kết luận NOT READY **không đến từ bảo mật ứng dụng**, mà từ bốn thứ định lượng được:
>
> 1. **Dữ liệu quá 100 dòng biến mất khỏi giao diện, không có cảnh báo** (FE-P-01).
> 2. **Lỗi API hiển thị thành "không có dữ liệu" ở 48/49 trang** (FE-U-01) — người dùng ra
>    quyết định vận hành trên thông tin sai mà hệ thống trình bày như sự thật.
> 3. **Không có một security header nào** cho tài liệu HTML (FE-S-01).
> 4. **Không có một dòng test nào** và **không có error tracking nào** (mục 5, 6).
>
> Ba trong bốn mục trên sửa được trong **2–3 ngày công**. Sau nhóm P0, điểm dự kiến ~104/140
> (≈75/100) = **CONDITIONALLY READY**.

---

## 1. Bảng trạng thái theo hạng mục

| Area | Status | Severity | Finding | Action |
|---|---|---|---|---|
| **Architecture** | ✅ | - | Phân lớp sạch: 0 lời gọi `fetch()` ngoài `lib/api.ts`; không vòng phụ thuộc; 47/58 trang lazy; 7 runtime dependency | Giữ nguyên |
| **Architecture — nguồn quyền** | ⚠️ | MEDIUM | `nav.ts` (`roles`) và `lib/rbac.ts` (`canXxx`) là **hai** danh sách vai trò viết độc lập → đã lệch ở `/quotations` (đã vá) và **`/documents/stats`** (chưa) | `nav.ts` dùng lại chính hàm `canXxx`; thêm test đối chiếu |
| **Security — headers** | ❌ | **HIGH** | `nginx.conf` có **đúng 1** `add_header` (Cache-Control cho `/assets/`). Không CSP, không X-Frame-Options, không nosniff, không Referrer-Policy, không HSTS. Middleware bảo mật của backend **chỉ áp cho `/api/`**, không cho tài liệu HTML | Thêm khối header + CSP vào `nginx.conf` (~30 phút) |
| **Security — XSS** | ✅ | - | **0** `dangerouslySetInnerHTML`, **0** `innerHTML`, **0** `eval`. Chỉ 1 `document.write` (`samplePdf.ts`) và nó có hàm `esc()` | Vá 2 điểm nội suy số chưa escape (FE-S-08) |
| **Security — secrets** | ✅ | - | Chỉ `VITE_API_BASE_URL` được inline (URL công khai). Không source map ở production. 1 `console.error` có chủ đích | Giữ nguyên |
| **Security — bên thứ ba** | ⚠️ | MEDIUM | Google Fonts từ CDN — gửi IP + Referer tới Google mỗi lần tải trang, và buộc nới CSP. Toàn bộ phần còn lại là self-hosted sau tunnel | Tự host font Inter |
| **Security — dependency** | ⚠️ | MEDIUM | 5 lỗ (2 high, 3 moderate): `postcss` (build-time, không ship) + `react-router` open-redirect. Đã kiểm: **không có đường điều hướng nào người dùng điều khiển được** → chưa khai thác được | `npm audit fix` (patch bump, không phá API) |
| **Authentication — luồng** | ✅ | - | Bearer + cookie refresh HttpOnly/Secure/SameSite=Strict/Path hẹp; gộp refresh trong tab; logout xoá token; khôi phục phiên khi reload | Giữ nguyên |
| **Authentication — đa tab** | ❌ | **HIGH** | `refreshPromise` là biến **module scope = mỗi tab một bản**. Không có khoá chéo tab. Với TTL access token 10 phút + polling 30s/60s mỗi tab, hai tab chạm 401 cùng lúc → cả hai gọi `/auth/refresh` với cùng cookie → backend `with_for_update` tuần tự hoá → request thứ hai kích hoạt **reuse detection → thu hồi TOÀN BỘ phiên của người dùng** | Web Locks API + đồng bộ token qua sự kiện `storage` |
| **Authorization** | ⚠️ | MEDIUM | Nguồn đúng: đọc `permissions` từ `/auth/me`, **không** giải mã JWT ở client ✅. Nhưng nhiều helper viết `hasPermission(...) \|\| !!user` — vế thứ hai vô hiệu hoá vế đầu (`canViewChemicals`, `canViewNC`, `canViewRisk`, `canViewImprovement`) | Bỏ `\|\| !!user` khi ma trận quyền đã đủ; nếu chưa đủ thì sửa ma trận, không sửa điều kiện |
| **Authorization — biên** | ✅ | - | `RequireAccess` chỉ ẩn UI; mọi endpoint đều được backend kiểm lại. Không có chỗ nào coi route guard là biên bảo mật | Giữ nguyên |
| **API Integration** | ✅ | - | Client tập trung duy nhất: base URL từ env, `x-correlation-id` mỗi request, unwrap `{success,data,meta}`, 401→refresh→retry×1, `Idempotency-Key` tự sinh, `AbortController` | Giữ nguyên |
| **API — timeout** | ❌ | MEDIUM | **Không có timeout** ở tầng fetch. Backend cũng không có (API-09). Mất mạng giữa chừng = spinner quay vô hạn | `AbortSignal.timeout(30_000)` |
| **API — mã lỗi** | ✅ | - | `lib/errors.ts` map ~150 mã → tiếng Việt; 5xx ẩn chi tiết + hiện correlationId; 401/403/409/422/429 đều có thông điệp riêng | Giữ nguyên |
| **State Management** | ⚠️ | MEDIUM | `useAsync` chống race đúng (sequence + AbortController) ✅. Nhưng không có cache dùng chung, không invalidation chéo trang → mutation ở trang A không làm mới trang B; badge trễ tới 60s | Chấp nhận ở quy mô hiện tại; ghi nhận giới hạn |
| **Business Logic UI** | ✅ | - | Không có booking/lịch. State machine (phiếu nhận mẫu, tài liệu, CAPA, báo giá) do backend enforce; UI ẩn nút theo trạng thái. Không tìm thấy optimistic update nào ⇒ không có rủi ro rollback sai | Giữ nguyên |
| **Concurrency / stale data** | ⚠️ | MEDIUM | Không có version conflict UI. Backend trả 409 `VERSION_CONFLICT` và `errors.ts` đã có thông điệp *"Một phiên bản khác vừa được ban hành. Vui lòng tải lại"* ✅ — nhưng không tự `reload()` sau 409 | Sau 409, gọi `reload()` tự động |
| **Form validation** | ⚠️ | LOW | Không dùng thư viện/schema; validate bằng `if` rải rác, một số form dựa hẳn vào 400 từ backend. `Field` có prop `error` nhưng nhiều form không truyền | Chuẩn hoá dần; backend luôn là authority ✅ |
| **File upload** | ⚠️ | MEDIUM | FE có `accept=` + giới hạn kích thước. **Nhưng backend chỉ tin `Content-Type` client khai, không kiểm magic bytes** (`docs/SECURITY_AUDIT.md` S-06) — FE không thể bù được | Sửa ở backend (P1 backend) |
| **Loading / Empty / Error** | ❌ | **HIGH** | Có `LoadingState` (27 trang) + `EmptyState` (27 trang). **Không có `ErrorState`** và **48/49 trang bỏ qua `error` của `useAsync`** → 500/mất mạng/403 đều hiện "Không có dữ liệu" | Thêm `ErrorState` + `if (error) return <ErrorState onRetry={reload}/>` |
| **UX — hành động phá huỷ** | ✅ | - | `ConfirmDialog` phủ hết thao tác xoá, có `loading`, có toast thành công/lỗi | Giữ nguyên |
| **UX — double submit** | ⚠️ | LOW | 57 vị trí `disabled={submitting}` ✅. `Idempotency-Key` **không** chặn double-click (mỗi click = key mới — comment `api.ts:206` ghi rõ) | Sinh key một lần trong `useRef` cho form tạo bản ghi |
| **UX — 404** | ⚠️ | MEDIUM | `path="*"` → `Navigate to="/dashboard"`. Link hỏng âm thầm về Dashboard | Thêm trang NotFound |
| **Performance — bundle** | ⚠️ | MEDIUM | Khởi động ~217 kB gzip, trong đó **110 kB là recharts** được `modulepreload` trên **mọi** trang kể cả `/login`, vì `Dashboard` import tĩnh ở `App.tsx:60` — vô hiệu hoá chính `manualChunks` đã tách nó ra | `lazy()` Dashboard + prefetch sau login |
| **Performance — danh sách** | ❌ | **HIGH** | **51** vị trí gọi `limit: 100` rồi cắt trang ở client; **0** trang dùng `DataTable server` (dù `DataTable.tsx:46` đã hỗ trợ và comment cảnh báo đúng vấn đề này). Vượt 100 bản ghi ⇒ phần dư **không hiển thị, không cảnh báo**, và UI vẫn ghi "/100 bản ghi" như thể đó là tổng | Bật server pagination cho các bảng chắc chắn vượt 100 |
| **Performance — polling** | ⚠️ | LOW | 30s (thông báo) + 60s (badge) mỗi tab, không dừng khi tab ẩn — cũng là nguyên nhân trực tiếp của đua refresh đa tab | Bọc `visibilitychange` |
| **Accessibility** | ⚠️ | MEDIUM | Nền tảng tốt: skip link, focus trap, không chặn zoom, `lang="vi"`, `<main>`, 53 `aria-*`. **Nhưng `ui/Field.tsx` render `<label>` không `htmlFor` và ô nhập không `id`** → 0 kết quả `htmlFor` trên 25 `<input>`; lỗi validate không có `aria-describedby`/`role="alert"` | Sửa **một** file `Field.tsx` (useId + htmlFor + aria-*) → phủ ~30 form |
| **Responsive** | ✅ | - | Có `RESPONSIVE_PLAN/IMPLEMENTATION/TESTPLAN.md` + `scripts/check-responsive.mjs` chạy trong CI. Drawer mobile + safe-area iPhone | Kiểm thủ công trên thiết bị vẫn cần — **UNKNOWN** trong audit này |
| **Testing** | ❌ | **HIGH** | **Không có hạ tầng test nào.** Không vitest/jest/testing-library/playwright/cypress. `package.json` script `lint` thực ra là `tsc -b --force` (type-check, không phải lint). Chỉ có `check-responsive.mjs` kiểm bất biến tĩnh | Dựng Vitest + Playwright; ưu tiên E2E âm tính cho phân quyền |
| **Observability** | ❌ | MEDIUM | Không Sentry/GlitchTip/bất kỳ error tracking nào. Lỗi render chỉ `console.error` trong `ErrorBoundary` — **không ai thấy**. Không đo Core Web Vitals. Không bắt `unhandledrejection` | Dựng error tracking self-hosted (GlitchTip) — có `correlationId` sẵn để nối với log backend |
| **Deployment — Docker** | ⚠️ | LOW | Multi-stage ✅ (node:22-alpine build → nginx:1.27-alpine runtime), image nhỏ ✅, tag ghim ✅. nginx master chạy **root** (mặc định image) | `USER nginx` + nginx unprivileged nếu siết thêm |
| **Deployment — nginx** | ⚠️ | MEDIUM | SPA fallback đúng ✅ (`try_files ... /index.html` — refresh `/samples/123` không 404). Cache `/assets/` immutable ✅. gzip ✅. **Nhưng: không security header (FE-S-01) và `index.html` không có `Cache-Control: no-cache`** → trình duyệt có thể giữ HTML cũ trỏ tới bundle hash đã xoá sau deploy | Thêm header + `location = /index.html { add_header Cache-Control "no-cache"; }` |
| **Deployment — HTTPS** | ✅ | - | TLS kết thúc ở biên Cloudflare qua tunnel; origin không mở cổng nào | Giữ nguyên |
| **Build** | ✅ | - | `npm run build` → **✓ 5,67s**, 0 lỗi, 0 cảnh báo vượt ngưỡng chunk, 0 source map | Bỏ giá trị mặc định `localhost` của build arg (FE-S-11) |
| **Env variables** | ✅ | - | Đúng **một** biến được expose: `VITE_API_BASE_URL` — public đúng loại. Không có secret nào mang prefix `VITE_` | Giữ nguyên |
| **SEO / indexing** | ⚠️ | LOW | Không có `robots.txt`; SPA trả `index.html` cho mọi path → trang đăng nhập có thể bị lập chỉ mục | Thêm `public/robots.txt` |
| **Browser storage** | ⚠️ | MEDIUM | `lims_access_token` (localStorage — nợ có chủ đích, TTL 10 phút, refresh token ở cookie HttpOnly ✅). **Nháp báo cáo tháng (`MonthlyReport`) không bị xoá khi logout** — dữ liệu nghiệp vụ còn lại trên máy dùng chung | Dọn khoá `lims_*` trong `logout()` |
| **PWA / Service Worker** | ✅ | - | `sw.js` **không cache gì**, chỉ push + notificationclick; URL điều hướng cố định nội bộ. Quyết định đúng cho dữ liệu nhạy cảm | Giữ nguyên |

---

## 2. Ma trận phân quyền (theo vai trò THẬT của hệ thống)

7 vai trò: `admin`, `leader`, `reception`, `qms`, `lab_manager`, `staff`, `office`
(`src/lib/rbac.ts:ROLE_OPTIONS`).

| Hành động | admin | leader | reception | qms | lab_manager | staff | office | Hàm quyết định |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|---|
| Xem mẫu thử nghiệm | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | `canViewSamples` |
| Phân công / duyệt kết quả | ✓ | ✓ | ✓¹ | ✗ | ✓ | ✓² | ✗ | `canAssignSample` / `canApproveResult` |
| Nhận & chuyển mẫu | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | `canViewIntake` / `canManageIntake` |
| Xem giá hoá chất | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | `canViewCost` |
| Giao dịch kho hoá chất | ✓ | — | — | — | — | ✓³ | ✗ | `canTransactChemical` |
| Duyệt tài liệu | ✓ | ✓ | ✗ | ✓ | ✓ | ✓² | ✗ | `canApproveDocuments` |
| Ghi thiết bị / hiệu chuẩn | ✓ | ✗ | ✗ | ✗ | ✓⁴ | ✗ | ✗ | `canWriteEquipment(Dept)` |
| Quản lý CAPA / rủi ro | ✓ | ✓ | ✗ | ✗ | ✗ | ✓⁵ | ✗ | `canManageCapa` / `canManageRisk` |
| Xem báo giá | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | `canViewQuotations` *(đã vá)* |
| Hồ sơ nhân sự (danh sách) | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ | `canListHr` |
| Sửa lương / hợp đồng | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | `canEditSalary` |
| Quản lý tài khoản | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | `canManageUsers` |
| Nhật ký hệ thống | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | `canViewAudit` |
| **Thống kê truy cập tài liệu** | ✓ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ✗ | `canViewDocumentStats` — **menu chỉ hiện cho admin nhưng route + backend cho 6 vai trò** |

¹ `reception` điều phối mẫu tới phòng lab nhưng không duyệt kết quả · ² chỉ khi `is_dept_lead`
· ³ qua permission `chemical:transact` · ⁴ chỉ phòng của mình (`canWriteEquipmentDept`)
· ⁵ chỉ khi `is_quality_manager`

**Bất nhất phát hiện được:** ô ⚠️ ở dòng cuối — xem FE-S-06/FE-A-01. Đây là ca thứ hai của
cùng một mẫu lỗi đã gây ra sự cố `/quotations`.

---

## 3. Luồng người dùng quan trọng — kiểm theo 8 tình huống

| Flow | Đường thường | Validate lỗi | Mạng hỏng | Thiếu quyền | Hết phiên | Sửa đồng thời | Gửi trùng | Lỗi backend |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Đăng nhập → Dashboard | ✅ | ✅ | ❌¹ | — | ✅ | — | ✅ | ✅ |
| Nhận mẫu (tạo phiếu) | ✅ | ⚠️² | ❌¹ | ✅ | ⚠️³ | ⚠️⁴ | ⚠️⁵ | ✅ |
| Chuyển mẫu → phòng lab | ✅ | ⚠️² | ❌¹ | ✅ | ⚠️³ | ⚠️⁴ | ⚠️⁵ | ✅ |
| Nhập & duyệt kết quả | ✅ | ✅ | ❌¹ | ✅ | ⚠️³ | ✅⁶ | ⚠️⁵ | ✅ |
| Duyệt tài liệu | ✅ | ✅ | ❌¹ | ✅ | ⚠️³ | ✅⁶ | ⚠️⁵ | ✅ |
| Nộp báo cáo tháng | ✅ | ⚠️² | ❌¹ | ✅ | ⚠️³ | — | ✅ | ✅ |
| Tải tệp đính kèm | ✅ | ✅ | ❌¹ | ✅ | ⚠️⁷ | — | — | ✅ |
| Quản trị tài khoản | ✅ | ✅ | ❌¹ | ✅ | ⚠️³ | ⚠️⁴ | ⚠️⁵ | ✅ |

¹ Không timeout → spinner vô hạn (FE-U-03) · ² Validate rải rác, một số dựa hẳn vào 400
· ³ Có thể bị đăng xuất toàn hệ thống do đua refresh đa tab (FE-S-02) · ⁴ Không tự reload sau
409 · ⁵ `disabled` chặn được, `Idempotency-Key` thì không (FE-U-05) · ⁶ Backend trả 409, có
thông điệp tiếng Việt rõ · ⁷ `apiUpload` không đăng xuất khi refresh hỏng (FE-S-09)

---

## 4. Điểm số

| Hạng mục | Điểm | Lý do |
|---|---:|---|
| **Architecture** | **8**/10 | Phân lớp sạch, 1 API client, không vòng phụ thuộc, 7 dependency. Trừ: hai nguồn quyền, 3 file quá lớn |
| **Security** | **5**/10 | XSS ~0, không secret, không source map, không open redirect. Trừ nặng: **0 security header**, Google Fonts ngoài, 5 CVE dependency |
| **Authentication** | **6**/10 | Luồng chuẩn (Bearer + cookie HttpOnly/Strict, gộp refresh, logout xoá token). Trừ nặng: đua refresh đa tab làm mất **toàn bộ** phiên, lặp lại mỗi 10 phút |
| **Authorization** | **6**/10 | Nguồn đúng (`/auth/me`, không đọc JWT). Trừ: 2 nguồn sự thật, `\|\| !!user` vô hiệu hoá kiểm quyền, `/documents/stats` lệch |
| **API Integration** | **9**/10 | Xuất sắc: tập trung, correlation-id, refresh, abort, idempotency, unwrap. Trừ: không timeout |
| **State Management** | **7**/10 | `useAsync` chống race đúng. Trừ: không cache, không invalidation chéo trang |
| **Business Logic** | **7**/10 | State machine do backend giữ, UI phản ánh đúng, không optimistic update rủi ro. Trừ: không tự reload sau 409 |
| **Performance** | **5**/10 | Code splitting tốt, build sạch, abort thật. Trừ nặng: **mất dữ liệu > 100 dòng**, recharts tải ở mọi trang |
| **UX** | **7**/10 | Bản đồ 150 mã lỗi, ConfirmDialog đầy đủ, loading/empty phủ rộng. Trừ nặng: **lỗi hiện thành "không có dữ liệu"**, không 404 |
| **Accessibility** | **7**/10 | Skip link, focus trap, không chặn zoom, 53 aria. Trừ: `Field` không nối label — ảnh hưởng mọi form |
| **Testing** | **1**/10 | **Không có test nào.** Chỉ script kiểm responsive tĩnh |
| **Deployment** | **5**/10 | Multi-stage, tag ghim, SPA fallback đúng, HTTPS qua tunnel. Trừ: **0 security header**, index.html không no-cache, nginx root |
| **Observability** | **2**/10 | Có `ErrorBoundary` + correlationId hiển thị cho người dùng. Nhưng **không error tracking**, không Web Vitals, không bắt `unhandledrejection` |
| **Maintainability** | **7**/10 | TypeScript strict, comment giải thích "vì sao", CI có kiểm kích thước file + responsive. Trừ: file lớn, không test |

### Tổng: **82 / 140** (≈ **59 / 100**)

```
Production Status:  ❌ NOT READY FOR PRODUCTION
```

**Theo thang điểm đã cho:** `<60 = NOT READY`. Điểm 59 nằm ngay dưới ngưỡng, và bị kéo xuống
chủ yếu bởi **Testing (1)** và **Observability (2)** — hai hạng mục không gây sự cố bảo mật
ngày đầu nhưng khiến mọi sự cố sau đó không phát hiện được.

**Điều quan trọng phải nói rõ:** đây **không** phải kết luận "frontend viết kém". Chất lượng
mã ở tầng API client, xử lý lỗi, chống race và responsive **cao hơn mặt bằng chung rõ rệt**.
Vấn đề nằm ở bốn khoảng trống cụ thể, ba trong số đó sửa trong vài giờ mỗi cái.

**Sau khi hoàn thành P0** (ước tính 2–3 ngày): Security 5→7, Performance 5→7, UX 7→9,
Deployment 5→7, Authentication 6→8 → **~104/140 (≈75/100) = ⚠️ CONDITIONALLY READY**.
Đạt `PRODUCTION READY WITH MINOR FIXES` cần thêm P1 + hạ tầng test tối thiểu.

---

## 5. TOP 10 RỦI RO nếu deploy hôm nay

Sắp theo khả năng gây sự cố thực tế × mức thiệt hại.

| # | Rủi ro | Loại | Vì sao đứng ở đây |
|---|---|---|---|
| **1** | **Danh sách > 100 dòng mất dữ liệu âm thầm** (FE-P-01) | Data integrity | Xảy ra **chắc chắn** trong năm đầu với `samples`/`test_parameters`/`documents`. KTV nhìn danh sách trống/thiếu và kết luận sai. Không có bất kỳ dấu hiệu nào |
| **2** | **Lỗi API hiện thành "không có dữ liệu"** (FE-U-01) | Data integrity / UX | 48/49 trang. Backend 500 hoặc Redis chết → mọi màn hình báo "không có dữ liệu" thay vì "hệ thống lỗi". Quyết định vận hành trên thông tin sai |
| **3** | **Đua refresh đa tab thu hồi toàn bộ phiên** (FE-S-02) | Auth / Reliability | Lặp **mỗi 10 phút** với người mở ≥2 tab. Mất công việc đang nhập dở. Đã có thông điệp `TOKEN_REUSED` trong code ⇒ nhiều khả năng đã xảy ra thật |
| **4** | **Không một security header nào** (FE-S-01) | Security | Clickjacking trên hệ thống mà một click = "duyệt kết quả". Và không có CSP giới hạn thiệt hại nếu về sau xuất hiện XSS — trong khi token nằm ở localStorage |
| **5** | **Không có test nào** | Reliability | 60 route, 7 vai trò, 0 test. Mọi thay đổi phân quyền đều không có lưới chắn. Chính lớp lỗi "nav.ts lệch rbac.ts" là thứ một test đối chiếu bắt được trong 1 giây |
| **6** | **Không có error tracking** | Observability | Lỗi JS ở máy người dùng **không ai biết**. `ErrorBoundary` chỉ `console.error`. Sự cố chỉ được phát hiện khi có người gọi điện báo |
| **7** | **Không timeout request → spinner vô hạn** (FE-U-03/FE-P-06) | UX / Reliability | Wi-Fi phòng lab chập chờn là điều kiện bình thường, không phải ngoại lệ |
| **8** | **`/documents/stats` lộ dữ liệu giám sát cho 4 vai trò** (FE-S-06) | Security | Menu chỉ cho admin, nhưng route **và backend** cho 6 vai trò đọc ai-tải-tài-liệu-nào. Ca thứ hai của mẫu lỗi đã gây sự cố `/quotations` |
| **9** | **Google Fonts gửi metadata ra ngoài** (FE-S-05) | Privacy | Hệ thống ISO 17025 self-hosted sau tunnel, nhưng mỗi lần tải trang vẫn báo cho Google biết ai đang dùng LIMS, ở đâu, trang nào |
| **10** | **`Field` không nối label ↔ ô nhập** (FE-AC-01) | Accessibility | Vi phạm WCAG 1.3.1/3.3.2 trên **toàn bộ** form. Sửa **một** file là xong — tỉ lệ lợi ích/công sức cao nhất trong báo cáo |

---

## 6. Deployment checklist

### SECURITY
```
[✓] Authentication verified — Bearer + cookie HttpOnly/Secure/SameSite=Strict
[⚠] Authorization verified — đúng nguồn (/auth/me) nhưng 2 nguồn sự thật; /documents/stats lệch
[✓] No secrets in frontend — chỉ VITE_API_BASE_URL (public)
[⚠] No sensitive token leakage — token ở localStorage (TTL 10p, refresh ở cookie)
[✓] XSS reviewed — 0 dangerouslySetInnerHTML / innerHTML / eval
[✗] CSP configured — KHÔNG CÓ
[✗] Security headers configured — KHÔNG CÓ (1 add_header duy nhất là Cache-Control)
[⚠] Dependencies audited — 5 lỗ; react-router chưa khai thác được, postcss build-time
```

### API
```
[✓] Production API URL — /api/v1 same-origin qua nginx (build arg)
[✓] HTTPS — Cloudflare Tunnel
[✗] Timeout — KHÔNG CÓ
[✓] Error handling — lib/errors.ts, ~150 mã
[✓] 401 handling — refresh → retry ×1 → logout
[✓] 403 handling — thông điệp riêng + RequireAccess
[✓] 429 handling — RATE_LIMIT_EXCEEDED có thông điệp
```

### UX
```
[✓] Loading states — LoadingState/Skeleton ở 27 trang
[✓] Empty states — EmptyState ở 27 trang
[✗] Error states — KHÔNG CÓ ErrorState; 48/49 trang bỏ qua error
[✓] Mobile responsive — có plan/implementation/testplan + script CI (chưa kiểm thiết bị thật)
[⚠] Accessibility — nền tảng tốt; label chưa nối ô nhập
[⚠] Duplicate submission prevention — disabled ✓, Idempotency-Key không chặn double-click
```

### PERFORMANCE
```
[✓] Production build — 5,67s, 0 lỗi, 0 source map
[⚠] Bundle reviewed — 217 kB gzip khởi động, 110 kB là recharts không dùng ở màn đầu
[✓] Code splitting — 47/58 trang lazy
[✗] Large lists optimized — 51 chỗ limit:100 + phân trang client; 0 chỗ dùng server pagination
[⚠] Images optimized — apple-touch-icon 66 kB cho ảnh 180×180
[⚠] API requests optimized — không cache, listUsers gọi lại ở ≥6 trang, polling không dừng khi ẩn tab
```

### DEPLOYMENT
```
[⚠] Docker reviewed — multi-stage ✓, tag ghim ✓, nginx chạy root
[⚠] Nginx reviewed — SPA fallback ✓, gzip ✓, cache assets ✓, KHÔNG security header
[✓] SPA fallback — try_files ... /index.html (refresh deep link không 404)
[⚠] Cache headers — /assets/ immutable ✓; index.html KHÔNG có no-cache
[✗] Security headers
[✓] HTTPS — TLS ở biên Cloudflare, origin không mở cổng
[✗] Monitoring — không có
[✗] Error tracking — không có
```

### TESTING
```
[✗] Login E2E
[✗] Booking E2E — (hệ thống không có booking; tương đương: Nhận & Chuyển mẫu)
[✗] Approval E2E
[✗] Admin E2E
[✗] Permission negative tests  ← quan trọng nhất, và là thứ đã để lọt lỗ hổng /quotations
[✗] Network failure tests
```
**0/6.** Không có hạ tầng test nào để chạy chúng.
