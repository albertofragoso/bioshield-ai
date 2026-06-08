# BioShield AI — Architecture Study Guide

> **Propósito:** Preparación para interrogatorio arquitectónico. Las Q&As priorizan "¿por qué?" sobre "¿qué hace?". Completar con una sesión real de Q&A contra un LLM antes del interrogatorio.
>
> ⚠️ **Discrepancia conocida:** `architecture.md §7.2` dice "Fernet (AES-128-CBC)" — el código real (`services/crypto.py`) usa **AES-256-GCM** via `cryptography.hazmat.primitives.ciphers.aead.AESGCM`. CLAUDE.md dice "AES-256" — eso es lo correcto. Si el LLM pregunta el algoritmo, la respuesta correcta es AES-256-GCM.

---

## §1 · Visión general

### Resumen
- BioShield escanea etiquetas nutricionales (barcode o foto), detecta aditivos ocultos via búsqueda semántica, y cruza los hallazgos con los biomarcadores de sangre del usuario para personalizar el riesgo.
- El output principal es un **semáforo** (GREEN/YELLOW/RED) + score numérico + insights personalizados + alternativas más limpias del catálogo de 16,000+ productos.
- Cuatro invariantes no negociables: JWT en todos los endpoints salvo tres rutas de auth, datos médicos siempre encriptados (AES-256-GCM), biomarkers expiran en 180 días, y todo endpoint que llame a Gemini tiene `Depends(token_budget(...))`.

### Preguntas anticipadas

**Q: ¿Por qué encriptar los biomarkers si ya están detrás de JWT?**
A: JWT protege el transporte — cualquier empleado con acceso a la DB podría leer los datos en plaintext. AES-256-GCM en reposo garantiza que incluso con DB comprometida, los datos médicos son ilegibles sin la `AES_KEY`. La separación de preocupaciones (auth ≠ confidencialidad de datos) es el principio detrás.

**Q: ¿Por qué sugerir alternativas del mismo catálogo y no de todo el mercado?**
A: El catálogo propio (16,023 productos) tiene `clean_score` calculado y está indexado en ChromaDB, lo que permite similarity search en tiempo real. Buscar en "todo el mercado" requeriría integración con N fuentes externas con latencia y disponibilidad incontrolables — la calidad de la recomendación sufriría.

---

## §2 · Topología de capas

### Resumen
- Tres capas: Browser/Next.js → FastAPI (Python) → servicios externos (LangGraph, Gemini, ChromaDB, SQLAlchemy/DB).
- JWT viaja en HttpOnly cookie — nunca en localStorage, inmune a XSS.
- FastAPI actúa como orquestador: recibe requests del frontend, delega al agente LangGraph, y consolida el resultado.
- ChromaDB corre local (no managed) — decisión de simplicidad operacional en dev; en prod se evaluaría el tradeoff.

### Preguntas anticipadas

**Q: ¿Por qué HTTPOnly cookie y no Authorization header con localStorage?**
A: JavaScript no puede leer HttpOnly cookies, lo que elimina la superficie de ataque de XSS. Con localStorage cualquier script inyectado puede exfiltrar el token. El tradeoff es que las cookies requieren `SameSite` y `CORS` bien configurados, pero el beneficio de seguridad supera esa complejidad.

**Q: ¿Por qué LangGraph y no un pipeline directo de llamadas Gemini?**
A: LangGraph provee un grafo de estado con checkpointing, retry por nodo, y streaming nativo. Un pipeline directo requeriría manejar manualmente state sharing entre pasos, recuperación de errores parciales, y el streaming SSE. LangGraph lo resuelve como primitiva.

---

## §3 · Backend — FastAPI

