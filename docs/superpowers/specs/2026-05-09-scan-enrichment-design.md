# Scan → Product Enrichment Pipeline — Design Spec

**Fecha:** 2026-05-09
**Branch:** `feat/fase2-alternative-matching`
**Worktree:** `/Users/albertofragoso/Desktop/IA_engineer/bio_shield_fase2`
**Nunca tocar:** `main`

---

## 1. Objetivo

Convertir cada scan exitoso de usuario en una contribución automática al curated DB de BioShield. Actualmente los ingredientes extraídos por Gemini Vision se guardan en `scan_history.result_json` pero nunca se escriben de vuelta al `Product` — el `clean_score` no se calcula y el producto no entra a ChromaDB para recomendaciones. Este pipeline cierra ese gap de forma automática, sin latencia para el usuario.

---

## 1.1 Dependencias Críticas (BLOQUEANTE)

**⚠️ IMPORTANTE:** Este feature depende de la initial curation completada en Fase 2.0:

| Dependencia | Descripción | Estado |
|---|---|---|
| **Curated DB Ingestion (Fase 2.0)** | 400–900 productos seed vía Open Food Facts Search API v2 (MX) + curation pipeline | ⏳ `docs/superpowers/specs/2026-05-12-product-ingestion-off-design.md` |
| **`compute_clean_scores.py` script** | Calcula `clean_score` para todos los productos seed | ⏳ Ejecutar post-ingesta |
| **`index_products_chroma.py` script** | Indexa collection `products` en ChromaDB | ⏳ Ejecutar post-ingesta |
| **ChromaDB collection `products` existente** | Debe estar creado antes de escribir en él | ⏳ Auto-creado por script |

**Este pipeline ENRIQUECE el DB initial, pero requiere que exista primero.**

---

## 2. Arquitectura General

### 2.1 Trigger y flujo principal

El pipeline se activa en dos endpoints:

**`POST /scan/barcode`** (barcode scan):
```
Scan exitoso
    ├──► respuesta inmediata al usuario
    └──► BackgroundTask: enrich_product(barcode, resolved, confidence, "scan")
              └── si confidence_avg ≥ 0.8 y product.ingredients_json is None
                      → escribe ingredients_json, clean_score
                      → re-indexa en ChromaDB
```

**`POST /scan/photo`** (foto scan) — tres excepciones en cascada:
```
Gemini Vision extrae ingredientes + intenta barcode
    │
    ├─► Ex.1: barcode visible en imagen
    │         → usar barcode real (no pseudo)
    │         → BackgroundTask: enrich_product (mismo flujo que barcode scan)
    │         → show_barcode_cta = False
    │
    └─► Sin barcode extraído → pseudo_barcode = "photo-{uuid}"
              → product.needs_barcode_link = True
              → show_barcode_cta = True en ScanResponse
              │
              ├─► Ex.2: BackgroundTask — OFF lookup por nombre+marca
              │         → si encuentra barcode real:
              │               crea/actualiza Product(real_barcode)
              │               copia ingredientes del ScanHistory
              │               enrich_product(real_barcode, ...)
              │               photo_product.needs_barcode_link = False
              │
              └─► Ex.4: Usuario escanea barcode físico (CTA)
                        POST /scan/photo/{pseudo_barcode}/link
                        → link_photo_to_barcode(pseudo, real, user_id)
                        → mismo flujo que Ex.2
                        → redirige a /scan/{real_barcode}
```

### 2.2 Regla unificada de enriquecimiento (first-write-wins)

Un `Product` se enriquece si y solo si:
- `barcode NOT LIKE 'photo-%'` (barcode real)
- `ingredients_json IS NULL` (no enriquecido aún)
- `confidence_avg ≥ 0.8` (calidad mínima del OCR)

Primera escritura gana. No se sobreescribe aunque un scan posterior tenga más ingredientes.

**Evolución futura (documentada, fuera de scope):** Sistema de votación por mayoría — un ingrediente entra al perfil oficial solo si ≥ 2 usuarios distintos lo reportaron para el mismo barcode. Requiere tabla `product_ingredient_votes`. Candidato para Fase 3.

### 2.3 Patrón BackgroundTask

Mismo patrón que `_run_off_contribution` ya existente en el codebase. Cada BackgroundTask abre su propia `SessionLocal()` porque la sesión del request ya se cerró al responder.

