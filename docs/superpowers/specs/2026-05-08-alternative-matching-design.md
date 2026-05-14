# BioShield Fase 2 — Ingredient-Based Alternative Matching

**Fecha:** 2026-05-08  
**Estado:** Aprobado — pendiente de implementación  
**Fase:** 2 (post-MVP)  
**Branch strategy:** `feat/fase2-alternative-matching` via git worktree — nunca directo en `main`

---

## 1. Contexto y objetivo

El MVP de BioShield (Fase 1) analiza etiquetas nutricionales y cruza ingredientes con biomarcadores del usuario para producir un semáforo de riesgo. El problema que no resuelve: cuando el semáforo es rojo/amarillo, el usuario sabe que el producto es problemático pero no sabe qué comprar en su lugar.

**Objetivo de Fase 2:** dado un producto con semáforo YELLOW, ORANGE o RED, encontrar y presentar alternativas reales del mercado mexicano con ingredientes más limpios, priorizando las que no generan conflictos con los biomarcadores activos del usuario.

**Pivot estratégico respecto a Fase 2 original del PRD:** se descarta el approach de conectores a APIs retail (Walmart/Cornershop/Mercado Libre) por cobertura pobre en productos health-conscious y dependencia de credenciales comerciales. Se reemplaza por un curated DB propio de productos health-conscious del mercado mexicano, ingesta vía **Open Food Facts Search API v2** (filtrado por país MX + categorías health). El único item que sobrevive del PRD original es el A/B testing de semáforo UI (independiente de este feature).

---

## 1.1 Dependencias Críticas (BLOQUEANTE)

**⚠️ IMPORTANTE:** Este feature NO puede testearse ni funcionar sin la siguiente dependencia completada primero:

| Dependencia | Descripción | Esfuerzo | Spec |
|---|---|---|---|
| **Curated DB Ingestion (Fase 2.1)** | Pipeline híbrido: OFF MX + OFF Global + USDA Branded Foods. Target: ≥ 7,000 productos únicos. Script canónico: `load_all_products.py` | ~3.5 días | `docs/superpowers/specs/2026-05-13-hybrid-ingestion-design.md` |
| **ChromaDB collection `products` indexada** | Embedding ingredient profiles + metadata persisted | ~1 día (post-ingesta) | Scripts: `index_products_chroma.py` |
| **Clean scores computed** | Cada producto debe tener `clean_score` calculado según BIOMARKER_RULES | ~1 día (post-ingesta) | Script: `compute_clean_scores.py` |
| **E2E fixture (5-10 productos)** | Seed de testing en DB + ChromaDB para Playwright specs | ~4h | Script: `seed_alternatives_fixture.py` |

**No implementar este feature hasta que ✅ curated DB esté cargado, indexado y testeado.**

---

## 2. Decisiones de diseño

| Pregunta | Decisión |
|---|---|
| Entry point | Botón "Ver alternativas más limpias" en `/scan/[id]`, visible solo cuando semáforo ∈ {YELLOW, ORANGE, RED} |
| Layout de resultados | Top pick personalizado (avatar blue, glow strong) + lista secundaria compacta (avatares soft) |
| Sin biomarcadores | Top pick degradado: muestra clean ingredients pero reemplaza biomarker insight row con CTA "Personaliza con tus labs →" → `/biosync` |
| Semáforo en lista secundaria | Pre-computado (ingredient-only score, sin biomarker context). Label "general" para ser honest con el usuario |
| "Ver análisis completo" | Corre el pipeline LangGraph completo del alternativo → redirige a `/scan/[alt-id]`. Se ejecuta on-tap, no on-load |
| Algorithm | Hybrid C: SQL first pass (categoría) → ChromaDB re-rank (ingredient profile) → biomarker filter rule-based |
| Branch | `feat/fase2-alternative-matching` via git worktree |

---

## 3. Arquitectura

```
/scan/[id]  (semáforo YELLOW | ORANGE | RED)
    ↓  botón "Ver alternativas más limpias"
/scan/[id]/alternatives
    ↓  GET /scan/{scan_id}/alternatives  (JWT required, 10 req/min)
    ├─ lee result_json del scan_id (ya persistido en scan_history.result_json)
    ├─ extrae flagged_ingredients[] del result_json
    ├─ SQL first pass → products WHERE category = ? AND clean_score < scanned.clean_score
    │   ORDER BY clean_score ASC LIMIT 20
    │   (fallback si category IS NULL: skip → fallback_used = true)
    ├─ ChromaDB re-rank → collection `products`, query = ingredient profile deseado
    │   retorna top 5 candidatos reordenados por similitud semántica
    ├─ biomarker filter → rule-based BIOMARKER_RULES sobre top pick
    │   (sin LangGraph, sin Gemini — solo reglas estáticas)
    └─ response: { top_pick, alternatives[], has_biomarkers, fallback_used }
    ↓  tap "Ver análisis completo" o tap en fila secundaria
    → pipeline LangGraph completo → /scan/[alt-id]
```

### Fuente de ingredientes del producto escaneado

