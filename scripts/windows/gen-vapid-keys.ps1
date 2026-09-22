<#
.SYNOPSIS
    Sinh cặp khoá Web Push VAPID đúng định dạng ứng dụng LIMS cần (bản Windows).

.DESCRIPTION
    Tương đương scripts/gen-vapid-keys.sh nhưng KHÔNG cần python, KHÔNG cần openssl
    và KHÔNG cần docker — dùng thẳng .NET có sẵn trong Windows.

    ĐỊNH DẠNG ĐÚNG (khác với thứ py_vapid in ra):
      - Khoá công khai: điểm EC không nén X9.62 (0x04 || X || Y = 65 byte),
                        base64url, bỏ '=' -> 87 ký tự
      - Khoá riêng:     số nguyên private 32 byte, base64url, bỏ '=' -> 43 ký tự

    `print(v.public_key)` của py_vapid in ra ĐỐI TƯỢNG Python
    ("<cryptography...ECPublicKey object at 0x...>"), không phải khoá. Đặt chuỗi đó
    vào .env thì container VẪN khởi động — phép kiểm ${VAR:?} của compose chỉ xét
    biến rỗng hay không — rồi Web Push hỏng âm thầm, không lỗi, không log. Vì vậy
    script này tự kiểm độ dài trước khi in ra.

.EXAMPLE
    .\scripts\windows\gen-vapid-keys.ps1
    .\scripts\windows\gen-vapid-keys.ps1 | Add-Content .env.prod
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

function ConvertTo-Base64Url([byte[]]$Bytes) {
    # base64url = base64 thường, đổi '+'->'-', '/'->'_', bỏ đệm '='. Web Push
    # (RFC 8291) yêu cầu đúng biến thể này; base64 thường sẽ bị trình duyệt từ chối.
    [Convert]::ToBase64String($Bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Get-LeftPadded([byte[]]$Bytes, [int]$Length) {
    # .NET trả về X/Y/D đủ 32 byte cho P-256, nhưng đặc tả không BẢO ĐẢM điều đó —
    # một số backend cắt bỏ byte 0 ở đầu. Thiếu một byte là khoá sai độ dài và
    # Web Push hỏng, nên đệm lại cho chắc thay vì tin vào may mắn.
    if ($Bytes.Length -eq $Length) { return $Bytes }
    if ($Bytes.Length -gt $Length) {
        throw "Thành phần khoá dài $($Bytes.Length) byte, chờ tối đa $Length"
    }
    $out = New-Object byte[] $Length
    [Array]::Copy($Bytes, 0, $out, $Length - $Bytes.Length, $Bytes.Length)
    return $out
}

try {
    $curve = [System.Security.Cryptography.ECCurve]::CreateFromFriendlyName('nistP256')
    $ecdsa = [System.Security.Cryptography.ECDsa]::Create($curve)
}
catch {
    Write-Error @"
Không tạo được khoá EC P-256 bằng .NET: $($_.Exception.Message)

Cần Windows PowerShell 5.1 (kèm .NET Framework 4.6.2+) hoặc PowerShell 7+.
Kiểm phiên bản bằng:  `$PSVersionTable.PSVersion

Cách thay thế nếu máy đã có Docker Desktop chạy:
  docker run --rm python:3.12-alpine sh -c "pip install -q cryptography && python -c \"
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
b=lambda r: base64.urlsafe_b64encode(r).decode().rstrip('=')
k=ec.generate_private_key(ec.SECP256R1())
print('VAPID_PUBLIC_KEY='+b(k.public_key().public_bytes(Encoding.X962,PublicFormat.UncompressedPoint)))
print('VAPID_PRIVATE_KEY='+b(k.private_numbers().private_value.to_bytes(32,'big')))\""
"@
    exit 1
}

try {
    $p = $ecdsa.ExportParameters($true)

    $x = Get-LeftPadded $p.Q.X 32
    $y = Get-LeftPadded $p.Q.Y 32
    $d = Get-LeftPadded $p.D   32

    # X9.62 uncompressed point: 1 byte tiền tố 0x04, rồi X, rồi Y.
    $point = New-Object byte[] 65
    $point[0] = 0x04
    [Array]::Copy($x, 0, $point, 1,  32)
    [Array]::Copy($y, 0, $point, 33, 32)

    $pub  = ConvertTo-Base64Url $point
    $priv = ConvertTo-Base64Url $d

    if ($pub.Length  -ne 87) { throw "Khoá công khai sai độ dài: $($pub.Length), cần 87" }
    if ($priv.Length -ne 43) { throw "Khoá riêng sai độ dài: $($priv.Length), cần 43" }

    Write-Output "# Web Push VAPID - sinh tu dong, KHONG commit hai dong duoi day"
    Write-Output "VAPID_PUBLIC_KEY=$pub"
    Write-Output "VAPID_PRIVATE_KEY=$priv"
}
finally {
    $ecdsa.Dispose()
}
