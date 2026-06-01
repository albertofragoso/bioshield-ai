"""Tests for config validation — C1 (Turnstile captcha fails open).

RED phase: test_turnstile_dev_key_rejected_in_prod should FAIL before fix.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_turnstile_dev_key_rejected_in_prod():
    """Settings rejects turnstile_secret_key='dev' when debug=False."""
    with pytest.raises((ValueError, ValidationError)):
        Settings(
            debug=False,
            turnstile_secret_key="dev",
            jwt_secret="prod-secret-long-enough-for-jwt",
            aes_key="prod-aes-key-32-bytes-xxxxxxxxxxx",
        )


def test_turnstile_dev_key_allowed_in_debug():
    """Settings allows turnstile_secret_key='dev' when debug=True."""
    settings = Settings(
        debug=True,
        turnstile_secret_key="dev",
        jwt_secret="test-jwt-secret-not-for-production",
        aes_key="test-aes-key-32-bytes-xxxxxxxxxx",
    )
    assert settings.turnstile_secret_key == "dev"
