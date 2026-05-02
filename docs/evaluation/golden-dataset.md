# Golden Dataset — RAG Evaluation

**Versión:** 1.0  
**Última actualización:** 2026-04-28  
**Audiencia:** Backend / DevOps  
**Ciclo de vida:** Re-construir cada vez que cambie el embedding model o se agreguen >10 nuevos `BIOMARKER_RULES`

---

## 1. ¿Qué es y por qué existe?

El golden dataset es el **ground truth** para medir si la búsqueda semántica (BGE-M3 + ChromaDB) devuelve los ingredientes correctos para cada regla clínica de biomarcador.

Sin él, no hay forma de saber si un cambio en el modelo de embeddings, en los ingredientes indexados, o en los umbrales de similitud **mejoró o degradó** la calidad del RAG.

**Qué mide:** la capacidad del sistema para recuperar ingredientes clínicamente relevantes para un biomarcador dado, aunque la query use sinónimos o vocabulario diferente a los keywords exactos de `BIOMARKER_RULES`.

**Qué NO mide:** calidad de OCR, calidad de los insights generados por Gemini, o cobertura del catálogo de ingredientes.

---

## 2. Arquitectura: 3 capas automáticas

No requiere anotadores humanos. La confianza viene de fuentes independientes.

```
CAPA 1 — Domain Knowledge (confidence 0.95)
│
│  Fuente: BIOMARKER_RULES en analysis.py
│  Lógica: keyword match exacto en canonical_name o synonyms
│  Relevance: 5 (name match) | 4 (synonym match)
│  Cobertura: ~100% de los ingredientes con nombre relevante
│  Nota: replica los mismos dos guards del matcher de producción:
│    - detección de negaciones via _has_negation (ventana ±15 chars)
│    - exclusión de falsos positivos industriales via rule.excludes
│
├─► CAPA 2 — Embedding Retrieval (confidence 0.80–0.90)
│
│  Fuente: ChromaDB (BGE-M3, 1024-dim)
│  Lógica: query top-20, comparar hits contra Capa 1
│  Nuevos: ingredientes con cosine ≥ 0.72 sin match en Capa 1
│           → "near-miss semántico" (relevance=3)
│  Valida: recall de los embeddings contra el ground truth de Capa 1
│
└─► CAPA 3 — Gemini Variations (confidence 0.70–0.85)

   Fuente: Gemini genera 3 phrasings alternativos por regla
   Lógica: correr cada variante en ChromaDB, aceptar si overlap
           con positivos de Capa 1 ≥ 50%
   Valida: robustez del RAG ante vocabulario diferente
   Costo: ~24 requests Gemini (dentro free tier)
```

**Gotcha de diseño:** Capa 1 y Capa 2 son independientes entre sí — Capa 1 usa SQL/keyword matching (sin embeddings), Capa 2 usa embeddings. La coincidencia entre ambas es evidencia de calidad, no circularidad.

---

## 3. Comandos

### Construir el golden dataset (primera vez)

**Siempre usar `--calibrate` en el primer build.** Esto corre el evaluador contra el
dataset recién construido y escribe los baselines como 90% de las métricas observadas,
evitando que reglas de regresión disparen falsas alarmas desde el primer día.

```bash
cd backend

# Completo con calibración automática (capas 1+2+3, ~10 minutos)
python -m scripts.build_golden_dataset --calibrate

# Modo offline — sin Gemini, capas 1+2 (~3 minutos)
python -m scripts.build_golden_dataset --skip-gemini --calibrate

# Solo capa 1 — instantáneo, cero dependencias
python -m scripts.build_golden_dataset --layers 1 --calibrate

# Ruta personalizada
python -m scripts.build_golden_dataset --output data/golden/v2_dataset.json --calibrate
```

Output esperado:
```
✓ Golden dataset written to data/golden/golden_dataset.json
  Queries  : 9
  Judgments: ~181 (depende de ingredientes en DB)
  Avg conf : 0.950
  Layers   : layer1_domain_knowledge, layer2_embedding_retrieval, layer3_gemini_variations

✓ Baselines calibrated (90% of observed metrics):
  ndcg_at_5_baseline             0.5848  (observed: 0.6498)
  mrr_at_10_baseline             0.7333  (observed: 0.8148)
  precision_at_3_baseline        0.3334  (observed: 0.3704)
  recall_at_10_baseline          0.4730  (observed: 0.5256)
```

**Por qué los baselines son más bajos que los valores "industria":** El dataset de EFSA
(4595 ingredientes) contiene principalmente sustancias técnicas industriales. El RAG los
ignora correctamente para queries clínicas, lo que baja Precision@3 y Recall@10 respecto
a benchmarks de NLP general. Los baselines calibrados reflejan la realidad del catálogo.

### Evaluar el RAG actual

