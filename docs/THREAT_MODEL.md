# THREAT MODEL — LIMS Backend

> Phương pháp: STRIDE + phân tích đường tấn công (attack path) dựa trên mã nguồn thực tế.
> Mã mối đe doạ: `T-xx`. Tham chiếu chéo: `S-xx` (SECURITY_AUDIT), `A-xx` (ARCHITECTURE_AUDIT).

---

## 1. Tài sản (Assets)

Xếp theo giá trị với tổ chức (Viện CNSH & Môi trường — phòng thử nghiệm theo ISO/IEC 17025 / VILAS).

| # | Tài sản | Nơi lưu | Mức nhạy cảm | Vì sao quan trọng |
|---|---|---|---|---|
| A1 | **Nhật ký kiểm toán** (`audit_logs`) | Postgres, append-only bằng trigger | 🔴 Rất cao | Bằng chứng tuân thủ §8.4. Mất/sửa được = mất công nhận VILAS |
| A2 | **Kết quả thử nghiệm + dữ liệu thô** (`sample_results`, attachment `sample_result`) | Postgres + MinIO | 🔴 Rất cao | Sản phẩm cốt lõi. Sửa được = gian lận kết quả |
| A3 | **Tài liệu chất lượng có kiểm soát** (`documents`, `document_versions` + file) | Postgres + MinIO | 🔴 Cao | §8.3 kiểm soát tài liệu. Có mức `restricted` |
| A4 | **Hồ sơ nhân sự + lương** (`hr_profiles`, `salary_history`, `competences` + file) | Postgres + MinIO | 🔴 Cao | PII + dữ liệu tài chính cá nhân |
| A5 | **Dữ liệu khách hàng + báo giá** (`customers`, `quotations`) | Postgres | 🟠 Cao | PII khách + giá thương mại. §4.2 bảo mật thông tin khách hàng |
| A6 | **Giấy chứng nhận hiệu chuẩn** (`calibration_records` + file) | Postgres (immutable trigger) + MinIO | 🟠 Cao | §6.4 thiết bị. Nền tảng giá trị pháp lý của kết quả |
| A7 | **Minh chứng VILAS** (`form_submissions` + file) | Postgres + MinIO | 🟠 Cao | Hồ sơ đánh giá công nhận |
| A8 | **Tài khoản & phiên** (`users`, `refresh_tokens`, `auth_tokens`) | Postgres + Redis | 🔴 Rất cao | Chiếm được = truy cập mọi tài sản khác |
| A9 | **Bí mật hạ tầng** (`JWT_SECRET`, DB/Redis/MinIO password, `CLOUDFLARE_TUNNEL_TOKEN`, `SMTP_PASSWORD`, VAPID key) | `.env.prod`, biến môi trường container | 🔴 Rất cao | `JWT_SECRET` = giả mạo token bất kỳ ai kể cả admin |
| A10 | **Tồn kho hoá chất** (`chemical_lots`, `chemical_transactions`) | Postgres | 🟡 Trung bình | Bao gồm hoá chất nguy hiểm; sai lệch tồn ảnh hưởng an toàn |
| A11 | **Tính sẵn sàng của dịch vụ** | Toàn hệ thống | 🟠 Cao | Ngừng = phòng lab không nhận/trả mẫu được |
| A12 | **Thẻ vào PTN** (`lab_access_cards`) | Postgres | 🟡 Trung bình | Kiểm soát vào phòng thí nghiệm vật lý |

---

## 2. Tác nhân (Actors)

