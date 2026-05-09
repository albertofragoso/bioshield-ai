# Scan → Product Enrichment Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir cada scan exitoso en una contribución automática al curated DB — escribir `ingredients_json`, recalcular `clean_score`, y re-indexar en ChromaDB, todo sin latencia para el usuario.

**Architecture:** BackgroundTask por scan (mismo patrón que `_run_off_contribution`). El servicio central (`enrichment.py`) aplica first-write-wins via `SELECT FOR UPDATE`. Foto scans sin barcode activan tres excepciones en cascada: Ex.1 Gemini extrae barcode de imagen, Ex.2 OFF lookup async, Ex.4 CTA manual del usuario.

**Tech Stack:** FastAPI BackgroundTasks, SQLAlchemy `with_for_update()`, httpx (OFF search API), ChromaDB upsert, BGE-M3 embeddings via `embed_text`, Pydantic v2, Next.js 14.

**Worktree:** `/Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2` (branch `feat/fase2-alternative-matching`). Nunca tocar `main`.

---

## File Map

| Archivo | Tipo | Cambio |
|---|---|---|
| `backend/alembic/versions/{hash}_add_enrichment_fields.py` | Nuevo | Migración: 4 campos en `products` |
| `backend/app/models/__init__.py` | Modificar | 4 campos ORM en `Product` |
| `backend/app/schemas/models.py` | Modificar | `ProductExtraction.barcode`, `ScanResponse.show_barcode_cta`, `LinkBarcodeRequest` |
| `backend/app/agents/state.py` | Modificar | `ScanState.extracted_barcode` |
| `backend/app/agents/nodes.py` | Modificar | `make_extract_ingredients_node` propaga `extracted_barcode` |
| `backend/app/services/off_client.py` | Modificar | Agregar `off_lookup_barcode()` |
| `backend/app/services/enrichment.py` | Nuevo | Toda la lógica de enriquecimiento |
| `backend/app/routers/scan.py` | Modificar | BackgroundTasks, scan_photo Ex.1+2, /link endpoint, GET fix, _persist fix |
| `backend/scripts/compute_clean_scores.py` | Modificar | Importar `_compute_clean_score` de enrichment, fix `main()` |
| `backend/tests/test_enrichment.py` | Nuevo | 12 tests unitarios del servicio |
| `frontend/lib/api/types.ts` | Modificar | `ScanResponse.show_barcode_cta`, `LinkBarcodeRequest` |
| `frontend/lib/api/scan.ts` | Modificar | `linkPhotoToBarcode()` |
| `frontend/app/(app)/scan/[id]/page.tsx` | Modificar | `LinkBarcodeCard` component + render condicional |
| `docs/architecture.md` | Modificar | §Enrichment Pipeline |
| `docs/embedding-strategy.md` | Modificar | §11 nota flywheel |
| `PRD.md` | Modificar | Fase 2 menciona enrichment |

---

## Task 1: DB Migration — 4 nuevos campos en `products`

**Files:**
- Create: `backend/alembic/versions/{hash}_add_enrichment_fields.py`

