"""Gemini 2.5 Flash client: Vision extraction + textual reconciliation.

Vision path uses Structured Outputs (response_schema) so we never parse
JSON by hand — per the project convention.
Reconciler returns IngredientConflict | None from the RAG context.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import re
from typing import Any

import google.generativeai as genai
from fastapi import HTTPException, status
from google.api_core import exceptions as google_exceptions
from pydantic import BaseModel
from pydantic import BaseModel as _PydanticBase

from app.agents.prompts import (
    BIOMARKER_EXTRACTION_PROMPT,
    EXTRACTOR_PROMPT,
    PERSONALIZED_INSIGHT_PROMPT,
    RECONCILER_PROMPT,
)
from app.config import Settings
from app.core.context import REQUEST_ID_VAR
from app.schemas.models import (
    ConflictSeverity,
    ConflictType,
    GeminiBiomarkerExtraction,
    IngredientConflict,
    PersonalizedInsightCopy,
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


_GEMINI_SCHEMA_ALLOWED = {
    "type",
    "format",
    "description",
    "nullable",
    "enum",
    "properties",
    "required",
    "items",
    "minItems",
    "maxItems",
    "minimum",
    "maximum",
}


def _to_gemini_schema(schema: dict, defs: dict | None = None) -> dict:
    """Recursively keep only fields supported by Gemini proto.Schema.

    Pydantic JSON Schema emits 'title', 'default', '$defs', '$ref', 'anyOf',
    etc. that the Gemini SDK proto rejects. Three transformations are applied
    before the allowed-key filter:

    1. $ref → inline the referenced $defs entry.
    2. anyOf: [{type: X}, {type: null}]  →  {type: X, nullable: true}
       (Pydantic's encoding of Optional[X]; Gemini uses nullable instead).
    3. Strip every key not in _GEMINI_SCHEMA_ALLOWED.

    'properties' values are property schemas (not keywords), so we recurse
    into each value without filtering the keys themselves.
    """
    if defs is None:
        defs = schema.get("$defs", {})

    # 1. Inline $ref
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        if ref_name in defs:
            return _to_gemini_schema(defs[ref_name], defs)

    # 2. Convert anyOf nullable pattern produced by Pydantic for Optional[X]
    if "anyOf" in schema:
        variants = schema["anyOf"]
        non_null = [v for v in variants if v.get("type") != "null"]
        has_null = any(v.get("type") == "null" for v in variants)
        if has_null and len(non_null) == 1:
            merged = {**schema, **non_null[0], "nullable": True}
            merged.pop("anyOf", None)
            return _to_gemini_schema(merged, defs)

    # 3. Filter to Gemini-allowed keys
    result: dict[str, Any] = {}
    for k, v in schema.items():
        if k not in _GEMINI_SCHEMA_ALLOWED:
            continue
        if k == "properties" and isinstance(v, dict):
            # keys are property names — preserve them, recurse into their schemas
            result[k] = {prop: _to_gemini_schema(sub, defs) for prop, sub in v.items()}
        elif isinstance(v, dict):
            result[k] = _to_gemini_schema(v, defs)
        elif isinstance(v, list):
            result[k] = [_to_gemini_schema(i, defs) if isinstance(i, dict) else i for i in v]
        else:
            result[k] = v
    return result


def _gemini_schema(model_cls: type[_PydanticBase]) -> dict:
    """Return a Gemini-compatible JSON schema dict for a Pydantic model."""
    return _to_gemini_schema(model_cls.model_json_schema())


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
                "response_schema": _gemini_schema(ProductExtraction),
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

    _usage = getattr(response, "usage_metadata", None)
    logger.info(
        "gemini_call_complete",
        extra={
            "request_id": REQUEST_ID_VAR.get(),
            "tokens_total": getattr(_usage, "total_token_count", 0),
            "tokens_prompt": getattr(_usage, "prompt_token_count", 0),
            "tokens_output": getattr(_usage, "candidates_token_count", 0),
            "model": settings.gemini_model,
        },
    )
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
        user_biomarkers=json.dumps(_biomarkers_to_flags(biomarkers)) if biomarkers else "(ninguno)",
    )

    model = genai.GenerativeModel(settings.gemini_model)
    try:
        response = await model.generate_content_async(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": _gemini_schema(_ReconcilerResponse),
            },
        )
    except google_exceptions.ResourceExhausted as exc:
        logger.warning("Gemini quota exhausted during reconciliation: %s", exc)
        return None
    except google_exceptions.GoogleAPIError as exc:
        logger.error("Gemini API error during reconciliation: %s", exc)
        return None

    _usage = getattr(response, "usage_metadata", None)
    logger.info(
        "gemini_call_complete",
        extra={
            "request_id": REQUEST_ID_VAR.get(),
            "tokens_total": getattr(_usage, "total_token_count", 0),
            "tokens_prompt": getattr(_usage, "prompt_token_count", 0),
            "tokens_output": getattr(_usage, "candidates_token_count", 0),
            "model": settings.gemini_model,
        },
    )
    parsed = _extract_parsed(response, _ReconcilerResponse)
    if parsed.conflict_type is None or parsed.severity is None:
        return None

    return IngredientConflict(
        conflict_type=parsed.conflict_type,
        severity=parsed.severity,
        summary=parsed.summary or "Conflict detected",
        sources=parsed.sources or [],
    )


async def extract_biomarkers_from_images(
    images_b64: list[str],
    settings: Settings,
) -> GeminiBiomarkerExtraction:
    """Run Gemini Vision on base64-encoded PDF pages; return raw biomarker extraction.

    Passes all pages as parts in a single Gemini call for cross-page coherence.
    """
    _configure(settings)
    model = genai.GenerativeModel(settings.gemini_model)

    parts: list = [BIOMARKER_EXTRACTION_PROMPT]
    for img_b64 in images_b64:
        raw = _decode_image(img_b64)
        parts.append({"mime_type": "image/jpeg", "data": raw})

    try:
        response = await model.generate_content_async(
            parts,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": _gemini_schema(GeminiBiomarkerExtraction),
            },
        )
        _usage = getattr(response, "usage_metadata", None)
        logger.info(
            "gemini_call_complete",
            extra={
                "request_id": REQUEST_ID_VAR.get(),
                "tokens_total": getattr(_usage, "total_token_count", 0),
                "tokens_prompt": getattr(_usage, "prompt_token_count", 0),
                "tokens_output": getattr(_usage, "candidates_token_count", 0),
                "model": settings.gemini_model,
            },
        )
        return _extract_parsed(response, GeminiBiomarkerExtraction)
    except google_exceptions.ResourceExhausted as exc:
        logger.warning("Gemini quota exhausted during biomarker extraction: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Gemini API quota exceeded, retry later",
        ) from exc
    except google_exceptions.GoogleAPIError as exc:
        logger.error("Gemini API error during biomarker extraction: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API unavailable",
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error during biomarker image extraction: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Error procesando el PDF con IA",
        ) from exc


async def extract_biomarkers_from_pdf(
    pdf_b64: str,
    settings: Settings,
) -> GeminiBiomarkerExtraction:
    """Run Gemini Vision on base64-encoded PDF; return raw biomarker extraction.

    Sends PDF directly to Gemini without converting to images.
    No poppler/pdf2image dependency needed.
    """
    _configure(settings)
    model = genai.GenerativeModel(settings.gemini_model)

    raw = _decode_base64_safe(pdf_b64, _MAX_PDF_BYTES)
    parts: list = [
        BIOMARKER_EXTRACTION_PROMPT,
        {"mime_type": "application/pdf", "data": raw},
    ]

    try:
        response = await model.generate_content_async(
            parts,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": _gemini_schema(GeminiBiomarkerExtraction),
            },
        )
        _usage = getattr(response, "usage_metadata", None)
        logger.info(
            "gemini_call_complete",
            extra={
                "request_id": REQUEST_ID_VAR.get(),
                "tokens_total": getattr(_usage, "total_token_count", 0),
                "tokens_prompt": getattr(_usage, "prompt_token_count", 0),
                "tokens_output": getattr(_usage, "candidates_token_count", 0),
                "model": settings.gemini_model,
            },
        )
        return _extract_parsed(response, GeminiBiomarkerExtraction)
    except google_exceptions.ResourceExhausted as exc:
        logger.warning("Gemini quota exhausted during biomarker extraction: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Gemini API quota exceeded, retry later",
        ) from exc
    except google_exceptions.GoogleAPIError as exc:
        logger.error("Gemini API error during biomarker extraction: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API unavailable",
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error during biomarker PDF extraction: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Error procesando el PDF con IA",
        ) from exc


_INSIGHT_FALLBACK_LABEL: dict[str, str] = {
    "ldl": 'tu colesterol "malo"',
    "hdl": 'tu colesterol "bueno"',
    "total_cholesterol": "tu colesterol total",
    "triglycerides": "tus triglicéridos",
    "glucose": "tu nivel de azúcar en sangre",
    "hba1c": "tu azúcar promedio de los últimos meses",
    "sodium": "tu sodio",
    "potassium": "tu potasio",
    "uric_acid": "tu ácido úrico",
    "creatinine": "la salud de tus riñones",
    "alt": "tu hígado",
    "ast": "tu hígado",
    "tsh": "tu tiroides",
    "vitamin_d": "tu vitamina D",
    "iron": "tu hierro",
    "ferritin": "tu hierro",
    "hemoglobin": "tu hemoglobina",
    "hematocrit": "tu hemoglobina",
    "platelets": "tus plaquetas",
    "wbc": "tus defensas",
}

# Normal ranges (low, high) for de-identification — values outside range get
# an "elevated" or "low" flag; unknown biomarkers get a "_present" flag only.
_BIOMARKER_THRESHOLDS: dict[str, tuple[float, float]] = {
    "ldl": (0.0, 129.0),
    "hdl": (40.0, 9999.0),
    "total_cholesterol": (0.0, 199.0),
    "triglycerides": (0.0, 149.0),
    "glucose": (70.0, 99.0),
    "hba1c": (0.0, 5.6),
    "sodium": (136.0, 145.0),
    "potassium": (3.5, 5.0),
    "uric_acid": (2.4, 7.0),
    "creatinine": (0.7, 1.2),
    "alt": (0.0, 40.0),
    "ast": (0.0, 40.0),
    "tsh": (0.4, 4.0),
    "vitamin_d": (30.0, 100.0),
    "iron": (60.0, 170.0),
    "ferritin": (12.0, 300.0),
    "hemoglobin": (12.0, 17.0),
    "hematocrit": (36.0, 50.0),
    "platelets": (150.0, 400.0),
    "wbc": (4.5, 11.0),
}

_MAX_PDF_BYTES = 20_971_520  # 20 MB

# Pattern used to detect numeric biomarker measurements leaking into LLM output.
_PHI_PATTERN = re.compile(r"\b\d+\.?\d*\s*(?:mg/dL|mmol/L|IU/L|g/dL|mEq/L|U/L|%)\b")


def _biomarkers_to_flags(biomarkers: dict) -> dict[str, bool]:
    """Convert raw biomarker dict to de-identified boolean flags.

    Numeric values never leave this function — only True/False classifications.
    """
    flags: dict[str, bool] = {}
    for name, value in biomarkers.items():
        if not isinstance(value, (int, float)):
            continue
        if name in _BIOMARKER_THRESHOLDS:
            low, high = _BIOMARKER_THRESHOLDS[name]
            if value < low:
                flags[f"{name}_low"] = True
            elif value > high:
                flags[f"{name}_elevated"] = True
            else:
                flags[f"{name}_normal"] = True
        else:
            flags[f"{name}_present"] = True
    return flags


def _decode_base64_safe(data: str, max_bytes: int) -> bytes:
    """Decode base64, rejecting oversized or malformed input before allocating."""
    estimated = len(data) * 3 // 4
    if estimated > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Payload exceeds maximum allowed size ({max_bytes} bytes)",
        )
    try:
        return base64.b64decode(data, validate=True)
    except binascii.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 encoding",
        ) from exc


def _assert_no_phi_leak(text: str) -> None:
    """Raise if LLM output contains numeric biomarker measurements."""
    if _PHI_PATTERN.search(text):
        raise ValueError(f"Potential PHI leak in LLM output: {text[:120]!r}")


async def generate_personalized_insight(
    biomarker_name: str,
    biomarker_value: float,
    biomarker_unit: str,
    classification: str,
    severity: str,
    affecting_ingredients: list[str],
    settings: Settings,
    kind: str = "alert",
) -> PersonalizedInsightCopy:
    """Generate friendly copy for one biomarker × ingredient conflict.

    On 429/503 falls back to a generic non-jargon copy so the scan still completes.
    """
    _configure(settings)
    model = genai.GenerativeModel(settings.gemini_model)

    prompt = PERSONALIZED_INSIGHT_PROMPT.format(
        biomarker_name=biomarker_name,
        classification=classification,
        severity=severity,
        affecting_ingredients=", ".join(affecting_ingredients),
        kind=kind,
    )

    try:
        response = await model.generate_content_async(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": _gemini_schema(PersonalizedInsightCopy),
            },
        )
        _usage = getattr(response, "usage_metadata", None)
        logger.info(
            "gemini_call_complete",
            extra={
                "request_id": REQUEST_ID_VAR.get(),
                "tokens_total": getattr(_usage, "total_token_count", 0),
                "tokens_prompt": getattr(_usage, "prompt_token_count", 0),
                "tokens_output": getattr(_usage, "candidates_token_count", 0),
                "model": settings.gemini_model,
            },
        )
        result = _extract_parsed(response, PersonalizedInsightCopy)
        _assert_no_phi_leak(result.friendly_explanation)
        _assert_no_phi_leak(result.friendly_recommendation)
        return result
    except (google_exceptions.ResourceExhausted, google_exceptions.GoogleAPIError) as exc:
        logger.warning("Gemini unavailable for personalized insight, using fallback: %s", exc)
        label = _INSIGHT_FALLBACK_LABEL.get(biomarker_name, biomarker_name)
        ingr_str = (
            " y ".join(affecting_ingredients[:2])
            if affecting_ingredients
            else "algunos ingredientes"
        )
        if kind == "watch":
            explanation = f"{label.capitalize()} está en rango normal pero este producto contiene {ingr_str}, que podrían subirlo."
        else:
            explanation = (
                f"{label.capitalize()} está {classification} y este producto contiene {ingr_str}."
            )
        return PersonalizedInsightCopy(
            friendly_title="Revisa este producto",
            friendly_biomarker_label=label,
            friendly_explanation=explanation,
            friendly_recommendation="Considera revisar la etiqueta de productos similares antes de decidir.",
        )
