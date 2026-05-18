# Alternative Matching — Implementation Plan

> **Actualizado Fase 2.1:** El pipeline de ingesta es ahora multi-fuente (OFF MX + OFF Global + USDA). Script canónico: `load_all_products.py`. Ver `docs/superpowers/specs/2026-05-13-hybrid-ingestion-design.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dado un producto con semáforo YELLOW/ORANGE/RED, mostrar alternativas reales del mercado mexicano con ingredientes más limpios, priorizadas por compatibilidad con los biomarcadores del usuario.

**Architecture:** Hybrid matching engine — SQL first pass por categoría, ChromaDB re-rank por similitud semántica de ingredient profiles, biomarker filter rule-based. Endpoint `GET /scan/{barcode}/alternatives` sobre el router existente. Nueva ChromaDB collection `products` separada de `ingredients`.

**Tech Stack:** FastAPI · SQLAlchemy · Alembic · ChromaDB · BGE-M3 · Next.js · React Query · Playwright

**Branch:** `feat/fase2-alternative-matching` via git worktree — nunca directo en `main`

**Spec:** `docs/superpowers/specs/2026-05-08-alternative-matching-design.md`

---

## Task 1: Setup — worktree y branch

**Files:**
- No files — solo git

- [ ] **Step 1: Crear worktree en branch nueva**

```bash
git worktree add ../bio_shield_fase2 -b feat/fase2-alternative-matching
```

- [ ] **Step 2: Verificar**

```bash
git worktree list
```

Esperado: dos entradas — `bio_shield` (main) y `bio_shield_fase2` (feat/fase2-alternative-matching).

- [ ] **Step 3: Todo el trabajo restante ocurre en `../bio_shield_fase2`**

```bash
cd ../bio_shield_fase2
```

---

## Task 2: DB Migration — category, clean_score, analytics_events

**Files:**
- Create: `backend/alembic/versions/XXXX_add_category_clean_score_analytics.py`

- [ ] **Step 1: Generar archivo de migración**

```bash
cd backend
alembic revision --autogenerate -m "add_category_clean_score_analytics"
```

Toma nota del Revision ID generado (ej. `b2c3d4e5f678`).

- [ ] **Step 2: Reemplazar el contenido del archivo generado con**

```python
"""add_category_clean_score_analytics

Revision ID: <el_id_generado>
Revises: a3f7c2d1e845
Create Date: 2026-05-08 00:00:00.000000
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "<el_id_generado>"
down_revision: Union[str, None] = "a3f7c2d1e845"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(sa.Column("category", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("clean_score", sa.SmallInteger(), nullable=False, server_default="0"))

    op.create_index("idx_products_category", "products", ["category"])
    op.create_index("idx_products_clean_score", "products", ["clean_score"])

    op.create_table(
        "analytics_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_analytics_user", "analytics_events", ["user_id"])
    op.create_index("idx_analytics_event", "analytics_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("idx_analytics_event", table_name="analytics_events")
    op.drop_index("idx_analytics_user", table_name="analytics_events")
    op.drop_table("analytics_events")
    op.drop_index("idx_products_clean_score", table_name="products")
    op.drop_index("idx_products_category", table_name="products")
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_column("clean_score")
        batch_op.drop_column("category")
```

- [ ] **Step 3: Aplicar migración**

```bash
alembic upgrade head
```

Esperado: `Running upgrade a3f7c2d1e845 -> <id>, add_category_clean_score_analytics`

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(db): add category, clean_score to products; add analytics_events table"
```

---

## Task 3: ORM models — Product fields + AnalyticsEvent

**Files:**
- Modify: `backend/app/models/__init__.py` (o donde viva el ORM model de `Product`)
- Inspect first: `cat backend/app/models/__init__.py`

- [ ] **Step 1: Abrir `backend/app/models/__init__.py` y localizar la clase `Product`**

Busca el bloque `class Product(Base)`.

- [ ] **Step 2: Agregar los dos campos nuevos a la clase `Product`**

```python
# Agregar después de image_url:
category: Mapped[str | None] = mapped_column(String(100), nullable=True)
clean_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
```

Si el modelo usa `Column` en lugar de `Mapped`, usar:
```python
category = Column(String(100), nullable=True)
clean_score = Column(SmallInteger, nullable=False, default=0)
```

- [ ] **Step 3: Agregar clase `AnalyticsEvent` al final del archivo (antes de `__all__` si existe)**

```python
class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
```

Asegúrate de que `AnalyticsEvent` esté en el `__all__` si el archivo lo define.

- [ ] **Step 4: Verificar que los imports necesarios existen en el archivo**

`uuid4`, `datetime`, `UTC`, `String`, `SmallInteger`, `JSON`, `ForeignKey`, `DateTime` deben estar importados. Agrega los que falten.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/
git commit -m "feat(models): add Product.category, Product.clean_score, AnalyticsEvent ORM"
```

---

## Task 4: Pydantic schemas

**Files:**
- Modify: `backend/app/schemas/models.py`

- [ ] **Step 1: Agregar los nuevos schemas al final de `backend/app/schemas/models.py` (antes de `model_rebuild` si existe)**

```python
# ─────────────────────────────────────────────
# Alternatives schemas (Fase 2)
# ─────────────────────────────────────────────

class AlternativeProductOut(BaseModel):
    barcode: str
    name: str | None = None
    brand: str | None = None
    clean_score: int


class AlternativeTopPick(BaseModel):
    product: AlternativeProductOut
    clean_ingredients: list[str]
    biomarker_conflicts: list[str]
    compatibility_pct: int
    avatar_variant: str  # "blue" | "yellow" | "orange" | "red" | "gray"


class AlternativeItem(BaseModel):
    product: AlternativeProductOut
    avatar_variant: str
    semaphore_precomputed: SemaphoreColor


class ScannedProductSummary(BaseModel):
    barcode: str
    name: str | None = None
    semaphore: SemaphoreColor


class AlternativesResponse(BaseModel):
    scanned_product: ScannedProductSummary
    top_pick: AlternativeTopPick | None
    alternatives: list[AlternativeItem]
    has_biomarkers: bool
    fallback_used: bool


# ─────────────────────────────────────────────
# Analytics schemas (Fase 2)
# ─────────────────────────────────────────────

class AnalyticsEventIn(BaseModel):
    event_type: Literal["alt_button_shown", "alt_page_opened", "alt_tapped"]
    payload: dict = {}
```

- [ ] **Step 2: Asegurar que `Literal` está importado**

```python
from typing import Literal  # ya debe existir en el archivo
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/models.py
git commit -m "feat(schemas): add AlternativesResponse, AlternativeTopPick, AnalyticsEventIn"
```

---

## Task 5: ChromaDB — products collection

**Files:**
- Modify: `backend/app/services/rag.py`

- [ ] **Step 1: Leer `backend/app/services/rag.py` para ver cómo está definido `get_collection`**

```bash
cat backend/app/services/rag.py
```

- [ ] **Step 2: Agregar función `get_products_collection` usando el mismo patrón que `get_collection`**

```python
def get_products_collection(settings: Settings):
    """Returns (or creates) the ChromaDB collection for curated product profiles.

    Separate from the 'ingredients' collection — stores product-level
    ingredient profile embeddings for alternative matching (Fase 2).
    """
    client = _get_client(settings)
    return client.get_or_create_collection(
        name="products",
        metadata={"hnsw:space": "cosine"},
    )
```

Si `rag.py` usa un patrón diferente (ej. `chromadb.Client().get_collection(...)`), replicar ese patrón exacto.

- [ ] **Step 3: Exportar la función — agregar al `__all__` de `rag.py` si existe, o simplemente dejarla pública**

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/rag.py
git commit -m "feat(rag): add get_products_collection for Fase 2 alternative matching"
```

---

## Task 6: Alternatives engine service

**Files:**
- Create: `backend/app/services/alternatives.py`

- [ ] **Step 1: Escribir el failing test primero (ver Task 7)**

Saltar a Task 7 para escribir el test, luego volver aquí a implementar.

- [ ] **Step 2: Implementar `backend/app/services/alternatives.py`**

```python
"""Alternative matching engine — Fase 2.

