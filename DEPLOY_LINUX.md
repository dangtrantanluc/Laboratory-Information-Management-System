# Triển khai LIMS trên máy Linux (qua Cloudflare Tunnel)

Hướng dẫn đi từ máy Linux trắng đến hệ thống chạy được trên tên miền công khai.

**Không cần IP tĩnh, không cần mở cổng firewall, không cần chứng chỉ TLS** —
Cloudflare Tunnel kết nối *ra ngoài* nên máy chủ có thể nằm sau NAT hoặc modem
nhà mạng.

> Kiểm chứng ngày 2026-07-26 trên commit `7e8ede4`. Nếu bạn deploy commit khác,
> đối chiếu lại danh sách biến bắt buộc ở §4.

---

## 0. Kiến trúc sau khi chạy

```
Người dùng ──HTTPS──> Cloudflare ──tunnel──> cloudflared ──> lims-web (nginx)
                                              (container)         │
                                                                  ├─> lims-api:8060
                                                                  └─> minio:9000
```

`lims-web` đã reverse-proxy sẵn `/api/` và `/lims-attachments/`, nên **toàn hệ
thống đi qua đúng một origin** và chỉ cần một tunnel.

Sáu container: `postgres` · `redis` · `minio` · `migrate` (chạy rồi thoát) ·
`lims-api` · `lims-web`, cộng `cloudflared`.

**Không container nào mở cổng ra host** khi dùng overlay Cloudflare. Đây là điểm
quan trọng về bảo mật, xem §6.

---

## 1. Yêu cầu máy

| Hạng mục | Tối thiểu | Khuyến nghị |
|---|---|---|
| CPU | 2 nhân | 4 nhân |
| RAM | 4 GB | 8 GB |
| Đĩa trống | 20 GB | 50 GB |
| Hệ điều hành | Ubuntu 22.04 / Debian 12 / RHEL 9 | Ubuntu 24.04 |

Cần **Docker Engine ≥ 24** và **Docker Compose v2** (lệnh `docker compose`, không
phải `docker-compose` có gạch nối).

```bash
# Ubuntu/Debian — cài Docker chính thức
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker

# Kiểm
docker --version
docker compose version        # phải là v2.x
nproc && free -g && df -h /
```

> **Máy 1 nhân:** `docker-compose.prod.yml` đặt `cpus: 2.0` cho `lims-api` và
> Docker sẽ **từ chối khởi động** nếu host ít nhân hơn. Overlay Cloudflare cho
> phép ghi đè bằng biến `LIMS_API_CPUS` — xem §4.

---

## 2. Lấy mã nguồn

```bash
sudo mkdir -p /opt/lims && sudo chown "$USER:$USER" /opt/lims
git clone https://github.com/dangtrantanluc/Laboratory-Information-Management-System.git /opt/lims
cd /opt/lims
git log --oneline -1        # ghi lại commit đang deploy
```

---

## 3. Sinh bí mật

**Không đặt bí mật thật vào bất kỳ file nào được git theo dõi.** Toàn bộ đi vào
`.env.prod` (đã nằm trong `.gitignore`).

```bash
cp .env.prod.example .env.prod
chmod 600 .env.prod
```

### 3.1 Khoá Web Push VAPID — bắt buộc

```bash
./scripts/gen-vapid-keys.sh >> .env.prod
```

> ⚠ **Đừng dùng `python -c "print(v.public_key)"` của py_vapid.** Nó in ra đối
> tượng Python (`<cryptography...ECPublicKey object at 0x...>`), không phải khoá.
> Đặt chuỗi đó vào `.env.prod` thì container **vẫn khởi động** — phép kiểm
> `${VAR:?}` chỉ xét biến rỗng hay không — rồi Web Push hỏng âm thầm, không lỗi,
> không log. Script trên tự khẳng định độ dài 87/43 ký tự nên sai định dạng là
> nó dừng ngay.

### 3.2 Các bí mật còn lại

