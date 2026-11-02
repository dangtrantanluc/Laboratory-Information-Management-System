# Hướng dẫn deploy LIMS lên máy chủ khách hàng (Windows)

Chuyển hệ thống LIMS đang chạy ở **ribe.com.vn** (máy Linux hiện tại) sang **máy chủ
Windows của khách**, mang theo **toàn bộ dữ liệu**: người dùng, mẫu, báo cáo, nhân sự,
tệp đính kèm. Tên miền **giữ nguyên ribe.com.vn**; người dùng không phải đổi gì.

> Tài liệu này là **lộ trình ngắn** để làm theo từng bước. Giải thích chi tiết từng
> bước và cách xử lý lỗi nằm ở [DEPLOY_WINDOWS.md](DEPLOY_WINDOWS.md); mục tương ứng
> được ghi trong ngoặc, ví dụ *(DW §1.2)*.

---

## Tình trạng hiện tại (cập nhật 02/11/2026)

| | |
|---|---|
| Dữ liệu đã xuất | **15/10/2026 09:06** — 78 bảng, 32 người dùng, 199 tệp |
| Gói dữ liệu | `/home/tanluc/lims-export.7z` (24 MB, **không mật khẩu**) trên máy cũ |
| Thư mục gốc của gói | `/home/tanluc/lims-export/` |
| ribe.com.vn | **Đang ngừng** từ 15/10 (tunnel máy cũ đã tắt, chưa máy nào nhận) |

Vì site ngừng ngay từ lúc xuất, không ai nhập thêm dữ liệu, nên **gói ngày 15/10 vẫn
đầy đủ**, không cần xuất lại. Việc còn lại: làm giai đoạn A–B (nếu chưa), rồi từ
**C3** trở đi trên máy Windows.

> Nếu quyết định **bật lại site trên máy cũ** trước khi chuyển
> (`docker compose start cloudflared`), thì từ đó sẽ có dữ liệu mới. Khi đó, đến ngày
> chuyển phải **xuất lại từ đầu** (C1).

## Hỏi nhanh

**Chỉ cần giải nén gói 7z là chạy được?** — **Không.** Gói chỉ chứa **dữ liệu**.
Máy Windows còn cần: Docker Desktop (A), mã nguồn qua `git clone` (B1), rồi chạy
script khôi phục (C3–C4) và bật tunnel (C5).

**Có cần lấy token Cloudflare mới không?** — **Không.** Token tunnel của ribe.com.vn
đã nằm sẵn trong `env.prod` của gói, và script khôi phục tự dùng nó. Cấu hình phía
Cloudflare (ribe.com.vn → `lims-web:80`) nằm trên Cloudflare, giữ nguyên. Máy nào
chạy cloudflared với token đó thì máy đó nhận tên miền, nên không phải sửa DNS hay
vào trang quản trị Cloudflare. Chỉ cần token mới nếu muốn tạo một tunnel **riêng**.

**Gói dữ liệu ở đâu?** — Trên máy cũ: `/home/tanluc/lims-export.7z`. Không có URL
web. Nếu cần gửi qua mạng thì tự tải lên, nhưng xem quy tắc an toàn ở C2.

---

## Tổng quan

| Giai đoạn | Làm ở đâu | Hệ thống có ngừng không | Thời gian |
|---|---|---|---|
| **A. Chuẩn bị máy Windows** | Máy khách | Không | 1–2 giờ |
| **B. Lấy mã nguồn + build sẵn** | Máy khách | Không | 15–30 phút |
| **C. Ngày chuyển: xuất → khôi phục → chuyển tên miền** | Cả hai máy | **Có, ~15–30 phút** | ~30 phút |
| **D. Nghiệm thu + cài backup** | Máy khách | Không | 30 phút |

A và B làm trước, vào ngày nào cũng được. Chỉ giai đoạn C mới làm gián đoạn người dùng.

**Thành phần hệ thống** (tất cả chạy trong Docker):

