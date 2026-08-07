# Runbook vận hành & khôi phục thảm hoạ — LIMS

Người chịu trách nhiệm điền phần **Liên hệ** trước khi go-live. Runbook không có
số điện thoại là runbook vô dụng lúc 2 giờ sáng.

---

## ⚠️ ĐỌC TRƯỚC — luôn dùng `limsc`, đừng gõ `docker compose` trần

```bash
alias limsc='docker compose -f /opt/lims/docker-compose.prod.yml \
                            -f /opt/lims/docker-compose.cloudflare.yml \
                            --env-file /opt/lims/.env.prod'
```
*(Đổi `/opt/lims` thành thư mục deploy thật. Kiểm bằng:
`docker inspect lims-api --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}'`)*

**Vì sao bắt buộc — đây là sự cố đã xảy ra thật, không phải cảnh báo lý thuyết.**
Chạy `docker compose -f docker-compose.prod.yml ...` mà **thiếu** overlay Cloudflare thì
Docker vẫn nhận ra đúng project `lims` và **dựng lại** service theo hồ sơ nó đọc được:

- `cloudflared` **không nằm trong** `docker-compose.prod.yml` ⇒ **không được tạo** ⇒
  tunnel mất ⇒ **hệ thống offline với người dùng thật**.
- `lims-web` lấy lại `ports: "3060:80"` ⇒ mở cổng ra host.
- Nếu lỡ dùng `docker-compose.yml` (hồ sơ DEV): Redis **mất `--requirepass`**, Postgres và
  Redis publish cổng ra host — hạ cấp bảo mật im lặng, dữ liệu vẫn nguyên nên không ai nhận ra.

Toàn bộ lệnh trong runbook này đã đổi sang `limsc`. Nếu bạn thấy `docker compose` trần ở
đâu đó, đó là lỗi — sửa đi.

**Kiểm nhanh sau MỌI thao tác dựng lại container:**
```bash
limsc ps        # phải đủ 6 container, cột PORTS KHÔNG có 0.0.0.0:*
```

---

## 0. Liên hệ

| Vai trò | Tên | Điện thoại | Email |
|---|---|---|---|
| Quản trị hệ thống | *(điền)* | | |
| Phụ trách CNTT Viện | *(điền)* | | |
| Trưởng phòng QLCL (sự cố dữ liệu) | *(điền)* | | |
| Nhà cung cấp hạ tầng | *(điền)* | | |

**Cam kết khôi phục**

| Chỉ số | Giá trị | Cơ sở |
|---|---|---|
| RTO (database) | **5 phút** | Đo thực tế khi diễn tập restore, xem R4.1 |
| RTO (toàn hệ thống) | ~30 phút | RTO DB + khôi phục MinIO + rebuild image |
| RPO | **24 giờ** | Cron backup 02:00 hằng ngày |

> RPO 24h nghĩa là **mất tối đa một ngày làm việc**. Nếu không chấp nhận được,
> phải bật WAL archiving — chưa nằm trong phạm vi đã triển khai.

---

## 1. Kiểm tra nhanh khi có sự cố

```bash
cd /opt/lims
limsc ps          # service nào unhealthy?
limsc logs --tail=100 lims-api
curl -fsS http://localhost:3060/api/v1/health/ready    # DB + Redis + MinIO
df -h /                                                # đĩa còn bao nhiêu
docker stats --no-stream
```

`/health` = liveness (không phụ thuộc gì). `/health/ready` = readiness (chạm DB,
Redis, MinIO) — dùng nó để biết thành phần nào hỏng.

---

## 2. Database mất

**Dấu hiệu:** mọi request 500, log có `OperationalError`, `/health/ready` đỏ.

```bash
limsc ps postgres
limsc logs --tail=200 postgres
df -h /                      # đĩa đầy là nguyên nhân phổ biến nhất
limsc restart postgres
```

**Nếu dữ liệu hỏng — khôi phục:**

```bash
limsc stop lims-api
ls -lt /var/backups/lims/db-*.dump | head        # chọn bản gần nhất
limsc exec -T postgres \
  pg_restore -U lims -d lims --clean --if-exists < /var/backups/lims/db-<TS>.dump
limsc exec postgres \
  psql -U lims -d lims -c "SELECT version_num FROM alembic_version;"
limsc start lims-api
```

⚠ `--clean` **xoá dữ liệu hiện có**. Chỉ chạy khi đã chắc dữ liệu hiện tại hỏng,
và chụp lại `pg_dump` trước đó nếu còn đọc được.

---

## 3. Redis mất

**Hệ thống suy giảm ra sao** (đã kiểm chứng, xem ARCHITECTURE_AUDIT.md §4):

| Chức năng | Khi Redis chết |
|---|---|
| Rate limit | Tự bỏ qua — request vẫn chạy (fail-open có chủ đích) |
| Lockout đăng nhập | Ngừng hoạt động → **mở đường brute-force** |
| jti denylist | Không kiểm được → token đã logout tạm thời dùng lại được |
| Leader-lock scheduler | Replica tự khởi động cron (per-job lock vẫn bảo vệ) |

```bash
limsc restart redis
limsc exec redis redis-cli -a "$REDIS_PASSWORD" ping
limsc exec redis ls -la /data/appendonlydir
```

Có AOF (R3.2) nên jti denylist sống sót qua restart. **Nếu `/data/appendonlydir`
không tồn tại**, AOF chưa bật — mọi token đã đăng xuất đang có hiệu lực trở lại;
phải buộc đăng xuất toàn hệ thống:

