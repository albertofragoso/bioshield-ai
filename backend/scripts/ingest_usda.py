"""Ingest products from USDA FoodData Central Branded Foods API.

Queries por categoría usando términos de búsqueda descriptivos.
Filtra solo productos de mercado US (datos de ingredientes más completos).
Outputs scripts/data/usda_products.json.

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
    # Lee la API key del entorno; DEMO_KEY funciona para pruebas con rate limit
    return os.environ.get("USDA_API_KEY", "DEMO_KEY")


def _fetch_page(query: str, page: int) -> dict:
    # POST requerido por la API de búsqueda de USDA FDC
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
    # Descarta si no tiene código de barras
    gtin = (food.get("gtinUpc") or "").strip()
    if not gtin:
        return None

    # Descarta si no tiene nombre de producto
    description = (food.get("description") or "").strip()
    if not description:
        return None

    # Solo filtrar si el campo existe y tiene un valor explícito no-US
    market = (food.get("marketCountry") or "").strip()
    if market and market != "United States":
        return None

    # Descarta si no hay lista de ingredientes
    ingredients_raw = (food.get("ingredients") or "").strip()
    if not ingredients_raw:
        return None

    # El parser devuelve [] si el texto no contiene ingredientes válidos
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

                # Deduplicar por GTIN/barcode entre categorías
                if product["barcode"] in seen:
                    stats["duplicate"] += 1
                    continue

                seen.add(product["barcode"])
                products.append(product)
                stats["accepted"] += 1

            total_hits = data.get("totalHits") or 0
            # Parar si ya cubrimos todos los hits o alcanzamos el límite de páginas
            if page * _PAGE_SIZE >= total_hits or page >= _MAX_PAGES:
                break
            page += 1
            # Respetar el rate limit de DEMO_KEY (~3 req/s)
            time.sleep(0.2)

    OUTPUT_PATH.write_text(json.dumps(products, ensure_ascii=False, indent=2))
    logger.info("Stats: %s", stats)
    logger.info("Output: %s (%d products)", OUTPUT_PATH, len(products))


if __name__ == "__main__":
    main()
