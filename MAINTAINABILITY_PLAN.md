# Kế hoạch cải thiện khả năng bảo trì — 80 ngày công / 24 tháng

> **TRẠNG THÁI 2026-07-26** — Giai đoạn 0, 1, 2 **ĐÃ XONG** (10/10 task, 6/6 cổng
> kiểm tra xanh). Biên bản nghiệm thu:
> [docs/maintainability-phase0-2-verification.md](docs/maintainability-phase0-2-verification.md)
>
> Giai đoạn 3 (Unit of Work) nay đã đủ điều kiện tiên quyết: lưới test đã có.

Phát hiện: [MAINTAINABILITY_REVIEW.md](./MAINTAINABILITY_REVIEW.md) · Tài liệu này = cách làm.

Mỗi task: **ID · file chính xác · code paste-được · tiêu chí nghiệm thu · giờ công · phụ thuộc · rủi ro**.

---

## 0. Nguyên tắc chi phối toàn bộ kế hoạch

### 0.1 Không có "tuần refactor"

80 ngày công trải trên 24 tháng ≈ **8% năng lực đội 5 người**, tức khoảng **nửa
ngày mỗi người mỗi tuần**. Kế hoạch được thiết kế để chạy **song song với việc
làm tính năng**, không phải thay thế nó. Mọi task đều:

- Có thể dừng giữa chừng mà hệ thống vẫn chạy
- Không yêu cầu đóng băng nhánh
- Không phá vỡ API đang phục vụ

### 0.2 Chặn nợ trước, trả nợ sau

Thứ tự **không** theo mức độ nghiêm trọng mà theo **tốc độ nợ tích tụ**. Giai đoạn 0
tốn 2 ngày nhưng ngăn 296 endpoint thành 400. Làm nó trước mọi thứ khác.

### 0.3 Ba chỉ số theo dõi hằng tháng

Dán vào README, cập nhật mỗi sprint. Không tiến bộ ba tháng liên tiếp = kế hoạch chết.

```bash
# scripts/maintainability-metrics.sh
echo "endpoint thiếu response_model: $(docker compose exec -T lims-api python -c "
from fastapi.routing import APIRoute
from app.main import app
print(sum(1 for r in app.routes if isinstance(r, APIRoute) and r.response_model is None))")"
echo "db.commit() trong services   : $(grep -rc 'db.commit()' lims-backend/app/services/*.py | awk -F: '{s+=\$2} END{print s}')"
echo "router có test               : $(ls lims-backend/app/tests/routers/ 2>/dev/null | grep -c test_)/41"
```

| Chỉ số | Hôm nay | Sau 6 tháng | Sau 12 tháng | Sau 24 tháng |
|---|---:|---:|---:|---:|
| Endpoint thiếu `response_model` | **294** | ≤200 | ≤80 | **0** |
| `db.commit()` trong service | **166** | ≤120 | ≤30 | **0** |
| Router có test | **0/41** | 12/41 | 25/41 | 41/41 |

### 0.4 Nhánh

Mỗi task một nhánh `maint/<id>-<mô-tả>`, merge độc lập. **Không gom nhiều task
vào một PR** — kế hoạch này sống nhờ việc mỗi mảnh nhỏ đủ để review trong 30 phút.

---

# GIAI ĐOẠN 0 — Chặn nợ · **2 ngày** · làm ngay tuần này

> Không có giai đoạn này thì 78 ngày còn lại là công cốc: nợ sinh nhanh hơn tốc độ trả.

## T0.1 — Bắt buộc `response_model` cho endpoint mới · **6h**

**File:** `lims-backend/app/tests/architecture/test_response_contract.py` ✨

```python
"""Chặn nợ hợp đồng API (M-01).

294/294 endpoint hiện KHÔNG khai báo response_model, nên OpenAPI không mô tả gì
về dữ liệu trả về và frontend phải viết tay 1.964 dòng type để đoán. Đổi tên một
trường ở backend không gây lỗi biên dịch ở đâu — nó hỏng lúc chạy, trên máy người
dùng.

Test này KHÔNG bắt sửa 294 endpoint cũ. Nó chỉ bảo đảm không có cái thứ 295.

LEGACY_ALLOWLIST chỉ được phép NGẮN ĐI. Thêm entry mới = từ chối trong review.
"""
import pathlib

from fastapi.routing import APIRoute

from app.main import app

_ALLOWLIST_FILE = pathlib.Path(__file__).parent / "response_model_legacy.txt"

# Endpoint không trả JSON body nên không cần response_model.
_EXEMPT_PATHS = {"/metrics"}


def _load_allowlist() -> set[str]:
    return {
        line.strip()
        for line in _ALLOWLIST_FILE.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }


def _endpoint_key(route: APIRoute) -> str:
    return f"{sorted(route.methods)[0]} {route.path}"


def _needs_contract(route: APIRoute) -> bool:
    if route.path in _EXEMPT_PATHS:
        return False
    # 204 No Content không có body
    if route.status_code == 204:
        return False
    return route.response_model is None


def test_no_new_endpoint_without_response_model():
    allowlist = _load_allowlist()
    offenders = sorted(
        _endpoint_key(r)
        for r in app.routes
        if isinstance(r, APIRoute) and _needs_contract(r) and _endpoint_key(r) not in allowlist
    )
    assert not offenders, (
        "Endpoint mới phải khai báo response_model.\n"
        "Xem MAINTAINABILITY_PLAN.md §T0.1.\n"
        "KHÔNG thêm vào response_model_legacy.txt — danh sách đó chỉ được ngắn đi.\n"
        + "\n".join(f"  - {o}" for o in offenders)
    )


def test_allowlist_only_shrinks():
    """Entry trong allowlist trỏ tới endpoint đã có response_model = nợ đã trả,
    phải xoá khỏi danh sách. Giữ lại sẽ che mất lần hồi quy sau."""
    allowlist = _load_allowlist()
    current = {_endpoint_key(r) for r in app.routes if isinstance(r, APIRoute) and _needs_contract(r)}
    stale = sorted(allowlist - current)
    assert not stale, (
        "Các endpoint sau đã có response_model — xoá khỏi response_model_legacy.txt:\n"
        + "\n".join(f"  - {s}" for s in stale)
    )
```

