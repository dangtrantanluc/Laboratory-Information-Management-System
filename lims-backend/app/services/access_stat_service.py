"""Access-stat service (M6.3) — GHI access_stats (login + page_view) best-effort.

Ngoại lệ READ-ONLY hợp lệ của M6 (CONSTRAINT-2 / FR-RPT-009). Ghi KHÔNG chặn request:
mọi lỗi ghi → log WARN, KHÔNG raise (BR-RPT-013). Lọc query string nhạy cảm khỏi path
(logging.md). Chỉ ghi page_view cho whitelist trang chính (BR-RPT-005).
"""
import logging
import re
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.access_stat import AccessStat

logger = logging.getLogger("lims.access_stat")

# Whitelist prefix các trang/module chính (FR-RPT-009, BR-RPT-005). Đường dẫn API tương
# ứng trang FE — middleware bắt request GET các prefix này; #14 cho SPA navigation.
WHITELIST_PREFIXES = (
    "/api/v1/dashboard",
    "/api/v1/reports",
    "/api/v1/samples",
    "/api/v1/test-requests",
    "/api/v1/chemicals",
    "/api/v1/chemical-lots",
    "/api/v1/inventory",
    "/api/v1/documents",
    "/api/v1/equipments",
    "/api/v1/calibrations",
    "/api/v1/hr-profiles",
    "/api/v1/research-projects",
    "/api/v1/research-publications",
    "/api/v1/research-achievements",
    "/api/v1/notifications",
    "/api/v1/audit-logs",
    "/api/v1/users",
    "/api/v1/departments",
    # FE route nội bộ (SPA — #14 page-view gửi path FE không có prefix API)
    "/dashboard",
    "/samples",
    "/chemicals",
    "/inventory",
    "/documents",
    "/equipments",
    "/hr",
    "/hr-profiles",
    "/research",
    "/reports",
    "/notifications",
)

# query string chứa các key này bị strip khỏi path trước khi ghi (logging.md)
_SENSITIVE_QS = re.compile(r"(token|secret|password|access_token|refresh_token)", re.I)


def is_whitelisted(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") or path == p for p in WHITELIST_PREFIXES)


def _strip_sensitive(path: str) -> str:
    """Bỏ query string nếu chứa key nhạy cảm; giữ path. Cắt tối đa 512 ký tự (cột DB)."""
    if "?" in path:
        base, qs = path.split("?", 1)
        if _SENSITIVE_QS.search(qs):
            path = base
    return path[:512]


def record(
    db: Session,
    *,
    user_id: Optional[uuid.UUID],
    path: str,
    method: Optional[str],
    status_code: Optional[int],
    ip: Optional[str],
    event_type: str,
    own_transaction: bool = True,
) -> None:
    """Ghi 1 bản ghi access_stats. Best-effort — lỗi KHÔNG raise (BR-RPT-013).

    own_transaction=True: tự commit (dùng cho middleware/#14 với session riêng).
    own_transaction=False: chỉ flush (caller trong transaction khác — vd login flow).
    """
    try:
        entry = AccessStat(
            user_id=user_id,
            path=_strip_sensitive(path),
            method=(method or "")[:8] or None,
            status_code=status_code,
            ip=ip,
            event_type=event_type,
        )
        db.add(entry)
        if own_transaction:
            db.commit()
        else:
            db.flush()
    except Exception as exc:  # noqa: BLE001 — ghi access_stats KHÔNG được fail request
        logger.warning(
            "access_stats write failed",
            extra={"event_type": event_type, "path": path, "error": str(exc)},
        )
        if own_transaction:
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                pass
