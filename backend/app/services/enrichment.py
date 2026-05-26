"""Scan → Product Enrichment Service."""

from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Ingredient, Product, RegulatoryStatus, ScanHistory
from app.schemas.models import IngredientResult
from app.services.embeddings import embed_text
from app.services.rag import build_product_profile, get_products_collection
from app.services.semaphore import semaphore_from_score

logger = logging.getLogger(__name__)

_BANNED_STATUSES = {"BANNED", "RESTRICTED"}
_MIN_CONFIDENCE = 0.8


def should_enrich(product: Product) -> bool:
    return product.ingredients_json is None and not product.barcode.startswith("photo-")


def _compute_clean_score(canonical_names: list[str], db: Session) -> int:
    score = 0
    for name in canonical_names:
        ing = db.scalar(select(Ingredient).where(Ingredient.canonical_name.ilike(name)))
        if ing is None:
            continue
        statuses = list(
            db.scalars(select(RegulatoryStatus).where(RegulatoryStatus.ingredient_id == ing.id))
        )
        if any(s.status in _BANNED_STATUSES for s in statuses):
            score += 1
    return score


async def _reindex_chroma(product: Product, settings: Settings) -> None:
    collection = get_products_collection(settings)
    profile = build_product_profile(product)
    embedding = await embed_text(profile, settings)
    collection.upsert(
        ids=[product.barcode],
        documents=[profile],
        embeddings=[embedding],  # type: ignore[arg-type]
        metadatas=[
            {
                "barcode": product.barcode,
                "category": product.category or "",
                "clean_score": product.clean_score,
                "semaphore_precomputed": semaphore_from_score(product.clean_score).value,
            }
        ],
    )


async def enrich_product(
    barcode: str,
    resolved: list[IngredientResult],
    avg_confidence: float,
    source: str,
    db: Session,
    settings: Settings,
) -> None:
    if avg_confidence < _MIN_CONFIDENCE:
        return

    product = db.scalar(select(Product).where(Product.barcode == barcode).with_for_update())
    if product is None or not should_enrich(product):
        return

    canonical_names = [r.canonical_name for r in resolved if r.canonical_name]
    product.ingredients_json = canonical_names
    product.ingredients_source = source
    product.ingredients_confidence = avg_confidence
    product.clean_score = _compute_clean_score(canonical_names, db)
    db.commit()

    if product.category:
        await _reindex_chroma(product, settings)


async def try_off_lookup(
    name: str | None,
    brand: str | None,
    pseudo_barcode: str,
    db: Session,
    settings: Settings,
) -> None:
    if not name:
        return

    from app.services.off_client import off_lookup_barcode

    barcode = await off_lookup_barcode(name, brand, settings)
    if not barcode:
        return

    photo_product = db.scalar(select(Product).where(Product.barcode == pseudo_barcode))

    real_product = db.scalar(select(Product).where(Product.barcode == barcode))
    if real_product is None:
        real_product = Product(barcode=barcode, name=name, brand=brand)
        db.add(real_product)
    db.flush()

    if should_enrich(real_product):
        history = db.scalar(
            select(ScanHistory)
            .where(ScanHistory.product_barcode == pseudo_barcode)
            .order_by(ScanHistory.scanned_at.desc())
        )
        if history and history.result_json and (history.confidence_score or 0) >= _MIN_CONFIDENCE:
            resolved = [
                IngredientResult.model_validate(i)
                for i in history.result_json.get("ingredients", [])
            ]
            await enrich_product(
                barcode, resolved, history.confidence_score or 0.0, "off", db, settings
            )

    if photo_product:
        photo_product.needs_barcode_link = False
    db.commit()


async def link_photo_to_barcode(
    pseudo_barcode: str,
    real_barcode: str,
    user_id: str,
    db: Session,
    settings: Settings,
) -> Product:
    history = db.scalar(
        select(ScanHistory)
        .where(
            ScanHistory.product_barcode == pseudo_barcode,
            ScanHistory.user_id == user_id,
        )
        .order_by(ScanHistory.scanned_at.desc())
    )
    if not history:
        raise HTTPException(status_code=403, detail="Scan no encontrado o no autorizado.")

    photo_product = db.scalar(select(Product).where(Product.barcode == pseudo_barcode))

    real_product = db.scalar(select(Product).where(Product.barcode == real_barcode))
    if real_product is None:
        real_product = Product(
            barcode=real_barcode,
            name=photo_product.name if photo_product else None,
        )
        db.add(real_product)
    db.flush()

    if history.result_json and should_enrich(real_product):
        resolved = [
            IngredientResult.model_validate(i) for i in history.result_json.get("ingredients", [])
        ]
        avg_conf = history.confidence_score or 0.0
        if avg_conf >= _MIN_CONFIDENCE:
            await enrich_product(real_barcode, resolved, avg_conf, "scan", db, settings)

    if photo_product:
        photo_product.needs_barcode_link = False
    db.commit()
    return real_product
