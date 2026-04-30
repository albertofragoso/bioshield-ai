# OFFContributeToggle — Design Spec

**Fecha:** 2026-04-29
**Branch:** feat/off-contribute-toggle (pendiente crear)
**Estado:** aprobado, listo para implementar

---

## Contexto

El backend tiene un endpoint `POST /scan/contribute` completo y testeado (commit `9179f60`).
El frontend tiene la función `contributeToOff()` en `lib/api/scan.ts` y los tipos
`OFFContributeRequest / OFFContributeResponse` en `lib/api/types.ts`.

Lo que faltaba era el componente UI y el wiring en la página de resultado.
El placeholder `{/* [FASE 2] OFFContributeToggle — pendiente de implementar */}` en
`scan/page.tsx:246` será eliminado como parte de esta implementación.

---

## Decisiones de diseño

### Ubicación
El toggle vive en `/scan/[id]` (pantalla de resultado), **no** en el tab de foto de `/scan`.

Razón: `OFFContributeRequest` requiere `barcode` e `ingredients[]`, datos que solo existen
después de que el backend procesa el scan. En el resultado el usuario además ve exactamente
qué va a compartir, haciendo el consentimiento completamente informado.

### Condición de renderizado
El componente se monta **solo cuando `data.source === "photo"`**. Para scans de barcode,
el producto ya proviene de Open Food Facts — contribuir los mismos datos no tiene sentido.

### Posición en la página
Full-width entre el acordeón de ingredientes y la sección "Para ti", separado por el
`border-top rgba(74,222,128,.08)` que ya existe como divisor visual.

### Enfoque de implementación
Componente autónomo (Opción A): recibe `scanData: ScanResponse` como única prop y
maneja internamente `useMutation({ mutationFn: contributeToOff })`. La página no
necesita conocer el estado del toggle.

---

## Componente `OFFContributeToggle`

**Archivo:** `frontend/components/scanner/OFFContributeToggle.tsx`

### Props
```ts
interface Props {
  scanData: ScanResponse;
}
```

### Estados internos
```ts
type ToggleState = "off" | "on" | "loading" | "success" | "error";
```

### Flujo de estados
```
off → (usuario activa toggle) → on
on  → (usuario presiona ENVIAR) → loading
loading → (POST 202) → success
loading → (POST 4xx/5xx) → error
error → (usuario presiona Reintentar) → loading
success → (estado terminal — no reversible)
```

### Payload
```ts
{
  barcode: scanData.product_barcode,
  ingredients: scanData.ingredients.map(i => i.name),
  consent: true,
}
```

`image_base64` y `scan_history_id` se omiten: no están disponibles en `ScanResponse`.

### UI por estado

| Estado | Toggle | Contenido extra |
|--------|--------|-----------------|
| `off` | apagado (gris) | Label "CONTRIBUIR A OPEN FOOD FACTS", sublabel gris |
| `on` | encendido (verde) | Sublabel actualizado + botón "ENVIAR →" |
| `loading` | encendido, deshabilitado | Spinner + "Enviando contribución…" |
| `success` | oculto | Banner verde ✓ "Contribución enviada" + mensaje |
| `error` | encendido | Banner rojo + botón "Reintentar" |

### Tokens visuales
Consistentes con el design system del proyecto:
- Toggle off: `bg rgba(255,255,255,.06)` border `rgba(255,255,255,.1)` thumb `#334155`
- Toggle on: `bg rgba(74,222,128,.25)` border `rgba(74,222,128,.5)` thumb `#4ADE80`
- Banner success: border `rgba(74,222,128,.25)` icon `✓` color `#4ADE80`
- Banner error: border `rgba(248,113,113,.25)` color `#F87171`
- Fuente labels: JetBrains Mono uppercase tracking `0.08em`
- Fuente sublabel: Space Grotesk 12px `#475569`

---

## Modificaciones a `scan/[id]/page.tsx`

1. Importar `OFFContributeToggle`.
2. Renderizar condicionalmente en el separador entre el acordeón de ingredientes y la
   sección "Para ti" (Row 2 del layout). El botón "Reportar" deshabilitado permanece
   donde está — en la columna izquierda sticky, no tiene relación con el toggle:
```tsx
{/* Entre el cierre del acordeón de ingredientes y el div de Para Ti */}
{data.source === "photo" && (
  <div className="pt-2" style={{ borderTop: "1px solid rgba(74,222,128,.08)" }}>
    <OFFContributeToggle scanData={data} />
  </div>
)}
```

---

## Modificaciones a `scan/page.tsx`

Eliminar el comentario placeholder en la línea 246:
```tsx
{/* [FASE 2] OFFContributeToggle — pendiente de implementar */}
```

---

## Tests E2E

**Archivo:** `tests/specs/scan/off-contribute.spec.ts`

Fixture: `page.route()` sobre `GET /scan/result/*` devuelve `ScanResponse` con
`source: "photo"`, `product_barcode: "photo-test-123"`, e `ingredients` con 2 items.

| # | Caso | Mock | Assertion |
|---|------|------|-----------|
| 1 | Toggle off por defecto | — | Toggle desactivado; botón "ENVIAR" ausente del DOM |
| 2 | Happy path | `POST /scan/contribute → 202` | Toggle on → ENVIAR → spinner → banner "Contribución enviada" |
| 3 | Error + reintentar | `POST /scan/contribute → 500` | Banner error visible + botón "Reintentar" presente |
| 4 | No se renderiza en barcode scan | fixture con `source: "barcode"` | Componente ausente del DOM |

---

## Actualizaciones de documentación

- `.claude/plans/frontend.md` — sección 7.0: descripción de `OFFContributeToggle` actualizada
  (placement en resultado, no en scan tab); marcador `[FASE 2]` eliminado
- `.claude/plans/frontend.md` — sección 7.3: checks de éxito `[FASE 2]` marcados como completados
- `.claude/plans/frontend.md` — sección 7.4: agregar check de éxito para el toggle
- `.claude/plans/frontend.md` — Fase E: agregar casos de test del toggle en "Scan — photo"
- `.claude/CLAUDE.md` — sección "Tests E2E" ya actualizada
- `frontend/CLAUDE.md` — sección "Tests E2E" ya actualizada

---

## Archivos que NO cambian

- `frontend/lib/api/scan.ts` — `contributeToOff()` ya existe
- `frontend/lib/api/types.ts` — tipos ya existen
- Backend — endpoint ya implementado y testeado
