"""Load products from all ingestion sources into the products table.

Merges off_mx_products.json, off_global_products.json, and usda_products.json.
Priority order: MX > Global > USDA — if a barcode already exists, it is skipped.
Safe to run multiple times — idempotent.

Prerequisites:
    python -m scripts.ingest_off_mexico
    python -m scripts.ingest_off_global
    python -m scripts.ingest_usda

Usage:
    cd backend && python -m scripts.load_all_products
"""
import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product
from app.models.base import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SOURCES = [
    Path(__file__).parent / "data" / "off_mx_products.json",      # prioridad 1
    Path(__file__).parent / "data" / "off_global_products.json",  # prioridad 2
    Path(__file__).parent / "data" / "usda_products.json",        # prioridad 3
]

BATCH_SIZE = 100


def _load_sources(sources: list[Path], db: Session) -> tuple[int, int]:
    """Carga productos de múltiples JSON en orden de prioridad.

    Si el barcode ya existe en DB, se hace skip (no update), preservando
    la fuente de mayor prioridad.

    Retorna (inserted, skipped).
    """
    inserted = skipped = errors = 0
    batch_count = 0

    for source in sources:
        if not source.exists():
            logger.warning("Source not found, skipping: %s", source)
            continue

        products = json.loads(source.read_text())
        logger.info("Loading %d products from %s...", len(products), source.name)

        for p in products:
            try:
                existing = db.scalar(
                    select(Product).where(Product.barcode == p["barcode"])
                )
                if existing:
                    skipped += 1
                    continue

                db.add(
                    Product(
                        barcode=p["barcode"],
                        name=p.get("name"),
                        brand=p.get("brand"),
                        category=p.get("category"),
                        image_url=p.get("image_url"),
                        ingredients_json=p.get("ingredients_json"),
                        ingredients_source=p.get("ingredients_source"),
                    )
                )
                inserted += 1
                batch_count += 1

                if batch_count % BATCH_SIZE == 0:
                    db.commit()
                    batch_count = 0
                    logger.info("  %d inserted so far...", inserted)

            except Exception as exc:
                logger.warning("Error on barcode %s: %s", p.get("barcode"), exc)
                errors += 1

    db.commit()
    if errors:
        logger.warning("Errors: %d", errors)
    return inserted, skipped


def main() -> None:
    db = SessionLocal()
    try:
        inserted, skipped = _load_sources(SOURCES, db)
        logger.info("Done. inserted=%d skipped=%d", inserted, skipped)
    finally:
        db.close()


if __name__ == "__main__":
    main()
