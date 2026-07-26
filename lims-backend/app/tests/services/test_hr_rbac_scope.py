"""Guard tests cho RBAC field-level HR (lương/HĐ/PII) — khoá ma trận quyền hiện tại.

Đặc biệt khoá QUYẾT ĐỊNH M8 (accepted debt): 'leader' đọc lương/HĐ TOÀN tổ chức nhưng
KHÔNG xem PII. Nếu ai đó vô ý đổi hành vi (mở PII cho leader, hoặc scope lương theo phòng)
thì test này fail → buộc review lại quyết định thay vì trôi im lặng.
"""
import uuid

from app.services import hr_common as hc


def test_leader_reads_any_salary_and_contract():
    other = uuid.uuid4()
    assert hc.can_read_salary(_u("leader"), other) is True
    assert hc.can_read_contract(_u("leader"), other) is True


def test_leader_cannot_read_pii_of_others():
    other = uuid.uuid4()
    assert hc.can_read_pii(_u("leader"), other) is False


def test_admin_office_read_all_three():
    other = uuid.uuid4()
    for role in ("admin", "office"):
        assert hc.can_read_salary(_u(role), other) is True
        assert hc.can_read_contract(_u(role), other) is True
        assert hc.can_read_pii(_u(role), other) is True


def test_staff_reads_only_own():
    me = uuid.uuid4()
    other = uuid.uuid4()
    assert hc.can_read_salary(_u("staff", uid=me), me) is True
    assert hc.can_read_salary(_u("staff", uid=me), other) is False
    assert hc.can_read_pii(_u("staff", uid=me), me) is True
    assert hc.can_read_pii(_u("staff", uid=me), other) is False


def test_only_admin_office_can_edit_salary():
    assert hc.can_edit_salary(_u("admin")) is True
    assert hc.can_edit_salary(_u("office")) is True
    assert hc.can_edit_salary(_u("leader")) is False
    assert hc.can_edit_salary(_u("staff")) is False


class _U:
    def __init__(self, role, uid):
        self.role = role
        self.id = uid


def _u(role, uid=None):
    return _U(role, uid or uuid.uuid4())
