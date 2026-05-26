"""Unit tests for the alternative matching engine.

Patches ChromaDB and embed_text so tests run offline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.models import Product, ScanHistory
from app.services.alternatives import (
    _biomarker_conflicts,
    _clean_ingredient_labels,
    _compatibility_pct,
    find_alternatives,
)
from app.services.semaphore import semaphore_from_score

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_product(db, barcode: str, name: str, category: str | None, clean_score: int) -> Product:
    p = Product(
        barcode=barcode,
        name=name,
        brand="TestBrand",
        category=category,
        clean_score=clean_score,
    )
    db.add(p)
    db.flush()
    return p


def _make_scan(
    db,
    barcode: str,
    semaphore: str,
    ingredients: list[str],
    flagged: list[str],
) -> ScanHistory:
    result_json = {
        "product_barcode": barcode,
        "semaphore": semaphore,
        "product_name": f"Product {barcode}",
        "ingredients": [
            {
                "name": i,
                "conflicts": [{"conflict_type": "REGULATORY"}] if i in flagged else [],
            }
            for i in ingredients
        ],
        "conflict_severity": None,
        "source": "barcode",
        "scanned_at": "2026-05-08T00:00:00",
        "personalized_insights": [],
    }
    s = ScanHistory(
        product_barcode=barcode,
        user_id="test-user-id-00000000000000000000",
        semaphore_result=semaphore,
        result_json=result_json,
        scanned_at=datetime.now(UTC),
    )
    db.add(s)
    db.flush()
    return s


# ── pure function tests (no DB needed) ───────────────────────────────────────


def test_semaphore_from_clean_score():
    assert semaphore_from_score(0) == "BLUE"
    assert semaphore_from_score(1) == "YELLOW"
    assert semaphore_from_score(2) == "YELLOW"
    assert semaphore_from_score(3) == "ORANGE"
    assert semaphore_from_score(5) == "RED"


def test_compatibility_pct_perfect():
    assert _compatibility_pct(0, 4, 0) == 100


def test_compatibility_pct_partial():
    assert _compatibility_pct(2, 4, 0) == 50


def test_compatibility_pct_with_conflicts():
    assert _compatibility_pct(0, 4, 1) == 90


def test_compatibility_pct_never_negative():
    assert _compatibility_pct(4, 4, 5) == 0


def test_biomarker_conflicts_detects_dextrose():
    # "sugar" is not in the canonical GLUCOSE keywords (too generic);
    # use "dextrose" which is an explicit entry in BIOMARKER_RULES for glucose.
    conflicts = _biomarker_conflicts(["dextrose", "water", "salt"], ["glucose"])
    assert any("glucose" in c.lower() for c in conflicts)


def test_biomarker_conflicts_no_match():
    conflicts = _biomarker_conflicts(["water", "pectina"], ["ldl"])
    assert conflicts == []


def test_clean_ingredient_labels():
    labels = _clean_ingredient_labels(["water", "salt", "sugar"], ["sugar"])
    assert "Sin water" in labels or "Sin salt" in labels
    assert not any("sugar" in la.lower() for la in labels)


# ── integration tests (with DB) ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_find_alternatives_sql_first_pass(db_session):
    """SQL first pass returns products with lower clean_score in same category."""
    _make_product(db_session, "BAD001", "Bad Yogurt", "yogurts", clean_score=3)
    _make_scan(
        db_session,
        "BAD001",
        "RED",
        ["sugar", "colorante E129", "leche"],
        ["sugar", "colorante E129"],
    )
    _make_product(db_session, "GOOD001", "Good Yogurt", "yogurts", clean_score=0)
    _make_product(db_session, "GOOD002", "Ok Yogurt", "yogurts", clean_score=1)
    _make_product(db_session, "DIFF001", "Other Category", "snacks", clean_score=0)

    from app.config import Settings

    settings = Settings(chroma_persist_directory="")

    with (
        patch("app.services.alternatives.embed_text", new_callable=AsyncMock) as mock_embed,
        patch("app.services.alternatives.get_products_collection") as mock_coll,
    ):
        mock_embed.return_value = [0.1] * 1024
        mock_coll.return_value.query.return_value = {
            "metadatas": [[{"barcode": "GOOD001"}, {"barcode": "GOOD002"}]],
            "distances": [[0.1, 0.2]],
        }

        result = await find_alternatives(
            barcode="BAD001",
            db=db_session,
            settings=settings,
            active_biomarkers=[],
            has_biomarkers=False,
        )

    assert result is not None
    all_barcodes = [result.top_pick.product.barcode] + [
        a.product.barcode for a in result.alternatives
    ]
    assert "GOOD001" in all_barcodes
    assert "DIFF001" not in all_barcodes


@pytest.mark.asyncio
async def test_find_alternatives_fallback_when_no_category(db_session):
    """fallback_used=True when scanned product has no category."""
    _make_product(db_session, "NOCAT001", "No Category Product", None, clean_score=3)
    _make_scan(db_session, "NOCAT001", "RED", ["sugar"], ["sugar"])

    from app.config import Settings

    settings = Settings(chroma_persist_directory="")

    with (
        patch("app.services.alternatives.embed_text", new_callable=AsyncMock),
        patch("app.services.alternatives.get_products_collection") as mock_coll,
    ):
        mock_coll.return_value.query.return_value = {"metadatas": [[]], "distances": [[]]}

        result = await find_alternatives(
            barcode="NOCAT001",
            db=db_session,
            settings=settings,
            active_biomarkers=[],
            has_biomarkers=False,
        )

    assert result is not None
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_find_alternatives_returns_none_when_scan_not_found(db_session):
    """Returns None when the barcode has no scan history."""
    from app.config import Settings

    settings = Settings(chroma_persist_directory="")

    result = await find_alternatives(
        barcode="NONEXISTENT",
        db=db_session,
        settings=settings,
        active_biomarkers=[],
        has_biomarkers=False,
    )
    assert result is None


@pytest.mark.asyncio
async def test_find_alternatives_chroma_failure_degrades_gracefully(db_session):
    """ChromaDB failure → uses SQL order, doesn't crash."""
    _make_product(db_session, "BAD002", "Bad Product", "bebidas", clean_score=4)
    _make_scan(db_session, "BAD002", "RED", ["sugar"], ["sugar"])
    _make_product(db_session, "GOOD003", "Good Drink", "bebidas", clean_score=0)

    from app.config import Settings

    settings = Settings(chroma_persist_directory="")

    with patch(
        "app.services.alternatives.embed_text",
        side_effect=Exception("chroma down"),
    ):
        result = await find_alternatives(
            barcode="BAD002",
            db=db_session,
            settings=settings,
            active_biomarkers=[],
            has_biomarkers=False,
        )

    assert result is not None
