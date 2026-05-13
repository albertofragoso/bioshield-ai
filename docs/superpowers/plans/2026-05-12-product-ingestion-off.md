# Product Ingestion Pipeline (OFF) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **⚠️ WORKTREE REQUIRED:** Before starting ANY task, invoke `superpowers:using-git-worktrees` to create an isolated workspace for branch `feat/fase2-product-ingestion`. NEVER commit to `main`.

**Goal:** Ingest 400–900 health-conscious products from Open Food Facts (Mexico) into the BioShield DB, compute clean scores, and index in ChromaDB so the Alternative Matching feature has real data to work with.

**Architecture:** OFF Search API v2 queried by country+category → `ingredient_parser` converts raw text to `list[str]` → DB upsert → `compute_clean_scores` → `index_products_chroma`. A shared `build_product_profile` function in `rag.py` ensures consistent ChromaDB embeddings whether products are indexed via bulk script or post-scan enrichment.

**Tech Stack:** Python 3.11+, SQLAlchemy 2.0, ChromaDB, BGE-M3 embeddings, `requests`, pytest + in-memory SQLite

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/scripts/utils/__init__.py` | CREATE | Package init |
| `backend/scripts/utils/ingredient_parser.py` | CREATE | Parse raw ingredient string → `list[str]` |
| `backend/scripts/ingest_off_mexico.py` | CREATE | Fetch OFF Search API v2, output `off_products.json` |
| `backend/scripts/load_products_to_db.py` | CREATE | Upsert `off_products.json` → `products` table |
| `backend/app/services/rag.py` | MODIFY | Add `build_product_profile(product) -> str` |
| `backend/app/services/enrichment.py` | MODIFY | Replace local `_build_profile` with `build_product_profile` |
| `backend/scripts/index_products_chroma.py` | MODIFY | Replace local `_build_profile` with `build_product_profile` |
| `backend/tests/test_ingredient_parser.py` | CREATE | Tests for parser |
| `backend/tests/test_ingest_off_mexico.py` | CREATE | Tests for ingestion script (mocked HTTP) |
| `backend/tests/test_load_products_to_db.py` | CREATE | Tests for DB upsert (in-memory SQLite) |
| `backend/tests/test_rag.py` | MODIFY | Add tests for `build_product_profile` |
| `.gitignore` | MODIFY | Add `backend/scripts/data/` |

---

## Task 0: Worktree Setup

**Files:** none — git setup only

- [ ] **Step 1: Invoke using-git-worktrees skill**

In Claude Code, invoke:
```
superpowers:using-git-worktrees
```
When prompted, use branch name: `feat/fase2-product-ingestion`

The skill will create the worktree and drop you into the isolated directory. All subsequent work happens there — never on `main`.

- [ ] **Step 2: Verify you are on the right branch**

```bash
git branch --show-current
```
Expected output: `feat/fase2-product-ingestion`

---

## Task 1: Ingredient Parser

**Files:**
- Create: `backend/scripts/utils/__init__.py`
- Create: `backend/scripts/utils/ingredient_parser.py`
- Create: `backend/tests/test_ingredient_parser.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_ingredient_parser.py`:

```python
"""Tests for the ingredient text parser."""
from scripts.utils.ingredient_parser import parse_ingredients


def test_simple_comma_list():
    assert parse_ingredients("Leche, Azúcar, Sal") == ["Leche", "Azúcar", "Sal"]


def test_sub_ingredients_extracted():
    result = parse_ingredients("Chocolate (Cacao (50%), Azúcar), Leche")
    assert "Chocolate" in result
    assert "Cacao" in result
    assert "Azúcar" in result
    assert "Leche" in result


def test_deduplication_preserves_order():
    result = parse_ingredients("Azúcar, Sal, Azúcar")
    assert result.count("Azúcar") == 1
    assert result.index("Azúcar") < result.index("Sal")


def test_strips_percentages():
    result = parse_ingredients("Harina (30%), Agua, Aceite (5%)")
    for item in result:
        assert "%" not in item


def test_e_numbers_extracted_as_ingredients():
    result = parse_ingredients("Lecitina de Soja (E322), Agua")
    assert "Lecitina de Soja" in result
    assert "E322" in result


