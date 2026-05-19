"""Tests for the USDA Branded Foods ingestion script.

HTTP calls are mocked — no network required.
"""

import json
from unittest.mock import patch


def _make_food(
    gtin="00030000315316",
    description="QUAKER INSTANT OATMEAL ORIGINAL",
    brand_owner="QUAKER OATS COMPANY",
    ingredients="WHOLE GRAIN ROLLED OATS, SALT, GUAR GUM",
    food_category="Breakfast Cereals",
    market_country="United States",
) -> dict:
    return {
        "gtinUpc": gtin,
        "description": description,
        "brandOwner": brand_owner,
        "ingredients": ingredients,
        "foodCategory": food_category,
        "marketCountry": market_country,
    }


def test_map_food_valid():
    from scripts.ingest_usda import _map_food

    result = _map_food(_make_food(), "cereals")
    assert result is not None
    assert result["barcode"] == "00030000315316"
    assert result["name"] == "Quaker Instant Oatmeal Original"
    assert result["brand"] == "QUAKER OATS COMPANY"
    assert result["category"] == "cereals"
    assert "WHOLE GRAIN ROLLED OATS" in result["ingredients_json"]
    assert result["ingredients_source"] == "usda_branded"
    assert result["image_url"] is None


def test_map_food_title_cases_name():
    from scripts.ingest_usda import _map_food

    result = _map_food(_make_food(description="WHOLE MILK GREEK YOGURT"), "dairy")
    assert result["name"] == "Whole Milk Greek Yogurt"


def test_map_food_returns_none_without_gtin():
    from scripts.ingest_usda import _map_food

    assert _map_food(_make_food(gtin=""), "cereals") is None
    assert _map_food(_make_food(gtin=None), "cereals") is None


def test_map_food_returns_none_without_description():
    from scripts.ingest_usda import _map_food

    assert _map_food(_make_food(description=""), "cereals") is None


def test_map_food_returns_none_without_ingredients():
    from scripts.ingest_usda import _map_food

    assert _map_food(_make_food(ingredients=""), "cereals") is None
    assert _map_food(_make_food(ingredients=None), "cereals") is None


def test_map_food_returns_none_when_parser_yields_empty():
    from scripts.ingest_usda import _map_food

    assert _map_food(_make_food(ingredients="   "), "cereals") is None


def test_map_food_skips_non_us_market():
    from scripts.ingest_usda import _map_food

    assert _map_food(_make_food(market_country="Canada"), "cereals") is None


def test_map_food_allows_empty_market_country():
    """marketCountry puede ser None o "" — no se descarta si falta el campo."""
    from scripts.ingest_usda import _map_food

    result = _map_food(_make_food(market_country=""), "cereals")
    assert result is not None

    result2 = _map_food(_make_food(market_country=None), "cereals")
    assert result2 is not None


def test_fetch_page_posts_correct_payload():
    import requests

    from scripts.ingest_usda import _fetch_page

    with patch.object(requests, "post") as mock_post:
        mock_post.return_value.json.return_value = {"foods": [], "totalHits": 0}
        mock_post.return_value.raise_for_status = lambda: None
        _fetch_page("cereals breakfast oatmeal granola", 1)

    call_kwargs = mock_post.call_args
    payload = call_kwargs[1]["json"]
    assert payload["dataType"] == ["Branded"]
    assert payload["pageSize"] == 200
    assert payload["pageNumber"] == 1
    assert "cereals" in payload["query"]


def test_main_writes_json_and_deduplicates(tmp_path):
    from scripts.ingest_usda import main as ingest_main

    food = _make_food()
    mock_page = {"foods": [food], "totalHits": 1}
    empty_page = {"foods": [], "totalHits": 0}

    def fake_fetch(query, page):
        return mock_page if page == 1 else empty_page

    with (
        patch("scripts.ingest_usda._fetch_page", side_effect=fake_fetch),
        patch("scripts.ingest_usda.OUTPUT_PATH", tmp_path / "out.json"),
    ):
        ingest_main()

    data = json.loads((tmp_path / "out.json").read_text())
    barcodes = [p["barcode"] for p in data]
    assert barcodes.count("00030000315316") == 1


def test_main_skips_http_errors(tmp_path):
    import requests

    from scripts.ingest_usda import main as ingest_main

    def fake_fetch(query, page):
        raise requests.RequestException("timeout")

    with (
        patch("scripts.ingest_usda._fetch_page", side_effect=fake_fetch),
        patch("scripts.ingest_usda.OUTPUT_PATH", tmp_path / "out.json"),
    ):
        ingest_main()

    data = json.loads((tmp_path / "out.json").read_text())
    assert data == []
