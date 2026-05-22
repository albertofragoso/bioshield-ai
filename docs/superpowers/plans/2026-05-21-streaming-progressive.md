# Streaming Progresivo del Pipeline de Scan — Implementation Plan

> **IMPLEMENTADO ✅ — PR #23** (feature/streaming-progressive → main, 2026-05-22)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Convertir `POST /scan/barcode` y `POST /scan/photo` de `graph.ainvoke()` a `graph.astream_events()` emitiendo SSE events progresivos, y actualizar el frontend para mostrar resultados parciales conforme llegan.

**Architecture:** Backend emite `StreamingResponse(text/event-stream)` con eventos `init → ingredients → insights → semaphore → done`. Zustand store en root layout persiste el stream a través de la navegación Next.js. Pending row en DB se inserta antes del stream para evitar 404 zombie.

**Tech Stack:** FastAPI 0.115, LangGraph 0.3 `astream_events()` v2, SQLAlchemy 2.0, Alembic, Next.js 16.2 App Router, Zustand 5.0, TanStack Query v5, TypeScript

---

## Archivos a crear/modificar

| Archivo | Cambio |
|---------|--------|
| `backend/app/models/__init__.py` | Columna `status: String(10)` en `ScanHistory` |
| `alembic/versions/<rev>_add_scan_status.py` | Migration: columna `status` con default `'done'` |
| `backend/app/routers/scan.py` | `ainvoke` → `astream_events`, `StreamingResponse`, pending row, error event |
| `backend/tests/test_scan.py` | Tests: stream events, pending row, error event |
| `frontend/lib/stores/scanning.ts` | Nuevo Zustand slice `scanStreamingStore` |
| `frontend/app/providers.tsx` | Sin cambio (el store es singleton, no necesita Provider) |
| `frontend/lib/api/scan.ts` | Función `startBarcodeStream()`, `startPhotoStream()` |
| `frontend/app/(app)/scan/page.tsx` | Llamar `startStream()` en lugar de mutations |
| `frontend/app/(app)/scan/[id]/page.tsx` | Leer de Zustand cuando `status === 'streaming'`; `clearStream()` en cleanup |

---

### Task 1: Columna `status` en ScanHistory + Migration

**Files:**
- Modify: `backend/app/models/__init__.py`
- Create: `alembic/versions/<rev>_add_scan_status.py`

- [x] **Step 1: Escribir el test failing**

```python
# backend/tests/test_scan.py — agregar al final del archivo
async def test_scan_history_has_status_column(db_session: AsyncSession):
    """Verifica que ScanHistory tiene columna status."""
    from backend.app.models import ScanHistory
    import inspect
    cols = {c.key for c in inspect(ScanHistory).mapper.columns}
    assert "status" in cols
```

- [x] **Step 2: Correr el test para verificar que falla**

```bash
cd backend && python -m pytest tests/test_scan.py::test_scan_history_has_status_column -v
```

Esperado: `FAILED — AssertionError: assert "status" in cols`

- [x] **Step 3: Agregar columna al modelo**

En `backend/app/models/__init__.py`, dentro de la clase `ScanHistory` (después de `result_json`):

```python
status: Mapped[str] = mapped_column(
    String(10), nullable=False, server_default="done"
)
```

- [x] **Step 4: Generar la migration Alembic**

```bash
cd backend && alembic revision --autogenerate -m "add_scan_status"
```

Abrir el archivo generado en `alembic/versions/` y verificar que el `upgrade()` contiene algo como:

```python
def upgrade() -> None:
    op.add_column('scan_history',
        sa.Column('status', sa.String(10), nullable=False, server_default='done')
    )

def downgrade() -> None:
    op.drop_column('scan_history', 'status')
```

- [x] **Step 5: Aplicar la migration**

```bash
cd backend && alembic upgrade head
```

Esperado: `Running upgrade ... -> <rev>, add_scan_status`

- [x] **Step 6: Correr el test para verificar que pasa**

```bash
cd backend && python -m pytest tests/test_scan.py::test_scan_history_has_status_column -v
```

