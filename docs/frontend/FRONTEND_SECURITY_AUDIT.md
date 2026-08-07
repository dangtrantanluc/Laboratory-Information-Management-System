# FRONTEND SECURITY AUDIT — LIMS

> Ngày audit: 2026-08-07 · Mã: `FE-S-xx`
> Phân loại: **[XÁC NHẬN]** = đọc mã và truy được đường khai thác · **[RỦI RO]** = phụ thuộc
> điều kiện triển khai · **[KHUYẾN NGHỊ]** = hardening.
>
> Nguyên tắc áp dụng xuyên suốt: **route guard không phải biên bảo mật**, **validate ở
> frontend không phải validate bảo mật**, **ẩn nút không phải phân quyền**. Mọi phát hiện
> dưới đây đều được đối chiếu với việc backend có chặn hay không.

---

## 0. Tóm tắt

| Mức | Số | Mã |
|---|---|---|
| 🔴 CRITICAL | **0** | — |
| 🟠 HIGH | 2 | FE-S-01, FE-S-02 |
| 🟡 MEDIUM | 5 | FE-S-03 … FE-S-07 |
| 🔵 LOW | 4 | FE-S-08 … FE-S-11 |
| ⚪ INFO | 3 | FE-S-12 … FE-S-14 |

**Không có CRITICAL.** Bề mặt XSS gần như bằng không (0 `dangerouslySetInnerHTML`, 0
`innerHTML`, 0 `eval`), không có secret trong bundle, không có open-redirect param, phân
quyền lấy từ server chứ không giải mã JWT, logout xoá token.

Hai HIGH đều thuộc **tầng triển khai**, không phải logic ứng dụng: thiếu toàn bộ security
header, và điều kiện đua refresh token đa tab làm người dùng bị đăng xuất toàn hệ thống.

---

## FE-S-01 · 🟠 HIGH — nginx phục vụ SPA KHÔNG có một security header nào **[XÁC NHẬN]**

| | |
|---|---|
| **Danh mục** | Security headers / Clickjacking / Thiếu lớp phòng vệ XSS |
| **File** | `lims-frontend/nginx.conf` |

### Bằng chứng

```
$ grep -c "add_header" lims-frontend/nginx.conf
1
$ grep -n "add_header" lims-frontend/nginx.conf
49:        add_header Cache-Control "public, immutable";     ← chỉ cache cho /assets/
```

**Không có:** `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`,
`Referrer-Policy`, `Permissions-Policy`, `Strict-Transport-Security`.

### Vì sao backend không bù được

`app/middleware/security_headers.py` của backend đặt đủ bộ header — **nhưng chỉ cho response
của API** (`/api/v1/*`). Tài liệu HTML, JS bundle, CSS và đường tải file
`/lims-attachments/` do nginx phục vụ, **không đi qua middleware đó**.

Docstring của middleware backend còn ghi rõ: *"Frontend SPA phục vụ qua nginx riêng có CSP
riêng"* — **CSP riêng đó chưa từng được viết**.

### Ảnh hưởng cụ thể

1. **Clickjacking.** Không `X-Frame-Options` / `frame-ancestors` → trang có thể nhúng iframe
   từ site bất kỳ. Trong LIMS, một cú click = "Duyệt kết quả thử nghiệm", "Đóng CAPA",
   "Xoá thiết bị". UI redressing biến thao tác phê duyệt ISO 17025 thành cú click bị lừa.
2. **Không có lưới chắn cho XSS.** Bề mặt XSS hiện tại rất nhỏ (xem FE-S-12), nhưng CSP là
   lớp phòng thủ *khi* lớp đầu thủng. Kết hợp với FE-S-02 (token trong localStorage), một
   XSS bất kỳ trong tương lai = chiếm tài khoản trọn vẹn, không có gì cản.
