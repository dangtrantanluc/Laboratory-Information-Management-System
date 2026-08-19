#!/usr/bin/env bash
# Dựng bản XEM THỬ của LIMS với code hiện tại + dữ liệu demo NCKH/Đào tạo.
#
#   ./scripts/preview-demo.sh          # dựng và seed
#   ./scripts/preview-demo.sh --down   # dẹp sạch
#
# VÌ SAO KHÔNG DÙNG docker-compose.yml
#
# Hồ sơ dev đặt container_name CỨNG (lims-postgres, lims-api, lims-web…) đúng bằng
# tên container production đang chạy từ cùng thư mục này. `docker compose up` — kể cả
# với -p khác — sẽ đụng tên và trong trường hợp xấu recreate container production
# theo cấu hình dev (đã xảy ra thật 2026-08-07: Redis mất mật khẩu, DB publish cổng
# ra host). Xem chốt an toàn trong scripts/test-backend.sh.
#
# Script này tự dựng container tên riêng, mạng riêng, volume riêng. Mẹo duy nhất cần
# biết: nginx của frontend proxy_pass tới hostname CỨNG `lims-api`, nên container API
# ở đây đặt tên lims-demo-api nhưng mang NETWORK ALIAS `lims-api` — trùng tên trong
# mạng demo, không đụng gì bên ngoài.
set -euo pipefail

cd "$(dirname "$0")/.."

NET=lims-demo-net
DB=lims-demo-db
REDIS=lims-demo-redis
MINIO=lims-demo-minio
API=lims-demo-api
WEB=lims-demo-web
API_IMAGE=lims-demo-api:latest
WEB_IMAGE=lims-demo-web:latest
# VS Code tự chuyển tiếp cổng của container và GIỮ chuyển tiếp đó sau khi container
# chết, nên cổng cố định hay bị chiếm giữa hai lần chạy. Chọn cổng trống đầu tiên.
pick_port() {
    for p in "$@"; do
        if ! (exec 3<>"/dev/tcp/127.0.0.1/$p") 2>/dev/null; then echo "$p"; return; fi
        exec 3<&- 2>/dev/null || true
    done
    echo "✗ Không còn cổng trống trong dải $*" >&2
    exit 1
}
WEB_PORT=$(pick_port 3070 3071 3072 3073)
API_PORT=$(pick_port 8070 8071 8072 8073)

ADMIN_EMAIL=admin@lims.local
ADMIN_PASSWORD='ChangeMe@123'

down() {
    docker rm -f "$WEB" "$API" "$MINIO" "$REDIS" "$DB" >/dev/null 2>&1 || true
    docker network rm "$NET" >/dev/null 2>&1 || true
}

if [ "${1:-}" = "--down" ]; then
    down
    echo "✔ Đã dẹp bản xem thử."
    exit 0
fi

# Chốt an toàn: tên container demo không được trùng bất kỳ container nào đang chạy.
for name in "$DB" "$REDIS" "$MINIO" "$API" "$WEB"; do
    case "$name" in
        lims-postgres|lims-redis|lims-api|lims-web|lims-minio|lims-cloudflared)
            echo "✗ TỪ CHỐI: '$name' trùng tên container production." >&2
            exit 1
            ;;
    esac
done

down  # dọn tàn dư lần trước

echo "→ mạng + hạ tầng riêng"
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" \
    -e POSTGRES_USER=lims -e POSTGRES_PASSWORD=lims -e POSTGRES_DB=lims \
    postgres:15-alpine >/dev/null
docker run -d --name "$REDIS" --network "$NET" redis:7-alpine >/dev/null
# MinIO BẮT BUỘC dù demo không dùng tệp đính kèm: nginx.conf có upstream "minio" và
# nginx từ chối khởi động khi không phân giải được hostname trong cấu hình.
docker run -d --name "$MINIO" --network "$NET" --network-alias minio \
    -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
    minio/minio:latest server /data >/dev/null

echo "→ build API (code hiện tại, gồm migration m34)"
docker build -q -t "$API_IMAGE" ./lims-backend >/dev/null

echo "→ build Web (bundle gọi /api/v1, nginx proxy sang lims-api)"
docker build -q -t "$WEB_IMAGE" --build-arg VITE_API_BASE_URL=/api/v1 ./lims-frontend >/dev/null

