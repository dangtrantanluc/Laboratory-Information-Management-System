# LIMS — Hệ thống Quản lý Phòng Thí nghiệm (ISO/IEC 17025:2017 · VILAS)

Phần mềm quản lý phòng thí nghiệm **học thuật / trường đại học** (có NCKH, giảng dạy,
hướng dẫn sinh viên) xây dựng theo tiêu chuẩn **ISO/IEC 17025:2017** cho phòng lab **đã
được công nhận VILAS** → kiểm soát tài liệu / hồ sơ chặt chẽ, audit đầy đủ.

Đây là **repo full-stack** gồm 3 phần, chạy chung bằng một file `docker-compose.yml`:

| Thư mục | Vai trò | Stack |
|---------|---------|-------|
| [`lims-backend/`](lims-backend/) | REST API (monolith) | FastAPI · SQLAlchemy 2 · PostgreSQL · Redis · MinIO |
| [`lims-frontend/`](lims-frontend/) | Web app (SPA, giao diện ERP) | React 18 · Vite · TypeScript · TailwindCSS |
| [`lims/docs/`](lims/docs/) | Tài liệu dự án (scope, SRS, contract) | Markdown (22 tài liệu) |

> Quy mô mục tiêu ~40 người dùng → **một FastAPI monolith + Postgres + Redis + MinIO là
> đủ**: không microservice, không message queue riêng, cron chạy in-process bằng APScheduler.

---

## 1. Tính năng — 7 module

Cây module 3 cấp đầy đủ + phân hạng P0/P1/P2 xem [`lims/docs/01-demo-scope.md`](lims/docs/01-demo-scope.md).

| Module | Tên | Nội dung chính |
|--------|-----|----------------|
| **M7** | Nền tảng & Quản trị | Auth (JWT + refresh rotation), Users, Departments (cây phòng ban), RBAC, Customers, Attachments (MinIO), Audit log (append-only §8.4), Notifications in-app |
| **M1** | Vòng đời Mẫu | Phiếu yêu cầu → mẫu (state machine) → phân công → chuyển giao (*chain of custody* §7.4) → nhập kết quả + versioning → duyệt (tách nhập/duyệt §7.8) → chốt done → trễ hạn (CRON-1/2) → xuất phiếu PDF → báo cáo on-time |
| **M2** | Hóa chất & Tồn kho | Danh mục + lô (lot/CoA/hạn dùng), đơn vị + quy đổi (Decimal, **không float**), giao dịch nhập/xuất/điều chỉnh (row-lock atomic + `balance_after` snapshot, **immutable**), tồn theo lô, cảnh báo dưới ngưỡng, FEFO, kiểm tra lại, xuất Excel, CRON-6 |
| **M3** | Kiểm soát Tài liệu | CRUD SOP/quy trình/biểu mẫu, version + lịch sử, quy trình duyệt (draft→review→approved→obsolete §8.3), thống kê lượt xem/tải/sửa |
| **M4** | Nhân sự & Thành tích NCKH | Hồ sơ + hợp đồng, chu kỳ nâng lương (tự tính, an toàn năm nhuận), lịch sử lương append-only, hồ sơ năng lực §6.2, đề tài NCKH / bài báo / sáng chế / hướng dẫn SV / giảng dạy / phục vụ cộng đồng, thống kê 3 chiều, CRON-3/4 |
| **M5** | Thiết bị & Hiệu chuẩn | Danh mục thiết bị, lịch hiệu chuẩn + chứng nhận, CRON-5 nhắc tới hạn |
| **M6** | Báo cáo & Thống kê | Dashboard KPI chéo module (1 round-trip, cache Redis 60s), biểu đồ, lọc thời gian thống nhất `[from, to)`, thống kê truy cập hệ thống (R15), xuất Excel/PDF |

**Ánh xạ điều khoản 17025** (§6.2 nhân sự · §6.4 thiết bị · §7.4 xử lý mẫu · §7.8 báo cáo ·
§8.3 kiểm soát tài liệu · §8.4 kiểm soát hồ sơ) → chi tiết ở mục E của demo-scope.

---

## 2. Kiến trúc