```bash
{
  echo "JWT_SECRET=$(openssl rand -hex 32)"
  echo "POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')"
  echo "REDIS_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')"
  echo "MINIO_ROOT_USER=lims-$(openssl rand -hex 4)"
  echo "MINIO_ROOT_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=')"
  echo "SEED_ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=')"
} >> .env.prod
```

Xoá các dòng rỗng trùng tên còn sót từ file mẫu:

```bash
awk -F= '!seen[$1]++ || $0 ~ /^#/ || NF<2' .env.prod > .env.prod.tmp && mv .env.prod.tmp .env.prod
grep -c '^[A-Z]' .env.prod        # đếm số biến đã điền
```

---

## 4. Điền `.env.prod`

Mở `.env.prod` và điền nốt phần phụ thuộc tên miền. **Thay `lims.tenmien.com`
bằng tên miền thật của bạn.**

```bash
APP_PUBLIC_URL=https://lims.tenmien.com
CORS_ORIGINS=https://lims.tenmien.com
MINIO_PUBLIC_ENDPOINT=https://lims.tenmien.com
VAPID_CLAIMS_EMAIL=admin@tenmien.com
SEED_ADMIN_EMAIL=admin@tenmien.com

# SMTP — dùng để gửi mail xác thực đăng ký và đặt lại mật khẩu
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=email-cua-ban@gmail.com
SMTP_PASSWORD=<app-password-16-ky-tu>
SMTP_STARTTLS=true
SMTP_FROM_NAME=LIMS Viện CNSH & Môi trường

# Hiệu năng — xem ghi chú bên dưới
UVICORN_WORKERS=4
DB_POOL_SIZE=8
DB_MAX_OVERFLOW=12
DB_POOL_TIMEOUT=5
ACCESS_TOKEN_TTL_MINUTES=10

# Chỉ thêm dòng này nếu máy có ÍT HƠN 2 nhân
# LIMS_API_CPUS=1.0
```

### Ba biến hay điền sai

| Biến | Quy tắc | Sai thì gặp gì |
|---|---|---|
| `APP_PUBLIC_URL` | Có `https://`, **không** có `/` cuối | Link trong mail xác thực hỏng |
| `CORS_ORIGINS` | Khớp **chính xác** tên miền, không `/` cuối | Trình duyệt chặn mọi lời gọi API |
| `MINIO_PUBLIC_ENDPOINT` | **Chỉ origin**, KHÔNG kèm tên bucket, không `/` cuối | Tải lên được nhưng tải về 403/404 (chữ ký presigned lệch) |

### Về `DB_POOL_SIZE`

Giá trị mặc định 8/12 tính cho `max_connections=100`. Đo tải thực tế ở **60
người đồng thời** cho thấy pool cạn (159 lỗi `QueuePool`) — xem
[docs/go-live-verification.md](docs/go-live-verification.md) §4.

- **Pilot dưới 20 người:** giữ nguyên 8/12, không chạm tới ngưỡng đó.
- **Trên 30 người:** nâng lên `DB_POOL_SIZE=12` / `DB_MAX_OVERFLOW=28` và
  bảo đảm Postgres `max_connections ≥ 200`.

### Kiểm cấu hình trước khi chạy

```bash
./scripts/preflight-deploy.sh .env.prod
```

Script này bắt các lỗi mà Docker **không** bắt được, hoặc chỉ bắt được khi đã
quá muộn:

- Biến còn nguyên giá trị mẫu `CHANGE_ME_*` — compose coi đó là hợp lệ vì phép
  kiểm `${VAR:?}` chỉ xét chuỗi rỗng, nên container khởi động bình thường rồi
  hỏng ở chỗ khác
- `MINIO_PUBLIC_ENDPOINT` bị thêm thừa tên bucket
- URL thừa dấu `/` cuối
- Khoá VAPID sai định dạng
- `JWT_SECRET` ngắn hơn 32 ký tự
- `SEED_ADMIN_PASSWORD` là mật khẩu mặc định đã công khai trong repo
- Máy ít nhân hơn `cpus` mà compose yêu cầu

