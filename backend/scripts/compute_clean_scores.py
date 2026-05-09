"""Compute and persist clean_score for all products in DB.

clean_score = number of flagged ingredients detected via regulatory_status.
Lower = cleaner. Run after loading the curated product dataset.

Usage:
    cd backend && python -m scripts.compute_clean_scores
"""
import logging
from sqlalchemy import select

from app.models import Ingredient, Product, RegulatoryStatus
from app.models.base import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_BANNED_STATUSES = {"Banned", "Restricted"}


def compute_clean_score(product_ingredients: list[str], db) -> int:
    score = 0
    for ing_name in product_ingredients:
        ing = db.scalar(
            select(Ingredient).where(Ingredient.canonical_name.ilike(ing_name))
        )
        if ing is None:
            continue
        statuses = list(
            db.scalars(
                select(RegulatoryStatus).where(RegulatoryStatus.ingredient_id == ing.id)
            )
        )
        if any(s.status in _BANNED_STATUSES for s in statuses):
            score += 1
    return score


def main():
    db = SessionLocal()
    try:
        products = list(db.scalars(select(Product)))
        logger.info("Computing clean_score for %d products...", len(products))
        for product in products:
            # Ingredient names are loaded from the curated data source.
            # Populate this list from your CSV or product_ingredients table.
            ingredients: list[str] = []
            product.clean_score = compute_clean_score(ingredients, db)
        db.commit()
        logger.info("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
