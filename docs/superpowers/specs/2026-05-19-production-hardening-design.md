# BioShield AI — Production Hardening Design

**Date:** 2026-05-19
**Status:** Approved (v2 — post deep-review, 2026-05-19)
**Scope:** Rate limiting tweaks, per-user daily token caps, unified error schema, structured JSON logging + request ID correlation

---

## 1. Context & Goals

The product is feature-complete. This spec addresses four orthogonal hardening concerns before production:

1. **Rate limiting** — minor gaps in existing slowapi setup
2. **Token caps per user** — no per-user Gemini budget exists today
3. **Error schema** — ad-hoc messages, no machine-readable error codes
4. **Observability** — stdlib logging only, no JSON structure, no request IDs, no token usage tracking

**Out of scope:** token streaming (deferred), OpenTelemetry (overkill at this stage).

---

## 2. Architecture Overview

```
Request
  │
  ▼
[Middleware: RequestID + JSON Logging]   ← new: app/middleware/logging.py
  │  sets REQUEST_ID_VAR (contextvars)
  ▼
[SlowAPI rate limiting]                  ← existing, minor tweaks
  │
  ▼
[Router endpoint]
  │  Depends(get_current_user)           ← existing
  │  Depends(token_budget(N))            ← new: app/dependencies/token_budget.py
  │    └─ atomic SQL UPDATE enforces cap
  ▼
[Service: gemini.py]
  │  captures usage_metadata via REQUEST_ID_VAR
  ▼
[BackgroundTask: record_token_usage]     ← reconciliation only (not enforcement)
```

**New files:**
- `app/core/context.py` — `REQUEST_ID_VAR = ContextVar('request_id', default=None)`
- `app/middleware/logging.py` — request ID generation + JSON log formatter
- `app/dependencies/token_budget.py` — FastAPI dependency for atomic budget check
- `app/schemas/errors.py` — unified error response schema

**Modified files:**
- `app/main.py` — register logging middleware, global exception handler
- `app/middleware/rate_limit.py` — dynamic `Retry-After`, tighten biosync limit
- `app/services/gemini.py` — capture `usage_metadata` at 4 call sites via contextvars
- `app/routers/scan.py`, `app/routers/biosync.py` — add `Depends(token_budget(N))`
- `app/models/` — add token budget columns to `User` ORM model
- `alembic/versions/` — migration for token budget columns on `users`
- `backend/CLAUDE.md` — note about required `Depends` on LLM endpoints

---

## 3. Rate Limiting Tweaks

### 3.1 Retry-After header

Current 429 handler returns no `Retry-After` header. The value must differ by 429 source:
- **Rate limit 429** → `Retry-After: 60` (sliding window approximation)
- **Token budget 429** → seconds until next midnight UTC (budget resets daily)

```python
def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "rate_limit_exceeded", "message": str(exc.detail)},
        headers={"Retry-After": "60"},
    )

def _seconds_until_midnight_utc() -> int:
    now = datetime.utcnow()
    midnight = datetime.combine(now.date() + timedelta(days=1), time.min)
    return int((midnight - now).total_seconds())
```

The token budget dependency uses `_seconds_until_midnight_utc()` in its 429 `Retry-After` header (see section 4.3).

### 3.2 Explicit limit on `/biosync/upload`

This endpoint calls Gemini Vision with a full PDF — the most expensive call in the system. It currently inherits only the global 60/min fallback. Add `@limiter.limit("5/minute")` on the upload endpoint.

No other rate limit changes. Auth (10/min) and scan (20/min) limits are appropriate.

---

## 4. Per-User Daily Token Budget

### 4.1 Database migration

Two new columns on the `users` table:

```sql
tokens_used_today  INTEGER NOT NULL DEFAULT 0
tokens_budget_date DATE    NOT NULL DEFAULT CURRENT_DATE
```

**ORM model** — column type must be `Date` (not `String`) so SQLAlchemy returns `datetime.date` objects, not raw strings (SQLite returns strings for untyped date columns, causing `TypeError` on `<` comparison):

```python
# app/models/user.py
tokens_used_today  = Column(Integer, nullable=False, server_default="0")
tokens_budget_date = Column(Date, nullable=False, server_default=func.current_date())
```

Reset happens via the atomic SQL UPDATE in the dependency (section 4.3) — no cron job, no in-band reset logic in Python.

### 4.2 Settings

```python
daily_token_budget: int = 50_000  # env: DAILY_TOKEN_BUDGET
```

No `min_threshold` setting — the atomic UPDATE rejects if `tokens_used_today + estimated_tokens > daily_token_budget`. The per-endpoint cost map in section 4.3 defines the effective minimum per call.

### 4.3 Dependency

