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

echo "[entrypoint] Chạy migration (alembic upgrade head)..."
alembic upgrade head

echo "[entrypoint] Khởi động ứng dụng..."
exec "$@"