Hybrid C: SQL first pass (category) → ChromaDB re-rank → biomarker filter.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Product, ScanHistory
from app.schemas.models import (
    AlternativeItem,
    AlternativeProductOut,
    AlternativesResponse,
    AlternativeTopPick,
    ScannedProductSummary,
    SemaphoreColor,
)
from app.services.embeddings import embed_text
from app.services.rag import get_products_collection

logger = logging.getLogger(__name__)

_SEMAPHORE_FROM_SCORE = {0: "BLUE", 1: "YELLOW", 2: "YELLOW", 3: "ORANGE"}
_AVATAR_FROM_SEMAPHORE = {
    "BLUE": "blue",
    "YELLOW": "yellow",
    "ORANGE": "orange",
    "RED": "red",
    "GRAY": "gray",
}

# Biomarker rules keywords (subset — enough for MVP filter)
_BIOMARKER_FLAG_KEYWORDS: dict[str, list[str]] = {
    "ldl": ["trans fat", "hydrogenated", "palm oil", "saturated fat"],
    "glucose": ["sugar", "sucrose", "high fructose", "dextrose", "maltose"],
    "sodium": ["sodium", "salt", "monosodium"],
    "triglycerides": ["sugar", "fructose", "alcohol"],
}


def _semaphore_from_clean_score(score: int) -> str:
    if score == 0:
        return "BLUE"
    if score <= 2:
        return "YELLOW"
    if score <= 4:
        return "ORANGE"
    return "RED"


def _avatar_from_semaphore(sem: str) -> str:
    return _AVATAR_FROM_SEMAPHORE.get(sem, "gray")


def _compatibility_pct(clean_score: int, max_score: int, n_conflicts: int) -> int:
    if max_score == 0:
        base = 100.0
    else:
        base = (1 - clean_score / max_score) * 100
    return max(0, round(base - n_conflicts * 10))


def _biomarker_conflicts(
    product_ingredients: list[str],
    active_biomarkers: list[str],
) -> list[str]:
    """Return list of human-readable conflict strings for the product."""
    conflicts: list[str] = []
    ingredients_lower = [i.lower() for i in product_ingredients]
    for biomarker in active_biomarkers:
        keywords = _BIOMARKER_FLAG_KEYWORDS.get(biomarker, [])
        for kw in keywords:
            if any(kw in ing for ing in ingredients_lower):
                conflicts.append(f"{biomarker.upper()} · contiene {kw}")
    return conflicts


def _clean_ingredient_labels(all_ingredients: list[str], flagged: list[str]) -> list[str]:
    """Return up to 3 'sin X' labels for ingredients NOT in flagged list."""
    flagged_lower = [f.lower() for f in flagged]
    labels: list[str] = []
    for ing in all_ingredients:
        if ing.lower() not in flagged_lower and len(labels) < 3:
            labels.append(f"Sin {ing.lower()}")
    return labels or ["Ingredientes más limpios"]


