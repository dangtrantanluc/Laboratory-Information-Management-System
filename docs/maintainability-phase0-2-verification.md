# Biên bản nghiệm thu — Giai đoạn 0–2 kế hoạch bảo trì

| | |
|---|---|
| **Ngày** | 2026-07-26 |
| **Phạm vi** | MAINTAINABILITY_PLAN.md Giai đoạn 0, 1, 2 (dự toán 25 ngày công) |
| **Nhánh** | `feat/p3-infrastructure` — 11 commit `maint(...)` / `fix(...)` |
| **Kế hoạch gốc** | [MAINTAINABILITY_PLAN.md](../MAINTAINABILITY_PLAN.md) · [MAINTAINABILITY_REVIEW.md](../MAINTAINABILITY_REVIEW.md) |

---

## KẾT LUẬN: ✅ **ĐẠT** — 10/10 task, 6/6 cổng kiểm tra xanh

Kèm **một lỗi production tìm được ngoài kế hoạch** và **hai số liệu trong báo cáo
gốc phải đính chính**.

---

## 1. Sáu cổng kiểm tra

| # | Cổng | Kết quả |
|---|---|---|
| 1 | `pytest app/tests` | **545 passed · 6 skipped · 0 failed** |
| 2 | Test kiến trúc (không cần DB) | **8 passed** |
| 3 | `ruff check app` | **All checks passed** |
| 4 | Trần kích thước file | **367 file, không file nào vượt 800 dòng** |
| 5 | `npm run check` (tsc + responsive) | **exit 0** |
| 6 | Migration `downgrade -1` → `upgrade head` | **thuận nghịch, về đúng head** |

**Khói end-to-end trên ứng dụng thật** (image dựng lại, không phải mã trên đĩa):
`/health` 200 · `/health/ready` 200 · đăng nhập OK · 10/10 endpoint đại diện trả 200.

**Chứng minh không mất endpoint:** so danh sách route đang chạy với bản chụp
trước khi refactor (commit `79b5f03`) → **0 endpoint bị mất**.

---

## 2. Trước / sau

| Chỉ số | Trước | Sau | |
|---|---:|---:|---|
| Test chạy được | 475 | **545** | +70 |
| Test skip im lặng | 21 | **6** | đều chủ đích (endpoint công khai) |
| Router có test | **0/40** | **4/40** | 40 test, 22 kịch bản nghiệp vụ |
| File backend lớn nhất | 1.736 dòng | **792 dòng** | −54% |
| File >800 dòng | 5 | **3** | đều đã có kế hoạch xử lý |
| Mã lỗi dạng chuỗi thô | 359 điểm | **0** | 153 mã vào enum |
| Router tự viết `_ip()` | 26 | **0** | |
| Cổng CI kiến trúc | 0 | **4** | |
| Vòng lặp chạy test | *không chạy được* | **6 giây** | |

Ba chỉ số dài hạn (mục tiêu 24 tháng), đo bằng `scripts/maintainability-metrics.sh`:

| | Hôm nay | 6 tháng | 12 tháng | 24 tháng |
|---|---:|---:|---:|---:|
| Endpoint thiếu `response_model` | **281** | ≤200 | ≤80 | 0 |
| `db.commit()` trong service | **166** | ≤120 | ≤30 | 0 |
| Router có test | **4/40** | 12/40 | 25/40 | 40/40 |

> Hai chỉ số đầu chưa nhúc nhích là **đúng thiết kế**: chúng thuộc Giai đoạn 3–4.
> Việc của Giai đoạn 0 là chặn chúng tăng thêm, và điều đó đã có test bảo vệ.

---

## 3. Lỗi production tìm được ngoài kế hoạch

### Nhật ký kiểm toán ghi IP của proxy thay vì IP người dùng

Phát hiện khi viết test router đầu tiên: mọi endpoint GHI đều ném
`DataError: invalid input syntax for type inet: "testclient"`.

Lần theo thì thấy **26 chỗ tự viết lại cùng một hàm**:

```python
def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None
```

Bản sửa F-04 (`ARCHITECTURE_AUDIT`) đã dạy `rate_limit.client_ip()` đọc
`X-Real-IP`, nhưng 25 bản sao trong router và 1 bản trong middleware `access_stat`
không được sửa theo. **Đó chính là cái giá của trùng lặp: sửa một chỗ không sửa
được 25 chỗ kia.**

Bằng chứng trên dữ liệu thật của hệ thống đang chạy:

