# BioMarker Rules Hardening — Design Spec

**Fecha:** 2026-05-01
**Estado:** Aprobado
**Audiencia:** Backend
**PRs:** 2 (secuenciales, worktrees paralelos durante desarrollo)

---

## Contexto

`BIOMARKER_RULES` es la fuente de verdad clínica del sistema: define qué ingredientes
conflictúan con qué biomarcadores. El matcher de producción (`_find_matches_keywords`)
usa substring matching simple, lo que produce falsos positivos industriales, no detecta
negaciones, y tiene reglas con solapamiento clínico no intencional. El golden dataset
hereda estos defectos en su Capa 1, contaminando el ground truth.

Estos problemas fueron identificados mediante análisis del golden dataset (327 judgments,
avg_confidence 0.83) y revisión del catálogo EFSA (4,637 ingredientes), donde términos
como `"hydrogenated"` matchean polímeros petroquímicos que no son alimentos.

---

## Scope

Tres componentes en dos PRs secuenciales:

1. **PR 1** — `analysis.py` (matcher producción) + `BIOMARKER_RULES` + tests + docs
2. **PR 2** — `build_golden_dataset.py` (replicar guards) + rebuild + calibración

---

## Worktree Strategy

```
main
├── worktree/pr1-biomarker-rules-hardening   ← desarrollo PR 1
└── worktree/pr2-golden-dataset-rebuild      ← se crea después de merge de PR 1
```

PR 2 no se abre hasta que PR 1 esté mergeado. El dataset debe reflejar las reglas
de producción finales para que los baselines sean válidos.

---

## PR 1: Fix del Matcher de Producción

### 1.1 Cambio de firma — `BiomarkerRule`

Agregar campo opcional `excludes` al dataclass existente:

```python
@dataclass(frozen=True)
class BiomarkerRule:
    biomarker: CanonicalBiomarker
    direction: Literal["raises", "lowers"]
    keywords: tuple[str, ...]
    severity: ConflictSeverity
    message: str
    excludes: tuple[str, ...] = ()   # substrings que descartan el match
```

El campo tiene default vacío: backward compatible, ningún caller existente se rompe.

### 1.2 Nuevo helper — `_has_negation`

```python
_NEGATION_TERMS = ("free", "without", "sin", "no ", "zero", "libre", "free of")

def _has_negation(text: str, keyword: str) -> bool:
    idx = text.find(keyword)
    if idx < 0:
        return False
    window = text[max(0, idx - 15):idx]
    return any(neg in window for neg in _NEGATION_TERMS)
```

Rationale: look-back de 15 chars cubre `"trans fat free"`, `"sin grasas trans"`,
`"hydrogenated-free"`. Ingredient names del catálogo EFSA/FDA son strings técnicos
cortos y bien formados — los edge cases de ambigüedad en práctica son cero.
Sin dependencias nuevas.

### 1.3 Update — `_find_matches_keywords`

Añadir dos guards en el loop de keywords, antes de confirmar el match:

```python
for kw in rule.keywords:
    if kw not in ing_names:
        continue
    if _has_negation(ing_names, kw):                        # guard negaciones
        continue
    if any(ex in ing_names for ex in rule.excludes):        # guard industriales
        continue
    matched_ingr.append(ing.canonical_name or ing.name)
```

Orden de los guards importa: negación primero (más barato), exclude después.

### 1.4 Constante compartida para lípidos

```python
_LIPID_RAISING_KEYWORDS = (
    "trans fat",
    "grasas trans",
    "aceite hidrogenado",
    "hydrogenated",
    "saturated fat",
    "palm oil",
    "aceite de palma",
)

_INDUSTRIAL_HYDROGENATED_EXCLUDES = (
    "petroleum",
    "resin",
    "polymer",
    "copolymer",
    "homopolymer",
    "mw:",
    "decene",
    "dodecene",
    "octene",
    "hexene",
)
```

LDL y TOTAL\_CHOLESTEROL referencian `_LIPID_RAISING_KEYWORDS` directamente.
Si la evidencia clínica diverge en el futuro, cada regla puede agregar keywords propios.

### 1.5 BIOMARKER\_RULES actualizadas

**LDL raises** (HIGH)
- keywords: `_LIPID_RAISING_KEYWORDS`
- excludes: `_INDUSTRIAL_HYDROGENATED_EXCLUDES`