async def find_alternatives(
    barcode: str,
    db: Session,
    settings: Settings,
    active_biomarkers: list[str],
    has_biomarkers: bool,
) -> AlternativesResponse | None:
    """Main entrypoint. Returns None if scan not found."""

    # ── 1. Load scan result_json ──────────────────────────────────────────
    scan_row = db.scalar(
        select(ScanHistory)
        .where(
            ScanHistory.product_barcode == barcode,
            ScanHistory.result_json.isnot(None),
        )
        .order_by(ScanHistory.scanned_at.desc())
    )
    if scan_row is None:
        return None

    result = scan_row.result_json  # dict
    scanned_semaphore = result.get("semaphore", "GRAY")
    product_name = result.get("product_name")
    all_ingredients: list[str] = [i["name"] for i in result.get("ingredients", [])]
    flagged_ingredients: list[str] = [
        i["name"] for i in result.get("ingredients", []) if i.get("conflicts")
    ]

    # ── 2. Load scanned product to get category + clean_score ─────────────
    scanned_product = db.scalar(select(Product).where(Product.barcode == barcode))
    category = scanned_product.category if scanned_product else None
    scanned_clean_score = scanned_product.clean_score if scanned_product else 0

    fallback_used = category is None

    # ── 3. SQL first pass ─────────────────────────────────────────────────
    if not fallback_used:
        candidates = list(
            db.scalars(
                select(Product)
                .where(
                    Product.category == category,
                    Product.barcode != barcode,
                    Product.clean_score < scanned_clean_score,
                )
                .order_by(Product.clean_score.asc())
                .limit(20)
            )
        )
    else:
        candidates = []

    # ── 4. ChromaDB re-rank ───────────────────────────────────────────────
    reranked: list[Product] = candidates  # default: keep SQL order

    if flagged_ingredients:
        query_text = (
            f"categoría: {category or 'alimento'} "
            f"sin {' sin '.join(flagged_ingredients[:5])}"
        )
        try:
            embedding = await embed_text(query_text, settings)
            collection = get_products_collection(settings)
            candidate_barcodes = [c.barcode for c in candidates] or None
            where_filter = (
                {"barcode": {"$in": candidate_barcodes}} if candidate_barcodes else None
            )
            results = collection.query(
                query_embeddings=[embedding],
                n_results=min(5, max(1, len(candidates))),
                where=where_filter,
                include=["metadatas", "distances"],
            )
            ranked_barcodes: list[str] = [
                m["barcode"] for m in (results["metadatas"][0] if results["metadatas"] else [])
            ]
            barcode_to_product = {c.barcode: c for c in candidates}
            reranked = [barcode_to_product[b] for b in ranked_barcodes if b in barcode_to_product]
            # Append any candidates not returned by ChromaDB
            seen = set(ranked_barcodes)
            reranked += [c for c in candidates if c.barcode not in seen]
        except Exception as exc:
            logger.warning("ChromaDB re-rank failed, using SQL order: %s", exc)

    top5 = reranked[:5]

    # ── 5. Biomarker filter — top pick selection ──────────────────────────
    max_score_in_category = max((c.clean_score for c in top5), default=1) or 1
    top_pick: AlternativeTopPick | None = None

    for candidate in top5:
        cand_ingredients = [candidate.name or ""]  # simplified — real impl reads result_json
        conflicts = _biomarker_conflicts(cand_ingredients, active_biomarkers)
        if not conflicts or not has_biomarkers:
            semaphore = _semaphore_from_clean_score(candidate.clean_score)
            clean_labels = _clean_ingredient_labels(all_ingredients, flagged_ingredients)
            top_pick = AlternativeTopPick(
                product=AlternativeProductOut(
                    barcode=candidate.barcode,
                    name=candidate.name,
                    brand=candidate.brand,
                    clean_score=candidate.clean_score,
                ),
                clean_ingredients=clean_labels,
                biomarker_conflicts=conflicts,
                compatibility_pct=_compatibility_pct(
                    candidate.clean_score, max_score_in_category, len(conflicts)
                ),
                avatar_variant=_avatar_from_semaphore(semaphore),
            )
            top5 = [c for c in top5 if c.barcode != candidate.barcode]
            break

    # ── 6. Build secondary list ───────────────────────────────────────────
    alternatives: list[AlternativeItem] = []
    for candidate in top5[:4]:
        sem = _semaphore_from_clean_score(candidate.clean_score)
        alternatives.append(
            AlternativeItem(
                product=AlternativeProductOut(
                    barcode=candidate.barcode,
                    name=candidate.name,
                    brand=candidate.brand,
                    clean_score=candidate.clean_score,
                ),
                avatar_variant=_avatar_from_semaphore(sem),
                semaphore_precomputed=SemaphoreColor(sem),
            )
        )

    return AlternativesResponse(
        scanned_product=ScannedProductSummary(
            barcode=barcode,
            name=product_name,
            semaphore=SemaphoreColor(scanned_semaphore),
        ),
        top_pick=top_pick,
        alternatives=alternatives,
        has_biomarkers=has_biomarkers,
        fallback_used=fallback_used,
    )
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/alternatives.py
git commit -m "feat(alternatives): implement hybrid matching engine — SQL + ChromaDB + biomarker filter"
```

---

## Task 7: Unit tests — alternatives engine

**Files:**
- Create: `backend/tests/test_alternatives.py`

- [ ] **Step 1: Escribir los tests**

```python
"""Unit tests for the alternative matching engine.

Patches ChromaDB and embed_text so tests run offline.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import Product, ScanHistory
from app.services.alternatives import (
    _biomarker_conflicts,
    _clean_ingredient_labels,
    _compatibility_pct,
    _semaphore_from_clean_score,
    find_alternatives,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_product(db, barcode: str, name: str, category: str | None, clean_score: int) -> Product:
    p = Product(barcode=barcode, name=name, brand="TestBrand", category=category, clean_score=clean_score)
    db.add(p)
    db.flush()
    return p


def _make_scan(db, barcode: str, semaphore: str, ingredients: list[str], flagged: list[str]) -> ScanHistory:
    result_json = {
        "product_barcode": barcode,
        "semaphore": semaphore,
        "product_name": f"Product {barcode}",
        "ingredients": [
            {"name": i, "conflicts": [{"conflict_type": "REGULATORY"}] if i in flagged else []}
            for i in ingredients
        ],
        "conflict_severity": None,
        "source": "barcode",
        "scanned_at": "2026-05-08T00:00:00",
        "personalized_insights": [],
    }
    from datetime import datetime, UTC
    s = ScanHistory(
        product_barcode=barcode,
        user_id="test-user-id",
        semaphore_result=semaphore,
        result_json=result_json,
        scanned_at=datetime.now(UTC),
    )
    db.add(s)
    db.flush()
    return s


# ── pure function tests (no DB needed) ───────────────────────────────────────

def test_semaphore_from_clean_score():
    assert _semaphore_from_clean_score(0) == "BLUE"
    assert _semaphore_from_clean_score(1) == "YELLOW"
    assert _semaphore_from_clean_score(2) == "YELLOW"
    assert _semaphore_from_clean_score(3) == "ORANGE"
    assert _semaphore_from_clean_score(5) == "RED"


def test_compatibility_pct_perfect():
    assert _compatibility_pct(0, 4, 0) == 100


def test_compatibility_pct_partial():
    assert _compatibility_pct(2, 4, 0) == 50


def test_compatibility_pct_with_conflicts():
    assert _compatibility_pct(0, 4, 1) == 90


def test_compatibility_pct_never_negative():
    assert _compatibility_pct(4, 4, 5) == 0


def test_biomarker_conflicts_detects_sugar():
    conflicts = _biomarker_conflicts(["sugar", "water", "salt"], ["glucose"])
    assert any("glucose" in c.lower() for c in conflicts)


def test_biomarker_conflicts_no_match():
    conflicts = _biomarker_conflicts(["water", "pectina"], ["ldl"])
    assert conflicts == []


def test_clean_ingredient_labels():
    labels = _clean_ingredient_labels(["water", "salt", "sugar"], ["sugar"])
    assert "Sin water" in labels or "Sin salt" in labels
    assert not any("sugar" in l.lower() for l in labels)


# ── integration tests (with DB) ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_alternatives_sql_first_pass(db_session):
    """SQL first pass returns products with lower clean_score in same category."""
    _make_product(db_session, "BAD001", "Bad Yogurt", "yogurts", clean_score=3)
    _make_scan(db_session, "BAD001", "RED", ["sugar", "colorante E129", "leche"], ["sugar", "colorante E129"])
    _make_product(db_session, "GOOD001", "Good Yogurt", "yogurts", clean_score=0)
    _make_product(db_session, "GOOD002", "Ok Yogurt", "yogurts", clean_score=1)
    _make_product(db_session, "DIFF001", "Other Category", "snacks", clean_score=0)

    from app.config import Settings
    settings = Settings(
        database_url="sqlite:///:memory:",
        jwt_secret="x" * 32,
        aes_key="x" * 32,
        gemini_api_key="test",
        chroma_persist_directory="",
    )

    with patch("app.services.alternatives.embed_text", new_callable=AsyncMock) as mock_embed, \
         patch("app.services.alternatives.get_products_collection") as mock_coll:
        mock_embed.return_value = [0.1] * 1024
        mock_coll.return_value.query.return_value = {
            "metadatas": [[{"barcode": "GOOD001"}, {"barcode": "GOOD002"}]],
            "distances": [[0.1, 0.2]],
        }

        result = await find_alternatives(
            barcode="BAD001",
            db=db_session,
            settings=settings,
            active_biomarkers=[],
            has_biomarkers=False,
        )

    assert result is not None
    all_barcodes = [result.top_pick.product.barcode] + [a.product.barcode for a in result.alternatives]
    assert "GOOD001" in all_barcodes
    assert "DIFF001" not in all_barcodes  # different category


@pytest.mark.asyncio
async def test_find_alternatives_fallback_when_no_category(db_session):
    """fallback_used=True when scanned product has no category."""
    _make_product(db_session, "NOCAT001", "No Category Product", None, clean_score=3)
    _make_scan(db_session, "NOCAT001", "RED", ["sugar"], ["sugar"])

    from app.config import Settings
    settings = Settings(
        database_url="sqlite:///:memory:",
        jwt_secret="x" * 32,
        aes_key="x" * 32,
        gemini_api_key="test",
        chroma_persist_directory="",
    )

    with patch("app.services.alternatives.embed_text", new_callable=AsyncMock), \
         patch("app.services.alternatives.get_products_collection") as mock_coll:
        mock_coll.return_value.query.return_value = {"metadatas": [[]], "distances": [[]]}

        result = await find_alternatives(
            barcode="NOCAT001",
            db=db_session,
            settings=settings,
            active_biomarkers=[],
            has_biomarkers=False,
        )

    assert result is not None
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_find_alternatives_returns_none_when_scan_not_found(db_session):
    from app.config import Settings
    settings = Settings(
        database_url="sqlite:///:memory:",
        jwt_secret="x" * 32,
        aes_key="x" * 32,
        gemini_api_key="test",
        chroma_persist_directory="",
    )
    result = await find_alternatives(
        barcode="NONEXISTENT",
        db=db_session,
        settings=settings,
        active_biomarkers=[],
        has_biomarkers=False,
    )
    assert result is None


@pytest.mark.asyncio
async def test_find_alternatives_chroma_failure_degrades_gracefully(db_session):
    """ChromaDB failure → uses SQL order, doesn't crash."""
    _make_product(db_session, "BAD002", "Bad Product", "bebidas", clean_score=4)
    _make_scan(db_session, "BAD002", "RED", ["sugar"], ["sugar"])
    _make_product(db_session, "GOOD003", "Good Drink", "bebidas", clean_score=0)

    from app.config import Settings
    settings = Settings(
        database_url="sqlite:///:memory:",
        jwt_secret="x" * 32,
        aes_key="x" * 32,
        gemini_api_key="test",
        chroma_persist_directory="",
    )

    with patch("app.services.alternatives.embed_text", side_effect=Exception("chroma down")):
        result = await find_alternatives(
            barcode="BAD002",
            db=db_session,
            settings=settings,
            active_biomarkers=[],
            has_biomarkers=False,
        )

    assert result is not None
    assert result.top_pick is not None or len(result.alternatives) >= 0
```

- [ ] **Step 2: Correr tests — deben fallar porque el servicio no existe aún**

```bash
cd backend
pytest tests/test_alternatives.py -v
```

Esperado: `ImportError` o `ModuleNotFoundError` en `app.services.alternatives`.

- [ ] **Step 3: Implementar el servicio (Task 6) y correr de nuevo**

```bash
pytest tests/test_alternatives.py -v
```

Esperado: todos los tests pasan.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_alternatives.py
git commit -m "test(alternatives): unit tests for matching engine — SQL, ChromaDB, biomarker filter, fallback"
```

---

## Task 8: Scan router — GET /scan/{barcode}/alternatives

**Files:**
- Modify: `backend/app/routers/scan.py`

- [ ] **Step 1: Agregar el endpoint al final de `backend/app/routers/scan.py` (antes del helper section si existe)**

```python
@router.get("/alternatives/{barcode}", response_model=AlternativesResponse)
@limiter.limit("10/minute")
async def get_alternatives(
    request: Request,
    barcode: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Return ingredient-based alternatives for a scanned product (Fase 2).

    Only meaningful when semaphore is YELLOW, ORANGE or RED — frontend enforces
    this via conditional button, but endpoint works for any barcode.
    """
    from app.services.biosync import get_active_biomarker_names  # noqa: PLC0415
    from app.services.alternatives import find_alternatives  # noqa: PLC0415

    has_biomarkers, active_biomarkers = await get_active_biomarker_names(current_user.id, db, settings)

    result = await find_alternatives(
        barcode=barcode,
        db=db,
        settings=settings,
        active_biomarkers=active_biomarkers,
        has_biomarkers=has_biomarkers,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan no encontrado.")
    return result
```

