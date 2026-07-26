# Runbook: clone code sang máy khác và deploy

Kiểm tra lại ngày **26/07/2026**. Phần Cloudflare chi tiết: [DEPLOY_CLOUDFLARE.md](./DEPLOY_CLOUDFLARE.md).

---

## GIAI ĐOẠN 0 — Kiểm tra trước khi rời máy dev

Khác với bản runbook trước, **`origin/main` giờ đã đủ để clone-và-chạy**:

```
origin/main = 7e8ede4  (Merge PR #1: Giai đoạn 0-2 kế hoạch bảo trì + hạ tầng P3)
migration   = 30/30 file đã có trên main
6 module backend đang được import (context, rate_limit, metrics,
  idempotency, request_limits, security_headers) = đã có trên main
docker-compose.prod.yml / .cloudflare.yml / .env.prod.example / .gitignore = đã có
```

Bao gồm cả `scripts/gen-vapid-keys.sh` và bản sửa lệnh sinh khoá VAPID — clone `main` là đủ, không cần nhánh nào khác.

### 0.1 Tự kiểm tra `origin/main` trước khi rời máy dev

Đừng tin bảng trên, chạy lại — repo thay đổi mỗi ngày:

```bash
git fetch origin
# Phải ra 30
git ls-tree -r --name-only origin/main -- lims-backend/alembic/versions/ | grep -c '\.py$'
# Phải ra 6
git ls-tree -r --name-only origin/main -- lims-backend/app | grep -cE \
  'core/(context|rate_limit|metrics)\.py|middleware/(idempotency|request_limits|security_headers)\.py'
# Phải liệt kê đủ 4 file
git ls-tree -r --name-only origin/main | grep -E \
  '^(docker-compose\.(prod|cloudflare)\.yml|\.env\.prod\.example|scripts/gen-vapid-keys\.sh)$'
# Nhánh làm việc còn commit nào chưa lên main không (phải rỗng)
git log --oneline origin/main..HEAD
```

### 0.2 `acc.txt` vẫn đang public trên GitHub

Vẫn được git track. File chứa email + mật khẩu tài khoản test theo vai trò.

Production **không** dùng lại mật khẩu này (`SEED_ADMIN_PASSWORD` đọc từ `.env.prod`), nên không phải sự cố rò rỉ production. Nhưng nên gỡ:

```bash
git rm --cached acc.txt
echo "acc.txt" >> .gitignore
git commit -m "chore: gỡ acc.txt khỏi git (tài khoản test)"
```

> Chỉ gỡ khỏi commit **tương lai**. File vẫn nằm trong lịch sử git; muốn xoá hẳn phải `git filter-repo` + force push.

### 0.3 Đừng chạy `git add -A`

5 file dump ở thư mục gốc chứa dữ liệu thật (người dùng, hash mật khẩu):

```
lims-pre-m25.dump … lims-pre-m29.dump   (536–674 KB)
```

`.gitignore` hiện đã có `*.dump`, nhưng kiểm tra lại trước mỗi lần push:

```bash
git log --stat -3 | grep -i "\.dump" && echo "⚠ CÓ DUMP — dừng lại!" || echo "✔ sạch"
```

---

## GIAI ĐOẠN 1 — Chuẩn bị máy đích

| | Tối thiểu | Khuyến nghị |
|---|---|---|
| CPU | 2 nhân | 4 nhân |
| RAM | **6 GB** | 8 GB |
| Đĩa | 30 GB | 60 GB |
| OS | Ubuntu 22.04 / 24.04 | |

```bash
nproc && free -g && df -h /
```

