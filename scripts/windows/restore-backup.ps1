<#
.SYNOPSIS
    Khôi phục LIMS từ bản backup hằng ngày do lims-backup.ps1 tạo ra.

.DESCRIPTION
    Backup chưa từng được khôi phục thử thì chưa phải backup — nó mới chỉ là một
    file có kích thước hợp lý. Script này có ba chế độ, và chế độ MẶC ĐỊNH là chế
    độ an toàn:

      (không cờ)  DIỄN TẬP  — khôi phục vào một database riêng tên lims_drill,
                              đếm bản ghi, rồi xoá. KHÔNG đụng tới production.
                              Chạy mỗi tháng một lần.
      -Full       KHÔI PHỤC THẬT — đè lên production. Hỏi xác nhận bằng cách gõ
                              chữ, và tự backup trạng thái hiện tại trước khi đè.
      -List       Liệt kê các bản backup đang có, đánh dấu bản nào thiếu vế.

    Mặc định là diễn tập chứ không phải khôi phục thật, vì lệnh gõ nhầm lúc 3 giờ
    sáng trong sự cố không được phép có hậu quả là mất nốt dữ liệu còn lại.

.PARAMETER BackupDir
    Thư mục chứa db-*.dump và files-*.tar.gz. Mặc định D:\lims-backup, không có thì
    C:\lims-backup.

.PARAMETER Timestamp
    Chọn bản cụ thể, dạng 2026-08-12_0200. Bỏ trống = bản mới nhất.

.PARAMETER Full
    Khôi phục ĐÈ LÊN PRODUCTION. Có hỏi xác nhận.

.PARAMETER DbOnly
    Chỉ khôi phục Postgres, giữ nguyên kho file. Dùng khi DB hỏng nhưng file vẫn tốt.

.PARAMETER FilesOnly
    Chỉ khôi phục kho file MinIO, giữ nguyên Postgres. Dùng khi lỡ xoá file đính kèm.

    Hai cờ này tạo ra trạng thái LỆCH giữa DB và kho file — bản ghi trỏ tới tệp
    không tồn tại, hoặc tệp mồ côi. Chỉ dùng khi bạn biết rõ vế còn lại vẫn đúng.

.PARAMETER SkipSafetyBackup
    Bỏ qua bước tự backup trước khi đè. Chỉ dùng khi ổ đĩa đã đầy và bạn chấp nhận
    mất đường lui.

.EXAMPLE
    .\scripts\windows\restore-backup.ps1 -List
.EXAMPLE
    .\scripts\windows\restore-backup.ps1
.EXAMPLE
    .\scripts\windows\restore-backup.ps1 -Timestamp 2026-08-12_0200 -Full
