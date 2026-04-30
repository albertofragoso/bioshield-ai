"""Tests para app/services/analysis.py — keyword matching, semantic path, compute_semaphore."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.schemas.models import (
    ConflictSeverity,
    IngredientResult,
    RegulatoryStatus,
    SemaphoreColor,
)
from app.services.analysis import (
    _find_matches_keywords,
    compute_semaphore,
    find_ingredient_matches,
)


def _bm(name: str, value: float, classification: str) -> dict:
    return {"name": name, "value": value, "unit": "mg/dL", "classification": classification}


def _ing(name: str, canonical: str | None = None) -> IngredientResult:
    return IngredientResult(
        name=name,
        canonical_name=canonical or name,
        regulatory_status=RegulatoryStatus.APPROVED,
        confidence_score=1.0,
        conflicts=[],
    )


def _base_settings(**overrides) -> Settings:
    base = dict(
        debug=True,
        database_url="sqlite:///:memory:",
        jwt_secret="test-jwt",
        aes_key="test-aes-key-32-bytes-xxxxxxxxxx",
        gemini_api_key="test-key",
        chroma_persist_directory="",
        allowed_origins=["http://testserver"],
        use_local_embeddings=True,
        bge_model_name="BAAI/bge-m3",
    )
    base.update(overrides)
    return Settings(**base)


# ─────────────────────────────────────────────
# _find_matches_keywords
# ─────────────────────────────────────────────


def test_keyword_match_ldl_high():
    biomarkers = [_bm("ldl", 160, "high")]
    ingredients = [_ing("hydrogenated vegetable oil")]
    matches = _find_matches_keywords(biomarkers, ingredients)
    assert len(matches) == 1
    bm, ingr_names, severity, kind, direction = matches[0]
    assert kind == "alert"
    assert direction == "raises"
    assert severity == ConflictSeverity.HIGH


def test_keyword_match_normal_returns_watch():
    biomarkers = [_bm("ldl", 100, "normal")]
    ingredients = [_ing("palm oil")]
    matches = _find_matches_keywords(biomarkers, ingredients)
    assert len(matches) == 1
    _, _, _, kind, _ = matches[0]
    assert kind == "watch"


def test_keyword_no_match_opposite_direction():
    """LDL raises pero classification=low → no debe dispararse."""
    biomarkers = [_bm("ldl", 50, "low")]
    ingredients = [_ing("trans fat ingredient")]
    matches = _find_matches_keywords(biomarkers, ingredients)
    assert matches == []


def test_keyword_empty_inputs():
    assert _find_matches_keywords(None, []) == []
    assert _find_matches_keywords([], [_ing("salt")]) == []


# ─────────────────────────────────────────────
# find_ingredient_matches — backward compat (sin settings)
# ─────────────────────────────────────────────


async def test_find_ingredient_matches_keyword_fallback_when_no_settings():
    biomarkers = [_bm("ldl", 160, "high")]
    ingredients = [_ing("trans fat"), _ing("olive oil")]

    matches = await find_ingredient_matches(biomarkers, ingredients, settings=None, collection=None)

    assert len(matches) == 1
    bm, ingr_names, severity, kind, direction, semantic_score = matches[0]
    assert semantic_score == 0.0
    assert "trans fat" in ingr_names


async def test_find_ingredient_matches_returns_no_matches_when_empty():
    result = await find_ingredient_matches([], [_ing("sugar")], settings=None, collection=None)
    assert result == []


# ─────────────────────────────────────────────
# find_ingredient_matches — semantic path
# ─────────────────────────────────────────────


async def test_find_ingredient_matches_semantic_adds_extra_hit():
    """Un hit semántico por encima del threshold extiende la lista de ingredientes."""
    from app.services.rag import RAGHit

    biomarkers = [_bm("ldl", 160, "high")]
    # keyword match: "trans fat"; semantic path debería agregar "lard"
    ingredients = [_ing("trans fat"), _ing("lard")]
    settings = _base_settings()
    mock_collection = MagicMock()

    semantic_hit = RAGHit(
        entity_id="NAME:lard",
        document="[Name: Lard] [Status: APPROVED]",
        metadata={"canonical_name": "lard"},
        similarity=0.80,
    )

    with (
        patch(
            "app.services.embeddings.embed_text", new_callable=AsyncMock, return_value=[0.1] * 1024
        ),
        patch("app.services.rag.query_by_embedding", return_value=[semantic_hit]),
    ):
        matches = await find_ingredient_matches(biomarkers, ingredients, settings, mock_collection)

    assert len(matches) == 1
    _, ingr_names, _, _, _, semantic_score = matches[0]
    assert "lard" in ingr_names
    assert semantic_score == pytest.approx(0.80)


async def test_find_ingredient_matches_semantic_below_threshold_ignored():
    """Hits con similarity < threshold no se agregan."""
    from app.services.rag import RAGHit

    biomarkers = [_bm("ldl", 160, "high")]
    ingredients = [_ing("trans fat"), _ing("canola oil")]
    settings = _base_settings()
    mock_collection = MagicMock()

    low_hit = RAGHit(
        entity_id="NAME:canola_oil",
        document="[Name: Canola Oil]",
        metadata={"canonical_name": "canola oil"},
        similarity=0.40,  # por debajo del threshold 0.65
    )

    with (
        patch(
            "app.services.embeddings.embed_text", new_callable=AsyncMock, return_value=[0.1] * 1024
        ),
        patch("app.services.rag.query_by_embedding", return_value=[low_hit]),
    ):
        matches = await find_ingredient_matches(biomarkers, ingredients, settings, mock_collection)

    _, ingr_names, _, _, _, semantic_score = matches[0]
    assert "canola oil" not in ingr_names
    assert semantic_score == 0.0


async def test_find_ingredient_matches_semantic_failure_falls_back_gracefully():
    """Si embed_text falla, el match se devuelve con semantic_score=0.0 (no crash)."""
    biomarkers = [_bm("ldl", 160, "high")]
    ingredients = [_ing("trans fat")]
    settings = _base_settings()
    mock_collection = MagicMock()

    with patch("app.services.embeddings.embed_text", side_effect=RuntimeError("api down")):
        matches = await find_ingredient_matches(biomarkers, ingredients, settings, mock_collection)

    assert len(matches) == 1
    _, _, _, _, _, semantic_score = matches[0]
    assert semantic_score == 0.0


# ─────────────────────────────────────────────
# compute_semaphore — regression guard (debe seguir siendo sync)
# ─────────────────────────────────────────────


def test_compute_semaphore_still_sync():
    """compute_semaphore NO debe ser async — regression guard del async cascade."""
    import inspect

    assert not inspect.iscoroutinefunction(compute_semaphore)


def test_compute_semaphore_orange_with_biomarker_conflict():
    biomarkers = [_bm("ldl", 160, "high")]
    ingredients = [_ing("trans fat")]
    color, severity, alerts = compute_semaphore(ingredients, biomarkers)
    assert color == SemaphoreColor.ORANGE
    assert alerts


def test_compute_semaphore_blue_no_conflicts():
    ingredients = [_ing("water", "water"), _ing("salt", "salt")]
    color, severity, alerts = compute_semaphore(ingredients)
    assert color == SemaphoreColor.BLUE
