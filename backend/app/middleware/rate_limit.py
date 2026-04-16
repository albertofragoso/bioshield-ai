"""Rate limiting configuration via slowapi.

Limits:
- Auth endpoints (register/login): 10 req/min per IP  — prevents credential stuffing
- Scan endpoints (barcode/photo):  20 req/min per user — controls Gemini API cost
- Global fallback:                 60 req/min per IP
"""

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
        from jose import jwt as _jwt
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


limiter = Limiter(key_func=_get_user_or_ip, default_limits=["60/minute"])


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}. Try again later."},
    )
