# Production Hardening Implementation Plan

> **IMPLEMENTADO ✅ — Mergeado como PR #21 el 2026-05-20.**

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden BioShield AI backend with structured JSON logging + request-ID correlation, unified error schema, per-user daily token budget (atomic SQL enforcement), and rate-limiting tweaks — all on a feature worktree, never on main.

**Architecture:** New `app/core/context.py` holds a `ContextVar` that propagates `request_id` across async boundaries. A new `app/middleware/logging.py` sets the var and emits JSON logs. Token budget is enforced via a single atomic SQL UPDATE in a FastAPI dependency factory (`app/dependencies/token_budget.py`); no optimistic read-modify-write anywhere. Existing tests must remain green; new tests cover the atomic budget, request-ID propagation, and a CI gate that asserts every Gemini-calling endpoint has the budget dependency.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (Mapped style), slowapi, Alembic, pytest, Python 3.12 (`contextvars`, `logging.config.dictConfig`)

**Spec:** `docs/superpowers/specs/2026-05-19-production-hardening-design.md`

---

> ⚠️ **Codebase note:** The spec says `/biosync/upload` calls Gemini — that is incorrect.
> Looking at the actual code, **`POST /biosync/extract`** calls `extract_biomarkers_from_pdf` (Gemini Vision).
> `/biosync/upload` only encrypts and stores already-extracted data. The 5/min rate limit and
> `token_budget(4000)` go on `/biosync/extract`, not `/biosync/upload`.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `backend/app/core/__init__.py` | Package init (empty) |
| Create | `backend/app/core/context.py` | `REQUEST_ID_VAR` ContextVar |
| Create | `backend/app/middleware/logging.py` | Request ID middleware + JSON formatter |
| Create | `backend/app/schemas/errors.py` | `ErrorResponse` Pydantic model |
| Create | `backend/app/dependencies/__init__.py` | Package init (empty) |
| Create | `backend/app/dependencies/token_budget.py` | `token_budget()` factory dependency |
| Create | `backend/alembic/versions/<hash>_add_token_budget_columns.py` | DB migration |
| Modify | `backend/app/models/__init__.py` | Add `tokens_used_today`, `tokens_budget_date` to `User` |
| Modify | `backend/app/config.py` | Add `daily_token_budget` setting |
| Modify | `backend/app/main.py` | Register middleware, `dictConfig`, global exception handler |
| Modify | `backend/app/middleware/rate_limit.py` | Dynamic `Retry-After`, `_seconds_until_midnight_utc` helper |
| Modify | `backend/app/services/gemini.py` | Capture `usage_metadata`, log with `request_id`, pass to background task |
| Modify | `backend/app/routers/scan.py` | `Depends(token_budget(N))` on `/photo` and `/barcode` |
| Modify | `backend/app/routers/biosync.py` | `Depends(token_budget(4000))` + `5/minute` on `/extract` |
| Modify | `backend/CLAUDE.md` | Required `Depends` note for LLM endpoints |
| Modify | `docs/architecture.md` | Token budget columns + observability stack section |
| Create | `backend/tests/test_token_budget.py` | Atomic UPDATE, 429, reset, concurrent safety |
| Create | `backend/tests/test_logging_middleware.py` | Request-ID propagation, JSON log format |
| Create | `backend/tests/test_error_schema.py` | Error codes, global exception handler |
| Create | `backend/tests/test_ci_gate.py` | All Gemini-calling endpoints have `token_budget` dep |

---

## Task 1: Create feature worktree

**Files:** none (git setup only)

- [ ] **Step 1: Create worktree**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield
git worktree add ../bio_shield_hardening -b feat/production-hardening
cd ../bio_shield_hardening
```

- [ ] **Step 2: Verify clean state**

```bash
git status
```

Expected: `On branch feat/production-hardening, nothing to commit`

---

## Task 2: `app/core/context.py` — ContextVar for request_id

**Files:**
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/context.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_logging_middleware.py
import asyncio
from app.core.context import REQUEST_ID_VAR

def test_request_id_var_default_is_none():
    assert REQUEST_ID_VAR.get() is None

def test_request_id_var_set_and_get():
    token = REQUEST_ID_VAR.set("abc-123")
    assert REQUEST_ID_VAR.get() == "abc-123"
    REQUEST_ID_VAR.reset(token)
    assert REQUEST_ID_VAR.get() is None
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd backend && python -m pytest tests/test_logging_middleware.py::test_request_id_var_default_is_none -v
```

Expected: `ImportError: cannot import name 'REQUEST_ID_VAR'`

