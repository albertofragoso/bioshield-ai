# Fases 1–6 — Backend BioShield AI: FastAPI + LangGraph + ChromaDB + Gemini

## Context

El backend es el núcleo del sistema. Procesa etiquetas nutricionales (barcode o foto), orquesta un pipeline de 7 nodos con LangGraph, busca aditivos en ChromaDB mediante retrieval híbrido (vector + BM25), cruza hallazgos con biomarcadores personalizados del usuario (AES-256 en reposo), y devuelve un semáforo de 5 colores (GRAY/BLUE/YELLOW/ORANGE/RED).

Estado actual: **MVP cerrado y verde** — 90 tests passing, 11 endpoints expuestos, pipeline LangGraph funcional, OCR Gemini Vision validado con 13 etiquetas MX reales.

El frontend (Fase 7) consume este backend directamente. Los contratos de este documento son la fuente de verdad para `frontend/lib/api/types.ts`.

---

## Stack

| Capa | Tecnología | Versión |
|---|---|---|
| Framework web | FastAPI | 0.115.6 |
| Servidor ASGI | Uvicorn | 0.34.0 |
| ORM | SQLAlchemy | 2.0.37 |
| Migraciones | Alembic | 1.14.1 |
| Validación | Pydantic v2 | 2.10.4 |
| Orquestación | LangGraph | 0.3.5 |
| LLM / Vision | Gemini 2.5 Flash | gemini-2.5-flash |
| Embeddings (primary) | Gemini embedding-001 | models/gemini-embedding-001 |
| Embeddings (fallback) | BGE-M3 (local) | BAAI/bge-m3 |
| Vector store | ChromaDB | 0.6.3 |
| BM25 | rank-bm25 | 0.2.2 |
| Fuzzy matching | rapidfuzz | 3.12.1 |
| Auth | python-jose + bcrypt | 3.3.0 / 4.2.1 |
| Encriptación | cryptography (AESGCM) | 44.0.0 |
| Rate limiting | slowapi | 0.1.9 |
| HTTP client | httpx | 0.28.1 |
| Base de datos dev | SQLite | — |
| Base de datos prod | PostgreSQL | psycopg2-binary |

---

## Estructura del proyecto

```
backend/
├── app/
│   ├── main.py                        # FastAPI app, CORS, middlewares, routers
│   ├── config.py                      # Settings (pydantic-settings) — todas las env vars
│   ├── middleware/
│   │   ├── auth.py                    # get_current_user dependency (JWT cookie)
│   │   └── rate_limit.py              # slowapi Limiter + custom key_func
│   ├── models/
│   │   ├── __init__.py                # Re-exports de todos los modelos ORM
│   │   └── base.py                    # DeclarativeBase, get_engine, get_db
│   ├── routers/
│   │   ├── auth.py                    # /auth: register, login, refresh, logout
│   │   ├── scan.py                    # /scan: barcode, photo + helpers
│   │   └── biosync.py                 # /biosync: upload, status, delete
│   ├── schemas/
│   │   └── models.py                  # Pydantic v2 — todos los request/response schemas
│   ├── agents/
│   │   ├── graph.py                   # StateGraph assembly (7 nodos)
│   │   ├── nodes.py                   # Node builders (closures sobre db + settings)
│   │   ├── prompts.py                 # EXTRACTOR_PROMPT, RECONCILER_PROMPT, OCR_CORRECTION_PROMPT
│   │   └── state.py                   # ScanState TypedDict
│   └── services/
│       ├── analysis.py                # compute_semaphore + BIOMARKER_RULES
│       ├── auth.py                    # JWT create/decode, bcrypt, refresh token storage
│       ├── conflicts.py               # detect_conflicts (SQL)
│       ├── crypto.py                  # AES-256-GCM encrypt/decrypt biomarkers
│       ├── embeddings.py              # embed_text con lock + LRU + rate-limit backoff
│       ├── entity_resolution.py       # resolve() — CAS → E-number → fuzzy
│       ├── gemini.py                  # extract_from_image + reconcile_ingredient
│       ├── maintenance.py             # expire_biomarkers (TTL cron)
│       ├── off_client.py              # Open Food Facts API client
│       ├── rag.py                     # ChromaDB client + upsert + query
│       ├── retrieval.py               # hybrid_search (vector 0.7 + BM25 0.3)
│       └── ingestion/
│           ├── common.py              # IngestionRecord, upsert_ingredient helpers
│           ├── codex_gsfa.py          # Parser Codex GSFA
│           ├── efsa_zenodo.py         # Parser EFSA OpenFoodTox (Zenodo)
│           └── fda_eafus.py           # Parser FDA EAFUS
├── alembic/
│   ├── versions/
│   │   ├── fbea1868d5e6_initial_schema.py
│   │   └── 1906e8b727d2_add_refresh_tokens_table.py
│   └── env.py
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_biosync.py
│   ├── test_crypto.py
│   ├── test_graph.py
│   ├── test_prompts_sync.py
│   ├── test_rag.py
│   ├── test_scan.py
│   └── test_services_external.py
├── requirements.txt
├── pytest.ini
├── alembic.ini
├── pyproject.toml                     # ruff + mypy config
├── CLAUDE.md
└── .env                               # env vars locales (no en git)
```