```bash
cd backend

# Evaluación completa con reporte JSON
python -m scripts.evaluate_rag

# Para CI/CD — exit 1 si alguna métrica baja del baseline
python -m scripts.evaluate_rag --fail-on-regression

# Dataset alternativo
python -m scripts.evaluate_rag --dataset data/golden/v2_dataset.json
```

Output esperado:
```
──────────────────────────────────────────────────
BioShield RAG Evaluation — 2026-04-28
──────────────────────────────────────────────────
  NDCG@5       : 0.8200  (baseline ≥ 0.70)
  MRR@10       : 0.7400  (baseline ≥ 0.60)
  Precision@3  : 0.8600  (baseline ≥ 0.75)
  Recall@10    : 0.9100  (baseline ≥ 0.80)
──────────────────────────────────────────────────
✅ All metrics above baseline.

Per-biomarker NDCG@5:
  glucose              0.7600
  hba1c                0.7800
  hdl                  0.8900
  ldl                  0.8900
  ...
```

---

## 4. Estructura del JSON generado

```
backend/data/golden/
├── golden_dataset.json      ← golden dataset (gitignored)
├── eval_20260428_143022.json ← reporte de evaluación (gitignored)
└── .gitkeep                  ← hace tracking del directorio vacío
```

`golden_dataset.json` schema:
```jsonc
{
  "metadata": {
    "version": "1.0",
    "created_at": "2026-04-28T...",
    "bge_model": "BAAI/bge-m3",
    "chromadb_size": 4637,
    "total_queries": 8,
    "total_judgments": 145,
    "avg_confidence": 0.882,
    "layers_built": ["layer1_domain_knowledge", "layer2_embedding_retrieval", "layer3_gemini_variations"]
  },
  "queries": [
    {
      "query_id": "ldl_raises_000",
      "biomarker": "ldl",
      "direction": "raises",
      "severity": "high",
      "query_text": "ldl raises: trans fat, grasas trans, aceite hidrogenado, ...",
      "layer": "layer1_domain_knowledge",
      "layer2_retrieval_stats": {
        "true_positives": 3,
        "false_positives": 12,
        "near_misses": 2
      },
      "layer3_variations": [
        {
          "variation_text": "foods that raise bad cholesterol",
          "l1_overlap": 0.75,
          "top_hits": [...]
        }
      ],
      "judgments": [
        {
          "ingredient_id": "...",
          "ingredient_name": "Trans Fat",
          "entity_id": "fda_trans_fat_001",
          "relevance": 5,
          "confidence": 0.95,
          "match_type": "keyword_exact",
          "matched_keyword": "trans fat"
        }
      ]
    }
  ],
  "thresholds": {
    "semantic_similarity": 0.65,
    "layer2_near_miss_min": 0.72,
    "layer3_variation_min_overlap": 0.50,
    "ndcg_at_5_baseline": 0.70,
    "mrr_at_10_baseline": 0.60,
    "precision_at_3_baseline": 0.75,
    "recall_at_10_baseline": 0.80
  }
}
```

---

## 5. Métricas explicadas

| Métrica | Qué mide | Baseline | Industria "bueno" |
|---|---|---|---|
| **NDCG@5** | ¿Los 5 mejores resultados están ordenados por relevancia? | 0.70 | > 0.70 |
| **MRR@10** | ¿El primer resultado correcto está cerca del top? | 0.60 | > 0.60 |
| **Precision@3** | ¿Cuántos de los 3 primeros son relevantes? | 0.75 | > 0.75 |
| **Recall@10** | ¿Cuántos positivos recupera en top-10? | 0.80 | > 0.80 |

**Escala de relevance en judgments:**

| Score | Significado | Fuente |
|---|---|---|
| 5 | Keyword exacto en canonical_name | Capa 1 |
| 4 | Keyword exacto en synonym | Capa 1 |
| 3 | Near-miss semántico (cosine ≥ 0.72, sin keyword) | Capa 2 |
| 0 | No relevante | implícito |

---

## 6. Cuándo re-construir el dataset

| Evento | Acción |
|---|---|
| Se cambió el embedding model (BGE-M3 → otro) | Re-construir + Re-seed ChromaDB |
| Se añadieron ≥ 10 nuevas `BIOMARKER_RULES` | Re-construir |
| Se hizo re-seed de ChromaDB (nuevos ingredientes) | Re-construir Capa 2 (`--layers 2 3`) |
| Evaluación muestra regresión > 5% en NDCG@5 | Investigar antes de re-construir |
| Rutina trimestral | Re-construir completo |
| Se modificaron `keywords`, `excludes`, o `negation logic` en reglas existentes | Re-construir (los scores de relevancia de Capa 1 cambian) |

```bash
# Re-construir solo capas 2 y 3 (reutiliza Capa 1 del JSON existente)
# ⚠️ El script actual no soporta re-uso parcial aún — re-corre todo
python -m scripts.build_golden_dataset --skip-gemini
```

---

## 7. Interpretando regresiones

