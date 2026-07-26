"""Tests cho report_common — RBAC scope + bộ lọc thời gian dùng chung M6."""
import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.services import report_common as rc


def _user(role: str, department_id=None) -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(),
        email=f"{role}@ribe.vn",
        full_name="Nguyễn Văn A",
        role=role,
        department_id=department_id,
        is_dept_lead=False,
        is_quality_manager=False,
        status="active",
        jti="test-jti",
        token_exp=9999999999,
    )


# ===================== resolve_scope_department =====================

def test_staff_scope_ignored_requested_department_forces_own():
    db = MagicMock()
    own_dept = uuid.uuid4()
    other_dept = uuid.uuid4()
    user = _user("staff", department_id=own_dept)

    result = rc.resolve_scope_department(db, user, requested=other_dept)

    assert result == own_dept
    db.get.assert_not_called()  # staff path không cần validate DB — luôn ép về phòng mình


def test_admin_scope_honors_requested_department_when_exists():
    db = MagicMock()
    db.get.return_value = object()  # phòng tồn tại
    dept = uuid.uuid4()
    user = _user("admin")

    result = rc.resolve_scope_department(db, user, requested=dept)

    assert result == dept


def test_admin_scope_404_when_requested_department_missing():
    db = MagicMock()
    db.get.return_value = None
    user = _user("admin")

    with pytest.raises(AppException) as exc:
        rc.resolve_scope_department(db, user, requested=uuid.uuid4())
    assert exc.value.http_status == 404
    assert exc.value.code == "DEPARTMENT_NOT_FOUND"


def test_scope_none_when_no_department_requested_and_not_staff():
    db = MagicMock()
    user = _user("leader")
    assert rc.resolve_scope_department(db, user, requested=None) is None


# ===================== RBAC guards =====================

def test_deny_office_samples_blocks_office():
    with pytest.raises(AppException) as exc:
        rc.deny_office_samples(_user("office"))
    assert exc.value.http_status == 403


def test_deny_office_samples_allows_other_roles():
    rc.deny_office_samples(_user("staff"))  # không raise


def test_require_audit_read_blocks_non_privileged():
    with patch("app.services.report_common.has_permission", return_value=False):
        with pytest.raises(AppException) as exc:
            rc.require_audit_read(MagicMock(), _user("staff"))
    assert exc.value.http_status == 403


def test_require_audit_read_allows_admin():
    with patch("app.services.report_common.has_permission", return_value=True):
        rc.require_audit_read(MagicMock(), _user("admin"))  # không raise


def test_can_see_cost_delegates_to_has_permission():
    with patch("app.services.report_common.has_permission", return_value=True) as mock_hp:
        assert rc.can_see_cost(MagicMock(), _user("office")) is True
        mock_hp.assert_called_once()


# ===================== resolve_range =====================

def test_resolve_range_empty_defaults_to_current_month():
    d_from, d_to = rc.resolve_range(None, None)
    assert d_from < d_to


def test_resolve_range_invalid_from_after_to():
    with pytest.raises(AppException) as exc:
        rc.resolve_range(date(2026, 2, 1), date(2026, 1, 1))
    assert exc.value.code == "INVALID_DATE_RANGE"


def test_resolve_range_within_cap_ok():
    d_from, d_to = rc.resolve_range(date(2024, 1, 1), date(2025, 12, 31))
    assert (d_to - d_from).days <= rc.MAX_RANGE_DAYS


def test_resolve_range_too_wide_rejected():
    with pytest.raises(AppException) as exc:
        rc.resolve_range(date(2020, 1, 1), date(2026, 1, 1))
    assert exc.value.code == "DATE_RANGE_TOO_WIDE"
    assert exc.value.http_status == 422
