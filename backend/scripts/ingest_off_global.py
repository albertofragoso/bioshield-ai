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
    # Sin countries_tags — diferencia clave respecto al script de México
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
    """Convierte ingredients_tags como ['en:wheat-flour', ...] a texto legible."""
    names = []
    for tag in tags or []:
        # Eliminar prefijo de idioma (ej. 'en:', 'es:')
        if ":" in tag:
            tag = tag.split(":", 1)[1]
        names.append(tag.replace("-", " "))
    return ", ".join(names)


def _map_product(hit: dict, category: str) -> dict | None:
    barcode = (hit.get("code") or "").strip()
    name = (hit.get("product_name_es") or hit.get("product_name") or "").strip()

    if not barcode or not name:
        return None

    # Preferir texto libre de ingredientes; fallback a tags estructurados
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
                    # Reemplazar con categoría más reciente (más específica por orden de lista)
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
