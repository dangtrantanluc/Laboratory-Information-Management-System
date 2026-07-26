# Tự phục vụ tài khoản (m30) — đăng ký, quên mật khẩu, phiên, ảnh đại diện

Migration: `1718870400029_m30_self_service_auth.py`

---

## 1. Quyết định thiết kế then chốt

### 1.1 Đăng ký KHÔNG tự cấp quyền

Hệ thống theo ISO/IEC 17025 — tài khoản là quyền truy cập hồ sơ thử nghiệm. Vì vậy
luồng đăng ký tách làm **hai việc khác nhau**:

| Bước | Chứng minh điều gì | Kết quả |
|---|---|---|
| Xác thực email | "Đúng là chủ hộp thư này" | `users.email_verified_at` được đặt |
| Quản trị viên duyệt | "Được phép vào hệ thống, với vai trò X" | `users.status` = `pending` → `active` |

Người đăng ký **không khai được vai trò hay phòng ban**. `RegisterRequest` chỉ nhận
`email`, `full_name`, `password` (`extra="forbid"`). Vai trò do Quản trị viên chọn ở
bước duyệt. Đây là điểm khiến việc mở form đăng ký công khai vẫn an toàn.

```
Đăng ký ──► status='pending', email_verified_at=NULL
   │            └─ đăng nhập: chặn "EMAIL_NOT_VERIFIED"
   ▼
Bấm link trong mail ──► email_verified_at=now()
   │            └─ đăng nhập: chặn "ACCOUNT_PENDING_APPROVAL"
   ▼
Admin duyệt (gán vai trò + phòng ban) ──► status='active'
                └─ đăng nhập được, mail thông báo đã gửi
```

### 1.2 Không rò rỉ danh sách người dùng

`/auth/register` và `/auth/forgot-password` **luôn trả cùng một thông điệp**, bất kể
email có tồn tại hay không. Nếu phân biệt, kẻ tấn công có thể dò xem ai có tài khoản
trong hệ thống. Cùng tinh thần với `_DUMMY_PASSWORD_HASH` mà `auth_service` dùng để
chống dò qua thời gian phản hồi.

Thông điệp trạng thái (`ACCOUNT_PENDING_APPROVAL`, `EMAIL_NOT_VERIFIED`) chỉ hiện
**sau khi mật khẩu đã đúng** — nên không dùng để dò được.

### 1.3 Token trong mail chỉ lưu dạng băm

Bảng `auth_tokens` lưu `sha256(token)` chứ không lưu token thô — cùng kỷ luật với
`refresh_tokens`. Rò rỉ nội dung bảng DB không cho phép kẻ tấn công đặt lại mật khẩu
của bất kỳ ai. Token dùng-một-lần: phát hành token mới sẽ vô hiệu token cũ cùng mục
đích, và token bị đánh dấu `used_at` ngay khi tiêu thụ.

### 1.4 Đặt lại mật khẩu thu hồi mọi phiên

Nếu người dùng đặt lại mật khẩu vì nghi bị chiếm tài khoản mà phiên của kẻ tấn công
vẫn sống, việc đổi mật khẩu là vô nghĩa. `reset_password` revoke toàn bộ
`refresh_tokens` của user và gửi mail cảnh báo.

### 1.5 Ảnh đại diện không đi qua bảng `attachments`

`attachments` có CHECK whitelist `owner_type` và một tầng phân quyền theo module. Ảnh
đại diện là dữ liệu 1-1 của user → gắn thẳng `users.avatar_key`. Ảnh nằm ở MinIO, DB
chỉ giữ object key, API trả presigned URL TTL 15 phút (bucket không cần công khai).

**Kiểm định dạng bằng magic bytes, không tin `Content-Type` của client.** Đổi đuôi
file `.svg` thành `.png` sẽ bị chặn — SVG là XML có thể nhúng script, sẽ thành
stored-XSS khi trình duyệt mở trực tiếp từ presigned URL.

---

## 2. Lược đồ dữ liệu

