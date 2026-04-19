"""LangGraph nodes for the scan pipeline.

Each builder returns an async callable bound to (db, settings) — the graph
is constructed per-request so nodes can access the live DB + external services.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.state import ScanState
from app.config import Settings
from app.models import Biomarker
from app.schemas.models import (
    IngredientConflict,
    IngredientResult,
    RegulatoryStatus,
)
from app.services import gemini as gemini_service
from app.services import off_client
from app.services.analysis import aggregate_regulatory_status, compute_semaphore
from app.services.conflicts import detect_conflicts
from app.services.crypto import decrypt_biomarker
from app.services.entity_resolution import resolve
from app.services.retrieval import hybrid_search

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 1. Identify product — OFF barcode lookup
# ─────────────────────────────────────────────

def make_identify_product_node(settings: Settings):
    async def node(state: ScanState) -> ScanState:
        barcode = state.get("barcode")
        if not barcode:
            return {"extracted_ingredients": [], "source": "photo"}

        product = await off_client.fetch_product(barcode, settings)
        if product is None:
            return {"extracted_ingredients": [], "source": "barcode"}

        return {
            "product_name": product["name"],
            "product_brand": product["brand"],
            "product_image_url": product["image_url"],
            "extracted_ingredients": product["ingredients"],
            "source": "barcode",
        }

    return node


# ─────────────────────────────────────────────
# 2. Extract ingredients via Gemini Vision (fallback)
# ─────────────────────────────────────────────

def make_extract_ingredients_node(settings: Settings):
    async def node(state: ScanState) -> ScanState:
        image = state.get("image_b64")
        if state.get("extracted_ingredients"):
            return {}  # already have ingredients from OFF
        if not image:
            return {"error": "No barcode match and no image provided"}

        extraction = await gemini_service.extract_from_image(image, settings)
        return {
            "extracted_ingredients": extraction.ingredients,
            "source": "photo",
        }

    return node


# ─────────────────────────────────────────────
# 3. Resolve entities
# ─────────────────────────────────────────────

def make_resolve_entities_node(db: Session):
    async def node(state: ScanState) -> ScanState:
        names = state.get("extracted_ingredients") or []
        resolved: list[IngredientResult] = []
        for name in names:
            res = resolve(name, db)
            ing = res.ingredient

            reg_status: RegulatoryStatus | None = None
            if ing is not None:
                status_by_source = {
                    s.source.name: s.status
                    for s in ing.regulatory_statuses
                    if s.source is not None
                }
                reg_status = aggregate_regulatory_status(status_by_source)

            resolved.append(
                IngredientResult(
                    name=name,
                    canonical_name=ing.canonical_name if ing else None,
                    cas_number=ing.cas_number if ing else None,
                    e_number=ing.e_number if ing else None,
                    regulatory_status=reg_status,
                    confidence_score=res.confidence,
                    conflicts=[],
                )
            )
        return {"resolved": resolved}

    return node


# ─────────────────────────────────────────────
# 4. Hybrid RAG search
# ─────────────────────────────────────────────

def make_search_regulatory_node(db: Session, settings: Settings):
    async def node(state: ScanState) -> ScanState:
        resolved = state.get("resolved") or []
        context: dict[str, str] = {}
        for item in resolved:
            lookup = item.canonical_name or item.name
            try:
                hits = await hybrid_search(lookup, db, settings, top_k=3)
                context[item.name] = "\n".join(h.document for h in hits)
            except Exception as exc:
                logger.warning("RAG search failed for %s: %s", lookup, exc)
                context[item.name] = ""
        return {"rag_context_by_ingredient": context}

    return node


# ─────────────────────────────────────────────
# 5. Bio-Sync — load & decrypt biomarkers
# ─────────────────────────────────────────────

def make_biosync_node(db: Session, settings: Settings):
    async def node(state: ScanState) -> ScanState:
        user_id = state.get("user_id")
        if not user_id:
            return {"biomarkers": None}

        biomarker = db.scalar(select(Biomarker).where(Biomarker.user_id == user_id))
        if not biomarker:
            return {"biomarkers": None}

        try:
            data = decrypt_biomarker(
                biomarker.encrypted_data, biomarker.encryption_iv, settings.aes_key
            )
        except Exception as exc:
            logger.error("Biomarker decryption failed for user %s: %s", user_id, exc)
            return {"biomarkers": None}

        return {"biomarkers": data}

    return node


# ─────────────────────────────────────────────
# 6. Detect conflicts (regulatory + biomarker)
# ─────────────────────────────────────────────

_BIOMARKER_KEYS_WARNING: dict[str, set[str]] = {
    "glucose": {"high-fructose corn syrup", "sucrose", "sugar", "dextrose"},
    "hba1c": {"high-fructose corn syrup", "sucrose", "sugar", "aspartame"},
    "cholesterol_ldl": {"butylated hydroxyanisole", "butylated hydroxytoluene"},
    "sodium": {"monosodium glutamate", "sodium nitrite", "sodium benzoate"},
}


def _biomarker_matches(biomarkers: dict, ingredient_name: str) -> list[str]:
    ing_lower = ingredient_name.lower()
    matched: list[str] = []
    for key, risky in _BIOMARKER_KEYS_WARNING.items():
        if key not in biomarkers:
            continue
        if any(term in ing_lower for term in risky):
            matched.append(key)
    return matched


def _sources_from_summary(summary: str) -> list[str]:
    sources = []
    for tag in ("FDA_EAFUS", "EFSA_OpenFoodTox", "Codex_GSFA"):
        if tag in summary:
            sources.append(tag.split("_")[0])
    return sources


def make_detect_conflicts_node(db: Session):
    async def node(state: ScanState) -> ScanState:
        resolved = state.get("resolved") or []

        for item in resolved:
            if item.canonical_name is None:
                continue

            res = resolve(item.canonical_name, db)
            if not res.ingredient:
                continue

            db_conflicts = detect_conflicts(res.ingredient, db)
            for c in db_conflicts:
                item.conflicts.append(
                    IngredientConflict(
                        conflict_type=c.conflict_type,
                        severity=c.severity,
                        summary=c.summary,
                        sources=_sources_from_summary(c.summary),
                    )
                )

        return {"resolved": resolved}

    return node


# ─────────────────────────────────────────────
# 7. Calculate semaphore risk
# ─────────────────────────────────────────────

def make_calculate_risk_node():
    async def node(state: ScanState) -> ScanState:
        resolved = state.get("resolved") or []
        biomarkers = state.get("biomarkers")

        semaphore, severity, _alerts = compute_semaphore(resolved, biomarkers)

        return {
            "semaphore": semaphore,
            "conflict_severity": severity.value if severity else None,
            "resolved": resolved,
        }

    return node


# ─────────────────────────────────────────────
# Conditional router
# ─────────────────────────────────────────────

def needs_image_extraction(state: ScanState) -> str:
    if state.get("extracted_ingredients"):
        return "resolve_entities"
    return "extract_ingredients"
