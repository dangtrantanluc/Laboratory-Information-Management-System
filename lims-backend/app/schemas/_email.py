"""Email validation cho LIMS nội bộ — cho phép special-use TLD (vd .local).

Pydantic EmailStr / email-validator chặn .local/.localhost (special-use). Hệ thống
nội bộ ~40 user dùng admin@lims.local (theo contract) → ta dùng regex RFC-pragmatic:
- 1 ký tự '@', local-part + domain hợp lệ, có ít nhất 1 dấu '.' ở domain.
- Lowercase chuẩn hóa. KHÔNG check deliverability (offline).
"""
import re
from typing import Annotated

from pydantic import AfterValidator

# Local-part: chữ/số và .!#$%&'*+/=?^_`{|}~- ; domain: nhãn chữ-số-gạch, phân tách dấu chấm
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def _validate_email(value: str) -> str:
    v = value.strip().lower()
    if len(v) > 255:
        raise ValueError("Email vượt quá 255 ký tự")
    if not _EMAIL_RE.match(v):
        raise ValueError("Email không hợp lệ")
    return v


# Email type dùng chung: validate + lowercase, chấp nhận .local
Email = Annotated[str, AfterValidator(_validate_email)]
