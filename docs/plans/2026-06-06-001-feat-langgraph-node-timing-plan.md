---
title: "LangGraph Per-Node Latency Instrumentation"
status: completed
date: 2026-06-06
shipped: 2026-06-06
branch: feat/langgraph-node-timing
origin: docs/brainstorms/2026-06-06-langgraph-node-latency-metrics-requirements.md
---

# LangGraph Per-Node Latency Instrumentation

## Problem Frame

El pipeline de scan corre 8 nodos LangGraph sin data de latencia por nodo. Cuando un scan
es lento, no hay forma de saber si el bottleneck es `search_regulatory` (ChromaDB + RAG),
`extract_ingredients` (Gemini Vision), o cualquier otro nodo sin agregar instrumentación
manual y re-correr. Solo existe el evento final `semaphore` con `scan_complete`.

## Scope

**In:** `timing.py` (nuevo) · `graph.py` (modificar) · `test_timing.py` (nuevo) · `test_ci_gate.py` (modificar)

**Out:** DB persistence · SSE timing events · Prometheus/OpenTelemetry · log sampling

`nodes.py`, `scan.py`, `state.py`, `config.py` — no se modifican.

---

## Key Technical Decisions

### 1. Correlation via `RequestIDMiddleware` ContextVar, no state

El requirements doc original especifica `state.get("scan_id")` como campo de correlación,
pero `ScanState` no tiene campo `scan_id`. El proyecto ya tiene `RequestIDMiddleware` con
`REQUEST_ID_VAR: ContextVar[str]` que `JsonFormatter` auto-incluye en todos los logs como
`request_id`. La correlación ya existe — `timed_node` no necesita extraer nada del state.

**Consecuencia:** `extra` dict en logs lleva solo `node` y `elapsed_ms`. El `request_id`
llega automáticamente por el formatter. No se modifica `ScanState`. (see origin: docs/brainstorms/2026-06-06-langgraph-node-latency-metrics-requirements.md)

### 2. Async/sync branching obligatorio en `timed_node`

Todos los 8 nodos del pipeline son `async def`. Pero `timed_node` debe soportar callables
sync para no romperse si se añade un nodo sync futuro o en tests. Usar
`inspect.iscoroutinefunction(fn)` para branching — ambas ramas presentes.

### 3. `@functools.wraps(fn)` en ambas ramas

`functools.wraps` preserva `__name__`, `__annotations__`, y setea `__wrapped__ = fn`
automáticamente (Python 3.2+). El CI gate usa `hasattr(fn, "__wrapped__")` para verificar
instrumentación. LangGraph usa `__name__` para labeling interno — sin `wraps` el grafo
ve todos los nodos como `async_wrapper`.

### 4. Feature flag sin code deploy

`os.getenv("ENABLE_NODE_TIMING", "true")` — si no es `"true"`, retornar `fn` sin wrap.
Excepción: `ENABLE_NODE_TIMING=false` en `.env` deshabilita sin redeploy.

**Nota:** El CLAUDE.md del backend prohíbe leer `os.environ` directamente. La feature flag
es la única excepción aceptable aquí porque config.py/Settings no permite valores de
runtime post-startup sin redeploy — que es precisamente lo que queremos evitar.

### 5. CI gate runtime (no AST)

El gate existente en `test_ci_gate.py` usa AST parsing puro (zero app imports). El nuevo
gate `test_all_nodes_are_timed` requiere ejecutar `build_scan_graph()` con mocks para
inspeccionar los nodos compilados. Coexistirá con el gate AST existente — misma clase,
nuevo método. Requiere fixtures de `conftest.py`.

---

## Implementation Units

### U1 — `backend/app/agents/timing.py` (nuevo)

**TDD posture: escribir U2 primero (RED), luego implementar (GREEN).**

Exporta:
- `SLOW_NODE_THRESHOLDS: dict[str, int]` — threshold por nodo en ms.
  Placeholders hasta baseline: `extract_ingredients` y `identify_product` (Gemini Vision)
  → 8000ms, resto → 2000ms. Baseline ≥20 scans representativos a P95+20% requerido antes
  del merge. Documentar baseline y fecha en comentario inline junto al dict.
- `timed_node(name: str, fn: Callable) -> Callable`

Contrato de `timed_node`:
1. Feature flag check al inicio — si `ENABLE_NODE_TIMING != "true"`, retorna `fn` original.
2. `inspect.iscoroutinefunction(fn)` → define `async_wrapper` o `sync_wrapper`.
3. `@functools.wraps(fn)` en ambas ramas.
4. `time.perf_counter()` antes/después de `await fn(state)` / `fn(state)`.
   Mide wall-clock del callable incluyendo I/O. En async incluye event loop yield time
   de otras tareas concurrentes — documentar en comentario inline.
