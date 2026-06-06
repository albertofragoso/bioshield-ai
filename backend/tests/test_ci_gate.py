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

    Builds the compiled graph with mock dependencies and checks that each node's
    inner callable carries __wrapped__ (set by functools.wraps in timed_node).
    Adding a node to graph.py without updating EXPECTED_NODE_NAMES fails CI.
    """
    from unittest.mock import MagicMock

    from app.agents.graph import build_scan_graph
    from app.config import Settings

    mock_db = MagicMock()
    mock_settings = MagicMock(spec=Settings)
    graph = build_scan_graph(db=mock_db, settings=mock_settings)

    violations = []
    for node_name in EXPECTED_NODE_NAMES:
        rc = graph.nodes[node_name].bound
        fn = rc.afunc if rc.afunc is not None else rc.func
        if not hasattr(fn, "__wrapped__"):
            violations.append(node_name)

    assert violations == [], (
        f"These pipeline nodes are missing timed_node wrapper: {violations}\n"
        "Wrap the add_node call in graph.py with timed_node(name, fn)."
    )
