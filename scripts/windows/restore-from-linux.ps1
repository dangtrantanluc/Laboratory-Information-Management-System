<#
.SYNOPSIS
    Khôi phục dữ liệu LIMS (Postgres + MinIO) từ gói do scripts/export-for-windows.sh tạo.

.DESCRIPTION
    Chạy MỘT LẦN trên máy Windows đích, sau khi đã copy mã nguồn và gói dữ liệu sang.

    Toàn bộ thao tác đi qua `docker cp` và volume có tên, KHÔNG mount thư mục host.
    Đây là lựa chọn có chủ đích: `docker run -v "C:\duong\dan:/backup"` trên Windows
    vướng dấu ':' của ký tự ổ đĩa và phụ thuộc thiết lập File Sharing của Docker
    Desktop, hỏng theo những kiểu rất khó đoán. Còn `docker cp` thì không đụng tới
    lớp chia sẻ file nào.

    Cũng vì vậy script này KHÔNG dùng toán tử '>' của PowerShell để hứng dữ liệu
    nhị phân: PowerShell 5.1 ghi ra UTF-16LE và sẽ làm hỏng file dump — dump hỏng
    theo kiểu vẫn tạo ra file, vẫn có kích thước hợp lý, chỉ là không restore được.

.PARAMETER BundlePath
    Thư mục chứa db.dump, minio-files.tar.gz, env.prod, SHA256SUMS.txt.

.PARAMETER Fresh
    XOÁ volume dữ liệu hiện có trước khi khôi phục. Có hỏi xác nhận.

.EXAMPLE
    .\scripts\windows\restore-from-linux.ps1 -BundlePath D:\lims-export-2026-08-12_1430
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BundlePath,
    [switch]$Fresh
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

function Say  { param($m) Write-Host "[restore] $m" -ForegroundColor Cyan }
function Ok   { param($m) Write-Host "[restore] OK  $m" -ForegroundColor Green }
function Die  { param($m) Write-Host "[restore] LOI $m" -ForegroundColor Red; exit 1 }

$Bundle = (Resolve-Path -LiteralPath $BundlePath).Path
$Dump   = Join-Path $Bundle 'db.dump'
$Tar    = Join-Path $Bundle 'minio-files.tar.gz'
$EnvSrc = Join-Path $Bundle 'env.prod'
foreach ($f in @($Dump, $Tar, $EnvSrc)) {
    if (-not (Test-Path -LiteralPath $f)) { Die "thieu $f trong goi du lieu" }
}
Say "goi du lieu: $Bundle"

# ── 1. Kiểm toàn vẹn ─────────────────────────────────────────────────────────
# Copy qua USB/mạng có thể cắt cụt file. Phát hiện ở đây rẻ hơn nhiều so với phát
# hiện sau khi đã restore được một nửa vào DB.
$Sums = Join-Path $Bundle 'SHA256SUMS.txt'
if (Test-Path -LiteralPath $Sums) {
    Say "kiem sha256..."
    $bad = 0
    foreach ($line in (Get-Content -LiteralPath $Sums)) {
        if ($line -notmatch '^([0-9a-fA-F]{64})\s+\*?(.+)$') { continue }
        $want = $Matches[1].ToLower(); $name = $Matches[2].Trim()
        $path = Join-Path $Bundle $name
        if (-not (Test-Path -LiteralPath $path)) { Write-Host "  thieu $name" -ForegroundColor Red; $bad = 1; continue }
        $got = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower()
        if ($got -ne $want) { Write-Host "  SAI  $name" -ForegroundColor Red; $bad = 1 }
        else                { Write-Host "  ok   $name" -ForegroundColor DarkGray }
    }
    if ($bad) { Die "checksum khong khop — copy lai goi du lieu" }
    Ok "sha256 khop"
} else {
    Write-Host "[restore] !   khong co SHA256SUMS.txt — bo qua kiem toan ven" -ForegroundColor Yellow
}

