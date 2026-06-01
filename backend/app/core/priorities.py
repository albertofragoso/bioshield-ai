# Semantic audit (2026-05-26): analysis.py used BANNED:4/RESTRICTED:3/UNDER_REVIEW:2/APPROVED:1
# and HIGH:3/MEDIUM:2/LOW:1. conflicts.py had NO local ranking dicts — it used hardcoded
# ConflictSeverity literals and raw string comparisons. No divergence to reconcile.
# Numeric values are normalized to 0-based here; relative order is identical.

from app.schemas.models import ConflictSeverity, RegulatoryStatus

_STATUS_RANK: dict[RegulatoryStatus, int] = {
    RegulatoryStatus.APPROVED: 0,
    RegulatoryStatus.UNDER_REVIEW: 1,
    RegulatoryStatus.RESTRICTED: 2,
    RegulatoryStatus.BANNED: 3,
}

_SEVERITY_RANK: dict[ConflictSeverity, int] = {
    ConflictSeverity.LOW: 0,
    ConflictSeverity.MEDIUM: 1,
    ConflictSeverity.HIGH: 2,
}


def worst_status(statuses: list[RegulatoryStatus]) -> RegulatoryStatus:
    """Return the highest-severity status from a list. Raises ValueError if list is empty."""
    if not statuses:
        raise ValueError("worst_status called with empty list")
    return max(statuses, key=lambda s: _STATUS_RANK[s])


def worst_severity(severities: list[ConflictSeverity]) -> ConflictSeverity:
    """Return the highest severity from a list. Raises ValueError if list is empty."""
    if not severities:
        raise ValueError("worst_severity called with empty list")
    return max(severities, key=lambda s: _SEVERITY_RANK[s])
