# OFFContributeToggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar el componente `OFFContributeToggle` en la pantalla de resultado de scan para foto-scans, conectándolo al endpoint `POST /scan/contribute` del backend.

**Architecture:** Componente autónomo `OFFContributeToggle` que recibe `ScanResponse` y maneja internamente su propia `useMutation`. La página de resultado lo renderiza condicionalmente cuando `data.source === "photo"`, entre el acordeón de ingredientes y la sección "Para ti". Los tests E2E mockan `POST /scan/contribute` con `page.route()` siguiendo el patrón existente de la suite.

**Tech Stack:** Next.js 16 App Router, TanStack Query v5 (`useMutation`), Playwright E2E, TypeScript strict.

---

## Mapa de archivos

| Acción | Archivo | Responsabilidad |
|--------|---------|-----------------|
| Modificar | `tests/fixtures/factories.ts` | Agregar `makeOFFContributeResponse` |
| Modificar | `tests/fixtures/api-mocks.ts` | Agregar `mockContributeOff`, `mockContributeOffError` |
| Crear | `tests/specs/scan/off-contribute.spec.ts` | 4 tests E2E del flujo |
| Crear | `frontend/components/scanner/OFFContributeToggle.tsx` | Componente autónomo con máquina de estados |
| Modificar | `frontend/app/(app)/scan/[id]/page.tsx` | Renderizado condicional del toggle |
| Modificar | `frontend/app/(app)/scan/page.tsx` | Eliminar comentario placeholder `[FASE 2]` |
| Modificar | `.claude/plans/frontend.md` | Actualizar estado de OFFContributeToggle |

---

## Task 1: Agregar helpers de fixture para `POST /scan/contribute`

**Files:**
- Modify: `tests/fixtures/factories.ts`
- Modify: `tests/fixtures/api-mocks.ts`

- [ ] **Step 1: Agregar `makeOFFContributeResponse` a factories.ts**

Abrir `tests/fixtures/factories.ts` y al final del archivo, después de `makeOrangeBiomarkerScan`, agregar:

```ts
export const makeOFFContributeResponse = (
  overrides: Partial<import("../../frontend/lib/api/types").OFFContributeResponse> = {},
): import("../../frontend/lib/api/types").OFFContributeResponse => ({
  contribution_id: "contrib-00000000-0001",
  status: "PENDING",
  message: "Contribution received and queued",
  ...overrides,
});
```

- [ ] **Step 2: Agregar mocks a api-mocks.ts**

En `tests/fixtures/api-mocks.ts`, en la sección `// ── Scan ──`, después de `mockScanHistory`, agregar:

```ts
export async function mockContributeOff(
  page: Page,
  response: import("../../frontend/lib/api/types").OFFContributeResponse = makeOFFContributeResponse(),
) {
  await page.route("**/scan/contribute", (route) => json(route, 202, response));
}

export async function mockContributeOffError(page: Page) {
  await page.route("**/scan/contribute", (route) =>
    json(route, 500, { detail: "Error interno del servidor" }),
  );
}
```

- [ ] **Step 3: Verificar que `makeOFFContributeResponse` está disponible en el barrel**

`tests/fixtures/index.ts` ya tiene `export * from "./factories"` y `export * from "./api-mocks"` — no requiere cambios. Solo verificar:

```bash
grep "makeOFFContributeResponse\|mockContributeOff" tests/fixtures/factories.ts tests/fixtures/api-mocks.ts
```

Salida esperada: las dos líneas con las definiciones recién agregadas.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/factories.ts tests/fixtures/api-mocks.ts
git commit -m "test(fixtures): add OFFContribute mocks and factory"
```

---

## Task 2: Escribir los tests E2E (failing)

**Files:**
- Create: `tests/specs/scan/off-contribute.spec.ts`

- [ ] **Step 1: Crear el archivo de tests**

```ts
// tests/specs/scan/off-contribute.spec.ts
import {
  test,
  expect,
  mockScanBarcode,
  mockScanResultGet,
  mockContributeOff,
  mockContributeOffError,
  makeScanResponse,
  makeIngredient,
} from "../../fixtures";

