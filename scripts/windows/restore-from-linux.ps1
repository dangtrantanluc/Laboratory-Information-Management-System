<#
.SYNOPSIS
    Khôi phục dữ liệu LIMS (Postgres + kho tệp Silo/MinIO) từ gói do scripts/export-for-windows.sh tạo.

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

    KHÔNG BẬT CLOUDFLARE TUNNEL theo mặc định. Máy mới và máy cũ dùng CHUNG một token
    tunnel; nếu cả hai cùng chạy, Cloudflare chia request cho cả hai máy và dữ liệu
    bị ghi vào hai database khác nhau mà không ai hay. Script dựng mọi thứ trừ
    tunnel, tự kiểm sức khoẻ, rồi dừng lại. Tắt hẳn máy cũ xong thì chạy lại với
    -StartTunnel (hoặc: .\scripts\windows\dc.ps1 up -d cloudflared).

    Đối chiếu với MANIFEST.txt của gói (nếu có): số dòng TỪNG bảng và số tệp đính
    kèm phải khớp đúng máy nguồn — không chỉ "bảng users có dữ liệu".

.PARAMETER BundlePath
    Thư mục chứa db.dump, minio-files.tar.gz, env.prod, SHA256SUMS.txt, MANIFEST.txt.

.PARAMETER Fresh
    XOÁ volume dữ liệu hiện có trước khi khôi phục. Có hỏi xác nhận.

.PARAMETER StartTunnel
    Chỉ bật Cloudflare Tunnel (đưa ribe.com.vn trỏ về máy này). Dùng SAU khi đã khôi
    phục và đã TẮT HẲN máy cũ. Có hỏi xác nhận. Không đụng tới dữ liệu.

.EXAMPLE
    # Bước 1 — khôi phục, kiểm tra (tunnel chưa bật)
    .\scripts\windows\restore-from-linux.ps1 -BundlePath D:\lims-export-2026-10-14_1030
    # Bước 2 — tắt máy cũ, rồi chuyển domain về máy này
    .\scripts\windows\restore-from-linux.ps1 -StartTunnel
#>
[CmdletBinding(DefaultParameterSetName = 'Restore')]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'Restore')][string]$BundlePath,
    [Parameter(ParameterSetName = 'Restore')][switch]$Fresh,
    [Parameter(Mandatory = $true, ParameterSetName = 'Tunnel')][switch]$StartTunnel
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

function Say  { param($m) Write-Host "[restore] $m" -ForegroundColor Cyan }
function Ok   { param($m) Write-Host "[restore] OK  $m" -ForegroundColor Green }
function Die  { param($m) Write-Host "[restore] LOI $m" -ForegroundColor Red; exit 1 }

$Compose = @('compose', '-f', 'docker-compose.prod.yml', '-f', 'docker-compose.cloudflare.yml',
             '--env-file', '.env.prod')

# ── Chế độ -StartTunnel: chỉ chuyển domain ───────────────────────────────────
if ($StartTunnel) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot '.env.prod'))) { Die "chua co .env.prod — chay khoi phuc truoc" }
    $apiUp = (& docker $Compose ps --status running --services 2>$null) -contains 'lims-api'
    if (-not $apiUp) { Die "lims-api chua chay tren may nay — khoi phuc va kiem tra truoc khi bat tunnel" }
    Write-Host ""
    Write-Host "Bat tunnel = ten mien trong APP_PUBLIC_URL tro ve MAY NAY." -ForegroundColor Yellow
    Write-Host "May cu PHAI da tat han (it nhat container lims-cloudflared), neu khong" -ForegroundColor Yellow
    Write-Host "Cloudflare chia request cho ca hai may va du lieu bi ghi vao hai DB khac nhau." -ForegroundColor Yellow
    Write-Host "  Tren may cu (Linux):  docker stop lims-cloudflared lims-api" -ForegroundColor DarkGray
    $ans = Read-Host "Go dung chu DA TAT MAY CU de tiep tuc"
    if ($ans -cne 'DA TAT MAY CU') { Die "huy bo — tunnel chua bat" }
    & docker $Compose up -d cloudflared
    if ($LASTEXITCODE -ne 0) { Die "khong bat duoc cloudflared" }
    Say "cho tunnel ket noi..."
    $reg = $false
    foreach ($i in 1..30) {
        $log = (& docker logs lims-cloudflared 2>&1) -join "`n"
        if ($log -match 'Registered tunnel connection') { $reg = $true; break }
        Start-Sleep -Seconds 2
    }
    if ($reg) { Ok "tunnel da ket noi — mo ten mien va dang nhap thu" }
    else { Write-Host "[restore] !   chua thay 'Registered tunnel connection' sau 60 giay — xem: docker logs lims-cloudflared" -ForegroundColor Yellow }
    exit 0
}