### Resumen
- Cinco routers: `/auth`, `/scan`, `/biosync`, `/analytics`, `/waitlist`. Solo tres endpoints sin JWT: `/auth/login`, `/auth/register`, `/auth/refresh`.
- Middleware stack en orden: `RequestIDMiddleware` (UUID por request) → `RateLimitMiddleware` (SlowAPI) → `JWTAuthMiddleware`.
- Dos dependencies críticas: `get_current_user` (decodifica JWT → User) y `token_budget(cost)` (atomic SQL UPDATE → 429 si excede el presupuesto diario).
- Config solo desde `app/config.py` (Pydantic Settings) — nunca `os.environ` directo.

### Preguntas anticipadas

**Q: ¿Por qué el token_budget usa un atomic SQL UPDATE en vez de leer el saldo primero?**
A: Un read-modify-write en dos queries crea una race condition si dos requests llegan simultáneamente — ambos leen el mismo saldo, ambos lo modifican, uno de los dos bypasea el límite. El atomic UPDATE con CASE en el WHERE garantiza que el budget check y la actualización ocurren en una sola operación atómica, sin locks externos.

**Q: ¿Cómo funciona exactamente el reset diario del token_budget?**
A: No hay cron. El reset lo dispara el **primer request del nuevo día**: el UPDATE tiene un CASE que dice "si `tokens_budget_date < hoy`, escribe `:estimated` (reset); si no, acumula `tokens_used + estimated`". La fecha también se actualiza a hoy en la misma operación. Si el usuario no hace requests un día, el estado queda stale hasta el siguiente request — no hay reset proactivo.

---

## §4 · Pipeline de agente LangGraph

### Resumen
- `build_scan_graph()` construye un StateGraph con 7 nodos que comparten `ScanState` (TypedDict).
- Orden de ejecución: `identify_product → extract_ingredients → resolve_entities → (search_regulatory ‖ biosync_node) → detect_conflicts → calculate_risk → personalize_node`.
- Solo dos nodos llaman a Gemini: `extract_ingredients` (lista de ingredientes del label) y `personalize_node` (insights personalizados con biomarkers). El resto opera sobre DB y ChromaDB.
- El estado se acumula via `ScanStateAccumulator.apply(output)` — nunca asignación directa.

### Preguntas anticipadas

**Q: ¿Por qué `search_regulatory` y `biosync_node` corren en paralelo?**
A: Son independientes — `search_regulatory` consulta ChromaDB para estatus regulatorio de ingredientes, y `biosync_node` carga y desencripta los biomarkers del usuario de la DB. Ninguno depende del output del otro. Correrlos en paralelo reduce la latencia del pipeline.

**Q: ¿Por qué separar `resolve_entities` de `extract_ingredients`?**
A: `extract_ingredients` devuelve nombres de ingredientes tal como aparecen en la etiqueta (ej. "E-621", "Glutamato monosódico", "MSG"). `resolve_entities` los mapea a un identificador canónico (CAS number) usando el Entity Resolution Layer (ERL 2.0) — sin esa normalización, la búsqueda en ChromaDB y la DB sería frágil ante variaciones de nombre.

---

## §5 · Frontend — Next.js

### Resumen
- App Router con tres grupos de rutas: `(marketing)` (landing pública), `(auth)` (login/register), `(app)` (experiencia autenticada — dashboard, scan, biosync, history).
- Invariante HTTP: ningún componente llama `fetch()` directamente — todo pasa por `frontend/lib/api/client.ts` que inyecta el JWT y intercepta 401s.
- State management dividido: TanStack Query para server state (scans, biomarkers, history), Zustand para client state (auth, SSE stream).
- Custom hooks (`hooks/use-scan.ts`, `hooks/use-biosync.ts`, `hooks/use-auth.ts`) son la única interfaz a TanStack Query — ningún componente instancia `useQuery`/`useMutation` directamente.

### Preguntas anticipadas

**Q: ¿Por qué TanStack Query y no solo Zustand para todo el state?**
A: TanStack Query maneja automáticamente caching, invalidación, refetching, y loading/error states para server data. Replicar eso con Zustand requeriría lógica manual significativa. Zustand se reserva para state puramente de cliente (¿está el usuario logueado?, ¿qué frame del SSE stream está activo?) donde no hay servidor involucrado.

