<#
.SYNOPSIS
    Sao lưu LIMS (PostgreSQL + MinIO) trên Windows. Bản tương đương ops/backup/lims-backup.sh.

.DESCRIPTION
    Thoát khác 0 nếu có bất kỳ lỗi nào, để Task Scheduler báo "Last Run Result"
    khác 0x0. Backup im lặng thất bại là backup vô dụng đúng lúc cần nhất.

    Không dùng toán tử '>' của PowerShell để hứng dữ liệu nhị phân từ container.
    PowerShell 5.1 ghi ra UTF-16LE, nên `docker compose exec -T postgres pg_dump -Fc
    lims > db.dump` tạo ra file có kích thước trông rất hợp lý nhưng pg_restore
    không đọc nổi — và người ta thường chỉ phát hiện ra vào ngày cần khôi phục.
    Thay vào đó: dump vào trong container rồi `docker cp` ra ngoài.

.PARAMETER Dest
    Thư mục lưu backup. Mặc định D:\lims-backup, không có thì C:\lims-backup.

.PARAMETER KeepDays
    Số ngày giữ bản cũ. Mặc định 14.

.PARAMETER RemotePath
    Thư mục thứ hai để nhân bản (ổ ngoài, share mạng \\NAS\lims). Backup nằm cùng
    ổ với dữ liệu gốc thì hỏng ổ là mất cả hai.

.EXAMPLE
    .\scripts\windows\lims-backup.ps1 -Dest D:\lims-backup -RemotePath \\nas\backup\lims
