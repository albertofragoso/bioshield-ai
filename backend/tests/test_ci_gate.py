"""CI gates:
1. Every router function calling Gemini must declare token_budget dependency.
2. Every LangGraph pipeline node must be wrapped with timed_node.
"""

import ast
import pathlib

ROUTER_DIR = pathlib.Path(__file__).parent.parent / "app" / "routers"

# Functions/names whose presence in a router endpoint body signals a Gemini call.
# Intentionally precise: only the actual call-sites used in the codebase.
# - build_scan_graph  → LangGraph pipeline that invokes Gemini vision/text
# - extract_biomarkers_from_pdf → direct gemini service call in biosync
# - generate_content / extract_from_image / reconcile_ingredient
#   / extract_biomarkers / generate_personalized_insight → future direct calls
GEMINI_INDICATORS = {
    "build_scan_graph",
    "extract_biomarkers_from_pdf",
    "generate_content",
    "extract_from_image",
    "reconcile_ingredient",
    "generate_personalized_insight",
}


def _function_calls_gemini(func_node: ast.FunctionDef) -> bool:
    """Return True if any Call in the function body references a Gemini function."""
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            # Direct call: func_name(...)
            if isinstance(node.func, ast.Name) and any(
                ind in node.func.id for ind in GEMINI_INDICATORS
            ):
                return True
            # Attribute call: obj.func_name(...)
            if isinstance(node.func, ast.Attribute) and any(
                ind in node.func.attr for ind in GEMINI_INDICATORS
            ):
                return True
    return False


def _function_has_token_budget(func_node: ast.FunctionDef) -> bool:
    """Return True if function signature contains token_budget in its defaults."""
    all_defaults = list(func_node.args.defaults) + list(func_node.args.kw_defaults)
    for default in all_defaults:
        if default is None:
            continue
        src = ast.unparse(default)
        if "token_budget" in src:
            return True
    return False


def test_all_gemini_endpoints_have_token_budget():
    """All router functions that call Gemini must have Depends(token_budget(...))."""
    violations = []

    for router_file in ROUTER_DIR.glob("*.py"):
        if router_file.name.startswith("_"):
            continue
        tree = ast.parse(router_file.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if _function_calls_gemini(node) and not _function_has_token_budget(node):
                violations.append(f"{router_file.name}::{node.name}")

    assert violations == [], (
        f"These router functions call Gemini but lack Depends(token_budget(...)): {violations}\n"
        "Add _budget: User = Depends(token_budget(ENDPOINT_TOKEN_COST[...])) to each."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Gate 2: all pipeline nodes must be wrapped with timed_node
# ─────────────────────────────────────────────────────────────────────────────

EXPECTED_NODE_NAMES = [
    "identify_product",
    "extract_ingredients",
    "resolve_entities",
    "search_regulatory",
    "biosync",
    "detect_conflicts",
    "personalize",
    "calculate_risk",
]


def test_all_nodes_are_timed():
    """Every LangGraph pipeline node must be wrapped with timed_node.

    Checks the _is_timed sentinel set exclusively by timed_node — unlike __wrapped__,
    this is not set by arbitrary functools.wraps decorators.

    Reverse-check: asserts graph.nodes matches EXPECTED_NODE_NAMES exactly so that
    adding a new node without updating this list fails CI.

    LangGraph compat: verified with langgraph==0.4.x (.bound.afunc/.func access pattern).
    If this test errors with AttributeError, the LangGraph internal API changed —
    update the introspection path and bump the version comment above.
    """
    from unittest.mock import MagicMock

    import pytest

    from app.agents.graph import build_scan_graph
    from app.config import Settings

    mock_db = MagicMock()
    mock_settings = MagicMock(spec=Settings)
    mock_settings.enable_node_timing = True
    graph = build_scan_graph(db=mock_db, settings=mock_settings)

    # Reverse check: no new nodes silently bypass the gate
    actual_nodes = [k for k in graph.nodes.keys() if k != "__start__"]
    assert set(actual_nodes) == set(EXPECTED_NODE_NAMES), (
        f"graph.nodes has changed — update EXPECTED_NODE_NAMES.\n"
        f"Actual: {sorted(actual_nodes)}\nExpected: {sorted(EXPECTED_NODE_NAMES)}"
    )

    violations = []
    for node_name in EXPECTED_NODE_NAMES:
        try:
            rc = graph.nodes[node_name].bound
            fn = rc.afunc if rc.afunc is not None else rc.func
        except AttributeError as exc:
            pytest.fail(
                f"Cannot introspect {node_name} via .bound.afunc/.func — "
                f"LangGraph internal API may have changed: {exc}"
            )

        assert fn is not None, (
            f"Could not resolve callable for {node_name} — check LangGraph version"
        )

        if not hasattr(fn, "_is_timed"):
            violations.append(node_name)

    assert violations == [], (
        f"These pipeline nodes are missing timed_node wrapper: {violations}\n"
        "Wrap the add_node call in graph.py with timed_node(name, fn)."
    )
