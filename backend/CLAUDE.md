# BioShield AI — Backend

## Qué es

Backend FastAPI que procesa etiquetas nutricionales via Gemini, busca aditivos ocultos mediante embeddings semánticos, y cruza hallazgos con biomarcadores encriptados del usuario. Orquestación con LangGraph, base de datos con SQLAlchemy.

## Stack

> Stack completo y convenciones de negocio en `.claude/CLAUDE.md`.

Adiciones específicas del backend:

- **ORM:** SQLAlchemy 2.0
- **Autenticación:** JWT con HTTP-only cookies
- **Encriptación:** AES-256-GCM (cryptography.hazmat AESGCM) para biomarcadores
- **Rate limiting:** slowapi (10 req/min auth, 20 req/min scan)

## Convenciones

- **Config:** toda variable de entorno vive en `app/config.py` como campo de `Settings`. Nunca leer `os.environ` directamente.
- **Dependencias FastAPI:** inyectar `settings: Settings = Depends(get_settings)` y `db: Session = Depends(get_db)` en los endpoints.
- **Migraciones:** no modificar `alembic/versions/` manualmente, usar Alembic CLI.
- **Queries:** usar SQLAlchemy, nunca queries SQL directas.

## Reglas de arquitectura (refactors C1–C4)

### Módulos compartidos van en `app/core/`, no en `app/services/`
Funciones puras sin estado (semáforo, rankings) viven en `app/core/`. Si dos servicios comparten la misma lógica, extraerla a `app/core/` antes de duplicar.

### Typed shapes para datos externos
- Los payloads que llegan de fuentes externas (decrypt, API, DB) DEBEN tener un dataclass tipado con `parse_*(raw)` que valide en el punto de entrada.
- `isinstance(x, dict)` en medio del pipeline = señal de que falta un typed shape.
- Ejemplo: `DecryptedBiomarker` + `parse_biomarker_payload()` en `app/services/biomarker_rules.py`.

### Acumuladores de estado: usar `apply()`, nunca dict ni asignación directa
- Los acumuladores parciales (p.ej. `ScanStateAccumulator`) usan `apply(output)` para TODAS las actualizaciones de nodo — sin excepción.
- `apply()` filtra `None` y claves desconocidas; la asignación directa bypasea esa guardia.
- Nunca mezclar `accumulator.apply(output)` con `accumulator.campo = output.get(...)` en el mismo stream.

### Pydantic models son inmutables: usar `model_copy(update=...)`
- Nunca mutar un modelo Pydantic in-place (`.campo = valor`, `.lista.append(...)`).
- Usar `item = item.model_copy(update={"campo": nuevo_valor})`.
- LangGraph con last-write-wins channels es especialmente vulnerable a mutaciones in-place que se acumulan en retries.

### StrEnum: no extraer `.value` para comparaciones
- `SemaphoreColor` y `ConflictSeverity` son `StrEnum` — sus instancias YA son strings.
- Extraer `.value` solo cuando el destino rechaza enums explícitamente (ChromaDB metadata, columnas DB `str`).
- En tests los mocks pueden devolver `str` crudo; proteger con `isinstance(x, SemaphoreColor)` antes de `.value`.

### LangGraph TypedDict state: imports en runtime, no TYPE_CHECKING
- LangGraph llama `get_type_hints()` al construir el grafo.
- Si un tipo en `ScanState` está bajo `TYPE_CHECKING`, la resolución falla silenciosamente.
- Usar import directo al nivel del módulo aunque genere una dependencia visible.

### Rankings y mappings compartidos: centralizar en `app/core/priorities.py`
- Dicts `_STATUS_RANK` / `_SEVERITY_RANK` duplicados en distintos servicios → `worst_status()` / `worst_severity()` en `app/core/priorities.py`.
- Antes de consolidar: auditar semánticamente que los dicts sean idénticos (diff explícito).

## Regla crítica: endpoints LLM

Todo endpoint que llame a `gemini.py` (directa o indirectamente via el agente LangGraph)
DEBE declarar `_budget: User = Depends(token_budget(ENDPOINT_TOKEN_COST["<key>"]))` en su firma.
El test `tests/test_ci_gate.py` falla si se omite. Sin excepción.

## Estructura

```
backend/
├── app/
│   ├── main.py                    # FastAPI app, CORS, rate limiting, routers
│   ├── config.py                  # Settings (Pydantic) — todas las env vars
│   ├── routers/                   # Endpoints HTTP: auth.py, scan.py, biosync.py, analytics.py, waitlist.py
│   ├── schemas/                   # Pydantic v2 request/response models
│   ├── models/                    # SQLAlchemy ORM models (Base, tables, relationships)
│   ├── agents/                    # LangGraph: graph.py, nodes.py, state.py, accumulator.py, timing.py, prompts.py
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
| GET    | /scan/history     | JWT  | Historial de scans del usuario (limit param, default 20) |
| POST   | /scan/barcode     | JWT  | Escaneo por código de barras         |
| POST   | /scan/photo       | JWT  | Escaneo por foto de etiqueta (Gemini)|
| GET    | /scan/{barcode}/alternatives | JWT | Alternativas más limpias — hybrid matching (SQL + ChromaDB) (Fase 2) |
| POST   | /scan/contribute  | JWT  | Contribución a Open Food Facts (Fase 2) — 202 Accepted, BackgroundTask async |
| POST   | /biosync/upload   | JWT  | Subir biomarcadores (AES-256-GCM)    |
| GET    | /biosync/status   | JWT  | Estado y expiración de biomarcadores |
| DELETE | /biosync/data     | JWT  | Eliminar datos médicos               |
| POST   | /analytics/events | JWT  | Registrar evento de analítica        |
| POST   | /waitlist/signup  | No   | Registro en lista de espera          |

## Variables de entorno

Ver `.env.example` en la raíz del proyecto. Todas las variables se definen en `app/config.py`.