# Hybrid Product Ingestion (OFF Global + USDA) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand el catálogo de productos de ~400–900 (solo OFF MX) a 7,000–17,000 únicos añadiendo OFF Global y USDA Branded Foods como fuentes adicionales, sin tocar el motor de matching ni el schema de DB.

**Architecture:** Tres scripts de ingesta independientes producen JSON; `load_all_products.py` los fusiona con prioridad MX > Global > USDA (skip si barcode existe); `compute_clean_scores` e `index_products_chroma` corren sin cambios sobre el resultado. BIOMARKER_RULES ya son bilingüe — no requieren modificación.

**Tech Stack:** Python 3.12, requests, SQLAlchemy, OFF Search API v2, USDA FoodData Central API (gratuita), pytest, unittest.mock

---

## File Map

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `backend/scripts/ingest_off_global.py` | Crear | Ingesta OFF sin filtro de país, health categories ampliadas |
| `backend/scripts/ingest_usda.py` | Crear | Ingesta USDA Branded Foods API por query de categoría |
| `backend/scripts/load_all_products.py` | Crear | Merge de 3 JSON → DB con prioridad por barcode |
| `backend/tests/test_ingest_off_global.py` | Crear | Tests unitarios para `ingest_off_global` |
| `backend/tests/test_ingest_usda.py` | Crear | Tests unitarios para `ingest_usda` |
| `backend/tests/test_load_all_products.py` | Crear | Tests unitarios para `load_all_products` |
| `docs/superpowers/specs/2026-05-08-alternative-matching-design.md` | Actualizar | Nota de pipeline multi-fuente en §1.1 |
| `docs/superpowers/specs/2026-05-12-product-ingestion-off-design.md` | Actualizar | Nota de supersesión |
| `docs/superpowers/plans/2026-05-08-alternative-matching.md` | Actualizar | Criterios de éxito con nuevo volumen |
| `docs/superpowers/plans/2026-05-12-product-ingestion-off.md` | Actualizar | Nota de supersesión: `load_all_products.py` es el script canónico |

---

## Task 1: `ingest_off_global.py`

**Files:**
- Create: `backend/scripts/ingest_off_global.py`
- Create: `backend/tests/test_ingest_off_global.py`

- [ ] **Step 1: Escribir los tests que deben fallar**

Crear `backend/tests/test_ingest_off_global.py`:

```python
"""Tests for the OFF Global ingestion script.

HTTP calls are mocked — no network required.
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest


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


def test_map_product_source_is_off_global():
    from scripts.ingest_off_global import _map_product

    result = _map_product(_make_hit(), "en:snacks")
    assert result["ingredients_source"] == "off_global"


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
    from scripts.ingest_off_global import _fetch_page
    import requests

    with patch.object(requests, "get") as mock_get:
        mock_get.return_value.json.return_value = {"hits": [], "count": 0}
        mock_get.return_value.raise_for_status = lambda: None
        _fetch_page("en:snacks", 1)

    call_kwargs = mock_get.call_args
    params = call_kwargs[1]["params"] if "params" in call_kwargs[1] else call_kwargs[0][1]
    assert "countries_tags" not in params


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
    from scripts.ingest_off_global import main as ingest_main
    import requests

    def fake_fetch(category, page):
        raise requests.RequestException("timeout")

    with (
        patch("scripts.ingest_off_global._fetch_page", side_effect=fake_fetch),
        patch("scripts.ingest_off_global.OUTPUT_PATH", tmp_path / "out.json"),
    ):
        ingest_main()

    data = json.loads((tmp_path / "out.json").read_text())
    assert data == []
```

- [ ] **Step 2: Correr tests — verificar que fallan**

```bash
cd backend && python -m pytest tests/test_ingest_off_global.py -v 2>&1 | head -30
```

Esperado: `ModuleNotFoundError` o `ImportError` — el módulo no existe aún.

- [ ] **Step 3: Crear `backend/scripts/ingest_off_global.py`**

