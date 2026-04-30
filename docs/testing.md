# Testing — BioShield AI

Pirámide de testing del proyecto. Cada nivel tiene un propósito; los niveles
NO se duplican entre sí.

```
┌─────────────────────────────────────────────────────────────┐
│ 3. Frontend E2E — integration (real backend) [futuro]      │
│    tests/specs-integration/ · ~5 smoke tests · nightly      │
├─────────────────────────────────────────────────────────────┤
│ 2. Frontend E2E — mock backend [implementado]              │
│    tests/specs/ · ~50 tests · cada PR                       │
├─────────────────────────────────────────────────────────────┤
│ 1. Backend unit + integration [implementado]               │
│    backend/tests/ · pytest + httpx ASGI · cada PR           │
└─────────────────────────────────────────────────────────────┘
```

## Nivel 1 — Backend (`backend/tests/`)

- **Stack:** pytest, httpx `AsyncClient(ASGITransport)`, SQLite in-memory.
- **Cubre:** lógica de negocio, schemas Pydantic, endpoints REST,
  RAG retrieval, biomarker analysis, OFF integration.
- **Convención:** factories como dict-builders (ver
  `backend/tests/test_biosync.py`).
- **CI:** corre en cada PR/push.

## Nivel 2 — Frontend E2E mock (`tests/specs/`)

- **Stack:** Playwright + TypeScript + `page.route()` para mockear el backend.
- **Cubre:** flujos de usuario UI (auth, scan, biosync, dashboard, history),
  estados de error/loading, accesibilidad básica (ARIA labels), persistencia
  vía cookies, refresh interceptor.
- **NO cubre:** lógica de negocio (eso es Nivel 1), interacción real con
  Gemini, persistencia real en Postgres, performance.
- **Factories:** `tests/fixtures/factories.ts` espeja
  `frontend/lib/api/types.ts` con defaults deterministas + `Partial<T>` overrides.
- **Selectores:** roles ARIA + texto en español (sin `data-testid`).
- **CI:** corre en cada PR/push (`.github/workflows/playwright.yml`).
- **Detalles operativos:** ver `tests/README.md`.

## Nivel 3 — Frontend E2E integration (`tests/specs-integration/`) [no implementado]

Smoke tests del happy path con backend real (Docker compose). Sirven para
detectar drift entre el contrato mockeado y el backend real (cambios de
schema, regresiones de OpenAPI, etc.).

**Decisiones ya tomadas (para el plan futuro):**

- **Carpeta:** `tests/specs-integration/` en root del repo (mismo Playwright
  binary, distinta carpeta).
- **Estructura:** un único subdirectorio `smoke/` con ~5 tests:
  1. Login real → token JWT real → cookie persistida.
  2. Scan barcode Nutella real → ChromaDB → semaphore.
  3. Upload PDF real → Gemini extract → review.
  4. Cache hit en backend (segunda llamada al mismo barcode).
  5. Logout real → cookies revocadas.
- **`playwright.config.ts`:** agregar `projects` separados con `testMatch`
  filtrando por carpeta. `globalSetup` que levanta `docker compose up` y
  espera health check.
- **Workflow CI:** archivo nuevo `.github/workflows/playwright-integration.yml`
  con `services: postgres`, secret `GEMINI_API_KEY`, trigger `schedule`
  (nightly) + `workflow_dispatch`. NO en cada PR (es lento y consume Gemini quota).
- **Datos de prueba:** seed via endpoint backend `/test/seed` (a crear) o
  via fixture SQL aplicado en `globalSetup`. NO usar el mismo Postgres que
  desarrollo.
- **Cleanup:** `globalTeardown` que tira `docker compose down -v`.
- **Quién lo escribe:** plan separado, cuando se decida que vale la pena
  el costo operativo (mantener docker-compose verde + secret de Gemini en CI).

## Out of scope del frontend E2E — planes futuros

Las siguientes áreas NO están cubiertas por `tests/specs/` y deben tener su
propio plan cuando se prioricen.

### Accesibilidad automatizada (axe-core)

