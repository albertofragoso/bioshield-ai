"""Rate limiting configuration via slowapi.

Limits:
- Auth endpoints (register/login): 10 req/min per IP  — prevents credential stuffing
- Scan endpoints (barcode/photo):  20 req/min per user — controls Gemini API cost
- Biosync extract:                  5 req/min per user — Gemini Vision on full PDF
- Global fallback:                 60 req/min per IP
"""

from datetime import UTC, datetime, time, timedelta

from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse


def _get_user_or_ip(request: Request) -> str:
    """Key function: use authenticated user_id when available, else fall back to IP.

    This prevents users from bypassing limits by rotating IPs once logged in,
    and avoids penalising users sharing an IP (e.g. corporate NAT).
    """
    # access_token cookie is already validated upstream by get_current_user;
    # here we just need the sub claim as a stable key — decode without raising.
    try:
        import jwt as _jwt

        token = request.cookies.get("access_token")
        if token:
            from app.config import get_settings

            settings = get_settings()
            payload = _jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
            )
            if sub := payload.get("sub"):
                return f"user:{sub}"
    except Exception:
        pass
    return get_remote_address(request)


def _seconds_until_midnight_utc() -> int:
    """Seconds from now until 00:00:00 UTC (when daily token budget resets)."""
    now = datetime.now(UTC)
    midnight = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=UTC)
    return max(1, int((midnight - now).total_seconds()))


import os as _os

_forwarded_allow_ips = _os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")

limiter = Limiter(
    key_func=_get_user_or_ip,
    default_limits=["60/minute"],
    headers_enabled=True,
    strategy="fixed-window",
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "rate_limit_exceeded", "message": str(exc.detail)},
        headers={"Retry-After": "60"},
    )
