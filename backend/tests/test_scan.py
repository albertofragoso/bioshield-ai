"""Tests for /scan/barcode and /scan/photo endpoints.

External services (OFF, Gemini) are monkey-patched at the module boundary —
the router calls `off_client.fetch_product(...)` and `gemini.extract_from_image(...)`
and we replace those attributes per test.
"""

import base64

from sqlalchemy import select

from app.models import (
    DataSource,
    Ingredient,
    Product,
    RegulatoryStatus,
    ScanHistory,
)
from app.schemas.models import ProductExtraction
from app.services import gemini as gemini_module
from app.services import off_client as off_module

REGISTER_URL = "/auth/register"
BARCODE_URL = "/scan/barcode"
PHOTO_URL = "/scan/photo"
UPLOAD_URL = "/biosync/upload"

_EMAIL = "scan@bioshield.ai"
_PASSWORD = "securepassword123"


async def _register(client) -> None:
    await client.post(REGISTER_URL, json={"email": _EMAIL, "password": _PASSWORD})


def _seed_source(db, name: str = "FDA", region: str = "US") -> DataSource:
    src = DataSource(name=name, region=region)
    db.add(src)
    db.flush()
    return src


def _seed_ingredient(
    db,
    *,
    canonical_name: str,
    synonyms: list[str] | None = None,
    cas: str | None = None,
    e_number: str | None = None,
) -> Ingredient:
    ing = Ingredient(
        canonical_name=canonical_name,
        synonyms=synonyms or [],
        cas_number=cas,
        e_number=e_number,
        entity_id=cas or e_number or canonical_name.lower().replace(" ", "_"),
    )
    db.add(ing)
    db.flush()
    return ing


def _seed_reg_status(db, ingredient: Ingredient, source: DataSource, status: str) -> None:
    db.add(
        RegulatoryStatus(
            ingredient_id=ingredient.id,
            source_id=source.id,
            status=status,
        )
    )
    db.flush()


def _off_payload(barcode: str, ingredients: list[str], name: str = "Test Product") -> dict:
    return {
        "barcode": barcode,
        "name": name,
        "brand": "TestBrand",
        "image_url": "https://x/image.jpg",
        "ingredients": ingredients,
    }


# ─────────────────────────────────────────────
# /scan/barcode — basic contract
# ─────────────────────────────────────────────


async def test_barcode_requires_auth(client):
    response = await client.post(BARCODE_URL, json={"barcode": "7501234567890"})
    assert response.status_code == 401


async def test_barcode_invalid_format_rejected(client):
    await _register(client)
    response = await client.post(BARCODE_URL, json={"barcode": "abc"})
    assert response.status_code == 422


async def test_barcode_product_not_found_returns_404(client, monkeypatch):
    await _register(client)

    async def _fake(*args, **kwargs):
        return None

    monkeypatch.setattr(off_module, "fetch_product", _fake)

    response = await client.post(BARCODE_URL, json={"barcode": "0000000000000"})
    assert response.status_code == 404
    assert "/scan/photo" in response.json()["detail"]


async def test_barcode_success_returns_scan_response(client, monkeypatch):
    await _register(client)

    async def _fake(barcode, settings):
        return _off_payload(barcode, ["sugar", "water"])

    monkeypatch.setattr(off_module, "fetch_product", _fake)

    response = await client.post(BARCODE_URL, json={"barcode": "7501234567890"})
    assert response.status_code == 200
    body = response.json()
    assert body["product_barcode"] == "7501234567890"
    assert body["product_name"] == "Test Product"
    assert body["source"] == "barcode"
    assert len(body["ingredients"]) == 2
    assert body["semaphore"] in {"GRAY", "BLUE"}


# ─────────────────────────────────────────────
# /scan/barcode — persistence
# ─────────────────────────────────────────────


