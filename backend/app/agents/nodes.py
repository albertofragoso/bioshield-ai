"""LangGraph nodes for the scan pipeline.

Each builder returns an async callable bound to (db, settings) — the graph
is constructed per-request so nodes can access the live DB + external services.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.state import ScanState
from app.config import Settings
from app.models import Biomarker
from app.schemas.models import (
    CanonicalBiomarker,
    ConflictSeverity,
    IngredientConflict,
    IngredientResult,
    PersonalizedInsight,
    RegulatoryStatus,
    SemaphoreColor,
)
from app.services import gemini as gemini_service
from app.services import off_client
from app.services.analysis import (
    aggregate_regulatory_status,
    compute_semaphore,
    find_ingredient_matches,
)
from app.services.conflicts import detect_conflicts
from app.services.crypto import decrypt_biomarker
from app.services.entity_resolution import resolve
from app.services.rag import get_collection
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

        # New structured format: {"biomarkers": [...], "lab_name": ..., "test_date": ...}
        # Legacy flat-dict format: {"ldl": 130, ...} — treat as no biomarkers for safety
        if isinstance(data, dict) and "biomarkers" in data:
            return {"biomarkers": data["biomarkers"]}

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


_SEVERITY_TO_AVATAR: dict[str, str] = {
    ConflictSeverity.HIGH.value: "red",
    ConflictSeverity.MEDIUM.value: "orange",
    ConflictSeverity.LOW.value: "yellow",
}


# ─────────────────────────────────────────────
# 7. Personalize — generate friendly insights per biomarker × ingredient
# ─────────────────────────────────────────────


def make_personalize_node(settings: Settings):
    async def node(state: ScanState) -> ScanState:
        resolved = state.get("resolved") or []
        biomarkers = state.get("biomarkers")

        collection = get_collection(settings)
        matches = await find_ingredient_matches(biomarkers, resolved, settings, collection)
        if not matches:
            return {"personalized_insights": []}

        async def _build_insight(
            bm,
            ingr_names: list[str],
            severity: ConflictSeverity,
            kind: str,
            direction: str,
            semantic_score: float = 0.0,
        ) -> PersonalizedInsight:
            name = bm.get("name") if isinstance(bm, dict) else getattr(bm, "name", "")
            value = bm.get("value") if isinstance(bm, dict) else getattr(bm, "value", 0.0)
            unit = bm.get("unit") if isinstance(bm, dict) else getattr(bm, "unit", "")
            classification = (
                bm.get("classification")
                if isinstance(bm, dict)
                else getattr(bm, "classification", "high")
            )
            ref_low = (
                bm.get("reference_range_low")
                if isinstance(bm, dict)
                else getattr(bm, "reference_range_low", None)
            )
            ref_high = (
                bm.get("reference_range_high")
                if isinstance(bm, dict)
                else getattr(bm, "reference_range_high", None)
            )
            name_val = name.value if (name is not None and hasattr(name, "value")) else str(name)
            class_val = (
                classification.value
                if (classification is not None and hasattr(classification, "value"))
                else str(classification)
            )
            float_value = float(value or 0.0)

            copy = await gemini_service.generate_personalized_insight(
                biomarker_name=name_val,
                biomarker_value=float_value,
                biomarker_unit=str(unit),
                classification=class_val,
                severity=severity.value,
                affecting_ingredients=ingr_names,
                kind=kind,
                settings=settings,
            )
            return PersonalizedInsight(
                biomarker_name=cast(CanonicalBiomarker, name_val),
                biomarker_value=float_value,
                biomarker_unit=str(unit),
                classification=cast(Literal["low", "normal", "high"], class_val),
                affecting_ingredients=ingr_names,
                severity=severity,
                kind=cast(Literal["alert", "watch"], kind),
                impact_direction=cast(Literal["raises", "lowers"], direction),
                reference_range_low=ref_low,
                reference_range_high=ref_high,
                friendly_title=copy.friendly_title,
                friendly_biomarker_label=copy.friendly_biomarker_label,
                friendly_explanation=copy.friendly_explanation,
                friendly_recommendation=copy.friendly_recommendation,
                avatar_variant=cast(
                    Literal["yellow", "orange", "red"],
                    _SEVERITY_TO_AVATAR.get(severity.value, "yellow"),
                ),
            )

        insights = await asyncio.gather(*[_build_insight(*m) for m in matches])
        return {"personalized_insights": list(insights)}

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
