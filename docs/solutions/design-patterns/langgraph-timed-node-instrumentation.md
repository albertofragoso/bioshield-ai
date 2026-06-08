---
title: "LangGraph Per-Node Latency Instrumentation with timed_node"
date: "2026-06-06"
category: design-patterns
module: "agents/scan-pipeline"
problem_type: design_pattern
component: assistant
severity: low
applies_when:
  - "Adding a new LangGraph node to the scan pipeline"
  - "Per-node latency visibility is needed without modifying node business logic"
  - "Feature-flagging instrumentation for prod vs dev environments"
tags:
  - langgraph
  - observability
  - structured-logging
  - async
  - feature-flag
  - ci-gate
related_components:
  - tooling
  - development_workflow
---

# LangGraph Per-Node Latency Instrumentation with timed_node

## Context

The BioShield scan pipeline has 8 LangGraph nodes (`identify_product`, `extract_ingredients`, `resolve_entities`, `search_regulatory`, `biosync`, `detect_conflicts`, `personalize`, `calculate_risk`) with no per-node observability. Only a final `scan_complete` event was logged. When a scan was slow, there was no way to tell which node was the bottleneck — Gemini Vision nodes? The ChromaDB search? The biosync join?

The fix: a `timed_node` wrapper in `backend/app/agents/timing.py` that emits structured `node_timing` logs (and `slow_node` WARNINGs) for every node, wired into `graph.py` at build time, gated by a CI test that prevents new nodes from silently skipping instrumentation.

## Guidance

**Wrapper signature:**

```python
def timed_node(name: str, fn: Callable, *, enabled: bool = True) -> Callable
```

- `name` — node name used in log `extra` dict (matches the string passed to `graph.add_node`)
- `fn` — the raw node callable (sync or async); `inspect.iscoroutinefunction` picks the right branch at wrap time
- `enabled` — feature flag; `False` returns `fn` unchanged, no sentinel set

**Core pattern (async branch — the non-obvious part):**

```python
@functools.wraps(fn)
async def async_wrapper(state):
    start = time.perf_counter()
    success = False
    try:
        result = await fn(state)
        success = True
        return result
    finally:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        # inner try/except: logger failures must not mask the original node exception
        try:
            logger.info("node_timing", extra={"node": name, "elapsed_ms": elapsed_ms})
            if success:
                threshold = SLOW_NODE_THRESHOLDS.get(name)
                if threshold is not None and elapsed_ms > threshold:
                    logger.warning("slow_node", extra={
                        "node": name, "elapsed_ms": elapsed_ms, "threshold_ms": threshold
                    })
        except Exception:
            pass

async_wrapper._is_timed = True
```

**Wiring in `graph.py`:**

```python
timing = settings.enable_node_timing  # read once at graph-build time

graph.add_node(
    "identify_product",
    timed_node("identify_product", make_identify_product_node(settings), enabled=timing),
)
# ... same pattern for all 8 nodes
```

**Feature flag in `config.py` (Pydantic Settings — never `os.getenv` directly):**

```python
enable_node_timing: bool = True  # env: ENABLE_NODE_TIMING — False disables without redeploy
```

**CI gate in `test_ci_gate.py`:**

```python
EXPECTED_NODE_NAMES = [
    "identify_product", "extract_ingredients", "resolve_entities",
    "search_regulatory", "biosync", "detect_conflicts", "personalize", "calculate_risk",
]

def test_all_nodes_are_timed():
    # Reverse check: no new nodes silently bypass the gate
    actual_nodes = [k for k in graph.nodes.keys() if k != "__start__"]
    assert set(actual_nodes) == set(EXPECTED_NODE_NAMES), (
        f"graph.nodes has changed — update EXPECTED_NODE_NAMES.\n"
        f"Actual: {sorted(actual_nodes)}\nExpected: {sorted(EXPECTED_NODE_NAMES)}"
    )
    for node_name in EXPECTED_NODE_NAMES:
        try:
            rc = graph.nodes[node_name].bound
            fn = rc.afunc if rc.afunc is not None else rc.func
        except AttributeError as exc:
            pytest.fail(f"LangGraph internal API changed: {exc}")
        assert fn is not None
        assert hasattr(fn, "_is_timed"), f"Node '{node_name}' is not wrapped with timed_node()"
```

**Per-node thresholds (`SLOW_NODE_THRESHOLDS`):**

```python
SLOW_NODE_THRESHOLDS: dict[str, int] = {
    "identify_product": 8000,    # Gemini Vision — placeholder, update from P95+20% baseline
    "extract_ingredients": 8000, # Gemini Vision — placeholder
    "resolve_entities": 2000,
    "search_regulatory": 2000,
    "biosync": 2000,
    "detect_conflicts": 2000,
    "personalize": 2000,
    "calculate_risk": 2000,
}
```

Values are placeholders. Must be updated to P95 + 20% from ≥20 representative scans before merging to prod.

## Why This Matters

**`finally` + `success` flag, not `except Exception: raise`**

