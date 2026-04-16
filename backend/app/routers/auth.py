from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.middleware.rate_limit import limiter
from app.models import User
from app.models.base import get_db
from app.schemas.models import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)

router = APIRouter()

_ACCESS_COOKIE = "access_token"
_REFRESH_COOKIE = "refresh_token"


def _set_auth_cookies(response: Response, access: str, refresh: str, settings: Settings) -> None:
    secure = not settings.debug
    response.set_cookie(
        key=_ACCESS_COOKIE,
        value=access,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.jwt_access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=refresh,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.jwt_refresh_token_expire_days * 86400,
        path="/auth/refresh",  # scope refresh cookie to refresh endpoint only
    )


# ─────────────────────────────────────────────
# POST /auth/register
# ─────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    existing = db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    access = create_access_token(user.id, settings)
    refresh = create_refresh_token(user.id, settings)
    _set_auth_cookies(response, access, refresh, settings)

    return UserResponse(id=user.id, email=user.email, created_at=user.created_at)


# ─────────────────────────────────────────────
# POST /auth/login
# ─────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access = create_access_token(user.id, settings)
    refresh = create_refresh_token(user.id, settings)
    _set_auth_cookies(response, access, refresh, settings)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


# ─────────────────────────────────────────────
# POST /auth/refresh
# ─────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
    )
    if not refresh_token:
        raise credentials_error

    try:
        user_id = decode_refresh_token(refresh_token, settings)
    except JWTError:
        raise credentials_error

    user = db.get(User, user_id)
    if not user:
        raise credentials_error

    # Token rotation: issue a new pair on every refresh
    new_access = create_access_token(user.id, settings)
    new_refresh = create_refresh_token(user.id, settings)
    _set_auth_cookies(response, new_access, new_refresh, settings)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


# ─────────────────────────────────────────────
# POST /auth/logout
# ─────────────────────────────────────────────

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie(_ACCESS_COOKIE)
    response.delete_cookie(_REFRESH_COOKIE, path="/auth/refresh")