- [ ] **Step 2: Agregar `AlternativesResponse` a los imports de schemas en `scan.py`**

```python
from app.schemas.models import (
    AlternativesResponse,   # agregar esta línea
    BarcodeRequest,
    ...
)
```

- [ ] **Step 3: Verificar que `get_active_biomarker_names` existe en `biosync` service**

```bash
grep -n "get_active_biomarker_names\|active_biomarker" backend/app/services/*.py backend/app/routers/biosync.py
```

Si la función no existe, crear una helper simple en `backend/app/services/alternatives.py`:

```python
async def _get_active_biomarkers(user_id: str, db: Session, settings: Settings) -> tuple[bool, list[str]]:
    """Returns (has_biomarkers, list_of_biomarker_canonical_names)."""
    from app.services.crypto import decrypt_biomarkers  # noqa: PLC0415
    from app.models import Biomarker  # noqa: PLC0415
    from datetime import datetime, UTC  # noqa: PLC0415

    row = db.scalar(
        select(Biomarker)
        .where(Biomarker.user_id == user_id, Biomarker.expires_at > datetime.now(UTC))
        .order_by(Biomarker.uploaded_at.desc())
    )
    if row is None:
        return False, []
    try:
        data = decrypt_biomarkers(row.encrypted_data, row.encryption_iv, settings)
        biomarkers = data.get("biomarkers", [])
        active = [b["name"] for b in biomarkers if b.get("classification") in ("high", "low")]
        return True, active
    except Exception:
        return True, []
```

Y en el router usar `_get_active_biomarkers` en lugar de `get_active_biomarker_names`.

- [ ] **Step 4: Correr tests existentes para verificar que no se rompió nada**

```bash
cd backend && pytest tests/test_scan.py -v
```

Esperado: todos los tests existentes pasan.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/scan.py
git commit -m "feat(scan): add GET /scan/alternatives/{barcode} endpoint (Fase 2)"
```

---

## Task 9: Analytics router

**Files:**
- Create: `backend/app/routers/analytics.py`

- [ ] **Step 1: Crear `backend/app/routers/analytics.py`**

```python
"""Analytics event ingestion — fire-and-forget (Fase 2).

Records user interactions with the alternatives feature.
Endpoint is intentionally permissive: errors are swallowed to never block the UI.
"""
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.middleware.auth import get_current_user
from app.models import User
from app.models.base import get_db
from app.models import AnalyticsEvent
from app.schemas.models import AnalyticsEventIn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", dependencies=[Depends(get_current_user)])


