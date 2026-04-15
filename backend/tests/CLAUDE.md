# BioShield AI — Convenciones de Testing (backend/tests)

## Stack de testing
- **pytest** como runner principal
- **httpx.AsyncClient** para tests de endpoints (async)
- **SQLite en memoria** como base de datos de test (`sqlite:///:memory:`)
- **pytest-asyncio** en modo `asyncio_mode = auto`

## Reglas críticas

### Base de datos
- Usar siempre SQLite en memoria para tests — no conectar a la base de datos de desarrollo
- No mockear el ORM ni SQLAlchemy: los tests deben ejercitar las queries reales
- Cada test recibe una sesión limpia (transaction rollback al finalizar via fixture `db_session`)

### Mocks permitidos
- Servicios externos: Gemini API, Open Food Facts API, ChromaDB
- Usar `unittest.mock.AsyncMock` o `pytest-mock` (`mocker`) para estos servicios
- Nunca mockear el modelo de datos ni la capa de acceso a DB

### Estructura de archivos
```
tests/
├── CLAUDE.md
├── conftest.py          # Fixtures globales (app, client, db_session, test settings)
├── test_auth.py         # Tests de registro, login, JWT, refresh
├── test_scan.py         # Tests de barcode scan, photo scan, fallback
├── test_biosync.py      # Tests de upload, TTL, encriptación, acceso sin permisos
└── test_rag.py          # Tests de búsqueda semántica, entity resolution, conflictos
```

## Cómo correr los tests
```bash
# Desde el directorio backend/
pytest

# Con cobertura
pytest --cov=app --cov-report=term-missing

# Solo un módulo
pytest tests/test_auth.py -v
```

## Variables de entorno en tests
Los tests sobreescriben `Settings` via la fixture `override_settings` en `conftest.py`.
No se requiere archivo `.env` para correr el suite de tests.
