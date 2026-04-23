"""Tests para POST /scan/contribute — flujo contributivo Open Food Facts (Fase 2)."""

import httpx
import pytest
from sqlalchemy import select

from app.models.off_contribution import OFFContribution
from tests.conftest import TEST_SETTINGS

# ─────────────────────────────────────────────
# Helpers de mock (extienden el patrón de test_services_external.py)
# ─────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code}",
                request=httpx.Request("POST", "http://x"),
                response=httpx.Response(self.status_code),
            )


class _FakeAsyncClient:
    """Soporta .get() y .post() para cubrir tanto fetch_product como contribute_product."""

    def __init__(self, response: _FakeResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, *args, **kwargs):
        return self._response

    async def post(self, *args, **kwargs):
        return self._response


# ─────────────────────────────────────────────
# Fixtures de autenticación
# ─────────────────────────────────────────────

async def _register_and_login(client) -> dict:
    """Registra un usuario de test y devuelve las cookies de sesión."""
    await client.post("/auth/register", json={"email": "contrib@test.com", "password": "test1234"})
    resp = await client.post("/auth/login", json={"email": "contrib@test.com", "password": "test1234"})
    assert resp.status_code == 200
    return resp.cookies


# ─────────────────────────────────────────────
# Tests de autenticación y validación
# ─────────────────────────────────────────────

async def test_contribute_requires_auth(client):
    resp = await client.post(
        "/scan/contribute",
        json={"barcode": "12345678", "ingredients": ["agua"], "consent": True},
    )
    assert resp.status_code == 401


async def test_contribute_consent_false_rejected(client):
    """Pydantic debe rechazar consent=False con 422."""
    cookies = await _register_and_login(client)
    resp = await client.post(
        "/scan/contribute",
        json={"barcode": "12345678", "ingredients": ["agua"], "consent": False},
        cookies=cookies,
    )
    assert resp.status_code == 422


async def test_contribute_empty_ingredients_rejected(client):
    cookies = await _register_and_login(client)
    resp = await client.post(
        "/scan/contribute",
        json={"barcode": "12345678", "ingredients": [], "consent": True},
        cookies=cookies,
    )
    assert resp.status_code == 422


async def test_contribute_barcode_too_short_rejected(client):
    cookies = await _register_and_login(client)
    resp = await client.post(
        "/scan/contribute",
        json={"barcode": "ab", "ingredients": ["agua"], "consent": True},
        cookies=cookies,
    )
    assert resp.status_code == 422


# ─────────────────────────────────────────────
# Tests de feature flag
# ─────────────────────────────────────────────

