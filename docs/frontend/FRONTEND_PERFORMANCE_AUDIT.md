# FRONTEND PERFORMANCE AUDIT — LIMS

> Ngày audit: 2026-08-07 · Mã: `FE-P-xx`
> Số liệu lấy từ `npm run build` thật (không ước lượng).

---

## 1. Bundle — số đo thực tế

`npm run build` → **✓ built in 5.67s**, không lỗi, không cảnh báo vượt `chunkSizeWarningLimit`.

### Tải lần đầu (mọi trang, kể cả `/login`)

| Chunk | Raw | Gzip | Vì sao nằm ở đây |
|---|---:|---:|---|
| `vendor-react` | 164,78 kB | 53,75 kB | react + react-dom + react-router |
| `index` | 149,11 kB | 43,75 kB | App, AuthContext, api, rbac, Login, Dashboard, ChangePassword |
| **`vendor-charts`** | **411,20 kB** | **110,45 kB** | **recharts — modulepreload trên MỌI trang** ⚠️ |
| `vendor-icons` | 45,23 kB | 8,61 kB | lucide-react |
| `index.css` | — | — | Tailwind |
| **Tổng** | **~770 kB** | **~217 kB** | |

### Lazy (chỉ tải khi vào trang)

47/58 trang được `lazy()`. Trang nặng nhất: `SampleFlow` 46 kB (12,24 kB gzip),
`Forms` 22,97 kB, `SampleDetail` 17,15 kB. Phần lớn dưới 10 kB. **Việc tách trang làm tốt.**

---

## 2. Phát hiện

### FE-P-01 · 🟠 HIGH — `limit: 100` + phân trang phía client → **dữ liệu quá 100 dòng biến mất im lặng**

| | |
|---|---|
| **Danh mục** | Correctness (không chỉ performance) |
| **Bằng chứng** | `grep -rn "limit: 100" src/` → **51 vị trí**; `grep -rln "serverPagination" src/` → **0 file** |

`src/components/ui/DataTable.tsx:46-58` **có sẵn** chế độ phân trang server, kèm comment
giải thích chính xác vấn đề:

> *"Bật phân trang SERVER: component cha tự nạp dữ liệu theo page/limit. Không có nó, mọi
> trang gọi API với `limit: 100` rồi cắt trang ở client"*

**Không một trang nào dùng nó.** Mọi bảng đều:

```ts
// src/pages/Users.tsx:34 — mẫu lặp lại ở 51 chỗ
useAsync(() => usersApi.listUsers({ q: dq, role, limit: 100 }), [dq, role])
```

rồi truyền mảng đó cho `DataTable` không có prop `server`, nên
`DataTable.tsx:109`: `totalCount = sorted.length` — **tối đa 100**.

### Vì sao đây là lỗi đúng nghĩa, không phải "tối ưu sau"

Khi cơ sở dữ liệu có 250 người dùng:
- API trả 100 dòng đầu (backend `limit` tối đa là 100 — `Query(default=20, ge=1, le=100)`).
- Giao diện hiển thị **"1–8 / 100 bản ghi"**.
- **150 người dùng còn lại không tồn tại trong giao diện.** Không có cảnh báo, không có
  "còn nữa", không có cách nào bấm tới.
- Tìm kiếm `q` giúp thu hẹp, nhưng người dùng phải **biết** là có thứ mình chưa thấy.

Với LIMS, các bảng chắc chắn vượt 100 trong năm đầu: `samples`, `chemicals`,
`test_parameters` (bảng giá phân tích), `users`, `documents`, `audit_logs`.

### Ảnh hưởng phụ về hiệu năng

Mỗi lần vào trang tải 100 bản ghi đầy đủ (kèm quan hệ đã serialize ở backend), render 100
hàng vào DOM rồi chỉ hiện 8. Ở `Equipment.tsx` có **2** lời gọi `limit: 100` song song.

### Khắc phục

Bật `server` cho các bảng có khả năng vượt 100 — hạ tầng đã có cả hai đầu (backend nhận
`page`/`limit` và trả `meta.total`; `DataTable` nhận prop `server`). Việc còn lại là nối dây:

```tsx
const [page, setPage] = useState(1);
const [limit, setLimit] = useState(20);
const { data, meta, loading } = useAsyncPaged(
  () => usersApi.listUsers({ q: dq, role, page, limit }), [dq, role, page, limit]);

<DataTable
  server={{ page, limit, total: meta?.total ?? 0, onPageChange: setPage, onLimitChange: setLimit }}
  ... />
```

Ưu tiên theo mức độ chắc chắn vượt ngưỡng: `samples` → `test_parameters` → `chemicals` →
`documents` → `users` → `audit_logs`.