3. **`/lims-attachments/` không có `nosniff`.** Backend chỉ chấp nhận MIME theo khai báo của
   client (SECURITY_AUDIT backend S-06 — không kiểm magic bytes). Tệp lưu với
   `Content-Type: application/pdf` nhưng nội dung là HTML, phục vụ same-origin, không
   `nosniff` → tăng rủi ro trình duyệt suy diễn kiểu.

### Khắc phục

```nginx
# lims-frontend/nginx.conf — đặt ở cấp server
add_header X-Frame-Options            "DENY"                       always;
add_header X-Content-Type-Options     "nosniff"                    always;
add_header Referrer-Policy            "strict-origin-when-cross-origin" always;
add_header Permissions-Policy         "geolocation=(), microphone=(), camera=()" always;
add_header Strict-Transport-Security  "max-age=31536000; includeSubDomains" always;
add_header Content-Security-Policy "
  default-src 'self';
  script-src  'self';
  style-src   'self' 'unsafe-inline' https://fonts.googleapis.com;
  font-src    'self' https://fonts.gstatic.com;
  img-src     'self' data: blob:;
  connect-src 'self';
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
  object-src 'none';
" always;
```

**Ba lưu ý bắt buộc khi áp dụng:**
- `style-src 'unsafe-inline'` là **cần thiết** — Tailwind + React inline style attribute.
  Không dùng được `unsafe-eval` hay `unsafe-inline` cho `script-src`: Vite build production
  không cần cả hai (đã kiểm `dist/index.html` — chỉ có `<script type="module" src=...>`).
- `fonts.googleapis.com` / `fonts.gstatic.com` phải có mặt **chỉ khi** vẫn giữ Google Fonts.
  Tự host font (FE-S-05) cho phép siết CSP về `'self'` hoàn toàn.
- `add_header` trong nginx **không kế thừa** vào `location` nào đã có `add_header` riêng —
  `location /assets/` đang có `Cache-Control` nên phải lặp lại bộ header ở đó, hoặc dùng
  `always` + kiểm tra lại bằng `curl -I`.

**Ưu tiên: P0** — chi phí ~30 phút, phạm vi bảo vệ rộng nhất trong toàn bộ báo cáo này.

---

## FE-S-02 · 🟠 HIGH — Đua refresh token đa tab làm thu hồi TOÀN BỘ phiên **[XÁC NHẬN]**

| | |
|---|---|
| **Danh mục** | Authentication / Availability |
| **File** | `src/lib/api.ts:85-114` (`refreshPromise`, `doRefresh`) |

### Vấn đề

```ts
let refreshPromise: Promise<boolean> | null = null;   // ← module scope = MỖI TAB một biến
```

Cơ chế gộp refresh chỉ hoạt động **trong một tab**. Không có `BroadcastChannel`, không có
Web Locks, không có cờ trong `localStorage`.

### Đường hỏng — tái dựng từ mã của cả hai phía

```
Người dùng mở 2 tab LIMS (rất thường: danh sách mẫu + chi tiết mẫu)
   │
   │  Mỗi tab tự polling độc lập:
   │    Topbar.tsx:106      setInterval(getUnreadCount, 30_000)
   │    useNavBadges.ts:34  setInterval(load, 60_000)
   │
   ▼  ACCESS_TOKEN_TTL_MINUTES = 10 (docker-compose.prod.yml:210)
Sau 10 phút, access token hết hạn. Nhịp poll kế tiếp ở CẢ HAI tab → 401
   │
   ├─ Tab A: doRefresh() → POST /auth/refresh, cookie R1
   └─ Tab B: doRefresh() → POST /auth/refresh, cookie R1   (cùng lúc, cùng cookie)
   │
   ▼  Backend auth_service.refresh() — với with_for_update() nên TUẦN TỰ HOÁ
Tab A thắng lock: R1.revoked_at = now, cấp R2 + access token mới
Tab B vào lock sau: đọc R1 → revoked_at KHÁC NULL
   │
   ▼  auth_service.py:253-280 — reuse detection
UPDATE refresh_tokens SET revoked_at = now()
  WHERE user_id = ? AND revoked_at IS NULL     ← THU HỒI MỌI PHIÊN CỦA USER
→ 401 TOKEN_REUSED
   │
   ▼
Cả hai tab (và mọi thiết bị khác của người này) bị đăng xuất.
errors.ts hiển thị: "Phát hiện dùng lại phiên cũ. Vì an toàn, vui lòng đăng nhập lại."
```

