# E2E Integration Tests Nivel 3 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Nivel 3 smoke test suite that runs a full Docker stack (postgres + backend + frontend) and validates the real API contracts against the 6 agreed endpoints.

**Architecture:** Three Playwright projects (`integration-setup`, `integration`, `integration-teardown`) chained via `dependencies`/`teardown`. Setup spins up `docker-compose.integration.yml`, seeds a test user via real API calls, and saves storageState cookies. Teardown runs `docker compose down -v`. ChromaDB is pre-seeded from a versioned snapshot in `tests/fixtures/chroma-seed/`.

**Tech Stack:** Playwright (TypeScript), Docker Compose, Next.js standalone build, FastAPI, ChromaDB, Python asyncio (seed script).

**Spec:** `docs/superpowers/specs/2026-04-30-e2e-integration-nivel3-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/next.config.ts` | Modify | Enable `output: 'standalone'` for Docker build |
| `.gitignore` | Modify | Ignore runtime auth state file |
| `frontend/Dockerfile` | Create | Production Next.js build (standalone) |
| `docker-compose.integration.yml` | Create | Full stack: postgres + backend + frontend |
| `playwright.config.ts` | Modify | Add 3 integration projects |
| `tests/specs-integration/smoke/integration-global-setup.ts` | Create | Playwright test: docker up + seed user |
| `tests/specs-integration/smoke/integration-global-teardown.ts` | Create | Playwright test: docker down -v |
| `tests/specs-integration/smoke/smoke.spec.ts` | Create | 6 smoke tests |
| `scripts/seed_chroma_integration.py` | Create | Generate ChromaDB snapshot with Nutella ingredients |
| `scripts/create_biosync_pdf.py` | Create | Generate minimal lab report PDF fixture |
| `tests/fixtures/chroma-seed/` | Generate | Run seed script once; commit output |
| `tests/fixtures/biosync-test.pdf` | Generate | Run PDF script once; commit output |
| `tests/fixtures/chroma-seed/README.md` | Create | Snapshot regeneration instructions |
| `.github/workflows/playwright-integration.yml` | Create | Nightly CI workflow |

---

## Task 1: Config foundations

**Files:**
- Modify: `frontend/next.config.ts`
- Modify: `.gitignore`

- [ ] **Step 1.1: Add `output: 'standalone'` to next.config.ts**

```typescript
// frontend/next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
```

- [ ] **Step 1.2: Add integration-auth.json to .gitignore**

Append to `.gitignore`:
```
# Integration test runtime auth state
tests/fixtures/integration-auth.json
```

- [ ] **Step 1.3: Verify**

```bash
grep "standalone" frontend/next.config.ts
grep "integration-auth" .gitignore
```

Expected output: one line each confirming both entries are present.

- [ ] **Step 1.4: Commit**

```bash
git add frontend/next.config.ts .gitignore
git commit -m "chore(integration): enable Next.js standalone output + gitignore auth state"
```

---

## Task 2: Frontend Dockerfile

**Files:**
- Create: `frontend/Dockerfile`

- [ ] **Step 2.1: Create the Dockerfile**

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:20-alpine AS builder
WORKDIR /app
RUN corepack enable
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

- [ ] **Step 2.2: Verify the build locally**

```bash
docker build ./frontend -f frontend/Dockerfile -t bioshield-frontend-test --no-cache
```

Expected: build completes successfully through all 3 stages (`deps`, `builder`, `runner`). The `standalone` output must exist: the builder stage should produce `.next/standalone/server.js`.

If the build fails at `pnpm build` with a missing env var, check `frontend/.env.local` — `NEXT_PUBLIC_*` vars needed at build time must be present there or passed as `--build-arg`.

- [ ] **Step 2.3: Commit**

```bash
git add frontend/Dockerfile
git commit -m "feat(integration): add frontend production Dockerfile"
```

---

## Task 3: docker-compose.integration.yml

**Files:**
- Create: `docker-compose.integration.yml`

- [ ] **Step 3.1: Create the file**