Esperado: `PASSED`

- [x] **Step 7: Commit**

```bash
git add backend/app/models/__init__.py alembic/versions/*_add_scan_status.py
git commit -m "feat(db): add status column to scan_history for streaming"
```

---

### Task 2: Helper `_update_scan_history()` y pending row pattern

**Files:**
- Modify: `backend/app/routers/scan.py`

El helper actual `_persist_scan_history()` hace INSERT. Necesitamos separar: insertar pending row primero, luego UPDATE al final del stream.

- [x] **Step 1: Escribir test failing para el pending row pattern**

```python
# backend/tests/test_scan.py
async def test_scan_stream_pending_row_created(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    """La fila ScanHistory existe con status='pending' antes de que el stream termine."""
    from backend.app import models
    events_seen = []

    async def mock_astream_events(*args, **kwargs):
        # Simula stream lento — yield init y pausa
        yield {"event": "on_chain_start", "name": "LangGraph", "data": {}}
        # Aquí el test verifica que la fila ya existe
        row = await db_session.scalar(
            select(models.ScanHistory).where(models.ScanHistory.status == "pending")
        )
        events_seen.append(row is not None)
        # Continuar stream completo para limpiar
        yield {
            "event": "on_chain_end",
            "name": "identify_product",
            "data": {"output": {"product_name": "Test", "product_brand": "Brand",
                                "ingredients": [], "source": "barcode"}},
        }
        yield {
            "event": "on_chain_end",
            "name": "personalize",
            "data": {"output": {"personalized_insights": []}},
        }
        yield {
            "event": "on_chain_end",
            "name": "calculate_risk",
            "data": {"output": {"semaphore": "GREEN", "conflict_severity": None,
                                "resolved": []}},
        }

    monkeypatch.setattr("backend.app.routers.scan.graph.astream_events", mock_astream_events)

    async with client.stream("POST", "/scan/barcode",
                             json={"barcode": "1234567890"},
                             cookies={"access_token": make_test_jwt()}) as response:
        async for _ in response.aiter_lines():
            pass

    assert True in events_seen, "La fila pending nunca existió antes de que el stream avanzara"
```

- [x] **Step 2: Correr el test para verificar que falla**

```bash
cd backend && python -m pytest tests/test_scan.py::test_scan_stream_pending_row_created -v
```

Esperado: `FAILED — AttributeError: module 'backend.app.routers.scan' has no attribute graph.astream_events` (o similar — el endpoint aún usa ainvoke)

- [x] **Step 3: Agregar función `_create_pending_row()`**

En `backend/app/routers/scan.py`, reemplazar `_persist_scan_history()` con dos helpers:

```python
async def _create_pending_row(
    db: AsyncSession,
    barcode: str,
    user_id: int,
) -> ScanHistory:
    # Insertar fila vacía antes de iniciar el stream.
    # Garantiza que /scan/[id] no retorna 404 durante el streaming.
    row = ScanHistory(
        product_barcode=barcode,
        user_id=user_id,
        result_json=None,
        status="pending",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _finalize_scan_history(
    db: AsyncSession,
    scan_id: int,
    response: ScanResponse,
) -> None:
    # UPDATE de la fila pending con el resultado completo.
    row = await db.get(ScanHistory, scan_id)
    if not row:
        return
    row.result_json = response.model_dump(
        mode="json", exclude={"show_barcode_cta"}
    )
    row.status = "done"
    await db.commit()
```

- [x] **Step 4: Correr el test para verificar que pasa**

```bash
cd backend && python -m pytest tests/test_scan.py::test_scan_stream_pending_row_created -v
```

Esperado: `PASSED`

- [x] **Step 5: Commit**

```bash
git add backend/app/routers/scan.py
git commit -m "feat(scan): add pending row helpers for streaming pattern"
```

---

### Task 3: Convertir `scan_barcode` a `StreamingResponse`

**Files:**
- Modify: `backend/app/routers/scan.py`

- [x] **Step 1: Escribir tests failing**