### Vì sao đây là XÁC NHẬN chứ không phải giả thuyết

- `with_for_update()` ở `auth_service.py:244` **bảo đảm** hai request đồng thời bị tuần tự
  hoá, nên request thứ hai **chắc chắn** thấy `revoked_at` đã set — không phải "có thể".
- `TOKEN_REUSED` đã có sẵn trong bản đồ thông báo `src/lib/errors.ts` — nghĩa là trạng thái
  này đã được gặp trong thực tế đủ để cần một câu tiếng Việt riêng.
- Nhịp lặp là **10 phút một lần, cả ngày làm việc**, với bất kỳ ai mở từ 2 tab trở lên.

### Ảnh hưởng

Không phải lỗ hổng bảo mật — cơ chế reuse detection của backend đang làm **đúng việc của
nó**. Đây là lỗi tích hợp phía client: người dùng bị đăng xuất ngẫu nhiên giữa lúc nhập
liệu. Với `MonthlyReport` (biểu mẫu dài, có nháp localStorage) hoặc form nhập kết quả thử
nghiệm, đó là mất công việc đang dở.

### Khắc phục

Khoá refresh **chéo tab**. Web Locks API (Chrome/Edge/Firefox/Safari 15.4+ — đủ cho môi
trường nội bộ):

```ts
async function doRefresh(): Promise<boolean> {
  if (!('locks' in navigator)) return doRefreshUnlocked();   // fallback
  return navigator.locks.request('lims-token-refresh', async () => {
    // Tab vào sau đã có token mới do tab trước ghi vào localStorage → không refresh lại.
    const before = getToken();
    if (before && before !== tokenAtCallTime) return true;
    return doRefreshUnlocked();
  });
}
```
Kèm `window.addEventListener('storage', …)` để tab khác nhận token mới ngay khi có.

**Ưu tiên: P0**

---

## FE-S-03 · 🟡 MEDIUM — Access token trong `localStorage` **[RỦI RO]**

**File:** `src/lib/api.ts:14-22` — khoá `lims_access_token`.

Token nằm ở nơi **mọi script cùng origin đọc được**. Đây là nợ kỹ thuật đã được ghi nhận có
chủ đích trong `DEPLOY_LINUX.md`: *"Access token nằm trong localStorage — XSS lấy được token.
Đã cân nhắc chuyển sang bộ nhớ nhưng dừng có chủ đích."*

**Đánh giá thật của audit này — không nâng lên HIGH, và đây là lý do:**

| Yếu tố | Trạng thái |
|---|---|
| Bề mặt XSS | **Gần bằng không** — 0 `dangerouslySetInnerHTML`, 0 `innerHTML`, 0 `eval`, 0 `new Function` (FE-S-12) |
| Script bên thứ ba | Chỉ Google Fonts (CSS, không phải JS) — xem FE-S-05 |
| TTL access token | **10 phút** (production) — cửa sổ dùng lại hẹp |
| Refresh token | **Không** ở localStorage — nằm trong cookie HttpOnly + Secure + SameSite=Strict + Path=/api/v1/auth ✅ |
| Xoá khi logout | ✅ `api/auth.ts:33` gọi `setToken(null)` |

Nghĩa là: kẻ tấn công phải **trước tiên** có XSS, mà hiện không có đường nào. Rủi ro là
*điều kiện*, không phải *hiện hữu*.