Chỉ chạy `docker compose up` khi script báo **SẴN SÀNG DEPLOY**.

---

## 5. Tạo Cloudflare Tunnel

Dùng tunnel **kiểu token** (remote-managed) — cấu hình trên dashboard, không cần
file config trong repo.

1. Vào **Cloudflare Dashboard → Zero Trust → Networks → Tunnels**
2. **Create a tunnel** → chọn **Cloudflared** → đặt tên, ví dụ `lims`
3. Trang tiếp theo hiện lệnh cài kèm token dài. **Chỉ copy chuỗi token**, dán vào
   `.env.prod`:

```bash
CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoi...
```

4. Sang tab **Public Hostname → Add a public hostname**:

| Trường | Giá trị |
|---|---|
| Subdomain | `lims` |
| Domain | `tenmien.com` |
| Type | `HTTP` |
| URL | `lims-web:80` |

> `lims-web:80` là **tên service trong mạng Docker**, không phải `localhost`.
> `cloudflared` chạy cùng mạng compose nên gọi thẳng được. Điền `localhost` là
> tunnel báo 502.
>
> Type là `HTTP` chứ không phải `HTTPS`: TLS kết thúc ở biên Cloudflare, chặng
> trong mạng Docker không cần mã hoá.

Tên miền phải đã được trỏ nameserver về Cloudflare. Bản ghi DNS do tunnel tự tạo,
bạn không cần thêm tay.

---

## 6. Khởi chạy

```bash
cd /opt/lims
docker compose \
  -f docker-compose.prod.yml \
  -f docker-compose.cloudflare.yml \
  --env-file .env.prod \
  up -d --build
```

**Ba điều quan trọng trong lệnh này:**

1. **Hai file `-f`.** Overlay `docker-compose.cloudflare.yml` thêm `cloudflared`
   và **gỡ mọi cổng đã publish** (`ports: !reset []`). Thiếu nó thì cổng 3060 mở
   ra `0.0.0.0`, ai trong mạng LAN cũng gọi thẳng nginx được — bỏ qua Cloudflare
   và **giả được header `CF-Connecting-IP`**, tức là né rate limit và đầu độc
   nhật ký kiểm toán.

2. **`--env-file .env.prod`.** Không có thì compose đọc `.env` mặc định và mọi
   biến `${VAR:?}` sẽ báo thiếu.

3. **`--build` là bắt buộc.** Bỏ nó thì compose dựng container từ image cũ có thể
   thiếu migration mới → alembic báo `Can't locate revision` và API trả 502. Đây
   là lỗi đã gặp thật, luôn dùng `--build` khi cập nhật mã.

### Migration chạy lúc nào

Tự động, không cần lệnh riêng. `entrypoint.sh` lấy **advisory lock của Postgres**
(khoá `875321875321`) trước khi chạy `alembic upgrade head`, nên nhiều container
khởi động cùng lúc vẫn an toàn — container sau chờ container trước xong.

Service `migrate` chạy migration rồi thoát; `lims-api` cũng kiểm lại. Trùng lặp
có chủ đích và vô hại nhờ lock.

### Theo dõi lần khởi động đầu

```bash
export C="docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml --env-file .env.prod"
$C ps
$C logs -f lims-api        # chờ dòng "[entrypoint] Khởi động ứng dụng..."
$C logs cloudflared | grep -i "registered\|connection"
```

Lần đầu mất 2–5 phút (build image + chạy 30 migration + seed dữ liệu gốc).

---

## 7. Kiểm tra sau khi chạy

```bash
# Trong máy — qua mạng docker, không qua internet
$C exec lims-web wget -qO- http://localhost/health && echo

# Từ ngoài — qua Cloudflare
curl -fsS https://lims.tenmien.com/health && echo
curl -fsS https://lims.tenmien.com/health/ready && echo   # kiểm cả DB, Redis, MinIO

# Migration đã lên head chưa
$C exec lims-api alembic current
```