Factory function — enforces the budget via a single **atomic SQL UPDATE**. This eliminates the read-modify-write race condition and the midnight reset race simultaneously.

```python
# app/dependencies/token_budget.py
from datetime import date, timedelta, datetime, time
from sqlalchemy import update, func

# Per-endpoint estimated token costs — update when Gemini model changes
ENDPOINT_TOKEN_COST: dict[str, int] = {
    "scan_photo": 2_000,
    "scan_barcode": 1_000,
    "biosync_upload": 4_000,
}

def token_budget(estimated_tokens: int):
    """Factory: returns a dependency that atomically reserves `estimated_tokens`.

    Uses a single SQL UPDATE with a WHERE guard — no read-modify-write race.
    Daily reset is handled by resetting tokens_budget_date in the same UPDATE
    when the date has changed.
    """
    assert estimated_tokens > 0, "estimated_tokens must be positive"

    async def _dep(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        settings: Settings = Depends(get_settings),
    ) -> User:
        today = date.today()

        # Atomic UPDATE: resets counter if date changed, then reserves tokens.
        # WHERE guard ensures we only succeed if budget allows the call.
        result = db.execute(
            update(User)
            .where(User.id == current_user.id)
            .where(
                # If date changed: effective used = 0 + estimated (always passes unless budget < estimated)
                # If same day: effective used = tokens_used_today + estimated <= budget
                func.case(
                    (User.tokens_budget_date < today, estimated_tokens),
                    else_=User.tokens_used_today + estimated_tokens,
                )
                <= settings.daily_token_budget
            )
            .values(
                tokens_used_today=func.case(
                    (User.tokens_budget_date < today, estimated_tokens),
                    else_=User.tokens_used_today + estimated_tokens,
                ),
                tokens_budget_date=today,
            )
            .returning(User.tokens_used_today)
        )
        db.commit()

        if result.rowcount == 0:
            retry_after = _seconds_until_midnight_utc()
            raise HTTPException(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                detail={
                    "error": "token_budget_exceeded",
                    "message": "Daily AI token limit reached",
                    "resets_at": (today + timedelta(days=1)).isoformat() + "T00:00:00Z",
                },
            )

        return current_user

    return _dep
```

### 4.4 Usage recording (background task — reconciliation only)

The atomic UPDATE in section 4.3 is the enforcement mechanism. The background task is reconciliation only — it corrects the estimated cost with the actual `usage_metadata.total_token_count` so the daily counter stays accurate for the remainder of the day.

```python
def record_token_usage(user_id: int, estimated: int, actual: int, db: Session) -> None:
    """Reconcile optimistic estimate with actual Gemini token usage.

    Must never raise — a failure here leaves the counter slightly off but
    does not break enforcement (enforcement is the atomic UPDATE in token_budget).
    """
    try:
        db.execute(
            update(User)
            .where(User.id == user_id)
            .values(tokens_used_today=func.greatest(0, User.tokens_used_today - estimated + actual))
        )
        db.commit()
    except Exception:
        logger.exception("record_token_usage failed — counter may be slightly off", extra={"user_id": user_id})
```

If `usage_metadata` is `None` (network error, partial response), pass `actual=estimated` — this is a no-op correction, leaving the optimistic reservation as-is rather than drifting in either direction.

### 4.5 Endpoint wiring

All three endpoints that call Gemini must declare the dependency. Missing one leaves an unguarded LLM path:

```python
# scan.py
@router.post("/photo")
async def scan_photo(
    ...,
    _budget: User = Depends(token_budget(ENDPOINT_TOKEN_COST["scan_photo"])),
):
    ...

@router.post("/barcode")
async def scan_barcode(
    ...,
    _budget: User = Depends(token_budget(ENDPOINT_TOKEN_COST["scan_barcode"])),
):
    ...

# biosync.py
@router.post("/upload")
@limiter.limit("5/minute")
async def upload_biomarkers(
    ...,
    _budget: User = Depends(token_budget(ENDPOINT_TOKEN_COST["biosync_upload"])),
):
    ...
```

**CI gate:** add a test that greps all router files for endpoints calling `gemini.py` functions and asserts `token_budget` appears in their signature. This prevents silent omissions on new endpoints.

---

## 5. Unified Error Schema

### 5.1 Schema

```python
# app/schemas/errors.py

class ErrorResponse(BaseModel):
    error: str               # snake_case machine-readable code
    message: str             # human-readable description
    detail: dict | None = None  # optional context (resets_at, limit, etc.)
```

### 5.2 Error code catalog

