"""Load curated products from off_products.json into the products table.

Upsert logic is dialect-agnostic (SQLite + PostgreSQL compatible).
Safe to run multiple times — subsequent runs update existing records.

Prerequisite: run ingest_off_mexico.py first.

Usage:
    cd backend && python -m scripts.load_products_to_db
"""
import json
import logging
from pathlib import Path

from sqlalchemy import select

from app.models import Product
from app.models.base import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INPUT_PATH = Path(__file__).parent / "data" / "off_products.json"
BATCH_SIZE = 100


def main() -> None:
    if not INPUT_PATH.exists():
        logger.error(
            "Input not found: %s — run ingest_off_mexico.py first", INPUT_PATH
        )
        return

    with INPUT_PATH.open() as f:
        products = json.load(f)

    logger.info("Loading %d products into DB...", len(products))
    db = SessionLocal()
    inserted = updated = errors = 0

    try:
        for i, p in enumerate(products):
            try:
                existing = db.scalar(
                    select(Product).where(Product.barcode == p["barcode"])
                )
                if existing:
                    existing.name = p.get("name")
                    existing.brand = p.get("brand")
                    existing.category = p.get("category")
                    existing.image_url = p.get("image_url")
                    existing.ingredients_json = p.get("ingredients_json")
                    existing.ingredients_source = p.get("ingredients_source")
                    updated += 1
                else:
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
            except Exception as exc:
                logger.warning("Error on barcode %s: %s", p.get("barcode"), exc)
                errors += 1

            if (i + 1) % BATCH_SIZE == 0:
                db.commit()
                logger.info("  %d/%d processed...", i + 1, len(products))

        db.commit()
        logger.info(
            "Done. inserted=%d updated=%d errors=%d", inserted, updated, errors
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
