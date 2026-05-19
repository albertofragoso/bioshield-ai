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
