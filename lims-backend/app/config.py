"""Cấu hình ứng dụng — đọc từ biến môi trường (.env). KHÔNG hardcode secret."""
from functools import lru_cache
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Giá trị mặc định/dev "well-known" — nếu còn tồn tại khi ENVIRONMENT=production/staging
# thì coi như cấu hình chưa được đổi và từ chối khởi động (PRODUCTION_READINESS_REVIEW §Risk 1).
_INSECURE_JWT_SECRETS = {
    "CHANGE_ME_IN_ENV_super_secret_key_min_32_chars",
    "CHANGE_ME_super_secret_key_at_least_32_characters_long",
    "dev_only_change_me_super_secret_key_min_32_chars",
}
_INSECURE_MINIO_CREDS = {"minioadmin"}
_INSECURE_SEED_PASSWORD = "ChangeMe@123"
_INSECURE_DB_CREDENTIALS = ("lims:lims@",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_name: str = "LIMS Backend (M7 Platform)"
    environment: str = Field(default="development")  # development | staging | production
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # --- Database ---
    database_url: str = Field(
        default="postgresql+psycopg2://lims:lims@localhost:5432/lims"
    )
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 10  # giây chờ 1 connection từ pool trước khi lỗi (fail-fast)

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0")
    # Timeout socket cho Redis — KHÔNG để mặc định (vô hạn): 1 Redis treo sẽ chặn mọi
    # caller (denylist/lockout/rate-limit/idempotency/scheduler) → đóng băng worker.
    redis_socket_timeout: float = 2.0
    redis_connect_timeout: float = 2.0

    # --- JWT ---
    jwt_secret: str = Field(default="CHANGE_ME_IN_ENV_super_secret_key_min_32_chars")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30  # NFR-SEC-003: <= 60
    refresh_token_ttl_days: int = 30  # NFR-SEC-003: <= 30

    # --- Auth lockout ---
    login_max_failed: int = 5
    login_lockout_minutes: int = 15

    # --- Scheduler (APScheduler) ---
    # Đặt false trên các replica KHÔNG chạy cron (khi scale ngang nhiều replica, chỉ 1
    # replica/worker nên bật). Mặc định true cho triển khai 1 replica hiện tại. Ngay cả
    # khi lỡ để true nhiều replica, Redis leader-lock + per-job lock vẫn chống chạy trùng.
    scheduler_enabled: bool = True

    # --- MinIO / S3 ---
    minio_endpoint: str = Field(default="http://localhost:9000")
    minio_public_endpoint: str = Field(default="http://localhost:9000")
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: str = Field(default="minioadmin")
    minio_bucket: str = Field(default="lims-attachments")
    minio_region: str = "us-east-1"
    minio_secure: bool = False
    presigned_url_ttl_seconds: int = 900  # 15 phút (theo contract #30)

    # --- File upload ---
    max_upload_size_bytes: int = 20 * 1024 * 1024  # 20MB (đồng bộ M1/M2)

    # --- CORS ---
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:3050")

    # --- Seed admin (chỉ dùng khi seed; mật khẩu thật đọc từ env) ---
    seed_admin_email: str = "admin@lims.local"
    seed_admin_password: str = Field(default="ChangeMe@123")

    # --- Web Push (VAPID) — M20: popup thông báo desktop ---
    vapid_public_key: str = Field(default="")
    vapid_private_key: str = Field(default="")
    vapid_claims_email: str = Field(default="admin@lims.local")

    # --- m30: URL công khai của frontend ---
    # Dùng để dựng link trong mail (xác thực đăng ký / đặt lại mật khẩu). Phải là
    # origin người dùng thực sự mở, không phải localhost khi chạy production.
    app_public_url: str = Field(default="http://localhost:3060")

    # --- m30: SMTP gửi mail ---
    # Bỏ trống smtp_host ⇒ chế độ DEV: không gửi thật, ghi link ra log để test.
    # Gmail: host=smtp.gmail.com, port=587, starttls=true, user=<mail>, password=<App Password 16 ký tự>
    smtp_host: str = Field(default="")
    smtp_port: int = 587
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_starttls: bool = True
    smtp_ssl: bool = False  # True nếu dùng cổng 465 (SMTPS) thay vì 587 (STARTTLS)
    smtp_from: str = Field(default="")  # bỏ trống → dùng smtp_user
    smtp_from_name: str = "Viện CNSH & Môi trường — LIMS"
    smtp_timeout_seconds: int = 10

    # --- m30: hiệu lực token trong mail ---
    email_verify_ttl_hours: int = 24
    password_reset_ttl_minutes: int = 30

    # --- m30: đăng ký tự phục vụ ---
    # Bật/tắt form đăng ký công khai. Tài khoản đăng ký LUÔN ở trạng thái 'pending'
    # và phải được Quản trị viên duyệt — cờ này chỉ quyết định có mở form hay không.
    self_registration_enabled: bool = True
    # Bỏ trống = nhận mọi domain. Điền để giới hạn, vd "hcmuaf.edu.vn,st.hcmuaf.edu.vn".
    self_registration_allowed_domains: str = Field(default="")

    # --- m30: ảnh đại diện ---
    avatar_max_size_bytes: int = 2 * 1024 * 1024  # 2MB — ảnh đại diện không cần lớn

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host)

    @property
    def smtp_sender(self) -> str:
        return self.smtp_from or self.smtp_user or "no-reply@lims.local"

    @property
    def self_registration_domain_list(self) -> List[str]:
        return [
            d.strip().lower().lstrip("@")
            for d in self.self_registration_allowed_domains.split(",")
            if d.strip()
        ]

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment in ("production", "staging")

    @model_validator(mode="after")
    def _guard_production_secrets(self) -> "Settings":
        """Từ chối khởi động ở production/staging nếu còn secret/credential mặc định."""
        if not self.is_production:
            return self

        insecure: List[str] = []
        if self.jwt_secret in _INSECURE_JWT_SECRETS or len(self.jwt_secret) < 32:
            insecure.append("JWT_SECRET")
        if (
            self.minio_access_key in _INSECURE_MINIO_CREDS
            or self.minio_secret_key in _INSECURE_MINIO_CREDS
        ):
            insecure.append("MINIO_ACCESS_KEY/MINIO_SECRET_KEY")
        if self.seed_admin_password == _INSECURE_SEED_PASSWORD:
            insecure.append("SEED_ADMIN_PASSWORD")
        if any(marker in self.database_url for marker in _INSECURE_DB_CREDENTIALS):
            insecure.append("DATABASE_URL (default lims/lims credentials)")

        if insecure:
            raise RuntimeError(
                "Refusing to start with ENVIRONMENT="
                f"{self.environment} while these settings still hold insecure "
                f"default/dev values: {', '.join(insecure)}. "
                "Set strong, unique values via environment variables before deploying."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
