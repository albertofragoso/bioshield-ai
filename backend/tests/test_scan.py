"""Tests for /scan/barcode and /scan/photo endpoints.

External services (OFF, Gemini) are monkey-patched at the module boundary —
the router calls `off_client.fetch_product(...)` and `gemini.extract_from_image(...)`
and we replace those attributes per test.
"""

import base64
import json as json_module

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


async def _stream_scan_barcode(client, barcode: str) -> dict:
    """Consume el stream SSE de /scan/barcode y retorna los datos acumulados de todos los eventos."""
    result: dict = {}
    lines_buf = []
    async with client.stream("POST", BARCODE_URL, json={"barcode": barcode}) as response:
        if response.status_code != 200:
            # Si el auth falló u otro error HTTP antes del stream
            return {"_status_code": response.status_code}
        async for line in response.aiter_lines():
            lines_buf.append(line)

    # Parsea eventos SSE del buffer completo
    current_event = None
    for line in lines_buf:
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and current_event:
            try:
                data = json_module.loads(line.removeprefix("data: ").strip())
                result[current_event] = data
            except json_module.JSONDecodeError:
                pass
            current_event = None

    return result


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


async def test_barcode_product_not_found_returns_error_event(client, monkeypatch):
    """Cuando el producto no existe, el stream emite evento error con código PRODUCT_NOT_FOUND."""
    await _register(client)

    async def _fake(*args, **kwargs):
        return None

    monkeypatch.setattr(off_module, "fetch_product", _fake)

    events = await _stream_scan_barcode(client, "0000000000000")
    # El endpoint debe emitir event:error — no debe llegar a done
    assert "error" in events, f"Se esperaba evento 'error', se recibieron: {list(events.keys())}"
    assert "done" not in events, "No debe emitirse 'done' cuando el producto no existe"
    assert events["error"].get("code") == "PRODUCT_NOT_FOUND"


async def test_barcode_success_returns_scan_response(client, monkeypatch):
    await _register(client)

    async def _fake(barcode, settings):
        return _off_payload(barcode, ["sugar", "water"])

    monkeypatch.setattr(off_module, "fetch_product", _fake)

    events = await _stream_scan_barcode(client, "7501234567890")
    assert "semaphore" in events or "done" in events


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

    events = await _stream_scan_barcode(client, "7501234567890")
    assert "semaphore" in events
    assert events["semaphore"]["semaphore"] == "RED"
    assert events["semaphore"]["conflict_severity"] == "HIGH"


async def test_barcode_approved_ingredients_return_blue(client, db_session, monkeypatch):
    await _register(client)
    source = _seed_source(db_session, name="FDA")
    ing = _seed_ingredient(db_session, canonical_name="Sugar", synonyms=["sugar", "azúcar"])
    _seed_reg_status(db_session, ing, source, "Approved")
    db_session.commit()

    async def _fake(barcode, settings):
        return _off_payload(barcode, ["sugar"])

    monkeypatch.setattr(off_module, "fetch_product", _fake)

    events = await _stream_scan_barcode(client, "7501234567890")
    assert "semaphore" in events
    assert events["semaphore"]["semaphore"] == "BLUE"


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

    events = await _stream_scan_barcode(client, "7501234567890")
    assert "semaphore" in events
    assert events["semaphore"]["semaphore"] == "YELLOW"


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

    events = await _stream_scan_barcode(client, "7501234567890")
    assert "semaphore" in events
    assert events["semaphore"]["semaphore"] == "ORANGE"
    assert events["semaphore"]["conflict_severity"] == "HIGH"


async def test_barcode_unresolved_ingredients_return_gray(client, db_session, monkeypatch):
    await _register(client)

    async def _fake(barcode, settings):
        return _off_payload(barcode, ["totally-unknown-additive-xyz"])

    monkeypatch.setattr(off_module, "fetch_product", _fake)

    events = await _stream_scan_barcode(client, "7501234567890")
    assert "semaphore" in events
    assert events["semaphore"]["semaphore"] == "GRAY"


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

    events = await _stream_scan_barcode(client, "7501234567890")
    assert "semaphore" in events
    assert events["semaphore"]["semaphore"] == "RED"


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


# ─────────────────────────────────────────────
# /scan/contribute — ownership check
# ─────────────────────────────────────────────

CONTRIBUTE_URL = "/scan/contribute"
LOGIN_URL = "/auth/login"