**Q: ¿Por qué `useRegister` hace auto-login en el mismo mutation en lugar de dos steps separados?**
A: UX — el usuario no debería tener que hacer login manualmente después de registrarse. Técnicamente, el backend ya devuelve tokens en el response de `/auth/register`, así que el hook puede establecer la sesión inmediatamente. Dos steps separados expondrían al usuario a una pantalla de login intermedia sin valor.

---

## §6 · Flujos críticos end-to-end

### Resumen
- Los flujos más críticos por criticality score: `register` (0.832), `login` (0.770), `extract_biomarkers` (0.703), `scan_barcode`/`scan_photo` (0.691).
- El flujo de registro crea access token + refresh token en el mismo request, los guarda en HttpOnly cookies, y hashea el refresh token (SHA-256) en DB — nunca se guarda el token raw.
- El scan por código de barras es SSE: el frontend consume eventos mientras el LangGraph pipeline ejecuta nodo a nodo.
- Scan por foto añade 3 estrategias de fallback en `identify_product`: OCR→EAN, OFF Search API, CTA manual para que el usuario linke con barcode.

### Preguntas anticipadas

**Q: ¿Por qué guardar el hash del refresh token en DB en lugar del token mismo?**
A: Si la DB se compromete, un atacante con los refresh tokens podría impersonar usuarios indefinidamente (tienen TTL de 7 días). Al guardar solo el hash SHA-256, el token raw nunca existe en DB — el atacante obtendría solo hashes inutilizables. El tradeoff es una operación de hash en cada refresh, que es despreciable.

**Q: ¿Por qué el scan usa SSE en lugar de un response HTTP normal?**
A: El pipeline LangGraph tarda varios segundos (OCR, Gemini, ChromaDB, personalización). Un response normal haría al usuario esperar con pantalla en blanco. SSE permite mostrar progreso node-by-node — el usuario ve "identificando producto", luego "analizando ingredientes", etc. — mejorando percibida performance significativamente.

---

## §7 · Seguridad

### Resumen
- JWT HS256: access token 15 min, refresh token 7 días. Single-use rotation — cada refresh invalida el token anterior.
- Encriptación de biomarkers: **AES-256-GCM** via `cryptography.hazmat.primitives.ciphers.aead.AESGCM` con key de 32 bytes desde env var `AES_KEY`. ⚠️ `architecture.md §7.2` dice "Fernet (AES-128-CBC)" — eso es un error en la doc; el código usa AES-256-GCM.
- Security headers en todas las responses: HSTS, CSP (`default-src 'self'`), X-Frame-Options DENY, etc.
- Rate limiting por SlowAPI: 60 req/min por IP (endpoints públicos), 10 req/min por usuario (endpoints LLM).
- **Key rotation de AES no está soportada**: cambiar `AES_KEY` invalida todos los biomarkers existentes — requeriría un migration job de re-encrypt manual. Esta limitación es intencional en v1.

### Preguntas anticipadas

**Q: ¿Por qué refresh tokens single-use (rotate on use) en lugar de long-lived estáticos?**
A: Si un refresh token es robado y el atacante lo usa, el sistema lo invalida — la víctima detecta la anomalía en su próximo refresh (su token ya no funciona). Con tokens estáticos de larga vida, el atacante puede usarlo durante 7 días sin que nadie lo detecte. El tradeoff es mayor complejidad en el cliente para manejar el nuevo token en cada refresh.

**Q: ¿Por qué AES-256-GCM sobre Fernet o libsodium/nacl?**
A: GCM provee autenticación integrada (AEAD — Authenticated Encryption with Associated Data), lo que significa que el ciphertext es a la vez confidencial e íntegro. Fernet (AES-128-CBC + HMAC separado) requiere dos operaciones distintas y su tamaño de key es menor. `cryptography.hazmat` da control directo sobre el algoritmo, nonce, y tag de autenticación.

---

## §8 · RAG y vector store