```python
# backend/tests/test_scan.py
async def test_scan_barcode_returns_event_stream(
    client: AsyncClient, mock_graph
):
    """Verifica que el endpoint retorna content-type text/event-stream."""
    async with client.stream("POST", "/scan/barcode",
                             json={"barcode": "1234567890"},
                             cookies={"access_token": make_test_jwt()}) as response:
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


async def test_scan_barcode_streams_events_in_order(
    client: AsyncClient, mock_graph
):
    """Verifica que los eventos llegan en orden: init → ingredients → insights → semaphore → done."""
    event_names = []
    async with client.stream("POST", "/scan/barcode",
                             json={"barcode": "1234567890"},
                             cookies={"access_token": make_test_jwt()}) as response:
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event_names.append(line.split(":", 1)[1].strip())

    assert event_names == ["init", "ingredients", "insights", "semaphore", "done"]


async def test_scan_barcode_init_event_has_scan_id(
    client: AsyncClient, mock_graph
):
    """El evento init contiene scan_id."""
    import json
    init_data = None
    async with client.stream("POST", "/scan/barcode",
                             json={"barcode": "1234567890"},
                             cookies={"access_token": make_test_jwt()}) as response:
        lines = [l async for l in response.aiter_lines()]

    for i, line in enumerate(lines):
        if line == "event: init":
            init_data = json.loads(lines[i + 1].removeprefix("data: "))
            break

    assert init_data is not None
    assert "scan_id" in init_data
    assert "product_barcode" in init_data
```

Fixture `mock_graph` en `conftest.py`:

```python
# backend/tests/conftest.py
@pytest.fixture
def mock_graph(monkeypatch):
    """Mock de graph.astream_events que retorna un stream completo mínimo."""
    async def _stream(*args, **kwargs):
        yield {"event": "on_chain_start", "name": "LangGraph", "data": {}}
        yield {
            "event": "on_chain_end",
            "name": "identify_product",
            "data": {"output": {
                "product_name": "TestProd",
                "product_brand": "Brand",
                "ingredients": [{"name": "Azúcar", "is_concerning": False,
                                  "concern_detail": None, "is_conflicting": False,
                                  "conflict_detail": None}],
                "source": "barcode",
            }},
        }
        yield {
            "event": "on_chain_end",
            "name": "personalize",
            "data": {"output": {"personalized_insights": []}},
        }
        yield {
            "event": "on_chain_end",
            "name": "calculate_risk",
            "data": {"output": {
                "semaphore": "GREEN",
                "conflict_severity": None,
                "resolved": [{"name": "Azúcar", "is_concerning": False,
                               "concern_detail": None, "is_conflicting": False,
                               "conflict_detail": None}],
            }},
        }

    monkeypatch.setattr("backend.app.routers.scan.graph.astream_events", _stream)
```

- [x] **Step 2: Correr los tests para verificar que fallan**

```bash
cd backend && python -m pytest tests/test_scan.py::test_scan_barcode_returns_event_stream tests/test_scan.py::test_scan_barcode_streams_events_in_order -v
```

Esperado: `FAILED` — los tests fallan porque el endpoint aún retorna JSON.

- [x] **Step 3: Reemplazar `scan_barcode` con la versión streaming**

En `backend/app/routers/scan.py`, reemplazar la función `scan_barcode` completa:

```python
@router.post("/barcode")
async def scan_barcode(
    body: BarcodeScanRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    # Insertar fila pending ANTES de iniciar el stream para evitar 404 zombie.
    pending_row = await _create_pending_row(db, body.barcode, current_user.id)

    await _check_token_budget(db, current_user.id, settings)

    product = await _upsert_product(db, body.barcode)

    state = GraphState(
        barcode=body.barcode,
        source="barcode",
        biomarkers=current_user.biomarkers or [],
        product_id=product.id if product else None,
    )

    async def event_generator():
        try:
            yield f"event: init\ndata: {json.dumps({'scan_id': pending_row.id, 'product_barcode': body.barcode})}\n\n"

            final_state: dict = {}

            async for event in graph.astream_events(state.model_dump(), version="v2"):
                if event["event"] != "on_chain_end":
                    continue
                name = event["name"]
                output = event["data"].get("output", {})

                if name == "identify_product":
                    payload = {
                        "product_name": output.get("product_name"),
                        "product_brand": output.get("product_brand"),
                        "ingredients": output.get("ingredients", []),
                        "source": output.get("source", "barcode"),
                    }
                    yield f"event: ingredients\ndata: {json.dumps(payload)}\n\n"
                    final_state.update(output)

                elif name == "extract_ingredients":
                    payload = {
                        "product_name": output.get("product_name"),
                        "product_brand": output.get("product_brand"),
                        "ingredients": output.get("ingredients", []),
                        "source": output.get("source", "barcode"),
                    }
                    yield f"event: ingredients\ndata: {json.dumps(payload)}\n\n"
                    final_state.update(output)

                elif name == "personalize":
                    payload = {"personalized_insights": output.get("personalized_insights", [])}
                    yield f"event: insights\ndata: {json.dumps(payload)}\n\n"
                    final_state.update(output)

                elif name == "calculate_risk":
                    final_state.update(output)
                    # calculate_risk es el último nodo — persistir y emitir semáforo.
                    response = _build_response(final_state, body.barcode)
                    await _finalize_scan_history(db, pending_row.id, response)

                    payload = {
                        "semaphore": output.get("semaphore"),
                        "conflict_severity": output.get("conflict_severity"),
                        "ingredients": [i.model_dump() for i in response.ingredients],
                    }
                    yield f"event: semaphore\ndata: {json.dumps(payload)}\n\n"

            yield f"event: done\ndata: {json.dumps({'scan_id': pending_row.id})}\n\n"

            # Enrich task (background, sin bloquear el stream).
            background_tasks.add_task(_run_enrich_task, db, body.barcode)

        except Exception as exc:
            error_payload = json.dumps({"message": "Pipeline failed", "code": "PIPELINE_ERROR"})
            yield f"event: error\ndata: {error_payload}\n\n"
            raise exc

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

Agregar imports al inicio del archivo si faltan:

```python
import json
from fastapi.responses import StreamingResponse
```

- [x] **Step 4: Correr los tests**

```bash
cd backend && python -m pytest tests/test_scan.py::test_scan_barcode_returns_event_stream tests/test_scan.py::test_scan_barcode_streams_events_in_order tests/test_scan.py::test_scan_barcode_init_event_has_scan_id -v
```

Esperado: `PASSED` los tres.

- [x] **Step 5: Commit**

```bash
git add backend/app/routers/scan.py backend/tests/conftest.py backend/tests/test_scan.py
git commit -m "feat(scan): convert scan_barcode to SSE streaming with astream_events"
```

---

### Task 4: Convertir `scan_photo` a `StreamingResponse`

**Files:**
- Modify: `backend/app/routers/scan.py`

- [x] **Step 1: Escribir tests failing**

```python
# backend/tests/test_scan.py
async def test_scan_photo_returns_event_stream(
    client: AsyncClient, mock_graph_photo
):
    """Verifica que scan_photo también retorna text/event-stream."""
    import io
    fake_image = io.BytesIO(b"fakejpegdata")
    fake_image.name = "test.jpg"

    async with client.stream(
        "POST", "/scan/photo",
        files={"file": ("test.jpg", fake_image, "image/jpeg")},
        cookies={"access_token": make_test_jwt()},
    ) as response:
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


async def test_scan_photo_streams_events_in_order(
    client: AsyncClient, mock_graph_photo
):
    """scan_photo emite init → ingredients → insights → semaphore → done."""
    import io
    fake_image = io.BytesIO(b"fakejpegdata")
    event_names = []

    async with client.stream(
        "POST", "/scan/photo",
        files={"file": ("test.jpg", fake_image, "image/jpeg")},
        cookies={"access_token": make_test_jwt()},
    ) as response:
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event_names.append(line.split(":", 1)[1].strip())

    assert event_names == ["init", "ingredients", "insights", "semaphore", "done"]
