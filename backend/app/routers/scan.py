"""Scan endpoints: barcode lookup + photo OCR fallback.

Both routes invoke the LangGraph pipeline (`agents.graph.build_scan_graph`)
and persist a ScanHistory row. Product is upserted on barcode matches to
avoid duplicating product metadata per scan.
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.graph import build_scan_graph
from app.config import Settings, get_settings
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import limiter
from app.models import Ingredient, Product, ScanHistory, User
from app.models.base import get_db
from app.schemas.models import (
    BarcodeRequest,
    IngredientResult,
    PhotoScanRequest,
    ScanResponse,
    SemaphoreColor,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/ping")
def ping(current_user: User = Depends(get_current_user)):
    """Smoke-test endpoint — verifies auth dependency is wired correctly."""
    return {"user_id": current_user.id}


# ─────────────────────────────────────────────
# POST /scan/barcode
# ─────────────────────────────────────────────

@router.post("/barcode", response_model=ScanResponse)
@limiter.limit("20/minute")
async def scan_barcode(
    request: Request,
    body: BarcodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    graph = build_scan_graph(db, settings)
    final_state = await graph.ainvoke(
        {"barcode": body.barcode, "user_id": current_user.id}
    )

    if not (final_state.get("extracted_ingredients") or []):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado. Intenta con /scan/photo.",
        )

    product = _upsert_product(
        db,
        barcode=body.barcode,
        name=final_state.get("product_name"),
        brand=final_state.get("product_brand"),
        image_url=final_state.get("product_image_url"),
    )
    _persist_scan_history(db, current_user, product.barcode, final_state)
    db.commit()

    return _build_response(final_state, product.barcode, product.name)


# ─────────────────────────────────────────────
# POST /scan/photo
# ─────────────────────────────────────────────

@router.post("/photo", response_model=ScanResponse)
@limiter.limit("20/minute")
async def scan_photo(
    request: Request,
    body: PhotoScanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    graph = build_scan_graph(db, settings)
    final_state = await graph.ainvoke(
        {"image_b64": body.image_base64, "user_id": current_user.id}
    )

    if final_state.get("error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=final_state["error"],
        )
    if not (final_state.get("extracted_ingredients") or []):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se pudo extraer lista de ingredientes de la imagen.",
        )

    # Photo scans have no real barcode — synthesize a marker so the FK holds.
    pseudo_barcode = f"photo:{uuid4().hex[:16]}"
    product = _upsert_product(db, barcode=pseudo_barcode, name=None, brand=None, image_url=None)
    _persist_scan_history(db, current_user, product.barcode, final_state)
    db.commit()

    return _build_response(final_state, product.barcode, product.name)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _upsert_product(
    db: Session,
    *,
    barcode: str,
    name: str | None,
    brand: str | None,
    image_url: str | None,
) -> Product:
    product = db.scalar(select(Product).where(Product.barcode == barcode))
    if product:
        if name and not product.name:
            product.name = name
        if brand and not product.brand:
            product.brand = brand
        if image_url and not product.image_url:
            product.image_url = image_url
    else:
        product = Product(barcode=barcode, name=name, brand=brand, image_url=image_url)
        db.add(product)
    db.flush()
    return product


def _persist_scan_history(
    db: Session,
    user: User,
    product_barcode: str,
    state: dict,
) -> None:
    resolved: list[IngredientResult] = state.get("resolved") or []
    semaphore = state.get("semaphore", SemaphoreColor.GRAY)

    primary_ingredient_id: str | None = None
    for ing in resolved:
        if ing.canonical_name:
            row = db.scalar(
                select(Ingredient).where(Ingredient.canonical_name == ing.canonical_name)
            )
            if row:
                primary_ingredient_id = row.id
                break

    avg_confidence = (
        sum(ing.confidence_score for ing in resolved) / len(resolved)
        if resolved
        else 0.0
    )

    db.add(
        ScanHistory(
            user_id=user.id,
            product_barcode=product_barcode,
            ingredient_id=primary_ingredient_id,
            semaphore_result=(
                semaphore.value if isinstance(semaphore, SemaphoreColor) else str(semaphore)
            ),
            confidence_score=avg_confidence,
            conflict_severity=state.get("conflict_severity"),
        )
    )


def _build_response(state: dict, barcode: str, product_name: str | None) -> ScanResponse:
    return ScanResponse(
        product_barcode=barcode,
        product_name=product_name or state.get("product_name"),
        semaphore=state.get("semaphore", SemaphoreColor.GRAY),
        ingredients=state.get("resolved") or [],
        conflict_severity=state.get("conflict_severity"),
        source=state.get("source", "barcode"),
        scanned_at=datetime.now(timezone.utc),
    )