---

## Fase 1 — Bootstrap y configuración base

### 1.1 · FastAPI app + Settings

`app/config.py` — `Settings` como `pydantic_settings.BaseSettings`:
- Lee desde `.env` automáticamente.
- Todas las variables centralizadas: nunca leer `os.environ` directo.
- `@lru_cache` en `get_settings()` para instancia singleton.

Variables de entorno relevantes:

| Variable | Default dev | Descripción |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./bioshield.db` | SQLite dev / PostgreSQL prod |
| `JWT_SECRET` | `dev-secret-change-in-production` | Firmar JWT (cambiar en prod) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | TTL access token |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | TTL refresh token |
| `AES_KEY` | `dev-aes-key-32-bytes-changethis!` | Exactamente 32 bytes UTF-8 |
| `GEMINI_API_KEY` | `""` | API key de Google AI |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Modelo para Vision + reconciliation |
| `GEMINI_EMBEDDING_MODEL` | `models/gemini-embedding-001` | Embeddings 768-dim |
| `CHROMA_PERSIST_DIRECTORY` | `./chroma_db` | Directorio de persistencia ChromaDB |
| `CHROMA_COLLECTION_NAME` | `bioshield_ingredients` | Nombre de la colección |
| `USE_LOCAL_EMBEDDINGS` | `false` | Activar BGE-M3 local en vez de Gemini |
| `ALLOWED_ORIGINS` | `["http://localhost:3000"]` | CORS allowlist |

`app/main.py` — assembla el app:
- `CORSMiddleware` con `allow_credentials=True` (necesario para cookies HTTP-only).
- `SlowAPIMiddleware` + handler de `RateLimitExceeded`.
- Tres routers: `/auth`, `/scan`, `/biosync`.
- `/health` sin auth.
- `/docs` y `/redoc` solo si `settings.debug=True`.

### 1.2 · Base de datos + ORM

`app/models/base.py`:
- `DeclarativeBase` para todos los modelos.
- `get_engine()` lazy-singleton (maneja `check_same_thread` para SQLite).
- `get_db()` generator para inyección de dependencia en FastAPI.

Tablas (Alembic migration `fbea1868d5e6_initial_schema`):
- `users` — id (UUID PK), email (unique), password_hash, created_at
- `products` — barcode (PK), name, brand, image_url, created_at
- `ingredients` — id (UUID PK), entity_id (unique), canonical_name, cas_number, e_number, synonyms (JSON), created_at
- `regulatory_statuses` — id, ingredient_id (FK), source_id (FK), status, hazard_note, usage_limits
- `data_sources` — id, name (unique)
- `ingestion_logs` — id, source_id (FK), started_at, finished_at, records_upserted
- `scan_history` — id (UUID PK), user_id (FK), product_barcode (FK), ingredient_id (FK nullable), semaphore_result, confidence_score, conflict_severity, scanned_at
- `biomarkers` — id (UUID PK), user_id (FK unique), encrypted_data (BLOB), encryption_iv (BLOB), uploaded_at, expires_at

Tabla adicional (migration `1906e8b727d2_add_refresh_tokens_table`):
- `refresh_tokens` — id (UUID PK), user_id (FK), token_hash, jti, expires_at, revoked

---

## Fase 2 — Autenticación JWT HTTP-only

### 2.1 · Auth service

`app/services/auth.py`:
- `hash_password(password)` — bcrypt.
- `verify_password(plain, hashed)` — bcrypt verify.
- `create_access_token(user_id, settings)` — JWT con `type: "access"`, `sub: user_id`, exp `30 min`.
- `create_refresh_token(user_id, settings)` — JWT con `type: "refresh"`, `sub: user_id`, exp `7 días`.
- `decode_token(token, settings)` — jose `jwt.decode`, devuelve payload dict.
- `store_refresh_token(db, user_id, token, jti, settings)` — persiste hash SHA-256 del token.
- `validate_and_rotate_refresh_token(db, token, settings)` — verifica, revoca el anterior, emite nuevo par (rotation).
- `revoke_user_token(db, token)` — marca `revoked=True` para logout.

### 2.2 · Auth router

`app/routers/auth.py` — 4 endpoints:

| Endpoint | Rate limit | Descripción |
|---|---|---|
| `POST /auth/register` | 10/min | Registra usuario, devuelve `UserResponse`, setea cookies |
| `POST /auth/login` | 10/min | Valida credenciales, devuelve `TokenResponse`, setea cookies |
| `POST /auth/refresh` | — | Lee cookie `refresh_token`, rota par, devuelve nuevo `TokenResponse` |
| `POST /auth/logout` | — | Revoca refresh token en DB, borra ambas cookies |

Cookies (`_set_auth_cookies`):
- `access_token`: `HttpOnly=True`, `Secure=True` (prod), `SameSite=lax`, `max_age=30min`
- `refresh_token`: `HttpOnly=True`, `Secure=True` (prod), `SameSite=lax`, `max_age=7d`, `path=/auth/refresh`

### 2.3 · Auth middleware

`app/middleware/auth.py` — `get_current_user` como dependencia FastAPI:
- Lee cookie `access_token`.
- Decodifica con jose, valida `type == "access"`.
- Retorna el `User` ORM del DB; lanza `401` si cualquier paso falla.

### 2.4 · Rate limiting

`app/middleware/rate_limit.py`:
- `key_func` custom: si hay `access_token` válido en cookie, la clave es `user:{user_id}`; si no, es la IP.
- Evita penalizar usuarios detrás de NAT compartido.
- Default global: `60/min`. Overrides en decoradores: auth `10/min`, scan `20/min`.
- `rate_limit_exceeded_handler` devuelve JSON `{"detail": "Rate limit exceeded: ..."}` con status `429`.

---

## Fase 3 — Pipeline de análisis (LangGraph)

### 3.1 · ScanState

`app/agents/state.py` — `TypedDict` con `total=False`:

```python
class ScanState(TypedDict, total=False):
    # Inputs
    barcode: str | None
    image_b64: str | None
    user_id: str
    source: str  # "barcode" | "photo"

    # Intermediate
    product_name: str | None
    product_brand: str | None
    product_image_url: str | None
    extracted_ingredients: list[str]
    resolved: list[IngredientResult]
    rag_context_by_ingredient: dict[str, str]
    biomarkers: dict[str, Any] | None
    conflicts_by_ingredient: dict[str, list[IngredientConflict]]

    # Output
    semaphore: SemaphoreColor
    conflict_severity: str | None
    scanned_at: datetime
    error: str | None
