"""Password hashing and JWT utilities for BioShield auth."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from app.models import RefreshToken

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select, update
from sqlalchemy.orm import Session

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
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "type": token_type,
        "jti": str(uuid4()),  # guarantees uniqueness even within the same second
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


# ─────────────────────────────────────────────
# Refresh token DB management
# ─────────────────────────────────────────────


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def store_refresh_token(
    db: Session,
    user_id: str,
    token: str,
    family_id: str,
    settings: Settings,
) -> "RefreshToken":
    from app.models import RefreshToken

    expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    record = RefreshToken(
        user_id=user_id,
        token_hash=hash_token(token),
        family_id=family_id,
        is_revoked=False,
        expires_at=expires_at,
    )
    db.add(record)
    return record


def validate_and_rotate_refresh_token(
    db: Session,
    token: str,
    settings: Settings,
) -> tuple[str, str, str]:
    """Validate a refresh token, detect reuse, and rotate.

    Returns (user_id, new_access_token, new_refresh_token).
    Raises HTTPException 401 on any failure.
    On reuse detection, revokes the entire token family before raising.
    """
    from app.models import RefreshToken

    _creds_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )

    try:
        user_id = decode_refresh_token(token, settings)
    except JWTError:
        raise _creds_error

    token_hash = hash_token(token)
    record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    if record is None:
        raise _creds_error

    if record.is_revoked:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == record.family_id)
            .values(is_revoked=True)
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token reuse detected. All sessions have been invalidated.",
        )

    if record.user_id != user_id:
        raise _creds_error

    record.is_revoked = True

    new_access = create_access_token(user_id, settings)
    new_refresh = create_refresh_token(user_id, settings)
    store_refresh_token(db, user_id, new_refresh, record.family_id, settings)

    db.commit()
    return user_id, new_access, new_refresh


def revoke_user_token(db: Session, token: str) -> None:
    from app.models import RefreshToken

    db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(token))
        .values(is_revoked=True)
    )
    db.commit()


def revoke_all_user_tokens(db: Session, user_id: str) -> None:
    from app.models import RefreshToken

    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, ~RefreshToken.is_revoked)
        .values(is_revoked=True)
    )
    db.commit()
