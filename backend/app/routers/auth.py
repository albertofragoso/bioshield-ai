from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
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
    hash_password,
    revoke_user_token,
    store_refresh_token,
    validate_and_rotate_refresh_token,
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
    db.flush()  # assigns user.id within the transaction without committing

    access = create_access_token(user.id, settings)
    refresh = create_refresh_token(user.id, settings)
    store_refresh_token(db, user.id, refresh, str(uuid4()), settings)

    db.commit()
    db.refresh(user)

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
    store_refresh_token(db, user.id, refresh, str(uuid4()), settings)
    db.commit()

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
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    _, new_access, new_refresh = validate_and_rotate_refresh_token(db, refresh_token, settings)
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
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
    db: Session = Depends(get_db),
):
    if refresh_token:
        revoke_user_token(db, refresh_token)
    response.delete_cookie(_ACCESS_COOKIE)
    response.delete_cookie(_REFRESH_COOKIE, path="/auth/refresh")