**Ưu tiên: P0** (mất dữ liệu khỏi tầm nhìn người dùng, không phải chậm)

---

### FE-P-02 · 🟡 MEDIUM — `vendor-charts` (110 kB gzip) tải trên **mọi** trang, kể cả `/login`

**File:** `vite.config.ts:12-16`, `src/App.tsx:60`

`vite.config.ts` tách recharts ra chunk riêng **có chủ đích**, comment ghi:

> *"recharts ~400KB nhưng chỉ dashboard/báo cáo dùng — tách riêng để các trang khác không
> phải kéo theo."*

**Ý đồ bị vô hiệu** bởi một dòng ở `App.tsx:60`:

```ts
import { Dashboard } from '@/pages/Dashboard';   // ← TĨNH, không lazy()
```

`Dashboard.tsx:37` `import ... from 'recharts'` → recharts trở thành phụ thuộc của chunk
entry → Rollup phát `modulepreload`. Xác nhận trong `dist/index.html`:

```html
<link rel="modulepreload" crossorigin href="/assets/vendor-charts-DABuJ_0H.js">
```

Nghĩa là người dùng mở **trang đăng nhập** cũng tải 110 kB gzip biểu đồ.

**Vì sao Dashboard được để tĩnh:** comment `App.tsx:10-12` giải thích *"Login/Dashboard/
ChangePassword giữ tĩnh vì là màn hình vào app đầu tiên"* — hợp lý về ý định (tránh nháy
Suspense sau khi đăng nhập), nhưng cái giá là recharts vào entry.

**Khắc phục — hai lựa chọn, không lựa chọn nào phá ý đồ ban đầu:**

1. **`lazy()` cho Dashboard + prefetch sau khi đăng nhập thành công.** Giữ trải nghiệm mượt
   mà không trả giá ở màn login:
   ```ts
   const Dashboard = lazy(() => import('@/pages/Dashboard'));
   // trong AuthContext.login(), sau khi thành công:
   import('@/pages/Dashboard');   // warm chunk trong lúc người dùng còn nhìn spinner
   ```
2. **Tách riêng phần biểu đồ trong Dashboard** — `lazy()` chỉ các component recharts, giữ
   phần thẻ số liệu tĩnh.

Lợi ích đo được: **−110 kB gzip** ở lần tải đầu (−50% payload khởi động).

---

### FE-P-03 · 🔵 LOW — Polling chạy mãi, không dừng khi tab ẩn

| Nguồn | Chu kỳ | File |
|---|---|---|
| Đếm thông báo chưa đọc | **30 giây** | `src/components/layout/Topbar.tsx:106` |
| Badge "Chờ duyệt" | **60 giây** | `src/lib/useNavBadges.ts:12,34` |

Cả hai đều `setInterval` thuần, **không kiểm `document.visibilityState`**. Một tab để nền cả
ngày vẫn gửi ~120 request/giờ; hai tab thì gấp đôi.

Với ~40 người dùng, tải này không đáng kể cho backend. Nhưng nó là **nguyên nhân trực tiếp**
của FE-S-02 (đua refresh đa tab): chính hai nhịp polling này bảo đảm mọi tab đều chạm 401
gần như cùng lúc khi access token hết hạn.

**Khắc phục:** bọc bằng `visibilitychange` — dừng khi ẩn, chạy ngay một lần khi hiện lại.
Vừa giảm request vừa giảm xác suất đua refresh.

---

### FE-P-04 · 🔵 LOW — Không có memo hoá ở bảng lớn, nhưng chưa phải nút thắt

`DataTable` sắp xếp/lọc bằng `useMemo`? — có `sorted` được tính trong render. Với trần 100
dòng hiện tại, chi phí không đáng kể. **Sẽ trở thành vấn đề sau khi sửa FE-P-01** nếu chuyển
sang server pagination với `limit` lớn hơn — lúc đó cân nhắc virtualization
(`@tanstack/react-virtual`) cho bảng > 200 dòng.

Không đề nghị thêm `memo`/`useCallback` đại trà — đó là tối ưu không có số đo hậu thuẫn.

---

### FE-P-05 · 🔵 LOW — Ảnh tĩnh chưa tối ưu

`public/`: `apple-touch-icon.png` 66 kB, `nlu-logo.png` 75 kB, `notification-icon-192.png`
33 kB, `ribe-logo.jpeg` 20 kB. Tổng ~200 kB.

Chỉ logo + favicon, tải một lần và được cache. Không phải nút thắt, nhưng
`apple-touch-icon` 66 kB cho ảnh 180×180 là nén kém — có thể xuống ~10 kB.

---

## 3. Network

