# BioMarker Rules Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar falsos positivos clínicos en el matcher de biomarcadores y recalibrar el golden dataset para que refleje las reglas corregidas.

**Architecture:** PR 1 endurece `BIOMARKER_RULES` en `analysis.py` (campo `excludes`, helper de negación, keywords diferenciados, dedup en display); PR 2 actualiza `build_golden_dataset.py` para replicar los mismos guards y recalibra el dataset. Merge secuencial: PR 2 parte de main con PR 1 ya integrado.

**Tech Stack:** Python 3.11+, FastAPI, pytest, SQLAlchemy, BGE-M3/ChromaDB

---

## Archivos involucrados

### PR 1
| Archivo | Acción |
|---------|--------|
| `backend/app/services/analysis.py` | Modificar — `BiomarkerRule`, `_has_negation`, `_find_matches_keywords`, `detect_biomarker_conflicts`, constantes, `BIOMARKER_RULES` |
| `backend/tests/test_analysis.py` | Modificar — agregar 10 tests nuevos |
| `docs/evaluation/golden-dataset.md` | Modificar — §2, §6, §8 |
| `docs/embedding-strategy.md` | Modificar — §10 |

### PR 2
| Archivo | Acción |
|---------|--------|
| `backend/scripts/build_golden_dataset.py` | Modificar — `_keyword_relevance` con guards replicados |

---

## PR 1 — Fix del Matcher de Producción

---

### Task 0: Crear worktree para PR 1

**Files:**
- No files touched — solo configuración de git

- [ ] **Step 1: Crear el worktree desde main**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield
git worktree add ../bio_shield-pr1-hardening -b pr1-biomarker-rules-hardening
```

Expected output:
```
Preparing worktree (new branch 'pr1-biomarker-rules-hardening')
HEAD is now at 74bf444 docs(spec): add biomarker rules hardening design spec
```

- [ ] **Step 2: Verificar que el worktree existe y está limpio**

```bash
git worktree list
```

Expected:
```
/Users/albertofragoso/Desktop/IA_engineer/bio_shield        74bf444 [main]
/Users/albertofragoso/Desktop/IA_engineer/bio_shield-pr1-hardening  74bf444 [pr1-biomarker-rules-hardening]
```

- [ ] **Step 3: Moverse al worktree para todo el trabajo de PR 1**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield-pr1-hardening
```

Todo el trabajo de PR 1 (Tasks 1–7) se ejecuta desde esta carpeta.

---

### Task 1: Escribir los 10 tests que deben fallar (RED)

**Files:**
- Modify: `backend/tests/test_analysis.py`

- [ ] **Step 1: Agregar imports necesarios al archivo de tests**

Abrir `backend/tests/test_analysis.py`. Al bloque de imports existente, agregar:

```python
from app.services.analysis import detect_biomarker_conflicts
```

El archivo ya importa `_find_matches_keywords` y `compute_semaphore`.

- [ ] **Step 2: Agregar los 10 tests al final del archivo**

