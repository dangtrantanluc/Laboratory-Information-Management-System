# Chuyển LIMS sang máy Windows và deploy

Hướng dẫn mang **toàn bộ hệ thống LIMS đang chạy** (mã nguồn + dữ liệu Postgres +
file đính kèm MinIO) từ máy Linux hiện tại sang một **máy Windows 10/11 dùng Docker
Desktop**, vẫn phục vụ qua **Cloudflare Tunnel + tên miền cũ**.

Viết ngày **12/08/2026**. Bản Linux: [DEPLOY_LINUX.md](./DEPLOY_LINUX.md) ·
Chi tiết Cloudflare: [DEPLOY_CLOUDFLARE.md](./DEPLOY_CLOUDFLARE.md).

---

## 0. Trước hết: repo đã được sửa những gì để chạy được trên Windows

Bốn thay đổi dưới đây là **bắt buộc**, không phải tuỳ chọn. Nếu bạn dùng một bản
clone cũ hơn commit này, ba trong bốn lỗi sẽ xảy ra ngay và thông báo lỗi không hề
chỉ đúng nguyên nhân.

| # | Vấn đề trên Windows | Triệu chứng nếu không sửa | Đã sửa ở đâu |
|---|---|---|---|
| 1 | Git for Windows mặc định `core.autocrlf=true`, đổi `entrypoint.sh` sang CRLF. File này là ENTRYPOINT của image Linux → shebang thành `#!/usr/bin/env bash\r`, kernel đi tìm interpreter tên `bash\r`. | `exec /app/entrypoint.sh: no such file or directory` — nói "không có file" trong khi file rõ ràng nằm đó. Container `lims-api` restart vô hạn. | [`.gitattributes`](./.gitattributes) mới — ép LF cho `*.sh`, `*.conf`, `*.yml`, Dockerfile |
| 2 | `COMPOSE_FILE=a.yml:b.yml` dùng dấu `:` — mặc định của Linux. Windows tách bằng `;`. | `no such file or directory: docker-compose.prod.yml:docker-compose.cloudflare.yml` | `.env.prod.example` — đổi sang `;` và khai tường minh `COMPOSE_PATH_SEPARATOR=;` (chạy đúng trên **cả hai** hệ điều hành) |
| 3 | Không khai `COMPOSE_PROJECT_NAME` → compose lấy **tên thư mục** làm tên project, mà tên volume dữ liệu = `<project>_lims_pgdata`. Clone vào thư mục tên khác là dữ liệu nằm ở volume khác. | Stack chạy bình thường, đăng nhập được, nhưng **DB trống trơn**. Dữ liệu không mất, chỉ nằm ở volume không ai gắn vào. | `.env.prod.example` + `.env.prod` — khoá cứng `COMPOSE_PROJECT_NAME=lims` |
| 4 | `image: minio/minio:latest` — máy Windows `docker pull` sẽ lấy bản **mới hơn** máy Linux. Cùng một commit, hai máy chạy hai phần mềm khác nhau. | Khác biệt hành vi không giải thích được, kiểu "trên máy anh chạy được". | `docker-compose.prod.yml` — ghim `minio/minio:RELEASE.2025-09-07T16-13-09Z` |

Ngoài ra `docker-compose.prod.yml` nay cho ghi đè `LIMS_API_CPUS` / `LIMS_API_MEM`
ngay ở hồ sơ prod (trước chỉ overlay Cloudflare mới cho) — cần thiết vì số nhân
Docker thấy trên Windows là số nhân **máy ảo WSL2**, không phải của máy.

**Không có bind mount nào** trong hồ sơ production — toàn bộ dữ liệu nằm trong
volume Docker. Đây là lý do việc chuyển sang Windows khả thi và gọn.

---

## 1. Yêu cầu máy Windows đích

| Hạng mục | Tối thiểu | Khuyến nghị |
|---|---|---|
| Hệ điều hành | Windows 10 64-bit 22H2 | Windows 11 |
| RAM máy | 8 GB | **16 GB** |
| RAM cấp cho Docker | 5 GB | 8 GB |
| CPU | 2 nhân | 4 nhân |
| Ổ đĩa trống trên C: | 30 GB | 60 GB |
| Ảo hoá | Bật trong BIOS (VT-x / AMD-V) | |

Tổng `mem_limit` khai trong hồ sơ prod là **4.75 GB** (postgres 2g + minio 1g +
api 1g + redis 512m + cloudflared 256m). Cấp cho Docker ít hơn 5 GB thì container
bị OOM-kill giữa chừng — biểu hiện là container tự restart mà **không có lỗi ứng
dụng nào trong log**, rất dễ đi tìm nhầm chỗ.

---

## GIAI ĐOẠN 1 — Chuẩn bị máy Windows