### Resumen
- ChromaDB con dos colecciones: `ingredients` (texto canónico de ingredientes/aditivos con estatus regulatorio, embeddings BGE-M3 de 1024 dims) y `products` (perfiles de 16,023 productos, mismo embedder).
- Embedder con fallback: primero `gemini-embedding-001` (API), si falla o `USE_LOCAL_EMBEDDINGS=true` → BGE-M3 local (HuggingFace `BAAI/bge-m3`).
- Entity Resolution Layer (ERL 2.0): mapea nombres de etiqueta a CAS number canónico via 4 estrategias en cascada (exact → E-number → synonym → vector similarity), con `confidence_score` para trazabilidad.
- Fuentes de datos RAG: FDA EAFUS (US), EFSA OpenFoodTox (EU), Codex GSFA (global).

### Preguntas anticipadas

**Q: ¿Por qué BGE-M3 local como fallback y no otro embedder de API?**
A: BGE-M3 es multilingüe y de alta calidad (MTEB benchmark top-tier), y al correr local no tiene latencia de red ni costo por token. Si `gemini-embedding-001` falla (API down, quota exhausted), el sistema sigue funcionando sin degradación de calidad observable. El tradeoff es el overhead de memoria de cargar el modelo (~500MB).

**Q: ¿Por qué cuatro estrategias en cascada para ERL en lugar de solo vector similarity?**
A: Vector similarity solo tiene ~80% de confianza para nombres ambiguos o nuevos. El CAS number exact match tiene confianza 1.0 — si lo hay, no tiene sentido gastar compute en un embedding. La cascada optimiza: usa el método más preciso primero y cae a similarity solo cuando los métodos deterministas fallan. `confidence_score` queda en `scan_history` para auditoría.

---

## §9 · Database schema

### Resumen
- SQLite en dev, PostgreSQL en prod. Migraciones con Alembic (13 versiones al 2026-06-03).
- Tablas principales: `users`, `products`, `biomarkers` (datos médicos encriptados), `scan_history`, `refresh_tokens`, `ingredients`, `regulatory_status`, `conflicts`, `data_sources`, `ingestion_log`, `off_contributions`.
- Biomarkers guardan `encrypted_data` + `encryption_iv` (nunca los valores en plaintext) + `expires_at` (180 días desde upload).
- `scan_history` guarda `semaphore_result`, `confidence_score`, `share_token` (para links públicos), y `result_json` completo para replay sin re-ejecutar el pipeline.

### Preguntas anticipadas

**Q: ¿Por qué guardar `result_json` en `scan_history` si ya están los ingredientes en la tabla `products`?**
A: Los insights personalizados son específicos del usuario (cruzan con sus biomarkers) — no son reproducibles desde `products` sola. `result_json` congela el estado completo del análisis en el momento del scan, permitiendo compartir el resultado via `share_token` o mostrarlo en historial sin re-ejecutar el pipeline LangGraph.

**Q: ¿Por qué SQLite en dev y no PostgreSQL desde el inicio?**
A: SQLite corre sin infra adicional — cero setup para nuevos desarrolladores. El tradeoff es que SQLite no soporta concurrencia de escritura ni algunos tipos de PostgreSQL (ej. `jsonb`). Alembic maneja las diferencias de dialectos. La decisión asume que dev no necesita simular carga concurrente — solo desarrollo y testing funcional.

---

## §10 · Pipeline de ingesta

### Resumen
- Ingesta offline (one-time): fetch paralelo de OFF Mexico, OFF Global, y USDA FoodData Central → carga a DB → scoring → indexado en ChromaDB (~30 min con BGE-M3).
- Prioridad de fuentes: OFF MX (1, mayor) > OFF Global (2) > USDA (3). Deduplicación: skip si barcode ya existe en DB, preservando la fuente de mayor prioridad.
- Resultado: 16,023 productos en DB — 431 OFF MX + 15,570 USDA + 22 legacy. 16,001 indexados en ChromaDB.
- Enrichment pipeline en runtime: cada scan exitoso dispara un `BackgroundTask` post-commit que actualiza `ingredients_json`, `clean_score`, y re-indexa en ChromaDB si `confidence >= 0.8`.

