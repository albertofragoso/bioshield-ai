# BioShield AI — Testing (backend/tests)

## Qué es

Suite integral de tests que valida endpoints FastAPI, lógica de autenticación (JWT/cookies), encriptación de biomarcadores, y consultas a la base de datos. Sin mocks de la capa de datos, con inyección de dependencias para servicios externos.

## Stack

- **Test Runner:** pytest
- **Async:** httpx.AsyncClient + pytest-asyncio (`asyncio_mode = auto`)
- **Base de datos:** SQLite en memoria (`sqlite:///:memory:`)
- **Mocking:** unittest.mock.AsyncMock / pytest-mock (`mocker`)
- **Fixtures:** conftest.py (app, client, db_session, override_settings, disable_rate_limiting)

## Convenciones

### Base de datos en tests
- Usar **siempre SQLite en memoria** — no conectar a desarrollo
- **No mockear** ORM ni SQLAlchemy: ejercitar queries reales
- Cada test recibe sesión limpia (transaction rollback via fixture `db_session`)
- El schema se crea con `Base.metadata.create_all()` en la fixture `test_engine` — **no** usa Alembic

### Mocks permitidos
- **Servicios externos:** Gemini API, Open Food Facts API, ChromaDB
- **Cómo mockear:** `unittest.mock.AsyncMock` o pytest-mock (`mocker`)
- **Prohibido mockear:** modelos de datos, capa ORM, acceso a DB

### Rate limiting en tests
- Desactivado globalmente via fixture `disable_rate_limiting` (`limiter._enabled = False`)
- No es necesario hacer nada extra en tests individuales

### Estructura de archivos

```
tests/
├── CLAUDE.md                    # Este archivo
├── conftest.py                  # Fixtures: app, client, db_session, settings
├── test_auth.py                 # Registro, login, JWT, refresh, logout
├── test_scan.py                 # Barcode scan, photo scan, fallback
├── test_biosync.py              # Upload, encriptación, TTL, acceso sin permisos
└── test_rag.py                  # Búsqueda semántica, entity resolution, conflictos
```

## Documentación de referencia

- **Backend:** backend/CLAUDE.md
- **pytest:** https://docs.pytest.org
- **httpx:** https://www.python-httpx.org
- **pytest-asyncio:** https://pytest-asyncio.readthedocs.io
- **SQLAlchemy Testing:** https://docs.sqlalchemy.org/20/faq/sessions.html#faq-session-rollback

## Cómo correr los tests

```bash
# Todos los tests
pytest

# Con cobertura
pytest --cov=app --cov-report=term-missing

# Un módulo específico
pytest tests/test_auth.py -v

# Un test específico
pytest tests/test_auth.py::test_register_success -v

# Con salida detallada
pytest -vv --tb=short
```

## Variables de entorno en tests

Los tests sobreescriben `Settings` via la fixture `override_settings` en `conftest.py`. No se requiere archivo `.env` para correr la suite.