async def test_contribute_feature_flag_off_creates_failed_row(client, db_session, monkeypatch):
    """Con off_contrib_enabled=False el row se crea en FAILED sin llamar a OFF."""
    # off_contrib_enabled=False por defecto en TEST_SETTINGS
    assert TEST_SETTINGS.off_contrib_enabled is False

    cookies = await _register_and_login(client)
    resp = await client.post(
        "/scan/contribute",
        json={"barcode": "photo:abc123abc123abc1", "ingredients": ["azúcar", "agua"], "consent": True},
        cookies=cookies,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "PENDING"  # respuesta inmediata siempre PENDING

    # El task síncrono ya corrió (off_contrib_sync_for_tests=True)
    row = db_session.scalar(
        select(OFFContribution).where(OFFContribution.id == data["contribution_id"])
    )
    assert row is not None
    assert row.status == "FAILED"
    assert row.off_error == "Feature flag disabled"
    assert row.consent_at is not None
    assert row.submitted_at is not None


# ─────────────────────────────────────────────
# Tests de happy path (feature flag ON)
# ─────────────────────────────────────────────

async def test_contribute_happy_path(client, db_session, monkeypatch):
    """Con off_contrib_enabled=True y OFF respondiendo 200, el row llega a SUBMITTED."""
    monkeypatch.setattr(
        TEST_SETTINGS, "off_contrib_enabled", True
    )
    monkeypatch.setattr(
        TEST_SETTINGS, "off_contributor_user", "bioshield_app"
    )
    monkeypatch.setattr(
        TEST_SETTINGS, "off_contributor_password", "test_password"
    )
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(_FakeResponse(200))
    )

    cookies = await _register_and_login(client)
    resp = await client.post(
        "/scan/contribute",
        json={"barcode": "photo:happypath000001", "ingredients": ["azúcar", "agua", "sal"], "consent": True},
        cookies=cookies,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["contribution_id"] is not None

    row = db_session.scalar(
        select(OFFContribution).where(OFFContribution.id == data["contribution_id"])
    )
    assert row is not None
    assert row.status == "SUBMITTED"
    assert row.off_response_url is not None
    assert "openfoodfacts.org" in row.off_response_url
    assert row.off_error is None
    assert row.submitted_at is not None


async def test_contribute_with_image_sets_image_submitted(client, db_session, monkeypatch):
    """Cuando se incluye image_base64, image_submitted=True en el row."""
    import base64
    monkeypatch.setattr(TEST_SETTINGS, "off_contrib_enabled", True)
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(_FakeResponse(200)))

    fake_image = base64.b64encode(b"fake-jpeg-bytes").decode()
    cookies = await _register_and_login(client)
    resp = await client.post(
        "/scan/contribute",
        json={
            "barcode": "photo:withimage000001",
            "ingredients": ["harina"],
            "image_base64": fake_image,
            "consent": True,
        },
        cookies=cookies,
    )
    assert resp.status_code == 202

    row = db_session.scalar(
        select(OFFContribution).where(OFFContribution.id == resp.json()["contribution_id"])
    )
    assert row.status == "SUBMITTED"
    assert row.image_submitted is True


# ─────────────────────────────────────────────
# Tests de error en OFF
# ─────────────────────────────────────────────

async def test_contribute_off_5xx_creates_failed_row(client, db_session, monkeypatch):
    """Si OFF responde 5xx, el row queda en FAILED con off_error poblado."""
    monkeypatch.setattr(TEST_SETTINGS, "off_contrib_enabled", True)
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda *a, **kw: _FakeAsyncClient(_FakeResponse(500))
    )

    cookies = await _register_and_login(client)
    resp = await client.post(
        "/scan/contribute",
        json={"barcode": "photo:serverfail00001", "ingredients": ["colorante"], "consent": True},
        cookies=cookies,
    )
    assert resp.status_code == 202

    row = db_session.scalar(
        select(OFFContribution).where(OFFContribution.id == resp.json()["contribution_id"])
    )
    assert row.status == "FAILED"
    assert row.off_error is not None
    assert row.image_submitted is False


# ─────────────────────────────────────────────
# Tests de integridad del row
# ─────────────────────────────────────────────

async def test_contribute_row_stores_ingredients_text(client, db_session):
    """ingredients_text debe ser la lista de ingredientes unida por coma."""
    cookies = await _register_and_login(client)
    resp = await client.post(
        "/scan/contribute",
        json={"barcode": "photo:checktext00001", "ingredients": ["lecitina", "sorbitol", "agua"], "consent": True},
        cookies=cookies,
    )
    assert resp.status_code == 202

    row = db_session.scalar(
        select(OFFContribution).where(OFFContribution.id == resp.json()["contribution_id"])
    )
    assert row.ingredients_text == "lecitina, sorbitol, agua"
    assert row.consent_at is not None


async def test_contribute_response_shape(client):
    """La respuesta 202 tiene el shape de OFFContributeResponse."""
    cookies = await _register_and_login(client)
    resp = await client.post(
        "/scan/contribute",
        json={"barcode": "photo:shapetst000001", "ingredients": ["azúcar"], "consent": True},
        cookies=cookies,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "contribution_id" in data
    assert data["status"] in ("PENDING", "SUBMITTED", "FAILED")
    assert isinstance(data["message"], str)
