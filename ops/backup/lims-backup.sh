#!/usr/bin/env bash
# Sao lưu LIMS — PostgreSQL + MinIO. Chạy hằng ngày qua cron.
#
# Thoát != 0 nếu có bất kỳ lỗi nào, để cron gửi mail cảnh báo. Backup im lặng thất
# bại là backup vô dụng đúng lúc cần nhất.
#
# Cài đặt:
#   sudo cp ops/backup/lims-backup.sh /usr/local/bin/lims-backup
#   sudo chmod +x /usr/local/bin/lims-backup
#   echo '0 2 * * * root LIMS_DIR=/opt/lims LIMS_BACKUP_REMOTE=user@host:/lims \
#         /usr/local/bin/lims-backup >> /var/log/lims-backup.log 2>&1' \
#     | sudo tee /etc/cron.d/lims-backup
set -euo pipefail

LIMS_DIR="${LIMS_DIR:-/opt/lims}"
DEST="${LIMS_BACKUP_DIR:-/var/backups/lims}"
REMOTE="${LIMS_BACKUP_REMOTE:-}"          # vd: user@backup-host:/lims
KEEP_DAYS="${LIMS_BACKUP_KEEP_DAYS:-14}"
TS="$(date +%F_%H%M)"

log() { echo "[lims-backup] $*"; }

mkdir -p "$DEST"
cd "$LIMS_DIR"

# ── Tên volume MinIO ──
# Docker Compose gắn tiền tố tên project vào tên volume (thư mục 'limb' ⇒
# limb_lims_miniodata). Hard-code 'lims_miniodata' sẽ trỏ vào một volume RỖNG khác
# và tạo ra bản backup 0 byte mà vẫn báo thành công. Hỏi chính compose cho chắc.
MINIO_VOL="$(docker compose config --format json \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["volumes"]["lims_miniodata"]["name"])')"
log "MinIO volume: $MINIO_VOL"

# ── PostgreSQL ──
# -Fc (custom format): nén sẵn, restore chọn lọc từng bảng được.
log "dump PostgreSQL..."
docker compose exec -T postgres pg_dump -U lims -Fc lims > "$DEST/db-$TS.dump"

# Dump hỏng mà không biết còn tệ hơn không có dump. pg_restore --list đọc được
# nghĩa là header + TOC còn nguyên.
docker run --rm -i postgres:15-alpine pg_restore --list < "$DEST/db-$TS.dump" > /dev/null
DB_SIZE=$(stat -c%s "$DEST/db-$TS.dump")
[ "$DB_SIZE" -gt 1024 ] || { log "LỖI: dump chỉ $DB_SIZE byte"; exit 1; }
log "  db-$TS.dump — $((DB_SIZE / 1024)) KB, pg_restore --list OK"

# ── MinIO ──
log "archive MinIO..."
docker run --rm -v "$MINIO_VOL":/data:ro -v "$DEST":/backup alpine \
  tar czf "/backup/files-$TS.tar.gz" -C /data .
FILE_SIZE=$(stat -c%s "$DEST/files-$TS.tar.gz")
# tar rỗng ~ 45 byte. Ngưỡng 1KB bắt được đúng lỗi "trỏ nhầm volume".
[ "$FILE_SIZE" -gt 1024 ] || { log "LỖI: archive MinIO chỉ $FILE_SIZE byte — sai volume?"; exit 1; }
log "  files-$TS.tar.gz — $((FILE_SIZE / 1024)) KB"

# ── Dọn bản cũ ──
find "$DEST" -name 'db-*.dump'      -mtime "+$KEEP_DAYS" -delete
find "$DEST" -name 'files-*.tar.gz' -mtime "+$KEEP_DAYS" -delete

# ── Đưa ra khỏi host ──
# Backup nằm cùng máy với dữ liệu gốc thì hỏng ổ là mất cả hai.
if [ -n "$REMOTE" ]; then
  log "đồng bộ tới $REMOTE..."
  rsync -a --delete "$DEST/" "$REMOTE/"
else
  log "CẢNH BÁO: LIMS_BACKUP_REMOTE chưa đặt — backup CHỈ nằm trên host này"
fi

log "HOÀN TẤT $TS"