async def test_contribute_rejects_unowned_scan_history_id(client, db_session):
    """contribute must return 403 if scan_history_id belongs to another user."""
    from app.models import User

    await client.post(REGISTER_URL, json={"email": "usera@test.ai", "password": "pass123456"})
    await client.post(REGISTER_URL, json={"email": "userb@test.ai", "password": "pass123456"})

    userb = db_session.scalar(select(User).where(User.email == "userb@test.ai"))

    product = Product(barcode="9991111111111", name="Foreign Product", brand=None, image_url=None)
    db_session.add(product)
    db_session.flush()

    foreign_scan = ScanHistory(
        user_id=userb.id,
        product_barcode="9991111111111",
        semaphore_result="GRAY",
        result_json={"product_barcode": "9991111111111", "semaphore": "GRAY", "ingredients": []},
    )
    db_session.add(foreign_scan)
    db_session.commit()

    await client.post(LOGIN_URL, json={"email": "usera@test.ai", "password": "pass123456"})

    response = await client.post(
        CONTRIBUTE_URL,
        json={
            "barcode": "9991111111111",
            "ingredients": ["sugar"],
            "scan_history_id": str(foreign_scan.id),
            "consent": True,
        },
    )
    assert response.status_code == 403


async def test_contribute_accepts_owned_scan_history_id(client, db_session, monkeypatch):
    """contribute must accept scan_history_id owned by the authenticated user."""
    from app.models import User
    from app.services import off_client as off_mod

    await client.post(REGISTER_URL, json={"email": "ownera@test.ai", "password": "pass123456"})
    await client.post(LOGIN_URL, json={"email": "ownera@test.ai", "password": "pass123456"})

    user = db_session.scalar(select(User).where(User.email == "ownera@test.ai"))
    product = Product(barcode="8881111111111", name="My Product", brand=None, image_url=None)
    db_session.add(product)
    db_session.flush()
    own_scan = ScanHistory(
        user_id=user.id,
        product_barcode="8881111111111",
        semaphore_result="GRAY",
        result_json={"product_barcode": "8881111111111", "semaphore": "GRAY", "ingredients": []},
    )
    db_session.add(own_scan)
    db_session.commit()

    monkeypatch.setattr(off_mod, "contribute_product", lambda *a, **kw: None)

    response = await client.post(
        CONTRIBUTE_URL,
        json={
            "barcode": "8881111111111",
            "ingredients": ["sugar"],
            "scan_history_id": str(own_scan.id),
            "consent": True,
        },
    )
    assert response.status_code == 202


async def test_contribute_without_scan_history_id_accepted(client, monkeypatch):
    """scan_history_id is optional — omitting it must work normally."""
    from app.services import off_client as off_mod

    await client.post(REGISTER_URL, json={"email": "noid@test.ai", "password": "pass123456"})
    await client.post(LOGIN_URL, json={"email": "noid@test.ai", "password": "pass123456"})

    monkeypatch.setattr(off_mod, "contribute_product", lambda *a, **kw: None)

    response = await client.post(
        CONTRIBUTE_URL,
        json={
            "barcode": "0000000000001",
            "ingredients": ["sugar"],
            "consent": True,
        },
    )
    assert response.status_code == 202


def test_scan_photo_has_token_budget_dep():
    import inspect

    from app.routers.scan import scan_photo

    source = inspect.getsource(scan_photo)
    assert "token_budget" in source, "/scan/photo missing token_budget dependency"


def test_scan_barcode_has_token_budget_dep():
    import inspect

    from app.routers.scan import scan_barcode

    source = inspect.getsource(scan_barcode)
    assert "token_budget" in source, "/scan/barcode missing token_budget dependency"


# ─────────────────────────────────────────────
# /scan/result/{barcode} — personalized_insights
# ─────────────────────────────────────────────