Sinh allowlist ban đầu:

```bash
docker compose exec -T lims-api python - <<'PY' > lims-backend/app/tests/architecture/response_model_legacy.txt
from fastapi.routing import APIRoute
from app.main import app
print("# Endpoint chưa có response_model — nợ kỹ thuật M-01.")
print("# DANH SÁCH NÀY CHỈ ĐƯỢC NGẮN ĐI. Xem MAINTAINABILITY_PLAN.md §T0.1.")
print(f"# Sinh ngày 2026-07-26 — {sum(1 for r in app.routes if isinstance(r, APIRoute) and r.response_model is None)} mục.")
for r in sorted(app.routes, key=lambda x: getattr(x, 'path', '')):
    if isinstance(r, APIRoute) and r.response_model is None and r.status_code != 204:
        print(f"{sorted(r.methods)[0]} {r.path}")
PY
```

**DoD**
- [ ] `pytest app/tests/architecture` xanh với allowlist đầy đủ
- [ ] Thêm một endpoint thử **không** có `response_model` → test đỏ; gỡ endpoint thử
- [ ] Xoá một dòng khỏi allowlist mà chưa sửa endpoint → test đỏ
- [ ] Ghi luật vào `CONTRIBUTING.md`

**Rủi ro** Rất thấp — chỉ thêm test. **Rollback** `git revert`.

---

## T0.2 — Trần kích thước file trong CI · **4h**

**File:** `scripts/check-file-size.mjs` ✨ + `.github/workflows/backend-ci.yml`

```javascript
#!/usr/bin/env node
/**
 * Trần kích thước file (M-03, M-07).
 *
 * research_service.py đã đạt 1.736 dòng và chứa 9 domain. Không có trần cứng thì
 * mọi service đều đi theo con đường đó: tiện nhất luôn là thêm hàm vào file sẵn có.
 *
 * Trần 800 dòng không phải con số thẩm mỹ — nó là ngưỡng mà 4 developer sửa 4
 * domain khác nhau bắt đầu conflict merge liên tục.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const LIMIT = 800;
const ROOT = process.cwd();

// File vượt trần TẠI THỜI ĐIỂM đặt luật. Danh sách chỉ được ngắn đi.
const GRANDFATHERED = new Map([
  ['lims-backend/app/services/research_service.py', 1736],  // T1.1 tách
  ['lims-backend/app/services/chemical_service.py', 850],   // T1.2 tách
  ['lims-frontend/src/pages/SampleFlow.tsx', 1298],         // T5.1 tách
  ['lims-frontend/src/pages/SampleDetail.tsx', 948],        // T5.1 tách
  // types/index.ts sẽ do openapi-typescript SINH RA (T4.4) → miễn trừ vĩnh viễn
]);

// File sinh tự động không tính — con người không đọc chúng.
const GENERATED = [/types\/api\.ts$/, /\.gen\.(ts|py)$/];

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (['node_modules', 'dist', '__pycache__', '.git', 'alembic'].includes(name)) continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(py|ts|tsx)$/.test(p)) out.push(p);
  }
  return out;
}

const problems = [];
for (const file of walk(join(ROOT, 'lims-backend/app')).concat(walk(join(ROOT, 'lims-frontend/src')))) {
  const rel = relative(ROOT, file);
  if (GENERATED.some((re) => re.test(rel))) continue;
  const lines = readFileSync(file, 'utf8').split('\n').length;
  const cap = GRANDFATHERED.get(rel) ?? LIMIT;
  if (lines > cap) {
    problems.push(`${rel}: ${lines} dòng (trần ${cap})`);
  } else if (GRANDFATHERED.has(rel) && lines < cap - 100) {
    problems.push(`${rel}: đã giảm còn ${lines} — hạ GRANDFATHERED xuống ${lines} hoặc bỏ hẳn`);
  }
}

if (problems.length) {
  console.error('✖ Vi phạm trần kích thước file:\n' + problems.map((p) => '  ' + p).join('\n'));
  console.error('\n  Tách theo ranh giới domain. Xem MAINTAINABILITY_PLAN.md §T0.2.');
  process.exit(1);
}
console.log(`✔ Không file nào vượt ${LIMIT} dòng (${GRANDFATHERED.size} file đang trong diện chuyển tiếp)`);
```

