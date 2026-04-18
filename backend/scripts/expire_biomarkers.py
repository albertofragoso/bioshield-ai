"""CLI: delete expired biomarker rows.

Intended to run on a schedule (Render cron / GitHub Actions / cron). Per
PRD §5, biomarkers expire 180 days after upload.

Usage:
    cd backend && python -m scripts.expire_biomarkers
"""

import sys

from sqlalchemy.orm import Session

from app.models.base import get_engine
from app.services.maintenance import expire_biomarkers


def main() -> int:
    engine = get_engine()
    with Session(engine) as db:
        removed = expire_biomarkers(db)
    print(f"Removed {removed} expired biomarker row(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
