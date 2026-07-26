#!/usr/bin/env bash
# Sinh cặp khoá Web Push VAPID ở đúng định dạng ứng dụng cần.
#
#   ./scripts/gen-vapid-keys.sh >> .env.prod
#
# CỐ Ý KHÔNG DÙNG `docker compose`: docker-compose.yml khai
# ${VAPID_PRIVATE_KEY:?...}, mà compose phân giải TOÀN BỘ biến trước khi chạy bất
# cứ thứ gì. Dùng compose ở đây tạo ra vòng luẩn quẩn — cần khoá để sinh ra khoá:
#
#   error while interpolating services.lims-api.environment.VAPID_PRIVATE_KEY:
#   required variable VAPID_PRIVATE_KEY is missing a value
#
# Script chạy độc lập: ưu tiên python3 sẵn có trên máy, không có thì mượn một
# container python dùng một lần. Không đọc, không cần file compose nào.
#
# ĐỊNH DẠNG ĐÚNG (khác với thứ py_vapid in ra):
#   - Khoá công khai: điểm EC không nén (X9.62, 65 byte), base64url, bỏ '=' → 87 ký tự
#   - Khoá riêng:     số nguyên private 32 byte, base64url, bỏ '='          → 43 ký tự
#
# `print(v.public_key)` của py_vapid in ra ĐỐI TƯỢNG Python
# ("<cryptography...ECPublicKey object at 0x...>"), không phải khoá. Đặt chuỗi đó
# vào .env thì container VẪN khởi động — ${VAR:?} chỉ xét biến rỗng hay không —
# rồi Web Push hỏng âm thầm, không lỗi, không log.
set -euo pipefail

PYSRC='
import base64

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


key = ec.generate_private_key(ec.SECP256R1())
pub = b64(key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint))
priv = b64(key.private_numbers().private_value.to_bytes(32, "big"))

assert len(pub) == 87, f"khoa cong khai sai do dai: {len(pub)}"
assert len(priv) == 43, f"khoa rieng sai do dai: {len(priv)}"

print("# Web Push VAPID — sinh tu dong, KHONG commit hai dong duoi day")
print(f"VAPID_PUBLIC_KEY={pub}")
print(f"VAPID_PRIVATE_KEY={priv}")
'

# 1) python3 trên máy, nếu đã có thư viện cryptography
if command -v python3 >/dev/null 2>&1 && python3 -c 'import cryptography' >/dev/null 2>&1; then
    exec python3 -c "$PYSRC"
fi

# 2) Mượn container python dùng một lần. `docker run` KHÔNG đọc file compose nên
#    không vướng biến ${VAPID_PRIVATE_KEY:?...}.
if command -v docker >/dev/null 2>&1; then
    echo "→ máy không có python3+cryptography, dùng container tạm..." >&2
    exec docker run --rm -i python:3.12-alpine sh -c \
        'pip install --quiet --disable-pip-version-check cryptography >/dev/null 2>&1 && python -' <<PY
$PYSRC
PY
fi

cat >&2 <<'EOF'
✗ Cần một trong hai:
    - python3 kèm thư viện cryptography:   pip3 install cryptography
    - hoặc docker (để mượn container tạm)
EOF
exit 1