> **Cơ chế then chốt:** khi một file grandfathered giảm xuống, script **buộc phải
> hạ trần của nó**. Nợ chỉ đi một chiều.

**DoD** CI đỏ khi thêm file 900 dòng · xanh với trạng thái hiện tại.

---

# GIAI ĐOẠN 1 — Thắng nhanh · **8 ngày** · tháng 1–2

## T1.1 — Tách `research_service.py` (1.736 dòng → 9 file) · **4 ngày**

Tác giả đã đánh dấu sẵn ranh giới. Đây là refactor **cơ học**, không đổi logic.

| Vùng | Dòng | Kích thước | File đích |
|---|---|---:|---|
| Helpers chung | 36–82 | 47 | `research/_shared.py` |
| ĐỀ TÀI | 83–417 | 335 | `research/project_service.py` |
| PUBLICATIONS | 418–806 | 389 | `research/publication_service.py` |
| STUDENT MENTORSHIPS | 807–979 | 173 | `research/mentorship_service.py` |
| LAB REGISTRATIONS | 980–1149 | 170 | `research/registration_service.py` |
| TEACHING COURSES | 1150–1332 | 183 | `research/teaching_service.py` |
| COMMUNITY SERVICES | 1333–1494 | 162 | `research/community_service.py` |
| COMPETENCE SUMMARY | 1495–1586 | 92 | `research/competence_service.py` |
| STATS | 1587–1736 | 150 | `research/stats_service.py` |

**Quy trình bắt buộc — mỗi vùng một commit riêng:**

```bash
# 1. Tạo package, giữ import cũ hoạt động
mkdir -p app/services/research
# app/services/research/__init__.py — mặt tiền tương thích ngược
cat > app/services/research/__init__.py <<'PY'
"""Package research — tách từ research_service.py 1.736 dòng (M-03).

__init__ re-export mọi hàm public để 100% lời gọi cũ
(`from app.services import research_service`) tiếp tục chạy trong lúc chuyển đổi.
Gỡ mặt tiền này khi mọi caller đã import trực tiếp từ module con.
"""
from app.services.research.project_service import *      # noqa: F401,F403
from app.services.research.publication_service import *  # noqa: F401,F403
# ... thêm dần theo từng commit
PY

# 2. Sau mỗi vùng: chạy test + kiểm không sót hàm
docker compose exec -T lims-api python - <<'PY'
import app.services.research_service as old, app.services.research as new
missing = {n for n in dir(old) if not n.startswith('_')} - {n for n in dir(new) if not n.startswith('_')}
assert not missing, f"Hàm bị mất khi tách: {sorted(missing)}"
print(f"✔ {len([n for n in dir(new) if not n.startswith('_')])} hàm public đầy đủ")
PY
```

**DoD**
- [ ] Mỗi file mới < 450 dòng
- [ ] `pytest app/tests` xanh sau **từng** commit (9 commit)
- [ ] Script đối chiếu ở trên không báo hàm mất
- [ ] `grep -rn "research_service" app/routers/` vẫn hoạt động (mặt tiền)
- [ ] `research_service.py` cũ xoá ở commit cuối, `GRANDFATHERED` gỡ entry

**Rủi ro** Thấp — di chuyển cơ học. **Rollback** revert từng commit.

## T1.2 — Tách `chemical_service.py` (850 dòng) · **1 ngày**

Cùng quy trình. Xác định ranh giới trước:

```bash
grep -n "^# ===\|^def " app/services/chemical_service.py | head -40
```

## T1.3 — `ErrorCode` enum (73 mã) · **2 ngày**

**Đo lại chính xác:** **73 mã lỗi duy nhất** đang dùng (không phải 380 như ước
lượng ban đầu — grep cũ đếm cả chuỗi hoa không phải mã lỗi). 73 là con số quản lý được.

Quét đã lộ ra lỗi thật: **`DEPARTMENT_NOT_FOUND` và `DEPT_NOT_FOUND` cùng tồn tại**
cho cùng một tình huống. Frontend muốn xử lý riêng phải biết cả hai.

**File:** `lims-backend/app/core/error_codes.py` ✨