```python
# ─────────────────────────────────────────────
# Negation detection
# ─────────────────────────────────────────────


def test_negation_trans_fat_free_no_match():
    """'Trans Fat Free' antes del keyword debe descartar el match."""
    biomarkers = [_bm("ldl", 160, "high")]
    ingredients = [_ing("Trans Fat Free Palm Oil Blend")]
    matches = _find_matches_keywords(biomarkers, ingredients)
    assert matches == []


def test_negation_sin_grasas_trans_no_match():
    """Negación en español ('sin') debe descartar el match."""
    biomarkers = [_bm("ldl", 160, "high")]
    ingredients = [_ing("Aceite sin grasas trans")]
    matches = _find_matches_keywords(biomarkers, ingredients)
    assert matches == []


# ─────────────────────────────────────────────
# Exclude list — polímeros industriales
# ─────────────────────────────────────────────


def test_exclude_petroleum_hydrocarbon_no_match():
    """Polímero industrial con 'hydrogenated' no debe alertar LDL."""
    biomarkers = [_bm("ldl", 160, "high")]
    ingredients = [_ing("Petroleum Hydrocarbon Resins (hydrogenated)")]
    matches = _find_matches_keywords(biomarkers, ingredients)
    assert matches == []


def test_exclude_sodium_bicarbonate_no_match():
    """Bicarbonato de sodio no debe alertar SODIUM."""
    biomarkers = [_bm("sodium", 150, "high")]
    ingredients = [_ing("Sodium bicarbonate")]
    matches = _find_matches_keywords(biomarkers, ingredients)
    assert matches == []


def test_exclude_potassium_salt_no_match():
    """'Potassium salt of fatty acid' no debe alertar SODIUM."""
    biomarkers = [_bm("sodium", 150, "high")]
    ingredients = [_ing("Potassium salt of fatty acid")]
    matches = _find_matches_keywords(biomarkers, ingredients)
    assert matches == []


# ─────────────────────────────────────────────
# GLUCOSE vs HBA1C — distinción temporal
# ─────────────────────────────────────────────


def test_glucose_dextrose_matches_glucose_not_hba1c():
    """'dextrose' (absorción rápida) → GLUCOSE sí, HBA1C no."""
    ingredients = [_ing("dextrose")]
    glucose_matches = _find_matches_keywords([_bm("glucose", 120, "high")], ingredients)
    hba1c_matches = _find_matches_keywords([_bm("hba1c", 7.5, "high")], ingredients)
    assert len(glucose_matches) == 1
    assert hba1c_matches == []


def test_hba1c_fructose_matches_hba1c_not_glucose():
    """'high fructose corn syrup' (carga crónica) → HBA1C sí, GLUCOSE no."""
    ingredients = [_ing("high fructose corn syrup")]
    glucose_matches = _find_matches_keywords([_bm("glucose", 120, "high")], ingredients)
    hba1c_matches = _find_matches_keywords([_bm("hba1c", 7.5, "high")], ingredients)
    assert glucose_matches == []
    assert len(hba1c_matches) == 1


# ─────────────────────────────────────────────
# POTASSIUM — keywords expandidos
# ─────────────────────────────────────────────


def test_potassium_dipotassium_matches():
    """'dipotassium phosphate' debe alertar POTASSIUM."""
    biomarkers = [_bm("potassium", 6.0, "high")]
    ingredients = [_ing("Dipotassium phosphate")]
    matches = _find_matches_keywords(biomarkers, ingredients)
    assert len(matches) == 1


def test_potassium_expanded_kcl_matches():
    """'KCl' (cloruro de potasio abreviado) debe alertar POTASSIUM."""
    biomarkers = [_bm("potassium", 6.0, "high")]
    ingredients = [_ing("KCl")]
    matches = _find_matches_keywords(biomarkers, ingredients)
    assert len(matches) == 1


# ─────────────────────────────────────────────
# Deduplicación en compute_semaphore
# ─────────────────────────────────────────────


def test_dedup_ldl_total_chol_single_alert():
    """Un ingrediente que matchea LDL y TOTAL_CHOL → una sola alerta."""
    biomarkers = [
        _bm("ldl", 160, "high"),
        _bm("total_cholesterol", 240, "high"),
    ]
    ingredients = [_ing("palm oil")]
    alerts = detect_biomarker_conflicts(ingredients, biomarkers)
    palm_oil_alerts = [a for a in alerts if a.ingredient == "palm oil"]
    assert len(palm_oil_alerts) == 1
```

- [ ] **Step 3: Verificar que los 10 tests fallan (RED)**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield-pr1-hardening/backend
python -m pytest tests/test_analysis.py -k "negation or exclude or glucose or hba1c or potassium or dedup" -v 2>&1 | tail -20
```

Expected: todos los 10 tests marcados como **FAILED**. Los tests de negación fallan porque actualmente `"Trans Fat Free Palm Oil Blend"` sí matchea; los de exclude fallan porque "hydrogenated" y "salt"/"sodium" matchean sin filtro; los de GLUCOSE/HBA1C fallan porque comparten keywords; los de POTASSIUM fallan porque "dipotassium" y "kcl" no están en las keywords; el de dedup falla porque se generan 2 alertas.

- [ ] **Step 4: Commit de los tests en rojo**

```bash
git add tests/test_analysis.py
git commit -m "test(analysis): add 10 failing tests for biomarker rules hardening

