#!/usr/bin/env bash
# Chạy test backend trong container có đủ dev deps.
#
#   ./scripts/test-backend.sh                    # toàn bộ
#   ./scripts/test-backend.sh app/tests/architecture -v
#   ./scripts/test-backend.sh -k "sample_flow"
#
# Tự tạo DB lims_test nếu chưa có, để test integration không bị skip im lặng.
# Xem MAINTAINABILITY_PLAN.md §T2.1.
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.test.yml)

# Postgres phải sẵn sàng trước khi tạo DB test.
"${COMPOSE[@]}" up -d postgres redis >/dev/null

if ! "${COMPOSE[@]}" exec -T postgres psql -U lims -lqt | cut -d'|' -f1 | grep -qw lims_test; then
    echo "→ tạo database lims_test"
    "${COMPOSE[@]}" exec -T postgres createdb -U lims lims_test
fi

# Mã nguồn app/ được mount vào container nên KHÔNG cần rebuild mỗi lần chạy —
# chỉ rebuild khi requirements đổi. REBUILD=1 để ép build lại.
BUILD_ARGS=()
if [ "${REBUILD:-0}" = "1" ] || ! docker image inspect limb-lims-test >/dev/null 2>&1; then
    BUILD_ARGS=(--build)
fi

exec "${COMPOSE[@]}" run --rm "${BUILD_ARGS[@]}" lims-test \
    python -m pytest "${@:-app/tests}" -q
