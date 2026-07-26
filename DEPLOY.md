# Runbook: clone code sang máy khác và deploy

Phần Cloudflare chi tiết: [DEPLOY_CLOUDFLARE.md](./DEPLOY_CLOUDFLARE.md).

---

## 🔴 GIAI ĐOẠN 0 — Repo hiện KHÔNG clone-và-chạy được

Kiểm tra ngày 26/07/2026:

```
remote origin  = 99992c7   (github.com/dangtrantanluc/Laboratory-Information-Management-System)
local  HEAD    = 99992c7   ← giống nhau, nghĩa là remote KHÔNG có gì mới
chưa commit    : 148 file sửa (M) + 133 file chưa track (??) + 1 file xoá
```

**Nếu clone ngay bây giờ, máy mới sẽ nhận bản thiếu nghiêm trọng:**

| Thứ bị thiếu | Số lượng | Hậu quả |
|---|---:|---|
| Migration Alembic `m11`→`m29` | **19/28 file** | Schema DB lùi lại nhiều tháng; `alembic upgrade head` dừng ở m10 |
| Module backend đang được import | **6 file** | **App không khởi động được** — `ImportError` ngay lúc import |
| `docker-compose.prod.yml` | 1 | Không có profile production |
| `.gitignore` | 1 | Remote không có gitignore → dễ lỡ commit secret |
| `.github/` (CI) | — | Mất pipeline |
| `.env.prod.example` | 1 | Không biết cần env gì |
| Toàn bộ công việc responsive | 62 file | — |

Chi tiết 6 module backend chưa commit nhưng **đang được import**:

| File | Số nơi import |
|---|---:|
| `app/core/context.py` | 10 |
| `app/core/rate_limit.py` | 5 |
| `app/middleware/idempotency.py` | 4 |
| `app/core/metrics.py` | 3 |
| `app/middleware/request_limits.py` | 2 |
| `app/middleware/security_headers.py` | 1 |

Cùng với 5 model/router mới (`sample_flow.py`, `quotation.py`, `form.py`, `lab_access.py`, `push_subscription.py`…) và các trang frontend mới (`Quotations.tsx`, `SampleFlow.tsx`, `MonthlyReport.tsx`, `Forms.tsx`, `components/sampleFlow/`…).

### 0.1 ⚠ Đừng chạy `git add -A`

5 file dump database ở thư mục gốc **chưa bị ignore** và sẽ bị commit:

```
lims-pre-m25.dump  536 KB
lims-pre-m26.dump  605 KB
lims-pre-m27.dump  626 KB
lims-pre-m28.dump  669 KB
lims-pre-m29.dump  674 KB
```

Dump chứa dữ liệu thật (người dùng, hash mật khẩu). Repo này **public**.

### 0.2 Bổ sung `.gitignore` trước

```bash
cd /home/bbsw/MTL_OCR/limb
cat >> .gitignore <<'EOF'

# Dump database — chứa dữ liệu thật, không bao giờ commit
*.dump
*.sql.gz

# Node
node_modules/
dist/

# Python
__pycache__/
*.pyc
.venv/
EOF
```

### 0.3 Commit theo nhóm (không gộp một cục)

```bash
# 1. Hạ tầng & cấu hình
git add .gitignore .github/ docker-compose.prod.yml docker-compose.cloudflare.yml \
        .env.prod.example DEPLOY.md DEPLOY_CLOUDFLARE.md
git commit -m "chore: bổ sung profile production, CI và gitignore"

# 2. Backend — migration + module (BẮT BUỘC, nếu thiếu app không chạy)
git add lims-backend/
git commit -m "feat(backend): migration m11-m29, rate limit, metrics, sample flow, quotation"

# 3. Frontend
git add lims-frontend/
git commit -m "feat(frontend): sample flow, quotation, báo cáo tháng + refactor responsive"

# 4. Kiểm tra KHÔNG có dump lọt vào trước khi push
git log --stat -3 | grep -i "\.dump" && echo "⚠ CÓ DUMP — dừng lại!" || echo "✔ sạch"

git push origin main
```

### 0.4 `acc.txt` đang public trên GitHub

File `acc.txt` (đã được track, đang ở trên GitHub) chứa danh sách email tài khoản test theo từng vai trò kèm mật khẩu.

Sản phẩm production **không dùng lại** mật khẩu này (`SEED_ADMIN_PASSWORD` đọc từ `.env.prod`), nên không phải sự cố rò rỉ production. Nhưng nên:

```bash
git rm --cached acc.txt
echo "acc.txt" >> .gitignore
git commit -m "chore: gỡ acc.txt khỏi git (tài khoản test)"
```

> Lưu ý: lệnh trên chỉ gỡ khỏi các commit **tương lai**. File vẫn còn trong lịch sử git. Muốn xoá hẳn phải `git filter-repo` + force push — chỉ làm nếu mật khẩu trong đó trùng với hệ thống thật.

---

## GIAI ĐOẠN 1 — Chuẩn bị máy đích

### Yêu cầu

| | Tối thiểu | Khuyến nghị |
|---|---|---|
| CPU | 2 nhân | 4 nhân |
| RAM | **6 GB** | 8 GB |
| Đĩa | 30 GB | 60 GB |
| OS | Ubuntu 22.04 / 24.04 | |

```bash
nproc && free -g && df -h /
```