```python
async def _run_enrich_task(barcode, resolved_json, avg_confidence, source, settings):
    db = SessionLocal()
    try:
        resolved = [IngredientResult.model_validate(i) for i in resolved_json]
        await enrich_product(barcode, resolved, avg_confidence, source, db, settings)
    except Exception as exc:
        logger.error("Enrichment failed for %s: %s", barcode, exc)
    finally:
        db.close()

async def _run_off_lookup_task(name, brand, pseudo_barcode, settings):
    db = SessionLocal()
    try:
        await try_off_lookup(name, brand, pseudo_barcode, db, settings)
    except Exception as exc:
        logger.error("OFF lookup failed for %s: %s", pseudo_barcode, exc)
    finally:
        db.close()
```

---

## 3. Data Model

### 3.1 Nuevos campos en `products`

Migration: encadena desde `aabbc492fe8d`. Usa `batch_alter_table` para compatibilidad SQLite.

| Campo | Tipo SQL | ORM | Default | Descripción |
|---|---|---|---|---|
| `ingredients_json` | `JSON` | `list[str] \| None` | `NULL` | Canonical names: `["sucralosa", "colorante rojo 40"]` |
| `ingredients_source` | `VARCHAR(20)` | `str \| None` | `NULL` | `"scan"` · `"off"` · `"manual"` |
| `ingredients_confidence` | `FLOAT` | `float \| None` | `NULL` | Promedio de confidence_score del scan que enriqueció |
| `needs_barcode_link` | `BOOLEAN` | `bool` | `FALSE` | `TRUE` en photo products sin barcode real resuelto |

**Índice:**
```sql
CREATE INDEX idx_products_needs_barcode_link
    ON products(needs_barcode_link)
    WHERE needs_barcode_link = TRUE;
```

**ORM:**
```python
# En class Product(Base):
ingredients_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
ingredients_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
ingredients_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
needs_barcode_link: Mapped[bool] = mapped_column(
    Boolean, nullable=False, default=False
)
```

### 3.2 `ScanResponse` — campo efímero (no persistido)

```python
class ScanResponse(BaseModel):
    # ... campos existentes ...
    show_barcode_cta: bool = False  # True solo en photo scans sin barcode resuelto
```

**Importante:** excluir de `result_json` en `_persist_scan_history`:
```python
result_json=response.model_dump(mode="json", exclude={"show_barcode_cta"})
```

El CTA se computa dinámicamente en `GET /scan/result/{barcode}` leyendo `product.needs_barcode_link` — nunca desde el resultado almacenado.

### 3.3 Nuevo schema — `LinkBarcodeRequest`

```python
class LinkBarcodeRequest(BaseModel):
    barcode: str = Field(..., min_length=8, max_length=14, pattern=r"^\d+$")
```

---

## 4. Enrichment Service (`app/services/enrichment.py`)

Módulo nuevo. Toda la lógica de enriquecimiento vive aquí — el router solo dispara BackgroundTasks.

### 4.1 `should_enrich(product) → bool`

```python
def should_enrich(product: Product) -> bool:
    return (
        product.ingredients_json is None
        and not product.barcode.startswith("photo-")
    )
```

### 4.2 `enrich_product(barcode, resolved, avg_confidence, source, db, settings) → None`

```python
async def enrich_product(
    barcode: str,
    resolved: list[IngredientResult],
    avg_confidence: float,
    source: str,
    db: Session,
    settings: Settings,
) -> None:
    product = db.scalar(
        select(Product)
        .where(Product.barcode == barcode)
        .with_for_update()  # serializa escrituras; compatible SQLite + PostgreSQL
    )
    if product is None or not should_enrich(product):
        return

    canonical_names = [r.canonical_name for r in resolved if r.canonical_name]
    product.ingredients_json = canonical_names
    product.ingredients_source = source
    product.ingredients_confidence = avg_confidence
    product.clean_score = _compute_clean_score(canonical_names, db)
    db.commit()

    if product.category:
        await _reindex_chroma(product, settings)
```

`_reindex_chroma` usa el mismo `embed_text` + `get_products_collection` de `index_products_chroma.py`. Solo indexa si el producto tiene categoría — consistente con el script de curation.

### 4.3 `try_off_lookup(name, brand, pseudo_barcode, db, settings) → None`

