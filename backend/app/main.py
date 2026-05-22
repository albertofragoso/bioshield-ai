import logging
import logging.config

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.core.context import REQUEST_ID_VAR
from app.middleware.logging import LOGGING_CONFIG, RequestIDMiddleware
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.routers import analytics, auth, biosync, scan

settings = get_settings()

logging.config.dictConfig(LOGGING_CONFIG)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Attach limiter so @limiter.limit decorators can resolve it from app.state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "0"
    if not settings.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _log = logging.getLogger("app.main")
    _log.exception("unhandled_exception", exc_info=exc)
    rid: str = getattr(request.state, "request_id", None) or REQUEST_ID_VAR.get() or "unknown"
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "An unexpected error occurred"},
        headers={"X-Request-ID": rid},
    )


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(scan.router, prefix="/scan", tags=["scan"])
app.include_router(scan.public_router, prefix="/scan", tags=["scan"])
app.include_router(biosync.router, prefix="/biosync", tags=["biosync"])
app.include_router(analytics.router, tags=["analytics"])


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "app": settings.app_name}