Làm hết giai đoạn này **trước** khi động vào máy Linux. Máy cũ vẫn phục vụ người
dùng bình thường trong lúc bạn chuẩn bị.

### 1.1 Bật WSL2 và cài Docker Desktop

Mở **PowerShell với quyền Administrator**:

```powershell
wsl --install
# Khởi động lại máy khi được yêu cầu, rồi:
wsl --update
wsl --set-default-version 2
wsl --status
```

Tải Docker Desktop tại <https://www.docker.com/products/docker-desktop/> và cài với
tuỳ chọn **Use WSL 2 instead of Hyper-V** (mặc định).

> **Giấy phép:** Docker Desktop miễn phí cho cá nhân, giáo dục và doanh nghiệp nhỏ,
> nhưng cần trả phí nếu tổ chức có **trên 250 nhân viên hoặc doanh thu trên 10 triệu
> USD/năm**. Phòng thí nghiệm thuộc trường đại học thường thuộc diện dùng miễn phí,
> nhưng đây là việc nên xác nhận với bộ phận CNTT trước, không phải sau.

### 1.2 Cấp tài nguyên cho WSL2

Docker trên Windows chạy trong một máy ảo WSL2. Mặc định máy ảo này chỉ được cấp
**50% RAM máy**, và đó là con số Docker thực sự có — không phải RAM của máy.

Tạo file `%USERPROFILE%\.wslconfig` (ví dụ `C:\Users\Admin\.wslconfig`):

```ini
[wsl2]
memory=8GB
processors=4
swap=2GB
```

Áp dụng (đóng hết cửa sổ WSL trước):

```powershell
wsl --shutdown
# Khởi động lại Docker Desktop, rồi kiểm:
docker info --format "CPU: {{.NCPU}}  RAM: {{.MemTotal}}"
```

Nếu máy chỉ có 2 nhân, mở `.env.prod` (ở giai đoạn 4) và thêm `LIMS_API_CPUS=2`.

### 1.3 Cho phép chạy script PowerShell

Windows chặn chạy file `.ps1` theo mặc định. Không mở khoá thì mọi script trong
`scripts\windows\` đều báo *"cannot be loaded because running scripts is disabled"*.

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

`RemoteSigned` chỉ đòi chữ ký với script **tải từ Internet**; script trong repo bạn
tự copy sang thì chạy được. Không cần `Unrestricted`.

> File copy từ USB/mạng đôi khi bị Windows gắn cờ "vùng Internet". Nếu vẫn bị chặn:
> `Get-ChildItem -Recurse scripts\windows\*.ps1 | Unblock-File`

### 1.4 Máy chủ thì đừng để ngủ

Máy Windows để bàn mặc định sẽ ngủ, và ngủ là toàn bộ container dừng phục vụ.

```powershell
# Chạy với quyền Administrator
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change monitor-timeout-ac 15
powercfg /hibernate off
```

### 1.5 Loại trừ thư mục Docker khỏi quét thời gian thực

Windows Defender quét từng lần ghi vào ổ đĩa ảo WSL2 làm I/O chậm rõ rệt (Postgres
là thứ chịu ảnh hưởng nặng nhất).

```powershell
# Quyền Administrator
Add-MpPreference -ExclusionPath "$env:LOCALAPPDATA\Docker"
Add-MpPreference -ExclusionProcess "com.docker.backend.exe"
Add-MpPreference -ExclusionProcess "vmmem.exe"
Add-MpPreference -ExclusionProcess "vmmemWSL.exe"
```

### 1.6 Docker Desktop phải tự khởi động

**Settings → General → ✅ Start Docker Desktop when you log in**.

> **Hạn chế thật, cần biết trước:** Docker Desktop cần một **phiên đăng nhập
> người dùng**. Máy khởi động lại mà không ai đăng nhập thì Docker không chạy, và
> `restart: unless-stopped` cũng vô nghĩa vì không có Docker để restart cái gì.
>
> Với máy đóng vai trò server, có hai cách xử lý — chọn theo chính sách CNTT của
> đơn vị:
>
> - **Tự đăng nhập rồi khoá màn hình** — dùng `netplwiz`, bỏ chọn "Users must enter
>   a user name and password", rồi tạo tác vụ khoá màn hình ngay sau khi đăng nhập.
>   Đơn giản, nhưng mật khẩu tài khoản đó nằm trong registry.
> - **Chuyển sang Docker Engine trong WSL2** (không dùng Docker Desktop) và bật
>   `systemd` trong WSL — chạy nền không cần đăng nhập, nhưng cấu hình phức tạp hơn
>   và ngoài phạm vi tài liệu này.
>
> Dù chọn cách nào, hãy **kiểm bằng cách khởi động lại máy thật** ở mục 6.3 trước
> khi bàn giao. Đây là điểm hay bị bỏ qua và chỉ lộ ra vào lần mất điện đầu tiên.

---

## GIAI ĐOẠN 2 — Đưa mã nguồn sang máy Windows

### 2.1 Nếu clone bằng git (khuyến nghị)

```powershell
# ĐẶT TRƯỚC KHI CLONE, không phải sau
git config --global core.autocrlf false