$Bundle = (Resolve-Path -LiteralPath $BundlePath).Path
$Manifest = Join-Path $Bundle 'MANIFEST.txt'
# table:<ten>=<so dong> va objects=<so tep> — sinh tren CHINH ban dump o may nguon.
$Expected = @{}
$ExpectedObjects = $null
if (Test-Path -LiteralPath $Manifest) {
    foreach ($line in (Get-Content -LiteralPath $Manifest -Encoding UTF8)) {
        if ($line -match '^table:([^=]+)=(\d+)$') { $Expected[$Matches[1]] = [int64]$Matches[2] }
        elseif ($line -match '^objects=(\d+)$') { $ExpectedObjects = [int64]$Matches[1] }
    }
}
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

# Bằng chứng thật, không tin mã thoát: đếm user, đọc phiên bản migration, rồi đối
# chiếu số dòng TỪNG bảng với MANIFEST của máy nguồn.
$users = (& docker $Compose exec -T postgres psql -U lims -d lims -tAc 'SELECT count(*) FROM users;') 2>$null
$alem  = (& docker $Compose exec -T postgres psql -U lims -d lims -tAc 'SELECT version_num FROM alembic_version;') 2>$null
if (-not $users -or [int]($users -replace '\D', '') -eq 0) {
    Die "bang users rong sau khi restore — du lieu KHONG vao. Xem log o tren."
}
Ok "Postgres: $($users.Trim()) nguoi dung, alembic=$($alem.Trim())"

if ($Expected.Count -gt 0) {
    Say "doi chieu so dong $($Expected.Count) bang voi MANIFEST..."
    $q = "SELECT table_name || '=' || (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM public.%I', table_name), false, true, '')))[1]::text FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"
    $actual = @{}
    foreach ($line in (& docker $Compose exec -T postgres psql -U lims -d lims -tA -c $q)) {
        if ($line -match '^([^=]+)=(\d+)$') { $actual[$Matches[1]] = [int64]$Matches[2] }
    }
    $diff = @()
    foreach ($t in $Expected.Keys) {
        $got = if ($actual.ContainsKey($t)) { $actual[$t] } else { -1 }
        if ($got -ne $Expected[$t]) { $diff += "  $t : may nguon $($Expected[$t]), may nay $got" }
    }
    if ($diff.Count -gt 0) {
        $diff | ForEach-Object { Write-Host $_ -ForegroundColor Red }
        Die "$($diff.Count) bang KHONG khop may nguon — khong khoi dong he thong. Chay lai voi -Fresh."
    }
    Ok "ca $($Expected.Count) bang khop so dong voi may nguon"
} else {
    Write-Host "[restore] !   goi khong co MANIFEST.txt — chi kiem duoc bang users" -ForegroundColor Yellow
}

# ── 5. Kho tệp (Silo — cùng định dạng dữ liệu với MinIO) ─────────────────────
Say "tao volume kho tep..."
& docker $Compose create minio *> $null
& docker volume inspect $MinioVol *> $null
if ($LASTEXITCODE -ne 0) { & docker volume create $MinioVol *> $null }

