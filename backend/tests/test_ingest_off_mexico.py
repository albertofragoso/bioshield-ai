"""Tests for the OFF Mexico ingestion script.

HTTP calls are mocked — no network required.
"""
import json
from unittest.mock import patch


def _make_hit(
    code="1234567890123",
    name="Yogurt Natural",
    name_es=None,
    brands="Danone,Other",
    categories="en:yogurts,en:dairy",
    ingredients="Leche, Fermentos lácteos",
    image="https://img.off.org/test.jpg",
) -> dict:
    return {
        "code": code,
        "product_name": name,
        "product_name_es": name_es,
        "brands": brands,
        "categories_tags": categories,
        "ingredients_text": ingredients,
        "image_front_url": image,
    }


def test_map_product_valid():
    from scripts.ingest_off_mexico import _map_product

    result = _map_product(_make_hit(), "en:yogurts")
    assert result is not None
    assert result["barcode"] == "1234567890123"
    assert result["name"] == "Yogurt Natural"
    assert result["brand"] == "Danone"
    assert result["category"] == "yogurts"
    assert "Leche" in result["ingredients_json"]
    assert result["ingredients_source"] == "off_dump_mx"


def test_map_product_prefers_spanish_name():
    from scripts.ingest_off_mexico import _map_product

    hit = _make_hit(name="Natural Yogurt", name_es="Yogurt Natural")
    result = _map_product(hit, "en:yogurts")
    assert result["name"] == "Yogurt Natural"


def test_map_product_returns_none_without_barcode():
    from scripts.ingest_off_mexico import _map_product

    assert _map_product(_make_hit(code=""), "en:yogurts") is None


def test_map_product_returns_none_without_name():
    from scripts.ingest_off_mexico import _map_product

    assert _map_product(_make_hit(name="", name_es=None), "en:yogurts") is None


def test_map_product_returns_none_without_ingredients():
    from scripts.ingest_off_mexico import _map_product

    assert _map_product(_make_hit(ingredients=""), "en:yogurts") is None


def test_map_product_returns_none_when_parser_yields_empty():
    from scripts.ingest_off_mexico import _map_product

    # ingredients_text that parses to empty (all stripped)
    assert _map_product(_make_hit(ingredients="   "), "en:yogurts") is None


def test_map_product_strips_extra_brands():
    from scripts.ingest_off_mexico import _map_product

    result = _map_product(_make_hit(brands="  Quaker , Other"), "en:yogurts")
    assert result["brand"] == "Quaker"


def test_main_writes_json_and_deduplicates(tmp_path):
    from scripts.ingest_off_mexico import main as ingest_main

    hit = _make_hit()
    mock_page = {"hits": [hit], "count": 1}
    empty_page = {"hits": [], "count": 1}

    def fake_fetch(category, page):
        return mock_page if page == 1 else empty_page

    with (
        patch("scripts.ingest_off_mexico._fetch_page", side_effect=fake_fetch),
        patch("scripts.ingest_off_mexico.OUTPUT_PATH", tmp_path / "out.json"),
    ):
        ingest_main()

    data = json.loads((tmp_path / "out.json").read_text())
    # Same barcode appears in multiple categories — dedup should keep only 1
    barcodes = [p["barcode"] for p in data]
    assert barcodes.count("1234567890123") == 1


def test_main_skips_http_errors(tmp_path):
    import requests

    from scripts.ingest_off_mexico import main as ingest_main

    def fake_fetch(category, page):
        raise requests.RequestException("timeout")

    with (
        patch("scripts.ingest_off_mexico._fetch_page", side_effect=fake_fetch),
        patch("scripts.ingest_off_mexico.OUTPUT_PATH", tmp_path / "out.json"),
    ):
        ingest_main()  # should not raise

    data = json.loads((tmp_path / "out.json").read_text())
    assert data == []
