"""Index curated products into ChromaDB 'products' collection.

Genera ingredient profile text por producto y embeddea con BGE-M3.
Corre después de compute_clean_scores.py.

Supports batch mode to avoid OOM on large catalogs:
    cd backend && python -m scripts.index_products_chroma --batch-size 500
    cd backend && python -m scripts.index_products_chroma --batch-size 500 --offset 500
    cd backend && python -m scripts.index_products_chroma --batch-size 500 --offset 1000
    ...

Sin args: corre todo de una vez (comportamiento original).
"""
import argparse
import asyncio
import logging
import threading
import time

from sqlalchemy import func, select

from app.config import get_settings
from app.models import Product
from app.models.base import SessionLocal
from app.services.embeddings import embed_text
from app.services.rag import build_product_profile, get_products_collection
from app.core.semaphore import semaphore_from_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _start_heartbeat(interval: int = 30) -> threading.Event:
    """Imprime un '.' cada `interval` segundos para mantener vivo el stream del proceso."""
    stop = threading.Event()

    def _beat() -> None:
        while not stop.wait(interval):
            print(".", end="", flush=True)

    t = threading.Thread(target=_beat, daemon=True)
    t.start()
    return stop


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--batch-size",
        type=int,
        default=0,
        help="Productos por ejecución. 0 = sin límite (procesa todo).",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Índice de inicio (para reanudar). Default 0.",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    settings = get_settings()
    heartbeat = _start_heartbeat(30)
    db = SessionLocal()
    collection = get_products_collection(settings)

    try:
        base_query = select(Product).where(Product.category.isnot(None)).order_by(Product.id)

        total = db.scalar(
            select(func.count()).select_from(
                select(Product).where(Product.category.isnot(None)).subquery()
            )
        )
        logger.info("Total productos con categoría: %d", total)

        # Aplica offset y limit solo si se especificaron
        query = base_query.offset(args.offset)
        if args.batch_size > 0:
            query = query.limit(args.batch_size)

        products = list(db.scalars(query))
        end = args.offset + len(products)
        logger.info(
            "Indexando productos %d–%d de %d...",
            args.offset + 1,
            end,
            total,
        )

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
                        "semaphore_precomputed": semaphore_from_score(product.clean_score).value,
                    }
                ],
            )
            if (i + 1) % 50 == 0:
                logger.info("  %d/%d del batch...", i + 1, len(products))

        logger.info("Done. %d productos indexados (offset=%d).", len(products), args.offset)

        if args.batch_size > 0 and end < total:
            logger.info(
                "Quedan %d productos. Corre con --offset %d para continuar.",
                total - end,
                end,
            )

    finally:
        heartbeat.set()
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
