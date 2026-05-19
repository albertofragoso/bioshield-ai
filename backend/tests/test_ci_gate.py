"""CI gate: every router function calling Gemini must declare token_budget dependency."""
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