RED phase: negation detection, exclude list, GLUCOSE/HBA1C temporal
distinction, POTASSIUM expanded keywords, LDL+TOTAL_CHOL dedup"
```

---

### Task 2: Agregar `excludes`, `_has_negation` y constantes compartidas

**Files:**
- Modify: `backend/app/services/analysis.py`

- [ ] **Step 1: Agregar `excludes` al dataclass `BiomarkerRule`**

Localizar el dataclass (línea ~56). Reemplazar:

```python
@dataclass(frozen=True)
class BiomarkerRule:
    biomarker: CanonicalBiomarker
    direction: Literal["raises", "lowers"]  # effect of the ingredient on this biomarker
    keywords: tuple[str, ...]  # substrings to look for in ingredient names (lowercase)
    severity: ConflictSeverity
    message: str
    # Firing logic (derived from direction):
    #   raises → alert when classification=="high", watch when "normal"
    #   lowers → alert when classification=="low",  watch when "normal"
```

Por:

```python
@dataclass(frozen=True)
class BiomarkerRule:
    biomarker: CanonicalBiomarker
    direction: Literal["raises", "lowers"]  # effect of the ingredient on this biomarker
    keywords: tuple[str, ...]  # substrings to look for in ingredient names (lowercase)
    severity: ConflictSeverity
    message: str
    excludes: tuple[str, ...] = ()  # substrings that disqualify a keyword match
    # Firing logic (derived from direction):
    #   raises → alert when classification=="high", watch when "normal"
    #   lowers → alert when classification=="low",  watch when "normal"
```

- [ ] **Step 2: Agregar `_NEGATION_TERMS`, `_has_negation`, y constantes de lípidos**

Después de la línea `_STATUS_RANK = {...}` (línea ~52) y antes de `BiomarkerRule`, agregar:

```python
_NEGATION_TERMS = ("free", "without", "sin", "no ", "zero", "libre", "free of")


def _has_negation(text: str, keyword: str) -> bool:
    """Return True if a negation word appears in the 15 chars before `keyword` in `text`."""
    idx = text.find(keyword)
    if idx < 0:
        return False
    window = text[max(0, idx - 15) : idx]
    return any(neg in window for neg in _NEGATION_TERMS)


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

- [ ] **Step 3: Commit**

```bash
git add app/services/analysis.py
git commit -m "feat(analysis): add BiomarkerRule.excludes, _has_negation helper, lipid constants"
```

---

### Task 3: Actualizar `_find_matches_keywords` con los dos guards

**Files:**
- Modify: `backend/app/services/analysis.py:249-258`

- [ ] **Step 1: Reemplazar el loop de keywords en `_find_matches_keywords`**

Localizar el bloque interno (línea ~249):

```python
            matched_ingr: list[str] = []
            for ing in ingredients:
                ing_names = " ".join(filter(None, (ing.name, ing.canonical_name))).lower()
                if any(kw in ing_names for kw in rule.keywords):
                    matched_ingr.append(ing.canonical_name or ing.name)
```

Reemplazar por:

```python
            matched_ingr: list[str] = []
            for ing in ingredients:
                ing_names = " ".join(filter(None, (ing.name, ing.canonical_name))).lower()
                for kw in rule.keywords:
                    if kw not in ing_names:
                        continue
                    if _has_negation(ing_names, kw):
                        continue
                    if any(ex in ing_names for ex in rule.excludes):
                        continue
                    matched_ingr.append(ing.canonical_name or ing.name)
                    break  # un keyword match es suficiente por ingrediente
```

