"""Cấu hình ứng dụng — đọc từ biến môi trường (.env). KHÔNG hardcode secret."""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- JWT ---
    jwt_secret: str = Field(default="CHANGE_ME_IN_ENV_super_secret_key_min_32_chars")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30  # NFR-SEC-003: <= 60
    refresh_token_ttl_days: int = 30  # NFR-SEC-003: <= 30

    # --- Auth lockout ---
    login_max_failed: int = 5
    login_lockout_minutes: int = 15

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

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment in ("production", "staging")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