| # | Tác nhân | Vị trí | Năng lực |
|---|---|---|---|
| P1 | **Người dùng ẩn danh (Internet)** | Ngoài | Gọi 14 endpoint công khai: login, register, verify-email, forgot/reset-password, registration-config, health |
| P2 | **Người tự đăng ký chưa duyệt** (`status=pending`) | Ngoài | Đã xác thực email nhưng **không đăng nhập được** (`auth_service.py:163-175`) |
| P3 | **Nhân viên `staff`** | Trong | Vai trò thấp nhất đang hoạt động. Truy cập mẫu/kết quả phòng mình, hồ sơ của chính mình |
| P4 | **`reception`** (Phòng nhận mẫu) | Trong | Nhận mẫu, báo giá, khách hàng |
| P5 | **`lab_manager`, `qms`** | Trong | Quản lý phòng lab / QLCL — duyệt biểu mẫu VILAS |
| P6 | **`office`** (Văn phòng) | Trong | HR, lương. **Bị cấm** dữ liệu mẫu/kết quả và ghi tài liệu |
| P7 | **`leader`** (Ban lãnh đạo) | Trong | Đọc toàn tổ chức kể cả lương; **không** đọc PII; đọc audit log |
| P8 | **`admin`** | Trong | Toàn quyền: tạo/xoá user, gán vai trò, đặt lại mật khẩu, chạy cron thủ công |
| P9 | **Kẻ tấn công bên ngoài** | Ngoài | Không có tài khoản. Bề mặt = 14 endpoint công khai + Cloudflare edge |
| P10 | **Kẻ tấn công có tài khoản hợp lệ** | Trong | Nhân viên bất mãn, hoặc tài khoản `staff` bị chiếm (phishing). **Đây là tác nhân nguy hiểm nhất với hệ thống này** |
| P11 | **Người vận hành hạ tầng** | Trong | Truy cập host, `docker exec`, `.env.prod`, volume |
| P12 | **Nhà cung cấp dịch vụ** (Cloudflare, Google SMTP, push service trình duyệt) | Ngoài | Thấy lưu lượng đã giải mã ở biên CF |

---

## 3. Ranh giới tin cậy

```
┌─ Ranh giới 1: Internet ↔ Cloudflare ───────────────────────────┐
│  TLS, WAF, DDoS. LIMS không kiểm soát. Tin ở mức "CF thấy       │
│  toàn bộ nội dung đã giải mã"                                   │
└──────────────────────────┬──────────────────────────────────────┘
┌─ Ranh giới 2: cloudflared ↔ lims-web (nginx) ─────────────────┐
│  HTTP thuần trong docker network. nginx quyết định IP thật     │
│  từ CF-Connecting-IP  ←── T-06                                 │
└──────────────────────────┬──────────────────────────────────────┘
┌─ Ranh giới 3: nginx ↔ lims-api ────────────────────────────────┐
│  uvicorn --forwarded-allow-ips '*' → TIN TUYỆT ĐỐI header       │
│  X-Forwarded-For. Chỉ an toàn vì lims-api không publish cổng    │
└──────────────────────────┬──────────────────────────────────────┘
┌─ Ranh giới 4: chưa xác thực ↔ đã xác thực ────────────────────┐
│  get_current_user: JWT + jti denylist + status + iat check ✅   │
│  KHÔNG tìm thấy đường vượt qua ranh giới này                    │
└──────────────────────────┬──────────────────────────────────────┘
┌─ Ranh giới 5: giữa các vai trò / phòng ban ───────────────────┐
│  ⚠️ RANH GIỚI YẾU NHẤT. 3 cơ chế song song, và đường           │
│  /attachments/{id} + /quotations đi vòng qua toàn bộ  ←── T-01 │
└──────────────────────────┬──────────────────────────────────────┘
┌─ Ranh giới 6: ứng dụng ↔ dữ liệu ──────────────────────────────┐
│  App kết nối bằng user SỞ HỮU schema → DROP được trigger       │
│  append-only bảo vệ audit_logs  ←── T-08                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Phân tích mối đe doạ (STRIDE)

### T-01 · Elevation of Privilege — Vượt phân quyền theo chiều ngang & dọc qua endpoint generic

| | |
|---|---|
| **STRIDE** | Elevation of Privilege / Information Disclosure |
| **Tác nhân** | P3 `staff`, P4 `reception`, P5 `qms`, P6 `office`, P10 |
| **Tài sản** | A2, A3, A4, A6, A7 |
| **Liên quan** | S-01, S-02, S-03 · **Khả năng: CAO · Ảnh hưởng: CAO** |

**Đường tấn công:**

```
[1] Đăng nhập bằng tài khoản staff hợp lệ (hoặc chiếm qua phishing)
     │
     ├─(1a)─→ GET /api/v1/quotations?limit=100
     │         → Toàn bộ báo giá: tên/địa chỉ/email/SĐT khách + đơn giá + tổng tiền
     │         → GET /quotations/{id}/export.xlsx  → file Excel đầy đủ
     │         KHÔNG cần biết id trước. KHÔNG có rate limit.          [A5 bị lộ]
     │
     └─(1b)─→ Thu thập attachment_id từ mọi listing mình có quyền:
               GET /documents/{id}/versions      → _file_dict trả attachment_id
               GET /forms/submissions/{id}/files → attachment id
               GET /samples/{id}/attachments     → id
               │
               ▼
          Lưu lại danh sách UUID
               │
          [thời gian trôi: đổi phòng ban / bị hạ quyền / tài liệu nâng lên 'restricted']
               │
               ▼
          GET /api/v1/attachments/{uuid}
               → _check_owner_read_permission chỉ hỏi: "role có phải 'office' và
                 owner_type có thuộc {test_request, sample, sample_result} không?"
               → Mọi luật khác (phòng ban, restricted, draft, competence) BỊ BỎ QUA
               → Trả presigned URL 15 phút                          [A2/A3/A4/A6/A7 bị lộ]
               │
               └─→ POST /api/v1/attachments {owner_type, owner_id, file}
                    → Chèn tệp vào bản tài liệu ĐÃ PHÊ DUYỆT / minh chứng ĐÃ DUYỆT
                    → Không kiểm quyền, không kiểm owner tồn tại, không kiểm trạng thái
                                                                     [A3/A7 bị PHÁ TOÀN VẸN]
