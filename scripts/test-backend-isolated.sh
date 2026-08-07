#!/usr/bin/env bash
# Chạy test backend trên hạ tầng HOÀN TOÀN TÁCH BIỆT khỏi mọi stack đang chạy.
#
#   ./scripts/test-backend-isolated.sh                       # toàn bộ
#   ./scripts/test-backend-isolated.sh app/tests/security -v
#   ./scripts/test-backend-isolated.sh -k "quotation"
#
# VÌ SAO CÓ FILE NÀY (và vì sao không dùng docker compose)
#
# `test-backend.sh` dùng `docker compose` với hồ sơ dev. Khi production chạy từ CÙNG
# thư mục, Docker coi cả hai là một project (tên project = tên thư mục) và recreate
# lims-postgres/lims-redis theo cấu hình dev — Redis mất mật khẩu, DB publish cổng ra
# host. Đã xảy ra thật ngày 2026-08-07.
#
# Script này không đụng tới compose: nó tự dựng container riêng, tên riêng, mạng riêng,
# và dọn sạch khi xong. Chạy được song song với production mà không ảnh hưởng gì.
set -euo pipefail

cd "$(dirname "$0")/.."

NET=lims-pytest-net
DB=lims-pytest-db
REDIS=lims-pytest-redis
IMAGE=lims-test-local:latest

cleanup() {
    docker rm -f "$DB" "$REDIS" >/dev/null 2>&1 || true
    docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup   # dọn tàn dư của lần chạy trước (vd bị Ctrl-C)

echo "→ dựng hạ tầng test cô lập"
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" \
    -e POSTGRES_USER=lims -e POSTGRES_PASSWORD=lims -e POSTGRES_DB=lims_test \
    postgres:15-alpine >/dev/null
docker run -d --name "$REDIS" --network "$NET" redis:7-alpine >/dev/null

# Build image test nếu chưa có (hoặc REBUILD=1). Mã nguồn được mount lúc chạy nên
# sửa test không cần build lại — chỉ build khi requirements đổi.
if [ "${REBUILD:-0}" = "1" ] || ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "→ build image test"
    docker build -q -f lims-backend/Dockerfile.test -t "$IMAGE" lims-backend >/dev/null
fi

echo "→ chờ Postgres"
for _ in $(seq 1 30); do
    docker exec "$DB" pg_isready -U lims -d lims_test >/dev/null 2>&1 && break
    sleep 1
done

echo "→ pytest"
docker run --rm --network "$NET" \
    -v "$PWD/lims-backend/app:/app/app:ro" \
    -v "$PWD/lims-backend/.coveragerc:/app/.coveragerc:ro" \
    -e DATABASE_URL="postgresql+psycopg2://lims:lims@$DB:5432/lims_test" \
    -e TEST_DATABASE_URL="postgresql+psycopg2://lims:lims@$DB:5432/lims_test" \
    -e REDIS_URL="redis://$REDIS:6379/1" \
    -e JWT_SECRET=test-only-secret-not-used-anywhere-else \
    -e ENVIRONMENT=development \
    -e MINIO_ENDPOINT=http://minio-unused:9000 \
    -e MINIO_ACCESS_KEY=test -e MINIO_SECRET_KEY=testtest -e MINIO_BUCKET=lims-test \
    "$IMAGE" \
    python -m pytest "${@:-app/tests}" -q
