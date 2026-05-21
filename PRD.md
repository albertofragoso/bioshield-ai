# PRD v6.0: BioShield AI – Sistema de Transparencia Metabólica & Reality Engineering

**Estatus:** MVP Completado y Demostrable — Fase 1 + Production Hardening ✅  
**Última actualización:** 2026-05-20 (PR #21 hardening + PR #22 scan pipeline fix)  
**Autor:** Alberto Fragoso  
**Stack Core:** Next.js 15 (Frontend), FastAPI (Backend), LangGraph, ChromaDB, Gemini 2.5 Flash, BGE-M3, Open Food Facts API.  
**Licencia:** MIT License (Software) / ODbL (Datos).

---

## 1. Arquitectura Técnica y Despliegue

### 1.1 · Frontend
- **Next.js 15 (App Router)** desplegado en Vercel. TypeScript strict, dark-only design (no light mode).
- **Gestión de estado:**
  - **Client:** Zustand para auth (`user`, `isAuthenticated`).
  - **Server:** TanStack Query v5 para cache de scans por barcode (30 min staleTime, `refetchOnWindowFocus: false` — scan results son inmutables), mutations (upload/delete).
- **UI:** Tailwind CSS v4 + shadcn/ui primitivos (Radix). Design tokens en `globals.css` (semáforo 5 colores dark-adjusted WCAG AA, hex-grid SVG, scanlines, animaciones: wobble, pulse-glow, scan-line, shimmer).
- **Iconografía:** Lucide React (HelpCircle/CheckCircle/AlertCircle/AlertTriangle/ShieldAlert para semáforo).
- **Avatares:** 12 PNG (992×1063px, fondo alpha transparente): main, welcome, progress, success, profile, support + semáforo gray/blue/yellow/orange/red.
- **Scanner:** @zxing/browser (barcode), dropzone con validación <10MB (foto).
- **Auth:** JWT vía HTTP-only cookies, `credentials: "include"`, refresh automático en 401.

### 1.2 · Backend
- **FastAPI 0.115.6** hosteado en Render/Railway. Python 3.11+, Pydantic v2, SQLAlchemy 2.0, Alembic.
- **Orquestación:** LangGraph 0.3.5 — grafo de 7 nodos (identify → extract → resolve → search → biosync → detect → risk).
- **Base de datos:** SQLite dev / PostgreSQL prod. ORM + migraciones versionadas.
- **Embeddings:** 
  - **Primary:** BGE-M3 local (1024-dim, `USE_LOCAL_EMBEDDINGS=true` default) — offline, sin cuota API.
  - **Fallback:** Gemini `gemini-embedding-001` (768-dim) — cuando BGE-M3 falla.
- **Vector store:** ChromaDB 0.6.3 con retrieval híbrido (0.7 vector + 0.3 BM25L).
- **VLM:** Gemini 2.5 Flash (Visión, Structured Outputs, reconciliador).
- **Rate limiting:** slowapi, por usuario o IP (10–20 req/min según endpoint).
- **Seguridad:** AES-256-GCM biomarkers en reposo, JWT refresh token rotation, IP logging.

### 1.3 · Integraciones externas
- **Open Food Facts API:** producto lookup, contribución asíncrona (Fase 2).
- **Google Gemini API:** OCR etiquetas, parsing PDFs laboratorio, embeddings fallback, copy generación.
- **Zenodo:** EFSA OpenFoodTox dataset (4595 sustancias).
- **FDA EAFUS:** fixtures offline (endpoint caído).
- **Codex GSFA:** fixtures offline (servicio caído).

---

## 2. Flujo Principal de Operación (Main Workflow)

### 2.1 · Escaneo de productos (barcode)
1. Usuario abre `/scan` tab "Código de barras".
2. Cámara abre, lector @zxing detecta barcode (0–5s).
3. `POST /scan/barcode {barcode: "8-14 dígitos"}` → Off API lookup.
4. **Éxito:** `/scan/[barcode]` con semáforo + ingredientes (cache TanStack Query por 30 min).
5. **Error 404:** modal "No encontramos este producto. ¿Intentar con foto?" → tab foto automático.

### 2.2 · Escaneo de productos (foto etiqueta)
1. Usuario abre `/scan` tab "Foto de etiqueta".
2. Dropzone o captura `capture="environment"` (mobile).
3. Validación <10MB, conversión base64.
4. `POST /scan/photo {image_base64}` → Gemini Vision (Structured Outputs) → extrae ingredientes.
5. **Loading:** `AILoadingState` con 4 anillos orbitales, terminal de log, `SCAN_PHASES`.
6. **Resultado:** `/scan/photo-{uuid16}` (pseudo-barcode para persistencia).
7. **[Fase 2]** Si `source === "photo"` y usuario activa toggle: `POST /scan/contribute {barcode, ingredients, image_base64, consent: true}` → 202 Accepted asíncrono.

### 2.3 · Procesamiento Bio-Sync (biomarcadores)
1. Usuario en `/biosync` sube PDF de laboratorio (<10MB).
2. `POST /biosync/extract {pdf}` → Gemini Vision procesa PDF multipage → `BiomarkerExtractionResult` (no persiste).
3. Estado "review": tabla editable con biomarcadores extraídos, clasificación (low/normal/high), rango referencia.
4. `POST /biosync/upload {biomarkers, lab_name, test_date}` → encripta AES-256, persiste con TTL 180d.
5. Cron automático expira a través de `expire_biomarkers()`.

### 2.4 · Análisis semántico (resultado semáforo)
1. Pipeline LangGraph ejecuta 7 nodos:
   - **identify_product:** OFF lookup, extrae nombre+brand+imagen.
   - **extract_ingredients:** OCR Gemini si no hay ingredientes.
   - **resolve_entities:** CAS → E-number → fuzzy match (token_sort_ratio ≥ 0.7).
   - **search_regulatory:** hybrid search ChromaDB (vector 0.7 + BM25L 0.3) por ingrediente.
   - **biosync:** desencripta biomarcadores del usuario.
   - **detect_conflicts:** `BIOMARKER_RULES` (11 reglas: LDL/HDL/glucose/hba1c/triglycerides/sodium/potassium/uric_acid/creatinine/alt/ast).
   - **personalize:** genera `PersonalizedInsight` en paralelo con `asyncio.gather` (avatar dinámico, friendly copy vía Gemini).
   - **calculate_risk:** `compute_semaphore()` con prioridad: RED > ORANGE > YELLOW > GRAY > BLUE.
2. **Prioridad semáforo:** RED si banned, ORANGE si biomarker alert, YELLOW si restricted/under-review/conflicto, GRAY si <50% resueltos, BLUE si clean.

### 2.5 · Dashboard y historial
1. `/` muestra:
   - Hero CTA "Escanear producto".
   - BiosyncCard: status biomarkers activos, badge ámbar si <30d expiry.
   - RecentScans: últimos 5 con semáforo thumbnail + nombre + fecha relativa.
2. `/history` lista todos los scans agrupados por día (Hoy/Ayer/Hace N días/Mes Año).
   - FilterTabs por semáforo (counts dinámicos).
   - Search por product_name.
   - Click → `/scan/[id]`.

---

## 3. Extracción Estructurada (Structured Outputs)

Todos los outputs críticos usan **Pydantic v2 + Gemini Structured Outputs** para garantizar integridad JSON.

### 3.1 · Extractor de ingredientes (Visión)
```python
class ProductExtraction(BaseModel):
    product_name: str | None
    ingredients: list[str]
    has_additives: bool
    language: str
```
**Prompt:** Analyze image of food label. Extract ingredients, avoid marketing claims, correct OCR errors using food chemistry context.

### 3.2 · Extractor de biomarcadores (PDF)
```python
class ExtractedBiomarker(BaseModel):
    name: CanonicalBiomarker
    raw_name: str
    value: float
    unit: str
    unit_normalized: bool
    reference_range_low: float | None
    reference_range_high: float | None

class GeminiBiomarkerExtraction(BaseModel):
    biomarkers: list[ExtractedBiomarker]
    lab_name: str | None
    test_date: date | None
    language: str
```
**Prompt:** Extract biomarker values from lab PDF. Normalize units to mg/dL. Extract reference ranges if available.

### 3.3 · Reconciliador de conflictos (RAG Node)
```python
class IngredientConflict(BaseModel):
    conflict_type: Literal["REGULATORY", "SCIENTIFIC", "TEMPORAL"]
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    summary: str
    sources: list[str]
```
**Prompt:** Synthesize ingredient risk using scientific context. Detect agency conflicts. Draft as literature findings, not medical advice.

### 3.4 · Insight personalizado
```python
class PersonalizedInsightCopy(BaseModel):
    friendly_title: str
    friendly_biomarker_label: str
    friendly_explanation: str
    friendly_recommendation: str
```
**Prompt:** Generate friendly (non-technical) insight. Avoid medical jargon. Include impact direction (raises/lowers) and severity.

---

## 4. Gestión de Caché y Latencia

| Estrategia | Nivel | Implementación | TTL |
|---|---|---|---|
| **Backend API** | `/scan` responses | SQLite/Postgres persistence | Indefinido (JOIN con scan_history) |
| **Frontend Query** | Barcode results | TanStack Query `["scan", barcode]` | 30 min (staleTime) |
| **Frontend LRU** | Text embeddings | `@lru_cache(maxsize=256)` en backend | Process lifetime |
| **Chromadb Index** | Vector search | Persistent client con volumen Docker | Indefinido (índice completo) |

**Mejora Futura (Fase 2):** Caché geográfica pre-cargar top-50 productos por código postal del usuario.

---

## 5. Plan de Gestión de Riesgos

| Riesgo | Impacto | Estrategia de Mitigación | Estado |
| :--- | :--- | :--- | :--- |
| **Privacidad de Datos** | Crítico | AES-256-GCM en reposo. Variables locales solo en memoria volátil. | ✅ Implementado |
| **Falla de Scanner (barcode)** | Medio | Fallback inmediato a foto con 1 click. Input manual barcode. | ✅ Implementado |
| **Vendor Lock-in (Gemini)** | Alto | BGE-M3 primary, Gemini fallback. Arquitectura modular para swap. | ✅ Mitigado (BGE-M3 primary) |
| **Free tier Gemini quota** | Alto | Lock + backoff en embeddings. Mock en tests. Staging con tier pagado. | ⏳ Dev mitigation; prod upgrade path |
| **HITL threshold (0.7)** | Medio | Sin calibración post-dogfood. Ground truth 200+ pares. | ⏳ Post-MVP |
| **E2E testing** | Medio | Playwright — 32/32 core passing (PR #7); alternatives E2E pendiente. | ⏳ Alternatives pendiente |
| **KMS para AES_KEY** | Crítico | Env var en dev/staging; AWS/GCP Secrets en prod. Path documentado. | ⏳ Pre-prod |
| **Cookies cross-origin (prod)** | Medio | SameSite=Lax local. Requiere `SameSite=None; Secure` si FE/BE en dominios distintos. | ⏳ Pre-prod staging |

---

## 6. Roadmap de Desarrollo

### Fase 1 — MVP (MVP Cerrado ✅)
**Estado:** Backend 90 tests passing, Frontend 8 pantallas + design tokens.  
**Entregables:**
- ✅ Backend: 11 endpoints (auth, scan barcode/photo, biosync upload/status/delete, health, ping).
- ✅ LangGraph: 7 nodos, semáforo 5 colores, BIOMARKER_RULES (11 reglas).
- ✅ Frontend: Dark-only Next.js 15, TanStack Query, Zustand, 8 pantallas (login, register, dashboard, scan, result, biosync, history, globals).
- ✅ Design tokens: semáforo dark-adjusted WCAG AA, hex-grid + scanlines, 12 avatares PNG, animaciones.
- ✅ E2E testing: Playwright — 32/32 critical tests passing (PR #7).
- ✅ Legal: Privacy Policy + T&C publicados (PR #10).

### Fase 1.5 — Production Hardening (Cerrado ✅, PR #21 + #22)
**Estado:** Mergeado 2026-05-20.  
**Entregables:**
- ✅ Structured JSON logging + `request_id` ContextVar propagado por async boundaries.
- ✅ Unified error schema (`ErrorResponse`) + global exception handler.
- ✅ Per-user daily token budget — atomic SQL UPDATE, no read-modify-write.
- ✅ Rate limiting dinámico — `Retry-After` calculado hasta medianoche UTC.
- ✅ Scan pipeline fix: `personalized_insights` persistidos en DB, `queryFn` usa GET no POST, `staleTime: 30min`, `refetchOnWindowFocus: false`.
- ✅ Prefetch en hover de historial (navegación instantánea).
- ✅ Optimistic UI en OFFContributeToggle con rollback en error.
- ✅ Alembic migration para rows históricas sin `personalized_insights`.

### Fase 2 — Alternative Matching (Health-Conscious)

**Objetivo:** dado un producto con semáforo YELLOW/ORANGE/RED, encontrar alternativas reales del mercado mexicano con ingredientes más limpios, priorizadas por compatibilidad con los biomarcadores activos del usuario.

**Pivot estratégico:** se descartaron los conectores a APIs retail (Walmart/Cornershop/Mercado Libre) por cobertura pobre en productos health-conscious y dependencia de credenciales comerciales. Se reemplaza por un curated DB propio de productos, ingesta vía **Open Food Facts Search API v2** (filtrado por `countries_tags=en:mexico` + categorías health). Mercado Libre descartado también como fuente — es marketplace sin datos de ingredientes.

**Features:**
- ✅ Hybrid matching engine: SQL first pass por categoría → ChromaDB re-rank → biomarker filter rule-based
- ✅ Pantalla `/scan/[id]/alternatives`: top pick personalizado (AvatarGlow blue) + lista secundaria
- ✅ `GET /scan/alternatives/{barcode}` endpoint · `POST /analytics/event` fire-and-forget
- ✅ Nueva ChromaDB collection `products` (ingredient profiles, 1024-dim BGE-M3)
- ✅ Enrichment Pipeline (Fase 2.1): scan → product DB auto-feeding
- ✅ **Curated DB ingestion** — OFF Mexico (PR #14) + OFF Global + USDA Branded Foods hybrid pipeline (PR #17)
- ⏳ A/B testing de semáforo UI en producción (independiente — sigue en roadmap post-Fase 2)

**Sub-fases:**
1. **Fase 2.0 — Ingesta + Curation** (Cerrado ✅, PRs #14 + #17)
   - Scripts implementados: `ingest_off_mexico.py`, `ingest_off_global.py`, `ingest_usda.py`
   - Curation pipeline implementado: `compute_clean_scores.py`, `index_products_chroma.py`, `seed_alternatives_fixture.py`, `load_all_products.py`
   - Spec: `docs/superpowers/specs/2026-05-12-product-ingestion-off-design.md`

2. **Fase 2.1 — Feature Implementation** (Cerrado ✅)
   - Backend APIs + Frontend UI + Enrichment Pipeline
   - Spec: `docs/superpowers/specs/2026-05-08-alternative-matching-design.md`

3. **Fase 2.2 — Testing & Validation**
   - E2E testing (36+ casos Playwright)
   - Legal validation (Privacy/T&C)
   - Dogfood real con usuarios

**Dependencias críticas:**
- ✅ Fase 1 shipped
- ✅ Curated DB scripts implementados (PRs #14 + #17)
- ⏳ E2E tests de alternatives passing
- ✅ Documentos legales publicados (PR #10)

#### Enrichment Pipeline (Fase 2.1)

Extensión del alternative matching: cada scan exitoso alimenta automáticamente
el curated DB sin intervención manual. Ver spec: `docs/superpowers/specs/2026-05-09-scan-enrichment-design.md`.

### Fase 3 — Reality Engineering
**Objetivo:** RAG multidimensional con sabiduría ancestral + agente conciliador holístico.
**Features:**
- Ingesta curada: nutrición tradicional (MX, LatAm), estudios etnobotánicos.
- Agente multi-fuente: pesa evidencia científica vs. tradicional.
- Insights "holísticos" (energía, digestibilidad, culturalidad).

**Dependencias:** Fuentes de datos curadas, etnógrafo/nutriólogo en equipo.

---

## 7. El Semáforo Visual (Output — Implementado ✅)

### 7.1 · Estados y significados
| Color | Icono Lucide | Label | Causa | Avatar PNG |
|---|---|---|---|---|
| **GRAY** | HelpCircle | Sin datos suficientes | <50% ingredientes resueltos / error OCR | gray.png |
| **BLUE** | CheckCircle | Seguro | Todos approved, sin conflictos | blue.png |
| **YELLOW** | AlertCircle | Precaución | Status RESTRICTED/UNDER_REVIEW o conflicto existente | yellow.png |
| **ORANGE** | AlertTriangle | Riesgo personal | Biomarker match (alto LDL + grasas trans, etc.) | orange.png |
| **RED** | ShieldAlert | Prohibido | Ingrediente BANNED por cualquier agencia | red.png |

### 7.2 · Diseño visual
- **Circle:** 120px en hero, color semáforo con glow del mismo color (css `drop-shadow`).
- **Animation:** `pulse-glow` keyframe (opacity + shadow breathing 2.4s).
- **Avatar:** PNG 120×120 lateral, `animate-pulse-glow`, `aria-hidden` (información ya en icono + label).
- **Label:** H1 Space Grotesk bold + descripción 1–2 líneas.
- **WCAG AA:** todos los colores validados contra fondo oscuro #080C07 (ratios 6.8:1–13.4:1).

### 7.3 · Sección "Para ti" (personalized insights)
- Renderiza solo si usuario tiene biomarcadores activos Y hay matches en BIOMARKER_RULES.
- Layout: carousel scroll-snap (`overflow-x-auto snap-x`), cards 460px ancho, tabs Alertas/Vigilar.
- **InsightCard:** avatar dinámico + friendly_title + friendly_biomarker_label + valor numérico + BiomarkerRangeBar (track animado con zonas) + impact arrows + friendly_explanation/recommendation + chips ingredientes.
- **Estados:**
  - Sin biomarcadores: `BiomarkerEmptyState` con link a `/biosync`.
  - Con biomarcadores pero sin matches: `BiomarkerClearState` "Buenas noticias, no detectamos conflictos".
  - Con matches: carousel de `InsightCard`.

---

## 8. Pantallas Frontend (Implementadas ✅)

### 8.1 · Públicas
| Pantalla | Ruta | Stack | Notas |
|---|---|---|---|
| **Login** | `/login` | AuthForm + AuthField + AuthAlert | JWT + cookies, auto-focus email |
| **Register** | `/register` | PasswordStrengthBar (inline) + checkbox privacidad | Auto-login post-registro |

### 8.2 · Protegidas (JWT guard)
| Pantalla | Ruta | Stack | Notas |
|---|---|---|---|
| **Dashboard** | `/` | Hero CTA + BiosyncCard + RecentScans | Empty state welcome.png + CTA escanear |
| **Scanner** | `/scan` | Tabs barcode/foto, BarcodeScanner, PhotoCapture, OFFContributeToggle | Fallback 404 → tab foto, loading AILoadingState |
| **Resultado** | `/scan/[id]` | SemaphoreHero + IngredientAccordion + ParaTiCarousel + PersonalizedInsights | Avatar PNG dinámico, nested accordions |
| **Biosync** | `/biosync` | 3 estados (upload/loading/review), PDFDropzone, BiomarkerTable, AvatarGlow | Review editable, delete fila, agregar custom |
| **Historial** | `/history` | FilterTabs, search, agrupación por día, SemaphoreBadge | Empty state welcome.png, chevron → `/scan/[id]` |
| **Global** | SessionExpiredDialog, ErrorPage, Skeletons | gray.png en dialog, support.png en error | Shimmer verde en skeletons |

### 8.3 · Componentes reutilizables (extracted)
- `AvatarGlow` — variant (gray/blue/yellow/orange/red), size, intensity; used in biosync + insights.
- `SemaphoreBadge` — thumbnail 40px, dashboard + history.
- `SessionExpiredDialog` — modal centered, gray.png, "entrar de nuevo" → hard redirect `/login`.
- `ErrorPage` — support.png, retry + ir al inicio.
- `Skeletons` — SkeletonCard / Row / Hero con shimmer verde.
- `AILoadingState` — 4 anillos orbitales, terminal typewriter, `SCAN_PHASES` / `BIOSYNC_PHASES`.

---

## 9. Cumplimiento Legal y Documentos Públicos

BioShield procesa **datos sensibles de salud** (biomarcadores) y **contenido de usuario** (fotos de etiquetas). Publicación de Política de Privacidad + Términos de Uso es **bloqueante para abrir registro público**.

### 9.1 · Estado actual
- **Privacidad:** outline + draft inicial en `docs/legal/` (pendiente revisión legal formal).
- **Términos:** outline + draft inicial (pendiente revisión legal formal).
- **ARCO endpoints:** `GET /account/export`, `DELETE /account` (pendiente backend).
- **UI checkboxes:** separado para datos médicos vs. identidad (implementado en register).

### 9.2 · Documentos públicos (por publicar)
```
/privacy    → Política de Privacidad (versionada, pie de página)
/terms      → Términos de Uso (versionada, pie de página)
/contact    → Formulario ARCO / contacto privacy@<dominio>
```

### 9.3 · Hitos legales
1. ✅ Redacción de drafts iniciales.
2. ⏳ Revisión por abogado especialista (México, LFPDPPP).
3. ⏳ Implementar ARCO endpoints en backend.
4. ⏳ Publicar `/privacy` y `/terms` con versionado.
5. ⏳ Registrar aviso ante INAI (si escala lo requiere, Fase 2).

### 9.4 · Flujo OFF (Fase 2, ya especificado)
- Toggle "Contribuir a Open Food Facts (ODbL)" en foto tab (default: off).
- `POST /scan/contribute` → 202 Accepted, audit trail local (PENDING/SUBMITTED/FAILED).
- Consentimiento granular por escaneo (no global).
- Referencia: `docs/off-contribution.md` (operacional) + sección legal en Privacidad.

---

## 10. Stack Detallado (Fase 1 Completo)

### 10.1 · Backend
| Componente | Versión | Notas |
|---|---|---|
| FastAPI | 0.115.6 | Web framework |
| Uvicorn | 0.34.0 | ASGI server |
| SQLAlchemy | 2.0.37 | ORM |
| Alembic | 1.14.1 | Migraciones DB |
| Pydantic | v2 (2.10.4) | Validación |
| LangGraph | 0.3.5 | Orquestación agentes |
| Gemini SDK | `google-generativeai` | VLM + embeddings fallback |
| BGE-M3 | BAAI/bge-m3 | Embeddings primary (1024-dim) |
| ChromaDB | 0.6.3 | Vector store |
| rank-bm25 | 0.2.2 | BM25L scoring |
| rapidfuzz | 3.12.1 | Fuzzy matching |
| python-jose + bcrypt | 3.3.0 / 4.2.1 | JWT + password hashing |
| cryptography | 44.0.0 | AES-GCM |
| slowapi | 0.1.9 | Rate limiting |
| httpx | 0.28.1 | HTTP client |
| SQLite / PostgreSQL | — | Dev / Prod DB |

### 10.2 · Frontend
| Componente | Versión | Notas |
|---|---|---|
| Next.js | 15 | Framework |
| React | 19 | UI library |
| TypeScript | strict | Type safety |
| Tailwind CSS | v4 | Styling |
| shadcn/ui | latest | Radix primitives |
| TanStack Query | v5 | Server state + caching |
| Zustand | latest | Client state (auth) |
| Zod | latest | Schema validation |
| @zxing/browser | latest | Barcode scanning |
| Lucide React | latest | Icons |
| next/font | — | Pacifico / Space Grotesk / JetBrains Mono |

---

## 11. Métricas de Éxito (Propuesta)

| Métrica | Target | Cómo medir | Estado |
|---|---|---|---|
| **OCR accuracy** | ≥90% ingredientes correctos | Golden set 30 etiquetas reales MX | ✅ 100% en 13 muestras |
| **Entity resolution precision** | ≥95% CAS / ≥85% fuzzy | Ground truth 200+ pares post-dogfood | ⏳ Calibración post-MVP |
| **RAG precision@3** | ≥85% | 50 queries curadas, anotadas | ⏳ Post-MVP |
| **p95 latencia `/scan/barcode`** | <3s | OpenTelemetry + Grafana (Fase 2) | ⏳ Medir en prod |
| **p95 latencia `/scan/photo`** | <5s | Mismo | ⏳ Medir en prod |
| **Test coverage backend** | ≥80% en `services/` + `routers/` | `pytest --cov` | ✅ 90 tests passing |
| **E2E test coverage** | Core 32/32 ✅; alternatives E2E pendiente | Playwright specs/features/ | ⏳ Alternatives pendiente |
| **Frontend Lighthouse** | ≥80 (perf/acc/best-practices) | Lighthouse CI en Vercel | ⏳ Post-deploy |
| **Uptime (Fase 2+)** | ≥99.5% | Monitoring / alertas | ⏳ Fase 2 |

---

## 12. Próximos Pasos (Orden de Prioridad)

### FASE 2: Ingesta de Productos (Cerrado ✅ — PRs #14 + #17)

- ✅ Scripts implementados: `ingest_off_mexico.py`, `ingest_off_global.py`, `ingest_usda.py`
- ✅ Curation pipeline: `compute_clean_scores.py`, `index_products_chroma.py`, `seed_alternatives_fixture.py`

### FASE 2: Testing & Validation

1. **E2E testing de alternatives (Playwright)** — casos de alternatives + existing flows.
2. **Frontend CI/CD (GitHub Actions)** — `pnpm install + build + lint + typecheck`. ~2h.
3. **Deployment staging** — docker compose full stack en Render/Railway, API key Gemini pagada.
4. **Dogfood real** — scan productos reales con alternatives, interview usuarios, calibración HITL.

### FASE 3: Optimizaciones de valor (candidatos)

5. **Streaming progresivo del pipeline** — mostrar semáforo primero (~2s), ingredients (~4s), insights al final (~8s).
6. **Scan result sharing** — URL única compartible del resultado de scan (para médico/nutriólogo).
7. **Caching inteligente por barcode+biomarker_hash** — evitar re-correr Gemini para el mismo producto con mismos biomarcadores.

---

## 13. Archivos de Referencia

| Archivo | Contenido |
|---|---|
| `.claude/plans/backend.md` | Especificación técnica backend (Fases 1–6) |
| `.claude/plans/frontend.md` | Especificación técnica frontend (Fase 7) |
| `docs/reviews/18-04.md` | Tracking de cambios y decisiones (§1–13) |
| `docs/design/tokens.md` | Design system tokens (semáforo, tipografía, motion) |
| `docs/design/login/` | Handoff histórico login (referencia visual) |
| `docs/prompts.md` | Prompt templates (sincronizados con `app/agents/prompts.py`) |
| `docs/embedding-strategy.md` | Estrategia BGE-M3 primary + Gemini fallback |
| `docs/deployment.md` | Runbook deploy local/staging/prod, rotación AES_KEY, KMS path |
| `docs/off-contribution.md` | Flujo contribución Open Food Facts (Fase 2) |
| `backend/CLAUDE.md` | Documentación backend (stack, convenciones, cómo correr) |
| `frontend/CLAUDE.md` | Documentación frontend (stack, convenciones, cómo correr) |
| `docs/legal/privacy-policy.md` | Borrador política de privacidad (pendiente) |
| `docs/legal/terms-of-service.md` | Borrador términos de uso (pendiente) |
| `docs/superpowers/specs/2026-05-12-product-ingestion-off-design.md` | Product Ingestion Pipeline — Fase 2.0.1 (BLOQUEANTE) |
| `docs/superpowers/specs/2026-05-08-alternative-matching-design.md` | Alternative Matching Feature Design — Fase 2.1 |
| `docs/superpowers/specs/2026-05-09-scan-enrichment-design.md` | Scan → Product Enrichment Pipeline — Fase 2.1 |

---

**Versión anterior:** v5.0 (2026-04-18). Cambios principales en v6.0: actualización stack (TanStack Query, Next.js 15, BGE-M3 primary), cierre Fase 1 (backend MVP + frontend completadas), E2E testing pendiente, legal documentos en borrador.
