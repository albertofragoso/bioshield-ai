"""Compute and persist clean_score for all enriched products in DB.

clean_score = número de ingredientes con estatus Banned o Restricted.
Solo procesa productos que ya tienen ingredients_json poblado (enriquecidos
vía scan o importación). Productos sin ingredients_json se saltan.

Usage:
    cd backend && python -m scripts.compute_clean_scores
"""
import logging

from sqlalchemy import select

from app.models import Product
from app.models.base import SessionLocal
from app.services.enrichment import _compute_clean_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    db = SessionLocal()
    try:
        products = list(
            db.scalars(select(Product).where(Product.ingredients_json.isnot(None)))
        )
        logger.info("Computing clean_score for %d enriched products...", len(products))
        for product in products:
            product.clean_score = _compute_clean_score(product.ingredients_json or [], db)
        db.commit()
        logger.info("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