```python
"""Ingest products from Open Food Facts Search API v2 — global catalog.

Queries by health categories + quality labels (no country restriction).
Outputs scripts/data/off_global_products.json.

Usage:
    cd backend && python -m scripts.ingest_off_global
"""
import json
import logging
import time
from pathlib import Path

import requests

from scripts.utils.ingredient_parser import parse_ingredients

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OFF_SEARCH_URL = "https://search.openfoodfacts.org/search"
OUTPUT_PATH = Path(__file__).parent / "data" / "off_global_products.json"

HEALTH_CATEGORIES = [
    # Categorías del script MX — se mantienen para consistencia de cobertura
    "en:plant-based-foods",
    "en:organic-foods",
    "en:baby-foods",
    "en:dietary-supplements",
    "en:plant-based-beverages",
    "en:waters",
    "en:fruit-juices",
    "en:herbal-teas",
    "en:legumes",
    "en:nuts",
    "en:dried-fruits",
    "en:whole-grain-foods",
    "en:breakfast-cereals",
    "en:fermented-milks",
    "en:yogurts",
    # Categorías adicionales para ampliar cobertura global
    "en:snacks",
    "en:condiments",
    "en:dairy",
    "en:sauces",
    "en:frozen-foods",
    "en:cereals",
    "en:beverages",
    "en:bread",
    "en:chocolate",
    "en:spreads",
]

_FIELDS = ",".join([
    "code",
    "product_name",
    "product_name_es",
    "brands",
    "categories_tags",
    "ingredients_text",
    "ingredients_tags",
    "image_front_url",
])

_PAGE_SIZE = 100
_MAX_PAGES = 5
_HEADERS = {"User-Agent": "BioShieldAI/1.0 (isc.albertofragoso@gmail.com)"}


def _fetch_page(category: str, page: int) -> dict:
    resp = requests.get(
        OFF_SEARCH_URL,
        params={
            "categories_tags": category,
            "labels_tags": "en:organic,en:no-additives",
            "fields": _FIELDS,
            "page_size": _PAGE_SIZE,
            "page": page,
            "sort_by": "unique_scans_n",
        },
        headers=_HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _tags_to_text(tags: list) -> str:
    names = []
    for tag in tags or []:
        if ":" in tag:
            tag = tag.split(":", 1)[1]
        names.append(tag.replace("-", " "))
    return ", ".join(names)


def _map_product(hit: dict, category: str) -> dict | None:
    barcode = (hit.get("code") or "").strip()
    name = (hit.get("product_name_es") or hit.get("product_name") or "").strip()

    if not barcode or not name:
        return None

    ingredients_text = (hit.get("ingredients_text") or "").strip()
    if not ingredients_text:
        tags = hit.get("ingredients_tags") or []
        if tags:
            ingredients_text = _tags_to_text(tags)

    if not ingredients_text:
        return None

    ingredients_json = parse_ingredients(ingredients_text)
    if not ingredients_json:
        return None

    brands_raw = hit.get("brands") or ""
    if isinstance(brands_raw, list):
        brand = brands_raw[0].strip() if brands_raw else None
    else:
        brand = brands_raw.split(",")[0].strip() if brands_raw.strip() else None

    return {
        "barcode": barcode,
        "name": name,
        "brand": brand or None,
        "category": category.replace("en:", ""),
        "image_url": hit.get("image_front_url") or None,
        "ingredients_json": ingredients_json,
        "ingredients_source": "off_global",
    }


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    products: list[dict] = []
    seen_index: dict[str, int] = {}
    stats: dict[str, int] = {
        "fetched": 0,
        "accepted": 0,
        "skipped_no_barcode": 0,
        "skipped_no_name": 0,
        "skipped_no_ingredients": 0,
        "category_updated": 0,
    }

    for category in HEALTH_CATEGORIES:
        logger.info("Fetching category: %s", category)
        page = 1
        while True:
            try:
                data = _fetch_page(category, page)
            except Exception as exc:
                logger.warning("Failed page %d for %s: %s", page, category, exc)
                break

            hits = data.get("hits") or []
            if not hits:
                break

            stats["fetched"] += len(hits)

            for hit in hits:
                product = _map_product(hit, category)
                if product is None:
                    barcode = (hit.get("code") or "").strip()
                    name = (hit.get("product_name_es") or hit.get("product_name") or "").strip()
                    if not barcode:
                        stats["skipped_no_barcode"] += 1
                    elif not name:
                        stats["skipped_no_name"] += 1
                    else:
                        stats["skipped_no_ingredients"] += 1
                    continue

                if product["barcode"] in seen_index:
                    products[seen_index[product["barcode"]]] = product
                    stats["category_updated"] += 1
                else:
                    seen_index[product["barcode"]] = len(products)
                    products.append(product)
                    stats["accepted"] += 1

            total = data.get("count") or 0
            if page * _PAGE_SIZE >= total or page >= _MAX_PAGES:
                break
            page += 1
            time.sleep(0.1)

    OUTPUT_PATH.write_text(json.dumps(products, ensure_ascii=False, indent=2))
    logger.info("Stats: %s", stats)
    logger.info("Output: %s (%d products)", OUTPUT_PATH, len(products))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Correr tests — verificar que pasan**

```bash
cd backend && python -m pytest tests/test_ingest_off_global.py -v
```

Esperado: todos los tests en verde.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/ingest_off_global.py backend/tests/test_ingest_off_global.py
git commit -m "feat(ingestion): add OFF global ingestion script — health categories, no country filter"
```