```python
"""Mã lỗi tập trung (M-05).

Trước đây là 73 chuỗi literal rải rác trong 67 service. Hệ quả:
  - Gõ sai một ký tự không ai phát hiện (không có compiler nào kiểm chuỗi)
  - Không grep ra được mã nào đã chết
  - Trùng nghĩa mà không biết: DEPARTMENT_NOT_FOUND và DEPT_NOT_FOUND cùng tồn tại
  - Frontend không thể xử lý theo mã vì không có nguồn danh sách

Kế thừa `str` để `ErrorCode.X == "X"` — mọi so sánh chuỗi cũ vẫn đúng.
"""
from enum import Enum


class ErrorCode(str, Enum):
    # ── Xác thực & tài khoản ──
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    ACCOUNT_PENDING_APPROVAL = "ACCOUNT_PENDING_APPROVAL"
    EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"
    EMAIL_EXISTS = "EMAIL_EXISTS"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_INVALID = "TOKEN_INVALID"
    TOKEN_REUSED = "TOKEN_REUSED"
    # ── Không tìm thấy ──
    DEPARTMENT_NOT_FOUND = "DEPARTMENT_NOT_FOUND"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    EQUIPMENT_NOT_FOUND = "EQUIPMENT_NOT_FOUND"
    CUSTOMER_NOT_FOUND = "CUSTOMER_NOT_FOUND"
    # ... 73 mã, nhóm theo miền
    # ── Quy tắc nghiệp vụ ──
    LAST_ADMIN_PROTECTED = "LAST_ADMIN_PROTECTED"
    SELF_DISABLE_FORBIDDEN = "SELF_DISABLE_FORBIDDEN"
    CAPA_CLOSED_IMMUTABLE = "CAPA_CLOSED_IMMUTABLE"
    # ── Hệ thống ──
    SERVER_BUSY = "SERVER_BUSY"
    CRON_ALREADY_RUNNING = "CRON_ALREADY_RUNNING"
```

Sinh khung ban đầu:

```bash
grep -rhoE '(AppException|conflict|unprocessable)\(\s*"[A-Z_]+"' lims-backend/app --include="*.py" \
  | grep -oE '"[A-Z_]+"' | tr -d '"' | sort -u \
  | awk '{printf "    %s = \"%s\"\n", $1, $1}'
```

Kèm test chặn hồi quy:

```python
def test_no_raw_error_code_strings():
    """Mã lỗi phải dùng ErrorCode.X, không phải chuỗi literal."""
    import re, pathlib
    pat = re.compile(r'(?:AppException|conflict|unprocessable)\(\s*"[A-Z_]{3,}"')
    offenders = [
        f"{p}:{i}" for p in pathlib.Path("app").rglob("*.py")
        for i, line in enumerate(p.read_text().splitlines(), 1) if pat.search(line)
    ]
    assert not offenders, "Dùng ErrorCode enum:\n" + "\n".join(offenders)
```

**DoD** 73 mã trong enum · 0 chuỗi literal còn lại · gộp `DEPT_NOT_FOUND` →
`DEPARTMENT_NOT_FOUND` (giữ alias 1 sprint rồi xoá) · `pytest` xanh.

## T1.4 — Trích `get_or_404` dùng chung · **1 ngày**

11 hàm `_get_X_or_404` có thân giống hệt nhau.

```python
# app/core/db_helpers.py ✨
from typing import TypeVar
from sqlalchemy.orm import Session
from app.core.exceptions import not_found

T = TypeVar("T")


def get_or_404(db: Session, model: type[T], pk, message: str) -> T:
    """db.get + kiểm None + raise. Thay 11 bản sao chép giống hệt nhau."""
    obj = db.get(model, pk)
    if obj is None:
        raise not_found(message)
    return obj
```

> **Không** trích 16 hàm `_X_dict`: chúng sẽ tự biến mất ở Giai đoạn 4 khi thay
> bằng `response_model`. Refactor chúng bây giờ là làm việc hai lần.

---

# GIAI ĐOẠN 2 — Lưới an toàn · **15 ngày** · tháng 2–4

> Đây là điều kiện tiên quyết của Giai đoạn 3. Không có test, việc gỡ 166 `commit()`
> là **không thể chấp nhận rủi ro**.

## T2.1 — Hạ tầng test: conftest + fixture · **4 ngày**

**Vì sao 0/41 router có test:** service gọi `db` trực tiếp nên muốn test phải dựng
Postgres. Rào cản đó khiến không ai viết. Cần gỡ rào trước.

**File:** `lims-backend/app/tests/conftest.py` (thay thế bản hiện có)

