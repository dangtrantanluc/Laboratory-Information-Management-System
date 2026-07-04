"""Structured JSON logging (rule logging.md).

- Production/staging: JSON 1 dòng/log (dễ parse, có correlationId).
- Dev: vẫn JSON cho nhất quán.
- KHÔNG log password/token (service layer chịu trách nhiệm không truyền vào).
"""
import json
import logging
import sys
from datetime import datetime, timezone

from app.config import settings

_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # các field extra (correlationId, userId, action...) được merge vào
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                base[key] = value
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # Giảm ồn từ uvicorn access (dùng access_stats riêng nếu cần)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