```

**Vì sao đường này tồn tại:** mỗi module tự xây luật đọc/ghi riêng và **đi vòng** quanh
endpoint generic thay vì vá nó. `form_file_service.py:7-10` ghi rõ nhận thức về nguy cơ:
*"endpoint đó chỉ yêu cầu đăng nhập… nên bất kỳ ai biết id biểu mẫu cũng ghi đè được kho VILAS"*.

**Giảm nhẹ hiện có:** `attachment_id` là UUIDv4 (không duyệt được) — nhưng đây là che giấu,
không phải kiểm soát. `/quotations` thì **không có cả che giấu**.

**Chặn:** bảng định tuyến quyền theo `owner_type`, **deny-by-default**; thêm `require_roles`
cho `/quotations`.

---

### T-02 · Denial of Service — Redis chết làm sập toàn bộ API

| | |
|---|---|
| **STRIDE** | Denial of Service |
| **Tác nhân** | P9 (gián tiếp), hoặc sự cố hạ tầng |
| **Tài sản** | A11 |
| **Liên quan** | S-05, A-04 · **Khả năng: TRUNG BÌNH · Ảnh hưởng: CAO** |

**Đường:**
```
Redis OOM (maxmemory 384mb, policy noeviction) hoặc container chết hoặc mạng chập
   │
   ▼
get_current_user → is_jti_denied() → redis.exists() ném ConnectionError
   │  (không có try/except — security.py:95)
   ▼
unhandled_exception_handler → HTTP 500
   │
   ▼
100% request đã xác thực trả 500. Login cũng 500 (_check_lockout).
Chỉ /health còn sống.
```

**Khuếch đại:** với `socket_timeout=2s`, Redis **treo** (không chết hẳn) làm mỗi request chờ
2 giây trước khi 500 → 160 worker-slot bị chiếm → sập dây chuyền nhanh hơn.

**Nghịch lý thiết kế:** mọi thành phần khác dùng Redis đều fail-open **có comment giải
thích**; riêng auth fail-closed **không có comment** → đây là thiếu sót chứ không phải
quyết định.

**Chặn:** bắt exception, quyết định có ý thức (503 có `Retry-After`, hoặc fail-open kèm log
SECURITY + TTL access token ngắn). Thêm cảnh báo Redis memory > 80%.

---

### T-03 · Information Disclosure — Rò rỉ bí mật hạ tầng qua Git

| | |
|---|---|
| **STRIDE** | Information Disclosure → Elevation of Privilege → Toàn bộ |
| **Tác nhân** | P11 (vô ý), P9 (khai thác) |
| **Tài sản** | A9 → tất cả |
| **Liên quan** | S-04 · **Khả năng: TRUNG BÌNH · Ảnh hưởng: THẢM HOẠ** |

**Đường:**
```
scripts/init-env-prod.sh chạy lại → sinh .env.prod.bak.<ngày>
   │
   ▼
