"""FastAPI dependency for JWT authentication via HTTP-only cookie."""

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import User
from app.models.base import get_db
from app.services.auth import decode_token

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Validate JWT from the access_token cookie and return the authenticated User.

    Raises 401 if the token is missing, invalid, or the user no longer exists.
    """
    if not access_token:
        raise _CREDENTIALS_ERROR

    try:
        payload = decode_token(access_token, settings)
    except JWTError:
        raise _CREDENTIALS_ERROR

    if payload.get("type") != "access":
        raise _CREDENTIALS_ERROR

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise _CREDENTIALS_ERROR

    user = db.get(User, user_id)
    if not user:
        raise _CREDENTIALS_ERROR

    return user
