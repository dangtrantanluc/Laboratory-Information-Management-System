"""Helper dùng chung cho các module research — validate thành viên/tác giả.

Tách từ research_service.py (1.736 dòng, 9 domain) — M-03/T1.1.
Xem app/services/research/__init__.py để biết vì sao có mặt tiền tương thích.
"""
import uuid

from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.deps import CurrentUser
from app.core.exceptions import AppException
from app.services import hr_common as hc


def _validate_members(db: Session, members: list, *, allow_external: bool, lead_user_id):
    """Validate danh sách thành viên/tác giả. Trả (internal_user_ids set).

    allow_external=False (project_members FK chặt): chỉ user_id; external → INVALID_AUTHOR.
    Đề tài: lead_user_id phải nằm trong members.
    """
    if not members:
        raise AppException(ErrorCode.VALIDATION_ERROR, "members không được rỗng", 400)
    seen_users: set[uuid.UUID] = set()
    for idx, m in enumerate(members):
        uid = m.get("user_id")
        ext = m.get("external_name")
        if (uid is None) == (ext is None):
            raise AppException(
                ErrorCode.INVALID_AUTHOR,
                "Mỗi thành viên phải là user_id HOẶC external_name, không cả hai/để trống",
                422,
                [{"field": f"members[{idx}]", "message": "XOR user_id/external_name"}],
            )
        if ext is not None and not allow_external:
            raise AppException(
                ErrorCode.INVALID_AUTHOR,
                "Thành viên đề tài phải là người nội bộ (user_id)",
                422,
                [{"field": f"members[{idx}]", "message": "external_name không cho phép"}],
            )
        if uid is not None:
            if uid in seen_users:
                raise AppException(
                    ErrorCode.DUPLICATE_MEMBER, "Một người là thành viên 2 lần", 409
                )
            hc.assert_user_exists(db, uid)
            seen_users.add(uid)
    if lead_user_id is not None and lead_user_id not in seen_users:
        raise AppException(
            ErrorCode.LEAD_REQUIRED, "Chủ nhiệm phải nằm trong danh sách thành viên", 400
        )
    return seen_users


def _assert_staff_in_members(user: CurrentUser, internal_users: set, field: str):
    """Staff own: phải là thành viên/tác giả nội bộ của bản ghi (BR-HR-023)."""
    if user.role == "staff" and user.id not in internal_users:
        raise hc.forbidden(f"Bạn phải là một {field} nội bộ của bản ghi này")
