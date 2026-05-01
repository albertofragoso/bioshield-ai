# Diseño — E2E Integration Tests Nivel 3

**Fecha:** 2026-04-30
**Estado:** aprobado
**Referencia:** `docs/testing.md` §Nivel 3

---

## Contexto

BioShield AI tiene una pirámide de testing de tres niveles. El Nivel 2 (`tests/specs/`) cubre los flujos de UI con el backend mockeado vía `page.route()`. El propósito del Nivel 3 es detectar drift entre el contrato mockeado y el backend real: cambios de schema en los endpoints, regresiones de OpenAPI, y comportamiento incorrecto del pipeline LangGraph con datos reales.

Este documento especifica la implementación del Nivel 3.

---

## Arquitectura general

El Nivel 3 es un proyecto Playwright separado dentro del mismo binario. No modifica `tests/specs/` ni los proyectos existentes en `playwright.config.ts`. Agrega un tercer `project` llamado `integration` que apunta a `tests/specs-integration/` y tiene su propio `globalSetup`/`globalTeardown`.

```
globalSetup
  1. docker compose -f docker-compose.integration.yml up -d --wait
  2. Esperar health check del backend (alembic upgrade head puede tardar)
  3. POST /auth/register  →  usuario de test vía API real
  4. POST /auth/login     →  cookies guardadas en tests/fixtures/integration-auth.json

Tests (secuenciales, workers: 1)
  → usan storageState con las cookies del paso 4

globalTeardown
  1. docker compose -f docker-compose.integration.yml down -v
  (el flag -v elimina volúmenes → siguiente run empieza con estado limpio)
```

**Stack en Docker:**

| Servicio   | Imagen / Build                  | Puerto host |
|------------|----------------------------------|-------------|
| postgres   | postgres:16-alpine               | —           |
| backend    | ./backend/Dockerfile (existente) | 8000        |
| frontend   | ./frontend/Dockerfile (nuevo)    | 3001        |

El snapshot de ChromaDB (`tests/fixtures/chroma-seed/`) se monta como volumen **read-only** en el backend. Contiene solo los ingredientes de Nutella (~7 entidades), suficiente para que el pipeline de scan devuelva un semáforo válido sin depender de OFF API en CI.

---

## Estructura de archivos

```
repo/
├── docker-compose.integration.yml
├── playwright.config.ts                        (modificado)
│
├── frontend/
│   └── Dockerfile                              (nuevo)
│
├── tests/
│   ├── fixtures/
│   │   ├── chroma-seed/                        (nuevo — snapshot versionado en git)
│   │   │   └── README.md                       (proceso de regeneración)
│   │   ├── integration-auth.json               (generado en runtime, gitignored)
│   │   └── biosync-test.pdf                    (nuevo — PDF fixture, 1 página)
│   │
│   └── specs-integration/
│       └── smoke/
│           ├── integration-global-setup.ts     (test Playwright — docker up + seed usuario)
│           ├── integration-global-teardown.ts  (test Playwright — docker down -v)
│           └── smoke.spec.ts
│
└── .github/workflows/
    └── playwright-integration.yml              (nuevo)
```

---

## Los 6 tests

Los tests corren secuencialmente (`workers: 1`) y comparten el `storageState` del usuario creado en `globalSetup`. El orden importa: los tests posteriores asumen que el scan de Nutella ya fue realizado.

### Test 1 — Verificar auth state
```
GET /scan/ping
→ 200, { user_id: <uuid> }
```
Verifica que el `storageState` guardado en `globalSetup` (login real + cookies) produce una sesión autenticada válida. El contrato de `/auth/login` está implícitamente cubierto por el propio `globalSetup`, que falla en startup si el login no devuelve 200.

