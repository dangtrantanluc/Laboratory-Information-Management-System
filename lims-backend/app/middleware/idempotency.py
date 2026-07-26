"""Idempotency-Key middleware — chống tạo trùng khi client retry POST đã timeout.

Mã (request_code/sample_code/...) sinh bằng COUNT()+1 dedupe theo tính duy nhất, KHÔNG
theo ý định client — một POST bị timeout rồi client thử lại (hoặc double-click) sẽ tạo
2 bản ghi thật: 2 phiếu yêu cầu, hoặc tệ hơn 2 giao dịch kho làm sai lệch tồn
(PRODUCTION_READINESS_REVIEW §API: "No idempotency-key support anywhere; a retried
timed-out request guarantees duplicates").

Cơ chế (opt-in, chỉ kích hoạt khi client gửi header `Idempotency-Key` trên POST):
- CHỈ áp dụng khi request có JWT hợp lệ (namespace theo user). Không xác định được user
  → bỏ qua idempotency (tránh 2 caller "anon" cùng key đọc nhầm response của nhau — M3).
- Khoá theo (user, method, path, key) — key của user A KHÔNG thể trả response của user B.
- SET NX 'PENDING' → giành quyền xử lý. Nếu đã tồn tại:
    * value == PENDING  → request trùng đang chạy → 409 IDEMPOTENCY_IN_PROGRESS.
    * ngược lại         → response đã cache → REPLAY nguyên trạng (status + body).
- Chỉ cache response 2xx (thành công), thân nhỏ (≤ _MAX_CACHE_BYTES) với TTL 24h.
  Response streaming/tải file lớn KHÔNG cache (M2). Response lỗi → xoá khoá để retry.
- Mọi lệnh Redis chạy qua threadpool (KHÔNG block event loop — H2/A1c).
- Redis lỗi → fail-open (bỏ qua idempotency) — cùng triết lý best-effort với rate-limit.
"""
import base64
import json
import logging

from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.redis_client import get_redis

logger = logging.getLogger("lims.idempotency")

_PENDING = "\x00PENDING\x00"
_RESULT_TTL_SECONDS = 24 * 3600
# PENDING TTL phải >= thời gian tối đa 1 handler chạy, nếu không marker hết hạn giữa
# chừng → client retry lại re-chạy op → đúng cái trùng lặp mà middleware phải chặn (M1).
# Đặt bằng trần request-timeout thực tế (uvicorn/proxy) — 5 phút.
_PENDING_TTL_SECONDS = 300
# Không cache thân response quá lớn (export/tải file) — tránh phình RAM/Redis (M2).
_MAX_CACHE_BYTES = 256 * 1024


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key = request.headers.get("Idempotency-Key")
        if request.method != "POST" or not key:
            return await call_next(request)

        # M3: chỉ áp dụng cho request có danh tính (JWT hợp lệ). Không có user → bỏ qua,
        # tránh 2 caller "anon" cùng key va nhau và đọc nhầm response của nhau.
        user_id = self._user_id_from_request(request)
        if not user_id:
            return await call_next(request)

        redis_key = f"idem:{user_id}:{request.method}:{request.url.path}:{key}"
        try:
            r = get_redis()
            acquired = await run_in_threadpool(
                r.set, redis_key, _PENDING, nx=True, ex=_PENDING_TTL_SECONDS
            )
        except Exception as exc:  # noqa: BLE001 — Redis lỗi → fail-open
            logger.warning("idempotency skipped (Redis unavailable)", extra={"error": str(exc)})
            return await call_next(request)

        if not acquired:
            try:
                existing = await run_in_threadpool(r.get, redis_key)
            except Exception:  # noqa: BLE001
                return await call_next(request)
            if existing == _PENDING:
                return JSONResponse(
                    status_code=409,
                    content={
                        "success": False,
                        "error": {
                            "code": "IDEMPOTENCY_IN_PROGRESS",
                            "message": "Yêu cầu trùng đang được xử lý, vui lòng chờ.",
                        },
                    },
                )
            return self._replay(existing)

        # Đã giành quyền xử lý — chạy thật, buffer response để cache.
        try:
            response = await call_next(request)
        except Exception:
            # Endpoint ném exception (sẽ thành 500) — xoá khoá để cho retry.
            await self._safe_delete(r, redis_key)
            raise

        body = b""
        too_large = False
        async for chunk in response.body_iterator:
            body += chunk
            if len(body) > _MAX_CACHE_BYTES:
                too_large = True  # M2: thân quá lớn (export/tải file) → không cache

        cacheable = 200 <= response.status_code < 300 and not too_large
        if cacheable:
            try:
                await run_in_threadpool(
                    r.setex, redis_key, _RESULT_TTL_SECONDS, self._serialize(response, body)
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("idempotency cache write failed", extra={"error": str(exc)})
        else:
            # Lỗi nghiệp vụ (4xx/5xx) hoặc thân quá lớn → không cache, cho client thử lại.
            await self._safe_delete(r, redis_key)

        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
            background=response.background,  # L7: giữ BackgroundTask nếu handler gắn
        )

    @staticmethod
    def _serialize(response: Response, body: bytes) -> str:
        return json.dumps(
            {
                "status": response.status_code,
                "media_type": response.media_type,
                "body_b64": base64.b64encode(body).decode("ascii"),
            }
        )

    @staticmethod
    def _replay(raw: str) -> Response:
        data = json.loads(raw)
        body = base64.b64decode(data["body_b64"])
        return Response(
            content=body,
            status_code=data["status"],
            media_type=data.get("media_type"),
            headers={"Idempotency-Replayed": "true"},
        )

    @staticmethod
    async def _safe_delete(r, redis_key: str) -> None:
        try:
            await run_in_threadpool(r.delete, redis_key)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _user_id_from_request(request: Request):
        """Lấy user_id từ JWT (best-effort, KHÔNG query DB) để namespace khoá theo user."""
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        try:
            from app.core import security

            payload = security.decode_access_token(auth[7:].strip())
            return payload.get("sub")
        except Exception:  # noqa: BLE001
            return None