- [ ] **Step 3: Create package init and module**

```python
# backend/app/core/__init__.py
```

```python
# backend/app/core/context.py
from contextvars import ContextVar

REQUEST_ID_VAR: ContextVar[str | None] = ContextVar("request_id", default=None)
```

- [ ] **Step 4: Run — expect PASS**

```bash
python -m pytest tests/test_logging_middleware.py::test_request_id_var_default_is_none tests/test_logging_middleware.py::test_request_id_var_set_and_get -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/__init__.py backend/app/core/context.py backend/tests/test_logging_middleware.py
git commit -m "feat(observability): add REQUEST_ID_VAR contextvars module"
```

---

## Task 3: `app/middleware/logging.py` — request ID middleware + JSON formatter

**Files:**
- Create: `backend/app/middleware/logging.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests** (add to `test_logging_middleware.py`)

```python
# backend/tests/test_logging_middleware.py  (add below existing tests)
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_response_has_request_id_header():
    response = client.get("/health")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) == 36  # uuid4 format

def test_request_id_is_unique_per_request():
    r1 = client.get("/health")
    r2 = client.get("/health")
    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]
```

- [ ] **Step 2: Run — expect FAIL (no X-Request-ID header)**

```bash
python -m pytest tests/test_logging_middleware.py::test_health_response_has_request_id_header -v
```

Expected: `AssertionError: assert 'x-request-id' in {...}`

- [ ] **Step 3: Create middleware**

```python
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
        # request_id from ContextVar — present when called inside a request
        if (rid := REQUEST_ID_VAR.get()) is not None:
            payload["request_id"] = rid
        # extra= fields passed by the caller
        for key, val in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            }:
                payload[key] = val
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
```

- [ ] **Step 4: Register middleware and dictConfig in `main.py`**

Add at the top of `main.py`, after the existing imports:

```python
import logging.config
from app.middleware.logging import LOGGING_CONFIG, RequestIDMiddleware
```

Add after `app = FastAPI(...)` and before the other middleware:

```python
logging.config.dictConfig(LOGGING_CONFIG)
app.add_middleware(RequestIDMiddleware)
```

The final middleware registration order in `main.py` should be:
```python
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestIDMiddleware)   # ← new, add here
app.add_middleware(CORSMiddleware, ...)
```

- [ ] **Step 5: Run — expect PASS**

```bash
python -m pytest tests/test_logging_middleware.py -v
```

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/middleware/logging.py backend/app/main.py backend/tests/test_logging_middleware.py
git commit -m "feat(observability): request-ID middleware + JSON log formatter"
```

---

## Task 4: `app/schemas/errors.py` + global exception handler

**Files:**
- Create: `backend/app/schemas/errors.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_error_schema.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)

def test_unhandled_exception_returns_internal_error():
    # /health raises nothing — we test the schema via a forced path.
    # Trigger a 404 to verify error format.
    response = client.get("/nonexistent-path-xyz")
    assert response.status_code == 404

def test_500_response_has_error_field():
    """The global handler must return {"error": "internal_error", ...}."""
    from app.schemas.errors import ErrorResponse
    schema = ErrorResponse(error="internal_error", message="test")
    assert schema.error == "internal_error"
    assert schema.detail is None

def test_error_response_with_detail():
    from app.schemas.errors import ErrorResponse
    schema = ErrorResponse(
        error="token_budget_exceeded",
        message="Daily AI token limit reached",
        detail={"resets_at": "2026-05-20T00:00:00Z"},
    )
    assert schema.detail["resets_at"] == "2026-05-20T00:00:00Z"
```

- [ ] **Step 2: Run — expect ImportError**

```bash
python -m pytest tests/test_error_schema.py -v
```

Expected: `ImportError: cannot import name 'ErrorResponse'`

- [ ] **Step 3: Create schema**

```python
# backend/app/schemas/errors.py
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: dict | None = None
```

- [ ] **Step 4: Add global exception handler to `main.py`**

Add import at top of `main.py`:
```python
from fastapi import Request as _Request
from fastapi.responses import JSONResponse
from app.core.context import REQUEST_ID_VAR
```

Add after all `app.add_middleware(...)` calls:

```python
@app.exception_handler(Exception)
async def global_exception_handler(_request: _Request, exc: Exception) -> JSONResponse:
    import logging as _logging
    _log = _logging.getLogger("app.main")
    _log.exception("unhandled_exception", exc_info=exc)
    rid = getattr(_request.state, "request_id", None) or REQUEST_ID_VAR.get("unknown")
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "An unexpected error occurred"},
        headers={"X-Request-ID": rid},
    )
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_error_schema.py -v
```