def test_empty_string_returns_empty_list():
    assert parse_ingredients("") == []


def test_whitespace_only_returns_empty_list():
    assert parse_ingredients("   ") == []


def test_strips_asterisk_organic_markers():
    result = parse_ingredients("*Avena integral, Agua")
    assert "Avena integral" in result
    assert "*Avena integral" not in result


def test_deeply_nested_parentheses():
    result = parse_ingredients("Salsa (Tomate (60%), Sal, Aceite de Oliva (Acidez: 0.5%)), Agua")
    assert "Salsa" in result
    assert "Tomate" in result
    assert "Sal" in result
    assert "Aceite de Oliva" in result
    assert "Agua" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_ingredient_parser.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError` or `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Create package init**

Create `backend/scripts/utils/__init__.py` (empty file):
```python
```

- [ ] **Step 4: Implement the parser**

Create `backend/scripts/utils/ingredient_parser.py`:

```python
import re


def parse_ingredients(text: str) -> list[str]:
    """Parse raw OFF ingredient string into individual ingredient names.

    Handles nested sub-ingredients recursively.
    "Chocolate (Cacao (50%), Azúcar), Leche" → ["Chocolate", "Cacao", "Azúcar", "Leche"]
    """
    if not text or not text.strip():
        return []
    segments = _split_top_level(text)
    result: list[str] = []
    seen: set[str] = set()
    for segment in segments:
        _extract(segment.strip(), result, seen)
    return result


def _split_top_level(text: str) -> list[str]:
    """Split on commas that are NOT inside parentheses."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            current.append(ch)
        elif ch == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _extract(segment: str, result: list[str], seen: set[str]) -> None:
    """Extract ingredient name and recurse into parenthesised sub-ingredients."""
    paren_start = segment.find("(")
    if paren_start == -1:
        name = _clean(segment)
        _add(name, result, seen)
        return

    name = _clean(segment[:paren_start])
    _add(name, result, seen)

    inner = _inner_content(segment, paren_start)
    for sub in _split_top_level(inner):
        _extract(sub.strip(), result, seen)


def _inner_content(text: str, start: int) -> str:
    """Return content between the matched parentheses beginning at start."""
    depth = 0
    chars: list[str] = []
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
            if depth > 1:
                chars.append(ch)
        elif ch == ")":
            depth -= 1
            if depth == 0:
                break
            chars.append(ch)
        else:
            chars.append(ch)
    return "".join(chars)


def _clean(segment: str) -> str:
    """Strip percentages, asterisks, and surrounding whitespace."""
    text = re.sub(r"\s*\d+(\.\d+)?\s*%", "", segment)
    return text.strip("* \t\n")


def _add(name: str, result: list[str], seen: set[str]) -> None:
    if name and name.lower() not in seen:
        seen.add(name.lower())
        result.append(name)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_ingredient_parser.py -v
```
Expected: all 9 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/utils/__init__.py backend/scripts/utils/ingredient_parser.py backend/tests/test_ingredient_parser.py
git commit -m "feat(ingestion): add robust ingredient text parser with sub-ingredient extraction"
```

---

## Task 2: `build_product_profile` in `rag.py`

**Files:**
- Modify: `backend/app/services/rag.py`
- Modify: `backend/tests/test_rag.py`

- [ ] **Step 1: Write the failing tests**

Append to the end of `backend/tests/test_rag.py`:

```python
# ─────────────────────────────────────────────
# build_product_profile
# ─────────────────────────────────────────────

from app.services.rag import build_product_profile  # noqa: E402


def test_build_product_profile_base_fields():
    p = Product(barcode="123", name="Avena", brand="Quaker", category="cereals", clean_score=2)
    profile = build_product_profile(p)
    assert "nombre: Avena" in profile
    assert "marca: Quaker" in profile
    assert "categoría: cereals" in profile
    assert "clean_score: 2" in profile
    assert "ingredientes:" not in profile


def test_build_product_profile_includes_ingredients_when_present():
    p = Product(
        barcode="123", name="Avena", brand="Quaker", category="cereals",
        clean_score=1, ingredients_json=["Avena integral", "Azúcar"],
    )
    profile = build_product_profile(p)
    assert "ingredientes: Avena integral, Azúcar" in profile