| Container | Vai trò |
|---|---|
| `lims-web` | Giao diện web (nginx) |
| `lims-api` | Backend (FastAPI, 2 worker) |
| `lims-postgres` | Cơ sở dữ liệu |
| `lims-minio` | Kho tệp đính kèm — chạy **Silo** (bản cộng đồng kế tục MinIO) |
| `lims-redis` | Phiên đăng nhập, giới hạn tần suất |
| `lims-cloudflared` | Đưa tên miền ribe.com.vn về máy này qua Cloudflare Tunnel |

RAM thực dùng khoảng **550 MB**; tổng giới hạn khai báo khoảng **2,4 GB**.

---

## A. Chuẩn bị máy Windows

### Yêu cầu tối thiểu

| | Tối thiểu | Khuyến nghị |
|---|---|---|
| Hệ điều hành | Windows 10 64-bit 22H2 | Windows 11 |
| CPU | 2 nhân | 4 nhân |
| RAM máy | 8 GB | 16 GB |
| RAM cấp cho Docker | 3 GB | 4 GB |
| Ổ C: trống | 30 GB | 60 GB |
| Ảo hoá (VT-x / AMD-V) | Bật trong BIOS | |
| Internet | Cần (build image + Cloudflare Tunnel) | |

### A1. Cài Docker Desktop và Git *(DW §1.1)*

1. Cài **Docker Desktop** → chọn **WSL 2 backend**, chế độ **Linux containers**.
2. Cài **Git for Windows**.
3. Mở PowerShell, kiểm tra:
   ```powershell
   docker version
   git --version
   ```

### A2. Cấp tài nguyên cho Docker *(DW §1.2)*

Tạo file `%USERPROFILE%\.wslconfig` (ví dụ `C:\Users\Admin\.wslconfig`):

```ini
[wsl2]
memory=4GB
processors=2
```

Rồi chạy `wsl --shutdown`, mở lại Docker Desktop. Kiểm tra:

```powershell
docker info --format "CPU={{.NCPU}}  RAM={{.MemTotal}}"
```

> **CPU phải ≥ 2.** Backend khai `cpus: 2.0`; ít hơn thì Docker từ chối khởi động.
> Máy chỉ có 1 nhân thì thêm `LIMS_API_CPUS=1` vào `.env.prod` ở bước C3.

### A3. Cấu hình Windows cho máy chủ *(DW §1.3–1.6)*

```powershell
# Cho phép chạy script PowerShell trong repo
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# Máy chủ không được ngủ (PowerShell Administrator)
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /hibernate off
```

- Docker Desktop → Settings → General → bật **Start Docker Desktop when you sign in**.
- Đặt máy **tự đăng nhập + khoá màn hình**: Docker Desktop cần một phiên đăng nhập để chạy.
- Loại trừ thư mục Docker khỏi quét virus thời gian thực *(DW §1.5)*.

**✓ Xong A khi:** `docker info` báo CPU ≥ 2; khởi động lại máy thì Docker tự chạy.

---

## B. Lấy mã nguồn và build sẵn (chưa cần dừng hệ thống cũ)

### B1. Clone mã nguồn *(DW §2.1)*

```powershell
# ĐẶT TRƯỚC KHI CLONE
git config --global core.autocrlf false

git clone https://github.com/dangtrantanluc/Laboratory-Information-Management-System C:\lims
cd C:\lims
git log --oneline -1
```

- Dùng đường dẫn ngắn `C:\lims` để tránh giới hạn 260 ký tự của Windows.
- **Không** tải ZIP từ GitHub rồi giải nén bằng Explorer. Cách đó làm hỏng kết thúc
  dòng của các file chạy trong container.

### B2. Build image trước *(rút ngắn thời gian ngừng ở ngày chuyển)*

Bước này cần `.env.prod` để compose đọc cấu hình. Tạm dùng file mẫu chỉ để build:

```powershell
Copy-Item .env.prod.example .env.prod
.\scripts\windows\dc.ps1 build
Remove-Item .env.prod          # BẮT BUỘC xoá: ngày chuyển sẽ dùng .env.prod thật của máy cũ
```

Lần đầu mất 5–15 phút (tải image, `npm ci`, `pip install`). Build xong, ngày chuyển
chỉ còn vài phút.

> Dù build lỗi ở bước này, cũng không ảnh hưởng gì. Ngày chuyển, script khôi phục
> tự build lại.

**✓ Xong B khi:** `docker images` có `lims-lims-api` và `lims-lims-web`; thư mục
`C:\lims` **không còn** file `.env.prod`.

---

## C. Ngày chuyển

> Chọn giờ ít người dùng (tối / cuối tuần) và **báo trước cho người dùng** khoảng
> 30 phút ngừng hệ thống. Từ bước C1 đến khi xong C5, người dùng không vào được.

### Trước khi bắt đầu — dọn tài khoản thử

Dữ liệu hiện có các **tài khoản thử dùng chung mật khẩu `Lims@1234`**. Nếu không xử lý
trước, chúng sẽ đi theo sang máy khách. Vào ribe.com.vn bằng tài khoản quản trị →
**Quản trị → Tài khoản**, rồi **vô hiệu hoá** (hoặc đổi mật khẩu) những tài khoản
không phải người dùng thật:

- `truongphonglab.<mã>@ribe.com.vn`, `ktv.<mã>@ribe.com.vn` (9 phòng lab)
- `ktv@`, `truongphonglab@`, `quantri@`, `lanhdao@`, `nhanmau@`, `chatluong@` `ribe.com.vn`
- các tài khoản `*.demo@lims.local`

> **Lỡ xuất rồi mới nhớ ra?** Không cần xuất lại. Sau khi chuyển xong, làm đúng việc
> này trên máy mới (mục D4). Chỉ cần đừng bàn giao khi các tài khoản này còn hoạt động.

### C1. Máy cũ (Linux): ngừng phục vụ và xuất dữ liệu *(DW §3)*

```bash
cd /home/tanluc/workspace/lims

# Ngắt tunnel: từ giây phút này người dùng không vào được nữa
docker compose stop cloudflared

# Xuất toàn bộ dữ liệu
./scripts/export-for-windows.sh ~/lims-export
```

Script tự tạo và tự kiểm tra:

| File | Nội dung |
|---|---|
| `db.dump` | Toàn bộ cơ sở dữ liệu |
| `minio-files.tar.gz` | Toàn bộ tệp đính kèm |
| `env.prod` | Cấu hình + **mọi mật khẩu + token Cloudflare** |
| `MANIFEST.txt` | Số dòng từng bảng + số tệp, để máy mới đối chiếu |
| `SHA256SUMS.txt` | Kiểm tra file không hỏng khi chuyển |
| `SOURCE-INFO.txt` | Phiên bản mã nguồn / database lúc xuất |

Kết quả phải có dòng `MANIFEST.txt — 78 bảng, … người dùng, … tệp`. Ví dụ lần xuất
ngày 15/10/2026:

```
[export]   db.dump — 938 KB, pg_restore --list OK
[export]   minio-files.tar.gz — 25294 KB
[export]   MANIFEST.txt — 78 bảng, 32 người dùng, 199 tệp
```

> ⚠️ Từ lúc `stop cloudflared`, **ribe.com.vn ngừng phục vụ** (trình duyệt báo lỗi
> 530 của Cloudflare). Phải làm liền mạch tới C5. Nếu máy Windows **chưa sẵn sàng
> trong ngày**, đừng để site ngừng: bật lại tunnel bằng
> `docker compose start cloudflared`, rồi đến ngày chuyển thật thì **xuất lại từ đầu**.
> Gói đã xuất chỉ chứa dữ liệu tới đúng thời điểm xuất; mọi thứ nhập sau đó sẽ không
> có trong gói.

