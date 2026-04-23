# BioShield AI — Backend

## Qué es

Backend FastAPI que procesa etiquetas nutricionales via Gemini, busca aditivos ocultos mediante embeddings semánticos, y cruza hallazgos con biomarcadores encriptados del usuario. Orquestación con LangGraph, base de datos con SQLAlchemy.

## Stack

> Stack completo y convenciones de negocio en `.claude/CLAUDE.md`.

Adiciones específicas del backend:

- **ORM:** SQLAlchemy 2.0
- **Autenticación:** JWT con HTTP-only cookies
- **Encriptación:** AES-256 (Fernet) para biomarcadores
- **Rate limiting:** slowapi (10 req/min auth, 20 req/min scan)

## Convenciones

- **Config:** toda variable de entorno vive en `app/config.py` como campo de `Settings`. Nunca leer `os.environ` directamente.
- **Dependencias FastAPI:** inyectar `settings: Settings = Depends(get_settings)` y `db: Session = Depends(get_db)` en los endpoints.
- **Migraciones:** no modificar `alembic/versions/` manualmente, usar Alembic CLI.
- **Queries:** usar SQLAlchemy, nunca queries SQL directas.

## Estructura

```
backend/
├── app/
│   ├── main.py                    # FastAPI app, CORS, rate limiting, routers
│   ├── config.py                  # Settings (Pydantic) — todas las env vars
│   ├── routers/                   # Endpoints HTTP: auth.py, scan.py, biosync.py
│   ├── schemas/                   # Pydantic v2 request/response models
│   ├── models/                    # SQLAlchemy ORM models (Base, tables, relationships)
│   ├── agents/                    # LangGraph: graph.py, nodes.py, state.py
│   └── services/                  # Clientes externos: gemini.py, off_client.py, embeddings.py
├── alembic/                       # Migraciones de base de datos
├── tests/                         # Suite de tests (ver tests/CLAUDE.md)
├── requirements.txt
├── pytest.ini
└── CLAUDE.md                      # Este archivo
```

## Documentación de referencia

- **Arquitectura y schema BD:** docs/architecture.md
- **Estrategia de embeddings:** docs/embedding-strategy.md
- **Fuentes de datos RAG:** docs/data-sources.md
- **Prompt templates:** docs/prompts.md
- **Testing:** backend/tests/CLAUDE.md
- **FastAPI:** https://fastapi.tiangolo.com
- **SQLAlchemy 2.0:** https://docs.sqlalchemy.org/20

## Cómo correr el backend

```bash
# Configurar entorno
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Desarrollo (con hot-reload)
uvicorn app.main:app --reload

# Tests (ver tests/CLAUDE.md para detalles)
pytest
pytest --cov=app --cov-report=term-missing
```

## Endpoints principales

| Método | Ruta              | Auth | Descripción                          |
|--------|-------------------|------|--------------------------------------|
| POST   | /auth/register    | No   | Registro de usuario                  |
| POST   | /auth/login       | No   | Login, devuelve JWT (HTTP-only)      |
| POST   | /auth/refresh     | No   | Refresca access token                |
| DELETE | /auth/logout      | JWT  | Logout (invalida refresh token)      |
| GET    | /health           | No   | Health check                         |
| POST   | /scan/barcode     | JWT  | Escaneo por código de barras         |
| POST   | /scan/photo       | JWT  | Escaneo por foto de etiqueta (Gemini)|
| POST   | /scan/contribute  | JWT  | Contribución a Open Food Facts (Fase 2) — 202 Accepted, BackgroundTask async |
| POST   | /biosync/upload   | JWT  | Subir biomarcadores (AES-256)        |
| GET    | /biosync/status   | JWT  | Estado y expiración de biomarcadores |
| DELETE | /biosync/data     | JWT  | Eliminar datos médicos               |

## Variables de entorno

Ver `.env.example` en la raíz del proyecto. Todas las variables se definen en `app/config.py`.