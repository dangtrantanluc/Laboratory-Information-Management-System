# Runbook: Sao lưu & khôi phục LIMS trên Windows

Dành cho máy Windows 10/11 chạy LIMS bằng Docker Desktop (xem
[DEPLOY_WINDOWS.md](../DEPLOY_WINDOWS.md)). Bản Linux: [RUNBOOK.md](./RUNBOOK.md).

Tài liệu này trả lời bốn câu, theo thứ tự quan trọng: **sao lưu cái gì**, **làm sao
biết nó thật sự chạy**, **làm sao biết nó thật sự khôi phục được**, và **khôi phục
như thế nào khi có sự cố**.

> Nguyên tắc xuyên suốt: một bản backup chưa từng được khôi phục thử thì **chưa
> phải backup** — nó mới chỉ là một file có kích thước trông hợp lý. Mục 4 là mục
> quan trọng nhất tài liệu này.

---

## 1. Sao lưu cái gì — và cố ý không sao lưu cái gì

| Thành phần | Backup? | Lý do |
|---|---|---|
| **PostgreSQL** (`lims_pgdata`) | ✅ `db-<ts>.dump` | Toàn bộ dữ liệu nghiệp vụ: mẫu, kết quả, hoá chất, nhân sự, audit log |
| **MinIO** (`lims_miniodata`) | ✅ `files-<ts>.tar.gz` | File đính kèm: CoA, MSDS, SOP, phiếu PDF, ảnh đại diện |
| **`.env.prod`** | ✅ nhưng **để riêng** | Xem mục 6 — để chung với dump là trao trọn gói cho người nhặt được |
| **Redis** (`lims_redisdata`) | ❌ có chủ đích | Chỉ chứa jti denylist, khoá đăng nhập, cache RBAC, lock cron — đều dựng lại được. Mất Redis nghĩa là token đã đăng xuất sống lại **tới khi hết hạn tự nhiên**; `ACCESS_TOKEN_TTL_MINUTES=10` giới hạn thiệt hại xuống 10 phút. Redis đã bật AOF nên vẫn sống qua restart. |
| **Image Docker** | ❌ | Build lại từ mã nguồn. Đó là lý do image MinIO được ghim phiên bản. |
| **Mã nguồn** | ❌ | Đã ở git. Nhưng hãy chắc chắn **mọi thay đổi cục bộ đã push**. |
| **`ext4.vhdx` của WSL2** | ❌ **và đừng thử** | Copy file ổ đĩa ảo khi Docker đang chạy cho ra ảnh chụp **không nhất quán** — Postgres đang ghi dở. Nó trông như một bản backup, mount được, và hỏng theo cách chỉ lộ ra khi cần dùng. |

Ba thứ đầu là đủ để dựng lại hệ thống từ một máy trống.

---

## 2. Lịch, RPO và RTO

| Chỉ số | Giá trị hiện tại | Ý nghĩa |
|---|---|---|
| Tần suất | 02:00 hằng ngày | |
| **RPO** (mất tối đa bao nhiêu dữ liệu) | **24 giờ** | Sự cố lúc 01:00 làm mất toàn bộ việc nhập của ngày hôm trước |
| **RTO** (khôi phục mất bao lâu) | ~10–20 phút | Với khối dữ liệu hiện tại: DB ~780 KB, file ~25 MB |
| Giữ bản cũ | 14 ngày | `-KeepDays` |

**RPO 24 giờ có chấp nhận được không?** Đó là quyết định nghiệp vụ, không phải
quyết định kỹ thuật. Phòng thí nghiệm nhập kết quả cả ngày thì mất một ngày công
nhập liệu là thiệt hại thật. Muốn giảm, cách rẻ nhất là **thêm một lần chạy giữa
trưa** (mục 3.3) → RPO còn 12 giờ. Xuống dưới mức đó cần WAL archiving liên tục,
phức tạp hơn nhiều và nằm ngoài phạm vi tài liệu này.

Lưu ý về **ISO/IEC 17025 §8.4**: thời hạn lưu hồ sơ của phòng lab thường dài hơn
14 ngày rất nhiều. `-KeepDays 14` là chu kỳ **backup vận hành** (để khôi phục sự
cố), **không phải** cơ chế lưu trữ hồ sơ theo tiêu chuẩn. Nếu cần lưu dài hạn, hãy
tách riêng: mỗi tháng copy một bản ra kho lưu trữ và **không** để `-KeepDays` xoá.

---

## 3. Thiết lập

### 3.1 Chạy thử bằng tay trước