**Nhưng nó khuếch đại mọi lỗi tương lai**, và hiện **không có CSP** nào giới hạn thiệt hại
(FE-S-01). Vì vậy: **sửa FE-S-01 trước** là biện pháp giảm rủi ro rẻ nhất; chuyển token vào
memory-only là việc lớn hơn (cần refresh khi mở tab mới) và có thể xếp sau.

**Ưu tiên: P2** (P0 cho FE-S-01 đã hạ phần lớn rủi ro).

---

## FE-S-04 · 🟡 MEDIUM — `react-router-dom` 6.30.4 dính CVE open redirect **[RỦI RO]**

```
react-router  6.0.0 - 7.17.0  (moderate)
  GHSA-wrjc-x8rr-h8h6 — Open redirect via backslash in <Link> and useNavigate
                         (bypass của CVE-2025-68470)
  GHSA-337j-9hxr-rhxg — Arbitrary Constructor Injection via deserializeErrors()
                         (SSR hydration)
```

**Khả năng khai thác trong dự án này: THẤP — đã kiểm từng đường điều hướng động:**

| Vị trí | Đích điều hướng | Nguồn |
|---|---|---|
| `App.tsx:98` `navigate(event.data.url)` | luôn là `/notifications` | do `public/sw.js:39` đặt cứng, không đọc từ payload push |
| `Topbar.tsx:152` `navigate(target)` | `lib/notifRoute.ts` | `switch` trả **chuỗi mẫu cố định**; `ref_id` chỉ nội suy vào giữa đường dẫn |
| `Sidebar.tsx:340`, `DashKit.tsx` | hằng số trong `nav.ts` | |

→ **Không tìm thấy đường nào người dùng điều khiển được toàn bộ chuỗi đích.** GHSA thứ hai
(SSR hydration) không áp dụng — đây là SPA thuần, không SSR.

**Vẫn nên vá** vì bản vá là patch bump không phá vỡ API (`6.30.4 → 6.30.5+`), và tình trạng
"lỗ hổng đã biết trong dependency shipped ra trình duyệt" là điều không nên giữ.

**Ưu tiên: P1**

---

## FE-S-05 · 🟡 MEDIUM — Google Fonts tải từ CDN bên thứ ba **[XÁC NHẬN]**

