"""Semaphore computation: maps ingredient results + biomarkers to a risk color.

Priority (first match wins):
    RED    — any ingredient banned by any regulator
    ORANGE — biomarker conflict detected for the current user
    YELLOW — restricted/under review status, or an unresolved conflict exists
    GRAY   — <50% of ingredients resolved, or retrieval degraded
    BLUE   — all ingredients approved, no conflicts

Biomarker conflict detection uses a small hand-curated map (`BIOMARKER_RULES`).
This is intentionally simple for MVP — expanding it is a data-curation task,
not a code change, beyond adding new rules here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.schemas.models import (
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
    biomarker_key: str       # dict key in the decrypted biomarker payload
    threshold: float         # value above which the rule fires
    keywords: tuple[str, ...]  # substrings to look for in ingredient names (lowercase)
    severity: ConflictSeverity
    message: str


# Data-curated rules. Extend this list rather than adding branches in code.
BIOMARKER_RULES: tuple[BiomarkerRule, ...] = (
    BiomarkerRule(
        biomarker_key="ldl",
        threshold=130.0,
        keywords=("trans fat", "grasas trans", "aceite hidrogenado", "hydrogenated", "saturated fat"),
        severity=ConflictSeverity.HIGH,
        message="LDL elevado con grasa trans/saturada",
    ),
    BiomarkerRule(
        biomarker_key="glucose",
        threshold=100.0,
        keywords=("jarabe de maíz", "high fructose", "corn syrup", "dextrosa", "dextrose", "azúcar añadida", "added sugar", "fructose"),
        severity=ConflictSeverity.HIGH,
        message="Glucosa en ayuno alta con azúcares añadidos",
    ),
    BiomarkerRule(
        biomarker_key="triglycerides",
        threshold=150.0,
        keywords=("fructose", "fructosa", "jarabe", "syrup"),
        severity=ConflictSeverity.MEDIUM,
        message="Triglicéridos altos con fructosa/jarabes",
    ),
    BiomarkerRule(
        biomarker_key="sodium",
        threshold=3000.0,
        keywords=("sodio", "sodium", "msg", "glutamato monosódico"),
        severity=ConflictSeverity.MEDIUM,
        message="Sodio alto con ingredientes salinos añadidos",
    ),
    BiomarkerRule(
        biomarker_key="uric_acid",
        threshold=7.0,
        keywords=("jarabe de maíz", "high fructose", "corn syrup"),
        severity=ConflictSeverity.MEDIUM,
        message="Ácido úrico alto con fructosa",
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


def detect_biomarker_conflicts(
    ingredients: list[IngredientResult],
    biomarkers: dict | None,
) -> list[PersonalizedAlert]:
    """Return alerts for ingredients that clash with the user's biomarker values."""
    if not biomarkers:
        return []

    alerts: list[PersonalizedAlert] = []
    for rule in BIOMARKER_RULES:
        raw_value = biomarkers.get(rule.biomarker_key)
        if raw_value is None:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if value <= rule.threshold:
            continue

        for ing in ingredients:
            ing_names = " ".join(
                filter(None, (ing.name, ing.canonical_name))
            ).lower()
            if any(kw in ing_names for kw in rule.keywords):
                alerts.append(
                    PersonalizedAlert(
                        ingredient=ing.canonical_name or ing.name,
                        biomarker_conflict=f"{rule.message} ({rule.biomarker_key}={value})",
                        severity=rule.severity,
                    )
                )
    return alerts


def compute_semaphore(
    ingredients: list[IngredientResult],
    biomarkers: dict | None = None,
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
