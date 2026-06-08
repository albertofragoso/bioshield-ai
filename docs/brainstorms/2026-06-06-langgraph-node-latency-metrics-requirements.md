# LangGraph Node Latency Metrics — Requirements

**Date:** 2026-06-06
**Status:** Shipped — `feat/langgraph-node-timing` (2026-06-06)
**Plan:** `docs/plans/2026-06-06-001-feat-langgraph-node-timing-plan.md`
**Solution doc:** `docs/solutions/design-patterns/langgraph-timed-node-instrumentation.md`

> ⚠️ Este documento refleja los **requisitos originales**. El plan anota las deviaciones
> de implementación. Ver plan para el estado real del código.

---

## Context

El pipeline de scan corre 8 nodos LangGraph sin ningún dato de latencia por nodo. Solo existe el evento final `semaphore` (SSE `scan_complete`). Diagnosticar slowdowns requiere adivinar cuál nodo es el cuello de botella — deuda técnica conocida.

---

## Problem

No existe data de latencia por nodo en el pipeline. Cuando un scan es lento, no hay forma de saber si el bottleneck es `search_regulatory` (ChromaDB + RAG), `extract_ingredients` (Gemini Vision), o cualquier otro nodo sin agregar `time.perf_counter()` manualmente y re-correr.

---

## Outcome

- Cada scan emite un log `INFO` por nodo con `elapsed_ms` y `scan_id` (correlation field)
- Nodos que superan su threshold emiten un `WARNING` adicional
- Un developer puede filtrar logs por `scan_id` y ver qué nodo fue lento en ese scan específico, sin modificar código ni re-correr
- Un CI gate previene que nuevos nodos se agreguen a `graph.py` sin instrumentación

---

## Scope

### In scope
- `app/agents/timing.py` (nuevo): `SLOW_NODE_THRESHOLDS` + `timed_node(name, fn)`
- `app/agents/graph.py` (modificar): 8 `add_node` calls wrapped con `timed_node`
- `backend/tests/test_timing.py` (nuevo): 6 unit tests
- `backend/tests/test_ci_gate.py` (modificar): gate de cobertura

### Out of scope
- Persistir timings en `ScanHistory` DB (sin migración)
- SSE events de timing al frontend
- Prometheus / Grafana / OpenTelemetry
- Log sampling o rate-limiting

---

## Requirements

### `app/agents/timing.py` (nuevo)

**`SLOW_NODE_THRESHOLDS: dict[str, int]`** — threshold por nodo en ms. Valores derivados de un baseline run de ≥20 scans representativos a P95 + 20% **antes del merge**. Baseline y fecha documentados en comentario inline. Hasta tener baseline, placeholders: nodos Gemini Vision → 8000ms, resto → 2000ms.

**`timed_node(name: str, fn: Callable) -> Callable`** — wraps cualquier callable de nodo con timing:

1. **Async/sync branching obligatorio**: detectar con `inspect.iscoroutinefunction(fn)`. Definir `async def async_wrapper` para nodos async, `def sync_wrapper` para sync. Ambas ramas presentes.

2. **`@functools.wraps(fn)` en ambas ramas**: preserva `__name__`, `__wrapped__`, `__annotations__` para que LangGraph introspection no se rompa.

3. **Feature flag**: si `os.getenv("ENABLE_NODE_TIMING", "true") != "true"`, retorna `fn` sin wrap. Sin code deploy para deshabilitar.

4. **Correlation field**: `state.get("scan_id")` como campo `extra` en cada log call. Si ausente, `None`.

5. **Exception path**: `finally` loguea timing incluso cuando el nodo lanza. La excepción propaga sin tocar. `WARNING slow_node` solo en happy path — no loguear performance data en el error path.

6. **Timing scope**: `time.perf_counter()` antes/después de `await fn(state)` / `fn(state)`. Mide wall-clock del callable interno incluyendo I/O awaited dentro de él. En un event loop async, incluye event loop yield time de otras tareas concurrentes — documentar esto en comentario inline.

**Log format** (structured `extra={}`, no f-string interpolation):
```python
logger.info(
    "node_timing",
    extra={"node": name, "elapsed_ms": round(elapsed * 1000, 1), "scan_id": scan_id}
)
logger.warning(
    "slow_node",
    extra={"node": name, "elapsed_ms": round(elapsed * 1000, 1), "threshold_ms": threshold, "scan_id": scan_id}
)
```

---

### `app/agents/graph.py` (modificar)

Todos los 8 `add_node` calls wrapped:
```python
graph.add_node("resolve_entities", timed_node("resolve_entities", make_resolve_entities_node(db)))
```

El router condicional `needs_image_extraction` no se wrappea — es función sync pura, no nodo del pipeline.

---

### `backend/tests/test_timing.py` (nuevo)

| Test | Qué verifica |
|------|-------------|
| `test_timed_node_async` | Nodo async: state muta correctamente post-wrap, timing fires |
| `test_timed_node_sync` | Nodo sync: idem |
| `test_timed_node_preserves_metadata` | `wrapper.__name__ == fn.__name__`; `wrapper.__wrapped__ is fn` |
| `test_timed_node_slow_warning` | Monkeypatch threshold → 1ms; verifica `logger.warning` con campos correctos |
| `test_timed_node_exception_propagates` | Excepción propaga; `finally` timing log fires |
| `test_timed_node_disabled` | `ENABLE_NODE_TIMING=false` → retorna `fn` original sin wrap |

---

### `backend/tests/test_ci_gate.py` (modificar)

Agregar gate que compila el grafo completo y verifica que cada nodo tiene el wrapper:
```python
def test_all_nodes_are_timed():
    graph = build_scan_graph(db=mock_db, settings=mock_settings)
    for node_name in EXPECTED_NODE_NAMES:
        fn = graph.nodes[node_name]["action"]
        assert hasattr(fn, "__wrapped__"), f"{node_name} missing timed_node wrapper"
```

`EXPECTED_NODE_NAMES` lista los 8 nodos — agregar un nodo sin actualizar la lista falla CI.

---

## Files to modify

| File | Change |
|------|--------|
| `backend/app/agents/timing.py` | **Nuevo** — `SLOW_NODE_THRESHOLDS`, `timed_node` |
| `backend/app/agents/graph.py` | Wrap 8 `add_node` calls; import `timed_node` |
| `backend/tests/test_timing.py` | **Nuevo** — 6 unit tests |
| `backend/tests/test_ci_gate.py` | Agregar `test_all_nodes_are_timed` |

`nodes.py`, `scan.py`, `state.py`, `config.py` — no se modifican.

---

## Open Questions (proceso — no bloqueantes para implementación)

- **¿Quién es dueño de las alerts?** El sistema de `WARNING` necesita un receptor nombrado (persona, Slack channel, alert rule) para que los thresholds sean significativos.
- **¿Hay un scan lento específico que motivó esto?** Si sí, usarlo para calibrar los thresholds en lugar de P95 genérico.

---

## Verification

1. `pytest backend/tests/test_timing.py` — 6 tests green
2. `pytest backend/tests/test_ci_gate.py::test_all_nodes_are_timed` — green
3. Backend corriendo: POST `/scan/barcode` → 8 líneas `node_timing` con `scan_id` en logs
4. `ENABLE_NODE_TIMING=false` → cero timing logs
5. `pytest backend/` completo green
