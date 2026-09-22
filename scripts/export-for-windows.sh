#!/usr/bin/env bash
# Đóng gói TOÀN BỘ trạng thái LIMS trên máy Linux này để mang sang máy Windows.
#
#   ./scripts/export-for-windows.sh [thư-mục-đích]
#
# Sinh ra một thư mục chứa 4 thứ, đủ để dựng lại y hệt:
#   db.dump          — Postgres, định dạng custom (-Fc)
#   minio-files.tar.gz — toàn bộ file đính kèm trong MinIO
#   env.prod         — bản sao .env.prod (CHỨA BÍ MẬT — xem cảnh báo cuối script)
#   SHA256SUMS.txt   — để bên Windows kiểm file có sang nguyên vẹn không
#
# Vì sao phải dump chứ không copy thẳng thư mục volume: dữ liệu Postgres trên đĩa
# phụ thuộc kiến trúc CPU, phiên bản và locale của initdb. Copy thư mục
# /var/lib/postgresql/data giữa hai máy là cách hỏng dữ liệu rất im lặng — server
# khởi động được, rồi index sai thứ tự sắp xếp. pg_dump/pg_restore đi qua SQL nên
# không có lớp phụ thuộc đó.
set -euo pipefail

cd "$(dirname "$0")/.."
LIMS_DIR="$PWD"

DEST="${1:-$HOME/lims-export-$(date +%F_%H%M)}"
ENV_FILE="${LIMS_ENV_FILE:-.env.prod}"

log()  { printf '[export] %s\n' "$*"; }
fail() { printf '[export] LỖI: %s\n' "$*" >&2; exit 1; }

[ -f "$ENV_FILE" ] || fail "không thấy $ENV_FILE trong $LIMS_DIR"

# Hồ sơ compose phải chỉ định tường minh. `docker compose` trần sẽ nạp
# docker-compose.yml (hồ sơ DEV) nếu COMPOSE_FILE trong .env vì lý do gì đó không
# được đọc — và khi đó script dump nhầm stack mà vẫn báo thành công.
COMPOSE=(docker compose
         -f "$LIMS_DIR/docker-compose.prod.yml"
         -f "$LIMS_DIR/docker-compose.cloudflare.yml"
         --env-file "$LIMS_DIR/$ENV_FILE")

"${COMPOSE[@]}" ps --status running --services 2>/dev/null | grep -q '^postgres$' \
    || fail "container postgres không chạy — không dump được. Chạy stack lên trước."

mkdir -p "$DEST"
chmod 700 "$DEST"
log "thư mục đích: $DEST"

# ── 1. Postgres ───────────────────────────────────────────────────────────────
log "dump Postgres..."
"${COMPOSE[@]}" exec -T postgres pg_dump -U lims -Fc lims > "$DEST/db.dump"

# Dump hỏng mà không biết còn tệ hơn không có dump. pg_restore --list đọc được
# nghĩa là header + mục lục còn nguyên vẹn.
docker run --rm -i postgres:15-alpine pg_restore --list < "$DEST/db.dump" > /dev/null \
    || fail "db.dump không đọc được bằng pg_restore — dump hỏng"
DB_SIZE=$(stat -c%s "$DEST/db.dump")
[ "$DB_SIZE" -gt 1024 ] || fail "db.dump chỉ $DB_SIZE byte"
log "  db.dump — $((DB_SIZE / 1024)) KB, pg_restore --list OK"

# ── 2. MinIO ──────────────────────────────────────────────────────────────────
# Hỏi chính compose tên volume thay vì đoán: compose gắn tiền tố tên project vào
# tên volume, hard-code 'lims_miniodata' sẽ trỏ vào một volume RỖNG khác và tạo ra
# bản backup 0 byte mà vẫn báo thành công.
MINIO_VOL="$("${COMPOSE[@]}" config --format json \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["volumes"]["lims_miniodata"]["name"])')"
log "archive MinIO (volume: $MINIO_VOL)..."
docker run --rm -v "$MINIO_VOL":/data:ro -v "$DEST":/backup alpine \
    tar czf /backup/minio-files.tar.gz -C /data .
FILE_SIZE=$(stat -c%s "$DEST/minio-files.tar.gz")
# tar rỗng ~45 byte. Ngưỡng 1KB bắt đúng lỗi "trỏ nhầm volume".
[ "$FILE_SIZE" -gt 1024 ] || fail "minio-files.tar.gz chỉ $FILE_SIZE byte — sai volume?"
log "  minio-files.tar.gz — $((FILE_SIZE / 1024)) KB"

# ── 3. Cấu hình ───────────────────────────────────────────────────────────────
# Đặt tên 'env.prod' (không có dấu chấm đầu) để file không bị ẩn khi copy qua USB
# và để không bị .gitignore nuốt mất nếu ai đó lỡ đặt thư mục export trong repo.
cp "$ENV_FILE" "$DEST/env.prod"
chmod 600 "$DEST/env.prod"
log "  env.prod — bản sao $ENV_FILE"

# ── 4. Checksum ───────────────────────────────────────────────────────────────
( cd "$DEST" && sha256sum db.dump minio-files.tar.gz env.prod > SHA256SUMS.txt )
log "  SHA256SUMS.txt"

# ── 5. Ghi lại phiên bản đang chạy ────────────────────────────────────────────
# Để bên Windows đối chiếu: nếu image khác phiên bản thì đó là biến số đầu tiên
# cần loại trừ khi có gì đó chạy khác đi.
{
    echo "# Trạng thái máy nguồn lúc export — $(date -Is)"
    echo "git_commit=$(git -C "$LIMS_DIR" rev-parse HEAD 2>/dev/null || echo 'không phải git repo')"
    echo "git_dirty=$(git -C "$LIMS_DIR" status --porcelain 2>/dev/null | wc -l) file thay đổi chưa commit"
    echo "docker=$(docker --version)"
    echo "compose=$(docker compose version --short)"
    echo "minio=$(docker exec lims-minio minio --version 2>/dev/null | head -1 || echo '?')"
    echo "postgres=$(docker exec lims-postgres postgres --version 2>/dev/null || echo '?')"
    echo "alembic_head=$("${COMPOSE[@]}" exec -T postgres psql -U lims -d lims -tAc \
        'SELECT version_num FROM alembic_version;' 2>/dev/null || echo '?')"
} > "$DEST/SOURCE-INFO.txt"
log "  SOURCE-INFO.txt"

cat <<EOF

═══ Xong — $DEST ═══

$(ls -lh "$DEST" | tail -n +2 | awk '{printf "  %-22s %s\n", $9, $5}')

⚠  env.prod CHỨA TOÀN BỘ MẬT KHẨU HẠ TẦNG + token Cloudflare.
   Chuyển qua kênh có mã hoá (USB đã mã hoá / SFTP / 7-Zip đặt mật khẩu), KHÔNG
   gửi qua Zalo/email/Drive không mã hoá. Xoá bản trung gian sau khi deploy xong.

Nén lại cho gọn khi mang đi:
   tar czf "$DEST.tar.gz" -C "$(dirname "$DEST")" "$(basename "$DEST")"

Bước tiếp theo ở máy Windows: xem DEPLOY_WINDOWS.md — GIAI ĐOẠN 4.
EOF