```python
"""Fixture dùng chung cho test router (M-04).

Dùng Postgres THẬT trong container, không SQLite: schema dùng CITEXT, INET,
gen_random_uuid() và trigger — SQLite không có, nên test chạy trên SQLite sẽ
xanh mà production vẫn hỏng.

Mỗi test chạy trong một giao dịch rồi rollback → nhanh, cô lập, không cần dọn.
"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.deps import get_current_user
from app.db.database import Base, get_db
from app.main import app

TEST_DB_URL = os.getenv("TEST_DATABASE_URL")
requires_db = pytest.mark.skipif(not TEST_DB_URL, reason="TEST_DATABASE_URL chưa đặt")


@pytest.fixture(scope="session")
def engine():
    if not TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL chưa đặt")
    eng = create_engine(TEST_DB_URL, poolclass=None)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    """Session bọc trong giao dịch, rollback sau mỗi test.

    Nhanh hơn TRUNCATE nhiều lần, và không test nào nhìn thấy dữ liệu của test khác.
    """
    conn = engine.connect()
    trans = conn.begin()
    session = sessionmaker(bind=conn)()
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def client(db) -> TestClient:
    """TestClient dùng chung session với fixture db."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def as_role(client, db):
    """Đăng nhập giả theo vai trò — bỏ qua bcrypt và JWT.

    Test router quan tâm tới RBAC và hình dạng response, không phải cơ chế đăng
    nhập (đã có test riêng). Bỏ qua bcrypt tiết kiệm ~250ms mỗi test.
    """
    from app.core.deps import CurrentUser

    def _login(role: str = "admin", department_id=None, is_dept_lead: bool = False):
        fake = CurrentUser(
            id=uuid.uuid4(), role=role, department_id=department_id,
            is_dept_lead=is_dept_lead, jti="test", token_exp=9999999999,
        )
        app.dependency_overrides[get_current_user] = lambda: fake
        return fake

    yield _login
    app.dependency_overrides.pop(get_current_user, None)
```

CI phải cấp Postgres — `backend-ci.yml` đã có service này ✔, chỉ cần đặt biến:

```yaml
      - run: python -m pytest app/tests -v
        env:
          TEST_DATABASE_URL: postgresql+psycopg2://lims:lims@localhost:5432/lims_test
```

**DoD** Một test router mẫu chạy < 200ms · hai test không thấy dữ liệu của nhau ·
CI chạy đủ test tích hợp (21 skip hiện tại → 0).

## T2.2 — 20 test luồng nghiệp vụ chính · **10 ngày**

**Không nhắm 100% coverage.** Nhắm đủ để developer năm thứ ba dám sửa code năm
thứ nhất.

| # | Luồng | Router | Vì sao chọn |
|---|---|---|---|
| 1 | Đăng nhập → đổi mật khẩu lần đầu | auth | Cửa vào hệ thống |
| 2 | Đăng ký → xác thực mail → duyệt | auth, users | m30, nhiều trạng thái |
| 3 | RBAC: staff KHÔNG xem được dữ liệu phòng khác | samples | Bảo mật cốt lõi |
| 4 | Nhận mẫu → báo giá → duyệt → chuyển lab → trả KQ | sample_flow, quotations | **Luồng nghiệp vụ chính** |
| 5 | Tạo tài liệu → gửi duyệt → phê duyệt → ban hành | documents | ISO §8.3 |
| 6 | Nhập hoá chất → xuất kho → cảnh báo tồn thấp | chemicals | Có tính toán số |
| 7 | Hiệu chuẩn thiết bị → tính hạn kế tiếp | equipments | Có logic ngày tháng |
| 8 | Mở CAPA → hành động → đóng → bất biến sau đóng | nonconformities | Bất biến nghiệp vụ |
| 9 | Đánh giá rủi ro → tính band từ P×I | risks | Logic thuần, dễ test |
| 10 | Upload đính kèm → tải về → soft-delete | attachments | Có chạm MinIO |
| … | (10 luồng còn lại theo mức dùng thực tế) | | |

**Khuôn mẫu bắt buộc** — dùng cho cả 20 test:

```python
# app/tests/routers/test_sample_flow.py
@requires_db
class TestSampleIntakeFlow:
    """Luồng nghiệp vụ chính: nhận mẫu → báo giá → chuyển lab → trả kết quả."""

    def test_reception_can_create_intake(self, client, as_role, seed_customer):
        as_role("reception")
        res = client.post("/api/v1/sample-intakes", json={
            "customer_name": "Công ty ABC", "description": "Mẫu nước thải",
        })
        assert res.status_code == 201
        body = res.json()["data"]
        # Khoá HÌNH DẠNG response — chính là thứ M-01 đang thiếu
        assert set(body) >= {"id", "code", "status", "customer_name"}
        assert body["status"] == "received"

    def test_lab_staff_cannot_create_intake(self, client, as_role):
        """RBAC: chỉ phòng nhận mẫu được tạo phiếu."""
        as_role("staff")
        assert client.post("/api/v1/sample-intakes", json={...}).status_code == 403

    def test_cannot_dispatch_before_payment(self, client, as_role, seed_intake):
        """Bất biến nghiệp vụ: chưa thanh toán thì không chuyển lab."""
        as_role("reception")
        res = client.post(f"/api/v1/sample-intakes/{seed_intake.id}/dispatch", json={...})
        assert res.status_code == 422
        assert res.json()["error"]["code"] == ErrorCode.PAYMENT_REQUIRED
```