cd C:\
git clone <url-repo> lims
cd C:\lims
```

`.gitattributes` mới đã ép LF cho mọi file chạy trong container, nên về nguyên tắc
`core.autocrlf` không còn quan trọng. Đặt `false` là lớp phòng thủ thứ hai.

Đường dẫn ngắn (`C:\lims`) tránh giới hạn 260 ký tự của Windows với cây
`node_modules` khi build frontend.

### 2.2 Nếu copy thủ công (USB / mạng)

Trên máy Linux, đóng gói **loại trừ** thư mục rác:

```bash
cd /home/tanluc/workspace
tar czf lims-source.tar.gz \
    --exclude='lims/.git' \
    --exclude='lims/**/node_modules' \
    --exclude='lims/**/__pycache__' \
    --exclude='lims/.env*' \
    lims
```

`--exclude='lims/.env*'` là cố ý: file cấu hình chứa bí mật sẽ đi riêng ở giai đoạn
3, qua kênh có mã hoá, chứ không lẫn trong gói mã nguồn.

Giải nén trên Windows bằng **7-Zip** (không dùng "Extract All" của Explorer với file
`.tar.gz` lồng nhau) vào `C:\lims`.

### 2.3 Kiểm bản sao ngay

```powershell
cd C:\lims
.\scripts\windows\preflight-deploy.ps1
```

Lúc này chưa có `.env.prod` nên script sẽ dừng ở dòng đầu — đúng như mong đợi. Điều
cần xem là **không có dòng `[X] CRLF trong: ...`** ở mục "Ket thuc dong". Nếu có,
quay lại 2.1 và clone lại; đừng sửa tay từng file.

---

## GIAI ĐOẠN 3 — Xuất dữ liệu từ máy Linux

### 3.1 Chốt thời điểm ngừng nhận dữ liệu mới

Mọi thứ người dùng nhập **sau** thời điểm dump sẽ không có trên máy mới. Vì vậy hãy
cắt luồng người dùng trước khi dump, thay vì dump lúc hệ thống đang được dùng:

```bash
cd /home/tanluc/workspace/lims