Busca en OFF por nombre+marca. Si encuentra barcode real, crea el Product real y lo enriquece con los ingredientes del ScanHistory del photo product.

```python
async def try_off_lookup(
    name: str | None,
    brand: str | None,
    pseudo_barcode: str,
    db: Session,
    settings: Settings,
) -> None:
    if not name:
        return
    barcode = await _off_lookup_barcode(name, brand, settings)
    if not barcode:
        return

    photo_product = db.scalar(select(Product).where(Product.barcode == pseudo_barcode))
    if not photo_product:
        return

    real_product = _upsert_product(db, barcode=barcode, name=name, brand=brand, image_url=None)
    db.flush()

    if should_enrich(real_product):
        history = db.scalar(
            select(ScanHistory)
            .where(ScanHistory.product_barcode == pseudo_barcode)
            .order_by(ScanHistory.scanned_at.desc())
        )
        if history and history.result_json and (history.confidence_score or 0) >= 0.8:
            resolved = [
                IngredientResult.model_validate(i)
                for i in history.result_json.get("ingredients", [])
            ]
            await enrich_product(barcode, resolved, history.confidence_score, "off", db, settings)

    photo_product.needs_barcode_link = False
    db.commit()
```

**`_off_lookup_barcode` (nueva función en `off_client.py`):**

```python
async def _off_lookup_barcode(
    name: str, brand: str | None, settings: Settings
) -> str | None:
    """Busca barcode en OFF por nombre+marca. Retorna EAN si confidence alta, None si no."""
    query = name
    if brand:
        query = f"{name} {brand}"
    url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={quote(query)}&cc=mx&json=1&page_size=5"
    # ... GET request, parsear primer resultado con score alto
    # Retorna product["code"] si encontrado, None si no
```

### 4.4 `link_photo_to_barcode(pseudo_barcode, real_barcode, user_id, db, settings) → Product`

```python
async def link_photo_to_barcode(
    pseudo_barcode: str,
    real_barcode: str,
    user_id: str,
    db: Session,
    settings: Settings,
) -> Product:
    # Validar ownership
    history = db.scalar(
        select(ScanHistory)
        .where(
            ScanHistory.product_barcode == pseudo_barcode,
            ScanHistory.user_id == user_id,
        )
        .order_by(ScanHistory.scanned_at.desc())
    )
    if not history:
        raise HTTPException(status_code=403, detail="Scan no encontrado o no autorizado.")

    photo_product = db.scalar(select(Product).where(Product.barcode == pseudo_barcode))

    real_product = _upsert_product(
        db, barcode=real_barcode,
        name=photo_product.name if photo_product else None,
        brand=None, image_url=None,
    )
    db.flush()

    if history.result_json and should_enrich(real_product):
        resolved = [
            IngredientResult.model_validate(i)
            for i in history.result_json.get("ingredients", [])
        ]
        avg_conf = history.confidence_score or 0.0
        if avg_conf >= 0.8:
            await enrich_product(real_barcode, resolved, avg_conf, "scan", db, settings)

    if photo_product:
        photo_product.needs_barcode_link = False
    db.commit()
    return real_product
```

### 4.5 `_compute_clean_score` (helper privado)

Reemplaza el placeholder vacío de `compute_clean_scores.py`. La lógica vive aquí — el script pasa a ser un thin wrapper.

```python
def _compute_clean_score(canonical_names: list[str], db: Session) -> int:
    _BANNED = {"Banned", "Restricted"}
    score = 0
    for name in canonical_names:
        ing = db.scalar(select(Ingredient).where(Ingredient.canonical_name.ilike(name)))
        if ing is None:
            continue
        statuses = db.scalars(
            select(RegulatoryStatus).where(RegulatoryStatus.ingredient_id == ing.id)
        )
        if any(s.status in _BANNED for s in statuses):
            score += 1
    return score
```

**Limitación conocida:** ingredientes que no existen en la tabla `Ingredient` se saltan silenciosamente — contribuyen `0` al score. Esto puede subestimar el riesgo de productos nuevos. Mitigación: los ingredientes en `resolved` ya pasaron por el pipeline RAG de LangGraph, por lo que la mayoría deberían estar en la tabla.

---

## 5. Cambios en Scan Router (`app/routers/scan.py`)

### 5.1 `scan_barcode` — agrega BackgroundTask