- [ ] **Step 2: Ejecutar los tests de negación para verificar que pasan**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield-pr1-hardening/backend
python -m pytest tests/test_analysis.py -k "negation" -v
```

Expected:
```
PASSED tests/test_analysis.py::test_negation_trans_fat_free_no_match
PASSED tests/test_analysis.py::test_negation_sin_grasas_trans_no_match
```

Los tests de exclude y POTASSIUM siguen fallando (las reglas aún no tienen `excludes` ni nuevos keywords).

- [ ] **Step 3: Verificar que los tests existentes no rompieron**

```bash
python -m pytest tests/test_analysis.py -k "not negation and not exclude and not glucose and not hba1c and not potassium and not dedup" -v
```

Expected: todos PASSED.

- [ ] **Step 4: Commit**

```bash
git add app/services/analysis.py
git commit -m "feat(analysis): add negation + exclude guards to _find_matches_keywords"
```

---

### Task 4: Actualizar `BIOMARKER_RULES` (las 9 reglas)

**Files:**
- Modify: `backend/app/services/analysis.py:68-157`

- [ ] **Step 1: Reemplazar el bloque completo de `BIOMARKER_RULES`**

Localizar `BIOMARKER_RULES: tuple[BiomarkerRule, ...] = (` (línea ~68) y reemplazar todo el bloque hasta el cierre `)` por:

```python
BIOMARKER_RULES: tuple[BiomarkerRule, ...] = (
    BiomarkerRule(
        biomarker=CanonicalBiomarker.LDL,
        direction="raises",
        keywords=_LIPID_RAISING_KEYWORDS,
        excludes=_INDUSTRIAL_HYDROGENATED_EXCLUDES,
        severity=ConflictSeverity.HIGH,
        message="LDL con grasa trans/saturada",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.TOTAL_CHOLESTEROL,
        direction="raises",
        keywords=_LIPID_RAISING_KEYWORDS,
        excludes=_INDUSTRIAL_HYDROGENATED_EXCLUDES,
        severity=ConflictSeverity.HIGH,
        message="Colesterol total con grasa trans/saturada",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.HDL,
        direction="lowers",
        keywords=("trans fat", "grasas trans", "hydrogenated", "aceite hidrogenado"),
        excludes=_INDUSTRIAL_HYDROGENATED_EXCLUDES,
        severity=ConflictSeverity.MEDIUM,
        message="HDL con grasas trans",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.GLUCOSE,
        direction="raises",
        keywords=(
            "dextrose",
            "dextrosa",
            "maltose",
            "maltosa",
            "refined sugar",
            "white sugar",
            "azúcar refinada",
            "glucose syrup",
            "jarabe de glucosa",
        ),
        severity=ConflictSeverity.HIGH,
        message="Glucosa con azúcares de absorción rápida",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.HBA1C,
        direction="raises",
        keywords=(
            "high fructose",
            "corn syrup",
            "jarabe de maíz",
            "fructose",
            "fructosa",
            "added sugar",
            "azúcar añadida",
        ),
        severity=ConflictSeverity.HIGH,
        message="HbA1c con azúcares de carga crónica",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.TRIGLYCERIDES,
        direction="raises",
        keywords=("fructose", "fructosa", "jarabe", "syrup", "added sugar"),
        severity=ConflictSeverity.MEDIUM,
        message="Triglicéridos con fructosa/jarabes",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.SODIUM,
        direction="raises",
        keywords=(
            "sodium chloride",
            "cloruro de sodio",
            "monosodium glutamate",
            "glutamato monosódico",
            "msg",
            "added salt",
            "sal de mesa",
            "table salt",
            "sodium",
            "sodio",
        ),
        excludes=(
            "potassium salt",
            "calcium salt",
            "magnesium salt",
            "fatty acid salt",
            "sodium bicarbonate",
            "sodium carbonate",
            "sodium silicate",
        ),
        severity=ConflictSeverity.MEDIUM,
        message="Sodio con ingredientes salinos",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.URIC_ACID,
        direction="raises",
        keywords=(
            "high fructose",
            "corn syrup",
            "fructose",
            "fructosa",
            "jarabe de maíz",
        ),
        severity=ConflictSeverity.MEDIUM,
        message="Ácido úrico con fructosa",
    ),
    BiomarkerRule(
        biomarker=CanonicalBiomarker.POTASSIUM,
        direction="raises",
        keywords=(
            "potassium chloride",
            "cloruro de potasio",
            "potassium",
            "potasio",
            "potásico",
            "kcl",
            "dipotassium",
            "potassic",
        ),
        severity=ConflictSeverity.LOW,
        message="Potasio con aditivos de potasio",
    ),
)
```

- [ ] **Step 2: Ejecutar los tests de exclude, GLUCOSE/HBA1C y POTASSIUM**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield-pr1-hardening/backend
python -m pytest tests/test_analysis.py -k "exclude or glucose or hba1c or potassium" -v
```