**Ba quy tắc chống test giòn:**
1. **Khẳng định hình dạng response, không khẳng định toàn bộ nội dung.** `set(body) >= {...}`
   cho phép thêm trường mà không làm đỏ test.
2. **Dùng `ErrorCode.X`, không dùng chuỗi.** Đổi tên mã lỗi thì test đỏ ở chỗ đúng.
3. **Mỗi test một khẳng định nghiệp vụ.** Tên test là câu mô tả quy tắc.

**DoD** 20 luồng · toàn bộ suite < 60s · chạy 3 lần liên tiếp cùng kết quả (không flaky).

## T2.3 — Đo và công bố vùng phủ · **1 ngày**

```yaml
      - run: pip install pytest-cov
      - run: python -m pytest app/tests --cov=app --cov-report=term --cov-report=xml
      # Ngưỡng CHỈ tăng, không giảm — chống trôi ngược
      - run: python -m pytest app/tests --cov=app --cov-fail-under=35
```

Bắt đầu ở mức đo được thực tế, nâng 5% mỗi quý.

---

# GIAI ĐOẠN 3 — Unit of Work · **25 ngày** · tháng 4–9

> Việc nặng nhất và rủi ro nhất. **Không bắt đầu trước khi Giai đoạn 2 xong.**

## T3.1 — Hạ tầng UoW + cấm commit mới · **3 ngày**

**File:** `lims-backend/app/db/uow.py` ✨

```python
"""Unit of Work — một request, một giao dịch (M-02).

Vấn đề đang có: 166 lời gọi db.commit() rải rác trong service, 5 cái nằm trong
router. Khi service A gọi service B, cả hai cùng commit → KHÔNG có giao dịch
nguyên tử. Luồng "duyệt báo giá → tạo dispatch → gửi thông báo" mà bước 2 lỗi
sau khi bước 1 đã commit sẽ để dữ liệu ở trạng thái nửa vời. Với hồ sơ thử
nghiệm chịu ISO/IEC 17025, đó là rủi ro toàn vẹn dữ liệu chứ không phải hiệu năng.

Sau chuyển đổi: service chỉ `db.flush()` khi cần id; commit do tầng ngoài quyết định.
"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session

from app.db.database import SessionLocal


@contextmanager
def unit_of_work() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_uow() -> Generator[Session, None, None]:
    """Dependency FastAPI thay cho get_db.

    Commit khi handler trả về bình thường; rollback nếu ném exception. Handler
    không cần biết gì về giao dịch.
    """
    with unit_of_work() as db:
        yield db
```

**Test chặn nợ mới** (cùng cơ chế allowlist như T0.1):

```python
def test_no_new_commit_in_services():
    """db.commit() trong service = ranh giới giao dịch không xác định.
    LEGACY_COMMITS chỉ được giảm."""
    import pathlib, json
    baseline = json.loads(pathlib.Path("app/tests/architecture/commit_baseline.json").read_text())
    current = {
        p.name: p.read_text().count("db.commit()")
        for p in pathlib.Path("app/services").rglob("*.py")
    }
    grew = {
        f: (current[f], baseline.get(f, 0))
        for f in current if current[f] > baseline.get(f, 0)
    }
    assert not grew, f"Thêm db.commit() mới: {grew}. Dùng unit_of_work — xem MAINTAINABILITY_PLAN §T3.1"
```

## T3.2 — Chuyển đổi theo module · **20 ngày**

**Thứ tự theo rủi ro tăng dần** — học trên module ít nghiệp vụ trước:

| Đợt | Module | commit() | Ngày | Vì sao thứ tự này |
|---|---|---:|---:|---|
| 1 | `customer`, `department`, `test_parameter` | ~8 | 2 | CRUD thuần, ít nhánh — học quy trình |
| 2 | `user`, `account`, `auth` | 17 | 4 | Đã có test tốt nhất (m30 + R8.3) |
| 3 | `document`, `document_version` | 11 | 3 | Có luồng duyệt nhiều bước |
| 4 | `chemical`, `chemical_txn` | 10 | 3 | Có tính toán tồn kho |
| 5 | `sample`, `sample_flow`, `quotation` | 16 | 4 | **Luồng chính** — làm khi đã quen |
| 6 | `research/*` (sau T1.1) | 19 | 3 | Đã tách nên dễ hơn con số gợi ý |
| 7 | Phần còn lại | ~85 | 1 | Chủ yếu là cron/report, ít rủi ro |

**Khuôn mẫu chuyển đổi cho từng hàm:**

```python
# TRƯỚC — service tự quyết định giao dịch
def create_customer(db, *, name, ...):
    c = Customer(name=name)
    db.add(c)
    audit_service.log_action(db, action="CREATE", ...)
    db.commit()          # ← gỡ
    db.refresh(c)        # ← thường không cần nữa
    return _serialize(c)

# SAU — service chỉ mô tả việc cần làm
def create_customer(db, *, name, ...):
    c = Customer(name=name)
    db.add(c)
    db.flush()           # cần id cho audit log
    audit_service.log_action(db, action="CREATE", resource_id=c.id, ...)
    return _serialize(c)
    # commit do get_db_uow lo khi handler trả về
```