`scan_history.result_json` (migration `a3f7c2d1e845` — ya existe). El endpoint lee el `ScanResponse` completo desde esta columna, sin re-correr el pipeline.

### Productos curados sin barcode OFF

Para productos del curated DB cuyo barcode no existe en OFF: el endpoint de "Ver análisis completo" feed el `result_json` pre-almacenado del producto curado directamente al pipeline LangGraph, saltando el lookup de OFF y Gemini Vision.

---

## 4. Data model

### Modificaciones a tabla `products`

```sql
ALTER TABLE products ADD COLUMN category VARCHAR(100);
ALTER TABLE products ADD COLUMN clean_score SMALLINT DEFAULT 0;
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_clean_score ON products(clean_score ASC);
```

**`clean_score`:** número de ingredientes problemáticos detectados (menor = más limpio). Se pre-computa en curation, nunca en runtime. Un producto con `clean_score = 0` tiene cero ingredientes flaggeados.

### Nueva tabla `analytics_events`

```sql
CREATE TABLE analytics_events (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id   UUID REFERENCES users(id) ON DELETE CASCADE,
  event_type VARCHAR(50) NOT NULL,
  -- valores: 'alt_button_shown' | 'alt_page_opened' | 'alt_tapped'
  payload   JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_analytics_user ON analytics_events(user_id);
CREATE INDEX idx_analytics_event ON analytics_events(event_type);
```

### Nueva ChromaDB collection: `products`

Colección separada de `ingredients`. Cada documento es el ingredient profile de un producto curado:

```
"nombre: Danone Activia Natural | marca: Danone | categoría: yogurts |
ingredientes: leche descremada, cultivos lácticos activos, pectina |
sin aditivos artificiales | sin colorantes | sin conservadores"
```

**Metadata por documento:** `{ barcode, category, clean_score, semaphore_precomputed }`  
**Dimensión:** 1024 (BGE-M3, consistente con collection `ingredients`)

---

## 5. Backend API

### `GET /scan/{scan_id}/alternatives`

```
Authorization: Bearer <jwt>  (requerido)
Rate limit: 10 req/min por usuario (hereda política de scan)
```

**Response 200:**
```json
{
  "scanned_product": {
    "barcode": "7501055300592",
    "name": "Yakult Original",
    "semaphore": "RED"
  },
  "top_pick": {
    "product": {
      "barcode": "7501055312345",
      "name": "Danone Activia Natural",
      "brand": "Danone",
      "clean_score": 0
    },
    "clean_ingredients": ["Sin azúcar añadida", "Sin colorantes artificiales", "Sin conservadores"],
    "biomarker_conflicts": [],
    "compatibility_pct": 92,
    "avatar_variant": "blue"
  },
  "alternatives": [
    {
      "product": { "barcode": "...", "name": "Lala Bio 100", "brand": "Lala", "clean_score": 1 },
      "avatar_variant": "yellow",
      "semaphore_precomputed": "YELLOW"
    }
  ],
  "has_biomarkers": true,
  "fallback_used": false
}
```

**`compatibility_pct`:**
```
base = (1 - clean_score_alternativa / max_clean_score_categoria) * 100
penalización = len(biomarker_conflicts) * 10
compatibility_pct = max(0, round(base - penalización))
```

**Lógica de fallback (foto sin categoría):**  
Si `category IS NULL` → ChromaDB query directo usando `flagged_ingredients` del producto escaneado como negative query. `fallback_used = true` en response → frontend muestra disclaimer "resultados aproximados".

### `POST /analytics/event`

```
Authorization: Bearer <jwt>
Body: { "event_type": "alt_button_shown" | "alt_page_opened" | "alt_tapped", "payload": {} }
Response: 202 Accepted (fire-and-forget)
```

---

## 6. Frontend

### Archivos nuevos

| Archivo | Descripción |
|---|---|
| `frontend/app/(app)/scan/[id]/alternatives/page.tsx` | Página principal de alternativas |
| `frontend/components/AlternativeTopPick.tsx` | Card del top pick: AvatarGlow blue (size=88, intensity="strong") + clean ingredients + biomarker insight row + CTA |
| `frontend/components/AlternativeRow.tsx` | Row de lista secundaria: AvatarGlow (size=40, intensity="soft", animDuration=4s) + nombre + semáforo general |

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `frontend/app/(app)/scan/[id]/page.tsx` | Botón condicional: `if semaphore ∈ {YELLOW, ORANGE, RED}` → `<Link href={/scan/${id}/alternatives}>` |
| `frontend/lib/api/scan.ts` | Agregar `getAlternatives(scanId: string): Promise<AlternativesResponse>` |
| `frontend/lib/api/types.ts` | Agregar `AlternativesResponse`, `AlternativeProduct`, `AlternativeTopPick` |
| `frontend/components/AILoadingState.tsx` | Agregar constante `ALTERNATIVES_PHASES` |

### `ALTERNATIVES_PHASES`

```ts
export const ALTERNATIVES_PHASES = [
  "Analizando categoría del producto...",
  "Buscando alternativas más limpias...",
  "Cruzando con tus biomarcadores...",
];
```

### Loading state

