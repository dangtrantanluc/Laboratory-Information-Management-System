"""Fixture dùng chung cho test router (M-04/T2.1).

VÌ SAO 0/41 ROUTER TỪNG CÓ TEST: service gọi `db` trực tiếp (~1.000 điểm chạm),
nên muốn test một endpoint phải dựng Postgres thật. Rào cản đó khiến không ai
viết. Sửa rào cản trước, test mới xuất hiện sau.

Dùng Postgres THẬT chứ không SQLite: schema dùng CITEXT, INET, gen_random_uuid()
và trigger append-only cho audit_logs. Test chạy trên SQLite sẽ xanh trong khi
production vẫn hỏng — tệ hơn là không có test.

CÔ LẬP TỪNG TEST: mở một giao dịch ngoài trên connection, bind session vào đó với
`join_transaction_mode="create_savepoint"`, cuối test rollback sạch. Chi tiết
quan trọng: service HIỆN VẪN gọi `db.commit()` (166 chỗ, gỡ ở Giai đoạn 3), nên
KHÔNG dùng được kiểu rollback đơn giản — savepoint là thứ cho phép app commit
mà test vẫn dọn sạch được.
"""
import os
import uuid
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

requires_db = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL chưa đặt — chạy bằng ./scripts/test-backend.sh",
)


@pytest.fixture(scope="session")
def engine():
    """Engine dùng chung, schema dựng bằng chính alembic của production.

    Không dùng `Base.metadata.create_all`: nó bỏ qua trigger, CHECK constraint và
    index mà migration tạo bằng SQL thô, nên test sẽ không thấy các ràng buộc
    thật sự tồn tại ở production.
    """
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL chưa đặt")
    eng = create_engine(TEST_DATABASE_URL, future=True)

    from alembic import command
    from alembic.config import Config

    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(Config("alembic.ini"), "head")
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    """Session cô lập theo test — mọi thay đổi (kể cả app commit) rollback ở cuối."""
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture
def client(db) -> TestClient:
    """TestClient dùng CHUNG session với fixture `db`.

    Nhờ vậy dữ liệu seed trong test nhìn thấy được từ request, và request ghi gì
    thì test đọc lại được — tất cả vẫn nằm trong giao dịch bị rollback.

    Header `X-Real-IP` là BẮT BUỘC, không phải trang trí: mặc định TestClient đặt
    `request.client.host = "testclient"` (chuỗi, không phải IP), trong khi
    `audit_logs.ip` là cột INET. Mọi endpoint GHI đều ném DataError "invalid input
    syntax for type inet" — tức là không test được endpoint ghi nào cho tới khi
    sửa chỗ này. Đúng loại rào cản khiến 0/41 router có test.

    Dùng header thay vì giả `request.client` vì đó CHÍNH LÀ đường đi ở production:
    `client_ip()` đọc X-Real-IP do nginx ghi đè (xem app/core/rate_limit.py).
    """
    from app.db.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, headers={"X-Real-IP": "127.0.0.1"}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def as_role(client, db):
    """Đăng nhập giả theo vai trò — bỏ qua bcrypt và JWT, nhưng TẠO USER THẬT.

    Test router quan tâm tới RBAC và hình dạng response, KHÔNG phải cơ chế đăng
    nhập (đã có test riêng ở test_auth_token_revocation.py). Bỏ qua bcrypt cost 12
    tiết kiệm ~250ms mỗi test, và đó là khác biệt giữa bộ test chạy 10 giây với
    bộ test chạy 3 phút — tức là giữa bộ test người ta chạy và bộ test bị bỏ qua.

    NHƯNG vẫn phải ghi user thật vào DB: hầu hết bảng có FK `created_by → users`,
    nên CurrentUser với uuid bịa ra sẽ làm mọi thao tác GHI đổ vỡ vì
    ForeignKeyViolation. Đây đúng là loại rào cản khiến người ta bỏ cuộc khi viết
    test router — fixture phải lo, không phải từng test tự lo.

    Trả về CurrentUser để test dùng luôn id/department_id khi seed dữ liệu.
    """
    from app.core.deps import CurrentUser, get_current_user
    from app.main import app
    from app.models.user import User

    def _login(
        role: str = "admin",
        *,
        department_id: Optional[uuid.UUID] = None,
        is_dept_lead: bool = False,
        is_quality_manager: bool = False,
        email: Optional[str] = None,
    ) -> CurrentUser:
        u = User(
            email=email or f"{role}-{uuid.uuid4().hex[:8]}@test.local",
            full_name=f"Test {role}",
            password_hash="$2b$12$" + "x" * 53,  # không dùng để đăng nhập
            role=role,
            status="active",
            department_id=department_id,
            is_quality_manager=is_quality_manager,
            # is_dept_lead KHÔNG phải cột của users — nó suy ra từ
            # departments.lead_user_id, nên chỉ đặt trên CurrentUser bên dưới.
        )
        db.add(u)
        db.flush()

        cu = CurrentUser(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=role,
            department_id=department_id,
            is_dept_lead=is_dept_lead,
            is_quality_manager=is_quality_manager,
            status="active",
            jti="test-jti",
            token_exp=9_999_999_999,
        )
        app.dependency_overrides[get_current_user] = lambda: cu
        return cu

    yield _login
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def seeded_user(db):
    """Tạo user thật trong DB — cần khi endpoint join sang bảng users.

    `as_role` chỉ giả CurrentUser ở tầng dependency; nó KHÔNG tạo hàng trong DB.
    Endpoint nào đọc `users` (audit log, tên người tạo...) thì cần fixture này.
    """
    from app.models.user import User

    def _make(role: str = "admin", **kw) -> User:
        u = User(
            email=kw.pop("email", f"{role}-{uuid.uuid4().hex[:8]}@test.local"),
            full_name=kw.pop("full_name", f"Test {role}"),
            password_hash="x" * 60,
            role=role,
            status=kw.pop("status", "active"),
            **kw,
        )
        db.add(u)
        db.flush()
        return u

    return _make


@pytest.fixture
def department(db):
    """Phòng ban thật trong DB.

    Nhiều endbpoint (risks, nonconformities...) bắt buộc `department_id` và trả
    400 "Cần chỉ định department_id" nếu thiếu. Fixture này để test không phải
    tự dựng lại mỗi lần.
    """
    from app.models.department import Department

    d = Department(name=f"Phòng Thử Nghiệm {uuid.uuid4().hex[:6]}", code=uuid.uuid4().hex[:8])
    db.add(d)
    db.flush()
    return d


@pytest.fixture
def audit_rows(db):
    """Đếm audit_logs — dùng để khẳng định thao tác có ghi vết.

    audit_logs là append-only ở tầng DB (trigger chặn UPDATE/DELETE), nên đây là
    cách duy nhất kiểm chứng: không xoá được để dọn.
    """

    def _count(action: Optional[str] = None) -> int:
        sql = "SELECT count(*) FROM audit_logs"
        params = {}
        if action:
            sql += " WHERE action = :a"
            params["a"] = action
        return db.execute(text(sql), params).scalar_one()

    return _count