Expected: todos PASSED.

- [ ] **Step 3: Verificar suite completa (excepto dedup que aún falla)**

```bash
python -m pytest tests/test_analysis.py -k "not dedup" -v
```

Expected: todos PASSED.

- [ ] **Step 4: Commit**

```bash
git add app/services/analysis.py
git commit -m "feat(analysis): update BIOMARKER_RULES — excludes, temporal glucose/hba1c split, POTASSIUM expanded"
```

---

### Task 5: Deduplicar alertas en `detect_biomarker_conflicts`

**Files:**
- Modify: `backend/app/services/analysis.py:348-374`

- [ ] **Step 1: Reemplazar `detect_biomarker_conflicts` con versión deduplicada**

Localizar la función (línea ~348). Reemplazar el cuerpo completo:

```python
def detect_biomarker_conflicts(
    ingredients: list[IngredientResult],
    biomarkers: list | None,
) -> list[PersonalizedAlert]:
    """Return PersonalizedAlert list for ORANGE semaphore detection.

    Thin wrapper around _find_matches_keywords — sync, no semantic path.
    Deduplicates by ingredient: when multiple rules fire on the same ingredient,
    only the highest-severity alert is kept.
    """
    if not biomarkers:
        return []

    alerts: list[PersonalizedAlert] = []
    for bm, ingr_names, severity, _kind, _direction in _find_matches_keywords(
        biomarkers, ingredients
    ):
        name = bm.get("name") if isinstance(bm, dict) else getattr(bm, "name", None)
        value = bm.get("value") if isinstance(bm, dict) else getattr(bm, "value", None)
        name_val = name.value if (name is not None and hasattr(name, "value")) else str(name)
        for ingr in ingr_names:
            alerts.append(
                PersonalizedAlert(
                    ingredient=ingr,
                    biomarker_conflict=f"{name_val}={value}",
                    severity=severity,
                )
            )

    # Per-ingredient dedup: keep only highest-severity alert
    seen: dict[str, PersonalizedAlert] = {}
    for alert in alerts:
        prev = seen.get(alert.ingredient)
        if prev is None or _SEVERITY_RANK[alert.severity] > _SEVERITY_RANK[prev.severity]:
            seen[alert.ingredient] = alert
    return list(seen.values())
```

