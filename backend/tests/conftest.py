import os

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
    gemini_api_key=os.getenv("GEMINI_API_KEY", "test-key"),
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
# Mock graph SSE
# ─────────────────────────────────────────────


@pytest.fixture
def mock_graph(monkeypatch):
    """Mock de build_scan_graph que retorna un objeto con astream_events SSE completo mínimo."""
    from app.routers import scan as scan_router_module

    async def _stream(*args, **kwargs):
        yield {"event": "on_chain_start", "name": "LangGraph", "data": {}}
        yield {
            "event": "on_chain_end",
            "name": "identify_product",
            "data": {
                "output": {
                    "product_name": "TestProd",
                    "product_brand": "Brand",
                    "extracted_ingredients": ["Azúcar"],
                    "source": "barcode",
                }
            },
        }
        yield {
            "event": "on_chain_end",
            "name": "personalize",
            "data": {"output": {"personalized_insights": []}},
        }
        yield {
            "event": "on_chain_end",
            "name": "calculate_risk",
            "data": {
                "output": {
                    "semaphore": "GRAY",
                    "conflict_severity": None,
                    "resolved": [],
                }
            },
        }

    class _MockGraph:
        def astream_events(self, *args, **kwargs):
            return _stream(*args, **kwargs)

    monkeypatch.setattr(scan_router_module, "build_scan_graph", lambda db, settings: _MockGraph())


@pytest.fixture
def mock_graph_photo(monkeypatch):
    """Mock del pipeline de foto para tests SSE."""
    from app.routers import scan as scan_router_module

    async def _stream(*args, **kwargs):
        yield {"event": "on_chain_start", "name": "LangGraph", "data": {}}
        yield {
            "event": "on_chain_end",
            "name": "extract_ingredients",
            "data": {
                "output": {
                    "product_name": "PhotoProd",
                    "product_brand": None,
                    "extracted_ingredients": ["Azúcar", "Sal"],
                    "source": "photo",
                }
            },
        }
        yield {
            "event": "on_chain_end",
            "name": "personalize",
            "data": {"output": {"personalized_insights": []}},
        }
        yield {
            "event": "on_chain_end",
            "name": "calculate_risk",
            "data": {
                "output": {
                    "semaphore": "GRAY",
                    "conflict_severity": None,
                    "resolved": [],
                }
            },
        }

    class _MockGraphPhoto:
        def astream_events(self, *args, **kwargs):
            return _stream(*args, **kwargs)

    monkeypatch.setattr(
        scan_router_module, "build_scan_graph", lambda db, settings: _MockGraphPhoto()
    )


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
