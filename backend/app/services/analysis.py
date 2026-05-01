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

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.config import Settings

from app.schemas.models import (
    CanonicalBiomarker,
    ConflictSeverity,
    IngredientResult,
    PersonalizedAlert,
    RegulatoryStatus,
    SemaphoreColor,
)

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


def _has_negation(text: str, keyword: str) -> bool:
    """Return True if a negation word appears within 15 chars before or after `keyword` in `text`."""
    idx = text.find(keyword)
    if idx < 0:
        return False
    end = idx + len(keyword)
    window = text[max(0, idx - 15) : end + 15]
    return any(neg in window for neg in _NEGATION_TERMS)


_LIPID_RAISING_KEYWORDS = (
    "trans fat",
    "grasas trans",
    "aceite hidrogenado",
    "hydrogenated",
    "saturated fat",
    "palm oil",
    "aceite de palma",
)

_INDUSTRIAL_HYDROGENATED_EXCLUDES = (
    "petroleum",
    "resin",
    "polymer",
    "copolymer",
    "homopolymer",
    "mw:",
    "decene",
    "dodecene",
    "octene",
    "hexene",
)


@dataclass(frozen=True)
class BiomarkerRule:
    biomarker: CanonicalBiomarker
    direction: Literal["raises", "lowers"]  # effect of the ingredient on this biomarker
    keywords: tuple[str, ...]  # substrings to look for in ingredient names (lowercase)
    severity: ConflictSeverity
    message: str
    excludes: tuple[str, ...] = ()  # substrings that disqualify a keyword match
    # Firing logic (derived from direction):
    #   raises → alert when classification=="high", watch when "normal"
    #   lowers → alert when classification=="low",  watch when "normal"


# Data-curated rules. Add entries here to extend coverage — no code changes needed.
BIOMARKER_RULES: tuple[BiomarkerRule, ...] = (
    BiomarkerRule(
        biomarker=CanonicalBiomarker.LDL,
        direction="raises",
        keywords=_LIPID_RAISING_KEYWORDS,
        excludes=_INDUSTRIAL_HYDROGENATED_EXCLUDES,
        severity=ConflictSeverity.HIGH,
        message="LDL con grasa trans/saturada",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.TOTAL_CHOLESTEROL,
        direction="raises",
        keywords=_LIPID_RAISING_KEYWORDS,
        excludes=_INDUSTRIAL_HYDROGENATED_EXCLUDES,
        severity=ConflictSeverity.HIGH,
        message="Colesterol total con grasa trans/saturada",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.HDL,
        direction="lowers",
        keywords=("trans fat", "grasas trans", "hydrogenated", "aceite hidrogenado"),
        excludes=_INDUSTRIAL_HYDROGENATED_EXCLUDES,
        severity=ConflictSeverity.MEDIUM,
        message="HDL con grasas trans",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.GLUCOSE,
        direction="raises",
        keywords=(
            "dextrose",
            "dextrosa",
            "maltose",
            "maltosa",
            "refined sugar",
            "white sugar",
            "azúcar refinada",
            "glucose syrup",
            "jarabe de glucosa",
        ),
        severity=ConflictSeverity.HIGH,
        message="Glucosa con azúcares de absorción rápida",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.HBA1C,
        direction="raises",
        keywords=(
            "high fructose",
            "corn syrup",
            "jarabe de maíz",
            "fructose",
            "fructosa",
            "added sugar",
            "azúcar añadida",
        ),
        severity=ConflictSeverity.HIGH,
        message="HbA1c con azúcares de carga crónica",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.TRIGLYCERIDES,
        direction="raises",
        keywords=("fructose", "fructosa", "jarabe", "syrup", "added sugar"),
        severity=ConflictSeverity.MEDIUM,
        message="Triglicéridos con fructosa/jarabes",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.SODIUM,
        direction="raises",
        keywords=(
            "sodium chloride",
            "cloruro de sodio",
            "monosodium glutamate",
            "glutamato monosódico",
            "msg",
            "added salt",
            "sal de mesa",
            "table salt",
            "sodium",
            "sodio",
        ),
        excludes=(
            "potassium salt",
            "calcium salt",
            "magnesium salt",
            "fatty acid salt",
            "sodium bicarbonate",
            "sodium carbonate",
            "sodium silicate",
        ),
        severity=ConflictSeverity.MEDIUM,
        message="Sodio con ingredientes salinos",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.URIC_ACID,
        direction="raises",
        keywords=(
            "high fructose",
            "corn syrup",
            "fructose",
            "fructosa",
            "jarabe de maíz",
        ),
        severity=ConflictSeverity.MEDIUM,
        message="Ácido úrico con fructosa",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.POTASSIUM,
        direction="raises",
        keywords=(
            "potassium chloride",
            "cloruro de potasio",
            "potassium",
            "potasio",
            "potásico",
            "kcl",
            "dipotassium",
            "potassic",
        ),
        severity=ConflictSeverity.LOW,
        message="Potasio con aditivos de potasio",
    ),
)


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
        name = bm.get("name") if isinstance(bm, dict) else getattr(bm, "name", None)
        classification = (
            bm.get("classification")
            if isinstance(bm, dict)
            else getattr(bm, "classification", None)
        )

        if name is None or classification is None:
            continue

        # Normalize to string value (handles both enum and plain str)
        name_val = name.value if hasattr(name, "value") else str(name)
        class_val = (
            classification.value if hasattr(classification, "value") else str(classification)
        )

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
                ing_names = " ".join(filter(None, (ing.name, ing.canonical_name))).lower()
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

        name = bm.get("name") if isinstance(bm, dict) else getattr(bm, "name", None)
        name_val = name.value if (name is not None and hasattr(name, "value")) else str(name)

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
        name = bm.get("name") if isinstance(bm, dict) else getattr(bm, "name", None)
        value = bm.get("value") if isinstance(bm, dict) else getattr(bm, "value", None)
        name_val = name.value if (name is not None and hasattr(name, "value")) else str(name)
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
