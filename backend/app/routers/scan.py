"""Scan endpoints: barcode lookup + photo OCR fallback + OFF contribution.

Both scan routes invoke the LangGraph pipeline (`agents.graph.build_scan_graph`)
and persist a ScanHistory row. Product is upserted on barcode matches to
avoid duplicating product metadata per scan.

/scan/contribute delega el POST a OFF a BackgroundTasks con sesión DB separada.
"""

import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.accumulator import ScanStateAccumulator
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
    ScanHistoryEntry,
    ScanResponse,
    ScanShareProjection,
    SemaphoreColor,
)
from app.services.off_client import contribute_product, upload_product_image

logger = logging.getLogger(__name__)


def _serialize(obj) -> str:
    """Serializa a JSON tolerando objetos Pydantic y enums."""

    def _default(o):
        if isinstance(o, BaseModel):
            return o.model_dump(mode="json")
        if hasattr(o, "value"):
            return o.value
        return str(o)

    return json.dumps(obj, default=_default)


router = APIRouter(dependencies=[Depends(get_current_user)])
public_router = APIRouter()


class ShareResponse(BaseModel):
    share_url: str
    expires_at: datetime


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
    response.db_id = row.id
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


@router.post("/barcode")
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
    # Inserta fila pending antes de iniciar el stream para evitar 404 durante streaming
    pending_row = _create_pending_row(db, body.barcode, current_user.id)

    graph = build_scan_graph(db, settings)

    async def _event_stream():
        # Estado acumulado del grafo entre eventos
        accumulator = ScanStateAccumulator(source="barcode")
        # Bandera para saber si el pipeline completó hasta calculate_risk
        finalized = False

        try:
            # Evento inicial con scan_id para que el cliente pueda hacer polling
            yield f"event: init\ndata: {_serialize({'scan_id': pending_row.id, 'product_barcode': body.barcode})}\n\n"

            async for event in graph.astream_events(
                {"barcode": body.barcode, "user_id": current_user.id},
                version="v2",
            ):
                # Solo procesamos eventos de fin de nodo
                if event.get("event") != "on_chain_end":
                    continue

                name = event.get("name", "")
                output = event.get("data", {}).get("output", {})

                if name == "identify_product":
                    # Acumula datos del producto e ingredientes
                    accumulator.apply(output)
                    ingredients = output.get("extracted_ingredients", [])

                    # Si no hay ingredientes, el producto no existe — emite error y termina
                    if not ingredients:
                        error_payload = _serialize(
                            {
                                "message": "Producto no encontrado. Usa /scan/photo para escanear la etiqueta.",
                                "code": "PRODUCT_NOT_FOUND",
                            }
                        )
                        yield f"event: error\ndata: {error_payload}\n\n"
                        return

                    yield f"event: ingredients\ndata: {_serialize({'ingredients': ingredients, 'product_name': output.get('product_name'), 'product_brand': output.get('product_brand')})}\n\n"

                elif name == "personalize":
                    # Acumula insights personalizados
                    accumulator.personalized_insights = output.get("personalized_insights", [])
                    yield f"event: insights\ndata: {_serialize({'personalized_insights': accumulator.personalized_insights})}\n\n"

                elif name == "calculate_risk":
                    # Acumula resultado de riesgo
                    accumulator.apply(output)

                    # Persiste producto y finaliza la fila pending
                    product = _upsert_product(
                        db,
                        barcode=body.barcode,
                        name=accumulator.get("product_name"),
                        brand=accumulator.get("product_brand"),
                        image_url=accumulator.get("product_image_url"),
                    )
                    response = _build_response(accumulator, product.barcode, product.name)
                    _finalize_scan_history(db, pending_row.id, response)
                    finalized = True

                    # Dispara enriquecimiento si hay alta confianza
                    resolved: list[IngredientResult] = accumulator.get("resolved") or []
                    avg_conf = (
                        sum(r.confidence_score for r in resolved if hasattr(r, "confidence_score"))
                        / len(resolved)
                        if resolved
                        else 0.0
                    )
                    if avg_conf >= 0.8:
                        background_tasks.add_task(
                            _run_enrich_task,
                            barcode=body.barcode,
                            resolved_json=[
                                r.model_dump(mode="json")
                                for r in resolved
                                if hasattr(r, "model_dump")
                            ],
                            avg_confidence=avg_conf,
                            source="scan",
                            settings=settings,
                        )

                    semaphore_value = output.get("semaphore", "GRAY")
                    if isinstance(semaphore_value, SemaphoreColor):
                        semaphore_value = semaphore_value.value
                    yield f"event: semaphore\ndata: {_serialize({'semaphore': semaphore_value, 'conflict_severity': output.get('conflict_severity')})}\n\n"

            yield "event: done\ndata: {}\n\n"

        except Exception as exc:  # noqa: BLE001
            logger.error("Error en stream de scan_barcode: %s", exc)
            yield f"event: error\ndata: {_serialize({'detail': str(exc)})}\n\n"
        finally:
            # Limpia la fila pending si el pipeline no llegó a calculate_risk
            if not finalized:
                _mark_scan_failed(db, pending_row.id)

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ─────────────────────────────────────────────
# POST /scan/photo
# ─────────────────────────────────────────────


