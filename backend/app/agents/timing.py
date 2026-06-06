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
import os
import time
from typing import Callable

logger = logging.getLogger(__name__)

# Threshold per node in milliseconds.
# Update from baseline before merge — see module docstring.
SLOW_NODE_THRESHOLDS: dict[str, int] = {
    "identify_product": 8000,     # Gemini Vision
    "extract_ingredients": 8000,  # Gemini Vision
    "resolve_entities": 2000,
    "search_regulatory": 2000,
    "biosync": 2000,
    "detect_conflicts": 2000,
    "personalize": 2000,
    "calculate_risk": 2000,
}


def timed_node(name: str, fn: Callable) -> Callable:
    """Wrap a LangGraph node callable with wall-clock timing.

    In async context, elapsed includes event-loop yield time from other
    concurrent tasks — it is not pure CPU or I/O time for this node alone.
    """
    if os.getenv("ENABLE_NODE_TIMING", "true") != "true":
        return fn

    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(state):
            start = time.perf_counter()
            try:
                result = await fn(state)
                elapsed = time.perf_counter() - start
                elapsed_ms = round(elapsed * 1000, 1)
                logger.info("node_timing", extra={"node": name, "elapsed_ms": elapsed_ms})
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
                return result
            except Exception:
                elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
                logger.info("node_timing", extra={"node": name, "elapsed_ms": elapsed_ms})
                raise

        return async_wrapper

    else:

        @functools.wraps(fn)
        def sync_wrapper(state):
            start = time.perf_counter()
            try:
                result = fn(state)
                elapsed = time.perf_counter() - start
                elapsed_ms = round(elapsed * 1000, 1)
                logger.info("node_timing", extra={"node": name, "elapsed_ms": elapsed_ms})
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
                return result
            except Exception:
                elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
                logger.info("node_timing", extra={"node": name, "elapsed_ms": elapsed_ms})
                raise

        return sync_wrapper
