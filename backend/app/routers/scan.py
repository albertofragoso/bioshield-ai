"""Scan endpoints: barcode lookup + photo OCR fallback + OFF contribution.

Both scan routes invoke the LangGraph pipeline (`agents.graph.build_scan_graph`)
and persist a ScanHistory row. Product is upserted on barcode matches to
avoid duplicating product metadata per scan.

/scan/contribute delega el POST a OFF a BackgroundTasks con sesión DB separada.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.graph import build_scan_graph
from app.config import Settings, get_settings
from app.dependencies.token_budget import ENDPOINT_TOKEN_COST, token_budget
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import limiter
from app.models import Ingredient, OFFContribution, Product, ScanHistory, User
from app.models.base import SessionLocal, get_db
from app.schemas.models import (
    AlternativesResponse,
    BarcodeRequest,
    IngredientResult,
    LinkBarcodeRequest,
    OFFContributeRequest,
    OFFContributeResponse,
    PhotoScanRequest,
    ScanHistoryEntry,
    ScanResponse,
    SemaphoreColor,
)
from app.services.off_client import contribute_product, upload_product_image

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/ping")
def ping(current_user: User = Depends(get_current_user)):
    """Smoke-test endpoint — verifies auth dependency is wired correctly."""
    return {"user_id": current_user.id}


# ─────────────────────────────────────────────
# GET /scan/history
# ─────────────────────────────────────────────


@router.get("/history", response_model=list[ScanHistoryEntry])
def get_scan_history(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(ScanHistory, Product.name)
        .join(Product, ScanHistory.product_barcode == Product.barcode)
        .where(ScanHistory.user_id == current_user.id)
        .order_by(ScanHistory.scanned_at.desc())
        .limit(limit)
    ).all()
    return [
        ScanHistoryEntry(
            id=row.ScanHistory.id,
            product_barcode=row.ScanHistory.product_barcode,
            product_name=row.name,
            semaphore=SemaphoreColor(row.ScanHistory.semaphore_result),
            conflict_severity=row.ScanHistory.conflict_severity,
            source="photo" if row.ScanHistory.product_barcode.startswith("photo-") else "barcode",
            scanned_at=row.ScanHistory.scanned_at,
        )
        for row in rows
    ]


# ─────────────────────────────────────────────
# GET /scan/result/{barcode}
# ─────────────────────────────────────────────


@router.get("/result/{barcode}", response_model=ScanResponse)
def get_scan_result(
    barcode: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(ScanHistory)
        .where(
            ScanHistory.product_barcode == barcode,
            ScanHistory.user_id == current_user.id,
            ScanHistory.result_json.isnot(None),
        )
        .order_by(ScanHistory.scanned_at.desc())
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan no encontrado.")
    product = db.scalar(select(Product).where(Product.barcode == barcode))
    response = ScanResponse.model_validate(row.result_json)
    response.show_barcode_cta = product.needs_barcode_link if product else False
    return response


# ─────────────────────────────────────────────
# GET /scan/alternatives/{barcode}  (Fase 2)
# ─────────────────────────────────────────────


@router.get("/alternatives/{barcode}", response_model=AlternativesResponse)
@limiter.limit("10/minute")
async def get_alternatives(
    request: Request,
    barcode: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Return ingredient-based alternatives for a scanned product (Fase 2).

    Semaphore guard is enforced in the frontend — endpoint works for any barcode
    with existing scan history.
    """
    from app.services.alternatives import find_alternatives, get_active_biomarkers  # noqa: PLC0415

    has_biomarkers, active_biomarkers = await get_active_biomarkers(
        str(current_user.id), db, settings
    )
    result = await find_alternatives(
        barcode=barcode,
        db=db,
        settings=settings,
        active_biomarkers=active_biomarkers,
        has_biomarkers=has_biomarkers,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan no encontrado.")
    return result


# ─────────────────────────────────────────────
# POST /scan/barcode
# ─────────────────────────────────────────────


@router.post("/barcode", response_model=ScanResponse)
@limiter.limit("20/minute")
async def scan_barcode(
    request: Request,
    body: BarcodeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _budget: User = Depends(token_budget(ENDPOINT_TOKEN_COST["scan_barcode"])),
):
    graph = build_scan_graph(db, settings)
    final_state = await graph.ainvoke({"barcode": body.barcode, "user_id": current_user.id})

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
    response = _build_response(final_state, product.barcode, product.name)
    _persist_scan_history(db, current_user, product.barcode, final_state, response)
    db.commit()

    resolved: list[IngredientResult] = final_state.get("resolved") or []
    avg_conf = sum(r.confidence_score for r in resolved) / len(resolved) if resolved else 0.0
    if avg_conf >= 0.8:
        background_tasks.add_task(
            _run_enrich_task,
            barcode=body.barcode,
            resolved_json=[r.model_dump(mode="json") for r in resolved],
            avg_confidence=avg_conf,
            source="scan",
            settings=settings,
        )

    return response


# ─────────────────────────────────────────────
# POST /scan/photo
# ─────────────────────────────────────────────


@router.post("/photo", response_model=ScanResponse)
@limiter.limit("20/minute")
async def scan_photo(
    request: Request,
    body: PhotoScanRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _budget: User = Depends(token_budget(ENDPOINT_TOKEN_COST["scan_photo"])),
):
    graph = build_scan_graph(db, settings)
    final_state = await graph.ainvoke({"image_b64": body.image_base64, "user_id": current_user.id})

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

    # Ex.1: Gemini extrajo barcode de la imagen → usar barcode real
    extracted_barcode: str | None = final_state.get("extracted_barcode")
    barcode_to_use = extracted_barcode or f"photo-{uuid4().hex[:16]}"
    show_cta = not bool(extracted_barcode)

    product = _upsert_product(
        db,
        barcode=barcode_to_use,
        name=final_state.get("product_name"),
        brand=None,
        image_url=None,
    )
    if show_cta:
        product.needs_barcode_link = True

    response = _build_response(final_state, product.barcode, product.name)
    response.show_barcode_cta = show_cta
    _persist_scan_history(db, current_user, product.barcode, final_state, response)
    db.commit()

    resolved: list[IngredientResult] = final_state.get("resolved") or []
    avg_conf = sum(r.confidence_score for r in resolved) / len(resolved) if resolved else 0.0

    if extracted_barcode and avg_conf >= 0.8:
        # Ex.1: barcode real disponible → enriquecer directamente
        background_tasks.add_task(
            _run_enrich_task,
            barcode=extracted_barcode,
            resolved_json=[r.model_dump(mode="json") for r in resolved],
            avg_confidence=avg_conf,
            source="scan",
            settings=settings,
        )
    elif show_cta:
        # Ex.2: sin barcode → buscar en OFF por nombre+marca en background
        background_tasks.add_task(
            _run_off_lookup_task,
            name=final_state.get("product_name"),
            brand=final_state.get("product_brand"),
            pseudo_barcode=barcode_to_use,
            settings=settings,
        )

    return response


# ─────────────────────────────────────────────
# POST /scan/photo/{pseudo_barcode}/link  (Fase 2)
# ─────────────────────────────────────────────


@router.post("/photo/{pseudo_barcode}/link", response_model=ScanResponse)
@limiter.limit("10/minute")
async def link_photo_barcode(
    request: Request,
    pseudo_barcode: str,
    body: LinkBarcodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    from app.services.enrichment import link_photo_to_barcode as _link  # noqa: PLC0415

    real_product = await _link(
        pseudo_barcode=pseudo_barcode,
        real_barcode=body.barcode,
        user_id=str(current_user.id),
        db=db,
        settings=settings,
    )

    history = db.scalar(
        select(ScanHistory)
        .where(
            ScanHistory.product_barcode == pseudo_barcode,
            ScanHistory.user_id == current_user.id,
        )
        .order_by(ScanHistory.scanned_at.desc())
    )
    if not history or not history.result_json:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan no encontrado.")

    response = ScanResponse.model_validate(history.result_json)
    response.product_barcode = real_product.barcode
    response.show_barcode_cta = False

    # Persiste ScanHistory para el barcode real; find_alternatives lo necesita.
    existing_real = db.scalar(
        select(ScanHistory)
        .where(
            ScanHistory.product_barcode == real_product.barcode,
            ScanHistory.user_id == current_user.id,
        )
        .order_by(ScanHistory.scanned_at.desc())
    )
    if existing_real is None:
        new_result_json = {**history.result_json, "product_barcode": real_product.barcode}
        new_result_json.pop("show_barcode_cta", None)
        db.add(
            ScanHistory(
                user_id=current_user.id,
                product_barcode=real_product.barcode,
                ingredient_id=history.ingredient_id,
                semaphore_result=history.semaphore_result,
                confidence_score=history.confidence_score or 0.0,
                conflict_severity=history.conflict_severity,
                result_json=new_result_json,
            )
        )
        db.commit()

    return response


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
    response: ScanResponse,
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
        sum(ing.confidence_score for ing in resolved) / len(resolved) if resolved else 0.0
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
            result_json=response.model_dump(
                mode="json", exclude={"show_barcode_cta"}
            ),
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
        scanned_at=datetime.now(UTC),
        personalized_insights=state.get("personalized_insights") or [],
    )


# ─────────────────────────────────────────────
# POST /scan/contribute  (Fase 2 — flujo contributivo OFF)
# ─────────────────────────────────────────────


@router.post("/contribute", response_model=OFFContributeResponse, status_code=202)
@limiter.limit("10/minute")
async def scan_contribute(
    request: Request,
    body: OFFContributeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> OFFContributeResponse:
    if body.scan_history_id is not None:
        owned = db.scalar(
            select(ScanHistory).where(
                ScanHistory.id == str(body.scan_history_id),
                ScanHistory.user_id == current_user.id,
            )
        )
        if owned is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="scan_history_id no pertenece al usuario autenticado",
            )

    ingredients_text = ", ".join(body.ingredients)

    row = OFFContribution(
        user_id=current_user.id,
        scan_history_id=str(body.scan_history_id) if body.scan_history_id else None,
        barcode=body.barcode,
        ingredients_text=ingredients_text,
        status="PENDING",
        consent_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    if settings.off_contrib_sync_for_tests:
        # En tests: reutiliza la sesión del request (misma transacción in-memory)
        await _run_off_contribution_impl(row.id, body, settings, db)
    else:
        background_tasks.add_task(_run_off_contribution, row.id, body, settings)

    return OFFContributeResponse(
        contribution_id=UUID(row.id),
        status="PENDING",
        message="Contribución recibida. Se enviará a Open Food Facts en segundo plano.",
    )


async def _run_off_contribution_impl(
    contribution_id: str,
    body: OFFContributeRequest,
    settings: Settings,
    db: Session,
) -> None:
    """Lógica de contribución OFF — acepta sesión DB como parámetro."""
    ingredients_text = ", ".join(body.ingredients)

    row = db.get(OFFContribution, contribution_id)
    if row is None:
        logger.error("OFFContribution %s not found", contribution_id)
        return

    try:
        result = await contribute_product(body.barcode, ingredients_text, settings)

        image_submitted = False
        if result["success"] and body.image_base64:
            image_submitted = await upload_product_image(body.barcode, body.image_base64, settings)

        row.status = "SUBMITTED" if result["success"] else "FAILED"
        row.off_response_url = result["off_url"]
        row.off_error = result["error"]
        row.image_submitted = image_submitted
        row.submitted_at = datetime.now(UTC)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("Unhandled error in OFF contribution %s: %s", contribution_id, exc)
        row.status = "FAILED"
        row.off_error = str(exc)
        row.submitted_at = datetime.now(UTC)
        db.commit()


async def _run_off_contribution(
    contribution_id: str,
    body: OFFContributeRequest,
    settings: Settings,
) -> None:
    """BackgroundTask wrapper — abre sesión DB propia (la del request ya se cerró)."""
    db = SessionLocal()
    try:
        await _run_off_contribution_impl(contribution_id, body, settings, db)
    finally:
        db.close()


async def _run_enrich_task(
    barcode: str,
    resolved_json: list[dict],
    avg_confidence: float,
    source: str,
    settings,
) -> None:
    from app.services.enrichment import enrich_product  # noqa: PLC0415

    db = SessionLocal()
    try:
        resolved = [IngredientResult.model_validate(i) for i in resolved_json]
        await enrich_product(barcode, resolved, avg_confidence, source, db, settings)
    except Exception as exc:
        logger.error("Enrichment failed for %s: %s", barcode, exc)
    finally:
        db.close()


async def _run_off_lookup_task(
    name: str | None,
    brand: str | None,
    pseudo_barcode: str,
    settings,
) -> None:
    from app.services.enrichment import try_off_lookup  # noqa: PLC0415

    db = SessionLocal()
    try:
        await try_off_lookup(name, brand, pseudo_barcode, db, settings)
    except Exception as exc:
        logger.error("OFF lookup failed for %s: %s", pseudo_barcode, exc)
    finally:
        db.close()