### Regresión en NDCG@5 (ranking worse)
```
NDCG@5: 0.58  (Δ -0.12 vs baseline 0.70) ← FALLA
```

Causas comunes:
1. **ChromaDB corrupto** — verificar con `collection_size()`
2. **Cambio en embed template** (`rag.py::build_embedding_template`) sin re-seed
3. **BGE-M3 model cache corrupto** — borrar `~/.cache/huggingface/` y reiniciar

### Regresión en Recall@10 (missing positives)
```
Recall@10: 0.62  (Δ -0.18 vs baseline 0.80) ← FALLA
```

Causas comunes:
1. **Threshold `_SEMANTIC_SIMILARITY_THRESHOLD` muy alto** — bajar de 0.65 a 0.60
2. **Ingrediente faltante en DB** — correr `python -m scripts.seed_rag`
3. **Query text cambió** — verificar que `BIOMARKER_RULES` no fue modificado

### Regresión solo en un biomarker

```
glucose: ndcg_at_5=0.45 ← solo glucose falla
```

Indica un problema específico de cobertura (pocos ingredientes relacionados con glucosa en DB). Correr re-seed con `--live` para obtener más datos.

---

## 8. Limitaciones conocidas

1. **Cobertura del curated seed**: con el seed local (20 ingredientes FDA + 56 Codex), los judgments de Capa 1 son pocos. El `--live` seed (4637 ingredientes) produce un dataset mucho más representativo.

2. **Sesgos de BIOMARKER_RULES**: el ground truth de Capa 1 hereda cualquier omisión en las reglas. Si "coconut oil" no está en los keywords de LDL, no aparecerá como positivo aunque clínicamente debería.

3. **Near-misses de Capa 2 (relevance=3)**: son candidatos a falsos positivos. El threshold de 0.72 es conservador; aun así, revisar los near-misses periódicamente para identificar falsos positivos sistemáticos.

4. **Variantes de Gemini (Capa 3)**: solo validan si las variantes *recuperan* los mismos ingredientes, no si las variantes son clínicamente correctas. Una variante incorrecta que casualmente recupere los mismos ingredientes sería aceptada.

5. **No mide PHI exposure**: el golden dataset no verifica que los valores de biomarcadores del usuario nunca se embedden. Ese control está en `analysis.py::find_ingredient_matches` (solo se embeddea el texto estático de la regla).

6. ~~**Falsos positivos industriales**~~ **(mitigado)**: términos como "hydrogenated" en polímeros petroquímicos ya no generan matches gracias al guard `rule.excludes` (lista de subcadenas descalificadoras como "petroleum", "resin", "copolymer").

7. ~~**Solapamiento GLUCOSE/HBA1C**~~ **(mitigado)**: dextrose/glucose syrup y fructose/corn syrup ya no se solapan entre ambos biomarcadores — los keyword sets están separados: dextrose/glucose syrup → GLUCOSE (spike agudo); fructose/corn syrup → HBA1C (carga crónica).

8. **Nota sobre `avg_confidence`:** Al eliminar falsos positivos de Capa 1 (confianza ~0.95), la proporción de near-misses de Capa 2 (confianza 0.65–0.72) aumenta en el mix, lo que puede reducir `avg_confidence` aun cuando la calidad del ground truth mejora. No es una regresión — es un artefacto de medición causado por el desplazamiento en la distribución de capas.

---

## 9. Integración con CI/CD

Agregar al pipeline (GitHub Actions, Render deploy hooks):

```yaml
# .github/workflows/rag-eval.yml
- name: Evaluate RAG quality
  run: |
    cd backend
    python -m scripts.evaluate_rag --fail-on-regression
  env:
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
    USE_LOCAL_EMBEDDINGS: "true"
```

El script devuelve exit code 1 si alguna métrica está bajo baseline, bloqueando el deploy. Útil para detectar regresiones causadas por re-seeds o cambios en el template de embeddings.

---

## 10. Decisiones de diseño

| Decisión | Alternativa | Razón |
|---|---|---|
| **Capa 1 basada en BIOMARKER_RULES** | Anotadores humanos | Las reglas YA son conocimiento experto codificado; no hay circularidad |
| **E5-Large excluido del consenso** | BGE-M3 + E5-Large + Gemini | E5 requiere 500MB adicional; cosine scores entre espacios no son comparables directamente; costo no justificado |
| **Near-miss threshold 0.72** | 0.65 (production threshold) | Más estricto que el threshold de producción para evitar falsos positivos en el ground truth |
| **Docs en `docs/evaluation/`** | Sección en `docs/embedding-strategy.md` | El dataset tiene lifecycle independiente (re-construir cada trimestre) y lo usa DevOps/QA, no solo el backend lead |
| **Reportes JSON gitignored** | Tracked en git | Los reportes son volátiles (crecen con cada eval); el schema y el golden dataset son los que importan |
