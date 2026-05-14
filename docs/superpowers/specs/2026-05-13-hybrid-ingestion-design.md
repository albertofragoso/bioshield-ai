# BioShield Fase 2.1 — Hybrid Product Ingestion (OFF Global + USDA)

## 1. Contexto y Objetivo

El catálogo actual de OFF México produce ~400–900 productos, lo cual es insuficiente para dar cobertura real al motor de alternativas en todas las categorías. Este spec define la expansión del pipeline de ingesta a tres fuentes paralelas: OFF MX (existente), OFF Global y USDA Branded Foods. El objetivo es alcanzar 7,000–17,000 productos únicos con `ingredients_text` válido, sin modificar el motor de matching ni el schema de DB.

### Criterio de éxito

| Criterio | Valor mínimo |
|---|---|
| Productos únicos en DB post-ingesta | ≥ 7,000 |
| Categorías con ≥ 50 productos | ≥ 8 de las 15 categorías health |
| `clean_score` correctamente computado para productos EN | > 90% (validado con muestra manual de 20 productos USDA) |
| Pipeline idempotente (correr 2× → mismo count) | ✅ |
| Docs de alternativas actualizados sin discrepancias | ✅ |

---

## 2. Arquitectura

```
[Fuente 1] ingest_off_mexico.py  (existente, sin cambios)
              → scripts/data/off_mx_products.json

[Fuente 2] ingest_off_global.py  (nuevo)
              → scripts/data/off_global_products.json

[Fuente 3] ingest_usda.py        (nuevo)
              → scripts/data/usda_products.json

[Merge]    load_all_products.py  (refactor de load_products_to_db.py)
              → Carga en orden de prioridad: MX > Global > USDA
              → Skip si barcode ya existe (preservar fuente de mayor prioridad)
              → DB tabla products

[Existente] compute_clean_scores.py   (sin cambios)
[Existente] index_products_chroma.py  (sin cambios)
```

Los tres scripts de ingesta son independientes y pueden correrse en paralelo. `load_all_products.py` requiere que los tres JSON existan antes de correr.

---

## 3. Scripts nuevos / modificados

### 3.1 `ingest_off_global.py` (nuevo)

Derivado de `ingest_off_mexico.py`. Diferencias:

- Eliminar `"countries_tags": "en:mexico"` del query
- Añadir filtro de calidad `"labels_tags": "en:organic,en:no-additives"` para reducir ruido
- Ampliar `HEALTH_CATEGORIES` con categorías faltantes:
  - `en:snacks`, `en:breakfast-cereals`, `en:condiments`, `en:dairy`, `en:sauces`, `en:frozen-foods`
- `ingredients_source = "off_global"`
- Output: `scripts/data/off_global_products.json`

Yield esperado: 3,000–8,000 productos.

### 3.2 `ingest_usda.py` (nuevo)

**API:** `POST https://api.nal.usda.gov/fdc/v1/foods/search`  
**Auth:** API key gratuita (DEMO_KEY para desarrollo)  
**Filtros:** `dataType=["Branded"]`, `marketCountry="United States"`

Estrategia de búsqueda: un request por categoría usando query terms descriptivos.

```python
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
```

Mapeo de campos USDA → schema interno:

| Campo USDA | Transformación | Campo Product |
|---|---|---|
| `gtinUpc` | directo | `barcode` |
| `description` | `.title()` | `name` |
| `brandOwner` | directo | `brand` |
| `ingredients` | `parse_ingredients()` | `ingredients_json` |
| query key | desde `USDA_QUERIES` | `category` |
| hardcoded `"usda_branded"` | | `ingredients_source` |
| N/A | siempre `None` | `image_url` |

Filtros de calidad: `gtinUpc` no vacío, `parse_ingredients()` retorna lista no vacía.

Paginación: `pageSize=200`, iterar hasta que `totalHits` esté cubierto o `_MAX_PAGES = 10`.

Output: `scripts/data/usda_products.json`

Yield esperado: 5,000–12,000 productos.

### 3.3 `load_all_products.py` (refactor de `load_products_to_db.py`)

Cambio clave respecto al script original: **skip en lugar de update si el barcode ya existe**, para preservar la fuente de mayor prioridad.

```python
SOURCES = [
    Path("data/off_mx_products.json"),      # prioridad 1
    Path("data/off_global_products.json"),  # prioridad 2
    Path("data/usda_products.json"),        # prioridad 3
]
```

Lógica de upsert:
- Si `barcode` ya existe → **skip** (no sobreescribir)
- Si no existe → insert

El script existente `load_products_to_db.py` se mantiene funcional para compatibilidad con el pipeline anterior, pero `load_all_products.py` pasa a ser el script canónico de carga.

---

## 4. BIOMARKER_RULES — compatibilidad bilingüe

Las reglas en `app/services/analysis.py` ya son parcialmente bilingüe. El matching opera sobre `_normalize_ingredient_name()` que lowercasea y normaliza puntuación, por lo que ingredientes USDA en mayúsculas (`"HIGH FRUCTOSE CORN SYRUP"`) se normalizan correctamente.

