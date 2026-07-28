#!/usr/bin/env bash
# Đo độ trễ endpoint — LÀM ẤM trước, lặp nhiều lần, lấy TRUNG VỊ.
#
#   ./perf/endpoint-latency.sh                       # bộ endpoint mặc định
#   ./perf/endpoint-latency.sh /samples /dashboard   # chỉ định endpoint
#   BASE=https://lims.tenmien.com ./perf/endpoint-latency.sh
#
# VÌ SAO PHẢI LÀM ẤM: bản audit đầu báo /dashboard 1.549 ms và kết luận đó là
# điểm nghẽn số một. Đo lại ở trạng thái ấm cho 11 ms — sai lệch 140 lần. Lần gọi
# đầu gồm chi phí import lần đầu của 51 lazy import trong codebase, cộng cache
# Redis chưa có và trang DB chưa nằm trong bộ nhớ. Nó KHÔNG phải độ trễ mà người
# dùng gặp.
#
# VÌ SAO TRUNG VỊ chứ không trung bình: một lần chậm bất thường (GC, checkpoint
# Postgres) kéo trung bình lệch hẳn, còn trung vị thì không.
set -euo pipefail

BASE="${BASE:-http://localhost:3060/api/v1}"
EMAIL="${EMAIL:-admin@lims.local}"
PASSWORD="${PASSWORD:-Lims@1234}"
WARMUP="${WARMUP:-3}"
RUNS="${RUNS:-5}"

DEFAULT_ENDPOINTS=(
    "/dashboard"
    "/samples?limit=100"
    "/test-requests?limit=100"
    "/forms/templates?limit=100"
    "/test-parameters?limit=100"
    "/documents?limit=100"
    "/notifications/unread-count"
)

TOK=$(curl -fsS -X POST "$BASE/auth/login" \
        -H 'Content-Type: application/json' \
        -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
      | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["access_token"])')

printf '═══ Độ trễ endpoint · %s ═══\n' "$BASE"
printf '    làm ấm %d lần · đo %d lần · lấy trung vị\n\n' "$WARMUP" "$RUNS"
printf '  %-40s %9s %9s %9s\n' "ENDPOINT" "TRUNG VỊ" "NHANH" "CHẬM"
printf '  %-40s %9s %9s %9s\n' "----------------------------------------" "--------" "--------" "--------"

for ep in "${@:-${DEFAULT_ENDPOINTS[@]}}"; do
    for _ in $(seq "$WARMUP"); do
        curl -s -o /dev/null "$BASE$ep" -H "Authorization: Bearer $TOK" || true
    done

    times=$(for _ in $(seq "$RUNS"); do
        curl -s -o /dev/null -w '%{time_total}\n' "$BASE$ep" -H "Authorization: Bearer $TOK" || echo 0
    done | awk '{printf "%.0f\n", $1*1000}' | sort -n)

    med=$(echo "$times" | awk '{a[NR]=$1} END{print (NR%2)?a[(NR+1)/2]:int((a[NR/2]+a[NR/2+1])/2)}')
    min=$(echo "$times" | head -1)
    max=$(echo "$times" | tail -1)

    printf '  %-40s %7s ms %7s ms %7s ms\n' "$ep" "$med" "$min" "$max"
done

printf '\n  Lưu kết quả để so sánh trước/sau:\n'
printf '    ./perf/endpoint-latency.sh > perf/baseline-$(date +%%F).txt\n'