| `audit_logs.ip` | Số dòng | Thực chất là |
|---|---:|---|
| `172.21.0.1` | 869 | gateway docker |
| `172.21.0.6` | 545 | container nginx |
| IP thật | 3 | |

Với hệ thống chịu ISO/IEC 17025, **cột IP của chính nhật ký kiểm toán gần như
không truy vết được ai**. `access_stats.ip` cũng vậy — và ở đó lỗi bị nuốt thành
một dòng WARNING nên không ai biết.

**Đã sửa** (commit `1ff62e5`): gộp về `app/core/request_meta.client_ip`, trả
`None` chứ không phải `"unknown"` vì cột là INET. Kèm 2 test: một kiểm IP thật
được ghi đúng, một chặn router tự viết lại `_ip()`.

---

## 4. Hai đính chính với báo cáo gốc

Báo cáo `MAINTAINABILITY_REVIEW.md` có hai số liệu sai. Cả hai đều do đo bằng
regex thay vì phân tích cú pháp.

**a) Mã lỗi: 380 → 73 → thực tế 153**

Lần đo đầu (380) đếm mọi chuỗi viết hoa. Lần hai (73) chỉ bắt mã nằm **cùng
dòng** với lời gọi. Đếm bằng AST cho con số đúng: **153 mã duy nhất, 359 điểm
dùng, 90 mã chỉ dùng đúng một lần**.

Con số cuối làm luận điểm gốc mạnh hơn chứ không yếu đi: 90/153 mã dùng một lần
là dấu hiệu mã được nghĩ ra tại chỗ thay vì chọn từ danh mục có sẵn.

**b) `research_service.py`: 6 domain → thực tế 9**

Bỏ sót COMMUNITY SERVICES, COMPETENCE SUMMARY và STATS.

**c) `_get_X_or_404`: "11 hàm giống hệt" → 13 hàm, chỉ 9 giống hệt**

4 hàm còn lại ném **mã lỗi riêng theo domain** (`PROJECT_NOT_FOUND`...) thay vì
`NOT_FOUND` chung — đó là cách làm **tốt hơn**. Ép cả 13 về một helper cứng sẽ
làm mất mã riêng, tức là bước lùi. Helper vì vậy nhận tham số `code`.

---

## 5. Việc đã làm, theo task

| Task | Nội dung | Bằng chứng nghiệm thu |
|---|---|---|
| **T0.1** | Test hợp đồng `response_model` + allowlist một chiều | Kiểm 3 chiều: endpoint mới thiếu schema → đỏ; xoá dòng allowlist chưa sửa → đỏ; entry thừa → đỏ |
| **T0.2** | Trần 800 dòng/file, `GRANDFATHERED` một chiều | Kiểm 3 chiều: file mới 900 dòng → đỏ; giảm >100 dòng chưa hạ trần → đỏ; xuống dưới 800 → buộc bỏ khỏi danh sách |
| **T1.1** | `research_service.py` 1.736 → 9 module | 52/52 tên public còn đủ, 31/31 chữ ký khớp; 30 lời gọi router trỏ thẳng module domain |
| **T1.2** | `chemical_service.py` 850 → 5 module | 15 lời gọi ở 2 router; DAG không vòng |
| **T1.3** | 153 mã lỗi → `ErrorCode` enum | JSON serialize ra đúng chuỗi cũ → **không phá vỡ hợp đồng API**; gộp `DEPT_NOT_FOUND` |
| **T1.4** | 13 bản sao `_get_X_or_404` → 2 helper | 5 test, có test chứng minh biến thể soft-delete thật sự loại bản ghi đã xoá |
| **T1.5** | *(ngoài kế hoạch)* Sửa 26 bản sao `_ip()` | §3 ở trên |
| **T2.1a** | Image test riêng | 475/21 skip → 493/6 skip — 15 test integration trước nay **không chạy dòng nào** |
| **T2.1** | conftest gốc: `client`, `as_role`, `department`, `audit_rows` | 3 cạm bẫy đã gỡ, xem §6 |
| **T2.2** | 40 test router / 22 kịch bản | Chạy 3 lần: 5.86s / 5.88s / 5.92s — **không giòn** |
| **T2.3** | Cổng vùng phủ 45% trong CI | Đo được **47,8%**. Xem §11 — con số 50,5% báo lần đầu là sai |

---

## 6. Ba cạm bẫy phải gỡ trước khi test router chạy được

Ghi lại vì đây chính là câu trả lời cho **"vì sao 0/41 router từng có test"** —
không phải vì lười.

