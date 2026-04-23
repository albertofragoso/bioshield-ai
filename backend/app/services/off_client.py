"""Open Food Facts API client.

Looks up products by barcode (read) y contribuye datos de vuelta a OFF (write).
La escritura requiere opt-in explícito del usuario y se ejecuta via BackgroundTask.

Docs: https://wiki.openfoodfacts.org/API
"""

import base64
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


class OFFContributionResult(TypedDict):
    success: bool
    off_url: str | None
    error: str | None


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


# ─────────────────────────────────────────────
# Flujo contributivo (write path, Fase 2)
# ─────────────────────────────────────────────

async def contribute_product(
    barcode: str,
    ingredients_text: str,
    settings: Settings,
) -> OFFContributionResult:
    """Envía ingredientes de un producto a Open Food Facts via POST form-urlencoded.

    Retorna inmediatamente si off_contrib_enabled=False (feature flag).
    No reintenta — el retry lo maneja el FE via re-POST al endpoint.
    """
    if not settings.off_contrib_enabled:
        return OFFContributionResult(success=False, off_url=None, error="Feature flag disabled")

    url = f"{settings.off_write_base_url}/product_jqm2.pl"
    user_agent = f"{settings.off_app_name}/{settings.off_app_version}"
    timeout = httpx.Timeout(settings.off_contrib_timeout_seconds)

    data = {
        "code": barcode,
        "user_id": settings.off_contributor_user,
        "password": settings.off_contributor_password,
        "ingredients_text_es": ingredients_text,
        "comment": f"Added via {settings.off_app_name}",
        "lang": "es",
    }

    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": user_agent}) as client:
        try:
            response = await client.post(url, data=data)
            response.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.warning("OFF contribute failed for %s: %s", barcode, exc)
            return OFFContributionResult(success=False, off_url=None, error=str(exc))

    off_url = f"https://world.openfoodfacts.org/product/{barcode}"
    return OFFContributionResult(success=True, off_url=off_url, error=None)


async def upload_product_image(
    barcode: str,
    image_b64: str,
    settings: Settings,
) -> bool:
    """Sube la imagen de ingredientes de un producto a Open Food Facts.

    Retorna True si el upload fue exitoso. Falla silenciosamente — la
    contribución de texto ya es valiosa aunque la imagen falle.
    """
    if not settings.off_contrib_enabled:
        return False

    url = f"{settings.off_write_base_url}/product_image_upload.pl"
    user_agent = f"{settings.off_app_name}/{settings.off_app_version}"
    timeout = httpx.Timeout(settings.off_contrib_timeout_seconds)

    try:
        image_bytes = base64.b64decode(image_b64)
    except Exception as exc:
        logger.warning("OFF image upload skipped — invalid base64 for %s: %s", barcode, exc)
        return False

    files = {"imgupload_ingredients_es": ("label.jpg", image_bytes, "image/jpeg")}
    data = {
        "code": barcode,
        "user_id": settings.off_contributor_user,
        "password": settings.off_contributor_password,
        "imagefield": "ingredients_es",
    }

    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": user_agent}) as client:
        try:
            response = await client.post(url, data=data, files=files)
            response.raise_for_status()
            return True
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.warning("OFF image upload failed for %s: %s", barcode, exc)
            return False
