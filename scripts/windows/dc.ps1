<#
.SYNOPSIS
    Gọi `docker compose` với ĐÚNG hồ sơ production. Dùng thay cho `docker compose` trần.

.DESCRIPTION
    Trên máy Linux, thư mục dự án có `.env` là symlink trỏ vào `.env.prod`, nên
    `docker compose ps` trần đã tự nạp COMPOSE_FILE và chạy đúng hồ sơ production.

    Windows KHÔNG có symlink đó (tạo symlink trên Windows cần quyền quản trị hoặc
    Developer Mode, và git không dựng lại nó khi clone). Hệ quả: `docker compose ps`
    trần trong thư mục dự án sẽ nạp docker-compose.yml — tức là hồ sơ DEV, với
    Postgres hardcode lims:lims. Lệnh vẫn chạy, không báo lỗi gì, chỉ là nó đang
    nói về một stack khác với stack đang phục vụ người dùng. Nguy hiểm nhất là
    `docker compose down -v`: xoá volume của hồ sơ nào thì tuỳ nó nạp file nào.

    Wrapper này khoá cứng cả hai file compose và --env-file, rồi chuyển tiếp mọi
    tham số còn lại.

.EXAMPLE
    .\scripts\windows\dc.ps1 ps
    .\scripts\windows\dc.ps1 logs -f lims-api
    .\scripts\windows\dc.ps1 up -d --build
    .\scripts\windows\dc.ps1 exec lims-api curl -fsS http://localhost:8060/health/ready
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args_
)

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $RepoRoot

if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot '.env.prod'))) {
    Write-Host "Khong thay .env.prod trong $RepoRoot" -ForegroundColor Red
    exit 1
}

& docker compose `
    -f 'docker-compose.prod.yml' `
    -f 'docker-compose.cloudflare.yml' `
    --env-file '.env.prod' @Args_
exit $LASTEXITCODE