- [ ] **Step 1: Generar migración vacía**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
source .venv/bin/activate
python -m alembic revision --autogenerate -m "add_enrichment_fields"
```

Esto crea un archivo en `alembic/versions/`. Anota el hash generado (e.g. `abc123_add_enrichment_fields.py`). Verifica que `down_revision` sea `"aabbc492fe8d"`.

- [ ] **Step 2: Reemplazar el contenido de la migración generada**

Reemplaza todo el contenido del archivo generado con:

```python
"""add enrichment fields to products

Revision ID: <el hash generado>
Revises: aabbc492fe8d
Create Date: 2026-05-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "<el hash generado>"
down_revision: str | None = "aabbc492fe8d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ingredients_json", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("ingredients_source", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("ingredients_confidence", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "needs_barcode_link",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
    op.create_index(
        "idx_products_needs_barcode_link",
        "products",
        ["needs_barcode_link"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_products_needs_barcode_link", table_name="products")
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_column("needs_barcode_link")
        batch_op.drop_column("ingredients_confidence")
        batch_op.drop_column("ingredients_source")
        batch_op.drop_column("ingredients_json")
```

**IMPORTANTE:** Sustituye `<el hash generado>` con el hash real del archivo. El hash aparece en el nombre del archivo y en `revision`.

- [ ] **Step 3: Aplicar migración**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -m alembic upgrade head
```

Expected output: `Running upgrade aabbc492fe8d -> <hash>, add enrichment fields to products`

- [ ] **Step 4: Verificar columnas**

```bash
python -c "
from sqlalchemy import inspect, create_engine
e = create_engine('sqlite:///./bioshield.db')
cols = {c['name'] for c in inspect(e).get_columns('products')}
required = {'ingredients_json', 'ingredients_source', 'ingredients_confidence', 'needs_barcode_link'}
missing = required - cols
print('OK' if not missing else f'MISSING: {missing}')
"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/
git commit -m "feat(db): add enrichment fields to products table"
```

---

## Task 2: ORM — 4 campos en `Product`

**Files:**
- Modify: `backend/app/models/__init__.py`

El modelo `Product` actualmente termina en la línea con `clean_score` y `created_at`. Lee el archivo para confirmar las líneas exactas antes de editar.

- [ ] **Step 1: Agregar imports faltantes al bloque de imports de SQLAlchemy**

Abre `backend/app/models/__init__.py`. Busca la línea de imports de sqlalchemy (ya existe `JSON`, `Boolean`, `Float`). Si alguno falta, agrégalo. Los imports actuales incluyen `Boolean`, `Float`, `JSON` — verifica que estén:

```python
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    String,
    text,
)
```

- [ ] **Step 2: Agregar los 4 campos al modelo `Product`**

En `class Product(Base)`, después de la línea `clean_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)` y antes de `created_at`, agrega:

```python
    ingredients_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    ingredients_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ingredients_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    needs_barcode_link: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
```

- [ ] **Step 3: Verificar que el modelo importa correctamente**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -c "from app.models import Product; p = Product.__table__.columns.keys(); assert 'ingredients_json' in p and 'needs_barcode_link' in p; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/models/__init__.py
git commit -m "feat(models): add enrichment fields to Product ORM"
```

---

## Task 3: Schemas — `ProductExtraction.barcode`, `ScanResponse.show_barcode_cta`, `LinkBarcodeRequest`

**Files:**
- Modify: `backend/app/schemas/models.py`

- [ ] **Step 1: Agregar `barcode` a `ProductExtraction`**

`ProductExtraction` está en `app/schemas/models.py`. Búscala. Actualmente tiene `product_name`, `ingredients`, `has_additives`, `language`. Agrégale `barcode`:

```python
class ProductExtraction(BaseModel):
    product_name: str | None = None
    ingredients: list[str]
    has_additives: bool
    language: str = "es"
    barcode: str | None = None  # EAN/UPC si es visible en la imagen
```

- [ ] **Step 2: Agregar `show_barcode_cta` a `ScanResponse`**

`ScanResponse` tiene `product_barcode`, `product_name`, `semaphore`, `ingredients`, `conflict_severity`, `source`, `scanned_at`, `personalized_insights`. Agrégale al final:

```python
class ScanResponse(BaseModel):
    product_barcode: str
    product_name: str | None = None
    semaphore: SemaphoreColor
    ingredients: list[IngredientResult]
    conflict_severity: ConflictSeverity | None = None
    source: str = Field(description="'barcode' if from OFF, 'photo' if from Gemini OCR")
    scanned_at: datetime
    personalized_insights: list["PersonalizedInsight"] = []
    show_barcode_cta: bool = False  # ephemeral — NO se persiste en result_json
```

- [ ] **Step 3: Agregar `LinkBarcodeRequest`**

Agrega esta clase cerca de `BarcodeRequest` o `PhotoScanRequest`:

```python
class LinkBarcodeRequest(BaseModel):
    barcode: str = Field(..., min_length=8, max_length=14, pattern=r"^\d+$")
```

- [ ] **Step 4: Verificar imports**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -c "
from app.schemas.models import ProductExtraction, ScanResponse, LinkBarcodeRequest
assert hasattr(ProductExtraction, 'barcode')
assert hasattr(ScanResponse, 'show_barcode_cta')
assert hasattr(LinkBarcodeRequest, 'barcode')
print('OK')
"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add app/schemas/models.py
git commit -m "feat(schemas): add barcode extraction field and CTA flag"
```

---

## Task 4: Agents — propagar `extracted_barcode` desde Gemini

**Files:**
- Modify: `backend/app/agents/state.py`
- Modify: `backend/app/agents/nodes.py`

El nodo `extract_ingredients` llama a `gemini_service.extract_from_image()` que retorna `ProductExtraction`. Ahora que `ProductExtraction.barcode` existe, hay que propagarlo al estado del grafo.

- [ ] **Step 1: Agregar `extracted_barcode` a `ScanState`**

En `backend/app/agents/state.py`, dentro de `class ScanState(TypedDict, total=False)`, en la sección `# ─── Intermediate ───`, agrega:

```python
    extracted_barcode: str | None  # barcode extraído por Gemini Vision de la imagen
```

La sección queda:

```python
    # ─── Intermediate ───
    product_name: str | None
    product_brand: str | None
    product_image_url: str | None
    extracted_ingredients: list[str]
    extracted_barcode: str | None  # barcode extraído por Gemini Vision de la imagen
    resolved: list[IngredientResult]
    rag_context_by_ingredient: dict[str, str]
    biomarkers: list | None
    conflicts_by_ingredient: dict[str, list[IngredientConflict]]
    personalized_insights: list[PersonalizedInsight]
```

- [ ] **Step 2: Actualizar `make_extract_ingredients_node` en `nodes.py`**

En `backend/app/agents/nodes.py`, busca `make_extract_ingredients_node`. Actualmente retorna:

```python
        return {
            "product_name": extraction.product_name,
            "extracted_ingredients": extraction.ingredients,
            "source": "photo",
        }
```

Cámbialo a:

```python
        return {
            "product_name": extraction.product_name,
            "extracted_ingredients": extraction.ingredients,
            "extracted_barcode": extraction.barcode,
            "source": "photo",
        }
```

- [ ] **Step 3: Verificar que el grafo importa sin errores**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -c "from app.agents.graph import build_scan_graph; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Agregar instrucción de barcode al prompt de Gemini**

En `backend/docs/prompts.md` (o el archivo donde viva `EXTRACTION_PROMPT`), busca el prompt de extracción de ingredientes. Agrega al final de las instrucciones:

```
Si el código de barras EAN/UPC aparece como número impreso en la imagen
(8–14 dígitos), extráelo en el campo `barcode`. Si no es claramente
visible o legible, devuelve null.
```

Para encontrar el archivo exacto:
```bash
grep -rn "EXTRACTION_PROMPT\|extract_from_image\|system_instruction" /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend/app/ | grep -v ".pyc"
```

- [ ] **Step 5: Commit**

```bash
git add app/agents/state.py app/agents/nodes.py
git commit -m "feat(agents): propagate barcode extracted from image via Gemini Vision"
```

---

## Task 5: OFF Client — agregar `off_lookup_barcode()`

**Files:**
- Modify: `backend/app/services/off_client.py`

Esta función busca un barcode en OFF por nombre y marca. Retorna el EAN del primer resultado con alta confianza, o `None`.

- [ ] **Step 1: Agregar `off_lookup_barcode` al final de `off_client.py`**

Agrega esta función después de `contribute_product`:

```python
async def off_lookup_barcode(
    name: str,
    brand: str | None,
    settings: Settings,
) -> str | None:
    """Busca el barcode EAN de un producto en OFF por nombre+marca.

    Retorna el EAN del primer resultado si tiene alta confianza de match,
    None si no encuentra o OFF está caído.
    """
    from urllib.parse import quote

    query = f"{name} {brand}" if brand else name
    url = f"{settings.off_write_base_url}/search.pl"
    timeout = httpx.Timeout(settings.off_timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(
                url,
                params={
                    "search_terms": query,
                    "cc": "mx",
                    "json": "1",
                    "page_size": "5",
                    "fields": "code,product_name,brands",
                },
            )
            if response.status_code != 200:
                return None
            data = response.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.warning("OFF search failed for '%s': %s", query, exc)
            return None

    products = data.get("products") or []
    if not products:
        return None

    first = products[0]
    code = first.get("code") or ""
    # Validar que el código tenga formato EAN válido (8–14 dígitos)
    if code and code.isdigit() and 8 <= len(code) <= 14:
        return code
    return None
```

- [ ] **Step 2: Verificar que importa correctamente**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -c "from app.services.off_client import off_lookup_barcode; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/services/off_client.py
git commit -m "feat(off-client): add barcode lookup by name+brand via OFF search API"
```

---

## Task 6: Enrichment Service — `app/services/enrichment.py`

**Files:**
- Create: `backend/app/services/enrichment.py`

Módulo nuevo con toda la lógica de enriquecimiento. El router solo dispara BackgroundTasks que llaman estas funciones.

- [ ] **Step 1: Escribir los tests primero (TDD)**

Crea `backend/tests/test_enrichment.py` con tests que van a fallar porque el módulo no existe aún:

```python
"""Tests for the product enrichment service.