### Preguntas anticipadas

**Q: ¿Por qué OFF Mexico tiene prioridad sobre USDA si USDA tiene más productos?**
A: OFF es open source y tiene mejor cobertura de ingredientes reales (incluyendo aditivos E-numbers) para el mercado mexicano. USDA FoodData Central tiene más productos pero los datos de ingredientes son menos granulares para el caso de uso de BioShield. Mayor prioridad → mejor calidad de análisis para el usuario target.

**Q: ¿Qué pasa si el enrichment BackgroundTask falla silenciosamente?**
A: El scan ya está completo y en `scan_history` — el failure no afecta al usuario en ese momento. Los datos del producto en `products` quedan sin actualizar hasta el próximo scan exitoso del mismo barcode. No hay retry automático ni alerting en v1 — esta es una limitación conocida (consistencia eventual sin garantía de entrega).

---

## §11 · Observabilidad

### Resumen
- Cada request tiene un UUID generado por `RequestIDMiddleware`, disponible en el header `X-Request-ID` y en `contextvars.ContextVar` propagado a services y background tasks.
- JSON structured logging: `{"ts": "...", "level": "INFO", "logger": "app.routers.scan", "request_id": "...", "msg": "scan_complete", "semaphore": "RED"}`.
- Cada llamada a Gemini emite un evento con `tokens_prompt`, `tokens_output`, y `tokens_total`.
- Token usage por usuario visible en `GET /auth/me` (campo `tokens_used_today`).

### Preguntas anticipadas

**Q: ¿Por qué usar `contextvars.ContextVar` para el request_id en lugar de pasarlo como parámetro?**
A: FastAPI maneja requests async — varios requests pueden estar "en flight" simultáneamente. `ContextVar` es per-async-context, lo que significa que cada coroutine tiene su propio valor de `request_id` sin interferencia. Pasarlo como parámetro requeriría añadirlo a la firma de cada función en el call stack — acoplamiento innecesario.

**Q: ¿Hay métricas de latencia por nodo LangGraph?**
A: No en v1 — solo se registra el evento final de `scan_complete` con el semáforo. Para profiling de latencia habría que añadir instrumentación por nodo en `nodes.py`. Esta es una deuda técnica conocida para cuando la app esté en producción con tráfico real.

---

## §12 · Infraestructura y despliegue

### Resumen
- Docker Compose para dev: `backend` (FastAPI, puerto 8000, hot-reload), `frontend` (Next.js, puerto 3000), `postgres` (volumen persistente).
- Dockerfiles optimizados con BuildKit cache (`--mount=type=cache`) — el backend usa Python 3.11-slim, el frontend Node 20-alpine con pnpm y output standalone.
- GitHub Actions con `DOCKER_BUILDKIT=1` habilitado. CI gate (`test_ci_gate.py`) bloquea merge si hay endpoints LLM sin `token_budget`.
- Variables críticas: `SECRET_KEY` (JWT), `AES_KEY` (32 bytes exactos), `GEMINI_API_KEY`, `ENCRYPTION_KEY` (Fernet/legacy), `CHROMA_PATH`.

### Preguntas anticipadas

**Q: ¿Por qué un CI gate específico para `token_budget` en lugar de solo code review?**
A: Un endpoint LLM sin `token_budget` permite que cualquier usuario haga llamadas ilimitadas a Gemini — el costo lo absorbe la compañía. El error es fácil de cometer y difícil de detectar en review manual (el endpoint funciona, solo falta el guard). El CI gate lo convierte en un error de compilación — sin el Depends, el PR no puede mergearse.

**Q: ¿Por qué SQLite en dev en lugar de usar PostgreSQL via Docker Compose desde el principio?**
A: Velocidad de setup y velocidad de tests. SQLite no requiere proceso separado, los tests se ejecutan en memoria (`:memory:`), y la suite entera corre más rápido. El riesgo es divergencia de comportamiento — Alembic y los tests de integración usan el docker-compose con PostgreSQL real para mitigarlo.

