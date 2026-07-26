"""Helper truy vấn dùng chung (M-09/T1.4).

13 service tự viết `_get_X_or_404` với thân hàm giống hệt nhau: nạp theo khoá
chính, kiểm None, ném not_found. Trùng lặp kiểu này không gây lỗi ngay nhưng
mỗi bản sao là một chỗ có thể quên điều kiện `deleted_at IS NULL` — và bản quên
sẽ trả về bản ghi đã xoá mềm mà không ai nhận ra.

Hai biến thể vì codebase có hai loại bảng:

  - Bảng thường          → `get_or_404`        (db.get, đi qua identity map)
  - Bảng có soft-delete  → `get_active_or_404` (lọc deleted_at IS NULL)

CỐ Ý không gộp thành một hàm với cờ `soft_delete=True`: gọi nhầm cờ thì lỗi im
lặng, còn gọi nhầm tên hàm thì đọc code là thấy.

Tham số `code` giữ lại mã lỗi riêng theo domain. 4 trong 13 service đang ném
`PROJECT_NOT_FOUND`, `PUBLICATION_NOT_FOUND`... thay vì `NOT_FOUND` chung —
đó là cách làm TỐT HƠN vì client phân biệt được, nên helper phải hỗ trợ chứ
không được ép tất cả về một mã.
"""
from typing import Optional, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException, not_found

T = TypeVar("T")


def _missing(message: str, code: Optional[ErrorCode]) -> AppException:
    if code is None:
        return not_found(message)
    return AppException(code, message, 404)


def get_or_404(
    db: Session, model: type[T], pk, message: str, *, code: Optional[ErrorCode] = None
) -> T:
    """Nạp bản ghi theo khoá chính, ném 404 nếu không có.

    Dùng `db.get` chứ không phải `select`: nó tra identity map trước nên không
    phát sinh truy vấn nếu object đã nằm trong session.
    """
    obj = db.get(model, pk)
    if obj is None:
        raise _missing(message, code)
    return obj


def get_active_or_404(
    db: Session, model: type[T], pk, message: str, *, code: Optional[ErrorCode] = None
) -> T:
    """Như `get_or_404` nhưng bỏ qua bản ghi đã xoá mềm.

    Bắt buộc dùng cho bảng có cột `deleted_at`. `db.get` KHÔNG áp được điều kiện
    lọc nên phải đi qua `select`.
    """
    obj = db.execute(
        select(model).where(model.id == pk, model.deleted_at.is_(None))
    ).scalar_one_or_none()
    if obj is None:
        raise _missing(message, code)
    return obj