Tests usan la capa de servicio directamente (no via HTTP) para evitar
complejidad con BackgroundTasks.
"""
import pytest
from sqlalchemy import select

from app.models import Ingredient, Product, RegulatoryStatus, ScanHistory
from app.schemas.models import IngredientResult


# ─── Fixtures ───────────────────────────────────────────────────────────────


def _make_ingredient_result(name: str, canonical: str | None, score: float = 0.9) -> IngredientResult:
    return IngredientResult(name=name, canonical_name=canonical, confidence_score=score)


def _add_product(db, barcode: str, ingredients_json=None) -> Product:
    p = Product(barcode=barcode, name=f"Prod {barcode}")
    if ingredients_json is not None:
        p.ingredients_json = ingredients_json
    db.add(p)
    db.flush()
    return p


# ─── should_enrich ───────────────────────────────────────────────────────────


def test_should_enrich_returns_true_for_clean_product(db_session):
    from app.services.enrichment import should_enrich

    product = _add_product(db_session, "7501111111111")
    assert should_enrich(product) is True


def test_should_enrich_returns_false_if_already_enriched(db_session):
    from app.services.enrichment import should_enrich

    product = _add_product(db_session, "7501111111112", ingredients_json=["azucar"])
    assert should_enrich(product) is False


def test_should_enrich_returns_false_for_pseudo_barcode(db_session):
    from app.services.enrichment import should_enrich

    product = _add_product(db_session, "photo-abc123def456")
    assert should_enrich(product) is False


# ─── _compute_clean_score ────────────────────────────────────────────────────


def test_compute_clean_score_ignores_unknown_ingredients(db_session):
    from app.services.enrichment import _compute_clean_score

    score = _compute_clean_score(["ingrediente_inexistente_xyz"], db_session)
    assert score == 0


def test_compute_clean_score_counts_banned_ingredients(db_session):
    from app.services.enrichment import _compute_clean_score

    # Crear ingrediente y su regulatory status como Banned
    ing = Ingredient(
        id="test-ing-1",
        canonical_name="test_banned_ing",
        entity_id="CAS:00000-00-0",
    )
    db_session.add(ing)
    db_session.flush()

    status = RegulatoryStatus(
        id="test-rs-1",
        ingredient_id=ing.id,
        region="GLOBAL",
        source="TEST",
        status="Banned",
    )
    db_session.add(status)
    db_session.flush()

    score = _compute_clean_score(["test_banned_ing"], db_session)
    assert score == 1


# ─── enrich_product ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_enrich_product_skips_if_low_confidence(db_session):
    from app.services.enrichment import enrich_product

    product = _add_product(db_session, "7501111111113")
    resolved = [_make_ingredient_result("azucar", "sucrose", score=0.5)]

    await enrich_product(
        barcode="7501111111113",
        resolved=resolved,
        avg_confidence=0.5,  # below threshold
        source="scan",
        db=db_session,
        settings=None,
    )

    db_session.refresh(product)
    # should NOT enrich — avg_confidence < 0.8
    assert product.ingredients_json is None


@pytest.mark.anyio
async def test_enrich_product_writes_ingredients_and_score(db_session, monkeypatch):
    from app.services import enrichment as enrichment_module

    async def _fake_reindex(*args, **kwargs):
        pass

    monkeypatch.setattr(enrichment_module, "_reindex_chroma", _fake_reindex)

    product = _add_product(db_session, "7501111111114")
    resolved = [_make_ingredient_result("water", "water", score=0.95)]

    await enrichment_module.enrich_product(
        barcode="7501111111114",
        resolved=resolved,
        avg_confidence=0.95,
        source="scan",
        db=db_session,
        settings=object(),  # settings not used when _reindex_chroma is mocked
    )

    db_session.refresh(product)
    assert product.ingredients_json == ["water"]
    assert product.ingredients_source == "scan"
    assert product.ingredients_confidence == pytest.approx(0.95)


@pytest.mark.anyio
async def test_enrich_product_concurrent_skip(db_session, monkeypatch):
    """Segundo call al mismo barcode no sobreescribe el primero."""
    from app.services import enrichment as enrichment_module

    async def _fake_reindex(*args, **kwargs):
        pass

    monkeypatch.setattr(enrichment_module, "_reindex_chroma", _fake_reindex)

    product = _add_product(db_session, "7501111111115")
    resolved_a = [_make_ingredient_result("sugar", "sucrose", score=0.9)]
    resolved_b = [_make_ingredient_result("salt", "sodium chloride", score=0.95)]

    # Primer enriquecimiento
    await enrichment_module.enrich_product("7501111111115", resolved_a, 0.9, "scan", db_session, object())
    # Segundo enriquecimiento — debe ser ignorado (first-write-wins)
    await enrichment_module.enrich_product("7501111111115", resolved_b, 0.95, "scan", db_session, object())

    db_session.refresh(product)
    assert product.ingredients_json == ["sucrose"]  # primer resultado se mantiene


# ─── link_photo_to_barcode ───────────────────────────────────────────────────


@pytest.mark.anyio
async def test_link_photo_to_barcode_validates_ownership(db_session, monkeypatch):
    from fastapi import HTTPException
    from app.services.enrichment import link_photo_to_barcode
    from app.models import User

    user = User(id="user-1", email="a@b.com", password_hash="x")
    db_session.add(user)
    pseudo = _add_product(db_session, "photo-aabbccddeeff0011")
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await link_photo_to_barcode("photo-aabbccddeeff0011", "7501000000001", "user-2", db_session, None)

    assert exc_info.value.status_code == 403


@pytest.mark.anyio
async def test_link_photo_to_barcode_enriches_real_product(db_session, monkeypatch):
    from app.services import enrichment as enrichment_module
    from app.models import User

    async def _fake_reindex(*args, **kwargs):
        pass

    async def _fake_enrich(barcode, resolved, avg_confidence, source, db, settings):
        product = db.scalar(select(Product).where(Product.barcode == barcode))
        if product:
            product.ingredients_json = [r.canonical_name for r in resolved if r.canonical_name]
            db.commit()

    monkeypatch.setattr(enrichment_module, "_reindex_chroma", _fake_reindex)
    monkeypatch.setattr(enrichment_module, "enrich_product", _fake_enrich)

    user = User(id="user-3", email="c@d.com", password_hash="x")
    db_session.add(user)
    db_session.flush()

    pseudo = _add_product(db_session, "photo-112233445566aabb")
    pseudo.needs_barcode_link = True
    db_session.flush()

    history = ScanHistory(
        id="hist-1",
        user_id="user-3",
        product_barcode="photo-112233445566aabb",
        confidence_score=0.92,
        result_json={"ingredients": [{"name": "water", "canonical_name": "water", "confidence_score": 0.92, "conflicts": []}]},
        semaphore_result="BLUE",
    )
    db_session.add(history)
    db_session.commit()

    real = await enrichment_module.link_photo_to_barcode(
        "photo-112233445566aabb", "7502000000001", "user-3", db_session, None
    )

    assert real.barcode == "7502000000001"
    db_session.refresh(pseudo)
    assert pseudo.needs_barcode_link is False
```

- [ ] **Step 2: Ejecutar tests — verificar que fallan por módulo faltante**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -m pytest tests/test_enrichment.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'should_enrich' from 'app.services.enrichment'` o `ModuleNotFoundError`.

- [ ] **Step 3: Crear `app/services/enrichment.py`**

```python
"""Scan → Product Enrichment Service.