const PHOTO_ID = "photo-off-test-00001";

const photoScan = makeScanResponse({
  product_barcode: PHOTO_ID,
  product_name: "Galletas Demo",
  source: "photo",
  ingredients: [
    makeIngredient({ name: "Harina de trigo" }),
    makeIngredient({ name: "Azúcar" }),
  ],
});

test.describe("Feature: OFF contribute toggle", () => {
  test("default — toggle is off and ENVIAR button is absent", async ({ mockedPage }) => {
    await mockScanResultGet(mockedPage, photoScan);
    await mockedPage.goto(`/scan/${PHOTO_ID}`);

    const toggle = mockedPage.getByRole("switch", { name: /contribuir a open food facts/i });
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveAttribute("aria-checked", "false");
    await expect(mockedPage.getByRole("button", { name: /enviar/i })).not.toBeVisible();
  });

  test("happy path — activate toggle → ENVIAR → success banner", async ({ mockedPage }) => {
    await mockScanResultGet(mockedPage, photoScan);
    await mockContributeOff(mockedPage);
    await mockedPage.goto(`/scan/${PHOTO_ID}`);

    const toggle = mockedPage.getByRole("switch", { name: /contribuir a open food facts/i });
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-checked", "true");

    const enviarBtn = mockedPage.getByRole("button", { name: /enviar/i });
    await expect(enviarBtn).toBeVisible();
    await enviarBtn.click();

    await expect(mockedPage.getByText(/contribución enviada/i)).toBeVisible();
    await expect(toggle).not.toBeVisible();
  });

  test("error — failed POST shows error banner with Reintentar button", async ({ mockedPage }) => {
    await mockScanResultGet(mockedPage, photoScan);
    await mockContributeOffError(mockedPage);
    await mockedPage.goto(`/scan/${PHOTO_ID}`);

    await mockedPage.getByRole("switch", { name: /contribuir a open food facts/i }).click();
    await mockedPage.getByRole("button", { name: /enviar/i }).click();

    await expect(mockedPage.getByText(/error al enviar/i)).toBeVisible();
    await expect(mockedPage.getByRole("button", { name: /reintentar/i })).toBeVisible();
  });

  test("not rendered for barcode scan", async ({ mockedPage }) => {
    const barcodeScan = makeScanResponse({ source: "barcode" });
    await mockScanBarcode(mockedPage, barcodeScan);
    await mockedPage.goto(`/scan/${barcodeScan.product_barcode}`);

    await expect(
      mockedPage.getByRole("switch", { name: /contribuir a open food facts/i }),
    ).not.toBeVisible();
  });
});
```

- [ ] **Step 2: Ejecutar para confirmar que fallan por la razón correcta**

```bash
cd /ruta/al/repo && pnpm test:e2e -- --grep "OFF contribute" 2>&1 | tail -20
```

Salida esperada: 4 tests FAILED con mensajes tipo `Expected: visible / Received: hidden` o `Locator not found`. Si hay errores de compilación TypeScript, corregirlos antes de continuar.

- [ ] **Step 3: Commit de los tests en rojo**

```bash
git add tests/specs/scan/off-contribute.spec.ts
git commit -m "test(e2e): off-contribute toggle — 4 failing specs"
```

---

## Task 3: Crear el componente `OFFContributeToggle`

**Files:**
- Create: `frontend/components/scanner/OFFContributeToggle.tsx`

- [ ] **Step 1: Crear el componente**

```tsx
"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { contributeToOff } from "@/lib/api/scan";
import type { ScanResponse } from "@/lib/api/types";

interface Props {
  scanData: ScanResponse;
}