**File:** `index.html:14-19`

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:..." rel="stylesheet" />
```

Toàn bộ phần còn lại của hệ thống là **self-hosted sau Cloudflare Tunnel, không mở cổng**.
Đây là ngoại lệ duy nhất, và nó có ba hệ quả:

1. **Rò rỉ metadata.** Mỗi lần tải trang, trình duyệt của cán bộ Viện gửi IP + `Referer`
   (chứa đường dẫn LIMS) tới máy chủ Google. Với hệ chịu ISO/IEC 17025 §4.2 (bảo mật thông
   tin khách hàng), đây là dữ liệu vận hành rời khỏi biên tổ chức mà không có lý do kỹ thuật.
2. **Buộc nới CSP.** Không thể đặt `style-src 'self'` / `font-src 'self'` — phải mở hai
   host ngoài, làm yếu chính lớp phòng vệ ở FE-S-01.
3. **Phụ thuộc sẵn sàng.** Mạng chặn Google (hoặc Google chậm) → render bị trễ font
   (`display=swap` nên không chặn hẳn, nhưng có FOUT).

**Khắc phục:** tự host font Inter (`@fontsource/inter` hoặc chép `.woff2` vào `public/`).
Chi phí ~15 phút, ~100 KB tĩnh, và cho phép siết CSP về `'self'` hoàn toàn.

**Ưu tiên: P1** (làm cùng lúc với FE-S-01 để CSP chặt ngay từ đầu)

---

## FE-S-06 · 🟡 MEDIUM — `/documents/stats` lộ dữ liệu giám sát cho 4 vai trò ngoài dự kiến **[XÁC NHẬN]**

Xem FRONTEND_ARCHITECTURE FE-A-01 cho nguyên nhân kiến trúc. Phần bảo mật:

| Lớp | Cho phép |
|---|---|
| `nav.ts` (menu) | **`admin`** |
| `App.tsx:183` `canViewDocumentStats` | mọi vai trò **trừ** `office` |
| Backend `document_service.py:622` | mọi vai trò **trừ** `office` |

Vì backend cũng chỉ chặn `office`, **đây là lộ dữ liệu thật, không chỉ là gap ở UI**:
`staff`, `qms`, `lab_manager`, `reception` gõ thẳng `/documents/stats` sẽ đọc được thống kê
ai đã tải/xem tài liệu kiểm soát nào, theo phòng ban, theo thời gian.

Đây là dữ liệu **giám sát hành vi người dùng**. Không phải bí mật cấp cao, nhưng rõ ràng
ngoài ý định của người thiết kế (menu chỉ mở cho admin).

**Khắc phục:** chốt danh sách vai trò với nghiệp vụ, rồi áp **đồng thời** ở
`nav.ts` + `rbac.canViewDocumentStats` + backend `aggregate_access_stats`. Ưu tiên siết
backend trước (nơi duy nhất là authority).

**Ưu tiên: P1**

---

## FE-S-07 · 🟡 MEDIUM — Bản nháp báo cáo tháng nằm lại `localStorage` sau khi đăng xuất **[XÁC NHẬN]**

**File:** `src/pages/MonthlyReport.tsx:86, 156, 200`

```ts
const DRAFT_PREFIX = 'lims_activity_report_draft:';
const draftKey = DRAFT_PREFIX + (user?.id ?? 'anon');
localStorage.setItem(draftKey, JSON.stringify(draft));   // tự lưu mỗi 500ms
```

Nháp chứa **nội dung nghiệp vụ**: môn giảng dạy, đề tài, bài báo, hợp đồng NCKH, ghi chú của
cán bộ. `logout()` chỉ gọi `setToken(null)` — **không dọn nháp**.

Trên máy dùng chung (phòng thí nghiệm), sau khi người A đăng xuất, dữ liệu vẫn nằm trong
`localStorage` của trình duyệt; người B mở DevTools là đọc được.

**Điểm làm đúng:** khoá có `user.id` nên **không hiển thị nhầm** nháp của A cho B trong UI.
Vấn đề chỉ là dữ liệu còn lưu lại, không phải rò rỉ qua giao diện.

**Khắc phục:** trong `AuthContext.logout()`, quét và xoá mọi khoá `lims_*` trừ tuỳ chọn giao
diện:
```ts
Object.keys(localStorage)
  .filter((k) => k.startsWith('lims_activity_report_draft:'))
  .forEach((k) => localStorage.removeItem(k));
```

**Ưu tiên: P2**

---

## FE-S-08 · 🔵 LOW — `samplePdf.ts`: 2 điểm nội suy không escape

**File:** `src/lib/samplePdf.ts:114, 128`

Hàm `esc()` (dòng 9-11) escape `& < >` và được áp cho **mọi** trường văn bản. Hai chỗ bỏ sót
vì được giả định là số:

```ts
const qty = (d.quantity ?? 1) > 1 ? ` (SL: ${d.quantity})` : '';          // :114
${ds.reduce((n, d) => n + (d.quantity ?? 1), 0)}                          // :128
```

HTML này được ghi bằng `document.write` vào `window.open('', '_blank')` — cửa sổ **cùng
origin**, tức có quyền đọc `localStorage` (và token, xem FE-S-03).

**Vì sao vẫn là LOW:** `quantity` khai kiểu `number`. Muốn khai thác, backend phải trả về
chuỗi ở trường này. Với chuỗi, `"1<img…" > 1` → `NaN > 1` → `false` → `qty` thành `''`; chỉ
`reduce` là nối chuỗi được. Đường khai thác hẹp và phụ thuộc backend trả sai kiểu.

**Khắc phục (2 dòng):** `${esc(String(d.quantity))}` và bọc `esc()` quanh `reduce`.
Không có lý do gì để hai chỗ này là ngoại lệ.

---

## FE-S-09 · 🔵 LOW — `apiUpload` không đăng xuất khi refresh thất bại

**File:** `src/lib/api.ts:255-274`

3/4 đường gọi (`request`, `apiDownload`, `apiUploadForm`) đều làm:
```ts
else { setToken(null); onSessionExpired?.(); }
```
Riêng `apiUpload` (dùng cho **ảnh đại diện**) thiếu nhánh `else` → refresh hỏng thì user ở
lại trạng thái "đã đăng nhập" trên UI với token đã chết, mọi thao tác sau đó lỗi khó hiểu.

Ảnh hưởng nhỏ (một đường upload), nhưng là **bất nhất trong chính module xử lý phiên**.

---

## FE-S-10 · 🔵 LOW — Không có `robots.txt`

`lims-frontend/public/` không có `robots.txt`, và SPA trả `index.html` cho **mọi** đường
dẫn. Ứng dụng công khai trên `https://lims.<tên-miền>` qua Cloudflare Tunnel.

