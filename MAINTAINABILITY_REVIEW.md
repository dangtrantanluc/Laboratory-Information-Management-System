# Maintainability Review — LIMS Viện CNSH & Môi trường

> **ĐÍNH CHÍNH 2026-07-26** — ba số liệu dưới đây đo bằng regex nên sai; đo lại
> bằng AST khi triển khai:
> - Mã lỗi: **153** (không phải 380), ở 359 điểm dùng, 90 mã chỉ dùng 1 lần
> - `research_service.py`: **9 domain** (không phải 6)
> - `_get_X_or_404`: **13 hàm**, chỉ 9 giống hệt — 4 hàm còn lại ném mã riêng
>   theo domain, tức là làm ĐÚNG hơn
>
> Kết luận và thứ tự ưu tiên không đổi. Giai đoạn 0–2 đã triển khai:
> [docs/maintainability-phase0-2-verification.md](docs/maintainability-phase0-2-verification.md)

**Câu hỏi:** *Codebase này có còn dễ bảo trì sau 2–5 năm không?*
**Ngày:** 2026-07-26 · **Sau remediation** (30 commit, PR #1–#9)
**Quy mô đo được:** BE 35.979 dòng / 177 file Python · FE 22.084 dòng / 84 file TSX

> Không review lại performance/security/infra — đã có `ARCHITECTURE_AUDIT.md`.
> Chỉ nêu vấn đề có ảnh hưởng **dài hạn**, kèm lợi ích định lượng.

---

## Tóm tắt điều hành

Codebase này **khoẻ hơn mức trung bình** của dự án nội bộ cùng quy mô. Phân tầng
nhất quán, router mỏng, migration kỷ luật, comment giải thích *vì sao* chứ không
phải *cái gì*. Đó là nền móng tốt hiếm gặp.

Nhưng có **một lỗ hổng kiến trúc duy nhất** sẽ quyết định số phận 5 năm tới:

> **Không tồn tại hợp đồng dữ liệu giữa backend và frontend.**
> 296/296 endpoint không khai báo `response_model`. 248 hàm service trả `dict`
> thuần. Frontend viết tay **1.964 dòng / 126 interface** để mô tả lại thứ backend
> trả về. Không compiler, không test, không OpenAPI nào bắt buộc hai bên khớp nhau.

Đổi tên một trường ở backend hôm nay → frontend hỏng lúc chạy, không ai biết cho
tới khi người dùng báo. Với 5 developer thì còn nhớ được. Với **30–50 developer
trong 5 năm** thì đây là nguồn lỗi sản xuất số một.

---

## Bảng phát hiện

| ID | Vấn đề | Mức | Effort | Risk |
|---|---|:--:|---:|:--:|
| **M-01** | Không có hợp đồng đầu ra BE↔FE | 🔴 Critical | 15–20 ngày | Trung bình |
| **M-02** | Không có tầng Repository; ranh giới transaction không xác định | 🟠 High | 20–25 ngày | Cao |
| **M-03** | God service — `research_service.py` 1.736 dòng / 6 domain | 🟠 High | 5 ngày | Thấp |
| **M-04** | 0/41 router có test; 146 test cho 296 endpoint | 🟠 High | 15 ngày | Thấp |
| **M-05** | 380 mã lỗi dạng chuỗi rải rác, không enum | 🟠 High | 3 ngày | Thấp |
| **M-06** | Khuôn mẫu CRUD lặp thủ công (11× `_get_or_404`, 16× `_dict`) | 🟡 Medium | 5 ngày | Thấp |
| **M-07** | Frontend fat page — 13 file >500 dòng, 705 `useState` | 🟡 Medium | 10 ngày | Trung bình |
| **M-08** | Hằng miền trùng lặp qua ranh giới ngôn ngữ (49 BE / 36 FE) | 🟡 Medium | 4 ngày | Thấp |
| **M-09** | 51 import lười — dấu hiệu phụ thuộc vòng | 🟡 Medium | 4 ngày | Trung bình |
| **M-10** | Mã HTTP dạng số literal (404 × 193 lần) | 🟢 Low | 0,5 ngày | Rất thấp |

---

## 🔴 M-01 · Không có hợp đồng đầu ra giữa backend và frontend

**Ví dụ**

```python
# app/services/research_service.py — 1 trong 248 hàm cùng dạng
def _project_dict(db, p) -> dict:
    return {"id": p.id, "title": p.title, "lead_user_name": ..., ...}

# app/routers/research.py — không có response_model
@router.get("/research-projects")
def list_projects(...):
    return paginated(items, page=page, limit=limit, total=total)
```

```typescript
// lims-frontend/src/types/index.ts — 1.964 dòng viết TAY mô tả lại
export interface ResearchProject {
  id: string;
  title: string;
  lead_user_name: string | null;   // ← khớp với backend nhờ NIỀM TIN
  ...
}
```

**Đo được**

| | |
|---|---|
| Endpoint có `response_model` | **0 / 296** |
| Endpoint có schema đầu ra trong OpenAPI | **0 / 296** |
| Hàm service trả `-> dict` | **248** |
| Hàm service trả schema Pydantic | **0** |
| Dòng type viết tay ở frontend | **1.964** (126 interface) |

**Nguyên nhân**
Dự án chọn cách trả `dict` từ service và bọc bằng `ok()`/`paginated()` ở router.
Nhanh lúc viết, nhưng bỏ mất tầng khai báo. Pydantic được dùng đầy đủ cho **đầu
vào** (21 file schema) — nghĩa là đội đã biết cách, chỉ là không áp cho đầu ra.

**Ảnh hưởng dài hạn**

- Đổi tên/xoá một trường backend **không gây lỗi biên dịch ở đâu cả**. Nó hỏng
  lúc chạy, trên máy người dùng.
- Frontend không thể sinh type tự động → 1.964 dòng phải sửa tay mỗi lần API đổi.
- OpenAPI vô dụng cho việc sinh client, sinh mock, viết test hợp đồng.
- Dev mới không có nguồn sự thật nào để biết endpoint trả gì — phải đọc code
  service hoặc gọi thử.
- **Chi phí tăng phi tuyến theo số developer.** 5 người còn nhớ được; 30 người
  thì không.

**Refactor đề xuất** — làm dần, không big-bang:

```python
# 1. Khai response schema cho các endpoint mới TRƯỚC (bắt buộc trong code review)
class ResearchProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    lead_user_name: str | None

@router.get("/research-projects", response_model=Page[ResearchProjectOut])
def list_projects(...): ...

# 2. Sinh type frontend từ OpenAPI, thay cho types/index.ts viết tay
#    npx openapi-typescript http://localhost:8060/openapi.json -o src/types/api.ts
```

Thêm một test chặn hồi quy:

```python
def test_every_endpoint_declares_a_response_model():
    missing = [r.path for r in app.routes
               if isinstance(r, APIRoute) and r.response_model is None
               and r.path not in LEGACY_ALLOWLIST]
    assert not missing
```

`LEGACY_ALLOWLIST` khởi đầu chứa cả 296 endpoint, **chỉ được phép ngắn đi**. Đây
là cách chuyển đổi mà không chặn tính năng.

**Effort** 15–20 ngày (296 endpoint, ~15 phút/endpoint + sinh lại type FE)
**Risk** Trung bình — schema sai làm hỏng response; giảm bằng cách làm từng router
**Priority** **P0 cho mọi endpoint MỚI ngay hôm nay** · P1 cho phần cũ

---

## 🟠 M-02 · Không có tầng Repository; ranh giới transaction không xác định

**Ví dụ**

```python
# app/services/user_service.py — service nói chuyện thẳng với SQLAlchemy
rows = db.execute(select(User).where(*conditions).offset(...).limit(limit)).scalars().all()
db.add(user); db.flush(); db.commit(); db.refresh(user)
```

**Đo được**

| Lời gọi Session trong `services/` | Số lần |
|---|---:|
| `db.execute(` | 319 |
| `db.get(` | 189 |
| `db.commit(` | **166** |
| `db.flush(` | 112 |
| `db.refresh(` | 108 |
| `db.add(` | 80 |
| `db.rollback(` | 28 |
| **Tổng** | **~1.000 điểm chạm** |

Và **5 lần `db.commit()` nằm trong `routers/`** — tầng trình bày đang quyết định
ranh giới giao dịch.

**Nguyên nhân**
Không có quy ước "ai commit". Mỗi service tự commit khi thấy tiện, nên khi service
A gọi service B, cả hai cùng commit → không có giao dịch nguyên tử.

**Ảnh hưởng dài hạn**

- **Không thể ghép hai thao tác thành một giao dịch.** Ví dụ nghiệp vụ thật:
  "duyệt báo giá → tạo dispatch → gửi thông báo" — nếu bước 2 lỗi sau khi bước 1
  đã commit, dữ liệu ở trạng thái nửa vời. Đây là rủi ro toàn vẹn dữ liệu, không
  phải rủi ro hiệu năng.
- **Test service phải có Postgres thật.** Đó chính là lý do 10/67 service có test.
- Đổi ORM/chiến lược truy vấn phải sửa ~1.000 chỗ.

**Refactor đề xuất** — không cần Repository đầy đủ, chỉ cần **rút commit lên một tầng**:

```python
# app/db/uow.py  ✨ Unit of Work
@contextmanager
def unit_of_work():
    """Một request = một giao dịch. Service KHÔNG commit."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

Bước chuyển đổi:
1. Cấm `db.commit()` mới trong service (thêm luật vào `check-*.mjs` hoặc ruff)
2. Gỡ commit khỏi service theo từng module, dùng `unit_of_work()` ở dependency
3. Repository chỉ trích cho các truy vấn phức tạp lặp lại (không phải mọi bảng)

**Lợi ích định lượng:** 166 điểm quyết định giao dịch → 1. Service test được bằng
session mock → mở đường cho M-04.

**Effort** 20–25 ngày · **Risk** **Cao** (đụng mọi luồng ghi) · **Priority** P1

---

## 🟠 M-03 · God service — `research_service.py`

**Ví dụ** — một file, 1.736 dòng, **29 hàm public**, **6 domain**:

```
dòng   84  ═══ ĐỀ TÀI (#17-#22) ═══
dòng  418  ═══ PUBLICATIONS (#23-#28) ═══
dòng  807  ═══ STUDENT MENTORSHIPS (#30-#32) ═══
dòng  980  ═══ LAB REGISTRATIONS (#33-#34c) ═══
dòng 1150  ═══ TEACHING COURSES (#35) ═══
```

Chính tác giả đã đánh dấu ranh giới bằng comment — nghĩa là **ranh giới module đã
tồn tại trong đầu người viết**, chỉ chưa thành file.

**Ảnh hưởng dài hạn**
Bốn developer sửa bốn domain khác nhau đều đụng cùng một file → conflict merge
liên tục. Với 30–50 dev, file này thành điểm nghẽn.

**Refactor đề xuất** — tách theo đúng ranh giới comment có sẵn:

```
services/research/
  ├── project_service.py       (~330 dòng)
  ├── publication_service.py   (~390)
  ├── mentorship_service.py    (~170)
  ├── registration_service.py  (~170)
  ├── teaching_service.py      (~250)
  └── _common.py               (_validate_members, _assert_staff_in_members)
```

Cơ học thuần tuý, không đổi logic. Đây là refactor **rẻ nhất và an toàn nhất**
trong toàn bộ danh sách.

**Effort** 5 ngày · **Risk** Thấp · **Priority** P2

---

## 🟠 M-04 · Vùng phủ test

**Đo được**

| | |
|---|---|
| Hàm test | 146 |
| Endpoint | 296 |
| **Router có test** | **0 / 41** |
| Service có test | 10 / 67 |
| conftest.py | 1 |
| Test cần Postgres thật | 2 file (tự skip) |

**Nguyên nhân** Không phải lười — là **hệ quả trực tiếp của M-02**. Service gọi
`db` thẳng nên muốn test phải dựng Postgres. Rào cản đó khiến người ta không viết.

**Ảnh hưởng dài hạn**
Không có lưới an toàn cho refactor. Mọi thay đổi phải kiểm tay. Với 5 năm và
nhiều thế hệ developer, đây là thứ khiến người ta *sợ động vào code cũ* — dấu
hiệu đầu tiên của việc rewrite.

> Điểm sáng: `app/tests/security/test_idor_routes.py` (thêm ở R8.3) chứng minh
> **có thể** test 329 bất biến mà không cần DB. Đó là khuôn mẫu nên nhân rộng.

**Refactor đề xuất**
1. `conftest.py` với fixture `client` + `as_role("admin")` — cho phép test router
   qua `TestClient` với DB SQLite in-memory hoặc session mock
2. Mục tiêu thực tế: **20 luồng nghiệp vụ chính**, không phải 100% coverage
3. Test hợp đồng cho M-01 (schema đầu ra) — một test chặn được cả lớp lỗi

**Effort** 15 ngày · **Risk** Thấp · **Priority** P1

---

## 🟠 M-05 · 380 mã lỗi dạng chuỗi, không có enum

**Ví dụ**

```python
raise AppException("SELF_DISABLE_FORBIDDEN", "...", 422)   # user_service.py
raise AppException("LAST_ADMIN_PROTECTED", "...", 422)     # user_service.py
raise unprocessable("NOT_PENDING", "...")                  # user_service.py
```

**Đo được**

| | |
|---|---|
| Chuỗi mã lỗi khác nhau trong service | **380** |
| Enum/hằng tập trung | **không có** |
| Mã lỗi frontend biết để xử lý riêng | **0** |

Frontend nhận mọi lỗi như nhau và chỉ hiển thị `message` — nghĩa là **380 mã đó
hiện không phục vụ ai**. Chúng là chi phí thuần: gõ sai một ký tự không ai phát
hiện, và không thể tra "mã này còn dùng không".

**Refactor đề xuất**

```python
# app/core/error_codes.py
class ErrorCode(str, Enum):
    SELF_DISABLE_FORBIDDEN = "SELF_DISABLE_FORBIDDEN"
    LAST_ADMIN_PROTECTED = "LAST_ADMIN_PROTECTED"
    ...
```

Lợi ích: gõ sai → lỗi biên dịch; xuất được sang frontend (giải quyết một phần
M-08); grep ra được mã chết.

**Effort** 3 ngày · **Risk** Thấp · **Priority** P2

---

## 🟡 M-06 · Khuôn mẫu CRUD lặp thủ công

**Đo được:** `_get_X_or_404` × **11**, `_X_dict` × **16**, `_assert_X_scope` × 3.

Cả 11 hàm `_get_X_or_404` có thân giống hệt: `db.get` → `if None` → `raise not_found`.

**Refactor đề xuất** — generic nhẹ, không phải framework:

```python
def get_or_404(db: Session, model: type[T], pk, msg: str) -> T:
    obj = db.get(model, pk)
    if obj is None:
        raise not_found(msg)
    return obj
```

**Lưu ý:** 16 hàm `_X_dict` **sẽ tự biến mất** khi làm M-01 (thay bằng
`response_model`). Đừng refactor chúng riêng — làm M-01 là đủ.

**Effort** 5 ngày (2 nếu làm cùng M-01) · **Risk** Thấp · **Priority** P3

---

## 🟡 M-07 · Frontend fat page, không có tầng server-state

**Đo được**

| | |
|---|---|
| File TSX > 500 dòng | **13** |
| File lớn nhất | `SampleFlow.tsx` **1.298 dòng** |
| `useState` toàn dự án | **705** |
| Context provider | 2 (Auth, Toast) |
| Thư viện server-state (React Query/SWR) | **0** |

`SampleFlow.tsx` chứa 3 tab + 4 modal + nhiều component con trong một file — cùng
bệnh với M-03 nhưng ở frontend.

**Ảnh hưởng dài hạn**
`useAsync` (đã sửa race ở R5.2) đang gánh vai trò của cả một thư viện server-state
nhưng không có cache, không dedupe, không invalidate. Mỗi lần điều hướng là gọi
lại API từ đầu. Khi số trang tăng, số `useState` tăng tuyến tính và không ai theo
dõi nổi trạng thái nào thuộc về ai.

**Refactor đề xuất**
1. Tách file >500 dòng theo ranh giới tab/modal (như M-03, cơ học)
2. Cân nhắc **TanStack Query** cho server-state — nhưng **chỉ khi** đã có M-01
   (không có type sinh tự động thì lợi ích giảm nhiều)

**Effort** 10 ngày · **Risk** Trung bình · **Priority** P3

---

## 🟡 M-08 · Hằng miền trùng lặp qua ranh giới ngôn ngữ

49 hằng ở backend, 36 bảng nhãn ở frontend. Ví dụ cụ thể:

```python
# lims-backend/app/services/user_service.py:374
ROLE_LABELS_VI = {"admin": "Quản trị viên", "leader": "Ban lãnh đạo", ...}
```
```typescript
// lims-frontend/src/types/index.ts:16
export const ROLE_LABELS: Record<Role, string> = { admin: 'Quản trị viên', ... }
```

Thêm một vai trò phải sửa **hai nơi bằng hai ngôn ngữ**. Quên một bên → giao diện
hiện mã thô `lab_manager` thay vì "Trưởng phòng lab".

**Refactor đề xuất** Backend là nguồn sự thật, expose qua `/api/v1/meta/enums`;
frontend nạp một lần lúc khởi động. Hoặc tối thiểu: sinh file TS từ Python trong CI.

**Effort** 4 ngày · **Risk** Thấp · **Priority** P3

---

## 🟡 M-09 · 51 import lười — dấu hiệu phụ thuộc vòng

```python
# app/services/attachment_service.py:65
from app.models.user import User  # local import tránh vòng import
```

51 chỗ import bên trong hàm. Mỗi chỗ là một vòng phụ thuộc bị né chứ không được
gỡ. Chúng làm chậm lần gọi đầu, giấu phụ thuộc thật khỏi công cụ phân tích, và
tích tụ tới lúc không gỡ được nữa.

`audit_service` được **39 service** import — nó là hub, và bất kỳ thay đổi nào ở
đó lan ra toàn hệ thống.

**Refactor đề xuất** Vẽ đồ thị phụ thuộc (`pydeps`), gỡ vòng bằng cách đưa kiểu
dùng chung xuống `app/core/types.py`. Đặt luật CI cấm import lười mới.

**Effort** 4 ngày · **Risk** Trung bình · **Priority** P3

---

## Điểm mạnh — phải ghi nhận

Review khắt khe không có nghĩa là chỉ nói xấu. Những điều sau **hiếm gặp** ở dự
án nội bộ và là lý do tôi trả lời "CÓ" ở phần cuối:

| Hạng mục | Bằng chứng |
|---|---|
| **Router mỏng đúng chuẩn** | **0/41** router có >10 nhánh điều kiện. Logic nằm đúng chỗ ở service. |
| **Kỷ luật migration** | **30/30** migration có `downgrade()`, chỉ 1 cái rỗng. Rất hiếm. |
| **Nợ kỹ thuật thấp** | **14 TODO, 0 FIXME, 0 HACK** trên 58.000 dòng. |
| **Comment giải thích *vì sao*** | `"CỐ Ý KHÔNG dùng $proxy_add_x_forwarded_for: biến đó CỘNG DỒN header client gửi"` — dạng comment giữ được tri thức qua nhiều thế hệ dev. |
| **Ngôn ngữ miền nhất quán** | Tên hàm/bảng bám sát nghiệp vụ VILAS, tham chiếu điều khoản ISO ngay trong code. |
| **Cấu hình tập trung** | 49 trường trong `config.py`, không rải `os.getenv` khắp nơi. |
| **Audit log bất biến** | Trigger chặn UPDATE/DELETE ở tầng DB, không dựa vào kỷ luật lập trình. |
| **Chi phí thêm module hợp lý** | Module `quotations` = **8 file mới + 6 file sửa** (main, models/__init__, App.tsx, nav.ts, types, rbac). |

---

## Điểm số

| Hạng mục | Điểm | Căn cứ |
|---|:---:|---|
| **Architecture** | **6**/10 | Phân tầng rõ, router mỏng. Trừ vì thiếu tầng DTO đầu ra và Repository |
| **Modularity** | **6**/10 | Thêm module = 8 file mới + 6 điểm đăng ký. Trừ vì God service 1.736 dòng |
| **Maintainability** | **5**/10 | M-01 + M-02 là hai thứ làm chi phí bảo trì tăng phi tuyến theo số dev |
| **Readability** | **8**/10 | Điểm cao nhất. Comment giải thích lý do, ngôn ngữ miền nhất quán, tham chiếu ISO |
| **Extensibility** | **6**/10 | Thêm module dễ. Thêm *trường* vào module có sẵn phải sửa 4 nơi (model, schema, service dict, FE type) |
| **Developer Experience** | **6**/10 | Cấu trúc đoán được. Trừ vì không có nguồn sự thật cho API và không test được nếu thiếu Postgres |
| **Testing** | **3**/10 | 0/41 router. 146 test cho 296 endpoint. Là hệ quả của M-02 |
| **Technical Debt** | **7**/10 | 14 TODO / 58k dòng là rất thấp. Nợ nằm ở kiến trúc, không ở code rác |
| **Documentation** | **7**/10 | Nhiều tài liệu vận hành mới. Thiếu ADR và sơ đồ kiến trúc tổng thể |
| **Overall Engineering Quality** | **6**/10 | Nền móng tốt, thiếu hai tầng trừu tượng then chốt |

---

## Trả lời câu hỏi cuối

> *Nếu đây là codebase của công ty 30–50 developer, nó có phát triển thêm 5 năm
> mà không cần rewrite không?*

### **CÓ — nhưng có điều kiện.**

**Vì sao không cần rewrite:** những thứ *không thể sửa dần* đều đã đúng. Phân tầng
nhất quán; router không chứa logic; migration có downgrade; ngôn ngữ miền rõ ràng;
nợ kỹ thuật thấp. Rewrite chỉ bắt buộc khi mô hình miền sai hoặc phân tầng lẫn lộn
— **cả hai đều không phải trường hợp này**.

Những vấn đề tôi tìm được đều là **thứ thiếu, không phải thứ sai**. Thêm một tầng
dễ hơn gỡ một mớ rối rất nhiều.

### Bốn điều kiện — thiếu bất kỳ điều nào thì 5 năm nữa sẽ phải rewrite

**1. Chặn nợ M-01 ngay hôm nay** *(0 ngày — chỉ là quy tắc)*
Mọi endpoint **mới** phải có `response_model`. Thêm test chặn hồi quy với
allowlist chỉ được ngắn đi. Không cần sửa 296 endpoint cũ ngay, nhưng **không
được thêm cái thứ 297 không có schema**. Đây là điều kiện rẻ nhất và quan trọng
nhất trong bốn điều.

**2. Rút `commit()` lên Unit of Work trong 12 tháng** *(20–25 ngày)*
Không phải vì đẹp, mà vì **166 điểm commit rải rác nghĩa là không có giao dịch
nguyên tử cho luồng nhiều bước** — với dữ liệu thử nghiệm chịu ISO/IEC 17025, đó
là rủi ro toàn vẹn. Nó cũng là thứ đang chặn M-04.

**3. Đưa vùng phủ test luồng chính lên ~20 kịch bản trong 6 tháng** *(15 ngày)*
Không cần 100% coverage. Cần đủ để một developer năm thứ ba **dám sửa code viết
năm thứ nhất**. Không có nó, mọi refactor đều bị hoãn, và hoãn refactor chính là
cơ chế sinh ra rewrite.

**4. Đặt trần kích thước file** *(5 ngày ban đầu, sau đó miễn phí)*
Luật CI: file >800 dòng thì fail. Hiện có 1 file BE (1.736) và 13 file FE vượt.
Trần cứng buộc phải tách khi module lớn lên, thay vì để nó thành God service —
`research_service.py` đã tự đánh dấu sẵn ranh giới, chỉ cần tách.

### Nếu vẫn phải rewrite — sẽ bắt đầu ở đâu

Không phải rewrite toàn bộ. Điểm vỡ đầu tiên sẽ là **tầng serialize**: 248 hàm trả
`dict` + 1.964 dòng type viết tay ở frontend. Khi số developer vượt ngưỡng mà
không ai nhớ hết hình dạng dữ liệu, đội sẽ bắt đầu viết endpoint v2 song song
thay vì sửa v1 — và **đó** là lúc rewrite bắt đầu, một cách âm thầm.

Điều kiện 1 ngăn đúng kịch bản đó, và nó tốn 0 ngày công.

---

## Lộ trình đề xuất

| Thời điểm | Việc | Ngày công | Vì sao bây giờ |
|---|---|---:|---|
| **Tuần này** | Quy tắc: endpoint mới bắt buộc `response_model` + test chặn | 1 | Chặn nợ tăng thêm, chi phí gần bằng 0 |
| **Tuần này** | Luật CI: trần 800 dòng/file | 1 | Chặn God service tiếp theo |
| **Tháng 1–2** | Tách `research_service.py` theo ranh giới có sẵn | 5 | Rẻ, an toàn, gỡ điểm nghẽn merge |
| **Tháng 1–2** | `ErrorCode` enum | 3 | Rẻ, mở đường cho FE xử lý lỗi theo mã |
| **Tháng 2–4** | conftest + 20 test luồng chính | 15 | Lưới an toàn cho mọi việc sau |
| **Tháng 4–9** | Unit of Work, gỡ commit khỏi service | 25 | Việc nặng nhất — cần lưới an toàn trước |
| **Tháng 6–12** | `response_model` cho endpoint cũ + sinh type FE | 20 | Làm dần theo module |
| **Năm 2** | Tách file FE >500 dòng, cân nhắc TanStack Query | 10 | Chỉ có ý nghĩa sau khi có type sinh tự động |

**Tổng: ~80 ngày công trải trên 2 năm** — khoảng **8% năng lực của một đội 5
người**. Đó là cái giá để không phải rewrite.
