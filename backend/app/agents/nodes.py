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
    ConflictSeverity,
    ConflictType,
    IngredientConflict,
    IngredientResult,
    RegulatoryStatus,
    SemaphoreColor,
)
from app.services import gemini as gemini_service
from app.services import off_client
from app.services.analysis import (
    aggregate_regulatory_status,
    compute_semaphore,
)
from app.services.biomarker_rules import parse_biomarker_payload
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
            "product_name": extraction.product_name,
            "extracted_ingredients": extraction.ingredients,
            "extracted_barcode": extraction.barcode,
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
                    s.source.name: s.status for s in ing.regulatory_statuses if s.source is not None
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
                result = await hybrid_search(lookup, db, settings, top_k=3)
                context[item.name] = "\n".join(h.document for h in result.hits)
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
            raw = decrypt_biomarker(
                biomarker.encrypted_data, biomarker.encryption_iv, settings.aes_key
            )
            return {"biomarkers": parse_biomarker_payload(raw)}
        except (ValueError, KeyError, TypeError) as exc:
            logger.error("biomarker_parse_failed for user %s: %s", user_id, exc)
            return {"biomarkers": None}
        except Exception as exc:
            logger.error("biomarker_decrypt_failed for user %s: %s", user_id, exc)
            return {"biomarkers": None}

    return node


# ─────────────────────────────────────────────
# 6. Detect conflicts (regulatory + biomarker)
# ─────────────────────────────────────────────


def _sources_from_summary(summary: str) -> list[str]:
    sources = []
    for tag in ("FDA_EAFUS", "EFSA_OpenFoodTox", "Codex_GSFA"):
        if tag in summary:
            sources.append(tag.split("_")[0])
    return sources


def make_detect_conflicts_node(db: Session):
    async def node(state: ScanState) -> ScanState:
        resolved = state.get("resolved") or []

        new_resolved: list[IngredientResult] = []
        for item in resolved:
            if item.canonical_name is None:
                new_resolved.append(item)
                continue

            res = resolve(item.canonical_name, db)
            if not res.ingredient:
                new_resolved.append(item)
                continue

            db_conflicts = detect_conflicts(res.ingredient, db)
            new_conflicts = [
                IngredientConflict(
                    conflict_type=ConflictType(c.conflict_type),
                    severity=ConflictSeverity(c.severity),
                    summary=c.summary,
                    sources=_sources_from_summary(c.summary),
                )
                for c in db_conflicts
            ]
            new_resolved.append(
                item.model_copy(update={"conflicts": new_conflicts})
            )

        return {"resolved": new_resolved}

    return node


# ─────────────────────────────────────────────
# 7. Personalize — generate friendly insights per biomarker × ingredient
# ─────────────────────────────────────────────


def make_personalize_node(settings: Settings):
    async def node(state: ScanState) -> ScanState:
        from app.services.analysis import generate_personalized_insights

        resolved = state.get("resolved") or []
        biomarkers = state.get("biomarkers")
        insights = await generate_personalized_insights(resolved, biomarkers, settings)
        return {"personalized_insights": insights}

    return node


# ─────────────────────────────────────────────
# 8. Calculate semaphore risk
# ─────────────────────────────────────────────


def make_calculate_risk_node():
    async def node(state: ScanState) -> ScanState:
        resolved = state.get("resolved") or []
        insights = state.get("personalized_insights") or []

        # Pass biomarkers to compute_semaphore for ORANGE detection
        biomarkers = state.get("biomarkers")
        semaphore, severity, _alerts = compute_semaphore(resolved, biomarkers)

        # If personalized insights exist but semaphore wasn't elevated to ORANGE, elevate it
        _rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        if insights and semaphore not in (SemaphoreColor.RED, SemaphoreColor.ORANGE):
            worst = max(
                insights,
                key=lambda i: _rank.get(
                    i.severity.value if hasattr(i.severity, "value") else str(i.severity), 1
                ),
            )
            semaphore = SemaphoreColor.ORANGE
            sev_val = (
                worst.severity.value if hasattr(worst.severity, "value") else str(worst.severity)
            )
            severity = ConflictSeverity(sev_val)

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