```
                          ┌──────────────────────────┐
   Trình duyệt  ───────▶  │  lims-web (nginx :3060)   │  React SPA build tĩnh
                          │  proxy /api → lims-api    │
                          └────────────┬─────────────┘
                                       │  /api/v1/*
                          ┌────────────▼─────────────┐
                          │  lims-api (FastAPI :8060) │  monolith, APScheduler in-process
                          └──┬─────────┬─────────┬────┘
                             │         │         │
                    ┌────────▼──┐ ┌────▼────┐ ┌──▼───────────┐
                    │ Postgres  │ │  Redis  │ │    MinIO     │
                    │  :5460    │ │  :6460  │ │  :9460/9461  │
                    │ dữ liệu   │ │ jti     │ │ file đính kèm│
                    │ nghiệp vụ │ │ denylist│ │ (S3 compat)  │
                    │           │ │ lockout │ │ CoA/MSDS/PDF │
                    │           │ │ rbac    │ │              │
                    │           │ │ cron    │ │              │
                    │           │ │ lock    │ │              │
                    └───────────┘ └─────────┘ └──────────────┘
```

- **API**: FastAPI monolith, prefix `/api/v1`, response bọc chuẩn `{success, data, meta}` /
  `{success, error{code,message,details}}`, correlationId xuyên suốt.
- **Redis**: JWT jti denylist, khóa đăng nhập (lockout), cache RBAC, **lock cron** (tránh
  chạy trùng khi có >1 instance).
- **MinIO**: lưu file mẫu, CoA, MSDS, tài liệu SOP, phiếu PDF — truy cập qua presigned URL
  (TTL 15 phút).
- **Cron**: APScheduler chạy trong tiến trình API (CRON-1…6).

---

## 3. Tech stack

**Backend** — Python 3.11+ · FastAPI 0.115 · SQLAlchemy 2.0 (sync) · Alembic · Pydantic v2 ·
PostgreSQL 15 (`pgcrypto`, `pg_trgm`, `citext`) · Redis 7 · MinIO (boto3) · JWT HS256
(python-jose) · bcrypt cost 12 (passlib) · APScheduler · reportlab (PDF) · openpyxl (Excel).

**Frontend** — React 18 · Vite 5 · TypeScript 5 · TailwindCSS 3 · react-router-dom 6 ·
recharts (biểu đồ) · lucide-react (icon). Không dùng thư viện state ngoài — Context API +
hook `useAsync`. Build tĩnh, phục vụ qua nginx (proxy `/api` → backend).

**Hạ tầng** — Docker Compose (Postgres + Redis + MinIO + API + Web).

---

## 4. Cấu trúc thư mục

```
demo/
├── docker-compose.yml         # full stack: pg + redis + minio + api + web
├── SRS-lims-mvp.docx          # SRS bản MVP (Word)
├── lims/
│   └── docs/                  # 22 tài liệu: demo-scope, SRS (M1–M6), contract (schema+API M1–M7)
├── lims-backend/              # FastAPI — xem lims-backend/README.md
│   ├── app/
│   │   ├── main.py            # wiring: CORS, middleware, exception handler, routers
│   │   ├── config.py          # Settings (pydantic-settings)
│   │   ├── scheduler.py       # APScheduler — CRON-1..6
│   │   ├── core/              # deps, rbac, security, redis_client, responses, exceptions, logging
│   │   ├── middleware/        # correlation_id, access_stat
│   │   ├── models/            # SQLAlchemy models (users, samples, chemicals, documents, hr…)
│   │   ├── schemas/           # Pydantic v2 request/response
│   │   ├── routers/           # ~30 router theo module
│   │   ├── services/          # business logic (một service/nghiệp vụ)
│   │   └── db/                # engine + session
│   ├── alembic/versions/      # 7 migration: M7→M1→M2→M4→M3→M5→M6
│   ├── requirements.txt
│   ├── Dockerfile · entrypoint.sh   # chờ PG → alembic upgrade head → uvicorn
│   └── seed_demo.sql
└── lims-frontend/             # React SPA — xem lims-frontend/README.md
    ├── src/
    │   ├── api/               # client theo domain (auth, samples, chemicals, hr…)
    │   ├── pages/             # mỗi nghiệp vụ một trang
    │   ├── components/        # layout (AppShell/Sidebar/Topbar) + ui + RequireAccess
    │   ├── context/           # AuthContext, ToastContext
    │   └── lib/               # api client, rbac, format, hooks
    ├── nginx.conf · Dockerfile
    └── package.json
```

---

## 5. Chạy nhanh — Docker Compose (khuyến nghị)

Yêu cầu: Docker + Docker Compose plugin.

```bash
cd demo
docker compose up -d --build
```

Compose khởi động 5 service. `lims-api` tự **chờ Postgres** → chạy **`alembic upgrade head`**
(tạo bảng + seed permissions/roles/4 phòng ban/admin) → khởi động uvicorn.

Truy cập:

