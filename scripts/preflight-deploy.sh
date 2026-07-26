#!/usr/bin/env bash
# Kiểm tra trước khi deploy — chạy TRƯỚC `docker compose up`.
#
#   ./scripts/preflight-deploy.sh .env.prod
#
# Bắt các lỗi cấu hình mà Docker chỉ phát hiện được lúc chạy, hoặc tệ hơn là
# KHÔNG phát hiện được: giá trị CHANGE_ME vẫn là chuỗi không rỗng nên phép kiểm
# ${VAR:?} của compose cho qua, container khởi động bình thường rồi hỏng ở chỗ
# khác — CORS chặn, tải tệp về 403, Web Push im lặng.
set -uo pipefail

ENV_FILE="${1:-.env.prod}"
cd "$(dirname "$0")/.."

ERR=0
warn() { printf '  ⚠  %s\n' "$*"; }
fail() { printf '  ✗  %s\n' "$*"; ERR=1; }
ok()   { printf '  ✓  %s\n' "$*"; }

get() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- ; }

echo "═══ Kiểm tra trước deploy — $ENV_FILE ═══"
echo

# ── 1. File cấu hình ──────────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
    fail "Không thấy $ENV_FILE. Chạy: cp .env.prod.example $ENV_FILE"
    exit 1
fi

perm=$(stat -c '%a' "$ENV_FILE")
[ "$perm" = "600" ] || warn "$ENV_FILE quyền $perm — nên là 600 (chmod 600 $ENV_FILE)"

# Kiểm chính xác "có bị git THEO DÕI không", không phải "có được ignore không":
# file nằm ngoài repo cũng khiến check-ignore trả false, gây báo động giả.
if git ls-files --error-unmatch "$ENV_FILE" >/dev/null 2>&1; then
    fail "$ENV_FILE ĐANG được git theo dõi — bí mật sẽ bị commit"
else
    ok "$ENV_FILE không bị git theo dõi"
fi

# ── 2. Biến bắt buộc, và phải khác giá trị mẫu ───────────────────────────────
echo
echo "── Biến bắt buộc ──"
REQUIRED=(
    APP_PUBLIC_URL CORS_ORIGINS JWT_SECRET MINIO_PUBLIC_ENDPOINT
    MINIO_ROOT_USER MINIO_ROOT_PASSWORD POSTGRES_PASSWORD REDIS_PASSWORD
    SEED_ADMIN_PASSWORD SMTP_HOST VAPID_PUBLIC_KEY VAPID_PRIVATE_KEY
    CLOUDFLARE_TUNNEL_TOKEN
)
missing=0
for v in "${REQUIRED[@]}"; do
    val=$(get "$v")
    if [ -z "$val" ]; then
        fail "$v chưa có giá trị"; missing=1
    elif [[ "$val" == *CHANGE_ME* ]] || [[ "$val" == *your-domain.example* ]]; then
        # Đây là lỗi hay bị bỏ sót nhất: compose coi CHANGE_ME là hợp lệ vì
        # nó chỉ kiểm chuỗi rỗng.
        fail "$v vẫn là giá trị mẫu ($val)"; missing=1
    fi
done
[ "$missing" = 0 ] && ok "đủ ${#REQUIRED[@]} biến bắt buộc, không còn giá trị mẫu"

