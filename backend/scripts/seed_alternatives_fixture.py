"""Seed 10 curated products for E2E test fixtures.

Inserts products into DB and ChromaDB. Safe to run multiple times (upsert).

Usage:
    cd backend && python -m scripts.seed_alternatives_fixture
"""
import asyncio
import logging

from app.config import get_settings
from app.models import Product
from app.models.base import SessionLocal
from app.services.embeddings import embed_text
from app.services.rag import get_products_collection
from app.services.semaphore import semaphore_from_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FIXTURE_PRODUCTS = [
    {"barcode": "FIX_YOGURT_001", "name": "Activia Natural", "brand": "Danone", "category": "yogurts", "clean_score": 0},
    {"barcode": "FIX_YOGURT_002", "name": "Lala Bio 100", "brand": "Lala", "category": "yogurts", "clean_score": 1},
    {"barcode": "FIX_YOGURT_003", "name": "Alpura Fit", "brand": "Alpura", "category": "yogurts", "clean_score": 2},
    {"barcode": "FIX_YOGURT_BAD", "name": "Yogurt con Sucralosa", "brand": "Generic", "category": "yogurts", "clean_score": 4},
    {"barcode": "FIX_DRINK_001", "name": "Agua Mineral Topo Chico", "brand": "Topo Chico", "category": "bebidas", "clean_score": 0},
    {"barcode": "FIX_DRINK_002", "name": "Nestea Limón", "brand": "Nestlé", "category": "bebidas", "clean_score": 3},
    {"barcode": "FIX_SNACK_001", "name": "Avena Natural", "brand": "Quaker", "category": "cereales", "clean_score": 0},
    {"barcode": "FIX_SNACK_002", "name": "Granola Orgánica", "brand": "Eden", "category": "cereales", "clean_score": 0},
    {"barcode": "FIX_SNACK_BAD", "name": "Cereal Azucarado", "brand": "Generic", "category": "cereales", "clean_score": 5},
    {"barcode": "FIX_NOCAT_001", "name": "Producto Sin Categoría", "brand": "Generic", "category": None, "clean_score": 3},
]


async def main():
    settings = get_settings()
    db = SessionLocal()
    collection = get_products_collection(settings)

    try:
        for p in FIXTURE_PRODUCTS:
            existing = db.scalar(
                __import__("sqlalchemy", fromlist=["select"]).select(Product).where(
                    Product.barcode == p["barcode"]
                )
            )
            if existing:
                existing.name = p["name"]
                existing.brand = p["brand"]
                existing.category = p["category"]
                existing.clean_score = p["clean_score"]
            else:
                db.add(Product(
                    barcode=p["barcode"],
                    name=p["name"],
                    brand=p["brand"],
                    category=p["category"],
                    clean_score=p["clean_score"],
                ))

            if p["category"]:
                profile = f"nombre: {p['name']} | marca: {p['brand']} | categoría: {p['category']}"
                embedding = await embed_text(profile, settings)
                collection.upsert(
                    ids=[p["barcode"]],
                    documents=[profile],
                    embeddings=[embedding],
                    metadatas=[{
                        "barcode": p["barcode"],
                        "category": p["category"],
                        "clean_score": p["clean_score"],
                        "semaphore_precomputed": semaphore_from_score(p["clean_score"]).value,
                    }],
                )

        db.commit()
        logger.info("Seeded %d fixture products.", len(FIXTURE_PRODUCTS))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