.gitignore chỉ có dòng ".env.prod" (khớp CHÍNH XÁC)
   → git check-ignore xác nhận: .env.prod.bak.20260729 KHÔNG bị ignore
   │
   ▼
git add -A  /  git add .   (thao tác thường ngày)
   │
   ▼
git push → repo CÔNG KHAI
   │
   ├─→ JWT_SECRET lộ  → ký token với role=admin cho bất kỳ user_id nào
   │                     → toàn quyền hệ thống, không cần mật khẩu
   ├─→ CLOUDFLARE_TUNNEL_TOKEN lộ → dựng tunnel giả trên tên miền
   ├─→ POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD, REDIS_PASSWORD lộ
   └─→ SMTP_PASSWORD lộ → gửi mail mạo danh Viện
   │
   ▼
gitleaks trong CI phát hiện — SAU KHI đã push và đã được lập chỉ mục
```

`.gitleaksignore` của chính repo này ghi lại một sự cố y hệt đã xảy ra với khoá VAPID:
*"repo đã public, các commit này đã được clone và lập chỉ mục… `git filter-repo` chỉ làm
lịch sử của ta sạch chứ không thu hồi được thứ đã phát tán."*

**Chặn:** `.gitignore` dùng `.env.*` + `!*.example`; pre-commit hook gitleaks **cục bộ**
(chặn trước khi commit, không phải phát hiện sau khi push); chuyển sang secret manager
(Docker secrets / SOPS / Vault) thay vì file phẳng.

---

### T-04 · Tampering / Repudiation — Mất dữ liệu vĩnh viễn

| | |
|---|---|
| **STRIDE** | Denial of Service / Repudiation |
| **Tác nhân** | Sự cố phần cứng, ransomware, thao tác nhầm (P11) |
| **Tài sản** | A1–A7, A10, A12 — **tất cả** |
| **Liên quan** | D-11, A-09 · **Khả năng: THẤP–TRUNG BÌNH · Ảnh hưởng: THẢM HOẠ** |

**Đường:**
```
Toàn bộ hệ thống trên MỘT host, MỘT Docker volume mỗi service
   │  lims_pgdata (Postgres) · lims_miniodata (MinIO) · lims_redisdata
   ▼
Hỏng ổ / ransomware / `docker compose down -v` gõ nhầm
   │
   ▼
docker-compose.prod.yml: không có service backup
scripts/: không có script backup
Không có cron/systemd timer
Không có bằng chứng đã restore thử
   │
   ▼
MẤT: toàn bộ kết quả thử nghiệm, toàn bộ nhật ký kiểm toán ISO 17025,
     toàn bộ tài liệu chất lượng, toàn bộ hồ sơ nhân sự
   │
   ▼
Không tái lập được → mất công nhận VILAS → phòng thử nghiệm ngừng hoạt động
```

`docs/DISASTER_RECOVERY.md` mô tả đúng quy trình **và tự nêu nguyên tắc "backup không kiểm
chứng = không có backup"**. Script thực thi **đã tồn tại và viết tốt** (`ops/backup/lims-backup.sh`
+ `ops/cron/lims-backup.cron`, xem D-11) — nhưng **chưa được cài trên host đang chạy**:
`/etc/cron.d/lims-backup`, `/usr/local/bin/lims-backup`, `/var/backups/lims` đều không tồn
tại, `crontab -l` rỗng. Nghĩa là hiện không có bản backup nào.

RPO thực tế: **∞**. RTO thực tế: **∞**.

**Chặn:** ưu tiên P0 — xem REMEDIATION_PLAN mục P0-5.

---

### T-05 · Spoofing — Chiếm tài khoản qua credential stuffing phân tán

| | |
|---|---|
| **STRIDE** | Spoofing |
| **Tác nhân** | P9 |
| **Tài sản** | A8 → tất cả |
| **Liên quan** | S-08, S-12 · **Khả năng: TRUNG BÌNH · Ảnh hưởng: CAO** |

**Đường:**
```
[1] Thu thập email nhân viên (website Viện, LinkedIn, giấy tờ công khai)
     Tên miền đăng ký giới hạn: hcmuaf.edu.vn / st.hcmuaf.edu.vn
     → định dạng email dễ đoán
     │
