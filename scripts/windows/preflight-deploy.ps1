<#
.SYNOPSIS
    Kiểm tra trước khi deploy LIMS trên Windows — chạy TRƯỚC `docker compose up`.

.DESCRIPTION
    Bản Windows của scripts/preflight-deploy.sh, cộng thêm các phép kiểm chỉ có ý
    nghĩa trên Windows (kết thúc dòng CRLF, dấu phân cách COMPOSE_FILE, tài nguyên
    WSL2 chứ không phải tài nguyên máy).

    Bắt các lỗi mà Docker chỉ phát hiện lúc chạy, hoặc tệ hơn là KHÔNG phát hiện:
    giá trị CHANGE_ME vẫn là chuỗi không rỗng nên phép kiểm ${VAR:?} của compose
    cho qua, container khởi động bình thường rồi hỏng ở chỗ khác — CORS chặn, tải
    tệp về 403, Web Push im lặng.

.EXAMPLE
    .\scripts\windows\preflight-deploy.ps1
    .\scripts\windows\preflight-deploy.ps1 -EnvFile .env.prod
#>
[CmdletBinding()]
param(
    [string]$EnvFile = '.env.prod'
)

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

# Về thư mục gốc dự án (script nằm ở <gốc>\scripts\windows\).
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

$script:Err = 0
function Write-Ok   { param($m) Write-Host "  [OK]   $m" -ForegroundColor Green }
function Write-Warn { param($m) Write-Host "  [!]    $m" -ForegroundColor Yellow }
function Write-Fail { param($m) Write-Host "  [X]    $m" -ForegroundColor Red; $script:Err = 1 }
function Write-Skip { param($m) Write-Host "  [-]    $m" -ForegroundColor DarkGray }

# ── Nạp file env ─────────────────────────────────────────────────────────────
$EnvPath = Join-Path $RepoRoot $EnvFile
Write-Host ""
Write-Host "=== Kiem tra truoc deploy — $EnvFile ===" -ForegroundColor Cyan
Write-Host "    thu muc: $RepoRoot"
Write-Host ""

if (-not (Test-Path -LiteralPath $EnvPath)) {
    Write-Fail "Khong thay $EnvFile. Chay: Copy-Item .env.prod.example $EnvFile"
    exit 1
}

$EnvMap = @{}
foreach ($line in (Get-Content -LiteralPath $EnvPath -Encoding UTF8)) {
    # Chỉ nhận dòng KEY=VALUE, bỏ comment và dòng trống. Giá trị giữ nguyên phần
    # sau dấu '=' ĐẦU TIÊN — mật khẩu và URL đều có thể chứa '='.
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
        $EnvMap[$Matches[1]] = $Matches[2].Trim()
    }
}
function Get-Val { param($k) if ($EnvMap.ContainsKey($k)) { $EnvMap[$k] } else { '' } }
function Test-Template {
    param($k)
    $v = Get-Val $k
    return ([string]::IsNullOrWhiteSpace($v) -or $v -like '*CHANGE_ME*' -or $v -like '*your-domain.example*')
}

# ── 1. File cấu hình có bị đưa vào git không ─────────────────────────────────
Write-Host "-- File cau hinh --"
# Kiểm chính xác "có bị git THEO DÕI không", không phải "có được ignore không":
# file nằm ngoài repo cũng khiến check-ignore trả false, gây báo động giả.
$gitOk = $null -ne (Get-Command git -ErrorAction SilentlyContinue)
if ($gitOk) {
    & git ls-files --error-unmatch $EnvFile *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Fail "$EnvFile DANG bi git theo doi — bi mat se bi commit"
    } else {
        Write-Ok "$EnvFile khong bi git theo doi"
    }
} else {
    Write-Skip "khong co git trong PATH — bo qua kiem tra theo doi"
}

