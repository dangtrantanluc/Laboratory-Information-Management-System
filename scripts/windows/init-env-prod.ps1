<#
.SYNOPSIS
    Điền .env.prod trên Windows: sinh mọi bí mật, đặt URL theo tên miền, giữ nguyên phần đã có.

.DESCRIPTION
    Bản Windows của scripts/init-env-prod.sh. Không cần openssl, không cần python.

    CHỈ dùng khi cài MỚI hoàn toàn trên máy Windows. Nếu bạn đang CHUYỂN hệ thống
    từ máy Linux sang (mang theo dữ liệu), ĐỪNG chạy script này — hãy dùng thẳng
    .env.prod copy từ máy cũ, vì POSTGRES_PASSWORD phải khớp với thời điểm initdb
    và đổi MINIO_ROOT_USER/PASSWORD sẽ khiến MinIO không đọc được kho file cũ.

    Chỉ ghi đè các dòng còn giá trị mẫu (CHANGE_ME_*, your-domain.example) — giá
    trị bạn đã tự điền được giữ nguyên, nên chạy lại nhiều lần vẫn an toàn.

    Hai thứ script KHÔNG tự làm được, phải điền tay sau đó:
      - CLOUDFLARE_TUNNEL_TOKEN  (lấy từ dashboard Cloudflare)
      - SMTP_USER / SMTP_PASSWORD

.EXAMPLE
    .\scripts\windows\init-env-prod.ps1 -Domain lims.hcmuaf.edu.vn
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Domain,
    [string]$EnvFile = '.env.prod'
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepoRoot

# Chặn lỗi hay gặp: dán cả https:// hoặc dấu / cuối vào tham số.
$Domain = $Domain -replace '^https?://', ''
$Domain = $Domain.TrimEnd('/')
if ([string]::IsNullOrWhiteSpace($Domain)) { throw "Ten mien rong" }

$EnvPath = Join-Path $RepoRoot $EnvFile
if (-not (Test-Path -LiteralPath $EnvPath)) {
    Copy-Item -LiteralPath (Join-Path $RepoRoot '.env.prod.example') -Destination $EnvPath
    Write-Host "-> tao $EnvFile tu mau"
}

# Đọc giữ nguyên thứ tự dòng — file này có rất nhiều chú thích giải thích vì sao
# từng giá trị là như vậy, ghi lại theo kiểu key=value sẽ xoá sạch chúng.
$Lines = [System.Collections.Generic.List[string]]::new()
[System.IO.File]::ReadAllLines($EnvPath) | ForEach-Object { [void]$Lines.Add($_) }

function Get-Cur {
    param([string]$Key)
    for ($i = $Lines.Count - 1; $i -ge 0; $i--) {
        if ($Lines[$i] -match "^\s*$([regex]::Escape($Key))\s*=(.*)$") { return $Matches[1].Trim() }
    }
    return ''
}
function Set-Line {
    param([string]$Key, [string]$Value)
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match "^\s*$([regex]::Escape($Key))\s*=") { $Lines[$i] = "$Key=$Value"; return }
    }
    [void]$Lines.Add("$Key=$Value")
}
function Test-Placeholder {
    param([string]$Value)
    return ([string]::IsNullOrWhiteSpace($Value) -or $Value -like '*CHANGE_ME*' -or $Value -like '*your-domain.example*')
}

# Chỉ đặt khi biến đang rỗng hoặc còn là giá trị mẫu.
function Set-Secret {
    param([string]$Key, [string]$Value)
    $cur = Get-Cur $Key
    # admin@lims.local là tài khoản demo được liệt kê công khai trong repo —
    # phải thay, không được coi là "giá trị người dùng đã tự điền".
    if (-not (Test-Placeholder $cur) -and $cur -notlike '*@lims.local') {
        Write-Host ("  .   {0,-28} giu nguyen gia tri da co" -f $Key) -ForegroundColor DarkGray
        return
    }
    Set-Line $Key $Value
    if ($Key -match 'PASSWORD|SECRET|TOKEN|KEY') {
        Write-Host ("  OK  {0,-28} (da sinh, khong hien thi)" -f $Key) -ForegroundColor Green
    } else {
        Write-Host ("  OK  {0,-28} {1}" -f $Key, $Value) -ForegroundColor Green
    }
}

# URL là giá trị SUY RA từ tham số -Domain, không phải bí mật ngẫu nhiên — nên
# LUÔN đặt lại theo tham số. Nếu không: chạy nhầm tên miền một lần rồi chạy lại
# với tên miền đúng sẽ bị "giữ nguyên giá trị đã có", tức là âm thầm deploy bằng
# tên miền sai và lỗi CORS chỉ lộ ra khi người dùng mở trình duyệt.
function Set-Url {
    param([string]$Key, [string]$Value)
    $cur = Get-Cur $Key
    if ($cur -ne $Value -and -not (Test-Placeholder $cur)) {
        Write-Host ("  ->  {0,-28} {1} -> {2}" -f $Key, $cur, $Value) -ForegroundColor Yellow
    } else {
        Write-Host ("  OK  {0,-28} {1}" -f $Key, $Value) -ForegroundColor Green
    }
    Set-Line $Key $Value
}

