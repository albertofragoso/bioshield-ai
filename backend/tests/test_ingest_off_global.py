"""Tests for the OFF Global ingestion script.

HTTP calls are mocked — no network required.
"""

import json
from unittest.mock import patch


def _make_hit(
    code="9876543210987",
    name="Organic Oatmeal",
    name_es="Avena Orgánica",
    brands="Quaker,Other",
    categories="en:breakfast-cereals,en:organic-foods",
    ingredients="Avena integral, Sal",
    image="https://img.off.org/oatmeal.jpg",
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
    from scripts.ingest_off_global import _map_product

    result = _map_product(_make_hit(), "en:breakfast-cereals")
    assert result is not None
    assert result["barcode"] == "9876543210987"
    assert result["name"] == "Avena Orgánica"
    assert result["brand"] == "Quaker"
    assert result["category"] == "breakfast-cereals"
    assert "Avena integral" in result["ingredients_json"]
    assert result["ingredients_source"] == "off_global"
    assert result["image_url"] == "https://img.off.org/oatmeal.jpg"


def test_map_product_returns_none_without_barcode():
    from scripts.ingest_off_global import _map_product

    assert _map_product(_make_hit(code=""), "en:snacks") is None


def test_map_product_returns_none_without_name():
    from scripts.ingest_off_global import _map_product

    assert _map_product(_make_hit(name="", name_es=None), "en:snacks") is None


def test_map_product_returns_none_without_ingredients():
    from scripts.ingest_off_global import _map_product

    assert _map_product(_make_hit(ingredients=""), "en:snacks") is None


def test_map_product_prefers_spanish_name():
    from scripts.ingest_off_global import _map_product

    hit = _make_hit(name="Organic Oatmeal", name_es="Avena Orgánica")
    result = _map_product(hit, "en:cereals")
    assert result["name"] == "Avena Orgánica"


def test_fetch_page_excludes_countries_tags():
    """Verifica que el request NO incluye countries_tags (diferencia clave vs MX)."""
    import requests

    from scripts.ingest_off_global import _fetch_page

    with patch.object(requests, "get") as mock_get:
        mock_get.return_value.json.return_value = {"hits": [], "count": 0}
        mock_get.return_value.raise_for_status = lambda: None
        _fetch_page("en:snacks", 1)

    call_kwargs = mock_get.call_args
    # params es ahora una lista de tuplas
    params = call_kwargs[1].get("params") or call_kwargs[0][1]
    param_keys = [k for k, v in params] if isinstance(params, list) else list(params.keys())
    assert "countries_tags" not in param_keys
    assert "labels_tags" in param_keys


def test_map_product_falls_back_to_ingredients_tags():
    """Cuando ingredients_text está vacío, debe usar ingredients_tags como fallback."""
    from scripts.ingest_off_global import _map_product

    hit = _make_hit(ingredients="")
    hit["ingredients_tags"] = ["en:whole-grain-oats", "en:salt"]
    result = _map_product(hit, "en:cereals")
    assert result is not None
    # El parser debe producir algo basado en los tags
    assert len(result["ingredients_json"]) >= 1


def test_main_writes_json_and_deduplicates(tmp_path):
    from scripts.ingest_off_global import main as ingest_main

    hit = _make_hit()
    mock_page = {"hits": [hit], "count": 1}
    empty_page = {"hits": [], "count": 1}

    def fake_fetch(category, page):
        return mock_page if page == 1 else empty_page

    with (
        patch("scripts.ingest_off_global._fetch_page", side_effect=fake_fetch),
        patch("scripts.ingest_off_global.OUTPUT_PATH", tmp_path / "out.json"),
    ):
        ingest_main()

    data = json.loads((tmp_path / "out.json").read_text())
    barcodes = [p["barcode"] for p in data]
    assert barcodes.count("9876543210987") == 1


def test_main_skips_http_errors(tmp_path):
    import requests

    from scripts.ingest_off_global import main as ingest_main

    def fake_fetch(category, page):
        raise requests.RequestException("timeout")

    with (
        patch("scripts.ingest_off_global._fetch_page", side_effect=fake_fetch),
        patch("scripts.ingest_off_global.OUTPUT_PATH", tmp_path / "out.json"),
    ):
        ingest_main()

    data = json.loads((tmp_path / "out.json").read_text())
    assert data == []