---

## §13 · Testing

### Resumen
- 42+ archivos de test backend (pytest). Categorías: auth, scan pipeline, biosync, RAG/embeddings, ingesta, seguridad (headers, PHI isolation, logging redaction), CI gate, config.
- Tests E2E con Playwright en `tests/specs/{feature}/` en la raíz del repo — nunca dentro de `frontend/`.
- `test_ci_gate.py` verifica que todos los endpoints que llaman a `gemini.py` tienen `token_budget` en su firma — es el único test que bloquea merge si falla.
- `fixtures-mock` (39 nodos) tiene la cohesión más alta del codebase (0.358) — es el módulo mejor encapsulado.

### Preguntas anticipadas

**Q: ¿Por qué Playwright para E2E en la raíz del repo y no dentro de `frontend/`?**
A: Los tests E2E son cross-stack — verifican flujos que cruzan frontend, API, y DB. Vivir en `frontend/` implicaría que son tests de frontend, cuando en realidad son tests de integración del sistema completo. La raíz del repo es el lugar natural para tests que no pertenecen a ningún layer específico.

**Q: ¿Qué garantiza `test_ci_gate.py` exactamente?**
A: Parsea todos los routers buscando endpoints que tengan `gemini` en su call graph, y verifica que cada uno declare `Depends(token_budget(...))` en su firma. No testea comportamiento — testea estructura. Si alguien añade un endpoint LLM sin el guard, el test falla antes de que el PR llegue a review.

---

## §14 · Comunidades y acoplamiento

### Resumen
- El grafo de código (Leiden algorithm, 1,505 nodos) identifica 10 comunidades. `services-scan` (257 nodos, Python) es el core del pipeline; `ui-dialog` (130 nodos, TSX) son los componentes React.
- `fixtures-mock` (39 nodos, cohesión 0.358) es la comunidad más cohesionada — los fixtures de test están bien encapsulados.
- Acoplamiento de riesgo: `ui-dialog ↔ api-scan` (55 aristas) — componentes que podrían estar llamando a la API directamente en lugar de pasar por hooks. Requiere monitoreo.
- Criticality scores: `register` (0.832) y `RegisterPage` (0.815) son los flows más críticos — un bug ahí bloquea el onboarding de todos los usuarios.
- ⚠️ Esta sección es **meta-análisis del tooling de code review**, no arquitectura operacional. Las preguntas sobre "criticality score" son preguntas sobre el grafo, no sobre el sistema en producción.

### Preguntas anticipadas

**Q: ¿Por qué `register` tiene el criticality score más alto si `scan_barcode` es el feature principal?**
A: Criticality en el grafo se calcula por el número de nodos y flows que dependen transitivamente de esa función. `register` es el punto de entrada de todos los usuarios — sin ella, nadie puede llegar a `scan_barcode`. Un bug en register tiene blast radius total; un bug en scan afecta solo usuarios registrados.

**Q: ¿Por qué `versions-upgrade` (Alembic) tiene cohesión 0 si las migraciones son código relacionado?**
A: Las migraciones Alembic son archivos independientes por diseño — cada una es una transformación atómica y no se llaman entre sí. El grafo no detecta relaciones temporales (migración A precede a B), solo dependencias de código estáticas. Cohesión 0 es el comportamiento esperado para archivos con zero interdependencias en código.

---

## Flujo end-to-end: un scan de código de barras

El usuario abre la app en el browser (Next.js App Router). Navega a `/scan` y escribe o escanea un EAN. El `ScanPage` llama a `POST /scan/barcode` via `frontend/lib/api/client.ts`, que inyecta el JWT desde la cookie y abre una conexión SSE.

