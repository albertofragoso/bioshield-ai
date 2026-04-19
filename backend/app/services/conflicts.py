"""Detect regulatory / scientific / temporal conflicts for an ingredient.

Per docs/embedding-strategy.md and PRD §3.B severity matrix. Writes to the
`conflicts` table (upsert by (ingredient_id, conflict_type)).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Conflict, Ingredient, RegulatoryStatus
from app.schemas.models import ConflictSeverity, ConflictType

_HAZARD_TERMS = (
    "genotoxicity",
    "genotóxico",
    "carcinogen",
    "carcinog",
    "noael",
    "mutagenic",
)

_STALE_THRESHOLD = timedelta(days=730)  # 24 months


def _status_map(statuses: Iterable[RegulatoryStatus]) -> dict[str, RegulatoryStatus]:
    """Keyed by DataSource.name (e.g. 'FDA_EAFUS', 'EFSA_OpenFoodTox')."""
    out: dict[str, RegulatoryStatus] = {}
    for s in statuses:
        if s.source and s.source.name:
            out[s.source.name] = s
    return out


def _mentions_hazard(note: str | None) -> bool:
    if not note:
        return False
    text = note.lower()
    return any(term in text for term in _HAZARD_TERMS)


def detect_conflicts(ingredient: Ingredient, db: Session) -> list[Conflict]:
    """Detect conflicts and upsert into the conflicts table.

    Returns the (possibly empty) list of persisted Conflict rows.
    """
    statuses = list(
        db.scalars(
            select(RegulatoryStatus).where(RegulatoryStatus.ingredient_id == ingredient.id)
        )
    )
    if not statuses:
        return []

    by_source = _status_map(statuses)
    detected: list[tuple[ConflictType, ConflictSeverity, str]] = []

    # Normalize status strings for case-insensitive comparisons
    status_values = {name: s.status.upper() for name, s in by_source.items()}

    # REGULATORY: status mismatch across agencies (BANNED vs APPROVED)
    banned_sources = [n for n, v in status_values.items() if v == "BANNED"]
    approved_sources = [n for n, v in status_values.items() if v == "APPROVED"]
    if banned_sources and approved_sources:
        detected.append(
            (
                ConflictType.REGULATORY,
                ConflictSeverity.HIGH,
                f"Banned in {','.join(banned_sources)}; Approved in {','.join(approved_sources)}",
            )
        )

    # SCIENTIFIC: hazard flagged but still approved somewhere
    hazard_source = next((n for n, s in by_source.items() if _mentions_hazard(s.hazard_note)), None)
    if hazard_source and approved_sources:
        detected.append(
            (
                ConflictType.SCIENTIFIC,
                ConflictSeverity.MEDIUM,
                f"Hazard flagged by {hazard_source}; still APPROVED by {','.join(approved_sources)}",
            )
        )

    # TEMPORAL: most recent evaluation is stale
    evaluations = [s.evaluated_at for s in statuses if s.evaluated_at]
    if evaluations:
        latest = max(evaluations)
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=UTC)
        if datetime.now(UTC) - latest > _STALE_THRESHOLD:
            detected.append(
                (
                    ConflictType.TEMPORAL,
                    ConflictSeverity.LOW,
                    f"Latest regulatory evaluation is {latest.date()} (>24 months old)",
                )
            )

    # Upsert each conflict by (ingredient_id, conflict_type)
    persisted: list[Conflict] = []
    for ctype, severity, summary in detected:
        existing = db.scalar(
            select(Conflict).where(
                Conflict.ingredient_id == ingredient.id,
                Conflict.conflict_type == ctype.value,
            )
        )
        if existing:
            existing.severity = severity.value
            existing.summary = summary
            existing.resolved = False
            persisted.append(existing)
        else:
            conflict = Conflict(
                ingredient_id=ingredient.id,
                conflict_type=ctype.value,
                severity=severity.value,
                summary=summary,
            )
            db.add(conflict)
            persisted.append(conflict)

    db.flush()
    return persisted
