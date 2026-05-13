"""Ingest products from Open Food Facts Search API v2 — Mexico market.

Queries by country (en:mexico) + health categories. Extracts products
with valid barcode and ingredients. Outputs scripts/data/off_products.json.

Usage:
    cd backend && python -m scripts.ingest_off_mexico
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
OUTPUT_PATH = Path(__file__).parent / "data" / "off_products.json"

HEALTH_CATEGORIES = [
    "en:yogurts",
    "en:fermented-milks",
    "en:plant-based-foods",
    "en:breakfast-cereals",
    "en:whole-grain-foods",
    "en:nuts",
    "en:dried-fruits",
    "en:legumes",
    "en:plant-based-beverages",
    "en:waters",
    "en:fruit-juices",
    "en:herbal-teas",
    "en:organic-foods",
    "en:baby-foods",
    "en:dietary-supplements",
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
_MAX_PAGES = 5  # up to 500 products per category
_HEADERS = {"User-Agent": "BioShieldAI/1.0 (isc.albertofragoso@gmail.com)"}


def _fetch_page(category: str, page: int) -> dict:
    resp = requests.get(
        OFF_SEARCH_URL,
        params={
            "countries_tags": "en:mexico",
            "categories_tags": category,
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
    """Convert ingredients_tags like ['en:wheat-flour', ...] to readable text."""
    names = []
    for tag in tags or []:
        # Strip language prefix (e.g. 'en:', 'es:')
        if ":" in tag:
            tag = tag.split(":", 1)[1]
        # Replace hyphens with spaces and title-case
        names.append(tag.replace("-", " "))
    return ", ".join(names)


def _map_product(hit: dict, category: str) -> dict | None:
    barcode = (hit.get("code") or "").strip()
    name = (hit.get("product_name_es") or hit.get("product_name") or "").strip()

    if not barcode or not name:
        return None

    # Prefer free-text ingredients; fall back to structured tags
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
        "ingredients_source": "off_dump_mx",
    }


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    products: list[dict] = []
    seen: set[str] = set()
    stats: dict[str, int] = {
        "fetched": 0,
        "accepted": 0,
        "skipped_no_barcode": 0,
        "skipped_no_name": 0,
        "skipped_no_ingredients": 0,
        "skipped_duplicate": 0,
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

                if product["barcode"] in seen:
                    stats["skipped_duplicate"] += 1
                    continue

                seen.add(product["barcode"])
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
