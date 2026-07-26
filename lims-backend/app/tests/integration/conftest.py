"""Harness integration test chống DB Postgres THẬT (PRODUCTION_READINESS_REVIEW Phase D).

Khác test đơn vị (mock db): các test ở đây chạy SQL/ràng buộc/khóa THẬT để chứng minh
những sửa lỗi cần DB thật (H3 giữ giao dịch kho khi notify lỗi, M6 khóa duyệt đăng ký,
tính atomic tồn kho...).

- Bật khi có env TEST_DATABASE_URL (throwaway Postgres — KHÔNG trỏ vào DB dev/prod!).
  Không có env → toàn bộ integration test tự SKIP (unit test vẫn chạy bình thường).
- Cô lập từng test: mở 1 transaction ngoài trên connection, bind session vào đó, và
  RESTART SAVEPOINT sau mỗi commit của app (recipe "join external transaction" của
  SQLAlchemy) → app vẫn gọi db.commit() được nhưng cuối test rollback sạch, không để lại dữ liệu.
"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set — integration tests skipped"
)


@pytest.fixture(scope="session")
def engine():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    eng = create_engine(TEST_DATABASE_URL, future=True)
    # Tạo schema thật qua alembic (ràng buộc/index/CHECK giống production).
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    """Session cô lập theo test — mọi thay đổi (kể cả app commit) rollback ở cuối test."""
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()
