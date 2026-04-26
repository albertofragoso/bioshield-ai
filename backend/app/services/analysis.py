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
from typing import Literal

from app.schemas.models import (
    CanonicalBiomarker,
    ConflictSeverity,
    IngredientResult,
    PersonalizedAlert,
    RegulatoryStatus,
    SemaphoreColor,
)

logger = logging.getLogger(__name__)

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


@dataclass(frozen=True)
class BiomarkerRule:
    biomarker: CanonicalBiomarker
    when_classification: Literal["low", "high"]  # fires when biomarker has this classification
    keywords: tuple[str, ...]  # substrings to look for in ingredient names (lowercase)
    severity: ConflictSeverity
    message: str


# Data-curated rules. Add entries here to extend coverage — no code changes needed.
BIOMARKER_RULES: tuple[BiomarkerRule, ...] = (
    BiomarkerRule(
        biomarker=CanonicalBiomarker.LDL,
        when_classification="high",
        keywords=("trans fat", "grasas trans", "aceite hidrogenado", "hydrogenated", "saturated fat", "palm oil", "aceite de palma"),
        severity=ConflictSeverity.HIGH,
        message="LDL alto con grasa trans/saturada",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.TOTAL_CHOLESTEROL,
        when_classification="high",
        keywords=("trans fat", "hydrogenated", "aceite hidrogenado", "palm oil", "saturated fat"),
        severity=ConflictSeverity.HIGH,
        message="Colesterol total alto con grasa trans/saturada",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.HDL,
        when_classification="low",
        keywords=("trans fat", "grasas trans", "hydrogenated", "aceite hidrogenado"),
        severity=ConflictSeverity.MEDIUM,
        message="HDL bajo con grasas trans",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.GLUCOSE,
        when_classification="high",
        keywords=("jarabe de maíz", "high fructose", "corn syrup", "dextrosa", "dextrose", "azúcar añadida", "added sugar", "fructose"),
        severity=ConflictSeverity.HIGH,
        message="Glucosa alta con azúcares añadidos",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.HBA1C,
        when_classification="high",
        keywords=("jarabe de maíz", "high fructose", "corn syrup", "dextrosa", "dextrose", "added sugar", "fructose"),
        severity=ConflictSeverity.HIGH,
        message="HbA1c alta con azúcares añadidos",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.TRIGLYCERIDES,
        when_classification="high",
        keywords=("fructose", "fructosa", "jarabe", "syrup", "added sugar"),
        severity=ConflictSeverity.MEDIUM,
        message="Triglicéridos altos con fructosa/jarabes",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.SODIUM,
        when_classification="high",
        keywords=("sodio", "sodium", "msg", "glutamato monosódico", "sal", "salt"),
        severity=ConflictSeverity.MEDIUM,
        message="Sodio alto con ingredientes salinos",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.URIC_ACID,
        when_classification="high",
        keywords=("jarabe de maíz", "high fructose", "corn syrup", "fructose", "fructosa"),
        severity=ConflictSeverity.MEDIUM,
        message="Ácido úrico alto con fructosa",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.POTASSIUM,
        when_classification="high",
        keywords=("potassium chloride", "cloruro de potasio"),
        severity=ConflictSeverity.LOW,
        message="Potasio alto con aditivos de potasio",
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


def find_ingredient_matches(
    biomarkers: list | None,
    ingredients: list[IngredientResult],
) -> list[tuple[object, list[str], ConflictSeverity]]:
    """Return (biomarker, matching_ingredient_names, severity) for each rule match.

    `biomarkers` is a list of Biomarker schema objects (or dicts with 'name',
    'value', 'classification' keys). Called by the `personalize` LangGraph node.
    """
    if not biomarkers or not ingredients:
        return []

    matches: list[tuple[object, list[str], ConflictSeverity]] = []
    for bm in biomarkers:
        name = bm.get("name") if isinstance(bm, dict) else getattr(bm, "name", None)
        classification = bm.get("classification") if isinstance(bm, dict) else getattr(bm, "classification", None)

        if name is None or classification is None:
            continue

        # Normalize to string value (handles both enum and plain str)
        name_val = name.value if hasattr(name, "value") else str(name)
        class_val = classification.value if hasattr(classification, "value") else str(classification)

        if class_val not in ("low", "high"):
            continue

        for rule in BIOMARKER_RULES:
            if rule.biomarker.value != name_val:
                continue
            if rule.when_classification != class_val:
                continue

            matched_ingr: list[str] = []
            for ing in ingredients:
                ing_names = " ".join(filter(None, (ing.name, ing.canonical_name))).lower()
                if any(kw in ing_names for kw in rule.keywords):
                    matched_ingr.append(ing.canonical_name or ing.name)

            if matched_ingr:
                matches.append((bm, matched_ingr, rule.severity))

    return matches


def detect_biomarker_conflicts(
    ingredients: list[IngredientResult],
    biomarkers: list | None,
) -> list[PersonalizedAlert]:
    """Return legacy PersonalizedAlert list for ORANGE semaphore detection.

    Thin wrapper around find_ingredient_matches — kept for backward compat
    with compute_semaphore until the personalize node fully takes over.
    """
    if not biomarkers:
        return []

    alerts: list[PersonalizedAlert] = []
    for bm, ingr_names, severity in find_ingredient_matches(biomarkers, ingredients):
        name = bm.get("name") if isinstance(bm, dict) else getattr(bm, "name", None)
        value = bm.get("value") if isinstance(bm, dict) else getattr(bm, "value", None)
        name_val = name.value if hasattr(name, "value") else str(name)
        for ingr in ingr_names:
            alerts.append(
                PersonalizedAlert(
                    ingredient=ingr,
                    biomarker_conflict=f"{name_val}={value}",
                    severity=severity,
                )
            )
    return alerts


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