Cierra el gap entre scan_history.result_json y products.ingredients_json.
Toda la lógica de enriquecimiento vive aquí — el router solo dispara BackgroundTasks.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Ingredient, Product, RegulatoryStatus, ScanHistory
from app.schemas.models import IngredientResult
from app.services.embeddings import embed_text
from app.services.rag import get_products_collection

logger = logging.getLogger(__name__)

_BANNED_STATUSES = {"Banned", "Restricted"}
_MIN_CONFIDENCE = 0.8


def should_enrich(product: Product) -> bool:
    """True si el producto aún no tiene ingredientes y tiene barcode real."""
    return (
        product.ingredients_json is None
        and not product.barcode.startswith("photo-")
    )


def _compute_clean_score(canonical_names: list[str], db: Session) -> int:
    """Cuenta ingredientes con estatus regulatorio Banned o Restricted."""
    score = 0
    for name in canonical_names:
        ing = db.scalar(select(Ingredient).where(Ingredient.canonical_name.ilike(name)))
        if ing is None:
            continue
        statuses = list(
            db.scalars(select(RegulatoryStatus).where(RegulatoryStatus.ingredient_id == ing.id))
        )
        if any(s.status in _BANNED_STATUSES for s in statuses):
            score += 1
    return score


def _semaphore(clean_score: int) -> str:
    if clean_score == 0:
        return "BLUE"
    if clean_score <= 2:
        return "YELLOW"
    if clean_score <= 4:
        return "ORANGE"
    return "RED"


def _build_profile(product: Product) -> str:
    return (
        f"nombre: {product.name or 'desconocido'} | "
        f"marca: {product.brand or 'desconocida'} | "
        f"categoría: {product.category or 'sin categoría'} | "
        f"clean_score: {product.clean_score}"
    )


async def _reindex_chroma(product: Product, settings: Settings) -> None:
    """Re-indexa un producto en la colección ChromaDB 'products'."""
    collection = get_products_collection(settings)
    profile = _build_profile(product)
    embedding = await embed_text(profile, settings)
    collection.upsert(
        ids=[product.barcode],
        documents=[profile],
        embeddings=[embedding],
        metadatas=[
            {
                "barcode": product.barcode,
                "category": product.category or "",
                "clean_score": product.clean_score,
                "semaphore_precomputed": _semaphore(product.clean_score),
            }
        ],
    )


async def enrich_product(
    barcode: str,
    resolved: list[IngredientResult],
    avg_confidence: float,
    source: str,
    db: Session,
    settings: Settings,
) -> None:
    """Escribe ingredients_json, clean_score y re-indexa en ChromaDB.

    First-write-wins: si otro proceso ya enriqueció el producto,
    el SELECT FOR UPDATE lo detecta y retorna sin modificar nada.
    No enriquece si avg_confidence < 0.8.
    """
    if avg_confidence < _MIN_CONFIDENCE:
        return

    product = db.scalar(
        select(Product).where(Product.barcode == barcode).with_for_update()
    )
    if product is None or not should_enrich(product):
        return

    canonical_names = [r.canonical_name for r in resolved if r.canonical_name]
    product.ingredients_json = canonical_names
    product.ingredients_source = source
    product.ingredients_confidence = avg_confidence
    product.clean_score = _compute_clean_score(canonical_names, db)
    db.commit()

    if product.category:
        await _reindex_chroma(product, settings)


async def try_off_lookup(
    name: str | None,
    brand: str | None,
    pseudo_barcode: str,
    db: Session,
    settings: Settings,
) -> None:
    """Busca el barcode real en OFF por nombre+marca (Ex.2).

    Si encuentra barcode real: crea/actualiza Product, copia ingredientes
    del ScanHistory y enriquece. Limpia needs_barcode_link del pseudo producto.
    """
    if not name:
        return

    from app.services.off_client import off_lookup_barcode

    barcode = await off_lookup_barcode(name, brand, settings)
    if not barcode:
        return

    photo_product = db.scalar(select(Product).where(Product.barcode == pseudo_barcode))

    # Upsert producto real
    real_product = db.scalar(select(Product).where(Product.barcode == barcode))
    if real_product is None:
        real_product = Product(barcode=barcode, name=name, brand=brand)
        db.add(real_product)
    db.flush()

    if should_enrich(real_product):
        history = db.scalar(
            select(ScanHistory)
            .where(ScanHistory.product_barcode == pseudo_barcode)
            .order_by(ScanHistory.scanned_at.desc())
        )
        if (
            history
            and history.result_json
            and (history.confidence_score or 0) >= _MIN_CONFIDENCE
        ):
            resolved = [
                IngredientResult.model_validate(i)
                for i in history.result_json.get("ingredients", [])
            ]
            await enrich_product(
                barcode, resolved, history.confidence_score, "off", db, settings
            )

    if photo_product:
        photo_product.needs_barcode_link = False
    db.commit()