`/health` là liveness (không phụ thuộc gì). `/health/ready` chạm DB, Redis, MinIO
— dùng nó để biết thành phần nào hỏng.

### Kiểm bằng tay — 4 việc

1. Mở `https://lims.tenmien.com`, đăng nhập bằng `SEED_ADMIN_EMAIL` +
   `SEED_ADMIN_PASSWORD`
2. **Đổi mật khẩu admin ngay**
3. Tạo thử một khách hàng → xác nhận lưu được
4. Tải lên một tệp đính kèm rồi **tải về** → xác nhận `MINIO_PUBLIC_ENDPOINT`
   đúng (đây là chỗ hay sai nhất, và chỉ lộ ra khi tải về chứ không phải lúc tải lên)

---

## 8. Bắt buộc làm ngay sau khi chạy được

### 8.1 Xử lý thông tin đăng nhập công khai

`acc.txt` trong repo liệt kê 9 tài khoản demo kèm mật khẩu dùng chung, và repo là
**công khai**. Nếu bạn seed các tài khoản đó, bất kỳ ai cũng đăng nhập được.

```bash
# Đổi mật khẩu mọi tài khoản demo, hoặc vô hiệu hoá chúng
$C exec postgres psql -U lims -d lims -c \
  "UPDATE users SET status='disabled' WHERE email LIKE '%@lims.local' AND role <> 'admin';"
```

### 8.2 Bật backup tự động

```bash
sudo cp ops/backup/lims-backup.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/lims-backup.sh
sudo mkdir -p /var/backups/lims

sudo crontab -e
# Thêm dòng:
0 2 * * * cd /opt/lims && /usr/local/bin/lims-backup.sh >> /var/log/lims-backup.log 2>&1
```

### 8.3 Diễn tập khôi phục — **làm một lần trước khi có dữ liệu thật**

```bash
sudo /usr/local/bin/lims-backup.sh          # tạo bản backup đầu tiên
ls -lh /var/backups/lims/
```

Rồi thử restore theo [ops/RUNBOOK.md](ops/RUNBOOK.md) §2 trên một máy khác hoặc
một database tạm. **Backup chưa từng restore thử thì chưa phải backup.**

### 8.4 Điền liên hệ trong runbook

[ops/RUNBOOK.md](ops/RUNBOOK.md) §0 còn 4 ô trống. Runbook không có số điện thoại
là runbook vô dụng lúc 2 giờ sáng.

---

## 9. Vận hành hằng ngày

Đặt bí danh cho gọn — thêm vào `~/.bashrc`:

```bash
alias limsc='docker compose -f /opt/lims/docker-compose.prod.yml -f /opt/lims/docker-compose.cloudflare.yml --env-file /opt/lims/.env.prod'
```

| Việc | Lệnh |
|---|---|
| Trạng thái | `limsc ps` |
| Log API | `limsc logs -f --tail=200 lims-api` |
| Tài nguyên | `docker stats --no-stream` |
| Khởi động lại một service | `limsc restart lims-api` |
| Dừng toàn bộ | `limsc down` (giữ nguyên dữ liệu) |

### Cập nhật mã mới

```bash
cd /opt/lims
git pull
limsc up -d --build          # LUÔN có --build
limsc exec lims-api alembic current
curl -fsS https://lims.tenmien.com/health/ready
```

### Quay lui bản lỗi

```bash
cd /opt/lims
git log --oneline -10
git checkout <commit-tốt>
limsc up -d --build
```

> ⚠ **Quay lui mã KHÔNG tự quay lui migration.** Nếu bản lỗi đã chạy migration
> mới, hạ cấp trước rồi mới checkout:
> ```bash
> limsc exec lims-api alembic downgrade -1
> ```
> Kiểm `downgrade()` của migration đó có thật sự đảo ngược được không — vài
> migration làm mất dữ liệu khi hạ cấp (ví dụ m30 hạ `pending` → `disabled`).