**TOTAL\_CHOLESTEROL raises** (HIGH)
- keywords: `_LIPID_RAISING_KEYWORDS`
- excludes: `_INDUSTRIAL_HYDROGENATED_EXCLUDES`

**HDL lowers** (MEDIUM)
- keywords: `("trans fat", "grasas trans", "hydrogenated", "aceite hidrogenado")`
- excludes: `_INDUSTRIAL_HYDROGENATED_EXCLUDES`

**GLUCOSE raises** (HIGH) — picos rápidos, absorción inmediata
- keywords: `("dextrose", "dextrosa", "maltose", "maltosa", "refined sugar", "white sugar", "azúcar refinada", "glucose syrup", "jarabe de glucosa")`
- excludes: `()`
- Nota: `"fructose"` y `"corn syrup"` se mueven a HBA1C — efecto crónico, no agudo.

**HBA1C raises** (HIGH) — carga glucémica crónica
- keywords: `("high fructose", "corn syrup", "jarabe de maíz", "fructose", "fructosa", "added sugar", "azúcar añadida")`
- excludes: `()`
- Nota: `"dextrose"` se mueve a GLUCOSE — pico agudo, no acumulativo.

**TRIGLYCERIDES raises** (MEDIUM)
- keywords: `("fructose", "fructosa", "jarabe", "syrup", "added sugar")`
- excludes: `()` — sin cambio

**SODIUM raises** (MEDIUM)
- keywords: `("sodium chloride", "cloruro de sodio", "monosodium glutamate", "glutamato monosódico", "msg", "added salt", "sal de mesa", "table salt", "sodium", "sodio")`
- excludes: `("potassium salt", "calcium salt", "magnesium salt", "fatty acid salt", "sodium bicarbonate", "sodium carbonate", "sodium silicate")`
- Rationale: excluir compuestos donde "sodium" es descriptor IUPAC de un aditivo
  no relacionado con ingesta de sal dietética.

**URIC\_ACID raises** (MEDIUM)
- keywords: `("high fructose", "corn syrup", "fructose", "fructosa", "jarabe de maíz")`
- excludes: `()` — sin cambio

**POTASSIUM raises** (LOW) — expandido para hiperkalemia
- keywords: `("potassium chloride", "cloruro de potasio", "potassium", "potasio", "potásico", "kcl", "dipotassium", "potassic")`
- excludes: `()` — keywords son suficientemente específicos

### 1.6 Deduplicación en `compute_semaphore`

Cuando múltiples reglas disparan sobre el mismo ingrediente (ej: LDL y TOTAL\_CHOL
ambos matchean "palm oil"), colapsar al conflicto de mayor severity antes de construir
la lista de `PersonalizedAlert`. La detección sigue siendo exhaustiva (beneficia al
golden dataset); el usuario ve una sola alerta por ingrediente.

Implementación: agrupar `matches` por `ingredient_name`, conservar el de mayor
`_SEVERITY_RANK`.

### 1.7 Tests nuevos en `test_analysis.py`

Cada gotcha resuelto requiere un test de regresión:

| Test | Verificación |
|------|-------------|
| `test_negation_trans_fat_free_no_match` | `"Trans Fat Free Palm Oil"` + LDL high → `[]` |
| `test_negation_sin_grasas_trans_no_match` | `"Aceite sin grasas trans"` + LDL high → `[]` |
| `test_exclude_petroleum_hydrocarbon_no_match` | `"Petroleum Hydrocarbon Resins (hydrogenated)"` + LDL high → `[]` |
| `test_exclude_sodium_bicarbonate_no_match` | `"Sodium bicarbonate"` + SODIUM high → `[]` |
| `test_exclude_potassium_salt_no_match` | `"Potassium salt of fatty acid"` + SODIUM high → `[]` |
| `test_glucose_dextrose_matches_glucose_not_hba1c` | `"dextrose"` → GLUCOSE match, HBA1C no match |
| `test_hba1c_fructose_matches_hba1c_not_glucose` | `"high fructose corn syrup"` → HBA1C match, GLUCOSE no match |
| `test_potassium_dipotassium_matches` | `"dipotassium phosphate"` → POTASSIUM match |
| `test_potassium_expanded_kcl_matches` | `"KCl"` (lowercase: `"kcl"`) → POTASSIUM match |
| `test_dedup_ldl_total_chol_single_alert` | `"palm oil"` + LDL high + TOTAL_CHOL high → una sola alerta en `compute_semaphore` |