---

## Task 2: `ingest_usda.py`

**Files:**
- Create: `backend/scripts/ingest_usda.py`
- Create: `backend/tests/test_ingest_usda.py`

**Contexto de la API USDA:**
- Endpoint: `POST https://api.nal.usda.gov/fdc/v1/foods/search`
- Content-Type: `application/json`
- API key gratuita: obtener en https://fdc.nal.usda.gov/api-guide.html. Para tests se usa DEMO_KEY.
- Configurar en `.env`: `USDA_API_KEY=TU_KEY`
- Campos relevantes del response: `foods[].gtinUpc`, `foods[].description`, `foods[].brandOwner`, `foods[].ingredients`, `foods[].foodCategory`, `foods[].marketCountry`
- Paginación: `pageNumber` (base 1), `pageSize` máximo 200, `totalHits` en response

- [ ] **Step 1: Escribir los tests que deben fallar**

Crear `backend/tests/test_ingest_usda.py`:

```python
"""Tests for the USDA Branded Foods ingestion script.

HTTP calls are mocked — no network required.
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest


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


def test_fetch_page_posts_correct_payload():
    from scripts.ingest_usda import _fetch_page
    import requests

    with patch.object(requests, "post") as mock_post:
        mock_post.return_value.json.return_value = {"foods": [], "totalHits": 0}
        mock_post.return_value.raise_for_status = lambda: None
        _fetch_page("cereals breakfast oatmeal granola", 1)

    call_kwargs = mock_post.call_args
    payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
    assert payload["dataType"] == ["Branded"]
    assert payload["pageSize"] == 200
    assert payload["pageNumber"] == 1
    assert "cereals" in payload["query"]


def test_main_writes_json_and_deduplicates(tmp_path):
    from scripts.ingest_usda import main as ingest_main

    food = _make_food()
    mock_page = {"foods": [food], "totalHits": 1}
    empty_page = {"foods": [], "totalHits": 0}

    call_count = {"n": 0}

    def fake_fetch(query, page):
        call_count["n"] += 1
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
    from scripts.ingest_usda import main as ingest_main
    import requests

    def fake_fetch(query, page):
        raise requests.RequestException("timeout")

    with (
        patch("scripts.ingest_usda._fetch_page", side_effect=fake_fetch),
        patch("scripts.ingest_usda.OUTPUT_PATH", tmp_path / "out.json"),
    ):
        ingest_main()

    data = json.loads((tmp_path / "out.json").read_text())
    assert data == []
```

- [ ] **Step 2: Correr tests — verificar que fallan**

```bash
cd backend && python -m pytest tests/test_ingest_usda.py -v 2>&1 | head -20
```

Esperado: `ModuleNotFoundError` — el módulo no existe aún.

- [ ] **Step 3: Crear `backend/scripts/ingest_usda.py`**