```yaml
# docker-compose.integration.yml
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
      JWT_SECRET: integration-test-jwt-secret-2026
      USE_LOCAL_EMBEDDINGS: "false"
      DEBUG: "true"
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

- [ ] **Step 3.2: Validate config syntax**

```bash
docker compose -f docker-compose.integration.yml config --quiet
```

Expected: exits 0 with no errors. The `--quiet` flag suppresses the full config dump.

- [ ] **Step 3.3: Commit**

```bash
git add docker-compose.integration.yml
git commit -m "feat(integration): add docker-compose.integration.yml for E2E stack"
```

---

## Task 4: Playwright config — add integration projects

**Files:**
- Modify: `playwright.config.ts`

- [ ] **Step 4.1: Add the three integration projects**

The current `playwright.config.ts` has a `projects` array with `chromium` and `firefox`. Add these three entries at the end of the array:

```typescript
// playwright.config.ts — add inside the projects array, after the firefox entry
{
  name: 'integration-setup',
  testMatch: /integration-global-setup\.ts/,
},
{
  name: 'integration',
  dependencies: ['integration-setup'],
  teardown: 'integration-teardown',
  testMatch: /specs-integration\/smoke\/smoke\.spec\.ts/,
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

- [ ] **Step 4.2: Verify the projects are recognized**

```bash
pnpm playwright --list --project=integration 2>&1 | head -20
```

Expected: the command lists `smoke.spec.ts` tests (6 items once the file is created). If the file doesn't exist yet, it will print an empty list or an error about no tests found — that's acceptable at this stage.

- [ ] **Step 4.3: Commit**

```bash
git add playwright.config.ts
git commit -m "feat(integration): add playwright integration projects (setup/integration/teardown)"
```

---

## Task 5: Global setup test

**Files:**
- Create: `tests/specs-integration/smoke/integration-global-setup.ts`

- [ ] **Step 5.1: Create the directory**

```bash
mkdir -p tests/specs-integration/smoke
```

- [ ] **Step 5.2: Create the setup test file**

```typescript
// tests/specs-integration/smoke/integration-global-setup.ts
import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

const BACKEND = 'http://localhost:8000';
const AUTH_FILE = 'tests/fixtures/integration-auth.json';
const TEST_EMAIL = 'integration-test@bioshield.test';
const TEST_PASSWORD = 'Integration!2026';

test('setup: start docker stack and seed test user', async ({ browser }) => {
  // 1. Start the full Docker stack
  execSync(
    'docker compose -f docker-compose.integration.yml up -d --wait',
    { stdio: 'inherit', timeout: 180_000 },
  );

  // 2. Wait for backend health (alembic migrations may add latency after --wait)
  await waitForBackend(BACKEND + '/health');

  // 3. Create browser context for cookie-aware API calls
  const context = await browser.newContext();

  // 4. Register test user (409 = already exists from a partial run — that's fine)
  const registerRes = await context.request.post(BACKEND + '/auth/register', {
    data: { email: TEST_EMAIL, password: TEST_PASSWORD },
  });
  expect([201, 409]).toContain(registerRes.status());

  // 5. Login and capture cookies
  const loginRes = await context.request.post(BACKEND + '/auth/login', {
    data: { email: TEST_EMAIL, password: TEST_PASSWORD },
  });
  expect(loginRes.status()).toBe(200);

  // 6. Save storageState (cookies) for smoke tests
  await context.storageState({ path: AUTH_FILE });
  await context.close();
});

async function waitForBackend(url: string, retries = 24, intervalMs = 3_000): Promise<void> {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`Backend at ${url} did not become healthy after ${retries} retries`);
}
```

- [ ] **Step 5.3: Verify the file is picked up by the setup project**

```bash
pnpm playwright --list --project=integration-setup
```

Expected: outputs one test: `setup: start docker stack and seed test user`.

- [ ] **Step 5.4: Commit**

```bash
git add tests/specs-integration/smoke/integration-global-setup.ts
git commit -m "feat(integration): add global setup — docker up + seed test user"
```

---

## Task 6: Global teardown test

**Files:**
- Create: `tests/specs-integration/smoke/integration-global-teardown.ts`

- [ ] **Step 6.1: Create the teardown test file**

```typescript
// tests/specs-integration/smoke/integration-global-teardown.ts
import { test } from '@playwright/test';
import { execSync } from 'child_process';

test('teardown: stop docker stack and remove volumes', async () => {
  execSync(
    'docker compose -f docker-compose.integration.yml down -v',
    { stdio: 'inherit', timeout: 60_000 },
  );
});
```

- [ ] **Step 6.2: Verify**

```bash
pnpm playwright --list --project=integration-teardown
```

Expected: one test listed: `teardown: stop docker stack and remove volumes`.

- [ ] **Step 6.3: Commit**

```bash
git add tests/specs-integration/smoke/integration-global-teardown.ts
git commit -m "feat(integration): add global teardown — docker down -v"
```

---

## Task 7: Smoke tests

**Files:**
- Create: `tests/specs-integration/smoke/smoke.spec.ts`

- [ ] **Step 7.1: Create the smoke test file**

```typescript
// tests/specs-integration/smoke/smoke.spec.ts
import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const BACKEND = 'http://localhost:8000';
const NUTELLA_BARCODE = '3017624010701';
const VALID_SEMAPHORES = ['RED', 'ORANGE', 'YELLOW', 'GRAY'];

// All requests use context.request to inherit the storageState cookies
// from tests/fixtures/integration-auth.json (set in playwright.config.ts)

test('1 — auth state is valid', async ({ context }) => {
  const res = await context.request.get(`${BACKEND}/scan/ping`);
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body).toHaveProperty('user_id');
  expect(typeof body.user_id).toBe('string');
});

test('2 — scan barcode Nutella → semáforo válido', async ({ context }) => {
  const res = await context.request.post(`${BACKEND}/scan/barcode`, {
    data: { barcode: NUTELLA_BARCODE },
  });
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(VALID_SEMAPHORES).toContain(body.semaphore);
  expect(body.product_name).toBeTruthy();
  expect(Array.isArray(body.ingredients)).toBe(true);
  expect(body.ingredients.length).toBeGreaterThan(0);
  expect(body.product_barcode).toBe(NUTELLA_BARCODE);
});

test('3 — biosync: extract → upload → status', async ({ context }) => {
  const pdfPath = path.join(process.cwd(), 'tests/fixtures/biosync-test.pdf');
  const pdfBuffer = fs.readFileSync(pdfPath);

  // 3a. Extract biomarkers from PDF
  const extractRes = await context.request.post(`${BACKEND}/biosync/extract`, {
    multipart: {
      file: {
        name: 'biosync-test.pdf',
        mimeType: 'application/pdf',
        buffer: pdfBuffer,
      },
    },
  });
  expect(extractRes.status()).toBe(200);
  const extracted = await extractRes.json();
  expect(Array.isArray(extracted.biomarkers)).toBe(true);
  expect(extracted.biomarkers.length).toBeGreaterThan(0);

  // 3b. Upload (persist with AES-256 encryption)
  const uploadRes = await context.request.post(`${BACKEND}/biosync/upload`, {
    data: { biomarkers: extracted.biomarkers },
  });
  expect(uploadRes.status()).toBe(201);
  const uploaded = await uploadRes.json();
  expect(uploaded.has_data).toBe(true);

  // 3c. Status confirms persistence
  const statusRes = await context.request.get(`${BACKEND}/biosync/status`);
  expect(statusRes.status()).toBe(200);
  const status = await statusRes.json();
  expect(status.has_data).toBe(true);
  expect(new Date(status.expires_at).getTime()).toBeGreaterThan(Date.now());
});

test('4 — resultado guardado del scan', async ({ context }) => {
  const res = await context.request.get(`${BACKEND}/scan/result/${NUTELLA_BARCODE}`);
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.product_barcode).toBe(NUTELLA_BARCODE);
  expect(VALID_SEMAPHORES).toContain(body.semaphore);
  expect(Array.isArray(body.ingredients)).toBe(true);
});

test('5 — historial de scans', async ({ context }) => {
  const res = await context.request.get(`${BACKEND}/scan/history`);
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(Array.isArray(body)).toBe(true);
  expect(body.length).toBeGreaterThan(0);
  const nutellaEntry = body.find(
    (e: { product_barcode: string }) => e.product_barcode === NUTELLA_BARCODE,
  );
  expect(nutellaEntry).toBeDefined();
  expect(VALID_SEMAPHORES).toContain(nutellaEntry.semaphore);
});

test('6 — logout revoca la sesión', async ({ context }) => {
  // Logout
  const logoutRes = await context.request.post(`${BACKEND}/auth/logout`);
  expect(logoutRes.status()).toBe(204);

  // Any auth-required endpoint must now return 401
  const verifyRes = await context.request.get(`${BACKEND}/scan/ping`);
  expect(verifyRes.status()).toBe(401);
});
```

- [ ] **Step 7.2: Verify the tests are listed**

```bash
pnpm playwright --list --project=integration
```

Expected: 6 tests listed (`1 — auth state is valid`, `2 — scan barcode Nutella…`, etc.).

- [ ] **Step 7.3: Commit**

```bash
git add tests/specs-integration/smoke/smoke.spec.ts
git commit -m "feat(integration): add 6 smoke tests (auth, scan, biosync, history, logout)"
```

---

## Task 8: ChromaDB seed snapshot

**Files:**
- Create: `scripts/seed_chroma_integration.py`
- Create: `tests/fixtures/chroma-seed/README.md`
- Generate: `tests/fixtures/chroma-seed/` (run script once)

- [ ] **Step 8.1: Create the seed script**

```python
#!/usr/bin/env python3
"""Generate ChromaDB seed snapshot for E2E integration tests.

Usage (from repo root):
    python scripts/seed_chroma_integration.py --output tests/fixtures/chroma-seed

Reads embedding settings from backend/.env. Requires GEMINI_API_KEY if
USE_LOCAL_EMBEDDINGS=false (the default). Set USE_LOCAL_EMBEDDINGS=true
to use BGE-M3 local model instead (needs sentence-transformers installed).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _ROOT / "backend"
sys.path.insert(0, str(_BACKEND))
os.chdir(_BACKEND)  # pydantic-settings reads env_file=".env" relative to cwd

from app.config import Settings  # noqa: E402
from app.services.embeddings import embed_text  # noqa: E402
from app.services.rag import (  # noqa: E402
    build_embedding_template,
    get_collection,
    upsert_record,
)

NUTELLA_INGREDIENTS: list[dict] = [
    {
        "entity_id": "CAS:57-50-1",
        "canonical_name": "Sugar",
        "fda_status": "GRAS",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "High glycemic index; excessive consumption linked to metabolic disorders",
        "usage_limits": "No regulatory limit",
        "e_number": "",
        "severity": "LOW",
        "conflict_flag": False,
    },
    {
        "entity_id": "CAS:57-10-3",
        "canonical_name": "Palm Oil",
        "fda_status": "APPROVED",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "High saturated fat (50%); GE and 3-MCPD contaminants flagged by EFSA at industrial refining temperatures",
        "usage_limits": "No regulatory limit; EFSA recommends minimizing GE exposure",
        "e_number": "",
        "severity": "MEDIUM",
        "conflict_flag": True,
    },
    {
        "entity_id": "CAS:84012-22-6",
        "canonical_name": "Hazelnuts",
        "fda_status": "GRAS",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "Tree nut allergen (FDA Top 9 allergens); no chemical safety concerns",
        "usage_limits": "N/A",
        "e_number": "",
        "severity": "LOW",
        "conflict_flag": False,
    },
    {
        "entity_id": "CAS:8002-31-1",
        "canonical_name": "Cocoa",
        "fda_status": "GRAS",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "May contain cadmium at elevated levels depending on geographic origin",
        "usage_limits": "Cadmium limit: 0.3 mg/kg (EU Reg 2019/1870) for cocoa powder",
        "e_number": "",
        "severity": "LOW",
        "conflict_flag": False,
    },
    {
        "entity_id": "CAS:8056-51-7",
        "canonical_name": "Skimmed Milk Powder",
        "fda_status": "GRAS",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "Milk allergen (FDA Top 9); no chemical safety concerns",
        "usage_limits": "N/A",
        "e_number": "",
        "severity": None,
        "conflict_flag": False,
    },
    {
        "entity_id": "CAS:8013-17-0",
        "canonical_name": "Whey Powder",
        "fda_status": "GRAS",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "Milk allergen; no chemical safety concerns",
        "usage_limits": "N/A",
        "e_number": "",
        "severity": None,
        "conflict_flag": False,
    },
    {
        "entity_id": "CAS:8002-43-5",
        "canonical_name": "Soy Lecithin",
        "fda_status": "GRAS",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "Soy allergen; generally well-tolerated in highly refined form",
        "usage_limits": "quantum satis (EU Regulation)",
        "e_number": "E322",
        "severity": None,
        "conflict_flag": False,
    },
    {
        "entity_id": "CAS:121-33-5",
        "canonical_name": "Vanillin",
        "fda_status": "GRAS",
        "efsa_status": "APPROVED",
        "codex_status": "APPROVED",
        "hazard_note": "No significant hazard at food-use concentrations",
        "usage_limits": "N/A",
        "e_number": "",
        "severity": None,
        "conflict_flag": False,
    },
]


async def main(output_dir: str) -> None:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    settings = Settings(chroma_persist_directory=str(out))
    collection = get_collection(settings)

    print(f"Seeding {len(NUTELLA_INGREDIENTS)} Nutella ingredients → {out}")
    print(f"Embedding model: {'BGE-M3 local' if settings.use_local_embeddings else settings.gemini_embedding_model}\n")

    for ing in NUTELLA_INGREDIENTS:
        template = build_embedding_template(
            entity_id=ing["entity_id"],
            canonical_name=ing["canonical_name"],
            fda_status=ing["fda_status"],
            efsa_status=ing["efsa_status"],
            codex_status=ing["codex_status"],
            hazard_note=ing["hazard_note"],
            usage_limits=ing["usage_limits"],
        )
        embedding = await embed_text(template, settings)
        upsert_record(
            collection,
            entity_id=ing["entity_id"],
            template_text=template,
            embedding=embedding,
            metadata={
                "entity_id": ing["entity_id"],
                "canonical_name": ing["canonical_name"],
                "e_number": ing["e_number"],
                "region": "GLOBAL",
                "source": "INTEGRATION_SEED",
                "conflict_flag": ing["conflict_flag"],
                "severity": ing["severity"] or "",
                "data_version": "2026.04.30",
            },
        )
        print(f"  ✓ {ing['canonical_name']} ({ing['entity_id']})")

    print(f"\nDone — {collection.count()} records in collection '{settings.chroma_collection_name}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", required=True, help="ChromaDB persist directory (will be created)")
    args = parser.parse_args()
    asyncio.run(main(args.output))
```

- [ ] **Step 8.2: Run the seed script to generate the snapshot**

Ensure `GEMINI_API_KEY` is set in `backend/.env` (or `USE_LOCAL_EMBEDDINGS=true` if BGE-M3 is installed). Then from the repo root:

```bash
python scripts/seed_chroma_integration.py --output tests/fixtures/chroma-seed
```

Expected output:
```
Seeding 8 Nutella ingredients → .../tests/fixtures/chroma-seed
Embedding model: models/gemini-embedding-001

  ✓ Sugar (CAS:57-50-1)
  ✓ Palm Oil (CAS:57-10-3)
  ...
  ✓ Vanillin (CAS:121-33-5)

Done — 8 records in collection 'bioshield_ingredients'
```

- [ ] **Step 8.3: Verify the snapshot was created**

```bash
ls tests/fixtures/chroma-seed/
```

Expected: a ChromaDB directory structure (typically `chroma.sqlite3` and a UUID-named subdirectory).

- [ ] **Step 8.4: Create the snapshot README**

```markdown
<!-- tests/fixtures/chroma-seed/README.md -->
# ChromaDB Integration Test Snapshot

Minimal ChromaDB collection with 8 Nutella ingredient embeddings.
Used by `docker-compose.integration.yml` (mounted read-only at `/data/chroma_db`).

## When to regenerate

- You change the embedding model (`USE_LOCAL_EMBEDDINGS`, `GEMINI_EMBEDDING_MODEL`, or `BGE_MODEL_NAME`).
  Changing models changes vector dimensions — the old collection becomes incompatible.
  See also: `docs/embedding-strategy.md` §1.
- You add ingredients to `NUTELLA_INGREDIENTS` in `scripts/seed_chroma_integration.py`.
- ChromaDB upgrades its on-disk format.

## How to regenerate

From the repo root (requires `GEMINI_API_KEY` in `backend/.env`, or set `USE_LOCAL_EMBEDDINGS=true`):

```bash
rm -rf tests/fixtures/chroma-seed
python scripts/seed_chroma_integration.py --output tests/fixtures/chroma-seed
git add tests/fixtures/chroma-seed
git commit -m "chore(integration): regenerate chroma-seed snapshot"
```

The script reads embedding settings from `backend/.env` and uses the active model.
Switch models by changing `USE_LOCAL_EMBEDDINGS` in `backend/.env` before running.
```

- [ ] **Step 8.5: Commit**

```bash
git add scripts/seed_chroma_integration.py tests/fixtures/chroma-seed/ tests/fixtures/chroma-seed/README.md
git commit -m "feat(integration): add chroma-seed snapshot + seed script for Nutella ingredients"
```

---

## Task 9: biosync PDF fixture

**Files:**
- Create: `scripts/create_biosync_pdf.py`
- Generate: `tests/fixtures/biosync-test.pdf`

- [ ] **Step 9.1: Create the PDF generation script**

```python
#!/usr/bin/env python3
"""Generate a minimal valid 1-page PDF with fake lab values for biosync E2E tests.

Usage (from repo root):
    python scripts/create_biosync_pdf.py

Output: tests/fixtures/biosync-test.pdf
"""
from pathlib import Path


def _fmt_offset(n: int) -> bytes:
    return f"{n:010d} 00000 n \n".encode()


def create_biosync_pdf(output_path: Path) -> None:
    """Create a valid PDF-1.4 with a synthetic lab report page."""

    stream_content = (
        b"BT\n"
        b"/F1 14 Tf\n"
        b"50 750 Td\n"
        b"(RESULTADOS DE LABORATORIO CLINICO) Tj\n"
        b"0 -25 Td\n"
        b"(Paciente: Usuario Prueba    Fecha: 2026-04-30) Tj\n"
        b"0 -35 Td\n"
        b"(QUIMICA SANGUINEA) Tj\n"
        b"0 -20 Td\n"
        b"(Glucosa en ayunas:    95 mg/dL     Referencia: 70 - 100 mg/dL) Tj\n"
        b"0 -18 Td\n"
        b"(Colesterol total:   185 mg/dL     Referencia: < 200 mg/dL) Tj\n"
        b"0 -18 Td\n"
        b"(HDL Colesterol:      55 mg/dL     Referencia: > 40 mg/dL) Tj\n"
        b"0 -18 Td\n"
        b"(LDL Colesterol:     110 mg/dL     Referencia: < 130 mg/dL) Tj\n"
        b"0 -18 Td\n"
        b"(Trigliceridos:      120 mg/dL     Referencia: < 150 mg/dL) Tj\n"
        b"0 -18 Td\n"
        b"(Hemoglobina:         14.2 g/dL    Referencia: 12.0 - 16.0 g/dL) Tj\n"
        b"ET\n"
    )

    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
        b"endobj\n"
    )
    obj4 = (
        b"4 0 obj\n<< /Length "
        + str(len(stream_content)).encode()
        + b" >>\nstream\n"
        + stream_content
        + b"endstream\nendobj\n"
    )
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"

    header = b"%PDF-1.4\n"
    off1 = len(header)
    off2 = off1 + len(obj1)
    off3 = off2 + len(obj2)
    off4 = off3 + len(obj3)
    off5 = off4 + len(obj4)
    xref_start = off5 + len(obj5)

    xref = (
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        + _fmt_offset(off1)
        + _fmt_offset(off2)
        + _fmt_offset(off3)
        + _fmt_offset(off4)
        + _fmt_offset(off5)
    )
    trailer = (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(xref_start).encode()
        + b"\n%%EOF\n"
    )

    pdf_bytes = header + obj1 + obj2 + obj3 + obj4 + obj5 + xref + trailer
    output_path.write_bytes(pdf_bytes)
    print(f"Created {output_path} ({len(pdf_bytes)} bytes)")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "biosync-test.pdf"
    create_biosync_pdf(out)
```

- [ ] **Step 9.2: Generate the PDF fixture**

```bash
python scripts/create_biosync_pdf.py
```

Expected:
```
Created .../tests/fixtures/biosync-test.pdf (XXXX bytes)
```

- [ ] **Step 9.3: Verify it is a valid PDF**

```bash
python -c "
data = open('tests/fixtures/biosync-test.pdf', 'rb').read()
assert data[:4] == b'%PDF', 'not a PDF'
assert b'%%EOF' in data, 'missing EOF marker'
print('valid PDF,', len(data), 'bytes')
"
```

Expected: `valid PDF, <N> bytes`.

- [ ] **Step 9.4: Commit**

```bash
git add scripts/create_biosync_pdf.py tests/fixtures/biosync-test.pdf
git commit -m "feat(integration): add biosync PDF fixture and generation script"
```

---

## Task 10: CI workflow

**Files:**
- Create: `.github/workflows/playwright-integration.yml`

- [ ] **Step 10.1: Create the workflow file**

```yaml
# .github/workflows/playwright-integration.yml
name: E2E Integration (nightly)

on:
  schedule:
    - cron: '0 4 * * *'    # 4am UTC daily
  workflow_dispatch:         # manual trigger from GitHub Actions UI

jobs:
  integration:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Install Playwright Chromium
        run: pnpm playwright install chromium --with-deps

      - name: Run integration smoke tests
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: pnpm playwright test --project=integration-setup --project=integration --project=integration-teardown --workers=1

      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: integration-report-${{ github.run_id }}
          path: playwright-report/
          retention-days: 7
```

- [ ] **Step 10.2: Validate YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/playwright-integration.yml'))" && echo "valid YAML"
```

Expected: `valid YAML`.

- [ ] **Step 10.3: Commit**

```bash
git add .github/workflows/playwright-integration.yml
git commit -m "feat(integration): add nightly E2E integration CI workflow"
```

---

## Task 11: End-to-end validation

This task runs the full suite locally to confirm all pieces work together before opening a PR.

**Prerequisites:**
- Docker daemon running
- `GEMINI_API_KEY` set in `backend/.env`
- `tests/fixtures/chroma-seed/` exists (Task 8)
- `tests/fixtures/biosync-test.pdf` exists (Task 9)

- [ ] **Step 11.1: Run the full integration suite**

```bash
pnpm playwright test \
  --project=integration-setup \
  --project=integration \
  --project=integration-teardown \
  --workers=1
```

Expected:
```
Running 8 tests using 1 worker

  ✓  [integration-setup] › integration-global-setup.ts › setup: start docker stack and seed test user
  ✓  [integration] › smoke.spec.ts › 1 — auth state is valid
  ✓  [integration] › smoke.spec.ts › 2 — scan barcode Nutella → semáforo válido
  ✓  [integration] › smoke.spec.ts › 3 — biosync: extract → upload → status
  ✓  [integration] › smoke.spec.ts › 4 — resultado guardado del scan
  ✓  [integration] › smoke.spec.ts › 5 — historial de scans
  ✓  [integration] › smoke.spec.ts › 6 — logout revoca la sesión
  ✓  [integration-teardown] › integration-global-teardown.ts › teardown: stop docker stack and remove volumes

  8 passed (Xm)
```

- [ ] **Step 11.2: Confirm Docker is cleaned up**

```bash
docker compose -f docker-compose.integration.yml ps 2>&1
```

Expected: `no such service` or empty output — teardown removes all containers.

- [ ] **Step 11.3: Confirm auth state file is gitignored**

```bash
git status tests/fixtures/integration-auth.json
```

Expected: `nothing to commit` or the file does not appear in git status (it is gitignored).

- [ ] **Step 11.4: Final commit if any loose files**

```bash
git status
# If clean, nothing to do. If there are untracked changes, stage and commit them.
git add -p
git commit -m "chore(integration): fix post-run cleanup"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** `output: standalone` (Task 1), Dockerfile (Task 2), docker-compose (Task 3), playwright projects (Task 4), global-setup (Task 5), global-teardown (Task 6), 6 smoke tests (Task 7), chroma-seed (Task 8), biosync PDF (Task 9), CI workflow (Task 10). All spec sections covered.
- [x] **No placeholders:** All steps contain complete code. No TBDs.
- [x] **Type consistency:** `VALID_SEMAPHORES`, `BACKEND`, `NUTELLA_BARCODE` constants defined once and reused. `context.request` used throughout smoke tests (not mixed with `request` fixture). `integration-auth.json` path matches between setup and playwright.config.ts.
- [x] **`pnpm/action-setup@v4`** added to CI — the existing `ci.yml` does not install pnpm, but that workflow uses `pip`. The integration workflow needs pnpm explicitly.
- [x] **ChromaDB read-only volume** — the backend container mounts `./tests/fixtures/chroma-seed:/data/chroma_db:ro`. The `_client_for()` function uses `@lru_cache` keyed by persist_directory, so the read-only mount works correctly (ChromaDB reads at query time, no writes needed for smoke tests).
