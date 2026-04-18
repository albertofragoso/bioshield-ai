"""StateGraph assembly for the scan pipeline.

Shape (§ ScanState):
    START
      └─► identify_product
            ├─[ingredients found]─► resolve_entities
            └─[else]──────────────► extract_ingredients ─► resolve_entities
    resolve_entities → search_regulatory → biosync → detect_conflicts → calculate_risk → END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.nodes import (
    make_biosync_node,
    make_calculate_risk_node,
    make_detect_conflicts_node,
    make_extract_ingredients_node,
    make_identify_product_node,
    make_resolve_entities_node,
    make_search_regulatory_node,
    needs_image_extraction,
)
from app.agents.state import ScanState
from app.config import Settings


def build_scan_graph(db: Session, settings: Settings):
    """Compile a per-request scan graph that closes over the live DB session."""
    graph = StateGraph(ScanState)

    graph.add_node("identify_product", make_identify_product_node(settings))
    graph.add_node("extract_ingredients", make_extract_ingredients_node(settings))
    graph.add_node("resolve_entities", make_resolve_entities_node(db))
    graph.add_node("search_regulatory", make_search_regulatory_node(db, settings))
    graph.add_node("biosync", make_biosync_node(db, settings))
    graph.add_node("detect_conflicts", make_detect_conflicts_node(db))
    graph.add_node("calculate_risk", make_calculate_risk_node())

    graph.add_edge(START, "identify_product")
    graph.add_conditional_edges(
        "identify_product",
        needs_image_extraction,
        {
            "extract_ingredients": "extract_ingredients",
            "resolve_entities": "resolve_entities",
        },
    )
    graph.add_edge("extract_ingredients", "resolve_entities")
    graph.add_edge("resolve_entities", "search_regulatory")
    graph.add_edge("search_regulatory", "biosync")
    graph.add_edge("biosync", "detect_conflicts")
    graph.add_edge("detect_conflicts", "calculate_risk")
    graph.add_edge("calculate_risk", END)

    return graph.compile()