def test_build_product_profile_caps_ingredients_at_20():
    p = Product(
        barcode="123", name="X", brand="Y", category="z", clean_score=0,
        ingredients_json=[f"ing{i}" for i in range(25)],
    )
    profile = build_product_profile(p)
    assert "ing19" in profile
    assert "ing20" not in profile


def test_build_product_profile_handles_none_fields():
    p = Product(barcode="123", clean_score=0)
    profile = build_product_profile(p)
    assert "desconocido" in profile
    assert "desconocida" in profile
    assert "sin categoría" in profile
```

Note: `Product` is already imported in `test_rag.py` via `from app.models import ...` — confirm the import exists at the top of the file; if not, add it.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_rag.py::test_build_product_profile_base_fields -v
```
Expected: `ImportError: cannot import name 'build_product_profile'`

- [ ] **Step 3: Add `build_product_profile` to `rag.py`**

Add the following at the end of `backend/app/services/rag.py` (after `collection_size`):

```python
def build_product_profile(product: "Product") -> str:  # type: ignore[name-defined]
    """Build a text profile for ChromaDB embedding.

    Includes ingredients when present so semantic search can match
    by composition, not just name/category.
    """
    base = (
        f"nombre: {product.name or 'desconocido'} | "
        f"marca: {product.brand or 'desconocida'} | "
        f"categoría: {product.category or 'sin categoría'} | "
        f"clean_score: {product.clean_score}"
    )
    if product.ingredients_json:
        ings = ", ".join(product.ingredients_json[:20])
        return base + f" | ingredientes: {ings}"
    return base
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_rag.py -v -k "build_product_profile"
```
Expected: 4 tests PASS.

- [ ] **Step 5: Run full test suite to verify no regressions**

```bash
cd backend && python -m pytest --tb=short -q
```
Expected: all previously passing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/rag.py backend/tests/test_rag.py
git commit -m "feat(rag): add build_product_profile with ingredient embedding support"
```

---

## Task 3: Refactor — Centralize `_build_profile`

**Files:**
- Modify: `backend/app/services/enrichment.py` (lines 51–57 and 62)
- Modify: `backend/scripts/index_products_chroma.py` (lines 1–30 and 54)

- [ ] **Step 1: Update `enrichment.py`**

In `backend/app/services/enrichment.py`:

Replace the import block — add `build_product_profile` to the existing `rag` import:
```python
from app.services.rag import get_products_collection, build_product_profile
```

Delete the local `_build_profile` function (lines 51–57):
```python
# DELETE THIS ENTIRE FUNCTION:
def _build_profile(product: Product) -> str:
    return (
        f"nombre: {product.name or 'desconocido'} | "
        f"marca: {product.brand or 'desconocida'} | "
        f"categoría: {product.category or 'sin categoría'} | "
        f"clean_score: {product.clean_score}"
    )
```

Update `_reindex_chroma` to use the shared function. Find this line:
```python
    profile = _build_profile(product)
```
Replace with:
```python
    profile = build_product_profile(product)
```

- [ ] **Step 2: Update `index_products_chroma.py`**

In `backend/scripts/index_products_chroma.py`:

Add import at the top (after existing imports):
```python
from app.services.rag import build_product_profile, get_products_collection
```

Delete the local `_build_profile` function (lines 24–30):
```python
# DELETE THIS ENTIRE FUNCTION:
def _build_profile(product: Product) -> str:
    return (
        f"nombre: {product.name or 'desconocido'} | "
        f"marca: {product.brand or 'desconocida'} | "
        f"categoría: {product.category or 'sin categoría'} | "
        f"clean_score: {product.clean_score}"
    )
```

In `main()`, find:
```python
            profile = _build_profile(product)
```
Replace with:
```python
            profile = build_product_profile(product)
```

Also update the existing `get_products_collection` import line — it is now imported via the line you added above, so remove the duplicate if present.

- [ ] **Step 3: Run full test suite**

```bash
cd backend && python -m pytest --tb=short -q
```
Expected: all tests PASS. No new failures.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/enrichment.py backend/scripts/index_products_chroma.py
git commit -m "refactor(rag): centralize build_product_profile in rag.py, remove local copies"
```