- [ ] **Step 2: Ejecutar el test de dedup**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield-pr1-hardening/backend
python -m pytest tests/test_analysis.py::test_dedup_ldl_total_chol_single_alert -v
```

Expected: PASSED.

- [ ] **Step 3: Ejecutar la suite completa**

```bash
python -m pytest tests/test_analysis.py -v
```

Expected: todos PASSED. Verificar que el count total sube en 10 respecto al baseline.

- [ ] **Step 4: Commit**

```bash
git add app/services/analysis.py
git commit -m "feat(analysis): dedup alerts by ingredient in detect_biomarker_conflicts"
```

---

### Task 6: Actualizar documentación

**Files:**
- Modify: `docs/evaluation/golden-dataset.md`
- Modify: `docs/embedding-strategy.md`

- [ ] **Step 1: Actualizar `golden-dataset.md` §2 — diagrama de Capa 1**

Localizar el bloque de Capa 1 en el diagrama ASCII (alrededor de la línea 29):

```
CAPA 1 — Domain Knowledge (confidence 0.95)
│
│  Fuente: BIOMARKER_RULES en analysis.py
│  Lógica: keyword match exacto en canonical_name o synonyms
│  Relevance: 5 (name match) | 4 (synonym match)
│  Cobertura: ~100% de los ingredientes con nombre relevante
```

Reemplazar por:

```
CAPA 1 — Domain Knowledge (confidence 0.95)
│
│  Fuente: BIOMARKER_RULES en analysis.py
│  Lógica: keyword match exacto en canonical_name o synonyms
│          + guard de negaciones ("trans fat free" → skip)
│          + guard de excludes (rule.excludes → skip polímeros industriales)
│  Nota: _keyword_relevance replica exactamente los guards de producción
│  Relevance: 5 (name match) | 4 (synonym match)
│  Cobertura: ~100% de los ingredientes con nombre relevante
```

- [ ] **Step 2: Actualizar `golden-dataset.md` §6 — cuándo re-construir**

Localizar la tabla de §6 (alrededor de la línea 228). Agregar una fila nueva:

```markdown
| Se modificaron `keywords`, `excludes`, o negation logic en reglas existentes | Re-construir Capas 1+2 (`--layers 1 2 --calibrate`) — el builder replica la lógica de producción |
```

- [ ] **Step 3: Actualizar `golden-dataset.md` §8 — limitaciones conocidas**

Localizar el punto 2 (alrededor de línea 278):

```
2. **Sesgos de BIOMARKER_RULES**: el ground truth de Capa 1 hereda cualquier omisión en las reglas. Si "coconut oil" no está en los keywords de LDL, no aparecerá como positivo aunque clínicamente debería.
```

Reemplazar por:

```
2. **Sesgos de BIOMARKER_RULES**: el ground truth de Capa 1 hereda cualquier omisión en las reglas. Si "coconut oil" no está en los keywords de LDL, no aparecerá como positivo aunque clínicamente debería. Los falsos positivos industriales (polímeros con "hydrogenated") están mitigados por el campo `excludes` de cada regla, que `_keyword_relevance` también respeta.
```

Localizar el punto 3 (alrededor de línea 281):

```
3. **Near-misses de Capa 2 (relevance=3)**: son candidatos a falsos positivos. El threshold de 0.72 es conservador; aun así, revisar los near-misses periódicamente para identificar falsos positivos sistemáticos.
```

Reemplazar por:

```
3. **Near-misses de Capa 2 (relevance=3)**: son candidatos a falsos positivos. El threshold de 0.72 es conservador; aun así, revisar los near-misses periódicamente. GLUCOSE y HBA1C ahora tienen keywords diferenciados por escala temporal, reduciendo near-misses cruzados entre ambas reglas.
```

- [ ] **Step 4: Actualizar `embedding-strategy.md` §10**

Localizar el segundo párrafo de §10 que menciona el ejemplo de query (alrededor de línea 145):

```
El re-ranking semántico de `find_ingredient_matches` embeddea el texto canónico de la regla clínica (e.g., `"ldl raises: trans fat, hydrogenated, palm oil"`) y lo compara contra los templates de ChromaDB.
```

Reemplazar por:

```
El re-ranking semántico de `find_ingredient_matches` embeddea el texto canónico de la regla clínica (e.g., `"ldl raises: trans fat, grasas trans, hydrogenated, saturated fat, palm oil, aceite de palma"`) y lo compara contra los templates de ChromaDB. El query text se construye solo de `rule.keywords`; el campo `rule.excludes` opera en el matcher de texto pero no forma parte del embedding.
```

- [ ] **Step 5: Commit**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield-pr1-hardening
git add docs/evaluation/golden-dataset.md docs/embedding-strategy.md
git commit -m "docs: update golden-dataset and embedding-strategy for hardened BIOMARKER_RULES

- golden-dataset §2: mention excludes/negation guards in Capa 1
- golden-dataset §6: add rebuild trigger for rule modifications
- golden-dataset §8: mark industrial FP and glucose/hba1c as mitigated
- embedding-strategy §10: clarify excludes not part of query text"
```

---

### Task 7: Verificación final y PR de PR 1

**Files:**
- No nuevos archivos