async def test_barcode_persists_product_and_scan_history(client, db_session, monkeypatch):
    await _register(client)

    async def _fake(barcode, settings):
        return _off_payload(barcode, ["sugar"])

    monkeypatch.setattr(off_module, "fetch_product", _fake)

    await client.post(BARCODE_URL, json={"barcode": "7501234567890"})

    product = db_session.scalar(select(Product).where(Product.barcode == "7501234567890"))
    assert product is not None
    assert product.name == "Test Product"

    scan = db_session.scalar(select(ScanHistory))
    assert scan is not None
    assert scan.product_barcode == "7501234567890"


async def test_barcode_repeat_does_not_duplicate_product(client, db_session, monkeypatch):
    await _register(client)

    async def _fake(barcode, settings):
        return _off_payload(barcode, ["sugar"])

    monkeypatch.setattr(off_module, "fetch_product", _fake)

    await client.post(BARCODE_URL, json={"barcode": "7501234567890"})
    await client.post(BARCODE_URL, json={"barcode": "7501234567890"})

    products = db_session.scalars(select(Product)).all()
    assert len(products) == 1

    scans = db_session.scalars(select(ScanHistory)).all()
    assert len(scans) == 2


# ─────────────────────────────────────────────
# Semaphore logic
# ─────────────────────────────────────────────


async def test_barcode_banned_ingredient_returns_red(client, db_session, monkeypatch):
    await _register(client)
    source = _seed_source(db_session, name="FDA")
    ing = _seed_ingredient(db_session, canonical_name="Aspartame", synonyms=["aspartame"])
    _seed_reg_status(db_session, ing, source, "Banned")
    db_session.commit()

    async def _fake(barcode, settings):
        return _off_payload(barcode, ["aspartame"])

    monkeypatch.setattr(off_module, "fetch_product", _fake)

    response = await client.post(BARCODE_URL, json={"barcode": "7501234567890"})
    assert response.status_code == 200
    body = response.json()
    assert body["semaphore"] == "RED"
    assert body["conflict_severity"] == "HIGH"


async def test_barcode_approved_ingredients_return_blue(client, db_session, monkeypatch):
    await _register(client)
    source = _seed_source(db_session, name="FDA")
    ing = _seed_ingredient(db_session, canonical_name="Sugar", synonyms=["sugar", "azúcar"])
    _seed_reg_status(db_session, ing, source, "Approved")
    db_session.commit()

    async def _fake(barcode, settings):
        return _off_payload(barcode, ["sugar"])

    monkeypatch.setattr(off_module, "fetch_product", _fake)

    response = await client.post(BARCODE_URL, json={"barcode": "7501234567890"})
    body = response.json()
    assert body["semaphore"] == "BLUE"


async def test_barcode_restricted_returns_yellow(client, db_session, monkeypatch):
    await _register(client)
    source = _seed_source(db_session, name="EFSA")
    ing = _seed_ingredient(
        db_session,
        canonical_name="Titanium Dioxide",
        synonyms=["titanium dioxide"],
        e_number="E171",
    )
    _seed_reg_status(db_session, ing, source, "Restricted")
    db_session.commit()

    async def _fake(barcode, settings):
        return _off_payload(barcode, ["titanium dioxide"])

    monkeypatch.setattr(off_module, "fetch_product", _fake)

    response = await client.post(BARCODE_URL, json={"barcode": "7501234567890"})
    body = response.json()
    assert body["semaphore"] == "YELLOW"


