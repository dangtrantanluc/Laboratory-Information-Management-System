"""Tests luật nghiệp vụ khi tải lên/thay tệp kho biểu mẫu VILAS (form_file_service).

Hai luật dễ hỏng nhất và đều có hệ quả thật:
- Minh chứng đã duyệt phải khóa tệp — cho đổi tệp sau khi duyệt làm chữ ký duyệt vô nghĩa.
- Phòng lab chỉ thao tác trên minh chứng phòng mình — tránh phòng này ghi đè phòng khác.
"""
import uuid
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.services import form_file_service as ffs

DEPT_A = uuid.uuid4()
DEPT_B = uuid.uuid4()


def _user(role: str, department_id=None):
    return SimpleNamespace(id=uuid.uuid4(), role=role, department_id=department_id)


def _submission(status: str = "pending", department_id=DEPT_A):
    return SimpleNamespace(
        id=uuid.uuid4(), status=status, department_id=department_id
    )


# ===== Trạng thái duyệt =====
def test_approved_submission_is_locked():
    with pytest.raises(AppException) as exc:
        ffs._check_submission_writable(_submission(status="approved"))
    assert exc.value.code == "INVALID_STATE"


@pytest.mark.parametrize("status", ["pending", "rejected"])
def test_pending_and_rejected_are_writable(status):
    ffs._check_submission_writable(_submission(status=status))  # không raise


# ===== Phạm vi phòng ban =====
def test_staff_can_edit_own_department():
    ffs._check_submission_scope(_user("staff", DEPT_A), _submission(department_id=DEPT_A))


def test_staff_cannot_edit_other_department():
    with pytest.raises(AppException) as exc:
        ffs._check_submission_scope(_user("staff", DEPT_B), _submission(department_id=DEPT_A))
    assert exc.value.http_status == 403


def test_staff_without_department_is_blocked():
    with pytest.raises(AppException):
        ffs._check_submission_scope(_user("staff", None), _submission(department_id=DEPT_A))


@pytest.mark.parametrize("role", ["admin", "qms"])
def test_privileged_roles_edit_any_department(role):
    ffs._check_submission_scope(_user(role, DEPT_B), _submission(department_id=DEPT_A))


# ===== Bảng action audit =====
def test_every_owner_type_has_full_action_set():
    for owner in (ffs.OWNER_TEMPLATE, ffs.OWNER_SUBMISSION):
        actions = ffs._ACTIONS[owner]
        assert set(actions) == {"upload", "replace", "delete"}
        # Mọi action đều phải có nhãn tiếng Việt để hiện ở màn hình lịch sử.
        for action in actions.values():
            assert ffs._ACTION_LABELS.get(action)