[2] Thử endpoint /auth/register để xác nhận email tồn tại?
     → ❌ CHẶN: luôn trả 202 + thông điệp chung (account_service.py:141-146)
     → ❌ CHẶN: /auth/login cùng thông điệp + cân bằng thời gian bằng hash mồi
     │
[3] Credential stuffing từ nhiều IP:
     - Khoá lockout = login:fail:{email}:{ip}  ← CÓ IP trong khoá
     - check_rate("login_identity", "{email}|{ip}", 10/300s)  ← CÓ IP
     - rate_limit IP thuần: 300/60s (cố ý nới vì cả viện dùng 1 IP NAT)
     → 100 IP × 5 lần = 500 lần thử/tài khoản mà KHÔNG chạm ngưỡng nào
     │
[4] Chính sách mật khẩu: ≥8 ký tự, ≥1 chữ + ≥1 số, không kiểm danh sách lộ
     → "Password1", "lims2026", "12345678a" đều hợp lệ
     │
     ▼
[5] Chiếm được tài khoản staff → T-01 → toàn bộ tài sản
```

**Đánh đổi có chủ ý:** gắn IP vào khoá để **kẻ tấn công không khoá được tài khoản nạn nhân**
(DoS nhắm mục tiêu) — ghi ở `redis_client.py:32-33`. Đánh đổi đúng, nhưng chỉ có một vế.

**Chặn:** bộ đếm **thứ hai** theo email toàn cục, ngưỡng cao (30/giờ), hành vi mềm
(CAPTCHA / delay tăng dần / cảnh báo admin + mail cho chủ tài khoản) thay vì khoá cứng.
Nâng chính sách mật khẩu lên 12 ký tự + chặn danh sách phổ biến. Cân nhắc MFA cho `admin`.

---

### T-06 · Repudiation / Spoofing — Giả mạo IP khi chạy sai profile compose

| | |
|---|---|
| **STRIDE** | Repudiation + bypass kiểm soát |
| **Tác nhân** | P11 (vô ý mở cửa), rồi P10/P9 (khai thác) |
| **Tài sản** | A1 (giá trị truy vết), A11 |
| **Liên quan** | S-09 · **Khả năng: THẤP · Ảnh hưởng: TRUNG BÌNH** |

> **ĐÍNH CHÍNH 2026-08-07:** bản đầu đặt T-06 ở nhánh "CAO nếu không có overlay CF". Đã xác
> minh triển khai thực tế **có** overlay: `lims-web` không publish cổng nào, mạng
> `lims_default` chỉ có 6 container LIMS + `cloudflared`. Mối đe doạ này **không đứng được
> ở trạng thái hiện tại** — nó chỉ mở ra khi ai đó chạy sai lệnh compose.

**Điều kiện tiên quyết (hiện KHÔNG thoả):** nginx phải tiếp cận được từ ngoài mạng docker.
Với Cloudflare Tunnel, đường vào duy nhất là `cloudflared` (kết nối hướng ra, không lắng
nghe cổng), và biên Cloudflare **ghi đè** `CF-Connecting-IP` nên client không giả mạo được.

**Đường tấn công — bắt đầu bằng một sai sót vận hành, không phải bằng kẻ tấn công:**

```
[0] Sự cố production → kỹ sư mở ops/RUNBOOK.md §6 Rollback (dòng 149):
       docker compose -f docker-compose.prod.yml up -d --build
       │  ← THIẾU -f docker-compose.cloudflare.yml
       │  grep -c "cloudflare.yml" ops/RUNBOOK.md  →  0   (15 lệnh đều thiếu)
       ▼
    lims-web dựng lại VỚI ports "3060:80"  ·  cloudflared KHÔNG được tạo
       │
       ├─→ Hệ quả tức thì: tunnel mất → hệ thống offline với người dùng thật
       └─→ Hệ quả âm thầm: cổng 3060 mở trên host
              │