# ── 2. Bẫy riêng của Windows: kết thúc dòng ──────────────────────────────────
# Đây là lỗi số 1 khi mang repo sang Windows. Git for Windows mặc định
# core.autocrlf=true; nếu bản clone này được tạo TRƯỚC khi repo có .gitattributes
# thì entrypoint.sh đang mang CRLF. File đó chạy làm ENTRYPOINT trong image Linux,
# shebang thành "#!/usr/bin/env bash\r", kernel tìm interpreter tên "bash\r" và
# container chết ngay với thông báo đánh lạc hướng:
#   exec /app/entrypoint.sh: no such file or directory
Write-Host ""
Write-Host "-- Ket thuc dong (loi Windows pho bien nhat) --"
$lfTargets = @(
    'lims-backend\entrypoint.sh',
    'lims-frontend\nginx.conf',
    'docker-compose.prod.yml',
    'docker-compose.cloudflare.yml'
)
$crlfFound = @()
$absent    = @()
foreach ($rel in $lfTargets) {
    $p = Join-Path $RepoRoot $rel
    # File thiếu KHÔNG phải là file "đã đạt LF". Không tách hai trường hợp này thì
    # một bản copy thiếu file vẫn nhận được dòng "[OK] đều là LF" ngay dưới dòng
    # báo thiếu — mâu thuẫn ngay trong cùng một mục, đọc xong không biết tin dòng nào.
    if (-not (Test-Path -LiteralPath $p)) { Write-Fail "thieu file $rel"; $absent += $rel; continue }
    $bytes = [System.IO.File]::ReadAllBytes($p)
    $hasCr = $false
    for ($i = 0; $i -lt $bytes.Length - 1; $i++) {
        if ($bytes[$i] -eq 0x0D -and $bytes[$i + 1] -eq 0x0A) { $hasCr = $true; break }
    }
    if ($hasCr) { $crlfFound += $rel }
}
if ($crlfFound.Count -gt 0) {
    Write-Fail "CRLF trong: $($crlfFound -join ', ')"
    Write-Fail "  Container se chet voi loi 'no such file or directory' du file van o do."
    Write-Fail "  Sua bang cach clone lai cho dung:"
    Write-Fail "     git config --global core.autocrlf false"
    Write-Fail "     git rm --cached -r . ; git reset --hard"
} elseif ($absent.Count -gt 0) {
    Write-Skip "khong ket luan duoc — con $($absent.Count) file chua co mat"
} else {
    Write-Ok "cac file chay trong container deu la LF"
}

# ── 3. Hồ sơ compose — dấu phân cách khác nhau theo hệ điều hành ─────────────
Write-Host ""
Write-Host "-- Ho so compose --"
$sep  = Get-Val 'COMPOSE_PATH_SEPARATOR'
$cf   = Get-Val 'COMPOSE_FILE'
$proj = Get-Val 'COMPOSE_PROJECT_NAME'
if ([string]::IsNullOrWhiteSpace($cf)) {
    Write-Warn "COMPOSE_FILE chua dat — moi lenh 'docker compose' phai tu them -f"
} elseif ($cf -match ':' -and $cf -notmatch '^[A-Za-z]:\\') {
    # Đây chính là lỗi khi bê thẳng .env.prod từ Linux sang: compose trên Windows
    # tách bằng ';' nên hiểu cả chuỗi là MỘT tên file.
    Write-Fail "COMPOSE_FILE dung dau ':' (kieu Linux): $cf"
    Write-Fail "  Tren Windows phai la ';'. Sua thanh:"
    Write-Fail "     COMPOSE_PATH_SEPARATOR=;"
    Write-Fail "     COMPOSE_FILE=docker-compose.prod.yml;docker-compose.cloudflare.yml"
} elseif ([string]::IsNullOrWhiteSpace($sep)) {
    Write-Warn "COMPOSE_FILE dung ';' nhung thieu COMPOSE_PATH_SEPARATOR=; — them vao cho chac"
} else {
    Write-Ok "COMPOSE_FILE = $cf"
}
if ([string]::IsNullOrWhiteSpace($proj)) {
    # Tên project quyết định tên volume dữ liệu. Không khoá cứng thì đổi tên thư
    # mục là dữ liệu "biến mất" (thực ra nằm ở volume khác).
    Write-Fail "COMPOSE_PROJECT_NAME chua dat — ten volume se phu thuoc ten thu muc"
    Write-Fail "  Them vao ${EnvFile}:  COMPOSE_PROJECT_NAME=lims"
} else {
    Write-Ok "COMPOSE_PROJECT_NAME = $proj  (volume: ${proj}_lims_pgdata)"
}

# ── 4. Biến bắt buộc ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "-- Bien bat buoc --"
$required = @(
    'APP_PUBLIC_URL', 'CORS_ORIGINS', 'JWT_SECRET', 'MINIO_PUBLIC_ENDPOINT',
    'MINIO_ROOT_USER', 'MINIO_ROOT_PASSWORD', 'POSTGRES_PASSWORD', 'REDIS_PASSWORD',
    'SEED_ADMIN_EMAIL', 'SEED_ADMIN_PASSWORD', 'SMTP_HOST',
    'VAPID_PUBLIC_KEY', 'VAPID_PRIVATE_KEY', 'CLOUDFLARE_TUNNEL_TOKEN'
)
$missing = 0
foreach ($v in $required) {
    $val = Get-Val $v
    if ([string]::IsNullOrWhiteSpace($val)) {
        Write-Fail "$v chua co gia tri"; $missing++
    } elseif ($val -like '*CHANGE_ME*' -or $val -like '*your-domain.example*') {
        # Lỗi hay bị bỏ sót nhất: compose coi CHANGE_ME là hợp lệ vì nó chỉ kiểm
        # chuỗi rỗng, nên stack khởi động được rồi hỏng ở tầng ứng dụng.
        Write-Fail "$v van la gia tri mau ($val)"; $missing++
    }
}
if ($missing -eq 0) { Write-Ok "du $($required.Count) bien bat buoc, khong con gia tri mau" }