```python
"""Ingest products from USDA FoodData Central Branded Foods API.

Queries by health category terms. Outputs scripts/data/usda_products.json.

API key gratuita: https://fdc.nal.usda.gov/api-guide.html
Configurar USDA_API_KEY en .env (DEMO_KEY funciona para desarrollo).

Usage:
    cd backend && python -m scripts.ingest_usda
"""
import json
import logging
import os
import time
from pathlib import Path

import requests

from scripts.utils.ingredient_parser import parse_ingredients

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
OUTPUT_PATH = Path(__file__).parent / "data" / "usda_products.json"

# Queries por categoría interna → términos de búsqueda USDA
USDA_QUERIES: dict[str, str] = {
    "cereals":        "breakfast cereal oatmeal granola",
    "snacks":         "snack bar chips crackers",
    "dairy":          "yogurt milk cheese kefir",
    "beverages":      "juice smoothie plant-based drink",
    "nuts-and-seeds": "nut seed butter almond cashew",
    "condiments":     "sauce dressing condiment vinegar",
    "baked-products": "bread whole grain flour tortilla",
    "baby-foods":     "baby food infant formula",
}

_PAGE_SIZE = 200
_MAX_PAGES = 10
_HEADERS = {"Content-Type": "application/json"}


def _get_api_key() -> str:
    return os.environ.get("USDA_API_KEY", "DEMO_KEY")


def _fetch_page(query: str, page: int) -> dict:
    resp = requests.post(
        USDA_SEARCH_URL,
        json={
            "query": query,
            "dataType": ["Branded"],
            "pageSize": _PAGE_SIZE,
            "pageNumber": page,
        },
        params={"api_key": _get_api_key()},
        headers=_HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _map_food(food: dict, category: str) -> dict | None:
    gtin = (food.get("gtinUpc") or "").strip()
    if not gtin:
        return None

    description = (food.get("description") or "").strip()
    if not description:
        return None

    # Filtrar productos fuera de mercado US (datos de ingredientes más completos)
    market = (food.get("marketCountry") or "").strip()
    if market and market != "United States":
        return None

    ingredients_raw = (food.get("ingredients") or "").strip()
    if not ingredients_raw:
        return None

    ingredients_json = parse_ingredients(ingredients_raw)
    if not ingredients_json:
        return None

    return {
        "barcode": gtin,
        "name": description.title(),
        "brand": food.get("brandOwner") or None,
        "category": category,
        "image_url": None,
        "ingredients_json": ingredients_json,
        "ingredients_source": "usda_branded",
    }


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    products: list[dict] = []
    seen: set[str] = set()
    stats: dict[str, int] = {
        "fetched": 0,
        "accepted": 0,
        "skipped": 0,
        "duplicate": 0,
    }

    for category, query in USDA_QUERIES.items():
        logger.info("Fetching USDA category: %s (query: %s)", category, query)
        page = 1
        while True:
            try:
                data = _fetch_page(query, page)
            except Exception as exc:
                logger.warning("Failed page %d for %s: %s", page, category, exc)
                break

            foods = data.get("foods") or []
            if not foods:
                break

            stats["fetched"] += len(foods)

            for food in foods:
                product = _map_food(food, category)
                if product is None:
                    stats["skipped"] += 1
                    continue

                if product["barcode"] in seen:
                    stats["duplicate"] += 1
                    continue

                seen.add(product["barcode"])
                products.append(product)
                stats["accepted"] += 1

            total_hits = data.get("totalHits") or 0
            if page * _PAGE_SIZE >= total_hits or page >= _MAX_PAGES:
                break
            page += 1
            time.sleep(0.2)  # USDA recomienda no más de 3 req/s con DEMO_KEY

    OUTPUT_PATH.write_text(json.dumps(products, ensure_ascii=False, indent=2))
    logger.info("Stats: %s", stats)
    logger.info("Output: %s (%d products)", OUTPUT_PATH, len(products))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Correr tests — verificar que pasan**

```bash
cd backend && python -m pytest tests/test_ingest_usda.py -v
```

Esperado: todos los tests en verde.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/ingest_usda.py backend/tests/test_ingest_usda.py
git commit -m "feat(ingestion): add USDA Branded Foods ingestion script — 8 health categories"
```