# Ngắt tunnel: người dùng không vào được nữa, nhưng Postgres/MinIO vẫn chạy để dump.
docker compose stop cloudflared
```

Từ giây phút này hệ thống ngừng phục vụ. Phần còn lại của giai đoạn 3–5 nên làm
liền mạch; với khối dữ liệu cỡ hiện tại (DB ~780 KB, file ~25 MB) toàn bộ mất
khoảng 20–30 phút, phần lớn là thời gian build image trên máy Windows.

### 3.2 Chạy script xuất

```bash
./scripts/export-for-windows.sh ~/lims-export
```

Script tự làm và tự kiểm:

| Việc | Cách tự kiểm |
|---|---|
| `db.dump` — Postgres định dạng custom (`-Fc`) | chạy `pg_restore --list`, dump hỏng là dừng ngay |
| `minio-files.tar.gz` — toàn bộ file đính kèm | hỏi compose tên volume thật, chặn archive < 1 KB |
| `env.prod` — bản sao cấu hình | |
| `SHA256SUMS.txt` | để bên Windows kiểm file sang có nguyên vẹn không |
| `SOURCE-INFO.txt` | commit git, phiên bản Docker/MinIO/Postgres, `alembic_version` đang ở đâu |

> **Vì sao phải dump chứ không copy thẳng thư mục volume:** dữ liệu Postgres trên
> đĩa phụ thuộc kiến trúc CPU, phiên bản server và locale lúc `initdb`. Copy thẳng
> `/var/lib/postgresql/data` giữa hai máy là cách làm hỏng dữ liệu rất im lặng —
> server vẫn khởi động, rồi index sai thứ tự sắp xếp. `pg_dump`/`pg_restore` đi qua
> SQL nên không mang theo lớp phụ thuộc đó.

### 3.3 Đóng gói để mang đi

```bash
tar czf ~/lims-export.tar.gz -C ~ lims-export
sha256sum ~/lims-export.tar.gz
```

⚠️ **`env.prod` chứa toàn bộ mật khẩu hạ tầng và token Cloudflare.** Chuyển qua kênh
có mã hoá — USB đã mã hoá BitLocker, SFTP, hoặc 7-Zip đặt mật khẩu (chế độ AES-256).
Không gửi qua Zalo/email/Drive không mã hoá. Xoá bản trung gian sau khi deploy xong.

### 3.4 **Chưa** xoá gì trên máy Linux

Giữ nguyên volume và container trên máy cũ cho tới khi máy Windows đã nghiệm thu
xong (giai đoạn 6). Đó là phương án quay lui duy nhất của bạn.

**Tuyệt đối không chạy `docker compose down -v`** trên máy Linux — cờ `-v` xoá volume
dữ liệu. Chỉ `docker compose down` (không có `-v`) là đủ để dừng.

---

## GIAI ĐOẠN 4 — Cấu hình trên máy Windows

Giải nén gói dữ liệu ra một thư mục, ví dụ `D:\lims-export`.

### 4.1 Cấu hình: dùng lại `.env.prod` của máy cũ

Vì đang **mang dữ liệu theo**, hãy dùng thẳng file cũ. **Đừng** chạy
`init-env-prod.ps1` — script đó sinh bí mật mới, mà:

- `POSTGRES_PASSWORD` phải khớp với giá trị lúc `initdb` chạy trên volume mới;
- đổi `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` sẽ khiến MinIO không đọc được kho
  file vừa khôi phục;
- đổi `JWT_SECRET` làm mọi phiên đăng nhập hiện có mất hiệu lực (chấp nhận được,
  nhưng nên là quyết định có chủ đích).

Script `restore-from-linux.ps1` ở giai đoạn 5 sẽ tự copy `env.prod` → `.env.prod`.
Nếu muốn làm tay:

```powershell
Copy-Item D:\lims-export\env.prod C:\lims\.env.prod
```

### 4.2 Sửa dấu phân cách hồ sơ compose

Mở `C:\lims\.env.prod` bằng **Notepad** (hoặc VS Code) và kiểm ba dòng đầu:

```ini
COMPOSE_PATH_SEPARATOR=;
COMPOSE_FILE=docker-compose.prod.yml;docker-compose.cloudflare.yml
COMPOSE_PROJECT_NAME=lims
```

Nếu file cũ còn ghi `docker-compose.prod.yml:docker-compose.cloudflare.yml` (dấu hai
chấm), **phải đổi thành dấu chấm phẩy**. Preflight ở bước 5.1 cũng bắt lỗi này.

> Lưu bằng Notepad ở dạng **UTF-8**, không phải "UTF-8 with BOM". Có BOM thì compose
> đọc khoá đầu tiên thành `\ufeffCOMPOSE_PATH_SEPARATOR` và lặng lẽ bỏ qua nó — sau
> đó báo thiếu file compose trong khi dòng khai báo rành rành trong file.

### 4.3 Số nhân CPU

```powershell
docker info --format "{{.NCPU}}"
```

Nếu kết quả **nhỏ hơn 2**, thêm vào `.env.prod`:

```ini
LIMS_API_CPUS=1
```

Docker **từ chối khởi động** container nếu `cpus` khai lớn hơn số nhân sẵn có. Nếu
số nhân nhỏ hơn 4, nên hạ luôn `UVICORN_WORKERS` cho khớp (mỗi worker mà không có
nhân riêng thì tranh CPU, chậm hơn chứ không nhanh hơn).

### 4.4 Cloudflare Tunnel — dùng lại token cũ

Cách gọn nhất: **giữ nguyên `CLOUDFLARE_TUNNEL_TOKEN`**. Tunnel chỉ là một connector
đăng ký ngược lên Cloudflare; máy nào cầm token thì máy đó nhận traffic. Không phải
sửa DNS, không phải tạo tunnel mới, tên miền không đổi.

> ⚠️ **Điều kiện bắt buộc: không được để hai máy cùng chạy tunnel một lúc.** Cả hai
> connector cùng đăng ký thì Cloudflare **chia đều traffic** giữa chúng — khoảng một
> nửa số request rơi vào máy Linux cũ với dữ liệu cũ. Đây là lỗi rất khó chẩn đoán
> vì hệ thống *hầu như* hoạt động: người dùng lúc thấy dữ liệu mới, lúc thấy dữ liệu
> cũ, tuỳ request. Ở bước 3.1 ta đã `docker compose stop cloudflared` trên máy Linux
> chính là để tránh việc này — hãy chắc chắn nó đã dừng.

Nếu muốn tạo tunnel mới thay vì dùng lại: Cloudflare Dashboard → Zero Trust →
Networks → Tunnels → Create tunnel → copy token vào `.env.prod`. Tab **Public
Hostname** đặt `<tên-miền>` → `HTTP` → `lims-web:80` (là tên service trong mạng
docker, **không phải** `localhost`).

---

## GIAI ĐOẠN 5 — Khôi phục và khởi chạy

### 5.1 Preflight

```powershell
cd C:\lims
.\scripts\windows\preflight-deploy.ps1
```

Phải thấy **`=== SAN SANG DEPLOY ===`**. Script kiểm 8 nhóm: kết thúc dòng, hồ sơ
compose, đủ 14 biến bắt buộc và không còn `CHANGE_ME`, định dạng URL, độ dài khoá
VAPID, độ mạnh bí mật, chế độ Linux containers, và tài nguyên WSL2.

Dòng `[!]` là cảnh báo (chạy được nhưng nên xem), dòng `[X]` là lỗi chặn.

### 5.2 Khôi phục dữ liệu và khởi chạy

Một lệnh làm hết:

```powershell
.\scripts\windows\restore-from-linux.ps1 -BundlePath D:\lims-export
```

Script sẽ, theo thứ tự:

1. kiểm SHA-256 của cả 3 file — sai là dừng, không restore một nửa;
2. tạo `.env.prod` nếu chưa có (không ghi đè nếu đã có);
3. **dừng lại nếu volume dữ liệu đã tồn tại** và yêu cầu bạn chạy lại kèm `-Fresh`
   (rồi gõ đúng chữ `XOA` để xác nhận) — chốt an toàn chống ghi đè nhầm;
4. dựng Postgres rỗng, chờ `pg_isready`, `docker cp` dump vào rồi `pg_restore`;
5. **đếm số bản ghi bảng `users` và đọc `alembic_version`** — bảng rỗng là báo lỗi,
   không tin vào mã thoát của `pg_restore` (nó luôn cảnh báo về owner/extension);
6. giải nén file đính kèm vào volume MinIO;
7. `docker compose up -d --build` toàn bộ stack.

> Bước 4 và 6 đi qua `docker cp` và volume có tên, **không mount thư mục host**. Đây
> là lựa chọn có chủ đích cho Windows: `docker run -v "C:\duong\dan:/backup"` vướng
> dấu `:` của ký tự ổ đĩa và phụ thuộc thiết lập File Sharing của Docker Desktop.
> Script cũng không dùng toán tử `>` của PowerShell để hứng dữ liệu nhị phân —
> PowerShell 5.1 ghi ra UTF-16LE, tạo ra file dump trông đủ lớn nhưng `pg_restore`
> không đọc nổi, và người ta thường chỉ phát hiện vào đúng ngày cần khôi phục.

Lần đầu build mất **5–15 phút** (npm ci + vite build + pip install).

### 5.3 Theo dõi lúc khởi động

```powershell
.\scripts\windows\dc.ps1 ps
.\scripts\windows\dc.ps1 logs -f lims-api
```

`dc.ps1` là wrapper gọi `docker compose` với đúng hai file `-f` và `--env-file`.
**Dùng nó thay cho `docker compose` trần**: trên Linux thư mục dự án có `.env` là
symlink trỏ vào `.env.prod` nên compose trần chạy đúng hồ sơ, còn Windows không có
symlink đó — `docker compose ps` trần sẽ nạp `docker-compose.yml`, tức hồ sơ **dev**,
và nói về một stack khác với stack đang phục vụ.

Mốc cần thấy trong log:

| Service | Dòng cần thấy |
|---|---|
| `lims-migrate` | thoát với mã 0 (`docker compose ps -a` hiện `Exited (0)`) |
| `lims-api` | `Application startup complete` |
| `lims-cloudflared` | `Registered tunnel connection` |
| tất cả | `docker compose ps` hiện `(healthy)` |

`lims-api` có `start_period: 90s` nên trong phút rưỡi đầu trạng thái `starting` là
bình thường, chưa phải dấu hiệu hỏng.

---

## GIAI ĐOẠN 6 — Nghiệm thu

### 6.1 Kiểm từ bên trong

```powershell
# Liveness + readiness (readiness chạm cả DB, Redis, MinIO)
.\scripts\windows\dc.ps1 exec lims-api curl -fsS http://localhost:8060/health
.\scripts\windows\dc.ps1 exec lims-api curl -fsS http://localhost:8060/health/ready