### C2. Đóng gói và gửi sang máy khách

Phải gửi sang máy khách **hai thứ**, theo hai đường khác nhau:

| Thứ cần gửi | Cách gửi |
|---|---|
| **Mã nguồn** | Không gửi file. Máy khách tự `git clone` từ GitHub (bước B1) |
| **Gói dữ liệu** `~/lims-export` | Nén thành **một file 7z có mật khẩu** (bên dưới) |

**Đóng gói trên máy cũ — chọn một trong hai cách:**

```bash
cd ~

# Cách 1 (khuyến nghị) — CÓ mật khẩu, AES-256, mã hoá cả tên file bên trong:
7z a -t7z -mhe=on -p lims-export.7z lims-export      # hỏi mật khẩu 2 lần

# Cách 2 — KHÔNG mật khẩu (cách đang dùng cho lần chuyển này):
7z a -t7z lims-export.7z lims-export

# Cả hai cách: kiểm file nén không hỏng — phải báo "Everything is Ok"
7z t lims-export.7z
ls -lh lims-export.7z   # ~24–26 MB
```

> Mật khẩu ở cách 1 là **mật khẩu bạn tự nhập** lúc chạy lệnh; không ai khác biết
> và không khôi phục được. Quên thì xoá file, nén lại từ thư mục `~/lims-export`
> (thư mục vẫn còn, không cần xuất lại dữ liệu).

**Gửi đi:**

| | Cách 1 (có mật khẩu) | Cách 2 (không mật khẩu) |
|---|---|---|
| Kênh gửi file | USB, Drive hay Zalo đều được | **Chỉ USB trực tiếp**, hoặc Drive chia sẻ **riêng cho đúng một người** |
| Mật khẩu | Gửi qua **kênh khác** với kênh gửi file (gọi điện / nhắn riêng) | — |
| Tuyệt đối không | Gửi mật khẩu kèm file | Đăng lên nhóm Zalo; để link Drive "ai có link cũng xem được" |

> Vì sao phải cẩn thận: trong gói có `env.prod`, chứa **mật khẩu database, kho tệp,
> khoá JWT và token Cloudflare**. Ai có token này là có thể kéo tên miền ribe.com.vn
> về máy của họ. Với cách 2, **ai cầm được file là đọc được hết**.

**Giải nén trên máy Windows:** chuột phải `lims-export.7z` → 7-Zip → *Extract to…*
→ (nhập mật khẩu nếu dùng cách 1) → giải nén vào `D:\lims-export`. Thư mục phải có đủ `db.dump`,
`minio-files.tar.gz`, `env.prod`, `MANIFEST.txt`, `SHA256SUMS.txt`, `SOURCE-INFO.txt`.

### C3. Máy Windows: kiểm tra trước khi khôi phục *(DW §5.1)*

```powershell
cd C:\lims
Copy-Item D:\lims-export\env.prod .env.prod
.\scripts\windows\preflight-deploy.ps1
```

Phải thấy **`=== SAN SANG DEPLOY ===`**. Dòng `[X]` là lỗi phải sửa; dòng `[!]` là
cảnh báo nên đọc.

> **Không** chạy `init-env-prod.ps1`: script đó sinh mật khẩu mới, và dữ liệu cũ sẽ
> không mở được bằng mật khẩu mới.

### C4. Máy Windows: khôi phục *(DW §5.2 — Bước A)*

```powershell
.\scripts\windows\restore-from-linux.ps1 -BundlePath D:\lims-export
```

Script tự làm theo thứ tự, sai ở bước nào là **dừng ngay ở bước đó**:

1. Kiểm SHA-256 của gói dữ liệu.
2. Khôi phục database → **đối chiếu số dòng cả 78 bảng** với máy cũ.
3. Giải nén tệp đính kèm → **đối chiếu số tệp** với máy cũ.
4. Build và khởi động mọi thứ **trừ tunnel**.
5. Chờ backend báo sẵn sàng (database + Redis + kho tệp) và web phục vụ trang.