```powershell
cd C:\lims
.\scripts\windows\lims-backup.ps1 -Dest D:\lims-backup
```

Script tự kiểm ba thứ, và **dừng với mã thoát khác 0** nếu bất kỳ thứ nào sai:

- dump đọc được bằng `pg_restore --list` (header + mục lục còn nguyên);
- dump lớn hơn 1 KB;
- archive MinIO lớn hơn 1 KB — ngưỡng này bắt đúng lỗi *trỏ nhầm volume*, vì tar
  rỗng chỉ khoảng 45 byte và vẫn được tạo ra "thành công".

Nó cũng **hỏi chính compose tên volume MinIO** thay vì đoán, vì tên volume mang
tiền tố tên project; hard-code `lims_miniodata` sẽ trỏ vào một volume rỗng khác.

> Script cố ý **không** dùng toán tử `>` của PowerShell để hứng dữ liệu nhị phân.
> PowerShell 5.1 ghi ra UTF-16LE, nên `pg_dump -Fc lims > db.dump` tạo ra file có
> kích thước rất hợp lý mà `pg_restore` không đọc nổi — và người ta thường chỉ
> phát hiện vào đúng ngày cần khôi phục. Thay vào đó: dump vào trong container rồi
> `docker cp` ra ngoài.

### 3.2 Đặt lịch bằng Task Scheduler

Mở PowerShell **quyền Administrator**:

```powershell
$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\lims\scripts\windows\lims-backup.ps1" -Dest "D:\lims-backup" -RemotePath "\\nas\backup\lims"'

$trigger = New-ScheduledTaskTrigger -Daily -At 2:00AM

# Phải chạy dưới CHÍNH tài khoản đang đăng nhập Docker Desktop. Tác vụ chạy dưới
# SYSTEM hoặc một tài khoản khác sẽ không thấy Docker và thất bại mỗi đêm.
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 15)

Register-ScheduledTask -TaskName 'LIMS Backup' `
    -Action $action -Trigger $trigger -Principal $principal -Settings $settings
```

`-StartWhenAvailable` để máy tắt lúc 2 giờ sáng thì tác vụ chạy bù khi bật lại.
`-RestartCount 2` để lần chạy trượt vì Docker Desktop chưa kịp lên sẽ được thử lại.

**Kiểm ngay, đừng đợi tới 2 giờ sáng:**

```powershell
Start-ScheduledTask -TaskName 'LIMS Backup'
Start-Sleep 90
Get-ScheduledTaskInfo -TaskName 'LIMS Backup' | Select LastRunTime, LastTaskResult
# LastTaskResult phải là 0
Get-ChildItem D:\lims-backup | Sort LastWriteTime -Desc | Select -First 4
```

> **Ràng buộc phải biết:** `-LogonType S4U` cho phép tác vụ chạy khi người dùng
> không đăng nhập, nhưng **Docker Desktop thì lại cần phiên đăng nhập**
> (DEPLOY_WINDOWS.md mục 1.6). Nếu máy dùng phương án tự đăng nhập + khoá màn hình
> thì backup chạy được. Nếu không có ai đăng nhập, Docker không chạy và backup sẽ
> thất bại với `LastTaskResult` khác 0 — đúng như mong muốn, vì đó chính là thông
> tin bạn cần biết, thay vì im lặng.

### 3.3 Thêm một lần chạy giữa trưa (tuỳ chọn, RPO 24h → 12h)

```powershell
$t2 = New-ScheduledTaskTrigger -Daily -At 12:30PM
$task = Get-ScheduledTask -TaskName 'LIMS Backup'
Set-ScheduledTask -TaskName 'LIMS Backup' -Trigger @($task.Triggers[0], $t2)
```

### 3.4 Quy tắc 3-2-1

Ba bản sao, hai loại phương tiện, **một bản ngoài máy**. Backup nằm cùng ổ với dữ
liệu gốc thì hỏng ổ là mất cả hai; nằm cùng **toà nhà** thì cháy/mất trộm cũng vậy.

| Bản | Ở đâu | Cách làm |
|---|---|---|
| 1 | `D:\lims-backup` trên chính máy | `-Dest` — khôi phục nhanh nhất |
| 2 | NAS / máy khác trong mạng | `-RemotePath \\nas\backup\lims` |
| 3 | Ngoài toà nhà | Ổ cứng rời luân phiên hằng tuần (cất khác phòng), hoặc đồng bộ thư mục `D:\lims-backup` lên OneDrive/Google Drive **của tổ chức** |

Nếu chưa đặt `-RemotePath`, script in cảnh báo vàng mỗi lần chạy — đó là cố ý.

---

## 4. Làm sao biết backup thật sự dùng được

Hai câu hỏi khác nhau, cần hai phép kiểm khác nhau.

### 4.1 "Backup có chạy không?" — kiểm hằng tuần

Task Scheduler báo thành công không có nghĩa là có file. Kiểm **tuổi của file mới
nhất**, vì đó mới là thứ bạn cần lúc sự cố:

```powershell
$newest = Get-ChildItem D:\lims-backup\db-*.dump | Sort LastWriteTime -Desc | Select -First 1
$age = (Get-Date) - $newest.LastWriteTime
if ($age.TotalHours -gt 30) {
    Write-Host "CANH BAO: ban backup moi nhat da $([int]$age.TotalHours) gio tuoi!" -ForegroundColor Red
} else {
    Write-Host "OK - ban moi nhat: $($newest.Name), $([int]$age.TotalHours) gio truoc" -ForegroundColor Green
}
```

Muốn tự động: đặt đoạn trên thành một tác vụ hằng tuần ghi vào Event Log
(`Write-EventLog`), rồi để hệ thống giám sát của đơn vị bắt sự kiện đó.

### 4.2 "Backup có khôi phục được không?" — diễn tập hằng tháng

Đây là phép kiểm thật sự. Chế độ **mặc định** của script khôi phục là diễn tập, và
nó **không đụng tới production**:

```powershell
cd C:\lims
.\scripts\windows\restore-backup.ps1
```

Việc nó làm:

1. giải nén **thật** archive file đính kèm ra `/dev/null` để đếm số mục — `gzip -t`
   chỉ kiểm checksum gzip, không phát hiện tar bị cụt đuôi;
2. khôi phục dump vào một database riêng tên `lims_drill`;
3. đếm số bảng, số người dùng, đọc `alembic_version`, và **so số người dùng với
   production hiện tại** — chênh lệch lớn cho bạn biết ngay bản backup cũ tới mức nào;
4. xoá `lims_drill`, dọn file tạm.

Kết quả mong đợi:

```
[restore] OK  archive doc duoc — 728 muc
[restore] OK  dien tap thanh cong
     bang            : 69
     nguoi dung      : 10   (production hien tai: 10)
     alembic_version : 1718870400032