FastAPI recibe el request. El middleware stack lo procesa en orden: `RequestIDMiddleware` genera un UUID y lo mete en `contextvars`, `RateLimitMiddleware` verifica los 10 req/min, `JWTAuthMiddleware` decodifica el token y adjunta el `User`. Los dos `Depends` del endpoint se resuelven: `get_current_user` confirma la sesión y `token_budget(1000)` ejecuta el atomic SQL UPDATE — si el usuario excedió su budget diario, retorna 429 aquí mismo, antes de tocar Gemini.

Con el guard verde, FastAPI llama a `build_scan_graph()` y lanza el StateGraph. El primer nodo, `identify_product`, busca el barcode en la DB local. Si existe, retorna el producto cacheado; si no, consulta Open Food Facts API. El resultado — nombre, marca, imagen — se emite como primer evento SSE al frontend.

`extract_ingredients` recibe el label image o los ingredientes del OFF response y llama a Gemini Flash para extraer la lista de ingredientes como texto estructurado. Gemini retorna un JSON con los ingredientes; el nodo los escribe en `ScanState.ingredients`. Otro evento SSE.

`resolve_entities` toma esa lista y aplica ERL 2.0: para cada ingrediente busca CAS exact match, E-number match, synonym match, y como último recurso similarity search en ChromaDB `ingredients`. Cada ingrediente resuelto queda con un `confidence_score`. Los no resueltos quedan marcados como unknowns.

Los dos nodos siguientes corren en paralelo: `search_regulatory` hace similarity search en ChromaDB `ingredients` con los CAS numbers resueltos, recuperando el estatus regulatorio (FDA/EFSA/Codex) y notas de peligro. Simultáneamente, `biosync_node` consulta la DB, carga los biomarkers del usuario, los desencripta con AES-256-GCM, y aplica las reglas clínicas de `biomarker_rules.py` para identificar cuáles ingredientes tienen interacción con los valores del usuario.

`detect_conflicts` cruza los hallazgos regulatorios con los biomarkers para clasificar conflictos: REGULATORY (aditivo prohibido o restringido), SCIENTIFIC (evidencia de riesgo), o TEMPORAL (datos desactualizados). `calculate_risk` agrega todos los conflictos, aplica el ranking de severidad, y determina el semáforo final + score numérico. `personalize_node` llama a Gemini una segunda vez para generar 3-5 insights en lenguaje natural, personalizados para los valores del usuario.

Con el pipeline completo, el `_event_stream()` emite el evento final. Post-stream: `_upsert_product()` guarda o actualiza el producto en DB, `_create_pending_row()` inserta el `scan_history` con `status=pending`, y `_finalize_scan_history()` lo actualiza a `status=done` con `result_json` completo. Un `BackgroundTask` dispara `_run_enrich_task()` de forma asíncrona para actualizar `clean_score` y re-indexar en ChromaDB — sin bloquear la respuesta.

El `ScanResultPage` consume todos los eventos SSE, muestra el semáforo, los ingredientes de riesgo, y los insights. Si el usuario quiere alternativas, un query a `GET /scan/{id}/alternatives` lanza `AlternativeFinder`: embedding del producto actual, similarity search en ChromaDB `products` (top-10), filtrado por `clean_score < original`, ordenado ASC por score.

---

## Cheat Sheet

### Stack con tradeoffs

