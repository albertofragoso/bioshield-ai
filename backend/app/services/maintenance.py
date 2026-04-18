"""Maintenance jobs: TTL cleanup for medical data.

Per PRD §5 and architecture.md §1.5: biomarker records expire 180 days after
upload. This module provides the delete operation; scheduling (cron) is
handled externally (Render cron / GitHub Actions).
"""

from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Biomarker


def expire_biomarkers(db: Session) -> int:
    """Delete biomarker rows whose expires_at is in the past.

    Returns the number of rows removed.
    """
    now = datetime.now(timezone.utc)
    result = db.execute(delete(Biomarker).where(Biomarker.expires_at < now))
    db.commit()
    return result.rowcount or 0
