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

# ── CHỐT AN TOÀN: KHÔNG chạy đè lên stack production ──
#
# Sự cố đã xảy ra thật (2026-08-07): script này gọi `docker compose` với hồ sơ DEV
# trong khi production chạy từ CÙNG thư mục (cùng tên project `lims`). Docker coi đó
# là cùng một project và RECREATE `lims-postgres` + `lims-redis` theo định nghĩa dev:
#   - Redis mất `--requirepass`  → jti denylist, lockout, rate limit mở toang
#   - Postgres/Redis publish cổng ra host (5460/6460) → lộ ra ngoài container
# Dữ liệu không mất (volume giữ nguyên) nhưng cấu hình bảo mật bị hạ cấp im lặng.
#
# Cùng một cạm bẫy với ops/RUNBOOK.md — xem docs/SECURITY_AUDIT.md S-09.
if docker ps --filter "name=^lims-api$" --filter "status=running" --format '{{.Names}}' \
   | grep -q .; then
    cat >&2 <<'MSG'
✗ TỪ CHỐI CHẠY: stack production (lims-api) đang chạy từ thư mục này.

  Chạy test bằng hồ sơ dev sẽ recreate lims-postgres/lims-redis theo cấu hình DEV
  (Redis mất mật khẩu, DB publish cổng ra host).

  Chọn một trong hai:
    1) Dừng production trước:
         docker compose -f docker-compose.prod.yml -f docker-compose.cloudflare.yml \
                        --env-file .env.prod down
    2) Chạy test trên hạ tầng cô lập (khuyến nghị — không đụng production):
         ./scripts/test-backend-isolated.sh [đối số pytest...]
MSG
    exit 1
fi

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