| Kiểm tra | Kết quả |
|---|---|
| Request trùng | ⚠️ `usersApi.listUsers({limit:100})` gọi lại ở ≥6 trang, không cache (FE-A-04/FE-A-05) |
| Waterfall | ✅ Không — các `useAsync` trong cùng trang chạy song song |
| Huỷ request | ✅ `useAsync` dùng `AbortController`, huỷ thật khi deps đổi/unmount |
| Retry | ⚠️ Chỉ retry 1 lần sau `401 → refresh`. Không retry cho lỗi mạng/5xx |
| Polling | ⚠️ 30s + 60s, không dừng khi ẩn tab (FE-P-03) |
| Deduplication | ❌ Không có — hai component cùng gọi một endpoint sẽ gọi 2 lần |
| Timeout | ❌ **Không có timeout ở tầng fetch** — request treo tới khi trình duyệt bỏ cuộc |

**FE-P-06 · 🟡 MEDIUM — không có timeout cho request.** `src/lib/api.ts` không đặt
`AbortSignal.timeout()`. Backend cũng không có timeout tầng ứng dụng (xem `docs/API_AUDIT.md`
API-09). Kết quả: một truy vấn báo cáo chậm làm giao diện quay vòng **không giới hạn**, và
`useAsync` không có đường thoát. Khắc phục:
`signal: AbortSignal.any([opts.signal, AbortSignal.timeout(30_000)])` + thông báo lỗi riêng.

---

## 4. Core Web Vitals — đánh giá định tính

Không đo được LCP/INP/CLS thật trong phiên này (cần trình duyệt + dữ liệu production).
Đánh giá dựa trên cấu trúc:

| Chỉ số | Rủi ro | Lý do |
|---|---|---|
| **LCP** | 🟡 Trung bình | 217 kB gzip khởi động, trong đó 110 kB là recharts **không dùng ở màn đầu** (FE-P-02). Font từ CDN ngoài thêm 1 vòng DNS+TLS tới Google (FE-S-05) |
| **INP** | 🟢 Thấp | Không có tính toán nặng trong render; bảng tối đa 100 dòng |
| **CLS** | 🟢 Thấp | Có `LoadingState` giữ chỗ; `display=swap` cho font có thể gây dịch chuyển nhẹ khi font về |
| **TTFB** | 🟢 Thấp | Tệp tĩnh qua nginx + Cloudflare CDN |

**Ba việc cải thiện LCP theo thứ tự hiệu quả:** FE-P-02 (−110 kB) → FE-S-05 (bỏ vòng gọi
Google, tự host font) → nén ảnh (FE-P-05).

---

## 5. Đánh giá theo quy mô dữ liệu

| Quy mô | Đánh giá |
|---|---|
| **100 bản ghi/bảng** | ✅ Không vấn đề |
| **> 100 bản ghi/bảng** | ❌ **Dữ liệu biến mất khỏi giao diện** (FE-P-01) — đây là ngưỡng vỡ, không phải ngưỡng chậm |
| **10.000 bản ghi** | ❌ Như trên. Sau khi sửa FE-P-01 sang server pagination thì ổn (backend đã có index đầy đủ) |
| **40 người dùng đồng thời** | ✅ Polling 30s/60s × 40 = ~2 req/s — không đáng kể |

---

## 6. Tổng hợp

| ID | Mức | Vấn đề | Vị trí | Ưu tiên |
|---|---|---|---|---|
| FE-P-01 | 🟠 HIGH | `limit:100` + phân trang client → mất dữ liệu quá 100 dòng | 51 vị trí; `DataTable.tsx:46` | **P0** |
| FE-P-02 | 🟡 MEDIUM | recharts 110 kB gzip tải ở mọi trang kể cả `/login` | `App.tsx:60`, `vite.config.ts:12` | P1 |
| FE-P-06 | 🟡 MEDIUM | Không có timeout request | `lib/api.ts:136` | P1 |
| FE-P-03 | 🔵 LOW | Polling không dừng khi tab ẩn | `Topbar.tsx:106`, `useNavBadges.ts:34` | P2 |
| FE-P-04 | 🔵 LOW | Chưa virtualization (chỉ cần sau khi sửa FE-P-01) | `DataTable.tsx` | P3 |
| FE-P-05 | 🔵 LOW | Ảnh tĩnh nén kém | `public/` | P3 |

## 7. Điều làm ĐÚNG

- **Code splitting thật sự có tác dụng**: 47/58 trang lazy, chunk trang trung bình < 10 kB.
- **`manualChunks` tách vendor** để đổi một trang không bắt tải lại toàn bộ.
- **`AbortController` trong `useAsync`** — huỷ thật ở tầng mạng, không chỉ bỏ qua kết quả.
- **Build sạch**: 5,67s, 0 cảnh báo, 0 source map.
- **Chỉ 7 runtime dependency** — không có "bloat" từ UI kit.