Không rò dữ liệu (mọi trang cần đăng nhập, và crawler không có token), nhưng trang đăng nhập
+ tiêu đề hệ thống bị lập chỉ mục là lộ diện không cần thiết.

**Khắc phục:** `public/robots.txt` → `User-agent: *` / `Disallow: /`.

---

## FE-S-11 · 🔵 LOW — Mặc định build trỏ về `localhost`

**File:** `lims-frontend/Dockerfile:8`

```dockerfile
ARG VITE_API_BASE_URL=http://localhost:8060/api/v1
```

`docker-compose.prod.yml:231` truyền `/api/v1` nên đường triển khai đúng không bị ảnh hưởng.
Nhưng ai build image bằng `docker build ./lims-frontend` (không qua compose) sẽ tạo ra bundle
production trỏ `localhost:8060` — **build thành công, chạy hỏng, không có cảnh báo nào**.

**Khắc phục:** bỏ giá trị mặc định, để build thất bại tường minh nếu thiếu arg. Vite cũng
nên `throw` khi `import.meta.env.PROD && !VITE_API_BASE_URL`.

---

## FE-S-12 · ⚪ INFO — Bề mặt XSS: đã quét toàn bộ, gần như bằng không

```
$ grep -rnE "dangerouslySetInnerHTML|innerHTML|outerHTML|document\.write|eval\(|new Function|insertAdjacentHTML" src/
src/lib/samplePdf.ts:51:  w.document.write(...)      ← DUY NHẤT, có esc() (xem FE-S-08)
```

- **0** `dangerouslySetInnerHTML` trong 30.110 dòng.
- **0** render Markdown/HTML từ server.
- Mọi nội dung do người dùng nhập (tên khách hàng, mô tả mẫu, ghi chú) đều render qua JSX
  text node → React tự escape.

Đây là kết quả tốt hơn mặt bằng chung rõ rệt, và là lý do FE-S-03 không bị nâng lên HIGH.

## FE-S-13 · ⚪ INFO — Không có secret trong bundle; không có source map production

- Chỉ **một** biến môi trường được inline: `VITE_API_BASE_URL` — là URL công khai, đúng loại
  được phép expose.
- `find dist -name "*.map"` → **0 file**. Vite mặc định không sinh source map cho build
  production và dự án không bật.
- `console.*` còn lại trong `src/`: **đúng 1** (`ErrorBoundary.tsx:29` — `console.error` có
  chủ đích để lập trình viên đọc stack). Không có `console.log` debug sót lại.
- Không có mock data, không có endpoint test, không có credential dev trong `src/`.

## FE-S-14 · ⚪ INFO — CSRF: không áp dụng, và không phải thiếu sót

- API xác thực bằng **`Authorization: Bearer`** — trình duyệt không tự gắn header này khi
  bị site khác kích hoạt.