### `users` — 3 thay đổi

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `status` | CHECK mở rộng | thêm giá trị `'pending'` |
| `email_verified_at` | `TIMESTAMPTZ NULL` | mốc bấm link xác thực |
| `avatar_key` | `VARCHAR(512) NULL` | object key trong MinIO |

> Migration đặt `email_verified_at = created_at` cho mọi user `active` sẵn có — nếu
> không, người dùng cũ do Quản trị viên tạo sẽ bị luồng mới bắt xác thực lại vô lý.

### `auth_tokens` — bảng mới

| Cột | Ghi chú |
|---|---|
| `token_hash` | `VARCHAR(64)` — sha256 hex, UNIQUE |
| `purpose` | `'email_verify'` \| `'password_reset'` |
| `expires_at`, `used_at`, `ip`, `created_at` | |

---

## 3. API

### Công khai (không cần đăng nhập)

| Method | Đường dẫn | Rate limit | Ghi chú |
|---|---|---|---|
| GET | `/auth/registration-config` | — | Frontend hỏi trước khi hiện form |
| POST | `/auth/register` | 5 / 10 phút | Luôn trả 202 + thông điệp chung |
| POST | `/auth/verify-email` | 20 / 10 phút | |
| POST | `/auth/forgot-password` | 5 / 10 phút | Luôn trả 202 + thông điệp chung |
| POST | `/auth/reset-password` | 10 / 10 phút | Thu hồi mọi phiên |

### Cần đăng nhập

| Method | Đường dẫn | Ghi chú |
|---|---|---|
| GET | `/auth/me/sessions` | Đánh dấu `is_current` |
| DELETE | `/auth/me/sessions/{id}` | Chỉ phiên của chính mình |
| POST | `/auth/me/sessions/revoke-others` | Giữ phiên hiện tại |
| POST | `/auth/me/avatar` | multipart, ≤2MB, JPG/PNG/WEBP |
| DELETE | `/auth/me/avatar` | |

### Chỉ admin

| Method | Đường dẫn | Ghi chú |
|---|---|---|
| POST | `/users/{id}/approve` | Gán `role` + `department_id`, kích hoạt |
| POST | `/users/{id}/reject` | → `disabled`, gửi mail kèm lý do |
| GET | `/users?status=pending` | Hàng chờ duyệt |

---

## 4. Cấu hình

### 4.1 Gmail cá nhân (đang dùng)

```bash
APP_PUBLIC_URL=http://localhost:3060      # production: https://lims.<domain>

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your.email@gmail.com
SMTP_PASSWORD=<App Password 16 ký tự>     # KHÔNG phải mật khẩu Gmail
SMTP_STARTTLS=true
```

**Lấy App Password:**
1. Bật **Xác minh 2 bước** cho tài khoản Google
2. Vào <https://myaccount.google.com/apppasswords>
3. Tạo mật khẩu ứng dụng → dán 16 ký tự vào `SMTP_PASSWORD`

Mật khẩu Gmail thường **không dùng được** — Google chặn "ứng dụng kém an toàn" từ 2022.

### 4.2 Chế độ dev (chưa cấu hình SMTP)

Bỏ trống `SMTP_HOST` ⇒ không gửi thật, nội dung mail (kèm link) ghi ra log:

```bash
docker logs lims-api 2>&1 | grep -A6 "DEV.*SMTP"
```

Ở `ENVIRONMENT=production` mà thiếu SMTP thì ghi log mức **ERROR** để đội vận hành thấy.

### 4.3 Giới hạn tên miền đăng ký

```bash
SELF_REGISTRATION_ENABLED=true
SELF_REGISTRATION_ALLOWED_DOMAINS=hcmuaf.edu.vn,st.hcmuaf.edu.vn   # bỏ trống = mọi domain
```

---

## 5. Kết quả kiểm thử

Đã chạy **22 ca** trên API thật (cả trực tiếp cổng 8060 lẫn qua nginx cổng 3060):