#>
[CmdletBinding()]
param(
    [string]$Dest,
    [int]$KeepDays = 14,
    [string]$RemotePath = '',
    [string]$LimsDir = ''
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

# Chạy từ Task Scheduler thì thư mục hiện hành là C:\Windows\System32, nên phải
# tự xác định gốc dự án chứ không dựa vào nơi được gọi.
if ([string]::IsNullOrWhiteSpace($LimsDir)) {
    $LimsDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}
Set-Location -LiteralPath $LimsDir

if ([string]::IsNullOrWhiteSpace($Dest)) {
    $Dest = if (Test-Path 'D:\') { 'D:\lims-backup' } else { 'C:\lims-backup' }
}

$Ts   = Get-Date -Format 'yyyy-MM-dd_HHmm'
$Fail = 0
function Say { param($m) Write-Host "[lims-backup $(Get-Date -Format 'HH:mm:ss')] $m" }
function Die { param($m) Write-Host "[lims-backup] LOI: $m" -ForegroundColor Red; exit 1 }

Say "thu muc du an: $LimsDir"
Say "thu muc backup: $Dest"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null

# Hồ sơ compose chỉ định TƯỜNG MINH. `docker compose` trần sẽ nạp
# docker-compose.yml (hồ sơ DEV) nếu vì lý do gì đó COMPOSE_FILE không được đọc,
# và khi đó backup trỏ nhầm stack mà vẫn báo thành công.
$Compose = @('compose', '-f', 'docker-compose.prod.yml', '-f', 'docker-compose.cloudflare.yml',
             '--env-file', '.env.prod')

$running = & docker $Compose ps --status running --services 2>$null
if ($LASTEXITCODE -ne 0) { Die "khong chay duoc docker compose — Docker Desktop da khoi dong chua?" }
if ($running -notcontains 'postgres') { Die "container postgres khong chay — khong dump duoc" }

# ── PostgreSQL ───────────────────────────────────────────────────────────────
$DbFile = Join-Path $Dest "db-$Ts.dump"
Say "dump PostgreSQL..."
& docker $Compose exec -T postgres sh -c 'pg_dump -U lims -Fc lims > /tmp/lims-backup.dump'
if ($LASTEXITCODE -ne 0) { Die "pg_dump that bai" }
& docker $Compose cp postgres:/tmp/lims-backup.dump $DbFile
$cpCode = $LASTEXITCODE
& docker $Compose exec -T postgres rm -f /tmp/lims-backup.dump *> $null
if ($cpCode -ne 0) { Die "docker cp dump ra host that bai" }

# Dump hỏng mà không biết còn tệ hơn không có dump. pg_restore --list đọc được
# nghĩa là header + muc luc con nguyen ven. Chạy trong container để không cần cài
# công cụ Postgres trên Windows.
$DbSize = (Get-Item -LiteralPath $DbFile).Length
if ($DbSize -lt 1024) { Die "dump chi $DbSize byte" }
& docker $Compose cp $DbFile postgres:/tmp/verify.dump *> $null
& docker $Compose exec -T postgres pg_restore --list /tmp/verify.dump *> $null
$verifyCode = $LASTEXITCODE
& docker $Compose exec -T postgres rm -f /tmp/verify.dump *> $null
if ($verifyCode -ne 0) { Die "db-$Ts.dump khong doc duoc bang pg_restore — dump hong" }
Say ("  db-$Ts.dump — {0:N0} KB, pg_restore --list OK" -f ($DbSize / 1KB))

# ── MinIO ────────────────────────────────────────────────────────────────────
# Hỏi chính compose tên volume thay vì đoán: hard-code 'lims_miniodata' sẽ trỏ vào
# một volume RỖNG khác và tạo ra bản backup 0 byte mà vẫn báo thành công.
$cfgJson  = & docker $Compose config --format json
$MinioVol = ($cfgJson | ConvertFrom-Json).volumes.lims_miniodata.name
if ([string]::IsNullOrWhiteSpace($MinioVol)) { Die "khong xac dinh duoc ten volume MinIO" }
Say "archive MinIO (volume: $MinioVol)..."

$TarFile = Join-Path $Dest "files-$Ts.tar.gz"
$helper  = "lims-backup-helper-$Ts"
& docker rm -f $helper *> $null
& docker create --name $helper -v "${MinioVol}:/data:ro" alpine `
    sh -c 'tar czf /tmp/files.tar.gz -C /data . && echo TAR_OK' *> $null
if ($LASTEXITCODE -ne 0) { Die "khong tao duoc container phu tro" }
$tarOut  = & docker start -a $helper 2>&1
$tarCode = $LASTEXITCODE
if ($tarCode -eq 0 -and $tarOut -match 'TAR_OK') {
    & docker cp "${helper}:/tmp/files.tar.gz" $TarFile
    $cpCode = $LASTEXITCODE
} else { $cpCode = 1 }
& docker rm -f $helper *> $null
if ($cpCode -ne 0) { Die "archive MinIO that bai: $tarOut" }

$FileSize = (Get-Item -LiteralPath $TarFile).Length
# tar rỗng ~45 byte. Ngưỡng 1KB bắt đúng lỗi "trỏ nhầm volume".
if ($FileSize -lt 1024) { Die "archive MinIO chi $FileSize byte — sai volume?" }
Say ("  files-$Ts.tar.gz — {0:N0} KB" -f ($FileSize / 1KB))

# ── Dọn bản cũ ───────────────────────────────────────────────────────────────
$cutoff = (Get-Date).AddDays(-$KeepDays)
$old = Get-ChildItem -LiteralPath $Dest -File |
       Where-Object { ($_.Name -like 'db-*.dump' -or $_.Name -like 'files-*.tar.gz') -and $_.LastWriteTime -lt $cutoff }
if ($old) {
    $old | Remove-Item -Force
    Say "xoa $($old.Count) file cu hon $KeepDays ngay"
}

# ── Đưa ra khỏi máy ──────────────────────────────────────────────────────────
if (-not [string]::IsNullOrWhiteSpace($RemotePath)) {
    Say "nhan ban sang $RemotePath..."
    try {
        New-Item -ItemType Directory -Force -Path $RemotePath | Out-Null
        Copy-Item -LiteralPath $DbFile, $TarFile -Destination $RemotePath -Force
        Get-ChildItem -LiteralPath $RemotePath -File |
            Where-Object { ($_.Name -like 'db-*.dump' -or $_.Name -like 'files-*.tar.gz') -and $_.LastWriteTime -lt $cutoff } |
            Remove-Item -Force
        Say "  xong"
    } catch {
        # Không Die: bản cục bộ ĐÃ có và hợp lệ. Nhưng vẫn phải thoát khác 0 để
        # Task Scheduler báo lỗi, vì mất bản off-site là một sự cố thật.
        Write-Host "[lims-backup] LOI: khong nhan ban duoc sang ${RemotePath}: $($_.Exception.Message)" -ForegroundColor Red
        $Fail = 1
    }
} else {
    Write-Host "[lims-backup] CANH BAO: chua dat -RemotePath — backup CHI nam tren may nay" -ForegroundColor Yellow
}

Say "HOAN TAT $Ts"
exit $Fail