- [ ] **Step 1: Ejecutar suite completa de tests del backend**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield-pr1-hardening/backend
python -m pytest tests/ -v --tb=short
```

Expected: todos PASSED. Si alguno falla, corregir antes de continuar.

- [ ] **Step 2: Crear PR en GitHub**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield-pr1-hardening
gh pr create \
  --title "feat(analysis): harden BIOMARKER_RULES — excludes, negation, dedup" \
  --body "$(cat <<'EOF'
## Summary

- Add `excludes: tuple[str, ...]` to `BiomarkerRule` (default empty, backward compatible)
- Add `_has_negation()` helper: look-back 15 chars for negation words before a keyword
- Update `_find_matches_keywords` with negation + exclude guards
- Factor `_LIPID_RAISING_KEYWORDS` and `_INDUSTRIAL_HYDROGENATED_EXCLUDES` constants
- Update all 9 `BIOMARKER_RULES`: excludes for industrial polymers, GLUCOSE/HBA1C temporal split, POTASSIUM expanded keywords, SODIUM specific keywords + excludes
- Dedup alerts by ingredient in `detect_biomarker_conflicts` (highest severity wins)
- Update docs: golden-dataset.md §2/§6/§8, embedding-strategy.md §10

## Test plan

- [ ] `pytest tests/test_analysis.py -v` — all 10 new tests + existing suite green
- [ ] "Trans Fat Free Palm Oil" → no LDL alert
- [ ] "Petroleum Hydrocarbon Resins (hydrogenated)" → no LDL alert
- [ ] "Sodium bicarbonate" → no SODIUM alert
- [ ] "dextrose" → GLUCOSE alert, no HBA1C alert
- [ ] "high fructose corn syrup" → HBA1C alert, no GLUCOSE alert
- [ ] "dipotassium phosphate" → POTASSIUM alert
- [ ] "palm oil" with LDL + TOTAL_CHOL → single alert

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Anotar el URL del PR**

Copiar el URL que devuelve el comando anterior. El PR de PR 2 se abrirá solo después de que este sea mergeado.

---

## PR 2 — Golden Dataset Rebuild

> ⚠️ **Prerequisito:** PR 1 debe estar mergeado en `main` antes de comenzar este PR.

---

### Task 8: Crear worktree para PR 2

**Files:**
- No files touched

- [ ] **Step 1: Verificar que PR 1 está mergeado y main está actualizado**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield
git fetch origin
git pull origin main
git log --oneline -5
```

Expected: el commit de PR 1 aparece en el log de main.

- [ ] **Step 2: Crear worktree desde main actualizado**

```bash
git worktree add ../bio_shield-pr2-dataset -b pr2-golden-dataset-rebuild
```

- [ ] **Step 3: Moverse al worktree**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield-pr2-dataset
```

Todo el trabajo de PR 2 (Tasks 9–11) se ejecuta desde esta carpeta.

- [ ] **Step 4: Limpiar worktree de PR 1 (ya no se necesita)**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield
git worktree remove ../bio_shield-pr1-hardening
```

---

### Task 9: Actualizar `_keyword_relevance` en `build_golden_dataset.py`

**Files:**
- Modify: `backend/scripts/build_golden_dataset.py:76-95`

- [ ] **Step 1: Agregar import de `_has_negation`**

Localizar el bloque de imports de `app.services` (alrededor de línea 47):

```python
from app.services.analysis import BIOMARKER_RULES, BiomarkerRule
```

Reemplazar por:

```python
from app.services.analysis import BIOMARKER_RULES, BiomarkerRule, _has_negation
```

- [ ] **Step 2: Reemplazar `_keyword_relevance` completa**

Localizar la función (línea ~76). Reemplazar todo el cuerpo:

```python
def _keyword_relevance(rule: BiomarkerRule, ingredient: Ingredient) -> tuple[int, str | None]:
    """Return (relevance_score, matched_keyword) using rule keywords against the ingredient.

    Replicates production guards from _find_matches_keywords:
      - rule.excludes: if any exclude term is in the name, skip entirely
      - _has_negation: if a negation word precedes the keyword, skip it

    Scores:
      5 — exact keyword in canonical_name
      4 — exact keyword in a synonym
      0 — no match
    """
    name_lower = (ingredient.canonical_name or "").lower()

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

- [ ] **Step 3: Commit**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield-pr2-dataset
git add backend/scripts/build_golden_dataset.py
git commit -m "feat(golden-dataset): replicate excludes + negation guards in _keyword_relevance

Layer 1 now uses identical matching logic as production _find_matches_keywords,
eliminating industrial false positives from the ground truth."
```

---

### Task 10: Rebuild del golden dataset y calibración

**Files:**
- Modify: `backend/data/golden/golden_dataset.json` (regenerado)

- [ ] **Step 1: Activar entorno virtual**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield-pr2-dataset/backend
source .venv/bin/activate
```

- [ ] **Step 2: Ejecutar rebuild completo con calibración**

```bash
python -m scripts.build_golden_dataset --calibrate
```

Expected output (valores aproximados — los exactos dependerán del estado de la DB):
```
✓ Golden dataset written to data/golden/golden_dataset.json
  Queries  : 9
  Judgments: <número menor que 327 — polímeros industriales eliminados>
  Avg conf : <mayor que 0.83 — menos near-misses contaminados>
  Layers   : layer1_domain_knowledge, layer2_embedding_retrieval, layer3_gemini_variations