- Cookie refresh: `HttpOnly` + `Secure` (production) + **`SameSite=Strict`** +
  `Path=/api/v1/auth` (`lims-backend/app/routers/_cookies.py`).
- CORS backend dùng allowlist tường minh từ `CORS_ORIGINS`, không wildcard.

→ Không cần CSRF token. Ghi lại để không ai "bổ sung" nhầm sau này.

---

## Phụ lục — Checklist bảo mật bắt buộc (§39)

| Hạng mục | Kết quả |
|---|---|
| XSS | ✅ Bề mặt gần bằng không (FE-S-12); 2 điểm nội suy nhỏ cần vá (FE-S-08) |
| CSRF | ✅ Không áp dụng — Bearer + SameSite=Strict (FE-S-14) |
| IDOR/BOLA awareness | ✅ FE không tự phân quyền; mọi id đi qua API có kiểm ở backend. **Lưu ý:** backend còn lỗ hổng `/attachments` — xem `docs/SECURITY_AUDIT.md` S-01/S-02 |
| Open redirect | ✅ Không có param `?redirect/next/url/callback`; mọi `navigate()` đích cố định (FE-S-04) |
| Token leakage | ⚠️ localStorage (FE-S-03); không có token trong URL/log/analytics |
| Sensitive localStorage | ⚠️ Nháp báo cáo tháng không dọn khi logout (FE-S-07) |
| Secret exposure | ✅ Không (FE-S-13) |
| API key exposure | ✅ Không có API key nào ở frontend |
| Dependency vulnerabilities | ⚠️ 5 lỗ (3 moderate + 2 high) — FE-S-04 + postcss build-time |
| Malicious file upload | ⚠️ FE chỉ có `accept=`; backend là nơi phải chặn — **backend chưa kiểm magic bytes** |
| Unsafe HTML rendering | ✅ Không có |
| CSP | ❌ **Không có** (FE-S-01) |
| Security headers | ❌ **Không có** (FE-S-01) |
| Third-party scripts | ⚠️ Google Fonts (FE-S-05) — CSS, không phải JS |
| Source maps | ✅ Không sinh ở production |
| Debug code | ✅ 1 `console.error` có chủ đích |
| Production environment | ⚠️ Mặc định build trỏ localhost (FE-S-11) |

## Phụ lục — Bảng tổng hợp

| ID | Mức | Danh mục | Loại | File | Ưu tiên |
|---|---|---|---|---|---|
| FE-S-01 | 🟠 HIGH | Security headers / CSP | XÁC NHẬN | `nginx.conf` | **P0** |
| FE-S-02 | 🟠 HIGH | Auth / đua refresh đa tab | XÁC NHẬN | `lib/api.ts:85` | **P0** |
| FE-S-03 | 🟡 MEDIUM | Token storage | RỦI RO | `lib/api.ts:14` | P2 |
| FE-S-04 | 🟡 MEDIUM | Dependency CVE | RỦI RO | `package.json` | P1 |
| FE-S-05 | 🟡 MEDIUM | Bên thứ ba / privacy | XÁC NHẬN | `index.html:14` | P1 |
| FE-S-06 | 🟡 MEDIUM | Lộ dữ liệu giám sát | XÁC NHẬN | `nav.ts` + BE | P1 |
| FE-S-07 | 🟡 MEDIUM | Dữ liệu nhạy cảm còn lại | XÁC NHẬN | `MonthlyReport.tsx:200` | P2 |
| FE-S-08 | 🔵 LOW | XSS (hẹp) | XÁC NHẬN | `samplePdf.ts:114,128` | P2 |
| FE-S-09 | 🔵 LOW | Xử lý phiên bất nhất | XÁC NHẬN | `lib/api.ts:255` | P2 |
| FE-S-10 | 🔵 LOW | Indexing | KHUYẾN NGHỊ | `public/` | P3 |
| FE-S-11 | 🔵 LOW | Build config | XÁC NHẬN | `Dockerfile:8` | P2 |