| Thành phần | URL |
|-----------|-----|
| **Web app** | http://localhost:3060 |
| **API** | http://localhost:8060/api/v1 |
| **API docs** (Swagger, chỉ non-production) | http://localhost:8060/docs |
| **Health check** | http://localhost:8060/health/ready |
| **MinIO Console** | http://localhost:9461 (`minioadmin` / `minioadmin`) |

Kiểm tra API sẵn sàng:

```bash
curl http://localhost:8060/health/ready
# {"success":true,"data":{"status":"ok","checks":{"db":true,"redis":true}}}
```

Dừng / xóa dữ liệu:

```bash
docker compose down            # dừng, giữ volume
docker compose down -v         # dừng + xóa toàn bộ dữ liệu (pg/redis/minio)
```

### Bảng cổng (chọn riêng để không đụng dịch vụ khác trên máy)

| Dịch vụ | Cổng host | → Container |
|---------|:---------:|:-----------:|
| Web (nginx) | **3060** | 80 |
| API (FastAPI) | **8060** | 8060 |
| PostgreSQL | 5460 | 5432 |
| Redis | 6460 | 6379 |
| MinIO S3 | 9460 | 9000 |
| MinIO Console | 9461 | 9001 |

---

## 6. Đăng nhập lần đầu

Tài khoản admin **seed sẵn** (chỉ để khởi tạo):

```
Email:    admin@lims.local
Mật khẩu: ChangeMe@123
```

Lần đăng nhập đầu tiên trả `must_change_password: true` → **FE ép đổi mật khẩu ngay**
(admin seed có `password_changed_at = NULL`).

> ⚠️ **BẢO MẬT**: KHÔNG để mật khẩu mặc định trên staging/production (vi phạm NFR-SEC A05).
> Đổi `SEED_ADMIN_PASSWORD` + `JWT_SECRET` (≥ 32 ký tự) qua biến môi trường trước khi deploy.

Ví dụ đăng nhập bằng API:

```bash
curl -X POST http://localhost:8060/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@lims.local","password":"ChangeMe@123"}'
# → access_token (Bearer) + cookie refresh_token (HttpOnly)
```

---

## 7. Phân quyền — 4 vai trò (RBAC + phạm vi phòng ban)

| Role | Mô tả | Phạm vi dữ liệu |
|------|-------|-----------------|
| `admin` | Quản trị viên | Toàn hệ thống: users, phòng ban, mọi nghiệp vụ |
| `leader` | Ban lãnh đạo | Xem toàn hệ thống, duyệt, xem audit log |
| `accountant` | Kế toán | Chi phí hóa chất + lương/HĐ + báo cáo tài chính; **KHÔNG truy cập mẫu/kết quả** (cách ly nghiệp vụ) |
| `staff` | Nhân sự / KTV | Nghiệp vụ lab **theo phòng ban**; trưởng nhóm (`is_dept_lead`) được phân công / duyệt / chốt mẫu |

- Phạm vi (`scope`) mỗi quyền ∈ `{all, department, own}`, seed sẵn theo RBAC matrix.
- **Field-level RBAC**: cột giá (hóa chất) và lương/PII (nhân sự) bị *strip* tại tầng API
  cho vai trò không đủ quyền — không lộ qua response, không ghi ra log/audit (OWASP A01).
- Ma trận RBAC đầy đủ (module × hành động × vai trò): mục B của
  [`lims/docs/01-demo-scope.md`](lims/docs/01-demo-scope.md).

---

## 8. Cron job (APScheduler, in-process)

| Cron | Lịch | Logic | Thông báo |
|------|------|-------|-----------|
| CRON-1 | 07:00 hằng ngày | Mẫu tới hạn trong N ngày & chưa done | Người được giao |
| CRON-2 | 00:30 hằng ngày | Mẫu quá hạn & chưa done → `overdue` | Bắt buộc nhập lý do |
| CRON-3 | 07:00 hằng ngày | `next_salary_raise_date` còn 15/7/3 ngày | HR + lãnh đạo |
| CRON-4 | 07:00 hằng ngày | `contract_end_date` còn 30/15/7 ngày | HR |
| CRON-5 | 07:00 hằng ngày | Hiệu chuẩn `next_due_date` còn 30/15/7 ngày | Phụ trách thiết bị |
| CRON-6 | 07:00 hằng ngày | Hóa chất hết hạn / tới hạn kiểm tra lại | Phụ trách hóa chất |

Tất cả thông báo **chỉ in-app** (bảng `notifications`); email/Zalo để giai đoạn sau. Có
**lock Redis** tránh chạy trùng.

---

## 9. Phát triển local (không Docker)

**Backend** (cần Postgres + Redis + MinIO đang chạy):

