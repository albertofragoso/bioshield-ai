import json
from unittest.mock import MagicMock

from slowapi.errors import RateLimitExceeded

from app.middleware.rate_limit import _seconds_until_midnight_utc, rate_limit_exceeded_handler
from app.schemas.errors import ErrorResponse


def test_error_response_minimal():
    schema = ErrorResponse(error="internal_error", message="test")
    assert schema.error == "internal_error"
    assert schema.detail is None


def test_error_response_with_detail():
    schema = ErrorResponse(
        error="token_budget_exceeded",
        message="Daily AI token limit reached",
        detail={"resets_at": "2026-05-20T00:00:00Z"},
    )
    assert schema.detail["resets_at"] == "2026-05-20T00:00:00Z"


def test_error_response_all_fields():
    schema = ErrorResponse(error="rate_limit_exceeded", message="slow down", detail=None)
    assert schema.error == "rate_limit_exceeded"
    assert schema.message == "slow down"


def test_seconds_until_midnight_utc_is_positive():
    secs = _seconds_until_midnight_utc()
    assert 0 < secs <= 86400


def test_rate_limit_429_has_correct_schema():
    mock_request = MagicMock()
    mock_exc = MagicMock(spec=RateLimitExceeded)
    mock_exc.detail = "20 per 1 minute"
    response = rate_limit_exceeded_handler(mock_request, mock_exc)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    body = json.loads(response.body)
    assert body["error"] == "rate_limit_exceeded"
    assert "message" in body