[1] ─────────┘
    Ai trong LAN gọi http://<host>:3060/api/v1/auth/login
       với header CF-Connecting-IP: 203.0.113.<ngẫu nhiên mỗi request>
       │
       ▼
    nginx.conf:20-21  if ($http_cf_connecting_ip) { set $real_client $http_cf_connecting_ip; }
       → không kiểm $remote_addr là hop tin cậy hay không
       → X-Real-IP / X-Forwarded-For = giá trị tự đặt
       │
       ├─→ Né mọi rate limit theo IP (xoay giá trị mỗi request)
       ├─→ Né lockout đăng nhập (khoá gồm IP) → khuếch đại T-05
       └─→ audit_logs.ip và access_stats.ip ghi IP GIẢ
            → Nhật ký kiểm toán ISO 17025 mất giá trị truy vết
```

Trớ trêu: cấu hình này **cố ý** không dùng `$proxy_add_x_forwarded_for` để chống giả mạo
XFF (comment giải thích rất rõ ở `nginx.conf:14-19`) — nhưng để ngỏ một cửa khác ngay dòng
dưới. Với tunnel thì cửa đó không tới được; vấn đề là nó **phụ thuộc vào topology chứ không
tự bảo vệ**.

**Chặn — theo thứ tự hiệu quả:**
1. **Sửa `ops/RUNBOOK.md`** dùng alias đủ 2 file compose (alias đã có sẵn ở
   `DEPLOY_LINUX.md:360`). Đây là biện pháp có tác dụng thật.
2. **Gỡ `ports: "3060:80"` khỏi `docker-compose.prod.yml`** → chạy thiếu file không còn
   biến thành mở cổng.
3. ❌ **KHÔNG dùng `set_real_ip_from` với dải IP công khai của Cloudflare** — với tunnel,
   `$remote_addr` là IP container `cloudflared` (172.22.0.3), không bao giờ khớp dải đó →
   `real_ip` không kích hoạt → `X-Real-IP` rơi về IP container, tái tạo đúng lỗi mà
   `app/core/request_meta.py` được viết ra để sửa.

---

### T-07 · Information Disclosure — SSRF mù vào mạng nội bộ

| | |
|---|---|
| **STRIDE** | Information Disclosure / Tampering |
| **Tác nhân** | P10 |
| **Tài sản** | dịch vụ nội bộ |
| **Liên quan** | S-07, A-10 · **Khả năng: THẤP · Ảnh hưởng: TRUNG BÌNH** |

```
POST /api/v1/push/subscribe
  {"endpoint": "http://minio:9000/...", "keys": {"p256dh": "<khoá EC hợp lệ>", "auth": "..."}}
   │  → schemas/push.py:11 chỉ kiểm min_length/max_length
   ▼
Lưu vào push_subscriptions
   ▼
Mỗi notification → push_service._send_push_sync → webpush(endpoint=...)
   → POST từ trong docker network tới URL kẻ tấn công chọn
   → Đích: minio:9000, lims-api:8060, lims-web:80, 169.254.169.254, LAN
```
Response không trả về (SSRF **mù**), body đã mã hoá VAPID, timeout 5s → giá trị khai thác
hạn chế: dò port, kích hoạt endpoint nội bộ nhận POST.

**Chặn:** allowlist host push service; bắt buộc `https://`; từ chối IP literal + dải private.

---

### T-08 · Tampering — Vô hiệu hoá tính bất biến của nhật ký kiểm toán

| | |
|---|---|
| **STRIDE** | Tampering / Repudiation |
| **Tác nhân** | P11, hoặc P10 sau khi có RCE/SQLi trong tương lai |
| **Tài sản** | A1 |
| **Liên quan** | S-18 · **Khả năng: THẤP · Ảnh hưởng: CAO** |