---

## 10. Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `Set VAPID_PRIVATE_KEY in .env` khi khởi động | Chưa chạy `gen-vapid-keys.sh` | §3.1 |
| Container `lims-api` không khởi động, log nói về cpus | Host < 2 nhân | Thêm `LIMS_API_CPUS=1.0` vào `.env.prod` |
| Tunnel 502 | Public hostname điền `localhost` | Sửa thành `lims-web:80` (§5) |
| Trình duyệt báo lỗi CORS | `CORS_ORIGINS` lệch tên miền hoặc thừa `/` | §4 |
| Tải tệp lên được, tải về 403/404 | `MINIO_PUBLIC_ENDPOINT` sai — hay bị thêm thừa `/lims-attachments` | §4 |
| API 502 sau khi cập nhật | Quên `--build`, image cũ thiếu migration | `limsc up -d --build` |
| `Can't locate revision` | Cùng nguyên nhân trên | Như trên |
| Mail xác thực không tới | SMTP sai, hoặc Gmail cần App Password | Kiểm `limsc logs lims-api \| grep -i smtp` |
| Đĩa đầy | Log Docker, image cũ | `docker builder prune -af && docker image prune -a` |

Chẩn đoán chung khi chưa rõ:

```bash
limsc ps                                   # service nào unhealthy
limsc logs --tail=100 lims-api
curl -fsS https://lims.tenmien.com/health/ready   # thành phần nào hỏng
df -h / && docker stats --no-stream
```

---

## 11. Điều cần biết trước khi mở cho khách hàng

Trạng thái hiện tại theo
[docs/go-live-verification.md](docs/go-live-verification.md): **đạt 5/7 cổng
go-live**, hai cổng trượt đều do pool database cạn ở **60 người đồng thời**.

| Quy mô | Kết luận |
|---|---|
| Pilot ≤ 20 người | **Chạy được** — không chạm ngưỡng pool |
| 30–60 người | Cần nâng `DB_POOL_SIZE=12` / `DB_MAX_OVERFLOW=28` trước |

Những hạn chế cần chấp nhận có ý thức:

- **RPO 24 giờ** — sự cố mất tối đa một ngày làm việc. Muốn nhỏ hơn phải bật WAL
  archiving, chưa có trong repo.
- **Xuất Excel/PDF chạy trong request** — có semaphore giới hạn 2 nên không sập,
  chỉ chậm khi nhiều người xuất cùng lúc.
- **6/7 bảng phân trang phía client** — bảng lớn tải chậm.
- **Access token nằm trong `localStorage`** — XSS lấy được token. Đã cân nhắc
  chuyển sang bộ nhớ nhưng dừng có chủ đích, lý do ghi ở
  [ops/RUNBOOK.md](ops/RUNBOOK.md) §10.

---

## 12. Danh sách kiểm trước khi bàn giao

```
[ ] docker compose version → v2.x
[ ] .env.prod chmod 600, đủ 13 biến bắt buộc (§4)
[ ] Khoá VAPID sinh bằng scripts/gen-vapid-keys.sh, không phải chép tay
[ ] Chạy với ĐỦ HAI file -f (prod + cloudflare)
[ ] limsc ps → không cổng nào publish ra host
[ ] https://lims.tenmien.com/health/ready → 200
[ ] Đăng nhập được, ĐÃ ĐỔI mật khẩu admin
[ ] Tải tệp lên VÀ tải về đều được
[ ] Tài khoản demo trong acc.txt đã đổi mật khẩu hoặc vô hiệu hoá
[ ] Cron backup 02:00 đã bật
[ ] ĐÃ diễn tập restore ít nhất một lần
[ ] ops/RUNBOOK.md §0 đã điền liên hệ
[ ] Ghi lại commit đang chạy: git log --oneline -1
```
