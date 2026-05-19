# backend/tests/test_token_budget.py
import uuid
from datetime import date, timedelta

import bcrypt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies.token_budget import ENDPOINT_TOKEN_COST, token_budget
from app.models import User
from app.models.base import SessionLocal


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def test_user_has_token_budget_columns():
    """After migration, users table must have the two new columns."""
    engine = create_engine(
        "sqlite:///./bioshield.db",
        connect_args={"check_same_thread": False},
    )
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("users")}
    assert "tokens_used_today" in cols
    assert "tokens_budget_date" in cols
    engine.dispose()


@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.rollback()
    db.close()


@pytest.fixture
def test_user(db_session: Session):
    user = User(
        id=str(uuid.uuid4()),
        email=f"budget_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=_hash_password("testpass"),
        tokens_used_today=0,
        tokens_budget_date=date.today(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    db_session.delete(user)
    db_session.commit()


def test_endpoint_token_cost_keys_exist():
    assert "scan_photo" in ENDPOINT_TOKEN_COST
    assert "scan_barcode" in ENDPOINT_TOKEN_COST
    assert "biosync_extract" in ENDPOINT_TOKEN_COST
    assert all(v > 0 for v in ENDPOINT_TOKEN_COST.values())


@pytest.mark.asyncio
async def test_token_budget_allows_call_within_limit(db_session: Session, test_user: User):
    settings = get_settings()
    dep_fn = token_budget(ENDPOINT_TOKEN_COST["scan_barcode"])
    # Call the inner async function directly (bypass FastAPI DI)
    await dep_fn(current_user=test_user, db=db_session, settings=settings)
    db_session.refresh(test_user)
    assert test_user.tokens_used_today == ENDPOINT_TOKEN_COST["scan_barcode"]


@pytest.mark.asyncio
async def test_token_budget_rejects_when_over_limit(db_session: Session, test_user: User):
    settings = get_settings()
    test_user.tokens_used_today = settings.daily_token_budget
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await token_budget(1000)(current_user=test_user, db=db_session, settings=settings)

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["error"] == "token_budget_exceeded"
    assert "resets_at" in exc_info.value.detail
    assert "Retry-After" in exc_info.value.headers


@pytest.mark.asyncio
async def test_token_budget_resets_on_new_day(db_session: Session, test_user: User):
    settings = get_settings()
    test_user.tokens_used_today = settings.daily_token_budget
    test_user.tokens_budget_date = date.today() - timedelta(days=1)
    db_session.commit()

    await token_budget(ENDPOINT_TOKEN_COST["scan_barcode"])(
        current_user=test_user, db=db_session, settings=settings
    )
    db_session.refresh(test_user)
    assert test_user.tokens_budget_date == date.today()
    assert test_user.tokens_used_today == ENDPOINT_TOKEN_COST["scan_barcode"]
