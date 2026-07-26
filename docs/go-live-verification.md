# Biên bản nghiệm thu Go-live — LIMS

| | |
|---|---|
| **Ngày đo** | 2026-07-26 |
| **Nhánh** | `feat/p3-infrastructure` (chồng lên PR #1–#8) |
| **Commit** | xem `git log --oneline` — 3 commit nền + 21 commit remediation |
| **Image** | `limb-lims-api`, `limb-lims-web` (build local, chưa gắn tag phiên bản) |
| **Máy đo** | 12 nhân CPU · 15,62 GB RAM · đĩa 13 GB trống |
| **Cấu hình** | `UVICORN_WORKERS=4` · `DB_POOL_SIZE=8` · `DB_MAX_OVERFLOW=12` · `DB_POOL_TIMEOUT=5` |
| **Công cụ** | k6 v0.54.0 · `perf/baseline.js` · 80 tài khoản load-test |

---

## KẾT LUẬN: 🔴 **NO-GO**

Đạt **5/7** điều kiện cổng go-live. Hai điều kiện không đạt, cả hai cùng một
nguyên nhân gốc, và **không phải lỗi mới** — đó là F-03 (pool cạn) lần đầu tiên
quan sát được, sau khi F-04 được sửa và tải thật mới chạm tới tầng database.

---

## 1. Bảng cổng go-live

| # | Điều kiện | Ngưỡng | Đo được | Kết quả |
|---|---|---|---|:--:|
| 1 | k6 p95 | < 2 000 ms | **1 403 ms** | ✅ |
| 2 | Tỉ lệ lỗi | < 1 % | **1,49 %** | ❌ |
| 3 | Upload 18 MB không làm chậm `/health` | — | đỉnh 355,4 → **10,8 ms** | ✅ |
| 4 | Không có 429 do dùng chung IP proxy | 0 | **0** · login **100 %** | ✅ |
| 5 | Token đã logout vẫn bị từ chối sau restart Redis | 401 | **401** | ✅ |
| 6 | Restore backup thành công | — | RTO **5 s**, dữ liệu khớp 100 % | ✅ |
| 7 | Không có lỗi QueuePool | 0 | **159** | ❌ |

---

## 2. Diễn biến qua từng PR — bằng chứng các bản sửa có tác dụng

| Mốc | login thành công | errors | p95 | QueuePool |
|---|---|---|---|---|
| Baseline (trước sửa) | 20,49 % | 44,84 % | 949 ms | 0¹ |
| Sau PR #2 (worker + pool) | 21 % | 43,79 % | 310 ms | 0¹ |
| Sau PR #3 (IP thật) | 46 % | 26,41 % | 1 248 ms | 0¹ |
| Sau PR #3(c) (rate limit theo email) | **100 %** | 21,77 % | 1 248 ms | 0¹ |
| Sau khi sửa kịch bản đo | **100 %** | **1,49 %** | **1 403 ms** | **159** |

¹ Bằng 0 vì tải chưa bao giờ chạm tới database — rate limit chặn 80 % request
ngay ở cửa đăng nhập. Con số 0 ở các dòng trên **không phải là bằng chứng pool
khoẻ**, chỉ là bằng chứng tải không tới nơi.

---

## 3. Nguyên nhân của hai điều kiện không đạt

```
QueuePool limit of size 8 overflow 12 reached, connection timed out, timeout 5.00
```

| Yếu tố | Giá trị |
|---|---|
| Pool mỗi worker | 8 + 12 = **20** kết nối |
| Số worker | 4 |
| Tải đồng thời | 6 request song song/vòng × 20 VU = **120** |
| Phân bổ | ~**30** request/worker > 20 kết nối |
| Hệ quả | 10 request chờ, quá `pool_timeout=5s` → 500 |

**Không phải Postgres hết chỗ:** số kết nối thực tế cao nhất là **45/100** ở dev
(prod đã cấu hình 200). Nút thắt nằm ở pool SQLAlchemy của từng worker.

1,49 % lỗi và 159 lỗi QueuePool là **cùng một sự kiện** đếm theo hai cách.

Trễ tối đa **17 104 ms** trong đợt đo cũng đến từ đây: request xếp hàng chờ
connection rồi mới bị từ chối.

---

## 4. Khuyến nghị để chuyển sang GO

Kế hoạch quy định `DB_POOL_SIZE=8` / `DB_MAX_OVERFLOW=12`, tính theo
`max_connections=100` mặc định. Prod đã nâng lên 200 nên còn dư địa:

```bash
# 4 worker × (12 + 28) = 160 kết nối  <  max_connections 200
DB_POOL_SIZE=12
DB_MAX_OVERFLOW=28
DB_POOL_TIMEOUT=5
```

Đây là **thay đổi thông số do kế hoạch quy định**, nên tôi không tự áp dụng —
cần người phụ trách chấp thuận. Sau khi đổi phải chạy lại `k6 run perf/baseline.js`
và xác nhận `QueuePool = 0`, `errors < 1 %`.

Giải pháp bền vững là **R9.2 PgBouncer** (transaction pooling): nhiều worker dùng
chung một pool phía sau, thay vì mỗi worker giữ pool riêng. Chưa triển khai.

---

## 5. Số liệu tài nguyên

| Chỉ số | Giá trị | Ghi chú |
|---|---|---|
| RAM lims-api đỉnh | **753 MiB** | `mem_limit: 1g` — còn 25 % dư |
| Kết nối Postgres đỉnh | **45** | trần dev 100, prod 200 |
| Tổng request đợt đo | 3 427 | |
| CPU lims-api đỉnh | ~116 % | dùng được nhiều nhân sau R2.1 |

---

## 6. Kết quả kiểm thử khác

| Hạng mục | Kết quả |
|---|---|
| `pytest app/tests` | **475 passed · 21 skipped · 0 failed** (baseline: 0 chạy được) |
| Quét IDOR (R8.3) | **329 route** — không route `{id}`/ghi nào thiếu xác thực |
| `npm run check` (tsc + responsive) | exit 0 |
| `npm run build` | chunk vào app **148 KB** (trước 1 164 KB) · 74 chunk |
| Diễn tập restore | users/samples/documents/alembic khớp 100 %, 69 bảng, RTO 5 s |
| Idempotency | 2 POST cùng key → **1 bản ghi** (trước: 2) |
| Redis AOF | token đã logout vẫn 401 sau restart |

---

## 7. Hai lỗi trong chính công cụ đo — đã sửa

Ghi lại để lần đo sau không lặp lại:

1. **`vus_max` = 80 nhưng kế hoạch bảo tạo 60 tài khoản.** VU 61–80 đăng nhập
   bằng email không tồn tại → sai 5 lần → lockout. Lần đo đầu cho 4 % login
   thành công và suýt bị hiểu nhầm thành lỗi hệ thống.

2. **Kịch bản đăng nhập lại ở mỗi vòng lặp.** Mỗi tài khoản ~25 lần đăng nhập
   trong 5 phút, vượt giới hạn 10 lần/5 phút → 54 % request nhận 429. Nó đo
   throughput của `/auth/login` chứ không đo throughput ứng dụng. Người dùng
   thật đăng nhập một lần rồi dùng token suốt buổi. Đã sửa: `steady` lấy token
   trong `setup()` rồi tái sử dụng.

3. **`/reporting/dashboard` không tồn tại** (đúng là `/dashboard`) → 1/6 request
   trong batch luôn trả 404, chiếm ~17 % tỉ lệ lỗi.

---

## 8. Việc đã biết là chưa xử lý

| Mục | Trạng thái | Ghi chú |
|---|---|---|
| **R8.1** token in-memory | 🛑 **DỪNG CÓ CHỦ ĐÍCH** | Thử nghiệm cho thấy 2 tab cùng F5 → `TOKEN_REUSED` → 0 phiên còn sống. Xem `ops/RUNBOOK.md` §10 |
| R9.1 queue nền | chưa làm | Xuất Excel/PDF vẫn chạy trong request (có semaphore giới hạn 2) |
| R9.2 PgBouncer | chưa làm | Chính là giải pháp bền vững cho §4 |
| R9.4 E2E Playwright | chưa làm | |
| R9.5 Chaos test | chưa làm | Hành vi suy giảm đã ghi trong runbook nhưng chưa kiểm bằng thực nghiệm |
| R5.4 phân trang server | 1/7 bảng | Mới `TestParameters`; 6 bảng còn lại vẫn cắt trang ở client |
| R6.2 sửa N+1 | 1/5 service | Mới `user_service` |
| nginx tin `CF-Connecting-IP` | chưa siết | Cần giới hạn theo dải IP Cloudflare |

---

## 9. Chữ ký

| Vai trò | Tên | Ngày | Kết luận |
|---|---|---|---|
| Người thực hiện | *(tự động)* | 2026-07-26 | **NO-GO** — chờ quyết định về §4 |
| Người phê duyệt kỹ thuật | | | |
| Người phê duyệt nghiệp vụ | | | |