```sql
UPDATE refresh_tokens SET revoked_at = now() WHERE revoked_at IS NULL;
```

---

## 4. MinIO mất

Upload lỗi 500; ảnh đại diện tự rơi về chữ cái đầu (`avatar_url()` bắt lỗi);
presigned URL đã phát vẫn dùng được tới khi hết hạn 15 phút.

```bash
limsc restart minio
limsc exec minio ls -la /data
# Khôi phục file từ backup:
docker run --rm -v $(docker compose config --format json \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["volumes"]["lims_miniodata"]["name"])'):/data \
  -v /var/backups/lims:/backup alpine \
  tar xzf /backup/files-<TS>.tar.gz -C /data
```

---

## 5. Nghi ngờ tài khoản bị chiếm

```sql
-- 1. Xem phiên đang mở của người đó
SELECT id, ip, user_agent, created_at FROM refresh_tokens
WHERE user_id = '<uuid>' AND revoked_at IS NULL ORDER BY created_at DESC;

-- 2. Thu hồi TẤT CẢ phiên
UPDATE refresh_tokens SET revoked_at = now()
WHERE user_id = '<uuid>' AND revoked_at IS NULL;

-- 3. Vô hiệu tài khoản
UPDATE users SET status = 'disabled' WHERE id = '<uuid>';

-- 4. Truy vết hành vi (audit_logs là append-only, không ai xoá được)
SELECT at, action, resource, ip FROM audit_logs
WHERE user_id = '<uuid>' ORDER BY at DESC LIMIT 100;
```

> Access token là JWT stateless: thu hồi refresh token **không** giết token đang
> cầm. Nó hết hiệu lực trong tối đa `ACCESS_TOKEN_TTL_MINUTES` (10 phút). Cần
> chặn ngay lập tức thì dùng `/auth/logout?all=true` để đưa jti vào denylist.

---

## 6. Rollback bản deploy

```bash
cd /opt/lims
git log --oneline -10
git checkout <commit-tốt>
limsc up -d --build
```

⚠ **Rollback code KHÔNG tự rollback migration.** Nếu bản lỗi đã chạy migration
mới, phải hạ migration trước:

```bash
limsc exec lims-api alembic downgrade -1
```

Kiểm `downgrade()` của migration đó có thật sự đảo ngược được không — vài
migration làm mất dữ liệu khi hạ cấp (vd m30 hạ `pending` → `disabled`).

---

## 7. Đĩa gần đầy

```bash
df -h /
docker system df
docker builder prune -af          # cache build, an toàn
docker image prune -a             # image không dùng — KIỂM TRƯỚC
du -sh /var/lib/docker/containers/*/*-json.log | sort -h | tail
```

Log Docker đã có rotation (R4.2: 50m×5 cho api). Job CRON-9 dọn `access_stats`
quá 90 ngày và `auth_tokens` quá 7 ngày lúc 3h sáng.

---

## 8. Việc định kỳ

| Chu kỳ | Việc |
|---|---|
| Hằng ngày | Kiểm `/var/log/lims-backup.log` có dòng `HOÀN TẤT` |
| Hằng tuần | Xem top 20 truy vấn chậm (`lims-backend/docs/slow-query-analysis.md`) |
| Hằng tháng | **Diễn tập restore** trên máy khác, ghi lại RTO |
| Hằng quý | Đổi JWT_SECRET, rà soát tài khoản `disabled`, chạy `pip-audit`/`npm audit` |

---

## 9. Điều đã biết là chưa xử lý

| Vấn đề | Ảnh hưởng | Tham chiếu |
|---|---|---|
| Access token trong `localStorage` | XSS lấy được token | R8.1 — **dừng có chủ đích**, xem §10 |
| Không có queue nền | Xuất Excel/PDF chạy trong request | R9.1 chưa triển khai |
| Không có PgBouncer | Giới hạn số worker theo `max_connections` | R9.2 chưa triển khai |
| nginx tin `CF-Connecting-IP` vô điều kiện | **Không khai thác được với triển khai hiện tại** — tunnel là đường vào duy nhất và biên Cloudflare luôn ghi đè header này. Chỉ hở nếu chạy compose thiếu overlay (xem cảnh báo đầu runbook) | ⚠️ **KHÔNG** dùng `set_real_ip_from` với dải IP công khai của Cloudflare: với tunnel, `$remote_addr` là IP container `cloudflared` (172.x), dải đó không bao giờ khớp → `X-Real-IP` rơi về IP container → hỏng nhật ký IP. Xem `docs/SECURITY_AUDIT.md` S-09 |
| RPO 24 giờ | Mất tối đa một ngày làm việc | Cần WAL archiving |

## 10. Vì sao R8.1 (token in-memory) bị dừng

Chuyển access token sang biến JS đòi hỏi mỗi tab gọi `/auth/refresh` lúc khởi
động. Thử nghiệm thực tế cho thấy hai tab cùng làm việc đó:

```
tab 1 → 200
tab 2 → 401 TOKEN_REUSED
kết quả: 0 phiên còn sống — người dùng bị đăng xuất hoàn toàn
```

Reuse detection (`auth_service.refresh`) coi lần gọi thứ hai là dấu hiệu token bị
đánh cắp và thu hồi **toàn bộ chuỗi phiên**. Muốn làm R8.1 phải xử lý trước:
cho phép một cửa sổ ân hạn khi rotate, hoặc đồng bộ refresh giữa các tab bằng
`BroadcastChannel`/`localStorage` lock. Cả hai đều nằm ngoài phạm vi kế hoạch.
