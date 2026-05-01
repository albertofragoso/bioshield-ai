# Estrategia de Embeddings — BioShield AI

**Versión:** 2.0 · **Última actualización:** 2026-04-28

Documento que consolida las decisiones de embedding para el RAG regulatorio.
Complementa a `data-sources.md` (fuentes) y `architecture.md` (tabla `ingredients`).

---

## 1. Modelo de embeddings

| Capa | Modelo | Dimensión | Trigger |
|---|---|---|---|
| **Primaria** | `BAAI/bge-m3` (sentence-transformers, local) | 1024 | `USE_LOCAL_EMBEDDINGS=true` (default) |
| **Fallback API** | `gemini-embedding-001` (Gemini API) | 768 | `USE_LOCAL_EMBEDDINGS=false` |

**Nota importante:** las dimensiones difieren (1024 vs 768). Cambiar entre modelos requiere re-indexar la colección Chroma completa — no es hot-swappable. Ver §Migración en `docs/runbooks/embeddings-fallback.md`. Además, regenerar el snapshot de ChromaDB usado en los tests de integración E2E: ver `tests/fixtures/chroma-seed/README.md`.

**Gemini API** sigue siendo necesaria para Vision (OCR de etiquetas) y generación de insights personalizados, pero ya **no** para embeddings cuando `USE_LOCAL_EMBEDDINGS=true`.

---

## 2. Chunking

- **Chunk size:** 512 tokens
- **Overlap:** 50 tokens (≈10%)
- **Splitter:** `RecursiveCharacterTextSplitter` (LangChain)
- **Preservación semántica:** nunca fragmentar tablas de límites regulatorios ni tablas de sinónimos. Cuando el registro fuente excede 512 tokens, priorizar división por secciones (`<hazard>`, `<usage_limits>`, `<references>`).

Resuelve la inconsistencia marcada en el review previo (256 vs 512):

> El **chunk fuente** tiene 512 tokens (lo que se guarda en `document` de Chroma).
> El **embedding template** es el texto corto (~256 tokens) que se vectoriza.
> Son artefactos distintos — el template es un resumen estructurado para ranking.

---

## 3. Template de embedding (lo que se vectoriza)

Cada registro de ingrediente genera un texto normalizado para embedding:

```
[ID: {entity_id}] [Name: {canonical_name}] [Status: FDA:{fda_status}/EFSA:{efsa_status}/Codex:{codex_status}] [Risk: {hazard_note}] [Context: {usage_limits}]
```

Ejemplo real:
```
[ID: CAS:13463-67-7] [Name: Titanium Dioxide] [Status: FDA:APPROVED/EFSA:BANNED/Codex:RESTRICTED] [Risk: Genotoxicity positive (EFSA 2021)] [Context: 1% max concentration pre-ban]
```

**Reglas:**
- Orden estricto de campos (ID → Name → Status → Risk → Context).
- Campos ausentes se elide con `N/A`: `[Risk: N/A]`.
- Máximo 256 tokens — si se excede, truncar `Context` (último campo).

---

## 4. Metadata en ChromaDB

Cada registro se indexa con metadata para filtrado rápido:

```python
{
  "entity_id": "CAS:13463-67-7",
  "canonical_name": "Titanium Dioxide",
  "cas_number": "13463-67-7",
  "e_number": "E171",
  "region": "GLOBAL",          # US | EU | GLOBAL
  "source": "FDA_EAFUS",       # la fuente que produjo este chunk
  "conflict_flag": true,       # hay conflicto regulatorio detectado
  "severity": "HIGH",          # HIGH | MEDIUM | LOW | null
  "data_version": "2026.04.18",
}
```

**Colección única:** `bioshield_ingredients` (configurable vía `CHROMA_COLLECTION_NAME`).

---

## 5. Retrieval híbrido

**Score final:**
```
score = 0.7 * vector_similarity + 0.3 * bm25_score
```

- **Vector search:** top-20 de Chroma por similitud coseno.
- **BM25:** `rank_bm25.BM25Okapi` sobre `canonical_name + synonyms + hazard_note` (corpus cargado en memoria desde SQL al arranque; re-build en cada ingesta).
- **Re-ranking final:** top-5 post-scoring.
- **Filtros por metadata:** se aplican ANTES del scoring (ej: `region == 'EU'` para usuarios en UE).