```python
async def scan_barcode(request, body, background_tasks: BackgroundTasks, ...):
    # ... código existente hasta db.commit() ...

    resolved = final_state.get("resolved") or []
    avg_conf = sum(r.confidence_score for r in resolved) / len(resolved) if resolved else 0.0
    if avg_conf >= 0.8:
        background_tasks.add_task(
            _run_enrich_task,
            barcode=body.barcode,
            resolved_json=[r.model_dump(mode="json") for r in resolved],
            avg_confidence=avg_conf,
            source="scan",
            settings=settings,
        )
    return response
```

### 5.2 `scan_photo` — Excepciones 1 + 2 + CTA

```python
async def scan_photo(request, body, background_tasks: BackgroundTasks, ...):
    # ... error checks existentes ...

    # Ex.1: barcode extraído por Gemini
    extracted_barcode = final_state.get("barcode")
    barcode_to_use = extracted_barcode or f"photo-{uuid4().hex[:16]}"
    show_cta = not bool(extracted_barcode)

    product = _upsert_product(db, barcode=barcode_to_use,
                               name=final_state.get("product_name"),
                               brand=None, image_url=None)
    if show_cta:
        product.needs_barcode_link = True

    response = _build_response(final_state, product.barcode, product.name)
    response.show_barcode_cta = show_cta
    _persist_scan_history(db, current_user, product.barcode, final_state, response)
    db.commit()

    resolved = final_state.get("resolved") or []
    avg_conf = sum(r.confidence_score for r in resolved) / len(resolved) if resolved else 0.0

    if extracted_barcode and avg_conf >= 0.8:
        background_tasks.add_task(_run_enrich_task,
            barcode=extracted_barcode,
            resolved_json=[r.model_dump(mode="json") for r in resolved],
            avg_confidence=avg_conf, source="scan", settings=settings)
    elif show_cta:
        # Ex.2: OFF lookup async
        background_tasks.add_task(_run_off_lookup_task,
            name=final_state.get("product_name"),
            brand=final_state.get("product_brand"),
            pseudo_barcode=barcode_to_use,
            settings=settings)

    return response
```

### 5.3 `GET /scan/result/{barcode}` — CTA dinámico

```python
def get_scan_result(barcode, current_user, db):
    row = db.scalar(select(ScanHistory).where(...).order_by(ScanHistory.scanned_at.desc()))
    if row is None:
        raise HTTPException(status_code=404, detail="Scan no encontrado.")

    product = db.scalar(select(Product).where(Product.barcode == barcode))
    response = ScanResponse.model_validate(row.result_json)
    response.show_barcode_cta = product.needs_barcode_link if product else False
    return response
```

### 5.4 Nuevo endpoint `POST /scan/photo/{pseudo_barcode}/link`

```python
@router.post("/photo/{pseudo_barcode}/link", response_model=ScanResponse)
@limiter.limit("10/minute")
async def link_photo_barcode(
    request: Request,
    pseudo_barcode: str,
    body: LinkBarcodeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    from app.services.enrichment import link_photo_to_barcode as _link
    real_product = await _link(
        pseudo_barcode=pseudo_barcode,
        real_barcode=body.barcode,
        user_id=str(current_user.id),
        db=db, settings=settings,
    )
    history = db.scalar(
        select(ScanHistory)
        .where(ScanHistory.product_barcode == pseudo_barcode,
               ScanHistory.user_id == current_user.id)
        .order_by(ScanHistory.scanned_at.desc())
    )
    if not history or not history.result_json:
        raise HTTPException(status_code=404, detail="Scan no encontrado.")
    response = ScanResponse.model_validate(history.result_json)
    response.product_barcode = real_product.barcode
    response.show_barcode_cta = False
    return response
```

---

## 6. Gemini Prompt + Schema

### 6.1 `ProductExtraction` schema

```python
class ProductExtraction(BaseModel):
    # ... campos existentes ...
    barcode: str | None = None  # EAN/UPC si es visible en la imagen
```

### 6.2 Adición al prompt de extracción

```
Si el código de barras EAN/UPC aparece como número impreso en la imagen
(8–14 dígitos), extráelo en el campo `barcode`. Si no es claramente
visible o legible, devuelve null.
```

### 6.3 Propagación en LangGraph state

El nodo que procesa la extracción de Gemini propaga:
```python
state["barcode"] = extraction.barcode  # None si no encontrado
```