> Giới hạn RAM khai trong compose: postgres 2g + minio 1g + api 1g + redis 512m ≈ **4.5 GB**, chưa kể OS và lúc build.
>
> **Máy 1 nhân**: `docker-compose.prod.yml` khai `cpus: 2.0` và Docker **từ chối khởi động** nếu host ít nhân hơn. Đặt `LIMS_API_CPUS=0.8` trong `.env.prod` (chỉ overlay cloudflare đọc biến này — xem §B1 của DEPLOY_CLOUDFLARE.md).

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
docker compose version     # cần >= 2.24
```

---

## GIAI ĐOẠN 2 — Clone và kiểm tra bản clone

```bash
sudo mkdir -p /opt/lims && sudo chown $USER:$USER /opt/lims
git clone https://github.com/dangtrantanluc/Laboratory-Information-Management-System.git /opt/lims
cd /opt/lims
```

**Kiểm tra ngay, đừng bỏ qua** — thiếu là app không khởi động được:

```bash
# Phải ra 30
ls lims-backend/alembic/versions/*.py | wc -l

# Phải tồn tại đủ 6 file
ls lims-backend/app/core/{context,rate_limit,metrics}.py \
   lims-backend/app/middleware/{idempotency,request_limits,security_headers}.py

# Phải tồn tại
ls docker-compose.prod.yml docker-compose.cloudflare.yml .env.prod.example
```

---

## GIAI ĐOẠN 3 — Cấu hình `.env.prod`

```bash
cp .env.prod.example .env.prod
chmod 600 .env.prod
```

`.env.prod` **không bao giờ commit** (`.gitignore` dòng 2 đã chặn). Chỉ sửa `.env.prod`; `.env.prod.example` giữ nguyên `CHANGE_ME`.

### 3.1 Secret sinh bằng máy

```bash
gen() { python3 -c "import secrets;print(secrets.token_urlsafe($1))"; }
sed -i \
  -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(gen 32)|" \
  -e "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$(gen 32)|" \
  -e "s|^MINIO_ROOT_USER=.*|MINIO_ROOT_USER=lims-$(openssl rand -hex 6)|" \
  -e "s|^MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=$(gen 32)|" \
  -e "s|^JWT_SECRET=.*|JWT_SECRET=$(gen 48)|" \
  -e "s|^SEED_ADMIN_PASSWORD=.*|SEED_ADMIN_PASSWORD=$(gen 24)|" \
  .env.prod
```

> Dùng `token_urlsafe` (chỉ `A–Z a–z 0–9 _ -`) chứ **không** dùng `openssl rand -base64` thô: `POSTGRES_PASSWORD` và `REDIS_PASSWORD` được nhúng thẳng vào DSN (`postgresql+psycopg2://lims:PASS@postgres:5432/lims`, `redis://:PASS@redis:6379/0`) nên ký tự `/ + = @ :` sẽ phá URL.

### 3.2 Giá trị phụ thuộc tên miền — phải khớp chính xác, **không có `/` cuối**

```bash
MINIO_PUBLIC_ENDPOINT=https://lims.vien-sinh-hoc.edu.vn
CORS_ORIGINS=https://lims.vien-sinh-hoc.edu.vn
APP_PUBLIC_URL=https://lims.vien-sinh-hoc.edu.vn
VAPID_CLAIMS_EMAIL=admin@vien-sinh-hoc.edu.vn
```

> `MINIO_PUBLIC_ENDPOINT` sai ⇒ tải đính kèm trả `SignatureDoesNotMatch`. Backend ký presigned URL theo host này (`storage_service.py:90`), nginx chuyển tiếp Host nguyên vẹn xuống MinIO nên hai bên phải trùng.
>
> `APP_PUBLIC_URL` sai ⇒ link trong mail xác thực / đặt lại mật khẩu trỏ sai chỗ.

### 3.3 Khoá Web Push VAPID

Cách 1 — script có sẵn trong repo. **Chỉ dùng được sau khi image đã build**: script gọi `docker compose run ... lims-api` qua `docker-compose.yml` (profile dev), nên trên máy vừa clone nó sẽ kích hoạt build. Chú ý ghi vào `.env.prod`, **không** phải `.env`:

```bash
./scripts/gen-vapid-keys.sh >> .env.prod
```

Cách 2 — máy mới chưa build, chỉ cần `openssl`, không cần Docker cũng không cần `py_vapid`:

```bash
K=$(mktemp) && openssl ecparam -genkey -name prime256v1 -noout -out "$K"
PUB=$(openssl ec -in "$K" -pubout -outform DER 2>/dev/null | tail -c 65 | basenc --base64url | tr -d '=\n')
PRIV=$(openssl ec -in "$K" -outform DER 2>/dev/null | tail -c +8 | head -c 32 | basenc --base64url | tr -d '=\n')
shred -u "$K"
[ ${#PUB} -eq 87 ] && [ ${#PRIV} -eq 43 ] || { echo "SAI ĐỘ DÀI — dừng"; }
sed -i -e "s|^VAPID_PUBLIC_KEY=.*|VAPID_PUBLIC_KEY=$PUB|" \
       -e "s|^VAPID_PRIVATE_KEY=.*|VAPID_PRIVATE_KEY=$PRIV|" .env.prod
```

Định dạng đúng: công khai = điểm EC không nén (X9.62) base64url bỏ `=` → **87 ký tự**; riêng = số private 32 byte base64url bỏ `=` → **43 ký tự**.

> 🔴 KHÔNG dùng `print(v.public_key)` của py_vapid: nó in ra **đối tượng** khoá (`<cryptography...ECPublicKey object at 0x...>`). Đặt rác đó vào env thì container **vẫn khởi động** — kiểm tra `${VAR:?}` chỉ xét biến rỗng hay không — rồi Web Push hỏng âm thầm, không lỗi, không log.

### 3.4 SMTP — bắt buộc ở production

`SMTP_HOST` khai `${SMTP_HOST:?}` nên thiếu là compose chặn. `SMTP_USER`/`SMTP_PASSWORD` thì có mặc định rỗng: **để rỗng thì container vẫn chạy, nhưng mail xác thực và đặt lại mật khẩu không gửi được, chỉ ghi log ERROR.**

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=ten.ban@gmail.com
SMTP_PASSWORD=abcdefghijklmnop     # app password 16 ký tự, VIẾT LIỀN
```

> Gmail hiển thị app password dạng `abcd efgh ijkl mnop`. **Bỏ hết dấu cách.** File env đọc nguyên văn nên dấu cách — kể cả một dấu cách lẻ ở cuối dòng — trở thành phần của mật khẩu và Gmail từ chối auth.

### 3.5 Cloudflare Tunnel

Tạo tunnel và lấy token theo §5 của DEPLOY_CLOUDFLARE.md, rồi:

```bash
sed -i "s|^CLOUDFLARE_TUNNEL_TOKEN=.*|CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoi...|" .env.prod
```

### 3.6 Số worker khớp CPU của **máy đích**

```bash
sed -i "s|^UVICORN_WORKERS=.*|UVICORN_WORKERS=$(nproc)|" .env.prod
```

> Tổng kết nối DB = `UVICORN_WORKERS × (DB_POOL_SIZE + DB_MAX_OVERFLOW)` + dự phòng, phải nhỏ hơn `max_connections=200` mà compose đặt cho Postgres. Mặc định `4 × (8+12) + 20 = 100`. Đặt `UVICORN_WORKERS` quá lớn (ví dụ 16 → `16 × 20 = 320`) sẽ làm cạn kết nối.

### 3.7 Chốt: không còn `CHANGE_ME` nào

```bash
grep -n CHANGE_ME .env.prod && echo "⚠ CÒN THIẾU — đừng chạy" || echo "✔ đủ"
grep -nE "your-domain|your\.email" .env.prod && echo "⚠ CÒN PLACEHOLDER tên miền"
```

Compose khai `${VAR:?}` cho 13 biến — thiếu bất kỳ biến nào thì `up` dừng ngay với thông báo tên biến, **nhưng giá trị sai/rác thì nó không phát hiện được**.

---

## GIAI ĐOẠN 4 — Chạy

```bash
cd /opt/lims
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml \
               --env-file .env.prod up -d --build
```

Lần đầu mất **10–25 phút** (build Vite + cài Python deps).

```bash
# migrate phải kết thúc exit 0 TRƯỚC khi api khởi động
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml logs -f migrate

# tunnel: chờ dòng "Registered tunnel connection"
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml logs -f cloudflared
```

Thứ tự khởi động do compose ép: postgres/redis/minio `healthy` → `migrate` chạy `alembic upgrade head` **một lần** dưới advisory lock (`lims-backend/entrypoint.sh`) → `lims-api` (`SKIP_MIGRATIONS=true`, nên không container nào migrate lần hai).

Xác nhận không lộ cổng nào ra host — overlay cloudflare dùng `ports: !reset []` để gỡ `3060:80` mà `docker-compose.prod.yml` publish:

```bash
ss -tlnp | grep -E '3060|8060|5432|6379|9000'   # phải KHÔNG ra gì
```

> Chạy **thiếu** `-f docker-compose.cloudflare.yml` thì cổng 3060 mở ra host và `lims-api` đòi đúng 2 nhân CPU.

---

## GIAI ĐOẠN 5 — Nghiệm thu

| # | Kiểm tra | Kỳ vọng |
|---|---|---|
| 1 | `https://lims.<domain>` | Trang đăng nhập, ổ khoá xanh |
| 2 | Đăng nhập `SEED_ADMIN_EMAIL` | Vào dashboard |
| 3 | **Đổi mật khẩu admin ngay** | — |
| 4 | Tải lên + tải xuống 1 đính kèm | Không `SignatureDoesNotMatch` |
| 5 | F5 tại route con (`/documents/abc`) | Không 404 |
| 6 | Quên mật khẩu → nhận mail | Mail tới, link mở đúng domain |
| 7 | Bật thông báo đẩy trên trình duyệt | Nhận được push (khoá VAPID đúng) |
| 8 | Audit log sau khi đăng nhập | IP thật, **không** phải `172.x.x.x` (§B2 DEPLOY_CLOUDFLARE.md) |
| 9 | Mở bằng điện thoại | Giao diện responsive |
| 10 | `docker compose ps` | Mọi service `Up`, cột PORTS trống |

---

## GIAI ĐOẠN 6 — Ngày đầu vận hành

### Sao lưu — thiết lập ngay

```bash
sudo tee /etc/cron.daily/lims-backup >/dev/null <<'EOF'
#!/bin/bash
set -e
D=/var/backups/lims && mkdir -p $D
docker exec lims-postgres pg_dump -U lims lims | gzip > $D/db-$(date +%F).sql.gz
docker run --rm -v lims_miniodata:/data -v $D:/backup alpine \
  tar czf /backup/files-$(date +%F).tar.gz -C /data .
find $D -mtime +14 -delete
EOF
sudo chmod +x /etc/cron.daily/lims-backup
```

**Chép bản sao lưu ra khỏi máy chủ** — backup nằm cùng máy không phải backup.

### Cập nhật

```bash
cd /opt/lims && git pull
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml \
               --env-file .env.prod up -d --build
```

### Gỡ lỗi (không có cổng mở ra host)

```bash
docker exec -it lims-postgres psql -U lims -d lims
docker exec -it lims-redis redis-cli -a "$(grep ^REDIS_PASSWORD .env.prod | cut -d= -f2)"
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml logs -f lims-api
```

### Xoay secret

Mọi secret đọc từ env lúc khởi động, không nướng vào image — sửa `.env.prod` rồi `up -d` là đủ. Ngoại lệ:

| Secret | Lưu ý khi xoay |
|---|---|
| `JWT_SECRET` | Mọi token đang hoạt động thành vô hiệu → toàn bộ người dùng bị đăng xuất |
| `POSTGRES_PASSWORD` | Volume đã init: phải `ALTER USER lims PASSWORD` trong psql, đổi env một mình **không** đổi mật khẩu trong DB |
| `MINIO_ROOT_*` | Đổi được tự do, MinIO đọc root creds mỗi lần khởi động |
| `VAPID_*` | Mọi subscription push cũ chết, người dùng phải bật lại thông báo |

---

## Tóm tắt thứ tự

```
0. Kiểm origin/main đủ file (§0.1) + gỡ acc.txt
1. Cài Docker trên máy đích, kiểm nproc/RAM
2. git clone + kiểm 30 migration & 6 module
3. .env.prod: secret → domain → VAPID → SMTP → tunnel token → nproc
   chốt bằng: grep CHANGE_ME .env.prod  (phải rỗng)
4. Tạo Cloudflare Tunnel, lấy token
5. docker compose -f prod -f cloudflare --env-file .env.prod up -d --build
6. Nghiệm thu 10 mục + đổi mật khẩu admin
7. Bật cron sao lưu, chép backup ra ngoài
```