`asyncio.CancelledError` is `BaseException` in Python 3.8+, not `Exception`. Using `except Exception: raise` to re-raise after logging means task cancellation silently skips the timing log — the `except` clause doesn't match `CancelledError`, and the logger never fires. The `finally` block always runs, ensuring timing is always logged. The `success = False` flag ensures `slow_node` WARNING only fires on the happy path (flagging a cancelled node as "slow" would be misleading).

**Inner `try/except Exception: pass` around logger calls**

If `logger.info()` itself raises (misconfigured handler, broken formatter), and you're already in a `finally` block unwinding an exception, the logging exception replaces the original node exception. The inner `try/except` swallows logger failures, preserving the original node exception for the caller. Verified by `test_timed_node_sync_exception_propagates`: `ValueError("sync-boom")` propagates unchanged even when the `finally` timing log fires.

**`_is_timed = True` sentinel, not `__wrapped__`**

`__wrapped__` is set by any `functools.wraps()` call — FastAPI dependencies, caching decorators, other middleware wrappers all set it. Using `hasattr(fn, "__wrapped__")` in the CI gate produces false positives: a node wrapped by an unrelated decorator passes the check even without timing. `_is_timed` is set exclusively by `timed_node`, making the CI gate precise.

**CI reverse-check (`set(actual_nodes) == set(EXPECTED_NODE_NAMES)`)**

A unidirectional check (`EXPECTED_NODE_NAMES ⊆ graph.nodes`) passes silently when a new node is added to the graph but not added to `EXPECTED_NODE_NAMES`. The bidirectional set equality forces the engineer to update the expected list, at which point the per-node `_is_timed` check catches any un-timed additions.

**`request_id` correlation — no `ScanState` modification needed**

`ScanState` has no `scan_id` or `request_id` field. The `request_id` appears automatically in every `node_timing` log because `RequestIDMiddleware` stores it in a `contextvars.ContextVar` that `JsonFormatter` reads on every log call. The wrapper emits only `node` + `elapsed_ms` in its `extra` dict; the formatter merges `request_id` from context automatically.

**LangGraph introspection path**

The CI gate reaches the wrapped callable via `graph.nodes[name].bound` → `RunnableCallable` → `.afunc` (async) or `.func` (sync). This is an internal LangGraph API verified against `langgraph==0.4.x`. The `try/except AttributeError: pytest.fail(...)` guard ensures a LangGraph upgrade that renames these attributes fails loudly rather than silently passing the check with a `None`.

## When to Apply

Use this pattern for any LangGraph pipeline where:

- Nodes call external services (LLMs, databases, vector stores) with variable latency
- You need to distinguish which node in a multi-step pipeline is slow under load
- You want alert-level signals (WARNING) when individual nodes exceed SLO thresholds
- The pipeline is long-running enough that cancellation (task timeout, HTTP disconnect) is realistic

Not needed for pipelines with a single node or where all nodes are synchronous CPU-bound operations with sub-millisecond variance.

## Examples

**Async node, happy path (from `test_timing.py`):**

```python
fn = _make_async_node({"product_name": "TestProd"})
wrapped = timed_node("identify_product", fn)

with patch("app.agents.timing.logger") as mock_logger:
    result = await wrapped({"barcode": "123"})

assert result["product_name"] == "TestProd"
mock_logger.info.assert_called_once()
extra = mock_logger.info.call_args[1]["extra"]
assert extra["node"] == "identify_product"
assert isinstance(extra["elapsed_ms"], float)
```

**Exception propagation — `finally` does not swallow the original:**

```python
def bad_node(state):
    raise ValueError("sync-boom")

wrapped = timed_node("bad_sync_node", bad_node)
with patch("app.agents.timing.logger") as mock_logger:
    with pytest.raises(ValueError, match="sync-boom"):
        wrapped({})
# logger.info still fires (finally ran); warning silent (success=False)
mock_logger.info.assert_called_once()
mock_logger.warning.assert_not_called()
```

**Disabled wrapper returns original function identity:**

```python
result = timed_node("identify_product", fn, enabled=False)
assert result is fn
assert not hasattr(result, "_is_timed")
```

**Slow-node warning with controlled clock (deterministic, no asyncio.sleep flakiness):**

```python
monkeypatch.setitem(timing_module.SLOW_NODE_THRESHOLDS, "search_regulatory", 1)

perf_values = iter([0.0, 0.010])  # 10ms elapsed
with patch("app.agents.timing.time") as mock_time, \
     patch("app.agents.timing.logger") as mock_logger:
    mock_time.perf_counter = lambda: next(perf_values)
    await wrapped({})

mock_logger.warning.assert_called_once()
assert mock_logger.warning.call_args[1]["extra"]["threshold_ms"] == 1
```

## Related

- `backend/app/agents/timing.py` — wrapper implementation
- `backend/app/agents/graph.py` — wiring at graph-build time
- `backend/app/config.py` — `enable_node_timing` Settings field (line 67)
- `backend/tests/test_timing.py` — unit test coverage (7 tests)
- `backend/tests/test_ci_gate.py` — `test_all_nodes_are_timed` CI gate