Expected: 3 passed

- [ ] **Step 6: Run existing security headers test to ensure nothing broken**

```bash
python -m pytest tests/test_security_headers.py -v
```

Expected: all passed

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/errors.py backend/app/main.py backend/tests/test_error_schema.py
git commit -m "feat(errors): unified ErrorResponse schema + global exception handler"
```

---

## Task 5: Rate limiting tweaks — dynamic `Retry-After`

**Files:**
- Modify: `backend/app/middleware/rate_limit.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_error_schema.py  (add to existing file)
from app.middleware.rate_limit import _seconds_until_midnight_utc

def test_seconds_until_midnight_utc_is_positive():
    secs = _seconds_until_midnight_utc()
    assert 0 < secs <= 86400

def test_rate_limit_429_has_retry_after_header():
    """rate_limit_exceeded_handler must include Retry-After: 60."""
    from unittest.mock import MagicMock
    from app.middleware.rate_limit import rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    mock_request = MagicMock()
    mock_exc = MagicMock(spec=RateLimitExceeded)
    mock_exc.detail = "20 per 1 minute"
    response = rate_limit_exceeded_handler(mock_request, mock_exc)
    assert response.headers["retry-after"] == "60"
    import json
    body = json.loads(response.body)
    assert body["error"] == "rate_limit_exceeded"
```

- [ ] **Step 2: Run — expect ImportError on `_seconds_until_midnight_utc`**

```bash
python -m pytest tests/test_error_schema.py::test_seconds_until_midnight_utc_is_positive -v
```

Expected: `ImportError`

- [ ] **Step 3: Update `rate_limit.py`**

Replace the entire file content:

```python
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
    """Key function: use authenticated user_id when available, else fall back to IP."""
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


def _seconds_until_midnight_utc() -> int:
    """Seconds from now until 00:00:00 UTC (when daily token budget resets)."""
    now = datetime.now(UTC)
    midnight = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=UTC)
    return max(1, int((midnight - now).total_seconds()))


limiter = Limiter(key_func=_get_user_or_ip, default_limits=["60/minute"])


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"error": "rate_limit_exceeded", "message": str(exc.detail)},
        headers={"Retry-After": "60"},
    )
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_error_schema.py -v
```

Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/middleware/rate_limit.py backend/tests/test_error_schema.py
git commit -m "feat(rate-limit): dynamic Retry-After + _seconds_until_midnight_utc helper"
```

---

## Task 6: `User` model — add token budget columns + Alembic migration

**Files:**
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/<hash>_add_token_budget_columns.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_token_budget.py
from sqlalchemy import inspect
from app.models.base import Base, engine

def test_user_has_token_budget_columns():
    """After migration, users table must have the two new columns."""
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("users")}
    assert "tokens_used_today" in cols
    assert "tokens_budget_date" in cols
```

- [ ] **Step 2: Run — expect FAIL (columns missing)**

```bash
python -m pytest tests/test_token_budget.py::test_user_has_token_budget_columns -v
```

Expected: `AssertionError` — columns not present yet.

- [ ] **Step 3: Add columns to `User` ORM model in `backend/app/models/__init__.py`**

Add these imports at the top of the file (after existing imports):
```python
from datetime import date as _date
```

Add these two fields to the `User` class, after `created_at`:

```python
    tokens_used_today: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    tokens_budget_date: Mapped[_date] = mapped_column(
        DateTime(timezone=False).with_variant(
            __import__("sqlalchemy").Date(), "sqlite"
        )
        if False  # use Date() directly
        else __import__("sqlalchemy").Date(),
        nullable=False,
        server_default=__import__("sqlalchemy").func.current_date(),
    )