Ver `services/retrieval.py`.

---

## 6. Entity Resolution

Cuando un ingrediente llega de OFF/Gemini como texto libre:

| Estrategia | Confianza | Acción |
|---|---|---|
| Match exacto por **CAS** (regex `\d{2,7}-\d{2}-\d`) | 1.0 | Usar directo |
| Match exacto por **E-number** (regex `E\d{3,4}`) | 0.95 | Usar directo |
| Fuzzy match (RapidFuzz `token_sort_ratio`) ≥ 85% | 0.7–0.9 | Usar con flag de confianza |
| Fuzzy match 60–85% | 0.6–0.7 | Encolar para HITL (`hitl_queue` flag) |
| < 60% | — | Rechazar, marcar ingrediente como no resuelto |

El umbral HITL de 0.7 es **inicial/arbitrario**. Plan de calibración en
`backend/reviews/18-04.md` (requiere 200+ ground-truth samples).

---

## 7. Fallback chain

Orden de degradación cuando falla el path principal:

1. **BGE-M3 local healthy** → embedding local (1024-dim), vector search Chroma.
2. **BGE-M3 falla** (OOM, modelo no cacheado) → degradar a BM25.
3. **Chroma unreachable** → BM25 puro sobre SQL (`rank_bm25` in-process).
4. **Todo falla** → degraded response: `risk_level: "UNKNOWN"`, `semaphore: GRAY`, error log estructurado.

Fallback Gemini embedding (768-dim): solo disponible con `USE_LOCAL_EMBEDDINGS=false`. Requiere re-seed previo con Gemini para tener la colección a 768-dim.

---

## 8. Ingestion pipeline (resumen)

Ver `services/ingestion/` para detalles:

1. **Download** fuente (FDA Excel, EFSA Zenodo API, Codex scraping).
2. **Checksum** SHA-256 para `ingestion_log.source_checksum`.
3. **Parse** → modelo canónico (`ingredient_metadata`).
4. **Upsert** en `ingredients` + `regulatory_status` por `entity_id`.
5. **Generate embedding template** (§3) → `embed_text()` → Chroma upsert.
6. **Conflict detection** (`services/conflicts.py`) → poblar tabla `conflicts`.
7. **Log** en `ingestion_log` con status `SUCCESS`/`PARTIAL`/`FAILED`.

Trigger: `python -m scripts.seed_rag` (idempotente).

---

## 10. Limitaciones del semantic matching biomarker × ingrediente

El re-ranking semántico de `find_ingredient_matches` embeddea el texto canónico de la regla clínica (e.g., `"ldl raises: trans fat, hydrogenated, palm oil"`) y lo compara contra los templates de ChromaDB.

**Limitación clave:** los templates regulatorios codifican información de **estatus y riesgo regulatorio** (FDA/EFSA/Codex), no propiedades clínicas. La similitud coseno entre una query clínica y un template regulatorio puede ser baja (~0.40–0.55). El path semántico aporta principalmente:

- Captura de **sinónimos y variantes de nombre** no presentes en los keywords.
- Mejor recall para ingredientes con múltiples denominaciones internacionales.

**Lo que NO hace:** inferir nuevas relaciones clínicas biomarker-ingrediente no modeladas en `BIOMARKER_RULES`.

**Threshold actual:** `_SEMANTIC_SIMILARITY_THRESHOLD = 0.65`. Calibrar con ground truth antes de ajustar este valor.

**Garantía de privacidad:** los valores reales del biomarcador del usuario (ej. `ldl=160`) NUNCA se embeddean. Solo se embeddea el texto canónico de la regla (`"ldl raises: trans fat, hydrogenated..."`), que es código estático sin PHI.

---

## 9. Métricas de calidad (propuestas)

Todavía sin implementación de tracking; objetivos iniciales:

- **Recall@5** ≥ 0.85 en ground-truth de 50 aditivos controversiales (E171, aspartame, BHA, etc.).
- **Precision@3** ≥ 0.80.
- **Latencia p95** de hybrid retrieval < 400ms por query.

Dataset de evaluación pendiente — documentado en `reviews/18-04.md`.