### Test 2 — Scan barcode Nutella
```
POST /scan/barcode { barcode: "3017624010701" }
→ 200
Verifica: semaphore ∈ [RED, ORANGE, YELLOW, GRAY], product_name presente,
          ingredients.length > 0
```
No se afirma un color específico — el test valida el contrato del schema, no la calidad del análisis.

### Test 3 — Biosync flujo completo
```
POST /biosync/extract (multipart/form-data, PDF fixture)
→ 200, biomarkers.length > 0

POST /biosync/upload (con los biomarkers extraídos del paso anterior)
→ 201

GET /biosync/status
→ 200, has_data: true, expires_at en el futuro
```
Este test es el único que llama a Gemini API (`GEMINI_API_KEY` en el workflow de CI). El PDF fixture contiene valores inventados (glucosa, colesterol) — no datos reales de paciente.

### Test 4 — Resultado guardado del scan
```
GET /scan/result/3017624010701
→ 200, schema ScanResponse completo
Verifica: product_barcode === "3017624010701", semaphore presente
```
Valida el endpoint de recuperación del resultado cacheado, que usa un JOIN `ScanHistory ↔ Product`.

### Test 5 — Historial de scans
```
GET /scan/history
→ 200, array con al menos 1 entrada
Verifica: entries[0].product_barcode === "3017624010701", semaphore presente
```
Este endpoint alimenta la página `/history` y el dashboard. Tiene la query relacional más compleja del backend.

### Test 6 — Logout
```
POST /auth/logout
→ 204
Verifica: cookies access_token y refresh_token eliminadas del browser context
```

---

## Cambios en `playwright.config.ts`

`globalSetup`/`globalTeardown` y `workers` son opciones top-level en Playwright, no per-proyecto. Para aislar el setup de Docker al proyecto `integration` se usa el patrón `dependencies`/`teardown` de proyectos:

```typescript
// Agrega estos tres proyectos sin modificar los existentes (chromium, firefox)

{
  name: 'integration-setup',
  testMatch: /integration-global-setup\.ts/,
},
{
  name: 'integration',
  dependencies: ['integration-setup'],
  teardown: 'integration-teardown',
  testMatch: '**/specs-integration/smoke/smoke.spec.ts',
  use: {
    ...devices['Desktop Chrome'],
    baseURL: 'http://localhost:3001',
    storageState: 'tests/fixtures/integration-auth.json',
  },
  retries: 0,
},
{
  name: 'integration-teardown',
  testMatch: /integration-global-teardown\.ts/,
},
```

Con este patrón, `global-setup.ts` y `global-teardown.ts` se convierten en archivos de test Playwright (con `test()` blocks) en lugar de funciones exportadas. El proyecto `integration-setup` corre antes que `integration`, y `integration-teardown` corre al final.

En el CI workflow, los tests se ejecutan con `--workers=1` para garantizar orden secuencial:
```
pnpm playwright test --project=integration-setup --project=integration --project=integration-teardown --workers=1
```

- `baseURL: 'http://localhost:3001'` — el frontend en Docker expone el puerto 3001 en el host para no colisionar con el dev server (3000).
- `retries: 0` — sin reintentos. Un fallo es señal real de drift, no flakiness.

---

## `docker-compose.integration.yml`

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: bioshield
      POSTGRES_PASSWORD: bioshield
      POSTGRES_DB: bioshield
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bioshield -d bioshield"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://bioshield:bioshield@postgres:5432/bioshield
      CHROMA_PERSIST_DIRECTORY: /data/chroma_db
      ENVIRONMENT: test
      RATE_LIMIT_ENABLED: "false"
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      AES_KEY: ${AES_KEY:-integration-test-key-32-bytes-ok}
    volumes:
      - ./tests/fixtures/chroma-seed:/data/chroma_db:ro
    depends_on:
      postgres:
        condition: service_healthy
    command: >
      sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 5s
      timeout: 3s
      retries: 15

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3001:3000"
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:3000 || exit 1"]
      interval: 5s
      timeout: 3s
      retries: 20

