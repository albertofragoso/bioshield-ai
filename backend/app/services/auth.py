"""Password hashing and JWT utilities for BioShield auth."""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import Settings


# ─────────────────────────────────────────────
# Password
# ─────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ─────────────────────────────────────────────
# JWT
# ─────────────────────────────────────────────

def _create_token(
    user_id: str,
    token_type: str,
    expires_delta: timedelta,
    settings: Settings,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, settings: Settings) -> str:
    return _create_token(
        user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
        settings=settings,
    )


def create_refresh_token(user_id: str, settings: Settings) -> str:
    return _create_token(
        user_id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.jwt_refresh_token_expire_days),
        settings=settings,
    )


def decode_token(token: str, settings: Settings) -> dict:
    """Decode and validate a JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def decode_refresh_token(token: str, settings: Settings) -> str:
    """Validate a refresh token and return the user_id (sub). Raises JWTError on failure."""
    payload = decode_token(token, settings)
    if payload.get("type") != "refresh":
        raise JWTError("Not a refresh token")
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise JWTError("Missing sub claim")
    return user_id