async def link_photo_to_barcode(
    pseudo_barcode: str,
    real_barcode: str,
    user_id: str,
    db: Session,
    settings: Settings,
) -> Product:
    """Vincula un photo scan con un barcode real proporcionado por el usuario (Ex.4).

    Valida que el ScanHistory pertenezca al usuario (403 si no).
    Crea el Product real, lo enriquece con los ingredientes del scan original,
    y limpia needs_barcode_link del pseudo producto.
    """
    history = db.scalar(
        select(ScanHistory)
        .where(
            ScanHistory.product_barcode == pseudo_barcode,
            ScanHistory.user_id == user_id,
        )
        .order_by(ScanHistory.scanned_at.desc())
    )
    if not history:
        raise HTTPException(status_code=403, detail="Scan no encontrado o no autorizado.")

    photo_product = db.scalar(select(Product).where(Product.barcode == pseudo_barcode))

    # Upsert producto real
    real_product = db.scalar(select(Product).where(Product.barcode == real_barcode))
    if real_product is None:
        real_product = Product(
            barcode=real_barcode,
            name=photo_product.name if photo_product else None,
        )
        db.add(real_product)
    db.flush()

    if history.result_json and should_enrich(real_product):
        resolved = [
            IngredientResult.model_validate(i)
            for i in history.result_json.get("ingredients", [])
        ]
        avg_conf = history.confidence_score or 0.0
        if avg_conf >= _MIN_CONFIDENCE:
            await enrich_product(real_barcode, resolved, avg_conf, "scan", db, settings)

    if photo_product:
        photo_product.needs_barcode_link = False
    db.commit()
    return real_product
```

- [ ] **Step 4: Ejecutar tests — verificar que pasan**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -m pytest tests/test_enrichment.py -v 2>&1 | tail -30
```

Expected: todos los tests `PASSED`. Si algún test relacionado a fixtures de DB falla, revisar que `conftest.py` tenga el `test_engine` con `Base.metadata.create_all` incluyendo los nuevos campos.

- [ ] **Step 5: Commit**

```bash
git add app/services/enrichment.py tests/test_enrichment.py
git commit -m "feat(enrichment): add product enrichment service with first-write-wins"
```

---

## Task 7: Scan Router — BackgroundTasks + `_persist` fix

**Files:**
- Modify: `backend/app/routers/scan.py`

Cuatro cambios en `scan.py`:
1. Agregar imports
2. Fix `_persist_scan_history` para excluir `show_barcode_cta`
3. Agregar BackgroundTask helpers privados
4. Actualizar `scan_barcode` para disparar enriquecimiento

- [ ] **Step 1: Agregar imports faltantes**

En el bloque de imports de `scan.py`, agrega:

```python
from uuid import UUID, uuid4  # uuid4 ya existe — verificar
from app.models.base import SessionLocal  # verificar si ya existe
from app.schemas.models import LinkBarcodeRequest  # nuevo import
```

Verifica que `BackgroundTasks` esté importado de `fastapi`. Si no:
```python
from fastapi import BackgroundTasks, Depends, HTTPException, Request, status
```

- [ ] **Step 2: Fix `_persist_scan_history` — excluir `show_barcode_cta`**

Busca la línea en `_persist_scan_history` que dice:
```python
result_json=response.model_dump(mode="json"),
```

Cámbiala a:
```python
result_json=response.model_dump(mode="json", exclude={"show_barcode_cta"}),
```

Esto evita que el campo efímero se persista en la DB.

- [ ] **Step 3: Agregar BackgroundTask helpers al final del archivo (antes de las rutas o al final)**

Agrega estas dos funciones privadas. Siguen el mismo patrón que `_run_off_contribution`:

```python
async def _run_enrich_task(
    barcode: str,
    resolved_json: list[dict],
    avg_confidence: float,
    source: str,
    settings,
) -> None:
    """BackgroundTask wrapper para enrich_product.

    Abre su propia sesión DB porque la sesión del request ya está cerrada.
    """
    from app.services.enrichment import enrich_product

    db = SessionLocal()
    try:
        resolved = [IngredientResult.model_validate(i) for i in resolved_json]
        await enrich_product(barcode, resolved, avg_confidence, source, db, settings)
    except Exception as exc:
        logger.error("Enrichment failed for %s: %s", barcode, exc)
    finally:
        db.close()


async def _run_off_lookup_task(
    name: str | None,
    brand: str | None,
    pseudo_barcode: str,
    settings,
) -> None:
    """BackgroundTask wrapper para try_off_lookup.

    Abre su propia sesión DB porque la sesión del request ya está cerrada.
    """
    from app.services.enrichment import try_off_lookup

    db = SessionLocal()
    try:
        await try_off_lookup(name, brand, pseudo_barcode, db, settings)
    except Exception as exc:
        logger.error("OFF lookup failed for %s: %s", pseudo_barcode, exc)
    finally:
        db.close()
```

- [ ] **Step 4: Actualizar `scan_barcode` para disparar BackgroundTask**

Agrega `background_tasks: BackgroundTasks` a la firma de `scan_barcode` (ya tiene `Request`, `BarcodeRequest`, etc.):

```python
@router.post("/barcode", response_model=ScanResponse)
@limiter.limit("20/minute")
async def scan_barcode(
    request: Request,
    body: BarcodeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
```

Después de `db.commit()` y antes de `return response`, agrega:

```python
    resolved: list[IngredientResult] = final_state.get("resolved") or []
    avg_conf = (
        sum(r.confidence_score for r in resolved) / len(resolved) if resolved else 0.0
    )
    if avg_conf >= 0.8:
        background_tasks.add_task(
            _run_enrich_task,
            barcode=body.barcode,
            resolved_json=[r.model_dump(mode="json") for r in resolved],
            avg_confidence=avg_conf,
            source="scan",
            settings=settings,
        )
```

