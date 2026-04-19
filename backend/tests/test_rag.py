"""Tests for RAG stack: rag.py, retrieval.py, entity_resolution.py, conflicts.py,
and the ingestion/common upsert helpers.

Chroma runs in ephemeral mode (no persistence directory). Embedding calls to
Gemini are mocked; real API keys are never needed in the test suite.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import Ingredient, RegulatoryStatus
from app.services.conflicts import detect_conflicts
from app.services.entity_resolution import resolve
from app.services.ingestion.common import (
    IngestionRecord,
    get_or_create_source,
    upsert_ingredient,
    upsert_regulatory_status,
)
from app.services.rag import build_embedding_template

# ─────────────────────────────────────────────
# rag.py helpers
# ─────────────────────────────────────────────

def test_embedding_template_shape():
    template = build_embedding_template(
        entity_id="CAS:13463-67-7",
        canonical_name="Titanium Dioxide",
        fda_status="APPROVED",
        efsa_status="BANNED",
        hazard_note="Genotoxicity",
    )
    assert template.startswith("[ID: CAS:13463-67-7]")
    assert "[Name: Titanium Dioxide]" in template
    assert "FDA:APPROVED/EFSA:BANNED" in template
    assert "[Risk: Genotoxicity]" in template


def test_embedding_template_handles_missing_fields():
    template = build_embedding_template(entity_id="x", canonical_name="Unknown")
    assert "N/A" in template


# ─────────────────────────────────────────────
# ingestion/common upsert helpers
# ─────────────────────────────────────────────

def test_upsert_ingredient_creates_then_updates(db_session):
    rec = IngestionRecord(
        canonical_name="Titanium Dioxide",
        cas_number="13463-67-7",
        synonyms=["Titania"],
    )
    ing = upsert_ingredient(db_session, rec)
    assert ing.id is not None
    assert ing.entity_id == "CAS:13463-67-7"

    # Second call with additional synonyms merges them
    rec2 = IngestionRecord(
        canonical_name="Titanium Dioxide",
        cas_number="13463-67-7",
        synonyms=["E171"],
    )
    ing2 = upsert_ingredient(db_session, rec2)
    assert ing2.id == ing.id
    assert set(ing2.synonyms) == {"Titania", "E171"}


def test_upsert_regulatory_status_keyed_by_source(db_session):
    source = get_or_create_source(
        db_session,
        name="FDA_EAFUS",
        region="US",
        version="v1",
        source_checksum="sha256:x",
        license_="Public Domain",
        format_="XLSX",
    )
    ing = upsert_ingredient(
        db_session, IngestionRecord(canonical_name="Aspartame", cas_number="22839-47-0")
    )
    rec = IngestionRecord(
        canonical_name="Aspartame", cas_number="22839-47-0", status="APPROVED"
    )
    first = upsert_regulatory_status(db_session, ing, source, rec)
    assert first.status == "APPROVED"

    # Update in place
    rec.status = "RESTRICTED"
    second = upsert_regulatory_status(db_session, ing, source, rec)
    assert second.id == first.id
    assert second.status == "RESTRICTED"

    statuses = db_session.scalars(
        select(RegulatoryStatus).where(RegulatoryStatus.ingredient_id == ing.id)
    ).all()
    assert len(statuses) == 1


# ─────────────────────────────────────────────
# entity_resolution.py
# ─────────────────────────────────────────────

def _seed_ingredient(db, canonical: str, cas: str | None = None, e: str | None = None, synonyms: list[str] | None = None):
    ing = Ingredient(
        canonical_name=canonical,
        cas_number=cas,
        e_number=e,
        synonyms=synonyms or [],
        entity_id=f"CAS:{cas}" if cas else (f"E:{e}" if e else None),
    )
    db.add(ing)
    db.flush()
    return ing


def test_resolve_exact_cas(db_session):
    _seed_ingredient(db_session, "Titanium Dioxide", cas="13463-67-7")
    res = resolve("Additive CAS 13463-67-7 in the label", db_session)
    assert res.confidence == 1.0
    assert res.matched_on == "cas"
    assert res.ingredient.canonical_name == "Titanium Dioxide"


def test_resolve_exact_e_number(db_session):
    _seed_ingredient(db_session, "Titanium Dioxide", e="E171")
    res = resolve("color E171", db_session)
    assert res.confidence == 0.95
    assert res.matched_on == "e_number"


def test_resolve_fuzzy_match(db_session):
    _seed_ingredient(db_session, "Monosodium Glutamate", synonyms=["MSG"])
    res = resolve("monosodium glutamate", db_session)
    assert res.matched_on == "fuzzy"
    assert res.confidence >= 0.7
    assert res.needs_hitl is False


def test_resolve_below_threshold_returns_none(db_session):
    _seed_ingredient(db_session, "Titanium Dioxide", cas="13463-67-7")
    res = resolve("totally unrelated gobbledygook xyzabc", db_session)
    assert res.ingredient is None
    assert res.matched_on == "none"


# ─────────────────────────────────────────────
# conflicts.py
# ─────────────────────────────────────────────

def test_detect_regulatory_conflict_high(db_session):
    fda = get_or_create_source(
        db_session, "FDA_EAFUS", "US", "v1", "sha256:a", "Public Domain", "XLSX"
    )
    efsa = get_or_create_source(
        db_session, "EFSA_OpenFoodTox", "EU", "v1", "sha256:b", "CC BY 4.0", "JSON"
    )
    ing = upsert_ingredient(
        db_session,
        IngestionRecord(canonical_name="Titanium Dioxide", cas_number="13463-67-7"),
    )
    upsert_regulatory_status(
        db_session, ing, fda,
        IngestionRecord(canonical_name="Titanium Dioxide", status="APPROVED"),
    )
    upsert_regulatory_status(
        db_session, ing, efsa,
        IngestionRecord(canonical_name="Titanium Dioxide", status="BANNED", hazard_note="Genotoxicity"),
    )

    conflicts = detect_conflicts(ing, db_session)
    types = {c.conflict_type for c in conflicts}
    assert "REGULATORY" in types
    reg = next(c for c in conflicts if c.conflict_type == "REGULATORY")
    assert reg.severity == "HIGH"


def test_detect_scientific_conflict_medium(db_session):
    efsa = get_or_create_source(
        db_session, "EFSA_OpenFoodTox", "EU", "v1", "sha256:b", "CC BY 4.0", "JSON"
    )
    ing = upsert_ingredient(
        db_session, IngestionRecord(canonical_name="Aspartame", cas_number="22839-47-0")
    )
    upsert_regulatory_status(
        db_session, ing, efsa,
        IngestionRecord(
            canonical_name="Aspartame",
            status="APPROVED",
            hazard_note="IARC Group 2B (possibly carcinogenic)",
        ),
    )
    conflicts = detect_conflicts(ing, db_session)
    scientific = [c for c in conflicts if c.conflict_type == "SCIENTIFIC"]
    assert len(scientific) == 1
    assert scientific[0].severity == "MEDIUM"


def test_detect_temporal_conflict_low(db_session):
    fda = get_or_create_source(
        db_session, "FDA_EAFUS", "US", "v1", "sha256:a", "Public Domain", "XLSX"
    )
    ing = upsert_ingredient(
        db_session, IngestionRecord(canonical_name="BHA", cas_number="25013-16-5")
    )
    stale = datetime.now(UTC) - timedelta(days=900)
    upsert_regulatory_status(
        db_session, ing, fda,
        IngestionRecord(canonical_name="BHA", status="APPROVED", evaluated_at=stale),
    )
    conflicts = detect_conflicts(ing, db_session)
    temporal = [c for c in conflicts if c.conflict_type == "TEMPORAL"]
    assert len(temporal) == 1
    assert temporal[0].severity == "LOW"


def test_no_conflict_single_approval(db_session):
    fda = get_or_create_source(
        db_session, "FDA_EAFUS", "US", "v1", "sha256:a", "Public Domain", "XLSX"
    )
    ing = upsert_ingredient(
        db_session, IngestionRecord(canonical_name="Salt", cas_number="7647-14-5")
    )
    upsert_regulatory_status(
        db_session, ing, fda,
        IngestionRecord(
            canonical_name="Salt",
            status="APPROVED",
            evaluated_at=datetime.now(UTC),
        ),
    )
    assert detect_conflicts(ing, db_session) == []


# ─────────────────────────────────────────────
# retrieval.py — BM25 fallback path
# ─────────────────────────────────────────────

async def test_hybrid_search_bm25_fallback(db_session, monkeypatch):
    """Force vector search failure; retrieval must degrade to BM25."""
    from app.services import retrieval

    _seed_ingredient(db_session, "Titanium Dioxide", cas="13463-67-7", synonyms=["E171"])
    _seed_ingredient(db_session, "Aspartame", cas="22839-47-0", synonyms=["E951"])

    async def _fail_embed(*args, **kwargs):
        raise RuntimeError("no gemini in test")

    monkeypatch.setattr(retrieval, "embed_text", _fail_embed)

    from tests.conftest import TEST_SETTINGS
    results = await retrieval.hybrid_search("titanium dioxide", db_session, TEST_SETTINGS)
    assert results
    # Top hit should be Titanium Dioxide; degraded flag present
    top = results[0]
    assert "Titanium" in top.document
    assert top.metadata.get("degraded") is True