# Migration đã lên head chưa
.\scripts\windows\dc.ps1 exec postgres psql -U lims -d lims -tAc "SELECT version_num FROM alembic_version;"
```

Giá trị `alembic_version` phải **khớp với `SOURCE-INFO.txt`** trong gói dữ liệu.

### 6.2 Kiểm bằng tay qua trình duyệt — 5 việc

Mở tên miền thật (không phải `localhost`) và làm đủ 5 việc sau. Bốn việc đầu chỉ
chứng minh stack chạy; **việc thứ 5 mới là thứ chứng minh việc chuyển máy thành công**.

1. **Đăng nhập** bằng một tài khoản có thật từ máy cũ → xác nhận Postgres đã sang đủ.
2. **Mở dashboard** → xác nhận Redis cache và truy vấn chéo module chạy được.
3. **Tải về một file đính kèm cũ** (CoA, SOP, ảnh đại diện) → đây là phép kiểm quan
   trọng nhất: nó chứng minh **cả** MinIO có dữ liệu, **và** `MINIO_PUBLIC_ENDPOINT`
   khớp origin nên chữ ký presigned s3v4 hợp lệ. Tải về lỗi 403 hoặc 404 gần như
   luôn là do biến này sai, không phải do file mất.
4. **Tải lên một file mới** → xác nhận quyền ghi vào volume MinIO.
5. **Đếm chéo một con số** — ví dụ tổng số mẫu hoặc tổng số người dùng — và so với
   con số ghi lại từ máy Linux **trước khi** dump. Bằng nhau mới coi là chuyển xong.

### 6.3 Kiểm khả năng tự phục hồi — làm trước khi bàn giao

Đây là phép kiểm hay bị bỏ qua nhất, và là phép kiểm sẽ được dùng đến vào lần mất
điện đầu tiên:

```powershell
Restart-Computer
```

Sau khi máy lên (và đăng nhập nếu cần), **không chạy lệnh nào**, đợi 3–5 phút rồi mở
tên miền bằng điện thoại dùng 4G. Vào được nghĩa là chuỗi *Windows khởi động → Docker
Desktop tự chạy → container `unless-stopped` tự lên → tunnel tự đăng ký lại* đã liền
mạch. Không vào được thì quay lại mục 1.6.

### 6.4 Sau khi nghiệm thu xong

Trên máy **Linux**:

```bash
cd /home/tanluc/workspace/lims
docker compose down          # KHÔNG có -v — giữ volume để còn quay lui được
```

Giữ nguyên volume ít nhất **2 tuần** vận hành ổn định trên máy mới rồi mới tính
chuyện dọn.

Gói `lims-export` bạn vừa dùng chính là **bản backup ngày 0** của máy Windows. Cất
nó lại đúng chỗ (mục 7.1) thay vì xoá — cho tới khi tác vụ backup tự động đã chạy
thành công ít nhất hai đêm liên tiếp, đó là bản sao lưu duy nhất bạn có. Riêng
`env.prod` trong gói thì tách ra cất riêng, đừng để chung với dump.

---

## GIAI ĐOẠN 7 — Vận hành trên Windows

### 7.1 Backup tự động — thiết lập ngay ngày đầu

```powershell
# Chạy thử trước, xem có ra file không
.\scripts\windows\lims-backup.ps1 -Dest D:\lims-backup -RemotePath \\nas\backup\lims
```

Script dump Postgres, đóng gói MinIO, **tự kiểm bằng `pg_restore --list`**, xoá bản
cũ hơn 14 ngày, và nhân bản sang đường dẫn thứ hai. Thoát khác 0 nếu có bất kỳ lỗi
nào — backup im lặng thất bại là backup vô dụng đúng lúc cần nhất.

Đặt lịch chạy 02:00 hằng ngày (PowerShell **Administrator**):

```powershell
$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\lims\scripts\windows\lims-backup.ps1" -Dest "D:\lims-backup" -RemotePath "\\nas\backup\lims"'