✓ Baselines calibrated (90% of observed metrics):
  ndcg_at_5_baseline             <valor>  (observed: <valor>)
  mrr_at_10_baseline             <valor>  (observed: <valor>)
  precision_at_3_baseline        <valor>  (observed: <valor>)
  recall_at_10_baseline          <valor>  (observed: <valor>)
```

Si ChromaDB no está disponible en el entorno, usar modo offline:
```bash
python -m scripts.build_golden_dataset --skip-gemini --calibrate
```

- [ ] **Step 3: Verificar que el evaluador no detecta regresiones**

```bash
python -m scripts.evaluate_rag --fail-on-regression
```

Expected: exit code 0 y salida con `✅ All metrics above baseline.`

Si alguna métrica falla: **no mergear**. Investigar qué regla causó la regresión comparando el reporte JSON con el dataset anterior antes de continuar.

- [ ] **Step 4: Commit del dataset recalibrado**

```bash
git add data/golden/golden_dataset.json
git commit -m "data(golden): rebuild + calibrate dataset with hardened BIOMARKER_RULES

- Layer 1 now excludes industrial polymers and negated ingredients
- GLUCOSE/HBA1C have distinct ground truth judgments
- POTASSIUM has expanded positive judgments
- Baselines recalibrated to 90% of observed metrics on clean ground truth"
```

---

### Task 11: Verificación final y PR de PR 2

**Files:**
- No nuevos archivos

- [ ] **Step 1: Ejecutar evaluate_rag una vez más para confirmar**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield-pr2-dataset/backend
python -m scripts.evaluate_rag
```

Expected: `status: PASS` en el JSON del reporte.

- [ ] **Step 2: Crear PR en GitHub**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield-pr2-dataset
gh pr create \
  --title "data(golden): rebuild dataset with hardened BIOMARKER_RULES" \
  --body "$(cat <<'EOF'
## Summary

- `_keyword_relevance` now replicates production guards: `rule.excludes` check + `_has_negation` before accepting a Layer 1 positive
- Rebuilt golden dataset: Layer 1 judgments no longer include industrial polymers (Petroleum Hydrocarbon Resins, etc.)
- GLUCOSE and HBA1C have distinct ground truth (temporal split from PR 1)
- POTASSIUM has expanded positive judgments
- Baselines recalibrated to 90% of observed metrics on clean ground truth

## Test plan

- [ ] `python -m scripts.evaluate_rag --fail-on-regression` exits 0
- [ ] `total_judgments` in metadata is lower than previous 327 (industrial FP removed)
- [ ] `avg_confidence` is higher than previous 0.83

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Limpiar worktree de PR 2 tras merge**

Una vez mergeado PR 2:

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield
git worktree remove ../bio_shield-pr2-dataset
git pull origin main
```

---

## Criterios de Aceptación Globales

| Criterio | Cómo verificar |
|----------|---------------|
| `"Trans Fat Free Palm Oil"` → no alerta LDL | `test_negation_trans_fat_free_no_match` PASSED |
| Polímeros industriales con "hydrogenated" → no alerta | `test_exclude_petroleum_hydrocarbon_no_match` PASSED |
| `"Sodium bicarbonate"` → no alerta SODIUM | `test_exclude_sodium_bicarbonate_no_match` PASSED |
| `"dextrose"` → GLUCOSE sí, HBA1C no | tests temporales PASSED |
| `"dipotassium phosphate"` → POTASSIUM alerta | `test_potassium_dipotassium_matches` PASSED |
| Un ingrediente LDL+TOTAL_CHOL → una sola alerta | `test_dedup_ldl_total_chol_single_alert` PASSED |
| Suite completa backend verde | `pytest tests/` green |
| Dataset rebuild sin regresión | `evaluate_rag --fail-on-regression` exit 0 |
| Docs actualizados | golden-dataset.md §2/§6/§8, embedding-strategy.md §10 |
