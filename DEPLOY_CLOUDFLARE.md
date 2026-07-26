# Deploy LIMS lên máy chủ khác qua Cloudflare Tunnel

Đi kèm: `docker-compose.cloudflare.yml` (overlay), `docker-compose.prod.yml`, `.env.prod.example`.

---

## 1. Vì sao chọn Cloudflare Tunnel

Nginx trong `lims-web` **đã reverse-proxy sẵn** hai đường quan trọng:

```
/api/               → lims-api:8060
/lims-attachments/  → minio:9000     (giữ nguyên Host để chữ ký presigned s3v4 khớp)
/                   → SPA fallback
```

Nghĩa là toàn bộ ứng dụng chạy trên **một origin duy nhất**. Chỉ cần trỏ tunnel vào `lims-web:80` là xong — không phải tách frontend/backend, không phải bật CORS chéo domain, không phải cấu hình TLS.

**So sánh nhanh:**

| Cách | Cần IP public | Cần mở port | Cần TLS thủ công | Phù hợp |
|---|:--:|:--:|:--:|---|
| **Cloudflare Tunnel** ✅ | không | không | không | Máy sau NAT (mạng nội bộ trường/viện) |
| DNS proxy (cam vàng) | **có** | 80/443 | không (CF cấp) | Máy có IP tĩnh public |
| Cloudflare Pages + Tunnel API | không | không | không | ❌ Không nên — phá cơ chế proxy MinIO same-origin ở trên |

Khuyến nghị: **Tunnel**. Máy chủ không lộ cổng nào ra Internet.

---

## 2. ⚠ Ba việc PHẢI xử lý trước khi deploy

### B1 — `cpus: 2.0` sẽ làm Docker từ chối khởi động trên máy 1 nhân

`docker-compose.prod.yml` đặt `cpus: 2.0` cho `lims-api`. Docker báo lỗi
`Range of CPUs is from 0.01 to 1.00` nếu host chỉ có 1 nhân.

Overlay đã tham số hoá. Thêm vào `.env.prod`:

```bash
# Máy 1 nhân:
LIMS_API_CPUS=0.8
# Máy ≥2 nhân: bỏ dòng này (mặc định 2.0)
```

Kiểm tra số nhân của máy đích: `nproc`

### B2 — 🔴 Rate limiter đang khoá TOÀN BỘ người dùng chung một rổ

Đây là lỗi có thật, **không phải do Cloudflare gây ra**, nhưng lên production nó sẽ thành sự cố.

`app/core/rate_limit.py:29` và `app/routers/auth.py:29` lấy IP bằng `request.client.host`. Uvicorn chạy **không có `--proxy-headers`**, nên giá trị này luôn là **IP container nginx** (172.x.x.x), không phải IP người dùng.

Hậu quả: `/auth/login` giới hạn **20 request/phút/IP**. Vì mọi người dùng đều mang cùng một IP (nginx), chỉ cần ~20 lượt đăng nhập trong 1 phút là **cả viện bị chặn 429**. Ghi log audit và thống kê truy cập cũng ghi sai IP.

**Sửa — 3 thay đổi:**

**(a)** `lims-backend/Dockerfile` — bật xử lý proxy header:

```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8060", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
```

> `--forwarded-allow-ips *` an toàn ở đây vì container `lims-api` **không** publish cổng ra host khi dùng overlay Cloudflare — chỉ nginx trong mạng compose gọi tới được.

**(b)** `lims-frontend/nginx.conf` — chuyển tiếp IP thật từ Cloudflare. Cloudflare đặt IP người dùng vào header `CF-Connecting-IP`; nginx đang ghi đè `X-Forwarded-For` bằng chuỗi cộng dồn. Thêm vào block `location /api/`:

```nginx
    # Cloudflare gửi IP thật ở CF-Connecting-IP. Ưu tiên nó; nếu không có
    # (gọi trực tiếp trong LAN) thì giữ nguyên chuỗi X-Forwarded-For.
    set $real_client $remote_addr;
    if ($http_cf_connecting_ip) { set $real_client $http_cf_connecting_ip; }
    proxy_set_header X-Forwarded-For $real_client;
    proxy_set_header X-Real-IP $real_client;
    # Cloudflare luôn nói chuyện với người dùng bằng HTTPS
    proxy_set_header X-Forwarded-Proto https;
```

> Dòng `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` hiện có phải **thay** bằng dòng trên, không để cả hai.

**(c)** Bật **"Add visitor IP headers"** trong Cloudflare dashboard
→ *Rules → Transform Rules → Managed Transforms* (mặc định đã bật).

**Kiểm chứng sau khi deploy:** đăng nhập sai mật khẩu 1 lần, xem bảng audit log — cột IP phải là IP thật của máy bạn, không phải `172.x.x.x`.

### B3 — `MINIO_PUBLIC_ENDPOINT` và `CORS_ORIGINS` phải đúng domain public

Backend tạo presigned URL bằng `minio_public_endpoint` (`app/services/storage_service.py:90`). Chữ ký s3v4 ký theo **header Host**. Nginx chuyển tiếp `Host` nguyên vẹn xuống MinIO, nên hai giá trị phải khớp:

