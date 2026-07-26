"""Tests cho IdempotencyMiddleware — replay response 2xx, chặn request đang chạy,
không cache lỗi/thân lớn, bỏ qua khi không có header / không có danh tính, fail-open Redis."""
from contextlib import contextmanager
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.idempotency import IdempotencyMiddleware


class _FakeRedis:
    """Redis in-memory tối thiểu cho test (set nx/ex, get, setex, delete)."""

    def __init__(self):
        self.store: dict = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value
        return True

    def delete(self, key):
        self.store.pop(key, None)


@contextmanager
def _identified(user_id="user-1"):
    """Giả lập JWT hợp lệ — middleware namespace idempotency theo user này."""
    with patch.object(
        IdempotencyMiddleware, "_user_id_from_request", staticmethod(lambda request: user_id)
    ):
        yield


def _make_app(counter: dict):
    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)

    @app.post("/create")
    def create():
        counter["n"] += 1
        return {"created": counter["n"]}

    @app.post("/boom")
    def boom():
        counter["n"] += 1
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="bad")

    return app


def test_no_header_passes_through():
    counter = {"n": 0}
    with patch("app.middleware.idempotency.get_redis", return_value=_FakeRedis()), _identified():
        client = TestClient(_make_app(counter))
        r1 = client.post("/create")
        r2 = client.post("/create")
    assert r1.status_code == 200 and r2.status_code == 200
    assert counter["n"] == 2  # không header → không dedupe


def test_no_identity_skips_idempotency():
    """M3: không xác định được user (anon) → bỏ qua idempotency, tránh va chạm cross-user."""
    counter = {"n": 0}
    with patch("app.middleware.idempotency.get_redis", return_value=_FakeRedis()), \
         patch.object(IdempotencyMiddleware, "_user_id_from_request", staticmethod(lambda r: None)):
        client = TestClient(_make_app(counter))
        client.post("/create", headers={"Idempotency-Key": "abc"})
        client.post("/create", headers={"Idempotency-Key": "abc"})
    assert counter["n"] == 2  # anon → mỗi request chạy riêng


def test_same_key_replays_and_runs_once():
    counter = {"n": 0}
    with patch("app.middleware.idempotency.get_redis", return_value=_FakeRedis()), _identified():
        client = TestClient(_make_app(counter))
        r1 = client.post("/create", headers={"Idempotency-Key": "abc"})
        r2 = client.post("/create", headers={"Idempotency-Key": "abc"})
    assert counter["n"] == 1  # endpoint chỉ chạy 1 lần
    assert r1.json() == r2.json()  # response giống hệt
    assert r2.headers.get("Idempotency-Replayed") == "true"


def test_same_key_different_user_does_not_collide():
    """Key giống nhau nhưng user khác → KHÔNG replay chéo (namespace theo user)."""
    counter = {"n": 0}
    fake = _FakeRedis()
    with patch("app.middleware.idempotency.get_redis", return_value=fake):
        with _identified("user-A"):
            TestClient(_make_app(counter)).post("/create", headers={"Idempotency-Key": "same"})
        with _identified("user-B"):
            TestClient(_make_app(counter)).post("/create", headers={"Idempotency-Key": "same"})
    assert counter["n"] == 2  # mỗi user xử lý riêng


def test_different_keys_run_separately():
    counter = {"n": 0}
    with patch("app.middleware.idempotency.get_redis", return_value=_FakeRedis()), _identified():
        client = TestClient(_make_app(counter))
        client.post("/create", headers={"Idempotency-Key": "k1"})
        client.post("/create", headers={"Idempotency-Key": "k2"})
    assert counter["n"] == 2


def test_error_response_not_cached():
    counter = {"n": 0}
    with patch("app.middleware.idempotency.get_redis", return_value=_FakeRedis()), _identified():
        client = TestClient(_make_app(counter), raise_server_exceptions=False)
        r1 = client.post("/boom", headers={"Idempotency-Key": "e1"})
        r2 = client.post("/boom", headers={"Idempotency-Key": "e1"})
    assert r1.status_code == 400 and r2.status_code == 400
    assert counter["n"] == 2  # lỗi không cache → được chạy lại


def test_redis_unavailable_fails_open():
    counter = {"n": 0}

    class _BrokenRedis:
        def set(self, *a, **k):
            raise RuntimeError("redis down")

    with patch("app.middleware.idempotency.get_redis", return_value=_BrokenRedis()), _identified():
        client = TestClient(_make_app(counter))
        r1 = client.post("/create", headers={"Idempotency-Key": "x"})
        r2 = client.post("/create", headers={"Idempotency-Key": "x"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert counter["n"] == 2  # fail-open: xử lý bình thường
