# BioShield AI — Production Hardening Design

**Date:** 2026-05-19
**Status:** Approved
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
  │
  ▼
[SlowAPI rate limiting]                  ← existing, minor tweaks
  │
  ▼
[Router endpoint]
  │  Depends(get_current_user)           ← existing
  │  Depends(consume_token_budget)       ← new: app/dependencies/token_budget.py
  ▼
[Service: gemini.py]
  │  captures usage_metadata             ← 3 lines per call site
  ▼
[BackgroundTask: record_token_usage]     ← new, runs after response sent
```

**New files:**
- `app/middleware/logging.py` — request ID generation + JSON log formatter
- `app/dependencies/token_budget.py` — FastAPI dependency for budget check + deduction
- `app/schemas/errors.py` — unified error response schema

**Modified files:**
- `app/main.py` — register logging middleware, global exception handler
- `app/middleware/rate_limit.py` — add `Retry-After` header, tighten biosync limit
- `app/services/gemini.py` — capture `usage_metadata` at 4 call sites
- `app/routers/scan.py`, `app/routers/biosync.py` — add `Depends(consume_token_budget)`
- `alembic/versions/` — migration for token budget columns on `users`
- `backend/CLAUDE.md` — note about required `Depends` on LLM endpoints

---

## 3. Rate Limiting Tweaks

### 3.1 Retry-After header

Current 429 handler returns no `Retry-After` header. Fix:

```python
def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "rate_limit_exceeded", "message": str(exc.detail)},
        headers={"Retry-After": "60"},
    )
```

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

Reset is implicit: if `tokens_budget_date < today`, the dependency resets both columns to `0` and `today` before checking. No cron job required.

### 4.2 Settings

```python
daily_token_budget: int = 50_000  # env: DAILY_TOKEN_BUDGET
token_budget_min_threshold: int = 500  # min remaining to allow a call
```

### 4.3 Dependency

Factory function — returns a FastAPI-compatible dependency with the estimated cost baked in:

```python
# app/dependencies/token_budget.py

def token_budget(estimated_tokens: int):
    """Factory: returns a dependency that checks and reserves `estimated_tokens`."""

    async def _dep(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        settings: Settings = Depends(get_settings),
    ) -> User:
        today = date.today()

        # Implicit daily reset
        if current_user.tokens_budget_date < today:
            current_user.tokens_used_today = 0
            current_user.tokens_budget_date = today

        remaining = settings.daily_token_budget - current_user.tokens_used_today
        if remaining < settings.token_budget_min_threshold:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "token_budget_exceeded",
                    "message": "Daily AI token limit reached",
                    "resets_at": (today + timedelta(days=1)).isoformat() + "T00:00:00Z",
                },
            )

        # Optimistic reservation
        current_user.tokens_used_today += estimated_tokens
        db.commit()
        return current_user

    return _dep
```

### 4.4 Usage recording (background task)

After each Gemini call, a background task corrects the optimistic reservation with the actual `usage_metadata.total_token_count`:

```python
def record_token_usage(user_id: int, estimated: int, actual: int, db: Session) -> None:
    user = db.get(User, user_id)
    if user:
        user.tokens_used_today = max(0, user.tokens_used_today - estimated + actual)
        db.commit()
```

### 4.5 Endpoint wiring

Endpoints that call Gemini declare the dependency with their estimated token cost:

```python
# scan.py
@router.post("/photo")
async def scan_photo(
    ...,
    _budget: User = Depends(token_budget(2000)),
):
    ...

# biosync.py /upload
@router.post("/upload")
@limiter.limit("5/minute")
async def upload_biomarkers(
    ...,
    _budget: User = Depends(token_budget(4000)),
):
    ...
```

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

- Generates `request_id = str(uuid4())` per request
- Stores in `request.state.request_id`
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

### 6.2 JSON formatter

Stdlib-only (no new dependencies). Configured via `logging.config.dictConfig` in `main.py` on startup. All existing `logger = logging.getLogger(__name__)` calls in the codebase automatically emit JSON.

### 6.3 Gemini token usage logging

At each of the 4 `generate_content_async` call sites in `gemini.py`, extract and log `usage_metadata` after a successful response:

```python
usage = getattr(response, "usage_metadata", None)
logger.info("gemini_call_complete", extra={
    "tokens_total": getattr(usage, "total_token_count", 0),
    "tokens_prompt": getattr(usage, "prompt_token_count", 0),
    "tokens_output": getattr(usage, "candidates_token_count", 0),
    "model": settings.gemini_model,
})
```

This same `usage_metadata` value is passed to `record_token_usage` background task.

---

## 7. Implementation Notes

- `consume_token_budget` must be added to **every endpoint that calls Gemini**. Current endpoints: `POST /scan/photo`, `POST /scan/barcode` (if it calls reconciler), `POST /biosync/upload`. See backend `CLAUDE.md` for the rule.
- `POST /scan/barcode` calls `reconcile_ingredient` and `generate_personalized_insight` — include in token budget scope with `estimated_tokens=1000`.
- The `Retry-After: 60` value on rate limit responses is a fixed approximation (slowapi uses sliding window). Acceptable for v1.
- Token budget columns use `DATE` not `TIMESTAMP` — reset granularity is per calendar day in the server's local timezone. Set `TZ=UTC` in production env.