$trigger = New-ScheduledTaskTrigger -Daily -At 2:00AM

# -RunLevel Highest và tài khoản có quyền gọi Docker. Dùng chính tài khoản đang
# đăng nhập Docker Desktop: tác vụ chạy dưới tài khoản khác sẽ không thấy Docker.
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -TaskName 'LIMS Backup' `
    -Action $action -Trigger $trigger -Principal $principal -Settings $settings
```

Kiểm ngay, đừng đợi tới 2 giờ sáng:

```powershell
Start-ScheduledTask -TaskName 'LIMS Backup'
Get-ScheduledTaskInfo -TaskName 'LIMS Backup' | Select LastRunTime, LastTaskResult
# LastTaskResult phải là 0
Get-ChildItem D:\lims-backup
```

> `-LogonType S4U` cho phép tác vụ chạy khi người dùng **không đăng nhập**, nhưng
> Docker Desktop thì lại **cần** phiên đăng nhập (mục 1.6). Nghĩa là: nếu máy chọn
> phương án tự đăng nhập + khoá màn hình thì backup chạy được; nếu không có ai đăng
> nhập thì Docker không chạy và backup sẽ thất bại với `LastTaskResult` khác 0 —
> đúng như mong muốn, vì đó là thông tin bạn cần biết.

### 7.2 Diễn tập khôi phục — làm ngay, trước khi có dữ liệu mới

Backup chưa từng được khôi phục thử thì chưa phải backup — nó mới chỉ là một file có
kích thước trông hợp lý. Chế độ **mặc định** của script khôi phục là diễn tập, và nó
**không đụng tới production**:

```powershell
.\scripts\windows\restore-backup.ps1
```

Nó giải nén thật archive file đính kèm để đếm mục (`gzip -t` không phát hiện được
tar cụt đuôi), khôi phục dump vào một database riêng `lims_drill`, đếm bảng/người
dùng/`alembic_version`, **so số người dùng với production hiện tại**, rồi xoá sạch:

```
[restore] OK  archive doc duoc — 728 muc
[restore] OK  dien tap thanh cong
     bang            : 69
     nguoi dung      : 10   (production hien tai: 10)
     alembic_version : 1718870400032
```

Số khớp production là bản backup dùng được. Lệnh khác:

```powershell
.\scripts\windows\restore-backup.ps1 -List                      # co nhung ban nao, ban nao thieu ve
.\scripts\windows\restore-backup.ps1 -Timestamp 2026-08-12_0200 # dien tap mot ban cu the
.\scripts\windows\restore-backup.ps1 -Timestamp ... -Full       # KHOI PHUC THAT (hoi xac nhan)
```

### 7.2.1 Toàn bộ quy trình sao lưu & khôi phục

Bốn tình huống khôi phục (xoá nhầm vài bản ghi · DB hỏng · chỉ mất file đính kèm ·
mất cả máy), quy tắc 3-2-1, RPO/RTO, giám sát, bảo mật bản dump, và danh sách kiểm
theo tuần/tháng/năm — xem runbook riêng:

**→ [`ops/BACKUP_WINDOWS.md`](ops/BACKUP_WINDOWS.md)**

Ba điểm quan trọng nhất, tóm lại ở đây:

- **Redis cố ý không được backup.** Nó chỉ giữ jti denylist, lockout, cache RBAC và
  lock cron — dựng lại được hết. Mất Redis nghĩa là token đã đăng xuất sống lại tới
  khi hết hạn tự nhiên; `ACCESS_TOKEN_TTL_MINUTES=10` giới hạn thiệt hại còn 10 phút.
- **Đừng backup bằng cách copy `ext4.vhdx` của WSL2.** Copy ổ đĩa ảo khi Docker đang
  chạy cho ra ảnh chụp không nhất quán — Postgres đang ghi dở. Nó trông như một bản
  backup, mount được, và hỏng theo cách chỉ lộ ra khi cần dùng.
- **Cất `.env.prod` tách khỏi dump.** Để chung một ổ là trao cả dữ liệu lẫn chìa
  khoá cho người nhặt được. Mà thiếu nó thì dump vô dụng: `POSTGRES_PASSWORD` phải
  khớp lúc `initdb`.

### 7.3 Lệnh hằng ngày

```powershell
cd C:\lims
.\scripts\windows\dc.ps1 ps                     # trạng thái
.\scripts\windows\dc.ps1 logs -f lims-api       # log realtime
.\scripts\windows\dc.ps1 logs --tail 200 lims-api
.\scripts\windows\dc.ps1 restart lims-api       # khởi động lại 1 service
.\scripts\windows\dc.ps1 down                   # dừng (KHÔNG có -v)
.\scripts\windows\dc.ps1 up -d                  # chạy lại
docker stats --no-stream                        # RAM/CPU từng container
```

### 7.4 Cập nhật mã mới

```powershell
cd C:\lims
.\scripts\windows\lims-backup.ps1 -Dest D:\lims-backup   # backup TRƯỚC, luôn luôn
git pull
.\scripts\windows\preflight-deploy.ps1                   # biến mới có thể đã xuất hiện
.\scripts\windows\dc.ps1 up -d --build
.\scripts\windows\dc.ps1 logs -f lims-api
```

Migration chạy ở service `lims-migrate` riêng, có advisory lock, **trước** khi
`lims-api` khởi động — không cần làm gì thêm.

### 7.5 Gỡ lỗi khi không có cổng nào mở ra host

Overlay Cloudflare gỡ hết cổng publish, nên không `curl localhost:8060` được từ
Windows. Vào bên trong mà kiểm:

```powershell
.\scripts\windows\dc.ps1 exec lims-api sh
.\scripts\windows\dc.ps1 exec postgres psql -U lims -d lims
.\scripts\windows\dc.ps1 exec redis redis-cli -a "$((Select-String '^REDIS_PASSWORD=' .env.prod).Line -replace '^REDIS_PASSWORD=','')" ping
```

Cần mở tạm MinIO Console để xem kho file:

```powershell
docker run --rm -d --name minio-peek --network lims_default -p 9001:9001 alpine sleep 3600
# hoặc đơn giản hơn: thêm tạm `ports: ["9461:9001"]` cho service minio rồi up -d,
# xem xong NHỚ GỠ RA — console MinIO không nên mở ra host lâu dài.
```

---

