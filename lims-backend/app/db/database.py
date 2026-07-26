"""SQLAlchemy 2.x sync engine + session + declarative Base.

Dùng sync (đủ cho ~40 user, đơn giản hóa vận hành — quyết định stack).
"""
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.config import settings

engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,  # tránh "server closed connection" sau idle
    # Cạn pool → FAIL NHANH (mặc định 30s là quá lâu, giữ request treo) — dễ chẩn đoán +
    # trả lỗi sớm cho client thay vì tắc nghẽn dây chuyền (PRODUCTION_READINESS_REVIEW D4).
    pool_timeout=settings.db_pool_timeout,
)

SessionLocal = sessionmaker(
    bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
)


class Base(DeclarativeBase):
    """Base cho mọi ORM model."""

    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yield 1 session theo request, đóng khi xong."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