- [ ] **Step 5: Verificar que el servidor arranca sin errores**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -c "from app.routers.scan import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add app/routers/scan.py
git commit -m "feat(scan): trigger product enrichment as BackgroundTask after barcode scan"
```

---

## Task 8: Scan Router — `scan_photo` update (Ex.1 + Ex.2 + CTA)

**Files:**
- Modify: `backend/app/routers/scan.py`

Actualiza `scan_photo` para las tres excepciones. Actualmente crea `pseudo_barcode` siempre — ahora chequea `final_state.get("extracted_barcode")` primero.

- [ ] **Step 1: Reemplazar el cuerpo de `scan_photo`**

Encuentra la función `scan_photo` (comienza en `@router.post("/photo", ...)`). Reemplázala completa:

```python
@router.post("/photo", response_model=ScanResponse)
@limiter.limit("20/minute")
async def scan_photo(
    request: Request,
    body: PhotoScanRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    graph = build_scan_graph(db, settings)
    final_state = await graph.ainvoke({"image_b64": body.image_base64, "user_id": current_user.id})

    if final_state.get("error"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=final_state["error"],
        )
    if not (final_state.get("extracted_ingredients") or []):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se pudo extraer lista de ingredientes de la imagen.",
        )

    # Ex.1: Gemini extrajo barcode de la imagen → usar barcode real
    extracted_barcode: str | None = final_state.get("extracted_barcode")
    barcode_to_use = extracted_barcode or f"photo-{uuid4().hex[:16]}"
    show_cta = not bool(extracted_barcode)

    product = _upsert_product(
        db,
        barcode=barcode_to_use,
        name=final_state.get("product_name"),
        brand=None,
        image_url=None,
    )
    if show_cta:
        product.needs_barcode_link = True

    response = _build_response(final_state, product.barcode, product.name)
    response.show_barcode_cta = show_cta
    _persist_scan_history(db, current_user, product.barcode, final_state, response)
    db.commit()

    resolved: list[IngredientResult] = final_state.get("resolved") or []
    avg_conf = (
        sum(r.confidence_score for r in resolved) / len(resolved) if resolved else 0.0
    )

    if extracted_barcode and avg_conf >= 0.8:
        # Ex.1: barcode real disponible → enriquecer directamente
        background_tasks.add_task(
            _run_enrich_task,
            barcode=extracted_barcode,
            resolved_json=[r.model_dump(mode="json") for r in resolved],
            avg_confidence=avg_conf,
            source="scan",
            settings=settings,
        )
    elif show_cta:
        # Ex.2: sin barcode → buscar en OFF por nombre+marca en background
        background_tasks.add_task(
            _run_off_lookup_task,
            name=final_state.get("product_name"),
            brand=final_state.get("product_brand"),
            pseudo_barcode=barcode_to_use,
            settings=settings,
        )

    return response
```

- [ ] **Step 2: Verificar importación**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -c "from app.routers.scan import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/routers/scan.py
git commit -m "feat(scan): photo scan exceptions 1+2 — barcode extraction and OFF lookup"
```

---

## Task 9: Scan Router — GET fix + `/link` endpoint

**Files:**
- Modify: `backend/app/routers/scan.py`

Dos cambios restantes: fix del GET para CTA dinámico, y nuevo endpoint `/link`.

- [ ] **Step 1: Fix `GET /scan/result/{barcode}` para CTA dinámico**

Encuentra la función `get_scan_result`. Actualmente retorna:
```python
return ScanResponse.model_validate(row.result_json)
```

Reemplázala con:

```python
@router.get("/result/{barcode}", response_model=ScanResponse)
def get_scan_result(
    barcode: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(ScanHistory)
        .where(
            ScanHistory.product_barcode == barcode,
            ScanHistory.user_id == current_user.id,
            ScanHistory.result_json.isnot(None),
        )
        .order_by(ScanHistory.scanned_at.desc())
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan no encontrado.")

    product = db.scalar(select(Product).where(Product.barcode == barcode))
    response = ScanResponse.model_validate(row.result_json)
    response.show_barcode_cta = product.needs_barcode_link if product else False
    return response
```

Agrega `Product` a los imports del router si aún no está:
```python
from app.models import OFFContribution, Product, ScanHistory, User
```

- [ ] **Step 2: Agregar endpoint `POST /scan/photo/{pseudo_barcode}/link`**

Agrega este endpoint al router (después del endpoint de contribute):

```python
# ─────────────────────────────────────────────
# POST /scan/photo/{pseudo_barcode}/link
# ─────────────────────────────────────────────


@router.post("/photo/{pseudo_barcode}/link", response_model=ScanResponse)
@limiter.limit("10/minute")
async def link_photo_barcode(
    request: Request,
    pseudo_barcode: str,
    body: LinkBarcodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Ex.4: el usuario provee manualmente el barcode del producto fotografiado."""
    from app.services.enrichment import link_photo_to_barcode as _link

    real_product = await _link(
        pseudo_barcode=pseudo_barcode,
        real_barcode=body.barcode,
        user_id=str(current_user.id),
        db=db,
        settings=settings,
    )

    history = db.scalar(
        select(ScanHistory)
        .where(
            ScanHistory.product_barcode == pseudo_barcode,
            ScanHistory.user_id == current_user.id,
        )
        .order_by(ScanHistory.scanned_at.desc())
    )
    if not history or not history.result_json:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan no encontrado.")

    response = ScanResponse.model_validate(history.result_json)
    response.product_barcode = real_product.barcode
    response.show_barcode_cta = False
    return response
```

- [ ] **Step 3: Verificar importación y router**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -c "from app.routers.scan import router; routes = [r.path for r in router.routes]; print([r for r in routes if 'link' in r])"
```

Expected: `['/photo/{pseudo_barcode}/link']`

- [ ] **Step 4: Ejecutar tests existentes para verificar no regressions**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -m pytest tests/ -v --ignore=tests/test_enrichment.py -x 2>&1 | tail -30
```

Expected: todos los tests previos siguen pasando.

- [ ] **Step 5: Commit**

```bash
git add app/routers/scan.py
git commit -m "feat(scan): add /link endpoint and fix dynamic show_barcode_cta on GET"
```

---

## Task 10: Fix `compute_clean_scores.py`

**Files:**
- Modify: `backend/scripts/compute_clean_scores.py`

El script tiene el bug: `ingredients: list[str] = []` hardcodeado. Ahora que `_compute_clean_score` vive en `enrichment.py`, el script pasa a ser un thin wrapper.

- [ ] **Step 1: Reemplazar el contenido completo del script**

