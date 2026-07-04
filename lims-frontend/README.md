# LIMS — Hệ thống Quản lý Phòng Thí nghiệm (Frontend VILAS)

Frontend cho hệ thống LIMS theo chuẩn VILAS / ISO-IEC 17025, **kết nối backend thật**
(FastAPI, mặc định `http://localhost:8060/api/v1`). Giao diện ERP: sidebar + topbar,
mỗi nghiệp vụ một trang.

## Cấu hình

Tạo file `.env` (đã có sẵn `.env.example`):

```
VITE_API_BASE_URL=http://localhost:8060/api/v1
```

## Chạy

```bash
npm install
npm run dev        # http://localhost:5173 (tự nhảy port nếu bận)
npm run build      # tsc -b && vite build
npm run preview
```

> Backend phải đang chạy ở cổng cấu hình. Refresh token dùng cookie HttpOnly nên FE
> gửi `credentials: include` — backend cần cho phép CORS với credentials từ origin FE.

## Đăng nhập

Đăng nhập bằng tài khoản thật của backend. Tài khoản admin mặc định:
`admin@lims.local` / `ChangeMe@123` → lần đầu sẽ bị **ép đổi mật khẩu**.

## Vai trò (4 role)

| Role | Mô tả | Phạm vi |
|---|---|---|
| `admin` | Quản trị viên | Toàn quyền: users, phòng ban, mọi nghiệp vụ |
| `leader` | Ban lãnh đạo | Xem toàn hệ thống, duyệt, audit log |
| `accountant` | Kế toán | Tài chính hóa chất; **không truy cập mẫu** |
| `staff` | Nhân sự / KTV | Nghiệp vụ lab theo phòng; trưởng nhóm (`is_dept_lead`) được phân công / duyệt / chốt mẫu |

Menu và nút thao tác bật/tắt theo ma trận quyền trả về từ `GET /auth/me`. Backend luôn
re-validate mọi thao tác ghi.

## Trang chính

- **Login** + **đổi mật khẩu** (ép lần đầu, và trong Cài đặt).
- **Dashboard** — KPI mẫu theo trạng thái, mẫu quá hạn, hóa chất tồn thấp; scope theo role.
- **Mẫu** — phiếu yêu cầu (test-requests) → thêm mẫu → vòng đời mẫu: phân công (trưởng nhóm),
  chuyển giao + chain of custody, nhập kết quả (người được giao), duyệt (tách nhập–duyệt),
  chốt mẫu, nhập lý do trễ hạn, xuất PDF phiếu kết quả. Kế toán bị chặn (403).
- **Hóa chất** — danh mục, lô (giá/CoA), giao dịch nhập/xuất/điều chỉnh (quy đổi đơn vị,
  xác nhận cảnh báo lô fail/quá hạn), tồn theo lô, lịch sử, xuất Excel. Cột giá ẩn với staff.
- **Khách hàng** (admin + staff), **Nhân sự** & **Phòng ban** (admin), **Thông báo**,
  **Nhật ký hệ thống** (admin + leader), **Cài đặt**.

## Đặc điểm khớp backend

- **Auth**: access token (Bearer, lưu localStorage) + refresh cookie HttpOnly; auto-refresh
  khi 401 rồi retry. Logout thu hồi token.
- **Số thập phân là string** (qty_base, balance_after, unit_price...): không parseFloat để
  tính tiếp; chỉ format hiển thị qua `lib/format` (`formatDecimal`, `formatMoney`, `formatQty`).
- **Field-level price strip**: với staff, các key giá vắng mặt trong JSON → FE kiểm tra optional.
- **WARNING_NEEDS_CONFIRM (422)**: hiện dialog xác nhận → gửi lại `confirm_warning: true`.
- **x-correlation-id** gắn mỗi request; lỗi hệ thống hiển thị 8 ký tự đầu để trace.
- **Response format** `{success, data, meta?}` được unwrap; lỗi đọc `error.code` → toast tiếng Việt.

## Cấu trúc

```
src/
├── types/            # types khớp backend (M1 mẫu, M2 hóa chất, M7 nền tảng)
├── lib/
│   ├── api.ts        # fetch wrapper: token, correlationId, unwrap, auto-refresh, ApiError
│   ├── errors.ts     # map error.code → message tiếng Việt
│   ├── rbac.ts       # đọc permissions từ /auth/me, helper can*()
│   ├── format.ts     # format decimal/money/qty/ngày
│   └── useAsync.ts   # hook gọi API
├── api/              # auth, users, customers, samples, chemicals, notifications, audit
├── context/          # AuthContext (token+user+permissions), ToastContext
├── components/
│   ├── ui/           # Button, Card, DataTable, Modal, Field, Badge, StatusBadge…
│   └── layout/       # AppShell, Sidebar, Topbar, nav
└── pages/            # Login, ChangePassword, Dashboard, SampleRequests(+Detail),
                      # SampleDetail, Chemicals(+Detail), Customers, Users,
                      # Departments, Notifications, AuditLogs, Settings
```

## Tech stack

React 18 · TypeScript (strict) · Vite · TailwindCSS · React Router v6 · Recharts · Lucide.