async def test_scan_result_returns_persisted_insights(client, db_session):
    """GET /scan/result/{barcode} must return personalized_insights stored in result_json."""
    from app.models import User

    await _register(client)
    user = db_session.scalar(select(User).where(User.email == _EMAIL))

    product = Product(barcode="1111111111111", name="Insight Product", brand=None, image_url=None)
    db_session.add(product)
    db_session.flush()

    insight = {
        "biomarker_name": "ldl",
        "biomarker_value": 180.0,
        "biomarker_unit": "mg/dL",
        "classification": "high",
        "affecting_ingredients": ["hydrogenated oil"],
        "severity": "HIGH",
        "kind": "alert",
        "impact_direction": "raises",
        "reference_range_low": 0.0,
        "reference_range_high": 100.0,
        "friendly_title": "LDL elevado",
        "friendly_biomarker_label": "Colesterol LDL",
        "friendly_explanation": "Este ingrediente puede elevar tu LDL.",
        "friendly_recommendation": "Evita este producto.",
        "avatar_variant": "red",
    }
    result_json = {
        "product_barcode": "1111111111111",
        "product_name": "Insight Product",
        "semaphore": "ORANGE",
        "ingredients": [],
        "conflict_severity": "HIGH",
        "source": "barcode",
        "scanned_at": "2026-01-01T00:00:00+00:00",
        "personalized_insights": [insight],
    }
    db_session.add(
        ScanHistory(
            user_id=user.id,
            product_barcode="1111111111111",
            semaphore_result="ORANGE",
            result_json=result_json,
        )
    )
    db_session.commit()

    response = await client.get("/scan/result/1111111111111")
    assert response.status_code == 200
    body = response.json()
    assert len(body["personalized_insights"]) == 1
    assert body["personalized_insights"][0]["biomarker_name"] == "ldl"


async def test_scan_result_accepts_photo_id(client, db_session):
    """GET /scan/result/photo-abc123 must return 200 for photo pseudo-barcodes."""
    from app.models import User

    await _register(client)
    user = db_session.scalar(select(User).where(User.email == _EMAIL))

    photo_barcode = "photo-abc123"
    product = Product(barcode=photo_barcode, name="Photo Product", brand=None, image_url=None)
    db_session.add(product)
    db_session.flush()

    result_json = {
        "product_barcode": photo_barcode,
        "product_name": "Photo Product",
        "semaphore": "GRAY",
        "ingredients": [],
        "conflict_severity": None,
        "source": "photo",
        "scanned_at": "2026-01-01T00:00:00+00:00",
        "personalized_insights": [],
    }
    db_session.add(
        ScanHistory(
            user_id=user.id,
            product_barcode=photo_barcode,
            semaphore_result="GRAY",
            result_json=result_json,
        )
    )
    db_session.commit()

    response = await client.get(f"/scan/result/{photo_barcode}")
    assert response.status_code == 200
    assert response.json()["product_barcode"] == photo_barcode
    assert response.json()["source"] == "photo"
    assert response.json()["personalized_insights"] == []


async def test_persist_scan_history_stores_personalized_insights(client, db_session, monkeypatch):
    """POST /scan/barcode debe persistir personalized_insights en result_json via stream SSE."""
    from app.routers import scan as scan_router_module

    await _register(client)

    insight = {
        "biomarker_name": "ldl",
        "biomarker_value": 165.0,
        "biomarker_unit": "mg/dL",
        "classification": "high",
        "affecting_ingredients": ["palm oil"],
        "severity": "HIGH",
        "kind": "alert",
        "impact_direction": "raises",
        "reference_range_low": 0.0,
        "reference_range_high": 100.0,
        "friendly_title": "LDL elevado",
        "friendly_biomarker_label": "Colesterol LDL",
        "friendly_explanation": "El aceite de palma puede elevar el LDL.",
        "friendly_recommendation": "Evita este producto.",
        "avatar_variant": "red",
    }

    async def _stream(*args, **kwargs):
        yield {"event": "on_chain_start", "name": "LangGraph", "data": {}}
        yield {
            "event": "on_chain_end",
            "name": "identify_product",
            "data": {"output": {
                "product_name": "Palm Oil Snack",
                "product_brand": "TestBrand",
                "extracted_ingredients": ["palm oil"],
                "source": "barcode",
            }},
        }
        yield {
            "event": "on_chain_end",
            "name": "personalize",
            "data": {"output": {"personalized_insights": [insight]}},
        }
        yield {
            "event": "on_chain_end",
            "name": "calculate_risk",
            "data": {"output": {
                "semaphore": "ORANGE",
                "conflict_severity": "HIGH",
                "resolved": [],
            }},
        }

    class _FakeGraph:
        def astream_events(self, *args, **kwargs):
            return _stream(*args, **kwargs)

    monkeypatch.setattr(scan_router_module, "build_scan_graph", lambda db, settings: _FakeGraph())

    # Consume el stream completo para que se persistan los datos
    await _stream_scan_barcode(client, "2222222222222")

    # Busca la fila done (no la pending)
    scan = db_session.scalar(
        select(ScanHistory)
        .where(ScanHistory.product_barcode == "2222222222222", ScanHistory.status == "done")
    )
    assert scan is not None
    assert scan.result_json is not None
    insights_in_db = scan.result_json.get("personalized_insights", [])
    assert len(insights_in_db) == 1
    assert insights_in_db[0]["biomarker_name"] == "ldl"