| Capa | Tecnología | ¿Por qué no [alternativa]? |
|------|-----------|--------------------------|
| Backend | FastAPI (Python 3.11+) | vs. Django REST: FastAPI es async nativo, más liviano, mejor para SSE y streaming |
| Orquestación | LangGraph | vs. cadena directa: checkpointing, retry por nodo, streaming como primitiva |
| LLM | Gemini 2.5 Flash | vs. GPT-4o: mejor soporte de visión de etiquetas + pricing por token |
| Embeddings | gemini-embedding-001 + fallback BGE-M3 | vs. OpenAI embeddings: vendor lock-in; BGE-M3 garantiza disponibilidad offline |
| Vector store | ChromaDB | vs. Pinecone: zero infra en dev, no managed, no costo; tradeoff: no distribuido |
| Frontend | Next.js 16 App Router | vs. CRA/Vite: SSR para landing SEO, App Router para layouts nested auth/app |
| DB (dev) | SQLite | vs. PostgreSQL dev: zero setup, tests in-memory más rápidos; tradeoff: no concurrencia write |
| DB (prod) | PostgreSQL | vs. MySQL: mejor soporte JSONB, extensiones, ecosistema Python |
| CSS | Tailwind v4 + shadcn/ui | vs. CSS Modules: velocidad de desarrollo; shadcn = componentes sin vendor lock-in |
| Auth | JWT HS256 HttpOnly cookies | vs. sessions: stateless, compatible con múltiples instancias; HttpOnly previene XSS |
| Encriptación | AES-256-GCM (cryptography.hazmat) | vs. Fernet: Fernet es AES-128; GCM provee AEAD (auth + confidencialidad en uno) |

### Valores críticos del sistema

| Parámetro | Valor | Dónde vive |
|-----------|-------|-----------|
| JWT access TTL | 15 minutos | `app/services/auth.py` |
| JWT refresh TTL | 7 días | `app/services/auth.py` |
| Biomarker expiry | 180 días desde upload | `app/routers/biosync.py` |
| Daily token budget | 50,000 tokens (default) | `DAILY_TOKEN_BUDGET` env var |
| Token reset | Primer request del nuevo día (inline, no cron) | `app/dependencies/token_budget.py` |
| ChromaDB collections | `ingredients` (1024-dim, BGE-M3), `products` (1024-dim, BGE-M3) | `CHROMA_PATH` env var |
| Productos en catálogo | 16,023 (431 OFF MX + 15,570 USDA + 22 legacy) | `products` table |
| AES key size | 32 bytes exactos (256 bits) | `AES_KEY` env var |
| ERL confidence: exact | 1.0 | `services/entity_resolution.py` |
| ERL confidence: E-number | 0.95 | `services/entity_resolution.py` |
| ERL confidence: synonym | 0.85 | `services/entity_resolution.py` |
| ERL confidence: vector | ≤ 0.80 | `services/entity_resolution.py` |

### Endpoints públicos (sin JWT)

| Endpoint | Método |
|----------|--------|
| `/auth/login` | POST |
| `/auth/register` | POST |
| `/auth/refresh` | POST |

### Puertos Docker Compose

| Servicio | Puerto |
|---------|--------|
| Backend (FastAPI) | 8000 |
| Frontend (Next.js) | 3000 |
| PostgreSQL | 5432 |

---

## Preguntas abiertas

Estas son decisiones arquitectónicas sin respuesta definitiva en v1 — el objetivo es explorarlas con el LLM, no defenderlas:

1. **¿Cuándo migrar de SQLite a PostgreSQL en dev?** ¿En qué punto la divergencia de dialectos justifica el overhead de correr Postgres en dev siempre?
2. **¿Cómo se haría key rotation de AES-256 sin invalidar biomarkers existentes?** La opción técnica es `MultiFernet`-style con lista de keys activas, pero requiere migration job de re-encrypt.
3. **¿Qué pasa si ChromaDB se cae mid-scan?** ¿El pipeline tiene circuit breaker o el scan falla completo? ¿Cómo debería degradarse gracefully?
4. **¿Qué SLA tiene Open Food Facts API y qué pasa si está down durante el scan?** ¿Hay timeout configurado? ¿El fallback es solo la DB local?
5. **¿El enrichment BackgroundTask debería tener retry con backoff?** Actualmente si falla, el producto queda sin actualizar hasta el próximo scan del mismo barcode.
6. **¿Por qué `gemini-embedding-001` como primary en lugar de BGE-M3 local siempre?** ¿El tradeoff latencia/calidad/costo justifica la dependencia de API?
7. **¿Cómo se versiona el índice ChromaDB si los embeddings de BGE-M3 cambian en una versión futura?** ¿Hay plan de re-indexado incremental vs. full rebuild?