1. **Service vẫn gọi `db.commit()`** (166 chỗ, gỡ ở Giai đoạn 3) nên rollback đơn
   giản không dùng được. Phải bind session với
   `join_transaction_mode="create_savepoint"`.

2. **`as_role` phải tạo user THẬT trong DB.** Hầu hết bảng có FK
   `created_by → users`, nên `CurrentUser` với uuid bịa ra làm mọi thao tác ghi
   đổ vỡ vì `ForeignKeyViolation`.

3. **`TestClient` đặt `request.client.host = "testclient"`** trong khi
   `audit_logs.ip` là cột INET → mọi endpoint GHI ném `DataError`. Phải gửi
   header `X-Real-IP` — và dùng header chính là đường đi thật ở production.

Cả ba đều mất thời gian mò, và cả ba đều thuộc loại làm người ta bỏ cuộc. Giờ
chúng nằm trong `conftest.py` kèm giải thích, nên người tiếp theo không phải mò lại.

---

## 7. Hợp đồng API mà việc viết test làm lộ ra

Trước khi có test, không ai biết những điều sau nếu không dò trực tiếp — đúng
triệu chứng M-01:

| Điều | Thực tế |
|---|---|
| Lỗi **schema** (pydantic) | HTTP **400** `VALIDATION_ERROR` |
| Vi phạm **quy tắc nghiệp vụ** | HTTP **422** |
| Trường mã của phiếu NC | `nc_code`, **không phải** `code` |
| Mở CAPA | bắt buộc `owner_id` |
| Thêm hành động CAPA | trường là `action`, không phải `description` |
| Tạo rủi ro / NC | bắt buộc `department_id` |

Sự phân biệt 400/422 là một quyết định thiết kế hợp lý — nhưng nó **không được
ghi ở đâu cả**, và giờ đã có test giữ.

---

## 8. Việc CHƯA làm (đúng phạm vi, không phải thiếu sót)

| Mục | Thuộc | Ghi chú |
|---|---|---|
| Gỡ 166 `db.commit()` khỏi service | Giai đoạn 3 | Điều kiện tiên quyết (lưới test) nay **đã có** |
| `response_model` cho 281 endpoint | Giai đoạn 4 | Nợ đã bị **chặn không tăng** |
| Sinh type frontend từ OpenAPI | Giai đoạn 4 | |
| Tách file frontend >800 dòng | Giai đoạn 5 | 2 file còn trong `GRANDFATHERED` |
| `types/index.ts` 1.964 dòng | Giai đoạn 4 | Sẽ thay bằng bản sinh, không tách tay |

---

## 9. Còn tồn đọng, không liên quan kế hoạch này

Quyết định về `DB_POOL_SIZE=12` / `DB_MAX_OVERFLOW=28` để gỡ cổng NO-GO vẫn
đang chờ người phụ trách — xem [go-live-verification.md](./go-live-verification.md) §4.
Hai việc độc lập nhau.

---

## 10. Chữ ký

| Vai trò | Ngày | Kết luận |
|---|---|---|
| Người thực hiện | 2026-07-26 | **ĐẠT** — 10/10 task, 6/6 cổng |
| Người phê duyệt kỹ thuật | | |


---

## 11. Đính chính sau khi CI chạy thật

CI bắt được một lỗi mà kiểm thử local của tôi bỏ sót.

**Vùng phủ: báo 50,5%, thực tế 47,8%.**

Image test không chứa `.coveragerc` (file được tạo sau lần rebuild cuối), nên
`--cov-config=.coveragerc` trỏ vào một file không tồn tại. Coverage **không báo
lỗi** — nó âm thầm dùng cấu hình mặc định, tức là đếm cả `app/tests/` vốn luôn
~99% vì chúng tự chạy. Mẫu số phồng từ 13.648 lên 16.508 lệnh.

Đúng loại lỗi mà chính `.coveragerc` sinh ra để ngăn, và nó qua mặt được vì
**thiếu file cấu hình là im lặng, không phải lỗi**.

| | Báo lần đầu | Thực tế |
|---|---:|---:|
| Lệnh được đếm | 16.508 | **13.648** |
| Vùng phủ | 50,5% | **47,8%** |
| Cổng CI | 48% | **45%** |

Đã sửa: `docker-compose.test.yml` mount `.coveragerc` vào container, nên local
và CI giờ cho cùng con số. Cổng hạ về 45% cho khớp mức thật — hạ vì phép đo
gốc sai, không phải vì hạ chuẩn.