Keywords EN ya presentes que cubren los ingredientes problemáticos más comunes de USDA:

| Ingrediente USDA | Keyword ya en BIOMARKER_RULES |
|---|---|
| HIGH FRUCTOSE CORN SYRUP | `"high fructose"`, `"corn syrup"` |
| HYDROGENATED VEGETABLE OIL | `"hydrogenated"` |
| PALM OIL | `"palm oil"` |
| SODIUM BENZOATE | `"sodium"` |
| MONOSODIUM GLUTAMATE | `"monosodium glutamate"`, `"msg"` |
| ARTIFICIAL FLAVOR | ninguno — gap menor aceptable |
| SODIUM CHLORIDE | `"sodium chloride"` |

**No se requieren cambios a `analysis.py` para este feature.** Los gaps menores (artificial flavors, colorantes artificiales en inglés) son candidatos para una fase posterior de ampliación de reglas.

---

## 5. Pipeline de ejecución

```bash
# Paso 1 — Ingesta (los tres pueden correr en paralelo o secuencial):
cd backend
python -m scripts.ingest_off_mexico      # → data/off_mx_products.json
python -m scripts.ingest_off_global      # → data/off_global_products.json
python -m scripts.ingest_usda            # → data/usda_products.json

# Paso 2 — Carga a DB:
python -m scripts.load_all_products      # merge con prioridad MX > Global > USDA

# Paso 3 — Scoring e indexado (sin cambios):
python -m scripts.compute_clean_scores
python -m scripts.index_products_chroma
```

---

## 6. Validación post-ingesta

Queries de validación a correr después del pipeline:

```sql
-- Conteo total y por fuente
SELECT ingredients_source, COUNT(*) FROM products GROUP BY ingredients_source;

-- Distribución por categoría
SELECT category, COUNT(*) FROM products GROUP BY category ORDER BY COUNT(*) DESC;

-- Productos sin clean_score (error en compute)
SELECT COUNT(*) FROM products WHERE clean_score IS NULL AND ingredients_json IS NOT NULL;

-- Categorías con < 50 productos (cobertura insuficiente)
SELECT category, COUNT(*) FROM products
GROUP BY category HAVING COUNT(*) < 50 ORDER BY COUNT(*);
```

Muestra manual: revisar 20 productos USDA al azar y verificar que `clean_score` refleja correctamente los ingredientes problemáticos visibles en `ingredients_json`.

---

## 7. Actualización de documentación

Al completar la implementación, los siguientes documentos deben actualizarse para eliminar discrepancias:

| Documento | Qué actualizar |
|---|---|
| `docs/superpowers/specs/2026-05-08-alternative-matching-design.md` | Sección de dependencias: pipeline de ingesta ahora es multi-fuente |
| `docs/superpowers/specs/2026-05-12-product-ingestion-off-design.md` | Agregar nota de supersesión: este spec es reemplazado por el híbrido |
| `docs/superpowers/plans/2026-05-08-alternative-matching.md` | Actualizar criterios de éxito con nuevo volumen de productos |
| `docs/superpowers/plans/2026-05-12-product-ingestion-off.md` | Agregar nota de supersesión: `load_products_to_db.py` reemplazado por `load_all_products.py` |
| `README.md` o doc de onboarding (si existe) | Actualizar pipeline de ingesta con los 3 fuentes |

Regla: ningún documento debe hacer referencia al pipeline de ingesta como "solo OFF México" después de este desarrollo.

---

## 8. Tests

| Test | Archivo |
|---|---|
| `test_ingest_off_global.py` | Misma estructura que `test_ingest_off_mexico.py`: mock HTTP, validar `_map_product`, dedup |
| `test_ingest_usda.py` | Mock `POST /fdc/v1/foods/search`, validar mapeo de campos, filtro de calidad |
| `test_load_all_products.py` | Verificar prioridad: barcode OFF MX no se sobreescribe por USDA |

---

## 9. Archivos modificados / creados

### Crear (nuevos)
- `backend/scripts/ingest_off_global.py`
- `backend/scripts/ingest_usda.py`
- `backend/scripts/load_all_products.py`
- `backend/tests/test_ingest_off_global.py`
- `backend/tests/test_ingest_usda.py`
- `backend/tests/test_load_all_products.py`

### Mantener sin cambios
- `backend/scripts/ingest_off_mexico.py`
- `backend/scripts/load_products_to_db.py` (deprecado pero funcional)
- `backend/scripts/compute_clean_scores.py`
- `backend/scripts/index_products_chroma.py`
- `backend/app/services/analysis.py` (BIOMARKER_RULES)
- `backend/app/services/alternatives.py`

### Actualizar (docs)
- Ver §7 arriba

---

## 10. Esfuerzo estimado

| Tarea | Días |
|---|---|
| `ingest_off_global.py` + tests | 0.5 |
| `ingest_usda.py` + tests | 1.5 |
| `load_all_products.py` + tests | 0.5 |
| Ejecución del pipeline completo + validación | 0.5 |
| Actualización de documentación | 0.5 |
| **Total** | **3.5 días** |