```

### 3.2 · Grafo (graph.py)

```
START
  └─► identify_product
        ├─[tiene ingredientes]─► resolve_entities
        └─[sin ingredientes]──► extract_ingredients ─► resolve_entities
  resolve_entities → search_regulatory → biosync → detect_conflicts → calculate_risk → END
```

- Grafo construido **por request** (`build_scan_graph(db, settings)`): permite que los nodos accedan a la sesión DB viva.
- Condicional `needs_image_extraction`: si `extracted_ingredients` no está vacío, salta extracción Gemini.

### 3.3 · Nodos (nodes.py)

Los builders devuelven `async callable` cerrado sobre `(db, settings)`:

| Nodo | Responsabilidad |
|---|---|
| `identify_product` | Consulta Open Food Facts por barcode; si no hay barcode, retorna vacío |
| `extract_ingredients` | OCR con Gemini Vision (base64); usa `EXTRACTOR_PROMPT` + Structured Outputs |
| `resolve_entities` | Para cada ingrediente: CAS → E-number → fuzzy; agrega `regulatory_status` worst-case |
| `search_regulatory` | Búsqueda híbrida (vector + BM25) en ChromaDB/SQL por ingrediente; llena `rag_context_by_ingredient` |
| `biosync` | Carga y desencripta biomarkers del usuario desde DB; `None` si no tiene |
| `detect_conflicts` | Cruza ingredientes resueltos contra DB de conflictos (regulatory/scientific/temporal) |
| `calculate_risk` | Llama `compute_semaphore(resolved, biomarkers)`; asigna `semaphore` y `conflict_severity` |

### 3.4 · Prompts (prompts.py)

Los prompts viven como constantes en `app/agents/prompts.py` — mirror de `docs/prompts.md`. El test `test_prompts_sync.py` falla si divergen.

- `EXTRACTOR_PROMPT`: instrucciones para extracción de ingredientes desde imagen; normalización, separación de sustancias compuestas, idioma.
- `RECONCILER_PROMPT`: clasifica conflictos regulatorios (REGULATORY/SCIENTIFIC/TEMPORAL) y severidad (HIGH/MEDIUM/LOW) a partir de contexto RAG + biomarcadores.
- `OCR_CORRECTION_PROMPT`: corrige errores de OCR usando contexto químico (disponible para uso futuro).

---

## Fase 4 — Servicios externos y capa de datos

### 4.1 · Gemini Vision (gemini.py)

`extract_from_image(image_b64, settings)`:
- Valida base64; rechaza imágenes > 10 MB.
- Usa Structured Outputs con `response_schema` para obtener `ProductExtraction` tipado.
- `_to_gemini_schema()` filtra campos del JSON Schema de Pydantic que el SDK proto de Gemini no acepta (`title`, `default`, `$defs`, etc.).
- Graceful degradation: `ResourceExhausted` → 429; `GoogleAPIError` → 503.

`reconcile_ingredient(ingredient, rag_context, biomarkers, settings)`:
- Genera un `IngredientConflict | None` a partir del contexto RAG.
- Retorna `None` si no hay evidencia suficiente (degradación silenciosa).

### 4.2 · Open Food Facts (off_client.py)

- `fetch_product(barcode, settings)` — GET `world.openfoodfacts.org/api/v2/product/{barcode}`.
- Timeout configurable (`off_timeout_seconds`).
- Retorna `dict(name, brand, image_url, ingredients: list[str])` o `None` si 404 / error.

### 4.3 · Embeddings (embeddings.py)

`embed_text(text, settings)`:
- **Primario**: `genai.embed_content` con `gemini-embedding-001` (768 dim).
- **LRU cache** (`@lru_cache(maxsize=256)`) sobre `(text, model)`: hits no hacen API call.
- **API lock** (`asyncio.Lock`): serializa llamadas live para respetar rate limits del free tier (~15 RPM).
- **Backoff**: en `ResourceExhausted`, espera 65s y reintenta una vez.
- **Delay entre llamadas**: 4s (`_EMBED_INTER_CALL_DELAY`) cuando no hay cache hit.
- **Fallback**: `use_local_embeddings=True` → `_embed_local_bge()` (no wired en MVP; requiere `sentence-transformers`).

### 4.4 · ChromaDB RAG (rag.py)

- Colección cosine `bioshield_ingredients` con `get_or_create_collection`.
- `build_embedding_template()` — template determinístico: `[ID:...][Name:...][Status: FDA/EFSA/Codex][Risk:...][Context:...]`.
- `upsert_record()` — insert-or-update por `entity_id`.
- `query_by_embedding()` — devuelve `list[RAGHit]` con `similarity = 1 - (distance / 2)` (cosine).

### 4.5 · Retrieval híbrido (retrieval.py)

`hybrid_search(query, db, settings, top_k=5)`:
- Puntaje final: `0.7 * vector_similarity + 0.3 * bm25_score`.
- BM25L construido en-memory sobre todos los ingredientes SQL (canonical_name + synonyms).
- Degradación: si Chroma falla → BM25-only; si ambos fallan → lista vacía (semáforo GRAY).

### 4.6 · Entity Resolution (entity_resolution.py)

`resolve(extracted_name, db) → Resolution`:
1. Exact CAS → confidence 1.0
2. Exact E-number → confidence 0.95
3. Fuzzy `fuzz.token_sort_ratio` sobre canonical_name + synonyms:
   - `≥ 0.85` → confidence 0.7–0.9, `needs_hitl=False`
   - `0.60–0.85` → confidence 0.6–0.7, `needs_hitl=True` (HITL queue)
   - `< 0.60` → `ingredient=None`

### 4.7 · Ingesta de datos regulatorios (ingestion/)

Tres parsers, todos comparten helpers de `common.py`:
- `fda_eafus.py` — Parsea FDA EAFUS (Everything Added to Food in the United States).
- `efsa_zenodo.py` — Parsea EFSA OpenFoodTox desde Zenodo.
- `codex_gsfa.py` — Parsea Codex GSFA (General Standard for Food Additives).

`common.py`:
- `IngestionRecord` dataclass — forma canónica en memoria antes de persistir.
- `upsert_ingredient()` — upsert en SQL + embed + upsert en Chroma.
- `IngestionLog` — registro de corrida con `started_at`, `finished_at`, `records_upserted`.

---

## Fase 5 — Semáforo y análisis de biomarcadores

### 5.1 · BIOMARKER_RULES

`app/services/analysis.py` — `BIOMARKER_RULES: tuple[BiomarkerRule, ...]`:

| Biomarcador | Umbral | Keywords | Severidad | Mensaje |
|---|---|---|---|---|
| `ldl` | > 130 mg/dL | trans fat, grasas trans, aceite hidrogenado, hydrogenated, saturated fat | HIGH | LDL elevado con grasa trans/saturada |
| `glucose` | > 100 mg/dL | jarabe de maíz, high fructose, corn syrup, dextrosa, azúcar añadida, fructose | HIGH | Glucosa en ayuno alta con azúcares añadidos |
| `triglycerides` | > 150 mg/dL | fructose, fructosa, jarabe, syrup | MEDIUM | Triglicéridos altos con fructosa/jarabes |
| `sodium` | > 3000 mg/día | sodio, sodium, msg, glutamato monosódico | MEDIUM | Sodio alto con ingredientes salinos añadidos |
| `uric_acid` | > 7 mg/dL | jarabe de maíz, high fructose, corn syrup | MEDIUM | Ácido úrico alto con fructosa |

Las reglas se extienden **añadiendo entradas al tuple**, no modificando código.

### 5.2 · compute_semaphore

`compute_semaphore(ingredients, biomarkers, *, retrieval_degraded=False)`:

```
Prioridad (primer match gana):
  RED    ← cualquier ingrediente con regulatory_status = BANNED
  ORANGE ← alert de biomarker (detect_biomarker_conflicts)
  YELLOW ← status RESTRICTED o UNDER_REVIEW, o conflict existente
  GRAY   ← degraded retrieval, o < 50% de ingredientes resueltos
  BLUE   ← todos aprobados, sin conflictos
