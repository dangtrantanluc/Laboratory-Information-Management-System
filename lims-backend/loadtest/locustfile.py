"""Load test (Locust) — kiểm chứng ngưỡng pool 30 kết nối cho mục tiêu ~40 user đồng thời
sau khi đã gỡ N+1/blocking (PRODUCTION_READINESS_REVIEW D4).

Chạy:
    pip install locust
    LIMS_TOKEN=<access_token> locust -f loadtest/locustfile.py --host http://localhost:8060 \
        --users 40 --spawn-rate 5 --run-time 3m --headless

Theo dõi khi chạy:
    - p95 latency mỗi endpoint (mục tiêu < 500ms cho list, < 2s cho export)
    - tỉ lệ lỗi (đặc biệt 503/timeout do cạn pool)
    - Postgres: SELECT count(*) FROM pg_stat_activity WHERE datname='lims';  (số conn dùng)
    - /metrics: http_request_duration_seconds histogram + http_requests_total{status=~"5.."}

Điều chỉnh sau khi có số liệu (KHÔNG chỉnh mù):
    - Nếu pg_stat_activity chạm ~30 và request xếp hàng → tăng db_pool_size/db_max_overflow
      (app/config.py) HOẶC giảm thời gian giữ connection (đã làm: N+1, webpush off-path).
    - Đặt db_pool_timeout thấp (vd 5s) để cạn pool FAIL NHANH thay vì treo.
"""
import os

from locust import HttpUser, between, task

_TOKEN = os.getenv("LIMS_TOKEN", "")
_HEADERS = {"Authorization": f"Bearer {_TOKEN}"} if _TOKEN else {}


class LimsUser(HttpUser):
    wait_time = between(1, 3)  # mô phỏng người dùng thật giữa các thao tác

    @task(5)
    def list_samples(self):
        self.client.get("/api/v1/samples?page=1&limit=20", headers=_HEADERS, name="GET /samples")

    @task(4)
    def list_chemicals(self):
        self.client.get("/api/v1/chemicals?page=1&limit=20", headers=_HEADERS, name="GET /chemicals")

    @task(3)
    def dashboard(self):
        self.client.get("/api/v1/dashboard", headers=_HEADERS, name="GET /dashboard")

    @task(3)
    def chemical_transactions(self):
        # hot path đã sửa N+1 — kiểm tra độ trễ ổn định dưới tải
        self.client.get(
            "/api/v1/chemical-transactions?page=1&limit=50",
            headers=_HEADERS, name="GET /chemical-transactions",
        )

    @task(1)
    def health(self):
        self.client.get("/health/ready", name="GET /health/ready")
