import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.main import app

# ─────────────────────────────────────────────
# Test settings override
# ─────────────────────────────────────────────

TEST_SETTINGS = Settings(
    debug=True,
    database_url="sqlite:///:memory:",
    jwt_secret="test-jwt-secret-not-for-production",
    aes_key="test-aes-key-32-bytes-xxxxxxxxxxx",
    gemini_api_key="test-key",
    chroma_persist_directory="",
    allowed_origins=["http://testserver"],
)


@pytest.fixture(scope="session", autouse=True)
def override_settings():
    """Replace Settings singleton with test-safe values for the entire session."""
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    yield
    app.dependency_overrides.clear()


# ─────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_engine():
    """In-memory SQLite engine, shared across the test session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    # Tables will be created here once SQLAlchemy models are defined (task 1.1)
    # Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """Provide a transactional DB session that rolls back after each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ─────────────────────────────────────────────
# HTTP client
# ─────────────────────────────────────────────

@pytest.fixture
async def client():
    """Async HTTP client wired directly to the FastAPI app (no network)."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