```

- `aggregate_regulatory_status()` — colapsa per-source statuses a worst-case (Banned > Restricted > Under Review > Approved).
- `detect_biomarker_conflicts()` — recorre BIOMARKER_RULES; retorna `list[PersonalizedAlert]`.

---

## Fase 6 — Encriptación, endpoints Biosync y DevOps

### 6.1 · AES-256-GCM (crypto.py)

- `encrypt_biomarker(data, aes_key) → (ciphertext, iv)`: JSON-serializa el dict, encripta con AESGCM, IV aleatorio de 12 bytes.
- `decrypt_biomarker(ciphertext, iv, aes_key) → dict`: desencripta in-place; falla ruidosamente en tampering.
- Clave debe ser exactamente 32 bytes UTF-8 (`AES_KEY` env var).
- Path de upgrade a KMS (AWS/GCP) documentado en `docs/deployment.md`.

### 6.2 · Biosync router (biosync.py)

| Endpoint | Rate limit | Auth | Descripción |
|---|---|---|---|
| `POST /biosync/upload` | 20/min | JWT | Encripta + persiste biomarcadores; upsert (1 row por usuario); TTL 180 días |
| `GET /biosync/status` | — | JWT | Devuelve `BiomarkerStatusResponse` o 404 |
| `DELETE /biosync/data` | — | JWT | Elimina el row; 404 si no existe |

TTL hardcodeado: `_BIOMARKER_TTL_DAYS = 180`.

### 6.3 · CI/CD (GitHub Actions)

`.github/workflows/ci.yml` — 4 jobs paralelos:

| Job | Herramienta | Qué hace |
|---|---|---|
| `lint` | ruff | `ruff check` + `ruff format --check` |
| `typecheck` | mypy | `mypy app/` — ignora imports faltantes, excluye tests/alembic |
| `test` | pytest | `pytest --cov=app --cov-report=term-missing` |
| `docker` | docker build | Build imagen sin push (usa layer cache de GHA) |

`docker` requiere que `lint` y `test` pasen. `lint` y `typecheck` corren en paralelo.

`pyproject.toml` — config de ruff y mypy:
- ruff: target Python 3.11, reglas E/W/F/I/UP, excluye `alembic/` y `scripts/`.
- mypy: `ignore_missing_imports=True`, excluye `tests/`, `alembic/`, `scripts/`.

### 6.4 · Mantenimiento TTL (maintenance.py)

`expire_biomarkers(db) → int`:
- `DELETE FROM biomarkers WHERE expires_at < NOW()`.
- Retorna número de filas eliminadas.
- El scheduling es externo (Render cron / GitHub Actions schedule).

### 6.5 · Deployment (docs/deployment.md)

Runbook completo que cubre:
- Deploy local con `docker compose up --build`.
- Deploy en Render (backend Python + PostgreSQL managed).
- Configuración de GitHub Secrets (`AES_KEY`, `JWT_SECRET`, `GEMINI_API_KEY`, etc.).
- Procedimiento de rotación de `AES_KEY` (re-encrypt-in-place).
- Path de upgrade a KMS (AWS/GCP).
- Rollback con Alembic (`alembic downgrade -1`).
- Health check reference (`GET /health`).

---

## Endpoints — resumen completo

| Método | Ruta | Auth | Rate limit | Status codes |
|---|---|---|---|---|
| POST | `/auth/register` | No | 10/min | 201, 409, 422 |
| POST | `/auth/login` | No | 10/min | 200, 401, 429 |
| POST | `/auth/refresh` | Cookie refresh | — | 200, 401 |
| POST | `/auth/logout` | JWT | — | 204 |
| GET | `/health` | No | — | 200 |
| GET | `/scan/ping` | JWT | — | 200 |
| POST | `/scan/barcode` | JWT | 20/min | 200, 404, 429 |
| POST | `/scan/photo` | JWT | 20/min | 200, 400, 413, 422, 429, 503 |
| POST | `/biosync/upload` | JWT | 20/min | 201, 422 |
| GET | `/biosync/status` | JWT | — | 200, 404 |
| DELETE | `/biosync/data` | JWT | — | 204, 404 |

---

## Schemas Pydantic (source of truth del contrato API)

`app/schemas/models.py` — los schemas que el frontend espeja en `lib/api/types.ts`:

```python
# Enums
SemaphoreColor: GRAY | BLUE | YELLOW | ORANGE | RED
ConflictSeverity: HIGH | MEDIUM | LOW
ConflictType: REGULATORY | SCIENTIFIC | TEMPORAL
RegulatoryStatus: Approved | Banned | Restricted | Under Review

