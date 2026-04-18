"""Open Food Facts API client.

Looks up products by barcode and returns a normalized record with
ingredients extracted from the OFF payload. Returns None on 404 or
when the product has no usable ingredient list.

Docs: https://wiki.openfoodfacts.org/API
"""

import logging
from typing import TypedDict

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class OFFProduct(TypedDict):
    barcode: str
    name: str | None
    brand: str | None
    image_url: str | None
    ingredients: list[str]


def _parse_ingredients(ingredients_text: str | None) -> list[str]:
    """Convert OFF's comma/semicolon-delimited ingredient string to a list.

    OFF often nests parenthetical qualifiers; for MVP we strip them to keep
    the downstream entity resolution focused on canonical names.
    """
    if not ingredients_text:
        return []

    raw = ingredients_text.replace(";", ",")
    depth = 0
    buf: list[str] = []
    parts: list[str] = []
    for char in raw:
        if char == "(":
            depth += 1
            continue
        if char == ")":
            depth = max(0, depth - 1)
            continue
        if depth > 0:
            continue  # drop parenthetical qualifiers
        if char == ",":
            parts.append("".join(buf).strip())
            buf.clear()
            continue
        buf.append(char)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)

    return [p for p in parts if p and len(p) > 1 and p != "*"]


async def fetch_product(barcode: str, settings: Settings) -> OFFProduct | None:
    """Fetch a single product by barcode from Open Food Facts.

    Returns None when the product is not found, has no ingredient data,
    or OFF is unreachable (graceful degradation so the agent can fall
    back to photo OCR).
    """
    url = f"{settings.off_base_url}/product/{barcode}"
    timeout = httpx.Timeout(settings.off_timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(
                url,
                params={"fields": "product_name,brands,ingredients_text,image_url"},
            )
            if response.status_code >= 500:
                response = await client.get(url)  # single retry on server error
            if response.status_code == 404:
                return None
            response.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.warning("OFF lookup failed for %s: %s", barcode, exc)
            return None

    payload = response.json()
    if payload.get("status") != 1:  # OFF: status=1 found, 0 not found
        return None

    product = payload.get("product") or {}
    ingredients = _parse_ingredients(product.get("ingredients_text"))
    if not ingredients:
        return None

    return OFFProduct(
        barcode=barcode,
        name=product.get("product_name") or None,
        brand=product.get("brands") or None,
        image_url=product.get("image_url") or None,
        ingredients=ingredients,
    )