```
DATABASE_URL dùng user `lims` — cũng là POSTGRES_USER và OWNER của mọi bảng
   │
   ▼
User này có quyền DDL đầy đủ:
   DROP TRIGGER audit_logs_no_update ON audit_logs;
   DROP TRIGGER audit_logs_no_delete ON audit_logs;
   DELETE FROM audit_logs WHERE user_id = '<kẻ tấn công>';
   CREATE TRIGGER ... (dựng lại như cũ)
   │
   ▼
Bằng chứng append-only bị vô hiệu. Không còn vết của chính hành động xoá vết.
```

Trigger append-only là **điểm mạnh** của hệ thống — nhưng nó bảo vệ chống *ứng dụng ghi sai*,
không chống *kẻ có credential DB*. Hiện ứng dụng và migration dùng **cùng một credential**.

**Chặn:** tách vai trò `lims_migrate` (owner, chỉ service `migrate` dùng) và `lims_app`
(chỉ DML trên bảng nghiệp vụ, `REVOKE TRIGGER`, không DDL). Cân nhắc gửi bản sao audit log
sang kho append-only ngoài (WORM/S3 Object Lock).

---

### T-09 · Denial of Service — Cạn tài nguyên bằng endpoint tốn CPU/RAM

| | |
|---|---|
| **STRIDE** | Denial of Service |
| **Tác nhân** | P10 (hoặc P3 vô ý) |
| **Tài sản** | A11 |
| **Liên quan** | API-07, D-04, D-09 · **Khả năng: TRUNG BÌNH · Ảnh hưởng: TRUNG BÌNH** |

Ba đường độc lập, đều cần tài khoản hợp lệ:

```
(a) GET /samples/{id}/result-report.pdf     — sinh PDF ReportLab
    KHÔNG rate limit · KHÔNG export_slot()
    → gọi vòng lặp → chiếm CPU của cả 4 worker (cpus: 2.0)

(b) GET /quotations/{id}/export.xlsx        — sinh Excel openpyxl
    KHÔNG rate limit · KHÔNG export_slot() · KHÔNG kiểm quyền (T-01)

(c) GET /reports/samples?from=<đổi mỗi lần>  — unified_report_service.py:81
    Cache key chứa tham số client → luôn miss
    → SELECT toàn bộ cột thời gian về RAM, đếm bằng Python
    KHÔNG rate limit · KHÔNG statement_timeout
```

`export_slot()` (semaphore 2/process) **tồn tại** nhưng hai đường xuất nặng nhất không dùng.
Không có `statement_timeout` → truy vấn chậm giữ connection vô thời hạn; pool 160 cạn →
`db_pool_timeout=5s` bắt đầu từ chối request khác.

**Chặn:** áp `export_slot()` + rate limit cho (a) và (b); chuyển (c) sang `GROUP BY` trong
SQL; đặt `statement_timeout=30s` ở Postgres.

---

### T-10 · Tampering — Chèn phần mềm độc hại qua tệp đính kèm

| | |
|---|---|
| **STRIDE** | Tampering |
| **Tác nhân** | P10 |
| **Tài sản** | máy trạm người dùng, A2/A3/A7 (toàn vẹn) |
| **Liên quan** | S-06 · **Khả năng: TRUNG BÌNH · Ảnh hưởng: TRUNG BÌNH** |

```
Upload payload.exe với header Content-Type: application/pdf
   │  attachment_common.check_mime chỉ đọc Content-Type do client khai
   │  KHÔNG kiểm magic bytes · KHÔNG kiểm phần mở rộng · KHÔNG có antivirus
   ▼
Lưu MinIO với ContentType: application/pdf
   ▼
Đồng nghiệp tải "Bao_cao_ket_qua.pdf" → thực tế là file thực thi
   │
   ├─ Stored-XSS?  ❌ CHẶN: presigned URL luôn kèm Content-Disposition: attachment
   │                trừ mime trong allowlist inline (attachment_service.py:58-60)
   └─ Phát tán malware nội bộ ✅ KHÔNG CHẶN
   ▼
Kết hợp S-02: chèn tệp độc vào bản tài liệu chất lượng ĐÃ PHÊ DUYỆT
   → người dùng tin tưởng vì nó nằm trong hệ thống có kiểm soát
```

**Chặn:** kiểm magic bytes đối chiếu Content-Type + phần mở rộng; thêm
`X-Content-Type-Options: nosniff` cho `location /lims-attachments/`; cân nhắc ClamAV cho
tệp từ nguồn ngoài.

