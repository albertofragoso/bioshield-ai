"""End-to-end LangGraph tests — exercises the full scan pipeline against
a seeded in-memory DB with mocked OFF/Gemini/embedding layers.

Covers all 5 semaphore colors from PRD §7.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.agents.graph import build_scan_graph
from app.models import Biomarker
from app.schemas.models import SemaphoreColor
from app.services import gemini as gemini_service
from app.services import off_client, retrieval
from app.services.crypto import encrypt_biomarker
from app.services.ingestion.common import (
    IngestionRecord,
    get_or_create_source,
    upsert_ingredient,
    upsert_regulatory_status,
)
from tests.conftest import TEST_SETTINGS


@pytest.fixture
def seeded_db(db_session):
    """Minimal regulatory graph that can produce all semaphore colors."""
    fda = get_or_create_source(
        db_session, "FDA_EAFUS", "US", "v1", "sha256:a", "Public Domain", "XLSX"
    )
    efsa = get_or_create_source(
        db_session, "EFSA_OpenFoodTox", "EU", "v1", "sha256:b", "CC BY 4.0", "JSON"
    )

    titanium = upsert_ingredient(
        db_session,
        IngestionRecord(canonical_name="Titanium Dioxide", cas_number="13463-67-7", synonyms=["E171"]),
    )
    upsert_regulatory_status(
        db_session, titanium, fda,
        IngestionRecord(canonical_name="Titanium Dioxide", status="APPROVED"),
    )
    upsert_regulatory_status(
        db_session, titanium, efsa,
        IngestionRecord(
            canonical_name="Titanium Dioxide", status="BANNED",
            hazard_note="Genotoxicity cannot be ruled out",
            evaluated_at=datetime.now(UTC),
        ),
    )

    bha = upsert_ingredient(
        db_session,
        IngestionRecord(canonical_name="Butylated Hydroxyanisole", cas_number="25013-16-5"),
    )
    upsert_regulatory_status(
        db_session, bha, fda,
        IngestionRecord(
            canonical_name="Butylated Hydroxyanisole",
            status="APPROVED",
            hazard_note="IARC Group 2B carcinogen",
            evaluated_at=datetime.now(UTC),
        ),
    )

    salt = upsert_ingredient(
        db_session, IngestionRecord(canonical_name="Salt", cas_number="7647-14-5")
    )
    upsert_regulatory_status(
        db_session, salt, fda,
        IngestionRecord(
            canonical_name="Salt", status="APPROVED",
            evaluated_at=datetime.now(UTC),
        ),
    )

    # HFCS for biomarker-driven conflict test
    hfcs = upsert_ingredient(
        db_session, IngestionRecord(canonical_name="High-Fructose Corn Syrup")
    )
    upsert_regulatory_status(
        db_session, hfcs, fda,
        IngestionRecord(
            canonical_name="High-Fructose Corn Syrup",
            status="APPROVED",
            evaluated_at=datetime.now(UTC),
        ),
    )
    db_session.commit()
    return db_session


@pytest.fixture(autouse=True)
def _mock_external(monkeypatch):
    """Neutralize network-bound dependencies for graph tests."""
    async def _fake_hybrid(*args, **kwargs):
        return []

    monkeypatch.setattr(retrieval, "hybrid_search", _fake_hybrid)


async def _run_graph(db, state: dict) -> dict:
    graph = build_scan_graph(db, TEST_SETTINGS)
    return await graph.ainvoke(state)


# ─────────────────────────────────────────────
# GRAY: no ingredients found
# ─────────────────────────────────────────────

async def test_semaphore_gray_on_missing_product(seeded_db, monkeypatch):
    async def _off_miss(*a, **kw):
        return None

    monkeypatch.setattr(off_client, "fetch_product", _off_miss)

    result = await _run_graph(seeded_db, {"barcode": "9999999999", "user_id": "x"})
    # Without ingredients nor image → extract_ingredients node sets error; semaphore stays GRAY
    assert result["semaphore"] == SemaphoreColor.GRAY


# ─────────────────────────────────────────────
# BLUE: clean ingredients (no conflict anywhere)
# ─────────────────────────────────────────────

async def test_semaphore_blue_clean(seeded_db, monkeypatch):
    async def _off_hit(*a, **kw):
        return {
            "barcode": "1111",
            "name": "Plain Salt",
            "brand": "Basic",
            "image_url": None,
            "ingredients": ["Salt"],
        }

    monkeypatch.setattr(off_client, "fetch_product", _off_hit)

    result = await _run_graph(seeded_db, {"barcode": "1111", "user_id": "x"})
    assert result["semaphore"] == SemaphoreColor.BLUE


# ─────────────────────────────────────────────
# YELLOW: SCIENTIFIC conflict but no REGULATORY HIGH
# ─────────────────────────────────────────────

async def test_semaphore_yellow_scientific_only(seeded_db, monkeypatch):
    async def _off_hit(*a, **kw):
        return {
            "barcode": "2222",
            "name": "Crackers",
            "brand": "Snackco",
            "image_url": None,
            "ingredients": ["Butylated Hydroxyanisole"],
        }

    monkeypatch.setattr(off_client, "fetch_product", _off_hit)

    result = await _run_graph(seeded_db, {"barcode": "2222", "user_id": "x"})
    assert result["semaphore"] == SemaphoreColor.YELLOW


# ─────────────────────────────────────────────
# RED: REGULATORY HIGH (FDA approved, EFSA banned)
# ─────────────────────────────────────────────

async def test_semaphore_red_regulatory_high(seeded_db, monkeypatch):
    async def _off_hit(*a, **kw):
        return {
            "barcode": "3333",
            "name": "Candy",
            "brand": "Confectio",
            "image_url": None,
            "ingredients": ["Titanium Dioxide"],
        }

    monkeypatch.setattr(off_client, "fetch_product", _off_hit)

    result = await _run_graph(seeded_db, {"barcode": "3333", "user_id": "x"})
    assert result["semaphore"] == SemaphoreColor.RED


# ─────────────────────────────────────────────
# ORANGE: biomarker conflict (user glucose high + product has HFCS)
# ─────────────────────────────────────────────

async def test_semaphore_orange_biomarker_conflict(seeded_db, monkeypatch):
    async def _off_hit(*a, **kw):
        return {
            "barcode": "4444",
            "name": "Soda",
            "brand": "Fizzy",
            "image_url": None,
            "ingredients": ["High-Fructose Corn Syrup"],
        }

    monkeypatch.setattr(off_client, "fetch_product", _off_hit)

    # Seed a biomarker for the user
    user_id = "user-bio-123"
    ciphertext, iv = encrypt_biomarker({"glucose": 180, "hba1c": 7.2}, TEST_SETTINGS.aes_key)
    seeded_db.add(
        Biomarker(user_id=user_id, encrypted_data=ciphertext, encryption_iv=iv)
    )
    seeded_db.commit()

    result = await _run_graph(seeded_db, {"barcode": "4444", "user_id": user_id})
    assert result["semaphore"] == SemaphoreColor.ORANGE


# ─────────────────────────────────────────────
# Graph wiring sanity
# ─────────────────────────────────────────────

async def test_graph_photo_path_invokes_gemini(seeded_db, monkeypatch):
    """When there's no barcode, the extract_ingredients node runs Gemini."""
    async def _off_miss(*a, **kw):
        return None

    called = {"count": 0}

    async def _fake_extract(image_b64, settings):
        called["count"] += 1
        from app.schemas.models import ProductExtraction
        return ProductExtraction(ingredients=["Salt"], has_additives=False)

    monkeypatch.setattr(off_client, "fetch_product", _off_miss)
    monkeypatch.setattr(gemini_service, "extract_from_image", _fake_extract)

    result = await _run_graph(
        seeded_db,
        {"image_b64": "SGVsbG8=", "user_id": "x"},
    )
    assert called["count"] == 1
    assert result.get("source") == "photo"
    assert result["semaphore"] == SemaphoreColor.BLUE


async def test_graph_skips_gemini_when_off_has_ingredients(seeded_db, monkeypatch):
    async def _off_hit(*a, **kw):
        return {
            "barcode": "5555",
            "name": "Salted chips",
            "brand": "Chippy",
            "image_url": None,
            "ingredients": ["Salt"],
        }

    called = {"count": 0}

    async def _fake_extract(*a, **kw):
        called["count"] += 1
        from app.schemas.models import ProductExtraction
        return ProductExtraction(ingredients=[], has_additives=False)

    monkeypatch.setattr(off_client, "fetch_product", _off_hit)
    monkeypatch.setattr(gemini_service, "extract_from_image", _fake_extract)

    result = await _run_graph(
        seeded_db,
        {"barcode": "5555", "image_b64": "SGVsbG8=", "user_id": "x"},
    )
    assert called["count"] == 0  # gemini should not be called
    assert result.get("source") == "barcode"
