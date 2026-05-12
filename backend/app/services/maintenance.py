"""Maintenance jobs: TTL cleanup for medical data.

Per PRD §5 and architecture.md §1.5: biomarker records expire 180 days after
upload. This module provides the delete operation; scheduling (cron) is
handled externally (Render cron / GitHub Actions).
"""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models import Biomarker, ScanHistory


def expire_biomarkers(db: Session) -> int:
    """Delete biomarker rows whose expires_at is in the past.

    Returns the number of rows removed.
    """
    now = datetime.now(UTC)
    result = db.execute(delete(Biomarker).where(Biomarker.expires_at < now))
    db.commit()
    return result.rowcount or 0  # type: ignore


def scrub_scan_history_insights(db: Session, user_id: str) -> int:
    """Remove personalized_insights from result_json for all scans of a user.

    Does NOT commit — caller controls the transaction.
    Returns the number of rows modified.
    """
    rows = db.scalars(
        select(ScanHistory).where(
            ScanHistory.user_id == user_id,
            ScanHistory.result_json.isnot(None),
        )
    ).all()
    count = 0
    for row in rows:
        if isinstance(row.result_json, dict) and "personalized_insights" in row.result_json:
            row.result_json = {
                k: v for k, v in row.result_json.items() if k != "personalized_insights"
            }
            flag_modified(row, "result_json")
            count += 1
    return count