## 8. Lỗi thường gặp trên Windows

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `exec /app/entrypoint.sh: no such file or directory` | `entrypoint.sh` bị CRLF (bản clone cũ, chưa có `.gitattributes`) | `git config --global core.autocrlf false`, clone lại. Kiểm bằng preflight mục "Ket thuc dong". |
| `no such file or directory: docker-compose.prod.yml:docker-compose.cloudflare.yml` | `COMPOSE_FILE` dùng dấu `:` kiểu Linux | Đổi sang `;` và thêm `COMPOSE_PATH_SEPARATOR=;` |
| `... cannot be loaded because running scripts is disabled` | Execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (mục 1.3) |
| `image operating system "linux" cannot be used on this platform` | Docker đang ở chế độ Windows containers | Chuột phải biểu tượng Docker → *Switch to Linux containers* |
| `Range of CPUs is from 0.01 to N.00` khi `up` | `cpus: 2.0` > số nhân WSL2 | Thêm `LIMS_API_CPUS=<số nhân thật>` vào `.env.prod` |
| Container tự restart liên tục, **log không có lỗi ứng dụng nào** | WSL2 hết RAM, tiến trình bị OOM-kill | Tăng `memory=` trong `%USERPROFILE%\.wslconfig`, rồi `wsl --shutdown` |
| Đăng nhập được nhưng **DB trống** | `COMPOSE_PROJECT_NAME` khác lúc restore → gắn nhầm volume | `docker volume ls` xem volume nào có dữ liệu; đặt lại `COMPOSE_PROJECT_NAME` cho khớp |
| Tải file đính kèm về **403 / 404** | `MINIO_PUBLIC_ENDPOINT` không khớp origin thật → chữ ký presigned s3v4 sai | Đặt đúng `https://<tên-miền>`, **không** kèm `/lims-attachments`, **không** có `/` cuối |
| Lúc thấy dữ liệu mới, lúc thấy dữ liệu cũ | **Hai máy cùng chạy tunnel một token** → Cloudflare chia traffic | `docker compose stop cloudflared` trên máy Linux |
| Web Push im lặng, không lỗi, không log | Khoá VAPID sai định dạng (thường là đối tượng Python của `py_vapid`) | `.\scripts\windows\gen-vapid-keys.ps1` — tự kiểm 87/43 ký tự |
| Sau khi máy khởi động lại thì không vào được | Docker Desktop cần phiên đăng nhập | Mục 1.6 |
| `pg_restore` báo lỗi owner/extension | Bình thường — extension do superuser tạo | Bỏ qua; `restore-from-linux.ps1` đã kiểm bằng số bản ghi thật thay vì mã thoát |
| Postgres không nhận `POSTGRES_PASSWORD` mới | Volume đã có dữ liệu → `initdb` không chạy lại | Volume phải trống trước khi restore: dùng `-Fresh` |
| Build frontend lỗi đường dẫn quá dài | Giới hạn 260 ký tự | Clone vào `C:\lims`, hoặc `git config --system core.longpaths true` |

---

## 9. Danh sách kiểm trước khi bàn giao

**Máy Windows**

- [ ] `.wslconfig` cấp ≥ 8 GB RAM; `docker info` xác nhận
- [ ] Docker Desktop bật "Start when you log in"; đã **khởi động lại máy thật** và hệ thống tự lên (6.3)
- [ ] Máy không ngủ (`powercfg`)
- [ ] Execution policy cho phép chạy script
- [ ] Thư mục Docker đã loại trừ khỏi Defender

**Cấu hình**

- [ ] `preflight-deploy.ps1` ra `=== SAN SANG DEPLOY ===`
- [ ] `COMPOSE_PATH_SEPARATOR=;` · `COMPOSE_PROJECT_NAME=lims`
- [ ] `.env.prod` **không** bị git theo dõi (preflight tự kiểm)
- [ ] Chỉ **một** máy đang chạy `cloudflared`

**Dữ liệu**

- [ ] Số người dùng / số mẫu trên máy mới **khớp** với máy cũ (6.2 việc 5)
- [ ] Tải về được một file đính kèm **cũ** (6.2 việc 3)
- [ ] Tải lên được một file **mới** (6.2 việc 4)
- [ ] `alembic_version` khớp `SOURCE-INFO.txt`

**Vận hành**

- [ ] Tác vụ "LIMS Backup" đã chạy thử, `LastTaskResult = 0`, có file trong thư mục đích
- [ ] `restore-backup.ps1` (diễn tập) chạy sạch, số người dùng khớp production (7.2)
- [ ] `-RemotePath` trỏ tới đích **ngoài máy này**, và đã có phương án bản thứ 3 ngoài toà nhà
- [ ] `D:\lims-backup` bật BitLocker và đã giới hạn quyền thư mục
- [ ] `.env.prod` đã cất **tách khỏi** thư mục chứa dump, có ghi chú ngày tạo và người giữ
- [ ] Đã đổi mật khẩu admin gốc sau lần đăng nhập đầu
- [ ] Volume trên máy Linux vẫn còn nguyên để quay lui

**Bảo mật**

- [ ] Đã xoá gói `lims-export` (chứa `env.prod`) khỏi USB và mọi thư mục trung gian
- [ ] `.env.prod` trên máy Windows chỉ tài khoản quản trị đọc được