> Giới hạn RAM đã khai trong compose: postgres 2g + minio 1g + api 1g + redis 512m ≈ **4.5 GB**, chưa kể OS và lúc build.

### Cài Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
docker compose version     # cần >= 2.24
```

---

## GIAI ĐOẠN 2 — Clone

```bash
sudo mkdir -p /opt/lims && sudo chown $USER:$USER /opt/lims
git clone https://github.com/dangtrantanluc/Laboratory-Information-Management-System.git /opt/lims
cd /opt/lims
```

### Kiểm tra bản clone có đủ không — **làm ngay, đừng bỏ qua**

```bash
# Phải ra 28 (không phải 9)
ls lims-backend/alembic/versions/*.py | wc -l

# Phải tồn tại — thiếu là app không khởi động
ls lims-backend/app/core/rate_limit.py \
   lims-backend/app/core/context.py \
   lims-backend/app/core/metrics.py \
   lims-backend/app/middleware/idempotency.py \
   lims-backend/app/middleware/request_limits.py \
   lims-backend/app/middleware/security_headers.py

# Phải tồn tại
ls docker-compose.prod.yml docker-compose.cloudflare.yml .env.prod.example
```

Thiếu bất kỳ thứ gì ⇒ quay lại **Giai đoạn 0**, commit và push cho đủ.

---

## GIAI ĐOẠN 3 — Cấu hình

```bash
cp .env.prod.example .env.prod
chmod 600 .env.prod
```

Sinh secret:

```bash
echo "JWT_SECRET=$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d /=+ | cut -c1-32)"
echo "REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d /=+ | cut -c1-32)"
echo "MINIO_ROOT_PASSWORD=$(openssl rand -base64 32 | tr -d /=+ | cut -c1-32)"
echo "SEED_ADMIN_PASSWORD=$(openssl rand -base64 24 | tr -d /=+ | cut -c1-20)"
```

VAPID (Web Push):

```bash
pip install py-vapid
python3 -c "from py_vapid import Vapid02; v=Vapid02(); v.generate_keys(); print('VAPID_PUBLIC_KEY='+v.public_key); print('VAPID_PRIVATE_KEY='+v.private_key)"
```

Giá trị phụ thuộc tên miền — **phải khớp chính xác**, không có `/` cuối:

```bash
MINIO_PUBLIC_ENDPOINT=https://lims.vien-sinh-hoc.edu.vn
CORS_ORIGINS=https://lims.vien-sinh-hoc.edu.vn
CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoi...        # lấy ở DEPLOY_CLOUDFLARE.md §5
LIMS_API_CPUS=0.8                          # CHỈ khi host có 1 nhân
```

> `MINIO_PUBLIC_ENDPOINT` sai ⇒ tải file đính kèm trả `SignatureDoesNotMatch`. Backend ký presigned URL theo host này (`storage_service.py:90`), nginx chuyển tiếp Host nguyên vẹn xuống MinIO nên hai bên phải trùng.

---

## GIAI ĐOẠN 4 — Chạy

```bash
cd /opt/lims
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml \
               --env-file .env.prod up -d --build
```

Lần đầu mất **10–25 phút** (build Vite + cài Python deps). Theo dõi:

```bash
# migrate phải kết thúc exit 0 TRƯỚC khi api khởi động
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml logs -f migrate

# tunnel: chờ dòng "Registered tunnel connection"
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml logs -f cloudflared
```

Xác nhận không lộ cổng nào ra host:

```bash
ss -tlnp | grep -E '3060|8060|5432|6379|9000'   # phải KHÔNG ra gì
```

---

## GIAI ĐOẠN 5 — Nghiệm thu

| # | Kiểm tra | Kỳ vọng |
|---|---|---|
| 1 | `https://lims.<domain>` | Trang đăng nhập, ổ khoá xanh |
| 2 | Đăng nhập `SEED_ADMIN_EMAIL` | Vào dashboard |
| 3 | **Đổi mật khẩu admin ngay** | — |
| 4 | Tải lên + tải xuống 1 đính kèm | Không `SignatureDoesNotMatch` |
| 5 | F5 tại route con (`/documents/abc`) | Không 404 |
| 6 | Audit log sau khi đăng nhập | IP thật, **không** phải `172.x.x.x` (xem B2 ở DEPLOY_CLOUDFLARE.md) |
| 7 | Mở bằng điện thoại | Giao diện responsive (`RESPONSIVE_TESTPLAN.md`) |
| 8 | `docker compose ps` | Mọi service `Up`, cột PORTS trống |

---

## GIAI ĐOẠN 6 — Ngày đầu vận hành

### Sao lưu (thiết lập ngay)

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

Service `migrate` chạy `alembic upgrade head` một lần, có advisory lock, trước khi API lên.

### Gỡ lỗi (không có cổng mở ra host)

```bash
docker exec -it lims-postgres psql -U lims -d lims
docker exec -it lims-redis redis-cli -a "$REDIS_PASSWORD"
docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml logs -f lims-api
```

---

## Tóm tắt thứ tự

```
0. Commit + push cho đủ  ← BẮT BUỘC, hiện repo thiếu 19 migration + 6 module
1. Cài Docker trên máy đích
2. git clone + KIỂM TRA bản clone đủ file
3. .env.prod (secret + domain)
4. Tạo Cloudflare Tunnel, lấy token
5. docker compose up -d --build
6. Nghiệm thu 8 mục + đổi mật khẩu admin
7. Bật cron sao lưu
```
