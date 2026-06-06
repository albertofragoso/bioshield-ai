"""Unit tests for app.agents.timing — timed_node wrapper.

TDD RED phase: all tests fail until timing.py is implemented.
"""

from unittest.mock import patch

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_async_node(return_state: dict):
    """Returns a minimal async node callable."""

    async def node(state: dict) -> dict:
        return {**state, **return_state}

    node.__name__ = "test_async_node"
    return node


def _make_sync_node(return_state: dict):
    """Returns a minimal sync node callable."""

    def node(state: dict) -> dict:
        return {**state, **return_state}

    node.__name__ = "test_sync_node"
    return node


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


async def test_timed_node_async():
    """Async node: state returned correctly after wrap; logger.info fires."""
    from app.agents.timing import timed_node

    fn = _make_async_node({"product_name": "TestProd"})
    wrapped = timed_node("identify_product", fn)

    with patch("app.agents.timing.logger") as mock_logger:
        result = await wrapped({"barcode": "123"})

    assert result["product_name"] == "TestProd"
    assert result["barcode"] == "123"
    mock_logger.info.assert_called_once()
    call_kwargs = mock_logger.info.call_args
    assert call_kwargs[0][0] == "node_timing"
    extra = call_kwargs[1]["extra"]
    assert extra["node"] == "identify_product"
    assert isinstance(extra["elapsed_ms"], float)


async def test_timed_node_sync():
    """Sync node: state returned correctly after wrap; logger.info fires."""
    from app.agents.timing import timed_node

    fn = _make_sync_node({"resolved": []})
    wrapped = timed_node("resolve_entities", fn)

    with patch("app.agents.timing.logger") as mock_logger:
        result = wrapped({"barcode": "456"})

    assert result["resolved"] == []
    assert result["barcode"] == "456"
    mock_logger.info.assert_called_once()
    call_kwargs = mock_logger.info.call_args
    assert call_kwargs[0][0] == "node_timing"
    extra = call_kwargs[1]["extra"]
    assert extra["node"] == "resolve_entities"
    assert isinstance(extra["elapsed_ms"], float)


def test_timed_node_preserves_metadata():
    """Wrapper preserves __name__ and sets __wrapped__ via functools.wraps."""
    from app.agents.timing import timed_node

    fn = _make_async_node({})
    fn.__name__ = "identify_product"
    wrapped = timed_node("identify_product", fn)

    assert wrapped.__name__ == fn.__name__
    assert wrapped.__wrapped__ is fn


async def test_timed_node_slow_warning(monkeypatch):
    """When elapsed > threshold, logger.warning fires with node/elapsed_ms/threshold_ms."""
    from app.agents import timing as timing_module
    from app.agents.timing import timed_node

    monkeypatch.setitem(timing_module.SLOW_NODE_THRESHOLDS, "search_regulatory", 1)

    async def slow_node(state: dict) -> dict:
        import asyncio

        await asyncio.sleep(0.01)
        return state

    slow_node.__name__ = "search_regulatory"
    wrapped = timed_node("search_regulatory", slow_node)

    with patch("app.agents.timing.logger") as mock_logger:
        await wrapped({})

    mock_logger.warning.assert_called_once()
    warn_kwargs = mock_logger.warning.call_args
    assert warn_kwargs[0][0] == "slow_node"
    extra = warn_kwargs[1]["extra"]
    assert extra["node"] == "search_regulatory"
    assert extra["threshold_ms"] == 1
    assert extra["elapsed_ms"] > 1


async def test_timed_node_exception_propagates():
    """Exception propagates unchanged; logger.info still fires via finally."""
    from app.agents.timing import timed_node

    async def bad_node(state: dict) -> dict:
        raise RuntimeError("boom")

    bad_node.__name__ = "bad_node"
    wrapped = timed_node("bad_node", bad_node)

    with patch("app.agents.timing.logger") as mock_logger:
        with pytest.raises(RuntimeError, match="boom"):
            await wrapped({})

    mock_logger.info.assert_called_once()
    extra = mock_logger.info.call_args[1]["extra"]
    assert extra["node"] == "bad_node"
    # warning must NOT fire on exception path
    mock_logger.warning.assert_not_called()


def test_timed_node_disabled(monkeypatch):
    """ENABLE_NODE_TIMING=false returns the original fn without __wrapped__."""
    monkeypatch.setenv("ENABLE_NODE_TIMING", "false")

    # Re-import so the env var is re-evaluated on the call
    from app.agents.timing import timed_node

    fn = _make_sync_node({})
    result = timed_node("identify_product", fn)

    assert result is fn
    assert not hasattr(result, "__wrapped__")
