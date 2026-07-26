#!/usr/bin/env bash
# Điền .env.prod: sinh mọi bí mật, đặt URL theo tên miền, giữ nguyên phần đã có.
#
#   ./scripts/init-env-prod.sh lims.tenmien.com
#
# Chỉ ghi đè các dòng còn giá trị mẫu (CHANGE_ME_*, your-domain.example) — giá
# trị bạn đã tự điền được giữ nguyên, nên chạy lại nhiều lần vẫn an toàn.
#
# Hai thứ script KHÔNG tự làm được, phải điền tay sau đó:
#   - CLOUDFLARE_TUNNEL_TOKEN  (lấy từ dashboard Cloudflare)
#   - SMTP_USER / SMTP_PASSWORD
set -euo pipefail

cd "$(dirname "$0")/.."

DOMAIN="${1:-}"
ENV_FILE="${2:-.env.prod}"

if [ -z "$DOMAIN" ]; then
    cat >&2 <<'EOF'
Cách dùng: ./scripts/init-env-prod.sh <tên-miền> [file]

  ./scripts/init-env-prod.sh lims.vienccnsh.edu.vn

Tên miền KHÔNG kèm https:// và không có / ở cuối.
EOF
    exit 1
fi

# Chặn lỗi hay gặp: dán cả https:// hoặc dấu / cuối vào tham số.
DOMAIN="${DOMAIN#https://}"
DOMAIN="${DOMAIN#http://}"
DOMAIN="${DOMAIN%/}"

if [ ! -f "$ENV_FILE" ]; then
    cp .env.prod.example "$ENV_FILE"
    echo "→ tạo $ENV_FILE từ mẫu"
fi
chmod 600 "$ENV_FILE"

rnd() { openssl rand -base64 "$1" | tr -dc 'A-Za-z0-9' | head -c "$2"; }

_current() { grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- ; }

# Chỉ đặt khi biến đang rỗng hoặc còn là giá trị mẫu.
setv() {
    local key="$1" val="$2" cur
    cur=$(_current "$key")
    # admin@lims.local là tài khoản demo được liệt kê công khai trong acc.txt —
    # phải thay, không được coi là "giá trị người dùng đã tự điền".
    if [ -n "$cur" ] && [[ "$cur" != *CHANGE_ME* ]] && [[ "$cur" != *your-domain.example* ]] \
       && [[ "$cur" != *@lims.local ]]; then
        printf '  ·  %-28s giữ nguyên giá trị đã có\n' "$key"
        return
    fi
    if grep -qE "^$key=" "$ENV_FILE"; then
        # Dùng | làm phân cách vì giá trị có chứa /
        sed -i "s|^$key=.*|$key=$val|" "$ENV_FILE"
    else
        printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
    fi
    case "$key" in
        *PASSWORD*|*SECRET*|*TOKEN*|*KEY*) printf '  ✓  %-28s (đã sinh, không hiển thị)\n' "$key" ;;
        *) printf '  ✓  %-28s %s\n' "$key" "$val" ;;
    esac
}

echo "═══ Điền $ENV_FILE cho $DOMAIN ═══"
echo
# URL là giá trị SUY RA từ tham số $DOMAIN bạn vừa đưa, không phải bí mật ngẫu
# nhiên — nên LUÔN đặt lại theo tham số, khác với setv().
#
# Nếu không: chạy nhầm tên miền một lần rồi chạy lại với tên miền đúng sẽ bị
# "giữ nguyên giá trị đã có", tức là âm thầm deploy bằng tên miền sai và lỗi CORS
# chỉ lộ ra khi người dùng mở trình duyệt.
setv_url() {
    local key="$1" val="$2" cur
    cur=$(_current "$key")
    if [ "$cur" = "$val" ]; then
        printf '  ✓  %-28s %s\n' "$key" "$val"
    else
        [ -n "$cur" ] && [[ "$cur" != *CHANGE_ME* ]] && [[ "$cur" != *your-domain.example* ]] \
            && printf '  ↻  %-28s %s → %s\n' "$key" "$cur" "$val" \
            || printf '  ✓  %-28s %s\n' "$key" "$val"
        sed -i "s|^$key=.*|$key=$val|" "$ENV_FILE"
    fi
}

echo "── URL (cả ba dùng CHUNG một origin: thiết kế một-tunnel) ──"
setv_url APP_PUBLIC_URL        "https://$DOMAIN"
setv_url CORS_ORIGINS          "https://$DOMAIN"
# KHÔNG kèm tên bucket: boto3 path-style tự nối /lims-attachments/{key}.
setv_url MINIO_PUBLIC_ENDPOINT "https://$DOMAIN"

echo
echo "── Bí mật ──"
setv JWT_SECRET          "$(openssl rand -hex 32)"
setv POSTGRES_PASSWORD   "$(rnd 32 28)"
setv REDIS_PASSWORD      "$(rnd 32 28)"
setv MINIO_ROOT_USER     "lims-$(openssl rand -hex 4)"
setv MINIO_ROOT_PASSWORD "$(rnd 32 28)"
setv SEED_ADMIN_PASSWORD "$(rnd 24 20)"

echo
echo "── Khoá Web Push VAPID ──"
if [ -z "$(_current VAPID_PUBLIC_KEY)" ] || [[ "$(_current VAPID_PUBLIC_KEY)" == *CHANGE_ME* ]]; then
    tmp=$(mktemp); ./scripts/gen-vapid-keys.sh > "$tmp"
    setv VAPID_PUBLIC_KEY  "$(grep '^VAPID_PUBLIC_KEY='  "$tmp" | cut -d= -f2)"
    setv VAPID_PRIVATE_KEY "$(grep '^VAPID_PRIVATE_KEY=' "$tmp" | cut -d= -f2)"
    rm -f "$tmp"
else
    printf '  ·  %-28s giữ nguyên khoá đã có\n' "VAPID_*"
fi
setv VAPID_CLAIMS_EMAIL "admin@$DOMAIN"
setv SEED_ADMIN_EMAIL   "admin@$DOMAIN"

echo
echo "── Còn lại — PHẢI điền tay ──"
for k in CLOUDFLARE_TUNNEL_TOKEN SMTP_HOST SMTP_USER SMTP_PASSWORD; do
    cur=$(_current "$k")
    if [ -z "$cur" ] || [[ "$cur" == *CHANGE_ME* ]]; then
        printf '  ✗  %-28s chưa có\n' "$k"
    else
        printf '  ✓  %-28s đã điền\n' "$k"
    fi
done

cat <<EOF

═══ Việc còn lại ═══

  1. Token tunnel — Cloudflare Dashboard → Zero Trust → Networks → Tunnels
     → Create tunnel → copy token, rồi:
       sed -i 's|^CLOUDFLARE_TUNNEL_TOKEN=.*|CLOUDFLARE_TUNNEL_TOKEN=<token>|' $ENV_FILE

     Trong tab Public Hostname đặt:  $DOMAIN  →  HTTP  →  lims-web:80
     (lims-web:80 là tên service trong mạng docker, KHÔNG phải localhost)

  2. SMTP — ví dụ Gmail cần App Password 16 ký tự:
       SMTP_HOST=smtp.gmail.com  SMTP_PORT=587  SMTP_STARTTLS=true

  3. Kiểm lại rồi mới chạy:
       ./scripts/preflight-deploy.sh $ENV_FILE

  Mật khẩu admin lần đầu (ĐỔI NGAY sau khi đăng nhập):
       grep '^SEED_ADMIN_PASSWORD=' $ENV_FILE
EOF
