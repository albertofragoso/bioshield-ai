import pytest
from pydantic import ValidationError

from app.config import Settings


def test_dev_jwt_secret_rejected_in_production():
    with pytest.raises((ValidationError, ValueError)):
        Settings(
            debug=False,
            jwt_secret="dev-secret-change-in-production",
            aes_key="safe-aes-key-32-bytes-xxxxxxxxxxx",
            database_url="sqlite:///./test.db",
        )


def test_dev_aes_key_rejected_in_production():
    with pytest.raises((ValidationError, ValueError)):
        Settings(
            debug=False,
            jwt_secret="safe-jwt-secret-for-testing-only",
            aes_key="dev-aes-key-32-bytes-changethis!",
            database_url="sqlite:///./test.db",
        )


def test_both_safe_secrets_accepted_in_production():
    s = Settings(
        debug=False,
        jwt_secret="safe-jwt-secret-for-testing-only",
        aes_key="safe-aes-key-32-bytes-xxxxxxxxxxx",
        turnstile_secret_key="safe-turnstile-key-for-testing",
        database_url="sqlite:///./test.db",
    )
    assert s.debug is False