# ── 2. .env.prod ─────────────────────────────────────────────────────────────
$EnvDst = Join-Path $RepoRoot '.env.prod'
if (Test-Path -LiteralPath $EnvDst) {
    Say ".env.prod da co san — GIU NGUYEN (khong ghi de)"
} else {
    # Ghi UTF-8 KHONG BOM. Có BOM thì compose đọc khoá đầu tiên thành
    # "<U+FEFF>COMPOSE_PATH_SEPARATOR" và lặng lẽ bỏ qua nó.
    $content = [System.IO.File]::ReadAllText($EnvSrc)
    [System.IO.File]::WriteAllText($EnvDst, $content, (New-Object System.Text.UTF8Encoding $false))
    Ok "tao .env.prod tu goi du lieu"
}

# Đọc lại tên project — quyết định tên volume sẽ khôi phục vào.
$proj = 'lims'
foreach ($line in (Get-Content -LiteralPath $EnvDst)) {
    if ($line -match '^\s*COMPOSE_PROJECT_NAME\s*=(.*)$') { $proj = $Matches[1].Trim() }
}
$PgVol    = "${proj}_lims_pgdata"
$MinioVol = "${proj}_lims_miniodata"
Say "project=$proj  volume: $PgVol / $MinioVol"

$Compose = @('compose', '-f', 'docker-compose.prod.yml', '-f', 'docker-compose.cloudflare.yml',
             '--env-file', '.env.prod')

# ── 3. Volume phải trống ─────────────────────────────────────────────────────
# Image postgres CHỈ chạy initdb khi thư mục dữ liệu rỗng. Volume còn sót lại từ
# lần thử trước sẽ giữ nguyên mật khẩu cũ, POSTGRES_PASSWORD trong .env.prod bị bỏ
# qua hoàn toàn, và lims-api thất bại xác thực với một thông báo không hề nhắc tới
# nguyên nhân thật.
$existing = @()
foreach ($v in @($PgVol, $MinioVol)) {
    & docker volume inspect $v *> $null
    if ($LASTEXITCODE -eq 0) { $existing += $v }
}
if ($existing.Count -gt 0) {
    if (-not $Fresh) {
        Write-Host ""
        Write-Host "Volume da ton tai: $($existing -join ', ')" -ForegroundColor Yellow
        Write-Host "Khoi phuc de len volume cu se tron du lieu, va mat khau Postgres se van la"
        Write-Host "mat khau cu (initdb khong chay lai tren volume da co du lieu)."
        Write-Host "Chay lai kem -Fresh de XOA chung truoc khi khoi phuc." -ForegroundColor Yellow
        Die "dung lai de ban tu quyet dinh"
    }
    Write-Host ""
    Write-Host "SAP XOA VINH VIEN cac volume sau va toan bo du lieu ben trong:" -ForegroundColor Red
    $existing | ForEach-Object { Write-Host "   $_" -ForegroundColor Red }
    $ans = Read-Host "Go dung chu XOA de xac nhan"
    if ($ans -cne 'XOA') { Die "huy bo" }
    & docker $Compose down -v --remove-orphans
    foreach ($v in $existing) { & docker volume rm -f $v *> $null }
    Ok "da xoa volume cu"
}

# ── 4. Dựng Postgres rỗng rồi nạp dump ───────────────────────────────────────
Say "khoi dong Postgres..."
& docker $Compose up -d postgres
if ($LASTEXITCODE -ne 0) { Die "khong khoi dong duoc postgres" }

