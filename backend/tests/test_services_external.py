"""Unit tests for off_client + gemini helper layer (no network)."""

import base64

import httpx
import pytest

from app.config import Settings
from app.schemas.models import ProductExtraction
from app.services import gemini as gemini_service
from app.services.off_client import _parse_ingredients, fetch_product
from tests.conftest import TEST_SETTINGS


# ─────────────────────────────────────────────
# _parse_ingredients
# ─────────────────────────────────────────────

def test_parse_ingredients_basic():
    text = "sugar, water, salt"
    assert _parse_ingredients(text) == ["sugar", "water", "salt"]


def test_parse_ingredients_drops_parentheticals():
    text = "flour (wheat, enriched), sugar, salt (sodium chloride)"
    assert _parse_ingredients(text) == ["flour", "sugar", "salt"]


def test_parse_ingredients_mixed_separators():
    assert _parse_ingredients("sugar; water, salt; msg") == [
        "sugar",
        "water",
        "salt",
        "msg",
    ]


def test_parse_ingredients_empty_cases():
    assert _parse_ingredients(None) == []
    assert _parse_ingredients("") == []
    assert _parse_ingredients(", ,,") == []


# ─────────────────────────────────────────────
# fetch_product — OFF client
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
                request=httpx.Request("GET", "http://x"),
                response=httpx.Response(self.status_code),
            )


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, *args, **kwargs):
        return self._response


async def test_fetch_product_success(monkeypatch):
    payload = {
        "status": 1,
        "product": {
            "product_name": "Coke",
            "brands": "Coca-Cola",
            "ingredients_text": "carbonated water, sugar, caffeine",
            "image_url": "https://x/coke.jpg",
        },
    }
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: _FakeAsyncClient(_FakeResponse(200, payload)),
    )
    result = await fetch_product("7501", TEST_SETTINGS)
    assert result is not None
    assert result["name"] == "Coke"
    assert result["ingredients"] == ["carbonated water", "sugar", "caffeine"]


async def test_fetch_product_404(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: _FakeAsyncClient(_FakeResponse(404)),
    )
    assert await fetch_product("0000", TEST_SETTINGS) is None


async def test_fetch_product_status_zero(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: _FakeAsyncClient(_FakeResponse(200, {"status": 0})),
    )
    assert await fetch_product("0000", TEST_SETTINGS) is None


async def test_fetch_product_no_ingredients_returns_none(monkeypatch):
    payload = {"status": 1, "product": {"product_name": "Mystery", "ingredients_text": ""}}
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *a, **kw: _FakeAsyncClient(_FakeResponse(200, payload)),
    )
    assert await fetch_product("7501", TEST_SETTINGS) is None


async def test_fetch_product_timeout_returns_none(monkeypatch):
    class _Timeout(_FakeAsyncClient):
        async def get(self, *a, **kw):
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: _Timeout(_FakeResponse(200)))
    assert await fetch_product("7501", TEST_SETTINGS) is None


# ─────────────────────────────────────────────
# Gemini image decode
# ─────────────────────────────────────────────

def test_decode_image_valid():
    raw = b"\x89PNG\r\n\x1a\n" + b"x" * 100
    b64 = base64.b64encode(raw).decode()
    assert gemini_service._decode_image(b64) == raw


def test_decode_image_invalid_b64():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        gemini_service._decode_image("!!!not-base64!!!")
    assert exc.value.status_code == 400


def test_decode_image_too_large():
    from fastapi import HTTPException
    oversized = base64.b64encode(b"x" * (11 * 1024 * 1024)).decode()
    with pytest.raises(HTTPException) as exc:
        gemini_service._decode_image(oversized)
    assert exc.value.status_code == 413


# ─────────────────────────────────────────────
# Gemini extract_from_image (mocked)
# ─────────────────────────────────────────────

class _FakeGeminiResponse:
    def __init__(self, data: dict):
        self._text = ProductExtraction(**data).model_dump_json()
        self.parsed = None

    @property
    def text(self):
        return self._text


class _FakeModel:
    def __init__(self, response):
        self._response = response

    async def generate_content_async(self, *args, **kwargs):
        return self._response


async def test_extract_from_image_roundtrip(monkeypatch):
    fake = _FakeGeminiResponse({"ingredients": ["sugar", "water"], "has_additives": False})
    monkeypatch.setattr(gemini_service.genai, "configure", lambda **kw: None)
    monkeypatch.setattr(
        gemini_service.genai,
        "GenerativeModel",
        lambda *a, **kw: _FakeModel(fake),
    )
    raw = base64.b64encode(b"\x89PNG fake").decode()
    result = await gemini_service.extract_from_image(raw, TEST_SETTINGS)
    assert isinstance(result, ProductExtraction)
    assert result.ingredients == ["sugar", "water"]
