# backend/tests/test_token_budget.py
from sqlalchemy import create_engine, inspect


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