```

Script **không tin vào mã thoát của `pg_restore`** — lệnh đó luôn phàn nàn về owner
và extension do superuser tạo, nên mã thoát khác 0 là chuyện bình thường. Bằng chứng
được dùng là **số bản ghi thật**; bảng `users` rỗng là báo lỗi và dừng.

Xem có những bản nào, bản nào thiếu vế:

```powershell
.\scripts\windows\restore-backup.ps1 -List
```

```
Thoi diem                      DB        Files  Trang thai
------------------------------------------------------------------
2026-08-12_0200            957 KB     3,027 KB  du cap
2026-08-11_0200            928 KB            -  THIEU file dinh kem
```

Bản "THIEU file dinh kem" nghĩa là đêm đó archive MinIO thất bại. Khôi phục bản đó
sẽ cho DB đúng nhưng file đính kèm còn nguyên của hiện tại — trạng thái lệch.

---

## 5. Khôi phục — bốn tình huống

Trước khi làm bất cứ điều gì: **xác định bạn đang ở tình huống nào**. Dùng nhầm
công cụ cho tình huống A (khôi phục toàn bộ vì xoá nhầm 3 bản ghi) là cách biến một
sự cố nhỏ thành mất trọn một ngày dữ liệu.

### Tình huống A — Người dùng xoá/sửa nhầm vài bản ghi

**Đừng** khôi phục toàn bộ. Lấy dữ liệu ra từ bản diễn tập:

```powershell
# Dung DB dien tap lam nguon doc, KHONG dong vao production
.\scripts\windows\dc.ps1 cp D:\lims-backup\db-2026-08-12_0200.dump postgres:/tmp/r.dump
.\scripts\windows\dc.ps1 exec postgres createdb -U lims lims_drill
.\scripts\windows\dc.ps1 exec postgres pg_restore -U lims -d lims_drill --no-owner /tmp/r.dump

# Xem ban ghi can lay
.\scripts\windows\dc.ps1 exec postgres psql -U lims -d lims_drill -c "SELECT * FROM samples WHERE id = 123;"