| # | Ca | Kết quả |
|---|---|---|
| 1 | `registration-config` trả đúng cấu hình | ✔ |
| 2 | Đăng ký mới → tạo user `pending`, `role='staff'` tạm | ✔ |
| 3 | Đăng ký trùng email admin → **thông điệp giống hệt** | ✔ |
| 4 | Link xác thực xuất hiện trong log (chế độ dev) | ✔ |
| 5 | Đăng nhập khi chưa xác thực → `EMAIL_NOT_VERIFIED` | ✔ |
| 6 | Xác thực email → `awaiting_approval=true` | ✔ |
| 7 | Dùng lại token đã tiêu thụ → bị từ chối | ✔ |
| 8 | Đăng nhập sau xác thực, chưa duyệt → `ACCOUNT_PENDING_APPROVAL` | ✔ |
| 9 | Admin duyệt, gán vai trò + phòng ban | ✔ |
| 10 | Đăng nhập sau khi duyệt → thành công | ✔ |
| 11 | Duyệt lại tài khoản đã `active` → `NOT_PENDING` | ✔ |
| 12–13 | Quên mật khẩu: email tồn tại / không tồn tại → **giống hệt** | ✔ |
| 14 | Đặt lại mật khẩu bằng token | ✔ |
| 15 | Đăng nhập bằng mật khẩu cũ → thất bại | ✔ |
| 16 | Đăng nhập bằng mật khẩu mới → thành công | ✔ |
| 17 | Phiên cũ bị thu hồi sau khi reset | ✔ |
| 18 | Liệt kê 3 phiên, nhận diện đúng Chrome·Windows / Safari·iOS | ✔ |
| 19 | Thu hồi phiên khác → còn đúng 1 phiên `is_current` | ✔ |
| 20 | Upload avatar PNG → MinIO + `avatar_key` vào DB | ✔ |
| 21 | Upload `.png` giả (thực chất SVG) → **bị chặn** | ✔ |
| 22 | 4 route SPA mới trả HTTP 200 qua nginx | ✔ |

Ca biên bổ sung:

| Ca | Kết quả |
|---|---|
| Duyệt người chưa xác thực mail → `EMAIL_NOT_VERIFIED` | ✔ |
| Quên mật khẩu cho tài khoản `pending` → im lặng, **0 token** phát hành | ✔ |

---

## 6. Giao diện

| Trang / khối | Đường dẫn | Ghi chú |
|---|---|---|
| Đăng ký | `/register` | Nói rõ "cần Quản trị viên duyệt" ngay từ đầu |
| Quên mật khẩu | `/forgot-password` | Không bao giờ nói "email không tồn tại" |
| Đặt lại mật khẩu | `/reset-password?token=` | Cảnh báo sẽ đăng xuất mọi thiết bị |
| Xác thực email | `/verify-email?token=` | Chống StrictMode gọi 2 lần bằng `useRef` |
| Ảnh đại diện | Hồ sơ cá nhân | Xem trước ngay, ảnh hiện luôn trên Topbar |
| Thiết bị đăng nhập | Hồ sơ cá nhân | Thu hồi từng phiên / mọi thiết bị khác |
| Hàng chờ duyệt | Nhân sự | Tự ẩn khi không có ai chờ |

---

## 7. Việc còn lại

- [ ] **Rate limit hiện key theo IP proxy** (bug B2 ở `DEPLOY_CLOUDFLARE.md`). Với các
      endpoint mới, nghĩa là 5 lượt đăng ký/10 phút bị dùng chung cho **toàn bộ** người
      dùng thay vì từng IP. Cần bật `--proxy-headers` cho uvicorn trước khi lên production.
- [ ] Job dọn `auth_tokens` đã hết hạn (index `ix_auth_tokens_expires` đã sẵn sàng).
- [ ] Đổi email trong hồ sơ hiện vẫn ăn ngay, chưa bắt xác thực lại địa chỉ mới.
- [ ] Ảnh đại diện chưa nén/resize phía server — người dùng tải ảnh 2MB thì lưu nguyên 2MB.