volumes: {}
```

**Variables de entorno requeridas en CI:**
- `GEMINI_API_KEY` — secret de GitHub Actions, solo usado en test #3.
- `AES_KEY` — tiene default seguro para integration; en producción viene de `.env`.

**`RATE_LIMIT_ENABLED: "false"`** — deshabilita slowapi en el entorno de test para que el setup pueda llamar `/auth/register` y `/auth/login` sin triggear el rate limiter.

**`NEXT_PUBLIC_API_URL` no se setea en `environment`** — las variables `NEXT_PUBLIC_*` de Next.js se inkean en el bundle en build-time, no en runtime. Setearlas en docker-compose no tiene efecto. El cliente usa el fallback `http://localhost:8000` del código fuente, que funciona correctamente porque el backend está mapeado al host en ese puerto. Si en el futuro se necesita customizar esta URL, agregar `ARG NEXT_PUBLIC_API_URL` al Dockerfile y pasarla via `build.args` en docker-compose.

---

## `frontend/Dockerfile`

Build de producción con output `standalone` de Next.js. Requiere `output: 'standalone'` en `next.config.ts`.

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

---

## CI workflow — `.github/workflows/playwright-integration.yml`

```yaml
name: E2E Integration (nightly)

on:
  schedule:
    - cron: '0 4 * * *'
  workflow_dispatch:

jobs:
  integration:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm

      - run: pnpm install --frozen-lockfile

      - run: pnpm playwright install chromium --with-deps

      - name: Run integration smoke tests
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: pnpm playwright test --project=integration-setup --project=integration --project=integration-teardown --workers=1

      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: integration-report
          path: playwright-report/
          retention-days: 7
```

**Decisiones:**
- Trigger: nightly (4am UTC) + `workflow_dispatch`. NO en cada PR — es lento y consume Gemini quota.
- Solo Chromium — los smoke tests son de contrato, no cross-browser.
- `timeout-minutes: 20` — cubre build Docker (~3-4 min) + test #3 con Gemini (~30-60s) con margen.
- Artefacto de reporte solo en `failure()`.

---

## Snapshot de ChromaDB — proceso de regeneración

Ver `tests/fixtures/chroma-seed/README.md` para instrucciones detalladas.

**Cuándo regenerar:**
- Al migrar el modelo de embeddings (cambio de dimensión invalida la colección).
- Al agregar ingredientes al fixture de Nutella en los tests.
- Al cambiar el schema de ChromaDB (colecciones, metadata fields).

**Proceso resumido:**
```bash
# 1. Levantar backend con ChromaDB vacía temporal
CHROMA_PERSIST_DIRECTORY=/tmp/chroma-seed-fresh \
  uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. Ejecutar script de ingesta de seed
python scripts/seed_chroma_integration.py --output /tmp/chroma-seed-fresh

# 3. Reemplazar snapshot en el repo
rm -rf tests/fixtures/chroma-seed/
cp -r /tmp/chroma-seed-fresh tests/fixtures/chroma-seed/

# 4. Commitear
git add tests/fixtures/chroma-seed/
git commit -m "chore(integration): regenerate chroma-seed snapshot"
```

El script `scripts/seed_chroma_integration.py` llama directamente al servicio de embeddings del backend (sin servidor HTTP) y recibe una lista fija de ingredientes de Nutella. Usa el modelo activo configurado en `.env`.

---

## Out of scope

- Tests de `/auth/refresh` — menor prioridad para smoke tests.
- Tests de `POST /scan/contribute` (OFF contribution) — flujo asíncrono con BackgroundTasks, requiere su propio plan.
- Tests de `DELETE /biosync/data` — operación destructiva, no aporta detección de drift de schema.
- Cross-browser (Firefox, WebKit) — los smoke tests son de contrato, no de compatibilidad.
- Paralelización de tests — los tests comparten estado del usuario; secuencial es correcto.