```bash
MINIO_PUBLIC_ENDPOINT=https://lims.vien-sinh-hoc.edu.vn   # KHÔNG có dấu / cuối
CORS_ORIGINS=https://lims.vien-sinh-hoc.edu.vn
```

Sai giá trị này ⇒ **tải file đính kèm trả về `SignatureDoesNotMatch`**.

> Scheme (`http` vs `https`) không nằm trong chuỗi ký s3v4 nên không ảnh hưởng; chỉ host mới quan trọng.

---

## 3. Chuẩn bị máy đích

### Yêu cầu tối thiểu

| Tài nguyên | Tối thiểu | Khuyến nghị | Vì sao |
|---|---|---|---|
| CPU | 2 nhân | 4 nhân | 1 nhân chạy được nhưng build chậm (xem B1 + §4) |
| RAM | **6 GB** | 8 GB | Giới hạn đã khai báo: postgres 2g + minio 1g + api 1g + redis 512m ≈ 4.5g, chưa kể OS |
| Đĩa | 30 GB | 60 GB+ | Postgres + MinIO đính kèm tăng dần |
| OS | Ubuntu 22.04/24.04 | — | — |

```bash
# Kiểm tra trước khi bắt đầu
nproc && free -g && df -h /
```

### Cài Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER    # đăng xuất/đăng nhập lại
docker compose version           # cần >= 2.24 (overlay dùng cú pháp !reset)
```

---

## 4. Build ở đâu?

`lims-web` build Vite (`npm ci` + `tsc -b` + build) và `lims-api` cài Python deps. Trên máy 1–2 nhân việc này mất **10–25 phút** và ngốn RAM.

**Cách A — build ngay trên máy đích** (đơn giản, chấp nhận chờ):

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml \
               --env-file .env.prod up -d --build
```

**Cách B — build sẵn, đẩy qua registry** (khuyến nghị nếu máy đích yếu):

```bash
# Trên máy dev (mạnh hơn)
docker build -t ghcr.io/<user>/lims-api:1.0 ./lims-backend
docker build -t ghcr.io/<user>/lims-web:1.0 \
       --build-arg VITE_API_BASE_URL=/api/v1 ./lims-frontend
docker push ghcr.io/<user>/lims-api:1.0
docker push ghcr.io/<user>/lims-web:1.0
```

Rồi trên máy đích đổi `build:` thành `image:` trong overlay.

> **Lưu ý:** `VITE_API_BASE_URL` được Vite **nhúng cứng vào bundle lúc build**, không đổi được lúc chạy. Giá trị `/api/v1` (đường dẫn tương đối) là đúng — bundle chạy được trên bất kỳ domain nào. Đừng đổi thành URL tuyệt đối.

---

## 5. Tạo Cloudflare Tunnel

1. Vào **Cloudflare Zero Trust** → *Networks* → *Tunnels* → **Create a tunnel**
2. Chọn **Cloudflared** → đặt tên (vd `lims-vien-sinh-hoc`) → **Save**
3. Ở màn hình cài đặt, **copy token** (chuỗi dài bắt đầu bằng `eyJ...`) — bỏ qua phần lệnh cài đặt, ta chạy bằng Docker
4. Tab **Public Hostname** → **Add a public hostname**:

   | Trường | Giá trị |
   |---|---|
   | Subdomain | `lims` |
   | Domain | `vien-sinh-hoc.edu.vn` *(domain của bạn trên Cloudflare)* |
   | Path | *(để trống)* |
   | Type | `HTTP` |
   | URL | `lims-web:80` |

   > `HTTP` chứ không phải `HTTPS`: đoạn cloudflared → nginx nằm trong mạng nội bộ Docker. Mã hoá đầu-cuối do Cloudflare đảm nhiệm ở biên.

5. **Additional application settings → HTTP Settings**: bật **Disable Chunked Encoding** = OFF (mặc định), giữ nguyên phần còn lại.

---

## 6. Điền `.env.prod`

```bash
cd /opt/lims        # thư mục chứa repo trên máy đích
cp .env.prod.example .env.prod
chmod 600 .env.prod
```

Sinh secret:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET
openssl rand -base64 32                                          # các password khác
```

Các giá trị **bắt buộc đúng** cho Cloudflare (ngoài phần đã có trong `.env.prod.example`):

```bash
# --- Cloudflare Tunnel ---
CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiXXXXXXXX...        # token copy ở bước 5.3

# --- Phải là domain public, không phải localhost ---
MINIO_PUBLIC_ENDPOINT=https://lims.vien-sinh-hoc.edu.vn
CORS_ORIGINS=https://lims.vien-sinh-hoc.edu.vn

# --- Chỉ thêm nếu host có 1 nhân (xem B1) ---
LIMS_API_CPUS=0.8
```

VAPID keypair riêng cho production:

```bash
pip install py-vapid
python3 -c "from py_vapid import Vapid02; v=Vapid02(); v.generate_keys(); print(v.public_key, v.private_key)"
```

---

## 7. Khởi chạy

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml \
               --env-file .env.prod up -d --build
```