@router.post("/photo")
@limiter.limit("20/minute")
async def scan_photo(
    request: Request,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _budget: User = Depends(token_budget(ENDPOINT_TOKEN_COST["scan_photo"])),
):
    image_bytes = await file.read()
    photo_id = f"photo-{secrets.token_urlsafe(8)}"

    # Inserta fila pending antes de iniciar el stream para evitar 404 durante streaming
    pending_row = _create_pending_row(db, photo_id, current_user.id)

    graph = build_scan_graph(db, settings)

    async def _event_stream():
        # Estado acumulado del grafo entre eventos
        accumulator = ScanStateAccumulator(source="photo")
        # Bandera para saber si el pipeline completó hasta calculate_risk
        finalized = False

        try:
            # Evento inicial con scan_id y photo_id para que el cliente haga polling
            yield f"event: init\ndata: {_serialize({'scan_id': pending_row.id, 'product_barcode': photo_id})}\n\n"

            async for event in graph.astream_events(
                {"image_bytes": image_bytes, "user_id": current_user.id},
                version="v2",
            ):
                # Solo procesamos eventos de fin de nodo
                if event.get("event") != "on_chain_end":
                    continue

                name = event.get("name", "")
                output = event.get("data", {}).get("output", {})

                if name == "extract_ingredients":
                    # Acumula datos extraídos de la foto
                    accumulator.apply(output)
                    ingredients = output.get("extracted_ingredients", [])

                    yield f"event: ingredients\ndata: {_serialize({'ingredients': ingredients, 'product_name': output.get('product_name'), 'product_brand': output.get('product_brand')})}\n\n"

                elif name == "personalize":
                    # Acumula insights personalizados
                    accumulator.personalized_insights = output.get("personalized_insights", [])
                    yield f"event: insights\ndata: {_serialize({'personalized_insights': accumulator.personalized_insights})}\n\n"

                elif name == "calculate_risk":
                    # Acumula resultado de riesgo
                    accumulator.apply(output)

                    # Persiste producto y finaliza la fila pending
                    product = _upsert_product(
                        db,
                        barcode=photo_id,
                        name=accumulator.get("product_name"),
                        brand=accumulator.get("product_brand"),
                        image_url=None,
                    )
                    product.needs_barcode_link = True
                    response = _build_response(accumulator, product.barcode, product.name)
                    response.show_barcode_cta = True
                    _finalize_scan_history(db, pending_row.id, response)
                    finalized = True

                    # Dispara búsqueda OFF por nombre+marca en background
                    background_tasks.add_task(
                        _run_off_lookup_task,
                        name=accumulator.get("product_name"),
                        brand=accumulator.get("product_brand"),
                        pseudo_barcode=photo_id,
                        settings=settings,
                    )

                    semaphore_value = output.get("semaphore", "GRAY")
                    if isinstance(semaphore_value, SemaphoreColor):
                        semaphore_value = semaphore_value.value
                    yield f"event: semaphore\ndata: {_serialize({'semaphore': semaphore_value, 'conflict_severity': output.get('conflict_severity')})}\n\n"

            yield "event: done\ndata: {}\n\n"

        except Exception as exc:  # noqa: BLE001
            logger.error("Error en stream de scan_photo: %s", exc)
            yield f"event: error\ndata: {_serialize({'detail': str(exc)})}\n\n"
        finally:
            # Limpia la fila pending si el pipeline no llegó a calculate_risk
            if not finalized:
                _mark_scan_failed(db, pending_row.id)

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


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
            result_json=response.model_dump(mode="json", exclude={"show_barcode_cta"}),
        )
    )


