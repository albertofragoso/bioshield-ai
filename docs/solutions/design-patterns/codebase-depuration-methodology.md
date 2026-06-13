---
title: "Evidence-Based Codebase Depuration Methodology"
date: "2026-06-12"
category: design-patterns
module: "cleanup/depuration"
problem_type: methodology
component: codebase
severity: low
applies_when:
  - "Removing dead code, unused imports, or duplicate logic from any FastAPI/Next.js project"
  - "Starting a cleanup sprint that must not break existing flows"
  - "Evaluating whether a symbol is safe to delete"
tags:
  - dead-code
  - near-duplicates
  - false-positives
  - deduplication
  - code-quality
---

## Problema

Los scanners de dead code (grafos, linters) generan falsos positivos en proyectos que usan
frameworks de registro dinámico (FastAPI, LangGraph, pytest, Next.js). Borrar por `callers=0`
sin verificación manual rompe middleware, auth, health checks y dependencias invisibles al grafo.

## Metodología — 5 fases

### Principios transversales

1. **Grafo descubre, grep verifica** — el grafo de código (code-review-graph) mapea
   candidatos eficientemente, pero es ciego a referencias por string/dinámicas. Antes de borrar:
   grep de string-references + `callers_of` / `imports_of` / `tests_for` en el grafo.
2. **Gate cuantitativo, no booleano** — "CI verde" solo prueba lo cubierto. El gate real es
   cobertura numérica (`--cov-fail-under=<baseline>`). No borrar símbolos cuyas líneas estén en
   `--cov-report term-missing` (sin cobertura = sin evidencia de protección).
3. **Evidence-based** — ningún borrado sin verificar contra la taxonomía de falsos positivos.
4. **Grafo fresco por fase** — cada commit muta el grafo; refrescar con
   `build_or_update_graph_tool` (incremental) antes de cada fase.
5. **Staged + reversible** — feature branch, commit atómico por categoría, `git tag cleanup-cat-N`
   por fase para revert quirúrgico.

### Fase 0 — Baseline verde + medición

```bash
cd backend && source .venv/bin/activate
pytest --cov=app --cov-report=term-missing   # registrar % como --cov-fail-under
curl -s localhost:8000/openapi.json > /tmp/openapi_baseline.json
cd ../frontend && pnpm build && pnpm lint
cd .. && pnpm playwright test
```

Si algo está rojo de entrada: detener. No se miden regresiones contra un baseline roto.

### Fase 1 — Dead code verificado

1. `refactor_tool mode=dead_code` → candidatos
2. Filtrar con la taxonomía de falsos positivos (ver sección abajo)
3. Verificar supervivientes: `callers_of` + `imports_of` + grep de string-refs + cobertura
4. Borrar solo confirmados. Gate verde. Commit.

### Fase 2 — Imports y componentes sin usar

- Backend: imports muertos en módulos no-entry-point
- Frontend: componentes sin referencia JSX, exports de barrel sin consumidor

Verificar import dinámico (`import(...)`) antes de borrar. Gate verde. Commit.

### Fase 3 — Duplicados exactos

Misma firma + mismo body → borrar una copia, actualizar todos los import sites.
Borrado puro: no cambia comportamiento. Gate verde. Commit.

### Fase 4 — Near-duplicates (mayor riesgo)

**Única categoría que altera comportamiento.** Para cada par casi-duplicado:

1. Identificar el edge case divergente (en qué difieren las dos implementaciones)
2. Añadir test que cubra ese edge **antes** de consolidar
3. Si no se puede caracterizar la divergencia → NO consolidar
4. Destino de funciones puras compartidas: `app/core/` (backend CLAUDE.md §C1)

Ejemplo aplicado en BioShield: `_seconds_until_midnight_utc` existía en
`middleware/rate_limit.py` y `dependencies/token_budget.py` — idéntica lógica, sin edge case
divergente. Movida a `app/core/time_utils.py`. Test actualizado en `test_error_schema.py`.

