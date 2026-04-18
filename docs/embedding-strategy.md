# Estrategia de Embeddings — BioShield AI

**Versión:** 1.0 · **Última actualización:** 2026-04-18

Documento que consolida las decisiones de embedding para el RAG regulatorio.
Complementa a `data-sources.md` (fuentes) y `architecture.md` (tabla `ingredients`).

---

## 1. Modelo de embeddings

| Capa | Modelo | Dimensión | Trigger |
|---|---|---|---|
| **Primaria** | `gemini-embedding-001` (API Gemini) | 768 | `USE_LOCAL_EMBEDDINGS=false` (default) |
| **Fallback local** | `BAAI/bge-m3` (sentence-transformers) | 1024 | `USE_LOCAL_EMBEDDINGS=true` o API caída |

**Nota importante:** las dimensiones difieren. Cambiar de Gemini a BGE-M3 requiere re-indexar la colección Chroma completa (no es hot-swappable).

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

1. **Gemini API healthy** → embedding via API, vector search Chroma.
2. **Gemini rate-limited** → retry exponencial (100ms, 200ms, 400ms).
3. **Chroma unreachable** → BM25 puro sobre SQL (`rank_bm25` in-process).
4. **Todo falla** → degraded response: `risk_level: "UNKNOWN"`, `semaphore: GRAY`, error log estructurado.

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

## 9. Métricas de calidad (propuestas)

Todavía sin implementación de tracking; objetivos iniciales:

- **Recall@5** ≥ 0.85 en ground-truth de 50 aditivos controversiales (E171, aspartame, BHA, etc.).
- **Precision@3** ≥ 0.80.
- **Latencia p95** de hybrid retrieval < 400ms por query.

Dataset de evaluación pendiente — documentado en `reviews/18-04.md`.