**Bốn cạm bẫy phải kiểm mỗi đợt:**

| Cạm bẫy | Triệu chứng | Cách xử lý |
|---|---|---|
| `db.refresh()` sau khi gỡ commit | `expire_on_commit=False` nên object vẫn dùng được | Gỡ `refresh()`, dùng `flush()` nếu cần server default |
| Hàm trả object ORM ra ngoài request | `DetachedInstanceError` | Serialize **trong** service, đừng trả entity |
| Background task dùng session của request | Session đã đóng | Task nền phải tự mở `unit_of_work()` |
| Cron job | Không có request nên không có dependency | Cron dùng `with unit_of_work() as db:` trực tiếp |

**DoD mỗi đợt** Test module đó xanh · `db.commit()` của module = 0 ·
`commit_baseline.json` cập nhật giảm · smoke test luồng chính trên môi trường dev.

## T3.3 — Gỡ 5 `commit()` trong router · **1 ngày**

Tầng trình bày không được quyết định giao dịch.

```bash
grep -rn "db.commit()" app/routers/
```

## T3.4 — Kiểm chứng tính nguyên tử · **1 ngày**

Test chứng minh việc này có tác dụng thật:

```python
@requires_db
def test_multi_step_flow_is_atomic(client, as_role, db, monkeypatch):
    """Bước 2 lỗi → bước 1 KHÔNG được để lại dữ liệu.

    Trước UoW test này thất bại: create_dispatch đã commit trước khi
    notification lỗi, để lại dispatch mồ côi.
    """
    as_role("reception")
    from app.services import notification_service
    monkeypatch.setattr(notification_service, "notify_dispatch",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("SMTP down")))

    before = db.execute(text("SELECT count(*) FROM sample_dispatches")).scalar()
    res = client.post(f"/api/v1/sample-intakes/{intake_id}/dispatch", json={...})
    assert res.status_code == 500
    after = db.execute(text("SELECT count(*) FROM sample_dispatches")).scalar()
    assert after == before, "Giao dịch không nguyên tử — còn dispatch mồ côi"
```

---

# GIAI ĐOẠN 4 — Hợp đồng API · **20 ngày** · tháng 6–12 *(song song GĐ3)*

## T4.1 — Kiểu generic dùng chung · **2 ngày**

```python
# app/schemas/_envelope.py ✨
"""Vỏ response chuẩn — khớp đúng cấu trúc ok()/paginated() đang trả."""
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    success: bool = True
    data: T


class PageMeta(BaseModel):
    page: int
    limit: int
    total: int
    hasNext: bool


class Page(BaseModel, Generic[T]):
    success: bool = True
    data: list[T]
    meta: PageMeta
```

## T4.2 — Chuyển đổi theo router · **15 ngày**

294 endpoint / 41 router. **Thứ tự theo mức frontend phụ thuộc**, không theo số lượng:

| Đợt | Router | Endpoint | Ngày |
|---|---|---:|---:|
| 1 | auth, users | 25 | 2 |
| 2 | samples, sample_flow, quotations | 46 | 3 |
| 3 | documents, forms | 36 | 3 |
| 4 | chemicals, chemical_lots, equipments | 31 | 2 |
| 5 | research (sau T1.1) | 31 | 2 |
| 6 | hr_profiles, activities, activity_reports | 32 | 2 |
| 7 | 30 router còn lại | 93 | 1 |

**Khuôn mẫu:**

```python
# app/schemas/customer.py — thêm phần Out
class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    contact: str | None
    created_at: datetime

# app/routers/customers.py
@router.get("", response_model=Page[CustomerOut])
def list_customers(...):
    items, total = customer_service.list_customers(...)
    return paginated(items, page=page, limit=limit, total=total)
```

**Sau mỗi router: xoá dòng tương ứng khỏi `response_model_legacy.txt`** — test
T0.1 `test_allowlist_only_shrinks` sẽ bắt nếu quên.

**Cạm bẫy:** FastAPI **lọc bỏ** trường không khai trong `response_model`. Nếu
frontend đang dùng một trường mà schema quên khai, nó biến mất **im lặng**. Bắt buộc:

```python
def test_response_model_covers_service_output(client, as_role):
    """Schema phải chứa mọi khoá service trả về — thiếu là mất trường im lặng."""
    as_role("admin")
    body = client.get("/api/v1/customers?limit=1").json()["data"][0]
    assert set(body) == set(CustomerOut.model_fields), (
        f"Lệch: thiếu {set(CustomerOut.model_fields) - set(body)}, "
        f"thừa {set(body) - set(CustomerOut.model_fields)}"
    )
```

## T4.3 — Sinh type frontend từ OpenAPI · **2 ngày**