---

## Task 4: `ingest_off_mexico.py`

**Files:**
- Create: `backend/scripts/ingest_off_mexico.py`
- Create: `backend/tests/test_ingest_off_mexico.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_ingest_off_mexico.py`:

```python
"""Tests for the OFF Mexico ingestion script.

HTTP calls are mocked — no network required.
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest


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
    from scripts.ingest_off_mexico import main as ingest_main
    import requests

    def fake_fetch(category, page):
        raise requests.RequestException("timeout")

    with (
        patch("scripts.ingest_off_mexico._fetch_page", side_effect=fake_fetch),
        patch("scripts.ingest_off_mexico.OUTPUT_PATH", tmp_path / "out.json"),
    ):
        ingest_main()  # should not raise

    data = json.loads((tmp_path / "out.json").read_text())
    assert data == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_ingest_off_mexico.py -v 2>&1 | head -15
```
Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Implement `ingest_off_mexico.py`**

Create `backend/scripts/ingest_off_mexico.py`:

```python
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
    "image_front_url",
])


def _fetch_page(category: str, page: int) -> dict:
    resp = requests.get(
        OFF_SEARCH_URL,
        params={
            "countries_tags": "en:mexico",
            "categories_tags": category,
            "fields": _FIELDS,
            "page_size": 1000,
            "page": page,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _map_product(hit: dict, category: str) -> dict | None:
    barcode = (hit.get("code") or "").strip()
    name = (hit.get("product_name_es") or hit.get("product_name") or "").strip()
    ingredients_text = (hit.get("ingredients_text") or "").strip()

    if not barcode or not name or not ingredients_text:
        return None

    ingredients_json = parse_ingredients(ingredients_text)
    if not ingredients_json:
        return None

    brands_raw = hit.get("brands") or ""
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
            if page * 1000 >= total:
                break
            page += 1
            time.sleep(0.1)

    OUTPUT_PATH.write_text(json.dumps(products, ensure_ascii=False, indent=2))
    logger.info("Stats: %s", stats)
    logger.info("Output: %s (%d products)", OUTPUT_PATH, len(products))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_ingest_off_mexico.py -v
```
Expected: all 9 tests PASS.

- [ ] **Step 5: Run full suite**

```bash
cd backend && python -m pytest --tb=short -q
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/ingest_off_mexico.py backend/tests/test_ingest_off_mexico.py
git commit -m "feat(ingestion): add ingest_off_mexico.py — OFF Search API v2, MX health categories"
```

---

## Task 5: `load_products_to_db.py`

**Files:**
- Create: `backend/scripts/load_products_to_db.py`
- Create: `backend/tests/test_load_products_to_db.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_load_products_to_db.py`:

```python
"""Tests for the DB load script.

Uses in-memory SQLite — no file I/O, no network.
"""
import json

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models import Product
from app.models.base import Base


@pytest.fixture()
def mem_db():
    """Fresh in-memory SQLite with full schema."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _write_input(tmp_path, products: list[dict]) -> object:
    path = tmp_path / "off_products.json"
    path.write_text(json.dumps(products))
    return path


def _run_load(mem_db, tmp_path, products):
    import scripts.load_products_to_db as loader
    from unittest.mock import patch

    path = _write_input(tmp_path, products)
    with (
        patch.object(loader, "INPUT_PATH", path),
        patch.object(loader, "SessionLocal", lambda: mem_db),
    ):
        loader.main()


_PRODUCT = {
    "barcode": "1234567890123",
    "name": "Avena Quaker",
    "brand": "Quaker",
    "category": "breakfast-cereals",
    "image_url": None,
    "ingredients_json": ["Avena integral", "Sal"],
    "ingredients_source": "off_dump_mx",
}


def test_inserts_new_product(mem_db, tmp_path):
    _run_load(mem_db, tmp_path, [_PRODUCT])
    result = mem_db.scalar(select(Product).where(Product.barcode == "1234567890123"))
    assert result is not None
    assert result.name == "Avena Quaker"
    assert result.ingredients_source == "off_dump_mx"
    assert result.ingredients_json == ["Avena integral", "Sal"]


def test_updates_existing_product(mem_db, tmp_path):
    mem_db.add(Product(barcode="1234567890123", name="Old Name", clean_score=0))
    mem_db.commit()

    updated = {**_PRODUCT, "name": "New Name"}
    _run_load(mem_db, tmp_path, [updated])

    result = mem_db.scalar(select(Product).where(Product.barcode == "1234567890123"))
    assert result.name == "New Name"


def test_idempotent_run(mem_db, tmp_path):
    _run_load(mem_db, tmp_path, [_PRODUCT])
    _run_load(mem_db, tmp_path, [_PRODUCT])

    count = mem_db.scalar(
        select(func.count()).select_from(Product).where(Product.barcode == "1234567890123")
    )
    assert count == 1


def test_missing_file_exits_cleanly(mem_db, tmp_path):
    import scripts.load_products_to_db as loader
    from unittest.mock import patch

    missing = tmp_path / "nonexistent.json"
    with (
        patch.object(loader, "INPUT_PATH", missing),
        patch.object(loader, "SessionLocal", lambda: mem_db),
    ):
        loader.main()  # should log error, not raise


def test_inserts_multiple_products(mem_db, tmp_path):
    products = [
        {**_PRODUCT, "barcode": f"BC{i}", "name": f"Product {i}"}
        for i in range(5)
    ]
    _run_load(mem_db, tmp_path, products)

    count = mem_db.scalar(select(func.count()).select_from(Product))
    assert count == 5
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_load_products_to_db.py -v 2>&1 | head -15
```
Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Implement `load_products_to_db.py`**

Create `backend/scripts/load_products_to_db.py`:

```python
"""Load curated products from off_products.json into the products table.

Upsert logic is dialect-agnostic (SQLite + PostgreSQL compatible).
Safe to run multiple times — subsequent runs update existing records.

Prerequisite: run ingest_off_mexico.py first.

Usage:
    cd backend && python -m scripts.load_products_to_db
"""
import json
import logging
from pathlib import Path

from sqlalchemy import select

from app.models import Product
from app.models.base import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INPUT_PATH = Path(__file__).parent / "data" / "off_products.json"
BATCH_SIZE = 100


def main() -> None:
    if not INPUT_PATH.exists():
        logger.error(
            "Input not found: %s — run ingest_off_mexico.py first", INPUT_PATH
        )
        return

    with INPUT_PATH.open() as f:
        products = json.load(f)

    logger.info("Loading %d products into DB...", len(products))
    db = SessionLocal()
    inserted = updated = errors = 0

    try:
        for i, p in enumerate(products):
            try:
                existing = db.scalar(
                    select(Product).where(Product.barcode == p["barcode"])
                )
                if existing:
                    existing.name = p.get("name")
                    existing.brand = p.get("brand")
                    existing.category = p.get("category")
                    existing.image_url = p.get("image_url")
                    existing.ingredients_json = p.get("ingredients_json")
                    existing.ingredients_source = p.get("ingredients_source")
                    updated += 1
                else:
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
            except Exception as exc:
                logger.warning("Error on barcode %s: %s", p.get("barcode"), exc)
                errors += 1

            if (i + 1) % BATCH_SIZE == 0:
                db.commit()
                logger.info("  %d/%d processed...", i + 1, len(products))

        db.commit()
        logger.info(
            "Done. inserted=%d updated=%d errors=%d", inserted, updated, errors
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_load_products_to_db.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 5: Run full suite**

```bash
cd backend && python -m pytest --tb=short -q
```
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/load_products_to_db.py backend/tests/test_load_products_to_db.py
git commit -m "feat(ingestion): add load_products_to_db.py — dialect-agnostic upsert"
```

---

## Task 6: Gitignore + Pipeline Execution + Validation

**Files:**
- Modify: `.gitignore` (root)
- Run: full pipeline against real OFF API

- [ ] **Step 1: Add `scripts/data/` to gitignore**

In the root `.gitignore`, add:

```
# Ingestion script output (can be large, regenerated on demand)
backend/scripts/data/
```

Commit:
```bash
git add .gitignore
git commit -m "chore: gitignore backend/scripts/data/ ingestion output"
```