async def test_barcode_with_biomarkers_detects_orange(client, db_session, monkeypatch):
    await _register(client)
    # Upload structured biomarker: LDL high (180 mg/dL > canonical 100)
    ldl_biomarker = {
        "name": "ldl",
        "raw_name": "Colesterol LDL",
        "value": 180.0,
        "unit": "mg/dL",
        "unit_normalized": True,
        "reference_range_low": 0.0,
        "reference_range_high": 100.0,
        "reference_source": "canonical",
        "classification": "high",
    }
    await client.post(
        UPLOAD_URL, json={"biomarkers": [ldl_biomarker], "lab_name": None, "test_date": None}
    )

    # Seed an ingredient whose name triggers the LDL rule
    source = _seed_source(db_session, name="FDA")
    ing = _seed_ingredient(
        db_session,
        canonical_name="Hydrogenated oil",
        synonyms=["aceite hidrogenado", "hydrogenated oil"],
    )
    _seed_reg_status(db_session, ing, source, "Approved")
    db_session.commit()

    async def _fake(barcode, settings):
        return _off_payload(barcode, ["aceite hidrogenado"])

    monkeypatch.setattr(off_module, "fetch_product", _fake)

    response = await client.post(BARCODE_URL, json={"barcode": "7501234567890"})
    body = response.json()
    assert body["semaphore"] == "ORANGE"
    assert body["conflict_severity"] == "HIGH"


async def test_barcode_unresolved_ingredients_return_gray(client, db_session, monkeypatch):
    await _register(client)

    async def _fake(barcode, settings):
        return _off_payload(barcode, ["totally-unknown-additive-xyz"])

    monkeypatch.setattr(off_module, "fetch_product", _fake)

    response = await client.post(BARCODE_URL, json={"barcode": "7501234567890"})
    body = response.json()
    assert body["semaphore"] == "GRAY"


# ─────────────────────────────────────────────
# Regulatory status aggregation
# ─────────────────────────────────────────────


async def test_barcode_aggregates_worst_status_across_sources(client, db_session, monkeypatch):
    """If FDA says Approved but EFSA says Banned, result is RED."""
    await _register(client)
    fda = _seed_source(db_session, name="FDA")
    efsa = _seed_source(db_session, name="EFSA", region="EU")
    ing = _seed_ingredient(db_session, canonical_name="Red 40", synonyms=["red 40"])
    _seed_reg_status(db_session, ing, fda, "Approved")
    _seed_reg_status(db_session, ing, efsa, "Banned")
    db_session.commit()

    async def _fake(barcode, settings):
        return _off_payload(barcode, ["red 40"])

    monkeypatch.setattr(off_module, "fetch_product", _fake)

    response = await client.post(BARCODE_URL, json={"barcode": "7501234567890"})
    assert response.json()["semaphore"] == "RED"


# ─────────────────────────────────────────────
# /scan/photo
# ─────────────────────────────────────────────


async def test_photo_requires_auth(client):
    image_b64 = base64.b64encode(b"fake").decode()
    response = await client.post(PHOTO_URL, json={"image_base64": image_b64})
    assert response.status_code == 401


async def test_photo_success(client, monkeypatch):
    await _register(client)

    async def _fake(image_b64, settings):
        return ProductExtraction(ingredients=["sugar", "water"], has_additives=False, language="es")

    monkeypatch.setattr(gemini_module, "extract_from_image", _fake)

    image_b64 = base64.b64encode(b"fake").decode()
    response = await client.post(PHOTO_URL, json={"image_base64": image_b64})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "photo"
    assert body["product_barcode"].startswith("photo-")
    assert len(body["ingredients"]) == 2


async def test_photo_empty_ingredients_rejected(client, monkeypatch):
    await _register(client)

    async def _fake(image_b64, settings):
        return ProductExtraction(ingredients=[], has_additives=False, language="es")

    monkeypatch.setattr(gemini_module, "extract_from_image", _fake)

    image_b64 = base64.b64encode(b"fake").decode()
    response = await client.post(PHOTO_URL, json={"image_base64": image_b64})
    assert response.status_code == 422


async def test_photo_creates_pseudo_barcode_product(client, db_session, monkeypatch):
    await _register(client)

    async def _fake(image_b64, settings):
        return ProductExtraction(ingredients=["sugar"], has_additives=False)

    monkeypatch.setattr(gemini_module, "extract_from_image", _fake)

    image_b64 = base64.b64encode(b"fake").decode()
    await client.post(PHOTO_URL, json={"image_base64": image_b64})

    product = db_session.scalar(select(Product))
    assert product is not None
    assert product.barcode.startswith("photo-")
