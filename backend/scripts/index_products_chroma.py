"""Index curated products into ChromaDB 'products' collection.

Generates ingredient profile text per product and embeds with BGE-M3.
Run after compute_clean_scores.py.

Usage:
    cd backend && python -m scripts.index_products_chroma
"""
import asyncio
import logging

from sqlalchemy import select

from app.config import get_settings
from app.models import Product
from app.models.base import SessionLocal
from app.services.embeddings import embed_text
from app.services.rag import build_product_profile, get_products_collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _semaphore(clean_score: int) -> str:
    if clean_score == 0:
        return "BLUE"
    if clean_score <= 2:
        return "YELLOW"
    if clean_score <= 4:
        return "ORANGE"
    return "RED"


async def main():
    settings = get_settings()
    db = SessionLocal()
    collection = get_products_collection(settings)

    try:
        products = list(db.scalars(select(Product).where(Product.category.isnot(None))))
        logger.info("Indexing %d products into ChromaDB 'products' collection...", len(products))

        for i, product in enumerate(products):
            profile = build_product_profile(product)
            embedding = await embed_text(profile, settings)
            collection.upsert(
                ids=[product.barcode],
                documents=[profile],
                embeddings=[embedding],
                metadatas=[
                    {
                        "barcode": product.barcode,
                        "category": product.category or "",
                        "clean_score": product.clean_score,
                        "semaphore_precomputed": _semaphore(product.clean_score),
                    }
                ],
            )
            if (i + 1) % 50 == 0:
                logger.info("  %d/%d indexed...", i + 1, len(products))

        logger.info("Done. %d products indexed.", len(products))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
