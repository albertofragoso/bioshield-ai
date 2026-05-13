# BioShield Fase 2.0.1 — Product Ingestion Pipeline (Open Food Facts)

**Fecha:** 2026-05-12
**Autor:** Alberto Fragoso
**Estado:** Diseño aprobado — BLOQUEANTE para Fase 2.1 (Alternative Matching Feature)
**Prioridad:** CRÍTICA
**Reemplaza:** `2026-05-12-product-ingestion-mercado-libre.md` (descartado — ver §2)
**Dependencia para:** `docs/superpowers/specs/2026-05-08-alternative-matching-design.md` + `docs/superpowers/specs/2026-05-09-scan-enrichment-design.md`

---

## 1. Contexto y Objetivo

Fase 2 (Alternative Matching) requiere un **curated DB de productos health-conscious** para que el usuario reciba alternativas reales cuando escanea un producto con semáforo amarillo/naranja/rojo.

Sin este DB:
- No hay productos para matchear
- Hybrid matching engine (SQL → ChromaDB → biomarker filter) no puede funcionar
- E2E tests fallan (sin fixtures de datos)

**Objetivo:** Automatizar la ingesta de ~400–900 productos health-conscious del mercado mexicano usando Open Food Facts Search API v2, cargarlos a DB, computar clean scores, e indexarlos en ChromaDB.

---

## 2. Estrategia de Ingesta

### 2.1 Por qué OFF Search API v2 (no Mercado Libre)

El approach original (Mercado Libre + printingpress CLI) fue descartado por dos razones fundamentales:

1. **ML no tiene datos de ingredientes.** Mercado Libre es un marketplace — su API devuelve nombre, precio, imagen, vendedor. Sin `ingredients_json`, `clean_score = NULL` y el feature de alternativas no funciona.

2. **El dump global de OFF no tiene versión MX pequeña.** El CSV global es ~3GB comprimido. Descargarlo para filtrar ~1K productos es inviable.

**Solución:** OFF Search API v2 (`search.openfoodfacts.org/search`) con filtros `countries_tags=en:mexico` + categorías health, campos seleccionados explícitamente. Para ~1K productos: 30–75 requests, sin rate limiting real.

### 2.2 Fuente de datos

| Campo | Valor |
|---|---|
| API | `https://search.openfoodfacts.org/search` |
| Filtros | `countries_tags=en:mexico`, `categories_tags=<categoria>` |
| Campos | `code,product_name,product_name_es,brands,categories_tags,ingredients_text,image_front_url` |
| Page size | 1000 resultados/request |
| Estimado requests | 30–75 totales (15 categorías × 2–5 páginas) |
| Estimado productos finales | 400–900 (con `ingredients_text` válido) |

### 2.3 Categorías health (OFF taxonomy)

```python
HEALTH_CATEGORIES = [
    "en:yogurts", "en:fermented-milks", "en:plant-based-foods",
    "en:breakfast-cereals", "en:whole-grain-foods", "en:nuts",
    "en:dried-fruits", "en:legumes", "en:plant-based-beverages",
    "en:waters", "en:fruit-juices", "en:herbal-teas",
    "en:organic-foods", "en:baby-foods", "en:dietary-supplements",
]
```

### 2.4 Filtros de calidad por producto

Un producto se **descarta** si:
- Sin `code` (barcode)
- Sin `product_name` ni `product_name_es`
- Sin `ingredients_text` o vacío después de strip
- `parse_ingredients(ingredients_text)` devuelve lista vacía

---

## 3. Arquitectura de Scripts

```
backend/scripts/
├── utils/
│   └── ingredient_parser.py          ← NUEVO
│       parse_ingredients(text) -> list[str]
│       - Split top-level respetando paréntesis anidados
│       - Extrae sub-ingredientes recursivamente
│       - Strip porcentajes, whitespace
│       - Dedup manteniendo orden
│
├── ingest_off_mexico.py              ← NUEVO
│   - OFF Search API v2, por categoría en HEALTH_CATEGORIES
│   - Pagina hasta agotar resultados por categoría
│   - parse_ingredients(ingredients_text) → ingredients_json
│   - Crea scripts/data/ si no existe
│   - Output: scripts/data/off_products.json
│   - Log: total_fetched / accepted / skipped (con breakdown de razón)
│
├── load_products_to_db.py            ← NUEVO
│   - Lee scripts/data/off_products.json
│   - Upsert agnóstico SQLite/PostgreSQL:
│     select(Product).where(barcode==x) → update | insert
│   - Procesa en batches de 100, commit por batch
│   - Log: inserted / updated / errors
│
├── compute_clean_scores.py           ← SIN CAMBIOS
│   (requiere tabla `ingredients` + `regulatory_status` pobladas vía seed_rag.py)
│
├── index_products_chroma.py          ← MODIFICADO
│   - Usa build_product_profile() desde app.services.rag (ver §4)
│   - Perfil incluye ingredientes cuando ingredients_json is not None
│
└── seed_alternatives_fixture.py      ← SIN CAMBIOS
```

---

## 4. Refactor: `build_product_profile` centralizado

### Problema
`_build_profile` estaba duplicada en `enrichment.py` y `index_products_chroma.py` con formato idéntico pero sin ingredientes. Esto causaría perfiles inconsistentes en ChromaDB entre productos indexados vía bulk vs. post-scan.

### Solución
Nueva función en `app/services/rag.py`:

```python
def build_product_profile(product: Product) -> str:
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

Ambas copias locales (`enrichment.py._build_profile`, `index_products_chroma.py._build_profile`) se eliminan y se reemplazan con llamada a esta función.

**Por qué cap a 20 ingredientes:** BGE-M3 tiene ventana de 8192 tokens. 20 ingredientes × ~5 palabras = ~130 tokens. Bien dentro del límite. Los ingredientes más importantes (mayoritarios) aparecen primero en el texto de OFF.

---

## 5. Field Mapping OFF → Product

| OFF campo | Transformación | Product campo |
|---|---|---|
| `code` | directo | `barcode` |
| `product_name_es` → fallback `product_name` | preferir español | `name` |
| `brands` | `split(",")[0].strip()` | `brand` |
| `categories_tags` | primer match en HEALTH_CATEGORIES | `category` |
| `image_front_url` | directo, puede ser `""` | `image_url` |
| `ingredients_text` | `parse_ingredients()` | `ingredients_json` |
| hardcoded `"off_dump_mx"` | encode país sin migración | `ingredients_source` |

**Nota sobre `ingredients_source`:** se usa `"off_dump_mx"` (no `"off_dump"`) para encodear el país de origen sin requerir migración. Ver §6 sobre estrategia multi-país.

---

## 6. Estrategia Multi-País (Documentada para Escalar)

### Estado actual
El script soporta México como primer mercado. `ingredients_source = "off_dump_mx"` encoda el país.

### Cómo agregar un nuevo país (ej. España, Argentina)

**Paso 1 — Script (costo cero):**
`ingest_off_mexico.py` → parametrizar como `ingest_off.py --country-tag en:mexico --market mx`. Agregar España sería `--country-tag en:spain --market es`. Sin duplicación de código.

**Paso 2 — Migración DB (cuando haya 2+ países):**
```python
# Alembic migration
class Product(Base):
    ...
    market: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # "mx", "es", "ar", etc.
```
Backfill: `UPDATE products SET market = 'mx' WHERE ingredients_source = 'off_dump_mx'`.

**Paso 3 — Alternatives engine:**
Agregar filtro por mercado en `alternatives.py`:
```python
Product.market == user_market  # en SQL first pass
{"market": user_market}        # en ChromaDB where filter
```
El modelo de usuario necesitará un campo `market` o se infiere por IP/configuración.

**Paso 4 — ChromaDB metadata:**
Agregar `"market": "mx"` a los metadatos de cada embedding para pre-filtrado.

### Cuándo hacer el Paso 2+
Solo cuando se agregue la segunda fuente/país. No antes — YAGNI.

---

## 7. Prerequisitos de Ejecución

```bash
# 1. Prerequisito: tabla ingredients poblada
cd backend && python -m scripts.seed_rag

# 2. Pipeline de ingesta (en orden):
python -m scripts.ingest_off_mexico          # → scripts/data/off_products.json
python -m scripts.load_products_to_db        # → tabla products
python -m scripts.compute_clean_scores       # → products.clean_score
python -m scripts.index_products_chroma      # → ChromaDB 'products' collection

# 3. Fixture E2E (independiente):
python -m scripts.seed_alternatives_fixture
```

---

## 8. Success Criteria

| Criterio | Valor |
|---|---|
| `SELECT COUNT(*) FROM products WHERE ingredients_source = 'off_dump_mx'` | ≥ 400 |
| `SELECT COUNT(*) FROM products WHERE clean_score > 0` | > 0 (valida RAG funcional) |
| ChromaDB `products` collection size | ≥ 400 embeddings |
| `off_products.json` generado sin errores | ✅ |
| Upsert idempotente: correr `load_products_to_db.py` 2× → mismo count | ✅ |
| `seed_alternatives_fixture.py` sigue pasando sin cambios | ✅ |
| Perfiles ChromaDB incluyen ingredientes para productos con `ingredients_json` | ✅ |

---

## 9. Effort Estimate

| Task | Effort |
|---|---|
| `utils/ingredient_parser.py` | 2–3h |
| `ingest_off_mexico.py` | 3–4h |
| `load_products_to_db.py` | 2h |
| Refactor `build_product_profile` en `rag.py` | 1h |
| Update `index_products_chroma.py` + `enrichment.py` | 1h |
| Ejecutar pipeline + validar success criteria | 1–2h |
| **TOTAL** | **~2 días** |

---

## 10. Archivos Modificados / Creados

| Archivo | Tipo | Descripción |
|---|---|---|
| `backend/scripts/utils/__init__.py` | NUEVO | Package init |
| `backend/scripts/utils/ingredient_parser.py` | NUEVO | Parser robusto de ingredientes |
| `backend/scripts/ingest_off_mexico.py` | NUEVO | Ingesta OFF Search API v2 |
| `backend/scripts/load_products_to_db.py` | NUEVO | Upsert agnóstico a DB |
| `backend/app/services/rag.py` | MODIFICADO | + `build_product_profile()` |
| `backend/app/services/enrichment.py` | MODIFICADO | Usa `build_product_profile`, elimina copia local |
| `backend/scripts/index_products_chroma.py` | MODIFICADO | Usa `build_product_profile`, perfil con ingredientes |
| `backend/scripts/data/` | NUEVO DIR | Output de scripts de ingesta (gitignored) |

---

## 11. Referencias

- **OFF Search API v2:** `https://search.openfoodfacts.org/search`
- **OFF taxonomy:** `https://world.openfoodfacts.org/categories`
- **Alternative Matching Spec:** `docs/superpowers/specs/2026-05-08-alternative-matching-design.md`
- **Enrichment Pipeline Spec:** `docs/superpowers/specs/2026-05-09-scan-enrichment-design.md`
- **Embedding strategy:** `docs/embedding-strategy.md`