# ── 3. Định dạng URL — ba chỗ hay sai nhất ───────────────────────────────────
echo
echo "── Định dạng URL ──"
app=$(get APP_PUBLIC_URL)
for v in APP_PUBLIC_URL CORS_ORIGINS MINIO_PUBLIC_ENDPOINT; do
    val=$(get "$v")
    [ -z "$val" ] && continue
    [[ "$val" == https://* ]] || fail "$v phải bắt đầu bằng https:// (đang: $val)"
    [[ "$val" == */ ]] && fail "$v KHÔNG được có dấu / ở cuối (đang: $val)"
done
# MINIO_PUBLIC_ENDPOINT là ORIGIN, KHÔNG kèm tên bucket: boto3 dùng path-style
# nên tự nối thành {endpoint}/lims-attachments/{key}. Thêm "/lims-attachments"
# vào đây sẽ sinh URL lặp hai lần và tải về 404.
mp=$(get MINIO_PUBLIC_ENDPOINT)
if [ -n "$mp" ] && [[ "$mp" == */lims-attachments* ]]; then
    fail "MINIO_PUBLIC_ENDPOINT không được chứa tên bucket — chỉ là origin (đang: $mp)"
fi
if [ -n "$mp" ] && [ -n "$app" ] && [ "$mp" != "$app" ]; then
    warn "MINIO_PUBLIC_ENDPOINT ($mp) khác APP_PUBLIC_URL ($app)."
    warn "  Thiết kế một-tunnel dùng CHUNG origin; khác nhau thì phải tự route riêng cho MinIO."
fi
cors=$(get CORS_ORIGINS)
if [ -n "$app" ] && [ -n "$cors" ] && [[ "$cors" != *"${app#https://}"* ]]; then
    warn "CORS_ORIGINS ($cors) không chứa tên miền của APP_PUBLIC_URL ($app)"
fi
[ "$ERR" = 0 ] && ok "URL đúng định dạng"

# ── 4. Khoá VAPID — độ dài quyết định tính hợp lệ ────────────────────────────
echo
echo "── Khoá VAPID ──"
pub=$(get VAPID_PUBLIC_KEY); priv=$(get VAPID_PRIVATE_KEY)
if [[ "$pub" == *"object at"* ]] || [[ "$priv" == *"object at"* ]]; then
    fail "Khoá VAPID là đối tượng Python, không phải khoá. Dùng ./scripts/gen-vapid-keys.sh"
elif [ "${#pub}" != 87 ] || [ "${#priv}" != 43 ]; then
    fail "Khoá VAPID sai độ dài (công khai ${#pub}, cần 87; riêng ${#priv}, cần 43)"
else
    ok "khoá VAPID đúng định dạng"
fi

# ── 5. Độ mạnh bí mật ────────────────────────────────────────────────────────
echo
echo "── Độ mạnh bí mật ──"
jwt=$(get JWT_SECRET)
[ "${#jwt}" -lt 32 ] && fail "JWT_SECRET chỉ ${#jwt} ký tự — cần ≥32" || ok "JWT_SECRET ${#jwt} ký tự"
for v in POSTGRES_PASSWORD REDIS_PASSWORD MINIO_ROOT_PASSWORD SEED_ADMIN_PASSWORD; do
    val=$(get "$v")
    [ "${#val}" -lt 12 ] && warn "$v chỉ ${#val} ký tự — nên ≥12"
done
sa=$(get SEED_ADMIN_PASSWORD)
[[ "$sa" == "Lims@1234" || "$sa" == "ChangeMe@123" ]] && \
    fail "SEED_ADMIN_PASSWORD là mật khẩu mặc định đã công khai trong repo"

# ── 6. Môi trường máy ────────────────────────────────────────────────────────
echo
echo "── Máy chủ ──"
if docker compose version >/dev/null 2>&1; then
    ok "docker compose $(docker compose version --short 2>/dev/null)"
else
    fail "Thiếu Docker Compose v2 (lệnh 'docker compose', không phải 'docker-compose')"
fi

cores=$(nproc)
cpus=$(get LIMS_API_CPUS); cpus=${cpus:-2.0}
if awk "BEGIN{exit !($cores < $cpus)}"; then
    fail "Máy có $cores nhân nhưng lims-api yêu cầu $cpus — Docker sẽ từ chối khởi động."
    fail "  Thêm vào $ENV_FILE:  LIMS_API_CPUS=1.0"
else
    ok "$cores nhân ≥ $cpus yêu cầu"
fi

mem=$(free -g | awk '/^Mem:/{print $2}')
[ "$mem" -lt 4 ] && warn "RAM ${mem}GB — khuyến nghị ≥4GB" || ok "RAM ${mem}GB"

disk=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
[ "$disk" -lt 20 ] && warn "Đĩa trống ${disk}GB — khuyến nghị ≥20GB" || ok "đĩa trống ${disk}GB"

# ── Kết luận ─────────────────────────────────────────────────────────────────
echo
if [ "$ERR" = 0 ]; then
    echo "═══ ✓ SẴN SÀNG DEPLOY ═══"
    echo
    echo "  docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml \\"
    echo "                 --env-file $ENV_FILE up -d --build"
else
    echo "═══ ✗ CÒN LỖI — sửa xong rồi chạy lại ═══"
fi
exit "$ERR"
