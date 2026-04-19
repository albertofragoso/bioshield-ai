"""Tests for /auth endpoints: register, login, refresh, logout, and protected routes."""

from datetime import UTC, datetime, timedelta

from jose import jwt

from tests.conftest import TEST_SETTINGS

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

REGISTER_URL = "/auth/register"
LOGIN_URL = "/auth/login"
REFRESH_URL = "/auth/refresh"
LOGOUT_URL = "/auth/logout"
PROTECTED_URL = "/scan/ping"

VALID_EMAIL = "test@bioshield.ai"
VALID_PASSWORD = "securepassword123"


def _make_expired_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": datetime.now(UTC) - timedelta(hours=2),
        "exp": datetime.now(UTC) - timedelta(hours=1),
    }
    return jwt.encode(payload, TEST_SETTINGS.jwt_secret, algorithm=TEST_SETTINGS.jwt_algorithm)


# ─────────────────────────────────────────────
# POST /auth/register
# ─────────────────────────────────────────────

async def test_register_success(client):
    response = await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == VALID_EMAIL
    assert "id" in body
    assert "password_hash" not in body
    # Auth cookies must be set
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


async def test_register_duplicate_email(client):
    payload = {"email": "dup@bioshield.ai", "password": VALID_PASSWORD}
    await client.post(REGISTER_URL, json=payload)
    response = await client.post(REGISTER_URL, json=payload)
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


async def test_register_short_password(client):
    response = await client.post(REGISTER_URL, json={"email": "short@bioshield.ai", "password": "abc"})
    assert response.status_code == 422


async def test_register_invalid_email(client):
    response = await client.post(REGISTER_URL, json={"email": "not-an-email", "password": VALID_PASSWORD})
    assert response.status_code == 422


# ─────────────────────────────────────────────
# POST /auth/login
# ─────────────────────────────────────────────

async def test_login_success(client):
    await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    response = await client.post(LOGIN_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


async def test_login_wrong_password(client):
    await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    response = await client.post(LOGIN_URL, json={"email": VALID_EMAIL, "password": "wrongpassword"})
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


async def test_login_unknown_email(client):
    response = await client.post(LOGIN_URL, json={"email": "ghost@bioshield.ai", "password": VALID_PASSWORD})
    assert response.status_code == 401


# ─────────────────────────────────────────────
# Protected route access
# ─────────────────────────────────────────────

async def test_protected_route_without_token(client):
    response = await client.get(PROTECTED_URL)
    assert response.status_code == 401


async def test_protected_route_with_valid_token(client):
    await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    await client.post(LOGIN_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    # Cookie is now set in the client jar
    response = await client.get(PROTECTED_URL)
    assert response.status_code == 200
    assert response.json()["user_id"] is not None


async def test_protected_route_with_expired_token(client):
    # Register to get a real user_id in the DB
    reg = await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    user_id = reg.json()["id"]
    expired_token = _make_expired_access_token(user_id)
    response = await client.get(PROTECTED_URL, cookies={"access_token": expired_token})
    assert response.status_code == 401


async def test_protected_route_with_tampered_token(client):
    tampered = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJoYWNrZXIifQ.invalidsignature"
    response = await client.get(PROTECTED_URL, cookies={"access_token": tampered})
    assert response.status_code == 401


async def test_protected_route_with_refresh_token_rejected(client):
    """Refresh tokens must not be accepted on access-protected routes."""
    reg = await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    user_id = reg.json()["id"]
    # Build a valid refresh token and try to use it as access token
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(days=7),
    }
    refresh_token = jwt.encode(payload, TEST_SETTINGS.jwt_secret, algorithm=TEST_SETTINGS.jwt_algorithm)
    response = await client.get(PROTECTED_URL, cookies={"access_token": refresh_token})
    assert response.status_code == 401


# ─────────────────────────────────────────────
# POST /auth/refresh
# ─────────────────────────────────────────────

async def test_refresh_issues_new_token_pair(client):
    await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    await client.post(LOGIN_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})

    response = await client.post(REFRESH_URL)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    # New token is valid — can access protected route
    assert "access_token" in response.cookies
    protected = await client.get(PROTECTED_URL)
    assert protected.status_code == 200


async def test_refresh_without_cookie_returns_401(client):
    response = await client.post(REFRESH_URL)
    assert response.status_code == 401


async def test_refresh_with_access_token_as_refresh_rejected(client):
    """An access token must be rejected when used as a refresh token."""
    reg = await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    user_id = reg.json()["id"]
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=30),
    }
    access_as_refresh = jwt.encode(payload, TEST_SETTINGS.jwt_secret, algorithm=TEST_SETTINGS.jwt_algorithm)
    response = await client.post(REFRESH_URL, cookies={"refresh_token": access_as_refresh})
    assert response.status_code == 401


# ─────────────────────────────────────────────
# POST /auth/logout
# ─────────────────────────────────────────────

async def test_logout_clears_cookies(client):
    await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    await client.post(LOGIN_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})

    response = await client.post(LOGOUT_URL)
    assert response.status_code == 204
    # After logout, protected route must return 401
    response = await client.get(PROTECTED_URL)
    assert response.status_code == 401
