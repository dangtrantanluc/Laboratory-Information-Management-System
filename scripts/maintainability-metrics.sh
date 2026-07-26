#!/usr/bin/env bash
# Ba chỉ số theo dõi khả năng bảo trì (MAINTAINABILITY_PLAN.md §0.3).
#
# Chạy mỗi sprint, dán kết quả vào bảng trong plan. Không tiến bộ ba tháng liên
# tiếp = kế hoạch đã chết, cần xem lại chứ không cần cố thêm.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "═══ Chỉ số bảo trì — $(date +%F) ═══"

# Định nghĩa PHẢI khớp app/tests/architecture/test_response_contract.py:
# endpoint trả 204 không có body nên không cần response_model.
missing=$(docker compose exec -T lims-api python -c "
from fastapi.routing import APIRoute
from app.main import app
print(sum(1 for r in app.routes
          if isinstance(r, APIRoute)
          and r.methods - {'HEAD', 'OPTIONS'}
          and r.status_code != 204
          and r.response_model is None))" 2>/dev/null || echo "?")

commits=$(grep -rc 'db\.commit()' lims-backend/app/services/ --include='*.py' \
          | awk -F: '{s+=$2} END{print s+0}')

tested=$(ls lims-backend/app/tests/routers/test_*.py 2>/dev/null | wc -l)
routers=$(ls lims-backend/app/routers/*.py | grep -cv '__init__')

printf "  %-32s %6s   (mục tiêu 24 tháng: 0)\n"     "endpoint thiếu response_model" "$missing"
printf "  %-32s %6s   (mục tiêu 24 tháng: 0)\n"     "db.commit() trong service"     "$commits"
printf "  %-32s %4s/%-3s (mục tiêu 24 tháng: %s)\n" "router có test"  "$tested" "$routers" "$routers"
