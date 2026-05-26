"""Alternative matching engine — Fase 2.

Hybrid C: SQL first pass (category) → ChromaDB re-rank → biomarker filter.
No LangGraph at load time — only triggered on "Ver análisis completo" tap.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Product, ScanHistory
from app.schemas.models import (
    AlternativeItem,
    AlternativeProductOut,
    AlternativesResponse,
    AlternativeTopPick,
    ScannedProductSummary,
    SemaphoreColor,
)
from app.services.biomarker_rules import excludes_for, keywords_for
from app.services.semaphore import semaphore_from_score
from app.services.embeddings import embed_text
from app.services.rag import get_products_collection

logger = logging.getLogger(__name__)

_AVATAR_FROM_SEMAPHORE: dict[str, str] = {
    "BLUE": "blue",
    "YELLOW": "yellow",
    "ORANGE": "orange",
    "RED": "red",
    "GRAY": "gray",
}


def _avatar_from_semaphore(sem: str) -> str:
    return _AVATAR_FROM_SEMAPHORE.get(sem, "gray")


def _compatibility_pct(clean_score: int, max_score: int, n_conflicts: int) -> int:
    if max_score == 0:
        base = 100.0
    else:
        base = (1 - clean_score / max_score) * 100
    return max(0, round(base - n_conflicts * 10))


def _biomarker_conflicts(
    product_ingredients: list[str],
    active_biomarkers: list[str],
) -> list[str]:
    """Return human-readable conflict strings for flagged ingredient/biomarker pairs."""
    conflicts: list[str] = []
    ingredients_lower = [i.lower() for i in product_ingredients]
    for biomarker in active_biomarkers:
        keywords = keywords_for(biomarker)
        excludes = excludes_for(biomarker)
        for kw in keywords:
            if any(kw in ing and not any(ex in ing for ex in excludes) for ing in ingredients_lower):
                conflicts.append(f"{biomarker.upper()} · contiene {kw}")
                break  # one label per biomarker; display-only, not exhaustive matching
    return conflicts


def _clean_ingredient_labels(all_ingredients: list[str], flagged: list[str]) -> list[str]:
    """Return up to 3 'Sin X' labels for clean (non-flagged) ingredients."""
    flagged_lower = [f.lower() for f in flagged]
    labels: list[str] = []
    for ing in all_ingredients:
        if ing.lower() not in flagged_lower and len(labels) < 3:
            labels.append(f"Sin {ing.lower()}")
    return labels or ["Ingredientes más limpios"]


async def get_active_biomarkers(
    user_id: str, db: Session, settings: Settings
) -> tuple[bool, list[str]]:
    """Returns (has_biomarkers, list_of_canonical_names_with_abnormal_classification)."""
    from datetime import UTC, datetime  # noqa: PLC0415

    from app.models import Biomarker  # noqa: PLC0415
    from app.services.crypto import decrypt_biomarker  # noqa: PLC0415

    row = db.scalar(
        select(Biomarker).where(
            Biomarker.user_id == user_id,
            Biomarker.expires_at > datetime.now(UTC),
        )
    )
    if row is None:
        return False, []
    try:
        data = decrypt_biomarker(row.encrypted_data, row.encryption_iv, settings.aes_key)
        biomarkers = data.get("biomarkers", [])
        active = [
            b["name"].lower()
            for b in biomarkers
            if b.get("classification", "").lower() in ("high", "low")
        ]
        return True, active
    except Exception as exc:
        logger.warning("Failed to decrypt biomarkers for user %s: %s", user_id, exc)
        return True, []


async def find_alternatives(
    barcode: str,
    db: Session,
    settings: Settings,
    active_biomarkers: list[str],
    has_biomarkers: bool,
) -> AlternativesResponse | None:
    """Main entrypoint. Returns None if no scan history found for the barcode."""

    # ── 1. Load scan result_json ──────────────────────────────────────────────
    scan_row = db.scalar(
        select(ScanHistory)
        .where(
            ScanHistory.product_barcode == barcode,
            ScanHistory.result_json.isnot(None),
        )
        .order_by(ScanHistory.scanned_at.desc())
    )
    if scan_row is None:
        return None

    result: dict = scan_row.result_json  # type: ignore[assignment]
    scanned_semaphore = result.get("semaphore", "GRAY")
    product_name = result.get("product_name")
    all_ingredients: list[str] = [i["name"] for i in result.get("ingredients", [])]
    flagged_ingredients: list[str] = [
        i["name"] for i in result.get("ingredients", []) if i.get("conflicts")
    ]

    # ── 2. Load scanned product to get category + clean_score ────────────────
    scanned_product = db.scalar(select(Product).where(Product.barcode == barcode))
    category = scanned_product.category if scanned_product else None

    fallback_used = category is None

    # ── 3. SQL first pass ────────────────────────────────────────────────────
    # No filtramos por clean_score aquí — ChromaDB reordena por similaridad
    if not fallback_used:
        candidates = list(
            db.scalars(
                select(Product)
                .where(
                    Product.category == category,
                    Product.barcode != barcode,
                )
                .order_by(Product.clean_score.asc())
                .limit(20)
            )
        )
    else:
        candidates = []

    # ── 4. ChromaDB re-rank ──────────────────────────────────────────────────
    reranked: list[Product] = candidates

    # Activar cuando hay ingredientes problemáticos O cuando SQL no devolvió candidatos
    if flagged_ingredients or not candidates:
        if flagged_ingredients:
            query_text = (
                f"producto: {product_name or category or 'alimento'} "
                f"sin {' sin '.join(flagged_ingredients[:5])}"
            )
        else:
            query_text = (
                f"producto: {product_name or 'alimento'} "
                f"ingredientes: {', '.join(all_ingredients[:8])}"
            )
        try:
            embedding = await embed_text(query_text, settings)
            collection = get_products_collection(settings)
            if candidates:
                candidate_barcodes = [c.barcode for c in candidates]
                where_filter: dict | None = {"barcode": {"$in": candidate_barcodes}}
                n_results = min(5, len(candidates))
            else:
                where_filter = None
                n_results = 5
            results = collection.query(
                query_embeddings=[embedding],  # type: ignore[arg-type]
                n_results=n_results,
                where=where_filter,  # type: ignore[arg-type]
                include=["metadatas", "distances"],  # type: ignore[list-item]
            )
            metadatas = results.get("metadatas") or []
            ranked_barcodes: list[str] = [
                str(m["barcode"])
                for m in (metadatas[0] if metadatas else [])  # type: ignore[index]
            ]
            if candidates:
                barcode_to_product = {c.barcode: c for c in candidates}
                reranked = [
                    barcode_to_product[b] for b in ranked_barcodes if b in barcode_to_product
                ]
                seen = set(ranked_barcodes)
                reranked += [c for c in candidates if c.barcode not in seen]
            else:
                # Fallback: barcodes retornados por ChromaDB → buscar en DB
                fetched = list(
                    db.scalars(select(Product).where(Product.barcode.in_(ranked_barcodes)))
                )
                barcode_to_product = {p.barcode: p for p in fetched}
                reranked = [
                    barcode_to_product[b] for b in ranked_barcodes if b in barcode_to_product
                ]
        except Exception as exc:
            logger.warning("ChromaDB re-rank failed, falling back to SQL order: %s", exc)

    top5 = reranked[:5]

    # ── 5. Select top pick via biomarker filter ───────────────────────────────
    max_score = max((c.clean_score for c in top5), default=1) or 1
    top_pick: AlternativeTopPick | None = None
    remaining: list[Product] = list(top5)

    for candidate in top5:
        cand_ingredients = candidate.ingredients_json or []
        conflicts = _biomarker_conflicts(cand_ingredients, active_biomarkers)
        if not conflicts or not has_biomarkers:
            semaphore = semaphore_from_score(candidate.clean_score)
            clean_labels = _clean_ingredient_labels(all_ingredients, flagged_ingredients)
            top_pick = AlternativeTopPick(
                product=AlternativeProductOut(
                    barcode=candidate.barcode,
                    name=candidate.name,
                    brand=candidate.brand,
                    clean_score=candidate.clean_score,
                ),
                clean_ingredients=clean_labels,
                biomarker_conflicts=conflicts,
                compatibility_pct=_compatibility_pct(
                    candidate.clean_score, max_score, len(conflicts)
                ),
                avatar_variant=_avatar_from_semaphore(semaphore),
            )
            remaining = [c for c in top5 if c.barcode != candidate.barcode]
            break

    # ── 6. Build secondary list ───────────────────────────────────────────────
    alternatives: list[AlternativeItem] = []
    for candidate in remaining[:4]:
        sem = semaphore_from_score(candidate.clean_score)
        alternatives.append(
            AlternativeItem(
                product=AlternativeProductOut(
                    barcode=candidate.barcode,
                    name=candidate.name,
                    brand=candidate.brand,
                    clean_score=candidate.clean_score,
                ),
                avatar_variant=_avatar_from_semaphore(sem),
                semaphore_precomputed=sem,
            )
        )

    return AlternativesResponse(
        scanned_product=ScannedProductSummary(
            barcode=barcode,
            name=product_name,
            brand=scanned_product.brand if scanned_product else None,
            semaphore=SemaphoreColor(scanned_semaphore),
            clean_score=(scanned_product.clean_score or 0) if scanned_product else 0,
        ),
        top_pick=top_pick,
        alternatives=alternatives,
        has_biomarkers=has_biomarkers,
        fallback_used=fallback_used,
    )
