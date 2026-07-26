#!/usr/bin/env bash
set -e

echo "[entrypoint] Chờ Postgres sẵn sàng..."
python - <<'PY'
import time, sys
import psycopg2
from app.config import settings

dsn = settings.database_url.replace("+psycopg2", "")
for i in range(30):
    try:
        psycopg2.connect(dsn).close()
        print("[entrypoint] Postgres OK")
        break
    except Exception as e:
        print(f"[entrypoint] Postgres chưa sẵn sàng ({i+1}/30): {e}")
        time.sleep(2)
else:
    print("[entrypoint] Postgres không phản hồi, thoát.")
    sys.exit(1)
PY

if [ "${SKIP_MIGRATIONS:-false}" = "true" ]; then
    echo "[entrypoint] SKIP_MIGRATIONS=true — bỏ qua migration (chạy ở service migrate riêng)."
else
    echo "[entrypoint] Lấy advisory lock trước khi migrate (tránh nhiều container/replica race)..."
    python - <<'PY'
import subprocess
import sys

import psycopg2
from app.config import settings

# Advisory lock cố định riêng cho migration LIMS — mọi container/replica cùng chờ
# lock này trước khi chạy `alembic upgrade head`, tránh race khi rolling deploy /
# scale-out (PRODUCTION_READINESS_REVIEW: "Migrations run unconditionally inside
# every container's entrypoint, no coordination lock").
_LOCK_KEY = 875321875321

dsn = settings.database_url.replace("+psycopg2", "")
conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor()
try:
    print("[entrypoint] Đang chờ advisory lock (nếu container khác đang migrate)...")
    cur.execute("SELECT pg_advisory_lock(%s);", (_LOCK_KEY,))
    print("[entrypoint] Đã lấy lock, chạy alembic upgrade head...")
    subprocess.run(["alembic", "upgrade", "head"], check=True)
except subprocess.CalledProcessError as exc:
    print(f"[entrypoint] Migration thất bại: {exc}")
    sys.exit(exc.returncode or 1)
finally:
    cur.execute("SELECT pg_advisory_unlock(%s);", (_LOCK_KEY,))
    conn.close()
PY
fi

echo "[entrypoint] Khởi động ứng dụng..."
exec "$@"
