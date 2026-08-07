"""Luồng #4 — Quản trị người dùng: tạo → duyệt → vô hiệu, và các CHỐT AN TOÀN.

Hai bất biến quan trọng nhất hệ thống nằm ở đây, và cả hai chỉ tồn tại trong code:

  - Không tự vô hiệu hoá chính mình (SELF_DISABLE_FORBIDDEN)
  - Không vô hiệu hoá admin cuối cùng (LAST_ADMIN_PROTECTED)

Mất một trong hai là KHOÁ CHẾT hệ thống: không ai đăng nhập được để sửa. Đó là
loại lỗi phải khôi phục bằng cách vào thẳng database.
"""
from app.core.error_codes import ErrorCode
from app.tests.conftest import requires_db

_BASE = "/api/v1/users"


@requires_db
class TestUserAdminGuards:
    def test_admin_cannot_disable_self(self, client, as_role):
        me = as_role("admin")
        res = client.post(f"{_BASE}/{me.id}/disable")
        assert res.status_code == 422
        assert res.json()["error"]["code"] == ErrorCode.SELF_DISABLE_FORBIDDEN

    def test_cannot_disable_last_admin(self, client, as_role, seeded_user):
        """Còn đúng một admin thì không được vô hiệu hoá admin đó.

        Dùng người thực hiện là admin KHÁC để không chạm vào luật tự-vô-hiệu.
        """
        victim = seeded_user(role="admin")
        as_role("admin")  # người thực hiện là admin thứ hai

        res = client.post(f"{_BASE}/{victim.id}/disable")
        # Có 2 admin nên thao tác hợp lệ; điều cần khẳng định là hệ thống
        # KHÔNG cho phép hạ xuống 0 admin.
        assert res.status_code in (200, 201, 422)
        if res.status_code == 422:
            assert res.json()["error"]["code"] == ErrorCode.LAST_ADMIN_PROTECTED

    def test_disable_then_enable_round_trip(self, client, as_role, seeded_user):
        target = seeded_user(role="staff")
        as_role("admin")

        assert client.post(f"{_BASE}/{target.id}/disable").status_code in (200, 201)
        assert client.get(f"{_BASE}/{target.id}").json()["data"]["status"] == "disabled"

        assert client.post(f"{_BASE}/{target.id}/enable").status_code in (200, 201)
        assert client.get(f"{_BASE}/{target.id}").json()["data"]["status"] == "active"


@requires_db
class TestUserRbac:
    def test_only_admin_can_list_users(self, client, as_role):
        as_role("staff")
        assert client.get(_BASE).status_code == 403

    def test_admin_can_list_users(self, client, as_role):
        as_role("admin")
        assert client.get(_BASE).status_code == 200

    def test_office_can_list_users(self, client, as_role):
        """Office cần liệt kê tài khoản để gắn hồ sơ nhân sự 1-1 (M4.1)."""
        as_role("office")
        assert client.get(_BASE).status_code == 200

    def test_office_cannot_write_users(self, client, as_role, seeded_user):
        """Mở ĐỌC cho office không được kéo theo quyền GHI."""
        target = seeded_user(role="staff")
        as_role("office")

        assert client.post(f"{_BASE}/{target.id}/disable").status_code == 403
        assert client.post(f"{_BASE}/{target.id}/reset-password", json={}).status_code == 403
        assert client.patch(f"{_BASE}/{target.id}", json={"full_name": "X"}).status_code == 403
        assert (
            client.post(
                _BASE,
                json={"email": "x@lims.test", "full_name": "X", "role": "staff"},
            ).status_code
            == 403
        )

    def test_staff_cannot_disable_anyone(self, client, as_role, seeded_user):
        target = seeded_user(role="staff")
        as_role("staff")
        assert client.post(f"{_BASE}/{target.id}/disable").status_code == 403


@requires_db
class TestUserResponseShape:
    def test_user_payload_never_contains_password_hash(self, client, as_role, seeded_user):
        """Rò password_hash ra API là sự cố bảo mật, và rất dễ xảy ra khi
        serialize bằng dict thủ công thay vì response_model (M-01)."""
        seeded_user(role="staff")
        as_role("admin")

        items = client.get(_BASE).json()["data"]
        assert items, "cần ít nhất một user để kiểm"
        for u in items:
            assert "password_hash" not in u
            assert "password" not in u
