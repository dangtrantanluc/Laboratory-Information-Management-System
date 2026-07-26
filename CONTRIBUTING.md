# Quy ước đóng góp — LIMS

Tài liệu này chỉ ghi những luật **CI sẽ chặn**. Quy ước phong cách nằm trong
`ruff.toml` và `eslint.config.js`, không nhắc lại ở đây.

Bối cảnh và lý do: [MAINTAINABILITY_REVIEW.md](./MAINTAINABILITY_REVIEW.md) ·
Kế hoạch: [MAINTAINABILITY_PLAN.md](./MAINTAINABILITY_PLAN.md)

---

## 1. Endpoint mới bắt buộc khai `response_model`

```python
# ✗ CI ĐỎ
@router.get("/customers")
def list_customers(...):
    return paginated(items, page=page, limit=limit, total=total)

# ✓
@router.get("/customers", response_model=Page[CustomerOut])
def list_customers(...):
    return paginated(items, page=page, limit=limit, total=total)
```

**Vì sao:** không có `response_model` thì OpenAPI không mô tả gì về dữ liệu trả
về. Frontend phải viết tay type để đoán, và đổi tên một trường ở backend **không
gây lỗi biên dịch ở đâu cả** — nó hỏng lúc chạy, trên máy người dùng.

Kiểm tra: `app/tests/architecture/test_response_contract.py`

> **`response_model_legacy.txt` chỉ được NGẮN ĐI.**
> 281 endpoint cũ đang trong danh sách miễn trừ. Thêm dòng mới = từ chối trong
> review. Sửa được endpoint nào thì xoá dòng đó — có test bắt buộc điều này.

**Cạm bẫy:** FastAPI **lọc bỏ** trường không khai trong `response_model`. Thiếu
một trường mà frontend đang dùng thì nó biến mất im lặng, không lỗi, không log.
Khi thêm `response_model` cho endpoint cũ, phải kèm test đối chiếu:

```python
assert set(body) == set(CustomerOut.model_fields)
```

## 2. Trần 800 dòng mỗi file

```bash
node scripts/check-file-size.mjs
```

**Vì sao:** `research_service.py` từng đạt 1.736 dòng và chứa 9 domain. Không có
trần cứng thì mọi service đều đi con đường đó — tiện nhất luôn là thêm hàm vào
file sẵn có. 800 dòng là ngưỡng mà nhiều người sửa nhiều domain bắt đầu conflict
merge liên tục.

File trong diện chuyển tiếp (`GRANDFATHERED`) có trần riêng và **chỉ được hạ
xuống**: giảm được bao nhiêu thì phải cập nhật trần bấy nhiêu.

File sinh tự động (`*.gen.ts`) không tính — con người không đọc chúng.

## 3. Mã lỗi dùng `ErrorCode`, không dùng chuỗi

```python
# ✗ CI ĐỎ
raise AppException("CUSTOMER_NOT_FOUND", "Không tìm thấy khách hàng", 404)

# ✓
raise AppException(ErrorCode.CUSTOMER_NOT_FOUND, "Không tìm thấy khách hàng", 404)
```

**Vì sao:** trước đây là 73 chuỗi rải rác trong 67 service. Gõ sai một ký tự
không ai phát hiện; không grep ra được mã nào đã chết; và đã có lúc tồn tại song
song `DEPARTMENT_NOT_FOUND` với `DEPT_NOT_FOUND` cho cùng một tình huống.

Kiểm tra: `app/tests/architecture/test_error_codes.py`

## 4. Không thêm `db.commit()` mới trong service

```python
# ✗ service tự quyết định ranh giới giao dịch
def create_customer(db, ...):
    db.add(c)
    db.commit()      # ← không

# ✓ service chỉ mô tả việc; commit do tầng ngoài lo
def create_customer(db, ...):
    db.add(c)
    db.flush()       # chỉ khi cần id ngay
```

**Vì sao:** 166 điểm commit rải rác nghĩa là **không có giao dịch nguyên tử cho
luồng nhiều bước**. Luồng "duyệt báo giá → tạo dispatch → gửi thông báo" mà bước
2 lỗi sau khi bước 1 đã commit sẽ để dữ liệu ở trạng thái nửa vời — rủi ro toàn
vẹn dữ liệu với hồ sơ chịu ISO/IEC 17025.

Việc gỡ 166 commit hiện có thuộc Giai đoạn 3 của kế hoạch. Luật này chỉ chặn
**thêm mới**.

## 5. Migration phải có `downgrade()` chạy được

30/30 migration hiện tại đều có. Giữ nguyên tỉ lệ đó.

Nếu `downgrade()` làm mất dữ liệu (ví dụ m30 hạ `pending` → `disabled`), ghi rõ
trong docstring của migration.

---

## Chạy toàn bộ kiểm tra trước khi mở PR

```bash
# Backend
cd lims-backend && python -m pytest app/tests -q

# Kiến trúc (nhanh, không cần DB)
python -m pytest app/tests/architecture -v

# Frontend
cd lims-frontend && npm run check

# Trần kích thước file
node scripts/check-file-size.mjs
```
