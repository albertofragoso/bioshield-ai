"""S7 — Log formatter redaction tests (L3)."""
import logging


def _format_record(logger_name: str, msg: str, extra: dict | None = None) -> dict:
    import json

    from app.middleware.logging import JsonFormatter

    record = logging.LogRecord(
        name=logger_name,
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=msg,
        args=(),
        exc_info=None,
    )
    if extra:
        for k, v in extra.items():
            setattr(record, k, v)
    payload = json.loads(JsonFormatter().format(record))
    return payload


def test_safe_keys_pass_through():
    payload = _format_record("app", "req", extra={"method": "GET", "path": "/health"})
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"


def test_token_count_keys_pass_through():
    """tokens_total / tokens_prompt are legitimate cost-logging fields — not redacted."""
    payload = _format_record(
        "app", "call", extra={"tokens_total": 1000, "tokens_prompt": 500}
    )
    assert payload["tokens_total"] == 1000
    assert payload["tokens_prompt"] == 500


def test_sensitive_exact_password_redacted():
    payload = _format_record("app", "oops", extra={"password": "hunter2"})
    assert payload["password"] == "[REDACTED]"


def test_sensitive_exact_secret_redacted():
    payload = _format_record("app", "oops", extra={"secret": "abc"})
    assert payload["secret"] == "[REDACTED]"


def test_sensitive_suffix_key_redacted():
    payload = _format_record("app", "oops", extra={"jwt_key": "xyz", "aes_key": "abc"})
    assert payload["jwt_key"] == "[REDACTED]"
    assert payload["aes_key"] == "[REDACTED]"


def test_sensitive_suffix_token_redacted():
    payload = _format_record("app", "oops", extra={"access_token": "tok123"})
    assert payload["access_token"] == "[REDACTED]"


def test_sensitive_suffix_password_redacted():
    payload = _format_record("app", "oops", extra={"user_password": "secret"})
    assert payload["user_password"] == "[REDACTED]"
