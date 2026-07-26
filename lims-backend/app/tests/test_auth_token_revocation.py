"""Tests cho H1 — access token cấp TRƯỚC password_changed_at bị thu hồi trong get_current_user.

Mock DB (db.get) + JWT thật để khoá lại hợp đồng: token cũ → 401 sau khi đổi mật khẩu;
token mới (iat >= password_changed_at) vẫn hợp lệ; token khi password_changed_at=None (seed
admin chưa đổi) không bị chặn bởi kiểm tra này.
"""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core import deps, security
from app.core.exceptions import AppException


def _make_request(token: str):
    return SimpleNamespace(headers={"Authorization": f"Bearer {token}"})


def _fake_user(password_changed_at):
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="u@ribe.vn",
        full_name="U",
        role="staff",
        department_id=None,
        is_quality_manager=False,
        status="active",
        password_changed_at=password_changed_at,
    )


def _token_for(user_id):
    token, _jti, _ttl = security.create_access_token(
        user_id=user_id, role="staff", department_id=None, is_dept_lead=False
    )
    return token


def _run(token, user):
    db = MagicMock()
    db.get.return_value = user
    with patch.object(security, "is_jti_denied", return_value=False):
        return deps.get_current_user(_make_request(token), db=db)


def test_token_issued_before_password_change_is_revoked():
    user = _fake_user(password_changed_at=datetime.now(timezone.utc) + timedelta(hours=1))
    token = _token_for(user.id)  # iat = now, password_changed_at = now+1h → token cũ hơn
    with pytest.raises(AppException) as exc:
        _run(token, user)
    assert exc.value.http_status == 401
    assert exc.value.code == "TOKEN_INVALID"


def test_token_issued_after_password_change_is_valid():
    user = _fake_user(password_changed_at=datetime.now(timezone.utc) - timedelta(hours=1))
    token = _token_for(user.id)  # iat = now > password_changed_at (1h trước) → hợp lệ
    result = _run(token, user)
    assert result.id == user.id


def test_no_password_changed_at_not_blocked():
    user = _fake_user(password_changed_at=None)  # seed admin chưa đổi
    token = _token_for(user.id)
    result = _run(token, user)
    assert result.id == user.id