```

Fixture `mock_graph_photo` en `conftest.py`:

```python
@pytest.fixture
def mock_graph_photo(monkeypatch):
    """Mock del pipeline de foto."""
    async def _stream(*args, **kwargs):
        yield {"event": "on_chain_start", "name": "LangGraph", "data": {}}
        yield {
            "event": "on_chain_end",
            "name": "extract_ingredients",
            "data": {"output": {
                "product_name": "PhotoProd",
                "product_brand": None,
                "ingredients": [],
                "source": "photo",
            }},
        }
        yield {
            "event": "on_chain_end",
            "name": "personalize",
            "data": {"output": {"personalized_insights": []}},
        }
        yield {
            "event": "on_chain_end",
            "name": "calculate_risk",
            "data": {"output": {
                "semaphore": "GREEN",
                "conflict_severity": None,
                "resolved": [],
            }},
        }

    monkeypatch.setattr("backend.app.routers.scan.graph.astream_events", _stream)
```

- [x] **Step 2: Correr los tests para verificar que fallan**

```bash
cd backend && python -m pytest tests/test_scan.py::test_scan_photo_returns_event_stream tests/test_scan.py::test_scan_photo_streams_events_in_order -v
```

Esperado: `FAILED`

- [x] **Step 3: Reemplazar `scan_photo` con la versión streaming**

En `backend/app/routers/scan.py`, misma estructura que `scan_barcode` pero para foto:

```python
@router.post("/photo")
async def scan_photo(
    file: UploadFile,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    await _check_token_budget(db, current_user.id, settings)

    image_bytes = await file.read()
    photo_id = f"photo-{secrets.token_urlsafe(8)}"

    # Insertar fila pending antes de iniciar el stream.
    pending_row = await _create_pending_row(db, photo_id, current_user.id)

    state = GraphState(
        barcode=photo_id,
        source="photo",
        image_bytes=image_bytes,
        biomarkers=current_user.biomarkers or [],
        product_id=None,
    )

    async def event_generator():
        try:
            yield f"event: init\ndata: {json.dumps({'scan_id': pending_row.id, 'product_barcode': photo_id})}\n\n"

            final_state: dict = {}

            async for event in graph.astream_events(state.model_dump(), version="v2"):
                if event["event"] != "on_chain_end":
                    continue
                name = event["name"]
                output = event["data"].get("output", {})

                if name == "extract_ingredients":
                    payload = {
                        "product_name": output.get("product_name"),
                        "product_brand": output.get("product_brand"),
                        "ingredients": output.get("ingredients", []),
                        "source": "photo",
                    }
                    yield f"event: ingredients\ndata: {json.dumps(payload)}\n\n"
                    final_state.update(output)

                elif name == "personalize":
                    payload = {"personalized_insights": output.get("personalized_insights", [])}
                    yield f"event: insights\ndata: {json.dumps(payload)}\n\n"
                    final_state.update(output)

                elif name == "calculate_risk":
                    final_state.update(output)
                    response = _build_response(final_state, photo_id)
                    await _finalize_scan_history(db, pending_row.id, response)

                    payload = {
                        "semaphore": output.get("semaphore"),
                        "conflict_severity": output.get("conflict_severity"),
                        "ingredients": [i.model_dump() for i in response.ingredients],
                    }
                    yield f"event: semaphore\ndata: {json.dumps(payload)}\n\n"

            yield f"event: done\ndata: {json.dumps({'scan_id': pending_row.id})}\n\n"

        except Exception as exc:
            error_payload = json.dumps({"message": "Pipeline failed", "code": "PIPELINE_ERROR"})
            yield f"event: error\ndata: {error_payload}\n\n"
            raise exc

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

- [x] **Step 4: Correr los tests**

```bash
cd backend && python -m pytest tests/test_scan.py::test_scan_photo_returns_event_stream tests/test_scan.py::test_scan_photo_streams_events_in_order -v
```

Esperado: `PASSED`

- [x] **Step 5: Test de error event**

```python
async def test_scan_stream_error_event(
    client: AsyncClient, monkeypatch
):
    """Si el pipeline falla, el stream emite event: error."""
    async def _failing_stream(*args, **kwargs):
        yield {"event": "on_chain_start", "name": "LangGraph", "data": {}}
        raise RuntimeError("Simulated pipeline failure")
        yield  # hace que Python lo trate como generator

    monkeypatch.setattr("backend.app.routers.scan.graph.astream_events", _failing_stream)

    event_names = []
    async with client.stream("POST", "/scan/barcode",
                             json={"barcode": "1234567890"},
                             cookies={"access_token": make_test_jwt()}) as response:
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event_names.append(line.split(":", 1)[1].strip())

    assert "error" in event_names
```

```bash
cd backend && python -m pytest tests/test_scan.py::test_scan_stream_error_event -v
```

Esperado: `PASSED`

- [x] **Step 6: Correr suite completa del backend**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Todos los tests deben pasar.

- [x] **Step 7: Commit**

```bash
git add backend/app/routers/scan.py backend/tests/conftest.py backend/tests/test_scan.py
git commit -m "feat(scan): convert scan_photo to SSE streaming + error event test"
```

---

### Task 5: Zustand store `scanStreamingStore`

**Files:**
- Create: `frontend/lib/stores/scanning.ts`

- [x] **Step 1: Crear el store**

```typescript
// frontend/lib/stores/scanning.ts
import { create } from "zustand";

export type ScanStreamStatus = "idle" | "streaming" | "done" | "error";

export interface IngredientResult {
  name: string;
  is_concerning: boolean;
  concern_detail: string | null;
  is_conflicting: boolean;
  conflict_detail: string | null;
}

export interface PersonalizedInsight {
  insight: string;
  severity: string;
}

export interface ScanPartial {
  productName?: string;
  productBrand?: string;
  ingredients?: IngredientResult[];
  personalized_insights?: PersonalizedInsight[];
  semaphore?: string;
  conflict_severity?: string | null;
}

interface ScanStreamingState {
  scanId: string | null;
  productBarcode: string | null;
  status: ScanStreamStatus;
  partial: ScanPartial;
  _abort: AbortController | null;

  startBarcodeStream: (barcode: string) => void;
  startPhotoStream: (file: File) => void;
  clearStream: () => void;
  _handleEvent: (eventName: string, data: unknown) => void;
}

export const useScanStreamingStore = create<ScanStreamingState>((set, get) => ({
  scanId: null,
  productBarcode: null,
  status: "idle",
  partial: {},
  _abort: null,

  startBarcodeStream: (barcode) => {
    const prevAbort = get()._abort;
    prevAbort?.abort();

    const abort = new AbortController();
    set({ scanId: null, productBarcode: barcode, status: "streaming", partial: {}, _abort: abort });

    _consumeStream(
      fetch("/api/scan/barcode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ barcode }),
        credentials: "include",
        signal: abort.signal,
      }),
      get,
      set,
    );
  },

  startPhotoStream: (file) => {
    const prevAbort = get()._abort;
    prevAbort?.abort();

    const abort = new AbortController();
    const formData = new FormData();
    formData.append("file", file);

    set({ scanId: null, productBarcode: null, status: "streaming", partial: {}, _abort: abort });

    _consumeStream(
      fetch("/api/scan/photo", {
        method: "POST",
        body: formData,
        credentials: "include",
        signal: abort.signal,
      }),
      get,
      set,
    );
  },

  clearStream: () => {
    get()._abort?.abort();
    set({ scanId: null, productBarcode: null, status: "idle", partial: {}, _abort: null });
  },

  _handleEvent: (eventName, data) => {
    const d = data as Record<string, unknown>;
    switch (eventName) {
      case "init":
        set({ scanId: String(d.scan_id), productBarcode: String(d.product_barcode) });
        break;
      case "ingredients":
        set((s) => ({
          partial: {
            ...s.partial,
            productName: d.product_name as string | undefined,
            productBrand: d.product_brand as string | undefined,
            ingredients: d.ingredients as IngredientResult[],
          },
        }));
        break;
      case "insights":
        set((s) => ({
          partial: {
            ...s.partial,
            personalized_insights: d.personalized_insights as PersonalizedInsight[],
          },
        }));
        break;
      case "semaphore":
        set((s) => ({
          partial: {
            ...s.partial,
            semaphore: d.semaphore as string,
            conflict_severity: d.conflict_severity as string | null,
            ingredients: (d.ingredients as IngredientResult[]) ?? s.partial.ingredients,
          },
        }));
        break;
      case "done":
        set({ status: "done" });
        break;
      case "error":
        set({ status: "error" });
        break;
    }
  },
}));

async function _consumeStream(
  fetchPromise: Promise<Response>,
  get: () => ScanStreamingState,
  set: (partial: Partial<ScanStreamingState>) => void,
) {
  try {
    const response = await fetchPromise;
    if (!response.ok || !response.body) {
      set({ status: "error" });
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let currentEvent = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith("event:")) {
          currentEvent = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          const rawData = line.slice(5).trim();
          try {
            const parsed = JSON.parse(rawData);
            get()._handleEvent(currentEvent, parsed);
          } catch {
            // línea de datos malformada — ignorar
          }
          currentEvent = "";
        }
      }
    }
  } catch (err) {
    if ((err as Error).name !== "AbortError") {
      set({ status: "error" });
    }
  }
}
```

- [x] **Step 2: Verificar que TypeScript compila sin errores**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep scanning
```

Esperado: sin errores.

- [x] **Step 3: Commit**

```bash
git add frontend/lib/stores/scanning.ts
git commit -m "feat(frontend): add scanStreamingStore Zustand slice"
```

---

### Task 6: Actualizar `scan/page.tsx` para usar el store

**Files:**
- Modify: `frontend/app/(app)/scan/page.tsx`

- [x] **Step 1: Reemplazar mutations por `startStream()`**

Localizar la lógica de `barcodeMutation` y `photoMutation` y reemplazar:

```typescript
// ANTES — en el handler de barcode:
const barcodeMutation = useMutation({
  mutationFn: (barcode: string) => scanBarcode(barcode),
  onSuccess: (data) => {
    queryClient.setQueryData(["scan", data.product_barcode], data);
    router.push(`/scan/${encodeURIComponent(data.product_barcode)}`);
  },
});

// DESPUÉS — en el componente, agregar:
const { startBarcodeStream, startPhotoStream, scanId, status } = useScanStreamingStore();
const router = useRouter();

// El store emite evento "init" con scan_id; navegar cuando scanId aparece.
// Usar useEffect para detectar transición idle → scanId disponible.
```

Agregar el `useEffect` de navegación:

```typescript
import { useScanStreamingStore } from "@/lib/stores/scanning";

// Dentro del componente:
const { startBarcodeStream, startPhotoStream, scanId, status } = useScanStreamingStore();
const router = useRouter();
const navigatedRef = useRef(false);

useEffect(() => {
  if (scanId && status === "streaming" && !navigatedRef.current) {
    navigatedRef.current = true;
    router.push(`/scan/${scanId}`);
  }
  if (status === "idle") {
    navigatedRef.current = false;
  }
}, [scanId, status, router]);

// Handler de barcode:
const handleBarcodeSubmit = (barcode: string) => {
  startBarcodeStream(barcode);
};

// Handler de foto:
const handlePhotoSubmit = (file: File) => {
  startPhotoStream(file);
};
```

- [x] **Step 2: Verificar que TypeScript compila**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "scan/page"
```

Esperado: sin errores.

- [x] **Step 3: Commit**

```bash
git add frontend/app/\(app\)/scan/page.tsx
git commit -m "feat(frontend): replace scan mutations with startStream store calls"
```

---

### Task 7: Actualizar `/scan/[id]/page.tsx` para leer del store

**Files:**
- Modify: `frontend/app/(app)/scan/[id]/page.tsx`

- [x] **Step 1: Agregar lectura del store y cleanup**

En el componente `ScanResultInner` (o el componente que usa `useQuery`):

```typescript
import { useScanStreamingStore } from "@/lib/stores/scanning";

// Dentro del componente:
const { status: streamStatus, partial, clearStream } = useScanStreamingStore();
const isStreaming = streamStatus === "streaming";

// Cleanup en unmount para evitar state stale en back-navigation.
useEffect(() => {
  return () => {
    clearStream();
  };
}, [clearStream]);
```

Mostrar datos parciales mientras streaming está activo. Patrón: si `isStreaming && !data`, mostrar skeleton progresivo con lo que haya en `partial`. Si `data` ya está disponible (del GET), usar `data` directamente.

```typescript
// Renderizado condicional:
const displayData = data ?? (isStreaming ? buildPartialDisplay(partial) : null);

if (!displayData && !isStreaming) return <ScanErrorState />;
if (!displayData && isStreaming) return <ScanStreamingSkeleton partial={partial} />;
```

Helper `buildPartialDisplay()` — construye un objeto mínimo compatible con `ScanResponse` desde el estado parcial del stream:

```typescript
function buildPartialDisplay(partial: ScanPartial) {
  return {
    product_name: partial.productName ?? null,
    product_brand: partial.productBrand ?? null,
    ingredients: partial.ingredients ?? [],
    personalized_insights: partial.personalized_insights ?? [],
    semaphore: partial.semaphore ?? null,
    conflict_severity: partial.conflict_severity ?? null,
    scanned_at: new Date().toISOString(),
    show_barcode_cta: false,
    source: "barcode" as const,
  };
}
```

Al recibir el evento `done`, el store pone `status: "done"`. El `useQuery` con `staleTime: 30min` debe hacer un fetch final para poblar el cache con el resultado completo. Agregar:

```typescript
useEffect(() => {
  if (streamStatus === "done") {
    queryClient.invalidateQueries({ queryKey: ["scan", id] });
  }
}, [streamStatus, id, queryClient]);
```

- [x] **Step 2: Verificar que TypeScript compila**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep "\[id\]/page"
```

Esperado: sin errores.

- [x] **Step 3: Correr los E2E tests existentes para verificar regresiones**

```bash
cd /Users/albertofragoso/Desktop/IA_engineer/bio_shield && npx playwright test tests/specs/scan/ --reporter=list 2>&1 | tail -20
```

Esperado: sin nuevas regresiones.

- [x] **Step 4: Commit**

```bash
git add frontend/app/\(app\)/scan/\[id\]/page.tsx
git commit -m "feat(frontend): read from scanStreamingStore during active stream"
```

---

### Task 8: Full test suite + lint

- [x] **Step 1: Correr suite completa del backend**

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Esperado: todos verdes. Si hay fallos, corregir antes de continuar.

- [x] **Step 2: Ruff + mypy**

```bash
cd backend && ruff check . && mypy app/ --ignore-missing-imports 2>&1 | tail -20
```

Esperado: sin errores de tipo ni linting.

- [x] **Step 3: TypeScript check del frontend completo**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -20
```

Esperado: sin errores.

- [x] **Step 4: Commit final de cleanup si aplica**

```bash
git add -p  # revisar y stagear solo fixes de lint/tipos
git commit -m "fix(scan): lint and type fixes for streaming pipeline"
```

---

## Verificación manual

1. Con backend corriendo:
```bash
curl -N -X POST http://localhost:8000/scan/barcode \
  -H "Cookie: access_token=<jwt>" \
  -H "Content-Type: application/json" \
  -d '{"barcode":"7501055301157"}' \
  --no-buffer
```
Debe mostrar chunks incrementales, NO todo al final.

2. Network tab: response es `text/event-stream`, eventos llegan progresivamente.

3. `/scan/[id]` no muestra 404 en ningún punto del stream (fila pending existe desde el evento `init`).

4. Al fallar el pipeline: UI muestra `ScanErrorState`, no skeleton indefinido.