### Fase 5 — Documentación

- Documento de metodología en `docs/solutions/design-patterns/` (este archivo)
- Actualizar `docs/architecture.md` si cambió estructura de directorios
- Anotar hotspots diferidos (archivos gigantes) para pasada futura "agresiva"

---

## Taxonomía de falsos positivos

**Filtro obligatorio antes de borrar cualquier símbolo con `callers=0`.**

Esta lista es un allowlist de exclusión, no una prueba de completitud. Ante la duda: NO borrar.

| Patrón | Ejemplos | Por qué el grafo lo ve como "dead" |
|--------|----------|------------------------------------|
| **FastAPI decorators** | `@app.get`, `@router.post`, `@app.middleware`, `@app.exception_handler` | Registrados en el router, no llamados por nombre |
| **FastAPI Depends closures** | `_dep` dentro de `token_budget()`, `Depends(get_current_user)` | El closure lo invoca FastAPI en runtime |
| **LangGraph nodos** | `add_node("name", fn)` en `graph.py` | Referencia por string, no por call |
| **pytest fixtures/hooks** | fixtures en `conftest.py`, `pytest_configure` | pytest los descubre por nombre |
| **Pydantic validators** | `@field_validator`, `@model_validator` | Invocados por el metaclass |
| **SQLAlchemy event listeners** | `@event.listens_for` | Registrados en event bus |
| **Next.js file conventions** | `page.tsx`, `layout.tsx`, `route.ts`, `loading.tsx` | Next.js usa la ruta de archivo |
| **Next.js dynamic imports** | `import("./Component")` | Resuelto en runtime |
| **Barrel file exports** | re-exports en `index.ts` | El consumidor importa del barrel |
| **Contratos serializados** | deserializers Fernet, schemas en JWT/DB | Nombre vive en dato persistido |
| **Entry points** | `pyproject.toml` entry points, `__init_subclass__` | Registro implícito Python |

---

## Candidatos diferidos (no consolidados en esta pasada)

### Frontend mock architecture (fixtures.ts vs api-mocks.ts)

**Situación:** Dos archivos implementan mocks de Playwright con nombres similares
(`mockBiosyncStatus`, `mockScanHistory`, etc.) pero arquitecturas distintas:

- `tests/fixtures/fixtures.ts` — usa `mockOverrides: Record<string, Handler>`, un dict compartido
  que permite actualizar handlers mid-test (e.g., cambiar el status de biosync después de la carga
  inicial). Importado por la mayoría de los specs.
- `tests/fixtures/api-mocks.ts` — usa `page.route()` directo + mecanismo LIFO nativo de Playwright.
  Tiene `applyDefaultMocks` exportado. Usado por specs de foto y alternativas.

**Por qué NO se consolidó:** El mecanismo `mockOverrides` de `fixtures.ts` es una abstracción
arquitectural real (no solo syntactic sugar) — permite que los specs actualicen handlers sin
re-registrar rutas. Migrar requeriría refactorizar los 13 spec files y sus call sites. Es un
refactor de comportamiento, no una deduplicación.

**Acción recomendada:** Al iniciar una migración futura, estandarizar hacia `api-mocks.ts` con
`applyDefaultMocks` + overrides explícitos vía `page.route` LIFO. Crear un ADR antes de ejecutar.

### Hotspots de tamaño (fuera de alcance de pasada moderada)

Archivos con alta complejidad ciclomática candidatos a descomposición en una pasada futura "agresiva":

| Archivo | Razón |
|---------|-------|
| `frontend/app/(app)/scan/[id]/page.tsx` | UI monolítica con múltiples responsabilidades |
| `backend/app/routers/scan.py` | Router con lógica de negocio inline |
| `backend/app/services/gemini.py` | Cliente LLM con múltiples responsabilidades |

Descomposición = cambio de comportamiento observable → requiere pasada dedicada con tests de
integración cubriendo cada responsabilidad antes de separar.
