"""Seed the RAG stack: ingest FDA / EFSA / Codex records into SQL + Chroma.

By default reads `backend/data/seed/additives.json` (curated, offline-safe).
Pass `--live` to hit the real upstream sources (FDA Excel, EFSA Zenodo,
Codex GSFA scraping) — requires network access and may take minutes.

Usage:
    cd backend && python -m scripts.seed_rag              # curated (default)
    cd backend && python -m scripts.seed_rag --live       # live fetch
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.base import get_engine
from app.services.conflicts import detect_conflicts
from app.services.ingestion import codex_gsfa, efsa_zenodo, fda_eafus
from app.services.ingestion.common import IngestionRecord
from app.models import Ingredient
from sqlalchemy import select

logger = logging.getLogger(__name__)

SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "seed" / "additives.json"


def load_curated() -> dict[str, list[IngestionRecord]]:
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))

    fda = [
        IngestionRecord(
            canonical_name=row["canonical_name"],
            cas_number=row.get("cas_number"),
            status=row.get("status", "APPROVED"),
            synonyms=row.get("synonyms", []),
        )
        for row in data["fda_eafus"]
    ]

    efsa = []
    for row in data["efsa"]:
        evaluated = None
        if row.get("evaluated_at"):
            try:
                evaluated = datetime.fromisoformat(row["evaluated_at"]).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        efsa.append(
            IngestionRecord(
                canonical_name=row["name"],
                cas_number=row.get("cas"),
                e_number=row.get("e_number"),
                status=row.get("conclusion", "UNDER REVIEW"),
                hazard_note=row.get("hazard"),
                evaluated_at=evaluated,
            )
        )

    codex = [
        IngestionRecord(
            canonical_name=row["name"],
            e_number=f"E{row['ins']}" if row.get("ins") else None,
            status=row.get("status", "APPROVED"),
            usage_limits=row.get("usage"),
        )
        for row in data["codex"]
    ]

    return {"fda": fda, "efsa": efsa, "codex": codex}


async def run_curated(db: Session) -> None:
    settings = get_settings()
    records = load_curated()

    await fda_eafus.run(db, settings, records=records["fda"])
    await efsa_zenodo.run(db, settings, records=records["efsa"])
    await codex_gsfa.run(db, settings, records=records["codex"])

    # Conflict detection after all sources landed
    all_ingredients = list(db.scalars(select(Ingredient)))
    total_conflicts = 0
    for ing in all_ingredients:
        conflicts = detect_conflicts(ing, db)
        total_conflicts += len(conflicts)
    db.commit()
    logger.info("Detected %d conflicts across %d ingredients", total_conflicts, len(all_ingredients))


async def run_live(db: Session) -> None:
    settings = get_settings()
    logger.info("Live ingestion — hitting upstream sources (may take several minutes)")
    for name, coro in [
        ("FDA EAFUS", fda_eafus.run(db, settings)),
        ("EFSA Zenodo", efsa_zenodo.run(db, settings)),
        ("Codex GSFA", codex_gsfa.run(db, settings)),
    ]:
        try:
            await coro
        except Exception as exc:
            logger.warning("PARTIAL FAILURE — %s skipped: %s", name, exc)

    all_ingredients = list(db.scalars(select(Ingredient)))
    for ing in all_ingredients:
        detect_conflicts(ing, db)
    db.commit()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description="Seed BioShield RAG stack")
    parser.add_argument("--live", action="store_true", help="Fetch from upstream instead of curated seed")
    args = parser.parse_args()

    engine = get_engine()
    with Session(engine) as db:
        if args.live:
            asyncio.run(run_live(db))
        else:
            asyncio.run(run_curated(db))

    print("✓ Seed complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