# ── 5. Định dạng URL ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "-- Dinh dang URL --"
$errBefore = $script:Err
$checked = 0
foreach ($v in @('APP_PUBLIC_URL', 'CORS_ORIGINS', 'MINIO_PUBLIC_ENDPOINT')) {
    if (Test-Template $v) { continue }
    $val = Get-Val $v
    $checked = 1
    if ($val -notlike 'https://*') { Write-Fail "$v phai bat dau bang https:// (dang: $val)" }
    if ($val.EndsWith('/'))        { Write-Fail "$v KHONG duoc co dau / o cuoi (dang: $val)" }
}
# MINIO_PUBLIC_ENDPOINT là ORIGIN, KHÔNG kèm tên bucket: boto3 dùng path-style nên
# tự nối thành {endpoint}/lims-attachments/{key}. Thêm bucket vào đây sẽ sinh URL
# lặp hai lần và tải về 404.
$mp = if (Test-Template 'MINIO_PUBLIC_ENDPOINT') { '' } else { Get-Val 'MINIO_PUBLIC_ENDPOINT' }
if ($mp -and $mp -like '*/lims-attachments*') {
    Write-Fail "MINIO_PUBLIC_ENDPOINT khong duoc chua ten bucket — chi la origin (dang: $mp)"
}
$app = if (Test-Template 'APP_PUBLIC_URL') { '' } else { Get-Val 'APP_PUBLIC_URL' }
if ($mp -and $app -and $mp -ne $app) {
    Write-Warn "MINIO_PUBLIC_ENDPOINT ($mp) khac APP_PUBLIC_URL ($app)."
    Write-Warn "  Thiet ke mot-tunnel dung CHUNG origin; khac nhau thi phai tu route rieng cho MinIO."
}
$cors = if (Test-Template 'CORS_ORIGINS') { '' } else { Get-Val 'CORS_ORIGINS' }
if ($app -and $cors -and ($cors -notlike "*$($app -replace '^https://', '')*")) {
    Write-Warn "CORS_ORIGINS ($cors) khong chua ten mien cua APP_PUBLIC_URL ($app)"
}
if ($checked -eq 0)              { Write-Skip "bo qua: cac URL con la gia tri mau" }
elseif ($script:Err -eq $errBefore) { Write-Ok "URL dung dinh dang" }

# ── 6. Khoá VAPID — độ dài quyết định tính hợp lệ ────────────────────────────
Write-Host ""
Write-Host "-- Khoa VAPID --"
$pub = Get-Val 'VAPID_PUBLIC_KEY'; $priv = Get-Val 'VAPID_PRIVATE_KEY'
if ($pub -like '*object at*' -or $priv -like '*object at*') {
    Write-Fail "Khoa VAPID la doi tuong Python, khong phai khoa. Dung .\scripts\windows\gen-vapid-keys.ps1"
} elseif ($pub.Length -ne 87 -or $priv.Length -ne 43) {
    Write-Fail "Khoa VAPID sai do dai (cong khai $($pub.Length), can 87; rieng $($priv.Length), can 43)"
} else {
    Write-Ok "khoa VAPID dung dinh dang"
}

# ── 7. Độ mạnh bí mật ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "-- Do manh bi mat --"
if (Test-Template 'JWT_SECRET') {
    Write-Skip "bo qua: bi mat con la gia tri mau"
} else {
    $jwt = Get-Val 'JWT_SECRET'
    if ($jwt.Length -lt 32) { Write-Fail "JWT_SECRET chi $($jwt.Length) ky tu — can >=32" }
    else                    { Write-Ok  "JWT_SECRET $($jwt.Length) ky tu" }
    foreach ($v in @('POSTGRES_PASSWORD', 'REDIS_PASSWORD', 'MINIO_ROOT_PASSWORD', 'SEED_ADMIN_PASSWORD')) {
        if (Test-Template $v) { continue }
        $val = Get-Val $v
        if ($val.Length -lt 12) { Write-Warn "$v chi $($val.Length) ky tu — nen >=12" }
    }
}
$sa = Get-Val 'SEED_ADMIN_PASSWORD'
if ($sa -in @('Lims@1234', 'ChangeMe@123')) {
    Write-Fail "SEED_ADMIN_PASSWORD la mat khau mac dinh da cong khai trong repo"
}
if ((Get-Val 'MINIO_ROOT_USER') -eq 'minioadmin') {
    Write-Fail "MINIO_ROOT_USER = minioadmin — chot an toan trong config.py se chan khoi dong"
}