Theo dõi:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml logs -f migrate
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml logs -f cloudflared
```

Dấu hiệu tunnel thành công trong log `cloudflared`:

```
INF Registered tunnel connection connIndex=0 location=sin01
```

Xác nhận **không còn cổng nào lộ ra host**:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml ps
# cột PORTS phải TRỐNG với mọi service
ss -tlnp | grep -E '3060|8060|5432|6379|9000'   # không ra kết quả nào
```

---

## 8. Cấu hình Cloudflare sau khi chạy

### 8.1 Chặn cache cho API — **bắt buộc**

Mặc định Cloudflare không cache `application/json`, nhưng đừng phụ thuộc vào mặc định — một response `/api/v1/users` bị cache là sự cố rò rỉ dữ liệu giữa các tài khoản.

*Caching → Cache Rules → Create rule*

| | |
|---|---|
| Tên | `Bypass cache cho API` |
| Điều kiện | `URI Path` **starts with** `/api/` |
| Hành động | **Bypass cache** |

Thêm rule thứ hai tương tự cho `/lims-attachments/` (presigned URL có chữ ký theo thời gian, cache sẽ trả về URL hết hạn).

### 8.2 Giới hạn dung lượng upload

| Gói Cloudflare | Giới hạn body |
|---|---|
| Free | **100 MB** |
| Pro | 100 MB |
| Business | 200 MB |

App đang giới hạn 20 MB (`MAX_FILE_MB` ở frontend) và nginx `client_max_body_size 25m` → **không vướng**. Nhưng nếu sau này nâng giới hạn file, phải nhớ trần của Cloudflare.

### 8.3 Bảo vệ trang đăng nhập (khuyến nghị)

Vì B2 khiến rate limit hiện không tin cậy, nên bổ sung một lớp ở biên:
*Security → WAF → Rate limiting rules* — giới hạn `/api/v1/auth/login` ở **10 request / 10 phút / IP**. Cloudflare thấy IP thật nên chặn đúng người.

### 8.4 SSL/TLS

*SSL/TLS → Overview* → đặt **Full**. (Không cần *Full (strict)* vì chặng cloudflared→nginx là HTTP nội bộ Docker; Tunnel đã mã hoá chặng ra Internet.)

---

## 9. Kiểm thử sau deploy

| # | Kiểm tra | Kỳ vọng |
|---|---|---|
| 1 | Mở `https://lims.<domain>` | Trang đăng nhập hiện, ổ khoá xanh |
| 2 | Đăng nhập bằng `SEED_ADMIN_EMAIL` | Vào được dashboard |
| 3 | **Đổi mật khẩu admin ngay** | — |
| 4 | Tải lên 1 file đính kèm rồi tải xuống | Không có lỗi `SignatureDoesNotMatch` → B3 đúng |
| 5 | Xem audit log sau khi đăng nhập | Cột IP là **IP thật**, không phải `172.x.x.x` → B2 đúng |
| 6 | Nhấn F5 ở một route con (vd `/documents/abc`) | Không ra 404 (SPA fallback hoạt động) |
| 7 | Bật thông báo đẩy trên trình duyệt | Nhận được thông báo (Web Push cần HTTPS — Cloudflare đã cấp) |
| 8 | Mở bằng điện thoại | Giao diện responsive đúng (xem `RESPONSIVE_TESTPLAN.md`) |
| 9 | `curl -I https://lims.<domain>/api/v1/health` | Header `cf-cache-status: BYPASS` hoặc `DYNAMIC` |

---

## 10. Vận hành

### Sao lưu — làm ngay ngày đầu

```bash
# Postgres
docker exec lims-postgres pg_dump -U lims lims | gzip > lims-$(date +%F).sql.gz

# MinIO (đính kèm)
docker run --rm -v lims_miniodata:/data -v $PWD:/backup alpine \
  tar czf /backup/minio-$(date +%F).tar.gz -C /data .
```

Đặt vào cron hằng ngày và **chép ra khỏi máy chủ**.

### Cập nhật phiên bản

```bash
git pull
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml \
               --env-file .env.prod up -d --build
```

Service `migrate` chạy `alembic upgrade head` một lần, có advisory lock, trước khi API khởi động.

### Xem log / gỡ lỗi

Vì overlay không mở cổng ra host, truy cập DB/Redis/MinIO qua exec:

```bash
docker exec -it lims-postgres psql -U lims -d lims
docker exec -it lims-redis redis-cli -a "$REDIS_PASSWORD"
```

### Gỡ tunnel tạm thời (chạy nội bộ để debug)

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
# → quay lại có cổng 3060/8060 trên host
```

---

## 11. Việc chưa làm trong repo này

- [ ] Áp bản sửa B2 (`Dockerfile` + `nginx.conf`) — **tôi chưa sửa**, vì nó đổi hành vi ghi log/rate-limit của backend, cần bạn quyết
- [ ] Cron sao lưu tự động
- [ ] Giám sát (uptime, cảnh báo đĩa đầy)
- [x] `.env.prod` đã nằm trong `.gitignore` (đã kiểm tra) ✔
