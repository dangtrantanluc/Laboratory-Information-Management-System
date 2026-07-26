"""Middleware ghi access_stats page_view (M6.3 / FR-RPT-009, BR-RPT-005).

Ghi event_type='page_view' cho GET request vào whitelist trang/module chính, SAU khi
có response (không chặn). Best-effort: mọi lỗi → log WARN, KHÔNG fail request chính
(BR-RPT-013, NFR-PERF-RPT-003 overhead < 5ms). user_id lấy từ JWT (không query DB).

Ghi chạy nền qua threadpool (KHÔNG await trực tiếp trên event loop) — psycopg2 là
driver đồng bộ, gọi insert+commit ngay trong coroutine sẽ chặn toàn bộ event loop
cho mọi request khác đang chờ (PRODUCTION_READINESS_REVIEW §Performance: "Async
middleware performs a blocking sync DB write on nearly every GET request"). Dùng
asyncio.create_task để không trì hoãn việc trả response cho chính request hiện tại.

Login event_type='login' KHÔNG ghi ở đây — ghi trong auth flow login thành công
(access_stat_service.record own_transaction=False) để gắn đúng user.
"""
import asyncio
import logging

from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.request_meta import client_ip
from app.db.database import SessionLocal
from app.services import access_stat_service

logger = logging.getLogger("lims.access_stat_mw")

# Giữ tham chiếu task nền đang chạy — asyncio không giữ strong ref cho task tạo bằng
# create_task, để rơi vào GC giữa chừng có thể khiến task bị hủy trước khi ghi xong.
_background_tasks: set[asyncio.Task] = set()


async def drain_background_tasks() -> None:
    """Chờ mọi page_view-write đang chạy hoàn tất khi tắt app (L1) — tránh mất bản ghi."""
    if _background_tasks:
        await asyncio.gather(*list(_background_tasks), return_exceptions=True)


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
                    # Qua client_ip() để lấy X-Real-IP: request.client.host là IP
                    # của nginx, và access_stats.ip cũng là cột INET (M-09/T1.5).
                    ip = client_ip(request)
                    task = asyncio.create_task(
                        self._record_page_view(
                            user_id, full_path, response.status_code, ip
                        )
                    )
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)
        except Exception as exc:  # noqa: BLE001 — KHÔNG bao giờ fail request vì ghi log
            logger.warning("access_stat middleware skipped", extra={"error": str(exc)})

        return response

    @staticmethod
    async def _record_page_view(user_id, path, status_code, ip):
        try:
            await run_in_threadpool(
                AccessStatMiddleware._record_sync, user_id, path, status_code, ip
            )
        except Exception as exc:  # noqa: BLE001 — best-effort, KHÔNG raise trong background task
            logger.warning("access_stat write skipped", extra={"error": str(exc)})

    @staticmethod
    def _record_sync(user_id, path, status_code, ip) -> None:
        db = SessionLocal()
        try:
            access_stat_service.record(
                db,
                user_id=user_id,
                path=path,
                method="GET",
                status_code=status_code,
                ip=ip,
                event_type="page_view",
                own_transaction=True,
            )
        finally:
            db.close()

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