```bash
cd lims-backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # chỉnh DATABASE_URL / REDIS_URL / MINIO_* về localhost
alembic upgrade head          # tạo bảng + seed
uvicorn app.main:app --reload --port 8060
```

Migration:

```bash
alembic upgrade head      # áp migration + seed
alembic downgrade base    # rollback toàn bộ
alembic current           # revision hiện tại
```

**Frontend**:

```bash
cd lims-frontend
npm install
cp .env.example .env       # VITE_API_BASE_URL=http://localhost:8060/api/v1
npm run dev                # http://localhost:5173
npm run build              # tsc -b && vite build
```

> Refresh token dùng cookie HttpOnly → FE gửi `credentials: include`; backend phải bật CORS
> **credentials** cho origin FE (`CORS_ORIGINS`).

---

## 10. Cấu hình (biến môi trường backend)

Khai báo trong `docker-compose.yml` hoặc `lims-backend/.env`:

| Biến | Mặc định | Ghi chú |
|------|----------|---------|
| `DATABASE_URL` | `postgresql+psycopg2://lims:lims@postgres:5432/lims` | |
| `REDIS_URL` | `redis://redis:6379/0` | |
| `MINIO_ENDPOINT` / `MINIO_PUBLIC_ENDPOINT` | `http://minio:9000` / `http://localhost:3060` | internal vs presigned URL |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` / `MINIO_BUCKET` | `minioadmin` / `minioadmin` / `lims-attachments` | |
| `JWT_SECRET` | *(đổi bắt buộc)* | ≥ 32 ký tự; HS256 |
| `ENVIRONMENT` | `development` | `production` → tắt `/docs` |
| `CORS_ORIGINS` | `http://localhost:3060,http://localhost:5173` | phân tách bằng dấu phẩy |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` | `admin@lims.local` / `ChangeMe@123` | **đổi trên production** |

Tham số bảo mật cố định: access token TTL 30 phút (≤ 60), refresh token 30 ngày (có
rotation), khóa đăng nhập sau 5 lần sai / 15 phút, upload tối đa 20 MB, presigned URL 15 phút.

---

## 11. Tài liệu dự án ([`lims/docs/`](lims/docs/))

Quy trình theo **contract-first** (không code khi contract chưa APPROVED):

```
00-meeting-note-analysis  →  01-demo-scope  →  SRS (mỗi module)  →  contract (schema + API mỗi module)
```

| Nhóm | Tài liệu |
|------|----------|
| Phân tích & scope | `00-meeting-note-analysis`, `01-demo-scope` |
| SRS | `02-srs-m2-chemical`, `05-srs-m1-sample`, `10-srs-m4-hr`, `13-srs-m3-document`, `16-srs-m5-equipment`, `19-srs-m6-reporting` |
| Contract (schema + API) | M1: `06`/`07` · M2: `03`/`04` · M3: `14`/`15` · M4: `11`/`12` · M5: `17`/`18` · M6: `20`/`21` · M7: `08`/`09` |

README chi tiết từng phần: [`lims-backend/README.md`](lims-backend/README.md) ·
[`lims-frontend/README.md`](lims-frontend/README.md).

**Bảng xác nhận tính năng cho khách hàng** (non-tech, có ô tick xác nhận):
[`LIMS-Xac-nhan-tinh-nang.xlsx`](LIMS-Xac-nhan-tinh-nang.xlsx) — 62 tính năng mô tả bằng
ngôn ngữ đời thường, khách hàng chọn *Đồng ý / Cần chỉnh sửa / Chưa cần / Cần trao đổi* +
ghi ý kiến, dùng để chốt scope trước khi bắt đầu làm.

---

## 12. Ghi chú thiết kế quan trọng

- **Không dùng float cho số lượng / tiền**: hóa chất và lương dùng `NUMERIC`/`Decimal` để
  tránh sai số tích lũy. Tồn kho lưu theo **base unit**, không cộng gộp chéo nhóm đo.
- **Bản ghi bất biến (append-only)**: `audit_logs` (trigger chặn UPDATE/DELETE §8.4), giao
  dịch hóa chất, lịch sử nâng lương, chuỗi hành trình mẫu, kết quả đã duyệt → sửa = tạo bản mới.
- **Không lộ ID tuần tự**: mẫu/phiếu hiển thị mã riêng (`SP-YYYY-…`), không expose bigint PK.
- **`balance_after` snapshot** trong mỗi giao dịch → audit được tồn tại từng thời điểm, không
  phụ thuộc `SUM()` runtime.
- **`attachments` polymorphic** dùng chung cho mẫu / tài liệu / CoA / MSDS.