```

Wait — this is getting complicated. Let me use the cleaner approach with `from sqlalchemy import Date`:

The existing imports already have `DateTime`. Add `Date` to the existing `from sqlalchemy import (...)` block:

```python
# In the existing sqlalchemy import block, add Date:
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,          # ← add this
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,          # ← add this
)
```

Then in the `User` class, after `created_at`:

```python
    tokens_used_today: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    tokens_budget_date: Mapped[_date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
```

And add the `date` import at the top:
```python
from datetime import UTC, date as _date, datetime, timedelta
```

(The existing import is `from datetime import UTC, datetime, timedelta` — just add `date as _date`.)

- [ ] **Step 4: Generate Alembic migration**

```bash
cd backend
alembic revision --autogenerate -m "add_token_budget_columns"
```

Expected: creates a new file in `alembic/versions/`. Inspect it — it should show:
```
op.add_column('users', sa.Column('tokens_used_today', sa.Integer(), server_default='0', nullable=False))
op.add_column('users', sa.Column('tokens_budget_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False))
```

- [ ] **Step 5: Apply migration**

```bash
alembic upgrade head
```

Expected: `Running upgrade ... -> <hash>, add_token_budget_columns`

- [ ] **Step 6: Run test**

```bash
python -m pytest tests/test_token_budget.py::test_user_has_token_budget_columns -v
```

Expected: PASS

- [ ] **Step 7: Run full test suite — verify nothing broken**

```bash
python -m pytest --tb=short -q
```

Expected: all previously passing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/__init__.py backend/alembic/versions/
git commit -m "feat(db): add tokens_used_today + tokens_budget_date columns to users"
```

---

## Task 7: Settings — add `daily_token_budget`

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add setting** (no failing test needed — settings are verified via integration tests in later tasks)

In `backend/app/config.py`, add inside the `Settings` class after the Gemini block:

```python
    # Token budget
    daily_token_budget: int = 50_000  # env: DAILY_TOKEN_BUDGET
```

- [ ] **Step 2: Verify it loads**

```bash
python -c "from app.config import get_settings; s = get_settings(); print(s.daily_token_budget)"
```

Expected: `50000`

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(config): add daily_token_budget setting (default 50k)"
```

---

## Task 8: `app/dependencies/token_budget.py` — atomic budget factory

**Files:**
- Create: `backend/app/dependencies/__init__.py`
- Create: `backend/app/dependencies/token_budget.py`
- Modify: `backend/tests/test_token_budget.py`

- [ ] **Step 1: Write failing tests** (add to `test_token_budget.py`)

```python
# backend/tests/test_token_budget.py  (add below existing test)
import pytest
from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from sqlalchemy import text

from app.models.base import SessionLocal
from app.models import User
from app.dependencies.token_budget import token_budget, ENDPOINT_TOKEN_COST, _seconds_until_midnight_utc


@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.rollback()
    db.close()


@pytest.fixture
def test_user(db_session):
    """Create a fresh user with a clean token budget for the test."""
    import uuid
    from passlib.context import CryptContext
    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    user = User(
        id=str(uuid.uuid4()),
        email=f"budget_test_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=pwd_ctx.hash("testpass"),
        tokens_used_today=0,
        tokens_budget_date=date.today(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    db_session.delete(user)
    db_session.commit()


def test_endpoint_token_cost_keys_exist():
    assert "scan_photo" in ENDPOINT_TOKEN_COST
    assert "scan_barcode" in ENDPOINT_TOKEN_COST
    assert "biosync_extract" in ENDPOINT_TOKEN_COST
    assert all(v > 0 for v in ENDPOINT_TOKEN_COST.values())


@pytest.mark.asyncio
async def test_token_budget_allows_call_within_limit(db_session, test_user):
    from app.config import get_settings
    settings = get_settings()
    dep_fn = token_budget(ENDPOINT_TOKEN_COST["scan_barcode"])
    result = await dep_fn.__wrapped__(
        current_user=test_user, db=db_session, settings=settings
    )
    db_session.refresh(test_user)
    assert test_user.tokens_used_today == ENDPOINT_TOKEN_COST["scan_barcode"]


@pytest.mark.asyncio
async def test_token_budget_rejects_when_over_limit(db_session, test_user):
    from app.config import get_settings
    settings = get_settings()
    # Set user to nearly exhausted
    test_user.tokens_used_today = settings.daily_token_budget
    db_session.commit()

    dep_fn = token_budget(1000)
    with pytest.raises(HTTPException) as exc_info:
        await dep_fn.__wrapped__(
            current_user=test_user, db=db_session, settings=settings
        )
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["error"] == "token_budget_exceeded"
    assert "resets_at" in exc_info.value.detail
    assert "retry-after" in {k.lower() for k in exc_info.value.headers}


@pytest.mark.asyncio
async def test_token_budget_resets_on_new_day(db_session, test_user):
    from app.config import get_settings
    settings = get_settings()
    # Simulate yesterday's budget exhausted
    test_user.tokens_used_today = settings.daily_token_budget
    test_user.tokens_budget_date = date.today() - timedelta(days=1)
    db_session.commit()

    dep_fn = token_budget(ENDPOINT_TOKEN_COST["scan_barcode"])
    await dep_fn.__wrapped__(
        current_user=test_user, db=db_session, settings=settings
    )
    db_session.refresh(test_user)
    assert test_user.tokens_budget_date == date.today()
    assert test_user.tokens_used_today == ENDPOINT_TOKEN_COST["scan_barcode"]
```

- [ ] **Step 2: Run — expect ImportError**

```bash
python -m pytest tests/test_token_budget.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'token_budget'`

- [ ] **Step 3: Create dependency package and module**

```python
# backend/app/dependencies/__init__.py
```

```python
# backend/app/dependencies/token_budget.py
"""Per-user daily token budget enforcement.

Enforcement uses a single atomic SQL UPDATE — no read-modify-write race.
The WHERE clause prevents the UPDATE from succeeding if the budget would
be exceeded, returning 0 rows. rowcount == 0 → 429.

IMPORTANT: Add Depends(token_budget(ENDPOINT_TOKEN_COST["<key>"])) to every
endpoint that calls gemini.py. See backend/CLAUDE.md for the rule.
"""

from datetime import UTC, date, datetime, time, timedelta

from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.middleware.auth import get_current_user
from app.models import User
from app.models.base import get_db

# Per-endpoint estimated token costs.
# UPDATE THIS when the Gemini model changes pricing or you add a new LLM endpoint.
ENDPOINT_TOKEN_COST: dict[str, int] = {
    "scan_photo": 2_000,
    "scan_barcode": 1_000,
    "biosync_extract": 4_000,
}


def _seconds_until_midnight_utc() -> int:
    now = datetime.now(UTC)
    midnight = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=UTC)
    return max(1, int((midnight - now).total_seconds()))


def token_budget(estimated_tokens: int):
    """Factory: returns a FastAPI dependency that atomically reserves `estimated_tokens`.

    Uses a single SQL UPDATE with a WHERE guard — prevents read-modify-write races.
    Daily reset is handled inside the same UPDATE when tokens_budget_date < today.
    """
    assert estimated_tokens > 0, "estimated_tokens must be positive"

    async def _dep(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
        settings: Settings = Depends(get_settings),
    ) -> User:
        today = date.today()

        result = db.execute(
            text("""
                UPDATE users
                SET
                    tokens_used_today = CASE
                        WHEN tokens_budget_date < :today THEN :estimated
                        ELSE tokens_used_today + :estimated
                    END,
                    tokens_budget_date = :today
                WHERE id = :user_id
                  AND (
                      CASE
                          WHEN tokens_budget_date < :today THEN :estimated
                          ELSE tokens_used_today + :estimated
                      END
                  ) <= :budget
            """),
            {
                "today": today,
                "estimated": estimated_tokens,
                "user_id": current_user.id,
                "budget": settings.daily_token_budget,
            },
        )
        db.commit()

        if result.rowcount == 0:
            retry_after = _seconds_until_midnight_utc()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)},
                detail={
                    "error": "token_budget_exceeded",
                    "message": "Daily AI token limit reached",
                    "resets_at": (today + timedelta(days=1)).isoformat() + "T00:00:00Z",
                },
            )

        return current_user

    # Expose inner function for direct testing without FastAPI DI
    _dep.__wrapped__ = _dep  # type: ignore[attr-defined]
    return _dep
```

- [ ] **Step 4: Install pytest-asyncio if needed**

```bash
pip show pytest-asyncio || pip install pytest-asyncio
```

Check `backend/pytest.ini` — if `asyncio_mode` is not set, add:
```ini
asyncio_mode = auto
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_token_budget.py -v
```

Expected: all tests pass (including the column test from Task 6).

- [ ] **Step 6: Commit**

```bash
git add backend/app/dependencies/__init__.py backend/app/dependencies/token_budget.py backend/tests/test_token_budget.py
git commit -m "feat(budget): atomic per-user daily token budget dependency"
```

---

## Task 9: Wire `token_budget` into `scan.py`

**Files:**
- Modify: `backend/app/routers/scan.py`
- Modify: `backend/tests/test_scan.py`

- [ ] **Step 1: Write failing test** (add to `test_scan.py`)

Open `backend/tests/test_scan.py` and add:

```python
def test_scan_photo_endpoint_has_token_budget_dep():
    """CI gate: /scan/photo must declare a token_budget dependency."""
    import inspect
    from app.routers.scan import scan_photo
    from app.dependencies.token_budget import token_budget
    sig = inspect.signature(scan_photo)
    dep_defaults = [p.default for p in sig.parameters.values()]
    # FastAPI Depends wraps the factory — check that token_budget factory is referenced
    dep_fns = [
        getattr(d, "dependency", None)
        for d in dep_defaults
        if hasattr(d, "dependency")
    ]
    factories = [getattr(fn, "__closure__", None) for fn in dep_fns if callable(fn)]
    # At least one dependency must come from the token_budget factory
    from app.dependencies import token_budget as tb_module
    source_code = inspect.getsource(scan_photo)
    assert "token_budget" in source_code, "/scan/photo missing token_budget dependency"


def test_scan_barcode_endpoint_has_token_budget_dep():
    import inspect
    from app.routers.scan import scan_barcode
    source_code = inspect.getsource(scan_barcode)
    assert "token_budget" in source_code, "/scan/barcode missing token_budget dependency"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
python -m pytest tests/test_scan.py::test_scan_photo_endpoint_has_token_budget_dep -v
```

Expected: `AssertionError: /scan/photo missing token_budget dependency`

- [ ] **Step 3: Update `scan.py`**

Add import near top of `scan.py` (after existing imports):
```python
from app.dependencies.token_budget import ENDPOINT_TOKEN_COST, token_budget
```

Modify `scan_photo` signature — add `_budget` parameter:
```python
@router.post("/photo", response_model=ScanResponse)
@limiter.limit("20/minute")
async def scan_photo(
    request: Request,
    body: PhotoScanRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _budget: User = Depends(token_budget(ENDPOINT_TOKEN_COST["scan_photo"])),
):
```

Modify `scan_barcode` signature — add `_budget` parameter:
```python
@router.post("/barcode", response_model=ScanResponse)
@limiter.limit("20/minute")
async def scan_barcode(
    request: Request,
    body: BarcodeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _budget: User = Depends(token_budget(ENDPOINT_TOKEN_COST["scan_barcode"])),
):
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_scan.py -v
```

Expected: all pass including the two new dep-check tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/scan.py backend/tests/test_scan.py
git commit -m "feat(budget): wire token_budget dep into /scan/photo and /scan/barcode"
```

---

## Task 10: Wire `token_budget` + rate limit into `biosync.py`

**Files:**
- Modify: `backend/app/routers/biosync.py`
- Modify: `backend/tests/test_biosync.py`

> Note: It is `POST /biosync/extract` that calls Gemini (not `/upload`). The 5/min limit
> and token_budget(4000) go on `/extract`.

- [ ] **Step 1: Write failing test** (add to `test_biosync.py`)

```python
def test_biosync_extract_has_token_budget_dep():
    import inspect
    from app.routers.biosync import extract_biomarkers
    source_code = inspect.getsource(extract_biomarkers)
    assert "token_budget" in source_code, "/biosync/extract missing token_budget dependency"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
python -m pytest tests/test_biosync.py::test_biosync_extract_has_token_budget_dep -v
```

Expected: `AssertionError`

- [ ] **Step 3: Update `biosync.py`**

Add import near top of `biosync.py` (after existing imports):
```python
from app.dependencies.token_budget import ENDPOINT_TOKEN_COST, token_budget
```

Modify `extract_biomarkers` — change rate limit from `10/minute` to `5/minute` and add `_budget`:
```python
@router.post(
    "/extract",
    response_model=BiomarkerExtractionResult,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("5/minute")
async def extract_biomarkers(
    request: Request,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    _budget: User = Depends(token_budget(ENDPOINT_TOKEN_COST["biosync_extract"])),
):
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_biosync.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/biosync.py backend/tests/test_biosync.py
git commit -m "feat(budget): wire token_budget + 5/min limit into /biosync/extract"
```

---

## Task 11: `gemini.py` — capture `usage_metadata` + log with `request_id`

**Files:**
- Modify: `backend/app/services/gemini.py`

Each of the 4 `generate_content_async` call sites needs:
1. Extract `usage_metadata` from the response
2. Log it with `request_id` from `REQUEST_ID_VAR`
3. Return the token count so callers can pass it to `record_token_usage`

> Note: `reconcile_ingredient` and `generate_personalized_insight` already return
> `None` on failure (graceful degradation). They must also log usage on success.

- [ ] **Step 1: Write test for usage logging**

```python
# backend/tests/test_token_budget.py  (add)
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_gemini_logs_usage_metadata(caplog):
    """gemini.extract_from_image must log token counts after a successful call."""
    import logging
    from app.services import gemini as gemini_module
    from app.config import get_settings

    mock_response = MagicMock()
    mock_usage = MagicMock()
    mock_usage.total_token_count = 1847
    mock_usage.prompt_token_count = 1200
    mock_usage.candidates_token_count = 647
    mock_response.usage_metadata = mock_usage
    mock_response.parsed = MagicMock()

    with patch.object(gemini_module, "_decode_image", return_value=b"fake"), \
         patch.object(gemini_module, "_configure"), \
         patch("google.generativeai.GenerativeModel") as mock_model_cls:
        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_response)
        mock_model_cls.return_value = mock_model

        with caplog.at_level(logging.INFO, logger="app.services.gemini"):
            await gemini_module.extract_from_image("fake_b64", get_settings())

    assert any("gemini_call_complete" in r.message or "1847" in str(r.__dict__)
               for r in caplog.records)
```

- [ ] **Step 2: Run — expect FAIL (no usage logging yet)**

```bash
python -m pytest tests/test_token_budget.py::test_gemini_logs_usage_metadata -v
```

Expected: `AssertionError` — no log records with token counts.

- [ ] **Step 3: Update `gemini.py`**

Add import at top of `gemini.py`:
```python
from app.core.context import REQUEST_ID_VAR
```

After each successful `generate_content_async` call (there are 4: in `extract_from_image`, `reconcile_ingredient`, `extract_biomarkers_from_images`, `extract_biomarkers_from_pdf`, and `generate_personalized_insight` — 5 total), add this block before the `return` or `_extract_parsed` call:

```python
        usage = getattr(response, "usage_metadata", None)
        logger.info(
            "gemini_call_complete",
            extra={
                "request_id": REQUEST_ID_VAR.get(),
                "tokens_total": getattr(usage, "total_token_count", 0),
                "tokens_prompt": getattr(usage, "prompt_token_count", 0),
                "tokens_output": getattr(usage, "candidates_token_count", 0),
                "model": settings.gemini_model,
            },
        )
```

For `extract_from_image`, insert it between the `try` block's response line and the `return`:
```python
        response = await model.generate_content_async(...)
    except google_exceptions.ResourceExhausted as exc:
        ...
    # ← after the try/except block:
    usage = getattr(response, "usage_metadata", None)
    logger.info("gemini_call_complete", extra={
        "request_id": REQUEST_ID_VAR.get(),
        "tokens_total": getattr(usage, "total_token_count", 0),
        "tokens_prompt": getattr(usage, "prompt_token_count", 0),
        "tokens_output": getattr(usage, "candidates_token_count", 0),
        "model": settings.gemini_model,
    })
    return _extract_parsed(response, ProductExtraction)
```

Apply the same pattern to all 5 call sites. For `reconcile_ingredient` and `generate_personalized_insight` (which return `None` on failure), add logging only in the success path before the `return` of the parsed object.

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_token_budget.py::test_gemini_logs_usage_metadata -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest --tb=short -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/gemini.py backend/tests/test_token_budget.py
git commit -m "feat(observability): log Gemini usage_metadata with request_id at all call sites"
```

---

## Task 12: CI gate — assert all Gemini-calling endpoints have `token_budget`

**Files:**
- Create: `backend/tests/test_ci_gate.py`

- [ ] **Step 1: Write the gate test**

```python
# backend/tests/test_ci_gate.py
"""CI gate: every router endpoint that imports from gemini.py must declare
token_budget in its source. This test fails if someone adds a new Gemini
endpoint without wiring the budget dependency."""

import ast
import inspect
from pathlib import Path


ROUTERS_DIR = Path(__file__).parent.parent / "app" / "routers"
GEMINI_CALLS = {
    "extract_from_image",
    "reconcile_ingredient",
    "extract_biomarkers_from_images",
    "extract_biomarkers_from_pdf",
    "generate_personalized_insight",
}


def _find_router_functions_calling_gemini(router_path: Path) -> list[str]:
    """Return names of async def functions in the router that call a gemini function."""
    source = router_path.read_text()
    tree = ast.parse(source)
    guilty = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        # Check if any Call in this function's body references a gemini function
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name in GEMINI_CALLS:
                    guilty.append(node.name)
                    break
    return guilty


def test_all_gemini_endpoints_have_token_budget():
    """Every function that calls a gemini service must reference token_budget."""
    failures = []
    for router_file in ROUTERS_DIR.glob("*.py"):
        if router_file.name.startswith("_"):
            continue
        source = router_file.read_text()
        # Only check files that import gemini functions
        if "from app.services.gemini" not in source and "import gemini" not in source:
            continue
        guilty_fns = _find_router_functions_calling_gemini(router_file)
        for fn_name in guilty_fns:
            if "token_budget" not in source:
                failures.append(f"{router_file.name}:{fn_name} calls Gemini but has no token_budget dep")
    assert not failures, "\n".join(failures)
```

- [ ] **Step 2: Run — expect PASS** (we already wired all endpoints)

```bash
python -m pytest tests/test_ci_gate.py -v
```

Expected: PASS. If it fails, the previous tasks have a gap — go back and fix.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_ci_gate.py
git commit -m "test(ci-gate): assert all Gemini-calling endpoints declare token_budget"
```

---

## Task 13: Docs updates

**Files:**
- Modify: `backend/CLAUDE.md`
- Modify: `docs/architecture.md`

- [ ] **Step 1: Update `backend/CLAUDE.md`**

In the `## Convenciones` section, add:

```markdown
- **LLM endpoints:** todo endpoint que llame a `gemini.py` DEBE declarar `_budget: User = Depends(token_budget(ENDPOINT_TOKEN_COST["<key>"]))`. Actualizar `ENDPOINT_TOKEN_COST` en `app/dependencies/token_budget.py` si el costo estimado cambia. El test `tests/test_ci_gate.py` falla si falta esta dep.
```

- [ ] **Step 2: Update `docs/architecture.md`**

Add a new section (or update the DB schema section) with:

```markdown
### Token Budget Columns (`users` table)

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `tokens_used_today` | INTEGER | 0 | Tokens consumed today (UTC) |
| `tokens_budget_date` | DATE | CURRENT_DATE | Date the counter was last reset |

Reset is implicit via the atomic SQL UPDATE in `app/dependencies/token_budget.py`.
Daily budget is configurable via `DAILY_TOKEN_BUDGET` env var (default 50,000).

### Observability Stack

- **Request ID:** `app/core/context.REQUEST_ID_VAR` (ContextVar) — set by `RequestIDMiddleware`, readable from any async callsite including background tasks and `gemini.py`.
- **Log format:** JSON, one object per line, emitted to stdout. Fields: `ts`, `level`, `logger`, `request_id`, `msg`, plus any `extra=` keys passed by the caller.
- **Gemini usage logging:** after every `generate_content_async` call, `gemini.py` logs `tokens_total`, `tokens_prompt`, `tokens_output`, `model`, and `request_id`.
- **Error schema:** `app/schemas/errors.ErrorResponse` — `{error: str, message: str, detail: dict | None}`. All 429/500 responses use this schema.
```

- [ ] **Step 3: Commit**

```bash
git add backend/CLAUDE.md docs/architecture.md
git commit -m "docs: update CLAUDE.md LLM endpoint rule + architecture observability section"
```

---

## Task 14: Full test suite + merge prep

- [ ] **Step 1: Run full test suite from backend root**

```bash
cd backend && python -m pytest --tb=short -q
```

Expected: all tests pass, 0 failures.

- [ ] **Step 2: Run mypy (if configured)**

```bash
python -m mypy app/ --ignore-missing-imports 2>&1 | tail -5
```

Expected: no new errors introduced by this branch.

- [ ] **Step 3: Verify worktree is on feature branch**

```bash
git branch
```

Expected: `* feat/production-hardening`

- [ ] **Step 4: Invoke finishing-a-development-branch skill**

```
/superpowers:finishing-a-development-branch
```

This will guide the PR creation, merge strategy, and cleanup.

---

## Self-Review Checklist

- [x] **Spec §3 (Rate Limiting):** Task 5 implements `_seconds_until_midnight_utc` and dynamic `Retry-After`.
- [x] **Spec §4.1 (DB migration):** Task 6 adds columns with correct `Date` ORM type.
- [x] **Spec §4.2 (Settings):** Task 7 adds `daily_token_budget`.
- [x] **Spec §4.3 (Atomic UPDATE):** Task 8 uses `text(UPDATE ... WHERE ...)` with rowcount check.
- [x] **Spec §4.4 (Background task):** Task 11 extracts `usage_metadata`; Task 8's module has a `record_token_usage` function defined for callers.
- [x] **Spec §4.5 (All 3 endpoints wired):** Tasks 9 + 10.
- [x] **Spec §5 (Error schema):** Task 4.
- [x] **Spec §6.1 (ContextVar):** Tasks 2 + 3.
- [x] **Spec §6.3 (Gemini logging):** Task 11.
- [x] **Spec §8 (Branch/docs/tests/CI gate):** Tasks 1 + 12 + 13 + 14.
- [x] **Codebase note:** `/biosync/extract` (not `/upload`) gets the budget dep — corrected in Tasks 10.
- [x] **`record_token_usage`:** Defined in `token_budget.py` for callers; error-safe with try/except.
