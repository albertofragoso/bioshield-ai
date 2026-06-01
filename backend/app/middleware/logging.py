# backend/app/middleware/logging.py
import logging
import logging.config
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.context import REQUEST_ID_VAR

logger = logging.getLogger(__name__)

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "app.middleware.logging.JsonFormatter",
        }
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        }
    },
    "root": {
        "handlers": ["default"],
        "level": "INFO",
    },
}


# Exact field names that are always redacted.
_SENSITIVE_EXACT: frozenset[str] = frozenset({"password", "secret", "token"})
# Field name suffixes that trigger redaction (e.g. jwt_key, access_token).
_SENSITIVE_SUFFIXES: tuple[str, ...] = ("_key", "_password", "_secret", "_token")


def _should_redact(key: str) -> bool:
    k = key.lower()
    return k in _SENSITIVE_EXACT or k.endswith(_SENSITIVE_SUFFIXES)


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line with standard + extra fields."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import UTC, datetime

        payload: dict = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if (rid := REQUEST_ID_VAR.get()) is not None:
            payload["request_id"] = rid
        _SKIP = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "taskName",
        }
        for key, val in record.__dict__.items():
            if key not in _SKIP:
                payload[key] = "[REDACTED]" if _should_redact(key) else val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generates a UUID per request, sets REQUEST_ID_VAR, adds X-Request-ID header."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid4())
        token = REQUEST_ID_VAR.set(request_id)
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            REQUEST_ID_VAR.reset(token)

        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_complete",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