---

### T-11 · Denial of Service — Thông báo trùng lặp khi Redis khởi động chậm

| | |
|---|---|
| **STRIDE** | Denial of Service (nhẹ) / mất tin cậy dữ liệu |
| **Liên quan** | A-07 · **Khả năng: THẤP · Ảnh hưởng: THẤP** |

```
Redis chưa sẵn sàng lúc lims-api khởi động (dù compose có depends_on: service_healthy)
   │  ví dụ: Redis restart giữa chừng, hoặc mạng docker chập
   ▼
_acquire_leader_lock() bắt exception → return True  (scheduler.py:66-73, FAIL-OPEN)
   ▼
CẢ 4 uvicorn worker process đều đăng ký 9 cron job
   ▼
Lớp phòng thủ cuối = per-job Redis lock — CŨNG cần Redis
   ▼
Nếu Redis lên lại sau: per-job lock dedupe được ✅
Nếu Redis vẫn chập chờn: 4× thông báo/mail trùng cho cùng một sự kiện nhắc hạn
```

**Chặn:** đặt `SCHEDULER_ENABLED=true` cho đúng một replica và **fail-closed** khi Redis lỗi
(hoặc dùng `--workers 1` cho một container riêng chuyên chạy cron).

---

## 5. Ma trận rủi ro

```
Ảnh hưởng
   ▲
THẢM │              │ T-03 (secret)  │
HOẠ  │              │ T-04 (mất dữ liệu)
─────┼──────────────┼────────────────┼──────────────
CAO  │ T-08 (audit) │ T-02 (Redis)   │ T-01 (BOLA)
     │              │ T-05 (stuffing)│
─────┼──────────────┼────────────────┼──────────────
TB   │ T-06 (IP spoof)              │
     │ T-07 (SSRF)  │ T-09 (DoS)     │
     │              │ T-10 (malware) │
─────┼──────────────┼────────────────┼──────────────
THẤP │              │ T-11 (cron)    │
     └──────────────┴────────────────┴──────────────▶
        THẤP        TRUNG BÌNH        CAO      Khả năng
```
T-06 đã chuyển từ ô (CAO khả năng, CAO ảnh hưởng) xuống (THẤP, TB) sau khi xác minh
triển khai thực tế dùng Cloudflare Tunnel không publish cổng nào.

---

## 6. Thứ tự xử lý theo mô hình đe doạ

| Thứ tự | Mối đe doạ | Lý do đứng ở vị trí này |
|---|---|---|
| 1 | **T-04** (mất dữ liệu) | Ảnh hưởng thảm hoạ, không hồi phục được, chi phí khắc phục thấp nhất trong nhóm |
| 2 | **T-03** (secret vào git) | Ảnh hưởng thảm hoạ, khắc phục = 4 dòng `.gitignore` + 1 hook |
| 3 | **T-01** (BOLA) | Khả năng cao nhất, chạm 5/12 tài sản, đã có tài khoản là khai thác được |
| 4 | **T-05** (chiếm tài khoản) | Là bước [1] của T-01 |
| 5 | **T-02** (Redis SPOF) | Ảnh hưởng cao, khắc phục nhỏ (một `try/except` có chủ đích) |
| 6 | **T-09** (DoS tài nguyên) | Cần tài khoản; thiệt hại tạm thời |
| 7 | **T-10** (malware) | Cần tài khoản; thiệt hại phụ thuộc hành vi người nhận |
| 8 | **T-08** (phá audit) | Khả năng thấp (cần credential DB), nhưng bắt buộc với ISO 17025 dài hạn |
| 9 | **T-06** (giả mạo IP) | **Không đứng được với triển khai hiện tại.** Việc cần làm là sửa `ops/RUNBOOK.md` — mà lệnh rollback thiếu overlay còn nguy hiểm hơn ở chỗ nó làm **mất tunnel** (hệ thống offline), chứ không phải ở chỗ mở đường giả mạo IP |
| 10 | **T-07** (SSRF) | Mù, giá trị khai thác thấp |
| 11 | **T-11** (cron trùng) | Ảnh hưởng thấp |
