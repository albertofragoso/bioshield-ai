"""Gemini 1.5 Flash client: Vision extraction + textual reconciliation.

Vision path uses Structured Outputs (response_schema) so we never parse
JSON by hand — per the project convention.
Reconciler returns IngredientConflict | None from the RAG context.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from typing import Any

import google.generativeai as genai
from fastapi import HTTPException, status
from google.api_core import exceptions as google_exceptions
from pydantic import BaseModel

from app.agents.prompts import EXTRACTOR_PROMPT, RECONCILER_PROMPT
from app.config import Settings
from app.schemas.models import (
    ConflictSeverity,
    ConflictType,
    IngredientConflict,
    ProductExtraction,
)

logger = logging.getLogger(__name__)

_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


class _ReconcilerResponse(BaseModel):
    """Internal schema for reconciler — nullable conflict so 'no conflict' is expressible."""

    conflict_type: ConflictType | None = None
    severity: ConflictSeverity | None = None
    summary: str | None = None
    sources: list[str] | None = None


def _configure(settings: Settings) -> None:
    genai.configure(api_key=settings.gemini_api_key)


def _decode_image(image_b64: str) -> bytes:
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64 image: {exc}",
        ) from exc
    if len(raw) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds {_MAX_IMAGE_BYTES // (1024 * 1024)} MB limit",
        )
    return raw


def _extract_parsed(response: Any, model_cls):
    """Pull a typed model out of a Gemini response.

    The 0.8.x SDK exposes `response.parsed` when response_schema is set;
    otherwise we fall back to parsing `response.text` (guaranteed JSON
    by response_mime_type).
    """
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, model_cls):
        return parsed
    text = getattr(response, "text", None) or ""
    return model_cls.model_validate_json(text)


async def extract_from_image(image_b64: str, settings: Settings) -> ProductExtraction:
    """Run Gemini Vision on a base64 label image; return a typed ProductExtraction."""
    raw = _decode_image(image_b64)
    _configure(settings)

    model = genai.GenerativeModel(settings.gemini_model)
    try:
        response = await model.generate_content_async(
            [
                EXTRACTOR_PROMPT,
                {"mime_type": "image/jpeg", "data": raw},
            ],
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": ProductExtraction,
            },
        )
    except google_exceptions.ResourceExhausted as exc:
        logger.warning("Gemini quota exhausted: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Gemini API quota exceeded, retry later",
        ) from exc
    except google_exceptions.GoogleAPIError as exc:
        logger.error("Gemini API error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API unavailable",
        ) from exc

    return _extract_parsed(response, ProductExtraction)


async def reconcile_ingredient(
    ingredient: str,
    rag_context: str,
    biomarkers: dict | None,
    settings: Settings,
) -> IngredientConflict | None:
    """Ask Gemini to classify the conflict for a given ingredient.

    Returns None when there's insufficient evidence, or when Gemini is
    unavailable (graceful degradation — RAG hit alone remains).
    """
    _configure(settings)

    prompt = RECONCILER_PROMPT.format(
        ingredient=ingredient,
        rag_context=rag_context or "(sin contexto regulatorio disponible)",
        user_biomarkers=json.dumps(biomarkers) if biomarkers else "(ninguno)",
    )

    model = genai.GenerativeModel(settings.gemini_model)
    try:
        response = await model.generate_content_async(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": _ReconcilerResponse,
            },
        )
    except google_exceptions.ResourceExhausted as exc:
        logger.warning("Gemini quota exhausted during reconciliation: %s", exc)
        return None
    except google_exceptions.GoogleAPIError as exc:
        logger.error("Gemini API error during reconciliation: %s", exc)
        return None

    parsed = _extract_parsed(response, _ReconcilerResponse)
    if parsed.conflict_type is None or parsed.severity is None:
        return None

    return IngredientConflict(
        conflict_type=parsed.conflict_type,
        severity=parsed.severity,
        summary=parsed.summary or "Conflict detected",
        sources=parsed.sources or [],
    )