5. `finally`: emitir `logger.info("node_timing", extra={"node": name, "elapsed_ms": ...})`.
   La excepción propaga sin tocar.
6. Happy path (no excepción): si `elapsed_ms > threshold`, emitir `logger.warning("slow_node",
   extra={"node": name, "elapsed_ms": ..., "threshold_ms": threshold})`.

Log format exacto:
```python
logger.info("node_timing", extra={"node": name, "elapsed_ms": round(elapsed * 1000, 1)})
logger.warning("slow_node", extra={"node": name, "elapsed_ms": round(elapsed * 1000, 1), "threshold_ms": threshold})
```

**Tests:** `backend/tests/test_timing.py`

**Patterns existentes a seguir:**
- Logger: `logger = logging.getLogger(__name__)` — mismo patrón que `nodes.py:37`
- `extra={}` structured logging — ya usado en `nodes.py:141`
- `functools.wraps` — patrón estándar Python; no hay ejemplo previo en el proyecto

---

### U2 — `backend/tests/test_timing.py` (nuevo)

**TDD posture: escribir ANTES de implementar `timing.py` (RED → GREEN).**

| Test | Qué verifica |
|------|-------------|
| `test_timed_node_async` | Nodo async: state retornado correctamente post-wrap; `logger.info` llamado con campos `node` y `elapsed_ms` |
| `test_timed_node_sync` | Nodo sync: idem |
| `test_timed_node_preserves_metadata` | `wrapper.__name__ == fn.__name__`; `wrapper.__wrapped__ is fn` |
| `test_timed_node_slow_warning` | Monkeypatch `SLOW_NODE_THRESHOLDS["test_node"] = 1`; verifica `logger.warning` llamado con campos `node`, `elapsed_ms`, `threshold_ms` |
| `test_timed_node_exception_propagates` | Nodo que lanza `RuntimeError`; excepción propaga; `logger.info` en `finally` sí se llama |
| `test_timed_node_disabled` | `ENABLE_NODE_TIMING=false` vía `monkeypatch.setenv`; retorna `fn` original (sin `__wrapped__`) |

Fixtures a usar: `monkeypatch` (stdlib pytest). No requiere `db_session` ni `client`.
Logging mock: `unittest.mock.patch` sobre `app.agents.timing.logger`.

---

### U3 — `backend/app/agents/graph.py` (modificar)

Agregar import de `timed_node` desde `app.agents.timing`. Wrappear los 8 `add_node` calls:

```python
# Directional sketch — not implementation spec
graph.add_node("identify_product", timed_node("identify_product", make_identify_product_node(settings)))
graph.add_node("extract_ingredients", timed_node("extract_ingredients", make_extract_ingredients_node(settings)))
# ... idem los 8 nodos
```

`needs_image_extraction` (router condicional) — NO wrappear. Es función sync pura, no nodo
del pipeline LangGraph.

**Depends on:** U1 green (timing.py implementado).

---

### U4 — `backend/tests/test_ci_gate.py` (modificar)

Agregar `test_all_nodes_are_timed` que:
1. Construye el grafo completo via `build_scan_graph(db=mock_db, settings=mock_settings)`.
2. Itera `EXPECTED_NODE_NAMES` (lista explícita de los 8 nodos).
3. Para cada nodo: `fn = graph.nodes[node_name]["action"]`; `assert hasattr(fn, "__wrapped__")`.

`EXPECTED_NODE_NAMES` hardcodeado — agregar nodo sin actualizar la lista falla CI.

**Implementación:** Requiere mocks de `Session` y `Settings`. Usar fixtures existentes de
`conftest.py` (`db_session`, `override_settings`) o crear mocks inline con `MagicMock`.

**Depends on:** U1 + U3 green.

---

## Sequencing (Vertical Slices)

```
Slice 1 — timing utility (TDD)
  U2: test_timing.py  →  RED  (tests fallan — timing.py no existe)
  U1: timing.py       →  GREEN (6 tests pasan)

Slice 2 — pipeline wiring
  U3: graph.py        →  wrap 8 nodos (depends: Slice 1 green)
  U4: test_ci_gate.py →  CI gate (depends: Slice 1 + U3 green)
```

U2 antes de U1 es el orden de ejecución TDD. U3 y U4 son independientes entre sí pero
ambos dependen de Slice 1.

---

## Risk Register

