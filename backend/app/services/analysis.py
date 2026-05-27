"""Semaphore computation: maps ingredient results + biomarker insights to a risk color.

Priority (first match wins):
    RED    — any ingredient banned by any regulator
    ORANGE — personalized insight detected (biomarker × ingredient conflict)
    YELLOW — restricted/under review status, or an unresolved regulatory conflict
    GRAY   — <50% of ingredients resolved, or retrieval degraded
    BLUE   — all ingredients approved, no conflicts

Biomarker conflict detection uses `BIOMARKER_RULES` — a declarative map of
(canonical biomarker + classification) → (ingredient keywords + severity).
Extending it is a data-curation task, not a code change.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from app.config import Settings

from app.schemas.models import (
    CanonicalBiomarker,
    ConflictSeverity,
    IngredientResult,
    PersonalizedAlert,
    PersonalizedInsight,
    RegulatoryStatus,
    SemaphoreColor,
)
from app.services.biomarker_rules import BiomarkerRule, BIOMARKER_RULES

logger = logging.getLogger(__name__)

# Umbral de similitud coseno para considerar un hit semántico válido.
# BGE-M3 contra templates regulatorios (sin propiedades clínicas) puede dar
# similitudes bajas (~0.4–0.55); este valor captura sinónimos sin ruido.
# Calibrar con ground truth antes de subir.
_SEMANTIC_SIMILARITY_THRESHOLD = 0.65

_SEVERITY_RANK = {
    ConflictSeverity.HIGH: 3,
    ConflictSeverity.MEDIUM: 2,
    ConflictSeverity.LOW: 1,
}

_STATUS_RANK = {
    RegulatoryStatus.BANNED: 4,
    RegulatoryStatus.RESTRICTED: 3,
    RegulatoryStatus.UNDER_REVIEW: 2,
    RegulatoryStatus.APPROVED: 1,
}

_NEGATION_TERMS = ("free", "without", "sin", "no ", "zero", "libre", "free of")


def _normalize_ingredient_name(text: str) -> str:
    """Normalize ingredient names by converting non-alphanumeric chars to spaces.

    Handles cases like "High-Fructose Corn Syrup" → "high fructose corn syrup"
    so keyword matching works across different punctuation styles.
    """
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return " ".join(normalized.split())  # collapse multiple spaces


def _has_negation(text: str, keyword: str) -> bool:
    """Return True only if every occurrence of `keyword` in `text` has a negation
    term within 15 chars. Returns False as soon as one non-negated occurrence is found."""
    start = 0
    found_any = False
    while True:
        idx = text.find(keyword, start)
        if idx < 0:
            break
        found_any = True
        end = idx + len(keyword)
        window = text[max(0, idx - 15) : end + 15]
        if not any(neg in window for neg in _NEGATION_TERMS):
            return False  # non-negated occurrence found — do not suppress
        start = end
    return found_any  # True only if found occurrences AND all were negated


_STATUS_ALIASES = {
    "approved": RegulatoryStatus.APPROVED,
    "banned": RegulatoryStatus.BANNED,
    "restricted": RegulatoryStatus.RESTRICTED,
    "under review": RegulatoryStatus.UNDER_REVIEW,
}


def _coerce_status(raw: str) -> RegulatoryStatus | None:
    """Accept any case variant of the enum label (APPROVED / Approved / approved)."""
    key = (raw or "").strip().lower()
    return _STATUS_ALIASES.get(key)


def aggregate_regulatory_status(status_by_source: dict[str, str]) -> RegulatoryStatus | None:
    """Collapse per-source statuses to a single worst-case label.

    Priority: Banned > Restricted > Under Review > Approved. Unknown values
    are ignored (returns the worst recognized one, or None if none match).
    """
    worst: RegulatoryStatus | None = None
    worst_rank = 0
    for raw in status_by_source.values():
        status = _coerce_status(raw)
        if status is None:
            continue
        rank = _STATUS_RANK[status]
        if rank > worst_rank:
            worst = status
            worst_rank = rank
    return worst


def _find_matches_keywords(
    biomarkers: list | None,
    ingredients: list[IngredientResult],
) -> list[
    tuple[
        object, list[str], ConflictSeverity, Literal["alert", "watch"], Literal["raises", "lowers"]
    ]
]:
    """Keyword-only matching. Sync — usado por detect_biomarker_conflicts y como base de find_ingredient_matches."""
    if not biomarkers or not ingredients:
        return []

    matches: list[
        tuple[
            object,
            list[str],
            ConflictSeverity,
            Literal["alert", "watch"],
            Literal["raises", "lowers"],
        ]
    ] = []
    for bm in biomarkers:
        name = bm.name
        classification = bm.classification

        if name is None or classification is None:
            continue

        name_val = str(name)
        class_val = str(classification)

        if class_val == "unknown":
            continue

        for rule in BIOMARKER_RULES:
            if rule.biomarker.value != name_val:
                continue

            # Derive kind and decide whether to fire
            if class_val == "normal":
                kind: Literal["alert", "watch"] = "watch"
            elif rule.direction == "raises" and class_val == "high":
                kind = "alert"
            elif rule.direction == "lowers" and class_val == "low":
                kind = "alert"
            else:
                # Opposite direction (e.g. raises but classification is low) — skip
                continue

            matched_ingr: list[str] = []
            for ing in ingredients:
                ing_names_raw = " ".join(filter(None, (ing.name, ing.canonical_name))).lower()
                ing_names = _normalize_ingredient_name(ing_names_raw)
                for kw in rule.keywords:
                    if kw not in ing_names:
                        continue
                    if _has_negation(ing_names, kw):
                        continue
                    if any(ex in ing_names for ex in rule.excludes):
                        continue
                    matched_ingr.append(ing.canonical_name or ing.name)
                    break  # un keyword match es suficiente por ingrediente

            if matched_ingr:
                matches.append((bm, matched_ingr, rule.severity, kind, rule.direction))

    return matches


async def find_ingredient_matches(
    biomarkers: list | None,
    ingredients: list[IngredientResult],
    settings: Settings | None = None,
    collection=None,
) -> list[
    tuple[
        object,
        list[str],
        ConflictSeverity,
        Literal["alert", "watch"],
        Literal["raises", "lowers"],
        float,
    ]
]:
    """Keyword + semantic matching. Async — usado solo desde make_personalize_node.

    Cuando settings=None o collection=None, cae a keyword-only con semantic_score=0.0.
    Los valores reales del biomarcador NUNCA se embeddean — solo el texto canónico de la
    regla clínica (nombre + direction + keywords), que es código estático sin PHI.
    """
    if not biomarkers or not ingredients:
        return []

    keyword_results = _find_matches_keywords(biomarkers, ingredients)
    if settings is None or collection is None:
        return [(*m, 0.0) for m in keyword_results]

    from app.services.embeddings import embed_text
    from app.services.rag import query_by_embedding

    enriched = []
    for match in keyword_results:
        bm, ingr_names, severity, kind, direction = match

        name = bm.name
        name_val = str(name)

        rule = next(
            (
                r
                for r in BIOMARKER_RULES
                if r.biomarker.value == name_val and r.direction == direction
            ),
            None,
        )

        if rule is None:
            enriched.append((*match, 0.0))
            continue

        # Solo texto canónico de la regla — sin valores del usuario
        query_text = (
            f"{rule.biomarker.value.replace('_', ' ')} {rule.direction}: {', '.join(rule.keywords)}"
        )

        try:
            embedding = await embed_text(query_text, settings)
            hits = query_by_embedding(collection, embedding, top_k=5)

            semantic_score = 0.0
            additional: list[str] = []
            for hit in hits:
                if hit.similarity < _SEMANTIC_SIMILARITY_THRESHOLD:
                    continue
                hit_canonical = hit.metadata.get("canonical_name", "").lower()
                for ing in ingredients:
                    ing_canonical = (ing.canonical_name or "").lower()
                    if hit_canonical and (
                        ing_canonical == hit_canonical or hit_canonical in ing.name.lower()
                    ):
                        match_str = ing.canonical_name or ing.name
                        if match_str not in ingr_names and match_str not in additional:
                            additional.append(match_str)
                            semantic_score = max(semantic_score, hit.similarity)

            enriched.append(
                (bm, list(ingr_names) + additional, severity, kind, direction, semantic_score)
            )

        except Exception as exc:
            logger.warning("Semantic enrichment skipped for %s: %s", name_val, exc)
            enriched.append((*match, 0.0))

    return enriched


def detect_biomarker_conflicts(
    ingredients: list[IngredientResult],
    biomarkers: list | None,
) -> list[PersonalizedAlert]:
    """Return PersonalizedAlert list for ORANGE semaphore detection.

    Thin wrapper around _find_matches_keywords — sync, no semantic path.
    Deduplicates by ingredient: when multiple rules fire on the same ingredient,
    only the highest-severity alert is kept.
    """
    if not biomarkers:
        return []

    alerts: list[PersonalizedAlert] = []
    for bm, ingr_names, severity, _kind, _direction in _find_matches_keywords(
        biomarkers, ingredients
    ):
        name = bm.name
        value = bm.value
        name_val = str(name)
        for ingr in ingr_names:
            alerts.append(
                PersonalizedAlert(
                    ingredient=ingr,
                    biomarker_conflict=f"{name_val}={value}",
                    severity=severity,
                )
            )

    # Per-ingredient dedup: keep only highest-severity alert
    seen: dict[str, PersonalizedAlert] = {}
    for alert in alerts:
        prev = seen.get(alert.ingredient)
        if prev is None or _SEVERITY_RANK[alert.severity] > _SEVERITY_RANK[prev.severity]:
            seen[alert.ingredient] = alert
    return list(seen.values())


def compute_semaphore(
    ingredients: list[IngredientResult],
    biomarkers: list | None = None,
    *,
    retrieval_degraded: bool = False,
) -> tuple[SemaphoreColor, ConflictSeverity | None, list[PersonalizedAlert]]:
    """Return (semaphore_color, conflict_severity, biomarker_alerts).

    `retrieval_degraded` forces GRAY when the RAG layer returned no regulatory
    context (L3 fallback) — we can't render a confident verdict in that case.
    """
    if not ingredients:
        return SemaphoreColor.GRAY, None, []

    # RED: any banned ingredient
    for ing in ingredients:
        if ing.regulatory_status == RegulatoryStatus.BANNED:
            return SemaphoreColor.RED, ConflictSeverity.HIGH, []

    # ORANGE: biomarker conflict
    alerts = detect_biomarker_conflicts(ingredients, biomarkers)
    if alerts:
        worst = max(alerts, key=lambda a: _SEVERITY_RANK[a.severity])
        return SemaphoreColor.ORANGE, worst.severity, alerts

    # YELLOW: restricted/under review, or existing ingredient conflict
    worst_conflict_severity: ConflictSeverity | None = None
    has_warning_status = False
    for ing in ingredients:
        if ing.regulatory_status in (RegulatoryStatus.RESTRICTED, RegulatoryStatus.UNDER_REVIEW):
            has_warning_status = True
        for conflict in ing.conflicts:
            if (
                worst_conflict_severity is None
                or _SEVERITY_RANK[conflict.severity] > _SEVERITY_RANK[worst_conflict_severity]
            ):
                worst_conflict_severity = conflict.severity

    if has_warning_status or worst_conflict_severity:
        return (
            SemaphoreColor.YELLOW,
            worst_conflict_severity or ConflictSeverity.MEDIUM,
            [],
        )

    # GRAY: degraded retrieval or too few ingredients resolved
    if retrieval_degraded:
        return SemaphoreColor.GRAY, None, []

    resolved = sum(1 for ing in ingredients if ing.canonical_name)
    if resolved / len(ingredients) < 0.5:
        return SemaphoreColor.GRAY, None, []

    return SemaphoreColor.BLUE, None, []


# ─────────────────────────────────────────────
# Standalone personalization — shared by LangGraph node and read-path endpoints
# ─────────────────────────────────────────────

_SEVERITY_TO_AVATAR: dict[str, str] = {
    ConflictSeverity.HIGH.value: "red",
    ConflictSeverity.MEDIUM.value: "orange",
    ConflictSeverity.LOW.value: "yellow",
}


async def generate_personalized_insights(
    resolved: list[IngredientResult],
    biomarkers: list | None,
    settings: Settings,
) -> list[PersonalizedInsight]:
    """Keyword + semantic matching → Gemini copy → list[PersonalizedInsight].

    Extracted from make_personalize_node so endpoints can regenerate on read.
    Does NOT persist — caller decides what to do with the result.
    """
    from app.services import gemini as gemini_service
    from app.services.rag import get_collection

    collection = get_collection(settings)
    matches = await find_ingredient_matches(biomarkers, resolved, settings, collection)
    if not matches:
        return []

    async def _build_insight(
        bm,
        ingr_names: list[str],
        severity: ConflictSeverity,
        kind: str,
        direction: str,
        semantic_score: float = 0.0,
    ) -> PersonalizedInsight:
        name = bm.name
        value = bm.value
        unit = bm.unit
        classification = bm.classification
        ref_low = bm.reference_range_low
        ref_high = bm.reference_range_high
        name_val = str(name)
        class_val = str(classification)
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
    return list(insights)