Say "giai nen file dinh kem vao $MinioVol..."
$helper = 'lims-restore-helper'
& docker rm -f $helper *> $null
# Container dùng một lần, chỉ gắn volume có tên — không mount thư mục host nào.
# Đếm ngay sau khi giải nén: mỗi tệp S3 là một thư mục có xl.meta (.minio.sys là
# siêu dữ liệu nội bộ, không tính).
& docker create --name $helper -v "${MinioVol}:/data" alpine `
    sh -c 'tar xzf /tmp/minio-files.tar.gz -C /data && echo TAR_OK && echo OBJECTS=$(find /data -name xl.meta -not -path "*/.minio.sys/*" | wc -l)' *> $null
if ($LASTEXITCODE -ne 0) { Die "khong tao duoc container phu tro" }
& docker cp $Tar "${helper}:/tmp/minio-files.tar.gz"
if ($LASTEXITCODE -ne 0) { & docker rm -f $helper *> $null; Die "docker cp minio-files.tar.gz that bai" }
$tarOut = & docker start -a $helper 2>&1
$tarCode = $LASTEXITCODE
& docker rm -f $helper *> $null
# -join trước khi so khớp: $tarOut là MẢNG nhiều dòng, và -notmatch trên mảng trả về
# các dòng không khớp (luôn "đúng" khi có >1 dòng) chứ không trả về true/false.
$tarText = $tarOut -join "`n"
if ($tarCode -ne 0 -or ($tarText -notmatch 'TAR_OK')) { Die "giai nen that bai: $tarText" }
$gotObjects = if ($tarText -match 'OBJECTS=(\d+)') { [int64]$Matches[1] } else { -1 }
if ($null -ne $ExpectedObjects -and $gotObjects -ne $ExpectedObjects) {
    Die "so tep dinh kem: may nguon $ExpectedObjects, may nay $gotObjects — goi du lieu khong tron ven"
}
Ok "da giai nen $gotObjects tep dinh kem$(if ($null -ne $ExpectedObjects) { ' (khop may nguon)' })"

# ── 6. Dựng mọi thứ TRỪ tunnel ───────────────────────────────────────────────
$services = @(& docker $Compose config --services) | Where-Object { $_ -and $_ -ne 'cloudflared' }
Say "build va khoi dong: $($services -join ', ') (lan dau mat 5-15 phut)..."
& docker $Compose up -d --build @services
if ($LASTEXITCODE -ne 0) { Die "docker compose up that bai — xem log o tren" }

# ── 7. Tự kiểm sức khoẻ ──────────────────────────────────────────────────────
Say "cho lims-api san sang..."
$apiOk = $false
$ready = ''
# /health/ready trả HTTP 200 cả khi "degraded" — phải đọc "success": true, không tin mã thoát của curl.
foreach ($i in 1..90) {
    $ready = (& docker $Compose exec -T lims-api curl -sS http://localhost:8060/health/ready 2>$null) -join ''
    if ($ready -match '"success"\s*:\s*true') { $apiOk = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $apiOk) { Die "lims-api chua san sang sau 3 phut ($ready) — xem: .\scripts\windows\dc.ps1 logs lims-api" }
Ok "lims-api san sang (DB + Redis + kho tep deu ket noi duoc)"
& docker $Compose exec -T lims-web wget -qO- http://127.0.0.1/ *> $null
if ($LASTEXITCODE -ne 0) { Die "lims-web khong phuc vu trang — xem: .\scripts\windows\dc.ps1 logs lims-web" }
Ok "lims-web phuc vu trang"

Write-Host ""
Ok "khoi phuc xong — TUNNEL CHUA BAT, nguoi dung van dang vao may cu"
Write-Host ""
Write-Host "Buoc tiep theo:" -ForegroundColor Cyan
Write-Host "  1. Tren may cu (Linux) tat han he thong:  docker stop lims-cloudflared lims-api"
Write-Host "  2. Tren may nay chuyen ten mien ve:       .\scripts\windows\restore-from-linux.ps1 -StartTunnel"
Write-Host "  3. Mo ten mien trong APP_PUBLIC_URL, dang nhap, mo vai phieu co tep dinh kem."
Write-Host "  Giu may cu (da tat) vai ngay de con duong lui." -ForegroundColor DarkGray