- [ ] **Step 2: Verify `seed_rag.py` has been run (prerequisite)**

```bash
cd backend && python -m pytest tests/test_rag.py -v -q 2>&1 | tail -5
```

Also check the ingredients table is populated:
```bash
cd backend && python -c "
from sqlalchemy import select, func
from app.models import Ingredient
from app.models.base import SessionLocal
db = SessionLocal()
count = db.scalar(select(func.count()).select_from(Ingredient))
print(f'Ingredients in DB: {count}')
db.close()
"
```
If count is 0, run: `python -m scripts.seed_rag` before continuing.

- [ ] **Step 3: Run ingestion**

```bash
cd backend && python -m scripts.ingest_off_mexico
```

Expected log output (approximate):
```
INFO - Fetching category: en:yogurts
INFO - Fetching category: en:fermented-milks
...
INFO - Stats: {'fetched': XXXX, 'accepted': 4XX, 'skipped_no_barcode': XX, ...}
INFO - Output: .../scripts/data/off_products.json (4XX products)
```

If `accepted` is 0, check network access and that `ingredients_text` field is returned by the API.

- [ ] **Step 4: Load to DB**

```bash
cd backend && python -m scripts.load_products_to_db
```

Expected:
```
INFO - Loading 4XX products into DB...
INFO - Done. inserted=4XX updated=0 errors=0
```

- [ ] **Step 5: Compute clean scores**

```bash
cd backend && python -m scripts.compute_clean_scores
```

Expected:
```
INFO - Computing clean_score for 4XX enriched products...
INFO - Done.
```

- [ ] **Step 6: Index in ChromaDB**

```bash
cd backend && python -m scripts.index_products_chroma
```

Expected:
```
INFO - Indexing 4XX products into ChromaDB 'products' collection...
INFO - Done. 4XX products indexed.
```

- [ ] **Step 7: Validate success criteria**

```bash
cd backend && python -c "
from sqlalchemy import select, func
from app.models import Product
from app.models.base import SessionLocal

db = SessionLocal()

total = db.scalar(select(func.count()).select_from(Product).where(
    Product.ingredients_source == 'off_dump_mx'
))
print(f'OFF MX products: {total}')
assert total >= 400, f'Expected >= 400, got {total}'

scored = db.scalar(select(func.count()).select_from(Product).where(
    Product.clean_score > 0
))
print(f'Products with clean_score > 0: {scored}')
assert scored > 0, 'clean_score > 0 count must be > 0 (RAG not working?)'

db.close()
print('✅ All success criteria passed.')
"
```

- [ ] **Step 8: Validate ChromaDB**

```bash
cd backend && python -c "
from app.config import get_settings
from app.services.rag import get_products_collection

settings = get_settings()
col = get_products_collection(settings)
count = col.count()
print(f'ChromaDB products collection: {count} embeddings')
assert count >= 400, f'Expected >= 400, got {count}'
print('✅ ChromaDB OK.')
"
```

- [ ] **Step 9: Verify seed_alternatives_fixture still works**

```bash
cd backend && python -m scripts.seed_alternatives_fixture
```

Expected: `INFO - Seeded 10 fixture products.` — no errors.

- [ ] **Step 10: Run full test suite one final time**

```bash
cd backend && python -m pytest --tb=short -q
```
Expected: all tests PASS.

- [ ] **Step 11: Final commit**

```bash
git add .gitignore
git commit -m "chore(ingestion): gitignore scripts/data/, pipeline validated — 400+ products indexed"
```

---

## Multi-Country Scaling (When Needed)

When a second market is added, see `docs/superpowers/specs/2026-05-12-product-ingestion-off-design.md §6` for the full step-by-step. Summary:

1. Parametrize `ingest_off_mexico.py` → `ingest_off.py --country-tag en:spain --market es`
2. Add Alembic migration: `market VARCHAR(10)` column on `products`
3. Backfill: `UPDATE products SET market='mx' WHERE ingredients_source='off_dump_mx'`
4. Add `market` filter to `alternatives.py` SQL first pass + ChromaDB `where` metadata
5. Add `market` to ChromaDB embedding metadata in `index_products_chroma.py`

Do NOT do these steps now — YAGNI until a second market is actually being added.
