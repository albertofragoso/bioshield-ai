"""TypedDict state shared across LangGraph nodes in the scan pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from app.services.biomarker_rules import DecryptedBiomarker

from app.schemas.models import (
    IngredientConflict,
    IngredientResult,
    PersonalizedInsight,
    SemaphoreColor,
)


class ScanState(TypedDict, total=False):
    # ─── Inputs ───
    barcode: str | None
    image_b64: str | None
    user_id: str
    source: str  # "barcode" | "photo"

    # ─── Intermediate ───
    product_name: str | None
    product_brand: str | None
    product_image_url: str | None
    extracted_ingredients: list[str]
    extracted_barcode: str | None
    resolved: list[IngredientResult]
    rag_context_by_ingredient: dict[str, str]
    biomarkers: list[DecryptedBiomarker] | None
    conflicts_by_ingredient: dict[str, list[IngredientConflict]]
    personalized_insights: list[PersonalizedInsight]

    # ─── Output ───
    semaphore: SemaphoreColor
    conflict_severity: str | None
    scanned_at: datetime
    error: str | None
