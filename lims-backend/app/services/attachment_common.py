"""Shared MIME/size validation cho mọi luồng upload attachment (M1/M2/M3/M5/M7).

Trước đây mỗi module tự khai `_ALLOWED_MIME`/`_check_mime` riêng — generic
`attachment_service.create_attachment` (dùng bởi chemical/hr_profile/publication/
equipment qua router riêng, và trực tiếp bởi `POST /attachments` cho MỌI
owner_type) không kiểm tra gì cả, cho phép upload bất kỳ content-type nào
(PRODUCTION_READINESS_REVIEW §Security: "No MIME/extension validation on the
generic attachment upload path"). Module này là allowlist nền tảng dùng chung;
domain nào cần thêm loại đặc thù (vd document version cho DOCX/DOC) thì mở
rộng từ `BASE_ALLOWED_MIME` thay vì tự định nghĩa lại từ đầu.
"""
from typing import Optional

from app.config import settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import unprocessable

# Allowlist nền tảng (gốc từ sample_attachment_service — BR-SAMPLE-012).
BASE_ALLOWED_MIME = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
}

# Superset dùng cho luồng upload đa owner_type (generic `attachment_service` — dùng
# bởi chemical/hr_profile/publication/equipment/document/form/... qua `POST /attachments`).
# Union của mọi whitelist đặc thù hiện có (MSDS/competence/publication/equipment doc)
# để không phá vỡ use case hợp lệ nào, đồng thời vẫn chặn HTML/SVG/executable.
GENERIC_ALLOWED_MIME = BASE_ALLOWED_MIME | {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword",  # .doc
    # Kho biểu mẫu VILAS có tài liệu trình bày (vd "Sơ đồ Viện.pptx" — sơ đồ tổ chức
    # thuộc điều khoản 5). Chỉ mở cho nhóm GENERIC (biểu mẫu/minh chứng), KHÔNG mở ở
    # BASE để các module khác giữ nguyên phạm vi hẹp.
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
    "application/vnd.ms-powerpoint",  # .ppt
}


def check_mime(mime: Optional[str], *, allowed: Optional[set] = None) -> None:
    allowed_set = allowed if allowed is not None else BASE_ALLOWED_MIME
    if mime is None or mime.lower() not in allowed_set:
        raise unprocessable(
            ErrorCode.INVALID_FILE_TYPE,
            "Định dạng tệp không hợp lệ",
        )


def check_size(content: bytes) -> None:
    # Lớp kiểm tra size CHÍNH XÁC theo bytes thực đã đọc (Content-Length có thể vắng/giả
    # với chunked). Chặn sớm theo Content-Length do RequestLimitsMiddleware đảm nhiệm (M7).
    if len(content) > settings.max_upload_size_bytes:
        raise unprocessable(
            ErrorCode.FILE_TOO_LARGE,
            f"Tệp vượt quá giới hạn {settings.max_upload_size_bytes // (1024 * 1024)}MB",
        )


def is_inline_safe(mime: Optional[str], *, allowed: Optional[set] = None) -> bool:
    """True nếu mime nằm trong allowlist an toàn để phục vụ Content-Disposition: inline.

    Dùng ở đường tải file (không phải upload) để chặn stored-XSS: một attachment
    có content-type ngoài allowlist (vd text/html, image/svg+xml) KHÔNG BAO GIỜ
    được trả về inline, kể cả khi client yêu cầu `disposition=inline` — luôn ép
    về `attachment` bất kể client yêu cầu gì.
    """
    allowed_set = allowed if allowed is not None else BASE_ALLOWED_MIME
    return mime is not None and mime.lower() in allowed_set