1. **`AILoadingState`** con `ALTERNATIVES_PHASES` mientras el API call está en vuelo
2. **Transición a skeletons** (`SkeletonCard` + `SkeletonRow × 2`) si data llega antes de completar el ciclo de fases — evita flash abrupto

### Estados especiales

**Sin biomarcadores (`has_biomarkers: false`):**  
El top pick muestra clean ingredients + AvatarGlow blue, pero reemplaza el biomarker insight row con:
```
🔒 Personaliza con tus biomarcadores → [Ir a BioSync]
```

**Empty state (sin alternativas):**  
`AvatarGlow` variant="gray" size=80 intensity="soft" + mensaje:  
"No encontramos alternativas en nuestra base de datos aún · Estamos expandiendo el catálogo"

**Fallback used (`fallback_used: true`):**  
Disclaimer sutil bajo el header: "Resultados aproximados — producto sin categoría registrada"

---

## 7. Curation pipeline (scripts offline)

Scripts que se corren una vez al cargar el curated DB, y cada vez que se agregan productos nuevos:

| Script | Descripción |
|---|---|
| `backend/scripts/compute_clean_scores.py` | Para cada producto en DB: cuenta ingredientes flaggeados según `BIOMARKER_RULES` + `regulatory_status`. Persiste `clean_score` en `products.clean_score` |
| `backend/scripts/index_products_chroma.py` | Genera el ingredient profile text por producto → embeddea con BGE-M3 → indexa en ChromaDB collection `products` con metadata |
| `backend/scripts/seed_alternatives_fixture.py` | Inserta 5-10 productos curados de prueba en DB + ChromaDB para fixtures de E2E |

---

## 8. Error handling

| Caso | Handling |
|---|---|
| Sin alternativas en DB | Empty state con AvatarGlow gray |
| Foto-scan sin categoría | Fallback ChromaDB, `fallback_used: true` → disclaimer en UI |
| Sin biomarcadores | Top pick degradado + CTA a BioSync |
| ChromaDB unavailable | Retorna solo SQL results sin re-rank; no falla el endpoint |
| Producto curado sin barcode OFF | Pipeline LangGraph usa `result_json` del curated DB como input directo |

---

## 9. Testing

### E2E Playwright — `tests/specs/alternatives/alternatives.spec.ts`

- Scan con semáforo RED → botón "Ver alternativas" visible
- Scan con semáforo BLUE → botón NO visible
- Con biomarcadores activos: top pick muestra biomarker insight row
- Sin biomarcadores: top pick muestra CTA a BioSync
- Tap "Ver análisis completo" → redirige a `/scan/[alt-id]`
- Empty state cuando fixture DB está vacío
- Requiere `seed_alternatives_fixture.py` ejecutado en `conftest.py`

### Unit tests — `backend/tests/test_alternatives.py`

- SQL first pass retorna productos de misma categoría con menor `clean_score`
- ChromaDB re-rank reordena candidatos correctamente
- Biomarker filter descarta productos con conflictos activos
- Fallback se activa cuando `category IS NULL`
- `compatibility_pct` formula produce valores entre 0-100

---

## 10. Métricas de producto

Medibles desde día 1 via `analytics_events`.

| Métrica | Fórmula | Target |
|---|---|---|
| **CTR de alternativas** | `alt_page_opened / alt_button_shown` | >15% usuarios con biomarkers |
| **Conversion rate** | `alt_tapped / alt_page_opened` | >20% |
| **Empty state rate por categoría** | `responses con 0 alternativas / total requests, agrupado por category` | Dirige roadmap de curation |

---

## 11. Documentos a actualizar

| Archivo | Cambio |
|---|---|
| `PRD.md` § Fase 2 | Reemplazar "Retail Integration" con este feature. Nota: pivot estratégico — retail APIs descartadas |
| `docs/architecture.md` | Agregar sección "Fase 2 — Extensiones de Schema" con campos nuevos de `products` y tabla `analytics_events` |
| `docs/embedding-strategy.md` | Agregar sección "Fase 2 — Collection `products`" con template de embedding y pipeline de ingesta |

---

## 12. Archivos de implementación

### Modificar (existentes)
- `backend/app/models/base.py`
- `backend/app/routers/scan.py`
- `backend/app/main.py`
- `backend/app/schemas/models.py`
- `frontend/app/(app)/scan/[id]/page.tsx`
- `frontend/lib/api/scan.ts`
- `frontend/lib/api/types.ts`
- `frontend/components/AILoadingState.tsx`

### Crear (nuevos)
- `backend/alembic/versions/XXXX_add_category_clean_score_analytics.py`
- `backend/app/services/alternatives.py`
- `backend/app/routers/analytics.py`
- `backend/scripts/compute_clean_scores.py`
- `backend/scripts/index_products_chroma.py`
- `backend/scripts/seed_alternatives_fixture.py`
- `backend/tests/test_alternatives.py`
- `frontend/app/(app)/scan/[id]/alternatives/page.tsx`
- `frontend/components/AlternativeTopPick.tsx`
- `frontend/components/AlternativeRow.tsx`
- `tests/specs/alternatives/alternatives.spec.ts`