Thành công khi thấy:

```
[restore] OK  ca 78 bang khop so dong voi may nguon
[restore] OK  da giai nen ... tep dinh kem (khop may nguon)
[restore] OK  lims-api san sang (DB + Redis + kho tep deu ket noi duoc)
[restore] OK  khoi phuc xong — TUNNEL CHUA BAT, nguoi dung van dang vao may cu
```

> Nếu báo **volume đã tồn tại** (đã thử khôi phục trước đó): chạy lại kèm `-Fresh`,
> rồi gõ `XOA` để xác nhận xoá dữ liệu thử.

### C5. Tắt hẳn máy cũ, rồi chuyển tên miền về máy Windows *(DW §5.2 — Bước B)*

**Thứ tự này bắt buộc.** Hai máy dùng chung một token Cloudflare. Nếu cả hai cùng bật,
Cloudflare chia request cho cả hai, và dữ liệu bị ghi vào hai database khác nhau mà
không có báo lỗi nào.

```bash
# Máy cũ (Linux)
docker stop lims-cloudflared lims-api
```

```powershell
# Máy Windows — script hỏi xác nhận, gõ đúng:  DA TAT MAY CU
.\scripts\windows\restore-from-linux.ps1 -StartTunnel
```

Thành công khi thấy `[restore] OK  tunnel da ket noi`.

> **Không xoá gì trên máy cũ** ít nhất 1–2 tuần. Đó là đường lùi (xem mục E).

---

## D. Nghiệm thu và bàn giao

### D1. Kiểm tra qua trình duyệt *(DW §6.2)*

Mở **https://ribe.com.vn** (nên dùng cửa sổ ẩn danh) và kiểm:

- [ ] Đăng nhập được bằng tài khoản thật.
- [ ] Mở một phiếu có **tệp đính kèm** → tải / xem được tệp.
- [ ] **Báo cáo phân tích mẫu**: thấy đúng các quý đã nộp.
- [ ] **Báo cáo & Thống kê**: xuất thử một file Excel.
- [ ] **Thẻ vào PTN**: danh sách đúng số sinh viên như máy cũ.
- [ ] Tạo thử một bản ghi rồi xoá, để xác nhận ghi được dữ liệu.

Kiểm trạng thái container:

```powershell
.\scripts\windows\dc.ps1 ps          # tất cả phải (healthy)
docker stats --no-stream             # RAM từng container
```

### D2. Cài backup tự động — làm ngay trong ngày *(DW §7.1)*

```powershell
# Chạy thử
.\scripts\windows\lims-backup.ps1 -Dest D:\lims-backup -RemotePath \\nas\backup\lims
```

Rồi đặt lịch chạy 02:00 hằng ngày theo đoạn lệnh `Register-ScheduledTask` ở *DW §7.1*.
Kiểm ngay bằng `Start-ScheduledTask -TaskName 'LIMS Backup'`; `LastTaskResult` phải
bằng `0`.

> Nên có `-RemotePath` trỏ sang **ổ / máy khác**. Backup nằm chung ổ với dữ liệu thì
> hỏng ổ là mất cả hai.

### D3. Kiểm khả năng tự phục hồi *(DW §6.3)*

Khởi động lại máy Windows một lần. Sau khi đăng nhập, đợi khoảng 2 phút: ribe.com.vn
phải tự chạy lại mà không cần làm gì.

### D4. Dọn dẹp

- [ ] Xoá `lims-export.7z` và thư mục `lims-export` ở **mọi nơi** đã chép qua: máy cũ
      (`~/lims-export`, `~/lims-export.7z`), USB, Drive/Zalo, và `D:\lims-export` trên máy
      mới. Các bản này chứa toàn bộ mật khẩu.