Say "cho Postgres san sang..."
$ready = $false
foreach ($i in 1..60) {
    & docker $Compose exec -T postgres pg_isready -U lims -d lims *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { Die "Postgres khong san sang sau 120 giay. Xem: docker compose logs postgres" }
Ok "Postgres san sang"

Say "nap db.dump (co the mat vai phut)..."
& docker $Compose cp $Dump postgres:/tmp/db.dump
if ($LASTEXITCODE -ne 0) { Die "docker cp db.dump that bai" }

# --clean --if-exists: DB vừa initdb nên gần như rỗng, nhưng vẫn để --clean để
# chạy lại được sau một lần restore dở dang. --exit-on-error KHÔNG dùng: pg_restore
# luôn phàn nàn về extension/owner do superuser tạo, đó là cảnh báo vô hại.
& docker $Compose exec -T postgres pg_restore -U lims -d lims --clean --if-exists --no-owner /tmp/db.dump
$restoreCode = $LASTEXITCODE
& docker $Compose exec -T postgres rm -f /tmp/db.dump *> $null
if ($restoreCode -ne 0) {
    Write-Host "[restore] pg_restore ket thuc voi ma $restoreCode — thuong la canh bao ve owner/extension." -ForegroundColor Yellow
    Write-Host "[restore] Se kiem lai bang so ban ghi ngay duoi day." -ForegroundColor Yellow
}

# Bằng chứng thật, không tin mã thoát: đếm user và đọc phiên bản migration.
$users = (& docker $Compose exec -T postgres psql -U lims -d lims -tAc 'SELECT count(*) FROM users;') 2>$null
$alem  = (& docker $Compose exec -T postgres psql -U lims -d lims -tAc 'SELECT version_num FROM alembic_version;') 2>$null
if (-not $users -or [int]($users -replace '\D', '') -eq 0) {
    Die "bang users rong sau khi restore — du lieu KHONG vao. Xem log o tren."
}
Ok "Postgres: $($users.Trim()) nguoi dung, alembic=$($alem.Trim())"

# ── 5. MinIO ─────────────────────────────────────────────────────────────────
Say "tao volume MinIO..."
& docker $Compose create minio *> $null
& docker volume inspect $MinioVol *> $null
if ($LASTEXITCODE -ne 0) { & docker volume create $MinioVol *> $null }

Say "giai nen file dinh kem vao $MinioVol..."
$helper = 'lims-restore-helper'
& docker rm -f $helper *> $null
# Container dùng một lần, chỉ gắn volume có tên — không mount thư mục host nào.
& docker create --name $helper -v "${MinioVol}:/data" alpine `
    sh -c 'tar xzf /tmp/minio-files.tar.gz -C /data && echo TAR_OK' *> $null
if ($LASTEXITCODE -ne 0) { Die "khong tao duoc container phu tro" }
& docker cp $Tar "${helper}:/tmp/minio-files.tar.gz"
if ($LASTEXITCODE -ne 0) { & docker rm -f $helper *> $null; Die "docker cp minio-files.tar.gz that bai" }
$tarOut = & docker start -a $helper 2>&1
$tarCode = $LASTEXITCODE
& docker rm -f $helper *> $null
if ($tarCode -ne 0 -or ($tarOut -notmatch 'TAR_OK')) { Die "giai nen that bai: $tarOut" }
Ok "da giai nen file dinh kem"

# ── 6. Dựng toàn bộ stack ────────────────────────────────────────────────────
Say "build va khoi dong toan bo stack (lan dau mat 5-15 phut)..."
& docker $Compose up -d --build
if ($LASTEXITCODE -ne 0) { Die "docker compose up that bai — xem log o tren" }

Write-Host ""
Ok "khoi phuc xong"
Write-Host ""
Write-Host "Kiem tra tiep:" -ForegroundColor Cyan
Write-Host "  docker compose ps                          # tat ca phai (healthy)"
Write-Host "  docker compose logs -f lims-api            # cho dong 'Application startup complete'"
Write-Host "  docker compose logs lims-cloudflared       # cho 'Registered tunnel connection'"
Write-Host "  docker compose exec lims-api curl -fsS http://localhost:8060/health/ready"
Write-Host ""
Write-Host "Sau do mo trinh duyet vao ten mien trong APP_PUBLIC_URL va dang nhap thu." -ForegroundColor Cyan