```json
// lims-frontend/package.json
"scripts": {
  "gen:api": "openapi-typescript http://localhost:8060/openapi.json -o src/types/api.gen.ts",
  "check:api-types": "npm run gen:api && git diff --exit-code src/types/api.gen.ts"
}
```

```yaml
# frontend-ci.yml — CI đỏ nếu type sinh ra lệch với type đã commit
      - run: npm run check:api-types
```

**Chuyển đổi `types/index.ts` (1.964 dòng viết tay):**

```typescript
// src/types/index.ts — giữ file này cho type THUẦN FRONTEND
export type { CustomerOut as Customer } from './api.gen';   // re-export dần
// Xoá interface viết tay khi đã có bản sinh tương ứng
```

**DoD** `api.gen.ts` sinh được · CI bắt được khi BE đổi schema mà FE chưa sinh lại ·
`types/index.ts` giảm ≥60% dòng.

## T4.4 — Xoá 16 hàm `_X_dict` · **1 ngày**

Chúng thừa sau T4.2 — `from_attributes=True` serialize thẳng từ ORM object.

---

# GIAI ĐOẠN 5 — Frontend · **10 ngày** · năm 2

> Chỉ có ý nghĩa **sau** T4.3. Không có type sinh tự động thì lợi ích giảm nhiều.

## T5.1 — Tách 4 file >800 dòng · **4 ngày**

| File | Dòng | Tách thành |
|---|---:|---|
| `SampleFlow.tsx` | 1.298 | `sampleFlow/IntakesTab · DispatchesTab · InfoRequestsTab · modals/*` |
| `SampleDetail.tsx` | 948 | `sampleDetail/InfoPanel · ResultsPanel · AttachmentsPanel` |
| `Forms.tsx` | 787 | `forms/TemplatesTab · SubmissionsTab · HistoryTab` |
| `EquipmentDetail.tsx` | 748 | `equipmentDetail/InfoPanel · CalibrationTable` |

Cơ học như T1.1. Mỗi file một commit, `npm run check` sau mỗi commit.

## T5.2 — Cân nhắc TanStack Query · **6 ngày** *(quyết định, không mặc định)*

**Chỉ làm nếu** ≥2 trong 3 điều sau đúng sau 12 tháng:
- `useState` vượt 900 (hiện 705)
- Có ≥3 báo cáo lỗi "dữ liệu cũ hiện lại sau khi sửa"
- Trang danh sách gọi lại API mỗi lần điều hướng gây phàn nàn

`useAsync` (sau R5.2) đã xử lý race + huỷ request. Thiếu cache/dedupe/invalidate.
Thêm thư viện là **quyết định kiến trúc**, không phải dọn dẹp — cần đủ dữ liệu để
biện minh.

---

## Tổng hợp

| GĐ | Nội dung | Ngày | Thời điểm | Chặn GĐ sau |
|---|---|---:|---|:--:|
| 0 | Chặn nợ (test contract + trần file) | **2** | Tuần này | ✅ |
| 1 | Tách God service, ErrorCode, get_or_404 | **8** | Tháng 1–2 | — |
| 2 | conftest + 20 test luồng chính | **15** | Tháng 2–4 | ✅ chặn GĐ3 |
| 3 | Unit of Work | **25** | Tháng 4–9 | — |
| 4 | response_model + sinh type FE | **20** | Tháng 6–12 | — |
| 5 | Frontend | **10** | Năm 2 | — |
| | **Tổng** | **80** | 24 tháng | |

## Nếu chỉ làm được 20% (16 ngày)

Chọn đúng 3 việc này — chúng bảo vệ 80% giá trị:

1. **T0.1 + T0.2** (2 ngày) — chặn nợ tăng. Không có gì rẻ bằng.
2. **T2.1 + T2.2 rút gọn 10 luồng** (9 ngày) — lưới an toàn để dám refactor.
3. **T1.1 + T1.3** (5 ngày) — gỡ điểm nghẽn merge và mã lỗi.

Bỏ qua UoW và response_model **không** giết dự án trong 2 năm; bỏ qua ba việc
trên thì giết.

## Rủi ro của chính kế hoạch

| Rủi ro | Dấu hiệu sớm | Giảm thiểu |
|---|---|---|
| Kế hoạch chết sau 3 tháng | Ba chỉ số §0.3 đứng yên 2 sprint | Đưa vào định nghĩa Done của sprint, không phải "việc phụ" |
| GĐ3 làm hỏng dữ liệu | Test T3.4 đỏ | Không bắt đầu GĐ3 trước khi GĐ2 xong — **điều kiện cứng** |
| `response_model` làm mất trường im lặng | FE thiếu dữ liệu sau deploy | Test đối chiếu ở T4.2, bắt buộc mỗi router |
| Tách file gây conflict với tính năng đang làm | Merge đau đớn | Tách vào đầu sprint, thông báo trước, merge nhanh |
| Allowlist bị nới thay vì ngắn | PR thêm dòng vào legacy | `test_allowlist_only_shrinks` + luật review |
