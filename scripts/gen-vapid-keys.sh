#!/usr/bin/env bash
# Sinh cặp khoá Web Push VAPID ở đúng định dạng ứng dụng cần.
#
#   ./scripts/gen-vapid-keys.sh >> .env
#
# VÌ SAO LÀ SCRIPT CHỨ KHÔNG PHẢI LỆNH MỘT DÒNG: py_vapid trả về ĐỐI TƯỢNG khoá
# của thư viện cryptography, không phải chuỗi. `print(v.public_key)` in ra
# "<cryptography...ECPublicKey object at 0x7f...>" — rác. Đặt rác đó vào .env thì
# container VẪN KHỞI ĐỘNG (kiểm tra ${VAR:?} chỉ xét rỗng hay không) rồi Web Push
# hỏng âm thầm, không lỗi, không log.
#
# Định dạng đúng:
#   - Khoá công khai: điểm EC không nén (X9.62), base64url, bỏ '=' — 87 ký tự
#   - Khoá riêng:     số nguyên private 32 byte, base64url, bỏ '='  — 43 ký tự
set -euo pipefail

cd "$(dirname "$0")/.."

docker compose run --rm --no-deps -T --entrypoint python lims-api - <<'PY'
import base64

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


key = ec.generate_private_key(ec.SECP256R1())

pub = b64(key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint))
priv = b64(key.private_numbers().private_value.to_bytes(32, "big"))

assert len(pub) == 87, f"khoá công khai sai độ dài: {len(pub)}"
assert len(priv) == 43, f"khoá riêng sai độ dài: {len(priv)}"

print("# Web Push VAPID — sinh tự động, KHÔNG commit hai dòng dưới đây")
print(f"VAPID_PUBLIC_KEY={pub}")
print(f"VAPID_PRIVATE_KEY={priv}")
PY
