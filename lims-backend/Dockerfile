FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# psycopg2-binary cần libpq; build tools cho 1 vài wheel
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN chmod +x /app/entrypoint.sh

# Chạy dưới user không phải root — giảm blast radius nếu có lỗ hổng RCE trong deps
# (PRODUCTION_READINESS_REVIEW §Reliability: "Dockerfile runs as root").
RUN groupadd --system lims && useradd --system --gid lims --no-create-home lims \
    && chown -R lims:lims /app
USER lims

EXPOSE 8060

# Số worker uvicorn. Phải KHỚP số nhân của host: đặt cao hơn nproc thì các worker
# tranh CPU và chậm hơn là nhanh hơn. Ghi đè bằng biến môi trường khi deploy.
ENV UVICORN_WORKERS=4

ENTRYPOINT ["/app/entrypoint.sh"]
# Dùng sh -c để nội suy được ${UVICORN_WORKERS}.
#
# --proxy-headers + --forwarded-allow-ips: BẮT BUỘC để request.client.host trả IP
#   thật của người dùng thay vì IP container nginx. Không có nó, rate limit và audit
#   log đều dùng chung một "IP" cho toàn hệ thống (ARCHITECTURE_AUDIT.md F-04).
#   '*' chỉ an toàn vì lims-api KHÔNG publish cổng ra host — chỉ nginx trong mạng
#   compose gọi tới được, nên không ai giả mạo header được.
# --timeout-graceful-shutdown 30: chờ request đang xử lý xong khi deploy, thay vì
#   cắt ngang giữa chừng một upload/export.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8060 \
     --workers ${UVICORN_WORKERS} \
     --proxy-headers --forwarded-allow-ips '*' \
     --timeout-graceful-shutdown 30"]