```python
"""Compute and persist clean_score for all enriched products in DB.

clean_score = número de ingredientes con estatus Banned o Restricted.
Solo procesa productos que ya tienen ingredients_json poblado (enriquecidos
vía scan o importación). Productos sin ingredients_json se saltan.

Usage:
    cd backend && python -m scripts.compute_clean_scores
"""
import logging

from sqlalchemy import select

from app.models import Product
from app.models.base import SessionLocal
from app.services.enrichment import _compute_clean_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    db = SessionLocal()
    try:
        products = list(
            db.scalars(select(Product).where(Product.ingredients_json.isnot(None)))
        )
        logger.info("Computing clean_score for %d enriched products...", len(products))
        for product in products:
            product.clean_score = _compute_clean_score(product.ingredients_json or [], db)
        db.commit()
        logger.info("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verificar que importa**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -c "import scripts.compute_clean_scores; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/compute_clean_scores.py
git commit -m "fix(scripts): compute_clean_scores now reads ingredients_json from DB"
```

---

## Task 11: Frontend — `types.ts` + `scan.ts`

**Files:**
- Modify: `frontend/lib/api/types.ts`
- Modify: `frontend/lib/api/scan.ts`

- [ ] **Step 1: Agregar `show_barcode_cta` a `ScanResponse` en `types.ts`**

Busca `interface ScanResponse` (o `type ScanResponse`) en `frontend/lib/api/types.ts`. Agrega el campo al final:

```typescript
export interface ScanResponse {
  product_barcode: string;
  product_name: string | null;
  semaphore: SemaphoreColor;
  ingredients: IngredientResult[];
  conflict_severity: ConflictSeverity | null;
  source: string;
  scanned_at: string;
  personalized_insights: PersonalizedInsight[];
  show_barcode_cta: boolean;  // true en photo scans sin barcode resuelto
}
```

- [ ] **Step 2: Agregar `LinkBarcodeRequest` a `types.ts`**

Al final del archivo (o junto a otros request types):

```typescript
export interface LinkBarcodeRequest {
  barcode: string;
}
```

- [ ] **Step 3: Agregar `linkPhotoToBarcode` a `scan.ts`**

En `frontend/lib/api/scan.ts`, agrega después de las funciones existentes:

```typescript
export async function linkPhotoToBarcode(
  pseudoBarcode: string,
  barcode: string
): Promise<ScanResponse> {
  return apiFetch<ScanResponse>(`/scan/photo/${pseudoBarcode}/link`, {
    method: "POST",
    body: JSON.stringify({ barcode } satisfies LinkBarcodeRequest),
  });
}
```

Agrega `LinkBarcodeRequest` al import del tipo si es necesario.

- [ ] **Step 4: Verificar TypeScript**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/frontend
npx tsc --noEmit 2>&1 | grep -E "error TS|types.ts|scan.ts" | head -20
```

Expected: sin errores en los archivos modificados.

- [ ] **Step 5: Commit**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2
git add frontend/lib/api/types.ts frontend/lib/api/scan.ts
git commit -m "feat(frontend): add LinkBarcodeRequest type and linkPhotoToBarcode API"
```

---

## Task 12: Frontend — `LinkBarcodeCard` component en `scan/[id]/page.tsx`

**Files:**
- Modify: `frontend/app/(app)/scan/[id]/page.tsx`

El CTA se muestra cuando `data.show_barcode_cta === true` y `id.startsWith("photo-")`. Input siempre visible (sin click intermedio).

- [ ] **Step 1: Agregar imports necesarios en `page.tsx`**

Busca el bloque de imports en `frontend/app/(app)/scan/[id]/page.tsx`. Agrega `linkPhotoToBarcode` al import de scan API:

```typescript
import {
  getScanResult,
  scanBarcode,
  linkPhotoToBarcode,
} from "@/lib/api/scan";
```

Si `useState` no está importado desde React, agrégalo:

```typescript
import { useState } from "react";
```

- [ ] **Step 2: Agregar el componente `LinkBarcodeCard`**

Antes de la función `ScanResultInner` (o al final del archivo antes del export), agrega:

```tsx
function LinkBarcodeCard({ pseudoBarcode }: { pseudoBarcode: string }) {
  const router = useRouter();
  const [barcode, setBarcode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLink() {
    if (!/^\d{8,14}$/.test(barcode)) {
      setError("Código inválido — debe tener 8 a 14 dígitos");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await linkPhotoToBarcode(pseudoBarcode, barcode);
      router.push(`/scan/${result.product_barcode}`);
    } catch {
      setError("No pudimos linkear el producto. Intenta de nuevo.");
      setLoading(false);
    }
  }

  return (
    <div className="rounded-[14px] border border-[rgba(96,165,250,.2)] bg-[rgba(12,24,40,.5)] p-4 flex flex-col gap-3">
      <div className="flex items-start gap-2">
        <span className="text-[18px]">🔗</span>
        <div>
          <p className="text-[13px] font-semibold text-[#cbd5e1]">
            ¿Tienes el producto a la mano?
          </p>
          <p className="text-[11px] text-[#475569] mt-0.5">
            Escanea su código de barras para que BioShield lo recuerde
            y pueda sugerirte alternativas más limpias.
          </p>
        </div>
      </div>
      <input
        type="text"
        inputMode="numeric"
        pattern="\d*"
        placeholder="Ej. 7501030495584"
        value={barcode}
        onChange={(e) => setBarcode(e.target.value.replace(/\D/g, ""))}
        className="w-full px-3 py-2 rounded-lg bg-[#0f172a] border border-[#1e293b] text-[13px] text-[#f1f5f9] placeholder:text-[#334155] focus:outline-none focus:border-[#3b82f6]"
      />
      {error && <p className="text-[11px] text-[#f87171]">{error}</p>}
      <button
        onClick={handleLink}
        disabled={loading || barcode.length < 8}
        className="w-full py-2 rounded-lg bg-[#2563eb] text-white text-[13px] font-semibold disabled:opacity-40 hover:bg-[#1d4ed8] transition-colors"
      >
        {loading ? "Guardando..." : "Confirmar"}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Agregar el render condicional en `ScanResultInner`**

En `ScanResultInner`, dentro del JSX, busca el área donde se renderizan los cards (después del hero/semaphore card, antes del botón de alternativas). Agrega:

```tsx
{data.show_barcode_cta && id.startsWith("photo-") && (
  <LinkBarcodeCard pseudoBarcode={id} />
)}
```

- [ ] **Step 4: Verificar TypeScript**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/frontend
npx tsc --noEmit 2>&1 | grep "error TS" | head -20
```

Expected: sin errores nuevos.

