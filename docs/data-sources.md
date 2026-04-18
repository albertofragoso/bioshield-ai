# 🧬 Data Sources Specification v3.0: High-Fidelity Hybrid RAG

**Estatus:** Especificación de Arquitectura de Producción  
**Versión:** 3.1 (2026-04-15 — URL fixes, token inconsistency resolved, HITL calibration plan, ChromaDB fallback)  
**Arquitectura:** RAG Híbrido + Re-ranking + Entity Resolution Progresiva.

---

## 1. Overview
El sistema BioShield AI opera como un motor de **Confianza Crítica**. La arquitectura v3.0 introduce capas de validación de linaje y una estrategia de recuperación multi-vector para garantizar que las discrepancias entre agencias (FDA vs EFSA) sean tratadas como puntos de datos deterministas y no solo como coincidencias estadísticas.

---

## 2. Data Sources Inventory (Expanded)

### 2.1 FDA (Food and Drug Administration) - USA

* **Fuentes:** * **EAFUS** (Substances Added to Food Inventory)
    * **GRAS Notice Inventory** (Substances Generally Recognized as Safe)
* **URL:** [FDA EAFUS](https://www.fda.gov/food/food-additives-petitions/food-additive-status-list) | [GRAS Notices](https://www.fda.gov/food/generally-recognized-safe-gras/gras-notice-inventory)
* **⚠️ Nota de URL:** La URL original usaba el portal legacy `cfsanappsexternal.fda.gov`. La URL actualizada apunta al portal FDA actual. Verificar disponibilidad de descarga en cada ciclo de ingesta.
* **Formato:** Excel (.xlsx) / CSV.
* **Licencia:** Dominio Público (Gobierno de EE.UU.).
* **Registros:** ~4,000 (EAFUS) + ~1,200 (GRAS).
* **Plan de Ingesta:** Descarga manual/programada de archivos Excel procesados mediante scripts de Python (Pandas). Se registra un `source_hash` (SHA-256) y un `source_version` (ej. `FDA_EAFUS_2026_Q2`) por cada descarga para asegurar el linaje de datos.

### 2.2 EFSA (European Food Safety Authority) - UE

* **Fuentes:** * **EU Food Additives Database**
    * **OpenFoodTox** (Chemical Hazards Database)
* **URL:** [EU Food Additives](https://www.efsa.europa.eu/en/topics/topic/food-additives) | [Zenodo OpenFoodTox](https://zenodo.org/records/8120114)
* **Formato:** XML / XLSX / CSV.
* **Licencia:** CC BY 4.0 (Creative Commons Attribution).
* **Registros:** ~350 (Aditivos autorizados) + ~5,700 (Sustancias en OpenFoodTox).
* **Plan de Ingesta:** Ingesta automatizada vía Zenodo API para OpenFoodTox (`GET https://zenodo.org/api/records/8120114`). Esta fuente actúa como el "Golden Dataset" para los Scientific Embeddings, por lo que requiere una validación de esquema estricta y control de integridad de datos antes de la indexación.

### 2.3 Codex Alimentarius (FAO/WHO) - Global

* **Fuente:** GSFA Online (General Standard for Food Additives).
* **URL:** [Codex GSFA Online](https://www.fao.org/fao-who-codexalimentarius/codex-texts/dbs/gsfa/en/)
* **Formato:** HTML (Base de datos web relacional).
* **Licencia:** IGO (Uso para fines no comerciales e informativos).
* **Registros:** ~1,200 aditivos con límites por categoría.
* **Plan de Ingesta:** Script de scraping estructurado con detección de cambios en tablas comparativas. El pipeline mapea la relación [Aditivo x Categoría x Límite Máximo] preservando la jerarquía de categorías alimentarias del Codex.

---

## 3. Chunking & Indexing Strategy (MANDATORY)

Para garantizar la precisión del RAG, se aplica una partición semántica estricta:

* **Strategy:** Recursive Character Text Splitting con preservación de fronteras lógicas.
* **Chunk Size:** 512 tokens (texto fuente de la fuente regulatoria/científica original).
* **Overlap:** 10% (50 tokens) para mantener la coherencia técnica.
* **Semantic Boundaries:** Los chunks NO deben fragmentar tablas de límites (Codex) u objetos de riesgo específicos de OpenFoodTox.

> **Aclaración sobre tokens (resolución de inconsistencia):** Los 512 tokens del chunk corresponden al texto fuente que se ingiere. A partir de ese chunk, el pipeline genera un **Embedding Template** estructurado de máximo 256 tokens (ver Sección 5) que es lo que se vectoriza. Son dos representaciones distintas del mismo dato: el chunk es el texto de recuperación (`page_content`), el template es el texto de indexación vectorial (`embedding_input`). Ambos se almacenan en ChromaDB — el chunk como `document`, el template como input del vector.

---

## 4. Canonical Data Model v3.0

```json
{
  "entity_id": "CAS:13463-67-7",
  "lineage": {
    "data_version": "2026.04.10",
    "ingestion_id": "ingest_hash_98234db",
    "source_checksum": "sha256:7f83b...",
    "timestamp": "2026-04-10T13:00:00Z"
  },
  "ingredient_metadata": {
    "canonical_name": "Titanium Dioxide",
    "cas_number": "13463-67-7",
    "e_number": "E171",
    "synonyms": ["Titania", "Pigment White 6"]
  },
  "conflict_detection": {
    "conflict_flag": true,
    "severity": "HIGH",
    "type": "REGULATORY_DISCREPANCY",
    "summary": "Banned in EU (EFSA) due to genotoxicity; Approved in US (FDA)."
  },
  "embeddings": {
    "regulatory_summary": {
      "text": "[ID: E171] [Status: Approved-US/Banned-EU] [Limits: 1% US].",
      "vector": [...]
    },
    "scientific_summary": {
      "text": "[CAS: 13463-67-7] [Risk: Genotoxicity Positive] [NOAEL: 1000 mg/kg].",
      "vector": [...]
    }
  }
}
```

## 5. Embedding Standardization (STRICT Template)

Para prevenir el **Semantic Drift** (deriva semántica) y asegurar la relevancia en la recuperación, se implementa un template rígido para la generación de vectores:

* **Template:** `[ID: {ins_number/cas_number}] [Name: {canonical_name}] [Status: {status}] [Key_Risk: {hazard_note}] [Context: {usage_context}]`
* **Max Token Length:** 256 tokens para el resumen base.
* **Tone:** Técnico-Objetivo (eliminación de adjetivos, solo hechos regulatorios y científicos).
* **Required Fields Order:** ID -> Name -> Status -> Risk -> Context. Este orden es obligatorio para mantener la consistencia en el espacio latente del vector store.

## 6. Retrieval Layer: The Formal Contract

La recuperación utiliza una arquitectura de tres etapas para maximizar la fidelidad y el determinismo:

1.  **Stage 1 (Hybrid Search):** Combinación de búsqueda vectorial (similitud) con búsqueda por palabras clave (BM25).
    * `Score = (0.7 * Vector_Similarity) + (0.3 * BM25_Score)`
2.  **Stage 2 (Hard Filtering):** Aplicación de filtros booleanos deterministas sobre los metadatos (ej. `where region == 'EU'`, `where regulatory_status == 'Banned'`, o `where conflict_flag == true`).
3.  **Stage 3 (Cross-Encoder Re-ranker):** Los top 10 resultados pasan por un modelo reranker para asegurar que la intención de consulta del usuario (ej. salud vs. legalidad) priorice el resumen (`scientific` vs `regulatory`) correspondiente.

## 7. Entity Resolution Robustness (ERL 2.0)

El sistema maneja la incertidumbre de datos mediante una capa de resolución de identidades robusta:

1.  **Confidence Scoring:** Cada match de ingrediente recibe un score de confianza:
    * **Exact Match (CAS/E-Number):** 1.0
    * **Fuzzy Name Match:** 0.6 - 0.8
    * **Sin match:** < 0.6 → rechazado automáticamente como "Ingrediente No Identificado".
2.  **Composite Ingredients:** Para ingredientes compuestos (ej. "Mezcla de gomas"), el pipeline descompone el string en sub-tokens y genera consultas individuales para cada componente.
3.  **Human-in-the-Loop (HITL):** Cualquier resolución con confianza < 0.7 se envía a una cola de revisión manual, se marca como "Pendiente de Verificación" en la UI y se almacena con un checksum para asegurar la reproducibilidad.
    * **⚠️ Calibración del umbral:** El valor de 0.7 es el punto de partida inicial. Debe calibrarse en la Fase 3 con un set de validación de al menos 200 ingredientes anotados manualmente (ground truth). La métrica objetivo es minimizar falsos negativos (matches perdidos) sin saturar la cola HITL. El umbral final debe documentarse en `docs/embedding-strategy.md` junto con la curva precisión/recall del dataset de calibración.

## 8. Conflict Detection 2.0 (Logic-Based)

Se implementa una matriz de severidad para categorizar las discrepancias detectadas:

| Tipo de Conflicto | Condición | Severidad |
| :--- | :--- | :--- |
| **REGULATORY** | El estatus legal difiere entre agencias (ej. FDA vs EFSA). | **HIGH** |
| **SCIENTIFIC** | OpenFoodTox muestra riesgos no reflejados aún en la regulación formal. | **MEDIUM** |
| **TEMPORAL** | Los datos de la fuente tienen una antigüedad superior a 24 meses. | **LOW** |

## 9. Vector DB Justification: ChromaDB

* **Engine:** **ChromaDB** (Local-first).
* **Justificación:**
    * **Latencia:** < 50ms para búsqueda vectorial y filtrado en el volumen esperado (~20k chunks).
    * **Escala:** Compatible con la infraestructura actual (8GB RAM), permitiendo ejecución local y bajo costo operativo.
* **Tradeoff:** Se establece una ruta de migración hacia **Qdrant** si el sistema escala a >100k registros o requiere capacidades de búsqueda geográfica compleja.

### 9.1 Estrategia de Fallback (Obligatoria)

El servicio `backend/app/services/retrieval.py` debe implementar un circuit breaker ante fallo de ChromaDB:

| Nivel | Condición | Acción |
| :--- | :--- | :--- |
| **L1 — Retry** | ChromaDB timeout < 500ms | 2 reintentos con backoff exponencial (100ms, 200ms). |
| **L2 — Keyword Fallback** | ChromaDB inalcanzable después de reintentos | Búsqueda BM25 pura sobre metadatos en PostgreSQL (campos `canonical_name`, `cas_number`, `e_number`). Score devuelto marcado con `retrieval_mode: "keyword_only"`. |
| **L3 — Degraded Response** | PostgreSQL también falla | Devolver respuesta con `risk_level: "UNKNOWN"`, `conflict_flag: null`, y mensaje al usuario: *"Análisis regulatorio temporalmente no disponible. Consulta fuentes oficiales."* |

> El endpoint nunca debe retornar `500` al usuario final por fallo del vector store. El nivel de degradación se registra en el campo `retrieval_metadata` de la respuesta y en los logs de telemetría.

## 10. Future Iterations

* **EWG Integration:** Capa de percepción de riesgo público y "Food Scores" basada en datos propietarios (Fase 2).
* **FSCJ (Japan):** Incorporación de evaluaciones técnicas de la Food Safety Commission de Japón para ampliar el espectro científico.
* **Live Monitoring:** Alertas de cambios regulatorios en tiempo real mediante monitoreo automatizado de boletines oficiales y webhooks gubernamentales.