echo "→ chờ Postgres"
for _ in $(seq 1 30); do
    docker exec "$DB" pg_isready -U lims -d lims >/dev/null 2>&1 && break
    sleep 1
done

echo "→ khởi động API (entrypoint tự chạy alembic upgrade head)"
docker run -d --name "$API" --network "$NET" --network-alias lims-api \
    -e DATABASE_URL="postgresql+psycopg2://lims:lims@$DB:5432/lims" \
    -e REDIS_URL="redis://$REDIS:6379/0" \
    -e JWT_SECRET=demo_only_not_a_real_secret_min_32_characters_long \
    -e ENVIRONMENT=development \
    -e MINIO_ENDPOINT="http://$MINIO:9000" \
    -e MINIO_ACCESS_KEY=minioadmin -e MINIO_SECRET_KEY=minioadmin \
    -e MINIO_BUCKET=lims-demo \
    -e SEED_ADMIN_EMAIL="$ADMIN_EMAIL" -e SEED_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
    -e CORS_ORIGINS="http://localhost:$WEB_PORT" \
    -e UVICORN_WORKERS=2 \
    -e VAPID_PUBLIC_KEY=demo -e VAPID_PRIVATE_KEY=demo -e VAPID_CLAIMS_EMAIL="$ADMIN_EMAIL" \
    -p "$API_PORT:8060" \
    "$API_IMAGE" >/dev/null

echo "→ chờ API sẵn sàng (migration chạy trong entrypoint)"
for i in $(seq 1 60); do
    if docker exec "$API" python -c "
import urllib.request;urllib.request.urlopen('http://localhost:8060/health',timeout=2)" \
       >/dev/null 2>&1; then
        break
    fi
    [ "$i" = 60 ] && { echo "✗ API không lên. Nhật ký:"; docker logs --tail 40 "$API"; exit 1; }
    sleep 2
done

echo "→ seed dữ liệu demo NCKH & Đào tạo"
docker exec "$API" python scripts/seed_demo_research_2024_2025.py

echo "→ tài khoản thử theo vai trò (admin / lãnh đạo / văn phòng / KTV…)"
docker exec "$API" python scripts/seed_role_accounts.py >/dev/null 2>&1 \
    || echo "  (bỏ qua — seed_role_accounts cần phòng ban, không bắt buộc cho demo)"

echo "→ khởi động Web"
docker run -d --name "$WEB" --network "$NET" -p "$WEB_PORT:80" "$WEB_IMAGE" >/dev/null
sleep 2
if [ "$(docker inspect -f '{{.State.Running}}' "$WEB")" != "true" ]; then
    echo "✗ Web không chạy. Nhật ký:" >&2
    docker logs --tail 20 "$WEB" >&2
    exit 1
fi

cat <<EOF

═══════════════════════════════════════════════════════════════
  BẢN XEM THỬ SẴN SÀNG        http://localhost:$WEB_PORT
  API (nếu cần gọi trực tiếp) http://localhost:$API_PORT/api/v1

  Đăng nhập:  $ADMIN_EMAIL / $ADMIN_PASSWORD
  Vai trò khác (nếu seed được): vanphong@lims.local / Lims@1234

  Xem các thay đổi ở:
    Nghiên cứu ▸ Đề tài NCKH        kinh phí · chuyển giao · chủ nhiệm ngoài HT · minh chứng
    Nghiên cứu ▸ Bài báo & Sáng chế loại "Hội nghị/kỷ yếu" · phạm vi · SCIE/Scopus ·
                                     3 loại văn bằng · số đơn/ngày cấp/chủ bằng
    Nghiên cứu ▸ Hợp đồng NCKH      số hợp đồng · ngày ký · minh chứng
    Đào tạo    ▸ Môn giảng dạy      bậc ĐH/SĐH · bảng 3 học kỳ · thỉnh giảng
    Đào tạo    ▸ Chứng nhận đào tạo lớp ngắn hạn ↔ tập huấn an toàn PTN
    Công tác khác                   Đảng · Công đoàn · VILAS + minh chứng

  KHÔNG đụng tới stack production đang chạy.
  Dẹp:  ./scripts/preview-demo.sh --down
═══════════════════════════════════════════════════════════════
EOF