---

## 7. `compute_clean_scores.py` — actualización

El script pasa a ser un thin wrapper que llama `_compute_clean_score` de `enrichment.py`:

```python
from app.services.enrichment import _compute_clean_score

def main():
    db = SessionLocal()
    try:
        products = list(db.scalars(select(Product).where(Product.ingredients_json.isnot(None))))
        for product in products:
            product.clean_score = _compute_clean_score(product.ingredients_json or [], db)
        db.commit()
        logger.info("Done. %d products updated.", len(products))
    finally:
        db.close()
```

Antes filtraba todos los products con `ingredients: list[str] = []` hardcodeado (bug). Ahora filtra solo productos con `ingredients_json` ya poblado.

---

## 8. Frontend

### 8.1 `types.ts`

```typescript
export interface ScanResponse {
  // ... campos existentes ...
  show_barcode_cta: boolean;
}

export interface LinkBarcodeRequest {
  barcode: string;
}
```

### 8.2 `scan.ts`

```typescript
export async function linkPhotoToBarcode(
  pseudoBarcode: string,
  barcode: string
): Promise<ScanResponse> {
  return apiFetch<ScanResponse>(`/scan/photo/${pseudoBarcode}/link`, {
    method: "POST",
    body: JSON.stringify({ barcode } satisfies LinkBarcodeRequest),
  });
}
```

### 8.3 `scan/[id]/page.tsx` — `LinkBarcodeCard`

CTA con input visible directamente (sin click intermedio). Se monta cuando `data.show_barcode_cta === true` y el id empieza con `"photo-"`.

```tsx
function LinkBarcodeCard({ pseudoBarcode }: { pseudoBarcode: string }) {
  const router = useRouter();
  const [barcode, setBarcode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLink() {
    if (!/^\d{8,14}$/.test(barcode)) {
      setError("Código inválido — debe tener 8 a 14 dígitos");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await linkPhotoToBarcode(pseudoBarcode, barcode);
      router.push(`/scan/${result.product_barcode}`);
    } catch {
      setError("No pudimos linkear el producto. Intenta de nuevo.");
      setLoading(false);
    }
  }

  return (
    <div className="rounded-[14px] border border-[rgba(96,165,250,.2)] bg-[rgba(12,24,40,.5)] p-4 flex flex-col gap-3">
      <div className="flex items-start gap-2">
        <span className="text-[18px]">🔗</span>
        <div>
          <p className="text-[13px] font-semibold text-[#cbd5e1]">
            ¿Tienes el producto a la mano?
          </p>
          <p className="text-[11px] text-[#475569] mt-0.5">
            Escanea su código de barras para que BioShield lo recuerde
            y pueda sugerirte alternativas más limpias.
          </p>
        </div>
      </div>
      <input
        type="text"
        inputMode="numeric"
        pattern="\d*"
        placeholder="Ej. 7501030495584"
        value={barcode}
        onChange={(e) => setBarcode(e.target.value.replace(/\D/g, ""))}
        className="w-full px-3 py-2 rounded-lg bg-[#0f172a] border border-[#1e293b] text-[13px] text-[#f1f5f9] placeholder:text-[#334155] focus:outline-none focus:border-[#3b82f6]"
      />
      {error && <p className="text-[11px] text-[#f87171]">{error}</p>}
      <button
        onClick={handleLink}
        disabled={loading || barcode.length < 8}
        className="w-full py-2 rounded-lg bg-[#2563eb] text-white text-[13px] font-semibold disabled:opacity-40 hover:bg-[#1d4ed8] transition-colors"
      >
        {loading ? "Guardando..." : "Confirmar"}
      </button>
    </div>
  );
}
```

**Posición en el render** — después del hero card, antes del botón de alternativas:

```tsx
{data.show_barcode_cta && id.startsWith("photo-") && (
  <LinkBarcodeCard pseudoBarcode={id} />
)}
```

**Edge case documentado:** Si `try_off_lookup` (Ex.2) ya resolvió el barcode en background y el usuario igualmente toca el CTA con un barcode diferente, ambos Products quedan enriquecidos con los mismos ingredientes. Datos no corruptos — aceptable en first-write-wins. Candidato para depuración en Evolution B.

---

## 9. Tests

**`backend/tests/test_enrichment.py`** — unit + integration tests:

- `test_should_enrich_returns_false_if_already_enriched`
- `test_should_enrich_returns_false_for_pseudo_barcode`
- `test_should_enrich_returns_true_for_clean_product`
- `test_enrich_product_writes_ingredients_and_score`
- `test_enrich_product_skips_if_low_confidence` (called with avg < 0.8)
- `test_enrich_product_concurrent_skip_locked` (dos calls al mismo barcode — segundo no sobreescribe)
- `test_try_off_lookup_links_photo_product`
- `test_try_off_lookup_skips_if_no_name`
- `test_link_photo_to_barcode_validates_ownership` (user_id incorrecto → 403)
- `test_link_photo_to_barcode_enriches_real_product`
- `test_compute_clean_score_counts_banned_ingredients`
- `test_compute_clean_score_ignores_unknown_ingredients`

---

## 10. Docs a actualizar

| Archivo | Sección | Cambio |
|---|---|---|
| `docs/architecture.md` | Nueva §3 | Enrichment Pipeline — trigger, flujo, first-write-wins |
| `docs/embedding-strategy.md` | §11 (collection `products`) | Nota: collection crece automáticamente vía scans, no solo curation scripts |
| `PRD.md` | §Fase 2 Alternative Matching | Mencionar enrichment pipeline como extensión |

---

## 11. Next Step — Fase 3: Ingesta externa de catálogo MX

**Documentado como siguiente paso, fuera del scope de este feature.**

**Objetivo:** ampliar el curated DB con productos que aún no han sido escaneados por ningún usuario, usando fuentes externas de catálogo MX.

**Fuentes propuestas:**

| Fuente | Approach | Ingredientes | Viabilidad |
|---|---|---|---|
| Open Food Facts (otros países) | `ingest_off.py --country-tag en:spain --market es` | Directamente | 🟢 Alta |
| Soriana | Scraping bot (BeautifulSoup) | No disponible online | 🟡 Media |
| Costco MX | Scraping — anti-bot agresivo | No disponible online | 🔴 Baja |

**Approach recomendado para Fase 3:**
1. Parametrizar `ingest_off_mexico.py` → `ingest_off.py --country-tag --market` para agregar países sin duplicar código
2. Agregar columna `market` al modelo `Product` (Alembic migration) y filtro en `alternatives.py`
3. Ver estrategia completa de escalado multi-país en `docs/superpowers/specs/2026-05-12-product-ingestion-off-design.md §6`
4. Los ingredientes que OFF no tenga se llenan vía el flywheel de scans de usuarios (este pipeline)

**Branch:** nuevo `feat/fase3-catalog-ingestion` desde `main` cuando Fase 2 esté merged.

---

## 12. Archivos modificados / creados

| Archivo | Tipo | Cambio |
|---|---|---|
| `backend/alembic/versions/{hash}_add_enrichment_fields.py` | Nuevo | Migración: 4 campos en `products` |
| `backend/app/models/__init__.py` | Modificado | Campos ORM en `Product` |
| `backend/app/schemas/models.py` | Modificado | `ScanResponse.show_barcode_cta`, `LinkBarcodeRequest` |
| `backend/app/services/enrichment.py` | Nuevo | Toda la lógica de enriquecimiento |
| `backend/app/services/off_client.py` | Modificado | `_off_lookup_barcode()` |
| `backend/app/routers/scan.py` | Modificado | BackgroundTasks, scan_photo Ex.1+2, /link endpoint, GET fix |
| `backend/app/agents/` (Gemini node) | Modificado | Prompt + `ProductExtraction.barcode` field |
| `backend/scripts/compute_clean_scores.py` | Modificado | Thin wrapper → llama `_compute_clean_score` |
| `backend/tests/test_enrichment.py` | Nuevo | 12 tests |
| `frontend/lib/api/types.ts` | Modificado | `ScanResponse.show_barcode_cta`, `LinkBarcodeRequest` |
| `frontend/lib/api/scan.ts` | Modificado | `linkPhotoToBarcode()` |
| `frontend/app/(app)/scan/[id]/page.tsx` | Modificado | `LinkBarcodeCard`, render condicional |
| `docs/architecture.md` | Modificado | §3 Enrichment Pipeline |
| `docs/embedding-strategy.md` | Modificado | §11 nota flywheel |
| `PRD.md` | Modificado | Fase 2 menciona enrichment |