### 1.8 Actualizaciones de documentación (parte de PR 1)

**`docs/evaluation/golden-dataset.md`**

- §2 Arquitectura / Capa 1: agregar mención a guards de `excludes` y negación en
  `_keyword_relevance` — la Capa 1 replica el matcher de producción exactamente.
- §6 Cuándo re-construir: añadir trigger `"Se modificaron keywords, excludes, o
  negation logic en reglas existentes"` — no solo cuando se agregan >10 reglas nuevas.
- §8 Limitaciones conocidas: actualizar puntos 2 y 3 para reflejar que los falsos
  positivos industriales y la duplicación Glucose/HBA1C están mitigados.

**`docs/embedding-strategy.md`**

- §10 Limitaciones del semantic matching: aclarar que el query text canónico se
  construye solo de `rule.keywords`, no de `rule.excludes`. El ejemplo debe actualizarse
  si los keywords de LDL cambian (añadir nota inline).

---

## PR 2: Golden Dataset Rebuild

### 2.1 Update — `_keyword_relevance` en `build_golden_dataset.py`

Replicar los mismos guards de producción:

```python
def _keyword_relevance(rule: BiomarkerRule, ingredient: Ingredient) -> tuple[int, str | None]:
    name_lower = (ingredient.canonical_name or "").lower()

    # Mismo guard de excludes que producción
    if any(ex in name_lower for ex in rule.excludes):
        return 0, None

    for kw in rule.keywords:
        if kw in name_lower and not _has_negation(name_lower, kw):
            return 5, kw

    synonyms: list[str] = ingredient.synonyms or []
    for synonym in synonyms:
        syn_lower = synonym.lower()
        if any(ex in syn_lower for ex in rule.excludes):
            continue
        for kw in rule.keywords:
            if kw in syn_lower and not _has_negation(syn_lower, kw):
                return 4, kw

    return 0, None
```

`_has_negation` se importa desde `app.services.analysis` — misma función, sin duplicar.

### 2.2 Rebuild y calibración

```bash
cd backend

# Rebuild completo con nuevas reglas
python -m scripts.build_golden_dataset --calibrate

# Verificar que no hay regresión neta
python -m scripts.evaluate_rag --fail-on-regression
```

**Resultado esperado:**
- `total_judgments` baja (falsos positivos industriales eliminados de Capa 1)
- `avg_confidence` sube (near-misses contaminados reducidos)
- Métricas de evaluación mejoran o se mantienen (ground truth más limpio)

### 2.3 Criterio de aceptación de PR 2

`evaluate_rag` devuelve `status: PASS` con los nuevos baselines calibrados.
Si alguna métrica baja vs el dataset anterior, investigar antes de mergear.

---

## Criterios de Aceptación Globales

| Criterio | Verificación |
|----------|-------------|
| `"Trans Fat Free Palm Oil"` no genera alerta LDL | `test_negation_trans_fat_free_no_match` pasa |
| Polímeros industriales con "hydrogenated" no matchean | `test_exclude_petroleum_hydrocarbon_no_match` pasa |
| `"Sodium bicarbonate"` no genera alerta SODIUM | `test_exclude_sodium_bicarbonate_no_match` pasa |
| `"dextrose"` → GLUCOSE sí, HBA1C no | tests de distinción temporal pasan |
| `"dipotassium phosphate"` genera alerta POTASSIUM | `test_potassium_dipotassium_matches` pasa |
| Un ingrediente con LDL+TOTAL_CHOL → una sola alerta | `test_dedup_ldl_total_chol_single_alert` pasa |
| Suite completa de tests pasa | `pytest backend/tests/test_analysis.py` green |
| Dataset rebuild sin regresión | `evaluate_rag --fail-on-regression` exit 0 |
| Docs actualizados | golden-dataset.md §2/§6/§8, embedding-strategy.md §10 |

---

## Lo que NO está en scope

- Nuevas reglas para los 11 `CanonicalBiomarker` sin cobertura (CREATININE, VITAMIN_D, etc.)
- Severidad diferenciada por classification (`severity_by_classification: dict`)
- NLP negation detection (spaCy)
- Normalización automática de idioma (traducción pre-match)
- Cambio de firma de `BiomarkerRule.biomarker` a tuple (fusión de reglas)