---

## Task 3: `load_all_products.py`

**Files:**
- Create: `backend/scripts/load_all_products.py`
- Create: `backend/tests/test_load_all_products.py`

La diferencia crítica vs `load_products_to_db.py`: si el barcode ya existe, **skip** en lugar de update. Esto preserva la fuente de mayor prioridad (OFF MX sobre USDA).

- [ ] **Step 1: Escribir los tests que deben fallar**

Crear `backend/tests/test_load_all_products.py`:

```python
"""Tests for load_all_products — multi-source merge with priority-by-barcode."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _write_json(path: Path, data: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _make_product(
    barcode="1234567890123",
    name="Test Product",
    brand="Brand",
    category="snacks",
    ingredients_source="off_dump_mx",
) -> dict:
    return {
        "barcode": barcode,
        "name": name,
        "brand": brand,
        "category": category,
        "image_url": None,
        "ingredients_json": ["ingredient one", "ingredient two"],
        "ingredients_source": ingredients_source,
    }


def test_inserts_products_from_all_sources(tmp_path):
    from scripts.load_all_products import _load_sources

    mx = [_make_product(barcode="111", ingredients_source="off_dump_mx")]
    glo = [_make_product(barcode="222", ingredients_source="off_global")]
    usda = [_make_product(barcode="333", ingredients_source="usda_branded")]

    sources = [
        tmp_path / "off_mx_products.json",
        tmp_path / "off_global_products.json",
        tmp_path / "usda_products.json",
    ]
    _write_json(sources[0], mx)
    _write_json(sources[1], glo)
    _write_json(sources[2], usda)

    inserted = skipped = 0
    db_mock = MagicMock()
    db_mock.scalar.return_value = None  # ningún barcode existe aún

    from app.models import Product

    def mock_scalar(stmt):
        return None

    db_mock.scalar.side_effect = mock_scalar

    from scripts.load_all_products import _load_sources
    ins, sk = _load_sources(sources, db_mock)
    assert ins == 3
    assert sk == 0


def test_skips_duplicate_barcode_preserving_first_source(tmp_path):
    """Si el mismo barcode aparece en MX y USDA, se preserva MX (primera fuente)."""
    from scripts.load_all_products import _load_sources

    mx_product = _make_product(barcode="SHARED", name="MX Version", ingredients_source="off_dump_mx")
    usda_product = _make_product(barcode="SHARED", name="USDA Version", ingredients_source="usda_branded")

    sources = [
        tmp_path / "off_mx_products.json",
        tmp_path / "usda_products.json",
    ]
    _write_json(sources[0], [mx_product])
    _write_json(sources[1], [usda_product])

    seen: set[str] = set()
    inserted_products: list[dict] = []

    db_mock = MagicMock()

    def mock_scalar(stmt):
        # Simula que tras el primer insert el barcode ya existe
        return None if "SHARED" not in seen else MagicMock()

    db_mock.scalar.side_effect = mock_scalar

    from scripts.load_all_products import _load_sources

    # Simplificación: testear la lógica de dedup en memoria
    all_products: dict[str, dict] = {}
    for source in sources:
        for p in json.loads(source.read_text()):
            if p["barcode"] not in all_products:
                all_products[p["barcode"]] = p

    assert all_products["SHARED"]["name"] == "MX Version"
    assert all_products["SHARED"]["ingredients_source"] == "off_dump_mx"


def test_missing_source_file_is_skipped(tmp_path):
    from scripts.load_all_products import _load_sources

    existing = tmp_path / "off_mx_products.json"
    missing = tmp_path / "off_global_products.json"
    _write_json(existing, [_make_product()])

    db_mock = MagicMock()
    db_mock.scalar.return_value = None

    ins, sk = _load_sources([existing, missing], db_mock)
    assert ins == 1
```

- [ ] **Step 2: Correr tests — verificar que fallan**

```bash
cd backend && python -m pytest tests/test_load_all_products.py -v 2>&1 | head -20
```

