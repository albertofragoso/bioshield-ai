# Streaming Progresivo del Pipeline de Scan

**Fecha:** 2026-05-21  
**Estado:** Aprobado — listo para implementación  
**Spec relacionado:** —

---

## Contexto

El pipeline de scan actual (`POST /scan/barcode`, `POST /scan/photo`) usa `graph.ainvoke()` y bloquea la UI durante ~8-12 segundos. El usuario ve un spinner sin ningún feedback hasta que todo el grafo termina.

`calculate_risk` lee `personalized_insights` del state para elevar el semáforo a ORANGE cuando los insights tienen conflictos. Por eso los nodos **no pueden reordenarse** — el orden actual `personalize → calculate_risk` es una dependencia de datos, no solo de ejecución.

**El orden de streaming viable es:**
1. ~2-3s — ingredientes (tras `identify_product`/`extract_ingredients`)
2. ~8-10s — personalized insights (tras `personalize`)
3. ~10-12s — semáforo (tras `calculate_risk` — ÚLTIMO, depende de insights)

---

## Arquitectura

### Backend

**Cambio principal:** `graph.ainvoke()` → `graph.astream_events()` en `backend/app/routers/scan.py`.

El endpoint retorna `StreamingResponse(content_type="text/event-stream")` con headers:

```python
headers={
    "X-Accel-Buffering": "no",   # evita buffering en nginx/Render.com
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}
```

**Inserción anticipada de la fila (bloqueante):**  
Antes de llamar `astream_events()`, se inserta `ScanHistory` con `status='pending'` y `result_json=None`. Esto garantiza que el `scan_id` existe en DB cuando el frontend navega a `/scan/[id]` al recibir el primer evento.

**Eventos SSE emitidos (orden):**

```
event: init
data: {"scan_id": "<uuid>", "product_barcode": "<barcode_or_photo_id>"}

event: ingredients
data: {"product_name": "...", "product_brand": "...", "ingredients": [...], "source": "barcode"}

event: insights
data: {"personalized_insights": [...]}

event: semaphore
data: {"semaphore": "ORANGE", "conflict_severity": "HIGH", "ingredients": [...with conflicts...]}

event: done
data: {"scan_id": "..."}

event: error   # emitido solo en caso de falla del pipeline
data: {"message": "Pipeline failed", "code": "PIPELINE_ERROR"}
```

El `event: error` se emite dentro de un `try/except` en el generator. El cliente puede manejar errores explícitamente en lugar de ver el stream cerrado sin señal.

**`_persist_scan_history()` se llama una sola vez** al recibir el evento `on_chain_end` de `calculate_risk` (el último nodo), actualizando la fila insertada con `result_json` completo y `status='done'`. No hay doble INSERT.

**Parsing de `astream_events()`:**  
LangGraph emite eventos con shape `{"event": "on_chain_end", "name": "<node_name>", "data": {...}}`. El servidor filtra por `event == "on_chain_end"` y `name in {"identify_product", "extract_ingredients", "personalize", "calculate_risk"}` para emitir los SSE correspondientes.

### Frontend

**Zustand store `scanStreamingStore`:**  
Vive en el root layout (`app/layout.tsx`) — nunca se desmonta entre navegaciones. Expone:

```typescript
interface ScanStreamingState {
  scanId: string | null
  status: 'idle' | 'streaming' | 'done' | 'error'
  partial: {
    productName?: string
    ingredients?: IngredientResult[]
    personalized_insights?: PersonalizedInsight[]
    semaphore?: SemaphoreColor
    conflict_severity?: string
  }
  startStream: (type: 'barcode' | 'photo', input: string | File) => void
  clearStream: () => void
}
```

**`startStream()` inicia el fetch y mantiene el `AbortController` en el store** (no en un `useEffect`). Así el fetch sobrevive el desmontaje del componente que lo inició. El cleanup del stream es responsabilidad del store, no de React lifecycle.

**Flujo de navegación:**
1. Scanner page llama `startStream('barcode', barcode)`
2. Al recibir evento `init`, el store guarda `scanId`; scanner page navega a `/scan/[scanId]`
3. `/scan/[id]` lee de `scanStreamingStore` mientras `status === 'streaming'`
4. Al recibir `done`, el store hace `queryClient.setQueryData(["scan", scanId], fullResult)` y llama `clearStream()`
5. `/scan/[id]` pasa a leer de TanStack Query normalmente

**Cleanup en unmount de `/scan/[id]`:**  
El page component llama `clearStream()` en su cleanup para evitar state stale en back-navigation.

**Reopen desde historial (sin cambios):**  
`GET /scan/result/{id}` sigue igual. El streaming solo aplica al flujo de scan nuevo.

---

## Error handling

- **Pipeline falla mid-stream:** el generator emite `event: error` y cierra. El store pone `status: 'error'`; la UI muestra el error state existente (`ScanErrorState`).
- **Conexión cortada (mobile/offline):** no se implementa reconexión automática en esta iteración (out of scope). El usuario puede re-escanear.
- **Fila pending si pipeline falla:** si el pipeline falla antes de `_persist_scan_history()`, la fila queda con `status='pending'` y `result_json=null`. Un cron job de limpieza (o la próxima ingesta) puede limpiarlas.

---

## Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `backend/app/routers/scan.py` | `ainvoke` → `astream_events`, `StreamingResponse`, inserción pending row |
| `backend/app/models/__init__.py` | campo `status: String(10)` en `ScanHistory` (pending/done) |
| `alembic/versions/` | nueva migration — columna `status` en `scan_history` |
| `frontend/lib/stores/scanning.ts` | nuevo Zustand slice `scanStreamingStore` |
| `frontend/app/layout.tsx` | Provider del store (si no está ya como singleton) |
| `frontend/app/(app)/scan/page.tsx` | llamar `startStream()` en lugar de mutation directa |
| `frontend/app/(app)/scan/[id]/page.tsx` | leer de Zustand cuando `status === 'streaming'`; `clearStream()` en cleanup |

---

## Tests

### Backend (pytest)
- `test_scan_barcode_streams_events` — verifica que el endpoint retorna `text/event-stream` y emite `init`, `ingredients`, `insights`, `semaphore`, `done` en ese orden
- `test_scan_stream_pending_row_created` — verifica que la fila existe en DB antes de que el stream termine
- `test_scan_stream_error_event` — monkeypatcha el pipeline para fallar; verifica que el stream emite `event: error`

### E2E (Playwright)
- `scan_shows_ingredients_before_semaphore` — intercepta el SSE stream y verifica que ingredientes aparecen antes que el semáforo en el DOM
- `scan_navigate_to_result_no_404` — verifica que `/scan/[id]` carga sin 404 durante streaming

---

## Verificación

1. `curl -N -X POST http://localhost:8000/scan/barcode -H "Cookie: ..." -d '{"barcode":"..."}' --no-buffer` — debe mostrar chunks incrementales, no todo al final
2. Network tab: verificar que el response es `text/event-stream` y los eventos llegan progresivamente
3. `/scan/[id]` no debe mostrar 404 ni loading indefinido en ningún punto del stream
4. Con pipeline fallando (monkeypath): UI muestra error state, no skeleton indefinido
