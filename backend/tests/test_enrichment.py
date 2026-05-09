"""Tests for the product enrichment service."""
import pytest
from sqlalchemy import select

from app.models import (
    DataSource,
    Ingredient,
    Product,
    RegulatoryStatus,
    ScanHistory,
    User,
)
from app.schemas.models import IngredientResult


# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_ingredient_result(name: str, canonical: str | None, score: float = 0.9) -> IngredientResult:
    return IngredientResult(name=name, canonical_name=canonical, confidence_score=score)


def _add_product(db, barcode: str, ingredients_json=None) -> Product:
    p = Product(barcode=barcode, name=f"Prod {barcode}")
    if ingredients_json is not None:
        p.ingredients_json = ingredients_json
    db.add(p)
    db.flush()
    return p


def _add_data_source(db, name: str = "TEST") -> DataSource:
    ds = DataSource(id=f"ds-{name}", name=name, region="GLOBAL")
    db.add(ds)
    db.flush()
    return ds


# ─── should_enrich ───────────────────────────────────────────────────────────


def test_should_enrich_returns_true_for_clean_product(db_session):
    from app.services.enrichment import should_enrich
    product = _add_product(db_session, "7501111111111")
    assert should_enrich(product) is True


def test_should_enrich_returns_false_if_already_enriched(db_session):
    from app.services.enrichment import should_enrich
    product = _add_product(db_session, "7501111111112", ingredients_json=["azucar"])
    assert should_enrich(product) is False


def test_should_enrich_returns_false_for_pseudo_barcode(db_session):
    from app.services.enrichment import should_enrich
    product = _add_product(db_session, "photo-abc123def456")
    assert should_enrich(product) is False


# ─── _compute_clean_score ────────────────────────────────────────────────────


def test_compute_clean_score_ignores_unknown_ingredients(db_session):
    from app.services.enrichment import _compute_clean_score
    score = _compute_clean_score(["ingrediente_inexistente_xyz"], db_session)
    assert score == 0


def test_compute_clean_score_counts_banned_ingredients(db_session):
    from app.services.enrichment import _compute_clean_score

    ds = _add_data_source(db_session, "TEST-BANNED")

    ing = Ingredient(
        id="test-ing-1",
        canonical_name="test_banned_ing",
        entity_id="CAS:00000-00-0",
    )
    db_session.add(ing)
    db_session.flush()

    status = RegulatoryStatus(
        id="test-rs-1",
        ingredient_id=ing.id,
        source_id=ds.id,
        status="Banned",
    )
    db_session.add(status)
    db_session.flush()

    score = _compute_clean_score(["test_banned_ing"], db_session)
    assert score == 1


# ─── enrich_product ──────────────────────────────────────────────────────────


async def test_enrich_product_skips_if_low_confidence(db_session):
    from app.services.enrichment import enrich_product
    product = _add_product(db_session, "7501111111113")
    resolved = [_make_ingredient_result("azucar", "sucrose", score=0.5)]
    await enrich_product(
        barcode="7501111111113",
        resolved=resolved,
        avg_confidence=0.5,
        source="scan",
        db=db_session,
        settings=None,
    )
    db_session.refresh(product)
    assert product.ingredients_json is None


async def test_enrich_product_writes_ingredients_and_score(db_session, monkeypatch):
    from app.services import enrichment as enrichment_module

    async def _fake_reindex(*args, **kwargs):
        pass

    monkeypatch.setattr(enrichment_module, "_reindex_chroma", _fake_reindex)
    product = _add_product(db_session, "7501111111114")
    resolved = [_make_ingredient_result("water", "water", score=0.95)]
    await enrichment_module.enrich_product(
        barcode="7501111111114",
        resolved=resolved,
        avg_confidence=0.95,
        source="scan",
        db=db_session,
        settings=object(),
    )
    db_session.refresh(product)
    assert product.ingredients_json == ["water"]
    assert product.ingredients_source == "scan"
    assert product.ingredients_confidence == pytest.approx(0.95)


async def test_enrich_product_concurrent_skip(db_session, monkeypatch):
    """Segundo call al mismo barcode no sobreescribe el primero."""
    from app.services import enrichment as enrichment_module

    async def _fake_reindex(*args, **kwargs):
        pass

    monkeypatch.setattr(enrichment_module, "_reindex_chroma", _fake_reindex)
    product = _add_product(db_session, "7501111111115")
    resolved_a = [_make_ingredient_result("sugar", "sucrose", score=0.9)]
    resolved_b = [_make_ingredient_result("salt", "sodium chloride", score=0.95)]

    await enrichment_module.enrich_product("7501111111115", resolved_a, 0.9, "scan", db_session, object())
    await enrichment_module.enrich_product("7501111111115", resolved_b, 0.95, "scan", db_session, object())

    db_session.refresh(product)
    assert product.ingredients_json == ["sucrose"]


# ─── link_photo_to_barcode ───────────────────────────────────────────────────


async def test_link_photo_to_barcode_validates_ownership(db_session, monkeypatch):
    from fastapi import HTTPException
    from app.services.enrichment import link_photo_to_barcode

    user = User(id="user-1", email="a@b.com", password_hash="x")
    db_session.add(user)
    pseudo = _add_product(db_session, "photo-aabbccddeeff0011")
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await link_photo_to_barcode("photo-aabbccddeeff0011", "7501000000001", "user-2", db_session, None)

    assert exc_info.value.status_code == 403


async def test_link_photo_to_barcode_enriches_real_product(db_session, monkeypatch):
    from app.services import enrichment as enrichment_module

    async def _fake_reindex(*args, **kwargs):
        pass

    async def _fake_enrich(barcode, resolved, avg_confidence, source, db, settings):
        product = db.scalar(select(Product).where(Product.barcode == barcode))
        if product:
            product.ingredients_json = [r.canonical_name for r in resolved if r.canonical_name]
            db.commit()

    monkeypatch.setattr(enrichment_module, "_reindex_chroma", _fake_reindex)
    monkeypatch.setattr(enrichment_module, "enrich_product", _fake_enrich)

    user = User(id="user-3", email="c@d.com", password_hash="x")
    db_session.add(user)
    db_session.flush()

    pseudo = _add_product(db_session, "photo-112233445566aabb")
    pseudo.needs_barcode_link = True
    db_session.flush()

    history = ScanHistory(
        id="hist-1",
        user_id="user-3",
        product_barcode="photo-112233445566aabb",
        confidence_score=0.92,
        result_json={"ingredients": [{"name": "water", "canonical_name": "water", "confidence_score": 0.92, "conflicts": []}]},
        semaphore_result="BLUE",
    )
    db_session.add(history)
    db_session.commit()

    real = await enrichment_module.link_photo_to_barcode(
        "photo-112233445566aabb", "7502000000001", "user-3", db_session, None
    )

    assert real.barcode == "7502000000001"
    db_session.refresh(pseudo)
    assert pseudo.needs_barcode_link is False