- [ ] **Step 5: Commit**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2
git add frontend/app/\(app\)/scan/\[id\]/page.tsx
git commit -m "feat(ui): add LinkBarcodeCard CTA to photo scan result page"
```

---

## Task 13: Docs — `architecture.md`, `embedding-strategy.md`, `PRD.md`

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/embedding-strategy.md`
- Modify: `docs/PRD.md` (o `PRD.md` en la raíz)

- [ ] **Step 1: Agregar sección de Enrichment Pipeline en `architecture.md`**

Busca `docs/architecture.md`. Agrega una nueva sección (después de la sección de scan o después de ChromaDB, donde tenga sentido):

```markdown
## Enrichment Pipeline

El pipeline de enriquecimiento convierte cada scan exitoso en una contribución al curated DB.

**Trigger:** `POST /scan/barcode` y `POST /scan/photo` — disparan `BackgroundTask` después de `db.commit()`.

**Flujo:**
1. `_run_enrich_task` abre `SessionLocal()` propio (sesión del request ya cerrada).
2. `enrich_product()` aplica `SELECT FOR UPDATE` — first-write-wins, compatible SQLite + PostgreSQL.
3. Si `avg_confidence < 0.8`, la escritura se descarta.
4. Escribe `ingredients_json`, `ingredients_source`, `ingredients_confidence`, `clean_score` en `products`.
5. Si el producto tiene `category`, re-indexa en ChromaDB collection `products`.

**Photo scan — cascada de 3 excepciones:**
- **Ex.1:** Gemini extrae barcode EAN de la imagen → usa barcode real directamente.
- **Ex.2:** `_run_off_lookup_task` busca barcode por nombre+marca en OFF Search API → si encuentra, crea Product real y enriquece.
- **Ex.4:** CTA manual — `POST /scan/photo/{pseudo}/link` → `link_photo_to_barcode()` en `enrichment.py`.

**First-write-wins:** `product.ingredients_json IS NULL` verificado dentro del `SELECT FOR UPDATE`. Segunda escritura concurrente ve campo ya poblado y retorna sin modificar.

**Módulos clave:**
- `app/services/enrichment.py` — toda la lógica
- `app/services/off_client.py` — `off_lookup_barcode()` para Ex.2
- `app/routers/scan.py` — BackgroundTask wrappers `_run_enrich_task`, `_run_off_lookup_task`
- `scripts/compute_clean_scores.py` — thin wrapper que llama `_compute_clean_score` de `enrichment.py`
```

- [ ] **Step 2: Agregar nota flywheel en `embedding-strategy.md` §11**

En `docs/embedding-strategy.md`, busca la sección `## 11. Fase 2 — Collection products`. Al final de esa sección agrega:

```markdown
### Nota: Crecimiento automático vía flywheel de scans

A partir de la implementación del Enrichment Pipeline (Fase 2), la collection `products`
crece automáticamente con cada scan exitoso de barcode real (confianza ≥ 0.8).
Los scripts `compute_clean_scores.py` e `index_products_chroma.py` ahora complementan
el pipeline automático para re-scoring masivo o re-indexación inicial.

Los productos con `barcode LIKE 'photo-%'` nunca se indexan — solo se indexan productos
con barcode real y `category IS NOT NULL`.
```

- [ ] **Step 3: Mencionar enrichment en `PRD.md`**

Busca `PRD.md` (en la raíz del worktree o en `docs/`). En la sección de Fase 2, agrega:

```markdown
### Enrichment Pipeline (Fase 2.1)

Extensión del alternative matching: cada scan exitoso alimenta automáticamente
el curated DB sin intervención manual. Ver spec: `docs/superpowers/specs/2026-05-09-scan-enrichment-design.md`.
```

- [ ] **Step 4: Commit**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2
git add docs/architecture.md docs/embedding-strategy.md
# Agrega PRD.md si existe en este directorio:
git add PRD.md 2>/dev/null || git add docs/PRD.md 2>/dev/null || true
git commit -m "docs: document scan enrichment pipeline in architecture and embedding strategy"
```

---

## Task 14: Verificación final

- [ ] **Step 1: Ejecutar todos los tests del backend**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -m pytest tests/ -v 2>&1 | tail -40
```

Expected: todos los tests `PASSED`. Si hay failures, leerlos y corregir antes de continuar.

- [ ] **Step 2: Verificar TypeScript del frontend**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/frontend
npx tsc --noEmit 2>&1 | grep "error TS" | wc -l
```

Expected: `0`

- [ ] **Step 3: Verificar que el servidor FastAPI arranca**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -c "
from app.main import app
from app.routers.scan import router
routes = [r.path for r in router.routes]
print('Routes:', routes)
"
```

Expected: la lista incluye `/photo/{pseudo_barcode}/link` y `/result/{barcode}`.

- [ ] **Step 4: Verificar migración DB**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2/backend
python -m alembic current
```

Expected: HEAD en la migración de enrichment fields.

- [ ] **Step 5: Commit final si hay cambios sin commit**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2
git status
git log --oneline -10
```

---

## Notas de implementación

### Pattern BackgroundTask
El patrón `_run_enrich_task` / `_run_off_lookup_task` es idéntico a `_run_off_contribution` que ya existe en el codebase. Cada wrapper:
1. Abre `SessionLocal()` propio — la sesión del request está cerrada al momento de ejecutar.
2. Llama la función de servicio.
3. Cierra la sesión en `finally`.

### First-write-wins y concurrencia
`SELECT FOR UPDATE` sin `skip_locked` es compatible con SQLite (serializa writes). El segundo task concurrente espera, ve `should_enrich() = False` y sale. En PostgreSQL funciona igual.

### `show_barcode_cta` es efímero
- **Al guardar:** `response.model_dump(mode="json", exclude={"show_barcode_cta"})` — nunca se persiste.
- **Al leer:** `GET /scan/result/{barcode}` computa `show_barcode_cta = product.needs_barcode_link` dinámicamente.

### Gemini barcode extraction
`ProductExtraction.barcode` usa `str | None = None`. El campo es opcional — si Gemini no ve barcode legible, devuelve `null` y el pipeline sigue con pseudo_barcode normalmente.

### `_compute_clean_score` exportada como privada
La función tiene prefijo `_` pero es importada por `compute_clean_scores.py`. En Python, el prefijo `_` es convención, no enforcement — el import funciona. Si en el futuro quiere hacerse pública, renombrar a `compute_clean_score` (sin `_`).