#>
[CmdletBinding()]
param(
    [string]$BackupDir,
    [string]$Timestamp = '',
    [switch]$List,
    [switch]$Full,
    [switch]$DbOnly,
    [switch]$FilesOnly,
    [switch]$SkipSafetyBackup
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $RepoRoot

if ([string]::IsNullOrWhiteSpace($BackupDir)) {
    $BackupDir = if (Test-Path 'D:\lims-backup') { 'D:\lims-backup' } else { 'C:\lims-backup' }
}

function Say { param($m) Write-Host "[restore] $m" -ForegroundColor Cyan }
function Ok  { param($m) Write-Host "[restore] OK  $m" -ForegroundColor Green }
function Die { param($m) Write-Host "[restore] LOI $m" -ForegroundColor Red; exit 1 }

$Compose = @('compose', '-f', 'docker-compose.prod.yml', '-f', 'docker-compose.cloudflare.yml',
             '--env-file', '.env.prod')

if ($DbOnly -and $FilesOnly) { Die "-DbOnly va -FilesOnly loai tru nhau" }
if (($DbOnly -or $FilesOnly) -and -not $Full) {
    Die "-DbOnly / -FilesOnly chi co nghia kem -Full (che do dien tap luon kiem ca hai ve)"
}
if (-not (Test-Path -LiteralPath $BackupDir)) { Die "khong thay thu muc backup: $BackupDir" }

# ── Ghép cặp dump + archive theo dấu thời gian ───────────────────────────────
# Hai file của cùng một đêm phải đi cùng nhau. Khôi phục DB của đêm nay kèm file
# đính kèm của đêm khác sẽ tạo ra trạng thái chưa từng tồn tại: bản ghi trỏ tới
# tệp không có, hoặc tệp mồ côi không bản ghi nào trỏ tới.
$sets = @{}
foreach ($f in Get-ChildItem -LiteralPath $BackupDir -File) {
    if ($f.Name -match '^db-(.+)\.dump$')          { $ts = $Matches[1] }
    elseif ($f.Name -match '^files-(.+)\.tar\.gz$'){ $ts = $Matches[1] }
    else { continue }
    if (-not $sets.ContainsKey($ts)) { $sets[$ts] = @{ Ts = $ts; Db = $null; Files = $null } }
    if ($f.Name -like 'db-*')    { $sets[$ts].Db    = $f }
    else                         { $sets[$ts].Files = $f }
}
if ($sets.Count -eq 0) { Die "khong co ban backup nao trong $BackupDir" }
$ordered = $sets.Values | Sort-Object { $_.Ts } -Descending

if ($List) {
    Write-Host ""
    Write-Host "Ban backup trong $BackupDir" -ForegroundColor Cyan
    Write-Host ("{0,-20} {1,12} {2,12}  {3}" -f 'Thoi diem', 'DB', 'Files', 'Trang thai')
    Write-Host ("-" * 66)
    foreach ($s in $ordered) {
        $dbSz = if ($s.Db)    { '{0:N0} KB' -f ($s.Db.Length / 1KB) }    else { '-' }
        $flSz = if ($s.Files) { '{0:N0} KB' -f ($s.Files.Length / 1KB) } else { '-' }
        if ($s.Db -and $s.Files) { $st = 'du cap'; $c = 'Green' }
        elseif ($s.Db)           { $st = 'THIEU file dinh kem'; $c = 'Yellow' }
        else                     { $st = 'THIEU dump DB'; $c = 'Red' }
        Write-Host ("{0,-20} {1,12} {2,12}  {3}" -f $s.Ts, $dbSz, $flSz, $st) -ForegroundColor $c
    }
    Write-Host ""
    Write-Host "Dien tap ban moi nhat:  .\scripts\windows\restore-backup.ps1"
    exit 0
}

# ── Chọn bản ─────────────────────────────────────────────────────────────────
if ([string]::IsNullOrWhiteSpace($Timestamp)) {
    $pick = $ordered | Where-Object { $_.Db -and $_.Files } | Select-Object -First 1
    if (-not $pick) { Die "khong co ban nao du ca dump lan archive. Xem: -List" }
} else {
    if (-not $sets.ContainsKey($Timestamp)) { Die "khong thay ban $Timestamp. Xem: -List" }
    $pick = $sets[$Timestamp]
}
if (-not $pick.Db    -and -not $FilesOnly) { Die "ban $($pick.Ts) thieu dump DB. Chi khoi phuc file: them -FilesOnly" }
if (-not $pick.Files -and $FilesOnly)      { Die "ban $($pick.Ts) khong co archive file dinh kem" }
Say "ban backup: $($pick.Ts)"
Say "  $($pick.Db.Name)  ($('{0:N0}' -f ($pick.Db.Length / 1KB)) KB)"
if ($pick.Files) { Say "  $($pick.Files.Name)  ($('{0:N0}' -f ($pick.Files.Length / 1KB)) KB)" }
else             { Write-Host "[restore] !   ban nay KHONG co file dinh kem" -ForegroundColor Yellow }

$running = & docker $Compose ps --status running --services 2>$null
if ($LASTEXITCODE -ne 0) { Die "khong chay duoc docker compose — Docker Desktop da khoi dong chua?" }
if ($running -notcontains 'postgres') { Die "container postgres khong chay" }

# ═════════════════════════════════════════════════════════════════════════════
#  CHẾ ĐỘ DIỄN TẬP (mặc định)
# ═════════════════════════════════════════════════════════════════════════════
if (-not $Full) {
    Write-Host ""
    Say "CHE DO DIEN TAP — production khong bi dung toi"

    # 1. Kiểm tính toàn vẹn của archive file đính kèm bằng cách GIẢI NÉN THẬT ra
    #    /dev/null. `gzip -t` chỉ kiểm checksum gzip, không phát hiện tar cụt đuôi.
    if ($pick.Files) {
        Say "kiem archive file dinh kem..."
        $h = 'lims-drill-tar'
        & docker rm -f $h *> $null
        & docker create --name $h alpine sh -c 'tar tzf /tmp/f.tar.gz | wc -l' *> $null
        & docker cp $pick.Files.FullName "${h}:/tmp/f.tar.gz" *> $null
        $cnt = & docker start -a $h 2>&1
        $code = $LASTEXITCODE
        & docker rm -f $h *> $null
        if ($code -ne 0) { Die "archive hong, khong giai nen duoc: $cnt" }
        Ok "archive doc duoc — $(($cnt | Select-Object -Last 1).Trim()) muc"
    }

    # 2. Khôi phục DB vào một database riêng.
    Say "khoi phuc DB vao lims_drill..."
    & docker $Compose exec -T postgres dropdb -U lims --if-exists lims_drill *> $null
    & docker $Compose exec -T postgres createdb -U lims lims_drill
    if ($LASTEXITCODE -ne 0) { Die "khong tao duoc database lims_drill" }
    & docker $Compose cp $pick.Db.FullName postgres:/tmp/drill.dump
    if ($LASTEXITCODE -ne 0) { Die "docker cp dump vao container that bai" }
    & docker $Compose exec -T postgres pg_restore -U lims -d lims_drill --no-owner /tmp/drill.dump 2>&1 |
        Select-String -Pattern 'error|FATAL' -CaseSensitive:$false | Select-Object -First 5 |
        ForEach-Object { Write-Host "    $_" -ForegroundColor DarkYellow }

    # Bằng chứng thật, không tin mã thoát: pg_restore luôn phàn nàn về owner và
    # extension do superuser tạo, nên mã thoát khác 0 không có nghĩa là hỏng.
    $u = & docker $Compose exec -T postgres psql -U lims -d lims_drill -tAc 'SELECT count(*) FROM users;' 2>$null
    $a = & docker $Compose exec -T postgres psql -U lims -d lims_drill -tAc 'SELECT version_num FROM alembic_version;' 2>$null
    $t = & docker $Compose exec -T postgres psql -U lims -d lims_drill -tAc `
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>$null

    # So với production để thấy ngay bản backup đã cũ tới mức nào.
    $uProd = & docker $Compose exec -T postgres psql -U lims -d lims -tAc 'SELECT count(*) FROM users;' 2>$null

    & docker $Compose exec -T postgres dropdb -U lims lims_drill *> $null
    & docker $Compose exec -T postgres rm -f /tmp/drill.dump *> $null

    $uN = 0; [int]::TryParse(($u -replace '\D', ''), [ref]$uN) | Out-Null
    if ($uN -eq 0) { Die "bang users RONG sau khi khoi phuc — ban backup nay KHONG dung duoc" }

    Write-Host ""
    Ok "dien tap thanh cong"
    Write-Host "     bang            : $(($t | Out-String).Trim())"
    Write-Host "     nguoi dung      : $(($u | Out-String).Trim())   (production hien tai: $(($uProd | Out-String).Trim()))"
    Write-Host "     alembic_version : $(($a | Out-String).Trim())"
    Write-Host ""
    Write-Host "     Da xoa lims_drill. Production khong bi dung toi." -ForegroundColor DarkGray
    Write-Host "     Khoi phuc that:  .\scripts\windows\restore-backup.ps1 -Timestamp $($pick.Ts) -Full" -ForegroundColor DarkGray
    exit 0
}

# ═════════════════════════════════════════════════════════════════════════════
#  CHẾ ĐỘ KHÔI PHỤC THẬT
# ═════════════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "===============================================================" -ForegroundColor Red
Write-Host " KHOI PHUC DE LEN PRODUCTION" -ForegroundColor Red
Write-Host "===============================================================" -ForegroundColor Red
$scope = if ($DbOnly) { 'CHI Postgres (giu nguyen kho file)' }
         elseif ($FilesOnly) { 'CHI kho file MinIO (giu nguyen Postgres)' }
         else { 'Postgres VA kho file MinIO' }
Write-Host " Pham vi : $scope"
Write-Host " Ban     : $($pick.Ts)"
Write-Host ""
if (-not $FilesOnly) {
    Write-Host " Du lieu nghiep vu hien tai se bi thay bang ban $($pick.Ts)."
    Write-Host " Moi thay doi NGUOI DUNG NHAP SAU thoi diem do se mat vinh vien."
}
if ($pick.Files -and -not $DbOnly) {
    Write-Host " Kho file dinh kem se bi XOA TRANG roi dung lai tu archive —"
    Write-Host " tep tai len sau $($pick.Ts) cung se mat."
}
if ($DbOnly -or $FilesOnly) {
    Write-Host ""
    Write-Host " CANH BAO: khoi phuc mot ve tao ra trang thai LECH giua DB va kho file." -ForegroundColor Yellow
}
Write-Host ""
$ans = Read-Host " Go dung chu KHOI PHUC de xac nhan"
if ($ans -cne 'KHOI PHUC') { Die "huy bo — khong co gi bi thay doi" }

# ── Đường lui: backup trạng thái hiện tại TRƯỚC khi đè ───────────────────────
# Khôi phục nhầm bản, hoặc phát hiện bản backup cũ hơn mình tưởng, là chuyện có
# thật. Không có bước này thì sai lầm đó không thể sửa được nữa.
if (-not $SkipSafetyBackup) {
    Say "backup trang thai HIEN TAI truoc khi de (duong lui)..."
    & (Join-Path $PSScriptRoot 'lims-backup.ps1') -Dest $BackupDir -KeepDays 999
    if ($LASTEXITCODE -ne 0) {
        Die "backup an toan that bai — DUNG LAI. Chay lai kem -SkipSafetyBackup neu ban chap nhan mat duong lui."
    }
    Ok "da co ban luu truoc khi de"
}

# ── Dừng thứ ghi dữ liệu, giữ nguyên hạ tầng ─────────────────────────────────
# Dừng lims-api chứ không dừng cả stack: cần Postgres và MinIO còn sống để làm
# việc. Cũng dừng cloudflared để người dùng nhận lỗi kết nối rõ ràng thay vì gặp
# một hệ thống đang thay dữ liệu dưới chân họ.
Say "dung lims-api va cloudflared..."
& docker $Compose stop lims-api cloudflared *> $null

# ── Postgres ─────────────────────────────────────────────────────────────────
if ($FilesOnly) {
    Say "bo qua Postgres (-FilesOnly)"
} else {
Say "khoi phuc Postgres..."
& docker $Compose cp $pick.Db.FullName postgres:/tmp/restore.dump
if ($LASTEXITCODE -ne 0) { Die "docker cp dump that bai" }
& docker $Compose exec -T postgres pg_restore -U lims -d lims --clean --if-exists --no-owner /tmp/restore.dump 2>&1 |
    Select-String -Pattern 'error|FATAL' -CaseSensitive:$false | Select-Object -First 10 |
    ForEach-Object { Write-Host "    $_" -ForegroundColor DarkYellow }
& docker $Compose exec -T postgres rm -f /tmp/restore.dump *> $null

$u = & docker $Compose exec -T postgres psql -U lims -d lims -tAc 'SELECT count(*) FROM users;' 2>$null
$uN = 0; [int]::TryParse(($u -replace '\D', ''), [ref]$uN) | Out-Null
if ($uN -eq 0) { Die "bang users RONG sau khoi phuc. KHONG khoi dong lai lims-api. Xem log o tren." }
Ok "Postgres: $(($u | Out-String).Trim()) nguoi dung"
}

# ── MinIO ────────────────────────────────────────────────────────────────────
if ($pick.Files -and -not $DbOnly) {
    $cfgJson  = & docker $Compose config --format json
    $MinioVol = ($cfgJson | ConvertFrom-Json).volumes.lims_miniodata.name
    if ([string]::IsNullOrWhiteSpace($MinioVol)) { Die "khong xac dinh duoc ten volume MinIO" }

    Say "dung MinIO va khoi phuc kho file (volume: $MinioVol)..."
    & docker $Compose stop minio *> $null

    # XOÁ TRẮNG rồi mới giải nén, chứ không giải nén chồng lên. Giải nén chồng chỉ
    # ghi đè tệp trùng tên: tệp bị xoá sau thời điểm backup sẽ SỐNG LẠI, và trạng
    # thái thu được là một thứ chưa từng tồn tại — không phải DB của đêm đó, cũng
    # không phải kho file của đêm đó. `find -mindepth 1 -delete` chừa lại chính
    # thư mục /data (điểm gắn volume) và dọn cả .minio.sys.
    $h = 'lims-restore-files'
    & docker rm -f $h *> $null
    & docker create --name $h -v "${MinioVol}:/data" alpine `
        sh -c 'find /data -mindepth 1 -delete && tar xzf /tmp/f.tar.gz -C /data && echo TAR_OK' *> $null
    if ($LASTEXITCODE -ne 0) { Die "khong tao duoc container phu tro" }
    & docker cp $pick.Files.FullName "${h}:/tmp/f.tar.gz"
    if ($LASTEXITCODE -ne 0) { & docker rm -f $h *> $null; Die "docker cp archive that bai" }
    $out  = & docker start -a $h 2>&1
    $code = $LASTEXITCODE
    & docker rm -f $h *> $null
    if ($code -ne 0 -or ($out -notmatch 'TAR_OK')) {
        Die "giai nen that bai: $out — MinIO dang DUNG va kho file co the da bi xoa. Khoi phuc lai tu ban khac ngay."
    }
    & docker $Compose start minio *> $null
    Ok "kho file da khoi phuc"
}

# ── Bật lại ──────────────────────────────────────────────────────────────────
Say "khoi dong lai lims-api va cloudflared..."
& docker $Compose start lims-api cloudflared *> $null

Say "cho lims-api san sang..."
$ready = $false
foreach ($i in 1..40) {
    & docker $Compose exec -T lims-api curl -fsS http://localhost:8060/health/ready *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 3
}

Write-Host ""
if ($ready) { Ok "khoi phuc xong — /health/ready da xanh" }
else {
    Write-Host "[restore] !   lims-api chua san sang sau 2 phut." -ForegroundColor Yellow
    Write-Host "              Xem: .\scripts\windows\dc.ps1 logs -f lims-api" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Kiem bang tay truoc khi bao nguoi dung vao lai:" -ForegroundColor Cyan
Write-Host "  1. Dang nhap bang mot tai khoan that"
Write-Host "  2. Tai ve mot file dinh kem CU  (chung minh MinIO + presigned URL con dung)"
Write-Host "  3. Tai len mot file MOI          (chung minh quyen ghi)"
Write-Host "  4. Doi chieu mot con so tong (so mau / so nguoi dung) voi ky vong"