**Qué falta:** assertions automatizadas de WCAG AA via `@axe-core/playwright`.
La suite actual valida ARIA labels específicos (ej. `aria-label="Semáforo: ..."`)
pero no escanea la página completa por violaciones de contraste, headings,
landmarks, etc.

**Por qué su propio plan:** axe-core puede generar muchos falsos positivos
en un design tokenizado como BioShield (animaciones, hex-grid, scanlines).
Requiere triage caso a caso y posiblemente una whitelist por componente.

**Estimación de scope:** instalar `@axe-core/playwright`, configurar reglas
por página, escribir 1 spec `tests/specs/a11y/axe.spec.ts` con un test por
ruta. ~1 día.

### Tests con cámara real / ZXing

**Qué falta:** validar el flujo `<BarcodeScanner>` con `<video>` y la
detección real vía `@zxing/browser`. La suite actual usa solo el input manual
de barcode, que es un fallback legítimo del producto, pero el camino primario
queda sin cobertura.

**Por qué su propio plan:** requiere device emulation o stub de
`navigator.mediaDevices.getUserMedia` con un MediaStream sintético que
contenga un barcode renderizable. Es frágil y específico por browser
(WebKit difiere de Chromium). Probablemente solo valga para Chromium.

**Estimación de scope:** investigar `page.context().grantPermissions(['camera'])`
+ crear un MediaStream stub que reproduzca un PNG con barcode + verificar
que ZXing dispara `onDetect`. ~2 días, alto riesgo de inestabilidad.

### Refactor a `data-testid`

**Qué falta:** la suite actual depende de texto en español
(`getByText("Confirmar y guardar")`). Si la copia cambia, los tests rompen.

**Por qué su propio plan:** introducir `data-testid` es un cambio masivo en
componentes (no en tests). La política de cuándo agregar testids debe
acordarse con el equipo (¿solo en CTAs? ¿en todos los inputs? ¿con prefijo
de feature?). Mientras tanto, los selectores actuales son legibles y
documentan el comportamiento esperado del producto.

**Estimación de scope:** definir convención (ej. `data-testid="biosync-confirm-cta"`),
agregar a ~30 elementos críticos, refactorizar selectores en tests existentes.
~1 día.

### Performance / load testing

**Qué falta:** medir First Contentful Paint, Time to Interactive, bundle size
budget, regresiones de Lighthouse. Detectar lentitud en `/scan/[id]` cuando
hay muchos `personalized_insights` o ingredientes largos.

**Por qué su propio plan:** Playwright no es la herramienta correcta. Necesita
Lighthouse CI o k6. Scope distinto al del E2E funcional.

**Estimación de scope:** integrar `@lhci/cli` en GitHub Actions con
budgets en `lighthouserc.json`. ~0.5 días.

### Visual regression (screenshots)

**Qué falta:** detectar regresiones visuales (mal alineamiento de glow del
semáforo, scanlines descolocadas, fuente caída). El producto BioShield es
muy dependiente de tokens visuales (dark + brand palette + animations).

**Por qué su propio plan:** requiere snapshot baseline + revisión visual
manual cuando rompe. Decisiones de tooling (Playwright `toHaveScreenshot`
vs Chromatic vs Percy) tienen implicaciones de costo y workflow.

**Estimación de scope:** elegir herramienta, generar baseline en CI,
documentar workflow de aprobación de cambios visuales. ~1 día.

### Multi-idioma

**Qué falta:** la app es solo español hoy. Cuando se agregue i18n,
los selectores basados en texto romperán. Habrá que migrar a testids o
parametrizar las strings esperadas por locale.

**Por qué su propio plan:** depende de cuándo y cómo se introduzca i18n
(library, fallback locale, persistencia de preferencia). Decisión de producto.

## Cuándo crear un plan nuevo de testing

Si vas a agregar un nivel completo (ej. visual regression) o un área nueva
(ej. mobile native), crea un plan en `docs/superpowers/plans/` siguiendo el
formato del plan que generó esta documentación. Reusa los factories y mocks
existentes; no dupliques `tests/fixtures/factories.ts`.

Si vas a agregar un test individual a una suite existente, NO necesitas plan —
agrega el test al spec correspondiente y abre PR.