# Chep sang production — mot bang, mot dieu kien, khong hon
.\scripts\windows\dc.ps1 exec postgres psql -U lims -d lims -c `
  "INSERT INTO samples SELECT * FROM dblink('dbname=lims_drill','SELECT * FROM samples WHERE id=123') AS t(...);"

# Don
.\scripts\windows\dc.ps1 exec postgres dropdb -U lims lims_drill
.\scripts\windows\dc.ps1 exec postgres rm -f /tmp/r.dump
```

Nếu `dblink` chưa có, cách đơn giản hơn là `pg_dump` riêng bảng đó từ `lims_drill`
ra file SQL rồi đọc, sửa tay, và chạy `INSERT` thủ công. Với vài bản ghi thì làm tay
an toàn hơn tự động.

> Lưu ý audit log (§8.4): bảng audit là **append-only**. Đừng xoá dòng audit để "dọn
> cho sạch" sau khi khôi phục — chính việc khôi phục cũng là một sự kiện cần ghi lại.

### Tình huống B — DB hỏng, migration sai, hoặc cần quay lui cả hệ thống

```powershell
# 1. Xem co nhung ban nao
.\scripts\windows\restore-backup.ps1 -List

# 2. Dien tap ban dinh dung TRUOC (mat them 2 phut, tranh mot sai lam khong sua duoc)
.\scripts\windows\restore-backup.ps1 -Timestamp 2026-08-12_0200

# 3. Khoi phuc that
.\scripts\windows\restore-backup.ps1 -Timestamp 2026-08-12_0200 -Full
```

Bước 3 sẽ, theo thứ tự:

1. hỏi bạn gõ đúng chữ `KHOI PHUC` — không có cờ `-y` nào bỏ qua được;
2. **tự backup trạng thái hiện tại trước khi đè** (`-KeepDays 999`, không bị dọn) —
   đây là đường lui nếu bạn chọn nhầm bản, và nếu bước này thất bại thì script
   **dừng lại** thay vì đè tiếp;
3. dừng `lims-api` và `cloudflared` để người dùng nhận lỗi kết nối rõ ràng thay vì
   gặp một hệ thống đang thay dữ liệu dưới chân họ;
4. `pg_restore --clean --if-exists` rồi **đếm số người dùng** — rỗng là dừng, và
   **không** khởi động lại `lims-api`;
5. dừng MinIO, **xoá trắng** kho file rồi giải nén lại từ archive;
6. bật lại MinIO, `lims-api`, `cloudflared`, chờ `/health/ready` xanh.

> Bước 5 xoá trắng chứ không giải nén chồng lên, và đó là chủ ý. Giải nén chồng chỉ
> ghi đè tệp trùng tên, nên **tệp bị xoá sau thời điểm backup sẽ sống lại** — kết
> quả là một trạng thái chưa từng tồn tại: không phải kho file của đêm đó, cũng
> không phải của hiện tại.

### Tình huống C — Chỉ mất file đính kèm (DB vẫn đúng)

```powershell
.\scripts\windows\restore-backup.ps1 -Timestamp 2026-08-12_0200 -Full -FilesOnly
```

Ngược lại, DB hỏng nhưng file còn tốt: `-DbOnly`.

Hai cờ này tạo ra trạng thái **lệch** giữa DB và kho file (bản ghi trỏ tới tệp
không có, hoặc tệp mồ côi), nên script in cảnh báo riêng. Chỉ dùng khi bạn biết
chắc vế còn lại vẫn đúng.

### Tình huống D — Mất cả máy Windows

1. Dựng máy mới theo [DEPLOY_WINDOWS.md](../DEPLOY_WINDOWS.md) **GIAI ĐOẠN 1–2**
   (WSL2, Docker Desktop, clone mã nguồn).
2. Lấy `.env.prod` từ nơi cất giữ riêng (mục 6). **Không có file này thì dump vô
   dụng** — `POSTGRES_PASSWORD` phải khớp lúc `initdb`, và mất `JWT_SECRET` là mọi
   phiên đăng nhập hỏng.
3. Copy bản backup mới nhất về `D:\lims-backup`.
4. Dựng stack rỗng rồi khôi phục:

```powershell
cd C:\lims
.\scripts\windows\preflight-deploy.ps1
.\scripts\windows\dc.ps1 up -d --build
.\scripts\windows\restore-backup.ps1 -Full -SkipSafetyBackup
```

`-SkipSafetyBackup` ở đây là hợp lý và **chỉ** ở đây: hệ thống vừa dựng còn trống,
không có gì để lưu lại.

5. Nghiệm thu theo DEPLOY_WINDOWS.md mục 6.2 (5 việc).