@router.post("/event", status_code=status.HTTP_202_ACCEPTED)
def record_event(
    body: AnalyticsEventIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        db.add(
            AnalyticsEvent(
                id=str(uuid4()),
                user_id=str(current_user.id),
                event_type=body.event_type,
                payload=body.payload,
            )
        )
        db.commit()
    except Exception as exc:
        logger.warning("Analytics event failed silently: %s", exc)
    return JSONResponse(status_code=202, content={"status": "accepted"})
```

- [ ] **Step 2: Registrar el router en `backend/app/main.py`**

```python
from app.routers import analytics  # agregar este import

# En la sección donde se incluyen los routers (app.include_router):
app.include_router(analytics.router, tags=["analytics"])
```

- [ ] **Step 3: Verificar que el server arranca**

```bash
cd backend && python -m uvicorn app.main:app --reload --port 8001
```

Esperado: `Application startup complete.` sin errores.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/analytics.py backend/app/main.py
git commit -m "feat(analytics): add POST /analytics/event fire-and-forget endpoint (Fase 2)"
```

---

## Task 10: Curation scripts

**Files:**
- Create: `backend/scripts/compute_clean_scores.py`
- Create: `backend/scripts/index_products_chroma.py`
- Create: `backend/scripts/seed_alternatives_fixture.py`

- [ ] **Step 1: Crear `backend/scripts/compute_clean_scores.py`**

```python
"""Compute and persist clean_score for all products in DB.

clean_score = number of flagged ingredients detected via regulatory_status.
Lower = cleaner. Run after loading the curated product dataset.

Usage: python -m scripts.compute_clean_scores
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from app.models.base import SessionLocal
from app.models import Product, Ingredient, RegulatoryStatus

_BANNED_STATUSES = {"Banned", "Restricted"}

def compute_clean_score(product_ingredients: list[str], db) -> int:
    score = 0
    for ing_name in product_ingredients:
        ing = db.scalar(
            select(Ingredient).where(Ingredient.canonical_name.ilike(ing_name))
        )
        if ing is None:
            continue
        statuses = list(db.scalars(
            select(RegulatoryStatus).where(RegulatoryStatus.ingredient_id == ing.id)
        ))
        if any(s.status in _BANNED_STATUSES for s in statuses):
            score += 1
    return score


def main():
    db = SessionLocal()
    try:
        products = list(db.scalars(select(Product)))
        print(f"Computing clean_score for {len(products)} products...")
        for product in products:
            # Ingredient names stored in product.result_json or a product_ingredients table
            # For curated products, parse from a CSV field or dedicated table
            # Placeholder: if product has no ingredients list, score = 0
            ingredients: list[str] = []  # TODO: populate from your curation data source
            product.clean_score = compute_clean_score(ingredients, db)
        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Crear `backend/scripts/index_products_chroma.py`**

```python
"""Index curated products into ChromaDB 'products' collection.

Generates ingredient profile text per product and embeds with BGE-M3.
Run after compute_clean_scores.py.

Usage: python -m scripts.index_products_chroma
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
from sqlalchemy import select
from app.config import get_settings
from app.models.base import SessionLocal
from app.models import Product
from app.services.embeddings import embed_text
from app.services.rag import get_products_collection


def _build_profile(product: Product) -> str:
    return (
        f"nombre: {product.name or 'desconocido'} | "
        f"marca: {product.brand or 'desconocida'} | "
        f"categoría: {product.category or 'sin categoría'} | "
        f"clean_score: {product.clean_score}"
    )


async def main():
    settings = get_settings()
    db = SessionLocal()
    collection = get_products_collection(settings)

    try:
        products = list(db.scalars(select(Product).where(Product.category.isnot(None))))
        print(f"Indexing {len(products)} products into ChromaDB 'products' collection...")

        for i, product in enumerate(products):
            profile = _build_profile(product)
            embedding = await embed_text(profile, settings)
            semaphore = "BLUE" if product.clean_score == 0 else "YELLOW" if product.clean_score <= 2 else "ORANGE"
            collection.upsert(
                ids=[product.barcode],
                documents=[profile],
                embeddings=[embedding],
                metadatas=[{
                    "barcode": product.barcode,
                    "category": product.category or "",
                    "clean_score": product.clean_score,
                    "semaphore_precomputed": semaphore,
                }],
            )
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(products)} indexed...")

        print(f"Done. {len(products)} products indexed.")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Crear `backend/scripts/seed_alternatives_fixture.py`**

```python
"""Seed 10 curated products for E2E test fixtures.

Inserts products into DB and ChromaDB. Safe to run multiple times (upsert).

Usage: python -m scripts.seed_alternatives_fixture
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
from app.config import get_settings
from app.models.base import SessionLocal
from app.models import Product
from app.services.embeddings import embed_text
from app.services.rag import get_products_collection

FIXTURE_PRODUCTS = [
    {"barcode": "FIX_YOGURT_001", "name": "Activia Natural", "brand": "Danone", "category": "yogurts", "clean_score": 0},
    {"barcode": "FIX_YOGURT_002", "name": "Lala Bio 100", "brand": "Lala", "category": "yogurts", "clean_score": 1},
    {"barcode": "FIX_YOGURT_003", "name": "Alpura Fit", "brand": "Alpura", "category": "yogurts", "clean_score": 2},
    {"barcode": "FIX_YOGURT_BAD", "name": "Yogurt con Sucralosa", "brand": "Generic", "category": "yogurts", "clean_score": 4},
    {"barcode": "FIX_DRINK_001", "name": "Agua Mineral Topo Chico", "brand": "Topo Chico", "category": "bebidas", "clean_score": 0},
    {"barcode": "FIX_DRINK_002", "name": "Nestea Limón", "brand": "Nestlé", "category": "bebidas", "clean_score": 3},
    {"barcode": "FIX_SNACK_001", "name": "Avena Natural", "brand": "Quaker", "category": "cereales", "clean_score": 0},
    {"barcode": "FIX_SNACK_002", "name": "Granola Orgánica", "brand": "Eden", "category": "cereales", "clean_score": 0},
    {"barcode": "FIX_SNACK_BAD", "name": "Cereal Azucarado", "brand": "Generic", "category": "cereales", "clean_score": 5},
    {"barcode": "FIX_NOCAT_001", "name": "Producto Sin Categoría", "brand": "Generic", "category": None, "clean_score": 3},
]


async def main():
    settings = get_settings()
    db = SessionLocal()
    collection = get_products_collection(settings)

    try:
        for p in FIXTURE_PRODUCTS:
            existing = db.get(Product, p["barcode"])
            if existing:
                existing.name = p["name"]
                existing.brand = p["brand"]
                existing.category = p["category"]
                existing.clean_score = p["clean_score"]
            else:
                db.add(Product(**p, image_url=None))

            if p["category"]:
                profile = f"nombre: {p['name']} | marca: {p['brand']} | categoría: {p['category']}"
                embedding = await embed_text(profile, settings)
                sem = "BLUE" if p["clean_score"] == 0 else "YELLOW" if p["clean_score"] <= 2 else "ORANGE"
                collection.upsert(
                    ids=[p["barcode"]],
                    documents=[profile],
                    embeddings=[embedding],
                    metadatas=[{"barcode": p["barcode"], "category": p["category"],
                                "clean_score": p["clean_score"], "semaphore_precomputed": sem}],
                )

        db.commit()
        print(f"Seeded {len(FIXTURE_PRODUCTS)} fixture products.")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/compute_clean_scores.py backend/scripts/index_products_chroma.py backend/scripts/seed_alternatives_fixture.py
git commit -m "feat(scripts): curation pipeline — compute_clean_scores, index_products_chroma, seed_alternatives_fixture"
```

---

## Task 11: Frontend types

**Files:**
- Modify: `frontend/lib/api/types.ts`

- [ ] **Step 1: Agregar al final de `frontend/lib/api/types.ts` (antes del cierre del archivo)**

```ts
// ── Alternatives (Fase 2) ─────────────────────────────────────────────────

export interface AlternativeProductOut {
  barcode: string;
  name: string | null;
  brand: string | null;
  clean_score: number;
}

export interface AlternativeTopPick {
  product: AlternativeProductOut;
  clean_ingredients: string[];
  biomarker_conflicts: string[];
  compatibility_pct: number;
  avatar_variant: AvatarVariant;
}

export interface AlternativeItem {
  product: AlternativeProductOut;
  avatar_variant: AvatarVariant;
  semaphore_precomputed: SemaphoreColor;
}

export interface ScannedProductSummary {
  barcode: string;
  name: string | null;
  semaphore: SemaphoreColor;
}

export interface AlternativesResponse {
  scanned_product: ScannedProductSummary;
  top_pick: AlternativeTopPick | null;
  alternatives: AlternativeItem[];
  has_biomarkers: boolean;
  fallback_used: boolean;
}

// ── Analytics (Fase 2) ────────────────────────────────────────────────────

export type AnalyticsEventType = "alt_button_shown" | "alt_page_opened" | "alt_tapped";

export interface AnalyticsEventIn {
  event_type: AnalyticsEventType;
  payload?: Record<string, unknown>;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/types.ts
git commit -m "feat(types): add AlternativesResponse, AlternativeTopPick, AnalyticsEventIn"
```

---

## Task 12: Frontend API functions

**Files:**
- Modify: `frontend/lib/api/scan.ts`

- [ ] **Step 1: Agregar al final de `frontend/lib/api/scan.ts`**

```ts
import type {
  // agregar a los imports existentes:
  AlternativesResponse,
} from "./types";

export async function getAlternatives(barcode: string): Promise<AlternativesResponse> {
  return apiFetch<AlternativesResponse>(`/scan/alternatives/${barcode}`);
}
```

- [ ] **Step 2: Crear `frontend/lib/api/analytics.ts`**

```ts
import { apiFetch } from "./client";
import type { AnalyticsEventIn } from "./types";

export async function recordAnalyticsEvent(body: AnalyticsEventIn): Promise<void> {
  try {
    await apiFetch<void>("/analytics/event", {
      method: "POST",
      body: JSON.stringify(body),
    });
  } catch {
    // fire-and-forget — never throw
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/scan.ts frontend/lib/api/analytics.ts
git commit -m "feat(api): add getAlternatives, recordAnalyticsEvent client functions"
```

---

## Task 13: ALTERNATIVES_PHASES constant

**Files:**
- Modify: `frontend/components/AILoadingState.tsx`

- [ ] **Step 1: Agregar `ALTERNATIVES_PHASES` después de `BIOSYNC_PHASES` en `AILoadingState.tsx`**

```ts
export const ALTERNATIVES_PHASES: AILoadingPhase[] = [
  {
    label: "ANALYZING_CATEGORY",
    detail: "Identificando categoría del producto escaneado",
    nodeIndex: 0,
    completesAt: 800,
  },
  {
    label: "SEARCHING_ALTERNATIVES",
    detail: "Buscando alternativas más limpias en nuestra base de datos",
    nodeIndex: 1,
    completesAt: 2000,
  },
  {
    label: "CHECKING_BIOMARKERS",
    detail: "Cruzando con tus biomarcadores · priorizando compatibilidad personal",
    nodeIndex: 2,
    completesAt: Infinity,
  },
];
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/AILoadingState.tsx
git commit -m "feat(ui): add ALTERNATIVES_PHASES constant for alternatives loading state"
```

---

## Task 14: AlternativeTopPick component

**Files:**
- Create: `frontend/components/AlternativeTopPick.tsx`

- [ ] **Step 1: Crear el componente**

```tsx
"use client";

import Link from "next/link";
import { AvatarGlow } from "@/components/AvatarGlow";
import type { AlternativeTopPick as TopPickData } from "@/lib/api/types";
import type { AvatarVariant } from "@/lib/api/types";

interface AlternativeTopPickProps {
  data: TopPickData;
  hasBiomarkers: boolean;
}

export function AlternativeTopPick({ data, hasBiomarkers }: AlternativeTopPickProps) {
  const { product, clean_ingredients, biomarker_conflicts, compatibility_pct, avatar_variant } = data;

  return (
    <div className="rounded-[14px] overflow-hidden border border-[rgba(96,165,250,.35)]">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-[rgba(30,58,138,.25)] border-b border-[rgba(96,165,250,.15)]">
        <span className="font-mono text-[10px] font-bold text-[#93c5fd] uppercase tracking-[0.08em]">
          ⭐ Mejor match para ti
        </span>
        <span className="font-mono text-[11px] text-[#60a5fa]">{compatibility_pct}% compatible</span>
      </div>

      {/* Body */}
      <div className="flex items-start gap-3 p-4 bg-[rgba(12,24,40,.6)] relative">
        {/* Ambient glow */}
        <div
          className="absolute top-0 left-1/2 -translate-x-1/2 pointer-events-none"
          style={{
            width: 200,
            height: 100,
            background: "radial-gradient(ellipse at top, rgba(96,165,250,.10) 0%, transparent 70%)",
            borderRadius: "0 0 100% 100%",
          }}
        />

        <div className="flex flex-col items-center gap-1 shrink-0 relative z-10">
          <AvatarGlow variant={avatar_variant as AvatarVariant} size={88} intensity="strong" />
          <span className="font-mono text-[9px] text-[#60a5fa] font-semibold uppercase tracking-[0.06em]">
            Seguro
          </span>
        </div>

        <div className="flex-1 min-w-0 relative z-10">
          <p className="font-sans font-bold text-[17px] text-[#bfdbfe] leading-tight">{product.name}</p>
          <p className="text-[11px] text-[#475569] mt-0.5 mb-3">{product.brand}</p>
          {clean_ingredients.map((label) => (
            <p key={label} className="text-[11px] text-[#60a5fa] mb-1">
              ✓ {label}
            </p>
          ))}
        </div>
      </div>

      {/* Biomarker insight / CTA to BioSync */}
      <div className="px-3 py-2 border-t border-[rgba(96,165,250,.15)] bg-[rgba(30,58,138,.15)]">
        {hasBiomarkers ? (
          <p className="text-[11px] text-[#93c5fd]">
            💊{" "}
            {biomarker_conflicts.length === 0
              ? "Sin conflictos con tus biomarcadores"
              : biomarker_conflicts.slice(0, 2).join(" · ")}
          </p>
        ) : (
          <Link
            href="/biosync"
            className="flex items-center gap-1.5 text-[11px] text-[#93c5fd] hover:text-[#60a5fa] transition-colors"
          >
            🔒 Personaliza con tus biomarcadores →
          </Link>
        )}
      </div>

      {/* CTA */}
      <div className="px-3 py-2.5 bg-[rgba(15,30,60,.5)] border-t border-[rgba(96,165,250,.10)]">
        <Link
          href={`/scan/${product.barcode}`}
          className="block bg-[#2563eb] text-white text-center py-2 px-4 rounded-lg text-[13px] font-semibold hover:bg-[#1d4ed8] transition-colors"
        >
          Ver análisis completo →
        </Link>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/AlternativeTopPick.tsx
git commit -m "feat(ui): AlternativeTopPick component with AvatarGlow blue, biomarker insight, CTA"
```

---

## Task 15: AlternativeRow component

**Files:**
- Create: `frontend/components/AlternativeRow.tsx`

- [ ] **Step 1: Crear el componente**

```tsx
"use client";

import Link from "next/link";
import { AvatarGlow } from "@/components/AvatarGlow";
import type { AlternativeItem } from "@/lib/api/types";
import type { AvatarVariant } from "@/lib/api/types";

const SEMAPHORE_LABEL: Record<string, string> = {
  BLUE: "Seguro",
  YELLOW: "Precaución",
  ORANGE: "Riesgo",
  RED: "Prohibido",
  GRAY: "Sin datos",
};

const SEMAPHORE_COLORS: Record<string, { bg: string; text: string }> = {
  BLUE:   { bg: "rgba(37,99,235,.25)",  text: "#60a5fa" },
  YELLOW: { bg: "rgba(161,130,0,.25)",  text: "#facc15" },
  ORANGE: { bg: "rgba(154,52,18,.25)",  text: "#fb923c" },
  RED:    { bg: "rgba(127,29,29,.25)",  text: "#f87171" },
  GRAY:   { bg: "rgba(75,85,99,.25)",   text: "#9ca3af" },
};

interface AlternativeRowProps {
  item: AlternativeItem;
}

export function AlternativeRow({ item }: AlternativeRowProps) {
  const { product, avatar_variant, semaphore_precomputed } = item;
  const colors = SEMAPHORE_COLORS[semaphore_precomputed] ?? SEMAPHORE_COLORS.GRAY;
  const label = SEMAPHORE_LABEL[semaphore_precomputed] ?? "General";

  return (
    <Link
      href={`/scan/${product.barcode}`}
      className="flex items-center gap-3 px-3 py-2.5 rounded-[10px] border border-[#1a2318] bg-[#0b150b] hover:border-[#2d3f2d] transition-colors"
    >
      {/* Avatar — soft, slow pulse */}
      <div style={{ animation: "none" }}>
        <AvatarGlow
          variant={avatar_variant as AvatarVariant}
          size={40}
          intensity="soft"
          className="[animation-duration:4s]"
        />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-[13px] font-semibold text-[#cbd5e1] truncate">{product.name}</p>
        <p className="text-[11px] text-[#475569]">{product.brand}</p>
      </div>

      {/* Semaphore badge */}
      <div className="flex flex-col items-center gap-0.5 shrink-0">
        <span
          className="px-2 py-0.5 rounded-full text-[11px] font-bold"
          style={{ background: colors.bg, color: colors.text }}
        >
          {label}
        </span>
        <span className="text-[9px] text-[#334155]">general</span>
      </div>
    </Link>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/AlternativeRow.tsx
git commit -m "feat(ui): AlternativeRow component with AvatarGlow soft + semaphore badge"
```

---

## Task 16: Alternatives page

**Files:**
- Create: `frontend/app/(app)/scan/[id]/alternatives/page.tsx`

- [ ] **Step 1: Crear directorio**

```bash
mkdir -p frontend/app/\(app\)/scan/\[id\]/alternatives
```

- [ ] **Step 2: Crear `page.tsx`**

```tsx
"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { getAlternatives } from "@/lib/api/scan";
import { recordAnalyticsEvent } from "@/lib/api/analytics";
import { AILoadingState, ALTERNATIVES_PHASES } from "@/components/AILoadingState";
import { AlternativeTopPick } from "@/components/AlternativeTopPick";
import { AlternativeRow } from "@/components/AlternativeRow";
import { AvatarGlow } from "@/components/AvatarGlow";
import type { AlternativesResponse } from "@/lib/api/types";
import { useEffect } from "react";

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-4 py-16 px-4 text-center">
      <AvatarGlow variant="gray" size={80} intensity="soft" />
      <p className="text-[15px] font-semibold text-[#94a3b8]">
        No encontramos alternativas en nuestra base de datos aún
      </p>
      <p className="text-[12px] text-[#475569]">Estamos expandiendo el catálogo</p>
    </div>
  );
}

function SkeletonTopPick() {
  return (
    <div className="rounded-[14px] border border-[#1a2318] bg-[#0b150b] overflow-hidden animate-pulse">
      <div className="h-8 bg-[#1a2318]" />
      <div className="flex gap-3 p-4">
        <div className="w-[88px] h-[88px] rounded-full bg-[#1a2318] shrink-0" />
        <div className="flex-1 space-y-2 pt-2">
          <div className="h-4 bg-[#1a2318] rounded w-3/4" />
          <div className="h-3 bg-[#1a2318] rounded w-1/2" />
          <div className="h-3 bg-[#1a2318] rounded w-2/3" />
        </div>
      </div>
      <div className="h-8 bg-[#1a2318] mx-4 mb-4 rounded-lg" />
    </div>
  );
}

function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 px-3 py-2.5 rounded-[10px] border border-[#1a2318] bg-[#0b150b] animate-pulse">
      <div className="w-10 h-10 rounded-full bg-[#1a2318] shrink-0" />
      <div className="flex-1 space-y-1.5">
        <div className="h-3 bg-[#1a2318] rounded w-3/4" />
        <div className="h-2.5 bg-[#1a2318] rounded w-1/2" />
      </div>
      <div className="w-16 h-5 bg-[#1a2318] rounded-full" />
    </div>
  );
}

export default function AlternativesPage() {
  const { id: barcode } = useParams<{ id: string }>();
  const router = useRouter();

  const { data, isLoading, isError } = useQuery<AlternativesResponse>({
    queryKey: ["alternatives", barcode],
    queryFn: () => getAlternatives(barcode),
    staleTime: 10 * 60 * 1000,
  });

  useEffect(() => {
    recordAnalyticsEvent({ event_type: "alt_page_opened", payload: { barcode } });
  }, [barcode]);

  const isEmpty = data && !data.top_pick && data.alternatives.length === 0;

  return (
    <div className="relative z-10 px-4 py-6 max-w-[480px] mx-auto flex flex-col gap-5">
      {/* Back nav */}
      <Link
        href={`/scan/${barcode}`}
        className="inline-flex items-center gap-1.5 font-mono text-[11px] text-[#4a5568] hover:text-foreground transition-colors uppercase tracking-[0.08em] -mb-2"
      >
        <ArrowLeft size={13} />
        resultado del scan
      </Link>

      {/* Header */}
      <div>
        <h1 className="text-[22px] font-bold text-[#f1f5f9]">Alternativas más limpias</h1>
        {data && (
          <p className="text-[12px] text-[#475569] mt-0.5">
            Para: {data.scanned_product.name || barcode}
            {data.fallback_used && (
              <span className="ml-2 text-[#64748b]">· Resultados aproximados</span>
            )}
          </p>
        )}
      </div>

      {/* Loading */}
      {isLoading && (
        <>
          <AILoadingState phases={ALTERNATIVES_PHASES} />
          <SkeletonTopPick />
          <SkeletonRow />
          <SkeletonRow />
        </>
      )}

      {/* Error */}
      {isError && (
        <div className="text-center py-10 text-[#f87171] text-[14px]">
          Error al cargar alternativas. <button onClick={() => router.refresh()} className="underline">Reintentar</button>
        </div>
      )}

      {/* Empty */}
      {!isLoading && isEmpty && <EmptyState />}

      {/* Results */}
      {data && !isEmpty && (
        <>
          {data.top_pick && (
            <AlternativeTopPick data={data.top_pick} hasBiomarkers={data.has_biomarkers} />
          )}

          {data.alternatives.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="font-mono text-[10px] font-semibold text-[#64748b] uppercase tracking-[0.1em]">
                Otras opciones · semáforo general
              </p>
              {data.alternatives.map((alt) => (
                <div
                  key={alt.product.barcode}
                  onClick={() =>
                    recordAnalyticsEvent({
                      event_type: "alt_tapped",
                      payload: { barcode: alt.product.barcode },
                    })
                  }
                >
                  <AlternativeRow item={alt} />
                </div>
              ))}
            </div>
          )}

          <p className="text-[11px] text-[#334155] text-center mt-1">
            Toca cualquier opción para ver su análisis completo
          </p>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add "frontend/app/(app)/scan/[id]/alternatives/"
git commit -m "feat(ui): alternatives page with AILoadingState + AlternativeTopPick + AlternativeRow"
```

---

## Task 17: "Ver alternativas" button en scan result

**Files:**
- Modify: `frontend/app/(app)/scan/[id]/page.tsx`

- [ ] **Step 1: Localizar el Hero card en `page.tsx`**

Busca el bloque `{/* Hero card */}` o el elemento que contiene el `sem.avatar` image. El botón se agrega inmediatamente después del hero card, dentro del mismo `div` de la columna izquierda.

- [ ] **Step 2: Agregar el botón condicional**

```tsx
// Agregar entre el hero card y el resto del contenido, donde `sem` y `id` ya están disponibles
{(["YELLOW", "ORANGE", "RED"] as const).includes(data.semaphore) && (
  <Link
    href={`/scan/${id}/alternatives`}
    onClick={() =>
      import("@/lib/api/analytics").then(({ recordAnalyticsEvent }) =>
        recordAnalyticsEvent({
          event_type: "alt_button_shown",
          payload: { barcode: id, semaphore: data.semaphore },
        })
      )
    }
    className="bs-card flex items-center justify-between px-4 py-3 hover:border-[rgba(96,165,250,.4)] transition-colors group"
    style={{ borderColor: "rgba(96,165,250,.2)" }}
  >
    <span className="text-[13px] font-semibold text-[#93c5fd] group-hover:text-[#60a5fa] transition-colors">
      Ver alternativas más limpias
    </span>
    <span className="text-[#60a5fa] text-[16px]">→</span>
  </Link>
)}
```

- [ ] **Step 3: Agregar import de Link si no está ya importado**

```tsx
import Link from "next/link";  // ya debe existir
```

- [ ] **Step 4: Verificar que el typecheck pasa**

```bash
cd frontend && npx tsc --noEmit
```

Esperado: sin errores.

- [ ] **Step 5: Commit**

```bash
git add "frontend/app/(app)/scan/[id]/page.tsx"
git commit -m "feat(scan): add conditional 'Ver alternativas' button for YELLOW/ORANGE/RED semaphore"
```

---

## Task 18: E2E tests

**Files:**
- Create: `tests/specs/alternatives/alternatives.spec.ts`

- [ ] **Step 1: Crear directorio**

```bash
mkdir -p tests/specs/alternatives
```

- [ ] **Step 2: Crear `alternatives.spec.ts`**

```ts
import { test, expect } from "@playwright/test";

const BASE = "http://localhost:3000";
const API  = "http://localhost:8000";

async function registerAndLogin(page: any, email: string, password: string) {
  await page.request.post(`${API}/auth/register`, {
    data: { email, password },
  });
  const res = await page.request.post(`${API}/auth/login`, {
    data: { email, password },
  });
  const { access_token } = await res.json();
  await page.context().addCookies([
    { name: "access_token", value: access_token, domain: "localhost", path: "/" },
  ]);
  return access_token;
}

test.describe("Alternative Matching (Fase 2)", () => {
  test.beforeAll(async ({ request }) => {
    // Seed fixture products
    // In CI this should be handled by conftest / test setup script
    // Running seed script before E2E suite:
    // await exec("python -m scripts.seed_alternatives_fixture")
  });

  test("RED scan shows 'Ver alternativas' button", async ({ page }) => {
    await registerAndLogin(page, "alt-e2e-red@test.com", "password123");

    // Mock a scan result with RED semaphore
    await page.route(`${API}/scan/barcode`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          product_barcode: "FIX_YOGURT_BAD",
          product_name: "Yogurt con Sucralosa",
          semaphore: "RED",
          ingredients: [{ name: "sucralosa", canonical_name: "sucralosa", cas_number: null, e_number: null, regulatory_status: "Restricted", confidence_score: 0.9, conflicts: [{ conflict_type: "REGULATORY", severity: "HIGH", summary: "Banned in EU", sources: ["EFSA"] }] }],
          conflict_severity: "HIGH",
          source: "barcode",
          scanned_at: new Date().toISOString(),
          personalized_insights: [],
        }),
      });
    });

    await page.goto(`${BASE}/scan/FIX_YOGURT_BAD`);
    await expect(page.getByText("Ver alternativas más limpias")).toBeVisible();
  });

  test("BLUE scan does NOT show 'Ver alternativas' button", async ({ page }) => {
    await registerAndLogin(page, "alt-e2e-blue@test.com", "password123");

    await page.route(`${API}/scan/barcode`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          product_barcode: "FIX_YOGURT_001",
          product_name: "Activia Natural",
          semaphore: "BLUE",
          ingredients: [],
          conflict_severity: null,
          source: "barcode",
          scanned_at: new Date().toISOString(),
          personalized_insights: [],
        }),
      });
    });

    await page.goto(`${BASE}/scan/FIX_YOGURT_001`);
    await expect(page.getByText("Ver alternativas más limpias")).not.toBeVisible();
  });

  test("Alternatives page loads and shows top pick", async ({ page }) => {
    await registerAndLogin(page, "alt-e2e-alts@test.com", "password123");

    await page.route(`${API}/scan/alternatives/FIX_YOGURT_BAD`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          scanned_product: { barcode: "FIX_YOGURT_BAD", name: "Yogurt con Sucralosa", semaphore: "RED" },
          top_pick: {
            product: { barcode: "FIX_YOGURT_001", name: "Activia Natural", brand: "Danone", clean_score: 0 },
            clean_ingredients: ["Sin sucralosa", "Sin colorantes"],
            biomarker_conflicts: [],
            compatibility_pct: 95,
            avatar_variant: "blue",
          },
          alternatives: [
            {
              product: { barcode: "FIX_YOGURT_002", name: "Lala Bio 100", brand: "Lala", clean_score: 1 },
              avatar_variant: "yellow",
              semaphore_precomputed: "YELLOW",
            },
          ],
          has_biomarkers: false,
          fallback_used: false,
        }),
      });
    });

    await page.goto(`${BASE}/scan/FIX_YOGURT_BAD/alternatives`);
    await expect(page.getByText("Mejor match para ti")).toBeVisible();
    await expect(page.getByText("Activia Natural")).toBeVisible();
    await expect(page.getByText("Otras opciones")).toBeVisible();
    await expect(page.getByText("Lala Bio 100")).toBeVisible();
  });

  test("Without biomarkers shows BioSync CTA", async ({ page }) => {
    await registerAndLogin(page, "alt-e2e-nobio@test.com", "password123");

    await page.route(`${API}/scan/alternatives/**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          scanned_product: { barcode: "FIX_YOGURT_BAD", name: "Yogurt con Sucralosa", semaphore: "RED" },
          top_pick: {
            product: { barcode: "FIX_YOGURT_001", name: "Activia Natural", brand: "Danone", clean_score: 0 },
            clean_ingredients: ["Sin sucralosa"],
            biomarker_conflicts: [],
            compatibility_pct: 90,
            avatar_variant: "blue",
          },
          alternatives: [],
          has_biomarkers: false,
          fallback_used: false,
        }),
      });
    });

    await page.goto(`${BASE}/scan/FIX_YOGURT_BAD/alternatives`);
    await expect(page.getByText("Personaliza con tus biomarcadores")).toBeVisible();
  });

  test("Empty state shown when no alternatives found", async ({ page }) => {
    await registerAndLogin(page, "alt-e2e-empty@test.com", "password123");

    await page.route(`${API}/scan/alternatives/**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          scanned_product: { barcode: "FIX_NOCAT_001", name: "Producto Sin Categoría", semaphore: "RED" },
          top_pick: null,
          alternatives: [],
          has_biomarkers: false,
          fallback_used: true,
        }),
      });
    });

    await page.goto(`${BASE}/scan/FIX_NOCAT_001/alternatives`);
    await expect(page.getByText("No encontramos alternativas")).toBeVisible();
  });

  test("Tap on alternative navigates to its scan result", async ({ page }) => {
    await registerAndLogin(page, "alt-e2e-tap@test.com", "password123");

    await page.route(`${API}/scan/alternatives/**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          scanned_product: { barcode: "FIX_YOGURT_BAD", name: "Yogurt con Sucralosa", semaphore: "RED" },
          top_pick: {
            product: { barcode: "FIX_YOGURT_001", name: "Activia Natural", brand: "Danone", clean_score: 0 },
            clean_ingredients: ["Sin sucralosa"],
            biomarker_conflicts: [],
            compatibility_pct: 95,
            avatar_variant: "blue",
          },
          alternatives: [],
          has_biomarkers: false,
          fallback_used: false,
        }),
      });
    });

    await page.goto(`${BASE}/scan/FIX_YOGURT_BAD/alternatives`);
    await page.getByText("Ver análisis completo →").click();
    await expect(page).toHaveURL(/\/scan\/FIX_YOGURT_001/);
  });
});
```

- [ ] **Step 3: Commit**

```bash
git add tests/specs/alternatives/
git commit -m "test(e2e): alternatives feature — 6 Playwright specs covering happy path and edge cases"
```

---

## Task 19: Update docs

**Files:**
- Modify: `PRD.md`
- Modify: `docs/architecture.md`
- Modify: `docs/embedding-strategy.md`

- [ ] **Step 1: Reemplazar la sección `### Fase 2 — Retail Integration` en `PRD.md`**

Busca el bloque que empieza en `### Fase 2 — Retail Integration` y reemplázalo con:

```markdown
### Fase 2 — Alternative Matching (Health-Conscious)

**Objetivo:** dado un producto con semáforo YELLOW/ORANGE/RED, encontrar alternativas reales del mercado mexicano con ingredientes más limpios, priorizadas por compatibilidad con los biomarcadores activos del usuario.

**Pivot estratégico:** se descartaron los conectores a APIs retail (Walmart/Cornershop/Mercado Libre) por cobertura pobre en productos health-conscious y dependencia de credenciales comerciales. Se reemplaza por un curated DB propio de productos, ingesta vía Open Food Facts Search API v2 (MX). Ver spec: `docs/superpowers/specs/2026-05-12-product-ingestion-off-design.md`.

**Features:**
- Curated DB de 400–900 productos health-conscious vía Open Food Facts (MX, categorías health)
- Hybrid matching engine: SQL first pass por categoría → ChromaDB re-rank → biomarker filter rule-based
- Pantalla `/scan/[id]/alternatives`: top pick personalizado (AvatarGlow blue) + lista secundaria
- `GET /scan/alternatives/{barcode}` endpoint · `POST /analytics/event` fire-and-forget
- Nueva ChromaDB collection `products` (ingredient profiles, 1024-dim BGE-M3)
- A/B testing de semáforo UI en producción (independiente — sigue en roadmap)

**Spec completo:** `docs/superpowers/specs/2026-05-08-alternative-matching-design.md`

**Dependencias:** Fase 1 shipped, curated DB cargado y scripts de curation ejecutados.
```

- [ ] **Step 2: Agregar al final de `docs/architecture.md`**

```markdown
---

## 2. Fase 2 — Extensiones de Schema

### 2.1 Campos nuevos en `products`

| Campo | Tipo | Descripción |
|---|---|---|
| `category` | `VARCHAR(100)` | Categoría OFF (ej. `"yogurts"`, `"bebidas"`). `NULL` para productos foto-scaneados sin categoría. |
| `clean_score` | `SMALLINT DEFAULT 0` | Número de ingredientes problemáticos detectados. **Menor = más limpio.** 0 = cero ingredientes flaggeados. Pre-computado en curation via `scripts/compute_clean_scores.py`. |

Índices: `idx_products_category`, `idx_products_clean_score`.

### 2.2 Nueva tabla `analytics_events`

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | `UUID PK` | Identificador único |
| `user_id` | `UUID FK → users.id` | Usuario que generó el evento |
| `event_type` | `VARCHAR(50)` | `alt_button_shown` / `alt_page_opened` / `alt_tapped` |
| `payload` | `JSONB` | Contexto adicional (barcode, semaphore, etc.) |
| `created_at` | `TIMESTAMP` | Timestamp del evento |

### 2.3 Nueva ChromaDB collection: `products`

Separada de la collection `ingredients`. Cada documento es el ingredient profile de un producto curado. Dimensión: 1024 (BGE-M3, consistente con `ingredients`).

**Pipeline de ingesta:** `scripts/compute_clean_scores.py` → `scripts/index_products_chroma.py`

**Nota:** `scan_history.result_json` (migration `a3f7c2d1e845`) ya existe — Fase 2 lo consume para extraer `flagged_ingredients[]` sin re-correr el pipeline.
```

- [ ] **Step 3: Agregar al final de `docs/embedding-strategy.md`**

```markdown
---

## 11. Fase 2 — Collection `products`

### Propósito

Segunda collection de ChromaDB, separada de `ingredients`. Almacena ingredient profiles de productos curados para el alternative matching engine.

### Template de embedding

```
"nombre: {name} | marca: {brand} | categoría: {category} |
clean_score: {clean_score}"
```

Metadata por documento: `{ barcode, category, clean_score, semaphore_precomputed }`.

### Pipeline de ingesta

1. `backend/scripts/compute_clean_scores.py` — calcula `clean_score` y persiste en `products.clean_score`
2. `backend/scripts/index_products_chroma.py` — genera profile text → embed con BGE-M3 → upsert en collection `products`

Scripts offline: se corren una vez al cargar el curated DB y cada vez que se agregan productos nuevos.

### Modelo y dimensión

Mismo que la collection `ingredients`: BGE-M3 local (1024-dim). No requiere re-indexar `ingredients` — son collections independientes.

### Query en runtime

El alternatives engine (`backend/app/services/alternatives.py`) construye el query text como:
```
"categoría: {category} sin {flagged_ing_1} sin {flagged_ing_2}..."
```
y filtra con `where={"barcode": {"$in": candidate_barcodes}}` sobre los resultados del SQL first pass.
```

- [ ] **Step 4: Commit**

```bash
git add PRD.md docs/architecture.md docs/embedding-strategy.md
git commit -m "docs: update PRD Fase 2, architecture, embedding-strategy for alternative matching"
```

---

## Task 20: Verificación final

- [ ] **Step 1: Correr todos los unit tests del backend**

```bash
cd backend && pytest tests/ -v --tb=short
```

Esperado: todos los tests pasan incluyendo `test_alternatives.py`.

- [ ] **Step 2: Correr typecheck del frontend**

```bash
cd frontend && npx tsc --noEmit
```

Esperado: sin errores de tipos.

- [ ] **Step 3: Correr E2E tests de alternatives**

```bash
npx playwright test tests/specs/alternatives/ --reporter=list
```

Esperado: 6/6 tests pasan.

- [ ] **Step 4: Verificar que los tests existentes no se rompieron**

```bash
npx playwright test tests/specs/ --reporter=list
```

Esperado: todos los tests previos siguen pasando.

- [ ] **Step 5: Merge a main cuando todo esté verde**

```bash
# Desde el repo principal (no el worktree)
git merge feat/fase2-alternative-matching --no-ff -m "feat(fase2): ingredient-based alternative matching"
git worktree remove ../bio_shield_fase2
```