async def test_scan_result_legacy_row_missing_insights(client, db_session):
    """GET /scan/result/{barcode} must return [] not error when result_json lacks insights key."""
    from app.models import User

    await _register(client)
    user = db_session.scalar(select(User).where(User.email == _EMAIL))

    product = Product(barcode="3333333333333", name="Legacy Product", brand=None, image_url=None)
    db_session.add(product)
    db_session.flush()

    # Legacy row — no personalized_insights key
    result_json = {
        "product_barcode": "3333333333333",
        "product_name": "Legacy Product",
        "semaphore": "GRAY",
        "ingredients": [],
        "conflict_severity": None,
        "source": "barcode",
        "scanned_at": "2026-01-01T00:00:00+00:00",
    }
    db_session.add(
        ScanHistory(
            user_id=user.id,
            product_barcode="3333333333333",
            semaphore_result="GRAY",
            result_json=result_json,
        )
    )
    db_session.commit()

    response = await client.get("/scan/result/3333333333333")
    assert response.status_code == 200
    body = response.json()
    assert body["personalized_insights"] == []


async def test_scan_history_has_status_column(db_session):
    """Verifica que ScanHistory tiene columna status."""
    from sqlalchemy import inspect as sa_inspect

    from app.models import ScanHistory

    mapper = sa_inspect(ScanHistory)
    cols = {c.key for c in mapper.mapper.columns}
    assert "status" in cols


# Test que los nuevos helpers existen y son importables
def test_scan_helpers_exist():
    """Verifica que _create_pending_row y _finalize_scan_history existen en scan.py."""
    from app.routers import scan as scan_module
    assert hasattr(scan_module, '_create_pending_row'), "_create_pending_row no encontrado"
    assert hasattr(scan_module, '_finalize_scan_history'), "_finalize_scan_history no encontrado"


# ─────────────────────────────────────────────
# POST /scan/barcode — SSE streaming
# ─────────────────────────────────────────────

_STREAM_EMAIL = "stream@bioshield.ai"
_STREAM_PASSWORD = "streampassword123"


async def _register_stream(client) -> None:
    await client.post(REGISTER_URL, json={"email": _STREAM_EMAIL, "password": _STREAM_PASSWORD})


async def test_scan_barcode_returns_event_stream(client, mock_graph):
    """Verifica que el endpoint retorna content-type text/event-stream."""
    await _register_stream(client)
    async with client.stream("POST", "/scan/barcode",
                             json={"barcode": "1234567890123"}) as response:
        assert "text/event-stream" in response.headers.get("content-type", "")


async def test_scan_barcode_streams_events_in_order(client, mock_graph):
    """Verifica que los eventos llegan en orden: init → ingredients → insights → semaphore → done."""
    await _register_stream(client)
    event_names = []
    async with client.stream("POST", "/scan/barcode",
                             json={"barcode": "1234567890123"}) as response:
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event_names.append(line.split(":", 1)[1].strip())
    assert event_names == ["init", "ingredients", "insights", "semaphore", "done"]


async def test_scan_barcode_init_event_has_scan_id(client, mock_graph):
    """El evento init contiene scan_id y product_barcode."""
    import json as json_module

    await _register_stream(client)
    init_data = None
    lines_seen = []
    async with client.stream("POST", "/scan/barcode",
                             json={"barcode": "1234567890123"}) as response:
        async for line in response.aiter_lines():
            lines_seen.append(line)

    for i, line in enumerate(lines_seen):
        if line.strip() == "event: init" and i + 1 < len(lines_seen):
            data_line = lines_seen[i + 1]
            if data_line.startswith("data:"):
                init_data = json_module.loads(data_line.removeprefix("data: ").strip())
            break

    assert init_data is not None, f"No init event found. Lines: {lines_seen[:10]}"
    assert "scan_id" in init_data
    assert "product_barcode" in init_data