# Auth
RegisterRequest       { email, password (min 8) }
LoginRequest          { email, password }
TokenResponse         { access_token, refresh_token, token_type, expires_in }
UserResponse          { id: UUID, email, created_at }

# Scan
BarcodeRequest        { barcode: str (8-14 dígitos) }
PhotoScanRequest      { image_base64: str }
ProductExtraction     { ingredients: list[str], has_additives: bool, language: str }
IngredientConflict    { conflict_type, severity, summary, sources: list[str] }
IngredientResult      { name, canonical_name?, cas_number?, e_number?,
                        regulatory_status?, confidence_score, conflicts: [] }
ScanResponse          { product_barcode, product_name?, semaphore, ingredients,
                        conflict_severity?, source, scanned_at }

# Biosync
BiomarkerUploadRequest  { data: dict (non-empty) }
BiomarkerStatusResponse { id: UUID, uploaded_at, expires_at, has_data: bool }
PersonalizedAlert       { ingredient, biomarker_conflict, severity }
BiosyncAnalysis         { has_biomarkers, alerts: [], semaphore_override? }
```

---

## Suite de tests

9 módulos, 90 tests passing:

| Archivo | Qué prueba |
|---|---|
| `test_auth.py` | Register, login, refresh, logout, rate limiting, 409/401 |
| `test_biosync.py` | Upload, status, delete, TTL, 404, encriptación round-trip |
| `test_crypto.py` | AES-256 encrypt/decrypt, tampering detection, key length validation |
| `test_graph.py` | Pipeline LangGraph end-to-end mockeando servicios externos |
| `test_prompts_sync.py` | Verifica paridad entre `prompts.py` y `docs/prompts.md` |
| `test_rag.py` | ChromaDB upsert/query, hybrid_search, degradación BM25-only |
| `test_scan.py` | `/scan/barcode`, `/scan/photo`, 404, 422, 413, persistencia en DB |
| `test_services_external.py` | OFF client, Gemini Vision (mockeado con respx/httpx) |
| `conftest.py` | DB SQLite en-memoria, fixtures de usuario autenticado, app override |

`pytest.ini`:
```ini
[pytest]
testpaths = tests
asyncio_mode = auto
```

---

## Archivos críticos — resumen

| Archivo | Rol en el sistema |
|---|---|
| `app/schemas/models.py` | Contratos API — source of truth para FE tipos |
| `app/agents/graph.py` | Topología del pipeline — modificar aquí para añadir nodos |
| `app/services/analysis.py` | BIOMARKER_RULES — datos, no código; extender el tuple |
| `app/agents/prompts.py` | Templates de Gemini — mirror de `docs/prompts.md` |
| `app/services/embeddings.py` | Rate limiting de la API de embeddings — frágil en free tier |
| `app/routers/auth.py` | Gestión de cookies — `SameSite=lax`, scope de refresh cookie |
| `alembic/versions/` | Historial de migraciones — no editar manualmente |
| `.env` | Secretos locales — no commitear, usar `.env.example` como referencia |

---

## Decisiones de diseño y razones

| Decisión | Alternativa descartada | Razón |
|---|---|---|
| Grafo LangGraph por-request | Grafo singleton | Permite que los nodos accedan a la sesión DB viva sin compartir estado entre requests |
| JWT en HTTP-only cookies | Bearer header | CSRF protection + no exposición en JS; `SameSite=lax` mitiga CSRF en flujos normales |
| Refresh token en DB (con hash) | Refresh token stateless | Permite revocación instantánea en logout; rotation detecta replay attacks |
| Retrieval híbrido vector+BM25 | Solo vector | BM25 mantiene recall en queries cortos/exactos donde el embedding no discrimina |
| AES-256-GCM (AESGCM) | Fernet (AES-CBC+HMAC) | GCM provee AEAD nativo; IV aleatorio por operación; path a KMS más limpio |
| BIOMARKER_RULES como tuple de dataclasses | Lógica en código | Extender reglas sin cambiar branches; facilita revisión por nutricionistas |
| `compute_semaphore` prioridad fija | ML classifier | Determinismo auditable; explicable al usuario; suficiente para MVP |
| SQLite en dev / PostgreSQL en prod | Solo PostgreSQL | Onboarding inmediato sin Docker obligatorio; psycopg2-binary ya en requirements |
| BGE-M3 como fallback (no wired) | Siempre Gemini | Reserva offline/prod si free tier se agota; ~500MB extra de deps omitidos en MVP |

---

## Riesgos conocidos y estado

| Riesgo | Estado | Mitigación |
|---|---|---|
| Free tier Gemini agotado en dev | Activo | Lock + backoff en embeddings; mockear en tests FE; tier pagado en staging |
| HITL threshold (0.7) sin calibración | Pendiente | Revisión post-dogfood con datos reales de etiquetas MX |
| BGE-M3 fallback no implementado | Pendiente | `NotImplementedError` explícito; tracked en `reviews/18-04.md` |
| KMS para AES_KEY en producción | Pendiente | Path documentado en `docs/deployment.md`; runbook de rotación disponible |
| Cookies cross-origin en Vercel+Render | Pendiente | Requiere `SameSite=None; Secure` si dominios distintos; verificar en staging |