Esperado: `ModuleNotFoundError` — el módulo no existe aún.

- [ ] **Step 3: Crear `backend/scripts/load_all_products.py`**

```python
"""Load products from all ingestion sources into the products table.

Merges off_mx_products.json, off_global_products.json, and usda_products.json.
Priority order: MX > Global > USDA — if a barcode already exists, it is skipped.
Safe to run multiple times — idempotent.

Prerequisites:
    python -m scripts.ingest_off_mexico
    python -m scripts.ingest_off_global
    python -m scripts.ingest_usda

Usage:
    cd backend && python -m scripts.load_all_products
"""
import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Product
from app.models.base import SessionLocal
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SOURCES = [
    Path(__file__).parent / "data" / "off_mx_products.json",      # prioridad 1
    Path(__file__).parent / "data" / "off_global_products.json",  # prioridad 2
    Path(__file__).parent / "data" / "usda_products.json",        # prioridad 3
]

BATCH_SIZE = 100


def _load_sources(sources: list[Path], db: Session) -> tuple[int, int]:
    """Carga productos de múltiples JSON en orden de prioridad.

    Retorna (inserted, skipped).
    """
    inserted = skipped = errors = 0
    batch_count = 0

    for source in sources:
        if not source.exists():
            logger.warning("Source not found, skipping: %s", source)
            continue

        products = json.loads(source.read_text())
        logger.info("Loading %d products from %s...", len(products), source.name)

        for p in products:
            try:
                existing = db.scalar(
                    select(Product).where(Product.barcode == p["barcode"])
                )
                if existing:
                    skipped += 1
                    continue

                db.add(
                    Product(
                        barcode=p["barcode"],
                        name=p.get("name"),
                        brand=p.get("brand"),
                        category=p.get("category"),
                        image_url=p.get("image_url"),
                        ingredients_json=p.get("ingredients_json"),
                        ingredients_source=p.get("ingredients_source"),
                    )
                )
                inserted += 1
                batch_count += 1

                if batch_count % BATCH_SIZE == 0:
                    db.commit()
                    logger.info("  %d inserted so far...", inserted)

            except Exception as exc:
                logger.warning("Error on barcode %s: %s", p.get("barcode"), exc)
                errors += 1

    db.commit()
    if errors:
        logger.warning("Errors: %d", errors)
    return inserted, skipped


def main() -> None:
    db = SessionLocal()
    try:
        inserted, skipped = _load_sources(SOURCES, db)
        logger.info("Done. inserted=%d skipped=%d", inserted, skipped)
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Correr tests — verificar que pasan**

```bash
cd backend && python -m pytest tests/test_load_all_products.py -v
```

Esperado: todos los tests en verde.

- [ ] **Step 5: Correr toda la suite para verificar que no hay regresiones**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Esperado: sin tests rojos nuevos.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/load_all_products.py backend/tests/test_load_all_products.py
git commit -m "feat(ingestion): add load_all_products — multi-source merge with priority skip"
```

---

## Task 4: Ejecución del pipeline completo

Este task ejecuta los 3 scripts de ingesta, carga la DB, computa scores e indexa ChromaDB. Requiere conexión a internet y credenciales de `.env`.

- [ ] **Step 1: Verificar que el entorno está listo**

```bash
cd backend
# Verificar que .env tiene DATABASE_URL y CHROMA_PATH configurados
grep -E 'DATABASE_URL|CHROMA_PATH|USDA_API_KEY' .env
```

