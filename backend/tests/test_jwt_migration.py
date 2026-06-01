"""TDD tests for python-jose → PyJWT migration (H4 security fix).

These tests verify that the decode_token function:
1. Raises on forged signatures (wrong key)
2. Raises on wrong algorithm
3. Raises on expired tokens

Run RED before migration, GREEN after.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.config import Settings
from app.services.auth import decode_token

# Use a settings instance with known values
TEST_SETTINGS = Settings(
    debug=True,
    database_url="sqlite:///:memory:",
    jwt_secret="test-secret-key-for-migration-tests",
    jwt_access_token_expire_minutes=30,
    jwt_refresh_token_expire_days=7,
    aes_key="test-aes-key-32-bytes-xxxxxxxxxx",
    gemini_api_key="test-key",
    chroma_persist_directory="",
    allowed_origins=["http://testserver"],
)

WRONG_KEY_SETTINGS = Settings(
    debug=True,
    database_url="sqlite:///:memory:",
    jwt_secret="completely-different-wrong-key-xyz",
    jwt_access_token_expire_minutes=30,
    jwt_refresh_token_expire_days=7,
    aes_key="test-aes-key-32-bytes-xxxxxxxxxx",
    gemini_api_key="test-key",
    chroma_persist_directory="",
    allowed_origins=["http://testserver"],
)


def _make_token(payload: dict, key: str, algorithm: str = "HS256") -> str:
    import jwt as _jwt

    return _jwt.encode(payload, key, algorithm=algorithm)


def _valid_payload() -> dict:
    now = datetime.now(UTC)
    return {
        "sub": "user-123",
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=30),
    }


def test_invalid_signature_returns_401():
    """Token signed with wrong key must raise, not return None."""
    token = _make_token(_valid_payload(), key="wrong-key-attacker-forged")
    with pytest.raises(Exception):
        decode_token(token, TEST_SETTINGS)


def test_wrong_algorithm_rejected():
    """Token signed with HS512 should be rejected when server expects HS256."""
    payload = _valid_payload()
    token = _make_token(payload, key=TEST_SETTINGS.jwt_secret, algorithm="HS512")
    with pytest.raises(Exception):
        decode_token(token, TEST_SETTINGS)


def test_expired_token_raises():
    """Expired token must raise, not silently pass."""
    payload = {
        "sub": "user-123",
        "type": "access",
        "iat": datetime.now(UTC) - timedelta(hours=2),
        "exp": datetime.now(UTC) - timedelta(hours=1),
    }
    token = _make_token(payload, key=TEST_SETTINGS.jwt_secret)
    with pytest.raises(Exception):
        decode_token(token, TEST_SETTINGS)


def test_valid_token_decodes():
    """Sanity: a properly signed, non-expired token must decode successfully."""
    payload = _valid_payload()
    token = _make_token(payload, key=TEST_SETTINGS.jwt_secret)
    result = decode_token(token, TEST_SETTINGS)
    assert result["sub"] == "user-123"
    assert result["type"] == "access"
