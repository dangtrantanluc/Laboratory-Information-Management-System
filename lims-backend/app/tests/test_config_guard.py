"""Tests cho production secret guard (PRODUCTION_READINESS_REVIEW Risk #1).

App phải TỪ CHỐI khởi động ở production/staging khi còn secret/credential mặc định,
và khởi động bình thường ở dev hoặc khi đã đặt secret mạnh.
"""
import pytest

from app.config import Settings

_STRONG = dict(
    jwt_secret="a" * 40,
    minio_access_key="realkey",
    minio_secret_key="realsecret",
    seed_admin_password="S0meReal!Pass",
    database_url="postgresql+psycopg2://realuser:realpass@host:5432/db",
)


def test_dev_boots_with_defaults():
    s = Settings(environment="development")
    assert s.is_production is False


def test_production_rejects_default_jwt_secret():
    with pytest.raises(RuntimeError) as exc:
        Settings(
            environment="production",
            jwt_secret="dev_only_change_me_super_secret_key_min_32_chars",
            **{k: v for k, v in _STRONG.items() if k != "jwt_secret"},
        )
    assert "JWT_SECRET" in str(exc.value)


def test_production_rejects_short_jwt_secret():
    with pytest.raises(RuntimeError):
        Settings(environment="production", **{**_STRONG, "jwt_secret": "tooshort"})


def test_production_rejects_default_minio_creds():
    with pytest.raises(RuntimeError) as exc:
        Settings(environment="production", **{**_STRONG, "minio_access_key": "minioadmin"})
    assert "MINIO" in str(exc.value)


def test_production_rejects_default_db_credentials():
    with pytest.raises(RuntimeError) as exc:
        Settings(
            environment="production",
            **{**_STRONG, "database_url": "postgresql+psycopg2://lims:lims@postgres:5432/lims"},
        )
    assert "DATABASE_URL" in str(exc.value)


def test_production_boots_with_strong_secrets():
    s = Settings(environment="production", **_STRONG)
    assert s.is_production is True


def test_staging_also_guarded():
    with pytest.raises(RuntimeError):
        Settings(environment="staging", **{**_STRONG, "seed_admin_password": "ChangeMe@123"})