def _create_pending_row(
    db: Session,
    barcode: str,
    user_id: str,
) -> ScanHistory:
    # Inserta fila vacía antes de iniciar el stream.
    # Garantiza que /scan/[id] no retorna 404 durante el streaming.
    row = ScanHistory(
        product_barcode=barcode,
        user_id=user_id,
        semaphore_result="PENDING",
        result_json=None,
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _finalize_scan_history(
    db: Session,
    scan_id: str,
    response: ScanResponse,
) -> None:
    # UPDATE de la fila pending con el resultado completo.
    row = db.get(ScanHistory, scan_id)
    if not row:
        return
    row.result_json = response.model_dump(mode="json", exclude={"show_barcode_cta"})
    row.status = "done"
    db.commit()


def _mark_scan_failed(db: Session, scan_id: str) -> None:
    """Marca la fila pending como error si el pipeline no completó."""
    row = db.get(ScanHistory, scan_id)
    if row and row.status == "pending":
        row.status = "error"
        db.commit()


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


# ─────────────────────────────────────────────
# Scan sharing
# ─────────────────────────────────────────────


@router.post("/{scan_id}/share", response_model=ShareResponse)
def create_share_link(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Genera o retorna el share token del scan. Solo el owner puede llamarlo."""
    scan = db.scalar(
        select(ScanHistory).where(
            ScanHistory.id == scan_id,
            ScanHistory.user_id == current_user.id,
        )
    )
    if not scan:
        raise HTTPException(status_code=403)

    if not scan.share_token:
        scan.share_token = secrets.token_urlsafe(24)
        scan.share_expires_at = datetime.now(UTC) + timedelta(days=settings.share_link_ttl_days)
        db.commit()
        db.refresh(scan)

    # share_expires_at is always set by this point (either pre-existing or just assigned above)
    assert scan.share_expires_at is not None
    return ShareResponse(
        share_url=f"{settings.frontend_url}/scan/share/{scan.share_token}",
        expires_at=scan.share_expires_at,
    )


@router.delete("/{scan_id}/share", status_code=204)
def revoke_share_link(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoca el share token. Solo el owner puede llamarlo."""
    scan = db.scalar(
        select(ScanHistory).where(
            ScanHistory.id == scan_id,
            ScanHistory.user_id == current_user.id,
        )
    )
    if not scan:
        raise HTTPException(status_code=403)

    scan.share_token = None
    scan.share_expires_at = None
    db.commit()


@public_router.get("/share/{token}", response_model=ScanShareProjection)
def get_shared_scan(
    token: str,
    db: Session = Depends(get_db),
):
    """Endpoint público sin auth. Retorna la proyección segura del scan."""
    scan = db.scalar(select(ScanHistory).where(ScanHistory.share_token == token))
    if not scan:
        raise HTTPException(status_code=404)

    if scan.share_expires_at:
        # SQLite devuelve naive datetimes; normalizamos a UTC para comparar
        expires = scan.share_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(UTC):
            raise HTTPException(status_code=410, detail="Link expirado")

    result = ScanResponse.model_validate(scan.result_json)
    return ScanShareProjection.model_validate(result.model_dump())