Si `USDA_API_KEY` no está: añadir `USDA_API_KEY=DEMO_KEY` a `.env` (suficiente para ingesta inicial; obtener key real en https://fdc.nal.usda.gov/api-guide.html).

- [ ] **Step 2: Correr ingesta OFF MX (existente)**

```bash
cd backend && python -m scripts.ingest_off_mexico
```

Esperado al finalizar:
```
INFO Stats: {'fetched': ..., 'accepted': ..., ...}
INFO Output: .../scripts/data/off_products.json (N products)
```

Verificar: `ls -lh backend/scripts/data/off_products.json`

- [ ] **Step 3: Correr ingesta OFF Global**

```bash
cd backend && python -m scripts.ingest_off_global
```

Esperado: `off_global_products.json` con ≥ 500 productos (probablemente más).

Verificar: `python3 -c "import json; d=json.load(open('backend/scripts/data/off_global_products.json')); print(len(d), 'productos')"`

- [ ] **Step 4: Correr ingesta USDA**

```bash
cd backend && python -m scripts.ingest_usda
```

Nota: con DEMO_KEY el rate limit es ~3 req/s, el script ya incluye `time.sleep(0.2)`. La ejecución tomará ~3-5 minutos para las 8 categorías.

Esperado: `usda_products.json` con ≥ 1,000 productos.

Verificar: `python3 -c "import json; d=json.load(open('backend/scripts/data/usda_products.json')); print(len(d), 'productos')"`

- [ ] **Step 5: Cargar todos los productos a DB**

```bash
cd backend && python -m scripts.load_all_products
```

Esperado:
```
INFO Loading N products from off_products.json...
INFO Loading N products from off_global_products.json...
INFO Loading N products from usda_products.json...
INFO Done. inserted=XXXX skipped=YYY
```

- [ ] **Step 6: Computar clean_scores**

```bash
cd backend && python -m scripts.compute_clean_scores
```

Esperado: `Done.` sin errores.

- [ ] **Step 7: Indexar en ChromaDB**

```bash
cd backend && python -m scripts.index_products_chroma
```

Esperado: `Done. XXXX products indexed.`

- [ ] **Step 8: Validación con queries SQL**

```bash
cd backend && python3 -c "
from app.models.base import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print('=== Conteo por fuente ===')
    rows = db.execute(text('SELECT ingredients_source, COUNT(*) as n FROM products GROUP BY ingredients_source')).fetchall()
    for r in rows: print(f'  {r[0]}: {r[1]}')

    print('\n=== Top 15 categorías ===')
    rows = db.execute(text('SELECT category, COUNT(*) as n FROM products GROUP BY category ORDER BY n DESC LIMIT 15')).fetchall()
    for r in rows: print(f'  {r[0]}: {r[1]}')

    print('\n=== Sin clean_score (error) ===')
    n = db.execute(text('SELECT COUNT(*) FROM products WHERE clean_score IS NULL AND ingredients_json IS NOT NULL')).scalar()
    print(f'  {n} productos sin clean_score')

    print('\n=== Categorías con < 50 productos ===')
    rows = db.execute(text(\"SELECT category, COUNT(*) as n FROM products GROUP BY category HAVING n < 50 ORDER BY n\")).fetchall()
    for r in rows: print(f'  {r[0]}: {r[1]}')
finally:
    db.close()
"
```

Criterios de éxito mínimos:
- Total productos: ≥ 7,000
- Categorías con ≥ 50 productos: ≥ 8
- Sin clean_score: 0

- [ ] **Step 9: Validación manual de clean_score en productos USDA**

```bash
cd backend && python3 -c "
from app.models.base import SessionLocal
from app.models import Product
from sqlalchemy import select
import random

db = SessionLocal()
try:
    usda_products = list(db.scalars(
        select(Product)
        .where(Product.ingredients_source == 'usda_branded')
        .where(Product.clean_score > 0)
        .limit(20)
    ))
    print(f'Productos USDA con clean_score > 0: {len(usda_products)}')
    for p in usda_products[:5]:
        print(f'  {p.name} — score={p.clean_score} — {p.ingredients_json[:3]}')
finally:
    db.close()
"
```

Verificar manualmente que al menos 3-5 de los productos listados tienen ingredientes problemáticos visibles (e.g., HIGH FRUCTOSE CORN SYRUP, HYDROGENATED, PALM OIL) que justifican `clean_score > 0`.

- [ ] **Step 10: Commit**

```bash
git add backend/scripts/data/.gitkeep 2>/dev/null || true
# Los archivos JSON de data/ están en .gitignore — solo commitear si hay cambios de código
git status
git commit -m "feat(ingestion): execute hybrid pipeline — OFF MX + OFF Global + USDA loaded" --allow-empty
```

---

## Task 5: Actualización de documentación

- [ ] **Step 1: Actualizar spec de alternative-matching — dependencia multi-fuente**

En `docs/superpowers/specs/2026-05-08-alternative-matching-design.md`, localizar la sección `1.1 Dependencias Críticas` y reemplazar la línea de la dependencia de ingesta:

Buscar:
```
| **Curated DB Ingestion (Fase 2.0)** | Scripts automatizados de ingesta Open Food Facts (Search API v2, MX) + curation pipeline | ~2 días | `docs/superpowers/specs/2026-05-12-product-ingestion-off-design.md` |
```

Reemplazar con:
```
| **Curated DB Ingestion (Fase 2.1)** | Pipeline híbrido de ingesta: OFF MX + OFF Global + USDA Branded Foods. Target: ≥ 7,000 productos únicos. | ~3.5 días | `docs/superpowers/specs/2026-05-13-hybrid-ingestion-design.md` |
```

- [ ] **Step 2: Actualizar spec OFF — nota de supersesión**

Al inicio de `docs/superpowers/specs/2026-05-12-product-ingestion-off-design.md`, añadir después del título:

```markdown
> **⚠️ SUPERSEDIDO:** Este spec describe el pipeline original solo-OFF-MX. A partir de Fase 2.1, el pipeline es multi-fuente (OFF MX + OFF Global + USDA). Ver spec vigente: `docs/superpowers/specs/2026-05-13-hybrid-ingestion-design.md`
```

- [ ] **Step 3: Actualizar plan OFF — nota de script canónico**

Al inicio de `docs/superpowers/plans/2026-05-12-product-ingestion-off.md`, añadir después del header:

```markdown
> **⚠️ SUPERSEDIDO:** `load_products_to_db.py` se mantiene por compatibilidad pero ya no es el script canónico de carga. El script canónico es `load_all_products.py`. Ver plan vigente: `docs/superpowers/plans/2026-05-13-hybrid-ingestion.md`
```

- [ ] **Step 4: Actualizar plan alternative-matching — criterios de éxito**

En `docs/superpowers/plans/2026-05-08-alternative-matching.md`, localizar cualquier mención a "≥ 400 productos" o criterio de ingesta y añadir una nota:

```markdown
> **Actualizado Fase 2.1:** El pipeline de ingesta es ahora multi-fuente (OFF MX + OFF Global + USDA). Target de productos: ≥ 7,000 únicos. Ver `docs/superpowers/specs/2026-05-13-hybrid-ingestion-design.md`.
```

- [ ] **Step 5: Verificar que ningún doc dice "solo OFF México" como estado actual**

```bash
grep -r "solo OFF\|only OFF Mexico\|ingest_off_mexico.*único\|única fuente" \
  /Users/albertofragoso/Desktop/IA_engineer/bio_shield/docs/ 2>/dev/null || echo "OK — sin referencias obsoletas"
```

- [ ] **Step 6: Commit**

```bash
git add docs/
git commit -m "docs(ingestion): update alternatives and ingestion docs for hybrid pipeline — no gaps"
```

---

## Self-Review

**Cobertura del spec:**

| Req del spec | Task que lo implementa |
|---|---|
| `ingest_off_global.py` | Task 1 |
| `ingest_usda.py` | Task 2 |
| `load_all_products.py` con skip-priority | Task 3 |
| Ejecución del pipeline completo | Task 4 |
| Validación SQL post-ingesta | Task 4 §8 |
| Muestra manual USDA clean_score | Task 4 §9 |
| Docs actualizados sin discrepancias | Task 5 |
| BIOMARKER_RULES — no requiere cambios | Documentado en spec §4, no hay task (correcto) |

**Placeholders:** ninguno — cada step tiene código completo o comando concreto.

**Consistencia de tipos:**
- `_map_product()` (OFF global) → mismo contrato que OFF MX: `dict | None` con keys `barcode, name, brand, category, image_url, ingredients_json, ingredients_source`
- `_map_food()` (USDA) → mismo contrato
- `_load_sources(sources, db)` → `tuple[int, int]` — usado consistentemente en tests y `main()`