| `error` | HTTP | Trigger |
|---|---|---|
| `rate_limit_exceeded` | 429 | slowapi limit hit |
| `token_budget_exceeded` | 429 | daily budget exhausted |
| `gemini_quota_exhausted` | 429 | Gemini `ResourceExhausted` |
| `gemini_unavailable` | 503 | Gemini `GoogleAPIError` |
| `image_invalid` | 400 | malformed base64 |
| `image_too_large` | 413 | > 10 MB |
| `validation_error` | 422 | Pydantic / malformed request |
| `internal_error` | 500 | unexpected exception |

### 5.3 Global exception handler

Registered in `main.py`. Converts any unhandled `Exception` to `{"error": "internal_error", "message": "Unexpected error"}` and includes `X-Request-ID` in the response header for correlation. Existing `HTTPException` raises in `gemini.py` are updated to use the new `error` field names from the catalog.

---

## 6. Structured JSON Logging + Request ID

### 6.1 RequestID middleware (`app/middleware/logging.py`)

`request.state` is scoped to the request object and is not accessible from background tasks or from `gemini.py` (a service layer with no Request reference). Use a `contextvars.ContextVar` instead — it propagates correctly across async calls and background tasks within the same task tree.

```python
# app/core/context.py
from contextvars import ContextVar
REQUEST_ID_VAR: ContextVar[str | None] = ContextVar("request_id", default=None)
```

The middleware:
- Generates `request_id = str(uuid4())` per request
- Sets `REQUEST_ID_VAR.set(request_id)` (propagates to all async callees)
- Also stores in `request.state.request_id` for FastAPI route access if needed
- Adds `X-Request-ID` to the response header
- Logs one line at request completion:

```json
{
  "ts": "2026-05-19T14:52:00Z",
  "level": "INFO",
  "logger": "app.middleware.logging",
  "request_id": "abc-123",
  "msg": "request_complete",
  "method": "POST",
  "path": "/scan/photo",
  "status_code": 200,
  "duration_ms": 2340,
  "user_id": 42
}
```

**Global exception handler** reads `request_id` defensively: `getattr(request.state, "request_id", REQUEST_ID_VAR.get("unknown"))` — prevents `AttributeError` if the middleware failed during startup.

### 6.2 JSON formatter

Stdlib-only (no new dependencies). Configured via `logging.config.dictConfig` in `main.py` on startup. All existing `logger = logging.getLogger(__name__)` calls in the codebase automatically emit JSON.

### 6.3 Gemini token usage logging

At each of the 4 `generate_content_async` call sites in `gemini.py`, extract and log `usage_metadata`. Read `request_id` from `REQUEST_ID_VAR` (not `request.state` — `gemini.py` has no Request reference):

```python
from app.core.context import REQUEST_ID_VAR

usage = getattr(response, "usage_metadata", None)
tokens_total = getattr(usage, "total_token_count", 0)
tokens_prompt = getattr(usage, "prompt_token_count", 0)
tokens_output = getattr(usage, "candidates_token_count", 0)

logger.info("gemini_call_complete", extra={
    "request_id": REQUEST_ID_VAR.get(),
    "tokens_total": tokens_total,
    "tokens_prompt": tokens_prompt,
    "tokens_output": tokens_output,
    "model": settings.gemini_model,
})
```

The `usage_metadata` value (or `None`) is passed to `record_token_usage` background task. When `None`, pass `actual=estimated` (no-op correction — see section 4.4).

---

## 7. Implementation Notes

- `token_budget(N)` must be added to **every endpoint that calls Gemini**: `POST /scan/photo`, `POST /scan/barcode`, `POST /biosync/upload`. A CI test must enforce this (see section 4.5).
- Token budget columns use `DATE` not `TIMESTAMP`. Set `TZ=UTC` in production env — reset granularity is per calendar day UTC.
- `ENDPOINT_TOKEN_COST` in `token_budget.py` must be updated whenever the Gemini model changes. Add a comment flagging this.
- The `detail` field in `ErrorResponse` must never contain `str(exc)` or tracebacks — only structured data. The global handler for `internal_error` strips `detail` entirely; only explicitly raised `HTTPException`s propagate `detail`.
- Pin `google-generativeai` SDK version in `requirements.txt` — `usage_metadata` attribute names have changed across versions.

## 8. Development & Release Process

- **Branch:** all implementation work goes on a feature worktree, never directly on `main`.
- **Docs to update:** `backend/CLAUDE.md` (required Depends note), `docs/architecture.md` (token budget columns + observability stack), `backend/tests/CLAUDE.md` (if test patterns change).
- **Tests:** all existing tests must pass before merge. New tests required: token_budget atomic UPDATE unit test, request_id propagation integration test, CI gate for unguarded Gemini endpoints, `record_token_usage` exception-handling test.
- **Merge gate:** local CI green (pytest + mypy) before pushing the PR branch.
