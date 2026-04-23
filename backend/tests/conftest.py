import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.main import app
from app.middleware.rate_limit import limiter
from app.models.base import Base, get_db

# ─────────────────────────────────────────────
# Test settings override
# ─────────────────────────────────────────────

TEST_SETTINGS = Settings(
    debug=True,
    database_url="sqlite:///:memory:",
    jwt_secret="test-jwt-secret-not-for-production",
    jwt_access_token_expire_minutes=30,
    jwt_refresh_token_expire_days=7,
    aes_key="test-aes-key-32-bytes-xxxxxxxxxx",
    gemini_api_key="test-key",
    chroma_persist_directory="",
    allowed_origins=["http://testserver"],
    # OFF contribution — sincrónico en tests para evitar flakiness con BackgroundTask
    off_contrib_sync_for_tests=True,
)


@pytest.fixture(scope="session", autouse=True)
def override_settings():
    """Replace Settings singleton with test-safe values for the entire session."""
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    yield
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture(scope="session", autouse=True)
def disable_rate_limiting():
    """Disable slowapi rate limiting so tests can call endpoints freely."""
    limiter.enabled = False
    yield
    limiter.enabled = True


# ─────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_engine():
    """In-memory SQLite engine with all tables created once per session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """Transactional DB session per test — rolls back after each test for isolation.

    Also overrides the FastAPI get_db dependency so HTTP requests through
    the test client hit the same in-memory database.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    app.dependency_overrides[get_db] = lambda: session

    yield session

    app.dependency_overrides.pop(get_db, None)
    session.close()
    transaction.rollback()
    connection.close()


# ─────────────────────────────────────────────
# HTTP client
# ─────────────────────────────────────────────

@pytest.fixture
async def client(db_session):
    """Async HTTP client wired directly to the FastAPI app (no network).

    Depends on db_session so the get_db override is active for every request.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