| Riesgo | Prob | Impacto | Mitigation |
|--------|------|---------|-----------|
| Baseline run no ocurre antes del merge | Alta | Medio | Bloquear merge con checklist en PR: "baseline ≥20 scans con P95 documentado en `SLOW_NODE_THRESHOLDS`" |
| `graph.nodes[node]["action"]` no expone el callable wrapeado en LangGraph | Media | Alto | Verificar con `build_scan_graph()` + `print(graph.nodes)` en dev antes de escribir U4 |
| `functools.wraps` no setea `__wrapped__` en Python < 3.2 (project usa 3.11+) | Baja | Bajo | `python --version` en CI — project requiere 3.11+ |
| `ENABLE_NODE_TIMING` leída via `os.getenv` viola CLAUDE.md "nunca leer os.environ directamente" | Baja | Bajo | Excepción documentada en plan (ver decisión #4); config.py no soporta hot-reload |
| Alert fatiga si todos los nodos son "lentos" por thresholds mal calibrados | Alta | Medio | Thresholds placeholder con baseline obligatorio antes del merge |

---

## Test Scenarios (Verification)

1. `pytest backend/tests/test_timing.py` — 6 tests green
2. `pytest backend/tests/test_ci_gate.py::test_all_nodes_are_timed` — green
3. `pytest backend/` completo — sin regresiones
4. Backend corriendo: POST `/scan/barcode` → 8 líneas `node_timing` en logs con `node` y
   `elapsed_ms`; campo `request_id` auto-incluido por JsonFormatter
5. `ENABLE_NODE_TIMING=false` en env → cero timing logs en POST `/scan/barcode`
6. Simular nodo lento (monkeypatch threshold a 1ms en dev) → `slow_node` WARNING en logs

---

## Open Questions (no bloqueantes)

- **¿Quién recibe las alerts de `slow_node`?** El WARNING existe pero sin receptor nombrado
  (Slack channel, alert rule) los thresholds son operativamente inútiles. Definir receptor
  antes de considerar el feature completo.
- **¿Hay un scan lento específico que motivó esto?** Si sí, usarlo para calibrar thresholds
  en lugar de P95 genérico.

---

## Implementation Deviations (post-ship)

Las siguientes decisiones difieren del plan original. Documentadas para que el plan
refleje el código real en `feat/langgraph-node-timing`.

### Feature flag: `Settings.enable_node_timing`, no `os.getenv`

**Plan:** `os.getenv("ENABLE_NODE_TIMING", "true")` leído dentro de `timed_node`.
**Implementación:** `enable_node_timing: bool = True` en `app/config.py` (Pydantic Settings),
pasado como `enabled=settings.enable_node_timing` a `build_scan_graph()` y luego a cada
`timed_node(..., enabled=timing)`. Esto cumple la invariante global "nunca leer `os.environ`
directamente". El plan marcaba esto como excepción aceptable; la implementación encontró
la solución correcta: delegar a Settings. **`config.py` SÍ se modificó** (el plan decía que no).

### CI gate sentinel: `_is_timed`, no `__wrapped__`

**Plan:** `assert hasattr(fn, "__wrapped__")`.
**Implementación:** `assert hasattr(fn, "_is_timed")`. Motivo: `__wrapped__` lo setea cualquier
`functools.wraps()` — FastAPI deps, caching decorators, otros middlewares. `_is_timed = True`
es exclusivo de `timed_node`, haciendo el gate preciso y sin falsos positivos.

### Introspection path: `.bound.afunc/.func`, no `["action"]`

**Plan:** `fn = graph.nodes[node_name]["action"]`.
**Implementación:** `rc = graph.nodes[node_name].bound` → `fn = rc.afunc if rc.afunc is not None else rc.func`.
La API interna de LangGraph (0.4.x) expone el callable via `RunnableCallable.bound`, no
`["action"]`. El gate tiene `try/except AttributeError: pytest.fail(...)` para detectar
rápidamente si la API cambia en futuros upgrades.

### Tests: 7, no 6

Se agregó `test_timed_node_sync_exception_propagates` (sync path, excepción + finally).
El plan listaba 6 tests; la implementación añadió uno extra para cubrir simétricamente
el path sync (el plan solo cubría async para exception propagation).

### Bidirectional CI reverse-check

El plan solo verificaba `EXPECTED_NODE_NAMES ⊆ graph.nodes`. La implementación usa
`set(actual_nodes) == set(EXPECTED_NODE_NAMES)` — bidireccional. Impide que nodos nuevos
en el grafo pasen sin actualizar la lista esperada.