# ── 8. Docker trên Windows ───────────────────────────────────────────────────
Write-Host ""
Write-Host "-- Docker Desktop --"
if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Fail "Khong thay lenh 'docker'. Cai Docker Desktop va mo lai cua so PowerShell."
    Write-Host ""
    Write-Host "=== CON LOI — sua xong roi chay lai ===" -ForegroundColor Red
    exit 1
}

& docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Thieu Docker Compose v2 (lenh 'docker compose', khong phai 'docker-compose')"
} else {
    Write-Ok "docker compose $(& docker compose version --short)"
}

$info = & docker info --format '{{.NCPU}}|{{.MemTotal}}|{{.OSType}}|{{.OperatingSystem}}' 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($info)) {
    Write-Fail "Docker Desktop chua chay (docker info that bai). Mo Docker Desktop va doi bieu tuong het nhay."
} else {
    $parts   = $info -split '\|'
    $ncpu    = [int]$parts[0]
    $memGb   = [math]::Round([double]$parts[1] / 1GB, 1)
    $osType  = $parts[2]
    $osName  = $parts[3]

    # Container trong stack đều là Linux. Docker Desktop chuyển sang chế độ
    # Windows containers thì `docker compose up` báo lỗi "image operating system
    # linux cannot be used on this platform" — rất dễ gặp khi ai đó bấm nhầm menu.
    if ($osType -ne 'linux') {
        Write-Fail "Docker dang o che do '$osType' containers. Chuot phai bieu tuong Docker Desktop"
        Write-Fail "  -> 'Switch to Linux containers...'"
    } else {
        Write-Ok "che do Linux containers ($osName)"
    }

    # Số nhân/RAM Docker thấy là của MÁY ẢO WSL2, KHÔNG phải của máy. Máy 16GB mà
    # .wslconfig giới hạn 4GB thì stack (2g+1g+1g+512m) sẽ bị OOM-kill giữa chừng
    # — biểu hiện là container tự restart, không có lỗi ứng dụng nào.
    $cpusRaw = Get-Val 'LIMS_API_CPUS'
    $cpus    = if ([string]::IsNullOrWhiteSpace($cpusRaw)) { 2.0 } else { [double]$cpusRaw }
    if ($ncpu -lt $cpus) {
        Write-Fail "Docker chi thay $ncpu nhan nhung lims-api yeu cau $cpus — Docker se tu choi khoi dong."
        Write-Fail "  Them vao ${EnvFile}:  LIMS_API_CPUS=$ncpu"
    } else {
        Write-Ok "$ncpu nhan (WSL2) >= $cpus yeu cau"
    }

    # Tổng mem_limit khai trong hồ sơ prod: 2g + 1g + 1g + 512m + 256m = 4.75g.
    if ($memGb -lt 5) {
        Write-Warn "Docker chi co ${memGb}GB RAM — tong mem_limit cua stack la ~4.75GB."
        Write-Warn "  Tao %USERPROFILE%\.wslconfig voi:   [wsl2]  /  memory=8GB"
        Write-Warn "  Roi chay: wsl --shutdown  va khoi dong lai Docker Desktop."
    } else {
        Write-Ok "RAM Docker ${memGb}GB"
    }
}

$drive = (Get-Item $RepoRoot).PSDrive
if ($drive -and $drive.Free) {
    $freeGb = [math]::Round($drive.Free / 1GB, 1)
    # Image + volume của Docker Desktop nằm trong ổ đĩa ảo WSL2 ở %LOCALAPPDATA%,
    # tức là ổ C: — không phải ổ chứa thư mục dự án. Cảnh báo cho cả hai.
    if ($freeGb -lt 20) { Write-Warn "O $($drive.Name): con ${freeGb}GB — khuyen nghi >=20GB" }
    else                { Write-Ok  "o $($drive.Name): con ${freeGb}GB" }
}
$sysFree = [math]::Round((Get-PSDrive C -ErrorAction SilentlyContinue).Free / 1GB, 1)
if ($sysFree -and $sysFree -lt 20) {
    Write-Warn "O C: con ${sysFree}GB — dia ao WSL2 (image + volume Docker) nam o day"
}

# ── Kết luận ─────────────────────────────────────────────────────────────────
Write-Host ""
if ($script:Err -eq 0) {
    Write-Host "=== SAN SANG DEPLOY ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "  docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml ``"
    Write-Host "                 --env-file $EnvFile up -d --build"
} else {
    Write-Host "=== CON LOI — sua xong roi chay lai ===" -ForegroundColor Red
}
exit $script:Err
