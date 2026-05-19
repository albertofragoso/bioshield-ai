from contextvars import ContextVar

REQUEST_ID_VAR: ContextVar[str | None] = ContextVar("request_id", default=None)
