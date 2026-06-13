"""Per-node latency instrumentation for the LangGraph scan pipeline.

Wraps node callables with timing that emits structured logs.
request_id correlation is auto-included by RequestIDMiddleware via JsonFormatter.

Baseline requirement: SLOW_NODE_THRESHOLDS values must be updated from a run
of >=20 representative scans at P95 + 20% BEFORE merging to main.
Placeholder values: Gemini Vision nodes -> 8000ms, rest -> 2000ms.
Baseline date: pending.
"""

from __future__ import annotations

import functools
import inspect
import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Threshold per node in milliseconds.
# Update from baseline before merge — see module docstring.
SLOW_NODE_THRESHOLDS: dict[str, int] = {
    "identify_product": 8000,  # Gemini Vision
    "extract_ingredients": 8000,  # Gemini Vision
    "resolve_entities": 2000,
    "search_regulatory": 2000,
    "biosync": 2000,
    "detect_conflicts": 2000,
    "personalize": 2000,
    "calculate_risk": 2000,
}


def timed_node(name: str, fn: Callable, *, enabled: bool = True) -> Callable:
    """Wrap a LangGraph node callable with wall-clock timing.

    In async context, elapsed includes event-loop yield time from other
    concurrent tasks — it is not pure CPU or I/O time for this node alone.

    Pass enabled=False (from Settings.enable_node_timing) to skip wrapping
    without a redeploy.
    """
    if not enabled:
        return fn

    if inspect.iscoroutinefunction(fn):

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
                try:
                    logger.info("node_timing", extra={"node": name, "elapsed_ms": elapsed_ms})
                    if success:
                        threshold = SLOW_NODE_THRESHOLDS.get(name)
                        if threshold is not None and elapsed_ms > threshold:
                            logger.warning(
                                "slow_node",
                                extra={
                                    "node": name,
                                    "elapsed_ms": elapsed_ms,
                                    "threshold_ms": threshold,
                                },
                            )
                except Exception:
                    pass

        setattr(async_wrapper, "_is_timed", True)
        return async_wrapper

    else:

        @functools.wraps(fn)
        def sync_wrapper(state):
            start = time.perf_counter()
            success = False
            try:
                result = fn(state)
                success = True
                return result
            finally:
                elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
                try:
                    logger.info("node_timing", extra={"node": name, "elapsed_ms": elapsed_ms})
                    if success:
                        threshold = SLOW_NODE_THRESHOLDS.get(name)
                        if threshold is not None and elapsed_ms > threshold:
                            logger.warning(
                                "slow_node",
                                extra={
                                    "node": name,
                                    "elapsed_ms": elapsed_ms,
                                    "threshold_ms": threshold,
                                },
                            )
                except Exception:
                    pass

        setattr(sync_wrapper, "_is_timed", True)
        return sync_wrapper