function New-Secret {
    param([int]$Length)
    # Lấy mẫu có loại bỏ (rejection sampling) thay vì lấy dư modulo 62: modulo làm
    # 8 ký tự đầu bảng chữ cái xuất hiện nhiều hơn phần còn lại, làm giảm entropy
    # thật của mật khẩu so với con số ta tưởng.
    $chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    $max   = [math]::Floor(256 / $chars.Length) * $chars.Length
    $rng   = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $sb  = [System.Text.StringBuilder]::new()
        $buf = New-Object byte[] 1
        while ($sb.Length -lt $Length) {
            $rng.GetBytes($buf)
            if ($buf[0] -lt $max) { [void]$sb.Append($chars[$buf[0] % $chars.Length]) }
        }
        return $sb.ToString()
    } finally { $rng.Dispose() }
}
function New-HexSecret {
    param([int]$Bytes)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $b = New-Object byte[] $Bytes
        $rng.GetBytes($b)
        return (($b | ForEach-Object { $_.ToString('x2') }) -join '')
    } finally { $rng.Dispose() }
}

Write-Host ""
Write-Host "=== Dien $EnvFile cho $Domain ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "-- Ho so compose (dau ';' cho Windows) --"
Set-Url 'COMPOSE_PATH_SEPARATOR' ';'
Set-Url 'COMPOSE_FILE'           'docker-compose.prod.yml;docker-compose.cloudflare.yml'
Set-Url 'COMPOSE_PROJECT_NAME'   'lims'

Write-Host ""
Write-Host "-- URL (ca ba dung CHUNG mot origin: thiet ke mot-tunnel) --"
Set-Url 'APP_PUBLIC_URL' "https://$Domain"
Set-Url 'CORS_ORIGINS'   "https://$Domain"
# KHÔNG kèm tên bucket: boto3 path-style tự nối /lims-attachments/{key}.
Set-Url 'MINIO_PUBLIC_ENDPOINT' "https://$Domain"

Write-Host ""
Write-Host "-- Bi mat --"
Set-Secret 'JWT_SECRET'          (New-HexSecret 32)
Set-Secret 'POSTGRES_PASSWORD'   (New-Secret 28)
Set-Secret 'REDIS_PASSWORD'      (New-Secret 28)
Set-Secret 'MINIO_ROOT_USER'     ("lims-" + (New-HexSecret 4))
Set-Secret 'MINIO_ROOT_PASSWORD' (New-Secret 28)
Set-Secret 'SEED_ADMIN_PASSWORD' (New-Secret 20)

Write-Host ""
Write-Host "-- Khoa Web Push VAPID --"
if (Test-Placeholder (Get-Cur 'VAPID_PUBLIC_KEY')) {
    $vapid = & (Join-Path $PSScriptRoot 'gen-vapid-keys.ps1')
    foreach ($line in $vapid) {
        if ($line -match '^VAPID_PUBLIC_KEY=(.+)$')  { Set-Secret 'VAPID_PUBLIC_KEY'  $Matches[1] }
        if ($line -match '^VAPID_PRIVATE_KEY=(.+)$') { Set-Secret 'VAPID_PRIVATE_KEY' $Matches[1] }
    }
} else {
    Write-Host ("  .   {0,-28} giu nguyen khoa da co" -f 'VAPID_*') -ForegroundColor DarkGray
}
Set-Secret 'VAPID_CLAIMS_EMAIL' "admin@$Domain"
Set-Secret 'SEED_ADMIN_EMAIL'   "admin@$Domain"

# UTF-8 KHÔNG BOM, xuống dòng LF. Có BOM thì compose đọc khoá đầu tiên thành
# "<U+FEFF>COMPOSE_PATH_SEPARATOR" và lặng lẽ bỏ qua nó — biểu hiện là compose
# báo thiếu file compose dù dòng khai báo rành rành trong file.
$text = ($Lines -join "`n") + "`n"
[System.IO.File]::WriteAllText($EnvPath, $text, (New-Object System.Text.UTF8Encoding $false))

Write-Host ""
Write-Host "-- Con lai — PHAI dien tay --"
foreach ($k in @('CLOUDFLARE_TUNNEL_TOKEN', 'SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD')) {
    if (Test-Placeholder (Get-Cur $k)) { Write-Host ("  X   {0,-28} chua co" -f $k) -ForegroundColor Red }
    else                               { Write-Host ("  OK  {0,-28} da dien" -f $k) -ForegroundColor Green }
}

Write-Host ""
Write-Host "=== Viec con lai ===" -ForegroundColor Cyan
Write-Host @"

  1. Token tunnel — Cloudflare Dashboard -> Zero Trust -> Networks -> Tunnels
     -> Create tunnel -> copy token, roi mo $EnvFile bang Notepad va dan vao dong
     CLOUDFLARE_TUNNEL_TOKEN=

     Trong tab Public Hostname dat:  $Domain  ->  HTTP  ->  lims-web:80
     (lims-web:80 la ten service trong mang docker, KHONG phai localhost)

  2. SMTP — vi du Gmail can App Password 16 ky tu:
       SMTP_HOST=smtp.gmail.com  SMTP_PORT=587  SMTP_STARTTLS=true

  3. Kiem lai roi moi chay:
       .\scripts\windows\preflight-deploy.ps1

  Mat khau admin lan dau (DOI NGAY sau khi dang nhap):
       Select-String '^SEED_ADMIN_PASSWORD=' $EnvFile
"@
