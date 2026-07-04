"""Middleware ghi access_stats page_view (M6.3 / FR-RPT-009, BR-RPT-005).

Ghi event_type='page_view' cho GET request vào whitelist trang/module chính, SAU khi
có response (không chặn). Best-effort: mọi lỗi → log WARN, KHÔNG fail request chính
(BR-RPT-013, NFR-PERF-RPT-003 overhead < 5ms). user_id lấy từ JWT (không query DB).

Login event_type='login' KHÔNG ghi ở đây — ghi trong auth flow login thành công
(access_stat_service.record own_transaction=False) để gắn đúng user.
"""
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.db.database import SessionLocal
from app.services import access_stat_service

logger = logging.getLogger("lims.access_stat_mw")


class AccessStatMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Chỉ ghi page_view cho GET whitelist (BR-RPT-005). Bỏ qua mọi lỗi.
        try:
            if request.method == "GET":
                path = request.url.path
                if access_stat_service.is_whitelisted(path):
                    user_id = self._user_id_from_request(request)
                    full_path = path
                    if request.url.query:
                        full_path = f"{path}?{request.url.query}"
                    db = SessionLocal()
                    try:
                        access_stat_service.record(
                            db,
                            user_id=user_id,
                            path=full_path,
                            method="GET",
                            status_code=response.status_code,
                            ip=request.client.host if request.client else None,
                            event_type="page_view",
                            own_transaction=True,
                        )
                    finally:
                        db.close()
        except Exception as exc:  # noqa: BLE001 — KHÔNG bao giờ fail request vì ghi log
            logger.warning("access_stat middleware skipped", extra={"error": str(exc)})

        return response

    @staticmethod
    def _user_id_from_request(request: Request):
        """Lấy user_id từ JWT (best-effort, KHÔNG query DB, KHÔNG raise).

        page_view chưa đăng nhập (login page) → user_id=NULL (§0.9).
        """
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        try:
            import uuid

            from app.core import security

            payload = security.decode_access_token(auth[7:].strip())
            sub = payload.get("sub")
            return uuid.UUID(sub) if sub else None
        except Exception:  # noqa: BLE001 — token hỏng/hết hạn → ghi với user NULL
            return None
