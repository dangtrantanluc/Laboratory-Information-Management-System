"""Tests cho sample_common — state machine (FR-017) + RBAC scope (write/read).

Bao gồm regression cho IDOR fix: assert_read_scope (PRODUCTION_READINESS_REVIEW
§Security: "Sample detail read path has no department read-scope check").
"""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.services import sample_common as sc


def _user(role: str, department_id=None, is_dept_lead=False) -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(),
        email=f"{role}@ribe.vn",
        full_name="Nguyễn Văn A",
        role=role,
        department_id=department_id,
        is_dept_lead=is_dept_lead,
        is_quality_manager=False,
        status="active",
        jti="jti",
        token_exp=9999999999,
    )


# ===================== State machine whitelist =====================

@pytest.mark.parametrize("transition", list(sc.STATE_WHITELIST))
def test_whitelisted_transitions_apply(transition):
    from_status, to_status = transition
    sample = SimpleNamespace(status=from_status, id=uuid.uuid4())
    db = MagicMock()
    # audit_service.log_action gọi qua db — chỉ cần không raise
    sc.change_status(
        db, sample, to_status, trigger="test", user_id=uuid.uuid4(),
        correlation_id=None, ip=None,
    )
    assert sample.status == to_status


def test_non_whitelisted_transition_rejected():
    sample = SimpleNamespace(status="done", id=uuid.uuid4())
    db = MagicMock()
    with pytest.raises(AppException) as exc:
        sc.change_status(
            db, sample, "testing", trigger="test", user_id=uuid.uuid4(),
            correlation_id=None, ip=None,
        )
    assert exc.value.code == "INVALID_STATE_TRANSITION"
    assert exc.value.http_status == 422
    assert sample.status == "done"  # không đổi khi bị từ chối


def test_same_status_is_idempotent_noop():
    sample = SimpleNamespace(status="assigned", id=uuid.uuid4())
    db = MagicMock()
    sc.change_status(
        db, sample, "assigned", trigger="test", user_id=uuid.uuid4(),
        correlation_id=None, ip=None,
    )
    assert sample.status == "assigned"
    db.add.assert_not_called()  # không ghi audit khi from == to


# ===================== assert_write_scope =====================

def test_write_scope_privileged_bypasses_department():
    dept_a, dept_b = uuid.uuid4(), uuid.uuid4()
    sc.assert_write_scope(_user("admin"), dept_a)  # không raise
    sc.assert_write_scope(_user("leader", department_id=dept_b), dept_a)  # không raise


def test_write_scope_staff_same_department_ok():
    dept = uuid.uuid4()
    sc.assert_write_scope(_user("staff", department_id=dept), dept)


def test_write_scope_staff_other_department_forbidden():
    with pytest.raises(AppException) as exc:
        sc.assert_write_scope(_user("staff", department_id=uuid.uuid4()), uuid.uuid4())
    assert exc.value.http_status == 403


# ===================== assert_read_scope (IDOR fix) =====================

def test_read_scope_admin_leader_see_any_department():
    other = uuid.uuid4()
    sc.assert_read_scope(_user("admin"), other)
    sc.assert_read_scope(_user("leader", department_id=uuid.uuid4()), other)


def test_read_scope_reception_qms_see_any_department():
    other = uuid.uuid4()
    sc.assert_read_scope(_user("reception"), other)
    sc.assert_read_scope(_user("qms"), other)


def test_read_scope_staff_own_department_ok():
    dept = uuid.uuid4()
    sc.assert_read_scope(_user("staff", department_id=dept), dept)


def test_read_scope_staff_other_department_forbidden():
    with pytest.raises(AppException) as exc:
        sc.assert_read_scope(_user("staff", department_id=uuid.uuid4()), uuid.uuid4())
    assert exc.value.http_status == 403


def test_read_scope_staff_no_department_forbidden():
    with pytest.raises(AppException):
        sc.assert_read_scope(_user("staff", department_id=None), uuid.uuid4())