> Nếu tunnel Cloudflare vẫn dùng token cũ thì tên miền tự hoạt động trở lại, không
> phải sửa DNS. Nhớ nguyên tắc: **chỉ một máy được chạy `cloudflared` tại một thời
> điểm** — nếu máy cũ còn sống, dừng nó trước.

---

## 6. Bảo mật bản backup

Bản dump **là** cơ sở dữ liệu — chỉ khác ở chỗ nó nằm ngoài mọi lớp phân quyền của
ứng dụng.

| Nội dung trong bản backup | Hệ quả nếu lộ |
|---|---|
| Hash mật khẩu người dùng (bcrypt) | Đủ để tấn công offline lên mật khẩu yếu |
| Thông tin nhân sự, hợp đồng, lương (M4) | Dữ liệu cá nhân |
| Kết quả thử nghiệm của khách hàng (M1) | Vi phạm bảo mật thông tin khách hàng — 17025 §4.2 |
| Audit log | Toàn bộ dấu vết hoạt động |

Yêu cầu tối thiểu:

- **Ổ chứa backup bật BitLocker.** Ổ rời mang ra khỏi toà nhà thì đây là bắt buộc,
  không phải khuyến nghị.
- **Giới hạn quyền thư mục** — chỉ tài khoản quản trị:

```powershell
icacls D:\lims-backup /inheritance:r `
    /grant:r "$env:USERNAME:(OI)(CI)F" `
    /grant:r "Administrators:(OI)(CI)F"
```

- **Cất `.env.prod` TÁCH KHỎI dump.** Nếu để chung một thư mục, người nhặt được ổ
  đĩa có đủ cả dữ liệu lẫn chìa khoá. Nơi cất hợp lý: trình quản lý mật khẩu của
  đơn vị, hoặc phong bì niêm phong trong két — kèm ghi chú ngày tạo và ai giữ.
- **Sao lưu lên cloud thì mã hoá trước.** 7-Zip AES-256:

```powershell
& "C:\Program Files\7-Zip\7z.exe" a -t7z -p -mhe=on `
    D:\lims-backup-encrypted\lims-2026-08-12.7z D:\lims-backup\db-2026-08-12_0200.dump
```

---

## 7. Backup trước mỗi lần thay đổi

Ngoài lịch hằng ngày, chạy backup **thủ công ngay trước** những việc sau — mất
2 phút, và là khác biệt giữa "quay lui được" với "không":

```powershell
.\scripts\windows\lims-backup.ps1 -Dest D:\lims-backup
```

- trước `git pull` + `up -d --build` (mã mới có thể mang migration mới);
- trước khi nhập dữ liệu hàng loạt;
- trước khi sửa cấu hình `.env.prod`;
- trước khi cập nhật Docker Desktop hoặc Windows lớn;
- trước khi tự tay chạy `UPDATE`/`DELETE` trên DB.

Migration của LIMS chạy ở service `lims-migrate` riêng và **không có đường tự động
quay lui** — Alembic downgrade không được kiểm thử cho dự án này. Bản backup trước
khi `up -d --build` chính là cơ chế quay lui.

---

## 8. Danh sách kiểm

**Thiết lập lần đầu**

- [ ] `lims-backup.ps1` chạy tay ra đủ hai file, kích thước hợp lý
- [ ] Tác vụ "LIMS Backup" đã đăng ký, chạy thử `LastTaskResult = 0`
- [ ] `-RemotePath` trỏ tới đích **ngoài máy này** và ghi được
- [ ] Có phương án cho bản thứ 3 ngoài toà nhà
- [ ] `D:\lims-backup` bật BitLocker, đã giới hạn quyền
- [ ] `.env.prod` cất **tách riêng**, có ghi chú ngày tạo và người giữ
- [ ] Đã diễn tập khôi phục **một lần** và số bản ghi khớp

**Hằng tuần**

- [ ] Bản backup mới nhất dưới 30 giờ tuổi (mục 4.1)
- [ ] `-List` không có bản nào "THIEU"
- [ ] Đích off-site có file mới

**Hằng tháng**

- [ ] `restore-backup.ps1` (diễn tập) chạy sạch, số người dùng khớp production
- [ ] Ổ đĩa còn đủ chỗ cho 14 ngày backup
- [ ] Nếu cần lưu hồ sơ dài hạn: đã tách một bản của tháng ra kho lưu trữ

**Hằng năm**

- [ ] Diễn tập tình huống D (mất cả máy) trên một máy khác — đây là phép kiểm duy
      nhất chứng minh `.env.prod` đang cất giữ vẫn đúng và vẫn tìm lại được