- [ ] Vô hiệu hoá các **tài khoản thử** (mật khẩu `Lims@1234`) trong **Quản trị → Tài
      khoản**, nếu chưa làm trước khi xuất (xem đầu mục C).
- [ ] Đổi mật khẩu tài khoản quản trị mặc định, nếu vẫn còn dùng.
- [ ] Bàn giao cho khách: tài khoản quản trị, vị trí thư mục backup, tài liệu này.

### Checklist bàn giao

- [ ] `dc.ps1 ps`: mọi container `(healthy)`.
- [ ] ribe.com.vn vào được từ mạng ngoài (dùng 4G điện thoại).
- [ ] Tệp đính kèm mở được.
- [ ] Backup tự động đã chạy thử, `LastTaskResult = 0`.
- [ ] Đã thử khởi động lại máy → hệ thống tự lên.
- [ ] Tài khoản thử đã vô hiệu hoá.
- [ ] Gói xuất dữ liệu (`lims-export`, `lims-export.7z`) đã xoá ở mọi nơi.
- [ ] Máy cũ đã tắt, nhưng **chưa xoá**.

---

## E. Nếu có sự cố — quay về máy cũ

Máy cũ vẫn còn nguyên dữ liệu tại thời điểm xuất.

```powershell
# Máy Windows: tắt tunnel
.\scripts\windows\dc.ps1 stop cloudflared
```

```bash
# Máy cũ (Linux): bật lại
docker start lims-api lims-cloudflared
```

> ⚠️ Dữ liệu người dùng nhập **trên máy Windows** sau khi chuyển sẽ **không có** trên
> máy cũ. Chỉ quay về trong vài giờ đầu, nếu phát hiện lỗi nghiêm trọng.

---

## F. Vận hành hằng ngày trên máy khách

Luôn dùng `dc.ps1` thay cho `docker compose` trần. Gõ `docker compose` trần sẽ nạp
nhầm hồ sơ dev *(DW §5.3)*.

```powershell
cd C:\lims
.\scripts\windows\dc.ps1 ps                       # trạng thái
.\scripts\windows\dc.ps1 logs -f lims-api         # xem log backend
.\scripts\windows\dc.ps1 restart lims-api         # khởi động lại backend
.\scripts\windows\dc.ps1 down                     # dừng (TUYỆT ĐỐI không thêm -v: -v xoá dữ liệu)
.\scripts\windows\dc.ps1 up -d                    # chạy lại
```

### Cập nhật phiên bản mới *(DW §7.4)*

```powershell
cd C:\lims
.\scripts\windows\lims-backup.ps1 -Dest D:\lims-backup   # backup TRƯỚC, luôn luôn
git pull
.\scripts\windows\preflight-deploy.ps1
.\scripts\windows\dc.ps1 up -d --build
```

Migration database tự chạy trước khi backend khởi động.

### Lỗi thường gặp

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `running scripts is disabled` | Chưa mở khoá PowerShell | Bước A3; hoặc `Get-ChildItem -Recurse scripts\windows\*.ps1 \| Unblock-File` |
| Container không khởi động, báo về `cpus` | Docker có < 2 nhân | Tăng `processors=` trong `.wslconfig`, hoặc đặt `LIMS_API_CPUS=1` |
| Container tự restart liên tục, log không có lỗi | Docker thiếu RAM | Tăng `memory=` trong `.wslconfig`, rồi `wsl --shutdown` |
| `exec /app/entrypoint.sh: no such file or directory` | File bị đổi sang CRLF | Clone lại theo B1 (đặt `core.autocrlf false` **trước**) |
| Web vào được, tệp đính kèm không tải được | Kho tệp chưa chạy | `dc.ps1 ps` xem `lims-minio`; `dc.ps1 logs lims-minio` |
| Người dùng lúc thấy dữ liệu mới, lúc thấy cũ | **Hai máy cùng bật tunnel** | Tắt ngay `lims-cloudflared` trên máy cũ |

Danh sách đầy đủ: *DW §8*.