export function OFFContributeToggle({ scanData }: Props) {
  const [enabled, setEnabled] = useState(false);
  const [succeeded, setSucceeded] = useState(false);

  const mutation = useMutation({
    mutationFn: () =>
      contributeToOff({
        barcode: scanData.product_barcode,
        ingredients: scanData.ingredients.map((i) => i.name),
        consent: true,
      }),
    onSuccess: () => setSucceeded(true),
  });

  const isLoading = mutation.isPending;
  const isError = mutation.isError;

  function handleToggle() {
    if (isLoading) return;
    setEnabled((prev) => !prev);
    mutation.reset();
  }

  function handleSubmit() {
    mutation.mutate();
  }

  function handleRetry() {
    mutation.reset();
    mutation.mutate();
  }

  if (succeeded) {
    return (
      <div
        className="px-4 py-3 rounded-input flex items-center gap-3"
        style={{ background: "rgba(74,222,128,.06)", border: "1px solid rgba(74,222,128,.25)" }}
      >
        <span className="font-mono text-[14px]" style={{ color: "#4ADE80" }}>
          ✓
        </span>
        <div>
          <p className="font-mono text-[11px] text-brand-green uppercase tracking-[0.08em]">
            CONTRIBUCIÓN ENVIADA
          </p>
          <p className="font-sans text-[12px] text-subtext mt-0.5">
            Gracias. Los datos estarán en Open Food Facts pronto.
          </p>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div
        className="px-4 py-3 rounded-input flex items-center justify-between gap-4"
        style={{ background: "rgba(248,113,113,.06)", border: "1px solid rgba(248,113,113,.2)" }}
      >
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.08em]" style={{ color: "#F87171" }}>
            ERROR AL ENVIAR
          </p>
          <p className="font-sans text-[12px] text-subtext mt-0.5">
            No se pudo enviar la contribución.
          </p>
        </div>
        <button
          onClick={handleRetry}
          className="shrink-0 px-3 py-1.5 rounded-button font-mono text-[10px] uppercase tracking-[0.08em] transition-opacity hover:opacity-70"
          style={{
            background: "rgba(248,113,113,.1)",
            border: "1px solid rgba(248,113,113,.3)",
            color: "#F87171",
          }}
        >
          REINTENTAR
        </button>
      </div>
    );
  }

  return (
    <div
      className="px-4 py-3 rounded-input flex items-center justify-between gap-4"
      style={{
        background: enabled ? "rgba(74,222,128,.04)" : "rgba(255,255,255,.02)",
        border: `1px solid ${enabled ? "rgba(74,222,128,.2)" : "rgba(255,255,255,.06)"}`,
        transition: "all 0.2s",
      }}
    >
      <div className="flex-1 min-w-0">
        <p
          className="font-mono text-[11px] uppercase tracking-[0.08em]"
          style={{ color: enabled ? "#4ADE80" : "#94a3b8" }}
        >
          CONTRIBUIR A OPEN FOOD FACTS
        </p>

        {isLoading ? (
          <p className="font-sans text-[12px] text-subtext mt-0.5 flex items-center gap-1.5">
            <Spinner />
            Enviando contribución…
          </p>
        ) : enabled ? (
          <>
            <p className="font-sans text-[12px] text-subtext mt-0.5">
              Se compartirá: barcode · ingredientes detectados
            </p>
            <button
              onClick={handleSubmit}
              className="mt-2 px-3 py-1.5 rounded-button font-mono text-[10px] uppercase tracking-[0.08em] text-brand-green transition-all hover:opacity-80"
              style={{
                background: "rgba(74,222,128,.12)",
                border: "1px solid rgba(74,222,128,.35)",
              }}
            >
              ENVIAR →
            </button>
          </>
        ) : (
          <p className="font-sans text-[12px] text-subtext mt-0.5">
            Ayuda a identificar este producto a otros usuarios
          </p>
        )}
      </div>

      {!isLoading && (
        <button
          role="switch"
          aria-checked={enabled}
          aria-label="Contribuir a Open Food Facts"
          onClick={handleToggle}
          className="shrink-0"
          style={{
            width: "40px",
            height: "22px",
            borderRadius: "11px",
            border: `1px solid ${enabled ? "rgba(74,222,128,.5)" : "rgba(255,255,255,.1)"}`,
            background: enabled ? "rgba(74,222,128,.25)" : "rgba(255,255,255,.06)",
            display: "flex",
            alignItems: "center",
            padding: "3px",
            cursor: "pointer",
            transition: "all 0.2s",
          }}
        >
          <span
            style={{
              width: "15px",
              height: "15px",
              borderRadius: "50%",
              background: enabled ? "#4ADE80" : "#334155",
              marginLeft: enabled ? "auto" : "0",
              boxShadow: enabled ? "0 0 6px rgba(74,222,128,.6)" : "none",
              transition: "all 0.2s",
              display: "block",
            }}
          />
        </button>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <svg
      width="11"
      height="11"
      viewBox="0 0 14 14"
      fill="none"
      className="animate-spin shrink-0"
      aria-hidden
    >
      <circle
        cx="7"
        cy="7"
        r="5.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeDasharray="22"
        strokeDashoffset="10"
        strokeLinecap="round"
      />
    </svg>
  );
}
```

- [ ] **Step 2: Verificar que TypeScript compila sin errores**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep -i "OFFContributeToggle\|error"
```

Salida esperada: sin output (sin errores en el archivo nuevo).

- [ ] **Step 3: Commit**

```bash
git add frontend/components/scanner/OFFContributeToggle.tsx
git commit -m "feat(scanner): add OFFContributeToggle component"
```

---

## Task 4: Wiring en `scan/[id]/page.tsx`

**Files:**
- Modify: `frontend/app/(app)/scan/[id]/page.tsx`

- [ ] **Step 1: Agregar el import**

En `frontend/app/(app)/scan/[id]/page.tsx`, en el bloque de imports (después de `import { PhotoLoadingState ...}`), agregar:

```tsx
import { OFFContributeToggle } from "@/components/scanner/OFFContributeToggle";
```

- [ ] **Step 2: Insertar el toggle en el JSX**

En `ScanResultInner`, localizar el bloque que inicia con `{/* ── Row 2: Para Ti — fila dedicada ── */}` (línea ~311). Insertar **antes** de ese div:

```tsx
{/* ── OFF Contribute — foto scans only ── */}
{data.source === "photo" && (
  <div className="pt-2" style={{ borderTop: "1px solid rgba(74,222,128,.08)" }}>
    <OFFContributeToggle scanData={data} />
  </div>
)}
```

El resultado debe quedar así:

```tsx
      {/* ── OFF Contribute — foto scans only ── */}
      {data.source === "photo" && (
        <div className="pt-2" style={{ borderTop: "1px solid rgba(74,222,128,.08)" }}>
          <OFFContributeToggle scanData={data} />
        </div>
      )}

      {/* ── Row 2: Para Ti — fila dedicada ── */}
      <div className="pt-2" style={{ borderTop: "1px solid rgba(74,222,128,.08)" }}>
        {data.personalized_insights.length > 0 ? (
```

- [ ] **Step 3: Verificar TypeScript**

```bash
cd frontend && pnpm tsc --noEmit 2>&1 | grep -i "error"
```

Salida esperada: sin output.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/\(app\)/scan/\[id\]/page.tsx
git commit -m "feat(result): wire OFFContributeToggle for photo scans"
```

---

## Task 5: Limpiar placeholder en `scan/page.tsx`

**Files:**
- Modify: `frontend/app/(app)/scan/page.tsx`

- [ ] **Step 1: Eliminar el comentario placeholder**

En `frontend/app/(app)/scan/page.tsx`, eliminar la línea 246:

```tsx
              {/* [FASE 2] OFFContributeToggle — pendiente de implementar */}
```

El bloque del tab de foto queda simplemente:

```tsx
          {isPhotoLoading ? (
            <PhotoLoadingState />
          ) : (
            <div className="flex flex-col gap-4">
              <PhotoCapture onCapture={handlePhotoCapture} disabled={false} />

              {photoStatus === "error_read" && (
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\(app\)/scan/page.tsx
git commit -m "chore(scan): remove [FASE 2] OFFContributeToggle placeholder comment"
```

---

## Task 6: Ejecutar la suite E2E y verificar los 4 tests

- [ ] **Step 1: Asegurarse de que el frontend y backend están corriendo**

```bash
# Terminal 1 — backend
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && pnpm dev
```

- [ ] **Step 2: Correr solo los tests del toggle**

```bash
pnpm test:e2e -- --grep "OFF contribute"
```

Salida esperada:
```
✓ default — toggle is off and ENVIAR button is absent
✓ happy path — activate toggle → ENVIAR → success banner
✓ error — failed POST shows error banner with Reintentar button
✓ not rendered for barcode scan
4 passed
```

- [ ] **Step 3: Correr la suite completa para detectar regresiones**

```bash
pnpm test:e2e
```

Salida esperada: todos los tests previos siguen en verde. Si algún test rompe, investigar antes de continuar.

- [ ] **Step 4: Verificar que no quedan cambios sin commitear**

```bash
git status
```

Salida esperada: `nothing to commit, working tree clean`. Si hay archivos sin commitear, agregarlos antes de continuar con el Task 7.

---

## Task 7: Actualizar `.claude/plans/frontend.md`

**Files:**
- Modify: `.claude/plans/frontend.md`

- [ ] **Step 1: Actualizar sección 7.0 — tabla de componentes**

Localizar la fila de `OFFContributeToggle [FASE 2]` y actualizar:
- Cambiar descripción de "shadcn Switch + Tooltip + copy ODbL + `POST /scan/contribute`" a reflejar que vive en `/scan/[id]` (no en `/scan` tab foto)
- Eliminar el marcador `[FASE 2]`

La fila actualizada debe ser:

```
| `OFFContributeToggle` | `/scan/[id]` resultado | — (único consumer) | Autónomo con `useMutation`; visible solo cuando `source="photo"`, entre ingredientes y "Para ti"; estados: off/on/loading/success/error |
```

- [ ] **Step 2: Actualizar sección 7.3 — checks de éxito**

Localizar los 4 bullets `[FASE 2]` en la sección 7.3 y reemplazarlos con un bloque `✅`:

```markdown
**OFF Contribute ✅ IMPLEMENTADO:**
- Toggle visible solo cuando `source="photo"` en `/scan/[id]`, entre ingredientes y "Para ti".
- Toggle off por defecto → activar → botón "ENVIAR" aparece → POST → estado success/error.
- Con toggle off → `POST /scan/contribute` no se dispara bajo ninguna circunstancia.
- Si `/scan/contribute` retorna 5xx → banner rojo "Error al enviar" + botón "Reintentar".
```

- [ ] **Step 3: Actualizar sección 7.4 — checks de éxito**

Al final de los checks de éxito de 7.4 agregar:

```markdown
- `source="photo"`: OFFContributeToggle visible entre ingredientes y "Para ti".
- `source="barcode"`: OFFContributeToggle ausente del DOM.
```

- [ ] **Step 4: Actualizar Fase E — casos E2E**

En la sección "Scan — photo", después del caso 17, agregar:

```markdown
### OFF Contribute
18b. **Toggle off por defecto:** toggle `aria-checked=false`; botón ENVIAR ausente.
18c. **Happy path contribute:** toggle on → ENVIAR → banner "Contribución enviada".
18d. **Error contribute:** POST 500 → banner rojo + botón Reintentar visible.
18e. **No se renderiza en barcode scan:** `source="barcode"` → toggle ausente.
```

- [ ] **Step 5: Actualizar estimación de esfuerzo**

En la tabla de la sección "Estimación de esfuerzo", la fila `D.7.3` ya dice `✅ done`. Agregar nota al pie:

```markdown
| D.7.3 — OFF Contribute Toggle | ✅ done (implementado 2026-04-29) | — |
```

- [ ] **Step 6: Commit final**

```bash
git add .claude/plans/frontend.md
git commit -m "docs(plan): mark OFFContributeToggle as implemented, update E2E cases"
```
